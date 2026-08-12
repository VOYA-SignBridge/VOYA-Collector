"""Report exact duplicates and near-duplicate candidates. REPORT ONLY.

This script NEVER deletes, moves or edits a sample. Near-duplicate detection is
a heuristic: a flagged pair is a CANDIDATE for human review, not a verdict.
Legitimately repeated signs from one signer in one session are expected to look
similar — the point is to surface pairs that are so close they are likely the
same recording counted twice, which would inflate any accuracy computed over a
split that separates them.

Two independent notions of "exact":
  * file-level   identical sha256 over the .npz bytes
  * content-level identical sha256 over the normalized (60,126) float32 array
    (catches the same sequence re-saved with different metadata/compression)

Near-duplicate score: cosine distance between L2-normalized flattened
sequences, computed WITHIN a class only (cross-class near-duplicates are a
labelling question, not a duplication question). Pairs are additionally tagged
with whether they share a session and/or a signer.

KNOWN LIMITATION (measured on isds2026_v3, 930 samples): the within-class
distance distribution is a smooth continuum with no natural cut-off --
cos<=0.0005 -> 93 pairs, <=0.001 -> 312, <=0.005 -> 1904, <=0.02 -> 3555 --
and it is dominated by STATIC alphabet classes, where a sign held still for
60 frames legitimately produces near-identical sequences. Treat this metric as
a triage aid for static vocabulary, not as evidence of accidental duplication.
Dynamic classes (e.g. hoa_de) are far more informative here. The default
threshold is therefore deliberately tight.

Usage:
    python scripts/audit_duplicate_samples.py
    python scripts/audit_duplicate_samples.py --manifest-version isds2026_v3 \
        --threshold 0.02 --out-dir reports
"""

from __future__ import annotations

import sys as _sys
sys_path_dir = __import__('pathlib').Path(__file__).resolve().parent
if str(sys_path_dir) not in _sys.path:
    _sys.path.insert(0, str(sys_path_dir))
import _console  # noqa: F401  (force UTF-8 console on Windows)

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_SHAPE = (60, 126)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_sequence(npz_path: Path) -> np.ndarray | None:
    try:
        with np.load(npz_path, allow_pickle=True) as z:
            for key in ("landmarks_normalized", "sequence", "features", "arr_0"):
                if key in z:
                    arr = np.asarray(z[key], dtype=np.float32)
                    return arr if arr.shape == EXPECTED_SHAPE else None
    except Exception:
        return None
    return None


def load_manifest_index(manifest_path: Path) -> dict:
    """file_path -> {label_key, signer_id, session_id, sample_id}."""
    index: dict = {}
    if not manifest_path or not manifest_path.exists():
        return index
    with manifest_path.open("r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            p = (r.get("file_path") or "").strip()
            if not p:
                continue
            index[Path(p).name] = {
                "sample_id": r.get("sample_id", ""),
                "label_key": r.get("label_key", ""),
                "signer_id": r.get("signer_id", ""),
                "session_id": r.get("session_id", ""),
            }
    return index


def sidecar_meta(npz_path: Path) -> dict:
    side = npz_path.with_suffix(".json")
    if side.exists():
        try:
            return json.loads(side.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--features-root", type=Path, default=REPO_ROOT / "dataset" / "features")
    ap.add_argument("--manifest-version", type=str, default="",
                    help="use dataset/manifests/dataset_manifest_<v>.csv for label/signer/session")
    ap.add_argument("--manifest", type=Path, default=None)
    ap.add_argument("--threshold", type=float, default=0.001,
                    help="cosine distance below which a within-class pair is a candidate "
                         "(tight by default; see the KNOWN LIMITATION note above)")
    ap.add_argument("--max-pairs", type=int, default=200, help="max candidate pairs to report")
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "reports")
    args = ap.parse_args()

    manifest_path = args.manifest
    if manifest_path is None and args.manifest_version:
        manifest_path = (REPO_ROOT / "dataset" / "manifests" /
                         f"dataset_manifest_{args.manifest_version}.csv")
    meta_index = load_manifest_index(manifest_path) if manifest_path else {}

    files = sorted(args.features_root.rglob("*.npz"))
    if not files:
        print(f"No .npz under {args.features_root}")
        return 0
    print(f"scanning {len(files)} sample(s) ...")

    by_file_hash: dict = defaultdict(list)
    by_content_hash: dict = defaultdict(list)
    records: list = []
    unreadable: list = []

    for p in files:
        rel = p.relative_to(REPO_ROOT).as_posix() if p.is_relative_to(REPO_ROOT) else str(p)
        try:
            raw_bytes = p.read_bytes()
        except Exception as exc:
            unreadable.append({"file": rel, "error": str(exc)})
            continue
        seq = load_sequence(p)
        if seq is None:
            unreadable.append({"file": rel, "error": "no usable (60,126) array"})
            continue

        info = meta_index.get(p.name, {})
        side = sidecar_meta(p)
        rec = {
            "file": rel,
            "name": p.name,
            "label_key": info.get("label_key") or p.parent.name,
            "signer_id": info.get("signer_id") or str(side.get("signer_id") or ""),
            "session_id": info.get("session_id") or str(side.get("session_id") or ""),
            "file_hash": sha256_bytes(raw_bytes),
            "content_hash": sha256_bytes(np.ascontiguousarray(seq).tobytes()),
        }
        records.append(rec)
        by_file_hash[rec["file_hash"]].append(rec)
        by_content_hash[rec["content_hash"]].append(rec)

        # keep a unit-norm descriptor for the near-duplicate pass
        v = seq.reshape(-1)
        n = float(np.linalg.norm(v))
        rec["_vec"] = (v / n) if n > 1e-8 else v

    exact_file = [g for g in by_file_hash.values() if len(g) > 1]
    exact_content = [g for g in by_content_hash.values()
                     if len(g) > 1 and len({r["file_hash"] for r in g}) > 1]

    # ---- near-duplicate candidates, within class only -----------------------
    by_class: dict = defaultdict(list)
    for r in records:
        by_class[r["label_key"]].append(r)

    candidates: list = []
    for label, group in sorted(by_class.items()):
        if len(group) < 2:
            continue
        M = np.stack([r["_vec"] for r in group])
        sim = M @ M.T
        n = len(group)
        for i in range(n):
            for j in range(i + 1, n):
                dist = float(1.0 - sim[i, j])
                if dist <= args.threshold:
                    a, b = group[i], group[j]
                    if a["content_hash"] == b["content_hash"]:
                        continue  # already reported as an exact content duplicate
                    candidates.append({
                        "label_key": label,
                        "cosine_distance": round(dist, 6),
                        "same_session": bool(a["session_id"]) and a["session_id"] == b["session_id"],
                        "same_signer": bool(a["signer_id"]) and a["signer_id"] == b["signer_id"],
                        "a": a["file"], "b": b["file"],
                        "a_session": a["session_id"], "b_session": b["session_id"],
                        "a_signer": a["signer_id"], "b_signer": b["signer_id"],
                    })
    candidates.sort(key=lambda c: c["cosine_distance"])

    n_exact_files = sum(len(g) - 1 for g in exact_file)
    n_exact_content = sum(len(g) - 1 for g in exact_content)
    same_session = sum(1 for c in candidates if c["same_session"])

    print(f"\nexact duplicate files (identical bytes)      : {len(exact_file)} group(s), "
          f"{n_exact_files} redundant file(s)")
    print(f"exact duplicate content (different bytes)    : {len(exact_content)} group(s), "
          f"{n_exact_content} redundant file(s)")
    print(f"near-duplicate candidates (cos <= {args.threshold}) : {len(candidates)} pair(s) "
          f"({same_session} within the same session)")
    if unreadable:
        print(f"unreadable / wrong-shape                     : {len(unreadable)}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "features_root": str(args.features_root),
        "manifest": str(manifest_path) if manifest_path else None,
        "threshold": args.threshold,
        "scanned": len(files),
        "usable": len(records),
        "summary": {
            "exact_file_duplicate_groups": len(exact_file),
            "exact_file_redundant": n_exact_files,
            "exact_content_duplicate_groups": len(exact_content),
            "exact_content_redundant": n_exact_content,
            "near_duplicate_candidates": len(candidates),
            "near_duplicate_same_session": same_session,
            "unreadable": len(unreadable),
        },
        "exact_file_duplicates": [[r["file"] for r in g] for g in exact_file],
        "exact_content_duplicates": [[r["file"] for r in g] for g in exact_content],
        "near_duplicate_candidates": candidates[:args.max_pairs],
        "unreadable": unreadable,
        "note": "REPORT ONLY — nothing was deleted or modified. Near-duplicate "
                "pairs require human review before any action.",
    }
    jpath = args.out_dir / "duplicate_audit.json"
    jpath.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# Duplicate audit\n",
             f"\nGenerated: {report['generated_at']}\n",
             "\n**Report only — nothing was deleted or modified.**\n",
             f"\nScanned {len(files)} file(s), {len(records)} usable.\n",
             "\n| finding | count |\n|---|---|\n"]
    for k, v in report["summary"].items():
        lines.append(f"| {k.replace('_', ' ')} | {v} |\n")

    if exact_file:
        lines.append("\n## Exact duplicate files (identical bytes)\n\n")
        for g in exact_file[:50]:
            lines.append(f"- `{g[0]['label_key']}`\n")
            for r in g:
                lines.append(f"  - `{r['file']}`\n")
    if exact_content:
        lines.append("\n## Identical content, different bytes\n\n")
        for g in exact_content[:50]:
            lines.append(f"- `{g[0]['label_key']}`\n")
            for r in g:
                lines.append(f"  - `{r['file']}`\n")
    if candidates:
        lines.append(f"\n## Near-duplicate candidates (cosine distance <= {args.threshold})\n\n")
        lines.append("| class | cos dist | same session | same signer | A | B |\n")
        lines.append("|---|---|---|---|---|---|\n")
        for c in candidates[:args.max_pairs]:
            lines.append(
                f"| `{c['label_key']}` | {c['cosine_distance']:.5f} | "
                f"{'yes' if c['same_session'] else 'no'} | "
                f"{'yes' if c['same_signer'] else 'no'} | "
                f"`{Path(c['a']).name}` | `{Path(c['b']).name}` |\n")
        by_label = Counter(c["label_key"] for c in candidates)
        lines.append("\n### Candidate pairs per class\n\n| class | pairs |\n|---|---|\n")
        for label, n in by_label.most_common():
            lines.append(f"| `{label}` | {n} |\n")
    mpath = args.out_dir / "duplicate_audit.md"
    mpath.write_text("".join(lines), encoding="utf-8")

    print(f"\njson     -> {jpath}")
    print(f"markdown -> {mpath}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
