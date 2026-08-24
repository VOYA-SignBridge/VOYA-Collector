"""Cong dinh dang o `/upload/video`.

Vi sao co tep nay: truoc ban vá nay, mot tep BAT KY di qua `/upload/video` deu
duoc nhan, va — nghiem trong hon — `get_or_register_class` chay TRUOC moi phep
kiem, nen mot lan tai len that bai van de lai mot lop tu vung phai don tay.

Hai nhom test duoi day canh hai dieu khac nhau:
  * `_looks_like_video` nhan dung / tu choi dung theo CHU KY container;
  * `_peek_head` khong tieu thu luong — neu no an mat byte dau thi tep luu
    xuong dia se cut dau, mot loi im lang va rat kho truy.
"""

import io

import pytest

from app.routers.upload import _looks_like_video, _peek_head


def _pad(head: bytes) -> bytes:
    """Chu ky + phan dem cho du 12 byte — nguong toi thieu cua ham."""
    return head + b"\x00" * max(0, 16 - len(head))


class TestNhanDungDinhDangVideo:
    @pytest.mark.parametrize(
        "head, ten",
        [
            (b"\x00\x00\x00\x20ftypisom", "MP4/isom"),
            (b"\x00\x00\x00\x14ftypqt  ", "MOV/quicktime"),
            (b"\x1a\x45\xdf\xa3\x00\x00\x00\x00\x00\x00\x00\x00", "WebM/MKV (EBML)"),
            (b"RIFF\x00\x00\x00\x00AVI LIST", "AVI"),
            (b"FLV\x01\x05\x00\x00\x00\x09\x00\x00\x00", "FLV"),
            (b"\x00\x00\x01\xba\x21\x00\x01\x00\x01\x80\x00\x00", "MPEG-PS"),
        ],
    )
    def test_chap_nhan_container_hop_le(self, head, ten):
        assert _looks_like_video(_pad(head)) is True, ten


class TestTuChoiThuKhongPhaiVideo:
    @pytest.mark.parametrize(
        "head, ten",
        [
            (b"%PDF-1.7\n%\xe2\xe3\xcf\xd3", "PDF"),
            (b"PK\x03\x04\x14\x00\x00\x00\x08\x00\x00\x00", "ZIP/Office"),
            (b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0d", "PNG"),
            (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01", "JPEG"),
            (b"#!/bin/sh\necho hi\n", "shell script"),
            (b"class_uid,slug,label\n1,a,b\n", "CSV"),
        ],
    )
    def test_tu_choi_tep_khong_phai_video(self, head, ten):
        assert _looks_like_video(_pad(head)) is False, ten

    def test_tep_qua_ngan_bi_tu_choi(self):
        assert _looks_like_video(b"ftyp") is False
        assert _looks_like_video(b"") is False

    def test_mpeg_ts_khong_duoc_nhan(self):
        """0x47 la mot byte — nhan no se cho lot moi tep bat dau bang chu 'G'.

        Test nay ghim mot QUYET DINH, khong phai mot han che ky thuat: neu ai do
        them TS vao danh sach, cong se ngung chan duoc `b"Giao trinh..."`.
        """
        assert _looks_like_video(_pad(b"G" + b"\x00" * 11)) is False
        assert _looks_like_video(_pad(b"Giao trinh VSL")) is False


class TestPeekKhongTieuThuLuong:
    def test_con_tro_tro_ve_cho_cu(self):
        raw = b"\x00\x00\x00\x20ftypisom" + b"REST-OF-FILE" * 10
        buf = io.BytesIO(raw)
        head = _peek_head(buf)
        assert head == raw[:16]
        assert buf.tell() == 0, "peek da an mat byte dau — tep luu xuong se cut dau"
        assert buf.read() == raw, "noi dung doc lai phai nguyen ven"

    def test_peek_giu_nguyen_vi_tri_khac_khong(self):
        buf = io.BytesIO(b"0123456789abcdefghij")
        buf.seek(4)
        assert _peek_head(buf, 4) == b"4567"
        assert buf.tell() == 4
