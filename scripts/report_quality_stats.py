"""Pass / warn / reject statistics per collection campaign.

Reads the append-only capture-attempt audit log written by
app/processing/quality.record_quality_attempt (default
dataset/quality_attempts.jsonl). That log contains no landmarks and no video —
only the verdict, the metrics and the thresholds in force — and is never read
by the manifest builder, so a rejected attempt can never become training data.

Usage:
    python scripts/report_quality_stats.py
    python scripts/report_quality_stats.py --campaign isds2026_v4 --out-dir reports
"""

from __future__ import annotations

import sys as _sys
sys_path_dir = __import__('pathlib').Path(__file__).resolve().parent
if str(sys_path_dir) not in _sys.path:
    _sys.path.insert(0, str(sys_path_dir))
import _console  # noqa: F401  (force UTF-8 console on Windows)

import argparse
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = REPO_ROOT / "dataset" / "quality_attempts.jsonl"

STATUSES = ("accepted", "flagged", "rejected")


def load(path: Path, campaign: str | None) -> list:
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if campaign and str(rec.get("campaign") or "") != campaign:
                continue
            out.append(rec)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", type=Path, default=DEFAULT_LOG)
    ap.add_argument("--campaign", type=str, default=None)
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "reports")
    args = ap.parse_args()

    recs = load(args.log, args.campaign)
    if not recs:
        print(f"No attempt records in {args.log}"
              + (f" for campaign '{args.campaign}'" if args.campaign else ""))
        print("(the log is written by the live-capture path; it stays empty until "
              "a collection campaign runs)")
        return 0

    by_status = Counter(r.get("status", "?") for r in recs)
    by_campaign = Counter(r.get("campaign") or "<none>" for r in recs)
    by_signer: dict = defaultdict(Counter)
    by_profile: dict = defaultdict(Counter)
    by_label: dict = defaultdict(Counter)
    flags = Counter()
    qc_versions = Counter()
    metric_pool: dict = defaultdict(list)

    for r in recs:
        st = r.get("status", "?")
        by_signer[r.get("signer_id") or "<none>"][st] += 1
        by_profile[r.get("recognition_profile") or "<none>"][st] += 1
        by_label[r.get("label") or "<none>"][st] += 1
        qc_versions[r.get("quality_config_version") or "<none>"] += 1
        for code in str(r.get("flags") or "").split(","):
            if code.strip():
                flags[code.strip()] += 1
        m = r.get("metrics") or {}
        for k in ("completeness", "jitter_p95", "any_hand_ratio",
                  "left_hand_ratio", "right_hand_ratio", "both_hands_ratio"):
            if isinstance(m.get(k), (int, float)):
                metric_pool[k].append(float(m[k]))

    total = len(recs)
    accepted = by_status.get("accepted", 0)
    flagged = by_status.get("flagged", 0)
    rejected = by_status.get("rejected", 0)
    kept = accepted + flagged

    print(f"attempts        : {total}")
    for st in STATUSES:
        n = by_status.get(st, 0)
        print(f"  {st:<9}: {n:5d}  ({n / total:6.1%})")
    print(f"retention (kept): {kept}/{total} ({kept / total:.1%})")
    if len(qc_versions) > 1:
        print(f"\n[WARN] attempts span {len(qc_versions)} quality_config_versions: "
              f"{dict(qc_versions)} — do not pool them in one QC ablation.")
    else:
        print(f"quality_config  : {next(iter(qc_versions))}")

    if flags:
        print("\nflag frequency:")
        for code, n in flags.most_common():
            print(f"  {n:5d}  {code}")

    print("\nper signer (accepted/flagged/rejected):")
    for s, c in sorted(by_signer.items()):
        print(f"  {s:<12} {c.get('accepted', 0):4d} / {c.get('flagged', 0):4d} "
              f"/ {c.get('rejected', 0):4d}")

    print("\nper profile:")
    for p, c in sorted(by_profile.items()):
        tot = sum(c.values())
        print(f"  {p:<12} n={tot:4d}  reject_rate={c.get('rejected', 0) / max(1, tot):.1%}")

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "log": str(args.log),
        "campaign_filter": args.campaign,
        "totals": {"attempts": total, "accepted": accepted, "flagged": flagged,
                   "rejected": rejected, "kept": kept,
                   "retention_rate": round(kept / total, 4),
                   "reject_rate": round(rejected / total, 4)},
        "by_campaign": dict(by_campaign),
        "by_status": dict(by_status),
        "quality_config_versions": dict(qc_versions),
        "flag_frequency": dict(flags),
        "by_signer": {k: dict(v) for k, v in by_signer.items()},
        "by_profile": {k: dict(v) for k, v in by_profile.items()},
        "by_label": {k: dict(v) for k, v in by_label.items()},
        "metric_summary": {
            k: {"n": len(v), "mean": round(statistics.mean(v), 5),
                "median": round(statistics.median(v), 5),
                "min": round(min(v), 5), "max": round(max(v), 5)}
            for k, v in metric_pool.items() if v
        },
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    tag = args.campaign or "all"
    out = args.out_dir / f"quality_stats_{tag}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\njson -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
