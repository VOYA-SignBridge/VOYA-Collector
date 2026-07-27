"""Build the signer-count x repetitions grid for the collection-budget experiment.

The question: at a FIXED number of training samples, is it better to record more
signers or more repetitions from each? Speech recognition answers "more speakers"
(arXiv:2506.04364, arXiv:2211.00854); nobody has measured the exchange rate for
sign language.

Design, mirroring the matched-control experiment already in the paper: every cell
is held-out-signer evaluation on the SAME test set, and cells that share a budget
differ only in how that budget is composed.

    test   the held-out signer's full set — identical across every cell of a fold,
           so nothing about the test side can explain a difference
    train  n signers x r samples per class, sampled deterministically
    val    a fixed VAL_PER_CLASS per class per training signer, drawn from the
           samples NOT used for training, so validation never eats the budget
           being measured and never leaks a training sample

Iso-budget cells are the comparison that carries the argument. With r in
{4, 6, 8, 12} and up to 3 training signers:

    12 per class:  1 signer x 12  |  2 x 6  |  3 x 4
    24 per class:  2 signers x 12 |  3 x 8
     8 per class:  1 signer x 8   |  2 x 4

Every combination of training signers at a given n is generated and averaged over
at analysis time: with few signers, WHICH signers were picked moves the result
more than the model does, and averaging is what removes that.

Usage:
    python processed/splits/make_budget_grid.py \
        --source processed/splits/versions/hoa_de_sample_v5 \
        --output_version hoa_de_budget_v1
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Kept from the training pool, so a cell's train budget is exactly n * r per class.
VAL_PER_CLASS = 2


def read_split(src: Path):
    rows, fields = [], None
    for name in ("train", "val", "test"):
        p = src / f"{name}.csv"
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            rd = csv.DictReader(f)
            fields = rd.fieldnames
            rows.extend(list(rd))
    return rows, fields


def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def take_per_class(
    rows_by_class: dict, count: int, rng: random.Random
) -> tuple[list, dict]:
    """Deterministically take `count` rows per class; return (taken, leftover)."""
    taken, leftover = [], {}
    for label, rows in sorted(rows_by_class.items()):
        pool = sorted(rows, key=lambda r: r.get("sample_id", ""))
        rng.shuffle(pool)
        taken.extend(pool[:count])
        leftover[label] = pool[count:]
    return taken, leftover


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True,
                    help="A split version directory to draw all samples from")
    ap.add_argument("--output_version", type=str, required=True)
    ap.add_argument("--group_col", type=str, default="signer_id")
    ap.add_argument("--label_col", type=str, default="label_slug")
    ap.add_argument("--reps", type=int, nargs="+", default=[4, 6, 8, 12],
                    help="Samples per class per training signer")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out_root", type=Path,
                    default=REPO_ROOT / "processed" / "splits" / "versions")
    args = ap.parse_args()

    rows, fields = read_split(args.source)
    if not rows:
        print(f"[LOI] khong doc duoc split tu {args.source}")
        return 2

    src_meta_path = args.source / "split_metadata.json"
    src_meta = json.loads(src_meta_path.read_text(encoding="utf-8")) if src_meta_path.exists() else {}
    checksum = str(src_meta.get("dataset_manifest_checksum", ""))
    if not checksum:
        print("[CANH BAO] split nguon khong co dataset_manifest_checksum — "
              "cac fold sinh ra se khong hop le cho nghien cuu")

    rows = [r for r in rows if (r.get(args.group_col) or "").strip()]
    signers = sorted({r[args.group_col] for r in rows})
    labels = sorted({r[args.label_col] for r in rows})
    if len(signers) < 3:
        print(f"[LOI] can it nhat 3 nguoi ky (giu 1 lam test, thay doi 1..2 khi train); "
              f"dang co {len(signers)}: {signers}")
        return 2

    # The largest r we can honour for EVERY (signer, class) cell, leaving VAL_PER_CLASS aside.
    per_cell = Counter((r[args.group_col], r[args.label_col]) for r in rows)
    min_cell = min(per_cell[(s, l)] for s in signers for l in labels if (s, l) in per_cell)
    usable_reps = [r for r in sorted(args.reps) if r + VAL_PER_CLASS <= min_cell]
    dropped = [r for r in sorted(args.reps) if r not in usable_reps]
    if dropped:
        print(f"[CANH BAO] bo cac muc lap {dropped}: o nho nhat chi co {min_cell} mau/lop/nguoi, "
              f"can r + {VAL_PER_CLASS} <= {min_cell}")
    if not usable_reps:
        print("[LOI] khong muc lap nao dung duoc")
        return 2

    root = args.out_root / args.output_version
    root.mkdir(parents=True, exist_ok=True)
    print(f"{len(signers)} nguoi ky, {len(labels)} lop, o nho nhat {min_cell} mau")
    print(f"muc lap dung duoc: {usable_reps}\n")

    manifest, n_ok, n_bad = [], 0, 0
    for held in signers:
        pool = [s for s in signers if s != held]
        test_rows = [r for r in rows if r[args.group_col] == held]

        for n in range(1, len(pool) + 1):
            for combo in combinations(pool, n):
                for r_per in usable_reps:
                    # Seeded per cell so a cell is reproducible on its own, and
                    # the same (signer, class) draw is reused across cells that
                    # share it — the composition changes, the sampling noise does not.
                    rng = random.Random(f"{args.seed}|{held}|{'+'.join(combo)}|{r_per}")

                    train_rows, val_rows = [], []
                    for signer in combo:
                        by_class = defaultdict(list)
                        for row in rows:
                            if row[args.group_col] == signer:
                                by_class[row[args.label_col]].append(row)
                        taken, leftover = take_per_class(by_class, r_per, rng)
                        train_rows.extend(taken)
                        val_taken, _ = take_per_class(leftover, VAL_PER_CLASS, rng)
                        val_rows.extend(val_taken)

                    reasons = []
                    tr_ids = {x["sample_id"] for x in train_rows}
                    if tr_ids & {x["sample_id"] for x in val_rows}:
                        reasons.append("val trung mau voi train")
                    if tr_ids & {x["sample_id"] for x in test_rows}:
                        reasons.append("test trung mau voi train")
                    if {x[args.group_col] for x in train_rows} & {held}:
                        reasons.append("nguoi ky test co trong train")
                    tr_lab = {x[args.label_col] for x in train_rows}
                    if tr_lab != set(labels):
                        reasons.append(f"train thieu lop: {sorted(set(labels) - tr_lab)}")
                    if {x[args.label_col] for x in test_rows} != set(labels):
                        reasons.append("test thieu lop")
                    if not val_rows:
                        reasons.append("val rong")

                    cell = root / f"test_{held}" / f"n{n}_r{r_per}" / "+".join(combo)
                    write_csv(cell / "train.csv", train_rows, fields)
                    write_csv(cell / "val.csv", val_rows, fields)
                    write_csv(cell / "test.csv", test_rows, fields)

                    meta = {
                        "split_mode": "budget_grid_leave_one_signer_out",
                        "recognition_profile": src_meta.get("recognition_profile", ""),
                        "include_common": src_meta.get("include_common", False),
                        "seed": args.seed,
                        "group_col": args.group_col,
                        "held_out_signer": held,
                        "train_signers": list(combo),
                        "n_train_signers": n,
                        "reps_per_class": r_per,
                        # The quantity the experiment holds fixed across cells.
                        "budget_per_class": n * r_per,
                        "val_per_class_per_signer": VAL_PER_CLASS,
                        "valid_for_research": not reasons,
                        "invalid_reasons": reasons,
                        "num_classes": len(labels),
                        "label_keys": sorted({x.get("label_key", "") for x in rows} - {""}),
                        "counts": {"train": len(train_rows), "val": len(val_rows),
                                   "test": len(test_rows)},
                        "signers": {"train": sorted(combo), "val": sorted(combo), "test": [held]},
                        "class_coverage": {"train": len(tr_lab) / len(labels), "test": 1.0},
                        "dataset_manifest": src_meta.get("dataset_manifest", ""),
                        "dataset_manifest_checksum": checksum,
                        "source_split_version": src_meta.get("output_version", args.source.name),
                        "output_version": f"{args.output_version}/test_{held}/n{n}_r{r_per}/{'+'.join(combo)}",
                    }
                    (cell / "split_metadata.json").write_text(
                        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

                    manifest.append(meta)
                    if reasons:
                        n_bad += 1
                        print(f"  KHONG HOP LE test={held} n={n} r={r_per} "
                              f"[{'+'.join(combo)}]: {'; '.join(reasons)}")
                    else:
                        n_ok += 1

    budgets = defaultdict(set)
    for m in manifest:
        if m["valid_for_research"]:
            budgets[m["budget_per_class"]].add((m["n_train_signers"], m["reps_per_class"]))
    iso = {b: sorted(v) for b, v in sorted(budgets.items()) if len(v) > 1}

    (root / "grid_manifest.json").write_text(json.dumps({
        "output_version": args.output_version,
        "signers": signers,
        "classes": len(labels),
        "reps": usable_reps,
        "cells_valid": n_ok,
        "cells_invalid": n_bad,
        "iso_budget_cells": {str(k): v for k, v in iso.items()},
        "cells": manifest,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{n_ok} o hop le, {n_bad} o khong hop le -> {root}")
    print("O CUNG NGAN SACH (day la cac so sanh mang y nghia):")
    for budget, combos in iso.items():
        pretty = "  |  ".join(f"{n} nguoi x {r} lan" for n, r in combos)
        print(f"  {budget:3d} mau/lop:  {pretty}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
