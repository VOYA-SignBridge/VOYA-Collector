"""HTTP surface for tenant lifecycle.

Two authorities, never conflated
--------------------------------
**Platform operator** (`users.is_admin`) — runs the deployment. Creates and
deletes tenants, moves accounts between them. Not a tenant role.

**Tenant admin** (`tenant_members.role = 'admin'`) — runs one tenant. Manages
that tenant's members and invitations, and nothing outside it.

They are checked by two different dependencies on purpose. A single
`is_authorized` helper that took both into account is how being an admin *of
tenant A* eventually grants something in tenant B: the check passes, and
nothing at the call site shows which authority satisfied it.

This module contains no `system_scope` call. The cross-tenant work lives in
`app.tenant_admin`, and `test_tenant_isolation.py` asserts that no router
except `sot_admin` crosses the boundary — a request handler running as every
tenant is the shape most likely to grow a hole later.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

from fastapi import (
    APIRouter, Body, Depends, HTTPException, Path, Query, Request, Response, status,
)
from pydantic import BaseModel, Field

from app import audit, tenant_admin
from app.auth import get_current_user, require_admin
from app.rate_limit_deps import limit_catalog
from app.sudo_mode import require_sudo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants", tags=["tenants"])


# --------------------------------------------------------------------------- schemas


class TenantCreate(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=63)
    display_name: str = ""
    slug: str = ""


class TenantUpdate(BaseModel):
    display_name: Optional[str] = None
    is_active: Optional[bool] = None


# Bốn mô hình dưới đây khai `role: Optional[str] = None`, và `None` KHÔNG phải
# "chưa nói gì" — nó là câu trả lời: vào tổ chức, không kèm vai ở tầng tenant.
#
# Mặc định cũ là `"viewer"`, nghĩa là một client bỏ qua trường này vẫn cấp một
# vai đọc được hoá đơn, nhật ký kiểm toán, khoá API và trạng thái đồng thuận.
# Bỏ trường đi bây giờ không cấp gì. `tenant_admin._require_role` nhận cả
# `None`, `""` và `"none"`, nên một biểu mẫu gửi ô `<select>` rỗng cũng tới
# đúng chỗ này thay vì ăn 422 rồi bị "sửa" bằng cách gửi bừa một vai.
class MemberAdd(BaseModel):
    user_id: str
    role: Optional[str] = None


class MemberRoleUpdate(BaseModel):
    # KHÔNG có mặc định: đây là endpoint chuyên để đổi vai, nên một thân yêu cầu
    # không nêu vai là một lỗi của người gọi, không phải một ý định. Muốn GỠ vai
    # thì gửi `null` — tường minh.
    role: Optional[str]


class InvitationCreate(BaseModel):
    # `str`, not pydantic's `EmailStr`: that type pulls in `email-validator`,
    # which is not a dependency here, and the rest of this API (RegisterRequest)
    # already takes addresses as plain strings. `create_invitation` normalises
    # and checks the value — one place, shared by every caller.
    email: str = Field(..., min_length=3, max_length=255)
    role: Optional[str] = None


class HomeTenantUpdate(BaseModel):
    tenant_id: str
    role: Optional[str] = None


# --------------------------------------------------------------------------- guards


def _translate(exc: tenant_admin.TenantError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def require_tenant_admin(
    tenant_id: str = Path(...),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Admin OF THIS TENANT, or a platform operator.

    Platform operators pass because they must be able to repair a tenant whose
    only admin left. That is an escape hatch, and it is the ONLY place the two
    authorities meet — written once, here, rather than re-derived per endpoint.
    """
    from app.vocabulary_registry import tenant_role

    if user.get("is_admin"):
        return user

    if tenant_role(tenant_id, str(user.get("id") or "")) not in tenant_admin.TENANT_ADMIN_ROLES:
        # 403 rather than 404: the caller is authenticated and the tenant id came
        # from a path they were given. Hiding existence here would only confuse
        # a legitimate admin who mistyped, and reveals nothing an authenticated
        # member could not already learn.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"admin of tenant '{tenant_id}' required",
        )
    return user


# ------------------------------------------------------- literal paths (declare first)
#
# Starlette matches routes in declaration order, so any path whose first segment
# is a literal must be registered BEFORE `/{tenant_id}/...`. Otherwise
# `PUT /tenants/home-assignment/x` binds to `/{tenant_id}/members/{user_id}` with
# tenant_id="home-assignment" the moment someone adds a PUT there — a routing bug
# that only appears when an unrelated endpoint is added months later.


@router.post("/invitations/inspect", dependencies=[Depends(limit_catalog)])
def inspect_invitation(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """What a registration form may show before the account exists.

    POST, not GET: the token would otherwise land in access logs, browser
    history and any proxy in between. Same reason the invitation link itself
    should carry the token in a fragment or a posted form, never a query string.

    Unauthenticated by necessity — the person has no account yet. Rate-limited,
    and an unknown token returns the same 404 as an expired one so this cannot
    be used to test guesses.
    """
    try:
        return tenant_admin.peek_invitation(str(payload.get("token") or ""))
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc


@router.put("/home-assignment/{user_id}", dependencies=[Depends(limit_catalog)])
def set_home_tenant(
    user_id: str,
    payload: HomeTenantUpdate,
    _: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Move which tenant an account's future data belongs to. Operators only.

    Not under `/{tenant_id}/` because it is not an operation on one tenant: it
    takes an account out of one and points it at another.
    """
    try:
        tenant_admin.set_home_tenant(user_id, payload.tenant_id, role=payload.role)
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc
    return {"user_id": user_id, "tenant_id": payload.tenant_id}


# --------------------------------------------------------------------------- tenants


@router.get("", dependencies=[Depends(limit_catalog)])
def list_tenants(
    include_deleted: bool = Query(False),
    _: Dict[str, Any] = Depends(require_admin),
) -> List[Dict[str, Any]]:
    """Every tenant on the deployment. Platform operators only."""
    return tenant_admin.list_tenants(include_deleted=include_deleted)


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(limit_catalog)])
def create_tenant(
    payload: TenantCreate,
    operator: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    try:
        tenant = tenant_admin.create_tenant(
            payload.tenant_id,
            display_name=payload.display_name,
            slug=payload.slug,
            created_by=str(operator.get("id") or "") or None,
        )
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc
    logger.info("[TENANT_API] %s created tenant %s", operator.get("username"), payload.tenant_id)
    return tenant


@router.get("/{tenant_id}")
def get_tenant(
    tenant_id: str,
    _: Dict[str, Any] = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    try:
        return tenant_admin.get_tenant(tenant_id)
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc


@router.patch("/{tenant_id}")
def update_tenant(
    tenant_id: str,
    payload: TenantUpdate,
    _: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    try:
        return tenant_admin.update_tenant(
            tenant_id, display_name=payload.display_name, is_active=payload.is_active
        )
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc


@router.delete("/{tenant_id}")
def delete_tenant(
    tenant_id: str,
    _: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    try:
        return tenant_admin.delete_tenant(tenant_id)
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc


# --------------------------------------------------------------------------- members


@router.get("/{tenant_id}/members")
def list_members(
    tenant_id: str,
    _: Dict[str, Any] = Depends(require_tenant_admin),
) -> List[Dict[str, Any]]:
    try:
        return tenant_admin.list_members(tenant_id)
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc


@router.post("/{tenant_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(
    tenant_id: str,
    payload: MemberAdd,
    _: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Attach an existing account. Platform operators only.

    A tenant admin cannot do this: they would be able to pull any account on the
    deployment into their tenant by id, and account ids are not secret. Getting
    someone in is the invitation flow, which requires that person to act.
    """
    try:
        return tenant_admin.add_member(tenant_id, payload.user_id, payload.role)
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc


@router.patch("/{tenant_id}/members/{user_id}")
def update_member_role(
    tenant_id: str,
    user_id: str,
    payload: MemberRoleUpdate,
    request: Request,
    actor: Dict[str, Any] = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    try:
        result = tenant_admin.update_member_role(tenant_id, user_id, payload.role)
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc
    # Đổi vai là đổi QUYỀN. `tenant_members.role` chỉ nói vai HIỆN TẠI; khi cần
    # trả lời "ai cho người này quyền admin, và lúc nào", cột đó im lặng. Vai
    # CŨ đi vào `detail` vì "được nâng lên admin" và "bị gỡ vai" là hai câu
    # chuyện rất khác nhau, và `null` ở một trong hai vế là một trong số đó.
    #
    # `result["role"]` chứ không `payload.role`: cái sau là chuỗi thô của người
    # gọi, và `""` với `null` cùng được lưu thành NULL. Ghi vế thô vào sổ kiểm
    # toán làm hai dòng cùng một hành động trông như hai hành động khác nhau.
    audit.record("tenant.member_role_changed", actor=actor, request=request,
                 target_type="user", target_id=str(user_id), tenant_id=tenant_id,
                 detail={"role_moi": result.get("role"), "role_cu": result.get("role_cu")})
    return result


@router.delete(
    "/{tenant_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # Without this FastAPI infers a response model from the `-> None` annotation
    # and then refuses, because 204 must not carry a body.
    response_class=Response,
)
def remove_member(
    tenant_id: str,
    user_id: str,
    request: Request,
    actor: Dict[str, Any] = Depends(require_tenant_admin),
) -> Response:
    try:
        tenant_admin.remove_member(tenant_id, user_id)
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc
    # Gỡ một người khỏi tổ chức làm họ mất quyền xem chính dữ liệu họ đã đóng
    # góp. Sau khi hàng `tenant_members` biến mất thì không còn gì trong hệ
    # thống nói rằng họ đã từng ở đây.
    audit.record("tenant.member_removed", actor=actor, request=request,
                 target_type="user", target_id=str(user_id), tenant_id=tenant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- invitations


@router.get("/{tenant_id}/invitations")
def list_invitations(
    tenant_id: str,
    include_closed: bool = Query(False),
    _: Dict[str, Any] = Depends(require_tenant_admin),
) -> List[Dict[str, Any]]:
    """Invitations for this tenant. The token is not part of the response.

    It was returned once, when the invitation was created. There is no endpoint
    that reads it back, because the server does not keep it.
    """
    try:
        return tenant_admin.list_invitations(tenant_id, include_closed=include_closed)
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc


@router.post(
    "/{tenant_id}/invitations",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_catalog)],
)
def create_invitation(
    tenant_id: str,
    payload: InvitationCreate,
    request: Request,
    inviter: Dict[str, Any] = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    """Mint an invitation, mail it, and hand the link back.

    `accept_url` is built HERE, not in the browser
    ----------------------------------------------
    It used to be assembled by `AdminTenantsPage`, which meant the name of the
    `/invitation` route lived in two repositories at once. Renaming it on one
    side kills every invitation issued afterwards, and the failure surfaces days
    later as a blank page on a stranger's screen. The server knows its own
    public origin (allowlisted host, sub-path deploys included) and now owns the
    whole URL.

    `email_sent` is a fact, not a promise
    -------------------------------------
    Delivery failing must not undo the invitation — it is already in the table
    and the token is in this response, so the admin can still send the link by
    hand. Reporting the failure is what stops them assuming a mail went out that
    never did. The code path that raises is the one where SMTP is unconfigured,
    which is the normal state of a local deployment.

    Sent inline, not through Celery, and that is the trade being made: the
    request can block for up to the SMTP timeout. Handing it to a worker would
    return faster but `email_sent` would then mean "queued", which is exactly
    the promise this field exists to avoid making — a worker that is down would
    report success and deliver nothing.
    """
    from app import public_url
    from app.config import settings

    try:
        invitation, token = tenant_admin.create_invitation(
            tenant_id, str(payload.email), payload.role,
            invited_by=str(inviter.get("id") or "") or None,
        )
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc

    accept_url = public_url.frontend_url(request, "invitation", fragment=f"token={token}")

    email_sent = False
    try:
        from app.email_service import send_invitation_email

        send_invitation_email(
            invitation["email"],
            tenant_name=tenant_admin.get_tenant(tenant_id).get("display_name") or tenant_id,
            role=invitation["role"],
            accept_url=accept_url,
            expires_hours=int(settings.invitation_ttl_hours),
        )
        email_sent = True
    except Exception as exc:
        # Type name only. The message of a failing SMTP login can carry the
        # account it tried with, and this line goes to Loki.
        logger.warning(
            "[TENANT] invitation for %s created but not mailed (%s)",
            invitation["email"], type(exc).__name__,
        )

    return {
        **invitation,
        "token": token,
        "accept_url": accept_url,
        "email_sent": email_sent,
    }


@router.delete("/{tenant_id}/invitations/{invitation_id}")
def revoke_invitation(
    tenant_id: str,
    invitation_id: str,
    _: Dict[str, Any] = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    try:
        return tenant_admin.revoke_invitation(tenant_id, invitation_id)
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc


# --------------------------------------------------------------------------- lifecycle
#
# Xuất dữ liệu và xoá vĩnh viễn. Hai nửa của cùng một câu chuyện: một tổ chức
# rời nền tảng phải mang được dữ liệu của mình đi TRƯỚC khi nó biến mất.
#
# Quyền không giống nhau, và đó là chủ ý:
#   * XUẤT do quản trị viên CỦA TỔ CHỨC tự làm — dữ liệu là của họ.
#   * XOÁ VĨNH VIỄN chỉ quản trị viên nền tảng, và phải đang ở chế độ sudo.
#     Đây là thao tác duy nhất trong hệ thống không hoàn tác được.


class PurgeRequest(BaseModel):
    # Không phải boolean. Xem `tenant_lifecycle.purge_tenant`: một cờ true/false
    # bị vượt qua bởi mọi thứ từ lỡ tay tới script chạy sai biến.
    confirm_tenant_id: str = Field(..., min_length=1, max_length=63)
    reason: str = Field("", max_length=1000)
    skip_export_check: bool = False


# --------------------------------------------------------------------- đăng ký


@router.get("/{tenant_id}/subscription")
def read_subscription(
    tenant_id: str,
    _: Dict[str, Any] = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    """Kỳ hạn, còn bao nhiêu ngày, và có đang chỉ-đọc không.

    Vòng TENANT chứ không phải vòng nền tảng: chủ một tổ chức phải tự xem được
    gói của mình sắp hết hạn chưa. Trước đây thông tin này chỉ đọc được bằng
    một câu SQL, nên trên thực tế không ai đọc.
    """
    from app.subscription_lifecycle import describe

    return describe(tenant_id)


class AutoRenewUpdate(BaseModel):
    enabled: bool


@router.post("/{tenant_id}/subscription/auto-renew")
def set_subscription_auto_renew(
    tenant_id: str,
    payload: AutoRenewUpdate,
    _: Dict[str, Any] = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    """Bật/tắt tự gia hạn — đường "tự huỷ" của chính người dùng.

    Tắt KHÔNG đóng đăng ký ngay: kỳ đang chạy vẫn chạy hết. Đây là chỗ dễ làm
    sai nhất của mọi luồng huỷ, và làm sai theo hướng đó là lấy đi phần khách
    hàng đã trả tiền.
    """
    from app.subscription_lifecycle import SubscriptionError, describe, set_auto_renew

    try:
        set_auto_renew(tenant_id, payload.enabled)
    except SubscriptionError as exc:
        raise HTTPException(status_code=exc.status_code,
                            detail={"code": exc.code, "message": str(exc)}) from None
    return describe(tenant_id)


@router.post("/{tenant_id}/exports", status_code=status.HTTP_202_ACCEPTED)
def request_export(
    tenant_id: str,
    # `Literal`, not `Query(pattern=...)` — FastAPI 0.95 on pydantic 1.10 spells
    # that constraint `regex`, and swallows an unknown `pattern` without
    # enforcing it. `tenant_lifecycle.request_export` re-checks and raises 422,
    # which is why nothing broke; the schema was simply claiming a guarantee it
    # was not providing. See `routers/verification.py`.
    scope: Literal["metadata", "full"] = Query("metadata"),
    requester: Dict[str, Any] = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    """Đặt hàng một bản xuất. Trả về ngay; việc dựng gói do tác vụ nền làm.

    202 chứ không phải 201: chưa có gì tải được. Trả 201 sẽ khiến giao diện
    tưởng bản xuất đã sẵn sàng và hiện nút tải về một tệp chưa tồn tại.
    """
    from app import tenant_lifecycle

    try:
        job = tenant_lifecycle.request_export(
            tenant_id, requested_by=str(requester.get("id") or ""), scope=scope
        )
    except tenant_lifecycle.LifecycleError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    try:
        from app.saas_tasks import run_tenant_export

        run_tenant_export.delay(job["export_id"])
    except Exception as exc:
        # Yêu cầu đã nằm trong bảng ở trạng thái `pending`, nên nó không mất.
        # Báo cho người gọi biết thay vì để họ nhìn một dòng "đang xử lý" đứng
        # yên mãi mãi.
        logger.error("[EXPORT] không phái được tác vụ: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Đã ghi nhận yêu cầu nhưng chưa phái được tác vụ xử lý. Hãy thử lại.",
        ) from exc

    return job


@router.get("/{tenant_id}/exports")
def list_exports(
    tenant_id: str,
    _: Dict[str, Any] = Depends(require_tenant_admin),
) -> List[Dict[str, Any]]:
    from app import tenant_lifecycle

    return tenant_lifecycle.list_exports(tenant_id)


@router.get("/{tenant_id}/exports/{export_id}/download")
def download_export(
    tenant_id: str,
    export_id: str,
    _: Dict[str, Any] = Depends(require_tenant_admin),
):
    from fastapi.responses import FileResponse

    from app import tenant_lifecycle

    try:
        path = tenant_lifecycle.export_file(tenant_id, export_id)
    except tenant_lifecycle.LifecycleError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return FileResponse(
        path, media_type="application/zip", filename=f"{tenant_id}-export.zip"
    )


@router.get("/{tenant_id}/purge-preview")
def purge_preview(
    tenant_id: str,
    _: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Sẽ xoá những gì, và đã đủ điều kiện chưa. Không thay đổi gì cả."""
    from app import tenant_lifecycle

    try:
        return tenant_lifecycle.purge_preview(tenant_id)
    except tenant_lifecycle.LifecycleError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/{tenant_id}/purge")
def purge_tenant(
    tenant_id: str,
    payload: PurgeRequest,
    request: Request,
    operator: Dict[str, Any] = Depends(require_sudo),
) -> Dict[str, Any]:
    """Xoá vĩnh viễn một tổ chức. Không hoàn tác được."""
    from app import audit, tenant_lifecycle

    try:
        result = tenant_lifecycle.purge_tenant(
            tenant_id,
            confirm_tenant_id=payload.confirm_tenant_id,
            requested_by=str(operator.get("id") or ""),
            reason=payload.reason,
            skip_export_check=payload.skip_export_check,
        )
    except tenant_lifecycle.LifecycleError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    # Ghi kiểm toán SAU khi xoá, và ở tầng nền tảng (`tenant_id=None`): dòng
    # kiểm toán của chính tenant đó vừa bị xoá cùng mọi thứ khác, nên ghi trước
    # là ghi vào chỗ sắp biến mất.
    audit.record(
        "tenant.purged", actor=operator, request=request,
        target_type="tenant", target_id=tenant_id,
        detail={
            "purge_id": result["purge_id"],
            "total_rows": sum(result["row_counts"].values()),
            "files_removed": result["files_removed"],
            "reason": payload.reason,
        },
    )
    return result
