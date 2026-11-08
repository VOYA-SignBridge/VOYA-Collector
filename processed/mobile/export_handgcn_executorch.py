"""Export a trusted HD-GCN checkpoint to an ExecuTorch FP32 PTE artifact."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_tensor(value: object) -> torch.Tensor:
    if isinstance(value, torch.Tensor):
        return value
    if hasattr(value, "to_tensor"):
        return value.to_tensor()  # type: ignore[no-any-return]
    return torch.as_tensor(value)


def _mobile_labels(checkpoint: dict[object, object], num_classes: int) -> dict[str, str]:
    """Flatten the checkpoint's rich labels for simple Kotlin JSON parsing."""
    raw_labels = checkpoint.get("idx_to_label")
    if not isinstance(raw_labels, dict):
        raise SystemExit("Checkpoint is missing idx_to_label")

    labels: dict[str, str] = {}
    for index in range(num_classes):
        raw = raw_labels.get(index, raw_labels.get(str(index)))
        if isinstance(raw, dict):
            label = raw.get("label_original") or raw.get("label_slug") or raw.get("label_key")
        else:
            label = raw
        if not isinstance(label, str) or not label.strip():
            raise SystemExit(f"Checkpoint label {index} is missing or invalid")
        labels[str(index)] = label.strip()
    return labels


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a HandGCN checkpoint to ExecuTorch PTE.")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument(
        "--source-root",
        type=Path,
        help=(
            "Optional legacy HandGCN repository containing processed/train_utils/models. "
            "If omitted, use the HD-GCN architecture bundled with this exporter."
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-samples", type=int, default=16)
    args = parser.parse_args()

    checkpoint_path = args.checkpoint.resolve()
    if not checkpoint_path.is_file():
        raise SystemExit(f"Checkpoint not found: {checkpoint_path}")
    source_root = args.source_root.resolve() if args.source_root else None
    if source_root is not None:
        if not (source_root / "processed" / "train_utils" / "models" / "hd_gcn.py").is_file():
            raise SystemExit(f"HandGCN source not found under: {source_root}")
        sys.path.insert(0, str(source_root))
    scripts_dir = str(Path(sys.executable).resolve().parent)
    os.environ["PATH"] = scripts_dir + os.pathsep + os.environ.get("PATH", "")

    # Safe mode accepts tensors and primitive checkpoint metadata only.
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict) or str(checkpoint.get("model_type", "")).lower() not in {"handgcn", "hd-gcn", "hdgcn"}:
        raise SystemExit("Checkpoint is not a HandGCN checkpoint")
    if source_root is None:
        from processed.mobile.models.hd_gcn import HandGCNModel
    else:
        from processed.train_utils.models.hd_gcn import HandGCNModel

    feature_dim = int(checkpoint["feature_dim"])
    seq_len = int(checkpoint["seq_len"])
    num_classes = int(checkpoint["num_classes"])
    model = HandGCNModel.from_config(feature_dim, num_classes, checkpoint.get("model_config") or {}).eval()
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    sample = torch.randn(1, seq_len, feature_dim, dtype=torch.float32)
    with torch.inference_mode():
        expected = model(sample).cpu()

    from executorch.backends.xnnpack.partition.xnnpack_partitioner import XnnpackPartitioner
    from executorch.exir import to_edge_transform_and_lower
    from executorch.runtime import Runtime

    exported = torch.export.export(model, (sample,), strict=True)
    edge_program = to_edge_transform_and_lower(exported, partitioner=[XnnpackPartitioner()]).to_executorch()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(edge_program.buffer)
    method = Runtime.get().load_program(str(output)).load_method("forward")

    max_diff = 0.0
    mean_diff = 0.0
    same_top1 = 0
    count = max(1, int(args.verify_samples))
    with torch.inference_mode():
        for index in range(count):
            x = sample if index == 0 else torch.randn(1, seq_len, feature_dim, dtype=torch.float32)
            reference = model(x).cpu()
            actual = _as_tensor(method.execute([x])[0]).detach().cpu()
            diff = (reference - actual).abs()
            max_diff = max(max_diff, float(diff.max().item()))
            mean_diff += float(diff.mean().item())
            same_top1 += int(reference.argmax(1).item() == actual.argmax(1).item())
    verification = {"samples": count, "top1_agreement": same_top1 / count, "max_abs_diff": max_diff, "mean_abs_diff": mean_diff / count}
    if verification["top1_agreement"] < 1.0:
        raise RuntimeError(f"PTE parity failure: {verification}")

    labels = _mobile_labels(checkpoint, num_classes)
    labels_path = output.with_name(f"{output.stem}_labels.json")
    metadata_path = output.with_name(f"{output.stem}_metadata.json")
    metadata = {
        "format": "executorch_pte", "format_version": 1,
        "precision": "float32", "backend": "xnnpack", "model_type": "HandGCN",
        "method_name": "forward", "feature_dim": feature_dim, "seq_len": seq_len,
        "input": {"name": "landmarks", "shape": [1, seq_len, feature_dim]},
        "output": {"name": "logits", "shape": [1, num_classes]}, "num_classes": num_classes,
        "labels_file": labels_path.name,
        "idx_to_label": checkpoint.get("idx_to_label"), "label_to_idx": checkpoint.get("label_to_idx"),
        "checkpoint": str(checkpoint_path), "checkpoint_sha256": _sha256(checkpoint_path), "pte_sha256": _sha256(output),
        "model_config": checkpoint.get("model_config"), "preprocess_contract": checkpoint.get("preprocess_contract"),
        "normalization_version": checkpoint.get("normalization_version"), "verification": verification,
        "architecture_source": "bundled" if source_root is None else str(source_root),
        "versions": {"torch": torch.__version__, "executorch": importlib.metadata.version("executorch"), "numpy": np.__version__},
    }
    labels_path.write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported: {output}")
    print(f"Labels:   {labels_path}")
    print(f"Metadata: {metadata_path}")
    print(f"Parity: top1={verification['top1_agreement']:.2%}, max_abs_diff={max_diff:.8g}")


if __name__ == "__main__":
    main()
