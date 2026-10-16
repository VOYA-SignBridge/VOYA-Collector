"""HTTP surface for one-time codes: verifying an address, and recovering an account.

Two flows, deliberately different in what they reveal
-----------------------------------------------------
**Verification** (`/verify/*`) is authenticated. The caller already proved who
they are, so errors can be specific: "that code is wrong", "wait 40 seconds".

**Recovery** (`/recover/*`) is not. Every response is the same regardless of
whether the account exists, whether the address matches, or whether delivery
worked — otherwise this endpoint becomes a way to enumerate accounts, and an
account list for a special-education programme is exactly the kind of thing that
must not leak. The cost is real: a person who mistypes their address gets a
cheerful "we sent a code" and no code. That trade is the standard one, and the
message says "if the account exists" so the wording does not actively mislead.

`recover/confirm` is where it gets subtle. It must verify the code AND set the
password, and it cannot say which half failed — so a wrong code and an unknown
account produce one indistinguishable refusal.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, validator

from app import otp
from app.auth import _fetch_user_by_login, get_current_user
from app.config import settings
from app.rate_limit import enforce_ip_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

#: One message for every outcome of a recovery request. Same string, same status.
_RECOVERY_GENERIC = (
    "Nếu tài khoản tồn tại, chúng tôi đã gửi mã xác minh. "
    "Mã có hiệu lực trong ít phút."
)


# `Literal`, not `Field(pattern=...)`. This project runs pydantic 1.10, where
# the constraint keyword is `regex` and an unknown `pattern` is accepted in
# silence, filed under schema extras, and never enforced — every field here
# using it was unvalidated while looking validated. `Literal` is enforced by
# both major versions and cannot rot the same way. What saved the channel
# fields meanwhile was `otp.issue`, which re-checks and raises 422 of its own.
Channel = Literal["email", "sms"]


class SendCodeRequest(BaseModel):
    channel: Channel
    # Absent means "the address already on the account" for email. Required for
    # SMS, because the account may not have a number yet — that is the point of
    # verifying one.
    destination: Optional[str] = Field(None, max_length=255)


class ConfirmCodeRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=12)
    # Which challenge this code answers. Optional so the clients written before
    # it existed keep working; see `confirm_verification_code` for what naming
    # it buys and what omitting it costs. `reset_password` is deliberately not
    # offered — that code is spent at `/recover/confirm`, together with the new
    # password, and accepting it here would burn the challenge without one.
    purpose: Optional[Literal["verify_email", "verify_phone"]] = None


class RecoverStartRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=255)
    channel: Channel = "email"


class RecoverVerifyRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=4, max_length=12)


class RecoverConfirmRequest(BaseModel):
    """Hai đường vào, dùng đúng MỘT trong hai.

    * `reset_ticket` — đường của giao diện: mã đã được `/recover/verify` kiểm.
    * `identifier` + `code` — đường một-lượt, giữ lại cho khách gọi API trực
      tiếp và cho các test đã viết theo hợp đồng cũ.
    """

    new_password: str = Field(..., min_length=8, max_length=128)
    reset_ticket: Optional[str] = Field(None, max_length=4096)
    identifier: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, min_length=4, max_length=12)

    @validator("code", always=True)
    def _exactly_one_route(cls, code, values):  # noqa: N805
        # Chạy trên trường KHAI SAU CÙNG, nếu không `values` chưa có đủ.
        has_pair = bool(values.get("identifier")) and bool(code)
        if bool(values.get("reset_ticket")) == has_pair:
            raise ValueError(
                "gửi reset_ticket, hoặc gửi identifier kèm code — không phải cả hai"
            )
        return code


def _translate(exc: otp.OtpError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _deliver(channel: str, destination: str, code: str, purpose: str) -> None:
    """Hand the code to a transport. Raises if the transport cannot deliver.

    The code is passed as an argument and appears in no log line on either
    branch — see `sms_service` for why "log it in dev" is refused outright.
    """
    if channel == "sms":
        from app.sms_service import send_sms

        send_sms(destination, f"Mã xác minh VOYA-Collector: {code}")
        return
    from app.email_service import send_verification_code_email

    send_verification_code_email(destination, code, purpose)


# --------------------------------------------------------------------- verify (authed)


@router.get("/verification-status")
def verification_status(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """What the account has already proven, so the screen can stop asking.

    A separate endpoint rather than three more fields on `UserOut`: that model
    is the response of login, register, refresh AND `/me`, so widening it puts
    an extra column read on every authenticated request to serve one page.

    The phone number is returned in full. It belongs to the caller, who is
    authenticated, and half a number is not enough to answer the only question
    this page exists to answer — "is that still the right number?".
    """
    from app.auth import _identity_cursor

    with _identity_cursor() as cur:
        cur.execute(
            "SELECT email, email_verified_at, phone_number, phone_verified_at "
            "FROM users WHERE id = %s",
            (str(user["id"]),),
        )
        row = cur.fetchone() or {}

    return {
        "email": row.get("email") or user.get("email") or "",
        "email_verified": row.get("email_verified_at") is not None,
        "phone_number": row.get("phone_number") or "",
        "phone_verified": row.get("phone_verified_at") is not None,
        # Giao diện cần con số này để đếm ngược, và viết cứng ở hai nơi thì
        # một hôm nào đó chúng lệch nhau.
        "resend_cooldown_seconds": int(settings.otp_resend_cooldown_seconds),
        "code_ttl_minutes": int(settings.otp_ttl_minutes),
        "sms_available": _sms_available(),
    }


def _sms_available() -> bool:
    from app.sms_service import sms_available

    return bool(sms_available())


@router.post("/verify/send")
def send_verification_code(
    payload: SendCodeRequest,
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Send a code to prove the caller controls an address."""
    enforce_ip_limit(request, bucket="otp_send", max_calls=20, window=3600)

    purpose = "verify_phone" if payload.channel == "sms" else "verify_email"
    raw_destination = payload.destination or (
        user.get("email") if payload.channel == "email" else ""
    )

    from app.sms_service import SmsNotConfigured, sms_available

    if payload.channel == "sms" and not sms_available():
        # Refused before a challenge is minted. Issuing one that can never be
        # delivered would burn the cooldown and leave the account unable to
        # retry over email for a minute.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMS chưa được cấu hình trên hệ thống này; hãy dùng kênh email.",
        )

    try:
        challenge_id, code = otp.issue(
            user_id=user["id"], purpose=purpose,
            channel=payload.channel, destination=raw_destination or "",
        )
    except otp.OtpError as exc:
        raise _translate(exc) from exc

    from app.email_service import EmailNotConfigured

    try:
        _deliver(payload.channel, otp.normalize_destination(
            payload.channel, raw_destination or ""), code, purpose)
    except (SmsNotConfigured, EmailNotConfigured) as exc:
        # Both transports refuse rather than log the code, so both arrive here.
        # 503 and not 500: the deployment is misconfigured, the request was fine.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "challenge_id": challenge_id,
        "purpose": purpose,
        "channel": payload.channel,
        "expires_in_minutes": settings.otp_ttl_minutes,
    }


@router.post("/verify/confirm")
def confirm_verification_code(
    payload: ConfirmCodeRequest,
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Check the code and record the address as proven.

    Name the challenge with `purpose` whenever you know it
    ------------------------------------------------------
    Without it this probes `verify_phone` then `verify_email`, and the probe is
    not free: a wrong code **decrements the attempt counter of every challenge
    it touches**. Someone with both a phone and an email challenge live, who
    fat-fingers their email code twice, has spent four of their ten attempts and
    burnt half the budget of a challenge they were not even answering.

    The fallback stays because clients written before this parameter existed
    still call without it, and because the code itself is bound to one purpose
    by its digest — a phone code cannot satisfy the email challenge, so probing
    is wrong about cost, never about correctness.

    `VerifyContactPage` keeps exactly one flow open, which sidesteps the whole
    problem in the browser. It sends `purpose` anyway: the guarantee then lives
    in the request rather than in a screen's state machine, which is where the
    second client — a mobile app, an integration — can actually reach it.
    """
    enforce_ip_limit(request, bucket="otp_confirm", max_calls=30, window=3600)

    candidates = (payload.purpose,) if payload.purpose else ("verify_phone", "verify_email")

    last: Optional[otp.OtpError] = None
    for purpose in candidates:
        try:
            result = otp.verify(user_id=user["id"], purpose=purpose, code=payload.code)
        except otp.OtpError as exc:
            last = exc
            continue
        otp.mark_verified(user["id"], purpose, result["destination"])
        return {"verified": True, "purpose": purpose, "channel": result["channel"]}

    raise _translate(last or otp.OtpError("mã xác minh không đúng hoặc đã hết hạn"))


# ------------------------------------------------------------------ recover (anonymous)


@router.post("/recover/start")
def start_recovery(payload: RecoverStartRequest, request: Request) -> Dict[str, str]:
    """Begin an account recovery. The response never says whether the account exists."""
    enforce_ip_limit(request, bucket="otp_recover", max_calls=10, window=3600)

    user = _fetch_user_by_login(payload.identifier)
    if not user or not user.get("is_active", True):
        # Same message, same status, no timing shortcut worth the complexity of
        # equalising here — the expensive part (delivery) is skipped either way,
        # which is a signal the existing forgot-password endpoint also has.
        logger.info("[OTP] recovery requested for an unknown identifier")
        return {"message": _RECOVERY_GENERIC}

    from app.sms_service import sms_available

    channel = payload.channel
    if channel == "sms" and not sms_available():
        channel = "email"  # silently, so the response stays uniform

    destination = user["email"] if channel == "email" else (user.get("phone_number") or "")
    if not destination:
        return {"message": _RECOVERY_GENERIC}

    try:
        _, code = otp.issue(
            user_id=user["id"], purpose="reset_password",
            channel=channel, destination=destination,
        )
    except otp.OtpError:
        # Includes the resend cooldown. Reporting it would confirm the account
        # exists AND that someone recently asked — two facts, both useful to an
        # attacker and neither useful to a stranger who mistyped an address.
        return {"message": _RECOVERY_GENERIC}

    try:
        _deliver(channel, destination, code, "reset_password")
    except Exception as exc:
        logger.error("[OTP] recovery delivery failed: %s", type(exc).__name__)

    return {"message": _RECOVERY_GENERIC}


def _generic_code_refusal() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Mã xác minh không đúng hoặc đã hết hạn.",
    )


def _spend_recovery_code(identifier: str, code: str) -> Dict[str, Any]:
    """Burn the recovery code and return the account it belonged to.

    One refusal for every failure: a wrong code, an expired challenge and an
    account that never existed are indistinguishable from out here. Only
    `too_many_attempts` is surfaced, because it tells a legitimate person to
    request a new code and tells an attacker only that they already lost.
    """
    user = _fetch_user_by_login(identifier)
    if not user or not user.get("is_active", True):
        raise _generic_code_refusal()

    try:
        otp.verify(user_id=user["id"], purpose="reset_password", code=code)
    except otp.OtpError as exc:
        if exc.code == "too_many_attempts":
            raise _translate(exc) from exc
        raise _generic_code_refusal() from exc
    return user


@router.post("/recover/verify")
def verify_recovery_code(payload: RecoverVerifyRequest, request: Request) -> Dict[str, Any]:
    """Check a recovery code and hand back a short-lived ticket.

    Splitting this off from `/recover/confirm` is what lets the screen answer
    "is my code right?" before asking for a new password — the shape every
    mainstream reset flow has, and the reason the old screen had to ask for the
    identifier, the code and two password fields at once.

    It shares `otp_recover_confirm`'s rate-limit bucket **on purpose**: the code
    is now checkable at two endpoints, and a per-endpoint budget would hand an
    attacker twice the guesses for splitting a form in half. The five-attempt
    cap on the challenge row bounds guessing either way; this bounds the noise.
    """
    enforce_ip_limit(request, bucket="otp_recover_confirm", max_calls=20, window=3600)

    from app.auth import PASSWORD_RESET_TICKET_MINUTES, create_password_reset_ticket

    user = _spend_recovery_code(payload.identifier, payload.code)
    logger.info("[OTP] recovery code accepted for user %s", user["id"])
    return {
        "reset_ticket": create_password_reset_ticket(user["id"]),
        "expires_in_minutes": PASSWORD_RESET_TICKET_MINUTES,
    }


@router.post("/recover/confirm")
def confirm_recovery(payload: RecoverConfirmRequest, request: Request) -> Dict[str, str]:
    """Set a new password, given either a reset ticket or a code."""
    enforce_ip_limit(request, bucket="otp_recover_confirm", max_calls=20, window=3600)

    if len(payload.new_password) < int(settings.min_password_length):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mật khẩu phải có ít nhất {settings.min_password_length} ký tự.",
        )

    from app.auth import set_password_and_revoke_sessions, verify_password_reset_ticket

    if payload.reset_ticket:
        user_id = verify_password_reset_ticket(payload.reset_ticket)
        if not user_id:
            # Distinct from the code refusal, and safe to be: holding an expired
            # ticket already proves the code was right, so nothing is revealed.
            # Saying "wrong code" here would send someone to re-read an email
            # whose code is spent, which is the one thing that cannot help them.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phiên đặt lại mật khẩu đã hết hạn. Hãy xin mã mới.",
            )
    else:
        user_id = _spend_recovery_code(payload.identifier or "", payload.code or "")["id"]

    set_password_and_revoke_sessions(user_id, payload.new_password)
    logger.info("[OTP] password reset completed via code for user %s", user_id)
    return {"message": "Mật khẩu đã được đặt lại. Vui lòng đăng nhập lại."}
