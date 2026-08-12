from __future__ import annotations

import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from filelock import FileLock

from app.config import settings
from app.tenancy import DEFAULT_TENANT_ID, TENANT_COLUMN, tenant_id_of

logger = logging.getLogger(__name__)

DATASET_ROOT = settings.dataset_root
RAW_UPLOADS_DIR = DATASET_ROOT / "raw_videos"
RAW_UPLOADS_CSV = RAW_UPLOADS_DIR / "uploads.csv"

RAW_UPLOAD_FIELDS = [
    "upload_uid",
    "class_uid",
    "slug",
    "label_original",
    "language",
    "dialect",
    "source_type",
    "user_id",
    "session_id",
    "original_filename",
    "local_path",
    "storage_key",
    "storage_url",
    "created_at",
    "updated_at",
    # Owning tenant, appended last. raw_uploads is the third table the startup
    # sync writes and the third table A3 puts under RLS; leaving it out would
    # keep the tenant-less-rebuild hole alive in exactly one of the three.
    TENANT_COLUMN,
]


def now_str() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _ensure_raw_uploads_file() -> None:
    RAW_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    if not RAW_UPLOADS_CSV.exists():
        lock = FileLock(str(RAW_UPLOADS_CSV) + ".lock")
        with lock:
            if not RAW_UPLOADS_CSV.exists():
                with open(RAW_UPLOADS_CSV, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=RAW_UPLOAD_FIELDS)
                    writer.writeheader()
        return
    _upgrade_raw_uploads_header()


def _upgrade_raw_uploads_header() -> bool:
    """Add any missing RAW_UPLOAD_FIELDS column to an existing uploads.csv.

    Needed because append_raw_upload_row() writes with `fieldnames=
    RAW_UPLOAD_FIELDS` but only emits a header for an empty file — so appending
    a 16-column row to a file whose header still has 15 would put every value
    one column left of its name, silently.

    Existing rows get the bootstrap tenant for the same reason samples.csv does:
    they were written before tenants existed and provably belong to it.
    """
    lock = FileLock(str(RAW_UPLOADS_CSV) + ".lock")
    with lock:
        with open(RAW_UPLOADS_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            on_disk = list(reader.fieldnames or [])
            if all(col in on_disk for col in RAW_UPLOAD_FIELDS):
                return False
            rows = list(reader)
        for row in rows:
            row[TENANT_COLUMN] = tenant_id_of(row)
        tmp = str(RAW_UPLOADS_CSV) + ".tmp"
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=RAW_UPLOAD_FIELDS, extrasaction="ignore", restval=""
            )
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, RAW_UPLOADS_CSV)
    logger.info(
        "[RAW_UPLOADS] uploads.csv: nâng header lên %d cột (%d dòng giữ nguyên, "
        "tenant cũ điền '%s')",
        len(RAW_UPLOAD_FIELDS), len(rows), DEFAULT_TENANT_ID,
    )
    return True


def list_raw_uploads() -> List[Dict[str, str]]:
    _ensure_raw_uploads_file()
    lock = FileLock(str(RAW_UPLOADS_CSV) + ".lock")
    with lock:
        with open(RAW_UPLOADS_CSV, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))


def append_raw_upload_row(row: Dict[str, Any]) -> None:
    # DictWriter's restval is "", so an omitted key writes an empty cell rather
    # than defaulting. Copy, don't mutate the caller's dict.
    row = {**row, TENANT_COLUMN: tenant_id_of(row)}
    _ensure_raw_uploads_file()
    lock = FileLock(str(RAW_UPLOADS_CSV) + ".lock")
    with lock:
        file_exists = RAW_UPLOADS_CSV.exists()
        with open(RAW_UPLOADS_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=RAW_UPLOAD_FIELDS)
            if not file_exists or os.path.getsize(RAW_UPLOADS_CSV) == 0:
                writer.writeheader()
            writer.writerow(row)
            f.flush()
            os.fsync(f.fileno())

    from app.storage.catalog_mirror import mirror_csv_to_gdrive

    mirror_csv_to_gdrive(RAW_UPLOADS_CSV, "raw_uploads.csv")


def write_raw_upload_rows(rows: List[Dict[str, Any]]) -> None:
    _ensure_raw_uploads_file()
    lock = FileLock(str(RAW_UPLOADS_CSV) + ".lock")
    with lock:
        with open(RAW_UPLOADS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=RAW_UPLOAD_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())

    from app.storage.catalog_mirror import mirror_csv_to_gdrive

    mirror_csv_to_gdrive(RAW_UPLOADS_CSV, "raw_uploads.csv")


def update_raw_upload_row(upload_uid: str, updates: Dict[str, Any]) -> bool:
    """Update fields of one raw upload row by upload_uid.

    Used by the Celery GDrive mirror task to fill in storage_url after
    the background upload completes. Returns True if the row was found.
    """
    if not upload_uid:
        return False
    rows = list_raw_uploads()
    found = False
    for row in rows:
        if row.get("upload_uid") == upload_uid:
            row.update({k: str(v) for k, v in updates.items() if k in RAW_UPLOAD_FIELDS})
            row["updated_at"] = now_str()
            found = True
            break
    if found:
        write_raw_upload_rows(rows)
    return found


def find_raw_upload(upload_uid: str) -> Optional[Dict[str, str]]:
    if not upload_uid:
        return None
    for row in list_raw_uploads():
        if row.get("upload_uid") == upload_uid:
            return row
    return None


def find_raw_uploads_by_class(class_uid: str) -> List[Dict[str, str]]:
    if not class_uid:
        return []
    return [row for row in list_raw_uploads() if row.get("class_uid") == class_uid]


def delete_raw_upload(upload_uid: str) -> None:
    rows = list_raw_uploads()
    rows = [row for row in rows if row.get("upload_uid") != upload_uid]
    write_raw_upload_rows(rows)


def delete_raw_uploads_by_class(class_uid: str) -> None:
    rows = list_raw_uploads()
    rows = [row for row in rows if row.get("class_uid") != class_uid]
    write_raw_upload_rows(rows)
