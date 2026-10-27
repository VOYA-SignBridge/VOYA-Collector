"""Export an in-memory PyTorch sign model directly to float32 TFLite.

Official API: https://github.com/google-ai-edge/litert-torch/blob/main/docs/pytorch_converter/README.md

Call AFTER training and restoring the best validation weights:

    model.load_state_dict(best_state)  # an in-memory dict, not a .pt file
    export_tflite(model, "handgcn_lite.tflite", sample_input=validation_clip)

The converter needs the nn.Module AND sample inputs, not a bare state_dict.
This module never calls torch.save/load and does not train an exported model.
LiteRT Torch is imported lazily: normal PyTorch training needs no converter.
The upstream conversion environment currently targets Linux; set it up
separately. No TensorFlow reimplementation or checkpoint round-trip is used.
"""

from __future__ import annotations

import copy
import importlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable, Mapping, Optional, Union

import numpy as np
import torch
import torch.nn as nn


def require_litert_torch() -> Any:
    """Check the optional converter before spending time on a training run."""
    try:
        return importlib.import_module("litert_torch")
    except ImportError as exc:
        raise RuntimeError(
            "Direct TFLite export requires a working litert-torch environment. "
            "Follow https://github.com/google-ai-edge/litert-torch#installation "
            "(upstream currently targets Linux). No .pt fallback will be written. "
            f"Import error: {exc}"
        ) from exc


def export_tflite(
    model: nn.Module,
    output_path: Union[str, Path],
    *,
    sample_input: Optional[torch.Tensor] = None,
    seq_len: int = 60,
    validation_inputs: Iterable[torch.Tensor] = (),
    metadata: Optional[Mapping[str, Any]] = None,
    atol: float = 1e-5,
    rtol: float = 1e-4,
) -> Path:
    """Convert the model already in RAM, verify outputs, then export.

    The source model's weights, device, gradients and train/eval modes are
    untouched. Export operates on an independent CPU float32 evaluation copy.
    Shapes are FIXED to sample_input (default [1, 60, model.input_dim]).

    Verification covers the sample, zeros, deterministic random data and, for
    hands126, missing left/right hands. Pass preprocessed held-out clips via
    validation_inputs for meaningful checks of a trained model. This is output
    parity verification, not a claim about classification accuracy or speed.

    A sibling <name>.metadata.json records IO/configuration, conversion errors
    and the supplied training contract (labels, normalization, provenance).
    Normalization and softmax are NOT silently inserted into the model graph.
    """
    if not isinstance(model, nn.Module):
        raise TypeError("Pass an nn.Module, not a state_dict or checkpoint path")
    if not callable(getattr(model, "get_config", None)) or not callable(
        getattr(model, "get_model_name", None)
    ):
        raise TypeError("Expected the SignLanguageModel configuration interface")
    destination = Path(output_path)
    if destination.suffix.lower() != ".tflite":
        raise ValueError("output_path must end in .tflite")
    if atol < 0 or rtol < 0:
        raise ValueError("Verification tolerances must be non-negative")
    input_dim = getattr(model, "input_dim", None)
    if not isinstance(input_dim, int) or input_dim <= 0:
        raise ValueError("model.input_dim must describe the input features")
    if sample_input is None:
        if seq_len <= 0:
            raise ValueError("seq_len must be positive")
        sample_input = torch.zeros(1, seq_len, input_dim)

    def prepare(value: torch.Tensor) -> torch.Tensor:
        if not isinstance(value, torch.Tensor) or not value.is_floating_point():
            raise TypeError("Export inputs must be floating-point tensors")
        if value.ndim != 3 or value.shape[-1] != input_dim or min(value.shape) <= 0:
            raise ValueError("Expected nonempty [batch, frames, model.input_dim]")
        value = value.detach().cpu().to(torch.float32).contiguous().clone()
        if not torch.isfinite(value).all():
            raise ValueError("Export inputs contain NaN or infinity")
        return value

    sample = prepare(sample_input)
    generator = torch.Generator(device="cpu").manual_seed(0)
    random_clip = torch.randn(sample.shape, generator=generator)
    cases = [sample, torch.zeros_like(sample), random_clip]
    if input_dim == 126:
        left_only, right_only = random_clip.clone(), random_clip.clone()
        left_only[..., 63:] = 0
        right_only[..., :63] = 0
        cases.extend((left_only, right_only))
    for value in validation_inputs:
        value = prepare(value)
        if value.shape != sample.shape:
            raise ValueError("Every validation input must match the fixed export shape")
        cases.append(value)

    # Reject unserializable metadata before conversion or creating output files.
    training_contract = dict(metadata or {})
    json.dumps(training_contract, allow_nan=False)
    litert_torch = require_litert_torch()
    export_model = copy.deepcopy(model).cpu().float().eval()
    sample_inputs = (sample,)
    max_abs_error = 0.0
    with torch.no_grad():
        # Upstream API: eval nn.Module + tuple of positional tensor inputs.
        edge_model = litert_torch.convert(export_model, sample_inputs)
        for index, value in enumerate(cases):
            expected_tensor = export_model(value)
            if not isinstance(expected_tensor, torch.Tensor):
                raise TypeError("Expected a single logits tensor from the model")
            expected = expected_tensor.detach().numpy()
            actual = np.asarray(edge_model(value))
            if actual.shape != expected.shape:
                raise RuntimeError(f"TFLite output shape mismatch in validation case {index}")
            if not np.isfinite(expected).all() or not np.isfinite(actual).all():
                raise RuntimeError(f"Non-finite outputs in validation case {index}")
            try:
                np.testing.assert_allclose(actual, expected, atol=atol, rtol=rtol)
            except AssertionError as exc:
                raise RuntimeError(
                    f"TFLite/PyTorch outputs differ in validation case {index}; "
                    "the artifact was not exported"
                ) from exc
            max_abs_error = max(max_abs_error, float(np.max(np.abs(actual - expected))))

    manifest = {
        "schema_version": "1.0",
        "artifact_format": "tflite",
        "model_type": model.get_model_name(),
        "model_config": model.get_config(),
        "input": {"shape": list(sample.shape), "dtype": "float32",
                  "preprocessing": "external; identical to training"},
        "output": {"shape": list(expected.shape), "dtype": str(actual.dtype),
                   "semantics": "logits"},
        "converter": {"name": "litert_torch",
                      "version": str(getattr(litert_torch, "__version__", "unknown")),
                      "pytorch_version": str(torch.__version__)},
        "verification": {"cases": len(cases), "atol": atol, "rtol": rtol,
                         "max_abs_error": max_abs_error},
        "training_contract": training_contract,
    }
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Serialize only after parity passes. Use a temporary sibling so failed
    # serialization cannot replace an existing valid artifact with partial data.
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent, prefix=destination.stem + ".", suffix=".tflite"
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        edge_model.export(str(temporary))
        with temporary.open("rb") as exported:
            if exported.read(8)[4:8] != b"TFL3":
                raise RuntimeError("Converter did not write a TFLite FlatBuffer")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    destination.with_suffix(".metadata.json").write_text(manifest_text, encoding="utf-8")
    return destination
