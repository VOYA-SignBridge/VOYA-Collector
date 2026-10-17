"""Refresh-session workflow and persistence for the identity context."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, Tuple

from psycopg2.extras import RealDictCursor

from app.config import settings
from app.modules.identity.repository import ConnectionFactory, get_connection


UserById = Callable[[str], Optional[Dict[str, Any]]]


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_refresh_token(
    user_id: str,
    *,
    connection_factory: ConnectionFactory = get_connection,
) -> str:
    raw = secrets.token_urlsafe(48)
    token_hash = hash_refresh_token(raw)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.refresh_token_expire_minutes
    )
    conn = connection_factory()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO refresh_tokens (token_hash, user_id, expires_at)
                    VALUES (%s, %s, %s)
                    """,
                    (token_hash, user_id, expires_at),
                )
    finally:
        conn.close()
    return raw


def rotate_refresh_session(
    raw_token: str,
    *,
    user_lookup: UserById,
    connection_factory: ConnectionFactory = get_connection,
) -> Optional[Tuple[Dict[str, Any], str]]:
    if not raw_token:
        return None
    token_hash = hash_refresh_token(raw_token)

    conn = connection_factory()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT token_hash, user_id, expires_at, revoked_at
                    FROM refresh_tokens
                    WHERE token_hash = %s
                    """,
                    (token_hash,),
                )
                row = cur.fetchone()
                if not row or row["revoked_at"] is not None:
                    return None

                expires_at = row["expires_at"]
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at < datetime.now(timezone.utc):
                    return None

                user = user_lookup(str(row["user_id"]))
                if not user or not user.get("is_active", True):
                    return None

                new_raw = secrets.token_urlsafe(48)
                new_hash = hash_refresh_token(new_raw)
                new_expires = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.refresh_token_expire_minutes
                )
                cur.execute(
                    "UPDATE refresh_tokens SET revoked_at = NOW() WHERE token_hash = %s",
                    (token_hash,),
                )
                cur.execute(
                    """
                    INSERT INTO refresh_tokens (token_hash, user_id, expires_at)
                    VALUES (%s, %s, %s)
                    """,
                    (new_hash, row["user_id"], new_expires),
                )
                return user, new_raw
    finally:
        conn.close()


def revoke_refresh_session(
    raw_token: str,
    *,
    connection_factory: ConnectionFactory = get_connection,
) -> None:
    if not raw_token:
        return
    token_hash = hash_refresh_token(raw_token)
    conn = connection_factory()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE refresh_tokens
                    SET revoked_at = NOW()
                    WHERE token_hash = %s AND revoked_at IS NULL
                    """,
                    (token_hash,),
                )
    except Exception:
        pass
    finally:
        conn.close()
