"""Xác thực hai bước: đăng ký, xác nhận, tắt, cấp lại mã khôi phục.

Việc KIỂM mã lúc đăng nhập không nằm ở đây — nó thuộc `routers/auth.py`, vì nó
xảy ra khi chưa có phiên đăng nhập nào. Mọi đường trong file này đòi người dùng
đã đăng nhập rồi.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app import activity, two_factor
from app.auth import get_current_user, verify_password

router = APIRouter(prefix="/2fa", tags=["two-factor"])


class CodeRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class PasswordRequest(BaseModel):
    password: str = Field(..., min_length=1)


def _bad(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _require_password(current_user: Dict[str, Any], password: str) -> None:
    """Thao tác hạ thấp bảo mật thì phải nhập lại mật khẩu.

    Không phải nghi thức: nếu tắt được 2FA chỉ bằng một cookie phiên, thì bất kỳ
    ai mượn được máy đang mở của người dùng đều gỡ được lớp bảo vệ thứ hai — tức
    là lớp đó chỉ bảo vệ trước kẻ ở xa, không bảo vệ trước kẻ ngồi cạnh.
    """
    if not verify_password(password, current_user.get("password_hash") or ""):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mật khẩu không đúng.")


@router.get("/status")
def get_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    return two_factor.status(current_user["id"])


@router.post("/enroll")
def enroll(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Cấp bí mật mới ở trạng thái CHƯA bật, kèm URI cho ứng dụng xác thực.

    Bí mật trả về dạng đọc được — bắt buộc, vì người dùng phải nhập nó vào ứng
    dụng xác thực. Nó chỉ đi qua kết nối đã đăng nhập và không được ghi vào nhật
    ký ở bất kỳ đâu.
    """
    try:
        out = two_factor.begin_enrollment(
            current_user["id"],
            account_label=str(current_user.get("email") or current_user.get("username")))
    except two_factor.TwoFactorError as exc:
        raise _bad(exc)
    return {
        **out,
        # Nhóm 4 ký tự để người ta gõ tay được khi máy ảnh không quét được mã.
        "secret_grouped": " ".join(out["secret"][i:i + 4]
                                   for i in range(0, len(out["secret"]), 4)),
    }


@router.post("/confirm")
def confirm(payload: CodeRequest,
            current_user: Dict[str, Any] = Depends(get_current_user)):
    """Bật 2FA và trả về mã khôi phục — lần DUY NHẤT chúng đọc được."""
    try:
        codes = two_factor.confirm_enrollment(current_user["id"], payload.code)
    except two_factor.TwoFactorError as exc:
        raise _bad(exc)
    return {"enabled": True, "recovery_codes": codes}


@router.post("/disable")
def disable(payload: PasswordRequest, request: Request,
            current_user: Dict[str, Any] = Depends(get_current_user)):
    _require_password(current_user, payload.password)
    two_factor.disable(current_user["id"])
    # Tắt yếu tố thứ hai là ĐÚNG việc mà một người chiếm được mật khẩu sẽ làm
    # đầu tiên. Nó cần mật khẩu, nên nó không phải lỗ hổng — nhưng khi chủ tài
    # khoản quay lại và hỏi "chuyện gì đã xảy ra", thứ trả lời được là một dòng
    # có mốc thời gian và địa chỉ, chứ không phải một cột `enabled = false`
    # vốn chỉ nói trạng thái HIỆN TẠI.
    #
    # Đi qua `log_security_event` chứ không gọi thẳng `audit.record`: nó ghi CẢ
    # HAI nhật ký (Redis cho bảng "vừa có chuyện gì", Postgres cho bảng bền) và
    # tự thêm tiền tố `security.`. Gọi thẳng `audit.record` thì sự kiện mang
    # tiền tố an ninh nhưng lại VẮNG MẶT ở bảng an ninh — một chỗ lệch mà người
    # đọc không có cách nào đoán ra.
    activity.log_security_event(
        "2fa.disabled", actor=current_user.get("username", ""),
        target=str(current_user["id"]), actor_user=current_user, request=request)
    return {"enabled": False}


@router.post("/recovery-codes")
def regenerate(payload: PasswordRequest, request: Request,
               current_user: Dict[str, Any] = Depends(get_current_user)):
    """Cấp bộ mã khôi phục mới. Bộ cũ chết ngay lập tức."""
    _require_password(current_user, payload.password)
    if not two_factor.is_enabled(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="2FA chưa bật.")
    codes = two_factor.regenerate_recovery_codes(current_user["id"])
    # Cấp lại mã khôi phục giết bộ cũ. Nếu chủ tài khoản không phải người bấm
    # thì lần sau họ dùng mã cũ sẽ bị từ chối mà không hiểu vì sao — dòng này
    # là thứ giải thích được. KHÔNG ghi mã vào `detail`.
    activity.log_security_event(
        "2fa.recovery_codes_regenerated", actor=current_user.get("username", ""),
        target=str(current_user["id"]), actor_user=current_user, request=request)
    return {"recovery_codes": codes}
