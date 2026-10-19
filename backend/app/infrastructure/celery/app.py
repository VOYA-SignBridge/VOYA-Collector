"""Construction and configuration of the process-wide Celery application."""

from celery import Celery

from app.config import settings
from app.infrastructure.celery.schedules import build_beat_schedule

beat_schedule = build_beat_schedule(settings)

celery_app = Celery(
    "sign_dataset",
    broker=settings.broker_url,
    backend=settings.result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    beat_schedule=beat_schedule,
    worker_max_tasks_per_child=int(settings.worker_max_tasks_per_child),
    worker_max_memory_per_child=int(settings.worker_max_memory_per_child_kb),
    worker_prefetch_multiplier=1,
)
