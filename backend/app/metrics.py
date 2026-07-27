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

@router.get("/metrics")
async def metrics():
    # Gather data from the existing collect_resources logic
    res = await asyncio.to_thread(collect_resources)
    
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
            logger.error("Hardware disconnected or not found", extra={"resource": "gpu", "details": "Nvidia GPU is missing or unreadable."})
            hardware_error.labels(resource="gpu").set(1)
        else:
            hardware_error.labels(resource="gpu").set(0)

    data = generate_latest()
    return PlainTextResponse(data, media_type=CONTENT_TYPE_LATEST)
