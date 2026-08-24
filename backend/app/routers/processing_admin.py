"""Theo dõi HÀNG ĐỢI xử lý (UC16 — Monitor Processing).

`/admin/resources` đã có từ lâu, nhưng nó đo MÁY: CPU, RAM, GPU, đĩa. Câu hỏi
của UC16 là câu khác — *việc* đang chạy tới đâu, việc nào hỏng, việc nào đang
xếp hàng — và không màn hình nào trả lời được câu đó. Đây là màn hình ấy.

Một luật xuyên suốt: **không đo được thì nói là không đo được.** Celery trả lời
qua broadcast, và một worker bận hoặc vừa chết sẽ không trả lời trong hạn. Khi
đó endpoint này trả `null` kèm lý do chứ không trả `0` — vì `0` đọc như "hàng
đợi trống", đúng cái kết luận ngược với sự thật.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status  # pyright: ignore[reportMissingImports]
from pydantic import BaseModel, Field  # pyright: ignore[reportMissingImports]

from app import activity
from app.auth import require_tenant_editor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/processing", tags=["admin", "processing"])

#: Các hàng đợi mà hệ thống này thực sự dùng. Đếm chiều dài bằng LLEN trên
#: broker Redis: đó là số việc ĐÃ nhận nhưng CHƯA worker nào nhấc lên, thứ mà
#: `inspect` không thấy (inspect chỉ hỏi được worker đang sống).
_QUEUES = ("celery", "training", "preview")


class TaskRow(BaseModel):
    task_id: str
    name: str
    worker: str
    state: str            # "running" | "reserved" | "scheduled"
    args_preview: str = ""
    time_start: Optional[float] = None


class QueueDepth(BaseModel):
    name: str
    #: `None` = không đo được (không phải 0).
    depth: Optional[int] = None
    error: Optional[str] = None


class ProcessingSnapshot(BaseModel):
    workers: List[str]
    #: `None` khi không worker nào trả lời trong hạn — KHÁC với danh sách rỗng,
    #: vốn có nghĩa "có worker và nó đang rảnh".
    reachable: bool
    unreachable_reason: Optional[str] = None
    running: List[TaskRow]
    reserved: List[TaskRow]
    queues: List[QueueDepth]
    recent_failures: List[Dict[str, Any]]


class RevokeBody(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=200)
    terminate: bool = False


def _preview(args: Any) -> str:
    text = str(args or "")
    return text[:120] + ("…" if len(text) > 120 else "")


def _rows(payload: Optional[Dict[str, List[Dict[str, Any]]]], state: str) -> List[TaskRow]:
    out: List[TaskRow] = []
    for worker, tasks in (payload or {}).items():
        for tk in tasks or []:
            out.append(TaskRow(
                task_id=str(tk.get("id") or ""),
                name=str(tk.get("name") or "?"),
                worker=str(worker),
                state=state,
                args_preview=_preview(tk.get("args")),
                time_start=tk.get("time_start"),
            ))
    return out


@router.get("", response_model=ProcessingSnapshot)
def processing_snapshot(current_user: Dict[str, Any] = Depends(require_tenant_editor)):
    """Ảnh chụp hàng đợi: worker nào sống, việc nào chạy, việc nào đang chờ."""
    from app.worker import celery_app

    workers: List[str] = []
    running: List[TaskRow] = []
    reserved: List[TaskRow] = []
    reachable = True
    reason: Optional[str] = None

    try:
        insp = celery_app.control.inspect(timeout=2.0)
        active = insp.active()
        res = insp.reserved()
        if active is None and res is None:
            # Không worker nào trả lời. Đây KHÔNG phải "không có việc" — đó là
            # "không hỏi được", và hai thứ đó phải hiện khác nhau.
            reachable = False
            reason = "Không worker nào trả lời trong 2 giây"
        else:
            workers = sorted(set(list((active or {}).keys()) + list((res or {}).keys())))
            running = _rows(active, "running")
            reserved = _rows(res, "reserved")
    except Exception as exc:
        reachable = False
        reason = f"Không hỏi được worker: {exc}"
        logger.warning("[PROCESSING] inspect that bai: %s", exc)

    queues: List[QueueDepth] = []
    try:
        import redis  # pyright: ignore[reportMissingImports]
        from app.config import settings

        client = redis.Redis.from_url(settings.broker_url, socket_timeout=2)
        for q in _QUEUES:
            try:
                queues.append(QueueDepth(name=q, depth=int(client.llen(q))))
            except Exception as exc:
                queues.append(QueueDepth(name=q, depth=None, error=str(exc)))
    except Exception as exc:
        queues = [QueueDepth(name=q, depth=None, error=str(exc)) for q in _QUEUES]

    # Việc HỎNG gần đây. Celery không giữ sổ việc hỏng nếu không có backend kết
    # quả, nên chỗ này đọc nhật ký quản trị — nguồn duy nhất có thật.
    failures: List[Dict[str, Any]] = []
    try:
        from app.storage.metadata_db import _fetch_all

        failures = _fetch_all(
            "SELECT action, target, reason, created_at FROM audit_log "
            "WHERE action LIKE 'task.%%failed%%' ORDER BY created_at DESC LIMIT 20"
        )
    except Exception as exc:
        logger.debug("[PROCESSING] khong doc duoc nhat ky loi: %s", exc)

    return ProcessingSnapshot(
        workers=workers,
        reachable=reachable,
        unreachable_reason=reason,
        running=running,
        reserved=reserved,
        queues=queues,
        recent_failures=failures,
    )


@router.post("/revoke")
def revoke_task(body: RevokeBody, request: Request,
                current_user: Dict[str, Any] = Depends(require_tenant_editor)):
    """Huỷ một việc đang chờ, hoặc dừng hẳn một việc đang chạy.

    `terminate=False` chỉ gỡ việc khỏi hàng đợi — việc đã bắt đầu vẫn chạy nốt.
    `terminate=True` giết tiến trình đang chạy nó, và đó là thao tác có thể để
    lại công việc dở dang, nên giao diện phải hỏi lại trước khi gọi.
    """
    from app.worker import celery_app

    try:
        celery_app.control.revoke(body.task_id, terminate=body.terminate)
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=f"Không gửi được lệnh huỷ: {exc}")

    activity.log_security_event(
        "processing.task_revoked", actor=str(current_user.get("username", "")),
        target=body.task_id, extra={"terminate": body.terminate},
        actor_user=current_user, request=request)
    return {"task_id": body.task_id, "terminated": body.terminate}
