"""Làm sao mọi tiến trình biết policy đã đổi.

Bài toán
--------
Mỗi tiến trình API giữ một bản sao policy trong bộ nhớ. Thu hồi một role ghi
vào Postgres — và bốn tiến trình khác vẫn đang cho qua, cho tới khi có gì đó
bảo chúng nạp lại.

Casbin có Watcher cho việc này. Ở đây KHÔNG dùng, và lý do là bậc thang triển
khai chứ không phải kỹ thuật: Watcher đòi một kênh pub/sub và một vòng đời
riêng phải giám sát, còn hệ này đã có `event_outbox` — một bảng ghi cùng giao
dịch với thay đổi. Thêm một cơ chế đồng bộ thứ hai trước khi cần là thêm một
thứ có thể hỏng.

Ba lớp, cố ý xếp chồng
-----------------------
    1. Cùng tiến trình   `reload_policy()` gọi thẳng. Tức thì.
    2. Outbox            một dòng `authorization.policy.changed`, ghi trong
                         CÙNG giao dịch với thay đổi. Nếu giao dịch rollback
                         thì sự kiện cũng biến mất — không có sự kiện ma cho
                         một thay đổi chưa từng xảy ra.
    3. Nhịp nền          mỗi tiến trình tự đọc outbox theo chu kỳ và nạp lại
                         khi thấy dòng mới hơn thế hệ của mình.

Lớp 3 là thứ làm cho lớp 2 không cần phải hoàn hảo. Một sự kiện bị mất chỉ làm
policy cũ đi tới nhịp sau, chứ không sai vĩnh viễn — vì `reload_policy()` dựng
lại TOÀN BỘ từ cơ sở dữ liệu chứ không áp từng thay đổi.

Vì sao dò bằng `occurred_at` chứ không đánh dấu đã-xử-lý
--------------------------------------------------------
Nhiều tiến trình cùng đọc một hàng sự kiện. Nếu mỗi tiến trình đánh dấu
`processed_at`, tiến trình đầu tiên sẽ "tiêu thụ" sự kiện và bốn tiến trình còn
lại không bao giờ thấy nó — mỗi cái vẫn chạy policy cũ. Đây không phải hàng đợi
công việc mà là một mốc thời gian phát cho tất cả, nên mỗi tiến trình chỉ nhớ
"mình đã nạp tới đâu".

`dispatch_status` của những dòng này để nguyên `PENDING` vĩnh viễn — chúng
không dành cho worker webhook. Xem `EVENT_TYPE` bên dưới.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

#: Loại sự kiện. Worker webhook PHẢI bỏ qua loại này: nó là tín hiệu nội bộ
#: giữa các tiến trình API, không phải sự kiện nghiệp vụ để gửi cho khách hàng.
#: Gửi nó ra ngoài sẽ rò cấu trúc quyền nội bộ ra webhook của tenant.
EVENT_TYPE = "authorization.policy.changed"

#: Bao lâu thì hỏi outbox một lần. 20 giây là trần cho độ trễ lan truyền của
#: một lần thu hồi role — và §20 đã lo phần không chấp nhận được độ trễ đó
#: (`ALWAYS_REVALIDATE` đọc thẳng cơ sở dữ liệu).
POLL_INTERVAL_SECONDS = 20.0

_watermark: Optional[float] = None
_stop = threading.Event()
_thread: Optional[threading.Thread] = None


def emit(cur, *, tenant_id: Optional[str], reason: str,
         detail: Optional[dict] = None) -> None:
    """Ghi một sự kiện thay đổi policy. Phải dùng CON TRỎ CỦA GIAO DỊCH gọi.

    Nhận `cur` chứ không tự mở kết nối, và đó là toàn bộ điểm của outbox giao
    dịch: sự kiện và thay đổi cùng sống hoặc cùng chết. Mở kết nối riêng ở đây
    sẽ tạo ra hai kết cục sai — sự kiện gửi đi cho một thay đổi đã rollback, và
    thay đổi commit mà không có sự kiện nào.

    `tenant_id` để None cho thay đổi ở tầng nền tảng. Xem chú thích ở
    `CREATE TABLE event_outbox` về vì sao cột đó cho phép NULL, và về việc ghi
    NULL PHẢI xảy ra trong system scope.
    """
    payload = {"reason": reason}
    if detail:
        payload.update(detail)

    from psycopg2.extras import Json

    cur.execute(
        "INSERT INTO event_outbox (tenant_id, event_type_code, payload) "
        "VALUES (%s, %s, %s)",
        (tenant_id, EVENT_TYPE, Json(payload)),
    )


def latest_change() -> Optional[float]:
    """Thời điểm sự kiện đổi policy gần nhất, dạng epoch. None nếu chưa có."""
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("authz: doc moc thay doi policy cua moi tenant"):
        rows = _fetch_all(
            "SELECT extract(epoch FROM max(occurred_at)) AS latest "
            "  FROM event_outbox WHERE event_type_code = %s",
            (EVENT_TYPE,),
        )
    value = rows[0]["latest"] if rows else None
    return float(value) if value is not None else None


def check_once() -> bool:
    """Nạp lại nếu có thay đổi mới hơn lần nạp trước. True nếu đã nạp lại."""
    global _watermark

    try:
        latest = latest_change()
    except Exception as exc:
        # Postgres chớp một nhịp không được làm chết luồng nền. Policy hiện tại
        # vẫn dùng được; nhịp sau thử lại.
        logger.warning("[AUTHZ-INVALIDATE] khong doc duoc outbox: %s", exc)
        return False

    if latest is None:
        return False

    if _watermark is not None and latest <= _watermark:
        return False

    from app.authorization.enforcer import reload_policy

    first = _watermark is None
    _watermark = latest
    if first:
        # Lần chạy đầu chỉ ghi mốc. Enforcer vừa được `startup()` nạp xong nên
        # nó đã tươi; nạp lại ngay là một lượt đọc năm bảng không mua được gì.
        return False

    return reload_policy(reason="outbox: authorization.policy.changed")


def _loop() -> None:
    while not _stop.wait(POLL_INTERVAL_SECONDS):
        try:
            check_once()
        except Exception:  # pragma: no cover
            logger.exception("[AUTHZ-INVALIDATE] nhip nen that bai")


def start() -> None:
    """Bật luồng nền theo dõi thay đổi policy. Gọi lần hai là no-op."""
    global _thread, _watermark
    if _thread is not None and _thread.is_alive():
        return
    # Đặt mốc trước khi luồng chạy, để nhịp đầu tiên không nạp lại một cách vô
    # ích ngay sau `startup()`.
    try:
        _watermark = latest_change()
    except Exception:
        _watermark = None
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="authz-policy-watch", daemon=True)
    _thread.start()
    logger.info("[AUTHZ-INVALIDATE] theo doi thay doi policy moi %.0fs", POLL_INTERVAL_SECONDS)


def stop() -> None:
    _stop.set()


def reset_for_tests() -> None:
    global _watermark
    _watermark = None
    _stop.set()
