#!/usr/bin/env python3
"""Materialise the two arms of the z-fix ablation: hands126_v1 vs hands126_v2.

The question this is built to answer: does dividing z by the hand span (v2)
actually help, or is MediaPipe's z so shallow that fixing its units changes
nothing? v1 hands the model a z axis ~21.8x smaller than x/y; v2 brings that to
~5.25x, and the remainder is real geometry. Whether the model can use it is an
empirical question, and guessing at it is how the 3431-vs-440 mess happened.

What it writes
--------------
    <out-root>/v1/<same relative path>.npz     features as they are today
    <out-root>/v2/<same relative path>.npz     same samples, z divided by scale
    <out-root>/matched_samples.csv             the sample list both arms share

BOTH arms are rebuilt from `landmarks_raw` by the same code path and slimmed the
same way, so the ONLY difference between the trees is the normalization version.
Comparing the v2 tree against the existing dataset/features would confound the
fix with a different sample set (v2 can only cover the 51.6% that kept raw
landmarks) and with whatever else the stored files carry.

The correctness guard
---------------------
For every sample, the v1 arm is rebuilt from raw and compared against the
`sequence` already on disk. A sample that does not reproduce EXACTLY is skipped
and reported — it means the stored features and the stored raw landmarks
disagree, and such a sample would silently poison both arms. Verified on 148
random samples before this script existed: 148 exact, 0 mismatches.

Dry run by default. Nothing is written without --confirm.

Usage:
    python scripts/build_zfix_ablation.py                       # report only
    python scripts/build_zfix_ablation.py --confirm             # write both arms
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
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


def _rebuild(raw: np.ndarray, version: str) -> np.ndarray:
    return np.stack([normalize_hands_vector_126(raw[t], version)
                     for t in range(raw.shape[0])]).astype(np.float32)


def _write_arm(path: Path, sequence: np.ndarray, version: str, source: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # meta as a JSON string, not a dict: the training loader opens npz with
    # allow_pickle=False, and a dict would be stored as an object array that
    # cannot be read back without pickle.
    meta = json.dumps({
        "normalization_version": version,
        "rebuilt_from": str(source),
        "generator": "scripts/build_zfix_ablation.py",
    }, ensure_ascii=False)
    np.savez_compressed(path, sequence=sequence, meta_json=np.array(meta))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="/dataset")
    ap.add_argument("--out-root", default="/dataset/features_zfix")
    ap.add_argument("--confirm", action="store_true",
                    help="actually write; without it nothing touches the disk")
    ap.add_argument("--limit", type=int, default=0, help="stop after N samples (smoke test)")
    ap.add_argument("--manifest", default="",
                    help="an existing dataset manifest to filter down to the matched "
                         "samples, so both arms train on one identical split")
    ap.add_argument("--manifest-out", default="",
                    help="where to write that filtered manifest")
    args = ap.parse_args()

    root = Path(args.dataset)
    features = root / "features"
    out_root = Path(args.out_root)

    files = sorted(features.glob("**/*.npz"))
    if not files:
        print(f"FAIL  khong tim thay .npz duoi {features}")
        return 2

    matched: list[dict] = []
    n_no_raw = n_bad_shape = n_mismatch = n_error = 0
    written = 0

    for f in files:
        if args.limit and len(matched) >= args.limit:
            break
        try:
            with np.load(f, allow_pickle=True) as d:
                if "landmarks_raw" not in d:
                    n_no_raw += 1
                    continue
                raw = np.asarray(d["landmarks_raw"], dtype=np.float32)
                stored = np.asarray(d["sequence"], dtype=np.float32)
        except Exception:
            n_error += 1
            continue

        if raw.ndim != 2 or raw.shape[1] != 126 or raw.shape != stored.shape:
            n_bad_shape += 1
            continue

        v1 = _rebuild(raw, NORMALIZATION_V1)
        if not np.allclose(v1, stored, atol=1e-6):
            # Stored features and stored raw landmarks disagree. Whatever the
            # cause, this sample cannot be used to compare normalizations — the
            # baseline arm would not be the baseline.
            n_mismatch += 1
            continue

        rel = f.relative_to(features)
        matched.append({"relative_path": str(rel).replace("\\", "/"),
                        "source": str(f), "frames": int(raw.shape[0])})

        if args.confirm:
            _write_arm(out_root / "v1" / rel, v1, NORMALIZATION_V1, f)
            _write_arm(out_root / "v2" / rel, _rebuild(raw, NORMALIZATION_V2),
                       NORMALIZATION_V2, f)
            written += 1

    total = len(files)
    print(f"\n  Tong .npz duyet          : {total}")
    print(f"  Khong co landmarks_raw   : {n_no_raw}  -> khong dung lai duoc, ngoai thi nghiem")
    print(f"  Shape khong hop le       : {n_bad_shape}")
    print(f"  Doc loi                  : {n_error}")
    print(f"  LECH v1 vs sequence luu  : {n_mismatch}  <- bi loai, xem docstring")
    print(f"  Vao ca HAI nhanh         : {len(matched)}")

    if args.confirm:
        out_root.mkdir(parents=True, exist_ok=True)
        index = out_root / "matched_samples.csv"
        with index.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["relative_path", "source", "frames"])
            w.writeheader()
            w.writerows(matched)
        print(f"\n  Da ghi {written} mau x 2 nhanh:")
        print(f"    {out_root / 'v1'}")
        print(f"    {out_root / 'v2'}")
        print(f"    {index}")
    else:
        print("\n  DRY RUN — chua ghi gi. Them --confirm de ghi that.")

    # ---- filtered manifest: ONE split, shared by both arms ----------------
    #
    # Splitting each arm separately would be the subtle way to ruin this: two
    # runs of the same splitter on the same rows give the same partition only as
    # long as nothing about the input differs, and then the experiment silently
    # compares two models trained on two different train sets. One manifest, one
    # split, two --features_root values.
    if args.manifest:
        import os

        src = Path(args.manifest)
        keep_rel = {m["relative_path"] for m in matched}

        def _rel(p: str) -> str:
            return p.replace(os.sep, "/").split("dataset/features/", 1)[-1]

        with src.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            fields = reader.fieldnames or []
            rows = [r for r in reader if _rel(r.get("file_path", "")) in keep_rel]

        print(f"\n  Manifest goc             : {src.name}")
        print(f"  Dong con lai sau khi loc : {len(rows)}")
        dropped = len(keep_rel) - len(rows)
        if dropped:
            print(f"  Mau dung duoc nhung KHONG co trong manifest: {dropped}")

        if args.manifest_out and args.confirm:
            out = Path(args.manifest_out)
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=fields)
                w.writeheader()
                w.writerows(rows)
            print(f"  -> {out}")
        elif args.manifest_out:
            print("  (DRY RUN — chua ghi manifest)")

    if n_mismatch:
        print(f"\n  CANH BAO: {n_mismatch} mau co sequence khong khop landmarks_raw cua chinh no.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
