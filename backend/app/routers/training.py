"""
Training Pipeline API Router
Auto-loads dataset, manages training jobs, and streams real-time progress.
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import torch
import torch.nn as nn
import numpy as np
import redis
import sys
from importlib.util import spec_from_file_location, module_from_spec
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel

from app.auth import get_current_user, get_user_from_token, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training", tags=["training"])

# ============================================================================
# Redis (chỉ dùng để gửi tín hiệu cancel tới trainer container;
# job execution đi qua Celery queue "training")
# ============================================================================

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

try:
    redis_client = redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=5,
    )
    redis_client.ping()
    logger.info("Redis connected")
except Exception as e:
    logger.warning("Redis connection failed: %s", e)
    redis_client = None

# ============================================================================
# Model Loading Helper
# ============================================================================

# Map checkpoint model_type values (from model.get_model_name()) to registry keys
_MODEL_NAME_TO_REGISTRY_KEY = {
    "cnn": "cnn",
    "lstm": "lstm",
    "bigru + attention": "bigru_attention",
    "bigru attention": "bigru_attention",
    "bigru_attention": "bigru_attention",
    "handgcn": "handgcn",
    "hdgcn": "handgcn",
    "hd-gcn": "handgcn",   # model.get_model_name() returns "HD-GCN"
    "hd_gcn": "handgcn",
    "tcn": "tcn",
}


def _import_models_registry():
    """Import processed.train_utils.models as a real package.

    Must use a normal package import (not spec_from_file_location on
    __init__.py) because the package uses relative imports internally.
    """
    workspace = str(WORKSPACE_ROOT)
    if workspace not in sys.path:
        sys.path.insert(0, workspace)
    import importlib

    return importlib.import_module("processed.train_utils.models")


def _load_model_from_checkpoint(checkpoint_path: Path, model_type_override: Optional[str] = None) -> tuple[nn.Module, dict]:
    """Load model from checkpoint with support for multiple architectures.

    Returns: (model, ckpt)
    """
    ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)

    # Determine model type saved by train_tcn.py (e.g. "CNN", "BiGRU + Attention")
    model_type = model_type_override or ckpt.get("model_type", "TCN")
    model_config = ckpt.get("model_config", {}) or {}
    num_classes = int(ckpt.get("num_classes", 7))
    feature_dim = int(ckpt.get("feature_dim", 126))

    model_type_lower = str(model_type).lower().replace(" (legacy)", "").strip()
    registry_key = _MODEL_NAME_TO_REGISTRY_KEY.get(model_type_lower)

    model: Optional[nn.Module] = None

    if registry_key and registry_key != "tcn":
        # Non-TCN checkpoint: must load the real architecture from the registry.
        # Do NOT fall back to TCN here — mismatched weights would fail with a
        # confusing state_dict error instead of a clear one.
        try:
            models_module = _import_models_registry()
            model_class = models_module.get_model_class(registry_key)
            model = model_class.from_config(
                input_dim=feature_dim,
                output_dim=num_classes,
                config=model_config,
            ).to("cpu")
            logger.info("Loaded %s model from registry (checkpoint model_type=%s)", registry_key, model_type)
        except Exception as e:
            raise RuntimeError(
                f"Failed to build '{model_type}' model from registry for checkpoint "
                f"{checkpoint_path.name}: {e}"
            ) from e
    else:
        # TCN (or legacy checkpoint without model_type): build from the SAME
        # training registry so the Step 7 test modal always matches the trained
        # architecture — including the temporal_pool head (gap/attention/mean_max).
        # The old inline TCNClassifier was gap-only and broke on attention models.
        try:
            models_module = _import_models_registry()
            model = models_module.get_model_class("tcn").from_config(
                input_dim=feature_dim,
                output_dim=num_classes,
                config=model_config,  # carries temporal_pool; absent -> "gap"
            ).to("cpu")
            logger.info("Loaded TCN model from registry (temporal_pool=%s)",
                        model_config.get("temporal_pool", "gap"))
        except Exception as e:
            raise RuntimeError(
                f"Failed to build TCN model from registry for checkpoint "
                f"{checkpoint_path.name}: {e}"
            ) from e

    try:
        model.load_state_dict(ckpt["model_state_dict"])
        model.eval()
    except Exception as e:
        logger.error("Error loading model state dict: %s", e)
        raise

    return model, ckpt


# ============================================================================
# TCN Model Classes (for training model inference)
# ============================================================================
# DEPRECATED / UNUSED (2026-07-20): the inline Chomp1d/TemporalBlock/TCNClassifier
# below are a legacy gap-only copy. The Step 7 test loader now builds the TCN
# from the training registry (processed/train_utils/models/tcn.py) so it always
# matches the trained architecture — including the temporal_pool head. Do NOT
# reintroduce a fourth TCN implementation here; extend the registry model.

class Chomp1d(nn.Module):
    def __init__(self, chomp_size: int):
        super().__init__()
        self.chomp_size = chomp_size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x[:, :, : x.size(2) - self.chomp_size]


class TemporalBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, dilation: int, dropout: float):
        super().__init__()
        pad = (kernel_size - 1) * dilation
        self.conv1 = nn.Conv1d(in_channels, out_channels, kernel_size, padding=pad, dilation=dilation)
        self.chomp1 = Chomp1d(pad)
        self.relu1 = nn.ReLU()
        self.drop1 = nn.Dropout(dropout)
        self.conv2 = nn.Conv1d(out_channels, out_channels, kernel_size, padding=pad, dilation=dilation)
        self.chomp2 = Chomp1d(pad)
        self.relu2 = nn.ReLU()
        self.drop2 = nn.Dropout(dropout)
        self.downsample = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else None
        self.out_relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.drop1(self.relu1(self.chomp1(self.conv1(x))))
        out = self.drop2(self.relu2(self.chomp2(self.conv2(out))))
        res = x if self.downsample is None else self.downsample(x)
        return self.out_relu(out + res)


class TCNClassifier(nn.Module):
    def __init__(
        self,
        feature_dim: int,
        num_classes: int,
        channels: int = 64,
        levels: int = 3,
        kernel_size: int = 5,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.proj = nn.Conv1d(feature_dim, channels, kernel_size=1)
        blocks = []
        for i in range(levels):
            dilation = 2 ** i
            blocks.append(TemporalBlock(channels, channels, kernel_size, dilation, dropout))
        self.network = nn.Sequential(*blocks)
        self.classifier = nn.Linear(channels, num_classes)

    def forward(self, x_btd: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        x = x_btd.transpose(1, 2)
        x = self.proj(x)
        x = self.network(x)
        b, c, t = x.shape
        mask = torch.arange(t, device=x.device).unsqueeze(0) < lengths.unsqueeze(1)
        mask = mask.unsqueeze(1)
        x = x.masked_fill(~mask, 0.0)
        denom = lengths.clamp(min=1).unsqueeze(1).to(x.dtype)
        pooled = x.sum(dim=2) / denom
        logits = self.classifier(pooled)
        return logits


# In-memory cache of job state. Postgres là source of truth (trainer container
# ghi); cache chỉ giữ bản terminal để đỡ query lặp.
training_jobs: Dict[str, Dict[str, Any]] = {}

# Đường dẫn dataset - tính từ docker volume mount
# In Docker: . mounts to /workspace (root directory)
# Training subprocess runs with cwd=/workspace/processed
WORKSPACE_ROOT = Path("/workspace")
DATASET_ROOT = WORKSPACE_ROOT / "dataset"
SAMPLES_CSV = DATASET_ROOT / "samples.csv"
LABELS_CSV = DATASET_ROOT / "labels.csv"
SPLITS_DIR = WORKSPACE_ROOT / "processed" / "splits"
OUTPUTS_DIR = WORKSPACE_ROOT / "processed" / "train_utils" / "outputs"
CHECKPOINTS_DIR = WORKSPACE_ROOT / "checkpoints"
REGISTRY_PATH = WORKSPACE_ROOT / "backend" / "realtime_service" / "config" / "models.json"

# Realtime service reads checkpoints RELATIVE to its config dir
# (mounted at /app/realtime_service/config inside the realtime container).
REALTIME_CHECKPOINTS_DIR = REGISTRY_PATH.parent / "checkpoints"
# Same dir as seen from INSIDE the realtime container (for /reload payload)
REALTIME_CONTAINER_CHECKPOINTS = "/app/realtime_service/config/checkpoints"


# ============================================================================
# Pydantic Models
# ============================================================================

class DatasetInfo(BaseModel):
    """Thông tin dataset"""
    total_samples: int
    total_classes: int
    languages: List[str]
    dialects: Dict[str, List[str]]  # language -> dialects
    class_distribution: Dict[str, int]  # class_name -> count
    samples_by_dialect: Dict[str, int] = {}  # dialect -> sample count (for split viz)
    split_info: Optional[Dict[str, int]] = None  # train, val, test counts


class TrainingConfig(BaseModel):
    """Cấu hình training"""
    model_type: str = "tcn"  # Supported: tcn, cnn, lstm, bigru_attention, hdgcn
    dialects: List[str] = []  # nếu rỗng = training all
    languages: List[str] = []  # nếu rỗng = training all
    epochs: int = 80
    batch_size: int = 32
    learning_rate: float = 0.001
    dropout: float = 0.3
    channels: int = 64
    levels: int = 3
    kernel_size: int = 5


class TrainingJob(BaseModel):
    """Thông tin training job"""
    id: str
    status: str  # queued, running, completed, failed, cancelled
    config: TrainingConfig
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    current_epoch: int = 0
    total_epochs: int = 80
    checkpoint_path: Optional[str] = None  # Path to saved model after training
    test_acc: Optional[float] = None  # Test accuracy from checkpoint
    test_f1: Optional[float] = None  # Test F1 score from checkpoint
    error_message: Optional[str] = None  # Failure/cancellation reason
    promoted_at: Optional[str] = None  # When admin promoted this model to realtime


class TrainingMetrics(BaseModel):
    """Metrics trong quá trình training"""
    epoch: int
    train_loss: float
    train_acc: float
    val_loss: float
    val_acc: float
    val_f1: float
    learning_rate: Optional[float] = None


# ============================================================================
# Persistence (Postgres is the source of truth; the in-memory dict is a cache)
#
# All persistence calls are best-effort: a DB outage must never kill a
# running training job or block the API. Failures are logged and the
# in-memory state keeps serving until the DB recovers.
# ============================================================================

def _persist_job_sync(job: TrainingJob, auth_user_id: Optional[str] = None) -> None:
    try:
        from app.storage.metadata_db import upsert_training_job

        upsert_training_job({
            "job_id": job.id,
            "status": job.status,
            "model_type": job.config.model_type,
            "config": job.config.dict(),
            "auth_user_id": auth_user_id,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "current_epoch": job.current_epoch,
            "total_epochs": job.total_epochs,
            "checkpoint_path": job.checkpoint_path,
            "test_acc": job.test_acc,
            "test_f1": job.test_f1,
            "error_message": job.error_message,
            "promoted_at": job.promoted_at,
        })
    except Exception as e:
        logger.warning("job %s DB write failed (state kept in memory): %s", job.id, e)


async def _persist_job(job: TrainingJob, auth_user_id: Optional[str] = None) -> None:
    await asyncio.to_thread(_persist_job_sync, job, auth_user_id)


def _persist_metric_sync(job_id: str, metric: TrainingMetrics) -> None:
    try:
        from app.storage.metadata_db import insert_training_metric

        insert_training_metric({
            "job_id": job_id,
            "epoch": metric.epoch,
            "train_loss": metric.train_loss,
            "train_acc": metric.train_acc,
            "val_loss": metric.val_loss,
            "val_acc": metric.val_acc,
            "val_f1": metric.val_f1,
        })
    except Exception as e:
        logger.warning("metric epoch=%s job=%s DB write failed: %s", metric.epoch, job_id, e)


def _job_from_db_row(row: Dict[str, Any]) -> TrainingJob:
    config_raw = row.get("config") or {}
    try:
        config = TrainingConfig(**config_raw)
    except Exception:
        config = TrainingConfig()

    def _iso(v: Any) -> Optional[str]:
        if v is None:
            return None
        return v.isoformat() if hasattr(v, "isoformat") else str(v)

    return TrainingJob(
        id=str(row["job_id"]),
        status=str(row.get("status") or "failed"),
        config=config,
        created_at=_iso(row.get("created_at")) or datetime.now().isoformat(),
        started_at=_iso(row.get("started_at")),
        completed_at=_iso(row.get("completed_at")),
        current_epoch=int(row.get("current_epoch") or 0),
        total_epochs=int(row.get("total_epochs") or 0),
        checkpoint_path=row.get("checkpoint_path"),
        test_acc=row.get("test_acc"),
        test_f1=row.get("test_f1"),
        error_message=row.get("error_message"),
        promoted_at=_iso(row.get("promoted_at")),
    )


def _metrics_from_db_rows(rows: List[Dict[str, Any]]) -> List[TrainingMetrics]:
    metrics: List[TrainingMetrics] = []
    for r in rows:
        try:
            metrics.append(TrainingMetrics(
                epoch=int(r["epoch"]),
                train_loss=float(r.get("train_loss") or 0.0),
                train_acc=float(r.get("train_acc") or 0.0),
                val_loss=float(r.get("val_loss") or 0.0),
                val_acc=float(r.get("val_acc") or 0.0),
                val_f1=float(r.get("val_f1") or 0.0),
            ))
        except Exception:
            continue
    return metrics


TERMINAL_STATUSES = ("completed", "failed", "cancelled")


async def restore_jobs_from_db(limit: int = 50) -> None:
    """Rehydrate recent jobs from Postgres into memory after a backend restart.

    Training runs in the separate trainer container (Celery), so a backend
    restart does NOT interrupt running jobs — leave them alone; the trainer
    keeps updating Postgres. Queued jobs are re-dispatched to the Celery
    queue; duplicates are safe because the trainer task skips any job whose
    DB status is no longer "queued".
    """
    try:
        from app.storage.metadata_db import list_training_jobs

        rows = await asyncio.to_thread(list_training_jobs, limit)
    except Exception as e:
        logger.warning("Cannot read jobs from DB (starting empty): %s", e)
        return

    restored = 0
    requeued = 0

    # Oldest first so re-queued jobs keep their original order
    for row in reversed(rows):
        try:
            job = _job_from_db_row(row)
        except Exception as e:
            logger.warning("Skipping malformed job row: %s", e)
            continue

        if job.id in training_jobs:
            continue

        if job.status == "queued":
            try:
                from app.training_tasks import run_training_job

                run_training_job.apply_async(args=[job.id], queue="training")
                requeued += 1
            except Exception as e:
                logger.warning("Requeue failed for %s: %s", job.id, e)

        training_jobs[job.id] = {
            "job": job,
            "progress": [],  # per-epoch metrics load lazily from DB on demand
        }
        restored += 1

    logger.info("restored=%d requeued=%d", restored, requeued)


async def _ensure_job_loaded(job_id: str) -> Optional[Dict[str, Any]]:
    """Return job_info, refreshing from Postgres unless the cached copy is terminal.

    Postgres is the source of truth: the trainer container updates job rows
    while the backend only reads them. Terminal jobs are immutable (except
    promotion, which the backend itself writes), so the cache is safe there.
    """
    cached = training_jobs.get(job_id)
    if cached and cached["job"].status in TERMINAL_STATUSES:
        return cached

    try:
        from app.storage.metadata_db import get_training_job

        row = await asyncio.to_thread(get_training_job, job_id)
    except Exception as e:
        logger.warning("DB lookup failed for job %s: %s", job_id, e)
        return cached  # degrade to possibly-stale cache instead of erroring
    if not row:
        return cached

    job = _job_from_db_row(row)
    if cached:
        cached["job"] = job
        return cached

    job_info = {"job": job, "progress": []}
    training_jobs[job_id] = job_info
    return job_info


# ============================================================================
# Helper Functions
# ============================================================================

def _load_samples_and_labels() -> tuple[List[Dict], List[Dict]]:
    """Tải samples.csv và labels.csv"""
    samples = []
    labels = {}

    # Load labels
    if LABELS_CSV.exists():
        with open(LABELS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                class_uid = row.get("class_uid", "").strip()
                if class_uid:
                    labels[class_uid] = row

    # Load samples
    if SAMPLES_CSV.exists():
        with open(SAMPLES_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                samples.append(row)

    return samples, list(labels.values())


def _get_dialects_by_language() -> Dict[str, List[str]]:
    """Lấy mapping language -> dialects"""
    _, labels = _load_samples_and_labels()

    dialects_map: Dict[str, set] = {}
    for label in labels:
        language = label.get("language", "vn").strip() or "vn"
        dialect = label.get("dialect", "").strip()

        if language not in dialects_map:
            dialects_map[language] = set()

        if dialect:
            dialects_map[language].add(dialect)

    return {lang: sorted(list(dialects)) for lang, dialects in dialects_map.items()}


def _trainable_dialects_from_splits() -> Dict[str, int]:
    """Đọc split train.csv hiện tại, trả về {dialect: số_class}.

    Legacy training lọc frozen splits theo cột `dialect`; một dialect chỉ train
    được khi có >= 2 class trong split. Dialect có trong labels.csv nhưng KHÔNG
    có mẫu trong split (chưa chia lại sau khi thu) sẽ không xuất hiện ở đây —
    dùng để chặn sớm với thông báo rõ ràng thay vì để subprocess fail rc=1.
    """
    import csv as _csv

    train_csv = SPLITS_DIR / "train.csv"
    counts: Dict[str, set] = {}
    if not train_csv.exists():
        return {}
    try:
        with open(train_csv, newline="", encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                dialect = (row.get("dialect") or "").strip()
                cls = (row.get("class_idx") or row.get("label_key") or "").strip()
                if dialect and cls:
                    counts.setdefault(dialect, set()).add(cls)
    except Exception as exc:
        logger.warning("[TRAIN_VALIDATE] không đọc được train split: %s", exc)
        return {}
    return {d: len(classes) for d, classes in counts.items()}


def _copy_checkpoint_to_deployment(src_path: Path, model_id: str, dst_dir: Optional[Path] = None) -> Optional[str]:
    """Copy checkpoint (+ JSON sidecar) sang thư mục deployment."""
    try:
        target_dir = dst_dir or CHECKPOINTS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        # Tên model mới
        stem = src_path.stem  # "tcn_18_20260606_052123"
        new_name = f"{stem}.pt"
        dst_path = target_dir / new_name

        # Copy file
        if src_path.exists():
            dst_path.write_bytes(src_path.read_bytes())
            logger.info("Checkpoint copied: %s -> %s", src_path, dst_path)

            # Copy JSON metadata nếu có
            json_src = src_path.with_suffix(".json")
            if json_src.exists():
                json_dst = dst_path.with_suffix(".json")
                json_dst.write_bytes(json_src.read_bytes())

            return str(dst_path)
    except Exception as e:
        logger.error("Failed to copy checkpoint: %s", e)

    return None


def _registry_display_name(dialect: str) -> str:
    """Tên hiển thị của model đang phục vụ dialect này trong models.json ("" nếu chưa có)."""
    try:
        if not REGISTRY_PATH.exists():
            return ""
        registry_data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Không đọc được registry để lấy tên hiển thị: %s", e)
        return ""

    for m in registry_data.get("models", []):
        if isinstance(m, dict) and m.get("dialect") == dialect:
            name = str(m.get("name") or "").strip()
            if name:
                return name
    return ""


def _update_registry(model_id: str, checkpoint_rel_path: str, display_name: str,
                     ckpt: Dict[str, Any], dialect: str, language: str) -> bool:
    """Update models.json registry để realtime service load model mới.

    Entry được build từ chính checkpoint để pass validate_checkpoint_vs_registry
    của realtime service (normalization_version, seq_len, feature_dim phải khớp).

    Mỗi dialect chỉ có đúng một entry: promote model mới cho một dialect sẽ THAY
    THẾ entry cũ (giữ nguyên tên hiển thị) thay vì thêm model trùng vào danh sách.
    """
    try:
        if not REGISTRY_PATH.exists():
            logger.error("Registry not found: %s", REGISTRY_PATH)
            return False

        # Load existing registry
        registry_data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

        seq_len = int(ckpt.get("seq_len", 60))
        feature_dim = int(ckpt.get("feature_dim", 126))

        existing = [m for m in registry_data.get("models", []) if isinstance(m, dict)]

        # Giữ tên hiển thị của entry đang phục vụ dialect này (vd "Hòa đê") để
        # dropdown realtime không đổi nhãn sau mỗi lần promote.
        kept_name = _registry_display_name(dialect)

        model_entry = {
            "id": model_id,
            "name": kept_name or display_name,
            "checkpoint_path": checkpoint_rel_path,  # relative to config dir, e.g. "checkpoints/x.pt"
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
                    "missing_hands_policy": "zero_filled_by_frontend"
                },
                "expects_strict_shape": [seq_len, feature_dim]
            }
        }

        # Thay thế mọi entry cũ của dialect này (kể cả entry "training_<job_id>"
        # do các bản promote trước để lại) — một dialect = một model.
        registry_data["models"] = [
            m for m in existing
            if m.get("id") != model_id and m.get("dialect") != dialect
        ]
        registry_data["models"].append(model_entry)

        # Write updated registry
        REGISTRY_PATH.write_text(json.dumps(registry_data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Registry updated: %s", model_id)

        return True
    except Exception as e:
        logger.error("Failed to update registry: %s", e)

    return False


def _notify_realtime_service_reload(model_id: str, checkpoint_path: str, version_string: str,
                                    dialect: str = "", language: str = "vn") -> bool:
    """Notify realtime service to reload/add model via /reload endpoint"""
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
            else:
                logger.warning(
                    "Realtime service reload failed: status=%s body=%s",
                    response.status_code, response.text[:500],
                )
                return False
    except Exception as e:
        logger.error("Failed to notify realtime service: %s", e)
        return False


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
        logger.debug("WORKSPACE_ROOT: %s", WORKSPACE_ROOT)
        logger.debug("DATASET_ROOT: %s", DATASET_ROOT)
        logger.debug("SAMPLES_CSV exists: %s", SAMPLES_CSV.exists())
        logger.debug("LABELS_CSV exists: %s", LABELS_CSV.exists())

        samples, labels = _load_samples_and_labels()
        dialects_map = _get_dialects_by_language()

        # Nếu có filter dialect/language, giới hạn samples về đúng các
        # class_uid có label khớp trước khi tính total/class_distribution.
        # dialects/languages trả về vẫn là toàn bộ tập hợp có sẵn để UI
        # selector không bị mất option khi đang lọc.
        if dialect or language:
            label_by_uid = {
                label.get("class_uid", "").strip(): label
                for label in labels
                if label.get("class_uid", "").strip()
            }
            matching_uids = {
                uid
                for uid, label in label_by_uid.items()
                if (not language or (label.get("language", "vn").strip() or "vn") == language)
                and (not dialect or label.get("dialect", "").strip() == dialect)
            }
            samples = [s for s in samples if s.get("class_uid", "").strip() in matching_uids]

        class_counts: Dict[str, int] = {}
        for sample in samples:
            class_uid = sample.get("class_uid", "").strip()
            if class_uid:
                class_counts[class_uid] = class_counts.get(class_uid, 0) + 1

        # Per-dialect sample counts so the split step can show numbers for the
        # SELECTED dialects instead of the whole dataset.
        uid_to_dialect = {
            (lb.get("class_uid", "").strip()): (lb.get("dialect", "").strip())
            for lb in labels
            if lb.get("class_uid", "").strip()
        }
        samples_by_dialect: Dict[str, int] = {}
        for sample in samples:
            d = uid_to_dialect.get(sample.get("class_uid", "").strip(), "")
            if d:
                samples_by_dialect[d] = samples_by_dialect.get(d, 0) + 1

        return DatasetInfo(
            total_samples=len(samples),
            total_classes=len(class_counts),
            languages=list(dialects_map.keys()),
            dialects=dialects_map,
            class_distribution=class_counts,
            samples_by_dialect=samples_by_dialect,
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
        # Chặn sớm: lựa chọn dialect không có đủ dữ liệu trong split hiện tại sẽ
        # khiến subprocess train fail âm thầm (rc=1). Báo lỗi rõ ràng ngay đây.
        selected_dialects = list(config.dialects or [])
        if selected_dialects:
            trainable = _trainable_dialects_from_splits()
            empty = [d for d in selected_dialects if trainable.get(d, 0) < 2]
            if empty:
                available = sorted(d for d, n in trainable.items() if n >= 2)
                detail = (
                    f"Các phương ngữ đã chọn không đủ dữ liệu để huấn luyện "
                    f"(cần ≥2 lớp có mẫu trong tập chia): {empty}. "
                    f"Phương ngữ đang huấn luyện được: {available or 'chưa có'}. "
                    f"Nếu bạn vừa thu dữ liệu mới, hãy chia lại tập "
                    f"(processed/splits/make_splits.py) trước khi huấn luyện."
                )
                raise HTTPException(status_code=400, detail=detail)

        job_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        job = TrainingJob(
            id=job_id,
            status="queued",  # ✓ Changed from "pending" to "queued"
            config=config,
            created_at=now,
            total_epochs=config.epochs,
        )

        training_jobs[job_id] = {
            "job": job,
            "progress": [],
        }

        # Persist BEFORE enqueue: if the backend dies right after, the job
        # is recoverable instead of silently vanishing.
        await _persist_job(job, auth_user_id=str(current_user.get("id") or "") or None)

        # Dispatch to the dedicated trainer container (Celery queue "training",
        # concurrency 1 — jobs execute strictly one at a time, off the API CPU)
        try:
            from app.training_tasks import run_training_job

            await asyncio.to_thread(
                run_training_job.apply_async, kwargs={"job_id": job_id}, queue="training"
            )
            logger.info("job=%s dispatched to trainer by user=%s", job_id, current_user.get("username"))
        except Exception as dispatch_err:
            job.status = "failed"
            job.completed_at = datetime.now().isoformat()
            job.error_message = f"Không gửi được job tới trainer (Redis/Celery down?): {dispatch_err}"
            await _persist_job(job)
            raise HTTPException(
                status_code=503,
                detail="Hàng đợi training tạm thời không khả dụng — thử lại sau",
            )

        return job

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi bắt đầu training: {str(e)}")


@router.get("/jobs")
async def list_jobs(
    limit: int = Query(100, ge=1, le=500),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Lịch sử training jobs (mới nhất trước), kèm username người chạy."""
    try:
        from app.storage.metadata_db import list_training_jobs_with_user

        rows = await asyncio.to_thread(list_training_jobs_with_user, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không đọc được lịch sử training: {e}")

    items: List[Dict[str, Any]] = []
    for row in rows:
        try:
            job = _job_from_db_row(row)
        except Exception:
            continue
        item = job.dict()
        item["username"] = row.get("username")
        items.append(item)
    return items


@router.get("/jobs/{job_id}", response_model=TrainingJob)
async def get_job_status(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TrainingJob:
    """Lấy trạng thái training job (fallback sang DB nếu không có trong memory)"""
    job_info = await _ensure_job_loaded(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail=f"Training job {job_id} không tìm thấy")

    job = job_info["job"]

    # Load test metrics from checkpoint if job is completed
    if job.status == "completed" and job.checkpoint_path:
        logger.debug("job=%s checking test metrics: test_acc=%s checkpoint=%s", job_id, job.test_acc, job.checkpoint_path)
        if not job.test_acc:  # Only load if not already set
            try:
                ckpt_path = Path(job.checkpoint_path)
                logger.debug("job=%s loading checkpoint from %s, exists=%s", job_id, ckpt_path, ckpt_path.exists())
                if ckpt_path.exists():
                    # In thread — torch.load on a large checkpoint would block the event loop
                    ckpt = await asyncio.to_thread(
                        torch.load, ckpt_path, map_location="cpu", weights_only=False
                    )
                    metrics = ckpt.get("metrics", {})
                    logger.debug("job=%s checkpoint metrics keys: %s", job_id, list(metrics.keys()))
                    job.test_acc = float(metrics.get("test_acc", 0)) if metrics.get("test_acc") is not None else None
                    job.test_f1 = float(metrics.get("test_f1", 0)) if metrics.get("test_f1") is not None else None
                    logger.info("job=%s loaded test metrics: acc=%.4f f1=%.4f", job_id, job.test_acc, job.test_f1)
                    await _persist_job(job)
                else:
                    logger.warning("job=%s checkpoint file not found: %s", job_id, ckpt_path)
            except Exception:
                logger.exception("job=%s error loading test metrics", job_id)

    return job


@router.get("/jobs/{job_id}/metrics", response_model=List[TrainingMetrics])
async def get_job_metrics(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[TrainingMetrics]:
    """Lấy metrics của training job (fallback sang DB nếu không có trong memory)"""
    job_info = await _ensure_job_loaded(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail=f"Training job {job_id} không tìm thấy")

    # Metrics live in Postgres (written by the trainer container). Cache only
    # once the job is terminal; while running, read fresh each poll.
    is_terminal = job_info["job"].status in TERMINAL_STATUSES
    if not job_info["progress"] or not is_terminal:
        try:
            from app.storage.metadata_db import list_training_metrics

            rows = await asyncio.to_thread(list_training_metrics, job_id)
            job_info["progress"] = _metrics_from_db_rows(rows)
        except Exception as e:
            logger.warning("Metrics DB load failed for %s: %s", job_id, e)

    return job_info["progress"]


@router.get("/jobs/{job_id}/evaluation")
async def get_job_evaluation(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Per-class breakdown + confusion matrix trên test set (Step 7).

    Trả về {"available": false} thay vì 404 khi job cũ chưa có dữ liệu này
    (các job train trước khi tính năng evaluation được thêm).
    """
    job_info = await _ensure_job_loaded(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail=f"Training job {job_id} không tìm thấy")

    try:
        from app.storage.metadata_db import get_training_job

        row = await asyncio.to_thread(get_training_job, job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không đọc được evaluation: {e}")

    evaluation = (row or {}).get("evaluation")
    if not isinstance(evaluation, dict) or not evaluation.get("per_class"):
        return {"available": False, "job_id": job_id}

    return {"available": True, "job_id": job_id, **evaluation}


def _determinism_summary(determinism: Any) -> str:
    """Gộp khối determinism thành một dòng đọc được.

    train_tcn.py ghi nó dạng dict (cudnn_deterministic, deterministic_algorithms,
    cublas_workspace_config, warnings). Giao diện chỉ cần biết: đã bật đủ chưa,
    và có cảnh báo nào không.
    """
    if not isinstance(determinism, dict):
        return str(determinism or "")

    full = bool(determinism.get("cudnn_deterministic")) and bool(
        determinism.get("deterministic_algorithms")
    )
    warnings = determinism.get("warnings") or []
    text = "đầy đủ" if full else "một phần"
    if warnings:
        text += f" ({len(warnings)} cảnh báo)"
    return text


def _provenance_checks(ckpt: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Các tiêu chí tái lập trả lời được CHỈ từ checkpoint.

    Dùng lại đúng mã C1/C5/C10/C11/C13 của scripts/research_validity.py để một
    lần chạy được đánh giá giống nhau dù xem trên web hay chạy audit bằng script.
    """
    runtime_env = ckpt.get("runtime_env") or {}
    selection = ckpt.get("model_selection") or {}
    missing_env = [
        k for k in ("python_version", "pytorch_version", "numpy_version", "device")
        if not (runtime_env or {}).get(k)
    ]
    purpose = str(ckpt.get("run_purpose") or "")

    return [
        {
            "id": "C1",
            "label": "Chạy nghiên cứu (không phải smoke test)",
            "ok": purpose == "research",
            "detail": f"run_purpose = '{purpose or 'không ghi'}'",
        },
        {
            "id": "C5",
            "label": "Có checksum manifest dữ liệu",
            "ok": bool(str(ckpt.get("dataset_manifest_checksum") or "").strip()),
            "detail": str(ckpt.get("dataset_manifest_checksum") or "") or "trống",
        },
        {
            "id": "C10",
            "label": "Ghi đủ môi trường chạy",
            "ok": not missing_env,
            "detail": "đầy đủ" if not missing_env else f"thiếu: {', '.join(missing_env)}",
        },
        {
            "id": "C11",
            "label": "Ghim được commit sinh ra model",
            "ok": bool(str(ckpt.get("git_commit") or "").strip()),
            "detail": str(ckpt.get("git_commit") or "") or "trống",
        },
        {
            "id": "C13",
            "label": "Metrics lấy từ checkpoint val tốt nhất",
            "ok": bool(selection.get("restored_best_state")),
            "detail": (
                f"tiêu chí {selection.get('criterion')}, epoch {selection.get('best_epoch')}"
                if selection else "không ghi model_selection"
            ),
        },
    ]


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
            torch.load, str(job.checkpoint_path), map_location="cpu", weights_only=False
        )
    except Exception as e:
        logger.warning("job=%s không đọc được provenance: %s", job_id, e)
        return {"available": False, "job_id": job_id}

    if not isinstance(ckpt, dict) or "git_commit" not in ckpt:
        # Checkpoint có trước khi provenance được ghi — nói rõ thay vì hiện ô trống.
        return {"available": False, "job_id": job_id}

    checks = _provenance_checks(ckpt)
    return {
        "available": True,
        "job_id": job_id,
        "code": {
            "git_commit": ckpt.get("git_commit") or "",
            "seed": ckpt.get("seed"),
            "run_purpose": ckpt.get("run_purpose") or "",
            "run_status": ckpt.get("run_status") or "",
            # determinism là dict (cudnn/cublas/algorithms) — rút thành một câu
            # đọc được thay vì đổ nguyên object ra giao diện.
            "determinism": _determinism_summary(ckpt.get("determinism")),
            "created_at": ckpt.get("created_at") or "",
        },
        "data": {
            "dataset_version": ckpt.get("dataset_version") or "",
            "split_version": ckpt.get("split_version") or "",
            "dataset_manifest_checksum": ckpt.get("dataset_manifest_checksum") or "",
            "recognition_profile": ckpt.get("recognition_profile") or "",
            "vocabulary_schema_version": ckpt.get("vocabulary_schema_version") or "",
        },
        "model": {
            "model_type": ckpt.get("model_type") or "",
            "num_classes": ckpt.get("num_classes"),
            "seq_len": ckpt.get("seq_len"),
            "feature_dim": ckpt.get("feature_dim"),
            "normalization_version": ckpt.get("normalization_version") or "",
            "storage_contract_version": ckpt.get("storage_contract_version") or "",
        },
        "model_selection": ckpt.get("model_selection") or {},
        "runtime_env": ckpt.get("runtime_env") or {},
        "checks": checks,
        "reproducible": all(c["ok"] for c in checks),
    }


@router.get("/queue/status")
async def get_queue_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> dict:
    """Get training queue status (từ Postgres — trainer container ghi trạng thái)"""
    try:
        from app.storage.metadata_db import list_training_jobs

        rows = await asyncio.to_thread(list_training_jobs, 100)
    except Exception as e:
        return {"queue_enabled": False, "message": f"DB unavailable: {e}"}

    queued = [r for r in rows if str(r.get("status")) == "queued"]
    running = [r for r in rows if str(r.get("status")) == "running"]
    return {
        "queue_enabled": True,
        "queue_length": len(queued),
        "current_job": str(running[0]["job_id"]) if running else None,
        "worker_running": True,  # executor là container trainer riêng (celery -Q training)
    }


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
    job_info = await _ensure_job_loaded(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail=f"Training job {job_id} không tìm thấy")

    job = job_info["job"]

    if job.status in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Job đã ở trạng thái kết thúc ({job.status}), không thể hủy",
        )

    logger.info("job=%s cancel requested by user=%s", job_id, current_user.get("username"))

    # Signal the trainer (works for both queued — pre-start check — and running)
    if redis_client:
        try:
            await asyncio.to_thread(
                redis_client.set, f"training:cancel:{job_id}", "1", ex=86400
            )
        except Exception as e:
            logger.warning("job=%s cancel signal to Redis failed: %s", job_id, e)

    job.status = "cancelled"
    job.completed_at = datetime.now().isoformat()
    job.error_message = f"Bị hủy bởi {current_user.get('username', 'user')}"
    await _persist_job(job)
    return job


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
    job_info = await _ensure_job_loaded(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail=f"Training job {job_id} không tìm thấy")

    job = job_info["job"]
    if job.status not in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Chỉ xóa được job đã kết thúc (trạng thái hiện tại: {job.status}). Hãy hủy job trước.",
        )

    try:
        from app.storage.metadata_db import delete_training_job

        await asyncio.to_thread(delete_training_job, job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không xóa được job: {e}")

    training_jobs.pop(job_id, None)
    logger.info("job=%s deleted from history by user=%s", job_id, current_user.get("username"))
    return {"success": True, "job_id": job_id}


class PromoteResponse(BaseModel):
    """Kết quả promote model lên realtime"""
    job: TrainingJob
    model_id: str
    deployed_checkpoint: str
    registry_updated: bool
    realtime_reloaded: bool
    message: str


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
        ckpt = await asyncio.to_thread(
            torch.load, str(src_path), map_location="cpu", weights_only=False
        )
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
    model_id = dialect

    # 1. Copy đúng checkpoint của job vào thư mục realtime service đọc được
    deployed_path = await asyncio.to_thread(
        _copy_checkpoint_to_deployment, src_path, model_id, REALTIME_CHECKPOINTS_DIR
    )
    if not deployed_path:
        raise HTTPException(status_code=500, detail="Copy checkpoint sang realtime service thất bại")

    fname = Path(deployed_path).name

    # 2. Ghi models.json (bền vững — realtime restart vẫn load được)
    display_name = _registry_display_name(dialect) or f"{model_type.upper()} {dialect} ({job_id})"
    registry_updated = await asyncio.to_thread(
        _update_registry,
        model_id,
        f"checkpoints/{fname}",  # relative to realtime config dir
        display_name,
        ckpt,
        dialect,
        language,
    )

    # 3. Hot-swap: báo realtime service load model ngay (path TRONG container realtime)
    realtime_reloaded = await asyncio.to_thread(
        _notify_realtime_service_reload,
        model_id,
        f"{REALTIME_CONTAINER_CHECKPOINTS}/{fname}",
        f"{model_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        dialect,
        language,
    )

    # 4. Ghi nhận promotion. checkpoint_path trỏ sang bản deployed để:
    #    - retention sweep dọn outputs/ không thể phá model đã promote
    #    - Step 7 test modal vẫn hoạt động sau khi outputs/ bị dọn
    job.promoted_at = datetime.now().isoformat()
    job.checkpoint_path = deployed_path
    await _persist_job(job)

    # 5. Publish bản promoted lên Google Drive (background, best-effort):
    #    models/<tên model>/Deploy <thời điểm>/ gồm checkpoint + manifest inference
    try:
        from app.training_tasks import backup_promoted_checkpoint_task

        backup_promoted_checkpoint_task.delay(
            job_id=job_id,
            checkpoint_path=deployed_path,
            model_id=model_id,
            display_name=display_name,
            dialect=dialect,
            language=language,
            promoted_at=job.promoted_at,
        )
        logger.info("job=%s GDrive backup dispatched for promoted model", job_id)
    except Exception as e:
        logger.warning("job=%s GDrive backup dispatch failed (promotion vẫn OK): %s", job_id, e)

    logger.info(
        "job=%s promoted by admin=%s registry=%s reload=%s",
        job_id, current_user.get("username"), registry_updated, realtime_reloaded,
    )

    if realtime_reloaded:
        message = "Model đã được đưa vào realtime và sẵn sàng sử dụng ngay"
    elif registry_updated:
        message = "Model đã ghi vào registry — sẽ hoạt động sau khi realtime service khởi động lại"
    else:
        message = "Checkpoint đã copy nhưng cập nhật registry thất bại — kiểm tra log backend"

    return PromoteResponse(
        job=job,
        model_id=model_id,
        deployed_checkpoint=deployed_path,
        registry_updated=registry_updated,
        realtime_reloaded=realtime_reloaded,
        message=message,
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
    from app.cookie_auth import ACCESS_COOKIE

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

    # Training chạy trong container trainer và ghi tiến độ vào Postgres —
    # backend poll DB mỗi 2s và đẩy phần MỚI cho client (message shape giữ
    # nguyên như cũ nên FE không cần đổi).
    try:
        from app.storage.metadata_db import list_training_metrics

        last_epoch = 0
        last_status: Optional[str] = None

        while True:
            job_info = await _ensure_job_loaded(job_id)
            if not job_info:
                break
            job = job_info["job"]

            try:
                rows = await asyncio.to_thread(list_training_metrics, job_id)
                for metric in _metrics_from_db_rows(rows):
                    if metric.epoch > last_epoch:
                        await websocket.send_json({"type": "metric", "data": metric.dict()})
                        last_epoch = metric.epoch
            except Exception as e:
                logger.warning("WS metrics poll failed for %s: %s", job_id, e)

            if job.status != last_status:
                await websocket.send_json({"type": "status", "data": job.dict()})
                last_status = job.status

            if job.status in TERMINAL_STATUSES:
                break

            await asyncio.sleep(2)

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

class TrainedModelPredictRequest(BaseModel):
    """Request to predict using trained model"""
    frames: List[List[float]]  # 60 frames x 126 features


class TrainedModelPredictResponse(BaseModel):
    """Prediction response from trained model"""
    label: str
    confidence: float
    label_key: str


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
        # Setup sys.path for imports
        processed_root = str(WORKSPACE_ROOT / "processed")
        if processed_root not in sys.path:
            sys.path.insert(0, processed_root)

        # Import normalization from shared
        normalization_path = WORKSPACE_ROOT / "processed" / "shared" / "normalization.py"
        spec = spec_from_file_location("normalization", normalization_path)
        norm_module = module_from_spec(spec)
        spec.loader.exec_module(norm_module)
        normalize_hands_vector_126 = norm_module.normalize_hands_vector_126

        # Normalize frames
        frames_array = np.asarray(request_data.frames, dtype=np.float32)
        if frames_array.shape != (60, 126):
            raise ValueError(f"Expected shape (60, 126), got {frames_array.shape}")

        normalized_frames = np.array([
            normalize_hands_vector_126(frame) for frame in frames_array
        ], dtype=np.float32)

        # Load checkpoint with dynamic model support
        # In thread — checkpoint load + inference are disk/CPU heavy and would
        # stall every other request if run directly on the event loop
        checkpoint_path_obj = Path(checkpoint_path)
        model, ckpt = await asyncio.to_thread(_load_model_from_checkpoint, checkpoint_path_obj)

        # Log model type
        model_type = ckpt.get("model_type", "Unknown")
        logger.debug("job=%s loaded model: %s", job_id, model_type)

        # Run inference
        def _run_inference() -> torch.Tensor:
            x = torch.from_numpy(normalized_frames).unsqueeze(0).to(dtype=torch.float32)
            with torch.no_grad():
                # Check if model accepts lengths parameter (old BE TCNClassifier)
                # or just input (new models from registry)
                try:
                    return model(x, torch.tensor([60]))
                except TypeError:
                    return model(x)

        logits = await asyncio.to_thread(_run_inference)

        probs = torch.softmax(logits, dim=-1).detach().cpu().numpy().squeeze()
        pred_idx = int(np.argmax(probs))
        confidence = float(probs[pred_idx])

        # Build label map from checkpoint + labels.csv for label_original
        # Checkpoint idx_to_label: {0: "vn/dialect/slug", 1: ...}
        i2l = ckpt.get("idx_to_label")
        label_key = f"class_{pred_idx}"
        label = f"class_{pred_idx}"

        # Extract label_key from checkpoint
        if isinstance(i2l, dict):
            v = i2l.get(pred_idx) or i2l.get(str(pred_idx))
            if v:
                label_key = str(v).strip()
                label = label_key  # default to label_key
        elif isinstance(i2l, list) and pred_idx < len(i2l):
            v = i2l[pred_idx]
            if v:
                label_key = str(v).strip()
                label = label_key

        # Load labels.csv to get label_original
        # label_key format: "vn/hoa-de/rang-muoi" or "vn/rang-muoi"
        try:
            if LABELS_CSV.exists():
                # Parse label_key to extract slug (last part)
                parts = label_key.replace("\\", "/").split("/")
                slug = parts[-1] if parts else ""

                logger.debug("job=%s looking up slug='%s' from label_key='%s'", job_id, slug, label_key)

                with open(LABELS_CSV, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    found = False
                    for row in reader:
                        if row.get("slug", "").strip() == slug:
                            label_original = row.get("label_original", "").strip()
                            if label_original:
                                label = label_original
                                logger.debug("job=%s found label_original: %s", job_id, label)
                            found = True
                            break
                    if not found:
                        logger.warning("job=%s slug '%s' not found in labels.csv", job_id, slug)
        except Exception as e:
            logger.warning("job=%s error loading labels.csv: %s", job_id, e)

        return TrainedModelPredictResponse(
            label=label,
            confidence=confidence,
            label_key=label_key,
        )

    except Exception as e:
        logger.exception("job=%s inference error", job_id)
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")
