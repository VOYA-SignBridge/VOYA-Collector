"""Tồn đọng kênh hỗ trợ: đo, và báo khi vượt ngưỡng.

Vì sao cần cái này khi đã có thư báo phiếu mới
----------------------------------------------
Thư phiếu-mới báo một SỰ KIỆN: có người vừa hỏi. Nó không nói được điều quan
trọng hơn — rằng câu hỏi ấy vẫn chưa ai trả lời sau năm tiếng. Một hộp thư đầy
những thư "có phiếu mới" trông y hệt nhau dù mọi phiếu đã xong hay chưa phiếu
nào được đụng tới.

Nên mô-đun này đo TRẠNG THÁI và luôn kèm con số hiện tại: bao nhiêu phiếu đang
chờ, cái cũ nhất chờ bao lâu, bao nhiêu lời nhắn chưa được trả. Một cảnh báo
không có số lượng thì người đọc vẫn phải mở hệ thống ra mới quyết định được có
nên bỏ dở việc đang làm hay không, và như thế cảnh báo chưa làm xong việc của nó.

"Đang chờ" nghĩa là gì
-----------------------
Một phiếu đang chờ khi lời nhắn **cuối cùng của con người** trong đó là của
người dùng. Ba chi tiết, cả ba đều đã từng là chỗ đếm sai:

* Lời nhắn của trợ lý (`author_kind = 'bot'`) KHÔNG tính. Trợ lý luôn trả lời
  ngay, nên nếu tính nó thì không phiếu nào "đang chờ" bao giờ — cảnh báo sẽ
  im lặng vĩnh viễn và trông y như đang hoạt động tốt.
* Đếm theo lời nhắn cuối chứ không theo `status`. Trạng thái là thứ người ta
  bấm tay và quên bấm; lời nhắn thì không nói dối được.
* Phiếu đã `resolved`/`closed` không tính, kể cả khi người dùng nói lời cuối —
  đóng phiếu rồi thì lời cảm ơn không phải là một câu hỏi đang chờ.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.storage.metadata_db import _fetch_all

logger = logging.getLogger(__name__)

#: Ngưỡng do người vận hành đặt ra: phiếu chờ quá 5 giờ, hoặc quá 10 lời nhắn
#: chưa được trả lời. Hai ngưỡng bắt hai kiểu hỏng khác nhau — một phiếu duy
#: nhất bị bỏ quên cả buổi, và một đợt nhiều người cùng hỏi mà không ai kịp trả.
THRESHOLD_HOURS = 5
THRESHOLD_MESSAGES = 10

#: Gửi lại sớm nhất sau bấy nhiêu giây. Tồn đọng là trạng thái KÉO DÀI, nên nếu
#: không có khoảng lặng thì mỗi lượt kiểm tra lại đẻ một thư giống hệt thư
#: trước, và tới thư thứ tư thì người ta lập bộ lọc xoá thẳng cả loại thư đó.
RESEND_COOLDOWN_S = 4 * 3600


#: Lời nhắn CUỐI CÙNG của con người trong mỗi phiếu chưa đóng. `author_kind`
#: loại trợ lý ra — xem phần đầu tệp về lý do.
_WAITING_SQL = """
WITH last_human AS (
    SELECT DISTINCT ON (m.ticket_id)
           m.ticket_id, m.author_kind, m.created_at
      FROM support_messages m
      JOIN support_tickets t ON t.ticket_id = m.ticket_id
     WHERE m.author_kind <> 'bot'
       AND t.status IN ('open', 'pending')
     ORDER BY m.ticket_id, m.created_at DESC
)
SELECT t.tenant_id,
       COUNT(*)                                                   AS waiting,
       COALESCE(MAX(EXTRACT(EPOCH FROM (NOW() - l.created_at))), 0) AS oldest_s
  FROM last_human l
  JOIN support_tickets t ON t.ticket_id = l.ticket_id
 WHERE l.author_kind = 'user'
 GROUP BY t.tenant_id
"""

#: Số lời nhắn người dùng gửi SAU câu trả lời gần nhất của người trực (hoặc tất
#: cả, nếu chưa ai trả lời lần nào). Đây là "bao nhiêu câu đang treo", khác với
#: "bao nhiêu phiếu đang treo": một người có thể nhắn năm câu trong một phiếu.
_UNANSWERED_SQL = """
SELECT t.tenant_id, COUNT(*) AS n
  FROM support_messages m
  JOIN support_tickets t ON t.ticket_id = m.ticket_id
 WHERE m.author_kind = 'user'
   AND t.status IN ('open', 'pending')
   AND m.created_at > COALESCE(
         (SELECT MAX(s.created_at) FROM support_messages s
           WHERE s.ticket_id = m.ticket_id AND s.author_kind = 'staff'),
         '-infinity'::timestamptz)
 GROUP BY t.tenant_id
"""


def measure() -> List[Dict[str, Any]]:
    """Số liệu tồn đọng, mỗi tổ chức một dòng. Không gửi gì, không đổi gì.

    Tách khỏi phần gửi thư để test kiểm được phép đếm mà không cần SMTP, và để
    trang quản trị dùng lại đúng con số mà thư đã dùng — hai chỗ hiển thị hai
    con số khác nhau là cách nhanh nhất để mất lòng tin vào cả hai.
    """
    waiting = {str(r["tenant_id"]): r for r in _fetch_all(_WAITING_SQL, ())}
    unanswered = {str(r["tenant_id"]): int(r["n"]) for r in _fetch_all(_UNANSWERED_SQL, ())}

    out: List[Dict[str, Any]] = []
    for tenant_id in set(waiting) | set(unanswered):
        row = waiting.get(tenant_id)
        oldest_h = float(row["oldest_s"]) / 3600.0 if row else 0.0
        out.append({
            "tenant_id": tenant_id,
            "waiting": int(row["waiting"]) if row else 0,
            "oldest_hours": round(oldest_h, 2),
            "unanswered_messages": unanswered.get(tenant_id, 0),
        })
    return out


def breaches(stat: Dict[str, Any]) -> bool:
    """Dòng số liệu này có vượt ngưỡng nào không?"""
    return (stat["oldest_hours"] >= THRESHOLD_HOURS
            or stat["unanswered_messages"] >= THRESHOLD_MESSAGES)


def _cooldown_key(tenant_id: str) -> str:
    return f"support:backlog_alerted:{tenant_id}"


def sweep() -> Dict[str, Any]:
    """Đo tồn đọng, gửi thư cho quản trị viên của tổ chức nào vượt ngưỡng.

    Trả về số liệu để tác vụ nền ghi được vào nhật ký một câu có nghĩa, thay vì
    "đã chạy xong" — thứ không phân biệt được "không có tồn đọng" với "phép đếm
    hỏng và trả về rỗng".
    """
    from app import support
    from app.config import settings
    from app.monitoring import _redis_client

    stats = measure()
    client = _redis_client()
    base = (settings.frontend_base_url or "").rstrip("/")
    sent = 0
    over = 0

    for stat in stats:
        if not breaches(stat):
            continue
        over += 1
        tenant_id = stat["tenant_id"]

        # Khoảng lặng nằm ở Redis, không ở cơ sở dữ liệu: nó là trạng thái vận
        # hành, mất đi thì hậu quả tệ nhất là gửi sớm một thư. Không đáng thêm
        # một bảng và một lượt migrate.
        #
        # KHÔNG có Redis thì VẪN GỬI. Chọn hướng này có cân nhắc: hỏng theo
        # kiểu "thừa một thư" thì người ta thấy ngay và kêu; hỏng theo kiểu
        # "im lặng" thì đúng là thứ mà cảnh báo này sinh ra để chống lại.
        if client is not None:
            try:
                if not client.set(_cooldown_key(tenant_id), "1",
                                  nx=True, ex=RESEND_COOLDOWN_S):
                    continue
            except Exception as exc:
                logger.warning("[SUPPORT] khong doc duoc khoang lang Redis: %s", exc)

        recipients = support._staff_emails(support._staff_recipients(tenant_id))
        if not recipients:
            # Vượt ngưỡng mà không có ai để báo là một sự cố riêng, và nó im
            # lặng gấp đôi: phiếu không ai trả lời, thư cũng không ai nhận.
            logger.error(
                "[SUPPORT] tenant %s ton dong (%s phieu, %.1f gio) nhung khong "
                "co dia chi thu nao da xac minh de bao", tenant_id,
                stat["waiting"], stat["oldest_hours"])
            continue

        from app import email_service
        for addr in recipients:
            try:
                email_service.send_support_backlog_email(
                    addr, waiting=stat["waiting"],
                    oldest_hours=stat["oldest_hours"],
                    unanswered_messages=stat["unanswered_messages"],
                    threshold_hours=THRESHOLD_HOURS,
                    threshold_messages=THRESHOLD_MESSAGES,
                    link=f"{base}/admin/support")
                sent += 1
            except Exception as exc:
                logger.error("[SUPPORT] khong gui duoc thu ton dong toi %s: %s", addr, exc)

    logger.info("[SUPPORT] quet ton dong: %d to chuc co phieu cho, %d vuot nguong, %d thu",
                len(stats), over, sent)
    return {"tenants": len(stats), "vuot_nguong": over, "thu_da_gui": sent}
