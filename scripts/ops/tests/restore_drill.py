"""Real PostgreSQL 17 roundtrip. Isolated containers, no ports/production volumes."""
import json
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ops.transfer import Failure, Stack, dump_database, run
from ops.deployment import restore_database


class IsolatedPostgres(Stack):
    def __init__(self, name):
        self.name = name
        self.db = {"POSTGRES_USER": "admin", "POSTGRES_DB": "drill"}

    def pg(self, *args, **kwargs):
        return run(["docker", "exec", "-i", self.name, *args], **kwargs)


def main():
    token = uuid.uuid4().hex[:12]
    containers = []
    try:
        for suffix in ("source", "target"):
            name = f"voya-transfer-drill-{token}-{suffix}"
            run(["docker", "run", "-d", "--name", name, "--label", f"voya.transfer-drill={token}",
                 "--network", "none", "--tmpfs", "/var/lib/postgresql/data",
                 "-e", "POSTGRES_USER=admin", "-e", "POSTGRES_DB=drill",
                 "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:17"])
            containers.append(name)
            db = IsolatedPostgres(name)
            for attempt in range(60):
                try:
                    db.pg("pg_isready", "-U", "admin", "-d", "drill")
                    # pg_isready can hit initdb's temporary server; require TCP
                    # too, as only the final postmaster listens there.
                    db.pg("pg_isready", "-h", "127.0.0.1", "-U", "admin", "-d", "drill")
                    break
                except Failure:
                    time.sleep(1)
            else:
                raise Failure("Drill PostgreSQL startup timed out.")
        source, target = map(IsolatedPostgres, containers)
        source.sql("CREATE ROLE drill_reader LOGIN PASSWORD 'drill_only_password'; "
                   "CREATE TABLE samples(id integer PRIMARY KEY, label text NOT NULL); "
                   "INSERT INTO samples VALUES (1, 'Xin chào'), (2, 'Đ'); "
                   "CREATE TABLE empty_table(id integer); "
                   "ALTER TABLE samples ENABLE ROW LEVEL SECURITY; "
                   "CREATE POLICY own_sample ON samples FOR SELECT TO drill_reader USING (id=1); "
                   "GRANT SELECT ON samples TO drill_reader")
        source.sql("CREATE DATABASE extra_database")
        source.sql("CREATE TABLE extra(id integer); INSERT INTO extra VALUES (42)", "extra_database")
        source.sql("REVOKE CONNECT ON DATABASE drill FROM PUBLIC")
        source.sql("ALTER DATABASE drill SET work_mem = '8MB'")
        with tempfile.TemporaryDirectory(prefix="voya-drill-") as folder:
            bundle = Path(folder)
            databases = dump_database(source, bundle)
            manifest = {"bootstrap_role": "admin", "database": "drill", "databases": databases}
            restore_database(target, bundle, manifest)
            if target.sql("SELECT label FROM samples ORDER BY id") != "Xin chào\nĐ":
                raise Failure("Unicode data mismatch.")
            if target.sql("SET ROLE drill_reader; SELECT count(*) FROM samples").splitlines()[-1] != "1":
                raise Failure("Restored role/policy failed RLS check.")
            if target.sql("SELECT id FROM extra", "extra_database") != "42":
                raise Failure("Secondary database data mismatch.")
            if target.sql("SHOW work_mem") != "8MB":
                raise Failure("Database settings were not restored.")
            acl_query = ("SELECT CASE WHEN grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(grantee) END, "
                         "pg_get_userbyid(grantor), privilege_type, is_grantable FROM "
                         "aclexplode((SELECT datacl FROM pg_database WHERE datname='drill')) "
                         "ORDER BY 1,2,3,4")
            if target.sql(acl_query) != source.sql(acl_query):
                raise Failure("Database ACL mismatch.")
            try:
                restore_database(target, bundle, manifest)
            except Failure as exc:
                if "not empty" not in str(exc) and "Unexpected target" not in str(exc):
                    raise
            else:
                raise Failure("Second restore should have refused the populated database.")
        print("PASS: PG17 multi-database dump/restore, counts, Unicode, roles/RLS, DB ACL/settings, overwrite refusal.")
    finally:
        for name in containers:
            info = json.loads(run(["docker", "inspect", name]))[0]
            if info["Config"]["Labels"].get("voya.transfer-drill") != token:
                raise Failure("Refusing cleanup: drill ownership label mismatch.")
            run(["docker", "rm", "-f", name])


if __name__ == "__main__":
    main()
