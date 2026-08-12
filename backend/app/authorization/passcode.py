"""Mã hành động cá nhân — xác thực nâng cấp SAU khi phân quyền đã cho qua.

Nó KHÔNG phải cái gì
--------------------
Không phải một quyền. §16 nói bằng một câu: mã hành động không bao giờ biến
DENY thành ALLOW. Nó trả lời một câu hỏi khác hẳn — "đúng là người này đang
ngồi trước máy chứ không phải một phiên bị cướp" — và câu hỏi đó chỉ đáng hỏi
sau khi đã biết người ấy vốn được phép.

Trình tự bắt buộc, và mã ở đây không tự cưỡng chế được nó:

    authorize()  →  ALLOW  →  requires_passcode?  →  verify()  →  thực hiện
                 ↘  DENY   →  dừng, KHÔNG hỏi mã

Gọi `verify()` trước `authorize()` sẽ tạo ra một hệ thống mà nhập đúng mã thì
làm được mọi thứ. `require_step_up()` ở cuối tệp là hàm gộp đúng thứ tự, và
router nên gọi nó thay vì tự ghép.

Vì sao khác `sudo_mode.py`
---------------------------
`sudo_mode` là một CỬA SỔ thời gian: xác nhận một lần, rồi mọi thao tác nhạy
cảm trong N phút được miễn. Cái đó hợp cho một phiên quản trị.

Mã hành động gắn với MỘT hành động. Không có cửa sổ, không có `last_verified_at`
— cột đó cố ý vắng mặt trong `user_action_passcodes`, và chú thích ở DDL nói
rõ vì sao: có nó thì sẽ có người thêm "vừa xác nhận 5 phút trước thì bỏ qua",
và lúc đó nó thành một `sudo_mode` thứ hai với ngữ nghĩa mờ hơn.

Cả hai cùng tồn tại là có chủ ý. `sudo_mode` bảo vệ một phiên quản trị; cái này
bảo vệ một hành động không hoàn tác được.

Khoá sau khi thử sai
--------------------
Đếm sai tích luỹ, khoá tăng dần, và `failed_count` chỉ về 0 khi nhập ĐÚNG. Không
tự về 0 theo thời gian: một mã sáu ký tự với đồng hồ tự tha thứ là một mã bị dò
được, chỉ chậm hơn.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

#: Số lần sai trước khi khoá, và khoá bao lâu. Bậc thang chứ không một ngưỡng:
#: người thật gõ nhầm một hai lần, còn kẻ dò thì gặp tường tăng theo cấp số.
LOCK_THRESHOLDS: tuple[tuple[int, timedelta], ...] = (
    (5, timedelta(minutes=5)),
    (8, timedelta(minutes=30)),
    (12, timedelta(hours=24)),
)

#: Độ dài tối thiểu. Ngắn hơn thì không gian tìm kiếm nhỏ tới mức bậc thang
#: khoá ở trên cũng không cứu được.
MIN_LENGTH = 6


class PasscodeError(PermissionError):
    """Không qua được bước xác thực nâng cấp."""


class PasscodeNotSet(PasscodeError):
    """Quyền này đòi mã hành động nhưng tài khoản chưa đặt.

    Tách riêng khỏi `PasscodeError` vì giao diện phải phản ứng khác: một mã sai
    nghĩa là "thử lại", còn chưa đặt nghĩa là "vào phần cài đặt và đặt đi". Gộp
    hai cái làm người dùng kẹt trong một ô nhập không bao giờ đúng.
    """


class PasscodeLocked(PasscodeError):
    def __init__(self, until: datetime) -> None:
        super().__init__(f"ma hanh dong dang bi khoa toi {until.isoformat()}")
        self.locked_until = until


def _hasher():
    """Cùng bộ băm mật khẩu mà `auth.py` dùng.

    Nhập ở đây chứ không tự chọn thuật toán: hai bộ băm khác nhau cho hai loại
    bí mật nghĩa là hai lịch nâng cấp tham số, và cái ít được để ý sẽ tụt lại.
    """
    from app.auth import pwd_context

    return pwd_context


def _row(user_id: str) -> Optional[dict]:
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    # Mặt phẳng danh tính: bảng này không chịu RLS (xem chú thích ở
    # `TENANT_SCOPED_AUTHZ_TABLES`), nhưng đọc trong system scope để cùng một
    # hình dạng với `auth.py` — người gọi có thể đang ở tenant khác tenant nhà.
    with system_scope("authz: doc ma hanh dong cua chinh nguoi goi"):
        rows = _fetch_all(
            "SELECT user_id::text AS user_id, passcode_hash, status, failed_count, "
            "       locked_until, revoked_at "
            "  FROM user_action_passcodes WHERE user_id = %s",
            (str(user_id),),
        )
    return rows[0] if rows else None


def is_set(user_id: str) -> bool:
    row = _row(user_id)
    return bool(row and row["status"] == "ACTIVE" and row["revoked_at"] is None)


def set_passcode(user_id: str, passcode: str) -> None:
    """Đặt hoặc đổi mã hành động. Đặt lại sẽ xoá cả bộ đếm sai và khoá."""
    if len(passcode or "") < MIN_LENGTH:
        raise ValueError(f"ma hanh dong phai dai it nhat {MIN_LENGTH} ky tu")

    digest = _hasher().hash(passcode)
    from app.storage.metadata_db import _cursor
    from app.tenant_context import system_scope

    with system_scope("authz: dat ma hanh dong"), _cursor() as cur:
        cur.execute(
            "INSERT INTO user_action_passcodes "
            "  (user_id, passcode_hash, status, failed_count, updated_at) "
            "VALUES (%s, %s, 'ACTIVE', 0, NOW()) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "  passcode_hash = EXCLUDED.passcode_hash, status = 'ACTIVE', "
            "  failed_count = 0, locked_until = NULL, revoked_at = NULL, "
            "  updated_at = NOW()",
            (str(user_id), digest),
        )

    from app import audit

    audit.record("authz.passcode.set", actor={"id": user_id}, target_type="user",
                 target_id=str(user_id))


def revoke(user_id: str) -> None:
    """Gỡ mã hành động. Mọi quyền đòi mã sẽ không dùng được cho tới khi đặt lại."""
    from app.storage.metadata_db import _cursor
    from app.tenant_context import system_scope

    with system_scope("authz: go ma hanh dong"), _cursor() as cur:
        cur.execute(
            "UPDATE user_action_passcodes "
            "   SET status = 'REVOKED', revoked_at = NOW(), updated_at = NOW() "
            " WHERE user_id = %s AND revoked_at IS NULL",
            (str(user_id),),
        )


def _lock_for(failed_count: int) -> Optional[timedelta]:
    """Khoá bao lâu sau lần sai thứ `failed_count`. None = chưa khoá."""
    duration = None
    for threshold, window in LOCK_THRESHOLDS:
        if failed_count >= threshold:
            duration = window
    return duration


def verify(user_id: str, passcode: str) -> None:
    """Xác nhận mã. Trả về None nếu đúng, ném `PasscodeError` nếu không.

    Ném chứ không trả bool, và đó không phải sở thích: một hàm trả bool ở đường
    này sẽ có ngày được gọi mà không kiểm kết quả, và một `verify(...)` cụt
    trông y hệt như đã kiểm. Với ngoại lệ thì bỏ quên là không thể.
    """
    row = _row(user_id)
    if not row or row["revoked_at"] is not None or row["status"] == "REVOKED":
        raise PasscodeNotSet("tai khoan chua dat ma hanh dong")

    locked_until = row["locked_until"]
    if locked_until and locked_until > datetime.now(timezone.utc):
        raise PasscodeLocked(locked_until)

    if _hasher().verify(passcode or "", row["passcode_hash"]):
        _reset_failures(user_id, row["failed_count"])
        return

    _count_failure(user_id, int(row["failed_count"]) + 1)
    raise PasscodeError("ma hanh dong khong dung")


def _reset_failures(user_id: str, current: int) -> None:
    # Chỉ ghi khi có gì để ghi. Đường thành công là đường nóng, và một UPDATE
    # không đổi gì vẫn là một lượt đi về cơ sở dữ liệu và một dòng WAL.
    if not current:
        return
    from app.storage.metadata_db import _cursor
    from app.tenant_context import system_scope

    with system_scope("authz: reset dem sai ma hanh dong"), _cursor() as cur:
        cur.execute(
            "UPDATE user_action_passcodes "
            "   SET failed_count = 0, locked_until = NULL, status = 'ACTIVE', "
            "       updated_at = NOW() "
            " WHERE user_id = %s",
            (str(user_id),),
        )


def _count_failure(user_id: str, failed_count: int) -> None:
    lock = _lock_for(failed_count)
    from app.storage.metadata_db import _cursor
    from app.tenant_context import system_scope

    with system_scope("authz: ghi nhan sai ma hanh dong"), _cursor() as cur:
        cur.execute(
            "UPDATE user_action_passcodes "
            "   SET failed_count = %s, "
            "       locked_until = CASE WHEN %s::interval IS NULL THEN locked_until "
            "                           ELSE NOW() + %s::interval END, "
            "       status = CASE WHEN %s::interval IS NULL THEN status ELSE 'LOCKED' END, "
            "       updated_at = NOW() "
            " WHERE user_id = %s",
            (failed_count, lock, lock, lock, str(user_id)),
        )

    from app import audit

    audit.record(
        "authz.passcode.failed",
        actor={"id": user_id},
        target_type="user",
        target_id=str(user_id),
        detail={"failed_count": failed_count, "locked": lock is not None},
    )


def require_step_up(actor, permission: str, target=None, *, passcode: Optional[str] = None):
    """Phân quyền RỒI mới xác thực nâng cấp — đúng thứ tự, trong một lời gọi.

    Đây là hàm mà router nên gọi cho bất kỳ hành động nào có thể đòi mã. Ghép
    tay hai bước là chỗ thứ tự bị đảo, và thứ tự đảo thì không có gì phát hiện
    ra: hệ thống vẫn chạy, chỉ là mã hành động bỗng trở thành một cách vượt
    phân quyền.

    Trả về `Decision`. Ném `AuthorizationError` (403) hoặc `PasscodeError`
    (thường ánh xạ thành 401/409 tuỳ giao diện).
    """
    from app.authorization.authorization_service import require

    decision = require(actor, permission, target)  # DENY thì ném ở đây, trước mã.

    if decision.requires_passcode:
        user_id = actor.get("id") or actor.get("user_id")
        verify(str(user_id), passcode or "")

    return decision
