"""Từ một đối tượng nghiệp vụ tới chuỗi domain Casbin phải hỏi.

Vì sao Casbin không tự làm được việc này
-----------------------------------------
Casbin trả lời đúng một câu: "chủ thể S có quyền P tại domain D không". Nó
không biết một `sample_uid` thuộc project nào, project đó thuộc workspace nào,
workspace đó thuộc tenant nào. Cây phân cấp là dữ liệu, không phải policy.

Nên phải có một chỗ trả lời "đối tượng này ở đâu", và đó là tệp này. Nó là ranh
giới: mọi thứ phía trên nói bằng ngôn ngữ nghiệp vụ (`sample`, `class`,
`training_job`), mọi thứ phía dưới nói bằng domain (`prj:...`, `ten:...`).

Cây cầu tạm và vì sao nó được ghi ra rõ ràng
---------------------------------------------
Hôm nay `samples`, `classes`, `training_jobs` mang `tenant_id` và **không mang**
`project_id`. Cây bốn tầng vừa được dựng nhưng dữ liệu chưa được gắn vào nó.

Nên với các đối tượng đó, resolver trả về **project mặc định của tenant**. Đây
là một xấp xỉ, và nó ĐÚNG hôm nay vì mỗi tenant có đúng một project — backfill
đảm bảo điều đó. Nó sẽ SAI vào ngày project thứ hai ra đời, và ngày đó phải làm
đúng một việc: thêm `project_id` vào các bảng dữ liệu và đọc nó ở đây thay cho
`_default_project`.

Viết ra thay vì im lặng, vì một xấp xỉ không ghi chú sẽ được đọc là một quyết
định. Hàm `_default_project` mang tên như vậy chính để `grep` ra được toàn bộ
những chỗ còn nợ.

Vì sao có cache, và vì sao nó ngắn
-----------------------------------
`_default_project` chạy mỗi lần phân quyền một đối tượng dữ liệu — tức là gần
như mỗi request. Không cache thì đó là một truy vấn thừa trên mọi đường nóng.

Nhưng cache phân quyền là thứ nguy hiểm, nên cái này cố tình tầm thường: nó
chỉ nhớ **hình dạng của cây** (tenant → workspace/project mặc định), không nhớ
quyết định nào và không nhớ ai có quyền gì. Cây đổi khi có người tạo project,
không phải khi có người bị thu quyền — nên TTL 300 giây ở đây không kéo dài
tuổi thọ của một quyền đã bị thu hồi dù chỉ một mili giây.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, NamedTuple, Optional, Tuple

from app.authorization.adapter import (
    DOMAIN_SYSTEM,
    project_domain,
    tenant_domain,
    workspace_domain,
)

logger = logging.getLogger(__name__)

SYSTEM = "SYSTEM"
TENANT = "TENANT"
WORKSPACE = "WORKSPACE"
PROJECT = "PROJECT"

#: Bao lâu thì quên hình dạng cây. Xem docstring module: cache này KHÔNG giữ
#: quyết định phân quyền, nên nó không làm chậm việc thu hồi quyền.
_TREE_CACHE_TTL = 300.0


class Target(NamedTuple):
    """Đối tượng đang bị tác động.

    `kind` là loại nghiệp vụ (`sample`, `tenant`, `project`, `platform`...),
    `id` là định danh của nó, `tenant_id` là gợi ý khi người gọi đã biết —
    tránh một truy vấn, và với `kind='tenant'` thì chính `id` là tenant.
    """

    kind: str
    id: Optional[str] = None
    tenant_id: Optional[str] = None


@dataclass(frozen=True)
class ScopeContext:
    """Đối tượng nằm ở đâu trong cây. `None` = không áp dụng."""

    tenant_id: Optional[str] = None
    workspace_id: Optional[str] = None
    project_id: Optional[str] = None


#: Loại đối tượng thuộc tầng nền tảng: không thuộc tenant nào.
PLATFORM_KINDS = frozenset({"platform", "system", "user", "plan", "legal_document"})

#: Loại đối tượng mà `id` CHÍNH LÀ tenant_id.
TENANT_KINDS = frozenset({"tenant"})

#: Loại đối tượng sống trong dữ liệu của tenant nhưng chưa mang `project_id`.
#: Xem "Cây cầu tạm" trong docstring module. Mỗi mục ở đây là một món nợ.
TENANT_DATA_KINDS: Dict[str, Tuple[str, str]] = {
    # kind -> (bảng, cột khoá chính)
    "sample": ("samples", "sample_uid"),
    "raw_upload": ("raw_uploads", "upload_uid"),
    "class": ("classes", "class_uid"),
    "training_job": ("training_jobs", "job_id"),
    "capture_session": ("capture_sessions", "capture_session_id"),
    "signer": ("signers", "signer_id"),
    "api_key": ("api_keys", "key_id"),
    "webhook_endpoint": ("webhook_endpoints", "endpoint_id"),
}


class _TreeCache:
    """tenant_id → (workspace_id, project_id) mặc định, có hạn dùng."""

    def __init__(self) -> None:
        self._data: Dict[str, Tuple[float, Optional[Tuple[str, str]]]] = {}
        self._lock = threading.Lock()

    def get(self, tenant_id: str):
        with self._lock:
            entry = self._data.get(tenant_id)
        if entry and time.monotonic() - entry[0] < _TREE_CACHE_TTL:
            return entry[1]
        return None

    def put(self, tenant_id: str, value) -> None:
        with self._lock:
            self._data[tenant_id] = (time.monotonic(), value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_tree_cache = _TreeCache()


def invalidate_tree_cache() -> None:
    """Quên hình dạng cây. Gọi khi tạo/xoá workspace hoặc project."""
    _tree_cache.clear()


def _default_project(tenant_id: str) -> Tuple[Optional[str], Optional[str]]:
    """(workspace_id, project_id) mặc định của một tenant.

    NỢ KỸ THUẬT CÓ CHỦ Ý — xem "Cây cầu tạm" ở docstring module. Khi các bảng
    dữ liệu mang `project_id` thật, hàm này biến mất và người gọi đọc cột đó.

    Trả `(None, None)` khi tenant chưa được backfill. Người gọi phải xử lý:
    chuỗi domain sẽ ngắn đi (chỉ `ten:` và `sys`), nên quyền phạm vi PROJECT
    của một tenant chưa backfill chỉ cấp được từ vai tenant admin trở lên. Đó
    là hỏng theo hướng chặt, và nó có thể quan sát được qua log dưới đây.
    """
    cached = _tree_cache.get(tenant_id)
    if cached is not None:
        return cached

    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    # System scope, cùng lý do như `vocabulary_registry.tenant_role`: phạm vi
    # hiện hành của request là tenant NHÀ của người gọi, còn câu hỏi ở đây có
    # thể nói về một tenant khác được nêu trong đường dẫn. Lọc theo phạm vi nhà
    # sẽ luôn cho ra "không tìm thấy". Truy vấn là một phép tra điểm theo khoá
    # người gọi đã biết, không liệt kê được gì.
    with system_scope("authz: hinh dang cay cua tenant duoc neu ten"):
        rows = _fetch_all(
            "SELECT w.workspace_id::text AS workspace_id, p.project_id::text AS project_id "
            "  FROM workspaces w "
            "  JOIN projects p ON p.tenant_id = w.tenant_id "
            "                 AND p.workspace_id = w.workspace_id "
            "                 AND p.is_default AND p.status = 'ACTIVE' "
            "                 AND p.deleted_at IS NULL "
            " WHERE w.tenant_id = %s AND w.is_default AND w.status = 'ACTIVE' "
            "   AND w.deleted_at IS NULL",
            (tenant_id,),
        )

    if not rows:
        logger.warning(
            "[AUTHZ] tenant %s chua co workspace/project mac dinh; quyen pham vi "
            "PROJECT se chi cap duoc tu vai tenant tro len. Chay "
            "`python -m app.cli.backfill_authz --actor <ai do> --apply`.",
            tenant_id,
        )
        _tree_cache.put(tenant_id, (None, None))
        return (None, None)

    value = (rows[0]["workspace_id"], rows[0]["project_id"])
    _tree_cache.put(tenant_id, value)
    return value


def _tenant_of_row(kind: str, target_id: str) -> Optional[str]:
    """Tenant sở hữu một dòng dữ liệu."""
    table, key = TENANT_DATA_KINDS[kind]
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("authz: tim tenant so huu doi tuong duoc neu ten"):
        rows = _fetch_all(
            f"SELECT tenant_id FROM {table} WHERE {key}::text = %s",  # noqa: S608
            (str(target_id),),
        )
    return rows[0]["tenant_id"] if rows else None


def resolve(target: Target) -> ScopeContext:
    """Đối tượng này nằm ở đâu trong cây Tenant→Workspace→Project.

    Không tìm thấy đối tượng → `ScopeContext()` rỗng. Chuỗi domain khi đó chỉ
    còn `sys`, nghĩa là chỉ người vận hành nền tảng qua được. Đó là câu trả lời
    đúng cho "quyền trên một đối tượng không tồn tại": không ai có, trừ người
    có quyền trên mọi thứ.
    """
    kind = target.kind

    if kind in PLATFORM_KINDS:
        return ScopeContext()

    if kind in TENANT_KINDS:
        tenant_id = target.tenant_id or target.id
        if not tenant_id:
            return ScopeContext()
        workspace_id, project_id = _default_project(tenant_id)
        return ScopeContext(tenant_id, workspace_id, project_id)

    if kind == "workspace":
        return _resolve_workspace(target)

    if kind == "project":
        return _resolve_project(target)

    if kind in TENANT_DATA_KINDS:
        tenant_id = target.tenant_id or (
            _tenant_of_row(kind, target.id) if target.id else None
        )
        if not tenant_id:
            return ScopeContext()
        workspace_id, project_id = _default_project(tenant_id)
        return ScopeContext(tenant_id, workspace_id, project_id)

    # Loại chưa biết. KHÔNG đoán là tenant scope — đoán ở đây làm một đối
    # tượng mới thêm sau này được phân quyền lỏng hơn dự định, im lặng.
    logger.warning("[AUTHZ] khong biet resolve loai doi tuong %r; coi nhu pham vi he thong", kind)
    return ScopeContext()


def _resolve_workspace(target: Target) -> ScopeContext:
    if not target.id:
        return ScopeContext(target.tenant_id)
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("authz: tim tenant cua workspace duoc neu ten"):
        rows = _fetch_all(
            "SELECT tenant_id, workspace_id::text AS workspace_id FROM workspaces "
            "WHERE workspace_id::text = %s AND deleted_at IS NULL",
            (str(target.id),),
        )
    if not rows:
        return ScopeContext()
    return ScopeContext(rows[0]["tenant_id"], rows[0]["workspace_id"], None)


def _resolve_project(target: Target) -> ScopeContext:
    if not target.id:
        return ScopeContext(target.tenant_id)
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("authz: tim vi tri cua project duoc neu ten"):
        rows = _fetch_all(
            "SELECT tenant_id, workspace_id::text AS workspace_id, "
            "       project_id::text AS project_id "
            "  FROM projects WHERE project_id::text = %s AND deleted_at IS NULL",
            (str(target.id),),
        )
    if not rows:
        return ScopeContext()
    row = rows[0]
    return ScopeContext(row["tenant_id"], row["workspace_id"], row["project_id"])


def build_domains(context: ScopeContext, applicable_scope: str) -> list[str]:
    """Chuỗi domain phải thử, từ HẸP tới RỘNG.

    Đây là §14 — thống trị phạm vi — được viết ra thành mã, và thứ tự là toàn
    bộ nội dung của nó. Quyền phạm vi PROJECT được hỏi ở `prj:P`, rồi `ws:W`,
    rồi `ten:T`, rồi `sys`: một tenant admin không cần assignment nào ở project
    vẫn xoá được mẫu trong đó.

    Chiều ngược lại KHÔNG có, và đó mới là điều quan trọng: quyền phạm vi
    TENANT chỉ được hỏi ở `ten:T` và `sys`. Một `project_manager` không bao giờ
    chạm được vào `tenant.billing.manage`, dù có được gán role đó ở bao nhiêu
    project đi nữa — mà cũng không gán được, vì trigger dominance đã chặn từ
    trước.

    Mắt xích thiếu (ví dụ tenant chưa backfill nên `project_id` là None) chỉ
    làm chuỗi ngắn lại, không làm nó rộng ra.
    """
    domains: list[str] = []

    if applicable_scope == PROJECT and context.project_id:
        domains.append(project_domain(context.project_id))
    if applicable_scope in (PROJECT, WORKSPACE) and context.workspace_id:
        domains.append(workspace_domain(context.workspace_id))
    if applicable_scope in (PROJECT, WORKSPACE, TENANT) and context.tenant_id:
        domains.append(tenant_domain(context.tenant_id))

    # `sys` luôn ở cuối, cho mọi phạm vi. Người vận hành nền tảng thống trị tất.
    domains.append(DOMAIN_SYSTEM)
    return domains
