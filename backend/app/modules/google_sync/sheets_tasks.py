"""Celery tasks that reconcile dataset catalogs with Google Sheets."""

from __future__ import annotations

import hashlib
import json
import logging
import time

from app.config import settings
from app.infrastructure.celery.app import celery_app


logger = logging.getLogger(__name__)

_LABELS_SHEET_REFRESH_SECONDS = 3600


@celery_app.task(
    bind=True,
    name="app.export_tasks.export_samples_to_sheets",
    max_retries=3,
    default_retry_delay=30,
    platform_wide=True,
)
def export_samples_to_sheets(self):
    """Mirror ``samples.csv`` to Google Sheets via full replacement."""
    from app.modules.dataset.samples import (
        SAMPLE_FIELDS,
        SAMPLES_CSV,
        _load_all_samples_unscoped,
    )

    try:
        spreadsheet_id = str(getattr(settings, "google_sheets_samples_spreadsheet_id", "")).strip()
        sheet_gid = int(getattr(settings, "google_sheets_samples_sheet_gid", 0) or 0)
        if not spreadsheet_id or not sheet_gid:
            logger.debug("[EXPORT] Samples Sheets sync skipped: spreadsheet not configured")
            return {"status": "skipped", "reason": "not_configured"}

        rows = _load_all_samples_unscoped()
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
    platform_wide=True,
)
def export_labels_to_sheets(self):
    """Mirror ``labels.csv`` to Google Sheets via full replacement."""
    try:
        spreadsheet_id = str(getattr(settings, "google_sheets_labels_spreadsheet_id", "")).strip()
        sheet_gid = int(getattr(settings, "google_sheets_labels_sheet_gid", 0) or 0)
        if not spreadsheet_id or not sheet_gid:
            logger.debug("[EXPORT] Labels Sheets sync skipped: spreadsheet not configured")
            return {"status": "skipped", "reason": "not_configured"}

        from app.modules.dataset.catalog import (
            LABEL_FIELDS,
            MASTER_LABELS,
            _load_all_labels_unscoped,
        )
        from app.storage.metadata_db import list_deleted_classes

        active = _load_all_labels_unscoped()
        seen = {row.get("class_uid") or "" for row in active}
        merged = []
        for item in active:
            row = dict(item)
            row.setdefault("deleted_at", "")
            merged.append(row)
        for item in list_deleted_classes():
            if (item.get("class_uid") or "") in seen:
                continue
            row = dict(item)
            row["is_common_global"] = str(int(bool(item.get("is_common_global"))))
            row["is_common_language"] = str(int(bool(item.get("is_common_language"))))
            merged.append(row)

        if not merged:
            logger.debug("[EXPORT] No labels to export")
            return {"status": "skipped", "reason": "no_labels"}

        def _index(row):
            try:
                return int(row.get("class_idx") or 0)
            except (TypeError, ValueError):
                return 0

        merged.sort(key=lambda row: (_index(row), str(row.get("class_uid") or "")))
        header = list(LABEL_FIELDS) + ["deleted_at"]
        values = [header]
        values.extend(
            [str(row.get(field, "") or "") for field in header]
            for row in merged
        )

        digest = hashlib.sha256(
            json.dumps(
                [spreadsheet_id, sheet_gid, values],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        guard = MASTER_LABELS.parent / ".labels_sheet.synced"
        try:
            if (
                guard.read_text(encoding="utf-8").strip() == digest
                and time.time() - guard.stat().st_mtime < _LABELS_SHEET_REFRESH_SECONDS
            ):
                return {"status": "skipped", "reason": "unchanged", "rows": len(merged)}
        except (OSError, UnicodeError):
            pass

        from app.storage.gdrive_client import get_gdrive_client

        get_gdrive_client().replace_sheet_values(spreadsheet_id, sheet_gid, values)
        try:
            guard.write_text(digest, encoding="utf-8")
        except OSError:
            logger.warning("[EXPORT] Could not save labels sync fingerprint")
        logger.info("[EXPORT] ✅ Synced %d labels to Sheets", len(merged))
        return {"status": "success", "synced_count": len(merged)}
    except Exception as exc:
        logger.error("[EXPORT] Labels Sheets export failed: %s", exc)
        raise self.retry(exc=exc)
