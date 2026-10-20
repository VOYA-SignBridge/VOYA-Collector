"""Compatibility facade for activity monitoring and web security controls.

Implementations live in focused modules under app.modules.security. This
module keeps legacy imports stable for middleware, routers, and callers while
those components migrate independently.
"""

from app.infrastructure.redis.connection import get_activity_client
from app.modules.security.account_controls import (
    ack_user_warning,
    force_logout_user,
    format_until as _fmt_until,
    get_force_logout,
    get_user_lock,
    get_user_warning,
    is_user_denied,
    is_user_locked,
    list_locked_users,
    list_warned_users,
    lock_user,
    resolve_usernames as _resolve_usernames,
    revoke_all_refresh_tokens as _revoke_all_refresh_tokens,
    unlock_user,
    userlock_key as _userlock_key,
    warn_user,
)
from app.modules.security.activity_monitor import (
    ONLINE_ACTIVE_SECONDS,
    ONLINE_TTL,
    RATE_SKIP_PREFIXES as _RATE_SKIP_PREFIXES,
    RATE_WINDOW,
    RECORD_SKIP_PREFIXES as _RECORD_SKIP_PREFIXES,
    REQ_ALERT,
    activity_report,
    browser_name as _browser,
    detect_anomalies,
    guard,
    list_sessions,
    record,
    record_presence,
    should_record,
    user_id_from_request as _user_id_from_request,
)
from app.modules.security.audit_log import list_security_log, log_security_event
from app.modules.security.geo import (
    GEOIP_ASN_DB_PATH,
    GEOIP_DB_PATH,
    geo_lookup,
    get_asn_reader as _get_asn_reader,
    get_geo_reader as _get_geo_reader,
    is_private as _is_private,
    location_label as _loc_str,
)
from app.modules.security.ip_controls import (
    block_ip,
    block_key as _block_key,
    get_block,
    is_blocked,
    list_blocked,
    unblock_ip,
)

_client = get_activity_client
