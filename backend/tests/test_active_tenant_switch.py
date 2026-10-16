"""Một người, nhiều tổ chức: chọn tổ chức nào mà không phá ranh giới cách ly.

Hợp đồng đang được ghim
------------------------
`tenant_middleware` cố ý không nhận tenant từ bất kỳ trường nào của request.
Phép chọn tổ chức vì thế phải là trạng thái do MÁY CHỦ giữ
(`users.active_tenant_id`), ghi qua đúng một cửa (`POST /tenants/switch`) sau khi
đã kiểm tư cách thành viên.

Bài đáng giá nhất ở đây là `test_go_tu_cach_thanh_vien_thi_roi_ve_nha`: kiểm
một lần lúc chuyển là KHÔNG đủ, vì tư cách thành viên có thể bị gỡ trong khi con
trỏ vẫn trỏ vào đó. Không có phép kiểm lại trong `_tenant_of_user`, mọi request
sau đó vẫn tiếp tục lấy phạm vi của một tổ chức mà người ta đã bị đưa ra khỏi.
"""

from __future__ import annotations

import uuid

import pytest

from app import tenant_admin
from app.storage import metadata_db as db
from app.tenant_context import system_scope
from app.tenant_middleware import _tenant_of_user


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture
def hai_to_chuc():
    from conftest import purge_tenant

    a = f"test-{uuid.uuid4().hex[:10]}"
    b = f"test-{uuid.uuid4().hex[:10]}"
    tenant_admin.create_tenant(a, display_name="To chuc A")
    tenant_admin.create_tenant(b, display_name="To chuc B")
    yield a, b
    purge_tenant(a)
    purge_tenant(b)


@pytest.fixture
def tai_khoan():
    """Tài khoản dùng một lần; trả về hàm đúc và tự dọn."""
    tao: list[str] = []

    def _make(home: str) -> str:
        from app.auth import create_user

        name = f"sw{uuid.uuid4().hex[:10]}"
        user = create_user(username=name, email=f"{name}@example.test",
                           password="correct horse battery")
        uid = str(user["id"])
        tao.append(uid)
        with system_scope("test: dat to chuc nha"):
            db._execute("UPDATE users SET tenant_id = %s WHERE id = %s", (home, uid))
            db._execute(
                "INSERT INTO tenant_members (tenant_id, user_id, role, status) "
                "VALUES (%s, %s, NULL, 'ACTIVE') ON CONFLICT DO NOTHING",
                (home, uid))
        return uid

    yield _make

    with system_scope("test cleanup"):
        for uid in tao:
            db._execute("DELETE FROM tenant_members WHERE user_id = %s", (uid,))
            db._execute("DELETE FROM users WHERE id = %s", (uid,))


def _them_thanh_vien(uid: str, tenant: str) -> None:
    with system_scope("test: them thanh vien"):
        db._execute(
            "INSERT INTO tenant_members (tenant_id, user_id, role, status) "
            "VALUES (%s, %s, NULL, 'ACTIVE') ON CONFLICT DO NOTHING",
            (tenant, uid))


class TestChuyenToChuc:
    def test_chuyen_sang_to_chuc_minh_thuoc_ve(self, hai_to_chuc, tai_khoan):
        a, b = hai_to_chuc
        uid = tai_khoan(home=a)
        _them_thanh_vien(uid, b)

        ket_qua = tenant_admin.set_active_tenant(uid, b)

        assert ket_qua == {"tenant_id": b, "is_home": False}
        assert _tenant_of_user(uid) == b

    def test_khong_thuoc_thi_bi_tu_choi(self, hai_to_chuc, tai_khoan):
        """Và phạm vi KHÔNG đổi — phép từ chối phải là không-thao-tác."""
        a, b = hai_to_chuc
        uid = tai_khoan(home=a)

        with pytest.raises(tenant_admin.NotAMember):
            tenant_admin.set_active_tenant(uid, b)

        assert _tenant_of_user(uid) == a

    def test_ve_nha_thi_XOA_con_tro_chu_khong_tro_vao_nha(self, hai_to_chuc, tai_khoan):
        """Hai cách biểu diễn cùng một trạng thái là hai cách để chúng lệch nhau.

        NULL nghĩa "theo nhà", và nó tự đúng kể cả khi tổ chức nhà đổi sau này.
        """
        a, b = hai_to_chuc
        uid = tai_khoan(home=a)
        _them_thanh_vien(uid, b)
        tenant_admin.set_active_tenant(uid, b)

        ket_qua = tenant_admin.set_active_tenant(uid, a)

        assert ket_qua == {"tenant_id": a, "is_home": True}
        with system_scope("test: doc con tro"):
            rows = db._fetch_all(
                "SELECT active_tenant_id FROM users WHERE id = %s", (uid,))
        assert rows[0]["active_tenant_id"] is None
        assert _tenant_of_user(uid) == a

    def test_KHONG_doi_to_chuc_nha(self, hai_to_chuc, tai_khoan):
        """Xem tổ chức khác không được âm thầm chuyển nơi dữ liệu mới ghi vào."""
        a, b = hai_to_chuc
        uid = tai_khoan(home=a)
        _them_thanh_vien(uid, b)

        tenant_admin.set_active_tenant(uid, b)

        with system_scope("test: doc to chuc nha"):
            rows = db._fetch_all("SELECT tenant_id FROM users WHERE id = %s", (uid,))
        assert rows[0]["tenant_id"] == a, "to chuc NHA khong duoc doi"

    def test_go_tu_cach_thanh_vien_thi_roi_ve_nha(self, hai_to_chuc, tai_khoan):
        """Kiểm một lần lúc chuyển là KHÔNG đủ.

        Tư cách thành viên bị gỡ trong khi con trỏ vẫn trỏ vào tổ chức đó. Không
        có phép kiểm lại trong `_tenant_of_user`, mọi request sau vẫn lấy phạm
        vi của một tổ chức mà người ta đã bị đưa ra khỏi.
        """
        a, b = hai_to_chuc
        uid = tai_khoan(home=a)
        _them_thanh_vien(uid, b)
        tenant_admin.set_active_tenant(uid, b)
        assert _tenant_of_user(uid) == b

        with system_scope("test: go thanh vien"):
            db._execute(
                "UPDATE tenant_members SET status = 'REMOVED', removed_at = NOW() "
                " WHERE user_id = %s AND tenant_id = %s", (uid, b))

        assert _tenant_of_user(uid) == a, (
            "con tro con tro vao to chuc da bi go — pham vi van la cua no"
        )

    def test_to_chuc_bi_xoa_thi_con_tro_tro_nen_vo_hieu(self, hai_to_chuc, tai_khoan):
        """Cột không có khoá ngoại, cố ý: xoá tổ chức phải làm con trỏ VÔ HIỆU,
        không được chặn lượt xoá."""
        a, b = hai_to_chuc
        uid = tai_khoan(home=a)
        _them_thanh_vien(uid, b)
        tenant_admin.set_active_tenant(uid, b)

        with system_scope("test: xoa mem to chuc"):
            db._execute(
                "UPDATE tenants SET deleted_at = NOW(), is_active = FALSE "
                " WHERE tenant_id = %s", (b,))

        assert _tenant_of_user(uid) == a


class TestCongTruyCap:
    def test_duong_chuyen_nam_trong_danh_sach_tu_phuc_vu(self):
        """Không miễn ở cổng thì đây là cái bẫy ngược: người chưa có vai không
        chuyển sang nổi tổ chức nơi họ CÓ vai."""
        from app.access_gate import _is_self_service_write

        assert _is_self_service_write("/tenants/switch") is True

    def test_mien_nay_KHONG_lan_sang_duong_quan_tri_tenant(self):
        """Miễn theo ĐƯỜNG NGUYÊN VĂN, không theo tiền tố. Một tiền tố
        `/tenants/` sẽ mở mọi thao tác quản trị tổ chức cho người không vai."""
        from app.access_gate import _is_self_service_write

        assert _is_self_service_write("/tenants/abc/members") is False
        assert _is_self_service_write("/tenants/switch/extra") is False
