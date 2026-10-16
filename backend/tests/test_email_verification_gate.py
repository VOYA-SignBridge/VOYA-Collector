"""Refusing a session to an unverified address — and not locking everyone out.

The feature is one `if` in `login`. What needs testing is the two things around
it: that the refusal cannot be used to learn whether an address is registered,
and that the flag has a safe way to be switched on.
"""

from __future__ import annotations

import uuid

import pytest

from app.tenant_context import system_scope
from app.storage import metadata_db as db


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from conftest import LoopbackPeer, fresh_client_ip
    from app.main import app

    inner = TestClient(LoopbackPeer(app))

    class _PerRequestIp:
        def post(self, url, **kwargs):
            headers = {**kwargs.pop("headers", {}),
                       "X-Forwarded-For": fresh_client_ip()}
            return inner.post(url, headers=headers, **kwargs)

    return _PerRequestIp()


@pytest.fixture
def unverified():
    from app.auth import create_user

    name = f"ev{uuid.uuid4().hex[:10]}"
    user = create_user(username=name, email=f"{name}@example.test",
                       password="correct horse battery")
    yield user
    with system_scope("test cleanup"):
        db._execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user["id"],))
        db._execute("DELETE FROM tenant_members WHERE user_id = %s", (user["id"],))
        db._execute("DELETE FROM users WHERE id = %s", (user["id"],))


@pytest.fixture
def enforced(monkeypatch):
    from app.routers import auth as auth_router

    monkeypatch.setattr(auth_router.settings, "require_email_verification", True)


class TestTheGate:
    def test_off_by_default(self):
        """The default has to be off: every existing account is unverified, so
        a default-on flag would lock out the whole deployment on upgrade."""
        from app.config import Settings

        assert Settings().require_email_verification is False

    def test_an_unverified_account_is_refused_when_enforced(
        self, client, unverified, enforced
    ):
        res = client.post("/api/v1/auth/login", json={
            "identifier": unverified["email"], "password": "correct horse battery",
        })
        assert res.status_code == 403
        assert "xác minh" in res.json()["detail"]

    def test_the_same_account_logs_in_when_not_enforced(self, client, unverified):
        res = client.post("/api/v1/auth/login", json={
            "identifier": unverified["email"], "password": "correct horse battery",
        })
        assert res.status_code == 200, res.text

    def test_a_verified_account_logs_in_while_enforced(
        self, client, unverified, enforced
    ):
        with system_scope("test: mark verified"):
            db._execute("UPDATE users SET email_verified_at = now() WHERE id = %s",
                        (unverified["id"],))
        res = client.post("/api/v1/auth/login", json={
            "identifier": unverified["email"], "password": "correct horse battery",
        })
        assert res.status_code == 200, res.text

    def test_a_wrong_password_is_still_401_not_403(
        self, client, unverified, enforced
    ):
        """The order of the two checks is the whole point.

        If the verification gate ran BEFORE the password check, this endpoint
        would answer "403, unverified" to anyone who typed a registered address
        — an oracle for which addresses have accounts, answerable without the
        password. A 401 here proves the password check still runs first.
        """
        res = client.post("/api/v1/auth/login", json={
            "identifier": unverified["email"], "password": "not the password",
        })
        assert res.status_code == 401

    def test_an_unknown_address_is_401_not_403(self, client, enforced):
        res = client.post("/api/v1/auth/login", json={
            "identifier": "nobody@example.test", "password": "not the password",
        })
        assert res.status_code == 401


class TestTheGrandfatherCommand:
    """Every case here passes `--email-like %@example.test`.

    Not decoration. The suite runs against the real `signdb`, and an unfiltered
    `--apply` marks EVERY unverified account on the deployment — which is what
    the first version of this file did, silently stamping all ten real accounts
    before the run finished. The filter is what keeps a test from making a
    production decision on the operator's behalf.
    """

    SCOPE = ["--email-like", "%@example.test"]

    def test_check_reports_without_changing_anything(self, unverified, capsys):
        from app.cli.verify_existing_emails import main

        assert main(["--check", *self.SCOPE]) == 2
        assert unverified["email"] in capsys.readouterr().out

        with system_scope("test read"):
            row = db._fetch_all(
                "SELECT email_verified_at FROM users WHERE id = %s",
                (unverified["id"],))[0]
        assert row["email_verified_at"] is None

    def test_apply_marks_the_account(self, unverified):
        from app.cli.verify_existing_emails import main

        assert main(["--apply", *self.SCOPE]) == 0
        with system_scope("test read"):
            row = db._fetch_all(
                "SELECT email_verified_at FROM users WHERE id = %s",
                (unverified["id"],))[0]
        assert row["email_verified_at"] is not None

    def test_a_real_verification_is_not_overwritten(self, unverified):
        """`--apply` records a bulk decision about unverified addresses. An
        address someone actually proved between the SELECT and the UPDATE must
        keep its own timestamp, not have it replaced by this one."""
        from app.cli.verify_existing_emails import main

        with system_scope("test: verify for real"):
            db._execute(
                "UPDATE users SET email_verified_at = '2020-01-01' WHERE id = %s",
                (unverified["id"],))
        main(["--apply", *self.SCOPE])
        with system_scope("test read"):
            row = db._fetch_all(
                "SELECT email_verified_at FROM users WHERE id = %s",
                (unverified["id"],))[0]
        assert row["email_verified_at"].year == 2020

    def test_a_bad_date_is_refused_rather_than_ignored(self):
        from app.cli.verify_existing_emails import main

        assert main(["--apply", "--before", "07/08/2026", *self.SCOPE]) == 3

    def test_a_filtered_run_leaves_everyone_else_alone(self, unverified):
        """The property the first version of this file violated.

        `--apply` scoped to one address pattern must not stamp accounts outside
        it. Asserted against the real accounts on this deployment, because that
        is exactly who got stamped.
        """
        from app.cli.verify_existing_emails import main

        with system_scope("test read"):
            before = db._fetch_all(
                # The pattern is a PARAMETER, not inline. `_fetch_all` always
                # hands psycopg2 a params tuple, which turns on placeholder
                # parsing, and a bare `%` in the SQL then dies as a malformed
                # placeholder — the same trap documented in verify_deployment.py.
                "SELECT count(*) AS n FROM users "
                "WHERE email_verified_at IS NULL AND email NOT LIKE %s",
                ("%@example.test",),
            )[0]["n"]

        main(["--apply", *self.SCOPE])

        with system_scope("test read"):
            after = db._fetch_all(
                # The pattern is a PARAMETER, not inline. `_fetch_all` always
                # hands psycopg2 a params tuple, which turns on placeholder
                # parsing, and a bare `%` in the SQL then dies as a malformed
                # placeholder — the same trap documented in verify_deployment.py.
                "SELECT count(*) AS n FROM users "
                "WHERE email_verified_at IS NULL AND email NOT LIKE %s",
                ("%@example.test",),
            )[0]["n"]

        assert after == before
