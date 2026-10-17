def test_legacy_postgres_connection_import_is_an_exact_module_alias():
    from app.infrastructure.database import connection as current
    from app.storage import postgres_connection as legacy

    assert legacy is current
    assert legacy.connect_postgres is current.connect_postgres
    assert legacy.get_pool is current.get_pool
