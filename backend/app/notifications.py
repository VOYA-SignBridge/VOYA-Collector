"""Thông báo trong ứng dụng: bản ghi bền của những việc hệ thống đã làm.

Thư điện tử đã có sẵn và vẫn giữ, nhưng nó rời khỏi hệ thống rồi không quay lại:
không ai biết người dùng đã đọc chưa, thư vào hộp rác thì mất hẳn, và một người
đổi địa chỉ thư là mất luôn lịch sử. Bảng `notifications` là bản ghi bền của
cùng những sự kiện đó, đọc được ngay trong ứng dụng.

**Loại nào cũng phải có LÝ DO người dùng quan tâm.** Đây không phải nhật ký hệ
thống chuyển hướng vào giao diện — nhật ký đã có `audit_log` và Loki. Mỗi mục ở
`KINDS` tương ứng một việc mà người dùng cần biết để HÀNH ĐỘNG hoặc để yên tâm.
Thêm loại mà không trả lời được "người ta làm gì với thông tin này" là cách biến
cái chuông thành thứ ai cũng tắt.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.storage.metadata_db import _fetch_all
from app.tenant_context import current_tenant

logger = logging.getLogger(__name__)

#: Loại thông báo, và việc người dùng làm với nó.
KINDS: Dict[str, str] = {
    "subscription": "Gói dịch vụ sắp hết hạn, đã gia hạn, hoặc bị khoá mềm",
    "consent": "Văn bản pháp lý mới cần ký lại, hoặc đồng thuận đã được ghi nhận",
    "security": "Đăng nhập lạ, phiên bị thu hồi, 2FA thay đổi",
    "training": "Phiên huấn luyện xong hoặc hỏng",
    "support": "Phản hồi mới trên phiếu hỗ trợ",
    "data": "Bản xuất dữ liệu đã sẵn sàng, hoặc quá trình nhập đã xong",
    "system": "Bảo trì, thay đổi ảnh hưởng tới cách dùng",
    # Kết quả kiểm duyệt, gửi cho NGƯỜI ĐÓNG GÓP. Thiếu loại này thì lời hứa
    # "qua kiểm duyệt mới công khai" vô hình với đúng người cần biết.
    #
    # Danh sách này là allowlist ĐÓNG, và nó đã làm đúng việc của mình: bản đầu
    # của `moderation_admin` gửi `kind="moderation"` khi loại ấy chưa có ở đây,
    # nên thông báo bị bỏ kèm một dòng ERROR thay vì lặng lẽ tạo ra một loại mà
    # giao diện không có nhãn để hiển thị.
    "moderation": "Dữ liệu của bạn đã được duyệt hoặc bị từ chối",
}

SEVERITIES = ("info", "success", "warning", "critical")

#: Trần số dòng trả về một lượt. Chuông không phải kho lưu trữ.
MAX_PAGE = 100


def notify(user_id: str, kind: str, title: str, body: str = "",
           link: Optional[str] = None, severity: str = "info",
           tenant_id: Optional[str] = None) -> Optional[str]:
    """Ghi một thông báo. Trả về id, hoặc None nếu không ghi được.

    **Không bao giờ ném.** Thông báo là việc phụ của thao tác đã thành công: một
    phiên huấn luyện chạy xong rồi thì không được phép báo lỗi chỉ vì cái chuông
    ghi hụt. Hỏng thì ghi ERROR và đi tiếp.
    """
    if kind not in KINDS:
        logger.error("[NOTIFY] loai khong hop le: %s", kind)
        return None
    if severity not in SEVERITIES:
        severity = "info"

    tenant = tenant_id or current_tenant()
    if not tenant:
        # Fail-closed giống `audit.record()`: một dòng không biết mình thuộc
        # tenant nào là một dòng RLS sẽ giấu khỏi chính người cần đọc nó.
        logger.error("[NOTIFY] khong co pham vi tenant, bo qua: %s/%s", kind, title)
        return None

    try:
        rows = _fetch_all(
            "INSERT INTO notifications "
            "(tenant_id, user_id, kind, title, body, link, severity) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING notification_id",
            (tenant, str(user_id), kind, title[:200], body, link, severity))
        return str(rows[0]["notification_id"]) if rows else None
    except Exception as exc:
        logger.error("[NOTIFY] khong ghi duoc thong bao %s cho %s: %s",
                     kind, user_id, exc)
        return None


def notify_many(user_ids: List[str], **kwargs) -> int:
    """Cùng một thông báo cho nhiều người. Trả về số dòng ghi được."""
    return sum(1 for uid in user_ids if notify(uid, **kwargs))


def list_for_user(user_id: str, limit: int = 30, unread_only: bool = False,
                  before: Optional[str] = None) -> List[Dict[str, Any]]:
    """Thông báo của một người, mới nhất trước.

    `before` là con trỏ phân trang theo `created_at` chứ không phải OFFSET: với
    OFFSET, một thông báo mới đến giữa hai lần tải sẽ đẩy cả danh sách xuống một
    dòng và người dùng thấy lặp lại đúng mục vừa đọc.
    """
    limit = max(1, min(int(limit), MAX_PAGE))
    sql = ("SELECT notification_id, kind, title, body, link, severity, "
           "read_at, created_at FROM notifications WHERE user_id = %s")
    params: list = [str(user_id)]
    if unread_only:
        sql += " AND read_at IS NULL"
    if before:
        sql += " AND created_at < %s"
        params.append(before)
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    return _fetch_all(sql, tuple(params))


def unread_count(user_id: str) -> int:
    rows = _fetch_all(
        "SELECT COUNT(*) AS n FROM notifications "
        "WHERE user_id = %s AND read_at IS NULL",
        (str(user_id),))
    return int(rows[0]["n"]) if rows else 0


def mark_read(user_id: str, notification_ids: List[str]) -> int:
    """Đánh dấu đã đọc. `user_id` trong WHERE là ranh giới quyền, không dư thừa.

    Thiếu nó thì bất kỳ ai đoán được một UUID sẽ đánh dấu đã đọc hộ người khác —
    vô hại nghe qua, nhưng nó có nghĩa là một thông báo bảo mật có thể bị người
    ngoài làm cho biến mất khỏi tầm mắt nạn nhân.
    """
    if not notification_ids:
        return 0
    # `::uuid[]` là bắt buộc: psycopg2 gửi danh sách Python thành `text[]`, và
    # Postgres không có toán tử `uuid = text`. Thiếu ép kiểu thì câu này ném
    # UndefinedFunction chứ không âm thầm sai — nhưng nó ném ở tận runtime.
    rows = _fetch_all(
        "UPDATE notifications SET read_at = NOW() "
        "WHERE user_id = %s AND notification_id = ANY(%s::uuid[]) "
        "AND read_at IS NULL RETURNING notification_id",
        (str(user_id), [str(n) for n in notification_ids]))
    return len(rows)


def mark_all_read(user_id: str) -> int:
    rows = _fetch_all(
        "UPDATE notifications SET read_at = NOW() "
        "WHERE user_id = %s AND read_at IS NULL RETURNING notification_id",
        (str(user_id),))
    return len(rows)


def purge_old(days: int = 90) -> int:
    """Xoá thông báo ĐÃ ĐỌC cũ hơn `days`.

    Chỉ đã đọc: một thông báo chưa đọc, dù cũ, vẫn là việc chưa ai xem. Xoá nó
    là quyết định thay người dùng rằng việc đó không còn quan trọng.
    """
    rows = _fetch_all(
        "DELETE FROM notifications "
        "WHERE read_at IS NOT NULL AND read_at < NOW() - make_interval(days => %s) "
        "RETURNING notification_id",
        (max(1, int(days)),))
    return len(rows)
