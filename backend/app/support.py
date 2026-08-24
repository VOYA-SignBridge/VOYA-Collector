"""Kênh hỗ trợ: phiếu và trao đổi.

Trước đây người dùng gặp sự cố chỉ có một đường — thư tay tới người quản trị.
Đường đó không để lại dấu vết nào trong hệ thống, nên không ai trả lời được
"phiếu này mở bao lâu rồi", và người dùng không tự xem lại được việc mình đã báo.

Hai quyết định đáng nêu:

1. **`author_label` chép cứng lúc ghi và KHÔNG đổi theo lượt đổi tên tài khoản.**
   Cùng nguyên tắc với `audit_log.actor_label`: một cuộc trao đổi hỗ trợ là bằng
   chứng lịch sử. Nếu nó chạy theo tên hiện tại, đọc lại một phiếu cũ sẽ thấy
   những cái tên chưa từng tồn tại vào lúc đó. Xem `app/account_rename.py`.

2. **`is_staff` lấy từ vai trò của người GỬI lúc gửi, không phải lúc đọc.** Một
   người từng là quản trị viên rồi thôi vai trò không làm câu trả lời cũ của họ
   thành câu của người dùng thường.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app import notifications, support_bot
from app.storage.metadata_db import _execute, _fetch_all
from app.tenant_context import current_tenant

logger = logging.getLogger(__name__)

CATEGORIES = ("account", "billing", "data", "bug", "other")
STATUSES = ("open", "pending", "resolved", "closed")
PRIORITIES = ("low", "normal", "high", "urgent")

#: Trạng thái mà người dùng vẫn gửi tiếp lời được.
_REOPENABLE = ("open", "pending", "resolved")


def _staff_recipients(tenant_id: str) -> List[str]:
    """Ai phải biết rằng có người vừa nhắn.

    Bản đầu của mô-đun này chỉ báo theo chiều **người trực → người dùng**. Chiều
    ngược lại không có gì cả: người dùng mở phiếu, và điều duy nhất xảy ra là
    một hàng mới trong bảng. Không thư, không chuông, không con số nào tăng lên
    ở đâu. Phiếu chỉ được đọc nếu tình cờ có quản trị viên mở đúng trang hàng
    đợi — mà trang đó khi ấy còn chưa tồn tại.

    Người nhận là quản trị viên **của chính tổ chức giữ phiếu**. Không gửi cho
    quản trị viên tổ chức khác: nội dung phiếu là dữ liệu của tenant.
    """
    rows = _fetch_all(
        "SELECT id FROM users "
        "WHERE is_admin = TRUE AND is_active = TRUE AND tenant_id = %s",
        (str(tenant_id),))
    if not rows:
        # KHÔNG được im lặng. Danh sách rỗng ở đây có hai nghĩa rất khác nhau —
        # "tổ chức này thật sự không có quản trị viên" và "truy vấn chạy ngoài
        # phạm vi nên RLS trả về 0 dòng" — và cả hai đều dẫn tới một phiếu không
        # ai nhìn thấy. Xem `docs/needFix` về fail-open ở mặt phẳng danh tính.
        logger.error(
            "[SUPPORT] khong tim thay quan tri vien nao cho tenant %s — "
            "phieu se khong den tay ai", tenant_id)
        return []
    return [str(r["id"]) for r in rows]


def _staff_emails(user_ids: List[str]) -> List[str]:
    """Địa chỉ thư của những người trực đó, bỏ ai chưa xác minh.

    Chưa xác minh thì không gửi: một địa chỉ chưa ai chứng minh là có thật vẫn
    có thể là địa chỉ của người khác, và thư này mang tiêu đề phiếu cùng tên
    người gửi — đủ để lộ ai đang dùng hệ thống và họ đang gặp chuyện gì.
    """
    if not user_ids:
        return []
    # `email_verified_at IS NOT NULL`, không phải một cột boolean `email_verified`
    # — cột đó không tồn tại, và một điều kiện sai tên ở đây không nổ mà chỉ
    # lặng lẽ khớp 0 dòng, tức là không ai nhận được thư nào.
    # `%s::uuid[]` chứ không phải `%s`: `users.id` là uuid còn danh sách truyền
    # vào là chuỗi, và Postgres từ chối `uuid = text` bằng một lỗi — không phải
    # bằng 0 dòng. Lỗi đó bị `try/except` ở chỗ gọi nuốt mất, nên hậu quả là
    # KHÔNG THƯ NÀO ĐƯỢC GỬI BAO GIỜ, lặng lẽ, đúng thứ tính năng này sinh ra
    # để chống. Bộ test bắt được nó ngay lượt chạy đầu.
    rows = _fetch_all(
        "SELECT email FROM users WHERE id = ANY(%s::uuid[]) "
        "AND email IS NOT NULL AND email <> '' AND email_verified_at IS NOT NULL",
        ([str(u) for u in user_ids],))
    return [str(r["email"]) for r in rows]


def _alert_staff(ticket_id: str, tenant_id: str, subject: str,
                 title: str, author_label: str, *,
                 category: str = "", email: bool = False) -> None:
    """Báo cho người trực. Không bao giờ ném — `notify` đã nuốt lỗi của nó.

    `email` mặc định TẮT vì hai lối gọi khác nhau về nhịp: mở phiếu là một lần,
    còn trả lời qua lại có thể là hàng chục lượt trong mười phút. Gửi thư mỗi
    lượt thì hộp thư người trực thành cái loa, và cái loa nào cũng bị tắt tiếng
    sau vài ngày. Nhịp trả lời được che bởi cảnh báo tồn đọng ở dưới.
    """
    staff = _staff_recipients(tenant_id)
    notifications.notify_many(
        staff, kind="support", title=title,
        body=f"{author_label}: {subject}", link=f"/admin/support/{ticket_id}",
        tenant_id=tenant_id)
    if not email:
        return

    # Thư đi qua HÀNG ĐỢI, không gửi thẳng ở đây. `smtplib` mở kết nối với
    # `timeout=10` và người nhận là MỌI quản trị viên của tổ chức, nên gửi tại
    # chỗ là bắt người dùng ngồi nhìn nút "Gửi" quay cả phút cho một việc phụ
    # mà họ không hề yêu cầu.
    #
    # Phái hỏng cũng KHÔNG được làm hỏng việc mở phiếu: phiếu đã nằm trong cơ
    # sở dữ liệu và chuông trong ứng dụng đã kêu ở trên. Ném lỗi ra bây giờ chỉ
    # khiến người dùng gửi lại và tạo phiếu thứ hai.
    try:
        from app.saas_tasks import send_support_ticket_emails

        send_support_ticket_emails.delay(
            ticket_id=str(ticket_id), tenant_id=str(tenant_id),
            subject=subject, category=category or "other",
            requester=author_label or "Người dùng")
    except Exception as exc:
        logger.error("[SUPPORT] khong phai duoc tac vu gui thu cho phieu %s: %s",
                     ticket_id, exc)


class SupportError(RuntimeError):
    """Sai sót nghiệp vụ, đủ an toàn để hiện cho người dùng."""


def create_ticket(user_id: str, subject: str, body: str,
                  category: str = "other", author_label: str = "") -> Dict[str, Any]:
    """Mở một phiếu kèm lời nhắn đầu tiên.

    Phiếu và lời nhắn đầu luôn đi cùng nhau: một phiếu không có nội dung là một
    phiếu không ai xử lý được, và cho phép tạo nó sẽ đẻ ra hàng rỗng trong hàng
    đợi của người trực.
    """
    subject = (subject or "").strip()
    body = (body or "").strip()
    if len(subject) < 5:
        raise SupportError("Tiêu đề quá ngắn (tối thiểu 5 ký tự).")
    if len(body) < 10:
        raise SupportError("Hãy mô tả rõ hơn (tối thiểu 10 ký tự).")
    if category not in CATEGORIES:
        category = "other"

    tenant = current_tenant()
    if not tenant:
        raise SupportError("Không xác định được tổ chức của phiên đăng nhập.")

    rows = _fetch_all(
        "INSERT INTO support_tickets (tenant_id, user_id, subject, category) "
        "VALUES (%s, %s, %s, %s) RETURNING ticket_id",
        (tenant, str(user_id), subject[:200], category))
    ticket_id = str(rows[0]["ticket_id"])
    _add_message(ticket_id, tenant, user_id, author_label, body, is_staff=False)
    logger.info("[SUPPORT] phieu moi %s tu %s (%s)", ticket_id, user_id, category)

    # Báo cho người trực TRƯỚC khi trợ lý nói. Thứ tự này là chủ ý: nếu trợ lý
    # ném lỗi vì bất kỳ lý do gì, người trực vẫn đã biết có phiếu mới. Đảo lại
    # là để một lỗi ở nhánh phụ nuốt mất việc chính.
    _alert_staff(ticket_id, tenant, subject, "Phiếu hỗ trợ mới", author_label,
                 category=category, email=True)

    _bot_say(ticket_id, tenant, support_bot.GREETING)
    answer, _suggestions, _topic = support_bot.answer_for(f"{subject}\n{body}")
    _bot_say(ticket_id, tenant, answer)
    return get_ticket(ticket_id, user_id)


def _add_message(ticket_id: str, tenant: str, author_id: Optional[str],
                 author_label: str, body: str, is_staff: bool,
                 author_kind: str = "") -> None:
    kind = author_kind or ("staff" if is_staff else "user")
    _execute(
        "INSERT INTO support_messages "
        "(tenant_id, ticket_id, author_id, author_label, is_staff, body, author_kind) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (tenant, ticket_id, str(author_id) if author_id else None,
         author_label or "không rõ", is_staff, body, kind))


def _bot_say(ticket_id: str, tenant: str, body: str) -> None:
    """Trợ lý nói một câu.

    KHÔNG đi qua `reply()`, và đó là điểm quan trọng nhất của cả tính năng:

    * `reply()` đổi trạng thái phiếu. Một câu của trợ lý đẩy phiếu sang
      `pending` sẽ làm nó rơi khỏi hàng đợi mặc định của người trực — phiếu
      biến mất khỏi màn hình của người duy nhất có thể xử lý nó.
    * `reply()` gửi thông báo. Trợ lý báo cho chính người vừa nhắn là tiếng ồn;
      báo cho người trực lần nữa là tiếng ồn nhân đôi (họ đã được báo lúc phiếu
      mở).

    `author_id` để NULL: không có tài khoản nào đứng sau câu này, và mượn tài
    khoản người dùng làm tác giả là ghi sai vào một bản ghi trao đổi.
    """
    _add_message(ticket_id, tenant, None, support_bot.BOT_LABEL, body,
                 is_staff=False, author_kind="bot")
    # Chỉ nhích `updated_at` để phiếu nổi lên đúng thứ tự thời gian trong hàng
    # đợi. Trạng thái giữ nguyên — xem chú thích trên.
    _execute("UPDATE support_tickets SET updated_at = NOW() WHERE ticket_id = %s",
             (ticket_id,))


def reply(ticket_id: str, user_id: str, body: str, author_label: str = "",
          is_staff: bool = False) -> Dict[str, Any]:
    """Gửi thêm lời nhắn. Người trực trả lời cũng đi qua đây."""
    body = (body or "").strip()
    if len(body) < 2:
        raise SupportError("Nội dung trống.")

    ticket = _ticket_row(ticket_id)
    if not ticket:
        raise SupportError("Không tìm thấy phiếu.")
    if not is_staff and str(ticket["user_id"]) != str(user_id):
        raise SupportError("Không tìm thấy phiếu.")
    if ticket["status"] not in _REOPENABLE:
        raise SupportError("Phiếu đã đóng. Hãy mở phiếu mới.")

    _add_message(ticket_id, ticket["tenant_id"], user_id, author_label, body, is_staff)

    # Người dùng trả lời một phiếu đã giải quyết = mở lại; người trực trả lời =
    # chờ người dùng. Trạng thái đi theo AI vừa nói, chứ không phải một nút bấm
    # riêng mà ai cũng quên bấm.
    new_status = "pending" if is_staff else "open"
    _execute(
        "UPDATE support_tickets SET status = %s, updated_at = NOW(), "
        "resolved_at = NULL WHERE ticket_id = %s",
        (new_status, ticket_id))

    # Thông báo đi theo CHIỀU NGƯỢC với người vừa gửi. Cả hai chiều đều phải có:
    # thiếu chiều nào thì bên kia chỉ biết có tin nhắn nếu tự đi mở đúng trang.
    if is_staff:
        if ticket["user_id"]:
            notifications.notify(
                str(ticket["user_id"]), kind="support",
                title="Phản hồi mới trên phiếu hỗ trợ",
                # Đường CHUẨN, không phải `/support/<id>`. Đường cũ vẫn sống
                # (App.tsx chuyển hướng và giữ ID) vì các dòng thông báo đã gửi
                # mang nó, nhưng dòng MỚI thì trỏ thẳng — một cú nhấp không nên
                # phải đi qua một lượt chuyển hướng để tới nơi.
                body=ticket["subject"], link=f"/settings/support/{ticket_id}",
                tenant_id=ticket["tenant_id"])
    else:
        _alert_staff(ticket_id, str(ticket["tenant_id"]), ticket["subject"],
                     "Người dùng vừa trả lời phiếu hỗ trợ", author_label)
        # Trợ lý chỉ nói khi CHƯA có người trực nào vào phiếu. Sau khi một người
        # thật đã trả lời, chen thêm câu máy vào giữa cuộc trao đổi là phá cuộc
        # trao đổi đó — và tệ hơn, nó có thể mâu thuẫn với điều người trực vừa
        # nói mà người dùng không biết tin ai.
        if not _has_staff_reply(ticket_id):
            answer, _s, _t = support_bot.answer_for(body)
            _bot_say(ticket_id, str(ticket["tenant_id"]), answer)
    return get_ticket(ticket_id, user_id, as_staff=is_staff)


def _has_staff_reply(ticket_id: str) -> bool:
    rows = _fetch_all(
        "SELECT 1 FROM support_messages "
        "WHERE ticket_id = %s AND author_kind = 'staff' LIMIT 1",
        (str(ticket_id),))
    return bool(rows)


def set_status(ticket_id: str, status: str, user_id: str,
               is_staff: bool = False) -> Dict[str, Any]:
    """Đổi trạng thái. Người dùng chỉ được đóng phiếu của chính mình."""
    if status not in STATUSES:
        raise SupportError("Trạng thái không hợp lệ.")
    ticket = _ticket_row(ticket_id)
    if not ticket:
        raise SupportError("Không tìm thấy phiếu.")
    if not is_staff:
        if str(ticket["user_id"]) != str(user_id):
            raise SupportError("Không tìm thấy phiếu.")
        if status != "closed":
            raise SupportError("Bạn chỉ có thể đóng phiếu của mình.")

    _execute(
        "UPDATE support_tickets SET status = %s, updated_at = NOW(), "
        "resolved_at = CASE WHEN %s IN ('resolved', 'closed') THEN NOW() ELSE NULL END "
        "WHERE ticket_id = %s",
        (status, status, ticket_id))
    return get_ticket(ticket_id, user_id, as_staff=is_staff)


def _ticket_row(ticket_id: str) -> Optional[Dict[str, Any]]:
    rows = _fetch_all(
        "SELECT ticket_id, tenant_id, user_id, subject, category, status, "
        "priority, created_at, updated_at, resolved_at "
        "FROM support_tickets WHERE ticket_id = %s", (str(ticket_id),))
    return rows[0] if rows else None


def get_ticket(ticket_id: str, user_id: str,
               as_staff: bool = False) -> Dict[str, Any]:
    """Một phiếu kèm toàn bộ trao đổi.

    Không tìm thấy và không có quyền trả về CÙNG một lỗi: phân biệt hai cái cho
    phép dò xem một mã phiếu có tồn tại hay không.
    """
    ticket = _ticket_row(ticket_id)
    if not ticket or (not as_staff and str(ticket["user_id"]) != str(user_id)):
        raise SupportError("Không tìm thấy phiếu.")
    ticket["messages"] = _fetch_all(
        "SELECT message_id, author_label, is_staff, author_kind, body, created_at "
        "FROM support_messages WHERE ticket_id = %s ORDER BY created_at",
        (str(ticket_id),))
    ticket["bot_suggestions"] = _suggestions_for(ticket["messages"])
    return ticket


def _suggestions_for(messages: List[Dict[str, Any]]) -> List[str]:
    """Chip gợi ý hiện dưới ô nhập, suy từ lời CUỐI của người dùng.

    Suy lại mỗi lần đọc thay vì lưu vào cơ sở dữ liệu. Chip là chữ giao diện,
    không phải nội dung trao đổi — lưu chúng nghĩa là một lần đổi câu chữ sẽ để
    lại những chip cũ nằm mãi trong phiếu cũ, và chúng có thể trỏ tới màn hình
    không còn tồn tại.

    Không gợi ý gì nữa một khi người trực đã vào: từ lúc đó cuộc trao đổi là
    giữa hai người, và chip của máy chỉ chen ngang.
    """
    if any(m.get("author_kind") == "staff" for m in messages):
        return []
    last_user = next(
        (m for m in reversed(messages) if m.get("author_kind") == "user"), None)
    if last_user is None:
        return list(support_bot.STARTERS)
    _answer, suggestions, _topic = support_bot.answer_for(last_user["body"])
    return list(suggestions)


def list_tickets(user_id: Optional[str] = None, status: Optional[str] = None,
                 limit: int = 50) -> List[Dict[str, Any]]:
    """Phiếu của một người, hoặc — khi `user_id` là None — hàng đợi của người trực."""
    # `requester` lấy từ lời nhắn ĐẦU TIÊN của phiếu, không JOIN sang `users`.
    # Hai lý do: nhãn đó là bằng chứng lịch sử (xem chú thích đầu tệp — nó không
    # đổi theo lượt đổi tên tài khoản), và một phiếu vẫn phải đọc được sau khi
    # tài khoản người gửi đã bị xoá. JOIN sang `users` làm mất cả hai.
    #
    # `author_kind = 'user'` là bộ lọc BẮT BUỘC từ v3.16: trợ lý tự động cũng
    # ghi lời nhắn, và không lọc thì mọi phiếu trong hàng đợi đều mang tên người
    # gửi là "Trợ lý tự động". Cùng lý do cho `message_count` và `last_body` —
    # người trực cần biết NGƯỜI DÙNG nói gì lần cuối, không phải máy.
    sql = ("SELECT t.ticket_id, t.subject, t.category, t.status, t.priority, "
           "t.created_at, t.updated_at, "
           "(SELECT COUNT(*) FROM support_messages m "
           " WHERE m.ticket_id = t.ticket_id AND m.author_kind <> 'bot') "
           "AS message_count, "
           "(SELECT m.author_label FROM support_messages m "
           " WHERE m.ticket_id = t.ticket_id AND m.author_kind = 'user' "
           " ORDER BY m.created_at LIMIT 1) "
           "AS requester, "
           # Đoạn xem trước trong hàng đợi. Cắt ở SQL chứ không ở giao diện:
           # một phiếu dài 10.000 ký tự nhân với 200 dòng hàng đợi là hai
           # megabyte chuyển đi để hiển thị một dòng.
           "(SELECT LEFT(m.body, 160) FROM support_messages m "
           " WHERE m.ticket_id = t.ticket_id AND m.author_kind <> 'bot' "
           " ORDER BY m.created_at DESC LIMIT 1) "
           "AS last_snippet, "
           "(SELECT m.author_kind FROM support_messages m "
           " WHERE m.ticket_id = t.ticket_id AND m.author_kind <> 'bot' "
           " ORDER BY m.created_at DESC LIMIT 1) "
           "AS last_kind "
           "FROM support_tickets t WHERE 1 = 1")
    params: list = []
    if user_id:
        sql += " AND t.user_id = %s"
        params.append(str(user_id))
    if status in STATUSES:
        sql += " AND t.status = %s"
        params.append(status)
    sql += " ORDER BY t.updated_at DESC LIMIT %s"
    params.append(max(1, min(int(limit), 200)))
    return _fetch_all(sql, tuple(params))
