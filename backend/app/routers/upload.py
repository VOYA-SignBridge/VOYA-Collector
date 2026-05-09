import os
import uuid
import time
import logging
import numpy as np

from typing import Optional, Dict, Any
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, Body, HTTPException, Depends

from app.processing import storage_utils as su  # legacy for timestamp helper
from app.dataset_manager import get_or_register_class, normalize_dialect
from app.dataset_samples import save_sequence_npz
from app.raw_uploads import append_raw_upload_row, now_str as raw_now_str
from app.tasks import enqueue_process_video
from app.config import settings
from app.storage.artifact_store import store_raw_video
from app.processing.utils import canonicalize_vector_126
from app.logging_utils import get_logger as get_structured_logger
from app.storage.metadata_db import upsert_raw_upload
from app.api_validation import (
    validate_label,
    validate_language,
    validate_dialect,
    save_upload_with_limit,
)

slog = get_structured_logger("upload.operations")
from app.auth import get_current_user_optional


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _flatten_nested_landmarks(row):
    """Recursively flatten nested lists of landmarks into a 1D array."""
    if row is None:
        return np.array([], dtype="float32")
    if isinstance(row, np.ndarray):
        return row.flatten()
    if isinstance(row, (list, tuple)):
        result = []
        for item in row:
            flat = _flatten_nested_landmarks(item)
            result.extend(flat if isinstance(flat, (list, tuple)) else [flat])
        return np.array(result, dtype="float32")
    # Scalar value
    try:
        return np.array([float(row)], dtype="float32")
    except (TypeError, ValueError):
        return np.array([], dtype="float32")


router = APIRouter(prefix="/upload", tags=["upload"])


@router.options("/camera")
async def options_camera():
    """Handle CORS preflight for /upload/camera"""
    return {"success": True}


@router.post("/video")
async def upload_video(
    file: UploadFile = File(...),
    user: str = Form(""),
    label: str = Form(...),
    language: str = Form("vn"),
    dialect: str = Form("common"),
    session_id: str = Form(None),
    debug: bool = Form(False),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
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

    # Read video bytes from memory
    video_data = file.file.read()
    max_mb = int(os.getenv("MAX_UPLOAD_MB", "1024"))
    max_bytes = max_mb * 1024 * 1024 if max_mb > 0 else 0
    written = len(video_data)
    log.info("[UPLOAD][video] bytes_read=%s max_bytes=%s", written, max_bytes)

    # Store raw video using the hybrid policy.
    include_debug = bool(debug or getattr(settings, "cloudinary_debug_responses", False))

    storage_info = store_raw_video(
        video_data,
        class_meta,
        session_id=session_id,
        original_filename=getattr(file, "filename", "upload.mp4") or "upload.mp4",
        include_debug=include_debug,
    )

    try:
        raw_row = {
            "upload_uid": storage_info.get("upload_uid") or uuid.uuid4().hex[:8],
            "class_uid": class_meta.class_uid,
            "slug": class_meta.slug,
            "label_original": class_meta.label_original,
            "language": class_meta.language,
            "dialect": class_meta.dialect,
            "source_type": "video",
            "user_id": user,
            "session_id": session_id,
            "original_filename": getattr(file, "filename", "upload.mp4") or "upload.mp4",
            "local_path": storage_info.get("local_path") or storage_info.get("storage_url") or "",
            "storage_key": storage_info.get("storage_key") or "",
            "storage_url": storage_info.get("storage_url") or storage_info.get("local_path") or "",
            "cloudinary_public_id": storage_info.get("cloudinary_public_id") or "",
            "cloudinary_url": storage_info.get("cloudinary_url") or "",
            "created_at": raw_now_str(),
            "updated_at": raw_now_str(),
        }
        append_raw_upload_row(raw_row)
        upsert_raw_upload(raw_row)
    except Exception as e:
        log.warning("[UPLOAD][video] raw upload index mirror failed: %s", e)

    file_path_for_processing = storage_info.get("local_path") or storage_info.get("storage_url") or ""
    if not file_path_for_processing:
        return {"success": False, "message": "Upload failed"}

    try:
        job = enqueue_process_video.delay(
            video_path=file_path_for_processing,
            user=user,
            user_id=current_user["id"] if current_user else "",
            label=label,
            session_id=session_id,
            dialect=dialect,
            language=language,
        )
        response_message = "Upload accepted and queued for processing"
        
        # Log upload success with structured logger
        slog.log_upload(
            endpoint="video",
            success=True,
            session_id=session_id,
            job_id=job.id,
            duration_ms=time.time() - start,
            file_size_bytes=len(video_data),
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
            "message": response_message,
        }
    except Exception as e:
        # Log upload failure with structured logger
        slog.log_upload(
            endpoint="video",
            success=False,
            session_id=session_id,
            duration_ms=time.time() - start,
            file_size_bytes=len(video_data),
            error_message=str(e),
        )
        log.error("[UPLOAD][video][ERROR] queue failed: %s", e)
        return {"success": False, "message": f"queue failed: {e}"}


@router.post("/camera")
async def upload_camera(payload: dict = Body(...),
                        current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
                        ):
    """
    Accept frames (array of arrays) and metadata, save as npz via storage_utils.save_sample
    Payload example: { user: str, label: str, session_id: str, dialect: str, frames: [{timestamp, landmarks}, ...] }
    """
    start = time.time()
    user = payload.get("user", "")
    user_id = current_user["id"] if current_user else ""
    label = validate_label(payload.get("label"))
    dialect = validate_dialect(normalize_dialect(payload.get("dialect", "common")))
    language = validate_language(payload.get("language", "vn"))
    session_id = payload.get("session_id", None) or uuid.uuid4().hex
    frames = payload.get("frames")

    if not frames:
        return {"success": False, "message": "Missing label or frames"}

    # Basic payload size guard (prevents accidental huge posts)
    try:
        max_frames = int(os.getenv("MAX_CAMERA_FRAMES", "600"))
        if max_frames > 0 and isinstance(frames, list) and len(frames) > max_frames:
            return {"success": False, "message": f"Too many frames (max {max_frames})"}
    except Exception:
        pass

    # Ensure label exists
    class_meta = get_or_register_class(
        label_original=label, language=language, dialect=dialect or ""
    )

    log = logging.getLogger("upload.camera")

    # Convert frames (list of {timestamp, landmarks }) into numpy array
    # We expect landmarks arrays per frame; stack into (T, N) array
    try:
        # helper: convert a MediaPipe-like dict into a flat numeric vector (hands only)
        def flatten_landmarks(ld):
            # If already a list/array of numbers, return as-is
            if ld is None:
                return None
            if isinstance(ld, (list, tuple, np.ndarray)):
                return np.asarray(ld)

            # If dict (MediaPipe style) with keys for hands only
            if isinstance(ld, dict):
                # IMPORTANT: Always output fixed layout (left 63 + right 63 = 126).
                # If a hand is missing or has fewer than 21 landmarks, pad with zeros
                # to avoid shifting the other hand into the wrong block.
                parts = []

                def _hand_points_to_flat(elems):
                    elems = elems if isinstance(elems, (list, tuple)) else []
                    out = []
                    # MediaPipe Hands has 21 landmarks; preserve ordering by index.
                    for j in range(21):
                        p = elems[j] if j < len(elems) else None
                        if not isinstance(p, dict):
                            out.extend([0.0, 0.0, 0.0])
                            continue
                        x = p.get("x")
                        y = p.get("y")
                        z = p.get("z")
                        out.extend(
                            [
                                float(x) if x is not None else 0.0,
                                float(y) if y is not None else 0.0,
                                float(z) if z is not None else 0.0,
                            ]
                        )
                    return out

                # Only process hands (left_hand, right_hand) - no pose, no face
                parts.extend(_hand_points_to_flat(ld.get("left_hand", [])))
                parts.extend(_hand_points_to_flat(ld.get("right_hand", [])))
                return np.array(parts, dtype="float32")

            # Unknown format -> attempt to coerce
            return np.asarray(ld)

        landmarks_seq = []
        for f in frames:
            raw = f.get("landmarks")
            flat = flatten_landmarks(raw)
            if flat is None:
                raise ValueError("frame missing landmarks")
            landmarks_seq.append(flat)

        # Ensure all frames have same vector length by padding shorter ones
        maxlen = max([a.size for a in landmarks_seq])
        # Build a numeric 2D array explicitly to avoid object-dtype pitfalls
        T = len(landmarks_seq)
        seq = np.zeros((T, maxlen), dtype="float32")
        for i, a in enumerate(landmarks_seq):
            if a.size > maxlen:
                # truncate if unexpectedly longer
                seq[i, :] = a[:maxlen].astype("float32")
            else:
                seq[i, : a.size] = a.astype("float32")

        if getattr(settings, "debug_logging", False):
            log.debug("[LANDMARKS] first_type=%s", type(frames[0].get("landmarks")))
            log.debug(
                "[LANDMARKS] built_seq shape=%s dtype=%s",
                getattr(seq, "shape", None),
                getattr(seq, "dtype", None),
            )
        # Ensure sequence is numeric float32 (some inputs may produce object-dtype rows)
        try:
            seq = seq.astype("float32")
        except Exception as e:
            log.warning(
                "[LANDMARKS] seq.astype(float32) failed: %s; attempting per-row conversion",
                e,
            )
            new = np.zeros((T, maxlen), dtype="float32")
            for i in range(T):
                row = landmarks_seq[i]
                try:
                    arr = np.asarray(row, dtype=np.float32).flatten()
                except Exception:
                    arr = _flatten_nested_landmarks(row)

                if arr.size > maxlen:
                    new[i, :] = arr[:maxlen]
                else:
                    new[i, : arr.size] = arr
            seq = new
    except (TypeError, ValueError) as e:
        log.error("[LANDMARKS][ERROR] Failed to parse landmarks: %s", e)
        return {"success": False, "message": f"Invalid landmarks format: {e}"}
    except MemoryError:
        log.error("[LANDMARKS][ERROR] Payload too large")
        return {"success": False, "message": "Payload exceeds memory limits"}

    # Apply augmentation to create multiple samples
    from app.processing.augmenter import generate_augmented_sequences

    # Ensure sequence has proper shape (pad/truncate to settings.seq_len)
    T, D = seq.shape
    target_T = int(getattr(settings, "seq_len", 60))
    if T < target_T:
        pad = np.zeros((target_T - T, D), dtype=np.float32)
        seq_padded = np.vstack([seq, pad])
    else:
        seq_padded = seq[:target_T]

    # Ensure feature dimension matches spec (hands-only = 126)
    feat = int(getattr(settings, "feature_dim", 126))
    tT, tD = seq_padded.shape
    if tD < feat:
        col_pad = np.zeros((tT, feat - tD), dtype=np.float32)
        seq_padded = np.hstack([seq_padded.astype(np.float32), col_pad])
    elif tD > feat:
        seq_padded = seq_padded[:, :feat].astype(np.float32)
    else:
        seq_padded = seq_padded.astype(np.float32)

    # Sequence-level canonicalization (deterministic across frames)
    if seq_padded.shape[1] == 126:
        try:
            from app.processing.utils import canonicalize_sequence_126

            seq_padded = canonicalize_sequence_126(
                seq_padded,
                normalized=bool(getattr(settings, "normalize_keypoints", False)),
                mirror_invariant=bool(getattr(settings, "canonicalize_mirror", True)),
            )
        except Exception:
            # fallback to per-frame canonicalize in unlikely failure
            for t in range(seq_padded.shape[0]):
                seq_padded[t, :] = canonicalize_vector_126(seq_padded[t, :])

    # Generate augmented sequences (default count controlled by AUG_PER_SEQ)
    live_aug_enabled = bool(getattr(settings, "enable_live_aug", True))
    aug_n = int(getattr(settings, "augment_per_seq", 8)) if live_aug_enabled else 1
    log.info(
        "[LIVE_CFG] seq_len=%s feature_dim=%s live_aug=%s aug_n=%s",
        target_T,
        feat,
        live_aug_enabled,
        aug_n,
    )
    log.info(
        "[LIVE_SEQ] shape=%s dtype=%s",
        getattr(seq_padded, "shape", None),
        getattr(seq_padded, "dtype", None),
    )
    if live_aug_enabled:
        augmented_seq_list = generate_augmented_sequences(seq_padded, config={"n": aug_n})
    else:
        augmented_seq_list = [seq_padded]

    log.info("[LIVE_AUG] generated=%s", len(augmented_seq_list))

    saved_paths = []
    for i, aseq in enumerate(augmented_seq_list):
        # Safety checks before saving
        if (
            not isinstance(aseq, np.ndarray)
            or aseq.dtype.kind not in ("f", "i")
            or aseq.ndim != 2
        ):
            log.error(
                "[AUG][ERROR] idx=%s not numeric 2D array: type=%s dtype=%s ndim=%s",
                i,
                type(aseq),
                getattr(aseq, "dtype", None),
                getattr(aseq, "ndim", None),
            )
            continue

        meta = {
            "user": user,
            "user_id": user_id,
            "session_id": session_id,
            "fps_original": None,
            "fps_processed": None,
            "completeness": None,
            "created_at": su.now_str(),
        }
        path = save_sequence_npz(
            class_meta, aseq, meta=meta, augment_id=i, source_type="camera"
        )
        saved_paths.append(path)

    # Log camera capture completion (all details backend-only)
    elapsed_ms = (time.time() - start) * 1000
    log.info(
        "[UPLOAD][camera] completed session=%s aug_count=%s elapsed=%.3fs",
        session_id,
        len(saved_paths),
        elapsed_ms / 1000,
    )
    # Log saved paths as backend-only debug info
    for path in saved_paths:
        log.debug("[UPLOAD][camera] saved_path=%s", path)
    
    # Log camera upload success with structured logger
    response_message = "Camera capture processed and queued for training"
    slog.log_upload(
        endpoint="camera",
        success=True,
        session_id=session_id,
        job_id=session_id,  # Use session_id as job identifier for camera
        duration_ms=elapsed_ms,
    )
    
    # Return standardized response (minimal, frontend-safe)
    return {
        "success": True,
        "id": session_id,
        "session_id": session_id,
        "message": response_message,
    }
