"""Queue feature extraction for previously stored raw videos."""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from typing import Any, Callable, Dict

from app.modules.dataset.raw_uploads import find_raw_upload, find_raw_uploads_by_class
from app.modules.saas.tenancy import tenant_id_of

_UPLOAD_UID_PATTERN = re.compile(r"[a-fA-F0-9]{8,64}")
logger = logging.getLogger("upload.process")


class ProcessingRequestError(ValueError):
    pass


class RawUploadsNotFoundError(LookupError):
    pass


def in_request_tenant(row: Dict[str, Any], tenant_id: str) -> bool:
    """Do not disclose or reprocess a raw upload owned by another tenant."""
    return tenant_id_of(row) == tenant_id


def raw_upload_owner(upload_uid: str) -> str:
    """Return the authenticated owner recorded for the original upload."""
    if not upload_uid:
        return ""
    try:
        from app.storage.metadata_db import _fetch_all

        rows = _fetch_all(
            "SELECT auth_user_id FROM raw_uploads WHERE upload_uid = %s",
            (upload_uid,),
        )
        return str(rows[0]["auth_user_id"] or "") if rows else ""
    except Exception:
        return ""


def enqueue_video_processing(row: Dict[str, Any], triggered_by: str) -> Dict[str, Any]:
    """Enqueue one raw video, returning a per-item result instead of raising."""
    from app.tasks import enqueue_process_video

    upload_uid = str(row.get("upload_uid", "")).strip()
    video_path = (row.get("storage_url") or row.get("local_path") or "").strip()
    if not video_path:
        return {"upload_uid": upload_uid, "status": "no_file"}

    task = enqueue_process_video.delay(
        video_path=video_path,
        user=row.get("user_id", "") or "",
        label=row.get("label_original", "") or "",
        session_id=row.get("session_id", "") or uuid.uuid4().hex,
        dialect=row.get("dialect", "") or "common",
        language=row.get("language", "") or "vn",
        # Reprocessing must preserve the person who uploaded the sample. The
        # shared CSV has no auth_user_id column, so consult its database mirror.
        user_id=raw_upload_owner(upload_uid) or triggered_by,
        class_uid=row.get("class_uid", "") or "",
        visibility=row.get("visibility", "private") or "private",
    )
    return {"upload_uid": upload_uid, "job_id": task.id, "status": "queued"}


async def enqueue_uploaded_videos(
    payload: dict,
    *,
    triggered_by: str,
    tenant_id: str,
    find_one: Callable[[str], Dict[str, Any] | None] | None = None,
    find_by_class: Callable[[str], list[Dict[str, Any]]] | None = None,
    enqueue: Callable[[Dict[str, Any], str], Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Resolve a class/single/batch request and enqueue every valid raw upload."""
    find_one = find_one or find_raw_upload
    find_by_class = find_by_class or find_raw_uploads_by_class
    enqueue = enqueue or enqueue_video_processing
    class_uid = str(payload.get("class_uid", "") or "").strip()
    rows: list[Dict[str, Any]] = []
    if class_uid:
        rows = await asyncio.to_thread(find_by_class, class_uid)
        rows = [row for row in rows if in_request_tenant(row, tenant_id)]
        if not rows:
            raise RawUploadsNotFoundError(f"no raw uploads for class_uid: {class_uid}")
        results = [enqueue(row, triggered_by) for row in rows]
    else:
        upload_uids = payload.get("upload_uids")
        single = str(payload.get("upload_uid", "") or "").strip().lower()
        if single and not upload_uids:
            upload_uids = [single]
        if not upload_uids or not isinstance(upload_uids, list):
            raise ProcessingRequestError(
                "provide upload_uid, upload_uids[], or class_uid"
            )

        results = []
        for raw_uid in upload_uids:
            upload_uid = str(raw_uid).strip().lower()
            if not _UPLOAD_UID_PATTERN.fullmatch(upload_uid):
                results.append({"upload_uid": upload_uid, "status": "invalid_uid"})
                continue
            row = await asyncio.to_thread(find_one, upload_uid)
            if not row or not in_request_tenant(row, tenant_id):
                results.append({"upload_uid": upload_uid, "status": "not_found"})
                continue
            results.append(enqueue(row, triggered_by))

    queued = sum(1 for result in results if result.get("status") == "queued")
    logger.info(
        "[UPLOAD][process] triggered_by=%s queued=%s total=%s",
        triggered_by,
        queued,
        len(results),
    )
    return {"success": True, "queued": queued, "total": len(results), "results": results}
