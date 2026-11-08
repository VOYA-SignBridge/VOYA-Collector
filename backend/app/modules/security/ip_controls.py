"""Redis-backed client IP block controls."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from app.infrastructure.redis.connection import get_activity_client

logger = logging.getLogger("activity")

BLOCK_PREFIX = "block:ip:"


def block_key(ip: str) -> str:
    return f"{BLOCK_PREFIX}{ip}"


def is_blocked(ip: str) -> bool:
    client = get_activity_client()
    if client is None or not ip:
        return False
    try:
        return bool(client.exists(block_key(ip)))
    except Exception:
        return False


def get_block(ip: str) -> Optional[Dict[str, Any]]:
    client = get_activity_client()
    if client is None or not ip:
        return None
    try:
        raw = client.get(block_key(ip))
        if not raw:
            return None
        payload = json.loads(raw)
        ttl = client.ttl(block_key(ip))
        payload["ttl"] = ttl if ttl and ttl > 0 else 0
        return payload
    except Exception:
        return None


def block_ip(ip: str, by: str = "", reason: str = "", duration_seconds: int = 0) -> bool:
    client = get_activity_client()
    if client is None or not ip:
        return False
    try:
        duration = int(duration_seconds or 0)
        until = (time.time() + duration) if duration > 0 else 0
        payload = json.dumps({"by": by, "at": time.time(), "reason": reason, "until": until})
        if duration > 0:
            client.set(block_key(ip), payload, ex=duration)
        else:
            client.set(block_key(ip), payload)
        logger.info(
            "[ACTIVITY] IP blocked: %s by=%s dur=%ss reason=%s",
            ip,
            by,
            duration,
            (reason or "")[:40],
        )
        return True
    except Exception:
        return False


def unblock_ip(ip: str) -> bool:
    client = get_activity_client()
    if client is None or not ip:
        return False
    try:
        client.delete(block_key(ip))
        return True
    except Exception:
        return False


def list_blocked() -> List[Dict[str, Any]]:
    client = get_activity_client()
    if client is None:
        return []
    output: List[Dict[str, Any]] = []
    try:
        for key in client.scan_iter(match=f"{BLOCK_PREFIX}*", count=200):
            ip = key[len(BLOCK_PREFIX):]
            raw = client.get(key)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {}
            ttl = client.ttl(key)
            output.append({
                "ip": ip,
                "by": payload.get("by", ""),
                "at": payload.get("at"),
                "reason": payload.get("reason", ""),
                "until": payload.get("until", 0),
                "ttl": ttl if ttl and ttl > 0 else 0,
            })
        return output
    except Exception:
        return []
