"""`tenant_id` must reference a real tenant — enforced by the database.

Twelve tables carried a `tenant_id` and NOT ONE had a foreign key. A typo was
accepted everywhere and surfaced, if ever, as rows nobody could reach.

`clone_catalog_to_tenant` is where that turned into data loss rather than
clutter: it writes a whole catalogue keyed by `tenant_id`, then records the
provenance with `UPDATE tenants SET cloned_from_community_version WHERE
tenant_id = ...`. For an id that does not exist the catalogue half succeeds and
the provenance half matches zero rows — a tenant whose registry exists but whose
origin is unanswerable, with nothing raised.

routers/vocabulary.py checks before writing. These tests are about the other
layer: the database refusing regardless of which code path is used, including
ones written later by someone who never read that router.

Runs against the real Postgres. Every test cleans up inside a transaction it
rolls back itself, so no row survives a failure.
"""

from __future__ import annotations

import uuid

import psycopg2
import pytest

from app.storage import metadata_db as db


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


# ---------------------------------------------------------------- presence

def test_every_tenant_scoped_table_is_guarded():
    """The list is the assertion: a new tenant-scoped table added without a
    foreign key fails here rather than years later."""
    assert db.missing_tenant_foreign_keys() == []


def test_the_table_list_matches_what_the_database_actually_has():
    """`TENANT_SCOPED_TABLES` is the single source for both the migration and
    the audit. If a table grows a `tenant_id` column without being listed, the
    migration never guards it and the audit never notices — so compare the
    constant against the catalogue instead of trusting it."""
    # Chỉ BẢNG NỀN. `information_schema.columns` kể cả cột của VIEW, và
    # `tenant_members` giờ là một view trên `memberships` (PDM v5) mang cột
    # `tenant_id`. Không gắn được khoá ngoại lên view — Postgres từ chối — nên
    # bắt nó xuất hiện ở đây là đòi một thứ không tồn tại, và cách "sửa" duy
    # nhất sẽ là thêm nó vào `TENANT_SCOPED_TABLES` rồi để vòng lặp migration
    # thất bại lặng lẽ ở mỗi lần khởi động.
    #
    # Dữ liệu của view VẪN được canh, chỉ là canh ở đúng chỗ: `memberships` có
    # trong danh sách và nhận cả khoá ngoại lẫn RLS.
    rows = db._fetch_all(
        "SELECT c.table_name FROM information_schema.columns c "
        "  JOIN pg_tables t ON t.schemaname = c.table_schema "
        "                  AND t.tablename = c.table_name "
        "WHERE c.table_schema = 'public' AND c.column_name = 'tenant_id' "
        "AND c.table_name <> 'tenants'"
    )
    # `tenant_purges` mang `tenant_id` nhưng CỐ Ý đứng ngoài danh sách: nó ghi
    # lại việc một tenant đã bị xoá vĩnh viễn, nên một khoá ngoại tới `tenants`
    # sẽ khiến chính hành động nó tồn tại để ghi lại trở nên bất khả thi. Ở đây
    # `tenant_id` là chữ, là dấu vết, không phải một liên kết. Xem
    # `app/tenant_lifecycle.py` và `test_schema_v4.py`.
    # `roles` cũng đứng ngoài, nhưng vì lý do NGƯỢC LẠI: nó CÓ khoá ngoại tới
    # `tenants` (`fk_roles_tenant`), chỉ là khoá ấy được khai tường minh trong
    # `authz_schema` với ON DELETE CASCADE thay vì do vòng lặp
    # `TENANT_FK_LOOP_SQL` gắn với RESTRICT.
    #
    # Khác biệt đó là chủ ý: `tenant_id` của `roles` NULLABLE, và NULL nghĩa là
    # "role dựng sẵn của nền tảng, mọi tenant dùng chung". Một role do tenant
    # tự tạo thì chết theo tenant (CASCADE); một role nền tảng thì không thuộc
    # tenant nào để mà chết theo. RESTRICT ở đây sẽ khiến xoá tenant thất bại
    # chừng nào họ còn một role tự tạo — tức là biến việc dọn dẹp thành thủ công.
    #
    # Nó cũng KHÔNG chịu chính sách tenant chuẩn mà chịu chính sách danh mục
    # dùng chung (`rls.SHARED_CATALOGUE_TABLES`), nơi USING rộng hơn WITH CHECK.
    DELIBERATELY_UNLINKED = {"tenant_purges", "roles"}

    actual = {r["table_name"] for r in rows}
    unlisted = sorted(actual - set(db.TENANT_SCOPED_TABLES) - DELIBERATELY_UNLINKED)
    assert not unlisted, (
        f"these tables carry tenant_id but are not in TENANT_SCOPED_TABLES, so "
        f"nothing adds a foreign key to them: {unlisted}"
    )


# ---------------------------------------------------------------- enforcement

@pytest.fixture
def rollback_cursor():
    """A cursor whose work is always rolled back — these tests write on purpose.

    Bound to SYSTEM scope, and that is load-bearing rather than convenience.
    `dialects` gained a row-level policy on 2026-08-07, and an unscoped
    connection now fails the `WITH CHECK` before the foreign key is ever
    consulted. These tests would still have gone red-then-green — but green for
    the wrong reason: `InsufficientPrivilege` instead of `ForeignKeyViolation`,
    with the constraint under test no longer exercised at all. Scoping the
    cursor puts the FK back in the path.
    """
    from app.storage.rls import apply_scope
    from app.tenant_context import system_scope

    conn = psycopg2.connect(db.settings.database_url)
    conn.autocommit = False
    try:
        with system_scope("test: exercise FK constraints across tenants"):
            with conn.cursor() as cur:
                apply_scope(cur)
                yield cur
    finally:
        conn.rollback()
        conn.close()


def test_a_typoed_tenant_id_is_refused(rollback_cursor):
    """The exact shape of the clone bug: 'defualt' instead of 'default'."""
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        rollback_cursor.execute(
            "INSERT INTO dialects(tenant_id, dialect_id, display_name) "
            "VALUES('defualt', %s, 'X')", (f"t{uuid.uuid4().hex[:6]}",))


def test_deleting_a_tenant_cannot_take_its_data_with_it(rollback_cursor):
    """ON DELETE RESTRICT, never CASCADE.

    `tenants` soft-deletes (`deleted_at`), so a hard DELETE is already a
    mistake — CASCADE would turn that mistake into the silent loss of every
    class, sample and upload the tenant owns.
    """
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        rollback_cursor.execute("DELETE FROM tenants WHERE tenant_id = 'default'")


def test_renaming_a_tenant_id_is_refused(rollback_cursor):
    """ON UPDATE RESTRICT for the same reason `dialect_id` is immutable: the id
    names directories and published artifacts, so cascading a rename through the
    database would leave the filesystem pointing at nothing."""
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        rollback_cursor.execute(
            "UPDATE tenants SET tenant_id = 'renamed' WHERE tenant_id = 'default'")


def test_a_real_tenant_is_accepted(rollback_cursor):
    """The constraint must refuse typos without refusing legitimate work."""
    tid = f"test-{uuid.uuid4().hex[:8]}"
    rollback_cursor.execute(
        "INSERT INTO tenants(tenant_id, display_name, slug) VALUES(%s, %s, %s)",
        (tid, "Thử", tid))
    rollback_cursor.execute(
        "INSERT INTO dialects(tenant_id, dialect_id, display_name) VALUES(%s, %s, %s)",
        (tid, "vn-test", "Thử"))
    rollback_cursor.execute(
        "SELECT COUNT(*) FROM dialects WHERE tenant_id = %s", (tid,))
    assert rollback_cursor.fetchone()[0] == 1


# ---------------------------------------------------------------- migration

def test_the_migration_builds_its_sql_from_the_constant():
    """Guards against the failure this repo keeps repeating: a second copy of a
    list that drifts. The table names in the DDL must come from
    TENANT_SCOPED_TABLES, not be typed out again beside it."""
    stmts = [s for s in db.MIGRATION_STATEMENTS if "fk_' || t || '_tenant" in s]
    assert len(stmts) == 2, (
        "expected the tenant foreign-key loop exactly twice — once at its "
        "historical position and once at the very end. Schema v3 creates six "
        "tenant-scoped tables at the tail of MIGRATION_STATEMENTS, so on a "
        "FRESH database the first pass walks past names that do not exist yet "
        "and they are born without a tenant foreign key. Emitting the same "
        "constant a second time fixes that in one boot instead of two."
    )
    assert len(set(stmts)) == 1, (
        "both emissions must be the SAME constant (TENANT_FK_LOOP_SQL). Two "
        "hand-written copies would drift, which is the exact failure the test "
        "above exists to prevent."
    )
    sql = stmts[0]
    for table in db.TENANT_SCOPED_TABLES:
        assert f"'{table}'" in sql, f"{table} missing from the generated migration"


def test_running_the_loop_twice_is_free():
    """The second emission must be a no-op, not a second ALTER attempt."""
    assert "CONTINUE WHEN EXISTS (SELECT 1 FROM pg_constraint WHERE conname = name)" \
        in db.TENANT_FK_LOOP_SQL


def test_the_migration_never_cascades():
    stmts = [s for s in db.MIGRATION_STATEMENTS if "fk_' || t || '_tenant" in s]
    sql = stmts[0]
    assert "ON DELETE RESTRICT" in sql and "ON UPDATE RESTRICT" in sql
    assert "CASCADE" not in sql.split("FOREIGN KEY")[-1]
