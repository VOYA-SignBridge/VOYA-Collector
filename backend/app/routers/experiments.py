"""
Experiment Tracking API Router — SignBridge MVP

Exposes the storage layer from experiment_tracking_api_revised as FastAPI
endpoints under /api/v1/experiments and /api/v1/models.

Registered in main.py under api_v1 (prefix=/api/v1) only — not bare.

Endpoints:
  POST   /experiments               → create_experiment()
  GET    /experiments               → list_experiments()
  GET    /experiments/{id}          → get_experiment()
  PUT    /experiments/{id}/status   → update_experiment_status()
  POST   /experiments/{id}/metrics  → log_metric() (upsert, returns 200)
  POST   /experiments/{id}/summary  → update_experiment_summary()
  POST   /models                    → create_model_version()
  GET    /models                    → list_models()
  PUT    /models/{id}/status        → update_model_status()
  GET    /models/{dialect}/active   → get_best_model_for_dialect()

RuntimeError mapping:
  - create_experiment:        RuntimeError → 500  (INSERT returned no row)
  - log_metric:               RuntimeError → 500  (upsert returned no row)
  - update_experiment_status: RuntimeError → 404  (experiment_id not found)
  - update_experiment_summary:RuntimeError → 404  (experiment_id not found)
  - create_model_version:     RuntimeError → 500  (UNIQUE/FK violation)
  - update_model_status:      RuntimeError → 404  (version_id not found)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Response
from psycopg2.errors import UniqueViolation
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

from app.storage.experiment_tracking_api_revised import (
    create_experiment,
    get_experiment,
    list_experiments,
    log_metric,
    mark_experiment_starting,
    update_experiment_status,
    update_experiment_summary,
    create_model_version,
    list_models,
    update_model_status,
    get_best_model_for_dialect,
    get_model_version,
    promote_model_version,
)

router = APIRouter(tags=["experiments"])


# ============================================================================
# Request Models
# ============================================================================

class CreateExperimentRequest(BaseModel):
    dialect: str
    subset_path: str
    hyperparameters: Dict[str, Any]
    split_manifest: Optional[Dict[str, Any]] = None


class UpdateExperimentStatusRequest(BaseModel):
    status: str


class UpdateExperimentSummaryRequest(BaseModel):
    best_epoch: int
    best_val_acc: float
    best_val_f1: float


class LogMetricRequest(BaseModel):
    epoch: int
    train_loss: Optional[float] = None
    train_acc: Optional[float] = None
    val_loss: Optional[float] = None
    val_acc: Optional[float] = None
    val_f1: Optional[float] = None
    learning_rate: Optional[float] = None


class CreateModelVersionRequest(BaseModel):
    model_family: str
    experiment_id: int
    dialect: str
    checkpoint_path: str
    feature_contract: Dict[str, Any]
    runtime_env: Optional[Dict[str, Any]] = None
    accuracy: Optional[float] = None
    f1_macro: Optional[float] = None


class UpdateModelStatusRequest(BaseModel):
    status: str


# ============================================================================
# Response Models
# ============================================================================

class EpochMetricResponse(BaseModel):
    epoch: int
    train_loss: Optional[float] = None
    train_acc: Optional[float] = None
    val_loss: Optional[float] = None
    val_acc: Optional[float] = None
    val_f1: Optional[float] = None
    learning_rate: Optional[float] = None
    recorded_at: datetime


class ExperimentSummaryResponse(BaseModel):
    experiment_id: int
    dialect: str
    status: str
    subset_path: str
    best_epoch: Optional[int] = None
    best_val_acc: Optional[float] = None
    best_val_f1: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class ExperimentDetailResponse(ExperimentSummaryResponse):
    split_manifest: Dict[str, Any] = {}
    hyperparameters: Dict[str, Any] = {}
    metrics: List[EpochMetricResponse] = []


class MetricLogResponse(BaseModel):
    metric_id: int
    experiment_id: int
    epoch: int
    val_acc: Optional[float] = None
    val_f1: Optional[float] = None
    recorded_at: datetime


class ExperimentStatusResponse(BaseModel):
    experiment_id: int
    status: str
    completed_at: Optional[datetime] = None


class ExperimentSummaryUpdateResponse(BaseModel):
    experiment_id: int
    best_epoch: int
    best_val_acc: float
    best_val_f1: float


class ModelVersionCreateResponse(BaseModel):
    version_id: int
    model_family: str
    version_string: str
    dialect: str
    status: str
    created_at: datetime


class ModelVersionDetailResponse(BaseModel):
    version_id: int
    model_family: str
    version_string: str
    experiment_id: int
    dialect: str
    checkpoint_path: str
    feature_contract: Dict[str, Any]
    runtime_env: Dict[str, Any]
    accuracy: Optional[float] = None
    f1_macro: Optional[float] = None
    status: str
    created_at: datetime


class ModelVersionStatusResponse(BaseModel):
    version_id: int
    model_family: str
    version_string: str
    dialect: str
    status: str


class StartTrainingResponse(BaseModel):
    experiment_id: int
    status: str
    task_id: str


class PromoteModelResponse(BaseModel):
    version_id: int
    dialect: str
    version_string: str
    checkpoint_path: str
    status: str
    promoted_at: datetime
    reload_status: str  # "ok" | "pending"


# ============================================================================
# Experiment Endpoints
# ============================================================================

@router.post("/experiments", response_model=ExperimentSummaryResponse, status_code=201)
async def create_experiment_endpoint(req: CreateExperimentRequest):
    """Create a new training experiment with status 'pending'."""
    try:
        return create_experiment(
            dialect=req.dialect,
            subset_path=req.subset_path,
            hyperparameters=req.hyperparameters,
            split_manifest=req.split_manifest,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/experiments", response_model=List[ExperimentSummaryResponse])
async def list_experiments_endpoint(
    dialect: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    order_by: str = Query("created_at"),
    limit: int = Query(100),
):
    """List experiments with optional dialect and status filters. Returns [] if no match."""
    try:
        return list_experiments(
            dialect=dialect,
            status=status,
            order_by=order_by,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/experiments/{experiment_id}", response_model=ExperimentDetailResponse)
async def get_experiment_endpoint(experiment_id: int):
    """Get experiment details including all logged per-epoch metrics."""
    result = get_experiment(experiment_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment {experiment_id} not found",
        )
    return result


@router.put("/experiments/{experiment_id}/status", response_model=ExperimentStatusResponse)
async def update_experiment_status_endpoint(
    experiment_id: int,
    req: UpdateExperimentStatusRequest,
):
    """Transition experiment status. Sets completed_at automatically on terminal states (completed/failed)."""
    try:
        return update_experiment_status(experiment_id, req.status)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        # RuntimeError = experiment_id not found (UPDATE RETURNING yielded no row)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/experiments/{experiment_id}/metrics", response_model=MetricLogResponse)
async def log_metric_endpoint(experiment_id: int, req: LogMetricRequest):
    """Log one epoch of training metrics.

    Uses ON CONFLICT upsert — safe to call multiple times for the same epoch.
    Returns HTTP 200 (not 201) because the operation may update an existing row
    rather than always creating one.
    """
    try:
        return log_metric(
            experiment_id=experiment_id,
            epoch=req.epoch,
            train_loss=req.train_loss,
            train_acc=req.train_acc,
            val_loss=req.val_loss,
            val_acc=req.val_acc,
            val_f1=req.val_f1,
            learning_rate=req.learning_rate,
        )
    except RuntimeError as e:
        # RuntimeError = upsert returned no row (unexpected DB failure, not a not-found)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/experiments/{experiment_id}/summary", response_model=ExperimentSummaryUpdateResponse)
async def update_experiment_summary_endpoint(
    experiment_id: int,
    req: UpdateExperimentSummaryRequest,
):
    """Write best-of-run summary fields. Call after update_experiment_status('completed')."""
    try:
        return update_experiment_summary(
            experiment_id=experiment_id,
            best_epoch=req.best_epoch,
            best_val_acc=req.best_val_acc,
            best_val_f1=req.best_val_f1,
        )
    except HTTPException:
        raise
    except RuntimeError as e:
        # RuntimeError = experiment_id not found
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/experiments/{experiment_id}/start",
    response_model=StartTrainingResponse,
    status_code=202,
)
async def start_training_endpoint(experiment_id: int):
    """Enqueue a Celery training job for an existing experiment.

    Allowed only when status is 'pending' or 'failed'. Uses an atomic DB
    UPDATE to prevent double-enqueue from concurrent requests (TOCTOU guard).

    State transitions:
        pending → queued  (this endpoint)
        failed  → queued  (retry path)
        queued  → pending (broker failure rollback)
        queued  → running (worker picks up task)
    """
    from app.train_task import run_training_job  # late import — avoids circular at module load

    # Step 1: 404 guard
    record = get_experiment(experiment_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Experiment {experiment_id} not found",
        )

    # Step 2: fast 409 for non-startable statuses (no extra DB round-trip)
    current_status = record["status"]
    if current_status == "queued":
        raise HTTPException(
            status_code=409,
            detail=f"Experiment {experiment_id} is already queued",
        )
    if current_status == "running":
        raise HTTPException(
            status_code=409,
            detail=f"Experiment {experiment_id} is already running",
        )
    if current_status == "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Experiment {experiment_id} is already completed. Create a new experiment to retrain.",
        )

    # Step 3: atomic claim — TOCTOU guard for concurrent /start requests
    claimed = mark_experiment_starting(experiment_id)
    if claimed is None:
        raise HTTPException(
            status_code=409,
            detail=f"Experiment {experiment_id} could not be started — status changed concurrently",
        )

    # Step 4: enqueue; roll back to 'pending' if broker is unreachable
    try:
        task = run_training_job.delay(experiment_id)
    except Exception as exc:
        try:
            update_experiment_status(experiment_id, "pending")
        except Exception:
            pass
        raise HTTPException(
            status_code=503,
            detail=f"Training queue unavailable — broker connection failed: {exc}",
        )

    logger.info("[TRAIN][%d] enqueued — task_id=%s", experiment_id, task.id)

    return StartTrainingResponse(
        experiment_id=experiment_id,
        status="queued",
        task_id=task.id,
    )


# ============================================================================
# Model Version Endpoints
# ============================================================================

@router.post("/models", response_model=ModelVersionCreateResponse, status_code=201)
async def create_model_version_endpoint(req: CreateModelVersionRequest):
    """Register a trained checkpoint as a candidate model version.

    version_string is auto-generated as '{model_family}-v{experiment_id}'.
    New versions always start with status='candidate'.
    """
    try:
        return create_model_version(
            model_family=req.model_family,
            experiment_id=req.experiment_id,
            dialect=req.dialect,
            checkpoint_path=req.checkpoint_path,
            feature_contract=req.feature_contract,
            runtime_env=req.runtime_env,
            accuracy=req.accuracy,
            f1_macro=req.f1_macro,
        )
    except RuntimeError as e:
        # RuntimeError = INSERT failure (UNIQUE violation on version_string,
        # or FK violation if experiment_id does not exist)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models", response_model=List[ModelVersionDetailResponse])
async def list_models_endpoint(
    dialect: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100),
):
    """List model versions with optional dialect and status filters. Returns [] if no match.

    This endpoint exists for API convenience and UI support — not a core
    provenance requirement. Provenance is anchored by subset_path in
    experiments and feature_contract in model_versions.
    """
    try:
        return list_models(dialect=dialect, status=status, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{dialect}/active", response_model=ModelVersionDetailResponse)
async def get_active_model_endpoint(
    dialect: str,
    status: str = Query("production"),
):
    """Get the most recently registered model for a dialect at a given status tier.

    Primary query for inference routing. Defaults to status='production'.
    Pass ?status=candidate to query unvalidated models.
    """
    try:
        result = get_best_model_for_dialect(dialect=dialect, status=status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No {status} model found for dialect '{dialect}'",
        )
    return result


@router.put("/models/{version_id}/status", response_model=ModelVersionStatusResponse)
async def update_model_status_endpoint(
    version_id: int,
    req: UpdateModelStatusRequest,
):
    """Update model version status. Lifecycle: candidate → production → archived."""
    try:
        return update_model_status(version_id, req.status)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        # RuntimeError = version_id not found
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Promotion helpers
# ============================================================================

async def _call_reload(dialect: str, checkpoint_path: str, version_string: str) -> bool:
    """POST /reload to realtime_service. Returns True on HTTP 200, False on any error.

    Uses a one-shot AsyncClient with a 30 s timeout — model load + warmup can
    take several seconds on CPU. Caller downgrades the response to 202 on False.
    """
    url = f"{settings.realtime_service_url.rstrip('/')}/reload"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                json={
                    "dialect": dialect,
                    "checkpoint_path": checkpoint_path,
                    "version_string": version_string,
                },
            )
        if resp.status_code == 200:
            return True
        logger.warning(
            "[PROMOTE] reload returned status=%d body=%s",
            resp.status_code, resp.text[:200],
        )
        return False
    except Exception as exc:
        logger.warning("[PROMOTE] reload call failed: %s", exc)
        return False


@router.post("/models/{version_id}/promote", response_model=PromoteModelResponse)
async def promote_model_endpoint(version_id: int, response: Response):
    """Promote a candidate model version to production.

    Atomically archives the current production model for the same dialect and
    promotes the target. On success, hot-swaps the model in realtime_service
    via POST /reload.

    Returns HTTP 200 when DB commit and realtime reload both succeed.
    Returns HTTP 202 when DB committed but reload failed — DB is ahead of
    realtime_service; self-heals on container restart.
    """
    # Step 1: Pre-flight checks (404 / 409 / 422)
    record = get_model_version(version_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model version {version_id} not found",
        )

    current_status = record["status"]
    if current_status == "production":
        raise HTTPException(
            status_code=409,
            detail=f"Model version {version_id} is already in production",
        )
    if current_status == "archived":
        raise HTTPException(
            status_code=409,
            detail=f"Model version {version_id} is archived and cannot be promoted",
        )

    checkpoint_path = record["checkpoint_path"]
    if not Path(checkpoint_path).is_file():
        raise HTTPException(
            status_code=422,
            detail=f"Checkpoint not found on backend filesystem: {checkpoint_path}",
        )

    # Step 2: Atomic promotion — archive previous production, promote candidate
    try:
        promoted = promote_model_version(version_id)
    except UniqueViolation:
        # Concurrent promotion for the same dialect committed first
        raise HTTPException(
            status_code=409,
            detail=f"Concurrent promotion conflict for dialect '{record['dialect']}' — retry",
        )

    if promoted is None:
        # Status changed between pre-check and promotion (concurrent modification)
        raise HTTPException(
            status_code=409,
            detail=f"Model version {version_id} status changed concurrently — retry",
        )

    logger.info(
        "[PROMOTE] version_id=%d dialect=%s version=%s checkpoint=%s",
        promoted["version_id"], promoted["dialect"],
        promoted["version_string"], promoted["checkpoint_path"],
    )

    # Step 3: Hot-swap realtime_service — non-fatal on failure
    reload_ok = await _call_reload(
        dialect=promoted["dialect"],
        checkpoint_path=promoted["checkpoint_path"],
        version_string=promoted["version_string"],
    )

    # 200 = DB + reload both succeeded; 202 = DB committed, reload pending
    response.status_code = 200 if reload_ok else 202

    return PromoteModelResponse(
        version_id=promoted["version_id"],
        dialect=promoted["dialect"],
        version_string=promoted["version_string"],
        checkpoint_path=promoted["checkpoint_path"],
        status=promoted["status"],
        promoted_at=promoted["promoted_at"],
        reload_status="ok" if reload_ok else "pending",
    )
