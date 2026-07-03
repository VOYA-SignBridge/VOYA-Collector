"""Celery periodic tasks for batch-exporting data to Google Sheets.

Design:
    - Samples and labels are written to local CSV + Postgres immediately during upload.
    - Postgres column `sheets_synced = FALSE` marks rows pending sync.
    - Every 30 seconds, Celery beat triggers `export_samples_to_sheets()`:
        1. Query Postgres for unsynced rows (LIMIT 5000, ordered by created_at)
        2. Format as [[col1, col2, ...], ...] matrix
        3. Call `append_sheet_values()` — a single Sheets API call (append, not clear)
        4. UPDATE `sheets_synced = TRUE` for the batch
        5. Update `google_sheets_sync_status` row counter
    - If the sheet approaches 10M cells, a new spreadsheet can be created (rotation).
    - If Redis or Celery is down, data stays in Postgres with sheets_synced=FALSE.
      No data is lost; the next worker cycle picks up from where it left off.

Maximum rows per sheet:
    Google Sheets limit = 10,000,000 cells.
    With 19 columns: 10,000,000 / 19 ≈ 526,315 rows.
    We use max_rows_per_sheet = 500,000 for safety margin.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from app.worker import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


def _rows_to_values(rows: List[Dict[str, Any]], fieldnames: List[str]) -> List[List[Any]]:
    """Convert dict rows to Sheets-compatible value matrix (no header row)."""
    result = []
    for row in rows:
        result.append([str(row.get(field) or "") for field in fieldnames])
    return result


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def export_samples_to_sheets(self):
    """Batch sync samples to Google Sheets using FULL REPLACE.

    Runs periodically to ensure the Google Sheet is an exact replica
    of the active samples in Postgres (no duplicates, no deleted rows).
    """
    from app.storage.metadata_db import ensure_tables, _get_conn
    from app.dataset_samples import SAMPLE_FIELDS

    try:
        ensure_tables()

        spreadsheet_id = str(getattr(settings, "google_sheets_samples_spreadsheet_id", "")).strip()
        sheet_gid = int(getattr(settings, "google_sheets_samples_sheet_gid", 0) or 0)

        if not spreadsheet_id or not sheet_gid:
            logger.debug("[EXPORT] Samples Sheets sync skipped: spreadsheet not configured")
            return {"status": "skipped", "reason": "not_configured"}

        rows = []
        with _get_conn() as conn:
            with conn.cursor() as cur:
                fields_str = ", ".join(SAMPLE_FIELDS)
                cur.execute(f"SELECT {fields_str} FROM samples WHERE deleted_at IS NULL ORDER BY created_at ASC")
                for db_row in cur.fetchall():
                    row_dict = dict(zip(SAMPLE_FIELDS, db_row))
                    for k, v in row_dict.items():
                        if isinstance(v, datetime):
                            row_dict[k] = v.isoformat() + "Z"
                        elif v is None:
                            row_dict[k] = ""
                    rows.append(row_dict)

        if not rows:
            logger.debug("[EXPORT] No samples to export")
            return {"status": "skipped", "reason": "no_data"}

        # Build full matrix with header
        values = [list(SAMPLE_FIELDS)]
        for row in rows:
            values.append([str(row.get(field, "")) for field in SAMPLE_FIELDS])

        from app.storage.gdrive_client import get_gdrive_client
        client = get_gdrive_client()
        client.replace_sheet_values(spreadsheet_id, sheet_gid, values)

        logger.info("[EXPORT] ✅ Fully replaced Sheets with %d samples", len(rows))
        return {
            "status": "success",
            "synced_count": len(rows)
        }

    except Exception as exc:
        logger.error("[EXPORT] Samples Sheets export failed: %s", exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.critical(
                "[EXPORT][DLQ] Samples Sheets export PERMANENTLY FAILED after %d retries: %s",
                self.max_retries, exc,
            )
            return {"status": "dead_letter", "error": str(exc)}


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def export_labels_to_sheets(self):
    """Batch sync labels.csv to Google Sheets.

    Labels change less frequently than samples, so this runs less often.
    For labels, we use the full replace approach since the dataset typically
    has < 10K labels and the full state needs to be accurate.
    """
    from app.storage.metadata_db import ensure_tables

    try:
        ensure_tables()

        spreadsheet_id = str(getattr(settings, "google_sheets_labels_spreadsheet_id", "")).strip()
        sheet_gid = int(getattr(settings, "google_sheets_labels_sheet_gid", 0) or 0)

        if not spreadsheet_id or not sheet_gid:
            logger.debug("[EXPORT] Labels Sheets sync skipped: spreadsheet not configured")
            return {"status": "skipped", "reason": "not_configured"}

        # Labels are small enough to do full replace safely
        from app.dataset_manager import load_labels, LABEL_FIELDS

        rows = load_labels()
        if not rows:
            logger.debug("[EXPORT] No labels to export")
            return {"status": "skipped", "reason": "no_labels"}

        # Build full matrix with header
        values = [list(LABEL_FIELDS)]
        for row in rows:
            values.append([str(row.get(field, "")) for field in LABEL_FIELDS])

        from app.storage.gdrive_client import get_gdrive_client
        client = get_gdrive_client()
        client.replace_sheet_values(spreadsheet_id, sheet_gid, values)

        logger.info("[EXPORT] ✅ Synced %d labels to Sheets", len(rows))
        return {"status": "success", "synced_count": len(rows)}

    except Exception as exc:
        logger.error("[EXPORT] Labels Sheets export failed: %s", exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.critical(
                "[EXPORT][DLQ] Labels Sheets export PERMANENTLY FAILED after %d retries: %s",
                self.max_retries, exc,
            )
            return {"status": "dead_letter", "error": str(exc)}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def export_samples_to_local_csv(self):
    """Batch export samples from Postgres to local CSV file.
    Runs every 60 seconds.
    """
    import csv
    import tempfile
    import os
    from app.dataset_samples import SAMPLES_CSV, SAMPLE_FIELDS, _ensure_samples_file
    from app.storage.metadata_db import _get_conn
    from filelock import FileLock

    try:
        _ensure_samples_file()
        rows = []
        with _get_conn() as conn:
            with conn.cursor() as cur:
                # Query all samples except hard-deleted
                fields_str = ", ".join(SAMPLE_FIELDS)
                cur.execute(f"SELECT {fields_str} FROM samples WHERE deleted_at IS NULL ORDER BY created_at ASC")
                for db_row in cur.fetchall():
                    row_dict = dict(zip(SAMPLE_FIELDS, db_row))
                    # formatting dates
                    for k, v in row_dict.items():
                        if isinstance(v, datetime):
                            row_dict[k] = v.isoformat() + "Z"
                        elif v is None:
                            row_dict[k] = ""
                    rows.append(row_dict)

        if not rows:
            return {"status": "skipped", "reason": "no_data"}

        lock = FileLock(str(SAMPLES_CSV) + ".lock")
        with lock:
            tmp_path = str(SAMPLES_CSV) + ".tmp"
            with open(tmp_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=SAMPLE_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, SAMPLES_CSV)
            
        logger.info("[EXPORT] Dumped %d samples from DB to local CSV", len(rows))
        return {"status": "success", "synced_count": len(rows)}
    except Exception as exc:
        logger.error("[EXPORT] Local CSV export failed: %s", exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "dead_letter", "error": str(exc)}


@celery_app.task(bind=True, max_retries=5, default_retry_delay=10)
def upload_npz_to_gdrive_task(self, sample_uid: str, local_path: str, storage_key: str, sidecar_path: str):
    from app.storage.gdrive_client import upload_to_gdrive
    from app.processing.utils import atomic_write_json
    from app.storage.metadata_db import update_sample_gdrive_url
    from app.dataset_samples import update_sample_row
    import json
    import os

    try:
        if not os.path.exists(local_path):
            logger.warning("[GDRIVE_UPLOAD] Local file not found: %s", local_path)
            return {"status": "skipped", "reason": "file_not_found"}

        logger.info("[GDRIVE_UPLOAD] Uploading %s to GDrive key %s", local_path, storage_key)
        storage_url = upload_to_gdrive(local_path, storage_key)
        
        if not storage_url:
            raise RuntimeError("upload_to_gdrive returned None")

        logger.info("[GDRIVE_UPLOAD] Upload successful: %s", storage_url)

        # 1. Update sidecar JSON
        try:
            if os.path.exists(sidecar_path):
                with open(sidecar_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                metadata["storage_url"] = storage_url
                metadata["storage_key"] = storage_key
                metadata["storage_provider"] = "local+gdrive"
                atomic_write_json(sidecar_path, metadata, indent=2)
        except Exception as e:
            logger.warning("[GDRIVE_UPLOAD] Failed to update sidecar JSON: %s", e)

        # 2. Update Postgres database
        update_sample_gdrive_url(sample_uid, storage_url)

        # 3. Update samples.csv
        update_sample_row(sample_uid, {
            "storage_url": storage_url,
            "storage_key": storage_key
        })

        return {"status": "success", "storage_url": storage_url}

    except Exception as exc:
        logger.error("[GDRIVE_UPLOAD] Upload failed for %s: %s", sample_uid, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            # DLQ: Mark sample as ERROR in Postgres, keep raw file on disk
            logger.critical(
                "[GDRIVE_UPLOAD][DLQ] Upload PERMANENTLY FAILED for sample_uid=%s after %d retries: %s",
                sample_uid, self.max_retries, exc,
            )
            try:
                from app.storage.metadata_db import update_sample_status
                update_sample_status(
                    sample_uid,
                    status="ERROR",
                    error_log=f"GDrive upload failed after {self.max_retries} retries: {exc}",
                )
            except Exception as db_exc:
                logger.error("[GDRIVE_UPLOAD][DLQ] Failed to update DB status: %s", db_exc)
            return {"status": "dead_letter", "sample_uid": sample_uid, "error": str(exc)}
