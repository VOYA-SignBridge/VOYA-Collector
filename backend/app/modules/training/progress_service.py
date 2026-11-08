"""Polling and event emission for training progress transports."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from app.modules.training.job_service import TERMINAL_STATUSES, _ensure_job_loaded, _metrics_from_db_rows

logger = logging.getLogger(__name__)


async def stream_job_progress(
    job_id: str,
    send_json: Callable[[dict[str, Any]], Awaitable[None]],
    *,
    ensure_job=_ensure_job_loaded,
    poll_interval: float = 2.0,
) -> None:
    """Poll durable job state and emit only new metrics/status changes."""
    from app.storage.metadata_db import list_training_metrics

    last_epoch = 0
    last_status = None
    while True:
        job_info = await ensure_job(job_id)
        if not job_info:
            return
        job = job_info["job"]
        try:
            rows = await asyncio.to_thread(list_training_metrics, job_id)
            for metric in _metrics_from_db_rows(rows):
                if metric.epoch > last_epoch:
                    await send_json({"type": "metric", "data": metric.dict()})
                    last_epoch = metric.epoch
        except Exception as exc:
            logger.warning("Progress metrics poll failed for %s: %s", job_id, exc)

        if job.status != last_status:
            await send_json({"type": "status", "data": job.dict()})
            last_status = job.status
        if job.status in TERMINAL_STATUSES:
            return
        await asyncio.sleep(poll_interval)
