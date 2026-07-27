"""Cookie-based auth delivery.

Access + refresh tokens ride in httpOnly cookies so JavaScript (and therefore
any XSS) can't read them. Two companion non-httpOnly cookies let the SPA work:
  - HINT_COOKIE  : presence lets the client skip a pointless /auth/me for guests
  - CSRF_COOKIE  : echoed back in an X-CSRF-Token header (double-submit CSRF)

`Secure` is set when EITHER the config demands it (COOKIE_SECURE=1) or the
request itself arrived over HTTPS. The per-request half is what lets one
deployment serve plain-HTTP localhost and an HTTPS tunnel at the same time: with
a static COOKIE_SECURE=1 the localhost session breaks, with a static 0 the
tunnel's tokens ride an unprotected cookie. SameSite=Lax already stops
cross-site POSTs from sending these cookies; the CSRF token is defense-in-depth.
"""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Request, Response

from app.config import settings
from app.public_url import request_is_https

ACCESS_COOKIE = "voya_access"
REFRESH_COOKIE = "voya_refresh"
HINT_COOKIE = "voya_auth"
CSRF_COOKIE = "voya_csrf"

# Refresh cookie is only sent to the auth endpoints that need it (login sets it,
# refresh rotates it, logout clears it) — never to ordinary API calls.
_REFRESH_COOKIE_SUFFIX = "/api/v1/auth"


def refresh_cookie_path() -> str:
    """Path attribute for the refresh cookie, honoring a sub-path deploy.

    Under a sub-path (e.g. served at /voya/), the gateway strips "/voya" before
    the backend sees the request, but the browser still sends refresh calls to
    "/voya/api/v1/auth/refresh". The cookie's Path must therefore carry the same
    public prefix (COOKIE_PATH_PREFIX) or the browser never sends it back.
    """
    prefix = (settings.cookie_path_prefix or "").rstrip("/")
    return f"{prefix}{_REFRESH_COOKIE_SUFFIX}"


# Back-compat alias (root deploy): the exact string when no sub-path prefix.
REFRESH_COOKIE_PATH = _REFRESH_COOKIE_SUFFIX


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _domain() -> Optional[str]:
    return settings.cookie_domain or None


def _secure_for(request: Optional[Request]) -> bool:
    """Whether to mark this response's cookies Secure.

    COOKIE_SECURE=1 forces it everywhere. Otherwise it follows the scheme the
    browser actually used, so an HTTPS tunnel gets protected cookies without
    locking out plain-HTTP localhost on the same stack.
    """
    if settings.cookie_secure:
        return True
    return request is not None and request_is_https(request)


def _access_max_age() -> int:
    return int(settings.access_token_expire_minutes) * 60


def _refresh_max_age() -> int:
    return int(settings.refresh_token_expire_minutes) * 60


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    request: Optional[Request] = None,
) -> None:
    secure = _secure_for(request)
    samesite = settings.cookie_samesite
    domain = _domain()
    access_max = _access_max_age()
    refresh_max = _refresh_max_age()

    response.set_cookie(
        ACCESS_COOKIE, access_token,
        max_age=access_max, httponly=True, secure=secure,
        samesite=samesite, domain=domain, path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh_token,
        max_age=refresh_max, httponly=True, secure=secure,
        samesite=samesite, domain=domain, path=refresh_cookie_path(),
    )
    response.set_cookie(
        HINT_COOKIE, "1",
        max_age=refresh_max, httponly=False, secure=secure,
        samesite=samesite, domain=domain, path="/",
    )
    response.set_cookie(
        CSRF_COOKIE, csrf_token,
        max_age=refresh_max, httponly=False, secure=secure,
        samesite=samesite, domain=domain, path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    domain = _domain()
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=domain)
    response.delete_cookie(REFRESH_COOKIE, path=refresh_cookie_path(), domain=domain)
    response.delete_cookie(HINT_COOKIE, path="/", domain=domain)
    response.delete_cookie(CSRF_COOKIE, path="/", domain=domain)
