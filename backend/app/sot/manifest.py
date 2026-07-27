"""SOT manifests, checksums, and version naming.

A manifest is the SIGNED description of a version: which files it contains,
their sha256, row counts, schema version, and the required DB columns a reader
must be able to guarantee. Signing the manifest (not each file) makes the whole
version tamper-evident: a reader re-hashes every file and compares to the signed
manifest, so flipping a byte in any CSV invalidates the version.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Version folder name, e.g. "Ver1_18072026" = Ver{N}_{DDMMYYYY}.
VERSION_RE = re.compile(r"^Ver(\d+)_(\d{2})(\d{2})(\d{4})$")

MANIFEST_NAME = "manifest.json"
MANIFEST_SIG_NAME = "manifest.sig"
LATEST_NAME = "LATEST.json"
LATEST_SIG_NAME = "LATEST.sig"

CATALOG_FILES = ("labels.csv", "samples.csv", "raw_uploads.csv")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_bytes(obj: dict) -> bytes:
    """Deterministic serialization for signing/verifying.

    sort_keys + no whitespace => the exact same bytes on the writer and every
    reader, so a signature computed once verifies everywhere.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_manifest(
    *,
    version_name: str,
    machine_name: str,
    schema_version: int,
    file_hashes: Dict[str, str],
    row_counts: Dict[str, int],
    required_columns: Dict[str, List[str]],
    created_at: Optional[str] = None,
) -> dict:
    """Assemble the manifest dict (pre-signature)."""
    return {
        "sot_manifest_version": 1,
        "version": version_name,
        "machine": machine_name,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "schema_version": int(schema_version),
        "files": dict(sorted(file_hashes.items())),
        "row_counts": dict(sorted(row_counts.items())),
        "required_columns": {t: sorted(cols) for t, cols in sorted(required_columns.items())},
    }


def validate_manifest_shape(manifest: dict) -> None:
    """Raise ValueError if the manifest is missing required keys."""
    required = {"version", "files", "row_counts", "schema_version", "required_columns"}
    missing = required - set(manifest or {})
    if missing:
        raise ValueError(f"manifest missing keys: {sorted(missing)}")
    if not VERSION_RE.match(str(manifest["version"])):
        raise ValueError(f"invalid version name in manifest: {manifest['version']!r}")


def parse_version_name(name: str) -> Optional[Tuple[int, date]]:
    """"Ver3_18072026" -> (3, date(2026, 7, 18)); None if it doesn't match."""
    m = VERSION_RE.match(name or "")
    if not m:
        return None
    n = int(m.group(1))
    dd, mm, yyyy = int(m.group(2)), int(m.group(3)), int(m.group(4))
    try:
        return n, date(yyyy, mm, dd)
    except ValueError:
        return None


def next_version_name(existing: List[str], today: Optional[date] = None) -> str:
    """Next Ver{N+1}_{DDMMYYYY}, where N = highest existing version number.

    Numbering is global and monotonic (not per-day), so ordering is unambiguous
    even with multiple versions on the same date.
    """
    today = today or date.today()
    highest = 0
    for name in existing or []:
        parsed = parse_version_name(name)
        if parsed and parsed[0] > highest:
            highest = parsed[0]
    return f"Ver{highest + 1}_{today.strftime('%d%m%Y')}"


def latest_version(existing: List[str]) -> Optional[str]:
    """The version folder with the highest number (source of 'latest')."""
    best_name, best_n = None, -1
    for name in existing or []:
        parsed = parse_version_name(name)
        if parsed and parsed[0] > best_n:
            best_name, best_n = name, parsed[0]
    return best_name
