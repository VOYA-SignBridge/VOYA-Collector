from fastapi import APIRouter, FastAPI

from app import metrics
from app.routers import (
    admin,
    auth,
    billing,
    capture_sessions,
    classes,
    dataset,
    diagnostics,
    health,
    inference,
    integrations,
    jobs,
    label_sessions,
    learn as learn_router,
    legal as legal_router,
    legal_admin,
    moderation,
    notifications as notifications_router,
    personal_export as personal_export_router,
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
    two_factor as two_factor_router,
    upload,
    verification,
    vocabulary,
    workspaces as workspaces_router,
)


# Keep route order identical to the former app.main declarations. Besides
# preserving OpenAPI output, ordering matters when static and parameterized
# paths overlap.
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
    workspaces_router.router,
    billing.router,
    integrations.router,
    verification.router,
    vocabulary.router,
    vocabulary.catalog_router,
    trial.router,
    legal_router.router,
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
    workspaces_router.router,
    billing.router,
    integrations.router,
    verification.router,
    vocabulary.router,
    vocabulary.catalog_router,
    trial.router,
    legal_router.router,
    learn_router.router,
    legal_admin.router,
    notifications_router.router,
    personal_export_router.router,
    support.router,
    two_factor_router.router,
    presence.router,
    diagnostics.router,
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
