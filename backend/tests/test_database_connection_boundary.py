def test_postgres_connection_uses_canonical_module():
    from app.infrastructure.database import connection as current

    assert current.connect_postgres
    assert current.get_pool
