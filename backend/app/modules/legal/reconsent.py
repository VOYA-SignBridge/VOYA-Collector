"""Side effects triggered when a legal document requires fresh consent."""

from __future__ import annotations

import logging

from app.modules.support import notifications
from app.storage.metadata_db import _fetch_all


logger = logging.getLogger(__name__)


def notify_active_users(kind: str, version: str) -> int:
    """Notify active users in the current tenant, without failing publication.

    Legal documents apply platform-wide, while notification rows are tenant
    scoped.  The request's existing tenant scope therefore deliberately limits
    both the user lookup and every notification written by ``notify_many``.
    """
    try:
        rows = _fetch_all("SELECT id FROM users WHERE is_active")
    except Exception as exc:
        logger.warning(
            "[LEGAL] khong doc duoc danh sach nguoi dung de bao: %s",
            type(exc).__name__,
        )
        return 0

    return notifications.notify_many(
        [str(row["id"]) for row in rows],
        kind="consent",
        title="Văn bản pháp lý mới cần bạn đồng ý lại",
        body=(
            f"{kind} — bản {version}. Chưa ký lại thì một số thao tác "
            "sẽ bị tạm dừng."
        ),
        link="/settings/consents",
        severity="warning",
    )
