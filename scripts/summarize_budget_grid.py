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


def sufficiency_threshold(
    means: Dict[Tuple[str, int, int], float],
    helds: List[str],
    ns: List[int],
    reps: List[int],
) -> dict:
    """The smallest budget that is already as good as the best cell observed.

    Deliberately NOT the arg-max. Picking the highest cell in a noisy grid
    overestimates by roughly one standard error — the cell is highest partly
    because it got lucky — and with four folds that bias is around the size of
    the effects worth reporting. This is the one-standard-error rule used for
    model selection (Breiman et al., CART; Hastie et al., ESL): take the
    cheapest configuration whose mean is within 1 SE of the best one.

    It answers "from where on does more stop being worth it", which is the
    practical question, rather than "where is the peak", which is mostly noise.
    """
    stats = {}
    for n in ns:
        for r in reps:
            per_fold = [means[(h, n, r)] for h in helds if (h, n, r) in means]
            if len(per_fold) < 2:
                continue
            m = mean(per_fold)
            se = statistics.stdev(per_fold) / (len(per_fold) ** 0.5)
            stats[(n, r)] = {"mean": m, "se": se, "folds": len(per_fold),
                             "budget": n * r}
    if not stats:
        return {}

    best_cell = max(stats, key=lambda k: stats[k]["mean"])
    best = stats[best_cell]
    cutoff = best["mean"] - best["se"]

    within = [k for k, v in stats.items() if v["mean"] >= cutoff]
    # Cheapest first: fewest samples, then fewest signers to record.
    chosen = min(within, key=lambda k: (stats[k]["budget"], k[0]))

    # A threshold sitting on the edge of the grid is not a plateau — it is the
    # grid running out. Saying so is the difference between a finding and an
    # artefact.
    edges = []
    if chosen[0] == max(ns):
        edges.append(f"so nguoi = {chosen[0]} la muc CAO NHAT trong luoi")
    if chosen[1] == max(reps):
        edges.append(f"so lan lap = {chosen[1]} la muc CAO NHAT trong luoi")
    if best_cell[0] == max(ns):
        edges.append(f"o tot nhat cung dung o muc nguoi cao nhat ({max(ns)})")

    return {
        "best_cell": {"n": best_cell[0], "r": best_cell[1], **best},
        "cutoff": cutoff,
        "chosen": {"n": chosen[0], "r": chosen[1], **stats[chosen]},
        "candidates_within_1se": sorted(
            [{"n": n, "r": r, **stats[(n, r)]} for (n, r) in within],
            key=lambda c: c["budget"],
        ),
        "grid_edge_warnings": edges,
        "grid": {"n_levels": ns, "r_levels": reps},
    }


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

    # ---- how much is enough -----------------------------------------------
    suff = sufficiency_threshold(means, helds, ns, reps)
    if suff:
        best, chosen = suff["best_cell"], suff["chosen"]
        print(f"\nNGUONG DU DUNG (quy tac 1 sai so chuan, khong phai cuc dai):")
        print(f"  o tot nhat quan sat duoc : {best['n']} nguoi x {best['r']} lan"
              f"  = {best['mean']:.4f} (SE {best['se']:.4f}, {best['budget']} mau/lop)")
        print(f"  nguong  (>= {suff['cutoff']:.4f}) : {chosen['n']} nguoi x {chosen['r']} lan"
              f"  = {chosen['mean']:.4f}  -> {chosen['budget']} mau/lop")
        others = [c for c in suff["candidates_within_1se"]
                  if (c["n"], c["r"]) != (chosen["n"], chosen["r"])]
        if others:
            print("  cac cau hinh khac cung dat nguong: "
                  + ", ".join(f"{c['n']}x{c['r']}" for c in others))
        if suff["grid_edge_warnings"]:
            print("\n  [CANH BAO] nguong nam o MEP LUOI — day KHONG phai bang chung bao hoa,")
            print("             ma la dau hieu het du lieu de tang tiep:")
            for w in suff["grid_edge_warnings"]:
                print(f"               - {w}")
            print("             Dung viet 'bao hoa tai ...' trong bai; hay viet")
            print("             'trong dai da khao sat, chua quan sat duoc diem bao hoa'.")
        else:
            print("\n  Nguong nam BEN TRONG luoi — co the noi den dau hieu chung lai,")
            print("  van kem dieu kien: tren tap tu vung nay va kien truc nay.")

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
            "sufficiency_threshold": suff,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nda ghi {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
