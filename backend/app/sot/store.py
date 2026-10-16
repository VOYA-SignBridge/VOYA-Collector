"""Where SOT physically lives, behind one small interface.

`SotStore` is the seam that keeps publisher/reader testable: tests use
`LocalSotStore` (a temp directory) and production uses `GDriveSotStore`.
Paths are POSIX-style relative to the SOT root (e.g. "Ver1_18072026/labels.csv").
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Protocol

logger = logging.getLogger(__name__)


class SotStore(Protocol):
    def list_version_dirs(self) -> List[str]:
        """Top-level entries that look like version folders (Ver{N}_DDMMYYYY)."""

    def exists(self, rel_path: str) -> bool: ...

    def read_bytes(self, rel_path: str) -> bytes: ...

    def write_bytes(self, rel_path: str, data: bytes) -> None: ...


class SotReadOnlyError(RuntimeError):
    """Raised if a write is attempted on a read-only store (server/VPS)."""


# ---------------------------------------------------------------------------
# Local filesystem store (tests, and an optional on-disk SOT mirror)
# ---------------------------------------------------------------------------

class LocalSotStore:
    def __init__(self, root: Path, *, read_only: bool = False):
        self.root = Path(root)
        self.read_only = read_only
        self.root.mkdir(parents=True, exist_ok=True)

    def _abs(self, rel_path: str) -> Path:
        # Prevent path traversal outside the SOT root.
        p = (self.root / rel_path).resolve()
        if self.root.resolve() not in p.parents and p != self.root.resolve():
            raise ValueError(f"path escapes SOT root: {rel_path!r}")
        return p

    def list_version_dirs(self) -> List[str]:
        from app.sot.manifest import parse_version_name

        return sorted(
            p.name for p in self.root.iterdir() if p.is_dir() and parse_version_name(p.name)
        )

    def exists(self, rel_path: str) -> bool:
        return self._abs(rel_path).exists()

    def read_bytes(self, rel_path: str) -> bytes:
        return self._abs(rel_path).read_bytes()

    def write_bytes(self, rel_path: str, data: bytes) -> None:
        if self.read_only:
            raise SotReadOnlyError(f"store is read-only; refused write to {rel_path!r}")
        p = self._abs(rel_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


# ---------------------------------------------------------------------------
# Google Drive store (production)
# ---------------------------------------------------------------------------

class GDriveSotStore:
    """SotStore backed by the shared Google Drive under a `SOT/` root folder.

    Uses the existing gdrive_client. `read_only=True` (the server default) makes
    any write raise locally BEFORE touching Drive — defense in depth on top of
    the publisher's signing guard and (recommended) Drive Viewer permissions.
    """

    def __init__(self, root_folder: str = "SOT", *, read_only: bool = True):
        self.root_folder = root_folder.strip("/")
        self.read_only = read_only

    def _client(self):
        from app.storage.gdrive_client import get_gdrive_client

        return get_gdrive_client()

    def _find_folder_id(self, client, folder_path: str):
        """Resolve a '/'-path of folders to its Drive id WITHOUT creating any.

        Returns None if any segment is missing — so the reader never writes to
        Drive (unlike ensure_path, which creates). Used for read/list/exists.
        """
        parent = client.root_folder_id or "root"
        for part in [p for p in folder_path.strip("/").split("/") if p]:
            q = (
                f"name='{part}' and '{parent}' in parents "
                "and mimeType='application/vnd.google-apps.folder' and trashed=false"
            )
            res = client.service.files().list(q=q, spaces="drive", fields="files(id)").execute(
                num_retries=client.num_retries
            )
            files = res.get("files", [])
            if not files:
                return None
            parent = files[0]["id"]
        return parent

    def _resolve_file_id(self, client, rel_path: str):
        from pathlib import PurePosixPath

        p = PurePosixPath(f"{self.root_folder}/{rel_path}")
        folder_id = self._find_folder_id(client, p.parent.as_posix())
        if folder_id is None:
            return None
        return client._find_file_by_name(folder_id, p.name)

    def list_version_dirs(self) -> List[str]:
        from app.sot.manifest import parse_version_name

        client = self._client()
        root_id = self._find_folder_id(client, self.root_folder)
        if root_id is None:
            return []
        q = (
            f"'{root_id}' in parents and mimeType='application/vnd.google-apps.folder' "
            "and trashed=false"
        )
        # Paginate: Drive's files().list caps a page at 100 by default. Without
        # following nextPageToken, a SOT with >100 versions would truncate the
        # list — and next_version_name() could then REUSE a version number.
        names: List[str] = []
        page_token = None
        while True:
            res = client.service.files().list(
                q=q,
                spaces="drive",
                fields="nextPageToken, files(name)",
                pageSize=1000,
                pageToken=page_token,
            ).execute(num_retries=client.num_retries)
            names.extend(f.get("name", "") for f in res.get("files", []))
            page_token = res.get("nextPageToken")
            if not page_token:
                break
        return sorted(n for n in names if parse_version_name(n))

    def exists(self, rel_path: str) -> bool:
        return self._resolve_file_id(self._client(), rel_path) is not None

    def read_bytes(self, rel_path: str) -> bytes:
        import tempfile

        client = self._client()
        file_id = self._resolve_file_id(client, rel_path)
        if file_id is None:
            raise FileNotFoundError(f"SOT file not found on Drive: {self.root_folder}/{rel_path}")

        # A legitimately empty catalog file (e.g. raw_uploads.csv with no rows) is
        # 0 bytes, and download_file rejects 0-byte transfers as "corrupt". Ask
        # Drive for the size up front and short-circuit — deterministic, instead of
        # pattern-matching the download error string (which also swallowed real
        # truncated-download errors).
        try:
            meta = client.service.files().get(fileId=file_id, fields="size").execute(
                num_retries=client.num_retries
            )
            size = meta.get("size")
            # Only short-circuit on a KNOWN-zero size. A missing "size" (e.g. a
            # Google-native doc) must fall through to a real download, never be
            # mistaken for an empty file.
            if size is not None and int(size) == 0:
                return b""
        except Exception:
            # Metadata probe failed (e.g. a Google-native doc reports no size) —
            # fall through to the normal download rather than guessing.
            pass

        fd, tmp_path = tempfile.mkstemp(prefix="sot_dl_")
        os.close(fd)
        try:
            client.download_file(file_id, tmp_path)
            return Path(tmp_path).read_bytes()
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def write_bytes(self, rel_path: str, data: bytes) -> None:
        if self.read_only:
            raise SotReadOnlyError(
                f"GDriveSotStore is read-only on this machine; refused write to {rel_path!r}. "
                "Only registered writer machines publish to SOT."
            )
        client = self._client()
        key = f"{self.root_folder}/{rel_path}"
        client.upload_file(data, key, replace_existing=True)


# Convenience text helpers layered on the byte interface.
def read_text(store: SotStore, rel_path: str) -> str:
    return store.read_bytes(rel_path).decode("utf-8")


def write_text(store: SotStore, rel_path: str, text: str) -> None:
    store.write_bytes(rel_path, text.encode("utf-8"))
