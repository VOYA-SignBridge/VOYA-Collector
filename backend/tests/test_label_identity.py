"""Danh tính lớp trong huấn luyện phải là `class_uid`, không phải chuỗi hiển thị.

Ca trung tâm của tệp này là hình dạng mà việc nhập QIPEDC SẼ tạo ra: cùng slug,
cùng dialect, khác region.

    UID_1 | an     | pho-thong | bac
    UID_2 | an     | pho-thong | nam
    UID_3 | cam-on | pho-thong | common

Cơ sở dữ liệu cho phép cả ba cùng tồn tại — khoá duy nhất là
`(tenant_id, slug, language, dialect, region)`. Nhưng `label_key` mà tầng huấn
luyện dùng làm danh tính lại là `vn/<dialect>/<slug>`, KHÔNG có region. Nên
UID_1 và UID_2 ra cùng một khoá và bị gộp thành một lớp.

Đó là loại lỗi nguy nhất: không có ngoại lệ, không có cảnh báo, pipeline chạy
trót lọt và vẫn in ra một con số độ chính xác trông hợp lý. Con số đó nói về
một bài toán 2 lớp trong khi người dùng tưởng mình đang huấn luyện 3.

Đo ngày 14/08/2026: chưa có va chạm nào trong `signdb` — chưa slug nào có nhiều
region cùng dialect. Tệp này viết TRƯỚC khi nhập, chứ không phải sau khi hỏng.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from processed.train_utils.label_mapping import (  # noqa: E402
    MappingError,
    canonical_mapping_hash,
    consume_declared,
    legacy_row_order,
    partitions_agree,
    read_declared,
    validate_mapping,
)


def _hang(uid: str, slug: str, dialect: str, region: str, target_idx: int):
    """Một hàng split đúng hình dạng thật: mang CẢ hai loại khoá."""
    return {
        "class_uid": uid,
        "slug": slug,
        "dialect": dialect,
        "region": region,
        "language": "vn",
        "label_key": f"vn/{dialect}/{slug}",  # khoá cũ — cố ý va chạm được
        "target_idx": str(target_idx),
    }


QIPEDC = [
    _hang("UID_1", "an", "pho-thong", "bac", 0),
    _hang("UID_2", "an", "pho-thong", "nam", 1),
    _hang("UID_3", "cam-on", "pho-thong", "common", 2),
]


def _khai_bao(rows):
    """Bản khai mang ĐỦ metadata hiển thị, và đó là điều kiện để đột biến có nghĩa.

    Bản đầu của hàm này chỉ ghi `class_uid` + `target_idx`. Hệ quả: phép đột
    biến đổi khoá danh tính sang `label_key` KHÔNG làm đỏ được ca nào, vì
    `muc.get("label_key")` trả None rồi rơi về `class_uid` — đột biến thành vô
    hiệu và bộ kiểm trông như mạnh trong khi nó chưa chứng minh gì.

    Hiện vật thật mang cả `slug`, `dialect`, `region` (để đọc được checkpoint),
    nên fixture phải mang chúng. Chỉ khi bản khai chứa một khoá hiển thị VA
    CHẠM ĐƯỢC thì "danh tính phải là class_uid" mới là một khẳng định kiểm
    được.
    """
    anh_xa = {r["class_uid"]: int(r["target_idx"]) for r in rows}
    return {
        "purpose": "operational",
        "classes": [
            {"class_uid": r["class_uid"], "target_idx": int(r["target_idx"]),
             "class_idx": 100 + int(r["target_idx"]),
             "slug": r["slug"], "dialect": r["dialect"], "region": r["region"],
             "label_key": r["label_key"]}
            for r in rows
        ],
        "class_mapping_hash": canonical_mapping_hash(anh_xa),
    }


class TestHinhDangQIPEDC:
    def test_ba_lop_chu_khong_phai_hai(self):
        """Bất biến chính. Nếu ca này xanh khi khoá là `label_key` thì nó vô dụng
        — có một ca riêng bên dưới chứng minh nó KHÔNG xanh."""
        anh_xa = consume_declared(_khai_bao(QIPEDC))

        assert len(anh_xa) == 3, f"gộp mất lớp: {anh_xa}"
        assert anh_xa["UID_1"] != anh_xa["UID_2"], (
            "hai biến thể vùng của cùng một từ phải là hai chiều đầu ra khác nhau")
        assert sorted(anh_xa.values()) == [0, 1, 2]

    def test_khoa_cu_THAT_SU_va_cham(self):
        """Chứng minh mối nguy có thật thay vì chỉ khẳng định nó có thật.

        Nếu ba hàng này không va chạm dưới `label_key` thì cả tệp test này
        không bảo vệ điều gì cả.
        """
        khoa_cu = {r["label_key"] for r in QIPEDC}
        assert len(khoa_cu) == 2, (
            f"fixture không còn tái hiện được va chạm: {khoa_cu}")

        l2i, _ = legacy_row_order(QIPEDC)
        assert len(l2i) == 2, "đường tương thích cũ gộp 3 lớp còn 2 — đúng như mô tả"

    def test_khac_nhau_o_MOI_region_deu_giu_duoc(self):
        rows = [_hang(f"UID_{i}", "an", "pho-thong", v, i)
                for i, v in enumerate(("bac", "trung", "nam", "common", "unclassified"))]
        assert len(consume_declared(_khai_bao(rows))) == 5


class TestBaKiemDocLap:
    def test_song_anh_chu_khong_chi_lien_tuc(self):
        """`{A:0, B:0, C:1}` có tập chỉ số {0,1} và "không thủng lỗ" theo nghĩa
        hẹp, nhưng hai lớp dùng chung một chiều đầu ra — đúng hình dạng lỗi gộp
        vùng. Kiểm liên tục thôi sẽ cho nó lọt."""
        with pytest.raises(MappingError) as loi:
            validate_mapping({"A": 0, "B": 0, "C": 1})
        assert "dùng chung một target_idx" in str(loi.value)

    def test_phai_lien_tuc_0_den_K_tru_1(self):
        with pytest.raises(MappingError) as loi:
            validate_mapping({"A": 0, "B": 2})
        assert "liên tục" in str(loi.value)

    def test_khong_duoc_bat_dau_tu_1(self):
        with pytest.raises(MappingError):
            validate_mapping({"A": 1, "B": 2})

    def test_anh_xa_rong_bi_tu_choi(self):
        with pytest.raises(MappingError):
            validate_mapping({})

    def test_bool_khong_duoc_coi_la_so_nguyen(self):
        """`isinstance(True, int)` là True trong Python — cạm bẫy im lặng."""
        with pytest.raises(MappingError):
            validate_mapping({"A": False, "B": 1})


class TestBaPhanPhaiNoiCungMotChuyen:
    def test_uid_lech_target_idx_giua_train_va_val_bi_bat(self):
        """Mỗi tệp một mình trông hợp lệ; chỉ đối chiếu chéo mới thấy."""
        anh_xa = {"UID_1": 0, "UID_2": 1}
        train = [_hang("UID_1", "an", "pho-thong", "bac", 0)]
        val = [_hang("UID_1", "an", "pho-thong", "bac", 1)]  # lệch

        with pytest.raises(MappingError) as loi:
            partitions_agree({"train": train, "val": val}, anh_xa)
        assert "khác nhau giữa các phần" in str(loi.value)

    def test_uid_la_trong_split_bi_tu_choi_chu_khong_bi_loc(self):
        anh_xa = {"UID_1": 0}
        rows = [_hang("UID_1", "an", "pho-thong", "bac", 0),
                _hang("UID_LA", "moi", "pho-thong", "bac", 1)]

        with pytest.raises(MappingError) as loi:
            partitions_agree({"train": rows}, anh_xa)
        assert "KHÔNG nằm trong bản khai" in str(loi.value)
        assert "nói sai về nguồn gốc" in str(loi.value), (
            "câu báo lỗi phải nói vì sao KHÔNG lọc, nếu không người sau sẽ lọc")

    def test_khop_thi_khong_ken_gi(self):
        anh_xa = {r["class_uid"]: int(r["target_idx"]) for r in QIPEDC}
        partitions_agree({"train": QIPEDC, "val": QIPEDC[:1]}, anh_xa)


class TestKhongCoDuongROI:
    """Không có nhánh "thiếu class_uid thì dùng label_key"."""

    def test_thieu_class_uid_thi_TU_CHOI(self):
        meta = {"classes": [{"target_idx": 0}, {"target_idx": 1}],
                "class_mapping_hash": "x"}
        with pytest.raises(MappingError) as loi:
            consume_declared(meta)
        assert "thiếu `class_uid`" in str(loi.value)

    def test_thieu_target_idx_thi_TU_CHOI(self):
        meta = {"classes": [{"class_uid": "A"}], "class_mapping_hash": "x"}
        with pytest.raises(MappingError) as loi:
            consume_declared(meta)
        assert "thiếu `target_idx`" in str(loi.value)

    def test_thieu_mapping_hash_thi_TU_CHOI(self):
        meta = {"classes": [{"class_uid": "A", "target_idx": 0},
                            {"class_uid": "B", "target_idx": 1}]}
        with pytest.raises(MappingError) as loi:
            consume_declared(meta)
        assert "class_mapping_hash" in str(loi.value)

    def test_hash_khong_khop_chinh_no_thi_TU_CHOI(self):
        """Hiện vật bị sửa sau khi ghi: `classes` nói một đằng, hash một nẻo."""
        meta = _khai_bao(QIPEDC)
        meta["classes"][0]["target_idx"] = 2
        meta["classes"][2]["target_idx"] = 0
        with pytest.raises(MappingError) as loi:
            consume_declared(meta)
        assert "không khớp với chính mục `classes`" in str(loi.value)

    def test_khong_co_classes_thi_TU_CHOI(self):
        with pytest.raises(MappingError):
            consume_declared({"purpose": "operational", "class_mapping_hash": "x"})


class TestMaBamDanhTinh:
    def test_bam_theo_class_uid_khong_theo_nhan_hien_thi(self):
        """Đổi nhãn hiển thị của vùng KHÔNG được làm đổi mã băm danh tính."""
        a = canonical_mapping_hash({"UID_1": 0, "UID_2": 1})
        b = canonical_mapping_hash({"UID_2": 1, "UID_1": 0})
        assert a == b

    def test_doi_vi_tri_dau_ra_thi_bam_PHAI_doi(self):
        assert (canonical_mapping_hash({"UID_1": 0, "UID_2": 1})
                != canonical_mapping_hash({"UID_1": 1, "UID_2": 0}))

    def test_them_lop_thi_bam_doi(self):
        assert (canonical_mapping_hash({"A": 0, "B": 1})
                != canonical_mapping_hash({"A": 0, "B": 1, "C": 2}))


class TestBatBienCuaDuongVanHanh:
    """Hai điều kiện mà `train_tcn` phải giữ khi đi đường vận hành."""

    def test_dao_thu_tu_hang_KHONG_doi_target_idx(self):
        """Đây là thứ đường cũ KHÔNG có.

        `_build_subset_label_maps` gom nhãn theo thứ tự hàng, nên đảo CSV là
        đổi ngữ nghĩa đầu ra. Ánh xạ đã khai thì neo vào `class_uid`.
        """
        xuoi = consume_declared(_khai_bao(QIPEDC))
        nguoc = consume_declared(_khai_bao(list(reversed(QIPEDC))))
        assert xuoi == nguoc

        # và đường CŨ thì đổi thật — nếu không, so sánh trên vô nghĩa
        cu_xuoi, _ = legacy_row_order(QIPEDC)
        cu_nguoc, _ = legacy_row_order(list(reversed(QIPEDC)))
        assert cu_xuoi != cu_nguoc, (
            "fixture không tái hiện được tính phụ thuộc thứ tự của đường cũ")

    def test_doi_class_idx_KHONG_doi_target_idx(self):
        """`class_idx` là định danh danh mục, thưa và đổi được. `target_idx`
        là vị trí đầu ra. Đổi cái trước không được động tới cái sau."""
        khai = _khai_bao(QIPEDC)
        for muc in khai["classes"]:
            muc["class_idx"] = muc["class_idx"] * 7 + 13  # thưa hẳn ra
        assert consume_declared(khai) == consume_declared(_khai_bao(QIPEDC))

    def test_hai_vung_cung_slug_van_la_hai_lop(self):
        anh_xa = consume_declared(_khai_bao(QIPEDC))
        assert anh_xa["UID_1"] != anh_xa["UID_2"]
        assert len(set(anh_xa.values())) == 3


class TestNhanhDaDuocNoiThat:
    """Chứng minh mã mới NẰM TRONG đường chạy, không chỉ nằm cạnh nó.

    Giới hạn của ca này, nói trước: nó đọc CẤU TRÚC của `train_tcn.main()`
    bằng AST, không chạy huấn luyện. Nó chứng minh nhánh vận hành tồn tại và
    gọi đúng hàm; nó KHÔNG chứng minh một lượt huấn luyện thật cho ra ánh xạ
    đúng. Ca đó cần npz thật và thuộc lượt sau (checkpoint round-trip).

    Vẫn đáng có: sai lầm hay gặp nhất khi thêm một tầng mới là để nó tồn tại
    song song mà không ai gọi — và bộ kiểm đơn vị của tầng đó vẫn xanh rực.
    """

    def _than_main(self):
        import ast

        p = REPO_ROOT / "processed" / "train_utils" / "train_tcn.py"
        cay = ast.parse(p.read_text(encoding="utf-8"))
        for nut in cay.body:
            if isinstance(nut, ast.FunctionDef) and nut.name == "main":
                return nut
        pytest.fail("không tìm thấy train_tcn.main()")

    def _ten_ham_duoc_goi(self, nut):
        import ast

        ra = set()
        for con in ast.walk(nut):
            if isinstance(con, ast.Call):
                f = con.func
                if isinstance(f, ast.Name):
                    ra.add(f.id)
                elif isinstance(f, ast.Attribute):
                    ra.add(f.attr)
        return ra

    def test_main_co_goi_consume_declared(self):
        goi = self._ten_ham_duoc_goi(self._than_main())
        assert "consume_declared" in goi, (
            "train_tcn.main() không gọi consume_declared — tầng ánh xạ mới "
            "đang nằm cạnh đường chạy chứ không nằm trong nó")
        assert "read_declared" in goi
        assert "partitions_agree" in goi, (
            "thiếu đối chiếu ba phần: mỗi tệp riêng lẻ có thể hợp lệ trong khi "
            "cùng một class_uid mang target_idx khác nhau giữa chúng")

    def test_duong_cu_van_con_cho_nghien_cuu(self):
        """Không được xoá đường cũ — hiện vật nghiên cứu đã đóng băng cần nó
        để tái lập đúng hành vi lịch sử."""
        assert "_build_subset_label_maps" in self._ten_ham_duoc_goi(self._than_main())


class TestCheckpointGiuNguyenAnhXa:
    """Mắt xích cuối: split khai → trainer học → checkpoint đóng băng → suy luận.

    Ca quan trọng nhất không phải lưu/nạp riêng lẻ mà là ĐI TRỌN VÒNG: ánh xạ
    và mã băm trước phải bằng đúng ánh xạ và mã băm sau.
    """

    def _ckpt(self, rows=None):
        from processed.train_utils.label_mapping import (
            CHECKPOINT_MAPPING_KEY, build_checkpoint_mapping,
        )

        rows = rows or QIPEDC
        khai = _khai_bao(rows)
        anh_xa = {r["class_uid"]: int(r["target_idx"]) for r in rows}
        return anh_xa, {
            CHECKPOINT_MAPPING_KEY: build_checkpoint_mapping(
                anh_xa, khai["classes"]),
        }

    def test_di_tron_vong_anh_xa_va_hash_khong_doi(self):
        from processed.train_utils.label_mapping import (
            CHECKPOINT_MAPPING_KEY, canonical_mapping_hash,
            consume_checkpoint_mapping,
        )

        truoc, ckpt = self._ckpt()
        sau_nguoc = consume_checkpoint_mapping(ckpt)
        sau = {uid: idx for idx, uid in sau_nguoc.items()}

        assert sau == truoc
        assert (ckpt[CHECKPOINT_MAPPING_KEY]["class_mapping_hash"]
                == canonical_mapping_hash(truoc))

    def test_giai_ma_ra_dung_class_uid_cho_tung_vi_tri(self):
        from processed.train_utils.label_mapping import consume_checkpoint_mapping

        _, ckpt = self._ckpt()
        idx_to_uid = consume_checkpoint_mapping(ckpt)
        assert idx_to_uid[0] == "UID_1"
        assert idx_to_uid[1] == "UID_2"
        assert idx_to_uid[0] != idx_to_uid[1], "hai vùng của cùng slug"

    def test_dao_thu_tu_classes_KHONG_doi_ngu_nghia(self):
        """Đột biến 1. `classes` là danh sách, nhưng ngữ nghĩa là ánh xạ —
        thứ tự phần tử không được mang thông tin."""
        from processed.train_utils.label_mapping import (
            CHECKPOINT_MAPPING_KEY, consume_checkpoint_mapping,
        )

        _, ckpt = self._ckpt()
        xuoi = consume_checkpoint_mapping(ckpt)
        ckpt[CHECKPOINT_MAPPING_KEY]["classes"].reverse()
        assert consume_checkpoint_mapping(ckpt) == xuoi

    def test_sua_target_idx_ma_giu_hash_cu_thi_TU_CHOI_nap(self):
        """Đột biến 2, và là ca đáng giá nhất.

        Nạp một checkpoint như vậy nghĩa là giải mã SAI mọi dự đoán mà không có
        một dấu hiệu nào — độ chính xác vẫn ra số, nhãn vẫn ra chữ.
        """
        from processed.train_utils.label_mapping import (
            CHECKPOINT_MAPPING_KEY, MappingError, consume_checkpoint_mapping,
        )

        _, ckpt = self._ckpt()
        lop = ckpt[CHECKPOINT_MAPPING_KEY]["classes"]
        lop[0]["target_idx"], lop[1]["target_idx"] = (
            lop[1]["target_idx"], lop[0]["target_idx"])

        with pytest.raises(MappingError) as loi:
            consume_checkpoint_mapping(ckpt)
        assert "không khớp chính mục classes" in str(loi.value)
        assert "TỪ CHỐI nạp" in str(loi.value)

    def test_doi_labels_csv_sau_do_KHONG_doi_ket_qua_giai_ma(self, monkeypatch, tmp_path):
        """Đột biến 3: chứng minh đã triệt lỗi provenance theo thời gian.

        `dataset_loader` từng dựng ánh xạ từ `labels.csv` HIỆN TẠI khi thiếu
        tệp ánh xạ. Nếu chuỗi này còn sót đường đó, đổi danh mục sau khi tạo
        checkpoint sẽ đổi kết quả giải mã.
        """
        from processed.train_utils.label_mapping import consume_checkpoint_mapping

        _, ckpt = self._ckpt()
        truoc = consume_checkpoint_mapping(ckpt)

        gia = tmp_path / "labels.csv"
        gia.write_text("class_uid,class_idx,slug\nUID_1,999,khac-han\n",
                       encoding="utf-8")
        monkeypatch.setenv("VOYA_DATA_ROOT", str(tmp_path))

        assert consume_checkpoint_mapping(ckpt) == truoc

    def test_thieu_khoi_anh_xa_thi_noi_ro_chu_khong_doan(self):
        from processed.train_utils.label_mapping import (
            MappingError, consume_checkpoint_mapping,
        )

        with pytest.raises(MappingError) as loi:
            consume_checkpoint_mapping({"model_state_dict": {}})
        assert "đường tương thích riêng" in str(loi.value)

    def test_metadata_hien_thi_duoc_chep_kem_nhung_khong_quyet_dinh_gi(self):
        """`slug/dialect/region` có mặt để đọc; danh tính vẫn là class_uid."""
        from processed.train_utils.label_mapping import (
            CHECKPOINT_MAPPING_KEY, consume_checkpoint_mapping,
        )

        _, ckpt = self._ckpt()
        lop = {c["class_uid"]: c for c in ckpt[CHECKPOINT_MAPPING_KEY]["classes"]}
        assert lop["UID_1"]["region"] == "bac" and lop["UID_2"]["region"] == "nam"
        assert lop["UID_1"]["slug"] == lop["UID_2"]["slug"] == "an"

        truoc = consume_checkpoint_mapping(ckpt)
        for c in ckpt[CHECKPOINT_MAPPING_KEY]["classes"]:
            c["slug"], c["region"], c["class_idx"] = "doi-het", "trung", 1
        assert consume_checkpoint_mapping(ckpt) == truoc, (
            "đổi metadata hiển thị KHÔNG được làm đổi ánh xạ ngữ nghĩa")


class TestDocKhaiBao:
    def test_khong_co_tep_thi_None(self, tmp_path):
        assert read_declared(tmp_path) is None

    def test_tep_hong_thi_NEM_chu_khong_im_lang(self, tmp_path):
        """Khác `_split_snapshot` phía backend (chỉ để làm câu báo lỗi đẹp hơn):
        ở đây bản khai LÀ nguồn danh tính, nên đọc không được phải dừng."""
        (tmp_path / "split_metadata.json").write_text("{ hỏng", encoding="utf-8")
        with pytest.raises(MappingError):
            read_declared(tmp_path)

    def test_doc_duoc_thi_dung_duoc_ngay(self, tmp_path):
        (tmp_path / "split_metadata.json").write_text(
            json.dumps(_khai_bao(QIPEDC), ensure_ascii=False), encoding="utf-8")
        assert len(consume_declared(read_declared(tmp_path))) == 3
