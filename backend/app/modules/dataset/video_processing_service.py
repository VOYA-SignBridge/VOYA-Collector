"""Queue feature extraction for previously stored raw videos."""

from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any, Dict

from app.modules.dataset.raw_uploads import find_raw_upload, find_raw_uploads_by_class

_UPLOAD_UID_PATTERN = re.compile(r"[a-fA-F0-9]{8,64}")


class ProcessingRequestError(ValueError):
    pass


class RawUploadsNotFoundError(LookupError):
    pass


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
        user_id=row.get("user_id", "") or triggered_by,
        class_uid=row.get("class_uid", "") or "",
        visibility=row.get("visibility", "private") or "private",
    )
    return {"upload_uid": upload_uid, "job_id": task.id, "status": "queued"}


async def enqueue_uploaded_videos(
    payload: dict,
    *,
    triggered_by: str,
    find_one=find_raw_upload,
    find_by_class=find_raw_uploads_by_class,
    enqueue=enqueue_video_processing,
) -> Dict[str, Any]:
    """Resolve a class/single/batch request and enqueue every valid raw upload."""
    class_uid = str(payload.get("class_uid", "") or "").strip()
    rows: list[Dict[str, Any]] = []
    if class_uid:
        rows = await asyncio.to_thread(find_by_class, class_uid)
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
            if not row:
                results.append({"upload_uid": upload_uid, "status": "not_found"})
                continue
            results.append(enqueue(row, triggered_by))

    queued = sum(1 for result in results if result.get("status") == "queued")
    return {"success": True, "queued": queued, "total": len(results), "results": results}
