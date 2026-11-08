"""Bộ chạy kiểm thử cho bảng điều khiển VOYA. Gọi từ `voya.py`.

Một lượt chạy HẾT, theo thứ tự, rồi dọn và kiểm lại là đã dọn:

    backend  ->  Drive thật (sandbox)  ->  frontend, kiểm kiểu, i18n, dựng thử
             ->  trình duyệt thật + đo nhận dạng  ->  dọn  ->  báo cáo

Báo cáo nằm ở `reports/kiem-thu/`, dựng từ tệp máy do pytest, vitest, playwright sinh
ra. Lượt không chạy được ca nào, hoặc dọn còn sót, là KHÔNG ĐẠT.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

for _luong in (sys.stdout, sys.stderr):  # tiếng Việt trên console cp1252
    _luong.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kiem_thu_bao_cao as bao_cao  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ENV_DIR = ROOT / "scripts" / "kiem_thu_env"
OUT = ROOT / "reports" / "kiem-thu"
TAM = ROOT / "_tmp" / "kiem-thu"
IMAGE = "voya_backend_test:latest"
NHAN = "voya.kiem-thu=1"
NETWORK = "voya-collector_voya_network"
CSDL_E2E = "signdb_pytest_e2e"
#: Drive chỉ chờ mạng, nên chạy song song với backend, trên CSDL riêng để không đụng nhau.
CSDL_DRIVE = "signdb_pytest_drive"
CONG_E2E = 18080
GIU_LAI_LUOT = 10
REDIS_TEST = "13"
PY_ENV = "/src/scripts/kiem_thu_env"
#: Tệp thật phải y nguyên sau lượt test.
TEP_THAT = ("dataset/labels.csv", "dataset/samples.csv", "backend/realtime_service/config/models.json")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _bash() -> str:
    for c in (r"C:\Program Files\Git\bin\bash.exe", shutil.which("bash")):
        if c and Path(c).exists():
            return c
    raise SystemExit("Can Git Bash de chay kiem thu.")


def _npx() -> str:
    return shutil.which("npx.cmd") or shutil.which("npx") or "npx"


def _npm() -> str:
    return shutil.which("npm.cmd") or shutil.which("npm") or "npm"


def run(args, *, cwd=ROOT, env=None, capture=False, check=False):
    r = subprocess.run([str(a) for a in args], cwd=cwd, env=dict(os.environ, **(env or {})),
                       text=True, encoding="utf-8", errors="replace", capture_output=capture,
                       stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
    if check and r.returncode != 0:
        raise SystemExit(f"Lenh that bai ({r.returncode}): {' '.join(map(str, args))}\n{r.stderr or ''}")
    return r


def chay_va_ghi(args, tep_log: Path, *, cwd=ROOT, env=None, in_ra=True) -> int:
    """Chạy, vừa in ra vừa ghi tệp: bảng điều khiển thấy tiến độ, báo cáo đọc được sau."""
    with tep_log.open("w", encoding="utf-8") as log:
        p = subprocess.Popen([str(a) for a in args], cwd=cwd, env=dict(os.environ, **(env or {})), text=True,
                             encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        for dong in p.stdout:
            log.write(dong)
            if in_ra:
                print(dong, end="", flush=True)
        return p.wait()


def tieu_de(s: str) -> None:
    print(f"\n=== {s} ===", flush=True)


def _docker_ps(loc: str) -> list[str]:
    return run(["docker", "ps", "-aq", "--filter", loc], capture=True).stdout.split()


# --------------------------------------------------------------- điều kiện

def kiem_dieu_kien() -> None:
    """Báo thiếu gì bằng lời, thay vì để hàng trăm lỗi kết nối trông như hồi quy."""
    dang_chay = run(["docker", "ps", "--format", "{{.Names}}"], capture=True)
    if dang_chay.returncode != 0:
        raise SystemExit("Docker chua chay. Mo Docker Desktop roi bam lai.")
    thieu = {"voya_postgres", "voya_redis"} - set(dang_chay.stdout.split())
    if thieu:
        raise SystemExit(f"Thieu container {sorted(thieu)}. Bam 'Khoi dong' truoc.")
    con_chay = _docker_ps(f"ancestor={IMAGE}")
    for cid in con_chay:  # lượt trước bị dừng ngang: dừng sạch để pytest kịp dọn
        print("Dung luot kiem thu cu con sot...", flush=True)
        run(["docker", "kill", "--signal=INT", cid], capture=True)
    # Hai lượt chung một CSDL thì kết quả không tin được, nên phải CHỜ nó dừng hẳn.
    for _ in range(30):
        if not _docker_ps(f"ancestor={IMAGE}"):
            break
        time.sleep(1)
    else:
        for cid in con_chay:
            run(["docker", "rm", "-f", cid], capture=True)
    for cid in _docker_ps(f"label={NHAN}"):
        run(["docker", "rm", "-f", cid], capture=True)


def dam_bao_anh() -> None:
    """Ảnh test phải có pytest-html và đúng bản edge-tts của requirements.txt."""
    ban = re.search(r"^edge-tts==(\S+)", (ROOT / "backend/requirements.txt").read_text(encoding="utf-8"), re.M).group(1)
    co = run(["docker", "run", "--rm", "--entrypoint", "sh", IMAGE, "-c",
              "python -c 'import pytest_html' && test -d /workspace && pip show edge-tts | grep -q 'Version: " + ban + "'"],
             capture=True)
    if co.returncode == 0:
        return
    tieu_de("Dung lai anh test (chi khi phu thuoc doi)")
    run(["docker", "build", "-q", "-f", "backend/Dockerfile.test", "-t", IMAGE, "backend"], check=True)


# --------------------------------------------------------------- các bước

def buoc(ten: str, cong_cu: str, fn) -> dict:
    tieu_de(ten)
    bat_dau = time.time()
    ket_qua = fn()
    ket_qua.update(ten=ten, cong_cu=cong_cu, giay=round(time.time() - bat_dau, 1))
    print(f"--> {ten}: ma thoat {ket_qua['ma_thoat']} sau {ket_qua['giay']} giay", flush=True)
    return ket_qua


def _dem_pytest(tep: Path) -> dict:
    dem = {"dat": 0, "do": 0, "bo_qua": 0}
    if tep.exists():
        for d in tep.read_text(encoding="utf-8").splitlines():
            gd = json.loads(d).get("giai_doan", {}).values()
            dem["do" if "failed" in gd else "bo_qua" if "skipped" in gd else "dat"] += 1
    return dem


def _lenh_pytest(rel: str, ten_tep: str, them: str = "") -> str:
    return (f"env PYTHONPATH={PY_ENV}:/src:/src/backend KT_KET_QUA=/src/{rel}/{ten_tep} {them} "
            "python -m pytest -p ghi_ket_qua -o enable_assertion_pass_hook=true")


def chay_backend(thu_muc: Path) -> dict:
    rel = thu_muc.relative_to(ROOT).as_posix()
    ma = chay_va_ghi(
        [_bash(), "scripts/run_tests.sh", "backend/tests", "--ignore=backend/tests/test_sot_integration.py",
         "-q", "-p", "no:cacheprovider", "--timeout=300"],
        thu_muc / "backend.log",
        env={"VOYA_TEST_CMD": _lenh_pytest(rel, "backend-ket-qua.jsonl"), "MSYS_NO_PATHCONV": "1"})
    return {"ma_thoat": ma, **_dem_pytest(thu_muc / "backend-ket-qua.jsonl")}


def _drive_lenh(args: list[str], thu_muc: Path, ten_log: str) -> str:
    """Chạy `drive_sandbox.py` với bản sao thông tin đăng nhập."""
    rel_tam = TAM.relative_to(ROOT).as_posix()
    cmd = (f"env PYTHONPATH=/src/backend GOOGLE_DRIVE_CREDENTIALS=/src/{rel_tam}/gdrive/credentials.json "
           f"GOOGLE_DRIVE_TOKEN=/src/{rel_tam}/gdrive/token.json python {PY_ENV}/drive_sandbox.py")
    r = run([_bash(), "scripts/run_tests.sh", *args], capture=True,
            env={"VOYA_TEST_CMD": cmd, "MSYS_NO_PATHCONV": "1"})
    (thu_muc / ten_log).write_text((r.stdout or "") + (r.stderr or ""), encoding="utf-8")
    return r.stdout or ""


def chay_drive(thu_muc: Path, sandbox: str) -> dict:
    """13 ca SOT cần Drive thật, trong một thư mục sandbox tạo riêng cho lượt này."""
    goc = ROOT / "gdrive"
    if not (goc / "credentials.json").exists():
        print("Khong co gdrive/credentials.json tren may nay.", flush=True)
        return {"ma_thoat": 1, "dat": 0, "do": 0, "bo_qua": 0}
    (TAM / "gdrive").mkdir(parents=True, exist_ok=True)
    for ten in ("credentials.json", "token.json"):
        shutil.copyfile(goc / ten, TAM / "gdrive" / ten)
    m = re.search(r"SANDBOX_ID=(\S+)", _drive_lenh(["tao", sandbox], thu_muc, "drive-tao.log"))
    if not m:
        print("Khong tao duoc thu muc sandbox tren Drive.", flush=True)
        return {"ma_thoat": 1, "dat": 0, "do": 0, "bo_qua": 0}
    rel = thu_muc.relative_to(ROOT).as_posix()
    rel_tam = TAM.relative_to(ROOT).as_posix()
    them = (f"VOYA_TEST_DRIVE_THAT=1 GOOGLE_DRIVE_ROOT_FOLDER_ID={m.group(1)} "
            f"GOOGLE_DRIVE_CREDENTIALS=/src/{rel_tam}/gdrive/credentials.json "
            f"GOOGLE_DRIVE_TOKEN=/src/{rel_tam}/gdrive/token.json")
    ma = chay_va_ghi(
        [_bash(), "scripts/run_tests.sh", "backend/tests/test_sot_integration.py",
         "-q", "-p", "no:cacheprovider", "--timeout=300"],
        thu_muc / "drive.log", in_ra=False,
        env={"VOYA_TEST_CMD": _lenh_pytest(rel, "drive-ket-qua.jsonl", them), "MSYS_NO_PATHCONV": "1",
             "VOYA_TEST_DATABASE": CSDL_DRIVE})
    return {"ma_thoat": ma, **_dem_pytest(thu_muc / "drive-ket-qua.jsonl")}


def chay_vitest(thu_muc: Path) -> dict:
    json_out = thu_muc / "frontend.json"
    ma = chay_va_ghi(
        [_npx(), "vitest", "run", "--reporter=default", "--reporter=json", f"--outputFile.json={json_out}"],
        thu_muc / "frontend.log", cwd=ROOT / "frontend", env={"KT_KET_QUA": str(thu_muc / "frontend-ket-qua.jsonl")})
    ket = {"dat": 0, "do": 0, "bo_qua": 0}
    if json_out.exists():
        d = json.loads(json_out.read_text(encoding="utf-8"))
        ket = {"dat": d.get("numPassedTests", 0), "do": d.get("numFailedTests", 0), "bo_qua": d.get("numPendingTests", 0)}
    return {"ma_thoat": ma, **ket}


def chay_lenh(lenh, cwd, tep_log: Path) -> dict:
    return {"ma_thoat": chay_va_ghi(lenh, tep_log, cwd=cwd), "dat": 0, "do": 0, "bo_qua": 0}


# --------------------------------------------------------------- trình duyệt

def _psql(sql: str) -> str:
    return run(["docker", "exec", "voya_postgres", "sh", "-c", f'psql -qAt -U "$POSTGRES_USER" -d postgres -c "{sql}"'],
               check=True, capture=True).stdout


def _xoa_csdl(ten: str) -> None:
    _psql(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{ten}'")
    _psql(f"DROP DATABASE IF EXISTS {ten}")


def _tao_csdl_tu_test(ten: str) -> None:
    _xoa_csdl(ten)
    _psql("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='signdb_test'")
    _psql(f"CREATE DATABASE {ten} WITH TEMPLATE signdb_test")


def _ten_container(cid: str) -> str:
    return run(["docker", "inspect", "-f", "{{.Name}}", cid], capture=True, check=True).stdout.strip().lstrip("/")


def _redis_test(*lenh: str) -> str:
    return run(["docker", "exec", "voya_redis", "redis-cli", "-n", REDIS_TEST, *lenh], capture=True).stdout.strip()


def _chay_realtime_that() -> str:
    """Dịch vụ realtime THẬT, cùng mount với docker-compose.yml, trên bản sao cấu hình."""
    ban_sao = TAM / "realtime_service"
    shutil.rmtree(ban_sao, ignore_errors=True)
    shutil.copytree(ROOT / "backend" / "realtime_service", ban_sao, ignore=shutil.ignore_patterns("__pycache__"))
    p = ROOT / "processed"
    cid = run(["docker", "run", "-d", "--rm", "--label", NHAN, "--network", NETWORK,
               "-e", "NORMALIZATION_PY_PATH=/app/processed/shared/normalization.py",
               "-v", f"{ban_sao}:/app/realtime_service",
               "-v", f"{p / 'shared'}:/app/processed/shared:ro",
               "-v", f"{p / 'analysis'}:/app/processed/analysis:ro",
               "-v", f"{p / 'train_utils' / 'models'}:/app/processed/train_utils/models:ro",
               "voya_realtime_service:latest"],
              capture=True, check=True, env={"MSYS_NO_PATHCONV": "1"}).stdout.strip()
    kiem = "import urllib.request as u; u.urlopen('http://127.0.0.1:8010/health', timeout=2)"
    for _ in range(90):
        if run(["docker", "exec", cid, "python", "-c", kiem], capture=True).returncode == 0:
            return _ten_container(cid)
        time.sleep(1)
    raise SystemExit("Dich vu realtime khong len.")


def _do_nhan_dang(thu_muc: Path, realtime: str) -> None:
    print("Do nhan dang bang mau that...", flush=True)
    r = run(["docker", "run", "--rm", "--network", NETWORK, "--label", NHAN, "--entrypoint", "python",
             "-e", f"REALTIME_URL=http://{realtime}:8010",
             "-v", f"{ROOT / 'dataset'}:/dataset:ro",
             "-v", f"{ROOT / 'processed' / 'splits'}:/splits:ro",
             "-v", f"{ENV_DIR}:/kt:ro", "-v", f"{thu_muc}:/ra", IMAGE, "/kt/do_nhan_dang.py", "/ra/nhan-dang.json"],
            capture=True, env={"MSYS_NO_PATHCONV": "1"})
    if r.returncode != 0:
        print(f"Do nhan dang loi: {(r.stderr or '')[-400:]}", flush=True)


def _giu_nhat_ky_job(thu_muc: Path) -> None:
    """Giữ log của trainer trước khi container tạm biến mất."""
    for cid in _docker_ps(f"ancestor={IMAGE}"):
        run(["docker", "cp", f"{cid}:/workspace/processed/train_utils/outputs/job_artifacts", thu_muc / "trainer"],
            capture=True, env={"MSYS_NO_PATHCONV": "1"})


def _tat_moi_truong_tam(backend) -> None:
    for loc in (f"label={NHAN}", f"ancestor={IMAGE}"):
        for cid in _docker_ps(loc):
            run(["docker", "rm", "-f", cid], capture=True)
    if backend is not None:
        backend.wait(timeout=30)
    _xoa_csdl(CSDL_E2E)


def chay_trinh_duyet(thu_muc: Path, xem_truc_tiep: bool) -> dict:
    dist = TAM / "dist"
    print("Dung giao dien tu ma dang co...", flush=True)
    run([_npx(), "vite", "build", "--outDir", dist, "--emptyOutDir"], cwd=ROOT / "frontend", check=True, capture=True)

    # Pytest để lại việc trong hàng đợi db test; worker tạm không được nhặt chúng.
    _redis_test("flushdb")

    print("Bat dich vu realtime that...", flush=True)
    realtime = _chay_realtime_that()

    print("Tao CSDL tam tu signdb_test...", flush=True)
    _tao_csdl_tu_test(CSDL_E2E)

    log = (thu_muc / "backend-tam.log").open("w", encoding="utf-8")
    backend = subprocess.Popen(
        [_bash(), "scripts/run_tests.sh"], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        creationflags=NO_WINDOW,
        env=dict(os.environ, MSYS_NO_PATHCONV="1", VOYA_TEST_DATABASE=CSDL_E2E,
                 VOYA_TEST_CMD=f"env REALTIME_SERVICE_URL=http://{realtime}:8010 sh {PY_ENV}/chay_backend.sh"))
    try:
        cid = ""
        for _ in range(60):
            ds = _docker_ps(f"ancestor={IMAGE}")
            cid = ds[0] if ds else ""
            if cid or backend.poll() is not None:
                break
            time.sleep(1)
        if not cid:
            raise SystemExit("Backend tam khong len. Xem backend-tam.log trong bao cao.")
        run(["docker", "run", "-d", "--rm", "--label", NHAN, "--network", NETWORK,
             "-p", f"127.0.0.1:{CONG_E2E}:80", "-e", f"BACKEND={_ten_container(cid)}",
             "-v", f"{dist}:/usr/share/nginx/html:ro",
             "-v", f"{ENV_DIR / 'nginx.conf'}:/etc/nginx/templates/default.conf.template:ro", "nginx:alpine"],
            check=True, capture=True, env={"MSYS_NO_PATHCONV": "1"})

        url = f"http://127.0.0.1:{CONG_E2E}"
        print("Cho backend tam san sang...", flush=True)
        for _ in range(180):
            try:
                if urllib.request.urlopen(f"{url}/api/v1/health", timeout=2).status == 200:
                    break
            except Exception:
                time.sleep(1)
        else:
            raise SystemExit("Backend tam khong tra loi. Xem backend-tam.log trong bao cao.")

        # Mọi kịch bản trong tests-e2e/. Một luồng vì chúng dùng chung tài khoản.
        lenh = [_npx(), "playwright", "test", "--retries=0", "--workers=1",
                "--reporter=list,html,json", f"--output={thu_muc / 'tep'}"]
        if xem_truc_tiep:
            lenh.append("--headed")
        if os.environ.get("KIEM_THU_LOC"):  # chỉ dùng khi gỡ lỗi một kịch bản
            lenh += ["-g", os.environ["KIEM_THU_LOC"]]
        ma = chay_va_ghi(lenh, thu_muc / "trinh-duyet.log", cwd=ROOT / "frontend", env={
            "E2E_BASE_URL": url, "E2E_SLOWMO": "350" if xem_truc_tiep else "0",
            "E2E_VIDEO": str(ROOT.parent / "qipedc_mau" / "D0001B.mp4"),
            "ADMIN_USERNAME": "iso_admin_a", "ADMIN_PASSWORD": "IsoProbe!2026",
            "PLAYWRIGHT_HTML_OUTPUT_DIR": str(thu_muc / "trinh-duyet"), "PLAYWRIGHT_HTML_OPEN": "never",
            "PLAYWRIGHT_JSON_OUTPUT_FILE": str(thu_muc / "trinh-duyet.json")})
        _do_nhan_dang(thu_muc, realtime)
    finally:
        _giu_nhat_ky_job(thu_muc)
        _tat_moi_truong_tam(backend)
        log.close()

    ket = {"ma_thoat": ma, "bao_cao": "trinh-duyet/index.html", "dat": 0, "do": 0, "bo_qua": 0}
    tep = thu_muc / "trinh-duyet.json"
    if tep.exists():
        s = json.loads(tep.read_text(encoding="utf-8")).get("stats", {})
        ket.update(dat=s.get("expected", 0), do=s.get("unexpected", 0), bo_qua=s.get("skipped", 0))
    return ket


# --------------------------------------------------------------- dọn dẹp

def dau_van_tay() -> dict:
    ket = {}
    for rel in TEP_THAT:
        p = ROOT / rel
        ket[rel] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""
    return ket


def don_va_kiem(thu_muc: Path, truoc: dict, sandbox: str | None) -> list[dict]:
    """Dọn hết thứ lượt này tạo ra, rồi KIỂM LẠI từng thứ. Còn sót là KHÔNG ĐẠT."""
    tieu_de("Don dep va kiem lai")
    kq = []

    def ghi(viec, ok, ghi_chu=""):
        kq.append({"viec": viec, "ok": bool(ok), "ghi_chu": ghi_chu})
        print(f"  {'sach' if ok else 'CON SOT'}: {viec} {ghi_chu}", flush=True)

    if sandbox and (TAM / "gdrive").exists():
        ra = _drive_lenh(["xoa", sandbox], thu_muc, "drive-xoa.log")
        ghi(f"Thư mục sandbox trên Drive ({sandbox})", "SANDBOX_CON=khong" in ra)

    _tat_moi_truong_tam(None)
    ghi("Container test", not _docker_ps(f"ancestor={IMAGE}") and not _docker_ps(f"label={NHAN}"))

    ghi(f"CSDL tạm {CSDL_E2E}", not _psql(f"SELECT 1 FROM pg_database WHERE datname='{CSDL_E2E}'").strip())
    _xoa_csdl(CSDL_DRIVE)
    ghi(f"CSDL tạm {CSDL_DRIVE}", not _psql(f"SELECT 1 FROM pg_database WHERE datname='{CSDL_DRIVE}'").strip())

    _redis_test("flushdb")
    ghi(f"Redis test (db {REDIS_TEST})", _redis_test("dbsize") == "0")

    shutil.rmtree(TAM, ignore_errors=True)
    ghi("Thư mục tạm và bản sao thông tin đăng nhập Drive", not TAM.exists())

    log = thu_muc / "backend.log"
    if log.exists():
        noi_dung = log.read_text(encoding="utf-8", errors="replace")
        ghi("Hàng test tạo trong signdb_test", "0 hang con sot" in noi_dung or "khong de lai hang nao" in noi_dung,
            next((d.strip() for d in noi_dung.splitlines() if "hang con sot" in d or "khong de lai" in d), ""))

    sau = dau_van_tay()
    for rel in TEP_THAT:
        ghi(f"Tệp thật không đổi: {rel}", truoc[rel] == sau[rel])

    cac_luot = sorted((d for d in OUT.iterdir() if d.is_dir()), reverse=True)
    for cu in cac_luot[GIU_LAI_LUOT:]:
        shutil.rmtree(cu, ignore_errors=True)
    ghi(f"Báo cáo cũ (giữ {GIU_LAI_LUOT} lượt gần nhất)", True)
    return kq


# --------------------------------------------------------------- lượt chạy

def mo_bao_cao() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    trang = bao_cao.trang_tong_hop()
    webbrowser.open(trang.as_uri())
    print(f"Da mo: {trang}")


def chot(thu_muc: Path, cac_buoc: list[dict], don_dep: list[dict], bat_dau: float, *, mo: bool) -> int:
    so_ca = sum(b["dat"] + b["do"] for b in cac_buoc)
    dat = (bool(cac_buoc) and so_ca > 0 and all(b["ma_thoat"] == 0 for b in cac_buoc)
           and all(x["ok"] for x in don_dep))
    commit = run(["git", "rev-parse", "--short", "HEAD"], capture=True).stdout.strip()
    tep_sua = run(["git", "status", "--porcelain"], capture=True).stdout.splitlines()
    r = {"dat": dat, "commit": commit, "tep_chua_commit": len(tep_sua),
         "bat_dau": datetime.fromtimestamp(bat_dau).strftime("%d/%m/%Y %H:%M:%S"),
         "ket_thuc": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
         "nhanh": run(["git", "branch", "--show-current"], capture=True).stdout.strip(),
         "may": platform.node(), "kich_hoat": "Bấm nút" if mo else "Tự động / chạy ẩn",
         "giay": round(time.time() - bat_dau), "buoc": cac_buoc, "don_dep": don_dep}
    (thu_muc / "ket-qua.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    bao_cao.dung_luot(thu_muc, r)
    trang = bao_cao.trang_tong_hop()
    tieu_de(f"KET QUA: {'DAT' if dat else 'KHONG DAT'} ({so_ca} ca da chay)")
    if mo:
        webbrowser.open((thu_muc / "index.html").as_uri())
    print(f"Bao cao: {trang}", flush=True)
    return 0 if dat else 1


def toan_bo(xem_truc_tiep: bool = True, chi_trinh_duyet: bool = False) -> int:
    kiem_dieu_kien()
    dam_bao_anh()
    thu_muc = OUT / datetime.now().strftime("%Y%m%d-%H%M%S")
    thu_muc.mkdir(parents=True, exist_ok=True)
    TAM.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    truoc = dau_van_tay()
    sandbox = None if chi_trinh_duyet else f"_KIEM_THU_{thu_muc.name.replace('-', '_')}"
    fe = ROOT / "frontend"
    cac_buoc: list[dict] = []
    try:
        if not chi_trinh_duyet:
            _tao_csdl_tu_test(CSDL_DRIVE)
            with ThreadPoolExecutor(1) as nen:
                drive = nen.submit(buoc, "Drive thật (sandbox)", "pytest", lambda: chay_drive(thu_muc, sandbox))
                cac_buoc.append(buoc("Toàn bộ backend", "pytest", lambda: chay_backend(thu_muc)))
                cac_buoc.append(buoc("Toàn bộ frontend", "vitest", lambda: chay_vitest(thu_muc)))
                cac_buoc.insert(1, drive.result())
            cac_buoc.append(buoc("Kiểm kiểu", "tsc", lambda: chay_lenh([_npm(), "run", "typecheck"], fe, thu_muc / "kiem-kieu.log")))
            cac_buoc.append(buoc("Cổng i18n", "i18n-gate", lambda: chay_lenh(["node", "scripts/i18n-gate.mjs"], fe, thu_muc / "i18n.log")))
            cac_buoc.append(buoc("Dựng thử", "vite build", lambda: chay_lenh(
                [_npx(), "vite", "build", "--outDir", TAM / "dist-kiem", "--emptyOutDir"], fe, thu_muc / "dung-thu.log")))
        cac_buoc.append(buoc("Trình duyệt thật", "playwright", lambda: chay_trinh_duyet(thu_muc, xem_truc_tiep)))
    finally:
        don_dep = don_va_kiem(thu_muc, truoc, sandbox)
    return chot(thu_muc, cac_buoc, don_dep, t0, mo=xem_truc_tiep)


if __name__ == "__main__":
    lenh = sys.argv[1] if len(sys.argv) > 1 else ""
    bang = {"toan-bo": toan_bo, "toan-bo-an": lambda: toan_bo(False),
            "trinh-duyet-an": lambda: toan_bo(False, True), "bao-cao": mo_bao_cao}
    if lenh not in bang:
        raise SystemExit(f"Dung tu bang dieu khien. Lenh: {', '.join(bang)}")
    sys.exit(bang[lenh]() or 0)
