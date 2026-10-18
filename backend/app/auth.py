"""Compatibility facade for the identity bounded context.

New application code imports ``app.modules.identity``.  Legacy imports remain
stable here while implementation lives in focused identity components.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.modules.identity.dependencies import (
    get_current_user,
    get_current_user_optional,
    require_admin,
)
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
from app.modules.identity.service import (
    authenticate_user,
    create_user,
    get_user_from_token,
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


def _fetch_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    return find_user_by_id(user_id, connection_factory=_get_conn)


def _fetch_user_by_login(identifier: str) -> Optional[Dict[str, Any]]:
    return find_user_by_login(identifier, connection_factory=_get_conn)


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
