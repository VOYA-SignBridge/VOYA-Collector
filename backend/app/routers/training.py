"""
Training Pipeline API Router
Auto-loads dataset, manages training jobs, and streams real-time progress.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import subprocess
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import torch
import torch.nn as nn
import numpy as np
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel

router = APIRouter(prefix="/training", tags=["training"])

# ============================================================================
# TCN Model Classes (for training model inference)
# ============================================================================

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


# Lưu trữ trạng thái training jobs
training_jobs: Dict[str, Dict[str, Any]] = {}
training_websockets: Dict[str, List[WebSocket]] = {}

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
    split_info: Optional[Dict[str, int]] = None  # train, val, test counts


class TrainingConfig(BaseModel):
    """Cấu hình training"""
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
    status: str  # pending, running, completed, failed
    config: TrainingConfig
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    current_epoch: int = 0
    total_epochs: int = 80
    checkpoint_path: Optional[str] = None  # Path to saved model after training
    test_acc: Optional[float] = None  # Test accuracy from checkpoint
    test_f1: Optional[float] = None  # Test F1 score from checkpoint


class TrainingMetrics(BaseModel):
    """Metrics trong quá trình training"""
    epoch: int
    train_loss: float
    train_acc: float
    val_loss: float
    val_acc: float
    val_f1: float
    learning_rate: Optional[float] = None
    handedness: Optional[Dict[str, Any]] = None


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


def _count_samples_by_class() -> Dict[str, int]:
    """Đếm số samples cho mỗi class"""
    samples, _ = _load_samples_and_labels()

    class_counts: Dict[str, int] = {}
    for sample in samples:
        class_uid = sample.get("class_uid", "").strip()
        if class_uid:
            class_counts[class_uid] = class_counts.get(class_uid, 0) + 1

    return class_counts


def _copy_checkpoint_to_deployment(src_path: Path, model_id: str) -> Optional[str]:
    """Copy model từ outputs/ tới checkpoints/ cho realtime service"""
    try:
        CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

        # Tên model mới
        stem = src_path.stem  # "tcn_18_20260606_052123"
        new_name = f"{stem}.pt"
        dst_path = CHECKPOINTS_DIR / new_name

        # Copy file
        if src_path.exists():
            dst_path.write_bytes(src_path.read_bytes())
            print(f"[TRAINING] Checkpoint copied: {src_path} → {dst_path}")

            # Copy JSON metadata nếu có
            json_src = src_path.with_suffix(".json")
            if json_src.exists():
                json_dst = dst_path.with_suffix(".json")
                json_dst.write_bytes(json_src.read_bytes())

            return str(dst_path)
    except Exception as e:
        print(f"[TRAINING] Failed to copy checkpoint: {e}")

    return None


def _update_registry(model_id: str, checkpoint_path: str, model_meta: Dict[str, Any]) -> bool:
    """Update models.json registry để realtime service load model mới"""
    try:
        if not REGISTRY_PATH.exists():
            print(f"[TRAINING] Registry not found: {REGISTRY_PATH}")
            return False

        # Load existing registry
        registry_data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

        # Thêm/update model entry with required fields for realtime service
        model_entry = {
            "id": model_id,
            "name": f"Training {model_meta.get('training_job_id', model_id)[-8:]}",
            "checkpoint_path": checkpoint_path,
            "language": "vn",
            "dialect": model_meta.get("config", {}).get("dialects", ["multi"])[0] if model_meta.get("config", {}).get("dialects") else "multi",
            "seq_len": 60,
            "feature_dim": 126,
            "normalization_version": "v1",
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
                "expects_strict_shape": [60, 126]
            }
        }

        if "models" not in registry_data:
            registry_data["models"] = []

        # Remove existing model with same ID
        registry_data["models"] = [m for m in registry_data["models"] if m.get("id") != model_id]

        # Add new model
        registry_data["models"].append(model_entry)

        # Write updated registry
        REGISTRY_PATH.write_text(json.dumps(registry_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[TRAINING] Registry updated: {model_id}")

        return True
    except Exception as e:
        print(f"[TRAINING] Failed to update registry: {e}")

    return False


def _notify_realtime_service_reload(model_id: str, checkpoint_path: str, version_string: str) -> bool:
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
                    "language": "vn",
                },
            )
            if response.status_code == 200:
                print(f"[TRAINING] Realtime service reloaded model: {model_id}")
                return True
            else:
                print(f"[TRAINING] Realtime service reload failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"[TRAINING] Failed to notify realtime service: {e}")
        return False


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/dataset-info", response_model=DatasetInfo)
async def get_dataset_info(
    dialect: Optional[str] = Query(None, description="Filter by dialect"),
    language: Optional[str] = Query("vn", description="Filter by language"),
) -> DatasetInfo:
    """
    Lấy thông tin dataset hiện tại

    Auto-load từ folder dataset, không cần upload
    """
    try:
        print(f"[DEBUG] WORKSPACE_ROOT: {WORKSPACE_ROOT}")
        print(f"[DEBUG] DATASET_ROOT: {DATASET_ROOT}")
        print(f"[DEBUG] SAMPLES_CSV exists: {SAMPLES_CSV.exists()}")
        print(f"[DEBUG] LABELS_CSV exists: {LABELS_CSV.exists()}")

        samples, labels = _load_samples_and_labels()
        dialects_map = _get_dialects_by_language()
        class_counts = _count_samples_by_class()

        # Nếu có filter dialect/language
        if dialect or language:
            # TODO: implement filtering logic
            pass

        return DatasetInfo(
            total_samples=len(samples),
            total_classes=len(set(s.get("class_uid") for s in samples if s.get("class_uid"))),
            languages=list(dialects_map.keys()),
            dialects=dialects_map,
            class_distribution=class_counts,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tải dataset: {str(e)}")


@router.post("/start", response_model=TrainingJob)
async def start_training(config: TrainingConfig) -> TrainingJob:
    """
    Bắt đầu training job

    Tạo job ID, setup subprocess, return job info
    """
    try:
        job_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        job = TrainingJob(
            id=job_id,
            status="pending",
            config=config,
            created_at=now,
            total_epochs=config.epochs,
        )

        training_jobs[job_id] = {
            "job": job,
            "process": None,
            "progress": [],
            "latest_metrics": None,
        }

        # Bắt đầu training trong background
        asyncio.create_task(_run_training_subprocess(job_id, config))

        return job

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi bắt đầu training: {str(e)}")


@router.get("/jobs/{job_id}", response_model=TrainingJob)
async def get_job_status(job_id: str) -> TrainingJob:
    """Lấy trạng thái training job"""
    if job_id not in training_jobs:
        raise HTTPException(status_code=404, detail=f"Training job {job_id} không tìm thấy")

    job = training_jobs[job_id]["job"]

    # Load test metrics from checkpoint if job is completed
    if job.status == "completed" and job.checkpoint_path:
        print(f"[JOB {job_id}] Checking test metrics: test_acc={job.test_acc}, checkpoint={job.checkpoint_path}")
        if not job.test_acc:  # Only load if not already set
            try:
                ckpt_path = Path(job.checkpoint_path)
                print(f"[JOB {job_id}] Loading checkpoint from {ckpt_path}, exists={ckpt_path.exists()}")
                if ckpt_path.exists():
                    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
                    metrics = ckpt.get("metrics", {})
                    print(f"[JOB {job_id}] Checkpoint metrics keys: {list(metrics.keys())}")
                    job.test_acc = float(metrics.get("test_acc", 0)) if metrics.get("test_acc") is not None else None
                    job.test_f1 = float(metrics.get("test_f1", 0)) if metrics.get("test_f1") is not None else None
                    print(f"[JOB {job_id}] ✓ Loaded test metrics: acc={job.test_acc:.4f}, f1={job.test_f1:.4f}")
                else:
                    print(f"[JOB {job_id}] ✗ Checkpoint file not found")
            except Exception as e:
                print(f"[JOB {job_id}] ✗ Error loading test metrics: {e}")
                import traceback
                traceback.print_exc()

    return job


@router.get("/jobs/{job_id}/metrics", response_model=List[TrainingMetrics])
async def get_job_metrics(job_id: str) -> List[TrainingMetrics]:
    """Lấy metrics của training job"""
    if job_id not in training_jobs:
        raise HTTPException(status_code=404, detail=f"Training job {job_id} không tìm thấy")

    return training_jobs[job_id]["progress"]


@router.websocket("/ws/{job_id}")
async def websocket_training_progress(websocket: WebSocket, job_id: str):
    """
    WebSocket để stream real-time training progress

    Gửi metrics, epoch progress, handedness breakdowns
    """
    if job_id not in training_jobs:
        await websocket.close(code=4004, reason="Job not found")
        return

    await websocket.accept()

    if job_id not in training_websockets:
        training_websockets[job_id] = []

    training_websockets[job_id].append(websocket)

    try:
        # Gửi job status hiện tại trước tiên
        await websocket.send_json({
            "type": "status",
            "data": training_jobs[job_id]["job"].dict(),
        })

        # Gửi metrics cũ đã có
        for metric in training_jobs[job_id]["progress"]:
            await websocket.send_json({
                "type": "metric",
                "data": metric.dict(),
            })

        # Chờ new updates
        while True:
            data = await websocket.receive_text()
            # Client có thể gửi heartbeat hoặc commands
            if data == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        training_websockets[job_id].remove(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")


# ============================================================================
# Background Tasks
# ============================================================================

async def _run_training_subprocess(job_id: str, config: TrainingConfig):
    """Chạy train_tcn.py subprocess"""
    job_info = training_jobs[job_id]
    job_info["job"].status = "running"
    job_info["job"].started_at = datetime.now().isoformat()

    # Save event loop for use in background threads
    loop = asyncio.get_running_loop()

    # Broadcast status update immediately
    await _broadcast_status(job_id, job_info["job"])

    try:
        # Xây dựng command
        cmd = [
            "python",
            "-m",
            "processed.train_utils.train_tcn",
            f"--epochs={config.epochs}",
            f"--batch_size={config.batch_size}",
            f"--lr={config.learning_rate}",
            f"--dropout={config.dropout}",
            f"--channels={config.channels}",
            f"--levels={config.levels}",
            f"--kernel_size={config.kernel_size}",
            "--run_diagnostics",
        ]

        # Thêm dialect/language filters nếu có
        if config.dialects:
            for dialect in config.dialects:
                cmd.append(f"--dialect={dialect}")
        if config.languages:
            for language in config.languages:
                cmd.append(f"--filter_language={language}")

        # Debug
        # CWD phải là /workspace (project root mount point trong Docker)
        cwd_path = "/workspace"
        print(f"[TRAINING {job_id}] Starting subprocess")
        print(f"[TRAINING {job_id}] CWD: {cwd_path}")
        print(f"[TRAINING {job_id}] CMD: {' '.join(cmd)}")

        # Chạy subprocess
        env = os.environ.copy()
        env['PYTHONPATH'] = str(WORKSPACE_ROOT)
        env['PYTHONUNBUFFERED'] = '1'
        process = subprocess.Popen(
            cmd,
            cwd=cwd_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )

        print(f"[TRAINING {job_id}] Process started with PID {process.pid}")

        job_info["process"] = process

        # Read subprocess output in background thread to avoid deadlock
        import threading

        def read_process_output():
            """Threaded function to read and parse subprocess output"""
            handedness_data = {}
            try:
                print(f"[TRAINING {job_id}] Starting to read stdout...")
                for line in process.stdout:
                    if not line:
                        continue
                    line = line.strip()
                    # Log all output lines
                    print(f"[TRAINING {job_id}] OUT: {line}")

                    # Parse handedness: "left_only:0.85(150) right_only:0.90(120) both:0.88(200)"
                    if "left_only:" in line and "right_only:" in line:
                        try:
                            handedness_data = {}
                            left_match = re.search(r'left_only:([\d.]+)\((\d+)\)', line)
                            if left_match:
                                handedness_data['left_only_acc'] = float(left_match.group(1))
                                handedness_data['left_only_n'] = int(left_match.group(2))

                            right_match = re.search(r'right_only:([\d.]+)\((\d+)\)', line)
                            if right_match:
                                handedness_data['right_only_acc'] = float(right_match.group(1))
                                handedness_data['right_only_n'] = int(right_match.group(2))

                            both_match = re.search(r'both:([\d.]+)\((\d+)\)', line)
                            if both_match:
                                handedness_data['both_acc'] = float(both_match.group(1))
                                handedness_data['both_n'] = int(both_match.group(2))
                        except Exception as e:
                            print(f"[TRAINING {job_id}] Error parsing handedness: {e}")

                    # Parse epoch output: "epoch 001 | train loss 0.1234 acc 0.9234 | val loss ..."
                    if "epoch" in line and "train loss" in line:
                        try:
                            parts = line.split("|")
                            epoch_str = parts[0].split()[-1]  # "001"
                            epoch = int(epoch_str)
                            job_info["job"].current_epoch = epoch

                            train_part = parts[1]
                            val_part = parts[2] if len(parts) > 2 else ""

                            train_loss = float(train_part.split("loss")[1].split("acc")[0].strip())
                            train_acc = float(train_part.split("acc")[1].strip())
                            val_loss = float(val_part.split("loss")[1].split("acc")[0].strip())
                            val_acc = float(val_part.split("acc")[1].split("f1")[0].strip())
                            val_f1 = float(val_part.split("f1")[1].strip())

                            metric = TrainingMetrics(
                                epoch=epoch,
                                train_loss=train_loss,
                                train_acc=train_acc,
                                val_loss=val_loss,
                                val_acc=val_acc,
                                val_f1=val_f1,
                                handedness=handedness_data if handedness_data else None,
                            )

                            job_info["progress"].append(metric)
                            job_info["latest_metrics"] = metric

                            # Broadcast asynchronously
                            asyncio.run_coroutine_threadsafe(
                                _broadcast_metric(job_id, metric),
                                loop
                            )

                        except Exception as parse_error:
                            print(f"[TRAINING {job_id}] Error parsing training output: {parse_error}")
            except Exception as e:
                print(f"[TRAINING {job_id}] Error reading stdout: {e}")

        # Start background thread to read output
        output_thread = threading.Thread(target=read_process_output, daemon=True)
        output_thread.start()

        # Also capture stderr for debugging
        def read_stderr():
            try:
                for line in process.stderr:
                    if line:
                        print(f"[TRAINING {job_id}] STDERR: {line.strip()}")
            except Exception as e:
                print(f"[TRAINING {job_id}] Error reading stderr: {e}")

        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()

        # Wait for process in background thread (non-blocking for asyncio)
        try:
            await asyncio.to_thread(process.wait)
        except Exception as wait_err:
            print(f"[TRAINING {job_id}] Error waiting for process: {wait_err}")

        print(f"[TRAINING {job_id}] Process exited with returncode: {process.returncode}")
        if process.returncode == 0:
            job_info["job"].status = "completed"

            # ✅ Find & deploy checkpoint
            try:
                # Find latest .pt file in outputs
                output_files = sorted(OUTPUTS_DIR.glob("*.pt"), key=lambda x: x.stat().st_mtime, reverse=True)
                print(f"[TRAINING {job_id}] Found {len(output_files)} checkpoint files in {OUTPUTS_DIR}")
                if output_files:
                    latest_checkpoint = output_files[0]
                    model_id = f"training_{job_id}"

                    # Copy to checkpoints & update registry
                    deployed_path = _copy_checkpoint_to_deployment(latest_checkpoint, model_id)
                    if deployed_path:
                        job_info["job"].checkpoint_path = deployed_path

                        # Load test metrics from checkpoint immediately
                        try:
                            ckpt = torch.load(deployed_path, map_location="cpu", weights_only=False)
                            metrics = ckpt.get("metrics", {})
                            if metrics:
                                job_info["job"].test_acc = float(metrics.get("test_acc", 0))
                                job_info["job"].test_f1 = float(metrics.get("test_f1", 0))
                                print(f"[TRAINING {job_id}] ✓ Test metrics loaded: acc={job_info['job'].test_acc:.4f}, f1={job_info['job'].test_f1:.4f}")
                        except Exception as e:
                            print(f"[TRAINING {job_id}] Error loading test metrics: {e}")

                        # Note: Training models are NOT added to registry
                        # They're served via /api/v1/training/jobs/{job_id}/predict endpoint
                        # which loads checkpoints directly without registry requirement

                        print(f"[TRAINING] Model deployed: {deployed_path}")
            except Exception as e:
                print(f"[TRAINING] Checkpoint deployment error: {e}")
        else:
            job_info["job"].status = "failed"

        job_info["job"].completed_at = datetime.now().isoformat()

        # Broadcast final status
        await _broadcast_status(job_id, job_info["job"])

    except Exception as e:
        job_info["job"].status = "failed"
        job_info["job"].completed_at = datetime.now().isoformat()
        print(f"Training subprocess error: {e}")
        await _broadcast_error(job_id, str(e))


async def _broadcast_metric(job_id: str, metric: TrainingMetrics):
    """Gửi metric đến tất cả WebSocket clients"""
    if job_id not in training_websockets:
        return

    disconnected = []
    for ws in training_websockets[job_id]:
        try:
            await ws.send_json({
                "type": "metric",
                "data": metric.dict(),
            })
        except Exception:
            disconnected.append(ws)

    # Cleanup disconnected
    for ws in disconnected:
        try:
            training_websockets[job_id].remove(ws)
        except:
            pass


async def _broadcast_status(job_id: str, job: TrainingJob):
    """Gửi status update"""
    if job_id not in training_websockets:
        return

    disconnected = []
    for ws in training_websockets[job_id]:
        try:
            await ws.send_json({
                "type": "status",
                "data": job.dict(),
            })
        except Exception:
            disconnected.append(ws)

    for ws in disconnected:
        try:
            training_websockets[job_id].remove(ws)
        except:
            pass


async def _broadcast_error(job_id: str, error_msg: str):
    """Gửi error message"""
    if job_id not in training_websockets:
        return

    for ws in training_websockets[job_id]:
        try:
            await ws.send_json({
                "type": "error",
                "message": error_msg,
            })
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
async def predict_trained_model(job_id: str, request_data: TrainedModelPredictRequest) -> TrainedModelPredictResponse:
    """Predict using trained model checkpoint (for Step 7 test modal).

    Load checkpoint locally and run inference without requiring registry entry.
    """
    # Validate job exists
    if job_id not in training_jobs:
        raise HTTPException(status_code=404, detail=f"Training job {job_id} not found")

    job_info = training_jobs[job_id]
    job = job_info.get("job")
    if not job:
        raise HTTPException(status_code=404, detail="Job object not found")

    checkpoint_path = job.checkpoint_path
    if not checkpoint_path or not Path(checkpoint_path).exists():
        raise HTTPException(status_code=404, detail="Model checkpoint not found")

    try:
        # Setup sys.path for imports
        import importlib.util
        import sys
        processed_root = str(WORKSPACE_ROOT / "processed")
        if processed_root not in sys.path:
            sys.path.insert(0, processed_root)

        # Import normalization from shared
        normalization_path = WORKSPACE_ROOT / "processed" / "shared" / "normalization.py"
        spec = importlib.util.spec_from_file_location("normalization", normalization_path)
        norm_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(norm_module)
        normalize_hands_vector_126 = norm_module.normalize_hands_vector_126

        # Normalize frames
        frames_array = np.asarray(request_data.frames, dtype=np.float32)
        if frames_array.shape != (60, 126):
            raise ValueError(f"Expected shape (60, 126), got {frames_array.shape}")

        normalized_frames = np.array([
            normalize_hands_vector_126(frame) for frame in frames_array
        ], dtype=np.float32)

        # Load checkpoint
        ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)

        # Get model config from checkpoint
        config = ckpt.get("config", {})
        num_classes = ckpt.get("num_classes", 7)

        # Build model using inline TCNClassifier
        print(f"[TRAINING {job_id}] Building TCN model: classes={num_classes}")
        model = TCNClassifier(
            feature_dim=126,
            num_classes=num_classes,
            channels=config.get("channels", 64),
            levels=config.get("levels", 3),
            kernel_size=config.get("kernel_size", 5),
            dropout=config.get("dropout", 0.3),
        )
        model.load_state_dict(ckpt["model_state_dict"])
        model.eval()

        # Run inference
        x = torch.from_numpy(normalized_frames).unsqueeze(0).to(dtype=torch.float32)
        with torch.no_grad():
            logits = model(x, torch.tensor([60]))

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

                print(f"[TRAINING {job_id}] Looking up slug='{slug}' from label_key='{label_key}'")

                with open(LABELS_CSV, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    found = False
                    for row in reader:
                        if row.get("slug", "").strip() == slug:
                            label_original = row.get("label_original", "").strip()
                            if label_original:
                                label = label_original
                                print(f"[TRAINING {job_id}] Found label_original: {label}")
                            found = True
                            break
                    if not found:
                        print(f"[TRAINING {job_id}] Slug '{slug}' not found in labels.csv")
        except Exception as e:
            print(f"[TRAINING {job_id}] Error loading labels.csv: {e}")

        return TrainedModelPredictResponse(
            label=label,
            confidence=confidence,
            label_key=label_key,
        )

    except Exception as e:
        import traceback
        print(f"[TRAINING {job_id}] Inference error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")
