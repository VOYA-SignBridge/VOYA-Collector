"""Persist raw video uploads and dispatch optional Drive mirroring."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict

from app.config import settings
from app.core.http_validation import save_upload_with_limit
from app.modules.dataset.catalog import (
    get_or_register_class,
    list_classes,
    raw_class_dir,
)
from app.modules.dataset.raw_uploads import append_raw_upload_row, find_raw_upload, now_str
from app.modules.dataset.video_processing_service import enqueue_video_processing
from app.modules.saas import storage_quota
from app.modules.security.quota_deps import tenant_of

logger = logging.getLogger("upload.video")


class UploadReadError(ValueError):
    pass


class UploadTooLargeError(ValueError):
    pass


class InvalidVideoFormatError(ValueError):
    pass


class UploadClassNotFoundError(LookupError):
    pass


_VIDEO_MAGIC_HEAD_HEX = {
    "1a45dfa3",  # Matroska / WebM (EBML)
    "000001b3",  # MPEG-1 video
}


def _safe_path_part(value: str | None, fallback: str) -> str:
    text = str(value or fallback).strip() or fallback
    text = Path(text).name.strip() or fallback
    return "".join(character if character.isalnum() or character in " ._-" else "_" for character in text)


def peek_head(upload_file, n: int = 16) -> bytes:
    """Read a prefix without consuming bytes from the upload stream."""
    try:
        position = upload_file.tell()
        head = upload_file.read(n)
        upload_file.seek(position)
        return head or b""
    except Exception as exc:
        raise UploadReadError(f"cannot read uploaded file: {exc}") from exc


def looks_like_video(head: bytes) -> bool:
    """Recognise supported video containers by signature, not filename."""
    if len(head) < 12:
        return False
    if head[4:8] == b"ftyp":
        return True
    if head[:4].hex() in _VIDEO_MAGIC_HEAD_HEX:
        return True
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return True
    if head[:4] == b"\x00\x00\x01\xba":
        return True
    if head[:3] == b"FLV":
        return True
    return False


def _measure_upload_size(upload_file, *, max_bytes: int) -> int:
    try:
        upload_file.seek(0, 2)
        size = upload_file.tell()
        upload_file.seek(0)
    except Exception as exc:
        raise UploadReadError(f"cannot read uploaded file: {exc}") from exc
    if max_bytes > 0 and size > max_bytes:
        raise UploadTooLargeError(f"upload too large (max {max_bytes} bytes)")
    return int(size)


def _selected_class(class_uid: str | None, tenant_id: str):
    uid = str(class_uid or "").strip()
    if not uid:
        return None
    found = next(
        (item for item in list_classes(tenant_id=tenant_id) if item.class_uid == uid),
        None,
    )
    if found is None:
        raise UploadClassNotFoundError("Nhãn không thuộc tổ chức hiện tại")
    return found


def _log_pipeline_config() -> None:
    try:
        live = int(getattr(settings, "augment_per_seq", 8))
        video = int(getattr(settings, "video_augment_per_seq", 0) or 0)
        logger.info(
            "[PIPELINE_CFG] seq_len=%s feature_dim=%s stride=%s aug_n=%s "
            "(AUG_PER_SEQ=%s VIDEO_AUG_PER_SEQ=%s) VIDEO_COMPLETENESS=%s",
            int(getattr(settings, "seq_len", 60)),
            int(getattr(settings, "feature_dim", 126)),
            int(getattr(settings, "stride", 2)),
            video if video > 0 else live,
            live,
            video,
            float(getattr(settings, "video_completeness_threshold", 0.8)),
        )
    except Exception:
        pass


async def duplicate_upload_result(
    upload_uid: str | None,
    session_id: str | None,
) -> Dict[str, Any] | None:
    """Return the prior upload response for a valid idempotency key, if any."""
    if not upload_uid or not re.fullmatch(r"[a-fA-F0-9]{8,64}", upload_uid):
        return None
    uid = upload_uid.lower()
    existing = await asyncio.to_thread(find_raw_upload, uid)
    if not existing:
        return None
    logger.info("[UPLOAD][video] duplicate upload_uid=%s", uid)
    return {
        "success": True,
        "id": uid,
        "session_id": existing.get("session_id") or session_id or uuid.uuid4().hex,
        "upload_uid": uid,
        "storage_url": existing.get("storage_url") or existing.get("local_path", ""),
        "message": "already uploaded (duplicate ignored)",
        "duplicate": True,
    }


async def store_raw_video(
    *,
    file,
    user: str,
    label: str,
    language: str,
    dialect: str,
    class_uid: str | None,
    visibility: str,
    session_id: str | None,
    upload_uid: str | None,
    tenant_id: str,
    current_user: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist one video and enqueue processing with side effects in safe order."""
    started_at = time.time()
    session_id = session_id or uuid.uuid4().hex
    duplicate = await duplicate_upload_result(upload_uid, session_id)
    if duplicate is not None:
        return duplicate
    if upload_uid and re.fullmatch(r"[a-fA-F0-9]{8,64}", upload_uid):
        upload_uid = upload_uid.lower()
    else:
        upload_uid = uuid.uuid4().hex[:8]

    logger.info(
        "[UPLOAD][video] user=%s label=%s lang=%s dialect=%s filename=%s session=%s",
        user or current_user.get("username", ""), label, language, dialect,
        getattr(file, "filename", ""), session_id,
    )
    _log_pipeline_config()
    if not looks_like_video(peek_head(file.file)):
        raise InvalidVideoFormatError(
            "Tep khong phai dinh dang video duoc ho tro (MP4/MOV/WebM/MKV/AVI)."
        )

    max_mb = int(getattr(settings, "max_upload_mb", 1024))
    max_bytes = max_mb * 1024 * 1024 if max_mb > 0 else 0
    upload_size = _measure_upload_size(file.file, max_bytes=max_bytes)
    reservation = storage_quota.reserve(tenant_of(current_user), upload_size)
    settled = False
    try:
        class_meta = await asyncio.to_thread(_selected_class, class_uid, tenant_id)
        if class_meta is None:
            class_meta = await asyncio.to_thread(
                get_or_register_class,
                label_original=label,
                language=language,
                dialect=dialect or "",
            )
        else:
            label = class_meta.label_original
            language = class_meta.language
            dialect = class_meta.dialect

        original_filename = _safe_path_part(getattr(file, "filename", None), "upload.mp4")
        local_path = raw_class_dir(class_meta) / f"{upload_uid}_{original_filename}"
        storage_key = local_path.relative_to(settings.dataset_root).as_posix()
        bytes_written, local_path_str = await asyncio.to_thread(
            save_upload_with_limit,
            file.file,
            local_path,
            max_bytes=max_bytes,
        )
        await asyncio.to_thread(
            storage_quota.settle,
            reservation,
            bytes_written,
            discard=lambda: local_path.unlink(missing_ok=True),
        )
        settled = True
    finally:
        if not settled:
            storage_quota.release(reservation)

    created_at = now_str()
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
        "tenant_id": class_meta.tenant_id,
        "visibility": visibility,
        "original_filename": original_filename,
        "local_path": local_path_str,
        "storage_key": storage_key,
        "storage_url": local_path_str,
        "created_at": created_at,
        "updated_at": created_at,
    }
    try:
        await asyncio.to_thread(append_raw_upload_row, raw_upload_row)
    except Exception as exc:
        logger.warning("[UPLOAD][video] raw upload CSV metadata failed: %s", exc)
    try:
        from app.storage.metadata_db import insert_raw_upload

        await asyncio.to_thread(
            insert_raw_upload,
            {**raw_upload_row, "auth_user_id": current_user["id"]},
        )
    except Exception as exc:
        logger.warning(
            "[UPLOAD][video] raw upload DB metadata failed for %s: %s",
            upload_uid,
            exc,
        )

    gdrive_mirror = "disabled"
    if getattr(settings, "use_google_drive", False):
        try:
            from app.export_tasks import upload_raw_video_to_gdrive_task

            upload_raw_video_to_gdrive_task.delay(
                upload_uid=upload_uid,
                local_path=local_path_str,
                storage_key=storage_key,
                content_type=file.content_type or "application/octet-stream",
                tenant_id=class_meta.tenant_id,
            )
            gdrive_mirror = "queued"
        except Exception as exc:
            gdrive_mirror = "dispatch_failed"
            logger.warning("[UPLOAD][video] Drive dispatch failed; local copy kept: %s", exc)

    processing = enqueue_video_processing(
        raw_upload_row,
        triggered_by=str(current_user.get("id") or ""),
    )
    logger.info(
        "[UPLOAD][video] path=%s bytes_received=%s bytes_written=%s mirror=%s elapsed=%.3fs",
        local_path_str,
        upload_size,
        bytes_written,
        gdrive_mirror,
        time.time() - started_at,
    )
    return {
        "success": True,
        "id": upload_uid,
        "session_id": session_id,
        "upload_uid": upload_uid,
        "storage_url": local_path_str,
        "gdrive_mirror": gdrive_mirror,
        "job_id": processing.get("job_id"),
        "processing": processing.get("status"),
        "message": "raw video uploaded",
    }
