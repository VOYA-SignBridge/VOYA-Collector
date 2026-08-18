"""Workspace và Project: bề mặt vận hành cho hai tầng phạm vi dưới tenant.

Vì sao tệp này ra đời muộn hơn lược đồ
--------------------------------------
Hai bảng `workspaces` và `projects` đã tồn tại từ bản v5 của mô hình phân quyền,
cùng với `memberships.scope_level` và 13 vai dựng sẵn trải trên bốn miền. Nhưng
cho tới trước tệp này, **không router nào tạo được chúng**: đối chiếu
`/openapi.json` cho 0 đường dẫn chứa `workspace` hoặc `project`.

Hệ quả là một câu phải nói đi nói lại trong tài liệu: *"kiến trúc hỗ trợ nhiều
cấp; cưỡng chế chứng minh được ở cấp hệ thống và cấp tổ chức"* — hai tầng dưới là
**cấu trúc dữ liệu, chưa phải bề mặt vận hành**, nên không có gì để kiểm chứng
cách ly ở đó từ bên ngoài.

Tệp này đóng đúng khoảng trống ấy, và không hơn.

Phạm vi có ý thức — đọc trước khi mở rộng
------------------------------------------
Cái này CÓ:

* tạo / đổi tên / lưu trữ workspace và project trong một tenant
* liệt kê thành viên theo từng phạm vi, gán và thu vai ở cấp workspace/project
* mọi thao tác chạy **trong tenant scope**, để RLS là thứ cưỡng chế chứ không
  phải điều kiện lọc viết tay

Cái này KHÔNG có, và không được ngầm hiểu là có:

* **Dữ liệu vẫn chưa mang `project_id`.** `samples`, `classes`, `training_jobs`
  mang `tenant_id` và không mang `project_id`. `scope_resolver._default_project`
  vẫn là cây cầu tạm. Tạo được project **không** làm dữ liệu tự phân về project.
* **`AUTHZ_MODE` vẫn là `shadow`.** Gán một vai cấp workspace ghi đúng dữ liệu và
  Casbin đọc được nó, nhưng bên **quyết định** lúc chạy vẫn là hệ cũ hai phạm vi.
  Vai cấp workspace vì thế hiện chưa đổi được kết quả của một phép kiểm quyền.

Hai điều trên phải nói ra ở đây, vì một API tạo được workspace rất dễ bị đọc
thành "phân quyền bốn cấp đã chạy".

Membership là thứ mang phạm vi, không phải role_assignment
-----------------------------------------------------------
Mô hình v5 tách hai sự thật: *anh thuộc về đâu* (`memberships`) và *anh làm được
gì ở đó* (`role_assignments`). Một lần gán vai cấp workspace vì thế cần HAI dòng:

1. một `memberships` mang `scope_level='WORKSPACE'` + `workspace_id`
2. một `role_assignments` trỏ tới membership đó qua khoá ngoại ghép
   `(membership_id, user_id)`

Khoá ghép ở bước 2 là thứ bảo đảm lần gán vai và tư cách thành viên thuộc về
**cùng một người**. Với khoá đơn, một bản ghi gán vai cho người A dựa trên tư
cách của người B là hợp lệ về mặt cơ sở dữ liệu.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.tenancy import normalize_tenant_id

logger = logging.getLogger(__name__)

#: Trạng thái vòng đời dùng chung cho workspace và project. Trùng với
#: `authz_schema.CONTAINER_STATUSES`; nhập lại ở đây sẽ lệch vào ngày một trong
#: hai đổi, nên lấy thẳng từ nguồn.
from app.storage.authz_schema import CONTAINER_STATUSES  # noqa: E402

#: Vai gán được ở cấp workspace và ở cấp project. Lấy từ danh mục vai dựng sẵn
#: thay vì gõ tay: `roles.scope_level` đã nói vai nào áp ở cấp nào, và một danh
#: sách thứ hai trong mã là một danh sách sẽ lệch.
_ROLE_SQL = """
    SELECT role_id, role_code, role_name, description, scope_level
    FROM roles
    WHERE scope_level = %s AND is_active AND (tenant_id IS NULL OR tenant_id = %s)
    ORDER BY role_code
"""

_MAX_NAME = 80
_MAX_DESC = 500


class WorkspaceError(Exception):
    """Lỗi nghiệp vụ có mã HTTP đi kèm.

    Cùng khuôn với `tenant_admin.TenantError`: router chỉ dịch sang
    `HTTPException`, không tự quyết định mã.
    """

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


# --------------------------------------------------------------------------- helpers


def _clean_name(value: Any, *, field: str = "tên") -> str:
    text = str(value or "").strip()
    if not text:
        raise WorkspaceError(f"{field} không được để trống", status_code=422)
    if len(text) > _MAX_NAME:
        raise WorkspaceError(f"{field} không quá {_MAX_NAME} ký tự", status_code=422)
    return text


def _clean_desc(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) > _MAX_DESC:
        raise WorkspaceError(f"mô tả không quá {_MAX_DESC} ký tự", status_code=422)
    return text


def _require_status(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text not in CONTAINER_STATUSES:
        raise WorkspaceError(
            f"trạng thái phải là một trong {', '.join(CONTAINER_STATUSES)}",
            status_code=422,
        )
    return text


def _uuid_or_400(value: Any, *, field: str) -> str:
    """Ép một chuỗi thành UUID hợp lệ trước khi nó chạm SQL.

    Không phải để chống tiêm — tham số đã tách khỏi câu lệnh. Lý do thật: một
    chuỗi không phải UUID làm PostgreSQL ném `invalid input syntax`, và lỗi đó
    nổi lên thành 500. Người gọi gõ sai một mã thì đáng nhận 400, không phải
    một lỗi máy chủ.
    """
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise WorkspaceError(f"{field} không hợp lệ", status_code=400) from exc


# --------------------------------------------------------------------------- workspaces


def list_workspaces(tenant_id: str, *, include_archived: bool = False) -> List[Dict[str, Any]]:
    """Mọi workspace của một tenant, kèm số project và số thành viên.

    Đếm bằng hai truy vấn con gộp sẵn thay vì một truy vấn cho mỗi hàng: đây là
    trang danh sách, và bản N+1 chậm dần đúng theo mức tổ chức đó dùng nhiều.
    """
    from app.storage.metadata_db import _fetch_all

    tid = normalize_tenant_id(tenant_id)
    where = "" if include_archived else "AND w.status = 'ACTIVE'"
    rows = _fetch_all(
        f"""
        SELECT w.workspace_id, w.name, w.description, w.status, w.is_default,
               w.created_at, w.archived_at,
               COALESCE(p.n, 0) AS project_count,
               COALESCE(m.n, 0) AS member_count
        FROM workspaces w
        LEFT JOIN (
            SELECT workspace_id, COUNT(*) AS n FROM projects
            WHERE deleted_at IS NULL AND status <> 'DELETED'
            GROUP BY workspace_id
        ) p ON p.workspace_id = w.workspace_id
        LEFT JOIN (
            SELECT workspace_id, COUNT(*) AS n FROM memberships
            WHERE scope_level = 'WORKSPACE' AND status = 'ACTIVE'
            GROUP BY workspace_id
        ) m ON m.workspace_id = w.workspace_id
        WHERE w.tenant_id = %s AND w.deleted_at IS NULL {where}
        ORDER BY w.is_default DESC, w.created_at
        """,
        (tid,),
    )
    return [dict(r) for r in rows]


def get_workspace(tenant_id: str, workspace_id: str) -> Dict[str, Any]:
    from app.storage.metadata_db import _fetch_all

    tid = normalize_tenant_id(tenant_id)
    wid = _uuid_or_400(workspace_id, field="mã workspace")
    rows = _fetch_all(
        "SELECT * FROM workspaces WHERE tenant_id = %s AND workspace_id = %s "
        "AND deleted_at IS NULL",
        (tid, wid),
    )
    if not rows:
        raise WorkspaceError("không tìm thấy workspace", status_code=404)
    return dict(rows[0])


def create_workspace(
    tenant_id: str,
    *,
    name: str,
    description: str = "",
) -> Dict[str, Any]:
    """Tạo một workspace mới trong tenant đang mở.

    Tên duy nhất trong một tenant — cưỡng chế bằng chỉ mục
    `uq_workspaces_tenant_name ... WHERE deleted_at IS NULL`, không phải bằng một
    lượt `SELECT` kiểm trước. Kiểm trước rồi ghi là một cuộc đua: hai yêu cầu
    cùng lúc đều thấy tên còn trống.
    """
    from app.storage.metadata_db import _execute, _fetch_all

    tid = normalize_tenant_id(tenant_id)
    label = _clean_name(name, field="tên workspace")
    desc = _clean_desc(description)
    wid = str(uuid.uuid4())

    try:
        _execute(
            """
            INSERT INTO workspaces (workspace_id, tenant_id, name, description,
                                    status, is_default)
            VALUES (%s, %s, %s, %s, 'ACTIVE', FALSE)
            """,
            (wid, tid, label, desc),
        )
    except Exception as exc:  # noqa: BLE001 - phân loại ngay dưới
        if "uq_workspaces_tenant_name" in str(exc):
            raise WorkspaceError(
                f"đã có workspace tên {label!r} trong tổ chức này", status_code=409
            ) from exc
        raise

    logger.info("[WORKSPACE][CREATE] tenant=%s workspace=%s name=%s", tid, wid, label)
    rows = _fetch_all(
        "SELECT * FROM workspaces WHERE tenant_id = %s AND workspace_id = %s", (tid, wid)
    )
    return dict(rows[0])


def update_workspace(
    tenant_id: str,
    workspace_id: str,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """Đổi tên, mô tả hoặc trạng thái.

    Workspace mặc định **không lưu trữ được**: nó là chỗ `scope_resolver` rơi về
    khi một đối tượng dữ liệu chưa mang `project_id`. Lưu trữ nó sẽ làm cây phạm
    vi mất gốc trong khi dữ liệu vẫn trỏ tới đó — hỏng ở chỗ không ai nhìn.
    """
    from app.storage.metadata_db import _execute

    current = get_workspace(tenant_id, workspace_id)
    tid = normalize_tenant_id(tenant_id)
    wid = str(current["workspace_id"])

    sets: List[str] = []
    params: List[Any] = []

    if name is not None:
        sets.append("name = %s")
        params.append(_clean_name(name, field="tên workspace"))
    if description is not None:
        sets.append("description = %s")
        params.append(_clean_desc(description))
    if status is not None:
        new_status = _require_status(status)
        if new_status != "ACTIVE" and current.get("is_default"):
            raise WorkspaceError(
                "workspace mặc định không lưu trữ được — dữ liệu chưa mang project_id "
                "vẫn đang rơi về đây",
                status_code=409,
            )
        sets.append("status = %s")
        params.append(new_status)
        sets.append("archived_at = CASE WHEN %s = 'ACTIVE' THEN NULL ELSE NOW() END")
        params.append(new_status)

    if not sets:
        return current

    params.extend([tid, wid])
    try:
        _execute(
            f"UPDATE workspaces SET {', '.join(sets)} "
            "WHERE tenant_id = %s AND workspace_id = %s",
            tuple(params),
        )
    except Exception as exc:  # noqa: BLE001
        if "uq_workspaces_tenant_name" in str(exc):
            raise WorkspaceError("đã có workspace trùng tên trong tổ chức này",
                                 status_code=409) from exc
        raise

    logger.info("[WORKSPACE][UPDATE] tenant=%s workspace=%s fields=%s",
                tid, wid, len(sets))
    return get_workspace(tid, wid)


# --------------------------------------------------------------------------- projects


def list_projects(
    tenant_id: str,
    workspace_id: str,
    *,
    include_archived: bool = False,
) -> List[Dict[str, Any]]:
    from app.storage.metadata_db import _fetch_all

    workspace = get_workspace(tenant_id, workspace_id)
    tid = normalize_tenant_id(tenant_id)
    where = "" if include_archived else "AND p.status = 'ACTIVE'"
    rows = _fetch_all(
        f"""
        SELECT p.project_id, p.workspace_id, p.name, p.description, p.status,
               p.is_default, p.created_at, p.archived_at,
               COALESCE(m.n, 0) AS member_count
        FROM projects p
        LEFT JOIN (
            SELECT project_id, COUNT(*) AS n FROM memberships
            WHERE scope_level = 'PROJECT' AND status = 'ACTIVE'
            GROUP BY project_id
        ) m ON m.project_id = p.project_id
        WHERE p.tenant_id = %s AND p.workspace_id = %s AND p.deleted_at IS NULL {where}
        ORDER BY p.is_default DESC, p.created_at
        """,
        (tid, str(workspace["workspace_id"])),
    )
    return [dict(r) for r in rows]


def create_project(
    tenant_id: str,
    workspace_id: str,
    *,
    name: str,
    description: str = "",
) -> Dict[str, Any]:
    """Tạo project trong một workspace.

    Không nhận project của một workspace đã lưu trữ: một nhánh cây đã đóng mà vẫn
    mọc thêm lá là trạng thái không ai dọn được về sau.
    """
    from app.storage.metadata_db import _execute, _fetch_all

    workspace = get_workspace(tenant_id, workspace_id)
    if str(workspace.get("status")) != "ACTIVE":
        raise WorkspaceError("workspace đã lưu trữ, không tạo project mới được",
                             status_code=409)

    tid = normalize_tenant_id(tenant_id)
    wid = str(workspace["workspace_id"])
    label = _clean_name(name, field="tên project")
    desc = _clean_desc(description)
    pid = str(uuid.uuid4())

    try:
        _execute(
            """
            INSERT INTO projects (project_id, tenant_id, workspace_id, name,
                                  description, status, is_default)
            VALUES (%s, %s, %s, %s, %s, 'ACTIVE', FALSE)
            """,
            (pid, tid, wid, label, desc),
        )
    except Exception as exc:  # noqa: BLE001
        if "uq_projects_workspace_name" in str(exc):
            raise WorkspaceError(
                f"đã có project tên {label!r} trong workspace này", status_code=409
            ) from exc
        raise

    logger.info("[PROJECT][CREATE] tenant=%s workspace=%s project=%s name=%s",
                tid, wid, pid, label)
    rows = _fetch_all(
        "SELECT * FROM projects WHERE tenant_id = %s AND project_id = %s", (tid, pid)
    )
    return dict(rows[0])


def update_project(
    tenant_id: str,
    workspace_id: str,
    project_id: str,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    from app.storage.metadata_db import _execute, _fetch_all

    workspace = get_workspace(tenant_id, workspace_id)
    tid = normalize_tenant_id(tenant_id)
    wid = str(workspace["workspace_id"])
    pid = _uuid_or_400(project_id, field="mã project")

    rows = _fetch_all(
        "SELECT * FROM projects WHERE tenant_id = %s AND workspace_id = %s "
        "AND project_id = %s AND deleted_at IS NULL",
        (tid, wid, pid),
    )
    if not rows:
        raise WorkspaceError("không tìm thấy project", status_code=404)
    current = dict(rows[0])

    sets: List[str] = []
    params: List[Any] = []
    if name is not None:
        sets.append("name = %s")
        params.append(_clean_name(name, field="tên project"))
    if description is not None:
        sets.append("description = %s")
        params.append(_clean_desc(description))
    if status is not None:
        new_status = _require_status(status)
        if new_status != "ACTIVE" and current.get("is_default"):
            raise WorkspaceError(
                "project mặc định không lưu trữ được — xem ghi chú ở workspace mặc định",
                status_code=409,
            )
        sets.append("status = %s")
        params.append(new_status)
        sets.append("archived_at = CASE WHEN %s = 'ACTIVE' THEN NULL ELSE NOW() END")
        params.append(new_status)

    if not sets:
        return current

    params.extend([tid, pid])
    _execute(
        f"UPDATE projects SET {', '.join(sets)} WHERE tenant_id = %s AND project_id = %s",
        tuple(params),
    )
    logger.info("[PROJECT][UPDATE] tenant=%s project=%s fields=%s", tid, pid, len(sets))

    rows = _fetch_all(
        "SELECT * FROM projects WHERE tenant_id = %s AND project_id = %s", (tid, pid)
    )
    return dict(rows[0])


# --------------------------------------------------------------------------- roles


def list_assignable_roles(tenant_id: str, scope_level: str) -> List[Dict[str, Any]]:
    """Vai gán được ở một cấp phạm vi.

    Đọc từ `roles.scope_level` chứ không từ một danh sách trong mã. Danh mục vai
    đã nói vai nào áp ở cấp nào; nhân bản thông tin đó ra đây là tạo một nguồn
    sự thật thứ hai sẽ lệch.
    """
    from app.storage.metadata_db import _fetch_all

    level = str(scope_level or "").strip().upper()
    if level not in {"WORKSPACE", "PROJECT"}:
        raise WorkspaceError("cấp phạm vi phải là WORKSPACE hoặc PROJECT", status_code=422)
    rows = _fetch_all(_ROLE_SQL, (level, normalize_tenant_id(tenant_id)))
    return [dict(r) for r in rows]


def list_scope_members(
    tenant_id: str,
    *,
    workspace_id: str,
    project_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Ai đang có vai ở một workspace hoặc một project.

    Trả về **một dòng cho mỗi lần gán vai còn hiệu lực**, không gộp theo người:
    một người có thể mang hai vai ở cùng một phạm vi, và gộp lại sẽ giấu mất một
    trong hai khi thu hồi.
    """
    from app.storage.metadata_db import _fetch_all

    tid = normalize_tenant_id(tenant_id)
    wid = str(get_workspace(tid, workspace_id)["workspace_id"])

    if project_id:
        pid = _uuid_or_400(project_id, field="mã project")
        scope_sql = "m.scope_level = 'PROJECT' AND m.project_id = %s"
        params: tuple = (tid, wid, pid)
    else:
        scope_sql = "m.scope_level = 'WORKSPACE' AND m.project_id IS NULL"
        params = (tid, wid)

    rows = _fetch_all(
        f"""
        SELECT ra.assignment_id, ra.user_id, u.username, u.email,
               r.role_code, r.role_name, r.scope_level,
               m.membership_id, m.workspace_id, m.project_id, ra.assigned_at
        FROM memberships m
        JOIN role_assignments ra
          ON ra.membership_id = m.membership_id AND ra.user_id = m.user_id
        JOIN roles r ON r.role_id = ra.role_id
        JOIN users u ON u.id = m.user_id
        WHERE m.tenant_id = %s AND m.workspace_id = %s AND {scope_sql}
          AND m.status = 'ACTIVE' AND ra.revoked_at IS NULL
        ORDER BY u.username, r.role_code
        """,
        params,
    )
    return [dict(r) for r in rows]


def assign_scope_role(
    tenant_id: str,
    *,
    workspace_id: str,
    project_id: Optional[str],
    user_id: str,
    role_code: str,
    actor_user_id: str,
) -> Dict[str, Any]:
    """Gán một vai cấp workspace hoặc project cho một người.

    Ba bước, và bước đầu là bước dễ bỏ quên nhất:

    1. **Người đó phải đã là thành viên của tenant.** Không có bước này, gán vai
       cấp workspace trở thành một đường đưa người lạ vào tổ chức mà không đi qua
       lời mời — đúng lối vòng mà BR-1.4 tồn tại để bịt.
    2. Dựng (hoặc dùng lại) một `memberships` ở đúng cấp phạm vi.
    3. Ghi `role_assignments` trỏ tới membership đó.
    """
    from app.storage.metadata_db import _execute, _fetch_all

    tid = normalize_tenant_id(tenant_id)
    wid = str(get_workspace(tid, workspace_id)["workspace_id"])
    uid = _uuid_or_400(user_id, field="mã tài khoản")
    pid = _uuid_or_400(project_id, field="mã project") if project_id else None
    level = "PROJECT" if pid else "WORKSPACE"

    # (1) tư cách thành viên tenant — điều kiện tiên quyết, không phải hệ quả
    parent = _fetch_all(
        "SELECT membership_id FROM memberships "
        "WHERE tenant_id = %s AND user_id = %s AND scope_level = 'TENANT' "
        "AND status = 'ACTIVE' LIMIT 1",
        (tid, uid),
    )
    if not parent:
        raise WorkspaceError(
            "tài khoản chưa là thành viên của tổ chức — hãy mời họ vào tổ chức trước",
            status_code=409,
        )
    parent_id = str(parent[0]["membership_id"])

    role = _fetch_all(
        "SELECT role_id, role_code FROM roles "
        "WHERE role_code = %s AND scope_level = %s AND is_active "
        "AND (tenant_id IS NULL OR tenant_id = %s) LIMIT 1",
        (str(role_code or "").strip(), level, tid),
    )
    if not role:
        raise WorkspaceError(
            f"vai {role_code!r} không tồn tại ở cấp {level}", status_code=422
        )
    role_id = str(role[0]["role_id"])

    # (2) membership ở đúng cấp — dùng lại nếu đã có, để hai vai ở cùng phạm vi
    #     không sinh ra hai tư cách thành viên trùng nhau
    if pid:
        existing = _fetch_all(
            "SELECT membership_id FROM memberships WHERE tenant_id = %s AND user_id = %s "
            "AND scope_level = 'PROJECT' AND workspace_id = %s AND project_id = %s "
            "AND status = 'ACTIVE' LIMIT 1",
            (tid, uid, wid, pid),
        )
    else:
        existing = _fetch_all(
            "SELECT membership_id FROM memberships WHERE tenant_id = %s AND user_id = %s "
            "AND scope_level = 'WORKSPACE' AND workspace_id = %s AND project_id IS NULL "
            "AND status = 'ACTIVE' LIMIT 1",
            (tid, uid, wid),
        )

    if existing:
        membership_id = str(existing[0]["membership_id"])
    else:
        membership_id = str(uuid.uuid4())
        _execute(
            """
            INSERT INTO memberships (membership_id, user_id, scope_level, tenant_id,
                                     workspace_id, project_id, parent_membership_id,
                                     status, joined_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'ACTIVE', NOW())
            """,
            (membership_id, uid, level, tid, wid, pid, parent_id),
        )

    # (3) lần gán vai — trùng vai ở cùng phạm vi thì không ghi thêm dòng
    dup = _fetch_all(
        "SELECT assignment_id FROM role_assignments "
        "WHERE membership_id = %s AND user_id = %s AND role_id = %s "
        "AND revoked_at IS NULL LIMIT 1",
        (membership_id, uid, role_id),
    )
    if dup:
        raise WorkspaceError("người này đã có vai đó ở phạm vi này", status_code=409)

    assignment_id = str(uuid.uuid4())
    _execute(
        """
        INSERT INTO role_assignments (assignment_id, user_id, role_id, membership_id,
                                      assigned_by_user_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (assignment_id, uid, role_id, membership_id, _uuid_or_400(actor_user_id,
                                                                  field="mã người gán")),
    )
    logger.info("[SCOPE_ROLE][GRANT] tenant=%s level=%s ws=%s prj=%s user=%s role=%s",
                tid, level, wid, pid, uid, role_code)

    return {
        "assignment_id": assignment_id,
        "membership_id": membership_id,
        "scope_level": level,
        "workspace_id": wid,
        "project_id": pid,
        "user_id": uid,
        "role_code": role[0]["role_code"],
    }


def revoke_scope_role(
    tenant_id: str,
    *,
    assignment_id: str,
    actor_user_id: str,
    reason: str = "",
) -> Dict[str, Any]:
    """Thu vai bằng cách đánh dấu, không bằng cách xoá dòng.

    `role_assignments` có ràng buộc `CHECK (revoked_by_user_id, revoked_at)`: đã
    thu hồi thì bắt buộc ghi ai thu hồi. Xoá dòng đi sẽ mất luôn câu trả lời cho
    *"ai từng có quyền gì, tới khi nào"* — thứ mà một nhật ký kiểm toán không
    dựng lại được nếu chính bản ghi gốc biến mất.
    """
    from app.storage.metadata_db import _execute, _fetch_all

    tid = normalize_tenant_id(tenant_id)
    aid = _uuid_or_400(assignment_id, field="mã lần gán vai")

    rows = _fetch_all(
        """
        SELECT ra.assignment_id, m.tenant_id, m.scope_level
        FROM role_assignments ra
        JOIN memberships m ON m.membership_id = ra.membership_id
        WHERE ra.assignment_id = %s AND ra.revoked_at IS NULL
        """,
        (aid,),
    )
    if not rows or str(rows[0]["tenant_id"]) != tid:
        raise WorkspaceError("không tìm thấy lần gán vai này", status_code=404)
    if str(rows[0]["scope_level"]) not in {"WORKSPACE", "PROJECT"}:
        raise WorkspaceError(
            "chỉ thu được vai cấp workspace/project ở đây; vai cấp tổ chức quản lý ở "
            "trang Tổ chức",
            status_code=409,
        )

    _execute(
        "UPDATE role_assignments SET revoked_at = NOW(), revoked_by_user_id = %s, "
        "revoke_reason = %s WHERE assignment_id = %s",
        (_uuid_or_400(actor_user_id, field="mã người thu hồi"),
         str(reason or "")[:500] or None, aid),
    )
    logger.info("[SCOPE_ROLE][REVOKE] tenant=%s assignment=%s", tid, aid)
    return {"assignment_id": aid, "revoked": True}


# --------------------------------------------------------------------------- cấp phát

#: Chỉ tiêu cấp phát được xuống cấp project, và cột hạn mức tương ứng ở `plans`.
#:
#: Từ vựng tên chỉ tiêu DÙNG CHUNG với `tenant_usage_daily`. Đặt hai từ vựng
#: khác nhau cho cùng một khái niệm là cách chắc chắn nhất để hai bảng số liệu
#: nói hai chuyện rồi không ai đối chiếu được.
ALLOCATABLE_METRICS: Dict[str, str] = {
    "samples": "max_samples",
    "storage_mb": "max_storage_mb",
    "training_jobs_per_month": "max_training_jobs_per_month",
}


def _tenant_ceiling(tenant_id: str) -> Dict[str, Optional[int]]:
    """Trần của tenant cho từng chỉ tiêu, lấy từ gói cước đang áp.

    `None` nghĩa là **không giới hạn** — cùng quy ước với `plans`, và là chỗ đọc
    nhầm sẽ chặn toàn bộ hoạt động của một gói không giới hạn.
    """
    from app.plans import get_plan
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        "SELECT plan_code FROM tenants WHERE tenant_id = %s",
        (normalize_tenant_id(tenant_id),),
    )
    plan_code = str(rows[0]["plan_code"]) if rows else "free"
    try:
        plan = get_plan(plan_code) or {}
    except Exception:  # noqa: BLE001 - gói lạ không được làm sập trang cấp phát
        plan = {}
    return {
        metric: (None if plan.get(column) in (None, "") else int(plan[column]))
        for metric, column in ALLOCATABLE_METRICS.items()
    }


def list_allocations(tenant_id: str, workspace_id: str) -> Dict[str, Any]:
    """Bảng cấp phát của mọi project trong một workspace, kèm trần của tenant.

    Trả về **cả ba vế** cho mỗi chỉ tiêu: trần tenant · tổng đã cấp phát · phần
    còn lại. Trả mỗi phần đã cấp phát rồi để giao diện tự trừ là cách hai màn
    hình cùng tính ra hai con số khác nhau.
    """
    from app.storage.metadata_db import _fetch_all

    tid = normalize_tenant_id(tenant_id)
    wid = str(get_workspace(tid, workspace_id)["workspace_id"])
    projects = list_projects(tid, wid, include_archived=True)
    ceiling = _tenant_ceiling(tid)

    rows = _fetch_all(
        """
        SELECT a.project_id, a.metric, a.allocated, a.note, a.updated_at
        FROM project_allocations a
        JOIN projects p ON p.tenant_id = a.tenant_id AND p.project_id = a.project_id
        WHERE a.tenant_id = %s AND p.workspace_id = %s
        """,
        (tid, wid),
    )
    by_project: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        by_project.setdefault(str(r["project_id"]), {})[str(r["metric"])] = {
            "allocated": None if r["allocated"] is None else int(r["allocated"]),
            "note": r["note"],
            "updated_at": r["updated_at"],
        }

    used: Dict[str, int] = {m: 0 for m in ALLOCATABLE_METRICS}
    for metrics in by_project.values():
        for metric, cell in metrics.items():
            if metric in used and cell["allocated"] is not None:
                used[metric] += int(cell["allocated"])

    return {
        "workspace_id": wid,
        "metrics": list(ALLOCATABLE_METRICS),
        "tenant_ceiling": ceiling,
        "allocated_total": used,
        "remaining": {
            m: (None if ceiling.get(m) is None else max(0, int(ceiling[m]) - used[m]))
            for m in ALLOCATABLE_METRICS
        },
        "projects": [
            {
                "project_id": str(p["project_id"]),
                "name": p["name"],
                "status": p["status"],
                "is_default": bool(p["is_default"]),
                "allocations": by_project.get(str(p["project_id"]), {}),
            }
            for p in projects
        ],
    }


def set_allocation(
    tenant_id: str,
    *,
    workspace_id: str,
    project_id: str,
    metric: str,
    allocated: Optional[int],
    note: str = "",
    actor_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Cấp phát một phần hạn mức của tenant xuống một project.

    Hai phép kiểm, và cái thứ hai là lý do hàm này không phải một câu `UPSERT`:

    1. **Chỉ tiêu phải nằm trong từ vựng.** Một tên gõ sai sẽ tạo ra một dòng
       không ai đọc, và tổng cấp phát vẫn trông đúng.
    2. **Tổng cấp phát của mọi project không vượt trần tenant.** Không có phép
       kiểm này, cấp phát trở thành một con số trang trí: ba project mỗi cái
       được 1.000 mẫu trong khi gói cho 500.

    Trần `None` (không giới hạn) thì bỏ qua phép kiểm thứ hai — không có gì để
    vượt.
    """
    from app.storage.metadata_db import _execute, _fetch_all

    tid = normalize_tenant_id(tenant_id)
    wid = str(get_workspace(tid, workspace_id)["workspace_id"])
    pid = _uuid_or_400(project_id, field="mã project")
    key = str(metric or "").strip()

    if key not in ALLOCATABLE_METRICS:
        raise WorkspaceError(
            f"chỉ tiêu phải là một trong {', '.join(ALLOCATABLE_METRICS)}",
            status_code=422,
        )
    if allocated is not None and int(allocated) < 0:
        raise WorkspaceError("giá trị cấp phát không được âm", status_code=422)

    owned = _fetch_all(
        "SELECT project_id FROM projects WHERE tenant_id = %s AND workspace_id = %s "
        "AND project_id = %s AND deleted_at IS NULL",
        (tid, wid, pid),
    )
    if not owned:
        raise WorkspaceError("không tìm thấy project trong workspace này", status_code=404)

    ceiling = _tenant_ceiling(tid).get(key)
    if ceiling is not None and allocated is not None:
        others = _fetch_all(
            "SELECT COALESCE(SUM(allocated), 0) AS total FROM project_allocations "
            "WHERE tenant_id = %s AND metric = %s AND project_id <> %s",
            (tid, key, pid),
        )
        already = int(others[0]["total"] or 0) if others else 0
        if already + int(allocated) > int(ceiling):
            raise WorkspaceError(
                f"vượt trần của gói: đã cấp {already}, trần {ceiling}, "
                f"còn lại {max(0, int(ceiling) - already)}",
                status_code=409,
            )

    _execute(
        """
        INSERT INTO project_allocations (tenant_id, project_id, metric, allocated,
                                         note, updated_by, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (tenant_id, project_id, metric) DO UPDATE
            SET allocated = EXCLUDED.allocated,
                note       = EXCLUDED.note,
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW()
        """,
        # `updated_by` để NULL được: cột khai NULL và `ON DELETE SET NULL`, tức
        # lược đồ vốn đã chấp nhận "không rõ ai cấp". Ép phải có UUID ở đây sẽ
        # chặn đúng những đường ghi hợp lệ mà không có người dùng đứng sau —
        # migration, seed, và mọi test không dựng sẵn một tài khoản.
        (tid, pid, key, allocated, str(note or "")[:500],
         None if actor_user_id in (None, "") else
         _uuid_or_400(actor_user_id, field="mã người cấp phát")),
    )
    logger.info("[ALLOCATION][SET] tenant=%s project=%s metric=%s value=%s",
                tid, pid, key, allocated)
    return {"project_id": pid, "metric": key, "allocated": allocated}


# --------------------------------------------------------------------------- tổng quan


def scope_tree_summary(tenant_id: str) -> Dict[str, Any]:
    """Số liệu để trang hiển thị **đúng trạng thái**, không phải trạng thái mong muốn.

    Trả về cả `data_carries_project_id = False`. Đây không phải một trường thừa:
    nó là thứ giao diện dùng để in ra ghi chú rằng dữ liệu chưa gắn vào cây, thay
    vì để người xem tự suy ra rằng tạo project xong là dữ liệu đã phân về project.
    """
    from app.storage.metadata_db import _fetch_all

    tid = normalize_tenant_id(tenant_id)
    counts = _fetch_all(
        """
        SELECT
          (SELECT COUNT(*) FROM workspaces
             WHERE tenant_id = %s AND deleted_at IS NULL AND status = 'ACTIVE') AS workspaces,
          (SELECT COUNT(*) FROM projects
             WHERE tenant_id = %s AND deleted_at IS NULL AND status = 'ACTIVE') AS projects,
          (SELECT COUNT(*) FROM memberships
             WHERE tenant_id = %s AND scope_level = 'WORKSPACE' AND status = 'ACTIVE') AS ws_members,
          (SELECT COUNT(*) FROM memberships
             WHERE tenant_id = %s AND scope_level = 'PROJECT' AND status = 'ACTIVE') AS prj_members
        """,
        (tid, tid, tid, tid),
    )
    row = dict(counts[0]) if counts else {}
    from app.config import settings

    return {
        "tenant_id": tid,
        "workspaces": int(row.get("workspaces") or 0),
        "projects": int(row.get("projects") or 0),
        "workspace_members": int(row.get("ws_members") or 0),
        "project_members": int(row.get("prj_members") or 0),
        # Hai cờ dưới đây là phần TRUNG THỰC của màn hình. Xem docstring module.
        "data_carries_project_id": False,
        "authz_mode": str(getattr(settings, "authz_mode", "shadow")),
    }
