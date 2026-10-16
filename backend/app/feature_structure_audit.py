from __future__ import annotations
from pathlib import Path
from typing import Dict

def resolve_root(custom_root: str | None) -> Path:
    if custom_root:
        return Path(custom_root).expanduser().resolve()
    return Path("dataset") / "features"

def scan(root: str | None = None) -> Dict:
    FEATURES_ROOT = resolve_root(root)
    if not FEATURES_ROOT.exists():
        return {"error": "features root missing", "path": str(FEATURES_ROOT)}
    legacy = []
    misplaced = []
    for entry in FEATURES_ROOT.iterdir():
        if entry.is_dir():
            name = entry.name
            if name.startswith("class_"):
                legacy.append(name)
            elif name == "global_common":
                continue
            elif name == "_tenants":
                # Not a language root: one level of tenant partitions, each
                # containing its own language tree. Auditing them means
                # recursing one level deeper, which this scan does not do —
                # reporting them as malformed language roots would be worse
                # than skipping. Tracked in BACKEND_WORK_PLAN.md A4.
                continue
            else:
                # language root expected
                # check its children
                for child in entry.iterdir():
                    if child.is_dir():
                        if child.name.startswith("class_"):
                            misplaced.append(str(child))
    return {"root": str(FEATURES_ROOT), "legacy_roots": legacy, "misplaced_subdirs": misplaced}

if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", help="Custom features root path", default=None)
    args = ap.parse_args()
    print(json.dumps(scan(args.root), ensure_ascii=False, indent=2))
