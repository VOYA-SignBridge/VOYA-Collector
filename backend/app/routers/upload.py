import uuid
import time
import logging
import numpy as np

from typing import Dict, Any
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, Body, HTTPException

from app.processing import storage_utils as su
from app.dataset_manager import get_or_register_class, normalize_dialect
from app.processing.utils import normalize_hands_vector_126
from app.processing.utils import normalize_sequence
from app.dataset_samples import save_sequence_npz
from app.raw_uploads import append_raw_upload_row, now_str as raw_upload_now_str
from app.config import settings
from app.api_validation import (
    validate_label,
    validate_language,
    validate_dialect,
    save_upload_with_limit,
)
from app.storage.gdrive_client import upload_to_gdrive
from app.auth import get_current_user

router = APIRouter(prefix="/upload", tags=["upload"])

@router.options("/camera")
async def options_camera():
    return {"success": True}

def _safe_path_part(value: str | None, fallback: str) -> str:
    text = str(value or fallback).strip() or fallback
    text = Path(text).name.strip() or fallback
    return "".join(ch if ch.isalnum() or ch in " ._-" else "_" for ch in text)


def _measure_upload_size(upload_file, *, max_bytes: int) -> int:
    try:
        upload_file.seek(0, 2)
        size = upload_file.tell()
        upload_file.seek(0)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"cannot read uploaded file: {exc}") from exc

    if max_bytes > 0 and size > max_bytes:
        raise HTTPException(status_code=413, detail=f"upload too large (max {max_bytes} bytes)")
    return int(size)


def _raw_upload_local_path(class_meta, upload_uid: str, original_filename: str) -> Path:
    raw_dir = settings.dataset_root / "raw_videos" / class_meta.language / class_meta.dialect / class_meta.folder_name()
    return raw_dir / f"{upload_uid}_{original_filename}"


@router.post("/video")
async def upload_video(
    file: UploadFile = File(...),
    user: str = Form(""),
    label: str = Form(...),
    language: str = Form("vn"),
    dialect: str = Form("common"),
    session_uid: str = Form(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    start = time.time()
    log = logging.getLogger("upload.video")
    
    import re
    if not session_uid or not re.match(r"^(LC|UP)-\d{6}-\d{4}-[A-Z0-9a-z]{6}$", session_uid):
        return {"success": False, "message": "Invalid or missing session_uid. Must match LC/UP format."}

    # Validate & normalize inputs
    label = validate_label(label)
    language = validate_language(language)
    dialect = validate_dialect(normalize_dialect(dialect))

    log.info("[UPLOAD][video] user=%s label=%s lang=%s dialect=%s filename=%s session=%s", user or current_user.get("username", ""), label, language, dialect, getattr(file, 'filename', ''), session_uid)
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

    max_mb = int(getattr(settings, "max_upload_mb", 1024))
    max_bytes = max_mb * 1024 * 1024 if max_mb > 0 else 0
    upload_size = _measure_upload_size(file.file, max_bytes=max_bytes)
    log.info("[UPLOAD][video] bytes_received=%s max_bytes=%s", upload_size, max_bytes)

    upload_uid = uuid.uuid4().hex[:8]
    original_filename = _safe_path_part(getattr(file, "filename", None), "upload.mp4")
    local_path = _raw_upload_local_path(class_meta, upload_uid, original_filename)
    storage_key = local_path.relative_to(settings.dataset_root).as_posix()

    bytes_written, local_path_str = save_upload_with_limit(file.file, local_path, max_bytes=max_bytes)
    storage_url = ""
    provider = "local"

    if getattr(settings, "use_google_drive", False):
        credentials_path = Path(str(getattr(settings, "google_drive_credentials", "")))
        if credentials_path.exists():
            try:
                storage_url = upload_to_gdrive(
                    local_path_str,
                    storage_key,
                    content_type=file.content_type or "application/octet-stream",
                )
                provider = "local+gdrive"
                log.info("[UPLOAD][video] raw video mirrored to Google Drive key=%s url=%s", storage_key, storage_url)
            except Exception as exc:
                log.warning("[UPLOAD][video] Google Drive mirror failed, keeping local copy only: %s", exc)
        else:
            log.warning("[UPLOAD][video] Google Drive credentials missing at %s; keeping local copy only", credentials_path)

    created_at = raw_upload_now_str()
    raw_upload_row = {
        "upload_uid": upload_uid,
        "class_uid": class_meta.class_uid,
        "slug": class_meta.slug,
        "label_original": class_meta.label_original,
        "language": class_meta.language,
        "dialect": class_meta.dialect,
        "source_type": "video",
        "user_id": current_user["id"],
        "username": current_user["username"],
        "session_uid": session_uid,
        "original_filename": original_filename,
        "local_path": storage_key,  # Store relative path instead of absolute
        "storage_key": storage_key,
        "storage_url": storage_url,
        "created_at": created_at,
        "updated_at": created_at,
    }
    try:
        append_raw_upload_row(raw_upload_row)
    except Exception as e:
        log.warning("[UPLOAD][video] raw upload CSV metadata failed: %s", e)

    try:
        from app.storage.metadata_db import insert_raw_upload

        insert_raw_upload({**raw_upload_row, "user_id": current_user["id"]})
    except Exception as e:
        if getattr(settings, "debug_logging", False):
            log.debug("[UPLOAD][video] raw upload DB metadata failed: %s", e)

    log.info(
        "[UPLOAD][video] stored raw video provider=%s path=%s bytes_written=%s elapsed=%.3fs",
        provider,
        local_path_str,
        bytes_written,
        time.time() - start,
    )
    return {
        "success": True,
        "id": upload_uid,
        "session_uid": session_uid,
        "session_id": session_uid,
        "upload_uid": upload_uid,
        "storage_url": storage_url,
        "message": "raw video uploaded",
    }
    


@router.post("/camera")
async def upload_camera(
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Accept frames (array of arrays) and metadata, save as npz via storage_utils.save_sample
    Payload example: { user: str, label: str, session_id: str, dialect: str, frames: [{timestamp, landmarks}, ...] }
    """
    user = payload.get("user", "") or current_user.get("username", "")
    label = validate_label(payload.get("label"))
    dialect = validate_dialect(normalize_dialect(payload.get("dialect", "common")))
    language = validate_language(payload.get("language", "vn"))
    session_uid = payload.get("session_uid") or payload.get("session_id", "")
    frames = payload.get("frames")

    import re
    if not session_uid or not re.match(r"^(LC|UP)-\d{6}-\d{4}-[A-Z0-9a-z]{6}$", session_uid):
        return {"success": False, "message": "Invalid or missing session_uid. Must match LC/UP format."}

    if not frames:
        return {"success": False, "message": "Missing label or frames"}

    # Basic payload size guard (prevents accidental huge posts)
    try:
        max_frames = int(getattr(settings, "max_camera_frames", 600))
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
        "user_id": current_user["id"],
        "session_uid": session_uid,
        "fps_original": None,
        "fps_processed": None,
        "completeness": None,
        "created_at": su.now_str(),
    }

    try:
        path = save_sequence_npz(
            class_meta,
            seq_padded,
            meta=meta,
            augment_id=0,
            source_type="camera"
        )
    except Exception as e:
        log.error("[UPLOAD][camera][ERROR] sample save failed: %s", e)
        return {"success": False, "message": f"Sample upload failed: {e}"}

    return {
        "success": True,
        "id": session_uid,
        "paths": [path],
        "total_samples": 1,
        "message": "saved original sample",
        "language": language,
        "dialect": dialect
    }
