"""Đưa quyền đang chạy vào mặt phẳng RBAC mới, KHÔNG đổi hành vi.

Nó dịch cái gì
--------------
Ba nguồn quyền cũ, và chỉ ba:

    users.is_admin = TRUE            → role_assignments (membership_id NULL)
                                       → platform_administrator
    tenant_members.role = 'admin'    → role_assignments (membership TENANT)
                                       → tenant_administrator
    tenant_members.role = 'editor'   → role_assignments (membership TENANT)
                                       → tenant_editor
    tenant_members.role IS NULL      → KHÔNG gán gì

Dòng cuối là một trạng thái hợp lệ, không phải một dòng bị bỏ sót: người đó là
thành viên của tenant và chưa có vai nào ở tầng tenant. Họ vẫn nhận được
membership workspace/project như mọi thành viên khác (xem phần khung bên dưới);
thứ họ không nhận là một role ở tầng tenant, vì không có role nào để dịch sang.
Xem `authorization/catalog.py::RETIRED_BUILTIN_ROLES`.

Cộng với phần khung mà cây bốn tầng đòi hỏi: mỗi tenant nhận MỘT workspace và
MỘT project mặc định, và mọi thành viên tenant trở thành thành viên của cả hai.

Vì sao KHÔNG gán role xuống workspace/project
----------------------------------------------
Cám dỗ là gán `project_manager` cho mọi tenant admin, `project_editor` cho mọi
editor. Đừng. §14 PDM nói thẳng: **không tạo assignment giả xuống từng
project**. Thống trị phạm vi đã lo việc đó — `tenant_admin` cầm `sample.delete`
(phạm vi PROJECT), nên khi hỏi ở domain `prj:P` không ra gì, `AuthorizationService`
sẽ hỏi tiếp `ten:T` và tìm thấy.

Cái giá của việc gán thừa không phải là hiệu năng mà là **thu hồi**: gỡ ai đó
khỏi vai quản trị tenant sẽ phải nhớ gỡ cả bốn dòng ở bốn bảng, và cái bị quên
sẽ để họ giữ nguyên quyền trong project. Một dòng thì không quên được.

Vì sao thành viên workspace/project VẪN được tạo
-------------------------------------------------
Khác với role, tư cách thành viên là một sự kiện dữ liệu chứ không phải một
đường cấp quyền: nó nói "người này thuộc về đây". `AuthorizationService` kiểm
tra nó (§20 — trạng thái hiệu lực phải đọc từ nguồn thật, không từ cache
policy), và chuỗi khoá ngoại ghép của PDM đòi nó phải có trước khi bất kỳ role
phạm vi project nào gán được. Không tạo bây giờ thì Phase 5 phải vừa bật giao
diện vừa backfill trên hệ đang chạy.

`assigned_by_user_id` ghi ai?
-----------------------------
Cột đó NOT NULL, và ở đây không có con người nào bấm nút. Ba cách, và hai cách
sai:

  * Ghi chính người được cấp → dòng nói "tự cấp cho mình quyền quản trị nền
    tảng". Sai về sự thật và đúng cái loại sai mà một sổ kiểm toán không được
    phép mắc.
  * Nới cột thành NULL → mất luôn khả năng trả lời "ai cấp quyền này" cho MỌI
    dòng về sau, chỉ để chứa một lần chạy migration.
  * Đòi `--actor`: một người thật chịu trách nhiệm cho lần dịch này, và
    `audit_log` ghi rõ đây là backfill chứ không phải thao tác thủ công.

Cách thứ ba được chọn. Không đoán mặc định — thiếu `--actor` thì dừng.

CÁCH DÙNG
---------
    python -m app.cli.backfill_authz --actor <username|uuid>            # chỉ báo cáo
    python -m app.cli.backfill_authz --actor <username|uuid> --apply    # ghi thật
    python -m app.cli.backfill_authz --actor admin --apply --tenant ctu # một tenant

Phải chạy trong container tới được Postgres (host không tới được: dịch vụ
postgres không mở cổng nào ra ngoài).

Chạy lại được: mọi bước đều `ON CONFLICT DO NOTHING` hoặc có kiểm tra tồn tại
trước, nên lượt thứ hai báo 0 thay đổi.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, Dict, List, Optional

from app.authorization.catalog import LEGACY_SYSTEM_ADMIN_ROLE, LEGACY_TENANT_ROLE_MAP
from app.tenant_context import platform_command

logger = logging.getLogger("backfill.authz")

DEFAULT_WORKSPACE_NAME = "Mặc định"
DEFAULT_PROJECT_NAME = "Mặc định"


def _fetch(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    from app.storage.metadata_db import _fetch_all

    return _fetch_all(sql, params)


def _resolve_actor(actor: str) -> str:
    """Đổi `--actor` (username, email hoặc UUID) thành id tài khoản.

    Đòi tài khoản phải ĐANG HOẠT ĐỘNG. Quy quyền cho một tài khoản đã bị khoá
    làm dòng kiểm toán tự mâu thuẫn: nó nói một người không đăng nhập được đã
    cấp quyền cho người khác.
    """
    rows = _fetch(
        "SELECT id, username, is_active FROM users "
        "WHERE id::text = %s OR username = %s OR lower(email) = lower(%s)",
        (actor, actor, actor),
    )
    if not rows:
        raise SystemExit(f"--actor {actor!r}: khong tim thay tai khoan nao")
    if len(rows) > 1:
        raise SystemExit(f"--actor {actor!r}: khop {len(rows)} tai khoan, hay dung UUID")
    if not rows[0]["is_active"]:
        raise SystemExit(f"--actor {actor!r}: tai khoan dang bi khoa")
    return str(rows[0]["id"])


def _builtin_role_ids() -> Dict[str, str]:
    """Tên role dựng sẵn → role_id.

    Dừng hẳn nếu thiếu. Một role dựng sẵn vắng mặt nghĩa là seed chưa chạy hoặc
    đã hỏng, và backfill trong tình trạng đó sẽ gán được một phần rồi bỏ dở —
    trạng thái tệ hơn cả chưa chạy, vì nó TRÔNG như đã xong.
    """
    rows = _fetch(
        "SELECT role_id, role_code FROM roles WHERE is_builtin AND tenant_id IS NULL")
    found = {r["role_code"]: str(r["role_id"]) for r in rows}
    needed = set(LEGACY_TENANT_ROLE_MAP.values()) | {LEGACY_SYSTEM_ADMIN_ROLE}
    missing = sorted(needed - set(found))
    if missing:
        raise SystemExit(
            f"thieu role dung san: {', '.join(missing)}. "
            f"Chay lai ensure_tables() de seed danh muc truoc."
        )
    return found


# ---------------------------------------------------------------------------
# Các bước
# ---------------------------------------------------------------------------

def _plan_containers(tenants: List[str]) -> List[Dict[str, Any]]:
    """Tenant nào còn thiếu workspace hoặc project mặc định."""
    plan = []
    for tenant_id in tenants:
        ws = _fetch(
            "SELECT workspace_id FROM workspaces "
            "WHERE tenant_id = %s AND is_default AND status = 'ACTIVE' AND deleted_at IS NULL",
            (tenant_id,),
        )
        workspace_id = str(ws[0]["workspace_id"]) if ws else None
        project_id = None
        if workspace_id:
            pr = _fetch(
                "SELECT project_id FROM projects WHERE tenant_id = %s AND workspace_id = %s "
                "AND is_default AND status = 'ACTIVE' AND deleted_at IS NULL",
                (tenant_id, workspace_id),
            )
            project_id = str(pr[0]["project_id"]) if pr else None
        if workspace_id and project_id:
            continue
        plan.append({
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "project_id": project_id,
        })
    return plan


def _apply_containers(cur, item: Dict[str, Any]) -> Dict[str, str]:
    """Tạo workspace/project mặc định còn thiếu cho một tenant.

    `cur.fetchone()[0]`, không phải `["workspace_id"]`: `metadata_db._cursor()`
    trả con trỏ tuple thường. Chỉ `_fetch_all` mới dùng `RealDictCursor`, và
    nhầm hai cái là một lỗi lúc chạy chứ không phải lúc kiểm kiểu.
    """
    tenant_id = item["tenant_id"]
    workspace_id = item["workspace_id"]
    if not workspace_id:
        cur.execute(
            "INSERT INTO workspaces (tenant_id, name, description, is_default) "
            "VALUES (%s, %s, %s, TRUE) RETURNING workspace_id",
            (tenant_id, DEFAULT_WORKSPACE_NAME,
             "Workspace mặc định, tạo khi chuyển sang mô hình bốn tầng"),
        )
        workspace_id = str(cur.fetchone()[0])

    project_id = item["project_id"]
    if not project_id:
        cur.execute(
            "INSERT INTO projects (tenant_id, workspace_id, name, description, is_default) "
            "VALUES (%s, %s, %s, %s, TRUE) RETURNING project_id",
            (tenant_id, workspace_id, DEFAULT_PROJECT_NAME,
             "Project mặc định, chứa toàn bộ dữ liệu có trước mô hình bốn tầng"),
        )
        project_id = str(cur.fetchone()[0])

    return {"workspace_id": workspace_id, "project_id": project_id}


def _plan_memberships() -> List[Dict[str, Any]]:
    """Thành viên tenant còn thiếu tư cách thành viên workspace/project mặc định.

    Chỉ thành viên ĐANG HOẠT ĐỘNG. Người đã bị gỡ khỏi tenant không được lôi
    vào cây mới — làm vậy là hồi sinh một quyền đã bị thu. `ct_membership_chain`
    cũng từ chối một dòng ACTIVE treo dưới cha không ACTIVE, nên bỏ mệnh đề này
    sẽ đổi một lượt backfill im lặng thành một lượt ngã giữa chừng.

    Trả về cả `parent_membership_id` — id của tư cách thành viên TENANT. Cây
    membership của v5 là cây thật: `ct_membership_chain` đòi dòng WORKSPACE nêu
    cha TENANT và dòng PROJECT nêu cha WORKSPACE, cùng người và cùng tenant.
    Suy ra nó ở bước ghi thì phải truy vấn lại một lần nữa cho mỗi dòng.
    """
    return _fetch(
        """
        SELECT tm.tenant_id,
               tm.user_id::text          AS user_id,
               tm.membership_id::text    AS tenant_membership_id,
               w.workspace_id::text      AS workspace_id,
               p.project_id::text        AS project_id,
               (wm.membership_id IS NULL) AS needs_workspace,
               (pm.membership_id IS NULL) AS needs_project
          FROM memberships tm
          JOIN workspaces w
            ON w.tenant_id = tm.tenant_id AND w.is_default
           AND w.status = 'ACTIVE' AND w.deleted_at IS NULL
          JOIN projects p
            ON p.tenant_id = tm.tenant_id AND p.workspace_id = w.workspace_id
           AND p.is_default AND p.status = 'ACTIVE' AND p.deleted_at IS NULL
          LEFT JOIN memberships wm
            ON wm.scope_level = 'WORKSPACE' AND wm.tenant_id = tm.tenant_id
           AND wm.workspace_id = w.workspace_id AND wm.user_id = tm.user_id
          LEFT JOIN memberships pm
            ON pm.scope_level = 'PROJECT' AND pm.tenant_id = tm.tenant_id
           AND pm.project_id = p.project_id AND pm.user_id = tm.user_id
         WHERE tm.scope_level = 'TENANT'
           AND tm.status = 'ACTIVE' AND tm.left_at IS NULL
           AND (wm.membership_id IS NULL OR pm.membership_id IS NULL)
        """
    )


def _apply_membership(cur, row: Dict[str, Any]) -> None:
    """Dựng tư cách thành viên workspace rồi project cho một người.

    Workspace TRƯỚC project, và không đảo được: `ct_membership_chain` đòi cha
    của một dòng PROJECT là một dòng WORKSPACE **cùng nhánh** (INV-MEM-03).

    `legacy_role` nêu NULL TƯỜNG MINH ở cả hai câu:
    `ck_memberships_legacy_role_tenant_only` chỉ cho phép vai cũ ở mức TENANT.
    """
    workspace_membership_id = None
    if row["needs_workspace"]:
        cur.execute(
            "INSERT INTO memberships (user_id, scope_level, tenant_id, workspace_id, "
            "                         parent_membership_id, legacy_role, status, joined_at) "
            "VALUES (%s, 'WORKSPACE', %s, %s, %s, NULL, 'ACTIVE', NOW()) "
            "RETURNING membership_id",
            (row["user_id"], row["tenant_id"], row["workspace_id"],
             row["tenant_membership_id"]),
        )
        workspace_membership_id = cur.fetchone()[0]

    if row["needs_project"]:
        # Dòng workspace có thể vừa tạo ở trên, hoặc đã có từ trước (một người
        # có thể thiếu project mà không thiếu workspace). Đọc lại khi cần thay
        # vì giả định — giả định sai ở đây là `parent_membership_id = NULL` và
        # một `ct_membership_chain` ngã giữa lượt chạy.
        if workspace_membership_id is None:
            cur.execute(
                "SELECT membership_id FROM memberships "
                " WHERE scope_level = 'WORKSPACE' AND tenant_id = %s "
                "   AND workspace_id = %s AND user_id = %s",
                (row["tenant_id"], row["workspace_id"], row["user_id"]),
            )
            found = cur.fetchone()
            if not found:
                raise SystemExit(
                    f"backfill: thieu tu cach thanh vien workspace cho {row['user_id']} "
                    f"trong {row['tenant_id']} — khong dung duoc cay membership"
                )
            workspace_membership_id = found[0]

        cur.execute(
            "INSERT INTO memberships (user_id, scope_level, tenant_id, workspace_id, "
            "                         project_id, parent_membership_id, legacy_role, "
            "                         status, joined_at) "
            "VALUES (%s, 'PROJECT', %s, %s, %s, %s, NULL, 'ACTIVE', NOW())",
            (row["user_id"], row["tenant_id"], row["workspace_id"],
             row["project_id"], workspace_membership_id),
        )


def _plan_tenant_roles(role_ids: Dict[str, str], tenants: Optional[List[str]]) -> List[Dict[str, Any]]:
    """Thành viên tenant chưa có assignment tương ứng với `tenant_members.role`.

    Thành viên có `role IS NULL` không bao giờ vào kế hoạch, và không cần một
    mệnh đề nào để loại họ: vòng lặp chỉ chạy trên các khoá của
    `LEGACY_TENANT_ROLE_MAP`, và `tm.role = %s` không bao giờ đúng với NULL —
    SQL ba giá trị lo phần đó. Ghi ra vì "vắng mặt do đúng ngữ nghĩa" trông
    giống hệt "vắng mặt do quên" khi đọc lại sau sáu tháng.
    """
    plan = []
    for legacy_role, builtin in LEGACY_TENANT_ROLE_MAP.items():
        role_id = role_ids[builtin]
        # `membership_id` đi kèm vì `role_assignments` KHÔNG có `tenant_id`:
        # phạm vi của một lần gán được đọc từ membership nó trỏ tới, và
        # `ct_role_assignments_scope` từ chối một role TENANT không nêu
        # membership.
        sql = """
            SELECT tm.tenant_id,
                   tm.user_id::text       AS user_id,
                   tm.membership_id::text AS membership_id
              FROM memberships tm
             WHERE tm.scope_level = 'TENANT' AND tm.legacy_role = %s
               AND tm.status = 'ACTIVE' AND tm.left_at IS NULL
               AND NOT EXISTS (
                   SELECT 1 FROM role_assignments a
                    WHERE a.membership_id = tm.membership_id
                      AND a.role_id = %s AND a.revoked_at IS NULL
               )
        """
        params: tuple = (legacy_role, role_id)
        if tenants:
            sql += " AND tm.tenant_id = ANY(%s)"
            params = params + (tenants,)
        for row in _fetch(sql, params):
            plan.append({**row, "role_id": role_id, "role_name": builtin,
                         "legacy_role": legacy_role})
    return plan


def _plan_system_roles(role_ids: Dict[str, str]) -> List[Dict[str, Any]]:
    """Tài khoản `is_admin` chưa có assignment `platform_admin`.

    `is_active` được kiểm ở đây và KHÔNG ở phía tenant, vì hai lý do khác nhau:
    một tài khoản bị khoá vẫn nên giữ vai trò trong tenant của họ (để danh sách
    thành viên còn đọc được), nhưng quyền toàn nền tảng thì không nên tự động
    theo về khi tài khoản được mở lại.
    """
    role_id = role_ids[LEGACY_SYSTEM_ADMIN_ROLE]
    return [
        {**row, "role_id": role_id, "role_name": LEGACY_SYSTEM_ADMIN_ROLE}
        for row in _fetch(
            """
            SELECT u.id::text AS user_id, u.username
              FROM users u
             WHERE u.is_admin AND u.is_active
               AND NOT EXISTS (
                   SELECT 1 FROM role_assignments a
                    WHERE a.user_id = u.id AND a.role_id = %s
                      AND a.membership_id IS NULL AND a.revoked_at IS NULL
               )
            """,
            (role_id,),
        )
    ]


# ---------------------------------------------------------------------------
# Điều phối
# ---------------------------------------------------------------------------

@platform_command("cli: backfill mat phang phan quyen PDM")
def run(actor: str, apply: bool, tenants: Optional[List[str]]) -> int:
    from app.storage.metadata_db import _cursor

    actor_id = _resolve_actor(actor)
    role_ids = _builtin_role_ids()

    if tenants:
        known = {r["tenant_id"] for r in _fetch("SELECT tenant_id FROM tenants")}
        unknown = sorted(set(tenants) - known)
        if unknown:
            raise SystemExit(f"--tenant: khong co tenant nao ten {', '.join(unknown)}")
        tenant_list = tenants
    else:
        # `deleted_at IS NULL`: một tenant đã bị xoá mềm không cần cây phân
        # quyền, và tạo workspace cho nó sẽ làm `purge` sau này phải dọn thêm.
        tenant_list = [
            r["tenant_id"]
            for r in _fetch("SELECT tenant_id FROM tenants WHERE deleted_at IS NULL "
                            "ORDER BY tenant_id")
        ]

    containers = _plan_containers(tenant_list)
    print(f"[1/4] workspace+project mac dinh con thieu : {len(containers)} tenant")
    for item in containers:
        have = []
        if item["workspace_id"]:
            have.append("workspace da co")
        print(f"      - {item['tenant_id']}{' (' + ', '.join(have) + ')' if have else ''}")

    if apply and containers:
        with _cursor() as cur:
            for item in containers:
                _apply_containers(cur, item)

    # Tư cách thành viên chỉ đếm được SAU khi container tồn tại: truy vấn
    # JOIN vào `workspaces`/`projects`, nên trên một hệ chưa có workspace nào
    # nó trả về rỗng. Ở chế độ chỉ-báo-cáo với container còn thiếu, con số
    # thật chưa biết được — và in "0" ở đó là nói dối theo hướng trấn an.
    memberships = _plan_memberships()
    if not apply and containers:
        pending = sum(
            r["members"] for r in _fetch(
                "SELECT tenant_id, count(*) AS members FROM memberships "
                "WHERE scope_level = 'TENANT' AND status = 'ACTIVE' AND left_at IS NULL "
                "AND tenant_id = ANY(%s) GROUP BY tenant_id",
                ([c["tenant_id"] for c in containers],),
            )
        )
        print(f"[2/4] tu cach thanh vien workspace/project  : {len(memberships)} dong "
              f"+ ~{pending} sau khi tao container")
    else:
        print(f"[2/4] tu cach thanh vien workspace/project  : {len(memberships)} dong")
    if apply and memberships:
        with _cursor() as cur:
            for row in memberships:
                _apply_membership(cur, row)

    tenant_roles = _plan_tenant_roles(role_ids, tenants)
    print(f"[3/4] gan role trong tenant                 : {len(tenant_roles)} dong")
    by_role: Dict[str, int] = {}
    for row in tenant_roles:
        by_role[row["role_name"]] = by_role.get(row["role_name"], 0) + 1
    for name, count in sorted(by_role.items()):
        print(f"      - {name}: {count}")
    if apply and tenant_roles:
        with _cursor() as cur:
            for row in tenant_roles:
                cur.execute(
                    "INSERT INTO role_assignments "
                    "(user_id, role_id, membership_id, assigned_by_user_id) "
                    "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (row["user_id"], row["role_id"], row["membership_id"], actor_id),
                )

    system_roles = _plan_system_roles(role_ids)
    print(f"[4/4] gan role he thong (is_admin)          : {len(system_roles)} dong")
    for row in system_roles:
        print(f"      - {row['username']}")
    if apply and system_roles:
        with _cursor() as cur:
            for row in system_roles:
                cur.execute(
                    # `membership_id` NULL = phạm vi hệ thống.
                    # `ct_role_assignments_scope` cưỡng chế cả hai chiều, nên
                    # đây không phải quy ước mà là điều kiện để câu chèn đi lọt.
                    "INSERT INTO role_assignments "
                    "(user_id, role_id, membership_id, assigned_by_user_id) "
                    "VALUES (%s, %s, NULL, %s) ON CONFLICT DO NOTHING",
                    (row["user_id"], row["role_id"], actor_id),
                )

    total = len(containers) + len(memberships) + len(tenant_roles) + len(system_roles)
    if not apply:
        print(f"\nCHUA GHI GI. Them --apply de thuc hien {total} thay doi.")
        return 0

    # Một dòng kiểm toán cho cả lần chạy, không phải một dòng mỗi assignment.
    # Đây là MỘT hành động quản trị — "dịch quyền cũ sang mô hình mới" — và
    # ghi 400 dòng sẽ vùi lấp nhật ký đúng ngày người ta cần đọc nó nhất. Chi
    # tiết từng dòng nằm ở chính các bảng gán, kèm `assigned_at`.
    from app import audit

    audit.record(
        "authz.backfill",
        actor={"id": actor_id},
        target_type="authorization",
        detail={
            "containers": len(containers),
            "memberships": len(memberships),
            "tenant_roles": by_role,
            "system_roles": len(system_roles),
            "tenants": tenant_list if tenants else "all",
        },
    )
    print(f"\nDA GHI {total} thay doi. Quyen cu (is_admin / tenant_members.role) GIU NGUYEN.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill mat phang phan quyen PDM tu quyen dang chay")
    parser.add_argument(
        "--actor", required=True,
        help="Tai khoan chiu trach nhiem cho lan dich nay (username, email hoac UUID). "
             "Ghi vao assigned_by_user_id — xem docstring module ve vi sao khong co mac dinh.")
    parser.add_argument("--apply", action="store_true",
                        help="Ghi that. Khong co co nay thi chi bao cao.")
    parser.add_argument("--tenant", action="append", dest="tenants",
                        help="Gioi han o mot tenant. Lap lai duoc.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return run(actor=args.actor, apply=args.apply, tenants=args.tenants)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
