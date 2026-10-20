"""Nâng quyền tạm thời cho thao tác nhạy cảm: nhập lại mật khẩu, có hiệu lực 5 phút.

Vì sao mẫu này chứ không phải "mã PIN quản trị"
------------------------------------------------
Đây là mẫu **sudo mode** của GitHub, cũng là cách AWS Console, Google Workspace
và Stripe Dashboard bảo vệ thao tác nhạy cảm. Nó được chọn thay vì một mã PIN
dùng chung vì ba lý do cụ thể:

* Một PIN dùng chung là **một bí mật thứ hai** phải cất, phải xoay vòng, và
  không gắn với ai. Khi nó rò rỉ, nhật ký kiểm toán chỉ ghi được "ai đó biết
  PIN".
* Mật khẩu thì đã gắn với một tài khoản, đã được băm bằng passlib, và đã có
  đường xử lý khi bị lộ (đổi mật khẩu, thu hồi phiên).
* Nó chống đúng thứ cần chống: một phiên đăng nhập **bị bỏ quên trên máy chung**
  hoặc bị chiếm qua XSS. Kẻ chiếm phiên có cookie nhưng không có mật khẩu.

Cái nó KHÔNG chống: một người đã biết mật khẩu. Đó là việc của OTP, và
`app/otp.py` đã sẵn sàng nếu sau này muốn thêm — hàm `require_sudo` là chỗ duy
nhất phải sửa.

Vì sao 5 phút
-------------
Đủ dài để đổi vài thiết lập liên tiếp mà không phải gõ lại; đủ ngắn để một cái
laptop bỏ quên trong phòng lab không còn ở trạng thái nâng quyền khi người kế
tiếp ngồi xuống. Cùng bậc thời gian GitHub dùng (họ chọn 2 giờ cho thao tác nhẹ
hơn nhiều — ở đây thao tác đổi hạn ngạch toàn hệ thống nên chặt hơn).
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import Depends, HTTPException, Request, status

from app.auth import get_current_user, require_admin

logger = logging.getLogger(__name__)

_KEY_PREFIX = "sudo:"

#: Cửa sổ nâng quyền, giây.
SUDO_TTL_SECONDS = 300


def _client():
    from app.rate_limit import _client as shared_client

    return shared_client()


def grant(user_id: str) -> int:
    """Đánh dấu người này đã nâng quyền. Trả về số giây hiệu lực."""
    client = _client()
    if client is None:
        # Fail-CLOSED, ngược với `trial.py`.
        #
        # Redis chết mà vẫn cấp nâng quyền là biến một sự cố hạ tầng thành một
        # lỗ bảo mật. Thao tác nhạy cảm bị chặn trong lúc Redis chết là đúng —
        # phiền, nhưng đúng.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không xác minh được lúc này. Thử lại sau ít phút.",
        )
    client.setex(f"{_KEY_PREFIX}{user_id}", SUDO_TTL_SECONDS, "1")
    return SUDO_TTL_SECONDS


def revoke(user_id: str) -> None:
    client = _client()
    if client is not None:
        client.delete(f"{_KEY_PREFIX}{user_id}")


def seconds_remaining(user_id: str) -> int:
    client = _client()
    if client is None:
        return 0
    ttl = client.ttl(f"{_KEY_PREFIX}{user_id}")
    return max(0, int(ttl)) if ttl and ttl > 0 else 0


def elevate(user: Dict[str, Any], password: str) -> int:
    """Xác minh mật khẩu rồi nâng quyền. Ném lỗi nếu sai."""
    from app.auth import authenticate_user

    if not password or authenticate_user(user["email"], password) is None:
        # Ghi lại: mật khẩu sai ở bước nâng quyền nghĩa là có người đang ngồi
        # trước một phiên KHÔNG phải của họ. Đó là tín hiệu đáng chú ý hơn hẳn
        # một lần đăng nhập sai.
        logger.warning("[SUDO] sai mật khẩu khi nâng quyền, user=%s", user["id"])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mật khẩu không đúng.",
        )
    logger.info("[SUDO] nâng quyền %ds cho user=%s", SUDO_TTL_SECONDS, user["id"])
    return grant(str(user["id"]))


def require_sudo(
    request: Request,
    user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Dependency: quản trị viên nền tảng ĐANG ở trạng thái nâng quyền.

    Trả 403 kèm `code: "sudo_required"` chứ không phải 401: người dùng đã xác
    thực, chỉ là chưa đủ mức. Giao diện dùng mã đó để mở hộp thoại nhập lại mật
    khẩu thay vì đá người ta về màn hình đăng nhập — đá về màn hình đăng nhập là
    cách chắc chắn khiến họ mất công việc đang làm dở.
    """
    if seconds_remaining(str(user["id"])) <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "sudo_required",
                "message": "Thao tác này cần xác thực lại bằng mật khẩu.",
                "ttl_seconds": SUDO_TTL_SECONDS,
            },
        )
    return user
