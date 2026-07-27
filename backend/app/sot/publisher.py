"""Publish an immutable SOT version — WRITER path (registered machines only).

Guard chain (all must hold, else nothing is written):
  1. A private key exists on this machine (servers don't have one).
  2. Its public key is in the committed authorized_keys.json.
  3. The target version folder does not already exist (versions are immutable).

Only then are the CSVs + schema snapshotted, the manifest signed, and the files
uploaded, with LATEST.json bumped last so a reader never sees a half-written
version pointed to as "latest".
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.sot import keys, manifest as m
from app.sot.store import SotStore, write_text

logger = logging.getLogger(__name__)


class NotRegisteredError(PermissionError):
    """This machine may not publish (no key, or key not in authorized_keys)."""


class VersionExistsError(RuntimeError):
    """Refuse to overwrite an already-published (immutable) version."""


def _count_csv_rows(data: bytes) -> int:
    """Data rows (excludes the header)."""
    text = data.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = sum(1 for _ in reader)
    return max(0, rows - 1)


def publish_version(
    store: SotStore,
    *,
    csv_sources: Dict[str, bytes],
    schema_sql: str,
    schema_version: int,
    required_columns: Dict[str, List[str]],
    machine_name: str,
    private_key_path: Path = keys.DEFAULT_PRIVATE_KEY_PATH,
    authorized_keys_path: Path = keys.AUTHORIZED_KEYS_PATH,
    today: Optional[date] = None,
) -> str:
    """Publish a new version from in-memory CSV bytes. Returns the version name.

    csv_sources maps remote filename -> raw bytes, e.g.
        {"labels.csv": b"...", "samples.csv": b"...", "raw_uploads.csv": b"..."}
    """
    # 1. Guard: must hold a private key that is registered.
    try:
        private_key = keys.load_private_key(private_key_path)
    except FileNotFoundError as exc:
        raise NotRegisteredError(str(exc)) from exc

    my_pub = keys.public_key_b64(private_key)
    authorized = keys.load_authorized_keys(authorized_keys_path)
    if not any(entry.get("public_key") == my_pub for entry in authorized):
        raise NotRegisteredError(
            "This machine's key is not in authorized_keys.json. Register it "
            f"(fingerprint={keys.fingerprint(my_pub)}) and commit before publishing."
        )

    # 2. Immutable version name.
    version = m.next_version_name(store.list_version_dirs(), today)
    if store.exists(f"{version}/{m.MANIFEST_NAME}"):
        raise VersionExistsError(f"{version} already exists; versions are immutable")

    # 3. Hashes + counts over the exact bytes we will upload.
    file_hashes: Dict[str, str] = {}
    row_counts: Dict[str, int] = {}
    for name in m.CATALOG_FILES:
        if name not in csv_sources:
            raise ValueError(f"missing required catalog file: {name}")
        data = csv_sources[name]
        file_hashes[name] = m.sha256_bytes(data)
        row_counts[name] = _count_csv_rows(data)

    schema_bytes = schema_sql.encode("utf-8")
    file_hashes["schema/schema.sql"] = m.sha256_bytes(schema_bytes)

    # 4. Manifest + signature.
    created_at = datetime.now(timezone.utc).isoformat()
    manifest = m.build_manifest(
        version_name=version,
        machine_name=machine_name,
        schema_version=schema_version,
        file_hashes=file_hashes,
        row_counts=row_counts,
        required_columns=required_columns,
        created_at=created_at,
    )
    manifest_canonical = m.canonical_bytes(manifest)
    manifest_sig = keys.sign(private_key, manifest_canonical)

    # 5. Write the version (data + schema + manifest + sig). Manifest LAST among
    #    the version's own files so `exists(manifest)` implies a complete version.
    for name in m.CATALOG_FILES:
        store.write_bytes(f"{version}/{name}", csv_sources[name])
    store.write_bytes(f"{version}/schema/schema.sql", schema_bytes)
    write_text(store, f"{version}/schema/schema_version.txt", str(schema_version))
    store.write_bytes(f"{version}/{m.MANIFEST_NAME}", manifest_canonical)
    write_text(store, f"{version}/{m.MANIFEST_SIG_NAME}", manifest_sig)

    # 6. Bump LATEST last, signed, so readers only follow a fully-written version.
    latest = {
        "version": version,
        "manifest_sha256": m.sha256_bytes(manifest_canonical),
        "created_at": created_at,
        "machine": machine_name,
    }
    latest_canonical = m.canonical_bytes(latest)
    store.write_bytes(m.LATEST_NAME, latest_canonical)
    write_text(store, m.LATEST_SIG_NAME, keys.sign(private_key, latest_canonical))

    logger.info("[SOT] published %s (machine=%s, counts=%s)", version, machine_name, row_counts)
    return version
