"""Per-user / per-IP activity tracking for the admin activity monitor.

Multi-user web: the admin needs to see who is connected, from where (IP +
geolocation), how heavily each is using the service, plus a way to react —
block an abusive IP or force-logout a user.

Everything here is **best-effort and fail-open**: monitoring must never break a
real request. Redis down => tracking silently no-ops; requests still flow.

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
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import redis
from fastapi import Request
from jose import jwt

from app.config import settings
from app.cookie_auth import ACCESS_COOKIE
from app.rate_limit import client_ip

logger = logging.getLogger("activity")

_REDIS_URL = os.getenv("REDIS_URL", getattr(settings, "broker_url", "redis://redis:6379/0"))

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

_client_singleton: Optional[redis.Redis] = None
_client_failed = False


def _client() -> Optional[redis.Redis]:
    global _client_singleton, _client_failed
    if _client_singleton is not None:
        return _client_singleton
    if _client_failed:
        return None
    try:
        c = redis.from_url(_REDIS_URL, decode_responses=True,
                           socket_connect_timeout=2, socket_timeout=3)
        c.ping()
        _client_singleton = c
        return c
    except Exception as exc:  # pragma: no cover
        logger.warning("[ACTIVITY] Redis unavailable, tracking disabled: %s", exc)
        _client_failed = True
        return None


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


# ---------------------------------------------------------------------------
# Blocklist (enforced in middleware) — one key per IP with an optional TTL, so
# timed blocks auto-expire. Value carries who/when/why + expiry.
# ---------------------------------------------------------------------------
_BLOCK_PREFIX = "block:ip:"


def _block_key(ip: str) -> str:
    return f"{_BLOCK_PREFIX}{ip}"


def is_blocked(ip: str) -> bool:
    c = _client()
    if c is None or not ip:
        return False
    try:
        return bool(c.exists(_block_key(ip)))
    except Exception:
        return False


def get_block(ip: str) -> Optional[Dict[str, Any]]:
    """Full block record for an IP (reason/by/until + remaining ttl), or None."""
    c = _client()
    if c is None or not ip:
        return None
    try:
        raw = c.get(_block_key(ip))
        if not raw:
            return None
        d = json.loads(raw)
        ttl = c.ttl(_block_key(ip))
        d["ttl"] = ttl if ttl and ttl > 0 else 0  # 0 => permanent
        return d
    except Exception:
        return None


def block_ip(ip: str, by: str = "", reason: str = "", duration_seconds: int = 0) -> bool:
    """Block an IP. duration_seconds<=0 => permanent; otherwise auto-expires."""
    c = _client()
    if c is None or not ip:
        return False
    try:
        dur = int(duration_seconds or 0)
        until = (time.time() + dur) if dur > 0 else 0
        payload = json.dumps({"by": by, "at": time.time(), "reason": reason, "until": until})
        if dur > 0:
            c.set(_block_key(ip), payload, ex=dur)
        else:
            c.set(_block_key(ip), payload)
        logger.info("[ACTIVITY] IP blocked: %s by=%s dur=%ss reason=%s", ip, by, dur, (reason or "")[:40])
        return True
    except Exception:
        return False


def unblock_ip(ip: str) -> bool:
    c = _client()
    if c is None or not ip:
        return False
    try:
        c.delete(_block_key(ip))
        return True
    except Exception:
        return False


def list_blocked() -> List[Dict[str, Any]]:
    c = _client()
    if c is None:
        return []
    out: List[Dict[str, Any]] = []
    try:
        for key in c.scan_iter(match=f"{_BLOCK_PREFIX}*", count=200):
            ip = key[len(_BLOCK_PREFIX):]
            raw = c.get(key)
            if not raw:
                continue
            try:
                d = json.loads(raw)
            except Exception:
                d = {}
            ttl = c.ttl(key)
            out.append({
                "ip": ip, "by": d.get("by", ""), "at": d.get("at"),
                "reason": d.get("reason", ""), "until": d.get("until", 0),
                "ttl": ttl if ttl and ttl > 0 else 0,
            })
        return out
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Security audit log (admin actions) — capped Redis list
# ---------------------------------------------------------------------------
def log_security_event(action: str, actor: str = "", target: str = "",
                       reason: str = "", extra: Optional[Dict[str, Any]] = None,
                       actor_user: Optional[Dict[str, Any]] = None,
                       request: Any = None) -> None:
    """Ghi một hành động quản trị vào CẢ HAI nhật ký, và đó là chủ ý.

    Hai kho, hai câu hỏi khác nhau
    ------------------------------
    Danh sách Redis `sec:log` trả lời *"vừa có chuyện gì?"* — nó nhanh, rẻ, và
    là thứ trang Hoạt động hiển thị. Nó cũng bị `ltrim` về 500 mục và nằm trên
    một Redis chạy `volatile-lru`, nên nó **có thể mất dòng**.

    Bảng `audit_log` trả lời *"ai đã làm gì, tháng trước"*. Nó có RLS, có chỉ
    mục, không bị đuổi, và không xoá được bằng một lần `FLUSHDB`.

    Trước bản này chỉ có nhánh Redis. Hệ quả cụ thể: mọi lần khoá tài khoản,
    chặn IP, hay ép đăng xuất — bảy lối gọi — chỉ tồn tại trong một danh sách
    500 mục mà hệ thống được phép tự xoá khi cần chỗ. Đó không phải dấu vết
    kiểm toán.

    Vì sao ghi hai chỗ chứ không chuyển hẳn sang Postgres: đường Redis đang
    phục vụ giao diện và không hỏng; thay nó là đổi một thứ đang chạy để lấy
    một thứ chưa chạy. Ghi thêm thì cộng dồn, không trừ đi.

    `actor` là **chuỗi tên** để hiển thị; `actor_user` là dict người dùng đầy
    đủ để `audit.record` điền được khoá ngoại `actor_user_id`. Hai tham số chứ
    không phải một vì nhánh Redis chỉ cần chuỗi, và ép mọi lối gọi phải có
    dict là ép thêm việc lên những chỗ không có sẵn.

    Ghi hỏng ở một nhánh KHÔNG được kéo nhánh kia xuống theo — mỗi nhánh có
    `try` riêng. Cùng lập luận với `audit.record`: nhật ký hỏng không được biến
    một hành động quản trị đã thành công thành lỗi 500.
    """
    # Bản BỀN ghi trước. Cửa sổ giữa hai lượt ghi chỉ vài mili giây, nhưng nếu
    # tiến trình chết đúng lúc đó thì thứ tự quyết định cái nào sống sót — và
    # cái đáng giữ là cái không bị đuổi khỏi bộ nhớ.
    try:
        from app import audit

        detail: Dict[str, Any] = dict(extra or {})
        if reason:
            detail["reason"] = reason
        audit.record(
            f"security.{action}",
            actor=actor_user or ({"username": actor} if actor else None),
            target_type="security",
            target_id=target or None,
            detail=detail or None,
            request=request,
        )
    except Exception:
        # `audit.record` đã tự nuốt lỗi; cái `try` này chỉ che trường hợp import
        # hỏng ở môi trường cắt gọn.
        pass

    c = _client()
    if c is not None:
        try:
            entry = {"ts": time.time(), "action": action, "actor": actor,
                     "target": target, "reason": reason}
            if extra:
                entry.update(extra)
            c.lpush("sec:log", json.dumps(entry))
            c.ltrim("sec:log", 0, 499)
        except Exception:
            pass


def list_security_log(limit: int = 100) -> List[Dict[str, Any]]:
    c = _client()
    if c is None:
        return []
    try:
        out = []
        for r in c.lrange("sec:log", 0, max(0, limit - 1)):
            try:
                out.append(json.loads(r))
            except Exception:
                pass
        return out
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Force-logout (checked in auth.get_current_user_optional)
# ---------------------------------------------------------------------------
def force_logout_user(user_id: str, by: str = "", reason: str = "") -> bool:
    """Deny every access token this user holds NOW; revoke their refresh tokens.

    A fresh login afterwards works (its token iat is newer than the marker).
    Stores the reason so the client can tell the user why they were logged out.

    Ghi mốc vào CẢ Redis lẫn Postgres. Redis là đường nhanh (mỗi request đọc một
    lần), Postgres là đường bền. Trước đây mốc CHỈ nằm ở Redis, nghĩa là Redis
    khởi động lại — hoặc chỉ cần nấc một cái — là mọi lệnh thu hồi phiên của
    quản trị viên bốc hơi mà không có dòng nhật ký nào cho biết cơ chế đang mù.
    """
    if not user_id:
        return False
    ttl = int(settings.access_token_expire_minutes) * 60 + 120
    marker = time.time()
    c = _client()
    if c is not None:
        try:
            c.set(f"forcelogout:{user_id}",
                  json.dumps({"ts": marker, "by": by, "reason": reason}), ex=ttl)
        except Exception:
            pass
    _persist_force_logout_marker(user_id, marker)
    _revoke_all_refresh_tokens(user_id)
    logger.info("[ACTIVITY] force-logout user=%s by=%s", user_id, by)
    return True


def _persist_force_logout_marker(user_id: str, marker: float) -> None:
    """Hạ mốc force-logout xuống `users.sessions_invalid_before`.

    Chỉ tiến, không lùi (`GREATEST`): hai lệnh thu hồi gần nhau không được phép
    làm mốc trẻ lại, vì như thế là hồi sinh những token vừa bị đá.
    """
    try:
        from app.storage.postgres_connection import connect_postgres
        from app.storage.rls import apply_scope
        from app.tenant_context import system_scope

        # `apply_scope` là bắt buộc, không phải nghi thức: `users` có row-level
        # security, nên một kết nối KHÔNG scope không bị từ chối — nó chỉ đơn
        # giản khớp 0 dòng. Bản đầu thiếu dòng này và lệnh thu hồi phiên lặng lẽ
        # không ghi được gì; test `test_force_logout_ghi_ca_xuong_postgres` bắt.
        #
        # Thu hồi phiên là việc của mặt phẳng danh tính, chạy trước khi biết
        # tenant nào — cùng lý do với `auth._identity_cursor`.
        with system_scope("activity: thu hoi phien, mat phang danh tinh"):
            conn = connect_postgres(connect_timeout=5)
            try:
                with conn:
                    with conn.cursor() as cur:
                        apply_scope(cur)
                        cur.execute(
                            "UPDATE users SET sessions_invalid_before = "
                            "GREATEST(COALESCE(sessions_invalid_before, to_timestamp(0)), "
                            "to_timestamp(%s)) WHERE id = %s",
                            (marker, user_id),
                        )
                        if cur.rowcount == 0:
                            logger.error(
                                "[ACTIVITY] moc force-logout khong ghi duoc dong nao "
                                "cho user=%s — kiem tra scope/RLS", user_id,
                            )
            finally:
                conn.close()
    except Exception as exc:
        logger.error(
            "[ACTIVITY] KHONG ghi duoc moc force-logout ben cho user=%s: %s — "
            "lenh thu hoi nay chi song trong Redis", user_id, exc,
        )


def get_force_logout(user_id: str) -> Optional[Dict[str, Any]]:
    c = _client()
    if c is None or not user_id:
        return None
    try:
        v = c.get(f"forcelogout:{user_id}")
        if v is None:
            return None
        try:
            return json.loads(v)
        except Exception:
            return {"ts": float(v), "reason": ""}  # legacy plain-float value
    except Exception:
        return None


def is_user_denied(user_id: str, token_iat: Any) -> bool:
    """True if this token was issued before an active force-logout marker.

    Đường NHANH, đọc Redis. Vế bền nằm ở `auth.get_current_user_optional`, nơi
    nó đi ké truy vấn `_fetch_user_by_id` vốn đã chạy sẵn mỗi request — xem
    `token_predates_marker` bên dưới.

    Vì sao KHÔNG hỏi Postgres ngay tại đây, dù đó là chỗ trông có vẻ đúng nhất:
    hàm này chạy trên mọi request, và mở thêm một kết nối mỗi lần là đổi một lỗ
    bảo mật lấy một nút thắt cổ chai.
    """
    if not user_id:
        return False
    fl = get_force_logout(user_id)
    if not fl:
        return False
    try:
        return float(token_iat or 0) < float(fl.get("ts", 0))
    except Exception:
        return False


def token_predates_marker(token_iat: Any, marker: Any) -> bool:
    """Token cấp trước mốc thu hồi phiên chưa?

    `marker` là `users.sessions_invalid_before` — mốc BỀN, đọc kèm hồ sơ người
    dùng nên không tốn thêm truy vấn nào. Đây là vế cứu khi Redis chết hoặc khởi
    động lại: khoá Redis có TTL, còn cột Postgres thì không, nên một lệnh thu hồi
    đặt lúc Redis đang nghỉ vẫn có hiệu lực.
    """
    if marker is None:
        return False
    try:
        if hasattr(marker, "timestamp"):
            marker_ts = marker.timestamp()
        else:
            marker_ts = float(marker)
        return float(token_iat or 0) < marker_ts
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Access-token denylist (logout kills THIS session, not every device)
# ---------------------------------------------------------------------------
_JTI_DENY_PREFIX = "denyjti:"
_FAM_DENY_PREFIX = "denyfam:"


def deny_access_token(jti: str, expires_at: Any = None) -> bool:
    """Chặn đúng một access token cho tới khi nó tự hết hạn.

    TTL đặt bằng phần đời còn lại của chính token, nên danh sách chặn tự dọn —
    không có tác vụ quét nào phải viết, và bộ nhớ chiếm dụng có trần cứng bằng
    số phiên đang mở nhân với 60 phút.
    """
    if not jti:
        return False
    c = _client()
    if c is None:
        # Không im lặng bỏ qua: đăng xuất mà không chặn được token nghĩa là nút
        # "Đăng xuất" không làm đúng điều nó hứa, và người dùng phải biết cơ chế
        # đang mù chứ không phải đoán.
        logger.error("[ACTIVITY] khong co Redis — access token %s KHONG bi chan", jti)
        return False
    try:
        ttl = int(settings.access_token_expire_minutes) * 60 + 120
        if expires_at is not None:
            try:
                remaining = int(float(expires_at) - time.time()) + 5
                if remaining > 0:
                    ttl = min(ttl, remaining)
            except Exception:
                pass
        c.set(f"{_JTI_DENY_PREFIX}{jti}", "1", ex=max(1, ttl))
        return True
    except Exception as exc:
        logger.error("[ACTIVITY] chan access token %s that bai: %s", jti, exc)
        return False


def deny_token_family(family_id: str) -> bool:
    """Chặn mọi access token thuộc một HỌ (một lần đăng nhập = một họ).

    Dùng khi phát hiện refresh token bị dùng lại: cả nhánh phiên đó không còn
    đáng tin, nhưng các thiết bị khác của cùng người dùng thì vẫn đáng tin.
    Đó là khác biệt giữa hàm này và `force_logout_user`.
    """
    if not family_id:
        return False
    c = _client()
    if c is None:
        logger.error("[ACTIVITY] khong co Redis — ho token %s KHONG bi chan", family_id)
        return False
    try:
        # TTL bằng một vòng đời access token: sau chừng đó mọi token của họ đều
        # đã tự hết hạn, và refresh token thì đã chết trong Postgres vĩnh viễn
        # (`reuse_detected_at`), nên khoá Redis hết hạn không hồi sinh được gì.
        ttl = int(settings.access_token_expire_minutes) * 60 + 120
        c.set(f"{_FAM_DENY_PREFIX}{family_id}", "1", ex=ttl)
        return True
    except Exception as exc:
        logger.error("[ACTIVITY] chan ho token %s that bai: %s", family_id, exc)
        return False


def is_token_family_denied(family_id: str) -> bool:
    if not family_id:
        return False
    c = _client()
    if c is None:
        return False
    try:
        return c.get(f"{_FAM_DENY_PREFIX}{family_id}") is not None
    except Exception:
        return False


def is_access_token_denied(jti: str) -> bool:
    """True nếu token này đã bị đăng xuất. Redis chết thì trả False (fail-open).

    Fail-open ở đây chấp nhận được vì nó chỉ nới cho token đã bị đăng xuất sống
    nốt phần đời tối đa 60 phút — đúng bằng hành vi TRƯỚC bản vá này, chứ không
    mở thêm gì mới.
    """
    if not jti:
        return False
    c = _client()
    if c is None:
        return False
    try:
        return c.get(f"{_JTI_DENY_PREFIX}{jti}") is not None
    except Exception:
        return False


def _revoke_all_refresh_tokens(user_id: str) -> None:
    try:
        from app.storage.postgres_connection import connect_postgres

        conn = connect_postgres(connect_timeout=5)
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE refresh_tokens SET revoked_at = NOW() "
                        "WHERE user_id = %s AND revoked_at IS NULL",
                        (user_id,),
                    )
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("[ACTIVITY] revoke refresh tokens failed for %s: %s", user_id, exc)


# ---------------------------------------------------------------------------
# Account lock (disable a user for a reason + optional duration) & warnings
# ---------------------------------------------------------------------------
_USERLOCK_PREFIX = "userlock:"
_USERWARN_PREFIX = "userwarn:"


def _userlock_key(uid: str) -> str:
    return f"{_USERLOCK_PREFIX}{uid}"


def _fmt_until(until: float) -> str:
    if not until:
        return ""
    try:
        return datetime.fromtimestamp(until).strftime("%H:%M %d/%m/%Y")
    except Exception:
        return ""


def lock_user(user_id: str, by: str = "", reason: str = "", duration_seconds: int = 0) -> bool:
    """Disable an account (optionally timed) and cut off its live sessions now."""
    if not user_id:
        return False
    c = _client()
    if c is None:
        return False
    try:
        dur = int(duration_seconds or 0)
        until = (time.time() + dur) if dur > 0 else 0
        c.set(_userlock_key(user_id),
              json.dumps({"by": by, "at": time.time(), "reason": reason, "until": until}),
              **({"ex": dur} if dur > 0 else {}))
        # Immediately end any active sessions with a clear message.
        msg = f"Tài khoản của bạn đã bị khóa. Lý do: {reason or 'vi phạm quy định'}"
        if until:
            msg += f" (đến {_fmt_until(until)})"
        force_logout_user(user_id, by=by, reason=msg)
        logger.info("[ACTIVITY] user locked: %s by=%s dur=%ss", user_id, by, dur)
        return True
    except Exception:
        return False


def unlock_user(user_id: str) -> bool:
    c = _client()
    if c is None or not user_id:
        return False
    try:
        c.delete(_userlock_key(user_id))
        return True
    except Exception:
        return False


def get_user_lock(user_id: str) -> Optional[Dict[str, Any]]:
    c = _client()
    if c is None or not user_id:
        return None
    try:
        raw = c.get(_userlock_key(user_id))
        if not raw:
            return None
        d = json.loads(raw)
        ttl = c.ttl(_userlock_key(user_id))
        d["ttl"] = ttl if ttl and ttl > 0 else 0
        return d
    except Exception:
        return None


def is_user_locked(user_id: str) -> bool:
    c = _client()
    if c is None or not user_id:
        return False
    try:
        return bool(c.exists(_userlock_key(user_id)))
    except Exception:
        return False


def list_locked_users() -> Dict[str, Dict[str, Any]]:
    c = _client()
    if c is None:
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    try:
        for key in c.scan_iter(match=f"{_USERLOCK_PREFIX}*", count=200):
            uid = key[len(_USERLOCK_PREFIX):]
            raw = c.get(key)
            try:
                d = json.loads(raw) if raw else {}
            except Exception:
                d = {}
            ttl = c.ttl(key)
            d["ttl"] = ttl if ttl and ttl > 0 else 0
            out[uid] = d
        return out
    except Exception:
        return {}


def warn_user(user_id: str, by: str = "", message: str = "") -> bool:
    """Queue a one-off warning the user will see on their next visit."""
    c = _client()
    if c is None or not user_id:
        return False
    try:
        c.set(f"{_USERWARN_PREFIX}{user_id}",
              json.dumps({"by": by, "at": time.time(), "message": message}),
              ex=30 * 86400)
        return True
    except Exception:
        return False


def get_user_warning(user_id: str) -> Optional[Dict[str, Any]]:
    c = _client()
    if c is None or not user_id:
        return None
    try:
        raw = c.get(f"{_USERWARN_PREFIX}{user_id}")
        return json.loads(raw) if raw else None
    except Exception:
        return None


def ack_user_warning(user_id: str) -> None:
    c = _client()
    if c is None or not user_id:
        return
    try:
        c.delete(f"{_USERWARN_PREFIX}{user_id}")
    except Exception:
        pass


def list_warned_users() -> Set[str]:
    c = _client()
    if c is None:
        return set()
    try:
        return {key[len(_USERWARN_PREFIX):] for key in c.scan_iter(match=f"{_USERWARN_PREFIX}*", count=200)}
    except Exception:
        return set()


# ---------------------------------------------------------------------------
# Read side (admin endpoint)
# ---------------------------------------------------------------------------
def _resolve_usernames(user_ids: Set[str]) -> Dict[str, str]:
    ids = [u for u in user_ids if u]
    if not ids:
        return {}
    try:
        from app.storage.postgres_connection import connect_postgres
        from psycopg2.extras import RealDictCursor

        conn = connect_postgres(connect_timeout=5)
        try:
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # id is a UUID column; compare as text so a Python list of
                    # string ids matches without an explicit uuid[] cast.
                    cur.execute("SELECT id, username, is_admin FROM users WHERE id::text = ANY(%s)", (ids,))
                    return {str(r["id"]): {"username": r["username"], "is_admin": bool(r["is_admin"])}
                            for r in cur.fetchall()}
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("[ACTIVITY] username resolve failed: %s", exc)
        return {}


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
            # Same threshold the limiter itself warns at. Deliberately NOT the
            # per-pair backoff trigger: a handful of failures from one address
            # is a typo, and campus/VPN networks put hundreds of users behind
            # one IP — flagging those as "critical" buries the real bursts.
            from app.rate_limit import LOGIN_IP_WARN_ATTEMPTS

            for key in c.scan_iter(match="ratelimit:login:ip:*", count=200):
                try:
                    cnt = int(c.get(key) or 0)
                except Exception:
                    continue
                if cnt >= LOGIN_IP_WARN_ATTEMPTS:
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
