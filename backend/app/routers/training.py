"""
Training Pipeline API Router
Auto-loads dataset, manages training jobs, and streams real-time progress.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query

from app.infrastructure.redis.connection import get_redis_client
from app.auth import get_current_user, get_user_from_token, require_admin
from app.modules.dataset import catalog_service, preparation_service, provenance as dataset_provenance, research_catalog
from app.modules.dataset.vocabulary_registry import assert_can_use_dialect
from app.modules.security.quota_deps import guard_quota, tenant_of
from app.modules.security.rate_limit_deps import limit_training
from app.modules.saas.tenant_context import require_tenant
from app.modules.training import (
    inference_service,
    job_service,
    progress_service,
    promotion_service,
    provenance_service,
    submission_service,
)
from app.modules.training.checkpoint_io import load_checkpoint
from app.modules.training.tasks import OUTPUTS_DIR
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
from app.modules.training.submission_service import eligible_class_counts as _eligible_class_counts
from app.modules.training.job_service import evaluation_label_names as _evaluation_label_names
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


def _load_samples_and_labels() -> tuple[List[Dict], List[Dict]]:
    return catalog_service.load_samples_and_labels(SAMPLES_CSV, LABELS_CSV)


def _rows_of_tenant(rows: List[Dict], tenant_id: str) -> List[Dict]:
    from app.modules.saas.tenancy import tenant_id_of

    return [row for row in rows if tenant_id_of(row) == tenant_id]


def _get_dialects_by_language(tenant_id: Optional[str] = None) -> Dict[str, List[str]]:
    _, labels = _load_samples_and_labels()
    if tenant_id is not None:
        labels = _rows_of_tenant(labels, tenant_id)
    return catalog_service.dialects_by_language(labels)


def _provenance_from_dir(split_dir: Path) -> SplitProvenance:
    return dataset_provenance.provenance_from_dir(split_dir)


def _root_split_provenance() -> SplitProvenance:
    return dataset_provenance.root_split_provenance(WORKSPACE_ROOT)


def _effective_split_provenance(dialect: Optional[str]) -> SplitProvenance:
    return dataset_provenance.effective_split_provenance(dialect, WORKSPACE_ROOT)


def _trainable_dialects_from_splits() -> Dict[str, int]:
    return dataset_provenance.trainable_dialects(WORKSPACE_ROOT)


def _split_classes_below_floor(dialects, nguong, thu_muc=None):
    return dataset_provenance.split_classes_below_floor(
        dialects, nguong, Path(thu_muc) if thu_muc is not None else SPLITS_DIR
    )


def _split_evidence_problems(dialects, nguong, thu_muc=None):
    return dataset_provenance.split_evidence_problems(
        dialects, nguong, Path(thu_muc) if thu_muc is not None else SPLITS_DIR
    )


def _split_snapshot(thu_muc=None):
    return dataset_provenance.split_snapshot(
        Path(thu_muc) if thu_muc is not None else SPLITS_DIR
    )


def _operational_splits(tenant_id: str) -> List[Dict[str, Any]]:
    return dataset_provenance.operational_splits(
        tenant_id, SPLITS_DIR, WORKSPACE_ROOT
    )


def _split_provenance(**kwargs) -> SplitProvenance:
    return _effective_split_provenance(kwargs.get("dialect"))


def _research_splits() -> List[Dict[str, Any]]:
    return research_catalog.research_splits(WORKSPACE_ROOT)


def _evaluation_protocols() -> List[Dict[str, Any]]:
    return research_catalog.evaluation_protocols(WORKSPACE_ROOT)


def _profiles_for_dialects(
    dialects: List[str], tenant_id: Optional[str] = None
) -> Tuple[List[str], List[str]]:
    _, labels = _load_samples_and_labels()
    if tenant_id is not None:
        labels = _rows_of_tenant(labels, tenant_id)
    wanted = {str(value).strip() for value in dialects if str(value).strip()}
    by_dialect: Dict[str, set] = {}
    for label in labels:
        dialect = str(label.get("dialect") or "").strip()
        profile = str(label.get("recognition_profile") or "").strip()
        if dialect in wanted and profile:
            by_dialect.setdefault(dialect, set()).add(profile)
    profiles: List[str] = []
    unsupported: List[str] = []
    for dialect in sorted(wanted):
        found = {
            profile
            for profile in by_dialect.get(dialect, set())
            if profile != "legacy_unassigned"
        }
        if found:
            profiles.extend(found)
        else:
            unsupported.append(dialect)
    return sorted(set(profiles)), unsupported


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
    tenant_id = require_tenant()
    user_id = str(current_user.get("id") or "") or None
    if not body.dialects:
        raise HTTPException(status_code=400, detail="Chưa chọn phương ngữ nào.")
    for dialect in body.dialects or []:
        try:
            if tenant_id == "default":
                assert_can_use_dialect(dialect, user_id)
            else:
                assert_can_use_dialect(dialect, user_id, tenant_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        result = await asyncio.to_thread(
            preparation_service.queue_preparation,
            dialects=body.dialects,
            profiles=body.profiles,
            seed=body.seed,
            profiles_for_dialects=lambda dialects: _profiles_for_dialects(dialects, tenant_id),
            tenant_id=tenant_id,
            minimum_samples=body.min_samples_per_class or 25,
            with_research=body.with_research,
            requested_by=user_id or "",
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
    logger.info(
        "[PREP] admin=%s tenant=%s bắt đầu run=%s",
        current_user.get("username"), tenant_id, result["run_id"],
    )
    return result


@router.get("/dataset/prepare/{run_id}")
async def get_dataset_preparation(
    run_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Tiến độ và kết quả của một lần chuẩn bị dữ liệu."""
    from app.dataset_prep_tasks import read_report

    report = await asyncio.to_thread(read_report, run_id)
    if report is None or str(report.get("tenant_id") or "") != require_tenant():
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


@router.get("/splits/operational")
async def list_operational_splits(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(_operational_splits, require_tenant())


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
        tenant_id = require_tenant()
        samples, labels = await asyncio.to_thread(_load_samples_and_labels)
        samples = _rows_of_tenant(samples, tenant_id)
        labels = _rows_of_tenant(labels, tenant_id)
        dialects_map = await asyncio.to_thread(_get_dialects_by_language, tenant_id)
        if dialect or language:
            matching = {
                str(label.get("class_uid") or "").strip()
                for label in labels
                if (
                    not language
                    or (str(label.get("language") or "vn").strip() or "vn") == language
                )
                and (
                    not dialect
                    or str(label.get("dialect") or "").strip() == dialect
                )
            }
            samples = [
                row
                for row in samples
                if str(row.get("class_uid") or "").strip() in matching
            ]
        class_counts = Counter(
            str(row.get("class_uid") or "").strip()
            for row in samples
            if str(row.get("class_uid") or "").strip()
        )
        uid_to_dialect = {
            str(label.get("class_uid") or "").strip(): str(
                label.get("dialect") or ""
            ).strip()
            for label in labels
        }
        samples_by_dialect = Counter(
            uid_to_dialect.get(str(row.get("class_uid") or "").strip(), "")
            for row in samples
        )
        samples_by_dialect.pop("", None)
        provenance = await asyncio.to_thread(_split_provenance, tenant_id=tenant_id)
        return DatasetInfo(
            total_samples=len(samples),
            total_classes=len(class_counts),
            languages=list(dialects_map),
            dialects=dialects_map,
            class_distribution=dict(class_counts),
            samples_by_dialect=dict(samples_by_dialect),
            split_provenance=provenance,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tải dataset: {str(e)}")


@router.post(
    "/start",
    response_model=TrainingJob,
    dependencies=[Depends(limit_training)],
)
async def start_training(
    config: TrainingConfig,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TrainingJob:
    """
    Bắt đầu training job (enqueue to queue)

    Tạo job ID, thêm vào queue, return job info
    """
    working_tenant = require_tenant()
    guard_quota(current_user, "training_jobs_running")
    guard_quota(current_user, "training_jobs_queued")
    if working_tenant != tenant_of(current_user):
        guard_quota(current_user, "training_jobs_running", tenant_id=working_tenant)
        guard_quota(current_user, "training_jobs_queued", tenant_id=working_tenant)
    for dialect in config.dialects or []:
        try:
            assert_can_use_dialect(dialect, str(current_user.get("id") or ""))
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        return await submission_service.submit_training_job(
            config,
            auth_user_id=str(current_user.get("id") or "") or None,
            username=current_user.get("username"),
            tenant_id=working_tenant,
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
            load_checkpoint=load_checkpoint,
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
    try:
        return await provenance_service.load_job_provenance(
            job_id,
            ensure_job=_ensure_job_loaded,
            load_checkpoint=load_checkpoint,
            workspace_root=WORKSPACE_ROOT,
        )
    except provenance_service.ProvenanceJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
    try:
        response = await promotion_service.promote_job(
            job_id,
            ensure_job=_ensure_job_loaded,
            persist_job=_persist_job,
            load_checkpoint=load_checkpoint,
            model_name_map=_MODEL_NAME_TO_REGISTRY_KEY,
            copy_checkpoint=_copy_checkpoint_to_deployment,
            registry_display_name=_registry_display_name,
            update_registry=_update_registry,
            notify_reload=_notify_realtime_service_reload,
            checkpoints_dir=REALTIME_CHECKPOINTS_DIR,
            container_checkpoints_dir=REALTIME_CONTAINER_CHECKPOINTS,
        )
    except promotion_service.PromotionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except promotion_service.PromotionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except promotion_service.PromotionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except promotion_service.PromotionStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info("job=%s promoted by admin=%s", job_id, current_user.get("username"))
    return response


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
    from app.modules.saas import tenant_middleware
    from app.modules.saas.tenant_context import tenant_scope

    effective_token = token or websocket.cookies.get(ACCESS_COOKIE, "")
    user = await asyncio.to_thread(get_user_from_token, effective_token) if effective_token else None
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    working_tenant = await asyncio.to_thread(
        tenant_middleware._tenant_of_user, str(user.get("id") or "")
    )
    if not working_tenant:
        await websocket.close(code=4001, reason="Tenant unavailable")
        return

    # HTTP requests receive this scope from TenantScopeMiddleware. WebSockets do
    # not pass through that middleware, so keep the same active-tenant scope for
    # both the ownership check and every subsequent progress read.
    with tenant_scope(working_tenant):
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
    try:
        return await inference_service.predict_job(
            job_id,
            request_data.frames,
            ensure_job=_ensure_job_loaded,
            predict=inference_service.predict_checkpoint,
            workspace_root=WORKSPACE_ROOT,
            labels_csv=LABELS_CSV,
        )
    except inference_service.InferenceJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as e:
        logger.exception("job=%s inference error", job_id)
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")
