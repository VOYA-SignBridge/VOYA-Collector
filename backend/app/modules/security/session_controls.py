"""Revocation controls for access-token sessions.

Redis holds short-lived denylist entries; the durable account-wide marker is
stored in Postgres and compared here without any external I/O.
"""

import logging
import time
from typing import Any

from app.config import settings
from app.infrastructure.redis.connection import get_activity_client


logger = logging.getLogger(__name__)

_JTI_DENY_PREFIX = "denyjti:"
_FAMILY_DENY_PREFIX = "denyfam:"


def token_predates_marker(token_iat: Any, marker: Any) -> bool:
    """Return whether a token was issued before a durable revocation marker."""
    if marker is None:
        return False
    try:
        marker_ts = marker.timestamp() if hasattr(marker, "timestamp") else float(marker)
        return float(token_iat or 0) < marker_ts
    except Exception:
        return False


def deny_access_token(jti: str, expires_at: Any = None) -> bool:
    """Deny one access token until its normal expiration time."""
    if not jti:
        return False
    client = get_activity_client()
    if client is None:
        logger.error("[ACTIVITY] khong co Redis — access token %s KHONG bi chan", jti)
        return False
    try:
        ttl = int(settings.access_token_expire_minutes) * 60 + 120
        if expires_at is not None:
            try:
                remaining = int(float(expires_at) - time.time()) + 5
                if remaining > 0:
                    ttl = min(ttl, remaining)
            except Exception:
                pass
        client.set(f"{_JTI_DENY_PREFIX}{jti}", "1", ex=max(1, ttl))
        return True
    except Exception as exc:
        logger.error("[ACTIVITY] chan access token %s that bai: %s", jti, exc)
        return False


def deny_token_family(family_id: str) -> bool:
    """Deny access tokens descended from one compromised refresh session."""
    if not family_id:
        return False
    client = get_activity_client()
    if client is None:
        logger.error("[ACTIVITY] khong co Redis — ho token %s KHONG bi chan", family_id)
        return False
    try:
        ttl = int(settings.access_token_expire_minutes) * 60 + 120
        client.set(f"{_FAMILY_DENY_PREFIX}{family_id}", "1", ex=ttl)
        return True
    except Exception as exc:
        logger.error("[ACTIVITY] chan ho token %s that bai: %s", family_id, exc)
        return False


def is_token_family_denied(family_id: str) -> bool:
    if not family_id:
        return False
    client = get_activity_client()
    if client is None:
        return False
    try:
        return client.get(f"{_FAMILY_DENY_PREFIX}{family_id}") is not None
    except Exception:
        return False


def is_access_token_denied(jti: str) -> bool:
    if not jti:
        return False
    client = get_activity_client()
    if client is None:
        return False
    try:
        return client.get(f"{_JTI_DENY_PREFIX}{jti}") is not None
    except Exception:
        return False
