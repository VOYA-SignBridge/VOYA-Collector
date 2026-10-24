"""Cong dinh dang o `/upload/video`.

Vi sao co tep nay: truoc ban vá nay, mot tep BAT KY di qua `/upload/video` deu
duoc nhan, va — nghiem trong hon — `get_or_register_class` chay TRUOC moi phep
kiem, nen mot lan tai len that bai van de lai mot lop tu vung phai don tay.

Hai nhom test duoi day canh hai dieu khac nhau:
  * `looks_like_video` nhan dung / tu choi dung theo CHU KY container;
  * `peek_head` khong tieu thu luong — neu no an mat byte dau thi tep luu
    xuong dia se cut dau, mot loi im lang va rat kho truy.
"""

import asyncio
import inspect
import io

import pytest
from fastapi import UploadFile

from app.modules.saas.tenant_context import tenant_scope
from app.modules.dataset import raw_video_upload_service as upload_service
from app.routers import upload as upload_router
from app.modules.dataset.raw_video_upload_service import looks_like_video, peek_head


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
        assert looks_like_video(_pad(head)) is True, ten


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
        assert looks_like_video(_pad(head)) is False, ten

    def test_tep_qua_ngan_bi_tu_choi(self):
        assert looks_like_video(b"ftyp") is False
        assert looks_like_video(b"") is False

    def test_mpeg_ts_khong_duoc_nhan(self):
        """0x47 la mot byte — nhan no se cho lot moi tep bat dau bang chu 'G'.

        Test nay ghim mot QUYET DINH, khong phai mot han che ky thuat: neu ai do
        them TS vao danh sach, cong se ngung chan duoc `b"Giao trinh..."`.
        """
        assert looks_like_video(_pad(b"G" + b"\x00" * 11)) is False
        assert looks_like_video(_pad(b"Giao trinh VSL")) is False


class TestPeekKhongTieuThuLuong:
    def test_con_tro_tro_ve_cho_cu(self):
        raw = b"\x00\x00\x00\x20ftypisom" + b"REST-OF-FILE" * 10
        buf = io.BytesIO(raw)
        head = peek_head(buf)
        assert head == raw[:16]
        assert buf.tell() == 0, "peek da an mat byte dau — tep luu xuong se cut dau"
        assert buf.read() == raw, "noi dung doc lai phai nguyen ven"

    def test_peek_giu_nguyen_vi_tri_khac_khong(self):
        buf = io.BytesIO(b"0123456789abcdefghij")
        buf.seek(4)
        assert peek_head(buf, 4) == b"4567"
        assert buf.tell() == 4


def test_loi_sau_khi_giu_han_muc_phai_tra_lai_cho(monkeypatch):
    """Một lỗi trước quyết toán không được giam quota tới khi reservation hết hạn."""
    raw = _pad(b"\x00\x00\x00\x20ftypisom") + b"video-payload"
    upload = UploadFile(filename="clip.mp4", file=io.BytesIO(raw))
    reservation = object()
    guarded = []
    released = []

    def reserve(_tenant, nbytes):
        guarded.append(nbytes)
        return reservation

    def fail_class_registration(**_kwargs):
        raise RuntimeError("characterization: class registration failed")

    monkeypatch.setattr(upload_router, "normalize_dialect", lambda value, **_kwargs: value)
    monkeypatch.setattr(upload_service.storage_quota, "reserve", reserve)
    monkeypatch.setattr(upload_service, "get_or_register_class", fail_class_registration)
    monkeypatch.setattr(upload_service.storage_quota, "release", released.append)

    with tenant_scope("tenant-a"):
        with pytest.raises(RuntimeError, match="class registration failed"):
            asyncio.run(
                upload_router.upload_video(
                    file=upload,
                    user="collector",
                    label="Xin chao",
                    language="vn",
                    dialect="common",
                    class_uid=None,
                    visibility="private",
                    session_id="session-1",
                    upload_uid=None,
                    current_user={"id": "user-1", "tenant_id": "tenant-a"},
                )
            )

    assert guarded == [len(raw)]
    assert released == [reservation]


def test_route_chi_goi_service_khong_tu_luu_hien_vat():
    source = inspect.getsource(upload_router.upload_video)
    assert "raw_video_upload_service.store_raw_video" in source
    for forbidden in (
        "append_raw_upload_row",
        "save_upload_with_limit",
        "insert_raw_upload",
        "upload_raw_video_to_gdrive_task",
        "storage_quota.settle",
    ):
        assert forbidden not in source
