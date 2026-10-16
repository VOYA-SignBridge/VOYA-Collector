import os
import logging
from app.worker import celery_app
from app.processing.pipeline import process_video_job


def _download_from_storage(storage_url: str) -> str:
    """Download file from Google Drive to temp location."""
    if storage_url.startswith(("https://drive.google.com", "gdrive://")):
        import tempfile
        from app.storage.gdrive_client import download_from_gdrive

        fd, local_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        return download_from_gdrive(storage_url, local_path)
    return storage_url


@celery_app.task(bind=True)
def enqueue_process_video(
    self,
    video_path: str,
    user: str,
    label: str,
    session_id: str,
    dialect: str = "common",
    language: str = "vn",
    user_id: str = "",
):
    """Process video from Google Drive or local filesystem."""
    local_video_path = video_path
    temp_files_to_clean = []
    
    try:
        # Handle Google Drive URLs before passing the video to OpenCV.
        if video_path.startswith(("https://drive.google.com", "gdrive://")):
            local_video_path = _download_from_storage(video_path)
            if local_video_path and local_video_path != video_path:
                temp_files_to_clean.append(local_video_path)
        
        result = process_video_job(
            video_path=local_video_path,
            user=user,
            user_id=user_id,
            label=label,
            session_id=session_id,
            dialect=dialect,
            language=language,
        )
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
