import asyncio
import hmac
import logging
import time

from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from asgi_correlation_id import CorrelationIdMiddleware

from app import activity
from app.access_gate import access_gate
from app.config import settings
from app.cookie_auth import ACCESS_COOKIE, CSRF_COOKIE
from app.rate_limit import client_ip
# `experiments` and `dataset_exporter` are deliberately NOT imported. Both were
# imported here and never passed to include_router — 681 lines that read as live
# endpoints, are reachable by no URL, and were executed at import time on every
# boot. Removing the import makes their status honest; the files are kept for now
# pending a decision to mount or delete them (see BACKEND_WORK_PLAN.md B4).
from app.routers import (
    admin,
    auth,
    billing,
    classes,
    dataset,
    health,
    inference,
    integrations,
    jobs,
    label_sessions,
    legal as legal_router,
    legal_admin,
    notifications as notifications_router,
    realtime_proxy,
    sot_admin,
    support,
    tenants,
    training,
    trial,
    tts,
    two_factor as two_factor_router,
    upload,
    verification,
    workspaces as workspaces_router,
    vocabulary,
)
from app import metrics
from app.logging_config import configure_logging
from app.tenant_middleware import TenantScopeMiddleware

# Configure logging before importing routers — some (e.g. training) connect
# to Redis and log the result at module import time, which would otherwise
# run before the root logger is configured and get silently dropped.
configure_logging()
from app.db import init_db
from app.services.tts_service import init_tts, close_tts
from app.services.tts_prewarm import prewarm_tts_cache

app = FastAPI(title="Sign Dataset Backend")

def _metric_path(request: Request) -> str:
    """Low-cardinality path label: the matched route TEMPLATE (e.g.
    /api/v1/classes/{class_uid}/sessions), not the concrete URL. The route is
    only attached to the scope by Starlette's router, so this must be read AFTER
    call_next has run. Falls back to a coarse prefix for unmatched paths (404s,
    probes) so raw ids never explode the metric cardinality."""
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if template:
        return template
    parts = request.url.path.split("/")
    if len(parts) > 3:
        return "/".join(parts[:3]) + "/{id}"
    return request.url.path


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    import time
    from app.metrics import http_requests_total, http_request_duration_seconds, http_requests_in_progress

    method = request.method
    # in-progress is bracketed around the call and the route isn't known yet, so
    # label it by method only (path is added to the completed-request metrics).
    http_requests_in_progress.labels(method=method).inc()
    start_time = time.time()
    status_code = "500"
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        return response
    finally:
        duration = time.time() - start_time
        # Read the matched route template now — routing has run inside call_next.
        path = _metric_path(request)
        http_requests_in_progress.labels(method=method).dec()
        http_requests_total.labels(method=method, status=status_code, path=path).inc()
        http_request_duration_seconds.labels(method=method, status=status_code, path=path).observe(duration)

# CORS: origins configurable via CORS_ALLOWED_ORIGINS (comma-separated).
# The SPA is served same-origin through the nginx gateway, so the auth cookies
# ride along without CORS involvement. Keep allow_credentials=False (wildcard
# origin + credentials is invalid per spec). If you ever serve the API from a
# different origin than the SPA, set an explicit origin AND allow_credentials
# =True so the browser will send the cookies cross-origin.
app.add_middleware(CorrelationIdMiddleware)

# Tenant scope. Starlette applies middleware in reverse registration order, so
# what matters is that this is registered AFTER metrics/correlation-id and
# BEFORE routing: the ContextVar is bound by the time any route, dependency or
# query runs. The two middlewares that end up outside it (csrf_protect,
# activity_guard) read cookies and the activity tables only — neither touches a
# tenant-scoped table, so neither needs the scope. Anything added later that
# does must be registered after this line.
app.add_middleware(TenantScopeMiddleware)

# Cổng truy cập: mọi endpoint đóng trừ những cái khai báo trong access_gate.
#
# Đăng ký TRƯỚC CORSMiddleware là có chủ ý. Starlette chèn middleware vào đầu
# danh sách, nên cái đăng ký sau chạy ở vòng NGOÀI — đặt cổng ở đây khiến nó nằm
# TRONG CORS, và phản hồi 401 của nó vẫn mang đủ header CORS. Đảo lại thì trình
# duyệt thấy một lỗi mạng vô danh thay vì mã lỗi đọc được.
#
# Nằm ngoài TenantScopeMiddleware thì không sao: cổng chỉ đọc cookie và giải mã
# token, còn `_identity_cursor` trong auth.py tự vào system scope.
app.add_middleware(BaseHTTPMiddleware, dispatch=access_gate)

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

    # Phân quyền. Sau `init_db()` vì nó đọc các bảng RBAC mà `ensure_tables()`
    # vừa tạo và seed; trước khi cổng mở, vì `get_enforcer()` cố ý KHÔNG nạp
    # lười — một lần khởi động hỏng phải lộ ra ở đây, không phải ở request đầu
    # tiên tình cờ chạm vào một endpoint có kiểm quyền.
    #
    # `strict` chỉ bật ở chế độ `casbin`: khi Casbin đang thực sự quyết định,
    # không nạp được policy nghĩa là không trả lời được, và §40 nói rõ phải
    # hỏng-thì-đóng. Ở `shadow` thì hệ cũ vẫn quyết định, nên một lần nạp hỏng
    # chỉ làm mất phần quan sát — bắt nó làm sập tiến trình sẽ khiến không ai
    # dám bật shadow mode, và đó là kết cục tệ hơn nhiều.
    if db_ready and settings.authz_mode != "legacy":
        from app.authorization import enforcer as authz_enforcer
        from app.authorization import policy_invalidator

        strict = settings.authz_mode == "casbin"
        try:
            ok = authz_enforcer.startup(strict=strict)
            logger.info(
                "[STARTUP][AUTHZ] mode=%s policy=%s %s",
                settings.authz_mode, "ready" if ok else "NOT READY",
                authz_enforcer.status().get("policy"),
            )
            if ok:
                policy_invalidator.start()
        except Exception:
            if strict:
                raise
            logger.exception("[STARTUP][AUTHZ] khoi tao that bai; he cu van quyet dinh")
    else:
        logger.info("[STARTUP][AUTHZ] mode=%s — Casbin khong duoc nap",
                    settings.authz_mode)

    # CPU for the admin monitor is sampled in a background thread: measuring it
    # inside the request would need a blocking window, and a window short enough
    # not to hurt the request reports 0% on an idle-looking-but-busy host.
    from app.monitoring import start_cpu_monitor
    start_cpu_monitor()

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
app.include_router(label_sessions.router)
app.include_router(inference.router)
app.include_router(realtime_proxy.router)
app.include_router(tts.router)
app.include_router(training.router)
app.include_router(admin.router)
app.include_router(sot_admin.router)
app.include_router(tenants.router)
app.include_router(workspaces_router.router)
app.include_router(billing.router)
app.include_router(integrations.router)
app.include_router(verification.router)
app.include_router(vocabulary.router)
app.include_router(vocabulary.catalog_router)
app.include_router(trial.router)
app.include_router(legal_router.router)
app.include_router(legal_admin.router)
app.include_router(metrics.router)

# Versioned API (do not remove unversioned endpoints; FE may depend on them)
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(health.router)
api_v1.include_router(dataset.router)
api_v1.include_router(upload.router)
api_v1.include_router(jobs.router)
api_v1.include_router(classes.router)
api_v1.include_router(label_sessions.router)
api_v1.include_router(inference.router)
api_v1.include_router(auth.router)
api_v1.include_router(realtime_proxy.router)
api_v1.include_router(tts.router)
api_v1.include_router(training.router)
api_v1.include_router(admin.router)
api_v1.include_router(sot_admin.router)
api_v1.include_router(tenants.router)
api_v1.include_router(workspaces_router.router)
api_v1.include_router(billing.router)
api_v1.include_router(integrations.router)
api_v1.include_router(verification.router)
api_v1.include_router(vocabulary.router)
api_v1.include_router(vocabulary.catalog_router)
api_v1.include_router(trial.router)
api_v1.include_router(legal_router.router)
api_v1.include_router(legal_admin.router)
api_v1.include_router(notifications_router.router)
api_v1.include_router(support.router)
api_v1.include_router(two_factor_router.router)
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

@app.post("/api/v1/test/trigger-hardware-error", status_code=204)
async def trigger_hardware_error():
    """TEST ENDPOINT: Forces a hardware error metric to 1 to test Grafana Email Alert."""
    from app.metrics import hardware_error
    import time
    
    # Simulate a camera disconnecting
    hardware_error.labels(resource='test_camera_1').set(1)
    
    return Response(status_code=204)
