import psycopg2
from typing import Dict, Any, Iterable, List
from app.config import settings


def _get_conn():
    dburl = settings.database_url
    return psycopg2.connect(dburl)


def ensure_tables():
    sql = """
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
    );

    CREATE TABLE IF NOT EXISTS samples (
        sample_uid TEXT PRIMARY KEY,
        class_uid TEXT,
        slug TEXT,
        label_original TEXT,
        language TEXT,
        dialect TEXT,
        source_type TEXT,
        user_id TEXT,
        session_id TEXT,
        fps_original TEXT,
        fps_processed TEXT,
        seq_len INTEGER,
        augment_id INTEGER,
        completeness REAL,
        file_path TEXT,
        storage_url TEXT,
        checksum TEXT,
        created_at TIMESTAMP WITH TIME ZONE
    );

    CREATE TABLE IF NOT EXISTS raw_uploads (
        upload_uid TEXT PRIMARY KEY,
        class_uid TEXT,
        slug TEXT,
        label_original TEXT,
        language TEXT,
        dialect TEXT,
        source_type TEXT,
        user_id TEXT,
        session_id TEXT,
        original_filename TEXT,
        local_path TEXT,
        storage_key TEXT,
        storage_url TEXT,
        cloudinary_public_id TEXT,
        cloudinary_url TEXT,
        created_at TIMESTAMP WITH TIME ZONE,
        updated_at TIMESTAMP WITH TIME ZONE
    );
    """
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
    finally:
        conn.close()


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "t", "yes", "y"}


def upsert_class(row: Dict[str, Any]):
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO classes(class_uid,class_idx,slug,label_original,language,dialect,is_common_global,is_common_language,folder_name,created_at,migrated_at)
                    VALUES(%(class_uid)s,%(class_idx)s,%(slug)s,%(label_original)s,%(language)s,%(dialect)s,%(is_common_global)s,%(is_common_language)s,%(folder_name)s,%(created_at)s,%(migrated_at)s)
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
                    """,
                    {
                        **row,
                        "class_idx": int(row["class_idx"]) if str(row.get("class_idx", "")).strip() else None,
                        "is_common_global": _bool_value(row.get("is_common_global")),
                        "is_common_language": _bool_value(row.get("is_common_language")),
                    },
                )
    finally:
        conn.close()


def delete_class(class_uid: str):
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM classes WHERE class_uid = %s", (class_uid,))
    finally:
        conn.close()


def list_classes() -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT class_uid,class_idx,slug,label_original,language,dialect,is_common_global,is_common_language,folder_name,created_at,migrated_at FROM classes ORDER BY class_idx NULLS LAST, label_original ASC")
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()


def upsert_sample(row: Dict[str, Any]):
    """Insert or update a sample row into samples table."""
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO samples(sample_uid,class_uid,slug,label_original,language,dialect,source_type,user_id,session_id,fps_original,fps_processed,seq_len,augment_id,completeness,file_path,storage_url,checksum,created_at)
                    VALUES(%(sample_uid)s,%(class_uid)s,%(slug)s,%(label_original)s,%(language)s,%(dialect)s,%(source_type)s,%(user_id)s,%(session_id)s,%(fps_original)s,%(fps_processed)s,%(seq_len)s,%(augment_id)s,%(completeness)s,%(file_path)s,%(storage_url)s,%(checksum)s,%(created_at)s)
                    ON CONFLICT (sample_uid) DO UPDATE SET
                        class_uid = EXCLUDED.class_uid,
                        slug = EXCLUDED.slug,
                        label_original = EXCLUDED.label_original,
                        language = EXCLUDED.language,
                        dialect = EXCLUDED.dialect,
                        source_type = EXCLUDED.source_type,
                        user_id = EXCLUDED.user_id,
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
                    """,
                    row
                )
    finally:
        conn.close()


def insert_sample(row: Dict[str, Any]):
    upsert_sample(row)


def delete_sample(sample_uid: str):
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM samples WHERE sample_uid = %s", (sample_uid,))
    finally:
        conn.close()


def delete_samples_by_class(class_uid: str):
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM samples WHERE class_uid = %s", (class_uid,))
    finally:
        conn.close()


def upsert_raw_upload(row: Dict[str, Any]):
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO raw_uploads(upload_uid,class_uid,slug,label_original,language,dialect,source_type,user_id,session_id,original_filename,local_path,storage_key,storage_url,cloudinary_public_id,cloudinary_url,created_at,updated_at)
                    VALUES(%(upload_uid)s,%(class_uid)s,%(slug)s,%(label_original)s,%(language)s,%(dialect)s,%(source_type)s,%(user_id)s,%(session_id)s,%(original_filename)s,%(local_path)s,%(storage_key)s,%(storage_url)s,%(cloudinary_public_id)s,%(cloudinary_url)s,%(created_at)s,%(updated_at)s)
                    ON CONFLICT (upload_uid) DO UPDATE SET
                        class_uid = EXCLUDED.class_uid,
                        slug = EXCLUDED.slug,
                        label_original = EXCLUDED.label_original,
                        language = EXCLUDED.language,
                        dialect = EXCLUDED.dialect,
                        source_type = EXCLUDED.source_type,
                        user_id = EXCLUDED.user_id,
                        session_id = EXCLUDED.session_id,
                        original_filename = EXCLUDED.original_filename,
                        local_path = EXCLUDED.local_path,
                        storage_key = EXCLUDED.storage_key,
                        storage_url = EXCLUDED.storage_url,
                        cloudinary_public_id = EXCLUDED.cloudinary_public_id,
                        cloudinary_url = EXCLUDED.cloudinary_url,
                        created_at = EXCLUDED.created_at,
                        updated_at = EXCLUDED.updated_at
                    """,
                    row,
                )
    finally:
        conn.close()


def delete_raw_upload(upload_uid: str):
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM raw_uploads WHERE upload_uid = %s", (upload_uid,))
    finally:
        conn.close()


def delete_raw_uploads_by_class(class_uid: str):
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM raw_uploads WHERE class_uid = %s", (class_uid,))
    finally:
        conn.close()
