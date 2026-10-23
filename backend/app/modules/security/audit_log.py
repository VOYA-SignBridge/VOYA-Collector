"""Best-effort Redis security audit log for administrative actions."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from app.infrastructure.redis.connection import get_activity_client


logger = logging.getLogger("activity")

_NOTIFY_TARGET = {
    "lock_user": ("critical", "Tài khoản của bạn đã bị khoá"),
    "force_logout": ("warning", "Mọi phiên đăng nhập đã bị thu hồi"),
    "warn_user": ("warning", "Quản trị viên gửi một cảnh báo"),
    "password.changed": ("success", "Mật khẩu đã được đổi"),
    "password.change_rejected": ("warning", "Có người nhập sai mật khẩu hiện tại"),
    "2fa.disabled": ("critical", "Xác thực hai bước đã bị tắt"),
    "2fa.recovery_codes_regenerated": ("warning", "Mã khôi phục đã được cấp lại"),
}


def _notify_affected_user(action: str, target: str, actor: str, reason: str) -> None:
    entry = _NOTIFY_TARGET.get(action)
    if not entry or not (target or "").strip():
        return
    severity, title = entry
    body = f"Do {actor} thực hiện." if actor else ""
    if reason:
        body = (body + f" Lý do: {reason}").strip()
    try:
        from app.modules.support import notifications

        notifications.notify(
            target,
            "security",
            title,
            body=body[:500],
            link="/settings/security",
            severity=severity,
        )
    except Exception as exc:
        logger.warning(
            "[ACTIVITY] khong ghi duoc thong bao an ninh %s: %s",
            action,
            type(exc).__name__,
        )


def log_security_event(
    action: str,
    actor: str = "",
    target: str = "",
    reason: str = "",
    extra: Optional[Dict[str, Any]] = None,
    actor_user: Optional[Dict[str, Any]] = None,
    request: Any = None,
) -> None:
    # Keep a durable audit record as well as the short Redis activity feed.
    try:
        from app.modules.security import audit

        detail = dict(extra or {})
        if reason:
            detail["reason"] = reason
        audit.record(
            f"security.{action}",
            actor=actor_user or ({"username": actor} if actor else None),
            target_type="security",
            target_id=target or None,
            detail=detail or None,
            request=request,
        )
    except Exception:
        pass

    _notify_affected_user(action, target, actor, reason)

    client = get_activity_client()
    if client is None:
        return
    try:
        entry = {
            "ts": time.time(),
            "action": action,
            "actor": actor,
            "target": target,
            "reason": reason,
        }
        if extra:
            entry.update(extra)
        client.lpush("sec:log", json.dumps(entry))
        client.ltrim("sec:log", 0, 499)
    except Exception:
        pass


def list_security_log(limit: int = 100) -> List[Dict[str, Any]]:
    client = get_activity_client()
    if client is None:
        return []
    try:
        output = []
        for raw in client.lrange("sec:log", 0, max(0, limit - 1)):
            try:
                output.append(json.loads(raw))
            except Exception:
                pass
        return output
    except Exception:
        return []
