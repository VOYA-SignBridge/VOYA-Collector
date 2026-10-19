from fastapi import APIRouter, Request, Response
from starlette.concurrency import run_in_threadpool

from app import activity
from app.rate_limit import client_ip


router = APIRouter()


@router.post("/presence", status_code=204)
async def report_presence(request: Request):
    """Record optional browser-provided coordinates for the active session."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    ip = client_ip(request)
    lat, lon, acc = body.get("lat"), body.get("lon"), body.get("accuracy")
    if lat is not None and lon is not None:
        await run_in_threadpool(activity.record_presence, ip, lat, lon, acc)
    return Response(status_code=204)
