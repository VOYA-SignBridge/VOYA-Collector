"""Console quản trị phải ĐỌC ĐƯỢC dưới row-level security.

Vì sao tệp này tồn tại
-----------------------
Ngày 16/08/2026 màn hình "Quản lý người dùng" ghi *"Không có người dùng."* trong
khi `users` có mười tài khoản. Không có lỗi 500, không có dòng nhật ký nào, và
1.677 test vẫn xanh.

Nguyên nhân: `routers/admin.py` mở kết nối bằng `connect_postgres()` rồi truy vấn
thẳng. `users` mang chính sách RLS đọc GUC `app.tenant_id`; một kết nối chưa gọi
`apply_scope()` có GUC rỗng, `tenant_id = ''` khớp 0 dòng, và câu lệnh trả về
**danh sách rỗng chứ không phải lỗi**. Đây là kiểu hỏng fail-OPEN ở mặt phẳng
danh tính đã ghi trong `docs/`: cách hỏng trông y hệt "chưa có dữ liệu".

Vì sao bộ test cũ không bắt được — hai lý do, cả hai đều đáng nhớ:

1. **Không có test nào gọi `GET /admin/users`.** Tham chiếu duy nhất trong cả bộ
   là một lượt OPTIONS ở `test_access_gate.py`, tức chỉ kiểm CORS.
2. Fixture `_platform_scope` cho MỌI test chạy ở *system scope*. Một test viết
   cẩu thả ở phạm vi ấy sẽ xanh với cả câu truy vấn hỏng, vì
   `app.system_scope = 'on'` cho qua mọi dòng.

Nên mỗi test dưới đây **ép về phạm vi TENANT** — đúng thứ mà middleware HTTP đặt
cho một request thật — rồi đòi thấy dòng. Đó là điều kiện mà bản hỏng trượt.
"""

from __future__ import annotations

import uuid

import pytest

from app.routers import admin as admin_router
from app.storage.metadata_db import _execute
from app.tenancy import DEFAULT_TENANT_ID
from app.tenant_context import system_scope, tenant_scope


def _make_account(prefix: str) -> dict:
    from app.auth import create_user

    name = f"{prefix}{uuid.uuid4().hex[:8]}"
    user = create_user(username=name, email=f"{name}@example.test",
                       password="correct horse battery")
    return {"id": str(user["id"]), "username": name}


@pytest.fixture
def account():
    acc = _make_account("rlsadm")
    yield acc
    from conftest import purge_registered_account

    with system_scope("test cleanup: console quan tri"):
        _execute("DELETE FROM notifications WHERE user_id = %s", (acc["id"],))
    purge_registered_account(acc["username"])


@pytest.fixture
def tenant():
    """Phạm vi TENANT, không phải system.

    Đây là toàn bộ giá trị của tệp này. Ở system scope, câu truy vấn hỏng cũng
    trả về đủ dòng và test xanh — che đúng lỗi mà nó sinh ra để bắt.
    """
    with tenant_scope(DEFAULT_TENANT_ID):
        yield


class TestDanhSachNguoiDung:
    def test_thay_duoc_tai_khoan_cua_tenant_minh(self, account, tenant):
        rows = admin_router.get_all_users(current_user={"id": account["id"],
                                                        "is_admin": True})
        assert rows, (
            "Danh sách rỗng dưới phạm vi tenant — dấu hiệu của một kết nối "
            "chưa gọi apply_scope(). Xem chú thích đầu tệp."
        )
        assert account["id"] in {r["id"] for r in rows}

    def test_moi_dong_deu_serialize_duoc(self, account, tenant):
        """UUID và datetime phải đã thành chuỗi trước khi rời router.

        Không phải chuyện thẩm mỹ: đổi sang `_fetch_all` làm kiểu của `id` đổi
        theo, và một `UUID` lọt ra ngoài chỉ hỏng lúc FastAPI serialize — tức ở
        production, không phải ở đây.
        """
        rows = admin_router.get_all_users(current_user={"id": account["id"],
                                                        "is_admin": True})
        row = next(r for r in rows if r["id"] == account["id"])
        assert isinstance(row["id"], str)
        assert row["created_at"] is None or isinstance(row["created_at"], str)
        # Ba cột mà giao diện đọc thẳng; thiếu một cái là một cột trống trên bảng.
        assert set(row) >= {"username", "email", "is_admin", "is_active",
                            "locked", "has_warning"}


class TestDoiQuyen:
    def test_nang_va_ha_quyen_admin_cham_duoc_vao_dong(self, account, tenant):
        """Bản hỏng trả 404 "Không tìm thấy người dùng" cho tài khoản CÓ THẬT.

        Cùng một nguyên nhân với danh sách rỗng, nhưng biểu hiện khác hẳn: câu
        UPDATE khớp 0 dòng, `RETURNING` không trả gì, và router kết luận sai
        rằng người dùng không tồn tại.
        """
        payload = admin_router.UserRoleUpdate(is_admin=True)
        res = admin_router.update_user_role(
            account["id"], payload,
            current_user={"id": str(uuid.uuid4()), "is_admin": True})
        assert res["user"]["is_admin"] is True

        res = admin_router.update_user_role(
            account["id"], admin_router.UserRoleUpdate(is_admin=False),
            current_user={"id": str(uuid.uuid4()), "is_admin": True})
        assert res["user"]["is_admin"] is False


class TestTenPhienDangHoatDong:
    def test_resolve_usernames_tra_ve_ten_chu_khong_phai_rong(self, account, tenant):
        """Bảng "Phiên đang hoạt động" hiện MỌI dòng là "Khách" khi hàm này trả {}.

        `activity._resolve_usernames` cũng mở kết nối trần và cũng đọc `users`.
        Triệu chứng khác nhau, nguyên nhân giống hệt, nên nó phải được neo ở
        cùng một chỗ — nếu không lần sửa sau sẽ chỉ vá một nửa.
        """
        from app import activity

        got = activity._resolve_usernames({account["id"]})
        assert account["id"] in got, (
            "Không tra được tên — kết nối thiếu apply_scope(), và giao diện sẽ "
            "ghi 'Khách' cho mọi phiên."
        )
        assert got[account["id"]]["username"] == account["username"]
