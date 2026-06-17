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


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def export_samples_to_sheets(self):
    """Batch export unsynced samples from Postgres to Google Sheets.

    Called by Celery beat every 30 seconds.
    Uses append_sheet_values() — never clears existing data.
    """
    from app.storage.metadata_db import (
        ensure_tables,
        fetch_unsynced_samples,
        mark_samples_synced,
        get_sync_status,
        upsert_sync_status,
    )
    from app.dataset_samples import SAMPLE_FIELDS

    try:
        ensure_tables()

        spreadsheet_id = str(getattr(settings, "google_sheets_samples_spreadsheet_id", "")).strip()
        sheet_gid = int(getattr(settings, "google_sheets_samples_sheet_gid", 0) or 0)

        if not spreadsheet_id or not sheet_gid:
            logger.debug("[EXPORT] Samples Sheets sync skipped: spreadsheet not configured")
            return {"status": "skipped", "reason": "not_configured"}

        # Fetch unsynced rows
        rows = fetch_unsynced_samples(limit=5000)
        if not rows:
            logger.debug("[EXPORT] No unsynced samples to export")
            return {"status": "skipped", "reason": "no_pending_rows"}

        # Check rotation threshold
        sync_status = get_sync_status("samples")
        current_rows = sync_status["current_data_rows"] if sync_status else 0
        max_rows = sync_status["max_rows_per_sheet"] if sync_status else 500_000

        batch_size = len(rows)
        if current_rows + batch_size > max_rows:
            logger.warning(
                "[EXPORT] Sheet approaching limit: current=%d + batch=%d > max=%d. "
                "Manual rotation needed (create new spreadsheet and update config).",
                current_rows, batch_size, max_rows,
            )
            # Still proceed — Google Sheets will reject if truly full,
            # and we'll retry on the next cycle.

        # Convert to values matrix
        values = _rows_to_values(rows, SAMPLE_FIELDS)

        # Append to Google Sheets (1 API call for entire batch)
        from app.storage.gdrive_client import get_gdrive_client
        client = get_gdrive_client()
        client.append_sheet_values(spreadsheet_id, sheet_gid, values)

        # Mark as synced in Postgres
        sample_uids = [r["sample_uid"] for r in rows]
        mark_samples_synced(sample_uids)

        # Update sync status counter
        new_row_count = current_rows + batch_size
        upsert_sync_status("samples", spreadsheet_id, 1, new_row_count)

        logger.info(
            "[EXPORT] ✅ Synced %d samples to Sheets (total rows now: %d)",
            batch_size,
            new_row_count,
        )
        return {
            "status": "success",
            "synced_count": batch_size,
            "total_rows": new_row_count,
        }

    except Exception as exc:
        logger.error("[EXPORT] Samples Sheets export failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
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
        raise self.retry(exc=exc)


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
        raise self.retry(exc=exc)
