"""Cổng ghi phải nhận vai v5, không chỉ nhận bản sao ở sổ cũ.

Vì sao tệp này tồn tại
----------------------
`_has_any_tenant_grant` hỏi đúng HAI câu:

    1. `role_assignments` với `membership_id IS NULL`   -> grant phạm vi SYSTEM
    2. `tenant_members.role IS NOT NULL`                -> vai ở SỔ CŨ

Danh mục v5 có 17 vai trên 4 mức phạm vi. Câu 1 phủ 5 vai SYSTEM. Câu 2 KHÔNG
đọc `role_assignments` chút nào — nó đọc `tenant_members`, một VIEW trên
`memberships` phơi ra `legacy_role AS role`, và cột ấy bị ràng buộc
`admin | editor | NULL`.

Nghĩa là 12 vai còn lại (6 TENANT, 2 WORKSPACE, 4 PROJECT) **tự nó không đưa
được ai qua cổng ghi**. Hôm nay chưa ai thấy, vì mười tài khoản đang dùng hệ
thống đều nắm vai tenant CÓ bản sao ở sổ cũ (`tenant_administrator` -> `admin`,
`tenant_editor` -> `editor`). Cổng đọc bản sao, không đọc vai thật.

Chỗ nó vỡ ra
------------
`community_member` và `community_reviewer` KHÔNG có bản sao nào ở sổ cũ —
`legacy_role` không nhận được giá trị nào khác ngoài `admin`/`editor`/NULL. Nên
một thành viên cộng đồng nắm `sample.create` + `upload.create` sẽ bị 403 ở mọi
lượt ghi. Điều đó cũng đúng với `project_contributor`, vai mà chính mô tả của
nó nói là để "đóng góp và gán nhãn dữ liệu trong project".

Các test dưới đây ghim hành vi ĐÚNG. Chúng đỏ trước khi cổng được nới, và phải
xanh sau đó — nhưng `test_khong_co_grant_nao_thi_van_bi_tu_choi` phải xanh ở CẢ
HAI phía: nới cổng mà làm mất trạng thái "không grant nào cả" là biến một hàng
rào thành một lỗ.
"""

from __future__ import annotations

import uuid

import pytest

from app import tenant_admin
from app.storage import metadata_db as db
from app.access_gate import _has_any_tenant_grant
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


def _role_id(role_code: str) -> str:
    with system_scope("test: tra role_id"):
        rows = db._fetch_all(
            "SELECT role_id FROM roles WHERE role_code = %s AND is_active", (role_code,))
    assert rows, f"vai {role_code} chua duoc seed — kiem tra authz_schema"
    return str(rows[0]["role_id"])


@pytest.fixture
def tenant():
    from conftest import purge_tenant

    tid = f"test-{uuid.uuid4().hex[:10]}"
    tenant_admin.create_tenant(tid, display_name="Truong Thu Nghiem")
    yield tid
    purge_tenant(tid)


@pytest.fixture
def account():
    """Tài khoản dùng một lần, dọn cả membership và assignment của nó."""
    created: list[str] = []

    def _make() -> dict:
        from app.auth import create_user

        name = f"g{uuid.uuid4().hex[:10]}"
        user = create_user(
            username=name, email=f"{name}@example.test",
            password="correct horse battery",
        )
        created.append(str(user["id"]))
        return user

    yield _make

    with system_scope("test cleanup"):
        for uid in created:
            db._execute("DELETE FROM role_assignments WHERE user_id = %s", (uid,))
            db._execute("DELETE FROM memberships WHERE user_id = %s", (uid,))
            db._execute("DELETE FROM users WHERE id = %s", (uid,))


def _cap_vai_v5(user_id: str, tenant_id: str, role_code: str) -> str:
    """Cấp một vai v5 ở phạm vi TENANT, KHÔNG kèm bản sao ở sổ cũ.

    `legacy_role` để NULL là điểm mấu chốt của cả tệp này: nó dựng lại đúng
    hình dạng mà `community_member` bắt buộc phải có, vì ràng buộc
    `ck_memberships_legacy_role` không nhận giá trị nào ngoài admin/editor.
    """
    with system_scope("test: cap vai v5"):
        rows = db._fetch_all(
            "INSERT INTO memberships (user_id, scope_level, tenant_id, legacy_role, "
            "                         status, joined_at) "
            "VALUES (%s, 'TENANT', %s, NULL, 'ACTIVE', NOW()) "
            "RETURNING membership_id",
            (user_id, tenant_id),
        )
        membership_id = str(rows[0]["membership_id"])
        db._execute(
            "INSERT INTO role_assignments (user_id, role_id, membership_id, "
            "                              assigned_by_user_id) "
            "VALUES (%s, %s, %s, %s)",
            (user_id, _role_id(role_code), membership_id, user_id),
        )
    return membership_id


class TestVaiV5PhamViTenant:
    """Vai v5 ở phạm vi TENANT phải đưa được người ta qua cổng ghi."""

    def test_vai_tenant_khong_co_ban_sao_so_cu_van_qua_duoc(self, tenant, account):
        """Đây là ca của `community_member` và `community_reviewer`.

        Chỉ có một grant v5 (`membership_id` KHÔNG NULL, `legacy_role` NULL).
        Cổng phải thấy nó. Trước khi sửa, nó không thấy và trả `False`.
        """
        user = account()
        _cap_vai_v5(str(user["id"]), tenant, "tenant_editor")

        assert _has_any_tenant_grant({"id": str(user["id"])}) is True, (
            "Cong khong nhan vai v5 pham vi TENANT. Mot thanh vien cong dong "
            "giu sample.create se bi 403 o moi luot ghi."
        )

    def test_vai_bi_thu_hoi_thi_khong_qua(self, tenant, account):
        """Nới cổng không được làm mất hiệu lực của việc thu hồi."""
        user = account()
        _cap_vai_v5(str(user["id"]), tenant, "tenant_editor")
        with system_scope("test: thu hoi"):
            db._execute(
                "UPDATE role_assignments SET revoked_at = NOW(), "
                "       revoked_by_user_id = %s WHERE user_id = %s",
                (str(user["id"]), str(user["id"])),
            )

        assert _has_any_tenant_grant({"id": str(user["id"])}) is False

    def test_membership_da_roi_thi_khong_qua(self, tenant, account):
        """Vai gắn với một tư cách thành viên đã chấm dứt không còn là grant.

        Câu hỏi cũ (`tenant_members`) lọc `status='ACTIVE' AND removed_at IS
        NULL`. Câu mới phải lọc tương đương, nếu không nới cổng sẽ hồi sinh
        quyền ghi của người đã rời tổ chức.

        `REMOVED` chứ không phải `LEFT`: `MEMBER_STATUSES` chỉ nhận ACTIVE /
        INVITED / SUSPENDED / REMOVED, và `ck_memberships_left_consistent` đòi
        `left_at` được điền ĐÚNG KHI status là REMOVED — hai vế phải kể cùng
        một câu chuyện.
        """
        user = account()
        _cap_vai_v5(str(user["id"]), tenant, "tenant_editor")
        with system_scope("test: roi to chuc"):
            db._execute(
                "UPDATE memberships SET status = 'REMOVED', left_at = NOW() "
                " WHERE user_id = %s",
                (str(user["id"]),),
            )

        assert _has_any_tenant_grant({"id": str(user["id"])}) is False


class TestKhongDuocNoiQuaTay:
    """Nới cổng phải giữ nguyên trạng thái mà nó sinh ra để chặn."""

    def test_khong_co_grant_nao_thi_van_bi_tu_choi(self, account):
        """Tài khoản mới tinh, không membership, không assignment.

        Test này phải XANH ở cả trước lẫn sau khi sửa. Đỏ ở đây nghĩa là bản
        vá đã biến hàng rào thành một lỗ.
        """
        user = account()

        assert _has_any_tenant_grant({"id": str(user["id"])}) is False

    def test_thanh_vien_khong_vai_van_bi_tu_choi(self, tenant, account):
        """Có tư cách thành viên, KHÔNG có vai nào — đúng trạng thái mà cổng
        được sinh ra để chặn (lời mời không kèm vai)."""
        user = account()
        with system_scope("test: thanh vien khong vai"):
            db._execute(
                "INSERT INTO memberships (user_id, scope_level, tenant_id, "
                "                         legacy_role, status, joined_at) "
                "VALUES (%s, 'TENANT', %s, NULL, 'ACTIVE', NOW())",
                (str(user["id"]), tenant),
            )

        assert _has_any_tenant_grant({"id": str(user["id"])}) is False

    def test_khong_co_id_thi_tu_choi(self):
        """Hỏng-thì-đóng: không tra được thì không cho qua."""
        assert _has_any_tenant_grant({}) is False


class TestSoSachDanhMuc:
    """Đo trực tiếp trên danh mục: bao nhiêu vai KHÔNG qua nổi câu hỏi cũ.

    Không dựng dữ liệu, chỉ đọc danh mục — nên nó đỏ ngay cả trên máy chưa có
    tài khoản nào, và nó nói được VÌ SAO chứ không chỉ nói "sai".
    """

    def test_vai_ngoai_pham_vi_SYSTEM_deu_can_cong_moi(self):
        from app.authorization.catalog import BUILTIN_ROLES

        khong_system = [r.code for r in BUILTIN_ROLES if r.scope != "SYSTEM"]
        # Chỉ hai vai TENANT có bản sao ở sổ cũ (`legacy_role` chỉ nhận
        # admin/editor); số còn lại phụ thuộc HOÀN TOÀN vào việc cổng đọc được
        # `role_assignments`.
        co_ban_sao_so_cu = {"tenant_administrator", "tenant_editor"}
        khong_co_duong_nao_khac = sorted(
            c for c in khong_system if c not in co_ban_sao_so_cu)

        assert khong_co_duong_nao_khac == [
            "community_curator",
            "community_member",
            "community_reviewer",
            "project_administrator",
            "project_contributor",
            "project_reviewer",
            "project_viewer",
            "tenant_owner",
            "workspace_administrator",
            "workspace_viewer",
        ], (
            "Tap vai phu thuoc vao cong moi da doi. Danh sach nay la mot phep "
            "do, khong phai mot muc tieu: sua no khi danh muc doi, nhung doc "
            "lai COMMUNITY_MODERATION.md §8 PRE-1 truoc da."
        )

    def test_danh_muc_co_dung_14_vai(self):
        """Ghim con số, vì `roles` trong CSDL có NHIỀU HƠN.

        Bảng `roles` trên máy đang chạy có 17 hàng — 13 vai của danh mục lúc
        đo, cộng bốn hàng cũ đã tắt (`admin`, `contributor`, `guest`,
        `tenant_viewer`). Danh mục nay là 14 vai (thêm `community_reviewer`),
        nên hai con số càng không được suy ra từ nhau.
        Đếm bằng `SELECT count(*) FROM roles` sẽ ra một con số không mô tả
        danh mục, và mọi phát biểu dựa trên nó đều lệch.
        """
        from app.authorization.catalog import BUILTIN_ROLES

        assert len(BUILTIN_ROLES) == 14
