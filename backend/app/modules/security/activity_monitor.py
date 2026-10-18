"""Best-effort request, presence, and online-session monitoring."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Set

from fastapi import Request
from jose import jwt

from app.config import settings
from app.cookie_auth import ACCESS_COOKIE
from app.infrastructure.redis.connection import get_activity_client
from app.modules.security.account_controls import resolve_usernames
from app.modules.security.audit_log import list_security_log
from app.modules.security.geo import (
    geo_lookup,
    get_asn_reader,
    get_geo_reader,
    location_label,
)
from app.modules.security.ip_controls import block_key, get_block, list_blocked
from app.rate_limit import client_ip

ONLINE_TTL = int(os.getenv("ACTIVITY_ONLINE_TTL", "600"))
ONLINE_ACTIVE_SECONDS = int(os.getenv("ACTIVITY_ACTIVE_SECONDS", "120"))
RATE_WINDOW = int(os.getenv("ACTIVITY_RATE_WINDOW", "300"))
REQ_ALERT = int(os.getenv("ACTIVITY_REQ_ALERT", "400"))

RATE_SKIP_PREFIXES = ("/api/v1/realtime", "/realtime", "/api/v1/tts", "/tts", "/api/v1/presence")
RECORD_SKIP_PREFIXES = ("/health", "/api/v1/health")


def browser_name(user_agent: str) -> str:
    value = (user_agent or "").lower()
    if not value:
        return "—"
    if "edg/" in value or "edga" in value:
        name = "Edge"
    elif "chrome" in value and "chromium" not in value:
        name = "Chrome"
    elif "firefox" in value:
        name = "Firefox"
    elif "safari" in value and "chrome" not in value:
        name = "Safari"
    elif any(agent in value for agent in ("python", "curl", "wget", "httpx")):
        name = "Script/Bot"
    else:
        name = "Khác"
    if any(device in value for device in ("mobile", "android", "iphone")):
        name += " (mobile)"
    return name


def user_id_from_request(request: Request) -> Optional[str]:
    """Decode an access token without a database lookup for attribution only."""
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:]
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"verify_aud": False, "verify_exp": False},
        )
        return str(payload.get("sub") or "") or None
    except Exception:
        return None


def should_record(path: str) -> bool:
    return not any(path.startswith(prefix) for prefix in RECORD_SKIP_PREFIXES)


def guard(request: Request, enforce_block: bool = True) -> Optional[Dict[str, Any]]:
    """Return a block record when denied; otherwise record and fail open."""
    try:
        if enforce_block:
            blocked = get_block(client_ip(request))
            if blocked is not None:
                return blocked
    except Exception:
        pass
    record(request)
    return None


def record(request: Request) -> None:
    client = get_activity_client()
    if client is None:
        return
    try:
        path = request.url.path
        if not should_record(path):
            return
        ip = client_ip(request)
        now = time.time()
        user_agent = (request.headers.get("user-agent", "") or "")[:220]
        user_id = user_id_from_request(request)

        session_key = f"act:sess:{ip}"
        pipe = client.pipeline()
        mapping = {
            "ip": ip,
            "ua": user_agent,
            "last_path": path,
            "last_method": request.method,
            "last_seen": now,
        }
        if user_id:
            mapping["user_id"] = user_id
        pipe.hset(session_key, mapping=mapping)
        pipe.hsetnx(session_key, "first_seen", now)
        pipe.expire(session_key, ONLINE_TTL)
        pipe.zadd("act:active", {ip: now})
        pipe.expire("act:active", ONLINE_TTL * 4)
        if not any(path.startswith(prefix) for prefix in RATE_SKIP_PREFIXES):
            bucket = int(now // RATE_WINDOW)
            rate_key = f"act:rate:{ip}:{bucket}"
            pipe.incr(rate_key)
            pipe.expire(rate_key, RATE_WINDOW * 2)
        pipe.execute()
    except Exception:
        pass


def record_presence(ip: str, lat: Any, lon: Any, acc: Any) -> None:
    client = get_activity_client()
    if client is None or not ip:
        return
    try:
        latitude = float(lat)
        longitude = float(lon)
    except (TypeError, ValueError):
        return
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return
    try:
        session_key = f"act:sess:{ip}"
        pipe = client.pipeline()
        pipe.hset(
            session_key,
            mapping={
                "plat": latitude,
                "plon": longitude,
                "pacc": float(acc) if acc is not None else 0.0,
                "pts": time.time(),
            },
        )
        pipe.expire(session_key, ONLINE_TTL)
        pipe.execute()
    except Exception:
        pass


def list_sessions(limit: int = 100) -> List[Dict[str, Any]]:
    client = get_activity_client()
    if client is None:
        return []
    now = time.time()
    try:
        client.zremrangebyscore("act:active", 0, now - ONLINE_TTL)
        pairs = client.zrevrange("act:active", 0, limit - 1, withscores=True)
    except Exception:
        return []

    bucket = int(now // RATE_WINDOW)
    raw = []
    user_ids: Set[str] = set()
    for ip, score in pairs:
        try:
            values = client.hgetall(f"act:sess:{ip}") or {}
            rate = client.get(f"act:rate:{ip}:{bucket}")
            blocked = bool(client.exists(block_key(ip)))
        except Exception:
            continue
        user_id = values.get("user_id")
        if user_id:
            user_ids.add(user_id)
        raw.append((ip, float(score), values, int(rate or 0), blocked))

    user_map = resolve_usernames(user_ids)
    sessions = []
    for ip, score, values, rate, blocked in raw:
        user_id = values.get("user_id")
        user_info = user_map.get(user_id, {}) if user_id else {}
        geo = geo_lookup(ip)
        precise = None
        if values.get("plat") and values.get("plon"):
            try:
                position_time = float(values.get("pts") or 0)
                if now - position_time < ONLINE_TTL:
                    precise = {
                        "lat": float(values["plat"]),
                        "lon": float(values["plon"]),
                        "accuracy": round(float(values.get("pacc") or 0), 0),
                        "age_s": round(now - position_time, 1),
                    }
            except Exception:
                precise = None
        sessions.append({
            "ip": ip,
            "user_id": user_id,
            "username": user_info.get("username"),
            "is_admin": user_info.get("is_admin", False),
            "browser": browser_name(values.get("ua", "")),
            "user_agent": values.get("ua", ""),
            "last_path": values.get("last_path", ""),
            "last_seen": score,
            "seconds_ago": round(now - score, 1),
            "online": (now - score) < ONLINE_ACTIVE_SECONDS,
            "req_window": rate,
            "location": location_label(geo),
            "isp": geo.get("isp"),
            "precise": precise,
            "geo": geo,
            "blocked": blocked,
        })
    return sessions


def detect_anomalies(sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for session in sessions:
        if session["req_window"] >= REQ_ALERT:
            output.append({
                "level": "warning",
                "ip": session["ip"],
                "location": session["location"],
                "message": (
                    f"{session['ip']} ({session['location']}): "
                    f"{session['req_window']} request/5 phút — nghi bot/quét"
                ),
            })

    client = get_activity_client()
    if client is not None:
        try:
            from app.rate_limit import LOGIN_MAX_ATTEMPTS

            for key in client.scan_iter(match="ratelimit:login:ip:*", count=200):
                try:
                    count = int(client.get(key) or 0)
                except Exception:
                    continue
                if count >= LOGIN_MAX_ATTEMPTS:
                    ip = key.split(":")[-1]
                    location = location_label(geo_lookup(ip))
                    output.append({
                        "level": "critical",
                        "ip": ip,
                        "location": location,
                        "message": f"{ip} ({location}): {count} lần đăng nhập sai — nghi dò mật khẩu",
                    })
        except Exception:
            pass
    return output


def activity_report(limit: int = 100) -> Dict[str, Any]:
    sessions = list_sessions(limit)
    return {
        "sessions": sessions,
        "online_count": sum(1 for session in sessions if session["online"]),
        "anomalies": detect_anomalies(sessions),
        "blocked": list_blocked(),
        "security_log": list_security_log(limit=100),
        "geoip_enabled": get_geo_reader() is not None,
        "asn_enabled": get_asn_reader() is not None,
    }
