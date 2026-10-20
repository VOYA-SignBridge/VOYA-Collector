"""Compatibility entrypoint used by Docker and Celery CLI commands."""

from app.infrastructure.celery.app import beat_schedule, celery_app
from app.infrastructure.celery.registry import register_task_modules
from app.infrastructure.celery.signals import (
    release_memory_after_task as _release_memory_after_task,
    start_resource_monitor as _start_resource_monitor,
)
from app.infrastructure.celery.tenant import (
    TENANT_HEADER,
    clear_structlog_context,
    setup_structlog_context,
    stamp_tenant_on_task,
)

register_task_modules()

__all__ = [
    "beat_schedule",
    "celery_app",
    "TENANT_HEADER",
    "stamp_tenant_on_task",
    "setup_structlog_context",
    "clear_structlog_context",
]
