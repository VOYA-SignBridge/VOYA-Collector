import logging
import time
import uuid
from datetime import datetime, timezone

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
        
        # Check and sync missing data (Idempotent seed)
        sync_missing_data_on_startup()
        
        return True
    except Exception:
        # Best-effort: DB is optional
        logger.exception("[DB_INIT][FAILURE] schema initialization failed")
        return False

def sync_missing_data_on_startup():
    """Sync missing records from CSV to PostgreSQL on startup.
    Ensures Foreign Key safety by inserting parents first, and Idempotency
    by using ON CONFLICT DO UPDATE which preserves deleted_at.
    """
    from app.dataset_manager import load_labels
    from app.dataset_samples import list_samples
    from app.raw_uploads import list_raw_uploads
    from app.storage.metadata_db import _fetch_all, upsert_class, upsert_sample, upsert_raw_upload
    
    try:
        # 1. Classes (Parent table)
        labels = load_labels()
        if labels:
            db_classes_count = _fetch_all("SELECT COUNT(*) as c FROM classes")[0]["c"]
            if db_classes_count < len(labels):
                logger.info("[STARTUP_SYNC] Syncing classes. DB: %d, CSV: %d", db_classes_count, len(labels))
                for label in labels:
                    upsert_class(label)
                    
        # 2. Samples (Child table)
        samples = list_samples()
        if samples:
            db_samples_count = _fetch_all("SELECT COUNT(*) as c FROM samples")[0]["c"]
            if db_samples_count < len(samples):
                logger.info("[STARTUP_SYNC] Syncing samples. DB: %d, CSV: %d", db_samples_count, len(samples))
                for sample in samples:
                    upsert_sample(sample)
                    
        # 3. Raw Uploads (Child table)
        uploads = list_raw_uploads()
        if uploads:
            db_uploads_count = _fetch_all("SELECT COUNT(*) as c FROM raw_uploads")[0]["c"]
            if db_uploads_count < len(uploads):
                logger.info("[STARTUP_SYNC] Syncing raw_uploads. DB: %d, CSV: %d", db_uploads_count, len(uploads))
                for upload in uploads:
                    upsert_raw_upload(upload)
    except Exception as exc:
        logger.error("[STARTUP_SYNC] Failed to sync missing data: %s", exc)

def bootstrap_admin_user():
    """Create admin user from .env if not already exists.
    
    Reads ADMIN_USERNAME and ADMIN_PASSWORD from settings and creates
    a user with is_admin=True if the username doesn't exist yet.
    """
    from app.config import settings
    
    admin_username = getattr(settings, "admin_username", "").strip()
    admin_password = getattr(settings, "admin_password", "").strip()
    
    if not admin_username or not admin_password:
        logger.debug("[BOOTSTRAP_ADMIN] ADMIN_USERNAME or ADMIN_PASSWORD not configured, skipping")
        return
    
    try:
        from app.storage.metadata_db import _column_exists, _execute
        from app.auth import _fetch_user_by_login, get_password_hash
        
        # Check if users table exists
        if not _column_exists("users", "id"):
            logger.warning("[BOOTSTRAP_ADMIN] users table does not exist yet, skipping")
            return
        
        # Check if admin user already exists
        existing = _fetch_user_by_login(admin_username)
        if existing:
            logger.info("[BOOTSTRAP_ADMIN] admin user '%s' already exists, skipping", admin_username)
            return
        
        # Create admin user
        admin_id = str(uuid.uuid4())
        password_hash = get_password_hash(admin_password)
        
        sql = """
        INSERT INTO users(id, username, email, password_hash, is_active, is_admin, created_at)
        VALUES(%s, %s, %s, %s, true, true, %s)
        ON CONFLICT (id) DO NOTHING
        """
        
        _execute(
            sql,
            (
                admin_id,
                admin_username,
                f"{admin_username}@admin.local",
                password_hash,
                datetime.now(timezone.utc),
            ),
        )
        
        logger.info("[BOOTSTRAP_ADMIN] admin user '%s' created successfully", admin_username)
        
    except Exception as exc:
        logger.error("[BOOTSTRAP_ADMIN] failed to create admin user: %s", exc)