"""Recompute per-class frame-to-frame motion for Figure 2.

The statistic is the mean L2 displacement between consecutive frames of the
60x126 sequence, averaged over the samples of a class — the same quantity the
earlier `motion_by_class.json` recorded, now derived from a named manifest
instead of an undated snapshot.

Only samples present in the given manifest are counted, so exclusions (handedness
flips, two-handed samples in a one-handed class) are honoured automatically and
the figure cannot disagree with the tables.

    python reports/make_motion_by_class.py \
        --manifest dataset/manifests/dataset_manifest_isds2026_v13.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
PROFILES = {"alphabet": "bang-chu-cai", "hoa_de": "hoa-de"}
FEATURE_KEYS = ("sequence", "features", "x", "data", "arr_0")


def mean_l2_step(seq: np.ndarray) -> float:
    """Mean L2 norm of the frame-to-frame difference vector."""
    return float(np.linalg.norm(np.diff(seq, axis=0), axis=1).mean())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path,
                    default=REPO / "dataset/manifests/dataset_manifest_isds2026_v13.csv")
    ap.add_argument("--features-root", type=Path, default=REPO / "dataset/features")
    ap.add_argument("--out", type=Path, default=REPO / "reports/motion_by_class.json")
    args = ap.parse_args()

    want = {}
    for row in csv.DictReader(args.manifest.open(encoding="utf-8")):
        dialect = row.get("dialect") or ""
        for profile, d in PROFILES.items():
            if dialect == d:
                want[row["sample_id"]] = (profile, row["slug"])

    print(f"manifest: {args.manifest.name}  ({len(want)} mau thuoc 2 profile)")

    per = defaultdict(lambda: defaultdict(list))
    unreadable = 0
    for path in args.features_root.rglob("*.npz"):
        sid = path.stem.replace("sample_", "")
        hit = want.get(sid)
        if not hit:
            continue
        try:
            with np.load(path, allow_pickle=False) as z:
                key = next((k for k in FEATURE_KEYS if k in z), None)
                seq = np.asarray(z[key], dtype=np.float32) if key else None
        except Exception:
            unreadable += 1
            continue
        if seq is None or seq.ndim != 2 or seq.shape[1] != 126 or len(seq) < 2:
            unreadable += 1
            continue
        profile, slug = hit
        per[profile][slug].append(mean_l2_step(seq))

    out = {
        profile: {
            slug: {"mean": float(np.mean(v)), "std": float(np.std(v)), "n": len(v)}
            for slug, v in sorted(classes.items())
        }
        for profile, classes in per.items()
    }
    out["_provenance"] = {
        "manifest": args.manifest.name,
        "statistic": "mean L2 norm of frame-to-frame difference, averaged per class",
        "features_root": str(args.features_root),
    }

    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    for profile in PROFILES:
        c = out.get(profile, {})
        if c:
            lo = min(s["mean"] for s in c.values())
            hi = max(s["mean"] for s in c.values())
            print(f"  {profile:<9} {len(c):>3} lop  mean-L2 {lo:.4f} - {hi:.4f}")
    if unreadable:
        print(f"  bo qua {unreadable} file khong doc duoc")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
