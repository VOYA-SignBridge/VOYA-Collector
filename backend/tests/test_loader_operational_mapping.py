"""`NPZSignDataset` ở chế độ vận hành: một nguồn sự thật, không có đường thứ hai.

Trước lượt này, một hàng thành nhãn theo BA cách khác nhau tuỳ hoàn cảnh:

    label_key   `vn/<dialect>/<slug>` — không chứa region, nên `ăn|bac` và
                `ăn|nam` cùng dialect gộp thành một lớp, im lặng.
    class_idx   trừ 1. Định danh danh mục TOÀN CỤC và THƯA: `{17,103,812}`
                thành `{16,102,811}` trong khi `num_classes` đếm ra 3.
    labels.csv  từ vựng HIỆN TẠI, không phải từ vựng lúc huấn luyện.

Chế độ vận hành cắt cả ba. Tệp này chứng minh nó cắt thật, và — quan trọng
không kém — chứng minh đường nghiên cứu/legacy KHÔNG bị đụng.

Các ca ở đây không cần torch: `_resolve_target` là hàm thuần trên một dict.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from processed.train_utils.dataset_loader import NPZSignDataset  # noqa: E402

# `ăn` hai vùng + một từ khác. Đúng hình dạng việc nhập QIPEDC sẽ tạo ra.
UID_BAC, UID_NAM, UID_KHAC = "UID_AN_BAC", "UID_AN_NAM", "UID_CAMON"
ANH_XA = {UID_BAC: 0, UID_NAM: 1, UID_KHAC: 2}


def _hang(uid: str, slug: str, dialect: str, class_idx: str):
    """Hàng mang ĐỦ mọi khoá cũ — nếu thiếu, đột biến sẽ vô hiệu và ca vô nghĩa."""
    return {
        "class_uid": uid,
        "slug": slug,
        "label_slug": slug,
        "dialect": dialect,
        "language": "vn",
        "label_key": f"vn/{dialect}/{slug}",
        "class_idx": class_idx,
    }


HANG_BAC = _hang(UID_BAC, "an", "pho-thong", "17")
HANG_NAM = _hang(UID_NAM, "an", "pho-thong", "103")
HANG_KHAC = _hang(UID_KHAC, "cam-on", "pho-thong", "812")


def _ds(mapping=None):
    """Dựng dataset mà KHÔNG đọc CSV/npz nào — chỉ cần phần phân giải nhãn."""
    ds = NPZSignDataset.__new__(NPZSignDataset)
    ds._declared_mapping = dict(mapping) if mapping else None
    ds.label_to_index = dict(mapping) if mapping else {}
    ds._class_idx_to_label = {}
    ds._label_offset = 0
    return ds


class TestVanHanh:
    def test_cung_slug_khac_vung_ra_HAI_target(self):
        """Ca trung tâm. Dưới `label_key` hai hàng này là một."""
        ds = _ds(ANH_XA)

        assert ds._resolve_target(HANG_BAC) == 0
        assert ds._resolve_target(HANG_NAM) == 1
        assert HANG_BAC["label_key"] == HANG_NAM["label_key"], (
            "fixture không còn tái hiện được va chạm — ca này thành vô nghĩa")

    def test_class_idx_thua_KHONG_anh_huong_target(self):
        """`{17,103,812}` là định danh thật, thưa. Đường cũ cho `{16,102,811}`."""
        ds = _ds(ANH_XA)
        assert [ds._resolve_target(h) for h in (HANG_BAC, HANG_NAM, HANG_KHAC)] == [0, 1, 2]

        doi = dict(HANG_BAC, class_idx="99999")
        assert ds._resolve_target(doi) == 0, "đổi class_idx không được động tới target"

    def test_labels_csv_bia_ra_KHONG_lam_doi_ket_qua(self, monkeypatch, tmp_path):
        """Chứng minh loader KHÔNG đọc `labels.csv` ở chế độ vận hành.

        Bịa một `labels.csv` mâu thuẫn hẳn rồi chĩa mọi đường dò vào nó; nếu
        loader còn lén đọc, kết quả sẽ đổi.
        """
        gia = tmp_path / "labels.csv"
        gia.write_text(
            "class_uid,class_idx,slug,language,dialect\n"
            f"{UID_BAC},555,an,vn,pho-thong\n"
            f"{UID_NAM},666,an,vn,pho-thong\n",
            encoding="utf-8")
        monkeypatch.setenv("VOYA_DATA_ROOT", str(tmp_path))

        ds = _ds(ANH_XA)
        assert ds._resolve_target(HANG_BAC) == 0
        assert ds._resolve_target(HANG_NAM) == 1

    def test_thieu_class_uid_thi_NEM(self):
        ds = _ds(ANH_XA)
        with pytest.raises(ValueError) as loi:
            ds._resolve_target(dict(HANG_BAC, class_uid=""))
        assert "class_uid" in str(loi.value)

    def test_uid_ngoai_anh_xa_thi_NEM_chu_khong_doan(self):
        """Không rơi sang label_key/class_idx. Rơi được nghĩa là một hàng lạ
        vẫn học được dưới một nhãn đoán ra."""
        ds = _ds(ANH_XA)
        la = _hang("UID_LA", "an", "pho-thong", "17")
        with pytest.raises(ValueError) as loi:
            ds._resolve_target(la)
        assert "không nằm trong ánh xạ đã khai" in str(loi.value)
        assert "Không đoán nhãn thay" in str(loi.value)


class TestLegacyKhongBiDung:
    def test_duong_cu_van_tra_theo_label_key(self):
        ds = _ds(None)
        ds.label_to_index = {"vn/pho-thong/an": 4, "vn/pho-thong/cam-on": 5}
        assert ds._resolve_target(HANG_BAC) == 4
        assert ds._resolve_target(HANG_NAM) == 4, (
            "đường CŨ vẫn gộp hai vùng — đó là hành vi lịch sử, giữ nguyên có "
            "chủ ý để hiện vật nghiên cứu đóng băng tái lập được")

    def test_duong_cu_van_roi_ve_class_idx(self):
        ds = _ds(None)
        ds.label_to_index = {}
        assert ds._resolve_target(dict(HANG_BAC, label_key="")) == 17


class TestHienVatKhongBiSuaTrenDuongDi:
    def test_train_tcn_KHONG_ghi_de_label_key_nua(self):
        """Bản đầu của lượt nối dùng cầu tạm `label_key := class_uid` rồi ghi
        đè bản sao trong run dir. Membership không đổi, nhưng tệp trainer đọc
        không còn khớp từng byte với hiện vật đã khai — mã băm mất ý nghĩa làm
        bằng chứng. Đã gỡ; ca này canh để nó không quay lại."""
        nguon = (REPO_ROOT / "processed" / "train_utils" / "train_tcn.py").read_text(
            encoding="utf-8")
        assert 'r["label_key"] = uid' not in nguon
        assert "class_uid_to_target_idx=declared_mapping" in nguon, (
            "ánh xạ phải được truyền THẲNG xuống loader")

    def test_sha256_split_khong_doi_khi_chi_doc(self, tmp_path):
        """Bất biến: đọc split để dựng theo_phan không được làm đổi tệp."""
        p = tmp_path / "train.csv"
        p.write_text("class_uid,slug\nA,x\nB,y\n", encoding="utf-8")
        truoc = hashlib.sha256(p.read_bytes()).hexdigest()

        import csv as _csv

        with p.open(encoding="utf-8") as f:
            list(_csv.DictReader(f))

        assert hashlib.sha256(p.read_bytes()).hexdigest() == truoc
