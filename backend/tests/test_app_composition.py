from app.bootstrap.app_factory import create_app
from app.bootstrap.lifecycle import shutdown, startup


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
    assert "/auth/login" not in paths

    # Presence used to be declared directly on app.main and must not duplicate.
    assert paths.count("/api/v1/presence") == 1


def test_application_factory_registers_lifecycle_handlers_once():
    app = create_app()

    assert app.router.on_startup == [startup]
    assert app.router.on_shutdown == [shutdown]
