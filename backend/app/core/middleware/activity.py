from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.modules.security.activity_monitor import guard


_BLOCK_EXEMPT_PREFIXES = ("/api/v1/auth", "/auth", "/api/v1/admin", "/admin")


async def activity_guard(request: Request, call_next):
    """Record activity and reject requests from administratively blocked IPs."""
    path = request.url.path
    enforce = not any(path.startswith(prefix) for prefix in _BLOCK_EXEMPT_PREFIXES)
    try:
        block = await run_in_threadpool(guard, request, enforce)
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
