"""Point-in-time snapshots of web-system dependencies and host resources."""

from __future__ import annotations

import logging
import shutil
from typing import Any, Dict, Optional

from app.config import settings
from app.infrastructure.redis.connection import get_redis_client

logger = logging.getLogger("monitoring")


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return value.isoformat()
    except Exception:
        return str(value)


def host_snapshot() -> Dict[str, Any]:
    try:
        import psutil
        per_core = psutil.cpu_percent(interval=0.15, percpu=True)
        cpu = round(sum(per_core) / len(per_core), 1) if per_core else 0.0
        vm = psutil.virtual_memory()
        return {
            "cpu_pct": cpu, "cpu_count": psutil.cpu_count(),
            "cpu_per_core": [round(value, 1) for value in per_core],
            "ram_used_mb": round((vm.total - vm.available) / 1e6, 1),
            "ram_total_mb": round(vm.total / 1e6, 1), "ram_pct": round(vm.percent, 1),
        }
    except Exception as exc:
        return {"error": str(exc)}


def redis_snapshot() -> Dict[str, Any]:
    client = get_redis_client()
    if client is None:
        return {"available": False}
    try:
        info = client.info("memory")
        used = int(info.get("used_memory", 0) or 0)
        max_memory = int(info.get("maxmemory", 0) or 0)
        return {
            "available": True, "used_mb": round(used / 1e6, 1),
            "maxmemory_mb": round(max_memory / 1e6, 1) if max_memory else 0.0,
            "used_pct": round(100.0 * used / max_memory, 1) if max_memory else 0.0,
        }
    except Exception:
        return {"available": False}


def disk_snapshot() -> Dict[str, Any]:
    try:
        usage = shutil.disk_usage(str(settings.dataset_root))
        return {
            "available": True, "total_gb": round(usage.total / 1e9, 2),
            "used_gb": round(usage.used / 1e9, 2), "free_gb": round(usage.free / 1e9, 2),
            "used_pct": round(100.0 * usage.used / usage.total, 1) if usage.total else 0.0,
            "mount": str(settings.dataset_root),
        }
    except OSError as exc:
        logger.debug("[MONITOR] disk_usage failed: %s", exc)
        return {"available": False, "reason": str(exc)}


def training_snapshot() -> Dict[str, Any]:
    try:
        from app.storage.metadata_db import list_training_jobs
        for job in list_training_jobs(limit=20):
            if str(job.get("status")) == "running":
                config = job.get("config") or {}
                return {
                    "active": True, "job_id": job.get("job_id"),
                    "model_type": job.get("model_type") or config.get("model_type"),
                    "current_epoch": int(job.get("current_epoch") or 0),
                    "total_epochs": int(job.get("total_epochs") or 0),
                    "started_at": _iso(job.get("started_at")),
                }
        return {"active": False}
    except Exception as exc:
        return {"active": False, "error": str(exc)}
