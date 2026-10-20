"""Việc đang chờ quản trị viên, đếm theo từng mục của console.

Vì sao là "việc đang chờ" chứ không phải "có bao nhiêu thứ"
-----------------------------------------------------------
Một huy hiệu trên thanh bên là một lời hứa: **ở đây có việc cần bạn**. Nếu nó
đếm tồn kho — bao nhiêu người dùng, bao nhiêu nhãn, bao nhiêu tổ chức — thì nó
luôn khác 0 và luôn sáng, và trong đúng một tuần người ta thôi nhìn nó. Lúc đó
huy hiệu tệ hơn là không có, vì cái mục thật sự cần xử lý cũng chỉ sáng y hệt.

Nên mọi con số dưới đây đều thoả một điều kiện: **về 0 khi ai đó làm xong
việc**. Mục nào không có việc-cần-làm nào định nghĩa được thì không có huy hiệu,
và như thế là đúng.

Mỗi truy vấn phải rẻ
---------------------
Bảng này được hỏi lại theo chu kỳ ở mọi tab console đang mở. Không đếm bảng chỉ
tăng (`samples`, `audit_log`), không quét toàn văn. Cái nào không đếm rẻ được
thì bỏ hẳn khỏi bảng chứ không đếm chậm.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.storage.metadata_db import _fetch_all

logger = logging.getLogger(__name__)


def _scalar(sql: str, params: tuple = ()) -> int:
    """Một con số, và **0 khi truy vấn hỏng**.

    Nuốt lỗi ở đây là chủ ý và có giới hạn: một bảng chưa migrate hoặc một cột
    đổi tên KHÔNG được phép làm cả console trắng màn hình vì cái huy hiệu. Lỗi
    vẫn vào nhật ký ở mức `exception`, nên nó không biến mất — nó chỉ không
    được phép chắn đường.
    """
    try:
        rows = _fetch_all(sql, params)
        return int(rows[0]["n"]) if rows else 0
    except Exception:
        logger.exception("[ATTENTION] khong dem duoc: %s", sql.split("FROM")[-1].strip()[:60])
        return 0


def collect(tenant_id: str) -> Dict[str, Any]:
    """Đếm việc đang chờ, theo từng mục console.

    Khoá trả về khớp với `href` của mục trong `AdminShell` — không phải một tên
    riêng thứ hai. Hai bảng tên song song là chỗ chắc chắn sẽ lệch nhau khi
    thêm mục mới, và lệch theo kiểu im lặng: huy hiệu chỉ đơn giản không hiện.
    """
    tenant = str(tenant_id)

    # Hỗ trợ: phiếu mà lời nhắn cuối của CON NGƯỜI là của người dùng.
    # Lời của trợ lý không tính — nó luôn trả lời ngay, nên tính vào thì con số
    # này vĩnh viễn bằng 0. Cùng định nghĩa với `app/support_backlog.py`; sửa
    # một chỗ mà quên chỗ kia là để hai màn hình nói hai con số khác nhau.
    support_waiting = _scalar(
        "SELECT COUNT(*) AS n FROM ("
        "  SELECT DISTINCT ON (m.ticket_id) m.ticket_id, m.author_kind"
        "    FROM support_messages m"
        "    JOIN support_tickets t ON t.ticket_id = m.ticket_id"
        "   WHERE m.author_kind <> 'bot' AND t.status IN ('open', 'pending')"
        "     AND t.tenant_id = %s"
        "   ORDER BY m.ticket_id, m.created_at DESC"
        ") x WHERE x.author_kind = 'user'",
        (tenant,))

    # Từ vựng: đề xuất phương ngữ đang chờ duyệt.
    vocabulary_pending = _scalar(
        "SELECT COUNT(*) AS n FROM dialects "
        "WHERE tenant_id = %s AND status = 'pending'",
        (tenant,))

    # Văn bản pháp lý: bản nháp chưa công bố. Đây là việc CHƯA XONG, không phải
    # kho lưu trữ — bản đã công bố không đếm.
    # `status IN ('draft','in_review','approved')` — KHÔNG phải một cột
    # `published_at` (cột đó không tồn tại). `discarded` cũng không tính: bản
    # nháp đã bỏ là việc đã xong, không phải việc đang chờ.
    legal_drafts = _scalar(
        "SELECT COUNT(*) AS n FROM legal_document_drafts "
        "WHERE status IN ('draft', 'in_review', 'approved')")

    # Tổ chức: lời mời đã gửi mà chưa ai nhận và chưa hết hạn.
    invitations_pending = _scalar(
        "SELECT COUNT(*) AS n FROM tenant_invitations "
        "WHERE tenant_id = %s AND accepted_at IS NULL AND revoked_at IS NULL "
        "AND expires_at > NOW()",
        (tenant,))

    # Giám sát tài nguyên: số cảnh báo đang mở. Lấy thẳng từ `collect_resources`
    # để bảng thanh bên và trang giám sát không bao giờ nói hai con số khác nhau.
    try:
        from app.monitoring import collect_resources
        alerts = len(collect_resources().get("alerts") or [])
    except Exception:
        logger.exception("[ATTENTION] khong doc duoc canh bao tai nguyen")
        alerts = 0

    return {
        "/admin/support": support_waiting,
        "/admin/vocabulary": vocabulary_pending,
        "/admin/legal": legal_drafts,
        "/admin/tenants": invitations_pending,
        "/admin/resources": alerts,
    }
