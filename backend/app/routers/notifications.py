"""Trung tâm thông báo trong ứng dụng.

Mọi đường ở đây đều gắn với NGƯỜI ĐANG ĐĂNG NHẬP. Không có tham số `user_id`
nào nhận từ ngoài — một API thông báo cho phép chỉ định người khác là một API
đọc trộm.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app import notifications
from app.auth import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


class MarkReadRequest(BaseModel):
    ids: List[str] = Field(default_factory=list, max_items=200)


@router.get("")
def list_notifications(
    limit: int = Query(30, ge=1, le=100),
    unread_only: bool = Query(False),
    before: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Danh sách thông báo, mới nhất trước, kèm số chưa đọc."""
    return {
        "items": notifications.list_for_user(
            current_user["id"], limit=limit,
            unread_only=unread_only, before=before),
        "unread": notifications.unread_count(current_user["id"]),
    }


@router.get("/unread-count")
def get_unread_count(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Chỉ con số, cho cái chuông trên thanh điều hướng.

    Tách khỏi `GET /notifications` vì giao diện hỏi nó theo chu kỳ: trả về cả
    danh sách mỗi lần là gửi thừa vài chục kilobyte để hiển thị một chữ số.
    """
    return {"unread": notifications.unread_count(current_user["id"])}


@router.post("/read")
def mark_read(payload: MarkReadRequest,
              current_user: Dict[str, Any] = Depends(get_current_user)):
    return {"updated": notifications.mark_read(current_user["id"], payload.ids)}


@router.post("/read-all")
def mark_all_read(current_user: Dict[str, Any] = Depends(get_current_user)):
    return {"updated": notifications.mark_all_read(current_user["id"])}


@router.get("/kinds")
def list_kinds():
    """Loại thông báo kèm lý do tồn tại — giao diện dùng để chú giải bộ lọc."""
    return {"kinds": notifications.KINDS}
