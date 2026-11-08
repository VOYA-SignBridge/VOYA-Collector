"""Administrative account-recovery application workflow."""

from __future__ import annotations

from typing import Any, Callable, Dict

from app.modules.admin import user_service
from app.modules.identity import account_workflows
from app.modules.security import two_factor
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
        account_workflows.queue_password_reset(
            str(target.get("email") or ""), resolve_frontend_base_url(), enqueue
        )
        title = "Quản trị viên đã gửi lại liên kết đặt lại mật khẩu"
        body = (
            f"Do {operator_name or 'quản trị viên'} thực hiện. Lý do: {reason}. "
            "Kiểm tra hộp thư của bạn."
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
