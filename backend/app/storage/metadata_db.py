import psycopg2
from psycopg2.extras import Json, RealDictCursor
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
import logging
import re

from app.config import settings
from app.storage.postgres_connection import get_pooled_conn, put_pooled_conn

logger = logging.getLogger(__name__)


@contextmanager
def _cursor():
    # Borrow from the process-local pool instead of opening a fresh connection
    # per query (hot path: hundreds of insert/update during npz upload).
    conn = get_pooled_conn()
    broken = False
    try:
        with conn:  # commits on success, rolls back on exception
            with conn.cursor() as cur:
                yield cur
    except Exception:
        # A rolled-back connection stays reusable; only discard if truly dead.
        broken = bool(getattr(conn, "closed", 0))
        raise
    finally:
        put_pooled_conn(conn, close=broken)


def _execute(sql: str, params: Dict[str, Any] | tuple | None = None) -> None:
    with _cursor() as cur:
        cur.execute(sql, params)


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _int_or_none(value: Any) -> int | None:
    text = str(value).strip() if value is not None else ""
    try:
        return int(text) if text else None
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    text = str(value).strip() if value is not None else ""
    try:
        return float(text) if text else None
    except (TypeError, ValueError):
        return None


def _ts_or_none(value: Any) -> Any:
    """Empty string -> NULL for timestamp columns (CSV mirror leaves them blank,
    which Postgres rejects as 'invalid input syntax for type timestamp')."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        is_admin BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS classes (
        class_uid TEXT PRIMARY KEY,
        class_idx INTEGER,
        slug TEXT,
        label_original TEXT,
        language TEXT,
        dialect TEXT,
        is_common_global BOOLEAN,
        is_common_language BOOLEAN,
        folder_name TEXT,
        created_at TIMESTAMP WITH TIME ZONE,
        migrated_at TIMESTAMP WITH TIME ZONE,
        deleted_at TIMESTAMP WITH TIME ZONE,
        hands_required INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS samples (
        sample_uid TEXT PRIMARY KEY,
        class_uid TEXT,
        slug TEXT,
        label_original TEXT,
        language TEXT,
        dialect TEXT,
        source_type TEXT,
        user_id TEXT,
        auth_user_id UUID,
        session_id TEXT,
        fps_original TEXT,
        fps_processed TEXT,
        seq_len INTEGER,
        augment_id INTEGER,
        completeness REAL,
        file_path TEXT,
        storage_url TEXT,
        checksum TEXT,
        created_at TIMESTAMP WITH TIME ZONE,
        gdrive_synced BOOLEAN DEFAULT FALSE,
        deleted_at TIMESTAMP WITH TIME ZONE,
        left_hand_ratio REAL,
        right_hand_ratio REAL,
        both_hands_ratio REAL,
        jitter REAL,
        quality_flags TEXT,
        FOREIGN KEY (auth_user_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_uploads (
        upload_uid TEXT PRIMARY KEY,
        class_uid TEXT,
        slug TEXT,
        label_original TEXT,
        language TEXT,
        dialect TEXT,
        source_type TEXT,
        user_id TEXT,
        auth_user_id UUID,
        session_id TEXT,
        original_filename TEXT,
        local_path TEXT,
        storage_key TEXT,
        storage_url TEXT,
        created_at TIMESTAMP WITH TIME ZONE,
        updated_at TIMESTAMP WITH TIME ZONE,
        deleted_at TIMESTAMP WITH TIME ZONE,
        FOREIGN KEY (auth_user_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS training_jobs (
        job_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        model_type TEXT,
        config JSONB,
        auth_user_id UUID,
        created_at TIMESTAMP WITH TIME ZONE,
        started_at TIMESTAMP WITH TIME ZONE,
        completed_at TIMESTAMP WITH TIME ZONE,
        current_epoch INTEGER NOT NULL DEFAULT 0,
        total_epochs INTEGER NOT NULL DEFAULT 0,
        checkpoint_path TEXT,
        test_acc REAL,
        test_f1 REAL,
        error_message TEXT,
        promoted_at TIMESTAMP WITH TIME ZONE,
        evaluation JSONB,
        FOREIGN KEY (auth_user_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS training_metrics (
        job_id TEXT NOT NULL,
        epoch INTEGER NOT NULL,
        train_loss REAL,
        train_acc REAL,
        val_loss REAL,
        val_acc REAL,
        val_f1 REAL,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        PRIMARY KEY (job_id, epoch)
    )
    """,
]

INDEX_STATEMENTS = [
    # users.username/users.email đã có UNIQUE -> PostgreSQL tự tạo index, không cần tạo thêm index trùng
    "CREATE INDEX IF NOT EXISTS idx_classes_class_idx ON classes(class_idx)",
    "CREATE INDEX IF NOT EXISTS idx_classes_slug ON classes(slug)",
    "CREATE INDEX IF NOT EXISTS idx_classes_lang_dialect ON classes(language, dialect)",
    "CREATE INDEX IF NOT EXISTS idx_samples_class_uid ON samples(class_uid)",
    "CREATE INDEX IF NOT EXISTS idx_samples_auth_user_id ON samples(auth_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_samples_created_at ON samples(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_raw_uploads_class_uid ON raw_uploads(class_uid)",
    "CREATE INDEX IF NOT EXISTS idx_raw_uploads_auth_user_id ON raw_uploads(auth_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_uploads_created_at ON raw_uploads(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_training_jobs_created_at ON training_jobs(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_training_jobs_status ON training_jobs(status)",
    # Partial index for Celery export: only indexes rows not yet synced to Sheets
    "CREATE INDEX IF NOT EXISTS idx_samples_sheets_synced ON samples(sheets_synced) WHERE sheets_synced = FALSE",
    "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id)",
]

MIGRATION_STATEMENTS = [
    # Soft delete trash
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE",
    # Add sheets_synced column to samples (safe for existing data: defaults to FALSE)
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS sheets_synced BOOLEAN DEFAULT FALSE",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS gdrive_synced BOOLEAN DEFAULT TRUE",
    # Promotion timestamp for training jobs (admin promoted model to realtime)
    "ALTER TABLE training_jobs ADD COLUMN IF NOT EXISTS promoted_at TIMESTAMP WITH TIME ZONE",
    # Test-set evaluation (confusion matrix + per-class metrics) for Step 7
    "ALTER TABLE training_jobs ADD COLUMN IF NOT EXISTS evaluation JSONB",
    # Live-capture QC: per-class hand requirement + per-sample quality metrics
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS hands_required INTEGER",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS left_hand_ratio REAL",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS right_hand_ratio REAL",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS both_hands_ratio REAL",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS jitter REAL",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS quality_flags TEXT",
    # Sync status tracking table for Google Sheets auto-rotation
    """
    CREATE TABLE IF NOT EXISTS google_sheets_sync_status (
        id SERIAL PRIMARY KEY,
        table_name VARCHAR(50) UNIQUE NOT NULL,
        current_spreadsheet_id VARCHAR(100) NOT NULL DEFAULT '',
        current_sheet_index INT NOT NULL DEFAULT 1,
        current_data_rows INT NOT NULL DEFAULT 0,
        max_rows_per_sheet INT NOT NULL DEFAULT 500000,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
    """,
    # Forgot-password flow: stores a hash of the reset token (never the raw
    # token) so a leaked DB dump can't be used to reset accounts directly.
    """
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        token_hash TEXT PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        used_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
    # Refresh tokens for the cookie session flow. Only a sha256 hash of the
    # token is stored (a leaked DB dump can't be replayed). Rotated on every
    # refresh (old row gets revoked_at) and revoked on logout.
    """
    CREATE TABLE IF NOT EXISTS refresh_tokens (
        token_hash TEXT PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        revoked_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    )
    """,
]

def _column_exists(table: str, column: str) -> bool:
    # kiểm tra nếu column tồn tại trong table
    q = """
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
    LIMIT 1
    """
    try:
        with _cursor() as cur:
            cur.execute(q, (table, column))
            return cur.fetchone() is not None
    except Exception:
        logger.error(f"Error occurred while checking column existence: {table}.{column}")
        return False

def ensure_tables():
    # Apply DDL statements one-by-one so a later failure won't roll back earlier successful creates.
    for stmt in DDL_STATEMENTS:
        try:
            _execute(stmt)
        except Exception as exc:
            logger.warning("ensure_tables: DDL statement failed (ignored): %s : %s", getattr(exc, "pgerror", str(exc)), stmt[:120])

    # Apply migration statements (ALTER TABLE, new tables for sync tracking)
    for stmt in MIGRATION_STATEMENTS:
        try:
            _execute(stmt)
        except Exception as exc:
            logger.warning("ensure_tables: migration statement failed (ignored): %s : %s", getattr(exc, "pgerror", str(exc)), stmt[:120])

    # Create indexes safely: check referenced columns exist first.
    idx_re = re.compile(r"ON\s+([a-zA-Z_][\w]*)\s*\(([^)]+)\)", re.IGNORECASE)
    for stmt in INDEX_STATEMENTS:
        m = idx_re.search(stmt)
        if not m:
            # If we cannot parse, try to run but guard with exception
            try:
                _execute(stmt)
            except Exception as exc:
                logger.warning("ensure_tables: index creation failed (ignored): %s : %s", getattr(exc, "pgerror", str(exc)), stmt)
            continue

        table = m.group(1)
        cols = [c.strip().split()[0].strip('"') for c in m.group(2).split(",")]
        # check all columns exist
        all_exist = True
        for col in cols:
            if not _column_exists(table, col):
                logger.warning("ensure_tables: skipping index creation because column missing: %s.%s", table, col)
                all_exist = False
                break

        if not all_exist:
            continue

        try:
            _execute(stmt)
        except Exception as exc:
            logger.warning("ensure_tables: index creation failed (ignored): %s : %s", getattr(exc, "pgerror", str(exc)), stmt)

SQL_UPSERT_USER = """
INSERT INTO users(id, username, email, password_hash, is_active, is_admin, created_at)
VALUES(%(id)s, %(username)s, %(email)s, %(password_hash)s, %(is_active)s, %(is_admin)s, %(created_at)s)
ON CONFLICT (id) DO UPDATE SET
    username = EXCLUDED.username,
    email = EXCLUDED.email,
    password_hash = EXCLUDED.password_hash,
    is_active = EXCLUDED.is_active,
    is_admin = EXCLUDED.is_admin,
    created_at = EXCLUDED.created_at
"""

SQL_UPSERT_CLASS = """
INSERT INTO classes(
    class_uid, class_idx, slug, label_original, language, dialect,
    is_common_global, is_common_language, folder_name, created_at, migrated_at,
    hands_required
)
VALUES(
    %(class_uid)s, %(class_idx)s, %(slug)s, %(label_original)s, %(language)s, %(dialect)s,
    %(is_common_global)s, %(is_common_language)s, %(folder_name)s, %(created_at)s, %(migrated_at)s,
    %(hands_required)s
)
ON CONFLICT (class_uid) DO UPDATE SET
    class_idx = EXCLUDED.class_idx,
    slug = EXCLUDED.slug,
    label_original = EXCLUDED.label_original,
    language = EXCLUDED.language,
    dialect = EXCLUDED.dialect,
    is_common_global = EXCLUDED.is_common_global,
    is_common_language = EXCLUDED.is_common_language,
    folder_name = EXCLUDED.folder_name,
    created_at = EXCLUDED.created_at,
    migrated_at = EXCLUDED.migrated_at,
    hands_required = COALESCE(EXCLUDED.hands_required, classes.hands_required)
"""

SQL_UPSERT_SAMPLE = """
INSERT INTO samples(
    sample_uid, class_uid, slug, label_original, language, dialect,
    source_type, user_id, auth_user_id, session_id, fps_original, fps_processed,
    seq_len, augment_id, completeness, file_path, storage_url, checksum, created_at, gdrive_synced,
    left_hand_ratio, right_hand_ratio, both_hands_ratio, jitter, quality_flags
)
VALUES(
    %(sample_uid)s, %(class_uid)s, %(slug)s, %(label_original)s, %(language)s, %(dialect)s,
    %(source_type)s, %(user_id)s, %(auth_user_id)s, %(session_id)s, %(fps_original)s, %(fps_processed)s,
    %(seq_len)s, %(augment_id)s, %(completeness)s, %(file_path)s, %(storage_url)s, %(checksum)s, %(created_at)s, %(gdrive_synced)s,
    %(left_hand_ratio)s, %(right_hand_ratio)s, %(both_hands_ratio)s, %(jitter)s, %(quality_flags)s
)
ON CONFLICT (sample_uid) DO UPDATE SET
    class_uid = EXCLUDED.class_uid,
    slug = EXCLUDED.slug,
    label_original = EXCLUDED.label_original,
    language = EXCLUDED.language,
    dialect = EXCLUDED.dialect,
    source_type = EXCLUDED.source_type,
    user_id = EXCLUDED.user_id,
    auth_user_id = COALESCE(EXCLUDED.auth_user_id, samples.auth_user_id),
    session_id = EXCLUDED.session_id,
    fps_original = EXCLUDED.fps_original,
    fps_processed = EXCLUDED.fps_processed,
    seq_len = EXCLUDED.seq_len,
    augment_id = EXCLUDED.augment_id,
    completeness = EXCLUDED.completeness,
    file_path = EXCLUDED.file_path,
    storage_url = EXCLUDED.storage_url,
    checksum = EXCLUDED.checksum,
    created_at = EXCLUDED.created_at,
    gdrive_synced = EXCLUDED.gdrive_synced,
    left_hand_ratio = COALESCE(EXCLUDED.left_hand_ratio, samples.left_hand_ratio),
    right_hand_ratio = COALESCE(EXCLUDED.right_hand_ratio, samples.right_hand_ratio),
    both_hands_ratio = COALESCE(EXCLUDED.both_hands_ratio, samples.both_hands_ratio),
    jitter = COALESCE(EXCLUDED.jitter, samples.jitter),
    quality_flags = COALESCE(EXCLUDED.quality_flags, samples.quality_flags)
"""

SQL_UPSERT_RAW_UPLOAD = """
INSERT INTO raw_uploads(
    upload_uid, class_uid, slug, label_original, language, dialect,
    source_type, user_id, auth_user_id, session_id, original_filename,
    local_path, storage_key, storage_url, created_at, updated_at
)
VALUES(
    %(upload_uid)s, %(class_uid)s, %(slug)s, %(label_original)s, %(language)s, %(dialect)s,
    %(source_type)s, %(user_id)s, %(auth_user_id)s, %(session_id)s, %(original_filename)s,
    %(local_path)s, %(storage_key)s, %(storage_url)s, %(created_at)s, %(updated_at)s
)
ON CONFLICT (upload_uid) DO UPDATE SET
    class_uid = EXCLUDED.class_uid,
    slug = EXCLUDED.slug,
    label_original = EXCLUDED.label_original,
    language = EXCLUDED.language,
    dialect = EXCLUDED.dialect,
    source_type = EXCLUDED.source_type,
    user_id = EXCLUDED.user_id,
    auth_user_id = COALESCE(EXCLUDED.auth_user_id, raw_uploads.auth_user_id),
    session_id = EXCLUDED.session_id,
    original_filename = EXCLUDED.original_filename,
    local_path = EXCLUDED.local_path,
    storage_key = EXCLUDED.storage_key,
    storage_url = EXCLUDED.storage_url,
    created_at = EXCLUDED.created_at,
    updated_at = EXCLUDED.updated_at
"""


def insert_user(row: Dict[str, Any]):
    payload = {
        **row,
        "is_active": _bool_value(row.get("is_active", True)),
        "is_admin": _bool_value(row.get("is_admin", False)),
    }
    _execute(SQL_UPSERT_USER, payload)


def upsert_class(row: Dict[str, Any]):
    payload = {
        **row,
        "class_idx": _int_or_none(row.get("class_idx")),
        "is_common_global": _bool_value(row.get("is_common_global")),
        "is_common_language": _bool_value(row.get("is_common_language")),
        "created_at": _ts_or_none(row.get("created_at")),
        "migrated_at": _ts_or_none(row.get("migrated_at")),
        # CSV-derived rows may lack the column entirely or carry "" -> NULL;
        # ON CONFLICT COALESCEs so a lossy mirror upsert never wipes the value.
        "hands_required": _int_or_none(row.get("hands_required")),
    }
    _execute(SQL_UPSERT_CLASS, payload)


_SAMPLE_DB_KEYS = (
    "sample_uid", "class_uid", "slug", "label_original", "language", "dialect",
    "source_type", "user_id", "auth_user_id", "session_id", "fps_original", "fps_processed",
    "seq_len", "augment_id", "completeness", "file_path", "storage_url", "checksum",
    "created_at", "gdrive_synced",
    "left_hand_ratio", "right_hand_ratio", "both_hands_ratio", "jitter", "quality_flags",
)


def insert_sample(row: Dict[str, Any]):
    # Rows can arrive from the CSV mirror, which lacks DB-only columns
    # (auth_user_id) and names the session column differently (session_uid).
    # Build the payload defensively so a missing key never raises KeyError
    # mid-CRUD; ON CONFLICT COALESCEs auth_user_id so a lossy mirror upsert
    # doesn't wipe the real value.
    payload = {k: row.get(k) for k in _SAMPLE_DB_KEYS}
    if not payload.get("session_id"):
        payload["session_id"] = row.get("session_id") or row.get("session_uid") or ""
    # Numeric columns are empty strings in the CSV mirror; coerce "" -> NULL so
    # Postgres doesn't reject them ("invalid input syntax for type real/integer").
    payload["seq_len"] = _int_or_none(payload.get("seq_len"))
    payload["augment_id"] = _int_or_none(payload.get("augment_id"))
    payload["completeness"] = _float_or_none(payload.get("completeness"))
    for qc_key in ("left_hand_ratio", "right_hand_ratio", "both_hands_ratio", "jitter"):
        payload[qc_key] = _float_or_none(payload.get(qc_key))
    if payload.get("quality_flags") == "":
        payload["quality_flags"] = None
    payload["created_at"] = _ts_or_none(payload.get("created_at"))
    if payload.get("gdrive_synced") is None:
        payload["gdrive_synced"] = True
    _execute(SQL_UPSERT_SAMPLE, payload)


def upsert_sample(row: Dict[str, Any]):
    # backward-compatible name expected by catalog_sync
    insert_sample(row)


def delete_sample(sample_uid: str):
    _execute("DELETE FROM samples WHERE sample_uid = %s", (sample_uid,))


def update_sample_gdrive_url(sample_uid: str, storage_url: str):
    _execute(
        "UPDATE samples SET storage_url = %s, gdrive_synced = TRUE WHERE sample_uid = %s",
        (storage_url, sample_uid)
    )


def delete_samples_by_class(class_uid: str):
    _execute("DELETE FROM samples WHERE class_uid = %s", (class_uid,))


_RAW_UPLOAD_DB_KEYS = (
    "upload_uid", "class_uid", "slug", "label_original", "language", "dialect",
    "source_type", "user_id", "auth_user_id", "session_id", "original_filename",
    "local_path", "storage_key", "storage_url", "created_at", "updated_at",
)


def insert_raw_upload(row: Dict[str, Any]):
    payload = {k: row.get(k) for k in _RAW_UPLOAD_DB_KEYS}
    if not payload.get("session_id"):
        payload["session_id"] = row.get("session_id") or row.get("session_uid") or ""
    payload["created_at"] = _ts_or_none(payload.get("created_at"))
    payload["updated_at"] = _ts_or_none(payload.get("updated_at"))
    _execute(SQL_UPSERT_RAW_UPLOAD, payload)


def update_raw_upload_gdrive_url(upload_uid: str, storage_url: str):
    from datetime import datetime

    _execute(
        "UPDATE raw_uploads SET storage_url = %s, updated_at = %s WHERE upload_uid = %s",
        (storage_url, datetime.utcnow().isoformat() + "Z", upload_uid),
    )


# ============================================================================
# Training jobs persistence
#
# Source of truth for training job history — the in-memory dict in the
# training router is only a hot cache. All writes are idempotent upserts so
# the router can call them from any state transition without ordering bugs.
# ============================================================================

SQL_UPSERT_TRAINING_JOB = """
INSERT INTO training_jobs(
    job_id, status, model_type, config, auth_user_id,
    created_at, started_at, completed_at,
    current_epoch, total_epochs, checkpoint_path,
    test_acc, test_f1, error_message, promoted_at, evaluation
)
VALUES(
    %(job_id)s, %(status)s, %(model_type)s, %(config)s, %(auth_user_id)s,
    %(created_at)s, %(started_at)s, %(completed_at)s,
    %(current_epoch)s, %(total_epochs)s, %(checkpoint_path)s,
    %(test_acc)s, %(test_f1)s, %(error_message)s, %(promoted_at)s, %(evaluation)s
)
ON CONFLICT (job_id) DO UPDATE SET
    status = EXCLUDED.status,
    started_at = EXCLUDED.started_at,
    completed_at = EXCLUDED.completed_at,
    current_epoch = EXCLUDED.current_epoch,
    checkpoint_path = EXCLUDED.checkpoint_path,
    test_acc = EXCLUDED.test_acc,
    test_f1 = EXCLUDED.test_f1,
    error_message = EXCLUDED.error_message,
    promoted_at = EXCLUDED.promoted_at,
    evaluation = COALESCE(EXCLUDED.evaluation, training_jobs.evaluation)
"""


def upsert_training_job(row: Dict[str, Any]):
    payload = dict(row)
    payload.setdefault("evaluation", None)
    for jsonb_field in ("config", "evaluation"):
        value = payload.get(jsonb_field)
        if isinstance(value, (dict, list)):
            payload[jsonb_field] = Json(value)
    _execute(SQL_UPSERT_TRAINING_JOB, payload)


def insert_training_metric(row: Dict[str, Any]):
    _execute(
        """
        INSERT INTO training_metrics(job_id, epoch, train_loss, train_acc, val_loss, val_acc, val_f1)
        VALUES(%(job_id)s, %(epoch)s, %(train_loss)s, %(train_acc)s, %(val_loss)s, %(val_acc)s, %(val_f1)s)
        ON CONFLICT (job_id, epoch) DO NOTHING
        """,
        row,
    )


def _fetch_all(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    conn = get_pooled_conn()
    broken = False
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]
    except Exception:
        broken = bool(getattr(conn, "closed", 0))
        raise
    finally:
        put_pooled_conn(conn, close=broken)


def get_training_job(job_id: str) -> Optional[Dict[str, Any]]:
    rows = _fetch_all("SELECT * FROM training_jobs WHERE job_id = %s", (job_id,))
    return rows[0] if rows else None


def list_training_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    return _fetch_all(
        "SELECT * FROM training_jobs ORDER BY created_at DESC LIMIT %s", (limit,)
    )


def list_training_jobs_with_user(limit: int = 100) -> List[Dict[str, Any]]:
    """Job history rows + username of who started each job (for the history UI).

    Excludes the heavy `evaluation` JSONB — the list view doesn't need
    confusion matrices; the detail view fetches them per job.
    """
    return _fetch_all(
        """
        SELECT
            t.job_id, t.status, t.model_type, t.config, t.auth_user_id,
            t.created_at, t.started_at, t.completed_at,
            t.current_epoch, t.total_epochs, t.checkpoint_path,
            t.test_acc, t.test_f1, t.error_message, t.promoted_at,
            u.username
        FROM training_jobs t
        LEFT JOIN users u ON u.id = t.auth_user_id
        ORDER BY t.created_at DESC
        LIMIT %s
        """,
        (limit,),
    )


def list_training_metrics(job_id: str) -> List[Dict[str, Any]]:
    return _fetch_all(
        "SELECT * FROM training_metrics WHERE job_id = %s ORDER BY epoch ASC", (job_id,)
    )


def delete_training_job(job_id: str) -> None:
    """Xóa training job khỏi lịch sử (kèm metrics liên quan).

    Không xóa checkpoint file trên đĩa — job đã promote có thể vẫn đang
    được realtime service dùng; chỉ dọn bản ghi lịch sử.
    """
    _execute("DELETE FROM training_metrics WHERE job_id = %s", (job_id,))
    _execute("DELETE FROM training_jobs WHERE job_id = %s", (job_id,))


def upsert_raw_upload(row: Dict[str, Any]):
    # backward-compatible name expected by catalog_sync
    insert_raw_upload(row)


def delete_raw_upload(upload_uid: str):
    _execute("DELETE FROM raw_uploads WHERE upload_uid = %s", (upload_uid,))


def delete_raw_uploads_by_class(class_uid: str):
    _execute("DELETE FROM raw_uploads WHERE class_uid = %s", (class_uid,))


def delete_class(class_uid: str):
    _execute("DELETE FROM classes WHERE class_uid = %s", (class_uid,))


# ---------------------------------------------------------------------------
# Soft delete / restore (Trash) — sets deleted_at instead of removing the row.
# Files and Drive content are kept; a purge (hard delete) removes them later.
# ---------------------------------------------------------------------------

def soft_delete_class(class_uid: str):
    _execute("UPDATE classes SET deleted_at = NOW() WHERE class_uid = %s AND deleted_at IS NULL", (class_uid,))


def soft_delete_samples_by_class(class_uid: str):
    _execute("UPDATE samples SET deleted_at = NOW() WHERE class_uid = %s AND deleted_at IS NULL", (class_uid,))


def soft_delete_raw_uploads_by_class(class_uid: str):
    _execute("UPDATE raw_uploads SET deleted_at = NOW() WHERE class_uid = %s AND deleted_at IS NULL", (class_uid,))


def restore_class(class_uid: str):
    _execute("UPDATE classes SET deleted_at = NULL WHERE class_uid = %s", (class_uid,))


def restore_samples_by_class(class_uid: str):
    _execute("UPDATE samples SET deleted_at = NULL WHERE class_uid = %s", (class_uid,))


def restore_raw_uploads_by_class(class_uid: str):
    _execute("UPDATE raw_uploads SET deleted_at = NULL WHERE class_uid = %s", (class_uid,))


def soft_delete_sample(sample_uid: str):
    _execute("UPDATE samples SET deleted_at = NOW() WHERE sample_uid = %s AND deleted_at IS NULL", (sample_uid,))


def restore_sample(sample_uid: str):
    _execute("UPDATE samples SET deleted_at = NULL WHERE sample_uid = %s", (sample_uid,))


def list_deleted_classes() -> List[Dict[str, Any]]:
    """Soft-deleted classes for the Trash view, with their live sample counts."""
    return _fetch_all(
        """
        SELECT c.class_uid, c.class_idx, c.slug, c.label_original, c.language,
               c.dialect, c.is_common_global, c.is_common_language, c.folder_name,
               c.created_at, c.migrated_at, c.deleted_at,
               (SELECT COUNT(*) FROM samples s WHERE s.class_uid = c.class_uid) AS sample_count
        FROM classes c
        WHERE c.deleted_at IS NOT NULL
        ORDER BY c.deleted_at DESC
        """
    )


def get_deleted_class(class_uid: str) -> Optional[Dict[str, Any]]:
    rows = _fetch_all("SELECT * FROM classes WHERE class_uid = %s AND deleted_at IS NOT NULL", (class_uid,))
    return rows[0] if rows else None


def list_samples_by_class(class_uid: str, include_deleted: bool = True) -> List[Dict[str, Any]]:
    where = "class_uid = %s" if include_deleted else "class_uid = %s AND deleted_at IS NULL"
    return _fetch_all(f"SELECT * FROM samples WHERE {where}", (class_uid,))


def list_deleted_samples() -> List[Dict[str, Any]]:
    """Soft-deleted samples whose CLASS is still active (class-level trash lists
    classes separately, so this avoids double-listing a whole deleted class)."""
    return _fetch_all(
        """
        SELECT s.sample_uid, s.class_uid, s.slug, s.label_original, s.language,
               s.dialect, s.source_type, s.user_id, s.username, s.file_path,
               s.storage_url, s.seq_len, s.created_at, s.deleted_at
        FROM samples s
        JOIN classes c ON c.class_uid = s.class_uid
        WHERE s.deleted_at IS NOT NULL AND c.deleted_at IS NULL
        ORDER BY s.deleted_at DESC
        """
    )


def get_deleted_sample(sample_uid: str) -> Optional[Dict[str, Any]]:
    rows = _fetch_all("SELECT * FROM samples WHERE sample_uid = %s AND deleted_at IS NOT NULL", (sample_uid,))
    return rows[0] if rows else None


def get_sample_owner(sample_uid: str):
    """Return auth_user_id (str or None) for a sample. Used for ownership checks."""
    try:
        with _cursor() as cur:
            cur.execute(
                "SELECT auth_user_id FROM samples WHERE sample_uid = %s",
                (sample_uid,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return str(row[0]) if row[0] is not None else None
    except Exception:
        return None


def resolve_absolute_path(db_path_str: str) -> 'Path':
    """Resolve a file path from the database to an absolute path.

    Handles both absolute paths (legacy data) and relative paths (new data).
    Relative paths are resolved relative to DATASET_ROOT.
    """
    from pathlib import Path
    from app.config import settings
    path = Path(db_path_str)
    if path.is_absolute():
        return path
    return settings.dataset_root / path


def mark_samples_synced(sample_uids: list) -> None:
    """Mark a batch of samples as synced to Google Sheets."""
    if not sample_uids:
        return
    with _cursor() as cur:
        cur.execute(
            "UPDATE samples SET sheets_synced = TRUE WHERE sample_uid = ANY(%s)",
            (sample_uids,),
        )


def fetch_unsynced_samples(limit: int = 5000) -> list:
    """Fetch samples not yet synced to Google Sheets, ordered by creation time."""
    with _cursor() as cur:
        cur.execute(
            """
            SELECT sample_uid, class_uid, slug, label_original, language, dialect,
                   source_type, user_id, session_id, fps_original, fps_processed,
                   seq_len, augment_id, completeness, file_path, storage_url,
                   checksum, created_at
            FROM samples
            WHERE sheets_synced = FALSE AND gdrive_synced = TRUE
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (limit,),
        )
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def get_sync_status(table_name: str) -> dict | None:
    """Get Google Sheets sync pointer for a table."""
    try:
        with _cursor() as cur:
            cur.execute(
                "SELECT current_spreadsheet_id, current_sheet_index, current_data_rows, max_rows_per_sheet "
                "FROM google_sheets_sync_status WHERE table_name = %s",
                (table_name,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {
                "current_spreadsheet_id": row[0],
                "current_sheet_index": row[1],
                "current_data_rows": row[2],
                "max_rows_per_sheet": row[3],
            }
    except Exception:
        return None


def upsert_sync_status(table_name: str, spreadsheet_id: str, sheet_index: int, data_rows: int) -> None:
    """Create or update Google Sheets sync pointer."""
    _execute(
        """
        INSERT INTO google_sheets_sync_status (table_name, current_spreadsheet_id, current_sheet_index, current_data_rows, updated_at)
        VALUES (%(table_name)s, %(spreadsheet_id)s, %(sheet_index)s, %(data_rows)s, NOW())
        ON CONFLICT (table_name) DO UPDATE SET
            current_spreadsheet_id = EXCLUDED.current_spreadsheet_id,
            current_sheet_index = EXCLUDED.current_sheet_index,
            current_data_rows = EXCLUDED.current_data_rows,
            updated_at = NOW()
        """,
        {
            "table_name": table_name,
            "spreadsheet_id": spreadsheet_id,
            "sheet_index": sheet_index,
            "data_rows": data_rows,
        },
    )
