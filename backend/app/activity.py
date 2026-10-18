"""Activity tracking plus compatibility exports for web security controls.

Multi-user web: the admin needs to see who is connected, from where (IP +
geolocation), how heavily each is using the service, plus a way to react —
block an abusive IP or force-logout a user.

Redis connection, IP controls, audit logging, and account controls live in
focused infrastructure/security modules.  Their legacy names are re-exported
here while request/session monitoring remains in this module.

Everything is **best-effort and fail-open**: monitoring must never break a real
request. Redis down => tracking silently no-ops; requests still flow.

Storage (all in Redis, short TTLs so it self-prunes):
  act:active                 ZSET  ip -> last_seen (enumerate online sessions)
  act:sess:{ip}              HASH  ip, user_id, ua, last_path, last_seen, first_seen
  act:rate:{ip}:{bucket}     INT   requests in a fixed 5-min window (anomaly)
  act:geo:{ip}               STR   cached GeoIP lookup (JSON)
  block:ip                   SET   blocked client IPs (enforced in middleware)
  block:meta                 HASH  ip -> {by, at, reason}
  forcelogout:{user_id}      STR   epoch; tokens issued before it are rejected

GeoIP is offline (MaxMind GeoLite2) — no user IP ever leaves the server. The DB
file is optional; without it, location degrades to empty rather than failing.
"""
from __future__ import annotations

import ipaddress
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Set

from fastapi import Request
from jose import jwt

from app.config import settings
from app.cookie_auth import ACCESS_COOKIE
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
from app.modules.security.audit_log import log_security_event, list_security_log
from app.modules.security.ip_controls import (
    block_ip,
    block_key as _block_key,
    get_block,
    is_blocked,
    list_blocked,
    unblock_ip,
)
from app.rate_limit import client_ip

logger = logging.getLogger("activity")

ONLINE_TTL = int(os.getenv("ACTIVITY_ONLINE_TTL", "600"))        # session considered gone after
ONLINE_ACTIVE_SECONDS = int(os.getenv("ACTIVITY_ACTIVE_SECONDS", "120"))  # "online now" window
RATE_WINDOW = int(os.getenv("ACTIVITY_RATE_WINDOW", "300"))      # req-rate bucket = 5 min
REQ_ALERT = int(os.getenv("ACTIVITY_REQ_ALERT", "400"))         # req/5min -> anomaly
GEOIP_DB_PATH = os.getenv("GEOIP_DB_PATH", "/workspace/geoip/GeoLite2-City.mmdb")
GEOIP_ASN_DB_PATH = os.getenv("GEOIP_ASN_DB_PATH", "/workspace/geoip/GeoLite2-ASN.mmdb")

# High-frequency legitimate endpoints (realtime inference, TTS) — still update
# the session heartbeat, but excluded from the anomaly rate counter so normal
# recognition isn't flagged as a bot.
_RATE_SKIP_PREFIXES = ("/api/v1/realtime", "/realtime", "/api/v1/tts", "/tts", "/api/v1/presence")
# Requests we don't record at all (health probes / preflight noise).
_RECORD_SKIP_PREFIXES = ("/health", "/api/v1/health")

_client = get_activity_client


# ---------------------------------------------------------------------------
# GeoIP (offline MaxMind GeoLite2)
# ---------------------------------------------------------------------------
_geo_reader = None
_geo_tried = False
_asn_reader = None
_asn_tried = False


def _get_geo_reader():
    global _geo_reader, _geo_tried
    if _geo_tried:
        return _geo_reader
    _geo_tried = True
    try:
        import geoip2.database  # optional dependency

        if os.path.exists(GEOIP_DB_PATH):
            _geo_reader = geoip2.database.Reader(GEOIP_DB_PATH)
            logger.info("[ACTIVITY] GeoIP City DB loaded: %s", GEOIP_DB_PATH)
        else:
            logger.info("[ACTIVITY] GeoIP City DB not found at %s — location disabled", GEOIP_DB_PATH)
    except Exception as exc:
        logger.warning("[ACTIVITY] GeoIP City init failed (location disabled): %s", exc)
    return _geo_reader


def _get_asn_reader():
    """Optional ASN DB (GeoLite2-ASN) — resolves IP -> ISP / network operator."""
    global _asn_reader, _asn_tried
    if _asn_tried:
        return _asn_reader
    _asn_tried = True
    try:
        import geoip2.database  # optional dependency

        if os.path.exists(GEOIP_ASN_DB_PATH):
            _asn_reader = geoip2.database.Reader(GEOIP_ASN_DB_PATH)
            logger.info("[ACTIVITY] GeoIP ASN DB loaded: %s", GEOIP_ASN_DB_PATH)
        else:
            logger.info("[ACTIVITY] GeoIP ASN DB not found at %s — ISP disabled", GEOIP_ASN_DB_PATH)
    except Exception as exc:
        logger.warning("[ACTIVITY] GeoIP ASN init failed (ISP disabled): %s", exc)
    return _asn_reader


def _is_private(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except Exception:
        return True  # unknown / non-IP -> treat as local, skip lookup


def geo_lookup(ip: str) -> Dict[str, Any]:
    """IP -> {country, country_code, city, lat, lon}. Empty if local/unknown.

    Cached in Redis (24h). Private/LAN IPs are marked local and never looked up.
    """
    if not ip or _is_private(ip):
        return {"local": True}
    c = _client()
    ckey = f"act:geo:{ip}"
    if c is not None:
        try:
            cached = c.get(ckey)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
    geo: Dict[str, Any] = {}
    reader = _get_geo_reader()
    if reader is not None:
        try:
            r = reader.city(ip)
            geo = {
                "country": r.country.name,
                "country_code": r.country.iso_code,
                "city": r.city.name,
                "lat": r.location.latitude,
                "lon": r.location.longitude,
            }
        except Exception:
            geo = {}
    asn_reader = _get_asn_reader()
    if asn_reader is not None:
        try:
            a = asn_reader.asn(ip)
            geo["isp"] = a.autonomous_system_organization
            geo["asn"] = a.autonomous_system_number
        except Exception:
            pass
    if c is not None:
        try:
            c.set(ckey, json.dumps(geo), ex=86400)
        except Exception:
            pass
    return geo


def _loc_str(geo: Dict[str, Any]) -> str:
    if not geo or geo.get("local"):
        return "Nội bộ / LAN"
    parts = [p for p in (geo.get("city"), geo.get("country")) if p]
    return ", ".join(parts) if parts else "Không rõ"


# ---------------------------------------------------------------------------
# UA parsing (tiny heuristic — enough for an at-a-glance column)
# ---------------------------------------------------------------------------
def _browser(ua: str) -> str:
    u = (ua or "").lower()
    if not u:
        return "—"
    if "edg/" in u or "edga" in u:
        base = "Edge"
    elif "chrome" in u and "chromium" not in u:
        base = "Chrome"
    elif "firefox" in u:
        base = "Firefox"
    elif "safari" in u and "chrome" not in u:
        base = "Safari"
    elif "python" in u or "curl" in u or "wget" in u or "httpx" in u:
        base = "Script/Bot"
    else:
        base = "Khác"
    if "mobile" in u or "android" in u or "iphone" in u:
        base += " (mobile)"
    return base


# ---------------------------------------------------------------------------
# Recording (called from middleware, best-effort)
# ---------------------------------------------------------------------------
def _user_id_from_request(request: Request) -> Optional[str]:
    """Cheap JWT decode of the access cookie to attribute activity (no DB)."""
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm],
                             options={"verify_aud": False, "verify_exp": False})
        return str(payload.get("sub") or "") or None
    except Exception:
        return None


def should_record(path: str) -> bool:
    return not any(path.startswith(p) for p in _RECORD_SKIP_PREFIXES)


def guard(request: Request, enforce_block: bool = True) -> Optional[Dict[str, Any]]:
    """Middleware helper: return the block record if the request must be blocked
    (403), otherwise record it and return None. Runs in a threadpool (sync Redis)
    so it never blocks the event loop. Fail-open on every error."""
    try:
        if enforce_block:
            blk = get_block(client_ip(request))
            if blk is not None:
                return blk
    except Exception:
        pass
    record(request)
    return None


def record(request: Request) -> None:
    """Record one request against its client IP. Never raises."""
    c = _client()
    if c is None:
        return
    try:
        path = request.url.path
        if not should_record(path):
            return
        ip = client_ip(request)
        now = time.time()
        ua = (request.headers.get("user-agent", "") or "")[:220]
        uid = _user_id_from_request(request)

        skey = f"act:sess:{ip}"
        pipe = c.pipeline()
        mapping = {"ip": ip, "ua": ua, "last_path": path,
                   "last_method": request.method, "last_seen": now}
        if uid:
            mapping["user_id"] = uid
        pipe.hset(skey, mapping=mapping)
        pipe.hsetnx(skey, "first_seen", now)
        pipe.expire(skey, ONLINE_TTL)
        pipe.zadd("act:active", {ip: now})
        pipe.expire("act:active", ONLINE_TTL * 4)
        if not any(path.startswith(p) for p in _RATE_SKIP_PREFIXES):
            bucket = int(now // RATE_WINDOW)
            rkey = f"act:rate:{ip}:{bucket}"
            pipe.incr(rkey)
            pipe.expire(rkey, RATE_WINDOW * 2)
        pipe.execute()
    except Exception:
        pass


def record_presence(ip: str, lat: Any, lon: Any, acc: Any) -> None:
    """Store a browser-reported precise GPS position on the session (best-effort).

    Called by the /api/v1/presence heartbeat. The middleware already recorded the
    request itself, so this only attaches the precise coordinates + refreshes TTL.
    """
    c = _client()
    if c is None or not ip:
        return
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return
    if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
        return
    try:
        skey = f"act:sess:{ip}"
        pipe = c.pipeline()
        pipe.hset(skey, mapping={
            "plat": lat_f, "plon": lon_f,
            "pacc": float(acc) if acc is not None else 0.0,
            "pts": time.time(),
        })
        pipe.expire(skey, ONLINE_TTL)
        pipe.execute()
    except Exception:
        pass


def list_sessions(limit: int = 100) -> List[Dict[str, Any]]:
    c = _client()
    if c is None:
        return []
    now = time.time()
    try:
        c.zremrangebyscore("act:active", 0, now - ONLINE_TTL)
        pairs = c.zrevrange("act:active", 0, limit - 1, withscores=True)
    except Exception:
        return []

    bucket = int(now // RATE_WINDOW)
    raw = []
    user_ids: Set[str] = set()
    for ip, score in pairs:
        try:
            h = c.hgetall(f"act:sess:{ip}") or {}
            rate = c.get(f"act:rate:{ip}:{bucket}")
            blocked = bool(c.exists(_block_key(ip)))
        except Exception:
            continue
        uid = h.get("user_id")
        if uid:
            user_ids.add(uid)
        raw.append((ip, float(score), h, int(rate or 0), blocked))

    umap = _resolve_usernames(user_ids)
    sessions = []
    for ip, score, h, rate, blocked in raw:
        uid = h.get("user_id")
        uinfo = umap.get(uid, {}) if uid else {}
        geo = geo_lookup(ip)
        precise = None
        if h.get("plat") and h.get("plon"):
            try:
                pts = float(h.get("pts") or 0)
                if now - pts < ONLINE_TTL:  # only if reasonably fresh
                    precise = {
                        "lat": float(h["plat"]),
                        "lon": float(h["plon"]),
                        "accuracy": round(float(h.get("pacc") or 0), 0),
                        "age_s": round(now - pts, 1),
                    }
            except Exception:
                precise = None
        sessions.append({
            "ip": ip,
            "user_id": uid,
            "username": uinfo.get("username"),
            "is_admin": uinfo.get("is_admin", False),
            "browser": _browser(h.get("ua", "")),
            "user_agent": h.get("ua", ""),
            "last_path": h.get("last_path", ""),
            "last_seen": score,
            "seconds_ago": round(now - score, 1),
            "online": (now - score) < ONLINE_ACTIVE_SECONDS,
            "req_window": rate,
            "location": _loc_str(geo),
            "isp": geo.get("isp"),
            "precise": precise,
            "geo": geo,
            "blocked": blocked,
        })
    return sessions


def detect_anomalies(sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for s in sessions:
        if s["req_window"] >= REQ_ALERT:
            out.append({
                "level": "warning",
                "ip": s["ip"],
                "location": s["location"],
                "message": f"{s['ip']} ({s['location']}): {s['req_window']} request/5 phút — nghi bot/quét",
            })
    # Failed-login bursts (reuse the auth rate-limiter's per-IP counters).
    c = _client()
    if c is not None:
        try:
            from app.rate_limit import LOGIN_MAX_ATTEMPTS

            for key in c.scan_iter(match="ratelimit:login:ip:*", count=200):
                try:
                    cnt = int(c.get(key) or 0)
                except Exception:
                    continue
                if cnt >= LOGIN_MAX_ATTEMPTS:
                    ip = key.split(":")[-1]
                    out.append({
                        "level": "critical",
                        "ip": ip,
                        "location": _loc_str(geo_lookup(ip)),
                        "message": f"{ip} ({_loc_str(geo_lookup(ip))}): {cnt} lần đăng nhập sai — nghi dò mật khẩu",
                    })
        except Exception:
            pass
    return out


def activity_report(limit: int = 100) -> Dict[str, Any]:
    sessions = list_sessions(limit)
    return {
        "sessions": sessions,
        "online_count": sum(1 for s in sessions if s["online"]),
        "anomalies": detect_anomalies(sessions),
        "blocked": list_blocked(),
        "security_log": list_security_log(limit=100),
        "geoip_enabled": _get_geo_reader() is not None,
        "asn_enabled": _get_asn_reader() is not None,
    }
