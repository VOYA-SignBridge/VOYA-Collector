from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.auth import get_current_user, require_admin
from app.storage.postgres_connection import connect_postgres
from psycopg2.extras import RealDictCursor
from app.sync_tasks import download_missing_files_to_local
from app.monitoring import collect_resources
from app import activity

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------- sudo mode
#
# Nâng quyền tạm thời cho thao tác nhạy cảm. Xem app/sudo_mode.py để biết vì sao
# là "nhập lại mật khẩu" chứ không phải một mã PIN quản trị dùng chung.

class SudoRequest(BaseModel):
    password: str


class SettingUpdate(BaseModel):
    value: int


@router.post("/sudo")
def elevate_privileges(
    payload: SudoRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Xác thực lại bằng mật khẩu để mở cửa sổ nâng quyền 5 phút."""
    from app import audit, sudo_mode

    try:
        ttl = sudo_mode.elevate(current_user, payload.password)
    except Exception:
        # Ghi cả lần THẤT BẠI, và ghi trước khi ném lại. Một chuỗi
        # `sudo.elevate.failed` là dấu hiệu có người đang ngồi trước phiên
        # không phải của họ; nếu chỉ ghi lần thành công thì đúng cái chuỗi
        # đáng chú ý nhất lại không để lại gì.
        audit.record("sudo.elevate.failed", actor=current_user, request=request)
        raise
    audit.record("sudo.elevate", actor=current_user, request=request,
                 detail={"ttl_seconds": ttl})
    return {"elevated": True, "ttl_seconds": ttl}


@router.delete("/sudo", status_code=status.HTTP_204_NO_CONTENT)
def drop_privileges(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Response:
    """Kết thúc cửa sổ nâng quyền sớm.

    Có endpoint này vì bước rời khỏi trạng thái nâng quyền phải rẻ. Không có nó,
    cách duy nhất là chờ hết 5 phút — và người vận hành cẩn thận sẽ không có
    cách nào dọn sau khi xong việc.
    """
    from app import audit, sudo_mode

    sudo_mode.revoke(str(current_user["id"]))
    audit.record("sudo.revoke", actor=current_user, request=request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/settings")
def read_settings(
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Thiết lập đổi được lúc chạy, kèm giá trị mặc định và biên.

    ĐỌC chỉ cần quyền quản trị, không cần nâng quyền: xem một con số không thay
    đổi gì, và bắt nâng quyền để xem sẽ khiến người ta nâng quyền theo thói quen
    — đúng thứ làm cho bước xác thực lại mất ý nghĩa.
    """
    from app import platform_settings, sudo_mode

    return {
        "settings": platform_settings.current(),
        "sudo_seconds_remaining": sudo_mode.seconds_remaining(str(current_user["id"])),
    }


@router.put("/settings/{key}")
def write_setting(
    key: str,
    payload: SettingUpdate,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Đổi một thiết lập. **Cần nâng quyền.**

    `require_sudo` được gọi trong thân hàm chứ không phải qua `Depends`, vì nó
    tự phụ thuộc `require_admin` và khai báo cả hai sẽ chạy phép kiểm quản trị
    hai lần — vô hại nhưng khó đọc, và dễ khiến người sau bỏ một trong hai đi.
    """
    from app import audit, platform_settings, sudo_mode

    if sudo_mode.seconds_remaining(str(current_user["id"])) <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "sudo_required",
                "message": "Thao tác này cần xác thực lại bằng mật khẩu.",
                "ttl_seconds": sudo_mode.SUDO_TTL_SECONDS,
            },
        )

    # Giá trị CŨ phải đọc TRƯỚC khi ghi đè. Một dòng kiểm toán chỉ nói "đã đổi
    # thành 30" không trả lời được câu hỏi thật sự cần: đổi từ bao nhiêu. Đọc
    # sau khi ghi thì cả hai đầu đều là giá trị mới.
    before = platform_settings.current().get(key, {}).get("value")

    try:
        value = platform_settings.set_int(
            key, payload.value, updated_by=str(current_user["id"]))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Không có thiết lập {key!r}.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    audit.record("settings.update", actor=current_user, request=request,
                 target_type="platform_setting", target_id=key,
                 detail={"truoc": before, "sau": value})
    return {"key": key, "value": value}


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


@router.get("/attention")
def get_attention(current_user: Dict[str, Any] = Depends(require_admin)):
    """Việc đang chờ quản trị viên, đếm theo từng mục console (Chỉ Admin).

    Một endpoint gộp thay vì năm cái gọi song song. Thanh bên hỏi lại theo chu
    kỳ ở MỌI tab console đang mở, nên năm lời gọi là năm lần bắt tay, năm lần
    kiểm quyền, và năm dòng nhật ký truy cập cho đúng một lần vẽ lại huy hiệu.

    Phạm vi là tổ chức của người đang đăng nhập, không phải toàn hệ thống: số
    phiếu hỗ trợ của tổ chức khác không phải việc của họ, và nội dung phiếu là
    dữ liệu của tenant kia.
    """
    from app.admin_attention import collect
    from app.tenant_context import current_tenant

    return {"counts": collect(current_tenant() or current_user.get("tenant_id") or "")}


@router.get("/activity")
def get_activity(current_user: Dict[str, Any] = Depends(require_admin)):
    """Active sessions (IP, user, location, usage) + anomalies + blocklist."""
    return activity.activity_report(limit=150)


@router.post("/block-ip")
def block_ip(payload: IPAction, request: Request,
             current_user: Dict[str, Any] = Depends(require_admin)):
    """Block a client IP (optionally timed) — the gateway refuses its requests (403)."""
    ip = (payload.ip or "").strip()
    if not ip:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu địa chỉ IP")
    by = current_user.get("username", "")
    ok = activity.block_ip(ip, by=by, reason=payload.reason, duration_seconds=payload.duration_seconds)
    if ok:
        activity.log_security_event("block_ip", actor=by, target=ip, reason=payload.reason,
                                    extra={"duration_seconds": payload.duration_seconds},
                                    actor_user=current_user, request=request)
    return {"status": "success" if ok else "error", "ip": ip, "blocked": ok}


@router.post("/unblock-ip")
def unblock_ip(payload: IPAction, request: Request,
               current_user: Dict[str, Any] = Depends(require_admin)):
    """Remove a client IP from the blocklist."""
    ip = (payload.ip or "").strip()
    if not ip:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu địa chỉ IP")
    ok = activity.unblock_ip(ip)
    if ok:
        activity.log_security_event("unblock_ip", actor=current_user.get("username", ""),
                                    target=ip, actor_user=current_user, request=request)
    return {"status": "success" if ok else "error", "ip": ip, "blocked": False}


@router.post("/force-logout")
def force_logout(payload: ForceLogout, request: Request,
                 current_user: Dict[str, Any] = Depends(require_admin)):
    """Invalidate a user's live sessions (revoke refresh tokens + deny tokens)."""
    uid = (payload.user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu user_id")
    if str(uid) == str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Không thể tự đăng xuất chính mình bằng công cụ này")
    by = current_user.get("username", "")
    activity.force_logout_user(uid, by=by, reason=payload.reason)
    activity.log_security_event("force_logout", actor=by, target=uid, reason=payload.reason,
                                actor_user=current_user, request=request)
    return {"status": "success", "user_id": uid}


@router.post("/users/{user_id}/lock")
def lock_user_account(user_id: str, payload: LockUser, request: Request,
                      current_user: Dict[str, Any] = Depends(require_admin)):
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
                                    extra={"duration_seconds": payload.duration_seconds},
                                    actor_user=current_user, request=request)
    return {"status": "success" if ok else "error", "user_id": uid, "locked": ok}


@router.post("/users/{user_id}/unlock")
def unlock_user_account(user_id: str, request: Request,
                        current_user: Dict[str, Any] = Depends(require_admin)):
    """Re-enable a locked user account."""
    ok = activity.unlock_user(user_id)
    if ok:
        activity.log_security_event("unlock_user", actor=current_user.get("username", ""),
                                    target=user_id, actor_user=current_user, request=request)
    return {"status": "success" if ok else "error", "user_id": user_id, "locked": False}


@router.post("/users/{user_id}/warn")
def warn_user_account(user_id: str, payload: WarnUser, request: Request,
                      current_user: Dict[str, Any] = Depends(require_admin)):
    """Queue a warning message the user sees on their next visit."""
    msg = (payload.message or "").strip()
    if not msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu nội dung cảnh báo")
    by = current_user.get("username", "")
    ok = activity.warn_user(user_id, by=by, message=msg)
    if ok:
        activity.log_security_event("warn_user", actor=by, target=user_id, reason=msg,
                                    actor_user=current_user, request=request)
    return {"status": "success" if ok else "error", "user_id": user_id}


@router.get("/security-log")
def get_security_log(current_user: Dict[str, Any] = Depends(require_admin)):
    """Recent admin security actions (block / unblock / force-logout).

    Đọc từ danh sách Redis: nhanh, và **có thể mất dòng** (cắt còn 500 mục,
    Redis chạy `volatile-lru`). Cần bản đầy đủ thì dùng `/admin/audit-log`.
    """
    return {"events": activity.list_security_log(limit=150)}


@router.get("/audit-log")
def get_audit_log(
    limit: int = 150,
    action_prefix: str = "",
    current_user: Dict[str, Any] = Depends(require_admin),
):
    """Nhật ký kiểm toán BỀN, đọc từ Postgres.

    Bảng này tồn tại từ schema v3 nhưng cho tới bản này **không có đường đọc
    nào** — không endpoint, không giao diện, và lối gọi duy nhất tới
    `list_audit_log` nằm trong một tệp test. Một dấu vết kiểm toán không ai đọc
    được thì không khác gì không có: nó không trả lời được câu hỏi nào vào lúc
    có người cần hỏi.

    Khác `/admin/security-log` ở ba điểm: không bị đuổi khỏi bộ nhớ, có
    `ip_hash` đối chiếu được giữa các hành động, và chịu RLS — nên quản trị
    viên tenant chỉ thấy phần của mình. Dòng tầng nền tảng (`tenant_id` NULL)
    chỉ hiện trong system scope, và endpoint này **không** vượt ranh giới:
    xem `test_no_router_crosses_the_boundary_except_the_documented_one`.
    """
    from app.storage import metadata_db as db
    from app.tenant_context import current_tenant

    rows = db.list_audit_log(limit=limit, action_prefix=action_prefix or None)
    # Nói ra phạm vi thay vì để người đọc suy đoán. Dòng tầng nền tảng
    # (`tenant_id` NULL — Celery beat, CLI) KHÔNG nằm trong kết quả này, và một
    # bảng thiếu dòng mà không báo là một bảng nói dối: người đọc kết luận
    # "không có chuyện gì xảy ra" trong khi thực tế là "chuyện đó ở ngoài tầm
    # nhìn của bạn".
    return {
        "events": rows,
        "count": len(rows),
        "scope": current_tenant() or "(không có phạm vi)",
        "excludes_platform_rows": True,
    }


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

class IgnoreHardwarePayload(BaseModel):
    resource: str
    ignore: bool

@router.post("/config/ignore-hardware")
def ignore_hardware_alert(
    payload: IgnoreHardwarePayload,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Bật/tắt cảnh báo (mute) cho phần cứng bị thiếu thông qua Redis (Chỉ Admin)"""
    from app.monitoring import _redis_client
    r = _redis_client()
    if not r:
        raise HTTPException(status_code=500, detail="Redis unavailable")
    
    if payload.resource not in ["gpu", "disk"]:
        raise HTTPException(status_code=400, detail="Invalid resource")
        
    key = f"config:ignore_missing_{payload.resource}"
    if payload.ignore:
        r.set(key, "1")
    else:
        r.delete(key)
    return {"status": "success", "resource": payload.resource, "ignored": payload.ignore}
