"""Shared process-local Redis connection for web-system features."""

from __future__ import annotations

import logging
import os
from typing import Optional

import redis

from app.config import settings

logger = logging.getLogger(__name__)

_REDIS_URL = os.getenv("REDIS_URL", getattr(settings, "broker_url", "redis://redis:6379/0"))
_client_singleton: Optional[redis.Redis] = None
_client_failed = False


def get_redis_client() -> Optional[redis.Redis]:
    """Return the shared Redis client, failing open after connection errors."""
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
        logger.warning("[redis] unavailable, web security features fail open: %s", exc)
        _client_failed = True
        return None


# Compatibility name retained for activity/security modules migrated in BR-011.
get_activity_client = get_redis_client
