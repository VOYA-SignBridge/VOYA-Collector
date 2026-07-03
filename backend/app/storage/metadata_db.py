import psycopg2
from contextlib import contextmanager
from typing import Any, Dict, Optional, List, Tuple
import logging
import re

from app.config import settings
from app.storage.postgres_connection import connect_postgres

logger = logging.getLogger(__name__)

def _get_conn():
    # connect_timeout + application_name giúp dễ quan sát và fail fast hơn trong production
    return connect_postgres(
        connect_timeout=5,
        application_name="voya_backend_metadata_db",
    )


@contextmanager
def _cursor():
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                yield cur
    finally:
        conn.close()


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
    if text.lower() == "none" or text == "":
        return None
    return int(float(text))

def _float_or_none(value: Any) -> float | None:
    text = str(value).strip() if value is not None else ""
    if text.lower() == "none" or text == "":
        return None
    return float(text)


DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS roles (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(50) NOT NULL UNIQUE,
        description TEXT DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS languages (
        code VARCHAR(50) PRIMARY KEY,
        name TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dialects (
        code VARCHAR(50) PRIMARY KEY,
        language_code VARCHAR(50) REFERENCES languages(code),
        name TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_profiles (
        user_id UUID PRIMARY KEY,
        username TEXT UNIQUE,
        full_name TEXT DEFAULT '',
        avatar_url TEXT,
        yob INTEGER,
        gender TEXT,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )
    """,
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
        description TEXT DEFAULT '',
        language TEXT,
        dialect TEXT,
        is_common_global BOOLEAN,
        is_common_language BOOLEAN,
        is_active BOOLEAN DEFAULT TRUE,
        folder_name TEXT,
        created_at TIMESTAMP WITH TIME ZONE,
        migrated_at TIMESTAMP WITH TIME ZONE,
        deleted_at TIMESTAMP WITH TIME ZONE
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
        session_uid TEXT,
        fps_original TEXT,
        fps_processed TEXT,
        seq_len INTEGER,
        augment_id INTEGER,
        completeness REAL,
        file_path TEXT,
        storage_key TEXT DEFAULT '',
        storage_url TEXT,
        checksum TEXT,
        status VARCHAR(20) DEFAULT 'PENDING',
        error_log TEXT DEFAULT '',
        created_at TIMESTAMP WITH TIME ZONE,
        updated_at TIMESTAMP WITH TIME ZONE,
        deleted_at TIMESTAMP WITH TIME ZONE,
        gdrive_synced BOOLEAN DEFAULT FALSE
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
        session_uid TEXT,
        original_filename TEXT,
        local_path TEXT,
        storage_key TEXT,
        storage_url TEXT,
        status VARCHAR(20) DEFAULT 'PENDING',
        created_at TIMESTAMP WITH TIME ZONE,
        updated_at TIMESTAMP WITH TIME ZONE,
        deleted_at TIMESTAMP WITH TIME ZONE
    )
    """,
]

INDEX_STATEMENTS = [
    # users.username/users.email đã có UNIQUE -> PostgreSQL tự tạo index, không cần tạo thêm index trùng
    "CREATE INDEX IF NOT EXISTS idx_classes_class_idx ON classes(class_idx)",
    "CREATE INDEX IF NOT EXISTS idx_classes_slug ON classes(slug)",
    "CREATE INDEX IF NOT EXISTS idx_classes_lang_dialect ON classes(language, dialect)",
    "CREATE INDEX IF NOT EXISTS idx_samples_class_uid ON samples(class_uid)",
    "CREATE INDEX IF NOT EXISTS idx_samples_user_id ON samples(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_samples_created_at ON samples(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_raw_uploads_class_uid ON raw_uploads(class_uid)",
    "CREATE INDEX IF NOT EXISTS idx_raw_uploads_session_uid ON raw_uploads(session_uid)",
    "CREATE INDEX IF NOT EXISTS idx_raw_uploads_user_id ON raw_uploads(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_uploads_created_at ON raw_uploads(created_at DESC)",
    # Partial index for Celery export: only indexes rows not yet synced to Sheets
    "CREATE INDEX IF NOT EXISTS idx_samples_sheets_synced ON samples(sheets_synced) WHERE sheets_synced = FALSE",
    # Phase 2: indexes for soft delete, status queries
    "CREATE INDEX IF NOT EXISTS idx_classes_deleted_at ON classes(deleted_at) WHERE deleted_at IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_samples_deleted_at ON samples(deleted_at) WHERE deleted_at IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_samples_status ON samples(status)",
    "CREATE INDEX IF NOT EXISTS idx_raw_uploads_deleted_at ON raw_uploads(deleted_at) WHERE deleted_at IS NULL",
]

MIGRATION_STATEMENTS = [
    # --- Phase 1: Auth & RBAC ---
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS role_id UUID REFERENCES roles(id)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20) UNIQUE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE",
    # Populate role_id for existing users
    "UPDATE users SET role_id = (SELECT id FROM roles WHERE name = 'admin' LIMIT 1) WHERE is_admin = TRUE AND role_id IS NULL",
    "UPDATE users SET role_id = (SELECT id FROM roles WHERE name = 'contributor' LIMIT 1) WHERE is_admin = FALSE AND role_id IS NULL",

    # Add sheets_synced column to samples (safe for existing data: defaults to FALSE)
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS sheets_synced BOOLEAN DEFAULT FALSE",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS gdrive_synced BOOLEAN DEFAULT TRUE",
    # --- Phase 2: Soft Delete, Status, Error Handling ---
    # Classes: soft delete + metadata
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS description TEXT DEFAULT ''",
    "ALTER TABLE classes ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
    # Samples: soft delete + status + error tracking
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'PENDING'",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS error_log TEXT DEFAULT ''",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS storage_key TEXT DEFAULT ''",
    # Raw uploads: soft delete + status
    "ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'PENDING'",
    # --- Phase 2: Rename session_id → session_uid ---
    # Safe rename: add new column, copy data, keep old column for backward compat
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS session_uid TEXT",
    "ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS session_uid TEXT",
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
    # Backfill session_uid from session_id for existing rows
    "UPDATE samples SET session_uid = session_id WHERE session_uid IS NULL AND session_id IS NOT NULL",
    "UPDATE raw_uploads SET session_uid = session_id WHERE session_uid IS NULL AND session_id IS NOT NULL",
    
    # --- Phase 2.1: Fix user_id and username ---
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS username TEXT",
    "ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS username TEXT",
    # Migrate plain text names to username, keeping UUID format untouched
    "UPDATE samples SET username = user_id WHERE user_id NOT LIKE '%-%-%-%-%' AND user_id IS NOT NULL AND user_id != ''",
    "UPDATE raw_uploads SET username = user_id WHERE user_id NOT LIKE '%-%-%-%-%' AND user_id IS NOT NULL AND user_id != ''",
    # Clear invalid user_ids (names) from user_id column
    "UPDATE samples SET user_id = NULL WHERE user_id NOT LIKE '%-%-%-%-%'",
    "UPDATE raw_uploads SET user_id = NULL WHERE user_id NOT LIKE '%-%-%-%-%'",
    # Backfill valid UUIDs from users table into user_id by matching username
    "UPDATE samples s SET user_id = u.id::text FROM users u WHERE s.username = u.username AND s.user_id IS NULL",
    "UPDATE raw_uploads r SET user_id = u.id::text FROM users u WHERE r.username = u.username AND r.user_id IS NULL",
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

    # Seed data
    try:
        _execute("""
        INSERT INTO roles (name, description) VALUES
            ('admin', 'Quản trị hệ thống toàn quyền'),
            ('contributor', 'Người đóng góp dữ liệu'),
            ('guest', 'Khách xem dữ liệu công khai')
        ON CONFLICT (name) DO NOTHING;
        """)
        
        _execute("""
        INSERT INTO languages (code, name) VALUES
            ('vn', 'Tiếng Việt'),
            ('en', 'English')
        ON CONFLICT (code) DO NOTHING;
        """)

        _execute("""
        INSERT INTO dialects (code, language_code, name) VALUES
            ('common', 'vn', 'Chung'),
            ('bac', 'vn', 'Miền Bắc'),
            ('nam', 'vn', 'Miền Nam'),
            ('trung', 'vn', 'Miền Trung'),
            ('hoa-de', 'vn', 'Hòa Đê'),
            ('can-tho', 'vn', 'Cần Thơ'),
            ('bang-chu-cai', 'vn', 'Bảng chữ cái'),
            ('spa', 'vn', 'Spa')
        ON CONFLICT (code) DO NOTHING;
        """)

        # Populate role_id for existing users after roles are seeded
        _execute("UPDATE users SET role_id = (SELECT id FROM roles WHERE name = 'admin' LIMIT 1) WHERE is_admin = TRUE AND role_id IS NULL")
        _execute("UPDATE users SET role_id = (SELECT id FROM roles WHERE name = 'contributor' LIMIT 1) WHERE is_admin = FALSE AND role_id IS NULL")
    except Exception as exc:
        logger.warning("ensure_tables: seed data failed (ignored): %s", getattr(exc, "pgerror", str(exc)))

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
    class_uid, class_idx, slug, label_original, description, language, dialect,
    is_common_global, is_common_language, is_active, folder_name, created_at, migrated_at, deleted_at
)
VALUES(
    %(class_uid)s, %(class_idx)s, %(slug)s, %(label_original)s, %(description)s, %(language)s, %(dialect)s,
    %(is_common_global)s, %(is_common_language)s, %(is_active)s, %(folder_name)s, %(created_at)s, %(migrated_at)s, %(deleted_at)s
)
ON CONFLICT (class_uid) DO UPDATE SET
    class_idx = EXCLUDED.class_idx,
    slug = EXCLUDED.slug,
    label_original = EXCLUDED.label_original,
    description = EXCLUDED.description,
    language = EXCLUDED.language,
    dialect = EXCLUDED.dialect,
    is_common_global = EXCLUDED.is_common_global,
    is_common_language = EXCLUDED.is_common_language,
    is_active = EXCLUDED.is_active,
    folder_name = EXCLUDED.folder_name,
    created_at = EXCLUDED.created_at,
    migrated_at = EXCLUDED.migrated_at,
    deleted_at = EXCLUDED.deleted_at
"""

SQL_UPSERT_SAMPLE = """
INSERT INTO samples(
    sample_uid, class_uid, slug, label_original, language, dialect,
    source_type, user_id, username, session_uid, fps_original, fps_processed,
    seq_len, augment_id, completeness, file_path, storage_key, storage_url, checksum,
    status, error_log, created_at, updated_at, deleted_at, gdrive_synced, sheets_synced
)
VALUES(
    %(sample_uid)s, %(class_uid)s, %(slug)s, %(label_original)s, %(language)s, %(dialect)s,
    %(source_type)s, %(user_id)s, %(username)s, %(session_uid)s, %(fps_original)s, %(fps_processed)s,
    %(seq_len)s, %(augment_id)s, %(completeness)s, %(file_path)s, %(storage_key)s, %(storage_url)s, %(checksum)s,
    %(status)s, %(error_log)s, %(created_at)s, %(updated_at)s, %(deleted_at)s, %(gdrive_synced)s, %(sheets_synced)s
)
ON CONFLICT (sample_uid) DO UPDATE SET
    class_uid = EXCLUDED.class_uid,
    slug = EXCLUDED.slug,
    label_original = EXCLUDED.label_original,
    language = EXCLUDED.language,
    dialect = EXCLUDED.dialect,
    source_type = EXCLUDED.source_type,
    user_id = EXCLUDED.user_id,
    username = EXCLUDED.username,
    session_uid = EXCLUDED.session_uid,
    fps_original = EXCLUDED.fps_original,
    fps_processed = EXCLUDED.fps_processed,
    seq_len = EXCLUDED.seq_len,
    augment_id = EXCLUDED.augment_id,
    completeness = EXCLUDED.completeness,
    file_path = EXCLUDED.file_path,
    storage_key = EXCLUDED.storage_key,
    storage_url = EXCLUDED.storage_url,
    checksum = EXCLUDED.checksum,
    status = EXCLUDED.status,
    error_log = EXCLUDED.error_log,
    created_at = EXCLUDED.created_at,
    updated_at = EXCLUDED.updated_at,
    deleted_at = EXCLUDED.deleted_at,
    gdrive_synced = EXCLUDED.gdrive_synced,
    sheets_synced = EXCLUDED.sheets_synced
"""

SQL_UPSERT_RAW_UPLOAD = """
INSERT INTO raw_uploads(
    upload_uid, class_uid, slug, label_original, language, dialect,
    source_type, user_id, username, session_uid, original_filename,
    local_path, storage_key, storage_url, status, created_at, updated_at, deleted_at
)
VALUES(
    %(upload_uid)s, %(class_uid)s, %(slug)s, %(label_original)s, %(language)s, %(dialect)s,
    %(source_type)s, %(user_id)s, %(username)s, %(session_uid)s, %(original_filename)s,
    %(local_path)s, %(storage_key)s, %(storage_url)s, %(status)s, %(created_at)s, %(updated_at)s, %(deleted_at)s
)
ON CONFLICT (upload_uid) DO UPDATE SET
    class_uid = EXCLUDED.class_uid,
    slug = EXCLUDED.slug,
    label_original = EXCLUDED.label_original,
    language = EXCLUDED.language,
    dialect = EXCLUDED.dialect,
    source_type = EXCLUDED.source_type,
    user_id = EXCLUDED.user_id,
    username = EXCLUDED.username,
    session_uid = EXCLUDED.session_uid,
    original_filename = EXCLUDED.original_filename,
    local_path = EXCLUDED.local_path,
    storage_key = EXCLUDED.storage_key,
    storage_url = EXCLUDED.storage_url,
    status = EXCLUDED.status,
    created_at = EXCLUDED.created_at,
    updated_at = EXCLUDED.updated_at,
    deleted_at = EXCLUDED.deleted_at
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
        "description": row.get("description", ""),
        "is_common_global": _bool_value(row.get("is_common_global")),
        "is_common_language": _bool_value(row.get("is_common_language")),
        "is_active": _bool_value(row.get("is_active", True)),
        "created_at": row.get("created_at") or None,
        "migrated_at": row.get("migrated_at") or None,
        "deleted_at": row.get("deleted_at") or None,
    }
    _execute(SQL_UPSERT_CLASS, payload)


def insert_sample(row: Dict[str, Any]):
    payload = dict(row)
    if "gdrive_synced" not in payload:
        payload["gdrive_synced"] = True
    if "sheets_synced" not in payload:
        payload["sheets_synced"] = False
    # Phase 2: new columns with safe defaults
    if "status" not in payload:
        payload["status"] = "PENDING"
    if "error_log" not in payload:
        payload["error_log"] = ""
    if "updated_at" not in payload:
        payload["updated_at"] = None
    if "deleted_at" not in payload:
        payload["deleted_at"] = None
    if "storage_key" not in payload:
        payload["storage_key"] = ""
    # Backward compat: accept session_id, map to session_uid
    if "session_uid" not in payload and "session_id" in payload:
        payload["session_uid"] = payload.pop("session_id")
    elif "session_uid" not in payload:
        payload["session_uid"] = ""
        
    # Ensure all required SQL keys exist
    expected_keys = [
        "user_id", "username", "source_type", "fps_original", "fps_processed", 
        "seq_len", "augment_id", "completeness", "file_path", "storage_url", "checksum"
    ]
    for k in expected_keys:
        if k not in payload:
            payload[k] = None

    payload["fps_original"] = _float_or_none(payload.get("fps_original"))
    payload["fps_processed"] = _float_or_none(payload.get("fps_processed"))
    payload["seq_len"] = _int_or_none(payload.get("seq_len"))
    payload["augment_id"] = _int_or_none(payload.get("augment_id"))
    payload["completeness"] = _float_or_none(payload.get("completeness"))
    payload["created_at"] = payload.get("created_at") or None
    payload["updated_at"] = payload.get("updated_at") or None
    payload["deleted_at"] = payload.get("deleted_at") or None
    
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


def insert_raw_upload(row: Dict[str, Any]):
    payload = dict(row)
    # Backward compat: accept session_id, map to session_uid
    if "session_uid" not in payload and "session_id" in payload:
        payload["session_uid"] = payload.pop("session_id")
    elif "session_uid" not in payload:
        payload["session_uid"] = ""
    if "status" not in payload:
        payload["status"] = "PENDING"
    if "deleted_at" not in payload:
        payload["deleted_at"] = None
    if "updated_at" not in payload:
        payload["updated_at"] = None

    expected_keys = [
        "user_id", "username", "source_type", "original_filename", 
        "local_path", "storage_key", "storage_url"
    ]
    for k in expected_keys:
        if k not in payload:
            payload[k] = None
            
    payload["created_at"] = payload.get("created_at") or None
    payload["updated_at"] = payload.get("updated_at") or None
    payload["deleted_at"] = payload.get("deleted_at") or None
    
    _execute(SQL_UPSERT_RAW_UPLOAD, payload)


def upsert_raw_upload(row: Dict[str, Any]):
    # backward-compatible name expected by catalog_sync
    insert_raw_upload(row)


def delete_raw_upload(upload_uid: str):
    _execute("DELETE FROM raw_uploads WHERE upload_uid = %s", (upload_uid,))


def delete_raw_uploads_by_class(class_uid: str):
    _execute("DELETE FROM raw_uploads WHERE class_uid = %s", (class_uid,))


def delete_class(class_uid: str):
    _execute("DELETE FROM classes WHERE class_uid = %s", (class_uid,))


def get_sample_owner(sample_uid: str) -> Optional[str]:
    """Return user_id (str or None) for a sample. Used for ownership checks."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id FROM samples WHERE sample_uid = %s",
                    (sample_uid,)
                )
                row = cur.fetchone()
                if row and row[0]:
                    return str(row[0])
    except Exception as e:
        logging.getLogger(__name__).error("[GET_SAMPLE_OWNER] %s", e)
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
                   source_type, user_id, session_uid, fps_original, fps_processed,
                   seq_len, augment_id, completeness, file_path, storage_key, storage_url,
                   checksum, status, created_at
            FROM samples
            WHERE sheets_synced = FALSE AND gdrive_synced = TRUE AND deleted_at IS NULL
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


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 2: Soft Delete / Restore / Hard Delete / Status / Clean Queries
# ─────────────────────────────────────────────────────────────────────────────

def soft_delete_class(class_uid: str) -> None:
    """Move a class to trash by setting deleted_at."""
    _execute(
        "UPDATE classes SET deleted_at = NOW() WHERE class_uid = %s AND deleted_at IS NULL",
        (class_uid,),
    )


def restore_class(class_uid: str) -> None:
    """Restore a class from trash."""
    _execute(
        "UPDATE classes SET deleted_at = NULL WHERE class_uid = %s AND deleted_at IS NOT NULL",
        (class_uid,),
    )


def soft_delete_sample(sample_uid: str) -> None:
    """Move a sample to trash."""
    _execute(
        "UPDATE samples SET deleted_at = NOW(), status = 'DELETED', updated_at = NOW() WHERE sample_uid = %s AND deleted_at IS NULL",
        (sample_uid,),
    )


def restore_sample(sample_uid: str) -> None:
    """Restore a sample from trash."""
    _execute(
        "UPDATE samples SET deleted_at = NULL, status = 'PENDING', updated_at = NOW() WHERE sample_uid = %s AND deleted_at IS NOT NULL",
        (sample_uid,),
    )


def update_sample_status(sample_uid: str, status: str, error_log: str = "") -> None:
    """Update sample processing status. Used by Celery workers for DLQ tracking."""
    _execute(
        "UPDATE samples SET status = %s, error_log = %s, updated_at = NOW() WHERE sample_uid = %s",
        (status, error_log, sample_uid),
    )


def fetch_active_classes() -> list:
    """Fetch all classes NOT in trash. Used for clean CSV export."""
    with _cursor() as cur:
        cur.execute(
            """
            SELECT class_uid, class_idx, slug, label_original, description,
                   language, dialect, is_common_global, is_common_language,
                   is_active, folder_name, created_at, migrated_at
            FROM classes
            WHERE deleted_at IS NULL
            ORDER BY class_idx ASC
            """
        )
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def fetch_active_samples() -> list:
    """Fetch all samples NOT in trash. Used for clean CSV export."""
    with _cursor() as cur:
        cur.execute(
            """
            SELECT sample_uid, class_uid, slug, label_original, language, dialect,
                   source_type, user_id, session_uid, fps_original, fps_processed,
                   seq_len, augment_id, completeness, file_path, storage_key,
                   storage_url, checksum, status, created_at, updated_at
            FROM samples
            WHERE deleted_at IS NULL
            ORDER BY created_at ASC
            """
        )
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def list_trash_classes() -> list:
    """Fetch all soft-deleted classes (Trash Bin view)."""
    with _cursor() as cur:
        cur.execute(
            """
            SELECT class_uid, class_idx, slug, label_original, language, dialect,
                   folder_name, created_at, deleted_at
            FROM classes
            WHERE deleted_at IS NOT NULL
            ORDER BY deleted_at DESC
            """
        )
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def list_trash_samples() -> list:
    """Fetch all soft-deleted samples (Trash Bin view)."""
    with _cursor() as cur:
        cur.execute(
            """
            SELECT sample_uid, class_uid, slug, label_original, user_id,
                   status, error_log, created_at, deleted_at
            FROM samples
            WHERE deleted_at IS NOT NULL
            ORDER BY deleted_at DESC
            """
        )
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


# --- Phase 1: Auth & RBAC ---

def upsert_role(name: str, description: str = "") -> dict:
    """Upsert a role by name."""
    with _cursor() as cur:
        cur.execute(
            """
            INSERT INTO roles (name, description)
            VALUES (%s, %s)
            ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
            RETURNING id, name, description
            """,
            (name, description)
        )
        row = cur.fetchone()
        columns = [desc[0] for desc in cur.description]
        return dict(zip(columns, row))


def upsert_user_profile(user_id: str, profile_data: dict) -> dict:
    """Upsert user profile."""
    username = profile_data.get("username")
    full_name = profile_data.get("full_name", "")
    avatar_url = profile_data.get("avatar_url")
    yob = profile_data.get("yob")
    gender = profile_data.get("gender")
    with _cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_profiles (user_id, username, full_name, avatar_url, yob, gender, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                full_name = EXCLUDED.full_name,
                avatar_url = EXCLUDED.avatar_url,
                yob = EXCLUDED.yob,
                gender = EXCLUDED.gender,
                updated_at = NOW()
            RETURNING user_id, username, full_name, avatar_url, yob, gender, updated_at
            """,
            (user_id, username, full_name, avatar_url, yob, gender)
        )
        row = cur.fetchone()
        columns = [desc[0] for desc in cur.description]
        return dict(zip(columns, row))


def get_user_with_role(user_id: str) -> dict:
    """Get user along with role name and profile."""
    with _cursor() as cur:
        cur.execute(
            """
            SELECT u.id, u.username, u.email, u.is_active, u.created_at, u.updated_at,
                   r.name as role,
                   p.full_name, p.avatar_url, p.yob, p.gender
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            LEFT JOIN user_profiles p ON u.id = p.user_id
            WHERE u.id = %s AND u.deleted_at IS NULL
            """,
            (user_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        columns = [desc[0] for desc in cur.description]
        return dict(zip(columns, row))
