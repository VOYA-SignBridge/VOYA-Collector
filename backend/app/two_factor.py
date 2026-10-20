"""Xác thực hai bước: lưu trữ bí mật TOTP và mã khôi phục.

Thuật toán nằm ở `app/totp.py`; file này lo phần *trạng thái* — thứ mà một bản
cài đặt 2FA thường sai chứ không phải phép tính HMAC.

Bốn quyết định đáng nêu:

1. **Bí mật được MÃ HOÁ, mã khôi phục được BĂM.** Khác nhau vì mục đích khác
   nhau: TOTP cần chính bí mật để tính lại mã (băm một chiều thì vô dụng), còn
   mã khôi phục chỉ cần trả lời "đúng hay sai" nên băm là đủ và an toàn hơn.

2. **Chống phát lại.** Một mã TOTP sống 30 giây. Không ghi lại bước đã dùng thì
   người nhìn trộm màn hình gõ lại đúng mã đó trong 30 giây vẫn vào được — và
   đó chính là kịch bản 2FA sinh ra để chặn. `last_used_step` khoá cửa đó.

3. **Bật 2FA là hai bước, không phải một.** `begin_enrollment` chỉ ghi bí mật ở
   trạng thái CHƯA xác nhận; `confirm_enrollment` mới bật. Gộp làm một sẽ khoá
   người dùng ra khỏi tài khoản của chính họ khi ứng dụng xác thực quét hỏng
   hoặc đồng hồ điện thoại lệch — và họ không còn đường nào quay lại.

4. **Không có RLS trên hai bảng này** (xem `CREATE TABLE user_totp`). Bù lại,
   MỌI câu ở đây khoá theo `user_id` của đúng một người, lấy từ phiên đăng nhập
   hoặc từ chính hàng vừa đọc — không câu nào nhận điều kiện từ bên ngoài.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
from typing import Any, Dict, List, Optional

from app import totp
from app.config import settings
from app.storage.metadata_db import _execute, _fetch_all

logger = logging.getLogger(__name__)

#: Tên tổ chức hiện trong ứng dụng xác thực, cạnh mã 6 số.
#:
#: Hằng số chứ không phải cấu hình: nó được nướng vào chính mục đã đăng ký trên
#: điện thoại người dùng. Đổi nó về sau không cập nhật những mục đã tạo, nên một
#: biến môi trường ở đây chỉ tạo ra hai nguồn sự thật mà không đổi được gì.
ISSUER = "CTU.SignBridge"

#: Số mã khôi phục cấp mỗi lượt.
RECOVERY_CODE_COUNT = 10
#: Độ dài mỗi nửa của mã khôi phục (hiển thị dạng `xxxxx-xxxxx`).
_RECOVERY_HALF = 5
#: Bảng chữ cái mã khôi phục: bỏ 0/O/1/I/L để người ta không chép nhầm khi đọc
#: từ một tờ giấy in ra — đó là cách những mã này thực sự được cất giữ.
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


class TwoFactorError(RuntimeError):
    """Sai sót nghiệp vụ của luồng 2FA, đủ an toàn để hiện cho người dùng."""


# ---------------------------------------------------------------------------
# Mã hoá bí mật
# ---------------------------------------------------------------------------
def _fernet():
    """Khoá đối xứng dẫn xuất từ SECRET_KEY, không lưu trong CSDL.

    Nhờ vậy một bản dump CSDL bị rò KHÔNG đủ để sinh mã 2FA của bất kỳ ai — kẻ
    tấn công còn cần biến môi trường của ứng dụng.

    ĐÁNH ĐỔI phải nói rõ: đổi SECRET_KEY làm mọi bí mật đã lưu không giải mã
    được nữa, và toàn bộ người dùng phải đăng ký lại 2FA. Quy trình xoay khoá bí
    mật vì thế phải xử lý bảng này — ghi trong docs/03-security/TWO_FACTOR.md.
    """
    from cryptography.fernet import Fernet

    key = hashlib.sha256(
        f"totp-secret-v1:{settings.secret_key}".encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _encrypt(secret_b32: str) -> str:
    return _fernet().encrypt(secret_b32.encode("ascii")).decode("ascii")


def _decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode("ascii")).decode("ascii")


# ---------------------------------------------------------------------------
# Trạng thái
# ---------------------------------------------------------------------------
def _row(user_id: str) -> Optional[Dict[str, Any]]:
    rows = _fetch_all(
        "SELECT user_id, secret_enc, confirmed_at, last_used_step "
        "FROM user_totp WHERE user_id = %s",
        (str(user_id),))
    return rows[0] if rows else None


def is_enabled(user_id: str) -> bool:
    """2FA đã BẬT chưa (đã xác nhận, không phải mới đăng ký dở)."""
    row = _row(user_id)
    return bool(row and row["confirmed_at"] is not None)


def status(user_id: str) -> Dict[str, Any]:
    row = _row(user_id)
    return {
        "enabled": bool(row and row["confirmed_at"] is not None),
        "pending": bool(row and row["confirmed_at"] is None),
        "confirmed_at": row["confirmed_at"] if row else None,
        "recovery_codes_left": count_unused_recovery_codes(user_id),
    }


# ---------------------------------------------------------------------------
# Đăng ký
# ---------------------------------------------------------------------------
def begin_enrollment(user_id: str, account_label: str) -> Dict[str, str]:
    """Cấp một bí mật mới ở trạng thái CHƯA xác nhận. Trả về bí mật + URI.

    Gọi lại khi đang dở sẽ THAY bí mật cũ: người dùng quét hỏng rồi bấm lại là
    chuyện thường, và giữ bí mật cũ khiến mã trên điện thoại không bao giờ khớp.
    Không thay được nếu 2FA ĐÃ bật — muốn đổi thì phải tắt trước, và tắt thì cần
    xác thực.
    """
    if is_enabled(user_id):
        raise TwoFactorError("2FA đã bật. Hãy tắt trước khi đăng ký lại.")

    secret = totp.new_secret()
    _execute(
        "INSERT INTO user_totp (user_id, secret_enc) VALUES (%s, %s) "
        "ON CONFLICT (user_id) DO UPDATE SET secret_enc = EXCLUDED.secret_enc, "
        "confirmed_at = NULL, last_used_step = NULL, created_at = NOW()",
        (str(user_id), _encrypt(secret)))
    return {
        "secret": secret,
        "uri": totp.provisioning_uri(secret, account_label, ISSUER),
    }


def confirm_enrollment(user_id: str, code: str) -> List[str]:
    """Bật 2FA sau khi người dùng chứng minh ứng dụng của họ sinh đúng mã.

    Trả về danh sách mã khôi phục — **lần duy nhất** chúng tồn tại dưới dạng đọc
    được. Sau đó CSDL chỉ còn giữ băm.
    """
    row = _row(user_id)
    if not row:
        raise TwoFactorError("Chưa bắt đầu đăng ký 2FA.")
    if row["confirmed_at"] is not None:
        raise TwoFactorError("2FA đã bật rồi.")

    step = totp.verify(_decrypt(row["secret_enc"]), code)
    if step is None:
        raise TwoFactorError("Mã không đúng. Kiểm tra lại đồng hồ trên điện thoại.")

    _execute(
        "UPDATE user_totp SET confirmed_at = NOW(), last_used_step = %s "
        "WHERE user_id = %s",
        (step, str(user_id)))
    return regenerate_recovery_codes(user_id)


def disable(user_id: str) -> None:
    """Tắt 2FA và xoá sạch mã khôi phục.

    Xoá chứ không đánh dấu: mã khôi phục còn sót lại sau khi tắt là một đường
    vào không ai còn nhớ là mình đã mở.
    """
    _execute("DELETE FROM user_recovery_codes WHERE user_id = %s", (str(user_id),))
    _execute("DELETE FROM user_totp WHERE user_id = %s", (str(user_id),))


# ---------------------------------------------------------------------------
# Kiểm mã lúc đăng nhập
# ---------------------------------------------------------------------------
def verify_code(user_id: str, code: str) -> bool:
    """Kiểm một mã TOTP và tiêu nó đi. False nếu sai hoặc đã dùng rồi."""
    row = _row(user_id)
    if not row or row["confirmed_at"] is None:
        return False

    step = totp.verify(_decrypt(row["secret_enc"]), code)
    if step is None:
        return False

    # Chống phát lại: mỗi bước thời gian chỉ được tiêu một lần, và bước phải
    # TIẾN. Câu UPDATE tự nó là chỗ phân xử — điều kiện nằm trong `WHERE`, nên
    # hai yêu cầu chạy song song không thể cùng thắng.
    #
    # Kết quả đọc từ `RETURNING`, KHÔNG phải bằng một câu SELECT sau đó. Bản đầu
    # ghi rồi đọc lại và so `last_used_step == step`: lần gọi thứ hai thấy đúng
    # giá trị mà lần gọi THỨ NHẤT vừa ghi, nên nó kết luận thành công và mã dùng
    # lại được — tức là chống phát lại không hề chạy. `RETURNING` trả lời đúng
    # câu hỏi cần hỏi: "câu UPDATE NÀY có khớp dòng nào không".
    rows = _fetch_all(
        "UPDATE user_totp SET last_used_step = %s "
        "WHERE user_id = %s AND (last_used_step IS NULL OR last_used_step < %s) "
        "RETURNING user_id",
        (step, str(user_id), step))
    return bool(rows)


# ---------------------------------------------------------------------------
# Mã khôi phục
# ---------------------------------------------------------------------------
def _new_recovery_code() -> str:
    half = lambda: "".join(secrets.choice(_RECOVERY_ALPHABET)  # noqa: E731
                           for _ in range(_RECOVERY_HALF))
    return f"{half()}-{half()}"


def _hash_recovery(code: str) -> str:
    """HMAC khoá bằng SECRET_KEY, không phải SHA-256 trần.

    Mã khôi phục chỉ có ~50 bit entropy, nên một bảng tra cứu là khả thi nếu chỉ
    băm trần. Khoá nằm ngoài CSDL làm bản dump bị rò trở nên vô dụng — cùng lý
    do `app/tokens.py` dùng pepper cho mã OTP.
    """
    normalized = (code or "").strip().lower().replace(" ", "")
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        f"recovery-v1:{normalized}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def regenerate_recovery_codes(user_id: str) -> List[str]:
    """Cấp bộ mã mới, huỷ bộ cũ. Trả về mã ĐỌC ĐƯỢC đúng một lần."""
    _execute("DELETE FROM user_recovery_codes WHERE user_id = %s", (str(user_id),))
    codes = [_new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    for code in codes:
        _execute(
            "INSERT INTO user_recovery_codes (code_hash, user_id) VALUES (%s, %s) "
            "ON CONFLICT (code_hash) DO NOTHING",
            (_hash_recovery(code), str(user_id)))
    return codes


def count_unused_recovery_codes(user_id: str) -> int:
    rows = _fetch_all(
        "SELECT COUNT(*) AS n FROM user_recovery_codes "
        "WHERE user_id = %s AND used_at IS NULL",
        (str(user_id),))
    return int(rows[0]["n"]) if rows else 0


def consume_recovery_code(user_id: str, code: str) -> bool:
    """Tiêu một mã khôi phục. Mỗi mã dùng được đúng một lần.

    Điều kiện `used_at IS NULL` nằm TRONG câu UPDATE chứ không kiểm trước rồi
    ghi sau: hai yêu cầu gửi cùng một mã cùng lúc thì chỉ một câu khớp được dòng,
    câu kia thấy `rowcount = 0`. Kiểm-rồi-ghi sẽ để cả hai cùng qua.
    """
    if not code:
        return False
    rows = _fetch_all(
        "UPDATE user_recovery_codes SET used_at = NOW() "
        "WHERE code_hash = %s AND user_id = %s AND used_at IS NULL "
        "RETURNING code_hash",
        (_hash_recovery(code), str(user_id)))
    if rows:
        logger.info("[2FA] user=%s dung mot ma khoi phuc, con lai %d",
                    user_id, count_unused_recovery_codes(user_id))
        return True
    return False
