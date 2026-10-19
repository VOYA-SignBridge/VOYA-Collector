"""Stable identity boundary used by HTTP and application modules.

Consumers import only this facade; orchestration, request dependencies, and
security primitives live in focused identity components behind it.
"""

from app.modules.identity.dependencies import (
    get_current_user,
    get_current_user_optional,
    require_admin,
)
from app.modules.identity.service import (
    authenticate_user,
    create_refresh_token,
    create_user,
    get_user_from_token,
    request_password_reset,
    reset_password_with_token,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.modules.identity.tokens import create_access_token
from app.modules.identity.cookies import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    clear_auth_cookies,
    generate_csrf_token,
    set_auth_cookies,
)
from app.services.email import send_password_reset_email
from app.modules.security.rate_limits import (
    check_login_allowed,
    client_ip,
    enforce_ip_limit,
    register_failed_login,
    reset_login_attempts,
)

__all__ = [
    "ACCESS_COOKIE",
    "REFRESH_COOKIE",
    "authenticate_user",
    "check_login_allowed",
    "clear_auth_cookies",
    "client_ip",
    "create_access_token",
    "create_refresh_token",
    "create_user",
    "enforce_ip_limit",
    "generate_csrf_token",
    "get_current_user",
    "get_current_user_optional",
    "get_user_from_token",
    "register_failed_login",
    "request_password_reset",
    "require_admin",
    "reset_login_attempts",
    "reset_password_with_token",
    "revoke_refresh_token",
    "rotate_refresh_token",
    "send_password_reset_email",
    "set_auth_cookies",
]
