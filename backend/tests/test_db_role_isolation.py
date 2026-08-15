"""A2 — the application role must not be able to ignore row-level security.

What this file is defending
---------------------------
PostgreSQL exempts SUPERUSER and BYPASSRLS roles from row security
unconditionally, and `FORCE ROW LEVEL SECURITY` does not close that door (FORCE
only removes the table *owner's* exemption). So a deployment can have every
policy installed, `pg_tables.rowsecurity` true on every table, and still return
every tenant's rows to every query. Every configuration-level check goes green;
the behaviour is nil.

That state — "policies are theatre" — is the thing under test. Two groups:

* Unit tests run against fake connections and cover the decision logic, the
  provisioning DDL, and the DSN handling. They run anywhere.
* Integration tests need a live Postgres and assert on the real server: what the
  connected role actually is, and whether the policies really got installed.

Deliberately NOT asserted here: that queries return the right rows under RLS.
That is A3's proof set (`test_tenant_isolation.py`) and it needs the tenant GUC,
which this item does not introduce.
"""

from __future__ import annotations

import logging
import re

import pytest

from app.cli import provision_db_roles
from app.storage import rls
from app.storage.postgres_connection import RolePrivileges


# ---------------------------------------------------------------------------
# Fakes. A psycopg2 connection is a large interface and these tests need three
# methods of it, so a hand-rolled double is clearer here than a mock library:
# the queries are matched by substring, which keeps the double honest if the
# production SQL changes shape.
# ---------------------------------------------------------------------------


class _FakeCursor:
    def __init__(self, role_row, rls_rows):
        self._role_row = role_row
        self._rls_rows = rls_rows
        self._result = None

    def execute(self, sql, params=None):
        if "pg_roles" in sql and "current_user" in sql:
            self._result = [self._role_row]
        elif "pg_tables" in sql:
            self._result = list(self._rls_rows)
        elif "pg_roles" in sql:
            self._result = [(1,)] if params and params[0] == provision_db_roles.APP_ROLE else []
        else:  # pragma: no cover - guards against a silently unmatched query
            raise AssertionError(f"unexpected query: {sql}")

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result or [])

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, *, role="admin", superuser=True, bypassrls=True, rls_tables=()):
        self._role_row = (role, superuser, bypassrls)
        self._rls_rows = [(t,) for t in rls_tables]

    def cursor(self):
        return _FakeCursor(self._role_row, self._rls_rows)

    def close(self):
        pass


# ---------------------------------------------------------------------------
# Role privilege arithmetic
# ---------------------------------------------------------------------------


class TestRolePrivileges:
    def test_superuser_alone_bypasses_rls(self):
        """A superuser bypasses RLS even with rolbypassrls false.

        This is the trap: `rolbypassrls` reads false on the `admin` role of a
        default Postgres image, so a check that looked only at that column would
        report the role as contained. Superuser status alone is sufficient.
        """
        assert RolePrivileges("admin", True, False).can_bypass_rls is True

    def test_bypassrls_alone_is_enough(self):
        assert RolePrivileges("x", False, True).can_bypass_rls is True

    def test_plain_role_is_contained(self):
        assert RolePrivileges("voya_app", False, False).can_bypass_rls is False


# ---------------------------------------------------------------------------
# Posture: the combination that matters is (RLS on) AND (role bypasses)
# ---------------------------------------------------------------------------


class TestIsolationPosture:
    def test_policies_without_containment_is_theatre(self):
        conn = _FakeConn(role="admin", superuser=True, rls_tables=rls.RLS_TABLES)
        posture = rls.isolation_posture(conn)
        assert posture["rls_enabled"] is True
        assert posture["can_bypass_rls"] is True
        assert posture["policies_are_theatre"] is True

    def test_superuser_without_policies_is_not_theatre(self):
        """Honest pre-A3 state: no policies, superuser role, no false claim.

        Worth pinning explicitly — if this tripped the alarm, every deployment
        would be shouting from the day the check landed and operators would
        learn to ignore it, which is how a real alarm gets missed later.
        """
        conn = _FakeConn(role="admin", superuser=True, rls_tables=())
        assert rls.isolation_posture(conn)["policies_are_theatre"] is False

    def test_contained_role_with_policies_is_real(self):
        conn = _FakeConn(
            role="voya_app", superuser=False, bypassrls=False, rls_tables=rls.RLS_TABLES
        )
        posture = rls.isolation_posture(conn)
        assert posture["policies_are_theatre"] is False
        assert posture["rls_enabled"] is True

    def test_partial_rollout_still_counts_as_enabled(self):
        """One table with RLS and a bypassing role is already a false claim."""
        conn = _FakeConn(role="admin", superuser=True, rls_tables=("samples",))
        assert rls.isolation_posture(conn)["policies_are_theatre"] is True


class TestAssertIsolationEnforceable:
    def test_strict_mode_raises(self):
        conn = _FakeConn(role="admin", superuser=True, rls_tables=rls.RLS_TABLES)
        with pytest.raises(rls.IsolationPostureError) as exc:
            rls.assert_isolation_enforceable(conn, strict=True)
        # The message has to be actionable at 2am: name the role and the fix.
        assert "admin" in str(exc.value)
        assert "provision_db_roles" in str(exc.value)

    def test_non_strict_logs_error_and_returns(self, caplog):
        conn = _FakeConn(role="admin", superuser=True, rls_tables=rls.RLS_TABLES)
        with caplog.at_level(logging.ERROR, logger=rls.__name__):
            posture = rls.assert_isolation_enforceable(conn, strict=False)
        assert posture["policies_are_theatre"] is True
        assert any("THEATRE" in r.message for r in caplog.records)

    def test_healthy_posture_never_raises_in_strict_mode(self):
        conn = _FakeConn(
            role="voya_app", superuser=False, bypassrls=False, rls_tables=rls.RLS_TABLES
        )
        assert rls.assert_isolation_enforceable(conn, strict=True)["rls_enabled"] is True


# ---------------------------------------------------------------------------
# Provisioning DDL
# ---------------------------------------------------------------------------


class TestProvisioningStatements:
    @pytest.fixture
    def sql(self):
        return " ".join(s for s, _ in provision_db_roles._statements("voya_app", "pw"))

    def test_role_is_created_without_bypass_attributes(self, sql):
        assert "NOSUPERUSER" in sql
        assert "NOBYPASSRLS" in sql

    def test_never_grants_bypass(self, sql):
        """No statement may hand back the exemption the item exists to remove.

        The negative lookbehind is the whole test: `NOSUPERUSER` contains the
        substring `SUPERUSER`, so a plain `not in` check would pass on DDL that
        grants it and fail on DDL that revokes it — exactly backwards.
        """
        for attribute in ("SUPERUSER", "BYPASSRLS", "CREATEROLE", "CREATEDB"):
            assert re.search(rf"(?<!NO){attribute}", sql) is None

    def test_attributes_are_reasserted_on_every_run(self, sql):
        """ALTER ROLE, not just CREATE ROLE.

        An operator who once granted SUPERUSER by hand to debug something would
        otherwise leave the exemption in place forever: CREATE ROLE is skipped
        on re-run because the role exists, so nothing would ever take it back.
        """
        assert "ALTER ROLE" in sql and "NOSUPERUSER" in sql

    def test_grants_dml_but_no_ddl(self, sql):
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            assert privilege in sql
        assert "TRUNCATE" not in sql
        assert "GRANT ALL" not in sql
        assert "GRANT CREATE" not in sql

    def test_revokes_schema_create(self, sql):
        """PUBLIC held CREATE on `public` by default before PostgreSQL 15."""
        assert "REVOKE CREATE ON SCHEMA public" in sql

    def test_covers_tables_created_later(self, sql):
        """Without default privileges, tables added by a later deploy would be
        unreachable to the app role — a failure that shows up at runtime on one
        endpoint, long after the deploy that caused it."""
        assert "ALTER DEFAULT PRIVILEGES" in sql

    def test_password_is_a_bind_parameter(self):
        """A password formatted into SQL text would land in pg_stat_activity and
        in any statement log."""
        for stmt, params in provision_db_roles._statements("voya_app", "s3cret"):
            assert "s3cret" not in stmt
        assert any("s3cret" in (p or ()) for _, p in provision_db_roles._statements("voya_app", "s3cret"))


class TestAppDatabaseUrl:
    def test_keeps_host_port_and_database(self):
        url = provision_db_roles.app_database_url(
            "pw1234", template="postgresql://admin:admin@postgres:5432/signdb"
        )
        assert url == "postgresql://voya_app:pw1234@postgres:5432/signdb"

    def test_percent_encodes_the_password(self):
        """An unencoded '@' or '/' would silently repoint the DSN at another host
        or database rather than failing."""
        url = provision_db_roles.app_database_url(
            "p@ss/w:rd", template="postgresql://admin:admin@postgres:5432/signdb"
        )
        assert "@postgres:5432/signdb" in url
        assert "p%40ss%2Fw%3Ard" in url

    def test_drops_query_and_fragment(self):
        url = provision_db_roles.app_database_url(
            "pw", template="postgresql://admin:admin@h:1/db?sslmode=require#frag"
        )
        assert url == "postgresql://voya_app:pw@h:1/db"


# ---------------------------------------------------------------------------
# DSN split
# ---------------------------------------------------------------------------


class TestMigrationDsn:
    def test_falls_back_to_application_dsn(self, monkeypatch):
        """A deployment that has not split the roles must be unaffected."""
        from app.config import settings
        from app.storage import postgres_connection

        monkeypatch.setattr(settings, "migration_database_url", "", raising=False)
        assert postgres_connection.migration_dsn() == settings.database_url

    def test_uses_migration_url_when_set(self, monkeypatch):
        from app.config import settings
        from app.storage import postgres_connection

        monkeypatch.setattr(
            settings, "migration_database_url", "postgresql://m:m@h:5432/db", raising=False
        )
        assert postgres_connection.migration_dsn() == "postgresql://m:m@h:5432/db"

    def test_blank_string_is_treated_as_unset(self, monkeypatch):
        """Docker compose passes an unset variable through as an empty string, so
        `MIGRATION_DATABASE_URL=` must mean 'not split', not 'connect to ""'."""
        from app.config import settings
        from app.storage import postgres_connection

        monkeypatch.setattr(settings, "migration_database_url", "   ", raising=False)
        assert postgres_connection.migration_dsn() == settings.database_url


# ---------------------------------------------------------------------------
# RLS DDL shape
# ---------------------------------------------------------------------------


class TestRlsDdl:
    def test_every_tenant_scoped_table_has_a_policy(self):
        """The two lists must be equal, and until 2026-08-07 they were not.

        `TENANT_SCOPED_TABLES` is what carries a `tenant_id`;
        `RLS_TABLES` is what the database actually enforces. A table in the
        first and not the second has the column, has a foreign key, passes the
        deployment check that counts guarded tables — and is readable by every
        tenant. Nothing about it looks wrong.

        Asserting equality rather than containment on purpose: a policy on a
        table with no `tenant_id` cannot be created, so a name appearing only
        in `RLS_TABLES` would fail at boot and be swallowed into a log warning
        by `ensure_tables`.
        """
        from app.storage.metadata_db import TENANT_SCOPED_TABLES

        assert set(rls.RLS_TABLES) == set(TENANT_SCOPED_TABLES)

    def test_covers_every_declared_table(self):
        ddl = " ".join(rls.rls_ddl())
        for table in rls.RLS_TABLES:
            assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in ddl
            assert f"CREATE POLICY {rls.POLICY_NAME} ON {table}" in ddl

    def test_drops_before_creating(self):
        """Postgres allows several policies per table and ORs them together, so
        re-running without a DROP would stack duplicates and silently widen
        access rather than replace the policy."""
        for table in rls.RLS_TABLES:
            stmts = rls.policy_statements(table)
            drop = next(i for i, s in enumerate(stmts) if s.startswith("DROP POLICY"))
            create = next(i for i, s in enumerate(stmts) if s.startswith("CREATE POLICY"))
            assert drop < create

    def test_forces_rls_so_the_owner_is_not_exempt(self):
        ddl = " ".join(rls.rls_ddl())
        for table in rls.RLS_TABLES:
            assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in ddl

    def test_using_and_with_check_are_identical(self):
        """Different predicates would let a tenant either write rows it cannot
        read, or move a row out of its own partition."""
        stmt = next(s for s in rls.policy_statements("samples") if s.startswith("CREATE POLICY"))
        using = stmt.split("USING", 1)[1].split("WITH CHECK")[0].strip()
        check = stmt.split("WITH CHECK", 1)[1].strip()
        assert using == check

    def test_reads_gucs_with_missing_ok(self):
        """`current_setting(x)` raises when unset; `current_setting(x, true)`
        returns NULL. NULL makes the comparison false, which is what makes an
        unscoped connection see nothing instead of erroring — or, far worse,
        being special-cased into seeing everything."""
        stmt = next(s for s in rls.policy_statements("samples") if s.startswith("CREATE POLICY"))
        assert f"current_setting('{rls.TENANT_GUC}', true)" in stmt
        assert f"current_setting('{rls.SYSTEM_SCOPE_GUC}', true)" in stmt

    def test_system_scope_is_a_separate_guc_not_a_reserved_tenant_name(self):
        """The platform-wide escape hatch must not be expressible as a tenant id.

        `'on'` is a perfectly well-formed tenant id under `is_valid_tenant_id`.
        Had the policy said `tenant_id = 'on'` grants everything, then any tenant
        that happened to be named `on` — or a typo producing it — would silently
        acquire cross-tenant read access. Keeping the escape hatch in a different
        GUC makes that unreachable by any tenant value at all.
        """
        from app.tenancy import is_valid_tenant_id

        assert is_valid_tenant_id(rls.SYSTEM_SCOPE_ON), "premise of this test"
        assert rls.SYSTEM_SCOPE_GUC != rls.TENANT_GUC
        stmt = next(s for s in rls.policy_statements("samples") if s.startswith("CREATE POLICY"))
        assert f"tenant_id = '{rls.SYSTEM_SCOPE_ON}'" not in stmt


# ---------------------------------------------------------------------------
# Integration — needs the live database the rest of the suite already uses
# ---------------------------------------------------------------------------


def _live_conn():
    from app.storage.postgres_connection import connect_postgres

    try:
        return connect_postgres(connect_timeout=3)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no live Postgres: {exc}")


@pytest.mark.integration
class TestAgainstLiveDatabase:
    def test_reports_the_role_the_app_actually_connects_as(self):
        conn = _live_conn()
        try:
            from app.storage.postgres_connection import current_role_privileges

            privileges = current_role_privileges(conn)
            assert privileges.rolname
            # No assertion on WHICH role: this suite runs both before and after
            # the role split. What matters is that the answer is real and that
            # the boot check consumes it — see test_posture_is_self_consistent.
        finally:
            conn.close()

    def test_posture_is_self_consistent(self):
        conn = _live_conn()
        try:
            posture = rls.isolation_posture(conn)
            assert posture["policies_are_theatre"] == (
                posture["rls_enabled"] and posture["can_bypass_rls"]
            )
        finally:
            conn.close()

    def test_ensure_tables_installs_the_policies(self):
        """End-to-end: run the real migration path, then read pg_policies."""
        from app.storage.metadata_db import ensure_tables

        ensure_tables()
        conn = _live_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tablename FROM pg_policies "
                    "WHERE schemaname = 'public' AND policyname = %s",
                    (rls.POLICY_NAME,),
                )
                covered = {r[0] for r in cur.fetchall()}
            assert set(rls.RLS_TABLES) <= covered
        finally:
            conn.close()

    def test_strict_mode_would_refuse_this_database_when_bypassing(self):
        """Ties the unit logic to the real server: whatever this database's
        posture is, strict mode agrees with it."""
        conn = _live_conn()
        try:
            posture = rls.isolation_posture(conn)
            if posture["policies_are_theatre"]:
                with pytest.raises(rls.IsolationPostureError):
                    rls.assert_isolation_enforceable(conn, strict=True)
            else:
                rls.assert_isolation_enforceable(conn, strict=True)
        finally:
            conn.close()


class TestCliGuards:
    def test_refuses_missing_password(self, monkeypatch, capsys):
        # main() imports connect_migration at call time, so patching the module
        # it comes from is what takes effect.
        import app.storage.postgres_connection as pc

        monkeypatch.delenv(provision_db_roles.PASSWORD_ENV, raising=False)
        monkeypatch.setattr(pc, "connect_migration", lambda **_: _FakeConn())
        assert provision_db_roles.main([]) == 2
        assert provision_db_roles.PASSWORD_ENV in capsys.readouterr().err

    def test_refuses_short_password(self, monkeypatch, capsys):
        monkeypatch.setenv(provision_db_roles.PASSWORD_ENV, "short")
        import app.storage.postgres_connection as pc

        monkeypatch.setattr(pc, "connect_migration", lambda **_: _FakeConn())
        assert provision_db_roles.main([]) == 2
        assert "16 characters" in capsys.readouterr().err

    def test_refuses_when_not_superuser(self, monkeypatch, capsys):
        """Provisioning needs CREATE ROLE. Failing early with the reason beats a
        raw permission error twelve statements in."""
        monkeypatch.setenv(provision_db_roles.PASSWORD_ENV, "x" * 20)
        import app.storage.postgres_connection as pc

        monkeypatch.setattr(
            pc, "connect_migration", lambda **_: _FakeConn(role="voya_app", superuser=False)
        )
        assert provision_db_roles.main([]) == 3
        assert "cannot create roles" in capsys.readouterr().err


class TestCheckCommand:
    """`--check` must judge the RUNTIME connection, not the migration one.

    The first version connected only via `connect_migration()` — the DDL role,
    which is *required* to be a superuser. So on a correctly cut-over deployment
    it printed "policies are theatre" and exited 0: a permanent false alarm that
    also could never report the true failure. These tests pin both halves.
    """

    @staticmethod
    def _patch(monkeypatch, *, runtime, migration):
        import app.storage.postgres_connection as pc

        monkeypatch.setattr(pc, "connect_postgres", lambda **_: runtime)
        monkeypatch.setattr(pc, "connect_migration", lambda **_: migration)

    def test_superuser_migration_role_is_not_a_finding(self, monkeypatch, capsys):
        """The exact deployment that produced the false alarm: contained runtime
        role, superuser migration role, RLS installed. This must be clean."""
        self._patch(
            monkeypatch,
            runtime=_FakeConn(
                role="voya_app", superuser=False, bypassrls=False,
                rls_tables=rls.RLS_TABLES,
            ),
            migration=_FakeConn(role="admin", superuser=True, rls_tables=rls.RLS_TABLES),
        )
        assert provision_db_roles.main(["--check"]) == 0
        out = capsys.readouterr().out
        assert "in force" in out
        # Both are reported: hiding the migration role would trade a false alarm
        # for a blind spot.
        assert "voya_app" in out and "admin" in out

    def test_superuser_runtime_role_fails(self, monkeypatch, capsys):
        """The failure this command exists to catch — and used to report always."""
        self._patch(
            monkeypatch,
            runtime=_FakeConn(role="admin", superuser=True, rls_tables=rls.RLS_TABLES),
            migration=_FakeConn(role="admin", superuser=True, rls_tables=rls.RLS_TABLES),
        )
        assert provision_db_roles.main(["--check"]) == 3
        assert "RUNTIME role" in capsys.readouterr().err

    def test_policies_not_installed_fails(self, monkeypatch, capsys):
        """A contained role with no policies is not isolated either — it just
        cannot see the difference. Exiting 0 here would call an unprotected
        database safe."""
        self._patch(
            monkeypatch,
            runtime=_FakeConn(role="voya_app", superuser=False, bypassrls=False),
            migration=_FakeConn(role="admin", superuser=True),
        )
        assert provision_db_roles.main(["--check"]) == 3
        assert "row-level security" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Lớp 3 của việc cô lập bộ test: ranh giới quyền ở tầng PostgreSQL
# ---------------------------------------------------------------------------
#
# Lớp 1 đổi DSN (`scripts/run_tests.sh`), lớp 2 là cổng đích trong `conftest`.
# Cả hai là mã, và ngày 13/08/2026 đã chứng minh mã đó viết sai được: một hook
# của pytest chạy `migrate_database()` lên `signdb` sản xuất, áp một phần
# Billing v6 chưa hoàn chỉnh và đóng dấu một phiên bản không có thật.
#
# Lớp này không tin lớp nào ở trên: danh tính mà bộ test dùng KHÔNG có quyền
# CONNECT vào cơ sở dữ liệu sản xuất. DSN có trỏ nhầm thì PostgreSQL từ chối.

_PRODUCTION_DATABASE = "signdb"
_TEST_ROLE_PASSWORD_ENV = {
    "voya_test_app": "VOYA_TEST_APP_PASSWORD",
    "voya_test_owner": "VOYA_TEST_OWNER_PASSWORD",
}


def _server_address() -> tuple[str, int]:
    import os
    import urllib.parse

    parsed = urllib.parse.urlparse(os.environ["DATABASE_URL"])
    return parsed.hostname or "localhost", parsed.port or 5432


def _password_for(role: str) -> str:
    import os

    password = os.environ.get(_TEST_ROLE_PASSWORD_ENV[role], "")
    if not password:
        pytest.skip(
            f"chua cap phat role test ({_TEST_ROLE_PASSWORD_ENV[role]} trong). "
            f"Chay: sh scripts/provision_test_db_roles.sh")
    return password


def _try_connect(role: str, database: str):
    """Nối THẬT bằng đúng credential đó. Trả về None nếu được, lỗi nếu không."""
    import psycopg2

    host, port = _server_address()
    try:
        conn = psycopg2.connect(host=host, port=port, dbname=database,
                                user=role, password=_password_for(role),
                                connect_timeout=10)
    except psycopg2.OperationalError as exc:
        return exc
    conn.close()
    return None


@pytest.mark.integration
class TestTestRolesCannotReachProduction:
    """Đo bằng một lần kết nối thật, không bằng truy vấn danh mục dưới `admin`.

    `has_database_privilege()` trả lời câu hỏi danh mục. Câu hỏi thật là "một
    tiến trình pytest cầm credential này có mở được kết nối tới sản xuất
    không", và chỉ có cách thử mới trả lời được.
    """

    @pytest.mark.parametrize("role", ["voya_test_app", "voya_test_owner"])
    def test_a_test_role_is_refused_by_production(self, role):
        error = _try_connect(role, _PRODUCTION_DATABASE)

        assert error is not None, (
            f"{role} MO DUOC ket noi toi {_PRODUCTION_DATABASE}. Lop quyen "
            f"khong con, va hai lop tren deu la ma co the viet sai.")
        assert "permission denied for database" in str(error).lower(), (
            f"{role} bi tu choi, nhung KHONG phai vi quyen: {error}")

    @pytest.mark.parametrize("role", ["voya_test_app", "voya_test_owner"])
    def test_a_test_role_is_accepted_by_the_test_database(self, role):
        """Đối chứng dương, và nó là thứ làm hai test trên có nghĩa.

        Không có nó, một mật khẩu sai cũng làm test kia xanh — lúc đó ta đang
        chứng minh "credential hỏng" chứ không phải "ranh giới quyền có thật".
        """
        import os

        database = os.environ.get("POSTGRES_DB", "signdb_test")
        assert _try_connect(role, database) is None


@pytest.mark.integration
class TestSuiteRunsUnderTheTestApplicationRole:
    """Vai chạy bộ test phải phản chiếu vai runtime, nếu không suite RLS xanh giả."""

    def test_the_suite_connects_as_the_test_application_role(self):
        from app.storage.metadata_db import _cursor

        with _cursor() as cur:
            cur.execute("SELECT current_user")
            assert cur.fetchone()[0] == "voya_test_app"

    @pytest.mark.parametrize("role", ["voya_test_app", "voya_test_owner"])
    def test_a_test_role_matches_runtime_rls_properties(self, role):
        """Bốn thuộc tính, và mỗi cái chặn một kiểu hỏng khác nhau.

        `rolbypassrls` là cái nguy hiểm nhất: bật nó lên thì MỌI test RLS xanh
        mà không kiểm được gì — một kiểu hỏng không để lại dấu vết nào trong
        kết quả chạy.

        `rolcreaterole` phải tắt ở CẢ HAI vai, kể cả vai chủ sở hữu. Đó là thứ
        làm cho "conftest không thể tự cấp phát hạ tầng" trở thành một sự thật
        của PostgreSQL chứ không phải một quy ước — và chuỗi sự cố vừa rồi xảy
        ra đúng vì một hook khởi động có nhiều quyền hơn việc nó cần làm.

        `rolcreatedb` thì KHÁC, và bản đầu của phép kiểm này gộp nhầm hai thứ.
        Vai chủ sở hữu cần nó: `test_tenant_isolation.py` dựng một cơ sở dữ
        liệu nháp cho mỗi module để cài chính sách RLS thật lên đó, và không
        chạy chung cơ sở dữ liệu được vì phép kiểm đụng tới chính các câu DDL
        sửa chính sách.

        Hai quyền này không cùng hạng về hậu quả:

          * CREATEDB sinh ra cơ sở dữ liệu RỖNG từ `template1`. Nó không mở
            đường nào tới `signdb` — CONNECT đã bị thu hồi, và nhân bản bằng
            TEMPLATE cũng không đi được vì `signdb` không phải template và
            thuộc `admin`. Kiểm ở `TestTestRolesCannotReachProduction`.
          * CREATEROLE cho đổi mật khẩu của một vai không-superuser KHÁC, kể cả
            `voya_app` — vai duy nhất còn CONNECT được vào sản xuất. Đó là một
            đường leo thang thật, chỉ hai bước, nên nó ở lại danh sách cấm.
        """
        from app.storage.metadata_db import _migration_cursor

        with _migration_cursor() as cur:
            cur.execute(
                "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb "
                "FROM pg_roles WHERE rolname = %s", (role,))
            row = cur.fetchone()

        assert row is not None, f"chua cap phat {role}"
        super_, bypassrls, createrole, createdb = row
        assert (super_, bypassrls, createrole) == (False, False, False), (
            f"{role} mang quyen no khong duoc co: super={super_} "
            f"bypassrls={bypassrls} createrole={createrole}")
        # Đúng một vai được phép, và phải là vai chủ sở hữu: vai ỨNG DỤNG chạy
        # phần lớn bộ kiểm, và nó phải giống hệt `voya_app` trên sản xuất.
        expected_createdb = role == "voya_test_owner"
        assert createdb is expected_createdb, (
            f"{role}: createdb={createdb}, mong doi {expected_createdb}")

    def test_migration_runs_under_a_different_identity(self):
        """Vai migration sở hữu bảng (ALTER TABLE đòi sở hữu); vai ứng dụng thì
        không được. Trộn hai vai làm một là cho đường ghi của ứng dụng quyền
        đổi hình dạng lược đồ."""
        import os
        import urllib.parse

        migration_user = urllib.parse.urlparse(
            os.environ.get("MIGRATION_DATABASE_URL", "")).username
        runtime_user = urllib.parse.urlparse(os.environ["DATABASE_URL"]).username

        assert migration_user == "voya_test_owner"
        assert runtime_user == "voya_test_app"
        assert migration_user != runtime_user


# ---------------------------------------------------------------------------
# Danh mục toàn cục không được thành đường ghi vào dữ liệu của tenant
# ---------------------------------------------------------------------------


class TestGlobalCatalogueIsNotAWritePath:
    """RLS KHÔNG thay thế GRANT/REVOKE — và đây là bằng chứng thực nghiệm.

    Lỗ tìm được 14/08: `voya_app` có đủ bốn quyền trên `regions` và `languages`
    vì `provision_db_roles` cấp `ON ALL TABLES`. Hai bảng đó không mang
    `tenant_id` nên nằm ngoài RLS — đúng, chúng không phải dữ liệu của ai.
    Nhưng `classes` trỏ tới cả hai bằng khoá ngoại, nên một câu

        UPDATE regions SET code = ...

    ghi lại `classes` của MỌI tenant, mà lượt ghi đó không chạm bảng `classes`
    nên không policy nào của nó được hỏi tới.

    Bài học đặt tên được để còn rà: một bảng KHÔNG chứa dữ liệu tenant vẫn là
    ranh giới cô lập, nếu thao tác trên nó làm thay đổi được dữ liệu thuộc về
    tenant. Gọi là ĐƯỜNG GHI BẮC CẦU.
    """

    def test_the_app_role_can_only_read_the_reference_catalogues(self):
        """Ngược chiều với `REFERENCE_TABLES`: đọc quyền THẬT trong cơ sở dữ
        liệu, không đọc lại danh sách trong mã.

        Khuôn hiện tại là "GRANT rộng rồi REVOKE ngoại lệ", nên người thêm một
        danh mục mới (`countries`, `license_types`, …) rất dễ quên khoá ghi.
        Phép kiểm này là thứ bắt họ.
        """
        from app.cli.provision_db_roles import REFERENCE_TABLES
        from app.storage.metadata_db import _cursor

        with _cursor() as cur:
            cur.execute("SELECT current_user")
            app_role = cur.fetchone()[0]
            cur.execute(
                "SELECT table_name, privilege_type "
                "  FROM information_schema.role_table_grants "
                " WHERE grantee = %s AND table_name = ANY(%s)",
                (app_role, list(REFERENCE_TABLES)),
            )
            cap = {}
            for bang, quyen in cur.fetchall():
                cap.setdefault(bang, set()).add(quyen)

        for bang in REFERENCE_TABLES:
            co = cap.get(bang, set())
            assert "SELECT" in co, f"{app_role} không đọc được {bang}"
            thua = co & {"INSERT", "UPDATE", "DELETE"}
            assert not thua, (
                f"{app_role} GHI được danh mục toàn cục {bang}: {sorted(thua)}. "
                f"Sửa danh mục là việc của vai migration — xem REFERENCE_TABLES.")

    def test_no_direct_global_to_tenant_fk_cascade(self):
        """Bất biến CẤU TRÚC cho khoá ngoại TRỰC TIẾP, một cạnh.

        Tên hàm nói đúng phạm vi, và đó là chủ ý. Bộ kiểm này KHÔNG chứng minh
        "không tồn tại mọi đường ghi bắc cầu" — nó chỉ soi đúng một hình dạng:

            bảng KHÔNG có tenant_id  --FK ON UPDATE CASCADE-->  bảng CÓ tenant_id

        Những hình dạng nó KHÔNG thấy, và người sau đừng tưởng đã được phủ:
        cascade nhiều chặng (toàn cục A → toàn cục B → tenant C), trigger, hàm
        lưu sẵn, `ON DELETE CASCADE`, và mọi cơ chế đồng bộ hoá ở tầng ứng dụng.
        Lược đồ hiện tại chưa có những đường đó, nên chưa mở rộng; nhưng
        "đã kiểm một lớp nguy cơ" khác hẳn "đã chứng minh không còn đường nào".

        Thu quyền chặn được vai ứng dụng; `ON UPDATE RESTRICT` chặn thêm cả mã
        chạy dưới vai migration. Hai lớp cho cùng một lỗi, vì nó im lặng.

        `code` là ĐỊNH DANH MÁY, không phải nhãn hiển thị — `bac` cố định, còn
        `name_vi` mới là thứ người ta đổi. Nên cascade ở đây gần như không có
        công dụng thật, chỉ có rủi ro.
        """
        from app.storage.metadata_db import _migration_cursor

        # NGOẠI LỆ TẠM THỜI ĐÃ RÀ, KHÔNG PHẢI KIẾN TRÚC ĐƯỢC CHẤP NHẬN.
        #
        # `plans` không thể là chỉ-đọc: endpoint quản trị bảng giá cần ghi thật.
        # Nhưng cascade ở đây cũng KHÔNG phải thứ nghiệp vụ đang dựa vào — lượt
        # đổi mã gói v6 tự `UPDATE tenants` và `UPDATE tenant_subscriptions`
        # bằng câu riêng. Nó chỉ là một đường ghi thứ hai.
        #
        # `plans.code` là định danh máy bền, y như `regions.code`. Một endpoint
        # quản trị chạy `UPDATE plans SET code='school-v2' WHERE code='school'`
        # không nên có quyền âm thầm viết lại trạng thái đăng ký của TOÀN hệ
        # thống chỉ nhờ khoá ngoại. Với tính cước thì càng phải ép việc đổi mã
        # thành một migration có chủ ý.
        #
        # ĐIỀU KIỆN GỠ: có bộ kiểm hồi quy cho lượt đổi mã gói, rồi chuyển cả
        # hai sang ON UPDATE RESTRICT và xoá hẳn danh sách này.
        DUOC_PHEP = {"fk_tenants_plan", "tenant_subscriptions_plan_code_fkey"}

        with _migration_cursor() as cur:
            cur.execute("""
                WITH fk AS (
                  SELECT c.conname, c.confupdtype,
                         src.relname AS con, tgt.relname AS cha
                    FROM pg_constraint c
                    JOIN pg_class src ON src.oid = c.conrelid
                    JOIN pg_class tgt ON tgt.oid = c.confrelid
                   WHERE c.contype = 'f'
                ), co_tenant AS (
                  SELECT c.relname FROM pg_class c
                    JOIN pg_attribute a ON a.attrelid = c.oid
                   WHERE a.attname = 'tenant_id' AND a.attnum > 0
                     AND NOT a.attisdropped
                )
                SELECT conname, cha, con FROM fk
                 WHERE confupdtype = 'c'
                   AND cha NOT IN (SELECT relname FROM co_tenant)
                   AND con IN (SELECT relname FROM co_tenant)
            """)
            duong = [(r[0], r[1], r[2]) for r in cur.fetchall()]

        la = [d for d in duong if d[0] not in DUOC_PHEP]
        assert not la, (
            "đường ghi bắc cầu MỚI từ bảng toàn cục vào dữ liệu tenant: "
            + ", ".join(f"{c} ({cha} -> {con} qua {c})" for c, cha, con in la)
            + ". Đổi sang ON UPDATE RESTRICT, hoặc thêm vào DUOC_PHEP kèm lý do.")
