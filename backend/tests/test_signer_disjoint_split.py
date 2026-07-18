"""Standalone tests for manifest-based profile splits (make_splits v2 mode).

Run:  python tests/test_signer_disjoint_split.py
Pure stdlib — imports split_from_manifest directly.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from processed.splits.make_splits import split_from_manifest  # noqa: E402

PASSED: list = []
FAILED: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append((name, detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"  -> {detail}"))


def _mk_manifest_rows():
    """Synthetic manifest: 3 common classes + 2 hoa_de + 1 north, 6 signers,
    every class covered by >= 3 signers so strict isolation is feasible."""
    rng = random.Random(7)
    rows = []
    signers = [f"S{i:03d}" for i in range(1, 7)]
    classes = [
        ("cam-on", "common", ""), ("xin-chao", "common", ""), ("tam-biet", "common", ""),
        ("rang-muoi", "profile_specific", "hoa_de"), ("cat-ky", "profile_specific", "hoa_de"),
        ("tu-bac", "profile_specific", "north"),
    ]
    n = 0
    for slug, scope, profile in classes:
        for s in signers:
            for _ in range(rng.randint(3, 5)):
                n += 1
                rows.append({
                    "sample_id": f"smp{n:04d}", "slug": slug, "label_slug": slug,
                    "language": "vn", "vocabulary_scope": scope, "recognition_profile": profile,
                    "signer_id": s, "session_id": "x", "file_path": f"f{n}.npz",
                })
    return rows


def main() -> int:
    rows = _mk_manifest_rows()

    print("[S1 profile subset + strict signer disjoint]")
    train, val, test, rep = split_from_manifest(
        rows, split_mode="strict_signer_disjoint", recognition_profile="hoa_de",
        include_common=True, seed=42)
    keys = set(rep["label_keys"])
    check("classes = 3 common + 2 hoa_de", rep["num_classes"] == 5, rep["num_classes"])
    check("no north label in subset", not any("/north/" in k for k in keys), keys)
    check("common included exactly once each",
          sum(1 for k in keys if "/common/" in k) == 3, keys)
    tr_s, va_s, te_s = set(rep["signers"]["train"]), set(rep["signers"]["val"]), set(rep["signers"]["test"])
    check("train/val signers disjoint", tr_s.isdisjoint(va_s), (tr_s, va_s))
    check("train/test signers disjoint", tr_s.isdisjoint(te_s), (tr_s, te_s))
    check("val/test signers disjoint", va_s.isdisjoint(te_s), (va_s, te_s))
    check("all classes in train (coverage)", rep["class_coverage"]["train"] == 1.0, rep["class_coverage"])
    check("manifest checksum field slot present later (report has counts)",
          rep["counts"]["train"] > 0 and rep["counts"]["test"] > 0, rep["counts"])

    print("[S2 reproducibility]")
    t2, v2, e2, rep2 = split_from_manifest(
        _mk_manifest_rows(), split_mode="strict_signer_disjoint", recognition_profile="hoa_de",
        include_common=True, seed=42)
    check("same seed -> same signer assignment", rep2["signers"] == rep["signers"])

    print("[S3 unified]")
    _, _, _, rep_u = split_from_manifest(
        _mk_manifest_rows(), split_mode="strict_signer_disjoint", unified=True, seed=42)
    check("unified has all 6 classes", rep_u["num_classes"] == 6, rep_u["num_classes"])

    print("[S4 no-common]")
    _, _, _, rep_nc = split_from_manifest(
        _mk_manifest_rows(), split_mode="strict_signer_disjoint",
        recognition_profile="hoa_de", include_common=False, seed=42)
    check("no-common -> only 2 hoa_de classes", rep_nc["num_classes"] == 2, rep_nc["label_keys"])

    print("[S5 hard failures]")
    bad = _mk_manifest_rows()
    bad[0]["signer_id"] = ""
    try:
        split_from_manifest(bad, split_mode="strict_signer_disjoint",
                            recognition_profile="hoa_de", seed=42)
        check("unresolved signer_id fails", False)
    except SystemExit as e:
        check("unresolved signer_id fails", "no signer_id" in str(e), str(e))

    collide = _mk_manifest_rows() + [{
        "sample_id": "smpX", "slug": "cam-on", "label_slug": "cam-on", "language": "vn",
        "vocabulary_scope": "profile_specific", "recognition_profile": "hoa_de",
        "signer_id": "S001", "session_id": "x", "file_path": "fx.npz"}]
    try:
        split_from_manifest(collide, split_mode="strict_signer_disjoint",
                            recognition_profile="hoa_de", seed=42)
        check("common/profile collision fails", False)
    except SystemExit as e:
        check("common/profile collision fails", "collision" in str(e), str(e))

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for n, d in FAILED:
        print(f"  FAILED: {n}: {d}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
