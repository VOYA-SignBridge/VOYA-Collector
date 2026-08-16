"""Create the non-superuser application role that row-level security needs.

Why this command exists
-----------------------
The stack shipped connecting as ``admin``, which is both SUPERUSER and
BYPASSRLS. PostgreSQL exempts such roles from row security unconditionally:

    Superusers and roles with the BYPASSRLS attribute always bypass the row
    security system when accessing a table.

``ALTER TABLE ... FORCE ROW LEVEL SECURITY`` does not help — FORCE only removes
the *table owner's* exemption, not a superuser's. So installing policies while
the application still connects as ``admin`` produces a deployment where
``pg_policies`` lists every policy, ``pg_tables.rowsecurity`` is true on every
table, and every query still returns every tenant's rows. Configuration-level
verification goes green against zero actual isolation.

What it provisions
------------------
Two roles with disjoint powers:

  voya_app       LOGIN, NOSUPERUSER, NOBYPASSRLS, no DDL. What the application,
                 the workers and the SOT reader connect as. Can read and write
                 rows; cannot alter a table, and therefore cannot turn off the
                 policies that contain it.

  (migration)    The existing superuser, kept as-is and used only through
                 MIGRATION_DATABASE_URL for `ensure_tables()` and this command.

The separation is the point. A single role that can both write rows and run DDL
can revoke its own containment, which makes the containment advisory rather than
enforced.

Usage
-----
    # provision (idempotent; safe to re-run)
    VOYA_APP_DB_PASSWORD=... python -m app.cli.provision_db_roles

    # inspect without changing anything (reports BOTH DSNs; fails on a bad
    # runtime posture, so it is usable as a deployment gate)
    python -m app.cli.provision_db_roles --check

Exit codes: 0 ok, 2 bad usage/config, 3 posture unsafe / cannot provision.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional
from urllib.parse import quote, urlsplit, urlunsplit

from app.storage import control_plane as cp

logger = logging.getLogger("db.roles")

#: Role the application authenticates as at runtime.
APP_ROLE = "voya_app"

#: Environment variable carrying the password for APP_ROLE. Not a CLI flag: a
#: password passed as an argument lands in the shell history and in the process
#: list of every other user on the host.
PASSWORD_ENV = "VOYA_APP_DB_PASSWORD"

#: Mật khẩu vai ĐIỀU KHIỂN. Phải KHÁC mật khẩu vai ứng dụng: hai danh tính dùng
#: chung một bí mật thì ranh giới tin cậy chỉ tồn tại trên giấy — ai đọc được
#: một cái là có cái kia.
CONTROL_PASSWORD_ENV = "VOYA_CONTROL_DB_PASSWORD"

#: Object privileges the application role needs, and nothing beyond them.
#: Note the absence of TRUNCATE and REFERENCES: both are close enough to DDL to
#: be worth withholding, and no code path uses either.
TABLE_PRIVILEGES = "SELECT, INSERT, UPDATE, DELETE"

#: Danh mục THAM CHIẾU toàn cục: vai ứng dụng chỉ được ĐỌC.
#:
#: Chúng không mang `tenant_id` nên không nằm trong phạm vi RLS, và đó là đúng
#: — `bac` hay `vn` không phải dữ liệu của ai. Nhưng "ngoài RLS" cộng với
#: "ghi được" thì thành một đường vòng thật, không phải rủi ro lý thuyết:
#:
#:   classes.region   -> regions(code)     ON UPDATE CASCADE
#:   classes.language -> languages(code)   ON UPDATE CASCADE
#:
#: Một câu `UPDATE regions SET code = ...` chạy dưới vai ứng dụng sẽ ghi lại
#: `classes` của MỌI tenant cùng lúc — và lượt ghi đó KHÔNG chạm bảng
#: `classes`, nên không policy nào của nó được hỏi tới. Cô lập tenant bị đi
#: vòng qua một bảng mà bản thân nó chẳng chứa dữ liệu tenant nào.
#:
#: `DELETE` cũng phải chặn: xoá một mã đang được tham chiếu sẽ bị khoá ngoại từ
#: chối, nhưng xoá một mã CHƯA ai dùng thì lọt, và nó âm thầm thu hẹp tập giá
#: trị hợp lệ của mọi tenant.
#:
#: Sửa danh mục là việc của vai migration. Thêm bảng tham chiếu mới thì thêm
#: tên vào đây — `tests/test_db_role_isolation.py` canh danh sách này.
REFERENCE_TABLES: tuple[str, ...] = ("regions", "languages")


def _statements(role: str, password: str) -> list[tuple[str, tuple]]:
    """Idempotent provisioning DDL, in dependency order.

    CREATE ROLE has no IF NOT EXISTS, hence the DO block. The password is always
    (re)set so re-running after a rotation converges rather than leaving the old
    one in place — this command is the single definition of the role's state.
    """
    quoted = f'"{role}"'
    return [
        (
            "DO $$ BEGIN "
            "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s) THEN "
            f"    CREATE ROLE {quoted} LOGIN NOSUPERUSER NOBYPASSRLS "
            "        NOCREATEDB NOCREATEROLE NOREPLICATION; "
            "  END IF; "
            "END $$",
            (role,),
        ),
        # Re-asserted on every run, not only at creation: an operator who once
        # granted SUPERUSER by hand to debug something would otherwise leave the
        # exemption in place permanently, and nothing would report it.
        (f"ALTER ROLE {quoted} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE", ()),
        (f"ALTER ROLE {quoted} PASSWORD %s", (password,)),
        (f"GRANT USAGE ON SCHEMA public TO {quoted}", ()),
        (f"GRANT {TABLE_PRIVILEGES} ON ALL TABLES IN SCHEMA public TO {quoted}", ()),
        (f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted}", ()),
        # Tables created later (ensure_tables adds some on every deploy) would
        # otherwise be unreachable by the app role until someone re-ran the
        # GRANT above — a failure that appears at runtime, on one endpoint, long
        # after the deploy that caused it.
        (
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT {TABLE_PRIVILEGES} ON TABLES TO {quoted}",
            (),
        ),
        (
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT USAGE, SELECT ON SEQUENCES TO {quoted}",
            (),
        ),
        # CREATE on the schema is what would let the app role add objects; it is
        # revoked explicitly rather than merely not granted, because PUBLIC held
        # it by default on PostgreSQL 14 and older.
        (f"REVOKE CREATE ON SCHEMA public FROM {quoted}", ()),
        # Thu lại quyền GHI trên các danh mục tham chiếu. Phải đứng SAU câu
        # `GRANT ... ON ALL TABLES` ở trên, vì câu đó quét cả những bảng này —
        # xem REFERENCE_TABLES để biết vì sao ghi được chúng là một đường vòng
        # qua cô lập tenant.
        *[
            (f"REVOKE INSERT, UPDATE, DELETE ON {t} FROM {quoted}", ())
            for t in REFERENCE_TABLES
        ],
        # Bảng MẶT PHẲNG ĐIỀU KHIỂN: vai ứng dụng không có quyền nào, chấm hết.
        # Cùng vị trí và cùng lý do với `REFERENCE_TABLES` ở trên — phải đứng
        # SAU `GRANT ... ON ALL TABLES`, vì câu đó quét cả chúng.
        #
        # Xem `app/storage/control_plane.py` về vì sao `tenant_purges` là bảo vệ
        # theo QUYỀN chứ không theo RLS.
        *[(sql, ()) for sql in cp.revoke_from_app_statements(role)],
    ]


def _control_statements(role: str, password: str) -> list[tuple[str, tuple]]:
    """Vai ĐIỀU KHIỂN. Khác vai ứng dụng ở chỗ nó KHÔNG được cấp gì hàng loạt.

    Không `GRANT ... ON ALL TABLES`, không `ALTER DEFAULT PRIVILEGES`. Vai này
    chỉ chạm đúng những bảng đã khai báo ở `CONTROL_PLANE_TABLES`, nên một bảng
    mới sinh ra sau này KHÔNG tự động vào tầm với của nó — ngược hẳn với vai
    ứng dụng, nơi mặc-định-cấp là đúng vì nó phục vụ mọi request.

    Thuộc tính vai giống hệt vai ứng dụng: NOSUPERUSER, NOBYPASSRLS, NOCREATEDB,
    NOCREATEROLE, NOREPLICATION. Đây KHÔNG phải một vai quản trị mới — nó chỉ là
    một danh tính mang một tập năng lực điều khiển nhỏ.
    """
    quoted = f'"{role}"'
    return [
        (
            "DO $$ BEGIN "
            "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s) THEN "
            f"    CREATE ROLE {quoted} LOGIN NOSUPERUSER NOBYPASSRLS "
            "        NOCREATEDB NOCREATEROLE NOREPLICATION; "
            "  END IF; "
            "END $$",
            (role,),
        ),
        (f"ALTER ROLE {quoted} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE", ()),
        (f"ALTER ROLE {quoted} PASSWORD %s", (password,)),
        (f"GRANT USAGE ON SCHEMA public TO {quoted}", ()),
        (f"REVOKE CREATE ON SCHEMA public FROM {quoted}", ()),
        *[(sql, ()) for sql in cp.grant_to_control_statements(role)],
    ]


def app_database_url(password: str, template: Optional[str] = None) -> str:
    """The DATABASE_URL to deploy, derived from the current one.

    Keeps host, port and database name from the existing DSN so the operator
    changes exactly one thing — the credentials — rather than retyping a URL and
    silently pointing the app at a different database.
    """
    from app.config import settings

    parts = urlsplit(template or settings.database_url)
    host = parts.hostname or "postgres"
    netloc = f"{APP_ROLE}:{quote(password, safe='')}@{host}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def check(conn) -> dict:
    """Report the isolation posture of `conn` without changing anything."""
    from app.storage.postgres_connection import current_role_privileges
    from app.storage.rls import isolation_posture

    posture = isolation_posture(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
        posture["app_role_exists"] = cur.fetchone() is not None
    posture["connected_as"] = current_role_privileges(conn).rolname
    return posture


#: SQLSTATE 42501. Bắt theo mã chứ không theo lớp ngoại lệ: tệp này nhận `conn`
#: từ bên ngoài và cố ý không phụ thuộc vào một driver cụ thể.
_INSUFFICIENT_PRIVILEGE = "42501"

#: Bốn thuộc tính mà câu `ALTER ROLE ... NOSUPERUSER ...` đặt. Giữ thành hằng số
#: để phép kiểm "trạng thái mong muốn đã đúng chưa" không lệch khỏi câu lệnh.
_ROLE_ATTRIBUTES = ("rolsuper", "rolbypassrls", "rolcreatedb", "rolcreaterole")


def _desired_attributes_already_hold(cur, role: str) -> bool:
    cur.execute(
        f"SELECT {', '.join(_ROLE_ATTRIBUTES)} FROM pg_roles WHERE rolname = %s",
        (role,),
    )
    row = cur.fetchone()
    return row is not None and not any(row)


def provision(conn, password: str) -> None:
    """Tạo/sửa vai ứng dụng. Idempotent.

    Vì sao hai câu `ALTER ROLE` được phép thất bại
    ----------------------------------------------
    Vai là đối tượng của CẢ CỤM, không thuộc cơ sở dữ liệu nào; còn các GRANT
    bên dưới thì thuộc về cơ sở dữ liệu đang kết nối. Nên khi hàm này chạy lần
    thứ hai — trên một cơ sở dữ liệu KHÁC, để cấp quyền bảng ở đó — vai đã tồn
    tại sẵn với đúng thuộc tính cần có, và hai câu `ALTER ROLE` không còn việc
    gì để làm ngoài việc đòi quyền SUPERUSER.

    Đó chính là tình huống của `test_tenant_isolation.py`: nó dựng một cơ sở dữ
    liệu nháp rồi gọi hàm này để cấp quyền bảng trong đó. Bắt nó phải có một
    danh tính superuser chỉ để chạy lại hai câu lệnh vô tác dụng là đánh đổi
    toàn bộ lớp cô lập lấy không gì cả.

    Nới lỏng này KHÔNG che được sự cố mà câu lệnh tồn tại để chữa. Ta chỉ bỏ
    qua khi trạng thái mong muốn ĐÃ đúng, đo bằng `pg_roles`. Nếu ai đó thật sự
    cấp SUPERUSER cho vai ứng dụng thì `_desired_attributes_already_hold` trả
    về False và lỗi thiếu quyền được ném lại nguyên vẹn — vẫn phải có người
    superuser vào sửa, đúng như trước.
    """
    _apply(conn, _statements(APP_ROLE, password), APP_ROLE)
    logger.info("[DB_ROLES] role %s provisioned", APP_ROLE)


def provision_control(conn, password: str) -> None:
    """Tạo/sửa vai ĐIỀU KHIỂN. Idempotent, cùng nới lỏng savepoint như trên.

    Tách khỏi `provision()` chứ không thêm cờ: hai vai có hình dạng quyền khác
    hẳn nhau (một bên cấp hàng loạt, một bên cấp đúng bảng), và gộp chúng sau
    một tham số boolean là cách chắc chắn nhất để một ngày nào đó vai điều khiển
    thừa hưởng nhầm `GRANT ... ON ALL TABLES`.
    """
    _apply(conn, _control_statements(cp.CONTROL_ROLE, password), cp.CONTROL_ROLE)
    logger.info("[DB_ROLES] role %s provisioned", cp.CONTROL_ROLE)


def _apply(conn, statements: list[tuple[str, tuple]], role: str) -> None:
    with conn:
        with conn.cursor() as cur:
            for sql, params in statements:
                if not sql.startswith("ALTER ROLE"):
                    cur.execute(sql, params)
                    continue
                # Savepoint: không có nó thì một câu thất bại sẽ huỷ cả giao
                # dịch, và mọi GRANT phía sau — phần việc THẬT ở cơ sở dữ liệu
                # này — sẽ đổ theo.
                cur.execute("SAVEPOINT provision_role_attr")
                try:
                    cur.execute(sql, params)
                except Exception as exc:
                    if getattr(exc, "pgcode", None) != _INSUFFICIENT_PRIVILEGE:
                        raise
                    cur.execute("ROLLBACK TO SAVEPOINT provision_role_attr")
                    if not _desired_attributes_already_hold(cur, role):
                        raise
                    # Mật khẩu không đọc lại được để so sánh (nó đã băm). Bỏ
                    # qua an toàn vì sai mật khẩu lộ ra ngay ở lượt kết nối kế
                    # tiếp bằng chính vai này, chứ không âm thầm.
                    logger.info(
                        "[DB_ROLES] bo qua '%s...': thieu quyen o muc cum, nhung "
                        "thuoc tinh cua %s da dung san",
                        sql[:32], role,
                    )
                else:
                    cur.execute("RELEASE SAVEPOINT provision_role_attr")


def _report(posture: dict, *, label: str) -> None:
    print(f"{label:<10} role   : {posture['connected_as']}")
    print(f"  superuser       : {posture['is_superuser']}")
    print(f"  bypasses RLS    : {posture['bypasses_rls']}")
    print(f"  RLS enabled on  : {', '.join(posture['rls_tables']) or '(none)'}")


def check_command() -> int:
    """Report posture for both DSNs and fail when the RUNTIME one is unsafe.

    Two connections, because the two roles have opposite expectations and only
    one of them is a finding:

      runtime   (DATABASE_URL)           MUST NOT bypass RLS.
      migration (MIGRATION_DATABASE_URL) is *supposed* to be a superuser — it
                                         has to be, to run DDL and create roles.

    Reporting only the migration connection — which is what this command used to
    do, because provisioning needs it — meant `--check` printed "policies are
    theatre" on a correctly cut-over deployment. A check that cannot go green is
    worse than no check: it trains the operator to ignore the one warning that
    matters.
    """
    from app.storage.postgres_connection import connect_migration, connect_postgres

    runtime = connect_postgres(application_name="provision_db_roles")
    try:
        runtime_posture = check(runtime)
    finally:
        runtime.close()

    migration = connect_migration()
    try:
        migration_posture = check(migration)
    finally:
        migration.close()

    _report(runtime_posture, label="runtime")
    print()
    _report(migration_posture, label="migration")
    print(f"\n{APP_ROLE} exists   : {runtime_posture['app_role_exists']}")

    if runtime_posture["policies_are_theatre"]:
        print(
            "\n  FAIL: RLS is installed but the RUNTIME role "
            f"{runtime_posture['connected_as']!r} bypasses it.\n"
            "  Every query returns every tenant's rows. Point DATABASE_URL at "
            f"{APP_ROLE}.",
            file=sys.stderr,
        )
        return 3

    if not runtime_posture["rls_enabled"]:
        print(
            "\n  FAIL: no table has row-level security enabled. Isolation is not "
            "installed — run the backend once so ensure_tables() applies it.",
            file=sys.stderr,
        )
        return 3

    print("\n  OK: tenant isolation is in force on the runtime connection.")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="report posture, change nothing"
    )
    parser.add_argument(
        "--print-url",
        action="store_true",
        help=f"print the DATABASE_URL for {APP_ROLE} (reads {PASSWORD_ENV})",
    )
    args = parser.parse_args(argv)

    if args.check:
        return check_command()

    from app.storage.postgres_connection import connect_migration, current_role_privileges

    conn = connect_migration()
    try:
        password = os.getenv(PASSWORD_ENV, "").strip()
        if not password:
            print(f"error: {PASSWORD_ENV} is not set", file=sys.stderr)
            return 2
        if len(password) < 16:
            # A weak password here is not a small problem: this role can read
            # every tenant's corpus, and Postgres is reachable from every
            # container on the compose network.
            print(
                f"error: {PASSWORD_ENV} must be at least 16 characters",
                file=sys.stderr,
            )
            return 2

        privileges = current_role_privileges(conn)
        if not privileges.is_superuser:
            print(
                f"error: connected as {privileges.rolname!r}, which cannot create roles. "
                f"Point MIGRATION_DATABASE_URL at a superuser.",
                file=sys.stderr,
            )
            return 3

        provision(conn, password)
        _report(check(conn), label="migration")
        if args.print_url:
            print(f"\nDATABASE_URL={app_database_url(password)}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
