from __future__ import annotations

import argparse
import csv
import json
import math
import os
import platform
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
    from .augmentation import build_train_augment, augment_config_dict
except Exception:
    import sys
    from pathlib import Path as _P
    sys.path.append(str(_P(__file__).resolve().parents[2]))
    from processed.train_utils.augmentation import build_train_augment, augment_config_dict

try:
    from processed.shared.vocabulary import (
        RECOGNITION_PROFILES,
        check_label_collisions,
        label_key_v2,
        select_rows_for_profile,
        split_common_and_profile_labels,
    )
except Exception:
    import sys as _sys
    from pathlib import Path as _P
    _sys.path.append(str(_P(__file__).resolve().parents[2]))
    from processed.shared.vocabulary import (
        RECOGNITION_PROFILES,
        check_label_collisions,
        label_key_v2,
        select_rows_for_profile,
        split_common_and_profile_labels,
    )

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


def _git_commit_hash() -> str:
    """Best-effort HEAD commit for the checkpoint contract ('' if unavailable).

    Falls back to parsing .git/HEAD directly — training containers usually
    have the repo mounted but no git binary installed.
    """
    repo_root = Path(__file__).resolve().parents[2]
    try:
        import subprocess
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=str(repo_root),
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    try:
        head = (repo_root / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(None, 1)[1].strip()
            ref_file = repo_root / ".git" / ref
            if ref_file.exists():
                return ref_file.read_text(encoding="utf-8").strip()
            packed = repo_root / ".git" / "packed-refs"
            if packed.exists():
                for line in packed.read_text(encoding="utf-8").splitlines():
                    if line.endswith(ref):
                        return line.split()[0]
            return ""
        return head
    except Exception:
        return ""


def _read_split_manifest_checksum(train_csv: Path) -> str:
    """Read dataset_manifest_checksum from split_metadata.json next to the
    split CSVs (written by make_splits manifest mode). '' when absent."""
    try:
        meta_path = Path(train_csv).resolve().parent / "split_metadata.json"
        if meta_path.exists():
            return str(json.loads(meta_path.read_text(encoding="utf-8")).get(
                "dataset_manifest_checksum", ""))
    except Exception:
        pass
    return ""


CUBLAS_DETERMINISTIC_CONFIG = ":4096:8"


def _enforce_augmentation_contract(aug_cfg: dict, run_purpose: str) -> None:
    """Refuse to train on an augmentation config that cannot be trusted.

    Guards the three ways the augmentation contract can silently go wrong:
      1. the config carries no contract version at all;
      2. the mirror implementation drifts from the wrist-centered reflection
         the contract promises;
      3. temporal masking is switched back on while the model input has no
         frame-validity channel to disambiguate a masked frame from a padded
         one or from "both hands absent".
    """
    from processed.train_utils.augmentation import (
        AUGMENTATION_CONTRACT_VERSION, SignAugment,
    )

    def _fail(msg: str) -> None:
        if run_purpose == "research":
            raise SystemExit(f"[AUGMENT][CONTRACT] {msg}")
        print(f"[AUGMENT][CONTRACT][WARN] {msg}")

    if not aug_cfg.get("enabled", False):
        return

    version = str(aug_cfg.get("augmentation_contract_version") or "")
    if not version:
        _fail("augmentation config carries no augmentation_contract_version; "
              "the run would not be attributable to a mirror implementation.")
    elif version != AUGMENTATION_CONTRACT_VERSION:
        _fail(f"augmentation_contract_version '{version}' != code version "
              f"'{AUGMENTATION_CONTRACT_VERSION}'.")

    # Behavioural check: reflect a synthetic wrist-centered hand and verify the
    # wrist stays at the origin and the span is preserved. Catches a mirror
    # implementation that drifted back to the image-space form.
    probe = np.zeros((60, 126), dtype=np.float32)
    hand = np.linspace(0.05, 0.35, 21 * 3).astype(np.float32).reshape(21, 3)
    hand[0, 0] = 0.0
    hand[0, 1] = 0.0
    probe[:, :63] = hand.reshape(-1)
    mirrored = SignAugment(
        p=1.0, noise_std=0.0, scale_range=(1.0, 1.0), translation_std=0.0,
        dropout_prob=0.0, temporal_mask_prob=0.0, temporal_jitter_prob=0.0,
        mirror_prob=1.0, max_temporal_shift=0,
    )(probe).reshape(60, 2, 21, 3)
    src_x = hand[:, 0]
    dst_x = mirrored[0, 1, :, 0]  # slots are swapped by the mirror
    if abs(float(dst_x[0])) > 1e-6:
        _fail(f"mirror moved the wrist off the origin (x={float(dst_x[0]):.4f}); "
              f"implementation does not match the wrist-centered contract.")
    span_src = float(src_x.max() - src_x.min())
    span_dst = float(dst_x.max() - dst_x.min())
    if span_src > 1e-6 and abs(span_dst / span_src - 1.0) > 1e-3:
        _fail(f"mirror changed hand span by {span_dst / span_src:.2f}x; "
              f"expected an isometry.")

    if float(aug_cfg.get("temporal_mask_prob", 0.0)) > 0.0:
        _fail("temporal_mask_prob > 0 but the model input has no frame-validity "
              "channel: a masked frame is indistinguishable from padding and "
              "from a both-hands-absent frame.")


def _enforce_research_preconditions(args, cfg, manifest_checksum: str) -> None:
    """--run-purpose research: provenance and split validity must hold BEFORE
    a long training run burns compute and produces an uncitable checkpoint."""
    problems = []
    if not str(args.dataset_version or "").strip():
        problems.append("--dataset_version is empty")
    if not str(args.split_version or "").strip():
        problems.append("--split_version is empty")
    if not manifest_checksum:
        problems.append("no dataset_manifest_checksum found next to the split "
                        "(generate splits with make_splits.py --dataset_manifest ...)")
    if not _git_commit_hash():
        problems.append("git commit hash unavailable; run provenance cannot be pinned")

    meta_path = Path(cfg.train_csv).resolve().parent / "split_metadata.json"
    if not meta_path.exists():
        # cfg.train_csv may already point at the filtered copy in run_dir
        meta_path = Path(args.train_csv).resolve().parent / "split_metadata.json"
    if not meta_path.exists():
        problems.append(f"split_metadata.json not found next to {args.train_csv}")
    else:
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:
            problems.append(f"split_metadata.json unreadable: {exc}")
            meta = {}
        if "valid_for_research" not in meta:
            problems.append("split_metadata.json predates the validity gate "
                            "(no valid_for_research field) — regenerate the split")
        elif not meta.get("valid_for_research"):
            reasons = "; ".join(meta.get("invalid_reasons") or ["unspecified"])
            problems.append(f"split is not valid for research: {reasons}")

    if problems:
        detail = "\n  - ".join(problems)
        raise SystemExit(
            f"[RESEARCH] refusing to start a research run:\n  - {detail}\n"
            f"Fix the above, or use --run-purpose smoke_test for an exploratory run.")
    print("[RESEARCH] preconditions OK — provenance and split validity verified.")


def set_seed(seed: int, *, strict: bool = False, mode: str = "strict") -> dict:
    """Seed every RNG and request deterministic kernels.

    Returns a report describing what was actually achieved, so callers (and the
    checkpoint) can record whether the run was genuinely deterministic instead
    of assuming it. With strict=True a failure to enable deterministic
    algorithms raises instead of degrading silently.

    mode="fast" seeds every RNG exactly the same but leaves kernel selection
    free. Chỉ dành cho run thăm dò: cuDNN phải dùng thuật toán backward
    deterministic cho dilated Conv1d, và trên GPU này nó chậm hơn ~170 lần
    (4 ms -> 750 ms mỗi batch với TCN). Chế độ đã dùng luôn được ghi vào
    checkpoint nên không thể nhầm run thăm dò với run cho bài báo.

    NOTE: on CUDA, torch requires CUBLAS_WORKSPACE_CONFIG to be set BEFORE the
    CUDA context is created. Setting it here is already too late if a tensor
    has been allocated; scripts/verify_determinism.py sets it in the child
    environment before launching.
    """
    os.environ.setdefault("PYTHONHASHSEED", str(seed))
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    cublas_cfg = os.environ.get("CUBLAS_WORKSPACE_CONFIG", "")
    using_cuda = torch.cuda.is_available()
    fast_mode = str(mode).lower() == "fast"

    torch.backends.cudnn.deterministic = not fast_mode
    torch.backends.cudnn.benchmark = fast_mode

    report = {
        "seed": int(seed),
        "mode": "fast" if fast_mode else "strict",
        "cudnn_deterministic": not fast_mode,
        "cublas_workspace_config": cublas_cfg,
        "deterministic_algorithms": False,
        "warnings": [],
    }

    if fast_mode:
        msg = (
            "determinism=fast: kernel không deterministic, kết quả KHÔNG tái lập "
            "bit-for-bit. Chỉ dùng cho run thăm dò, không dùng cho số liệu bài báo."
        )
        report["warnings"].append(msg)
        print(f"[DETERMINISM][WARN] {msg}")
        return report

    if using_cuda and cublas_cfg not in (":4096:8", ":16:8"):
        msg = (
            "CUDA is available but CUBLAS_WORKSPACE_CONFIG is not set to "
            f"'{CUBLAS_DETERMINISTIC_CONFIG}' (got {cublas_cfg!r}); cuBLAS matmuls "
            "may be non-deterministic across runs."
        )
        if strict:
            raise RuntimeError(msg)
        report["warnings"].append(msg)
        print(f"[DETERMINISM][WARN] {msg}")

    try:
        torch.use_deterministic_algorithms(True)
        report["deterministic_algorithms"] = True
    except Exception as exc:
        msg = f"torch.use_deterministic_algorithms(True) failed: {exc}"
        if strict:
            raise RuntimeError(msg) from exc
        report["warnings"].append(msg)
        # Loud, not silent: a swallowed failure here silently invalidates any
        # reproducibility claim made about the run.
        print(f"[DETERMINISM][WARN] {msg}")

    return report


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
    contract_extra: Optional[Dict[str, object]] = None,
):
    ckpt = {
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
            # Persist the temporal pooling so realtime rebuilds the exact head.
            "temporal_pool": getattr(model, "temporal_pool", "gap"),
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
    if contract_extra:
        ckpt.update(contract_extra)
    return ckpt

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
        help="[DEPRECATED — legacy experiments only] filter by legacy dialect column. "
             "New experiments must use --recognition_profile / --unified.",
    )
    # --- Vocabulary schema v2: recognition-profile training ---
    parser.add_argument(
        "--recognition_profile",
        type=str,
        default="",
        choices=["", *RECOGNITION_PROFILES],
        help="Train a profile model: common vocabulary + this profile's vocabulary. "
             "One of: " + ", ".join(RECOGNITION_PROFILES),
    )
    parser.add_argument(
        "--include_common", dest="include_common", action="store_true", default=False,
        help="EXPLICITLY include common vocabulary in the profile model. "
             "Default: false — profiles (including the standalone 'alphabet') train independently.",
    )
    parser.add_argument("--no_include_common", dest="include_common", action="store_false",
                        help="[kept for compatibility — no-op now that the default is false]")
    parser.add_argument(
        "--unified", action="store_true",
        help="Unified baseline: common + every validly-assigned profile (mutually exclusive with --recognition_profile)",
    )
    parser.add_argument("--dataset_version", type=str, default="unversioned",
                        help="Dataset manifest version this run trains on (goes into output path + checkpoint)")
    parser.add_argument("--split_version", type=str, default="unversioned",
                        help="Split version identifier (goes into output path + checkpoint)")
    parser.add_argument(
        "--augmentation_profile", type=str, default="full",
        choices=["none", "spatial", "temporal", "full"],
        help="Train-time augmentation profile (validation/test are never augmented)",
    )
    parser.add_argument(
        "--aug_set", action="append", default=None, metavar="KEY=VALUE",
        help="Override an augmentation parameter, e.g. --aug_set mirror_probability=0.0 (repeatable)",
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
    parser.add_argument(
        "--temporal_pool", type=str, default="attention",
        choices=["gap", "attention", "mean_max"],
        help="TCN time-axis aggregation. 'attention' (default) keeps temporal "
             "order — better for dynamic multi-action phrases; 'gap' is the legacy "
             "order-agnostic average (only for reproducing old runs).",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--run-purpose", dest="run_purpose", type=str, default="smoke_test",
        choices=["smoke_test", "research"],
        help="Declare what this run is for. Defaults to smoke_test so an "
             "exploratory run can NEVER drift into a paper table: "
             "aggregate_experiment_results.py only reports run_purpose=research. "
             "Pass --run-purpose research for an official experiment; it also "
             "enforces provenance and split validity before training starts.",
    )
    parser.add_argument(
        "--determinism", type=str, default="strict", choices=["strict", "fast"],
        help="strict (mặc định): kernel deterministic, tái lập bit-for-bit — dùng "
             "cho mọi số liệu đưa vào bài báo. fast: bỏ ràng buộc kernel, TCN nhanh "
             "hơn ~170 lần nhưng KHÔNG tái lập; chỉ dùng để thử nghiệm. Chế độ được "
             "ghi vào checkpoint (determinism.mode).",
    )
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

    if args.determinism == "fast" and args.run_purpose == "research":
        raise SystemExit(
            "[RESEARCH] --determinism=fast không dùng được với --run-purpose research: "
            "số liệu bài báo phải tái lập bit-for-bit."
        )
    determinism_report = set_seed(cfg.seed, mode=args.determinism)
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    dialects = _parse_multi_values(args.dialect)
    languages = _parse_multi_values(args.filter_language)

    profile_mode = bool(args.recognition_profile or args.unified)
    if args.unified and args.recognition_profile:
        raise SystemExit("--unified and --recognition_profile are mutually exclusive.")
    if profile_mode and (dialects or languages):
        raise SystemExit("--recognition_profile/--unified cannot be combined with the "
                         "deprecated --dialect/--filter_language flags.")
    if dialects:
        print("[DEPRECATED] --dialect is a legacy-compatibility flag. New experiments "
              "must use --recognition_profile or --unified (vocabulary schema v2).")

    # Parse augmentation overrides (KEY=VALUE)
    aug_overrides: Dict[str, object] = {}
    for kv in (args.aug_set or []):
        if "=" not in kv:
            raise SystemExit(f"--aug_set expects KEY=VALUE, got '{kv}'")
        k, v = kv.split("=", 1)
        try:
            aug_overrides[k.strip()] = float(v)
        except ValueError:
            raise SystemExit(f"--aug_set value must be numeric: '{kv}'")

    subset_mode = bool(dialects or languages)

    # For subset runs, create a filtered copy of split CSVs and a local label mapping.
    # IMPORTANT: default behavior remains unchanged when no subset args are provided.
    features_root: Optional[Path] = None
    label_to_index_json: Optional[Path] = None
    subset_tag = ""
    subset_dir: Optional[Path] = None
    common_labels: List[str] = []
    profile_specific_labels: List[str] = []
    manifest_checksum = ""
    motion_types_present: List[str] = []

    if profile_mode:
        # ------------------------------------------------------------------
        # Vocabulary schema v2: common + selected profile (or unified).
        # Split CSVs must carry vocabulary_scope/recognition_profile columns
        # (produced by make_splits --dataset_manifest ...).
        # ------------------------------------------------------------------
        features_root = (args.features_root if args.features_root is not None
                         else _find_features_root_from_csv(cfg.train_csv))
        if features_root is None:
            try:
                dataset_root = cfg.train_csv.resolve().parents[2]
                features_root = dataset_root / "dataset" / "features"
            except Exception:
                features_root = None
        if features_root is None or not features_root.exists():
            raise SystemExit("Profile mode requires locating the 'features' folder.")

        profile_tag = "unified" if args.unified else args.recognition_profile
        subset_tag = profile_tag
        run_dir = (args.out_dir / args.dataset_version / profile_tag /
                   args.split_version / args.model_type / f"seed_{args.seed}")
        run_dir.mkdir(parents=True, exist_ok=True)
        subset_dir = run_dir
        # Capture the manifest checksum from the ORIGINAL split dir before
        # cfg.train_csv is repointed at the filtered copy in run_dir.
        manifest_checksum = _read_split_manifest_checksum(cfg.train_csv)

        def _prep_profile_csv(src_csv: Path, name: str) -> Path:
            rows, fieldnames = _read_csv_rows(src_csv)
            if rows and "vocabulary_scope" not in rows[0]:
                raise SystemExit(
                    f"{name} split CSV has no vocabulary schema v2 columns "
                    f"(vocabulary_scope/recognition_profile). Generate splits with "
                    f"make_splits.py --dataset_manifest ... first: {src_csv}")
            rows = select_rows_for_profile(
                rows,
                recognition_profile=(args.recognition_profile or None),
                include_common=args.include_common,
                unified=args.unified,
            )
            if not rows:
                raise SystemExit(f"Profile '{profile_tag}': {name} split empty after filtering.")
            for r in rows:
                r["label_key"] = label_key_v2(
                    r.get("language") or "vn", r.get("vocabulary_scope") or "",
                    r.get("recognition_profile") or "",
                    r.get("slug") or r.get("label_slug") or "")
                if not (r.get("label_slug") or "").strip():
                    r["label_slug"] = (r.get("slug") or "").strip()
            collisions = check_label_collisions(rows)
            if collisions:
                raise SystemExit(f"Label collision between common and profile-specific "
                                 f"vocabulary: {collisions} — resolve before training.")
            fieldnames = _ensure_cols(fieldnames, ["label_key", "label_slug", "label_original"])
            rows = _filter_rows_with_existing_features(
                rows, features_root=features_root, default_language="vn", label=f"{name} split")
            if not rows:
                raise SystemExit(f"Profile '{profile_tag}': {name} split empty after "
                                 f"removing missing feature files.")
            out_csv = run_dir / f"{name}.csv"
            _write_csv_rows(out_csv, rows, fieldnames)
            return out_csv

        sub_train = _prep_profile_csv(cfg.train_csv, "train")
        sub_val = _prep_profile_csv(cfg.val_csv, "val")
        sub_test = _prep_profile_csv(cfg.test_csv, "test")

        train_rows, _ = _read_csv_rows(sub_train)
        l2i, i2l = _build_subset_label_maps(train_rows, default_language="vn")
        if len(l2i) < 2:
            raise SystemExit(f"Profile '{profile_tag}': need at least 2 classes, got {len(l2i)}.")
        common_labels, profile_specific_labels = split_common_and_profile_labels(list(l2i.keys()))

        # Hard cross-profile guard: a profile checkpoint must never contain
        # another profile's labels (alphabet vs regional vs hoa_de isolation).
        if not args.unified:
            allowed = {f"vn/{args.recognition_profile}/"}
            if args.include_common:
                allowed.add("vn/common/")
            foreign = [k for k in l2i if not any(k.startswith(p) for p in allowed)]
            assert not foreign, (
                f"Cross-profile label leak into '{profile_tag}' label space: {foreign[:5]}")

        # Motion types present in this label space (checkpoint contract field).
        motion_types_present = sorted(
            {(r.get("motion_type") or "").strip() or "unknown" for r in train_rows})

        def _filter_profile_known(src_csv: Path, name: str) -> None:
            rows, fieldnames = _read_csv_rows(src_csv)
            before = len(rows)
            rows = [r for r in rows if (r.get("label_key") or "").strip() in l2i]
            if before - len(rows) > 0:
                print(f"Profile '{profile_tag}': removed {before - len(rows)} rows "
                      f"from {name} due to labels unseen in train.")
            if not rows:
                raise SystemExit(f"Profile '{profile_tag}': {name} split became empty.")
            _write_csv_rows(src_csv, rows, fieldnames)

        _filter_profile_known(sub_val, "val")
        _filter_profile_known(sub_test, "test")

        label_to_index_json = run_dir / "label_to_index.json"
        (run_dir / "label_to_index.json").write_text(
            json.dumps(l2i, indent=2, ensure_ascii=False), encoding="utf-8")
        (run_dir / "index_to_label.json").write_text(
            json.dumps({str(k): v for k, v in i2l.items()}, indent=2, ensure_ascii=False),
            encoding="utf-8")

        cfg.train_csv, cfg.val_csv, cfg.test_csv = sub_train, sub_val, sub_test
        cfg.out_dir = run_dir
        subset_mode = True  # reuse downstream subset bookkeeping (tag/summary/tracking)
        print(f"[PROFILE] {profile_tag}: common={len(common_labels)} "
              f"profile_specific={len(profile_specific_labels)} classes={len(l2i)}")

    if subset_mode and not profile_mode:
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
            "temporal_pool": args.temporal_pool,  # TCN only; others ignore it
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

    train_augment = build_train_augment(args.augmentation_profile, aug_overrides)
    augmentation_config = augment_config_dict(args.augmentation_profile, aug_overrides)
    print(f"[AUGMENT] profile={args.augmentation_profile} overrides={aug_overrides or '{}'}")

    _enforce_augmentation_contract(augmentation_config, args.run_purpose)
    if args.run_purpose == "research":
        _enforce_research_preconditions(args, cfg, manifest_checksum)

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

    # C13: test metrics must come from the restored best-validation state, and
    # the checkpoint must SAY so rather than leaving it to be assumed.
    restored_best_state = best_state is not None
    if restored_best_state:
        model.load_state_dict(best_state)  # type: ignore[arg-type]
    else:
        print("[WARN] no best-validation state was captured; test metrics come from "
              "the final epoch. This run is NOT research-valid (C13).")
    model_selection = {
        "criterion": "val_macro_f1",
        "restored_best_state": bool(restored_best_state),
        "best_epoch": int(_best_epoch_track),
        "best_val_f1": float(best_val_f1),
        "best_val_acc": float(_best_val_acc_track),
        "early_stopping_patience": int(patience),
    }

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
    cfg_json_for_ckpt = {k: (str(v) if isinstance(v, Path) else v) for k, v in asdict(cfg).items()}
    contract_extra = {
        "vocabulary_schema_version": "v2" if profile_mode else "v1_legacy",
        "recognition_profile": (args.recognition_profile or ("unified" if args.unified else "")),
        "include_common": bool(args.include_common),
        "unified": bool(args.unified),
        "dataset_version": args.dataset_version,
        "split_version": args.split_version,
        "preprocess_contract_version": "v2",
        "storage_contract_version": "npz_v2",
        "motion_types_present": motion_types_present,
        "common_labels": common_labels,
        "profile_specific_labels": profile_specific_labels,
        "seed": int(cfg.seed),
        "run_purpose": args.run_purpose,
        "run_status": "completed",
        "model_selection": model_selection,
        "determinism": determinism_report,
        "runtime_env": {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "pytorch_version": str(torch.__version__),
            "numpy_version": np.__version__,
            "cuda_version": torch.version.cuda or "none",
            "cudnn_version": (torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else None),
            "device": cfg.device,
            "platform": platform.platform(),
        },
        "git_commit": _git_commit_hash(),
        "training_config": {**cfg_json_for_ckpt, "model_type": args.model_type,
                            "augmentation": augmentation_config},
        "dataset_manifest_checksum": manifest_checksum or _read_split_manifest_checksum(cfg.train_csv),
    }
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
        contract_extra=contract_extra,
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
            "pytorch_version": str(torch.__version__),
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
        "vocabulary_schema_version": contract_extra["vocabulary_schema_version"],
        "recognition_profile": contract_extra["recognition_profile"],
        "dataset_version": args.dataset_version,
        "split_version": args.split_version,
        "git_commit": contract_extra["git_commit"],
        "augmentation": augmentation_config,
        "dataset_manifest_checksum": contract_extra["dataset_manifest_checksum"],
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
