#!/usr/bin/env python3
"""Export a trained VOYA HandGCN checkpoint (.pt) to ExecuTorch (.pte).

Run without arguments to choose a checkpoint in a Windows file dialog:

    python export_handgcn_to_pte.py

Or provide the checkpoint explicitly:

    python export_handgcn_to_pte.py --input processed/train_utils/outputs/model.pt

The source checkpoint is never modified. A verified ``.pte`` program and an
ordered ``.pte.metadata.json`` sidecar are written beside it (or to --output).

Inference contract:
    float32 [batch, time, features] -> float32 [batch, classes] logits

The default export preserves the checkpoint sequence length (normally 60),
uses batch size 1, keeps FP32 weights, and applies no quantization. In ``auto``
mode the exporter first tries the XNNPACK mobile CPU backend, then falls back
to ExecuTorch portable kernels. A candidate is retained only after its outputs
match eager PyTorch on several finite inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import torch
import torch.nn as nn


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "processed" / "train_utils" / "outputs"
DEFAULT_ATOL = 2e-4
DEFAULT_RTOL = 2e-4


def _import_handgcn_model():
    """Import the exact architecture used during training, regardless of cwd."""
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from processed.train_utils.models.hd_gcn import HandGCNModel

    return HandGCNModel


def _load_checkpoint(path: Path) -> Dict[str, Any]:
    try:
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:  # PyTorch before the weights_only argument existed.
        checkpoint = torch.load(path, map_location="cpu")

    if not isinstance(checkpoint, dict):
        raise ValueError(".pt must be a training checkpoint dictionary, not a serialized module.")
    if not isinstance(checkpoint.get("model_state_dict"), dict):
        raise ValueError("checkpoint has no 'model_state_dict'.")
    return checkpoint


def _require_handgcn_checkpoint(checkpoint: Dict[str, Any]) -> None:
    """Identify HandGCN from its weights instead of trusting model_type alone."""
    keys = set(checkpoint["model_state_dict"])
    required = {
        "fine_adj_d0",
        "part_adj_d0",
        "hierarchical_pooling_matrix",
        "input_projection.weight",
        "fine_gcns.0.linear_layers.0.weight",
        "fine_gcns.0.bn.running_mean",
        "part_gcns.0.linear_layers.0.weight",
        "temporal_conv1.weight",
        "temporal_conv2.weight",
        "attention.0.weight",
        "attention.2.weight",
        "classifier.0.weight",
        "classifier.3.weight",
    }
    missing = sorted(required - keys)
    if missing:
        raise ValueError(
            "This is not a compatible HandGCN checkpoint. "
            f"Missing parameter(s): {', '.join(missing)}"
        )


def _numbered_indices(keys: Iterable[str], prefix: str, suffix: str) -> List[int]:
    indices: List[int] = []
    for key in keys:
        if not key.startswith(prefix) or not key.endswith(suffix):
            continue
        end = len(key) - len(suffix) if suffix else len(key)
        middle = key[len(prefix) : end]
        if middle.isdigit():
            indices.append(int(middle))
    return sorted(set(indices))


def _infer_handgcn_config(checkpoint: Dict[str, Any]) -> Tuple[int, int, Dict[str, Any]]:
    """Infer shape-defining HandGCN settings from weights and validate metadata."""
    _require_handgcn_checkpoint(checkpoint)
    state = checkpoint["model_state_dict"]
    keys = set(state)

    num_nodes = int(state["fine_adj_d0"].shape[0])
    pooling_nodes = int(state["hierarchical_pooling_matrix"].shape[1])
    if pooling_nodes != num_nodes:
        raise ValueError(
            f"hierarchical pooling expects {pooling_nodes} nodes but fine adjacency has {num_nodes}."
        )

    node_features = int(state["input_projection.weight"].shape[1])
    input_dim = num_nodes * node_features
    gcn_channels = int(state["input_projection.weight"].shape[0])
    temporal_channels = int(state["temporal_conv2.weight"].shape[0])
    output_dim = int(state["classifier.3.weight"].shape[0])

    fine_layers = _numbered_indices(keys, "fine_gcns.", ".linear_layers.0.weight")
    if fine_layers != list(range(len(fine_layers))) or not fine_layers:
        raise ValueError(f"non-contiguous HandGCN fine layers: {fine_layers}")
    num_gcn_layers = len(fine_layers)

    distances = _numbered_indices(keys, "fine_adj_d", "")
    if distances != list(range(len(distances))) or not distances:
        raise ValueError(f"non-contiguous HandGCN distance adjacencies: {distances}")
    max_distance = len(distances) - 1

    declared_input = checkpoint.get("feature_dim")
    declared_output = checkpoint.get("num_classes")
    if declared_input is not None and int(declared_input) != input_dim:
        raise ValueError(
            f"feature_dim={declared_input} disagrees with checkpoint weights ({input_dim})."
        )
    if declared_output is not None and int(declared_output) != output_dim:
        raise ValueError(
            f"num_classes={declared_output} disagrees with checkpoint weights ({output_dim})."
        )

    saved_config = checkpoint.get("model_config")
    saved_config = saved_config if isinstance(saved_config, dict) else {}
    config = {
        "num_nodes": num_nodes,
        "gcn_channels": gcn_channels,
        "num_gcn_layers": num_gcn_layers,
        "temporal_channels": temporal_channels,
        # Dropout is disabled by eval(), but retain the training value faithfully.
        "dropout": float(saved_config.get("dropout", 0.3)),
        "max_distance": max_distance,
    }
    return input_dim, output_dim, config


def _build_eager_model(checkpoint: Dict[str, Any]) -> nn.Module:
    input_dim, output_dim, config = _infer_handgcn_config(checkpoint)
    model_class = _import_handgcn_model()
    model = model_class.from_config(input_dim, output_dim, config)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    return model.eval()


def _assert_close(
    name: str,
    actual: torch.Tensor,
    expected: torch.Tensor,
    atol: float,
    rtol: float,
) -> None:
    actual = actual.detach().cpu()
    expected = expected.detach().cpu()
    if actual.shape != expected.shape:
        raise RuntimeError(
            f"{name}: output shape differs: {tuple(actual.shape)} != {tuple(expected.shape)}"
        )
    if not torch.isfinite(actual).all():
        raise RuntimeError(f"{name}: output contains NaN or Inf.")
    if not torch.allclose(actual, expected, atol=atol, rtol=rtol):
        max_error = float((actual - expected).abs().max())
        raise RuntimeError(
            f"{name}: output differs from PyTorch (max abs error {max_error:.6g}; "
            f"allowed atol={atol}, rtol={rtol})."
        )


def _compile_to_temp(
    model: nn.Module,
    example_input: torch.Tensor,
    destination: Path,
    backend: str,
) -> None:
    """Compile a fixed-shape FP32 program for one ExecuTorch backend."""
    try:
        from executorch.exir import to_edge, to_edge_transform_and_lower
    except ImportError as exc:
        raise RuntimeError(
            "ExecuTorch is not installed. Install it in the active environment: pip install executorch"
        ) from exc

    with torch.no_grad():
        exported = torch.export.export(model.eval(), (example_input,), strict=True)
        if backend == "xnnpack":
            try:
                from executorch.backends.xnnpack.partition.xnnpack_partitioner import (
                    XnnpackPartitioner,
                )
            except ImportError as exc:
                raise RuntimeError("The installed ExecuTorch package has no XNNPACK partitioner.") from exc
            edge = to_edge_transform_and_lower(
                exported,
                partitioner=[XnnpackPartitioner()],
            )
        elif backend == "portable":
            edge = to_edge(exported)
        else:
            raise ValueError(f"unsupported backend: {backend}")
        program = edge.to_executorch()

    try:
        program.save(str(destination))
    except AttributeError:
        destination.write_bytes(program.buffer)


def _run_pte(pte_path: Path, inputs: Sequence[torch.Tensor]) -> List[torch.Tensor]:
    try:
        from executorch.runtime import Runtime
    except ImportError as exc:
        raise RuntimeError("ExecuTorch Python runtime is unavailable; cannot verify the .pte.") from exc

    runtime = Runtime.get()
    program = runtime.load_program(str(pte_path))
    method = program.load_method("forward")
    outputs: List[torch.Tensor] = []
    for value in inputs:
        result = method.execute([value])[0]
        if not isinstance(result, torch.Tensor):
            raise RuntimeError(
                f"ExecuTorch runtime returned {type(result).__name__}, not torch.Tensor."
            )
        outputs.append(result)
    return outputs


def _verification_inputs(shape: Tuple[int, int, int]) -> List[torch.Tensor]:
    """Use deterministic finite inputs, including realistic small magnitudes."""
    generator = torch.Generator(device="cpu")
    generator.manual_seed(20260914)
    return [
        torch.randn(shape, generator=generator, dtype=torch.float32),
        torch.zeros(shape, dtype=torch.float32),
        torch.randn(shape, generator=generator, dtype=torch.float32) * 0.25,
    ]


def _ordered_labels(raw: Any, output_dim: int) -> List[Any]:
    """Emit an array so JSON object key ordering cannot corrupt class decoding."""
    if isinstance(raw, list):
        labels = list(raw)
    elif isinstance(raw, dict):
        try:
            by_index = {int(key): value for key, value in raw.items()}
        except (TypeError, ValueError) as exc:
            raise ValueError("idx_to_label keys must be integer class indices.") from exc
        expected = set(range(output_dim))
        if set(by_index) != expected:
            raise ValueError(
                "idx_to_label indices must be contiguous from 0 to "
                f"{output_dim - 1}; got {sorted(by_index)}"
            )
        labels = [by_index[index] for index in range(output_dim)]
    else:
        raise ValueError("checkpoint idx_to_label must be a list or dict.")

    if len(labels) != output_dim:
        raise ValueError(f"idx_to_label has {len(labels)} entries; expected {output_dim}.")
    return labels


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _metadata_payload(
    checkpoint: Dict[str, Any],
    source_checkpoint: Path,
    pte_path: Path,
    input_shape: Tuple[int, int, int],
    backend: str,
) -> Dict[str, Any]:
    input_dim, output_dim, config = _infer_handgcn_config(checkpoint)
    checkpoint_seq_len = int(checkpoint.get("seq_len") or input_shape[1])
    contract = checkpoint.get("preprocess_contract")
    contract = dict(contract) if isinstance(contract, dict) else {}
    strict_shape = contract.get("expects_strict_shape")
    expected_strict_shape = [checkpoint_seq_len, input_dim]
    if strict_shape is not None and list(strict_shape) != expected_strict_shape:
        raise ValueError(
            f"preprocess_contract expects {strict_shape}, but checkpoint dimensions are {expected_strict_shape}."
        )

    labels = _ordered_labels(checkpoint.get("idx_to_label"), output_dim)
    return {
        "format": "voya-executorch-handgcn-v1",
        "model_type": "HandGCN",
        "backend": backend,
        "input": {
            "dtype": "float32",
            "shape": list(input_shape),
            "layout": "[batch, time, features]",
        },
        "output": {
            "dtype": "float32",
            "shape": [input_shape[0], output_dim],
            "meaning": "class logits",
        },
        "feature_dim": input_dim,
        "seq_len": input_shape[1],
        "num_classes": output_dim,
        "model_config": config,
        "idx_to_label": labels,
        "label_to_idx": checkpoint.get("label_to_idx"),
        "normalization_version": checkpoint.get("normalization_version"),
        "feature_version": checkpoint.get("feature_version"),
        "preprocess_contract": contract,
        "source_checkpoint": source_checkpoint.name,
        "source_checkpoint_sha256": _sha256(source_checkpoint),
        "pte_sha256": _sha256(pte_path),
        "torch_version": torch.__version__,
    }


def _write_verified_outputs(
    temporary_pte: Path,
    output_path: Path,
    payload: Dict[str, Any],
) -> Path:
    """Replace final files only after compilation, execution and metadata succeed."""
    metadata_path = output_path.with_suffix(".pte.metadata.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_bytes = json.dumps(
        _json_safe(payload), ensure_ascii=False, indent=2
    ).encode("utf-8")

    pte_temp = output_path.with_name(output_path.name + ".tmp")
    metadata_temp = metadata_path.with_name(metadata_path.name + ".tmp")
    try:
        pte_temp.write_bytes(temporary_pte.read_bytes())
        metadata_temp.write_bytes(metadata_bytes)
        os.replace(pte_temp, output_path)
        os.replace(metadata_temp, metadata_path)
    finally:
        pte_temp.unlink(missing_ok=True)
        metadata_temp.unlink(missing_ok=True)
    return metadata_path


def export_checkpoint(
    input_path: Path,
    output_path: Path,
    batch_size: int,
    backend_choice: str,
    atol: float,
    rtol: float,
) -> Tuple[Path, Path, str]:
    checkpoint = _load_checkpoint(input_path)
    model = _build_eager_model(checkpoint)
    input_dim, _, _ = _infer_handgcn_config(checkpoint)
    seq_len = int(checkpoint.get("seq_len") or 60)
    if batch_size < 1 or seq_len < 1:
        raise ValueError("batch_size and checkpoint seq_len must both be positive.")

    input_shape = (batch_size, seq_len, input_dim)
    verify_inputs = _verification_inputs(input_shape)
    with torch.no_grad():
        eager_outputs = [model(value) for value in verify_inputs]

    output_path = output_path.with_suffix(".pte")
    candidates = (
        ["xnnpack", "portable"]
        if backend_choice == "auto"
        else [backend_choice]
    )
    errors: List[str] = []
    with tempfile.TemporaryDirectory(prefix="voya_handgcn_pte_") as temp_dir:
        for backend in candidates:
            temporary_pte = Path(temp_dir) / f"handgcn-{backend}.pte"
            try:
                _compile_to_temp(model, verify_inputs[0], temporary_pte, backend)
                pte_outputs = _run_pte(temporary_pte, verify_inputs)
                for index, (actual, expected) in enumerate(zip(pte_outputs, eager_outputs)):
                    _assert_close(
                        f"HandGCN {backend} .pte verification input {index}",
                        actual,
                        expected,
                        atol,
                        rtol,
                    )
                payload = _metadata_payload(
                    checkpoint,
                    input_path,
                    temporary_pte,
                    input_shape,
                    backend,
                )
                metadata_path = _write_verified_outputs(temporary_pte, output_path, payload)
                return output_path, metadata_path, backend
            except Exception as exc:
                errors.append(f"{backend}: {exc}")
                temporary_pte.unlink(missing_ok=True)

    raise RuntimeError("Could not create a verified HandGCN .pte:\n  " + "\n  ".join(errors))


def _choose_input_file() -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise RuntimeError("Tkinter is unavailable. Run again with --input PATH_TO_MODEL.pt") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    initial_dir = DEFAULT_OUTPUT_DIR if DEFAULT_OUTPUT_DIR.exists() else REPO_ROOT
    selected = filedialog.askopenfilename(
        title="Chọn checkpoint HandGCN (.pt)",
        initialdir=str(initial_dir),
        filetypes=[("PyTorch checkpoint", "*.pt"), ("All files", "*.*")],
    )
    root.destroy()
    return Path(selected) if selected else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a trained HandGCN .pt checkpoint to a verified mobile ExecuTorch .pte."
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to the trained .pt checkpoint. Omit to use a file picker.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Destination .pte path. Default: same folder/name as --input.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Fixed exported batch size (default: 1).",
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "xnnpack", "portable"),
        default="auto",
        help="ExecuTorch backend (default: auto tries XNNPACK, then portable).",
    )
    parser.add_argument(
        "--atol",
        type=float,
        default=DEFAULT_ATOL,
        help=f"Output absolute tolerance (default: {DEFAULT_ATOL}).",
    )
    parser.add_argument(
        "--rtol",
        type=float,
        default=DEFAULT_RTOL,
        help=f"Output relative tolerance (default: {DEFAULT_RTOL}).",
    )
    args = parser.parse_args()

    input_path = args.input or _choose_input_file()
    if input_path is None:
        print("No checkpoint selected; nothing was exported.")
        return 0
    input_path = input_path.expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {input_path}")
    if input_path.suffix.lower() != ".pt":
        raise ValueError("Please choose a .pt checkpoint.")

    output_path = (args.output or input_path.with_suffix(".pte")).expanduser().resolve()
    pte_path, metadata_path, backend = export_checkpoint(
        input_path,
        output_path,
        args.batch_size,
        args.backend,
        args.atol,
        args.rtol,
    )
    print(
        f"Success ({backend}):\n"
        f"  PTE: {pte_path}\n"
        f"  Metadata: {metadata_path}\n"
        f"  Source .pt kept: {input_path}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"EXPORT FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
