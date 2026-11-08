import hashlib

import pytest
from fastapi import HTTPException


def test_token_hashes_share_the_expected_opaque_token_contract():
    from app.modules.identity.password_reset import hash_reset_token
    from app.modules.identity.sessions import hash_refresh_token

    expected = hashlib.sha256(b"opaque-token").hexdigest()

    assert hash_reset_token("opaque-token") == expected
    assert hash_refresh_token("opaque-token") == expected


def test_password_reset_service_preserves_injection_points(monkeypatch):
    from app.modules.identity import service

    lookup = lambda identifier: {"id": identifier}
    connection_factory = lambda: object()
    captured = {}

    def fake_issue(identifier, **kwargs):
        captured.update(identifier=identifier, **kwargs)
        return ({"id": "user-1"}, "reset-token")

    monkeypatch.setattr(service, "find_user_by_login", lookup)
    monkeypatch.setattr(service, "get_connection", connection_factory)
    monkeypatch.setattr(service, "issue_password_reset", fake_issue)

    result = service.request_password_reset("User@Example.com")

    assert result == ({"id": "user-1"}, "reset-token")
    assert captured == {
        "identifier": "User@Example.com",
        "user_lookup": lookup,
        "connection_factory": connection_factory,
    }


def test_refresh_rotation_service_preserves_injection_points(monkeypatch):
    from app.modules.identity import service

    lookup = lambda user_id: {"id": user_id}
    connection_factory = lambda: object()
    captured = {}

    def fake_rotate(raw_token, **kwargs):
        captured.update(raw_token=raw_token, **kwargs)
        return ({"id": "user-1"}, "replacement-token")

    monkeypatch.setattr(service, "find_user_by_id", lookup)
    monkeypatch.setattr(service, "get_connection", connection_factory)
    monkeypatch.setattr(service, "rotate_refresh_session", fake_rotate)

    result = service.rotate_refresh_token("refresh-token")

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
