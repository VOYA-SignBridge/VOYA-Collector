from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request


def test_legacy_facade_and_identity_api_share_service_callables():
    from app import auth as legacy
    from app.modules import identity
    from app.modules.identity import dependencies, service

    assert legacy.create_user is service.create_user
    assert legacy.authenticate_user is service.authenticate_user
    assert legacy.get_user_from_token is service.get_user_from_token
    assert legacy.get_current_user_optional is dependencies.get_current_user_optional
    assert legacy.get_current_user is dependencies.get_current_user
    assert legacy.require_admin is dependencies.require_admin
    assert identity.create_user is service.create_user
    assert identity.get_current_user is dependencies.get_current_user
    assert identity.request_password_reset is service.request_password_reset
    assert identity.create_refresh_token is service.create_refresh_token
    assert identity.rotate_refresh_token is service.rotate_refresh_token


def test_create_user_orchestrates_repository_without_database(monkeypatch):
    from app.modules.identity import service

    lookups = []
    inserted = {}

    def fake_lookup(identifier):
        lookups.append(identifier)
        return None

    def fake_insert(**kwargs):
        inserted.update(kwargs)
        return {"id": kwargs["user_id"], "username": kwargs["username"]}

    monkeypatch.setattr(service, "find_user_by_login", fake_lookup)
    monkeypatch.setattr(service, "insert_user", fake_insert)
    monkeypatch.setattr(service, "get_password_hash", lambda password: f"hashed:{password}")

    user = service.create_user("  Alice  ", "  ALICE@Example.COM ", "long-enough", True)

    assert lookups == ["Alice", "alice@example.com"]
    assert user["username"] == "Alice"
    assert inserted["email"] == "alice@example.com"
    assert inserted["password_hash"] == "hashed:long-enough"
    assert inserted["is_admin"] is True
    assert inserted["user_id"]


def test_authenticate_user_keeps_dummy_verify_for_unknown_account(monkeypatch):
    from app.modules.identity import service

    calls = []
    monkeypatch.setattr(service, "find_user_by_login", lambda identifier: None)
    monkeypatch.setattr(
        service,
        "verify_password",
        lambda password, password_hash: calls.append((password, password_hash)) or False,
    )

    assert service.authenticate_user("missing", "candidate") is None
    assert calls == [("candidate", service.DUMMY_PASSWORD_HASH)]


def test_current_user_dependency_prefers_cookie_over_bearer(monkeypatch):
    from app import activity
    from app.cookie_auth import ACCESS_COOKIE
    from app.modules.identity import dependencies

    decoded = []
    monkeypatch.setattr(
        dependencies,
        "decode_access_token",
        lambda token: decoded.append(token) or {"sub": "user-1", "iat": 123},
    )
    monkeypatch.setattr(
        dependencies,
        "find_user_by_id",
        lambda user_id: {"id": user_id, "is_active": True},
    )
    monkeypatch.setattr(activity, "is_user_denied", lambda user_id, issued_at: False)

    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"cookie", f"{ACCESS_COOKIE}=cookie-token".encode())],
    })
    bearer = HTTPAuthorizationCredentials(scheme="Bearer", credentials="stale-header-token")

    user = dependencies.get_current_user_optional(request, bearer)

    assert decoded == ["cookie-token"]
    assert user["id"] == "user-1"
