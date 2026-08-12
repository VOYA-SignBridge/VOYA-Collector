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

logger = logging.getLogger("db.roles")

#: Role the application authenticates as at runtime.
APP_ROLE = "voya_app"

#: Environment variable carrying the password for APP_ROLE. Not a CLI flag: a
#: password passed as an argument lands in the shell history and in the process
#: list of every other user on the host.
PASSWORD_ENV = "VOYA_APP_DB_PASSWORD"

#: Object privileges the application role needs, and nothing beyond them.
#: Note the absence of TRUNCATE and REFERENCES: both are close enough to DDL to
#: be worth withholding, and no code path uses either.
TABLE_PRIVILEGES = "SELECT, INSERT, UPDATE, DELETE"


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


def provision(conn, password: str) -> None:
    """Create/repair the application role. Idempotent."""
    with conn:
        with conn.cursor() as cur:
            for sql, params in _statements(APP_ROLE, password):
                cur.execute(sql, params)
    logger.info("[DB_ROLES] role %s provisioned", APP_ROLE)


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
