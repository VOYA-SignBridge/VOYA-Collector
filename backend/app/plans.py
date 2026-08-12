"""Gói dịch vụ và hạn mức: nơi duy nhất trả lời "tenant này được làm gì".

Vì sao hạn mức đọc từ nguồn thật, không từ bộ đếm riêng
--------------------------------------------------------
Cách thường thấy là nuôi một bộ đếm (`tenant_usage.samples = 1200`) và tăng nó
ở mỗi lượt ghi. Cách đó nhanh hơn, và nó sai mỗi khi một lượt ghi hỏng giữa
chừng, mỗi khi ai đó xoá dữ liệu bằng SQL, mỗi khi một tác vụ nền chèn hàng mà
quên gọi bộ đếm. Sai lệch đó không tự lộ ra: người dùng chỉ thấy mình bị chặn ở
mức 900 mẫu trên gói 1000, hoặc tệ hơn, vượt trần mà không ai biết.

Ở đây `count(*)` chạy thẳng trên bảng nguồn, có chỉ mục `tenant_id`. Với quy mô
của nền tảng này (mẫu nhiều nhất là vài chục nghìn dòng một tenant) đó là một
index-only scan vài mili-giây, và nó **không thể lệch** vì không có bản sao nào
để lệch. Bảng `tenant_usage_daily` tồn tại cho hoá đơn và biểu đồ — nó là bản
GỘP để đọc nhanh theo thời gian, không phải nguồn để chặn.

Nếu một ngày `samples` lớn tới mức `count(*)` thành nút cổ chai, chỗ sửa là
thêm một bộ đếm có đối chiếu định kỳ với `count(*)` — không phải thay thế nó.

NULL nghĩa là không giới hạn
-----------------------------
Quy ước của bảng `plans` (xem v4.1). Ở đây nó thành một dòng: `if limit is
None: return`. Không có số thần kỳ nào phải nhớ.

Vì sao 402 chứ không phải 403
------------------------------
403 nghĩa là "bạn không được phép" — người dùng không làm gì thay đổi được.
402 Payment Required nghĩa là "yêu cầu hợp lệ, gói của bạn không đủ" — có đường
đi tiếp, và đường đó là nâng gói. Giao diện cần phân biệt hai thứ đó để hiện
đúng nút; trả cùng một mã cho cả hai là ép giao diện đoán bằng chuỗi thông báo.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.tenancy import DEFAULT_TENANT_ID, normalize_tenant_id

logger = logging.getLogger(__name__)


class QuotaExceeded(Exception):
    """Gói hiện tại không đủ cho thao tác vừa yêu cầu."""

    def __init__(
        self,
        message: str,
        *,
        metric: str = "",
        limit: Optional[int] = None,
        current: Optional[int] = None,
        status_code: int = 402,
    ) -> None:
        super().__init__(message)
        self.metric = metric
        self.limit = limit
        self.current = current
        self.status_code = status_code


class TenantSuspended(Exception):
    """Tenant đang bị treo hoặc đã huỷ — mọi đường ghi đóng lại."""

    def __init__(self, message: str, *, status_code: int = 403) -> None:
        super().__init__(message)
        self.status_code = status_code


#: Trạng thái thanh toán còn được phép GHI. `past_due` vẫn ghi được có chủ ý:
#: khoá dữ liệu của một trường vì hoá đơn trễ vài ngày là cách nhanh nhất để
#: mất họ, và số tiền không vì thế mà đòi được nhanh hơn. Treo là quyết định
#: của người vận hành (`suspended`), không phải hệ quả tự động của một ngày.
WRITABLE_BILLING_STATUSES: Tuple[str, ...] = ("trialing", "active", "past_due")


# --------------------------------------------------------------------------- plans

_PLAN_CACHE_TTL = 30.0
_plan_cache: Dict[str, Tuple[float, Optional[Dict[str, Any]]]] = {}


def _clear_caches() -> None:
    """Dùng trong test và ngay sau khi đổi gói. Không phải API công khai."""
    _plan_cache.clear()


def list_plans(*, include_unlisted: bool = False) -> List[Dict[str, Any]]:
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    where = "" if include_unlisted else "WHERE is_listed"
    with system_scope("plans: read the platform price list"):
        rows = _fetch_all(f"SELECT * FROM plans {where} ORDER BY sort_order, plan_code")
    return [dict(r) for r in rows]


def get_plan(plan_code: str) -> Optional[Dict[str, Any]]:
    """Một gói theo mã, có đệm 30 giây.

    Đệm được vì bảng giá đổi vài lần một năm còn đường đọc chạy ở mỗi lượt tải
    lên. Cùng lý do và cùng thời hạn với `platform_settings`.
    """
    code = (plan_code or "").strip()
    if not code:
        return None

    hit = _plan_cache.get(code)
    now = time.monotonic()
    if hit and now - hit[0] < _PLAN_CACHE_TTL:
        return hit[1]

    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    try:
        with system_scope("plans: read one plan"):
            rows = _fetch_all("SELECT * FROM plans WHERE plan_code = %s", (code,))
        plan = dict(rows[0]) if rows else None
    except Exception as exc:
        # Không đệm thất bại: một lỗi kết nối thoáng qua không được biến thành
        # 30 giây "gói này không tồn tại" cho mọi lượt gọi tiếp theo.
        logger.warning("[PLANS] không đọc được gói %s: %s", code, type(exc).__name__)
        raise

    _plan_cache[code] = (now, plan)
    return plan


def plan_for_tenant(tenant_id: Optional[str]) -> Dict[str, Any]:
    """Gói đang có hiệu lực của một tenant.

    Không tìm thấy tenant, hoặc tenant chưa gắn gói, thì trả về gói `trial` —
    tức là hạn mức CHẶT NHẤT, không phải rộng nhất. Một lỗi tra cứu phải nghiêng
    về từ chối; nghiêng về cho phép nghĩa là mọi sự cố đều mở toang hạn mức.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id) if tenant_id else DEFAULT_TENANT_ID
    with system_scope("plans: resolve the plan of a tenant"):
        rows = _fetch_all(
            "SELECT plan_code, billing_status FROM tenants WHERE tenant_id = %s",
            (tenant,),
        )
    code = (rows[0].get("plan_code") if rows else None) or settings.self_serve_plan_code
    plan = get_plan(code) or get_plan("trial")
    if plan is None:
        # Bảng giá trống. Xảy ra được duy nhất khi migration chưa chạy xong;
        # trả về một gói bằng 0 để đường ghi đóng lại chứ không mở ra.
        logger.error("[PLANS] bảng plans trống — áp hạn mức bằng 0 cho %s", tenant)
        return {
            "plan_code": "unknown", "display_name": "Không xác định",
            "max_seats": 0, "max_samples": 0, "max_storage_mb": 0, "max_classes": 0,
            "max_training_jobs_per_month": 0, "max_concurrent_training_jobs": 0,
            "max_queued_training_jobs": 0, "max_api_keys": 0,
            "max_webhook_endpoints": 0,
        }
    return plan


#: Cột sửa được lúc chạy, kèm (kiểu, cho phép NULL).
#:
#: Danh sách trắng, không phải bảng tự do — cùng lý do với
#: `platform_settings.EDITABLE`. `plan_code` vắng mặt có chủ ý: nó là khoá
#: chính và có khoá ngoại từ `tenants` và `tenant_subscriptions` trỏ tới, nên
#: đổi nó là đổi định danh của một gói đang được dùng. Đặt tên khác thì tạo gói
#: mới rồi chuyển tenant sang, đừng đổi tên gói cũ.
EDITABLE_PLAN_FIELDS: Dict[str, bool] = {
    # tên cột -> có cho phép NULL (tức "không giới hạn") không
    "display_name": False,
    "description": False,
    "max_seats": True,
    "max_samples": True,
    "max_storage_mb": True,
    "max_classes": True,
    "max_training_jobs_per_month": True,
    "max_concurrent_training_jobs": False,
    "max_queued_training_jobs": False,
    "max_api_keys": False,
    "max_webhook_endpoints": False,
    "price_cents": False,
    "is_self_serve": False,
    "is_listed": False,
    "trial_days": False,
}


class PlanError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def update_plan(plan_code: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    """Sửa hạn mức của một gói mà không cần triển khai lại.

    Tồn tại vì migration v4.1 seed bảng giá bằng `ON CONFLICT DO NOTHING` — cố
    ý, để một lần khởi động lại không ghi đè mọi chỉnh tay. Nhưng nếu không có
    đường sửa nào thì "chỉnh tay" chỉ có nghĩa là gõ SQL vào cơ sở dữ liệu sản
    xuất, và chú thích trong migration hoá ra hứa một thứ không tồn tại.

    Xoá bộ đệm ngay sau khi ghi: `get_plan` đệm 30 giây, và người vận hành vừa
    sửa hạn mức sẽ tải lại trang để xem kết quả trong vòng vài giây.
    """
    plan = get_plan(plan_code)
    if plan is None:
        raise PlanError(f"gói {plan_code!r} không tồn tại", status_code=404)

    unknown = sorted(set(changes) - set(EDITABLE_PLAN_FIELDS))
    if unknown:
        raise PlanError(f"không sửa được các trường: {', '.join(unknown)}", status_code=422)

    sets, params = [], []
    for column, value in changes.items():
        if value is None and not EDITABLE_PLAN_FIELDS[column]:
            raise PlanError(
                f"{column} không nhận giá trị rỗng — chỉ những trần có thể "
                f"'không giới hạn' mới nhận NULL",
                status_code=422,
            )
        sets.append(f"{column} = %s")
        params.append(value)

    if not sets:
        return plan

    from app.storage.metadata_db import _execute
    from app.tenant_context import system_scope

    params.append(plan_code)
    with system_scope("plans: an operator edits the price list"):
        try:
            _execute(
                f"UPDATE plans SET {', '.join(sets)}, updated_at = NOW() "
                f"WHERE plan_code = %s",
                tuple(params),
            )
        except Exception as exc:
            # `ck_plans_limits_non_negative` là chỗ chặn số âm; dịch nó thành
            # một câu người vận hành đọc được thay vì để lộ thông điệp Postgres.
            raise PlanError(
                f"giá trị không hợp lệ cho gói {plan_code!r}: {exc}", status_code=422
            ) from exc
    _clear_caches()
    logger.info("[PLANS] sửa gói %s: %s", plan_code, sorted(changes))
    return get_plan(plan_code) or plan


def billing_status_of(tenant_id: Optional[str]) -> str:
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id) if tenant_id else DEFAULT_TENANT_ID
    with system_scope("plans: read the billing status of a tenant"):
        rows = _fetch_all(
            "SELECT billing_status FROM tenants WHERE tenant_id = %s", (tenant,)
        )
    return (rows[0].get("billing_status") if rows else None) or "active"


# --------------------------------------------------------------------------- usage

#: Mỗi chỉ số: (cột hạn mức trong `plans`, câu đếm, nhãn tiếng Việt).
#:
#: Một bảng duy nhất cho cả đo lẫn chặn. Tách ra hai chỗ là cách chắc chắn để
#: một ngày nào đó biểu đồ nói 900 còn bộ chặn nói 1200 trên cùng một tenant.
USAGE_METRICS: Dict[str, Tuple[Optional[str], str, str]] = {
    "samples": (
        "max_samples",
        "SELECT count(*) AS n FROM samples WHERE tenant_id = %s AND deleted_at IS NULL",
        "số mẫu",
    ),
    "classes": (
        "max_classes",
        "SELECT count(*) AS n FROM classes WHERE tenant_id = %s AND deleted_at IS NULL",
        "số lớp từ vựng",
    ),
    "seats": (
        "max_seats",
        "SELECT count(*) AS n FROM tenant_members WHERE tenant_id = %s",
        "số thành viên",
    ),
    "api_keys": (
        "max_api_keys",
        "SELECT count(*) AS n FROM api_keys WHERE tenant_id = %s AND revoked_at IS NULL",
        "số khoá API",
    ),
    "webhook_endpoints": (
        "max_webhook_endpoints",
        "SELECT count(*) AS n FROM webhook_endpoints WHERE tenant_id = %s AND is_active",
        "số webhook",
    ),
    "training_jobs_this_month": (
        "max_training_jobs_per_month",
        "SELECT count(*) AS n FROM training_jobs WHERE tenant_id = %s "
        "AND created_at >= date_trunc('month', NOW())",
        "số lượt huấn luyện trong tháng",
    ),
    "training_jobs_running": (
        "max_concurrent_training_jobs",
        "SELECT count(*) AS n FROM training_jobs WHERE tenant_id = %s "
        "AND status = 'running'",
        "số lượt huấn luyện đang chạy",
    ),
    "training_jobs_queued": (
        "max_queued_training_jobs",
        "SELECT count(*) AS n FROM training_jobs WHERE tenant_id = %s "
        "AND status = 'queued'",
        "số lượt huấn luyện đang chờ",
    ),
}


def current_usage(tenant_id: str, metric: str) -> int:
    """Số hiện tại của một chỉ số, đọc từ bảng nguồn.

    Trả 0 khi truy vấn hỏng. Đây là lựa chọn fail-OPEN, ngược với phần còn lại
    của module, và nó có lý do: chỉ số đếm được dùng ở đường ghi nóng, và biến
    một sự cố cơ sở dữ liệu thành "mọi người hết hạn mức" là nhân sự cố lên.
    Ranh giới thật — ai đọc được dữ liệu nào — nằm ở RLS, không ở đây.
    """
    spec = USAGE_METRICS.get(metric)
    if spec is None:
        raise KeyError(f"chỉ số không biết: {metric!r}")

    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id)
    try:
        with system_scope(f"plans: count {metric} of a tenant"):
            rows = _fetch_all(spec[1], (tenant,))
        return int(rows[0]["n"]) if rows else 0
    except Exception as exc:
        logger.warning(
            "[PLANS] không đếm được %s cho %s: %s", metric, tenant, type(exc).__name__
        )
        return 0


def usage_snapshot(tenant_id: str) -> Dict[str, Dict[str, Any]]:
    """Mọi chỉ số kèm trần của nó — thứ giao diện "mức dùng" cần trong một lượt."""
    plan = plan_for_tenant(tenant_id)
    out: Dict[str, Dict[str, Any]] = {}
    for metric, (limit_column, _sql, label) in USAGE_METRICS.items():
        limit = plan.get(limit_column) if limit_column else None
        used = current_usage(tenant_id, metric)
        out[metric] = {
            "label": label,
            "used": used,
            "limit": limit,
            "unlimited": limit is None,
            # Phần trăm chỉ có nghĩa khi có trần; None ở đây để giao diện vẽ
            # thanh tiến trình hoặc không, thay vì chia cho None.
            "percent": None if limit in (None, 0) else round(used * 100.0 / limit, 1),
        }
    out["_plan"] = {
        "plan_code": plan.get("plan_code"),
        "display_name": plan.get("display_name"),
    }
    return out


# --------------------------------------------------------------------------- gates


def assert_writable(tenant_id: str) -> None:
    """Chặn mọi đường ghi của một tenant bị treo hoặc đã huỷ."""
    status = billing_status_of(tenant_id)
    if status not in WRITABLE_BILLING_STATUSES:
        raise TenantSuspended(
            "Tổ chức của bạn đang tạm ngưng dịch vụ "
            f"(trạng thái: {status}). Vui lòng liên hệ quản trị viên nền tảng."
        )


def check_quota(tenant_id: str, metric: str, *, adding: int = 1) -> None:
    """Ném `QuotaExceeded` nếu thêm `adding` đơn vị nữa sẽ vượt trần.

    So sánh là `used + adding > limit`, không phải `used >= limit`: người dùng
    ở đúng mức 500/500 phải bị chặn ở lần thêm tiếp theo, còn người ở 499 tải
    lên một lượt 5 mẫu cũng phải bị chặn — kiểm từng-cái-một sẽ cho lọt bốn cái.
    """
    spec = USAGE_METRICS.get(metric)
    if spec is None:
        raise KeyError(f"chỉ số không biết: {metric!r}")
    limit_column, _sql, label = spec

    plan = plan_for_tenant(tenant_id)
    limit = plan.get(limit_column) if limit_column else None
    if limit is None:
        return

    used = current_usage(tenant_id, metric)
    if used + adding > limit:
        raise QuotaExceeded(
            f"Gói \"{plan.get('display_name') or plan.get('plan_code')}\" cho phép tối đa "
            f"{limit} {label}; hiện đã dùng {used}. Nâng gói để tiếp tục.",
            metric=metric,
            limit=int(limit),
            current=int(used),
        )


def enforce(tenant_id: str, metric: str, *, adding: int = 1) -> None:
    """Hai cổng thường đi cùng nhau: còn được ghi không, và còn hạn mức không.

    Gộp lại thành một lời gọi vì gọi thiếu một trong hai là lỗi dễ mắc và
    không lộ ra — đường ghi vẫn chạy đúng cho tới khi gặp một tenant bị treo.
    """
    assert_writable(tenant_id)
    check_quota(tenant_id, metric, adding=adding)
