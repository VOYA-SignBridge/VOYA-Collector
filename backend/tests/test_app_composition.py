from app.bootstrap.app_factory import create_app
from app.bootstrap.lifecycle import shutdown, startup
from app.core.middleware.activity import activity_guard
from app.core.middleware.csrf import csrf_protect
from app.modules.saas.tenant_middleware import TenantScopeMiddleware
from app.modules.security.access_gate import access_gate


def test_application_factory_preserves_public_route_layout():
    app = create_app()
    paths = [route.path for route in app.routes]

    # Existing compatibility routes remain available.
    assert "/health" in paths
    assert "/upload/video" in paths
    assert "/training/start" in paths

    # Versioned routes expose the same features, while auth remains v1-only.
    assert "/api/v1/health" in paths
    assert "/api/v1/upload/video" in paths
    assert "/api/v1/training/start" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/tenants" in paths
    assert "/api/v1/billing/plans" in paths
    assert "/api/v1/trial/status" in paths
    assert "/auth/login" not in paths

    # Presence used to be declared directly on app.main and must not duplicate.
    assert paths.count("/api/v1/presence") == 1


def test_application_factory_registers_lifecycle_handlers_once():
    app = create_app()

    assert app.router.on_startup == [startup]
    assert app.router.on_shutdown == [shutdown]


def test_application_factory_preserves_security_middleware_order():
    app = create_app()

    middleware = app.user_middleware
    assert middleware[0].options["dispatch"] is activity_guard
    assert middleware[1].options["dispatch"] is csrf_protect
    assert middleware[3].options["dispatch"] is access_gate
    assert middleware[4].cls is TenantScopeMiddleware
