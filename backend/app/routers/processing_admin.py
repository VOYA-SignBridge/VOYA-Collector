"""Theo dõi HÀNG ĐỢI xử lý (UC16 — Monitor Processing).

`/admin/resources` đã có từ lâu, nhưng nó đo MÁY: CPU, RAM, GPU, đĩa. Câu hỏi
của UC16 là câu khác — *việc* đang chạy tới đâu, việc nào hỏng, việc nào đang
xếp hàng — và không màn hình nào trả lời được câu đó. Đây là màn hình ấy.

Một luật xuyên suốt: **không đo được thì nói là không đo được.** Celery trả lời
qua broadcast, và một worker bận hoặc vừa chết sẽ không trả lời trong hạn. Khi
đó endpoint này trả `null` kèm lý do chứ không trả `0` — vì `0` đọc như "hàng
đợi trống", đúng cái kết luận ngược với sự thật.

Luật thứ hai: **worker dùng chung, danh sách việc thì không.** Mọi tổ chức gửi
việc vào cùng các worker, nên `celery inspect` trả việc của cả nền tảng. Trước
23/10/2026 endpoint này trả nguyên danh sách đó cho biên tập viên của BẤT KỲ tổ
chức nào, kèm 120 ký tự đầu tham số, và `/revoke` nhận mọi `task_id` — biên tập
viên trường A huỷ được việc đang chạy của trường B. Giờ:

  * người dùng tổ chức chỉ thấy và chỉ huỷ được việc gửi cho tổ chức ĐANG LÀM
    VIỆC của họ (tra trong `app.task_registry`)
  * việc không tra được chủ (việc nền tảng, việc cũ, sổ hết hạn) bị ẩn với họ —
    fail-closed
  * quản trị nền tảng thấy và huỷ được mọi việc (danh sách việc đến từ worker
    và sổ Redis, không qua RLS); việc HỎNG thì ai cũng chỉ đọc của tổ chức đang
    làm việc — router này không mở `system_scope`
  * chiều dài hàng đợi là con số TỔNG của cả nền tảng; nó không lộ nội dung việc
    nào nên vẫn hiện, và `queues_scope` nói rõ điều đó
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status  # pyright: ignore[reportMissingImports]
from pydantic import BaseModel, Field  # pyright: ignore[reportMissingImports]

from app.modules.security import audit_log
from app.modules.identity._web_compat import require_tenant_editor

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
    #: Tổ chức đã gửi việc; `None` = việc nền tảng hoặc không tra được.
    tenant_id: Optional[str] = None


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
    #: Khác `None` khi không đọc được nhật ký việc hỏng — khi đó danh sách rỗng
    #: nghĩa là "không biết", không phải "không có việc hỏng".
    recent_failures_error: Optional[str] = None
    #: "tenant": danh sách việc đã lọc theo tổ chức đang làm việc.
    #: "platform": quản trị nền tảng, thấy mọi việc.
    task_scope: Literal["tenant", "platform"]
    #: Chiều dài hàng đợi luôn là số của cả nền tảng.
    queues_scope: Literal["platform"] = "platform"


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


def _is_platform_admin(user: Dict[str, Any]) -> bool:
    # Khoá API luôn thuộc đúng một tổ chức, dù cờ trên dict là gì.
    return bool(user.get("is_admin")) and user.get("auth_method") != "api_key"


def _viewer_tenant(user: Dict[str, Any]) -> str:
    """Tổ chức đang làm việc của người gọi; fail-closed nếu không xác định được."""
    from app.modules.security.quota_deps import working_tenant_of
    from app.modules.saas.tenant_context import TenantScopeError

    try:
        tenant = (working_tenant_of(user) or "").strip()
    except TenantScopeError:
        tenant = ""
    if not tenant:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            detail="Không xác định được tổ chức của tài khoản.")
    return tenant


def _attach_owners(rows: List[TaskRow]) -> None:
    """Điền `tenant_id` cho từng dòng. Sổ không đọc được thì mọi dòng thành vô chủ."""
    from app import task_registry

    try:
        owners = task_registry.owners_of(r.task_id for r in rows)
    except Exception as exc:
        logger.warning("[PROCESSING] khong doc duoc so chu tac vu: %s", exc)
        owners = {}
    for r in rows:
        r.tenant_id = owners.get(r.task_id)


def _recent_failures(tenant: str) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """20 việc hỏng gần nhất của MỘT tổ chức, từ `audit_log` (do `worker.audit_task_failure` ghi).

    Trả về đúng hình dạng mà giao diện vẫn đọc (`action`, `target`, `reason`,
    `created_at`). Lọc bằng cả RLS lẫn vị từ tường minh — vị từ không thừa, nó
    là lớp thứ hai nếu phạm vi request bị đặt sai.

    Quản trị nền tảng cũng chỉ đọc tổ chức đang làm việc của mình, KHÔNG đọc
    trong `system_scope`. Bất biến của dự án là đúng một router HTTP được vượt
    ranh giới tenant (`sot_admin`, xem `test_no_router_crosses_the_boundary_
    except_the_documented_one`), và một màn hình theo dõi không đáng để mở cái
    thứ hai. Muốn xem tổ chức khác thì chuyển tổ chức đang làm việc; việc hỏng
    của tác vụ nền tảng (`tenant_id` NULL) nằm trong nhật ký vận hành.
    """
    from app.storage.metadata_db import _fetch_all

    try:
        rows = _fetch_all(
            "SELECT action, target_id, detail, created_at, tenant_id FROM audit_log "
            "WHERE action = 'task.failed' AND tenant_id = %s "
            "ORDER BY created_at DESC LIMIT 20",
            (tenant,),
        )
    except Exception as exc:
        logger.warning("[PROCESSING] khong doc duoc nhat ky viec hong: %s", exc)
        return [], f"Không đọc được nhật ký việc hỏng: {exc}"

    out: List[Dict[str, Any]] = []
    for r in rows:
        detail = r.get("detail") or {}
        out.append({
            "action": (detail.get("name") if isinstance(detail, dict) else None) or r.get("action"),
            "target": r.get("target_id") or "",
            "reason": (detail.get("error") if isinstance(detail, dict) else "") or "",
            "created_at": r.get("created_at"),
            "tenant_id": r.get("tenant_id"),
        })
    return out, None


@router.get("", response_model=ProcessingSnapshot)
def processing_snapshot(current_user: Dict[str, Any] = Depends(require_tenant_editor)):
    """Ảnh chụp hàng đợi: worker nào sống, việc nào chạy, việc nào đang chờ."""
    from app.worker import celery_app

    platform = _is_platform_admin(current_user)
    # Cả quản trị nền tảng cũng có tổ chức đang làm việc: việc hỏng đọc theo nó.
    tenant = _viewer_tenant(current_user)

    workers: List[str] = []
    running: List[TaskRow] = []
    reserved: List[TaskRow] = []
    reachable = True
    reason: Optional[str] = None

    try:
        insp = celery_app.control.inspect(timeout=2.0)
        # Mỗi lệnh đợi TRỌN `timeout` vì không biết còn worker nào sắp trả lời, nên
        # hỏi nối tiếp mất 4 giây, trên một trang tự gọi lại mỗi 5 giây.
        with ThreadPoolExecutor(max_workers=2) as pool:
            hoi_active, hoi_reserved = pool.submit(insp.active), pool.submit(insp.reserved)
            active, res = hoi_active.result(), hoi_reserved.result()
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

    _attach_owners(running + reserved)
    if not platform:
        running = [r for r in running if r.tenant_id == tenant]
        reserved = [r for r in reserved if r.tenant_id == tenant]

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

    failures, failures_error = _recent_failures(tenant)

    return ProcessingSnapshot(
        workers=workers,
        reachable=reachable,
        unreachable_reason=reason,
        running=running,
        reserved=reserved,
        queues=queues,
        recent_failures=failures,
        recent_failures_error=failures_error,
        task_scope="platform" if platform else "tenant",
    )


@router.post("/revoke")
def revoke_task(body: RevokeBody, request: Request,
                current_user: Dict[str, Any] = Depends(require_tenant_editor)):
    """Huỷ một việc đang chờ, hoặc dừng hẳn một việc đang chạy.

    `terminate=False` chỉ gỡ việc khỏi hàng đợi — việc đã bắt đầu vẫn chạy nốt.
    `terminate=True` giết tiến trình đang chạy nó, và đó là thao tác có thể để
    lại công việc dở dang, nên giao diện phải hỏi lại trước khi gọi.

    Người dùng tổ chức chỉ huỷ được việc mà sổ ghi là của tổ chức đang làm việc
    của họ. Mọi trường hợp khác — việc của tổ chức khác, việc nền tảng, việc
    không tra được, sổ không đọc được — đều trả 404 như thể việc không tồn
    tại: trả 403 sẽ xác nhận cho người gọi rằng `task_id` đó có thật.
    """
    from app.worker import celery_app

    platform = _is_platform_admin(current_user)
    if not platform:
        from app import task_registry

        tenant = _viewer_tenant(current_user)
        try:
            owner = task_registry.owners_of([body.task_id]).get(body.task_id)
        except Exception as exc:
            logger.warning("[PROCESSING] khong doc duoc so chu tac vu: %s", exc)
            owner = None
        if owner != tenant:
            # Lần bị từ chối cũng là bằng chứng: một biên tập viên dò `task_id`
            # của tổ chức khác là thứ cần thấy được khi điều tra.
            audit_log.log_security_event(
                "processing.task_revoke_denied",
                actor=str(current_user.get("username", "")),
                target=body.task_id, reason="task not owned by the caller's tenant",
                extra={"terminate": body.terminate},
                actor_user=current_user, request=request)
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tác vụ.")

    try:
        celery_app.control.revoke(body.task_id, terminate=body.terminate)
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=f"Không gửi được lệnh huỷ: {exc}")

    audit_log.log_security_event(
        "processing.task_revoked", actor=str(current_user.get("username", "")),
        target=body.task_id, extra={"terminate": body.terminate},
        actor_user=current_user, request=request)
    return {"task_id": body.task_id, "terminated": body.terminate}
