import logging
from io import BytesIO
from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)


def _get_minio_client():
    if not settings.use_minio:
        logger.warning("USE_MINIO not enabled")
        return None

    if not settings.minio_endpoint:
        logger.error("MINIO_ENDPOINT not configured")
        return None

    access_key = settings.minio_access_key
    secret_key = settings.minio_secret_key

    if not access_key or not secret_key:
        logger.error("MINIO_ACCESS_KEY or MINIO_SECRET_KEY not configured")
        return None

    try:
        client = Minio(
            settings.minio_endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=False,
        )
        logger.info("[MINIO] Client initialized for endpoint=%s bucket=%s", 
                    settings.minio_endpoint, settings.minio_bucket)
        return client
    except Exception as e:
        logger.error("[MINIO] Failed to initialize client: %s", e)
        return None


def _ensure_bucket_exists(client):
    bucket = settings.minio_bucket
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info("[MINIO] Created bucket: %s", bucket)
        return True
    except S3Error as e:
        logger.error("[MINIO] Failed to ensure bucket exists: %s", e)
        return False


def _upload_to_minio(client, file_data, key: str, content_type: str = "application/octet-stream") -> str | None:
    if not client:
        return None

    if not _ensure_bucket_exists(client):
        return None

    bucket = settings.minio_bucket

    try:
        if isinstance(file_data, (str, BytesIO)):
            if isinstance(file_data, str):
                import os
                file_path = file_data
                if not os.path.exists(file_path):
                    logger.error("[MINIO] File not found: %s", file_path)
                    return None
                with open(file_path, "rb") as f:
                    file_data = BytesIO(f.read())
            
            if isinstance(file_data, BytesIO):
                file_data.seek(0, 2)
                file_size = file_data.tell()
                file_data.seek(0)
            else:
                file_size = 0

            client.put_object(
                bucket,
                key,
                file_data,
                length=file_size,
                content_type=content_type,
            )
        else:
            logger.error("[MINIO] Unsupported file_data type: %s", type(file_data))
            return None

        minio_url = f"s3://{bucket}/{key}"
        logger.info("[MINIO] Uploaded to: %s", minio_url)
        return minio_url
    except S3Error as e:
        logger.error("[MINIO] Upload failed for key=%s: %s", key, e)
        return None
    except Exception as e:
        logger.error("[MINIO] Upload error for key=%s: %s", key, e)
        return None


def upload_file(file_data, key: str) -> str | None:
    if not settings.use_minio:
        logger.info("[MINIO] USE_MINIO not enabled, skipping upload")
        return None
    
    client = _get_minio_client()
    if client:
        return _upload_to_minio(client, file_data, key)
    return None
