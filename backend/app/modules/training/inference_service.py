"""Checkpoint loading and local inference for completed training jobs."""

from __future__ import annotations

import asyncio
import csv
import importlib
import logging
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, Optional

import numpy as np
import torch
import torch.nn as nn

from app.modules.training.schemas import TrainedModelPredictResponse

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path("/workspace")
LABELS_CSV = WORKSPACE_ROOT / "dataset" / "labels.csv"

_MODEL_NAME_TO_REGISTRY_KEY = {
    "cnn": "cnn",
    "lstm": "lstm",
    "bigru + attention": "bigru_attention",
    "bigru attention": "bigru_attention",
    "bigru_attention": "bigru_attention",
    "handgcn": "handgcn",
    "hdgcn": "handgcn",
    "hd-gcn": "handgcn",
    "hd_gcn": "handgcn",
    "tcn": "tcn",
}


class InferenceJobNotFoundError(LookupError):
    """Raised when a job or its checkpoint cannot be used for inference."""


def load_checkpoint(checkpoint_path: Path | str) -> dict[str, Any]:
    """Load a trusted training checkpoint on CPU."""
    return torch.load(checkpoint_path, map_location="cpu", weights_only=False)


def _import_models_registry(workspace_root: Path = WORKSPACE_ROOT):
    """Import the model registry as a package so relative imports keep working."""
    workspace = str(workspace_root)
    if workspace not in sys.path:
        sys.path.insert(0, workspace)
    return importlib.import_module("processed.train_utils.models")


def _load_model_from_checkpoint(
    checkpoint_path: Path,
    model_type_override: Optional[str] = None,
    *,
    workspace_root: Path = WORKSPACE_ROOT,
) -> tuple[nn.Module, dict[str, Any]]:
    """Build the checkpoint's real architecture and restore its weights."""
    ckpt = load_checkpoint(checkpoint_path)
    model_type = model_type_override or ckpt.get("model_type", "TCN")
    model_config = ckpt.get("model_config", {}) or {}
    num_classes = int(ckpt.get("num_classes", 7))
    feature_dim = int(ckpt.get("feature_dim", 126))
    model_type_lower = str(model_type).lower().replace(" (legacy)", "").strip()
    registry_key = _MODEL_NAME_TO_REGISTRY_KEY.get(model_type_lower)

    try:
        models_module = _import_models_registry(workspace_root)
        resolved_key = registry_key if registry_key and registry_key != "tcn" else "tcn"
        model = models_module.get_model_class(resolved_key).from_config(
            input_dim=feature_dim,
            output_dim=num_classes,
            config=model_config,
        ).to("cpu")
        logger.info(
            "Loaded %s model from registry (checkpoint model_type=%s)",
            resolved_key,
            model_type,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to build '{model_type}' model from registry for checkpoint "
            f"{checkpoint_path.name}: {exc}"
        ) from exc

    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    return model, ckpt


def _normalization_function(workspace_root: Path = WORKSPACE_ROOT):
    normalization_path = workspace_root / "processed" / "shared" / "normalization.py"
    spec = spec_from_file_location("training_normalization", normalization_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import normalization module: {normalization_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.normalize_hands_vector_126


def _resolve_label(
    checkpoint: dict[str, Any],
    prediction_index: int,
    labels_csv: Path = LABELS_CSV,
) -> tuple[str, str]:
    """Resolve both stable label key and human-readable label."""
    index_to_label = checkpoint.get("idx_to_label")
    label_key = f"class_{prediction_index}"
    label = label_key

    value: Any = None
    if isinstance(index_to_label, dict):
        value = index_to_label.get(prediction_index)
        if value is None:
            value = index_to_label.get(str(prediction_index))
    elif isinstance(index_to_label, list) and prediction_index < len(index_to_label):
        value = index_to_label[prediction_index]

    if isinstance(value, dict):
        label_key = str(value.get("label_key") or label_key).strip()
        label = str(value.get("label_original") or "").strip() or label_key
        return label_key, label
    if value:
        label_key = str(value).strip()
        label = label_key

    if labels_csv.exists():
        slug = label_key.replace("\\", "/").split("/")[-1]
        try:
            with labels_csv.open("r", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    if row.get("slug", "").strip() == slug:
                        label = row.get("label_original", "").strip() or label
                        break
        except Exception as exc:
            logger.warning("Error loading labels.csv: %s", exc)
    return label_key, label


def predict_checkpoint(
    checkpoint_path: Path,
    frames: list[list[float]],
    *,
    workspace_root: Path = WORKSPACE_ROOT,
    labels_csv: Path = LABELS_CSV,
) -> TrainedModelPredictResponse:
    """Normalize a 60-frame window and infer it with one checkpoint."""
    frames_array = np.asarray(frames, dtype=np.float32)
    if frames_array.shape != (60, 126):
        raise ValueError(f"Expected shape (60, 126), got {frames_array.shape}")

    normalize = _normalization_function(workspace_root)
    normalized_frames = np.array([normalize(frame) for frame in frames_array], dtype=np.float32)
    model, checkpoint = _load_model_from_checkpoint(
        checkpoint_path,
        workspace_root=workspace_root,
    )
    tensor = torch.from_numpy(normalized_frames).unsqueeze(0).to(dtype=torch.float32)
    with torch.no_grad():
        try:
            logits = model(tensor, torch.tensor([60]))
        except TypeError:
            logits = model(tensor)

    probabilities = torch.softmax(logits, dim=-1).detach().cpu().numpy().squeeze()
    prediction_index = int(np.argmax(probabilities))
    label_key, label = _resolve_label(checkpoint, prediction_index, labels_csv)
    return TrainedModelPredictResponse(
        label=label,
        confidence=float(probabilities[prediction_index]),
        label_key=label_key,
    )


async def predict_job(
    job_id: str,
    frames: list[list[float]],
    *,
    ensure_job,
    predict,
    workspace_root: Path = WORKSPACE_ROOT,
    labels_csv: Path = LABELS_CSV,
) -> TrainedModelPredictResponse:
    """Resolve a persisted job and run inference with its deployed checkpoint."""
    job_info = await ensure_job(job_id)
    if not job_info:
        raise InferenceJobNotFoundError(f"Training job {job_id} not found")

    job = job_info.get("job")
    if not job:
        raise InferenceJobNotFoundError("Job object not found")

    checkpoint_path = job.checkpoint_path
    if not checkpoint_path or not Path(checkpoint_path).exists():
        raise InferenceJobNotFoundError("Model checkpoint not found")

    return await asyncio.to_thread(
        predict,
        Path(checkpoint_path),
        frames,
        workspace_root=workspace_root,
        labels_csv=labels_csv,
    )
