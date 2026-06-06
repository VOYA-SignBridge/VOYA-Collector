from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import tensorflow as tf
from tensorflow.keras import layers

import torch
from torch.utils.data import DataLoader

try:
    # local metrics (accuracy, SCS, macro-f1) for future use
    from .metrics import sequence_consistency_score  # type: ignore
except Exception:  # pragma: no cover
    try:
        from metrics import sequence_consistency_score
    except ImportError:
        import sys as _sys
        from pathlib import Path as _P
        _sys.path.append(str(_P(__file__).resolve().parents[2]))
        from processed.train_utils.metrics import sequence_consistency_score  # type: ignore

try:
    # When run as module: python -m processed.train_utils.train_tcn
    from .dataset_loader import NPZSignDataset, pad_collate_fn  # type: ignore
except Exception:  # pragma: no cover
    # When run as script: python processed/train_utils/train_tcn.py
    try:
        from dataset_loader import NPZSignDataset, pad_collate_fn
    except ImportError:
        import sys
        from pathlib import Path as _P
        sys.path.append(str(_P(__file__).resolve().parents[2]))
        from processed.train_utils.dataset_loader import NPZSignDataset, pad_collate_fn  # type: ignore


EXPECTED_FEATURE_DIM = 126


import keras

@keras.saving.register_keras_serializable(name="compute_masked_pooling")
def compute_masked_pooling(inputs):
    x_val, lens_val = inputs
    t = tf.shape(x_val)[1]
    mask = tf.sequence_mask(lens_val, maxlen=t, dtype=x_val.dtype)
    mask = tf.expand_dims(mask, axis=-1)
    x_masked = x_val * mask
    denom = tf.cast(tf.maximum(lens_val, 1), x_val.dtype)
    denom = tf.expand_dims(denom, axis=-1)
    return tf.reduce_sum(x_masked, axis=1) / denom

def set_seed(seed: int) -> None:
    os.environ.setdefault("PYTHONHASHSEED", str(seed))
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    tf.random.set_seed(seed)
    try:
        tf.config.experimental.enable_op_determinism()
    except Exception:
        pass


def _seed_worker(worker_id: int) -> None:
    worker_seed = torch.initial_seed() % 2**32
    np.random.seed(worker_seed)
    random.seed(worker_seed)


def build_tcn_model(
    in_dim: int,
    num_classes: int,
    channels: int = 64,
    levels: int = 3,
    kernel_size: int = 5,
    dropout: float = 0.3,
    use_proj: bool = True,
    proj_dim: Optional[int] = None,
) -> tf.keras.Model:
    inputs = tf.keras.Input(shape=(None, in_dim), name="inputs")
    lengths = tf.keras.Input(shape=(), dtype=tf.int32, name="lengths")

    proj_dim = proj_dim or channels
    
    x = inputs
    if use_proj and in_dim != proj_dim:
        x = layers.Conv1D(filters=proj_dim, kernel_size=1, padding='same', name="proj")(x)
        
    current_in = proj_dim if (use_proj and in_dim != proj_dim) else in_dim
    
    for i in range(levels):
        dilation = 2 ** i
        # Conv1
        c1 = layers.Conv1D(
            filters=channels,
            kernel_size=kernel_size,
            padding='causal',
            dilation_rate=dilation,
            kernel_initializer='he_normal',
            name=f"tblock_{i}_conv1"
        )(x)
        r1 = layers.ReLU(name=f"tblock_{i}_relu1")(c1)
        d1 = layers.Dropout(dropout, name=f"tblock_{i}_drop1")(r1)
        
        # Conv2
        c2 = layers.Conv1D(
            filters=channels,
            kernel_size=kernel_size,
            padding='causal',
            dilation_rate=dilation,
            kernel_initializer='he_normal',
            name=f"tblock_{i}_conv2"
        )(d1)
        r2 = layers.ReLU(name=f"tblock_{i}_relu2")(c2)
        d2 = layers.Dropout(dropout, name=f"tblock_{i}_drop2")(r2)
        
        # Downsample
        if current_in != channels:
            res = layers.Conv1D(
                filters=channels,
                kernel_size=1,
                padding='same',
                kernel_initializer='he_normal',
                name=f"tblock_{i}_downsample"
            )(x)
        else:
            res = x
            
        x = layers.Add(name=f"tblock_{i}_add")([d2, res])
        x = layers.ReLU(name=f"tblock_{i}_out_relu")(x)
        current_in = channels
        
    # Masked Global Average Pooling
    pooled = layers.Lambda(compute_masked_pooling, name="masked_pool")([x, lengths])
    
    # Force float32 for mixed precision stability
    logits = layers.Dense(num_classes, name="classifier", dtype=tf.float32)(pooled)
    
    model = tf.keras.Model(inputs=[inputs, lengths], outputs=logits, name="tcn_classifier")
    return model


@dataclass
class TrainConfig:
    train_csv: Path
    val_csv: Path
    test_csv: Path
    batch_size: int = 32
    epochs: int = 80
    lr: float = 1e-3
    weight_decay: float = 1e-4
    dropout: float = 0.3
    channels: int = 64
    levels: int = 3
    kernel_size: int = 5
    seed: int = 42
    device: str = "gpu" if len(tf.config.list_physical_devices('GPU')) > 0 else "cpu"
    num_workers: int = 0
    out_dir: Path = Path(__file__).resolve().parents[1] / "train_utils" / "outputs"
    
    # --- Advanced Training Features ---
    label_smoothing: float = 0.1
    mixed_precision: bool = True
    warmup_ratio: float = 0.1
    temporal_mask_prob: float = 0.15


def macro_f1(logits_np: np.ndarray, targets_np: np.ndarray, num_classes: int) -> float:
    y_pred = logits_np.argmax(axis=1)
    f1s: List[float] = []
    for c in range(num_classes):
        tp = np.sum((y_pred == c) & (targets_np == c))
        fp = np.sum((y_pred == c) & (targets_np != c))
        fn = np.sum((y_pred != c) & (targets_np == c))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        f1s.append(f1)
    return float(sum(f1s) / len(f1s)) if f1s else 0.0


def infer_input_dim(csv_path: Path, *, scan_limit: int = 0) -> int:
    ds = NPZSignDataset(csv_path, to_tensor=True)
    n = len(ds)
    if n == 0:
        raise SystemExit(f"Empty dataset: {csv_path}")
    limit = n if int(scan_limit) <= 0 else min(n, int(scan_limit))
    max_d = 1
    for i in range(limit):
        x, _, _ = ds[i]
        d = int(x.shape[1] if x.ndim >= 2 else 1)
        if d > max_d:
            max_d = d
    return int(max_d)


def infer_input_dim_with_overrides(
    csv_path: Path,
    *,
    features_root: Optional[Path] = None,
    label_to_index_json: Optional[Path] = None,
    scan_limit: int = 0,
) -> int:
    ds = NPZSignDataset(csv_path, root=features_root, label_to_index_json=label_to_index_json, to_tensor=True)
    n = len(ds)
    if n == 0:
        raise SystemExit(f"Empty dataset: {csv_path}")
    limit = n if int(scan_limit) <= 0 else min(n, int(scan_limit))
    max_d = 1
    for i in range(limit):
        x, _, _ = ds[i]
        d = int(x.shape[1] if x.ndim >= 2 else 1)
        if d > max_d:
            max_d = d
    return int(max_d)


def build_loader(
    csv_path: Path,
    batch_size: int,
    shuffle: bool,
    num_workers: int,
    *,
    features_root: Optional[Path] = None,
    label_to_index_json: Optional[Path] = None,
    feature_dim: Optional[int] = None,
    seed: int = 42,
) -> DataLoader:
    ds = NPZSignDataset(csv_path, root=features_root, label_to_index_json=label_to_index_json, to_tensor=True)
    if feature_dim is None:
        collate = pad_collate_fn
    else:
        collate = lambda b: pad_collate_fn(
            b,
            feature_dim=int(feature_dim),
            on_feature_dim_mismatch="error",
            log_feature_dim_mismatch=False,
        )
    g = torch.Generator()
    g.manual_seed(int(seed))
    return DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=shuffle,
        collate_fn=collate,
        num_workers=num_workers,
        worker_init_fn=_seed_worker,
        generator=g,
    )


def _slugify(text: str) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9\-\+_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "subset"


def _parse_multi_values(values: Optional[Sequence[str]]) -> List[str]:
    if not values:
        return []
    out: List[str] = []
    for v in values:
        if v is None:
            continue
        parts = [p.strip() for p in str(v).split(",")]
        for p in parts:
            if p:
                out.append(p)
    seen = set()
    deduped: List[str] = []
    for x in out:
        if x in seen:
            continue
        seen.add(x)
        deduped.append(x)
    return deduped


def _read_csv_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


def _write_csv_rows(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def _ensure_cols(fieldnames: List[str], needed: Iterable[str]) -> List[str]:
    out = list(fieldnames)
    for n in needed:
        if n not in out:
            out.append(n)
    return out


def _build_subset_label_maps(
    rows: List[Dict[str, str]],
    *,
    default_language: str = "vn",
) -> Tuple[Dict[str, int], Dict[int, Dict[str, str]]]:
    for r in rows:
        if not (r.get("language") or "").strip():
            r["language"] = default_language
        if not (r.get("label_key") or "").strip():
            ci = (r.get("class_idx") or "").strip()
            slug = (r.get("label_slug") or "").strip()
            dialect = (r.get("dialect") or "").strip()
            language = (r.get("language") or default_language).strip()
            if slug:
                r["label_key"] = f"{language}/{dialect}/{slug}" if dialect else f"{language}/{slug}"
            elif ci:
                r["label_key"] = f"class_idx/{ci}"
            else:
                r["label_key"] = "unknown"

    unique_keys: List[str] = []
    seen = set()
    for r in rows:
        k = (r.get("label_key") or "").strip()
        if not k or k in seen:
            continue
        seen.add(k)
        unique_keys.append(k)

    label_to_index: Dict[str, int] = {k: i for i, k in enumerate(unique_keys)}
    index_to_label: Dict[int, Dict[str, str]] = {}

    first_by_key: Dict[str, Dict[str, str]] = {}
    for r in rows:
        k = (r.get("label_key") or "").strip()
        if k and k not in first_by_key:
            first_by_key[k] = r

    for k, i in label_to_index.items():
        r = first_by_key.get(k, {})
        index_to_label[i] = {
            "label_key": k,
            "label_slug": (r.get("label_slug") or "").strip(),
            "label_original": (r.get("label_original") or "").strip(),
            "language": (r.get("language") or default_language).strip(),
            "dialect": (r.get("dialect") or "").strip(),
        }
    return label_to_index, index_to_label


def _ensure_label_key_inplace(rows: List[Dict[str, str]], *, default_language: str = "vn") -> None:
    for r in rows:
        if not (r.get("language") or "").strip():
            r["language"] = default_language
        if not (r.get("label_key") or "").strip():
            ci = (r.get("class_idx") or "").strip()
            slug = (r.get("label_slug") or "").strip()
            dialect = (r.get("dialect") or "").strip()
            language = (r.get("language") or default_language).strip()
            if slug:
                r["label_key"] = f"{language}/{dialect}/{slug}" if dialect else f"{language}/{slug}"
            elif ci:
                r["label_key"] = f"class_idx/{ci}"
            else:
                r["label_key"] = "unknown"


def _find_features_root_from_csv(csv_path: Path) -> Optional[Path]:
    p = csv_path.resolve()
    try:
        from train_model.dataset_versioning import get_features_dir
        features_root = get_features_dir()
        if features_root.exists() and features_root.is_dir():
            return features_root
    except Exception:
        pass
    for parent in [p] + list(p.parents)[:8]:
        cand = parent / "features"
        if cand.exists() and cand.is_dir():
            return cand
    return None


def _infer_language_dialect_from_label_key(label_key: str, *, default_language: str = "vn") -> Tuple[str, str]:
    lk = (label_key or "").strip()
    if not lk:
        return (default_language, "")
    parts = [p for p in lk.split("/") if p]
    if not parts:
        return (default_language, "")
    if parts[0] in {"class_idx", "unknown"}:
        return (default_language, "")
    language = parts[0]
    dialect = parts[1] if len(parts) >= 3 else ""
    return (language or default_language, dialect)


def _filter_rows_by_dialect(rows: List[Dict[str, str]], dialects: Sequence[str]) -> List[Dict[str, str]]:
    if not dialects:
        return list(rows)
    wanted = {d.strip() for d in dialects if d.strip()}

    out: List[Dict[str, str]] = []
    for r in rows:
        row_dialect = (r.get("dialect") or "").strip()
        if not row_dialect:
            lk = (r.get("label_key") or "").strip()
            _, inferred_dialect = _infer_language_dialect_from_label_key(lk, default_language=(r.get("language") or "vn").strip() or "vn")
            row_dialect = (inferred_dialect or "").strip()
        if row_dialect in wanted:
            out.append(r)
    return out


def _filter_rows_by_language(rows: List[Dict[str, str]], languages: Sequence[str], *, default_language: str = "vn") -> List[Dict[str, str]]:
    if not languages:
        return list(rows)
    wanted = {d.strip() for d in languages if d.strip()}

    out: List[Dict[str, str]] = []
    for r in rows:
        row_lang = (r.get("language") or "").strip()
        if not row_lang:
            lk = (r.get("label_key") or "").strip()
            inferred_lang, _ = _infer_language_dialect_from_label_key(lk, default_language=default_language)
            row_lang = (inferred_lang or default_language).strip()
        if row_lang in wanted:
            out.append(r)
    return out


def _row_feature_path_candidates(row: Dict[str, str], *, features_root: Path, default_language: str = "vn") -> List[Path]:
    folder_name = (row.get("folder_name") or "").strip()
    file_name = (row.get("file") or "").strip()
    if not folder_name or not file_name:
        return []
    candidates: List[Path] = [features_root / folder_name / file_name]

    language = (row.get("language") or default_language).strip() or default_language
    dialect = (row.get("dialect") or "").strip()
    if not dialect:
        lk = (row.get("label_key") or "").strip()
        _, inferred_dialect = _infer_language_dialect_from_label_key(lk, default_language=language)
        dialect = (inferred_dialect or "").strip()
    if dialect:
        candidates.append(features_root / language / dialect / folder_name / file_name)
    return candidates


def _filter_rows_with_existing_features(
    rows: List[Dict[str, str]],
    *,
    features_root: Path,
    default_language: str = "vn",
    max_examples: int = 3,
    label: str = "split",
) -> List[Dict[str, str]]:
    kept: List[Dict[str, str]] = []
    missing_examples: List[str] = []
    missing_count = 0
    for r in rows:
        candidates = _row_feature_path_candidates(r, features_root=features_root, default_language=default_language)
        ok = any(p.exists() for p in candidates)
        if ok:
            kept.append(r)
        else:
            missing_count += 1
            if len(missing_examples) < max_examples:
                sid = (r.get("sample_id") or "").strip()
                folder_name = (r.get("folder_name") or "").strip()
                file_name = (r.get("file") or "").strip()
                missing_examples.append(f"sample_id={sid} folder={folder_name} file={file_name}")
    if missing_count:
        suffix = (" Examples: " + " | ".join(missing_examples)) if missing_examples else ""
        print(f"[WARN] Removed {missing_count} rows from {label} due to missing .npz feature files." + suffix)
    return kept


def apply_temporal_mask(x: tf.Tensor, mask_prob: float = 0.15) -> tf.Tensor:
    """Randomly drop out entire frames (set to 0) to prevent overfitting on specific temporal patterns."""
    if mask_prob <= 0.0:
        return x
    # x shape: [B, T, D]
    mask = tf.random.uniform(tf.shape(x)[:2]) > mask_prob
    mask = tf.cast(mask, x.dtype)
    return x * tf.expand_dims(mask, -1)


def train_one_epoch(model: tf.keras.Model, loader: DataLoader, opt: tf.keras.optimizers.Optimizer, loss_fn, num_classes: int, temporal_mask_prob: float) -> Tuple[float, float]:
    total_loss = 0.0
    total_acc = 0.0
    n = 0
    for X, y, lengths, _ in loader:
        X_tf = tf.convert_to_tensor(X.numpy(), dtype=tf.float32)
        y_tf = tf.convert_to_tensor(y.numpy(), dtype=tf.int64)
        lengths_tf = tf.convert_to_tensor(lengths.numpy(), dtype=tf.int32)

        # Apply augmentation: temporal masking
        if temporal_mask_prob > 0:
            X_tf = apply_temporal_mask(X_tf, temporal_mask_prob)

        y_onehot = tf.one_hot(y_tf, depth=num_classes)

        with tf.GradientTape() as tape:
            logits = model([X_tf, lengths_tf], training=True)
            loss = loss_fn(y_onehot, logits)
            
            # If using mixed precision, scale the loss before computing gradients
            if hasattr(opt, 'scale_loss'):
                scaled_loss = opt.scale_loss(loss)
            elif hasattr(opt, 'get_scaled_loss'):
                scaled_loss = opt.get_scaled_loss(loss)
            else:
                scaled_loss = loss

        grads = tape.gradient(scaled_loss, model.trainable_variables)
        opt.apply_gradients(zip(grads, model.trainable_variables))

        preds = tf.argmax(logits, axis=1)
        acc = tf.reduce_sum(tf.cast(preds == y_tf, tf.float32))

        bs = int(tf.shape(y_tf)[0].numpy())
        total_loss += loss.numpy() * bs
        total_acc += acc.numpy()
        n += bs
    return total_loss / n, total_acc / n


def evaluate(model: tf.keras.Model, loader: DataLoader, num_classes: int, loss_fn) -> Tuple[float, float, float]:
    total_loss = 0.0
    total_acc = 0.0
    n = 0
    all_logits = []
    all_targets = []
    for X, y, lengths, _ in loader:
        X_tf = tf.convert_to_tensor(X.numpy(), dtype=tf.float32)
        y_tf = tf.convert_to_tensor(y.numpy(), dtype=tf.int64)
        lengths_tf = tf.convert_to_tensor(lengths.numpy(), dtype=tf.int32)

        logits = model([X_tf, lengths_tf], training=False)
        
        y_onehot = tf.one_hot(y_tf, depth=num_classes)
        loss = loss_fn(y_onehot, logits)

        bs = int(tf.shape(y_tf)[0].numpy())
        total_loss += loss.numpy() * bs
        preds = tf.argmax(logits, axis=1)
        total_acc += tf.reduce_sum(tf.cast(preds == y_tf, tf.float32)).numpy()
        n += bs

        all_logits.append(logits.numpy())
        all_targets.append(y_tf.numpy())

    logits_np = np.concatenate(all_logits, axis=0) if all_logits else np.zeros((0, num_classes))
    targets_np = np.concatenate(all_targets, axis=0) if all_targets else np.zeros((0,), dtype=np.int64)

    mf1 = macro_f1(logits_np, targets_np, num_classes) if len(logits_np) > 0 else 0.0
    return total_loss / n, total_acc / n, mf1


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a TCN classifier on NPZ sign-sequence features using TensorFlow/Keras.")
    try:
        from train_model.dataset_versioning import get_splits_dir
        default_root = get_splits_dir()
    except Exception:
        default_root = Path(__file__).resolve().parents[1] / "splits"
    parser.add_argument("--train_csv", type=Path, default=default_root / "train.csv")
    parser.add_argument("--val_csv", type=Path, default=default_root / "val.csv")
    parser.add_argument("--test_csv", type=Path, default=default_root / "test.csv")
    parser.add_argument(
        "--dialect",
        action="append",
        default=None,
        help="Optional: filter to one or more dialects (can repeat or comma-separate). Example: --dialect bac",
    )
    parser.add_argument(
        "--filter_language",
        action="append",
        default=None,
        help="Optional: filter to one or more languages (can repeat or comma-separate). Example: --filter_language vn",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="vn",
        help="Default language tag used when missing in CSV (only relevant for subset runs).",
    )
    parser.add_argument(
        "--tag",
        type=str,
        default="",
        help="Optional output tag. If omitted, auto-generated from subset (e.g. dialect).",
    )
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument(
        "--feature_dim",
        type=int,
        default=EXPECTED_FEATURE_DIM,
        help=f"Fixed feature dimension D. Must be {EXPECTED_FEATURE_DIM}.",
    )
    parser.add_argument(
        "--feature_dim_scan",
        type=int,
        default=0,
        help="Unused when feature_dim is fixed.",
    )
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight_decay", type=float, default=1e-4)
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--channels", type=int, default=64)
    parser.add_argument("--levels", type=int, default=3)
    parser.add_argument("--kernel_size", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", type=str, default="gpu")
    parser.add_argument("--num_workers", type=int, default=0)
    parser.add_argument("--out_dir", type=Path, default=Path(__file__).resolve().parent / "outputs")
    
    # Advanced features args
    parser.add_argument("--label_smoothing", type=float, default=0.1)
    parser.add_argument("--mixed_precision", type=lambda v: v.lower() not in ("false", "0", "no"), default=True,
                        help="Enable mixed precision FP16 training (default: True). Pass False/0/no to disable.")
    parser.add_argument("--warmup_ratio", type=float, default=0.1)
    parser.add_argument("--temporal_mask_prob", type=float, default=0.15)
    
    args = parser.parse_args()

    cfg = TrainConfig(
        train_csv=args.train_csv,
        val_csv=args.val_csv,
        test_csv=args.test_csv,
        batch_size=args.batch_size,
        epochs=args.epochs,
        lr=args.lr,
        weight_decay=args.weight_decay,
        dropout=args.dropout,
        channels=args.channels,
        levels=args.levels,
        kernel_size=args.kernel_size,
        seed=args.seed,
        num_workers=args.num_workers,
        out_dir=args.out_dir,
        label_smoothing=args.label_smoothing,
        mixed_precision=args.mixed_precision,
        warmup_ratio=args.warmup_ratio,
        temporal_mask_prob=args.temporal_mask_prob,
    )

    if cfg.mixed_precision:
        policy = tf.keras.mixed_precision.Policy('mixed_float16')
        tf.keras.mixed_precision.set_global_policy(policy)
        print("[INFO] Enabled Mixed Precision (mixed_float16)")

    set_seed(cfg.seed)
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    dialects = _parse_multi_values(args.dialect)
    languages = _parse_multi_values(args.filter_language)
    subset_mode = bool(dialects or languages)

    features_root: Optional[Path] = None
    label_to_index_json: Optional[Path] = None
    subset_tag = ""
    if subset_mode:
        features_root = _find_features_root_from_csv(cfg.train_csv)
        if features_root is None:
            try:
                dataset_root = cfg.train_csv.resolve().parents[2]
                features_root = dataset_root / "features"
            except Exception:
                features_root = None
        if features_root is None or not features_root.exists():
            raise SystemExit("Subset mode requires locating the 'features' folder. Pass split CSVs from this repo layout.")

        if str(args.tag or "").strip():
            subset_tag = _slugify(args.tag)
        else:
            parts: List[str] = []
            if languages:
                parts.append("lang-" + "+".join(languages))
            if dialects:
                parts.append("dialect-" + "+".join(dialects))
            subset_tag = _slugify("_".join(parts) if parts else "subset")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        subset_dir = cfg.out_dir / f"subset_{subset_tag}_{stamp}"
        subset_dir.mkdir(parents=True, exist_ok=True)

        def _prep_one(src_csv: Path, name: str) -> Path:
            rows, fieldnames = _read_csv_rows(src_csv)

            default_lang = str(args.language or "vn").strip() or "vn"
            for r in rows:
                lk = (r.get("label_key") or "").strip()
                if lk:
                    lang, dia = _infer_language_dialect_from_label_key(lk, default_language=default_lang)
                    if not (r.get("language") or "").strip():
                        r["language"] = lang
                    if not (r.get("dialect") or "").strip() and dia:
                        r["dialect"] = dia
            rows = _filter_rows_by_language(rows, languages, default_language=default_lang)
            rows = _filter_rows_by_dialect(rows, dialects)
            if not rows:
                raise SystemExit(
                    f"Subset '{subset_tag}': {name} split is empty after filtering language={languages} dialect={dialects}."
                )
            fieldnames = _ensure_cols(fieldnames, ["dialect", "language", "label_key", "label_slug", "label_original"])
            for r in rows:
                if not (r.get("language") or "").strip():
                    r["language"] = default_lang
            _ensure_label_key_inplace(rows, default_language=default_lang)

            rows = _filter_rows_with_existing_features(
                rows,
                features_root=features_root,  # type: ignore[arg-type]
                default_language=default_lang,
                label=f"{name} split",
            )
            if not rows:
                raise SystemExit(f"Subset '{subset_tag}': {name} split became empty after removing missing feature files.")

            out_csv = subset_dir / f"{name}.csv"
            _write_csv_rows(out_csv, rows, fieldnames)
            return out_csv

        sub_train = _prep_one(cfg.train_csv, "train")
        sub_val = _prep_one(cfg.val_csv, "val")
        sub_test = _prep_one(cfg.test_csv, "test")

        train_rows, _ = _read_csv_rows(sub_train)
        l2i, i2l = _build_subset_label_maps(train_rows, default_language=str(args.language or "vn"))
        if len(l2i) < 2:
            raise SystemExit(f"Subset '{subset_tag}': need at least 2 classes to train; got {len(l2i)}.")

        def _filter_to_known_labels(src_csv: Path, name: str) -> None:
            rows, fieldnames = _read_csv_rows(src_csv)
            _ensure_label_key_inplace(rows, default_language=str(args.language or "vn").strip() or "vn")
            before = len(rows)
            rows = [r for r in rows if (r.get("label_key") or "").strip() in l2i]
            removed = before - len(rows)
            if removed > 0:
                print(f"Subset '{subset_tag}': removed {removed} rows from {name} split due to unseen labels.")
            if not rows:
                raise SystemExit(f"Subset '{subset_tag}': {name} split became empty after removing unseen labels.")
            _write_csv_rows(src_csv, rows, fieldnames)

        _filter_to_known_labels(sub_val, "val")
        _filter_to_known_labels(sub_test, "test")

        label_to_index_json = subset_dir / "label_to_index.json"
        index_to_label_json = subset_dir / "index_to_label.json"
        label_to_index_json.write_text(json.dumps(l2i, indent=2, ensure_ascii=False), encoding="utf-8")
        index_to_label_json.write_text(json.dumps({str(k): v for k, v in i2l.items()}, indent=2, ensure_ascii=False), encoding="utf-8")

        cfg.train_csv = sub_train
        cfg.val_csv = sub_val
        cfg.test_csv = sub_test

    requested_dim = int(args.feature_dim) if int(args.feature_dim) > 0 else EXPECTED_FEATURE_DIM
    if requested_dim != EXPECTED_FEATURE_DIM:
        raise SystemExit(f"feature_dim must be {EXPECTED_FEATURE_DIM}; got {requested_dim}.")
    in_dim = EXPECTED_FEATURE_DIM
    
    ds_tmp = NPZSignDataset(cfg.train_csv, root=features_root, label_to_index_json=label_to_index_json, to_tensor=True)
    if ds_tmp.index_to_label:
        num_classes = len(ds_tmp.index_to_label)
    else:
        label_set = set()
        n_scan = min(len(ds_tmp), 512)
        for i in range(n_scan):
            _, y_i, _ = ds_tmp[i]
            label_set.add(int(y_i))
        num_classes = max(label_set) + 1 if label_set else 1

    model = build_tcn_model(
        in_dim=in_dim,
        num_classes=num_classes,
        channels=cfg.channels,
        levels=cfg.levels,
        kernel_size=cfg.kernel_size,
        dropout=cfg.dropout,
    )

    train_loader = build_loader(
        cfg.train_csv,
        cfg.batch_size,
        shuffle=True,
        num_workers=cfg.num_workers,
        features_root=features_root,
        label_to_index_json=label_to_index_json,
        feature_dim=in_dim,
        seed=cfg.seed,
    )
    val_loader = build_loader(
        cfg.val_csv,
        cfg.batch_size,
        shuffle=False,
        num_workers=cfg.num_workers,
        features_root=features_root,
        label_to_index_json=label_to_index_json,
        feature_dim=in_dim,
        seed=cfg.seed,
    )
    test_loader = build_loader(
        cfg.test_csv,
        cfg.batch_size,
        shuffle=False,
        num_workers=cfg.num_workers,
        features_root=features_root,
        label_to_index_json=label_to_index_json,
        feature_dim=in_dim,
        seed=cfg.seed,
    )

    opt = tf.keras.optimizers.AdamW(learning_rate=cfg.lr, weight_decay=cfg.weight_decay, clipnorm=1.0)
    if cfg.mixed_precision:
        opt = tf.keras.mixed_precision.LossScaleOptimizer(opt)
        
    loss_fn = tf.keras.losses.CategoricalCrossentropy(from_logits=True, label_smoothing=cfg.label_smoothing)

    best_val_f1 = -1.0
    best_weights = None
    patience = 10
    since_best = 0

    warmup_epochs = max(1, int(cfg.epochs * cfg.warmup_ratio))
    
    for epoch in range(1, cfg.epochs + 1):
        if epoch <= warmup_epochs:
            lr = cfg.lr * (epoch / warmup_epochs)
        else:
            progress = (epoch - warmup_epochs) / (cfg.epochs - warmup_epochs)
            lr = cfg.lr * 0.5 * (1 + math.cos(math.pi * progress))
            
        if isinstance(opt, tf.keras.mixed_precision.LossScaleOptimizer):
            opt.inner_optimizer.learning_rate.assign(lr)
        else:
            opt.learning_rate.assign(lr)

        tr_loss, tr_acc = train_one_epoch(model, train_loader, opt, loss_fn, num_classes, cfg.temporal_mask_prob)
        va_loss, va_acc, va_f1 = evaluate(model, val_loader, num_classes, loss_fn)
        
        improved = va_f1 > best_val_f1
        if improved:
            best_val_f1 = va_f1
            best_weights = model.get_weights()
            since_best = 0
        else:
            since_best += 1

        print(
            f"epoch {epoch:03d} | train loss {tr_loss:.4f} acc {tr_acc:.4f} | val loss {va_loss:.4f} acc {va_acc:.4f} f1 {va_f1:.4f}"
        )
        if since_best >= patience:
            print("Early stopping: no improvement in validation F1.")
            break

    if best_weights is not None:
        model.set_weights(best_weights)

    te_loss, te_acc, te_f1 = evaluate(model, test_loader, num_classes, loss_fn)
    te_scs = None
    print(f"test loss {te_loss:.4f} acc {te_acc:.4f} f1 {te_f1:.4f}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"tcn_{stamp}" if not subset_mode else f"tcn_{subset_tag}_{stamp}"
    out_ckpt = cfg.out_dir / f"{prefix}.h5"
    
    label_map = ds_tmp.label_to_index or {}
    if not label_map:
        raise SystemExit("label_map is empty; ensure labels.csv or label_to_index.json is present and valid.")

    model.save(str(out_ckpt), save_format="h5")

    cfg_json = {
        k: (str(v) if isinstance(v, Path) else v)
        for k, v in asdict(cfg).items()
    }

    summary = {
        "timestamp": stamp,
        "subset": {"languages": languages, "dialects": dialects, "language_default": args.language, "tag": subset_tag} if subset_mode else None,
        "config": cfg_json,
        "in_dim": in_dim,
        "feature_dim": in_dim,
        "num_classes": num_classes,
        "label_map": label_map,
        "val_best_f1": best_val_f1,
        "test": {"loss": te_loss, "acc": te_acc, "f1": te_f1, "scs": te_scs},
        "checkpoint": str(out_ckpt),
    }

    (cfg.out_dir / f"{prefix}.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved checkpoint to {out_ckpt} and summary to {cfg.out_dir}")


if __name__ == "__main__":
    main()
