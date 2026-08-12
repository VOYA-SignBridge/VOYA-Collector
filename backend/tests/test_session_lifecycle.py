"""Vòng đời phiên đăng nhập: xoay token, phát hiện tái sử dụng, đăng xuất thật.

Bốn lỗ được rà ngày 2026-07-31 (`docs/needFix/AUTH_TOKEN_LIFECYCLE.md`) và vá
ngày 2026-08-10. Bộ này ghim đúng những tính chất mà bản vá hứa, và — quan trọng
hơn — ghim cả cái GIÁ của nó, vì hai yêu cầu ở đây kéo ngược chiều nhau:

  * phát hiện tái sử dụng muốn ân hạn bằng 0
  * hai tab cùng mở lại đua nhau gọi /refresh một cách hoàn toàn hợp lệ

Làm riêng lẻ thì hoặc đá oan người dùng, hoặc mở cửa cho token bị trộm. Vì thế
`test_trong_an_han_thi_cap_moi` và `test_ngoai_an_han_thi_dot_ca_ho` phải cùng
xanh; một mình cái nào xanh cũng không chứng minh được gì.

Chạy trên Postgres THẬT, không giả lập: thứ đang được kiểm phần lớn là các câu
SQL (`COALESCE(revoked_at, NOW())`, `GREATEST(...)`) và một bản giả sẽ chỉ kiểm
lại chính bản giả đó.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import auth
from app.storage.metadata_db import _execute, _fetch_all
from app.tenant_context import system_scope


@pytest.fixture
def account():
    """Một tài khoản dùng một lần, dọn sạch kể cả khi test đỏ."""
    from app.auth import create_user
    from conftest import purge_registered_account

    name = f"sess{uuid.uuid4().hex[:8]}"
    user = create_user(username=name, email=f"{name}@example.test",
                       password="correct horse battery")
    yield {"id": str(user["id"]), "username": name}
    with system_scope("test cleanup: go refresh token"):
        _execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user["id"],))
    purge_registered_account(name)


def _row(raw_token: str) -> dict | None:
    with system_scope("test read: mot dong refresh_tokens"):
        rows = _fetch_all(
            "SELECT token_hash, family_id, revoked_at, replaced_by, "
            "reuse_detected_at, expires_at FROM refresh_tokens "
            "WHERE token_hash = %s",
            (auth._hash_token(raw_token),))
    return rows[0] if rows else None


def _backdate_revocation(raw_token: str, seconds: int) -> None:
    """Đẩy `revoked_at` lùi lại để ra khỏi cửa sổ ân hạn mà không phải chờ thật.

    Sửa mốc trong CSDL chứ không vá `settings.refresh_grace_seconds` về 0: cái
    đang được kiểm là phép SO SÁNH tuổi của lần thu hồi, và một test đặt ân hạn
    về 0 sẽ xanh ngay cả khi phép so sánh đó bị viết sai hoàn toàn.
    """
    with system_scope("test setup: day moc thu hoi lui lai"):
        _execute(
            "UPDATE refresh_tokens SET revoked_at = NOW() - make_interval(secs => %s) "
            "WHERE token_hash = %s",
            (seconds, auth._hash_token(raw_token)))


class TestXoayTokenBinhThuong:
    def test_token_hop_le_xoay_duoc_va_token_cu_chet(self, account):
        raw = auth.create_refresh_token(account["id"])

        result = auth.rotate_refresh_token(raw)
        assert result is not None
        user, new_raw, _fam = result
        assert str(user["id"]) == account["id"]
        assert new_raw != raw

        old = _row(raw)
        assert old["revoked_at"] is not None
        assert old["replaced_by"] == auth._hash_token(new_raw)

    def test_moi_lan_dang_nhap_sinh_mot_HO_moi(self, account):
        """Hai lần đăng nhập là hai thiết bị. Gộp chung họ thì một lần phát hiện
        tái sử dụng trên điện thoại sẽ đá luôn phiên trên máy tính."""
        a = auth.create_refresh_token(account["id"])
        b = auth.create_refresh_token(account["id"])
        assert _row(a)["family_id"] != _row(b)["family_id"]

    def test_xoay_token_GIU_NGUYEN_ho(self, account):
        """Đây là thứ làm cho việc đốt cả họ có nghĩa. Nếu mỗi lần xoay sinh một
        họ mới thì `_burn_token_family` chỉ đốt được đúng một dòng, và cơ chế
        trở thành trang trí."""
        raw = auth.create_refresh_token(account["id"])
        fam = _row(raw)["family_id"]

        _, gen2, _f = auth.rotate_refresh_token(raw)
        _, gen3, _f = auth.rotate_refresh_token(gen2)

        assert _row(gen2)["family_id"] == fam
        assert _row(gen3)["family_id"] == fam

    def test_token_khong_ton_tai_hoac_het_han_thi_tra_None(self, account):
        assert auth.rotate_refresh_token("khong-he-ton-tai") is None
        assert auth.rotate_refresh_token("") is None

        raw = auth.create_refresh_token(account["id"])
        with system_scope("test setup: lam token het han"):
            _execute(
                "UPDATE refresh_tokens SET expires_at = NOW() - interval '1 hour' "
                "WHERE token_hash = %s", (auth._hash_token(raw),))
        assert auth.rotate_refresh_token(raw) is None


class TestCuaSoAnHan:
    """§2 — nhiều tab đua nhau, và vì sao không được coi đó là tấn công."""

    def test_trong_an_han_thi_cap_moi(self, account):
        """Tab A xoay xong, tab B gửi cùng token cũ vài mili-giây sau.

        Trước bản vá, tab B nhận 401 → `clear_auth_cookies()` → và vì cookie
        dùng chung cho cả trình duyệt nên CẢ HAI tab cùng văng ra.
        """
        raw = auth.create_refresh_token(account["id"])
        _, tab_a, _f = auth.rotate_refresh_token(raw)

        tab_b = auth.rotate_refresh_token(raw)  # cùng token cũ, ngay lập tức
        assert tab_b is not None, "tab thua bị đá ra — chính là lỗi đang vá"
        assert tab_b[1] != tab_a

    def test_token_cap_trong_an_han_cung_thuoc_HO_cu(self, account):
        raw = auth.create_refresh_token(account["id"])
        fam = _row(raw)["family_id"]
        auth.rotate_refresh_token(raw)
        _, tab_b, _f = auth.rotate_refresh_token(raw)
        assert _row(tab_b)["family_id"] == fam

    def test_moc_thu_hoi_KHONG_truot_theo_moi_lan_dua(self, account):
        """Bẫy tinh vi nhất của cả bản vá.

        Nếu mỗi lượt đua ghi đè `revoked_at = NOW()`, cửa sổ ân hạn sẽ trượt về
        phía trước mỗi lần token được dùng lại — và một token bị đánh cắp sống
        VĨNH VIỄN chỉ bằng cách gọi /refresh đều đặn 10 giây một lần. Đó là lý do
        câu SQL viết `COALESCE(revoked_at, NOW())` chứ không phải `NOW()`.
        """
        raw = auth.create_refresh_token(account["id"])
        auth.rotate_refresh_token(raw)
        moc_dau = _row(raw)["revoked_at"]

        time.sleep(1.1)
        auth.rotate_refresh_token(raw)

        assert _row(raw)["revoked_at"] == moc_dau, "cửa sổ ân hạn bị trượt"


class TestPhatHienTaiSuDung:
    """§1 — token đã thu hồi quay lại NGOÀI cửa sổ ân hạn."""

    def test_ngoai_an_han_thi_dot_ca_ho(self, account):
        raw = auth.create_refresh_token(account["id"])
        _, gen2, _f = auth.rotate_refresh_token(raw)
        _, gen3, _f = auth.rotate_refresh_token(gen2)

        _backdate_revocation(raw, seconds=120)
        assert auth.rotate_refresh_token(raw) is None

        # Không chỉ token bị dùng lại — token MỚI NHẤT phải chết theo, vì kẻ
        # trộm chính là người đang cầm nó.
        assert _row(raw)["reuse_detected_at"] is not None
        assert _row(gen3)["revoked_at"] is not None
        assert _row(gen3)["reuse_detected_at"] is not None

    def test_ho_da_dot_thi_token_con_han_cung_chet(self, account):
        """Kiểm TRƯỚC hạn dùng, nên một họ đã đốt không hồi sinh bằng đường nào."""
        raw = auth.create_refresh_token(account["id"])
        _, gen2, _f = auth.rotate_refresh_token(raw)
        _backdate_revocation(raw, seconds=120)
        auth.rotate_refresh_token(raw)

        assert _row(gen2)["expires_at"] > datetime.now(timezone.utc)
        assert auth.rotate_refresh_token(gen2) is None

    def test_dot_ho_nay_KHONG_dung_toi_ho_khac(self, account):
        """Đá mọi thiết bị mới là hành vi của reset mật khẩu, không phải của
        phát hiện tái sử dụng. Nhầm hai cái là biến một bản vá thành hồi quy."""
        dien_thoai = auth.create_refresh_token(account["id"])
        may_tinh = auth.create_refresh_token(account["id"])

        auth.rotate_refresh_token(dien_thoai)
        _backdate_revocation(dien_thoai, seconds=120)
        auth.rotate_refresh_token(dien_thoai)

        assert _row(may_tinh)["revoked_at"] is None
        assert auth.rotate_refresh_token(may_tinh) is not None

    def test_phat_hien_tai_su_dung_da_luon_access_token_CUA_HO_DO(self, account):
        """Refresh token bị sao chép nghĩa là phiên đó không còn đáng tin. Access
        token thì stateless nên tự nó không biết điều đó.

        Bản nháp đầu gọi `force_logout_user` ở đây và sai theo HAI cách cùng lúc:
        hàm đó mở một kết nối Postgres thứ hai từ bên trong giao dịch đang giữ
        khoá trên chính những dòng nó muốn sửa (treo vĩnh viễn — test này dựng
        lại được), và nó đá MỌI thiết bị của người dùng, tức trừng phạt nạn nhân.
        """
        from app import activity

        raw = auth.create_refresh_token(account["id"])
        fam_bi_trom = str(_row(raw)["family_id"])
        may_tinh = auth.create_refresh_token(account["id"])
        fam_an_toan = str(_row(may_tinh)["family_id"])

        auth.rotate_refresh_token(raw)
        _backdate_revocation(raw, seconds=120)
        auth.rotate_refresh_token(raw)

        assert activity.is_token_family_denied(fam_bi_trom) is True
        assert activity.is_token_family_denied(fam_an_toan) is False

    def test_phat_hien_tai_su_dung_KHONG_TREO(self, account):
        """Ghim riêng cái deadlock, vì nó im lặng và chỉ lộ ra dưới tải thật.

        `_burn_token_family` chạy BÊN TRONG giao dịch đang giữ khoá hàng trên
        `refresh_tokens`. Bất kỳ ai sau này thêm vào đó một lệnh mở kết nối
        Postgres mới sẽ dựng lại đúng bế tắc cũ — và test này sẽ hết giờ thay vì
        để nó ra tới sản xuất.
        """
        raw = auth.create_refresh_token(account["id"])
        auth.rotate_refresh_token(raw)
        _backdate_revocation(raw, seconds=120)

        bat_dau = time.time()
        assert auth.rotate_refresh_token(raw) is None
        assert time.time() - bat_dau < 5, "phát hiện tái sử dụng bị treo trên khoá"


class TestDangXuatGietDungPhienDo:
    """§3 — và ranh giới với `force_logout_user`, thứ đá MỌI thiết bị."""

    def test_moi_access_token_mang_mot_jti_rieng(self):
        from jose import jwt as jose_jwt

        from app.config import settings

        a = auth.create_access_token({"sub": "u1"})
        b = auth.create_access_token({"sub": "u1"})
        claims_a = jose_jwt.decode(a, settings.secret_key,
                                   algorithms=[settings.algorithm],
                                   options={"verify_aud": False})
        claims_b = jose_jwt.decode(b, settings.secret_key,
                                   algorithms=[settings.algorithm],
                                   options={"verify_aud": False})
        assert claims_a["jti"] and claims_a["jti"] != claims_b["jti"]

    def test_dang_xuat_chan_dung_token_do(self):
        from app import activity

        token = auth.create_access_token({"sub": "u1"})
        assert auth.deny_this_access_token(token) is True

        from jose import jwt as jose_jwt

        from app.config import settings
        jti = jose_jwt.decode(token, settings.secret_key,
                              algorithms=[settings.algorithm],
                              options={"verify_aud": False})["jti"]
        assert activity.is_access_token_denied(jti) is True

    def test_dang_xuat_KHONG_dung_toi_phien_khac(self):
        from app import activity
        from jose import jwt as jose_jwt

        from app.config import settings

        dien_thoai = auth.create_access_token({"sub": "u1"})
        may_tinh = auth.create_access_token({"sub": "u1"})
        auth.deny_this_access_token(dien_thoai)

        jti_may_tinh = jose_jwt.decode(may_tinh, settings.secret_key,
                                       algorithms=[settings.algorithm],
                                       options={"verify_aud": False})["jti"]
        assert activity.is_access_token_denied(jti_may_tinh) is False

    def test_token_gia_KHONG_chan_duoc_gi(self):
        """Nếu đọc claim mà không xác minh chữ ký, bất kỳ ai cũng tự chế được một
        token mang `jti` tuỳ chọn — và chặn `jti` của người khác nếu đoán trúng.

        Đây là lỗi tôi đã viết ra ở bản nháp đầu (`jwt.get_unverified_claims`) và
        bắt được lúc tự soát lại; test này để nó không quay lại.
        """
        from jose import jwt as jose_jwt

        gia = jose_jwt.encode({"sub": "nan-nhan", "jti": "jti-doan-trung"},
                              "khoa-sai-hoan-toan", algorithm="HS256")
        assert auth.deny_this_access_token(gia) is False

    def test_token_cu_khong_co_jti_van_di_qua_duoc(self):
        """Đường chuyển tiếp: token cấp TRƯỚC bản vá không có `jti`. Chúng sống
        nốt tối đa 60 phút — đúng bằng hành vi cũ — rồi tự hết. Không cần cờ cấu
        hình nào, và cũng không được phép 401 hàng loạt lúc triển khai."""
        from jose import jwt as jose_jwt

        from app.config import settings

        cu = jose_jwt.encode(
            {"sub": "u1", "typ": "access",
             "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
            settings.secret_key, algorithm=settings.algorithm)
        assert auth.deny_this_access_token(cu) is False


class TestResetMatKhauDaMoiThietBi:
    def test_reset_dat_moc_thu_hoi_ben(self, account):
        """Khác với đăng xuất: ở đây "đá mọi thiết bị" MỚI là hành vi đúng, vì
        lý do người ta reset thường là "tôi nghi mình bị chiếm tài khoản"."""
        auth.set_password_and_revoke_sessions(account["id"], "mat khau moi hoan toan")

        with system_scope("test read: moc thu hoi"):
            rows = _fetch_all(
                "SELECT sessions_invalid_before FROM users WHERE id = %s",
                (account["id"],))
        assert rows[0]["sessions_invalid_before"] is not None

    def test_token_cap_truoc_moc_bi_tu_choi(self, account):
        from app import activity

        cu = time.time() - 3600
        auth.set_password_and_revoke_sessions(account["id"], "mat khau moi hoan toan")
        with system_scope("test read: moc thu hoi"):
            moc = _fetch_all(
                "SELECT sessions_invalid_before FROM users WHERE id = %s",
                (account["id"],))[0]["sessions_invalid_before"]

        assert activity.token_predates_marker(cu, moc) is True
        assert activity.token_predates_marker(time.time() + 60, moc) is False

    def test_khong_co_moc_thi_khong_tu_choi_ai(self):
        from app import activity

        assert activity.token_predates_marker(time.time(), None) is False


class TestMocThuHoiBen:
    """§5 — trước đây mốc CHỈ nằm ở Redis, nên Redis nấc một cái là mọi lệnh thu
    hồi phiên của quản trị viên bốc hơi, và không có dòng log nào báo."""

    def test_force_logout_ghi_ca_xuong_postgres(self, account):
        from app import activity

        activity.force_logout_user(account["id"], by="test", reason="kiem tra")
        with system_scope("test read: moc thu hoi"):
            rows = _fetch_all(
                "SELECT sessions_invalid_before FROM users WHERE id = %s",
                (account["id"],))
        assert rows[0]["sessions_invalid_before"] is not None

    def test_moc_chi_tien_khong_lui(self, account):
        """`GREATEST`: hai lệnh thu hồi gần nhau không được làm mốc trẻ lại, vì
        như thế là hồi sinh đúng những token vừa bị đá."""
        from app import activity

        activity.force_logout_user(account["id"], by="test")
        with system_scope("test read"):
            moc1 = _fetch_all("SELECT sessions_invalid_before FROM users WHERE id = %s",
                              (account["id"],))[0]["sessions_invalid_before"]

        activity._persist_force_logout_marker(account["id"], time.time() - 7200)
        with system_scope("test read"):
            moc2 = _fetch_all("SELECT sessions_invalid_before FROM users WHERE id = %s",
                              (account["id"],))[0]["sessions_invalid_before"]

        assert moc2 == moc1


class TestDonBangRefreshTokens:
    """§4 — bảng chỉ lớn lên nếu không ai dọn."""

    def test_don_token_het_han_qua_lau(self, account):
        raw = auth.create_refresh_token(account["id"])
        with system_scope("test setup: token het han tu 30 ngay truoc"):
            _execute(
                "UPDATE refresh_tokens SET expires_at = NOW() - interval '30 days' "
                "WHERE token_hash = %s", (auth._hash_token(raw),))

        auth.purge_expired_refresh_tokens(retain_days=7)
        assert _row(raw) is None

    def test_KHONG_xoa_token_con_han(self, account):
        """Cái phải sợ ở một câu DELETE định kỳ không phải là nó xoá thiếu."""
        raw = auth.create_refresh_token(account["id"])
        auth.purge_expired_refresh_tokens(retain_days=7)
        assert _row(raw) is not None

    def test_KHONG_xoa_token_vua_het_han_trong_cua_so_giu_lai(self, account):
        """Chuỗi `replaced_by` là thứ duy nhất dựng lại được đường xoay token khi
        điều tra một vụ tái sử dụng. Xoá sạch tức thì là vứt bằng chứng của chính
        cơ chế vừa dựng."""
        raw = auth.create_refresh_token(account["id"])
        with system_scope("test setup: het han 2 ngay truoc"):
            _execute(
                "UPDATE refresh_tokens SET expires_at = NOW() - interval '2 days' "
                "WHERE token_hash = %s", (auth._hash_token(raw),))

        auth.purge_expired_refresh_tokens(retain_days=7)
        assert _row(raw) is not None


class TestKhongRoBamMatKhau:
    """`/auth/login` bỏ `response_model=UserOut` để trả được HAI hình dạng — hồ sơ
    người dùng, hoặc vé bước hai. Việc bỏ đó đã vô tình gỡ luôn bộ lọc duy nhất
    ngăn `password_hash` đi ra ngoài.

    Lỗi sống vài phút và do tự soát lại mà thấy, không phải do test bắt. Test này
    tồn tại để lần sau nó bị bắt.
    """

    def test_ho_so_tra_ve_KHONG_mang_bam_mat_khau(self, account):
        from app.routers.auth import _public_user

        day_du = auth._fetch_user_by_id(account["id"])
        assert "password_hash" in day_du, (
            "test này chỉ có nghĩa nếu hồ sơ nội bộ THẬT SỰ mang cột đó")

        assert "password_hash" not in _public_user(day_du)

    def test_bo_loc_la_danh_sach_CHO_PHEP_khong_phai_danh_sach_cam(self):
        """Danh sách cấm sẽ rò mọi cột nhạy cảm thêm vào sau này. `UserOut` liệt
        kê tường minh những gì được ra, nên cột mới mặc định KHÔNG ra."""
        from app.routers.auth import _public_user

        ra = _public_user({
            "id": "u-1", "username": "a", "email": "a@b.vn",
            "is_active": True, "is_admin": False, "created_at": None,
            "tenant_id": "default",
            "password_hash": "$2b$12$bimat",
            "sessions_invalid_before": None,
            "mot_cot_nhay_cam_them_sau_nay": "khong duoc ra",
        })
        assert "mot_cot_nhay_cam_them_sau_nay" not in ra
        assert "sessions_invalid_before" not in ra
        assert ra["username"] == "a"
