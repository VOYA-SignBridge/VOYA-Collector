"""Apply CONFIRMED signer identity merges.

Usage:
    python scripts/apply_signer_merges.py                # dry-run (default)
    python scripts/apply_signer_merges.py --confirm      # write changes

Reads config/legacy_signer_merge.json (owner-confirmed merges only — this
script performs NO name heuristics itself). Effects on --confirm:
  - dataset/signers.csv: absorbed rows get is_active=0 (kept for audit,
    never deleted); canonical row keeps its display_name;
  - config/legacy_signer_mapping.json: every raw name in a merge group maps
    to the canonical signer_id, and the group is removed from
    merge_candidates_requiring_confirmation;
  - a timestamped backup of both files is created first.

Idempotent: re-running after apply changes nothing.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _backup(path: Path, backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_dir / f"{path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{path.suffix}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--merge-config", type=Path, default=REPO_ROOT / "config" / "legacy_signer_merge.json")
    ap.add_argument("--signers-csv", type=Path, default=REPO_ROOT / "dataset" / "signers.csv")
    ap.add_argument("--signer-mapping", type=Path, default=REPO_ROOT / "config" / "legacy_signer_mapping.json")
    ap.add_argument("--backup-dir", type=Path, default=REPO_ROOT / "dataset" / "backups")
    ap.add_argument("--confirm", action="store_true", help="Actually write changes (otherwise dry-run)")
    args = ap.parse_args()

    cfg = json.loads(args.merge_config.read_text(encoding="utf-8"))
    merges = cfg.get("merges", [])
    if not merges:
        print("No merges configured — nothing to do.")
        return 0

    with args.signers_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        signers = list(reader)
        fieldnames = list(reader.fieldnames or [])
    by_id = {s["signer_id"]: s for s in signers}

    mapping = json.loads(args.signer_mapping.read_text(encoding="utf-8"))
    name_to_id = mapping.get("legacy_name_to_signer_id", {})
    candidates = mapping.get("merge_candidates_requiring_confirmation", [])

    changes = []
    for m in merges:
        canon = m["canonical_signer_id"]
        if canon not in by_id:
            print(f"[ERROR] canonical signer {canon} not found in registry")
            return 2
        for absorbed in m["absorbed_signer_ids"]:
            row = by_id.get(absorbed)
            if row is None:
                print(f"[WARN] absorbed signer {absorbed} not in registry (already merged?)")
                continue
            if (row.get("is_active") or "1").strip() != "0":
                changes.append(f"signers.csv: {absorbed} ({row.get('display_name')}) -> is_active=0 (merged into {canon})")
        for name in m["all_names"]:
            if name_to_id.get(name) != canon:
                changes.append(f"mapping: '{name}' -> {canon} (was {name_to_id.get(name)})")

    remaining_candidates = [
        c for c in candidates
        if not any(set(c.get("names", [])) <= set(m["all_names"]) for m in merges)
    ]
    if len(remaining_candidates) != len(candidates):
        changes.append(f"mapping: resolved {len(candidates) - len(remaining_candidates)} merge-candidate group(s)")

    if not changes:
        print("Already applied — nothing to change (idempotent).")
        return 0

    print(("DRY-RUN — would apply:" if not args.confirm else "APPLYING:"))
    for c in changes:
        print(f"  {c}")
    if not args.confirm:
        print("\nRe-run with --confirm to write.")
        return 0

    _backup(args.signers_csv, args.backup_dir)
    _backup(args.signer_mapping, args.backup_dir)

    for m in merges:
        for absorbed in m["absorbed_signer_ids"]:
            if absorbed in by_id:
                by_id[absorbed]["is_active"] = "0"
        for name in m["all_names"]:
            name_to_id[name] = m["canonical_signer_id"]

    with args.signers_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(signers)
    mapping["legacy_name_to_signer_id"] = name_to_id
    mapping["merge_candidates_requiring_confirmation"] = remaining_candidates
    mapping["merges_applied"] = {"config": str(args.merge_config), "applied_at": datetime.utcnow().isoformat() + "Z"}
    args.signer_mapping.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Done. Merged registry + mapping updated (backups in dataset/backups/).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
