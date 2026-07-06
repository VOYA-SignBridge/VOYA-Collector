import asyncio
import logging
import time

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging_config import configure_logging

# Configure logging before importing routers — some (e.g. training) connect
# to Redis and log the result at module import time, which would otherwise
# run before the root logger is configured and get silently dropped.
configure_logging()

from app.routers import dataset, upload, jobs, classes, inference, health, auth, realtime_proxy, tts, training
from app.db import init_db
from app.services.tts_service import init_tts, close_tts
from app.services.tts_prewarm import prewarm_tts_cache

app = FastAPI(title="Sign Dataset Backend")

# CORS: origins configurable via CORS_ALLOWED_ORIGINS (comma-separated).
# Auth uses Bearer tokens (no cookies), so credentialed CORS isn't needed —
# allow_credentials=True combined with a wildcard origin is invalid per spec
# and browsers reject it anyway.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# init DB tables (dev). In prod, use migrations (alembic).
@app.on_event("startup")
async def startup():
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

    # Restore training jobs from Postgres. Training execution runs in the
    # dedicated trainer container (Celery queue "training") — the backend
    # only dispatches jobs and reads progress from Postgres.
    try:
        await training.restore_jobs_from_db()
    except Exception as exc:
        logger.warning("[STARTUP][TRAINING_RESTORE] failed: %s", exc)


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

# Versioned API (do not remove unversioned endpoints; FE may depend on them)
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(health.router)
api_v1.include_router(dataset.router)
api_v1.include_router(upload.router)
api_v1.include_router(jobs.router)
api_v1.include_router(classes.router)
api_v1.include_router(inference.router)
api_v1.include_router(auth.router)
api_v1.include_router(realtime_proxy.router)
api_v1.include_router(tts.router)
api_v1.include_router(training.router)
app.include_router(api_v1)

# test