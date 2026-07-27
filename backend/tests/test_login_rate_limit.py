"""Login brute-force soft-lock + registration cap — against the real DB + redis.

Contract:
  - up to 5 failed logins per IP AND per identifier within a 30-min window;
    the 5th arms a 15-min soft lock that refuses even the CORRECT password
  - a successful login clears the counters (a legit user is never left locked)
  - the lock keys on BOTH the IP and the identifier, independently
  - registration: max 5 new accounts per IP per day

Each test uses fresh RANDOM IPs so redis buckets never collide across runs
(login counters live 30 min, so a fixed scheme would poison later runs).
"""

from __future__ import annotations

import random
import uuid

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import app
from app.storage.metadata_db import _execute

client = TestClient(app)

LOGIN = "/api/v1/auth/login"
REGISTER = "/api/v1/auth/register"


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
# login soft-lock
# ===========================================================================

def test_five_wrong_passwords_then_locked_even_with_correct_password(user):
    ip = _ip()
    for _ in range(5):
        assert _login(user["username"], "WrongPass!", ip).status_code == 401
    # 6th attempt — correct password — is still refused by the soft lock.
    r = _login(user["username"], user["password"], ip)
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_fewer_than_five_failures_do_not_lock(user):
    ip = _ip()
    for _ in range(4):
        assert _login(user["username"], "WrongPass!", ip).status_code == 401
    # 4 failures < threshold → the correct password still logs in.
    assert _login(user["username"], user["password"], ip).status_code == 200


def test_lock_follows_the_identifier_across_ips(user):
    # 5 failures from FIVE different IPs → per-IP counters never reach 5, but the
    # per-identifier counter does → the account is locked from any IP.
    for _ in range(5):
        assert _login(user["username"], "WrongPass!", _ip()).status_code == 401
    assert _login(user["username"], user["password"], _ip()).status_code == 429


def test_lock_follows_the_ip_across_identifiers(user):
    # 5 failures from ONE IP against five different (nonexistent) usernames →
    # the per-IP counter reaches 5 → that IP is locked even for a valid login.
    ip = _ip()
    for _ in range(5):
        assert _login(f"ghost_{uuid.uuid4().hex[:8]}", "x", ip).status_code == 401
    assert _login(user["username"], user["password"], ip).status_code == 429


def test_successful_login_clears_the_counter(user):
    ip = _ip()
    for _ in range(4):
        assert _login(user["username"], "WrongPass!", ip).status_code == 401
    # success resets counters…
    assert _login(user["username"], user["password"], ip).status_code == 200
    # …so a fresh streak of 4 failures still doesn't lock (would have been 8).
    for _ in range(4):
        assert _login(user["username"], "WrongPass!", ip).status_code == 401
    assert _login(user["username"], user["password"], ip).status_code == 200


def test_one_users_lockout_does_not_affect_another(user):
    locked_ip = _ip()
    for _ in range(5):
        _login(user["username"], "WrongPass!", locked_ip)
    # A different user from a different IP is unaffected.
    other = auth.create_user(username=f"rlok_{uuid.uuid4().hex[:8]}",
                             email=f"rlok_{uuid.uuid4().hex[:8]}@example.com",
                             password="OtherPass9!", is_admin=False)
    try:
        assert _login(other["username"], "OtherPass9!", _ip()).status_code == 200
    finally:
        _execute("DELETE FROM users WHERE id = %s", (other["id"],))


# ===========================================================================
# registration cap (5 / IP / day)
# ===========================================================================

def test_register_allows_five_then_blocks_the_sixth_per_ip():
    ip = _ip()
    created = []
    try:
        for _ in range(5):
            u = f"reg_{uuid.uuid4().hex[:8]}"
            r = client.post(REGISTER,
                            json={"username": u, "email": f"{u}@example.com", "password": "GoodPass12!"},
                            headers={"X-Forwarded-For": ip})
            assert r.status_code == 201, r.text
            created.append(u)
        # 6th account from the same IP within the day → throttled.
        u = f"reg_{uuid.uuid4().hex[:8]}"
        r = client.post(REGISTER,
                        json={"username": u, "email": f"{u}@example.com", "password": "GoodPass12!"},
                        headers={"X-Forwarded-For": ip})
        assert r.status_code == 429
    finally:
        for u in created:
            try:
                _execute("DELETE FROM users WHERE username = %s", (u,))
            except Exception:
                pass


def test_register_cap_is_per_ip(user):
    # One IP exhausts its 5, a different IP can still register.
    busy = _ip()
    made = []
    try:
        for _ in range(5):
            u = f"reg_{uuid.uuid4().hex[:8]}"
            client.post(REGISTER, json={"username": u, "email": f"{u}@example.com", "password": "GoodPass12!"},
                        headers={"X-Forwarded-For": busy})
            made.append(u)
        u = f"reg_{uuid.uuid4().hex[:8]}"
        r = client.post(REGISTER, json={"username": u, "email": f"{u}@example.com", "password": "GoodPass12!"},
                        headers={"X-Forwarded-For": _ip()})  # fresh IP
        assert r.status_code == 201
        made.append(u)
    finally:
        for u in made:
            try:
                _execute("DELETE FROM users WHERE username = %s", (u,))
            except Exception:
                pass
