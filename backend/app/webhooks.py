"""Webhook: nền tảng gọi ngược về hệ thống của khách khi có việc xảy ra.

Khoá API cho khách hỏi nền tảng. Webhook là chiều ngược lại — không có nó,
tích hợp duy nhất khả thi là hỏi dò theo chu kỳ, và hỏi dò thì hoặc chậm hoặc
tốn, không có ở giữa.

Chữ ký, và vì sao phải có dấu thời gian trong đó
------------------------------------------------
Mỗi lần giao mang hai header:

    X-Voya-Timestamp: 1754630400
    X-Voya-Signature: sha256=<hex>

trong đó chữ ký là HMAC-SHA256 của chuỗi ``<timestamp>.<thân thư>``.

Nếu chỉ ký thân thư, một người chặn được đường truyền có thể phát lại nguyên
văn một lần giao cũ mãi mãi và chữ ký vẫn đúng — "mẫu đã được duyệt" gửi lại
một nghìn lần. Đưa dấu thời gian vào phần được ký khiến bên nhận từ chối được
mọi thứ cũ hơn vài phút, và họ không thể tự làm điều đó nếu dấu thời gian nằm
ngoài chữ ký (sửa được thì vô nghĩa). Đây là cách Stripe làm, vì cùng lý do.

Lùi dần và bỏ cuộc
-------------------
Năm lần thử, cách nhau 1, 5, 25, 125 phút. Sau lần thứ năm thì lần giao đó
`failed` và đếm hỏng liên tiếp của endpoint tăng lên; tới 20 lần hỏng liên
tiếp thì endpoint tự TẮT. Không tắt thì một URL đã chết vĩnh viễn sẽ được thử
lại mãi mãi, và hàng đợi giao dần biến thành một danh sách rác chạy nền.

Một lần giao THÀNH CÔNG đặt lại bộ đếm về 0, nên một sự cố ngắn bên khách hàng
không tích luỹ tới ngưỡng tắt.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Loại sự kiện phát ra. Danh sách trắng, không phải chuỗi tự do: một endpoint
#: đăng ký nhận `sample.creted` (gõ sai) sẽ im lặng không bao giờ nhận gì, và
#: người dựng tích hợp mất một buổi chiều để phát hiện.
EVENT_TYPES = (
    "sample.created",
    "training.completed",
    "training.failed",
    "class.created",
    "quota.exceeded",
    "tenant.plan_changed",
)

#: Số phút chờ trước mỗi lần thử lại, tính từ lần thử đầu.
RETRY_SCHEDULE_MINUTES = (1, 5, 25, 125)
MAX_ATTEMPTS = len(RETRY_SCHEDULE_MINUTES) + 1

#: Số lần hỏng liên tiếp trước khi tự tắt một endpoint.
FAILURE_STREAK_LIMIT = 20

#: Trần kích thước thân thư gửi đi. Một payload khổng lồ làm nghẽn tiến trình
#: giao cho mọi endpoint khác, vì hàng đợi giao chỉ có một.
MAX_PAYLOAD_BYTES = 64 * 1024

_TIMEOUT_SECONDS = 10


class WebhookError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


# --------------------------------------------------------------------------- endpoints


def _validate_url(url: str) -> str:
    """Chỉ nhận http(s) và chặn địa chỉ nội bộ.

    Một webhook trỏ vào `http://localhost:8000/api/v1/...` hay
    `http://169.254.169.254/` biến nền tảng thành công cụ gửi yêu cầu hộ vào
    chính mạng nội bộ của nó (SSRF). Người tạo webhook là khách hàng, không
    phải người vận hành, nên đây là dữ liệu không tin được.

    Chặn theo TÊN MÁY chứ không phải theo IP đã phân giải, và đó là hạn chế đã
    biết: một tên miền công khai trỏ về 127.0.0.1 vẫn lọt. Chặn triệt để cần
    phân giải DNS rồi kiểm IP ngay trước khi gửi, và phải làm lại ở mỗi lần thử
    vì DNS đổi được giữa chừng. Ghi ra đây để lần sau ai đọc cũng biết ranh
    giới nằm ở đâu, thay vì tưởng chỗ này đã kín.
    """
    from urllib.parse import urlparse

    text = (url or "").strip()
    if len(text) > 2000:
        raise WebhookError("URL quá dài", status_code=422)
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https"):
        raise WebhookError("URL phải bắt đầu bằng http:// hoặc https://", status_code=422)
    host = (parsed.hostname or "").lower()
    if not host:
        raise WebhookError("URL thiếu tên máy", status_code=422)

    blocked = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}
    if host in blocked or host.endswith(".localhost") or host.endswith(".internal"):
        raise WebhookError("URL không được trỏ vào mạng nội bộ", status_code=422)
    if host.startswith(("10.", "192.168.", "169.254.", "172.16.", "172.17.",
                        "172.18.", "172.19.", "172.2", "172.30.", "172.31.")):
        raise WebhookError("URL không được trỏ vào mạng nội bộ", status_code=422)
    return text


def _validate_events(event_types: str) -> str:
    text = (event_types or "*").strip()
    if text == "*":
        return "*"
    wanted = [e.strip() for e in text.split(",") if e.strip()]
    unknown = [e for e in wanted if e not in EVENT_TYPES]
    if unknown:
        raise WebhookError(
            f"loại sự kiện không biết: {', '.join(unknown)}. "
            f"Đang hỗ trợ: {', '.join(EVENT_TYPES)}",
            status_code=422,
        )
    return ",".join(wanted)


def create_endpoint(
    tenant_id: str,
    *,
    url: str,
    event_types: str = "*",
    description: str = "",
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Đăng ký một URL nhận sự kiện. Bí mật ký chỉ trả về ở đây, một lần."""
    from app.plans import QuotaExceeded, enforce
    from app.storage.metadata_db import _execute
    from app.tenancy import normalize_tenant_id
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id)
    clean_url = _validate_url(url)
    events = _validate_events(event_types)

    try:
        enforce(tenant, "webhook_endpoints", adding=1)
    except QuotaExceeded as exc:
        raise WebhookError(str(exc), status_code=exc.status_code) from exc

    endpoint_id = str(uuid.uuid4())
    secret = f"whsec_{secrets.token_urlsafe(32)}"
    with system_scope("webhooks: register an endpoint for a tenant"):
        _execute(
            "INSERT INTO webhook_endpoints(endpoint_id, tenant_id, url, secret, "
            "event_types, description, created_by) VALUES(%s, %s, %s, %s, %s, %s, %s)",
            (
                endpoint_id, tenant, clean_url, secret, events,
                (description or "").strip()[:500],
                str(created_by) if created_by else None,
            ),
        )
    logger.info("[WEBHOOK] %s đăng ký endpoint %s", tenant, endpoint_id)
    return {
        "endpoint_id": endpoint_id, "tenant_id": tenant, "url": clean_url,
        "event_types": events, "is_active": True, "secret": secret,
    }


def list_endpoints(tenant_id: str) -> List[Dict[str, Any]]:
    """Endpoint của một tenant. KHÔNG bao giờ kèm `secret`.

    Cột bí mật bị loại ngay ở câu SELECT chứ không lọc ở Python: một hàm tuần
    tự hoá thêm sau này sẽ không thể vô tình đưa nó ra ngoài nếu nó chưa từng
    rời khỏi cơ sở dữ liệu.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenancy import normalize_tenant_id
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id)
    with system_scope("webhooks: list the endpoints of a tenant"):
        rows = _fetch_all(
            "SELECT endpoint_id, tenant_id, url, event_types, is_active, description, "
            "created_by, created_at, last_success_at, last_failure_at, failure_streak, "
            "disabled_at, disabled_reason FROM webhook_endpoints "
            "WHERE tenant_id = %s ORDER BY created_at DESC",
            (tenant,),
        )
    return [dict(r) for r in rows]


def delete_endpoint(tenant_id: str, endpoint_id: str) -> None:
    from app.storage.metadata_db import _execute, _fetch_all
    from app.tenancy import normalize_tenant_id
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id)
    with system_scope("webhooks: delete an endpoint"):
        if not _fetch_all(
            "SELECT 1 FROM webhook_endpoints WHERE endpoint_id = %s AND tenant_id = %s",
            (str(endpoint_id), tenant),
        ):
            raise WebhookError("không tìm thấy endpoint", status_code=404)
        _execute("DELETE FROM webhook_endpoints WHERE endpoint_id = %s", (str(endpoint_id),))
    logger.info("[WEBHOOK] xoá endpoint %s", endpoint_id)


# --------------------------------------------------------------------------- signing


def sign(secret: str, timestamp: int, body: bytes) -> str:
    """Chữ ký của một lần giao. Xem chú thích đầu tệp về vì sao có dấu thời gian."""
    message = f"{timestamp}.".encode("utf-8") + body
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify(secret: str, timestamp: int, body: bytes, signature: str,
           *, tolerance_seconds: int = 300) -> bool:
    """Bản kiểm chứng phía nhận, để tài liệu và test dùng chung một cài đặt.

    Đưa vào đây thay vì chỉ mô tả bằng lời trong tài liệu: một mô tả bằng lời
    sẽ trôi khỏi mã, còn hàm này thì bị test giữ lại đúng.
    """
    now = int(datetime.now(timezone.utc).timestamp())
    if abs(now - int(timestamp)) > tolerance_seconds:
        return False
    return hmac.compare_digest(sign(secret, int(timestamp), body), signature or "")


# --------------------------------------------------------------------------- dispatch


def emit(tenant_id: str, event_type: str, payload: Dict[str, Any]) -> int:
    """Xếp một sự kiện vào hàng giao cho mọi endpoint đang nghe nó.

    Không gửi ngay tại chỗ. Đường gọi tới đây là đường ghi của người dùng
    (tải mẫu lên, xong một lượt huấn luyện), và một URL của khách hàng mất mười
    giây mới trả lời sẽ làm chậm đúng mười giây thao tác của người dùng đó.
    Ghi vào bảng rồi để tác vụ nền giao là thứ tách hai chuyện đó ra.

    Nuốt mọi lỗi: webhook là tính năng phụ trợ, và làm hỏng một lượt tải mẫu vì
    bảng giao ghi không được là đánh đổi sai.
    """
    if event_type not in EVENT_TYPES:
        logger.error("[WEBHOOK] loại sự kiện không biết: %s", event_type)
        return 0

    try:
        from app.storage.metadata_db import _execute, _fetch_all
        from app.tenancy import normalize_tenant_id
        from app.tenant_context import system_scope

        tenant = normalize_tenant_id(tenant_id)
        body = json.dumps(
            {"event": event_type, "tenant_id": tenant, "data": payload,
             "created_at": datetime.now(timezone.utc).isoformat()},
            ensure_ascii=False,
        )
        if len(body.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            logger.error("[WEBHOOK] %s: payload quá lớn, bỏ qua", event_type)
            return 0

        with system_scope("webhooks: queue a delivery for each listening endpoint"):
            rows = _fetch_all(
                "SELECT endpoint_id FROM webhook_endpoints "
                "WHERE tenant_id = %s AND is_active "
                "AND (event_types = '*' OR event_types LIKE %s)",
                (tenant, f"%{event_type}%"),
            )
            for row in rows:
                _execute(
                    "INSERT INTO webhook_deliveries(delivery_id, tenant_id, endpoint_id, "
                    "event_type, payload) VALUES(%s, %s, %s, %s, %s)",
                    (str(uuid.uuid4()), tenant, str(row["endpoint_id"]), event_type, body),
                )
        return len(rows)
    except Exception as exc:
        logger.warning("[WEBHOOK] không xếp được %s: %s", event_type, type(exc).__name__)
        return 0


def _record_success(endpoint_id: str, delivery_id: str, status_code: int) -> None:
    from app.storage.metadata_db import _execute

    _execute(
        "UPDATE webhook_deliveries SET status = 'delivered', delivered_at = NOW(), "
        "attempts = attempts + 1, last_status_code = %s, last_error = NULL "
        "WHERE delivery_id = %s",
        (status_code, delivery_id),
    )
    _execute(
        "UPDATE webhook_endpoints SET last_success_at = NOW(), failure_streak = 0 "
        "WHERE endpoint_id = %s",
        (endpoint_id,),
    )


def _record_failure(
    endpoint_id: str, delivery_id: str, attempts: int,
    status_code: Optional[int], error: str,
) -> None:
    from app.storage.metadata_db import _execute, _fetch_all

    attempt_no = attempts + 1
    exhausted = attempt_no >= MAX_ATTEMPTS
    if exhausted:
        _execute(
            "UPDATE webhook_deliveries SET status = 'failed', attempts = %s, "
            "last_status_code = %s, last_error = %s WHERE delivery_id = %s",
            (attempt_no, status_code, error[:500], delivery_id),
        )
    else:
        delay = RETRY_SCHEDULE_MINUTES[attempt_no - 1]
        _execute(
            "UPDATE webhook_deliveries SET attempts = %s, last_status_code = %s, "
            "last_error = %s, next_attempt_at = NOW() + %s * INTERVAL '1 minute' "
            "WHERE delivery_id = %s",
            (attempt_no, status_code, error[:500], delay, delivery_id),
        )

    _execute(
        "UPDATE webhook_endpoints SET last_failure_at = NOW(), "
        "failure_streak = failure_streak + 1 WHERE endpoint_id = %s",
        (endpoint_id,),
    )
    rows = _fetch_all(
        "SELECT failure_streak FROM webhook_endpoints WHERE endpoint_id = %s",
        (endpoint_id,),
    )
    if rows and int(rows[0]["failure_streak"] or 0) >= FAILURE_STREAK_LIMIT:
        _execute(
            "UPDATE webhook_endpoints SET is_active = FALSE, disabled_at = NOW(), "
            "disabled_reason = %s WHERE endpoint_id = %s AND is_active",
            (f"Tự tắt sau {FAILURE_STREAK_LIMIT} lần giao hỏng liên tiếp.", endpoint_id),
        )
        logger.warning("[WEBHOOK] tự tắt endpoint %s", endpoint_id)


def deliver_pending(*, limit: int = 50) -> Dict[str, int]:
    """Giao những lần đang chờ tới hạn. Gọi từ tác vụ nền.

    `limit` chặn một lượt chạy kéo dài vô hạn khi có tồn đọng lớn: lượt sau sẽ
    lấy tiếp phần còn lại, và trong lúc đó tác vụ nền vẫn trả quyền điều khiển
    cho những việc khác.
    """
    import requests

    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    sent = failed = 0
    with system_scope("webhooks: read the pending delivery queue"):
        rows = _fetch_all(
            "SELECT d.delivery_id, d.endpoint_id, d.payload, d.attempts, d.event_type, "
            "e.url, e.secret FROM webhook_deliveries d "
            "JOIN webhook_endpoints e ON e.endpoint_id = d.endpoint_id "
            "WHERE d.status = 'pending' AND d.next_attempt_at <= NOW() AND e.is_active "
            "ORDER BY d.next_attempt_at LIMIT %s",
            (int(limit),),
        )

    for row in rows:
        delivery_id = str(row["delivery_id"])
        endpoint_id = str(row["endpoint_id"])
        payload = row["payload"]
        body = (payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False))
        body_bytes = body.encode("utf-8")
        timestamp = int(datetime.now(timezone.utc).timestamp())

        try:
            response = requests.post(
                row["url"],
                data=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "VOYA-Webhooks/1",
                    "X-Voya-Event": row["event_type"],
                    "X-Voya-Delivery": delivery_id,
                    "X-Voya-Timestamp": str(timestamp),
                    "X-Voya-Signature": sign(row["secret"], timestamp, body_bytes),
                },
                timeout=_TIMEOUT_SECONDS,
                # Không đi theo chuyển hướng: một endpoint đã qua kiểm URL rồi
                # trả về 302 tới `http://127.0.0.1` là đường vòng qua đúng cái
                # kiểm tra SSRF ở `_validate_url`.
                allow_redirects=False,
            )
            with system_scope("webhooks: record a delivery outcome"):
                if 200 <= response.status_code < 300:
                    _record_success(endpoint_id, delivery_id, response.status_code)
                    sent += 1
                else:
                    _record_failure(
                        endpoint_id, delivery_id, int(row["attempts"] or 0),
                        response.status_code, f"HTTP {response.status_code}",
                    )
                    failed += 1
        except Exception as exc:
            with system_scope("webhooks: record a delivery error"):
                _record_failure(
                    endpoint_id, delivery_id, int(row["attempts"] or 0),
                    None, f"{type(exc).__name__}: {exc}",
                )
            failed += 1

    if sent or failed:
        logger.info("[WEBHOOK] giao xong: %d thành công, %d hỏng", sent, failed)
    return {"sent": sent, "failed": failed}


def queue_test_delivery(tenant_id: str, endpoint_id: str) -> str:
    """Xếp một sự kiện thử cho đúng một endpoint, đi qua đường giao thật.

    Cùng chữ ký, cùng header, cùng cơ chế thử lại. Một nút "thử" gửi bằng
    đường riêng sẽ chứng minh được một thứ không phải thứ người dùng cần biết.
    """
    from app.storage.metadata_db import _execute, _fetch_all
    from app.tenancy import normalize_tenant_id
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id)
    with system_scope("webhooks: queue a test delivery"):
        if not _fetch_all(
            "SELECT 1 FROM webhook_endpoints "
            "WHERE endpoint_id = %s AND tenant_id = %s AND is_active",
            (str(endpoint_id), tenant),
        ):
            raise WebhookError("không tìm thấy endpoint đang bật", status_code=404)
        delivery_id = str(uuid.uuid4())
        body = json.dumps(
            {
                "event": "sample.created",
                "tenant_id": tenant,
                "data": {"test": True, "message": "Đây là sự kiện thử từ VOYA."},
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        )
        _execute(
            "INSERT INTO webhook_deliveries(delivery_id, tenant_id, endpoint_id, "
            "event_type, payload) VALUES(%s, %s, %s, 'sample.created', %s)",
            (delivery_id, tenant, str(endpoint_id), body),
        )
    return delivery_id


def recent_deliveries(tenant_id: str, endpoint_id: str, *, limit: int = 25) -> List[Dict[str, Any]]:
    """Lịch sử giao gần đây của một endpoint — thứ cần để gỡ rối một tích hợp.

    Không trả `payload`: nó có thể lớn, và người dựng tích hợp cần biết KẾT QUẢ
    (mã trạng thái, lỗi, số lần thử) chứ không cần đọc lại nội dung mình vừa
    nhận được.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenancy import normalize_tenant_id
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id)
    with system_scope("webhooks: read recent deliveries of an endpoint"):
        rows = _fetch_all(
            "SELECT delivery_id, event_type, status, attempts, last_status_code, "
            "last_error, next_attempt_at, created_at, delivered_at "
            "FROM webhook_deliveries WHERE endpoint_id = %s AND tenant_id = %s "
            "ORDER BY created_at DESC LIMIT %s",
            (str(endpoint_id), tenant, max(1, min(int(limit), 100))),
        )
    return [dict(r) for r in rows]


def purge_old_deliveries(*, days: int = 30) -> int:
    """Dọn lịch sử giao cũ. Không có nó, bảng này lớn mãi không dừng."""
    from app.storage.metadata_db import _execute
    from app.tenant_context import system_scope

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    with system_scope("webhooks: purge old delivery history"):
        _execute(
            "DELETE FROM webhook_deliveries WHERE created_at < %s "
            "AND status IN ('delivered', 'failed', 'dropped')",
            (cutoff,),
        )
    return 0
