from app.bootstrap.app_factory import create_app
from app.bootstrap.lifecycle import shutdown, startup


def _middleware_name(entry):
    dispatch = entry.options.get("dispatch")
    return getattr(dispatch, "__name__", entry.cls.__name__)


def test_application_factory_preserves_representative_public_routes():
    app = create_app()
    paths = [route.path for route in app.routes]

    assert "/health" in paths
    assert "/upload/video" in paths
    assert "/training/start" in paths
    assert "/metrics" in paths

    assert "/api/v1/health" in paths
    assert "/api/v1/upload/video" in paths
    assert "/api/v1/training/start" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/learn/signs" in paths
    assert "/auth/login" not in paths
    assert paths.count("/api/v1/presence") == 1
    assert paths.count("/api/v1/test/trigger-hardware-error") == 1


def test_application_factory_registers_lifecycle_handlers_once():
    app = create_app()

    assert app.router.on_startup == [startup]
    assert app.router.on_shutdown == [shutdown]


def test_application_factory_preserves_middleware_order():
    app = create_app()

    assert [_middleware_name(entry) for entry in app.user_middleware] == [
        "activity_guard",
        "csrf_protect",
        "CORSMiddleware",
        "access_gate",
        "TenantScopeMiddleware",
        "CorrelationIdMiddleware",
        "metrics_middleware",
    ]
