"""Quản trị TENANT không bao giờ là quản trị NỀN TẢNG.

Chạy:
    bash scripts/run_tests.sh backend/tests/test_tenant_admin_is_not_platform_admin.py -v -s

Vì sao tệp này tồn tại
======================
Ngày 16/08/2026 một lượt đo đối kháng cho ra kết quả trông như lỗ hổng nặng:

    "quản trị viên của tenant A" xoá được tenant B      HTTP 200

Nhưng tài khoản dùng trong lượt ấy có `users.is_admin = TRUE`, mà theo
`docs/03-security/AUTHORIZATION.md` §247 cờ đó ánh xạ sang
`platform_administrator` — vai cầm mọi quyền ở mọi phạm vi. Nói cách khác, phép
đo trao quyền nền tảng cho một tài khoản rồi ngạc nhiên vì nó dùng quyền nền
tảng. Hệ thống không sai; bộ đo chọn sai chủ thể.

Bài học, và nó đáng ghi thành một dòng:

    Một ca kiểm phân quyền ÂM chỉ có nghĩa khi chủ thể CHƯA sẵn có quyền
    thực hiện hành động đang thử.

Ba loại chủ thể, đừng gộp
=========================
```
users.is_admin = TRUE          -> platform_administrator    phạm vi NỀN TẢNG
tenant_members.role = 'admin'  -> tenant_administrator       phạm vi MỘT TENANT
tenant_members.role = 'editor' -> tenant_editor              phạm vi MỘT TENANT
```

Các ca dưới đây khoá ranh giới giữa hai loại đầu, vì đó là ranh giới mà một
dòng mã kiểu `if user["is_admin"]` xoá đi lúc nào không hay.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.auth import require_admin
from app.authorization.catalog import (
    LEGACY_SYSTEM_ADMIN_ROLE,
    LEGACY_TENANT_ROLE_MAP,
)


def _nguoi(is_admin: bool, tenant_id: str = "iso_a") -> dict:
    return {"id": str(uuid.uuid4()), "username": "x", "email": "x@x",
            "is_active": True, "is_admin": is_admin, "tenant_id": tenant_id}


# =========================================================================
# Ánh xạ vai — hai trục khác nhau, không được chạm nhau
# =========================================================================

def test_vai_tenant_khong_bao_gio_anh_xa_sang_vai_nen_tang():
    """`tenant_members.role` KHÔNG có đường nào dẫn tới vai nền tảng.

    Nếu một ngày `LEGACY_TENANT_ROLE_MAP` mọc thêm một mục trỏ tới
    `platform_administrator`, mọi quản trị viên tenant lập tức thành người vận
    hành nền tảng — im lặng, không migration, không ai duyệt.
    """
    print(f"\n[evidence] map tenant = {LEGACY_TENANT_ROLE_MAP}")
    print(f"[evidence] vai nen tang = {LEGACY_SYSTEM_ADMIN_ROLE!r}")
    assert LEGACY_SYSTEM_ADMIN_ROLE not in LEGACY_TENANT_ROLE_MAP.values()
    for legacy, builtin in LEGACY_TENANT_ROLE_MAP.items():
        assert builtin.startswith("tenant_"), (
            f"vai tenant {legacy!r} anh xa sang {builtin!r} — khong phai vai tenant")


def test_vai_admin_cua_tenant_la_tenant_administrator_chu_khong_phai_platform():
    """`role='admin'` trong một tenant là `tenant_administrator`.

    Cùng một chữ "admin" mang hai nghĩa ở hai bảng khác nhau. Đó chính là chỗ
    lượt đo đầu trượt chân.
    """
    assert LEGACY_TENANT_ROLE_MAP["admin"] == "tenant_administrator"
    assert LEGACY_TENANT_ROLE_MAP["admin"] != LEGACY_SYSTEM_ADMIN_ROLE


# =========================================================================
# Cổng `require_admin` — cổng NỀN TẢNG, không phải cổng tenant
# =========================================================================

def test_require_admin_tu_choi_quan_tri_TENANT():
    """Quản trị viên tenant (is_admin=False) KHÔNG qua được `require_admin`.

    Đây là bất biến "quyền cao hơn không làm phạm vi rộng hơn". Một tài khoản
    có toàn quyền TRONG tổ chức mình vẫn không chạm được đường nền tảng.
    """
    with pytest.raises(HTTPException) as ei:
        require_admin(_nguoi(is_admin=False))
    print(f"\n[evidence] status={ei.value.status_code} detail={ei.value.detail!r}")
    assert ei.value.status_code == 403


def test_require_admin_cho_qua_quan_tri_NEN_TANG():
    """Đối chứng dương: thiếu nó thì ca trên xanh kể cả khi cổng chặn TẤT CẢ.

    Một cổng từ chối mọi người cũng làm ca âm ở trên xanh — và khi đó phép thử
    không chứng minh được điều nó tuyên bố.
    """
    u = require_admin(_nguoi(is_admin=True))
    assert u["is_admin"] is True


def test_cot_tenant_id_khong_anh_huong_cong_nen_tang():
    """Thuộc `default` KHÔNG cấp quyền nền tảng.

    `default` là nguồn bootstrap/seed, không phải "tenant của người vận hành".
    Sau khi bỏ `DEFAULT 'default'` khỏi `users.tenant_id` (16/08/2026), điều
    còn phải giữ là: nằm trong tenant ấy không kèm theo đặc quyền nào.
    """
    with pytest.raises(HTTPException):
        require_admin(_nguoi(is_admin=False, tenant_id="default"))
