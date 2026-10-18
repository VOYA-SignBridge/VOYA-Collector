"""Full migration pack: the verified app bundle PLUS everything it leaves out.

`backup()` produces a restorable bundle but deliberately excludes Git history,
backup history, Drive content, Docker images, anonymous volumes and host
configuration (cloudflared, scheduled tasks, WSL/Docker settings). Moving to a
new server needs all of them, so this module collects each one into a single
folder with ONE manifest covering every file. Never logs secrets.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .transfer import Failure, Stack, backup, digest, env_read, inside, run, verify

PACK_FORMAT = 1
MANIFEST = "PACK_MANIFEST.json"
README = "00_HUONG-DAN-KHOI-PHUC.md"

#: Every migration artefact lives under ONE folder with this name, so packs,
#: zips and the Drive pre-copy never mix with anything else on the disk.
HOME_DIR = "SignBridge_ChuyenServer"
DRIVE_CACHE = "drive-cache"

#: Folder names INSIDE a pack. Numbered so they list in restore order; ASCII
#: without diacritics so they survive every zip tool and Windows path rule.
TOOLS = "00_cong-cu"
APP = "01_ung-dung-va-database"
GIT = "02_lich-su-git"
DRIVE = "03_google-drive"
RELATED_DIR = "04_video-va-du-lieu-canh-repo"
HISTORY = "05_lich-su-backup"
IMAGES = "06_docker-images"
VOLUMES = "07_docker-volumes"
LAYERS = "08_file-trong-container"
REFERENCED = "09_file-db-tro-ra-ngoai"
HOST = "10_cau-hinh-may-va-khoa"
REPORTS = "11_bao-cao"


def migration_home(base):
    """`F:/` -> `F:/SignBridge_ChuyenServer`; a path already named so is kept."""
    base = Path(base).resolve()
    return base if base.name == HOME_DIR else base / HOME_DIR


def pack_name(now=None):
    """`SignBridge_ChuyenServer_2026-10-16_14h30`: sorts by date, readable aloud."""
    return f"{HOME_DIR}_{(now or datetime.now()):%Y-%m-%d_%Hh%M}"
LONG = 12 * 3600  # Drive export and `docker save` of the torch images take hours, not minutes.
TASK_PATTERN = ("voya", "signbridge")


def is_link(path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


class Dedup:
    """Store byte-identical files once; the manifest maps every copy to the kept one.

    Old dumps recur across backup folders (and `Videos` was once a full copy of
    `qipedc_mau`). Dropping a folder by NAME would lose any file that differs; keying
    on size + SHA-256 drops only true duplicates, and restore re-creates them.
    """

    def __init__(self, pack):
        self.pack, self.kept, self.links, self.saved = Path(pack), {}, {}, 0

    def copy(self, source, out):
        size = source.stat().st_size
        key = (size, digest(source))
        rel = out.relative_to(self.pack).as_posix()
        if key in self.kept:
            self.links[rel] = self.kept[key]
            self.saved += size
            return
        shutil.copy2(source, out)
        self.kept[key] = rel


def copy_tree(source, target, dedup=None):
    """Copy regular files only; a link would silently pull in data from elsewhere."""
    source, target = Path(source), Path(target)
    for folder, dirs, files in os.walk(source):
        current = Path(folder)
        for name in dirs + files:
            if is_link(current / name):
                raise Failure(f"Resolve symlink/junction before packing: {current / name}")
        out = target / current.relative_to(source)
        out.mkdir(parents=True, exist_ok=True)
        for name in files:
            if dedup:
                dedup.copy(current / name, out / name)
            else:
                shutil.copy2(current / name, out / name)


def tree_size(path, skip=()):
    total = 0
    for folder, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".venv")]
        total += sum((Path(folder) / f).stat().st_size for f in files if not is_link(Path(folder) / f))
    return total


def history_sources(root, env, extra=()):
    """Backup history that lives outside the workspace tarball, labelled for the pack."""
    sources = {"backups": root / "backups"}
    for key in ("BACKUP_HOST_DIR", "BACKUP_MIRROR_HOST_DIR"):
        value = str(env.get(key) or "").strip()
        if value:
            path = (root / value).resolve()
            if path != (root / "backups").resolve():
                sources[key.lower()] = path
    for path in extra:
        path = Path(path).resolve()
        label = "extra-" + "".join(c if c.isalnum() or c in "-_" else "_" for c in path.name)
        if label in sources:
            raise Failure(f"Two --external folders share the name {path.name}.")
        sources[label] = path
    missing = [str(p) for label, p in sources.items() if label != "backups" and not p.is_dir()]
    if missing:
        raise Failure("History folder not found: " + ", ".join(missing))
    return {label: p for label, p in sources.items() if p.is_dir()}


#: Data folders that live NEXT TO the repo but belong to this server. They are
#: restored as siblings again, so `../qipedc_mau`-style references keep working.
RELATED = (
    "qipedc_mau",                     # QIPEDC reference videos + extracted .npz (scripts, tests, learn catalog)
    "voya_test_clips",                # Test clips
    "voya_backups",                   # Hand-made pre-migration dumps and .env snapshots
    "voya-migration",                 # July 2026 migration dumps
    "voya_lop_vung_2026-08-14",       # Region-class repair: before/after data
    "2. BackupData_VOYA-Collector",   # Older full backup (config, secrets, backup.sql)
)


def related_sources(root):
    return {name: root.parent / name for name in RELATED if (root.parent / name).is_dir()}


# ---- individual sections. Each returns a small JSON-able status. ----

def pack_git(root, target):
    if not (root / ".git").exists():
        return {"status": "absent"}
    target.mkdir(parents=True)
    git = ["git", "-C", str(root)]
    # --all = every branch, tag, remote-tracking ref and refs/stash. Uncommitted
    # and untracked files are already in the app bundle's workspace.tar.gz.
    run(git + ["bundle", "create", str(target / "repo.bundle"), "--all"], timeout=LONG)
    run(git + ["bundle", "verify", "--quiet", str(target / "repo.bundle")], timeout=LONG)
    remotes = {}
    for line in run(git + ["remote", "-v"]).splitlines():
        name, url, kind = line.split()
        if kind == "(fetch)":
            remotes[name] = url
    state = {"branch": run(git + ["branch", "--show-current"]), "head": run(git + ["rev-parse", "HEAD"]),
             "remotes": remotes, "stashes": len(run(git + ["stash", "list"]).splitlines()),
             "uncommitted": len(run(git + ["status", "--porcelain", "-uall"]).splitlines())}
    (target / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    warnings = []
    if state["stashes"] > 1:
        warnings.append(f"Git has {state['stashes']} stashes; only the newest is a ref in the bundle.")
    return {"status": "ok", **state, "warnings": warnings}


def compose_containers(stack):
    ids = stack.call("ps", "-a", "-q").splitlines()
    return json.loads(run(["docker", "inspect", *ids])) if ids else []


def pack_images(stack, target):
    """`docker save` the images the containers ACTUALLY run, by ID when a tag moved on."""
    target.mkdir(parents=True)
    entries = {}
    for container in compose_containers(stack):
        tag, image_id = container["Config"]["Image"], container["Image"]
        entries[image_id] = {"tag": tag, "id": image_id,
                             "service": container["Config"]["Labels"].get("com.docker.compose.service")}
    for service in stack.config["services"].values():  # Services never started still need images.
        tag = service.get("image")
        if tag and tag not in {e["tag"] for e in entries.values()}:
            try:
                image_id = run(["docker", "image", "inspect", "--format", "{{.Id}}", tag])
            except Failure:
                continue  # Not present locally: the destination pulls/builds it.
            entries.setdefault(image_id, {"tag": tag, "id": image_id, "service": None})
    refs = []
    for entry in entries.values():
        try:
            current = run(["docker", "image", "inspect", "--format", "{{.Id}}", entry["tag"]])
        except Failure:
            current = None
        # A rebuilt tag no longer names the running image; save the exact ID.
        entry["saved_as"] = entry["tag"] if current == entry["id"] else entry["id"]
        refs.append(entry["saved_as"])
    if not refs:
        raise Failure("No Docker images found for this Compose project.")
    run(["docker", "save", "-o", str(target / "images.tar"), *sorted(set(refs))], timeout=LONG)
    (target / "images.json").write_text(json.dumps(list(entries.values()), indent=2), encoding="utf-8")
    return {"status": "ok", "images": len(entries)}


def pack_anonymous_volumes(stack, target):
    named = {v["name"] for v in stack.config.get("volumes", {}).values()}
    found = []
    for container in compose_containers(stack):
        for mount in container.get("Mounts", []):
            if mount["Type"] != "volume" or mount["Name"] in named:
                continue
            artifact = f"anon-{len(found)}.tar.gz"
            target.mkdir(parents=True, exist_ok=True)
            with (target / artifact).open("wb") as stream:
                run(["docker", "run", "--rm", "--network", "none", "-v", f"{mount['Name']}:/payload:ro",
                     "--entrypoint", "tar", stack.pg_image, "-czf", "-", "-C", "/payload", "."], output=stream)
            found.append({"artifact": artifact, "volume": mount["Name"], "destination": mount["Destination"],
                          "container": container["Name"].lstrip("/")})
    if found:
        (target / "anonymous.json").write_text(json.dumps(found, indent=2), encoding="utf-8")
    return {"status": "ok" if found else "absent", "volumes": len(found)}


def drive_sync(stack, target):
    """Run the read-only exporter in the backend image; incremental on `target`."""
    target = Path(target).resolve()
    if inside(target, stack.root):
        raise Failure("Drive export folder must be OUTSIDE the workspace (it is bind-mounted).")
    target.mkdir(parents=True, exist_ok=True)
    stack.call("run", "--rm", "--no-deps", "-T", "-v", f"{target}:/export", "backend",
               "python", "/workspace/scripts/ops/drive_export.py", "/export",
               output=sys.stdout, timeout=LONG)
    inventory = json.loads((target / "inventory.json").read_text(encoding="utf-8"))
    return {"status": "ok", "files": len(inventory["files"]), "bytes": inventory["bytes"],
            "root": inventory["root"]}


def cloudflared_service():
    """ImagePath of the Windows service, with any inline token removed."""
    if os.name != "nt":
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\Cloudflared") as key:
            return winreg.QueryValueEx(key, "ImagePath")[0]
    except OSError:
        return None


def pack_host(target):
    """Host configuration the workspace never contained. Best effort, but every gap is reported."""
    target.mkdir(parents=True)
    warnings, found = [], []
    command = cloudflared_service()
    if command:
        parts = [p.strip('"') for p in shlex.split(command, posix=False)]
        service = {"command": " ".join("<token>" if parts[i - 1] == "--token" else p
                                       for i, p in enumerate(parts))}
        (target / "cloudflared").mkdir()
        if "--token-file" in parts:
            token = Path(parts[parts.index("--token-file") + 1])
            try:
                shutil.copy2(token, target / "cloudflared" / "token")
                found.append("cloudflared token")
            except OSError:
                warnings.append(f"Cannot read {token} (run as Administrator), or copy the tunnel "
                                "token from the Cloudflare dashboard on the new machine.")
        elif "--token" in parts:
            warnings.append("Tunnel token is inline in the service command; take it from the dashboard.")
        for port in range(20241, 20246):  # cloudflared's default metrics ports.
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/config", timeout=3) as response:
                    (target / "cloudflared" / "ingress.json").write_bytes(response.read())
                found.append("cloudflared ingress")
                break
            except OSError:
                continue
        (target / "cloudflared" / "service.json").write_text(json.dumps(service, indent=2), encoding="utf-8")
    else:
        warnings.append("No cloudflared Windows service found on this host.")
    home = Path.home()
    for source, name in ((home / ".wslconfig", "wslconfig"), (home / ".docker" / "daemon.json", "docker-daemon.json")):
        if source.is_file():
            shutil.copy2(source, target / name)
            found.append(name)
    # SOT signing key (app/sot/keys.py default). A publisher host that loses it
    # can no longer publish: a new key means editing authorized_keys everywhere.
    if (home / ".voya").is_dir():
        copy_tree(home / ".voya", target / "voya-home")
        found.append("~/.voya (SOT signing key)")
    if os.name == "nt":
        listing = subprocess.run(["schtasks", "/query", "/fo", "csv", "/nh"], capture_output=True, text=True)
        names = {line.split('","')[0].strip('"') for line in listing.stdout.splitlines() if line}
        for name in sorted(n for n in names if any(p in n.lower() for p in TASK_PATTERN)):
            xml = subprocess.run(["schtasks", "/query", "/tn", name, "/xml"], capture_output=True)
            if xml.returncode == 0:
                (target / "tasks").mkdir(exist_ok=True)
                (target / "tasks" / (name.strip("\\").replace("\\", "_") + ".xml")).write_bytes(xml.stdout)
                found.append(f"task {name}")
    system = {"platform": platform.platform(), "python": sys.version.split()[0]}
    for key, args in (("docker", ["docker", "version", "--format", "{{.Server.Version}}"]),
                      ("compose", ["docker", "compose", "version", "--short"]),
                      ("gpu", ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"])):
        try:
            system[key] = subprocess.run(args, capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            system[key] = None
    (target / "system.json").write_text(json.dumps(system, indent=2), encoding="utf-8")
    return {"status": "ok", "found": found, "warnings": warnings}


#: Launchers copied to the ROOT of every pack, numbered in the order to run them.
NEW_HOST_SCRIPTS = ("0_CHUAN_BI_MAY_MOI.bat", "CHUAN_BI_MAY_MOI.ps1",
                    "1_KHOI_PHUC_MAY_MOI.bat", "KHOI_PHUC_MAY_MOI.ps1",
                    "2_BAT_DOMAIN_MAY_MOI.bat", "BAT_DOMAIN_MAY_MOI.ps1")


def pack_tools(scripts_dir, destination):
    """Carry the restore tools OUTSIDE the archives they restore.

    The same scripts are inside the app bundle's workspace.tar.gz, but that is
    exactly what they are needed to unpack; a new host must not have to clone
    the repo first.
    """
    scripts_dir = Path(scripts_dir)
    tools = destination / TOOLS
    (tools / "ops").mkdir(parents=True)
    for name in ("migration_pack.py", "deploy.py", "backup.py"):
        shutil.copy2(scripts_dir / name, tools / name)
    for path in sorted((scripts_dir / "ops").glob("*.py")):
        shutil.copy2(path, tools / "ops" / path.name)
    for name in NEW_HOST_SCRIPTS:
        shutil.copy2(scripts_dir / "chuyen_server" / name, destination / name)
    return {"status": "ok", "launchers": list(NEW_HOST_SCRIPTS[::2])}


#: Every column that points at a file. Paths are what the containers saw.
FILE_REFS = (("samples", "file_path"), ("samples", "storage_key"), ("samples", "storage_url"),
             ("raw_uploads", "local_path"), ("raw_uploads", "storage_key"), ("raw_uploads", "storage_url"),
             ("legal_documents", "storage_key"), ("legal_documents", "url"),
             ("legal_document_drafts", "storage_key"), ("legal_document_events", "storage_key"),
             ("training_jobs", "checkpoint_path"), ("tenant_exports", "file_path"),
             ("personal_exports", "file_path"))
CONTAINER_ROOTS = (("/app/dataset", "dataset"), ("/dataset", "dataset"), ("/workspace", ""),
                   ("/gdrive", "gdrive"), ("/app/processed", "processed"))
DRIVE_ID = re.compile(r"(?:/d/|[?&]id=|/folders/)([A-Za-z0-9_-]{20,})")


def resolve_ref(value, root, table):
    """Host file a DB value points at, or None. Mirrors resolve_absolute_path + mounts."""
    text = value.strip().replace("\\", "/")
    for prefix, local in CONTAINER_ROOTS:
        if text == prefix or text.startswith(prefix + "/"):
            return root / local / text[len(prefix):].lstrip("/")
    if re.match(r"^[A-Za-z]:/", text):
        return Path(text)  # Legacy rows written by host-side scripts.
    candidates = [root / "dataset" / text, root / text]
    if table.startswith("legal_"):
        candidates.insert(0, root / "dataset" / "legal" / text)
    return next((c for c in candidates if c.exists()), candidates[0])


def audit_file_refs(stack, target, drive_inventory=None):
    """Prove every file the database points at is in this pack (or on Drive)."""
    root = stack.root
    present = set(json.loads(stack.sql(
        "SELECT coalesce(json_agg(table_name || '.' || column_name), '[]') FROM information_schema.columns "
        "WHERE table_schema = 'public'")))
    drive_ids, drive_paths = set(), set()
    if drive_inventory:
        for item in drive_inventory["files"] + drive_inventory["folders"]:
            drive_ids.add(item["id"])
            drive_paths.add(item.get("path", "").strip("/"))
    report, external, warnings = {}, [], []
    for table, column in FILE_REFS:
        if f"{table}.{column}" not in present:
            continue
        values = json.loads(stack.sql(
            f'SELECT coalesce(json_agg(DISTINCT "{column}"), \'[]\') FROM public."{table}" '
            f'WHERE "{column}" IS NOT NULL AND "{column}" <> \'\''))
        row = {"distinct": len(values), "local": 0, "drive": 0, "external": 0, "missing": []}
        for value in values:
            if value.startswith(("http://", "https://")):
                match = DRIVE_ID.search(value)
                if match and match.group(1) in drive_ids:
                    row["drive"] += 1
                elif match and drive_inventory is None:
                    row["drive"] += 1  # Drive not exported (USE_GOOGLE_DRIVE=0): not checkable here.
                elif match or "google" in value:
                    row["missing"].append(value)
                continue  # Other URLs (public pages) are not files.
            path = resolve_ref(value, root, table)
            if path.is_file() or path.is_dir():
                if inside(path, root):
                    row["local"] += 1
                else:
                    row["external"] += 1
                    external.append(path)
            elif value.strip("/") in drive_paths:
                row["drive"] += 1
            else:
                row["missing"].append(value)
        if row["missing"]:
            warnings.append(f"{table}.{column}: {len(row['missing'])} referenced file(s) not found "
                            f"on this host (see {REPORTS}/db_file_refs.json).")
        report[f"{table}.{column}"] = row
    # Files the DB needs but that live outside the workspace travel in the pack too.
    copied = []
    for index, path in enumerate(sorted(set(external))):
        out = target / REFERENCED / f"{index:05d}-{path.name}"
        out.parent.mkdir(parents=True, exist_ok=True)
        (copy_tree(path, out) if path.is_dir() else shutil.copy2(path, out))
        copied.append({"original": str(path), "stored": out.relative_to(target).as_posix()})
    (target / REPORTS).mkdir(parents=True, exist_ok=True)
    (target / REPORTS / "db_file_refs.json").write_text(json.dumps(
        {"columns": report, "outside_workspace": copied}, indent=1, ensure_ascii=False), encoding="utf-8")
    missing = sum(len(r["missing"]) for r in report.values())
    return {"status": "ok" if not missing else "missing", "columns": len(report), "missing": missing,
            "copied_from_outside": len(copied), "warnings": warnings}


#: Container paths whose changes are runtime noise, not data.
LAYER_NOISE = re.compile(r"(__pycache__|\.pyc$|^/tmp/\.|^/run/|^/var/run/|^/var/cache/|^/var/log/apt|"
                         r"/\.cache(/|$)|^/proc|^/sys|^/dev)")


def pack_container_layers(stack, target):
    """Files written INSIDE containers (not on a mount): lost on recreate, so carry them."""
    saved = []
    for container in compose_containers(stack):
        mounts = [m["Destination"] for m in container.get("Mounts", [])]
        entries, paths = [], set()
        for line in run(["docker", "diff", container["Id"]]).splitlines():
            kind, _, path = line.partition(" ")
            paths.add(path)  # ALL entries: a dir whose only change is noise is still a dir.
            if kind == "D" or LAYER_NOISE.search(path):
                continue
            if any(path == m or path.startswith(m.rstrip("/") + "/") for m in mounts):
                continue
            entries.append((path, kind))
        added = {p for p, k in entries if k == "A"}
        keep = []
        for path, kind in sorted(entries):
            parents = [path.rsplit("/", n)[0] for n in range(1, path.count("/"))]
            if any(p in added for p in parents):
                continue  # Copied with its new parent directory.
            if kind == "C" and any(p.startswith(path + "/") for p in paths):
                continue  # A changed DIRECTORY: copy its changed children, not the image's content.
            keep.append(path)
        name = container["Name"].lstrip("/")
        for index, path in enumerate(keep):
            out = target / name / f"{index:04d}.tar"
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("wb") as stream:
                run(["docker", "cp", f"{container['Id']}:{path}", "-"], output=stream)
            saved.append({"container": name, "path": path, "artifact": out.relative_to(target).as_posix()})
    if saved:
        (target / "layers.json").write_text(json.dumps(saved, indent=1), encoding="utf-8")
    return {"status": "ok" if saved else "absent", "paths": len(saved)}


# ---- manifest ----

def inventory(pack):
    files = {}
    for path in sorted(pack.rglob("*")):
        if is_link(path):
            raise Failure(f"Link inside pack: {path.relative_to(pack)}")
        if path.is_file() and path != pack / MANIFEST:
            files[path.relative_to(pack).as_posix()] = {"size": path.stat().st_size, "sha256": digest(path)}
    return files


def verify_pack(pack):
    pack = Path(pack).resolve()
    try:
        manifest = json.loads((pack / MANIFEST).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Failure("No PACK_MANIFEST.json: the pack is incomplete (creation did not finish).")
    if manifest.get("format") != PACK_FORMAT:
        raise Failure("Unsupported pack format.")
    expected = manifest["files"]
    actual = {p.relative_to(pack).as_posix() for p in pack.rglob("*") if p.is_file() and p != pack / MANIFEST}
    if actual != set(expected):
        extra, missing = sorted(actual - set(expected)), sorted(set(expected) - actual)
        raise Failure(f"Pack contents differ from manifest (missing {missing[:5]}, unexpected {extra[:5]}).")
    for name, info in expected.items():
        path = pack / name
        if is_link(path) or path.stat().st_size != info["size"] or digest(path) != info["sha256"]:
            raise Failure(f"Checksum mismatch: {name}")
    for copy, kept in manifest.get("dedup", {}).items():
        if copy in actual or kept not in expected:
            raise Failure(f"Broken duplicate entry: {copy} -> {kept}")
    verify(pack / APP)
    drive = manifest["sections"].get("drive", {})
    if drive.get("status") == "ok":
        listed = json.loads((pack / DRIVE / "inventory.json").read_text(encoding="utf-8"))
        if listed.get("errors"):
            raise Failure("Drive inventory records failed downloads.")
        stored = [f["stored"] for f in listed["files"] if "stored" in f]
        if any(f"{DRIVE}/{name}" not in expected for name in stored):
            raise Failure("A Drive file listed in the inventory is missing from the pack.")
    return manifest


def describe(manifest):
    lines = [f"Pack created {manifest['created_at']} from {manifest['source']['root']}"]
    for name, section in manifest["sections"].items():
        detail = {k: v for k, v in section.items() if k not in ("status", "warnings", "found")}
        lines.append(f"  {name:<18} {section['status']:<8} {json.dumps(detail, ensure_ascii=False)[:110]}")
    warnings = [w for s in manifest["sections"].values() for w in s.get("warnings", [])]
    for warning in warnings:
        lines.append(f"  WARNING: {warning}")
    total = sum(f["size"] for f in manifest["files"].values())
    lines.append(f"  {len(manifest['files'])} files, {total / 1024**3:.2f} GiB, all SHA-256 verified.")
    return "\n".join(lines)


def readme(manifest):
    git = manifest["sections"].get("git", {})
    url = manifest["source"].get("public_url") or "https://<domain>"
    return f"""# Gói chuyển server SignBridge — {manifest['name']}

Tạo lúc {manifest['created_at']} từ `{manifest['source']['root']}`.
Gói chứa BÍ MẬT (.env, token Drive, token Cloudflare, khoá ký SOT, mật khẩu DB đã băm) và dữ liệu cá nhân:
chỉ chép bằng ổ đã mã hóa (BitLocker To Go), không upload công khai, không đưa vào Git.

| Thư mục | Nội dung |
|---|---|
| `{APP}/` | Mọi database + roles, workspace (source kể cả chưa commit, `.env`, dataset, video thô `raw_videos`, processed, gdrive), named volumes |
| `{GIT}/` | `repo.bundle` toàn bộ lịch sử Git (nhánh `{git.get('branch', '?')}`), `state.json` |
| `{DRIVE}/` | Bản sao toàn bộ cây Google Drive của app + các Google Sheets cấu hình, lưu theo file ID; `inventory.json` ghi đường dẫn gốc |
| `{RELATED_DIR}/` | Thư mục cạnh repo: video mẫu `qipedc_mau`, `voya_test_clips`, `voya_backups`, `voya-migration`, ...; khôi phục thành thư mục ngang hàng với app |
| `{HISTORY}/` | Lịch sử backup: `backups/` của repo, mirror, các `--external` |
| `{IMAGES}/` | Docker images đang chạy (`docker save`) |
| `{VOLUMES}/` | Anonymous volumes của container |
| `{LAYERS}/` | File được ghi BÊN TRONG container (không nằm trên mount), theo `docker diff` |
| `{REFERENCED}/` | File DB trỏ tới nhưng nằm ngoài repo |
| `{HOST}/` | Cloudflared (token, ingress), khoá ký SOT `~/.voya`, scheduled tasks, `.wslconfig`, Docker `daemon.json`, thông tin máy |
| `{REPORTS}/` | `db_file_refs.json`: đối chiếu mọi cột đường dẫn trong DB với file thật (local / Drive / thiếu) |

File giống hệt nhau chỉ lưu một lần; `{MANIFEST}` → `dedup` ghi bản nào trỏ về bản nào, `restore-extras` tạo lại đủ.

## Trên máy mới: 3 file .bat theo thứ tự (chuột phải → Run as administrator)

Giải nén file zip (chuột phải → Extract All, hoặc `tar -xf <file>.zip`) rồi mở thư mục `{manifest['name']}/`.
Chỉ cần cài tay trước: **driver NVIDIA** (nếu muốn GPU). Mọi thứ khác do file 0 lo.

| Thứ tự | File | Làm gì |
|---|---|---|
| 0 | `0_CHUAN_BI_MAY_MOI.bat` | Máy trắng: cài Git, Python 3.12, Docker Desktop (winget), bật WSL2, kiểm driver NVIDIA, **hỏi** rồi mới đặt chế độ nguồn (không ngủ khi cắm sạc). Chạy lại được. Xong thì **khởi động lại máy**, mở Docker Desktop một lần cho tới khi "Engine running" |
| 1 | `1_KHOI_PHUC_MAY_MOI.bat` | Kiểm máy → kiểm SHA-256 → **bản triển khai cũ trên máy (nếu có): sao lưu toàn bộ DB cũ, ghi lại, DỪNG để nhường cổng — không xoá gì, có `QUAY_LAI_BAN_CU.txt`** → dò GPU → nạp Docker images từ gói (**không tải torch/CUDA**) → khôi phục DB/file/volume vào `D:/SignBridge/app` (không có ổ D thì `C:/SignBridge/app`) → Git, lịch sử, video, khoá SOT → chờ `http://127.0.0.1` trả 200 → cài 2 tác vụ Windows (tự bật sau khởi động, canh gác 30 phút) + 2 lối tắt Desktop. **Không đụng domain.** |
| — | (máy cũ) `scripts/chuyen_server/TAT_MAY_CU.bat` | Dừng service Cloudflared (Disabled) và stack cũ. Không xoá gì; `-HoanTac` để bật lại |
| 2 | `2_BAT_DOMAIN_MAY_MOI.bat` | Hỏi xác nhận máy cũ đã tắt → cài connector của **chính tunnel hiện có** bằng token trong gói → chờ tunnel sẵn sàng → kiểm tra {url} trả 200 |

Bản cũ khác schema không sao: bản mới chạy project và volume RIÊNG, DB cũ không bị đọc hay ghi đè.
Nếu bản cũ có mẫu MỚI hơn lúc tạo gói, `so_lieu_ban_cu.txt` trong thư mục dự phòng sẽ cho thấy — cần hợp nhất sau.
Sau khi xong, vận hành bằng lối tắt **VOYA - Bảng điều khiển** trên Desktop.

Đổi thư mục cài: `1_KHOI_PHUC_MAY_MOI.bat -AppRoot E:/SignBridge/app`. Nhật ký ghi ra `khoi-phuc_{manifest['name']}.log` cạnh thư mục gói.
DNS không đổi: domain → tunnel → `localhost:80` của máy đang chạy connector. **Không bao giờ** để hai máy cùng chạy connector.

Công cụ dùng bởi hai file trên nằm trong `{TOOLS}/` (bản sao `scripts/migration_pack.py`, `deploy.py`, `backup.py`, `ops/`).
Drive KHÔNG được tải lên lại: máy mới tiếp tục dùng cùng Drive (giữ file ID); `{DRIVE}/` là bản sao độc lập để đối chiếu/cứu dữ liệu.

Route hiện tại xem trong `{HOST}/cloudflared/ingress.json`; giữ Nginx publish ở port 80 trên máy mới.
"""


def create(stack, destination, *, drive_cache=None, extra_history=(), skip_images=False,
           keep_stopped=False, skip_drive=False, skip_related=False):
    destination = Path(destination).resolve()
    root = stack.root
    if destination.exists() or inside(destination, root) or inside(root, destination):
        raise Failure("Pack path must be NEW and OUTSIDE the workspace.")
    env = stack.config["services"]["backend"]["environment"]
    histories = history_sources(root, env, extra_history)
    # Gói GỌN (17/10/2026): máy mới tự dựng image, vẫn dùng chung Drive, thư mục
    # phụ cạnh repo ở lại máy cũ. Chỉ dữ liệu ứng dụng + lịch sử Git + cấu hình máy.
    related = {} if skip_related else related_sources(root)
    for path in [*histories.values(), *related.values()]:
        if inside(destination, path) or inside(path, destination):
            raise Failure(f"Pack path overlaps a history/related folder: {path}")
    uses_drive = str(env.get("USE_GOOGLE_DRIVE", "0")).lower() in ("1", "true") and not skip_drive
    need = (tree_size(root, skip={"node_modules", ".git", "__pycache__", "backups"})
            + tree_size(root / ".git") + sum(tree_size(p) for p in [*histories.values(), *related.values()]))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(destination.parent).free < need * 1.1 + 20 * 1024**3:
        raise Failure(f"Destination needs > {need * 1.1 / 1024**3 + 20:.0f} GiB free "
                      "(local data + 10% + 20 GiB for images/Drive).")
    destination.mkdir(mode=0o700)
    dedup = Dedup(destination)
    sections = {}
    # Phase 1, writers still running: content that live traffic does not change.
    print("[1/4] Restore tools, Git history, Docker images, host configuration...")
    sections["tools"] = pack_tools(root / "scripts", destination)
    sections["git"] = pack_git(root, destination / GIT)
    sections["images"] = ({"status": "skipped", "warnings": ["Images skipped by --skip-images."]}
                          if skip_images else pack_images(stack, destination / IMAGES))
    sections["host"] = pack_host(destination / HOST)
    # The app never writes these folders, so copy them while it still serves.
    print("  Related folders next to the repo (videos, old dumps)...")
    for name, path in related.items():
        copy_tree(path, destination / RELATED_DIR / name, dedup)
    sections["related"] = {"status": "ok" if related else "absent",
                           "folders": {n: str(p) for n, p in related.items()}}
    if uses_drive and drive_cache:
        print("  Seeding Drive copy from the pre-synced cache...")
        copy_tree(drive_cache, destination / DRIVE)
    running = stack.running()
    stopped = [s for s in running if s != "postgres"]
    completed = False
    try:
        # Phase 2: the consistent snapshot. backup() stops writers and, with
        # resume=False, leaves them stopped so phase 3 sees the same state.
        print("[2/4] Application bundle (writers stopped)...")
        backup(stack, destination / APP, accept_external=True, resume=False)
        sections["app-bundle"] = {"status": "ok"}
        print("[3/4] Drive, backup history, volumes, container files, DB file references...")
        sections["drive"] = (drive_sync(stack, destination / DRIVE) if uses_drive
                             else {"status": "skipped", "warnings": ["Drive copy skipped by --skip-drive; "
                                   "the new host keeps using the same Drive (same file IDs)."]}
                             if skip_drive else {"status": "absent"})
        for label, path in histories.items():
            copy_tree(path, destination / HISTORY / label, dedup)
        sections["history"] = {"status": "ok", "sources": {k: str(v) for k, v in histories.items()}}
        sections["volumes"] = pack_anonymous_volumes(stack, destination / VOLUMES)
        sections["container-files"] = pack_container_layers(stack, destination / LAYERS)
        inventory_file = destination / DRIVE / "inventory.json"
        drive_inventory = (json.loads(inventory_file.read_text(encoding="utf-8"))
                           if sections["drive"]["status"] == "ok" else None)
        sections["db-file-refs"] = audit_file_refs(stack, destination, drive_inventory)
        print("[4/4] Checksums...")
        manifest = {"format": PACK_FORMAT, "name": destination.name, "created_at": datetime.now(timezone.utc).isoformat(),
                    "source": {"root": str(root), "host": platform.node(),
                               "public_url": env.get("FRONTEND_BASE_URL")},
                    "sections": sections, "dedup": dedup.links}
        sections["dedup"] = {"status": "ok", "duplicates": len(dedup.links),
                             "saved_gib": round(dedup.saved / 1024**3, 2)}
        (destination / README).write_text(readme(manifest), encoding="utf-8")
        manifest["files"] = inventory(destination)
        # Written LAST: a pack without it is, by definition, incomplete.
        (destination / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        verify_pack(destination)
        completed = True
        print(describe(manifest))
        print(f"Verified migration pack: {destination}. Contains secrets; use encrypted storage.")
    finally:
        if stopped and (not keep_stopped or not completed) and "app-bundle" in sections:
            stack.call("start", *stopped)
            stack.wait(stopped, seconds=300)
    return manifest


def plan(root, extra_history=(), destination=None):
    """Read-only size estimate; works with Docker stopped."""
    root = Path(root).resolve()
    env = env_read(root / ".env") if (root / ".env").exists() else {}
    rows = [(f"workspace (-> {APP})", tree_size(root, skip={"node_modules", ".git", "__pycache__", "backups"})),
            ("git history", tree_size(root / ".git"))]
    for label, path in history_sources(root, env, extra_history).items():
        rows.append((f"{HISTORY}/{label}", tree_size(path)))
    related = related_sources(root)
    for name, path in related.items():
        rows.append((f"{RELATED_DIR}/{name}", tree_size(path)))
    for label, size in rows:
        print(f"  {label:<62} {size / 1024**3:8.2f} GiB")
    print(f"  {'TOTAL local':<62} {sum(s for _, s in rows) / 1024**3:8.2f} GiB "
          "(+ Docker images, + Drive, + database dump)")
    if str(env.get("USE_GOOGLE_DRIVE", "0")).lower() in ("1", "true"):
        print("  Drive: enabled; size known only after `drive-sync` (pre-copy it while the site is live).")
    others = sorted(p.name for p in root.parent.iterdir()
                    if p.is_dir() and p != root and p.name not in related
                    and not any(inside(p, Path(x)) for x in extra_history))
    if others:
        print("  NOT included (other projects next to the repo; add with --external if needed):")
        print("    " + ", ".join(others))
    if destination:
        parent = Path(destination).resolve()
        while not parent.exists():
            parent = parent.parent
        print(f"  Free at {parent}: {shutil.disk_usage(parent).free / 1024**3:.1f} GiB")


def place(source, out):
    """Copy without ever overwriting a different file."""
    if out.exists():
        if digest(out) != digest(source):
            raise Failure(f"Different file already at {out}; refusing to overwrite.")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, out)


def restore_extras(pack, root, *, history_root=None, load_images=True):
    """After deploy.py --restore: Git, backup history and images. Never overwrites."""
    pack, root = Path(pack).resolve(), Path(root).resolve()
    manifest = verify_pack(pack)
    if not (root / ".env").is_file():
        raise Failure("Run deploy.py --restore first; --root must be the restored application.")
    git = manifest["sections"].get("git", {})
    if git.get("status") == "ok":
        if (root / ".git").exists():
            print("Git: .git already exists in the target, left untouched.")
        else:
            g = ["git", "-C", str(root)]
            run(g + ["init", "-q"])
            run(g + ["fetch", "-q", "--update-head-ok", str(pack / GIT / "repo.bundle"), "+refs/*:refs/*"], timeout=LONG)
            for name, url in git.get("remotes", {}).items():
                run(g + ["remote", "add", name, url])
            run(g + ["symbolic-ref", "HEAD", f"refs/heads/{git['branch']}"])
            # Mixed reset: index = HEAD, working tree (the restored files) untouched,
            # so uncommitted changes show up exactly as they were on the old host.
            run(g + ["reset", "-q"])
            print(f"Git: history restored on branch {git['branch']}.")
    history_root = Path(history_root or root.parent / "migrated-history").resolve()
    links = manifest.get("dedup", {})
    for scope in (HISTORY, RELATED_DIR):
        # Names from the manifest, not the folder listing: a folder made only of
        # duplicates has no files in the pack, and copy tools drop empty dirs.
        names = {n.split("/")[1] for n in [*manifest["files"], *links] if n.startswith(scope + "/")}
        for name in sorted(names):
            if scope == RELATED_DIR:
                target = root.parent / name
            else:
                target = root / "backups" if name == "backups" else history_root / name
            prefix = f"{scope}/{name}/"
            files = {n: n for n in manifest["files"] if n.startswith(prefix)}
            files.update({n: kept for n, kept in links.items() if n.startswith(prefix)})
            for rel, stored in files.items():
                place(pack / stored, target / rel[len(prefix):])
            print(f"Copied: {name} -> {target} ({len(files)} files)")
    voya = pack / HOST / "voya-home"
    if voya.is_dir():
        home = Path.home() / ".voya"
        for path in voya.rglob("*"):
            out = home / path.relative_to(voya)
            if path.is_file() and not out.exists():
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, out)
            elif path.is_file() and digest(out) != digest(path):
                raise Failure(f"A different {out} already exists; refusing to overwrite the SOT key.")
        print(f"SOT key: {home}")
    if load_images and (pack / IMAGES / "images.tar").is_file():
        run(["docker", "load", "-i", str(pack / IMAGES / "images.tar")], timeout=LONG)
        for entry in json.loads((pack / IMAGES / "images.json").read_text(encoding="utf-8")):
            if entry["saved_as"] == entry["id"]:
                # Tag under a pack-specific name: the restored deploy builds its own :latest.
                repo = entry["tag"].rsplit(":", 1)[0]
                run(["docker", "tag", entry["id"], f"{repo}:pack-{entry['id'].split(':')[-1][:12]}"])
        print("Images: loaded.")
    print(f"Not applied automatically: Cloudflare connector and scheduled tasks (see {README}),"
          f" anonymous volumes in {VOLUMES}/ (archival).")


# ---- zip: one file to carry, named exactly like the pack folder ----

#: Already compressed: deflating them again costs hours and saves nothing.
STORED = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".gz", ".tgz", ".zip", ".npz", ".dump", ".gpg",
          ".bundle", ".png", ".jpg", ".jpeg", ".pt", ".pth", ".xlsx", ".docx", ".pptx", ".pdf"}


def zip_pack(pack):
    """`<name>/` -> `<name>.zip` + `<name>.zip.sha256`, side by side. The pack stays."""
    pack = Path(pack).resolve()
    verify_pack(pack)  # Never zip a pack that is already broken.
    archive = pack.with_name(pack.name + ".zip")
    if archive.exists():
        raise Failure(f"{archive.name} already exists; refusing to overwrite.")
    partial = archive.with_name(archive.name + ".part")
    partial.unlink(missing_ok=True)
    size = sum(p.stat().st_size for p in pack.rglob("*") if p.is_file())
    if shutil.disk_usage(pack.parent).free < size * 1.02 + 1024**3:
        raise Failure(f"Zip needs about {size / 1024**3:.1f} GiB free next to the pack.")
    with zipfile.ZipFile(partial, "x", allowZip64=True) as output:
        for path in sorted(pack.rglob("*")):
            if path.is_file():
                # Everything under ONE top folder: extracting never spills files around.
                name = f"{pack.name}/{path.relative_to(pack).as_posix()}"
                if path.suffix.lower() in STORED:
                    output.write(path, name, compress_type=zipfile.ZIP_STORED)
                else:
                    output.write(path, name, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    with zipfile.ZipFile(partial) as check:
        bad = check.testzip()  # Re-reads every member and checks its CRC.
    if bad:
        raise Failure(f"Zip CRC check failed for {bad}; {partial.name} kept for inspection.")
    partial.replace(archive)
    checksum = archive.with_name(archive.name + ".sha256")
    # `sha256sum -c` format, so Linux can check it too.
    checksum.write_text(f"{digest(archive)}  {archive.name}\n", encoding="ascii")
    print(f"Zip: {archive} ({archive.stat().st_size / 1024**3:.2f} GiB), checksum {checksum.name}")
    return archive


def unzip_pack(archive, base):
    """Check SHA-256, extract under `<base>/SignBridge_ChuyenServer/`, then verify the pack."""
    archive = Path(archive).resolve()
    checksum = archive.with_name(archive.name + ".sha256")
    if not checksum.is_file():
        raise Failure(f"Missing {checksum.name}; copy it next to the zip (it proves the copy is intact).")
    if checksum.read_text(encoding="ascii").split()[0] != digest(archive):
        raise Failure("Zip SHA-256 mismatch: the file was damaged while copying. Copy it again.")
    home = migration_home(base)
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        tops = {m.filename.split("/", 1)[0] for m in members}
        if len(tops) != 1:
            raise Failure("Zip must contain exactly one top folder (the pack).")
        top = tops.pop()
        for member in members:
            parts = member.filename.split("/")
            if (member.filename.startswith(("/", "\\")) or ".." in parts or "\\" in member.filename
                    or ":" in member.filename):
                raise Failure(f"Unsafe zip entry: {member.filename}")
        target = home / top
        if target.exists():
            raise Failure(f"{target} already exists; refusing to overwrite.")
        home.mkdir(parents=True, exist_ok=True)
        size = sum(m.file_size for m in members)
        if shutil.disk_usage(home).free < size * 1.05:
            raise Failure(f"Need {size / 1024**3:.1f} GiB free at {home}.")
        source.extractall(home)
    manifest = verify_pack(target)
    print(f"Unzipped and verified: {target}")
    return target, manifest
