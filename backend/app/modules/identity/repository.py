"""PostgreSQL persistence for identity accounts."""

from typing import Any, Callable, Dict, Optional

from psycopg2.extras import RealDictCursor

from app.infrastructure.database.connection import connect_postgres


ConnectionFactory = Callable[[], Any]


def get_connection():
    return connect_postgres(connect_timeout=5)


def normalize_login(identifier: str) -> str:
    return (identifier or "").strip().lower()


def row_to_user(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "username": row["username"] or "",
        "email": row["email"] or "",
        "password_hash": row["password_hash"] or "",
        "is_active": bool(row.get("is_active", True)),
        "is_admin": bool(row.get("is_admin", False)),
        "created_at": row.get("created_at"),
    }


def find_user_by_id(
    user_id: str,
    connection_factory: ConnectionFactory = get_connection,
) -> Optional[Dict[str, Any]]:
    conn = connection_factory()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, username, email, password_hash, is_active, is_admin, created_at
                    FROM users
                    WHERE id = %s
                    """,
                    (user_id,),
                )
                return row_to_user(cur.fetchone())
    finally:
        conn.close()


def find_user_by_login(
    identifier: str,
    connection_factory: ConnectionFactory = get_connection,
) -> Optional[Dict[str, Any]]:
    login = normalize_login(identifier)
    if not login:
        return None

    conn = connection_factory()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, username, email, password_hash, is_active, is_admin, created_at
                    FROM users
                    WHERE lower(username) = %s OR lower(email) = %s
                    LIMIT 1
                    """,
                    (login, login),
                )
                return row_to_user(cur.fetchone())
    finally:
        conn.close()


def insert_user(
    *,
    user_id: str,
    username: str,
    email: str,
    password_hash: str,
    is_admin: bool,
    connection_factory: ConnectionFactory = get_connection,
) -> Dict[str, Any]:
    conn = connection_factory()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO users (id, username, email, password_hash, is_active, is_admin)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, username, email, password_hash, is_active, is_admin, created_at
                    """,
                    (
                        user_id,
                        username,
                        email,
                        password_hash,
                        True,
                        bool(is_admin),
                    ),
                )
                return row_to_user(cur.fetchone()) or {}
    finally:
        conn.close()
