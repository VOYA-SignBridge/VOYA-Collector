"""Tác vụ nền của mặt phẳng SaaS: gộp số đo, giao webhook, dọn bản xuất.

Mọi tác vụ ở đây đều `platform_wide=True`. Không phải vì tiện: chúng đọc hoặc ghi
qua NHIỀU tenant trong một lượt chạy (gộp số đo cho tất cả, giao webhook cho
tất cả), và một tác vụ như thế bị giới hạn vào ngữ cảnh tenant của yêu cầu đã
phái nó đi sẽ âm thầm chỉ làm được một phần — kiểu hỏng mà `export_tasks` đã
gặp và ghi lại: "the export succeeds, it is just short".

`run_tenant_export` chỉ chạm một tenant, nhưng vẫn platform_wide vì nó được
phái từ một quản trị viên nền tảng đang đứng ở tenant KHÁC với tenant được
xuất — đúng tình huống mà ngữ cảnh của người phái là câu trả lời sai.
"""

from __future__ import annotations

import logging

from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300, platform_wide=True)
def rollup_usage_daily(self, day: str | None = None):
    """Gộp số đo mức dùng của ngày hôm qua cho mọi tenant.

    Chạy lại an toàn — xem chú thích ở `app/usage.py`. Đó là lý do việc thử lại
    ở đây không cần thận trọng gì đặc biệt.
    """
    from datetime import date

    from app.usage import rollup_day

    try:
        target = date.fromisoformat(day) if day else None
        return rollup_day(target)
    except Exception as exc:
        logger.error("[SAAS] gộp số đo hỏng: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, platform_wide=True)
def deliver_webhooks(self, limit: int = 50):
    """Giao những webhook đang chờ tới hạn.

    KHÔNG thử lại ở tầng Celery: việc thử lại đã nằm trong chính bảng giao
    (`next_attempt_at` + `attempts`). Thêm một tầng thử lại nữa ở đây sẽ nhân
    số lần gọi tới máy chủ của khách hàng lên, và làm bộ đếm hỏng-liên-tiếp
    chạy nhanh gấp bội thực tế — endpoint sẽ bị tự tắt oan.
    """
    from app.webhooks import deliver_pending

    try:
        return deliver_pending(limit=int(limit))
    except Exception as exc:
        logger.error("[SAAS] vòng giao webhook hỏng: %s", exc)
        return {"sent": 0, "failed": 0, "error": type(exc).__name__}


@celery_app.task(bind=True, platform_wide=True)
def run_tenant_export(self, export_id: str):
    """Dựng gói zip cho một yêu cầu xuất."""
    from app.tenant_lifecycle import run_export

    try:
        return run_export(str(export_id))
    except Exception as exc:
        # `run_export` đã ghi trạng thái 'failed' kèm nguyên nhân vào bảng
        # trước khi ném, nên người dùng thấy được lý do trên giao diện. Ở đây
        # chỉ cần không nuốt mất dấu vết trong nhật ký.
        logger.error("[SAAS] xuất %s hỏng: %s", export_id, exc)
        raise


@celery_app.task(bind=True, platform_wide=True)
def sweep_subscriptions(self):
    """Một lượt vòng đời đăng ký: nhắc → gia hạn → ân hạn → khoá mềm.

    Vỏ mỏng có chủ ý. Toàn bộ luật nằm ở `app/subscription_lifecycle.sweep()`,
    nơi gọi được thẳng từ bộ test và từ dòng lệnh mà không cần Celery — một
    quy tắc nghiệp vụ chỉ chạy được bên trong một tác vụ nền là quy tắc không
    ai kiểm được.

    KHÔNG thu tiền: hệ thống không có cổng thanh toán. `auto_renew` chỉ nói
    "mở kỳ tiếp theo". Xem `docs/SUBSCRIPTION_LIFECYCLE.md`.
    """
    from app.subscription_lifecycle import sweep

    try:
        return sweep()
    except Exception as exc:
        # Nuốt ở tầng ngoài cùng: một lượt quét hỏng không được phép làm
        # celery-beat coi tác vụ là chết và ngừng lên lịch.
        logger.error("[SAAS] quét vòng đời đăng ký hỏng: %s", exc)
        return {"loi": 1}


@celery_app.task(bind=True, platform_wide=True)
def cleanup_saas_artifacts(self, delivery_history_days: int = 30):
    """Dọn định kỳ: bản xuất hết hạn và lịch sử giao webhook cũ.

    Gộp hai việc vào một tác vụ vì cả hai đều là dọn rác theo ngày và cùng
    nhịp; hai mục lịch riêng cho hai câu DELETE là thêm thứ phải nhớ mà không
    thêm khả năng nào.
    """
    from app.tenant_lifecycle import cleanup_expired_exports
    from app.webhooks import purge_old_deliveries

    out = {"exports_removed": 0, "deliveries_purged": 0}
    try:
        out["exports_removed"] = cleanup_expired_exports()
    except Exception as exc:
        logger.error("[SAAS] dọn bản xuất hỏng: %s", exc)
    try:
        purge_old_deliveries(days=int(delivery_history_days))
        out["deliveries_purged"] = 1
    except Exception as exc:
        logger.error("[SAAS] dọn lịch sử webhook hỏng: %s", exc)
    return out


@celery_app.task(bind=True, platform_wide=True)
def cleanup_refresh_tokens(self, retain_days: int = 7):
    """Dọn refresh token đã hết hạn. Logic ở `auth.purge_expired_refresh_tokens`.

    `platform_wide` vì bảng `refresh_tokens` thuộc mặt phẳng danh tính — nó
    không mang `tenant_id`, và một lượt dọn theo tenant sẽ bỏ sót phần lớn bảng.
    """
    from app.auth import purge_expired_refresh_tokens

    try:
        removed = purge_expired_refresh_tokens(retain_days=int(retain_days))
        if removed:
            logger.info("[AUTH] don %d refresh token het han", removed)
        return {"removed": removed}
    except Exception as exc:
        logger.error("[AUTH] dọn refresh token hỏng: %s", exc)
        return {"loi": 1}


@celery_app.task(bind=True, platform_wide=True)
def sweep_support_backlog(self):
    """Một lượt kiểm tồn đọng kênh hỗ trợ.

    `platform_wide=True` là bắt buộc, không phải trang trí. Tác vụ này đọc
    `support_tickets`/`support_messages` của MỌI tổ chức để biết tổ chức nào
    đang có phiếu bị bỏ quên. Chạy trong phạm vi một tenant — hoặc tệ hơn,
    không phạm vi nào — thì RLS trả về đúng 0 dòng và lượt quét báo "không có
    tồn đọng" một cách hoàn hảo, mãi mãi. Xem `storage/rls.py` và
    `docs/needFix` về fail-open ở mặt phẳng danh tính.
    """
    from app.support_backlog import sweep

    try:
        return sweep()
    except Exception as exc:
        # Nuốt ở tầng ngoài: một lượt quét hỏng không được phép làm celery-beat
        # coi tác vụ là chết và thôi lên lịch — đúng lúc cần nó nhất.
        logger.error("[SUPPORT] quét tồn đọng hỏng: %s", exc)
        return {"loi": 1}


@celery_app.task(bind=True, platform_wide=True, max_retries=3)
def send_support_ticket_emails(self, ticket_id: str, tenant_id: str,
                               subject: str, category: str, requester: str):
    """Gửi thư báo phiếu mới cho người trực — NGOÀI luồng yêu cầu.

    Vì sao không gửi thẳng trong `create_ticket`
    ---------------------------------------------
    Người nhận là *mọi* quản trị viên của tổ chức, và `smtplib` mở kết nối với
    `timeout=10`. Một tổ chức mười quản trị viên gặp một máy chủ thư chậm là
    người dùng ngồi nhìn nút "Gửi" quay cả phút — cho một việc phụ mà họ không
    hề yêu cầu. Phiếu đã nằm trong cơ sở dữ liệu và chuông trong ứng dụng đã
    kêu trước đó; thư có tới sau vài giây cũng không sao.

    `platform_wide=True`: tác vụ tự tra danh sách người nhận theo `tenant_id`
    được truyền vào, nên nó cần đọc `users` ngoài phạm vi của người phái.
    """
    from app import email_service, support
    from app.config import settings

    try:
        recipients = support._staff_emails(support._staff_recipients(str(tenant_id)))
        if not recipients:
            logger.warning("[SUPPORT] phieu %s: khong co dia chi thu da xac minh", ticket_id)
            return {"da_gui": 0}

        base = (settings.frontend_base_url or "").rstrip("/")
        link = f"{base}/admin/support/{ticket_id}"
        for addr in recipients:
            email_service.send_support_ticket_email(
                addr, ticket_id=str(ticket_id), subject=subject,
                category=category or "other",
                requester=requester or "Người dùng", link=link)
        return {"da_gui": len(recipients)}
    except Exception as exc:
        logger.error("[SUPPORT] khong gui duoc thu bao phieu %s: %s", ticket_id, exc)
        return {"loi": 1}
