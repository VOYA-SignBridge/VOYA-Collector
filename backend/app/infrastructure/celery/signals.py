"""Worker lifecycle signal handlers."""

from __future__ import annotations

import logging

from celery.signals import setup_logging, task_failure, task_postrun, worker_ready

from app.infrastructure.celery.memory import release_memory

logger = logging.getLogger(__name__)


@setup_logging.connect
def config_loggers(*_args, **_kwargs) -> None:
    """Không để Celery tự cấu hình log: dùng log JSON chung để Loki đọc được nhãn."""
    from app.bootstrap.logging import configure_logging

    configure_logging()


@task_failure.connect
def audit_task_failure(sender=None, task_id=None, exception=None, **_kwargs) -> None:
    """Persist a final Celery failure under the owning tenant scope."""
    try:
        from contextlib import nullcontext

        from app import task_registry
        from app.modules.saas.tenant_context import (
            current_tenant,
            in_system_scope,
            system_scope,
            tenant_scope,
        )
        from app.modules.security import audit

        name = getattr(sender, "name", None) or "?"
        error = f"{type(exception).__name__}: {exception}" if exception else ""
        if current_tenant() or in_system_scope():
            scope = nullcontext()
        else:
            owner = task_registry.owners_of([str(task_id or "")]).get(
                str(task_id or "")
            )
            scope = (
                tenant_scope(owner)
                if owner
                else system_scope("task_failure in worker parent process")
            )
        with scope:
            audit.record(
                "task.failed",
                target_type="task",
                target_id=str(task_id or ""),
                detail={"name": name, "error": error[:300]},
            )
    except Exception as exc:  # pragma: no cover - audit must not break workers
        logger.warning(
            "[TASK-FAILURE] could not audit %s: %s",
            task_id,
            exc,
        )


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
