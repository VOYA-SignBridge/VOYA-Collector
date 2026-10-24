from typing import Any, Dict, List
from fastapi import (
    APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status,
)
from pydantic import BaseModel

from app.modules.identity._web_compat import get_current_user, require_admin
from app.modules.security.sudo_mode import require_sudo
from app.modules.admin.user_service import set_user_admin_role
from app.modules.monitoring.service import collect_resources
from app.modules.security import account_controls, activity_monitor, audit_log, ip_controls
from app.routers import admin_data as _admin_data

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(_admin_data.router)

# Compatibility exports for callers that historically imported these handlers
# from ``app.routers.admin``. Their implementation and route registration now
# have one owner: ``admin_data``.
get_data_report = _admin_data.get_data_report
sync_local_files = _admin_data.sync_local_files
get_sync_status = _admin_data.get_sync_status


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
    from app.modules.security import audit, sudo_mode

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
    from app.modules.security import audit, sudo_mode

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
    from app.modules.admin import platform_settings
    from app.modules.security import sudo_mode

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
    from app.modules.admin import platform_settings
    from app.modules.security import audit, sudo_mode

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
    """Người dùng CỦA TENANT hiện tại (Chỉ Admin).

    Đi qua `_fetch_all` chứ không mở kết nối trần. `users` mang chính sách
    row-level security (`storage/rls.py`), và chính sách đó đọc GUC
    `app.tenant_id`. Một kết nối trần chưa từng gọi `apply_scope()` thì GUC rỗng,
    `tenant_id = ''` không khớp dòng nào, và câu lệnh trả về **danh sách rỗng —
    không phải lỗi**. Đó chính là kiểu hỏng mà `docs/` gọi là RLS fail-open ở mặt
    phẳng danh tính: màn hình ghi "Không có người dùng." trong khi cơ sở dữ liệu
    có mười tài khoản, và không có gì trong nhật ký để lần ra.
    """
    from app.storage.metadata_db import _fetch_all

    users = _fetch_all(
        """
        SELECT id, username, email, is_active, is_admin, created_at
        FROM users
        ORDER BY created_at DESC
        """
    )
    locked = account_controls.list_locked_users()
    warned = account_controls.list_warned_users()
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

@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    payload: UserRoleUpdate,
    current_user: Dict[str, Any] = Depends(require_admin),
    # Mặc định `None`, KHÔNG bọc `Optional[Request]`: FastAPI chỉ nhận diện
    # được kiểu tiêm-thẳng đặc biệt này khi chú thích kiểu là ĐÚNG `Request`,
    # và `Optional[Request]` làm nó rơi vào nhánh dựng field Pydantic bình
    # thường rồi vỡ ngay lúc nạp router (`Request` không phải kiểu Pydantic
    # hợp lệ) — đo được khi chạy `test_admin_console_reads_under_rls.py`.
    # `test_admin_console_reads_under_rls.py` gọi thẳng hàm này (bỏ qua HTTP)
    # mà không truyền `request`; FastAPI vẫn tiêm đúng đối tượng thật khi chạy
    # qua HTTP dù tham số có giá trị mặc định.
    request: Request = None,
):
    """Cấp hoặc gỡ quyền QUẢN TRỊ NỀN TẢNG (`users.is_admin`) — Chỉ Admin.

    Đây là hành động mạnh nhất trong hệ thống: `is_admin=TRUE` ánh xạ sang
    `platform_administrator`, vai cầm mọi quyền ở MỌI tenant, không riêng
    tenant của người được cấp. Trước bản vá này endpoint không ghi kiểm toán
    gì cả — một tài khoản có thể được nâng lên quản trị nền tảng mà không ai
    tra lại được ai đã cấp, lúc nào.
    """
    from app.modules.security import audit

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
            detail="Không tìm thấy người dùng"
        )
    # `is_admin_moi` trong `detail` chứ không chỉ hành động: "cấp quyền" và
    # "gỡ quyền" là hai câu chuyện khác hẳn nhau, cùng lý do đã ghi ở
    # `tenant.member_role_changed` trong routers/tenants.py.
    audit.record(
        "account.platform_admin_role_changed", actor=current_user, request=request,
        target_type="user", target_id=str(updated["id"]),
        detail={"username": updated["username"], "is_admin_moi": bool(updated["is_admin"])},
    )
    return {"status": "success",
            "user": {"id": str(updated["id"]),
                     "username": updated["username"],
                     "is_admin": updated["is_admin"]}}

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
    from app.modules.admin.admin_attention import collect
    from app.modules.saas.tenant_context import current_tenant

    return {"counts": collect(current_tenant() or current_user.get("tenant_id") or "")}


@router.get("/activity")
def get_activity(current_user: Dict[str, Any] = Depends(require_admin)):
    """Active sessions (IP, user, location, usage) + anomalies + blocklist."""
    return activity_monitor.activity_report(limit=150)


@router.post("/block-ip")
def block_ip(payload: IPAction, request: Request,
             current_user: Dict[str, Any] = Depends(require_admin)):
    """Block a client IP (optionally timed) — the gateway refuses its requests (403)."""
    ip = (payload.ip or "").strip()
    if not ip:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu địa chỉ IP")
    by = current_user.get("username", "")
    ok = ip_controls.block_ip(ip, by=by, reason=payload.reason, duration_seconds=payload.duration_seconds)
    if ok:
        audit_log.log_security_event("block_ip", actor=by, target=ip, reason=payload.reason,
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
    ok = ip_controls.unblock_ip(ip)
    if ok:
        audit_log.log_security_event("unblock_ip", actor=current_user.get("username", ""),
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
    account_controls.force_logout_user(uid, by=by, reason=payload.reason)
    audit_log.log_security_event("force_logout", actor=by, target=uid, reason=payload.reason,
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
    ok = account_controls.lock_user(uid, by=by, reason=payload.reason, duration_seconds=payload.duration_seconds)
    if ok:
        audit_log.log_security_event("lock_user", actor=by, target=uid, reason=payload.reason,
                                    extra={"duration_seconds": payload.duration_seconds},
                                    actor_user=current_user, request=request)
    return {"status": "success" if ok else "error", "user_id": uid, "locked": ok}


@router.post("/users/{user_id}/unlock")
def unlock_user_account(user_id: str, request: Request,
                        current_user: Dict[str, Any] = Depends(require_admin)):
    """Re-enable a locked user account."""
    ok = account_controls.unlock_user(user_id)
    if ok:
        audit_log.log_security_event("unlock_user", actor=current_user.get("username", ""),
                                    target=user_id, actor_user=current_user, request=request)
    return {"status": "success" if ok else "error", "user_id": user_id, "locked": False}


class RecoveryAssist(BaseModel):
    #: `reset_link` gửi lại thư đặt lại mật khẩu; `clear_2fa` gỡ yếu tố thứ hai
    #: cho người đã mất thiết bị VÀ hết mã khôi phục.
    action: str
    reason: str = ""


@router.post("/users/{user_id}/recovery")
def assist_recovery(user_id: str, payload: RecoveryAssist,
                    background_tasks: BackgroundTasks, request: Request,
                    operator: Dict[str, Any] = Depends(require_sudo)):
    """Quản trị viên giúp một người lấy lại tài khoản.

    Vì sao đường này tồn tại
    -------------------------
    Người dùng của hệ thống này phần lớn là người khiếm thính/khiếm ngôn, và
    luồng tự phục vụ giả định một chuỗi thao tác mà không phải ai cũng đi hết
    được: mở hộp thư, tìm thư trong mục quảng cáo, bấm liên kết trước khi nó hết
    hạn, hiểu vì sao ứng dụng xác thực báo "mã sai" khi đồng hồ điện thoại lệch.
    Không có đường này thì "mất điện thoại" nghĩa là mất tài khoản vĩnh viễn,
    kèm toàn bộ dữ liệu đã đóng góp.

    Vì sao nó KHÔNG phải "admin đặt mật khẩu hộ"
    --------------------------------------------
    Quản trị viên không bao giờ được biết mật khẩu của người khác — biết là có
    thể mạo danh, và mọi dòng kiểm toán từ đó trở đi mất giá trị vì không phân
    biệt được ai đã thao tác. Nên hai hành động ở đây đều chỉ **mở lại cánh
    cửa**, còn bước cuối vẫn do chính chủ tài khoản đi:

        reset_link  ->  gửi lại thư đặt lại mật khẩu, chính chủ tự đặt
        clear_2fa   ->  gỡ yếu tố thứ hai, chính chủ đăng nhập bằng mật khẩu

    Ba lớp chặn lạm dụng
    ---------------------
    1. `require_sudo` — nhập lại mật khẩu của chính quản trị viên, không phải
       một mã PIN dùng chung.
    2. `audit.record` — dòng bền, kèm lý do bắt buộc.
    3. **Thông báo cho chính người bị tác động.** Đây là lớp quan trọng nhất và
       cũng là lớp hay bị bỏ: nếu chủ tài khoản không bao giờ biết ai đó đã gỡ
       2FA của mình, thì hai lớp trên chỉ phục vụ việc điều tra SAU KHI đã có
       người tố cáo — và người duy nhất có thể tố cáo lại chính là người không
       được báo.
    """
    from app.modules.security import audit, two_factor
    from app.modules.support import notifications
    from app.modules.identity._web_compat import request_password_reset
    from app.services.email import send_password_reset_email
    from app.core.public_url import resolve_frontend_base_url
    from app.storage.metadata_db import _fetch_all

    action = (payload.action or "").strip()
    if action not in {"reset_link", "clear_2fa"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="action phải là 'reset_link' hoặc 'clear_2fa'.")
    reason = (payload.reason or "").strip()
    if len(reason) < 5:
        # Bắt buộc, không phải cho đẹp: một dòng kiểm toán ghi "clear_2fa" mà
        # không nói vì sao thì sáu tháng sau không ai dựng lại được câu chuyện.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Cần ghi lý do (ít nhất 5 ký tự).")

    # Đi qua `_fetch_all` để RLS áp: một quản trị viên chỉ hỗ trợ được người
    # trong tenant của mình. Xem `get_all_users` về vì sao kết nối trần là bẫy.
    rows = _fetch_all("SELECT id, username, email FROM users WHERE id = %s",
                      (user_id,))
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Không tìm thấy người dùng")
    target = rows[0]

    if action == "clear_2fa":
        two_factor.disable(str(target["id"]))
        title = "Quản trị viên đã gỡ xác thực hai bước"
        body = (f"Do {operator.get('username', 'quản trị viên')} thực hiện. "
                f"Lý do: {reason}. Nếu không phải bạn yêu cầu, hãy đổi mật khẩu "
                f"và báo ngay.")
    else:
        result = request_password_reset(str(target["email"] or ""))
        if result:
            user, token = result
            link = f"{resolve_frontend_base_url(request)}/reset-password?token={token}"
            background_tasks.add_task(
                send_password_reset_email, user["email"], user["username"], link)
        title = "Quản trị viên đã gửi lại liên kết đặt lại mật khẩu"
        body = (f"Do {operator.get('username', 'quản trị viên')} thực hiện. "
                f"Lý do: {reason}. Kiểm tra hộp thư của bạn.")

    notifications.notify(str(target["id"]), "security", title, body=body,
                         link="/settings/security", severity="warning")
    audit.record("account.recovery.assisted", actor=operator,
                 target_type="user", target_id=str(target["id"]),
                 detail={"action": action, "reason": reason}, request=request)
    audit_log.log_security_event(
        f"recovery.{action}", actor=operator.get("username", ""),
        target=str(target["id"]), reason=reason,
        actor_user=operator, request=request)

    return {"status": "success", "action": action,
            "user_id": str(target["id"])}


@router.post("/users/{user_id}/warn")
def warn_user_account(user_id: str, payload: WarnUser, request: Request,
                      current_user: Dict[str, Any] = Depends(require_admin)):
    """Queue a warning message the user sees on their next visit."""
    msg = (payload.message or "").strip()
    if not msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu nội dung cảnh báo")
    by = current_user.get("username", "")
    ok = account_controls.warn_user(user_id, by=by, message=msg)
    if ok:
        audit_log.log_security_event("warn_user", actor=by, target=user_id, reason=msg,
                                    actor_user=current_user, request=request)
    return {"status": "success" if ok else "error", "user_id": user_id}


@router.get("/security-log")
def get_security_log(current_user: Dict[str, Any] = Depends(require_admin)):
    """Recent admin security actions (block / unblock / force-logout).

    Đọc từ danh sách Redis: nhanh, và **có thể mất dòng** (cắt còn 500 mục,
    Redis chạy `volatile-lru`). Cần bản đầy đủ thì dùng `/admin/audit-log`.
    """
    return {"events": audit_log.list_security_log(limit=150)}


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
    from app.modules.saas.tenant_context import current_tenant

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


class IgnoreHardwarePayload(BaseModel):
    resource: str
    ignore: bool

@router.post("/config/ignore-hardware")
def ignore_hardware_alert(
    payload: IgnoreHardwarePayload,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Bật/tắt cảnh báo (mute) cho phần cứng bị thiếu thông qua Redis (Chỉ Admin)"""
    from app.infrastructure.redis.connection import get_redis_client as _redis_client
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
