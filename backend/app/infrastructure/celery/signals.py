"""Worker lifecycle signal handlers."""

from __future__ import annotations

import logging

from celery.signals import task_postrun, worker_ready

from app.infrastructure.celery.memory import release_memory

logger = logging.getLogger(__name__)


@task_postrun.connect
def release_memory_after_task(sender=None, **_kwargs) -> None:
    """Return native buffers to the OS after a worker task completes."""
    name = getattr(sender, "name", "task")
    try:
        release_memory(context=name)
    except Exception:
        logger.exception("[MEM] release_memory failed after %s", name)


@worker_ready.connect
def start_resource_monitor(sender=None, **_kwargs) -> None:
    """Start the GPU sampler when this worker has compatible hardware."""
    try:
        from app.modules.monitoring.gpu import start_gpu_monitor

        hostname = str(getattr(sender, "hostname", "") or "")
        start_gpu_monitor(is_trainer=hostname.startswith("trainer@"))
    except Exception:
        logger.exception("[MONITOR] failed to start GPU sampler")
