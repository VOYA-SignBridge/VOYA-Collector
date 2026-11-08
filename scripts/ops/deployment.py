"""Fail-closed deployment and non-destructive restore into a new installation."""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from .transfer import (Failure, Stack, backup, complete_role_passwords, configure, extract, preflight,
                       run, verify)


def destination_settings(root, project, public_url):
    if not re.fullmatch(r"[a-z][a-z0-9_-]{2,40}", project):
        raise Failure("Project name must be 3-41 lowercase letters, digits, - or _.")
    url = urlsplit(public_url)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.query or url.fragment:
        raise Failure("Use a public http(s) URL without credentials, query or fragment.")
    if any(c in public_url for c in "\r\n\x00$'\""):
        raise Failure("Invalid public URL.")
    configure(root, {"COMPOSE_PROJECT_NAME": project, "CONTAINER_PREFIX": project,
                     "COMPOSE_FILE": "docker-compose.yml" + os.pathsep + "docker-compose.prod.yml",
                     "COMPOSE_PATH_SEPARATOR": os.pathsep, "FRONTEND_BASE_URL": public_url.rstrip("/"),
                     "CORS_ALLOWED_ORIGINS": f"{url.scheme}://{url.netloc}",
                     "COOKIE_SECURE": "1" if url.scheme == "https" else "0",
                     "COOKIE_DOMAIN": "", "APP_ENV": "production",
                     "BACKUP_HOST_DIR": "./backups", "BACKUP_MIRROR_HOST_DIR": "./backups",
                     "BACKUP_MIRROR_DIR": "", "ROLLBACK_DIR": "./backups/rollback"})
    (root / "deploy/public_hosts.txt").write_text(url.netloc + "\n", encoding="utf-8")
    (root / "backups").mkdir(exist_ok=True)


def check_ports(stack):
    for service in stack.config["services"].values():
        for port in service.get("ports", []):
            if port.get("protocol", "tcp") != "tcp":
                raise Failure("UDP port preflight is not supported.")
            with socket.socket() as sock:
                try:
                    sock.bind((port.get("host_ip", "0.0.0.0"), int(port["published"])))
                except OSError as exc:
                    raise Failure(f"Published port {port['published']} is unavailable.") from exc


def require_new_project(stack):
    project = stack.config["name"]
    if run(["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"]):
        raise Failure("Destination project already has containers; restore refuses to overwrite.")
    existing = set(run(["docker", "volume", "ls", "--format", "{{.Name}}"]).splitlines())
    if any(v["name"] in existing for v in stack.config.get("volumes", {}).values()):
        raise Failure("Destination volumes already exist; restore refuses to overwrite.")
    names = set(run(["docker", "ps", "-a", "--format", "{{.Names}}"]).splitlines())
    if any(s.get("container_name") in names for s in stack.config["services"].values()):
        raise Failure("Destination container name is already in use.")
    check_ports(stack)


def restore(bundle, target, *, project, public_url, accept_external=False):
    """Restore data only. Do not expose an application before migration/audit."""
    target, bundle = Path(target).resolve(), Path(bundle).resolve()
    manifest = verify(bundle)
    if manifest.get("external_storage") and not accept_external:
        raise Failure("Bundle depends on external Drive. Confirm --accept-external-storage.")
    if target.exists():
        raise Failure("Restore target must not exist; use a new directory and project.")
    required = (sum(v.get("unpacked_size", v["size"]) for v in manifest["files"].values())
                + manifest.get("database_bytes", 0))
    parent = target.parent
    if not parent.is_dir() or shutil.disk_usage(parent).free < required * 1.2 + 10 * 1024**3:
        raise Failure("Target parent must exist with unpacked backup size + 20% + 10 GiB free.")
    # Trusted backups only: SQL/config/source are executable, not merely data.
    target.mkdir(mode=0o700)
    extract(bundle / "workspace.tar.gz", target)
    destination_settings(target, project, public_url)
    stack = Stack(target)
    if complete_role_passwords(stack):
        stack = Stack(target)
    preflight(stack)
    if stack.pg_image != manifest["postgres_image"]:
        raise Failure("PostgreSQL image differs from the backup; use the backed-up version first.")
    if stack.db["POSTGRES_DB"] != manifest["database"] or stack.db["POSTGRES_USER"] != manifest["bootstrap_role"]:
        raise Failure("Database identity differs from the backup.")
    expected = set(stack.config.get("volumes", {})) - {m["source"] for m in
        stack.config["services"]["postgres"]["volumes"] if m["type"] == "volume"}
    if expected != set(manifest["volumes"]):
        raise Failure("Compose volume inventory differs from the backup.")
    require_new_project(stack)
    print("Creating a NEW database project; application services remain stopped.")
    stack.call("up", "-d", "postgres")
    stack.wait(["postgres"])
    restore_database(stack, bundle, manifest)
    for key in manifest["volumes"]:
        name = stack.config["volumes"][key]["name"]
        run(["docker", "volume", "create", "--label", f"com.docker.compose.project={project}",
             "--label", f"com.docker.compose.volume={key}", name])
        with (bundle / f"volume-{key}.tar.gz").open("rb") as stream:
            run(["docker", "run", "--rm", "-i", "--network", "none", "-v", f"{name}:/payload",
                 "--entrypoint", "tar", stack.pg_image, "-xzf", "-", "-C", "/payload"], input_file=stream)
    print("Restore OK: checksums, database table counts and named volumes verified.")
    return stack


def restore_database(stack, bundle, manifest):
    # Called only after require_new_project: no pre-existing host DB is ever
    # dropped. Check ALL freshly initialized databases before restoring roles.
    existing = json.loads(stack.sql("SELECT json_agg(datname) FROM pg_database WHERE NOT datistemplate"))
    if set(existing) - {manifest["database"], "postgres"}:
        raise Failure("Unexpected target database; refusing to overwrite.")
    if any(stack.counts(name) for name in existing):
        raise Failure("Target database is not empty.")
    # pg_dumpall includes CREATE ROLE for the bootstrap superuser, which initdb
    # has already made. Skip exactly that one CREATE; retain ALTER/password/grants.
    role = manifest["bootstrap_role"]
    quoted = '"' + role.replace('"', '""') + '"'
    creates = {f"CREATE ROLE {quoted};", f"CREATE ROLE {role};"}
    roles = (bundle / "roles.sql").read_text(encoding="utf-8")
    roles = "\n".join(line for line in roles.splitlines() if line.strip() not in creates)
    with tempfile.TemporaryFile() as stream:
        stream.write(roles.encode("utf-8"))
        stream.seek(0)
        stack.pg("psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", role, "-d",
                 "template1", input_file=stream)
    # pg_restore --create restores database ACL/owner/settings too. Recreate
    # only the empty databases initdb made in THIS NEW project, never --clean.
    for name in existing:
        if name not in manifest["databases"]:
            raise Failure("Target bootstrap database is absent from the backup.")
        quoted_name = '"' + name.replace('"', '""') + '"'
        stack.sql(f"DROP DATABASE {quoted_name}", "template1")
    for name, info in manifest["databases"].items():
        with (bundle / info["artifact"]).open("rb") as stream:
            stack.pg("pg_restore", "--create", "--exit-on-error", "-U", role,
                     "-d", "template1", input_file=stream)
        if stack.counts(name) != info["counts"]:
            raise Failure("Restored table counts do not match snapshot. Application remains stopped.")


def missing_built_images(stack) -> list[str]:
    """Image của các service tự dựng (`build:`) mà máy này CHƯA có."""
    missing = []
    for service in stack.config["services"].values():
        ref = service.get("image")
        if service.get("build") and ref:
            try:
                run(["docker", "image", "inspect", "--format", "{{.Id}}", ref])
            except Failure:
                missing.append(ref)
    return sorted(set(missing))


def deploy(stack, *, backup_dir=None, prepared_backup=None, restored=False,
           image_tag=None, accept_external=False, use_local_images=False):
    preflight(stack)
    if prepared_backup:
        manifest = verify(prepared_backup)
        if (set(stack.running()) != {"postgres"} or any(
                stack.counts(name) != info["counts"] for name, info in manifest["databases"].items())):
            raise Failure("Prepared backup requires all writers stopped and unchanged table counts.")
    elif not restored:
        # Do not modify a host with unresolved source-data/permission failures.
        stack.audit()
        if backup_dir is None:
            raise Failure("An existing deployment requires --backup-dir (new path outside workspace).")
    if image_tag:
        if not re.fullmatch(r"sha-[0-9a-f]{40}", image_tag):
            raise Failure("Registry deployments require a full 40-character commit SHA tag.")
        if run(["git", "rev-parse", "HEAD"], cwd=stack.root) != image_tag[4:]:
            raise Failure("Bind-mounted source commit does not match the requested image.")
        if run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=stack.root):
            raise Failure("Registry deployment requires a clean tracked worktree.")
        stack.call("pull")
    elif use_local_images and not missing_built_images(stack):
        # Image ĐÚNG như máy nguồn đang chạy, nạp từ gói chuyển server (`docker
        # load`). Dựng lại thì phải tải torch/CUDA vài GB (30–60 phút, cần mạng)
        # và còn có thể ra một bản khác bản đã chạy ổn trên máy nguồn.
        print("Using the images loaded from the migration pack; skipping the build.")
    else:
        if use_local_images:
            print("Pack images incomplete (" + ", ".join(missing_built_images(stack)) + "); building.")
        stack.call("build", "--pull")
    # A restored directory can be owned by a different Linux uid. Check actual
    # writes as the IMAGE user, not merely host permissions or root access.
    stack.call("run", "--rm", "--no-deps", "-T", "backend", "python", "-c",
               "import tempfile; from pathlib import Path; "
               "paths=['/dataset','/gdrive','/workspace/processed']; "
               "[(lambda f: f.close())(tempfile.TemporaryFile(dir=p)) for p in paths]")
    if not restored and not prepared_backup:
        backup(stack, backup_dir, accept_external=accept_external, resume=False)
    # After this point failures leave writers stopped. Never roll a DB back
    # automatically: schema changes may not be reversible.
    stack.call("stop", "--timeout", "300")
    stack.call("up", "-d", "postgres", "redis")
    stack.wait(["postgres", "redis"])
    version = stack.call("run", "--rm", "--no-deps", "-T", "backend", "python", "-c",
                         "from app.storage.schema_version import APP_SCHEMA_VERSION; print(APP_SCHEMA_VERSION)")
    if not version.isdigit():
        raise Failure("Cannot resolve image schema version.")
    def cli(module, *args):
        return stack.call("run", "--rm", "--no-deps", "-T", "-e",
                          "EXPECTED_DATABASE=" + stack.db["POSTGRES_DB"],
                          "backend", "python", "-m", module, *args,
                          safe_report=module == "app.cli.verify_deployment")
    cli("app.cli.migrate", "--to", version)
    cli("app.cli.provision_db_roles")
    cli("app.cli.provision_db_roles", "--check")
    cli("app.cli.migrate", "--status")
    print(cli("app.cli.verify_deployment"))
    # Start internal services first, keeping the public gateway offline.
    internal = [name for name in stack.config["services"] if name != "nginx"]
    stack.call("up", "-d", "--no-build", *internal)
    ready = [name for name in internal if name != "sot-init"]
    stack.wait(ready, seconds=300)
    cli("app.cli.migrate", "--status")
    stack.audit()
    stack.call("up", "-d", "--no-build", "nginx")
    stack.wait(["nginx"])
    print("Deployment passed schema, role, data and service-health gates.")
