"""Slot realtime thuộc về ai — để promote không đè mô hình của tổ chức khác.

Vì sao cần
----------
`models.json` có đúng một slot cho mỗi phương ngữ, và cả nền tảng dùng chung
danh sách đó. Khi chỉ quản trị nền tảng promote được thì chuyện đó chịu được.
Quyền `training.promote` thuộc vai tổ chức (xem `authorization/catalog.py`), nên
mở nó mà giữ slot chung nghĩa là biên tập viên trường A thay được mô hình
`hoa-de` mà trường B đang dùng — và mô hình học từ dữ liệu của A hiện ra cho mọi
tổ chức.

Quy ước
-------
Chủ của slot nằm ngay trong `model_id`:

    hoa-de                          slot chung, thuộc mặt phẳng Cộng đồng
    hoa-de@truong-a-1f2e3d           slot của tổ chức `truong-a-1f2e3d`
    hoa-de@truong-a-1f2e3d~<user id>  slot cá nhân của một thành viên ở tổ chức đó

Thành viên không có vai biên tập vẫn dùng được model của chính mình: slot cá nhân
chỉ hiện với đúng người ấy, nên không đè và không lộ sang ai khác.

Để trong `model_id` chứ không thêm cột vào `models.json`, vì `id` đã đi qua mọi
chặng (registry, `/reload`, `/predict`), nên proxy kiểm được quyền bằng một phép
tách chuỗi trên đường nóng, không cần đọc tệp ở mỗi khung hình. Dịch vụ realtime
không cần biết gì về tenant: với nó đây vẫn chỉ là một `model_id`.

Luật đọc: fail-closed. Slot có chủ chỉ hiện với đúng chủ; khách vãng lai và mọi
tổ chức khác không thấy, không gọi được.
"""

from __future__ import annotations

from typing import Optional

from app.storage.authz_schema import COMMUNITY_TENANT_ID

SEPARATOR = "@"
PERSONAL_SEPARATOR = "~"


def slot_id(dialect: str, tenant_id: Optional[str], user_id: Optional[str] = None) -> str:
    """`model_id` của slot phục vụ `dialect`; có `user_id` thì là slot cá nhân."""
    tenant = (tenant_id or "").strip()
    if user_id:
        return f"{dialect}{SEPARATOR}{tenant or COMMUNITY_TENANT_ID}{PERSONAL_SEPARATOR}{user_id}"
    if not tenant or tenant == COMMUNITY_TENANT_ID:
        return dialect
    return f"{dialect}{SEPARATOR}{tenant}"


def slot_owner(model_id: Optional[str]) -> Optional[str]:
    """Tổ chức sở hữu slot; `None` = slot chung."""
    _, sep, owner = str(model_id or "").rpartition(SEPARATOR)
    return (owner.strip() or None) if sep else None


def is_personal(model_id: Optional[str]) -> bool:
    return PERSONAL_SEPARATOR in (slot_owner(model_id) or "")


def visible_to(model_id: Optional[str], tenant_id: Optional[str],
               user_id: Optional[str] = None) -> bool:
    """Người gọi ở `tenant_id` (có thể `None` với khách) có được thấy và gọi slot này không."""
    owner = slot_owner(model_id)
    if owner is None:
        return True
    tenant, sep, nguoi = owner.partition(PERSONAL_SEPARATOR)
    if tenant != (tenant_id or "").strip():
        return False
    return not sep or nguoi == str(user_id or "")
