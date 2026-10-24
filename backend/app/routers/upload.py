import uuid

from typing import Dict, Any
from fastapi import APIRouter, Depends, UploadFile, File, Form, Body, HTTPException

from app.modules.security.rate_limit_deps import limit_upload
from app.modules.dataset import (
    camera_capture_service,
    raw_video_upload_service,
    video_processing_service,
)
from app.dataset_manager import normalize_dialect
from app.processing.class_registry import AlphabetLabelError
from app.core.http_validation import (
    validate_label,
    validate_language,
    validate_dialect,
)
from app.modules.identity._web_compat import get_current_user
from app.modules.saas.tenant_context import require_tenant
from app.modules.saas import storage_quota
from app.modules.security.quota_deps import storage_full_http

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
    try:
        return await video_processing_service.enqueue_uploaded_videos(
            payload,
            triggered_by=str(current_user.get("id", "") or ""),
            tenant_id=require_tenant(),
        )
    except video_processing_service.ProcessingRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except video_processing_service.RawUploadsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/camera")
async def upload_camera(
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Validate and persist one live-camera landmark capture."""
    user = payload.get("user", "") or current_user.get("username", "")
    label = validate_label(payload.get("label"))
    dialect_requested = str(payload.get("dialect", "common") or "")
    language = validate_language(payload.get("language", "vn"))
    class_uid = str(payload.get("class_uid") or "").strip()
    dialect = (
        ""
        if class_uid
        else validate_dialect(
            normalize_dialect(dialect_requested, tenant_id=require_tenant())
        )
    )
    visibility = str(payload.get("visibility") or "private").strip().lower()
    if visibility not in {"private", "tenant", "community"}:
        visibility = "private"
    session_id = payload.get("session_id") or uuid.uuid4().hex

    try:
        return camera_capture_service.capture_camera_sample(
            payload=payload,
            current_user=current_user,
            user=user,
            label=label,
            language=language,
            dialect=dialect,
            session_id=session_id,
            class_uid=class_uid,
            visibility=visibility,
        )
    except camera_capture_service.CameraClassNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AlphabetLabelError as exc:
        raise HTTPException(
            status_code=422,
            detail=_alphabet_error_detail(exc, dialect_requested, dialect),
        ) from exc
    except camera_capture_service.CameraQualityRejected as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from exc
