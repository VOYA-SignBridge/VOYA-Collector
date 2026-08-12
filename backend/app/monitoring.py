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

# Ngọn đèn "trainer đang chạy và KHÔNG thấy thiết bị nào" — xem
# `_publish_absence_beacon`. TTL rộng hơn nhịp làm tươi khá nhiều để một lần
# Redis chớp không biến "không có GPU" thành "trainer chết".
GPU_ABSENCE_KEY = "monitor:gpu:absent"
GPU_ABSENCE_INTERVAL = 60
GPU_ABSENCE_TTL = 180

# CPU is sampled in the background for the same reason GPU is: measuring it
# inside the request needs a blocking window, and a window short enough not to
# hurt the request is too short to measure anything.
#
# /proc/stat counts in jiffies at USER_HZ=100, so a 0.15s window gives each core
# at most 15 ticks — a core at 3% earns 0.45 of a tick and reports exactly 0.
# Measured on this host at idle: interval=0.15s put 3 of 12 cores above zero and
# averaged 1.55%; interval=1.0s put 12 of 12 above zero and averaged 12.8%. The
# admin panel was reading 0-1% while the machine was doing real work.
CPU_SAMPLE_INTERVAL = 2.0  # seconds — long enough that per-core values resolve

# Alert thresholds (percent)
RAM_ALERT_PCT = 90
CPU_ALERT_PCT = 92
VRAM_ALERT_PCT = 90
REDIS_ALERT_PCT = 90
# Ngưỡng đĩa — HAI con số, và đây là NGUỒN DUY NHẤT của cả hai.
#
# Trước 2026-08-09 cùng một ngưỡng được viết ở ba nơi với ba giá trị: 85 ở đây,
# 0.95 trong `sync_tasks.DISK_HIGH_WATERMARK`, và một phép trừ `watermark - 5`
# trong `cli/verify_deployment.py`. Ba nơi không thể sửa cùng lúc, nên bảng
# quản trị cảnh báo ở 85 trong khi kiểm tra sau triển khai im lặng tới 90.
#
# `sync_tasks` nhập DISK_CRIT_PCT từ đây chứ không ngược lại: `sync_tasks` kéo
# theo `app.worker`, mà `app.worker` nhập chính module này — chiều ngược lại là
# một vòng nhập khẩu.
DISK_WARN_PCT = 85     # Cảnh báo admin.
DISK_CRIT_PCT = 95     # Chặn Sync để bảo vệ CSDL. KHÔNG nới theo cảnh báo.
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


_torch_cache: Dict[str, Any] = {}


def _torch_verdict() -> Dict[str, Any]:
    """Torch trên container này CÓ chạy được trên đúng con chip này không.

    Vì sao đây là câu hỏi riêng, không suy ra được từ `nvidia-smi`: một wheel
    torch chỉ mang kernel cho những kiến trúc nó được biên dịch cho.
    `torch.cuda.is_available()` trả True trên một card mới hơn, rồi lượt phóng
    kernel ĐẦU TIÊN chết giữa buổi huấn luyện với `no kernel image is available
    for execution on the device` — sau khi dữ liệu đã nạp xong, và với một câu
    lỗi đọc như lỗi lập trình chứ không như lệch bản dựng.

    Cụ thể, hai máy của dự án này không cùng một chip:

        máy A  RTX 3050 Laptop   Ampere    sm_86
        máy B  RTX 5060 Ti       Blackwell sm_120

    torch 2.7.1+cu128 (bản đang cài) mang `sm_75…sm_90, sm_100, sm_120`, nên cả
    hai đều chạy được. Điều đó KHÔNG hiển nhiên và không vĩnh viễn: hạ về một
    wheel cu121 là máy B lặng lẽ rơi xuống CPU. Nên phép so khớp này được ĐO ở
    nơi có card và gửi kèm ảnh chụp, thay vì để ai đó nhớ.

    Cache lại: `import torch` tốn vài giây và câu trả lời không đổi trong suốt
    vòng đời container.
    """
    if _torch_cache:
        return _torch_cache
    verdict: Dict[str, Any] = {}
    try:
        import torch  # nặng, nên nhập trong hàm

        major, minor = torch.cuda.get_device_capability(0)
        arch = f"sm_{major}{minor}"
        supported = list(torch.cuda.get_arch_list())
        verdict = {
            "compute_capability": arch,
            "torch_version": str(torch.__version__),
            "torch_arch_list": supported,
            # Không có arch list (bản dựng CPU) thì không kết luận được — báo
            # None chứ không báo False, để bên đọc phân biệt "không hỗ trợ" với
            # "không biết".
            "torch_supports_this_gpu": (arch in supported) if supported else None,
        }
    except Exception as exc:
        logger.debug("[MONITOR] torch capability probe failed: %s", exc)
        verdict = {"torch_supports_this_gpu": None}
    _torch_cache.update(verdict)
    return verdict


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
            **_torch_verdict(),
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


def _publish_absence_beacon() -> None:
    """Ghi lại việc TRÌNH HUẤN LUYỆN đã khởi động và KHÔNG thấy thiết bị nào.

    Vì sao cần một tín hiệu riêng cho việc "không có": thiếu ảnh chụp trong
    Redis là câu trả lời chung cho ba tình huống rất khác nhau —

      * máy chủ không có GPU;
      * máy chủ CÓ GPU nhưng container trainer được dựng thiếu overlay, nên
        thiết bị không được cấp vào trong;
      * trainer chết hẳn, không ai chụp gì cả.

    Sự cố ngày 2026-08-09 là trường hợp thứ hai, và cảnh báo gửi đi nói
    "Nvidia GPU is missing or unreadable" — đọc lên hệt trường hợp thứ nhất.
    Người nhận đi tìm cái card mà cái card vẫn nằm trong máy. Ngọn đèn báo
    "tôi có chạy, và tôi không thấy thiết bị nào" tách được hai cái đầu ra
    khỏi cái thứ ba.

    Khoá riêng, KHÔNG dùng chung `monitor:gpu`: tín hiệu `worker_ready` nổ ở
    CẢ trình xử lý video (không bao giờ có GPU) lẫn trainer, nên ghi đè lên
    khoá chính sẽ xoá mất ảnh chụp thật của trainer mỗi lần trình xử lý video
    khởi động lại.
    """
    client = _redis_client()
    if client is None:
        return
    try:
        client.set(
            GPU_ABSENCE_KEY,
            json.dumps({"reason": "no_device_in_container", "ts": time.time()}),
            ex=GPU_ABSENCE_TTL,
        )
    except Exception as e:
        logger.debug("[MONITOR] absence beacon not published: %s", e)
    finally:
        try:
            client.close()
        except Exception:
            pass


def _absence_beacon_loop() -> None:
    """Làm tươi ngọn đèn báo vắng mặt, và TẮT NÓ khi thiết bị xuất hiện.

    Chạy chậm hơn bộ chụp thật rất nhiều: đây là một sự thật gần như không đổi
    trong suốt vòng đời container, và mỗi nhịp tốn một lần gọi `nvidia-smi`.
    Vẫn phải kiểm lại chứ không chỉ ghi một lần rồi thôi — trình điều khiển
    NVIDIA trên máy trạm có thể xuất hiện lại sau một lần nâng cấp mà container
    không hề khởi động lại, và lúc đó ngọn đèn phải tự tắt.
    """
    global _sampler_started
    while True:
        if sample_gpu() is not None:
            with _sampler_lock:
                if not _sampler_started:
                    threading.Thread(target=_sampler_loop, name="gpu-monitor",
                                     daemon=True).start()
                    _sampler_started = True
                    logger.info("[MONITOR] GPU xuat hien tro lai — bat bo chup")
            return
        _publish_absence_beacon()
        time.sleep(GPU_ABSENCE_INTERVAL)


def start_gpu_monitor(*, is_trainer: bool = False) -> None:
    """Start the GPU sampler thread once — only where a GPU is actually visible.

    `is_trainer` chỉ đổi hành vi khi KHÔNG có thiết bị: chỉ trainer mới được
    thắp đèn báo vắng mặt, vì chỉ trainer mới được kỳ vọng có GPU. Trình xử lý
    video không có GPU là chuyện bình thường, không phải sự cố.
    """
    global _sampler_started
    with _sampler_lock:
        if _sampler_started:
            return
        has_device = shutil.which("nvidia-smi") is not None and sample_gpu() is not None
        if has_device:
            threading.Thread(target=_sampler_loop, name="gpu-monitor", daemon=True).start()
            _sampler_started = True
            logger.info("[MONITOR] GPU sampler thread launched")
            return

    logger.info("[MONITOR] no GPU visible here — sampler disabled (trainer=%s)", is_trainer)
    if is_trainer:
        threading.Thread(target=_absence_beacon_loop, name="gpu-absence",
                         daemon=True).start()


# ---------------------------------------------------------------------------
# Read side (runs inside the backend)
# ---------------------------------------------------------------------------

#: Vì sao GPU không đọc được, dịch sang câu người vận hành làm được việc gì đó.
#: Đi vào cả thư cảnh báo lẫn bảng quản trị — cùng một câu, một chỗ sửa.
GPU_ABSENCE_HINTS: Dict[str, str] = {
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


def read_gpu_snapshot() -> Dict[str, Any]:
    client = _redis_client()
    if client is None:
        return {"available": False, "reason": "redis_unavailable",
                "hint": GPU_ABSENCE_HINTS["redis_unavailable"]}
    try:
        raw = client.get(GPU_SNAPSHOT_KEY)
        # Chỉ hỏi ngọn đèn báo vắng mặt khi KHÔNG có ảnh chụp thật. Ảnh chụp
        # thật luôn thắng: đèn có TTL dài hơn nên nó còn sống một lúc sau khi
        # thiết bị quay lại.
        beacon = None if raw else client.get(GPU_ABSENCE_KEY)
    except Exception:
        return {"available": False, "reason": "redis_error",
                "hint": GPU_ABSENCE_HINTS["redis_error"]}
    finally:
        try:
            client.close()
        except Exception:
            pass
    if not raw:
        reason = "no_device_in_container" if beacon else "no_snapshot"
        return {"available": False, "reason": reason,
                "hint": GPU_ABSENCE_HINTS[reason]}
    try:
        data = json.loads(raw)
        data["age_s"] = round(time.time() - float(data.get("ts", 0)), 1)
        return data
    except Exception:
        return {"available": False, "reason": "parse_error",
                "hint": GPU_ABSENCE_HINTS["parse_error"]}


_cpu_lock = threading.Lock()
_cpu_latest: List[float] = []
_cpu_sampler_started = False


def _cpu_sampler_loop() -> None:
    global _cpu_latest
    import psutil

    while True:
        try:
            # Blocking form: psutil sleeps the interval and diffs /proc/stat
            # across it. Blocking is fine here — it is this thread's only job.
            per_core = psutil.cpu_percent(interval=CPU_SAMPLE_INTERVAL, percpu=True)
            with _cpu_lock:
                _cpu_latest = list(per_core)
        except Exception as e:
            logger.debug("[MONITOR] cpu sampler tick error: %s", e)
            time.sleep(CPU_SAMPLE_INTERVAL)


def start_cpu_monitor() -> None:
    """Start the CPU sampler thread once, in whichever process serves /resources."""
    global _cpu_sampler_started
    with _sampler_lock:
        if _cpu_sampler_started:
            return
        try:
            import psutil  # noqa: F401
        except Exception:
            logger.info("[MONITOR] psutil missing — CPU sampler disabled")
            return
        threading.Thread(target=_cpu_sampler_loop, name="cpu-monitor", daemon=True).start()
        _cpu_sampler_started = True
        logger.info("[MONITOR] CPU sampler started (interval=%ss)", CPU_SAMPLE_INTERVAL)


def host_snapshot() -> Dict[str, Any]:
    """Host/VM CPU + RAM. Inside Docker Desktop this reflects the WSL2 VM
    (the whole 6-core / 12GB budget), which is the view we want."""
    try:
        import psutil

        with _cpu_lock:
            per_core = list(_cpu_latest)
        if not per_core:
            # Sampler not warm yet (first request after boot). One blocking
            # read at a window wide enough to actually resolve, rather than
            # reporting a zero that looks like an idle machine.
            per_core = psutil.cpu_percent(interval=1.0, percpu=True)
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
    
    # Fetch ignore flags from Redis
    client = _redis_client()
    if client:
        try:
            if client.get("config:ignore_missing_gpu") in (b"1", "1"):
                gpu["ignored"] = True
            if client.get("config:ignore_missing_disk") in (b"1", "1"):
                disk["ignored"] = True
        except Exception as e:
            logger.debug("[MONITOR] Failed to fetch ignore flags: %s", e)

    alerts = _build_alerts(host, gpu, training, rds, disk)
    
    if not gpu.get("available") and not gpu.get("ignored"):
        # This used to read "Server không tìm thấy phần cứng đồ họa" at level
        # critical, which was wrong twice over. The backend never looks at the
        # hardware — it only reads a snapshot the worker publishes, and the
        # worker publishes nothing when nvidia-smi is absent from ITS container.
        # On this host `docker run --gpus all` prints an RTX 3050 quite happily;
        # the stack was simply started without docker-compose.gpu.yml. And
        # CPU-only is the documented default deploy (that overlay is opt-in
        # precisely so hosts without the NVIDIA toolkit still come up), so
        # flagging it critical raised a red alarm over a supported setup.
        # Câu này KHÔNG còn chứa lệnh docker.
        #
        # Một dòng `docker compose -f … -f … -f … up -d` dán giữa bảng theo dõi
        # là thứ không ai gõ được từ trình duyệt, và nó chiếm chỗ của điều thật
        # sự cần nói: huấn luyện đang chậm hơn lẽ ra. Việc bật lại GPU thuộc về
        # `scripts/deploy.sh`, vốn tự dò card và tự ghi COMPOSE_FILE — người vận
        # hành chỉ cần biết CHẠY LẠI nó, không cần thuộc lòng ba tệp overlay.
        alerts.append({
            "level": "warning",
            "message": "Huấn luyện đang chạy bằng CPU — container không được cấp GPU.",
            "hint": (
                "Nếu máy này có card NVIDIA: chạy lại scripts/deploy.sh (nó tự dò "
                "card và bật overlay). Nếu máy không có card thì đây là trạng thái "
                "đúng — tắt cảnh báo bằng nút bên cạnh."
            ),
            "resource": "gpu",
        })
        
    if disk and not disk.get("available") and not disk.get("ignored"):
        alerts.append({"level": "critical", "message": "Mất kết nối Ổ cứng lưu trữ (Dataset volume).", "resource": "disk"})

    return {
        "timestamp": _iso_now(),
        "host": host,
        "gpu": gpu,
        "training": training,
        "redis": rds,
        "disk": disk,
        "config": resource_config(),
        "alerts": alerts,
    }
