"""Boundary checks for the canonical database bootstrap modules."""

from pathlib import Path

from app.bootstrap import admin, database


def test_database_bootstrap_implementations_have_canonical_modules() -> None:
    assert database.init_db.__module__ == "app.bootstrap.database"
    assert database.sync_missing_data_on_startup.__module__ == "app.bootstrap.database"
    assert admin.bootstrap_admin_user.__module__ == "app.bootstrap.admin"


def test_legacy_database_facade_is_removed() -> None:
    app_root = Path(__file__).resolve().parents[1] / "app"
    assert not (app_root / "db.py").exists()


def test_admin_bootstrap_is_system_scoped_and_sets_tenant_explicitly(monkeypatch) -> None:
    from app.config import settings
    from app.modules.identity import passwords
    from app.modules.saas import tenant_context
    from app.modules.saas.tenancy import DEFAULT_TENANT_ID
    from app.storage import metadata_db

    monkeypatch.setattr(settings, "admin_username", "bootstrap-test")
    monkeypatch.setattr(settings, "admin_password", "test-password")
    monkeypatch.setattr(passwords, "get_password_hash", lambda _value: "hash")

    def column_exists(_table, _column):
        assert tenant_context.in_system_scope()
        return True

    def fetch_all(_sql, _params):
        assert tenant_context.in_system_scope()
        return []

    executed = {}

    def execute(sql, params):
        assert tenant_context.in_system_scope()
        executed.update(sql=sql, params=params)

    monkeypatch.setattr(metadata_db, "_column_exists", column_exists)
    monkeypatch.setattr(metadata_db, "_fetch_all", fetch_all)
    monkeypatch.setattr(metadata_db, "_execute", execute)

    admin.bootstrap_admin_user()

    assert "tenant_id" in executed["sql"]
    assert executed["params"][-1] == DEFAULT_TENANT_ID
