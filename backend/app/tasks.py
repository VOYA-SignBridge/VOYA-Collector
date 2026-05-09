import logging
import os

from app.worker import celery_app
from app.processing.pipeline import process_video_job
from app.storage.artifact_store import download_artifact_to_tempfile


def _is_remote_storage_uri(source_uri: str) -> bool:
    return bool(source_uri) and source_uri.startswith(("s3://", "http://", "https://"))


def _download_from_storage(source_uri: str) -> str:
    """Download remote storage objects to a temp local path and return it."""
    if not source_uri:
        raise ValueError("source_uri is empty")

    if not _is_remote_storage_uri(source_uri):
        return source_uri

    temp_path = download_artifact_to_tempfile(source_uri)
    if not temp_path or not os.path.exists(temp_path):
        raise FileNotFoundError(f"Downloaded temp file not found for {source_uri}")

    logging.getLogger(__name__).info(
        "[STORAGE_DOWNLOAD] Downloaded from %s to %s",
        source_uri,
        temp_path,
    )
    return temp_path


@celery_app.task(bind=True)
def enqueue_process_video(
    self,
    video_path: str,
    user: str,
    user_id: str,
    label: str,
    session_id: str,
    dialect: str = "common",
    language: str = "vn",
):
    if not video_path:
        raise ValueError("video_path is empty")

    local_video_path = video_path
    temp_files_to_clean = []

    try:
        if _is_remote_storage_uri(video_path):
            local_video_path = _download_from_storage(video_path)
            if local_video_path != video_path:
                temp_files_to_clean.append(local_video_path)

        result = process_video_job(
            local_video_path,
            user,
            user_id=user_id,
            label=label,
            session_id=session_id,
            dialect=dialect,
            language=language,
        )
        return {"status": "done", "result": result}

    except Exception:
        logging.getLogger(__name__).exception(
            "[CELERY][FAIL] video_path=%s label=%s user=%s user_id=%s session_id=%s",
            video_path,
            label,
            user,
            user_id,
            session_id,
        )
        raise

    finally:
        for file_path in temp_files_to_clean:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    logging.getLogger(__name__).info(
                        "[CLEANUP] Removed temp file: %s",
                        file_path,
                    )
            except Exception:
                logging.getLogger(__name__).warning(
                    "[CLEANUP] Failed to remove temp file: %s",
                    file_path,
                )