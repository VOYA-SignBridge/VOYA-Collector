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
    # blank a row that is INSIDE the default (profile-only) subset
    next(r for r in bad if r["recognition_profile"] == "hoa_de")["signer_id"] = ""
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
        # collision is only reachable when common is explicitly included
        split_from_manifest(collide, split_mode="strict_signer_disjoint",
                            recognition_profile="hoa_de", include_common=True, seed=42)
        check("common/profile collision fails", False)
    except SystemExit as e:
        check("common/profile collision fails", "collision" in str(e), str(e))

    # New default policy: without include_common the subset is profile-only.
    _, _, _, rep_def = split_from_manifest(
        _mk_manifest_rows(), split_mode="strict_signer_disjoint",
        recognition_profile="hoa_de", seed=42)
    check("default excludes common (2 hoa_de classes only)",
          rep_def["num_classes"] == 2, rep_def["label_keys"])

    print("[S5 dominant signers must not empty a split]")
    # Regression: the count-matching greedy assigns whole signers to whichever
    # split keeps per-class sample counts closest to target, with no notion of
    # coverage. Given two signers that hold most of the data it emptied val
    # entirely — real alphabet data (S001=987, S002=708 of 2482) hit exactly
    # this, and hoa_de_signer_disjoint_v1/_v3 had already reached disk with
    # val=0/test=0 the same way. A valid partition existed in every case.
    rng = random.Random(11)
    lopsided = []
    n = 0
    # 4 signers, 5 classes, all covered by all signers, but wildly uneven sizes.
    for slug in ("alpha", "beta", "gamma", "delta", "epsilon"):
        for signer, reps in (("S001", 40), ("S002", 30), ("S003", 4), ("S004", 3)):
            for _ in range(reps + rng.randint(0, 2)):
                n += 1
                lopsided.append({
                    "sample_id": f"lop{n:05d}", "slug": slug, "label_slug": slug,
                    "language": "vn", "vocabulary_scope": "profile_specific",
                    "recognition_profile": "alphabet",
                    "signer_id": signer, "session_id": "x", "file_path": f"l{n}.npz",
                })
    tr, va, te, rep5 = split_from_manifest(
        lopsided, split_mode="strict_signer_disjoint",
        recognition_profile="alphabet", seed=42)
    check("no split is empty", min(len(tr), len(va), len(te)) > 0, rep5["counts"])
    check("every class present in all three splits",
          rep5["class_coverage"] == {"train": 1.0, "val": 1.0, "test": 1.0},
          rep5["class_coverage"])
    check("stamped valid_for_research", rep5["valid_for_research"] is True,
          rep5.get("invalid_reasons"))
    s5 = (set(rep5["signers"]["train"]), set(rep5["signers"]["val"]), set(rep5["signers"]["test"]))
    check("signers still disjoint",
          s5[0].isdisjoint(s5[1]) and s5[0].isdisjoint(s5[2]) and s5[1].isdisjoint(s5[2]), s5)
    # Determinism: the exact search must not depend on dict iteration order.
    _, _, _, rep5b = split_from_manifest(
        list(reversed(lopsided)), split_mode="strict_signer_disjoint",
        recognition_profile="alphabet", seed=42)
    check("partition is order-independent",
          rep5b["signers"] == rep5["signers"], (rep5["signers"], rep5b["signers"]))

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for n, d in FAILED:
        print(f"  FAILED: {n}: {d}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# Vỏ pytest, và ĐÍNH CHÍNH cho bản đầu của chú thích này.
#
# Bản đầu viết rằng tệp này "chưa từng được kiểm trong CI". SAI. Nó nằm trong
# `conftest.STANDALONE_SUITES` từ trước, và `test_research_suites.py` chạy nó
# như một TIẾN TRÌNH CON, lấy mã thoát làm phán quyết. Phép quét AST chỉ đo
# được "pytest thu 0 hàm test_* từ tệp này" — đúng, nhưng KHÔNG đồng nghĩa với
# "không chạy", vì bộ chạy nằm ở chỗ khác.
#
# Vỏ này vẫn có ích, chỉ là vì lý do khiêm tốn hơn: gọi thẳng
# `pytest <tệp này>` giờ chạy được thay vì thu 0 ca. Bộ chạy thật vẫn là
# `test_research_suites.py`.
#
# Chốt `assert PASSED or FAILED` thì đáng giữ, và nó đã bắt được một ca thật:
# một kịch bản in "SKIP:" rồi `return 0` sẽ thành XANH ở CẢ HAI đường.
# ---------------------------------------------------------------------------

def test_toan_bo_kich_ban() -> None:
    ma = main()
    assert PASSED or FAILED, (
        "không ca nào chạy — kịch bản trả về xanh mà chưa kiểm gì cả")
    assert ma == 0, "; ".join(f"{n}: {d}" for n, d in FAILED)
