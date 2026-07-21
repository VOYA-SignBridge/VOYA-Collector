"""Aggregate experiment results into a CSV + LaTeX table, purely from artifacts.

Reads ONLY files on disk — never a database, never a live service:
  <out_dir>/<dataset_version>/<profile>/<split_version>/<model>/seed_<n>/
      *.pt                     checkpoint contract (metrics, seed, git commit,
                               augmentation config, manifest checksum)
      *.json                   run summary written next to the checkpoint
  processed/splits/versions/<split_version>/split_metadata.json
                               split mode, signer assignment, class coverage
  dataset/manifests/dataset_stats_<dataset_version>.json
                               sample counts for the dataset version

Every emitted row carries research_valid (see scripts/audit_checkpoint_validity.py):
runs trained with the pre-2026-07-21 image-space mirror are marked and, unless
--include-invalid is passed, kept OUT of the LaTeX table so a broken run cannot
silently reach the paper.

Usage:
    python scripts/aggregate_experiment_results.py
    python scripts/aggregate_experiment_results.py --out-dir reports \
        --group-by profile --include-invalid
"""

from __future__ import annotations

import sys as _sys
sys_path_dir = __import__('pathlib').Path(__file__).resolve().parent
if str(sys_path_dir) not in _sys.path:
    _sys.path.insert(0, str(sys_path_dir))
import _console  # noqa: F401  (force UTF-8 console on Windows)

import argparse
import csv
import json
import statistics
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(REPO_ROOT))

from research_validity import (  # noqa: E402  (THE shared verdict logic)
    RUN_PURPOSE_RESEARCH,
    evaluate_checkpoint,
    load_split_metadata,
    run_purpose_of,
)

COLUMNS = [
    "run_id", "research_valid", "invalid_reasons", "run_purpose",
    "split_valid_for_research",
    "recognition_profile", "unified", "include_common",
    "dataset_version", "split_version", "split_mode", "model_type", "seed",
    "num_classes", "n_train", "n_val", "n_test",
    "test_acc", "test_f1", "val_best_f1",
    "augmentation_profile", "augmentation_contract_version", "mirror_prob",
    "epochs", "batch_size", "lr", "device",
    "git_commit", "dataset_manifest_checksum",
    "signers_train", "signers_val", "signers_test",
    "checkpoint_path",
]


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _split_metadata(split_version: str) -> dict:
    if not split_version:
        return {}
    return _load_json(
        REPO_ROOT / "processed" / "splits" / "versions" / split_version / "split_metadata.json"
    )


def collect(outputs_root: Path) -> list[dict]:
    try:
        import torch
    except ImportError:
        print("[ERROR] torch is required to read checkpoints.")
        raise SystemExit(2)

    rows: list[dict] = []
    for ckpt_path in sorted(outputs_root.rglob("*.pt")):
        try:
            ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        except Exception as exc:
            print(f"[WARN] unreadable checkpoint skipped: {ckpt_path.name} ({exc})")
            continue

        # Only contract-v2 runs are aggregatable; legacy checkpoints lack the
        # provenance needed for a paper table and are reported by
        # audit_checkpoint_validity.py instead.
        if "recognition_profile" not in ckpt:
            continue

        summary = _load_json(ckpt_path.with_suffix(".json"))
        tc = ckpt.get("training_config") if isinstance(ckpt.get("training_config"), dict) else {}
        aug = tc.get("augmentation") if isinstance(tc.get("augmentation"), dict) else {}
        metrics = ckpt.get("metrics") if isinstance(ckpt.get("metrics"), dict) else {}
        split_version = str(ckpt.get("split_version") or "")
        smeta = _split_metadata(split_version)
        counts = smeta.get("counts") or {}
        signers = smeta.get("signers") or {}
        verdict = evaluate_checkpoint(ckpt, split_meta=smeta or None)

        rows.append({
            "run_id": ckpt_path.stem,
            "research_valid": verdict.label,
            "invalid_reasons": "; ".join(verdict.reasons),
            "run_purpose": run_purpose_of(ckpt) or "",
            "split_valid_for_research": smeta.get("valid_for_research", ""),
            "recognition_profile": ckpt.get("recognition_profile") or "",
            "unified": ckpt.get("unified", ""),
            "include_common": ckpt.get("include_common", ""),
            "dataset_version": ckpt.get("dataset_version") or "",
            "split_version": split_version,
            "split_mode": smeta.get("split_mode", ""),
            "model_type": ckpt.get("model_type") or "",
            "seed": ckpt.get("seed", ""),
            "num_classes": ckpt.get("num_classes", ""),
            "n_train": counts.get("train", ""),
            "n_val": counts.get("val", ""),
            "n_test": counts.get("test", ""),
            "test_acc": metrics.get("test_acc", ""),
            "test_f1": metrics.get("test_f1", ""),
            "val_best_f1": summary.get("val_best_f1", ""),
            "augmentation_profile": aug.get("profile", ""),
            "augmentation_contract_version": aug.get("augmentation_contract_version", ""),
            "mirror_prob": aug.get("mirror_prob", ""),
            "epochs": tc.get("epochs", ""),
            "batch_size": tc.get("batch_size", ""),
            "lr": tc.get("lr", ""),
            "device": tc.get("device", ""),
            "git_commit": (ckpt.get("git_commit") or "")[:8],
            "dataset_manifest_checksum": (ckpt.get("dataset_manifest_checksum") or "")[:12],
            "signers_train": len(signers.get("train") or []),
            "signers_val": len(signers.get("val") or []),
            "signers_test": len(signers.get("test") or []),
            "checkpoint_path": (ckpt_path.relative_to(REPO_ROOT).as_posix()
                                if ckpt_path.is_relative_to(REPO_ROOT) else str(ckpt_path)),
        })
    return rows


def _fmt(value, digits: int = 4) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "--"


def _latex_escape(text: str) -> str:
    for a, b in (("\\", r"\textbackslash{}"), ("_", r"\_"), ("%", r"\%"),
                 ("&", r"\&"), ("#", r"\#")):
        text = text.replace(a, b)
    return text


def render_latex(rows: list[dict], group_by: str) -> str:
    """Mean +/- sd over seeds, grouped by the chosen key."""
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        # dataset_version + split_version are ALWAYS part of the key: runs on
        # different label spaces (e.g. hoa_de with 30 vs 7 classes) must never
        # be averaged together. Only the seed is allowed to vary within a group.
        scope = (r["dataset_version"], r["split_version"])
        if group_by == "profile":
            key = scope + (r["recognition_profile"], r["model_type"], r["augmentation_profile"])
        elif group_by == "augmentation":
            key = scope + (r["augmentation_profile"], r["recognition_profile"], r["model_type"])
        else:
            key = (r["run_id"],)
        groups.setdefault(key, []).append(r)

    def agg(items, field):
        vals = []
        for it in items:
            try:
                vals.append(float(it[field]))
            except (TypeError, ValueError):
                pass
        if not vals:
            return "--"
        if len(vals) == 1:
            return _fmt(vals[0])
        return f"{statistics.mean(vals):.4f} $\\pm$ {statistics.stdev(vals):.4f}"

    lines = [
        "% Generated by scripts/aggregate_experiment_results.py",
        f"% {datetime.now().isoformat(timespec='seconds')} -- do not edit by hand",
        "\\begin{table}[t]",
        "\\centering",
        "\\caption{Results aggregated from frozen artifacts. Values are mean $\\pm$ sd "
        "over seeds. $N$ denotes test-set size; $|C|$ the number of classes.}",
        "\\label{tab:results}",
        "\\begin{tabular}{lllrrrr}",
        "\\toprule",
        "Profile & Model & Aug. & $|C|$ & $N$ & Accuracy & Macro-F1 \\\\",
        "\\midrule",
    ]
    for key in sorted(groups):
        items = groups[key]
        first = items[0]
        lines.append(
            f"{_latex_escape(first['recognition_profile'] or '--')} & "
            f"{_latex_escape(str(first['model_type']) or '--')} & "
            f"{_latex_escape(first['augmentation_profile'] or '--')} & "
            f"{first['num_classes'] or '--'} & {first['n_test'] or '--'} & "
            f"{agg(items, 'test_acc')} & {agg(items, 'test_f1')} \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outputs-root", type=Path,
                    default=REPO_ROOT / "processed" / "train_utils" / "outputs")
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "reports")
    ap.add_argument("--group-by", choices=["profile", "augmentation", "run"],
                    default="profile")
    ap.add_argument("--include-invalid", action="store_true",
                    help="also put non-research_valid runs in the LaTeX table (NOT for papers)")
    args = ap.parse_args()

    rows = collect(args.outputs_root)
    if not rows:
        print(f"No contract-v2 runs found under {args.outputs_root}")
        print("(legacy checkpoints are inventoried by scripts/audit_checkpoint_validity.py)")
        return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "experiment_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    # Two independent gates, both on by default:
    #   run_purpose == research   -> a smoke test can never drift into a table
    #   research_valid == true    -> C1..C14 from research_validity.py
    research_rows = [r for r in rows if r["run_purpose"] == RUN_PURPOSE_RESEARCH]
    valid_rows = [r for r in research_rows if r["research_valid"] == "true"]
    table_rows = rows if args.include_invalid else valid_rows
    tex_path = args.out_dir / "experiment_results.tex"
    tex_path.write_text(render_latex(table_rows, args.group_by), encoding="utf-8")

    dropped_split = [r for r in rows if r["split_valid_for_research"] is False]

    print(f"runs found            : {len(rows)}")
    print(f"  run_purpose=research: {len(research_rows)}")
    print(f"  research_valid=true : {len(valid_rows)}")
    if dropped_split:
        print(f"  dropped, split invalid: {len(dropped_split)}")
    print(f"csv                   -> {csv_path}")
    print(f"latex                 -> {tex_path}")
    if not table_rows:
        print("\n[WARN] LaTeX table is EMPTY: no research-valid run exists yet.")
        print("       Train with --run-purpose research after the 2026-07-21")
        print("       augmentation fix, on a split whose metadata says")
        print("       valid_for_research=true. Pass --include-invalid to inspect.")
        for r in rows[:5]:
            print(f"       - {r['run_id']}: {r['invalid_reasons'][:150]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
