"""End-to-end tests for the forgot-password / reset-password flow.

Runs against the REAL Postgres (exercises the actual SQL — the thing most likely
to break: token insert/select/update, single-use, expiry, cascade) and the REAL
FastAPI routes (/api/v1/auth/*). Email delivery is patched so we can capture the
one-time token that is otherwise only sent by email.

Isolation:
  - each test gets its own throwaway user (fixture cleans it up; token rows
    cascade-delete with the user)
  - a unique X-Forwarded-For per call gives each test its own rate-limit bucket,
    so functional tests never trip the limiter and the limiter test is precise

Requires: postgres + redis up (see docker-compose test-ports override), env
DATABASE_URL/REDIS_URL pointed at them.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import app
from app.storage.metadata_db import _execute, _fetch_all
from conftest import LoopbackPeer, fresh_client_ip

client = TestClient(LoopbackPeer(app))

FORGOT = "/api/v1/auth/forgot-password"
RESET = "/api/v1/auth/reset-password"
LOGIN = "/api/v1/auth/login"

def _ip() -> str:
    """A fresh rate-limit bucket per call. Shared with the other HTTP suites —
    see `conftest.fresh_client_ip` for why both the peer and the forwarded
    address are needed."""
    return fresh_client_ip()


@pytest.fixture
def user():
    uid = uuid.uuid4().hex[:10]
    username = f"pwuser_{uid}"
    email = f"{username}@example.com"
    password = "OldPassw0rd!"
    u = auth.create_user(username=username, email=email, password=password, is_admin=False)
    u["password"] = password
    yield u
    # token rows cascade on user delete; be explicit + also clear refresh tokens.
    try:
        _execute("DELETE FROM users WHERE id = %s", (u["id"],))
    except Exception:
        pass


def _token_rows(user_id):
    return _fetch_all(
        "SELECT token_hash, expires_at, used_at FROM password_reset_tokens WHERE user_id = %s",
        (user_id,),
    )


def _forgot(identifier, ip=None):
    return client.post(FORGOT, json={"identifier": identifier},
                       headers={"X-Forwarded-For": ip or _ip()})


def _forgot_capture(identifier, ip=None):
    """POST forgot-password and capture the raw token from the (patched) email."""
    cap = {}

    def fake_send(to_email, username, reset_link):
        cap["to_email"] = to_email
        cap["reset_link"] = reset_link
        cap["token"] = reset_link.split("token=")[-1]

    with patch("app.routers.auth.send_password_reset_email", side_effect=fake_send) as m:
        resp = _forgot(identifier, ip)
    return resp, cap, m


# ===========================================================================
# forgot-password
# ===========================================================================

def test_forgot_unknown_identifier_returns_generic_and_sends_no_email():
    resp, cap, m = _forgot_capture(f"nobody_{uuid.uuid4().hex}@example.com")
    assert resp.status_code == 200
    assert "email" in resp.json()["message"].lower()
    m.assert_not_called()          # no email for a non-existent account
    assert "token" not in cap


def test_forgot_existing_by_username_creates_hashed_token_and_emails(user):
    resp, cap, m = _forgot_capture(user["username"])
    assert resp.status_code == 200
    m.assert_called_once()
    assert cap["to_email"] == user["email"]
    rows = _token_rows(user["id"])
    assert len(rows) == 1
    # Stored value is the sha256 hash, never the raw token.
    assert rows[0]["token_hash"] == auth._hash_reset_token(cap["token"])
    assert rows[0]["token_hash"] != cap["token"]
    assert rows[0]["used_at"] is None


def test_forgot_existing_by_email_also_works(user):
    resp, cap, m = _forgot_capture(user["email"])
    assert resp.status_code == 200
    m.assert_called_once()
    assert len(_token_rows(user["id"])) == 1


def test_forgot_inactive_user_makes_no_token_and_no_email(user):
    _execute("UPDATE users SET is_active = FALSE WHERE id = %s", (user["id"],))
    resp, cap, m = _forgot_capture(user["username"])
    assert resp.status_code == 200                 # still generic (no leak)
    m.assert_not_called()
    assert _token_rows(user["id"]) == []


def test_forgot_response_is_identical_for_real_and_fake_accounts(user):
    real = _forgot_capture(user["username"])[0].json()["message"]
    fake = _forgot_capture(f"ghost_{uuid.uuid4().hex}")[0].json()["message"]
    assert real == fake                            # enumeration-proof


@pytest.mark.parametrize("body", [{}, {"identifier": ""}])
def test_forgot_rejects_missing_or_empty_identifier(body):
    r = client.post(FORGOT, json=body, headers={"X-Forwarded-For": _ip()})
    assert r.status_code == 422


def test_forgot_rate_limited_after_five_from_same_ip(user):
    ip = _ip()
    codes = [
        client.post(FORGOT, json={"identifier": user["username"]},
                    headers={"X-Forwarded-For": ip}).status_code
        for _ in range(7)
    ]
    assert 429 in codes, f"limiter never engaged: {codes}"
    assert codes[:5] == [200] * 5                  # first 5 allowed, then throttled


# ===========================================================================
# reset-password
# ===========================================================================

def test_reset_with_valid_token_changes_password_and_lets_user_log_in(user):
    _, cap, _ = _forgot_capture(user["username"])
    new_pw = "BrandNewPass9!"
    r = client.post(RESET, json={"token": cap["token"], "new_password": new_pw},
                    headers={"X-Forwarded-For": _ip()})
    assert r.status_code == 200

    # New password works…
    ok = client.post(LOGIN, json={"identifier": user["username"], "password": new_pw},
                     headers={"X-Forwarded-For": _ip()})
    assert ok.status_code == 200
    # …and the old one no longer does.
    bad = client.post(LOGIN, json={"identifier": user["username"], "password": user["password"]},
                      headers={"X-Forwarded-For": _ip()})
    assert bad.status_code == 401


def test_reset_unknown_token_is_rejected(user):
    r = client.post(RESET, json={"token": "not-a-real-token", "new_password": "Whatever123!"},
                    headers={"X-Forwarded-For": _ip()})
    assert r.status_code == 400


def test_reset_expired_token_is_rejected(user):
    _, cap, _ = _forgot_capture(user["username"])
    _execute(
        "UPDATE password_reset_tokens SET expires_at = NOW() - INTERVAL '1 hour' WHERE user_id = %s",
        (user["id"],),
    )
    r = client.post(RESET, json={"token": cap["token"], "new_password": "Whatever123!"},
                    headers={"X-Forwarded-For": _ip()})
    assert r.status_code == 400


def test_reset_token_is_single_use(user):
    _, cap, _ = _forgot_capture(user["username"])
    first = client.post(RESET, json={"token": cap["token"], "new_password": "FirstPass12!"},
                        headers={"X-Forwarded-For": _ip()})
    assert first.status_code == 200
    second = client.post(RESET, json={"token": cap["token"], "new_password": "SecondPass12!"},
                         headers={"X-Forwarded-For": _ip()})
    assert second.status_code == 400               # already used


def test_reset_invalidates_all_other_outstanding_tokens(user):
    _, cap1, _ = _forgot_capture(user["username"])
    _, cap2, _ = _forgot_capture(user["username"])
    assert cap1["token"] != cap2["token"]
    assert len(_token_rows(user["id"])) == 2

    used = client.post(RESET, json={"token": cap1["token"], "new_password": "AfterReset12!"},
                       headers={"X-Forwarded-For": _ip()})
    assert used.status_code == 200
    # The still-unredeemed second token must now be dead too (no replay).
    replay = client.post(RESET, json={"token": cap2["token"], "new_password": "TryReplay12!"},
                         headers={"X-Forwarded-For": _ip()})
    assert replay.status_code == 400
    assert all(r["used_at"] is not None for r in _token_rows(user["id"]))


@pytest.mark.parametrize("body", [
    {"new_password": "NoTokenField1!"},            # missing token
    {"token": "x"},                                # missing new_password
    {"token": "x", "new_password": "short"},       # < 8 chars
])
def test_reset_validation_errors(body):
    r = client.post(RESET, json=body, headers={"X-Forwarded-For": _ip()})
    assert r.status_code == 422


# ===========================================================================
# direct function-level checks (hit the query paths without the HTTP layer)
# ===========================================================================

def test_request_password_reset_returns_none_for_unknown_and_inactive(user):
    assert auth.request_password_reset(f"missing_{uuid.uuid4().hex}") is None
    _execute("UPDATE users SET is_active = FALSE WHERE id = %s", (user["id"],))
    assert auth.request_password_reset(user["username"]) is None


def test_reset_password_with_token_rejects_short_password(user):
    res = auth.request_password_reset(user["username"])
    assert res is not None
    _, token = res
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        auth.reset_password_with_token(token, "short")
    assert exc.value.status_code == 400


# ===========================================================================
# extra coverage: rate-limit on reset, case-insensitive email, trimming
# ===========================================================================

def test_reset_rate_limited_after_ten_from_same_ip():
    ip = _ip()
    codes = [
        client.post(RESET, json={"token": "bad-token", "new_password": "Whatever123!"},
                    headers={"X-Forwarded-For": ip}).status_code
        for _ in range(12)
    ]
    assert 429 in codes, f"reset limiter never engaged: {codes}"
    assert codes[:10] == [400] * 10          # first 10 processed (bad token), then throttled


def test_forgot_email_lookup_is_case_insensitive(user):
    # user email is stored lowercase; an upper-cased identifier must still match.
    resp, cap, m = _forgot_capture(user["email"].upper())
    assert resp.status_code == 200
    m.assert_called_once()
    assert len(_token_rows(user["id"])) == 1


def test_forgot_trims_surrounding_whitespace(user):
    resp, cap, m = _forgot_capture(f"   {user['username']}   ")
    assert resp.status_code == 200
    m.assert_called_once()
    assert len(_token_rows(user["id"])) == 1


def test_reset_revokes_all_existing_sessions(user):
    # Establish an active session (login mints a refresh_tokens row).
    login = client.post(LOGIN, json={"identifier": user["username"], "password": user["password"]},
                        headers={"X-Forwarded-For": _ip()})
    assert login.status_code == 200
    before = _fetch_all("SELECT revoked_at FROM refresh_tokens WHERE user_id = %s", (user["id"],))
    assert before and all(r["revoked_at"] is None for r in before)   # session is live

    _, cap, _ = _forgot_capture(user["username"])
    r = client.post(RESET, json={"token": cap["token"], "new_password": "PostReset123!"},
                    headers={"X-Forwarded-For": _ip()})
    assert r.status_code == 200

    # Every pre-reset session must now be revoked (a compromised session can't
    # outlive the password reset).
    after = _fetch_all("SELECT revoked_at FROM refresh_tokens WHERE user_id = %s", (user["id"],))
    assert after and all(r["revoked_at"] is not None for r in after)
    client.cookies.clear()  # don't leak this session cookie into other tests
