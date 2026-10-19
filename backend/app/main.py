"""ASGI entry point for the VOYA backend."""

from app.bootstrap.logging import configure_logging


# Configure logging before the application factory imports routers. Some router
# modules initialize external clients and emit diagnostics during import.
configure_logging()

from app.bootstrap.app_factory import create_app  # noqa: E402
from app.bootstrap.lifecycle import _run_prewarm, shutdown, startup  # noqa: E402,F401
from app.core.middleware.activity import activity_guard  # noqa: E402,F401
from app.core.middleware.csrf import csrf_protect  # noqa: E402,F401
from app.routers.presence import report_presence  # noqa: E402,F401


app = create_app()

# Compatibility export for code that inspected app.main.api_v1 directly.
api_v1 = app.state.api_v1
