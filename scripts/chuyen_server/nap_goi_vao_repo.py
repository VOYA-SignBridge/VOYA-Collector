#!/usr/bin/env python3
"""Nạp gói chuyển server vào CHÍNH repo VOYA-Collector trên máy mới, rồi dựng và chạy web từ đó.

Khác `1_KHOI_PHUC_MAY_MOI.bat` (khôi phục vào một thư mục MỚI, `D:/SignBridge/app`): ở đây
mã nguồn đến từ `git pull`, còn gói chỉ góp những gì git KHÔNG mang:

    DB (schema + dữ liệu mọi tổ chức + role)      từ 01_ung-dung-va-database/*.dump, roles.sql
    .env, frontend/.env, deploy/public_hosts.txt   cấu hình + mật khẩu + khoá của máy cũ
    geoip/, gdrive/, backend/secrets/              cơ sở dữ liệu GeoIP, thông tin đăng nhập Drive
    dataset/, processed/                           mẫu, video, CSV, văn bản pháp lý, splits
    ~/.voya/sot_private.key                        khoá ký SOT (máy này thành máy phát hành)

Chỉ nạp tệp git KHÔNG theo dõi: tệp có trong repo luôn là bản của `git pull`.

Bản triển khai cũ của chính repo này (nếu có) KHÔNG bị xoá:
    * DB cũ: pg_dumpall vào thư mục dự phòng, volume postgres cũ chép sang `<tên>_cu_<giờ>`
    * tệp ẩn cũ (.env, dataset/, ...): DỜI vào thư mục dự phòng
    * container cũ: `docker compose down` (không -v)

Rồi: dựng image từ mã nguồn, migrate, cấp role, kiểm, bật dịch vụ (scripts/ops/deployment.deploy),
cài tác vụ tự bật, tải dữ liệu còn thiếu từ Drive và video mẫu QIPEDC.

Chạy trong repo đã `git pull` (Git Bash hoặc PowerShell), Docker Desktop đang chạy:
    python scripts/chuyen_server/nap_goi_vao_repo.py --pack D:/SignBridge_ChuyenServer/SignBridge_ChuyenServer_2026-10-18_15h10
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from ops.deployment import deploy, restore_database  # noqa: E402
from ops.pack import APP, HOST, verify_pack  # noqa: E402
from ops.transfer import (HOST_STATE, Failure, Stack, complete_role_passwords,  # noqa: E402
                          configure, inside, run, safe_members, verify)

#: Tệp/thư mục git bỏ qua mà ứng dụng CẦN để chạy. Mọi thứ khác trong gói (log,
#: scratchpad, bản đo, bản dump cũ...) ở lại.
NEEDED = (".env", "frontend/.env", "deploy/public_hosts.txt",
          "geoip/", "gdrive/", "backend/secrets/", "dataset/", "processed/")
CONFIRM = "NAP VAO REPO"


def say(text: str) -> None:
    print(text, flush=True)


def tracked_files(root: Path) -> set[str]:
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True)
    return {p for p in out.stdout.decode("utf-8").split("\0") if p}


def is_needed(name: str) -> bool:
    return any(name == n or (n.endswith("/") and name.startswith(n)) for n in NEEDED)


def local_needed_files(root: Path, tracked: set[str]) -> list[Path]:
    """Tệp ẩn đang có của bản cũ (để dời đi trước khi nạp bản mới)."""
    found = []
    for n in NEEDED:
        p = root / n.rstrip("/")
        if p.is_file():
            if n.rstrip("/") not in tracked:
                found.append(p)
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file() and f.relative_to(root).as_posix() not in tracked:
                    found.append(f)
    return found


def old_containers() -> list[str]:
    """Container của bản cũ (`voya_*`). Gọi `docker` trực tiếp, KHÔNG qua compose: `.env` cũ
    có thể thiếu biến mà docker-compose.yml mới (vừa pull) đòi, và compose sẽ từ chối chạy."""
    return [n for n in run(["docker", "ps", "-a", "--format", "{{.Names}}"]).splitlines()
            if n.startswith("voya_")]


def backup_old_db(names: list[str], backup: Path) -> None:
    pgs = [n for n in names if "postgres" in n and "backup" not in n]
    for pg in pgs:
        run(["docker", "start", pg])
        for _ in range(60):
            if subprocess.run(["docker", "exec", pg, "sh", "-c", "pg_isready -q -U $POSTGRES_USER"],
                              capture_output=True).returncode == 0:
                break
            time.sleep(2)
        else:
            raise Failure(f"Postgres cũ ({pg}) không lên — không sao lưu được, chưa đụng gì.")
        run(["docker", "exec", pg, "sh", "-c", "pg_dumpall -U $POSTGRES_USER -f /tmp/du_phong.sql"])
        dest = backup / f"{pg}_pg_dumpall.sql"
        run(["docker", "cp", f"{pg}:/tmp/du_phong.sql", str(dest)])
        if dest.stat().st_size < 1024:
            raise Failure("Bản sao lưu DB cũ quá nhỏ — dừng, chưa đụng gì.")
        say(f"  DB cũ: {dest} ({dest.stat().st_size / 1e6:.1f} MB)")


def postgres_volume(name: str) -> str | None:
    mounts = json.loads(run(["docker", "inspect", "--format", "{{json .Mounts}}", name]))
    return next((m["Name"] for m in mounts if m.get("Type") == "volume"
                 and m.get("Destination") == "/var/lib/postgresql/data"), None)


def retire_old(names: list[str], pg_image: str, stamp: str) -> None:
    """Gỡ container cũ (không -v) và chép volume DB cũ sang tên `_cu_<giờ>` để DB mới khởi tạo sạch."""
    volumes = [v for v in (postgres_volume(n) for n in names if "postgres" in n and "backup" not in n) if v]
    run(["docker", "stop", "-t", "120", *names])
    run(["docker", "rm", *names])
    for vol in volumes:
        copy = f"{vol}_cu_{stamp}"
        run(["docker", "volume", "create", copy])
        run(["docker", "run", "--rm", "-v", f"{vol}:/from:ro", "-v", f"{copy}:/to",
             "--entrypoint", "sh", pg_image, "-c", "cp -a /from/. /to/"], timeout=3600)
        run(["docker", "volume", "rm", vol])
        say(f"  Volume DB cũ giữ ở: {copy}")


def extract_needed(workspace: Path, root: Path, tracked: set[str]) -> int:
    count = 0
    with tarfile.open(workspace, "r:gz") as archive:
        for member in safe_members(archive):
            name = member.name
            if not member.isfile() or not is_needed(name) or name in tracked or name in HOST_STATE:
                continue
            dest = root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)
            count += 1
    return count


def gpu_available() -> bool:
    return subprocess.run(["docker", "run", "--rm", "--gpus", "all", "alpine:3.20", "true"],
                          capture_output=True).returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", type=Path, required=True, help="thư mục gói đã giải nén")
    ap.add_argument("--backup-dir", type=Path, help="mặc định: cạnh thư mục gói")
    ap.add_argument("--yes", action="store_true", help=f"không hỏi '{CONFIRM}'")
    ap.add_argument("--bo-qua-qipedc", action="store_true", help="không tải video mẫu QIPEDC (~2,7 GB)")
    args = ap.parse_args()

    pack = args.pack.resolve()
    # "Extract All" của Windows thêm một tầng cùng tên quanh thư mục gốc có sẵn trong zip.
    if not (pack / "PACK_MANIFEST.json").is_file() and (pack / pack.name / "PACK_MANIFEST.json").is_file():
        pack = pack / pack.name
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    backup = (args.backup_dir or pack.parent / f"du_phong_VOYA-Collector_{stamp}").resolve()
    if inside(pack, ROOT) or inside(backup, ROOT):
        raise Failure("Gói và thư mục dự phòng phải nằm NGOÀI repo.")

    say(f"[1/8] Kiểm gói {pack.name} (SHA-256 mọi tệp)")
    verify_pack(pack)
    bundle = pack / APP
    manifest = verify(bundle)
    if run(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"]):
        raise Failure("Repo còn thay đổi chưa commit ở tệp được theo dõi — commit hoặc stash trước.")
    say(f"  Repo: {ROOT} @ {run(['git', '-C', str(ROOT), 'log', '--oneline', '-1'])}")

    tracked = tracked_files(ROOT)
    old_files = local_needed_files(ROOT, tracked)
    names = old_containers()
    say(f"[2/8] Bản cũ: {len(names)} container voya_*, "
        f"{len(old_files)} tệp ẩn sẽ được dời vào {backup}")
    if not args.yes and input(f"  Gõ {CONFIRM} để tiếp tục (Enter = huỷ): ").strip().upper() != CONFIRM:
        say("Đã huỷ, chưa đụng gì.")
        return 1
    backup.mkdir(parents=True)

    if names:
        say("[3/8] Sao lưu DB cũ, giữ volume DB cũ, gỡ container cũ (không xoá volume/thư mục)")
        (backup / "containers_cu.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
        backup_old_db(names, backup)
        retire_old(names, manifest["postgres_image"], stamp)
    else:
        say("[3/8] Không có bản cũ đang chạy.")
    for f in old_files:
        dest = backup / "tep_an_cu" / f.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), str(dest))

    say("[4/8] Nạp tệp ẩn từ gói vào repo (.env, geoip, gdrive, dataset, processed, ...)")
    n = extract_needed(bundle / "workspace.tar.gz", ROOT, tracked)
    say(f"  {n} tệp.")
    gpu = gpu_available()
    files = "docker-compose.yml:docker-compose.prod.yml" + (":docker-compose.gpu.yml" if gpu else "")
    configure(ROOT, {"COMPOSE_FILE": files})
    say(f"  GPU: {'có' if gpu else 'không'} -> COMPOSE_FILE={files}")
    key_src = pack / HOST / "voya-home" / "sot_private.key"
    key_dst = Path.home() / ".voya" / "sot_private.key"
    if key_src.is_file() and not key_dst.exists():
        key_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(key_src, key_dst)
        say(f"  Khoá ký SOT: {key_dst}")

    say("[5/8] Khôi phục DB vào volume mới (role + dữ liệu, so số dòng từng bảng)")
    stack = Stack(ROOT, gpu=gpu)
    if complete_role_passwords(stack):
        stack = Stack(ROOT, gpu=gpu)
    if stack.pg_image != manifest["postgres_image"]:
        raise Failure("Image PostgreSQL khác bản trong gói.")
    stack.call("up", "-d", "postgres")
    stack.wait(["postgres"])
    restore_database(stack, bundle, manifest)

    say("[6/8] Dựng image từ mã nguồn, migrate, cấp role, kiểm, bật dịch vụ (lần đầu lâu, cần mạng)")
    deploy(stack, restored=True, accept_external=True)

    say("[7/8] Tác vụ Windows tự bật stack sau khởi động")
    env = dict(os.environ, VOYA_CONFIRMED="co")
    for cmd in (["start"], ["autostart", "install"]):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "voya.py"), *cmd], env=env)
        if r.returncode:
            say(f"  CẢNH BÁO: voya.py {' '.join(cmd)} lỗi (chạy lại bằng quyền admin).")

    say("[8/8] Tải dữ liệu không mang theo gói")
    try:
        say("  " + stack.call("exec", "-T", "-w", "/app", "worker", "python", "-c",
                              "from app.sync_tasks import download_missing_files_to_local as t; "
                              "print(t.apply().get())", timeout=7200))
    except Failure as exc:
        say(f"  CẢNH BÁO: tải từ Drive lỗi ({exc}); chạy lại 3_TAI_DU_LIEU_MAY_MOI.bat -AppRoot {ROOT}")
    if not args.bo_qua_qipedc:
        dest = ROOT.parent / "qipedc_mau"
        dest.mkdir(exist_ok=True)
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "tai_mau_qipedc.py"), "--thu-muc", str(dest)])
        if r.returncode:
            say("  CẢNH BÁO: tải QIPEDC dừng giữa chừng; chạy lại để tải tiếp.")

    say("")
    say("XONG: web chạy từ repo này, chưa bật domain.")
    say("  1. Mở http://localhost , đăng nhập bằng tài khoản ở máy cũ.")
    say("  2. Máy cũ: scripts\\chuyen_server\\TAT_MAY_CU.bat (Run as administrator).")
    say(f"  3. Máy này: {pack / '2_BAT_DOMAIN_MAY_MOI.bat'} (Run as administrator).")
    say(f"  Dự phòng bản cũ: {backup}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        raise SystemExit(main())
    except Failure as exc:
        say(f"DỪNG LẠI: {exc}")
        raise SystemExit(2)
