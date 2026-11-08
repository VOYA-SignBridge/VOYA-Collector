import hmac

from fastapi import Request
from fastapi.responses import JSONResponse

from app.modules.identity.cookies import ACCESS_COOKIE, CSRF_COOKIE


_CSRF_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
_CSRF_EXEMPT_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
}


async def csrf_protect(request: Request, call_next):
    """Enforce the double-submit token for cookie-authenticated mutations."""
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
