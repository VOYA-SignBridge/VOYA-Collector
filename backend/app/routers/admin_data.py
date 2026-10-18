"""Administrative dataset reporting and local-file synchronization routes."""

from collections import Counter
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app import activity
from app.modules.identity import require_admin
from app.sync_tasks import download_missing_files_to_local

router = APIRouter()


@router.get("/data-report")
def get_data_report(current_user: Dict[str, Any] = Depends(require_admin)):
    """Return dataset totals, breakdowns, contributors, and recent samples."""
    from app.dataset_manager import list_classes
    from app.dataset_samples import list_samples

    metas = list_classes()
    samples = list_samples()

    label_counts: Counter = Counter()
    region_counts: Counter = Counter()
    source_counts: Counter = Counter()
    contributor_counts: Counter = Counter()
    for sample in samples:
        label_counts[(sample.get("label_original") or sample.get("slug") or "?").strip() or "?"] += 1
        region_counts[(sample.get("dialect") or "").strip() or "khác"] += 1
        source_counts[(sample.get("source_type") or "").strip() or "khác"] += 1
        user_id = (sample.get("user_id") or "").strip()
        if user_id:
            contributor_counts[user_id] += 1

    regions = {(getattr(meta, "dialect", "") or "").strip() for meta in metas}
    regions.discard("")

    top_ids = [user_id for user_id, _ in contributor_counts.most_common(10)]
    user_map = activity._resolve_usernames(set(top_ids))
    top_contributors = [
        {
            "user_id": user_id,
            "username": (user_map.get(user_id) or {}).get("username") or user_id[:8],
            "count": count,
        }
        for user_id, count in contributor_counts.most_common(10)
    ]

    recent = sorted(
        samples,
        key=lambda sample: str(sample.get("created_at") or ""),
        reverse=True,
    )[:12]
    recent_output = [
        {
            "label": sample.get("label_original") or sample.get("slug"),
            "dialect": sample.get("dialect"),
            "source": sample.get("source_type"),
            "created_at": str(sample.get("created_at") or ""),
        }
        for sample in recent
    ]

    return {
        "labels_count": len(metas),
        "total_samples": len(samples),
        "contributors_count": len(contributor_counts),
        "regions_count": len(regions),
        "top_labels": [
            {"label": label, "count": count}
            for label, count in label_counts.most_common(12)
        ],
        "by_region": [
            {"region": region, "count": count}
            for region, count in region_counts.most_common()
        ],
        "by_source": [
            {"source": source, "count": count}
            for source, count in source_counts.most_common()
        ],
        "top_contributors": top_contributors,
        "recent": recent_output,
    }


@router.post("/sync-local")
def sync_local_files(current_user: Dict[str, Any] = Depends(require_admin)):
    """Start downloading missing feature and raw-video files from Google Drive."""
    task = download_missing_files_to_local.delay()
    return {
        "status": "success",
        "message": "Đã bắt đầu quá trình đồng bộ hóa file về server",
        "task_id": task.id,
    }


@router.get("/sync-status/{task_id}")
def get_sync_status(task_id: str, current_user: Dict[str, Any] = Depends(require_admin)):
    """Return the current Celery state for a local-file synchronization task."""
    from celery.result import AsyncResult

    task = AsyncResult(task_id)
    if task.state == "PENDING":
        return {
            "state": task.state,
            "current": 0,
            "total": 1,
            "status": "Pending...",
        }
    if task.state == "PROGRESS":
        return {
            "state": task.state,
            "current": task.info.get("current", 0),
            "total": task.info.get("total", 1),
            "downloaded": task.info.get("downloaded", 0),
            "skipped": task.info.get("skipped", 0),
            "errors": task.info.get("errors", 0),
        }
    if task.state == "SUCCESS":
        return {
            "state": task.state,
            "current": task.info.get("current", 1),
            "total": task.info.get("total", 1),
            "downloaded": task.info.get("downloaded", 0),
            "skipped": task.info.get("skipped", 0),
            "errors": task.info.get("errors", 0),
        }
    return {"state": task.state, "status": str(task.info)}
