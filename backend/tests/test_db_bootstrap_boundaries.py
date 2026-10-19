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
