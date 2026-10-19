from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.access_gate import access_gate
from app.bootstrap.lifecycle import shutdown, startup
from app.bootstrap.routing import register_routers
from app.config import settings
from app.core.middleware.activity import activity_guard
from app.core.middleware.csrf import csrf_protect
from app.core.middleware.metrics import metrics_middleware
from app.tenant_middleware import TenantScopeMiddleware


def create_app() -> FastAPI:
    """Compose the FastAPI application without changing its public contracts."""
    app = FastAPI(title="Sign Dataset Backend")

    # Starlette inserts newly registered middleware at the front. Keep these
    # calls in the same order as the former app.main implementation so the
    # effective outer-to-inner stack remains:
    # activity -> csrf -> CORS -> access gate -> tenant -> correlation -> metrics.
    app.middleware("http")(metrics_middleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(TenantScopeMiddleware)
    app.add_middleware(BaseHTTPMiddleware, dispatch=access_gate)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(csrf_protect)
    app.middleware("http")(activity_guard)

    app.add_event_handler("startup", startup)
    app.add_event_handler("shutdown", shutdown)
    app.state.api_v1 = register_routers(app)
    return app
