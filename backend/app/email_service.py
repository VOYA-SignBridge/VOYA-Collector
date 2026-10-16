"""Minimal outbound email support (stdlib smtplib, no extra dependency).

If SMTP isn't configured (local/dev), *some* messages are logged instead of
sent so the password-reset flow stays testable without a real mail server.

Which ones is not a detail — it is the whole point of the `loggable` flag on
`_send`. A password-reset link is a 32-byte single-use token, and printing one
into a dev log trades a little safety for a lot of convenience. A six-digit OTP
is not comparable: it is weak enough that the only thing protecting it is the
fact it exists in exactly two places, the recipient's inbox and nowhere else.
Logging it puts it in Loki, which more people can read than the database.

`app/sms_service.py` refuses this exact shortcut and says why. Until now the
email path quietly took it — `_send` logged the whole body, and the body of a
verification email IS the code. So a deployment that lost SMTP_HOST would not
have failed; it would have kept "working" while writing every OTP to disk.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from typing import Optional

from app.config import settings

logger = logging.getLogger("email")


def _host_port() -> tuple[str, int]:
    """Resolve (host, port) tolerating a combined 'host:port' in SMTP_HOST.

    The same SMTP_HOST env var is shared with Grafana, which expects the
    'smtp.gmail.com:587' form. Passing that whole string to smtplib would make
    it DNS-resolve a host literally named 'smtp.gmail.com:587' and every send
    would fail. If a port is baked into the host, split it out and let it win.
    """
    host = (settings.smtp_host or "").strip()
    port = settings.smtp_port
    if host.count(":") == 1:  # 'host:port' (ignore IPv6 which has multiple ':')
        h, _, p = host.partition(":")
        if p.isdigit():
            host, port = h, int(p)
    return host, port


class EmailNotConfigured(RuntimeError):
    """No SMTP host, and this message is one that must never be logged."""


def _send(to_email: str, subject: str, body: str, *, loggable: bool) -> None:
    """Send a message, or fall back to a log only when `loggable` allows it.

    `loggable` has no default on purpose. Adding a third sender should force
    the author to answer "may this body appear in a log file?" rather than
    inherit an answer chosen for a different message.
    """
    if not settings.smtp_host:
        if not loggable:
            # Refused, not degraded. The alternative — pretending to send —
            # surfaces as "the code never arrives" long after the deploy that
            # caused it, and the caller can turn this into a 503 the person
            # sees at the moment they ask.
            raise EmailNotConfigured(
                "Email chưa được cấu hình trên hệ thống này."
            )
        logger.warning("[EMAIL] SMTP not configured — would send to %s\nSubject: %s\n%s", to_email, subject, body)
        return

    host, port = _host_port()

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user or "no-reply@voya-collector.local"
    msg["To"] = to_email

    try:
        if settings.smtp_use_tls:
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.starttls()
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(host, port, timeout=10) as server:
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        logger.info("[EMAIL] Sent %r to %s", subject, to_email)
    except Exception as exc:
        # Best-effort: forgot-password already returns a generic response to
        # the client regardless of outcome, so a delivery failure here should
        # not surface as a 500 — just log it for ops to investigate.
        logger.error("[EMAIL] Failed to send %r to %s: %s", subject, to_email, exc)


def send_verification_code_email(to_email: str, code: str, purpose: str) -> None:
    """Deliver a one-time code.

    `loggable=False` is the load-bearing argument: with no SMTP host this
    RAISES instead of writing the code to a log. Every other path here logs
    the subject and the address only — never the body, which is the one place
    the code appears.
    """
    from app.config import settings as _settings

    what = {
        "verify_email": "xác minh địa chỉ email",
        "verify_phone": "xác minh số điện thoại",
        "reset_password": "đặt lại mật khẩu",
    }.get(purpose, "xác minh")

    subject = f"Mã xác minh VOYA-Collector: {what}"
    body = (
        f"Mã {what} của bạn là:\n\n"
        f"    {code}\n\n"
        f"Mã có hiệu lực trong {_settings.otp_ttl_minutes} phút và chỉ dùng được một lần.\n"
        "Nếu bạn không yêu cầu điều này, hãy bỏ qua email này — "
        "không có thay đổi nào được thực hiện.\n"
    )
    _send(to_email, subject, body, loggable=False)


#: What a role is called to the person being offered it. Kept here rather than
#: imported from the SPA's `ROLE_LABEL`: an email is read outside the app, often
#: by someone who has never seen it, so each name has to be spelled out.
#:
#: `viewer` vẫn còn ở đây dù vai đó đã nghỉ (xem
#: `authorization/catalog.py::RETIRED_BUILTIN_ROLES`), vì một lời mời cũ đã gửi
#: đi vẫn có thể được mở lại; bảng này chỉ dịch tên sang tiếng người, nó không
#: cấp gì.
_ROLE_IN_WORDS = {
    "admin": "quản trị viên",
    "contributor": "người đóng góp dữ liệu",
    "annotator": "người gán nhãn",
    "viewer": "người xem",
}

#: Lời mời không kèm vai. Phải nói ra, không được để trống: một câu "với vai trò
#: ." là thứ làm người nhận tưởng thư bị lỗi và không bấm vào liên kết.
_NO_ROLE_IN_WORDS = "thành viên (chưa được cấp vai cụ thể)"


def send_invitation_email(
    to_email: str, *, tenant_name: str, role: Optional[str],
    accept_url: str, expires_hours: int
) -> None:
    """Invite someone into a tenant. Raises if the message cannot be delivered.

    `loggable=False`, unlike the password-reset link next door, and the two are
    worth comparing because the tokens are the same strength. The difference is
    what happens on the failure path. A reset is asked for by a person waiting
    at a screen; with no SMTP the log is the only way that flow can be exercised
    at all. An invitation is issued by an admin who is holding the link already
    — `create_invitation` returns it — so writing it to Loki buys nothing and
    costs a tenant-joining credential sitting in a store more people can read
    than the database.

    So this raises, the caller turns it into "sent: no", and the admin copies
    the link by hand. The invitation itself is already minted and stays valid.
    """
    what = _NO_ROLE_IN_WORDS if not role else _ROLE_IN_WORDS.get(role, role)
    subject = f"Lời mời tham gia {tenant_name} trên VOYA-Collector"
    body = (
        f"Bạn được mời tham gia tổ chức {tenant_name} trên VOYA-Collector "
        f"với vai trò {what}.\n\n"
        "Mở liên kết sau để tạo tài khoản và nhận lời mời:\n\n"
        f"{accept_url}\n\n"
        f"Liên kết có hiệu lực trong {expires_hours} giờ và chỉ dùng được một lần.\n"
        "Nếu bạn không mong đợi lời mời này, hãy bỏ qua email — "
        "không có tài khoản nào được tạo cho tới khi bạn tự mở liên kết.\n"
    )
    _send(to_email, subject, body, loggable=False)


def send_subscription_reminder_email(
    to_email: str, *, tenant_id: str, plan_name: str, days_left: int,
    ends_at, ) -> None:
    """Nhắc trước hạn. Gửi cho quản trị viên của tổ chức, ở mốc 7 / 3 / 1 ngày.

    Thư này cố ý **không** doạ mất dữ liệu, vì hết hạn không làm mất dữ liệu:
    tổ chức chuyển sang chỉ-đọc và đường xuất dữ liệu vẫn chạy. Viết sai điều
    đó là làm người đọc hoảng vì một việc hệ thống không làm — và lần sau họ
    sẽ không tin thư nào nữa.

    `loggable=False`: nội dung không mang bí mật nào, nhưng nó mang tên tổ chức
    và mốc hết hạn, tức thông tin thương mại của một khách hàng cụ thể. Nhật ký
    có nhiều người đọc hơn hộp thư.
    """
    when = ends_at.strftime("%d/%m/%Y") if hasattr(ends_at, "strftime") else str(ends_at)
    subject = f"Gói {plan_name} của {tenant_id} còn {days_left} ngày"
    body = (
        f"Gói dịch vụ \"{plan_name}\" của tổ chức {tenant_id} sẽ hết hạn vào "
        f"ngày {when} — còn {days_left} ngày.\n\n"
        "Nếu tự động gia hạn đang bật, kỳ mới sẽ mở ngay khi kỳ này kết thúc và "
        "bạn không cần làm gì.\n\n"
        "Nếu không, sau khi hết hạn tổ chức sẽ chuyển sang chế độ CHỈ ĐỌC: "
        "không thêm được dữ liệu mới, nhưng toàn bộ dữ liệu đã có vẫn còn nguyên "
        "và bạn vẫn tải về được bất cứ lúc nào.\n\n"
        "Xem và thay đổi ở trang \"Tổ chức của tôi\".\n"
    )
    _send(to_email, subject, body, loggable=False)


def send_password_reset_email(to_email: str, username: str, reset_link: str) -> None:
    subject = "Đặt lại mật khẩu VOYA-Collector"
    body = (
        f"Xin chào {username},\n\n"
        "Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn.\n"
        f"Nhấp vào liên kết sau để đặt mật khẩu mới (hết hạn sau "
        f"{settings.password_reset_token_expire_minutes} phút):\n\n"
        f"{reset_link}\n\n"
        "Nếu bạn không yêu cầu điều này, vui lòng bỏ qua email này — mật khẩu của bạn sẽ không thay đổi.\n"
    )
    # Loggable: this is the documented dev fallback (.env.example says so), and
    # the link carries a high-entropy single-use token with a 30-minute life.
    _send(to_email, subject, body, loggable=True)


# ---------------------------------------------------------------------------
# Hỗ trợ — thư cho người trực
#
# Vì sao phiếu hỗ trợ phải có thư, khi trong ứng dụng đã có chuông
# ------------------------------------------------------------------
# Chuông chỉ kêu với người ĐANG mở ứng dụng. Người trực phần lớn thời gian
# không mở nó, nên một phiếu gửi lúc 21 giờ nằm im tới sáng hôm sau mà không
# ai biết là nó đã nằm im. Thư đi tới chỗ người ta thật sự có mặt.
#
# Cả hai thư dưới đây đều `loggable=True`. Chúng KHÔNG chở nội dung phiếu —
# chỉ tiêu đề, người gửi và số lượng. Nội dung trao đổi hỗ trợ là dữ liệu của
# tenant và không được rơi vào nhật ký chung; xem `docs/06-operations/OBSERVABILITY_PLAN.md`.
# ---------------------------------------------------------------------------
def send_support_ticket_email(
    to_email: str, *, ticket_id: str, subject: str, category: str,
    requester: str, link: str,
) -> None:
    """Báo một phiếu MỚI.

    Tiêu đề thư mang thẳng tiêu đề phiếu: người trực lọc hộp thư bằng dòng
    tiêu đề, và "Có phiếu hỗ trợ mới" lặp lại năm mươi lần thì không lọc được
    gì. Phần thân KHÔNG chép nội dung người dùng viết — ai cần đọc thì bấm
    vào, và lúc đó việc đọc có kiểm soát truy cập.
    """
    mail_subject = f"[Hỗ trợ] {subject}"
    body = (
        f"{requester} vừa mở một phiếu hỗ trợ.\n\n"
        f"Tiêu đề: {subject}\n"
        f"Phân loại: {category}\n"
        f"Mã phiếu: {ticket_id}\n\n"
        f"Mở hội thoại: {link}\n\n"
        "Trợ lý tự động đã trả lời ngay để người dùng không phải chờ trắng, "
        "nhưng nó chỉ xử lý được vài tình huống quen thuộc.\n"
    )
    _send(to_email, mail_subject, body, loggable=True)


def send_support_backlog_email(
    to_email: str, *, waiting: int, oldest_hours: float, unanswered_messages: int,
    threshold_hours: int, threshold_messages: int, link: str,
) -> None:
    """Báo TỒN ĐỌNG: có phiếu chờ quá lâu, hoặc quá nhiều lời nhắn chưa trả.

    Khác thư phiếu-mới ở một điểm quan trọng: thư kia báo một SỰ KIỆN, thư này
    báo một TRẠNG THÁI. Nên nó luôn nói con số hiện tại — bao nhiêu phiếu đang
    chờ, cái cũ nhất chờ bao lâu — chứ không chỉ nói "có tồn đọng". Một cảnh báo
    không kèm số lượng thì người đọc vẫn phải mở hệ thống ra mới biết nên bỏ dở
    việc đang làm hay không.
    """
    reasons = []
    if oldest_hours >= threshold_hours:
        reasons.append(f"phiếu cũ nhất đã chờ {oldest_hours:.1f} giờ (ngưỡng {threshold_hours} giờ)")
    if unanswered_messages >= threshold_messages:
        reasons.append(
            f"{unanswered_messages} lời nhắn chưa được trả lời (ngưỡng {threshold_messages})")

    mail_subject = f"[Hỗ trợ] {waiting} phiếu đang chờ người trực"
    body = (
        "Kênh hỗ trợ đang có tồn đọng.\n\n"
        f"Phiếu đang chờ trả lời:      {waiting}\n"
        f"Phiếu cũ nhất chờ:           {oldest_hours:.1f} giờ\n"
        f"Lời nhắn chưa được trả lời:  {unanswered_messages}\n\n"
        "Lý do gửi thư này: " + "; ".join(reasons) + ".\n\n"
        f"Hàng đợi: {link}\n\n"
        "Thư này chỉ gửi lại khi tình trạng còn kéo dài, không gửi mỗi lượt kiểm tra.\n"
    )
    _send(to_email, mail_subject, body, loggable=True)
