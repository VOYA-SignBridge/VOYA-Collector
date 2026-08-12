"""Khoá API và webhook — hai đường để hệ thống khác nối vào nền tảng.

Quyền: `require_tenant_editor`, không phải `require_admin`.

Đây là quyết định có cân nhắc. Khoá API của một tổ chức là việc của tổ chức
đó; bắt họ mở phiếu yêu cầu để người vận hành nền tảng cấp hộ là biến một sản
phẩm tự phục vụ thành một quầy dịch vụ. Rủi ro được chặn ở chỗ khác: khoá
không bao giờ vượt được quyền của tenant nó thuộc về, và hạn mức `max_api_keys`
của gói giới hạn số khoá tồn tại cùng lúc.

Bí mật hiện đúng một lần
-------------------------
`POST /api-keys` và `POST /webhooks` là những chỗ DUY NHẤT trả về khoá thật và
bí mật ký. Không endpoint nào đọc lại được — với khoá API thì vì chỉ băm được
lưu, với webhook thì vì câu SELECT trong `webhooks.list_endpoints` không lấy
cột đó. Người dùng mất thì cấp lại; đó rẻ hơn nhiều so với việc giữ một bản có
thể bị lấy đi.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app import api_keys as api_keys_service
from app import webhooks as webhooks_service
from app.auth import require_tenant_editor
from app.quota_deps import tenant_of
from app.rate_limit_deps import limit_catalog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


class ApiKeyCreate(BaseModel):
    name: str = Field("", max_length=120)
    scopes: str = Field("read", max_length=16)
    expires_in_days: Optional[int] = Field(None, ge=1, le=3650)


class WebhookCreate(BaseModel):
    url: str = Field(..., min_length=8, max_length=2000)
    event_types: str = Field("*", max_length=500)
    description: str = Field("", max_length=500)


# --------------------------------------------------------------------------- api keys


@router.get("/api-keys")
def list_api_keys(
    include_revoked: bool = False,
    current_user: Dict[str, Any] = Depends(require_tenant_editor),
) -> List[Dict[str, Any]]:
    return api_keys_service.list_keys(
        tenant_of(current_user), include_revoked=include_revoked
    )


@router.post(
    "/api-keys",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_catalog)],
)
def create_api_key(
    payload: ApiKeyCreate,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_tenant_editor),
) -> Dict[str, Any]:
    """Cấp khoá mới. Trường `key` trong câu trả lời không xuất hiện lần thứ hai."""
    from app import audit

    expires_at = None
    if payload.expires_in_days:
        from datetime import timedelta

        expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)

    try:
        result = api_keys_service.create_key(
            tenant_of(current_user),
            name=payload.name,
            scopes=payload.scopes,
            created_by=str(current_user.get("id") or ""),
            expires_at=expires_at,
        )
    except api_keys_service.ApiKeyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    # Ghi PREFIX, không ghi khoá. `audit._redact` đã chặn khoá "api_key" nhưng
    # cách chắc chắn nhất vẫn là không đưa nó vào lời gọi.
    audit.record(
        "api_key.created", actor=current_user, request=request,
        target_type="api_key", target_id=result["key_id"],
        detail={"prefix": result["prefix"], "scopes": result["scopes"]},
    )
    return result


@router.delete(
    "/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # Không có dòng này FastAPI suy ra một response model từ chú thích trả về
    # rồi từ chối, vì 204 không được mang thân thư. Cùng khuôn với
    # `tenants.remove_member`.
    response_class=Response,
)
def revoke_api_key(
    key_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_tenant_editor),
) -> Response:
    from app import audit

    try:
        api_keys_service.revoke_key(
            tenant_of(current_user), key_id, revoked_by=str(current_user.get("id") or "")
        )
    except api_keys_service.ApiKeyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    audit.record(
        "api_key.revoked", actor=current_user, request=request,
        target_type="api_key", target_id=str(key_id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- webhooks


@router.get("/webhooks/event-types")
def list_event_types() -> Dict[str, Any]:
    """Danh sách loại sự kiện đăng ký được.

    Có endpoint riêng để giao diện dựng được ô chọn từ dữ liệu thật thay vì
    chép cứng một danh sách sẽ lệch khỏi backend ở lần thêm sự kiện tiếp theo.
    """
    return {"event_types": list(webhooks_service.EVENT_TYPES)}


@router.get("/webhooks")
def list_webhooks(
    current_user: Dict[str, Any] = Depends(require_tenant_editor),
) -> List[Dict[str, Any]]:
    return webhooks_service.list_endpoints(tenant_of(current_user))


@router.post(
    "/webhooks",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_catalog)],
)
def create_webhook(
    payload: WebhookCreate,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_tenant_editor),
) -> Dict[str, Any]:
    from app import audit

    try:
        result = webhooks_service.create_endpoint(
            tenant_of(current_user),
            url=payload.url,
            event_types=payload.event_types,
            description=payload.description,
            created_by=str(current_user.get("id") or ""),
        )
    except webhooks_service.WebhookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    audit.record(
        "webhook.created", actor=current_user, request=request,
        target_type="webhook", target_id=result["endpoint_id"],
        detail={"url": result["url"], "event_types": result["event_types"]},
    )
    return result


@router.delete(
    "/webhooks/{endpoint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_webhook(
    endpoint_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_tenant_editor),
) -> Response:
    from app import audit

    try:
        webhooks_service.delete_endpoint(tenant_of(current_user), endpoint_id)
    except webhooks_service.WebhookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    audit.record(
        "webhook.deleted", actor=current_user, request=request,
        target_type="webhook", target_id=str(endpoint_id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/webhooks/{endpoint_id}/test", dependencies=[Depends(limit_catalog)])
def test_webhook(
    endpoint_id: str,
    current_user: Dict[str, Any] = Depends(require_tenant_editor),
) -> Dict[str, Any]:
    """Xếp một sự kiện thử vào hàng giao cho đúng endpoint này."""
    try:
        delivery_id = webhooks_service.queue_test_delivery(
            tenant_of(current_user), endpoint_id
        )
    except webhooks_service.WebhookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {"queued": True, "delivery_id": delivery_id}


@router.get("/webhooks/{endpoint_id}/deliveries")
def list_deliveries(
    endpoint_id: str,
    limit: int = 25,
    current_user: Dict[str, Any] = Depends(require_tenant_editor),
) -> List[Dict[str, Any]]:
    """Lịch sử giao gần đây của một endpoint — thứ cần để gỡ rối một tích hợp."""
    return webhooks_service.recent_deliveries(
        tenant_of(current_user), endpoint_id, limit=limit
    )
