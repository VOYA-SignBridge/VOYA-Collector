"""Redis-backed abuse limiter for the auth endpoints.

Two independent counters gate login:
  - per client IP  → stops one host hammering many accounts (credential stuffing)
  - per identifier → stops many hosts hammering one account (targeted brute force)

Both use a fixed window (INCR + EXPIRE). Exceeding the threshold within the
window returns HTTP 429 with Retry-After until the window rolls over. A generic
per-IP limiter also guards register / forgot-password / reset-password against
spam floods.

Redis being unavailable fails OPEN (requests allowed). The nginx edge
rate-limit still caps raw flood, and locking every user out on a Redis hiccup
would be worse than the residual risk. All failures are best-effort.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

import redis
from fastapi import HTTPException, Request, status

from app.config import settings

logger = logging.getLogger(__name__)

_REDIS_URL = os.getenv("REDIS_URL", getattr(settings, "broker_url", "redis://redis:6379/0"))

# Tunables (env-overridable). Defaults: up to 5 failed logins per identifier/IP
# within a 30-minute detection window; the 5th trips a 15-minute soft lock. The
# detection window and the lock are separate on purpose ("5 sai trong 30p, khóa
# mềm 15p") — the counter still rides its 30-min window for the admin anomaly
# view, while the lock decides whether a login is refused.
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "1800"))   # 30-min detection window
LOGIN_LOCK_SECONDS = int(os.getenv("LOGIN_LOCK_SECONDS", "900"))        # 15-min soft lock

_KEY_PREFIX = "ratelimit:"

_client_singleton: Optional[redis.Redis] = None
_client_failed = False


def _client() -> Optional[redis.Redis]:
    global _client_singleton, _client_failed
    if _client_singleton is not None:
        return _client_singleton
    if _client_failed:
        return None
    try:
        c = redis.from_url(
            _REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=3,
        )
        c.ping()
        _client_singleton = c
        return c
    except Exception as exc:  # pragma: no cover - infra dependent
        logger.warning("[ratelimit] Redis unavailable, failing open: %s", exc)
        _client_failed = True
        return None


def client_ip(request: Request) -> str:
    """Best-effort real client IP behind the nginx gateway.

    nginx sets X-Forwarded-For / X-Real-IP; take the first hop. Falls back to
    the socket peer. Never raises.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return (request.client.host if request.client else "unknown") or "unknown"


def _incr_with_window(key: str, window: int) -> Tuple[int, int]:
    """INCR key, set EXPIRE on first hit. Returns (count, ttl_seconds)."""
    c = _client()
    if c is None:
        return (0, 0)
    try:
        count = int(c.incr(key))
        if count == 1:
            c.expire(key, window)
        ttl = int(c.ttl(key))
        if ttl < 0:
            # Key had no TTL (shouldn't happen) — set one defensively.
            c.expire(key, window)
            ttl = window
        return (count, ttl)
    except Exception as exc:  # pragma: no cover
        logger.warning("[ratelimit] incr failed for %s: %s", key, exc)
        return (0, 0)


def _peek(key: str) -> Tuple[int, int]:
    """Read count + ttl without incrementing. Returns (count, ttl_seconds)."""
    c = _client()
    if c is None:
        return (0, 0)
    try:
        raw = c.get(key)
        count = int(raw) if raw is not None else 0
        ttl = int(c.ttl(key))
        return (count, max(ttl, 0))
    except Exception as exc:  # pragma: no cover
        logger.warning("[ratelimit] peek failed for %s: %s", key, exc)
        return (0, 0)


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau.",
        headers={"Retry-After": str(max(retry_after, 1))},
    )


# --- Login-specific (per IP + per identifier) --------------------------------

def _login_ip_key(ip: str) -> str:
    return f"{_KEY_PREFIX}login:ip:{ip}"


def _login_id_key(identifier: str) -> str:
    return f"{_KEY_PREFIX}login:id:{(identifier or '').strip().lower()}"


def _login_lock_ip_key(ip: str) -> str:
    return f"{_KEY_PREFIX}login:lock:ip:{ip}"


def _login_lock_id_key(identifier: str) -> str:
    return f"{_KEY_PREFIX}login:lock:id:{(identifier or '').strip().lower()}"


def _set_lock(key: str, seconds: int) -> None:
    c = _client()
    if c is None:
        return
    try:
        c.set(key, "1", ex=max(1, seconds))
    except Exception as exc:  # pragma: no cover
        logger.warning("[ratelimit] set lock failed for %s: %s", key, exc)


def _lock_ttl(key: str) -> int:
    """Remaining lock seconds, or 0 if not locked."""
    c = _client()
    if c is None:
        return 0
    try:
        ttl = int(c.ttl(key))
        return ttl if ttl > 0 else 0
    except Exception:  # pragma: no cover
        return 0


def check_login_allowed(ip: str, identifier: str) -> None:
    """Raise 429 if the IP or the identifier is currently soft-locked.

    Called BEFORE verifying credentials so a locked account/IP never even runs
    bcrypt. The lock is a separate key from the failure counter, so it survives a
    fixed 15 minutes regardless of the 30-minute counting window.
    """
    for key in (_login_lock_ip_key(ip), _login_lock_id_key(identifier)):
        ttl = _lock_ttl(key)
        if ttl > 0:
            raise _too_many(ttl)


def register_failed_login(ip: str, identifier: str) -> None:
    """Count a failed login against both the IP and the identifier; on the
    LOGIN_MAX_ATTEMPTS-th failure within the window, arm the 15-minute lock."""
    for counter_key, lock_key in (
        (_login_ip_key(ip), _login_lock_ip_key(ip)),
        (_login_id_key(identifier), _login_lock_id_key(identifier)),
    ):
        count, _ = _incr_with_window(counter_key, LOGIN_WINDOW_SECONDS)
        if count >= LOGIN_MAX_ATTEMPTS:
            _set_lock(lock_key, LOGIN_LOCK_SECONDS)


def reset_login_attempts(ip: str, identifier: str) -> None:
    """Clear counters AND locks after a successful login so a legit user who
    finally gets their password right is never left locked."""
    c = _client()
    if c is None:
        return
    try:
        c.delete(
            _login_ip_key(ip), _login_id_key(identifier),
            _login_lock_ip_key(ip), _login_lock_id_key(identifier),
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("[ratelimit] reset failed: %s", exc)


# --- Generic per-IP limiter (register / forgot / reset) ----------------------

def enforce_ip_limit(request: Request, bucket: str, max_calls: int, window: int) -> None:
    """Raise 429 if this IP has exceeded `max_calls` in `bucket` within window."""
    ip = client_ip(request)
    key = f"{_KEY_PREFIX}{bucket}:ip:{ip}"
    count, ttl = _incr_with_window(key, window)
    if count > max_calls:
        raise _too_many(ttl or window)
