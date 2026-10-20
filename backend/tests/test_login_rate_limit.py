"""Login throttling + registration cap — against the real DB + redis.

Contract (see app/rate_limit.py for the reasoning):
  - the pair (identifier, client IP) gets 10 free failures; the 11th arms a
    30s wait, then 2m, 5m, 15m as the streak continues
  - a wait refuses even the CORRECT password, and does not grow while it runs
  - a successful login clears that pair's streak — and only that pair's
  - the SAME account from a different IP is untouched: nobody can lock you out
    of your own account by typing your email wrong
  - one IP is not blocked for a handful of failures; the per-IP block is a
    flood valve (1000 / 10 min), not a login gate
  - registration: max 5 new accounts per IP per day

The client is built with a peer inside TRUSTED_PROXIES, otherwise client_ip()
ignores X-Forwarded-For (as it must for anything reaching us directly) and every
test would collapse into one bucket.

Each test uses fresh RANDOM IPs so redis buckets never collide across runs.
"""

from __future__ import annotations

import random
import uuid

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import app
from app.rate_limit import (
    LOGIN_PAIR_BACKOFF_STEPS,
    LOGIN_PAIR_FREE_FAILURES,
    REGISTER_REQUESTS_PER_MINUTE,
    _client,
    _lock_ttl,
    _login_ip_key,
    _pair_block_key,
    _pair_fail_key,
    _peek,
    _register_accounts_key,
    register_failed_login,
    reset_login_attempts,
)
from app.storage.metadata_db import _execute


class _FromTrustedProxy:
    """Stamp an ASGI peer that client_ip() will trust.

    TestClient hard-codes the peer as ("testclient", 50000) — not an IP, so
    never inside TRUSTED_PROXIES, so X-Forwarded-For is (correctly) ignored and
    every test here would share one bucket. Wrapping the app is version-proof;
    the `client=` argument only exists on newer starlette.
    """

    def __init__(self, inner, peer=("10.0.0.9", 51234)):
        self.inner, self.peer = inner, peer

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            scope = dict(scope, client=self.peer)
        await self.inner(scope, receive, send)


client = TestClient(_FromTrustedProxy(app))

LOGIN = "/api/v1/auth/login"
REGISTER = "/api/v1/auth/register"

FREE = LOGIN_PAIR_FREE_FAILURES


def _ip() -> str:
    return f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


@pytest.fixture(autouse=True)
def _clear_cookies():
    yield
    client.cookies.clear()  # don't leak a session cookie between tests


@pytest.fixture
def user():
    uid = uuid.uuid4().hex[:10]
    username = f"rluser_{uid}"
    u = auth.create_user(username=username, email=f"{username}@example.com",
                         password="OldPassw0rd!", is_admin=False)
    u["password"] = "OldPassw0rd!"
    yield u
    try:
        _execute("DELETE FROM users WHERE id = %s", (u["id"],))
    except Exception:
        pass


def _login(identifier, password, ip):
    return client.post(LOGIN, json={"identifier": identifier, "password": password},
                       headers={"X-Forwarded-For": ip})


# ===========================================================================
# the free allowance
# ===========================================================================

def test_the_free_failures_do_not_throttle(user):
    """A user fumbling their password is not the threat model."""
    ip = _ip()
    for _ in range(FREE):
        assert _login(user["username"], "WrongPass!", ip).status_code == 401
    # Still inside the allowance → the correct password logs in normally.
    assert _login(user["username"], user["password"], ip).status_code == 200


def test_one_past_the_allowance_arms_the_first_backoff_step(user):
    ip = _ip()
    for _ in range(FREE + 1):
        assert _login(user["username"], "WrongPass!", ip).status_code == 401
    r = _login(user["username"], user["password"], ip)
    assert r.status_code == 429
    # First step only — a mistyped password must not cost a quarter of an hour.
    assert 0 < int(r.headers["Retry-After"]) <= LOGIN_PAIR_BACKOFF_STEPS[0]


def test_waiting_does_not_make_the_wait_longer(user):
    """Hammering while blocked must not re-arm a longer step.

    The previous implementation kept counting during the lock, so a blocked
    caller (or a user retrying too early) climbed the ladder without ever
    reaching the password check.
    """
    ip = _ip()
    for _ in range(FREE + 1):
        _login(user["username"], "WrongPass!", ip)
    first = int(_login(user["username"], "WrongPass!", ip).headers["Retry-After"])
    for _ in range(5):
        again = int(_login(user["username"], "WrongPass!", ip).headers["Retry-After"])
        assert again <= first  # only ever counts down


# ===========================================================================
# the lock-out-by-proxy hole this design exists to close
# ===========================================================================

def test_an_attacker_cannot_lock_the_real_user_out(user):
    """Someone else's failures from THEIR address must not reach you.

    This is the whole reason the block keys on (identifier, IP): with an
    identifier-only key, knowing a victim's email is enough to keep them out
    indefinitely.
    """
    attacker_ip = _ip()
    for _ in range(FREE + 4):
        _login(user["username"], "WrongPass!", attacker_ip)
    assert _login(user["username"], "WrongPass!", attacker_ip).status_code == 429

    # The real user, from their own address, is completely unaffected.
    assert _login(user["username"], user["password"], _ip()).status_code == 200


def test_a_few_failures_from_one_ip_do_not_block_that_ip(user):
    """Campus/VPN networks share one address between many people.

    The per-IP rule is a flood valve at 1000 failures / 10 min, so a dozen
    failures against unknown accounts must leave the address usable.
    """
    ip = _ip()
    for _ in range(FREE + 4):
        assert _login(f"ghost_{uuid.uuid4().hex[:8]}", "x", ip).status_code == 401
    assert _login(user["username"], user["password"], ip).status_code == 200


def test_one_users_throttle_does_not_affect_another(user):
    busy_ip = _ip()
    for _ in range(FREE + 1):
        _login(user["username"], "WrongPass!", busy_ip)

    other = auth.create_user(username=f"rlok_{uuid.uuid4().hex[:8]}",
                             email=f"rlok_{uuid.uuid4().hex[:8]}@example.com",
                             password="OtherPass9!", is_admin=False)
    try:
        assert _login(other["username"], "OtherPass9!", busy_ip).status_code == 200
    finally:
        _execute("DELETE FROM users WHERE id = %s", (other["id"],))


def test_successful_login_clears_the_streak(user):
    ip = _ip()
    for _ in range(FREE - 1):
        assert _login(user["username"], "WrongPass!", ip).status_code == 401
    assert _login(user["username"], user["password"], ip).status_code == 200
    # Streak reset, so another near-full run of failures still doesn't throttle.
    for _ in range(FREE - 1):
        assert _login(user["username"], "WrongPass!", ip).status_code == 401
    assert _login(user["username"], user["password"], ip).status_code == 200


# ===========================================================================
# the backoff ladder, at the limiter level (no waiting out real seconds)
# ===========================================================================

@pytest.mark.skipif(_client() is None, reason="cần Redis")
def test_backoff_ladder_climbs_then_holds_at_the_ceiling():
    ip, ident = _ip(), f"ladder_{uuid.uuid4().hex[:8]}@example.com"
    steps = LOGIN_PAIR_BACKOFF_STEPS
    try:
        for _ in range(FREE):
            register_failed_login(ip, ident)
        assert _lock_ttl(_pair_block_key(ident, ip)) == 0, "chưa hết lượt miễn phí"

        seen = []
        for _ in range(len(steps) + 2):
            register_failed_login(ip, ident)
            seen.append(_lock_ttl(_pair_block_key(ident, ip)))

        expected = steps + [steps[-1]] * 2  # ladder, then held at the ceiling
        for got, want in zip(seen, expected):
            assert want - 1 <= got <= want, f"chờ {want}s, nhận {got}s"
    finally:
        c = _client()
        if c is not None:
            c.delete(_pair_fail_key(ident, ip), _pair_block_key(ident, ip),
                     _login_ip_key(ip))


@pytest.mark.skipif(_client() is None, reason="cần Redis")
def test_reset_clears_the_pair_but_not_the_ip_abuse_counter():
    """A successful login proves who you are — it says nothing about the other
    accounts your address has been probing."""
    ip, ident = _ip(), f"reset_{uuid.uuid4().hex[:8]}@example.com"
    try:
        for _ in range(3):
            register_failed_login(ip, ident)
        assert _peek(_pair_fail_key(ident, ip))[0] == 3
        assert _peek(_login_ip_key(ip))[0] == 3

        reset_login_attempts(ip, ident)
        assert _peek(_pair_fail_key(ident, ip))[0] == 0
        assert _peek(_login_ip_key(ip))[0] == 3, "bộ đếm lạm dụng của IP phải giữ nguyên"
    finally:
        c = _client()
        if c is not None:
            c.delete(_login_ip_key(ip))


# ===========================================================================
# registration: tight cap on ATTEMPTS, loose cap on ACCOUNTS CREATED
# ===========================================================================

RATE = REGISTER_REQUESTS_PER_MINUTE


def _register(ip, password="GoodPass12!"):
    """A registration that gets as far as the rate limiter.

    `registration_consents()` is not decoration. Publishing the terms switches
    consent enforcement on, and this suite runs against a copy of the real
    database where they are published — without the versions every call here
    would be refused 400 before the limiter ever counted it, and three tests
    about counting would be measuring nothing.
    """
    from conftest import registration_consents

    u = f"reg_{uuid.uuid4().hex[:8]}"
    r = client.post(REGISTER,
                    json={"username": u, "email": f"{u}@example.com",
                          "password": password, **registration_consents()},
                    headers={"X-Forwarded-For": ip})
    return u, r


def _drop(usernames):
    """Uỷ cho bản dùng chung ở conftest — xem `purge_registered_account`."""
    from conftest import purge_registered_account

    for u in usernames:
        purge_registered_account(u)


def test_register_burst_is_capped_per_minute():
    ip = _ip()
    created = []
    try:
        for _ in range(RATE):
            u, r = _register(ip)
            assert r.status_code == 201, r.text
            created.append(u)
        # One past the per-minute allowance → refused, with a countdown.
        _, r = _register(ip)
        assert r.status_code == 429
        assert "Retry-After" in r.headers
    finally:
        _drop(created)


def test_register_cap_is_per_ip():
    """A busy address must not spend anyone else's allowance."""
    busy = _ip()
    made = []
    try:
        for _ in range(RATE):
            u, _r = _register(busy)
            made.append(u)
        u, r = _register(_ip())  # fresh address
        assert r.status_code == 201
        made.append(u)
    finally:
        _drop(made)


def test_a_rejected_attempt_costs_a_request_but_not_an_account():
    """The daily account cap must describe real accounts.

    A duplicate username or a too-short password creates nothing, so counting it
    would let a handful of typos push a shared campus address toward a limit
    meant for spam runs. It still costs a request, which is what stops a script.
    """
    ip = _ip()
    made = []
    try:
        for _ in range(3):
            _, r = _register(ip, password="short")  # below MIN_PASSWORD_LENGTH
            assert r.status_code >= 400
        assert _peek(_register_accounts_key(ip))[0] == 0, "lần bị từ chối không được tính là tài khoản"

        u, r = _register(ip)
        assert r.status_code == 201, r.text
        made.append(u)
        assert _peek(_register_accounts_key(ip))[0] == 1
    finally:
        _drop(made)
