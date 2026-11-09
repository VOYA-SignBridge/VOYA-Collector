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
    # Redis khởi động lại vài giây (cập nhật, đổi cấu hình) thì Celery đi qua
    # được thay vì báo lỗi: thử lại kết nối cả lúc khởi động lẫn lúc chạy, giữ
    # TCP keepalive, kiểm kết nối định kỳ. Đây là bản vá đợt "lỗi Redis lác đác".
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=None,
    broker_transport_options={
        "socket_keepalive": True,
        "retry_on_timeout": True,
        "health_check_interval": 30,
        # Worker chết giữa chừng mà chưa ack thì việc được xếp lại sau 1 giờ.
        "visibility_timeout": 3600,
    },
    result_backend_transport_options={
        "retry_on_timeout": True,
        "health_check_interval": 30,
    },
)

# Connect tenant-scope propagation signals for every celery_app user (web
# dispatcher and worker alike) — importing the module registers its
# before_task_publish / task_prerun / task_postrun handlers.
from app.infrastructure.celery import tenant as _tenant  # noqa: E402,F401
