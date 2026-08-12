from typing import Any, Dict

from fastapi import APIRouter, Depends
from app.auth import get_current_user
from app.worker import celery_app
from app.api_validation import validate_job_id

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job_status(job_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Query job status from Celery

    Authenticated because the payload includes `traceback` and the stringified
    exception on failure. A traceback names filesystem paths, module layout and
    library versions — an inventory of the deployment, handed to anyone who can
    guess a job id. The only caller is the upload poller in `frontend/src/api/
    jobs.ts`, which always runs with a session (uploading requires one), so the
    guard costs nothing.
    """
    from celery.result import AsyncResult
    job_id = validate_job_id(job_id)
    result = AsyncResult(job_id, app=celery_app)

    response = {
        "job_id": job_id,
        "status": result.status,   # PENDING, STARTED, SUCCESS, FAILURE, RETRY
        "result": result.result if result.successful() else None,
        "traceback": str(result.traceback) if result.failed() else None,
        # Extra fields (non-breaking): useful when result is FAILURE and result payload is not returned
        "error": str(result.result) if result.failed() else None,
    }
    return response


@router.get("/")
def list_jobs(limit: int = 10):
    """
    ⚠️ Celery không lưu job history mặc định.
    Để list nhiều job, bạn cần kết hợp Redis backend hoặc DB backend.
    Ở đây chỉ demo nên chỉ trả thông báo.
    """
    return {"message": f"Listing last {limit} jobs not implemented (use DB backend)."}
