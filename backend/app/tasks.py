import logging
import os
import tempfile
from app.worker import celery_app
from app.processing.pipeline import process_video_job

def _download_from_minio(minio_url: str) -> str:
    """Download file from MinIO to temp location and return local path."""
    from app.config import settings
    from app.storage.minio_client import _get_minio_client
    
    if not minio_url.startswith("s3://"):
        return minio_url  # Not a MinIO URL, return as-is
    
    try:
        minio_client = _get_minio_client()
        if not minio_client:
            raise Exception("Cannot get MinIO client")
        
        # Parse s3://bucket/key
        parts = minio_url.replace("s3://", "").split("/")
        bucket = parts[0]
        key = "/".join(parts[1:])
        
        # Create temp file
        _, ext = os.path.splitext(key)
        fd, temp_path = tempfile.mkstemp(suffix=ext)
        os.close(fd)
        
        # Download
        minio_client.fget_object(bucket, key, temp_path)
        logging.getLogger(__name__).info("[MINIO_DOWNLOAD] Downloaded from %s to %s", minio_url, temp_path)
        
        return temp_path
    except Exception as e:
        logging.getLogger(__name__).error("[MINIO_DOWNLOAD] Failed: %s", e)
        raise

@celery_app.task(bind=True)
def enqueue_process_video(self, video_path: str, user: str, label: str, session_id: str, dialect: str = "common", language: str = "vn"):
    # This wrapper calls processing.pipeline (synchronous heavy processing)
    # Use try/except to capture failure and push status
    
    # Handle MinIO URLs by downloading to temp file
    local_video_path = video_path
    temp_files_to_clean = []
    
    try:
        if video_path.startswith("s3://"):
            local_video_path = _download_from_minio(video_path)
            temp_files_to_clean.append(local_video_path)
        
        result = process_video_job(local_video_path, user, label, session_id, dialect=dialect, language=language)
        return {"status": "done", "result": result}
    except Exception as e:
        logging.getLogger(__name__).exception("[CELERY][FAIL] video_path=%s label=%s user=%s session_id=%s", video_path, label, user, session_id)
        # Raise so Celery marks the job as FAILURE (visible via /jobs/{job_id})
        raise
    finally:
        # Clean up temp files
        for f in temp_files_to_clean:
            try:
                if os.path.exists(f):
                    os.remove(f)
                    logging.getLogger(__name__).info("[CLEANUP] Removed temp file: %s", f)
            except Exception:
                pass
