import os
import uuid
import time
import logging
import numpy as np

from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, Body

from app.processing import storage_utils as su
from app.dataset_manager import get_or_register_class, normalize_dialect
from app.processing.utils import normalize_hands_vector_126
from app.processing.utils import normalize_sequence
from app.dataset_samples import save_sequence_npz
from app.tasks import enqueue_process_video
from app.config import settings
from app.api_validation import (
    validate_label,
    validate_language,
    validate_dialect,
    save_upload_with_limit,
)

router = APIRouter(prefix="/upload", tags=["upload"])

@router.options("/camera")
async def options_camera():
    return {"success": True}

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

    log.info("[UPLOAD][video] user=%s label=%s lang=%s dialect=%s filename=%s session=%s", user, label, language, dialect, getattr(file, 'filename', ''), session_id)
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
    except Exception:
        pass

    # Register / fetch class in new hierarchy
    class_meta = get_or_register_class(label_original=label, language=language, dialect=dialect or "")

    save_name = f"{user}_{label}_{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, save_name)
    max_mb = int(os.getenv("MAX_UPLOAD_MB", "1024"))
    max_bytes = max_mb * 1024 * 1024 if max_mb > 0 else 0
    written, _ = save_upload_with_limit(file.file, Path(file_path), max_bytes=max_bytes)
    log.info("[UPLOAD][video] bytes_written=%s max_bytes=%s", written, max_bytes)
    # Log the resolved save path and dataset root for debugging
    log.info("[UPLOAD][video] saved path=%s dataset_root=%s", file_path, settings.dataset_root)

    # Gửi task tới Celery
    try:
        job = enqueue_process_video.delay(video_path=file_path, user=user, label=label, session_id=session_id, dialect=dialect, language=language)
        log.info("[UPLOAD][video] queued job=%s elapsed=%.3fs", getattr(job, 'id', 'unknown'), time.time() - start)
        return {"success": True, "id": job.id, "session_id": session_id, "message": "queued"}
    except Exception as e:
        log.error("[UPLOAD][video][ERROR] queue failed: %s", e)
        return {"success": False, "message": f"queue failed: {e}"}
    


@router.post("/camera")
async def upload_camera(payload: dict = Body(...)):
    """
    Accept frames (array of arrays) and metadata, save as npz via storage_utils.save_sample
    Payload example: { user: str, label: str, session_id: str, dialect: str, frames: [{timestamp, landmarks}, ...] }
    """
    user = payload.get("user", "")
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
    class_meta = get_or_register_class(label_original=label, language=language, dialect=dialect or "")

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
                return np.asarray( ld, dtype=np.float32 ).flatten()

            # If dict (MediaPipe style) with keys for hands only
            if isinstance(ld, dict):
                parts = []
                # Only process hands (left_hand, right_hand) - no pose, no face
                for key in ("left_hand", "right_hand"):
                    elems = ld.get(key, [])
                    # enforce exactly 21 landmarks
                    elems = elems[:21]

                    while len(elems) < 21:
                        elems.append(None)

                    # each elem is expected to be dict with x,y,z (no visibility for hands)
                    for p in elems:
                        if p is None:
                            # missing point -> pad zeros (only x,y,z for hands)
                            parts.extend([0.0, 0.0, 0.0])
                            continue
                        x = p.get("x") if isinstance(p, dict) else None
                        y = p.get("y") if isinstance(p, dict) else None
                        z = p.get("z") if isinstance(p, dict) else None
                        # Only x,y,z for hands (no visibility)
                        parts.extend([
                            float(x) if x is not None else 0.0,
                            float(y) if y is not None else 0.0,
                            float(z) if z is not None else 0.0,
                        ])
                return np.array(parts, dtype="float32")

            # Unknown format -> attempt to coerce
            return np.asarray( ld, dtype=np.float32 ).flatten()

        landmarks_seq = []
        for f in frames:
            raw = f.get("landmarks")
            flat = flatten_landmarks(raw)
            if flat is None:
                raise ValueError("frame missing landmarks")
            landmarks_seq.append(flat)

        # Ensure all frames have same vector length by padding shorter ones
        maxlen = int( getattr(settings, "feature_dim", 126) )
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
            log.debug("[LANDMARKS] built_seq shape=%s dtype=%s", getattr(seq, "shape", None), getattr(seq, "dtype", None))
        # Ensure sequence is numeric float32 (some inputs may produce object-dtype rows)
        try:
            seq = seq.astype("float32")
        except Exception as e:
            log.warning("[LANDMARKS] seq.astype(float32) failed: %s; attempting per-row conversion", e)
            new = np.zeros((T, maxlen), dtype="float32")
            for i in range(T):
                row = landmarks_seq[i]
                try:
                    arr = np.asarray(row, dtype=np.float32).flatten()
                except Exception:
                    # best-effort flatten for nested dict/list structures
                    vals = []
                    def collect(x):
                        if x is None:
                            return
                        if isinstance(x, (int, float)):
                            vals.append(float(x))
                        elif isinstance(x, dict):
                            # prefer x,y,z,visibility order if available
                            for k in ("x", "y", "z", "visibility"):
                                if k in x:
                                    try:
                                        vals.append(float(x.get(k) or 0.0))
                                    except Exception:
                                        vals.append(0.0)
                            # if dict has nested lists, collect them too
                            for v in x.values():
                                if isinstance(v, (list, tuple)):
                                    for it in v:
                                        collect(it)
                        elif isinstance(x, (list, tuple, np.ndarray)):
                            for it in x:
                                collect(it)
                        else:
                            # ignore unknown types
                            return
                    collect(row)
                    arr = np.asarray(vals, dtype=np.float32)

                if arr.size > maxlen:
                    new[i, :] = arr[:maxlen]
                else:
                    new[i, : arr.size] = arr
            seq = new
    except Exception as e:
        log.error("[LANDMARKS][ERROR] %s", e)
        return {"success": False, "message": f"Invalid frames payload: {e}"}
    
    # Ensure sequence has proper shape (pad/truncate to settings.seq_len)
    seq_padded, info = normalize_sequence(
        seq,
        expected_T=int(getattr(settings, "seq_len", 60)),
        expected_D=int(getattr(settings, "feature_dim", 126)),
    )

    for t in range(seq_padded.shape[0]):
        seq_padded[t] = normalize_hands_vector_126(
            seq_padded[t]
        )

    valid_ratio = np.mean(
        np.any(seq_padded != 0.0, axis=1)
    )

    if valid_ratio < 0.7:
        return {
            "success": False,
            "message": "Too many invalid frames"
        }

    meta = {
        "user": user,
        "session_id": session_id,
        "fps_original": None,
        "fps_processed": None,
        "completeness": None,
        "created_at": su.now_str(),
    }

    path = save_sequence_npz(
        class_meta,
        seq_padded,
        meta=meta,
        augment_id=0,
        source_type="camera"
    )

    return {
        "success": True,
        "id": session_id,
        "paths": [path],
        "total_samples": 1,
        "message": "saved original sample",
        "language": language,
        "dialect": dialect
    }
