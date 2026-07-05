from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
import shutil
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
try:
    # local metrics (accuracy, SCS, macro-f1) for future use
    from .metrics import sequence_consistency_score  # type: ignore
except Exception:  # pragma: no cover
    import sys as _sys
    from pathlib import Path as _P
    _sys.path.append(str(_P(__file__).resolve().parents[2]))
    from processed.train_utils.metrics import sequence_consistency_score  # type: ignore

try:
    from .handedness_analysis import HandednessAnalyzer, detect_hand_presence  # type: ignore
except Exception:  # pragma: no cover
    import sys as _sys
    from pathlib import Path as _P
    _sys.path.append(str(_P(__file__).resolve().parents[2]))
    from processed.train_utils.handedness_analysis import HandednessAnalyzer, detect_hand_presence  # type: ignore

try:
    from .signer_diversity_checker import check_signer_diversity  # type: ignore
except Exception:
    try:
        from processed.train_utils.signer_diversity_checker import check_signer_diversity  # type: ignore
    except Exception:
        check_signer_diversity = None  # diagnostic optional

try:
    from .sequence_length_analyzer import check_sequence_length_bias  # type: ignore
except Exception:
    try:
        from processed.train_utils.sequence_length_analyzer import check_sequence_length_bias  # type: ignore
    except Exception:
        check_sequence_length_bias = None  # diagnostic optional

try:
    from .imbalance_detector import detect_imbalance  # type: ignore
except Exception:
    try:
        from processed.train_utils.imbalance_detector import detect_imbalance  # type: ignore
    except Exception:
        detect_imbalance = None  # diagnostic optional

try:
    from .augmentation import build_train_augment
except Exception:
    import sys
    from pathlib import Path as _P
    sys.path.append(str(_P(__file__).resolve().parents[2]))
    from processed.train_utils.augmentation import build_train_augment

try:
    # When run as module: python -m processed.train_utils.train_tcn
    from .dataset_loader import NPZSignDataset # type: ignore
except Exception:  # pragma: no cover
    # When run as script: python processed/train_utils/train_tcn.py
    import sys
    from pathlib import Path as _P
    sys.path.append(str(_P(__file__).resolve().parents[2]))
    from processed.train_utils.dataset_loader import NPZSignDataset # type: ignore

try:
    try:
        from .tracking_client import TrackingClient as _TrackingClient  # type: ignore
    except ImportError:
        from processed.train_utils.tracking_client import TrackingClient as _TrackingClient  # type: ignore
except Exception:
    _TrackingClient = None  # type: ignore

try:
    from .models import get_model_class  # type: ignore
except Exception:
    try:
        from processed.train_utils.models import get_model_class  # type: ignore
    except Exception:
        get_model_class = None  # models not available yet


EXPECTED_FEATURE_DIM = 126


def set_seed(seed: int) -> None:
    os.environ.setdefault("PYTHONHASHSEED", str(seed))
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    try:
        torch.use_deterministic_algorithms(True)
    except Exception:
        pass


def _seed_worker(worker_id: int) -> None:
    worker_seed = torch.initial_seed() % 2**32
    np.random.seed(worker_seed)
    random.seed(worker_seed)


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
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    num_workers: int = 0
    out_dir: Path = Path(__file__).resolve().parents[1] / "train_utils" / "outputs"


def accuracy(pred: torch.Tensor, target: torch.Tensor) -> float:
    return (pred.argmax(1) == target).float().mean().item()


def macro_f1(pred: torch.Tensor, target: torch.Tensor, num_classes: int) -> float:
    y_pred = pred.argmax(1)
    f1s: List[float] = []
    for c in range(num_classes):
        tp = ((y_pred == c) & (target == c)).sum().item()
        fp = ((y_pred == c) & (target != c)).sum().item()
        fn = ((y_pred != c) & (target == c)).sum().item()
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        f1s.append(f1)
    return float(sum(f1s) / len(f1s))


def infer_input_dim(csv_path: Path, *, scan_limit: int = 0) -> int:
    """Infer a stable feature dimension (D) for Conv1D input channels.

    If scan_limit == 0, scans the whole dataset. Otherwise scans up to scan_limit samples.
    """
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
    augment_fn=None,
    *,
    features_root: Optional[Path] = None,
    label_to_index_json: Optional[Path] = None,
    feature_dim: Optional[int] = None,
    seed: int = 42,
) -> DataLoader:
    ds = NPZSignDataset(
        csv_path,
        root=features_root,
        label_to_index_json=label_to_index_json,
        to_tensor=True,
        augment_fn=augment_fn,
    )
    g = torch.Generator()
    g.manual_seed(int(seed))
    return DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        worker_init_fn=_seed_worker,
        generator=g,
        pin_memory=torch.cuda.is_available(),
        persistent_workers=( num_workers > 0 and os.name != "nt" ),
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
    # dedupe while keeping order
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
    # Ensure every row has a stable label_key.
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

    # Best-effort metadata: pick the first row for each key.
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
    # Look upwards for a sibling 'features' folder (common repo layout).
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
    # Non-hierarchical fallback keys used in some CSVs.
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


def train_one_epoch(model: nn.Module, loader: DataLoader, opt: torch.optim.Optimizer, device: str) -> Tuple[float, float]:
    model.train()
    total_loss = 0.0
    total_acc = 0.0
    n = 0
    criterion = nn.CrossEntropyLoss()
    for X, y, _ in loader:
        X = X.to(device)
        y = y.to(device)
        logits = model(X)
        loss = criterion(logits, y)
        if not torch.isfinite(loss):
            print("Non-finite loss detected.")
            continue
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        opt.step()
        bs = y.size(0)
        total_loss += loss.item() * bs
        total_acc += (logits.argmax(1) == y).float().sum().item()
        n += bs
    return total_loss / n, total_acc / n


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: str, num_classes: int) -> Tuple[float, float, float]:
    model.eval()
    criterion = nn.CrossEntropyLoss()
    total_loss = 0.0
    total_acc = 0.0
    n = 0
    all_logits: List[torch.Tensor] = []
    all_targets: List[torch.Tensor] = []
    for X, y, _ in loader:
        X = X.to(device)
        y = y.to(device)
        logits = model(X)
        loss = criterion(logits, y)
        bs = y.size(0)
        total_loss += loss.item() * bs
        total_acc += (logits.argmax(1) == y).float().sum().item()
        n += bs
        all_logits.append(logits.cpu())
        all_targets.append(y.cpu())
    logits = torch.cat(all_logits, dim=0) if all_logits else torch.empty(0, num_classes)
    targets = torch.cat(all_targets, dim=0) if all_targets else torch.empty(0, dtype=torch.long)
    mf1 = macro_f1(logits, targets, num_classes) if logits.numel() > 0 else 0.0
    return total_loss / n, total_acc / n, mf1


@torch.no_grad()
def evaluate_with_handedness(
    model: nn.Module,
    loader: DataLoader,
    device: str,
    num_classes: int,
) -> Tuple[float, float, float, Dict[str, float]]:
    """
    Evaluate with per-hand accuracy tracking.

    Returns:
        (loss, accuracy, macro_f1, handedness_metrics)
    """
    model.eval()
    criterion = nn.CrossEntropyLoss()
    total_loss = 0.0
    total_acc = 0.0
    n = 0

    # Per-hand tracking
    left_only_acc = 0.0
    left_only_n = 0
    right_only_acc = 0.0
    right_only_n = 0
    both_acc = 0.0
    both_n = 0

    all_logits: List[torch.Tensor] = []
    all_targets: List[torch.Tensor] = []

    for X, y, meta in loader:
        X = X.to(device)
        y = y.to(device)
        logits = model(X)
        loss = criterion(logits, y)

        preds = logits.argmax(1)
        correct = (preds == y).float()

        bs = y.size(0)
        total_loss += loss.item() * bs
        total_acc += correct.sum().item()
        n += bs

        # Analyze hand presence per sample
        X_np = X.cpu().numpy()
        for i in range(bs):
            left_p, right_p = detect_hand_presence(X_np[i])
            is_correct = bool(correct[i].item())

            if left_p and not right_p:
                left_only_acc += float(is_correct)
                left_only_n += 1
            elif right_p and not left_p:
                right_only_acc += float(is_correct)
                right_only_n += 1
            elif left_p and right_p:
                both_acc += float(is_correct)
                both_n += 1

        all_logits.append(logits.cpu())
        all_targets.append(y.cpu())

    logits = torch.cat(all_logits, dim=0) if all_logits else torch.empty(0, num_classes)
    targets = torch.cat(all_targets, dim=0) if all_targets else torch.empty(0, dtype=torch.long)
    mf1 = macro_f1(logits, targets, num_classes) if logits.numel() > 0 else 0.0

    hand_metrics = {
        'left_only_acc': left_only_acc / max(1, left_only_n),
        'left_only_n': left_only_n,
        'right_only_acc': right_only_acc / max(1, right_only_n),
        'right_only_n': right_only_n,
        'both_acc': both_acc / max(1, both_n),
        'both_n': both_n,
    }

    return total_loss / n, total_acc / n, mf1, hand_metrics

@torch.no_grad()
def compute_test_evaluation(
    model: nn.Module,
    loader: DataLoader,
    device: str,
    num_classes: int,
    label_map: Dict[str, int],
) -> Dict[str, object]:
    """Confusion matrix + per-class precision/recall/F1 on a loader.

    Returned structure is JSON-serializable and goes into the metrics-file
    "final" record so the trainer can persist it for the Step 7 UI.
    """
    model.eval()
    cm = [[0] * num_classes for _ in range(num_classes)]
    for X, y, _ in loader:
        X = X.to(device)
        preds = model(X).argmax(1).cpu().tolist()
        for t, p in zip(y.tolist(), preds):
            if 0 <= t < num_classes and 0 <= p < num_classes:
                cm[t][p] += 1

    idx_to_label = {int(v): str(k) for k, v in label_map.items()}
    per_class = []
    for c in range(num_classes):
        tp = cm[c][c]
        support = sum(cm[c])
        pred_total = sum(cm[r][c] for r in range(num_classes))
        precision = tp / pred_total if pred_total else 0.0
        recall = tp / support if support else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        per_class.append({
            "class_idx": c,
            "label_key": idx_to_label.get(c, f"class_{c}"),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        })

    labels = [idx_to_label.get(c, f"class_{c}") for c in range(num_classes)]
    return {"labels": labels, "confusion_matrix": cm, "per_class": per_class}


def build_checkpoint(
    *,
    model,
    cfg,
    in_dim,
    num_classes,
    label_map,
    te_acc=None,
    te_f1=None,
    te_hand_metrics=None,
    stamp="",
):
    return {
        "schema_version": "1.0",

        "model_state_dict": {
            k: v.detach().cpu()
            for k, v in model.state_dict().items()
        },

        "model_type": "TCN",

        "model_config": {
            "channels": cfg.channels,
            "levels": cfg.levels,
            "kernel_size": cfg.kernel_size,
            "dropout": cfg.dropout,
        },

        "feature_dim": EXPECTED_FEATURE_DIM,

        "seq_len": 60,

        "num_classes": num_classes,

        "idx_to_label": {
            int(v): k
            for k, v in label_map.items()
        },

        "label_to_idx": label_map,

        "normalization_version": "hands126_v1",

        "preprocess_contract": {
            "landmark_order": "MP_Left(63)+MP_Right(63)",
            "missing_hands": "zero_filled",
            "coordinate_space": "mediapipe_normalized",
            "coordinate_order": "xyz",
            "frontend_mirroring": "visual_only",
            "expects_strict_shape": [60, 126],
        },

        "metrics": {
            "test_acc": te_acc,
            "test_f1": te_f1,
            "handedness": te_hand_metrics or {},
        },

        "created_at": stamp,
    }

def main() -> None:
    parser = argparse.ArgumentParser(description="Train a TCN classifier on NPZ sign-sequence features.")
    try:
        from train_model.dataset_versioning import get_splits_dir
        default_root = get_splits_dir()
    except Exception:
        default_root = Path(__file__).resolve().parents[1] / "splits"
    parser.add_argument("--train_csv", type=Path, default=default_root / "train.csv")
    parser.add_argument("--val_csv", type=Path, default=default_root / "val.csv")
    parser.add_argument("--test_csv", type=Path, default=default_root / "test.csv")
    parser.add_argument(
        "--features_root",
        type=Path,
        default=None,
        help="Root directory containing feature .npz files"
    )
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
    parser.add_argument(
        "--model_type",
        type=str,
        default="tcn",
        choices=["tcn", "cnn", "lstm", "bigru_attention", "hdgcn"],
        help="Model architecture to use. Default: tcn",
    )
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument(
        "--metrics_file",
        type=str,
        default="",
        help=(
            "Optional path to a JSONL file. One JSON object per epoch is appended "
            "(structured metrics channel for the backend — more robust than stdout parsing)."
        ),
    )
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
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--num_workers", type=int, default=0)
    parser.add_argument("--out_dir", type=Path, default=Path(__file__).resolve().parent / "outputs")
    parser.add_argument("--run_diagnostics", action="store_true", help="Run signer diversity, imbalance, and sequence length diagnostics after training")
    parser.add_argument(
        "--track",
        action="store_true",
        default=False,
        help="Enable experiment tracking via the SignBridge API. Training is unaffected if the API is unavailable.",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000/api/v1",
        help="Base URL for the SignBridge tracking API (default: http://localhost:8000/api/v1).",
    )
    parser.add_argument(
        "--experiment-id",
        type=int,
        default=None,
        help="Attach tracking to an existing experiment ID instead of creating a new one.",
    )
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
        device=args.device,
        num_workers=args.num_workers,
        out_dir=args.out_dir,
    )

    set_seed(cfg.seed)
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    dialects = _parse_multi_values(args.dialect)
    languages = _parse_multi_values(args.filter_language)
    subset_mode = bool(dialects or languages)

    # For subset runs, create a filtered copy of split CSVs and a local label mapping.
    # IMPORTANT: default behavior remains unchanged when no subset args are provided.
    features_root: Optional[Path] = None
    label_to_index_json: Optional[Path] = None
    subset_tag = ""
    if subset_mode:
        # Determine an absolute features root so generated CSVs can live anywhere.
        features_root = ( args.features_root if args.features_root is not None else _find_features_root_from_csv(cfg.train_csv) )
        if features_root is None:
            # Back-compat heuristic for the default layout: <root>/processed/splits/train.csv
            try:
                dataset_root = cfg.train_csv.resolve().parents[2]
                features_root = dataset_root / "dataset" / "features"
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

            # Some older split CSVs don't include explicit dialect/language columns.
            # Infer them from label_key so --dialect can still work without regenerating splits.
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
            # fill language default if missing
            for r in rows:
                if not (r.get("language") or "").strip():
                    r["language"] = default_lang
            # ensure label_key exists (so dataset uses the same key consistently)
            _ensure_label_key_inplace(rows, default_language=default_lang)

            # Guardrail: remove rows whose referenced feature files don't exist.
            # This prevents crashes during feature_dim inference / __getitem__.
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

        # Build label maps from TRAIN split only (common practice).
        train_rows, _ = _read_csv_rows(sub_train)
        l2i, i2l = _build_subset_label_maps(train_rows, default_language=str(args.language or "vn"))
        if len(l2i) < 2:
            raise SystemExit(f"Subset '{subset_tag}': need at least 2 classes to train; got {len(l2i)}.")

        # Guardrail: ensure val/test don't contain unseen labels (prevents out-of-range targets).
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

        # Update config to point at the subset CSVs.
        cfg.train_csv = sub_train
        cfg.val_csv = sub_val
        cfg.test_csv = sub_test

    # Enforce fixed feature dimension to match dataset spec (60,126).
    requested_dim = int(args.feature_dim) if int(args.feature_dim) > 0 else EXPECTED_FEATURE_DIM
    if requested_dim != EXPECTED_FEATURE_DIM:
        raise SystemExit(f"feature_dim must be {EXPECTED_FEATURE_DIM}; got {requested_dim}.")
    in_dim = EXPECTED_FEATURE_DIM
    # infer number of classes from label_to_index if present
    ds_tmp = NPZSignDataset(cfg.train_csv, root=features_root, label_to_index_json=label_to_index_json, to_tensor=True)
    label_map = ds_tmp.label_to_index or {}

    if not label_map:
        raise SystemExit(
            "label_map is empty; ensure labels.csv or label_to_index.json is present and valid."
        )
    if ds_tmp.index_to_label:
        num_classes = len(ds_tmp.index_to_label)
        if num_classes < 2:
            raise SystemExit(
                f"Need at least 2 classes, got {num_classes}"
            )
    else:
        # fallback: scan labels from a subset of the train set
        label_set = set()
        n_scan = min(len(ds_tmp), 512)
        for i in range(n_scan):
            _, y_i, _ = ds_tmp[i]
            label_set.add(int(y_i))
        num_classes = max(label_set) + 1 if label_set else 1

    # Create model from registry (unified for all architectures)
    if get_model_class is None:
        raise RuntimeError("Models registry not available. Check processed/train_utils/models/__init__.py")

    try:
        model_class = get_model_class(args.model_type)
        config = {
            "channels": cfg.channels,
            "levels": cfg.levels,
            "kernel_size": cfg.kernel_size,
            "dropout": cfg.dropout,
        }
        model = model_class.from_config(
            input_dim=in_dim,
            output_dim=num_classes,
            config=config,
        ).to(cfg.device)
        model_name = model.get_model_name()
    except Exception as e:
        raise RuntimeError(
            f"Failed to load model '{args.model_type}': {e}\n"
            f"Supported models: tcn, cnn, lstm, bigru_attention, handgcn (hdgcn)"
        )

    print(f"\n{'='*70}")
    print(f"Model: {model_name}")
    print(f"Input Dim: {in_dim} | Output Dim: {num_classes}")
    print(f"{'='*70}")

    train_augment = build_train_augment()

    train_loader = build_loader(
        cfg.train_csv,
        cfg.batch_size,
        shuffle=True,
        num_workers=cfg.num_workers,
        features_root=features_root,
        label_to_index_json=label_to_index_json,
        feature_dim=in_dim,
        seed=cfg.seed,
        augment_fn=train_augment,
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
        augment_fn=None,
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
        augment_fn=None,
    )

    sample_batch = next(iter(train_loader))

    X0 = sample_batch[0]

    if X0.shape[-1] != EXPECTED_FEATURE_DIM:
        raise RuntimeError(
            f"Invalid feature dim: {X0.shape}"
        )


    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=cfg.epochs)

    best_val_f1 = -1.0
    best_state = None
    patience = 10
    since_best = 0
    _best_epoch_track = 0
    _best_val_acc_track = 0.0

    # For handedness analysis
    hand_analyzer = HandednessAnalyzer()

    # === EXPERIMENT TRACKING SETUP ===
    # Active only when --track is passed. All failures are caught and logged.
    # If the API is offline or returns errors, training continues unaffected.
    tracker = None
    experiment_id = None
    if args.track and _TrackingClient is not None:
        try:
            tracker = _TrackingClient(args.api_url)
            if args.experiment_id is not None:
                # Attach to existing experiment — caller (e.g. run_training_job) already
                # created the row and set status to "running". Skip create_experiment().
                experiment_id = args.experiment_id
                print(f"[TRACKING] Attached to existing experiment {experiment_id} at {args.api_url}")
            else:
                if subset_mode:
                    _subset_path_track = str(subset_dir.resolve())
                else:
                    # Freeze a snapshot of the live splits so every tracked experiment
                    # references an immutable directory, not the mutable splits folder.
                    _snap_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    _snapshot_dir = cfg.out_dir / f"snapshot_{_snap_stamp}"
                    _snapshot_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(cfg.train_csv, _snapshot_dir / "train.csv")
                    shutil.copy2(cfg.val_csv,   _snapshot_dir / "val.csv")
                    shutil.copy2(cfg.test_csv,  _snapshot_dir / "test.csv")
                    _subset_path_track = str(_snapshot_dir.resolve())
                _dialect_track = "+".join(dialects) if dialects else "all"
                experiment_id = tracker.create_experiment(
                    dialect=_dialect_track,
                    subset_path=_subset_path_track,
                    hyperparameters={
                        "lr": cfg.lr,
                        "batch_size": cfg.batch_size,
                        "epochs": cfg.epochs,
                        "dropout": cfg.dropout,
                        "channels": cfg.channels,
                        "levels": cfg.levels,
                        "kernel_size": cfg.kernel_size,
                        "seed": cfg.seed,
                        "weight_decay": cfg.weight_decay,
                    },
                    split_manifest={
                        "train_count": len(train_loader.dataset),
                        "val_count": len(val_loader.dataset),
                        "test_count": len(test_loader.dataset),
                    },
                )
                if experiment_id is not None:
                    tracker.update_status(experiment_id, "running")
                    print(f"[TRACKING] Experiment {experiment_id} created at {args.api_url}")
        except Exception as _te:
            print(f"[TRACKING] Setup failed (tracking disabled for this run): {_te}")
            tracker = None
            experiment_id = None
    elif args.track:
        print("[TRACKING] tracking_client.py not available; --track disabled.")

    # Structured metrics channel (JSONL) — appended per epoch, fsync'd so an
    # external tailer (Celery trainer task) sees each line as soon as written.
    metrics_file_path: Optional[Path] = None
    if getattr(args, "metrics_file", ""):
        metrics_file_path = Path(args.metrics_file)
        metrics_file_path.parent.mkdir(parents=True, exist_ok=True)

    def _append_metric_line(payload: Dict[str, object]) -> None:
        if metrics_file_path is None:
            return
        try:
            with open(metrics_file_path, "a", encoding="utf-8") as mf:
                mf.write(json.dumps(payload, ensure_ascii=False) + "\n")
                mf.flush()
                os.fsync(mf.fileno())
        except Exception as _me:
            print(f"[METRICS_FILE] write failed: {_me}")

    try:
        for epoch in range(1, cfg.epochs + 1):
            tr_loss, tr_acc = train_one_epoch(model, train_loader, opt, cfg.device)
            va_loss, va_acc, va_f1, hand_metrics = evaluate_with_handedness(model, val_loader, cfg.device, num_classes)
            _lr_logged = float(opt.param_groups[0]['lr'])
            scheduler.step()
            improved = va_f1 > best_val_f1
            if improved:
                best_val_f1 = va_f1
                best_state = {k: v.cpu() for k, v in model.state_dict().items()}
                since_best = 0
                _best_epoch_track = epoch
                _best_val_acc_track = va_acc
            else:
                since_best += 1

            hand_str = f"left_only:{hand_metrics['left_only_acc']:.3f}({hand_metrics['left_only_n']}) right_only:{hand_metrics['right_only_acc']:.3f}({hand_metrics['right_only_n']}) both:{hand_metrics['both_acc']:.3f}({hand_metrics['both_n']})"
            print(
                f"[{model_name}] epoch {epoch:03d} | train loss {tr_loss:.4f} acc {tr_acc:.4f} | val loss {va_loss:.4f} acc {va_acc:.4f} f1 {va_f1:.4f}"
            )
            print(f"           | {hand_str}")

            _append_metric_line({
                "type": "epoch",
                "epoch": epoch,
                "total_epochs": cfg.epochs,
                "train_loss": round(tr_loss, 6),
                "train_acc": round(tr_acc, 6),
                "val_loss": round(va_loss, 6),
                "val_acc": round(va_acc, 6),
                "val_f1": round(va_f1, 6),
                "learning_rate": _lr_logged,
            })

            if tracker and experiment_id:
                tracker.log_metric(
                    experiment_id, epoch,
                    tr_loss, tr_acc, va_loss, va_acc, va_f1, _lr_logged,
                )

            if since_best >= patience:
                print("Early stopping: no improvement in validation F1.")
                break
    except BaseException:
        if tracker and experiment_id:
            tracker.update_status(experiment_id, "failed")
        raise

    if best_state is not None:
        model.load_state_dict(best_state)  # type: ignore[arg-type]

    te_loss, te_acc, te_f1, te_hand_metrics = evaluate_with_handedness(model, test_loader, cfg.device, num_classes)

    # Per-class breakdown + confusion matrix for the Step 7 results UI
    test_evaluation = None
    try:
        test_evaluation = compute_test_evaluation(model, test_loader, cfg.device, num_classes, label_map)
    except Exception as _ee:
        print(f"[EVAL] confusion matrix computation failed (non-fatal): {_ee}")
    # Note: SCS (Sequence Consistency Score) pertains to stability across consecutive window predictions.
    # This trainer produces one prediction per sequence, not per sliding window, so SCS is not applicable here.
    # We include it as None in the summary for compatibility with realtime/windowed evaluation.
    te_scs = None
    print(f"\n{'='*70}")
    print("TEST METRICS")
    print(f"{'='*70}")
    print(f"test loss {te_loss:.4f} acc {te_acc:.4f} f1 {te_f1:.4f}")
    print(f"Handedness breakdown:")
    print(f"  Left-hand-only:  {te_hand_metrics['left_only_acc']:.4f} ({te_hand_metrics['left_only_n']} samples)")
    print(f"  Right-hand-only: {te_hand_metrics['right_only_acc']:.4f} ({te_hand_metrics['right_only_n']} samples)")
    print(f"  Both hands:      {te_hand_metrics['both_acc']:.4f} ({te_hand_metrics['both_n']} samples)")
    print(f"{'='*70}\n")

    if tracker and experiment_id:
        tracker.update_status(experiment_id, "completed")
        tracker.update_summary(experiment_id, _best_epoch_track, _best_val_acc_track, best_val_f1)

    # save
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    final_checkpoint = build_checkpoint(
        model=model,
        cfg=cfg,
        in_dim=in_dim,
        num_classes=num_classes,
        label_map=label_map,
        te_acc=te_acc,
        te_f1=te_f1,
        te_hand_metrics=te_hand_metrics,
        stamp=stamp,
    )
    # Use actual model name instead of hardcoded "tcn"
    # Clean up model name: remove special chars, normalize spaces
    model_type = model_name.lower()
    model_type = model_type.replace(" + ", "_").replace(" ", "_").replace("(legacy)", "").strip()
    model_type = "".join(c for c in model_type if c.isalnum() or c == "_")  # Remove special chars

    # Update checkpoint with actual model type
    final_checkpoint["model_type"] = model_name

    prefix = f"{model_type}_{stamp}" if not subset_mode else f"{model_type}_{subset_tag}_{stamp}"
    out_ckpt = cfg.out_dir / f"{prefix}.pt"

    torch.save(final_checkpoint, out_ckpt)

    # Final line tells the tailer the EXACT checkpoint of this run
    # (no more "latest file by mtime" guessing) + test metrics.
    _append_metric_line({
        "type": "final",
        "checkpoint_path": str(out_ckpt.resolve()),
        "test_acc": round(float(te_acc), 6),
        "test_f1": round(float(te_f1), 6),
        "model_type": model_name,
        "evaluation": test_evaluation,  # confusion matrix + per-class (may be None)
    })

    if tracker and experiment_id:
        _model_family_track = f"{subset_tag}-{model_type}" if subset_mode else model_type
        _dialect_model_track = "+".join(dialects) if dialects else "all"
        _runtime_env_track = {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "pytorch_version": torch.__version__,
            "cuda_version": torch.version.cuda or "none",
            "device": cfg.device,
        }
        tracker.register_model(
            experiment_id=experiment_id,
            model_family=_model_family_track,
            dialect=_dialect_model_track,
            checkpoint_path=str(out_ckpt.resolve()),
            feature_contract={
                "extractor": "mediapipe_hands",
                "input_shape": [60, 126],
                "normalization": "hands126_v1",
                "coordinate_order": "xyz",
                "missing_hands": "zero_filled",
            },
            runtime_env=_runtime_env_track,
            accuracy=te_acc,
            f1_macro=te_f1,
        )

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
        "val_best_f1": best_val_f1,
        "test": {
            "loss": te_loss,
            "acc": te_acc,
            "f1": te_f1,
            "scs": te_scs,
            "handedness": {
                "left_only_acc": te_hand_metrics['left_only_acc'],
                "left_only_n": te_hand_metrics['left_only_n'],
                "right_only_acc": te_hand_metrics['right_only_acc'],
                "right_only_n": te_hand_metrics['right_only_n'],
                "both_acc": te_hand_metrics['both_acc'],
                "both_n": te_hand_metrics['both_n'],
            }
        },
        "checkpoint": str(out_ckpt),
    }

    (cfg.out_dir / f"{prefix}.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved checkpoint and summary to {cfg.out_dir}")

    # OPTIONAL: Run diagnostic tools (additive observability only)
    if args.run_diagnostics:
        print(f"\n{'='*80}")
        print("RUNNING DIAGNOSTICS (ADDITIVE OBSERVABILITY)")
        print(f"{'='*80}")

        label_by_idx = {int(v): k for k, v in label_map.items()}

        # Signer diversity check
        if check_signer_diversity is not None:
            try:
                check_signer_diversity(cfg.train_csv, label_by_idx)
            except Exception as e:
                print(f"[WARN] Signer diversity check failed: {e}")

        # Imbalance detection
        if detect_imbalance is not None:
            try:
                detect_imbalance(cfg.train_csv, label_by_idx)
            except Exception as e:
                print(f"[WARN] Imbalance detection failed: {e}")

        # Sequence length analysis
        if check_sequence_length_bias is not None:
            try:
                features_root = _find_features_root_from_csv(cfg.train_csv)
                if features_root is None:
                    try:
                        dataset_root = cfg.train_csv.resolve().parents[2]
                        features_root = dataset_root / "dataset" / "features"
                    except Exception:
                        features_root = None

                if features_root is not None and features_root.exists():
                    check_sequence_length_bias(cfg.train_csv, features_root, label_by_idx)
                else:
                    print(f"[WARN] Features root not found for sequence length analysis")
            except Exception as e:
                print(f"[WARN] Sequence length analysis failed: {e}")


if __name__ == "__main__":
    main()
