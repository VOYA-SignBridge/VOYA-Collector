"""
Training Pipeline API Router
Auto-loads dataset, manages training jobs, and streams real-time progress.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query

from app.infrastructure.redis.connection import get_redis_client
from app.modules.identity import get_current_user, get_user_from_token, require_admin
from app.modules.dataset import catalog_service, preparation_service, provenance as dataset_provenance, research_catalog
from app.modules.training import inference_service, job_service, progress_service, submission_service
from app.modules.training.inference_service import (
    _MODEL_NAME_TO_REGISTRY_KEY,
    _import_models_registry,
    _load_model_from_checkpoint,
)
from app.modules.training.job_service import (
    TERMINAL_STATUSES,
    _ensure_job_loaded,
    _job_from_db_row,
    _metrics_from_db_rows,
    _persist_job,
    _persist_job_sync,
    _persist_metric_sync,
    _split_prov_from_row,
    restore_jobs_from_db,
    training_jobs,
)
from app.modules.training.provenance_service import (
    _CRITERION_LABELS,
    _determinism_summary,
    _load_research_validity,
    _provenance_checks,
    build_provenance_report,
)
from app.modules.training.promotion_service import (
    CHECKPOINTS_DIR,
    REGISTRY_PATH,
    REALTIME_CHECKPOINTS_DIR,
    REALTIME_CONTAINER_CHECKPOINTS,
    CheckpointCopyError,
    _copy_checkpoint_to_deployment,
    _notify_realtime_service_reload,
    _registry_display_name,
    _update_registry,
    deploy_checkpoint,
)
from app.modules.training.schemas import (
    DatasetInfo,
    DatasetPrepareRequest,
    PromoteResponse,
    SplitProvenance,
    TrainedModelPredictRequest,
    TrainedModelPredictResponse,
    TrainingConfig,
    TrainingJob,
    TrainingMetrics,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training", tags=["training"])

# ============================================================================
# Redis (chỉ dùng để gửi tín hiệu cancel tới trainer container;
# job execution đi qua Celery queue "training")
# ============================================================================

# Compatibility injection point for tests/legacy callers. Runtime code falls
# back to the shared lazy infrastructure client instead of owning a connection.
redis_client = None

# Đường dẫn dataset - tính từ docker volume mount
# In Docker: . mounts to /workspace (root directory)
# Training subprocess runs with cwd=/workspace/processed
WORKSPACE_ROOT = Path("/workspace")
DATASET_ROOT = WORKSPACE_ROOT / "dataset"
SAMPLES_CSV = DATASET_ROOT / "samples.csv"
LABELS_CSV = DATASET_ROOT / "labels.csv"
SPLITS_DIR = WORKSPACE_ROOT / "processed" / "splits"
OUTPUTS_DIR = WORKSPACE_ROOT / "processed" / "train_utils" / "outputs"
# ============================================================================
# Helper Functions
# ============================================================================

def _load_samples_and_labels() -> tuple[List[Dict], List[Dict]]:
    return catalog_service.load_samples_and_labels(SAMPLES_CSV, LABELS_CSV)


def _get_dialects_by_language() -> Dict[str, List[str]]:
    _, labels = _load_samples_and_labels()
    return catalog_service.dialects_by_language(labels)


def _provenance_from_dir(split_dir: Path) -> SplitProvenance:
    return dataset_provenance.provenance_from_dir(split_dir)


def _root_split_provenance() -> SplitProvenance:
    return dataset_provenance.root_split_provenance(WORKSPACE_ROOT)


def _effective_split_provenance(dialect: Optional[str]) -> SplitProvenance:
    return dataset_provenance.effective_split_provenance(dialect, WORKSPACE_ROOT)


def _trainable_dialects_from_splits() -> Dict[str, int]:
    return dataset_provenance.trainable_dialects(WORKSPACE_ROOT)


def _research_splits() -> List[Dict[str, Any]]:
    return research_catalog.research_splits(WORKSPACE_ROOT)


def _evaluation_protocols() -> List[Dict[str, Any]]:
    return research_catalog.evaluation_protocols(WORKSPACE_ROOT)


def _profiles_for_dialects(dialects: List[str]) -> Tuple[List[str], List[str]]:
    return catalog_service.profiles_for_dialects(dialects, labels_csv=LABELS_CSV)


@router.post("/dataset/prepare")
async def start_dataset_preparation(
    body: DatasetPrepareRequest,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Sinh manifest + split triển khai + split nghiên cứu + fold LOSO.

    Trước đây phải chạy bốn script CLI đúng thứ tự, nên người thu dữ liệu qua
    nền tảng không tự biến nó thành thứ huấn luyện được. Một lần bấm sinh cả
    đường dùng hằng ngày lẫn đường nghiên cứu, từ cùng một manifest, nên hai
    đường không thể lệch nhau về việc đang mô tả bộ dữ liệu nào.
    """
    try:
        result = await asyncio.to_thread(
            preparation_service.queue_preparation,
            dialects=body.dialects,
            profiles=body.profiles,
            seed=body.seed,
            profiles_for_dialects=_profiles_for_dialects,
        )
    except preparation_service.UnsupportedDialectsError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Phương ngữ đã chọn chưa được gán nhóm nhận dạng "
                f"({', '.join(exc.dialects) or 'không rõ'}), nên chưa chuẩn bị được. "
                "Hãy gán recognition_profile cho các nhãn của phương ngữ này trước."
            ),
        ) from exc
    logger.info("[PREP] admin=%s bắt đầu run=%s version=%s",
                current_user.get("username"), result["run_id"], result["manifest_version"])
    return result


@router.get("/dataset/prepare/{run_id}")
async def get_dataset_preparation(
    run_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Tiến độ và kết quả của một lần chuẩn bị dữ liệu."""
    report = await asyncio.to_thread(preparation_service.preparation_report, run_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy lần chuẩn bị {run_id}")
    return report


@router.get("/protocols")
async def list_evaluation_protocols(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Bộ fold nhiều lần chạy (LOSO...) — cơ sở của các bảng trong báo cáo."""
    return await asyncio.to_thread(_evaluation_protocols)


@router.get("/splits")
async def list_research_splits(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Split đã versioned mà chế độ nghiên cứu có thể chạy trên đó."""
    return await asyncio.to_thread(_research_splits)


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/dataset-info", response_model=DatasetInfo)
async def get_dataset_info(
    dialect: Optional[str] = Query(None, description="Filter by dialect"),
    language: Optional[str] = Query("vn", description="Filter by language"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> DatasetInfo:
    """
    Lấy thông tin dataset hiện tại

    Auto-load từ folder dataset, không cần upload
    """
    try:
        return await asyncio.to_thread(
            catalog_service.build_dataset_info,
            dialect=dialect,
            language=language,
            effective_provenance=_effective_split_provenance,
            samples_csv=SAMPLES_CSV,
            labels_csv=LABELS_CSV,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tải dataset: {str(e)}")


@router.post("/start", response_model=TrainingJob)
async def start_training(
    config: TrainingConfig,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TrainingJob:
    """
    Bắt đầu training job (enqueue to queue)

    Tạo job ID, thêm vào queue, return job info
    """
    try:
        return await submission_service.submit_training_job(
            config,
            auth_user_id=str(current_user.get("id") or "") or None,
            username=current_user.get("username"),
            jobs=training_jobs,
            research_splits=_research_splits,
            trainable_dialects=_trainable_dialects_from_splits,
            effective_provenance=_effective_split_provenance,
            persist_job=_persist_job,
        )
    except submission_service.SubmissionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except submission_service.QueueUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail="Hàng đợi training tạm thời không khả dụng — thử lại sau",
        ) from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi bắt đầu training: {str(e)}")


@router.get("/jobs")
async def list_jobs(
    limit: int = Query(100, ge=1, le=500),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Lịch sử training jobs (mới nhất trước), kèm username người chạy."""
    try:
        return await job_service.list_job_history(limit)
    except job_service.JobStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/jobs/{job_id}", response_model=TrainingJob)
async def get_job_status(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TrainingJob:
    """Lấy trạng thái training job (fallback sang DB nếu không có trong memory)"""
    try:
        return await job_service.load_job_status(
            job_id,
            ensure_job=_ensure_job_loaded,
            persist_job=_persist_job,
            load_checkpoint=inference_service.load_checkpoint,
        )
    except job_service.JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/metrics", response_model=List[TrainingMetrics])
async def get_job_metrics(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[TrainingMetrics]:
    """Lấy metrics của training job (fallback sang DB nếu không có trong memory)"""
    try:
        return await job_service.load_job_metrics(job_id, ensure_job=_ensure_job_loaded)
    except job_service.JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/evaluation")
async def get_job_evaluation(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Per-class breakdown + confusion matrix trên test set (Step 7).

    Trả về {"available": false} thay vì 404 khi job cũ chưa có dữ liệu này
    (các job train trước khi tính năng evaluation được thêm).
    """
    try:
        return await job_service.load_job_evaluation(job_id, ensure_job=_ensure_job_loaded)
    except job_service.JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except job_service.JobStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/provenance")
async def get_job_provenance(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> dict:
    """Nguồn gốc & khả năng tái lập của model (Step 7).

    Đọc thẳng từ checkpoint chứ không từ bảng job: checkpoint mới là thứ được
    promote, xuất bản và nạp lại — nên cái nó mang theo mới là cái thực sự tái
    lập được. Trả {"available": false} cho job cũ chưa ghi provenance, giống
    cách endpoint evaluation xử lý.
    """
    job_info = await _ensure_job_loaded(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail=f"Training job {job_id} không tìm thấy")

    job = job_info["job"]
    if not job.checkpoint_path or not Path(job.checkpoint_path).exists():
        return {"available": False, "job_id": job_id}

    try:
        ckpt = await asyncio.to_thread(
            inference_service.load_checkpoint, job.checkpoint_path
        )
    except Exception as e:
        logger.warning("job=%s không đọc được provenance: %s", job_id, e)
        return {"available": False, "job_id": job_id}

    if not isinstance(ckpt, dict) or "git_commit" not in ckpt:
        # Checkpoint có trước khi provenance được ghi — nói rõ thay vì hiện ô trống.
        return {"available": False, "job_id": job_id}

    return build_provenance_report(job_id, ckpt, WORKSPACE_ROOT)


@router.get("/queue/status")
async def get_queue_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> dict:
    """Get training queue status (từ Postgres — trainer container ghi trạng thái)"""
    return await job_service.queue_status()


@router.post("/jobs/{job_id}/cancel", response_model=TrainingJob)
async def cancel_training_job(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TrainingJob:
    """Hủy training job.

    Training chạy trong container trainer riêng, nên hủy = set Redis key
    ``training:cancel:{job_id}`` — vòng giám sát của trainer thấy key này
    trong ≤2s và terminate subprocess (SIGKILL sau 30s nếu lì).
    DB được đánh dấu cancelled ngay để UI phản hồi tức thì.
    """
    logger.info("job=%s cancel requested by user=%s", job_id, current_user.get("username"))
    try:
        return await job_service.cancel_job(
            job_id,
            current_user.get("username", "user"),
            redis_client=redis_client or get_redis_client(),
            ensure_job=_ensure_job_loaded,
            persist_job=_persist_job,
        )
    except job_service.JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except job_service.JobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/jobs/{job_id}")
async def delete_training_job_endpoint(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Xóa training job khỏi lịch sử huấn luyện.

    Chỉ cho phép xóa job đã kết thúc (completed/failed/cancelled) — job đang
    chạy/đang chờ phải hủy trước (xem cancel_training_job). Không xóa
    checkpoint file trên đĩa (xem delete_training_job trong metadata_db.py).
    """
    try:
        await job_service.delete_job(job_id, ensure_job=_ensure_job_loaded)
    except job_service.JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except job_service.JobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except job_service.JobStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    logger.info("job=%s deleted from history by user=%s", job_id, current_user.get("username"))
    return {"success": True, "job_id": job_id}


@router.post("/jobs/{job_id}/promote", response_model=PromoteResponse)
async def promote_training_job(
    job_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> PromoteResponse:
    """Promote model của job lên tab nhận diện realtime (ADMIN ONLY).

    Luồng: copy đúng checkpoint của job → config/checkpoints của realtime
    service → ghi entry vào models.json (bền qua restart) → gọi /reload để
    hot-swap → ghi promoted_at vào DB.
    """
    job_info = await _ensure_job_loaded(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail=f"Training job {job_id} không tìm thấy")

    job = job_info["job"]

    if job.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Chỉ promote được job đã hoàn thành (trạng thái hiện tại: {job.status})",
        )

    if not job.checkpoint_path or not Path(job.checkpoint_path).exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy checkpoint của job này")

    # Load checkpoint để validate model type. Realtime service dựng kiến trúc
    # ngoài TCN từ chính registry đã huấn luyện nó, nên chỉ cần chặn những
    # model_type không nhận ra — /reload vẫn validate + warmup trước khi swap.
    src_path = Path(job.checkpoint_path)
    try:
        ckpt = await asyncio.to_thread(inference_service.load_checkpoint, src_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không đọc được checkpoint: {e}")

    model_type = str(ckpt.get("model_type", "TCN")).replace(" (legacy)", "").strip()
    if model_type.lower() not in _MODEL_NAME_TO_REGISTRY_KEY:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Không nhận ra kiến trúc '{model_type}' — realtime service hỗ trợ: "
                f"{', '.join(sorted(set(_MODEL_NAME_TO_REGISTRY_KEY.values())))}. "
                "Model vẫn dùng được qua nút Test Model ở Step 7."
            ),
        )

    # Slot realtime được đánh khóa theo dialect (giống lúc startup load từ DB):
    # promote model mới cho "hoa-de" sẽ thay model "hoa-de" đang chạy, không
    # thêm một lựa chọn trùng vào tab nhận diện.
    dialect = (job.config.dialects[0] if job.config.dialects else "multi")
    language = (job.config.languages[0] if job.config.languages else "vn")
    try:
        deployment = await asyncio.to_thread(
            deploy_checkpoint,
            src_path=src_path,
            job_id=job_id,
            model_type=model_type,
            dialect=dialect,
            language=language,
            ckpt=ckpt,
            copy_checkpoint=_copy_checkpoint_to_deployment,
            registry_display_name=_registry_display_name,
            update_registry=_update_registry,
            notify_reload=_notify_realtime_service_reload,
            checkpoints_dir=REALTIME_CHECKPOINTS_DIR,
            container_checkpoints_dir=REALTIME_CONTAINER_CHECKPOINTS,
        )
    except CheckpointCopyError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # 4. Ghi nhận promotion. checkpoint_path trỏ sang bản deployed để:
    #    - retention sweep dọn outputs/ không thể phá model đã promote
    #    - Step 7 test modal vẫn hoạt động sau khi outputs/ bị dọn
    job.promoted_at = datetime.now().isoformat()
    job.checkpoint_path = deployment.deployed_path
    await _persist_job(job)

    # 5. Publish bản promoted lên Google Drive (background, best-effort):
    #    models/<tên model>/Deploy <thời điểm>/ gồm checkpoint + manifest inference
    try:
        from app.training_tasks import backup_promoted_checkpoint_task

        backup_promoted_checkpoint_task.delay(
            job_id=job_id,
            checkpoint_path=deployment.deployed_path,
            model_id=deployment.model_id,
            display_name=deployment.display_name,
            dialect=dialect,
            language=language,
            promoted_at=job.promoted_at,
        )
        logger.info("job=%s GDrive backup dispatched for promoted model", job_id)
    except Exception as e:
        logger.warning("job=%s GDrive backup dispatch failed (promotion vẫn OK): %s", job_id, e)

    logger.info(
        "job=%s promoted by admin=%s registry=%s reload=%s",
        job_id,
        current_user.get("username"),
        deployment.registry_updated,
        deployment.realtime_reloaded,
    )

    return PromoteResponse(
        job=job,
        model_id=deployment.model_id,
        deployed_checkpoint=deployment.deployed_path,
        registry_updated=deployment.registry_updated,
        realtime_reloaded=deployment.realtime_reloaded,
        message=deployment.message,
    )


@router.websocket("/ws/{job_id}")
async def websocket_training_progress(websocket: WebSocket, job_id: str, token: str = Query(default="")):
    """
    WebSocket để stream real-time training progress

    Gửi metrics, epoch progress.
    Auth: browsers cannot set headers on WS. Cookie-auth SPA has no JS-readable
    token (httpOnly), so prefer the access COOKIE the browser sends on the WS
    handshake; fall back to ?token= for legacy/API clients.
    """
    from app.modules.identity import ACCESS_COOKIE

    effective_token = token or websocket.cookies.get(ACCESS_COOKIE, "")
    user = await asyncio.to_thread(get_user_from_token, effective_token) if effective_token else None
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    job_info = await _ensure_job_loaded(job_id)
    if not job_info:
        await websocket.close(code=4004, reason="Job not found")
        return

    await websocket.accept()

    try:
        await progress_service.stream_job_progress(
            job_id,
            websocket.send_json,
            ensure_job=_ensure_job_loaded,
        )
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("WebSocket error: %s", e)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ============================================================================
# Training Model Inference (for Step 7 test modal)
# ============================================================================

@router.post("/jobs/{job_id}/predict", response_model=TrainedModelPredictResponse)
async def predict_trained_model(
    job_id: str,
    request_data: TrainedModelPredictRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TrainedModelPredictResponse:
    """Predict using trained model checkpoint (for Step 7 test modal).

    Load checkpoint locally and run inference without requiring registry entry.
    """
    # Validate job exists (fallback sang DB — job vẫn test được sau khi backend restart)
    job_info = await _ensure_job_loaded(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail=f"Training job {job_id} not found")

    job = job_info.get("job")
    if not job:
        raise HTTPException(status_code=404, detail="Job object not found")

    checkpoint_path = job.checkpoint_path
    if not checkpoint_path or not Path(checkpoint_path).exists():
        raise HTTPException(status_code=404, detail="Model checkpoint not found")

    try:
        return await asyncio.to_thread(
            inference_service.predict_checkpoint,
            Path(checkpoint_path),
            request_data.frames,
            workspace_root=WORKSPACE_ROOT,
            labels_csv=LABELS_CSV,
        )
    except Exception as e:
        logger.exception("job=%s inference error", job_id)
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")
