from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.cookie_auth import ACCESS_COOKIE
from app.storage.postgres_connection import connect_postgres

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

# Precomputed bcrypt hash used to equalize login response time when the account
# does not exist. Without it, a missing user returns immediately (no bcrypt)
# while a real user with a wrong password pays the bcrypt cost — an attacker can
# measure that gap to enumerate valid usernames. Verifying against this dummy on
# the "no such user" path makes both branches take the same time.
_DUMMY_PASSWORD_HASH = pwd_context.hash("voya-timing-equalizer-not-a-real-secret")


def _get_conn():
    return connect_postgres(connect_timeout=5)


def _normalize_login(identifier: str) -> str:
    return (identifier or "").strip().lower()


def _row_to_user(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "username": row["username"] or "",
        "email": row["email"] or "",
        "password_hash": row["password_hash"] or "",
        "is_active": bool(row.get("is_active", True)),
        "is_admin": bool(row.get("is_admin", False)),
        "created_at": row.get("created_at"),
    }


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload.update(
        {
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "typ": "access",
        }
    )
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def _decode_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )
    return payload


def get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode a raw JWT and fetch the user, returning None instead of raising.

    Intended for WebSocket endpoints, where the token arrives as a query
    param (browsers cannot set Authorization headers on WS connections)
    rather than through the HTTPBearer dependency used by regular routes.
    """
    try:
        payload = _decode_token(token)
    except HTTPException:
        return None
    user = _fetch_user_by_id(str(payload.get("sub") or ""))
    if not user or not user.get("is_active", True):
        return None
    return user


def _fetch_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, username, email, password_hash, is_active, is_admin, created_at
                    FROM users
                    WHERE id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                return _row_to_user(row)
    finally:
        conn.close()


def _fetch_user_by_login(identifier: str) -> Optional[Dict[str, Any]]:
    login = _normalize_login(identifier)
    if not login:
        return None

    conn = _get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, username, email, password_hash, is_active, is_admin, created_at
                    FROM users
                    WHERE lower(username) = %s OR lower(email) = %s
                    LIMIT 1
                    """,
                    (login, login),
                )
                row = cur.fetchone()
                return _row_to_user(row)
    finally:
        conn.close()


def create_user(
    username: str,
    email: str,
    password: str,
    is_admin: bool = False,
) -> Dict[str, Any]:
    username_norm = (username or "").strip()
    email_norm = _normalize_login(email)
    if not username_norm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is required")
    if not email_norm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")
    if len(password or "") < int(settings.min_password_length):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {settings.min_password_length} characters",
        )

    existing = _fetch_user_by_login(username_norm) or _fetch_user_by_login(email_norm)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    user_id = str(uuid.uuid4())
    password_hash = get_password_hash(password)

    conn = _get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO users (id, username, email, password_hash, is_active, is_admin)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, username, email, password_hash, is_active, is_admin, created_at
                    """,
                    (
                        user_id,
                        username_norm,
                        email_norm,
                        password_hash,
                        True,
                        bool(is_admin),
                    ),
                )
                row = cur.fetchone()
                return _row_to_user(row) or {}
    finally:
        conn.close()


def authenticate_user(identifier: str, password: str) -> Optional[Dict[str, Any]]:
    user = _fetch_user_by_login(identifier)
    if not user or not user.get("is_active", True):
        # Run a dummy verify so this path costs the same as a real "wrong
        # password" — defeats username enumeration via timing side-channel.
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[Dict[str, Any]]:
    # Prefer the httpOnly access COOKIE (the SPA's session), then fall back to
    # the Authorization: Bearer header (API clients / WS fallback). Order
    # matters: browsers migrated from the legacy localStorage flow may still
    # send a STALE Bearer header on every request — if that were preferred, a
    # perfectly valid fresh cookie session would 401 forever (login -> bounce
    # loop). Pure API clients send no cookies, so they are unaffected.
    token = request.cookies.get(ACCESS_COOKIE)
    if not token and credentials is not None:
        token = credentials.credentials
    if not token:
        return None

    payload = _decode_token(token)
    user_id = str(payload.get("sub") or "")

    # Force-logout: an admin can invalidate a user's live sessions. Tokens
    # issued before the force-logout marker are rejected; a fresh login works.
    try:
        from app import activity

        if activity.is_user_denied(user_id, payload.get("iat")):
            fl = activity.get_force_logout(user_id) or {}
            msg = "Phiên đã bị đăng xuất bởi quản trị viên"
            if fl.get("reason"):
                msg += f": {fl['reason']}"
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=msg)
    except HTTPException:
        raise
    except Exception:
        pass

    user = _fetch_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Dict[str, Any]:
    user = get_current_user_optional(request, credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


# ============================================================================
# Forgot / reset password
# ============================================================================

def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_password_reset(identifier: str) -> Optional[Tuple[Dict[str, Any], str]]:
    """Look up the user and issue a reset token if the account exists and is active.

    Returns (user, raw_token) or None if there's no matching active account.
    Callers must respond with the same generic message either way, to avoid
    leaking which identifiers correspond to real accounts.
    """
    user = _fetch_user_by_login(identifier)
    if not user or not user.get("is_active", True):
        return None

    token = secrets.token_urlsafe(32)
    token_hash = _hash_reset_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_token_expire_minutes
    )

    conn = _get_conn()
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


def reset_password_with_token(token: str, new_password: str) -> None:
    """Validate a reset token and set the new password. Raises HTTPException on failure."""
    if len(new_password or "") < int(settings.min_password_length):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {settings.min_password_length} characters",
        )

    token_hash = _hash_reset_token(token)
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn",
    )

    conn = _get_conn()
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
                # Invalidate every outstanding reset token for this user,
                # including the one just used, so old links can't be replayed.
                cur.execute(
                    """
                    UPDATE password_reset_tokens
                    SET used_at = NOW()
                    WHERE user_id = %s AND used_at IS NULL
                    """,
                    (row["user_id"],),
                )
                # Kill every existing session too. A reset is often "my account
                # may be compromised" — leaving an attacker's still-valid refresh
                # token alive would defeat the point. Same transaction as the
                # password change, so it's all-or-nothing.
                cur.execute(
                    "UPDATE refresh_tokens SET revoked_at = NOW() "
                    "WHERE user_id = %s AND revoked_at IS NULL",
                    (row["user_id"],),
                )
    finally:
        conn.close()


# ============================================================================
# Refresh tokens (cookie session flow)
# ============================================================================

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token(user_id: str) -> str:
    """Issue a new opaque refresh token, storing only its hash. Returns the raw
    token (to be set as an httpOnly cookie)."""
    raw = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.refresh_token_expire_minutes
    )
    conn = _get_conn()
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


def rotate_refresh_token(raw_token: str) -> Optional[Tuple[Dict[str, Any], str]]:
    """Validate a refresh token, revoke it, and mint a replacement.

    Returns (user, new_raw_token) or None if the token is missing / expired /
    revoked / belongs to an inactive user. Rotation means a stolen refresh
    token stops working the moment the legitimate client next refreshes.
    """
    if not raw_token:
        return None
    token_hash = _hash_token(raw_token)

    conn = _get_conn()
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

                user = _fetch_user_by_id(str(row["user_id"]))
                if not user or not user.get("is_active", True):
                    return None

                new_raw = secrets.token_urlsafe(48)
                new_hash = _hash_token(new_raw)
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


def revoke_refresh_token(raw_token: str) -> None:
    """Mark a refresh token revoked (logout). Best-effort; never raises."""
    if not raw_token:
        return
    token_hash = _hash_token(raw_token)
    conn = _get_conn()
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