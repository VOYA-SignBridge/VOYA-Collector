"""Thiết bị đang đăng nhập, lịch sử đăng nhập, và thư báo thay đổi bảo mật.

Ba việc cùng trả lời câu "có ai khác đang dùng tài khoản của tôi không": thấy được
thiết bị nào đang vào, đăng xuất được từng cái, và được báo qua email khi mật khẩu
hay email đổi — kể cả tới hộp thư CŨ, nơi kẻ chiếm phiên không với tới.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.config import settings
from app.modules.identity import _web_compat as auth
from app.modules.identity import account_workflows as wf
from app.modules.identity import device_sessions as ds
from app.modules.identity import login_history as lh
from app.modules.saas.tenancy import DEFAULT_TENANT_ID
from app.modules.saas.tenant_context import system_scope, tenant_scope
from app.storage.metadata_db import _execute, _fetch_all

CHROME_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
EDGE_WIN = CHROME_WIN + " Edg/130.0"
FIREFOX_LINUX = "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0"
SAFARI_IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
CHROME_ANDROID = "Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"


class TestDescribeDevice:
    @pytest.mark.parametrize("ua, expected", [
        (CHROME_WIN, "Chrome · Windows"),
        (EDGE_WIN, "Edge · Windows"),  # Edge cũng có chữ Chrome: không được nhận nhầm
        (FIREFOX_LINUX, "Firefox · Linux"),
        (SAFARI_IPHONE, "Safari · iPhone"),
        (CHROME_ANDROID, "Chrome · Android"),  # Android cũng có chữ Linux
        ("curl/8.0", "Thiết bị không xác định"),
        ("", "Thiết bị không xác định"),
        (None, "Thiết bị không xác định"),
    ])
    def test_nhan_ra_trinh_duyet_va_he_dieu_hanh(self, ua, expected):
        assert ds.describe_device(ua) == expected

    def test_user_agent_dai_bi_cat(self):
        assert len(ds.clip_user_agent("x" * 1000)) == ds.UA_MAX
        assert ds.clip_user_agent("   ") is None


@pytest.fixture
def account():
    from conftest import purge_registered_account

    name = f"dev{uuid.uuid4().hex[:8]}"
    user = auth.create_user(username=name, email=f"{name}@example.test",
                            password="correct horse battery")
    yield {"id": str(user["id"]), "username": name, "email": f"{name}@example.test"}
    with system_scope("test cleanup: go refresh token"):
        _execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user["id"],))
        _execute("DELETE FROM audit_log WHERE actor_user_id = %s", (user["id"],))
    purge_registered_account(name)


def _login(account, ua=CHROME_WIN, lifetime=None):
    """Một lần đăng nhập: trả về (token thô, họ)."""
    fam = auth.new_session_family()
    raw = auth.create_refresh_token(account["id"], family_id=fam, lifetime=lifetime, user_agent=ua)
    return raw, fam


class TestDanhSachThietBi:
    def test_moi_lan_dang_nhap_la_mot_thiet_bi_co_nhan(self, account):
        _, f1 = _login(account, CHROME_WIN)
        _, f2 = _login(account, SAFARI_IPHONE)
        got = {s["id"]: s for s in ds.list_sessions(account["id"], current=f1)}
        assert set(got) == {f1, f2}
        assert got[f1]["device"] == "Chrome · Windows" and got[f1]["current"] is True
        assert got[f2]["device"] == "Safari · iPhone" and got[f2]["current"] is False

    def test_xoay_token_van_la_mot_thiet_bi_va_giu_nhan(self, account):
        raw, fam = _login(account, FIREFOX_LINUX)
        auth.rotate_session(raw)
        auth.rotate_session(auth.rotate_session(raw).refresh_token)
        sessions = ds.list_sessions(account["id"], current=None)
        assert [s["id"] for s in sessions] == [fam]
        assert sessions[0]["device"] == "Firefox · Linux"

    def test_phien_ghi_nho_duoc_danh_dau(self, account):
        _login(account, lifetime=timedelta(days=settings.remember_me_days))
        assert ds.list_sessions(account["id"], None)[0]["remembered"] is True

    def test_phien_thuong_khong_phai_ghi_nho(self, account):
        _login(account)
        assert ds.list_sessions(account["id"], None)[0]["remembered"] is False

    def test_khong_thay_thiet_bi_cua_nguoi_khac(self, account):
        _login(account)
        assert ds.list_sessions(str(uuid.uuid4()), None) == []

    def test_phien_het_han_khong_hien(self, account):
        raw, _ = _login(account)
        with system_scope("test setup: cho token het han"):
            _execute("UPDATE refresh_tokens SET expires_at = NOW() - interval '1 minute' "
                     "WHERE token_hash = %s", (auth._hash_token(raw),))
        assert ds.list_sessions(account["id"], None) == []


class TestDangXuatThietBi:
    def test_dang_xuat_mot_thiet_bi_chi_dong_dung_thiet_bi_do(self, account):
        _, keep = _login(account, CHROME_WIN)
        _, drop = _login(account, SAFARI_IPHONE)
        assert ds.revoke_session(account["id"], drop) is True
        assert [s["id"] for s in ds.list_sessions(account["id"], keep)] == [keep]

    def test_khong_dang_xuat_duoc_thiet_bi_cua_nguoi_khac(self, account):
        _, fam = _login(account)
        assert ds.revoke_session(str(uuid.uuid4()), fam) is False
        assert [s["id"] for s in ds.list_sessions(account["id"], None)] == [fam]

    def test_thiet_bi_vua_bi_dang_xuat_khong_lam_moi_duoc_ke_ca_trong_an_han(self, account):
        """Cửa sổ ân hạn 15 giây dành cho hai tab đua nhau, không cho thiết bị bị đá."""
        raw, fam = _login(account)
        ds.revoke_session(account["id"], fam)
        assert auth.rotate_session(raw) is None

    def test_dang_xuat_cac_thiet_bi_khac_giu_lai_thiet_bi_hien_tai(self, account):
        _, keep = _login(account)
        _login(account)
        _login(account)
        assert ds.revoke_other_sessions(account["id"], keep) == 2
        assert [s["id"] for s in ds.list_sessions(account["id"], keep)] == [keep]

    def test_khong_con_phien_nao_thi_la_so_khong(self, account):
        assert ds.revoke_other_sessions(account["id"], None) == 0


class TestLichSuDangNhap:
    @pytest.fixture
    def scope(self):
        with tenant_scope(DEFAULT_TENANT_ID):
            yield

    def _request(self, ua=CHROME_WIN):
        return SimpleNamespace(
            headers={"user-agent": ua}, client=SimpleNamespace(host="10.9.9.9"),
            url=SimpleNamespace(path="/api/v1/auth/login", netloc="", scheme="http"), method="POST")

    def test_ghi_roi_doc_lai_theo_thu_tu_moi_nhat_truoc(self, account, scope):
        user = auth._fetch_user_by_id(account["id"])
        lh.record_login(user, self._request(CHROME_WIN), remember=False)
        lh.record_login(user, self._request(SAFARI_IPHONE), remember=True)
        events = lh.recent_logins(account["id"])
        assert [e["device"] for e in events] == ["Safari · iPhone", "Chrome · Windows"]
        assert [e["remember"] for e in events] == [True, False]

    def test_khong_luu_dia_chi_ip_tho(self, account, scope):
        user = auth._fetch_user_by_id(account["id"])
        lh.record_login(user, self._request(), remember=False)
        with system_scope("test: doc dong kiem toan"):
            rows = _fetch_all("SELECT detail::text AS d, ip_hash FROM audit_log "
                              "WHERE actor_user_id = %s AND action = 'auth.login'", (account["id"],))
        assert rows and "10.9.9.9" not in rows[0]["d"]
        assert rows[0]["ip_hash"] != "10.9.9.9"

    def test_loi_ghi_vet_khong_lam_hong_dang_nhap(self, account, scope, monkeypatch):
        """Phiên đã cấp rồi; ghi vết hỏng không được biến nó thành 500."""
        monkeypatch.setattr(lh, "describe_device", lambda *_: 1 / 0)
        lh.record_login(auth._fetch_user_by_id(account["id"]), self._request(), remember=False)

    def test_chi_doc_duoc_lich_su_cua_chinh_minh(self, account, scope):
        lh.record_login(auth._fetch_user_by_id(account["id"]), self._request(), remember=False)
        assert lh.recent_logins(str(uuid.uuid4())) == []


class TestThuBaoBaoMat:
    def _capture(self):
        sent = []
        return sent, lambda fn, *args: sent.append((fn.__name__, args))

    def test_doi_mat_khau_gui_thu_toi_email_hien_tai(self):
        sent, enqueue = self._capture()
        wf.notify_password_changed({"username": "kha", "email": "kha@example.test"}, enqueue)
        assert len(sent) == 1
        name, (to, username, subject, message) = sent[0]
        assert name == "send_security_notice_email" and to == "kha@example.test"
        assert "đăng xuất" in message

    def test_tai_khoan_khong_co_email_thi_khong_gui_gi(self):
        sent, enqueue = self._capture()
        wf.notify_password_changed({"username": "x", "email": ""}, enqueue)
        assert sent == []

    def test_mask_email(self):
        assert wf._mask_email("khanh@cantho.edu.vn") == "k***@cantho.edu.vn"
        assert wf._mask_email("khong-co-a-cong") == "khong-co-a-cong"

    def test_noi_dung_thu_khong_chua_ma_hay_lien_ket(self):
        """Thư báo chỉ MÔ TẢ thay đổi; kẻ đọc được hộp thư cũng không lấy được gì."""
        import app.services.email as email

        captured = {}
        orig = email._send
        email._send = lambda to, subject, body, *, loggable: captured.update(to=to, body=body, loggable=loggable)
        try:
            email.send_security_notice_email("a@b.test", "kha", "Tiêu đề", "Mật khẩu vừa đổi.")
        finally:
            email._send = orig
        assert "http" not in captured["body"] and captured["loggable"] is True
        assert "Quên mật khẩu" in captured["body"]
