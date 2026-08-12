"""Tenant lifecycle: creating tenants, moving people into them, taking them out.

Why this is a separate plane
----------------------------
Everything else in this codebase acts *inside* one tenant. This module acts
*on* tenants, which means most of its work is cross-tenant by construction: a
platform operator sitting in the `default` tenant creates tenant B and invites
someone into it. Those operations therefore run in `system_scope`, and this
module is on the boundary allowlist in `test_tenant_isolation.py` for that
reason.

The crossing is kept here, in the service layer, and NOT in `routers/tenants.py`
— a request handler that runs as every tenant is the shape most likely to grow
an accidental hole later, and there is a test asserting no router except
`sot_admin` contains one.

How a person ends up in a tenant
--------------------------------
Exactly three ways, all deliberate:

1. **A platform operator adds an existing account** (`add_member`).
2. **An invitation is accepted at registration** (`consume_invitation`).
3. **Someone signs up without an invitation** (`create_self_serve_tenant`) and
   gets a brand-new tenant of their own, on the trial plan.

Đường thứ ba được thêm ở v4, và nó thay thế một hành vi CŨ NGUY HIỂM: trước
đây, đăng ký không kèm lời mời để tài khoản lại trong tenant bootstrap — tức
là trong đúng tổ chức đang giữ toàn bộ dữ liệu thật. Người lạ đăng ký xong là
thành viên hoạt động ở đó. Không còn đường nào dẫn vào tenant gốc nữa: hoặc
tenant riêng, hoặc bị từ chối (`settings.self_serve_signup`).

Lo ngại cũ — tenant-spam — được xử bằng hạn mức chứ không bằng cách đóng cửa:
gói `trial` cho 3 ghế, 500 mẫu, 1 lượt huấn luyện đồng thời, và `rate_limit`
đã chặn số tài khoản tạo được mỗi ngày trên một IP. Một tenant rác tốn đúng
một dòng bảng và một danh mục sao chép.

Home tenant vs membership
-------------------------
`users.tenant_id` is the **home** tenant — the one the request scope resolves
to, the one whose data the person sees. `tenant_members` carries **membership**,
and separately a role. Every user has exactly one home tenant and a matching
member row; `orphaned_members()` reports drift rather than letting the two
disagree silently.

Membership và vai là HAI sự thật, không phải một
-------------------------------------------------
`tenant_members.role` nhận `'admin'`, `'editor'`, hoặc **NULL** — và NULL không
phải dữ liệu thiếu. Nó nghĩa là: người này ở trong tổ chức, và chưa có vai nào ở
tầng tenant. Quyền của họ đến từ assignment ở workspace/project hoặc từ một role
do tổ chức tự tạo.

Cột này từng là `NOT NULL DEFAULT 'viewer'`, tức là ba khái niệm bị ép thành
một: có mặt trong tổ chức, và được cấp một vai đọc được hoá đơn với nhật ký
kiểm toán. Xem `NO_ROLE` bên dưới và
`authorization/catalog.py::RETIRED_BUILTIN_ROLES`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.tenancy import DEFAULT_TENANT_ID, normalize_tenant_id
from app.tenant_context import system_scope
from app.tokens import hash_link_token, new_link_token

logger = logging.getLogger(__name__)

#: Roles a member may hold, most authority first.
#:
#: HAI, không phải ba. `viewer` đã nghỉ cùng role dựng sẵn `tenant_viewer` — xem
#: `authorization/catalog.py::RETIRED_BUILTIN_ROLES`. Thứ thay nó KHÔNG phải một
#: vai khác mà là **không vai nào**: `None`.
ROLES: Tuple[str, ...] = ("admin", "editor")

#: Roles allowed to administer their own tenant (members, invitations).
TENANT_ADMIN_ROLES: Tuple[str, ...] = ("admin",)

#: Tư cách thành viên và vai là HAI chuyện, và đây là chỗ tách chúng ra.
#:
#: `None` nghĩa CHÍNH XÁC là: **tư cách thành viên đang hoạt động, không có
#: authorization grant nào ở phạm vi tenant.**
#:
#: Nó KHÔNG có nghĩa "chỉ đọc"
#: ----------------------------
#: Đây là phân biệt quan trọng nhất trong tệp này, và gọi nhầm nó là "read-only"
#: dẫn tới hai quyết định sai ngược chiều nhau:
#:
#:   * Tưởng nó là một mức QUYỀN → có người sẽ "hoàn thiện" nó bằng cách gắn
#:     thêm quyền đọc, và `tenant_viewer` mọc lại dưới một cái tên khác.
#:   * Tưởng nó CẤM ghi vĩnh viễn → có người sẽ dựa vào đó thay cho một phép
#:     kiểm quyền thật, rồi ngạc nhiên khi một grant ở workspace cho phép ghi.
#:
#: Đúng là: `None` phát biểu về việc KHÔNG có grant ở MỘT phạm vi. Người mang
#: nó vẫn nhận được quyền — kể cả quyền ghi — qua assignment ở
#: workspace/project, hoặc qua một role TỰ TẠO mà chủ tenant dựng. Những đường
#: đó đi qua Casbin, và chúng có hiệu lực thật khi `AUTHZ_MODE=casbin`.
#:
#: Nền tối thiểu mà một thành viên không vai VẪN có
#: -------------------------------------------------
#: Không phải là con số không, và ranh giới được cưỡng chế ở hai chỗ khác nhau:
#:
#:   ĐỌC     RLS cho họ thấy dữ liệu của tenant nhà, y như mọi thành viên khác.
#:           Không có phép kiểm vai nào trên đường đọc, và đó là chủ ý: một
#:           người trong tổ chức phải xem được tổ chức mình.
#:   GHI     Chỉ mặt phẳng TỰ PHỤC VỤ — tài khoản, mật khẩu, phiên, 2FA, xác
#:           minh, đồng thuận, chấp nhận điều khoản, phiếu hỗ trợ, thông báo
#:           của chính họ. Danh sách nằm ở
#:           `access_gate.SELF_SERVICE_WRITE_PREFIXES`, và nó là danh sách
#:           CHO PHÉP: mọi đường ghi khác bị từ chối chừng nào còn ở shadow mode.
#:
#: Hai câu trên là hợp đồng. Đổi một trong hai là đổi ý nghĩa của "không vai".
#:
#: Vì sao nó là MẶC ĐỊNH của cả mời lẫn thêm thành viên
#: -----------------------------------------------------
#: Mặc định cũ là `'viewer'`, và vai đó đọc được hoá đơn, nhật ký kiểm toán,
#: danh sách khoá API và trạng thái đồng thuận của người ký thật. Nghĩa là bấm
#: "Mời" mà không đụng vào ô chọn vai là đã cấp quyền đọc bốn thứ đó — một
#: quyết định phân quyền do một giá trị mặc định đưa ra.
#:
#: Không vai là mặc định an toàn duy nhất: nó không cấp gì, và nó buộc người cấp
#: phải nói ra ý định của mình.
NO_ROLE: None = None


class TenantError(Exception):
    """A tenant operation refused for a business reason.

    Carries an HTTP status so the router can translate without re-deciding what
    each failure means — the decision belongs next to the rule it enforces.
    """

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def _require_role(role: Optional[str]) -> Optional[str]:
    """Chuẩn hoá một vai do người gọi cung cấp. `None` là câu trả lời hợp lệ.

    Ba dạng đầu vào cùng nghĩa "không vai", và cả ba đều phải nhận được, vì
    chúng đến từ ba nơi khác nhau:

        None      lời gọi Python bỏ tham số
        ""        ô `<select>` rỗng trong biểu mẫu, đi qua JSON thành chuỗi rỗng
        "none"    người gõ tay vào API

    Nhận cả ba KHÔNG phải là dễ dãi. Cái nguy hiểm là ngược lại: nếu `""` bị
    coi là một vai không hợp lệ và trả 422, giao diện sẽ buộc phải gửi một vai
    nào đó — và cái được chọn để "cho qua" sẽ là vai thấp nhất, tức là đúng cái
    mặc định âm thầm mà lượt này gỡ đi.

    Một chuỗi KHÁC ba dạng trên và không nằm trong `ROLES` vẫn là 422. Đặc biệt
    `"viewer"`: nó từng hợp lệ, nên nó sẽ còn nằm trong script và bookmark của
    người ta một thời gian nữa, và im lặng dịch nó sang `None` sẽ giấu mất việc
    chỗ gọi đó cần được sửa.
    """
    if role is None:
        return None
    text = str(role).strip().lower()
    if text in ("", "none"):
        return None
    if text not in ROLES:
        raise TenantError(
            f"role must be one of {', '.join(ROLES)}, or empty for no tenant-level role",
            status_code=422,
        )
    return text


def _role_label(role: Optional[str]) -> str:
    """Vai để ghi log. `None` thành một chữ, không thành `"None"`.

    Một dòng log "as None" đọc như một biến chưa gán, và người đọc lúc 2 giờ
    sáng sẽ đi tìm chỗ hỏng. "khong-vai" nói rằng đó là ý định.
    """
    return role or "khong-vai"


def _require_tenant_id(value: str) -> str:
    """Validate a caller-supplied tenant id against the strict alphabet.

    `normalize_tenant_id` raises on a malformed value and falls back on an
    absent one. Creating a tenant is the one place where "absent" must not
    become "default": that would silently return the bootstrap tenant to
    someone who asked for a new one.
    """
    text = (value or "").strip()
    if not text:
        raise TenantError("tenant_id is required", status_code=422)
    try:
        return normalize_tenant_id(text)
    except (ValueError, TypeError) as exc:
        raise TenantError(str(exc), status_code=422) from exc


# --------------------------------------------------------------------------- tenants


def _tenant_row(tenant_id: str) -> Optional[Dict[str, Any]]:
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all("SELECT * FROM tenants WHERE tenant_id = %s", (tenant_id,))
    return dict(rows[0]) if rows else None


def get_tenant(tenant_id: str, *, include_deleted: bool = False) -> Dict[str, Any]:
    with system_scope("tenant admin: read tenant record"):
        row = _tenant_row(_require_tenant_id(tenant_id))
    if not row or (row.get("deleted_at") is not None and not include_deleted):
        raise TenantError(f"tenant {tenant_id!r} not found", status_code=404)
    return row


def list_tenants(*, include_deleted: bool = False) -> List[Dict[str, Any]]:
    """Every tenant, with its member count.

    The count comes from one grouped join rather than a query per tenant: this
    is the platform operator's index page, and the N+1 version gets slower
    exactly as the platform succeeds.
    """
    from app.storage.metadata_db import _fetch_all

    where = "" if include_deleted else "WHERE t.deleted_at IS NULL"
    with system_scope("tenant admin: list every tenant"):
        rows = _fetch_all(
            f"""
            SELECT t.*, COALESCE(m.member_count, 0) AS member_count
            FROM tenants t
            LEFT JOIN (
                SELECT tenant_id, COUNT(*) AS member_count
                FROM tenant_members GROUP BY tenant_id
            ) m ON m.tenant_id = t.tenant_id
            {where}
            ORDER BY t.created_at
            """
        )
    return [dict(r) for r in rows]


def _resolve_plan(plan_code: Optional[str], *, must_be_self_serve: bool = False) -> Dict[str, Any]:
    """Đổi mã gói thành dòng gói, hoặc từ chối.

    Không có đường "gói không tồn tại thì thôi bỏ qua": một tenant không gói là
    một tenant không hạn mức, và cách một hệ thống mất kiểm soát hạn mức là
    chấp nhận âm thầm những mã gói viết sai.
    """
    from app.plans import get_plan

    code = (plan_code or settings.self_serve_plan_code).strip()
    plan = get_plan(code)
    if plan is None:
        raise TenantError(f"gói {code!r} không tồn tại", status_code=422)
    if must_be_self_serve and not plan.get("is_self_serve"):
        raise TenantError(
            f"gói {code!r} không mở cho đăng ký tự phục vụ", status_code=422
        )
    return plan


def create_tenant(
    tenant_id: str,
    *,
    display_name: str = "",
    slug: str = "",
    created_by: Optional[str] = None,
    clone_catalog: bool = True,
    plan_code: Optional[str] = None,
    owner_user_id: Optional[str] = None,
    is_self_serve: bool = False,
) -> Dict[str, Any]:
    """Create a tenant AND give it a working vocabulary catalogue.

    The clone is not an optional extra. `classes` references `dialects` through
    a COMPOSITE foreign key — `(tenant_id, dialect) -> dialects(tenant_id,
    dialect_id)` — so a tenant with no dialect rows of its own cannot hold a
    single class. Creating the `tenants` row alone produces a tenant that looks
    fine in the operator's list and rejects every write, with a foreign-key
    error naming a table the operator never heard of.

    That composite key is the right design: it is what stops tenant B's classes
    from pointing at tenant A's dialects. But it means "create a tenant" and
    "give the tenant a catalogue" are one operation, not two.

    `clone_catalog=False` exists for the tests that want the empty state on
    purpose, and for a restore that will supply its own catalogue.

    Gói là BẮT BUỘC kể từ v4, kể cả khi người gọi không nêu — `_resolve_plan`
    rơi về `settings.self_serve_plan_code`. Một tenant không gói sẽ đi qua mọi
    cổng hạn mức mà không bị hỏi gì, nên "chưa gán gói" không phải một trạng
    thái được phép tồn tại, dù chỉ trong chốc lát.
    """
    tenant_id = _require_tenant_id(tenant_id)
    display = (display_name or tenant_id).strip()
    slug_value = (slug or tenant_id).strip().lower()
    plan = _resolve_plan(plan_code, must_be_self_serve=is_self_serve)

    trial_days = int(plan.get("trial_days") or 0)
    trial_ends = _now() + timedelta(days=trial_days) if trial_days > 0 else None
    # `trialing` chỉ khi gói thật sự có thời hạn dùng thử. Đặt mọi tenant mới
    # vào `trialing` sẽ làm trạng thái này mất nghĩa, và bảng điều khiển "sắp
    # hết hạn dùng thử" sẽ liệt kê cả những tenant đã trả tiền.
    billing_status = "trialing" if trial_ends else "active"

    from app.storage.metadata_db import _execute

    with system_scope("tenant admin: create tenant"):
        if _tenant_row(tenant_id):
            raise TenantError(f"tenant {tenant_id!r} already exists", status_code=409)
        try:
            _execute(
                "INSERT INTO tenants(tenant_id, display_name, slug, plan_code, "
                "billing_status, trial_ends_at, is_self_serve, owner_user_id, "
                "current_period_start) "
                "VALUES(%s, %s, %s, %s, %s, %s, %s, %s, NOW())",
                (
                    tenant_id, display, slug_value, plan["plan_code"],
                    billing_status, trial_ends, bool(is_self_serve),
                    str(owner_user_id) if owner_user_id else None,
                ),
            )
        except Exception as exc:  # unique violation on slug
            raise TenantError(
                f"could not create tenant {tenant_id!r}: {exc}", status_code=409
            ) from exc

        _open_subscription(
            tenant_id, plan["plan_code"], changed_by=created_by,
            note="Dòng mở đầu khi tạo tenant.",
        )

        counts = {}
        if clone_catalog:
            from app.vocabulary_registry import clone_catalog_to_tenant

            counts = clone_catalog_to_tenant(tenant_id, created_by)
        row = _tenant_row(tenant_id)

    logger.info(
        "[TENANT] created %s (%s) plan=%s catalogue=%s",
        tenant_id, display, plan["plan_code"], counts or "skipped",
    )
    return {**(row or {"tenant_id": tenant_id}), "catalog": counts}


def _open_subscription(
    tenant_id: str,
    plan_code: str,
    *,
    changed_by: Optional[str] = None,
    note: str = "",
) -> None:
    """Đóng dòng đăng ký đang mở (nếu có) rồi mở dòng mới.

    Hai câu, cùng một khối, theo đúng thứ tự đó: chỉ mục duy nhất một phần
    `uq_tenant_subscriptions_open` chỉ cho phép một dòng `ended_at IS NULL`
    cho mỗi tenant, nên mở trước đóng sau sẽ vi phạm ràng buộc và cả hai cùng
    bị huỷ. Trật tự này khiến ràng buộc trở thành thứ bảo vệ chứ không phải
    thứ cản đường.
    """
    import uuid as _uuid

    from app.storage.metadata_db import _execute

    _execute(
        "UPDATE tenant_subscriptions SET ended_at = NOW(), status = 'superseded' "
        "WHERE tenant_id = %s AND ended_at IS NULL",
        (tenant_id,),
    )
    _execute(
        "INSERT INTO tenant_subscriptions"
        "(subscription_id, tenant_id, plan_code, status, changed_by, note) "
        "VALUES(%s, %s, %s, 'active', %s, %s)",
        (
            str(_uuid.uuid4()), tenant_id, plan_code,
            str(changed_by) if changed_by else None, note,
        ),
    )


def change_plan(
    tenant_id: str,
    plan_code: str,
    *,
    changed_by: Optional[str] = None,
    note: str = "",
) -> Dict[str, Any]:
    """Đổi gói của một tenant và ghi lại chuỗi thay đổi.

    KHÔNG kiểm mức dùng hiện tại có vừa gói mới hay không, và đó là chủ ý: hạ
    gói một tenant đang có 900 mẫu xuống trần 500 là một quyết định hợp lệ của
    người vận hành (khách ngừng trả tiền). Kết quả đúng là họ giữ nguyên dữ
    liệu đã có và không thêm được nữa, chứ không phải hệ thống từ chối thao
    tác hạ gói. Cổng hạn mức ở `plans.check_quota` xử lý phần còn lại vì nó so
    `used + adding > limit`, nên 900 > 500 tự khoá đường ghi.
    """
    tenant_id = _require_tenant_id(tenant_id)
    get_tenant(tenant_id)
    plan = _resolve_plan(plan_code)

    from app.plans import _clear_caches
    from app.storage.metadata_db import _execute

    with system_scope("tenant admin: change the plan of a tenant"):
        _execute(
            "UPDATE tenants SET plan_code = %s WHERE tenant_id = %s",
            (plan["plan_code"], tenant_id),
        )
        _open_subscription(
            tenant_id, plan["plan_code"], changed_by=changed_by,
            note=note or "Đổi gói qua API quản trị.",
        )
    _clear_caches()
    logger.info("[TENANT] plan %s -> %s", tenant_id, plan["plan_code"])
    return get_tenant(tenant_id)


def set_billing_status(
    tenant_id: str,
    status: str,
    *,
    reason: str = "",
) -> Dict[str, Any]:
    """Treo hoặc mở lại một tenant.

    Tenant gốc không treo được, cùng lý do với `is_active` ở `update_tenant`:
    treo nó là tự khoá mình ra khỏi chính API vừa dùng để treo.
    """
    valid = ("trialing", "active", "past_due", "suspended", "cancelled")
    status = (status or "").strip().lower()
    if status not in valid:
        raise TenantError(f"trạng thái phải là một trong {', '.join(valid)}", 422)

    tenant_id = _require_tenant_id(tenant_id)
    get_tenant(tenant_id)
    if tenant_id == DEFAULT_TENANT_ID and status in ("suspended", "cancelled"):
        raise TenantError(
            f"tenant gốc {DEFAULT_TENANT_ID!r} không thể bị treo", status_code=409
        )

    from app.storage.metadata_db import _execute

    suspended = status in ("suspended", "cancelled")
    with system_scope("tenant admin: change the billing status of a tenant"):
        _execute(
            "UPDATE tenants SET billing_status = %s, "
            "suspended_at = CASE WHEN %s THEN NOW() ELSE NULL END, "
            "suspended_reason = CASE WHEN %s THEN %s ELSE NULL END "
            "WHERE tenant_id = %s",
            (status, suspended, suspended, reason.strip() or None, tenant_id),
        )
    logger.info("[TENANT] billing status %s -> %s", tenant_id, status)
    return get_tenant(tenant_id)


def _slugify_tenant(text: str) -> str:
    """Biến một tên tổ chức bất kỳ thành phần đầu hợp lệ của tenant id.

    Bỏ dấu tiếng Việt trước khi lọc: `unicodedata.normalize('NFKD', ...)` tách
    "ườ" thành "u" + dấu tổ hợp, và bước lọc sau đó vứt dấu đi. Không có bước
    này thì "Trường B" thành "tr-ng-b" — vẫn hợp lệ nhưng không ai đọc được.
    """
    import re
    import unicodedata

    stripped = unicodedata.normalize("NFKD", text or "")
    ascii_only = "".join(c for c in stripped if not unicodedata.combining(c))
    # đ/Đ không tách được bằng NFKD; nó là một chữ cái riêng, không phải d + dấu.
    ascii_only = ascii_only.replace("đ", "d").replace("Đ", "D")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    # Chừa chỗ cho "-" + 6 ký tự hậu tố trong giới hạn 63 ký tự của tenant id.
    slug = slug[:50].strip("-")
    # Tenant id phải bắt đầu bằng chữ hoặc số. Một tên toàn ký tự đặc biệt
    # ("!!!") rút lại thành chuỗi rỗng, và chuỗi rỗng thì không tạo id được.
    return slug if slug and slug[0].isalnum() else f"t{slug}" if slug else "tenant"


def create_self_serve_tenant(
    user_id: str,
    *,
    display_name: str,
    plan_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Tạo tenant riêng cho một tài khoản vừa tự đăng ký, và đặt họ làm chủ.

    Thay cho hành vi cũ — thả tài khoản không lời mời vào tenant gốc — nên nó
    phải không bao giờ trả về tenant gốc, kể cả khi mọi thứ khác hỏng. Đó là
    lý do hàm này ném lỗi thay vì rơi về một mặc định.

    Hậu tố ngẫu nhiên chứ không phải bộ đếm: `truong-b-2` cho biết đã có
    `truong-b`, tức là ai cũng dò được danh sách tổ chức trên nền tảng bằng
    cách thử đăng ký. Sáu ký tự hex thì không cho biết gì.
    """
    import secrets

    if not settings.self_serve_signup:
        raise TenantError(
            "Nền tảng đang chỉ nhận thành viên qua lời mời.", status_code=403
        )

    base = _slugify_tenant(display_name)
    plan = _resolve_plan(plan_code or settings.self_serve_plan_code, must_be_self_serve=True)

    last_error: Optional[Exception] = None
    for _ in range(5):
        candidate = f"{base}-{secrets.token_hex(3)}"
        try:
            tenant = create_tenant(
                candidate,
                display_name=display_name.strip() or candidate,
                created_by=str(user_id),
                plan_code=plan["plan_code"],
                is_self_serve=True,
            )
            break
        except TenantError as exc:
            # Chỉ thử lại khi trùng id. Mọi lỗi khác (gói sai, id không hợp lệ)
            # thử lại cũng chỉ ra đúng lỗi đó, chỉ chậm hơn năm lần.
            if exc.status_code != 409:
                raise
            last_error = exc
    else:
        raise TenantError(
            "Không tạo được mã tổ chức duy nhất, vui lòng thử lại.", status_code=503
        ) from last_error

    tenant_id = tenant["tenant_id"]
    set_home_tenant(str(user_id), tenant_id, role="admin")
    # Vai trò phải là admin: đây là người duy nhất trong tổ chức vừa tạo, và
    # `set_home_tenant` dùng `ON CONFLICT DO NOTHING` nên nó sẽ không nâng
    # quyền một dòng thành viên đã có. Ở đây chưa thể có dòng nào, nhưng viết
    # rõ vẫn hơn dựa vào điều đó.
    update_member_role(tenant_id, str(user_id), "admin")

    from app.storage.metadata_db import _execute

    with system_scope("tenant admin: record the owner of a self-serve tenant"):
        _execute(
            "UPDATE tenants SET owner_user_id = %s WHERE tenant_id = %s",
            (str(user_id), tenant_id),
        )

    logger.info("[TENANT] self-serve %s cho tài khoản %s", tenant_id, user_id)
    return get_tenant(tenant_id)


def update_tenant(
    tenant_id: str,
    *,
    display_name: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    tenant_id = _require_tenant_id(tenant_id)
    get_tenant(tenant_id)  # 404 before anything else

    if is_active is False and tenant_id == DEFAULT_TENANT_ID:
        # Deactivating it would lock out every pre-tenant account and every
        # anonymous reader of the public catalogue, with no way back in through
        # the API that just did it.
        raise TenantError(
            f"the bootstrap tenant {DEFAULT_TENANT_ID!r} cannot be deactivated",
            status_code=409,
        )

    sets, params = [], []
    if display_name is not None:
        sets.append("display_name = %s")
        params.append(display_name.strip())
    if is_active is not None:
        sets.append("is_active = %s")
        params.append(bool(is_active))
    if not sets:
        return get_tenant(tenant_id)

    from app.storage.metadata_db import _execute

    params.append(tenant_id)
    with system_scope("tenant admin: update tenant record"):
        _execute(f"UPDATE tenants SET {', '.join(sets)} WHERE tenant_id = %s", tuple(params))
    logger.info("[TENANT] updated %s", tenant_id)
    return get_tenant(tenant_id)


def delete_tenant(tenant_id: str) -> Dict[str, Any]:
    """Soft-delete. A hard DELETE is refused by the database anyway.

    Every tenant-scoped table carries `ON DELETE RESTRICT` against `tenants`, so
    a real DELETE fails once the tenant owns a single row. Marking `deleted_at`
    is the supported operation, and it keeps the data addressable for an export
    or a restore.
    """
    tenant_id = _require_tenant_id(tenant_id)
    if tenant_id == DEFAULT_TENANT_ID:
        raise TenantError(
            f"the bootstrap tenant {DEFAULT_TENANT_ID!r} cannot be deleted",
            status_code=409,
        )
    get_tenant(tenant_id)

    from app.storage.metadata_db import _execute

    with system_scope("tenant admin: soft-delete tenant"):
        _execute(
            "UPDATE tenants SET deleted_at = NOW(), is_active = FALSE "
            "WHERE tenant_id = %s AND deleted_at IS NULL",
            (tenant_id,),
        )
    logger.info("[TENANT] soft-deleted %s", tenant_id)
    return get_tenant(tenant_id, include_deleted=True)


# --------------------------------------------------------------------------- members


def list_members(tenant_id: str) -> List[Dict[str, Any]]:
    from app.storage.metadata_db import _fetch_all

    tenant_id = _require_tenant_id(tenant_id)
    get_tenant(tenant_id)
    with system_scope("tenant admin: list members of a tenant"):
        rows = _fetch_all(
            """
            SELECT m.tenant_id, m.user_id, m.role, m.created_at,
                   u.username, u.email, u.is_active
            FROM tenant_members m
            JOIN users u ON u.id = m.user_id
            WHERE m.tenant_id = %s
            ORDER BY m.role, u.username
            """,
            (tenant_id,),
        )
    return [dict(r) for r in rows]


def _member_row(tenant_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        "SELECT * FROM tenant_members WHERE tenant_id = %s AND user_id = %s",
        (tenant_id, str(user_id)),
    )
    return dict(rows[0]) if rows else None


def _admin_count(tenant_id: str, *, excluding: Optional[str] = None) -> int:
    from app.storage.metadata_db import _fetch_all

    sql = "SELECT COUNT(*) AS n FROM tenant_members WHERE tenant_id = %s AND role = 'admin'"
    params: Tuple[Any, ...] = (tenant_id,)
    if excluding:
        sql += " AND user_id <> %s"
        params = (tenant_id, str(excluding))
    return int(_fetch_all(sql, params)[0]["n"])


def _assert_not_last_admin(tenant_id: str, user_id: str) -> None:
    """A tenant with no admin cannot be administered — not even to add one back.

    Checked on both removal and demotion, because demoting the last admin
    produces exactly the same dead end as removing them.
    """
    if _admin_count(tenant_id, excluding=user_id) == 0 and _member_row(
        tenant_id, user_id
    ) and _member_row(tenant_id, user_id)["role"] == "admin":
        raise TenantError(
            f"user {user_id} is the last admin of {tenant_id!r}; promote another "
            f"member first",
            status_code=409,
        )


def _assert_seat_available(tenant_id: str, user_id: str) -> None:
    """Còn ghế trống trong gói cho MỘT người nữa hay không.

    Bỏ qua khi người đó đã là thành viên: đổi vai trò của một người đang có
    không tiêu thêm ghế nào, và tính nó là tiêu ghế sẽ khiến một tenant đầy
    ghế không sửa nổi vai trò của chính thành viên mình.

    `QuotaExceeded` được dịch sang `TenantError` ở đây để router chỉ phải biết
    một loại lỗi từ module này.
    """
    from app.plans import QuotaExceeded, check_quota

    if _member_row(tenant_id, str(user_id)):
        return
    try:
        check_quota(tenant_id, "seats", adding=1)
    except QuotaExceeded as exc:
        raise TenantError(str(exc), status_code=exc.status_code) from exc


def add_member(
    tenant_id: str, user_id: str, role: Optional[str] = NO_ROLE
) -> Dict[str, Any]:
    """Attach an EXISTING account to a tenant.

    This does not move the user's home tenant. Changing where someone's data
    lands is `set_home_tenant`, kept separate because the two have very
    different consequences: a role change is reversible, a home change means
    every sample they record afterwards belongs somewhere else.

    Mặc định KHÔNG vai (`NO_ROLE`). Gắn một người vào tổ chức và cấp cho họ một
    vai là hai hành động; gộp chúng lại làm hành động thứ hai xảy ra mà không ai
    yêu cầu. Xem chú thích ở `NO_ROLE`.
    """
    from app.storage.metadata_db import _execute, _fetch_all

    tenant_id = _require_tenant_id(tenant_id)
    role = _require_role(role)
    get_tenant(tenant_id)

    with system_scope("tenant admin: add member to a tenant"):
        if not _fetch_all("SELECT 1 FROM users WHERE id = %s", (str(user_id),)):
            raise TenantError(f"user {user_id} not found", status_code=404)
        _assert_seat_available(tenant_id, str(user_id))
        # Ghi thẳng `memberships`, KHÔNG qua view `tenant_members`.
        #
        # View chèn được, nhưng `ON CONFLICT` thì KHÔNG: mệnh đề đó cần một
        # ràng buộc/chỉ mục duy nhất để bám vào, và view không có cái nào.
        # Postgres trả `InvalidColumnReference: there is no unique or exclusion
        # constraint matching the ON CONFLICT specification`.
        #
        # Chỉ mục thật nằm trên bảng nền và nó là chỉ mục TỪNG PHẦN
        # (`uq_memberships_tenant_user ... WHERE scope_level = 'TENANT'`), nên
        # vị từ phải được lặp lại trong `ON CONFLICT` — thiếu nó thì Postgres
        # cũng không suy ra được chỉ mục nào.
        _execute(
            "INSERT INTO memberships(tenant_id, user_id, scope_level, legacy_role, "
            "                        status, joined_at) "
            "VALUES(%s, %s, 'TENANT', %s, 'ACTIVE', NOW()) "
            "ON CONFLICT (tenant_id, user_id) WHERE scope_level = 'TENANT' "
            "DO UPDATE SET legacy_role = EXCLUDED.legacy_role",
            (tenant_id, str(user_id), role),
        )
        row = _member_row(tenant_id, str(user_id))
    logger.info("[TENANT] member %s -> %s as %s", user_id, tenant_id, _role_label(role))
    return row or {}


def update_member_role(
    tenant_id: str, user_id: str, role: Optional[str]
) -> Dict[str, Any]:
    """Đổi vai của một thành viên. `None` = GỠ vai, giữ tư cách thành viên.

    Gỡ vai không phải là gỡ người. Sau lời gọi này họ vẫn ở trong tổ chức, dữ
    liệu của họ vẫn thuộc về tổ chức, và họ vẫn nhận được quyền từ assignment ở
    workspace/project. Muốn đưa họ ra hẳn thì gọi `remove_member`.

    `_assert_not_last_admin` vẫn canh: gỡ vai của người quản trị cuối cùng để
    lại một tenant không ai quản trị được, y hệt như hạ họ xuống editor.
    """
    from app.storage.metadata_db import _execute

    tenant_id = _require_tenant_id(tenant_id)
    role = _require_role(role)
    get_tenant(tenant_id)

    with system_scope("tenant admin: change a member's role"):
        truoc = _member_row(tenant_id, str(user_id))
        if not truoc:
            raise TenantError(f"user {user_id} is not a member of {tenant_id!r}", 404)
        if role != "admin":
            _assert_not_last_admin(tenant_id, str(user_id))
        _execute(
            "UPDATE tenant_members SET role = %s WHERE tenant_id = %s AND user_id = %s",
            (role, tenant_id, str(user_id)),
        )
        row = _member_row(tenant_id, str(user_id))
    logger.info("[TENANT] role %s in %s -> %s", user_id, tenant_id, _role_label(role))
    # `role_cu` đi kèm để chỗ gọi ghi được dấu vết kiểm toán có NGHĨA: "nâng từ
    # viewer lên admin" và "hạ từ admin xuống viewer" là hai câu chuyện khác
    # nhau, mà một dòng chỉ có vai mới thì không phân biệt được. Đọc lại vai cũ
    # ở chỗ gọi là một truy vấn thứ hai chạy SAU khi giá trị đã bị ghi đè.
    return {**(row or {}), "role_cu": (truoc or {}).get("role")}


def remove_member(tenant_id: str, user_id: str) -> None:
    from app.storage.metadata_db import _execute, _fetch_all

    tenant_id = _require_tenant_id(tenant_id)
    get_tenant(tenant_id)

    with system_scope("tenant admin: remove a member from a tenant"):
        if not _member_row(tenant_id, str(user_id)):
            raise TenantError(f"user {user_id} is not a member of {tenant_id!r}", 404)
        _assert_not_last_admin(tenant_id, str(user_id))
        # Removing someone from the tenant their data lands in would leave an
        # account that writes into a tenant it has no role in — a state with no
        # correct behaviour. Move their home first.
        home = _fetch_all("SELECT tenant_id FROM users WHERE id = %s", (str(user_id),))
        if home and (home[0]["tenant_id"] or "") == tenant_id:
            raise TenantError(
                f"{tenant_id!r} is this user's home tenant; move it before removing "
                f"their membership",
                status_code=409,
            )
        _execute(
            "DELETE FROM tenant_members WHERE tenant_id = %s AND user_id = %s",
            (tenant_id, str(user_id)),
        )
    logger.info("[TENANT] removed member %s from %s", user_id, tenant_id)


def set_home_tenant(
    user_id: str, tenant_id: str, *, role: Optional[str] = NO_ROLE
) -> None:
    """Move where this account's future data lands, and make sure it is a member there.

    Both writes or neither: an account whose home tenant has no matching member
    row can read nothing and write into a tenant it is not part of.

    Cái bắt buộc là TƯ CÁCH THÀNH VIÊN, không phải vai — nên mặc định là
    `NO_ROLE`. Chỗ gọi nào cần một vai thì nêu ra: `create_self_serve_tenant`
    nêu `"admin"`, vì người tự tạo tổ chức của mình phải quản trị được nó.
    """
    from app.storage.metadata_db import _execute, _fetch_all

    tenant_id = _require_tenant_id(tenant_id)
    role = _require_role(role)
    get_tenant(tenant_id)

    with system_scope("tenant admin: move a user's home tenant"):
        if not _fetch_all("SELECT 1 FROM users WHERE id = %s", (str(user_id),)):
            raise TenantError(f"user {user_id} not found", status_code=404)
        # Xem chú thích ở `add_member`: `ON CONFLICT` không bám được vào view.
        _execute(
            "INSERT INTO memberships(tenant_id, user_id, scope_level, legacy_role, "
            "                        status, joined_at) "
            "VALUES(%s, %s, 'TENANT', %s, 'ACTIVE', NOW()) "
            "ON CONFLICT (tenant_id, user_id) WHERE scope_level = 'TENANT' DO NOTHING",
            (tenant_id, str(user_id), role),
        )
        _execute("UPDATE users SET tenant_id = %s WHERE id = %s", (tenant_id, str(user_id)))
    logger.info("[TENANT] home tenant of %s -> %s", user_id, tenant_id)


def orphaned_members() -> List[Dict[str, Any]]:
    """Accounts whose home tenant has no matching `tenant_members` row.

    The two facts are written by different code paths, so "they agree" is a
    claim that needs checking rather than assuming. Empty list = consistent.
    """
    from app.storage.metadata_db import _fetch_all

    with system_scope("tenant admin: audit home tenant against membership"):
        rows = _fetch_all(
            """
            SELECT u.id AS user_id, u.username, u.tenant_id
            FROM users u
            LEFT JOIN tenant_members m
                   ON m.user_id = u.id AND m.tenant_id = u.tenant_id
            WHERE m.user_id IS NULL
            ORDER BY u.username
            """
        )
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- invitations


def _invitation_public(row: Dict[str, Any]) -> Dict[str, Any]:
    """An invitation as the API may show it — never including the token digest.

    The digest is not the token, but publishing it would still be a mistake:
    it turns a database-read into an offline target, and it has no use to any
    caller.
    """
    return {
        "invitation_id": str(row["invitation_id"]),
        "tenant_id": row["tenant_id"],
        "email": row["email"],
        "role": row["role"],
        "created_at": row.get("created_at"),
        "expires_at": row.get("expires_at"),
        "accepted_at": row.get("accepted_at"),
        "revoked_at": row.get("revoked_at"),
        "status": invitation_status(row),
    }


def invitation_status(row: Dict[str, Any]) -> str:
    if row.get("revoked_at"):
        return "revoked"
    if row.get("accepted_at"):
        return "accepted"
    expires = row.get("expires_at")
    if expires and expires <= _now():
        return "expired"
    return "pending"


def create_invitation(
    tenant_id: str, email: str, role: Optional[str] = NO_ROLE,
    *, invited_by: Optional[str] = None
) -> Tuple[Dict[str, Any], str]:
    """Mint an invitation. Returns (public row, RAW TOKEN).

    `role=None` mời người ta vào tổ chức mà không kèm vai nào ở tầng tenant —
    mặc định, và xem `NO_ROLE` về lý do. Vai được cấp sau, bằng một hành động
    riêng có dấu vết kiểm toán riêng.

    The raw token is returned exactly once, to exactly one caller, and is never
    stored or logged. Losing it means revoking and re-inviting — which is the
    correct trade: a token the server can re-read is a token an attacker can
    read too.

    Re-inviting an address that already has a live invitation REPLACES it. Two
    valid tokens for one seat means revoking one still leaves a way in, and the
    partial unique index makes the database enforce this rather than trusting
    this function to be the only writer.
    """
    from app.storage.metadata_db import _execute

    tenant_id = _require_tenant_id(tenant_id)
    role = _require_role(role)
    email = _normalize_email(email)
    if "@" not in email:
        raise TenantError("a valid email address is required", status_code=422)

    tenant = get_tenant(tenant_id)
    if not tenant.get("is_active", True):
        raise TenantError(f"tenant {tenant_id!r} is not active", status_code=409)

    token = new_link_token()
    invitation_id = str(uuid.uuid4())
    expires_at = _now() + timedelta(hours=max(1, int(settings.invitation_ttl_hours)))

    with system_scope("tenant admin: invite a person into a tenant"):
        _execute(
            "UPDATE tenant_invitations SET revoked_at = NOW() "
            "WHERE tenant_id = %s AND email = %s "
            "  AND accepted_at IS NULL AND revoked_at IS NULL",
            (tenant_id, email),
        )
        _execute(
            """
            INSERT INTO tenant_invitations(
                invitation_id, tenant_id, email, role, token_hash, invited_by, expires_at
            ) VALUES(%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                invitation_id, tenant_id, email, role,
                hash_link_token(token), invited_by, expires_at,
            ),
        )
        row = _invitation_row_by_id(invitation_id)

    # The address and the tenant are operational facts worth having in the log.
    # The token is not, and never appears in one.
    logger.info("[TENANT] invited %s to %s as %s", email, tenant_id, _role_label(role))
    return _invitation_public(row or {}), token


def _invitation_row_by_id(invitation_id: str) -> Optional[Dict[str, Any]]:
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        "SELECT * FROM tenant_invitations WHERE invitation_id = %s", (str(invitation_id),)
    )
    return dict(rows[0]) if rows else None


def list_invitations(tenant_id: str, *, include_closed: bool = False) -> List[Dict[str, Any]]:
    from app.storage.metadata_db import _fetch_all

    tenant_id = _require_tenant_id(tenant_id)
    get_tenant(tenant_id)
    where = "WHERE tenant_id = %s"
    if not include_closed:
        where += " AND accepted_at IS NULL AND revoked_at IS NULL"
    with system_scope("tenant admin: list invitations for a tenant"):
        rows = _fetch_all(
            f"SELECT * FROM tenant_invitations {where} ORDER BY created_at DESC",
            (tenant_id,),
        )
    return [_invitation_public(dict(r)) for r in rows]


def revoke_invitation(tenant_id: str, invitation_id: str) -> Dict[str, Any]:
    from app.storage.metadata_db import _execute

    tenant_id = _require_tenant_id(tenant_id)
    with system_scope("tenant admin: revoke an invitation"):
        row = _invitation_row_by_id(invitation_id)
        # Scoped by tenant as well as id: a tenant admin must not be able to
        # revoke another tenant's invitation by guessing a UUID.
        if not row or row["tenant_id"] != tenant_id:
            raise TenantError("invitation not found", status_code=404)
        if row.get("accepted_at"):
            raise TenantError("invitation was already accepted", status_code=409)
        _execute(
            "UPDATE tenant_invitations SET revoked_at = NOW() "
            "WHERE invitation_id = %s AND revoked_at IS NULL",
            (str(invitation_id),),
        )
        row = _invitation_row_by_id(invitation_id)
    logger.info("[TENANT] revoked invitation %s", invitation_id)
    return _invitation_public(row or {})


def peek_invitation(token: str) -> Dict[str, Any]:
    """What a registration form may show BEFORE an account exists.

    Deliberately thin: the tenant's display name and the address the invitation
    was issued to, so the form can say "you are joining X". It does not reveal
    who else is a member, and an invalid token gets the same 404 as an expired
    one — an unauthenticated caller must not be able to tell a wrong guess from
    a stale link.
    """
    row = _invitation_by_token(token)
    if not row or invitation_status(row) != "pending":
        raise TenantError("invitation not found or no longer valid", status_code=404)
    tenant = get_tenant(row["tenant_id"])
    return {
        "tenant_id": row["tenant_id"],
        "tenant_display_name": tenant.get("display_name") or row["tenant_id"],
        "email": row["email"],
        "role": row["role"],
        "expires_at": row.get("expires_at"),
    }


def _invitation_by_token(token: str) -> Optional[Dict[str, Any]]:
    from app.storage.metadata_db import _fetch_all

    if not (token or "").strip():
        return None
    with system_scope("tenant admin: resolve an invitation token"):
        rows = _fetch_all(
            "SELECT * FROM tenant_invitations WHERE token_hash = %s",
            (hash_link_token(token),),
        )
    return dict(rows[0]) if rows else None


def consume_invitation(token: str, *, email: str, user_id: str) -> Dict[str, Any]:
    """Accept an invitation on behalf of a just-created account.

    Four separate refusals, each for a different attack:

    * unknown token — a guess, or a link from a deleted tenant
    * expired / revoked / already accepted — replay of an old link
    * email mismatch — a forwarded link. The invitation names a person; letting
      whoever holds the URL join instead turns email delivery into the
      authentication factor, and mail forwarding is not one.
    * inactive tenant — the relationship ended while the link was in flight

    Marking `accepted_at` is conditional on it still being NULL, so two
    simultaneous accepts cannot both win: the second updates zero rows and is
    refused.
    """
    from app.storage.metadata_db import _execute, _fetch_all

    row = _invitation_by_token(token)
    if not row:
        raise TenantError("invitation not found or no longer valid", status_code=404)

    status = invitation_status(row)
    if status != "pending":
        raise TenantError(f"invitation is {status}", status_code=409)

    if _normalize_email(email) != _normalize_email(row["email"]):
        raise TenantError(
            "this invitation was issued to a different email address",
            status_code=403,
        )

    tenant_id = row["tenant_id"]
    tenant = get_tenant(tenant_id)
    if not tenant.get("is_active", True):
        raise TenantError(f"tenant {tenant_id!r} is not active", status_code=409)

    # Ghế được kiểm ở LÚC CHẤP NHẬN, không chỉ lúc gửi lời mời. Một tổ chức có
    # thể gửi năm lời mời khi còn năm ghế rồi hạ gói xuống ba; nếu chỉ kiểm lúc
    # gửi, cả năm người vẫn vào được và tenant vượt trần mà không endpoint nào
    # từng thấy vi phạm.
    _assert_seat_available(tenant_id, str(user_id))

    with system_scope("tenant admin: accept an invitation"):
        _execute(
            "UPDATE tenant_invitations SET accepted_at = NOW(), accepted_by = %s "
            "WHERE invitation_id = %s AND accepted_at IS NULL AND revoked_at IS NULL",
            (str(user_id), str(row["invitation_id"])),
        )
        confirmed = _fetch_all(
            "SELECT accepted_by FROM tenant_invitations WHERE invitation_id = %s",
            (str(row["invitation_id"]),),
        )
        if not confirmed or str(confirmed[0]["accepted_by"] or "") != str(user_id):
            raise TenantError("invitation was accepted by someone else", status_code=409)

        # Xem chú thích ở `add_member`: `ON CONFLICT` không bám được vào view.
        _execute(
            "INSERT INTO memberships(tenant_id, user_id, scope_level, legacy_role, "
            "                        status, joined_at) "
            "VALUES(%s, %s, 'TENANT', %s, 'ACTIVE', NOW()) "
            "ON CONFLICT (tenant_id, user_id) WHERE scope_level = 'TENANT' "
            "DO UPDATE SET legacy_role = EXCLUDED.legacy_role",
            (tenant_id, str(user_id), row["role"]),
        )
        _execute("UPDATE users SET tenant_id = %s WHERE id = %s", (tenant_id, str(user_id)))

    logger.info("[TENANT] %s joined %s as %s via invitation", user_id, tenant_id,
                _role_label(row["role"]))
    return {"tenant_id": tenant_id, "role": row["role"]}
