"""One-time codes for email and phone, and the rules that make them worth having.

A six-digit code is a weak secret on purpose — it has to be typeable from an SMS.
Everything here exists to make that weakness survivable:

* **The code is never stored.** Only `HMAC(pepper, purpose‖destination‖code)`,
  with the pepper outside the database. See `app/tokens.py` for why a plain hash
  would be decoration.
* **The code is never logged.** Not at DEBUG, not inside an exception message,
  not in a metric label. Delivery failures log the *destination* and the
  *purpose*; the digits do not appear in any artefact this process writes. There
  is a test asserting this against captured log output, because "we were careful"
  is not a control.
* **Guessing is bounded, not merely slowed.** One million codes and unlimited
  attempts is a solved problem for an attacker. Five attempts and the challenge
  is dead — the counter is on the row, so it survives restarts and cannot be
  reset by opening a new connection.
* **One live challenge per person per purpose.** Enforced by a partial unique
  index, not just by this module.

The channel-switch case
-----------------------
Someone requests a password reset by email, then returns and picks SMS instead.
Three things could happen, and only one of them is right:

1. Both codes stay valid — the email code sits in an inbox and still opens the
   account long after the person moved on. This is the common implementation and
   it is wrong.
2. The switch is refused until the first expires — safe, and users read it as
   the system being broken, so they retry until something works.
3. **Issuing the new challenge closes the old one.** The person has one live
   code, on the channel they last chose.

`issue()` does (3), and the partial unique index means the database refuses (1)
even if some future caller forgets.

What this module does NOT do
----------------------------
It does not send anything. Delivery is the caller's job — `email_service` for
mail, and there is no SMS provider configured on this deployment, so
`send_sms` raises rather than pretending. A verification system whose SMS silently
does nothing is worse than one that admits it cannot send.
"""

from __future__ import annotations

import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from app.config import settings
from app.tokens import codes_match, hash_code  # noqa: F401  (re-exported for tests)

logger = logging.getLogger(__name__)

#: Digits in a code. Six is what people expect from an SMS and what fits in a
#: notification preview; the attempt cap, not the length, is what bounds guessing.
CODE_DIGITS = 6

PURPOSES: Tuple[str, ...] = ("verify_email", "verify_phone", "reset_password")
CHANNELS: Tuple[str, ...] = ("email", "sms")

#: E.164-ish. Deliberately permissive about country conventions and strict about
#: shape: a destination that is not canonical is a destination two rows can
#: disagree about, and `+84 90 123 4567` must not be a different person from
#: `+84901234567`.
_PHONE_RE = re.compile(r"\A\+[1-9]\d{7,14}\Z")


class OtpError(Exception):
    """A challenge operation refused for a reason the caller may act on."""

    def __init__(self, message: str, *, status_code: int = 400, code: str = "otp_error"):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_phone(value: str) -> str:
    """Canonical E.164, or raise.

    Spaces, dashes and parentheses are stripped before validation — people type
    them and they carry no information. A leading `0` with no `+` is rejected
    rather than guessed at: inferring the country code from the server's locale
    is how a Vietnamese number becomes a US one.
    """
    cleaned = re.sub(r"[\s\-().]", "", value or "")
    if not cleaned:
        raise OtpError("số điện thoại là bắt buộc", status_code=422, code="phone_required")
    if not _PHONE_RE.match(cleaned):
        raise OtpError(
            "số điện thoại phải ở dạng quốc tế, ví dụ +84901234567",
            status_code=422,
            code="phone_invalid",
        )
    return cleaned


def normalize_email(value: str) -> str:
    email = (value or "").strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise OtpError("địa chỉ email không hợp lệ", status_code=422, code="email_invalid")
    return email


def normalize_destination(channel: str, value: str) -> str:
    if channel == "sms":
        return normalize_phone(value)
    return normalize_email(value)


def new_code() -> str:
    """A uniformly random six-digit code.

    `secrets.randbelow`, not `random`: the latter is a Mersenne Twister seeded
    from the clock, and a few observed codes are enough to predict the rest.
    Zero-padded so `000123` stays six characters — a code that is sometimes five
    digits leaks a bit of entropy and confuses the input field.
    """
    return f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"


def _live_challenge(user_id: str, purpose: str) -> Optional[Dict[str, Any]]:
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        "SELECT * FROM verification_codes "
        "WHERE user_id = %s AND purpose = %s AND consumed_at IS NULL",
        (str(user_id), purpose),
    )
    return dict(rows[0]) if rows else None


def seconds_until_resend_allowed(user_id: str, purpose: str) -> int:
    """How long the caller must wait before a new code may be issued.

    A cooldown, not a rate limit: the rate limiter protects the endpoint, this
    protects the *recipient*. Without it, anyone who knows an address can have
    the system text a stranger once a second.
    """
    live = _live_challenge(user_id, purpose)
    if not live:
        return 0
    age = (_now() - live["created_at"]).total_seconds()
    remaining = int(settings.otp_resend_cooldown_seconds - age)
    return max(0, remaining)


def issue(
    *,
    user_id: str,
    purpose: str,
    channel: str,
    destination: str,
) -> Tuple[str, str]:
    """Mint a challenge. Returns (challenge_id, RAW CODE) — the only time the code exists.

    The caller delivers it and then forgets it. Nothing else in the system can
    read it back, which is the point.

    Any live challenge for the same (user, purpose) is consumed first, whatever
    channel it was on. See the module docstring for why that is the correct
    handling of a mid-flow channel switch.
    """
    from app.storage.metadata_db import _execute

    if purpose not in PURPOSES:
        raise OtpError(f"purpose must be one of {', '.join(PURPOSES)}", status_code=422)
    if channel not in CHANNELS:
        raise OtpError(f"channel must be one of {', '.join(CHANNELS)}", status_code=422)

    dest = normalize_destination(channel, destination)

    wait = seconds_until_resend_allowed(user_id, purpose)
    if wait > 0:
        raise OtpError(
            f"vui lòng đợi {wait} giây trước khi yêu cầu mã mới",
            status_code=429,
            code="resend_too_soon",
        )

    code = new_code()
    challenge_id = str(uuid.uuid4())
    expires_at = _now() + timedelta(minutes=max(1, int(settings.otp_ttl_minutes)))

    # Closing the previous challenge and opening the new one happen against the
    # partial unique index, so a race between two requests cannot leave two live
    # rows: the loser's INSERT violates the index and is refused.
    _execute(
        "UPDATE verification_codes SET consumed_at = NOW() "
        "WHERE user_id = %s AND purpose = %s AND consumed_at IS NULL",
        (str(user_id), purpose),
    )
    _execute(
        "INSERT INTO verification_codes("
        "  challenge_id, user_id, purpose, channel, destination, code_hash,"
        "  max_attempts, expires_at"
        ") VALUES(%s, %s, %s, %s, %s, %s, %s, %s)",
        (
            challenge_id, str(user_id), purpose, channel, dest,
            hash_code(code, purpose=purpose, subject=dest),
            int(settings.otp_max_attempts), expires_at,
        ),
    )

    # Destination and purpose, never the code. This line is what a support
    # engineer needs to answer "did we send it?"; the digits would answer
    # "what was it?", which nobody may ask.
    logger.info("[OTP] issued purpose=%s channel=%s to=%s", purpose, channel, _mask(dest))
    return challenge_id, code


def _mask(destination: str) -> str:
    """Enough of the destination to recognise it, not enough to harvest it.

    Logs are shipped to Loki and read by more people than the database is.
    """
    if "@" in destination:
        name, _, domain = destination.partition("@")
        head = name[:2] if len(name) > 2 else name[:1]
        return f"{head}***@{domain}"
    return f"{destination[:4]}***{destination[-2:]}" if len(destination) > 6 else "***"


def verify(*, user_id: str, purpose: str, code: str) -> Dict[str, Any]:
    """Check a code. Consumes the challenge on success, counts the attempt on failure.

    Failure modes are deliberately NOT distinguished to the caller: an expired
    challenge, a wrong code and a challenge that never existed all return the
    same refusal. Telling them apart would let someone with a stolen address
    learn whether a reset is in flight.

    The attempt counter is incremented BEFORE the comparison. If the process
    dies mid-verification the attempt is still spent — the failure mode of a
    crash must be one fewer guess, never one more.
    """
    from app.storage.metadata_db import _execute, _fetch_all

    generic = OtpError(
        "mã xác minh không đúng hoặc đã hết hạn",
        status_code=400,
        code="code_invalid",
    )

    live = _live_challenge(user_id, purpose)
    if not live:
        raise generic
    if live["expires_at"] <= _now():
        raise generic

    if live["attempts"] >= live["max_attempts"]:
        _execute(
            "UPDATE verification_codes SET consumed_at = NOW() WHERE challenge_id = %s",
            (str(live["challenge_id"]),),
        )
        raise OtpError(
            "đã nhập sai quá số lần cho phép; hãy yêu cầu mã mới",
            status_code=429,
            code="too_many_attempts",
        )

    _execute(
        "UPDATE verification_codes SET attempts = attempts + 1 WHERE challenge_id = %s",
        (str(live["challenge_id"]),),
    )

    candidate = hash_code(
        (code or "").strip(), purpose=purpose, subject=live["destination"]
    )
    if not codes_match(candidate, live["code_hash"]):
        remaining = live["max_attempts"] - live["attempts"] - 1
        logger.info(
            "[OTP] failed attempt purpose=%s to=%s remaining=%s",
            purpose, _mask(live["destination"]), max(0, remaining),
        )
        raise generic

    _execute(
        "UPDATE verification_codes SET consumed_at = NOW() WHERE challenge_id = %s",
        (str(live["challenge_id"]),),
    )
    logger.info("[OTP] verified purpose=%s to=%s", purpose, _mask(live["destination"]))
    return {
        "challenge_id": str(live["challenge_id"]),
        "purpose": purpose,
        "channel": live["channel"],
        "destination": live["destination"],
    }


def mark_verified(user_id: str, purpose: str, destination: str) -> None:
    """Record on the ACCOUNT that an address was proven.

    Separate from `verify` so the proof and its consequence are two steps: a
    caller that only wants to check a code (password reset) does not
    accidentally mark an address as verified.
    """
    from app.storage.metadata_db import _execute

    if purpose == "verify_email":
        _execute(
            "UPDATE users SET email_verified_at = NOW() WHERE id = %s AND lower(email) = %s",
            (str(user_id), destination),
        )
    elif purpose == "verify_phone":
        _execute(
            "UPDATE users SET phone_number = %s, phone_verified_at = NOW() WHERE id = %s",
            (destination, str(user_id)),
        )


def purge_expired(older_than_days: int = 7) -> int:
    """Drop dead challenges. Every retained row is a digest with no purpose."""
    from app.storage.metadata_db import _execute

    _execute(
        "DELETE FROM verification_codes "
        "WHERE expires_at < NOW() - make_interval(days => %s)",
        (int(older_than_days),),
    )
    return 0
