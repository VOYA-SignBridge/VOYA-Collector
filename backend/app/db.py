"""Compatibility facade for legacy database bootstrap imports.

New application code should import from :mod:`app.bootstrap.database` and
:mod:`app.bootstrap.admin`.
"""

from app.bootstrap.admin import bootstrap_admin_user
from app.bootstrap.database import init_db, sync_missing_data_on_startup

__all__ = ["bootstrap_admin_user", "init_db", "sync_missing_data_on_startup"]
