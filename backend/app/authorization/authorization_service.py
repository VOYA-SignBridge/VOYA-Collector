"""Một cửa duy nhất cho câu hỏi "người này được làm việc này không".

Vì sao chỉ một cửa
------------------
Trước tệp này, câu trả lời được ghép lại từ `current_user["is_admin"]` ở 12 tệp
và `tenant_role(...) in EDITOR_ROLES` ở vài chỗ khác. Kiểu thất bại của cách đó
không phải là một chỗ sai, mà là **không ai trả lời được câu hỏi tổng thể**:
"những ai xoá được mẫu của người khác" đòi đọc hết router.

Với một cửa, câu hỏi đó thành một truy vấn SQL.

Thứ tự BẮT BUỘC, §16 và §20
----------------------------
    1. Xác thực              (đã xong trước khi tới đây)
    2. Tư cách thành viên còn hiệu lực?   ← đọc từ NGUỒN THẬT, không từ cache
    3. Casbin: có quyền không?            ← DENY thì DỪNG
    4. Quyền này đòi mã hành động không?  ← chỉ chạy khi ĐÃ ALLOW
    5. Thực hiện + audit + outbox

Bước 4 **không bao giờ** biến DENY thành ALLOW. Mã hành động là bằng chứng
"đúng là người này đang ngồi đây", không phải một quyền. Đảo hai bước sẽ tạo ra
một hệ thống mà nhập đúng mã thì làm được mọi thứ — và đó là lỗi thiết kế mà
§16 tồn tại để đặt tên.

Bước 2 đọc từ nguồn thật chứ không từ policy đã nạp, và đó là §20: giữa lúc thu
hồi và lúc mọi tiến trình nạp lại policy có một khoảng. Với thao tác thường,
khoảng đó chấp nhận được. Với `tenant.purge` hay `role.manage` thì không —
người vừa bị đuổi khỏi tổ chức không được xoá dữ liệu của tổ chức đó vì cache
chưa kịp cập nhật.

Hệ CŨ được suy ra, không chép lại
----------------------------------
`_legacy_decision` không có bảng ánh xạ riêng "quyền nào cần role nào". Nó đọc
CHÍNH các role dựng sẵn: `tenant_editor` được định nghĩa là tập quyền tương
đương `tenant_members.role = 'editor'`, nên "hệ cũ có cho phép không" trở thành
"quyền này có trong role dựng sẵn tương ứng không".

Lý do là chuyện sẽ xảy ra nếu làm cách kia. Một bảng ánh xạ thứ hai sẽ trôi ra
khỏi định nghĩa role, và khi nó trôi thì shadow mode bắt đầu báo mismatch cho
những khác biệt do CHÍNH NÓ tạo ra — tiếng ồn che mất tín hiệu thật. Suy ra từ
một nguồn khiến mọi mismatch còn lại nhất định là khác biệt về DỮ LIỆU:
assignment chưa backfill, membership lệch, role bị vô hiệu. Đó đúng là thứ
shadow mode cần tìm.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from app.authorization.adapter import DOMAIN_SYSTEM, subject
from app.authorization.catalog import (
    BUILTIN_ROLES,
    BY_CODE,
    LEGACY_TENANT_ROLE_MAP,
)
from app.authorization.scope_resolver import (
    ScopeContext,
    Target,
    build_domains,
    resolve,
)

logger = logging.getLogger(__name__)

MODE_LEGACY = "legacy"
MODE_SHADOW = "shadow"
MODE_CASBIN = "casbin"

#: Quyền mà §20 gọi là nhạy cảm: luôn xác nhận lại tư cách thành viên và trạng
#: thái assignment từ cơ sở dữ liệu trước khi cho qua, bất kể policy nói gì.
#:
#: Danh sách này KHÔNG phải `risk_level = 'CRITICAL'` — hai thứ trả lời hai câu
#: khác nhau. `risk_level` là để hiển thị và phân loại kiểm toán. Cái này là
#: một quyết định về ĐỘ TƯƠI của dữ liệu, và nó tốn một truy vấn mỗi lần, nên
#: nó ngắn có chủ ý.
ALWAYS_REVALIDATE = frozenset({
    "platform.tenant.purge", "tenant.purge",
    "platform.role.manage", "tenant.role.manage",
    "tenant.billing.manage",
    "platform.user.manage",
    "platform.legal.publish",
    "tenant.apikey.manage",
})

#: MÃ role dựng sẵn → tập quyền của nó. Dựng một lần lúc import.
#:
#: Khoá là `r.code`, cùng thứ mà `LEGACY_TENANT_ROLE_MAP` trỏ tới và cùng thứ mà
#: `seed.py` ghi vào `roles.name`. `r.name` là nhãn hiển thị ("Tenant Editor");
#: khoá theo nó thì mọi lần tra ở `_legacy_decision` là `KeyError`, và một
#: `KeyError` trong shadow mode được ghi nhận thành `kind="error"` chứ không
#: thành một quyết định — tức là shadow mode ngừng so sánh mà vẫn báo bận.
_BUILTIN_PERMISSIONS: dict[str, frozenset[str]] = {
    r.code: frozenset(r.permissions) for r in BUILTIN_ROLES
}


@dataclass(frozen=True)
class Decision:
    """Kết quả phân quyền, kèm đủ thông tin để giải thích nó.

    `reason` và `domains` không phải để trang trí: khi ai đó hỏi "vì sao tôi bị
    403", câu trả lời phải nói được ĐÃ HỎI Ở ĐÂU và không tìm thấy gì. Không có
    chúng, gỡ rối phân quyền là đoán.
    """

    allowed: bool
    permission: str
    reason: str
    domains: tuple[str, ...] = ()
    matched_domain: Optional[str] = None
    requires_passcode: bool = False
    context: ScopeContext = field(default_factory=ScopeContext)

    def __bool__(self) -> bool:
        return self.allowed


class AuthorizationError(PermissionError):
    """403. Mang theo `decision` để router ghi kiểm toán mà không đoán lại."""

    def __init__(self, decision: Decision) -> None:
        super().__init__(
            f"khong du quyen {decision.permission!r}: {decision.reason}"
        )
        self.decision = decision


# ---------------------------------------------------------------------------
# Trợ giúp
# ---------------------------------------------------------------------------

def _mode() -> str:
    from app.config import settings

    return getattr(settings, "authz_mode", MODE_SHADOW)


def _actor_id(actor: Mapping[str, Any]) -> Optional[str]:
    value = actor.get("id") or actor.get("user_id")
    return str(value) if value else None


def _membership_active(actor_id: str, context: ScopeContext) -> bool:
    """Người này còn là thành viên đang hoạt động của tenant không.

    Đọc thẳng cơ sở dữ liệu, không qua policy — xem §20 ở docstring module.

    Không có tenant trong ngữ cảnh (đối tượng thuộc tầng nền tảng) thì không có
    gì để kiểm: quyền SYSTEM không đi qua tư cách thành viên tenant.
    """
    if not context.tenant_id:
        return True

    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("authz: xac nhan tu cach thanh vien con hieu luc"):
        rows = _fetch_all(
            "SELECT 1 FROM tenant_members "
            " WHERE tenant_id = %s AND user_id = %s "
            "   AND status = 'ACTIVE' AND removed_at IS NULL",
            (context.tenant_id, actor_id),
        )
    return bool(rows)


def _casbin_decision(actor_id: str, permission: str,
                     domains: list[str]) -> tuple[bool, Optional[str], Optional[str]]:
    """(allowed, matched_domain, error). Lỗi = không quyết định được."""
    from app.authorization.enforcer import PolicyNotLoaded, get_enforcer

    try:
        enforcer = get_enforcer()
    except PolicyNotLoaded as exc:
        return False, None, str(exc)

    sub = subject(actor_id)
    for domain in domains:
        try:
            if enforcer.enforce(sub, domain, permission):
                return True, domain, None
        except Exception as exc:  # pragma: no cover - lỗi bên trong Casbin
            return False, None, f"{exc.__class__.__name__}: {exc}"
    return False, None, None


def _legacy_decision(actor: Mapping[str, Any], permission: str,
                     context: ScopeContext) -> bool:
    """Hệ CŨ có cho phép không — suy ra từ chính role dựng sẵn.

    Xem docstring module về vì sao suy ra chứ không chép lại.
    """
    if actor.get("is_admin"):
        # `platform_admin` cầm mọi quyền, nên cờ cũ tương đương đúng như vậy.
        return True

    if not context.tenant_id:
        # Quyền tầng nền tảng, mà người này không phải quản trị viên nền tảng.
        return False

    from app.vocabulary_registry import tenant_role

    actor_id = _actor_id(actor)
    legacy = tenant_role(context.tenant_id, actor_id) if actor_id else None
    if not legacy:
        # HAI trạng thái tới đây, và cả hai trả lời giống nhau ở tầng tenant:
        #
        #     không phải thành viên            → không có gì để cấp
        #     là thành viên, `role IS NULL`    → có tư cách, chưa có vai
        #
        # Vế thứ hai là trạng thái HỢP LỆ ra đời khi `tenant_viewer` nghỉ hưu,
        # KHÔNG phải dữ liệu hỏng, nên nó KHÔNG được kêu. Người ở vế đó vẫn
        # nhận quyền bình thường qua assignment ở workspace/project — đường đó
        # đi qua Casbin, không qua hàm này, vì hệ CŨ không có khái niệm tương
        # ứng để so sánh.
        #
        # Hệ quả cho shadow mode, và nó đã được cân nhắc: một người không vai
        # mà có assignment ở project sẽ hiện ra dưới dạng `deny_to_allow`. Đó
        # là mismatch THẬT — chuyển sang enforcement mở rộng quyền của họ so
        # với hệ cũ — nhưng nó mở rộng đúng bằng thứ đã được cấp tường minh ở
        # một mức mà hệ cũ không biết diễn đạt. Hôm nay con số đó là 0:
        # `workspace_member_roles` và `project_member_roles` đều rỗng.
        return False

    builtin = LEGACY_TENANT_ROLE_MAP.get(legacy)
    if not builtin:
        # `tenant_members_role_valid` giới hạn cột ở 'admin' | 'editor' | NULL,
        # và NULL đã được xử lý ở trên. Tới đây nghĩa là schema và mã đã lệch
        # nhau — ví dụ một dòng `'viewer'` sót lại vì lượt di trú không chạy.
        # Từ chối, và kêu to.
        logger.error("[AUTHZ] role cu %r khong co trong LEGACY_TENANT_ROLE_MAP", legacy)
        return False

    return permission in _BUILTIN_PERMISSIONS[builtin]


def _record_shadow(actor_id: str, permission: str, legacy: bool, casbin: bool,
                   domains: list[str], error: Optional[str]) -> None:
    """Ghi lại một lần so sánh cũ-mới. Chỉ ghi khi BẤT ĐỒNG.

    Ghi cả lần khớp sẽ tạo ra một dòng log cho mỗi phép phân quyền của mỗi
    request — hàng trăm nghìn dòng mỗi ngày nói "vẫn ổn". Cái đáng đọc là chỗ
    hai bên khác nhau, và nó phải nổi lên chứ không chìm.

    `DENY→ALLOW` (cũ từ chối, Casbin cho qua) là hạng mục CRITICAL: nó nghĩa là
    chuyển sang enforcement sẽ MỞ RỘNG quyền của ai đó. `ALLOW→DENY` chỉ làm
    hẹp lại — vẫn phải sửa, nhưng nó hỏng theo hướng an toàn.
    """
    if legacy == casbin and not error:
        return

    if error:
        logger.error(
            "[AUTHZ-SHADOW][ERROR] khong danh gia duoc Casbin cho %s (user=%s): %s",
            permission, actor_id, error,
        )
        kind = "error"
    elif casbin and not legacy:
        logger.error(
            "[AUTHZ-SHADOW][DENY->ALLOW] %s user=%s domains=%s — chuyen sang "
            "enforcement se MO RONG quyen. Dieu tra truoc khi doi AUTHZ_MODE.",
            permission, actor_id, ",".join(domains),
        )
        kind = "deny_to_allow"
    else:
        logger.warning(
            "[AUTHZ-SHADOW][ALLOW->DENY] %s user=%s domains=%s — thieu "
            "assignment hoac membership trong RBAC moi?",
            permission, actor_id, ",".join(domains),
        )
        kind = "allow_to_deny"

    # Số đo để dựng cảnh báo Grafana: "mismatch DENY->ALLOW > 0" là điều kiện
    # dừng cho việc chuyển chế độ.
    #
    # Cả phép import lẫn phép đo đều nằm trong `try`, và không phải vì cẩn thận
    # quá mức: `app.metrics` kéo theo `prometheus_client` và `app.monitoring`,
    # vốn không có mặt ở mọi lối vào (CLI, một số test). Một `ImportError` ở
    # đây sẽ làm hỏng chính phép phân quyền — tức là một chỉ số quan sát làm
    # sập thứ nó đang quan sát.
    try:
        from app import metrics

        metrics.authz_shadow_mismatch.labels(kind=kind, permission=permission).inc()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# API công khai
# ---------------------------------------------------------------------------

def authorize(actor: Mapping[str, Any], permission: str,
              target: Target | None = None) -> Decision:
    """Chủ thể `actor` có được thực hiện `permission` trên `target` không.

    Không ném lỗi — trả về `Decision`. Router muốn 403 thì gọi `require()`.
    """
    meta = BY_CODE.get(permission)
    if meta is None:
        # Mã quyền không có trong danh mục. Từ chối, và ghi ERROR: đây gần như
        # chắc chắn là lỗi chính tả ở nơi gọi, và nó làm endpoint đó từ chối
        # TẤT CẢ mọi người — kể cả quản trị viên nền tảng.
        logger.error("[AUTHZ] quyen %r khong co trong danh muc; tu choi", permission)
        return Decision(False, permission, "quyen khong ton tai trong danh muc")

    actor_id = _actor_id(actor)
    if not actor_id:
        return Decision(False, permission, "khong xac dinh duoc chu the")

    context = resolve(target) if target else ScopeContext()
    domains = build_domains(context, meta.scope)

    # §20. Tư cách thành viên được đọc từ NGUỒN THẬT, trước Casbin: policy đang
    # nạp có thể còn mang một assignment vừa bị thu hồi.
    #
    # Nhưng nó CẮT BỚT chuỗi domain chứ không từ chối thẳng, và khác biệt đó
    # quan trọng. Mất tư cách thành viên tenant làm mất thẩm quyền TRONG tenant
    # đó; nó không đụng gì tới thẩm quyền ở tầng nền tảng. Từ chối thẳng sẽ
    # khiến người vận hành nền tảng — vốn thường KHÔNG phải thành viên của
    # tenant họ đang xử lý — bị 403 ở mọi thao tác quản trị, kể cả trong shadow
    # mode, nơi lẽ ra không kết quả nào được đổi.
    #
    # Giữ lại `sys` là câu trả lời đúng: `platform_admin` vẫn qua, mọi thẩm
    # quyền dựa trên tenant thì không.
    if context.tenant_id and not _membership_active(actor_id, context):
        domains = [DOMAIN_SYSTEM]

    mode = _mode()

    if mode == MODE_LEGACY:
        return _finish(actor, Decision(
            _legacy_decision(actor, permission, context), permission,
            "he cu (is_admin / tenant_members.role)",
            tuple(domains), None, meta.requires_passcode, context))

    casbin_allowed, matched, error = _casbin_decision(actor_id, permission, domains)

    if mode == MODE_SHADOW:
        # `_legacy_decision` chỉ chạy ở hai chế độ CẦN nó. Ở `casbin` nó là một
        # lượt đọc `tenant_members` thừa trên MỌI phép phân quyền của MỌI
        # request — tức là đúng thứ mà việc chuyển sang Casbin lẽ ra loại bỏ.
        legacy_allowed = _legacy_decision(actor, permission, context)
        _record_shadow(actor_id, permission, legacy_allowed, casbin_allowed, domains, error)
        # Hệ CŨ quyết định. Đó là toàn bộ ý nghĩa của shadow mode, và đảo lại
        # dù chỉ cho một quyền sẽ biến nó thành enforcement từng phần — không
        # ai lường được, không ai kiểm được.
        return _finish(actor, Decision(
            legacy_allowed, permission,
            "he cu quyet dinh (shadow: Casbin " + ("dong y" if casbin_allowed == legacy_allowed
                                                   else "BAT DONG") + ")",
            tuple(domains), matched, meta.requires_passcode, context))

    # MODE_CASBIN
    if error:
        # §40: không quyết định được thì từ chối. KHÔNG rơi về hệ cũ — im lặng
        # rơi về là cách một sự cố nạp policy biến thành một lần nới quyền mà
        # không ai thấy.
        return _finish(actor, Decision(
            False, permission, f"phan quyen chua san sang: {error}",
            tuple(domains), None, meta.requires_passcode, context))

    return _finish(actor, Decision(
        casbin_allowed, permission,
        f"khop tai {matched}" if matched else "khong role nao cap quyen nay",
        tuple(domains), matched, meta.requires_passcode, context))


def _finish(actor: Mapping[str, Any], decision: Decision) -> Decision:
    if not decision.allowed:
        _audit_denial(actor, decision)
    return decision


def _audit_denial(actor: Mapping[str, Any], decision: Decision) -> None:
    """Ghi kiểm toán MỌI lần từ chối.

    Chỉ ghi lần từ chối, không ghi lần cho qua: một hành động được cho qua sẽ
    tự sinh dòng kiểm toán của chính nó (`sample.delete` ghi "đã xoá mẫu X"),
    còn một lần từ chối thì không để lại dấu vết nào khác. Và chuỗi từ chối lặp
    lại là tín hiệu duy nhất phân biệt "cấu hình sai" với "có người đang dò".
    """
    from app import audit

    audit.record(
        "authz.denied",
        actor=actor,
        target_type="permission",
        target_id=decision.permission,
        detail={
            "reason": decision.reason,
            "domains": list(decision.domains),
            "tenant_id": decision.context.tenant_id,
        },
    )


def require(actor: Mapping[str, Any], permission: str,
            target: Target | None = None) -> Decision:
    """Như `authorize`, nhưng ném `AuthorizationError` khi bị từ chối."""
    decision = authorize(actor, permission, target)
    if not decision.allowed:
        raise AuthorizationError(decision)
    return decision


def needs_revalidation(permission: str) -> bool:
    """Quyền này có thuộc nhóm luôn phải xác nhận lại từ nguồn thật không."""
    return permission in ALWAYS_REVALIDATE
