"""Compatibility facade for operational monitoring.

New code belongs in :mod:`app.modules.monitoring`; existing imports from
``app.monitoring`` remain stable for the worker and admin router.
"""

from app.infrastructure.redis.connection import get_redis_client as _redis_client
from app.modules.monitoring.compose_config import (
    _parse_concurrency,
    _parse_mem_limit,
    _service_has_gpu,
    resource_config,
)
from app.modules.monitoring.gpu import (
    GPU_SAMPLE_INTERVAL,
    GPU_SNAPSHOT_KEY,
    GPU_SNAPSHOT_TTL,
    read_gpu_snapshot,
    sample_gpu,
    start_gpu_monitor,
)
from app.modules.monitoring.service import (
    CPU_ALERT_PCT,
    DISK_CRIT_PCT,
    DISK_WARN_PCT,
    GPU_LEAK_MB,
    RAM_ALERT_PCT,
    REDIS_ALERT_PCT,
    VRAM_ALERT_PCT,
    _build_alerts,
    collect_resources,
)
from app.modules.monitoring.snapshots import (
    disk_snapshot,
    host_snapshot,
    redis_snapshot,
    training_snapshot,
)

__all__ = [
    "collect_resources",
    "disk_snapshot",
    "host_snapshot",
    "read_gpu_snapshot",
    "redis_snapshot",
    "resource_config",
    "sample_gpu",
    "start_gpu_monitor",
    "training_snapshot",
]
