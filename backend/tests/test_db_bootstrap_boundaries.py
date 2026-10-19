"""Boundary checks for the legacy database bootstrap facade."""

from app import db
from app.bootstrap import admin, database


def test_db_facade_reexports_bootstrap_implementations() -> None:
    assert db.init_db is database.init_db
    assert db.sync_missing_data_on_startup is database.sync_missing_data_on_startup
    assert db.bootstrap_admin_user is admin.bootstrap_admin_user
