"""Read deployed service resource limits from Docker Compose."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("monitoring")

SERVICE_ROLES = {
    "backend": "API", "worker": "Xử lý video", "trainer": "Huấn luyện (GPU)",
    "realtime_service": "Nhận dạng realtime", "celery-beat": "Lịch định kỳ",
    "redis": "Cache / Broker", "postgres": "CSDL", "nginx": "Gateway", "frontend": "Web tĩnh",
}
COMPOSE_CANDIDATES = ["/workspace/docker-compose.prod.yml", "/workspace/docker-compose.yml"]
_config_cache: Dict[str, Any] = {"ts": 0.0, "data": None}


def _parse_mem_limit(value: Any) -> float:
    if value is None:
        return 0.0
    raw = str(value).strip().lower()
    if not raw:
        return 0.0
    multiplier = 1.0
    if raw[-1] in "bkmg":
        multiplier = {"b": 1 / (1024 * 1024), "k": 1 / 1024, "m": 1.0, "g": 1024.0}[raw[-1]]
        raw = raw[:-1]
    try:
        return round(float(raw) * multiplier, 1)
    except Exception:
        return 0.0


def _parse_concurrency(command: Any) -> Optional[int]:
    if not command:
        return None
    tokens = command.split() if isinstance(command, str) else [str(token) for token in command]
    for index, token in enumerate(tokens):
        if token == "-c" and index + 1 < len(tokens):
            try:
                return int(tokens[index + 1])
            except Exception:
                return None
        if token.startswith("-c") and token[2:].isdigit():
            return int(token[2:])
    return None


def _service_has_gpu(service: Dict[str, Any]) -> bool:
    try:
        devices = service["deploy"]["resources"]["reservations"]["devices"]
        for device in devices or []:
            capabilities = device.get("capabilities") or []
            flat = [item for group in capabilities for item in (group if isinstance(group, list) else [group])]
            if device.get("driver") == "nvidia" or "gpu" in flat:
                return True
    except Exception:
        pass
    return False


def resource_config() -> Dict[str, Any]:
    now = time.time()
    cached = _config_cache.get("data")
    if cached and now - _config_cache["ts"] < 60:
        return cached
    result: Dict[str, Any] = {"available": False}
    try:
        import yaml
        path = next((candidate for candidate in COMPOSE_CANDIDATES if os.path.exists(candidate)), None)
        if path:
            with open(path, "r", encoding="utf-8") as stream:
                document = yaml.safe_load(stream) or {}
            services: List[Dict[str, Any]] = []
            total = 0.0
            for name, service in (document.get("services") or {}).items():
                service = service or {}
                memory = _parse_mem_limit(service.get("mem_limit"))
                total += memory
                cpus = service.get("cpus")
                services.append({
                    "name": name, "role": SERVICE_ROLES.get(name, ""), "mem_limit_mb": memory,
                    "gpu": _service_has_gpu(service), "cpus": float(cpus) if cpus else None,
                    "concurrency": _parse_concurrency(service.get("command")),
                })
            services.sort(key=lambda service: service["mem_limit_mb"], reverse=True)
            result = {"available": True, "source_file": os.path.basename(path),
                      "services": services, "total_alloc_mb": round(total, 1)}
    except Exception as exc:
        logger.debug("[MONITOR] resource_config parse failed: %s", exc)
        result = {"available": False}
    _config_cache["ts"] = now
    _config_cache["data"] = result
    return result
