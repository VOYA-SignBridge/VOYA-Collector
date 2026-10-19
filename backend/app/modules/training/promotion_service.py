"""Deploy completed training checkpoints to the realtime service."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

import httpx

from app.modules.training.schemas import PromoteResponse

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path("/workspace")
CHECKPOINTS_DIR = WORKSPACE_ROOT / "checkpoints"
REGISTRY_PATH = WORKSPACE_ROOT / "backend" / "realtime_service" / "config" / "models.json"
REALTIME_CHECKPOINTS_DIR = REGISTRY_PATH.parent / "checkpoints"
REALTIME_CONTAINER_CHECKPOINTS = "/app/realtime_service/config/checkpoints"


@dataclass(frozen=True)
class DeploymentResult:
    model_id: str
    deployed_path: str
    display_name: str
    registry_updated: bool
    realtime_reloaded: bool
    message: str


class CheckpointCopyError(RuntimeError):
    """Raised when a trained checkpoint cannot be copied into deployment."""


class PromotionNotFoundError(LookupError):
    pass


class PromotionConflictError(RuntimeError):
    pass


class PromotionValidationError(ValueError):
    pass


class PromotionStorageError(RuntimeError):
    pass


def _copy_checkpoint_to_deployment(
    src_path: Path,
    model_id: str,
    dst_dir: Optional[Path] = None,
) -> Optional[str]:
    """Copy a checkpoint and its optional JSON sidecar into deployment."""
    try:
        target_dir = dst_dir or CHECKPOINTS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        dst_path = target_dir / f"{src_path.stem}.pt"

        if src_path.exists():
            dst_path.write_bytes(src_path.read_bytes())
            logger.info("Checkpoint copied: %s -> %s", src_path, dst_path)

            json_src = src_path.with_suffix(".json")
            if json_src.exists():
                dst_path.with_suffix(".json").write_bytes(json_src.read_bytes())
            return str(dst_path)
    except Exception as exc:
        logger.error("Failed to copy checkpoint: %s", exc)
    return None


def _registry_display_name(dialect: str) -> str:
    """Return the current display name for a dialect, if one is registered."""
    try:
        if not REGISTRY_PATH.exists():
            return ""
        registry_data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Không đọc được registry để lấy tên hiển thị: %s", exc)
        return ""

    for model in registry_data.get("models", []):
        if isinstance(model, dict) and model.get("dialect") == dialect:
            name = str(model.get("name") or "").strip()
            if name:
                return name
    return ""


def _update_registry(
    model_id: str,
    checkpoint_rel_path: str,
    display_name: str,
    ckpt: Dict[str, Any],
    dialect: str,
    language: str,
) -> bool:
    """Replace the realtime registry entry for a dialect with this checkpoint."""
    try:
        if not REGISTRY_PATH.exists():
            logger.error("Registry not found: %s", REGISTRY_PATH)
            return False

        registry_data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        seq_len = int(ckpt.get("seq_len", 60))
        feature_dim = int(ckpt.get("feature_dim", 126))
        existing = [
            model for model in registry_data.get("models", [])
            if isinstance(model, dict)
        ]
        kept_name = _registry_display_name(dialect)

        model_entry = {
            "id": model_id,
            "name": kept_name or display_name,
            "checkpoint_path": checkpoint_rel_path,
            "language": language,
            "dialect": dialect,
            "seq_len": seq_len,
            "feature_dim": feature_dim,
            "normalization_version": str(ckpt.get("normalization_version", "hands126_v1")),
            "expected_contract_hash": None,
            "preprocess_contract": {
                "feature_layout": {
                    "type": "hands_126",
                    "slots": ["left_slot_63", "right_slot_63"],
                    "handedness_policy": "swapped_mp_handedness_slots",
                    "coordinate_space": "mediapipe_normalized",
                    "coordinate_order": "xyz",
                    "frontend_mirroring": "visual_only",
                    "missing_hands_policy": "zero_filled_by_frontend",
                },
                "expects_strict_shape": [seq_len, feature_dim],
            },
        }

        registry_data["models"] = [
            model for model in existing
            if model.get("id") != model_id and model.get("dialect") != dialect
        ]
        registry_data["models"].append(model_entry)
        REGISTRY_PATH.write_text(
            json.dumps(registry_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Registry updated: %s", model_id)
        return True
    except Exception as exc:
        logger.error("Failed to update registry: %s", exc)
        return False


def _notify_realtime_service_reload(
    model_id: str,
    checkpoint_path: str,
    version_string: str,
    dialect: str = "",
    language: str = "vn",
) -> bool:
    """Ask the realtime service to validate, warm up and hot-swap a model."""
    realtime_service_url = os.getenv("REALTIME_SERVICE_URL", "http://realtime_service:8010")
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(
                f"{realtime_service_url}/reload",
                json={
                    "model_id": model_id,
                    "checkpoint_path": checkpoint_path,
                    "version_string": version_string,
                    "dialect": dialect or model_id,
                    "language": language,
                },
            )
            if response.status_code == 200:
                logger.info("Realtime service reloaded model: %s", model_id)
                return True
            logger.warning(
                "Realtime service reload failed: status=%s body=%s",
                response.status_code,
                response.text[:500],
            )
            return False
    except Exception as exc:
        logger.error("Failed to notify realtime service: %s", exc)
        return False


def deploy_checkpoint(
    *,
    src_path: Path,
    job_id: str,
    model_type: str,
    dialect: str,
    language: str,
    ckpt: Dict[str, Any],
    copy_checkpoint: Callable[..., Optional[str]] = _copy_checkpoint_to_deployment,
    registry_display_name: Callable[[str], str] = _registry_display_name,
    update_registry: Callable[..., bool] = _update_registry,
    notify_reload: Callable[..., bool] = _notify_realtime_service_reload,
    checkpoints_dir: Path = REALTIME_CHECKPOINTS_DIR,
    container_checkpoints_dir: str = REALTIME_CONTAINER_CHECKPOINTS,
) -> DeploymentResult:
    """Copy, register and hot-reload one completed training checkpoint."""
    model_id = dialect
    deployed_path = copy_checkpoint(src_path, model_id, checkpoints_dir)
    if not deployed_path:
        raise CheckpointCopyError("Copy checkpoint sang realtime service thất bại")

    filename = Path(deployed_path).name
    display_name = registry_display_name(dialect) or f"{model_type.upper()} {dialect} ({job_id})"
    registry_updated = update_registry(
        model_id,
        f"checkpoints/{filename}",
        display_name,
        ckpt,
        dialect,
        language,
    )
    realtime_reloaded = notify_reload(
        model_id,
        f"{container_checkpoints_dir}/{filename}",
        f"{model_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        dialect,
        language,
    )

    if realtime_reloaded:
        message = "Model đã được đưa vào realtime và sẵn sàng sử dụng ngay"
    elif registry_updated:
        message = "Model đã ghi vào registry — sẽ hoạt động sau khi realtime service khởi động lại"
    else:
        message = "Checkpoint đã copy nhưng cập nhật registry thất bại — kiểm tra log backend"

    return DeploymentResult(
        model_id=model_id,
        deployed_path=deployed_path,
        display_name=display_name,
        registry_updated=registry_updated,
        realtime_reloaded=realtime_reloaded,
        message=message,
    )


async def promote_job(
    job_id: str,
    *,
    ensure_job,
    persist_job: Callable[..., Awaitable[None]],
    load_checkpoint,
    model_name_map: Dict[str, str],
    copy_checkpoint: Callable[..., Optional[str]] = _copy_checkpoint_to_deployment,
    registry_display_name: Callable[[str], str] = _registry_display_name,
    update_registry: Callable[..., bool] = _update_registry,
    notify_reload: Callable[..., bool] = _notify_realtime_service_reload,
    checkpoints_dir: Path = REALTIME_CHECKPOINTS_DIR,
    container_checkpoints_dir: str = REALTIME_CONTAINER_CHECKPOINTS,
) -> PromoteResponse:
    """Validate and deploy a completed training job to the realtime service."""
    job_info = await ensure_job(job_id)
    if not job_info:
        raise PromotionNotFoundError(f"Training job {job_id} không tìm thấy")

    job = job_info["job"]
    if job.status != "completed":
        raise PromotionConflictError(
            f"Chỉ promote được job đã hoàn thành (trạng thái hiện tại: {job.status})"
        )
    if not job.checkpoint_path or not Path(job.checkpoint_path).exists():
        raise PromotionNotFoundError("Không tìm thấy checkpoint của job này")

    source = Path(job.checkpoint_path)
    try:
        checkpoint = await asyncio.to_thread(load_checkpoint, source)
    except Exception as exc:
        raise PromotionStorageError(f"Không đọc được checkpoint: {exc}") from exc

    model_type = str(checkpoint.get("model_type", "TCN")).replace(" (legacy)", "").strip()
    if model_type.lower() not in model_name_map:
        raise PromotionValidationError(
            f"Không nhận ra kiến trúc '{model_type}' — realtime service hỗ trợ: "
            f"{', '.join(sorted(set(model_name_map.values())))}. "
            "Model vẫn dùng được qua nút Test Model ở Step 7."
        )

    dialect = job.config.dialects[0] if job.config.dialects else "multi"
    language = job.config.languages[0] if job.config.languages else "vn"
    try:
        deployment = await asyncio.to_thread(
            deploy_checkpoint,
            src_path=source,
            job_id=job_id,
            model_type=model_type,
            dialect=dialect,
            language=language,
            ckpt=checkpoint,
            copy_checkpoint=copy_checkpoint,
            registry_display_name=registry_display_name,
            update_registry=update_registry,
            notify_reload=notify_reload,
            checkpoints_dir=checkpoints_dir,
            container_checkpoints_dir=container_checkpoints_dir,
        )
    except CheckpointCopyError as exc:
        raise PromotionStorageError(str(exc)) from exc

    job.promoted_at = datetime.now().isoformat()
    job.checkpoint_path = deployment.deployed_path
    await persist_job(job)

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
    except Exception as exc:
        logger.warning(
            "job=%s GDrive backup dispatch failed (promotion vẫn OK): %s",
            job_id,
            exc,
        )

    return PromoteResponse(
        job=job,
        model_id=deployment.model_id,
        deployed_checkpoint=deployment.deployed_path,
        registry_updated=deployment.registry_updated,
        realtime_reloaded=deployment.realtime_reloaded,
        message=deployment.message,
    )
