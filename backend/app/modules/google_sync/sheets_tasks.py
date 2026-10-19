"""Celery tasks that reconcile dataset catalogs with Google Sheets."""

from __future__ import annotations

import hashlib
import json
import logging

from app.config import settings
from app.infrastructure.celery.app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.export_tasks.export_samples_to_sheets",
    max_retries=3,
    default_retry_delay=30,
)
def export_samples_to_sheets(self):
    """Mirror ``samples.csv`` to Google Sheets via full replacement."""
    from app.modules.dataset.samples import SAMPLE_FIELDS, SAMPLES_CSV, list_samples

    try:
        spreadsheet_id = str(getattr(settings, "google_sheets_samples_spreadsheet_id", "")).strip()
        sheet_gid = int(getattr(settings, "google_sheets_samples_sheet_gid", 0) or 0)
        if not spreadsheet_id or not sheet_gid:
            logger.debug("[EXPORT] Samples Sheets sync skipped: spreadsheet not configured")
            return {"status": "skipped", "reason": "not_configured"}

        rows = list_samples()
        values = [list(SAMPLE_FIELDS)]
        values.extend(
            [str(row.get(field, "") or "") for field in SAMPLE_FIELDS]
            for row in rows
        )

        digest = hashlib.sha256(
            json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        guard = SAMPLES_CSV.parent / ".samples_sheet.synced"
        try:
            if guard.exists() and guard.read_text(encoding="utf-8").strip() == digest:
                logger.debug("[EXPORT] Samples sheet already up-to-date; skipping rewrite")
                return {"status": "skipped", "reason": "unchanged", "rows": len(rows)}
        except Exception:
            pass

        from app.storage.gdrive_client import get_gdrive_client

        get_gdrive_client().replace_sheet_values(spreadsheet_id, sheet_gid, values)
        try:
            guard.write_text(digest, encoding="utf-8")
        except Exception:
            pass

        logger.info("[EXPORT] ✅ Mirrored %d samples to Sheets (full replace)", len(rows))
        return {"status": "success", "synced_count": len(rows)}
    except Exception as exc:
        logger.error("[EXPORT] Samples Sheets export failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="app.export_tasks.export_labels_to_sheets",
    max_retries=3,
    default_retry_delay=60,
)
def export_labels_to_sheets(self):
    """Mirror ``labels.csv`` to Google Sheets via full replacement."""
    from app.storage.metadata_db import ensure_tables

    try:
        ensure_tables()
        spreadsheet_id = str(getattr(settings, "google_sheets_labels_spreadsheet_id", "")).strip()
        sheet_gid = int(getattr(settings, "google_sheets_labels_sheet_gid", 0) or 0)
        if not spreadsheet_id or not sheet_gid:
            logger.debug("[EXPORT] Labels Sheets sync skipped: spreadsheet not configured")
            return {"status": "skipped", "reason": "not_configured"}

        from app.modules.dataset.catalog import LABEL_FIELDS, load_labels

        rows = load_labels()
        if not rows:
            logger.debug("[EXPORT] No labels to export")
            return {"status": "skipped", "reason": "no_labels"}

        values = [list(LABEL_FIELDS)]
        values.extend([str(row.get(field, "")) for field in LABEL_FIELDS] for row in rows)

        from app.storage.gdrive_client import get_gdrive_client

        get_gdrive_client().replace_sheet_values(spreadsheet_id, sheet_gid, values)
        logger.info("[EXPORT] ✅ Synced %d labels to Sheets", len(rows))
        return {"status": "success", "synced_count": len(rows)}
    except Exception as exc:
        logger.error("[EXPORT] Labels Sheets export failed: %s", exc)
        raise self.retry(exc=exc)
