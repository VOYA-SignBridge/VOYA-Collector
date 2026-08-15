"""Một lượt chạy phải biết CHÍNH XÁC nó tiêu thụ hiện vật nào.

Trước lượt này, câu hỏi "lượt này đọc tệp nào" có ba câu trả lời khác nhau tuỳ
hỏi ai: giá trị mặc định của `train_tcn`, nhánh nghiên cứu của `_build_cmd`, và
`_split_csvs_of` (trả RỖNG cho nhánh legacy, nên cổng đồng thuận không soi lượt
huấn luyện legacy nào). Ba cách hiểu lệch nhau được mà không ai biết.

Bốn ca đầu là bốn bằng chứng đã chốt; ca thứ tư và năm — smoke đầu-cuối thật —
nằm ở `test_operational_smoke_run.py` vì chúng cần torch và npz thật.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from processed.train_utils.split_artifact import (  # noqa: E402
    SplitArtifactError,
    file_hashes,
    resolve_split_artifact,
)

COT = "sample_uid,class_uid,slug,dialect,region,target_idx\n"


def _dung_hien_vat(goc: Path, split_id: str, *, purpose="operational",
                   sua_id=None) -> Path:
    """Dựng một hiện vật vận hành hợp lệ trong tmp."""
    d = goc / "operational" / split_id
    d.mkdir(parents=True, exist_ok=True)
    for ten in ("train", "val", "test"):
        (d / f"{ten}.csv").write_text(
            COT + f"s-{ten},UID_A,an,pho-thong,bac,0\n", encoding="utf-8")
    meta = {
        "purpose": purpose,
        "split_id": sua_id if sua_id is not None else split_id,
        "files": file_hashes(d),
        "classes": [{"class_uid": "UID_A", "target_idx": 0}],
    }
    (d / "split_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


class TestBangChung1_VanHanhKhongCoIdThiTuChoi:
    """Bất biến quan trọng nhất của tầng này."""

    def test_thieu_split_id_thi_DUNG_chu_khong_roi_ve_nghien_cuu(self, tmp_path):
        with pytest.raises(SplitArtifactError) as loi:
            resolve_split_artifact(purpose="operational", splits_root=tmp_path)
        msg = str(loi.value)
        assert "phải ghim một `split_id`" in msg
        assert "KHÔNG rơi về" in msg, (
            "câu báo lỗi phải nói rõ vì sao không có mặc định — nếu không, "
            "người sau sẽ thêm một mặc định cho tiện")

    def test_id_khong_ton_tai_thi_DUNG(self, tmp_path):
        with pytest.raises(SplitArtifactError) as loi:
            resolve_split_artifact(purpose="operational", splits_root=tmp_path,
                                   split_id="chua-dung")
        assert "không có hiện vật vận hành" in str(loi.value)

    def test_khong_bao_gio_tra_ve_ba_tep_goc_cho_van_hanh(self, tmp_path):
        """Kể cả khi ba tệp nghiên cứu NẰM NGAY ĐÓ."""
        for ten in ("train", "val", "test"):
            (tmp_path / f"{ten}.csv").write_text(COT, encoding="utf-8")
        with pytest.raises(SplitArtifactError):
            resolve_split_artifact(purpose="operational", splits_root=tmp_path)


class TestBangChung2_NghienCuuVanTraVeBaTepDongBang:
    def test_resolve_dung_ba_tep_goc(self, tmp_path):
        for ten in ("train", "val", "test"):
            (tmp_path / f"{ten}.csv").write_text(COT + f"s,{ten},a,d,bac,0\n",
                                                 encoding="utf-8")
        (tmp_path / "FROZEN_RESEARCH_SPLITS.json").write_text(
            json.dumps({"purpose": "research", "files": file_hashes(tmp_path)}),
            encoding="utf-8")

        hv = resolve_split_artifact(purpose="research", splits_root=tmp_path)

        assert hv.purpose == "research"
        assert hv.train_csv == tmp_path / "train.csv"
        assert hv.split_id == "frozen-research-legacy"

    def test_thieu_so_dang_ky_thi_DUNG(self, tmp_path):
        for ten in ("train", "val", "test"):
            (tmp_path / f"{ten}.csv").write_text(COT, encoding="utf-8")
        with pytest.raises(SplitArtifactError) as loi:
            resolve_split_artifact(purpose="research", splits_root=tmp_path)
        assert "không phát hiện được nếu ba tệp đã bị dựng lại" in str(loi.value)

    def test_ba_tep_bi_dung_lai_thi_DUNG(self, tmp_path):
        for ten in ("train", "val", "test"):
            (tmp_path / f"{ten}.csv").write_text(COT, encoding="utf-8")
        (tmp_path / "FROZEN_RESEARCH_SPLITS.json").write_text(
            json.dumps({"purpose": "research", "files": file_hashes(tmp_path)}),
            encoding="utf-8")
        (tmp_path / "val.csv").write_text(COT + "them,X,a,d,bac,0\n",
                                          encoding="utf-8")

        with pytest.raises(SplitArtifactError) as loi:
            resolve_split_artifact(purpose="research", splits_root=tmp_path)
        assert "không khớp mã băm đã khai" in str(loi.value)


class TestBangChung3_XacMinhChuKhongChiTimThay:
    def test_hien_vat_hop_le_thi_di_qua(self, tmp_path):
        _dung_hien_vat(tmp_path, "smoke-01")
        hv = resolve_split_artifact(purpose="operational", splits_root=tmp_path,
                                    split_id="smoke-01")
        assert hv.split_id == "smoke-01" and hv.purpose == "operational"
        assert hv.train_csv.exists()

    def test_sua_mot_CSV_thi_xac_minh_HONG(self, tmp_path):
        d = _dung_hien_vat(tmp_path, "smoke-02")
        (d / "val.csv").write_text(COT + "them,UID_B,an,pho-thong,nam,1\n",
                                   encoding="utf-8")

        with pytest.raises(SplitArtifactError) as loi:
            resolve_split_artifact(purpose="operational", splits_root=tmp_path,
                                   split_id="smoke-02")
        assert "không khớp mã băm đã khai" in str(loi.value)

    def test_chep_CSV_tu_hien_vat_khac_vao_thu_muc_nay_thi_BI_BAT(self, tmp_path):
        """Ca bạn nêu: metadata nói split_id=X nhưng ba CSV đến từ Y."""
        _dung_hien_vat(tmp_path, "X")
        dy = _dung_hien_vat(tmp_path, "Y")
        (dy / "train.csv").write_text(COT + "khac,UID_Z,khac,d,nam,0\n",
                                      encoding="utf-8")
        # chép ba CSV của Y đè lên X, giữ nguyên bản khai của X
        dx = tmp_path / "operational" / "X"
        for ten in ("train", "val", "test"):
            (dx / f"{ten}.csv").write_text(
                (dy / f"{ten}.csv").read_text(encoding="utf-8"), encoding="utf-8")

        with pytest.raises(SplitArtifactError) as loi:
            resolve_split_artifact(purpose="operational", splits_root=tmp_path,
                                   split_id="X")
        assert "chép vào đây từ một hiện vật khác" in str(loi.value)

    def test_doi_ten_thu_muc_thi_BI_BAT(self, tmp_path):
        _dung_hien_vat(tmp_path, "ten-moi", sua_id="ten-cu")
        with pytest.raises(SplitArtifactError) as loi:
            resolve_split_artifact(purpose="operational", splits_root=tmp_path,
                                   split_id="ten-moi")
        assert "bị đổi tên hoặc chép nhầm chỗ" in str(loi.value)

    def test_purpose_KHONG_suy_tu_ten_thu_muc(self, tmp_path):
        """Thư mục nằm dưới `operational/` chưa đủ — hiện vật phải TỰ KHAI."""
        _dung_hien_vat(tmp_path, "gia-dang", purpose="research")
        with pytest.raises(SplitArtifactError) as loi:
            resolve_split_artifact(purpose="operational", splits_root=tmp_path,
                                   split_id="gia-dang")
        assert "Không suy purpose từ tên thư mục" in str(loi.value)

    def test_thieu_muc_files_thi_KHONG_coi_la_da_xac_minh(self, tmp_path):
        d = _dung_hien_vat(tmp_path, "khong-hash")
        meta = json.loads((d / "split_metadata.json").read_text(encoding="utf-8"))
        del meta["files"]
        (d / "split_metadata.json").write_text(json.dumps(meta), encoding="utf-8")

        with pytest.raises(SplitArtifactError) as loi:
            resolve_split_artifact(purpose="operational", splits_root=tmp_path,
                                   split_id="khong-hash")
        assert "Đó chưa phải xác minh" in str(loi.value)


class TestPurposeLa:
    def test_purpose_khong_ro_thi_DUNG_chu_khong_doan(self, tmp_path):
        with pytest.raises(SplitArtifactError) as loi:
            resolve_split_artifact(purpose="linh-tinh", splits_root=tmp_path)
        assert "mở lại đúng chỗ mơ hồ vừa đóng" in str(loi.value)
