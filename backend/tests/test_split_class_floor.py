"""Sàn số mẫu/lớp: lọc lúc CHIA, từ chối lúc HUẤN LUYỆN.

Cổng huấn luyện đã biết đếm lớp đủ điều kiện từ CSDL, nhưng trainer không đọc
CSDL — nó đọc `processed/splits/*.csv`. Hai thứ đó lệch nhau được, và khi lệch
thì lượt chạy học một tập nhãn khác với tập nhãn vừa được duyệt. Đo trên đĩa
ngày 14/08: `bang-chu-cai` có 22/23 lớp đạt sàn 25, `hoa-de` có 7/8 — cả hai
qua cổng cũ trót lọt rồi huấn luyện kèm một lớp không thể học được.

Chia làm hai nửa, và ranh giới giữa chúng là điều đáng nhớ nhất ở đây:

  - LỌC thuộc về lúc chia. `make_splits.py --min_samples_per_class` loại hẳn
    lớp thiếu mẫu và khai báo tập lớp còn lại.
  - TỪ CHỐI thuộc về lúc huấn luyện. Cổng không tự lọc, vì một checkpoint
    huấn luyện trên tập nhỏ hơn tệp split khai báo là một checkpoint nói sai
    về nguồn gốc của nó — đúng nguyên tắc `_consent_preflight` đã chốt.
"""

from __future__ import annotations

import csv
import json
import sys
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from processed.splits.make_splits import (  # noqa: E402
    assign_target_indices,
    class_mapping_checksum,
    class_set_checksum,
    enforce_min_classes,
    filter_classes_below_floor,
    split_from_manifest,
    write_legacy_snapshot,
)

from app.routers import training as tr  # noqa: E402
from app.storage import metadata_db as db  # noqa: E402
from app.tenant_context import system_scope  # noqa: E402


# --------------------------------------------------------------------------
# Nửa thứ nhất: lọc lúc chia
# --------------------------------------------------------------------------

def _hang(uid: str, n: int):
    return [{"class_uid": uid, "label_original": uid.lower()} for _ in range(n)]


class TestLocLucChia:
    def test_loai_ca_lop_chu_khong_cat_bot_mau(self):
        """Loại CẢ LỚP, không phải cắt bớt mẫu cho bằng nhau.

        Một lớp 5 mẫu chia 70/15/15 còn 3 mẫu huấn luyện. Nó không học được,
        nhưng vẫn chiếm một chiều trong tầng softmax và vẫn hiện ở danh sách
        lớp thời gian thực — kéo tụt số đo mà không đóng góp gì.
        """
        rows = _hang("A", 30) + _hang("B", 5) + _hang("C", 25)
        giu, loai = filter_classes_below_floor(rows, 25)

        assert {r["class_uid"] for r in giu} == {"A", "C"}
        assert len(giu) == 55, "mẫu của lớp đạt phải còn nguyên vẹn"
        assert [d["class"] for d in loai] == ["B"]
        assert loai[0]["samples"] == 5

    def test_dung_bang_san_thi_duoc_giu(self):
        """`< floor` chứ không phải `<= floor`. 25 mẫu là ĐẠT."""
        giu, loai = filter_classes_below_floor(_hang("A", 25), 25)
        assert len(giu) == 25 and loai == []

    def test_san_bang_khong_la_tat_han(self):
        """Đường gọi cũ chưa khai sàn phải giữ nguyên hành vi, không lọc gì."""
        rows = _hang("A", 1) + _hang("B", 2)
        giu, loai = filter_classes_below_floor(rows, 0)
        assert len(giu) == len(rows) and loai == []

    def test_bam_khong_phu_thuoc_thu_tu(self):
        """Hai lần chia cùng dữ liệu phải ra cùng mã, dù thứ tự hàng khác nhau."""
        assert class_set_checksum(["b", "a"]) == class_set_checksum(["a", "b", "a"])
        assert class_set_checksum(["a", "b"]) != class_set_checksum(["a", "c"])

    def test_bam_doi_khi_tap_lop_doi(self):
        """Đây là điều làm nó dùng được: thêm hoặc bớt một lớp là mã đổi."""
        assert class_set_checksum(["a", "b"]) != class_set_checksum(["a", "b", "c"])


class TestManifestMode:
    def _manifest(self, signers, slug, per):
        return [{"sample_id": f"{slug}-{s}-{i}", "slug": slug, "label_slug": slug,
                 "language": "vn", "vocabulary_scope": "profile_specific",
                 "recognition_profile": "hoa_de", "signer_id": s,
                 "file_path": f"{slug}{s}{i}.npz"}
                for s in signers for i in range(per)]

    def test_class_idx_khong_bi_thung_lo_sau_khi_loc(self):
        """Lọc phải xảy ra TRƯỚC khi đánh số, và đây là lý do.

        Trainer lấy số lớp bằng `max(class_idx)` chứ không bằng số lớp thật.
        Đánh số trước rồi loại sau sẽ để lại lỗ trong dãy, và tầng softmax thừa
        ra một chiều không lớp nào chiếm — mô hình học được cách không bao giờ
        chọn nó, và số đo vẫn "đúng", nên chuyện này lặng lẽ.
        """
        six = [f"S{i:03d}" for i in range(1, 7)]
        rows = (self._manifest(six, "rang-muoi", 5)
                + self._manifest(six, "cat-ky", 5)
                + self._manifest(six, "tom", 1))  # 6 mẫu — dưới sàn

        _tr, _va, _te, rep = split_from_manifest(
            rows, split_mode="strict_signer_disjoint",
            recognition_profile="hoa_de", min_samples_per_class=25)

        assert rep["num_classes"] == 2
        assert [d["label"] for d in rep["excluded_below_floor"]] == ["tom"]

        moi_idx = {int(r["class_idx"]) for r in _tr + _va + _te}
        assert moi_idx == {1, 2}, f"dãy class_idx thủng lỗ: {sorted(moi_idx)}"

    def test_bao_cao_mang_du_san_va_bam(self):
        """Hiện vật phải TỰ KHAI sàn nó đã dùng — nếu không, không ai kiểm
        được một checkpoint đã huấn luyện trên tập lớp nào."""
        six = [f"S{i:03d}" for i in range(1, 7)]
        rows = self._manifest(six, "a", 5) + self._manifest(six, "b", 5)
        _t, _v, _e, rep = split_from_manifest(
            rows, split_mode="strict_signer_disjoint",
            recognition_profile="hoa_de", min_samples_per_class=10)

        assert rep["min_samples_per_class"] == 10
        assert rep["class_set_checksum"] == class_set_checksum(rep["label_keys"])

    def test_san_loai_het_thi_dung_han_chu_khong_chia_tap_rong(self):
        six = [f"S{i:03d}" for i in range(1, 7)]
        rows = self._manifest(six, "a", 1)
        with pytest.raises(SystemExit) as loi:
            split_from_manifest(rows, split_mode="strict_signer_disjoint",
                                recognition_profile="hoa_de",
                                min_samples_per_class=100)
        assert "không còn gì để chia" in str(loi.value)


class TestSoLopToiThieu:
    """Cổng thứ hai của `make_splits`, và nó phải nằm TRONG CLI.

    `make_splits.py` chạy được thẳng từ dòng lệnh, ngoài mọi cổng của backend.
    Một cổng chỉ bảo vệ được đường đi qua nó.
    """

    def test_hinh_dang_can_tho_bi_chan(self):
        """Ca thật trên đĩa 14/08: 8 lớp, sàn 25 loại 7, còn ĐÚNG MỘT."""
        with pytest.raises(SystemExit) as loi:
            enforce_min_classes(["chi-con-mot"], 2, ten_tap="can-tho",
                                so_ung_vien=8,
                                da_loai=[{"class": "x", "label": "xin chào",
                                          "samples": 4}])
        msg = str(loi.value)
        assert "còn 1 lớp, cần ≥2" in msg
        assert "KHÔNG ghi tập chia" in msg, "phải nói rõ là không có hiện vật nào được ghi"
        assert "xin chào" in msg, "phải nêu lớp nào đã bị loại, nếu không người dùng mù"

    def test_du_lop_thi_di_qua(self):
        enforce_min_classes(["a", "b"], 2)

    def test_dem_theo_LOP_chu_khong_theo_so_lan_xuat_hien(self):
        with pytest.raises(SystemExit):
            enforce_min_classes(["a", "a", "a"], 2)

    def test_bang_khong_la_tat(self):
        enforce_min_classes([], 0)


class TestChiSoDauRa:
    """`target_idx` là trường RIÊNG, không phải `class_idx` viết đè."""

    def test_lien_tuc_khong_thung_lo(self):
        """Bất biến trực tiếp, không dựa vào một fixture cụ thể."""
        khoa = ["uid-C", "uid-A", "uid-B", "uid-D"]
        anh_xa = assign_target_indices(khoa)

        assert sorted(anh_xa.values()) == list(range(len(khoa)))
        assert len(anh_xa) == len(set(khoa))

    def test_tat_dinh_khong_theo_thu_tu_dua_vao(self):
        """Hai lần chia cùng tập lớp phải cho cùng ánh xạ.

        Đây là thứ `_build_subset_label_maps` của trainer KHÔNG có: nó gom nhãn
        theo thứ tự hàng xuất hiện trong CSV, nên lớp 0 là "nhãn nào ở dòng
        đầu". Ánh xạ ở đây neo vào khoá lớp, không vào thứ tự hàng.
        """
        assert (assign_target_indices(["b", "a", "c"])
                == assign_target_indices(["c", "b", "a"]))

    def test_class_idx_KHONG_bi_viet_de_trong_che_do_manifest(self):
        """Hai khái niệm, hai trường. Trộn chúng là một lỗi đắt.

        `class_idx` là định danh toàn cục bền qua mọi lượt chia; `target_idx`
        là vị trí trong tầng đầu ra của RIÊNG lượt chia này. Loại một lớp thì
        mọi lớp sau nó dịch xuống — nên `target_idx` không phải định danh, và
        ghi đè `class_idx` bằng nó sẽ làm mọi hiện vật trỏ vào `class_idx` trỏ
        nhầm chỗ ở lần chia kế tiếp.
        """
        six = [f"S{i:03d}" for i in range(1, 7)]
        rows = [{"sample_id": f"{slug}-{s}-{i}", "slug": slug, "label_slug": slug,
                 "language": "vn", "vocabulary_scope": "profile_specific",
                 "recognition_profile": "hoa_de", "signer_id": s,
                 "file_path": f"{slug}{s}{i}.npz"}
                for slug in ("a", "b") for s in six for i in range(5)]

        tr, va, te, rep = split_from_manifest(
            rows, split_mode="strict_signer_disjoint",
            recognition_profile="hoa_de", min_samples_per_class=10)

        moi = tr + va + te
        assert {int(r["class_idx"]) for r in moi} == {1, 2}, "class_idx giữ 1-based"
        assert {int(r["target_idx"]) for r in moi} == {0, 1}, "target_idx là 0-based"
        assert all(int(r["class_idx"]) != int(r["target_idx"]) for r in moi), (
            "hai trường phải PHÂN BIỆT được — nếu trùng nhau thì bộ kiểm này "
            "không chứng minh được gì")

        ghi = {c["class_uid"]: c["target_idx"] for c in rep["classes"]}
        assert sorted(ghi.values()) == [0, 1]
        assert rep["class_mapping_hash"] == class_mapping_checksum(ghi.items())


class TestHaiMaBam:
    def test_bam_TAP_bo_qua_thu_tu(self):
        assert class_set_checksum(["b", "a"]) == class_set_checksum(["a", "b"])

    def test_bam_ANH_XA_phan_biet_duoc_hai_anh_xa_cung_tap(self):
        """Đây là lý do phải có HAI mã băm, không phải một.

        `A→0 B→1 C→2` và `A→2 B→0 C→1` có CÙNG tập lớp. Một checkpoint dùng
        ánh xạ này mà đọc nhãn theo ánh xạ kia sẽ đoán sai toàn bộ, âm thầm,
        với độ chính xác báo cáo vẫn đẹp.
        """
        m1 = [("A", 0), ("B", 1), ("C", 2)]
        m2 = [("A", 2), ("B", 0), ("C", 1)]

        assert class_set_checksum([k for k, _ in m1]) == \
               class_set_checksum([k for k, _ in m2]), "cùng tập lớp"
        assert class_mapping_checksum(m1) != class_mapping_checksum(m2), \
            "nhưng KHÁC ánh xạ — một mã băm duy nhất sẽ không thấy khác biệt này"

    def test_bam_ANH_XA_khong_phu_thuoc_thu_tu_dua_vao(self):
        assert (class_mapping_checksum([("B", 1), ("A", 0)])
                == class_mapping_checksum([("A", 0), ("B", 1)]))


class TestKhaiBao:
    def test_ghi_du_truong_de_kiem_lai_duoc(self, tmp_path):
        p = write_legacy_snapshot(
            tmp_path, class_keys=["U1", "U2"], floor=25,
            excluded=[{"class": "U3", "label": "x", "samples": 4}],
            mode="sample", seed=42, min_classes=2,
            sample_counts={"U1": 37, "U2": 25},
            counts={"train": 10, "val": 2, "test": 2})

        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["num_classes"] == 2
        assert data["excluded_below_floor"][0]["class"] == "U3"
        assert data["seed"] == 42 and data["split_mode"] == "sample"

    def test_chinh_sach_phai_co_CA_HAI_nguong(self, tmp_path):
        """Ghi mỗi con số 25 là chưa đủ.

        Người đọc sau sẽ không biết tập chia này đã được kiểm điều kiện thứ hai
        (số lớp tối thiểu) hay chưa — và "chưa kiểm" với "kiểm rồi, đạt" là hai
        trạng thái khác nhau.
        """
        p = write_legacy_snapshot(tmp_path, class_keys=["U1", "U2"], floor=25,
                                  excluded=[], mode="sample", seed=42,
                                  min_classes=2, counts={})
        chinh_sach = json.loads(p.read_text(encoding="utf-8"))["policy"]
        assert chinh_sach == {"min_samples_per_class": 25, "min_classes": 2}

    def test_luu_anh_xa_day_du_va_so_mau_truoc_khi_chia(self, tmp_path):
        """Thiếu ánh xạ thì không ai dựng lại được ý nghĩa của tầng đầu ra."""
        p = write_legacy_snapshot(tmp_path, class_keys=["U2", "U1"], floor=25,
                                  excluded=[], mode="sample", seed=42,
                                  sample_counts={"U1": 37, "U2": 26}, counts={})
        data = json.loads(p.read_text(encoding="utf-8"))

        lop = {c["class_uid"]: c for c in data["classes"]}
        assert sorted(c["target_idx"] for c in data["classes"]) == [0, 1]
        assert lop["U1"]["sample_count_before_split"] == 37
        assert data["class_mapping_hash"] == class_mapping_checksum(
            {k: v["target_idx"] for k, v in lop.items()}.items())

    def test_hai_ma_bam_deu_co_mat_va_khac_nhau(self, tmp_path):
        p = write_legacy_snapshot(tmp_path, class_keys=["U1", "U2"], floor=25,
                                  excluded=[], mode="sample", seed=42, counts={})
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["class_set_hash"] and data["class_mapping_hash"]
        assert data["class_set_hash"] != data["class_mapping_hash"]


# --------------------------------------------------------------------------
# Nửa thứ hai: từ chối lúc huấn luyện
# --------------------------------------------------------------------------

CAC_COT = ["sample_uid", "class_uid", "slug", "dialect", "class_idx"]


def _viet_split(thu_muc: Path, hang):
    for ten in ("train", "val", "test"):
        with (thu_muc / f"{ten}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAC_COT)
            w.writeheader()
            if ten == "train":
                w.writerows(hang)


@pytest.fixture
def split_gia(tmp_path, monkeypatch):
    """Trỏ cổng vào một thư mục split tạm, không đụng tệp thật trên đĩa."""
    monkeypatch.setattr(tr, "SPLITS_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def lop_rong():
    """Một lớp có thật trong CSDL nhưng KHÔNG có mẫu nào.

    Đúng hình dạng của mục thư viện nhập từ từ điển quốc gia: `class_idx` thật
    (theo chủ ý — `class_idx` là ĐỊNH DANH, không phải trạng thái sẵn sàng),
    nên không có gì khác ngăn nó đi vào tập huấn luyện.
    """
    uid = f"FLOOR_{uuid.uuid4().hex[:10]}"
    with system_scope("test: dựng lớp 0 mẫu"):
        db._execute(
            "INSERT INTO classes(tenant_id, class_uid, slug, label_original, "
            "language, region) VALUES('default', %s, %s, %s, 'vn', 'unclassified')",
            (uid, uid.lower(), "lớp trống"),
        )
    yield uid
    with system_scope("test cleanup"):
        db._execute("DELETE FROM classes WHERE class_uid = %s", (uid,))


@pytest.mark.integration
class TestTuChoiLucHuanLuyen:
    def test_bat_duoc_lop_thieu_mau_nam_trong_split(self, split_gia, lop_rong):
        _viet_split(split_gia, [{"sample_uid": "s1", "class_uid": lop_rong,
                                 "slug": "x", "dialect": "d1", "class_idx": "1"}])

        lan = tr._split_classes_below_floor(["d1"], 25)

        assert [uid for _ten, uid, _n in lan] == [lop_rong]
        assert lan[0][2] == 0, "lớp 0 mẫu phải ra 0, không phải bị loại khỏi kết quả"

    def test_chi_soi_phuong_ngu_da_chon(self, split_gia, lop_rong):
        """Lớp yếu ở phương ngữ KHÁC không được chặn lượt chạy này."""
        _viet_split(split_gia, [{"sample_uid": "s1", "class_uid": lop_rong,
                                 "slug": "x", "dialect": "khac", "class_idx": "1"}])
        assert tr._split_classes_below_floor(["d1"], 25) == []

    def test_san_bang_khong_thi_cong_khong_ket_luan_gi(self, split_gia, lop_rong):
        _viet_split(split_gia, [{"sample_uid": "s1", "class_uid": lop_rong,
                                 "slug": "x", "dialect": "d1", "class_idx": "1"}])
        assert tr._split_classes_below_floor(["d1"], 0) == []

    def test_khong_co_tep_split_thi_khong_ket_luan_gi(self, split_gia):
        """Không có gì để soi thì KHÔNG được kết luận là đạt hay không đạt."""
        assert tr._split_classes_below_floor(["d1"], 25) == []

    def test_doc_ca_val_va_test_chu_khong_chi_train(self, split_gia, lop_rong):
        """Một lớp chỉ nằm ở val vẫn chiếm một chiều trong không gian nhãn."""
        _viet_split(split_gia, [])  # train rỗng
        with (split_gia / "val.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAC_COT)
            w.writeheader()
            w.writerow({"sample_uid": "s1", "class_uid": lop_rong,
                        "slug": "x", "dialect": "d1", "class_idx": "1"})

        lan = tr._split_classes_below_floor(["d1"], 25)
        assert [uid for _t, uid, _n in lan] == [lop_rong]


class TestCongChungCu:
    """Lời khai có thể sai. Cổng này chỉ đọc nội dung tệp."""

    def _viet(self, thu_muc: Path, phan_bo):
        """`phan_bo` = {tên_tệp: [(class_uid, số_hàng)]}"""
        for ten in ("train", "val", "test"):
            with (thu_muc / f"{ten}.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=CAC_COT)
                w.writeheader()
                for uid, n in phan_bo.get(ten, []):
                    for i in range(n):
                        w.writerow({"sample_uid": f"{uid}-{ten}-{i}", "class_uid": uid,
                                    "slug": "x", "dialect": "d1", "class_idx": "1"})

    def test_tong_ba_phan_duoi_san_bi_tu_choi_du_khai_bao_ghi_25(self, split_gia):
        """3+1+1=5 phải trượt, kể cả khi `split_metadata.json` khai sàn 25.

        Đây chính là ca hỏng dữ liệu / sửa tay CSV: metadata nói dối, nội dung
        thì không.
        """
        self._viet(split_gia, {"train": [("U1", 3)], "val": [("U1", 1)],
                               "test": [("U1", 1)]})
        write_legacy_snapshot(split_gia, class_keys=["U1"], floor=25, excluded=[],
                              mode="sample", seed=42, counts={})

        van_de = tr._split_evidence_problems(["d1"], 25)

        assert any("dưới sàn 25" in v for v in van_de), van_de
        assert tr._split_snapshot()["policy"]["min_samples_per_class"] == 25, (
            "lời khai vẫn nói 25 — nên nếu cổng chỉ đọc lời khai thì nó đã cho qua")

    def test_lop_vang_mat_o_mot_phan_bi_tu_choi(self, split_gia):
        """Đúng hình dạng sự cố `hoa_de_signer_disjoint_v1/_v3`: val=0, test=0.

        Với sàn 25 và tỉ lệ 70/15/15 thì luôn đủ chỗ cho cả ba phần, nên một
        phần rỗng nghĩa là bộ chia hỏng — không phải dữ liệu hiếm.
        """
        self._viet(split_gia, {"train": [("U1", 30)]})
        van_de = tr._split_evidence_problems(["d1"], 25)
        assert any("vắng mặt" in v and "val/test" in v for v in van_de), van_de

    def test_lop_day_du_thi_khong_ken_gi(self, split_gia):
        self._viet(split_gia, {"train": [("U1", 20)], "val": [("U1", 4)],
                               "test": [("U1", 4)]})
        assert tr._split_evidence_problems(["d1"], 25) == []

    def test_khong_co_tep_thi_khong_ket_luan_gi(self, split_gia):
        assert tr._split_evidence_problems(["d1"], 25) == []


class TestKhongTepNaoThu0Ca:
    """Bất biến rẻ tiền cho một dạng nguy hiểm: hiểu lầm là đang có bảo vệ.

    Nguy không phải test đỏ. Nguy là người viết tưởng test đang canh X, còn
    pytest thì chưa từng chạy X một lần nào. Ngày 14/08/2026 có BẢY tệp như
    vậy, ba trong đó là bộ bảo vệ tập chia.
    """

    def test_moi_tep_test_deu_thu_duoc_it_nhat_mot_ca(self):
        import ast

        thu_muc = Path(__file__).resolve().parent
        # Các tệp bị `collect_ignore` loại khỏi bộ kiểm một cách CÓ CHỦ Ý —
        # chúng chạy như tiến trình con qua `test_research_suites.py`, nơi mã
        # thoát mang phán quyết. Đọc động, không viết cứng.
        try:
            from conftest import STANDALONE_SUITES

            bo_qua = {Path(p).name for p in STANDALONE_SUITES}
        except Exception:
            bo_qua = set()

        trong = []
        for p in sorted(thu_muc.glob("test_*.py")):
            if p.name in bo_qua:
                continue
            cay = ast.parse(p.read_text(encoding="utf-8"))
            n = 0
            for nut in cay.body:
                if isinstance(nut, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and nut.name.startswith("test"):
                    n += 1
                elif isinstance(nut, ast.ClassDef) and nut.name.startswith("Test"):
                    n += sum(1 for b in nut.body
                             if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef))
                             and b.name.startswith("test"))
            if n == 0:
                trong.append(p.name)

        assert not trong, (
            f"{len(trong)} tệp pytest thu được 0 ca — chúng trông như đang được "
            f"kiểm nhưng không: {trong}. Thêm hàm `test_*`, hoặc đưa vào "
            f"STANDALONE_SUITES nếu chúng chạy ở nơi khác.")


class TestDocKhaiBao:
    def test_chua_co_khai_bao_thi_tra_ve_rong_chu_khong_no(self, split_gia):
        """Split dựng trước khi cơ chế này tồn tại vẫn phải chạy được."""
        assert tr._split_snapshot() == {}

    def test_khai_bao_hong_thi_tra_ve_rong_chu_khong_no(self, split_gia):
        (split_gia / "split_metadata.json").write_text("{ hỏng", encoding="utf-8")
        assert tr._split_snapshot() == {}

    def test_doc_duoc_san_da_khai(self, split_gia):
        write_legacy_snapshot(split_gia, class_keys=["U1"], floor=25, excluded=[],
                              mode="sample", seed=42, counts={})
        assert tr._split_snapshot()["min_samples_per_class"] == 25
