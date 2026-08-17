"""Vòng đời đăng ký: kỳ hạn, nhắc trước hạn, ân hạn, khoá mềm.

Khoảng trống được lấp
----------------------
`tenant_subscriptions` từ v4 chỉ có `started_at` và `ended_at` (thời điểm bị
đóng). Không cột nào nói **bao giờ hết hạn**, nên một đăng ký mở là mở vô thời
hạn cho tới khi người vận hành sửa tay. Hệ quả dây chuyền: không hết hạn thì
không có gia hạn, không có gì để nhắc, không có ân hạn để đệm, và
`plans.trial_days` chưa từng được một dòng mã nào đọc tới. Lịch Celery beat có
5 tác vụ định kỳ và không tác vụ nào chạm tới đăng ký.

Điều module này KHÔNG làm, nói trước để không ai hiểu nhầm
-----------------------------------------------------------
**Không thu tiền.** Hệ thống không có cổng thanh toán, không có hoá đơn, không
có bút toán. `auto_renew = TRUE` nghĩa là *"tới hạn thì mở tiếp kỳ mới"*, chứ
KHÔNG phải *"trừ tiền thẻ"* — việc thu tiền diễn ra ngoài hệ thống, và đăng ký
ở đây chỉ ghi lại quyết định đó. Đặt tên là `auto_renew` mà bên dưới không có
giao dịch nào là chỗ dễ hiểu nhầm nhất của cả module, nên nó được viết ra ở
đây, ở docstring của `sweep()`, và trong `docs/07-business/SUBSCRIPTION_LIFECYCLE.md`.

Bốn trạng thái, và ranh giới giữa chúng
----------------------------------------
Trạng thái sống ở `tenants.billing_status`, không ở đây — module này chỉ *di
chuyển* nó. Bảng từ vựng đã có sẵn từ trước (`ck_tenants_billing_status`), và
`plans.assert_writable` đã cưỡng chế nó ở mọi đường ghi. Nghĩa là "khoá mềm"
không cần một cơ chế mới: nó là `suspended`, và cổng chặn đã đứng sẵn ở đó.

    trialing / active   → ghi được, mọi thứ bình thường
    past_due            → ghi được, nhưng đã quá hạn và đang trong ân hạn
    suspended           → CHỈ ĐỌC. Dữ liệu còn nguyên, không mất gì.
    cancelled           → chỉ đọc, và là quyết định của người dùng

`past_due` vẫn ghi được là quyết định có từ trước và module này giữ nguyên:
khoá dữ liệu của một trường vì hoá đơn trễ hai ngày là cách nhanh nhất để mất
họ, và số tiền không vì thế mà đòi được nhanh hơn.

Vì sao khoá mềm KHÔNG BAO GIỜ xoá gì
-------------------------------------
Hết hạn là một sự kiện thương mại, không phải một phán quyết về dữ liệu. Người
dùng phải luôn lấy lại được thứ họ đã đóng góp — đường xuất ở
`routers/tenants.py` vẫn chạy khi tenant `suspended`, và đó là chủ ý.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: `plans.billing_period` → độ dài một kỳ, tính bằng ngày.
#:
#: `none` trả về None và nghĩa là **không có kỳ hạn** — gói nội bộ và gói dùng
#: thử của nền tảng không hết hạn theo lịch. Trả None chứ không trả một số lớn:
#: "vô hạn" và "365 ngày" là hai điều khác nhau, và mã đọc phải phân biệt được.
PERIOD_DAYS: Dict[str, Optional[int]] = {
    "none": None,
    "monthly": 30,
    "quarterly": 91,
    "yearly": 365,
}

#: Nhắc trước bao nhiêu ngày. Giảm dần — `_reminder_due` dựa vào thứ tự này.
REMINDER_DAYS: tuple[int, ...] = (7, 3, 1)


class SubscriptionError(RuntimeError):
    def __init__(self, message: str, *, code: str = "subscription_error",
                 status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _grace_days() -> int:
    from app.config import settings

    return max(0, int(getattr(settings, "subscription_grace_days", 7)))


def period_length_days(plan: Dict[str, Any]) -> Optional[int]:
    """Độ dài một kỳ của gói, hoặc None khi gói không có kỳ hạn.

    Một `billing_period` lạ trả về None chứ không đoán: mở vô thời hạn là hỏng
    an toàn (người dùng không mất quyền ghi vì một giá trị chưa ai lường), còn
    đoán bừa 30 ngày thì khoá người ta vì một lỗi chính tả trong bảng gói.
    """
    period = str(plan.get("billing_period") or "none").strip().lower()
    if period not in PERIOD_DAYS:
        logger.warning("[SUB] billing_period la: %r (goi %s) — coi nhu khong ky han",
                       period, plan.get("plan_code"))
        return None
    return PERIOD_DAYS[period]


def open_subscription(tenant_id: str) -> Optional[Dict[str, Any]]:
    """Đăng ký ĐANG MỞ của một tenant. `uq_tenant_subscriptions_open` bảo đảm ≤1."""
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("subscription: doc dang ky dang mo"):
        rows = _fetch_all(
            "SELECT * FROM tenant_subscriptions "
            "WHERE tenant_id = %s AND ended_at IS NULL",
            (str(tenant_id),),
        )
    return dict(rows[0]) if rows else None


def start_period(tenant_id: str, *, plan_code: Optional[str] = None,
                 now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """Đặt kỳ hạn cho đăng ký đang mở, kể cả khi nó chưa từng có kỳ nào.

    Là **idempotent theo mốc**: gọi lại khi kỳ hiện tại còn hiệu lực sẽ không
    dời mốc. Đây là điều bắt buộc, vì hàm này được gọi cả từ `sweep()` (mỗi
    giờ) lẫn từ đường đổi gói.

    Gói không có kỳ hạn (`billing_period='none'`) thì các cột kỳ hạn được để
    NULL — không phải một ngày rất xa. NULL đọc được là "không áp dụng"; một
    ngày năm 2999 thì trông như dữ liệu hỏng.
    """
    from app import plans
    from app.storage.metadata_db import _execute
    from app.tenant_context import system_scope

    at = now or _now()
    sub = open_subscription(tenant_id)
    if sub is None:
        return None

    plan = plans.get_plan(plan_code or sub.get("plan_code") or "") or {}
    length = period_length_days(plan)
    if length is None:
        return sub

    # Kỳ hiện tại còn hiệu lực → không đụng vào.
    if sub.get("current_period_end") and sub["current_period_end"] > at:
        return sub

    trial_days = int(plan.get("trial_days") or 0)
    # Kỳ ĐẦU TIÊN của một gói có dùng thử thì dài bằng thời gian dùng thử. Sau
    # đó mới tới các kỳ tính phí. Không cộng dồn hai khoảng: "30 ngày dùng thử
    # rồi 30 ngày trả phí" khác hẳn "60 ngày", và người dùng đọc hoá đơn sẽ thấy.
    prev_end = sub.get("current_period_end")
    first_period = prev_end is None
    span = trial_days if (first_period and trial_days > 0) else length

    if first_period:
        start = at
    else:
        # NEO VÀO MỐC CŨ, không neo vào "bây giờ". Lượt quét chạy mỗi giờ nên
        # một lần gia hạn luôn diễn ra muộn hơn mốc hết hạn một chút; lấy `at`
        # làm điểm bắt đầu thì mỗi kỳ trôi thêm chừng ấy, và sau một năm gói
        # tháng lệch khoảng nửa ngày so với ngày người ta đã trả tiền cho.
        start = prev_end
    end = start + timedelta(days=span)

    # Worker nghỉ dài (hoặc `SUBSCRIPTION_SWEEP_ENABLED=0` một thời gian) có thể
    # bỏ lỡ NHIỀU kỳ. Nhảy tới kỳ đang chứa `at` thay vì mở một kỳ đã hết hạn
    # từ trước — mở kỳ quá khứ nghĩa là lượt quét sau lại thấy nó hết hạn, và
    # tổ chức đi qua chuỗi "gia hạn → hết hạn" hàng loạt trong một giờ.
    guard = 0
    while end <= at and guard < 1000:
        start, end = end, end + timedelta(days=span)
        guard += 1

    with system_scope("subscription: dat ky han"):
        _execute(
            "UPDATE tenant_subscriptions SET current_period_start = %s, "
            "current_period_end = %s, grace_until = NULL, last_reminder_days = NULL, "
            "trial_ends_at = COALESCE(trial_ends_at, %s) "
            "WHERE subscription_id = %s",
            (start, end, end if (first_period and trial_days > 0) else None,
             sub["subscription_id"]),
        )
    logger.info("[SUB] tenant=%s ky moi %s -> %s (%s ngay)",
                tenant_id, start.date(), end.date(), span)
    return open_subscription(tenant_id)


def _set_billing_status(tenant_id: str, status: str, *, reason: str) -> None:
    """Di chuyển `tenants.billing_status`. Đây là toàn bộ mặt cưỡng chế.

    Không viết một cơ chế khoá riêng: `plans.assert_writable` đã đứng ở mọi
    đường ghi và đọc đúng cột này. Một cơ chế thứ hai song song là cách chắc
    chắn để hai cái bất đồng, và lúc đó không ai biết cái nào đang có hiệu lực.
    """
    from app.storage.metadata_db import _execute
    from app.tenant_context import system_scope

    with system_scope("subscription: doi trang thai thanh toan"):
        _execute("UPDATE tenants SET billing_status = %s WHERE tenant_id = %s",
                 (status, str(tenant_id)))
    logger.info("[SUB] tenant=%s billing_status -> %s (%s)", tenant_id, status, reason)


def _reminder_due(days_left: int, already_sent: Optional[int]) -> Optional[int]:
    """Mốc nhắc cần gửi bây giờ, hoặc None.

    `already_sent` là mốc gần nhất ĐÃ gửi (7, 3, 1). Vì tác vụ quét chạy mỗi
    giờ, thiếu phép so này thì một người nhận 24 lá thư "còn 7 ngày" trong một
    ngày — đủ để họ lọc mọi thư của hệ thống vào thùng rác.
    """
    # Lấy mốc GẦN NHẤT còn áp dụng, không phải mốc khớp đầu tiên. `REMINDER_DAYS`
    # giảm dần, nên phải duyệt hết rồi mới chốt: thoát sớm ở mốc đầu tiên khớp
    # sẽ luôn chốt vào 7, và khi còn 0 ngày thì phép so `7 < 7` cho ra "đã gửi
    # rồi" — người dùng nhận đúng một thư ở mốc 7 ngày rồi không nghe gì nữa
    # cho tới lúc mất quyền ghi. Bộ test `test_moc_gan_hon_thi_gui_tiep` canh
    # đúng chỗ này.
    candidate: Optional[int] = None
    for mark in REMINDER_DAYS:            # 7, 3, 1 — giảm dần
        if days_left <= mark:
            candidate = mark
    if candidate is None:
        return None
    if already_sent is None or candidate < already_sent:
        return candidate
    return None


def _tenant_admin_emails(tenant_id: str) -> List[str]:
    """Địa chỉ nhận thư nhắc: quản trị viên CỦA TỔ CHỨC đó.

    Không gửi cho mọi thành viên. Một người xem không quyết định được việc gia
    hạn, nên thư tới họ chỉ là nhiễu — và nhiễu là thứ làm người ta ngừng đọc
    những thư thật sự cần đọc.
    """
    return [r["email"] for r in _tenant_admins(tenant_id) if r.get("email")]


def _tenant_admins(tenant_id: str) -> list:
    """Quản trị viên của tenant, kèm `id` — cần cả id để ghi thông báo.

    Tách ra khỏi `_tenant_admin_emails` khi thêm thông báo trong ứng dụng: hai
    kênh cùng hỏi một câu ("ai quyết định được việc gia hạn"), và hỏi hai lần
    bằng hai câu SQL là hai câu sẽ lệch nhau vào ngày định nghĩa "quản trị viên
    tenant" đổi.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("subscription: tim quan tri vien cua tenant"):
        return _fetch_all(
            "SELECT u.id, u.email FROM tenant_members m "
            "JOIN users u ON u.id = m.user_id "
            "WHERE m.tenant_id = %s AND m.role = 'admin' AND u.is_active",
            (str(tenant_id),),
        )


def _send_reminder(tenant_id: str, days_left: int, ends_at: datetime,
                   plan_name: str) -> int:
    """Gửi thư nhắc. Trả về số thư gửi được.

    Nuốt lỗi có chủ ý: SMTP hỏng KHÔNG được phép làm hỏng lượt quét. Nếu một
    ngoại lệ ở đây thoát ra, tác vụ chết giữa chừng và những tenant xếp sau
    trong danh sách không bao giờ được xét — một sự cố thư biến thành một sự cố
    vòng đời.
    """
    from app import email_service, notifications

    sent = 0
    for row in _tenant_admins(tenant_id):
        addr = row.get("email")
        if addr:
            try:
                email_service.send_subscription_reminder_email(
                    addr, tenant_id=tenant_id, plan_name=plan_name,
                    days_left=days_left, ends_at=ends_at)
                sent += 1
            except Exception as exc:
                logger.warning("[SUB] khong gui duoc thu nhac cho %s (%s: %s)",
                               addr, type(exc).__name__, exc)

        # Bản ghi bền trong ứng dụng, song song với thư.
        #
        # Thư rời khỏi hệ thống rồi không quay lại: không ai biết đã đọc chưa,
        # một địa chỉ sai là mất hẳn, và thư nhắc gia hạn là đúng loại thư mà bộ
        # lọc quảng cáo hay nuốt. Một tenant bị khoá mềm vì "không ai thấy thư"
        # là sự cố có thật và tránh được.
        #
        # `tenant_id` truyền TƯỜNG MINH: hàm này chạy trong tác vụ định kỳ dưới
        # `system_scope`, nên `current_tenant()` là rỗng và `notify()` sẽ từ
        # chối ghi. Đó là fail-closed đúng — và chỗ sửa là nói ra phạm vi, không
        # phải nới lỏng nó.
        notifications.notify(
            str(row["id"]), "subscription",
            "Gói dịch vụ sắp hết hạn",
            body=(f"Gói {plan_name} của tổ chức {tenant_id} còn {days_left} "
                  f"ngày, hết hạn {ends_at:%d/%m/%Y}."),
            link="/settings/billing",
            severity="warning" if days_left > 3 else "critical",
            tenant_id=str(tenant_id),
        )
    return sent


def sweep(now: Optional[datetime] = None) -> Dict[str, int]:
    """Một lượt quét toàn bộ đăng ký đang mở. Đây là thứ tác vụ định kỳ gọi.

    Trả về bản tóm tắt đếm được, để nhật ký nói ra việc gì đã xảy ra thay vì
    chỉ nói "đã chạy".

    **Không thu tiền.** `auto_renew` chỉ quyết định có mở kỳ mới hay không; việc
    thanh toán diễn ra ngoài hệ thống. Xem docstring đầu tệp.

    Thứ tự xét cho MỖI đăng ký, và thứ tự này quan trọng:

    1. chưa tới hạn  → có tới mốc nhắc nào chưa
    2. tới hạn, `auto_renew` → mở kỳ mới, trả trạng thái về `active`
    3. tới hạn, không tự gia hạn, chưa có `grace_until` → vào ân hạn (`past_due`)
    4. hết ân hạn    → `suspended`, tức CHỈ ĐỌC

    Một tenant hỏng không được làm hỏng lượt quét: mỗi đăng ký nằm trong `try`
    riêng. Bài học từ teardown của bộ test — một câu ném ngoại lệ giữa chừng thì
    mọi thứ xếp sau nó không bao giờ chạy tới.
    """
    from app import plans
    from app.storage.metadata_db import _execute, _fetch_all
    from app.tenant_context import system_scope

    at = now or _now()
    grace = _grace_days()
    summary = {"xet": 0, "nhac": 0, "gia_han": 0, "vao_an_han": 0, "khoa_mem": 0,
               "loi": 0}

    with system_scope("subscription: quet dang ky den han"):
        rows = _fetch_all(
            "SELECT * FROM tenant_subscriptions WHERE ended_at IS NULL "
            "ORDER BY tenant_id"
        )

    for row in rows:
        sub = dict(row)
        tenant_id = sub["tenant_id"]
        summary["xet"] += 1
        try:
            end = sub.get("current_period_end")
            if end is None:
                # Chưa có kỳ hạn: hoặc gói không kỳ hạn, hoặc đăng ký có từ
                # trước v3.14. `start_period` tự phân biệt hai trường hợp.
                start_period(tenant_id, now=at)
                continue

            if at < end:
                days_left = max(0, (end - at).days)
                mark = _reminder_due(days_left, sub.get("last_reminder_days"))
                if mark is not None:
                    plan = plans.get_plan(sub.get("plan_code") or "") or {}
                    n = _send_reminder(
                        tenant_id, mark, end,
                        str(plan.get("display_name") or plan.get("plan_code") or ""))
                    # Ghi mốc dù gửi được 0 thư: nếu không, một hộp thư hỏng làm
                    # lượt quét thử lại mỗi giờ cho tới khi hết kỳ.
                    with system_scope("subscription: ghi moc nhac"):
                        _execute(
                            "UPDATE tenant_subscriptions SET last_reminder_days = %s "
                            "WHERE subscription_id = %s",
                            (mark, sub["subscription_id"]))
                    summary["nhac"] += n
                continue

            # --- đã tới hạn ---
            if sub.get("auto_renew"):
                start_period(tenant_id, now=at)
                if plans.billing_status_of(tenant_id) in ("trialing", "past_due"):
                    _set_billing_status(tenant_id, "active", reason="gia han")
                summary["gia_han"] += 1
                continue

            grace_until = sub.get("grace_until")
            if grace_until is None:
                grace_until = end + timedelta(days=grace)
                with system_scope("subscription: vao an han"):
                    _execute(
                        "UPDATE tenant_subscriptions SET grace_until = %s "
                        "WHERE subscription_id = %s",
                        (grace_until, sub["subscription_id"]))
                _set_billing_status(tenant_id, "past_due", reason="het ky, khong tu gia han")
                summary["vao_an_han"] += 1
                continue

            if at >= grace_until:
                if plans.billing_status_of(tenant_id) != "suspended":
                    _set_billing_status(tenant_id, "suspended", reason="het an han")
                    summary["khoa_mem"] += 1
        except Exception as exc:
            summary["loi"] += 1
            logger.error("[SUB] loi khi xet tenant=%s (%s: %s)",
                         tenant_id, type(exc).__name__, exc)

    logger.info("[SUB] quet xong: %s", summary)
    return summary


def set_auto_renew(tenant_id: str, enabled: bool) -> Dict[str, Any]:
    """Bật/tắt tự gia hạn. Đây là đường "tự huỷ" của người dùng.

    Tắt tự gia hạn KHÔNG đóng đăng ký ngay: kỳ đã trả tiền vẫn chạy hết. Đóng
    ngay khi người ta bấm huỷ là lấy đi phần họ đã trả.
    """
    from app.storage.metadata_db import _execute
    from app.tenant_context import system_scope

    sub = open_subscription(tenant_id)
    if sub is None:
        raise SubscriptionError("Tổ chức này chưa có đăng ký nào đang mở.",
                                code="no_subscription", status_code=404)
    with system_scope("subscription: doi co tu gia han"):
        _execute("UPDATE tenant_subscriptions SET auto_renew = %s "
                 "WHERE subscription_id = %s", (bool(enabled), sub["subscription_id"]))
    logger.info("[SUB] tenant=%s auto_renew -> %s", tenant_id, bool(enabled))
    return open_subscription(tenant_id) or {}


def describe(tenant_id: str) -> Dict[str, Any]:
    """Bản tóm tắt cho giao diện: còn bao nhiêu ngày, đang ở trạng thái nào.

    `days_left` là None khi gói không có kỳ hạn — KHÔNG phải 0. Giao diện vẽ
    "còn 0 ngày" cho một gói vĩnh viễn là một câu sai đủ để người dùng gọi điện.
    """
    from app import plans

    sub = open_subscription(tenant_id)
    status = plans.billing_status_of(tenant_id)
    if sub is None:
        return {"has_subscription": False, "billing_status": status,
                "days_left": None, "auto_renew": None, "current_period_end": None,
                "grace_until": None, "read_only": status not in
                plans.WRITABLE_BILLING_STATUSES}

    end = sub.get("current_period_end")
    days_left = None if end is None else max(0, (end - _now()).days)
    return {
        "has_subscription": True,
        "plan_code": sub.get("plan_code"),
        "billing_status": status,
        "auto_renew": bool(sub.get("auto_renew")),
        "current_period_start": sub.get("current_period_start"),
        "current_period_end": end,
        "grace_until": sub.get("grace_until"),
        "trial_ends_at": sub.get("trial_ends_at"),
        "days_left": days_left,
        # Đưa xuống dưới dạng một cờ đã tính sẵn: mỗi màn hình tự suy ra từ
        # danh sách trạng thái là mỗi màn hình một cách hiểu.
        "read_only": status not in plans.WRITABLE_BILLING_STATUSES,
    }


def open_subscription_for(tenant_id: str, plan_code: str, *,
                          changed_by: Optional[str] = None,
                          note: str = "") -> Dict[str, Any]:
    """Mở một đăng ký mới và đặt kỳ hạn ngay. Dùng ở đường tạo tenant/đổi gói.

    Đóng đăng ký cũ TRƯỚC khi mở cái mới: `uq_tenant_subscriptions_open` chỉ
    cho một dòng mở cho mỗi tenant, và làm ngược thứ tự sẽ đụng chỉ mục.
    """
    from app.storage.metadata_db import _execute
    from app.tenant_context import system_scope

    with system_scope("subscription: mo dang ky moi"):
        _execute(
            "UPDATE tenant_subscriptions SET ended_at = NOW() "
            "WHERE tenant_id = %s AND ended_at IS NULL", (str(tenant_id),))
        _execute(
            "INSERT INTO tenant_subscriptions "
            "(subscription_id, tenant_id, plan_code, status, changed_by, note) "
            "VALUES (%s, %s, %s, 'active', %s, %s)",
            (str(uuid.uuid4()), str(tenant_id), plan_code, changed_by, note))
    return start_period(tenant_id, plan_code=plan_code) or {}
