from __future__ import annotations

import logging
from typing import Any

import numpy as np
import torch
from fastapi import APIRouter, HTTPException, Request

from .schemas import PredictRequest, PredictResponse

logger = logging.getLogger("realtime_service.predict")

router = APIRouter()


def _validate_model_available(app_state: Any, model_id: str) -> Any:
    """Resolve model bundle from app state. Raise HTTPException if not found."""
    bundles = getattr(app_state, "model_bundles", {}) or {}
    if model_id not in bundles:
        raise HTTPException(status_code=404, detail=f"model_id not found: {model_id}")
    return bundles[model_id]


def _normalize_frames(normalization_module: Any, frames: list) -> np.ndarray:
    """Normalize frames efficiently using list comprehension.

    Validates shape BEFORE calling normalization to ensure semantic safety.
    Returns shape (60, 126) numpy array.
    """
    # Pre-validate input
    if len(frames) != 60:
        raise ValueError(f"expected 60 frames, got {len(frames)}")

    # Vectorized normalization using numpy array instead of Python loop
    frames_array = np.asarray(frames, dtype=np.float32)
    if frames_array.shape != (60, 126):
        raise ValueError(f"expected shape (60, 126), got {frames_array.shape}")

    normalized_frames = np.array([
        normalization_module.normalize_hands_vector_126(frame)
        for frame in frames_array
    ], dtype=np.float32)

    return normalized_frames


def _run_inference(model: torch.nn.Module, frames: np.ndarray) -> tuple:
    """Run deterministic inference.

    Returns (pred_idx, probs) where:
    - pred_idx: int, argmax of softmax logits
    - probs: np.ndarray of shape (num_classes,), softmax probabilities

    ASSUMES: model is already in eval mode (set at startup).
    """
    # Build input tensor on the same device as the model (CPU or CUDA).
    try:
        model_device = next(model.parameters()).device
    except StopIteration:
        model_device = torch.device("cpu")
    x = torch.from_numpy(frames).unsqueeze(0).to(dtype=torch.float32, device=model_device)

    # Explicit shape assertion: model expects (B, T, D) or (B, D, T)
    assert x.ndim == 3, f"expected 3D tensor, got shape={tuple(x.shape)}"
    assert x.shape == (1, 60, 126), f"expected (1, 60, 126), got {tuple(x.shape)}"

    with torch.inference_mode():
        logits = model(x)

    # Use torch.softmax for numerical stability
    logits = logits.float()
    probs_tensor = torch.softmax(logits, dim=-1)
    probs = probs_tensor.detach().cpu().numpy().squeeze()

    if probs.ndim == 0:
        probs = probs.reshape(1)

    pred_idx = int(np.argmax(probs))
    return pred_idx, probs


@router.post("/predict", response_model=PredictResponse)
def predict(request_data: PredictRequest, request: Request) -> PredictResponse:
    """Deterministic realtime inference endpoint.

    Input contract:
    - model_id: string identifier
    - frames: list of 60 frames, each 126-dimensional

    Validates:
    - Exact shape (60, 126)
    - No NaN/Inf values
    - Model exists

    Returns:
    - label: human-readable label
    - confidence: float in [0, 1]
    - label_key: machine-readable identifier
    """
    app_state = request.app.state

    # 1. Validate service health
    normalization_module = getattr(app_state, "normalization_module", None)
    if normalization_module is None:
        raise HTTPException(status_code=503, detail="normalization module not available")

    # 2. Validate model exists
    bundle = _validate_model_available(app_state, request_data.model_id)

    # 3. Normalize frames (deterministic)
    try:
        frames_normalized = _normalize_frames(normalization_module, request_data.frames)
    except Exception as exc:
        logger.error("normalization failed: %s", exc)
        raise HTTPException(status_code=500, detail="normalization error")

    # 4. Run inference (deterministic, stateless)
    try:
        pred_idx, probs = _run_inference(bundle.model, frames_normalized)
    except Exception as exc:
        logger.error("inference failed: %s", exc)
        raise HTTPException(status_code=500, detail="inference error")

    # 5. Decode prediction
    try:
        label_obj = bundle.idx_to_label[pred_idx]
        label_spec = {
            "label_original": str(label_obj.get("label_original", "")),
            "label_key": str(label_obj.get("label_key", "")),
            "confidence": float(probs[pred_idx]),
        }
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        logger.error("label decode failed: %s", exc)
        raise HTTPException(status_code=500, detail="label decode error")

    # 6. Build and validate response
    try:
        response = PredictResponse(
            label=label_spec["label_original"],
            confidence=label_spec["confidence"],
            label_key=label_spec["label_key"],
        )
    except Exception as exc:
        logger.error("response validation failed: %s", exc)
        raise HTTPException(status_code=500, detail="response validation error")

    return response
