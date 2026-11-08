"""Password-reset workflow and persistence for the identity context."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, Tuple

from fastapi import HTTPException, status
from psycopg2.extras import RealDictCursor

from app.config import settings
from app.modules.identity.passwords import get_password_hash
from app.modules.identity.repository import ConnectionFactory, get_connection


UserLookup = Callable[[str], Optional[Dict[str, Any]]]


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_password_reset(
    identifier: str,
    *,
    user_lookup: UserLookup,
    connection_factory: ConnectionFactory = get_connection,
) -> Optional[Tuple[Dict[str, Any], str]]:
    user = user_lookup(identifier)
    if not user or not user.get("is_active", True):
        return None

    token = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_token_expire_minutes
    )

    conn = connection_factory()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO password_reset_tokens (token_hash, user_id, expires_at)
                    VALUES (%s, %s, %s)
                    """,
                    (token_hash, user["id"], expires_at),
                )
    finally:
        conn.close()

    return user, token


def apply_password_reset(
    token: str,
    new_password: str,
    *,
    connection_factory: ConnectionFactory = get_connection,
) -> None:
    if len(new_password or "") < int(settings.min_password_length):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {settings.min_password_length} characters",
        )

    token_hash = hash_reset_token(token)
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn",
    )

    conn = connection_factory()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT token_hash, user_id, expires_at, used_at
                    FROM password_reset_tokens
                    WHERE token_hash = %s
                    """,
                    (token_hash,),
                )
                row = cur.fetchone()

                if not row or row["used_at"] is not None:
                    raise invalid

                expires_at = row["expires_at"]
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at < datetime.now(timezone.utc):
                    raise invalid

                password_hash = get_password_hash(new_password)
                cur.execute(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (password_hash, row["user_id"]),
                )
                cur.execute(
                    """
                    UPDATE password_reset_tokens
                    SET used_at = NOW()
                    WHERE user_id = %s AND used_at IS NULL
                    """,
                    (row["user_id"],),
                )
    finally:
        conn.close()
