"""`region` là một phần ĐỊNH DANH của lớp, không phải chú thích.

Cơ sở dữ liệu đã nói điều đó từ v3.18: khoá duy nhất là
`(tenant_id, slug, language, dialect, region)`. Nhưng tầng ứng dụng thì chưa —
và ba chỗ dưới đây, tìm ra ngày 15/08/2026 khi dựng hai lớp vùng thật đầu tiên,
đều dùng khoá BỐN cột trong khi cơ sở dữ liệu dùng khoá NĂM cột.

Cả ba đều im lặng. Không lỗi, không cảnh báo, API trả 200, và người dùng nhận
về một thứ trông hợp lệ:

  1. `register_class` — phép tìm "lớp đã tồn tại chưa" bỏ qua `region`. Tạo
     `ăn|pho-thong|bac` rồi tạo `ăn|pho-thong|nam` thì lần thứ hai KHÔNG tạo
     gì; nó trả về lớp `bac`. Mọi mẫu thu cho "miền Nam" sau đó rơi vào lớp
     miền Bắc.
  2. `list_classes` — dựng lại `ClassMetadata` mà không truyền `region`, nên
     MỌI lớp trong `/classes/list` trả về `unclassified`. Hai biến thể miền
     hiện ra hai dòng giống hệt nhau, không cách nào phân biệt.
  3. `catalog_sync._build_updated_class_meta` — cũng dựng lại thiếu `region`,
     nên MỖI lần sửa nhãn là một lần XOÁ vùng: sửa chính tả của `ăn [bac]` là
     nó thành `ăn [unclassified]`.

Lỗi (3) nặng nhất vì nó phá dữ liệu đã đúng, và nó chạy ở một thao tác mà
không ai ngờ có liên quan tới vùng miền.

Từ điển quốc gia có 483 từ mang biến thể miền. Ba lỗi này là ba cách khác nhau
để gộp sạch chúng lại trong lúc nhập.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.dataset_manager import (  # noqa: E402
    REGION_UNCLASSIFIED,
    normalize_region,
)

SLUG = "an-vung-test"
COT_TOI_THIEU = ("class_uid", "class_idx", "slug", "label_original", "language",
                 "dialect", "region", "folder_name", "is_active")


def _hang(uid: str, idx: int, region: str) -> dict:
    return {"class_uid": uid, "class_idx": str(idx), "slug": SLUG,
            "label_original": "an", "language": "vn", "dialect": "pho-thong",
            "region": region, "folder_name": f"class_{SLUG}_{uid}",
            "is_active": "1"}


@pytest.fixture
def phuong_ngu_that():
    """`pho-thong` phải TỒN TẠI trong `dialects`, và test phải tự dựng nó.

    `register_class` gọi `_assert_known_dialect`, đọc thẳng bảng `dialects`.
    Bản đầu của tệp này không dựng gì — nó xanh vì tôi đã chèn `pho-thong` vào
    `signdb_test` bằng tay lúc thử nghiệm, rồi dọn đi ở lượt sau. Ba ca ĐỎ ngay
    lượt full suite kế tiếp.

    Đó là xanh-giả kiểu quen thuộc theo một đường khác: **bài kiểm dựa vào
    trạng thái môi trường mà nó không tự tạo**. Chạy riêng lẻ thì xanh, chạy
    trên một máy sạch thì đỏ — và cái nó thật sự đo được là "hôm nay CSDL tình
    cờ có gì", không phải bất biến nó tuyên bố.
    """
    from app.storage.metadata_db import _execute, _fetch_all
    from app.tenant_context import system_scope

    with system_scope("test: dựng phương ngữ"):
        da_co = _fetch_all(
            "SELECT 1 FROM dialects WHERE tenant_id='default' AND dialect_id=%s",
            ("pho-thong",))
        if not da_co:
            _execute(
                "INSERT INTO dialects(tenant_id, dialect_id, display_name, "
                "language, status) VALUES('default','pho-thong','Phổ thông',"
                "'vn','approved')")
    yield "pho-thong"
    # Chỉ dọn thứ CHÍNH MÌNH tạo. Xoá một phương ngữ vốn đã có ở đó là để lại
    # môi trường tệ hơn lúc nhận — đúng cái đã gây ra ba ca đỏ này.
    if not da_co:
        with system_scope("test cleanup"):
            _execute("DELETE FROM dialects WHERE tenant_id='default' "
                     "AND dialect_id='pho-thong'")


@pytest.fixture
def kho_tam(monkeypatch, tmp_path):
    """Kho dữ liệu tạm, và `dataset_manager` được nạp LẠI để trỏ vào nó.

    `MASTER_LABELS` được phân giải lúc NẠP MODULE, nên đặt `DATASET_ROOT` sau
    đó không có tác dụng — bài thử sẽ lặng lẽ ghi vào `dataset/labels.csv`
    thật. Đây đúng là sự cố 13/08 ở dạng khác, nên nó được nói ra ở đây.
    """
    import importlib

    from app import dataset_manager as dm

    monkeypatch.setenv("DATASET_ROOT", str(tmp_path))
    monkeypatch.setattr(dm, "MASTER_LABELS", tmp_path / "labels.csv")
    monkeypatch.setattr(dm, "DATASET_ROOT", tmp_path)
    assert dm.MASTER_LABELS.parent == tmp_path
    yield dm
    importlib.reload(dm)


def _viet_labels(dm, hang):
    with dm.MASTER_LABELS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=dm.LABEL_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(hang)


class TestVungLaDinhDanh:
    def test_khoa_nam_cot_chu_khong_bon(self, kho_tam):
        """Hai biến thể miền là HAI lớp, không phải một lớp được ghi chú."""
        dm = kho_tam
        _viet_labels(dm, [_hang("RG-BAC", 901, "bac"), _hang("RG-NAM", 902, "nam")])

        metas = [m for m in dm.list_classes(language="vn", dialect="pho-thong",
                                            tenant_id="default")
                 if m.slug == SLUG]

        assert len(metas) == 2, f"gộp mất một lớp: {len(metas)}"
        assert {m.class_uid for m in metas} == {"RG-BAC", "RG-NAM"}
        assert {m.region for m in metas} == {"bac", "nam"}, (
            "region bị đánh rơi — hai dòng sẽ hiện ra GIỐNG HỆT nhau ở giao diện")

    def test_to_label_row_mang_region_ra_toi_API(self, kho_tam):
        """`/classes/list` trả về đúng thứ này; thiếu là giao diện mù."""
        dm = kho_tam
        _viet_labels(dm, [_hang("RG-BAC", 901, "bac"), _hang("RG-NAM", 902, "nam")])

        theo_uid = {m.class_uid: m.to_label_row()
                    for m in dm.list_classes(language="vn", dialect="pho-thong",
                                             tenant_id="default")
                    if m.slug == SLUG}

        assert theo_uid["RG-BAC"]["region"] == "bac"
        assert theo_uid["RG-NAM"]["region"] == "nam"


class TestDangKyKhongGopHaiVung:
    def test_tao_bien_the_thu_hai_KHONG_tra_ve_lop_cu(self, kho_tam, phuong_ngu_that):
        """Ca đắt nhất của tệp này, và nó từng đỏ.

        Trước bản vá: lần gọi thứ hai trả về CÙNG `class_uid` và `region='bac'`.
        API trả 200 kèm một lớp trông hợp lệ, nên người dùng không có cách nào
        biết biến thể miền Nam chưa từng được tạo.
        """
        dm = kho_tam
        a = dm.register_class("an", "vn", phuong_ngu_that, region="bac")
        b = dm.register_class("an", "vn", phuong_ngu_that, region="nam")

        assert a.class_uid != b.class_uid, (
            "lần tạo thứ hai trả về lớp cũ — biến thể miền Nam chưa từng tồn tại")
        assert (a.region, b.region) == ("bac", "nam")
        assert a.slug == b.slug and a.dialect == b.dialect

    def test_goi_lai_dung_mot_vung_van_tra_ve_lop_cu(self, kho_tam, phuong_ngu_that):
        """Không được đi quá đà: cùng vùng thì vẫn là cùng một lớp."""
        dm = kho_tam
        a = dm.register_class("an", "vn", phuong_ngu_that, region="bac")
        lai = dm.register_class("an", "vn", phuong_ngu_that, region="bac")

        assert a.class_uid == lai.class_uid

    def test_bo_trong_vung_thi_unclassified_chu_khong_doan(self, kho_tam, phuong_ngu_that):
        """`unclassified` là một BƯỚC trong quy trình, không phải chỗ trống.

        Cố ý không rơi về `common`: `common` nghĩa là "đã xác minh rằng không
        cần phân biệt vùng" — một khẳng định mạnh hơn hẳn "chưa ai xem".
        """
        dm = kho_tam
        m = dm.register_class("cam on", "vn", phuong_ngu_that)

        assert m.region == REGION_UNCLASSIFIED


class TestKhongNoiVungThiKhongDuocDE_THEM_LOP:
    """Hồi quy 15/08/2026 — bản vá vùng tự nó đẻ ra một lỗi nặng hơn.

    Khi `region` bước vào phép tìm, `unclassified` thôi là "chỗ trống" và trở
    thành một GIÁ TRỊ CỤ THỂ phải khớp. Nhưng mọi đường thu mẫu —
    `upload.py` (video và camera) và `processing/pipeline.py` — gọi
    `get_or_register_class(label, language, dialect)` mà không truyền vùng.

    Sản xuất có 60/60 nhãn mang `region='nam'`. Phép tìm không khớp cái nào,
    nên hàm rơi xuống nhánh TẠO và sinh ra lớp thứ hai. Mẫu vừa thu đi vào lớp
    ma ấy. Khoá duy nhất năm cột KHÔNG chặn — hai vùng là hai lớp hợp lệ, đó
    chính là điều nó được dựng lên để cho phép.

    Ba ca dưới đây khoá ba nửa của cùng một quy tắc: không nói ra vùng nghĩa là
    "nhãn nào cũng được, miễn không mơ hồ", còn nói ra thì là một khẳng định.
    """

    def test_nhan_da_co_MOT_vung_thi_dung_lai_no(self, kho_tam, phuong_ngu_that):
        """Ca đắt nhất: đúng đường mà thu mẫu trực tiếp đang đi."""
        dm = kho_tam
        _viet_labels(dm, [_hang("RG-NAM", 902, "nam")])

        meta = dm.get_or_register_class(
            label_original=SLUG, language="vn", dialect=phuong_ngu_that)

        con_lai = list(csv.DictReader(dm.MASTER_LABELS.open(encoding="utf-8")))
        assert len(con_lai) == 1, (
            f"da de them lop: {[r['class_uid'] + '/' + r['region'] for r in con_lai]}")
        assert meta.class_uid == "RG-NAM"
        assert meta.region == "nam", "tra ve lop dung nhung mat vung"

    def test_nhieu_bien_the_vung_ma_khong_noi_ro_thi_TU_CHOI(self, kho_tam, phuong_ngu_that):
        """Mơ hồ thì dừng, đừng đoán.

        `ăn|bac` và `ăn|nam` cùng tồn tại thì một yêu cầu chỉ nói "ăn" không có
        câu trả lời đúng. Đoán một trong hai là ghi dữ liệu vào lớp sai — hỏng
        nặng hơn hẳn việc từ chối, vì nó không để lại dấu vết nào.
        """
        dm = kho_tam
        _viet_labels(dm, [_hang("RG-BAC", 901, "bac"), _hang("RG-NAM", 902, "nam")])

        with pytest.raises(ValueError) as loi:
            dm.get_or_register_class(
                label_original=SLUG, language="vn", dialect=phuong_ngu_that)

        assert "bac" in str(loi.value) and "nam" in str(loi.value), (
            f"loi phai NOI RA co nhung vung nao de con chon: {loi.value}")
        assert len(list(csv.DictReader(dm.MASTER_LABELS.open(encoding="utf-8")))) == 2, (
            "da tu choi ma van ghi them dong")

    def test_mo_ho_ke_ca_khi_MOT_bien_the_la_unclassified(self, kho_tam, phuong_ngu_that):
        """Ca mà bộ kiểm bỏ sót và smoke sau triển khai bắt được.

        Ba ca trên dựng `bac` + `nam` — không cái nào là giá trị MẶC ĐỊNH. Bản
        vá đầu vẫn so khớp chính xác `region_key` (= `unclassified` khi bỏ
        trống) TRƯỚC, rồi mới xét mơ hồ nếu không khớp gì. Với `bac` + `nam`
        thì phép so ấy không khớp gì nên nhánh mơ hồ chạy, và ba ca đều xanh.

        Nhưng khi một biến thể LÀ `unclassified`, phép so khớp ngay và nhánh mơ
        hồ không bao giờ chạy: hệ thống lặng lẽ chọn bản `unclassified` thay vì
        từ chối. Đúng thứ mà "đừng đoán" cấm.

        Bài học chung: khi kiểm một quy tắc về "nhiều giá trị khác nhau", phải
        có ít nhất một ca mà một trong các giá trị ấy là MẶC ĐỊNH của hệ thống.
        """
        dm = kho_tam
        _viet_labels(dm, [_hang("RG-NAM", 902, "nam"),
                          _hang("RG-CHUA", 903, REGION_UNCLASSIFIED)])

        with pytest.raises(ValueError) as loi:
            dm.get_or_register_class(
                label_original=SLUG, language="vn", dialect=phuong_ngu_that)

        assert "nam" in str(loi.value) and REGION_UNCLASSIFIED in str(loi.value)
        assert len(list(csv.DictReader(dm.MASTER_LABELS.open(encoding="utf-8")))) == 2

    def test_noi_RO_unclassified_van_la_mot_khang_dinh(self, kho_tam, phuong_ngu_that):
        """Nửa còn lại, và nó giữ cho bản vá không đi quá tay.

        `region=None` (không nhắc tới) khác `region='unclassified'` (nói rõ).
        Nếu gộp hai thứ này thì không còn cách nào tạo một lớp `unclassified`
        bên cạnh một biến thể vùng đã có — mà đó là trạng thái hợp lệ:
        "từ này đã có bản miền Nam, và đây là một bản chưa ai phân loại".
        """
        dm = kho_tam
        _viet_labels(dm, [_hang("RG-NAM", 902, "nam")])

        meta = dm.get_or_register_class(
            label_original=SLUG, language="vn", dialect=phuong_ngu_that,
            region=REGION_UNCLASSIFIED)

        assert meta.class_uid != "RG-NAM"
        assert meta.region == REGION_UNCLASSIFIED
        assert len(list(csv.DictReader(dm.MASTER_LABELS.open(encoding="utf-8")))) == 2


class TestSuaNhanKhongDuocXoaVung:
    """Lỗi phá dữ liệu ĐÃ ĐÚNG, ở một thao tác không ai ngờ liên quan."""

    def test_payload_im_lang_thi_GIU_NGUYEN_vung(self):
        from app.catalog_sync import _build_updated_class_meta

        meta = _build_updated_class_meta(_hang("RG-BAC", 901, "bac"),
                                         {"label_original": "an sang"})

        assert meta.region == "bac", (
            f"sửa chính tả nhãn đã xoá vùng thành {meta.region!r} — "
            f"bản ghi không còn phân biệt được với biến thể miền khác")

    def test_payload_noi_ra_thi_doi_duoc(self):
        from app.catalog_sync import _build_updated_class_meta

        meta = _build_updated_class_meta(_hang("RG-BAC", 901, "bac"),
                                         {"label_original": "an", "region": "trung"})

        assert meta.region == "trung"

    def test_gia_tri_rac_roi_ve_unclassified_chu_khong_doan_bua(self):
        """Giá trị lạ KHÔNG được đoán thành một vùng cụ thể.

        Rơi về `unclassified` để người phân loại còn thấy mà xử lý, thay vì
        biến mất thành một vùng nào đó không ai chọn.
        """
        from app.catalog_sync import _build_updated_class_meta

        meta = _build_updated_class_meta(_hang("RG-BAC", 901, "bac"),
                                         {"label_original": "an",
                                          "region": "khong-co-vung-nay"})

        assert meta.region == REGION_UNCLASSIFIED


class TestChuanHoaVung:
    @pytest.mark.parametrize("vao,ra", [
        ("bac", "bac"), ("Bắc", "bac"), ("north", "bac"),
        ("nam bộ", "nam"), ("south", "nam"), ("chung", "common"),
        ("", REGION_UNCLASSIFIED), (None, REGION_UNCLASSIFIED),
        ("khong-co-that", REGION_UNCLASSIFIED),
    ])
    def test_chuan_hoa(self, vao, ra):
        assert normalize_region(vao) == ra

    def test_khong_bao_gio_tra_rong(self):
        """Cột `classes.region` là NOT NULL từ v3.19."""
        for v in ("", None, "   ", "rác"):
            assert normalize_region(v), f"{v!r} cho ra giá trị rỗng"
