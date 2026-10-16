"""Gói, hạn mức và mức dùng — mặt HTTP của `app/plans.py` và `app/usage.py`.

Ba nhóm người đọc, ba mức quyền, cố ý tách rời:

* **Ai cũng xem được bảng giá** (`GET /billing/plans`). Đây là thông tin thương
  mại công khai; bắt đăng nhập mới xem được giá là chặn đúng người đang cân
  nhắc dùng sản phẩm.
* **Thành viên xem được gói và mức dùng của TỔ CHỨC MÌNH**. Không cần vai trò
  quản trị: một người đóng góp bị chặn vì hết hạn mức phải nhìn thấy được vì
  sao, nếu không thông báo lỗi trở thành một điều bí ẩn.
* **Chỉ quản trị viên nền tảng đổi được gói và trạng thái thanh toán**, và việc
  đó thêm `require_sudo`. Hạ gói một tổ chức hay treo họ là thao tác gây hậu
  quả trực tiếp lên người dùng thật.

Không có endpoint nào ở đây nhận thanh toán. Cổng thanh toán là bước sau, và nó
cần số đo — thứ vừa mới có. Bảng `tenant_subscriptions` đã ghi sẵn chuỗi thay
đổi gói mà một tích hợp hoá đơn sẽ cần đọc.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app import plans as plans_service
from app import tenant_admin, usage
from app.auth import get_current_user, require_admin
from app.quota_deps import tenant_of
from app.rate_limit_deps import limit_catalog
from app.sudo_mode import require_sudo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


class PlanChange(BaseModel):
    plan_code: str = Field(..., min_length=1, max_length=64)
    note: str = Field("", max_length=500)


class StatusChange(BaseModel):
    billing_status: str = Field(..., min_length=1, max_length=32)
    reason: str = Field("", max_length=500)


def _translate(exc: tenant_admin.TenantError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


# --------------------------------------------------------------------------- catalogue


@router.get("/plans")
def list_plans() -> List[Dict[str, Any]]:
    """Bảng giá công khai. Gói không niêm yết (`internal`) không xuất hiện."""
    return plans_service.list_plans()


# --------------------------------------------------------------------------- my tenant


@router.get("/me")
def my_billing(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Gói, trạng thái và mức dùng hiện tại của tổ chức người gọi.

    Một lượt gọi trả đủ thứ giao diện cần để vẽ trang "Gói dịch vụ": không bắt
    nó ghép ba endpoint lại rồi tự xử lý ba trạng thái tải khác nhau.
    """
    tenant_id = tenant_of(current_user)
    try:
        tenant = tenant_admin.get_tenant(tenant_id)
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc

    return {
        "tenant": {
            "tenant_id": tenant["tenant_id"],
            "display_name": tenant.get("display_name"),
            "plan_code": tenant.get("plan_code"),
            "billing_status": tenant.get("billing_status"),
            "trial_ends_at": tenant.get("trial_ends_at"),
            "is_self_serve": tenant.get("is_self_serve"),
        },
        "plan": plans_service.plan_for_tenant(tenant_id),
        "usage": plans_service.usage_snapshot(tenant_id),
    }


@router.get("/usage")
def my_usage(
    days: int = Query(30, ge=1, le=365),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Chuỗi thời gian mức dùng của tổ chức người gọi."""
    tenant_id = tenant_of(current_user)
    return {
        "tenant_id": tenant_id,
        "days": days,
        "totals": usage.usage_totals(tenant_id, days=days),
        "series": usage.usage_series(tenant_id, days=days),
    }


# --------------------------------------------------------------------------- platform


@router.patch("/plans/{plan_code}", dependencies=[Depends(limit_catalog)])
def update_plan(
    plan_code: str,
    request: Request,
    changes: Dict[str, Any] = Body(...),
    operator: Dict[str, Any] = Depends(require_sudo),
) -> Dict[str, Any]:
    """Sửa hạn mức hoặc giá của một gói.

    Thân thư là một đối tượng thưa: chỉ những trường muốn đổi. Dùng `Body`
    thay vì một model Pydantic có mọi trường Optional, vì với model đó không
    phân biệt được "không nêu" và "đặt về null" — mà null ở đây mang nghĩa
    KHÔNG GIỚI HẠN, tức là gần như trái ngược với "để nguyên".

    Đổi hạn mức tác động tới mọi tenant đang ở gói đó, nên nó đòi sudo và được
    ghi kiểm toán cùng nội dung thay đổi.
    """
    from app import audit

    try:
        updated = plans_service.update_plan(plan_code, changes)
    except plans_service.PlanError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    audit.record(
        "plan.updated", actor=operator, request=request,
        target_type="plan", target_id=plan_code, detail={"changes": changes},
    )
    return updated


@router.get("/platform-usage")
def platform_usage(
    days: int = Query(30, ge=1, le=365),
    _: Dict[str, Any] = Depends(require_admin),
) -> List[Dict[str, Any]]:
    """Bảng mức dùng của MỌI tenant. Chỉ quản trị viên nền tảng."""
    return usage.platform_totals(days=days)


@router.patch(
    "/tenants/{tenant_id}/plan",
    dependencies=[Depends(limit_catalog)],
)
def change_tenant_plan(
    tenant_id: str,
    payload: PlanChange,
    request: Request,
    operator: Dict[str, Any] = Depends(require_sudo),
) -> Dict[str, Any]:
    """Đổi gói của một tổ chức.

    Ghi vào nhật ký kiểm toán vì đây là thay đổi có hệ quả thương mại: một
    tranh chấp hoá đơn sẽ hỏi ai đổi, đổi lúc nào, từ gì sang gì.
    """
    from app import audit

    try:
        before = tenant_admin.get_tenant(tenant_id).get("plan_code")
        tenant = tenant_admin.change_plan(
            tenant_id, payload.plan_code,
            changed_by=str(operator.get("id") or ""), note=payload.note,
        )
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc

    audit.record(
        "tenant.plan_changed", actor=operator, request=request,
        target_type="tenant", target_id=tenant_id,
        detail={"from": before, "to": payload.plan_code, "note": payload.note},
    )
    _emit_plan_changed(tenant_id, before, payload.plan_code)
    return tenant


@router.patch(
    "/tenants/{tenant_id}/status",
    dependencies=[Depends(limit_catalog)],
)
def change_tenant_status(
    tenant_id: str,
    payload: StatusChange,
    request: Request,
    operator: Dict[str, Any] = Depends(require_sudo),
) -> Dict[str, Any]:
    """Treo hoặc mở lại một tổ chức."""
    from app import audit

    try:
        tenant = tenant_admin.set_billing_status(
            tenant_id, payload.billing_status, reason=payload.reason
        )
    except tenant_admin.TenantError as exc:
        raise _translate(exc) from exc

    audit.record(
        "tenant.status_changed", actor=operator, request=request,
        target_type="tenant", target_id=tenant_id,
        detail={"status": payload.billing_status, "reason": payload.reason},
    )
    return tenant


def _emit_plan_changed(tenant_id: str, before: Optional[str], after: str) -> None:
    """Báo cho webhook của chính tổ chức đó biết gói vừa đổi.

    Tách thành hàm riêng và nuốt lỗi ở trong: đổi gói đã thành công rồi, và một
    sự cố ở tầng webhook không được biến câu trả lời thành lỗi.
    """
    try:
        from app.webhooks import emit

        emit(tenant_id, "tenant.plan_changed", {"from": before, "to": after})
    except Exception as exc:
        logger.warning("[BILLING] không phát được sự kiện đổi gói: %s", type(exc).__name__)
