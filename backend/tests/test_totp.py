"""TOTP đối chiếu với vector thử công bố trong RFC, không phải với chính nó.

`app/totp.py` là mã tự viết thay cho `pyotp` (lý do ở docstring của nó). Một bản
tự viết chỉ đáng tin nếu nó khớp với một nguồn ĐỘC LẬP — nếu không, test chỉ
chứng minh rằng mã nhất quán với chính mình, kể cả khi cả hai cùng sai.

Nguồn: RFC 4226 Phụ lục D (HOTP) và RFC 6238 Phụ lục B (TOTP). Đây là những con
số mà mọi thư viện TOTP trên thế giới đều phải khớp.
"""

from __future__ import annotations

import pytest

from app import totp

#: RFC 4226 Phụ lục D. Bí mật là ASCII "12345678901234567890".
RFC4226_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
RFC4226_EXPECTED = [
    "755224", "287082", "359152", "969429", "338314",
    "254676", "287922", "162583", "399871", "520489",
]

#: RFC 6238 Phụ lục B, các dòng SHA-1. `T` là giây kể từ epoch.
RFC6238_SHA1 = [
    (59, "94287082"),
    (1111111109, "07081804"),
    (1111111111, "14050471"),
    (1234567890, "89005924"),
    (2000000000, "69279037"),
    (20000000000, "65353130"),
]


class TestVectorRFC:
    @pytest.mark.parametrize("counter,expected", enumerate(RFC4226_EXPECTED))
    def test_hotp_khop_rfc4226(self, counter, expected):
        assert totp.hotp(RFC4226_SECRET, counter) == expected

    @pytest.mark.parametrize("t,expected8", RFC6238_SHA1)
    def test_totp_khop_rfc6238(self, t, expected8):
        """RFC in mã 8 chữ số; hệ thống dùng 6, nên so 6 chữ số CUỐI.

        Cắt đuôi là đúng chứ không phải xấp xỉ: mã n chữ số là `code % 10**n`,
        nên mã 6 chữ số luôn bằng 6 chữ số cuối của mã 8 chữ số cùng thời điểm.
        """
        assert totp.totp(RFC4226_SECRET, at=t) == expected8[-6:]
        assert totp.totp(RFC4226_SECRET, at=t, digits=8) == expected8

    def test_cat_bit_dong_bo_bit_dau(self):
        """Quên `& 0x7fffffff` làm khoảng một nửa số mã sai — và sai không theo
        quy luật nhìn thấy được, nên nó lọt qua một test viết hời hợt.

        Bộ 10 vector RFC 4226 ở trên có chứa trường hợp bit cao bằng 1, nên
        chúng đã bắt được lỗi này. Test này chỉ nêu tên nó cho người đọc sau.
        """
        assert all(len(c) == 6 and c.isdigit()
                   for c in (totp.hotp(RFC4226_SECRET, i) for i in range(200)))


class TestKiemMa:
    def test_ma_dung_thi_tra_ve_BUOC(self):
        step = totp.current_step()
        ma = totp.totp(RFC4226_SECRET)
        assert totp.verify(RFC4226_SECRET, ma) == step

    def test_ma_sai_tra_None(self):
        assert totp.verify(RFC4226_SECRET, "000000", at=59) is None

    @pytest.mark.parametrize("rac", ["", "12345", "1234567", "abcdef", "12 34 56", None])
    def test_dinh_dang_sai_bi_tu_choi_khong_ne(self, rac):
        assert totp.verify(RFC4226_SECRET, rac) is None

    def test_cua_so_lech_dong_ho(self):
        """±1 bước. Điện thoại lệch vài giây là chuyện thường; từ chối oan vì
        chuyện đó biến 2FA thành thứ người dùng xin tắt đi."""
        moc = 1111111111
        assert totp.verify(RFC4226_SECRET, totp.totp(RFC4226_SECRET, at=moc - 30),
                           at=moc) is not None
        assert totp.verify(RFC4226_SECRET, totp.totp(RFC4226_SECRET, at=moc + 30),
                           at=moc) is not None

    def test_ngoai_cua_so_thi_tu_choi(self):
        moc = 1111111111
        assert totp.verify(RFC4226_SECRET, totp.totp(RFC4226_SECRET, at=moc - 90),
                           at=moc) is None

    def test_window_0_chi_nhan_dung_buoc_hien_tai(self):
        moc = 1111111111
        assert totp.verify(RFC4226_SECRET, totp.totp(RFC4226_SECRET, at=moc - 30),
                           at=moc, window=0) is None


class TestBiMatVaURI:
    def test_bi_mat_moi_khong_trung_nhau(self):
        assert len({totp.new_secret() for _ in range(200)}) == 200

    def test_bi_mat_dai_160_bit(self):
        """RFC 4226 §4 R6 đòi tối thiểu 128 bit và khuyến nghị 160."""
        import base64
        s = totp.new_secret()
        raw = base64.b32decode(s + "=" * (-len(s) % 8))
        assert len(raw) == 20

    def test_bi_mat_moi_dung_duoc_ngay(self):
        s = totp.new_secret()
        assert totp.verify(s, totp.totp(s)) is not None

    def test_chap_nhan_bi_mat_nguoi_dung_chep_kem_dau_cach(self):
        """Giao diện hiển thị bí mật theo nhóm 4 ký tự cho dễ gõ, nên chuỗi
        người dùng dán vào gần như luôn có dấu cách."""
        s = totp.new_secret()
        nhom = " ".join(s[i:i + 4] for i in range(0, len(s), 4))
        assert totp.totp(nhom) == totp.totp(s)

    def test_uri_mang_du_thong_tin_ung_dung_can(self):
        uri = totp.provisioning_uri("ABCDEFGHIJKLMNOP", "an@ctu.edu.vn", "CTU.SignBridge")
        assert uri.startswith("otpauth://totp/")
        assert "secret=ABCDEFGHIJKLMNOP" in uri
        assert "issuer=CTU.SignBridge" in uri
        assert "period=30" in uri and "digits=6" in uri

    def test_uri_ma_hoa_ky_tu_dac_biet_trong_nhan(self):
        """`@` và dấu cách trong nhãn phải được mã hoá, không thì một số ứng dụng
        cắt nhãn ở đúng ký tự đó."""
        uri = totp.provisioning_uri("AAAA", "a b@c.vn", "CTU SignBridge")
        assert " " not in uri
        assert "%40" in uri
