import psycopg2
from contextlib import contextmanager
from typing import Any, Dict
import logging
import re

from app.config import settings

logger = logging.getLogger(__name__)

def _get_conn():
    # connect_timeout + application_name giúp dễ quan sát và fail fast hơn trong production
    return psycopg2.connect(
        settings.database_url,
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
        cloudinary_public_id TEXT,
        cloudinary_url TEXT,
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
    seq_len, augment_id, completeness, file_path, storage_url, checksum, created_at
)
VALUES(
    %(sample_uid)s, %(class_uid)s, %(slug)s, %(label_original)s, %(language)s, %(dialect)s,
    %(source_type)s, %(user_id)s, %(auth_user_id)s, %(session_id)s, %(fps_original)s, %(fps_processed)s,
    %(seq_len)s, %(augment_id)s, %(completeness)s, %(file_path)s, %(storage_url)s, %(checksum)s, %(created_at)s
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
    created_at = EXCLUDED.created_at
"""

SQL_UPSERT_RAW_UPLOAD = """
INSERT INTO raw_uploads(
    upload_uid, class_uid, slug, label_original, language, dialect,
    source_type, user_id, auth_user_id, session_id, original_filename,
    local_path, storage_key, storage_url, cloudinary_public_id,
    cloudinary_url, created_at, updated_at
)
VALUES(
    %(upload_uid)s, %(class_uid)s, %(slug)s, %(label_original)s, %(language)s, %(dialect)s,
    %(source_type)s, %(user_id)s, %(auth_user_id)s, %(session_id)s, %(original_filename)s,
    %(local_path)s, %(storage_key)s, %(storage_url)s, %(cloudinary_public_id)s,
    %(cloudinary_url)s, %(created_at)s, %(updated_at)s
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
    cloudinary_public_id = EXCLUDED.cloudinary_public_id,
    cloudinary_url = EXCLUDED.cloudinary_url,
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
    _execute(SQL_UPSERT_SAMPLE, row)


def upsert_sample(row: Dict[str, Any]):
    # backward-compatible name expected by catalog_sync
    insert_sample(row)


def delete_sample(sample_uid: str):
    _execute("DELETE FROM samples WHERE sample_uid = %s", (sample_uid,))


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