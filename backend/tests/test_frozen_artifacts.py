"""Standalone test: frozen manifests/splits must never be modified.

Run:  python tests/test_frozen_artifacts.py
Verifies every released manifest still matches its recorded sha256, and that
frozen split versions still reference their original manifest checksum.
Skips versions that don't exist locally.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "dataset" / "manifests"
SPLITS_DIR = REPO_ROOT / "processed" / "splits"

PASSED: list = []
FAILED: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append((name, detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"  -> {detail}"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    print("[F1 manifest immutability]")
    found = 0
    for sha_path in sorted(MANIFEST_DIR.glob("dataset_manifest_*.sha256")):
        version = sha_path.stem.replace("dataset_manifest_", "")
        manifest = MANIFEST_DIR / f"dataset_manifest_{version}.csv"
        if not manifest.exists():
            check(f"{version}: manifest file exists for recorded checksum", False)
            continue
        found += 1
        recorded = sha_path.read_text(encoding="utf-8").strip()
        check(f"{version}: sha256 unchanged", sha256_file(manifest) == recorded)
    check("at least one released manifest present", found >= 1, found)

    print("[F2 legacy root splits untouched by v2 tooling]")
    for name in ("train.csv", "val.csv", "test.csv"):
        check(f"legacy {name} still present", (SPLITS_DIR / name).exists())

    print("[F3 split versions reference their manifest checksum]")
    for meta_path in sorted((SPLITS_DIR / "versions").glob("*/split_metadata.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        version = meta_path.parent.name
        m = Path(meta.get("dataset_manifest", ""))
        if not m.is_absolute():
            m = REPO_ROOT / m
        if m.exists():
            check(f"{version}: manifest checksum still matches",
                  sha256_file(m) == meta.get("dataset_manifest_checksum"),
                  str(m))
        for split_name in ("train", "val", "test"):
            check(f"{version}: {split_name}.csv present",
                  (meta_path.parent / f"{split_name}.csv").exists())

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for n, d in FAILED:
        print(f"  FAILED: {n}: {d}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
