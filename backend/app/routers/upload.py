import asyncio
import re
import uuid
import time
import logging
import numpy as np

from typing import Dict, Any
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, Body, HTTPException

from app.processing import storage_utils as su
from app.dataset_manager import (
    get_or_register_class,
    normalize_dialect,
    parse_hands_required,
    set_class_hands_required,
)
from app.processing.utils import normalize_hands_vector_126
from app.processing.utils import normalize_sequence
from app.processing.quality import compute_quality_metrics, evaluate_quality
from app.dataset_samples import save_sequence_npz
from app.raw_uploads import (
    append_raw_upload_row,
    find_raw_upload,
    find_raw_uploads_by_class,
    now_str as raw_upload_now_str,
)
from app.config import settings
from app.api_validation import (
    validate_label,
    validate_language,
    validate_dialect,
    save_upload_with_limit,
)
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
    session_id: str = Form(None),
    upload_uid: str = Form(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    start = time.time()
    log = logging.getLogger("upload.video")
    if not session_id:
        session_id = uuid.uuid4().hex

    # Idempotency key: client sends a stable upload_uid so a client-side
    # timeout + retry does not create duplicate records + duplicate mirrors.
    if upload_uid and re.fullmatch(r"[a-fA-F0-9]{8,64}", upload_uid):
        upload_uid = upload_uid.lower()
        existing = await asyncio.to_thread(find_raw_upload, upload_uid)
        if existing:
            log.info("[UPLOAD][video] duplicate upload_uid=%s — returning existing record", upload_uid)
            return {
                "success": True,
                "id": upload_uid,
                "session_id": existing.get("session_id") or session_id,
                "upload_uid": upload_uid,
                "storage_url": existing.get("storage_url") or existing.get("local_path", ""),
                "message": "already uploaded (duplicate ignored)",
                "duplicate": True,
            }
    else:
        upload_uid = uuid.uuid4().hex[:8]

    # Validate & normalize inputs
    label = validate_label(label)
    language = validate_language(language)
    dialect = validate_dialect(normalize_dialect(dialect))

    log.info("[UPLOAD][video] user=%s label=%s lang=%s dialect=%s filename=%s session=%s", user or current_user.get("username", ""), label, language, dialect, getattr(file, 'filename', ''), session_id)
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

    # Register / fetch class in new hierarchy (in thread — CSV/DB I/O)
    class_meta = await asyncio.to_thread(
        get_or_register_class, label_original=label, language=language, dialect=dialect or ""
    )

    max_mb = int(getattr(settings, "max_upload_mb", 1024))
    max_bytes = max_mb * 1024 * 1024 if max_mb > 0 else 0
    upload_size = _measure_upload_size(file.file, max_bytes=max_bytes)
    log.info("[UPLOAD][video] bytes_received=%s max_bytes=%s", upload_size, max_bytes)

    original_filename = _safe_path_part(getattr(file, "filename", None), "upload.mp4")
    local_path = _raw_upload_local_path(class_meta, upload_uid, original_filename)
    storage_key = local_path.relative_to(settings.dataset_root).as_posix()

    # In thread — large file write + fsync would block the event loop
    bytes_written, local_path_str = await asyncio.to_thread(
        save_upload_with_limit, file.file, local_path, max_bytes=max_bytes
    )
    storage_url = local_path_str
    provider = "local"

    created_at = raw_upload_now_str()
    raw_upload_row = {
        "upload_uid": upload_uid,
        "class_uid": class_meta.class_uid,
        "slug": class_meta.slug,
        "label_original": class_meta.label_original,
        "language": class_meta.language,
        "dialect": class_meta.dialect,
        "source_type": "video",
        "user_id": user or current_user.get("username", ""),
        "session_id": session_id,
        "original_filename": original_filename,
        "local_path": local_path_str,
        "storage_key": storage_key,
        "storage_url": storage_url,
        "created_at": created_at,
        "updated_at": created_at,
    }
    try:
        await asyncio.to_thread(append_raw_upload_row, raw_upload_row)
    except Exception as e:
        log.warning("[UPLOAD][video] raw upload CSV metadata failed: %s", e)

    try:
        from app.storage.metadata_db import insert_raw_upload

        await asyncio.to_thread(insert_raw_upload, {**raw_upload_row, "auth_user_id": current_user["id"]})
    except Exception as e:
        if getattr(settings, "debug_logging", False):
            log.debug("[UPLOAD][video] raw upload DB metadata failed: %s", e)

    # Defer Google Drive mirror to Celery (same pattern as npz samples).
    # The user gets a response immediately after the local save; the worker
    # transfers the video to Drive and updates storage_url when done.
    gdrive_mirror = "disabled"
    if getattr(settings, "use_google_drive", False):
        try:
            from app.export_tasks import upload_raw_video_to_gdrive_task

            upload_raw_video_to_gdrive_task.delay(
                upload_uid=upload_uid,
                local_path=local_path_str,
                storage_key=storage_key,
                content_type=file.content_type or "application/octet-stream",
            )
            gdrive_mirror = "queued"
            log.info("[UPLOAD][video] Google Drive mirror deferred to Celery key=%s", storage_key)
        except Exception as e:
            gdrive_mirror = "dispatch_failed"
            log.warning("[UPLOAD][video] Failed to dispatch GDrive mirror task (local copy kept): %s", e)

    log.info(
        "[UPLOAD][video] stored raw video provider=%s path=%s bytes_written=%s gdrive_mirror=%s elapsed=%.3fs",
        provider,
        local_path_str,
        bytes_written,
        gdrive_mirror,
        time.time() - start,
    )
    return {
        "success": True,
        "id": upload_uid,
        "session_id": session_id,
        "upload_uid": upload_uid,
        "storage_url": storage_url,
        "gdrive_mirror": gdrive_mirror,
        "message": "raw video uploaded",
    }


def _enqueue_video_processing(row: Dict[str, Any], triggered_by: str) -> Dict[str, Any]:
    """Enqueue the async feature-extraction pipeline for one raw upload row.

    Returns a per-item status dict (never raises) so batch calls can report
    partial results. Prefers the Drive URL when present (worker downloads it),
    else the local path (shared /dataset mount).
    """
    from app.tasks import enqueue_process_video

    uid = str(row.get("upload_uid", "")).strip()
    video_path = (row.get("storage_url") or row.get("local_path") or "").strip()
    if not video_path:
        return {"upload_uid": uid, "status": "no_file"}

    task = enqueue_process_video.delay(
        video_path=video_path,
        user=row.get("user_id", "") or "",
        label=row.get("label_original", "") or "",
        session_id=row.get("session_id", "") or uuid.uuid4().hex,
        dialect=row.get("dialect", "") or "common",
        language=row.get("language", "") or "vn",
        user_id=triggered_by,
    )
    return {"upload_uid": uid, "job_id": task.id, "status": "queued"}


@router.post("/video/process")
async def process_uploaded_videos(
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Manually trigger feature extraction (.npz) for previously uploaded raw videos.

    `/upload/video` only stores the raw file; this endpoint enqueues the async
    MediaPipe pipeline on demand (batch-friendly, avoids flooding the worker on
    every upload). Accepts one of:
      - {"upload_uid": "<uid>"}            → single video
      - {"upload_uids": ["<uid>", ...]}    → explicit batch
      - {"class_uid": "<class_uid>"}       → all raw uploads of a class
    """
    log = logging.getLogger("upload.process")

    uid_pattern = re.compile(r"[a-fA-F0-9]{8,64}")

    def _valid(uid: str) -> bool:
        return bool(uid_pattern.fullmatch(uid))

    # 1. Resolve the set of raw-upload rows to process.
    rows: list[Dict[str, Any]] = []
    class_uid = str(payload.get("class_uid", "") or "").strip()
    if class_uid:
        rows = await asyncio.to_thread(find_raw_uploads_by_class, class_uid)
        if not rows:
            raise HTTPException(status_code=404, detail=f"no raw uploads for class_uid: {class_uid}")
    else:
        uids = payload.get("upload_uids")
        single = str(payload.get("upload_uid", "") or "").strip().lower()
        if single and not uids:
            uids = [single]
        if not uids or not isinstance(uids, list):
            raise HTTPException(
                status_code=422,
                detail="provide upload_uid, upload_uids[], or class_uid",
            )

    triggered_by = str(current_user.get("id", "") or "")

    # 2. Enqueue each. Missing/invalid entries are reported, not fatal.
    results: list[Dict[str, Any]] = []
    if class_uid:
        for row in rows:
            results.append(_enqueue_video_processing(row, triggered_by))
    else:
        for raw_uid in uids:
            uid = str(raw_uid).strip().lower()
            if not _valid(uid):
                results.append({"upload_uid": uid, "status": "invalid_uid"})
                continue
            row = await asyncio.to_thread(find_raw_upload, uid)
            if not row:
                results.append({"upload_uid": uid, "status": "not_found"})
                continue
            results.append(_enqueue_video_processing(row, triggered_by))

    queued = sum(1 for r in results if r.get("status") == "queued")
    log.info("[UPLOAD][process] triggered_by=%s queued=%s total=%s", triggered_by, queued, len(results))
    return {"success": True, "queued": queued, "total": len(results), "results": results}


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
    session_id = payload.get("session_id", None) or uuid.uuid4().hex
    frames = payload.get("frames")
    # Client-declared hand requirement (1|2, anything else -> unknown) and
    # client-computed quality snapshot (informational only; server recomputes).
    hands_required_payload = parse_hands_required(payload.get("hands_required")) or 0
    client_quality = payload.get("quality_info") if isinstance(payload.get("quality_info"), dict) else None

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

    # Class value is authoritative; the payload only fills it in on first
    # capture of the label (first-capture-wins, persisted to labels.csv + DB).
    effective_hands = class_meta.hands_required or hands_required_payload
    if not class_meta.hands_required and hands_required_payload in (1, 2):
        try:
            set_class_hands_required(class_meta.class_uid, hands_required_payload)
        except Exception as exc:
            log.warning("[QC] persisting hands_required failed (upload continues): %s", exc)

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

    # QC metrics must be computed BEFORE per-hand normalization: coordinates
    # are still image-normalized (0..1) so jitter has a physical scale, and a
    # missing hand is still an all-zero block.
    metrics = compute_quality_metrics(seq_padded, hands_required=effective_hands)
    verdict = evaluate_quality(metrics, settings)
    log.info(
        "[QC] label=%s hands_required=%s completeness=%.3f L=%.3f R=%.3f both=%.3f jitter_p95=%.4f activity=%.4f flags=%s",
        label, effective_hands or 0, metrics.completeness,
        metrics.left_hand_ratio, metrics.right_hand_ratio, metrics.both_hands_ratio,
        metrics.jitter_p95, metrics.activity, verdict.flags or "-",
    )

    if settings.qc_enabled and verdict.reject_code:
        raise HTTPException(
            status_code=422,
            detail={
                "code": verdict.reject_code,
                "message": "Mẫu không đạt chất lượng tối thiểu, vui lòng thu lại.",
                "metrics": metrics.as_dict(),
            },
        )

    for t in range(seq_padded.shape[0]):
        seq_padded[t] = normalize_hands_vector_126(
            seq_padded[t]
        )

    meta = {
        "user": user,
        "user_id": user,
        "auth_user_id": current_user["id"],
        "session_id": session_id,
        "fps_original": None,
        "fps_processed": None,
        "completeness": round(metrics.completeness, 4),
        "left_hand_ratio": round(metrics.left_hand_ratio, 4),
        "right_hand_ratio": round(metrics.right_hand_ratio, 4),
        "both_hands_ratio": round(metrics.both_hands_ratio, 4),
        "jitter": round(metrics.jitter_p95, 5),
        "activity": round(metrics.activity, 5),
        "quality_flags": verdict.flags,
        "hands_required": effective_hands or None,
        "client_quality": client_quality,
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

    quality_payload = metrics.as_dict()
    quality_payload["warnings"] = [
        {
            "code": code,
            "message": "Chất lượng mẫu thấp — mẫu đã được lưu và đánh dấu để kiểm tra.",
            "detail": {
                "completeness": round(metrics.completeness, 4),
                "jitter_p95": round(metrics.jitter_p95, 5),
                "hands_required": effective_hands or None,
            },
        }
        for code in verdict.warning_codes
    ]

    return {
        "success": True,
        "id": session_id,
        "paths": [path],
        "total_samples": 1,
        "message": "saved original sample",
        "language": language,
        "dialect": dialect,
        "quality": quality_payload,
    }
