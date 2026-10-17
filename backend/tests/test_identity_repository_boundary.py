def test_legacy_account_helpers_delegate_to_identity_repository():
    from app import auth as legacy
    from app.modules.identity import repository

    assert legacy._normalize_login is repository.normalize_login
    assert legacy._row_to_user is repository.row_to_user


def test_repository_normalizes_login_and_maps_user_rows():
    from app.modules.identity.repository import (
        find_user_by_login,
        normalize_login,
        row_to_user,
    )

    assert normalize_login("  User@Example.COM  ") == "user@example.com"
    assert normalize_login("") == ""
    assert find_user_by_login("   ", connection_factory=lambda: None) is None
    assert row_to_user(None) is None
    assert row_to_user(
        {
            "id": 42,
            "username": None,
            "email": "user@example.com",
            "password_hash": None,
            "is_active": 1,
            "is_admin": 0,
            "created_at": None,
        }
    ) == {
        "id": "42",
        "username": "",
        "email": "user@example.com",
        "password_hash": "",
        "is_active": True,
        "is_admin": False,
        "created_at": None,
    }
