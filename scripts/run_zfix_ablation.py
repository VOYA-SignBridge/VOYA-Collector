#!/usr/bin/env python3
"""Run the z-fix ablation grid and print one comparison table.

Pairs with scripts/build_zfix_ablation.py, which materialises the two feature
trees and the single shared manifest. This runs seeds x arms and reports whether
hands126_v2 (z divided by the hand span) beats hands126_v1 (z left raw).

Why a grid and not one run each: on 1334 training samples the seed-to-seed
spread is easily larger than the effect being measured, so a single pair of runs
can show either sign and mean nothing. The table prints per-seed numbers next to
the mean so a difference smaller than the spread is visible as such instead of
being reported as a result.

Both arms share ONE split (processed/splits/versions/<split>/), so the only
difference between them is the normalization version of the features.

Usage:
    python scripts/run_zfix_ablation.py --seeds 42,43,44 --epochs 80
    python scripts/run_zfix_ablation.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TRAINER = REPO / "processed" / "train_utils" / "train_tcn.py"

ARMS = ("v1", "v2")


def _find_summary(out_dir: Path) -> dict | None:
    """The trainer nests its output under version/profile/version/arch/seed_N."""
    candidates = sorted(out_dir.rglob("*.json"))
    for c in candidates:
        try:
            data = json.loads(c.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and any(
                k in data for k in ("test_acc", "test_accuracy", "test", "metrics")):
            return data
    return None


def _metric(summary: dict, *names: str) -> float | None:
    for n in names:
        if n in summary and isinstance(summary[n], (int, float)):
            return float(summary[n])
    for key in ("test", "metrics", "test_metrics"):
        block = summary.get(key)
        if isinstance(block, dict):
            for n in names:
                if n in block and isinstance(block[n], (int, float)):
                    return float(block[n])
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="zfix")
    ap.add_argument("--features-root", default="/dataset/features_zfix")
    ap.add_argument("--out-root", default=str(REPO / "processed" / "train_utils" / "outputs" / "zfix"))
    ap.add_argument("--seeds", default="42,43,44")
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--results", default=str(REPO / "reports" / "zfix_ablation.json"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--summarize-only", action="store_true",
                    help="re-print the table from --results without retraining")
    args = ap.parse_args()

    if args.summarize_only:
        saved = json.loads(Path(args.results).read_text(encoding="utf-8"))
        results = saved.get("runs", [])
        seeds = sorted({r["seed"] for r in results})
        return _report(results, seeds, args)

    split_dir = REPO / "processed" / "splits" / "versions" / args.split
    if not (split_dir / "train.csv").exists():
        print(f"FAIL  khong thay split {split_dir}/train.csv")
        print("      Chay scripts/build_zfix_ablation.py + processed/splits/make_splits.py truoc.")
        return 2

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    results: list[dict] = []

    for seed in seeds:
        for arm in ARMS:
            out_dir = Path(args.out_root) / f"{arm}_seed{seed}"
            cmd = [
                sys.executable, str(TRAINER),
                "--train_csv", str(split_dir / "train.csv"),
                "--val_csv", str(split_dir / "val.csv"),
                "--test_csv", str(split_dir / "test.csv"),
                "--features_root", f"{args.features_root}/{arm}",
                "--unified",
                "--epochs", str(args.epochs),
                "--seed", str(seed),
                "--device", args.device,
                "--num_workers", str(args.num_workers),
                "--out_dir", str(out_dir),
            ]
            if args.dry_run:
                print("  " + " ".join(cmd))
                continue

            print(f"\n=== arm={arm} seed={seed} ===", flush=True)
            t0 = time.time()
            proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
            elapsed = time.time() - t0
            if proc.returncode != 0:
                print(f"  FAIL rc={proc.returncode}")
                print(proc.stdout[-1500:])
                print(proc.stderr[-1500:])
                results.append({"arm": arm, "seed": seed, "ok": False})
                continue

            summary = _find_summary(out_dir) or {}
            acc = _metric(summary, "test_acc", "test_accuracy", "acc", "accuracy")
            f1 = _metric(summary, "test_f1", "f1", "f1_macro")
            if acc is None:
                # The trainer always prints them; fall back to the stdout it just wrote.
                for line in reversed(proc.stdout.splitlines()):
                    if line.strip().startswith("test loss"):
                        parts = line.split()
                        try:
                            acc = float(parts[parts.index("acc") + 1])
                            f1 = float(parts[parts.index("f1") + 1])
                        except Exception:
                            pass
                        break
            print(f"  acc={acc}  f1={f1}  ({elapsed / 60:.1f} min)", flush=True)
            results.append({"arm": arm, "seed": seed, "ok": True,
                            "test_acc": acc, "test_f1": f1,
                            "minutes": round(elapsed / 60, 1)})

    if args.dry_run:
        return 0

    return _report(results, seeds, args)


def _report(results: list, seeds: list, args) -> int:
    # ---- table -----------------------------------------------------------
    def _vals(arm: str, key: str) -> list[float]:
        return [r[key] for r in results
                if r.get("ok") and r["arm"] == arm and isinstance(r.get(key), (int, float))]

    print("\n" + "=" * 62)
    print("  Z-FIX ABLATION — cung split, cung seed, chi khac chuan hoa")
    print("=" * 62)
    print(f"  {'seed':>6}  {'v1 acc':>8}  {'v2 acc':>8}  {'delta':>8}   "
          f"{'v1 f1':>7}  {'v2 f1':>7}")
    for seed in seeds:
        a = next((r for r in results if r["arm"] == "v1" and r["seed"] == seed and r.get("ok")), None)
        b = next((r for r in results if r["arm"] == "v2" and r["seed"] == seed and r.get("ok")), None)
        if not a or not b or a["test_acc"] is None or b["test_acc"] is None:
            print(f"  {seed:>6}  {'--':>8}  {'--':>8}  {'--':>8}")
            continue
        print(f"  {seed:>6}  {a['test_acc']:>8.4f}  {b['test_acc']:>8.4f}  "
              f"{b['test_acc'] - a['test_acc']:>+8.4f}   "
              f"{(a['test_f1'] or 0):>7.4f}  {(b['test_f1'] or 0):>7.4f}")

    v1a, v2a = _vals("v1", "test_acc"), _vals("v2", "test_acc")
    if v1a and v2a:
        import statistics as st
        m1, m2 = st.mean(v1a), st.mean(v2a)
        s1 = max(v1a) - min(v1a) if len(v1a) > 1 else 0.0
        s2 = max(v2a) - min(v2a) if len(v2a) > 1 else 0.0
        # Compare against the WIDER arm, not the narrower one. Using v1's spread
        # alone would let a quiet baseline certify a noisy challenger: the bar
        # for "this difference is real" has to clear the noise of whichever arm
        # is noisier, otherwise the verdict is decided by which arm you measured
        # the spread on.
        spread = max(s1, s2)
        deltas = []
        for seed in seeds:
            a = next((r for r in results if r["arm"] == "v1" and r["seed"] == seed and r.get("ok")), None)
            b = next((r for r in results if r["arm"] == "v2" and r["seed"] == seed and r.get("ok")), None)
            if a and b and a["test_acc"] is not None and b["test_acc"] is not None:
                deltas.append(b["test_acc"] - a["test_acc"])
        consistent = bool(deltas) and (all(d > 0 for d in deltas) or all(d < 0 for d in deltas))

        print("-" * 62)
        print(f"  {'mean':>6}  {m1:>8.4f}  {m2:>8.4f}  {m2 - m1:>+8.4f}")
        print(f"\n  Do trai seed-to-seed: v1 {s1:.4f}   v2 {s2:.4f}")
        print(f"  Dau cua delta nhat quan qua cac seed: {'CO' if consistent else 'KHONG'}")

        if abs(m2 - m1) <= spread or not consistent:
            print("\n  -> CHUA KET LUAN DUOC.")
            if not consistent:
                print("     Delta doi dau giua cac seed — mot seed nghieng ben nay,")
                print("     seed khac nghieng ben kia.")
            if abs(m2 - m1) <= spread:
                print(f"     Chenh lech trung binh ({abs(m2 - m1):.4f}) khong vuot noi do trai")
                print(f"     lon nhat giua cac seed ({spread:.4f}).")
            print("     Can them seed hoac them du lieu — khong phai them y kien.")
        else:
            better = "v2" if m2 > m1 else "v1"
            print(f"\n  -> {better} thang: dau nhat quan qua moi seed VA bien do vuot do trai.")

    if args.summarize_only:
        return 0

    out = Path(args.results)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"split": args.split, "epochs": args.epochs,
                               "runs": results}, indent=2), encoding="utf-8")
    print(f"\n  -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
