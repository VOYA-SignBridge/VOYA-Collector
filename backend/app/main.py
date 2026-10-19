"""ASGI entry point for the VOYA backend."""

from app.logging_config import configure_logging


# Configure logging before the factory imports routers. Some modules initialize
# external clients and emit diagnostics during import.
configure_logging()

from app.bootstrap.app_factory import create_app  # noqa: E402
from app.bootstrap.lifecycle import (  # noqa: E402,F401
    _run_prewarm,
    shutdown,
    startup,
)
from app.core.middleware.activity import activity_guard  # noqa: E402,F401
from app.core.middleware.csrf import csrf_protect  # noqa: E402,F401
from app.core.middleware.metrics import (  # noqa: E402,F401
    metric_path as _metric_path,
    metrics_middleware,
)
from app.routers.diagnostics import trigger_hardware_error  # noqa: E402,F401
from app.routers.presence import report_presence  # noqa: E402,F401


app = create_app()

# Compatibility export for callers that inspect app.main.api_v1 directly.
api_v1 = app.state.api_v1
