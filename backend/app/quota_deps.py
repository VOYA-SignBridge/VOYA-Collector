"""Cầu nối giữa lớp hạn mức và tầng HTTP.

`app/plans.py` cố ý không biết gì về FastAPI: nó được gọi từ router, từ tác vụ
Celery và từ CLI, và hai trong ba chỗ đó không có request nào để trả mã lỗi.
Module này là chỗ duy nhất dịch `QuotaExceeded`/`TenantSuspended` thành
`HTTPException`, theo đúng khuôn `rate_limit_deps.py` đã dùng cho giới hạn tần
suất.

Vì sao trả cả `X-Quota-*` trong header
---------------------------------------
Giao diện cần biết mình đụng trần nào và trần đó là bao nhiêu để hiện đúng câu
"đã dùng 500/500 mẫu" kèm nút nâng gói. Nhét mấy con số đó vào chuỗi thông báo
buộc giao diện phải phân tích văn bản tiếng Việt — thứ sẽ hỏng ngay lần đầu ai
đó sửa lại câu chữ. Header là dữ liệu, câu thông báo là cho người đọc.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.plans import QuotaExceeded, TenantSuspended, enforce
from app.tenancy import normalize_tenant_id


def tenant_of(current_user: Optional[Dict[str, Any]]) -> str:
    """Tenant nhà của người gọi.

    Lấy từ bản ghi tài khoản chứ không từ ngữ cảnh yêu cầu: hai thứ này gần
    như luôn bằng nhau, nhưng khi lệch thì bản ghi tài khoản mới là thứ quyết
    định dữ liệu ghi vào đâu — nên hạn mức phải tính trên chính nó.
    """
    return normalize_tenant_id((current_user or {}).get("tenant_id"))


def guard_quota(
    current_user: Optional[Dict[str, Any]],
    metric: str,
    *,
    adding: int = 1,
) -> None:
    """Chặn thao tác nếu tenant bị treo hoặc đã chạm trần gói.

    Gọi ở ĐẦU handler, trước mọi tác dụng phụ. Gọi sau khi đã ghi tệp thì hạn
    mức không còn là hạn mức nữa — nó chỉ là một thông báo sau khi chuyện đã
    rồi.
    """
    tenant_id = tenant_of(current_user)
    try:
        enforce(tenant_id, metric, adding=adding)
    except TenantSuspended as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except QuotaExceeded as exc:
        _announce_quota_exceeded(tenant_id, exc)
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
            headers={
                "X-Quota-Metric": exc.metric,
                "X-Quota-Limit": str(exc.limit if exc.limit is not None else ""),
                "X-Quota-Current": str(exc.current if exc.current is not None else ""),
            },
        ) from exc


def _announce_quota_exceeded(tenant_id: str, exc: QuotaExceeded) -> None:
    """Báo cho hệ thống của khách hàng biết họ vừa chạm trần.

    Đây là sự kiện duy nhất trong hệ phát ra từ một đường THẤT BẠI, và nó đáng
    có: người bị chặn là người đang thao tác trên giao diện, còn người cần
    biết để nâng gói thường là người khác — quản trị viên của tổ chức, hoặc
    một hệ thống theo dõi bên họ. Không có sự kiện này thì thông tin dừng lại
    ở màn hình của người đang bị chặn.

    Chống dội: một vòng lặp tải lên đang bị chặn sẽ gọi hàm này ở MỖI lượt, và
    không có gì hãm thì một buổi chiều hỏng có thể sinh hàng nghìn lần giao.
    Một khoá Redis sống 15 phút cho mỗi (tenant, chỉ số) là đủ: người ta cần
    biết mình chạm trần, không cần biết mình chạm trần một nghìn lần.
    """
    try:
        from app.rate_limit import _client

        client = _client()
        if client is not None:
            key = f"quota:announced:{tenant_id}:{exc.metric}"
            # `nx=True` — chỉ đặt được nếu chưa có. Trả về None nghĩa là khoá
            # đã tồn tại, tức đã báo trong 15 phút qua.
            if not client.set(key, "1", ex=900, nx=True):
                return
    except Exception:
        # Redis chết thì vẫn phát, chỉ mất phần chống dội. Fail-open ở đây
        # cùng lý do với `rate_limit` và `trial`: thứ bị rủi ro là một thông
        # báo trùng lặp, không phải dữ liệu của ai.
        pass

    try:
        from app.webhooks import emit

        emit(tenant_id, "quota.exceeded", {
            "metric": exc.metric, "limit": exc.limit, "current": exc.current,
        })
    except Exception:
        pass
