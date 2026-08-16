"""B-ID-1..5 — danh tính tenant không bao giờ được SUY RA khi thiếu.

Chạy:
    bash scripts/run_tests.sh backend/tests/test_identity_tenant_no_implicit_default.py -v -s

Bất biến
========
```
tenant_id tường minh = 'default'   ->  default        HỢP LỆ
tenant_id thiếu / rỗng / hỏng      ->  FAIL CLOSED    không bao giờ -> default
```

`default` vẫn là một tenant hợp lệ — nó là nguồn BOOTSTRAP/SEED. Điều bị cấm
không phải "thuộc default", mà là **rơi vào default vì thiếu dữ liệu**. Một lỗi
quên truyền phạm vi không được biến thành một tư cách thành viên có thật.

Vì sao lược đồ phải đổi chứ không chỉ sửa mã
============================================
`users.tenant_id` từng là `NOT NULL DEFAULT 'default'`. Nghĩa là PostgreSQL —
chứ không phải mã ứng dụng — thực hiện phép rơi-về-default, và không lớp kiểm
tra nào ở Python nhìn thấy nó. Câu một chiều `_DROP_USERS_TENANT_DEFAULT`
(16/08/2026) bỏ DEFAULT và GIỮ NOT NULL: "không có tenant" không phải một trạng
thái hợp lệ để lưu, nó là lỗi phải chặn lúc ghi.

Không hàng nào bị di chuyển. Tài khoản đang thuộc `default` vẫn thuộc `default`.
"""

from __future__ import annotations

import uuid

import pytest

from app.auth import _row_to_user
from app.storage.metadata_db import _migration_cursor, insert_user
from app.tenancy import DEFAULT_TENANT_ID


# =========================================================================
# B-ID-3 — lược đồ tự nó phải từ chối
# =========================================================================

def test_B_ID_3_INSERT_thieu_tenant_bi_CSDL_tu_choi():
    """Bỏ `tenant_id` khỏi câu INSERT phải NỔ, không sinh ra user `default`.

    Đây là phép thử của LƯỢC ĐỒ, không phải của mã ứng dụng: nếu DEFAULT còn
    đó thì câu này chạy êm và tạo ra một tư cách thành viên mà không ai yêu cầu.
    """
    uid = str(uuid.uuid4())
    with pytest.raises(Exception) as ei:
        with _migration_cursor() as cur:
            cur.execute(
                "INSERT INTO users (id, username, email, password_hash, is_active) "
                "VALUES (%s, %s, %s, %s, TRUE)",
                (uid, f"khong-tenant-{uid[:8]}", f"{uid[:8]}@x.local", "x"))
    print(f"\n[evidence] CSDL tu choi: {type(ei.value).__name__}")

    # Và không được sót lại hàng nào.
    with _migration_cursor() as cur:
        cur.execute("SELECT count(*) FROM users WHERE id = %s", (uid,))
        assert cur.fetchone()[0] == 0


def test_lucre_do_giu_NOT_NULL_va_bo_DEFAULT():
    """Cột phải NOT NULL **và** không còn DEFAULT. Thiếu vế nào cũng hỏng:

    * còn DEFAULT  -> lỗi thiếu phạm vi lại thành membership im lặng
    * bỏ NOT NULL  -> "không có tenant" trở thành trạng thái lưu được, và mọi
                      đường đọc sau đó phải tự đoán nghĩa của NULL
    """
    with _migration_cursor() as cur:
        cur.execute(
            "SELECT is_nullable, column_default FROM information_schema.columns "
            "WHERE table_name = 'users' AND column_name = 'tenant_id'")
        is_nullable, default = cur.fetchone()
    print(f"\n[evidence] is_nullable={is_nullable} column_default={default!r}")
    assert is_nullable == "NO"
    assert default is None


# =========================================================================
# B-ID-4/5 — tầng ứng dụng không bịa
# =========================================================================

def test_B_ID_4_row_thieu_tenant_thi_khong_bia_ra_default():
    """`_row_to_user` không được biến một cột KHÔNG ĐƯỢC SELECT thành `default`.

    Vì cột là NOT NULL, `row['tenant_id']` vắng mặt chỉ có thể do truy vấn quên
    chọn nó — một lỗi lập trình. Che nó bằng một tenant đoán được là cách chắc
    chắn nhất để không bao giờ phát hiện ra.
    """
    u = _row_to_user({"id": uuid.uuid4(), "username": "x", "email": "x@x",
                      "password_hash": "h"})
    print(f"\n[evidence] tenant_id khi row thieu cot: {u['tenant_id']!r}")
    assert u["tenant_id"] != DEFAULT_TENANT_ID
    assert u["tenant_id"] == ""


@pytest.mark.parametrize("gia_tri", [None, "", "   "])
def test_B_ID_5_gia_tri_rong_khong_thanh_default(gia_tri):
    u = _row_to_user({"id": uuid.uuid4(), "username": "x", "email": "x@x",
                      "password_hash": "h", "tenant_id": gia_tri})
    assert u["tenant_id"] == ""


def test_B_ID_1_2_gia_tri_TUONG_MINH_duoc_giu_nguyen():
    """Cả tenant thường lẫn `default` tường minh đều đi qua không bị đổi.

    B-ID-2 là ca dễ bị bỏ sót: `default` KHÔNG phải giá trị đáng ngờ. Nó chỉ
    đáng ngờ khi xuất hiện mà không ai gán.
    """
    for gt in ("iso_a", DEFAULT_TENANT_ID):
        u = _row_to_user({"id": uuid.uuid4(), "username": "x", "email": "x@x",
                          "password_hash": "h", "tenant_id": gt})
        assert u["tenant_id"] == gt


# =========================================================================
# Đường tạo user: bắt buộc nói ra ý định
# =========================================================================

def test_insert_user_doi_tenant_tuong_minh():
    """`insert_user` không có mặc định `DEFAULT_TENANT_ID` trong Python.

    Đặt mặc định ở đây chỉ chuyển phép rơi-về-default từ PostgreSQL lên Python:
    cùng một lỗ, khác tầng, và khó thấy hơn vì không còn nằm trong lược đồ.
    """
    with pytest.raises(ValueError) as ei:
        insert_user({"id": str(uuid.uuid4()), "username": "x", "email": "x@x",
                     "password_hash": "h"})
    print(f"\n[evidence] {ei.value}")
    assert "tenant_id" in str(ei.value)
