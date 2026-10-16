"""Đổi địa chỉ email khi đang đăng nhập.

Vì sao tệp này tồn tại
-----------------------
Trước 16/08/2026 **không có đường nào đổi email**. `PATCH /auth/me` chỉ nhận
`username`; `otp.mark_verified` thì đánh dấu đã xác minh **chỉ khi địa chỉ trùng
email hiện tại** (`AND lower(email) = %s`), nên gửi mã tới một địa chỉ mới rồi
xác nhận sẽ khớp 0 dòng và không có gì xảy ra. Người gõ nhầm email lúc đăng ký
mắc kẹt vĩnh viễn với một hộp thư họ không đọc được — tức là mất luôn đường
khôi phục tài khoản.

Hai tính chất được ghim kỹ nhất, vì cả hai là chỗ một bản cài đặt *trông như
chạy được* vẫn mở đường chiếm tài khoản:

1. **Mã đi tới địa chỉ MỚI.** Thứ cần chứng minh là "bạn đọc được hộp thư mới".
   Gửi tới hộp thư cũ chỉ chứng minh lại điều mà việc đang đăng nhập đã chứng
   minh rồi.
2. **Mật khẩu hỏi ở CẢ HAI bước.** Bước đầu chỉ gửi một lá thư; bước sau mới
   đổi địa chỉ nhận thư khôi phục — tức bước biến một phiên bị chiếm thành mất
   tài khoản vĩnh viễn. Một cửa sổ trình duyệt bỏ quên giữa hai bước không được
   phép là đủ.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app import notifications, otp
from app.routers import auth as auth_router
from app.storage.metadata_db import _execute, _fetch_all
from app.tenancy import DEFAULT_TENANT_ID
from app.tenant_context import system_scope, tenant_scope

PASSWORD = "correct horse battery"


class _Req:
    def __init__(self) -> None:
        self.client = type("C", (), {"host": f"10.1.0.{uuid.uuid4().int % 250}"})()
        self.headers = {}
        self.url = type("U", (), {"path": "/api/v1/auth/change-email/start"})()
        self.method = "POST"


def _make_account(prefix: str) -> dict:
    from app.auth import create_user

    name = f"{prefix}{uuid.uuid4().hex[:8]}"
    user = create_user(username=name, email=f"{name}@example.test",
                       password=PASSWORD)
    return {"id": str(user["id"]), "username": name,
            "email": f"{name}@example.test"}


def _current(account: dict) -> dict:
    rows = _fetch_all("SELECT id, username, email, password_hash, is_admin "
                      "FROM users WHERE id = %s", (account["id"],))
    row = dict(rows[0])
    row["id"] = str(row["id"])
    return row


@pytest.fixture
def account():
    acc = _make_account("chmail")
    yield acc
    from conftest import purge_registered_account

    with system_scope("test cleanup: doi email"):
        _execute("DELETE FROM notifications WHERE user_id = %s", (acc["id"],))
        _execute("DELETE FROM verification_codes WHERE user_id = %s", (acc["id"],))
    # Tài khoản có thể đã đổi tên email; dọn theo username vẫn đúng.
    purge_registered_account(acc["username"])


@pytest.fixture
def scope():
    with tenant_scope(DEFAULT_TENANT_ID):
        yield


def _start(account, *, new_email, password=PASSWORD):
    payload = auth_router.ChangeEmailStartRequest(
        current_password=password, new_email=new_email)
    return auth_router.change_email_start(payload, _Req(), _current(account))


def _confirm(account, *, code, password=PASSWORD):
    payload = auth_router.ChangeEmailConfirmRequest(
        current_password=password, code=code)
    return auth_router.change_email_confirm(payload, _Req(), _current(account))


# Mã thật không đọc lại được — bảng chỉ giữ digest. Nên các bài dưới gọi thẳng
# `otp.issue` để có mã trong tay. Điều đó KHÔNG làm nhẹ bài kiểm: `otp.issue`
# tiêu mọi thử thách còn sống của cùng (người, mục đích), nên mã lấy được ở đây
# là mã duy nhất còn hiệu lực — đúng cái mà endpoint sẽ đối chiếu.


class TestGuiMa:
    def test_ma_di_toi_dia_chi_MOI(self, account, scope, monkeypatch):
        sent: dict = {}

        def fake_send(to_email, code, purpose):
            sent["to"] = to_email
            sent["code"] = code

        monkeypatch.setattr("app.email_service.send_verification_code_email",
                            fake_send)
        new = f"moi{uuid.uuid4().hex[:6]}@example.test"
        out = _start(account, new_email=new)

        assert out["sent_to"] == new
        assert sent["to"] == new, "mã phải tới hộp thư MỚI, không phải hộp thư cũ"

    def test_sai_mat_khau_thi_403_va_khong_gui_gi(self, account, scope, monkeypatch):
        called: list = []
        monkeypatch.setattr("app.email_service.send_verification_code_email",
                            lambda *a, **k: called.append(1))
        with pytest.raises(HTTPException) as exc:
            _start(account, new_email="ai-do@example.test", password="sai")
        assert exc.value.status_code == 403
        assert not called, "không được gửi thư khi mật khẩu sai"

    def test_dia_chi_trung_dia_chi_dang_dung_bi_tu_choi(self, account, scope):
        with pytest.raises(HTTPException) as exc:
            _start(account, new_email=account["email"])
        assert exc.value.status_code == 400

    def test_dia_chi_da_co_tai_khoan_khac_dung_thi_409(self, account, scope):
        """Bắt ở BƯỚC ĐẦU, không để câu INSERT vỡ vì ràng buộc UNIQUE ở bước
        cuối. Người dùng cần một câu trả lời rõ ràng, không phải lỗi 500 sau khi
        đã đi hết hai bước."""
        other = _make_account("chmail2")
        try:
            with pytest.raises(HTTPException) as exc:
                _start(account, new_email=other["email"])
            assert exc.value.status_code == 409
        finally:
            from conftest import purge_registered_account

            purge_registered_account(other["username"])

    def test_dia_chi_khong_hop_le_bi_chan_o_lop_kieu(self, account, scope):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            auth_router.ChangeEmailStartRequest(
                current_password=PASSWORD, new_email="khong-phai-email")


class TestXacNhan:
    def _issue(self, account, new_email):
        _, code = otp.issue(user_id=account["id"], purpose="verify_email",
                            channel="email", destination=new_email)
        return code

    def test_doi_duoc_va_danh_dau_da_xac_minh(self, account, scope):
        new = f"moi{uuid.uuid4().hex[:6]}@example.test"
        code = self._issue(account, new)

        out = _confirm(account, code=code)
        assert out["email"] == new
        assert out["email_verified"] is True

        rows = _fetch_all("SELECT email, email_verified_at FROM users WHERE id = %s",
                          (account["id"],))
        assert rows[0]["email"] == new
        assert rows[0]["email_verified_at"] is not None

    def test_mat_khau_van_bi_hoi_o_BUOC_HAI(self, account, scope):
        """Đây là lớp chặn một phiên bị chiếm. Bỏ nó đi thì bước đầu (có mật
        khẩu) và bước sau (không) tạo ra một cửa sổ: ai mượn được máy sau khi
        chủ tài khoản đã bấm "gửi mã" chỉ cần đọc mã là xong."""
        new = f"moi{uuid.uuid4().hex[:6]}@example.test"
        code = self._issue(account, new)

        with pytest.raises(HTTPException) as exc:
            _confirm(account, code=code, password="sai")
        assert exc.value.status_code == 403

        rows = _fetch_all("SELECT email FROM users WHERE id = %s", (account["id"],))
        assert rows[0]["email"] == account["email"], "email không được đổi"

    def test_ma_sai_thi_khong_doi_gi(self, account, scope):
        new = f"moi{uuid.uuid4().hex[:6]}@example.test"
        self._issue(account, new)

        with pytest.raises(HTTPException):
            _confirm(account, code="000000")
        rows = _fetch_all("SELECT email FROM users WHERE id = %s", (account["id"],))
        assert rows[0]["email"] == account["email"]

    def test_bao_cho_chinh_chu_tai_khoan(self, account, scope):
        """Đổi địa chỉ nhận thư khôi phục là thao tác biến một phiên bị chiếm
        thành mất tài khoản vĩnh viễn. Nếu chủ tài khoản không bao giờ biết, họ
        không có gì để tố cáo."""
        new = f"moi{uuid.uuid4().hex[:6]}@example.test"
        code = self._issue(account, new)
        _confirm(account, code=code)

        items = notifications.list_for_user(account["id"])
        assert items and items[0]["kind"] == "security"
        assert items[0]["severity"] == "critical"
        assert account["email"] in items[0]["body"]
        assert new in items[0]["body"]

    def test_KHONG_dung_duoc_lai_ma_da_tieu(self, account, scope):
        new = f"moi{uuid.uuid4().hex[:6]}@example.test"
        code = self._issue(account, new)
        _confirm(account, code=code)

        with pytest.raises(HTTPException):
            _confirm(account, code=code)
