"""Cổng kiểm duyệt: ai thấy được mẫu chưa duyệt, và ai thì không.

Không đụng cơ sở dữ liệu — trạng thái nằm sẵn trên từng dòng, ở cả CSV lẫn
Postgres. Đó là chủ ý của thiết kế: tiến trình huấn luyện đọc thẳng từ tệp và
phải lọc được mà không cần kết nối.

Bài đáng giá nhất ở đây là `test_o_rong_doc_thanh_CHO_DUYET`. Một dòng đến từ
tệp ghi trước lượt migration không nói gì về việc nó đã được duyệt hay chưa.
Đọc sự im lặng ấy thành "đã duyệt" biến việc chép một tệp cũ vào thành một lần
phát hành hàng loạt — đúng cái cửa cổng này sinh ra để đóng.
"""

from __future__ import annotations

import pytest

from app.moderation import (
    APPROVED, PENDING, REASON_PENDING, REASON_REJECTED, REJECTED,
    filter_rows, status_of,
)

ME = "11111111-1111-1111-1111-111111111111"
NGUOI_KHAC = "22222222-2222-2222-2222-222222222222"


def _mau(status=None, chu=None, **kw):
    row = dict(kw)
    if status is not None:
        row["review_status"] = status
    if chu is not None:
        row["auth_user_id"] = chu
    return row


class TestDocTrangThai:
    @pytest.mark.parametrize("gia_tri", [None, "", "   "])
    def test_o_rong_doc_thanh_CHO_DUYET(self, gia_tri):
        """Im lặng nghĩa là "chưa biết", và chưa biết thì chưa được dùng chung."""
        assert status_of(_mau(status=gia_tri)) == PENDING

    def test_khoa_vang_mat_cung_the(self):
        assert status_of({}) == PENDING

    @pytest.mark.parametrize("gia_tri,mong", [
        ("approved", APPROVED), ("APPROVED", APPROVED), (" Approved ", APPROVED),
        ("rejected", REJECTED), ("pending", PENDING),
    ])
    def test_chuan_hoa_hoa_thuong_va_khoang_trang(self, gia_tri, mong):
        assert status_of(_mau(status=gia_tri)) == mong


class TestKhongCoNguoiXem:
    """Phát hành, công bố, thống kê công khai: chỉ `approved` đi tiếp."""

    def test_chi_approved_di_tiep(self):
        rows = [_mau(APPROVED, ME), _mau(PENDING, ME), _mau(REJECTED, ME)]

        kq = filter_rows(rows, viewer_id=None)

        assert len(kq.kept) == 1
        assert kq.kept[0]["review_status"] == APPROVED
        assert kq.reasons == {REASON_PENDING: 1, REASON_REJECTED: 1}

    def test_mau_vo_chu_KHONG_lot_qua(self):
        """997 mẫu cũ không có `auth_user_id`. Nếu phép so sánh chủ sở hữu coi
        "không có người xem" và "không có chủ" là khớp nhau, cả nhóm ấy sẽ đi
        thẳng vào bản phát hành."""
        kq = filter_rows([_mau(PENDING, None)], viewer_id=None)

        assert kq.kept == []


class TestCoNguoiXem:
    def test_chu_so_huu_dung_duoc_mau_chua_duyet_cua_minh(self):
        """Nửa còn lại của hợp đồng: thu xong là dùng được ngay, chỉ chưa được
        dùng CHUNG."""
        kq = filter_rows([_mau(PENDING, ME)], viewer_id=ME)

        assert len(kq.kept) == 1

    def test_khong_thay_mau_chua_duyet_cua_NGUOI_KHAC(self):
        kq = filter_rows([_mau(PENDING, NGUOI_KHAC)], viewer_id=ME)

        assert kq.kept == []
        assert kq.reasons == {REASON_PENDING: 1}

    def test_mau_da_duyet_cua_nguoi_khac_thi_van_thay(self):
        kq = filter_rows([_mau(APPROVED, NGUOI_KHAC)], viewer_id=ME)

        assert len(kq.kept) == 1

    def test_mau_BI_TU_CHOI_cua_chinh_minh_van_dung_duoc(self):
        """Từ chối không xoá dữ liệu và không tước nó khỏi người đóng góp —
        xem §7.2. Nó chỉ chặn việc dùng chung."""
        kq = filter_rows([_mau(REJECTED, ME)], viewer_id=ME)

        assert len(kq.kept) == 1

    def test_chu_so_huu_vo_danh_khong_khop_voi_ai(self):
        """`auth_user_id` rỗng không được khớp với một `viewer_id` rỗng."""
        kq = filter_rows([_mau(PENDING, "")], viewer_id="")

        assert kq.kept == []

    @pytest.mark.parametrize("kieu", [str, lambda s: f"  {s}  "])
    def test_so_sanh_chiu_duoc_ba_nguon_kieu_khac_nhau(self, kieu):
        """`auth_user_id` tới từ ô CSV, từ UUID của psycopg2, và từ chuỗi JSON."""
        kq = filter_rows([_mau(PENDING, kieu(ME))], viewer_id=ME)

        assert len(kq.kept) == 1


class TestTongKet:
    def test_summary_dem_dung_va_doc_duoc(self):
        rows = [_mau(APPROVED, ME), _mau(PENDING, NGUOI_KHAC),
                _mau(PENDING, NGUOI_KHAC), _mau(REJECTED, NGUOI_KHAC)]

        kq = filter_rows(rows, viewer_id=ME)

        assert kq.total == 4
        assert len(kq.kept) == 1
        assert "1/4" in kq.summary()
        assert "chờ duyệt" in kq.summary()

    def test_khong_giu_lai_gi_thi_summary_khong_ke_ly_do(self):
        kq = filter_rows([_mau(APPROVED, ME)], viewer_id=None)

        assert "giữ lại" not in kq.summary()


class TestDocLapVoiCongDongThuan:
    def test_hai_cong_tra_loi_HAI_cau_hoi_khac_nhau(self):
        """Ghim rằng cổng này KHÔNG đọc `signer_id` hay đồng thuận.

        Một mẫu đã duyệt vẫn phải chịu cổng đồng thuận, và ngược lại. Nếu ai đó
        gộp hai phép kiểm vào đây, bài này đỏ — và nó đỏ trước khi một bản phát
        hành đi ra ngoài với dữ liệu chưa được người ký cho phép.
        """
        import inspect

        from app import moderation

        src = inspect.getsource(moderation)
        assert "signer_id" not in src
        assert "consent" not in src.lower().replace("consent_gate", "")
