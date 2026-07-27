#!/usr/bin/env python3
"""Detect mid-sample left/right slot flips in recorded landmark sequences.

MediaPipe classifies handedness per frame with no temporal state, so a single
physical hand can be labelled "Left" on one frame and "Right" on the next --
typically while rotating palm-to-back, or when the capture loop falls back to
the raw label because spatial continuity was lost. When that happens the same
hand jumps between the two halves of the 126-dim vector, and the sample encodes
a hand swap that never physically occurred.

Layout (verified against processed/shared/normalization.py and
backend/app/processing/keypoints_adapter.py):

    v[0:63]    left hand   21 landmarks x (x, y, z)
    v[63:126]  right hand
    an absent hand is all-zero, and normalize_single_hand() returns an all-zero
    hand untouched, so "the 63-block is all zero" is an exact absence test.

Per frame each sample is in one of four states:

    B  both hands present      L  left only
    R  right only              -  neither

Two findings are reported, deliberately kept apart because their strength
differs:

  * DIRECT flip -- adjacent frames go L->R or R->L. A hand cannot leave one
    anatomical slot and appear in the other between two consecutive frames
    while remaining the only hand visible. This is conclusive evidence of a
    labelling flip, not of signing.

  * GAPPED flip -- the single visible hand changes slot with only '-' frames in
    between. Consistent with a flip during a brief loss of detection, but also
    with a signer genuinely switching hands, so it is reported as suspicion,
    not proof.

Usage:
    python scripts/audit_handedness_flips.py --features-root dataset/features
    python scripts/audit_handedness_flips.py --dialect bang-chu-cai --out report.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

HAND_BLOCK = 63
FEATURE_KEY_PRIORITY = ("sequence", "features", "x", "data", "arr_0")


def _array_from_npz(npz) -> np.ndarray:
    for key in FEATURE_KEY_PRIORITY:
        if key in npz:
            return npz[key]
    for key in npz.keys():
        return npz[key]
    raise KeyError("no array found in npz archive")


def frame_states(seq: np.ndarray) -> str:
    """Map each frame to one of B / L / R / '-'."""
    left_present = np.any(seq[:, :HAND_BLOCK] != 0, axis=1)
    right_present = np.any(seq[:, HAND_BLOCK:] != 0, axis=1)

    states = []
    for l, r in zip(left_present, right_present):
        if l and r:
            states.append("B")
        elif l:
            states.append("L")
        elif r:
            states.append("R")
        else:
            states.append("-")
    return "".join(states)


def analyse(states: str) -> Dict[str, object]:
    """Count direct and gapped slot flips in a state string."""
    direct: List[Tuple[int, str]] = []
    for i in range(len(states) - 1):
        pair = states[i] + states[i + 1]
        if pair in ("LR", "RL"):
            direct.append((i, pair))

    # Gapped: walk the single-hand frames in order. A change of slot counts only
    # when at least one '-' frame sat between them and no 'B' did -- a 'B' means
    # both hands were genuinely visible, which explains the change, and no gap at
    # all means it is a direct flip, already counted above. The two categories
    # are kept disjoint so the totals can be added without double counting.
    gapped = 0
    last_single: Optional[str] = None
    saw_both_since = False
    saw_gap_since = False
    for s in states:
        if s == "B":
            saw_both_since = True
            continue
        if s == "-":
            saw_gap_since = True
            continue
        if (
            last_single is not None
            and s != last_single
            and not saw_both_since
            and saw_gap_since
        ):
            gapped += 1
        last_single = s
        saw_both_since = False
        saw_gap_since = False

    counts = Counter(states)
    single_frames = counts["L"] + counts["R"]
    minority = min(counts["L"], counts["R"])

    return {
        "states": states,
        "n_frames": len(states),
        "n_both": counts["B"],
        "n_left_only": counts["L"],
        "n_right_only": counts["R"],
        "n_empty": counts["-"],
        "direct_flips": len(direct),
        "direct_positions": [i for i, _ in direct[:10]],
        "gapped_flips": gapped,
        # Share of single-hand frames sitting in the minority slot: a one-handed
        # sample that flipped once mid-clip lands near 0.5, a clean one near 0.
        "minority_share": round(minority / single_frames, 4) if single_frames else 0.0,
    }


def load_manifest(path: Path) -> Dict[str, Dict[str, str]]:
    """sample_id -> {dialect, slug, signer_id} for grouping the report."""
    import csv

    meta: Dict[str, Dict[str, str]] = {}
    if not path.is_file():
        return meta
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            meta[str(row.get("sample_id") or "")] = {
                "dialect": row.get("dialect") or "",
                "slug": row.get("slug") or "",
                "signer_id": row.get("signer_id") or "",
            }
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--features-root", type=Path, default=Path("dataset/features"))
    parser.add_argument("--manifest", type=Path,
                        default=Path("dataset/manifests/dataset_manifest_isds2026_v6.csv"))
    parser.add_argument("--dialect", default="", help="restrict to one dialect/group")
    parser.add_argument("--out", type=Path, default=None, help="write a JSON report")
    parser.add_argument("--list", type=int, default=15, help="how many worst samples to print")
    args = parser.parse_args()

    meta = load_manifest(args.manifest)
    files = sorted(args.features_root.rglob("*.npz"))
    if not files:
        print(f"no .npz under {args.features_root}")
        return 2

    findings: List[Dict[str, object]] = []
    skipped = 0
    by_dialect: Dict[str, Counter] = defaultdict(Counter)
    by_signer: Dict[str, Counter] = defaultdict(Counter)
    by_class: Dict[str, Counter] = defaultdict(Counter)

    for path in files:
        sample_id = path.stem.replace("sample_", "")
        info = meta.get(sample_id, {})
        dialect = info.get("dialect") or path.parts[-3] if len(path.parts) >= 3 else ""
        if args.dialect and dialect != args.dialect:
            continue

        try:
            with np.load(path, allow_pickle=False) as data:
                seq = np.asarray(_array_from_npz(data), dtype=np.float32)
        except Exception:
            skipped += 1
            continue
        if seq.ndim != 2 or seq.shape[1] != 2 * HAND_BLOCK:
            skipped += 1
            continue

        result = analyse(frame_states(seq))
        result.update({
            "sample_id": sample_id,
            "dialect": dialect,
            "slug": info.get("slug", ""),
            "signer_id": info.get("signer_id", ""),
            "path": str(path),
        })

        flagged = result["direct_flips"] > 0
        suspicious = result["gapped_flips"] > 0
        for bucket, key in ((by_dialect, dialect), (by_signer, info.get("signer_id") or "(empty)"),
                            (by_class, info.get("slug") or "(unknown)")):
            bucket[key]["total"] += 1
            if flagged:
                bucket[key]["direct"] += 1
            if suspicious:
                bucket[key]["gapped"] += 1

        if flagged or suspicious:
            findings.append(result)

    total = sum(c["total"] for c in by_dialect.values())
    n_direct = sum(c["direct"] for c in by_dialect.values())
    n_gapped = sum(c["gapped"] for c in by_dialect.values())

    print(f"scanned {total} samples ({skipped} unreadable/skipped)")
    print(f"  DIRECT flips (conclusive) : {n_direct}  ({100 * n_direct / total:.1f}%)" if total else "")
    print(f"  GAPPED flips (suspicion)  : {n_gapped}  ({100 * n_gapped / total:.1f}%)" if total else "")

    def _table(title: str, bucket: Dict[str, Counter]) -> None:
        rows = [(k, c) for k, c in bucket.items() if c["direct"] or c["gapped"]]
        if not rows:
            return
        print(f"\n{title}")
        for key, c in sorted(rows, key=lambda kv: -kv[1]["direct"]):
            print(f"  {key:24} {c['direct']:4} direct / {c['gapped']:4} gapped  of {c['total']:4}")

    _table("by dialect", by_dialect)
    _table("by signer", by_signer)
    _table("by class", by_class)

    worst = sorted(findings, key=lambda f: (-f["direct_flips"], -f["minority_share"]))
    if worst:
        print(f"\nworst {min(args.list, len(worst))} samples")
        for f in worst[:args.list]:
            print(f"  {f['sample_id']}  {f['dialect']}/{f['slug']}  signer={f['signer_id'] or '-'}  "
                  f"direct={f['direct_flips']} gapped={f['gapped_flips']} "
                  f"minority={f['minority_share']}")
            print(f"      {f['states']}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({
            "scanned": total,
            "skipped": skipped,
            "direct_flip_samples": n_direct,
            "gapped_flip_samples": n_gapped,
            "by_dialect": {k: dict(v) for k, v in by_dialect.items()},
            "by_signer": {k: dict(v) for k, v in by_signer.items()},
            "by_class": {k: dict(v) for k, v in by_class.items()},
            "findings": findings,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
