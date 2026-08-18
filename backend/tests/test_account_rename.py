"""Đổi tên tài khoản phải kéo theo mọi bản sao của cái tên — và chỉ đúng những chỗ đó.

`username` được CHÉP vào dữ liệu lúc ghi, ở bảy cột thuộc năm bảng cộng một cột
trong `dataset/samples.csv`. Đổi mỗi bảng `users` thì tài khoản mang tên mới còn
dữ liệu đã đóng góp vẫn mang tên cũ.

Ranh giới quan trọng hơn cả việc cập nhật: `audit_log.actor_label` và
`legal_document_events.actor_label` là **bằng chứng lịch sử** và tuyệt đối không
được đổi. Bộ test này ghim cả hai chiều.
"""
from __future__ import annotations

import uuid

import pytest

from app import account_rename as ar
from app.storage.metadata_db import _execute, _fetch_all
from app.tenant_context import system_scope


@pytest.fixture
def account():
    """Một tài khoản dùng một lần, dọn sạch kể cả khi test đỏ."""
    from app.auth import create_user
    from conftest import purge_registered_account

    name = f"rn{uuid.uuid4().hex[:8]}"
    user = create_user(username=name, email=f"{name}@example.test",
                       password="correct horse battery")
    yield {"id": str(user["id"]), "username": name}
    purge_registered_account(name)
    purge_registered_account(f"{name}x")


@pytest.fixture
def sample_row(account):
    """Một hàng `samples` mang tên hiển thị của tài khoản trên."""
    # `samples_uid_is_hex10` bắt đúng 10 ký tự hex, và `fk_samples_class_tenant`
    # đòi lớp phải có thật — nên mượn một lớp đang tồn tại thay vì bịa một cái.
    #
    # Lớp phải nằm ĐÚNG trong tenant của tài khoản. Bản trước viết
    # `FROM classes LIMIT 1` không kèm `ORDER BY`, nên nó nhận về bất kỳ lớp nào
    # Postgres trả ra trước — và khi bộ đo cách ly để lại dữ liệu ở `iso_a`,
    # `iso_b` thì hàng mẫu được dựng ở một tenant khác hẳn tenant của tài khoản.
    # Đường đổi tên lọc theo `tenant_id` (cố ý, để không đổi tên hàng vô chủ của
    # tenant khác), nên nó bỏ qua hàng ấy và đúng ba phép kiểm đỏ — trong khi
    # sản phẩm hành xử chính xác. Fixture dựng dữ liệu xuyên tenant thì phép
    # kiểm không còn đo cái nó tưởng mình đang đo.
    uid = uuid.uuid4().hex[:10]
    with system_scope("test setup: dung mot hang mau"):
        classes = _fetch_all(
            "SELECT c.class_uid, c.tenant_id FROM classes c "
            "JOIN users u ON u.tenant_id = c.tenant_id "
            "WHERE u.id = %s ORDER BY c.class_uid LIMIT 1",
            (account["id"],))
        if not classes:
            pytest.skip("tenant cua tai khoan khong co lop nao de gan mau thu")
        _execute(
            "INSERT INTO samples (sample_uid, class_uid, user_id, username, "
            "auth_user_id, tenant_id, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, now())",
            (uid, classes[0]["class_uid"], account["username"], account["username"],
             account["id"], classes[0]["tenant_id"]))
    yield uid
    with system_scope("test cleanup: go hang mau"):
        _execute("DELETE FROM samples WHERE sample_uid = %s", (uid,))


def _sample(uid: str) -> dict:
    with system_scope("test read"):
        rows = _fetch_all("SELECT user_id, username FROM samples WHERE sample_uid = %s",
                          (uid,))
    return rows[0] if rows else {}


class TestTenDiTheoDuLieu:
    def test_doi_ten_keo_theo_hang_mau(self, account, sample_row):
        new = f"{account['username']}x"
        result = ar.rename_user(account["id"], new)

        assert result["changed"] is True
        row = _sample(sample_row)
        assert row["user_id"] == new
        assert row["username"] == new

    def test_bang_users_cung_doi(self, account, sample_row):
        new = f"{account['username']}x"
        ar.rename_user(account["id"], new)

        with system_scope("test read"):
            rows = _fetch_all("SELECT username FROM users WHERE id = %s", (account["id"],))
        assert rows[0]["username"] == new

    def test_doi_ve_chinh_no_thi_khong_lam_gi(self, account):
        result = ar.rename_user(account["id"], account["username"])
        assert result["changed"] is False
        assert result["rows"] == {}

    def test_bao_cao_so_hang_da_doi(self, account, sample_row):
        result = ar.rename_user(account["id"], f"{account['username']}x")
        # Người vận hành phải thấy việc gì đã thật sự xảy ra, không chỉ "xong".
        assert result["rows"]["samples.user_id"] >= 1
        assert result["rows"]["users"] == 1


class TestBangChungLichSuKhongDuocSua:
    def test_dong_kiem_toan_giu_nguyen_ten_cu(self, account, sample_row):
        """Sửa `actor_label` theo tên mới là viết lại lịch sử: dòng kiểm toán cũ
        sẽ mô tả một người không tồn tại vào thời điểm đó."""
        from app import audit

        old = account["username"]
        audit.record("test.rename.probe", actor={"id": account["id"], "username": old},
                     target_type="user", target_id=account["id"])

        ar.rename_user(account["id"], f"{old}x")

        with system_scope("test read"):
            rows = _fetch_all(
                "SELECT actor_label FROM audit_log WHERE action = 'test.rename.probe' "
                "AND target_id = %s", (account["id"],))
        assert rows, "dong kiem toan phai ton tai de test co nghia"
        assert rows[0]["actor_label"] == old, "ten cu phai duoc giu nguyen"

        with system_scope("test cleanup"):
            _execute("DELETE FROM audit_log WHERE action = 'test.rename.probe' "
                     "AND target_id = %s", (account["id"],))

    def test_danh_sach_cam_khong_giao_voi_danh_sach_phai_doi(self):
        """Một danh sách cấm không ai kiểm thì chỉ là một lời bình luận."""
        assert not (set(ar.STATE_COPIES) & set(ar.FROZEN_COPIES))


class TestTuChoiNhungCaiPhaiTuChoi:
    def test_ten_trong(self, account):
        with pytest.raises(ar.RenameError) as exc:
            ar.rename_user(account["id"], "   ")
        assert exc.value.code == "empty_username"

    def test_tai_khoan_khong_ton_tai(self):
        with pytest.raises(ar.RenameError) as exc:
            ar.rename_user(str(uuid.uuid4()), "aiday")
        assert exc.value.status_code == 404

    def test_trung_ten_bao_bang_tieng_nguoi(self, account):
        """Để ràng buộc UNIQUE tự bắn thì thông báo nói về tên chỉ mục, không
        nói được với người dùng rằng cái tên họ chọn đã có người lấy."""
        from app.auth import create_user
        from conftest import purge_registered_account

        other = f"rn{uuid.uuid4().hex[:8]}"
        create_user(username=other, email=f"{other}@example.test",
                    password="correct horse battery")
        try:
            with pytest.raises(ar.RenameError) as exc:
                ar.rename_user(account["id"], other)
            assert exc.value.code == "username_taken"
            assert exc.value.status_code == 409
        finally:
            purge_registered_account(other)

    def test_trung_ten_khong_phan_biet_hoa_thuong(self, account):
        from app.auth import create_user
        from conftest import purge_registered_account

        other = f"rn{uuid.uuid4().hex[:8]}"
        create_user(username=other, email=f"{other}@example.test",
                    password="correct horse battery")
        try:
            with pytest.raises(ar.RenameError):
                ar.rename_user(account["id"], other.upper())
        finally:
            purge_registered_account(other)


class TestSoatTenLacHau:
    def test_khong_con_hang_nao_lac_hau_sau_khi_doi(self, account, sample_row):
        ar.rename_user(account["id"], f"{account['username']}x")
        stale = ar.find_stale_display_names()
        # Chỉ khẳng định về hàng của CHÍNH tài khoản này: bản sao dữ liệu thật
        # có sẵn hàng cũ từ thời chưa có đường đổi tên, và khẳng định con số
        # tuyệt đối trên dữ liệu thật là kiểu đỏ giả đã gặp nhiều lần.
        with system_scope("test read"):
            rows = _fetch_all(
                "SELECT count(*) AS n FROM samples s JOIN users u ON u.id = s.auth_user_id "
                "WHERE s.auth_user_id = %s AND s.user_id <> u.username",
                (account["id"],))
        assert int(rows[0]["n"]) == 0
        assert isinstance(stale, dict)
