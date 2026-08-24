"""Quản lý PHIÊN THU — `capture_sessions` (UC12).

Tệp này tên là `collection_sessions.py` cho tới 24/08/2026, và cái tên ấy đã
thành bẫy: ngày 23/08 lược đồ có thêm một bảng THẬT tên `collection_sessions`
với nghĩa khác hẳn — BUỔI thu, tầng cha gom nhiều `capture_sessions` cùng một
mã phiên. Hai khái niệm, một cái tên.

    collection_sessions   buổi thu   1 mã phiên trình duyệt, N phiên thu
    capture_sessions      phiên thu  1 lớp, N mẫu          <- tệp này

Đường dẫn HTTP giữ nguyên `/sessions`: đổi nó sẽ phá giao diện, còn cái sai
nằm ở tên mô-đun chứ không ở URL.

Bảng `capture_sessions` có từ lược đồ v3 và đang giữ 250 dòng thật, nhưng chưa
màn hình nào đọc nó. Phiên thu tới giờ chỉ nhìn thấy được GIÁN TIẾP: mở trang
chi tiết một nhãn thì thấy các lần quay CỦA NHÃN ĐÓ. Không có chỗ nào trả lời
được "hôm qua tôi thu những gì", "phiên nào chưa đóng", hay "ai thu phiên này".

Khoá của một phiên là CẶP (class_uid, session_id), không phải riêng session_id
--------------------------------------------------------------------------------
Một lượt ngồi trước máy quay có thể đi qua nhiều nhãn, và mỗi nhãn mở một dòng
riêng — nên 57 `session_id` khác nhau đang trải ra thành 250 dòng. Gộp theo
`session_id` một mình sẽ trộn mẫu của nhiều lớp vào một hàng và làm số mẫu sai.

Phạm vi: người dùng thường thấy phiên CỦA MÌNH (theo `auth_user_id`), người có
quyền biên tập thấy cả tenant. Không ai thấy phiên của tenant khác — truy vấn
đều mang `tenant_id` tường minh chứ không dựa vào RLS một mình.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status  # pyright: ignore[reportMissingImports]
from pydantic import BaseModel, Field  # pyright: ignore[reportMissingImports]

from app import activity
from app.auth import get_current_user
from app.storage.metadata_db import _execute, _fetch_all
from app.tenant_context import require_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["capture-sessions"])


class SessionRow(BaseModel):
    capture_session_id: str
    session_id: str
    class_uid: str
    label: Optional[str] = None
    dialect: Optional[str] = None
    signer_id: Optional[str] = None
    signer_name: Optional[str] = None
    contributor: Optional[str] = None
    source_type: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    note: Optional[str] = None
    sample_count: int = 0
    is_open: bool = False
    is_mine: bool = False


class SessionsResponse(BaseModel):
    sessions: List[SessionRow]
    tenant_id: str
    total: int
    open_count: int
    scope: str  # "mine" | "tenant"


class SessionUpdate(BaseModel):
    #: Đóng phiên. Chỉ đi một chiều: đã đóng thì không mở lại được từ đây, vì
    #: "mở lại" nghĩa là gắn thêm mẫu vào một phiên đã kết thúc — và thời điểm
    #: kết thúc là một dữ kiện của lịch sử thu, không phải một ô cấu hình.
    close: Optional[bool] = None
    note: Optional[str] = Field(None, max_length=500)


def _is_editor(user: Dict[str, Any]) -> bool:
    if user.get("is_admin"):
        return True
    return str(user.get("tenant_role") or "").lower() in ("admin", "editor", "owner")


@router.get("", response_model=SessionsResponse)
def list_sessions(
    # `Literal`, KHÔNG phải `Query(pattern=...)`: bản FastAPI/pydantic ở đây spell
    # ràng buộc ấy là `regex`, và nó NUỐT `pattern` lạ mà không cưỡng chế gì —
    # tức lược đồ hứa một điều nó không thi hành. Xem chú thích cùng nội dung ở
    # `routers/tenants.py :: request_export`.
    scope: Literal["auto", "mine", "tenant"] = Query("auto"),
    limit: int = Query(200, ge=1, le=1000),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Phiên thu, kèm số mẫu đếm lại từ chính bảng `samples`.

    Số mẫu KHÔNG lưu trong `capture_sessions` mà đếm mỗi lần hỏi. Một con số
    lưu sẵn sẽ lệch ngay lần đầu ai đó xoá mẫu, và một bảng nói "20 mẫu" bên
    cạnh một danh sách 17 dòng là thứ không ai biết nên tin bên nào.
    """
    tenant = require_tenant()
    uid = str(current_user.get("id") or "")
    editor = _is_editor(current_user)
    want = scope if scope != "auto" else ("tenant" if editor else "mine")
    if want == "tenant" and not editor:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            detail="Chỉ người có quyền biên tập mới xem được phiên của cả tổ chức")

    # Thứ tự tham số phải khớp thứ tự dấu %s trong câu dưới, và câu ấy có tenant
    # ở HAI chỗ (một trong truy vấn con đếm mẫu, một ở mệnh đề WHERE ngoài).
    # Viết thẳng danh sách ra đây thay vì cộng dồn nhiều mảnh: một tham số lệch
    # chỗ trong truy vấn này không báo lỗi, nó chỉ trả về kết quả của tenant khác.
    where_mine = ""
    params: List[Any] = [tenant, tenant]      # (1) truy vấn con, (2) WHERE ngoài
    if want == "mine":
        where_mine = "AND cs.auth_user_id = %s"
        params.append(uid)                    # (3) chỉ khi lọc theo người dùng
    params.append(limit)                      # (4) LIMIT

    rows = _fetch_all(
        f"""
        SELECT cs.capture_session_id, cs.session_id, cs.class_uid, cs.signer_id,
               cs.auth_user_id, cs.source_type, cs.started_at, cs.ended_at, cs.note,
               c.label_original, c.dialect,
               u.username AS contributor,
               s.signer_name,
               COALESCE(n.cnt, 0) AS sample_count
          FROM capture_sessions cs
          LEFT JOIN classes c
                 ON c.tenant_id = cs.tenant_id AND c.class_uid = cs.class_uid
          LEFT JOIN users u ON u.id = cs.auth_user_id
          LEFT JOIN (SELECT signer_id, display_name AS signer_name FROM signers) s
                 ON s.signer_id = cs.signer_id
          LEFT JOIN (
                SELECT class_uid, session_id, COUNT(*) AS cnt
                  FROM samples
                 WHERE tenant_id = %s AND (deleted_at IS NULL)
                 GROUP BY class_uid, session_id
               ) n ON n.class_uid = cs.class_uid AND n.session_id = cs.session_id
         WHERE cs.tenant_id = %s {where_mine}
         ORDER BY cs.started_at DESC NULLS LAST, cs.created_at DESC
         LIMIT %s
        """,
        tuple(params),
    )

    out: List[SessionRow] = []
    for r in rows:
        out.append(SessionRow(
            capture_session_id=str(r["capture_session_id"]),
            session_id=r["session_id"],
            class_uid=r["class_uid"],
            label=r.get("label_original"),
            dialect=r.get("dialect"),
            signer_id=r.get("signer_id") or None,
            signer_name=r.get("signer_name") or None,
            contributor=r.get("contributor") or None,
            source_type=r.get("source_type") or None,
            started_at=r["started_at"].isoformat() if r.get("started_at") else None,
            ended_at=r["ended_at"].isoformat() if r.get("ended_at") else None,
            note=r.get("note") or None,
            sample_count=int(r.get("sample_count") or 0),
            is_open=r.get("ended_at") is None,
            is_mine=str(r.get("auth_user_id") or "") == uid,
        ))

    return SessionsResponse(
        sessions=out,
        tenant_id=tenant,
        total=len(out),
        open_count=len([r for r in out if r.is_open]),
        scope=want,
    )


@router.patch("/{capture_session_id}")
def update_session(
    capture_session_id: str,
    body: SessionUpdate,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Đóng một phiên, hoặc ghi chú lại điều kiện thu của nó.

    Quyền: chủ phiên, hoặc người có quyền biên tập. Kiểm bằng `auth_user_id`
    chứ không bằng tên hiển thị — hai người trùng tên là chuyện có thật trong
    kho này, và một phép kiểm theo tên sẽ cho người nọ sửa phiên người kia.
    """
    tenant = require_tenant()
    uid = str(current_user.get("id") or "")

    found = _fetch_all(
        "SELECT capture_session_id, auth_user_id, ended_at FROM capture_sessions "
        "WHERE tenant_id = %s AND capture_session_id = %s",
        (tenant, capture_session_id),
    )
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không có phiên thu này")
    row = found[0]
    if str(row.get("auth_user_id") or "") != uid and not _is_editor(current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Phiên này không phải của bạn")

    if body.close and row.get("ended_at") is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Phiên đã đóng rồi")

    sets: List[str] = []
    params: List[Any] = []
    if body.close:
        sets.append("ended_at = NOW()")
    if body.note is not None:
        sets.append("note = %s")
        params.append(body.note.strip() or None)
    if not sets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Không có gì để sửa")

    params.extend([tenant, capture_session_id])
    _execute(
        f"UPDATE capture_sessions SET {', '.join(sets)} "
        f"WHERE tenant_id = %s AND capture_session_id = %s",
        tuple(params),
    )

    activity.log_security_event(
        "collection_session.updated", actor=str(current_user.get("username", "")),
        target=capture_session_id,
        extra={"closed": bool(body.close), "note_set": body.note is not None},
        actor_user=current_user, request=request)

    return {"capture_session_id": capture_session_id, "closed": bool(body.close)}
