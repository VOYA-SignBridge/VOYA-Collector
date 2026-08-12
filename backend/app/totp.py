"""TOTP (RFC 6238) và HOTP (RFC 4226) bằng thư viện chuẩn.

Vì sao tự viết thay vì thêm `pyotp`: thuật toán là 20 dòng `hmac` + `struct`,
trong khi thêm một phụ thuộc đòi dựng lại ảnh Docker — và ảnh đó chống lưng 5
dịch vụ. Đổi lại, phần này được kiểm bằng **vector thử công bố trong chính RFC**
(RFC 4226 Phụ lục D và RFC 6238 Phụ lục B), tức là đúng đắn được chứng minh với
một bên thứ ba chứ không phải với chính mình.

Hai chỗ dễ viết sai và đều đã được ghim bằng test:

  * **Cắt bit động** (dynamic truncation) — phải AND với `0x7fffffff` để bỏ bit
    dấu. Thiếu bước đó thì khoảng một nửa số mã sai, và sai không theo quy luật
    nào nhìn thấy được.
  * **So sánh mã** phải dùng `hmac.compare_digest`. So bằng `==` rò rỉ thời gian
    và biến việc dò 6 chữ số thành việc dò từng chữ số một.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

#: Bước thời gian, giây. 30 là giá trị mọi ứng dụng xác thực mặc định dùng.
STEP_SECONDS = 30
#: Số chữ số của mã.
DIGITS = 6
#: Số bước chấp nhận lệch về mỗi phía.
#:
#: 1 bước = ±30 giây, tức cửa sổ thật khoảng 90 giây. Đây là mức bù cho đồng hồ
#: điện thoại lệch và cho việc người dùng gõ chậm. Đặt 0 sẽ từ chối oan bất cứ ai
#: có đồng hồ lệch vài giây; đặt 2 trở lên thì nới cửa sổ tấn công mà không giải
#: quyết thêm vấn đề thực tế nào.
DEFAULT_WINDOW = 1


def new_secret(length: int = 20) -> str:
    """Bí mật base32 mới. 20 byte = 160 bit, đúng khuyến nghị của RFC 4226 §4."""
    return base64.b32encode(secrets.token_bytes(length)).decode("ascii").rstrip("=")


def _decode_secret(secret_b32: str) -> bytes:
    # Ứng dụng xác thực hiển thị bí mật không có dấu `=` và người dùng hay chép
    # kèm dấu cách. Chuẩn hoá ở đây để chỗ gọi không phải nhớ.
    raw = (secret_b32 or "").strip().replace(" ", "").upper()
    padding = "=" * (-len(raw) % 8)
    return base64.b32decode(raw + padding, casefold=True)


def hotp(secret_b32: str, counter: int, digits: int = DIGITS) -> str:
    """Mã HOTP cho một bộ đếm (RFC 4226 §5.3)."""
    key = _decode_secret(secret_b32)
    digest = hmac.new(key, struct.pack(">Q", int(counter)), hashlib.sha1).digest()
    # Cắt bit động: 4 bit thấp của byte cuối chọn điểm bắt đầu.
    offset = digest[-1] & 0x0F
    # `& 0x7fffffff` bỏ bit dấu — bỏ quên là lỗi kinh điển của phần này.
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def current_step(at: float | None = None) -> int:
    return int((at if at is not None else time.time()) // STEP_SECONDS)


def totp(secret_b32: str, at: float | None = None, digits: int = DIGITS) -> str:
    """Mã TOTP tại một thời điểm (RFC 6238)."""
    return hotp(secret_b32, current_step(at), digits=digits)


def verify(secret_b32: str, code: str, at: float | None = None,
           window: int = DEFAULT_WINDOW) -> int | None:
    """Kiểm mã. Trả về BƯỚC THỜI GIAN đã khớp, hoặc None.

    Trả về bước chứ không phải True/False là có chủ ý: chỗ gọi cần lưu lại bước
    vừa dùng để chặn phát lại. Một mã TOTP sống 30 giây, nên nếu không ghi lại
    thì kẻ nhìn trộm màn hình gõ lại đúng mã đó vẫn vào được.
    """
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != DIGITS:
        return None
    now_step = current_step(at)
    for drift in range(-abs(window), abs(window) + 1):
        step = now_step + drift
        if step < 0:
            continue
        # compare_digest, không phải `==`: so sánh thường thoát ra ở ký tự đầu
        # tiên khác nhau, và thời gian thoát đó đủ để dò từng chữ số một.
        if hmac.compare_digest(hotp(secret_b32, step), code):
            return step
    return None


def provisioning_uri(secret_b32: str, account: str, issuer: str) -> str:
    """URI `otpauth://` mà ứng dụng xác thực quét được.

    `issuer` xuất hiện HAI lần theo đúng đặc tả của Google Authenticator: một
    lần làm tiền tố của nhãn (để danh sách trong ứng dụng nhóm đúng), một lần
    làm tham số (để ứng dụng đọc máy). Bỏ một trong hai thì một số ứng dụng hiển
    thị mục không có tên tổ chức.
    """
    label = quote(f"{issuer}:{account}", safe="")
    return (
        f"otpauth://totp/{label}"
        f"?secret={secret_b32}&issuer={quote(issuer, safe='')}"
        f"&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}"
    )
