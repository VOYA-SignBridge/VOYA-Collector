"""Process-local Redis connection for best-effort activity/security features."""

from __future__ import annotations

import logging
import os
from typing import Optional

import redis

from app.config import settings

logger = logging.getLogger("activity")

_REDIS_URL = os.getenv("REDIS_URL", getattr(settings, "broker_url", "redis://redis:6379/0"))
_client_singleton: Optional[redis.Redis] = None
_client_failed = False


def get_activity_client() -> Optional[redis.Redis]:
    """Return the shared activity Redis client, failing open after connection errors."""
    global _client_singleton, _client_failed
    if _client_singleton is not None:
        return _client_singleton
    if _client_failed:
        return None
    try:
        client = redis.from_url(
            _REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=3,
        )
        client.ping()
        _client_singleton = client
        return client
    except Exception as exc:  # pragma: no cover - depends on external Redis
        logger.warning("[ACTIVITY] Redis unavailable, tracking disabled: %s", exc)
        _client_failed = True
        return None
