def test_identity_boundary_exports_canonical_callables():
    from app.modules import identity
    from app.modules.identity import dependencies, service, tokens

    assert identity.authenticate_user is service.authenticate_user
    assert identity.create_access_token is tokens.create_access_token
    assert identity.get_current_user is dependencies.get_current_user
    assert identity.require_admin is dependencies.require_admin
