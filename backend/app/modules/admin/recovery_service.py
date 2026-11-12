"""Administrative account-recovery application workflow."""

from __future__ import annotations

from typing import Any, Callable, Dict

from app.modules.admin import user_service
from app.modules.identity import account_workflows
from app.modules.security import two_factor
from app.services import email
from app.modules.support import notifications


def assist(
    user_id: str,
    action: str,
    *,
    reason: str,
    operator_name: str,
    resolve_frontend_base_url: Callable[[], str],
    enqueue: Callable[..., Any],
) -> Dict[str, Any]:
    """Open a recovery path and notify the affected account."""
    target = user_service.get_user(user_id)
    if target is None:
        raise LookupError(user_id)

    if action == "clear_2fa":
        two_factor.disable(str(target["id"]))
        title = "Quản trị viên đã gỡ xác thực hai bước"
        body = (
            f"Do {operator_name or 'quản trị viên'} thực hiện. Lý do: {reason}. "
            "Nếu không phải bạn yêu cầu, hãy đổi mật khẩu và báo ngay."
        )
    else:
        # Tra theo email, không có email thì theo tên đăng nhập (hàm tra khớp
        # cả hai). Tài khoản không có email vẫn phải lấy lại được, mà đó lại
        # đúng là ca cần quản trị viên nhất. Liên kết được trả về để quản trị
        # viên chuyển tay qua kênh khác; thư chỉ là MỘT đường, không phải duy nhất.
        identifier = str(target.get("email") or "").strip() or str(target.get("username") or "")
        issued = account_workflows.issue_password_reset_link(
            identifier, resolve_frontend_base_url()
        )
        if issued is None:
            raise PermissionError("inactive")
        user, link = issued
        mail_to = str(user.get("email") or "").strip()
        if mail_to:
            enqueue(email.send_password_reset_email, mail_to, user["username"], link)
        target = {**target, "reset_link": link, "email_sent": bool(mail_to)}
        title = "Quản trị viên đã tạo liên kết đặt lại mật khẩu cho bạn"
        body = (
            f"Do {operator_name or 'quản trị viên'} thực hiện. Lý do: {reason}. "
            "Liên kết được gửi vào hộp thư của bạn và có thể được quản trị viên "
            "chuyển trực tiếp cho bạn. Nếu không phải bạn yêu cầu, hãy báo ngay."
        )

    notifications.notify(
        str(target["id"]),
        "security",
        title,
        body=body,
        link="/settings/security",
        severity="warning",
    )
    return target
