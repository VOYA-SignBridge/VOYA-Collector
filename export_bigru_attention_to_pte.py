#!/usr/bin/env python3
"""Export a trained BiGRU + Attention checkpoint (.pt) to ExecuTorch (.pte).

Run without arguments to choose a checkpoint in a Windows file dialog:

    python export_bigru_attention_to_pte.py

Or use it from a terminal/CI:

    python export_bigru_attention_to_pte.py --input processed/train_utils/outputs/model.pt

The source .pt is NEVER deleted or renamed.  A .pte plus a small
``.pte.metadata.json`` sidecar are written next to it (or to --output).  The
sidecar is needed by a phone app to preserve the label ordering and the input
pre-processing contract; a .pte contains executable inference code, not the
whole training checkpoint.

Requirements (use one compatible virtual environment):

    pip install torch executorch

The generated program has the same inference contract as the checkpoint:
float32 [batch_size, seq_len, feature_dim] -> float32 [batch_size, num_classes].
The default is batch_size=1 and the checkpoint's seq_len (normally 60), which
is the usual on-device inference contract.  The script numerically compares
eager PyTorch output with the exported program before it retains the .pte.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "processed" / "train_utils" / "outputs"
DEFAULT_ATOL = 2e-4
DEFAULT_RTOL = 2e-4


def _import_bigru_model():
    """Import the exact architecture used by training, regardless of cwd."""
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from processed.train_utils.models.bigru_attention import BiGRUAttentionModel

    return BiGRUAttentionModel


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


def _require_bigru_attention_checkpoint(checkpoint: Dict[str, Any]) -> None:
    """Identify BiGRU from its weights, not only checkpoint['model_type'].

    Older train_tcn.py versions wrote ``model_type='TCN'`` for every model.
    The parameter names are the reliable architecture identity.
    """
    keys = set(checkpoint["model_state_dict"])
    required = {
        "gru.weight_ih_l0",
        "gru.weight_hh_l0",
        "gru.weight_ih_l0_reverse",
        "attention.query.weight",
        "attention.key.weight",
        "attention.value.weight",
        "classifier.0.weight",
        "classifier.3.weight",
    }
    missing = sorted(required - keys)
    if missing:
        raise ValueError(
            "This is not a compatible BiGRU + Attention checkpoint. "
            f"Missing parameter(s): {', '.join(missing)}"
        )


def _infer_bigru_config(checkpoint: Dict[str, Any]) -> Tuple[int, int, Dict[str, Any]]:
    """Return input_dim, output_dim and a safe BiGRU config.

    Dimensions are inferred from weights as a guard against stale checkpoint
    metadata.  Hyperparameters are read from model_config when present.
    """
    state = checkpoint["model_state_dict"]
    first_weight = state["gru.weight_ih_l0"]
    hidden_size = int(first_weight.shape[0] // 3)
    input_dim = int(first_weight.shape[1])
    output_dim = int(state["classifier.3.weight"].shape[0])

    layers = []
    for key in state:
        if key.startswith("gru.weight_ih_l") and not key.endswith("_reverse"):
            suffix = key.removeprefix("gru.weight_ih_l")
            if suffix.isdigit():
                layers.append(int(suffix))
    num_layers = max(layers) + 1 if layers else 1

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
        "hidden_size": hidden_size,
        "num_layers": num_layers,
        # Dropout has no effect after model.eval(); retain it for faithful construction.
        "dropout": float(saved_config.get("dropout", 0.3)),
    }
    return input_dim, output_dim, config


def _build_eager_model(checkpoint: Dict[str, Any]) -> nn.Module:
    _require_bigru_attention_checkpoint(checkpoint)
    input_dim, output_dim, config = _infer_bigru_config(checkpoint)
    model_class = _import_bigru_model()
    model = model_class.from_config(input_dim, output_dim, config)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    return model.eval()


class ExportableBiGRUAttention(nn.Module):
    """BiGRU inference expressed with elementary operations for ExecuTorch.

    ``nn.GRU`` may export as the fused ``aten.gru`` operator, which some mobile
    ExecuTorch builds do not ship.  This module calculates the identical GRU
    equations using linear/sigmoid/tanh operations, so it is a portable fallback.
    It is used only if direct export cannot be executed by the local runtime.
    """

    def __init__(self, trained_model: nn.Module):
        super().__init__()
        self.trained_model = trained_model
        self.hidden_size = int(trained_model.hidden_size)
        self.num_layers = int(trained_model.num_layers)

    @staticmethod
    def _gru_step(
        x: torch.Tensor,
        hidden: torch.Tensor,
        weight_ih: torch.Tensor,
        weight_hh: torch.Tensor,
        bias_ih: torch.Tensor,
        bias_hh: torch.Tensor,
    ) -> torch.Tensor:
        # PyTorch GRU gate order is reset, update, new (r, z, n).
        gi = F.linear(x, weight_ih, bias_ih)
        gh = F.linear(hidden, weight_hh, bias_hh)
        i_r, i_z, i_n = gi.chunk(3, dim=1)
        h_r, h_z, h_n = gh.chunk(3, dim=1)
        reset = torch.sigmoid(i_r + h_r)
        update = torch.sigmoid(i_z + h_z)
        new = torch.tanh(i_n + reset * h_n)
        return (1.0 - update) * new + update * hidden

    def _run_direction(self, sequence: torch.Tensor, layer: int, reverse: bool) -> torch.Tensor:
        suffix = f"_l{layer}" + ("_reverse" if reverse else "")
        gru = self.trained_model.gru
        weight_ih = getattr(gru, "weight_ih" + suffix)
        weight_hh = getattr(gru, "weight_hh" + suffix)
        bias_ih = getattr(gru, "bias_ih" + suffix)
        bias_hh = getattr(gru, "bias_hh" + suffix)
        batch = sequence.shape[0]
        steps = sequence.shape[1]
        hidden = torch.zeros((batch, self.hidden_size), dtype=sequence.dtype, device=sequence.device)
        outputs = []
        indices: Iterable[int] = range(steps - 1, -1, -1) if reverse else range(steps)
        for index in indices:
            hidden = self._gru_step(sequence[:, index, :], hidden, weight_ih, weight_hh, bias_ih, bias_hh)
            outputs.append(hidden)
        if reverse:
            outputs.reverse()
        return torch.stack(outputs, dim=1)

    def forward(self, x_btd: torch.Tensor) -> torch.Tensor:
        sequence = x_btd
        for layer in range(self.num_layers):
            forward = self._run_direction(sequence, layer, reverse=False)
            backward = self._run_direction(sequence, layer, reverse=True)
            sequence = torch.cat((forward, backward), dim=2)

        attention = self.trained_model.attention
        query = attention.query(sequence)
        key = attention.key(sequence)
        value = attention.value(sequence)
        scores = torch.matmul(query, key.transpose(-2, -1)) / attention.scale
        context = torch.matmul(torch.softmax(scores, dim=-1), value)
        return self.trained_model.classifier(context.mean(dim=1))


def _assert_close(name: str, actual: torch.Tensor, expected: torch.Tensor, atol: float, rtol: float) -> None:
    actual = actual.detach().cpu()
    expected = expected.detach().cpu()
    if actual.shape != expected.shape:
        raise RuntimeError(f"{name}: output shape differs: {tuple(actual.shape)} != {tuple(expected.shape)}")
    if not torch.allclose(actual, expected, atol=atol, rtol=rtol):
        max_error = float((actual - expected).abs().max())
        raise RuntimeError(
            f"{name}: output differs from PyTorch (max abs error {max_error:.6g}; "
            f"allowed atol={atol}, rtol={rtol})."
        )


def _export_to_temp(model: nn.Module, example_input: torch.Tensor, destination: Path) -> None:
    """Export to a temporary filename so a failed verification leaves no .pte."""
    try:
        from executorch.exir import to_edge
    except ImportError as exc:
        raise RuntimeError(
            "ExecuTorch is not installed. Install it in the active environment: pip install executorch"
        ) from exc

    with torch.no_grad():
        exported = torch.export.export(model.eval(), (example_input,), strict=True)
        program = to_edge(exported).to_executorch()
    # save() is the current public API; buffer supports older ExecuTorch releases.
    try:
        program.save(str(destination))
    except AttributeError:
        destination.write_bytes(program.buffer)


def _run_pte(pte_path: Path, example_input: torch.Tensor) -> torch.Tensor:
    try:
        from executorch.runtime import Runtime
    except ImportError as exc:
        raise RuntimeError("ExecuTorch Python runtime is unavailable; cannot verify the .pte.") from exc

    runtime = Runtime.get()
    method = runtime.load_program(str(pte_path)).load_method("forward")
    result = method.execute([example_input])[0]
    if not isinstance(result, torch.Tensor):
        # Recent runtimes return torch.Tensor; fail loudly rather than silently
        # accepting an unknown output representation.
        raise RuntimeError(f"ExecuTorch runtime returned {type(result).__name__}, not torch.Tensor.")
    return result


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


def _write_metadata(
    checkpoint: Dict[str, Any],
    source_checkpoint: Path,
    pte_path: Path,
    input_shape: Tuple[int, int, int],
) -> Path:
    input_dim, output_dim, config = _infer_bigru_config(checkpoint)
    payload = {
        "format": "voya-executorch-bigru-attention-v1",
        "model_type": "BiGRU + Attention",
        "input": {"dtype": "float32", "shape": list(input_shape), "layout": "[batch, time, features]"},
        "output": {"dtype": "float32", "shape": [input_shape[0], output_dim], "meaning": "class logits"},
        "feature_dim": input_dim,
        "seq_len": input_shape[1],
        "num_classes": output_dim,
        "model_config": config,
        "label_to_idx": checkpoint.get("label_to_idx"),
        "idx_to_label": checkpoint.get("idx_to_label"),
        "normalization_version": checkpoint.get("normalization_version"),
        "feature_version": checkpoint.get("feature_version"),
        "preprocess_contract": checkpoint.get("preprocess_contract"),
        "source_checkpoint": source_checkpoint.name,
    }
    metadata_path = pte_path.with_suffix(".pte.metadata.json")
    metadata_path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata_path


def export_checkpoint(
    input_path: Path,
    output_path: Path,
    batch_size: int,
    seq_len_override: int | None,
    atol: float,
    rtol: float,
) -> Tuple[Path, Path, str]:
    checkpoint = _load_checkpoint(input_path)
    model = _build_eager_model(checkpoint)
    input_dim, _, _ = _infer_bigru_config(checkpoint)
    seq_len = seq_len_override or int(checkpoint.get("seq_len") or 60)
    if batch_size < 1 or seq_len < 1:
        raise ValueError("batch_size and seq_len must both be positive.")

    # Fixed seed makes failures reproducible while still exercising all operations.
    torch.manual_seed(20260914)
    example_input = torch.randn(batch_size, seq_len, input_dim, dtype=torch.float32)
    with torch.no_grad():
        eager_output = model(example_input)

    # Validate the portable fallback itself before trying to compile it.
    fallback = ExportableBiGRUAttention(model).eval()
    with torch.no_grad():
        _assert_close("BiGRU portable wrapper", fallback(example_input), eager_output, atol, rtol)

    output_path = output_path.with_suffix(".pte")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    with tempfile.TemporaryDirectory(prefix="voya_pte_") as temp_dir:
        temporary_pte = Path(temp_dir) / output_path.name
        # Prefer the compact native GRU graph. If that cannot run under the
        # ExecuTorch runtime, retry with the mathematically equivalent wrapper.
        for label, candidate in (("native-gru", model), ("portable-gru-wrapper", fallback)):
            try:
                _export_to_temp(candidate, example_input, temporary_pte)
                pte_output = _run_pte(temporary_pte, example_input)
                _assert_close(f"{label} .pte", pte_output, eager_output, atol, rtol)
                output_path.write_bytes(temporary_pte.read_bytes())
                metadata_path = _write_metadata(
                    checkpoint, input_path, output_path, tuple(example_input.shape)
                )
                return output_path, metadata_path, label
            except Exception as exc:
                errors.append(f"{label}: {exc}")
                temporary_pte.unlink(missing_ok=True)

    raise RuntimeError("Could not create a verified .pte:\n  " + "\n  ".join(errors))


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
        title="Chọn checkpoint BiGRU + Attention (.pt)",
        initialdir=str(initial_dir),
        filetypes=[("PyTorch checkpoint", "*.pt"), ("All files", "*.*")],
    )
    root.destroy()
    return Path(selected) if selected else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a trained BiGRU + Attention .pt checkpoint to a verified .pte.")
    parser.add_argument("--input", type=Path, help="Path to the trained .pt checkpoint. Omit to use a file picker.")
    parser.add_argument("--output", type=Path, help="Destination .pte path. Default: same folder/name as --input.")
    parser.add_argument("--batch-size", type=int, default=1, help="Fixed exported batch size (default: 1).")
    parser.add_argument("--seq-len", type=int, help="Override checkpoint seq_len; only use if the mobile app sends this length.")
    parser.add_argument("--atol", type=float, default=DEFAULT_ATOL, help=f"Output absolute tolerance (default: {DEFAULT_ATOL}).")
    parser.add_argument("--rtol", type=float, default=DEFAULT_RTOL, help=f"Output relative tolerance (default: {DEFAULT_RTOL}).")
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
    pte_path, metadata_path, mode = export_checkpoint(
        input_path, output_path, args.batch_size, args.seq_len, args.atol, args.rtol
    )
    print(f"Success ({mode}):\n  PTE: {pte_path}\n  Metadata: {metadata_path}\n  Source .pt kept: {input_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"EXPORT FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
