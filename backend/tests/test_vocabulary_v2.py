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
    trainable_profiles,
    label_key_v2,
    select_rows_for_profile,
    semantic_label_from_slug,
    split_common_and_profile_labels,
    validate_label_v2,
)

PASSED: list = []
FAILED: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    """Ghi nhan ket qua, VA nem khi sai.

    Cau `raise` la bat buoc, khong phai trang tri. Tep nay von la script chay
    tay: verdict nam o `sys.exit(1 if FAILED else 0)` cuoi `main()`, nen
    `check` chi can ghi vao danh sach. Nhung pytest KHONG goi `main()` - no
    thu tung ham `test_*` mot. Khong co `raise` thi moi ham o day xanh vo
    dieu kien, ke ca khi moi phep kiem ben trong deu sai.

    Da do, khong phai suy doan: sua mot dieu kien thanh hang sai roi chay
    `pytest ...::test_config_defaults` van ra "1 passed".

    `main()` boc try/except quanh tung test nen che do chay tay van nguyen;
    khac biet duy nhat la no dung o phep kiem sai DAU TIEN trong mot ham thay
    vi gom het - dung cach pytest van bao loi.
    """
    if cond:
        PASSED.append(name)
        print(f"  PASS  {name}")
        return
    FAILED.append((name, str(detail)))
    print(f"  FAIL  {name}  -> {detail}")
    raise AssertionError(f"{name}" + (f"  -> {detail}" if detail else ""))


def test_scope_profile_rules():
    print("[V1 scope/profile rules]")
    check("alphabet is a recognition profile", "alphabet" in RECOGNITION_PROFILES,
          RECOGNITION_PROFILES)
    check("profile order starts with alphabet", RECOGNITION_PROFILES[0] == "alphabet")
    check("motion_type static valid",
          validate_label_v2({"vocabulary_scope": "profile_specific",
                             "recognition_profile": "alphabet", "motion_type": "static"}) == [])
    errs = validate_label_v2({"vocabulary_scope": "common", "motion_type": "wiggly"})
    check("invalid motion_type rejected", len(errs) == 1, errs)
    check("common + no profile: valid",
          validate_label_v2({"vocabulary_scope": "common", "recognition_profile": ""}) == [])
    errs = validate_label_v2({"vocabulary_scope": "common", "recognition_profile": "hoa_de"})
    check("common + profile: INVALID", len(errs) == 1, errs)
    errs = validate_label_v2({"vocabulary_scope": "profile_specific", "recognition_profile": ""})
    check("profile_specific without profile: INVALID", len(errs) == 1, errs)
    # TRAINABLE, not merely registered: legacy_unassigned is a registered
    # profile whose whole job is to mark rows nobody has classified, so
    # "profile_specific + legacy_unassigned" must stay invalid (asserted next).
    # The two sets were identical only while this list was a hardcoded 5-tuple
    # that happened to omit the sentinel.
    for p in trainable_profiles():
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
    check("alphabet key", label_key_v2("vn", "profile_specific", "alphabet", "a") == "vn/alphabet/a")
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
        {"vocabulary_scope": "profile_specific", "recognition_profile": "alphabet", "label_slug": "a-letter"},
        {"vocabulary_scope": "", "recognition_profile": "legacy_unassigned", "label_slug": "can-tho-word"},
        {"vocabulary_scope": "", "recognition_profile": "", "label_slug": "a"},
    ]


def test_profile_selection():
    print("[V3 subset selection]")
    rows = _rows()
    # Policy 2026-07-19: include_common DEFAULTS TO FALSE — profiles train independently.
    sel = select_rows_for_profile(rows, "hoa_de")
    check("DEFAULT: hoa_de only, NO common", [r["label_slug"] for r in sel] == ["rang-muoi"],
          [r["label_slug"] for r in sel])
    sel = select_rows_for_profile(rows, "alphabet")
    check("DEFAULT: alphabet only, NO common/regional",
          [r["label_slug"] for r in sel] == ["a-letter"], [r["label_slug"] for r in sel])
    sel = select_rows_for_profile(rows, "hoa_de", include_common=True)
    slugs = sorted(r["label_slug"] for r in sel)
    check("explicit include_common: common + hoa_de", slugs == ["cam-on", "rang-muoi", "xin-chao"], slugs)
    check("hoa_de excludes north + alphabet",
          all(r.get("recognition_profile") not in ("north", "alphabet") for r in sel))
    sel = select_rows_for_profile(rows, unified=True)
    slugs = sorted(r["label_slug"] for r in sel)
    check("unified = common + ALL valid profiles (incl. alphabet), NO legacy_unassigned",
          slugs == ["a-letter", "cam-on", "rang-muoi", "tu-bac", "xin-chao"], slugs)
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
