import time

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from asgi_correlation_id import CorrelationIdMiddleware

from app.bootstrap.lifecycle import shutdown, startup
from app.bootstrap.routing import register_routers
from app.config import settings
from app.core.middleware.activity import activity_guard
from app.core.middleware.csrf import csrf_protect
from app.infrastructure.observability.metrics import (
    http_request_duration_seconds,
    http_requests_in_progress,
    http_requests_total,
)
from app.modules.saas.tenant_middleware import TenantScopeMiddleware
from app.modules.security.access_gate import access_gate


def _metric_path(request: Request) -> str:
    """Return a bounded-cardinality label for the matched route."""
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if template:
        return template
    parts = request.url.path.split("/")
    if len(parts) > 3:
        return "/".join(parts[:3]) + "/{id}"
    return request.url.path


async def metrics_middleware(request: Request, call_next):
    """Record request count, duration and concurrency with bounded labels."""
    method = request.method
    http_requests_in_progress.labels(method=method).inc()
    started_at = time.time()
    status_code = "500"
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        return response
    finally:
        path = _metric_path(request)
        duration = time.time() - started_at
        http_requests_in_progress.labels(method=method).dec()
        http_requests_total.labels(method=method, status=status_code, path=path).inc()
        http_request_duration_seconds.labels(
            method=method, status=status_code, path=path
        ).observe(duration)


def create_app() -> FastAPI:
    """Compose the FastAPI application from explicit infrastructure pieces."""
    app = FastAPI(title="Sign Dataset Backend")

    # Keep the deployed middleware order. Starlette applies middleware in
    # reverse registration order; request execution is therefore activity,
    # CSRF, CORS, access gate, tenant scope, correlation id, then metrics.
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
