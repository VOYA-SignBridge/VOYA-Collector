"""FastAPI dependencies for resolving and authorizing the current account."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.cookie_auth import ACCESS_COOKIE
from app.modules.identity.repository import find_user_by_id
from app.modules.identity.tokens import bearer_scheme, decode_access_token
from app.modules.security.account_controls import get_force_logout, is_user_denied


def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[Dict[str, Any]]:
    """Resolve the current account from cookie first, then Bearer credentials."""
    # Cookie precedence is intentional: browsers migrating from the legacy
    # localStorage flow can keep sending a stale header alongside a fresh cookie.
    token = request.cookies.get(ACCESS_COOKIE)
    if not token and credentials is not None:
        token = credentials.credentials
    if not token:
        return None

    payload = decode_access_token(token)
    user_id = str(payload.get("sub") or "")

    # Admin force-logout is a best-effort Redis policy.  Preserve the historical
    # fail-open behaviour when activity tracking itself is unavailable.
    try:
        if is_user_denied(user_id, payload.get("iat")):
            force_logout = get_force_logout(user_id) or {}
            message = "Phiên đã bị đăng xuất bởi quản trị viên"
            if force_logout.get("reason"):
                message += f": {force_logout['reason']}"
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)
    except HTTPException:
        raise
    except Exception:
        pass

    user = find_user_by_id(user_id)
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
