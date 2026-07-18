"""Standalone tests for vocabulary schema v2 (processed/shared/vocabulary.py).

Run:  python tests/test_vocabulary_v2.py   (from backend/, or repo root)
Pure stdlib — no torch/numpy/pydantic needed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from processed.shared.vocabulary import (  # noqa: E402
    LEGACY_UNASSIGNED,
    RECOGNITION_PROFILES,
    check_label_collisions,
    label_key_v2,
    select_rows_for_profile,
    semantic_label_from_slug,
    split_common_and_profile_labels,
    validate_label_v2,
)

PASSED: list = []
FAILED: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append((name, str(detail)))
        print(f"  FAIL  {name}  -> {detail}")


def test_scope_profile_rules():
    print("[V1 scope/profile rules]")
    check("common + no profile: valid",
          validate_label_v2({"vocabulary_scope": "common", "recognition_profile": ""}) == [])
    errs = validate_label_v2({"vocabulary_scope": "common", "recognition_profile": "hoa_de"})
    check("common + profile: INVALID", len(errs) == 1, errs)
    errs = validate_label_v2({"vocabulary_scope": "profile_specific", "recognition_profile": ""})
    check("profile_specific without profile: INVALID", len(errs) == 1, errs)
    for p in RECOGNITION_PROFILES:
        check(f"profile_specific + {p}: valid",
              validate_label_v2({"vocabulary_scope": "profile_specific", "recognition_profile": p}) == [])
    errs = validate_label_v2({"vocabulary_scope": "profile_specific", "recognition_profile": LEGACY_UNASSIGNED})
    check("profile_specific + legacy_unassigned: INVALID (not trainable)", len(errs) == 1, errs)
    check("empty scope + legacy_unassigned: allowed (pending review)",
          validate_label_v2({"vocabulary_scope": "", "recognition_profile": LEGACY_UNASSIGNED}) == [])
    errs = validate_label_v2({"vocabulary_scope": "bogus", "recognition_profile": ""})
    check("invalid scope enum rejected", len(errs) == 1, errs)


def test_label_key_generation():
    print("[V2 label key]")
    check("common key", label_key_v2("vn", "common", "", "cam-on") == "vn/common/cam-on")
    check("profile key", label_key_v2("vn", "profile_specific", "hoa_de", "rang-muoi") == "vn/hoa_de/rang-muoi")
    check("north key", label_key_v2("vn", "profile_specific", "north", "tu-mien-bac") == "vn/north/tu-mien-bac")
    try:
        label_key_v2("vn", "", "", "x")
        check("unassigned row raises", False)
    except ValueError:
        check("unassigned row raises", True)
    try:
        label_key_v2("vn", "profile_specific", LEGACY_UNASSIGNED, "x")
        check("legacy_unassigned raises", False)
    except ValueError:
        check("legacy_unassigned raises", True)
    check("semantic from slug", semantic_label_from_slug("rang-muoi") == "rang_muoi")


def _rows():
    return [
        {"vocabulary_scope": "common", "recognition_profile": "", "label_slug": "cam-on"},
        {"vocabulary_scope": "common", "recognition_profile": "", "label_slug": "xin-chao"},
        {"vocabulary_scope": "profile_specific", "recognition_profile": "hoa_de", "label_slug": "rang-muoi"},
        {"vocabulary_scope": "profile_specific", "recognition_profile": "north", "label_slug": "tu-bac"},
        {"vocabulary_scope": "", "recognition_profile": "legacy_unassigned", "label_slug": "can-tho-word"},
        {"vocabulary_scope": "", "recognition_profile": "", "label_slug": "a"},
    ]


def test_profile_selection():
    print("[V3 subset selection]")
    rows = _rows()
    sel = select_rows_for_profile(rows, "hoa_de", include_common=True)
    slugs = sorted(r["label_slug"] for r in sel)
    check("hoa_de = common + hoa_de only", slugs == ["cam-on", "rang-muoi", "xin-chao"], slugs)
    check("hoa_de excludes north", all(r.get("recognition_profile") != "north" for r in sel))
    sel = select_rows_for_profile(rows, "hoa_de", include_common=False)
    check("no-common: only hoa_de", [r["label_slug"] for r in sel] == ["rang-muoi"])
    sel = select_rows_for_profile(rows, unified=True)
    slugs = sorted(r["label_slug"] for r in sel)
    check("unified = common + all valid profiles, NO legacy_unassigned",
          slugs == ["cam-on", "rang-muoi", "tu-bac", "xin-chao"], slugs)
    try:
        select_rows_for_profile(rows, "south_east")
        check("invalid profile raises", False)
    except ValueError:
        check("invalid profile raises", True)
    try:
        select_rows_for_profile(rows, "north", unified=True)
        check("unified + profile mutually exclusive", False)
    except ValueError:
        check("unified + profile mutually exclusive", True)


def test_collisions_and_partition():
    print("[V4 collision + partition]")
    rows = _rows()
    check("no collision in clean set", check_label_collisions(rows) == [])
    rows2 = rows + [{"vocabulary_scope": "profile_specific", "recognition_profile": "north", "label_slug": "cam-on"}]
    check("collision detected (cam-on in common and north)", check_label_collisions(rows2) == ["cam-on"])
    common, spec = split_common_and_profile_labels(
        ["vn/common/cam-on", "vn/hoa_de/rang-muoi", "vn/north/tu-bac"])
    check("partition common", common == ["vn/common/cam-on"], common)
    check("partition specific", spec == ["vn/hoa_de/rang-muoi", "vn/north/tu-bac"], spec)


def main() -> int:
    for fn in (test_scope_profile_rules, test_label_key_generation,
               test_profile_selection, test_collisions_and_partition):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            FAILED.append((fn.__name__, f"exception: {exc!r}"))
            print(f"  FAIL  {fn.__name__} -> exception: {exc!r}")
    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for n, d in FAILED:
        print(f"  FAILED: {n}: {d}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
