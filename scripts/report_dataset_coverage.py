"""Dataset coverage report over a versioned manifest.

Usage:
    python scripts/report_dataset_coverage.py --version isds2026_v2
    python scripts/report_dataset_coverage.py --version isds2026_v2 --json-out reports/coverage_isds2026_v2.json

Reports coverage by recognition profile, label, signer and session, and warns on:
  - labels with < --min-signers distinct signers (signer-disjoint eval impossible);
  - labels with < --min-sessions distinct sessions;
  - labels with no raw landmarks at all;
  - class imbalance (max/min sample ratio above --imbalance-ratio);
  - labels whose vocabulary metadata is still unassigned (needs review);
  - samples with unresolved signer_id.

Read-only. Exit code: 0 (even with warnings) unless --strict, then 1 when any
warning fires — usable as a release gate.
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
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", required=True)
    ap.add_argument("--manifest-dir", type=Path, default=REPO_ROOT / "dataset" / "manifests")
    ap.add_argument("--min-signers", type=int, default=2)
    ap.add_argument("--min-sessions", type=int, default=2)
    ap.add_argument("--imbalance-ratio", type=float, default=4.0)
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--strict", action="store_true", help="Exit 1 when any warning fires (release gate)")
    args = ap.parse_args()

    manifest_path = args.manifest_dir / f"dataset_manifest_{args.version}.csv"
    if not manifest_path.exists():
        print(f"[ERROR] manifest not found: {manifest_path}")
        return 2
    with manifest_path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    def prof(r):
        scope = (r.get("vocabulary_scope") or "").strip()
        if scope == "common":
            return "common"
        if scope == "profile_specific":
            return (r.get("recognition_profile") or "?").strip() or "?"
        return "<unassigned>"

    by_profile = defaultdict(list)
    by_label = defaultdict(list)
    for r in rows:
        by_profile[prof(r)].append(r)
        by_label[r["label_key"]].append(r)

    report = {
        "version": args.version,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_samples": len(rows),
        "profiles": {},
        "labels": {},
        "warnings": [],
    }

    print(f"=== Dataset coverage — {args.version} ({len(rows)} samples) ===\n")
    print(f"{'profile':<14}{'samples':>8}{'labels':>8}{'signers':>8}{'sessions':>9}{'raw':>6}"
          f"{'motion(st/dy/mx/?)':>20}{'disjoint-ready':>15}")
    for p, prows in sorted(by_profile.items()):
        signers = {(r.get('signer_id') or '').strip() for r in prows} - {""}
        sessions = {(r.get('session_id') or '').strip() for r in prows} - {""}
        labels = {r['label_key'] for r in prows}
        raw = sum(1 for r in prows if r.get("raw_landmarks_available") == "1")
        motion = Counter((r.get("motion_type") or "").strip() or "unknown" for r in prows)
        # Signer-disjoint readiness: EVERY label in the profile needs >= 2
        # distinct signers, otherwise a strict group split cannot cover it.
        label_signers = defaultdict(set)
        for r in prows:
            s = (r.get('signer_id') or '').strip()
            if s:
                label_signers[r['label_key']].add(s)
        blocking = sorted(lk for lk in labels if len(label_signers.get(lk, set())) < 2)
        # A 3-way (train/val/test) group-disjoint split additionally needs at
        # least 3 distinct signers overall — 2 signers can only fill train.
        disjoint_ready = (not blocking) and len(signers) >= 3
        report["profiles"][p] = {
            "samples": len(prows), "labels": len(labels),
            "signers": sorted(signers), "sessions": len(sessions), "raw_samples": raw,
            "motion_types": dict(motion),
            "signer_disjoint_ready": disjoint_ready,
            "signer_disjoint_blocking_labels": blocking,
        }
        mo = f"{motion.get('static',0)}/{motion.get('dynamic',0)}/{motion.get('mixed',0)}/{motion.get('unknown',0)}"
        print(f"{p:<14}{len(prows):>8}{len(labels):>8}{len(signers):>8}{len(sessions):>9}{raw:>6}"
              f"{mo:>20}{('YES' if disjoint_ready else 'no'):>15}")
        if blocking:
            print(f"{'':<14}  blocked by {len(blocking)} label(s) with <2 signers, e.g. {blocking[:3]}")
        elif not disjoint_ready:
            print(f"{'':<14}  blocked: only {len(signers)} distinct signer(s) — a 3-way split needs >= 3")

    warn = report["warnings"].append
    counts = {k: len(v) for k, v in by_label.items()}
    if counts:
        mx, mn = max(counts.values()), min(counts.values())
        if mn > 0 and mx / mn > args.imbalance_ratio:
            worst = min(counts, key=counts.get)
            best = max(counts, key=counts.get)
            warn({"type": "class_imbalance",
                  "detail": f"max/min = {mx}/{mn} = {mx/mn:.1f}x (> {args.imbalance_ratio}x): "
                            f"{best}={mx} vs {worst}={mn}"})

    unresolved_signers = sum(1 for r in rows if not (r.get("signer_id") or "").strip())
    if unresolved_signers:
        warn({"type": "unresolved_signer", "detail": f"{unresolved_signers} sample(s) without signer_id"})

    for lk, lrows in sorted(by_label.items()):
        signers = {(r.get('signer_id') or '').strip() for r in lrows} - {""}
        sessions = {(r.get('session_id') or '').strip() for r in lrows} - {""}
        raw = sum(1 for r in lrows if r.get("raw_landmarks_available") == "1")
        scope = (lrows[0].get("vocabulary_scope") or "").strip()
        entry = {"samples": len(lrows), "signers": len(signers), "sessions": len(sessions),
                 "raw_samples": raw, "vocabulary_scope": scope or "<unassigned>"}
        report["labels"][lk] = entry
        if len(signers) < args.min_signers:
            warn({"type": "few_signers", "label": lk,
                  "detail": f"{len(signers)} signer(s) < {args.min_signers} — signer-disjoint eval impossible"})
        if len(sessions) < args.min_sessions:
            warn({"type": "few_sessions", "label": lk,
                  "detail": f"{len(sessions)} session(s) < {args.min_sessions}"})
        if raw == 0:
            warn({"type": "no_raw_landmarks", "label": lk,
                  "detail": "no sample has raw landmarks (preprocessing ablation impossible)"})
        if not scope:
            warn({"type": "metadata_unreviewed", "label": lk,
                  "detail": "vocabulary_scope unassigned — label pending review"})

    print(f"\nWarnings: {len(report['warnings'])}")
    by_type = Counter(w["type"] for w in report["warnings"])
    for t, n in sorted(by_type.items()):
        print(f"  {t}: {n}")
        for w in [w for w in report["warnings"] if w["type"] == t][:3]:
            print(f"    - {w.get('label', '')} {w['detail']}")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON -> {args.json_out}")

    return 1 if (args.strict and report["warnings"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
