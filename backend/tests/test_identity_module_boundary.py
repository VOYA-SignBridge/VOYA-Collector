def test_identity_boundary_preserves_legacy_callable_identity():
    from app import auth as legacy
    from app.modules import identity

    assert identity.authenticate_user is legacy.authenticate_user
    assert identity.create_access_token is legacy.create_access_token
    assert identity.get_current_user is legacy.get_current_user
    assert identity.require_admin is legacy.require_admin
