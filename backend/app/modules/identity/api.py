"""Stable identity boundary used by HTTP and application modules.

The implementation remains in the legacy modules during the incremental
migration. Consumers import only this facade so internals can move later without
another repository-wide rewrite.
"""

from app.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_user,
    get_current_user,
    get_current_user_optional,
    get_user_from_token,
    request_password_reset,
    require_admin,
    reset_password_with_token,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.cookie_auth import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    clear_auth_cookies,
    generate_csrf_token,
    set_auth_cookies,
)
from app.email_service import send_password_reset_email
from app.rate_limit import (
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
