"""Public API for authentication, sessions, and account identity.

Exports are resolved lazily so legacy modules can delegate their implementation
to this bounded context while the incremental migration is in progress.
"""

from importlib import import_module

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
    "ForgotPasswordRequest",
    "LoginRequest",
    "MessageResponse",
    "RegisterRequest",
    "ResetPasswordRequest",
    "UserOut",
]

_SCHEMA_EXPORTS = {
    "ForgotPasswordRequest",
    "LoginRequest",
    "MessageResponse",
    "RegisterRequest",
    "ResetPasswordRequest",
    "UserOut",
}


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name = "schemas" if name in _SCHEMA_EXPORTS else "api"
    module = import_module(f"{__name__}.{module_name}")
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
