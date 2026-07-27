import logging
from celery import Celery
from celery.signals import task_prerun, task_postrun, worker_ready, setup_logging
from app.config import settings
from app.mem_utils import release_memory
from app.logging_config import configure_logging
import structlog
from asgi_correlation_id import correlation_id

@setup_logging.connect
def config_loggers(*args, **kwargs):
    configure_logging()

@task_prerun.connect
def setup_structlog_context(task_id, task, *args, **kwargs):
    # Retrieve request_id from kwargs if it was passed by the API
    # otherwise fallback to task_id
    req_id = kwargs.get("kwargs", {}).get("request_id", task_id)
    correlation_id.set(req_id)
    structlog.contextvars.bind_contextvars(
        task_id=task_id,
        task_name=task.name
    )

@task_postrun.connect
def clear_structlog_context(*args, **kwargs):
    structlog.contextvars.clear_contextvars()
    correlation_id.set(None)

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
    # Integrity safety-net: re-add any active Postgres sample missing from
    # samples.csv (append-only; heals the rare append-vs-catalog-rewrite race).
    "reconcile-samples-csv-every-5min": {
        "task": "app.export_tasks.reconcile_samples_csv_task",
        "schedule": 300.0,
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

# Optional periodic Drive->local pull: restores any samples/raw uploads whose
# local file is missing (fresh deploy, failed download, or another node added
# data to the shared DB). Disabled by default; set DRIVE_PULL_INTERVAL_MINUTES.
if settings.use_google_drive and int(getattr(settings, "drive_pull_interval_hours", 0)) > 0:
    beat_schedule["pull-missing-files-from-drive"] = {
        "task": "app.sync_tasks.download_missing_files_to_local",
        "schedule": float(settings.drive_pull_interval_hours) * 3600.0,
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
    # ---- Broker/result resilience (Redis) ----
    # A Redis restart/recreate (deploy, config change) takes a few seconds. These
    # make Celery ride over that blip instead of erroring: retry the broker
    # connection at startup AND at runtime, keep TCP keepalive on so dead sockets
    # are detected, and periodically health-check the connection. This is the
    # main defense against the sporadic "redis down" the users were seeing.
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=None,  # never give up reconnecting
    broker_transport_options={
        "socket_keepalive": True,
        "retry_on_timeout": True,
        "health_check_interval": 30,
        # Re-queue a task if the worker dies mid-run without acking (default 1h).
        "visibility_timeout": 3600,
    },
    result_backend_transport_options={
        "retry_on_timeout": True,
        "health_check_interval": 30,
    },
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


@worker_ready.connect
def _start_resource_monitor(**_kwargs):
    """Launch the GPU sampler once the worker is up.

    Fires in every worker's MainProcess (survives child recycling). Self-gates:
    on the CPU-only video worker nvidia-smi is absent, so it no-ops — only the
    GPU trainer actually samples and publishes to Redis.
    """
    try:
        from app.monitoring import start_gpu_monitor

        start_gpu_monitor()
    except Exception:  # monitoring must never break the worker
        logger.exception("[MONITOR] failed to start GPU sampler")

# Import tasks to register them with Celery
from app import tasks  # noqa: F401, E402
from app import export_tasks  # noqa: F401, E402
from app import training_tasks  # noqa: F401, E402
from app import sync_tasks  # noqa: F401, E402
from app import preview_tasks  # noqa: F401, E402
