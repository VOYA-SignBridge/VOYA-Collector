from fastapi import APIRouter, UploadFile, File, Form
import os
import uuid
import time
import logging
from pathlib import Path
import numpy as np

from app.processing import storage_utils as su  # legacy for timestamp helper
from app.dataset_manager import get_or_register_class, normalize_dialect
from app.dataset_samples import save_sequence_npz
from app.tasks import enqueue_process_video
from app.config import settings
from app.processing.utils import canonicalize_vector_126
from app.api_validation import (
    validate_label,
    validate_language,
    validate_dialect,
    save_upload_with_limit,
)

router = APIRouter(prefix="/upload", tags=["upload"])


# Align raw video storage with DATASET_ROOT so it matches features path
UPLOAD_DIR = str(settings.dataset_root / "raw_videos")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/video")
async def upload_video(
    file: UploadFile = File(...),
    user: str = Form(""),
    label: str = Form(...),
    language: str = Form("vn"),
    dialect: str = Form("common"),
    session_id: str = Form(None),
):
    start = time.time()
    log = logging.getLogger("upload.video")
    if not session_id:
        session_id = uuid.uuid4().hex

    # Validate & normalize inputs
    label = validate_label(label)
    language = validate_language(language)
    dialect = validate_dialect(normalize_dialect(dialect))

    log.info(
        "[UPLOAD][video] user=%s label=%s lang=%s dialect=%s filename=%s session=%s",
        user,
        label,
        language,
        dialect,
        getattr(file, "filename", ""),
        session_id,
    )
    # Log pipeline-relevant settings for traceability
    try:
        seq_len = int(getattr(settings, "seq_len", 60))
        feat_dim = int(getattr(settings, "feature_dim", 126))
        aug_live = int(getattr(settings, "augment_per_seq", 8))
        aug_video = int(getattr(settings, "video_augment_per_seq", 0) or 0)
        aug_n = aug_video if aug_video > 0 else aug_live
        log.info(
            "[PIPELINE_CFG] seq_len=%s feature_dim=%s stride=%s aug_n=%s (AUG_PER_SEQ=%s VIDEO_AUG_PER_SEQ=%s) VIDEO_COMPLETENESS=%s",
            seq_len,
            feat_dim,
            int(getattr(settings, "stride", 2)),
            aug_n,
            aug_live,
            aug_video,
            float(getattr(settings, "video_completeness_threshold", 0.8)),
        )
    except Exception as e:
        log.warning("[PIPELINE_CFG] Failed to log config: %s", e)

    # Register / fetch class in new hierarchy
    class_meta = get_or_register_class(
        label_original=label, language=language, dialect=dialect or ""
    )

    save_name = f"{label}_{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, save_name)
    max_mb = int(os.getenv("MAX_UPLOAD_MB", "1024"))
    max_bytes = max_mb * 1024 * 1024 if max_mb > 0 else 0
    written, _ = save_upload_with_limit(file.file, Path(file_path), max_bytes=max_bytes)
    log.info("[UPLOAD][video] bytes_written=%s max_bytes=%s", written, max_bytes)
    # Log the resolved save path and dataset root for debugging
    log.info(
        "[UPLOAD][video] saved path=%s dataset_root=%s",
        file_path,
        settings.dataset_root,
    )

    # Upload to MinIO if configured
    if settings.use_minio:
        try:
            from app.storage.minio_client import _get_minio_client, _upload_to_minio

            minio_client = _get_minio_client()
            if minio_client:
                minio_key = f"raw_videos/{save_name}"
                minio_url = _upload_to_minio(minio_client, file_path, minio_key)
                if minio_url:
                    log.info("[UPLOAD][video] uploaded to MinIO: %s", minio_url)
                else:
                    log.warning("[UPLOAD][video] MinIO upload failed: no URL returned")
        except Exception as e:
            log.warning("[UPLOAD][video] MinIO upload failed: %s", e)

    # Gửi task tới Celery
    try:
        job = enqueue_process_video.delay(
            video_path=file_path,
            user=user,
            label=label,
            session_id=session_id,
            dialect=dialect,
            language=language,
        )
        log.info(
            "[UPLOAD][video] queued job=%s elapsed=%.3fs",
            getattr(job, "id", "unknown"),
            time.time() - start,
        )
        return {
            "success": True,
            "id": job.id,
            "session_id": session_id,
            "message": "queued",
        }
    except Exception as e:
        log.error("[UPLOAD][video][ERROR] queue failed: %s", e)
        return {"success": False, "message": f"queue failed: {e}"}

