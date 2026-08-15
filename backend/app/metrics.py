from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Gauge, Counter, Histogram
from app.monitoring import collect_resources
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Define Prometheus metrics
cpu_usage = Gauge('voya_cpu_usage_percent', 'Host CPU Usage Percent')
ram_used = Gauge('voya_ram_used_mb', 'Host RAM Used in MB')
ram_total = Gauge('voya_ram_total_mb', 'Host RAM Total in MB')
disk_used = Gauge('voya_disk_used_gb', 'Dataset Disk Used in GB')
disk_total = Gauge('voya_disk_total_gb', 'Dataset Disk Total in GB')
gpu_usage = Gauge('voya_gpu_usage_percent', 'GPU Usage Percent')
gpu_vram_used = Gauge('voya_gpu_vram_used_mb', 'GPU VRAM Used in MB')
hardware_error = Gauge('voya_hardware_error', '1 if there is a non-ignored hardware error, 0 otherwise', ['resource'])

http_requests_total = Counter('http_requests_total', 'Total HTTP requests', ['method', 'status', 'path'])
http_request_duration_seconds = Histogram('http_request_duration_seconds', 'HTTP request duration in seconds', ['method', 'status', 'path'], buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0))
# Labelled by method only: the concurrency gauge brackets the request, before the
# matched route (path) is known, so adding a path label there would be unbounded.
http_requests_in_progress = Gauge('http_requests_in_progress', 'Concurrent HTTP requests in progress', ['method'])

# Dependency liveness (scraped from backend:8000 — no separate exporter needed).
# 1 = reachable, 0 = check failed. Lets Grafana/Prometheus alert on Redis or
# Postgres going away even though only the backend is a scrape target.
redis_up = Gauge('voya_redis_up', '1 if Redis (Celery broker) answered PING, else 0')
postgres_up = Gauge('voya_postgres_up', '1 if Postgres answered SELECT 1, else 0')

# System-caused training failures (infra: broker/trainer/timeout/resource) — the
# ones escalated to admins. Labelled by where it broke. Grafana can alert on the
# rate of this. (User DATA failures are deliberately NOT counted here.)
training_system_failures_total = Counter(
    'voya_training_system_failures_total',
    'Training jobs that failed due to a system/infra problem (escalated to admins)',
    ['source'],
)

# --------------------------------------------------------------------------- per-tenant
#
# Cho tới v4, /metrics chỉ nói về MÁY CHỦ: CPU, RAM, đĩa, GPU. Không nhãn nào
# cho biết tenant nào đang tiêu chỗ đó, nên câu hỏi "tháng này trường B dùng
# bao nhiêu" không có chỗ nào trả lời được.
#
# Vì sao có trần số nhãn
# ----------------------
# Prometheus tính chi phí theo CHUỖI THỜI GIAN, và mỗi tenant nhân số chuỗi
# lên: bốn chỉ số × N tenant. Với hai mươi tenant thì không sao; với hai nghìn
# tenant tự đăng ký thì đây là cách làm nổ Prometheus, và đúng loại lỗi mà
# docs/06-operations/OBSERVABILITY_PLAN.md đã cảnh báo về promtail.
#
# Phần vượt trần được GỘP vào nhãn `_other` chứ không bị bỏ: tổng toàn nền tảng
# vẫn cộng ra đúng, chỉ mất phân giải ở phần đuôi. Bỏ hẳn thì biểu đồ tổng sẽ
# im lặng nói dối, và đó là kiểu sai tệ nhất trong một hệ đo lường.
tenant_samples_total = Gauge(
    'voya_tenant_samples_total', 'Số mẫu đang có của một tenant', ['tenant']
)
tenant_storage_mb = Gauge(
    'voya_tenant_storage_mb', 'Dung lượng đĩa một tenant đang chiếm (MB)', ['tenant']
)
tenant_training_seconds_30d = Gauge(
    'voya_tenant_training_seconds_30d', 'Giây huấn luyện của một tenant trong 30 ngày', ['tenant']
)
tenant_members_total = Gauge(
    'voya_tenant_members_total', 'Số thành viên của một tenant', ['tenant']
)


# ----------------------------------------------------------------- nhật ký kiểm toán
#
# Ba chỉ số cho hai kiểu hỏng khác nhau, và chúng không thay được nhau.
#
# `audit_write_failures_total` bắt lần ghi NÉM LỖI. `audit.record` cố ý nuốt
# mọi ngoại lệ — nó không được phép làm hỏng thao tác mà nó đang ghi lại — nên
# cho tới nay lần hỏng đó chỉ để lại một dòng `[AUDIT-FAIL]` trong nhật ký ứng
# dụng, tức là chỉ tìm ra khi có người đi tìm.
#
# `audit_log_age_seconds` bắt kiểu hỏng NGUY HIỂM HƠN: đường ghi biến mất mà
# không ném gì cả. Không có ngoại lệ nào để đếm, không có dòng log nào để đọc
# — chỉ có một cái sổ ngừng dày lên. Bộ đếm ở trên mù hoàn toàn với nó.
#
# `audit_log_entries_1h` là con số dùng để nhìn, không phải để báo động: nó cho
# biết "yên tĩnh" nghĩa là gì trên bản triển khai này trước khi ai đó chọn
# ngưỡng cho hai chỉ số kia.
audit_write_failures_total = Counter(
    'voya_audit_write_failures_total',
    'Số lần ghi một dòng kiểm toán thất bại (đã ghi [AUDIT-FAIL] vào log)',
)
audit_log_age_seconds = Gauge(
    'voya_audit_log_age_seconds',
    'Số giây kể từ dòng kiểm toán gần nhất; -1 nếu sổ rỗng hoặc không đọc được',
)
audit_log_entries_1h = Gauge(
    'voya_audit_log_entries_1h',
    'Số dòng kiểm toán ghi trong một giờ qua; -1 nếu không đọc được',
)

# --------------------------------------------------------------------------
# Phân quyền — shadow mode
#
# Chỉ số này là ĐIỀU KIỆN DỪNG để chuyển AUTHZ_MODE từ `shadow` sang `casbin`,
# nên nó tách nhãn theo `kind` chứ không gộp thành một con số "số lần lệch":
#
#   deny_to_allow  hệ cũ từ chối, Casbin cho qua. Chuyển chế độ sẽ MỞ RỘNG
#                  quyền của ai đó. Phải về 0 trước khi chuyển. CẢNH BÁO.
#   allow_to_deny  hệ cũ cho qua, Casbin từ chối. Chuyển chế độ sẽ làm hẹp
#                  lại — thường là thiếu assignment chưa backfill. Cũng phải
#                  về 0, nhưng nó hỏng theo hướng an toàn.
#   error          không đánh giá được Casbin (policy chưa nạp, lỗi enforcer).
#                  Ở chế độ `casbin` thì đây sẽ là 403; ở shadow thì vô hại.
#
# Gộp ba loại vào một số sẽ làm cái nguy hiểm nhất chìm trong cái vô hại nhất.
authz_shadow_mismatch = Counter(
    'voya_authz_shadow_mismatch_total',
    'Số lần quyết định phân quyền cũ và Casbin bất đồng, theo loại và quyền',
    ['kind', 'permission'],
)
authz_policy_generation = Gauge(
    'voya_authz_policy_generation',
    'Thế hệ policy Casbin đang nạp trong tiến trình này; 0 nghĩa là chưa nạp',
)
authz_policy_age_seconds = Gauge(
    'voya_authz_policy_age_seconds',
    'Số giây kể từ lần nạp policy gần nhất; -1 nếu chưa nạp lần nào',
)


def _refresh_audit_gauges() -> None:
    """Nạp lại hai đồng hồ kiểm toán. Đồng bộ — gọi trong thread.

    Hai câu truy vấn gộp trên một bảng có chỉ mục theo `created_at`, ở nhịp
    Prometheus 15 giây. Rẻ hơn hẳn phần theo tenant ngay bên trên, vốn đọc cả
    một bảng gộp.
    """
    from app import audit

    audit_log_age_seconds.set(audit.seconds_since_last_entry())
    audit_log_entries_1h.set(audit.count_since(3600))


def _refresh_tenant_gauges() -> None:
    """Nạp lại các chỉ số theo tenant từ bảng gộp. Chạy đồng bộ, gọi trong thread.

    Đọc `tenant_usage_daily` chứ không đếm lại trên bảng nguồn: /metrics bị
    Prometheus gọi mỗi 15 giây, và bốn lượt `count(*)` cho mỗi tenant ở nhịp đó
    sẽ biến chính hệ đo lường thành thứ nặng nhất trên cơ sở dữ liệu.
    """
    from app.config import settings
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope
    from app.usage import platform_totals

    try:
        rows = platform_totals(days=30)
        with system_scope("metrics: member counts per tenant"):
            members = {
                r["tenant_id"]: int(r["n"])
                for r in _fetch_all(
                    "SELECT tenant_id, count(*) AS n FROM tenant_members GROUP BY tenant_id"
                )
            }
    except Exception as exc:
        logger.warning("[METRICS] không nạp được số liệu theo tenant: %s", type(exc).__name__)
        return

    cap = max(1, int(settings.metrics_max_tenant_labels))
    # `platform_totals` đã sắp theo số mẫu giảm dần, nên phần bị gộp luôn là
    # những tenant nhỏ nhất — chỗ mất phân giải ít gây tiếc nhất.
    head, tail = rows[:cap], rows[cap:]

    for gauge in (tenant_samples_total, tenant_storage_mb,
                  tenant_training_seconds_30d, tenant_members_total):
        # Xoá hết trước khi ghi lại: một tenant bị xoá phải BIẾN MẤT khỏi
        # /metrics, không đứng lại mãi ở giá trị cuối cùng nó từng có.
        gauge.clear()

    for row in head:
        tenant = row["tenant_id"]
        tenant_samples_total.labels(tenant=tenant).set(row["samples"])
        tenant_storage_mb.labels(tenant=tenant).set(row["storage_mb"])
        tenant_training_seconds_30d.labels(tenant=tenant).set(row["training_seconds"])
        tenant_members_total.labels(tenant=tenant).set(members.get(tenant, 0))

    if tail:
        tenant_samples_total.labels(tenant="_other").set(sum(r["samples"] for r in tail))
        tenant_storage_mb.labels(tenant="_other").set(sum(r["storage_mb"] for r in tail))
        tenant_training_seconds_30d.labels(tenant="_other").set(
            sum(r["training_seconds"] for r in tail)
        )
        tenant_members_total.labels(tenant="_other").set(
            sum(members.get(r["tenant_id"], 0) for r in tail)
        )


def _refresh_authz_gauges() -> None:
    """Tuổi và thế hệ của policy Casbin trong TIẾN TRÌNH NÀY.

    Đồng bộ và không chạm cơ sở dữ liệu — nó chỉ đọc trạng thái trong bộ nhớ,
    nên không cần `to_thread` như hai hàm trên.

    Tuổi phải tính lúc QUÉT chứ không lúc nạp: một `set(0)` ở thời điểm nạp cho
    ra một đồng hồ đứng yên ở 0 mãi mãi, tức là một chỉ số nói "policy vừa mới
    tinh" kể cả khi tiến trình đã chạy ba ngày không nạp lại. Đó là loại chỉ số
    tệ hơn không có: nó khiến cảnh báo "policy quá cũ" không bao giờ kêu.

    `-1` khi chưa nạp lần nào, cùng quy ước với `audit_log_age_seconds`: một số
    âm là tín hiệu "đừng suy luận từ giá trị này", khác hẳn với 0.
    """
    try:
        from app.config import settings

        if getattr(settings, "authz_mode", "shadow") == "legacy":
            # Casbin cố ý không chạy. Không phát ra số nào có thể đọc nhầm
            # thành "policy đã cũ".
            authz_policy_generation.set(0)
            authz_policy_age_seconds.set(-1)
            return

        from app.authorization import enforcer as authz_enforcer

        state = authz_enforcer.status()
        authz_policy_generation.set(state["generation"])
        age = state["age_seconds"]
        authz_policy_age_seconds.set(age if age is not None else -1)
    except Exception:
        authz_policy_age_seconds.set(-1)


@router.get("/metrics")
async def metrics():
    # Gather data from the existing collect_resources logic
    res = await asyncio.to_thread(collect_resources)
    await asyncio.to_thread(_refresh_tenant_gauges)
    await asyncio.to_thread(_refresh_audit_gauges)
    _refresh_authz_gauges()

    # Update Gauges
    host = res.get("host", {})
    if host:
        cpu_usage.set(host.get("cpu_pct", 0))
        ram_used.set(host.get("ram_used_mb", 0))
        ram_total.set(host.get("ram_total_mb", 0))

    disk = res.get("disk", {})
    if disk and disk.get("available"):
        disk_used.set(disk.get("used_gb", 0))
        disk_total.set(disk.get("total_gb", 0))
        hardware_error.labels(resource="disk").set(0)
    else:
        disk_used.set(0)
        disk_total.set(0)
        if disk and not disk.get("ignored"):
            logger.error("Hardware disconnected or not found", extra={"resource": "disk", "details": "Dataset volume is unavailable."})
            hardware_error.labels(resource="disk").set(1)
        else:
            hardware_error.labels(resource="disk").set(0)
        
    # Dependency liveness — reuse the health router's probes (off the event loop).
    async def _probe(check) -> int:
        try:
            await asyncio.to_thread(check)
            return 1
        except Exception:
            return 0

    from app.routers.health import _check_redis, _check_postgres
    redis_up.set(await _probe(_check_redis))
    postgres_up.set(await _probe(_check_postgres))

    gpu = res.get("gpu", {})
    if gpu and gpu.get("available"):
        gpu_usage.set(gpu.get("util_pct", 0))
        gpu_vram_used.set(gpu.get("vram_used_mb", 0))
        hardware_error.labels(resource="gpu").set(0)
    else:
        gpu_usage.set(0)
        gpu_vram_used.set(0)
        if gpu and not gpu.get("ignored"):
            # `details` phải nói được VIỆC CẦN LÀM, không chỉ nói "hỏng". Câu cũ
            # là "Nvidia GPU is missing or unreadable" cho mọi nguyên nhân, nên
            # ngày 2026-08-09 nó gửi đi một lá thư bảo đi tìm cái card đang nằm
            # yên trong máy — cái sai thật là stack được dựng thiếu overlay GPU.
            from app.monitoring import GPU_ABSENCE_HINTS

            reason = str(gpu.get("reason") or "unknown")
            logger.error(
                "Hardware disconnected or not found",
                extra={"resource": "gpu",
                       "reason": reason,
                       "details": gpu.get("hint")
                       or GPU_ABSENCE_HINTS.get(reason, "Khong ro nguyen nhan.")},
            )
            hardware_error.labels(resource="gpu").set(1)
        else:
            hardware_error.labels(resource="gpu").set(0)

    data = generate_latest()
    return PlainTextResponse(data, media_type=CONTENT_TYPE_LATEST)
