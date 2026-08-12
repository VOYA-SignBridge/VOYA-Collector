"""Mặt phẳng phân quyền của PDM v5.0 — DDL, và lý do từng ràng buộc tồn tại.

Bảng này giải bài toán gì
-------------------------
Trước module này, câu trả lời cho "người này được làm gì" nằm rải ở hai chỗ và
cả hai đều là cột trần:

    users.is_admin        BOOLEAN   — đọc ở 12 tệp
    tenant_members.role   TEXT      — 'admin' | 'editor' | NULL

Kiểu thất bại của thiết kế đó không phải là sai, mà là **không trả lời được**.
Không có nơi nào liệt kê được "quyền nào tồn tại", nên không kiểm toán được ai
có quyền gì; không có lịch sử, nên không trả lời được "ai đã cấp quyền này, khi
nào"; và vì mỗi router tự diễn giải hai chữ 'admin'/'editor' theo cách riêng,
hai endpoint cùng gọi là "chỉ admin" có thể đang hiểu khác nhau mà không gì
phát hiện ra.

PDM tách nó thành bốn thứ tách bạch:

    permissions        danh mục NĂNG LỰC — bảng phẳng, không thuộc tenant nào
    roles              gói năng lực, có phạm vi (SYSTEM/TENANT/WORKSPACE/PROJECT)
    role_permissions   role nào chứa quyền nào
    role_assignments   ai giữ role nào, ở đâu, TỪ BAO GIỜ TỚI BAO GIỜ

Vì sao v5 gộp 8 bảng còn 2
---------------------------
Bản v1.0 của tệp này có ba bảng thành viên (`tenant_members`,
`workspace_members`, `project_members`) và bốn bảng gán (`system_user_roles`,
`tenant_member_roles`, `workspace_member_roles`, `project_member_roles`). Nó
chạy được, và nó sai theo một kiểu chỉ lộ ra khi đọc lại: **mỗi câu hỏi về
phân quyền phải hỏi bốn nơi rồi UNION lại.** Adapter của Casbin có năm truy
vấn; thêm một mức phạm vi là thêm hai bảng và sửa năm chỗ.

v5 dùng `memberships` + `role_assignments`, phân biệt phạm vi bằng CỘT chứ
không bằng BẢNG. Cái giá là các bất biến trước đây do khoá ngoại ghép chứng
minh (thành viên project phải là thành viên workspace) giờ cần trigger —
xem `authz_check_membership_chain`. Cái được là một câu hỏi, một truy vấn.

Vì sao `tenant_members` trở thành VIEW chứ không biến mất
----------------------------------------------------------
`tenant_members` bị 110 chỗ trong 33 tệp tham chiếu, và cột `role` của nó là vế
"cũ" của phép so sánh shadow mode. Xoá nó cùng lượt với việc gộp bảng nghĩa là
vừa đổi kiến trúc vừa vứt đi thứ duy nhất chứng minh kiến trúc mới cho cùng
kết quả.

Nên nó trở thành một view CẬP NHẬT ĐƯỢC trên lát cắt `scope_level = 'TENANT'`
của `memberships`. Hai điều làm việc này an toàn, và cả hai đã được kiểm:

  * `WITH (security_invoker = true)` — PostgreSQL 15+. Không có nó, view chạy
    với quyền của CHỦ SỞ HỮU và RLS trên `memberships` bị BỎ QUA. Đó là
    fail-OPEN ở mặt phẳng danh tính, đúng kiểu hỏng đã xảy ra ba lần trong dự
    án này. Máy đang chạy là PostgreSQL 17.10.
  * Chỉ có ĐÚNG HAI khoá ngoại từng trỏ vào `tenant_members`, và cả hai nằm
    trên bảng mà v5 xoá bỏ. Sau khi gộp, không còn ai tham chiếu — mà khoá
    ngoại thì không trỏ vào view được.

View này là cầu tạm, không phải đích. Nó biến mất ở Phase D cùng với cột
`legacy_role`, khi router đã chuyển hết sang `authorize()`.

Vì sao dựng cả Workspace/Project khi chưa có giao diện nào cho chúng
--------------------------------------------------------------------
Hôm nay sản phẩm chỉ có `User → Tenant → dữ liệu`. PDM định nghĩa
`Tenant → Workspace → Project`, và domain của Casbin (`ws:`, `prj:`) dựa vào đó.

Dựng schema đầy đủ ngay bây giờ, với mỗi tenant nhận MỘT workspace và MỘT
project mặc định, có một tính chất mà cách làm dần không có: khi tính năng
workspace thật sự được bật, không phải migrate kiến trúc phân quyền lần nữa.

Quan hệ với ba lớp phòng thủ đã có
-----------------------------------
Ba câu hỏi khác nhau, ba cơ chế khác nhau, không cái nào thay được cái nào:

    RLS            dòng này ai được CHẠM tới?          (storage/rls.py)
    Composite FK   quan hệ này có được phép TỒN TẠI?   (INTEGRITY_FK_SPECS)
    Casbin         chủ thể này có NĂNG LỰC nghiệp vụ?  (authorization/)

Liên quan: :doc:`docs/AUTHORIZATION.md`, ``app/authorization/``,
``app/cli/backfill_authz.py``.
"""

from __future__ import annotations

from typing import Iterable

# ---------------------------------------------------------------------------
# Từ vựng chung
# ---------------------------------------------------------------------------

#: Bốn mức phạm vi, theo đúng thứ tự thống trị của PDM.
#:
#: Thứ tự này KHÔNG chỉ là tài liệu — nó được ghim thành số trong hàm SQL
#: `authz_scope_rank()` bên dưới, và cả trigger kiểm tra thống trị lẫn
#: `ScopeResolver` ở tầng Python đều đọc cùng một thứ tự. Ba nơi, một nguồn.
SCOPE_LEVELS: tuple[str, ...] = ("SYSTEM", "TENANT", "WORKSPACE", "PROJECT")

#: Hai loại tenant. `COMMUNITY` là tenant dự trữ DUY NHẤT của nền tảng: nơi mọi
#: tài khoản mới nhận tư cách thành viên, và nơi từ vựng dùng chung sống.
#: `ORGANIZATION` là tenant riêng của một tổ chức — kín, chỉ thành viên thấy.
TENANT_TYPES: tuple[str, ...] = ("COMMUNITY", "ORGANIZATION")

#: Trạng thái vòng đời dùng chung cho membership. `INVITED` có mặt vì lời mời
#: đã tồn tại trong `tenant_invitations`; membership chỉ sinh ra khi lời mời
#: được chấp nhận, nên trạng thái này hiện chưa được ghi — nó ở đây để CHECK
#: không phải sửa khi luồng mời đổi.
MEMBER_STATUSES: tuple[str, ...] = ("ACTIVE", "INVITED", "SUSPENDED", "REMOVED")

#: Trạng thái vòng đời của workspace/project.
CONTAINER_STATUSES: tuple[str, ...] = ("ACTIVE", "ARCHIVED", "DELETED")

#: Định danh của tenant cộng đồng dự trữ. Hằng số, không cấu hình được: mã ở ba
#: nơi (seed, đăng ký, kiểm tra triển khai) phải đồng ý về nó, và một biến môi
#: trường lệch giữa hai máy sẽ tạo ra HAI tenant cộng đồng — mà chỉ mục duy
#: nhất bên dưới cấm, nên máy thứ hai sẽ hỏng lúc khởi động chứ không lặng lẽ.
COMMUNITY_TENANT_ID = "community"

#: Bảng mới mang `tenant_id` và vì vậy phải chịu chính sách tenant chuẩn.
#:
#: `roles` KHÔNG có ở đây dù nó có cột `tenant_id`: cột đó NULLABLE, và NULL
#: nghĩa là "danh mục chung của nền tảng". Vị từ chuẩn (`tenant_id = guc`) cho
#: ra NULL với dòng đó, tức là mọi role dựng sẵn sẽ VÔ HÌNH trong tenant scope
#: — bao gồm chính role mà tenant admin cần gán. Nó dùng chính sách bất đối
#: xứng riêng, xem `SHARED_CATALOGUE_TABLES` trong `storage/rls.py`.
#:
#: `role_assignments` KHÔNG có ở đây dù nó thuộc về tenant qua `membership_id`:
#: nó không MANG cột `tenant_id`, và không thể mang — một dòng gán role SYSTEM
#: theo định nghĩa không thuộc tenant nào. Cô lập của nó đi qua `memberships`.
#:
#: `permissions` và `role_permissions` cũng không: chúng là danh mục phẳng của
#: nền tảng, mọi tenant đọc cùng một bảng, và không tenant nào ghi được (chỉ
#: seed và migration ghi).
#:
#: `user_action_passcodes` CỐ Ý không có, cùng lý do đã viết cho `user_totp`:
#: nó thuộc mặt phẳng danh tính và được đọc GIỮA CHỪNG một thao tác nhạy cảm.
#: RLS ở đó fail-OPEN — khớp 0 dòng đọc thành "người này chưa đặt mã", tức là
#: âm thầm BỎ QUA bước xác thực nâng cấp. Đó là hỏng theo hướng nguy hiểm.
TENANT_SCOPED_AUTHZ_TABLES: tuple[str, ...] = (
    "workspaces",
    "projects",
    "memberships",
    "event_outbox",
)

#: Bảng danh mục dùng chung: đọc được cả dòng nền tảng lẫn dòng của mình, nhưng
#: chỉ GHI được dòng của mình. Xem `storage/rls.py::shared_catalogue_statements`.
SHARED_CATALOGUE_AUTHZ_TABLES: tuple[str, ...] = ("roles",)


def add_constraint(table: str, name: str, definition: str) -> str:
    """Gắn một ràng buộc CHỈ KHI nó chưa có. Chạy lại là no-op im lặng.

    Vì sao không dùng `DROP CONSTRAINT IF EXISTS` rồi `ADD CONSTRAINT`
    -------------------------------------------------------------------
    Đó là bản đầu, và nó hỏng ở lượt khởi động THỨ HAI trên sản xuất:

        ERROR: cannot drop constraint uq_workspaces_tenant_scope on table
        workspaces because other objects depend on it
        DETAIL: constraint fk_inv_ten_02_project_workspace on table projects
        depends on index uq_workspaces_tenant_scope

    Một khoá ứng viên có khoá ngoại ghép trỏ tới thì không drop được, nên câu
    DROP thất bại, rồi câu ADD cũng thất bại vì ràng buộc vẫn còn đó. Kết cục
    ĐÚNG (ràng buộc có mặt) nhưng mỗi lần khởi động của mỗi worker lại đẻ ra
    hai dòng WARNING — và trên năm service dùng chung ảnh này, đó là hàng chục
    dòng cảnh báo vĩnh viễn về một tình trạng hoàn toàn bình thường.

    Cái giá thật của tiếng ồn đó không phải là dung lượng log: nó dạy người vận
    hành bỏ qua cảnh báo của `ensure_tables`, và cảnh báo tiếp theo có thể là
    thật.

    Hệ quả phải chấp nhận: sửa ĐỊNH NGHĨA của một ràng buộc đã tồn tại sẽ không
    còn tự động áp dụng. Đó là đánh đổi đúng — đổi định nghĩa một ràng buộc là
    việc phải viết một câu migration có chủ đích, không phải thứ nên xảy ra âm
    thầm vì ai đó sửa một dòng Python.
    """
    return f"""
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{name}') THEN
        ALTER TABLE {table} ADD CONSTRAINT {name} {definition};
    END IF;
END $$
"""


def _in_list(column: str, values: Iterable[str]) -> str:
    """Sinh mệnh đề `col IN ('a','b')` từ một hằng số Python.

    Viết tay danh sách này trong SQL nghĩa là có hai nguồn sự thật cho cùng một
    tập giá trị, và cái sai lệch sẽ chỉ lộ ra khi ai đó chèn giá trị thứ năm.
    """
    joined = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({joined})"


# ---------------------------------------------------------------------------
# Hàm phụ trợ trong cơ sở dữ liệu
# ---------------------------------------------------------------------------

#: Thứ hạng phạm vi, dưới dạng hàm SQL.
#:
#: Cần ở tầng cơ sở dữ liệu vì các trigger kiểm tra thống trị chạy ở đó và
#: không gọi được mã Python. `IMMUTABLE` để planner được phép dùng nó trong
#: biểu thức chỉ mục sau này; `STRICT` để NULL vào thì NULL ra chứ không phải 0
#: — 0 sẽ làm một phạm vi thiếu trở thành "thấp hơn mọi thứ" và lặng lẽ cho qua.
_SCOPE_RANK_FN = """
CREATE OR REPLACE FUNCTION authz_scope_rank(level TEXT)
RETURNS INTEGER
LANGUAGE sql
IMMUTABLE
STRICT
AS $$
    SELECT CASE level
        WHEN 'SYSTEM'    THEN 4
        WHEN 'TENANT'    THEN 3
        WHEN 'WORKSPACE' THEN 2
        WHEN 'PROJECT'   THEN 1
        ELSE NULL
    END
$$
"""


# ---------------------------------------------------------------------------
# 0. Tenant: loại và cờ dự trữ
# ---------------------------------------------------------------------------

_TENANT_TYPE_DDL: list[str] = [
    # Mặc định `ORGANIZATION`: mọi tenant đã tồn tại là tổ chức thật, và tenant
    # cộng đồng được nâng lên tường minh bằng câu UPDATE bên dưới. Mặc định
    # ngược lại sẽ biến dữ liệu thật của CTU thành dữ liệu cộng đồng công khai.
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS tenant_type TEXT NOT NULL "
    "DEFAULT 'ORGANIZATION'",
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS is_system_reserved BOOLEAN NOT NULL "
    "DEFAULT FALSE",
    add_constraint("tenants", "ck_tenants_type",
                   "CHECK (%s)" % _in_list("tenant_type", TENANT_TYPES)),

    # Tenant cộng đồng dự trữ. `INSERT ... WHERE NOT EXISTS` chứ không
    # `ON CONFLICT`: xem chú thích cùng chủ đề ở `metadata_db.py` — `ON CONFLICT`
    # vẫn dựng tuple rồi mới phát hiện trùng, nên mọi NOT NULL thêm về sau (như
    # `plan_code` ở v4.2) sẽ bị kiểm TRƯỚC bước phát hiện đó và làm câu này thất
    # bại lặng lẽ từ lượt chạy thứ hai.
    #
    # `plan_code` phải nêu tường minh vì lý do vừa nói; `internal` vì tenant này
    # thuộc nền tảng, không phải khách hàng, nên không chịu hạn mức gói dùng thử.
    f"""
    INSERT INTO tenants (tenant_id, display_name, slug, tenant_type,
                         is_system_reserved, plan_code)
    SELECT '{COMMUNITY_TENANT_ID}', 'Cộng đồng', '{COMMUNITY_TENANT_ID}',
           'COMMUNITY', TRUE, 'internal'
     WHERE NOT EXISTS (SELECT 1 FROM tenants WHERE tenant_id = '{COMMUNITY_TENANT_ID}')
    """,
    # Idempotent, và cần tách khỏi câu INSERT: trên máy đã chạy bản trước, dòng
    # `community` có thể đã tồn tại với `tenant_type` mặc định 'ORGANIZATION'.
    f"UPDATE tenants SET tenant_type = 'COMMUNITY', is_system_reserved = TRUE "
    f"WHERE tenant_id = '{COMMUNITY_TENANT_ID}' AND tenant_type <> 'COMMUNITY'",

    # ĐÚNG MỘT tenant cộng đồng. Chỉ mục trên chính cột được lọc: mọi dòng thoả
    # vị từ đều có cùng giá trị 'COMMUNITY', nên tính duy nhất trên cột đó
    # tương đương "nhiều nhất một dòng".
    #
    # Vì sao là ràng buộc chứ không phải quy ước: `community_member` là role
    # dựng sẵn bị chặn theo `tenant_type_constraint = 'COMMUNITY'`. Hai tenant
    # cộng đồng nghĩa là hai không gian mà role đó gán được, và câu "người dùng
    # mới vào cộng đồng" mất tính xác định.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_tenants_single_community "
    "ON tenants (tenant_type) WHERE tenant_type = 'COMMUNITY'",
]


# ---------------------------------------------------------------------------
# 1. Tenant → Workspace → Project
# ---------------------------------------------------------------------------

_HIERARCHY_DDL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS workspaces (
        workspace_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id    TEXT NOT NULL,
        name         TEXT NOT NULL,
        description  TEXT NOT NULL DEFAULT '',
        status       TEXT NOT NULL DEFAULT 'ACTIVE',
        is_default   BOOLEAN NOT NULL DEFAULT FALSE,
        created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        archived_at  TIMESTAMP WITH TIME ZONE,
        deleted_at   TIMESTAMP WITH TIME ZONE,
        CONSTRAINT ck_workspaces_status CHECK (%(status)s)
    )
    """ % {"status": _in_list("status", CONTAINER_STATUSES)},

    # Khoá ứng viên cho khoá ngoại ghép. `workspace_id` một mình đã là PK, nên
    # ràng buộc này thừa về mặt tính duy nhất — nó tồn tại vì Postgres đòi hỏi
    # đích của một REFERENCES ghép phải có UNIQUE trên ĐÚNG bộ cột đó.
    #
    # Đây là thứ làm cho `projects(tenant_id, workspace_id)` không thể trỏ sang
    # workspace của tenant khác: hai cột đi cùng nhau qua khoá ngoại, nên một
    # project của tenant A tham chiếu workspace của tenant B sẽ không tìm thấy
    # dòng nào. Không có nó, chỉ `workspace_id` được kiểm, và cây phân cấp có
    # thể bắc cầu giữa hai tenant mà cơ sở dữ liệu không phản đối.
    add_constraint("workspaces", "uq_workspaces_tenant_scope",
                   "UNIQUE (tenant_id, workspace_id)"),

    "CREATE UNIQUE INDEX IF NOT EXISTS uq_workspaces_tenant_name "
    "ON workspaces (tenant_id, name) WHERE deleted_at IS NULL",

    # ĐÚNG MỘT workspace mặc định cho mỗi tenant, và chỉ trong số còn sống.
    # Backfill dựa vào nó: chạy lại lần hai không được tạo workspace thứ hai.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_workspaces_default_active "
    "ON workspaces (tenant_id) "
    "WHERE is_default = TRUE AND status = 'ACTIVE' AND deleted_at IS NULL",

    """
    CREATE TABLE IF NOT EXISTS projects (
        project_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id    TEXT NOT NULL,
        workspace_id UUID NOT NULL,
        name         TEXT NOT NULL,
        description  TEXT NOT NULL DEFAULT '',
        status       TEXT NOT NULL DEFAULT 'ACTIVE',
        is_default   BOOLEAN NOT NULL DEFAULT FALSE,
        created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        archived_at  TIMESTAMP WITH TIME ZONE,
        deleted_at   TIMESTAMP WITH TIME ZONE,
        CONSTRAINT ck_projects_status CHECK (%(status)s)
    )
    """ % {"status": _in_list("status", CONTAINER_STATUSES)},

    add_constraint("projects", "uq_projects_tenant_scope",
                   "UNIQUE (tenant_id, project_id)"),

    # Khoá ứng viên ba cột, cần cho `memberships` chứng minh rằng project nó
    # trỏ tới nằm đúng trong workspace mà dòng đó khai báo.
    add_constraint("projects", "uq_projects_workspace_scope",
                   "UNIQUE (tenant_id, workspace_id, project_id)"),

    # INV-TEN-02: project phải nằm trong workspace CÙNG tenant.
    add_constraint("projects", "fk_inv_ten_02_project_workspace",
                   "FOREIGN KEY (tenant_id, workspace_id)  REFERENCES workspaces (tenant_id, workspace_id) ON DELETE RESTRICT"),

    "CREATE UNIQUE INDEX IF NOT EXISTS uq_projects_workspace_name "
    "ON projects (tenant_id, workspace_id, name) WHERE deleted_at IS NULL",

    "CREATE UNIQUE INDEX IF NOT EXISTS uq_projects_default_active "
    "ON projects (tenant_id, workspace_id) "
    "WHERE is_default = TRUE AND status = 'ACTIVE' AND deleted_at IS NULL",

    "CREATE INDEX IF NOT EXISTS ix_projects_workspace ON projects (workspace_id)",
]


# ---------------------------------------------------------------------------
# 2. RBAC — nguồn sự thật
# ---------------------------------------------------------------------------

_RBAC_DDL: list[str] = [
    # `roles` đã tồn tại với hình dạng `(id, name UNIQUE, description)` và ba
    # dòng hạt giống mà — theo chú thích ở `metadata_db.py` — chưa có mã nào
    # đọc. Nó được ĐỔI HÌNH tại chỗ chứ không tạo bảng mới, vì một bảng
    # `roles_v2` bên cạnh một bảng `roles` chết là thứ sẽ còn đó ba năm nữa.
    #
    # Bọc mọi RENAME trong DO vì `ALTER ... RENAME` không có dạng IF EXISTS và
    # lượt khởi động thứ hai sẽ ném lỗi — mà `_run_ddl` chỉ ghi WARNING, nên
    # lỗi đó sẽ trở thành tiếng ồn cố định trong nhật ký mỗi lần khởi động.
    """
    DO $$ BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'roles' AND column_name = 'id'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'roles' AND column_name = 'role_id'
        ) THEN
            ALTER TABLE roles RENAME COLUMN id TO role_id;
        END IF;
    END $$
    """,
    """
    CREATE TABLE IF NOT EXISTS roles (
        role_id UUID PRIMARY KEY DEFAULT gen_random_uuid()
    )
    """,
    # v5 đổi `name` → `role_code`, và thêm `role_name` cho nhãn hiển thị. Hai
    # thứ khác nhau: `role_code` là định danh ổn định xuất hiện trong policy của
    # Casbin và trong nhật ký kiểm toán; `role_name` là thứ người dùng đọc và
    # tenant sửa được cho role của mình. Trộn hai vai vào một cột nghĩa là đổi
    # nhãn hiển thị sẽ làm gãy mọi policy đang tham chiếu tên cũ.
    """
    DO $$ BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'roles' AND column_name = 'name'
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'roles' AND column_name = 'role_code'
        ) THEN
            ALTER TABLE roles RENAME COLUMN name TO role_code;
        END IF;
    END $$
    """,
    # Bỏ cột `name` TÀN DƯ, và chỉ khi `role_code` đã có mặt.
    #
    # Điều kiện đó là toàn bộ sự an toàn của câu này: `role_code` tồn tại nghĩa
    # là lượt đổi tên ở trên ĐÃ chạy xong, nên `name` — nếu còn — là một cột
    # thứ hai không ai ghi và không ai đọc. Không có điều kiện, câu này sẽ xoá
    # đúng cột đang giữ mã role trên một máy chưa kịp đổi tên.
    #
    # Nó tồn tại vì `MIGRATION_STATEMENTS` dựng `roles(id, name, description)`
    # và chạy TRƯỚC danh sách này. Trên máy dựng từ số không, thứ tự đó đúng:
    # tạo rồi đổi tên. Nhưng nếu một lượt chạy nào đó dừng giữa chừng sau khi
    # `role_code` đã được thêm mà trước khi `name` được đổi, cả hai cột cùng
    # sống — và câu `INSERT INTO roles (name, ...)` cũ sẽ ghi vào cột chết,
    # để lại một dòng có `role_code` NULL. Đó chính là hình dạng quan sát được
    # trên bản sao sản xuất ngày 12/08/2026.
    # Điều kiện thứ BA — `role_code` phải đã được điền đủ — là thứ biến câu này
    # từ "gần như an toàn" thành an toàn.
    #
    # Hai điều kiện đầu chỉ chứng minh cả hai cột cùng tồn tại. Chúng KHÔNG
    # phân biệt được hai tình huống ngược nhau:
    #
    #   `role_code` đã có dữ liệu, `name` là bản sao chết   → bỏ `name` là đúng
    #   `role_code` vừa được thêm và còn rỗng, `name` giữ    → bỏ `name` là MẤT
    #   dữ liệu thật                                            DỮ LIỆU
    #
    # Tình huống thứ hai xảy ra được: nếu một lượt chạy dừng giữa chừng sau
    # `ADD COLUMN role_code` mà trước khi seed kịp điền. Nên câu này chỉ bỏ
    # `name` khi KHÔNG CÒN dòng nào mà `name` biết còn `role_code` thì không.
    #
    # Sai theo hướng giữ lại: một cột thừa sót lại chỉ là rác đọc bằng mắt, còn
    # một cột bị bỏ nhầm là mất mã của mọi role.
    # Phép kiểm dữ liệu nằm trong IF LỒNG và đi qua `EXECUTE`, không nằm cùng
    # biểu thức với hai phép kiểm sự tồn tại. Đây không phải chuyện thẩm mỹ:
    #
    # PostgreSQL chuẩn bị TOÀN BỘ biểu thức điều kiện như một câu lệnh, nên một
    # `... AND NOT EXISTS (SELECT ... FROM roles WHERE name IS NOT NULL)` sẽ
    # phải phân giải cột `name` NGAY CẢ KHI vế đầu đã cho biết cột đó không tồn
    # tại. Không có short-circuit ở tầng phân giải tên.
    #
    # Hậu quả nếu viết phẳng: trên mọi máy đã bỏ xong `name` — tức là trạng thái
    # bình thường sau lượt chạy đầu — câu này ném lỗi ở MỖI lần khởi động, và
    # `_run_ddl` biến nó thành một dòng WARNING vĩnh viễn. Đúng loại tiếng ồn mà
    # lượt này vừa dọn đi ba chỗ.
    #
    # `EXECUTE` hoãn việc phân giải tới lúc chạy, và nó chỉ được chạy khi nhánh
    # ngoài đã xác nhận cả hai cột cùng có mặt.
    """
    DO $$
    DECLARE
        stuck BIGINT;
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'roles' AND column_name = 'name')
           AND EXISTS (SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'roles' AND column_name = 'role_code') THEN
            EXECUTE 'SELECT count(*) FROM roles WHERE role_code IS NULL AND name IS NOT NULL'
               INTO stuck;
            IF stuck = 0 THEN
                ALTER TABLE roles DROP COLUMN name;
            END IF;
        END IF;
    END $$
    """,
    "ALTER TABLE roles ADD COLUMN IF NOT EXISTS tenant_id TEXT",
    "ALTER TABLE roles ADD COLUMN IF NOT EXISTS role_code TEXT",
    "ALTER TABLE roles ADD COLUMN IF NOT EXISTS role_name TEXT",
    "ALTER TABLE roles ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE roles ADD COLUMN IF NOT EXISTS scope_level TEXT",
    # NULL = "dùng được với mọi loại tenant". Chỉ role Community dùng giá trị
    # khác NULL, và nó là thứ ngăn `community_curator` bị gán trong một tenant
    # tổ chức — nơi role đó sẽ mang ý nghĩa hoàn toàn khác.
    "ALTER TABLE roles ADD COLUMN IF NOT EXISTS tenant_type_constraint TEXT",
    "ALTER TABLE roles ADD COLUMN IF NOT EXISTS is_builtin BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE roles ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE roles ADD COLUMN IF NOT EXISTS created_by_user_id UUID",
    "ALTER TABLE roles ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE "
    "NOT NULL DEFAULT NOW()",
    "ALTER TABLE roles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE "
    "NOT NULL DEFAULT NOW()",

    # `role_name` mặc định bằng `role_code` cho mọi dòng đã có. Không thể để
    # NULL rồi SET NOT NULL: dòng cũ sẽ chặn.
    "UPDATE roles SET role_name = role_code WHERE role_name IS NULL",

    # Đổi tên role dựng sẵn của bản v1.0 sang danh pháp v5. ĐỔI TẠI CHỖ, không
    # tạo dòng mới rồi trỏ lại.
    #
    # Đây là điểm mà một lựa chọn tưởng như tương đương lại khác nhau rất nhiều.
    # Cách kia — seed ra 14 role mới, rồi UPDATE 14 dòng gán sang `role_id`
    # mới, rồi xoá 9 role cũ — có ba bước đều có thể hỏng lẻ, và nếu hỏng ở
    # bước hai thì có người mất quyền giữa chừng. Đổi `role_code` giữ nguyên
    # `role_id`, nên mọi dòng gán, mọi dòng `role_permissions` và mọi tham
    # chiếu trong nhật ký kiểm toán vẫn trỏ đúng chỗ. Không có bước hai.
    #
    # Ánh xạ do người dùng chốt, và nguyên tắc là KHÔNG ĐỔI QUYỀN CỦA AI:
    #     platform_admin    → platform_administrator
    #     tenant_admin      → tenant_administrator
    #     workspace_manager → workspace_administrator
    #     project_manager   → project_administrator
    #     project_editor    → project_contributor
    #
    # Ba role KHÔNG đổi tên, và mỗi cái vì một lý do riêng. `tenant_viewer` từng
    # là cái thứ tư ở đây; nó không đổi tên mà đã NGHỈ HẲN — xem
    # `authorization/catalog.py::RETIRED_BUILTIN_ROLES`.
    #
    #   tenant_editor     v5 gọi vai này là `tenant_member`, nhưng "member" mô
    #                     tả TƯ CÁCH THÀNH VIÊN — thứ mà bảng `memberships` giờ
    #                     đã biểu diễn. Hai khái niệm khác nhau trùng tên là nợ
    #                     đọc hiểu vĩnh viễn. `editor` mô tả đúng cái nó cấp.
    #   workspace_viewer  giữ nguyên cả tên lẫn 7 quyền cũ. Bản trước đổi thành
    #                     `workspace_member` và nới lên 20 quyền; không ai đang
    #                     mang vai này nên không hại ai, nhưng một lượt di trú
    #                     không nên đổi ý nghĩa của role như tác dụng phụ.
    #   project_viewer    tên v5 trùng tên cũ.
    #
    # `WHERE NOT EXISTS` chống lại lượt chạy thứ hai VÀ chống lại trường hợp
    # đích đã tồn tại vì lý do khác — không có nó, câu thứ hai sẽ va vào
    # `uq_roles_builtin_code`.
    *[
        f"""
        UPDATE roles SET role_code = '{new}'
         WHERE role_code = '{old}' AND tenant_id IS NULL
           AND NOT EXISTS (SELECT 1 FROM roles x
                            WHERE x.role_code = '{new}' AND x.tenant_id IS NULL)
        """
        for old, new in (
            ("platform_admin", "platform_administrator"),
            ("tenant_admin", "tenant_administrator"),
            ("workspace_manager", "workspace_administrator"),
            ("project_manager", "project_administrator"),
            ("project_editor", "project_contributor"),
        )
    ],

    # Dọn ba dòng hạt giống cũ ('admin', 'contributor', 'guest') và mọi dòng rác
    # do vòi rò đã mô tả ở `metadata_db` (câu chèn ba role cũ mất tính idempotent
    # khi `roles_name_key` bị bỏ).
    #
    # v5 siết `ck_role_ownership` thành hai chiều: role dựng sẵn PHẢI thuộc nền
    # tảng, role tuỳ biến PHẢI thuộc một tenant. Ba dòng cũ có
    # `is_builtin = FALSE, tenant_id = NULL` nên chúng VI PHẠM ràng buộc mới —
    # phải đi trước khi ràng buộc được gắn, không thì `ALTER TABLE` thất bại và
    # `_run_ddl` nuốt lỗi, để lại một hệ không có ràng buộc đó.
    #
    # Vị từ được viết theo ĐÚNG hình dạng mà ràng buộc mới cấm, chứ không theo
    # một dấu hiệu gián tiếp. Bản đầu lọc `scope_level IS NULL` — và bản sao của
    # sản xuất bác bỏ ngay: lượt triển khai TRƯỚC đã chuẩn hoá ba dòng đó thành
    # `scope_level = 'SYSTEM'`, nên chúng không còn khớp dấu hiệu ấy nữa nhưng
    # vẫn vi phạm ràng buộc. Lọc theo chính điều kiện vi phạm thì không lệch
    # được, vì hai vế là cùng một câu.
    #
    # NHẬN NUÔI, không xoá. Đây là bản thứ ba của câu này, và hai bản trước đều
    # bị bản sao của sản xuất bác bỏ:
    #
    #   bản 1  lọc `scope_level IS NULL` → không bắt được ba dòng ấy nữa, vì
    #          lượt triển khai trước đã chuẩn hoá chúng thành 'SYSTEM'
    #   bản 2  xoá mọi dòng vi phạm mà không ai tham chiếu → va vào
    #          `users_role_id_fkey`:
    #
    #              update or delete on table "roles" violates foreign key
    #              constraint "users_role_id_fkey" on table "users"
    #
    #          Có một cột `users.role_id` từ thời trước, và 5 tài khoản đang trỏ
    #          vào 'admin' (3) và 'contributor' (2). Danh sách "ai tham chiếu"
    #          mà bản 2 dựng lên đã BỎ SÓT nó — và cách duy nhất để không bỏ sót
    #          là không cần danh sách đó nữa.
    #
    # Nên: đổi dòng cho HỢP LỆ thay vì loại nó. `is_builtin = TRUE` với
    # `tenant_id IS NULL` thoả `ck_role_ownership`; `is_active = FALSE` giữ nó
    # ngoài phép chiếu của Casbin (adapter lọc theo cột này). Không khoá ngoại
    # nào gãy, không dòng nào mất, và không có danh sách tham chiếu nào để quên.
    #
    # Vì sao trước đây phải xoá mà giờ thì không: vòi rò sinh ra dòng rác là câu
    # seed cũ mất tính idempotent khi `roles_name_key` bị bỏ. Giờ đã có
    # `uq_roles_builtin_code` chặn đúng lớp lỗi đó ở tầng schema, nên số dòng
    # loại này bị chặn trên, không còn tích luỹ.
    "UPDATE roles SET is_builtin = TRUE, is_active = FALSE, "
    "role_name = COALESCE(role_name, role_code) "
    "WHERE tenant_id IS NULL AND NOT is_builtin",

    # Ràng buộc UNIQUE toàn cục cũ trên `name` phải đi. Nó bắt tên role là duy
    # nhất trên TOÀN nền tảng, tức là tenant "ctu" đặt một role tên "Editor" sẽ
    # chặn mọi tenant khác dùng đúng cái tên hiển nhiên đó. Tên role thuộc về
    # không gian tên của tenant, không phải của nền tảng.
    "ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_name_key",

    add_constraint("roles", "ck_roles_scope_level",
                   "CHECK (%s)" % _in_list("scope_level", SCOPE_LEVELS)),
    add_constraint("roles", "ck_roles_tenant_type_constraint",
                   "CHECK (tenant_type_constraint IS NULL OR %s)"
                   % _in_list("tenant_type_constraint", TENANT_TYPES)),

    # v5 §3/§4, và đây là ràng buộc quan trọng nhất của toàn tệp.
    #
    # Chiều thứ nhất — role dựng sẵn thuộc nền tảng. Một bản sao `tenant_admin`
    # do tenant sở hữu sẽ sửa được bởi chính tenant đó, tức là tenant tự viết
    # lại định nghĩa của role mà nền tảng cung cấp.
    #
    # Chiều thứ hai — role tuỳ biến PHẢI có chủ và KHÔNG được ở phạm vi SYSTEM.
    # `tenant_id IS NULL AND is_builtin = FALSE` là hình dạng của một role không
    # ai quản lý; `scope_level = 'SYSTEM'` do tenant sở hữu là tenant tự cấp cho
    # mình quyền toàn nền tảng.
    #
    # Bản v1.0 chỉ có chiều thứ nhất, dạng nới hơn (`scope_level <> 'SYSTEM' OR
    # tenant_id IS NULL`). Nó cho phép đúng cái dòng rác vừa bị xoá ở trên tồn
    # tại, và đó là lý do chúng tồn tại được tới lúc bị phát hiện trên sản xuất.
    add_constraint("roles", "ck_role_ownership",
                   "CHECK ((is_builtin AND tenant_id IS NULL) "
                   "OR (NOT is_builtin AND tenant_id IS NOT NULL "
                   "AND scope_level <> 'SYSTEM'))"),

    # Tính duy nhất của mã, tách làm hai chỉ mục từng phần thay vì một ràng
    # buộc `UNIQUE NULLS NOT DISTINCT`. Cái sau chỉ có từ PostgreSQL 15, và
    # dùng nó nghĩa là schema âm thầm khác nhau giữa hai máy tuỳ theo phiên bản
    # — đúng loại lệch mà `verify_deployment` tồn tại để bắt.
    #
    # v5 làm `role_code` của role dựng sẵn duy nhất TOÀN CỤC chứ không theo
    # phạm vi. Chặt hơn bản v1.0, và đúng: `role_code` xuất hiện trần trong
    # policy của Casbin, nên hai role khác phạm vi mà trùng mã sẽ là hai dòng
    # policy không phân biệt được.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_roles_builtin_code "
    "ON roles (role_code) WHERE tenant_id IS NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_roles_custom_code "
    "ON roles (tenant_id, role_code) WHERE tenant_id IS NOT NULL",

    add_constraint("roles", "fk_roles_tenant",
                   "FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id) ON DELETE CASCADE"),
    add_constraint("roles", "fk_roles_creator",
                   "FOREIGN KEY (created_by_user_id) REFERENCES users (id) ON DELETE SET NULL"),

    # ------------------------------------------------------------------
    # Danh mục quyền. Không thuộc tenant nào và không tenant nào ghi được:
    # thêm một năng lực là thay đổi mã nguồn (phải có endpoint kiểm nó), nên
    # nó đi qua seed chứ không qua API.
    #
    # Khoá chính là chính MÃ quyền chứ không phải UUID. `sample.delete` đã là
    # định danh ổn định, đọc được trong nhật ký kiểm toán, và xuất hiện nguyên
    # văn trong policy của Casbin — thêm một UUID ở giữa chỉ tạo thêm một phép
    # nối cho mọi truy vấn mà không mua được gì.
    """
    CREATE TABLE IF NOT EXISTS permissions (
        permission_code   TEXT PRIMARY KEY,
        description       TEXT NOT NULL DEFAULT '',
        applicable_scope  TEXT NOT NULL,
        risk_level        TEXT NOT NULL DEFAULT 'NORMAL',
        requires_passcode BOOLEAN NOT NULL DEFAULT FALSE,
        is_api_assignable BOOLEAN NOT NULL DEFAULT FALSE,
        is_active         BOOLEAN NOT NULL DEFAULT TRUE,
        created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT ck_permissions_scope CHECK (%(scope)s),
        CONSTRAINT ck_permissions_risk CHECK (risk_level IN ('NORMAL', 'SENSITIVE', 'CRITICAL')),
        CONSTRAINT ck_permissions_code_shape CHECK (permission_code ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$')
    )
    """ % {"scope": _in_list("applicable_scope", SCOPE_LEVELS)},

    # v5 §4/§6: quyền nào được phép nằm trong một role do tenant tự tạo.
    #
    # Mặc định TRUE là chủ ý và đáng nói: nó có nghĩa là một quyền THÊM MỚI vào
    # danh mục sẽ tự động cấp được cho custom role trừ khi tác giả nói khác.
    # Hướng ngược lại (mặc định FALSE) an toàn hơn về lý thuyết nhưng hỏng theo
    # kiểu khó thấy — một quyền nghiệp vụ bình thường bị bỏ quên sẽ không xuất
    # hiện trong trình tạo role, và triệu chứng là "tenant không tự cấu hình
    # được thứ họ nhìn thấy trong tài liệu".
    #
    # Cái bảo vệ thật không phải là giá trị mặc định mà là ràng buộc bên dưới:
    # quyền SYSTEM KHÔNG BAO GIỜ cấp được cho custom role, bất kể cột này.
    "ALTER TABLE permissions ADD COLUMN IF NOT EXISTS is_custom_role_allowed "
    "BOOLEAN NOT NULL DEFAULT TRUE",

    # Bắt buộc, và phải chạy TRƯỚC ràng buộc bên dưới. `ADD COLUMN ... DEFAULT
    # TRUE` điền TRUE cho mọi dòng đã có, kể cả 13 quyền phạm vi SYSTEM — nên
    # ngay giây tiếp theo, `ck_permissions_system_not_custom_role` bị vi phạm
    # bởi chính dữ liệu mà câu ALTER vừa tạo ra.
    #
    # Bản sao của sản xuất bắt được đúng điều này. Nó không phải lỗi lý thuyết:
    # `_run_ddl` nuốt lỗi, nên trên hệ thật ràng buộc sẽ đơn giản KHÔNG tồn tại
    # và không ai biết, cho tới khi một tenant gắn `platform.tenant.purge` vào
    # role tự tạo của họ.
    "UPDATE permissions SET is_custom_role_allowed = FALSE "
    "WHERE applicable_scope = 'SYSTEM' AND is_custom_role_allowed",

    # Quyền phạm vi SYSTEM không bao giờ được cấp cho khoá API của tenant.
    add_constraint("permissions", "ck_permissions_system_not_api_assignable",
                   "CHECK (NOT (applicable_scope = 'SYSTEM' AND is_api_assignable))"),

    # ... và cũng không bao giờ vào được một role do tenant tự tạo. Hai đường
    # khác nhau tới cùng một đích (tenant cầm quyền nền tảng), nên cần hai
    # ràng buộc; cái trên chặn đường khoá API, cái này chặn đường custom role.
    add_constraint("permissions", "ck_permissions_system_not_custom_role",
                   "CHECK (NOT (applicable_scope = 'SYSTEM' AND is_custom_role_allowed))"),

    """
    CREATE TABLE IF NOT EXISTS role_permissions (
        role_id         UUID NOT NULL,
        permission_code TEXT NOT NULL,
        granted_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CONSTRAINT pk_role_permissions PRIMARY KEY (role_id, permission_code),
        CONSTRAINT fk_role_permissions_role
            FOREIGN KEY (role_id) REFERENCES roles (role_id) ON DELETE CASCADE,
        CONSTRAINT fk_role_permissions_permission
            FOREIGN KEY (permission_code) REFERENCES permissions (permission_code)
            ON UPDATE CASCADE ON DELETE RESTRICT
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_role_permissions_permission "
    "ON role_permissions (permission_code)",
]


# ---------------------------------------------------------------------------
# 3. Membership hợp nhất
# ---------------------------------------------------------------------------

#: Ba cột vòng đời trên bảng CŨ `tenant_members`, thêm trước khi gộp.
#:
#: Vì sao chúng phải sống ở ĐÂY chứ không ở đâu khác
#: --------------------------------------------------
#: Máy đang chạy CÓ ba cột này; máy cài mới thì KHÔNG. Không tệp nào trong kho
#: tạo ra chúng — phiên bản mã từng làm việc đó đã bị gỡ trong lượt viết lại v5,
#: và chỉ còn dấu vết là `REQUIRED_COLUMNS` canh chúng. Kết quả là một lệch
#: lược đồ im lặng theo đúng hướng tệ nhất: `_MIGRATE_MEMBERSHIPS` đọc
#: `tm.status`, ngã với `UndefinedColumn`, `_run_ddl` nuốt lỗi, và lượt gộp
#: KHÔNG BAO GIỜ chạy. Bảng cũ ở lại, view không được dựng, và mọi thứ phía sau
#: chạy trên một mặt phẳng phân quyền dở dang mà `healthy` vẫn xanh.
#:
#: Đo được trên một cơ sở dữ liệu dựng từ số không 11/08/2026: đúng một dòng
#: `authz statement failed (ignored): column tm.status does not exist`, và không
#: gì khác chỉ ra rằng cả lượt di trú đã không xảy ra.
#:
#: Phải chạy TRƯỚC `_DATA_MIGRATION_DDL`, và có canh `pg_tables`: sau lượt gộp
#: đầu tiên `tenant_members` là VIEW, và `ALTER TABLE` trên view là lỗi ở mọi
#: lần khởi động về sau.
_LEGACY_MEMBER_COLUMNS_DDL: list[str] = [
    """
    DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_tables
                        WHERE schemaname = current_schema()
                          AND tablename = 'tenant_members') THEN
            RETURN;
        END IF;

        ALTER TABLE tenant_members
            ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'ACTIVE';
        ALTER TABLE tenant_members
            ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMP WITH TIME ZONE;
        ALTER TABLE tenant_members
            ADD COLUMN IF NOT EXISTS removed_at TIMESTAMP WITH TIME ZONE;

        -- Cùng hai ràng buộc mà máy đang chạy có. Thiếu chúng, một dòng
        -- `status='REMOVED'` với `removed_at IS NULL` là hợp lệ — và adapter
        -- (lọc theo CẢ HAI) sẽ loại nó trong khi giao diện (lọc một cái) vẫn
        -- hiện. Hai câu trả lời cho một câu hỏi.
        IF NOT EXISTS (SELECT 1 FROM pg_constraint
                        WHERE conname = 'tenant_members_status_valid') THEN
            ALTER TABLE tenant_members ADD CONSTRAINT tenant_members_status_valid
                CHECK (status IN ('ACTIVE', 'INVITED', 'SUSPENDED', 'REMOVED'));
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint
                        WHERE conname = 'tenant_members_removed_consistent') THEN
            ALTER TABLE tenant_members ADD CONSTRAINT tenant_members_removed_consistent
                CHECK ((status = 'REMOVED') = (removed_at IS NOT NULL));
        END IF;
    END $$
    """,
]

_MEMBERSHIP_DDL: list[str] = [
    # v5 §2. Một bảng cho cả ba mức, phân biệt bằng `scope_level`.
    #
    # `scope_level` có DEFAULT 'TENANT', và đó KHÔNG phải sự tuỳ tiện: nó là thứ
    # làm cho view `tenant_members` bên dưới chèn được. Một câu
    # `INSERT INTO tenant_members (tenant_id, user_id, role)` đi qua view không
    # nêu `scope_level` — với view cập nhật được, cột không nêu lấy DEFAULT của
    # BẢNG NỀN. Chèn workspace/project luôn nêu `scope_level` tường minh nên
    # mặc định này không chạm tới chúng.
    #
    # `legacy_role` là cột CHUYỂN TIẾP, không thuộc v5. Nó là vế "cũ" của phép
    # so sánh trong shadow mode và 15 tệp còn đọc nó. Xoá nó bây giờ là vừa đổi
    # kiến trúc vừa vứt đi thứ duy nhất chứng minh kiến trúc mới cho cùng kết
    # quả. Nó đi ở Phase D.
    #
    # BA trạng thái, không phải ba giá trị: 'admin', 'editor', và NULL. Giá trị
    # thứ ba cũ — 'viewer' — đã nghỉ cùng role dựng sẵn `tenant_viewer`, và cột
    # này KHÔNG còn mặc định. Tư cách thành viên và vai là hai chuyện: một người
    # có membership TENANT đang hoạt động mà `legacy_role IS NULL` là hợp lệ, và
    # nghĩa là "chưa có vai nào ở tầng tenant" — họ nhận quyền qua assignment ở
    # workspace/project, hoặc qua role tự tạo của tổ chức.
    #
    # Bỏ `DEFAULT 'viewer'` là chỗ dễ hiểu nhầm nhất trong lượt này. Mặc định đó
    # từng được ghi là "cần thiết để view `tenant_members` chèn được" — không
    # đúng: câu chèn qua view NÊU TÊN cột `role`, nên nó luôn cấp giá trị. Cái
    # mặc định chỉ chạm tới câu chèn KHÔNG nêu vai, và với những câu đó, NULL
    # mới là câu trả lời đúng. `scope_level` thì khác — mặc định của nó thật sự
    # cần, xem chú thích ngay trên.
    """
    CREATE TABLE IF NOT EXISTS memberships (
        membership_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id              UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
        scope_level          TEXT NOT NULL DEFAULT 'TENANT',
        tenant_id            TEXT NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
        workspace_id         UUID,
        project_id           UUID,
        parent_membership_id UUID,
        legacy_role          TEXT,
        status               TEXT NOT NULL DEFAULT 'ACTIVE',
        joined_at            TIMESTAMP WITH TIME ZONE,
        suspended_at         TIMESTAMP WITH TIME ZONE,
        left_at              TIMESTAMP WITH TIME ZONE,
        created_at           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

        CONSTRAINT ck_memberships_scope_level CHECK (%(scope)s),
        CONSTRAINT ck_memberships_status CHECK (%(status)s),

        -- v5 §2: hình dạng của mỗi mức. Đây là thứ thay cho việc có ba bảng —
        -- không có nó, một dòng WORKSPACE thiếu `workspace_id` là hợp lệ và
        -- mọi truy vấn theo workspace sẽ lặng lẽ bỏ sót nó.
        CONSTRAINT ck_memberships_shape CHECK (
            (scope_level = 'TENANT'    AND workspace_id IS NULL     AND project_id IS NULL)
         OR (scope_level = 'WORKSPACE' AND workspace_id IS NOT NULL AND project_id IS NULL)
         OR (scope_level = 'PROJECT'   AND workspace_id IS NOT NULL AND project_id IS NOT NULL)
        ),

        -- `status` và `left_at` phải kể cùng một câu chuyện. Không có ràng buộc
        -- này, một dòng `status='ACTIVE'` với `left_at` đã điền là hợp lệ — và
        -- truy vấn của adapter (lọc theo CẢ HAI) sẽ loại nó, trong khi giao
        -- diện quản trị (lọc theo một cái) vẫn hiện. Hai câu trả lời cho một
        -- câu hỏi, và cái sai là cái người dùng nhìn thấy.
        CONSTRAINT ck_memberships_left_consistent
            CHECK ((status = 'REMOVED') = (left_at IS NOT NULL)),

        -- Chỉ membership TENANT mang vai cũ. Một dòng WORKSPACE có
        -- `legacy_role = 'admin'` sẽ làm view `tenant_members` — vốn lọc theo
        -- scope — vẫn đúng, nhưng nó là dữ liệu vô nghĩa mời gọi người đọc sau
        -- này tin rằng vai cũ có ý nghĩa ở mọi mức.
        CONSTRAINT ck_memberships_legacy_role_tenant_only
            CHECK (scope_level = 'TENANT' OR legacy_role IS NULL),

        -- Hai giá trị và NULL. `_LEGACY_ROLE_RETIREMENT_DDL` gắn cùng ràng buộc
        -- này cho những cơ sở dữ liệu đã có `memberships` từ trước lượt gỡ
        -- `tenant_viewer`; ở đây nó có mặt để một máy cài mới không phải đợi
        -- bước sửa mới đúng hình.
        CONSTRAINT ck_memberships_legacy_role_valid
            CHECK (legacy_role IS NULL OR legacy_role IN ('admin', 'editor'))
    )
    """ % {
        "scope": _in_list("scope_level", ("TENANT", "WORKSPACE", "PROJECT")),
        "status": _in_list("status", MEMBER_STATUSES),
    },

    # Khoá ứng viên cho `role_assignments(membership_id, user_id)`. Đây là thứ
    # v5 §5 gọi là "an assignment cannot point at a membership owned by another
    # user": không có nó, `role_assignments` chỉ kiểm được `membership_id` tồn
    # tại, và một dòng gán có thể nói "người A giữ role qua membership của
    # người B" — cả hai đều là dòng có thật, khoá ngoại không phản đối.
    add_constraint("memberships", "uq_memberships_id_user",
                   "UNIQUE (membership_id, user_id)"),

    # Cây phân cấp membership. Khoá ngoại GHÉP với `user_id` chứ không chỉ
    # `parent_membership_id`: nó đồng thời chứng minh cha thuộc CÙNG MỘT NGƯỜI.
    # Chỉ `parent_membership_id` thì tư cách thành viên workspace của người A có
    # thể treo dưới tư cách thành viên tenant của người B.
    add_constraint("memberships", "fk_memberships_parent",
                   "FOREIGN KEY (parent_membership_id, user_id)  "
                   "REFERENCES memberships (membership_id, user_id) ON DELETE CASCADE"),

    # Workspace/project phải thuộc đúng tenant của dòng này. Cột NULL làm khoá
    # ngoại ghép (MATCH SIMPLE) tự thoả, nên dòng TENANT không bị hai ràng buộc
    # này chạm tới — đúng như mong muốn.
    add_constraint("memberships", "fk_memberships_workspace",
                   "FOREIGN KEY (tenant_id, workspace_id)  "
                   "REFERENCES workspaces (tenant_id, workspace_id) ON DELETE CASCADE"),
    add_constraint("memberships", "fk_memberships_project",
                   "FOREIGN KEY (tenant_id, workspace_id, project_id)  "
                   "REFERENCES projects (tenant_id, workspace_id, project_id) ON DELETE CASCADE"),

    # Tính duy nhất theo từng mức.
    #
    # KHÁC v5 một cách có chủ ý: v5 lọc thêm `status = 'ACTIVE'`, cho phép nhiều
    # dòng đã rời đi cho cùng một (người, phạm vi). Ở đây KHÔNG lọc theo trạng
    # thái, vì bảng cũ `tenant_members` có khoá chính `(tenant_id, user_id)` —
    # nhiều nhất một dòng cho mỗi cặp, bất kể trạng thái.
    #
    # 15 tệp còn viết `SELECT ... WHERE tenant_id = ? AND user_id = ?` và mong
    # đợi 0 hoặc 1 dòng. Nới sang bản v5 trong cùng lượt gộp bảng sẽ làm những
    # truy vấn đó trả về 2 dòng sau lần rời-rồi-vào-lại đầu tiên, và triệu chứng
    # sẽ xuất hiện hàng tháng sau ở một chỗ không liên quan. Chặt hơn thì an
    # toàn; nới ra là một câu migration có chủ đích cho Phase D.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_memberships_tenant_user "
    "ON memberships (tenant_id, user_id) WHERE scope_level = 'TENANT'",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_memberships_workspace_user "
    "ON memberships (tenant_id, workspace_id, user_id) WHERE scope_level = 'WORKSPACE'",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_memberships_project_user "
    "ON memberships (tenant_id, project_id, user_id) WHERE scope_level = 'PROJECT'",

    "CREATE INDEX IF NOT EXISTS ix_memberships_user ON memberships (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_memberships_tenant_scope "
    "ON memberships (tenant_id, scope_level)",
]


# ---------------------------------------------------------------------------
# 4. Lịch sử gán role — một bảng cho cả bốn phạm vi
# ---------------------------------------------------------------------------

_ASSIGNMENT_DDL: list[str] = [
    # v5 §5. Khoá thay thế `assignment_id` chứ không phải khoá tự nhiên
    # `(user, role)`. Lý do là một chuỗi rất bình thường: cấp → thu hồi → cấp
    # lại. Với khoá tự nhiên, lần cấp thứ hai phải GHI ĐÈ dòng cũ và lịch sử lần
    # thu hồi biến mất. Với khoá thay thế, ba lần đó là ba dòng, và chỉ mục duy
    # nhất TỪNG PHẦN (`WHERE revoked_at IS NULL`) giữ cho "đang hiệu lực" vẫn là
    # duy nhất.
    #
    # `membership_id IS NULL` nghĩa là gán ở phạm vi SYSTEM — người giữ role này
    # hành động thay cho nền tảng, không thay cho tenant nào, nên không có
    # membership để treo vào.
    #
    # `assigned_by_user_id` là NOT NULL và `ON DELETE RESTRICT`. Đó là chủ ý:
    # một dòng nói "ai đó được cấp quyền, không rõ ai cấp" thì vô dụng đúng lúc
    # cần nó nhất. Nếu tài khoản người cấp phải bị xoá, dòng gán phải được thu
    # hồi trước — và điều đó đúng, vì quyền do một người đã rời đi cấp thì nên
    # được xem lại chứ không nên tự động ở lại.
    """
    CREATE TABLE IF NOT EXISTS role_assignments (
        assignment_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id             UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
        role_id             UUID NOT NULL REFERENCES roles (role_id) ON DELETE RESTRICT,
        membership_id       UUID,
        assigned_by_user_id UUID NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
        assigned_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        revoked_by_user_id  UUID REFERENCES users (id) ON DELETE SET NULL,
        revoked_at          TIMESTAMP WITH TIME ZONE,
        revoke_reason       TEXT,

        -- Không thể có người thu hồi mà không có lúc thu hồi. Chiều ngược lại
        -- thì được: `revoked_by_user_id` là ON DELETE SET NULL, nên một lần
        -- thu hồi do tài khoản đã bị xoá thực hiện vẫn giữ nguyên `revoked_at`.
        CONSTRAINT ck_role_assignments_revoked_consistent
            CHECK (revoked_by_user_id IS NULL OR revoked_at IS NOT NULL)
    )
    """,

    # Khoá ngoại GHÉP — xem `uq_memberships_id_user`. Đây là bất biến v5 §5.
    add_constraint("role_assignments", "fk_role_assignments_membership",
                   "FOREIGN KEY (membership_id, user_id)  "
                   "REFERENCES memberships (membership_id, user_id) ON DELETE CASCADE"),

    # Hai chỉ mục, vì "đang hiệu lực" có hai hình dạng. Gộp làm một
    # (`COALESCE(membership_id, ...)`) sẽ mất tính dùng được của chỉ mục cho
    # truy vấn thường và không đơn giản hơn chút nào.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_role_assignments_scoped "
    "ON role_assignments (membership_id, role_id) "
    "WHERE membership_id IS NOT NULL AND revoked_at IS NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_role_assignments_system "
    "ON role_assignments (user_id, role_id) "
    "WHERE membership_id IS NULL AND revoked_at IS NULL",

    "CREATE INDEX IF NOT EXISTS ix_role_assignments_user ON role_assignments (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_role_assignments_role ON role_assignments (role_id)",
    "CREATE INDEX IF NOT EXISTS ix_role_assignments_membership "
    "ON role_assignments (membership_id) WHERE membership_id IS NOT NULL",
]


# ---------------------------------------------------------------------------
# 5. Di trú dữ liệu từ hình dạng v1.0 (8 bảng) sang v5 (2 bảng)
# ---------------------------------------------------------------------------
#
# Chạy MỘT LẦN, và tự biết mình đã chạy: mỗi câu chỉ chép dòng chưa có mặt ở
# đích. Chạy lại là no-op, không phải lỗi — điều bắt buộc vì `ensure_tables()`
# chạy ở mỗi lần khởi động của mỗi worker.
#
# Vì sao là DO block chứ không phải câu INSERT trần: bảng nguồn KHÔNG TỒN TẠI
# trên máy cài mới. Một câu SQL tham chiếu bảng không có sẽ hỏng lúc PARSE, tức
# là trước khi bất kỳ `NOT EXISTS` nào kịp chạy. `to_regclass` + `EXECUTE` hoãn
# việc phân giải tên tới lúc chạy.

_MIGRATE_MEMBERSHIPS = """
DO $$
BEGIN
    -- 1. tenant_members → memberships (TENANT).
    --    Chỉ khi `tenant_members` còn là BẢNG. Sau lượt di trú đầu nó là VIEW
    --    trên chính `memberships`, và chép từ view vào bảng nền là vòng lặp.
    IF EXISTS (SELECT 1 FROM pg_tables
                WHERE schemaname = current_schema() AND tablename = 'tenant_members') THEN
        INSERT INTO memberships (user_id, scope_level, tenant_id, legacy_role,
                                 status, joined_at, suspended_at, left_at, created_at)
        SELECT tm.user_id, 'TENANT', tm.tenant_id, tm.role,
               tm.status, tm.created_at, tm.suspended_at, tm.removed_at, tm.created_at
          FROM tenant_members tm
         WHERE NOT EXISTS (
                   SELECT 1 FROM memberships m
                    WHERE m.scope_level = 'TENANT'
                      AND m.tenant_id = tm.tenant_id AND m.user_id = tm.user_id);
    END IF;

    -- 2. workspace_members → memberships (WORKSPACE), treo dưới membership
    --    TENANT của cùng người. `parent_membership_id` không suy ra được sau
    --    này nếu bỏ qua ở đây, nên nó được nối ngay trong câu chép.
    IF to_regclass('workspace_members') IS NOT NULL THEN
        -- `legacy_role` nêu NULL TƯỜNG MINH. Cột không còn `DEFAULT 'viewer'`
        -- (nó nghỉ cùng `tenant_viewer`), nên hôm nay bỏ tên cột đi cũng cho ra
        -- NULL — nhưng dựa vào điều đó là dựa vào việc cột KHÔNG có mặc định,
        -- và một mặc định thêm lại sau này sẽ lặng lẽ tạo ra dòng WORKSPACE
        -- mang vai cũ. `ck_memberships_legacy_role_tenant_only` từ chối, và vì
        -- cả khối DO là một giao dịch, nó kéo đổ luôn phần đã chép ở bước 1.
        -- Bản sao của sản xuất bắt được đúng chuỗi này hồi cột còn mặc định.
        INSERT INTO memberships (user_id, scope_level, tenant_id, workspace_id,
                                 parent_membership_id, legacy_role,
                                 status, joined_at, left_at, created_at)
        SELECT wm.user_id, 'WORKSPACE', wm.tenant_id, wm.workspace_id,
               parent.membership_id, NULL,
               wm.status, wm.created_at, wm.removed_at, wm.created_at
          FROM workspace_members wm
          JOIN memberships parent
            ON parent.scope_level = 'TENANT'
           AND parent.tenant_id = wm.tenant_id
           AND parent.user_id = wm.user_id
         WHERE NOT EXISTS (
                   SELECT 1 FROM memberships m
                    WHERE m.scope_level = 'WORKSPACE'
                      AND m.tenant_id = wm.tenant_id
                      AND m.workspace_id = wm.workspace_id
                      AND m.user_id = wm.user_id);
    END IF;

    -- 3. project_members → memberships (PROJECT), treo dưới membership
    --    WORKSPACE tương ứng.
    IF to_regclass('project_members') IS NOT NULL THEN
        INSERT INTO memberships (user_id, scope_level, tenant_id, workspace_id, project_id,
                                 parent_membership_id, legacy_role,
                                 status, joined_at, left_at, created_at)
        SELECT pm.user_id, 'PROJECT', pm.tenant_id, pm.workspace_id, pm.project_id,
               parent.membership_id, NULL,
               pm.status, pm.created_at, pm.removed_at, pm.created_at
          FROM project_members pm
          JOIN memberships parent
            ON parent.scope_level = 'WORKSPACE'
           AND parent.tenant_id = pm.tenant_id
           AND parent.workspace_id = pm.workspace_id
           AND parent.user_id = pm.user_id
         WHERE NOT EXISTS (
                   SELECT 1 FROM memberships m
                    WHERE m.scope_level = 'PROJECT'
                      AND m.tenant_id = pm.tenant_id
                      AND m.project_id = pm.project_id
                      AND m.user_id = pm.user_id);
    END IF;
END $$
"""

_MIGRATE_ASSIGNMENTS = """
DO $$
BEGIN
    -- Gán SYSTEM: `membership_id` NULL.
    IF to_regclass('system_user_roles') IS NOT NULL THEN
        INSERT INTO role_assignments (assignment_id, user_id, role_id, membership_id,
                                      assigned_by_user_id, assigned_at,
                                      revoked_by_user_id, revoked_at, revoke_reason)
        SELECT s.assignment_id, s.user_id, s.role_id, NULL,
               s.assigned_by_user_id, s.assigned_at,
               s.revoked_by_user_id, s.revoked_at, s.revoke_reason
          FROM system_user_roles s
         WHERE NOT EXISTS (SELECT 1 FROM role_assignments r
                            WHERE r.assignment_id = s.assignment_id);
    END IF;

    -- Gán TENANT/WORKSPACE/PROJECT: nối sang `memberships` để lấy
    -- `membership_id`. `assignment_id` được GIỮ NGUYÊN, không sinh mới — nhật
    -- ký kiểm toán và mọi tham chiếu ngoài đều nói về id đó.
    IF to_regclass('tenant_member_roles') IS NOT NULL THEN
        INSERT INTO role_assignments (assignment_id, user_id, role_id, membership_id,
                                      assigned_by_user_id, assigned_at,
                                      revoked_by_user_id, revoked_at, revoke_reason)
        SELECT t.assignment_id, t.user_id, t.role_id, m.membership_id,
               t.assigned_by_user_id, t.assigned_at,
               t.revoked_by_user_id, t.revoked_at, t.revoke_reason
          FROM tenant_member_roles t
          JOIN memberships m
            ON m.scope_level = 'TENANT'
           AND m.tenant_id = t.tenant_id AND m.user_id = t.user_id
         WHERE NOT EXISTS (SELECT 1 FROM role_assignments r
                            WHERE r.assignment_id = t.assignment_id);
    END IF;

    IF to_regclass('workspace_member_roles') IS NOT NULL THEN
        INSERT INTO role_assignments (assignment_id, user_id, role_id, membership_id,
                                      assigned_by_user_id, assigned_at,
                                      revoked_by_user_id, revoked_at, revoke_reason)
        SELECT w.assignment_id, w.user_id, w.role_id, m.membership_id,
               w.assigned_by_user_id, w.assigned_at,
               w.revoked_by_user_id, w.revoked_at, w.revoke_reason
          FROM workspace_member_roles w
          JOIN memberships m
            ON m.scope_level = 'WORKSPACE'
           AND m.tenant_id = w.tenant_id AND m.workspace_id = w.workspace_id
           AND m.user_id = w.user_id
         WHERE NOT EXISTS (SELECT 1 FROM role_assignments r
                            WHERE r.assignment_id = w.assignment_id);
    END IF;

    IF to_regclass('project_member_roles') IS NOT NULL THEN
        INSERT INTO role_assignments (assignment_id, user_id, role_id, membership_id,
                                      assigned_by_user_id, assigned_at,
                                      revoked_by_user_id, revoked_at, revoke_reason)
        SELECT p.assignment_id, p.user_id, p.role_id, m.membership_id,
               p.assigned_by_user_id, p.assigned_at,
               p.revoked_by_user_id, p.revoked_at, p.revoke_reason
          FROM project_member_roles p
          JOIN memberships m
            ON m.scope_level = 'PROJECT'
           AND m.tenant_id = p.tenant_id AND m.project_id = p.project_id
           AND m.user_id = p.user_id
         WHERE NOT EXISTS (SELECT 1 FROM role_assignments r
                            WHERE r.assignment_id = p.assignment_id);
    END IF;
END $$
"""

#: Bỏ các bảng cũ SAU khi đã chép, và chỉ khi đã chép ĐỦ.
#:
#: Câu đếm là điều kiện, không phải trang trí. `_run_ddl` nuốt lỗi: nếu câu chép
#: ở trên thất bại một phần (một dòng vi phạm ràng buộc mới, chẳng hạn), bỏ bảng
#: nguồn sẽ XOÁ VĨNH VIỄN phần chưa chép được. Với `RAISE EXCEPTION`, lượt khởi
#: động để lại một WARNING và bảng cũ nguyên vẹn — hỏng theo hướng giữ dữ liệu.
_DROP_LEGACY_MEMBERSHIP_TABLES = """
DO $$
DECLARE
    src BIGINT;
    dst BIGINT;
BEGIN
    IF to_regclass('workspace_member_roles') IS NOT NULL THEN
        SELECT count(*) INTO src FROM workspace_member_roles;
        SELECT count(*) INTO dst FROM role_assignments ra
          JOIN memberships m ON m.membership_id = ra.membership_id
         WHERE m.scope_level = 'WORKSPACE';
        IF dst < src THEN
            RAISE EXCEPTION 'di tru workspace_member_roles chua du: % / %', dst, src;
        END IF;
        DROP TABLE workspace_member_roles;
    END IF;

    IF to_regclass('project_member_roles') IS NOT NULL THEN
        SELECT count(*) INTO src FROM project_member_roles;
        SELECT count(*) INTO dst FROM role_assignments ra
          JOIN memberships m ON m.membership_id = ra.membership_id
         WHERE m.scope_level = 'PROJECT';
        IF dst < src THEN
            RAISE EXCEPTION 'di tru project_member_roles chua du: % / %', dst, src;
        END IF;
        DROP TABLE project_member_roles;
    END IF;

    IF to_regclass('tenant_member_roles') IS NOT NULL THEN
        SELECT count(*) INTO src FROM tenant_member_roles;
        SELECT count(*) INTO dst FROM role_assignments ra
          JOIN memberships m ON m.membership_id = ra.membership_id
         WHERE m.scope_level = 'TENANT';
        IF dst < src THEN
            RAISE EXCEPTION 'di tru tenant_member_roles chua du: % / %', dst, src;
        END IF;
        DROP TABLE tenant_member_roles;
    END IF;

    IF to_regclass('system_user_roles') IS NOT NULL THEN
        SELECT count(*) INTO src FROM system_user_roles;
        SELECT count(*) INTO dst FROM role_assignments WHERE membership_id IS NULL;
        IF dst < src THEN
            RAISE EXCEPTION 'di tru system_user_roles chua du: % / %', dst, src;
        END IF;
        DROP TABLE system_user_roles;
    END IF;

    IF to_regclass('project_members') IS NOT NULL THEN
        SELECT count(*) INTO src FROM project_members;
        SELECT count(*) INTO dst FROM memberships WHERE scope_level = 'PROJECT';
        IF dst < src THEN
            RAISE EXCEPTION 'di tru project_members chua du: % / %', dst, src;
        END IF;
        DROP TABLE project_members;
    END IF;

    IF to_regclass('workspace_members') IS NOT NULL THEN
        SELECT count(*) INTO src FROM workspace_members;
        SELECT count(*) INTO dst FROM memberships WHERE scope_level = 'WORKSPACE';
        IF dst < src THEN
            RAISE EXCEPTION 'di tru workspace_members chua du: % / %', dst, src;
        END IF;
        DROP TABLE workspace_members;
    END IF;

    -- `tenant_members` đi CUỐI: hai bảng vừa bỏ ở trên có khoá ngoại trỏ vào
    -- nó, và một bảng còn người tham chiếu thì không DROP được.
    IF EXISTS (SELECT 1 FROM pg_tables
                WHERE schemaname = current_schema() AND tablename = 'tenant_members') THEN
        SELECT count(*) INTO src FROM tenant_members;
        SELECT count(*) INTO dst FROM memberships WHERE scope_level = 'TENANT';
        IF dst < src THEN
            RAISE EXCEPTION 'di tru tenant_members chua du: % / %', dst, src;
        END IF;
        DROP TABLE tenant_members;
    END IF;
END $$
"""

#: View tương thích. Xem docstring module về vì sao nó tồn tại.
#:
#: `security_invoker = true` là bắt buộc, không phải tuỳ chọn. Không có nó,
#: view chạy dưới quyền của CHỦ SỞ HỮU và RLS trên `memberships` bị BỎ QUA —
#: mọi tenant đọc được thành viên của mọi tenant khác. PostgreSQL 15+.
#:
#: `WITH LOCAL CHECK OPTION` chặn một câu UPDATE qua view đẩy dòng ra khỏi lát
#: cắt TENANT. Không có nó, `UPDATE tenant_members SET tenant_id = 'khac'` sẽ
#: thành công và dòng đó biến mất khỏi chính view vừa sửa nó.
_TENANT_MEMBERS_VIEW = """
CREATE OR REPLACE VIEW tenant_members
WITH (security_invoker = true) AS
    SELECT tenant_id,
           user_id,
           legacy_role  AS role,
           created_at,
           status,
           suspended_at,
           left_at      AS removed_at
      FROM memberships
     WHERE scope_level = 'TENANT'
WITH LOCAL CHECK OPTION
"""


_DATA_MIGRATION_DDL: list[str] = [
    _MIGRATE_MEMBERSHIPS,
    _MIGRATE_ASSIGNMENTS,
    _DROP_LEGACY_MEMBERSHIP_TABLES,
    _TENANT_MEMBERS_VIEW,
]


# ---------------------------------------------------------------------------
# 5b. Vai cũ 'viewer' nghỉ hưu
# ---------------------------------------------------------------------------
#
# Vì sao SAU `_DATA_MIGRATION_DDL` chứ không nằm cạnh `CREATE TABLE memberships`
# -----------------------------------------------------------------------------
# Vì `_MIGRATE_MEMBERSHIPS` chép `tenant_members.role` thẳng vào `legacy_role`.
# Gắn ràng buộc TRƯỚC lượt chép nghĩa là một dòng 'viewer' còn sót sẽ làm cả
# khối di trú `RAISE` — và vì nó là một giao dịch, phần đã chép bị cuốn theo,
# bảng cũ không bao giờ bị bỏ, và hệ kẹt ở nửa đường sau mỗi lần khởi động.
#
# Đặt sau: chép xong rồi mới chuẩn hoá rồi mới siết. Thứ tự này chịu được cả ba
# tình huống — máy cài mới, máy đang ở lược đồ cũ, và máy đã có `memberships`
# từ trước lượt gỡ `tenant_viewer`.
_LEGACY_ROLE_RETIREMENT_DDL: list[str] = [
    # 'viewer' → NULL, KHÔNG → 'editor'. Xem `catalog.RETIRED_BUILTIN_ROLES`:
    # hạ xuống editor là NỚI quyền ghi cho người chưa từng có, như một tác dụng
    # phụ của việc đổi lược đồ.
    "UPDATE memberships SET legacy_role = NULL WHERE legacy_role = 'viewer'",
    "ALTER TABLE memberships ALTER COLUMN legacy_role DROP DEFAULT",
    add_constraint(
        "memberships", "ck_memberships_legacy_role_valid",
        "CHECK (legacy_role IS NULL OR legacy_role IN ('admin', 'editor'))",
    ),
]


# ---------------------------------------------------------------------------
# 6. Trigger: những bất biến mà FK/CHECK không chứng minh được
# ---------------------------------------------------------------------------
#
# PDM xếp trigger ở bậc 8-9 trong mười bậc cưỡng chế, tức là gần cuối. Bốn
# trigger dưới đây ở đó vì lý do kỹ thuật thật, không phải vì tiện — mỗi cái
# đều so sánh thuộc tính của HAI bảng khác nhau khi ghi vào bảng thứ BA. Một
# CHECK chỉ nhìn được dòng đang ghi, và khoá ngoại chỉ chứng minh tồn tại chứ
# không so sánh được thuộc tính.

_ROLE_PERMISSION_DOMINANCE_TRIGGER = """
CREATE OR REPLACE FUNCTION authz_check_role_permission_dominance()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    role_scope   TEXT;
    role_builtin BOOLEAN;
    perm_scope   TEXT;
    perm_custom  BOOLEAN;
BEGIN
    SELECT scope_level, is_builtin INTO role_scope, role_builtin
      FROM roles WHERE role_id = NEW.role_id;
    SELECT applicable_scope, is_custom_role_allowed INTO perm_scope, perm_custom
      FROM permissions WHERE permission_code = NEW.permission_code;

    -- Một role ở phạm vi HẸP không được chứa quyền áp ở phạm vi RỘNG.
    -- Cụ thể: "Project Contributor" không được cầm `tenant.billing.manage`, vì
    -- gán role đó cho một project sẽ lặng lẽ trao quyền toàn tenant.
    --
    -- Chiều ngược lại thì ĐƯỢC và cần thiết: "Tenant Administrator" (TENANT)
    -- chứa `sample.delete` (PROJECT) chính là cơ chế thống trị phạm vi —
    -- quản trị viên tenant xoá được mẫu trong mọi project mà không cần gán
    -- role giả xuống từng project.
    IF authz_scope_rank(role_scope) < authz_scope_rank(perm_scope) THEN
        RAISE EXCEPTION
            'ct_role_permission_dominance: role scope % cannot hold permission % (scope %)',
            role_scope, NEW.permission_code, perm_scope
            USING ERRCODE = 'check_violation';
    END IF;

    -- v5 §4: role do tenant tự tạo chỉ được chứa quyền mà nền tảng cho phép.
    -- Đây là nửa thứ hai của cơ chế; nửa thứ nhất là
    -- `ck_permissions_system_not_custom_role`, vốn chỉ chặn quyền SYSTEM. Cái
    -- này chặn mọi quyền được đánh dấu `is_custom_role_allowed = FALSE` ở BẤT
    -- KỲ phạm vi nào — ví dụ `tenant.purge` hay `tenant.role.manage`, những
    -- thứ phạm vi TENANT nhưng không nên tự cấu hình lại được.
    IF NOT role_builtin AND NOT perm_custom THEN
        RAISE EXCEPTION
            'ct_role_permission_dominance: permission % is not allowed in custom roles',
            NEW.permission_code
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END $$
"""

_ROLE_ASSIGNMENT_TRIGGER = """
CREATE OR REPLACE FUNCTION authz_check_role_assignment()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    role_scope    TEXT;
    role_tenant   TEXT;
    role_type_c   TEXT;
    role_active   BOOLEAN;
    mem_scope     TEXT;
    mem_tenant    TEXT;
    tenant_type_v TEXT;
BEGIN
    SELECT scope_level, tenant_id, tenant_type_constraint, is_active
      INTO role_scope, role_tenant, role_type_c, role_active
      FROM roles WHERE role_id = NEW.role_id;

    -- Gán một role đã tắt tạo ra một dòng "đang hiệu lực" mà adapter lọc bỏ:
    -- giao diện nói người này có role, Casbin nói không. Chặn ở đây thay vì để
    -- hai bên bất đồng.
    IF NOT role_active THEN
        RAISE EXCEPTION 'ct_role_assignment: role % is inactive', NEW.role_id
            USING ERRCODE = 'check_violation';
    END IF;

    -- Phạm vi SYSTEM ⟺ không có membership. Hai chiều, vì cả hai hướng sai đều
    -- có nghĩa: một role TENANT gán mà không nêu membership sẽ có hiệu lực ở
    -- MỌI tenant; một role SYSTEM treo vào membership sẽ bị `memberships` giới
    -- hạn phạm vi trong khi quyền của nó là toàn nền tảng.
    IF (role_scope = 'SYSTEM') <> (NEW.membership_id IS NULL) THEN
        RAISE EXCEPTION
            'ct_role_assignment: role scope % vs membership_id % — SYSTEM roles take no membership, others require one',
            role_scope, NEW.membership_id
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.membership_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT m.scope_level, m.tenant_id, t.tenant_type
      INTO mem_scope, mem_tenant, tenant_type_v
      FROM memberships m
      JOIN tenants t ON t.tenant_id = m.tenant_id
     WHERE m.membership_id = NEW.membership_id;

    IF role_scope IS DISTINCT FROM mem_scope THEN
        RAISE EXCEPTION
            'ct_role_assignment: role scope % cannot be assigned on a % membership',
            role_scope, mem_scope
            USING ERRCODE = 'check_violation';
    END IF;

    -- Role thuộc tenant chỉ được gán TRONG tenant đó. Không có kiểm tra này,
    -- quản trị viên tenant A tạo một role rồi gán nó cho người của tenant B —
    -- khoá ngoại không phản đối, vì cả `role_id` lẫn `membership_id` đều trỏ
    -- tới dòng có thật.
    IF role_tenant IS NOT NULL AND role_tenant IS DISTINCT FROM mem_tenant THEN
        RAISE EXCEPTION
            'ct_role_assignment: role belongs to tenant %, cannot assign in tenant %',
            role_tenant, mem_tenant
            USING ERRCODE = 'check_violation';
    END IF;

    -- v5 §3: role Community chỉ dùng được trong tenant Community. `community_
    -- curator` gán trong một tenant tổ chức sẽ mang tập quyền được thiết kế
    -- cho không gian dùng chung vào một không gian riêng tư.
    IF role_type_c IS NOT NULL AND role_type_c IS DISTINCT FROM tenant_type_v THEN
        RAISE EXCEPTION
            'ct_role_assignment: role is restricted to % tenants, membership is in a % tenant',
            role_type_c, tenant_type_v
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END $$
"""

#: Cây membership: workspace treo dưới tenant, project treo dưới workspace.
#:
#: Bản v1.0 chứng minh việc này bằng khoá ngoại ghép giữa ba bảng
#: (`project_members(tenant_id, workspace_id, user_id)` → `workspace_members`).
#: Gộp ba bảng làm một thì cách đó không còn: một khoá ngoại tự-tham-chiếu chỉ
#: chứng minh được cha TỒN TẠI và CÙNG NGƯỜI (đã làm, xem `fk_memberships_parent`),
#: không chứng minh được cha đúng MỨC và đúng NHÁNH.
_MEMBERSHIP_CHAIN_TRIGGER = """
CREATE OR REPLACE FUNCTION authz_check_membership_chain()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    parent_scope     TEXT;
    parent_tenant    TEXT;
    parent_workspace UUID;
    parent_status    TEXT;
BEGIN
    IF NEW.scope_level = 'TENANT' THEN
        IF NEW.parent_membership_id IS NOT NULL THEN
            RAISE EXCEPTION 'ct_membership_chain: TENANT membership has no parent'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.parent_membership_id IS NULL THEN
        RAISE EXCEPTION 'ct_membership_chain: % membership requires a parent', NEW.scope_level
            USING ERRCODE = 'check_violation';
    END IF;

    SELECT scope_level, tenant_id, workspace_id, status
      INTO parent_scope, parent_tenant, parent_workspace, parent_status
      FROM memberships WHERE membership_id = NEW.parent_membership_id;

    IF NEW.scope_level = 'WORKSPACE' AND parent_scope <> 'TENANT' THEN
        RAISE EXCEPTION 'ct_membership_chain: WORKSPACE parent must be TENANT, got %', parent_scope
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.scope_level = 'PROJECT' THEN
        IF parent_scope <> 'WORKSPACE' THEN
            RAISE EXCEPTION 'ct_membership_chain: PROJECT parent must be WORKSPACE, got %', parent_scope
                USING ERRCODE = 'check_violation';
        END IF;
        -- Cùng NHÁNH, không chỉ cùng tenant. Đây là INV-MEM-03: không thể là
        -- thành viên project P nếu tư cách thành viên workspace được viện dẫn
        -- lại thuộc một workspace khác.
        IF parent_workspace IS DISTINCT FROM NEW.workspace_id THEN
            RAISE EXCEPTION
                'ct_membership_chain: project membership in workspace % but parent is in workspace %',
                NEW.workspace_id, parent_workspace
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    IF parent_tenant IS DISTINCT FROM NEW.tenant_id THEN
        RAISE EXCEPTION 'ct_membership_chain: parent is in tenant %, child in tenant %',
            parent_tenant, NEW.tenant_id
            USING ERRCODE = 'check_violation';
    END IF;

    -- Một tư cách thành viên còn sống không được treo dưới một tư cách đã bị
    -- gỡ. Nếu không chặn, gỡ người khỏi tenant sẽ để lại tư cách workspace/
    -- project "còn hiệu lực" — và adapter, vốn chỉ nối lên cha khi cần, có thể
    -- vẫn chiếu role đó vào policy.
    IF NEW.status = 'ACTIVE' AND parent_status <> 'ACTIVE' THEN
        RAISE EXCEPTION
            'ct_membership_chain: cannot hold an ACTIVE % membership under a % parent',
            NEW.scope_level, parent_status
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END $$
"""

#: Role Community bị ghim vào tenant Community — kiểm ở chính bảng `roles`.
#:
#: Trigger assignment ở trên chặn việc GÁN sai. Cái này chặn việc TẠO một role
#: tuỳ biến mang `tenant_type_constraint` không khớp loại tenant sở hữu nó —
#: một dòng như vậy không gán được cho ai, tức là một cấu hình chết mà giao
#: diện vẫn hiện ra như bình thường.
_ROLE_TENANT_TYPE_TRIGGER = """
CREATE OR REPLACE FUNCTION authz_check_role_tenant_type()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    owner_type TEXT;
BEGIN
    IF NEW.tenant_id IS NULL OR NEW.tenant_type_constraint IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT tenant_type INTO owner_type FROM tenants WHERE tenant_id = NEW.tenant_id;

    IF owner_type IS DISTINCT FROM NEW.tenant_type_constraint THEN
        RAISE EXCEPTION
            'ct_role_tenant_type: role is owned by a % tenant but restricted to % tenants',
            owner_type, NEW.tenant_type_constraint
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$
"""


def _replace_trigger(name: str, table: str, timing: str, function: str) -> list[str]:
    """DROP rồi CREATE, vì Postgres không có `CREATE OR REPLACE TRIGGER`.

    `CREATE TRIGGER` trần trên bảng đã có trigger cùng tên sẽ lỗi, và `_run_ddl`
    chỉ ghi WARNING — nên lỗi đó thành tiếng ồn im lặng, và tệ hơn, nếu định
    nghĩa trigger đổi thì bản CŨ vẫn đang chạy.
    """
    return [
        f"DROP TRIGGER IF EXISTS {name} ON {table}",
        f"CREATE TRIGGER {name} {timing} ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {function}",
    ]


_TRIGGER_DDL: list[str] = [
    _SCOPE_RANK_FN,
    _ROLE_PERMISSION_DOMINANCE_TRIGGER,
    _ROLE_ASSIGNMENT_TRIGGER,
    _MEMBERSHIP_CHAIN_TRIGGER,
    _ROLE_TENANT_TYPE_TRIGGER,

    *_replace_trigger("ct_role_permissions_dominance", "role_permissions",
                      "BEFORE INSERT OR UPDATE",
                      "authz_check_role_permission_dominance()"),
    *_replace_trigger("ct_role_assignments_scope", "role_assignments",
                      "BEFORE INSERT OR UPDATE OF role_id, membership_id",
                      "authz_check_role_assignment()"),
    *_replace_trigger("ct_memberships_chain", "memberships",
                      "BEFORE INSERT OR UPDATE OF scope_level, tenant_id, workspace_id, "
                      "project_id, parent_membership_id, status",
                      "authz_check_membership_chain()"),
    *_replace_trigger("ct_roles_tenant_type", "roles",
                      "BEFORE INSERT OR UPDATE OF tenant_id, tenant_type_constraint",
                      "authz_check_role_tenant_type()"),
]


# ---------------------------------------------------------------------------
# 7. Mã hành động cá nhân (xác thực nâng cấp)
# ---------------------------------------------------------------------------

_PASSCODE_DDL: list[str] = [
    # Mã hành động KHÔNG BAO GIỜ biến DENY thành ALLOW. Nó chỉ chạy SAU khi
    # phân quyền đã cho qua, cho những quyền có `requires_passcode`.
    #
    # Vì sao KHÔNG có cột `last_verified_at`
    # ---------------------------------------
    # Một cột như vậy mời gọi tối ưu hoá "vừa xác nhận cách đây 5 phút thì bỏ
    # qua". Cái đó biến xác thực nâng cấp thành một phiên thứ hai với thời hạn
    # riêng, và giá trị của bước này nằm đúng ở chỗ nó gắn với MỘT hành động cụ
    # thể. Cửa sổ thời gian, nếu cần, thuộc về `sudo_mode.py` — nơi đã có nó và
    # nơi ngữ nghĩa của nó được viết ra.
    """
    CREATE TABLE IF NOT EXISTS user_action_passcodes (
        user_id       UUID PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
        passcode_hash TEXT NOT NULL,
        status        TEXT NOT NULL DEFAULT 'ACTIVE',
        failed_count  SMALLINT NOT NULL DEFAULT 0,
        created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        locked_until  TIMESTAMP WITH TIME ZONE,
        revoked_at    TIMESTAMP WITH TIME ZONE,
        CONSTRAINT ck_user_action_passcodes_status
            CHECK (status IN ('ACTIVE', 'LOCKED', 'REVOKED')),
        CONSTRAINT ck_user_action_passcodes_failed_count CHECK (failed_count >= 0)
    )
    """,
]


# ---------------------------------------------------------------------------
# 8. Hộp thư sự kiện (transactional outbox)
# ---------------------------------------------------------------------------

_OUTBOX_DDL: list[str] = [
    # Vô hiệu hoá policy cache đi qua outbox thay vì một bảng
    # `casbin_policy_version` riêng.
    #
    # `tenant_id` NULLABLE, khác với PDM vốn ghi NOT NULL. Lý do giống hệt lý do
    # `audit_log` cho phép NULL: sự kiện `authorization.policy.changed` cho một
    # thay đổi ở phạm vi SYSTEM không thuộc tenant nào. Bắt nó NOT NULL sẽ buộc
    # phải bịa ra một tenant, và tenant bịa đó sẽ lọt vào bộ lọc của người tiêu
    # thụ sự kiện.
    #
    # Hệ quả đối xứng, và nó phải được tôn trọng ở tầng gọi: với vị từ RLS dùng
    # chung, ghi một dòng tenant_id NULL trong lúc đang ở tenant scope sẽ bị
    # WITH CHECK từ chối. Sự kiện nền tảng phải phát ra trong system scope.
    """
    CREATE TABLE IF NOT EXISTS event_outbox (
        event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id       TEXT,
        event_type_code TEXT NOT NULL,
        payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
        occurred_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        dispatch_status TEXT NOT NULL DEFAULT 'PENDING',
        attempts        INTEGER NOT NULL DEFAULT 0,
        available_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        processed_at    TIMESTAMP WITH TIME ZONE,
        last_error      TEXT,
        CONSTRAINT ck_event_outbox_status
            CHECK (dispatch_status IN ('PENDING', 'IN_FLIGHT', 'DONE', 'FAILED')),
        CONSTRAINT ck_event_outbox_type_not_blank CHECK (event_type_code <> ''),
        CONSTRAINT ck_event_outbox_attempts CHECK (attempts >= 0)
    )
    """,
    # Chỉ mục cho câu hỏi DUY NHẤT mà worker hỏi: "còn sự kiện nào đến hạn
    # chưa gửi không". Từng phần theo `dispatch_status`, nên nó không phình
    # theo lịch sử đã gửi — bảng này chỉ tăng, phần chờ xử lý thì không.
    "CREATE INDEX IF NOT EXISTS ix_event_outbox_pending "
    "ON event_outbox (available_at) WHERE dispatch_status = 'PENDING'",
    "CREATE INDEX IF NOT EXISTS ix_event_outbox_type_time "
    "ON event_outbox (event_type_code, occurred_at DESC)",
]


# ---------------------------------------------------------------------------
# Danh sách hợp nhất
# ---------------------------------------------------------------------------

#: Toàn bộ DDL của mặt phẳng phân quyền, ĐÚNG thứ tự phụ thuộc.
#:
#: Thứ tự quan trọng vì `_run_ddl` không dừng khi lỗi: một `ALTER TABLE ... ADD
#: CONSTRAINT` chạy trước `CREATE TABLE` của bảng nó tham chiếu sẽ ghi WARNING
#: rồi đi tiếp, và ràng buộc đó sẽ THIẾU cho tới lần khởi động sau. Trên một hệ
#: chỉ khởi động lại khi triển khai, "lần sau" có thể là hàng tuần.
#:
#: Bốn ràng buộc thứ tự KHÔNG được đổi:
#:   * `_TENANT_TYPE_DDL` trước mọi thứ — trigger role đọc `tenants.tenant_type`
#:   * `_RBAC_DDL` trước `_ASSIGNMENT_DDL` — khoá ngoại trỏ vào `roles`
#:   * `_LEGACY_MEMBER_COLUMNS_DDL` trước `_DATA_MIGRATION_DDL` — lượt gộp đọc
#:     `tenant_members.status`, và trên máy cài mới cột đó chưa tồn tại
#:   * `_MEMBERSHIP_DDL` trước `_DATA_MIGRATION_DDL` — đích phải có trước nguồn
#:   * `_LEGACY_ROLE_RETIREMENT_DDL` SAU `_DATA_MIGRATION_DDL` — nó siết giá trị
#:     của `legacy_role`, mà lượt chép mới là nơi giá trị cũ đi vào
#:   * `_TRIGGER_DDL` SAU `_DATA_MIGRATION_DDL` — di trú chép dữ liệu lịch sử,
#:     trong đó có dòng đã thu hồi và role đã tắt mà trigger sẽ từ chối. Gắn
#:     trigger trước nghĩa là di trú thất bại và bảng cũ không bao giờ bị bỏ.
AUTHZ_DDL_STATEMENTS: list[str] = [
    *_TENANT_TYPE_DDL,
    *_HIERARCHY_DDL,
    *_RBAC_DDL,
    *_LEGACY_MEMBER_COLUMNS_DDL,
    *_MEMBERSHIP_DDL,
    *_ASSIGNMENT_DDL,
    *_DATA_MIGRATION_DDL,
    *_LEGACY_ROLE_RETIREMENT_DDL,
    *_TRIGGER_DDL,
    *_PASSCODE_DDL,
    *_OUTBOX_DDL,
]


# ---------------------------------------------------------------------------
# Kiểm tra: cái lưới bắt những câu lệnh đã lặng lẽ thất bại
# ---------------------------------------------------------------------------

#: Đối tượng phải tồn tại sau khi `ensure_tables()` chạy xong.
#:
#: Cần vì `_run_ddl` nuốt lỗi — thiết kế đó đúng (một câu hỏng không được kéo
#: đổ hai mươi câu sau), nhưng nó có nghĩa là "khởi động thành công" KHÔNG
#: chứng minh schema đúng. Danh sách này biến sự im lặng đó thành một câu trả
#: lời kiểm tra được, và `verify_deployment` in ra.
REQUIRED_TABLES: tuple[str, ...] = (
    "workspaces", "projects",
    "memberships", "role_assignments",
    "roles", "permissions", "role_permissions",
    "user_action_passcodes", "event_outbox",
)

#: Bảng của bản v1.0 phải KHÔNG còn, vì chúng đã được gộp. Một cái còn sót lại
#: nghĩa là di trú dừng giữa chừng và hệ đang có hai nguồn sự thật — trạng thái
#: nguy hiểm hơn cả hai đầu, vì adapter đọc bảng mới trong khi 15 tệp còn ghi
#: vào bảng cũ.
FORBIDDEN_TABLES: tuple[str, ...] = (
    "tenant_member_roles", "workspace_member_roles", "project_member_roles",
    "system_user_roles", "workspace_members", "project_members",
)

#: View tương thích phải là VIEW, không phải bảng. Nếu nó còn là bảng thì di
#: trú chưa chạy xong và `tenant_members` đang là bản sao chết của `memberships`.
REQUIRED_VIEWS: tuple[str, ...] = ("tenant_members",)

#: Ràng buộc mà nếu thiếu thì một bất biến CRITICAL không còn ai cưỡng chế.
#: Mỗi mục là `(bảng, tên ràng buộc, điều nó ngăn)`.
REQUIRED_CONSTRAINTS: tuple[tuple[str, str, str], ...] = (
    ("projects", "fk_inv_ten_02_project_workspace",
     "project nam trong workspace cua tenant khac"),
    ("memberships", "uq_memberships_id_user",
     "gan role qua membership cua NGUOI KHAC"),
    ("memberships", "fk_memberships_parent",
     "membership con treo duoi cha cua nguoi khac"),
    ("memberships", "fk_memberships_workspace",
     "membership workspace tro sang tenant khac"),
    ("memberships", "fk_memberships_project",
     "membership project tro sang tenant khac"),
    ("memberships", "ck_memberships_shape",
     "membership WORKSPACE/PROJECT thieu dinh danh pham vi"),
    ("role_assignments", "fk_role_assignments_membership",
     "gan role cho nguoi khong phai thanh vien"),
    ("roles", "ck_role_ownership",
     "role dung san thuoc mot tenant, hoac role tuy bien khong co chu"),
    ("permissions", "ck_permissions_system_not_api_assignable",
     "quyen SYSTEM cap duoc cho khoa API cua tenant"),
    ("permissions", "ck_permissions_system_not_custom_role",
     "quyen SYSTEM cap duoc cho role tuy bien cua tenant"),
    ("tenants", "ck_tenants_type",
     "tenant mang loai khong hop le"),
)

#: Trigger mà nếu thiếu thì một bất biến không được cưỡng chế.
REQUIRED_TRIGGERS: tuple[tuple[str, str], ...] = (
    ("role_permissions", "ct_role_permissions_dominance"),
    ("role_assignments", "ct_role_assignments_scope"),
    ("memberships", "ct_memberships_chain"),
    ("roles", "ct_roles_tenant_type"),
)

#: Cột THÊM vào bảng CŨ mà mã đang chạy đã phụ thuộc vào.
#:
#: Tách khỏi `REQUIRED_TABLES` vì kiểu hỏng khác hẳn: một bảng thiếu thì tính
#: năng mới không chạy, còn một CỘT thiếu trên bảng cũ thì mã cũ NGÃ. Cụ thể
#: `vocabulary_registry.tenant_role()` lọc theo `tenant_members.status`, và
#: `ALTER TABLE ... ADD COLUMN` thất bại lặng lẽ trong `_run_ddl` sẽ làm mọi
#: lời gọi hàm đó ném lỗi — tức là mọi phép kiểm quyền biên tập của mọi tenant.
REQUIRED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("tenant_members", "status"),
    ("tenant_members", "removed_at"),
    ("tenant_members", "role"),
    ("tenants", "tenant_type"),
    ("permissions", "is_custom_role_allowed"),
    ("roles", "role_code"),
    ("roles", "tenant_type_constraint"),
)

#: Chỉ mục duy nhất từng phần giữ cho "đang hiệu lực" là duy nhất.
REQUIRED_INDEXES: tuple[str, ...] = (
    "uq_role_assignments_scoped",
    "uq_role_assignments_system",
    "uq_memberships_tenant_user",
    "uq_memberships_workspace_user",
    "uq_memberships_project_user",
    "uq_roles_builtin_code",
    "uq_roles_custom_code",
    "uq_workspaces_default_active",
    "uq_projects_default_active",
    "uq_tenants_single_community",
)


def missing_objects(conn) -> list[str]:
    """Liệt kê đối tượng schema phân quyền còn thiếu. Rỗng nghĩa là đủ.

    Nhận sẵn một connection thay vì tự mở, để người gọi quyết định chạy dưới
    vai nào — `verify_deployment` dùng vai migration, test dùng vai ứng dụng.
    """
    missing: list[str] = []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"
        )
        present_tables = {r[0] for r in cur.fetchall()}
        missing += [f"table {t}" for t in REQUIRED_TABLES if t not in present_tables]

        # Bảng cũ CÒN SÓT là lỗi nặng hơn bảng mới còn thiếu: nó nghĩa là hai
        # nguồn sự thật đang cùng sống. Nói rõ điều đó trong thông điệp, vì
        # người đọc `verify_deployment` sẽ thấy nó lẫn giữa các dòng khác.
        missing += [
            f"BANG CU CON SOT: {t} (di tru v5 chua hoan tat — hai nguon su that)"
            for t in FORBIDDEN_TABLES if t in present_tables
        ]
        missing += [
            f"BANG CU CON SOT: tenant_members van la BANG, chua thanh view"
            for t in ("tenant_members",) if t in present_tables
        ]

        cur.execute(
            "SELECT viewname FROM pg_views WHERE schemaname = current_schema()"
        )
        present_views = {r[0] for r in cur.fetchall()}
        missing += [f"view {v}" for v in REQUIRED_VIEWS if v not in present_views]

        cur.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema()"
        )
        present_columns = {(r[0], r[1]) for r in cur.fetchall()}
        missing += [
            f"column {table}.{column}"
            for table, column in REQUIRED_COLUMNS
            if (table, column) not in present_columns
        ]

        cur.execute("SELECT conname FROM pg_constraint")
        present_constraints = {r[0] for r in cur.fetchall()}
        missing += [
            f"constraint {name} on {table} (cho phep: {why})"
            for table, name, why in REQUIRED_CONSTRAINTS
            if name not in present_constraints
        ]

        cur.execute("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")
        present_triggers = {r[0] for r in cur.fetchall()}
        missing += [
            f"trigger {name} on {table}"
            for table, name in REQUIRED_TRIGGERS
            if name not in present_triggers
        ]

        cur.execute("SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()")
        present_indexes = {r[0] for r in cur.fetchall()}
        missing += [f"index {i}" for i in REQUIRED_INDEXES if i not in present_indexes]

    return missing
