"""Huy hiệu "việc đang chờ" của console quản trị.

Vì sao tệp này tồn tại
-----------------------
`admin_attention._scalar` **nuốt lỗi** và trả về 0. Đó là quyết định đúng cho
lúc chạy — một cột đổi tên không được phép làm trắng cả console vì cái huy hiệu
— nhưng nó biến mọi câu truy vấn sai thành một con số 0 hoàn toàn thuyết phục.

Và truy vấn sai là chuyện đã xảy ra thật, hai lần trong một lượt viết: bảng
`legal_document_drafts` không có cột `published_at` (nó có `status`), còn
`tenant_invitations` thì có thêm `revoked_at` mà bản đầu bỏ qua. Không có tệp
này thì cả hai đã lặng lẽ báo "không có việc gì" mãi mãi.

Nên mỗi test dưới đây làm đúng một việc: **tạo ra một hàng thật, rồi đòi con số
tăng lên**. Không mock, không kiểm chuỗi SQL — chỉ hỏi câu truy vấn có chạy
được trên lược đồ thật hay không.
"""

from __future__ import annotations

import uuid

import pytest

from app import admin_attention, support
from app.storage.metadata_db import _execute
from app.tenancy import DEFAULT_TENANT_ID
from app.tenant_context import system_scope, tenant_scope


def _make_account(prefix: str) -> dict:
    from app.auth import create_user

    name = f"{prefix}{uuid.uuid4().hex[:8]}"
    user = create_user(username=name, email=f"{name}@example.test",
                       password="correct horse battery")
    return {"id": str(user["id"]), "username": name}


def _purge(account: dict) -> None:
    from conftest import purge_registered_account

    with system_scope("test cleanup: attention"):
        _execute("DELETE FROM support_messages WHERE ticket_id IN "
                 "(SELECT ticket_id FROM support_tickets WHERE user_id = %s)",
                 (account["id"],))
        _execute("DELETE FROM support_tickets WHERE user_id = %s", (account["id"],))
    purge_registered_account(account["username"])


@pytest.fixture
def scope():
    with tenant_scope(DEFAULT_TENANT_ID):
        yield


def _dem():
    with system_scope("test: doc huy hieu"):
        return admin_attention.collect(str(DEFAULT_TENANT_ID))


class TestMoiTruyVanChayDuocTrenLuocDoThat:
    """Đây là phần quan trọng nhất của tệp.

    `_scalar` trả 0 khi truy vấn ném, nên "tất cả bằng 0" trông y hệt "mọi thứ
    đều rảnh". Cách duy nhất phân biệt là tạo dữ liệu thật rồi đòi con số nhúc
    nhích.
    """

    def test_phieu_ho_tro_moi_lam_tang_con_so(self, scope):
        acc = _make_account("att")
        try:
            truoc = _dem()["/admin/support"]
            support.create_ticket(
                acc["id"], "Phiếu để đếm huy hiệu",
                "Nội dung đủ dài để qua kiểm tra.", "other", acc["username"])
            assert _dem()["/admin/support"] == truoc + 1
        finally:
            _purge(acc)

    def test_de_xuat_phuong_ngu_dang_cho_lam_tang_con_so(self, scope):
        slug = f"tst-{uuid.uuid4().hex[:8]}"
        try:
            truoc = _dem()["/admin/vocabulary"]
            with system_scope("test: them de xuat phuong ngu"):
                _execute(
                    "INSERT INTO dialects (dialect_id, tenant_id, display_name, status) "
                    "VALUES (%s, %s, %s, 'pending')",
                    (slug, str(DEFAULT_TENANT_ID), "Phương ngữ thử"))
            assert _dem()["/admin/vocabulary"] == truoc + 1
        finally:
            with system_scope("test cleanup: de xuat phuong ngu"):
                _execute("DELETE FROM dialects WHERE dialect_id = %s", (slug,))

    def test_loi_moi_da_thu_hoi_KHONG_tinh_la_viec_dang_cho(self, scope):
        """`revoked_at` là chỗ bản đầu bỏ sót.

        Một lời mời đã thu hồi không còn là việc của ai. Đếm nó vào nghĩa là
        huy hiệu không bao giờ về 0 được — và một huy hiệu không bao giờ tắt
        thì thôi mang nghĩa gì.
        """
        inv = str(uuid.uuid4())
        try:
            truoc = _dem()["/admin/tenants"]
            with system_scope("test: them loi moi"):
                _execute(
                    "INSERT INTO tenant_invitations "
                    "(invitation_id, tenant_id, email, role, token_hash, expires_at) "
                    # 'viewer' da nghi — xem catalog.RETIRED_BUILTIN_ROLES.
                    "VALUES (%s, %s, %s, 'editor', %s, NOW() + INTERVAL '7 days')",
                    (inv, str(DEFAULT_TENANT_ID), f"m{uuid.uuid4().hex[:8]}@example.test",
                     uuid.uuid4().hex))
            assert _dem()["/admin/tenants"] == truoc + 1

            with system_scope("test: thu hoi loi moi"):
                _execute("UPDATE tenant_invitations SET revoked_at = NOW() "
                         "WHERE invitation_id = %s", (inv,))
            assert _dem()["/admin/tenants"] == truoc
        finally:
            with system_scope("test cleanup: loi moi"):
                _execute("DELETE FROM tenant_invitations WHERE invitation_id = %s", (inv,))

    def test_khoa_tra_ve_khop_voi_href_cua_thanh_ben(self, scope):
        """Khoá PHẢI là `href`, không phải một tên riêng thứ hai.

        Hai bảng tên song song là chỗ chắc chắn lệch nhau khi thêm mục mới, và
        lệch theo kiểu im lặng: huy hiệu chỉ đơn giản không hiện ra.
        """
        counts = _dem()
        for key in counts:
            assert key.startswith("/admin/"), f"{key!r} không phải một href"

    def test_moi_con_so_deu_la_so_nguyen_khong_am(self, scope):
        for key, n in _dem().items():
            assert isinstance(n, int), f"{key}: {n!r} không phải số nguyên"
            assert n >= 0
