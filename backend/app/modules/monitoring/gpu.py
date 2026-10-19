"""GPU sampling and Redis-backed snapshot transport."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

from app.infrastructure.redis.connection import get_redis_client

logger = logging.getLogger("monitoring")
GPU_SNAPSHOT_KEY = "monitor:gpu"
GPU_SNAPSHOT_TTL = 15
GPU_SAMPLE_INTERVAL = 4
_sampler_started = False
_sampler_lock = threading.Lock()


def _to_float(value: Any) -> float:
    try:
        return round(float(str(value).strip()), 2)
    except Exception:
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return 0


def _sample_gpu_processes() -> List[Dict[str, Any]]:
    """Return compute processes visible to the current container."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        processes: List[Dict[str, Any]] = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = [part.strip() for part in line.split(",")]
            if len(parts) >= 2:
                processes.append({"pid": _to_int(parts[0]), "vram_mb": _to_float(parts[1])})
        return processes
    except Exception:
        return []


def sample_gpu() -> Optional[Dict[str, Any]]:
    """Query ``nvidia-smi`` once, or return ``None`` if no GPU is visible."""
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,name",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        parts = [part.strip() for part in result.stdout.strip().splitlines()[0].split(",")]
        util, mem_used, mem_total, temp, power, name = (parts + [""] * 6)[:6]
        used = _to_float(mem_used)
        total = _to_float(mem_total)
        return {
            "available": True, "name": name, "util_pct": _to_float(util),
            "vram_used_mb": used, "vram_total_mb": total,
            "vram_pct": round(100.0 * used / total, 1) if total else 0.0,
            "temp_c": _to_float(temp), "power_w": _to_float(power),
            "processes": _sample_gpu_processes(),
        }
    except Exception as exc:
        logger.debug("[MONITOR] nvidia-smi query failed: %s", exc)
        return None


def _sampler_loop() -> None:
    logger.info("[MONITOR] GPU sampler started (interval=%ss)", GPU_SAMPLE_INTERVAL)
    while True:
        try:
            snapshot = sample_gpu()
            if snapshot is not None:
                snapshot["ts"] = time.time()
                client = get_redis_client()
                if client is not None:
                    client.set(GPU_SNAPSHOT_KEY, json.dumps(snapshot), ex=GPU_SNAPSHOT_TTL)
        except Exception as exc:
            logger.debug("[MONITOR] sampler tick error: %s", exc)
        time.sleep(GPU_SAMPLE_INTERVAL)


def start_gpu_monitor() -> None:
    """Start one sampler thread, only where a GPU is visible."""
    global _sampler_started
    with _sampler_lock:
        if _sampler_started:
            return
        if shutil.which("nvidia-smi") is None or sample_gpu() is None:
            logger.info("[MONITOR] no GPU visible here — sampler disabled")
            return
        threading.Thread(target=_sampler_loop, name="gpu-monitor", daemon=True).start()
        _sampler_started = True
        logger.info("[MONITOR] GPU sampler thread launched")


def read_gpu_snapshot() -> Dict[str, Any]:
    client = get_redis_client()
    if client is None:
        return {"available": False, "reason": "redis_unavailable"}
    try:
        raw = client.get(GPU_SNAPSHOT_KEY)
    except Exception:
        return {"available": False, "reason": "redis_error"}
    if not raw:
        return {"available": False, "reason": "no_snapshot"}
    try:
        data = json.loads(raw)
        data["age_s"] = round(time.time() - float(data.get("ts", 0)), 1)
        return data
    except Exception:
        return {"available": False, "reason": "parse_error"}
