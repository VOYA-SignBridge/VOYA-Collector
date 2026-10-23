"""Celery task boundary for dataset video feature extraction."""

from __future__ import annotations

import logging
import os
import tempfile

from app.infrastructure.celery.app import celery_app
from app.processing.pipeline import process_video_job

logger = logging.getLogger(__name__)


def _download_from_storage(storage_url: str) -> str:
    """Download a remote Drive video to a temporary local path."""
    if not storage_url.startswith(("https://drive.google.com", "gdrive://")):
        return storage_url

    from app.storage.gdrive_client import download_from_gdrive

    file_descriptor, local_path = tempfile.mkstemp(suffix=".mp4")
    os.close(file_descriptor)
    return download_from_gdrive(storage_url, local_path)


@celery_app.task(bind=True, name="app.tasks.enqueue_process_video")
def enqueue_process_video(
    self,
    video_path: str,
    user: str,
    label: str,
    session_id: str,
    dialect: str = "common",
    language: str = "vn",
    user_id: str = "",
    class_uid: str = "",
    visibility: str = "private",
):
    """Process one local or Drive-hosted video and clean temporary files."""
    local_video_path = video_path
    temporary_files: list[str] = []
    try:
        if video_path.startswith(("https://drive.google.com", "gdrive://")):
            local_video_path = _download_from_storage(video_path)
            if local_video_path and local_video_path != video_path:
                temporary_files.append(local_video_path)

        result = process_video_job(
            video_path=local_video_path,
            user=user,
            user_id=user_id,
            label=label,
            session_id=session_id,
            dialect=dialect,
            language=language,
            class_uid=class_uid,
            visibility=visibility,
        )
        return {"status": "done", "result": result}
    except Exception:
        logger.exception(
            "[CELERY][FAIL] video_path=%s label=%s user=%s session_id=%s",
            video_path,
            label,
            user,
            session_id,
        )
        raise
    finally:
        for path in temporary_files:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    logger.info("[CLEANUP] Removed temp file: %s", path)
            except Exception:
                logger.warning("[CLEANUP] Could not remove temp file: %s", path)
