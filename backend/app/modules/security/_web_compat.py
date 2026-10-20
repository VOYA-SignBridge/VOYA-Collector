"""Redis-backed abuse limiter for the auth endpoints.

Login is gated by ONE blocking rule and two observation-only ones.

Blocking — the pair (identifier, client IP):
    failures 1..10   allowed
    failure 11       wait 30s
    failure 12       wait 2m
    failure 13       wait 5m
    failure 14+      wait 15m (ceiling)

Keying the block on the PAIR, not on the identifier alone, is the whole point.
A block keyed on the identifier lets anyone who knows your email lock you out
for as long as they care to keep typing — the attacker's failures and yours land
in the same bucket. On the pair, an attacker at another address only ever blocks
themselves. This is why the large platforms throttle-and-challenge instead of
locking accounts, and it is what NIST SP 800-63B means by rate-limiting rather
than lockout.

While a pair is blocked the password is never checked, the counter does not grow
and the wait is not extended: `check_login_allowed` raises before
`register_failed_login` can run. Without that, one wrong keystroke right after a
block expired would re-arm the full penalty — the exact trap the previous
version fell into, where a stale 30-minute counter still sat above the threshold
and every later failure re-armed a fresh 15-minute lock.

Observation only — never refuses a login:
  - per identifier across all IPs → many sources hammering one account
    (distributed / targeted attack)
  - per IP across all identifiers → one source hammering many accounts
    (credential stuffing, password spraying)

The per-IP rule does hard-block, but only at flood scale (1000 failures in 10
minutes). It has to stay loose: campus, dorm, office, VPN and mobile-carrier
networks put hundreds of legitimate users behind one address, so a tight per-IP
limit locks out a whole building to slow one attacker down.

Redis being unavailable fails OPEN (requests allowed). The nginx edge rate-limit
still caps raw flood, and locking every user out on a Redis hiccup would be
worse than the residual risk. All failures here are best-effort.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import os
import time
from typing import List, Optional, Tuple

import redis
from fastapi import HTTPException, Request, status

from app.config import settings

logger = logging.getLogger(__name__)

_REDIS_URL = os.getenv("REDIS_URL", getattr(settings, "broker_url", "redis://redis:6379/0"))


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        logger.warning("[ratelimit] %s không phải số nguyên — dùng %d", name, default)
        return default


def _steps_env(name: str, default: str) -> List[int]:
    raw = os.getenv(name, default)
    steps = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            steps.append(max(1, int(part)))
        except ValueError:
            logger.warning("[ratelimit] %s: bỏ qua bậc không hợp lệ %r", name, part)
    return steps or [int(s) for s in default.split(",")]


# --- (identifier, IP) pair: the only rule that refuses a login ---------------
LOGIN_PAIR_FREE_FAILURES = _int_env("LOGIN_PAIR_FREE_FAILURES", 10)
LOGIN_PAIR_BACKOFF_STEPS = _steps_env("LOGIN_PAIR_BACKOFF_STEPS", "30,120,300,900")
# The failure streak is forgotten after this long with no further failure, so a
# user who mistypes today does not start tomorrow one keystroke from a penalty.
LOGIN_PAIR_WINDOW = _int_env("LOGIN_PAIR_WINDOW", 3600)

# --- per-IP: mostly telemetry, hard block only at flood scale ----------------
LOGIN_IP_WINDOW = _int_env("LOGIN_IP_WINDOW", 600)
LOGIN_IP_WARN_ATTEMPTS = _int_env("LOGIN_IP_WARN_ATTEMPTS", 200)
LOGIN_IP_HIGH_RISK_ATTEMPTS = _int_env("LOGIN_IP_HIGH_RISK_ATTEMPTS", 500)
LOGIN_IP_HARD_LIMIT = _int_env("LOGIN_IP_HARD_LIMIT", 1000)
LOGIN_IP_HARD_BLOCK = _int_env("LOGIN_IP_HARD_BLOCK", 600)
# One address trying many different accounts is password spraying.
LOGIN_IP_DISTINCT_IDENTIFIER_WARN = _int_env("LOGIN_IP_DISTINCT_IDENTIFIER_WARN", 50)
# One account tried from many addresses is a distributed attack on that account.
LOGIN_ID_DISTINCT_IP_WARN = _int_env("LOGIN_ID_DISTINCT_IP_WARN", 10)

# --- registration: request rate is tight, account count is mostly telemetry ---
# Two different questions, so two different counters. The per-minute one counts
# every ATTEMPT (a validation error is still a request) and stops a script from
# hammering the endpoint. The daily one counts accounts that were actually
# CREATED, because that is the number an operator cares about — and it stays
# loose, since a class registering together from one campus address is normal
# and must not be mistaken for a spam run.
REGISTER_REQUESTS_PER_MINUTE = _int_env("REGISTER_REQUESTS_PER_MINUTE", 10)
REGISTER_ACCOUNTS_WINDOW = _int_env("REGISTER_ACCOUNTS_WINDOW", 86400)
REGISTER_ACCOUNTS_WARN = _int_env("REGISTER_ACCOUNTS_WARN", 20)
REGISTER_ACCOUNTS_HIGH_RISK = _int_env("REGISTER_ACCOUNTS_HIGH_RISK", 50)
REGISTER_ACCOUNTS_HARD_LIMIT = _int_env("REGISTER_ACCOUNTS_HARD_LIMIT", 100)

# Addresses allowed to speak for someone else via X-Real-IP / X-Forwarded-For.
# Default covers loopback plus the private ranges Docker/Compose networks live
# in, which is where the nginx gateway sits. The backend itself is never
# published (compose uses `expose`, not `ports`), so nothing outside the network
# can reach it directly and forge these headers.
TRUSTED_PROXIES = os.getenv(
    "TRUSTED_PROXIES",
    "127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
)

_KEY_PREFIX = "ratelimit:"

_client_singleton: Optional[redis.Redis] = None

#: Thời điểm sớm nhất được thử kết nối lại sau một lần thất bại. 0 = thử ngay.
_client_retry_at: float = 0.0

#: Bao lâu thì thử lại. Đủ dài để một Redis đang chết không bị 5 lượt/giây gõ
#: cửa, đủ ngắn để một cú chớp không tắt giới hạn tần suất quá vài chục giây.
_RETRY_COOLDOWN_SECONDS = 30.0


def _client() -> Optional[redis.Redis]:
    """Kết nối Redis dùng chung, hoặc None khi Redis không với tới được.

    **Thử lại sau một khoảng, KHÔNG chốt vĩnh viễn.**

    Bản trước đặt `_client_failed = True` và không bao giờ gỡ. Nghĩa là MỘT lần
    Redis chớp — một `socket_timeout` 3 giây trong lúc redis bận, một lần
    recreate container khi triển khai — sẽ tắt **toàn bộ** giới hạn tần suất
    cho tới khi tiến trình khởi động lại: chống dò mật khẩu, trần đăng ký, trần
    suy luận, tất cả. Im lặng, và chỉ có đúng MỘT dòng log ở lần đầu.

    Bản triển khai này đã có những cú chớp như vậy (xem
    `stack-missing-prod-override`: các lỗi redis lẻ tẻ lúc dispatch), nên đây
    không phải rủi ro lý thuyết. Nó cũng làm bộ test đỏ ngẫu nhiên: một cú chớp
    giữa 1.250 test khiến mọi bộ đếm sau đó im lặng không tăng, và test nào
    khẳng định bộ đếm sẽ hỏng ở một chỗ không liên quan gì tới nguyên nhân.

    Vẫn fail-OPEN trong lúc chờ: chặn mọi request vì Redis chết là biến một sự
    cố phụ thành mất dịch vụ. Nhưng giờ nó tự lành.
    """
    global _client_singleton, _client_retry_at

    if _client_singleton is not None:
        return _client_singleton
    if time.monotonic() < _client_retry_at:
        return None
    try:
        c = redis.from_url(
            _REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=3,
        )
        c.ping()
        _client_singleton = c
        _client_retry_at = 0.0
        logger.info("[ratelimit] Redis đã kết nối; giới hạn tần suất đang hiệu lực")
        return c
    except Exception as exc:  # pragma: no cover - infra dependent
        _client_retry_at = time.monotonic() + _RETRY_COOLDOWN_SECONDS
        logger.warning(
            "[ratelimit] Redis không với tới được, TẠM fail-open %ds: %s",
            int(_RETRY_COOLDOWN_SECONDS), exc,
        )
        return None


# ---------------------------------------------------------------------------
# Client identity
# ---------------------------------------------------------------------------

def _parse_networks(raw: str) -> List:
    nets = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            nets.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            logger.warning("[ratelimit] TRUSTED_PROXIES: bỏ qua mục không hợp lệ %r", item)
    return nets


_TRUSTED_NETWORKS = _parse_networks(TRUSTED_PROXIES)


def _as_ip(value: str):
    try:
        return ipaddress.ip_address((value or "").strip())
    except ValueError:
        return None


def _is_trusted(value: str) -> bool:
    addr = _as_ip(value)
    return addr is not None and any(addr in net for net in _TRUSTED_NETWORKS)


def client_ip(request: Request) -> str:
    """Real client address as our own gateway resolved it. Never raises.

    This value is not a logging nicety: it keys the per-IP flood block, the
    generic limiter below and activity.get_block(), the admin's IP ban list.
    Anything a caller can choose here, a caller can use to reset all three on
    every request — so a header is believed ONLY when the TCP peer is one of our
    own proxies (TRUSTED_PROXIES). Reached directly, headers are ignored
    outright and the socket peer wins.

    Behind a trusted proxy, X-Real-IP comes first: nginx OVERWRITES it on every
    proxied location (the $rl_client map in nginx.conf), so whatever a caller
    sent is already gone. X-Forwarded-For is the fallback and is read RIGHT TO
    LEFT, skipping our own proxies, because each hop APPENDS — Cloudflare adds
    the real client behind whatever arrived, so a forged "X-Forwarded-For:
    1.2.3.4" shows up as "1.2.3.4, <real client>" and the leftmost entry is the
    attacker's choice. The first untrusted address from the right is the last
    one no caller could have written.
    """
    peer = (request.client.host if request.client else "") or ""
    if not _is_trusted(peer):
        return peer or "unknown"

    real = request.headers.get("x-real-ip", "")
    first = real.split(",")[0].strip()
    if _as_ip(first):
        return first

    chain = request.headers.get("x-forwarded-for", "").split(",")
    for hop in reversed(chain):
        hop = hop.strip()
        if hop and not _is_trusted(hop) and _as_ip(hop):
            return hop

    return peer or "unknown"


# ---------------------------------------------------------------------------
# Redis primitives
# ---------------------------------------------------------------------------

def _incr_with_window(key: str, window: int, sliding: bool = False) -> Tuple[int, int]:
    """INCR key and keep a TTL on it. Returns (count, ttl_seconds).

    `sliding=True` pushes the expiry out on every hit, so the counter measures
    "failures since the last quiet spell" rather than "failures since the first
    one" — which is what a backoff streak should mean.
    """
    c = _client()
    if c is None:
        return (0, 0)
    try:
        count = int(c.incr(key))
        if sliding or count == 1:
            c.expire(key, window)
        ttl = int(c.ttl(key))
        if ttl < 0:
            # Key had no TTL (shouldn't happen) — set one defensively.
            c.expire(key, window)
            ttl = window
        return (count, ttl)
    except Exception as exc:  # pragma: no cover
        logger.warning("[ratelimit] incr failed for %s: %s", key, exc)
        return (0, 0)


def _peek(key: str) -> Tuple[int, int]:
    """Read count + ttl without incrementing. Returns (count, ttl_seconds)."""
    c = _client()
    if c is None:
        return (0, 0)
    try:
        raw = c.get(key)
        count = int(raw) if raw is not None else 0
        ttl = int(c.ttl(key))
        return (count, max(ttl, 0))
    except Exception as exc:  # pragma: no cover
        logger.warning("[ratelimit] peek failed for %s: %s", key, exc)
        return (0, 0)


def _set_lock(key: str, seconds: int) -> None:
    c = _client()
    if c is None:
        return
    try:
        c.set(key, "1", ex=max(1, seconds))
    except Exception as exc:  # pragma: no cover
        logger.warning("[ratelimit] set lock failed for %s: %s", key, exc)


def _lock_ttl(key: str) -> int:
    """Remaining block seconds, or 0 if not blocked."""
    c = _client()
    if c is None:
        return 0
    try:
        ttl = int(c.ttl(key))
        return ttl if ttl > 0 else 0
    except Exception:  # pragma: no cover
        return 0


def _count_distinct(key: str, member: str, window: int) -> int:
    """Add `member` to a windowed set, return how many distinct ones it holds."""
    c = _client()
    if c is None:
        return 0
    try:
        c.sadd(key, member)
        c.expire(key, window)
        return int(c.scard(key))
    except Exception as exc:  # pragma: no cover
        logger.warning("[ratelimit] distinct-count failed for %s: %s", key, exc)
        return 0


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau.",
        headers={"Retry-After": str(max(retry_after, 1))},
    )


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

def _norm(identifier: str) -> str:
    return (identifier or "").strip().lower()


def _hashed(value: str) -> str:
    """Short digest, so alert logs can count distinct accounts without keeping a
    list of real usernames/emails in Redis or in the log line."""
    return hashlib.sha256(_norm(value).encode("utf-8")).hexdigest()[:16]


def _pair_fail_key(identifier: str, ip: str) -> str:
    return f"{_KEY_PREFIX}login:pair:{_norm(identifier)}:{ip}"


def _pair_block_key(identifier: str, ip: str) -> str:
    return f"{_KEY_PREFIX}login:pairblock:{_norm(identifier)}:{ip}"


# Kept at this exact name: activity.detect_anomalies scans "ratelimit:login:ip:*"
# to surface failed-login bursts on the admin activity page.
def _login_ip_key(ip: str) -> str:
    return f"{_KEY_PREFIX}login:ip:{ip}"


def _ip_block_key(ip: str) -> str:
    return f"{_KEY_PREFIX}login:ipblock:{ip}"


def _ip_identifiers_key(ip: str) -> str:
    return f"{_KEY_PREFIX}login:ipids:{ip}"


def _login_id_key(identifier: str) -> str:
    return f"{_KEY_PREFIX}login:id:{_norm(identifier)}"


def _id_ips_key(identifier: str) -> str:
    return f"{_KEY_PREFIX}login:idips:{_norm(identifier)}"


# ---------------------------------------------------------------------------
# Login gate
# ---------------------------------------------------------------------------

def check_login_allowed(ip: str, identifier: str) -> None:
    """Raise 429 if this (identifier, IP) pair is waiting out a backoff step, or
    if the IP is inside a flood block.

    Called BEFORE the password is verified, so a blocked caller never even runs
    bcrypt — and, just as importantly, never reaches register_failed_login, so
    waiting can never make the wait longer.
    """
    for key in (_pair_block_key(identifier, ip), _ip_block_key(ip)):
        ttl = _lock_ttl(key)
        if ttl > 0:
            raise _too_many(ttl)


def register_failed_login(ip: str, identifier: str) -> None:
    """Record one failed login: arm the pair backoff once the free allowance is
    spent, then update the two observation-only views."""
    count, _ = _incr_with_window(
        _pair_fail_key(identifier, ip), LOGIN_PAIR_WINDOW, sliding=True
    )
    if count > LOGIN_PAIR_FREE_FAILURES:
        level = count - LOGIN_PAIR_FREE_FAILURES  # 1 on the first penalised try
        wait = LOGIN_PAIR_BACKOFF_STEPS[min(level, len(LOGIN_PAIR_BACKOFF_STEPS)) - 1]
        _set_lock(_pair_block_key(identifier, ip), wait)
        logger.warning(
            "[auth] login_throttled identifier_hash=%s source_ip=%s "
            "failure_count=%d backoff_seconds=%d limit_type=identifier_ip",
            _hashed(identifier), ip, count, wait,
        )

    _observe_identifier(identifier, ip)
    _observe_ip(ip, identifier)


def _observe_identifier(identifier: str, ip: str) -> None:
    """One account under fire from many addresses. Alert only — blocking here is
    exactly the lock-out-by-proxy hole the pair key exists to close."""
    count, _ = _incr_with_window(_login_id_key(identifier), LOGIN_IP_WINDOW)
    sources = _count_distinct(_id_ips_key(identifier), ip, LOGIN_IP_WINDOW)
    if sources >= LOGIN_ID_DISTINCT_IP_WARN:
        logger.warning(
            "[auth] login_distributed_attack identifier_hash=%s distinct_ips=%d "
            "failure_count=%d window_seconds=%d",
            _hashed(identifier), sources, count, LOGIN_IP_WINDOW,
        )


def _observe_ip(ip: str, identifier: str) -> None:
    """One address under suspicion. Escalates warn → high risk → block, with the
    block deliberately far out at flood scale (see module docstring)."""
    count, _ = _incr_with_window(_login_ip_key(ip), LOGIN_IP_WINDOW)
    accounts = _count_distinct(_ip_identifiers_key(ip), _hashed(identifier), LOGIN_IP_WINDOW)

    if count >= LOGIN_IP_HARD_LIMIT:
        _set_lock(_ip_block_key(ip), LOGIN_IP_HARD_BLOCK)
        logger.error(
            "[auth] login_ip_blocked source_ip=%s failure_count=%d block_seconds=%d",
            ip, count, LOGIN_IP_HARD_BLOCK,
        )
    elif count >= LOGIN_IP_HIGH_RISK_ATTEMPTS:
        logger.warning(
            "[auth] login_ip_high_risk source_ip=%s failure_count=%d window_seconds=%d",
            ip, count, LOGIN_IP_WINDOW,
        )
    elif count >= LOGIN_IP_WARN_ATTEMPTS:
        logger.warning(
            "[auth] login_ip_warning source_ip=%s failure_count=%d window_seconds=%d",
            ip, count, LOGIN_IP_WINDOW,
        )

    if accounts >= LOGIN_IP_DISTINCT_IDENTIFIER_WARN:
        logger.warning(
            "[auth] login_password_spraying source_ip=%s distinct_identifiers=%d "
            "window_seconds=%d",
            ip, accounts, LOGIN_IP_WINDOW,
        )


def reset_login_attempts(ip: str, identifier: str) -> None:
    """Clear the pair's streak and backoff after a successful login — someone who
    proved who they are goes straight back to a clean slate.

    The per-IP abuse counters are deliberately NOT cleared: one success says
    nothing about the other accounts that address has been probing, and clearing
    them would hand an attacker a free reset by logging into any account they do
    own.
    """
    c = _client()
    if c is None:
        return
    try:
        c.delete(_pair_fail_key(identifier, ip), _pair_block_key(identifier, ip))
    except Exception as exc:  # pragma: no cover
        logger.warning("[ratelimit] reset failed: %s", exc)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def _register_requests_key(ip: str) -> str:
    return f"{_KEY_PREFIX}register:req:{ip}"


def _register_accounts_key(ip: str) -> str:
    return f"{_KEY_PREFIX}register:accounts:{ip}"


def check_register_allowed(request: Request) -> str:
    """Gate a registration attempt; returns the client IP for the caller to pass
    to `register_account_created` once the account really exists.

    Raises 429 on a request burst, or once this address has created so many
    accounts today that it can no longer be explained by a shared network.
    """
    ip = client_ip(request)

    count, ttl = _incr_with_window(_register_requests_key(ip), 60)
    if count > REGISTER_REQUESTS_PER_MINUTE:
        raise _too_many(ttl or 60)

    created, created_ttl = _peek(_register_accounts_key(ip))
    if created >= REGISTER_ACCOUNTS_HARD_LIMIT:
        raise _too_many(created_ttl or REGISTER_ACCOUNTS_WINDOW)

    return ip


def register_account_created(ip: str) -> None:
    """Count an account that was actually created, and escalate the alerts.

    Called AFTER creation on purpose: a request rejected for a duplicate
    username or a weak password created nothing, so it must not push a shared
    campus address towards a limit meant to describe real accounts.
    """
    count, _ = _incr_with_window(_register_accounts_key(ip), REGISTER_ACCOUNTS_WINDOW)

    if count >= REGISTER_ACCOUNTS_HARD_LIMIT:
        logger.error(
            "[auth] register_ip_blocked source_ip=%s accounts_created=%d "
            "window_seconds=%d",
            ip, count, REGISTER_ACCOUNTS_WINDOW,
        )
    elif count >= REGISTER_ACCOUNTS_HIGH_RISK:
        logger.warning(
            "[auth] register_ip_high_risk source_ip=%s accounts_created=%d "
            "window_seconds=%d",
            ip, count, REGISTER_ACCOUNTS_WINDOW,
        )
    elif count >= REGISTER_ACCOUNTS_WARN:
        logger.warning(
            "[auth] register_ip_warning source_ip=%s accounts_created=%d "
            "window_seconds=%d",
            ip, count, REGISTER_ACCOUNTS_WINDOW,
        )


# --- Generic per-IP limiter (forgot / reset password) ------------------------

def enforce_ip_limit(request: Request, bucket: str, max_calls: int, window: int) -> None:
    """Raise 429 if this IP has exceeded `max_calls` in `bucket` within window."""
    ip = client_ip(request)
    key = f"{_KEY_PREFIX}{bucket}:ip:{ip}"
    count, ttl = _incr_with_window(key, window)
    if count > max_calls:
        raise _too_many(ttl or window)


def enforce_actor_limit(
    request: Request,
    bucket: str,
    max_calls: int,
    window: int,
    user_id: Optional[str] = None,
) -> None:
    """Per-user limit when we know who is calling, per-IP otherwise.

    Keying on the user matters here specifically because of where this data is
    collected: contributors record at special-education facilities behind one
    campus NAT, so an IP-only bucket would have a whole room of collectors
    sharing one allowance and throttling each other. An anonymous caller has no
    identity to key on, so IP is the only option left.

    The two key spaces are kept distinct (`:user:` vs `:ip:`) so signing in can
    never inherit an anonymous caller's spent budget or vice versa.
    """
    if user_id:
        key = f"{_KEY_PREFIX}{bucket}:user:{_hashed(str(user_id))}"
    else:
        key = f"{_KEY_PREFIX}{bucket}:ip:{client_ip(request)}"

    count, ttl = _incr_with_window(key, window)
    if count > max_calls:
        logger.warning(
            "[RATE_LIMIT] bucket=%s over limit (%d/%d in %ds) actor=%s",
            bucket, count, max_calls, window, "user" if user_id else "ip",
        )
        raise _too_many(ttl or window)
