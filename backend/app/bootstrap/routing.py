from fastapi import APIRouter, FastAPI

from app.routers import (
    admin,
    auth,
    billing,
    capture_sessions,
    classes,
    dataset,
    health,
    inference,
    integrations,
    jobs,
    label_sessions,
    learn,
    legal,
    legal_admin,
    moderation,
    notifications,
    personal_export,
    presence,
    processing_admin,
    realtime_proxy,
    signers_admin,
    sot_admin,
    support,
    tenants,
    training,
    trial,
    tts,
    two_factor,
    upload,
    verification,
    vocabulary,
    workspaces,
)
from app.infrastructure.observability import metrics


_UNVERSIONED_ROUTERS = (
    health.router,
    dataset.router,
    upload.router,
    jobs.router,
    classes.router,
    label_sessions.router,
    inference.router,
    realtime_proxy.router,
    tts.router,
    training.router,
    admin.router,
    sot_admin.router,
    signers_admin.router,
    moderation.router,
    processing_admin.router,
    capture_sessions.router,
    tenants.router,
    workspaces.router,
    billing.router,
    integrations.router,
    verification.router,
    vocabulary.router,
    vocabulary.catalog_router,
    trial.router,
    legal.router,
    legal_admin.router,
    metrics.router,
)

_VERSIONED_ROUTERS = (
    health.router,
    dataset.router,
    upload.router,
    jobs.router,
    classes.router,
    label_sessions.router,
    inference.router,
    auth.router,
    realtime_proxy.router,
    tts.router,
    training.router,
    admin.router,
    sot_admin.router,
    signers_admin.router,
    moderation.router,
    processing_admin.router,
    capture_sessions.router,
    tenants.router,
    workspaces.router,
    billing.router,
    integrations.router,
    verification.router,
    vocabulary.router,
    vocabulary.catalog_router,
    trial.router,
    legal.router,
    learn.router,
    legal_admin.router,
    notifications.router,
    personal_export.router,
    support.router,
    two_factor.router,
    presence.router,
)


def register_routers(app: FastAPI) -> APIRouter:
    """Register legacy and versioned routes without changing public URLs."""
    for router in _UNVERSIONED_ROUTERS:
        app.include_router(router)

    api_v1 = APIRouter(prefix="/api/v1")
    for router in _VERSIONED_ROUTERS:
        api_v1.include_router(router)
    app.include_router(api_v1)
    return api_v1
