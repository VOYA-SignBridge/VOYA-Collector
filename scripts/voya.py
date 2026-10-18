"""VOYA — một cửa cho mọi việc vận hành. Bấm đúp VOYA.bat, hoặc gõ:

    python scripts/voya.py            menu đánh số
    python scripts/voya.py status     chạy thẳng một lệnh (xem `help`)

Không chứa logic nghiệp vụ: mỗi lệnh gọi lại đúng script/lệnh đã có
(docker compose, run_tests.sh, migration_pack.py, docker_gc.sh, ...), để chỉ
còn MỘT tên phải nhớ. Lệnh có rủi ro hỏi xác nhận trước khi chạy.

`docker compose` luôn gọi TRẦN trong thư mục repo: COMPOSE_FILE trong .env giữ
đúng overlay prod + gpu (gõ tay danh sách -f từng làm rơi GPU, xem
docs/06-operations/DEPLOY_SECOND_MACHINE.md §3.1).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
BASE_IMAGE = os.environ.get("VOYA_BACKEND_BASE", "voya_backend:base")
BACKEND_IMAGE_SERVICES = ("backend", "worker", "trainer", "celery-beat", "sot-init")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 VOYA-status"

for stream in (sys.stdout, sys.stderr):  # Vietnamese on a cp1252 console.
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------- helpers

#: Chạy nền (Scheduled Task qua pythonw): không có console, nên tiến trình con
#: không được bật cửa sổ đen lên màn hình người đang dùng máy.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.stdout is None or os.environ.get("VOYA_HEADLESS") else 0


def sh(args, *, check=True, capture=False, cwd=ROOT, timeout=None, env=None):
    """Run a command in the repo. Streams output unless `capture`."""
    result = subprocess.run(args, cwd=cwd, text=True, encoding="utf-8", errors="replace",
                            capture_output=capture, timeout=timeout, creationflags=NO_WINDOW,
                            env=dict(os.environ, **env) if env else None)
    if check and result.returncode != 0:
        raise SystemExit(f"Lenh that bai ({result.returncode}): {' '.join(map(str, args))}")
    return result


def compose(*args, **kw):
    return sh(["docker", "compose", *args], **kw)


#: Trạng thái vận hành của MÁY NÀY (đã nằm trong .gitignore): nhật ký thao tác,
#: lần triển khai gần nhất, trạng thái canh gác.
STATE_DIR = ROOT / ".voya"
ACTIONS_LOG = STATE_DIR / "actions.jsonl"
DEPLOY_STATE = STATE_DIR / "deploy_state.json"
WATCH_STATE = STATE_DIR / "watch_state.json"
#: nginx kiểm sự có mặt của tệp này ở MỖI request (nginx.conf, khối "Bảo trì").
MAINT_FLAG = ROOT / "nginx.conf.d" / "maintenance.on"
#: Admin CỐ Ý dừng stack (voya stop, tạo gói chuyển server). Canh gác và lượt
#: khởi động sau khi bật máy KHÔNG được tự bật lại — nếu không, tác vụ 30 phút sẽ
#: hồi sinh stack giữa lúc đóng gói và gói mất nhất quán.
STOPPED_FLAG = STATE_DIR / "stopped_intentionally.json"
#: Một lượt triển khai / quay lui tại một thời điểm, dù gọi từ VOYA.bat hay bảng điều khiển.
DEPLOY_LOCK = STATE_DIR / "deploy.lock"
#: Không gắn attestation (provenance/SBOM) mặc định của buildx: với nó, mỗi lần
#: dựng lại — kể cả cache 100% — ra một image ID MỚI cùng nội dung, `compose`
#: không tạo lại container, và tag `latest` lệch khỏi image đang chạy (17/10/2026).
BUILD_ENV = {"BUILDX_NO_DEFAULT_ATTESTATIONS": "1"}

_CANCELLED = False


def confirm(question: str, word: str = "co") -> bool:
    """Hỏi xác nhận. Bảng điều khiển web (voya_ui.py) đã hỏi người dùng TRƯỚC khi
    chạy và truyền câu trả lời qua VOYA_CONFIRMED — không có bàn phím nào để hỏi."""
    global _CANCELLED
    given = os.environ.get("VOYA_CONFIRMED")
    if given is None:
        try:
            given = input(f"{question}\n  Go '{word}' de tiep tuc, Enter de huy: ")
        except EOFError:
            given = ""
    ok = given.strip().lower() == word
    if not ok:
        _CANCELLED = True
        print("(da huy)")
    return ok


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def running_images() -> dict:
    """{service: image id} của các container đang có trong project."""
    ids = compose("ps", "-q", capture=True, check=False).stdout.split()
    if not ids:
        return {}
    out = sh(["docker", "inspect", "--format",
              '{{index .Config.Labels "com.docker.compose.service"}} {{.Image}}', *ids],
             capture=True, check=False).stdout
    return dict(line.split(" ", 1) for line in out.splitlines() if " " in line)


def record_deploy(label: str) -> None:
    """Ghi lại image ĐANG chạy sau một lần triển khai thành công. `watch` so với
    bản ghi này để bắt kiểu sự cố 17/10/2026: Docker Desktop tự cập nhật, bật kho
    image khác, và stack lặng lẽ chạy lại mã 4 tuần trước mà vẫn 'healthy'."""
    head = sh(["git", "rev-parse", "--short", "HEAD"], capture=True, check=False).stdout.strip()
    _write_json(DEPLOY_STATE, {"time": datetime.now().isoformat(timespec="seconds"),
                               "label": label, "git": head, "images": running_images()})


def mark_stopped(reason: str) -> None:
    _write_json(STOPPED_FLAG, {"time": datetime.now().isoformat(timespec="seconds"), "reason": reason,
                               "by": os.environ.get("VOYA_ACTOR") or os.environ.get("USERNAME") or "?"})


def clear_stopped() -> None:
    STOPPED_FLAG.unlink(missing_ok=True)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":  # os.kill(pid, 0) trên Windows là TerminateProcess — không dùng
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class deploy_lock:
    """Khoá một-lượt-một-lúc cho triển khai / quay lui. Khoá của tiến trình đã chết
    thì được giành lại (máy tắt giữa chừng không được khoá mãi)."""

    def __enter__(self):
        held = _read_json(DEPLOY_LOCK, {})
        if held and _pid_alive(int(held.get("pid") or 0)):
            raise SystemExit(f"Dang co mot luot '{held.get('what')}' chay tu {held.get('time')} "
                             f"(pid {held.get('pid')}) -> doi no xong.")
        _write_json(DEPLOY_LOCK, {"pid": os.getpid(), "time": datetime.now().isoformat(timespec="seconds"),
                                  "what": " ".join(sys.argv[1:2]) or "?"})
        return self

    def __exit__(self, *exc):
        DEPLOY_LOCK.unlink(missing_ok=True)
        return False


def set_maintenance(on: bool) -> None:
    if on:
        MAINT_FLAG.parent.mkdir(exist_ok=True)
        MAINT_FLAG.write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
    elif MAINT_FLAG.exists():
        MAINT_FLAG.unlink()


def notify(title: str, message: str) -> None:
    """Báo ra màn hình Windows, và email nếu .env có ALERT_EMAIL + SMTP_*."""
    if os.name == "nt":
        ps = ("Add-Type -AssemblyName System.Windows.Forms;"
              "$n=New-Object System.Windows.Forms.NotifyIcon;"
              "$n.Icon=[System.Drawing.SystemIcons]::Warning;$n.Visible=$true;"
              f"$n.ShowBalloonTip(15000,{json.dumps(title)},{json.dumps(message[:250])},'Warning');"
              "Start-Sleep 16;$n.Dispose()")
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    to, host = env_value("ALERT_EMAIL"), env_value("SMTP_HOST")
    if to and host:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = f"[VOYA] {title}", env_value("SMTP_FROM") or env_value("SMTP_USER"), to
        msg.set_content(message)
        try:
            with smtplib.SMTP(host, int(env_value("SMTP_PORT") or 587), timeout=20) as s:
                if (env_value("SMTP_USE_TLS") or "1") not in ("0", "false"):
                    s.starttls()
                if env_value("SMTP_USER"):
                    s.login(env_value("SMTP_USER"), env_value("SMTP_PASSWORD"))
                s.send_message(msg)
        except Exception as exc:  # báo động hỏng không được làm hỏng lượt kiểm
            print(f"  (khong gui duoc email: {type(exc).__name__})")


def bash() -> str:
    for candidate in (shutil.which("bash"), r"C:\Program Files\Git\bin\bash.exe"):
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit("Can Git Bash (bash) de chay script .sh")


def env_value(key: str) -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')
    return ""


def http_status(url: str, timeout=10) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return str(r.status)
    except urllib.error.HTTPError as e:
        return str(e.code)
    except Exception as e:
        return type(e).__name__


def wait_healthy(seconds=600) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if http_status("http://127.0.0.1/api/v1/health", 5) == "200":
            return True
        time.sleep(5)
    return False


#: Lines that look like errors but are not. uvicorn's logger is NAMED "uvicorn.error"
#: and logs "startup complete" at INFO through it — so judge by LEVEL, never by the
#: logger name: the same logger carries real "Exception in ASGI application" errors.
NOT_AN_ERROR = re.compile(r'"level": "(info|debug|warning)"')
IS_ERROR = re.compile(r'"level": "(error|critical)"|Traceback|\bFATAL\b|\bERROR:|level=error|\bPANIC\b',
                      re.IGNORECASE)


def error_lines(text: str) -> list[str]:
    return [l for l in text.splitlines() if IS_ERROR.search(l) and not NOT_AN_ERROR.search(l)]


#: Read-only snapshot of what actually took the site down on 16-17/10/2026: the
#: laptop host sleeping and its phone-hotspot Wi-Fi dropping. Looked like "flaky
#: Docker DNS" until the timestamps were laid next to these Windows events.
HOST_PS = r"""
$r = Get-NetRoute -DestinationPrefix 0.0.0.0/0 -ErrorAction SilentlyContinue | Sort-Object RouteMetric | Select-Object -First 1
$a = if ($r) { Get-NetAdapter -InterfaceIndex $r.ifIndex -ErrorAction SilentlyContinue }
$ssid = if ($a -and $a.MediaType -match '802.11') { ((netsh wlan show interfaces) -match '^\s+SSID\s' | Select-Object -First 1) -replace '^\s+SSID\s+:\s*','' }
$b = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
$since = (Get-Date).AddHours(-24)
$sleep = @(Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Power'; Id=42; StartTime=$since} -ErrorAction SilentlyContinue)
$drop = @(Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-NetworkProfile/Operational'; Id=10001; StartTime=$since} -ErrorAction SilentlyContinue)
[pscustomobject]@{
  interface = if ($a) { $a.Name } else { $null }
  wired = if ($a) { $a.MediaType -notmatch '802.11' } else { $null }
  ssid = $ssid; gateway = if ($r) { $r.NextHop } else { $null }
  battery = if ($b) { [int]$b.BatteryStatus } else { $null }
  boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('s')
  sleeps = $sleep.Count; last_sleep = if ($sleep) { $sleep[0].TimeCreated.ToString('s') } else { $null }
  drops = $drop.Count; last_drop = if ($drop) { $drop[0].TimeCreated.ToString('s') } else { $null }
} | ConvertTo-Json -Compress
"""

#: Phone hotspots hand out these ranges: iPhone 172.20.10.0/28, Android 192.168.43.0/24.
HOTSPOT_GATEWAY = re.compile(r"^(172\.20\.10\.\d+|192\.168\.43\.\d+)$")


def describe_host(info: dict) -> tuple[list[str], list[str]]:
    """(lines, warnings) for the host network/power snapshot. Pure: testable."""
    lines, warn = [], []
    if info.get("interface"):
        kind = "day mang" if info.get("wired") else f"Wi-Fi '{info.get('ssid') or '?'}'"
        lines.append(f"  mang     : {kind} qua {info['interface']}, gateway {info.get('gateway')}")
        if not info.get("wired"):
            warn.append("May chu dang dung Wi-Fi; server nen cam day mang.")
        if HOTSPOT_GATEWAY.match(str(info.get("gateway") or "")):
            warn.append("Gateway la diem phat tu DIEN THOAI: dien thoai khoa/di xa la site mat mang.")
    if info.get("battery") is not None:
        on_battery = info["battery"] == 1
        lines.append(f"  nguon    : laptop, {'DANG CHAY PIN' if on_battery else 'dang cam sac'}")
        if on_battery:
            warn.append("Laptop dang chay pin: het pin hoac tiet kiem pin se lam may ngu.")
    lines.append(f"  bat may  : {info.get('boot')}")
    lines.append(f"  24h qua  : ngu {info.get('sleeps', 0)} lan (gan nhat {info.get('last_sleep') or '-'}), "
                 f"mat mang {info.get('drops', 0)} lan (gan nhat {info.get('last_drop') or '-'})")
    if info.get("sleeps"):
        warn.append("May da NGU trong 24h qua: luc ngu site sap, task/build dung giua chung.")
    return lines, warn


def host_health() -> dict:
    if os.name != "nt":
        return {}
    out = subprocess.run(["powershell", "-NoProfile", "-Command", HOST_PS],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(out.stdout.strip() or "{}")
    except ValueError:
        return {}


# ---------------------------------------------------------------- commands

def cmd_status(_args):
    """Tinh trang: container, trang web, RAM backend, o dia, ban sao luu moi nhat."""
    print("== Container ==")
    out = compose("ps", "-a", "--format", "{{.Service}}\t{{.Status}}", capture=True, check=False).stdout
    bad = []
    for line in sorted(out.splitlines()):
        service, _, state = line.partition("\t")
        ok = "(healthy)" in state or (service == "sot-init" and "Exited (0)" in state)
        bad += [] if ok else [service]
        print(f"  {'OK ' if ok else '!! '} {service:<18} {state}")
    print("== Trang web ==")
    print(f"  may nay  http://127.0.0.1/api/v1/health : {http_status('http://127.0.0.1/api/v1/health')}")
    domain = env_value("FRONTEND_BASE_URL")
    if domain:
        print(f"  domain   {domain} : {http_status(domain, 20)}")
    mem = compose("exec", "-T", "backend", "sh", "-c",
                  "awk '/^anon /{print $2}' /sys/fs/cgroup/memory.stat; cat /sys/fs/cgroup/memory.max",
                  capture=True, check=False).stdout.split()
    if len(mem) == 2 and mem[1].isdigit():
        print(f"== RAM backend: {int(mem[0]) // 2**20} / {int(mem[1]) // 2**20} MiB "
              f"({100 * int(mem[0]) // int(mem[1])}%)")
    print("== O dia ==")
    for drive in sorted({Path(ROOT).anchor, "C:\\", "D:\\"}):
        if Path(drive).exists():
            u = shutil.disk_usage(drive)
            print(f"  {drive:<4} trong {u.free / 2**30:6.1f} GB / {u.total / 2**30:6.1f} GB")
    dumps = sorted((ROOT / "backups").glob("signdb_*.dump"), key=lambda p: p.stat().st_mtime)
    if dumps:
        age = (time.time() - dumps[-1].stat().st_mtime) / 3600
        print(f"== Sao luu DB moi nhat: {dumps[-1].name} ({age:.0f} gio truoc)")
    info = host_health()
    if info:
        lines, warn = describe_host(info)
        print("== May chu: mang & nguon ==")
        print("\n".join(lines))
        for w in warn:
            print(f"  !! {w}")
    if bad:
        print(f"\n!! Container chua on: {', '.join(bad)} -> xem: voya logs")


def cmd_start(_args):
    """Khoi dong stack (va ap dung thay doi trong .env / compose)."""
    clear_stopped()
    compose("up", "-d", "--no-build")
    print("Cho trang san sang...")
    if wait_healthy():
        # Mốc cho canh gác: máy vừa khôi phục chưa có lần triển khai nào để so.
        record_deploy("start")
        print("OK")
    else:
        print("!! Chua thay health 200 sau 10 phut -> voya logs")


def cmd_stop(_args):
    """Dung stack (du lieu va volume con nguyen)."""
    if confirm("Dung toan bo container? Trang web se ngung hoat dong."):
        mark_stopped("voya stop")
        compose("stop", "--timeout", "300")
        print("Da dung. Canh gac se KHONG tu bat lai cho toi khi chay 'voya start'.")


def cmd_restart(_args):
    """Khoi dong lai container (KHONG doc lai .env; doi .env thi dung `start`)."""
    if confirm("Khoi dong lai toan bo container? Trang gian doan 1-2 phut."):
        clear_stopped()
        compose("restart")
        print("OK" if wait_healthy() else "!! Chua thay health 200 -> voya logs")


def cmd_logs(args):
    """Loi that trong log (bo qua bao nham), mac dinh 60 phut qua: voya logs [phut]."""
    minutes = int(args[0]) if args and args[0].isdigit() else 60
    services = compose("ps", "--services", capture=True).stdout.split()
    total = 0
    for s in services:
        text = compose("logs", s, "--since", f"{minutes}m", "--no-log-prefix", capture=True, check=False).stdout
        lines = error_lines(text)
        total += len(lines)
        if lines:
            print(f"== {s}: {len(lines)} dong loi ==")
            for l in lines[-5:]:
                print("   " + l[:220])
    print(f"Tong: {total} dong loi trong {minutes} phut qua." if total else f"Khong co loi trong {minutes} phut qua.")


def cmd_verify(_args):
    """Kiem tra trien khai: schema, phan quyen, du lieu, GPU (verify_deployment)."""
    # Theo TÊN SERVICE: máy khôi phục đặt tên container theo project mới (signbridge-ctu_backend).
    compose("exec", "-T", "backend", "python", "-m", "app.cli.verify_deployment", check=False)


def do_backup(prefix: str = "manual") -> tuple[Path, bool]:
    out = ROOT / "backups" / f"signdb_{prefix}_{datetime.now():%Y%m%d_%H%M%S}.dump"
    out.parent.mkdir(exist_ok=True)
    with out.open("wb") as f:
        dumped = subprocess.run(["docker", "compose", "exec", "-T", "postgres", "sh", "-c",
                                 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'],
                                cwd=ROOT, stdout=f, creationflags=NO_WINDOW).returncode == 0
    with out.open("rb") as f:
        ok = dumped and out.stat().st_size > 0 and subprocess.run(
            ["docker", "compose", "exec", "-T", "postgres", "pg_restore", "-l"],
            cwd=ROOT, stdin=f, capture_output=True, creationflags=NO_WINDOW).returncode == 0
    print(f"{'OK' if ok else '!! HONG'}: {out.relative_to(ROOT)} ({out.stat().st_size / 2**20:.1f} MB)")
    return out, ok


def cmd_backup(_args):
    """Sao luu DB ngay vao backups/ (pg_dump, kiem doc lai duoc)."""
    if not do_backup()[1]:
        raise SystemExit("Sao luu HONG.")


#: Ba image có thể quay lui. Image khác (postgres, nginx, ...) là bản phát hành
#: cố định, không do repo này dựng.
ROLLBACK_REPOS = ("voya_backend", "voya_frontend", "voya_realtime_service")
#: Giữ bao nhiêu mốc quay lui tự động (mỗi mốc chỉ là TAG, không tốn thêm dung lượng
#: cho tới khi image `latest` đổi; image cũ được giữ lại vì còn tag trỏ vào).
KEEP_AUTO_ROLLBACKS = 3


#: Build cache không ai dùng lâu hơn bấy nhiêu thì bỏ. Cache của lần dựng vừa rồi
#: (lớp `npm ci` / pip, ~1,1 GB "private") được GIỮ, nên lần sau vẫn nhanh; cache cũ
#: thì không tích lại. Lưu ý khi đọc `docker system df`: phần lớn con số "Build
#: Cache" (18/10/2026: 4,65/5,78 GB) là "shared" — chung đĩa với lớp của image đang
#: dùng, xoá đi không trả lại chỗ. Trần theo dung lượng (`--max-used-space`) vì thế
#: không bao giờ chạm được và không dọn gì; trần theo thời gian thì có.
BUILD_CACHE_MAX_AGE = os.environ.get("VOYA_BUILD_CACHE_MAX_AGE", "72h")


def tidy_docker_after_build() -> None:
    """Dọn thứ mỗi lần dựng để lại, giữ thứ làm lần sau nhanh.

    * image treo `<none>` — lớp cũ mà tag `latest` vừa bỏ đi; không ai dùng.
    * build cache không ai dùng quá `BUILD_CACHE_MAX_AGE`.
    Không đụng volume (có thể là dữ liệu) và không đụng mốc quay lui (đã có
    `KEEP_AUTO_ROLLBACKS`). Lỗi ở đây không bao giờ làm hỏng lần triển khai.
    """
    def _df() -> dict:
        out = sh(["docker", "system", "df", "--format", "{{.Type}}|{{.Size}}"],
                 capture=True, check=False).stdout
        # Tên loại có dấu cách ("Build Cache", "Local Volumes") — tách theo dòng và
        # `|`, không theo khoảng trắng (bản đầu tách theo khoảng trắng và ném
        # IndexError SAU khi triển khai đã xong, làm lệnh thoát mã 1).
        return dict(line.split("|", 1) for line in out.splitlines() if "|" in line)

    try:
        before = _df()
        sh(["docker", "image", "prune", "-f"], capture=True, check=False)
        sh(["docker", "builder", "prune", "-f", "--filter", f"until={BUILD_CACHE_MAX_AGE}"],
           capture=True, check=False)
        after = _df()
        print("Don sau khi dung: " + "; ".join(
            f"{k}: {before.get(k, '?')} -> {after.get(k, '?')}" for k in ("Images", "Build Cache")))
    except Exception as exc:  # noqa: BLE001 — dọn dẹp không được làm hỏng lần triển khai
        print(f"(bo qua buoc don: {exc})")


def image_tags(repo: str) -> list[str]:
    out = sh(["docker", "image", "ls", repo, "--format", "{{.Tag}}"], capture=True, check=False).stdout
    return [t for t in out.split() if t and t != "<none>"]


def tag_rollback_point() -> str:
    """Gắn tag `rollback-auto-<giờ>` cho image `latest` hiện tại. Trả tên tag."""
    tag = f"rollback-auto-{datetime.now():%Y%m%d-%H%M%S}"
    for repo in ROLLBACK_REPOS:
        if "latest" in image_tags(repo):
            sh(["docker", "tag", f"{repo}:latest", f"{repo}:{tag}"], check=False)
    for repo in ROLLBACK_REPOS:  # dọn mốc tự động cũ
        for old in sorted(t for t in image_tags(repo) if t.startswith("rollback-auto-"))[:-KEEP_AUTO_ROLLBACKS]:
            sh(["docker", "image", "rm", f"{repo}:{old}"], capture=True, check=False)
    return tag


def restore_rollback_point(tag: str) -> None:
    for repo in ROLLBACK_REPOS:
        if tag in image_tags(repo):
            sh(["docker", "tag", f"{repo}:{tag}", f"{repo}:latest"], check=False)
    compose("up", "-d", "--no-build", check=False)


def stale_services() -> list[str]:
    """Service có container KHÔNG chạy đúng image mà tag của nó đang trỏ tới.

    `compose up -d` không tạo lại container khi nó cho rằng cấu hình không đổi;
    hỏi thẳng image ID của container và của tag mới biết chắc mã mới đã chạy."""
    out = compose("ps", "-q", capture=True, check=False).stdout.split()
    if not out:
        return []
    rows = sh(["docker", "inspect", "--format",
               '{{index .Config.Labels "com.docker.compose.service"}} {{.Config.Image}} {{.Image}}', *out],
              capture=True, check=False).stdout.splitlines()
    stale = []
    for row in rows:
        parts = row.split()
        if len(parts) != 3 or not parts[1].split(":")[0] in ROLLBACK_REPOS:
            continue
        service, ref, running = parts
        want = sh(["docker", "image", "inspect", "--format", "{{.Id}}", ref], capture=True, check=False).stdout.strip()
        if want and want != running:
            stale.append(service)
    return sorted(stale)


def problems_after_deploy(wait_seconds: int = 600) -> list[str]:
    """Những gì hỏng sau khi triển khai; rỗng = ổn."""
    stale = stale_services()
    if stale:
        print(f"Container chua chay image moi ({', '.join(stale)}) -> tao lai.")
        compose("up", "-d", "--no-build", "--force-recreate", *stale, check=False)
    problems = [] if wait_healthy(wait_seconds) else ["API khong tra 200 (http://127.0.0.1/api/v1/health)"]
    still = stale_services()
    if still:
        problems.append(f"container van chay image cu: {', '.join(still)}")
    deadline = time.time() + 180   # healthcheck của container cần thêm vài nhịp
    while True:
        bad = unhealthy_services()
        if not bad or time.time() > deadline:
            break
        time.sleep(10)
    return problems + [f"container chua on: {', '.join(bad)}"] * bool(bad)


def unhealthy_services() -> list[str]:
    out = compose("ps", "-a", "--format", "{{.Name}}\t{{.Service}}\t{{.Status}}", capture=True, check=False).stdout
    bad = []
    for line in out.splitlines():
        name, _, rest = line.partition("\t")
        if "-run-" in name:   # `docker compose run` một lần (vd chép Drive): không phải service
            continue
        service, _, state = rest.partition("\t")
        if not ("(healthy)" in state or (service == "sot-init" and "Exited (0)" in state)):
            bad.append(service)
    return sorted(bad)


def build_and_deploy(*, backend: bool, full: bool, frontend: bool, nginx: bool, label: str) -> bool:
    """Dựng → triển khai → kiểm; hỏng thì TỰ QUAY LUI về image vừa chạy.

    Thứ tự là nội dung: mốc quay lui và bản sao lưu có TRƯỚC khi đụng vào gì cả,
    bảo trì bật để người dùng thấy trang 'đang bảo trì' thay vì lỗi 502, và luôn
    tắt ở `finally` — kể cả khi dựng hỏng giữa chừng.
    """
    with deploy_lock():
        return _build_and_deploy(backend=backend, full=full, frontend=frontend, nginx=nginx, label=label)


def _build_and_deploy(*, backend: bool, full: bool, frontend: bool, nginx: bool, label: str) -> bool:
    clear_stopped()
    tag = tag_rollback_point()
    print(f"Moc quay lui: {tag}")
    backup, ok = do_backup("PRE_deploy")
    if not ok:
        raise SystemExit("Khong sao luu duoc DB -> DUNG, chua dung vao gi.")
    set_maintenance(True)
    print("Bat che do bao tri (nguoi dung thay trang 'dang bao tri').")
    try:
        if backend and full:
            compose("build", "backend", env=BUILD_ENV)
        elif backend:
            if BASE_IMAGE not in [f"voya_backend:{t}" for t in image_tags("voya_backend")]:
                sh(["docker", "tag", "voya_backend:latest", BASE_IMAGE])
                print(f"Tao anh nen {BASE_IMAGE} tu voya_backend:latest (lan dau).")
            sh(["docker", "build", "-f", "Dockerfile.coderefresh", "--build-arg", f"BASE={BASE_IMAGE}",
                "-t", "voya_backend:latest", "."], cwd=ROOT / "backend", env=BUILD_ENV)
        if frontend:
            compose("build", "frontend", env=BUILD_ENV)
        compose("up", "-d", "--no-build")
        if nginx:
            compose("exec", "-T", "nginx", "nginx", "-s", "reload", check=False)
        problems = problems_after_deploy()
        if problems:
            print("!! Trien khai HONG: " + "; ".join(problems))
            print(f"Tu quay lui ve {tag} ...")
            restore_rollback_point(tag)
            after = problems_after_deploy(300)
            msg = (f"{label}: hong ({'; '.join(problems)}). Da tu quay lui ve {tag} — "
                   + ("he thong da on lai." if not after else f"VAN CON LOI: {'; '.join(after)}.")
                   + f" Ban sao luu DB truoc khi cap nhat: {backup.name}")
            print(msg)
            notify("Cap nhat that bai, da quay lui", msg)
            return False
        record_deploy(label)
        print(f"OK: {label} — da kiem health va container.")
        tidy_docker_after_build()
        return True
    finally:
        set_maintenance(False)
        print("Tat che do bao tri.")


def cmd_update_code(args):
    """Dua code backend (va frontend neu --frontend) dang co tren may vao chay; --full = build day du."""
    if not confirm("Dung lai he thong voi code hien tai tren may? Gian doan 1-3 phut "
                   "(co sao luu DB truoc, hong thi tu quay lui)."):
        return
    ok = build_and_deploy(backend=True, full="--full" in args, frontend="--frontend" in args,
                          nginx=False, label="update-code")
    if not ok:
        raise SystemExit(1)


def plan_from_changes(changed: list[str]) -> dict:
    """Từ danh sách tệp đổi → cần dựng gì. Pure: testable."""
    full = any(f in ("backend/requirements.txt", "backend/Dockerfile") for f in changed)
    return {
        "backend": full or any(f.startswith("backend/app/") for f in changed),
        "full": full,
        "frontend": any(f.startswith("frontend/") and "/__tests__/" not in f
                        and not f.endswith((".test.ts", ".test.tsx")) for f in changed),
        "nginx": "nginx.conf" in changed,
        # `processed/`, `scripts/`, `config/` được gắn vào container qua /workspace:
        # có hiệu lực ngay khi kéo về, không cần dựng image.
    }


def cmd_update_git(args):
    """Keo code moi tu GitHub, tu chon cach dung, trien khai, kiem; hong thi tu quay lui."""
    dirty = [l for l in sh(["git", "status", "--porcelain", "--untracked-files=no"],
                           capture=True).stdout.splitlines() if l.strip()]
    if dirty and "--force" not in args:
        raise SystemExit(f"Co {len(dirty)} tep da sua ma chua commit tren may nay -> khong keo code de "
                         "khoi ghi de. Commit/stash truoc (hoac them --force neu chac chan).")
    upstream = sh(["git", "rev-parse", "--abbrev-ref", "@{u}"], capture=True, check=False)
    if upstream.returncode != 0:
        branch = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture=True, check=False).stdout.strip()
        raise SystemExit(f"Nhanh '{branch}' chua noi voi nhanh nao tren GitHub -> chay mot lan: "
                         f"git branch --set-upstream-to=origin/{branch}")
    sh(["git", "fetch", "--quiet"])
    incoming = sh(["git", "log", "--oneline", "HEAD..@{u}"], capture=True, check=False).stdout.strip()
    if not incoming:
        print("Code tren may da moi nhat, khong co gi de cap nhat.")
        return
    print("Commit moi se keo ve:\n" + incoming)
    changed = sh(["git", "diff", "--name-only", "HEAD", "@{u}"], capture=True).stdout.split()
    plan = plan_from_changes(changed)
    print("Ke hoach: " + (", ".join(k for k, v in plan.items() if v)
                          or "chi cap nhat tep (khong dung image)"))
    if not confirm("Keo code moi va trien khai? Gian doan 1-3 phut (dung day du thi lau hon)."):
        return
    sh(["git", "pull", "--ff-only"])
    if not any(plan.values()):
        record_deploy("update-git (tep)")
        print("OK: chi cap nhat tep gan vao container, khong can dung image.")
        return
    if not build_and_deploy(label="update-git", **plan):
        raise SystemExit("Image da quay lui; code tren o dia VAN la ban moi -> sua loi roi chay lai.")


def cmd_rollback(args):
    """Quay lui image ve mot moc (mac dinh: moc tu dong gan nhat): voya rollback [tag]."""
    tags = sorted({t for t in image_tags("voya_backend") if t.startswith("rollback")}, reverse=True)
    if not tags:
        raise SystemExit("Khong co moc quay lui nao.")
    tag = args[0] if args else tags[0]
    if tag not in tags:
        raise SystemExit(f"Khong co moc '{tag}'. Co: {', '.join(tags)}")
    print("Cac moc: " + ", ".join(tags))
    if not confirm(f"Quay lui image backend/frontend ve {tag}? DB KHONG bi dong toi.", "quay lui"):
        return
    with deploy_lock():
        clear_stopped()
        restore_rollback_point(tag)
        problems = problems_after_deploy()
    if problems:
        raise SystemExit("!! Sau quay lui van loi: " + "; ".join(problems))
    record_deploy(f"rollback {tag}")
    print(f"OK: dang chay {tag}.")


def cmd_maintenance(args):
    """Trang bao tri cho nguoi dung: voya maintenance on|off (khong co doi so = xem)."""
    what = (args[0] if args else "").lower()
    if what in ("off", "tat") and STOPPED_FLAG.exists():
        print("Luu y: ung dung dang DUNG CO Y (tao goi?) -> tat bao tri thi nguoi dung thay loi 502.")
    if what in ("on", "bat"):
        set_maintenance(True)
        print("Da BAT bao tri: nguoi dung thay trang 'dang bao tri' (API health van tra loi).")
    elif what in ("off", "tat"):
        set_maintenance(False)
        print("Da TAT bao tri.")
    else:
        print("Bao tri: " + ("DANG BAT tu " + MAINT_FLAG.read_text(encoding='utf-8')
                             if MAINT_FLAG.exists() else "tat"))


def cmd_fresh(_args):
    """Code dang chay co phai code moi nhat trong repo khong (chi doc)."""
    sh([PY, "scripts/check_deploy_freshness.py"], check=False)


def cmd_test(args):
    """Chay test backend tren DB test (signdb_test): voya test [tep/test ...]."""
    targets = args or ["backend/tests"]
    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    subprocess.run([bash(), "scripts/run_tests.sh", *targets, "-q", "-p", "no:cacheprovider"], cwd=ROOT, env=env)


def cmd_disk(args):
    """Dung luong Docker; --don = don an toan, --nen = nen o ao (dung stack)."""
    sh(["docker", "system", "df"], check=False)
    if "--don" in args and confirm("Don Docker an toan (docker_gc.sh)?"):
        sh([bash(), "scripts/docker_gc.sh"], check=False)
    if "--nen" in args and confirm("Nen o ao Docker? Phai DUNG stack va bam UAC."):
        sh([bash(), "scripts/docker_gc.sh", "--compact"], check=False)


def _noi_luu(args) -> str:
    return args[0] if args else input("O/thu muc luu goi (vd F:/): ").strip()


def cmd_pack_plan(args):
    """Chuyen server: uoc luong goi (chi doc): voya goi-uoc-luong [F:/]."""
    sh([PY, "scripts/migration_pack.py", "plan", *(args[:1])], check=False)


def cmd_pack_drive(args):
    """Chuyen server: chep Drive truoc (site van chay, chay lai duoc)."""
    sh([PY, "scripts/migration_pack.py", "drive-sync", _noi_luu(args)], check=False)


def cmd_pack_create(args):
    """Chuyen server: tao GOI CUOI + zip (DUNG ghi, giu dung sau khi xong)."""
    where = _noi_luu(args)
    if confirm(f"Tao goi cuoi o {where}? Ung dung se DUNG ghi va GIU dung (bao tri).", "tao goi"):
        mark_stopped(f"tao goi chuyen server o {where}")
        extra = [a for a in args[1:] if a in ("--skip-images", "--skip-drive", "--skip-related")]
        r = sh([PY, "scripts/migration_pack.py", "create", where, "--allow-downtime", "--zip", "--keep-stopped",
                *extra], check=False)
        # Ứng dụng vẫn dừng (dữ liệu sau gói sẽ mất nếu còn ghi). Chỉ bật nginx với
        # trang bảo trì: người vào domain thấy "đang cập nhật" thay vì lỗi 502 của
        # Cloudflare suốt thời gian chuyển máy. nginx không cần backend để khởi động
        # (upstream phân giải theo request).
        set_maintenance(True)
        compose("up", "-d", "--no-deps", "nginx", check=False)
        print("Trang bao tri dang BAT tren may nay (nginx chay, ung dung dung).")
        if r.returncode != 0:
            raise SystemExit("Tao goi THAT BAI -> xem thong bao o tren. Muon chay lai site: voya start")


def cmd_pack_verify(args):
    """Chuyen server: kiem SHA-256 moi tep trong mot goi."""
    pack = args[0] if args else input("Duong dan thu muc goi: ").strip()
    sh([PY, "scripts/migration_pack.py", "verify", pack], check=False)


def cmd_old_off(_args):
    """Chuyen server: tat may cu (tunnel + stack) — mo TAT_MAY_CU.bat voi quyen Admin."""
    bat = ROOT / "scripts" / "chuyen_server" / "TAT_MAY_CU.bat"
    print(f"Mo {bat.name} voi quyen Administrator...")
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Start-Process -FilePath '{bat}' -Verb RunAs"], check=False)


BACKUP_MAX_AGE_HOURS = 26      # pg-backup chạy mỗi 24h
#: Ngưỡng theo DUNG LƯỢNG chứ không theo %: ổ 466 GB còn 8% vẫn là 35 GB, dư sức.
DISK_MIN_FREE_GB = 20
MAINT_MAX_MINUTES = 30


def watch_problems() -> list[str]:
    """Các phép kiểm NHẸ (vài lệnh docker + 1 request + stat tệp) cho lượt canh
    gác 30 phút/lần. Không chạy test, không băm tệp, không gọi verify_deployment."""
    problems = []
    if STOPPED_FLAG.exists():
        return []   # admin cố ý dừng (có thể chỉ còn nginx + trang bảo trì): không báo động
    if not compose("ps", "-q", capture=True, check=False).stdout.split():
        return ["stack dang TAT (khong co container nao chay)"]
    bad = unhealthy_services()
    if bad:
        problems.append(f"container chua on: {', '.join(bad)}")
    if http_status("http://127.0.0.1/api/v1/health", 10) != "200":
        problems.append("API khong tra 200")
    dumps = sorted((ROOT / "backups").glob("signdb_*.dump"), key=lambda p: p.stat().st_mtime)
    age = (time.time() - dumps[-1].stat().st_mtime) / 3600 if dumps else None
    if age is None or age > BACKUP_MAX_AGE_HOURS:
        problems.append("chua co ban sao luu DB nao" if age is None else f"ban sao luu DB moi nhat da {age:.0f} gio")
    for drive in sorted({Path(ROOT).anchor, "D:\\"}):
        if Path(drive).exists():
            u = shutil.disk_usage(drive)
            if u.free / 2**30 < DISK_MIN_FREE_GB:
                problems.append(f"o {drive} chi con {u.free / 2**30:.0f} GB")
    recorded = _read_json(DEPLOY_STATE, {}).get("images") or {}
    if recorded:
        now = running_images()
        drift = sorted(s for s, img in recorded.items() if s in now and now[s] != img)
        if drift:
            problems.append(f"image dang chay KHAC lan trien khai cuoi ({', '.join(drift)}) — "
                            "Docker vua tu cap nhat/doi kho image? Xem 'voya fresh'")
    if MAINT_FLAG.exists() and time.time() - MAINT_FLAG.stat().st_mtime > MAINT_MAX_MINUTES * 60:
        problems.append(f"che do bao tri dang bat qua {MAINT_MAX_MINUTES} phut (voya maintenance off)")
    return problems


def cmd_watch(args):
    """Canh gac (nhe): kiem va bao dong khi CO THAY DOI; --fix = tu bat lai stack neu dang tat."""
    if STOPPED_FLAG.exists():
        held = _read_json(STOPPED_FLAG, {})
        print(f"Stack dang DUNG CO Y tu {held.get('time')} ({held.get('reason')}) -> khong tu bat lai.")
    problems = watch_problems()
    if "--fix" in args and problems and problems[0].startswith("stack dang TAT"):
        print("Stack dang tat -> tu khoi dong lai.")
        compose("up", "-d", "--no-build", check=False)
        wait_healthy(600)
        problems = watch_problems()
    previous = _read_json(WATCH_STATE, {}).get("problems", [])
    _write_json(WATCH_STATE, {"time": datetime.now().isoformat(timespec="seconds"), "problems": problems})
    for p in problems:
        print(f"!! {p}")
    if not problems:
        print("OK: moi thu on.")
    # Chỉ báo khi tình trạng ĐỔI — cùng một lỗi không được báo lại mỗi 30 phút.
    new = [p for p in problems if p not in previous]
    if new:
        notify("Server VOYA co van de", "\n".join(new) + "\nXem bang dieu khien: VOYA_UI.bat")
    elif previous and not problems:
        notify("Server VOYA da on lai", "Cac van de truoc do da het.")


def docker_ready(timeout: int) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if sh(["docker", "info", "--format", "{{.ServerVersion}}"], capture=True, check=False).returncode == 0:
            return True
        time.sleep(10)
    return False


DOCKER_DESKTOP = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "Docker Desktop.exe"


def cmd_boot(_args):
    """Sau khi bat may: doi/mo Docker Desktop, bat stack, kiem (Scheduled Task goi lenh nay)."""
    if not docker_ready(60):
        if DOCKER_DESKTOP.exists():
            print("Docker chua chay -> mo Docker Desktop.")
            subprocess.Popen([str(DOCKER_DESKTOP)], creationflags=NO_WINDOW)
        if not docker_ready(600):
            notify("Server VOYA khong len duoc", "Docker khong chay sau 10 phut ke tu khi bat may.")
            raise SystemExit("Docker khong chay.")
    if STOPPED_FLAG.exists():
        held = _read_json(STOPPED_FLAG, {})
        print(f"Stack da duoc DUNG CO Y ({held.get('reason')}, {held.get('time')}) -> khong tu bat. "
              "Bat lai bang 'voya start'.")
        return
    compose("up", "-d", "--no-build", check=False)
    wait_healthy(900)
    cmd_watch([])


#: Tên tác vụ (thư mục \VOYA\ trong Task Scheduler) -> (lệnh voya, loại trigger).
TASKS = {
    "VOYA\\Khoi dong sau khi bat may": ("boot", "logon"),
    "VOYA\\Canh gac 30 phut": ("watch --fix", "every30"),
}


def _pythonw() -> Path:
    pyw = Path(PY).with_name("pythonw.exe")
    return pyw if pyw.exists() else Path(PY)


def task_script(name: str) -> str:
    """PowerShell tạo MỘT tác vụ cho RIÊNG tài khoản đang đăng nhập.

    Register-ScheduledTask chứ không `schtasks /SC ONLOGON`: dạng sau mặc định áp
    cho MỌI người dùng nên đòi quyền Admin ("Access is denied", đo 17/10/2026).
    Trigger gắn đúng tài khoản này thì không cần Admin — và đó cũng là điều đúng,
    vì Docker Desktop chạy theo phiên của chính người dùng ấy.

    Cho chạy khi dùng pin: mặc định của Task Scheduler là bỏ qua lượt chạy khi
    laptop rút sạc, đúng lúc dễ sập nhất."""
    sub, kind = TASKS[name]
    folder, _, leaf = name.rpartition("\\")
    trigger = ('$t = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\\$env:USERNAME"; $t.Delay = "PT1M"'
               if kind == "logon" else
               '$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) '
               '-RepetitionInterval (New-TimeSpan -Minutes 30)')
    return "; ".join([
        f'$a = New-ScheduledTaskAction -Execute "{_pythonw()}" '
        f'-Argument \'"{ROOT / "scripts" / "voya.py"}" {sub}\' -WorkingDirectory "{ROOT}"',
        trigger,
        '$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries '
        '-StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)',
        f'Register-ScheduledTask -TaskPath "\\{folder}\\" -TaskName "{leaf}" -Action $a -Trigger $t '
        f'-Settings $s -Description "VOYA: voya {sub}" -Force -ErrorAction Stop | Out-Null',
    ])


def _powershell(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", creationflags=NO_WINDOW)


def cmd_autostart(args):
    """Tac vu Windows: tu bat stack sau khi bat may + canh gac 30 phut: voya autostart install|remove."""
    what = (args[0] if args else "").lower()
    if what == "install":
        if not confirm("Tao 2 tac vu Windows (Task Scheduler) cho tai khoan nay: bat stack khi dang nhap, "
                       "canh gac moi 30 phut?"):
            return
        failed = []
        for name in TASKS:
            r = _powershell(task_script(name))
            if r.returncode != 0:
                failed.append(name)
                print(f"  !! {name}: {(r.stderr or r.stdout).strip().splitlines()[-1:]}")
        print("Luu y: tac vu 'khi dang nhap' can Windows TU DANG NHAP sau khi khoi dong lai "
              "(netplwiz), vi Docker Desktop chay theo phien nguoi dung.")
        if failed:
            raise SystemExit(f"Khong tao duoc: {', '.join(failed)}")
    elif what == "remove":
        if confirm("Xoa 2 tac vu VOYA khoi Task Scheduler?"):
            for name in TASKS:
                sh(["schtasks", "/Delete", "/F", "/TN", name], check=False)
    for name in TASKS:
        folder, _, leaf = name.rpartition("\\")
        r = _powershell(f'$t = Get-ScheduledTask -TaskPath "\\{folder}\\" -TaskName "{leaf}" -ErrorAction Stop; '
                        f'$i = $t | Get-ScheduledTaskInfo; '
                        f'"{{0}}|{{1}}|{{2}}|{{3}}" -f $t.State, $i.LastRunTime, $i.LastTaskResult, $i.NextRunTime')
        if r.returncode != 0:
            print(f"  {name}: CHUA CAI")
            continue
        state, last, result, nxt = (r.stdout.strip().split("|") + ["", "", "", ""])[:4]
        ran = "chua chay lan nao" if not last or last.startswith("11/30/1999") else f"lan chay cuoi {last} (ma {result})"
        print(f"  {name}: {state}; {ran}; lan toi {nxt or 'khi dang nhap'}")
    last = _read_json(WATCH_STATE, {})
    if last:
        print(f"  Lan canh gac gan nhat: {last.get('time')} — " + ("; ".join(last.get('problems') or []) or "on"))


#: (key, menu label, function). Order = menu order; groups by the first word.
COMMANDS = [
    ("status", "Hang ngay | Tinh trang he thong", cmd_status),
    ("logs", "Hang ngay | Xem loi gan day", cmd_logs),
    ("start", "Hang ngay | Khoi dong / ap dung .env moi", cmd_start),
    ("restart", "Hang ngay | Khoi dong lai", cmd_restart),
    ("stop", "Hang ngay | Dung", cmd_stop),
    ("backup", "Hang ngay | Sao luu DB ngay", cmd_backup),
    ("watch", "Hang ngay | Canh gac (kiem nhanh, bao dong)", cmd_watch),
    ("verify", "Bao tri | Kiem tra trien khai (verify_deployment)", cmd_verify),
    ("update-git", "Bao tri | Cap nhat code tu GitHub (tu quay lui neu hong)", cmd_update_git),
    ("update-code", "Bao tri | Trien khai code dang co tren may", cmd_update_code),
    ("rollback", "Bao tri | Quay lui image ve moc truoc", cmd_rollback),
    ("maintenance", "Bao tri | Trang bao tri (on/off)", cmd_maintenance),
    ("fresh", "Bao tri | Code dang chay co moi nhat khong", cmd_fresh),
    ("test", "Bao tri | Chay test (DB test)", cmd_test),
    ("disk", "Bao tri | Dung luong Docker / don", cmd_disk),
    ("autostart", "Bao tri | Tu bat sau khi khoi dong + canh gac 30 phut", cmd_autostart),
    ("boot", "Bao tri | Bat stack sau khi bat may (tac vu tu goi)", cmd_boot),
    ("goi-uoc-luong", "Chuyen server | Uoc luong goi", cmd_pack_plan),
    ("goi-drive", "Chuyen server | Chep Drive truoc", cmd_pack_drive),
    ("goi-tao", "Chuyen server | Tao goi cuoi + zip", cmd_pack_create),
    ("goi-kiem", "Chuyen server | Kiem goi", cmd_pack_verify),
    ("tat-may-cu", "Chuyen server | Tat may cu (tunnel + stack)", cmd_old_off),
]


#: Mức rủi ro cho bảng điều khiển web: "safe" chạy ngay, "confirm" hỏi lại,
#: "danger" bắt GÕ chữ xác nhận. Lệnh không có ở đây là "safe".
RISK = {
    "start": "confirm", "restart": "confirm", "backup": "confirm", "update-code": "confirm",
    "update-git": "confirm", "maintenance": "confirm", "disk": "confirm", "autostart": "confirm",
    "boot": "confirm", "goi-drive": "confirm", "test": "confirm",
    "stop": "danger", "rollback": "danger", "goi-tao": "danger", "tat-may-cu": "danger",
}
#: Chữ phải gõ cho `confirm()` của từng lệnh (mặc định "co").
CONFIRM_WORD = {"rollback": "quay lui", "goi-tao": "tao goi"}
#: Gợi ý đối số cho ô nhập của bảng điều khiển (lệnh không có ở đây không nhận đối số).
ARGS_HINT = {
    "logs": "so phut, vd 60", "update-code": "--full | --frontend", "update-git": "--force",
    "rollback": "ten moc (bo trong = moc gan nhat)", "maintenance": "on | off",
    "test": "tep test, vd backend/tests/test_x.py", "disk": "--don | --nen",
    "autostart": "install | remove", "watch": "--fix",
    "goi-uoc-luong": "o luu, vd F:/", "goi-drive": "o luu, vd F:/",
    "goi-tao": "o luu [--skip-images --skip-drive --skip-related]",
    "goi-kiem": "thu muc goi",
}
#: Lệnh cần đối số khi chạy không có bàn phím (bảng điều khiển, tác vụ nền).
ARGS_REQUIRED = {"goi-drive", "goi-tao", "goi-kiem"}
#: Chỉ những thao tác ĐỔI trạng thái hệ thống mới vào nhật ký — không ghi
#: status/logs/fresh để nhật ký còn đọc được.
IMPORTANT = {"start", "stop", "restart", "backup", "update-code", "update-git", "rollback",
             "maintenance", "disk", "autostart", "goi-tao", "tat-may-cu"}


def log_action(key: str, args: list, result: str, seconds: float) -> None:
    if key not in IMPORTANT or (key in ("maintenance", "autostart", "disk") and not args):
        return
    STATE_DIR.mkdir(exist_ok=True)
    entry = {"time": datetime.now().isoformat(timespec="seconds"), "command": key, "args": args,
             "result": result, "seconds": round(seconds),
             "by": os.environ.get("VOYA_ACTOR") or os.environ.get("USERNAME") or os.environ.get("USER") or "?"}
    with ACTIONS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def show_help():
    print(__doc__.split("\n\n")[0])
    group = None
    for key, label, fn in COMMANDS:
        g, _, _ = label.partition(" | ")
        if g != group:
            print(f"\n{g}:")
            group = g
        print(f"  voya {key:<14} {fn.__doc__.strip().splitlines()[0]}")


def menu():
    while True:
        print("\n=========== VOYA ===========")
        group = None
        for i, (_, label, _) in enumerate(COMMANDS, 1):
            g, _, name = label.partition(" | ")
            if g != group:
                print(f"-- {g} --")
                group = g
            print(f"  {i:>2}. {name}")
        print("   0. Thoat")
        choice = input("Chon so: ").strip()
        if choice in ("0", "", "q"):
            return
        if choice.isdigit() and 1 <= int(choice) <= len(COMMANDS):
            try:
                main([COMMANDS[int(choice) - 1][0]])   # qua main(): có nhật ký thao tác
            except SystemExit as exc:
                print(exc)
            except KeyboardInterrupt:
                print("\n(huy)")
            input("\nEnter de quay lai menu...")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return menu()
    if argv[0] in ("help", "-h", "--help"):
        return show_help()
    table = {key: fn for key, _, fn in COMMANDS}
    if argv[0] not in table:
        show_help()
        raise SystemExit(f"\nKhong co lenh '{argv[0]}'.")
    global _CANCELLED
    _CANCELLED = False
    key, rest, started, result = argv[0], argv[1:], time.time(), "ok"
    try:
        return table[key](rest)
    except SystemExit as exc:
        result = "ok" if exc.code in (None, 0) else "loi"
        raise
    except BaseException:
        result = "loi"
        raise
    finally:
        log_action(key, rest, "huy" if _CANCELLED else result, time.time() - started)


if __name__ == "__main__":
    if sys.stdout is None:  # pythonw (tác vụ nền): không có console -> ghi ra tệp
        STATE_DIR.mkdir(exist_ok=True)
        task_log = STATE_DIR / "task.log"
        if task_log.exists() and task_log.stat().st_size > 2 * 2**20:   # ~2 MB thì xoay vòng
            os.replace(task_log, task_log.with_suffix(".log.1"))
        sys.stdout = sys.stderr = open(task_log, "a", encoding="utf-8", buffering=1)
        print(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} voya {' '.join(sys.argv[1:])}")
    main()
