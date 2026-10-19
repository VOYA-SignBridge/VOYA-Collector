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
        from app.modules.identity.repository import find_user_by_login
        from app.storage.metadata_db import _column_exists, _execute

        if not _column_exists("users", "id"):
            logger.warning("[BOOTSTRAP_ADMIN] users table does not exist yet, skipping")
            return

        if find_user_by_login(admin_username):
            logger.info(
                "[BOOTSTRAP_ADMIN] admin user '%s' already exists, skipping",
                admin_username,
            )
            return

        admin_id = str(uuid.uuid4())
        _execute(
            """
            INSERT INTO users(id, username, email, password_hash, is_active, is_admin, created_at)
            VALUES(%s, %s, %s, %s, true, true, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                admin_id,
                admin_username,
                f"{admin_username}@admin.local",
                get_password_hash(admin_password),
                datetime.now(timezone.utc),
            ),
        )
        logger.info("[BOOTSTRAP_ADMIN] admin user '%s' created successfully", admin_username)
    except Exception as exc:
        logger.error("[BOOTSTRAP_ADMIN] failed to create admin user: %s", exc)
