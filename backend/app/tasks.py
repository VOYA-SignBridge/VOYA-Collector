import os
import logging
from app.worker import celery_app
from app.processing.pipeline import process_video_job


def _download_from_storage(storage_url: str) -> str:
    """Download file from object storage (MinIO or R2) to temp location."""
    from app.storage.r2_client import download_from_r2
    return download_from_r2(storage_url)


@celery_app.task(bind=True)
def enqueue_process_video(self, video_path: str, user: str, label: str, session_id: str, dialect: str = "common", language: str = "vn"):
    """Process video from object storage (MinIO or R2)."""
    local_video_path = video_path
    temp_files_to_clean = []
    
    try:
        # Handle object storage URLs before passing the video to OpenCV.
        if video_path.startswith(("r2://", "s3://")):
            local_video_path = _download_from_storage(video_path)
            if local_video_path and local_video_path != video_path:
                temp_files_to_clean.append(local_video_path)
        
        result = process_video_job(local_video_path, user, label, session_id, dialect=dialect, language=language)
        return {"status": "done", "result": result}
    except Exception as e:
        logging.getLogger(__name__).exception("[CELERY][FAIL] video_path=%s label=%s user=%s session_id=%s", video_path, label, user, session_id)
        raise
    finally:
        for f in temp_files_to_clean:
            try:
                if os.path.exists(f):
                    os.remove(f)
                    logging.getLogger(__name__).info("[CLEANUP] Removed temp file: %s", f)
            except Exception:
                pass
