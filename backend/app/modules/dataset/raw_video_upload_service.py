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
from app.modules.dataset.catalog import get_or_register_class
from app.modules.dataset.raw_uploads import append_raw_upload_row, find_raw_upload, now_str

logger = logging.getLogger("upload.video")


class UploadReadError(ValueError):
    pass


class UploadTooLargeError(ValueError):
    pass


def _safe_path_part(value: str | None, fallback: str) -> str:
    text = str(value or fallback).strip() or fallback
    text = Path(text).name.strip() or fallback
    return "".join(character if character.isalnum() or character in " ._-" else "_" for character in text)


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


async def store_raw_video(
    *,
    file,
    user: str,
    label: str,
    language: str,
    dialect: str,
    session_id: str | None,
    upload_uid: str | None,
    current_user: Dict[str, Any],
    save_upload,
    normalize_fields,
    find_existing=find_raw_upload,
) -> Dict[str, Any]:
    """Idempotently store one video and record its catalog metadata."""
    started_at = time.time()
    session_id = session_id or uuid.uuid4().hex
    if upload_uid and re.fullmatch(r"[a-fA-F0-9]{8,64}", upload_uid):
        upload_uid = upload_uid.lower()
        existing = await asyncio.to_thread(find_existing, upload_uid)
        if existing:
            logger.info("[UPLOAD][video] duplicate upload_uid=%s", upload_uid)
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

    label, language, dialect = normalize_fields(label, language, dialect)
    class_meta = await asyncio.to_thread(
        get_or_register_class,
        label_original=label,
        language=language,
        dialect=dialect or "",
    )
    max_mb = int(getattr(settings, "max_upload_mb", 1024))
    max_bytes = max_mb * 1024 * 1024 if max_mb > 0 else 0
    upload_size = _measure_upload_size(file.file, max_bytes=max_bytes)
    original_filename = _safe_path_part(getattr(file, "filename", None), "upload.mp4")
    raw_dir = (
        settings.dataset_root
        / "raw_videos"
        / class_meta.language
        / class_meta.dialect
        / class_meta.folder_name()
    )
    local_path = raw_dir / f"{upload_uid}_{original_filename}"
    storage_key = local_path.relative_to(settings.dataset_root).as_posix()
    bytes_written, local_path_str = await asyncio.to_thread(
        save_upload,
        file.file,
        local_path,
        max_bytes=max_bytes,
    )

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
        if getattr(settings, "debug_logging", False):
            logger.debug("[UPLOAD][video] raw upload DB metadata failed: %s", exc)

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
        except Exception as exc:
            gdrive_mirror = "dispatch_failed"
            logger.warning("[UPLOAD][video] Drive dispatch failed; local copy kept: %s", exc)

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
        "message": "raw video uploaded",
    }
