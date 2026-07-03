import asyncio
import logging
import time

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import dataset, upload, jobs, classes, inference, health, auth, realtime_proxy, tts, training, session, trash, taxonomies
from app.logging_config import configure_logging
from app.db import init_db
from app.services.tts_service import init_tts, close_tts
from app.services.tts_prewarm import prewarm_tts_cache

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter

app = FastAPI(
    title="Sign Dataset Backend",
    swagger_ui_parameters={"operationsSorter": "method"}
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Setup CORS securely
# cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Tạm thời allow all theo yêu cầu
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# init DB tables (dev). In prod, use migrations (alembic).
@app.on_event("startup")
async def startup():
    configure_logging()
    logger = logging.getLogger("startup")
    logger.setLevel(logging.INFO)
    started_at = time.time()
    logger.info(
        "[STARTUP] dataset_root=%s database_url=%s",
        settings.dataset_root,
        settings.database_url,
    )
    db_ready = init_db()

    # Bootstrap admin user if configured
    if db_ready:
        from app.db import bootstrap_admin_user
        bootstrap_admin_user()

    logger.info(
        "[STARTUP][DB_INIT] status=%s duration_ms=%.1f",
        "ready" if db_ready else "warning",
        (time.time() - started_at) * 1000,
    )

    # Initialize dedicated httpx client for realtime proxy
    # Backend starts cleanly even if inference service is offline
    realtime_proxy.init_client()

    # Initialize TTS service (Redis pool)
    await init_tts()

    # Spawn TTS prewarm as background task (non-blocking)
    if settings.tts_prewarm_on_startup:
        asyncio.create_task(_run_prewarm())


async def _run_prewarm() -> None:
    """Background prewarm task — does not block server startup."""
    logger = logging.getLogger("startup")
    try:
        summary = await prewarm_tts_cache()
        logger.info("[STARTUP][TTS_PREWARM] %s", summary)
    except Exception as exc:
        logger.warning("[STARTUP][TTS_PREWARM] failed: %s", exc)


@app.on_event("shutdown")
async def shutdown():
    await realtime_proxy.close_client()
    await close_tts()

# Include routers
app.include_router(health.router)
app.include_router(dataset.router)
app.include_router(upload.router)
app.include_router(jobs.router)
app.include_router(classes.router)
app.include_router(inference.router)
app.include_router(realtime_proxy.router)
app.include_router(tts.router)
app.include_router(training.router)
app.include_router(session.router)
app.include_router(trash.router)
app.include_router(taxonomies.router)

# Versioned API (do not remove unversioned endpoints; FE may depend on them)
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(health.router)
api_v1.include_router(dataset.router)
api_v1.include_router(upload.router)
api_v1.include_router(jobs.router)
api_v1.include_router(classes.router)
api_v1.include_router(session.router)
api_v1.include_router(trash.router)
api_v1.include_router(inference.router)
api_v1.include_router(auth.router)
api_v1.include_router(realtime_proxy.router)
api_v1.include_router(tts.router)
api_v1.include_router(training.router)
api_v1.include_router(taxonomies.router)
app.include_router(api_v1)

# test