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

    print("[F2 frozen research splits — checksum, not just presence]")
    # Bản trước của mục này chỉ hỏi "tệp còn đó không". Tên nó là
    # "untouched by v2 tooling" nhưng nó KHÔNG phát hiện được việc ghi đè —
    # một lượt `make_splits.py` vô tình vẫn đè được mà bộ kiểm vẫn xanh. Đây là
    # phần cưỡng chế còn thiếu: chống-ghi bằng ĐỐI CHIẾU.
    #
    # docs/02-data/VOCABULARY_SCHEMA_V2.md:107 đã tuyên bố ba tệp này bất biến
    # từ trước; tới 14/08/2026 mới có thứ bắt được khi ai đó phá tuyên bố đó.
    registry = SPLITS_DIR / "FROZEN_RESEARCH_SPLITS.json"
    check("sổ đóng băng tồn tại", registry.exists(), str(registry))
    if registry.exists():
        khai = json.loads(registry.read_text(encoding="utf-8"))
        check("sổ tự khai purpose=research",
              khai.get("purpose") == "research", khai.get("purpose"))
        for name, muc in sorted((khai.get("files") or {}).items()):
            p = SPLITS_DIR / name
            if not p.exists():
                check(f"frozen {name} còn tồn tại", False, str(p))
                continue
            that = sha256_file(p)
            check(
                f"frozen {name} chưa bị đổi",
                that == muc.get("sha256"),
                f"HIỆN VẬT NGHIÊN CỨU ĐÓNG BĂNG ĐÃ ĐỔI. Đừng dựng lại hay ghi "
                f"đè tệp này — split vận hành thuộc về một hiện vật riêng có "
                f"split_id. khai={muc.get('sha256')} thật={that}",
            )

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
