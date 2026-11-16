"""Ảnh đại diện TẢI LÊN: chuẩn hoá, lưu, phát lại.

Ảnh người dùng gửi là đầu vào không tin được, và người dùng ở đây phần lớn là học
sinh. Ba thứ phải đúng: không lưu bản gốc (EXIF có toạ độ GPS), không nhận tệp
không phải ảnh, và không ngốn bộ nhớ vì một tệp khai báo kích thước khổng lồ.
"""

from __future__ import annotations

import io
import struct
import uuid
import zlib

import pytest
from PIL import Image

from app.modules.identity import _web_compat as auth
from app.modules.identity import account_workflows as wf
from app.modules.identity import avatar_image as ai
from app.modules.saas.tenancy import DEFAULT_TENANT_ID
from app.modules.saas.tenant_context import tenant_scope


def _img(fmt: str, size=(640, 360), mode="RGB", color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, format=fmt)
    return buf.getvalue()


def _png_claiming(width: int, height: int) -> bytes:
    """Tệp PNG nhỏ xíu khai báo kích thước khổng lồ — mẫu "bom giải nén"."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(b"\x00" * 10)) + chunk(b"IEND", b""))


class TestNormalise:
    @pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
    def test_moi_dinh_dang_nhan_vao_deu_ra_webp_vuong_256(self, fmt):
        out = Image.open(io.BytesIO(ai.normalise(_img(fmt))))
        assert out.format == "WEBP"
        assert out.size == (ai.SIDE, ai.SIDE)

    def test_anh_nho_va_lech_khung_van_ra_dung_cang(self):
        for size in [(10, 10), (1000, 100), (100, 1000)]:
            out = Image.open(io.BytesIO(ai.normalise(_img("PNG", size=size))))
            assert out.size == (ai.SIDE, ai.SIDE)

    def test_nen_trong_suot_thanh_trang_chu_khong_phai_den(self):
        out = Image.open(io.BytesIO(ai.normalise(_img("PNG", mode="RGBA", color=(0, 0, 0, 0)))))
        r, g, b = out.convert("RGB").getpixel((5, 5))
        assert min(r, g, b) > 240

    def test_exif_co_toa_do_khong_duoc_giu_lai(self):
        """Ảnh chụp từ điện thoại mang vị trí nhà người dùng."""
        exif = Image.Exif()
        exif[0x010F] = "Camera"
        exif[0x8825] = {1: "N"}  # GPS IFD
        buf = io.BytesIO()
        Image.new("RGB", (100, 100), "blue").save(buf, "JPEG", exif=exif)
        assert Image.open(io.BytesIO(buf.getvalue())).getexif(), "đầu vào phải thật sự có EXIF"
        assert not Image.open(io.BytesIO(ai.normalise(buf.getvalue()))).getexif()

    @pytest.mark.parametrize("name, data, code", [
        ("svg", b"<svg xmlns='http://www.w3.org/2000/svg'><script>1</script></svg>", "invalid"),
        ("html", b"<html><script>alert(1)</script></html>", "invalid"),
        ("rong", b"", "invalid"),
        ("rac", b"\x00\x01\x02" * 100, "invalid"),
    ])
    def test_tep_khong_phai_anh_bi_tu_choi(self, name, data, code):
        with pytest.raises(ai.AvatarImageError) as exc:
            ai.normalise(data)
        assert exc.value.code == code

    def test_gif_la_anh_that_nhung_khong_nhan(self):
        with pytest.raises(ai.AvatarImageError) as exc:
            ai.normalise(_img("GIF"))
        assert exc.value.code == "unsupported"

    def test_qua_2mb_bi_tu_choi_truoc_khi_giai_ma(self):
        with pytest.raises(ai.AvatarImageError) as exc:
            ai.normalise(b"x" * (ai.MAX_UPLOAD_BYTES + 1))
        assert exc.value.code == "too_large"

    def test_tep_khai_bao_kich_thuoc_khong_lo_bi_tu_choi_chu_khong_ngon_bo_nho(self):
        with pytest.raises(ai.AvatarImageError):
            ai.normalise(_png_claiming(40_000, 40_000))


@pytest.fixture
def account():
    from conftest import purge_registered_account

    name = f"avu{uuid.uuid4().hex[:8]}"
    user = auth.create_user(username=name, email=f"{name}@example.test",
                            password="correct horse battery")
    yield {"id": str(user["id"]), "username": name}
    purge_registered_account(name)


@pytest.fixture
def scope():
    with tenant_scope(DEFAULT_TENANT_ID):
        yield


class TestStoreAndServe:
    def test_tai_len_roi_doc_lai_dung_anh_da_chuan_hoa(self, account, scope):
        key = wf.store_uploaded_avatar(account["id"], _img("JPEG"))
        assert key.startswith(wf.UPLOADED_PREFIX)
        assert auth._fetch_user_by_id(account["id"])["avatar_key"] == key
        stored = wf.read_avatar(account["id"])
        assert Image.open(io.BytesIO(stored)).size == (ai.SIDE, ai.SIDE)

    def test_chua_tai_len_thi_khong_co_anh(self, account, scope):
        assert wf.read_avatar(account["id"]) is None

    def test_khoa_doi_moi_lan_tai_len(self, account, scope, monkeypatch):
        """Đường dẫn ảnh phải đổi để trình duyệt không giữ ảnh cũ."""
        times = iter([1_700_000_000, 1_700_000_001])
        monkeypatch.setattr(wf.time, "time", lambda: next(times))
        first = wf.store_uploaded_avatar(account["id"], _img("PNG"))
        second = wf.store_uploaded_avatar(account["id"], _img("PNG"))
        assert first != second

    def test_chon_mau_thi_xoa_anh_da_tai_len(self, account, scope):
        wf.store_uploaded_avatar(account["id"], _img("PNG"))
        wf.set_avatar(account["id"], "hand")
        assert wf.read_avatar(account["id"]) is None
        assert auth._fetch_user_by_id(account["id"])["avatar_key"] == "hand"

    def test_bo_chon_cung_xoa_anh_da_tai_len(self, account, scope):
        wf.store_uploaded_avatar(account["id"], _img("PNG"))
        wf.set_avatar(account["id"], None)
        assert wf.read_avatar(account["id"]) is None

    def test_khong_the_tu_cap_khoa_anh_tai_len_bang_cach_chon_mau(self, account, scope):
        """`u-...` chỉ do `store_uploaded_avatar` cấp; gửi tay sẽ trỏ tới ảnh không có."""
        with pytest.raises(ValueError):
            wf.set_avatar(account["id"], "u-1700000000")

    def test_anh_gui_len_khong_bao_gio_nam_trong_ho_so(self, account, scope):
        wf.store_uploaded_avatar(account["id"], _img("PNG"))
        user = auth._fetch_user_by_id(account["id"])
        assert "avatar_image" not in user
        from app.routers import auth as auth_router

        assert "avatar_image" not in auth_router._public_user(user)
