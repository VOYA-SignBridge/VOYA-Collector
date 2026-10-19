import asyncio
import uuid
import logging

from typing import Dict, Any
from fastapi import APIRouter, Depends, UploadFile, File, Form, Body, HTTPException

from app.modules.dataset import (
    camera_capture_service,
    raw_video_upload_service,
    video_processing_service,
)
from app.modules.dataset.catalog import normalize_dialect
from app.core.http_validation import (
    validate_label,
    validate_language,
    validate_dialect,
    save_upload_with_limit,
)
from app.modules.identity import get_current_user

router = APIRouter(prefix="/upload", tags=["upload"])


@router.options("/camera")
async def options_camera():
    return {"success": True}


def _normalize_video_fields(label: str, language: str, dialect: str) -> tuple[str, str, str]:
    return (
        validate_label(label),
        validate_language(language),
        validate_dialect(normalize_dialect(dialect)),
    )


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
    """Validate upload fields and delegate raw-video persistence."""
    try:
        return await raw_video_upload_service.store_raw_video(
            file=file,
            user=user,
            label=label,
            language=language,
            dialect=dialect,
            session_id=session_id,
            upload_uid=upload_uid,
            current_user=current_user,
            save_upload=save_upload_with_limit,
            normalize_fields=_normalize_video_fields,
        )
    except raw_video_upload_service.UploadReadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except raw_video_upload_service.UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc


@router.post("/video/process")
async def process_uploaded_videos(
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Queue feature extraction for one, many, or one class of raw uploads."""
    triggered_by = str(current_user.get("id", "") or "")
    try:
        result = await video_processing_service.enqueue_uploaded_videos(
            payload,
            triggered_by=triggered_by,
        )
    except video_processing_service.RawUploadsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except video_processing_service.ProcessingRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    logging.getLogger("upload.process").info(
        "[UPLOAD][process] triggered_by=%s queued=%s total=%s",
        triggered_by,
        result["queued"],
        result["total"],
    )
    return result


@router.post("/camera")
async def upload_camera(
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Validate the HTTP payload and delegate camera capture processing."""
    user = payload.get("user", "") or current_user.get("username", "")
    label = validate_label(payload.get("label"))
    dialect = validate_dialect(normalize_dialect(payload.get("dialect", "common")))
    language = validate_language(payload.get("language", "vn"))
    session_id = payload.get("session_id") or uuid.uuid4().hex

    try:
        return await asyncio.to_thread(
            camera_capture_service.capture_camera_sample,
            payload=payload,
            current_user=current_user,
            user=user,
            label=label,
            language=language,
            dialect=dialect,
            session_id=session_id,
        )
    except camera_capture_service.CameraQualityRejected as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from exc
