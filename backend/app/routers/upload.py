import asyncio
import re
import uuid
import logging
import numpy as np

from typing import Dict, Any
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, Body, HTTPException

from app.modules.security.rate_limit_deps import limit_upload
from app.modules.dataset import raw_video_upload_service
from app.modules.dataset.catalog import now_str as dataset_now_str
from app.dataset_manager import (
    get_or_register_class,
    list_classes,
    normalize_dialect,
    parse_hands_required,
    set_class_hands_required,
)
from app.processing.utils import (
    DEFAULT_NORMALIZATION_VERSION,
    normalize_hands_vector_126,
)
from app.processing.utils import normalize_sequence
from app.processing.class_registry import AlphabetLabelError
from app.processing.quality import (
    compute_quality_metrics,
    evaluate_quality,
    qc_threshold_snapshot,
    record_quality_attempt,
)
from app.dataset_samples import save_sequence_npz
from app.raw_uploads import (
    find_raw_upload,
    find_raw_uploads_by_class,
)
from app.config import settings
from app.core.http_validation import (
    validate_label,
    validate_language,
    validate_dialect,
)
from app.modules.identity._web_compat import get_current_user
from app.modules.saas.tenant_context import require_tenant
from app.modules.saas import storage_quota
from app.modules.security.quota_deps import guard_storage, storage_full_http
from app.modules.saas.webhooks import emit

# The limit is declared on the router rather than per endpoint because all three
# endpoints here are writes, and this is the most expensive path in the system:
# one request writes a file to disk, runs MediaPipe over it and enqueues a Celery
# task. A per-endpoint decoration would also be one more thing for the next
# endpoint added here to forget.
router = APIRouter(
    prefix="/upload", tags=["upload"], dependencies=[Depends(limit_upload)]
)

@router.options("/camera")
async def options_camera():
    return {"success": True}

def _class_by_uid(class_uid: str):
    """Resolve a selected class inside the request tenant, never globally."""
    uid = str(class_uid or "").strip()
    if not uid:
        return None
    tenant = require_tenant()
    found = next((m for m in list_classes(tenant_id=tenant) if m.class_uid == uid), None)
    if found is None:
        raise HTTPException(status_code=404, detail="Nhãn không thuộc tổ chức hiện tại")
    return found


def _bytes_da_ghi(npz_path) -> int:
    """Số byte một mẫu camera thật sự chiếm trên đĩa.

    Một mẫu là BA tệp, không phải một: `.npz` đặc trưng, bản sao trong kho raw
    (`raw_archive_path`), và sidecar JSON cạnh nó. Chỉ đo tệp đặc trưng sẽ tính
    thiếu khoảng một phần ba — kho raw giữ `landmarks_raw` và `landmarks_world`,
    đo được là 33% của một npz v2 — và bộ đếm sẽ lệch đúng chừng ấy mỗi ngày cho
    tới lượt đối chiếu.

    Bảng hiện vật tính phí ở `docs/07-business/BILLABLE_STORAGE_INVENTORY.md`.
    """
    from app.dataset_samples import raw_archive_path

    p = Path(npz_path)
    tong = 0
    for q in (p, raw_archive_path(p), p.with_suffix(".json")):
        try:
            tong += q.stat().st_size
        except OSError:
            continue
    return tong


def _alphabet_error_detail(exc: Exception, requested: str, resolved: str) -> str:
    """Câu 422 cho nhãn bảng chữ cái sai — kèm lý do NẾU phương ngữ bị đổi.

    16/09/2026: người thu chọn phương ngữ `test`, nhận "A fingerspelling label
    must be exactly one letter" và không hiểu vì sao — `test` đã được gộp vào
    `bang-chu-cai` từ 22/08 (`dialect_aliases`), nên máy chủ âm thầm đưa mẫu
    sang bảng chữ cái rồi áp luật một chữ cái. Không nói ra bước gộp thì thông
    báo đúng mà vô nghĩa với người đọc.
    """
    from app.modules.dataset.vocabulary_registry import slugify_dialect

    req = slugify_dialect(requested or "")
    if req and resolved and req != resolved:
        return (f"{exc} Phương ngữ '{req}' đã được gộp vào '{resolved}' (bảng chữ cái), "
                f"nên nhãn phải là một chữ cái. Chọn phương ngữ khác nếu đây không phải mẫu bảng chữ cái.")
    return str(exc)

@router.post("/video")
async def upload_video(
    file: UploadFile = File(...),
    user: str = Form(""),
    label: str = Form(...),
    language: str = Form("vn"),
    dialect: str = Form("common"),
    class_uid: str = Form(None),
    visibility: str = Form("private"),
    session_id: str = Form(None),
    upload_uid: str = Form(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    duplicate = await raw_video_upload_service.duplicate_upload_result(
        upload_uid, session_id
    )
    if duplicate is not None:
        return duplicate
    label = validate_label(label)
    language = validate_language(language)
    dialect_requested = dialect
    # A selected class_uid is canonical. Do not resolve a stale display
    # dialect through an alias before the UID is checked; an old alias such as
    # `test -> bang-chu-cai` must not make "Xin chào" fail the alphabet rule.
    dialect = (
        ""
        if class_uid
        else validate_dialect(normalize_dialect(dialect, tenant_id=require_tenant()))
    )
    visibility = visibility if visibility in {"private", "tenant", "community"} else "private"
    try:
        return await raw_video_upload_service.store_raw_video(
            file=file,
            user=user,
            label=label,
            language=language,
            dialect=dialect,
            class_uid=class_uid,
            visibility=visibility,
            session_id=session_id,
            upload_uid=upload_uid,
            tenant_id=require_tenant(),
            current_user=current_user,
        )
    except raw_video_upload_service.UploadReadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except raw_video_upload_service.UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except raw_video_upload_service.InvalidVideoFormatError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except raw_video_upload_service.UploadClassNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AlphabetLabelError as exc:
        raise HTTPException(
            status_code=422,
            detail=_alphabet_error_detail(exc, dialect_requested, dialect),
        ) from exc
    except storage_quota.StorageQuotaExceeded as exc:
        raise storage_full_http(exc) from exc

def _raw_upload_owner(upload_uid: str) -> str:
    """`auth_user_id` của người đã tải video lên (rỗng nếu không tra được)."""
    if not upload_uid:
        return ""
    try:
        from app.storage.metadata_db import _fetch_all

        rows = _fetch_all("SELECT auth_user_id FROM raw_uploads WHERE upload_uid = %s", (upload_uid,))
        return str(rows[0]["auth_user_id"] or "") if rows else ""
    except Exception:
        return ""


def _in_request_tenant(row: Dict[str, Any], tenant: str) -> bool:
    """`uploads.csv` là tệp CHUNG của mọi tenant: chỉ nhận dòng của tenant đang dùng.

    Trước 17/10/2026 endpoint xử lý lại nhận bất kỳ `upload_uid`/`class_uid` nào
    trong tệp, nên thành viên tenant A đưa được video của tenant B vào hàng xử lý.
    Lọc ở đây cũng làm task mang đúng header tenant (tenant của request = tenant
    của bản tải lên), nên pipeline tìm được `class_uid` của nó.
    """
    from app.modules.saas.tenancy import tenant_id_of

    return tenant_id_of(row) == tenant


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
        # Chủ mẫu là người TẢI video lên, không phải người bấm xử lý lại.
        # `uploads.csv` không có cột này nên đọc từ bảng `raw_uploads`.
        user_id=_raw_upload_owner(uid) or triggered_by,
        class_uid=row.get("class_uid", "") or "",
        visibility=row.get("visibility", "private") or "private",
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
    tenant = require_tenant()
    if class_uid:
        rows = await asyncio.to_thread(find_raw_uploads_by_class, class_uid)
        rows = [r for r in rows if _in_request_tenant(r, tenant)]
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
            if not row or not _in_request_tenant(row, tenant):
                # Cùng câu trả lời cho "không có" và "của tenant khác".
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
    dialect_requested = str(payload.get("dialect", "common") or "")
    language = validate_language(payload.get("language", "vn"))
    class_uid = str(payload.get("class_uid") or "").strip()
    dialect = (
        ""
        if class_uid
        else validate_dialect(normalize_dialect(dialect_requested, tenant_id=require_tenant()))
    )
    visibility = str(payload.get("visibility") or "private").strip().lower()
    if visibility not in {"private", "tenant", "community"}:
        visibility = "private"
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
    try:
        class_meta = _class_by_uid(class_uid)
        if class_meta is None:
            class_meta = get_or_register_class(label_original=label, language=language, dialect=dialect or "")
        else:
            label, language, dialect = class_meta.label_original, class_meta.language, class_meta.dialect
    except AlphabetLabelError as exc:
        # Cùng lý do như ở /video: lỗi của người gửi thì trả 422 có lời, không 500.
        raise HTTPException(status_code=422, detail=_alphabet_error_detail(exc, dialect_requested, dialect)) from exc

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
        def flatten_landmarks(ld, keys=("left_hand", "right_hand")):
            # If already a list/array of numbers, return as-is
            if ld is None:
                return None
            if isinstance(ld, (list, tuple, np.ndarray)):
                return np.asarray( ld, dtype=np.float32 ).flatten()

            # If dict (MediaPipe style) with keys for hands only
            if isinstance(ld, dict):
                parts = []
                # Only process hands (left_hand, right_hand) - no pose, no face
                for key in keys:
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
    
    # Preprocess contract v2: keep the RAW landmark sequence (image-normalized
    # MediaPipe coordinates, BEFORE wrist centering/scaling and BEFORE temporal
    # padding) so future preprocessing experiments stay possible. Legacy
    # samples never get a synthesized raw copy.
    seq_raw = seq.astype(np.float32, copy=True)
    sequence_length_original = int(seq.shape[0])

    # MediaPipe's OTHER landmark set, when the recorder sent it. `seq` above is
    # built from `landmarks`, which is 2.5D: x,y are image coordinates and z is
    # a relative depth regressed against the wrist, explicitly not metric.
    # `world_landmarks` is real 3D in metres, origin at the hand's geometric
    # centre. It is the only thing that makes a 3D view of a hand geometrically
    # honest, so it is stored verbatim and never normalized or padded — it
    # exists to be LOOKED at, not to be learned from.
    #
    # Absent for every sample recorded before the capture modal sent it; None
    # then, so no zero-filled array is written that a reader could mistake for
    # a measurement.
    seq_world = None
    try:
        world_rows = [
            flatten_landmarks(f.get("landmarks"), keys=("left_hand_world", "right_hand_world"))
            for f in frames
        ]
        if any(r is not None and r.size and np.any(r != 0.0) for r in world_rows):
            seq_world = np.zeros((len(world_rows), maxlen), dtype=np.float32)
            for i, row in enumerate(world_rows):
                if row is None or not row.size:
                    continue
                n = min(row.size, maxlen)
                seq_world[i, :n] = row[:n].astype(np.float32)
    except Exception as e:
        # Never fail an upload over the display-only array.
        log.warning("[LANDMARKS][world] ignored malformed world landmarks: %s", e)
        seq_world = None

    # Ensure sequence has proper shape (pad/truncate to settings.seq_len)
    seq_padded, info = normalize_sequence(
        seq,
        expected_T=int(getattr(settings, "seq_len", 60)),
        expected_D=int(getattr(settings, "feature_dim", 126)),
    )

    # Validity masks, computed BEFORE per-hand normalization (zero block = absent)
    left_hand_valid_mask = np.any(seq_padded[:, :63] != 0.0, axis=1)
    right_hand_valid_mask = np.any(seq_padded[:, 63:] != 0.0, axis=1)
    frame_valid_mask = left_hand_valid_mask | right_hand_valid_mask

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

    qc_thresholds = qc_threshold_snapshot(settings)

    if settings.qc_enabled and verdict.reject_code:
        # A rejected attempt keeps NO landmarks and NO video — only a minimal
        # audit record, so pass/warn/reject rates are reportable without the
        # rejected data ever entering the dataset. This log is deliberately
        # separate from samples.csv and is never read by the manifest builder.
        try:
            from app.signers import resolve_signer_for_user
            _signer = resolve_signer_for_user(current_user)
        except Exception:
            _signer = ""
        record_quality_attempt({
            "attempt_id": uuid.uuid4().hex[:12],
            "campaign": getattr(settings, "collection_campaign", "") or "",
            "signer_id": _signer,
            "session_id": session_id,
            "recognition_profile": class_meta.recognition_profile or "",
            "vocabulary_scope": class_meta.vocabulary_scope or "",
            "label": label,
            "status": "rejected",
            "flags": verdict.flags,
            "metrics": metrics.as_dict(),
            "quality_config_version": qc_thresholds["quality_config_version"],
            "quality_thresholds": qc_thresholds,
            "source_type": "camera",
            "timestamp": dataset_now_str(),
        })
        raise HTTPException(
            status_code=422,
            detail={
                "code": verdict.reject_code,
                "message": "Mẫu không đạt chất lượng tối thiểu, vui lòng thu lại.",
                "metrics": metrics.as_dict(),
            },
        )

    # One name for what is computed AND what is stamped on the row below. The
    # version used to be a string literal in the metadata dict, three hundred
    # lines away from the call that did the work — so the row could claim v1
    # while the features were anything at all, and nothing would disagree.
    normalization_version = DEFAULT_NORMALIZATION_VERSION
    for t in range(seq_padded.shape[0]):
        seq_padded[t] = normalize_hands_vector_126(
            seq_padded[t], normalization_version
        )

    # Vocabulary schema v2: normalized signer identity (never free text) +
    # provenance + preprocess contract. Class-level v2 fields ride along so
    # samples are self-describing even before the class is fully migrated.
    try:
        from app.signers import resolve_signer_for_user
        signer_id = resolve_signer_for_user(current_user)
    except Exception as exc:
        log.warning("[SIGNER] resolution failed (sample saved without signer_id): %s", exc)
        signer_id = ""

    meta = {
        "user": user,
        "user_id": user,
        "auth_user_id": current_user["id"],
        "visibility": visibility,
        "signer_id": signer_id,
        "session_id": session_id,
        "collection_campaign": getattr(settings, "collection_campaign", "") or "",
        "vocabulary_scope": class_meta.vocabulary_scope or "",
        "recognition_profile": class_meta.recognition_profile or "",
        "vocabulary_group": class_meta.vocabulary_group or "",
        "semantic_label": class_meta.semantic_label or "",
        "normalization_version": normalization_version,
        "preprocess_contract_version": "v2",
        # Renamed from "mediapipe_normalized", which collided head-on with
        # MediaPipe's own vocabulary: there, "normalized landmarks" means image
        # coordinates in [0,1] — the opposite of what is stored here. Readers
        # still accept the old spelling (COORD_SPACE_WRIST_CENTRED).
        "coordinate_space": "wrist_centred_v1",
        "target_sequence_length": int(getattr(settings, "seq_len", 60)),
        "feature_dimension": int(getattr(settings, "feature_dim", 126)),
        "sequence_length_original": sequence_length_original,
        "quality_status": "flagged" if verdict.warning_codes else "ok",
        "fps_original": None,
        "fps_processed": None,
        "completeness": round(metrics.completeness, 4),
        "left_hand_ratio": round(metrics.left_hand_ratio, 4),
        "right_hand_ratio": round(metrics.right_hand_ratio, 4),
        "both_hands_ratio": round(metrics.both_hands_ratio, 4),
        "any_hand_ratio": round(metrics.any_hand_ratio, 4),
        # 'jitter' is kept for backward compatibility with existing readers;
        # 'jitter_p95' is the explicit name used from the pilot campaign on.
        "jitter": round(metrics.jitter_p95, 5),
        "jitter_p95": round(metrics.jitter_p95, 5),
        "activity": round(metrics.activity, 5),
        "quality_flags": verdict.flags,
        "quality_config_version": qc_thresholds["quality_config_version"],
        "quality_thresholds": qc_thresholds,
        "hands_required": effective_hands or None,
        "client_quality": client_quality,
        "created_at": dataset_now_str(),
    }

    # Hạn mức dung lượng. Đường này gửi landmark dạng JSON, nên kích thước trên
    # dây không nói gì về `.npz` sẽ ghi ra — nhưng CẬN TRÊN thì tính được chính
    # xác, và một cận trên tính được thì tốt hơn hẳn một ước lượng:
    #
    #   `_atomic_write_npz` dùng `savez_compressed`, nên tệp ra LUÔN nhỏ hơn
    #   tổng `nbytes` của các mảng đi vào. Cộng tổng ấy lại là một cận trên
    #   đúng theo định nghĩa, không phải một phỏng đoán.
    #
    # Hệ quả: `settle` trên đường này chỉ có thể GIẢM. Nó vẫn nhận
    # `absorb_overflow=True` chứ không phải `discard=`, vì tới lúc quyết toán
    # thì `save_sequence_npz` đã ghi cả samples.csv lẫn Postgres — gỡ tệp lúc ấy
    # để lại dòng metadata trỏ vào hư không, tệ hơn hẳn một lần vượt trần tạm
    # thời mà lượt ghi sau đã chặn. Nếu cảnh báo "cận trên SAI" xuất hiện trong
    # nhật ký thì phép tính dưới đây thiếu một mảng, và đó là một lỗi phải sửa.
    can_tren = int(seq_padded.nbytes) * 2          # `sequence` + `landmarks_normalized`
    for _mang in (seq_raw, seq_world, frame_valid_mask,
                  left_hand_valid_mask, right_hand_valid_mask):
        if _mang is not None:
            can_tren += int(np.asarray(_mang).nbytes)
    can_tren += 64 * 1024                           # sidecar JSON + header npz
    giu_cho = guard_storage(current_user, nbytes=can_tren)

    da_tieu_giu_cho = False
    try:
        try:
            path = save_sequence_npz(
                class_meta,
                seq_padded,
                meta=meta,
                augment_id=0,
                source_type="camera",
                raw_sequence=seq_raw,
                world_sequence=seq_world,
                coordinate_space="wrist_centred_v1",
                frame_valid_mask=frame_valid_mask,
                left_hand_valid_mask=left_hand_valid_mask,
                right_hand_valid_mask=right_hand_valid_mask,
            )
        except Exception as e:
            log.error("[UPLOAD][camera][ERROR] sample save failed: %s", e)
            return {"success": False, "message": f"Sample upload failed: {e}"}

        storage_quota.settle(giu_cho, _bytes_da_ghi(path), absorb_overflow=True)
        da_tieu_giu_cho = True
    finally:
        if not da_tieu_giu_cho:
            storage_quota.release(giu_cho)

    # Same audit stream as rejected attempts, so pass/warn/reject rates for a
    # campaign are computable from ONE file.
    record_quality_attempt({
        "attempt_id": uuid.uuid4().hex[:12],
        "campaign": getattr(settings, "collection_campaign", "") or "",
        "signer_id": signer_id,
        "session_id": session_id,
        "recognition_profile": class_meta.recognition_profile or "",
        "vocabulary_scope": class_meta.vocabulary_scope or "",
        "label": label,
        "status": "flagged" if verdict.warning_codes else "accepted",
        "flags": verdict.flags,
        "metrics": metrics.as_dict(),
        "quality_config_version": qc_thresholds["quality_config_version"],
        "quality_thresholds": qc_thresholds,
        "source_type": "camera",
        "sample_path": path,
        "timestamp": dataset_now_str(),
    })

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

    # Sự kiện phát SAU khi mẫu đã nằm trên đĩa, không phải trước. Phát trước là
    # hứa với hệ thống của khách hàng về một thứ còn có thể hỏng.
    #
    # `emit` chỉ XẾP HÀNG (một dòng INSERT) rồi trả về; việc gọi HTTP tới máy
    # chủ khách hàng do tác vụ nền làm. Nếu gọi thẳng ở đây, một endpoint chậm
    # mười giây của khách sẽ làm chậm đúng mười giây thao tác thu mẫu của người
    # dùng. `emit` cũng nuốt mọi lỗi — webhook là tính năng phụ trợ và không
    # được phép làm hỏng một lượt tải mẫu đã thành công.
    emit(
        class_meta.tenant_id, "sample.created",
        {
            "session_id": session_id, "label": label, "language": language,
            "dialect": dialect, "class_uid": class_meta.class_uid,
            "source_type": "camera",
        },
    )

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
