"""Resource monitoring for the admin dashboard.

GPU stats come from a different place than everything else, on purpose:

  The backend API container has **no GPU passthrough** (only the trainer does),
  so it cannot query the GPU directly. Instead a lightweight sampler thread runs
  **inside the trainer worker** (which sees the GPU), snapshots ``nvidia-smi``
  every few seconds, and publishes the result to Redis. The backend then reads
  the latest snapshot from Redis. This keeps the API container GPU-free while
  still surfacing live GPU numbers — even while a job is training.

Self-gating: the sampler is started from the Celery ``worker_ready`` signal,
which fires in both the CPU-only video worker and the GPU trainer. Where
``nvidia-smi`` is absent (the video worker), ``start_gpu_monitor`` no-ops, so
the same image/signal is safe everywhere.

Freshness: snapshots carry a short TTL. A missing/expired key is reported as
"gpu unavailable" rather than as stale numbers.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis

from app.config import settings

logger = logging.getLogger("monitoring")

GPU_SNAPSHOT_KEY = "monitor:gpu"
GPU_SNAPSHOT_TTL = 15      # seconds — must exceed the sample interval so it never flaps
GPU_SAMPLE_INTERVAL = 4    # seconds between nvidia-smi samples

# Alert thresholds (percent)
RAM_ALERT_PCT = 90
CPU_ALERT_PCT = 92
VRAM_ALERT_PCT = 90
REDIS_ALERT_PCT = 90
DISK_WARN_PCT = 85     # Soft limit — cảnh báo admin
DISK_CRIT_PCT = 95     # Hard limit — chặn Sync, bảo vệ DB
# VRAM (MB) held by compute processes with NO active training job before we
# flag a possible leak. A margin above 0 avoids false positives from a job that
# is a few seconds into tearing down.
GPU_LEAK_MB = 400

_sampler_started = False
_sampler_lock = threading.Lock()


# ---------------------------------------------------------------------------
# small parse helpers (nvidia-smi emits "[N/A]" for some laptop fields)
# ---------------------------------------------------------------------------

def _to_float(v: Any) -> float:
    try:
        return round(float(str(v).strip()), 2)
    except Exception:
        return 0.0


def _to_int(v: Any) -> int:
    try:
        return int(float(str(v).strip()))
    except Exception:
        return 0


def _iso(v: Any) -> Optional[str]:
    if v is None:
        return None
    try:
        return v.isoformat()
    except Exception:
        return str(v)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redis_client() -> Optional["redis.Redis"]:
    try:
        return redis.from_url(
            settings.broker_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=3,
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# GPU sampling (runs inside the trainer)
# ---------------------------------------------------------------------------

def _sample_gpu_processes() -> List[Dict[str, Any]]:
    """Compute processes visible to THIS container (i.e. our training subprocess).

    Host desktop/graphics usage does not appear here, so a non-empty list with no
    active training job is a strong leak signal.
    """
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        procs: List[Dict[str, Any]] = []
        for line in out.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                procs.append({"pid": _to_int(parts[0]), "vram_mb": _to_float(parts[1])})
        return procs
    except Exception:
        return []


def sample_gpu() -> Optional[Dict[str, Any]]:
    """Query ``nvidia-smi`` once. Returns None where no GPU / nvidia-smi is present."""
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=utilization.gpu,memory.used,memory.total,"
             "temperature.gpu,power.draw,name",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return None
        parts = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")]
        parts = (parts + [""] * 6)[:6]
        util, mem_used, mem_total, temp, power, name = parts
        used = _to_float(mem_used)
        total = _to_float(mem_total)
        return {
            "available": True,
            "name": name,
            "util_pct": _to_float(util),
            "vram_used_mb": used,
            "vram_total_mb": total,
            "vram_pct": round(100.0 * used / total, 1) if total else 0.0,
            "temp_c": _to_float(temp),
            "power_w": _to_float(power),
            "processes": _sample_gpu_processes(),
        }
    except Exception as e:
        logger.debug("[MONITOR] nvidia-smi query failed: %s", e)
        return None


def _sampler_loop() -> None:
    logger.info("[MONITOR] GPU sampler started (interval=%ss)", GPU_SAMPLE_INTERVAL)
    while True:
        try:
            snap = sample_gpu()
            if snap is not None:
                snap["ts"] = time.time()
                client = _redis_client()
                if client is not None:
                    try:
                        client.set(GPU_SNAPSHOT_KEY, json.dumps(snap), ex=GPU_SNAPSHOT_TTL)
                    finally:
                        try:
                            client.close()
                        except Exception:
                            pass
        except Exception as e:
            logger.debug("[MONITOR] sampler tick error: %s", e)
        time.sleep(GPU_SAMPLE_INTERVAL)


def start_gpu_monitor() -> None:
    """Start the GPU sampler thread once — only where a GPU is actually visible."""
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


# ---------------------------------------------------------------------------
# Read side (runs inside the backend)
# ---------------------------------------------------------------------------

def read_gpu_snapshot() -> Dict[str, Any]:
    client = _redis_client()
    if client is None:
        return {"available": False, "reason": "redis_unavailable"}
    try:
        raw = client.get(GPU_SNAPSHOT_KEY)
    except Exception:
        return {"available": False, "reason": "redis_error"}
    finally:
        try:
            client.close()
        except Exception:
            pass
    if not raw:
        return {"available": False, "reason": "no_snapshot"}
    try:
        data = json.loads(raw)
        data["age_s"] = round(time.time() - float(data.get("ts", 0)), 1)
        return data
    except Exception:
        return {"available": False, "reason": "parse_error"}


def host_snapshot() -> Dict[str, Any]:
    """Host/VM CPU + RAM. Inside Docker Desktop this reflects the WSL2 VM
    (the whole 6-core / 12GB budget), which is the view we want."""
    try:
        import psutil

        per_core = psutil.cpu_percent(interval=0.15, percpu=True)
        cpu = round(sum(per_core) / len(per_core), 1) if per_core else 0.0
        vm = psutil.virtual_memory()
        return {
            "cpu_pct": cpu,
            "cpu_count": psutil.cpu_count(),
            "cpu_per_core": [round(c, 1) for c in per_core],
            "ram_used_mb": round((vm.total - vm.available) / 1e6, 1),
            "ram_total_mb": round(vm.total / 1e6, 1),
            "ram_pct": round(vm.percent, 1),
        }
    except Exception as e:
        return {"error": str(e)}


def redis_snapshot() -> Dict[str, Any]:
    client = _redis_client()
    if client is None:
        return {"available": False}
    try:
        info = client.info("memory")
        used = int(info.get("used_memory", 0) or 0)
        maxmem = int(info.get("maxmemory", 0) or 0)
        return {
            "available": True,
            "used_mb": round(used / 1e6, 1),
            "maxmemory_mb": round(maxmem / 1e6, 1) if maxmem else 0.0,
            "used_pct": round(100.0 * used / maxmem, 1) if maxmem else 0.0,
        }
    except Exception:
        return {"available": False}
    finally:
        try:
            client.close()
        except Exception:
            pass


def disk_snapshot() -> Dict[str, Any]:
    """Disk usage for the dataset volume.  shutil.disk_usage is a single
    syscall (statvfs) — essentially free, safe to call every poll cycle."""
    try:
        usage = shutil.disk_usage(str(settings.dataset_root))
        total_gb = round(usage.total / 1e9, 2)
        used_gb = round(usage.used / 1e9, 2)
        free_gb = round(usage.free / 1e9, 2)
        used_pct = round(100.0 * usage.used / usage.total, 1) if usage.total else 0.0
        return {
            "available": True,
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "used_pct": used_pct,
            "mount": str(settings.dataset_root),
        }
    except OSError as e:
        logger.debug("[MONITOR] disk_usage failed: %s", e)
        return {"available": False, "reason": str(e)}


def training_snapshot() -> Dict[str, Any]:
    """The currently running training job (if any), from Postgres."""
    try:
        from app.storage.metadata_db import list_training_jobs

        for job in list_training_jobs(limit=20):
            if str(job.get("status")) == "running":
                cfg = job.get("config") or {}
                return {
                    "active": True,
                    "job_id": job.get("job_id"),
                    "model_type": job.get("model_type") or cfg.get("model_type"),
                    "current_epoch": int(job.get("current_epoch") or 0),
                    "total_epochs": int(job.get("total_epochs") or 0),
                    "started_at": _iso(job.get("started_at")),
                }
        return {"active": False}
    except Exception as e:
        return {"active": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Resource configuration (allocation) — parsed from the deployed compose file.
# This is the "cấu hình tài nguyên": how the RAM budget is carved up per
# container + which service holds the GPU. Cached (rarely changes).
# ---------------------------------------------------------------------------

_SERVICE_ROLES = {
    "backend": "API",
    "worker": "Xử lý video",
    "trainer": "Huấn luyện (GPU)",
    "realtime_service": "Nhận dạng realtime",
    "celery-beat": "Lịch định kỳ",
    "redis": "Cache / Broker",
    "postgres": "CSDL",
    "nginx": "Gateway",
    "frontend": "Web tĩnh",
}
_COMPOSE_CANDIDATES = ["/workspace/docker-compose.prod.yml", "/workspace/docker-compose.yml"]
_config_cache: Dict[str, Any] = {"ts": 0.0, "data": None}


def _parse_mem_limit(v: Any) -> float:
    """Docker mem_limit ("3500m", "2g", "512M") -> megabytes. 0 => unlimited."""
    if v is None:
        return 0.0
    s = str(v).strip().lower()
    if not s:
        return 0.0
    mult = 1.0
    if s[-1] in "bkmg":
        mult = {"b": 1 / (1024 * 1024), "k": 1 / 1024, "m": 1.0, "g": 1024.0}[s[-1]]
        s = s[:-1]
    try:
        return round(float(s) * mult, 1)
    except Exception:
        return 0.0


def _parse_concurrency(cmd: Any) -> Optional[int]:
    """Celery worker concurrency from a service ``command`` (``-c N``)."""
    if not cmd:
        return None
    tokens = cmd.split() if isinstance(cmd, str) else [str(t) for t in cmd]
    for i, t in enumerate(tokens):
        if t == "-c" and i + 1 < len(tokens):
            try:
                return int(tokens[i + 1])
            except Exception:
                return None
        if t.startswith("-c") and t[2:].isdigit():
            return int(t[2:])
    return None


def _service_has_gpu(svc: Dict[str, Any]) -> bool:
    try:
        devices = svc["deploy"]["resources"]["reservations"]["devices"]
        for d in devices or []:
            caps = d.get("capabilities") or []
            flat = [c for grp in caps for c in (grp if isinstance(grp, list) else [grp])]
            if d.get("driver") == "nvidia" or "gpu" in flat:
                return True
    except Exception:
        pass
    return False


def resource_config() -> Dict[str, Any]:
    """Per-service memory allocation + GPU assignment from the deployed compose."""
    now = time.time()
    cached = _config_cache.get("data")
    if cached and now - _config_cache["ts"] < 60:
        return cached

    result: Dict[str, Any] = {"available": False}
    try:
        import yaml

        path = next((p for p in _COMPOSE_CANDIDATES if os.path.exists(p)), None)
        if path:
            with open(path, "r", encoding="utf-8") as f:
                doc = yaml.safe_load(f) or {}
            services: List[Dict[str, Any]] = []
            total = 0.0
            for name, svc in (doc.get("services") or {}).items():
                svc = svc or {}
                mem = _parse_mem_limit(svc.get("mem_limit"))
                total += mem
                cpus = svc.get("cpus")
                services.append({
                    "name": name,
                    "role": _SERVICE_ROLES.get(name, ""),
                    "mem_limit_mb": mem,      # 0 => unlimited
                    "gpu": _service_has_gpu(svc),
                    "cpus": float(cpus) if cpus else None,          # hard CPU cap (usually None = shared)
                    "concurrency": _parse_concurrency(svc.get("command")),
                })
            services.sort(key=lambda s: s["mem_limit_mb"], reverse=True)
            result = {
                "available": True,
                "source_file": os.path.basename(path),
                "services": services,
                "total_alloc_mb": round(total, 1),
            }
    except Exception as e:
        logger.debug("[MONITOR] resource_config parse failed: %s", e)
        result = {"available": False}

    _config_cache["ts"] = now
    _config_cache["data"] = result
    return result


def _build_alerts(host: Dict[str, Any], gpu: Dict[str, Any],
                  training: Dict[str, Any], rds: Dict[str, Any],
                  disk: Dict[str, Any] | None = None) -> List[Dict[str, str]]:
    alerts: List[Dict[str, str]] = []

    if host.get("ram_pct", 0) >= RAM_ALERT_PCT:
        alerts.append({"level": "critical",
                       "message": f"RAM {host['ram_pct']}% ≥ {RAM_ALERT_PCT}% — nguy cơ hết bộ nhớ"})
    if host.get("cpu_pct", 0) >= CPU_ALERT_PCT:
        alerts.append({"level": "warning",
                       "message": f"CPU {host['cpu_pct']}% ≥ {CPU_ALERT_PCT}%"})

    if gpu.get("available"):
        if gpu.get("vram_pct", 0) >= VRAM_ALERT_PCT:
            alerts.append({"level": "critical",
                           "message": f"VRAM {gpu['vram_pct']}% ≥ {VRAM_ALERT_PCT}%"})
        # Leak signal: compute processes hold VRAM but no training job is active.
        if not training.get("active"):
            held = sum(p.get("vram_mb", 0) for p in (gpu.get("processes") or []))
            if held >= GPU_LEAK_MB:
                alerts.append({"level": "warning",
                               "message": f"GPU đang giữ {held:.0f}MB nhưng KHÔNG có job "
                                          "training — nghi tiến trình chưa trả VRAM"})

    if rds.get("available") and rds.get("used_pct", 0) >= REDIS_ALERT_PCT:
        alerts.append({"level": "warning",
                       "message": f"Redis {rds['used_pct']}% ≥ {REDIS_ALERT_PCT}%"})

    # Disk watermark alerts
    if disk and disk.get("available"):
        dpct = disk.get("used_pct", 0)
        if dpct >= DISK_CRIT_PCT:
            alerts.append({"level": "critical",
                           "message": f"Ổ cứng {dpct}% ≥ {DISK_CRIT_PCT}% — Sync GDrive "
                                      "tạm dừng, cần giải phóng dung lượng ngay"})
        elif dpct >= DISK_WARN_PCT:
            alerts.append({"level": "warning",
                           "message": f"Ổ cứng {dpct}% ≥ {DISK_WARN_PCT}% — sắp đầy"})

    return alerts


def collect_resources() -> Dict[str, Any]:
    """Full snapshot for GET /admin/resources."""
    host = host_snapshot()
    gpu = read_gpu_snapshot()
    training = training_snapshot()
    rds = redis_snapshot()
    disk = disk_snapshot()
    return {
        "timestamp": _iso_now(),
        "host": host,
        "gpu": gpu,
        "training": training,
        "redis": rds,
        "disk": disk,
        "config": resource_config(),
        "alerts": _build_alerts(host, gpu, training, rds, disk),
    }
