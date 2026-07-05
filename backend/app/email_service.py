"""Minimal outbound email support (stdlib smtplib, no extra dependency).

If SMTP isn't configured (local/dev), emails are logged instead of sent so
the password-reset flow stays testable without a real mail server.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger("email")


def _send(to_email: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        logger.warning("[EMAIL] SMTP not configured — would send to %s\nSubject: %s\n%s", to_email, subject, body)
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user or "no-reply@voya-collector.local"
    msg["To"] = to_email

    try:
        if settings.smtp_use_tls:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                server.starttls()
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        logger.info("[EMAIL] Sent %r to %s", subject, to_email)
    except Exception as exc:
        # Best-effort: forgot-password already returns a generic response to
        # the client regardless of outcome, so a delivery failure here should
        # not surface as a 500 — just log it for ops to investigate.
        logger.error("[EMAIL] Failed to send %r to %s: %s", subject, to_email, exc)


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
    _send(to_email, subject, body)
