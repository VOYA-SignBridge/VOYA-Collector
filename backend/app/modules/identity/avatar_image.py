"""Chuẩn hoá ảnh đại diện người dùng tải lên.

Mọi ảnh đi qua đây đều được GIẢI MÃ rồi VẼ LẠI thành một ảnh WebP vuông nhỏ, chứ
không bao giờ lưu nguyên bytes người dùng gửi. Vì sao không lưu nguyên:

  * tệp tải lên là đầu vào KHÔNG tin được — một tệp "ảnh" có thể là HTML/SVG
    mang script, hoặc một polyglot; vẽ lại thì chỉ còn điểm ảnh;
  * ảnh chụp từ điện thoại mang EXIF, trong đó có TOẠ ĐỘ GPS của nhà người
    dùng. Người dùng ở đây phần lớn là học sinh; ảnh đại diện không được lộ
    chỗ ở của họ;
  * ảnh 12 MB làm chậm mọi trang có hiện ảnh đại diện. 256x256 WebP chỉ vài KB.

Chặn ảnh "bom giải nén": một tệp PNG vài trăm KB có thể khai báo 50.000x50.000
điểm ảnh và ngốn hàng GB bộ nhớ khi giải mã. Kích thước được đọc từ tiêu đề
TRƯỚC, và từ chối trước khi giải mã.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

#: Trần dung lượng tệp tải lên.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
#: Trần số điểm ảnh khai báo (khoảng 5000x5000).
MAX_PIXELS = 25_000_000
#: Cạnh của ảnh lưu lại.
SIDE = 256
#: Định dạng nhận vào. SVG cố ý KHÔNG có: nó là tài liệu có thể chứa script.
ACCEPTED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
CONTENT_TYPE = "image/webp"


class AvatarImageError(ValueError):
    """Ảnh không dùng được. `code` để giao diện/ máy chủ chọn câu trả lời."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def normalise(raw: bytes) -> bytes:
    """Giải mã, cắt vuông giữa, thu về SIDE x SIDE, xuất WebP không kèm siêu dữ liệu."""
    if len(raw) > MAX_UPLOAD_BYTES:
        raise AvatarImageError("too_large")
    try:
        with Image.open(io.BytesIO(raw)) as img:
            if img.format not in ACCEPTED_FORMATS:
                raise AvatarImageError("unsupported")
            width, height = img.size
            if width < 1 or height < 1 or width * height > MAX_PIXELS:
                raise AvatarImageError("dimensions")
            img.load()
            img = ImageOps.exif_transpose(img)  # xoay đúng chiều TRƯỚC khi bỏ EXIF
            img = _flatten(img)
            img = ImageOps.fit(img, (SIDE, SIDE), method=Image.Resampling.LANCZOS)
            out = io.BytesIO()
            img.save(out, format="WEBP", quality=85)  # không truyền exif: không lưu gì
            return out.getvalue()
    except AvatarImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise AvatarImageError("invalid") from None


def _flatten(img: Image.Image) -> Image.Image:
    """Ảnh có nền trong suốt: đặt lên nền trắng thay vì để thành đen."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        base = Image.new("RGB", rgba.size, "white")
        base.paste(rgba, mask=rgba.getchannel("A"))
        return base
    return img.convert("RGB")
