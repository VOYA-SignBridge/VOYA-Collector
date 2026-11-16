"""\"Ghi nhớ đăng nhập trên thiết bị này\".

Ba tính chất cần ghim, vì lỗi ở đây không làm trang đỏ mà làm phiên sống lâu hơn
(hoặc ngắn hơn) người dùng đã chọn:

  * tick thì sống lâu hơn, KHÔNG tick thì y như trước, quản trị viên ngắn hơn;
  * xoay token KHÔNG làm mất lựa chọn — không có cột nào lưu "đã ghi nhớ", thời
    hạn của token cũ (`expires_at - created_at`) chính là lựa chọn đó;
  * trình duyệt biết phiên nào được ghi nhớ qua giá trị của cookie gợi ý.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from fastapi import Response

from app.config import settings
from app.modules.identity import _web_compat as auth
from app.modules.identity import cookies as cookie_auth
from app.modules.saas.tenant_context import system_scope
from app.storage.metadata_db import _execute

DEFAULT = timedelta(minutes=settings.refresh_token_expire_minutes)
REMEMBERED = timedelta(days=settings.remember_me_days)
REMEMBERED_ADMIN = timedelta(days=settings.remember_me_admin_days)


class TestSessionLifetime:
    def test_khong_tick_thi_nhu_cu(self):
        assert auth.session_lifetime(False, False) == DEFAULT
        assert auth.session_lifetime(False, True) == DEFAULT

    def test_tick_thi_dai_hon_va_admin_ngan_hon_nguoi_dung(self):
        assert auth.session_lifetime(True, False) == REMEMBERED
        assert auth.session_lifetime(True, True) == REMEMBERED_ADMIN
        assert REMEMBERED_ADMIN < REMEMBERED

    def test_ghi_nho_khong_bao_gio_ngan_hon_mac_dinh(self, monkeypatch):
        """Cấu hình sai (0 ngày) không được biến "ghi nhớ" thành phiên NGẮN hơn."""
        monkeypatch.setattr(settings, "remember_me_days", 0)
        assert auth.session_lifetime(True, False) == DEFAULT


def _cookies(lifetime=None):
    resp = Response()
    cookie_auth.set_auth_cookies(
        resp, access_token="a", refresh_token="r", csrf_token="c", lifetime=lifetime)
    out = {}
    for raw in resp.headers.getlist("set-cookie"):
        name, _, rest = raw.partition("=")
        value = rest.split(";")[0]
        age = next((p.split("=")[1] for p in rest.split("; ") if p.startswith("Max-Age")), None)
        out[name] = (value, int(age) if age else None)
    return out


class TestCookies:
    def test_phien_thuong_giu_gia_tri_cu(self):
        c = _cookies()
        assert c[cookie_auth.HINT_COOKIE] == (cookie_auth.HINT_SESSION, int(DEFAULT.total_seconds()))
        assert c[cookie_auth.REFRESH_COOKIE][1] == int(DEFAULT.total_seconds())

    def test_phien_ghi_nho_dai_hon_va_cookie_goi_y_noi_ro(self):
        c = _cookies(REMEMBERED)
        seconds = int(REMEMBERED.total_seconds())
        assert c[cookie_auth.HINT_COOKIE] == (cookie_auth.HINT_REMEMBERED, seconds)
        assert c[cookie_auth.REFRESH_COOKIE][1] == seconds
        assert c[cookie_auth.CSRF_COOKIE][1] == seconds
        # Access token KHÔNG kéo dài theo: thứ bị đánh cắp vẫn chỉ sống ngắn.
        assert c[cookie_auth.ACCESS_COOKIE][1] == int(settings.access_token_expire_minutes) * 60


@pytest.fixture
def account():
    from app.modules.identity._web_compat import create_user
    from conftest import purge_registered_account

    name = f"rem{uuid.uuid4().hex[:8]}"
    user = create_user(username=name, email=f"{name}@example.test",
                       password="correct horse battery")
    yield {"id": str(user["id"]), "username": name}
    with system_scope("test cleanup: go refresh token"):
        _execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user["id"],))
    purge_registered_account(name)


def _make_admin(account) -> None:
    with system_scope("test setup: nang tai khoan len admin"):
        _execute("UPDATE users SET is_admin = TRUE WHERE id = %s", (account["id"],))


def _close(a: timedelta, b: timedelta) -> bool:
    return abs(a - b) < timedelta(seconds=5)


class TestRotationKeepsTheChoice:
    def test_xoay_giu_nguyen_thoi_han_ghi_nho(self, account):
        raw = auth.create_refresh_token(account["id"], lifetime=REMEMBERED)
        first = auth.rotate_session(raw)
        second = auth.rotate_session(first.refresh_token)
        assert _close(first.lifetime, REMEMBERED)
        assert _close(second.lifetime, REMEMBERED)

    def test_phien_thuong_van_thuong_sau_khi_xoay(self, account):
        raw = auth.create_refresh_token(account["id"])
        assert _close(auth.rotate_session(raw).lifetime, DEFAULT)

    def test_len_admin_thi_phien_ghi_nho_bi_rut_ngan(self, account):
        raw = auth.create_refresh_token(account["id"], lifetime=REMEMBERED)
        _make_admin(account)
        assert _close(auth.rotate_session(raw).lifetime, REMEMBERED_ADMIN)

    def test_ham_cu_van_tra_bo_ba_cho_noi_goi_cu(self, account):
        raw = auth.create_refresh_token(account["id"])
        user, new_raw, family = auth.rotate_refresh_token(raw)
        assert user["id"] == account["id"] and new_raw and family
