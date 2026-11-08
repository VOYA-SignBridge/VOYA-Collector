"""Aggregate resource snapshots and derive operator-facing alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.modules.monitoring.compose_config import resource_config
from app.modules.monitoring.gpu import read_gpu_snapshot
from app.modules.monitoring.snapshots import disk_snapshot, host_snapshot, redis_snapshot, training_snapshot

RAM_ALERT_PCT = 90
CPU_ALERT_PCT = 92
VRAM_ALERT_PCT = 90
REDIS_ALERT_PCT = 90
DISK_WARN_PCT = 85
DISK_CRIT_PCT = 95
GPU_LEAK_MB = 400


def _build_alerts(
    host: Dict[str, Any], gpu: Dict[str, Any], training: Dict[str, Any],
    redis_data: Dict[str, Any], disk: Dict[str, Any] | None = None,
) -> List[Dict[str, str]]:
    alerts: List[Dict[str, str]] = []
    if host.get("ram_pct", 0) >= RAM_ALERT_PCT:
        alerts.append({"level": "critical", "message": f"RAM {host['ram_pct']}% ≥ {RAM_ALERT_PCT}% — nguy cơ hết bộ nhớ"})
    if host.get("cpu_pct", 0) >= CPU_ALERT_PCT:
        alerts.append({"level": "warning", "message": f"CPU {host['cpu_pct']}% ≥ {CPU_ALERT_PCT}%"})
    if gpu.get("available"):
        if gpu.get("vram_pct", 0) >= VRAM_ALERT_PCT:
            alerts.append({"level": "critical", "message": f"VRAM {gpu['vram_pct']}% ≥ {VRAM_ALERT_PCT}%"})
        if not training.get("active"):
            held = sum(process.get("vram_mb", 0) for process in (gpu.get("processes") or []))
            if held >= GPU_LEAK_MB:
                alerts.append({"level": "warning", "message": f"GPU đang giữ {held:.0f}MB nhưng KHÔNG có job training — nghi tiến trình chưa trả VRAM"})
    if redis_data.get("available") and redis_data.get("used_pct", 0) >= REDIS_ALERT_PCT:
        alerts.append({"level": "warning", "message": f"Redis {redis_data['used_pct']}% ≥ {REDIS_ALERT_PCT}%"})
    if disk and disk.get("available"):
        disk_percent = disk.get("used_pct", 0)
        if disk_percent >= DISK_CRIT_PCT:
            alerts.append({"level": "critical", "message": f"Ổ cứng {disk_percent}% ≥ {DISK_CRIT_PCT}% — Sync GDrive tạm dừng, cần giải phóng dung lượng ngay"})
        elif disk_percent >= DISK_WARN_PCT:
            alerts.append({"level": "warning", "message": f"Ổ cứng {disk_percent}% ≥ {DISK_WARN_PCT}% — sắp đầy"})
    return alerts


def collect_resources() -> Dict[str, Any]:
    host = host_snapshot()
    gpu = read_gpu_snapshot()
    training = training_snapshot()
    redis_data = redis_snapshot()
    disk = disk_snapshot()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(), "host": host, "gpu": gpu,
        "training": training, "redis": redis_data, "disk": disk, "config": resource_config(),
        "alerts": _build_alerts(host, gpu, training, redis_data, disk),
    }
