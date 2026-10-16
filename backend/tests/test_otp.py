"""One-time codes: the guarantees, and the ones that are easy to believe without checking.

Three properties here are not "does the happy path work" but "is the weak secret
survivable":

  * the code never reaches a log or the database
  * guessing is bounded by a counter that survives a restart
  * switching channel mid-flow kills the code already sent

Runs against the real Postgres — the single-live-challenge rule is enforced by a
partial unique index, and an in-memory fake would assert the Python instead of
the constraint that actually holds the line.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import otp
from app.storage import metadata_db as db
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture(autouse=True)
def _pepper(monkeypatch):
    monkeypatch.setattr(
        otp.settings, "otp_pepper", "pepper-for-tests-at-least-32-chars", raising=False
    )


@pytest.fixture
def account():
    from app.auth import create_user

    name = f"otp{uuid.uuid4().hex[:10]}"
    user = create_user(
        username=name, email=f"{name}@example.test", password="correct horse battery"
    )
    yield user
    with system_scope("test cleanup"):
        db._execute("DELETE FROM verification_codes WHERE user_id = %s", (user["id"],))
        db._execute("DELETE FROM tenant_members WHERE user_id = %s", (user["id"],))
        db._execute("DELETE FROM users WHERE id = %s", (user["id"],))


@pytest.fixture
def client():
    """A TestClient whose requests each arrive from a fresh IP.

    Module-level rather than owned by one class: every rate-limited endpoint
    here would otherwise 429 its way through the file, and the counters live in
    Redis so they survive between runs. `LoopbackPeer` exists because Starlette
    0.27 hardcodes the peer as the string "testclient", which is not an address
    the rate limiter can bucket by.
    """
    from fastapi.testclient import TestClient
    from conftest import LoopbackPeer, fresh_client_ip
    from app.main import app

    inner = TestClient(LoopbackPeer(app))

    class _PerRequestIp:
        def post(self, url, **kwargs):
            headers = {**kwargs.pop("headers", {}),
                       "X-Forwarded-For": fresh_client_ip()}
            return inner.post(url, headers=headers, **kwargs)

        def get(self, url, **kwargs):
            headers = {**kwargs.pop("headers", {}),
                       "X-Forwarded-For": fresh_client_ip()}
            return inner.get(url, headers=headers, **kwargs)

    return _PerRequestIp()


def _access_token_for(user) -> str:
    """A Bearer token for `user`, minted the same way `/auth/login` mints one.

    Bearer rather than the login cookie on purpose: `csrf_protect` only engages
    when an access COOKIE is present, so this keeps the test about the endpoint
    under examination instead of about CSRF plumbing.
    """
    from app.auth import create_access_token

    return create_access_token(data={
        "sub": user["id"], "username": user["username"],
        "email": user["email"], "is_admin": user.get("is_admin", False),
    })


@pytest.fixture
def no_cooldown(monkeypatch):
    """Most tests are not about the cooldown and would otherwise 429 each other."""
    monkeypatch.setattr(otp.settings, "otp_resend_cooldown_seconds", 0, raising=False)


def _row(challenge_id: str) -> dict:
    with system_scope("test read"):
        return db._fetch_all(
            "SELECT * FROM verification_codes WHERE challenge_id = %s", (challenge_id,)
        )[0]


class TestTheCodeIsNeverWrittenDown:
    """The constraint the whole design rests on."""

    def test_the_database_holds_a_digest_not_the_code(self, account):
        cid, code = otp.issue(
            user_id=account["id"], purpose="verify_email",
            channel="email", destination=account["email"],
        )
        stored = " ".join(str(v) for v in _row(cid).values())
        assert code not in stored, "the raw code reached the database"
        assert len(_row(cid)["code_hash"]) == 64

    def test_no_log_line_contains_the_code(self, account, caplog):
        """Asserted against captured output, not against care.

        Logs go to Loki, which more people can read than the database. A code in
        a log line is a code an operator can use.
        """
        with caplog.at_level(logging.DEBUG):
            cid, code = otp.issue(
                user_id=account["id"], purpose="verify_email",
                channel="email", destination=account["email"],
            )
            with pytest.raises(otp.OtpError):
                otp.verify(user_id=account["id"], purpose="verify_email", code="000000")
            otp.verify(user_id=account["id"], purpose="verify_email", code=code)

        emitted = "\n".join(r.getMessage() for r in caplog.records)
        assert code not in emitted, "the code appeared in a log line"
        # The failure it must still be possible to diagnose: something was sent.
        assert "[OTP] issued" in emitted

    def test_the_destination_is_masked_in_logs(self, account, caplog):
        with caplog.at_level(logging.INFO):
            otp.issue(
                user_id=account["id"], purpose="verify_email",
                channel="email", destination=account["email"],
            )
        emitted = "\n".join(r.getMessage() for r in caplog.records)
        assert account["email"] not in emitted
        assert "***" in emitted

    def test_an_error_message_does_not_echo_the_code(self, account):
        otp.issue(
            user_id=account["id"], purpose="verify_email",
            channel="email", destination=account["email"],
        )
        with pytest.raises(otp.OtpError) as exc:
            otp.verify(user_id=account["id"], purpose="verify_email", code="123456")
        assert "123456" not in str(exc.value)


class TestGuessingIsBounded:
    def test_the_challenge_dies_after_the_attempt_cap(self, account, monkeypatch):
        monkeypatch.setattr(otp.settings, "otp_max_attempts", 3, raising=False)
        _, code = otp.issue(
            user_id=account["id"], purpose="verify_email",
            channel="email", destination=account["email"],
        )
        for _ in range(3):
            with pytest.raises(otp.OtpError):
                otp.verify(user_id=account["id"], purpose="verify_email", code="000000")

        # The real code no longer works: the budget is spent, not merely delayed.
        with pytest.raises(otp.OtpError) as exc:
            otp.verify(user_id=account["id"], purpose="verify_email", code=code)
        assert exc.value.code == "too_many_attempts"

    def test_the_counter_lives_on_the_row(self, account, monkeypatch):
        """So it survives a restart and cannot be reset by reconnecting. An
        in-process counter would be cleared by the deploy that follows an
        attack."""
        monkeypatch.setattr(otp.settings, "otp_max_attempts", 5, raising=False)
        cid, _ = otp.issue(
            user_id=account["id"], purpose="verify_email",
            channel="email", destination=account["email"],
        )
        for expected in (1, 2):
            with pytest.raises(otp.OtpError):
                otp.verify(user_id=account["id"], purpose="verify_email", code="000000")
            assert _row(cid)["attempts"] == expected

    def test_a_wrong_code_and_no_challenge_are_indistinguishable(self, account):
        """Otherwise someone holding a stolen address learns whether a reset is
        in flight."""
        with pytest.raises(otp.OtpError) as nothing:
            otp.verify(user_id=account["id"], purpose="reset_password", code="123456")
        otp.issue(
            user_id=account["id"], purpose="reset_password",
            channel="email", destination=account["email"],
        )
        with pytest.raises(otp.OtpError) as wrong:
            otp.verify(user_id=account["id"], purpose="reset_password", code="123456")
        assert str(nothing.value) == str(wrong.value)
        assert nothing.value.status_code == wrong.value.status_code

    def test_an_expired_code_is_refused(self, account):
        _, code = otp.issue(
            user_id=account["id"], purpose="verify_email",
            channel="email", destination=account["email"],
        )
        with system_scope("test setup"):
            db._execute(
                "UPDATE verification_codes SET expires_at = %s WHERE user_id = %s",
                (datetime.now(timezone.utc) - timedelta(seconds=1), account["id"]),
            )
        with pytest.raises(otp.OtpError):
            otp.verify(user_id=account["id"], purpose="verify_email", code=code)

    def test_a_code_cannot_be_used_twice(self, account):
        _, code = otp.issue(
            user_id=account["id"], purpose="verify_email",
            channel="email", destination=account["email"],
        )
        otp.verify(user_id=account["id"], purpose="verify_email", code=code)
        with pytest.raises(otp.OtpError):
            otp.verify(user_id=account["id"], purpose="verify_email", code=code)


class TestChannelSwitch:
    """"Asked for a reset by email, came back and chose phone."""

    def test_the_new_channel_kills_the_code_already_sent(self, account, no_cooldown):
        """The email code is sitting in an inbox. After the switch it must not
        open the account — that inbox may be exactly what the attacker has."""
        _, email_code = otp.issue(
            user_id=account["id"], purpose="reset_password",
            channel="email", destination=account["email"],
        )
        _, sms_code = otp.issue(
            user_id=account["id"], purpose="reset_password",
            channel="sms", destination="+84901234567",
        )

        with pytest.raises(otp.OtpError):
            otp.verify(user_id=account["id"], purpose="reset_password", code=email_code)
        assert otp.verify(
            user_id=account["id"], purpose="reset_password", code=sms_code
        )["channel"] == "sms"

    def test_only_one_live_challenge_survives_per_purpose(self, account, no_cooldown):
        """Enforced by a partial unique index, so a future caller that forgets to
        close the old row is refused by the database rather than quietly leaving
        two ways in."""
        for _ in range(3):
            otp.issue(
                user_id=account["id"], purpose="reset_password",
                channel="email", destination=account["email"],
            )
        with system_scope("test read"):
            live = db._fetch_all(
                "SELECT challenge_id FROM verification_codes "
                "WHERE user_id = %s AND purpose = %s AND consumed_at IS NULL",
                (account["id"], "reset_password"),
            )
        assert len(live) == 1

    def test_purposes_do_not_interfere(self, account, no_cooldown):
        """Verifying an email and resetting a password are separate flows; one
        must not cancel the other's code."""
        _, verify_code = otp.issue(
            user_id=account["id"], purpose="verify_email",
            channel="email", destination=account["email"],
        )
        _, reset_code = otp.issue(
            user_id=account["id"], purpose="reset_password",
            channel="email", destination=account["email"],
        )
        assert otp.verify(
            user_id=account["id"], purpose="verify_email", code=verify_code
        )
        assert otp.verify(
            user_id=account["id"], purpose="reset_password", code=reset_code
        )

    def test_a_code_from_one_purpose_does_not_satisfy_another(self, account, no_cooldown):
        """Domain separation, end to end: the digest binds the purpose, so the
        same six digits issued for one flow cannot answer the challenge of
        another even when they happen to collide."""
        _, verify_code = otp.issue(
            user_id=account["id"], purpose="verify_email",
            channel="email", destination=account["email"],
        )
        otp.issue(
            user_id=account["id"], purpose="reset_password",
            channel="email", destination=account["email"],
        )
        with system_scope("test setup"):
            # Force the collision rather than waiting for it: both challenges now
            # hold the same digits.
            db._execute(
                "UPDATE verification_codes SET code_hash = %s "
                "WHERE user_id = %s AND purpose = 'reset_password' AND consumed_at IS NULL",
                (
                    otp.hash_code(
                        verify_code, purpose="verify_email", subject=account["email"]
                    ),
                    account["id"],
                ),
            )
        with pytest.raises(otp.OtpError):
            otp.verify(
                user_id=account["id"], purpose="reset_password", code=verify_code
            )


class TestResendCooldown:
    def test_a_second_code_too_soon_is_refused(self, account, monkeypatch):
        """Protects the RECIPIENT: without it anyone who knows an address can
        have the system text a stranger once a second."""
        monkeypatch.setattr(otp.settings, "otp_resend_cooldown_seconds", 300, raising=False)
        otp.issue(
            user_id=account["id"], purpose="verify_phone",
            channel="sms", destination="+84901234567",
        )
        with pytest.raises(otp.OtpError) as exc:
            otp.issue(
                user_id=account["id"], purpose="verify_phone",
                channel="sms", destination="+84901234567",
            )
        assert exc.value.status_code == 429
        assert exc.value.code == "resend_too_soon"


class TestDestinations:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("+84901234567", "+84901234567"),
            ("+84 90 123 4567", "+84901234567"),
            ("+84-90-123-4567", "+84901234567"),
            ("  +84901234567  ", "+84901234567"),
        ],
    )
    def test_phone_is_canonicalised(self, raw, expected):
        """Two spellings of one number must not be two people."""
        assert otp.normalize_phone(raw) == expected

    @pytest.mark.parametrize(
        "bad",
        [
            pytest.param("0901234567", id="no-country-code"),
            pytest.param("+0901234567", id="leading-zero-country"),
            pytest.param("+84", id="too-short"),
            pytest.param("+8490123456789012", id="too-long"),
            pytest.param("not a phone", id="letters"),
            pytest.param("", id="empty"),
        ],
    )
    def test_malformed_phone_is_refused(self, bad):
        """`0901234567` is the interesting one: guessing the country code from
        the server's locale is how a Vietnamese number becomes a US one."""
        with pytest.raises(otp.OtpError):
            otp.normalize_phone(bad)

    def test_code_is_six_digits_and_zero_padded(self):
        codes = [otp.new_code() for _ in range(300)]
        assert all(re.fullmatch(r"\d{6}", c) for c in codes)
        # Not a distribution test — just that the generator is not stuck.
        assert len(set(codes)) > 200


class TestRecoveryEndpointRevealsNothing:
    """`/auth/recover/*` is unauthenticated, so every response must be uniform.

    An account list for a special-education programme is exactly the kind of
    thing that must not be enumerable, and a recovery endpoint that answers
    differently for a known and an unknown address is an enumeration oracle.
    """

    def test_known_and_unknown_identifiers_are_indistinguishable(self, client, account):
        known = client.post("/api/v1/auth/recover/start",
                            json={"identifier": account["email"], "channel": "email"})
        unknown = client.post("/api/v1/auth/recover/start",
                              json={"identifier": "nobody@example.test", "channel": "email"})
        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()

    def test_sms_on_an_unconfigured_deployment_still_looks_the_same(self, client, account):
        """Falling back to email must not be visible: a different response for
        SMS would reveal whether the account has a verified number."""
        res = client.post("/api/v1/auth/recover/start",
                          json={"identifier": account["email"], "channel": "sms"})
        assert res.status_code == 200
        assert "Nếu tài khoản tồn tại" in res.json()["message"]

    def test_a_wrong_code_and_an_unknown_account_give_the_same_refusal(
        self, client, account
    ):
        otp.issue(user_id=account["id"], purpose="reset_password",
                  channel="email", destination=account["email"])
        wrong = client.post("/api/v1/auth/recover/confirm", json={
            "identifier": account["email"], "code": "000000",
            "new_password": "a-new-password-1",
        })
        unknown = client.post("/api/v1/auth/recover/confirm", json={
            "identifier": "nobody@example.test", "code": "000000",
            "new_password": "a-new-password-1",
        })
        assert wrong.status_code == unknown.status_code == 400
        assert wrong.json() == unknown.json()

    def test_a_correct_code_resets_the_password_and_kills_sessions(
        self, client, account
    ):
        from app.auth import authenticate_user

        _, code = otp.issue(user_id=account["id"], purpose="reset_password",
                            channel="email", destination=account["email"])
        res = client.post("/api/v1/auth/recover/confirm", json={
            "identifier": account["email"], "code": code,
            "new_password": "a-brand-new-password",
        })
        assert res.status_code == 200, res.text
        assert authenticate_user(account["email"], "a-brand-new-password")
        assert authenticate_user(account["email"], "correct horse battery") is None

        with system_scope("test read"):
            live = db._fetch_all(
                "SELECT 1 FROM refresh_tokens WHERE user_id = %s AND revoked_at IS NULL",
                (account["id"],),
            )
        assert live == []

    def test_the_code_is_spent_after_a_successful_reset(self, client, account):
        """A reset completed on one channel must not leave a live code able to
        reset again — that is the window an attacker who saw one code needs."""
        _, code = otp.issue(user_id=account["id"], purpose="reset_password",
                            channel="email", destination=account["email"])
        client.post("/api/v1/auth/recover/confirm", json={
            "identifier": account["email"], "code": code,
            "new_password": "a-brand-new-password",
        })
        second = client.post("/api/v1/auth/recover/confirm", json={
            "identifier": account["email"], "code": code,
            "new_password": "yet-another-password",
        })
        assert second.status_code == 400


class TestRecoveryInTwoSteps:
    """`/recover/verify` answers the code, `/recover/confirm` takes the password.

    Split so the screen can tell someone their code is wrong *before* asking
    them to think of a password. The split creates two things worth checking
    that the one-shot version never had: a ticket that must not be usable as
    anything else, and a second endpoint that must not double the guess budget.
    """

    def _code(self, account):
        _, code = otp.issue(user_id=account["id"], purpose="reset_password",
                            channel="email", destination=account["email"])
        return code

    def test_a_correct_code_returns_a_ticket_and_is_then_spent(self, client, account):
        code = self._code(account)
        first = client.post("/api/v1/auth/recover/verify",
                            json={"identifier": account["email"], "code": code})
        assert first.status_code == 200, first.text
        assert first.json()["reset_ticket"]

        # The code is consumed by the check, not by the password change. A code
        # that survives its own verification is a code sitting in an inbox with
        # the account still open behind it.
        second = client.post("/api/v1/auth/recover/verify",
                             json={"identifier": account["email"], "code": code})
        assert second.status_code == 400

    def test_a_wrong_code_and_an_unknown_account_give_the_same_refusal(
        self, client, account
    ):
        self._code(account)
        wrong = client.post("/api/v1/auth/recover/verify",
                            json={"identifier": account["email"], "code": "000000"})
        unknown = client.post("/api/v1/auth/recover/verify",
                              json={"identifier": "nobody@example.test", "code": "000000"})
        assert wrong.status_code == unknown.status_code == 400
        assert wrong.json() == unknown.json()

    def test_the_ticket_resets_the_password_and_kills_sessions(self, client, account):
        from app.auth import authenticate_user

        ticket = client.post(
            "/api/v1/auth/recover/verify",
            json={"identifier": account["email"], "code": self._code(account)},
        ).json()["reset_ticket"]

        res = client.post("/api/v1/auth/recover/confirm",
                          json={"reset_ticket": ticket, "new_password": "a-brand-new-password"})
        assert res.status_code == 200, res.text
        assert authenticate_user(account["email"], "a-brand-new-password")
        assert authenticate_user(account["email"], "correct horse battery") is None

        with system_scope("test read"):
            live = db._fetch_all(
                "SELECT 1 FROM refresh_tokens WHERE user_id = %s AND revoked_at IS NULL",
                (account["id"],),
            )
        assert live == []

    def test_the_ticket_is_not_an_access_token(self, client, account):
        """The 2FA challenge had exactly this hole: every token is signed with
        the same key, so a valid signature proves only that this system issued
        it — never what it was issued *for*. `_decode_token` rejects anything
        whose `typ` is not `access`; this asserts the reset ticket is caught by
        that same gate rather than relying on nobody trying."""
        ticket = client.post(
            "/api/v1/auth/recover/verify",
            json={"identifier": account["email"], "code": self._code(account)},
        ).json()["reset_ticket"]

        res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ticket}"})
        assert res.status_code == 401

    def test_a_2fa_challenge_is_not_a_reset_ticket(self, account):
        """And the other direction: passing the two-token check in one place
        must not pass it in the other."""
        from app.auth import create_2fa_challenge, verify_password_reset_ticket

        assert verify_password_reset_ticket(create_2fa_challenge(account["id"])) is None

    def test_an_expired_ticket_is_refused_but_does_not_say_wrong_code(
        self, client, account
    ):
        """Someone holding a dead ticket already proved their code was right.
        Telling them "wrong code" sends them back to re-read an email whose code
        is spent — the one instruction guaranteed not to help."""
        res = client.post("/api/v1/auth/recover/confirm",
                          json={"reset_ticket": "not-a-jwt", "new_password": "a-new-password-1"})
        assert res.status_code == 400
        assert "hết hạn" in res.json()["detail"]
        assert "Mã xác minh" not in res.json()["detail"]

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param({"new_password": "a-new-password-1"}, id="neither"),
            pytest.param(
                {"new_password": "a-new-password-1", "reset_ticket": "t",
                 "identifier": "someone", "code": "123456"},
                id="both",
            ),
        ],
    )
    def test_confirm_demands_exactly_one_route(self, client, body):
        """Accepting both would let a caller send a ticket for one account and a
        code for another, and the handler would have to pick — a branch with no
        right answer is a branch that should not exist."""
        assert client.post("/api/v1/auth/recover/confirm", json=body).status_code == 422


class TestVerificationState:
    def test_verifying_an_email_marks_the_account(self, account):
        _, code = otp.issue(
            user_id=account["id"], purpose="verify_email",
            channel="email", destination=account["email"],
        )
        result = otp.verify(user_id=account["id"], purpose="verify_email", code=code)
        otp.mark_verified(account["id"], "verify_email", result["destination"])

        with system_scope("test read"):
            row = db._fetch_all(
                "SELECT email_verified_at FROM users WHERE id = %s", (account["id"],)
            )[0]
        assert row["email_verified_at"] is not None

    def test_verifying_a_phone_stores_the_canonical_number(self, account):
        _, code = otp.issue(
            user_id=account["id"], purpose="verify_phone",
            channel="sms", destination="+84 90 123 4567",
        )
        result = otp.verify(user_id=account["id"], purpose="verify_phone", code=code)
        otp.mark_verified(account["id"], "verify_phone", result["destination"])

        with system_scope("test read"):
            row = db._fetch_all(
                "SELECT phone_number, phone_verified_at FROM users WHERE id = %s",
                (account["id"],),
            )[0]
        assert row["phone_number"] == "+84901234567"
        assert row["phone_verified_at"] is not None

    def test_checking_a_reset_code_does_not_mark_anything_verified(self, account):
        """`verify` proves the code; `mark_verified` records the consequence.
        Fusing them would let a password reset silently mark an address as
        verified, which is a different claim."""
        _, code = otp.issue(
            user_id=account["id"], purpose="reset_password",
            channel="email", destination=account["email"],
        )
        otp.verify(user_id=account["id"], purpose="reset_password", code=code)
        with system_scope("test read"):
            row = db._fetch_all(
                "SELECT email_verified_at FROM users WHERE id = %s", (account["id"],)
            )[0]
        assert row["email_verified_at"] is None


class TestUnconfiguredEmailNeverLeaksTheCode:
    """A missing SMTP host must not turn the log into the delivery channel.

    This is the email twin of the rule `sms_service` states outright. It was
    NOT true until 2026-08-07: `_send` logged the whole body when `smtp_host`
    was empty, and the body of a verification email is the code. Nothing failed
    — that is what made it worth a test rather than a comment.
    """

    def test_sending_a_code_without_smtp_raises_instead_of_logging(
        self, monkeypatch, caplog
    ):
        import app.email_service as es

        monkeypatch.setattr(es.settings, "smtp_host", "")
        with caplog.at_level(logging.WARNING):
            with pytest.raises(es.EmailNotConfigured):
                es.send_verification_code_email("who@example.test", "424242",
                                                "verify_email")
        assert "424242" not in caplog.text

    def test_a_reset_link_may_still_fall_back_to_the_log(self, monkeypatch, caplog):
        """The documented dev convenience stays. The token is 32 bytes and
        single-use, which is a different risk from a six-digit code."""
        import app.email_service as es

        monkeypatch.setattr(es.settings, "smtp_host", "")
        with caplog.at_level(logging.WARNING):
            es.send_password_reset_email("who@example.test", "someone",
                                         "https://example.test/reset?t=abc")
        assert "https://example.test/reset?t=abc" in caplog.text

    def test_the_endpoint_reports_503_rather_than_a_server_error(
        self, client, account, monkeypatch
    ):
        """A misconfigured deployment is not the caller's fault, and the person
        needs to learn about it now rather than by never receiving a code."""
        import app.email_service as es

        monkeypatch.setattr(es.settings, "smtp_host", "")
        token = _access_token_for(account)
        res = client.post(
            "/api/v1/auth/verify/send",
            json={"channel": "email", "destination": account["email"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 503, res.text


class TestTheStatusEndpointTheScreenReadsFrom:
    """`GET /auth/verification-status` — what the verify page renders from.

    A separate endpoint rather than three more fields on `UserOut`: that model
    is the response of login, register, refresh AND `/me`, so widening it puts
    an extra column read on every authenticated request to serve one page.
    """

    def _get(self, client, account):
        return client.get(
            "/api/v1/auth/verification-status",
            headers={"Authorization": f"Bearer {_access_token_for(account)}"},
        )

    def test_a_fresh_account_has_proven_nothing(self, client, account):
        body = self._get(client, account).json()
        assert body["email"] == account["email"]
        assert body["email_verified"] is False
        assert body["phone_number"] == ""
        assert body["phone_verified"] is False

    def test_it_reflects_a_verification_that_actually_happened(self, client, account):
        otp.mark_verified(account["id"], "verify_email", account["email"].lower())
        body = self._get(client, account).json()
        assert body["email_verified"] is True

    def test_a_verified_phone_comes_back_in_full(self, client, account):
        """Half a number cannot answer the only question the page asks —
        "is that still the right number?" — and it belongs to the caller."""
        otp.mark_verified(account["id"], "verify_phone", "+84901234567")
        body = self._get(client, account).json()
        assert body["phone_number"] == "+84901234567"
        assert body["phone_verified"] is True

    def test_the_cooldown_comes_from_the_server_not_the_browser(self, client, account,
                                                                monkeypatch):
        """The countdown on screen is a courtesy layer; the server is the one
        that refuses. Hardcoding 60 in the SPA makes the two drift apart the
        first time someone tunes the env var."""
        monkeypatch.setattr(otp.settings, "otp_resend_cooldown_seconds", 90,
                            raising=False)
        body = self._get(client, account).json()
        assert body["resend_cooldown_seconds"] == 90
        assert body["code_ttl_minutes"] == int(otp.settings.otp_ttl_minutes)

    def test_it_says_whether_sms_can_be_sent_at_all(self, client, account):
        """Normal state on this deployment is False. The page needs it so the
        SMS button is disabled rather than issuing a challenge that cannot be
        delivered — a failed send still burns the cooldown, which then blocks
        the email channel for a minute."""
        body = self._get(client, account).json()
        assert isinstance(body["sms_available"], bool)

    def test_it_is_not_readable_without_a_session(self, client):
        assert client.get("/api/v1/auth/verification-status").status_code == 401


class TestNamingTheChallengeBeingAnswered:
    """`POST /auth/verify/confirm` and its `purpose` parameter.

    The thing being pinned is a cost, not a correctness bug. A code is bound to
    one purpose by its digest, so probing never accepts the wrong challenge —
    but every probe that misses spends an attempt on a challenge the person was
    not answering. With both channels live, five fat-fingered email codes kill
    the phone challenge too, and nothing on screen explains why.
    """

    def _confirm(self, client, account, code, purpose=None):
        return client.post(
            "/api/v1/auth/verify/confirm",
            json={"code": code, **({"purpose": purpose} if purpose else {})},
            headers={"Authorization": f"Bearer {_access_token_for(account)}"},
        )

    def _attempts(self, user_id, purpose) -> int:
        with system_scope("test read"):
            rows = db._fetch_all(
                "SELECT attempts FROM verification_codes "
                "WHERE user_id = %s AND purpose = %s AND consumed_at IS NULL",
                (str(user_id), purpose),
            )
        return int(rows[0]["attempts"]) if rows else -1

    def test_naming_the_purpose_leaves_the_other_challenge_untouched(
        self, client, account, no_cooldown
    ):
        """The whole reason the parameter exists."""
        otp.issue(user_id=account["id"], purpose="verify_phone",
                  channel="sms", destination="+84901234567")
        otp.issue(user_id=account["id"], purpose="verify_email",
                  channel="email", destination=account["email"])

        res = self._confirm(client, account, "000000", purpose="verify_email")
        assert res.status_code >= 400

        assert self._attempts(account["id"], "verify_email") == 1
        assert self._attempts(account["id"], "verify_phone") == 0, (
            "a wrong email code spent an attempt on the phone challenge"
        )

    def test_without_a_purpose_the_probe_still_erodes_both(
        self, client, account, no_cooldown
    ):
        """Pinned deliberately: this is the behaviour clients written before the
        parameter existed still get, and it must stay a known cost rather than
        quietly change under them."""
        otp.issue(user_id=account["id"], purpose="verify_phone",
                  channel="sms", destination="+84901234567")
        otp.issue(user_id=account["id"], purpose="verify_email",
                  channel="email", destination=account["email"])

        assert self._confirm(client, account, "000000").status_code >= 400

        assert self._attempts(account["id"], "verify_phone") == 1
        assert self._attempts(account["id"], "verify_email") == 1

    def test_a_named_purpose_verifies_the_right_one(self, client, account, no_cooldown):
        _, code = otp.issue(user_id=account["id"], purpose="verify_email",
                            channel="email", destination=account["email"])
        body = self._confirm(client, account, code, purpose="verify_email").json()
        assert body["verified"] is True
        assert body["purpose"] == "verify_email"

    def test_naming_the_wrong_purpose_refuses_rather_than_falling_back(
        self, client, account, no_cooldown
    ):
        """Otherwise the parameter would be a hint, not a constraint — and a
        hint cannot protect the budget it exists to protect."""
        _, code = otp.issue(user_id=account["id"], purpose="verify_email",
                            channel="email", destination=account["email"])
        assert self._confirm(client, account, code, purpose="verify_phone").status_code >= 400
        # ...and the email challenge is still there to be answered properly.
        assert self._confirm(client, account, code, purpose="verify_email").status_code == 200

    def test_reset_password_cannot_be_confirmed_through_this_endpoint(
        self, client, account, no_cooldown
    ):
        """A reset code sets a password; it is spent at `/recover/confirm`,
        together with the new one. Accepting it here would let a live session
        burn the challenge without ever choosing a password — and 422 at the
        schema is cheaper than a handler that has to remember why."""
        assert self._confirm(client, account, "123456",
                             purpose="reset_password").status_code == 422
