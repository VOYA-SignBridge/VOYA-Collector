"""Mặt giao diện của `app.modules.export.personal_export` — "cho tôi tệp của chính tôi".

Mọi thành viên đã đăng nhập gọi được, không cần vai biên tập hay quản trị:
phạm vi luôn tự khoá vào chính tài khoản đang gọi (`current_user["id"]`), không
bao giờ nhận id của ai khác qua tham số — khác hẳn `/tenants/{id}/exports`, nơi
người gọi PHẢI là quản trị viên vì gói đó chứa dữ liệu của cả tổ chức.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.modules.identity._web_compat import get_current_user
from app.modules.saas.tenant_context import require_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me/exports", tags=["personal-export"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def request_export(
    request: Request, current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Đặt hàng một bản xuất dữ liệu của chính người gọi. Trả về ngay.

    202 chứ không 201, cùng lý do với `/tenants/{id}/exports`: chưa có gì tải
    được — việc dựng gói do tác vụ nền làm.

    Không đòi cam kết sử dụng như `/tenants/{id}/exports`: gói ở đó chứa dữ
    liệu của NHIỀU người đóng góp, gói này chỉ chứa dữ liệu của chính người
    đang gọi — không có bên thứ ba nào để cam kết bảo vệ.
    """
    from app.modules.export import personal_export
    from app.modules.security import audit

    tenant = require_tenant()
    uid = str(current_user.get("id") or "")
    job = personal_export.request_export(tenant, uid)
    audit.record(
        "personal_export.requested", actor=current_user, request=request,
        target_type="personal_export", target_id=job["export_id"], tenant_id=tenant,
    )

    try:
        from app.modules.saas.saas_tasks import run_personal_export

        run_personal_export.delay(job["export_id"])
    except Exception as exc:
        # Yêu cầu đã nằm trong bảng ở trạng thái 'pending', nên nó không mất.
        logger.error("[PERSONAL_EXPORT] không phái được tác vụ: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Đã ghi nhận yêu cầu nhưng chưa phái được tác vụ xử lý. Hãy thử lại.",
        ) from exc

    return job


@router.get("")
def list_exports(current_user: Dict[str, Any] = Depends(get_current_user)) -> List[Dict[str, Any]]:
    from app.modules.export import personal_export

    tenant = require_tenant()
    uid = str(current_user.get("id") or "")
    return personal_export.list_exports(tenant, uid)


@router.get("/{export_id}/download")
def download_export(
    export_id: str, request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Tải tệp. Ghi kiểm toán ở ĐÂY, không chỉ lúc đặt hàng — cùng lý do với
    `/tenants/{id}/exports/{export_id}/download`: đặt hàng và tải về là hai
    thời điểm khác nhau."""
    from fastapi.responses import FileResponse

    from app.modules.export import personal_export
    from app.modules.security import audit

    tenant = require_tenant()
    uid = str(current_user.get("id") or "")
    try:
        path = personal_export.export_file(tenant, uid, export_id)
    except personal_export.PersonalExportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    audit.record(
        "personal_export.downloaded", actor=current_user, request=request,
        target_type="personal_export", target_id=export_id, tenant_id=tenant,
    )
    return FileResponse(
        path, media_type="application/zip", filename="du-lieu-cua-toi.zip"
    )
