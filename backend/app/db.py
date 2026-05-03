import logging
import time


logger = logging.getLogger("db.init")


def init_db():
    """Initialize database tables.

    Note: this project primarily persists labels/samples to CSV + JSON sidecars.
    Postgres is optional and used for mirroring sample metadata via
    `app.storage.metadata_db`.

    Historically this module used SQLAlchemy to create legacy tables named
    `labels` and `samples`. Those schemas conflict with the current
    `samples(sample_uid, ...)` schema used by `metadata_db`.

    We now ensure the correct tables exist using `metadata_db.ensure_tables()`.
    """
    started_at = time.time()
    logger.info("[DB_INIT] starting schema initialization")
    try:
        from app.storage.metadata_db import ensure_tables
        ensure_tables()
        logger.info("[DB_INIT][SUCCESS] duration_ms=%.1f", (time.time() - started_at) * 1000)
        return True
    except Exception:
        # Best-effort: DB is optional
        logger.exception("[DB_INIT][FAILURE] schema initialization failed")
        return False
