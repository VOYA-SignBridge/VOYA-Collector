"""Bind every HTTP request to the tenant it is acting for.

Division of labour
------------------
This middleware decides **scope**; the route dependencies decide **access**. It
never rejects a request and never raises: an expired, forged or conflicting
token simply produces "no authenticated user", and the endpoint's own
`Depends(get_current_user)` still returns 401 exactly as before. Keeping the two
apart means adding tenant scoping cannot change any endpoint's auth behaviour —
the failure modes stay where they already were.

Why pure ASGI and not `@app.middleware("http")`
-----------------------------------------------
`@app.middleware("http")` is `BaseHTTPMiddleware`, which runs the downstream
application in a task it spawns itself. Context propagation across that boundary
is a well-known source of subtle breakage, and the value being propagated here
decides which tenant's rows a query returns — the one place where "usually
works" is not good enough. A plain ASGI callable awaits the app in the *same*
task and the same context, so there is nothing to propagate across.

Resolution order
----------------
1. A valid session (cookie first, then Bearer — same precedence as
   `get_current_user_optional`) resolves to that user's `users.tenant_id`.
2. Anything else is anonymous and resolves to `settings.public_tenant_id`, the
   single tenant whose catalogue is public.
3. If that setting is empty, the request stays unscoped and the database returns
   nothing.

Note what is deliberately absent: no header or query parameter can choose the
tenant. Honouring a client-supplied `X-Tenant-Id` would make the isolation
boundary a request field. When per-request tenant selection is introduced for
users who belong to several tenants, it has to be validated against membership
before it reaches this function — see docs/needFix/MULTITENANT_ARCHITECTURE.md
§4.3.
"""

from __future__ import annotations

import logging
from typing import Optional

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

from app.config import settings
from app.cookie_auth import ACCESS_COOKIE
from app.tenant_context import bind_request_scope, unbind_request_scope

logger = logging.getLogger(__name__)


def _tenant_of_user(user_id: str) -> Optional[str]:
    """The tenant a user belongs to, or None.

    This read runs in system scope, and it has to: it is the step that DECIDES
    the request's scope, so filtering it by that scope is circular. `users`
    carries a tenant policy (added with `training_jobs`), and under it an
    unscoped read matches nothing — every request would resolve to anonymous
    and the whole deployment would look logged out.

    The exemption is this one statement, selecting one column for one id. It
    cannot enumerate, and it returns nothing a caller did not already prove they
    are by presenting a valid token.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("middleware: resolve the scope, which cannot need a scope"):
        rows = _fetch_all(
            "SELECT tenant_id FROM users WHERE id = %s AND is_active", (user_id,)
        )
    if not rows:
        return None
    return (rows[0].get("tenant_id") or "").strip() or None


def resolve_tenant(access_cookie: Optional[str], bearer: Optional[str]) -> Optional[str]:
    """Tenant for a request carrying these credentials. Never raises."""
    from app.auth import _subject_of

    token = access_cookie or bearer
    if token:
        try:
            user_id = _subject_of(token)
            if user_id:
                tenant = _tenant_of_user(user_id)
                if tenant:
                    return tenant
                # Authenticated but unattributable: the account was deleted or
                # deactivated between issuing the token and this request. Fall
                # through to anonymous rather than guessing a tenant.
        except Exception:
            # Resolution is best-effort by design. A database blip here must
            # degrade to "anonymous", not 500 every request in the process.
            logger.warning("[SCOPE] tenant resolution failed; treating as anonymous",
                           exc_info=True)

    return (settings.public_tenant_id or "").strip() or None


class TenantScopeMiddleware:
    """ASGI middleware setting the tenant ContextVar for the request's lifetime."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            # Websockets and lifespan carry no tenant of their own. Lifespan in
            # particular must stay unscoped: startup work spans tenants and asks
            # for `system_scope` explicitly where it needs it.
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        bearer = None
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            bearer = authorization[7:].strip() or None

        # Blocking psycopg2 call — off the event loop, same as activity_guard.
        tenant = await run_in_threadpool(
            resolve_tenant, request.cookies.get(ACCESS_COOKIE), bearer
        )

        tokens = bind_request_scope(tenant)
        try:
            await self.app(scope, receive, send)
        finally:
            unbind_request_scope(tokens)
