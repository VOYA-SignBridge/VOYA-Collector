import psycopg2
from contextlib import contextmanager
from typing import Any, Dict
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
    return int(text) if text else None


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
        migrated_at TIMESTAMP WITH TIME ZONE
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
        FOREIGN KEY (auth_user_id) REFERENCES users(id) ON DELETE SET NULL
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
    # Partial index for Celery export: only indexes rows not yet synced to Sheets
    "CREATE INDEX IF NOT EXISTS idx_samples_sheets_synced ON samples(sheets_synced) WHERE sheets_synced = FALSE",
]

MIGRATION_STATEMENTS = [
    # Add sheets_synced column to samples (safe for existing data: defaults to FALSE)
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS sheets_synced BOOLEAN DEFAULT FALSE",
    "ALTER TABLE samples ADD COLUMN IF NOT EXISTS gdrive_synced BOOLEAN DEFAULT TRUE",
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
    is_common_global, is_common_language, folder_name, created_at, migrated_at
)
VALUES(
    %(class_uid)s, %(class_idx)s, %(slug)s, %(label_original)s, %(language)s, %(dialect)s,
    %(is_common_global)s, %(is_common_language)s, %(folder_name)s, %(created_at)s, %(migrated_at)s
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
    migrated_at = EXCLUDED.migrated_at
"""

SQL_UPSERT_SAMPLE = """
INSERT INTO samples(
    sample_uid, class_uid, slug, label_original, language, dialect,
    source_type, user_id, auth_user_id, session_id, fps_original, fps_processed,
    seq_len, augment_id, completeness, file_path, storage_url, checksum, created_at, gdrive_synced
)
VALUES(
    %(sample_uid)s, %(class_uid)s, %(slug)s, %(label_original)s, %(language)s, %(dialect)s,
    %(source_type)s, %(user_id)s, %(auth_user_id)s, %(session_id)s, %(fps_original)s, %(fps_processed)s,
    %(seq_len)s, %(augment_id)s, %(completeness)s, %(file_path)s, %(storage_url)s, %(checksum)s, %(created_at)s, %(gdrive_synced)s
)
ON CONFLICT (sample_uid) DO UPDATE SET
    class_uid = EXCLUDED.class_uid,
    slug = EXCLUDED.slug,
    label_original = EXCLUDED.label_original,
    language = EXCLUDED.language,
    dialect = EXCLUDED.dialect,
    source_type = EXCLUDED.source_type,
    user_id = EXCLUDED.user_id,
    auth_user_id = EXCLUDED.auth_user_id,
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
    gdrive_synced = EXCLUDED.gdrive_synced
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
    auth_user_id = EXCLUDED.auth_user_id,
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
    }
    _execute(SQL_UPSERT_CLASS, payload)


def insert_sample(row: Dict[str, Any]):
    if "gdrive_synced" not in row:
        row["gdrive_synced"] = True
    _execute(SQL_UPSERT_SAMPLE, row)


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
    _execute(SQL_UPSERT_RAW_UPLOAD, row)


def upsert_raw_upload(row: Dict[str, Any]):
    # backward-compatible name expected by catalog_sync
    insert_raw_upload(row)


def delete_raw_upload(upload_uid: str):
    _execute("DELETE FROM raw_uploads WHERE upload_uid = %s", (upload_uid,))


def delete_raw_uploads_by_class(class_uid: str):
    _execute("DELETE FROM raw_uploads WHERE class_uid = %s", (class_uid,))


def delete_class(class_uid: str):
    _execute("DELETE FROM classes WHERE class_uid = %s", (class_uid,))


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
