"""Best-effort Redis security audit log for administrative actions."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from app.infrastructure.redis.connection import get_activity_client


def log_security_event(
    action: str,
    actor: str = "",
    target: str = "",
    reason: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    client = get_activity_client()
    if client is None:
        return
    try:
        entry = {
            "ts": time.time(),
            "action": action,
            "actor": actor,
            "target": target,
            "reason": reason,
        }
        if extra:
            entry.update(extra)
        client.lpush("sec:log", json.dumps(entry))
        client.ltrim("sec:log", 0, 499)
    except Exception:
        pass


def list_security_log(limit: int = 100) -> List[Dict[str, Any]]:
    client = get_activity_client()
    if client is None:
        return []
    try:
        output = []
        for raw in client.lrange("sec:log", 0, max(0, limit - 1)):
            try:
                output.append(json.loads(raw))
            except Exception:
                pass
        return output
    except Exception:
        return []
