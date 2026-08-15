"""Which tenant the current unit of work is acting for.

This module is the only place that answers that question, and it is deliberately
dependency-free: the storage layer imports it on every query, so it must not
drag in FastAPI, Celery or the database.

Two states, and the difference is the security boundary
-------------------------------------------------------
``tenant_scope("truong-b")``  acting for exactly one tenant. Postgres row-level
                              security will show that tenant's rows and nothing
                              else, and will refuse writes stamped with any
                              other tenant.

``system_scope("reason")``    acting for the platform. Row-level security is
                              satisfied for every tenant. This exists because
                              real work has no request behind it — the startup
                              CSV->DB sync, the SOT reader, Celery maintenance —
                              and such work legitimately spans tenants.

Neither is the default. **Unset means no tenant at all**, which the database
policy turns into zero rows rather than all rows. That choice is the whole
design: a code path someone forgot to scope returns nothing and gets noticed,
instead of returning everything and not getting noticed. Fail-closed is only a
property if the closed state is the one you get by doing nothing.

Why ``system_scope`` takes a reason
-----------------------------------
It is the escape hatch from the guarantee the rest of the system is built on, so
every use should say out loud why it is entitled to one. The string is logged
and it makes `grep -rn "system_scope("` a readable inventory of every place the
boundary is crossed, rather than a list of call sites someone has to go read.

Why a ContextVar rather than a parameter
----------------------------------------
The alternative is threading a tenant id through every function between the
request handler and `_cursor()` — several hundred call sites, and one missed
parameter is a silent cross-tenant read. A ContextVar is set once at the entry
point and read once at the exit point, with nothing in between able to forget
it. ContextVars are also copied into anyio worker threads, so the sync database
code FastAPI runs in a threadpool sees the value the async request set.

Related: ``storage/rls.py`` (the policies), ``tenant_middleware.py`` (the HTTP
entry point), docs/11-worklog/BACKEND_WORK_PLAN.md item A3.
"""

from __future__ import annotations

import functools
import logging
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Optional

from app.tenancy import is_valid_tenant_id

logger = logging.getLogger(__name__)

#: The tenant the current task is acting for. None means "no tenant", which the
#: database policy resolves to zero rows.
_tenant: ContextVar[Optional[str]] = ContextVar("voya_tenant_id", default=None)

#: True while acting for the platform across all tenants.
_system: ContextVar[bool] = ContextVar("voya_system_scope", default=False)


def current_tenant() -> Optional[str]:
    """The tenant in force, or None when nothing has been scoped."""
    return _tenant.get()


def in_system_scope() -> bool:
    """True when the current task is acting for the platform, not one tenant."""
    return _system.get()


def describe_scope() -> str:
    """One short string for logs and error messages."""
    if _system.get():
        return "system"
    tenant = _tenant.get()
    return f"tenant:{tenant}" if tenant else "unscoped"


class TenantScopeError(RuntimeError):
    """Raised when a code path that requires a tenant does not have one."""


def require_tenant() -> str:
    """The tenant in force, or raise.

    For write paths that must stamp a row with an owner. Returning a default
    here instead of raising is how rows end up silently assigned to the wrong
    tenant, so this deliberately has no fallback — see `app.tenancy` for the
    same argument made about the CSV layer.
    """
    tenant = _tenant.get()
    if not tenant:
        raise TenantScopeError(
            f"this operation requires a tenant scope, but the current scope is "
            f"{describe_scope()!r}"
        )
    return tenant


def _set(tenant: Optional[str], system: bool) -> tuple[Token, Token]:
    return _tenant.set(tenant), _system.set(system)


def _reset(tokens: tuple[Token, Token]) -> None:
    tenant_token, system_token = tokens
    _tenant.reset(tenant_token)
    _system.reset(system_token)


@contextmanager
def tenant_scope(tenant_id: str) -> Iterator[str]:
    """Act for exactly one tenant for the duration of the block.

    Validates the id rather than trusting it: the value reaches Postgres as a
    GUC that a policy compares against `tenant_id`, and an id that is merely
    *different* (a stray newline, a capital letter) does not error anywhere — it
    silently becomes a partition of its own that matches no rows and is
    indistinguishable from the real one in any log line.

    Entering a tenant scope always leaves system scope, including when nested
    inside one. Platform work that then needs to act as a specific tenant should
    get that tenant's view, not a wider one.
    """
    if not is_valid_tenant_id(tenant_id):
        raise ValueError(f"invalid tenant_id for scope: {tenant_id!r}")
    tokens = _set(tenant_id, False)
    try:
        yield tenant_id
    finally:
        _reset(tokens)


@contextmanager
def system_scope(reason: str) -> Iterator[None]:
    """Act for the platform, across every tenant, for the duration of the block.

    `reason` is required and is logged at debug level. It is not decoration: this
    is the one construct that steps outside the isolation guarantee, and a bare
    `system_scope()` at a call site tells a reviewer nothing about whether it is
    justified.
    """
    if not reason or not reason.strip():
        raise ValueError("system_scope requires a non-empty reason")
    logger.debug("[SCOPE] entering system scope: %s", reason)
    tokens = _set(None, True)
    try:
        yield
    finally:
        _reset(tokens)


@contextmanager
def no_scope() -> Iterator[None]:
    """Drop all scope for the duration of the block.

    Used by tests to assert the fail-closed behaviour, and by nothing else. It
    exists as a named construct so that "this block is deliberately unscoped"
    can be distinguished from "someone forgot".
    """
    tokens = _set(None, False)
    try:
        yield
    finally:
        _reset(tokens)


def bind_request_scope(tenant_id: Optional[str]) -> tuple[Token, Token]:
    """Set the scope for an in-flight request; caller must reset the tokens.

    Separate from `tenant_scope` because ASGI middleware cannot wrap the
    downstream call in a `with` block and still reset in the right task — it
    binds before awaiting the app and resets in its own `finally`.

    A None tenant is accepted and means the request is unscoped, which is the
    correct outcome for a caller we could not attribute to any tenant.
    """
    if tenant_id is not None and not is_valid_tenant_id(tenant_id):
        # Never propagate a malformed id into the GUC: it would silently behave
        # as an empty partition rather than as an error.
        logger.warning("[SCOPE] refusing malformed tenant_id from request: %r", tenant_id)
        tenant_id = None
    return _set(tenant_id, False)


def unbind_request_scope(tokens: tuple[Token, Token]) -> None:
    """Undo `bind_request_scope`."""
    _reset(tokens)


def enter_system_scope(reason: str) -> None:
    """Enter system scope without a matching `with` block.

    For Celery's `task_prerun`/`task_postrun` signal pair, which cannot bracket
    the task body in a context manager. Every task body is platform work — it
    has no request and no user — and the tenant of a row it writes comes from
    the row's own data, not from the worker's ambient scope.

    Pair with `clear_scope()`. A task that ends without one leaks system scope to
    whatever the worker thread runs next, so `task_postrun` must fire even on
    failure — which Celery guarantees.
    """
    logger.debug("[SCOPE] entering system scope: %s", reason)
    _tenant.set(None)
    _system.set(True)


def enter_tenant_scope(tenant_id: str) -> bool:
    """Bind one tenant without a matching `with` block; returns whether it took.

    The Celery twin of `bind_request_scope`, for the same reason: `task_prerun`
    and `task_postrun` are two separate callbacks and cannot bracket the task
    body in a context manager.

    Returns False on a malformed id rather than raising, and the caller then
    falls back to system scope. A worker that refuses to start a task because
    the tenant header was mangled fails a maintenance job closed on a detail
    that has nothing to do with the job — whereas falling back to the scope the
    task would have had before this feature existed is exactly the old
    behaviour. The value is still never propagated: an invalid id reaching the
    GUC would behave as an empty partition, which looks like data loss.
    """
    if not is_valid_tenant_id(tenant_id):
        logger.warning("[SCOPE] refusing malformed tenant_id from task: %r", tenant_id)
        return False
    _tenant.set(tenant_id)
    _system.set(False)
    return True


def clear_scope() -> None:
    """Return to the unscoped default: no tenant, not system."""
    _tenant.set(None)
    _system.set(False)


def platform_command(reason: str):
    """Decorator running a CLI entry point in system scope.

    Operator commands act on the deployment, not on one tenant's data, and they
    have no session to derive a tenant from. Marking the entry point is better
    than a `with` block inside it: the claim "this command is platform-wide" ends
    up in the signature where a reviewer sees it, and it survives an early
    `return` added later.
    """

    def decorate(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with system_scope(reason):
                return fn(*args, **kwargs)

        return wrapper

    return decorate
