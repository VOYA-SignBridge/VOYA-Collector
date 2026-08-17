"""Đổi mật khẩu khi đang đăng nhập, và đường quản trị viên hỗ trợ khôi phục.

Vì sao tệp này tồn tại
-----------------------
Trước 16/08/2026 hệ thống KHÔNG có đường đổi mật khẩu cho người đang đăng nhập.
`PATCH /auth/me` chỉ đổi tên; đổi mật khẩu chỉ có luồng quên-mật-khẩu qua email.
Trang `/settings/security` có một khối chữ tên "Quên mật khẩu?" — không nút, chỉ
chữ. Người muốn đổi mật khẩu định kỳ phải giả vờ quên nó.

Yêu cầu ban đầu là "phải bật 2FA mới cho đổi mật khẩu". Không làm thế, và lý do
được neo thành test ở đây: bắt buộc 2FA tạo một đường KHOÁ CỬA. Người dùng chính
của hệ thống này là người khiếm thính/khiếm ngôn; một người không có điện thoại
thông minh sẽ vĩnh viễn không đổi được mật khẩu. Hướng hỏng đó tệ hơn thứ nó
định chặn.

Nên hợp đồng là: **mật khẩu hiện tại luôn bắt buộc; yếu tố thứ hai chỉ bắt buộc
khi đã bật; và mã khôi phục luôn thay được mã TOTP.**
"""

from __future__ import annotations

import time
import uuid

import pytest
from fastapi import HTTPException

from app import notifications, totp, two_factor
from app.routers import auth as auth_router
from app.storage.metadata_db import _execute, _fetch_all
from app.tenancy import DEFAULT_TENANT_ID
from app.tenant_context import system_scope, tenant_scope

PASSWORD = "correct horse battery"


class _Req:
    """Đủ thứ mà `enforce_ip_limit` và `audit.record` đọc, không hơn."""

    def __init__(self) -> None:
        self.client = type("C", (), {"host": f"10.0.0.{uuid.uuid4().int % 250}"})()
        self.headers = {}
        self.url = type("U", (), {"path": "/api/v1/auth/change-password"})()
        self.method = "POST"


def _make_account(prefix: str) -> dict:
    from app.auth import create_user

    name = f"{prefix}{uuid.uuid4().hex[:8]}"
    user = create_user(username=name, email=f"{name}@example.test",
                       password=PASSWORD)
    return {"id": str(user["id"]), "username": name}


def _current(account: dict) -> dict:
    """Hàng người dùng như `get_current_user` trả về — kèm `password_hash`."""
    rows = _fetch_all("SELECT id, username, email, password_hash, is_admin "
                      "FROM users WHERE id = %s", (account["id"],))
    row = dict(rows[0])
    row["id"] = str(row["id"])
    return row


@pytest.fixture
def account():
    acc = _make_account("chpw")
    yield acc
    from conftest import purge_registered_account

    with system_scope("test cleanup: doi mat khau"):
        _execute("DELETE FROM notifications WHERE user_id = %s", (acc["id"],))
        _execute("DELETE FROM user_recovery_codes WHERE user_id = %s", (acc["id"],))
        _execute("DELETE FROM user_totp WHERE user_id = %s", (acc["id"],))
    purge_registered_account(acc["username"])


@pytest.fixture
def scope():
    with tenant_scope(DEFAULT_TENANT_ID):
        yield


def _change(account, **kw):
    payload = auth_router.ChangePasswordRequest(
        current_password=kw.pop("current_password", PASSWORD),
        new_password=kw.pop("new_password", "a brand new passphrase"),
        code=kw.pop("code", None),
    )
    return auth_router.change_password(payload, _Req(), _current(account))


class TestKhongCo2FA:
    def test_doi_duoc_bang_mat_khau_hien_tai(self, account, scope):
        _change(account)
        from app.auth import verify_password

        assert verify_password("a brand new passphrase",
                               _current(account)["password_hash"])

    def test_sai_mat_khau_hien_tai_thi_403(self, account, scope):
        with pytest.raises(HTTPException) as exc:
            _change(account, current_password="sai bét")
        assert exc.value.status_code == 403

    def test_mat_khau_moi_trung_mat_khau_cu_bi_tu_choi(self, account, scope):
        with pytest.raises(HTTPException) as exc:
            _change(account, new_password=PASSWORD)
        assert exc.value.status_code == 400

    def test_thu_hoi_moi_phien_tren_moi_thiet_bi(self, account, scope):
        """Lý do phổ biến nhất để đổi mật khẩu là "tôi nghi bị chiếm tài khoản".
        Giữ lại phiên cũ là bỏ sót đúng cái mình định đuổi."""
        _change(account)
        rows = _fetch_all("SELECT sessions_invalid_before FROM users WHERE id = %s",
                          (account["id"],))
        assert rows[0]["sessions_invalid_before"] is not None

    def test_bao_cho_chinh_chu_tai_khoan(self, account, scope):
        _change(account)
        items = notifications.list_for_user(account["id"])
        assert any(n["kind"] == "security" for n in items)

    def test_lan_nhap_sai_cung_de_lai_dau(self, account, scope):
        """Người chiếm được máy đang mở sẽ đoán mật khẩu ở đây. Chủ tài khoản
        phải thấy được điều đó, nếu không thì lớp "nhập lại mật khẩu" chỉ chặn
        chứ không tố cáo."""
        with pytest.raises(HTTPException):
            _change(account, current_password="đoán bừa")
        titles = [n["title"] for n in notifications.list_for_user(account["id"])]
        assert any("sai mật khẩu" in t for t in titles)


class TestCo2FA:
    @pytest.fixture
    def with_2fa(self, account):
        out = two_factor.begin_enrollment(account["id"], account["username"])
        codes = two_factor.confirm_enrollment(
            account["id"], totp.totp(out["secret"]))
        return {"secret": out["secret"], "recovery": codes}

    def test_thieu_ma_thi_400_kem_ma_may_doc_duoc(self, account, scope, with_2fa):
        """Giao diện dùng `code` để mở ô nhập mã, thay vì hiện một câu lỗi đỏ mà
        người dùng không biết phải làm gì với nó."""
        with pytest.raises(HTTPException) as exc:
            _change(account)
        assert exc.value.status_code == 400
        assert exc.value.detail["code"] == "2fa_required"

    def test_ma_totp_dung_thi_doi_duoc(self, account, scope, with_2fa):
        # Mã của bước KẾ TIẾP, không phải bước hiện tại. Bước hiện tại đã bị
        # `confirm_enrollment` tiêu mất trong fixture, và `verify_code` từ chối
        # phát lại một bước đã dùng — đúng như nó phải làm. Dùng lại bước ấy ở
        # đây sẽ làm test đỏ vì một tính chất bảo mật đang hoạt động đúng, và
        # cách "sửa" mà nó gợi ý là nới chống-phát-lại ra.
        _change(account, code=totp.totp(with_2fa["secret"], at=time.time() + 30))
        from app.auth import verify_password

        assert verify_password("a brand new passphrase",
                               _current(account)["password_hash"])

    def test_ma_khoi_phuc_THAY_DUOC_ma_totp(self, account, scope, with_2fa):
        """Mất điện thoại không được đồng nghĩa với mất tài khoản. Đây là điều
        kiện đã chọn thay cho "bắt buộc bật 2FA" — xem chú thích đầu tệp."""
        _change(account, code=with_2fa["recovery"][0])
        from app.auth import verify_password

        assert verify_password("a brand new passphrase",
                               _current(account)["password_hash"])

    def test_ma_khoi_phuc_chi_dung_duoc_MOT_lan(self, account, scope, with_2fa):
        code = with_2fa["recovery"][0]
        _change(account, code=code)
        with pytest.raises(HTTPException) as exc:
            _change(account, current_password="a brand new passphrase",
                    new_password="mot mat khau khac nua", code=code)
        assert exc.value.status_code == 403

    def test_ma_sai_thi_403(self, account, scope, with_2fa):
        with pytest.raises(HTTPException) as exc:
            _change(account, code="000000")
        assert exc.value.status_code == 403


class TestAdminHoTroKhoiPhuc:
    """Quản trị viên mở lại cánh cửa, KHÔNG đặt mật khẩu hộ.

    Ranh giới đó là điều kiện để nhật ký kiểm toán còn giá trị: một quản trị
    viên biết mật khẩu của người khác thì mọi dòng ghi từ đó trở đi không phân
    biệt được ai đã thao tác.
    """

    @pytest.fixture
    def operator(self):
        acc = _make_account("adminop")
        yield {**_current(acc), "is_admin": True}
        from conftest import purge_registered_account

        purge_registered_account(acc["username"])

    def _call(self, account, operator, action, reason="mat dien thoai"):
        from app.routers import admin as admin_router

        class _BG:
            def add_task(self, *a, **kw):
                # Thư đi qua BackgroundTasks thật ở production; ở đây chỉ cần
                # biết endpoint có xếp việc gửi hay không.
                self.called = True

        payload = admin_router.RecoveryAssist(action=action, reason=reason)
        return admin_router.assist_recovery(
            account["id"], payload, _BG(), _Req(), operator)

    def test_go_2fa_cho_nguoi_mat_thiet_bi(self, account, scope, operator):
        out = two_factor.begin_enrollment(account["id"], account["username"])
        two_factor.confirm_enrollment(account["id"], totp.totp(out["secret"]))
        assert two_factor.is_enabled(account["id"])

        self._call(account, operator, "clear_2fa")
        assert not two_factor.is_enabled(account["id"])

    def test_nguoi_bi_tac_dong_LUON_duoc_bao(self, account, scope, operator):
        """Lớp quan trọng nhất, và là lớp hay bị bỏ. Nếu chủ tài khoản không bao
        giờ biết ai đó đã gỡ 2FA của mình thì kiểm toán chỉ phục vụ điều tra sau
        khi có người tố cáo — mà người tố cáo được lại chính là người bị giấu."""
        self._call(account, operator, "clear_2fa", reason="mat ca ma khoi phuc")
        items = notifications.list_for_user(account["id"])
        assert items and items[0]["kind"] == "security"
        assert "mat ca ma khoi phuc" in items[0]["body"]

    def test_thieu_ly_do_thi_tu_choi(self, account, scope, operator):
        with pytest.raises(HTTPException) as exc:
            self._call(account, operator, "clear_2fa", reason="x")
        assert exc.value.status_code == 400

    def test_hanh_dong_la_thi_tu_choi(self, account, scope, operator):
        with pytest.raises(HTTPException) as exc:
            self._call(account, operator, "set_password")
        assert exc.value.status_code == 400

    def test_nguoi_dung_khong_ton_tai_thi_404(self, scope, operator):
        with pytest.raises(HTTPException) as exc:
            self._call({"id": str(uuid.uuid4())}, operator, "clear_2fa")
        assert exc.value.status_code == 404
