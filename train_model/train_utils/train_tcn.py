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
    from train_model.train_utils.metrics import sequence_consistency_score  # type: ignore

try:
    # When run as module: python -m processed.train_utils.train_tcn
    from .dataset_loader import NPZSignDataset, pad_collate_fn  # type: ignore
except Exception:  # pragma: no cover
    # When run as script: python processed/train_utils/train_tcn.py
    import sys
    from pathlib import Path as _P
    sys.path.append(str(_P(__file__).resolve().parents[2]))
    from train_model.train_utils.dataset_loader import NPZSignDataset, pad_collate_fn  # type: ignore


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


class Chomp1d(nn.Module):
    def __init__(self, chomp_size: int):
        super().__init__()
        self.chomp_size = chomp_size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x[:, :, : x.size(2) - self.chomp_size]


class TemporalBlock(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        dilation: int,
        dropout: float,
    ) -> None:
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

        # Kaiming initialization
        for m in [self.conv1, self.conv2]:
            nn.init.kaiming_normal_(m.weight, nonlinearity="relu")
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        if self.downsample is not None:
            nn.init.kaiming_normal_(self.downsample.weight, nonlinearity="linear")
            if self.downsample.bias is not None:
                nn.init.zeros_(self.downsample.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.conv1(x)
        out = self.chomp1(out)
        out = self.relu1(out)
        out = self.drop1(out)

        out = self.conv2(out)
        out = self.chomp2(out)
        out = self.relu2(out)
        out = self.drop2(out)

        res = x if self.downsample is None else self.downsample(x)
        return self.out_relu(out + res)


class TCNClassifier(nn.Module):
    def __init__(
        self,
        in_dim: int,
        num_classes: int,
        channels: int = 64,
        levels: int = 3,
        kernel_size: int = 5,
        dropout: float = 0.3,
        use_proj: bool = True,
        proj_dim: Optional[int] = None,
    ) -> None:
        super().__init__()
        proj_dim = proj_dim or channels
        self.proj = nn.Identity()
        current_in = in_dim
        if use_proj and in_dim != proj_dim:
            self.proj = nn.Conv1d(in_dim, proj_dim, kernel_size=1)
            current_in = proj_dim

        blocks: List[nn.Module] = []
        for i in range(levels):
            dilation = 2 ** i
            blocks.append(
                TemporalBlock(
                    in_channels=current_in if i == 0 else channels,
                    out_channels=channels,
                    kernel_size=kernel_size,
                    dilation=dilation,
                    dropout=dropout,
                )
            )
        self.network = nn.Sequential(*blocks)
        self.classifier = nn.Linear(channels, num_classes)
        nn.init.kaiming_uniform_(self.classifier.weight, a=math.sqrt(5))
        if self.classifier.bias is not None:
            nn.init.zeros_(self.classifier.bias)

    def forward(self, x_btd: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        # x_btd: [B, T, D] -> [B, D, T]
        x = x_btd.transpose(1, 2)
        x = self.proj(x)
        x = self.network(x)
        # masked global average pooling over time
        b, c, t = x.shape
        mask = torch.arange(t, device=x.device).unsqueeze(0) < lengths.unsqueeze(1)
        mask = mask.unsqueeze(1)  # [B,1,T]
        x = x.masked_fill(~mask, 0.0)
        denom = lengths.clamp(min=1).unsqueeze(1).to(x.dtype)  # [B,1]
        pooled = x.sum(dim=2) / denom
        logits = self.classifier(pooled)
        return logits


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
    out_dir: Path = Path(__file__).resolve().parents[1] / "processed" / "train_utils" / "outputs"


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
    for X, y, lengths, _ in loader:
        X = X.to(device)
        y = y.to(device)
        lengths = lengths.to(device)
        logits = model(X, lengths)
        loss = criterion(logits, y)
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
    for X, y, lengths, _ in loader:
        X = X.to(device)
        y = y.to(device)
        lengths = lengths.to(device)
        logits = model(X, lengths)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a TCN classifier on NPZ sign-sequence features.")
    try:
        from train_model.dataset_versioning import get_splits_dir
        default_root = get_splits_dir()
    except Exception:
        default_root = Path(__file__).resolve().parents[1] / "processed" / "splits"
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
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--num_workers", type=int, default=0)
    parser.add_argument("--out_dir", type=Path, default=Path("processed/train_utils/outputs"))
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
    subset_mode = bool(dialects)

    # For subset runs, create a filtered copy of split CSVs and a local label mapping.
    # IMPORTANT: default behavior remains unchanged when no subset args are provided.
    features_root: Optional[Path] = None
    label_to_index_json: Optional[Path] = None
    subset_tag = ""
    if subset_mode:
        # Determine an absolute features root so generated CSVs can live anywhere.
        features_root = _find_features_root_from_csv(cfg.train_csv)
        if features_root is None:
            # Back-compat heuristic for the default layout: <root>/processed/splits/train.csv
            try:
                dataset_root = cfg.train_csv.resolve().parents[2]
                features_root = dataset_root / "features"
            except Exception:
                features_root = None
        if features_root is None or not features_root.exists():
            raise SystemExit("Subset mode requires locating the 'features' folder. Pass split CSVs from this repo layout.")

        subset_tag = _slugify(args.tag) if str(args.tag or "").strip() else _slugify("dialect-" + "+".join(dialects))
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
            rows = _filter_rows_by_dialect(rows, dialects)
            if not rows:
                raise SystemExit(f"Subset '{subset_tag}': {name} split is empty after filtering dialect={dialects}.")
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
    if ds_tmp.index_to_label:
        num_classes = len(ds_tmp.index_to_label)
    else:
        # fallback: scan labels from a subset of the train set
        label_set = set()
        n_scan = min(len(ds_tmp), 512)
        for i in range(n_scan):
            _, y_i, _ = ds_tmp[i]
            label_set.add(int(y_i))
        num_classes = max(label_set) + 1 if label_set else 1

    model = TCNClassifier(
        in_dim=in_dim,
        num_classes=num_classes,
        channels=cfg.channels,
        levels=cfg.levels,
        kernel_size=cfg.kernel_size,
        dropout=cfg.dropout,
    ).to(cfg.device)

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

    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=cfg.epochs)

    best_val_f1 = -1.0
    best_state = None
    patience = 10
    since_best = 0

    for epoch in range(1, cfg.epochs + 1):
        tr_loss, tr_acc = train_one_epoch(model, train_loader, opt, cfg.device)
        va_loss, va_acc, va_f1 = evaluate(model, val_loader, cfg.device, num_classes)
        scheduler.step()
        improved = va_f1 > best_val_f1
        if improved:
            best_val_f1 = va_f1
            best_state = {k: v.cpu() for k, v in model.state_dict().items()}
            since_best = 0
        else:
            since_best += 1

        print(
            f"epoch {epoch:03d} | train loss {tr_loss:.4f} acc {tr_acc:.4f} | val loss {va_loss:.4f} acc {va_acc:.4f} f1 {va_f1:.4f}"
        )
        if since_best >= patience:
            print("Early stopping: no improvement in validation F1.")
            break

    if best_state is not None:
        model.load_state_dict(best_state)  # type: ignore[arg-type]

    te_loss, te_acc, te_f1 = evaluate(model, test_loader, cfg.device, num_classes)
    # Note: SCS (Sequence Consistency Score) pertains to stability across consecutive window predictions.
    # This trainer produces one prediction per sequence, not per sliding window, so SCS is not applicable here.
    # We include it as None in the summary for compatibility with realtime/windowed evaluation.
    te_scs = None
    print(f"test loss {te_loss:.4f} acc {te_acc:.4f} f1 {te_f1:.4f}")

    # save
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"tcn_{stamp}" if not subset_mode else f"tcn_{subset_tag}_{stamp}"
    out_ckpt = cfg.out_dir / f"{prefix}.pt"
    label_map = ds_tmp.label_to_index or {}
    if not label_map:
        raise SystemExit("label_map is empty; ensure labels.csv or label_to_index.json is present and valid.")

    torch.save({
        "model_state": model.state_dict(),
        "config": asdict(cfg),
        "in_dim": in_dim,
        "feature_dim": in_dim,
        "num_classes": num_classes,
        "label_map": label_map,
        "subset": {"dialects": dialects, "language_default": args.language, "tag": subset_tag} if subset_mode else None,
        "label_to_index_json": str(label_to_index_json) if label_to_index_json else None,
        "metrics": {"test_acc": te_acc, "test_f1": te_f1, "test_scs": te_scs},
    }, out_ckpt)

    cfg_json = {
        k: (str(v) if isinstance(v, Path) else v)
        for k, v in asdict(cfg).items()
    }

    summary = {
        "timestamp": stamp,
        "subset": {"dialects": dialects, "language_default": args.language, "tag": subset_tag} if subset_mode else None,
        "config": cfg_json,
        "in_dim": in_dim,
        "feature_dim": in_dim,
        "num_classes": num_classes,
        "val_best_f1": best_val_f1,
        "test": {"loss": te_loss, "acc": te_acc, "f1": te_f1, "scs": te_scs},
        "checkpoint": str(out_ckpt),
    }

    (cfg.out_dir / f"{prefix}.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved checkpoint and summary to {cfg.out_dir}")


if __name__ == "__main__":
    main()
