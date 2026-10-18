"""Administrative account controls backed by Redis and refresh-token revocation."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional, Set

from psycopg2.extras import RealDictCursor

from app.config import settings
from app.infrastructure.database.connection import connect_postgres
from app.infrastructure.redis.connection import get_activity_client

logger = logging.getLogger("activity")

USERLOCK_PREFIX = "userlock:"
USERWARN_PREFIX = "userwarn:"


def userlock_key(user_id: str) -> str:
    return f"{USERLOCK_PREFIX}{user_id}"


def format_until(until: float) -> str:
    if not until:
        return ""
    try:
        return datetime.fromtimestamp(until).strftime("%H:%M %d/%m/%Y")
    except Exception:
        return ""


def revoke_all_refresh_tokens(user_id: str) -> None:
    try:
        connection = connect_postgres(connect_timeout=5)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE refresh_tokens SET revoked_at = NOW() "
                        "WHERE user_id = %s AND revoked_at IS NULL",
                        (user_id,),
                    )
        finally:
            connection.close()
    except Exception as exc:
        logger.warning("[ACTIVITY] revoke refresh tokens failed for %s: %s", user_id, exc)


def force_logout_user(user_id: str, by: str = "", reason: str = "") -> bool:
    """Invalidate current access tokens and revoke all active refresh tokens."""
    if not user_id:
        return False
    ttl = int(settings.access_token_expire_minutes) * 60 + 120
    client = get_activity_client()
    if client is not None:
        try:
            client.set(
                f"forcelogout:{user_id}",
                json.dumps({"ts": time.time(), "by": by, "reason": reason}),
                ex=ttl,
            )
        except Exception:
            pass
    revoke_all_refresh_tokens(user_id)
    logger.info("[ACTIVITY] force-logout user=%s by=%s", user_id, by)
    return True


def get_force_logout(user_id: str) -> Optional[Dict[str, Any]]:
    client = get_activity_client()
    if client is None or not user_id:
        return None
    try:
        value = client.get(f"forcelogout:{user_id}")
        if value is None:
            return None
        try:
            return json.loads(value)
        except Exception:
            return {"ts": float(value), "reason": ""}
    except Exception:
        return None


def is_user_denied(user_id: str, token_iat: Any) -> bool:
    force_logout = get_force_logout(user_id)
    if not force_logout:
        return False
    try:
        return float(token_iat or 0) < float(force_logout.get("ts", 0))
    except Exception:
        return False


def lock_user(user_id: str, by: str = "", reason: str = "", duration_seconds: int = 0) -> bool:
    if not user_id:
        return False
    client = get_activity_client()
    if client is None:
        return False
    try:
        duration = int(duration_seconds or 0)
        until = (time.time() + duration) if duration > 0 else 0
        client.set(
            userlock_key(user_id),
            json.dumps({"by": by, "at": time.time(), "reason": reason, "until": until}),
            **({"ex": duration} if duration > 0 else {}),
        )
        message = f"Tài khoản của bạn đã bị khóa. Lý do: {reason or 'vi phạm quy định'}"
        if until:
            message += f" (đến {format_until(until)})"
        force_logout_user(user_id, by=by, reason=message)
        logger.info("[ACTIVITY] user locked: %s by=%s dur=%ss", user_id, by, duration)
        return True
    except Exception:
        return False


def unlock_user(user_id: str) -> bool:
    client = get_activity_client()
    if client is None or not user_id:
        return False
    try:
        client.delete(userlock_key(user_id))
        return True
    except Exception:
        return False


def get_user_lock(user_id: str) -> Optional[Dict[str, Any]]:
    client = get_activity_client()
    if client is None or not user_id:
        return None
    try:
        raw = client.get(userlock_key(user_id))
        if not raw:
            return None
        payload = json.loads(raw)
        ttl = client.ttl(userlock_key(user_id))
        payload["ttl"] = ttl if ttl and ttl > 0 else 0
        return payload
    except Exception:
        return None


def is_user_locked(user_id: str) -> bool:
    client = get_activity_client()
    if client is None or not user_id:
        return False
    try:
        return bool(client.exists(userlock_key(user_id)))
    except Exception:
        return False


def list_locked_users() -> Dict[str, Dict[str, Any]]:
    client = get_activity_client()
    if client is None:
        return {}
    output: Dict[str, Dict[str, Any]] = {}
    try:
        for key in client.scan_iter(match=f"{USERLOCK_PREFIX}*", count=200):
            user_id = key[len(USERLOCK_PREFIX):]
            raw = client.get(key)
            try:
                payload = json.loads(raw) if raw else {}
            except Exception:
                payload = {}
            ttl = client.ttl(key)
            payload["ttl"] = ttl if ttl and ttl > 0 else 0
            output[user_id] = payload
        return output
    except Exception:
        return {}


def warn_user(user_id: str, by: str = "", message: str = "") -> bool:
    client = get_activity_client()
    if client is None or not user_id:
        return False
    try:
        client.set(
            f"{USERWARN_PREFIX}{user_id}",
            json.dumps({"by": by, "at": time.time(), "message": message}),
            ex=30 * 86400,
        )
        return True
    except Exception:
        return False


def get_user_warning(user_id: str) -> Optional[Dict[str, Any]]:
    client = get_activity_client()
    if client is None or not user_id:
        return None
    try:
        raw = client.get(f"{USERWARN_PREFIX}{user_id}")
        return json.loads(raw) if raw else None
    except Exception:
        return None


def ack_user_warning(user_id: str) -> None:
    client = get_activity_client()
    if client is None or not user_id:
        return
    try:
        client.delete(f"{USERWARN_PREFIX}{user_id}")
    except Exception:
        pass


def list_warned_users() -> Set[str]:
    client = get_activity_client()
    if client is None:
        return set()
    try:
        return {
            key[len(USERWARN_PREFIX):]
            for key in client.scan_iter(match=f"{USERWARN_PREFIX}*", count=200)
        }
    except Exception:
        return set()


def resolve_usernames(user_ids: Set[str]) -> Dict[str, Dict[str, Any]]:
    ids = [user_id for user_id in user_ids if user_id]
    if not ids:
        return {}
    try:
        connection = connect_postgres(connect_timeout=5)
        try:
            with connection:
                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(
                        "SELECT id, username, is_admin FROM users WHERE id::text = ANY(%s)",
                        (ids,),
                    )
                    return {
                        str(row["id"]): {
                            "username": row["username"],
                            "is_admin": bool(row["is_admin"]),
                        }
                        for row in cursor.fetchall()
                    }
        finally:
            connection.close()
    except Exception as exc:
        logger.warning("[ACTIVITY] username resolve failed: %s", exc)
        return {}
