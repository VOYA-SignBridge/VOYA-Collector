import logging
from celery import Celery
from celery.signals import task_postrun
from app.config import settings
from app.mem_utils import release_memory

logger = logging.getLogger(__name__)

# dùng Redis làm broker & backend từ environment variables
celery_app = Celery(
    "sign_dataset",
    broker=settings.broker_url,
    backend=settings.result_backend,
)

# Only schedule the Google Sheets export beats when a spreadsheet is
# actually configured — otherwise celery-beat fires them every 30s/60s
# forever just to have export_tasks.py no-op with "not_configured".
beat_schedule = {
    # Retention: prune old experimental checkpoints + job logs daily
    "cleanup-training-artifacts-daily": {
        "task": "app.training_tasks.cleanup_training_artifacts",
        "schedule": 86400.0,
    },
}

if str(settings.google_sheets_samples_spreadsheet_id).strip():
    beat_schedule["export-samples-every-30s"] = {
        "task": "app.export_tasks.export_samples_to_sheets",
        "schedule": 30.0,
    }

if str(settings.google_sheets_labels_spreadsheet_id).strip():
    beat_schedule["export-labels-every-60s"] = {
        "task": "app.export_tasks.export_labels_to_sheets",
        "schedule": 60.0,
    }

if settings.use_google_drive:
    # Keep the Drive CSV snapshots (samples.csv/labels.csv/raw_uploads.csv)
    # fresh — the per-append mirror was removed for quota reasons, and without
    # this beat the Drive copies go permanently stale.
    beat_schedule["mirror-catalog-csvs-every-5min"] = {
        "task": "app.export_tasks.mirror_catalog_csvs_to_drive",
        "schedule": 300.0,
    }

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    beat_schedule=beat_schedule,
    # ---- Memory hygiene ----
    # Recycle each prefork child after N tasks so native buffers held by
    # MediaPipe/OpenCV/NumPy are returned to the OS (chief defense against
    # the slow RSS creep of long-lived video workers).
    worker_max_tasks_per_child=int(settings.worker_max_tasks_per_child),
    # Hard ceiling per child (KB): child restarts if it exceeds this.
    worker_max_memory_per_child=int(settings.worker_max_memory_per_child_kb),
    # Don't let one worker hoard many heavy video jobs at once.
    worker_prefetch_multiplier=1,
)


@task_postrun.connect
def _release_memory_after_task(sender=None, **_kwargs):
    """Free heap + trim glibc arenas after every task completes.

    Runs in the child process right after each task, so RSS settles back
    down between video jobs instead of holding at the peak.
    """
    name = getattr(sender, "name", "task")
    try:
        release_memory(context=name)
    except Exception:  # never let cleanup break the worker
        logger.exception("[MEM] release_memory failed after %s", name)

# Import tasks to register them with Celery
from app import tasks  # noqa: F401, E402
from app import export_tasks  # noqa: F401, E402
from app import training_tasks  # noqa: F401, E402
from app import sync_tasks  # noqa: F401, E402
