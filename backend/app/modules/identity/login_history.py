"""Lịch sử đăng nhập của chính người dùng.

Ghi vào `audit_log` (hành động `auth.login`) chứ không dựng bảng mới: nhật ký kiểm
toán đã là sổ bền, có chỉ mục theo người thực hiện, và đã là nơi các thao tác bảo
mật khác của tài khoản được ghi.

Không lưu IP thô. `audit.record` chỉ giữ BẢN BĂM của IP. Thứ người dùng cần để nhận
ra một lần đăng nhập lạ là thiết bị và, nếu máy chủ có cơ sở dữ liệu GeoIP, nơi
đăng nhập ở mức thành phố/quốc gia — cả hai đều lưu dạng nhãn, không phải địa chỉ.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.modules.identity.device_sessions import clip_user_agent, describe_device

logger = logging.getLogger(__name__)

ACTION = "auth.login"


def _place(request: Any) -> str:
    """Nơi đăng nhập ("Cần Thơ, Việt Nam"), hoặc rỗng nếu không biết. Không bao giờ ném."""
    try:
        from app.modules.security import geo
        from app.modules.security._web_compat import client_ip

        return geo.location_label(geo.geo_lookup(client_ip(request))) or ""
    except Exception:  # noqa: BLE001 — định vị chỉ để trang trí
        return ""


def record_login(user: Dict[str, Any], request: Any, remember: bool) -> None:
    """Ghi một lần đăng nhập THÀNH CÔNG. Không bao giờ ném: phiên đã được cấp rồi.

    Trang đăng nhập không có phạm vi tổ chức, mà `audit.record` cần một phạm vi và
    nuốt lỗi khi thiếu — gọi trần thì dấu vết biến mất lặng lẽ. Nên vào đúng tổ chức
    của người này trước.
    """
    try:
        from app.modules.saas.tenant_context import tenant_scope
        from app.modules.saas.tenant_middleware import _tenant_of_user
        from app.modules.security import audit

        tenant = _tenant_of_user(str(user["id"]))
        if not tenant:
            return
        agent = clip_user_agent(request.headers.get("user-agent"))
        detail = {"device": describe_device(agent), "remember": bool(remember)}
        place = _place(request)
        if place:
            detail["place"] = place
        with tenant_scope(tenant):
            audit.record(
                ACTION,
                actor={"id": str(user["id"]), "username": user.get("username")},
                target_type="user",
                target_id=str(user["id"]),
                detail=detail,
                request=request,
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("[LOGIN] khong ghi duoc lich su dang nhap: %s", exc.__class__.__name__)


def recent_logins(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Các lần đăng nhập gần đây của `user_id`, mới nhất trước.

    Đọc theo PHẠM VI của request (RLS) và chỉ hàng của chính người này.
    """
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        """
        SELECT created_at, detail
        FROM audit_log
        WHERE actor_user_id = %s AND action = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (str(user_id), ACTION, max(1, min(int(limit), 50))),
    )
    out = []
    for r in rows:
        d = r.get("detail") or {}
        out.append(
            {
                "at": r["created_at"],
                "device": d.get("device") or "Thiết bị không xác định",
                "place": d.get("place") or "",
                "remember": bool(d.get("remember")),
            }
        )
    return out

