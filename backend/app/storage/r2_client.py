import logging
from io import BytesIO
from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)


def _get_r2_client():
    """Get Cloudflare R2 client (S3-compatible)."""
    if not settings.use_object_storage:
        logger.warning("Object storage not enabled")
        return None

    # Use R2 config
    config = settings.get_object_storage_config()
    
    if config["provider"] != "r2":
        logger.info("Not using R2 provider, falling back to other storage")
        return None

    if not config["endpoint"]:
        logger.error("R2_ENDPOINT not configured")
        return None

    if not config["access_key"] or not config["secret_key"]:
        logger.error("R2 access key or secret key not configured")
        return None

    if not config["bucket"]:
        logger.error("R2 bucket not configured")
        return None

    try:
        # Remove https:// prefix if present for endpoint
        endpoint = config["endpoint"].replace("https://", "").replace("http://", "")
        
        client = Minio(
            endpoint,
            access_key=config["access_key"],
            secret_key=config["secret_key"],
            secure=True,  # R2 always uses HTTPS
        )
        logger.info("[R2] Client initialized for endpoint=%s bucket=%s", 
                    config["endpoint"], config["bucket"])
        return client
    except Exception as e:
        logger.error("[R2] Failed to initialize client: %s", e)
        return None


def _ensure_bucket_exists(client):
    """Ensure bucket exists in R2."""
    config = settings.get_object_storage_config()
    bucket = config["bucket"]
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info("[R2] Created bucket: %s", bucket)
        return True
    except S3Error as e:
        logger.error("[R2] Failed to ensure bucket exists: %s", e)
        return False


def upload_to_r2(file_data, key: str, content_type: str = "application/octet-stream") -> str | None:
    """Upload file to Cloudflare R2."""
    if not settings.use_object_storage:
        logger.info("[R2] Object storage not enabled, skipping upload")
        return None
    
    client = _get_r2_client()
    if not client:
        return None

    config = settings.get_object_storage_config()
    bucket = config["bucket"]

    if not _ensure_bucket_exists(client):
        return None

    try:
        # Prepare file data
        if isinstance(file_data, str):
            import os
            file_path = file_data
            if not os.path.exists(file_path):
                logger.error("[R2] File not found: %s", file_path)
                return None
            with open(file_path, "rb") as f:
                file_data = BytesIO(f.read())
        
        if isinstance(file_data, BytesIO):
            file_data.seek(0, 2)
            file_size = file_data.tell()
            file_data.seek(0)
        elif isinstance(file_data, bytes):
            file_size = len(file_data)
            file_data = BytesIO(file_data)
        else:
            logger.error("[R2] Unsupported file_data type: %s", type(file_data))
            return None

        client.put_object(
            bucket,
            key,
            file_data,
            length=file_size,
            content_type=content_type,
        )

        # Generate appropriate URL
        if config.get("public_url"):
            r2_url = f"{config['public_url'].rstrip('/')}/{key}"
        else:
            r2_url = f"r2://{bucket}/{key}"
        
        logger.info("[R2] Uploaded to: %s", r2_url)
        return r2_url
    except S3Error as e:
        logger.error("[R2] Upload failed for key=%s: %s", key, e)
        return None
    except Exception as e:
        logger.error("[R2] Upload error for key=%s: %s", key, e)
        return None


def download_from_r2(r2_url: str) -> str | None:
    """Download file from R2 to temp location and return local path."""
    if not r2_url.startswith(("r2://", "s3://")):
        return r2_url  # Not an R2 URL, return as-is
    
    client = _get_r2_client()
    if not client:
        raise Exception("Cannot get R2 client")
    
    config = settings.get_object_storage_config()
    bucket = config["bucket"]
    
    # Parse r2://bucket/key or s3://bucket/key.
    parts = r2_url.replace("r2://", "").replace("s3://", "").split("/")
    if len(parts) >= 2:
        bucket = parts[0]
        key = "/".join(parts[1:])
    else:
        key = parts[0]
    
    import tempfile
    import os
    _, ext = os.path.splitext(key)
    fd, temp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    
    try:
        client.fget_object(bucket, key, temp_path)
        logger.info("[R2] Downloaded from %s to %s", r2_url, temp_path)
        return temp_path
    except Exception as e:
        logger.error("[R2] Download failed: %s", e)
        raise
