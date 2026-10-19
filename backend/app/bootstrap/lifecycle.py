import asyncio
import logging
import time

from app.bootstrap.admin import bootstrap_admin_user
from app.bootstrap.database import init_db
from app.config import redact_db_url, settings
from app.routers import realtime_proxy, training
from app.services.tts_prewarm import prewarm_tts_cache
from app.services.tts_service import close_tts, init_tts


_INSECURE_DEFAULT_SECRET = "change-me-in-production"


async def startup() -> None:
    """Initialize infrastructure required by the HTTP application."""
    logger = logging.getLogger("startup")
    logger.setLevel(logging.INFO)
    started_at = time.time()

    if settings.app_env == "production" and (
        settings.secret_key == _INSECURE_DEFAULT_SECRET
        or settings.auth_token_secret_key == _INSECURE_DEFAULT_SECRET
    ):
        raise RuntimeError(
            "SECRET_KEY/AUTH_TOKEN_SECRET_KEY is still the insecure default "
            "with APP_ENV=production. Set a real secret before starting."
        )

    logger.info(
        "[STARTUP] dataset_root=%s database_url=%s",
        settings.dataset_root,
        redact_db_url(settings.database_url),
    )
    db_ready = init_db()

    if db_ready:
        bootstrap_admin_user()

    logger.info(
        "[STARTUP][DB_INIT] status=%s duration_ms=%.1f",
        "ready" if db_ready else "warning",
        (time.time() - started_at) * 1000,
    )

    realtime_proxy.init_client()
    await init_tts()

    if settings.tts_prewarm_on_startup:
        asyncio.create_task(_run_prewarm())

    try:
        await training.restore_jobs_from_db()
    except Exception as exc:
        logger.warning("[STARTUP][TRAINING_RESTORE] failed: %s", exc)


async def _run_prewarm() -> None:
    """Warm the TTS cache without blocking application startup."""
    logger = logging.getLogger("startup")
    try:
        summary = await prewarm_tts_cache()
        logger.info("[STARTUP][TTS_PREWARM] %s", summary)
    except Exception as exc:
        logger.warning("[STARTUP][TTS_PREWARM] failed: %s", exc)


async def shutdown() -> None:
    """Close application-owned clients."""
    await realtime_proxy.close_client()
    await close_tts()
