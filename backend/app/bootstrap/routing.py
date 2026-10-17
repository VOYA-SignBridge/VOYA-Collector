from fastapi import APIRouter, FastAPI

from app.routers import (
    admin,
    auth,
    classes,
    dataset,
    health,
    inference,
    jobs,
    presence,
    realtime_proxy,
    training,
    tts,
    upload,
)


_UNVERSIONED_ROUTERS = (
    health.router,
    dataset.router,
    upload.router,
    jobs.router,
    classes.router,
    inference.router,
    realtime_proxy.router,
    tts.router,
    training.router,
    admin.router,
)

_VERSIONED_ROUTERS = (
    health.router,
    dataset.router,
    upload.router,
    jobs.router,
    classes.router,
    inference.router,
    auth.router,
    realtime_proxy.router,
    tts.router,
    training.router,
    admin.router,
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
