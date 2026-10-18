"""Portable local-state backup. Never logs resolved Compose config or secrets."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit, urlunsplit


class Failure(RuntimeError):
    pass


def run(args, *, cwd=None, output=None, input_file=None, timeout=3600, safe_report=False):
    # Capture stderr: Docker/psql errors can contain credentials from config.
    result = subprocess.run(args, cwd=cwd, stdout=output or subprocess.PIPE,
                            stdin=input_file, stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        if safe_report and result.stdout:
            print(result.stdout.decode("utf-8", errors="replace"))
        raise Failure(f"Command failed (exit {result.returncode}): {args[0]} {args[1]}; "
                      "inspect the service logs locally (credentials are not printed).")
    return result.stdout.decode("utf-8").strip() if output is None else ""


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inside(path, root):
    return path.resolve().is_relative_to(root.resolve())


def env_read(path):
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values


PLAIN_ENV_VALUE = re.compile(r"[A-Za-z0-9_.,:/@%+=-]*")


def configure(root, changes):
    """Change only explicit destination settings; keep identity/crypto keys."""
    path = root / ".env"
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    lines = [line for line in lines if line.split("=", 1)[0].strip() not in changes]
    for key, value in changes.items():
        if any(c in value for c in "\r\n\x00"):
            raise Failure(f"Invalid setting: {key}")
        # Plain values stay unquoted: several repo scripts read .env with
        # `grep ^KEY= | cut -d= -f2-` and would keep the quotes as part of a DSN.
        # Anything Compose could reinterpret ($, spaces, #, quotes) is quoted.
        if PLAIN_ENV_VALUE.fullmatch(value):
            encoded = value
        else:
            encoded = json.dumps(value, ensure_ascii=False).replace("$", "$$")
        lines.append(f"{key}={encoded}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)


def complete_role_passwords(stack):
    """Fill missing provisioning variables from existing DSNs, never rotate."""
    env = stack.config["services"]["backend"]["environment"]
    changes = {}
    for key, dsn in (("VOYA_APP_DB_PASSWORD", "DATABASE_URL"),
                     ("VOYA_CONTROL_DB_PASSWORD", "CONTROL_DATABASE_URL")):
        if not env.get(key):
            password = unquote(urlsplit(str(env.get(dsn) or "")).password or "")
            if len(password) >= 16 and "CHANGE_ME" not in password.upper():
                changes[key] = password
    if changes:
        configure(stack.root, changes)
        print("Filled missing provisioning variables from existing DSNs: " + ", ".join(changes))
    return bool(changes)


def rotate_bootstrap_password(stack):
    """Give the bootstrap superuser a strong password: in PostgreSQL FIRST, then .env.

    Editing only .env does nothing to an initialised cluster (POSTGRES_PASSWORD is
    read once, at initdb), and the role dump in a backup would carry the old hash
    to the new host. Hex only, so it needs no quoting in SQL or URL encoding.
    """
    if len(str(stack.db.get("POSTGRES_PASSWORD", ""))) >= 16:
        print("POSTGRES_PASSWORD is already strong; nothing changed.")
        return False
    if "postgres" not in stack.running():
        raise Failure("Postgres must be running to change its password.")
    env = stack.config["services"]["backend"]["environment"]
    migration = urlsplit(str(env.get("MIGRATION_DATABASE_URL") or ""))
    if not migration.hostname:
        raise Failure("MIGRATION_DATABASE_URL is missing; fix it before rotating.")
    user, password = stack.db["POSTGRES_USER"], secrets.token_hex(24)
    role = '"' + user.replace('"', '""') + '"'
    # Through stdin, never argv: argv shows up in process lists and docker events.
    with tempfile.TemporaryFile() as stream:
        stream.write(f"ALTER ROLE {role} PASSWORD '{password}';\n".encode("ascii"))
        stream.seek(0)
        stack.pg("psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-U", user, "-d", stack.db["POSTGRES_DB"],
                 input_file=stream)
    netloc = f"{quote(user, safe='')}:{password}@{migration.hostname}"
    if migration.port:
        netloc += f":{migration.port}"
    configure(stack.root, {"POSTGRES_PASSWORD": password,
                           "MIGRATION_DATABASE_URL": urlunsplit(migration._replace(netloc=netloc))})
    print("Bootstrap password changed in PostgreSQL and in .env (value not printed).")
    return True


class Stack:
    def __init__(self, root, *, gpu=False, image_tag=None):
        self.root = Path(root).resolve()
        self.args = ["docker", "compose", "--project-directory", str(self.root),
                     "--env-file", str(self.root / ".env"),
                     "-f", str(self.root / "docker-compose.yml"),
                     "-f", str(self.root / "docker-compose.prod.yml")]
        if gpu:
            self.args += ["-f", str(self.root / "docker-compose.gpu.yml")]
        if image_tag:
            os.environ["VOYA_IMAGE_TAG"] = image_tag
            self.args += ["-f", str(self.root / "docker-compose.registry.yml")]
        self.config = json.loads(self.call("config", "--format", "json"))
        self.db = self.config["services"]["postgres"]["environment"]
        self.pg_image = self.config["services"]["postgres"]["image"]

    def call(self, *args, **kwargs):
        return run(self.args + list(args), cwd=self.root, **kwargs)

    def pg(self, *args, **kwargs):
        return self.call("exec", "-T", "postgres", *args, **kwargs)

    def sql(self, sql, database=None):
        return self.pg("psql", "-X", "-v", "ON_ERROR_STOP=1", "-U",
                       self.db["POSTGRES_USER"], "-d", database or self.db["POSTGRES_DB"],
                       "-At", "-c", sql)

    def counts(self, database=None):
        statements = self.sql("SELECT format('SELECT %L, count(*) FROM %I.%I', "
                              "schemaname || '.' || tablename, schemaname, tablename) "
                              "FROM pg_tables WHERE schemaname NOT IN "
                              "('pg_catalog', 'information_schema') ORDER BY 1", database)
        if not statements:
            return {}
        return dict(line.rsplit("|", 1) for line in self.sql(
            " UNION ALL ".join(statements.splitlines()), database).splitlines())

    def running(self):
        return self.call("ps", "--status", "running", "--services").splitlines()

    def wait(self, services, seconds=180):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            ids = self.call("ps", "-a", "-q", *services).splitlines()
            states = json.loads(run(["docker", "inspect", *ids])) if ids else []
            if len(states) == len(services) and all(
                s["State"].get("Health", {}).get("Status") == "healthy"
                if "Health" in s["State"] else s["State"]["Status"] == "running"
                for s in states
            ):
                return
            time.sleep(2)
        raise Failure("Timed out waiting for services: " + ", ".join(services))

    def audit(self):
        # Exit failure is deliberately NOT swallowed, including RBAC failures.
        report = self.call("exec", "-T", "backend", "python", "-m",
                           "app.cli.verify_deployment", safe_report=True)
        print(report)


def preflight(stack, *, disk_gb=10, strict=True):
    root, config = stack.root, stack.config
    engine = json.loads(run(["docker", "info", "--format", "{{json .}}"], timeout=30))
    if engine["OSType"] != "linux":
        raise Failure("Docker must use Linux containers.")
    if engine["MemTotal"] < 6 * 1024**3:
        raise Failure("Docker needs at least 6 GiB RAM; training may need more.")
    if shutil.disk_usage(root).free < disk_gb * 1024**3:
        raise Failure(f"Need at least {disk_gb} GiB free on the workspace drive.")
    if strict:
        validate_configuration(stack)
    excluded_binds = []
    for name, service in config["services"].items():
        for mount in service.get("volumes", []):
            if mount["type"] != "bind":
                continue
            if mount["target"] == "/var/run/docker.sock":
                continue
            if name == "pg-backup" and mount["target"] in ("/backups", "/mirror"):
                excluded_binds.append(mount["source"])
                continue
            source = Path(mount["source"])
            if not inside(source, root):
                raise Failure(f"External bind mount in {name}: relocate it inside the workspace first.")
            if not source.exists():
                raise Failure(f"Missing bind source for {name}: {source.relative_to(root)}")
    for excluded in excluded_binds:
        for data in (root / "dataset", root / "gdrive", root / "processed"):
            if inside(data, Path(excluded)) or inside(Path(excluded), data):
                raise Failure("Backup/mirror location overlaps an application data directory.")
    print("Preflight OK: Linux Docker, memory/disk and bind mounts" +
          (", DB role configuration and public URL." if strict else "."))
    return excluded_binds


def validate_configuration(stack):
    root = stack.root
    env = stack.config["services"]["backend"]["environment"]
    required = {"SECRET_KEY": 32, "AUTH_TOKEN_SECRET_KEY": 32,
                "VOYA_APP_DB_PASSWORD": 16, "VOYA_CONTROL_DB_PASSWORD": 16}
    for key, size in required.items():
        value = str(env.get(key) or "")
        if len(value) < size or "CHANGE_ME" in value.upper():
            raise Failure(f"Missing/weak {key}; configure it before deployment.")
    if env["VOYA_APP_DB_PASSWORD"] == env["VOYA_CONTROL_DB_PASSWORD"]:
        raise Failure("Application and control role passwords must differ.")
    if len(str(stack.db.get("POSTGRES_PASSWORD", ""))) < 16:
        raise Failure("POSTGRES_PASSWORD must have at least 16 characters.")
    for key, role, password in (
        ("DATABASE_URL", "voya_app", env["VOYA_APP_DB_PASSWORD"]),
        ("CONTROL_DATABASE_URL", "voya_control", env["VOYA_CONTROL_DB_PASSWORD"]),
        ("MIGRATION_DATABASE_URL", stack.db["POSTGRES_USER"], stack.db["POSTGRES_PASSWORD"]),
    ):
        parsed = urlsplit(str(env.get(key) or ""))
        if (parsed.scheme not in ("postgresql", "postgres") or parsed.hostname != "postgres"
                or parsed.port not in (None, 5432)
                or unquote(parsed.path.lstrip("/")) != stack.db["POSTGRES_DB"]
                or unquote(parsed.username or "") != role
                or unquote(parsed.password or "") != password):
            raise Failure(f"{key} must match the Compose database and its dedicated role.")
    if str(env.get("DB_STRICT_ISOLATION")) != "1":
        raise Failure("DB_STRICT_ISOLATION must be 1.")
    base = urlsplit(str(env.get("FRONTEND_BASE_URL") or ""))
    if base.scheme not in ("https", "http") or not base.hostname:
        raise Failure("Set FRONTEND_BASE_URL to the destination public URL.")
    if base.scheme == "https" and str(env.get("COOKIE_SECURE")) not in ("1", "true", "True"):
        raise Failure("HTTPS requires COOKIE_SECURE=1.")
    hosts = {line.strip().lower() for line in (root / "deploy/public_hosts.txt").read_text(
        encoding="utf-8-sig").splitlines() if line.strip() and not line.strip().startswith("#")}
    if base.netloc.lower() not in hosts:
        raise Failure("Destination host is missing from deploy/public_hosts.txt.")
    origins = {x.strip() for x in str(env.get("CORS_ALLOWED_ORIGINS") or "").split(",")}
    if f"{base.scheme}://{base.netloc}" not in origins or "*" in origins:
        raise Failure("CORS_ALLOWED_ORIGINS must explicitly include the public origin, without wildcard.")


def safe_members(archive):
    """Reject traversal, Windows aliases, symlinks/devices and duplicate files."""
    seen = set()
    for member in archive:
        name = member.name
        path = PurePosixPath(name)
        if (path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name
                or not (member.isdir() or member.isfile())):
            raise Failure("Unsafe archive entry.")
        for part in path.parts:
            if (part.endswith((".", " ")) or
                    re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part)):
                raise Failure("Archive contains a non-portable filename.")
        key = str(path).casefold()
        if member.isfile() and key in seen:
            raise Failure("Archive contains duplicate or case-colliding filenames.")
        seen.add(key)
        yield member


def validate_tar(path):
    total = 0
    with tarfile.open(path, "r:gz") as archive:
        for member in safe_members(archive):
            total += member.size
    return total


def extract(path, target):
    # Validate the ENTIRE archive before creating any entries.
    validate_tar(path)
    target = Path(target)
    if target.exists() and (target.is_symlink() or any(target.iterdir())):
        raise Failure("Archive extraction requires an empty destination.")
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "r:gz") as archive:
        # Explicit regular-file extraction also works on early Python 3.11
        # releases without tarfile's later filter= security backport.
        for member in safe_members(archive):
            destination = target / member.name
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, destination.open("xb") as output:
                    shutil.copyfileobj(source, output)
                destination.chmod(member.mode & 0o777)


def verify(bundle):
    bundle = Path(bundle).resolve()
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != 1:
        raise Failure("Unsupported backup format.")
    files = manifest["files"]
    if not {"workspace.tar.gz", "database.dump", "roles.sql"} <= files.keys():
        raise Failure("Incomplete backup manifest.")
    if manifest.get("database") not in manifest.get("databases", {}):
        raise Failure("Manifest is missing the application database inventory.")
    expected = set(files) | {"manifest.json"}
    if {p.name for p in bundle.iterdir()} != expected:
        raise Failure("Backup contains missing or unexpected files.")
    for name, info in files.items():
        path = bundle / name
        if Path(name).name != name or path.is_symlink() or not path.is_file():
            raise Failure("Invalid backup artifact path.")
        if path.stat().st_size != info["size"] or digest(path) != info["sha256"]:
            raise Failure(f"Checksum mismatch: {name}")
        if name.endswith(".tar.gz"):
            validate_tar(path)
    required = {f"volume-{name}.tar.gz" for name in manifest["volumes"]}
    required.update(db["artifact"] for db in manifest["databases"].values())
    if not required <= files.keys():
        raise Failure("Missing volume backup.")
    return manifest


# Never exclude dataset/processed/gdrive/config/certs, even when gitignored.
SKIP = {".git", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache"}
#: Trạng thái của RIÊNG máy nguồn (scripts/voya.py). Sang máy mới chúng nói sai:
#: cờ "dừng có chủ ý" do chính lượt tạo gói đặt ra sẽ chặn máy mới tự bật stack
#: và tắt báo động; image ID của lần triển khai cuối là của máy cũ, nên canh gác
#: báo "image khác" mãi; cờ bảo trì làm site mới hiện trang bảo trì. Lịch sử thao
#: tác (.voya/actions.jsonl) vẫn đi theo — đó là lịch sử, không phải trạng thái.
HOST_STATE = {".voya/stopped_intentionally.json", ".voya/deploy_state.json", ".voya/deploy.lock",
              ".voya/watch_state.json", ".voya/task.log", ".voya/task.log.1",
              "nginx.conf.d/maintenance.on"}


def snapshot_workspace(root, destination, excluded):
    root = root.resolve()
    excluded = [Path(p).resolve() for p in excluded] + [root / "backups"]
    if any(inside(root, path) for path in excluded):
        raise Failure("A backup/mirror mount overlaps the workspace root.")
    with tarfile.open(destination, "w:gz") as archive:
        for folder, dirs, files in os.walk(root, followlinks=False):
            current = Path(folder)
            dirs[:] = sorted(d for d in dirs if d not in SKIP and not d.startswith(".venv")
                             and not any(inside(current / d, ex) for ex in excluded))
            for name in dirs + sorted(files):
                path = current / name
                if path.relative_to(root).as_posix() in HOST_STATE:
                    continue
                if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                    raise Failure(f"Resolve symlink/junction before backup: {path.relative_to(root)}")
                before = path.stat()
                archive.add(path, arcname=path.relative_to(root).as_posix(), recursive=False)
                after = path.stat()
                if path.is_file() and (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise Failure("A workspace file changed during backup; stop local writers and retry.")


def dump_database(stack, destination):
    if stack.sql("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user") != "t":
        raise Failure("Backup role must bypass RLS to export every tenant.")
    if stack.sql("SELECT count(*) FROM pg_tablespace WHERE spcname NOT IN ('pg_default','pg_global')") != "0":
        raise Failure("Custom tablespaces need explicit host path mapping before transfer.")
    names = json.loads(stack.sql("SELECT json_agg(datname ORDER BY datname) FROM pg_database "
                                 "WHERE NOT datistemplate"))
    databases = {}
    for index, name in enumerate(names):
        artifact = "database.dump" if name == stack.db["POSTGRES_DB"] else f"database-{index}.dump"
        info = {"artifact": artifact, "counts": stack.counts(name),
                "bytes": int(stack.sql("SELECT pg_database_size(current_database())", name))}
        with (destination / artifact).open("wb") as stream:
            stack.pg("pg_dump", "-U", stack.db["POSTGRES_USER"], "-d", name,
                     "--create", "-Fc", output=stream)
        with (destination / artifact).open("rb") as stream:
            stack.pg("pg_restore", "-f", "/dev/null", input_file=stream)
        databases[name] = info
    with (destination / "roles.sql").open("wb") as stream:
        stack.pg("pg_dumpall", "-U", stack.db["POSTGRES_USER"], "--roles-only", output=stream)
    return databases


def backup(stack, destination, *, accept_external=False, resume=True):
    destination = Path(destination).resolve()
    if inside(destination, stack.root) or destination.exists():
        raise Failure("Backup path must be NEW and OUTSIDE the workspace.")
    exclusions = preflight(stack, strict=False)
    env = stack.config["services"]["backend"]["environment"]
    external = str(env.get("USE_GOOGLE_DRIVE", "0")).lower() in ("1", "true")
    if external and not accept_external:
        raise Failure("Google Drive is external storage. Use --accept-external-storage only if "
                      "the destination keeps access to the same Drive; this is NOT a cloud export.")
    running = stack.running()
    if "postgres" not in running:
        raise Failure("Source Postgres must be running.")
    # `docker compose run` containers are not services: `stop` leaves them running and
    # they keep their DB connections, so the snapshot would be refused AFTER the site
    # was already taken down (17/10/2026: an interrupted Drive export). Refuse first.
    oneoff = run(["docker", "ps", "--format", "{{.Names}}", "--filter",
                  f"label=com.docker.compose.project={stack.config.get('name', '')}",
                  "--filter", "label=com.docker.compose.oneoff=True"]).split()
    if oneoff:
        raise Failure("One-off containers are still running and may hold DB connections: "
                      + ", ".join(oneoff) + ". Stop them (docker rm -f <name>) and retry.")
    destination.mkdir(parents=True, mode=0o700)
    stopped = [s for s in running if s != "postgres"]
    completed = False
    try:
        print("Stopping application writers for a consistent local-state snapshot...")
        # Graceful stop; SIGKILL would risk partially written clips/checkpoints.
        if stopped:
            stack.call("stop", "--timeout", "300", *stopped)
            ids = stack.call("ps", "-a", "-q", *stopped).splitlines()
            states = json.loads(run(["docker", "inspect", *ids]))
            if any(s["State"].get("OOMKilled") or s["State"].get("ExitCode") == 137 for s in states):
                raise Failure("A service was killed, not drained. No valid backup was published.")
        # Backups preserve even imperfect data. Semantic validation gates DEPLOY,
        # not the ability to rescue an unhealthy host.
        if stack.sql("SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' "
                     "AND pid <> pg_backend_pid()") != "0":
            raise Failure("External database clients are still connected; stop them before snapshotting.")
        databases = dump_database(stack, destination)
        pg_volumes = {m["source"] for m in stack.config["services"]["postgres"]["volumes"]
                      if m["type"] == "volume"}
        volumes = {}
        for key, value in stack.config.get("volumes", {}).items():
            if key in pg_volumes:
                continue
            actual = value["name"]
            run(["docker", "volume", "inspect", actual])  # Do not create an absent source.
            with (destination / f"volume-{key}.tar.gz").open("wb") as stream:
                run(["docker", "run", "--rm", "--network", "none", "-v", f"{actual}:/payload:ro",
                     "--entrypoint", "tar", stack.pg_image, "-czf", "-", "-C", "/payload", "."], output=stream)
            volumes[key] = actual
        snapshot_workspace(stack.root, destination / "workspace.tar.gz", exclusions)
        manifest = {"format": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                    "postgres_image": stack.pg_image, "database": stack.db["POSTGRES_DB"],
                    "bootstrap_role": stack.db["POSTGRES_USER"],
                    "counts": databases[stack.db["POSTGRES_DB"]]["counts"], "databases": databases,
                    "database_bytes": sum(db["bytes"] for db in databases.values()),
                    "volumes": volumes, "external_storage": external,
                    "exclusions": sorted(SKIP) + [".venv*", "backups", "backup mirror mounts"],
                    "files": {}}
        for path in destination.iterdir():
            path.chmod(0o600)
            info = {"size": path.stat().st_size, "sha256": digest(path)}
            if path.name.endswith(".tar.gz"):
                info["unpacked_size"] = validate_tar(path)
            manifest["files"][path.name] = info
        # Written LAST: an interrupted backup is never accepted as complete.
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        verify(destination)
        completed = True
        print(f"Verified backup: {destination}. Contains secrets; use encrypted storage/transport.")
    finally:
        if stopped and (resume or not completed):
            stack.call("start", *stopped)
            try:
                stack.wait(stopped, seconds=300)
            except Failure as exc:
                if completed:
                    raise
                # Never let the restart replace the error that made the backup fail.
                print(f"WARNING while restarting services after the failure: {exc}")
