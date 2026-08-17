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
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx
import torch
import torch.nn as nn
import numpy as np
import redis
import sys
from importlib.util import spec_from_file_location, module_from_spec
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.auth import get_current_user, get_user_from_token, require_admin
from app.checkpoint_io import load_checkpoint
from app.quota_deps import guard_quota, tenant_of
from app.rate_limit_deps import limit_predict, limit_training
from app.vocabulary_registry import assert_can_use_dialect, dialect_owner
from app.cookie_auth import ACCESS_COOKIE

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
    ckpt = load_checkpoint(checkpoint_path)

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

    # Chế độ nghiên cứu. Mặc định smoke_test là CỐ Ý (xem scripts/research_validity.py
    # C1): job thăm dò dựng subset tạm từ bộ lọc dialect, nhanh nhưng không truy
    # ngược được về một phiên bản dữ liệu cố định nên không trích dẫn được.
    # Đặt run_purpose="research" + split_version để chạy trên split đã versioned;
    # khi đó dialects/languages bị bỏ qua vì split đã định nghĩa sẵn tập dữ liệu.
    run_purpose: str = "smoke_test"
    split_version: Optional[str] = None
    #: Hiện vật VẬN HÀNH mà lượt chạy này ghim. Bắt buộc khi
    #: `run_purpose="operational"`; đặt nó ở bất kỳ purpose nào khác research
    #: cũng chuyển lượt chạy sang hợp đồng vận hành.
    #:
    #: KHÔNG có mặc định và KHÔNG có "split mới nhất". Nhận một trường rỗng rồi
    #: tự chọn hộ là mở lại đúng chỗ vừa bịt: lượt vận hành sẽ lặng lẽ học trên
    #: ba tệp nghiên cứu đóng băng và checkpoint khai sai nguồn gốc.
    operational_split_id: Optional[str] = None
    # Suy ra từ metadata của split ở phía server, không nhận từ client — nếu để
    # client tự khai, checkpoint có thể khai một dataset_version khác với dữ
    # liệu thực sự đã train.
    dataset_version: Optional[str] = None
    recognition_profile: Optional[str] = None


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
    # Set when a LATER promotion for the same dialect took over the realtime
    # slot. "Đang phục vụ" is promoted_at set AND superseded_at unset — with one
    # slot per dialect, promoted_at alone no longer answers that question.
    superseded_at: Optional[str] = None


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
        superseded_at=_iso(row.get("superseded_at")),
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
            # ★ C3 — vòng lặp này chạy lúc khởi động và nạp job của MỌI tổ chức
            # vào một `dict` dùng chung. Thiếu chủ sở hữu ở đây thì ngay sau mỗi
            # lần khởi động lại, bất kỳ tenant nào biết `job_id` cũng đọc được
            # job của tenant khác — không cần chủ thật vào xem trước.
            "tenant_id": str(row.get("tenant_id") or "").strip(),
        }
        restored += 1

    logger.info("restored=%d requeued=%d", restored, requeued)


async def _ensure_job_loaded(job_id: str) -> Optional[Dict[str, Any]]:
    """Return job_info, refreshing from Postgres unless the cached copy is terminal.

    Postgres is the source of truth: the trainer container updates job rows
    while the backend only reads them. Terminal jobs are immutable (except
    promotion, which the backend itself writes), so the cache is safe there.

    ★ C3 — `training_jobs` là bộ nhớ CHUNG của tiến trình, RLS không với tới
    ==================================================================
    Trước 16/08/2026 hàm này mở đầu bằng `training_jobs.get(job_id)` rồi trả
    thẳng bản sao nếu job đã ở trạng thái cuối — **không hỏi Postgres**, nên
    không gặp RLS. Một tiến trình backend phục vụ mọi tổ chức, nên tổ chức B chỉ
    cần biết `job_id` của A là đọc được toàn bộ hàng job của A: cấu hình, chỉ số
    thử nghiệm, và `checkpoint_path` — vị trí hiện vật mô hình đã huấn luyện.

    Hai đường vào cache, và đường thứ hai nặng hơn:

    ```
    A xem job của mình  ->  nạp vào cache  ->  B hỏi cùng job_id  ->  đọc được
    backend KHỞI ĐỘNG   ->  `_restore_jobs_from_db` nạp job của MỌI tenant
                        ->  B đọc được ngay, không cần A làm gì
    ```

    Đường thứ hai nghĩa là ngay sau mỗi lần khởi động lại, cache đã chứa sẵn job
    của tất cả các tổ chức.

    Bản vá giữ nguyên cache — nó có lý do tồn tại — nhưng gắn CHỦ SỞ HỮU vào mỗi
    mục và đối chiếu trước khi phục vụ. Một mục không thuộc phạm vi đang chạy
    được coi như không có, đúng cách hàng bị RLS lọc trông như không tồn tại.
    """
    from app.tenant_context import current_tenant

    pham_vi = (current_tenant() or "").strip()
    cached = training_jobs.get(job_id)

    # Fail-closed hai chiều: không có phạm vi thì không phục vụ từ cache, và
    # một mục không mang chủ sở hữu (do bản cũ để lại) cũng không được tin.
    if cached is not None and (
            not pham_vi or cached.get("tenant_id") != pham_vi):
        cached = None

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
    # `get_training_job` chạy dưới RLS, nên tới được đây nghĩa là hàng thuộc
    # phạm vi hiện tại. Ghi chủ sở hữu từ CHÍNH hàng đó, không từ phạm vi: nếu
    # hai giá trị lệch nhau thì hàng mới là sự thật.
    chu = str(row.get("tenant_id") or "").strip() or pham_vi
    if cached:
        cached["job"] = job
        cached["tenant_id"] = chu
        return cached

    job_info = {"job": job, "progress": [], "tenant_id": chu}
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


def _trainable_dialects_from_splits(thu_muc: Optional[Path] = None) -> Dict[str, int]:
    """Đọc split train.csv hiện tại, trả về {dialect: số_class}.

    Legacy training lọc frozen splits theo cột `dialect`; một dialect chỉ train
    được khi có >= 2 class trong split. Dialect có trong labels.csv nhưng KHÔNG
    có mẫu trong split (chưa chia lại sau khi thu) sẽ không xuất hiện ở đây —
    dùng để chặn sớm với thông báo rõ ràng thay vì để subprocess fail rc=1.
    """
    import csv as _csv

    train_csv = (Path(thu_muc) if thu_muc is not None else SPLITS_DIR) / "train.csv"
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


def _eligible_class_counts(
    dialects: Sequence[str], nguong: int
) -> Dict[str, int]:
    """{phương ngữ: số lớp có ĐỦ `nguong` mẫu còn sống}.

    Đếm lớp ĐẠT chứ không đếm lớp thiếu, và khác biệt đó là cả một quyết định
    thiết kế. Bản đầu từ chối cả phiên nếu có BẤT KỲ lớp nào dưới ngưỡng — bộ
    test bắt được ngay: `hoa-de` có 7/8 lớp đạt, một lớp 16 mẫu, và cả phương
    ngữ thành không huấn luyện được. Nặng hơn nữa: `pho-thong` nhập từ từ điển
    mang hàng nghìn mục 0 mẫu, nên nó sẽ VĨNH VIỄN bị khoá.
    Một lớp thu dở không được phép khoá cả phương ngữ.

    Ngưỡng ≥2 lớp giữ nguyên ngữ nghĩa của cổng đã có ở trên — dưới hai lớp thì
    không có bài toán phân loại nào để học.

    Đếm từ CƠ SỞ DỮ LIỆU chứ không từ split: split là ảnh chụp của lần chia gần
    nhất, còn câu hỏi ở đây thuộc về hiện tại. Dùng split sẽ báo thiếu cho lớp
    vừa thu xong mà chưa chia lại.
    """
    if not dialects or nguong <= 0:
        return {}
    from app.storage.metadata_db import _fetch_all

    try:
        rows = _fetch_all(
            "SELECT dialect, count(*) AS n FROM ("
            "  SELECT c.dialect, c.class_uid, "
            "         count(s.sample_uid) FILTER (WHERE s.deleted_at IS NULL) AS m "
            "    FROM classes c "
            "    LEFT JOIN samples s ON s.class_uid = c.class_uid "
            "   WHERE c.deleted_at IS NULL AND c.dialect = ANY(%s) "
            "   GROUP BY c.dialect, c.class_uid"
            ") t WHERE m >= %s GROUP BY dialect",
            (list(dialects), nguong),
        )
    except Exception as exc:
        # Cổng an toàn hỏng phải ồn ào, không được im lặng cho qua.
        logger.error("[TRAIN_VALIDATE] không đếm được mẫu theo lớp: %s", exc)
        raise
    return {(r.get("dialect") or ""): int(r.get("n") or 0) for r in rows}


def _split_class_uids(dialects: Sequence[str], thu_muc: Optional[Path] = None) -> Dict[str, str]:
    """{class_uid: dialect} — các lớp mà trainer SẼ đọc.

    Đọc cả ba tệp train/val/test chứ không chỉ train: một lớp chỉ nằm ở val vẫn
    chiếm một chiều trong không gian nhãn của lượt chạy.

    `thu_muc` là hiện vật ĐÃ GHIM của lượt chạy. Mặc định `SPLITS_DIR` giữ
    nguyên hành vi legacy. Bốn cổng đều nhận tham số này vì nếu chúng cứ đọc ba
    tệp gốc trong khi lượt chạy ghim một hiện vật vận hành thì cổng duyệt một
    tập lớp còn trainer học một tập khác — đúng loại sai mà từng tầng vẫn "đúng".
    """
    import csv as _csv

    goc = Path(thu_muc) if thu_muc is not None else SPLITS_DIR
    chon = {d for d in dialects if d}
    ra: Dict[str, str] = {}
    for ten in ("train", "val", "test"):
        p = goc / f"{ten}.csv"
        if not p.exists():
            continue
        try:
            with open(p, newline="", encoding="utf-8") as f:
                for row in _csv.DictReader(f):
                    d = (row.get("dialect") or "").strip()
                    uid = (row.get("class_uid") or "").strip()
                    if uid and d and (not chon or d in chon):
                        ra[uid] = d
        except Exception as exc:
            logger.warning("[TRAIN_VALIDATE] không đọc được split %s: %s", ten, exc)
    return ra


def _split_classes_below_floor(
    dialects: Sequence[str], nguong: int, thu_muc: Optional[Path] = None
) -> List[Tuple[str, str, int]]:
    """Các lớp CÓ TRONG SPLIT nhưng chưa đủ `nguong` mẫu. [(tên, uid, số_mẫu)]

    Đây là cổng khác hẳn với `_eligible_class_counts`, và cần cả hai. Cổng kia
    hỏi "phương ngữ này có đủ lớp đạt để học không" — điều kiện CẦN. Cổng này
    hỏi "tập lớp mà trainer sắp đọc có lẫn lớp chưa đủ mẫu không" — điều kiện
    ĐỦ. Một phương ngữ 22 lớp đạt lẫn 1 lớp 5 mẫu qua được cổng kia dễ dàng, và
    đó chính là `bang-chu-cai` trên đĩa lúc này.

    Vì sao TỪ CHỐI chứ không tự lọc: `_consent_preflight` trong
    `training_tasks.py` đã chốt nguyên tắc rồi — split là đầu vào đã đóng băng,
    và một checkpoint huấn luyện trên tập nhỏ hơn tệp split khai báo là một
    checkpoint nói dối về nguồn gốc của nó. Áp cùng nguyên tắc ở đây, kể cả khi
    tự lọc thì tiện hơn cho người dùng.
    """
    if nguong <= 0:
        return []
    trong_split = _split_class_uids(dialects, thu_muc)
    if not trong_split:
        return []

    from app.storage.metadata_db import _fetch_all

    try:
        rows = _fetch_all(
            "SELECT c.class_uid, c.label_original, c.slug, "
            "       count(s.sample_uid) FILTER (WHERE s.deleted_at IS NULL) AS n "
            "  FROM classes c "
            "  LEFT JOIN samples s ON s.class_uid = c.class_uid "
            " WHERE c.class_uid = ANY(%s) "
            " GROUP BY c.class_uid, c.label_original, c.slug "
            "HAVING count(s.sample_uid) FILTER (WHERE s.deleted_at IS NULL) < %s "
            " ORDER BY 4 ASC",
            (sorted(trong_split), nguong),
        )
    except Exception as exc:
        # Cổng an toàn hỏng phải ồn ào. Xem `_eligible_class_counts`.
        logger.error("[TRAIN_VALIDATE] không đối chiếu được split với CSDL: %s", exc)
        raise

    ra: List[Tuple[str, str, int]] = []
    for r in rows:
        uid = (r.get("class_uid") or "").strip()
        ten = (r.get("label_original") or r.get("slug") or uid).strip()
        ra.append((ten, uid, int(r.get("n") or 0)))
    return ra


def _split_row_counts(dialects: Sequence[str],
                      thu_muc: Optional[Path] = None) -> Dict[str, Dict[str, int]]:
    """{class_uid: {'train': n, 'val': n, 'test': n}} đếm THẲNG trong tệp split.

    Khác `_split_classes_below_floor` ở nguồn bằng chứng, và cần cả hai. Hàm kia
    hỏi CSDL: "lớp này đã thu đủ chưa". Hàm này hỏi chính tệp sắp được đọc:
    "tệp này có đúng chừng ấy hàng không". Một tệp bị sửa tay, cắt cụt, hay ghi
    hỏng giữa chừng sẽ qua được câu hỏi thứ nhất và trượt ở câu thứ hai.
    """
    import csv as _csv

    goc = Path(thu_muc) if thu_muc is not None else SPLITS_DIR
    chon = {d for d in dialects if d}
    ra: Dict[str, Dict[str, int]] = {}
    for ten in ("train", "val", "test"):
        p = goc / f"{ten}.csv"
        if not p.exists():
            continue
        try:
            with open(p, newline="", encoding="utf-8") as f:
                for row in _csv.DictReader(f):
                    d = (row.get("dialect") or "").strip()
                    uid = (row.get("class_uid") or "").strip()
                    if not uid or not d or (chon and d not in chon):
                        continue
                    ra.setdefault(uid, {"train": 0, "val": 0, "test": 0})[ten] += 1
        except Exception as exc:
            logger.warning("[TRAIN_VALIDATE] không đọc được split %s: %s", ten, exc)
    return ra


def _split_evidence_problems(
    dialects: Sequence[str], nguong: int, thu_muc: Optional[Path] = None
) -> List[str]:
    """Những gì NỘI DUNG tệp split tự tố cáo. Rỗng nghĩa là không có gì để nói.

    Lời khai trong `split_metadata.json` có thể sai — vì lỗi, vì sửa tay, vì
    tệp CSV bị thay sau khi khai. Nên cổng phải kiểm cả hai: lời khai VÀ chứng
    cứ. Ở đây chỉ có chứng cứ.

    Hai bất biến:

      1. Tổng ba phần của một lớp phải đạt sàn. Một lớp `3+1+1=5` bị từ chối dù
         lời khai có ghi sàn 25.
      2. Mỗi lớp phải có mặt ở CẢ BA phần. Với sàn 25 và tỉ lệ 70/15/15 thì
         luôn đủ chỗ, nên phần rỗng nghĩa là bộ chia hỏng — đúng hình dạng của
         sự cố `hoa_de_signer_disjoint_v1/_v3` (val=0, test=0) đã lọt lên đĩa
         và trông như thành công.

    CHỈ áp cho split vận hành. Split nghiên cứu đã versioned đi đường khác và
    có giao thức riêng: ép luật vận hành lên chúng sẽ phá tính lặp lại của
    chính kết quả đã công bố.
    """
    dem = _split_row_counts(dialects, thu_muc)
    if not dem:
        return []

    thieu_tong: List[str] = []
    thieu_phan: List[str] = []
    for uid, phan in sorted(dem.items()):
        tong = phan["train"] + phan["val"] + phan["test"]
        if nguong > 0 and tong < nguong:
            thieu_tong.append(f"{uid} ({tong} hàng)")
        rong = [t for t in ("train", "val", "test") if phan[t] == 0]
        if rong:
            thieu_phan.append(f"{uid} (rỗng ở {'/'.join(rong)})")

    van_de: List[str] = []
    if thieu_tong:
        van_de.append(
            f"{len(thieu_tong)} lớp có tổng số hàng dưới sàn {nguong}: "
            f"{', '.join(thieu_tong[:5])}"
            + (f" và {len(thieu_tong) - 5} lớp nữa" if len(thieu_tong) > 5 else ""))
    if thieu_phan:
        van_de.append(
            f"{len(thieu_phan)} lớp vắng mặt ở ít nhất một phần: "
            f"{', '.join(thieu_phan[:5])}"
            + (f" và {len(thieu_phan) - 5} lớp nữa" if len(thieu_phan) > 5 else ""))
    return van_de


def _split_snapshot(thu_muc: Optional[Path] = None) -> Dict[str, Any]:
    """Bản khai báo tập lớp mà `make_splits.py` ghi cạnh split legacy.

    Trả về `{}` khi chưa có — split dựng trước khi cơ chế này tồn tại vẫn chạy
    được, chỉ là không tự khai được nó đã dùng sàn nào. Cổng phía trên vẫn kết
    luận đúng nhờ đối chiếu thẳng với CSDL; tệp này chỉ làm câu báo lỗi nói
    được nguyên nhân.
    """
    p = (Path(thu_muc) if thu_muc is not None else SPLITS_DIR) / "split_metadata.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("[SPLITS] khai báo split không đọc được: %s", exc)
        return {}


def _research_splits() -> List[Dict[str, Any]]:
    """Các split đã versioned dùng được cho chế độ nghiên cứu.

    Chỉ nhận split "phẳng" (train/val/test ngay trong thư mục) — các bộ LOSO /
    matched-leak chia theo fold con là giao thức đánh giá nhiều lần chạy, không
    phải một job huấn luyện đơn lẻ, nên không liệt kê ở đây.

    Bỏ qua split có valid_for_research=false: train_tcn.py sẽ từ chối chúng ở
    _enforce_research_preconditions, nên hiện ra chỉ để người dùng chọn rồi
    thất bại là vô ích.
    """
    versions_dir = WORKSPACE_ROOT / "processed" / "splits" / "versions"
    if not versions_dir.is_dir():
        return []

    out: List[Dict[str, Any]] = []
    for d in sorted(versions_dir.iterdir()):
        meta_path = d / "split_metadata.json"
        if not d.is_dir() or not (d / "train.csv").exists() or not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[SPLITS] bỏ qua %s: metadata không đọc được (%s)", d.name, exc)
            continue

        if not meta.get("valid_for_research"):
            continue
        checksum = str(meta.get("dataset_manifest_checksum") or "").strip()
        if not checksum:
            continue

        # dataset_version suy ra từ tên manifest: .../dataset_manifest_isds2026_v5.csv
        manifest = str(meta.get("dataset_manifest") or "")
        dataset_version = ""
        stem = Path(manifest).stem
        if stem.startswith("dataset_manifest_"):
            dataset_version = stem[len("dataset_manifest_"):]

        counts = meta.get("counts") or {}
        out.append({
            "split_version": d.name,
            "dataset_version": dataset_version,
            "recognition_profile": str(meta.get("recognition_profile") or ""),
            "split_mode": str(meta.get("split_mode") or ""),
            "num_classes": meta.get("num_classes"),
            "counts": {k: counts.get(k) for k in ("train", "val", "test")},
            "seed": meta.get("seed"),
            "dataset_manifest_checksum": checksum,
        })
    return out


@router.get("/splits")
async def list_research_splits(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Split đã versioned mà chế độ nghiên cứu có thể chạy trên đó."""
    return await asyncio.to_thread(_research_splits)


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

        samples, labels = await run_in_threadpool(_load_samples_and_labels)
        dialects_map = await run_in_threadpool(_get_dialects_by_language)

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


@router.post("/start", response_model=TrainingJob, dependencies=[Depends(limit_training)])
async def start_training(
    config: TrainingConfig,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TrainingJob:
    """
    Bắt đầu training job (enqueue to queue)

    Tạo job ID, thêm vào queue, return job info

    Ba hạn mức được kiểm trước mọi thứ khác, và chúng là chỗ duy nhất giữ công
    bằng tài nguyên giữa các tenant. Hàng đợi `training` chỉ có một chỗ chạy
    (concurrency 1) và phục vụ theo thứ tự đến, nên nếu không có trần thì một
    tổ chức xếp hai mươi lượt là mọi tổ chức khác chờ hết hai mươi lượt đó.
    Trần số lượt CHỜ là thứ thực sự chặn chuyện này; trần số lượt CHẠY và trần
    theo tháng là để chặn hai kiểu vượt mức khác.

    Đây là công bằng bằng hạn ngạch, không phải bằng lịch biểu: nó không xen
    kẽ lượt giữa các tenant, chỉ giới hạn mỗi tenant chiếm bao nhiêu hàng đợi.
    Lập lịch chia lượt thật cần bộ chạy tự chọn job thay vì nhận từ hàng đợi
    Celery — thay đổi lớn hơn nhiều và chưa cần ở quy mô này.
    """
    guard_quota(current_user, "training_jobs_this_month")
    guard_quota(current_user, "training_jobs_running")
    guard_quota(current_user, "training_jobs_queued")

    # MỘT nguồn danh tính cho cả lượt gọi này: hạn mức, cổng hiện vật và chủ sở
    # hữu của mục cache đều đọc đúng giá trị này. Ba nguồn khác nhau cho cùng
    # một lượt chạy là cách một hệ thống tự mâu thuẫn mà không tầng nào sai.
    # `tenant_of` fail-closed, nên tới được dòng sau là đã biết chắc tổ chức.
    pham_vi_nguoi_goi = tenant_of(current_user)

    try:
        # ------------------------------------------------------------------
        # Hợp đồng nguồn dữ liệu, chốt TRƯỚC mọi cổng khác.
        #
        # Ba đường, và chúng không được lẫn:
        #   research     → split đã versioned, ghim bằng `split_version`
        #   operational  → hiện vật bất biến, ghim bằng `operational_split_id`
        #   legacy       → ba tệp nghiên cứu đóng băng (tương thích ngược)
        #
        # `hien_vat` là thư mục mà BỐN cổng phía dưới sẽ soi. Trước lượt này
        # chúng luôn đọc `SPLITS_DIR`, nên một lượt vận hành ghim hiện vật X
        # vẫn được duyệt dựa trên nội dung ba tệp nghiên cứu — cổng duyệt một
        # tập lớp, trainer học một tập khác, và từng tầng vẫn tự thấy mình đúng.
        # ------------------------------------------------------------------
        hien_vat: Optional[Path] = None
        van_hanh = (config.run_purpose == "operational"
                    or bool(str(config.operational_split_id or "").strip()))

        if van_hanh and config.run_purpose == "research":
            raise HTTPException(
                status_code=400,
                detail=("Không thể vừa là lượt nghiên cứu vừa ghim hiện vật vận "
                        "hành. Hai hợp đồng này khác nhau: nghiên cứu cần tính "
                        "lặp lại, vận hành cần tính hợp lệ hiện tại."),
            )

        if van_hanh:
            split_id = str(config.operational_split_id or "").strip()
            if not split_id:
                raise HTTPException(
                    status_code=400,
                    detail=("Lượt huấn luyện vận hành phải ghim một hiện vật: "
                            "thiếu `operational_split_id`. Hệ thống KHÔNG tự chọn "
                            "hiện vật mới nhất và KHÔNG rơi về ba tệp nghiên cứu "
                            "đóng băng — học trên chúng rồi khai là lượt vận hành "
                            "là khai sai nguồn gốc. Dựng hiện vật bằng "
                            "processed/splits/make_splits.py "
                            "--operational_split_id=<ID>."),
                )
            from processed.train_utils.split_artifact import (
                PURPOSE_OPERATIONAL, SplitArtifactError, resolve_split_artifact,
            )

            try:
                art = await run_in_threadpool(
                    lambda: resolve_split_artifact(
                        purpose=PURPOSE_OPERATIONAL, splits_root=SPLITS_DIR,
                        split_id=split_id, tenant_id=pham_vi_nguoi_goi),
                )
            except SplitArtifactError as exc:
                # Phân giải ở ĐÂY chứ không chỉ ở worker, để người gọi nhận lỗi
                # đồng bộ. Worker vẫn phân giải lại — đó không phải thừa: giữa
                # lúc duyệt và lúc chạy, hiện vật có thể bị đổi.
                raise HTTPException(status_code=400, detail=str(exc))
            hien_vat = Path(art.train_csv).parent
            config.run_purpose = "operational"

            # Phạm vi phương ngữ đến từ chính hiện vật, không từ người gọi.
            #
            # Hai lý do. Thứ nhất, `--dialect` là thứ đưa trainer vào chế độ
            # subset — nơi nhánh `class_uid → target_idx` sống — nên bỏ trống
            # là lặng lẽ quay về `enumerate` theo thứ tự hàng. Thứ hai, bốn
            # cổng phía dưới đều nằm trong `if selected_dialects:`, nên bỏ
            # trống cũng là bỏ qua cả bốn.
            pham_vi = list((art.metadata.get("scope") or {}).get("dialects") or [])
            xin = [d for d in (config.dialects or []) if d]
            if xin and pham_vi and set(xin) - set(pham_vi):
                raise HTTPException(
                    status_code=400,
                    detail=(f"Hiện vật '{split_id}' chỉ chứa phương ngữ "
                            f"{pham_vi}, nhưng lượt chạy xin {sorted(set(xin))}. "
                            f"Lọc thêm sẽ làm checkpoint học một tập nhỏ hơn tập "
                            f"hiện vật khai báo."),
                )
            if not xin:
                config.dialects = pham_vi

        if config.run_purpose == "research":
            # Chặn sớm với thông báo rõ, thay vì để train_tcn.py SystemExit ở
            # _enforce_research_preconditions sau khi job đã vào hàng đợi.
            if not config.split_version:
                raise HTTPException(
                    status_code=400,
                    detail="Chế độ nghiên cứu cần chọn một split đã versioned.",
                )
            available = {s["split_version"]: s for s in _research_splits()}
            chosen = available.get(config.split_version)
            if not chosen:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Split '{config.split_version}' không dùng được cho nghiên cứu "
                        f"(không tồn tại, thiếu checksum manifest, hoặc valid_for_research=false). "
                        f"Đang dùng được: {sorted(available) or 'chưa có'}."
                    ),
                )
            # Khoá provenance theo đúng split đã chọn.
            config.dataset_version = chosen["dataset_version"]
            config.recognition_profile = chosen["recognition_profile"]

        # Chặn sớm: lựa chọn dialect không có đủ dữ liệu trong split hiện tại sẽ
        # khiến subprocess train fail âm thầm (rc=1). Báo lỗi rõ ràng ngay đây.
        # Chế độ nghiên cứu không lọc theo dialect — split đã định nghĩa dữ liệu.
        selected_dialects = [] if config.run_purpose == "research" else list(config.dialects or [])

        # A dialect awaiting admin approval belongs to whoever asked for it, and
        # so does everything derived from it. Training on someone else's
        # unapproved vocabulary would produce a model whose label set describes a
        # vocabulary nobody has agreed exists — and promoting it would put that
        # into the shared realtime list. Owner-only until approved.
        for d in selected_dialects:
            try:
                assert_can_use_dialect(d, str(current_user.get("id") or ""))
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail=str(exc))

        if selected_dialects:
            trainable = _trainable_dialects_from_splits(hien_vat)
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

            # Cổng thứ hai, ở mức LỚP. Cổng phía trên đếm số lớp trong một
            # phương ngữ; cổng này đếm số mẫu trong một lớp. Hai câu hỏi khác
            # nhau, và một phương ngữ có 30 lớp vẫn có thể chứa một lớp 3 mẫu.
            #
            # Vì sao nó phải nằm ở đây chứ không ở giao diện: thư viện nhãn
            # nhập từ từ điển quốc gia mang `class_idx` thật (theo chủ ý —
            # `class_idx` là ĐỊNH DANH, không phải trạng thái sẵn sàng), nên
            # không có gì khác ngăn một lớp 0 mẫu đi vào tập huấn luyện. Nhãn
            # "Đã đủ điều kiện huấn luyện" trên giao diện là thông tin, không
            # phải hàng rào — người dùng gọi thẳng API thì nó không tồn tại.
            from app.config import settings as _cfg

            nguong = int(_cfg.min_samples_per_class_for_training or 0)
            if nguong > 0:
                du = _eligible_class_counts(selected_dialects, nguong)
                ngheo = [d for d in selected_dialects if du.get(d, 0) < 2]
                if ngheo:
                    chi_tiet = ", ".join(f"{d} ({du.get(d, 0)} lớp đạt)" for d in ngheo)
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Không đủ lớp đã thu đủ mẫu để huấn luyện: {chi_tiet}. "
                            f"Một lớp phải có ≥{nguong} npz "
                            f"(≈{nguong // 5} lần quay) mới được tính, và mỗi "
                            f"phương ngữ cần ≥2 lớp như vậy."
                        ),
                    )

                # Cổng thứ ba, và là cổng duy nhất nhìn vào thứ trainer THẬT SỰ
                # đọc. Hai cổng trên hỏi về CSDL; tệp split trên đĩa mới là đầu
                # vào. Chúng lệch nhau được, và khi lệch thì lượt chạy học một
                # tập nhãn khác với tập nhãn vừa được duyệt.
                lan = _split_classes_below_floor(selected_dialects, nguong, hien_vat)
                if lan:
                    khai = _split_snapshot(hien_vat)
                    san_split = khai.get("min_samples_per_class")
                    vi_du = "; ".join(f"{ten} ({n} mẫu)" for ten, _uid, n in lan[:5])
                    them = f" và {len(lan) - 5} lớp nữa" if len(lan) > 5 else ""
                    if san_split is None:
                        ly_do = ("Tập chia hiện tại không khai báo sàn nào "
                                 "(dựng trước khi có cơ chế này).")
                    elif int(san_split or 0) < nguong:
                        ly_do = (f"Tập chia được dựng với sàn {san_split}, "
                                 f"thấp hơn sàn đang áp ({nguong}).")
                    else:
                        ly_do = (f"Tập chia khai sàn {san_split} nhưng dữ liệu đã đổi "
                                 f"từ lúc chia — có mẫu bị xoá sau đó.")
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Tập chia còn {len(lan)} lớp chưa đủ {nguong} mẫu: "
                            f"{vi_du}{them}. {ly_do} "
                            f"Hãy chia lại trước khi huấn luyện: "
                            f"python processed/splits/make_splits.py "
                            f"--min_samples_per_class={nguong}. "
                            f"Hệ thống KHÔNG tự lọc các lớp này ra, vì một checkpoint "
                            f"huấn luyện trên tập nhỏ hơn tệp split khai báo là một "
                            f"checkpoint nói sai về nguồn gốc của nó."
                        ),
                    )

                # Cổng thứ tư: CHỨNG CỨ, không phải lời khai. Ba cổng trên tin
                # vào CSDL và vào `split_metadata.json`; cổng này chỉ đọc nội
                # dung tệp split. Lời khai sai — vì lỗi, vì sửa tay, vì tệp bị
                # thay sau khi khai — thì chỉ chỗ này bắt được.
                bang_chung = _split_evidence_problems(selected_dialects, nguong, hien_vat)
                if bang_chung:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Nội dung tập chia không khớp với chính sách nó khai báo: "
                            + "; ".join(bang_chung)
                            + f". Chia lại: python processed/splits/make_splits.py "
                              f"--min_samples_per_class={nguong}."
                        ),
                    )

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
            # Chủ sở hữu lấy từ tenant NHÀ của người gọi — cùng nguồn mà
            # `guard_quota` và cổng hiện vật ở trên đã dùng. Ba quyết định về
            # một lượt chạy phải đọc cùng một danh tính.
            "tenant_id": pham_vi_nguoi_goi,
        }

        # Persist BEFORE enqueue: if the backend dies right after, the job
        # is recoverable instead of silently vanishing.
        await _persist_job(job, auth_user_id=str(current_user.get("id") or "") or None)

        # Dispatch to the dedicated trainer container (Celery queue "training",
        # concurrency 1 — jobs execute strictly one at a time, off the API CPU).
        # Retry a few times with backoff so a momentary broker blip (e.g. Redis
        # being recreated during a deploy) doesn't turn into a failed job.
        try:
            from app.training_tasks import run_training_job

            dispatch_err = None
            for attempt in range(3):
                try:
                    await run_in_threadpool(
                        run_training_job.apply_async,
                        kwargs={"job_id": job_id}, queue="training",
                    )
                    dispatch_err = None
                    break
                except Exception as e:  # broker hiccup — brief backoff, then retry
                    dispatch_err = e
                    logger.warning(
                        "job=%s dispatch attempt %d/3 failed: %s", job_id, attempt + 1, e
                    )
                    if attempt < 2:
                        await asyncio.sleep(0.5 * (attempt + 1))
            if dispatch_err is not None:
                raise dispatch_err
            logger.info("job=%s dispatched to trainer by user=%s", job_id, current_user.get("username"))
        except Exception as dispatch_err:
            job.status = "failed"
            job.completed_at = datetime.now().isoformat()
            job.error_message = f"Không gửi được job tới trainer (Redis/Celery down?): {dispatch_err}"
            await _persist_job(job)
            # A dispatch failure is always a system/infra problem (not the user's
            # data) → escalate to admins.
            try:
                from app.training_alerts import notify_admins_training_failure

                notify_admins_training_failure(
                    job_id=job_id,
                    actor=str(current_user.get("username") or current_user.get("id") or ""),
                    error=job.error_message,
                    source="dispatch",
                )
            except Exception:
                pass
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

        rows = await run_in_threadpool(list_training_jobs_with_user, limit)
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
                    ckpt = await run_in_threadpool(load_checkpoint, ckpt_path)
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

            rows = await run_in_threadpool(list_training_metrics, job_id)
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
        ckpt = await asyncio.to_thread(load_checkpoint, str(job.checkpoint_path))
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


@router.post("/jobs/{job_id}/promote", response_model=PromoteResponse, dependencies=[Depends(limit_training)])
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
        ckpt = await asyncio.to_thread(load_checkpoint, str(src_path))
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

    # Promoting means "everyone now sees this in the realtime tab". A model
    # trained on a dialect still waiting for approval must not get there: its
    # label set describes a vocabulary only one person has proposed. Approve the
    # dialect first, then promote — the order matters, not the permission of the
    # admin doing it.
    owner = dialect_owner(dialect)
    if owner is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Phương ngữ '{dialect}' đang chờ duyệt nên model của nó chỉ người tạo "
                f"dùng được. Duyệt phương ngữ trước, rồi mới promote."
            ),
        )

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
    job.superseded_at = None
    job.checkpoint_path = deployed_path
    await _persist_job(job)

    # 4b. One dialect = one realtime slot, so the job that used to hold this
    #     slot is no longer serving. _update_registry already dropped its entry
    #     from models.json; without this the database still called it promoted,
    #     and two jobs showed as live for one dialect.
    try:
        from app.storage.metadata_db import supersede_other_promotions

        retired = await asyncio.to_thread(supersede_other_promotions, job_id, dialect)
        # The in-memory cache never re-reads a terminal job (see
        # _ensure_job_loaded), so a DB-only update would keep serving the stale
        # flag until the backend restarts.
        stamp = datetime.now().isoformat()
        for old_id in retired:
            cached = training_jobs.get(old_id)
            if cached:
                cached["job"].superseded_at = stamp
        if retired:
            logger.info("job=%s superseded %d earlier promotion(s) for dialect=%s",
                        job_id, len(retired), dialect)
    except Exception as e:
        # Promotion itself already succeeded; a bookkeeping failure must not
        # undo a model that is now serving traffic.
        logger.warning("job=%s không đánh dấu được promotion cũ của '%s': %s", job_id, dialect, e)

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
    Auth: browsers cannot set headers on WS. Same-origin WS handshakes DO send
    cookies, so we read the httpOnly access cookie; the ?token= query param is
    kept as a fallback for legacy Bearer clients.
    """
    if not token:
        token = websocket.cookies.get(ACCESS_COOKIE, "")
    user = await asyncio.to_thread(get_user_from_token, token) if token else None
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # ★ C3 — `TenantScopeMiddleware` KHÔNG chạy cho WebSocket.
    #
    # Nó thoát sớm ở `scope["type"] != "http"`, có chủ ý và đúng với `lifespan`.
    # Hệ quả là mọi truy vấn trong endpoint này chạy NGOÀI phạm vi tenant, và
    # từ đó có hai chuyện:
    #
    #   `training_jobs`     RLS fail-CLOSED khi không phạm vi  ->  đọc ra rỗng
    #   `training_metrics`  không có tenant_id, không có RLS   ->  đọc ra ĐỦ
    #
    # Nghĩa là cổng duy nhất bảo vệ chỉ số huấn luyện là hàng job cha; chạy
    # ngoài phạm vi thì cổng ấy vừa chặn nhầm người đúng, vừa không chặn được
    # gì ở bảng chỉ số. Đặt phạm vi ở đây làm cả hai chuyện đó biến mất.
    #
    # Phạm vi lấy từ tài khoản ĐÃ xác thực ngay phía trên, cùng nguồn mà
    # middleware dùng cho đường HTTP — không phải từ `job_id` người gọi đưa.
    from app.tenant_context import tenant_scope

    pham_vi = str((user or {}).get("tenant_id") or "").strip()
    if not pham_vi:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    with tenant_scope(pham_vi):
        await _phat_tien_do(websocket, job_id)


async def _phat_tien_do(websocket: WebSocket, job_id: str) -> None:
    """Thân của endpoint WS, tách ra để phạm vi tenant bọc trọn vòng đời.

    `asyncio.to_thread` chép ngữ cảnh hiện tại sang luồng phụ, nên các lượt đọc
    CSDL bên trong vẫn thấy phạm vi đã đặt.
    """
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


@router.post("/jobs/{job_id}/predict", response_model=TrainedModelPredictResponse, dependencies=[Depends(limit_predict)])
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
