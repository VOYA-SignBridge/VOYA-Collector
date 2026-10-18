"""Administrative user queries and role updates.

This module owns the database transaction and response-shaping work. HTTP
authorization, self-demotion validation, and status-code mapping remain in the
admin router.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from app.infrastructure.database.connection import connect_postgres
from app.modules.security.account_controls import list_locked_users, list_warned_users


def list_users() -> List[Dict[str, Any]]:
    """Return users enriched with current Redis lock and warning state."""
    connection = connect_postgres()
    try:
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT id, username, email, is_active, is_admin, created_at
                    FROM users
                    ORDER BY created_at DESC
                    """
                )
                users = cursor.fetchall()
    finally:
        connection.close()

    locked_users = list_locked_users()
    warned_users = list_warned_users()
    output: List[Dict[str, Any]] = []
    for row in users:
        user = dict(row)
        user["id"] = str(user["id"])
        if user.get("created_at"):
            user["created_at"] = user["created_at"].isoformat()
        lock = locked_users.get(user["id"])
        user["locked"] = bool(lock)
        user["lock_reason"] = (lock or {}).get("reason", "")
        user["lock_until"] = (lock or {}).get("until", 0)
        user["has_warning"] = user["id"] in warned_users
        output.append(user)
    return output


def set_user_admin_role(user_id: str, is_admin: bool) -> Optional[Dict[str, Any]]:
    """Update a user's admin flag and return the normalized updated row."""
    connection = connect_postgres()
    try:
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "UPDATE users SET is_admin = %s WHERE id = %s "
                    "RETURNING id, username, is_admin",
                    (is_admin, user_id),
                )
                updated = cursor.fetchone()
    finally:
        connection.close()

    if not updated:
        return None
    return {
        "id": str(updated["id"]),
        "username": updated["username"],
        "is_admin": updated["is_admin"],
    }
