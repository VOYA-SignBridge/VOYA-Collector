#!/usr/bin/env python3
"""Turn the signer x repetition grid into the claim it exists to test.

The headline is NOT "accuracy goes up with more data" — that is never in doubt.
It is the ISO-BUDGET comparison: with the number of training samples held fixed,
does spending it on more signers beat spending it on more takes each?

Every iso-budget comparison is PAIRED on the held-out signer, exactly as the
matched-control experiment in the paper is. Between-signer variation is the
dominant noise here (this dataset spans ~0.25 accuracy between its easiest and
hardest performer), so an unpaired mean would drown the effect being measured.

    python scripts/summarize_budget_grid.py \
        reports/budget_grid_hoa_de_budget_v1_tcn_raw.txt \
        --grid processed/splits/versions/hoa_de_budget_v1/grid_manifest.json
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# "test_S001 n2_r6 S002+S012 tcn seed=42 0.8621 f1 0.8523"
LINE = re.compile(
    r"^(?P<held>test_\S+)\s+n(?P<n>\d+)_r(?P<r>\d+)\s+(?P<combo>\S+)\s+"
    r"(?P<model>\S+)\s+seed=(?P<seed>\d+)\s+(?P<acc>[0-9.]+)\s+f1\s+(?P<f1>[0-9.]+)\s*$"
)


def parse(path: Path) -> List[dict]:
    rows, failed = [], 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.endswith("FAILED"):
            failed += 1
            continue
        m = LINE.match(raw.strip())
        if not m:
            continue
        d = m.groupdict()
        rows.append({
            "held": d["held"].replace("test_", ""),
            "n": int(d["n"]),
            "r": int(d["r"]),
            "combo": d["combo"],
            "seed": int(d["seed"]),
            "acc": float(d["acc"]),
            "f1": float(d["f1"]),
            "budget": int(d["n"]) * int(d["r"]),
        })
    if failed:
        print(f"[CANH BAO] {failed} lan chay that bai, da bo qua\n")
    return rows


def mean(xs: List[float]) -> float:
    return statistics.fmean(xs) if xs else float("nan")


def cell_means(rows: List[dict], metric: str) -> Dict[Tuple[str, int, int], float]:
    """(held, n, r) -> mean over every signer combination and seed.

    Averaging over combinations is the point: with few signers, WHICH ones landed
    in the training set moves the result more than the composition does.
    """
    buckets = defaultdict(list)
    for row in rows:
        buckets[(row["held"], row["n"], row["r"])].append(row[metric])
    return {k: mean(v) for k, v in buckets.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw", type=Path, help="budget_grid_*_raw.txt")
    ap.add_argument("--grid", type=Path, default=None, help="grid_manifest.json")
    ap.add_argument("--metric", default="acc", choices=["acc", "f1"])
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    rows = parse(args.raw)
    if not rows:
        print(f"khong doc duoc ket qua nao tu {args.raw}")
        return 2

    helds = sorted({r["held"] for r in rows})
    ns = sorted({r["n"] for r in rows})
    reps = sorted({r["r"] for r in rows})
    print(f"{len(rows)} lan chay | {len(helds)} fold | n={ns} | r={reps} | metric={args.metric}\n")

    # ---- the grid itself -------------------------------------------------
    means = cell_means(rows, args.metric)
    print("Trung binh tren cac fold (hang = so nguoi train, cot = so lan lap):")
    print("        " + "".join(f"r={r:<8}" for r in reps))
    for n in ns:
        cells = []
        for r in reps:
            vals = [means[(h, n, r)] for h in helds if (h, n, r) in means]
            cells.append(f"{mean(vals):.3f}   " if vals else "  --    ")
        print(f"  n={n}   " + "".join(cells))

    # ---- iso-budget: the comparison that carries the argument -------------
    by_budget = defaultdict(set)
    for (_, n, r) in means:
        by_budget[n * r].add((n, r))
    iso = {b: sorted(v) for b, v in sorted(by_budget.items()) if len(v) > 1}

    print("\nO CUNG NGAN SACH — cung so mau train, khac cach chia:")
    report = []
    for budget, combos in iso.items():
        print(f"\n  Ngan sach {budget} mau/lop")
        per_combo = {}
        for (n, r) in combos:
            vals = [means[(h, n, r)] for h in helds if (h, n, r) in means]
            per_combo[(n, r)] = vals
            print(f"    {n} nguoi x {r:2d} lan : {mean(vals):.4f}"
                  f"   (tung fold: {', '.join(f'{v:.3f}' for v in vals)})")

        # Paired against the LEAST diverse composition at this budget.
        base = min(combos, key=lambda c: c[0])
        for (n, r) in combos:
            if (n, r) == base:
                continue
            pairs = [
                (means[(h, n, r)] - means[(h, base[0], base[1])])
                for h in helds
                if (h, n, r) in means and (h, base[0], base[1]) in means
            ]
            if not pairs:
                continue
            wins = sum(1 for d in pairs if d > 0)
            print(f"    -> {n}x{r} so voi {base[0]}x{base[1]}: "
                  f"{mean(pairs):+.4f} trung binh, thang {wins}/{len(pairs)} fold")
            report.append({
                "budget": budget,
                "more_signers": {"n": n, "r": r},
                "fewer_signers": {"n": base[0], "r": base[1]},
                "paired_delta_mean": mean(pairs),
                "paired_deltas": pairs,
                "folds_won": wins,
                "folds_total": len(pairs),
            })

    if report:
        gains = [x["paired_delta_mean"] for x in report]
        won = sum(x["folds_won"] for x in report)
        tot = sum(x["folds_total"] for x in report)
        print(f"\nTONG HOP: {len(report)} so sanh cung ngan sach, "
              f"trung binh {mean(gains):+.4f}, "
              f"cach chia nhieu nguoi hon thang {won}/{tot} fold")
        print("(duong > 0 = cung ngan sach, them NGUOI tot hon them LAN LAP)")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({
            "source": str(args.raw),
            "metric": args.metric,
            "runs": len(rows),
            "folds": helds,
            "grid_mean": {f"n{n}_r{r}": mean([means[(h, n, r)] for h in helds
                                              if (h, n, r) in means])
                          for n in ns for r in reps
                          if any((h, n, r) in means for h in helds)},
            "iso_budget_comparisons": report,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nda ghi {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
