"""Hàng đợi kiểm duyệt và hai cái nút: Duyệt, Từ chối.

Xem docs/01-architecture/COMMUNITY_MODERATION.md §1, §6, §7.

Đơn vị là PHIÊN THU, không phải mẫu
------------------------------------
Đo trên dữ liệu thật: 3.862 mẫu nhưng chỉ **250 phiên thu** — trung bình 11,5
mẫu mỗi phiên, vì một lần quay sinh ra 1 mẫu gốc cộng N mẫu tăng cường dùng
chung `capture_session_id`.

Kiểm duyệt theo mẫu nghĩa là bắt người duyệt xem cùng một cử chỉ 11 lần và bắn
11 thông báo cho một lần quay. Hàng đợi 250 mục thì duyệt được; 3.862 mục thì
không. Nên: **quyết định theo phiên, lưu trạng thái theo dòng.**

Quyết định phải ghi vào CẢ HAI nơi
-----------------------------------
`samples.csv` là nguồn sự thật, Postgres là bản sao. Ghi một bên thôi thì lượt
đồng bộ kế tiếp sẽ lấy bên kia đè lên — và với `review_status`, "bên kia" là
tệp, nên một quyết định chỉ ghi vào cơ sở dữ liệu sẽ **bị xoá lặng lẽ**.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.moderation import APPROVED, PENDING, REJECTED

logger = logging.getLogger(__name__)

#: Quyền quyết định. Xem `authorization/catalog.py`.
PERM_MODERATE = "sample.moderate"


class ModerationError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


# --------------------------------------------------------------------------- quyền


def can_moderate(user: Dict[str, Any]) -> bool:
    """Người này có được duyệt không.

    Hỏi BA câu, cùng hình dạng với `access_gate._has_any_tenant_grant` — và vì
    cùng một lý do: không có câu nào trong ba trả lời thay được hai câu kia.

        1. `is_admin`                     quản trị viên nền tảng, cầm mọi quyền
        2. grant v5 mang `sample.moderate`  vai mới, gồm `community_reviewer`
        3. vai ở SỔ CŨ ánh xạ sang role dựng sẵn có quyền ấy

    Vì sao câu 2 không thừa
    ------------------------
    `AUTHZ_MODE=shadow` nghĩa là `authorize()` quyết định bằng hệ CŨ, và hệ cũ
    chỉ biết đọc `tenant_members.role` — cột bị ràng buộc ở `admin|editor|NULL`.
    `community_reviewer` không có bản sao nào ở đó, nên gọi `authorize()` một
    mình sẽ từ chối đúng cái vai vừa được tạo ra để duyệt. Câu 2 là thứ làm vai
    ấy có thật trước khi Casbin cầm quyền.

    Vì sao câu 3 không thừa
    ------------------------
    Sáu người đang mang `tenant_editor` và bốn người mang `tenant_administrator`
    có quyền này qua tập quyền của role dựng sẵn, nhưng KHÔNG có dòng
    `role_assignments` nào ở phạm vi tenant cho họ — họ đi qua sổ cũ.

    Hỏng-thì-ĐÓNG: tra cứu lỗi thì trả `False`.
    """
    if user.get("is_admin"):
        return True

    user_id = str(user.get("id") or user.get("user_id") or "").strip()
    if not user_id:
        return False

    try:
        from app.storage.metadata_db import _fetch_all
        from app.tenant_context import system_scope

        with system_scope("moderation: ai duoc duyet"):
            v5 = _fetch_all(
                "SELECT 1 FROM role_assignments a "
                "  JOIN roles r ON r.role_id = a.role_id "
                "  JOIN role_permissions rp ON rp.role_id = r.role_id "
                "  LEFT JOIN memberships m ON m.membership_id = a.membership_id "
                "                         AND m.user_id = a.user_id "
                "  LEFT JOIN tenants t ON t.tenant_id = m.tenant_id "
                " WHERE a.user_id = %s AND a.revoked_at IS NULL AND r.is_active "
                "   AND rp.permission_code = %s "
                "   AND (a.membership_id IS NULL "
                "        OR (m.status = 'ACTIVE' AND m.left_at IS NULL "
                "            AND t.deleted_at IS NULL AND t.is_active)) "
                " LIMIT 1",
                (user_id, PERM_MODERATE),
            )
            if v5:
                return True

            cu = _fetch_all(
                "SELECT role FROM tenant_members "
                " WHERE user_id = %s AND role IS NOT NULL "
                "   AND status = 'ACTIVE' AND removed_at IS NULL",
                (user_id,),
            )
    except Exception:
        logger.exception("[MODERATION] khong tra duoc quyen cho %s; tu choi", user_id)
        return False

    # Cả hai lấy từ `catalog` — nơi ĐỊNH NGHĨA chúng. `authorization_service`
    # cũng phơi ra `LEGACY_TENANT_ROLE_MAP`, nhưng nhập qua đó là mượn tên qua
    # một mô-đun trung gian và kéo theo cả hệ Casbin vào một phép tra danh mục.
    from app.authorization.catalog import BUILTIN_BY_CODE, LEGACY_TENANT_ROLE_MAP

    for row in cu:
        builtin = LEGACY_TENANT_ROLE_MAP.get((row.get("role") or "").strip())
        if builtin and PERM_MODERATE in BUILTIN_BY_CODE[builtin].permissions:
            return True
    return False


# --------------------------------------------------------------------------- hàng đợi


def pending_session_count(tenant_id: str) -> int:
    """Số PHIÊN đang chờ duyệt. Dùng cho huy hiệu trên thanh bên.

    Đếm phiên chứ không đếm mẫu: huy hiệu phải khớp với số mục người ta thấy
    trong hàng đợi, nếu không nó nói 3.862 trong khi màn hình có 250 dòng.

    Rẻ nhờ `idx_samples_pending_review` — chỉ mục TỪNG PHẦN, nên nó chỉ lớn
    bằng phần đang chờ chứ không bằng cả bảng.
    """
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        "SELECT count(DISTINCT capture_session_id) AS n FROM samples "
        " WHERE tenant_id = %s AND review_status = %s AND deleted_at IS NULL",
        (tenant_id, PENDING),
    )
    return int(rows[0]["n"]) if rows else 0


def list_pending_sessions(tenant_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Các phiên đang chờ duyệt, cũ nhất trước.

    Cũ nhất trước, vì hàng đợi kiểm duyệt là hàng đợi công bằng: người đóng góp
    đầu tiên không nên chờ lâu nhất.

    Mỗi dòng gộp cả phiên và mang sẵn thứ màn hình cần — nhãn, người đóng góp,
    số mẫu, và `sample_uid` của MẪU GỐC (`augment_id = 0`) để xem lại. Người
    duyệt cần xem một lần quay, không phải mười một bản tăng cường của nó.
    """
    from app.storage.metadata_db import _fetch_all

    return _fetch_all(
        "SELECT s.capture_session_id, "
        "       min(s.label_original) AS label_original, "
        "       min(s.dialect)        AS dialect, "
        "       min(s.language)       AS language, "
        "       count(*)              AS sample_count, "
        "       min(s.created_at)     AS captured_at, "
        "       min(s.auth_user_id::text) AS contributor_id, "
        "       min(u.username)       AS contributor_name, "
        "       min(u.email)          AS contributor_email, "
        "       min(s.completeness)   AS completeness, "
        "       (array_agg(s.sample_uid ORDER BY s.augment_id NULLS LAST))[1] AS original_uid "
        "  FROM samples s LEFT JOIN users u ON u.id = s.auth_user_id "
        " WHERE s.tenant_id = %s AND s.review_status = %s AND s.deleted_at IS NULL "
        "   AND s.capture_session_id IS NOT NULL "
        " GROUP BY s.capture_session_id "
        " ORDER BY min(s.created_at) "
        " LIMIT %s",
        (tenant_id, PENDING, int(limit)),
    )


# --------------------------------------------------------------------------- quyết định


def decide_session(
    capture_session_id: str,
    *,
    approve: bool,
    actor_id: str,
    tenant_id: str,
    note: str = "",
) -> Dict[str, Any]:
    """Duyệt hoặc từ chối MỘT phiên thu, ghi vào cả CSV lẫn Postgres.

    Từ chối KHÔNG xoá gì
    ---------------------
    Theo đúng bài học của `POST /vocabulary/dialects/{id}/reject`: tới lúc người
    duyệt nhìn tới thì người đóng góp đã bỏ công quay rồi. Từ chối đặt
    `review_status = 'rejected'` kèm lý do; dữ liệu vẫn thuộc về họ và họ vẫn
    dùng được cho riêng mình. Đó là hợp đồng "chưa duyệt thì chỉ chủ dùng được",
    và nó không đổi khi câu trả lời là không.

    Lý do là BẮT BUỘC khi từ chối. Một lượt từ chối không nói vì sao thì người
    đóng góp không có gì để sửa, và họ sẽ quay lại đúng như cũ.
    """
    from app.catalog_sync import CatalogSyncError, sync_set_review_status
    from app.tenancy import TENANT_COLUMN

    sid = str(capture_session_id or "").strip()
    if not sid:
        raise ModerationError("Thiếu mã phiên thu.", status_code=400)
    if not approve and not (note or "").strip():
        raise ModerationError(
            "Từ chối phải kèm lý do — người đóng góp cần biết phải sửa gì.",
            status_code=400)

    trang_thai = APPROVED if approve else REJECTED

    # Ghi tệp + cơ sở dữ liệu do `catalog_sync` làm, KHÔNG làm ở đây.
    #
    # Mô-đun ấy sở hữu `samples.csv`: khoá tệp, thứ tự ghi, phép hoàn nguyên khi
    # hỏng, và phân vai "đọc thẩm quyền theo phạm vi / đọc tuần tự hoá toàn
    # cục". Bản đầu của hàm này tự làm cả bốn thứ đó, và
    # `test_file_backed_tenant_isolation` bắt được: một đường phục vụ request
    # không được tự đi đọc toàn kho. Nới danh sách cho phép sẽ làm bài kiểm im
    # đi mà không sửa điều nó chỉ ra.
    try:
        kq = sync_set_review_status(
            sid, trang_thai, tenant_id=tenant_id,
            reviewed_by=actor_id, note=note)
    except CatalogSyncError as exc:
        raise ModerationError(str(exc), status_code=exc.status_code) from exc

    thuoc_phien = kq["rows"]
    nguoi_dong_gop = next(
        (str(r["auth_user_id"]) for r in thuoc_phien if r.get("auth_user_id")), "")
    nhan = next((str(r.get("label_original") or "") for r in thuoc_phien), "")

    _bao_cho_nguoi_dong_gop(nguoi_dong_gop, approve=approve, nhan=nhan,
                            note=note, tenant_id=tenant_id)

    logger.info("[MODERATION] phien=%s -> %s (%d mau) boi %s",
                sid, trang_thai, kq["sample_count"], actor_id)
    return {
        "capture_session_id": sid,
        "review_status": trang_thai,
        "sample_count": kq["sample_count"],
        TENANT_COLUMN: tenant_id,
    }


def _bao_cho_nguoi_dong_gop(user_id: str, *, approve: bool, nhan: str,
                            note: str, tenant_id: str) -> None:
    """Người đóng góp phải biết kết quả.

    Thiếu thông báo này thì lời hứa "qua kiểm duyệt mới công khai" là vô hình
    với đúng người cần biết, và họ sẽ đi hỏi qua kênh hỗ trợ — biến một sự kiện
    tự động thành việc tay cho người trực.

    Best-effort: một lượt gửi hỏng KHÔNG được làm hỏng quyết định vừa ghi. Cùng
    nguyên tắc đã ghi ở `training_tasks.py`.
    """
    if not user_id:
        return
    try:
        from app import notifications

        if approve:
            notifications.notify(
                user_id, kind="moderation", severity="success",
                title="Dữ liệu của bạn đã được duyệt",
                body=f"Phần thu cho nhãn “{nhan}” đã được công khai.",
                link="/labels", tenant_id=tenant_id)
        else:
            notifications.notify(
                user_id, kind="moderation", severity="warning",
                title="Dữ liệu của bạn chưa được duyệt",
                body=f"Phần thu cho nhãn “{nhan}”: {note.strip()}",
                link="/labels", tenant_id=tenant_id)
    except Exception:
        logger.exception("[MODERATION] khong gui duoc thong bao ket qua cho %s", user_id)
