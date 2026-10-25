"""Bootstrap the optional administrator configured through environment settings."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("db.init")


def bootstrap_admin_user() -> None:
    """Create the configured admin account when it does not already exist."""
    from app.config import settings

    admin_username = getattr(settings, "admin_username", "").strip()
    admin_password = getattr(settings, "admin_password", "").strip()
    if not admin_username or not admin_password:
        logger.debug(
            "[BOOTSTRAP_ADMIN] ADMIN_USERNAME or ADMIN_PASSWORD not configured, skipping"
        )
        return

    try:
        from app.modules.identity.passwords import get_password_hash
        from app.modules.saas.tenant_context import system_scope
        from app.modules.saas.tenancy import DEFAULT_TENANT_ID
        from app.storage.metadata_db import _column_exists, _execute, _fetch_all

        # Đây là bootstrap của NỀN TẢNG, chạy trước khi có request/tenant. Mọi
        # truy vấn phải đi qua metadata_db trong system_scope để apply_scope đặt
        # GUC cho RLS; repository danh tính mở connection riêng nên không nhận
        # được scope và luôn nhìn thấy 0 dòng rồi bị WITH CHECK chặn khi INSERT.
        with system_scope("bootstrap configured platform administrator"):
            if not _column_exists("users", "id"):
                logger.warning("[BOOTSTRAP_ADMIN] users table does not exist yet, skipping")
                return

            login = admin_username.lower()
            if _fetch_all(
                "SELECT 1 FROM users "
                "WHERE lower(username) = %s OR lower(email) = %s LIMIT 1",
                (login, login),
            ):
                logger.info(
                    "[BOOTSTRAP_ADMIN] admin user '%s' already exists, skipping",
                    admin_username,
                )
                return

            admin_id = str(uuid.uuid4())
            _execute(
                """
                INSERT INTO users(
                    id, username, email, password_hash, is_active, is_admin,
                    created_at, tenant_id
                )
                VALUES(%s, %s, %s, %s, true, true, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    admin_id,
                    admin_username,
                    f"{admin_username}@admin.local",
                    get_password_hash(admin_password),
                    datetime.now(timezone.utc),
                    DEFAULT_TENANT_ID,
                ),
            )
        logger.info("[BOOTSTRAP_ADMIN] admin user '%s' ensured", admin_username)
    except Exception as exc:
        logger.error("[BOOTSTRAP_ADMIN] failed to create admin user: %s", exc)
