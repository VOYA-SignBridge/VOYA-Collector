"""Standalone tests for dataset manifest create/validate scripts.

Run:  python tests/test_manifest.py
Builds a tiny synthetic dataset in a temp dir. Requires numpy.
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
CREATE = REPO_ROOT / "scripts" / "create_dataset_manifest.py"
VALIDATE = REPO_ROOT / "scripts" / "validate_dataset_manifest.py"

PASSED: list = []
FAILED: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append((name, detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"  -> {detail}"))


def _mk_dataset(ws: Path):
    feats = ws / "features" / "vn" / "hoa-de" / "class_rang-muoi_u1"
    feats.mkdir(parents=True)
    seq = np.random.rand(60, 126).astype(np.float32)
    raw = np.random.rand(45, 126).astype(np.float32)
    # v2 sample: raw + masks
    np.savez_compressed(feats / "sample_aaa.npz",
                        sequence=seq, landmarks_normalized=seq, landmarks_raw=raw,
                        frame_valid_mask=np.ones(60, bool),
                        left_hand_valid_mask=np.ones(60, bool),
                        right_hand_valid_mask=np.zeros(60, bool))
    (feats / "sample_aaa.json").write_text(json.dumps(
        {"user_id": "Minh", "session_id": "sess1", "signer_id": "S002",
         "quality_status": "ok", "normalization_version": "hands126_v1",
         "collection_campaign": "test"}), encoding="utf-8")
    # legacy sample: only 'sequence'
    np.savez_compressed(feats / "sample_bbb.npz", sequence=seq)
    labels = ws / "labels.csv"
    with labels.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["class_uid", "class_idx", "slug", "label_original", "language",
                                          "dialect", "folder_name", "semantic_label", "vocabulary_scope",
                                          "recognition_profile", "vocabulary_group", "collection_campaign"])
        w.writeheader()
        w.writerow({"class_uid": "u1", "class_idx": "1", "slug": "rang-muoi", "label_original": "rang muối",
                    "language": "vn", "dialect": "hoa-de", "folder_name": "class_rang-muoi_u1",
                    "semantic_label": "rang_muoi", "vocabulary_scope": "profile_specific",
                    "recognition_profile": "hoa_de", "vocabulary_group": "hoa_de_vocabulary",
                    "collection_campaign": "legacy_2026"})
    signers = ws / "signers.csv"
    with signers.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["signer_id", "display_name", "regional_group",
                                          "external_user_id", "is_active", "created_at"])
        w.writeheader()
        w.writerow({"signer_id": "S002", "display_name": "Minh", "is_active": "1", "created_at": "t"})


def _create(ws: Path, version: str, *extra):
    """Dựng manifest trong một thư mục tạm.

    `--skip-consent-gate` mặc định ở HÀM TRỢ GIÚP, không phải ở từng lời gọi:
    bộ này kiểm việc dựng manifest, và cổng đồng thuận cần một ảnh chụp lấy từ
    cơ sở dữ liệu mà bộ này cố tình không có. Bản thân cái cổng có bộ test
    riêng (`tests/test_consent_gate.py`) và một trường hợp ngay dưới đây kiểm
    rằng nó THẬT SỰ chặn khi không truyền cờ — nếu không thì cờ này sẽ lặng lẽ
    biến cả bộ thành bộ không bao giờ chạm tới cổng.
    """
    if not any(str(a).startswith("--consent") or a == "--skip-consent-gate"
               for a in extra):
        extra = ("--skip-consent-gate", *extra)
    return subprocess.run(
        [sys.executable, str(CREATE), "--version", version,
         "--features-root", str(ws / "features"),
         "--labels-csv", str(ws / "labels.csv"),
         "--signers-csv", str(ws / "signers.csv"),
         "--signer-mapping", str(ws / "nonexistent.json"),
         "--out-dir", str(ws / "manifests"), *extra],
        capture_output=True, text=True, encoding="utf-8")


def _validate(ws: Path, version: str, *extra):
    return subprocess.run(
        [sys.executable, str(VALIDATE), "--version", version,
         "--manifest-dir", str(ws / "manifests"),
         "--features-root", str(ws / "features"), *extra],
        capture_output=True, text=True, encoding="utf-8")


def main() -> int:
    ws = Path(tempfile.mkdtemp(prefix="manifest_test_"))
    try:
        _mk_dataset(ws)
        print("[MF1 create]")
        r = _create(ws, "test_v1")
        check("create exit 0", r.returncode == 0, r.stderr[-400:] + r.stdout[-200:])
        mpath = ws / "manifests" / "dataset_manifest_test_v1.csv"
        check("manifest written", mpath.exists())
        with mpath.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        check("2 samples", len(rows) == 2, len(rows))
        by_id = {r0["sample_id"]: r0 for r0 in rows}
        check("v2 sample raw_landmarks_available=1", by_id["aaa"]["raw_landmarks_available"] == "1")
        check("legacy sample raw_landmarks_available=0", by_id["bbb"]["raw_landmarks_available"] == "0")
        check("label_key v2", by_id["aaa"]["label_key"] == "vn/hoa_de/rang-muoi", by_id["aaa"]["label_key"])
        check("signer from sidecar", by_id["aaa"]["signer_id"] == "S002")
        check("checksum present (64 hex)", len(by_id["aaa"]["file_checksum"]) == 64)
        check("frozen labels copy", (ws / "manifests" / "labels_test_v1.csv").exists())
        check("stats json", (ws / "manifests" / "dataset_stats_test_v1.json").exists())

        print("[MF2 immutability]")
        r = _create(ws, "test_v1")
        check("re-create same version refused", r.returncode == 2, r.stdout[-200:])

        print("[MF3 validate clean]")
        r = _validate(ws, "test_v1", "--check-checksums")
        check("validate passes", r.returncode == 0, r.stdout[-300:])

        print("[MF4 detect problems]")
        # orphan: new file not in manifest
        feats = ws / "features" / "vn" / "hoa-de" / "class_rang-muoi_u1"
        np.savez_compressed(feats / "sample_ccc.npz", sequence=np.zeros((60, 126), np.float32))
        # missing: delete a manifested file
        (feats / "sample_bbb.npz").unlink()
        r = _validate(ws, "test_v1")
        check("validate detects problems (exit 1)", r.returncode == 1, r.stdout[-300:])
        check("missing file reported", "missing files: 1" in r.stdout, r.stdout[-400:])
        check("orphan reported", "orphan files: 1" in r.stdout, r.stdout[-400:])
        # tamper manifest -> checksum mismatch
        mpath.write_text(mpath.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        r = _validate(ws, "test_v1")
        check("tampered manifest detected", "manifest was modified" in r.stdout, r.stdout[-300:])

        print("[MF5 cong dong thuan]")
        # KHÔNG truyền `--skip-consent-gate`: đây là chỗ duy nhất trong bộ này
        # để cái cờ ở `_create` không âm thầm biến cổng thành thứ không ai chạm
        # tới. Không có ảnh chụp → phải TỪ CHỐI, không được lặng lẽ dựng một
        # manifest chưa lọc.
        r = _create(ws, "test_gate", "--consent-scope", "research_release",
                    "--consent-snapshot", str(ws / "khong-co.json"))
        check("thieu anh chup -> tu choi (exit 4)", r.returncode == 4,
              f"exit={r.returncode} {r.stdout[-300:]}")
        check("khong ghi manifest nao",
              not (ws / "manifests" / "dataset_manifest_test_gate.csv").exists())
        check("noi ro cach sua", "consent_snapshot" in r.stdout, r.stdout[-300:])

        # Bỏ qua có chủ ý thì được chạy, và việc bỏ qua phải ĐI THEO phiên bản.
        r = _create(ws, "test_skip")
        check("skip-consent-gate chay duoc", r.returncode == 0, r.stdout[-300:])
        stats = json.loads((ws / "manifests" / "dataset_stats_test_skip.json")
                           .read_text(encoding="utf-8"))
        check("viec bo qua duoc ghi vao stats",
              stats.get("consent_gate", {}).get("enforced") is False,
              stats.get("consent_gate"))
    finally:
        shutil.rmtree(ws, ignore_errors=True)

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
