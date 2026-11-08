"""Account authentication and registration orchestration.

This module owns identity use-cases.  Persistence, password primitives, and
token primitives stay in their focused modules; HTTP request dependencies live
in ``dependencies.py``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import uuid

from fastapi import HTTPException, status

from app.config import settings
from app.modules.identity.passwords import (
    DUMMY_PASSWORD_HASH,
    get_password_hash,
    verify_password,
)
from app.modules.identity.password_reset import apply_password_reset, issue_password_reset
from app.modules.identity.repository import (
    find_user_by_id,
    find_user_by_login,
    get_connection,
    insert_user,
    normalize_login,
)
from app.modules.identity.sessions import (
    issue_refresh_token,
    revoke_refresh_session,
    rotate_refresh_session,
)
from app.modules.identity.tokens import decode_access_token


def get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """Resolve a raw access token for non-HTTP dependency consumers.

    WebSocket endpoints use this because browsers cannot attach the normal
    Authorization dependency when opening a socket.  Invalid tokens deliberately
    return ``None`` rather than leaking an HTTP exception into the socket flow.
    """
    try:
        payload = decode_access_token(token)
    except HTTPException:
        return None
    user = find_user_by_id(str(payload.get("sub") or ""))
    if not user or not user.get("is_active", True):
        return None
    return user


def create_user(
    username: str,
    email: str,
    password: str,
    is_admin: bool = False,
) -> Dict[str, Any]:
    """Validate and create an account without exposing persistence details."""
    username_norm = (username or "").strip()
    email_norm = normalize_login(email)
    if not username_norm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is required")
    if not email_norm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")
    if len(password or "") < int(settings.min_password_length):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {settings.min_password_length} characters",
        )

    existing = find_user_by_login(username_norm) or find_user_by_login(email_norm)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    return insert_user(
        user_id=str(uuid.uuid4()),
        username=username_norm,
        email=email_norm,
        password_hash=get_password_hash(password),
        is_admin=is_admin,
    )


def authenticate_user(identifier: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate an active account while resisting login timing probes."""
    user = find_user_by_login(identifier)
    if not user or not user.get("is_active", True):
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def request_password_reset(identifier: str) -> Optional[Tuple[Dict[str, Any], str]]:
    return issue_password_reset(
        identifier,
        user_lookup=find_user_by_login,
        connection_factory=get_connection,
    )


def reset_password_with_token(token: str, new_password: str) -> None:
    apply_password_reset(token, new_password, connection_factory=get_connection)


def create_refresh_token(user_id: str) -> str:
    return issue_refresh_token(user_id, connection_factory=get_connection)


def rotate_refresh_token(raw_token: str) -> Optional[Tuple[Dict[str, Any], str]]:
    return rotate_refresh_session(
        raw_token,
        user_lookup=find_user_by_id,
        connection_factory=get_connection,
    )


def revoke_refresh_token(raw_token: str) -> None:
    revoke_refresh_session(raw_token, connection_factory=get_connection)
