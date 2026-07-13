from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import get_current_user, require_admin
from app.storage.postgres_connection import connect_postgres
from psycopg2.extras import RealDictCursor
from app.sync_tasks import download_missing_files_to_local
from app.monitoring import collect_resources
from app import activity

router = APIRouter(prefix="/admin", tags=["admin"])

class UserRoleUpdate(BaseModel):
    is_admin: bool

class IPAction(BaseModel):
    ip: str
    reason: str = ""
    duration_seconds: int = 0  # 0 => permanent

class ForceLogout(BaseModel):
    user_id: str
    reason: str = ""

class LockUser(BaseModel):
    reason: str = ""
    duration_seconds: int = 0  # 0 => until manually unlocked

class WarnUser(BaseModel):
    message: str

@router.get("/users")
def get_all_users(current_user: Dict[str, Any] = Depends(require_admin)):
    """Lấy danh sách tất cả người dùng (Chỉ Admin)"""
    conn = connect_postgres()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, username, email, is_active, is_admin, created_at
                    FROM users
                    ORDER BY created_at DESC
                    """
                )
                users = cur.fetchall()
                locked = activity.list_locked_users()
                warned = activity.list_warned_users()
                # Chuyển đổi UUID/datetime sang string để FastAPI tự serialize
                for u in users:
                    u["id"] = str(u["id"])
                    if u["created_at"]:
                        u["created_at"] = u["created_at"].isoformat()
                    lk = locked.get(u["id"])
                    u["locked"] = bool(lk)
                    u["lock_reason"] = (lk or {}).get("reason", "")
                    u["lock_until"] = (lk or {}).get("until", 0)
                    u["has_warning"] = u["id"] in warned
                return users
    finally:
        conn.close()

@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: str, 
    payload: UserRoleUpdate,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Cập nhật quyền của người dùng (Chỉ Admin)"""
    # Không cho phép tự gỡ quyền admin của chính mình
    if str(user_id) == str(current_user["id"]) and not payload.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự gỡ quyền Admin của chính mình."
        )

    conn = connect_postgres()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "UPDATE users SET is_admin = %s WHERE id = %s RETURNING id, username, is_admin",
                    (payload.is_admin, user_id)
                )
                updated = cur.fetchone()
                if not updated:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Không tìm thấy người dùng"
                    )
                return {"status": "success", "user": {"id": str(updated["id"]), "username": updated["username"], "is_admin": updated["is_admin"]}}
    finally:
        conn.close()

@router.get("/resources")
def get_resources(current_user: Dict[str, Any] = Depends(require_admin)):
    """Live resource snapshot for the admin monitor (Chỉ Admin).

    Host CPU/RAM (psutil), GPU (published to Redis by the trainer's sampler),
    the running training job, Redis memory, and threshold-based alerts.
    """
    return collect_resources()


@router.get("/activity")
def get_activity(current_user: Dict[str, Any] = Depends(require_admin)):
    """Active sessions (IP, user, location, usage) + anomalies + blocklist."""
    return activity.activity_report(limit=150)


@router.post("/block-ip")
def block_ip(payload: IPAction, current_user: Dict[str, Any] = Depends(require_admin)):
    """Block a client IP (optionally timed) — the gateway refuses its requests (403)."""
    ip = (payload.ip or "").strip()
    if not ip:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu địa chỉ IP")
    by = current_user.get("username", "")
    ok = activity.block_ip(ip, by=by, reason=payload.reason, duration_seconds=payload.duration_seconds)
    if ok:
        activity.log_security_event("block_ip", actor=by, target=ip, reason=payload.reason,
                                    extra={"duration_seconds": payload.duration_seconds})
    return {"status": "success" if ok else "error", "ip": ip, "blocked": ok}


@router.post("/unblock-ip")
def unblock_ip(payload: IPAction, current_user: Dict[str, Any] = Depends(require_admin)):
    """Remove a client IP from the blocklist."""
    ip = (payload.ip or "").strip()
    if not ip:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu địa chỉ IP")
    ok = activity.unblock_ip(ip)
    if ok:
        activity.log_security_event("unblock_ip", actor=current_user.get("username", ""), target=ip)
    return {"status": "success" if ok else "error", "ip": ip, "blocked": False}


@router.post("/force-logout")
def force_logout(payload: ForceLogout, current_user: Dict[str, Any] = Depends(require_admin)):
    """Invalidate a user's live sessions (revoke refresh tokens + deny tokens)."""
    uid = (payload.user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu user_id")
    if str(uid) == str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Không thể tự đăng xuất chính mình bằng công cụ này")
    by = current_user.get("username", "")
    activity.force_logout_user(uid, by=by, reason=payload.reason)
    activity.log_security_event("force_logout", actor=by, target=uid, reason=payload.reason)
    return {"status": "success", "user_id": uid}


@router.post("/users/{user_id}/lock")
def lock_user_account(user_id: str, payload: LockUser, current_user: Dict[str, Any] = Depends(require_admin)):
    """Disable a user account (optionally timed) and end its live sessions."""
    uid = (user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu user_id")
    if str(uid) == str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Không thể tự khóa tài khoản của chính mình")
    by = current_user.get("username", "")
    ok = activity.lock_user(uid, by=by, reason=payload.reason, duration_seconds=payload.duration_seconds)
    if ok:
        activity.log_security_event("lock_user", actor=by, target=uid, reason=payload.reason,
                                    extra={"duration_seconds": payload.duration_seconds})
    return {"status": "success" if ok else "error", "user_id": uid, "locked": ok}


@router.post("/users/{user_id}/unlock")
def unlock_user_account(user_id: str, current_user: Dict[str, Any] = Depends(require_admin)):
    """Re-enable a locked user account."""
    ok = activity.unlock_user(user_id)
    if ok:
        activity.log_security_event("unlock_user", actor=current_user.get("username", ""), target=user_id)
    return {"status": "success" if ok else "error", "user_id": user_id, "locked": False}


@router.post("/users/{user_id}/warn")
def warn_user_account(user_id: str, payload: WarnUser, current_user: Dict[str, Any] = Depends(require_admin)):
    """Queue a warning message the user sees on their next visit."""
    msg = (payload.message or "").strip()
    if not msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu nội dung cảnh báo")
    by = current_user.get("username", "")
    ok = activity.warn_user(user_id, by=by, message=msg)
    if ok:
        activity.log_security_event("warn_user", actor=by, target=user_id, reason=msg)
    return {"status": "success" if ok else "error", "user_id": user_id}


@router.get("/security-log")
def get_security_log(current_user: Dict[str, Any] = Depends(require_admin)):
    """Recent admin security actions (block / unblock / force-logout)."""
    return {"events": activity.list_security_log(limit=150)}


@router.get("/data-report")
def get_data_report(current_user: Dict[str, Any] = Depends(require_admin)):
    """Dataset dashboard: totals, per-label / per-region / per-source breakdowns,
    top contributors, and the most recent samples."""
    from collections import Counter
    from app.dataset_manager import list_classes
    from app.dataset_samples import list_samples

    metas = list_classes()
    samples = list_samples()

    label_c: Counter = Counter()
    region_c: Counter = Counter()
    source_c: Counter = Counter()
    contrib_c: Counter = Counter()
    for s in samples:
        label_c[(s.get("label_original") or s.get("slug") or "?").strip() or "?"] += 1
        region_c[(s.get("dialect") or "").strip() or "khác"] += 1
        source_c[(s.get("source_type") or "").strip() or "khác"] += 1
        uid = (s.get("user_id") or "").strip()
        if uid:
            contrib_c[uid] += 1

    regions = {(getattr(m, "dialect", "") or "").strip() for m in metas}
    regions.discard("")

    top_ids = [uid for uid, _ in contrib_c.most_common(10)]
    umap = activity._resolve_usernames(set(top_ids))
    top_contributors = [
        {"user_id": uid, "username": (umap.get(uid) or {}).get("username") or uid[:8], "count": cnt}
        for uid, cnt in contrib_c.most_common(10)
    ]

    recent = sorted(samples, key=lambda s: str(s.get("created_at") or ""), reverse=True)[:12]
    recent_out = [{
        "label": r.get("label_original") or r.get("slug"),
        "dialect": r.get("dialect"),
        "source": r.get("source_type"),
        "created_at": str(r.get("created_at") or ""),
    } for r in recent]

    return {
        "labels_count": len(metas),
        "total_samples": len(samples),
        "contributors_count": len(contrib_c),
        "regions_count": len(regions),
        "top_labels": [{"label": l, "count": c} for l, c in label_c.most_common(12)],
        "by_region": [{"region": r, "count": c} for r, c in region_c.most_common()],
        "by_source": [{"source": s, "count": c} for s, c in source_c.most_common()],
        "top_contributors": top_contributors,
        "recent": recent_out,
    }


@router.post("/sync-local")
def sync_local_files(current_user: Dict[str, Any] = Depends(require_admin)):
    """Trigger task tải các file feature và raw video thiếu từ Google Drive về local"""
    task = download_missing_files_to_local.delay()
    return {
        "status": "success",
        "message": "Đã bắt đầu quá trình đồng bộ hóa file về server",
        "task_id": task.id
    }

@router.get("/sync-status/{task_id}")
def get_sync_status(task_id: str, current_user: Dict[str, Any] = Depends(require_admin)):
    """Kiểm tra trạng thái tiến trình đồng bộ"""
    from celery.result import AsyncResult
    task = AsyncResult(task_id)
    
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'current': 0,
            'total': 1,
            'status': 'Pending...'
        }
    elif task.state == 'PROGRESS':
        response = {
            'state': task.state,
            'current': task.info.get('current', 0),
            'total': task.info.get('total', 1),
            'downloaded': task.info.get('downloaded', 0),
            'skipped': task.info.get('skipped', 0),
            'errors': task.info.get('errors', 0)
        }
    elif task.state == 'SUCCESS':
        response = {
            'state': task.state,
            'current': task.info.get('current', 1),
            'total': task.info.get('total', 1),
            'downloaded': task.info.get('downloaded', 0),
            'skipped': task.info.get('skipped', 0),
            'errors': task.info.get('errors', 0)
        }
    else:
        # FAILURE or others
        response = {
            'state': task.state,
            'status': str(task.info)
        }
    
    return response
