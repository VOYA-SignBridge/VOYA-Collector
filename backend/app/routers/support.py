"""Kênh hỗ trợ: người dùng mở phiếu, người trực trả lời.

Một router, hai vai. Vai được quyết định bởi `current_user["is_admin"]` ở phía
máy chủ, không bao giờ bởi tham số của yêu cầu — nếu không thì bất kỳ ai cũng tự
xưng là người trực và đọc phiếu của người khác.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app import support, support_bot
from app.auth import get_current_user, require_admin

router = APIRouter(prefix="/support", tags=["support"])


class CreateTicketRequest(BaseModel):
    subject: str = Field(..., min_length=5, max_length=200)
    body: str = Field(..., min_length=10, max_length=10000)
    category: str = Field("other")


class ReplyRequest(BaseModel):
    body: str = Field(..., min_length=2, max_length=10000)


class StatusRequest(BaseModel):
    status: str


def _label(user: Dict[str, Any]) -> str:
    return str(user.get("username") or user.get("email") or "không rõ")


def _bad_request(exc: support.SupportError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/categories")
def categories():
    return {"categories": list(support.CATEGORIES), "statuses": list(support.STATUSES)}


@router.get("/starters")
def starters(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Chip câu hỏi nhanh cho ô soạn hội thoại mới.

    Lấy từ máy chủ chứ không viết cứng trong giao diện: chúng phải khớp với
    bảng luật của trợ lý (`app/support_bot.py`). Một chip không khớp luật nào
    là một cái bẫy — người dùng bấm vào rồi nhận đúng câu "tôi chưa hiểu".
    """
    return {"starters": support_bot.starters(),
            "escape": support_bot.ESCAPE_CHIP}


@router.get("/tickets")
def my_tickets(status_filter: Optional[str] = Query(None, alias="status"),
               current_user: Dict[str, Any] = Depends(get_current_user)):
    """Phiếu của chính người đang đăng nhập."""
    return {"items": support.list_tickets(
        user_id=current_user["id"], status=status_filter)}


@router.post("/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(payload: CreateTicketRequest,
                  current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        return support.create_ticket(
            current_user["id"], payload.subject, payload.body,
            category=payload.category, author_label=_label(current_user))
    except support.SupportError as exc:
        raise _bad_request(exc)


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str,
               current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        return support.get_ticket(
            ticket_id, current_user["id"],
            as_staff=bool(current_user.get("is_admin")))
    except support.SupportError as exc:
        # 404, không phải 403: phân biệt "không có" với "không được xem" cho
        # phép dò xem một mã phiếu có tồn tại hay không.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/tickets/{ticket_id}/reply")
def reply(ticket_id: str, payload: ReplyRequest,
          current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        return support.reply(
            ticket_id, current_user["id"], payload.body,
            author_label=_label(current_user),
            is_staff=bool(current_user.get("is_admin")))
    except support.SupportError as exc:
        raise _bad_request(exc)


@router.post("/tickets/{ticket_id}/status")
def set_status(ticket_id: str, payload: StatusRequest,
               current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        return support.set_status(
            ticket_id, payload.status, current_user["id"],
            is_staff=bool(current_user.get("is_admin")))
    except support.SupportError as exc:
        raise _bad_request(exc)


@router.get("/queue")
def staff_queue(status_filter: Optional[str] = Query("open", alias="status"),
                _admin: Dict[str, Any] = Depends(require_admin)):
    """Hàng đợi của người trực. `user_id=None` nghĩa là mọi phiếu.

    Vẫn nằm trong ranh giới tenant: `support_tickets` chịu row-level security,
    nên "mọi phiếu" ở đây là mọi phiếu CỦA TENANT NÀY.
    """
    return {"items": support.list_tickets(user_id=None, status=status_filter)}
