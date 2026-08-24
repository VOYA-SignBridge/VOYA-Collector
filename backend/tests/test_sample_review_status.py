"""Trạng thái kiểm duyệt của mẫu: nó bắt đầu ở đâu, và cái gì được phép đổi nó.

Xem docs/01-architecture/COMMUNITY_MODERATION.md.

Test đáng giá nhất ở đây là `test_dong_bo_im_lang_KHONG_ha_cap_mau_da_duyet`.
Nó canh một cái bẫy cụ thể trong `SQL_UPSERT_SAMPLE`: mệnh đề `VALUES` thay giá
trị vắng mặt bằng `'pending'`, nên `EXCLUDED.review_status` **không bao giờ
NULL**. Một mệnh đề `ON CONFLICT` viết theo thói quen —
`COALESCE(EXCLUDED.review_status, samples.review_status)` — sẽ hạ cấp mọi mẫu
đã duyệt về trạng thái chờ ở lượt đồng bộ CSV kế tiếp, xoá sạch công của người
kiểm duyệt mà không sinh ra một lỗi nào. Cùng cái bẫy mà `tenant_id` đã mắc và
đã ghi lại ngay trong SQL ấy.
"""

from __future__ import annotations

import uuid

import pytest

from app.storage import metadata_db as db
from app.tenancy import DEFAULT_TENANT_ID
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture
def lop_va_mau():
    """Một lớp dùng một lần, và một hàm đúc `sample_uid` hợp lệ cho nó.

    `sample_uid` phải là ĐÚNG 10 ký tự hex thường — ràng buộc
    `samples_uid_is_hex10`. Một tiền tố dễ đọc kiểu `test_smp_…` bị CHECK từ
    chối, và thông báo lỗi khi đó nói về ràng buộc chứ không nói về fixture.
    """
    tag = uuid.uuid4().hex[:8]
    class_uid = f"revtest_cls_{tag}"
    da_tao: list[str] = []

    with system_scope("test: dung lop tam"):
        db._execute(
            "INSERT INTO classes (tenant_id, class_uid, slug, label_original) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (DEFAULT_TENANT_ID, class_uid, f"revtest-{tag}", "lop cho test kiem duyet"))

    def _mau() -> str:
        uid = uuid.uuid4().hex[:10]
        da_tao.append(uid)
        return uid

    yield class_uid, _mau

    with system_scope("test cleanup: go lop tam"):
        for sql, args in (
            ("DELETE FROM samples WHERE sample_uid = ANY(%s)", (da_tao,)),
            ("DELETE FROM classes WHERE tenant_id = %s AND class_uid = %s",
             (DEFAULT_TENANT_ID, class_uid)),
        ):
            try:
                db._execute(sql, args)
            except Exception:
                pass


def _trang_thai(sample_uid: str) -> str:
    with system_scope("test: doc trang thai duyet"):
        rows = db._fetch_all(
            "SELECT review_status FROM samples WHERE sample_uid = %s", (sample_uid,))
    assert rows, f"khong tim thay mau {sample_uid}"
    return str(rows[0]["review_status"])


# ---------------------------------------------------------------------------
# Giá trị khởi đầu — chính sách, không đụng CSDL
# ---------------------------------------------------------------------------


class TestTrangThaiKhoiDau:
    """Mẫu mới LUÔN chờ duyệt. Không có ngoại lệ, và không có công tắc."""

    def test_luon_luon_cho_duyet(self):
        from app.dataset_samples import REVIEW_PENDING, initial_review_status

        assert initial_review_status() == REVIEW_PENDING

    def test_khong_nhan_tham_so_nao(self):
        """Ghim CHỮ KÝ, không chỉ giá trị trả về.

        Bản đầu nhận `tenant_id` và miễn kiểm duyệt cho tenant tổ chức. Bỏ tham
        số đi là cách làm cho ngoại lệ ấy không diễn đạt được nữa: muốn thêm lại
        thì phải đổi chữ ký, tức là phải đi qua bài test này.
        """
        import inspect

        from app.dataset_samples import initial_review_status

        assert list(inspect.signature(initial_review_status).parameters) == []

    @pytest.mark.parametrize("cau_hinh", ["", "   ", None, "default", "truong-abc"])
    def test_khong_cau_hinh_nao_tat_duoc_khau_kiem_duyet(self, monkeypatch, cau_hinh):
        """Một cổng chất lượng không được phép tắt vì một biến môi trường.

        `public_tenant_id` từng quyết định mẫu nào cần duyệt, nên một biến bị bỏ
        quên hay gõ nhầm sẽ **tắt lặng lẽ toàn bộ khâu kiểm duyệt**: mọi đóng
        góp tự động thành đã duyệt, không một dòng log, không một mẫu nào lọt
        vào hàng đợi để ai đó nhận ra. Nay nó không còn dự phần vào quyết định
        này nữa, và bài test đi qua cả năm hình dạng của cấu hình để chứng minh.
        """
        from app.config import settings
        from app.dataset_samples import initial_review_status

        monkeypatch.setattr(settings, "public_tenant_id", cau_hinh, raising=False)
        assert initial_review_status() == "pending"


class TestAiDuocDuyet:
    """Cấp bậc người duyệt nằm trong PHẠM VI của vai, không nằm ở ba quyền."""

    @pytest.mark.parametrize("vai", [
        "platform_administrator",   # nền tảng: có tất cả
        "tenant_owner",             # chủ tenant
        "tenant_administrator",     # quản trị tenant: khắp tenant
        "workspace_administrator",  # workspace + project bên trong nó
        "project_administrator",    # chỉ project của mình
        "project_reviewer",         # "editor" ở cấp project
        "community_reviewer",       # chuyên gia của cộng đồng
    ])
    def test_vai_duoc_duyet(self, vai):
        from app.authorization.catalog import BUILTIN_BY_CODE

        assert "sample.moderate" in BUILTIN_BY_CODE[vai].permissions, (
            f"{vai} phai duyet duoc"
        )

    @pytest.mark.parametrize("vai", [
        "project_contributor",   # người đóng góp KHÔNG tự duyệt mẫu của mình
        "project_viewer",
        "workspace_viewer",
        "community_member",      # tài khoản mới: nộp được, không duyệt được
        "community_curator",     # biên tập từ vựng, không phán xét dữ liệu
        "platform_auditor",      # đọc mọi thứ, ghi không gì
    ])
    def test_vai_KHONG_duoc_duyet(self, vai):
        from app.authorization.catalog import BUILTIN_BY_CODE

        assert "sample.moderate" not in BUILTIN_BY_CODE[vai].permissions, (
            f"{vai} khong duoc phep duyet"
        )

    def test_quyen_duoc_danh_dau_nhay_cam(self):
        """Cùng hạng với `dataset.publish`, không cùng hạng với
        `sample.annotate`: đây là cái nút biến dữ liệu riêng thành dữ liệu
        chung."""
        from app.authorization.catalog import BY_CODE

        assert BY_CODE["sample.moderate"].risk == "SENSITIVE"


# ---------------------------------------------------------------------------
# Ngữ nghĩa của upsert
# ---------------------------------------------------------------------------


class TestUpsert:
    def test_nguon_im_lang_thi_mau_moi_CHO_DUYET(self, lop_va_mau):
        """Hỏng-thì-ĐÓNG: một dòng không nói gì thì chưa được coi là đã duyệt."""
        class_uid, mau = lop_va_mau
        uid = mau()

        db.insert_sample({"sample_uid": uid, "class_uid": class_uid})

        assert _trang_thai(uid) == "pending"

    def test_nguon_noi_ro_thi_ton_trong(self, lop_va_mau):
        class_uid, mau = lop_va_mau
        uid = mau()

        db.insert_sample({"sample_uid": uid, "class_uid": class_uid,
                          "review_status": "approved"})

        assert _trang_thai(uid) == "approved"

    def test_dong_bo_im_lang_KHONG_ha_cap_mau_da_duyet(self, lop_va_mau):
        """Cái bẫy chính. Xem docstring đầu tệp.

        Lượt đồng bộ CSV -> Postgres chạy theo chu kỳ và upsert lại MỌI dòng.
        Nếu nó mang theo một ô rỗng — chuyện xảy ra với bất kỳ tệp nào ghi từ
        trước lượt migration — thì mẫu đã duyệt phải giữ nguyên trạng thái.
        """
        class_uid, mau = lop_va_mau
        uid = mau()
        db.insert_sample({"sample_uid": uid, "class_uid": class_uid,
                          "review_status": "approved"})
        assert _trang_thai(uid) == "approved"

        # Đúng hình dạng một dòng đến từ CSV chưa có cột: khoá vắng mặt.
        db.insert_sample({"sample_uid": uid, "class_uid": class_uid})
        assert _trang_thai(uid) == "approved", (
            "Luot dong bo im lang da HA CAP mau da duyet ve 'pending'. Menh de "
            "ON CONFLICT dang doc EXCLUDED thay vi doc THAM SO."
        )

        # Ô rỗng, cùng nghĩa "không có ý kiến", cùng kết quả.
        db.insert_sample({"sample_uid": uid, "class_uid": class_uid,
                          "review_status": ""})
        assert _trang_thai(uid) == "approved"

    def test_quyet_dinh_moi_van_ghi_de_duoc(self, lop_va_mau):
        """Giữ giá trị cũ chỉ áp dụng khi nguồn IM LẶNG. Một nguồn nói rõ vẫn
        phải thắng, nếu không quyết định kiểm duyệt không lan được sang máy
        khác qua SOT."""
        class_uid, mau = lop_va_mau
        uid = mau()
        db.insert_sample({"sample_uid": uid, "class_uid": class_uid,
                          "review_status": "approved"})

        db.insert_sample({"sample_uid": uid, "class_uid": class_uid,
                          "review_status": "rejected"})

        assert _trang_thai(uid) == "rejected"

    def test_gia_tri_la_thi_bi_rang_buoc_chan(self, lop_va_mau):
        """Ba giá trị, không hơn. Không có ràng buộc thì một lỗi gõ phím tạo ra
        một trạng thái thứ tư mà không bộ lọc nào biết phải xử lý thế nào."""
        import psycopg2

        class_uid, mau = lop_va_mau
        uid = mau()

        with pytest.raises(psycopg2.errors.CheckViolation):
            db.insert_sample({"sample_uid": uid, "class_uid": class_uid,
                              "review_status": "duyet_roi_nhe"})


# ---------------------------------------------------------------------------
# Hợp đồng với CSV và SOT
# ---------------------------------------------------------------------------


class TestHopDongTepVaSOT:
    def test_cot_nam_o_CUOI_header(self):
        """Bản nhân bản Google Sheets phát header nguyên văn thành dòng 1, nên
        một cột chèn vào GIỮA sẽ đẩy mọi cột hiện có sang phải một ô — trên một
        bảng tính người ta đang mở."""
        from app.dataset_samples import SAMPLE_FIELDS

        assert SAMPLE_FIELDS[-1] == "review_status"

    def test_SOT_bat_ben_doc_phai_co_cot_nay(self):
        """Thiếu nó thì một ảnh chụp nhập vào lược đồ không có cột, và trạng
        thái duyệt của cả kho biến mất trong im lặng."""
        from app.sot.catalog_schema import REQUIRED_COLUMNS

        assert "review_status" in REQUIRED_COLUMNS["samples"]

    def test_upsert_that_su_ghi_cot_nay(self):
        """`REQUIRED_COLUMNS` chỉ là lời hứa; `_SAMPLE_DB_KEYS` mới là thứ ghi.

        Hai danh sách lệch nhau là đúng lỗi mà `test_sot_schema_coverage.py`
        sinh ra để bắt — ghim lại ở đây để người đọc tệp này thấy cả hai vế.
        """
        from app.storage.metadata_db import _SAMPLE_DB_KEYS

        assert "review_status" in _SAMPLE_DB_KEYS
