import logging
import os
import tempfile
from app.worker import celery_app
from app.processing.pipeline import process_video_job
from app.storage.artifact_store import download_artifact_to_tempfile

def _download_from_storage(source_uri: str) -> str:
    """Download remote storage objects to a temp local path and return it."""
    if not source_uri:
        return source_uri

    if not source_uri.startswith(("s3://", "http://", "https://")):
        return source_uri

    try:
        temp_path = download_artifact_to_tempfile(source_uri)
        logging.getLogger(__name__).info("[STORAGE_DOWNLOAD] Downloaded from %s to %s", source_uri, temp_path)
        return temp_path
    except Exception as e:
        logging.getLogger(__name__).error("[STORAGE_DOWNLOAD] Failed: %s", e)
        raise

@celery_app.task(bind=True)
def enqueue_process_video(self, video_path: str, user: str, label: str, session_id: str, dialect: str = "common", language: str = "vn"):
    # This wrapper calls processing.pipeline (synchronous heavy processing)
    # Use try/except to capture failure and push status
    
    # Handle MinIO URLs by downloading to temp file
    local_video_path = video_path
    temp_files_to_clean = []
    
    try:
        if video_path.startswith(("s3://", "http://", "https://")):
            local_video_path = _download_from_storage(video_path)
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
