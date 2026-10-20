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

# Human-readable hints for why a GPU snapshot is absent (added in
# deploy_ctu_ver-2.2.1; consumed by app.infrastructure.observability.metrics). Kept on the facade so the
# legacy ``from app.monitoring import GPU_ABSENCE_HINTS`` import resolves.
GPU_ABSENCE_HINTS = {
    "no_device_in_container": (
        "Trainer đang chạy nhưng không được cấp thiết bị nào. Nếu máy chủ có card "
        "NVIDIA thì stack đã được dựng thiếu overlay GPU — chạy lại scripts/deploy.sh, "
        "nó tự dò card. Nếu máy chủ không có card thì đây là trạng thái đúng."
    ),
    "no_snapshot": (
        "Không container nào báo cáo GPU. Trainer có thể đã chết, hoặc đang chạy ảnh "
        "cũ chưa có ngọn đèn báo vắng mặt — kiểm tra trainer còn sống không trước khi "
        "kết luận về phần cứng."
    ),
    "redis_unavailable": "Không nối được Redis — đây là sự cố Redis, không phải sự cố GPU.",
    "redis_error": "Redis trả lời lỗi — đây là sự cố Redis, không phải sự cố GPU.",
    "parse_error": "Ảnh chụp GPU trong Redis không đọc được (hỏng định dạng).",
}

__all__ = [
    "GPU_ABSENCE_HINTS",
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
