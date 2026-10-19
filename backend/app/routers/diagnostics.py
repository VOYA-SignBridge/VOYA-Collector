from fastapi import APIRouter, Response


router = APIRouter()


@router.post("/test/trigger-hardware-error", status_code=204)
async def trigger_hardware_error():
    """Force the test hardware metric to exercise the Grafana alert path."""
    from app.metrics import hardware_error

    hardware_error.labels(resource="test_camera_1").set(1)
    return Response(status_code=204)
