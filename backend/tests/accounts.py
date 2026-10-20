"""Ba địa chỉ email THẬT dùng cho mọi test liên quan tới email.

Vì sao không dùng `@example.com`
--------------------------------
Địa chỉ giả chứng minh được logic, nhưng không chứng minh được thứ hay hỏng
nhất trong đường đi của email: địa chỉ có thật, hộp thư có nhận, và định dạng
địa chỉ thật (dấu chấm, tên miền `.edu.vn` bốn cấp) không làm vỡ chỗ nào. Một
bộ test toàn `nobody@example.test` xanh rực vẫn để lọt lỗi ở đúng chỗ đó.

Ba địa chỉ này do chủ dự án cung cấp và là hộp thư thật:

    mainhatminh1004@gmail.com          — Gmail
    minhb2203567@student.ctu.edu.vn    — tên miền trường, bốn cấp
    mainhatminhct1910@gmail.com        — Gmail, tài khoản chủ dự án

Chúng khác nhau ở điểm có ý nghĩa: hai nhà cung cấp khác nhau, và một địa chỉ
có tên miền con nhiều cấp — thứ hay làm vỡ regex kiểm định địa chỉ viết vội.

VÌ SAO CÓ HÀNG RÀO Ở DƯỚI
-------------------------
Đây là tài khoản THẬT trong cơ sở dữ liệu THẬT. Một test đặt lại mật khẩu hay
xoá tài khoản chạy nhầm vào `signdb` sẽ khoá chủ dự án ra khỏi hệ thống của
chính họ. Nên mọi test có ghi vào ba tài khoản này phải gọi
`refuse_to_touch_production()` trước, và hàm đó dừng test khi `DATABASE_URL`
trỏ vào cơ sở dữ liệu sản xuất.

Cách chạy đúng: nhân bản `signdb` sang `signdb_test` rồi trỏ `DATABASE_URL` vào
bản sao (xem `docs` và ghi chú trong `Dockerfile.test`). Lúc đó ba địa chỉ này
vừa là địa chỉ thật, vừa không đụng được vào dữ liệu thật.

Test chỉ ĐỌC — kiểm định dạng địa chỉ, dựng nội dung thư, khớp regex — không
cần hàng rào và dùng thẳng ba hằng số này.
"""

from __future__ import annotations

import os
import re

import pytest

#: Hộp thư Gmail thứ nhất.
EMAIL_GMAIL = "mainhatminh1004@gmail.com"

#: Tên miền trường, bốn cấp — `student.ctu.edu.vn`.
EMAIL_UNIVERSITY = "minhb2203567@student.ctu.edu.vn"

#: Tài khoản chủ dự án.
EMAIL_OWNER = "mainhatminhct1910@gmail.com"

#: Thứ tự cố định để `parametrize` cho ra tên test ổn định giữa các lần chạy.
ALL_EMAILS = (EMAIL_GMAIL, EMAIL_UNIVERSITY, EMAIL_OWNER)

#: Mật khẩu chủ dự án đặt cho ba tài khoản này.
PASSWORD = "@Minh123456"

#: Tên cơ sở dữ liệu sản xuất. Test nào ghi vào tài khoản thật mà thấy tên này
#: thì dừng, không chạy.
PRODUCTION_DB_NAME = "signdb"


def _database_name() -> str:
    url = os.getenv("DATABASE_URL", "")
    match = re.search(r"/([^/?]+)(\?|$)", url)
    return match.group(1) if match else ""


def refuse_to_touch_production() -> None:
    """Dừng test nếu nó sắp ghi vào tài khoản thật trong cơ sở dữ liệu thật.

    `pytest.skip` chứ không `fail`: chạy suite trên máy chỉ có cơ sở dữ liệu
    sản xuất là một tình huống hợp lệ, và biến nó thành đỏ sẽ khiến người ta
    tìm cách tắt hàng rào đi. Skip kèm lý do nói rõ phải làm gì.

    Điều kiện là tên cơ sở dữ liệu ĐÚNG BẰNG `signdb`, không phải "có chứa":
    `signdb_test` và `signdb_v3test` là bản sao và được phép ghi. Dùng
    `startswith` ở đây sẽ chặn nhầm chính các bản sao mà hàng rào này khuyến
    khích dùng.
    """
    if _database_name() == PRODUCTION_DB_NAME:
        pytest.skip(
            "Test này ghi vào tài khoản email THẬT. DATABASE_URL đang trỏ vào "
            f"'{PRODUCTION_DB_NAME}' (cơ sở dữ liệu sản xuất), nên nó sẽ sửa "
            "hoặc xoá tài khoản thật của người dùng. Hãy nhân bản sang "
            "'signdb_test' rồi trỏ DATABASE_URL vào bản sao."
        )


def username_for(email: str) -> str:
    """Tên đăng nhập suy ra từ địa chỉ, đủ ngắn cho cột và ổn định giữa các lần.

    Ổn định là điều kiện để fixture nhận ra tài khoản mình đã tạo lần trước và
    dọn nó đi, thay vì bỏ lại một hàng mới sau mỗi lần chạy.
    """
    local = email.split("@", 1)[0]
    return re.sub(r"[^a-zA-Z0-9]", "_", local)[:40]
