"""Compatibility shim: legacy import path ``app.storage.*``.

The storage modules moved to ``app.core.storage.*`` during the v2 restructure,
but the legacy routers (and the moved modules themselves) still import
``app.storage.<mod>``. Each submodule below is aliased to the moved module
object, so both import paths resolve to the SAME module (shared state,
including underscore helpers like ``_execute``/``_get_conn``).

Remove this package together with the legacy app (Roadmap v2 — GĐ 6).
Import order matters: modules are listed dependency-first.
"""
import importlib
import sys

_MODULES = (
    "postgres_connection",
    "metadata_db",
    "gdrive_client",
    "catalog_mirror",
    # NOTE: "experiment_tracking_db" is intentionally excluded — dead module
    # with a pre-existing import bug (`from typing import UUID`); nothing
    # imports app.storage.experiment_tracking_db.
    "experiment_tracking_api",
    "experiment_tracking_api_revised",
)

for _name in _MODULES:
    sys.modules[f"{__name__}.{_name}"] = importlib.import_module(
        f"app.core.storage.{_name}"
    )
