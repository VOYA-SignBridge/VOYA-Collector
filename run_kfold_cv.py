#!/usr/bin/env python3
"""
K-fold cross-validation harness for the sign-language model suite.

Design decisions (see conversation 2026-07-05):
  * ADDITIVE: test.csv stays a fixed held-out set, evaluated once per fold.
    K-fold runs only over the pooled train.csv + val.csv rows.
  * Reuses the EXISTING training entry point (train_utils.train_tcn) as a
    subprocess, so every fold trains through the exact same pipeline,
    augmentation, and hyperparameters as a normal run. Nothing in the
    training code changes.
  * Identical fold splits are reused across every model, so a model-vs-model
    comparison is paired (same data per fold) and supports a paired
    significance test.

Two CV modes:
  * stratified  : StratifiedKFold on class label. Measures SAMPLE-level
                  generalization. NOTE: with few signers the same signer
                  appears in train and val, so this is NOT a signer-
                  independent estimate.
  * signer      : Leave-one-signer-group-out (StratifiedGroupKFold grouped by
                  user_id). Measures SIGNER-level generalization — the harder,
                  more honest benchmark. n_splits is capped at the number of
                  distinct signers.

Outputs mean +/- std across folds for val-best-F1, test-acc, test-F1, plus a
paired Wilcoxon test between models when more than one model is given.

Example:
    python run_kfold_cv.py --dialect hoa-de --model_type tcn --model_type cnn \\
        --n_splits 5 --mode stratified --epochs 80
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent
PROCESSED_DIR = REPO_ROOT / "processed"
SPLITS_DIR = PROCESSED_DIR / "splits"
FEATURES_ROOT = REPO_ROOT / "dataset" / "features"

# Column used to stratify (one class label per row) and to group by signer.
LABEL_COL = "label_key"
GROUP_COL = "user_id"


# ----------------------------------------------------------------------------
# Data pooling
# ----------------------------------------------------------------------------
def load_pooled_rows(
    dialects: Optional[List[str]],
    languages: Optional[List[str]],
) -> Tuple[List[dict], List[str]]:
    """Pool train.csv + val.csv, optionally filtered by dialect/language."""
    rows: List[dict] = []
    fieldnames: List[str] = []
    for name in ("train.csv", "val.csv"):
        path = SPLITS_DIR / name
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or fieldnames
            for r in reader:
                if dialects and (r.get("dialect") or "").strip() not in dialects:
                    continue
                if languages and (r.get("language") or "").strip() not in languages:
                    continue
                rows.append(r)
    return rows, fieldnames


# ----------------------------------------------------------------------------
# Fold construction
# ----------------------------------------------------------------------------
def build_folds(
    rows: List[dict],
    mode: str,
    n_splits: int,
    seed: int,
) -> List[Tuple[List[int], List[int]]]:
    """Return a list of (train_idx, val_idx) into `rows`, identical for all models."""
    y = [(_r.get(LABEL_COL) or "").strip() for _r in rows]

    if mode == "signer":
        from sklearn.model_selection import StratifiedGroupKFold

        groups = [(_r.get(GROUP_COL) or "").strip() for _r in rows]
        n_groups = len(set(groups))
        if n_splits > n_groups:
            print(
                f"[warn] mode=signer: only {n_groups} distinct signers; "
                f"capping n_splits {n_splits} -> {n_groups}."
            )
            n_splits = n_groups
        splitter = StratifiedGroupKFold(
            n_splits=n_splits, shuffle=True, random_state=seed
        )
        return [
            (list(tr), list(va)) for tr, va in splitter.split(rows, y, groups)
        ]

    # default: stratified on class
    from sklearn.model_selection import StratifiedKFold

    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    return [(list(tr), list(va)) for tr, va in splitter.split(rows, y)]


def write_fold_csv(path: Path, fieldnames: List[str], rows: List[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


# ----------------------------------------------------------------------------
# Single training run (one model, one fold) via the real training entry point
# ----------------------------------------------------------------------------
def run_one(
    model_type: str,
    fold_idx: int,
    train_csv: Path,
    val_csv: Path,
    out_dir: Path,
    args: argparse.Namespace,
) -> Optional[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "train_utils.train_tcn",
        f"--train_csv={train_csv}",
        f"--val_csv={val_csv}",
        f"--test_csv={SPLITS_DIR / 'test.csv'}",
        f"--features_root={FEATURES_ROOT}",
        f"--model_type={model_type}",
        f"--epochs={args.epochs}",
        f"--batch_size={args.batch_size}",
        f"--lr={args.lr}",
        f"--dropout={args.dropout}",
        f"--channels={args.channels}",
        f"--levels={args.levels}",
        f"--kernel_size={args.kernel_size}",
        f"--seed={args.seed}",
        f"--out_dir={out_dir}",
        f"--tag=fold{fold_idx}",
    ]
    for d in (args.dialect or []):
        cmd.append(f"--dialect={d}")
    for l in (args.filter_language or []):
        cmd.append(f"--filter_language={l}")

    proc = subprocess.run(
        cmd, cwd=str(PROCESSED_DIR), capture_output=True, text=True
    )
    if proc.returncode != 0:
        print(f"[FAIL] {model_type} fold {fold_idx} (exit {proc.returncode})")
        tail = "\n".join(proc.stdout.strip().splitlines()[-8:])
        err = "\n".join(proc.stderr.strip().splitlines()[-8:])
        if tail:
            print("  stdout:", tail.replace("\n", "\n          "))
        if err:
            print("  stderr:", err.replace("\n", "\n          "))
        return None

    # The training script writes exactly one summary json to out_dir root
    # (label-map jsons live in a subset_* subdir, so a non-recursive glob is safe).
    summaries = [
        p for p in out_dir.glob("*.json")
        if _looks_like_summary(p)
    ]
    if not summaries:
        print(f"[FAIL] {model_type} fold {fold_idx}: no summary json found")
        return None
    summary = json.loads(summaries[0].read_text(encoding="utf-8"))
    return {
        "val_best_f1": float(summary.get("val_best_f1", 0.0)),
        "test_acc": float(summary.get("test", {}).get("acc", 0.0)),
        "test_f1": float(summary.get("test", {}).get("f1", 0.0)),
    }


def _looks_like_summary(p: Path) -> bool:
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        return "val_best_f1" in obj and "test" in obj
    except Exception:
        return False


# ----------------------------------------------------------------------------
# Aggregation + reporting
# ----------------------------------------------------------------------------
def summarize(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = statistics.fmean(values)
    std = statistics.pstdev(values) if len(values) > 1 else 0.0
    return mean, std


def main() -> int:
    parser = argparse.ArgumentParser(description="K-fold CV harness (additive to fixed test holdout).")
    parser.add_argument("--dialect", action="append", default=None,
                        help="Filter to dialect(s). Repeat for multiple. E.g. --dialect hoa-de")
    parser.add_argument("--filter_language", action="append", default=None)
    parser.add_argument("--model_type", action="append", default=None,
                        help="Model(s) to evaluate. Repeat to compare. Default: tcn")
    parser.add_argument("--mode", choices=["stratified", "signer"], default="stratified")
    parser.add_argument("--n_splits", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--channels", type=int, default=64)
    parser.add_argument("--levels", type=int, default=3)
    parser.add_argument("--kernel_size", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out_root", type=Path, default=None,
                        help="Where to write fold outputs. Default: a temp dir.")
    args = parser.parse_args()

    models = args.model_type or ["tcn"]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_root = args.out_root or Path(tempfile.gettempdir()) / f"kfold_{stamp}"
    out_root.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("  K-FOLD CROSS-VALIDATION  (test.csv held out, evaluated per fold)")
    print("=" * 78)
    print(f"  Dialect(s):   {args.dialect or 'ALL'}")
    print(f"  Models:       {models}")
    print(f"  Mode:         {args.mode}")
    print(f"  Folds:        {args.n_splits}")
    print(f"  Epochs/fold:  {args.epochs}")
    print(f"  Output:       {out_root}")

    rows, fieldnames = load_pooled_rows(args.dialect, args.filter_language)
    print(f"\n  Pooled train+val samples: {len(rows)}")
    n_classes = len({(_r.get(LABEL_COL) or '').strip() for _r in rows})
    n_signers = len({(_r.get(GROUP_COL) or '').strip() for _r in rows})
    print(f"  Classes: {n_classes} | Signers: {n_signers}")
    if args.mode == "stratified" and n_signers <= 3:
        print(f"  [note] Only {n_signers} signers -> stratified folds share signers "
              f"between train/val (sample-level generalization, not signer-level).")

    folds = build_folds(rows, args.mode, args.n_splits, args.seed)
    print(f"  Built {len(folds)} folds.\n")

    # model -> metric -> list over folds
    results: Dict[str, Dict[str, List[float]]] = {
        m: {"val_best_f1": [], "test_acc": [], "test_f1": []} for m in models
    }

    for fold_idx, (tr, va) in enumerate(folds):
        tr_rows = [rows[i] for i in tr]
        va_rows = [rows[i] for i in va]
        fold_dir = out_root / f"fold{fold_idx}"
        fold_dir.mkdir(parents=True, exist_ok=True)
        train_csv = fold_dir / "train.csv"
        val_csv = fold_dir / "val.csv"
        write_fold_csv(train_csv, fieldnames, tr_rows)
        write_fold_csv(val_csv, fieldnames, va_rows)
        print(f"Fold {fold_idx}: train={len(tr_rows)} val={len(va_rows)}")

        for m in models:
            res = run_one(m, fold_idx, train_csv, val_csv,
                          fold_dir / f"out_{m}", args)
            if res is None:
                continue
            for k in ("val_best_f1", "test_acc", "test_f1"):
                results[m][k].append(res[k])
            print(f"  {m:18} val_f1={res['val_best_f1']:.4f} "
                  f"test_acc={res['test_acc']:.4f} test_f1={res['test_f1']:.4f}")

    # ---- report ----
    print("\n" + "=" * 78)
    print("  CROSS-VALIDATION SUMMARY  (mean +/- std over folds)")
    print("=" * 78)
    print(f"{'Model':<18} {'Val F1':<18} {'Test Acc':<18} {'Test F1':<18}")
    print("-" * 78)
    report = {}
    for m in models:
        vf_m, vf_s = summarize(results[m]["val_best_f1"])
        ta_m, ta_s = summarize(results[m]["test_acc"])
        tf_m, tf_s = summarize(results[m]["test_f1"])
        report[m] = {
            "val_best_f1": {"mean": vf_m, "std": vf_s, "folds": results[m]["val_best_f1"]},
            "test_acc": {"mean": ta_m, "std": ta_s, "folds": results[m]["test_acc"]},
            "test_f1": {"mean": tf_m, "std": tf_s, "folds": results[m]["test_f1"]},
        }
        print(f"{m:<18} {vf_m*100:6.2f} +/- {vf_s*100:4.2f}%   "
              f"{ta_m*100:6.2f} +/- {ta_s*100:4.2f}%   "
              f"{tf_m*100:6.2f} +/- {tf_s*100:4.2f}%")

    # ---- paired significance between models (on test_f1) ----
    sig = {}
    if len(models) >= 2:
        print("\n" + "-" * 78)
        print("  Paired comparison on test-F1 (same folds) — Wilcoxon signed-rank")
        print("-" * 78)
        try:
            from scipy.stats import wilcoxon
            for i in range(len(models)):
                for j in range(i + 1, len(models)):
                    a, b = models[i], models[j]
                    xa, xb = results[a]["test_f1"], results[b]["test_f1"]
                    if len(xa) == len(xb) and len(xa) >= 3 and any(
                        x != y for x, y in zip(xa, xb)
                    ):
                        stat, p = wilcoxon(xa, xb)
                        verdict = "significant" if p < 0.05 else "n.s."
                        sig[f"{a}_vs_{b}"] = {"p": p, "verdict": verdict}
                        print(f"  {a} vs {b}: p={p:.4f} ({verdict})")
                    else:
                        print(f"  {a} vs {b}: not enough distinct paired samples for a test")
        except Exception as e:
            print(f"  [skip] significance test unavailable: {e}")

    out_json = out_root / "kfold_results.json"
    out_json.write_text(json.dumps({
        "timestamp": stamp,
        "config": {
            "dialect": args.dialect, "mode": args.mode, "n_splits": len(folds),
            "epochs": args.epochs, "models": models, "seed": args.seed,
            "pooled_samples": len(rows), "classes": n_classes, "signers": n_signers,
        },
        "results": report,
        "significance": sig,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
