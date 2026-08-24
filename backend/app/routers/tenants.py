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
    #
    # Nhận CẢ HAI: một địa chỉ thư, hoặc TÊN ĐĂNG NHẬP của một tài khoản đã có.
    # Người quản trị tổ chức thường biết đồng nghiệp mình qua tên tài khoản chứ
    # không thuộc lòng địa chỉ thư của họ, và bắt họ đoán địa chỉ là cách chắc
    # chắn để lời mời đi lạc. Không nhận `user_id`: mã nội bộ không phải thứ
    # con người gõ được, và một ô nhận mã tuỳ ý là ô dò được cả nền tảng.
    email: str = Field(..., min_length=1, max_length=255)
    role: Optional[str] = None


class SelfServeTenantCreate(BaseModel):
    display_name: str = Field(..., min_length=2, max_length=120)
    plan_code: Optional[str] = Field(None, max_length=50)


class InvitationAccept(BaseModel):
    token: str = Field(..., max_length=512)


class ActiveTenantSwitch(BaseModel):
    tenant_id: str = Field(..., max_length=63)


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


@router.post("/invitations/accept", dependencies=[Depends(limit_catalog)])
def accept_invitation(
    payload: InvitationAccept,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Nhan loi moi bang mot tai khoan DA CO.

    Vi sao endpoint nay phai ton tai
    --------------------------------
    Cho toi ban nay, `consume_invitation` chi voi toi duoc tu MOT cho:
    `POST /auth/register`. He qua la mot loi moi gui toi dia chi DA co tai khoan
    khong bao gio nhan duoc — nguoi nhan bam lien ket, bi dua toi trang dang ky,
    va dang ky tu choi vi email da dung. Loi moi nam lai o trang thai `pending`
    cho toi luc het han, va khong co thong bao nao giai thich vi sao.

    Vi sao email lay tu PHIEN, khong lay tu than yeu cau
    ----------------------------------------------------
    `consume_invitation` tu choi khi email khong khop, va do la thu ngan mot
    lien ket bi chuyen tiep bien hop thu thanh yeu to xac thuc. Neu email do
    chinh nguoi goi khai thi phep kiem ay tu doi chieu voi loi khai cua ke tan
    cong — no khong con kiem gi ca. Lay tu phien dang nhap thi no moi la that.

    Chap nhan loi moi DOI to chuc nha
    ---------------------------------
    `consume_invitation` ghi `users.tenant_id`, nen du lieu MOI cua tai khoan se
    roi vao to chuc vua gia nhap. Tu cach thanh vien cu va du lieu da dong gop o
    to chuc cu KHONG bi dung toi — cung ngu nghia voi `create_own_tenant`.
    """
    try:
        result = tenant_admin.consume_invitation(
            payload.token,
            email=str(current_user.get("email") or ""),
            user_id=str(current_user.get("id") or ""),
        )
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc

    audit.record("tenant.invitation.accepted", actor=current_user, request=request,
                 target_type="tenant", target_id=result["tenant_id"],
                 tenant_id=result["tenant_id"], detail={"role": result["role"]})
    logger.info("[TENANT_API] %s nhan loi moi vao %s (vai %s)",
                current_user.get("username"), result["tenant_id"], result["role"])
    return result


@router.post("/switch", dependencies=[Depends(limit_catalog)])
def switch_active_tenant(
    payload: ActiveTenantSwitch,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Doi to chuc ma nguoi goi DANG XEM.

    Vi sao can mot endpoint thay vi mot doan duong dan
    --------------------------------------------------
    Mot tai khoan co the thuoc nhieu to chuc, nen giao dien phai noi duoc no
    dang hien to chuc nao. `tenant_middleware` co y KHONG nhan tenant tu bat ky
    truong nao cua request — lam the bien ranh gioi cach ly thanh mot thu nguoi
    goi tu khai. Nen phep chon phai duoc GHI o may chu, sau khi kiem tu cach
    thanh vien, va do la viec cua endpoint nay.

    Doan `/org/<id>/...` tren thanh dia chi la BAN SAO cua trang thai ay, de
    nguoi dung sao chep duoc lien ket. No khong quyet dinh pham vi, va gia mao
    no khong doi duoc gi.

    KHONG doi to chuc NHA
    ---------------------
    `users.tenant_id` quyet dinh du lieu MOI thuoc ve dau. Tron hai thu lai thi
    mot cu bam de XEM to chuc khac se am tham chuyen ca noi nhung mau sau nay
    duoc ghi vao. Doi nha la viec cua `PUT /tenants/home-assignment/{user_id}`.
    """
    try:
        result = tenant_admin.set_active_tenant(
            str(current_user.get("id") or ""), payload.tenant_id)
    except tenant_admin.NotAMember as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    audit.record("tenant.active.switched", actor=current_user, request=request,
                 target_type="tenant", target_id=result["tenant_id"],
                 tenant_id=result["tenant_id"],
                 detail={"is_home": result["is_home"]})
    return result


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


@router.post("/self-serve", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(limit_catalog)])
def create_own_tenant(
    payload: SelfServeTenantCreate,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Người dùng tự lập tổ chức của mình và làm quản trị viên của nó.

    Khác `POST /tenants` ở chỗ nào
    ------------------------------
    Endpoint kia là công cụ của người vận hành NỀN TẢNG: nó nhận `tenant_id` do
    người gọi đặt và không gắn ai vào tổ chức. Endpoint này không nhận mã tổ
    chức — mã do máy chủ sinh kèm hậu tố ngẫu nhiên, nên không ai dò được danh
    sách tổ chức đã có bằng cách thử tạo trùng tên.

    Bốn câu hỏi mà một nút "tạo tổ chức" phải trả lời, và câu trả lời ở đây:

        ai được tạo   — tài khoản đã đăng nhập, khi nền tảng đang mở tự phục vụ
        mỗi người mấy — theo GÓI. Gói `free` cho 3; xem
                        `tenant_admin.SELF_SERVE_TENANT_CAP`.
        gói mặc định  — chỉ gói tự phục vụ; `_resolve_plan` cưỡng chế điều đó
        chặn lạm dụng — cùng bộ giới hạn tần suất với các endpoint danh mục

    Tổ chức cũ KHÔNG bị đụng tới. Dữ liệu đã đóng góp ở lại đó, và tư cách thành
    viên cũ vẫn còn — thứ đổi là tổ chức NHÀ, tức nơi dữ liệu MỚI sẽ rơi vào.
    """
    uid = str(current_user.get("id") or "")
    # Câu hỏi này vượt ranh giới tenant, nên nó KHÔNG sống ở đây. Xem
    # `tenant_admin.tenant_owned_by` và chú thích trong module này về việc
    # `routers/tenants.py` cố ý không chứa lời gọi `system_scope` nào.
    # Trần theo GÓI, không phải trần cứng bằng 1.
    #
    # Bản đầu từ chối ngay khi tài khoản đã sở hữu MỘT tổ chức. Con số ấy quá
    # chặt cho cách người ta thật sự dùng: một giảng viên có thể cần một tổ chức
    # để thử, một cho lớp, một cho đề tài. Trần tồn tại để chặn việc đúc tổ chức
    # rỗng hàng loạt, và ba vẫn chặn được điều đó.
    #
    # Đếm ở tầng dịch vụ vì câu hỏi vượt ranh giới tenant — `routers/tenants.py`
    # cố ý không chứa lời gọi `system_scope` nào.
    goi = (payload.plan_code or "").strip() or "free"
    tran = tenant_admin.SELF_SERVE_TENANT_CAP.get(
        goi, tenant_admin.SELF_SERVE_TENANT_CAP_DEFAULT)
    dang_co = tenant_admin.count_tenants_owned_by(uid)
    if dang_co >= tran:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(f"Tài khoản này đã sở hữu {dang_co} tổ chức — gói "
                    f"\"{goi}\" cho tối đa {tran}."),
        )

    try:
        tenant = tenant_admin.create_self_serve_tenant(
            uid,
            display_name=payload.display_name.strip(),
            plan_code=(payload.plan_code or "").strip() or None,
        )
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc

    audit.record("tenant.self_serve_created", actor=current_user, request=request,
                 target_type="tenant", target_id=tenant["tenant_id"],
                 tenant_id=tenant["tenant_id"])
    logger.info("[TENANT_API] %s tu tao to chuc %s",
                current_user.get("username"), tenant["tenant_id"])
    return tenant


@router.get("/me")
def get_my_tenant(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Tổ chức CỦA CHÍNH người gọi, ở mức một THÀNH VIÊN được phép thấy.

    `GET /{tenant_id}` đòi quản trị tenant, nên trước endpoint này một tài khoản
    `editor` — tức phần lớn người dùng — không có cách nào biết mình đang thuộc
    tổ chức nào. Giao diện phải trả lời bằng một câu từ chối, và "bạn không phải
    quản trị viên" là câu trả lời cho một câu hỏi khác hẳn câu người ta hỏi.

    Không nhận tenant từ người gọi. Phạm vi lấy từ phiên đăng nhập, đúng chỗ
    middleware đã phân giải — nên không có tham số nào để giả mạo.

    Trả về ÍT hơn bản dành cho quản trị: tên, số thành viên, vai của chính
    người gọi. Không danh sách thành viên, không thư điện tử, không lời mời —
    những thứ đó vẫn thuộc về quản trị tenant.
    """
    from app.tenant_context import require_tenant

    scope = require_tenant()
    try:
        tenant = tenant_admin.get_tenant(scope)
        members = tenant_admin.list_members(scope)
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc

    uid = str(current_user.get("id") or "")
    my_role = next(
        (m.get("role") for m in members if str(m.get("user_id") or "") == uid), None
    )

    # Danh sach dong nghiep, o muc MOT THANH VIEN duoc thay: ten va vai.
    #
    # Biet minh dang o to chuc nao ma khong biet ai cung o do la mot nua cau tra
    # loi — va la nua vo dung khi nguoi ta vao day de tim xem hoi ai. Nhung chi
    # nua do thoi: KHONG dia chi thu, KHONG ma tai khoan. Hai thu ay la cong cu
    # cua quan tri vien, va mot danh sach thu cua ca to chuc la thu chep ra duoc
    # trong mot luot tai trang.
    roster = [
        {
            "username": m.get("username"),
            "role": m.get("role"),
            "is_me": str(m.get("user_id") or "") == uid,
        }
        for m in members
        if m.get("is_active", True)
    ]
    roster.sort(key=lambda r: (r["role"] != "admin", (r["username"] or "").lower()))

    return {
        "tenant_id": tenant.get("tenant_id"),
        "display_name": tenant.get("display_name"),
        "created_at": tenant.get("created_at"),
        "plan_code": tenant.get("plan_code"),
        "member_count": len(members),
        "admin_count": len([m for m in members if m.get("role") == "admin"]),
        "my_role": my_role,
        "is_self_serve": tenant.get("is_self_serve"),
        "members": roster,
    }


@router.get("/mine", dependencies=[Depends(limit_catalog)])
def list_my_tenants(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Mọi tổ chức người gọi đang thuộc về — không chỉ tổ chức nhà.

    Vì sao đường này phải đứng TRƯỚC `/{tenant_id}`
    -----------------------------------------------
    FastAPI khớp route theo thứ tự khai báo. Đặt sau, `mine` sẽ rơi vào
    `/{tenant_id}` và trở thành một lượt tra tổ chức mang mã "mine" — trả 404
    cho một đường hoàn toàn hợp lệ, và lỗi đó chỉ hiện ra lúc chạy.

    Không nhận `user_id`
    --------------------
    Danh sách này đọc được từ MỌI tenant, nên nếu nhận id từ người gọi thì bất
    kỳ ai cũng dò được người khác đang ở những tổ chức nào. Id lấy từ phiên, và
    đó là toàn bộ phép kiểm quyền cần có ở đây: người ta luôn được biết mình ở
    đâu.

    `is_home` nói tổ chức nào nhận DỮ LIỆU MỚI, không phải "đang xem". Chừng nào
    chưa có đường chuyển tenant thì hai thứ đó trùng nhau — nhưng giao diện nên
    đọc đúng tên ngay từ đầu.
    """
    return tenant_admin.list_tenants_of_user(str(current_user.get("id") or ""))


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

    # Người mời gõ TÊN ĐĂNG NHẬP hay ĐỊA CHỈ THƯ đều được.
    #
    # Không có dấu `@` thì đây là tên đăng nhập: tra ra tài khoản rồi mời tới
    # địa chỉ ĐÃ ĐĂNG KÝ của họ. Địa chỉ đó KHÔNG trả về cho người mời — biết
    # tên một đồng nghiệp không phải là quyền được biết thư của họ, và một ô
    # tra cứu trả về địa chỉ là một ô moi dữ liệu danh bạ.
    #
    # Tra cứu chỉ khớp ĐÚNG TUYỆT ĐỐI, không khớp một phần, không gợi ý: gợi ý
    # biến ô này thành công cụ dò xem ai có mặt trên nền tảng.
    identifier = str(payload.email or "").strip()
    invited_username: Optional[str] = None
    if identifier and "@" not in identifier:
        found = tenant_admin.find_account_by_username(identifier)
        if not found:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Không có tài khoản nào tên \"{identifier}\". "
                       f"Hãy kiểm tra lại tên đăng nhập, hoặc nhập địa chỉ email.",
            )
        invited_username = found["username"]
        identifier = found["email"]

    try:
        invitation, token = tenant_admin.create_invitation(
            tenant_id, identifier, payload.role,
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

    out = {
        **invitation,
        "token": token,
        "accept_url": accept_url,
        "email_sent": email_sent,
    }
    if invited_username:
        # Mời bằng tên đăng nhập: trả lại TÊN, che ĐỊA CHỈ. Người mời đã biết
        # tên (họ vừa gõ nó); địa chỉ thì họ chưa từng biết và không cần biết
        # để lời mời đi tới nơi.
        out["invited_username"] = invited_username
        addr = str(invitation.get("email") or "")
        local, _, domain = addr.partition("@")
        out["email"] = (local[:1] + "***@" + domain) if domain else "***"
    return out


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
    export_purpose: Literal[
        "tenant_portability", "internal_training", "research_release", "public_library"
    ] = Query("tenant_portability"),
    requester: Dict[str, Any] = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    """Đặt hàng một bản xuất. Trả về ngay; việc dựng gói do tác vụ nền làm.

    202 chứ không phải 201: chưa có gì tải được. Trả 201 sẽ khiến giao diện
    tưởng bản xuất đã sẵn sàng và hiện nút tải về một tệp chưa tồn tại.

    `export_purpose` mặc định là `tenant_portability` — mức KHÔNG có thẩm quyền
    phát hành. Một người gọi cũ không truyền tham số này nhận đúng hành vi cũ
    (gói hoàn trả đầy đủ, kèm bản kê hạn chế), chứ không vô tình dựng được một
    gói phát hành. Mặc định phải nghiêng về phía không cấp quyền; ở tầng dưới,
    `tenant_lifecycle.request_export` bắt buộc tham số và không có mặc định nào.
    """
    from app import tenant_lifecycle

    try:
        job = tenant_lifecycle.request_export(
            tenant_id, requested_by=str(requester.get("id") or ""), scope=scope,
            export_purpose=export_purpose,
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
