from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.config import settings
from app.cookie_auth import ACCESS_COOKIE
from app.modules.identity.passwords import (
    DUMMY_PASSWORD_HASH,
    get_password_hash,
    verify_password,
)
from app.modules.identity.password_reset import (
    apply_password_reset,
    hash_reset_token,
    issue_password_reset,
)
from app.modules.identity.repository import (
    find_user_by_id,
    find_user_by_login,
    get_connection,
    insert_user,
    normalize_login,
    row_to_user,
)
from app.modules.identity.sessions import (
    hash_refresh_token,
    issue_refresh_token,
    revoke_refresh_session,
    rotate_refresh_session,
)
from app.modules.identity.tokens import (
    bearer_scheme,
    create_access_token,
    decode_access_token,
)

# Compatibility aliases for consumers that still import private legacy names.
_DUMMY_PASSWORD_HASH = DUMMY_PASSWORD_HASH
_decode_token = decode_access_token
_normalize_login = normalize_login
_row_to_user = row_to_user
_hash_reset_token = hash_reset_token
_hash_token = hash_refresh_token


def _get_conn():
    return get_connection()


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
    return find_user_by_id(user_id, connection_factory=_get_conn)


def _fetch_user_by_login(identifier: str) -> Optional[Dict[str, Any]]:
    return find_user_by_login(identifier, connection_factory=_get_conn)


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

    return insert_user(
        user_id=user_id,
        username=username_norm,
        email=email_norm,
        password_hash=password_hash,
        is_admin=is_admin,
        connection_factory=_get_conn,
    )


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

def request_password_reset(identifier: str) -> Optional[Tuple[Dict[str, Any], str]]:
    """Look up the user and issue a reset token if the account exists and is active.

    Returns (user, raw_token) or None if there's no matching active account.
    Callers must respond with the same generic message either way, to avoid
    leaking which identifiers correspond to real accounts.
    """
    return issue_password_reset(
        identifier,
        user_lookup=_fetch_user_by_login,
        connection_factory=_get_conn,
    )


def reset_password_with_token(token: str, new_password: str) -> None:
    """Validate a reset token and set the new password. Raises HTTPException on failure."""
    apply_password_reset(
        token,
        new_password,
        connection_factory=_get_conn,
    )


# ============================================================================
# Refresh tokens (cookie session flow)
# ============================================================================

def create_refresh_token(user_id: str) -> str:
    """Issue a new opaque refresh token, storing only its hash. Returns the raw
    token (to be set as an httpOnly cookie)."""
    return issue_refresh_token(user_id, connection_factory=_get_conn)


def rotate_refresh_token(raw_token: str) -> Optional[Tuple[Dict[str, Any], str]]:
    """Validate a refresh token, revoke it, and mint a replacement.

    Returns (user, new_raw_token) or None if the token is missing / expired /
    revoked / belongs to an inactive user. Rotation means a stolen refresh
    token stops working the moment the legitimate client next refreshes.
    """
    return rotate_refresh_session(
        raw_token,
        user_lookup=_fetch_user_by_id,
        connection_factory=_get_conn,
    )


def revoke_refresh_token(raw_token: str) -> None:
    """Mark a refresh token revoked (logout). Best-effort; never raises."""
    revoke_refresh_session(raw_token, connection_factory=_get_conn)
