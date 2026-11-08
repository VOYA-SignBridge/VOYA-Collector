from __future__ import annotations
import argparse, shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.migration.feature_structure_audit import scan

FEATURES_ROOT = REPO_ROOT / "dataset" / "features"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", action="store_true", help="Delete legacy root class_* folders")
    args = ap.parse_args()
    res = scan()
    legacy = res.get("legacy_roots", [])
    print({"legacy": legacy, "delete": args.delete})
    if args.delete:
        for name in legacy:
            p = FEATURES_ROOT / name
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
        print({"removed": len(legacy)})

if __name__ == "__main__":
    main()
