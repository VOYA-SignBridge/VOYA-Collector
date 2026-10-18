from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi import HTTPException


class FakeCursor:
    def __init__(self, *, rows=None, row=None):
        self.rows = rows or []
        self.row = row
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        self.executions.append((" ".join(query.split()), params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False
        self.cursor_factory = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self, cursor_factory=None):
        self.cursor_factory = cursor_factory
        return self._cursor

    def close(self):
        self.closed = True


def test_list_users_preserves_query_serialization_and_security_state(monkeypatch):
    from app.modules.admin import user_service

    user_id = UUID("12345678-1234-5678-1234-567812345678")
    created_at = datetime(2026, 10, 18, 8, 30, tzinfo=timezone.utc)
    cursor = FakeCursor(rows=[{
        "id": user_id,
        "username": "alice",
        "email": "alice@example.com",
        "is_active": True,
        "is_admin": False,
        "created_at": created_at,
    }])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(user_service, "connect_postgres", lambda: connection)
    monkeypatch.setattr(
        user_service,
        "list_locked_users",
        lambda: {str(user_id): {"reason": "review", "until": 1234}},
    )
    monkeypatch.setattr(user_service, "list_warned_users", lambda: {str(user_id)})

    users = user_service.list_users()

    assert connection.closed is True
    assert cursor.executions == [(
        "SELECT id, username, email, is_active, is_admin, created_at "
        "FROM users ORDER BY created_at DESC",
        None,
    )]
    assert users == [{
        "id": str(user_id),
        "username": "alice",
        "email": "alice@example.com",
        "is_active": True,
        "is_admin": False,
        "created_at": created_at.isoformat(),
        "locked": True,
        "lock_reason": "review",
        "lock_until": 1234,
        "has_warning": True,
    }]


def test_set_user_admin_role_preserves_update_contract(monkeypatch):
    from app.modules.admin import user_service

    user_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    cursor = FakeCursor(row={"id": user_id, "username": "bob", "is_admin": True})
    connection = FakeConnection(cursor)
    monkeypatch.setattr(user_service, "connect_postgres", lambda: connection)

    updated = user_service.set_user_admin_role(str(user_id), True)

    assert connection.closed is True
    assert cursor.executions == [(
        "UPDATE users SET is_admin = %s WHERE id = %s RETURNING id, username, is_admin",
        (True, str(user_id)),
    )]
    assert updated == {"id": str(user_id), "username": "bob", "is_admin": True}


def test_admin_router_keeps_http_validation_and_status_mapping(monkeypatch):
    from app.routers import admin

    called = []
    monkeypatch.setattr(admin, "set_user_admin_role", lambda user_id, value: called.append((user_id, value)))

    with pytest.raises(HTTPException) as self_demote:
        admin.update_user_role(
            "admin-1",
            admin.UserRoleUpdate(is_admin=False),
            {"id": "admin-1", "is_admin": True},
        )
    assert self_demote.value.status_code == 400
    assert called == []

    with pytest.raises(HTTPException) as missing:
        admin.update_user_role(
            "missing",
            admin.UserRoleUpdate(is_admin=True),
            {"id": "admin-1", "is_admin": True},
        )
    assert missing.value.status_code == 404
    assert called == [("missing", True)]
