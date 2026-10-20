"""Ngữ nghĩa TẦNG ỨNG DỤNG của việc phân loại vùng.

`test_tenant_isolation.py` đã chứng minh tầng CSDL: policy chặn mọi lượt đọc và
ghi xuyên tenant, kể cả khi truy vấn quên lọc. Tệp này chứng minh thứ khác hẳn
— rằng hàm phía trên policy trả lời ĐÚNG, và trả lời theo cách không rò rỉ.

Điểm quan trọng nhất ở đây không phải "cross-tenant bị chặn" (điều đó đã chứng
minh ở tầng dưới) mà là HÌNH DẠNG CÂU TRẢ LỜI: hỏi một `class_uid` của tenant
khác phải nhận đúng thứ mà hỏi một `class_uid` bịa ra nhận được. Một câu trả
lời phân biệt được "không tồn tại" với "tồn tại nhưng của người khác" đã tiết
lộ chính thứ cần giấu.
"""

from __future__ import annotations

import uuid

import pytest

from app.storage import metadata_db as db
from app.tenant_context import system_scope
from app.vocabulary_registry import RegionReclassifyError, reclassify_class_region

TENANT_A = "default"
TENANT_B = "recl-b"


def _dialect() -> str:
    """Một dialect có thật của tenant A. Không viết cứng: bản sao mỗi máy khác nhau."""
    with system_scope("test: pick a dialect"):
        rows = db._fetch_all(
            "SELECT dialect_id FROM dialects WHERE tenant_id = %s ORDER BY dialect_id LIMIT 1",
            (TENANT_A,),
        )
    if not rows:
        pytest.skip("tenant mặc định không có dialect nào")
    return rows[0]["dialect_id"]


def _make_class(tenant: str, slug: str, region: str, dialect=None) -> str:
    """`dialect` để None cho tenant phụ, và đó không phải lười.

    `classes_dialect_fkey` là khoá ngoại GHÉP `(tenant_id, dialect)`, kiểu MATCH
    SIMPLE — một thành phần NULL làm nó không được cưỡng chế. Nhờ vậy tenant thứ
    hai không phải nhân bản cả một danh mục từ vựng chỉ để chứng minh một tính
    chất về khả năng nhìn thấy. Cùng thủ thuật `test_tenant_isolation._seed`
    đang dùng, và vì cùng lý do.
    """
    uid = f"RECL_{uuid.uuid4().hex[:10]}"
    with system_scope("test: dựng lớp thử"):
        db._execute(
            "INSERT INTO classes(tenant_id, class_uid, slug, label_original, "
            "language, dialect, region) VALUES(%s, %s, %s, %s, 'vn', %s, %s)",
            (tenant, uid, slug, slug.replace("-", " "), dialect, region),
        )
    return uid


@pytest.fixture
def dialect():
    return _dialect()


@pytest.fixture(autouse=True)
def _don_dep():
    yield
    with system_scope("test cleanup"):
        db._execute("DELETE FROM classes WHERE class_uid LIKE 'RECL_%%'")
        db._execute("DELETE FROM tenants WHERE tenant_id = %s", (TENANT_B,))


class TestDuongThanhCong:
    def test_doi_duoc_va_giu_nguyen_class_uid(self, dialect):
        """`class_uid` KHÔNG đổi là cả điểm của thiết kế: mẫu, tệp npz, video và
        lịch sử đều treo vào nó, nên giữ nó là không phải dời gì cả."""
        uid = _make_class(TENANT_A, f"an-{uuid.uuid4().hex[:6]}", "unclassified", dialect)

        ket_qua = reclassify_class_region(uid, "bac", tenant_id=TENANT_A)

        assert ket_qua["changed"] is True
        assert ket_qua["from"] == "unclassified"
        assert ket_qua["to"] == "bac"
        assert ket_qua["class_uid"] == uid
        with system_scope("test: đọc lại"):
            rows = db._fetch_all(
                "SELECT region FROM classes WHERE class_uid = %s", (uid,))
        assert rows[0]["region"] == "bac"

    def test_unclassified_sang_common_cung_di_duoc(self, dialect):
        """Bốn đích đều hợp lệ từ `unclassified`, không chỉ ba vùng địa lý."""
        uid = _make_class(TENANT_A, f"cam-on-{uuid.uuid4().hex[:6]}",
                          "unclassified", dialect)
        assert reclassify_class_region(uid, "common", tenant_id=TENANT_A)["to"] == "common"

    def test_doi_sang_chinh_no_la_khong_lam_gi(self, dialect):
        """Idempotent, và KHÔNG ghi một dòng kiểm toán giả cho việc không xảy ra."""
        uid = _make_class(TENANT_A, f"x-{uuid.uuid4().hex[:6]}", "nam", dialect)
        ket_qua = reclassify_class_region(uid, "nam", tenant_id=TENANT_A)
        assert ket_qua["changed"] is False


class TestCauTraLoiKhongRoRi:
    """Hai câu hỏi khác nhau phải nhận cùng một câu trả lời."""

    def test_uid_bia_ra_thi_404(self):
        with pytest.raises(RegionReclassifyError) as loi:
            reclassify_class_region("RECL_khong_ton_tai", "bac", tenant_id=TENANT_A)
        assert loi.value.status_code == 404

    def test_uid_cua_tenant_khac_cung_404_va_cung_thong_diep(self, dialect):
        """Đây là ca đáng giá nhất tệp này.

        Nếu tenant khác nhận được 403 "lớp này thuộc tenant khác" thì họ vừa
        học được rằng lớp đó CÓ TỒN TẠI. Số hiệu lỗi phải giống, và hình dạng
        thông điệp cũng phải giống — chỉ khác đúng cái mã họ tự gõ vào.
        """
        with system_scope("test: dựng tenant thứ hai"):
            db._execute(
                "INSERT INTO tenants(tenant_id, display_name, slug) VALUES(%s, %s, %s) "
                "ON CONFLICT (tenant_id) DO NOTHING",
                (TENANT_B, "Recl B", TENANT_B),
            )
        cua_b = _make_class(TENANT_B, f"cua-b-{uuid.uuid4().hex[:6]}", "unclassified")

        with pytest.raises(RegionReclassifyError) as thuc:
            reclassify_class_region(cua_b, "bac", tenant_id=TENANT_A)
        with pytest.raises(RegionReclassifyError) as bia:
            reclassify_class_region("RECL_khong_ton_tai", "bac", tenant_id=TENANT_A)

        assert thuc.value.status_code == bia.value.status_code == 404
        # Cùng khuôn thông điệp: bỏ đúng phần mã người gọi tự đưa vào thì hai
        # câu phải trùng khít.
        assert str(thuc.value).replace(cua_b, "X") == \
               str(bia.value).replace("RECL_khong_ton_tai", "X")

        with system_scope("test: lớp của B không hề bị đụng"):
            rows = db._fetch_all(
                "SELECT region FROM classes WHERE class_uid = %s", (cua_b,))
        assert rows[0]["region"] == "unclassified"

    def test_lop_da_xoa_mem_cung_404(self, dialect):
        """Xoá mềm nghĩa là không còn tồn tại với người dùng — kể cả ở đây."""
        uid = _make_class(TENANT_A, f"da-xoa-{uuid.uuid4().hex[:6]}",
                          "unclassified", dialect)
        with system_scope("test: xoá mềm"):
            db._execute(
                "UPDATE classes SET deleted_at = NOW() WHERE class_uid = %s", (uid,))
        with pytest.raises(RegionReclassifyError) as loi:
            reclassify_class_region(uid, "bac", tenant_id=TENANT_A)
        assert loi.value.status_code == 404


class TestVungDich:
    def test_vung_khong_co_trong_danh_muc_bi_tu_choi(self, dialect):
        uid = _make_class(TENANT_A, f"y-{uuid.uuid4().hex[:6]}", "unclassified", dialect)
        with pytest.raises(RegionReclassifyError) as loi:
            reclassify_class_region(uid, "tay-nguyen", tenant_id=TENANT_A)
        assert "danh mục" in str(loi.value)

    def test_vung_da_nghi_huu_bi_tu_choi(self, dialect):
        """Khoá ngoại chặn mã KHÔNG TỒN TẠI, nhưng nó không phân biệt được
        "chưa có" với "đã tắt". Chuyển vào một vùng đã nghỉ hưu tạo ra dữ liệu
        không hiện lên ở đâu cả."""
        uid = _make_class(TENANT_A, f"z-{uuid.uuid4().hex[:6]}", "unclassified", dialect)

        # Phải dùng vai MIGRATION để tắt vùng, không dùng vai ứng dụng — và ca
        # này đã tự chứng minh điều đó: bản đầu viết bằng `db._execute` và đỏ
        # với `permission denied for table regions`. Đó chính là bảo vệ mới
        # đang hoạt động: sửa danh mục toàn cục KHÔNG phải việc của ứng dụng.
        def _dat(bat: bool) -> None:
            from app.storage.metadata_db import _migration_cursor

            with _migration_cursor() as cur:
                cur.execute(
                    "UPDATE regions SET is_active = %s WHERE code = 'trung'", (bat,))

        _dat(False)
        try:
            with pytest.raises(RegionReclassifyError) as loi:
                reclassify_class_region(uid, "trung", tenant_id=TENANT_A)
            assert "nghỉ hưu" in str(loi.value)
        finally:
            _dat(True)


class TestVaCham:
    def test_dich_da_co_lop_thi_bao_GOP_chu_khong_doi(self, dialect):
        """Khoá duy nhất sẽ ném, nhưng thông báo của Postgres không nói được
        cho người vận hành rằng việc cần làm là GỘP. Bắt trước để trả lời đúng
        câu hỏi đó, và trả 409 chứ không phải 400."""
        slug = f"trung-ten-{uuid.uuid4().hex[:6]}"
        _make_class(TENANT_A, slug, "bac", dialect)
        chua_phan = _make_class(TENANT_A, slug, "unclassified", dialect)

        with pytest.raises(RegionReclassifyError) as loi:
            reclassify_class_region(chua_phan, "bac", tenant_id=TENANT_A)

        assert loi.value.status_code == 409
        assert "GỘP" in str(loi.value)

        with system_scope("test: không đổi gì cả"):
            rows = db._fetch_all(
                "SELECT region FROM classes WHERE class_uid = %s", (chua_phan,))
        assert rows[0]["region"] == "unclassified"
