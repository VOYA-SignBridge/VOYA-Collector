"""Row-level security: the tenant boundary Postgres itself enforces.

Why this lives at the database layer
------------------------------------
`tenant_id` existed on twelve tables long before this module, but it was a
metadata column, not a boundary: every query that forgot a `WHERE tenant_id`
returned every tenant's rows and nothing complained. `delete_sample()`,
`delete_samples_by_class()` and `update_sample_gdrive_url()` in
``storage/metadata_db.py`` are three that still carry no tenant filter today.

A policy in the database fixes all of them at once, and — the part that matters
more — it also covers the queries nobody has written yet. Application-level
filtering protects the code that exists; RLS protects the code that will exist.

The two GUCs
------------
``app.tenant_id``    the tenant a request is acting for. Unset means *no rows*,
                     never *all rows* (see below).
``app.system_scope`` set to ``'on'`` for platform work that legitimately spans
                     tenants: the startup CSV->DB sync, the SOT reader, Celery
                     maintenance. Deliberately a separate GUC rather than a
                     magic tenant id, so "acting for everyone" can never be
                     produced by a typo in a tenant name.

Both are read with ``current_setting(..., true)``, the missing_ok form, which
returns NULL rather than raising when the setting was never assigned. That is
what makes the policy fail *closed*: ``tenant_id = NULL`` evaluates to NULL,
NULL is not TRUE, so a connection that never set the GUC sees zero rows and can
insert nothing. The raising form would have produced a 500 instead — louder, but
it would also have taken down every unrelated query on the same connection.

Why the GUC must be set with SET LOCAL
--------------------------------------
Connections come from a shared ``ThreadedConnectionPool``. A plain ``SET``
persists on the connection after it is returned to the pool, so the next request
to borrow it — possibly a different tenant — would inherit the previous tenant's
context. ``SET LOCAL`` is scoped to the transaction and disappears on commit or
rollback. This is the classic RLS-plus-pooling defect and it produces no error
of any kind: just one unlucky user reading someone else's data.

Why the application role must not be able to run DDL
----------------------------------------------------
``ALTER TABLE x DISABLE ROW LEVEL SECURITY`` is DDL. A role that can alter a
table can therefore switch off its own containment, which makes the guarantee
self-revocable and hence not a guarantee. Hence the split between
``DATABASE_URL`` (DML only) and ``MIGRATION_DATABASE_URL`` (DDL), provisioned by
``app.cli.provision_db_roles``.

Related: docs/11-worklog/BACKEND_WORK_PLAN.md items A2 and A3.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

# Module level, not inside apply_scope: that function runs once per database
# transaction — hundreds of times during a single video upload — and
# tenant_context is dependency-free precisely so this import is safe here.
from app.tenant_context import current_tenant, in_system_scope

logger = logging.getLogger(__name__)

def _authz_tenant_tables() -> tuple[str, ...]:
    """The PDM authorization-plane tables that carry a `tenant_id`.

    Imported rather than re-typed. The list lives next to the DDL that creates
    those tables, which is the only place that can add one — so a table added
    there arrives here automatically instead of depending on someone
    remembering two files. A table with `tenant_id` and no policy is exactly
    the failure this module exists to prevent, and it produces no error.

    Deferred inside a function because `authz_schema` is a sibling in the same
    package and this module is imported very early (metadata_db imports it at
    module scope); a top-level import would fix the order in a way that a
    future import in `authz_schema` could break.
    """
    from app.storage.authz_schema import TENANT_SCOPED_AUTHZ_TABLES

    return TENANT_SCOPED_AUTHZ_TABLES


#: GUC carrying the tenant a statement is acting for.
TENANT_GUC = "app.tenant_id"

#: GUC that opts a transaction into platform scope (all tenants).
SYSTEM_SCOPE_GUC = "app.system_scope"

#: Value SYSTEM_SCOPE_GUC must hold to take effect. Any other value, including
#: the empty string a reset leaves behind, means "not in system scope".
SYSTEM_SCOPE_ON = "on"

#: Tables the tenant policy is installed on: all thirteen that carry a
#: `tenant_id`, matching `metadata_db.TENANT_SCOPED_TABLES` exactly.
#:
#: It grew in three steps, and the order says something about the design. The
#: first three hold the corpus and are what the startup CSV->DB sync writes to.
#: `training_jobs` and `users` were added after a demonstrable leak:
#: `list_training_jobs` reads ``SELECT * FROM training_jobs ORDER BY created_at
#: DESC LIMIT %s`` with no tenant predicate at all, so a second tenant would
#: have seen every tenant's jobs the day it was created.
#:
#: The remaining eight — the reference plane — were added last, on 2026-08-07.
#: The argument for leaving them out had been that they are reachable only
#: through code paths that already join to one of the first five. That was true
#: of the code as written, which is exactly the guarantee this module exists to
#: stop relying on: application-level filtering protects the code that exists,
#: a policy protects the code that will exist. `registry_versions` in
#: particular is the artifact plane's provenance record, and reading another
#: tenant's version history discloses their vocabulary.
#:
#: Verified before enabling: none of the eight held a NULL `tenant_id`. A NULL
#: there would match no policy and the row would vanish from the application's
#: view — indistinguishable from deletion.
#:
#: `users` is the subtle one, and its guarantee is NARROWER than the others —
#: see the note on the identity plane below.
#:
#: The identity plane is exempt, and cannot not be
#: ------------------------------------------------
#: Authentication happens BEFORE the tenant is known: a login looks an account
#: up by email, and the request middleware reads `users.tenant_id` in order to
#: DECIDE the scope. A policy that filtered those reads by the scope they are
#: computing is circular — it would return zero rows and nobody could log in.
#:
#: So `app/auth.py` and `tenant_middleware._tenant_of_user` run in system scope,
#: and RLS on `users` does not constrain them. What it DOES constrain is every
#: data-plane read: the joins in `metadata_db` that decorate a sample or a
#: training job with its contributor's name, the activity feed's username
#: lookup, and the dialect list's `created_by`. Those are the places a
#: cross-tenant `auth_user_id` would otherwise resolve to a real name; with the
#: policy they resolve to NULL instead. That is a real guarantee and a limited
#: one, and it is written down here so nobody reads "RLS on users" as more than
#: it is.
#:
#: Sáu bảng cuối vào cùng lượt schema v3 (2026-08-08). Hai chỗ đáng nói:
#:
#: `audit_log` là bảng DUY NHẤT ở đây cho phép `tenant_id` NULL, và điều đó có
#: chủ ý. Một hành động ở tầng nền tảng — cấp sudo, đổi hạn mức trải nghiệm —
#: không thuộc tenant nào. Với vị từ dùng chung, `NULL = 'abc'` cho ra NULL chứ
#: không phải TRUE, nên dòng đó chỉ hiện trong system scope: sự kiện nền tảng
#: chỉ quản trị viên nền tảng đọc được, còn quản trị viên tenant vẫn thấy đủ
#: phần của mình. Hệ quả đối xứng mà `app/audit.py` phải tôn trọng: ghi một
#: dòng tenant_id NULL trong lúc đang ở tenant scope sẽ bị WITH CHECK từ chối.
#:
#: `signer_consents` chịu RLS vì nó là dữ liệu về người thật — ai đồng ý cho
#: công bố hình ảnh của mình. Rò bảng này sang tenant khác vừa là rò danh tính
#: vừa là rò bằng chứng pháp lý.
RLS_TABLES: tuple[str, ...] = (
    # corpus
    "samples", "classes", "raw_uploads",
    # added after a demonstrable leak
    "training_jobs", "users",
    # reference plane
    "dialect_aliases", "dialects", "recognition_profiles", "registry_versions",
    # `tenant_members` KHÔNG còn ở đây: PDM v5 biến nó thành VIEW trên
    # `memberships`, và `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` trên view là
    # lỗi ở mọi lần khởi động. Policy sống trên bảng nền — có trong
    # `TENANT_SCOPED_AUTHZ_TABLES` — và view khai `security_invoker = true` nên
    # truy vấn qua nó chạy dưới quyền NGƯỜI GỌI và chịu đúng policy đó.
    #
    # Cái phải canh giờ là `security_invoker`, không phải sự có mặt trong danh
    # sách này: bỏ thuộc tính đó đi thì view chạy bằng quyền chủ sở hữu và MỌI
    # tenant đọc được thành viên của mọi tenant khác. Xem `_TENANT_MEMBERS_VIEW`
    # và `test_the_compatibility_view_does_not_bypass_rls`.
    "signers", "tenant_invitations",
    "vocabulary_registry_meta",
    # schema v3
    "audit_log", "capture_sessions", "signer_aliases", "signer_consents",
    "training_job_classes", "vocabulary_groups",
    # `tenants` — BẢNG GỐC, mỗi dòng LÀ một tenant, nên vị từ chuẩn
    # `tenant_id = current_setting('app.tenant_id')` đọc ra thành "chỉ thấy dòng
    # của chính mình". Thêm ngày 15/08/2026.
    #
    # Nó vắng mặt ở đây KHÔNG phải vì bị loại có lý do — nó chưa từng được nhắc
    # tới. Đo được với `voya_test_app`, vai đặc quyền tối thiểu, KHÔNG cần
    # sentinel: `SELECT` trả 28 tenant, `UPDATE` chạm 28 dòng. Cột lộ ra gồm
    # `plan_code`, `billing_status`, `billing_exempt`, `owner_user_id`.
    #
    # Ba đường ĐỌC XUYÊN TENANT hợp lệ đã được kiểm kê và đều chạy trong
    # `system_scope`: xác thực khoá API (`api_keys.py`, mặt phẳng danh tính),
    # kiểm tenant đích tồn tại trước khi sao chép danh mục
    # (`routers/vocabulary.py` — được bọc CÙNG lượt này, trước đó nó không có
    # phạm vi nào), và hậu điều kiện gieo dữ liệu đời cũ của SOT.
    "tenants",
    # schema v4 — mặt phẳng thương mại. `plans` không có ở đây vì nó là danh
    # mục chung của nền tảng (mọi tenant đọc cùng một bảng giá).
    #
    # `tenant_purges` cũng chưa có, nhưng KHÔNG còn là ngoại lệ có giải trình.
    # Lập luận cũ — "sau khi xoá thì không còn tenant nào để phạm vi hoá theo" —
    # chỉ đứng vững nếu vai ứng dụng không có đường ghi trực tiếp. Phép đo bác
    # bỏ điều đó: `voya_app` có đủ bốn quyền DML trên bảng ấy. Nó là khoảng
    # trống thật, đang chờ xử ngay sau `tenants`. Xem
    # docs/TENANT_ISOLATION_AND_AUTHZ.md §5.
    "api_keys", "tenant_exports", "tenant_subscriptions", "tenant_usage_daily",
    "webhook_deliveries", "webhook_endpoints",
    # schema v6 — thông báo và hỗ trợ. Cả hai mang nội dung do NGƯỜI viết ra:
    # một phiếu hỗ trợ thường chứa mô tả sự cố, ảnh chụp màn hình, đôi khi cả
    # dữ liệu thật. Rò sang tenant khác là rò chính thứ khách hàng gửi riêng.
    #
    # `user_totp` và `user_recovery_codes` CỐ Ý không có ở đây: chúng thuộc mặt
    # phẳng danh tính và được đọc GIỮA CHỪNG lúc đăng nhập, trước khi tenant
    # được biết. RLS ở đó fail-OPEN (khớp 0 dòng = "không bật 2FA"), nên nó sẽ
    # âm thầm vô hiệu hoá lớp bảo vệ thứ hai. Xem chú thích ở `CREATE TABLE
    # user_totp` trong metadata_db.py.
    "notifications", "support_messages", "support_tickets",
    # PDM v1.0 — mặt phẳng phân quyền. Cây Tenant→Workspace→Project và ba bảng
    # gán role theo tenant. Danh sách nguồn ở `storage/authz_schema.py`; nối
    # vào đây thay vì gõ lại, để thêm một bảng ở đó không thể quên bật RLS.
    #
    # Ba nhóm của mặt phẳng đó KHÔNG có ở đây và mỗi nhóm vì một lý do khác:
    # `roles` dùng chính sách danh mục dùng chung bên dưới; `role_assignments`
    # không mang `tenant_id` (phạm vi của nó đọc từ `memberships`, vốn CÓ chịu
    # RLS); `permissions`/`role_permissions` là danh mục toàn nền tảng. Xem chú
    # thích ở `TENANT_SCOPED_AUTHZ_TABLES`.
    *_authz_tenant_tables(),
)

#: Bảng danh mục vừa có dòng CỦA NỀN TẢNG vừa có dòng CỦA TENANT.
#:
#: `roles` là bảng duy nhất hiện nay: chín role dựng sẵn mang `tenant_id NULL`
#: và mọi tenant phải ĐỌC được chúng (nếu không thì không gán được role nào),
#: nhưng không tenant nào được GHI vào chúng.
#:
#: Đây là chỗ duy nhất trong tệp này mà USING và WITH CHECK CỐ Ý khác nhau, và
#: docstring của `_policy_predicate` giải thích vì sao thường thì không được
#: phép. Lập luận ở đó — "USING hẹp hơn WITH CHECK cho phép ghi dòng không đọc
#: lại được; ngược lại cho phép chuyển dòng sang tenant khác" — nói về bảng dữ
#: liệu. Với danh mục thì chiều rộng-đọc/hẹp-ghi có nghĩa chính xác và mong
#: muốn: **đọc được thứ mình không sửa được**, y như một bảng giá.
#:
#: Điều PHẢI giữ là vế WITH CHECK không được nới. Nếu nó cũng cho `tenant_id IS
#: NULL` qua, một tenant sẽ tạo được role toàn nền tảng — và vì role dựng sẵn
#: `platform_admin` chứa mọi quyền SYSTEM, đó là đường leo thang đặc quyền
#: thẳng từ tenant lên nền tảng.
SHARED_CATALOGUE_TABLES: tuple[str, ...] = ("roles",)

#: Policy name, one per table. Named rather than anonymous so re-running the
#: migration can drop-and-recreate deterministically instead of stacking
#: duplicate policies (Postgres permits several policies per table and ORs them,
#: so a stacked duplicate would silently widen access).
POLICY_NAME = "tenant_isolation"

#: Policy name for the shared-catalogue shape. Different name so a table can
#: never end up carrying both — two policies on one table are OR-ed, and the
#: wider one would win silently.
CATALOGUE_POLICY_NAME = "tenant_catalogue_access"


def _policy_predicate() -> str:
    """SQL predicate shared by USING and WITH CHECK.

    Same expression for both on purpose: USING governs which existing rows are
    visible to SELECT/UPDATE/DELETE, WITH CHECK governs which rows INSERT/UPDATE
    may produce. Using a narrower USING than WITH CHECK would let a tenant write
    a row it cannot then read; the reverse would let it move a row into another
    tenant. Equal predicates make the table a closed partition.
    """
    return (
        f"(current_setting('{SYSTEM_SCOPE_GUC}', true) = '{SYSTEM_SCOPE_ON}'"
        f" OR tenant_id = current_setting('{TENANT_GUC}', true))"
    )


def policy_statements(table: str) -> list[str]:
    """Idempotent DDL installing the tenant policy on one table."""
    predicate = _policy_predicate()
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        # FORCE additionally subjects the table OWNER to the policy. Without it
        # the owner is exempt, and the owner is the migration role — so any
        # future maintenance script connecting with that DSN would quietly see
        # every tenant. The migration role only runs DDL, so nothing legitimate
        # is lost by closing that door.
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table}",
        # Symmetric with `shared_catalogue_statements`: drop the other shape too,
        # so moving a table between the two lists cannot leave both policies
        # installed. Postgres ORs them, and the wider one wins.
        f"DROP POLICY IF EXISTS {CATALOGUE_POLICY_NAME} ON {table}",
        f"CREATE POLICY {POLICY_NAME} ON {table} "
        f"USING {predicate} WITH CHECK {predicate}",
    ]


def shared_catalogue_statements(table: str) -> list[str]:
    """Idempotent DDL installing the shared-catalogue policy on one table.

    Read: platform rows (`tenant_id IS NULL`) plus this tenant's own rows.
    Write: this tenant's own rows only.

    The asymmetry is the point — see `SHARED_CATALOGUE_TABLES` for why it is
    correct here and forbidden everywhere else.
    """
    system = f"current_setting('{SYSTEM_SCOPE_GUC}', true) = '{SYSTEM_SCOPE_ON}'"
    own = f"tenant_id = current_setting('{TENANT_GUC}', true)"
    using = f"({system} OR tenant_id IS NULL OR {own})"
    # `tenant_id IS NULL` is absent from WITH CHECK, deliberately. Adding it
    # would let any tenant mint a platform-wide role.
    check = f"({system} OR {own})"
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        # Drop BOTH policy names, not just the one about to be created. A table
        # that ever carried the plain tenant policy would otherwise keep it,
        # and Postgres ORs multiple policies — so the stricter one would have
        # no effect and the mistake would be invisible.
        f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table}",
        f"DROP POLICY IF EXISTS {CATALOGUE_POLICY_NAME} ON {table}",
        f"CREATE POLICY {CATALOGUE_POLICY_NAME} ON {table} "
        f"USING {using} WITH CHECK {check}",
    ]


def rls_ddl() -> list[str]:
    """Every statement needed to install tenant isolation, in order."""
    statements = [stmt for table in RLS_TABLES for stmt in policy_statements(table)]
    statements += [
        stmt for table in SHARED_CATALOGUE_TABLES
        for stmt in shared_catalogue_statements(table)
    ]
    return statements


class IsolationPostureError(RuntimeError):
    """Raised at boot when RLS is on but the connected role can ignore it."""


def isolation_posture(conn) -> Dict[str, Any]:
    """Describe whether tenant isolation is actually in force on `conn`.

    Returns the three facts that together decide it: who we are connected as,
    whether that role can bypass RLS, and which tables have RLS switched on.
    Kept as data rather than a bare bool so the caller can log the specifics and
    a test can assert on them.
    """
    from app.storage.postgres_connection import current_role_privileges, rls_enabled_tables

    privileges = current_role_privileges(conn)
    # Both shapes count: a shared-catalogue table with RLS switched off is just
    # as exposed as a tenant table with RLS switched off, and reporting only the
    # first list would have declared the posture healthy while `roles` sat open.
    enabled = rls_enabled_tables(conn, RLS_TABLES + SHARED_CATALOGUE_TABLES)
    return {
        "role": privileges.rolname,
        "is_superuser": privileges.is_superuser,
        "bypasses_rls": privileges.bypasses_rls,
        "can_bypass_rls": privileges.can_bypass_rls,
        "rls_tables": enabled,
        "rls_enabled": bool(enabled),
        # The state this whole module exists to make impossible: policies
        # installed and reported as active, while the connected role ignores
        # every one of them.
        "policies_are_theatre": bool(enabled) and privileges.can_bypass_rls,
    }


def assert_isolation_enforceable(conn, *, strict: bool) -> Dict[str, Any]:
    """Fail loudly when the isolation guarantee is only on paper.

    `strict` comes from DB_STRICT_ISOLATION. It defaults off so a deployment can
    sequence "install policies" and "switch DATABASE_URL to the non-superuser
    role" as two separate steps without the first one bricking the stack. Once
    the role is switched it should be turned on, because from then on this
    condition can only be reached by a regression.
    """
    posture = isolation_posture(conn)

    if not posture["policies_are_theatre"]:
        if posture["rls_enabled"]:
            logger.info(
                "[RLS] tenant isolation in force: role=%s tables=%s",
                posture["role"], ",".join(posture["rls_tables"]),
            )
        return posture

    message = (
        f"Row-level security is enabled on {', '.join(posture['rls_tables'])} but the "
        f"application role {posture['role']!r} bypasses it "
        f"(superuser={posture['is_superuser']}, bypassrls={posture['bypasses_rls']}). "
        f"Every query returns every tenant's rows while pg_policies and "
        f"pg_tables.rowsecurity both report isolation as active. "
        f"Fix: run `python -m app.cli.provision_db_roles` and point DATABASE_URL at "
        f"the non-superuser role."
    )

    if strict:
        raise IsolationPostureError(message)

    logger.error("[RLS][THEATRE] %s", message)
    return posture


#: Sets both GUCs in one round trip. `set_config(..., true)` is the function form
#: of ``SET LOCAL``: transaction-scoped, and — unlike ``SET LOCAL app.tenant_id =
#: 'x'`` — it accepts a bind parameter. The literal form cannot be parameterised
#: at all, which would mean formatting a tenant id into SQL text on every query.
#:
#: BOTH are written every time, even though a transaction-scoped setting cannot
#: survive its transaction. It costs nothing extra (same statement) and it means
#: the scope of a transaction is fully determined by this one call rather than
#: partly by whatever the previous holder of this pooled connection did.
_APPLY_SCOPE_SQL = "SELECT set_config(%s, %s, true), set_config(%s, %s, true)"


def scope_parameters(tenant_id: str | None, system: bool) -> tuple:
    """Bind parameters for `_APPLY_SCOPE_SQL` given a scope.

    The empty string is used for "not set" rather than NULL because
    `set_config` with a NULL value is an error, while `'' = 'on'` is simply
    false and `tenant_id = ''` matches no row — the fail-closed outcome.
    """
    if system:
        return (SYSTEM_SCOPE_GUC, SYSTEM_SCOPE_ON, TENANT_GUC, "")
    return (SYSTEM_SCOPE_GUC, "", TENANT_GUC, tenant_id or "")


def apply_scope(cur) -> None:
    """Bind the current transaction to the ambient scope.

    Must be the first statement of the transaction, before anything reads or
    writes a policy-protected table.

    Called from the two functions in ``storage/metadata_db`` that every metadata
    query goes through, and explicitly from the handful of places that open
    their own connection. It reads the scope from `app.tenant_context` rather
    than taking it as an argument, so no caller can pass a tenant that differs
    from the one the surrounding code believes it is acting for.
    """
    cur.execute(_APPLY_SCOPE_SQL, scope_parameters(current_tenant(), in_system_scope()))
