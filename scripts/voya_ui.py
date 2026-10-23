"""Bảng điều khiển máy chủ VOYA — giao diện web CỤC BỘ cho các lệnh vận hành.

Bấm đúp VOYA_UI.bat (hoặc: python scripts/voya_ui.py). Trình duyệt mở
http://127.0.0.1:8765/?t=<token>.

Vì sao là một server riêng trên máy, KHÔNG phải một trang trong web app
-----------------------------------------------------------------------
Các lệnh này chạm vào máy chủ: docker compose, tệp sao lưu trên ổ, Task
Scheduler. Muốn web app làm được thì backend phải cầm Docker socket — tức quyền
root trên máy — trong khi web app mở ra internet qua domain. Ở đây:

* chỉ nghe 127.0.0.1 (tunnel Cloudflare chỉ trỏ cổng 80, không tới cổng này);
* mọi request /api cần token ngẫu nhiên sinh mỗi lần mở (header X-VOYA-Token);
* kiểm `Host` để một trang web lạ không gọi vào được qua DNS rebinding;
* POST chỉ nhận JSON — form HTML của trang lạ không gửi được;
* KHÔNG có logic vận hành nào ở đây: mọi nút chạy `python scripts/voya.py <lệnh>`,
  nên VOYA.bat và giao diện không bao giờ làm hai việc khác nhau.
"""
from __future__ import annotations

import json
import os
import secrets
import shlex
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import voya  # noqa: E402

HERE = Path(__file__).resolve().parent
PAGE = HERE / "voya_ui.html"
VOYA = HERE / "voya.py"
#: Sổ tay Dev và tài liệu nó trỏ tới. Chỉ đọc, không cần token: trong docs/ không có
#: bí mật, và đường /docs/ không chạy được lệnh nào. Ngoài docs/ thì không phục vụ gì.
DOCS = voya.ROOT / "docs"
GUIDE = "/docs/HUONG_DAN_DEV.html"
DOC_TYPES = {".html": "text/html; charset=utf-8", ".md": "text/plain; charset=utf-8",
             ".png": "image/png", ".svg": "image/svg+xml"}

#: Tên và mô tả có dấu cho giao diện. Lệnh mới chưa có ở đây vẫn hiện (dùng nhãn
#: không dấu của voya.py) — bảng này chỉ là trình bày.
VI = {
    "status": ("Tình trạng hệ thống", "Container, trang web, RAM, ổ đĩa, sao lưu, mạng và nguồn"),
    "logs": ("Xem lỗi gần đây", "Chỉ dòng lỗi thật trong log, mặc định 60 phút"),
    "watch": ("Canh gác ngay", "Kiểm nhanh như tác vụ 30 phút, báo động nếu có thay đổi"),
    "start": ("Khởi động / áp dụng .env", "Bật stack và đọc lại .env, compose"),
    "restart": ("Khởi động lại", "Gián đoạn 1–2 phút, không đọc lại .env"),
    "stop": ("Dừng toàn bộ", "Trang web ngừng hoạt động, dữ liệu còn nguyên"),
    "backup": ("Sao lưu DB ngay", "pg_dump vào backups/ và kiểm đọc lại được"),
    "verify": ("Kiểm tra triển khai", "Schema, phân quyền, dữ liệu, GPU"),
    "update-git": ("Cập nhật từ GitHub", "Kéo code, tự chọn cách dựng, kiểm, hỏng thì tự quay lui"),
    "update-code": ("Triển khai code trên máy", "Code đang có ở thư mục repo; hỏng thì tự quay lui"),
    "rollback": ("Quay lui image", "Về mốc trước (DB không bị động tới)"),
    "maintenance": ("Trang bảo trì", "Bật/tắt trang 'đang bảo trì' cho người dùng"),
    "fresh": ("Code đang chạy có mới nhất?", "So image và container với mã nguồn"),
    "test": ("Chạy test backend", "Trên DB test riêng, không đụng dữ liệu thật"),
    "disk": ("Dung lượng Docker", "Xem; --don dọn an toàn; --nen nén ổ ảo (dừng stack)"),
    "autostart": ("Tự bật sau khởi động + canh gác", "Tạo/xoá tác vụ Windows; bỏ trống = xem"),
    "boot": ("Bật stack như sau khi khởi động", "Đợi/mở Docker Desktop, bật stack, kiểm"),
    "goi-uoc-luong": ("Ước lượng gói chuyển server", "Chỉ đọc"),
    "goi-drive": ("Chép Drive trước", "Site vẫn chạy, chạy lại được"),
    "goi-tao": ("Tạo gói cuối + zip", "DỪNG ghi và giữ dừng sau khi xong"),
    "goi-kiem": ("Kiểm gói", "SHA-256 mọi tệp trong gói"),
    "tat-may-cu": ("Tắt máy cũ", "Tắt tunnel + stack (mở cửa sổ quyền Admin)"),
}
GROUP_VI = {"Hang ngay": "Hằng ngày", "Bao tri": "Bảo trì", "Chuyen server": "Chuyển server"}


class Job:
    """Một lệnh tại một thời điểm — hai lượt triển khai chồng nhau là cách hỏng nhanh nhất."""

    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.key = None
        self.lines: list[str] = []
        self.exit = None
        self.started = None

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, key: str, args: list[str], confirmed: str | None) -> None:
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
                   VOYA_ACTOR=f"ui:{os.environ.get('USERNAME', '?')}")
        # Lệnh "an toàn" không được âm thầm vượt một câu hỏi xác nhận bên trong:
        # chuỗi rỗng làm mọi confirm() trả về "không".
        env["VOYA_CONFIRMED"] = confirmed if confirmed is not None else ""
        self.proc = subprocess.Popen(
            [sys.executable, str(VOYA), key, *args], cwd=voya.ROOT, env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.key, self.lines, self.exit, self.started = key, [f"$ voya {key} {' '.join(args)}".rstrip()], None, time.time()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            with self.lock:
                self.lines.append(line.rstrip("\n"))
                del self.lines[:-5000]
        self.exit = self.proc.wait()
        with self.lock:
            self.lines.append(f"[xong, ma thoat {self.exit}, {time.time() - self.started:.0f} giay]")

    def cancel(self):
        if self.running():
            if os.name == "nt":
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.proc.pid)], capture_output=True)
            else:
                self.proc.terminate()


def commands_meta() -> list[dict]:
    out = []
    for key, label, fn in voya.COMMANDS:
        group, _, name = label.partition(" | ")
        title, desc = VI.get(key, (name, (fn.__doc__ or "").strip().splitlines()[0]))
        risk = voya.RISK.get(key, "safe")
        out.append({"key": key, "group": GROUP_VI.get(group, group), "title": title, "desc": desc,
                    "risk": risk, "word": voya.CONFIRM_WORD.get(key, "co"),
                    "hint": voya.ARGS_HINT.get(key, ""), "args_required": key in voya.ARGS_REQUIRED})
    return out


def validate_run(body: dict) -> tuple[str, list[str], str | None]:
    """(key, args, confirmed) hoặc ValueError. Pure: testable."""
    key = str(body.get("key") or "")
    meta = {m["key"]: m for m in commands_meta()}
    if key not in meta:
        raise ValueError(f"không có lệnh '{key}'")
    m = meta[key]
    raw = str(body.get("args") or "").strip()
    if raw and not m["hint"]:
        raise ValueError("lệnh này không nhận đối số")
    args = shlex.split(raw, posix=False) if raw else []
    if m["args_required"] and not args:
        raise ValueError(f"cần đối số: {m['hint']}")
    confirmed = None
    if m["risk"] != "safe":
        confirmed = str(body.get("confirm") or "").strip().lower()
        if confirmed != m["word"]:
            raise ValueError(f"chưa xác nhận (phải gõ '{m['word']}')")
    return key, args, confirmed


def doc_file(url_path: str) -> Path | None:
    """Tệp dưới docs/ cho đường `/docs/...`, hoặc None. Pure: testable.

    Chặn `..` và đường vòng qua liên kết bằng cách so đường đã resolve với DOCS.
    """
    if not url_path.startswith("/docs/"):
        return None
    target = (DOCS / unquote(url_path[len("/docs/"):])).resolve()
    try:
        target.relative_to(DOCS.resolve())
    except ValueError:
        return None
    if target.suffix.lower() not in DOC_TYPES or not target.is_file():
        return None
    return target


_status_cache: dict = {"at": 0.0, "data": None}


def quick_status() -> dict:
    """Ảnh chụp nhẹ cho thanh trên cùng; cache 20 giây để nhiều tab không dội lệnh docker."""
    if time.time() - _status_cache["at"] < 20 and _status_cache["data"]:
        return _status_cache["data"]
    out = voya.compose("ps", "-a", "--format", "{{.Service}}\t{{.Status}}", capture=True, check=False).stdout
    services = [l for l in out.splitlines() if l.strip()]
    bad = voya.unhealthy_services() if services else []
    dumps = sorted((voya.ROOT / "backups").glob("signdb_*.dump"), key=lambda p: p.stat().st_mtime)
    git = voya.sh(["git", "status", "--porcelain", "--untracked-files=no"], capture=True, check=False).stdout
    branch = voya.sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture=True, check=False).stdout.strip()
    data = {
        "containers_total": len(services), "containers_bad": bad,
        "health": voya.http_status("http://127.0.0.1/api/v1/health", 5),
        "backup_hours": round((time.time() - dumps[-1].stat().st_mtime) / 3600, 1) if dumps else None,
        "disk": [{"drive": d, "free_gb": round(voya.shutil.disk_usage(d).free / 2**30),
                  "free_pct": round(100 * voya.shutil.disk_usage(d).free / voya.shutil.disk_usage(d).total)}
                 for d in sorted({Path(voya.ROOT).anchor, "D:\\"}) if Path(d).exists()],
        "maintenance": voya.MAINT_FLAG.exists(),
        "stopped": voya._read_json(voya.STOPPED_FLAG, {}),
        "deploy_running": voya._read_json(voya.DEPLOY_LOCK, {}),
        "last_deploy": voya._read_json(voya.DEPLOY_STATE, {}),
        "last_watch": voya._read_json(voya.WATCH_STATE, {}),
        "git": {"branch": branch, "modified": len([l for l in git.splitlines() if l.strip()])},
    }
    _status_cache.update(at=time.time(), data=data)
    return data


def recent_actions(limit: int = 50) -> list[dict]:
    try:
        lines = voya.ACTIONS_LOG.read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def make_handler(token: str, port: int, job: Job):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # yên lặng; nhật ký thao tác nằm ở .voya/actions.jsonl
            pass

        def _send(self, code: int, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _guard(self, api: bool) -> bool:
            if self.headers.get("Host", "") not in allowed_hosts:
                self._send(403, {"error": "host"})
                return False
            if api and not secrets.compare_digest(self.headers.get("X-VOYA-Token", ""), token):
                self._send(403, {"error": "token"})
                return False
            return True

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/":
                if not self._guard(False):
                    return
                if not secrets.compare_digest((parse_qs(url.query).get("t") or [""])[0], token):
                    return self._send(403, "Mo bang VOYA_UI.bat (link co token).".encode(), "text/plain; charset=utf-8")
                html = PAGE.read_text(encoding="utf-8").replace("__VOYA_TOKEN__", token)
                return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if url.path in ("/huong-dan", "/docs", "/docs/"):
                if not self._guard(False):
                    return
                self.send_response(302)
                self.send_header("Location", GUIDE)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if url.path.startswith("/docs/"):
                if not self._guard(False):
                    return
                path = doc_file(url.path)
                if path is None:
                    return self._send(404, {"error": "not found"})
                return self._send(200, path.read_bytes(), DOC_TYPES[path.suffix.lower()])
            if not self._guard(True):
                return
            if url.path == "/api/meta":
                return self._send(200, {"commands": commands_meta()})
            if url.path == "/api/status":
                return self._send(200, quick_status())
            if url.path == "/api/actions":
                return self._send(200, {"actions": recent_actions()})
            if url.path == "/api/job":
                since = int((parse_qs(url.query).get("since") or ["0"])[0] or 0)
                with job.lock:
                    lines = job.lines[since:]
                    total = len(job.lines)
                return self._send(200, {"key": job.key, "running": job.running(), "exit": job.exit,
                                        "lines": lines, "total": total})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._guard(True):
                return
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return self._send(415, {"error": "json only"})
            length = min(int(self.headers.get("Content-Length") or 0), 10_000)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._send(400, {"error": "bad json"})
            path = urlparse(self.path).path
            if path == "/api/run":
                if job.running():
                    return self._send(409, {"error": f"đang chạy '{job.key}', đợi xong đã"})
                try:
                    key, args, confirmed = validate_run(body)
                except ValueError as exc:
                    return self._send(400, {"error": str(exc)})
                job.start(key, args, confirmed)
                _status_cache["at"] = 0
                return self._send(202, {"ok": True})
            if path == "/api/cancel":
                job.cancel()
                return self._send(200, {"ok": True})
            self._send(404, {"error": "not found"})

    return Handler


def main():
    token = secrets.token_urlsafe(24)
    job = Job()
    for port in range(8765, 8775):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(token, port, job))
            break
        except OSError:
            continue
    else:
        raise SystemExit("Khong mo duoc cong 8765-8774.")
    url = f"http://127.0.0.1:{port}/?t={token}"
    print(f"Bang dieu khien VOYA: {url}\n(Dong cua so nay de tat bang dieu khien.)", flush=True)
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
