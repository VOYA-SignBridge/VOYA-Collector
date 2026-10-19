def test_identity_public_api_exports_security_primitives():
    from app.modules import identity
    from app.modules.identity import passwords, tokens

    assert identity.create_access_token is tokens.create_access_token
    assert passwords.get_password_hash.__module__ == "app.modules.identity.passwords"
    assert passwords.verify_password.__module__ == "app.modules.identity.passwords"
    assert tokens.decode_access_token.__module__ == "app.modules.identity.tokens"
    assert tokens.bearer_scheme is not None


def test_password_helpers_keep_existing_behavior():
    from app.modules.identity.passwords import get_password_hash, verify_password

    hashed = get_password_hash("correct-horse-battery-staple")

    assert verify_password("correct-horse-battery-staple", hashed) is True
    assert verify_password("wrong-password", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password("correct-horse-battery-staple", "") is False
