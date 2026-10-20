"""Ai xem / quản lý được mẫu nào trong MỘT tenant — một câu hỏi, một chỗ trả lời.

Quy tắc (chốt 17/10/2026):

    quản trị viên nền tảng            -> mọi mẫu của tenant đang dùng
    admin / editor CỦA tenant ấy      -> mọi mẫu của tenant ấy (xem + quản lý)
    thành viên thường                 -> mẫu của chính mình
                                         + mẫu thuộc phiên đã mở `tenant`/`community`

`private` nghĩa là "riêng với các THÀNH VIÊN khác", không phải "riêng với người
quản lý tenant": tổ chức chịu trách nhiệm về dữ liệu của mình nên người quản lý
phải kiểm tra, duyệt, xoá, xuất được. Bản trước áp cổng chủ-sở-hữu cho MỌI vai,
và đo trên máy thật thì cả 4.205 mẫu của tenant `default` đều private hoặc
không có phiên — admin mở trang nhãn chỉ thấy bản thu của chính mình.

Vai đọc theo TENANT ĐANG DÙNG, không theo cờ trên `current_user`: `tenant_role`
chỉ được tính ở `/auth/me`, nên `user.get("tenant_role")` ở router khác luôn
rỗng (lỗi ngầm của `capture_sessions._is_editor` trước đây).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Set


def can_manage_tenant_samples(user: Dict[str, Any], tenant_id: str) -> bool:
    """Platform admin, hoặc vai admin/editor trong đúng `tenant_id`."""
    if user.get("is_admin"):
        return True
    user_id = str(user.get("id") or "").strip()
    if not user_id or not tenant_id:
        return False
    from app.modules.dataset.vocabulary_registry import EDITOR_ROLES, tenant_role

    try:
        return (tenant_role(tenant_id, user_id) or "") in EDITOR_ROLES
    except Exception:
        # Không tra được vai thì coi như thành viên thường: hẹp hơn là an toàn.
        return False


def readable_sample_uids(user: Dict[str, Any], sample_uids: Iterable[Any], tenant_id: str,
                         *, include_deleted: bool = False) -> Set[str]:
    """Các `sample_uid` trong `sample_uids` mà `user` được xem ở `tenant_id`."""
    from app.storage.metadata_db import get_readable_sample_uids

    return get_readable_sample_uids(
        [str(u) for u in sample_uids if u], str(user.get("id") or ""), tenant_id,
        include_deleted=include_deleted,
        manage_all=can_manage_tenant_samples(user, tenant_id),
    )
