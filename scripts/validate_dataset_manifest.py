"""Validate manifest <-> filesystem consistency.

Usage:
    python scripts/validate_dataset_manifest.py --version isds2026_v1
    python scripts/validate_dataset_manifest.py --version isds2026_v1 --check-checksums

Checks:
  - manifest file's own sha256 matches the recorded .sha256 (immutability);
  - every manifest row's file exists (missing files);
  - every .npz under features-root appears in the manifest (orphan files);
  - optional (--check-checksums): per-file sha256 matches;
  - schema sanity via vocabulary v2 rules.

This script NEVER modifies data. Exit code 0 = consistent, 1 = problems found.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from processed.shared.vocabulary import validate_label_v2  # noqa: E402


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", required=True)
    ap.add_argument("--manifest-dir", type=Path, default=REPO_ROOT / "dataset" / "manifests")
    ap.add_argument("--features-root", type=Path, default=REPO_ROOT / "dataset" / "features")
    ap.add_argument("--check-checksums", action="store_true")
    args = ap.parse_args()

    manifest_path = args.manifest_dir / f"dataset_manifest_{args.version}.csv"
    sha_path = args.manifest_dir / f"dataset_manifest_{args.version}.sha256"
    if not manifest_path.exists():
        print(f"[ERROR] manifest not found: {manifest_path}")
        return 1

    problems = 0

    # 1. Manifest immutability
    if sha_path.exists():
        recorded = sha_path.read_text(encoding="utf-8").strip()
        actual = sha256_file(manifest_path)
        if recorded != actual:
            print(f"[FAIL] manifest checksum mismatch (recorded {recorded[:12]}..., actual {actual[:12]}...) "
                  f"— manifest was modified after release!")
            problems += 1
        else:
            print("[OK] manifest checksum matches (immutable)")
    else:
        print("[WARN] no .sha256 recorded for this manifest")

    with manifest_path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"[OK] manifest rows: {len(rows)}")

    # 2. Missing files + schema sanity (+ optional checksums)
    missing, bad_schema, bad_checksum = [], [], []
    manifest_files = set()
    for r in rows:
        p = REPO_ROOT / r["file_path"]
        manifest_files.add(p.resolve())
        if not p.exists():
            missing.append(r["file_path"])
            continue
        if (r.get("vocabulary_scope") or "").strip():
            errs = validate_label_v2(r)
            if errs:
                bad_schema.append({"sample_id": r["sample_id"], "errors": errs})
        if args.check_checksums:
            if sha256_file(p) != r["file_checksum"]:
                bad_checksum.append(r["file_path"])

    # 3. Orphans
    orphans = [str(p) for p in sorted(args.features_root.rglob("*.npz"))
               if p.resolve() not in manifest_files]

    for name, items in (("missing files", missing), ("schema violations", bad_schema),
                        ("checksum mismatches", bad_checksum), ("orphan files", orphans)):
        if items:
            problems += len(items)
            print(f"[FAIL] {name}: {len(items)}")
            for it in items[:5]:
                print(f"    {it}")
        else:
            print(f"[OK] no {name}")

    print(f"\n{'CONSISTENT' if problems == 0 else f'{problems} PROBLEM(S) FOUND'}")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
