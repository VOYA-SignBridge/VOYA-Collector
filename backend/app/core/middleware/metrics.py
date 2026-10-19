import time

from fastapi import Request


def metric_path(request: Request) -> str:
    """Return the matched route template, never a high-cardinality raw id."""
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if template:
        return template
    parts = request.url.path.split("/")
    if len(parts) > 3:
        return "/".join(parts[:3]) + "/{id}"
    return request.url.path


async def metrics_middleware(request: Request, call_next):
    """Record request count, latency and in-progress Prometheus metrics."""
    from app.metrics import (
        http_request_duration_seconds,
        http_requests_in_progress,
        http_requests_total,
    )

    method = request.method
    http_requests_in_progress.labels(method=method).inc()
    started_at = time.time()
    status_code = "500"
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        return response
    finally:
        duration = time.time() - started_at
        path = metric_path(request)
        http_requests_in_progress.labels(method=method).dec()
        http_requests_total.labels(
            method=method, status=status_code, path=path
        ).inc()
        http_request_duration_seconds.labels(
            method=method, status=status_code, path=path
        ).observe(duration)
