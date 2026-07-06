from celery import Celery
from app.config import settings

# dùng Redis làm broker & backend từ environment variables
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
    beat_schedule={
        "export-samples-every-30s": {
            "task": "app.export_tasks.export_samples_to_sheets",
            "schedule": 30.0,
        },
        "export-labels-every-60s": {
            "task": "app.export_tasks.export_labels_to_sheets",
            "schedule": 60.0,
        },
        # Retention: prune old experimental checkpoints + job logs daily
        "cleanup-training-artifacts-daily": {
            "task": "app.training_tasks.cleanup_training_artifacts",
            "schedule": 86400.0,
        },
    },
)

# Import tasks to register them with Celery
from app import tasks  # noqa: F401, E402
from app import export_tasks  # noqa: F401, E402
from app import training_tasks  # noqa: F401, E402
from app import sync_tasks  # noqa: F401, E402
