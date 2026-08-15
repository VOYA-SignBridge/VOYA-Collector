"""Strict signer-disjoint split must fail loudly instead of writing a dead split.

Regression guard for the split-validity gate. Before it existed,
split_from_manifest happily produced hoa_de_signer_disjoint_v1 and _v3 with
counts {"train": 209, "val": 0, "test": 0}: with only 2-3 signers the greedy
group assignment puts every signer in train, and _assert_signer_disjoint then
passes vacuously because the empty set is disjoint from everything. Those
artifacts looked successful on disk and were unusable for evaluation.

Run:  python tests/test_split_safety.py
Pure stdlib.

Covers:
  S1  2 signers -> strict split fails
  S2  empty validation split -> fails
  S3  empty test split -> fails
  S4  >= 6 signers with full coverage -> succeeds and is valid_for_research
  S5  compatibility override -> writes an artifact stamped invalid
  S6  aggregator refuses runs trained on an invalid split
  S7  metadata carries every required provenance field
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from processed.splits.make_splits import split_from_manifest  # noqa: E402

PASSED: list = []
FAILED: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append((name, detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"  -> {detail}"))


def rows_for(signers, classes=("rang-muoi", "cat-ky", "tom"), per=4, profile="hoa_de"):
    """Manifest rows: every listed signer performs every class `per` times."""
    out = []
    n = 0
    for slug in classes:
        for s in signers:
            for _ in range(per):
                n += 1
                out.append({
                    "sample_id": f"s{n:05d}", "slug": slug, "label_slug": slug,
                    "language": "vn", "vocabulary_scope": "profile_specific",
                    "recognition_profile": profile, "signer_id": s,
                    "session_id": f"sess-{s}", "file_path": f"f{n}.npz",
                })
    return out


def strict(rows, **kw):
    return split_from_manifest(
        rows, split_mode="strict_signer_disjoint",
        recognition_profile="hoa_de", seed=42, **kw)


def main() -> int:
    print("[S1 two signers -> strict split must fail]")
    try:
        _, _, _, rep = strict(rows_for(["S001", "S002"]))
        check("2 signers rejected", False,
              f"split succeeded with counts={rep['counts']} — degenerate split written")
    except SystemExit as e:
        msg = str(e)
        check("2 signers rejected", "not usable for research" in msg, msg[:160])
        check("reason names the empty split",
              ("validation split is empty" in msg) or ("test split is empty" in msg)
              or ("missing from" in msg), msg[:200])

    print("[S2/S3 empty val or test -> fail]")
    # 3 signers, 3 classes: not enough groups to fill three non-empty splits
    # while keeping every class covered.
    for n_signers in (2, 3):
        try:
            _, _, _, rep = strict(rows_for([f"S{i:03d}" for i in range(1, n_signers + 1)]))
            empty = [k for k, v in rep["counts"].items() if v == 0]
            check(f"{n_signers} signers: no split written with an empty subset",
                  not empty, f"counts={rep['counts']}")
        except SystemExit as e:
            check(f"{n_signers} signers: failed loudly", "not usable for research" in str(e))

    print("[S4 six signers with full coverage -> success]")
    six = [f"S{i:03d}" for i in range(1, 7)]
    try:
        tr, va, te, rep = strict(rows_for(six, per=4))
        check("split produced", bool(tr) and bool(va) and bool(te),
              f"counts={rep['counts']}")
        check("valid_for_research is True", rep["valid_for_research"] is True,
              rep.get("invalid_reasons"))
        check("no invalid reasons", rep["invalid_reasons"] == [], rep["invalid_reasons"])
        s = rep["signers"]
        check("train/val signers disjoint", set(s["train"]).isdisjoint(s["val"]))
        check("train/test signers disjoint", set(s["train"]).isdisjoint(s["test"]))
        check("val/test signers disjoint", set(s["val"]).isdisjoint(s["test"]))
        check("every split has >= 1 signer",
              all(rep["signer_counts"][k] >= 1 for k in ("train", "val", "test")),
              rep["signer_counts"])
        check("class coverage complete in train",
              rep["class_coverage"]["train"] == 1.0, rep["class_coverage"])
    except SystemExit as e:
        check("6 signers split succeeds", False, str(e)[:200])

    print("[S5 compatibility override -> artifact stamped invalid]")
    try:
        _, _, _, rep = strict(rows_for(["S001", "S002"]), fail_on_missing_eval=False)
        check("override produces a report instead of raising", True)
        check("valid_for_research is False", rep["valid_for_research"] is False)
        check("invalid_reasons non-empty", len(rep["invalid_reasons"]) > 0,
              rep["invalid_reasons"])
    except SystemExit as e:
        check("override produces a report instead of raising", False, str(e)[:200])

    print("[S6 aggregator refuses runs on an invalid split]")
    try:
        from research_validity import evaluate_split_metadata
        bad = evaluate_split_metadata({"valid_for_research": False,
                                       "invalid_reasons": ["test split is empty"]})
        good = evaluate_split_metadata({"valid_for_research": True, "invalid_reasons": []})
        check("invalid split rejected", bad[0] is False, bad)
        check("valid split accepted", good[0] is True, good)
        check("missing metadata rejected", evaluate_split_metadata(None)[0] is False)
    except ImportError as e:
        check("research_validity module importable", False, str(e))

    print("[S7 metadata carries required provenance]")
    _, _, _, rep = strict(rows_for(six, per=4))
    for field in ("valid_for_research", "invalid_reasons", "signer_counts",
                  "class_coverage", "sample_counts", "excluded_unresolved_signers",
                  "seed"):
        check(f"metadata has '{field}'", field in rep, sorted(rep))
    # manifest_checksum is attached by run_manifest_mode when the split is
    # written to disk (the function itself never reads the manifest file).
    check("seed recorded correctly", rep["seed"] == 42, rep["seed"])
    check("sample_counts consistent with counts",
          rep["sample_counts"]["train"] == rep["counts"]["train"], rep["sample_counts"])

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
