#!/usr/bin/env python3
"""Non-neural reference baselines for the signer-independent (LOSO) protocol.

Regenerates ``reports/baselines.json``: majority-class, nearest-centroid and
1-NN classifiers on raw flattened 60x126 landmark sequences, with one held-out
signer per fold. These establish that the task is non-trivial but partially
separable without learning, and bound the reported neural results from below.

Requires the participant landmark files, which are private and NOT part of this
artifact: only the resulting ``baselines.json`` is released. Authorized data
holders can regenerate it with:

    python scripts/compute_baselines.py \
        --splits processed/splits/versions/hoa_de_loso_v5 \
        --features-root /path/to/dataset/features \
        --out reports/baselines.json

Deterministic: no sampling, no shuffling, ties broken by sorted label order.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

EXPECTED_SHAPE = (60, 126)

# Mirrors SignFeatureDataset.feature_key_priority so both read the same array.
FEATURE_KEY_PRIORITY = ("sequence", "features", "x", "data", "arr_0")


def _array_from_npz(npz) -> np.ndarray:
    for key in FEATURE_KEY_PRIORITY:
        if key in npz:
            return npz[key]
    for key in npz.keys():
        return npz[key]
    raise KeyError("no array found in npz archive")


def _resolve(file_path: str, features_root: Path) -> Path:
    """Map a manifest ``file_path`` onto the local feature tree.

    Manifest paths are recorded as ``/dataset/features/vn/<group>/<class>/<file>``
    (container-absolute). Strip that prefix and re-root it, falling back to the
    literal path so an already-correct absolute path still works.
    """
    raw = file_path.strip().replace("\\", "/")
    literal = Path(raw)
    if literal.is_file():
        return literal

    marker = "dataset/features/"
    idx = raw.find(marker)
    if idx != -1:
        candidate = features_root / raw[idx + len(marker):]
        if candidate.is_file():
            return candidate

    candidate = features_root / raw.lstrip("/")
    if candidate.is_file():
        return candidate

    raise FileNotFoundError(f"feature file not found for {file_path!r} under {features_root}")


def _label_of(row: Dict[str, str]) -> str:
    for column in ("label_key", "label_slug", "slug", "class_idx"):
        value = (row.get(column) or "").strip()
        if value:
            return value
    raise KeyError(f"no usable label column in row: {sorted(row)}")


def load_split(csv_path: Path, features_root: Path) -> Tuple[np.ndarray, List[str], List[str]]:
    """Return (X flattened, labels, sample_ids) for one split CSV."""
    features: List[np.ndarray] = []
    labels: List[str] = []
    sample_ids: List[str] = []

    with csv_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            path = _resolve(row["file_path"], features_root)
            with np.load(path, allow_pickle=False) as data:
                arr = np.asarray(_array_from_npz(data), dtype=np.float32)
            if arr.shape != EXPECTED_SHAPE:
                raise ValueError(f"{path}: expected {EXPECTED_SHAPE}, got {arr.shape}")
            features.append(arr.reshape(-1))
            labels.append(_label_of(row))
            sample_ids.append((row.get("sample_id") or "").strip())

    if not features:
        raise ValueError(f"{csv_path} is empty")
    return np.stack(features), labels, sample_ids


def majority_accuracy(train_labels: List[str], test_labels: List[str]) -> float:
    counts = Counter(train_labels)
    top = max(counts.values())
    # Sorted tie-break keeps the result reproducible across runs and platforms.
    predicted = sorted(label for label, count in counts.items() if count == top)[0]
    return float(np.mean([label == predicted for label in test_labels]))


def nearest_centroid_accuracy(
    x_train: np.ndarray, train_labels: List[str],
    x_test: np.ndarray, test_labels: List[str],
) -> float:
    classes = sorted(set(train_labels))
    train_arr = np.asarray(train_labels)
    centroids = np.stack([x_train[train_arr == label].mean(axis=0) for label in classes])
    distances = _squared_distances(x_test, centroids)
    predicted = [classes[i] for i in distances.argmin(axis=1)]
    return float(np.mean([p == t for p, t in zip(predicted, test_labels)]))


def one_nn_accuracy(
    x_train: np.ndarray, train_labels: List[str],
    x_test: np.ndarray, test_labels: List[str],
) -> float:
    distances = _squared_distances(x_test, x_train)
    predicted = [train_labels[i] for i in distances.argmin(axis=1)]
    return float(np.mean([p == t for p, t in zip(predicted, test_labels)]))


def _squared_distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise squared Euclidean distances, chunked to bound peak memory."""
    out = np.empty((a.shape[0], b.shape[0]), dtype=np.float64)
    b64 = b.astype(np.float64)
    b_sq = (b64 ** 2).sum(axis=1)
    for start in range(0, a.shape[0], 256):
        chunk = a[start:start + 256].astype(np.float64)
        out[start:start + 256] = (
            (chunk ** 2).sum(axis=1)[:, None] - 2.0 * chunk @ b64.T + b_sq[None, :]
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--splits", type=Path, required=True,
                        help="LOSO split version directory containing test_S*/ folds")
    parser.add_argument("--features-root", type=Path, required=True,
                        help="Root of the private feature tree (…/dataset/features)")
    parser.add_argument("--out", type=Path, required=True, help="Destination JSON")
    parser.add_argument("--task", default="hoa_de", help="Task name recorded in the output")
    parser.add_argument("--train-only", action="store_true",
                        help="Fit on train alone; the default (train+val) matches the released baselines.json")
    parser.add_argument("--source", default="dataset/features/vn/hoa-de",
                        help="Feature source recorded in the output note")
    args = parser.parse_args()

    fold_dirs = sorted(p for p in args.splits.glob("test_*") if p.is_dir())
    if not fold_dirs:
        raise SystemExit(f"no test_*/ fold directories under {args.splits}")

    per_fold: Dict[str, Dict[str, float]] = {}
    all_labels: set = set()
    all_samples: set = set()

    for fold_dir in fold_dirs:
        fold = fold_dir.name.replace("test_", "", 1)

        x_train, train_labels, train_ids = load_split(fold_dir / "train.csv", args.features_root)
        x_test, test_labels, test_ids = load_split(fold_dir / "test.csv", args.features_root)
        x_val, val_labels, val_ids = load_split(fold_dir / "val.csv", args.features_root)

        all_labels.update(train_labels, val_labels, test_labels)
        all_samples.update(train_ids, val_ids, test_ids)

        if not args.train_only:
            x_train = np.concatenate([x_train, x_val])
            train_labels = train_labels + val_labels

        per_fold[fold] = {
            "majority": majority_accuracy(train_labels, test_labels),
            "nearest_centroid": nearest_centroid_accuracy(x_train, train_labels, x_test, test_labels),
            "one_nn_raw": one_nn_accuracy(x_train, train_labels, x_test, test_labels),
        }
        print(f"[{fold}] " + "  ".join(f"{k}={v:.4f}" for k, v in per_fold[fold].items()))

    metrics = ("majority", "nearest_centroid", "one_nn_raw")
    mean_across_folds = {
        metric: float(np.mean([per_fold[f][metric] for f in per_fold])) for metric in metrics
    }

    fitted_on = "train" if args.train_only else "train+val"
    result = {
        "task": args.task,
        "protocol": f"LOSO_{len(fold_dirs)}fold_signer_independent",
        "n_samples": len(all_samples),
        "n_classes": len(all_labels),
        "n_signers": len(fold_dirs),
        "random_chance": 1.0 / len(all_labels),
        "per_fold": per_fold,
        "mean_across_folds": mean_across_folds,
        "note": (
            f"1-NN/nearest-centroid/majority on raw flattened 60x126 features "
            f"(fitted on {fitted_on}); test = held-out signer. "
            f"Source features: {args.source}."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {args.out}")
    print("  " + "  ".join(f"{k}={v:.4f}" for k, v in mean_across_folds.items()))


if __name__ == "__main__":
    main()
