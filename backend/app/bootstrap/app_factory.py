from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bootstrap.lifecycle import shutdown, startup
from app.bootstrap.routing import register_routers
from app.config import settings
from app.core.middleware.activity import activity_guard
from app.core.middleware.csrf import csrf_protect


def create_app() -> FastAPI:
    """Compose the FastAPI application from explicit infrastructure pieces."""
    app = FastAPI(title="Sign Dataset Backend")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Preserve the previous registration order: activity wraps CSRF, which wraps
    # CORS in Starlette's middleware stack.
    app.middleware("http")(csrf_protect)
    app.middleware("http")(activity_guard)

    app.add_event_handler("startup", startup)
    app.add_event_handler("shutdown", shutdown)
    app.state.api_v1 = register_routers(app)
    return app
