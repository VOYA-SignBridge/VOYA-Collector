"""Application workflows for account lifecycle side effects.

HTTP routers own request validation and status translation.  This module owns
identity-plane persistence, OTP issuance and outbound account email dispatch.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict

from app.modules.identity import _web_compat as identity
from app.modules.security import otp
from app.modules.support import notifications
from app.services import email


logger = logging.getLogger(__name__)


class AccountWorkflowError(Exception):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def send_welcome_verification(user: Dict[str, Any]) -> None:
    """Issue and send the registration verification code, fail-soft."""
    try:
        _, code = otp.issue(
            user_id=user["id"],
            purpose="verify_email",
            channel="email",
            destination=user["email"],
        )
        email.send_verification_code_email(user["email"], code, "verify_email")
    except Exception as exc:  # registration has already committed
        logger.warning(
            "[REGISTER] không gửi được mã xác minh cho %s: %s",
            user["id"],
            type(exc).__name__,
        )


def issue_password_reset_link(identifier: str, frontend_base_url: str):
    """Issue a reset token; return ``(user, link)`` or ``None`` (no active account)."""
    result = identity.request_password_reset(identifier.strip())
    if not result:
        return None
    user, token = result
    return user, f"{frontend_base_url}/reset-password?token={token}"


def queue_password_reset(
    identifier: str,
    frontend_base_url: str,
    enqueue: Callable[..., Any],
) -> bool:
    """Issue a reset token and enqueue its email without revealing lookup state."""
    issued = issue_password_reset_link(identifier, frontend_base_url)
    if not issued:
        return False
    user, reset_link = issued
    enqueue(email.send_password_reset_email, user["email"], user["username"], reset_link)
    return True


def note_password_reset_by_link(user_id: str, request: Any = None) -> None:
    """Ghi kiểm toán + báo chủ tài khoản sau khi một liên kết đặt lại được DÙNG.

    Trang đặt lại mật khẩu không cần đăng nhập, nên lúc này KHÔNG có phạm vi
    tổ chức. Cả `audit.record` lẫn `notifications.notify` đều cần một phạm vi
    và đều nuốt lỗi — gọi trần thì dấu vết mất lặng lẽ. Nên vào đúng tổ chức
    của chủ tài khoản trước.

    Không bao giờ ném lên: mật khẩu ĐÃ đổi xong, một lỗi ghi vết không được
    biến lượt đặt lại thành công thành "thất bại" trên màn hình.
    """
    try:
        from app.modules.saas.tenant_context import tenant_scope
        from app.modules.saas.tenant_middleware import _tenant_of_user
        from app.modules.security import audit

        tenant = _tenant_of_user(str(user_id))
        if not tenant:
            logger.error("[RESET] khong tim thay to chuc cua %s, bo qua ghi vet", user_id)
            return
        user = identity._fetch_user_by_id(str(user_id)) or {}
        with tenant_scope(tenant):
            audit.record(
                "security.password.reset_by_link",
                actor={"id": str(user_id), "username": user.get("username")},
                target_type="user",
                target_id=str(user_id),
                detail={"sessions_revoked": True},
                request=request,
            )
            notifications.notify(
                str(user_id),
                "security",
                "Mật khẩu của bạn vừa được đặt lại",
                body=("Mật khẩu được đặt lại bằng liên kết đặt lại mật khẩu. Mọi "
                      "phiên đăng nhập cũ đã bị đăng xuất và liên kết không dùng "
                      "lại được. Nếu không phải bạn, hãy báo quản trị viên ngay."),
                link="/settings/security",
                severity="warning",
            )
    except Exception as exc:  # noqa: BLE001 — xem docstring
        logger.error("[RESET] ghi vet sau dat lai mat khau that bai: %s",
                     exc.__class__.__name__)


def apply_password_change(user_id: str, new_password: str) -> None:
    """Change the password and invalidate every existing session."""
    with identity._identity_cursor() as cursor:
        identity._apply_password_reset(cursor, str(user_id), new_password)


def begin_email_change(user: Dict[str, Any], new_email: str) -> Dict[str, str]:
    """Validate a new mailbox, issue its proof code and send it."""
    normalized = str(new_email).strip().lower()
    if normalized == str(user.get("email") or "").strip().lower():
        raise AccountWorkflowError(
            "Địa chỉ mới trùng địa chỉ đang dùng.", status_code=400
        )

    with identity._identity_cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM users WHERE lower(email) = %s AND id <> %s",
            (normalized, str(user["id"])),
        )
        if cursor.fetchone():
            raise AccountWorkflowError(
                "Địa chỉ này đã có tài khoản khác dùng.", status_code=409
            )

    if identity.find_user_with_same_mailbox(
        normalized, exclude_user_id=str(user["id"])
    ):
        raise AccountWorkflowError(
            "Hộp thư này đã có tài khoản khác dùng "
            "(địa chỉ viết khác nhưng cùng hộp thư).",
            status_code=409,
        )

    challenge_id, code = otp.issue(
        user_id=user["id"],
        purpose="verify_email",
        channel="email",
        destination=normalized,
    )
    email.send_verification_code_email(normalized, code, "verify_email")
    return {"challenge_id": challenge_id, "sent_to": normalized}


def confirm_email_change(user: Dict[str, Any], code: str) -> Dict[str, str]:
    """Consume mailbox proof, persist the address and notify the account."""
    result = otp.verify(user_id=user["id"], purpose="verify_email", code=code)
    new_email = str(result["destination"]).strip().lower()
    old_email = str(user.get("email") or "")

    with identity._identity_cursor() as cursor:
        cursor.execute(
            "UPDATE users SET email = %s, email_verified_at = NOW() WHERE id = %s",
            (new_email, str(user["id"])),
        )

    notifications.notify(
        str(user["id"]),
        "security",
        "Địa chỉ email đã được đổi",
        body=f"Từ {old_email} sang {new_email}.",
        link="/settings/security",
        severity="critical",
    )
    return {"old_email": old_email, "new_email": new_email}
