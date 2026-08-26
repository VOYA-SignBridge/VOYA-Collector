import logging
from celery import Celery
from celery.signals import (
    before_task_publish, task_prerun, task_postrun, worker_ready, setup_logging,
)
from app.config import settings
from app.mem_utils import release_memory
from app.logging_config import configure_logging
from app.tenant_context import (
    clear_scope, current_tenant, enter_system_scope, enter_tenant_scope,
)
import structlog
from asgi_correlation_id import correlation_id

#: Message header carrying the tenant a task was dispatched for.
#: A header rather than a task argument on purpose: every one of the 40-odd
#: `.delay()` / `.apply_async()` call sites would otherwise need editing, and
#: the one that got missed would be a silent cross-tenant write rather than a
#: type error.
TENANT_HEADER = "voya_tenant"


@setup_logging.connect
def config_loggers(*args, **kwargs):
    configure_logging()


@before_task_publish.connect
def stamp_tenant_on_task(headers=None, **_kwargs):
    """Record which tenant asked for this task, at dispatch time.

    Dispatch is the only moment the answer is known. By the time the worker
    picks the message up, the request that caused it is long gone — which is
    why every task used to run as the platform regardless of who triggered it.

    Only a real tenant scope is stamped. Platform work (beat schedules, CLI,
    startup sync) is in system scope, `current_tenant()` returns None, and no
    header is added — so those tasks keep the behaviour they have always had.
    """
    tenant = current_tenant()
    if tenant and headers is not None:
        headers[TENANT_HEADER] = tenant


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
    # Tenant scope for the task body, in the one place a task added later
    # cannot forget it. Without any scope, row-level security shows the task
    # zero rows and the symptom is a job that reports success having done
    # nothing — see storage/rls.py.
    #
    # Two cases, and the narrower one wins:
    #
    #   header present  -> the task was dispatched from inside a request acting
    #                      for one tenant, so run as that tenant. Reads are
    #                      filtered and writes are refused for anyone else.
    #   header absent   -> platform work (beat, CLI, startup sync). System
    #                      scope, exactly as before this header existed.
    #
    # The header is written by our own backend, but it is still validated on
    # arrival: anyone able to forge it can already enqueue arbitrary tasks, so
    # this is not a trust boundary — it is a guard against a malformed value
    # silently becoming a GUC that matches no rows. Note also that a header can
    # only NARROW the scope; there is no value it can carry that grants system
    # scope, because system is what you get by not being a valid tenant.
    #
    # `platform_wide` overrides the header. Some tasks read whole tables to
    # build ONE artifact for the deployment — the Google Sheets exports are
    # dispatched from inside catalog mutations, i.e. from a tenant request, and
    # scoping them to that tenant would silently drop every other tenant's rows
    # from a spreadsheet that is shared. That failure is invisible: the export
    # succeeds, it is just short.
    if getattr(task, "platform_wide", False):
        enter_system_scope(f"celery:{task.name} (platform_wide)")
        return
    tenant = getattr(task.request, TENANT_HEADER, None)
    if tenant and enter_tenant_scope(tenant):
        structlog.contextvars.bind_contextvars(tenant_id=tenant)
        return
    enter_system_scope(f"celery:{task.name}")

@task_postrun.connect
def clear_structlog_context(*args, **kwargs):
    structlog.contextvars.clear_contextvars()
    correlation_id.set(None)
    # Must run even when the task raised, or a prefork child keeps system scope
    # for whatever it picks up next. Celery fires task_postrun on both paths.
    clear_scope()

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
    # --- mặt phẳng SaaS (v4) ---
    #
    # Gộp số đo mỗi giờ chứ không mỗi ngày, dù nó gộp theo NGÀY: chạy hàng giờ
    # nghĩa là bảng điều khiển thấy được ngày HÔM NAY đang tăng dần, chứ không
    # phải chờ tới nửa đêm mới có số. Chạy lại cùng một ngày là không tốn gì —
    # mọi câu đều `ON CONFLICT DO UPDATE`.
    "rollup-usage-hourly": {
        "task": "app.saas_tasks.rollup_usage_daily",
        "schedule": 3600.0,
    },
    # Mỗi phút. Đây là độ trễ tối đa của một webhook, và một phút là ngưỡng mà
    # tích hợp còn cảm thấy "gần như tức thì" mà không biến hàng đợi thành một
    # vòng bận. Lần thử lại đầu tiên cũng cách một phút, nên hai nhịp khớp nhau.
    "deliver-webhooks-every-minute": {
        "task": "app.saas_tasks.deliver_webhooks",
        "schedule": 60.0,
    },
    "cleanup-saas-artifacts-daily": {
        "task": "app.saas_tasks.cleanup_saas_artifacts",
        "schedule": 86400.0,
    },
    # Bảng `refresh_tokens` chỉ lớn lên nếu không ai dọn: một dòng mỗi lần đăng
    # nhập VÀ một dòng mỗi lần xoay (~1 dòng/giờ cho mỗi người đang hoạt động).
    # Giữ lại 7 ngày sau khi hết hạn để chuỗi `replaced_by` còn dựng lại được
    # đường xoay khi phải điều tra một vụ tái sử dụng token.
    "cleanup-refresh-tokens-daily": {
        "task": "app.saas_tasks.cleanup_refresh_tokens",
        "schedule": 86400.0,
    },
    # Tồn đọng kênh hỗ trợ. Mỗi 30 phút, và con số đó đến từ chính ngưỡng: cảnh
    # báo nói "đã chờ quá 5 giờ", nên độ trễ phát hiện phải nhỏ hơn hẳn 5 giờ,
    # nếu không câu cảnh báo là một lời nói dối làm tròn. Nửa tiếng cho sai số
    # tối đa 10% — đủ để câu chữ trong thư vẫn đúng.
    #
    # Chạy thừa không tốn gì: hai truy vấn gộp, và khoảng lặng ở Redis giữ cho
    # thư không lặp lại (app/support_backlog.py :: RESEND_COOLDOWN_S).
    "support-backlog-every-30min": {
        "task": "app.saas_tasks.sweep_support_backlog",
        "schedule": 1800.0,
    },
    # Hạn mức dung lượng, lớp thứ ba. Bộ đếm được cập nhật đồng bộ ở mọi đường
    # ghi, nên lượt này KHÔNG phải cách usage được tính — nó là cách ta biết bộ
    # đếm đã trôi, và trôi bao nhiêu. Mỗi lần lệch là một dòng WARNING kèm hai
    # con số; im lặng sửa thì bộ đếm cứ trôi mãi mà không ai biết nguyên nhân.
    #
    # Mỗi ngày chứ không mỗi giờ: lượt này đi bộ toàn bộ cây tệp của mọi tenant.
    "reconcile-storage-quota-daily": {
        "task": "app.saas_tasks.reconcile_storage_quota",
        "schedule": 86400.0,
    },
}

# Vòng đời đăng ký: nhắc trước hạn, gia hạn, ân hạn, khoá mềm.
#
# Mỗi GIỜ chứ không mỗi ngày, và lý do là hành vi khi máy chủ nghỉ: một tác vụ
# chạy 24 giờ một lần mà trúng lúc worker đang khởi động lại thì lỡ nguyên một
# ngày, và "lỡ một ngày" ở đây nghĩa là một tổ chức đã hết ân hạn vẫn ghi được
# thêm 24 giờ, hoặc một thư nhắc "còn 1 ngày" tới sau khi đã hết hạn. Lượt quét
# là idempotent (mốc nhắc ghi vào `last_reminder_days`, kỳ hạn chỉ mở khi kỳ cũ
# đã qua), nên chạy thừa không tốn gì ngoài một truy vấn.
if settings.subscription_sweep_enabled:
    beat_schedule["subscription-sweep-hourly"] = {
        "task": "app.saas_tasks.sweep_subscriptions",
        "schedule": 3600.0,
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

    Nhận diện trainer bằng `-n trainer@%h` trong compose, không bằng biến môi
    trường mới: hai container chạy CÙNG MỘT ảnh và cùng một .env, nên biến môi
    trường phải thêm ở compose — đúng chỗ mà tên node đã nói rồi. Đoán sai chỉ
    làm mất ngọn đèn báo vắng mặt (xem monitoring._publish_absence_beacon),
    không ảnh hưởng gì tới việc chụp số liệu thật.
    """
    try:
        from app.monitoring import start_gpu_monitor

        sender = _kwargs.get("sender")
        node = str(getattr(sender, "hostname", "") or "")
        start_gpu_monitor(is_trainer=node.startswith("trainer@"))
    except Exception:  # monitoring must never break the worker
        logger.exception("[MONITOR] failed to start GPU sampler")

# Import tasks to register them with Celery
from app import tasks  # noqa: F401, E402
from app import export_tasks  # noqa: F401, E402
from app import training_tasks  # noqa: F401, E402
from app import sync_tasks  # noqa: F401, E402
from app import preview_tasks  # noqa: F401, E402
from app import saas_tasks  # noqa: F401, E402
