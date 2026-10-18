"""Compatibility facade for web-system rate limiting.

The implementation lives in app.modules.security.rate_limits. Legacy imports
remain available here while application modules use the focused component.
"""

from app.infrastructure.redis.connection import get_redis_client as _client
from app.modules.security.rate_limits import (
    KEY_PREFIX as _KEY_PREFIX,
    LOGIN_MAX_ATTEMPTS,
    LOGIN_WINDOW_SECONDS,
    check_login_allowed,
    client_ip,
    enforce_ip_limit,
    increment_with_window as _incr_with_window,
    login_identifier_key as _login_id_key,
    login_ip_key as _login_ip_key,
    peek as _peek,
    register_failed_login,
    reset_login_attempts,
    too_many_requests as _too_many,
)
