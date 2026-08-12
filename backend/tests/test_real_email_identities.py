"""Đường đi của email, kiểm bằng BA ĐỊA CHỈ THẬT chứ không phải `@example.test`.

Mỗi test ở đây tương ứng một loại lỗi đã hoặc có thể xảy ra với địa chỉ thật,
không phải để chạy cho có:

  - danh tính trùng vì khác chữ hoa/thường  → `TestMotDiaChiMotTaiKhoan`
  - tên miền bốn cấp làm vỡ kiểm định       → `TestTenMienBonCap`
  - mã bí mật lọt vào log                   → `TestKhongLoMa`
  - mã của người này dùng được cho người kia → `TestMaKhongDungCheo`
  - phản hồi làm lộ địa chỉ nào có đăng ký  → `TestKhongLoDanhSach`

Ba địa chỉ và hàng rào chống ghi nhầm vào cơ sở dữ liệu sản xuất nằm ở
`tests/accounts.py`. Đọc phần đầu file đó trước khi thêm test mới ở đây.
"""

from __future__ import annotations

import uuid

import pytest

from accounts import (
    ALL_EMAILS,
    EMAIL_GMAIL,
    EMAIL_OWNER,
    EMAIL_UNIVERSITY,
    PASSWORD,
    refuse_to_touch_production,
    username_for,
)
from app.storage import metadata_db as db
from app.tenant_context import system_scope


# --------------------------------------------------------------------------- hạ tầng

@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    """Lược đồ phải có mặt trước khi khẳng định về ràng buộc của nó.

    Thiếu fixture này, `test_co_so_du_lieu_tu_tu_choi_dia_chi_viet_hoa` chạy
    trên một cơ sở dữ liệu chưa có `users_email_lower`, câu INSERT chữ hoa
    THÀNH CÔNG, và hàng đó nằm lại — test vừa xanh sai vừa để lại rác.
    """
    db.ensure_tables()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from conftest import LoopbackPeer, fresh_client_ip
    from app.main import app

    inner = TestClient(LoopbackPeer(app))

    class _MoiLuotMotIp:
        """Mỗi lượt gọi mang một IP khác nhau.

        Không có nó, `test_login_rate_limit` và các test ở đây dùng chung một
        thùng đếm và test sau bị 429 vì test trước — đỏ ngẫu nhiên theo thứ tự
        chạy, loại đỏ tốn nhiều giờ nhất để hiểu.
        """

        def __getattr__(self, verb):
            def call(url, **kwargs):
                headers = {**kwargs.pop("headers", {}),
                           "X-Forwarded-For": fresh_client_ip()}
                return getattr(inner, verb)(url, headers=headers, **kwargs)
            return call

    return _MoiLuotMotIp()


def _xoa_tai_khoan(user_id: str) -> None:
    """Dọn một tài khoản, chịu được việc một bảng con chưa tồn tại.

    Từng câu trong `try` riêng, và `users` xoá SAU CÙNG dù các câu trước hỏng
    hay không. Mẫu này không phải cẩn thận thừa: một fixture gọi bốn `_execute`
    liên tiếp trong một khối đã để lại 10 tài khoản test trong cơ sở dữ liệu
    thật vào 2026-08-08, vì câu thứ ba đụng bảng chưa tồn tại và câu xoá `users`
    không bao giờ chạy tới.
    """
    con = (
        "DELETE FROM user_consents WHERE user_id = %s",
        "DELETE FROM verification_codes WHERE user_id = %s",
        "DELETE FROM password_reset_tokens WHERE user_id = %s",
        "DELETE FROM refresh_tokens WHERE user_id = %s",
        "DELETE FROM tenant_members WHERE user_id = %s",
    )
    with system_scope("test cleanup: tai khoan email that"):
        for sql in con:
            try:
                db._execute(sql, (user_id,))
            except Exception:
                pass
        db._execute("DELETE FROM users WHERE id = %s", (user_id,))


@pytest.fixture
def tai_khoan_that(request):
    """Tài khoản mang một trong ba địa chỉ thật, dọn sạch sau khi xong.

    Chỉ chạy trên bản sao — xem `refuse_to_touch_production()`. Nếu địa chỉ đã
    có sẵn trong bản sao (nó có, vì bản sao chép từ dữ liệu thật) thì dùng lại
    hàng đó và KHÔNG xoá nó đi lúc kết thúc: xoá một hàng mình không tạo ra là
    phá dữ liệu của người khác, kể cả trên bản sao.
    """
    refuse_to_touch_production()
    from app.auth import create_user

    email = request.param
    with system_scope("test: tim tai khoan san co"):
        san_co = db._fetch_all("SELECT id FROM users WHERE lower(email) = %s",
                               (email.lower(),))
    if san_co:
        yield {"id": str(san_co[0]["id"]), "email": email}, False
        return

    user = create_user(username=f"{username_for(email)}_{uuid.uuid4().hex[:6]}",
                       email=email, password=PASSWORD)
    try:
        yield user, True
    finally:
        _xoa_tai_khoan(user["id"])


# ------------------------------------------------- một địa chỉ = một tài khoản

class TestMotDiaChiMotTaiKhoan:
    """Chữ hoa/thường không được đẻ ra tài khoản thứ hai.

    Hậu quả nếu sai không phải phiền phức mà là hai danh tính cho một người:
    `_fetch_user_by_login` tra bằng `lower(username) = ... OR lower(email) =
    ...` kèm `LIMIT 1` mà KHÔNG có ORDER BY, nên với hai hàng khớp thì hàng nào
    được trả về là do Postgres quyết định — mật khẩu, quyền và dữ liệu của
    người dùng phụ thuộc vào một thứ không xác định.
    """

    @pytest.mark.parametrize("email", ALL_EMAILS)
    def test_tra_cuu_khong_phan_biet_hoa_thuong(self, email):
        """Đăng nhập bằng ĐỊA CHỈ VIẾT HOA phải ra đúng tài khoản đó."""
        from app.auth import _fetch_user_by_login

        thuong = _fetch_user_by_login(email)
        hoa = _fetch_user_by_login(email.upper())
        if thuong is None:
            pytest.skip(f"{email} chưa có tài khoản trong cơ sở dữ liệu này")
        assert hoa is not None, "viết hoa địa chỉ làm mất tài khoản"
        assert hoa["id"] == thuong["id"]

    def test_co_so_du_lieu_tu_tu_choi_dia_chi_viet_hoa(self, rollback_cursor):
        """Bất biến phải nằm ở CƠ SỞ DỮ LIỆU, không chỉ ở một nhánh mã.

        `create_user` có hạ chữ thường, nên đường đăng ký thì an toàn. Nhưng đó
        là MỘT đường: đồng bộ CSV, công cụ quản trị, hay một endpoint viết sau
        đều ghi thẳng vào `users`. Chính kho mã này đã kết luận như vậy cho
        `tenant_invitations` và đặt `CHECK (email = lower(email))` ở đó; bảng
        `users` quan trọng hơn mà lại yếu hơn.

        Lần chạy đầu tiên của test này ĐỎ, và nó đỏ đúng cách: ràng buộc chưa
        tồn tại, câu INSERT chữ hoa thành công, và
        `MAINHATMINH1004@GMAIL.COM` xuất hiện bên cạnh
        `mainhatminh1004@gmail.com` — hai tài khoản cho một người, đúng thứ
        đang được mô tả.
        """
        import psycopg2

        with pytest.raises(psycopg2.errors.CheckViolation):
            rollback_cursor.execute(
                "INSERT INTO users(id, username, email, password_hash, tenant_id) "
                "VALUES(%s, %s, %s, 'x', 'default')",
                (str(uuid.uuid4()), f"case{uuid.uuid4().hex[:8]}",
                 EMAIL_GMAIL.upper()))

    def test_du_lieu_dang_co_thoa_bat_bien(self):
        """Ràng buộc trên chỉ có nghĩa nếu dữ liệu hiện tại đã sạch."""
        with system_scope("test: kiem du lieu"):
            ban = db._fetch_all(
                "SELECT email FROM users WHERE email <> lower(email)")
        assert ban == [], f"có tài khoản email chưa chữ thường: {ban}"


# --------------------------------------------------------- tên miền bốn cấp

class TestTenMienBonCap:
    """`minhb2203567@student.ctu.edu.vn` — bốn cấp tên miền.

    Đây là địa chỉ hay làm vỡ nhất trong ba, vì regex kiểm định địa chỉ viết
    vội thường chỉ chấp nhận `ten@mien.tld` hoặc giới hạn phần đuôi 2–3 ký tự.
    Cả trường dùng tên miền này, nên hỏng ở đây là hỏng với toàn bộ người dùng
    thật của hệ thống.
    """

    def test_pydantic_chap_nhan(self):
        from app.routers.auth import RegisterRequest

        req = RegisterRequest(username="minhb2203567", email=EMAIL_UNIVERSITY,
                              password=PASSWORD)
        assert req.email == EMAIL_UNIVERSITY

    def test_khong_bi_cat_khi_chuan_hoa(self):
        from app.auth import _normalize_login

        assert _normalize_login(f"  {EMAIL_UNIVERSITY.upper()}  ") == EMAIL_UNIVERSITY

    def test_dung_duoc_lam_dich_cua_ma_xac_minh(self):
        """`verification_codes.destination` là nơi địa chỉ được lưu nguyên văn;
        một chỗ cắt chuỗi ở đây sẽ khiến mã gửi đi không bao giờ khớp lại."""
        from app.tokens import hash_code

        digest = hash_code("123456", purpose="verify_email",
                           subject=EMAIL_UNIVERSITY)
        assert digest == hash_code("123456", purpose="verify_email",
                                   subject=EMAIL_UNIVERSITY)
        assert digest != hash_code("123456", purpose="verify_email",
                                   subject=EMAIL_GMAIL)


# ------------------------------------------------------------- không lộ mã

class TestKhongLoMa:
    """Quy tắc của chủ dự án, không có ngoại lệ: log không được chứa mã.

    Chỗ nguy hiểm cụ thể: khi `SMTP_HOST` trống, `email_service` từng ghi cả
    nội dung thư ra log để tiện phát triển — và nội dung thư chứa mã OTP. Trên
    máy triển khai thật, log đi vào Loki và ở lại đó.
    """

    @pytest.mark.parametrize("email", ALL_EMAILS)
    def test_gui_ma_khong_cau_hinh_smtp_thi_bao_loi_chu_khong_log_ma(
            self, email, monkeypatch, caplog):
        import logging

        from app import email_service as es

        monkeypatch.setattr(es.settings, "smtp_host", "")
        ma = "424242"
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(es.EmailNotConfigured):
                es.send_verification_code_email(email, ma, purpose="verify_email")
        assert ma not in caplog.text, "mã OTP lọt vào log"

    @pytest.mark.parametrize("email", ALL_EMAILS)
    def test_ban_bam_khong_the_dao_nguoc_ve_ma(self, email):
        """Sáu chữ số chỉ có một triệu khả năng: băm trần là duyệt cạn trong
        một giây. Bảng chỉ được giữ HMAC khoá bằng pepper ngoài cơ sở dữ liệu.
        """
        from app.tokens import hash_code

        moi_kha_nang = {
            hash_code(f"{n:06d}", purpose="verify_email", subject=email)
            for n in range(0, 1000)
        }
        assert len(moi_kha_nang) == 1000, "hai mã khác nhau cho cùng một băm"
        that = hash_code("000123", purpose="verify_email", subject=email)
        assert that not in {
            __import__("hashlib").sha256(f"{n:06d}".encode()).hexdigest()
            for n in range(0, 1000)
        }, "băm trùng với SHA-256 trần — pepper không được dùng"


# ---------------------------------------------------- mã không dùng chéo được

class TestMaKhongDungCheo:
    """Mã cấp cho địa chỉ này không được dùng cho địa chỉ kia.

    Đây là lý do `verification_codes` có cột `destination`. Không có ràng buộc
    này, một người có ba địa chỉ — đúng tình huống của chủ dự án — có thể lấy
    mã gửi tới hộp thư mình kiểm soát rồi dùng nó để xác minh một địa chỉ khác.
    """

    def test_ma_gan_chat_voi_dia_chi_nhan(self):
        from app.tokens import hash_code

        ma = "135790"
        cho_gmail = hash_code(ma, purpose="verify_email", subject=EMAIL_GMAIL)
        cho_truong = hash_code(ma, purpose="verify_email", subject=EMAIL_UNIVERSITY)
        cho_chu = hash_code(ma, purpose="verify_email", subject=EMAIL_OWNER)
        assert len({cho_gmail, cho_truong, cho_chu}) == 3

    def test_ma_gan_chat_voi_muc_dich(self):
        """Mã xác minh email không được dùng làm mã đặt lại mật khẩu."""
        from app.tokens import hash_code

        ma = "135790"
        assert (hash_code(ma, purpose="verify_email", subject=EMAIL_OWNER)
                != hash_code(ma, purpose="reset_password", subject=EMAIL_OWNER))

    @pytest.mark.parametrize("tai_khoan_that", [EMAIL_OWNER], indirect=True)
    def test_chi_mot_thu_thach_con_hieu_luc_moi_muc_dich(self, tai_khoan_that):
        """Xin mã qua email rồi đổi sang kênh khác phải HUỶ mã cũ.

        Không có ràng buộc này, mã đầu tiên vẫn nằm trong hộp thư và vẫn mở
        được tài khoản — đúng tình huống mà việc đổi kênh nhằm chấm dứt.
        """
        import psycopg2

        user, _ = tai_khoan_that
        uid = user["id"]
        with system_scope("test: thu thach trung"):
            try:
                db._execute(
                    "INSERT INTO verification_codes"
                    "(challenge_id, user_id, purpose, channel, destination, "
                    " code_hash, expires_at) VALUES(%s, %s, 'verify_email', "
                    "'email', %s, 'h1', NOW() + interval '10 min')",
                    (str(uuid.uuid4()), uid, EMAIL_OWNER))
                with pytest.raises(psycopg2.errors.UniqueViolation):
                    db._execute(
                        "INSERT INTO verification_codes"
                        "(challenge_id, user_id, purpose, channel, destination, "
                        " code_hash, expires_at) VALUES(%s, %s, 'verify_email', "
                        "'sms', %s, 'h2', NOW() + interval '10 min')",
                        (str(uuid.uuid4()), uid, EMAIL_OWNER))
            finally:
                db._execute("DELETE FROM verification_codes WHERE user_id = %s",
                            (uid,))


# ------------------------------------------------------- không lộ danh sách

class TestKhongLoDanhSach:
    """Phản hồi không được tiết lộ địa chỉ nào đã đăng ký.

    Ba địa chỉ này CÓ đăng ký. Nếu `/auth/forgot-password` trả lời khác nhau
    cho địa chỉ có và không có, bất kỳ ai cũng dò được danh sách người dùng —
    và với một nền tảng phục vụ giáo dục đặc biệt, danh sách đó tự nó là dữ
    liệu nhạy cảm.
    """

    @pytest.mark.parametrize("email", ALL_EMAILS)
    def test_quen_mat_khau_tra_loi_giong_nhau_cho_dia_chi_co_va_khong(
            self, email, client):
        khong_co = f"khong-ton-tai-{uuid.uuid4().hex[:10]}@gmail.com"
        a = client.post("/api/v1/auth/forgot-password", json={"email": email})
        b = client.post("/api/v1/auth/forgot-password", json={"email": khong_co})
        assert a.status_code == b.status_code, (
            "mã trạng thái khác nhau giữa địa chỉ có và không có đăng ký"
        )
        assert a.json() == b.json(), "nội dung phản hồi làm lộ địa chỉ nào tồn tại"
