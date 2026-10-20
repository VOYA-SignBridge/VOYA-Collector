"""Tenant-scope propagation for Celery tasks.

A task runs in a worker long after the request that dispatched it is gone, so
the tenant it was acting for must be carried on the message itself. This stamps
the dispatching tenant onto the task headers at publish time and re-enters that
scope in the worker before the task body runs — without it, row-level security
shows the task zero rows and a job reports success having done nothing.

Ported from the pre-refactor monolith ``app.worker`` into son_arrange's celery
layout; ``app.tenant_context`` now lives at ``app.modules.saas.tenant_context``.
"""

from __future__ import annotations

import structlog
from asgi_correlation_id import correlation_id
from celery.signals import before_task_publish, task_postrun, task_prerun

from app.modules.saas.tenant_context import (
    clear_scope,
    current_tenant,
    enter_system_scope,
    enter_tenant_scope,
)

#: Message header carrying the tenant a task was dispatched for.
#: A header rather than a task argument on purpose: every one of the 40-odd
#: `.delay()` / `.apply_async()` call sites would otherwise need editing, and
#: the one that got missed would be a silent cross-tenant write rather than a
#: type error.
TENANT_HEADER = "voya_tenant"


@before_task_publish.connect
def stamp_tenant_on_task(headers=None, **_kwargs):
    """Record which tenant asked for this task, at dispatch time.

    Only a real tenant scope is stamped. Platform work (beat schedules, CLI,
    startup sync) is in system scope, ``current_tenant()`` returns None, and no
    header is added — so those tasks keep the behaviour they have always had.
    """
    tenant = current_tenant()
    if tenant and headers is not None:
        headers[TENANT_HEADER] = tenant


@task_prerun.connect
def setup_structlog_context(task_id, task, *args, **kwargs):
    # request_id from kwargs if the API passed it, else fall back to task_id.
    req_id = kwargs.get("kwargs", {}).get("request_id", task_id)
    correlation_id.set(req_id)
    structlog.contextvars.bind_contextvars(task_id=task_id, task_name=task.name)
    # Tenant scope for the task body, in the one place a task added later cannot
    # forget it. `platform_wide` tasks read whole tables to build ONE artifact
    # for the deployment, so they run in system scope regardless of the header;
    # otherwise a present header narrows the scope to that tenant, and its
    # absence means platform work (system scope, as before the header existed).
    if getattr(task, "platform_wide", False):
        enter_system_scope(f"celery:{task.name} (platform_wide)")
        return
    tenant = getattr(task.request, TENANT_HEADER, None)
    if tenant and enter_tenant_scope(tenant):
        structlog.contextvars.bind_contextvars(tenant_id=tenant)
        return
    enter_system_scope(f"celery:{task.name}")


@task_postrun.connect
def clear_structlog_context(*args, **kwargs):
    structlog.contextvars.clear_contextvars()
    correlation_id.set(None)
    # Must run even when the task raised, or a prefork child keeps system scope
    # for whatever it picks up next. Celery fires task_postrun on both paths.
    clear_scope()
