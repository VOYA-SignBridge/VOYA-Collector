import hashlib

import pytest
from fastapi import HTTPException


def test_legacy_token_hashes_are_identity_module_aliases():
    from app import auth as legacy
    from app.modules.identity.password_reset import hash_reset_token
    from app.modules.identity.sessions import hash_refresh_token

    expected = hashlib.sha256(b"opaque-token").hexdigest()

    assert legacy._hash_reset_token is hash_reset_token
    assert legacy._hash_token is hash_refresh_token
    assert legacy._hash_reset_token("opaque-token") == expected
    assert legacy._hash_token("opaque-token") == expected


def test_legacy_password_reset_wrapper_preserves_injection_points(monkeypatch):
    from app import auth as legacy

    lookup = lambda identifier: {"id": identifier}
    connection_factory = lambda: object()
    captured = {}

    def fake_issue(identifier, **kwargs):
        captured.update(identifier=identifier, **kwargs)
        return ({"id": "user-1"}, "reset-token")

    monkeypatch.setattr(legacy, "_fetch_user_by_login", lookup)
    monkeypatch.setattr(legacy, "_get_conn", connection_factory)
    monkeypatch.setattr(legacy, "issue_password_reset", fake_issue)

    result = legacy.request_password_reset("User@Example.com")

    assert result == ({"id": "user-1"}, "reset-token")
    assert captured == {
        "identifier": "User@Example.com",
        "user_lookup": lookup,
        "connection_factory": connection_factory,
    }


def test_legacy_refresh_rotation_wrapper_preserves_injection_points(monkeypatch):
    from app import auth as legacy

    lookup = lambda user_id: {"id": user_id}
    connection_factory = lambda: object()
    captured = {}

    def fake_rotate(raw_token, **kwargs):
        captured.update(raw_token=raw_token, **kwargs)
        return ({"id": "user-1"}, "replacement-token")

    monkeypatch.setattr(legacy, "_fetch_user_by_id", lookup)
    monkeypatch.setattr(legacy, "_get_conn", connection_factory)
    monkeypatch.setattr(legacy, "rotate_refresh_session", fake_rotate)

    result = legacy.rotate_refresh_token("refresh-token")

    assert result == ({"id": "user-1"}, "replacement-token")
    assert captured == {
        "raw_token": "refresh-token",
        "user_lookup": lookup,
        "connection_factory": connection_factory,
    }


def test_session_short_circuits_do_not_open_database_connections():
    from app.modules.identity.sessions import (
        revoke_refresh_session,
        rotate_refresh_session,
    )

    def unexpected_connection():
        raise AssertionError("database connection should not be opened")

    assert rotate_refresh_session(
        "",
        user_lookup=lambda user_id: {"id": user_id},
        connection_factory=unexpected_connection,
    ) is None
    assert revoke_refresh_session(
        "",
        connection_factory=unexpected_connection,
    ) is None


def test_password_reset_validation_precedes_database_access():
    from app.modules.identity.password_reset import apply_password_reset

    def unexpected_connection():
        raise AssertionError("database connection should not be opened")

    with pytest.raises(HTTPException) as exc_info:
        apply_password_reset(
            "reset-token",
            "short",
            connection_factory=unexpected_connection,
        )

    assert exc_info.value.status_code == 400
