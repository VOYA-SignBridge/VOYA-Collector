import asyncio
import hmac
import logging
import time

from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app import activity
from app.config import settings, redact_db_url
from app.cookie_auth import ACCESS_COOKIE, CSRF_COOKIE
from app.rate_limit import client_ip
from app.routers import (
    admin,
    auth,
    classes,
    dataset,
    dataset_exporter,
    experiments,
    health,
    inference,
    jobs,
    realtime_proxy,
    training,
    tts,
    upload,
)
from app.logging_config import configure_logging

# Configure logging before importing routers — some (e.g. training) connect
# to Redis and log the result at module import time, which would otherwise
# run before the root logger is configured and get silently dropped.
configure_logging()
from app.db import init_db
from app.services.tts_service import init_tts, close_tts
from app.services.tts_prewarm import prewarm_tts_cache

app = FastAPI(title="Sign Dataset Backend")

# CORS: origins configurable via CORS_ALLOWED_ORIGINS (comma-separated).
# The SPA is served same-origin through the nginx gateway, so the auth cookies
# ride along without CORS involvement. Keep allow_credentials=False (wildcard
# origin + credentials is invalid per spec). If you ever serve the API from a
# different origin than the SPA, set an explicit origin AND allow_credentials
# =True so the browser will send the cookies cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CSRF (double-submit token) ---------------------------------------------
# Cookies are sent automatically by the browser, so cookie-authenticated
# state-changing requests need a second proof that the caller is our own JS:
# the non-httpOnly CSRF cookie echoed back in an X-CSRF-Token header. A
# cross-site attacker can't read that cookie, so can't set a matching header.
# Only enforced when an access cookie is present (Bearer-header/API clients and
# guests are unaffected) and skipped for the auth endpoints that bootstrap or
# tear down the session.
_CSRF_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
_CSRF_EXEMPT_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
}


@app.middleware("http")
async def csrf_protect(request: Request, call_next):
    if request.method not in _CSRF_SAFE_METHODS:
        path = request.url.path
        if path not in _CSRF_EXEMPT_PATHS and request.cookies.get(ACCESS_COOKIE):
            header = request.headers.get("x-csrf-token", "")
            cookie = request.cookies.get(CSRF_COOKIE, "")
            if not header or not cookie or not hmac.compare_digest(header, cookie):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token missing or invalid"},
                )
    return await call_next(request)


# --- Activity tracking + IP blocklist ---------------------------------------
# Records who is calling (IP, user, rate) for the admin activity monitor, and
# cuts off IPs an admin has blocked. The auth + admin endpoints are never
# IP-blocked, so an admin can always undo a bad block / stays reachable.
# Runs in a threadpool (sync Redis) and fails open — never breaks a request.
_BLOCK_EXEMPT_PREFIXES = ("/api/v1/auth", "/auth", "/api/v1/admin", "/admin")


@app.middleware("http")
async def activity_guard(request: Request, call_next):
    path = request.url.path
    enforce = not any(path.startswith(p) for p in _BLOCK_EXEMPT_PREFIXES)
    try:
        block = await run_in_threadpool(activity.guard, request, enforce)
    except Exception:
        block = None
    if block:
        reason = block.get("reason") or "Vi phạm quy định sử dụng"
        return JSONResponse(
            status_code=403,
            content={
                "detail": f"Truy cập của bạn đã bị quản trị viên chặn. Lý do: {reason}",
                "blocked": True,
                "reason": reason,
                "until": block.get("until", 0),
                "ttl": block.get("ttl", 0),
                "contact": settings.support_email,
            },
        )
    return await call_next(request)


# init DB tables (dev). In prod, use migrations (alembic).
_INSECURE_DEFAULT_SECRET = "change-me-in-production"


@app.on_event("startup")
async def startup():
    logger = logging.getLogger("startup")
    logger.setLevel(logging.INFO)
    started_at = time.time()

    # Refuse to serve a real deployment signed with the fallback secret from
    # config.py — anyone who read that source line could forge admin tokens.
    # Only enforced for app_env=="production" so local/dev setups that never
    # set SECRET_KEY still boot without ceremony.
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
app.include_router(admin.router)

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
api_v1.include_router(admin.router)
app.include_router(api_v1)


@app.post("/api/v1/presence", status_code=204)
async def report_presence(request: Request):
    """Browser heartbeat: keeps the session 'online' and (opt-in) attaches a
    precise GPS position for the admin activity monitor. Open to any client —
    each caller only reports its own IP/coordinates. Body: {lat, lon, accuracy}."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    ip = client_ip(request)
    lat, lon, acc = body.get("lat"), body.get("lon"), body.get("accuracy")
    if lat is not None and lon is not None:
        await run_in_threadpool(activity.record_presence, ip, lat, lon, acc)
    return Response(status_code=204)


# test