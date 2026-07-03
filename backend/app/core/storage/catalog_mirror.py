from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, List

from app.config import settings

logger = logging.getLogger(__name__)


def _read_csv_matrix(csv_path: Path) -> List[List[Any]]:
    path = Path(csv_path)
    if not path.exists():
        return []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = [list(fieldnames)]
        for row in reader:
            rows.append([row.get(field, "") for field in fieldnames])
        return rows


def _mirror_csv_to_gdrive_sync(local_path: Path, remote_path: str) -> None:
    if not getattr(settings, "use_google_drive", False):
        return

    path = Path(local_path)
    if not path.exists():
        return

    try:
        from app.storage.gdrive_client import apply_gdrive_suffix_to_remote_path, upload_to_gdrive

        snapshot_remote_path = apply_gdrive_suffix_to_remote_path(remote_path)

        upload_to_gdrive(
            str(path),
            snapshot_remote_path,
            content_type="text/csv",
            make_public=False,
            replace_existing=True,
        )
        logger.info("[CATALOG_MIRROR] uploaded %s to gdrive:%s", path, snapshot_remote_path)
    except Exception as exc:
        logger.warning(
            "[CATALOG_MIRROR] failed to upload %s to gdrive:%s: %s",
            path,
            remote_path,
            exc,
        )


def _sync_catalog_csv_sync(
    local_path: Path,
    remote_name: str,
    *,
    spreadsheet_id: str = "",
    sheet_gid: int = 0,
) -> None:
    """Best-effort sync for a single catalog CSV to Drive and, when configured, Sheets."""
    if not getattr(settings, "use_google_drive", False):
        return

    path = Path(local_path)
    if not path.exists():
        return

    try:
        from app.storage.gdrive_client import get_gdrive_client, apply_gdrive_suffix_to_remote_path

        client = get_gdrive_client()
        remote_path = apply_gdrive_suffix_to_remote_path(remote_name)

        client.upload_file(
            str(path),
            remote_path,
            content_type="text/csv",
            make_public=False,
            replace_existing=True,
        )
        logger.info("[CATALOG_MIRROR] mirrored %s to gdrive:%s", path, remote_path)

        if spreadsheet_id and int(sheet_gid or 0):
            values = _read_csv_matrix(path)
            if values:
                client.replace_sheet_values(spreadsheet_id, int(sheet_gid), values)
                logger.info(
                    "[CATALOG_MIRROR] mirrored %s to sheets spreadsheet_id=%s sheet_gid=%s",
                    path,
                    spreadsheet_id,
                    sheet_gid,
                )
    except Exception as exc:
        logger.warning("[CATALOG_MIRROR] catalog csv sync failed for %s: %s", path, exc)


def _sync_labels_snapshot_sync(labels_csv: Path) -> None:
    _sync_catalog_csv_sync(
        labels_csv,
        "labels.csv",
        spreadsheet_id=str(getattr(settings, "google_sheets_labels_spreadsheet_id", "") or "").strip(),
        sheet_gid=int(getattr(settings, "google_sheets_labels_sheet_gid", 0) or 0),
    )


def _sync_samples_snapshot_sync(samples_csv: Path) -> None:
    _sync_catalog_csv_sync(
        samples_csv,
        "samples.csv",
        spreadsheet_id=str(getattr(settings, "google_sheets_samples_spreadsheet_id", "") or "").strip(),
        sheet_gid=int(getattr(settings, "google_sheets_samples_sheet_gid", 0) or 0),
    )


def _sync_catalog_snapshots_sync(labels_csv: Path, samples_csv: Path) -> None:
    _sync_labels_snapshot_sync(Path(labels_csv))
    _sync_samples_snapshot_sync(Path(samples_csv))


# ---------------------------------------------------------------------------
# Public API — called by dataset_samples.py and dataset_manager.py after writes
#
# DESIGN DECISION (per user review):
# These functions NO LONGER spawn daemon threads or call Google APIs directly.
# Instead, they log the event and rely on:
#   1. Postgres sheets_synced=FALSE column (the source of truth for pending sync)
#   2. Celery periodic task (export_tasks.py) to batch-export to Google Sheets
#
# If Redis is down, we do NOT fallback to sync — Postgres holds the data safely,
# and Celery will pick it up when it recovers. This prevents:
#   - HTTP request blocking (daemon threads could stall requests)
#   - Google API quota exhaustion from realtime per-upload API calls
#   - 429 errors under concurrent upload load
# ---------------------------------------------------------------------------


def mirror_csv_to_gdrive(local_path: Path, remote_path: str) -> None:
    """No-op: Google Sheets sync is now handled by Celery export task."""
    logger.debug(
        "[CATALOG_MIRROR] Sheets sync deferred to Celery worker: local=%s remote=%s",
        local_path,
        remote_path,
    )


def mirror_labels_to_gdrive_and_sheets(labels_csv: Path) -> None:
    """No-op: labels sync is now handled by Celery export task."""
    logger.debug(
        "[CATALOG_MIRROR] Labels Sheets sync deferred to Celery worker: %s",
        labels_csv,
    )


def mirror_samples_to_gdrive_and_sheets(samples_csv: Path) -> None:
    """No-op: samples sync is now handled by Celery export task."""
    logger.debug(
        "[CATALOG_MIRROR] Samples Sheets sync deferred to Celery worker: %s",
        samples_csv,
    )


def mirror_catalog_to_gdrive_and_sheets(labels_csv: Path, samples_csv: Path) -> None:
    """No-op: catalog sync is now handled by Celery export task."""
    logger.debug(
        "[CATALOG_MIRROR] Catalog Sheets sync deferred to Celery worker: labels=%s samples=%s",
        labels_csv,
        samples_csv,
    )
