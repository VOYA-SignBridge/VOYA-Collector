"""Is the code that is RUNNING the code that is in the working tree?

    python scripts/check_deploy_freshness.py

Exit 0 = everything running is current, 1 = something is stale. Read-only.

Why this exists rather than `docker compose ps`:

  Every container reported "healthy" while the frontend image was five hours
  old, so none of the frontend work of that session was actually running. A
  health check answers "is the process alive", never "is it the process you
  just built" — and a stale bundle fails in the one place a health check cannot
  look: the browser. The page loaded fine. It was the previous page.

Three ways to be stale, three different fixes — which is why they are reported
separately rather than as one "out of date":

  1. TAG CU        source is newer than the image that bakes it
                   -> docker compose build <service>
  2. CONTAINER CU  the tag was rebuilt but the container still runs the previous
                   image id. `restart` re-runs the OLD image; only recreation
                   picks up a new one.
                   -> docker compose up -d --force-recreate <service>
  3. CAN RESTART   the service bind-mounts its source instead of baking it, and
                   the source changed after the container started. Rebuilding
                   would do nothing here.
                   -> docker compose restart <service>

Only the paths a Dockerfile actually COPYs are compared, so editing
backend/tests/ does not claim the backend image is stale — tests never enter it.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", ".pytest_cache", ".mypy_cache",
    "dist", "build", ".venv", "venv", ".vite", "coverage", "checkpoints",
}
SKIP_SUFFIXES = {".pyc", ".pyo", ".log", ".pt", ".npz", ".zip", ".md"}

# What each image is actually made of. Derived from the COPY lines of its
# Dockerfile — NOT from the build context, which is much wider than the image.
#
#   baked   = the code lives inside the image; needs build + force-recreate
#   mounted = the code is bind-mounted at runtime; needs restart only
IMAGES = {
    "voya_backend:latest": {
        "mode": "baked",
        # backend/Dockerfile: COPY app/ ./app/  +  COPY requirements.txt .
        "paths": ["backend/app", "backend/requirements.txt", "backend/Dockerfile"],
    },
    "voya_frontend:latest": {
        "mode": "baked",
        # frontend/Dockerfile: COPY . .  (minus .dockerignore)
        "paths": ["frontend"],
    },
    "voya_realtime_service:latest": {
        "mode": "mounted",
        # Its Dockerfile copies requirements.txt and nothing else; the service
        # code arrives through bind mounts declared in docker-compose.yml.
        "paths": [
            "backend/realtime_service/requirements.txt",
            "backend/realtime_service/Dockerfile",
        ],
        "mounted_paths": ["backend/realtime_service", "processed/shared"],
    },
}


def sh(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True).stdout.strip()


def newest(paths: list[str]) -> tuple[float, Path | None]:
    """Newest mtime across the given repo-relative files/directories."""
    best, best_path = 0.0, None

    def consider(p: Path) -> None:
        nonlocal best, best_path
        try:
            m = p.stat().st_mtime
        except OSError:
            return
        if m > best:
            best, best_path = m, p

    for rel in paths:
        target = REPO / rel
        if target.is_file():
            consider(target)
            continue
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if Path(f).suffix in SKIP_SUFFIXES:
                    continue
                consider(Path(root) / f)
    return best, best_path


def fmt(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%m-%d %H:%M") if ts else "-"


def rel(p: Path | None) -> str:
    if p is None:
        return "?"
    try:
        return p.relative_to(REPO).as_posix()
    except ValueError:
        return str(p)


def main() -> int:
    cfg = sh("docker", "compose", "config", "--format", "json")
    if not cfg:
        print("FAIL  khong doc duoc `docker compose config` - dang o dung thu muc repo chua?")
        return 1

    # One image backs several services (voya_backend runs backend, worker,
    # trainer, celery-beat, sot-init) — every one of them must be recreated.
    users: dict[str, list[str]] = {}
    for name, svc in json.loads(cfg).get("services", {}).items():
        if svc.get("build") and svc.get("image") in IMAGES:
            users.setdefault(svc["image"], []).append(name)

    problems: list[str] = []
    print(f"{'image':30} {'built':13} {'nguon':13} trang thai")
    print("-" * 78)

    for img, spec in sorted(IMAGES.items()):
        created_raw = sh("docker", "image", "inspect", "-f", "{{.Created}}", img)
        if not created_raw:
            print(f"{img:30} {'-':13} {'-':13} CHUA CO IMAGE")
            problems.append(f"{img}: chua build bao gio -> docker compose build")
            continue
        created = datetime.fromisoformat(created_raw.replace("Z", "+00:00")).timestamp()
        src_ts, src_path = newest(spec["paths"])
        svcs = sorted(users.get(img, []))

        note = "ok"
        if src_ts > created:
            note = "TAG CU"
            problems.append(
                f"{img}: {rel(src_path)} moi hon image "
                f"-> docker compose build {svcs[0] if svcs else ''}".rstrip()
            )
        print(f"{img:30} {fmt(created):13} {fmt(src_ts):13} {note}")

        tag_id = sh("docker", "image", "inspect", "-f", "{{.Id}}", img)
        for svc in svcs:
            cid = sh("docker", "compose", "ps", "-q", svc)
            if not cid:
                continue
            cid = cid.splitlines()[0]
            run_id = sh("docker", "inspect", "-f", "{{.Image}}", cid)
            if spec["mode"] == "baked" and run_id and tag_id and run_id != tag_id:
                print(f"{'':30} {'':13} {'':13}   +-- {svc}: CONTAINER CU")
                problems.append(
                    f"{svc}: dang chay image cu hon tag "
                    f"-> docker compose up -d --force-recreate {svc}"
                )
            if spec["mode"] == "mounted":
                started_raw = sh("docker", "inspect", "-f", "{{.State.StartedAt}}", cid)
                if not started_raw:
                    continue
                started = datetime.fromisoformat(started_raw[:26] + "+00:00").timestamp()
                mnt_ts, mnt_path = newest(spec.get("mounted_paths", []))
                if mnt_ts > started:
                    print(f"{'':30} {'':13} {'':13}   +-- {svc}: CAN RESTART")
                    problems.append(
                        f"{svc}: {rel(mnt_path)} doi sau khi container khoi dong "
                        f"-> docker compose restart {svc}"
                    )

    print()
    if problems:
        print(f"{len(problems)} van de:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("Tat ca image va container deu khop voi ma nguon.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
