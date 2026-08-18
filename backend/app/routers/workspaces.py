"""Mặt HTTP của `app/workspace_admin.py` — hai tầng phạm vi dưới tenant.

Vì sao router này tồn tại, nói bằng một câu kiểm chứng được
------------------------------------------------------------
Trước nó, `/openapi.json` có **0** đường dẫn chứa `workspace` hoặc `project`,
trong khi lược đồ đã có đủ hai bảng, `memberships.scope_level` bốn giá trị và 13
vai dựng sẵn trải trên bốn miền. Đó là lý do mọi phát biểu trong tài liệu phải
kèm mệnh đề *"hai cấp dưới có cấu trúc dữ liệu, chưa có bề mặt vận hành"*.

Router này đóng khoảng trống đó. Nó **không** đóng hai khoảng trống còn lại, và
điều đó được nói thẳng ở `GET /workspaces/summary`:

* dữ liệu (`samples`, `classes`, `training_jobs`) vẫn **chưa mang `project_id`**
* `AUTHZ_MODE` vẫn là `shadow` — Casbin quan sát, hệ cũ hai phạm vi quyết định

Quyền: ai đọc, ai ghi
----------------------
* **Đọc** — thành viên của tenant. Một người đóng góp phải nhìn thấy được cây
  phạm vi mà dữ liệu của họ sẽ nằm vào; giấu nó chỉ làm cấu trúc trở nên bí ẩn.
* **Ghi** — quản trị viên của tenant, hoặc quản trị viên nền tảng. Cùng chốt
  chặn với `routers/tenants.py::require_tenant_admin`, viết lại ở đây vì tenant
  đến từ **người gọi** chứ không từ đường dẫn.

Không có endpoint nào ở đây chạy `system_scope`. Workspace và project thuộc về
đúng một tenant, nên RLS là thứ cưỡng chế — không phải một điều kiện lọc viết
tay trong từng câu truy vấn.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app import workspace_admin
from app.auth import get_current_user
from app.quota_deps import tenant_of
from app.rate_limit_deps import limit_catalog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


# --------------------------------------------------------------------------- models


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field("", max_length=500)


class WorkspaceUpdate(BaseModel):
    # Cả ba tuỳ chọn: đây là PATCH, và một thân yêu cầu chỉ đổi tên không nên bị
    # buộc gửi lại mô tả — gửi lại là cách một giá trị bị ghi đè bằng bản cũ mà
    # người dùng không định đụng tới.
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = None


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field("", max_length=500)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = None


class ScopeRoleGrant(BaseModel):
    user_id: str
    role_code: str
    #: Rỗng nghĩa là gán ở cấp workspace. Tường minh hơn hai endpoint gần giống
    #: nhau, và giữ được ràng buộc hình dạng của `memberships` ở một chỗ.
    project_id: Optional[str] = None


class ScopeRoleRevoke(BaseModel):
    reason: str = Field("", max_length=500)


class AllocationSet(BaseModel):
    project_id: str
    metric: str
    #: `None` tường minh nghĩa là **không giới hạn**, cùng quy ước với `plans`.
    #: Không đặt mặc định: một thân yêu cầu không nêu giá trị là lỗi của người
    #: gọi, không phải ý định gỡ hạn mức.
    allocated: Optional[int] = Field(..., ge=0)
    note: str = Field("", max_length=500)


# --------------------------------------------------------------------------- guards


def _translate(exc: workspace_admin.WorkspaceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _caller_tenant(user: Dict[str, Any]) -> str:
    try:
        return tenant_of(user)
    except Exception as exc:  # noqa: BLE001 - đổi sang lỗi HTTP đọc được
        raise HTTPException(
            status_code=400,
            detail="không xác định được tổ chức của tài khoản đang đăng nhập",
        ) from exc


def require_tenant_member(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Đọc được cây phạm vi của chính tổ chức mình."""
    _caller_tenant(user)
    return user


def require_tenant_admin(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Sửa được cây phạm vi: quản trị tổ chức, hoặc quản trị nền tảng.

    Quản trị nền tảng đi qua vì họ phải sửa được một tổ chức mà quản trị viên
    duy nhất đã rời đi — cùng lối thoát đã viết ở `routers/tenants.py`, và là
    chỗ duy nhất hai thẩm quyền gặp nhau.
    """
    from app import tenant_admin as tenant_admin_service
    from app.vocabulary_registry import tenant_role

    if user.get("is_admin"):
        return user

    tenant_id = _caller_tenant(user)
    role = tenant_role(tenant_id, str(user.get("id") or ""))
    if role not in tenant_admin_service.TENANT_ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="cần vai quản trị của tổ chức để sửa workspace hoặc project",
        )
    return user


# --------------------------------------------------------------------------- literal paths
#
# Starlette khớp tuyến theo THỨ TỰ KHAI BÁO, nên mọi đường có đoạn đầu là chuỗi
# cố định phải đăng ký TRƯỚC `/{workspace_id}`. Không thì `GET /workspaces/summary`
# sẽ bám vào `/{workspace_id}` với workspace_id="summary" — một lỗi định tuyến
# chỉ lộ ra khi ai đó thêm một đường mới nhiều tháng sau.


@router.get("/summary", dependencies=[Depends(limit_catalog)])
def read_summary(user: Dict[str, Any] = Depends(require_tenant_member)) -> Dict[str, Any]:
    """Số liệu cây phạm vi, KÈM hai cờ nói ra giới hạn hiện tại.

    `data_carries_project_id` và `authz_mode` không phải trường thừa: chúng là
    thứ giao diện dùng để in ra đúng trạng thái, thay vì để người xem suy ra rằng
    tạo được project nghĩa là dữ liệu đã phân về project và vai cấp project đã
    có hiệu lực.
    """
    try:
        return workspace_admin.scope_tree_summary(_caller_tenant(user))
    except workspace_admin.WorkspaceError as exc:
        raise _translate(exc) from exc


@router.get("/roles", dependencies=[Depends(limit_catalog)])
def list_roles(
    scope_level: str = Query(..., pattern="^(WORKSPACE|PROJECT)$"),
    user: Dict[str, Any] = Depends(require_tenant_member),
) -> List[Dict[str, Any]]:
    try:
        return workspace_admin.list_assignable_roles(_caller_tenant(user), scope_level)
    except workspace_admin.WorkspaceError as exc:
        raise _translate(exc) from exc


# --------------------------------------------------------------------------- workspaces


@router.get("", dependencies=[Depends(limit_catalog)])
def list_workspaces(
    include_archived: bool = Query(False),
    user: Dict[str, Any] = Depends(require_tenant_member),
) -> List[Dict[str, Any]]:
    try:
        return workspace_admin.list_workspaces(
            _caller_tenant(user), include_archived=include_archived
        )
    except workspace_admin.WorkspaceError as exc:
        raise _translate(exc) from exc


@router.post("", status_code=201, dependencies=[Depends(limit_catalog)])
def create_workspace(
    payload: WorkspaceCreate = Body(...),
    user: Dict[str, Any] = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    try:
        return workspace_admin.create_workspace(
            _caller_tenant(user), name=payload.name, description=payload.description
        )
    except workspace_admin.WorkspaceError as exc:
        raise _translate(exc) from exc


@router.get("/{workspace_id}")
def get_workspace(
    workspace_id: str = Path(...),
    user: Dict[str, Any] = Depends(require_tenant_member),
) -> Dict[str, Any]:
    try:
        return workspace_admin.get_workspace(_caller_tenant(user), workspace_id)
    except workspace_admin.WorkspaceError as exc:
        raise _translate(exc) from exc


@router.patch("/{workspace_id}")
def update_workspace(
    workspace_id: str = Path(...),
    payload: WorkspaceUpdate = Body(...),
    user: Dict[str, Any] = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    try:
        return workspace_admin.update_workspace(
            _caller_tenant(user),
            workspace_id,
            name=payload.name,
            description=payload.description,
            status=payload.status,
        )
    except workspace_admin.WorkspaceError as exc:
        raise _translate(exc) from exc


# --------------------------------------------------------------------------- projects


@router.get("/{workspace_id}/projects")
def list_projects(
    workspace_id: str = Path(...),
    include_archived: bool = Query(False),
    user: Dict[str, Any] = Depends(require_tenant_member),
) -> List[Dict[str, Any]]:
    try:
        return workspace_admin.list_projects(
            _caller_tenant(user), workspace_id, include_archived=include_archived
        )
    except workspace_admin.WorkspaceError as exc:
        raise _translate(exc) from exc


@router.post("/{workspace_id}/projects", status_code=201)
def create_project(
    workspace_id: str = Path(...),
    payload: ProjectCreate = Body(...),
    user: Dict[str, Any] = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    try:
        return workspace_admin.create_project(
            _caller_tenant(user),
            workspace_id,
            name=payload.name,
            description=payload.description,
        )
    except workspace_admin.WorkspaceError as exc:
        raise _translate(exc) from exc


@router.patch("/{workspace_id}/projects/{project_id}")
def update_project(
    workspace_id: str = Path(...),
    project_id: str = Path(...),
    payload: ProjectUpdate = Body(...),
    user: Dict[str, Any] = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    try:
        return workspace_admin.update_project(
            _caller_tenant(user),
            workspace_id,
            project_id,
            name=payload.name,
            description=payload.description,
            status=payload.status,
        )
    except workspace_admin.WorkspaceError as exc:
        raise _translate(exc) from exc


# --------------------------------------------------------------------------- cấp phát


@router.get("/{workspace_id}/allocations")
def list_allocations(
    workspace_id: str = Path(...),
    user: Dict[str, Any] = Depends(require_tenant_member),
) -> Dict[str, Any]:
    """Bảng cấp phát của mọi project trong workspace, kèm trần gói và phần còn lại.

    Đọc mở cho thành viên: một người bị chặn vì project hết hạn mức phải nhìn
    thấy được vì sao, nếu không thông báo lỗi trở thành một điều bí ẩn — cùng lập
    luận đã viết ở `routers/billing.py`.
    """
    try:
        return workspace_admin.list_allocations(_caller_tenant(user), workspace_id)
    except workspace_admin.WorkspaceError as exc:
        raise _translate(exc) from exc


@router.put("/{workspace_id}/allocations")
def set_allocation(
    workspace_id: str = Path(...),
    payload: AllocationSet = Body(...),
    user: Dict[str, Any] = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    try:
        return workspace_admin.set_allocation(
            _caller_tenant(user),
            workspace_id=workspace_id,
            project_id=payload.project_id,
            metric=payload.metric,
            allocated=payload.allocated,
            note=payload.note,
            actor_user_id=str(user.get("id") or ""),
        )
    except workspace_admin.WorkspaceError as exc:
        raise _translate(exc) from exc


# --------------------------------------------------------------------------- vai theo phạm vi


@router.get("/{workspace_id}/members")
def list_members(
    workspace_id: str = Path(...),
    project_id: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_tenant_member),
) -> List[Dict[str, Any]]:
    try:
        return workspace_admin.list_scope_members(
            _caller_tenant(user), workspace_id=workspace_id, project_id=project_id
        )
    except workspace_admin.WorkspaceError as exc:
        raise _translate(exc) from exc


@router.post("/{workspace_id}/members", status_code=201)
def grant_role(
    workspace_id: str = Path(...),
    payload: ScopeRoleGrant = Body(...),
    user: Dict[str, Any] = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    try:
        return workspace_admin.assign_scope_role(
            _caller_tenant(user),
            workspace_id=workspace_id,
            project_id=payload.project_id,
            user_id=payload.user_id,
            role_code=payload.role_code,
            actor_user_id=str(user.get("id") or ""),
        )
    except workspace_admin.WorkspaceError as exc:
        raise _translate(exc) from exc


@router.delete("/{workspace_id}/members/{assignment_id}")
def revoke_role(
    workspace_id: str = Path(...),
    assignment_id: str = Path(...),
    payload: ScopeRoleRevoke = Body(default=ScopeRoleRevoke()),
    user: Dict[str, Any] = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    try:
        return workspace_admin.revoke_scope_role(
            _caller_tenant(user),
            assignment_id=assignment_id,
            actor_user_id=str(user.get("id") or ""),
            reason=payload.reason,
        )
    except workspace_admin.WorkspaceError as exc:
        raise _translate(exc) from exc
