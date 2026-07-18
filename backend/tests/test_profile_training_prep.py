"""Standalone test: profile-training data prep against the REAL versioned split.

Validates (without torch) exactly the subset/label-map rules train_tcn.py
applies in profile mode, on processed/splits/versions/hoa_de_sample_v1/.
Skips gracefully if that split has not been generated yet.

Run:  python tests/test_profile_training_prep.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from processed.shared.vocabulary import (  # noqa: E402
    check_label_collisions,
    label_key_v2,
    select_rows_for_profile,
    split_common_and_profile_labels,
)

SPLIT_DIR = REPO_ROOT / "processed" / "splits" / "versions" / "hoa_de_sample_v1"

PASSED: list = []
FAILED: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append((name, detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"  -> {detail}"))


def _load(name: str):
    with (SPLIT_DIR / f"{name}.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    if not SPLIT_DIR.exists():
        print(f"SKIP: {SPLIT_DIR} not generated (run make_splits --dataset_manifest ... first)")
        return 0

    train, val, test = _load("train"), _load("val"), _load("test")
    print("[P1 subset semantics on real split]")
    sel = select_rows_for_profile(train, "hoa_de", include_common=True)
    check("every train row selectable for hoa_de profile", len(sel) == len(train),
          f"{len(sel)}/{len(train)}")
    check("no row from another profile",
          all((r.get("recognition_profile") or "") in ("", "hoa_de") for r in train))
    check("no legacy_unassigned row",
          all((r.get("recognition_profile") or "") != "legacy_unassigned" for r in train))

    print("[P2 label keys + maps]")
    keys = set()
    for r in train:
        k = label_key_v2(r.get("language") or "vn", r["vocabulary_scope"],
                         r["recognition_profile"], r["slug"])
        keys.add(k)
    check("7 classes in train", len(keys) == 7, sorted(keys))
    check("all keys are vn/hoa_de/*", all(k.startswith("vn/hoa_de/") for k in keys), sorted(keys))
    common, spec = split_common_and_profile_labels(sorted(keys))
    check("common label list empty (none confirmed common yet)", common == [], common)
    check("7 profile-specific labels", len(spec) == 7)
    check("no common/profile collision", check_label_collisions(train) == [])

    print("[P3 val/test label space subset of train]")
    for name, rows in (("val", val), ("test", test)):
        rows_keys = {label_key_v2(r.get("language") or "vn", r["vocabulary_scope"],
                                  r["recognition_profile"], r["slug"]) for r in rows}
        check(f"{name} labels ⊆ train labels", rows_keys <= keys, rows_keys - keys)

    print("[P4 split metadata]")
    meta = (SPLIT_DIR / "split_metadata.json").read_text(encoding="utf-8")
    check("metadata records manifest checksum", "dataset_manifest_checksum" in meta)
    check("metadata records seed", '"seed": 42' in meta)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for n, d in FAILED:
        print(f"  FAILED: {n}: {d}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
