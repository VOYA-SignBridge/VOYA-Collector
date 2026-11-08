"""Redis-backed abuse limits for authentication and public account endpoints.

Login is limited independently by client IP and normalized identifier. Generic
per-IP buckets protect registration and password-reset workflows. Redis errors
fail open so an infrastructure outage cannot lock every user out.
"""

from __future__ import annotations

import logging
import os
from typing import Tuple

from fastapi import HTTPException, Request, status

from app.infrastructure.redis.connection import get_redis_client

logger = logging.getLogger(__name__)

LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "900"))

KEY_PREFIX = "ratelimit:"


def client_ip(request: Request) -> str:
    """Return the first trusted gateway IP header, then the socket peer."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return (request.client.host if request.client else "unknown") or "unknown"


def increment_with_window(key: str, window: int) -> Tuple[int, int]:
    """Increment a fixed-window counter and return its count and remaining TTL."""
    client = get_redis_client()
    if client is None:
        return (0, 0)
    try:
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, window)
        ttl = int(client.ttl(key))
        if ttl < 0:
            client.expire(key, window)
            ttl = window
        return (count, ttl)
    except Exception as exc:  # pragma: no cover - Redis transport failure
        logger.warning("[ratelimit] increment failed for %s: %s", key, exc)
        return (0, 0)


def peek(key: str) -> Tuple[int, int]:
    """Read a counter and TTL without incrementing it."""
    client = get_redis_client()
    if client is None:
        return (0, 0)
    try:
        raw = client.get(key)
        count = int(raw) if raw is not None else 0
        ttl = int(client.ttl(key))
        return (count, max(ttl, 0))
    except Exception as exc:  # pragma: no cover - Redis transport failure
        logger.warning("[ratelimit] read failed for %s: %s", key, exc)
        return (0, 0)


def too_many_requests(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau.",
        headers={"Retry-After": str(max(retry_after, 1))},
    )


def login_ip_key(ip: str) -> str:
    return f"{KEY_PREFIX}login:ip:{ip}"


def login_identifier_key(identifier: str) -> str:
    return f"{KEY_PREFIX}login:id:{(identifier or '').strip().lower()}"


def check_login_allowed(ip: str, identifier: str) -> None:
    """Raise HTTP 429 before bcrypt when either login counter is at its limit."""
    for key in (login_ip_key(ip), login_identifier_key(identifier)):
        count, ttl = peek(key)
        if count >= LOGIN_MAX_ATTEMPTS:
            raise too_many_requests(ttl or LOGIN_WINDOW_SECONDS)


def register_failed_login(ip: str, identifier: str) -> None:
    increment_with_window(login_ip_key(ip), LOGIN_WINDOW_SECONDS)
    increment_with_window(login_identifier_key(identifier), LOGIN_WINDOW_SECONDS)


def reset_login_attempts(ip: str, identifier: str) -> None:
    client = get_redis_client()
    if client is None:
        return
    try:
        client.delete(login_ip_key(ip), login_identifier_key(identifier))
    except Exception as exc:  # pragma: no cover - Redis transport failure
        logger.warning("[ratelimit] reset failed: %s", exc)


def enforce_ip_limit(request: Request, bucket: str, max_calls: int, window: int) -> None:
    """Raise HTTP 429 after an IP exceeds a generic fixed-window bucket."""
    ip = client_ip(request)
    key = f"{KEY_PREFIX}{bucket}:ip:{ip}"
    count, ttl = increment_with_window(key, window)
    if count > max_calls:
        raise too_many_requests(ttl or window)
