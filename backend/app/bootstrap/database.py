"""Database schema initialization and dataset catalog mirroring at startup."""

from __future__ import annotations

import logging
import time

logger = logging.getLogger("db.init")


def sync_missing_data_on_startup() -> None:
    """Mirror missing CSV catalog records into PostgreSQL in dependency order."""
    from app.modules.dataset.catalog import load_labels
    from app.modules.dataset.raw_uploads import list_raw_uploads
    from app.modules.dataset.samples import list_samples
    from app.storage.metadata_db import (
        _fetch_all,
        upsert_class,
        upsert_raw_upload,
        upsert_sample,
    )

    try:
        labels = load_labels()
        if labels:
            database_count = _fetch_all("SELECT COUNT(*) as c FROM classes")[0]["c"]
            if database_count < len(labels):
                logger.info(
                    "[STARTUP_SYNC] Syncing classes. DB: %d, CSV: %d",
                    database_count,
                    len(labels),
                )
                for label in labels:
                    upsert_class(label)

        samples = list_samples()
        if samples:
            database_count = _fetch_all("SELECT COUNT(*) as c FROM samples")[0]["c"]
            if database_count < len(samples):
                logger.info(
                    "[STARTUP_SYNC] Syncing samples. DB: %d, CSV: %d",
                    database_count,
                    len(samples),
                )
                for sample in samples:
                    upsert_sample(sample)

        uploads = list_raw_uploads()
        if uploads:
            database_count = _fetch_all("SELECT COUNT(*) as c FROM raw_uploads")[0]["c"]
            if database_count < len(uploads):
                logger.info(
                    "[STARTUP_SYNC] Syncing raw_uploads. DB: %d, CSV: %d",
                    database_count,
                    len(uploads),
                )
                for upload in uploads:
                    upsert_raw_upload(upload)
    except Exception as exc:
        logger.error("[STARTUP_SYNC] Failed to sync missing data: %s", exc)


def init_db() -> bool:
    """Ensure the current metadata schema exists, then mirror missing records.

    PostgreSQL remains best-effort for application startup, so initialization
    reports failure instead of preventing the HTTP service from starting.
    """
    started_at = time.time()
    logger.info("[DB_INIT] starting schema initialization")
    try:
        from app.storage.metadata_db import ensure_tables

        ensure_tables()
        logger.info(
            "[DB_INIT][SUCCESS] duration_ms=%.1f",
            (time.time() - started_at) * 1000,
        )
        sync_missing_data_on_startup()
        return True
    except Exception:
        logger.exception("[DB_INIT][FAILURE] schema initialization failed")
        return False
