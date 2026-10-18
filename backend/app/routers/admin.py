from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.modules.admin.user_service import list_users, set_user_admin_role
from app.modules.identity import require_admin
from app.monitoring import collect_resources
from app import activity
from app.routers.admin_data import (
    get_data_report,
    get_sync_status,
    router as data_router,
    sync_local_files,
)

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(data_router)

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
    return list_users()

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

    updated = set_user_admin_role(user_id, payload.is_admin)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy người dùng",
        )
    return {"status": "success", "user": updated}

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
