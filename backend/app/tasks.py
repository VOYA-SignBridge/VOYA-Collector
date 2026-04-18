from app.worker import celery_app
from app.processing.pipeline import process_video_job
import logging

@celery_app.task(bind=True)
def enqueue_process_video(self, video_path: str, user: str, label: str, session_id: str, dialect: str = "common", language: str = "vn"):
    # This wrapper calls processing.pipeline (synchronous heavy processing)
    # Use try/except to capture failure and push status
    try:
        result = process_video_job(video_path, user, label, session_id, dialect=dialect, language=language)
        return {"status": "done", "result": result}
    except Exception as e:
        logging.getLogger(__name__).exception("[CELERY][FAIL] video_path=%s label=%s user=%s session_id=%s", video_path, label, user, session_id)
        # Raise so Celery marks the job as FAILURE (visible via /jobs/{job_id})
        raise
