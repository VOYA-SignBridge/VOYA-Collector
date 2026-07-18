"""Quarantine orphan/invalid dataset files — never deletes anything.

Usage:
    python scripts/quarantine_files.py                 # dry-run: show what would move
    python scripts/quarantine_files.py --confirm       # move decision=quarantine files

Reads config/orphan_file_decisions.json. Only entries whose decision is
exactly "quarantine" are moved (sidecar JSON moves along with the npz), into
dataset/quarantine/<timestamp>/ preserving the relative path, with a
quarantine_log.json recording provenance. 'pending' and 'keep' entries are
never touched. Restoring = moving the file back manually (log has both paths).
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--decisions", type=Path, default=REPO_ROOT / "config" / "orphan_file_decisions.json")
    ap.add_argument("--quarantine-root", type=Path, default=REPO_ROOT / "dataset" / "quarantine")
    ap.add_argument("--confirm", action="store_true", help="Actually move files (otherwise dry-run)")
    args = ap.parse_args()

    cfg = json.loads(args.decisions.read_text(encoding="utf-8"))
    entries = cfg.get("files", [])
    to_move, pending, keep, missing = [], 0, 0, []
    for e in entries:
        decision = (e.get("decision") or "pending").strip()
        if decision == "keep":
            keep += 1
            continue
        if decision != "quarantine":
            pending += 1
            continue
        src = REPO_ROOT / e["path"]
        if not src.exists():
            missing.append(e["path"])
            continue
        to_move.append((src, e))

    print(f"decisions: quarantine={len(to_move)} pending={pending} keep={keep} "
          f"missing={len(missing)}")
    for p in missing:
        print(f"  [WARN] listed but not found on disk: {p}")
    if not to_move:
        print("Nothing marked decision='quarantine' — edit the decisions file first.")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_root = args.quarantine_root / stamp
    log = []
    for src, e in to_move:
        rel = src.relative_to(REPO_ROOT)
        dest = dest_root / rel
        moves = [(src, dest)]
        sidecar = src.with_suffix(".json")
        if sidecar.exists():
            moves.append((sidecar, dest_root / sidecar.relative_to(REPO_ROOT)))
        for s, d in moves:
            print(f"  {'MOVE' if args.confirm else 'would move'}: {s.relative_to(REPO_ROOT)} -> {d.relative_to(REPO_ROOT)}")
        if args.confirm:
            for s, d in moves:
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(s), str(d))
            log.append({"from": str(rel), "to": str(dest.relative_to(REPO_ROOT)),
                        "reason": e.get("reason", ""), "quarantined_at": stamp})

    if args.confirm:
        dest_root.mkdir(parents=True, exist_ok=True)
        (dest_root / "quarantine_log.json").write_text(
            json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nQuarantined {len(log)} file(s) -> {dest_root} (log: quarantine_log.json). "
              f"Nothing was deleted.")
    else:
        print("\nDry-run only. Re-run with --confirm to move.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
