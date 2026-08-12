#!/usr/bin/env python3
"""Answer one question: if we switched to hands126_v2 today, what would we get?

READ-ONLY. Writes nothing, rebuilds nothing, and is safe to run against a live
dataset.

Why this exists
---------------
`normalize_single_hand` v1 leaves z in raw MediaPipe units while x/y are in
units of hand span, so the third axis arrives an order of magnitude smaller than
the other two and a model reads it as noise. v2 divides z by the same scale.

Switching is not a code decision, it is a data decision: v2 features can only be
produced for samples whose UN-normalized landmarks were kept. v1 threw the
originals away, so a sample without `landmarks_raw` cannot be converted — its
scale divisor is gone. Rebuilding only the samples that can be rebuilt would
leave the corpus in TWO coordinate spaces feeding one model, which is the exact
defect that cost 3431-vs-440 samples earlier in this project.

So the number that matters is not "is v2 better" (it is, measurably) but "how
much of the corpus can follow", and that is what this prints.

Usage:
    python scripts/report_normalization_v2_readiness.py [--dataset /dataset]
                                                        [--limit N] [--json OUT]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from processed.shared.normalization import (  # noqa: E402
    NORMALIZATION_V1,
    NORMALIZATION_V2,
    normalize_hands_vector_126,
)


def _axis_ratio(seq: np.ndarray, version: str, max_frames: int) -> float | None:
    """Mean (x/y span) / (z span) for one sample — the units mismatch, measured.

    1.0 would mean the three axes are equally scaled. v1 is expected to be far
    above that purely because z was never divided; whatever v2 leaves behind is
    the real shallowness of MediaPipe's regressed depth, not a unit error.
    """
    frames = seq[:max_frames]
    out = np.stack([normalize_hands_vector_126(f, version) for f in frames])
    hands = out.reshape(len(out), 2, 21, 3)
    ratios = []
    for hi in range(2):
        h = hands[:, hi]
        present = np.any(h.reshape(len(h), -1) != 0, axis=1)
        h = h[present]
        if len(h) == 0:
            continue
        span_xy = np.maximum(h[:, :, 0].max(1) - h[:, :, 0].min(1),
                             h[:, :, 1].max(1) - h[:, :, 1].min(1)).mean()
        span_z = (h[:, :, 2].max(1) - h[:, :, 2].min(1)).mean()
        if span_z > 1e-9:
            ratios.append(float(span_xy / span_z))
    return float(np.mean(ratios)) if ratios else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="/dataset",
                    help="dataset root containing features/ (default: /dataset)")
    ap.add_argument("--limit", type=int, default=0,
                    help="measure the axis ratio on at most N rebuildable samples "
                         "(0 = every one; counting always covers all files)")
    ap.add_argument("--max-frames", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0,
                    help="seed for the --limit sample, so a quoted number is reproducible")
    ap.add_argument("--json", default="", help="also write the summary here")
    args = ap.parse_args()

    root = Path(args.dataset)
    files = sorted(root.glob("features/**/*.npz"))
    if not files:
        print(f"FAIL  khong tim thay .npz nao duoi {root}/features")
        return 2

    # ---- coverage: who can follow -------------------------------------
    kinds: Counter = Counter()
    per_dialect: dict = defaultdict(Counter)
    rebuildable: list = []
    unreadable = 0

    for f in files:
        try:
            with np.load(f, allow_pickle=True) as d:
                keys = set(d.keys())
        except Exception:
            unreadable += 1
            continue
        kind = ("raw" if "landmarks_raw" in keys
                else "normalized_only" if "landmarks_normalized" in keys
                else "sequence_only")
        kinds[kind] += 1
        # features/<lang>/<dialect>/<class>/<sample>.npz
        parts = f.relative_to(root / "features").parts
        per_dialect[parts[1] if len(parts) > 2 else "?"][kind] += 1
        if kind == "raw":
            rebuildable.append(f)

    total = sum(kinds.values())
    n_rebuildable = kinds["raw"]
    pct = 100.0 * n_rebuildable / total if total else 0.0

    # ---- effect: how much better, on real data ------------------------
    # A seeded random sample, not the first N: the files sort by dialect, so
    # `[:N]` would measure almost nothing but bang-chu-cai and report its median
    # as the corpus median.
    if args.limit <= 0 or args.limit >= len(rebuildable):
        targets = rebuildable
    else:
        targets = random.Random(args.seed).sample(rebuildable, args.limit)
    r_v1, r_v2 = [], []
    for f in targets:
        try:
            with np.load(f, allow_pickle=True) as d:
                raw = np.asarray(d["landmarks_raw"], dtype=np.float32)
        except Exception:
            continue
        if raw.ndim != 2 or raw.shape[1] != 126 or len(raw) == 0:
            continue
        a = _axis_ratio(raw, NORMALIZATION_V1, args.max_frames)
        b = _axis_ratio(raw, NORMALIZATION_V2, args.max_frames)
        if a is not None and b is not None:
            r_v1.append(a)
            r_v2.append(b)

    summary = {
        "total_samples": total,
        "unreadable": unreadable,
        "by_archive_kind": dict(kinds),
        "rebuildable_to_v2": n_rebuildable,
        "rebuildable_pct": round(pct, 1),
        "stranded_on_v1": total - n_rebuildable,
        "measured": len(r_v1),
        "axis_ratio_v1_median": round(float(np.median(r_v1)), 2) if r_v1 else None,
        "axis_ratio_v2_median": round(float(np.median(r_v2)), 2) if r_v2 else None,
        "by_dialect": {k: dict(v) for k, v in sorted(per_dialect.items())},
    }

    print(f"\n  Tong mau                : {total}"
          + (f"  (khong doc duoc: {unreadable})" if unreadable else ""))
    print(f"  Dung duoc cho v2        : {n_rebuildable}  ({pct:.1f}%)   <- co landmarks_raw")
    print(f"  Ket lai o v1            : {total - n_rebuildable}  ({100 - pct:.1f}%)   "
          f"<- khong con toa do goc, khong dung lai duoc")
    if r_v1:
        print(f"\n  Lech don vi giua truc (span_xy / span_z, trung vi tren {len(r_v1)} mau):")
        print(f"    v1  {np.median(r_v1):6.2f}x   z nho hon x/y bay nhieu lan -> mo hinh doc z nhu nhieu")
        print(f"    v2  {np.median(r_v2):6.2f}x   phan con lai la do nong THAT cua z, khong phai loi don vi")

    print("\n  Theo phuong ngu:")
    width = max((len(k) for k in per_dialect), default=1)
    for dialect, c in sorted(per_dialect.items()):
        n = sum(c.values())
        ok = c["raw"]
        print(f"    {dialect:<{width}}  {ok:5}/{n:<5} ({100.0 * ok / n:5.1f}%) san sang v2")

    print("\n  Doc so nay the nao:")
    print("    - Lat sang v2 ngay = huan luyen lai TOAN BO, va corpus tut xuong")
    print(f"      {n_rebuildable} mau. Tron v1 voi v2 trong mot mo hinh la tai dung")
    print("      lai dung loi da tra gia o dot 3431-vs-440 mau.")
    print("    - Moi mau thu MOI deu co raw, nen ty le nay chi tang theo thoi gian.")
    print("    - v1 van la mac dinh; khong co gi gay cho toi khi ban quyet dinh.\n")

    if args.json:
        Path(args.json).write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        print(f"  -> {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
