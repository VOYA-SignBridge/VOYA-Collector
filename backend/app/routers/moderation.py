"""API kiểm duyệt: hàng đợi, Duyệt, Từ chối.

Xem docs/01-architecture/COMMUNITY_MODERATION.md §6, §7.

Vì sao KHÔNG dùng `require_admin`
----------------------------------
Người kiểm duyệt là chuyên gia được mời, không phải quản trị viên nền tảng. Bắt
họ phải là admin để duyệt dữ liệu nghĩa là hoặc không ai duyệt được, hoặc phải
cấp quyền toàn nền tảng cho một người chỉ cần xem cử chỉ và bấm một trong hai
nút. `moderation_admin.can_moderate` hỏi đúng câu cần hỏi.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from app import audit, moderation_admin
from app.auth import get_current_user
from app.tenant_context import require_tenant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/moderation", tags=["moderation"])


def require_moderator(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Chặn ở tầng router, và đây là phép kiểm THẬT chứ không phải trang trí.

    Vỏ giao diện ẩn mục Kiểm duyệt với người không có quyền, nhưng ẩn không
    phải chặn — một lệnh `curl` không đọc thanh bên.
    """
    if not moderation_admin.can_moderate(current_user):
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền kiểm duyệt dữ liệu.",
        )
    return current_user


class Decision(BaseModel):
    #: Bắt buộc khi từ chối — `decide_session` cưỡng chế, không phải chỗ này.
    #: Kiểm ở tầng dịch vụ để một lời gọi từ dòng lệnh cũng phải qua cùng luật.
    note: str = Field("", max_length=2000)


@router.get("/queue")
def queue(
    limit: int = Query(100, ge=1, le=500),
    _: Dict[str, Any] = Depends(require_moderator),
) -> Dict[str, Any]:
    """Các phiên thu đang chờ duyệt, cũ nhất trước.

    Trả về cả `count` lẫn `items`: huy hiệu trên thanh bên cần con số mà không
    cần tải danh sách, và hai bên phải đến từ CÙNG một ảnh chụp — lệch nhau thì
    huy hiệu nói 5 trong khi màn hình có 4 dòng.
    """
    tenant = require_tenant()
    items = moderation_admin.list_pending_sessions(tenant, limit=limit)
    return {
        "count": moderation_admin.pending_session_count(tenant),
        "items": items,
    }


@router.post("/sessions/{capture_session_id}/approve")
def approve(
    request: Request,
    capture_session_id: str = Path(..., max_length=64),
    payload: Decision = Body(default=Decision()),
    current_user: Dict[str, Any] = Depends(require_moderator),
) -> Dict[str, Any]:
    """Công khai một phiên thu: mọi mẫu trong phiên thành `approved`."""
    return _decide(request, capture_session_id, True, payload, current_user)


@router.post("/sessions/{capture_session_id}/reject")
def reject(
    request: Request,
    capture_session_id: str = Path(..., max_length=64),
    payload: Decision = Body(...),
    current_user: Dict[str, Any] = Depends(require_moderator),
) -> Dict[str, Any]:
    """Từ chối một phiên thu. **Không xoá gì.**

    Dữ liệu vẫn thuộc về người đóng góp và họ vẫn dùng được cho riêng mình —
    chỉ không được dùng chung. Lý do là bắt buộc: một lượt từ chối không nói vì
    sao thì người đóng góp không có gì để sửa.
    """
    return _decide(request, capture_session_id, False, payload, current_user)


def _decide(request: Request, session_id: str, approve_it: bool,
            payload: Decision, user: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = moderation_admin.decide_session(
            session_id,
            approve=approve_it,
            actor_id=str(user.get("id") or ""),
            tenant_id=require_tenant(),
            note=payload.note,
        )
    except moderation_admin.ModerationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    audit.record(
        "moderation.session.approved" if approve_it else "moderation.session.rejected",
        actor=user, request=request,
        target_type="capture_session", target_id=session_id,
        tenant_id=result["tenant_id"],
        detail={"sample_count": result["sample_count"],
                "note": payload.note.strip()[:200]},
    )
    return result
