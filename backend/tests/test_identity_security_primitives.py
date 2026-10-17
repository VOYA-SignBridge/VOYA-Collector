def test_legacy_auth_exports_identity_security_primitives():
    from app import auth as legacy
    from app.modules.identity import passwords, tokens

    assert legacy.get_password_hash is passwords.get_password_hash
    assert legacy.verify_password is passwords.verify_password
    assert legacy.create_access_token is tokens.create_access_token
    assert legacy._decode_token is tokens.decode_access_token
    assert legacy.bearer_scheme is tokens.bearer_scheme


def test_password_helpers_keep_existing_behavior():
    from app.modules.identity.passwords import get_password_hash, verify_password

    hashed = get_password_hash("correct-horse-battery-staple")

    assert verify_password("correct-horse-battery-staple", hashed) is True
    assert verify_password("wrong-password", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password("correct-horse-battery-staple", "") is False
