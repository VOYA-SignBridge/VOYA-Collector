#!/usr/bin/env python3
"""Hợp đồng giữa docker-compose, nginx và công cụ vận hành còn nguyên không?

    python scripts/check_compose_contracts.py

Thoát 0 = đạt, 1 = có hợp đồng bị phá. Chỉ đọc, cần `pyyaml`.

Vì sao cần
----------
Ba tệp viết bởi ba người khác nhau phải khớp nhau mà không tệp nào nhắc tới tệp
kia:

* `scripts/voya.py` bật bảo trì bằng cách tạo `nginx.conf.d/maintenance.on`;
* `nginx.conf` trả trang bảo trì khi thấy `/etc/nginx/conf.d/maintenance.on`;
* `docker-compose.yml` là thứ duy nhất nối hai đường đó bằng một bind mount.

Ngày 08/11/2026 phát hiện dòng mount ấy đã bị xoá từ 20/10 trong một đợt dọn
dẹp. Không có gì báo lỗi: nginx khởi động bình thường, `voya update-*` vẫn tạo
tệp cờ, chỉ có người dùng nhận lỗi 502 thay vì trang "đang bảo trì" trong mỗi
lần cập nhật. Phép kiểm này giữ cho ba đầu dây còn nối với nhau.

Ngoài ra: mọi tệp cấu hình mà compose gắn vào container (nginx.conf, cấu hình
Loki/Prometheus/Grafana, script sao lưu) phải được git theo dõi. Một tệp bị dời
hoặc bị gitignore nhầm làm Docker tự tạo một THƯ MỤC rỗng cùng tên, và dịch vụ
khởi động với cấu hình trống thay vì báo thiếu tệp.

Cuối cùng: mọi đường `COPY`/`ADD` trong mọi Dockerfile phải trỏ vào tệp có trong
git, tính từ thư mục của Dockerfile (cũng là build context). Một đợt dời thư mục
làm hỏng đường này thì ảnh chỉ hỏng lúc dựng, và với `Dockerfile.coderefresh`
(đường `voya update-code`) thì là lúc dựng trên chính máy chạy web. Phép kiểm
này bắt nó trong chưa tới một giây, không cần dựng ảnh 13 GB.
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILES = sorted(ROOT.glob("docker-compose*.yml"))
#: Thư mục dữ liệu sinh ra lúc chạy: không có trong git là đúng.
RUNTIME_DIRS = ("dataset", "gdrive", "certs", "backups", "processed")


def tracked() -> set[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return set(out.stdout.splitlines())


def bind_mounts(path: Path):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for name, svc in (data.get("services") or {}).items():
        for vol in svc.get("volumes") or []:
            if isinstance(vol, str):
                parts = vol.split(":")
                src, dst = parts[0], (parts[1] if len(parts) > 1 else "")
            else:
                src, dst = vol.get("source", ""), vol.get("target", "")
            if src.startswith("."):
                yield name, src, dst


def dockerfile_copy_problems(files: set[str]) -> list[str]:
    """Nguồn của COPY/ADD (trừ `--from=`) phải khớp ít nhất một tệp trong git."""
    problems = []
    for df in sorted(f for f in files if Path(f).name.startswith("Dockerfile")):
        context = str(Path(df).parent).replace("\\", "/")
        prefix = "" if context == "." else context + "/"
        text = (ROOT / df).read_text(encoding="utf-8", errors="replace")
        # Nối các dòng kết thúc bằng `\` thành một lệnh.
        for instr in re.sub(r"\\\n", " ", text).splitlines():
            parts = instr.split()
            if not parts or parts[0].upper() not in ("COPY", "ADD"):
                continue
            args = [a for a in parts[1:] if not a.startswith("--")]
            if any(a.startswith("--from") for a in parts[1:]) or len(args) < 2:
                continue
            for src in args[:-1]:
                if src in (".", "./") or src.startswith(("http://", "https://", "$")):
                    continue
                pattern = prefix + src.rstrip("/")
                if not any(fnmatch.fnmatch(f, pattern) or f.startswith(pattern + "/") for f in files):
                    problems.append(f"{df}: `{instr.strip()}` chép `{src}` nhưng không có tệp nào khớp "
                                    f"trong `{context}/`")
    return problems


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    problems: list[str] = []
    files = tracked()

    # 1. Mọi tệp/thư mục cấu hình được gắn vào container phải có trong git.
    for compose in COMPOSE_FILES:
        for svc, src, _dst in bind_mounts(compose):
            rel = src[2:].rstrip("/") if src.startswith("./") else src
            if rel in ("", ".") or rel.split("/")[0] in RUNTIME_DIRS:
                continue
            if rel not in files and not any(f.startswith(rel + "/") for f in files):
                problems.append(f"{compose.name}: service `{svc}` gắn `{src}` nhưng git không theo dõi nó")

    # 2. Chuỗi bảo trì: voya.py -> nginx.conf.d/ -> mount -> nginx.conf.
    voya = (ROOT / "scripts" / "voya.py").read_text(encoding="utf-8")
    if not re.search(r'MAINT_FLAG\s*=\s*ROOT\s*/\s*"nginx\.conf\.d"\s*/\s*"maintenance\.on"', voya):
        problems.append("scripts/voya.py: MAINT_FLAG không còn là nginx.conf.d/maintenance.on; sửa luôn các bước dưới")
    base = ROOT / "docker-compose.yml"
    nginx_mounts = {(src.rstrip("/"), dst) for svc, src, dst in bind_mounts(base) if svc == "nginx"}
    if ("./nginx.conf.d", "/etc/nginx/conf.d") not in nginx_mounts:
        problems.append("docker-compose.yml: nginx thiếu `./nginx.conf.d:/etc/nginx/conf.d:ro`; "
                        "bật bảo trì sẽ không có tác dụng và người dùng nhận lỗi 502")
    conf = (ROOT / "nginx.conf").read_text(encoding="utf-8")
    if "/etc/nginx/conf.d/maintenance.on" not in conf:
        problems.append("nginx.conf: không còn kiểm /etc/nginx/conf.d/maintenance.on")
    if "nginx.conf.d/maintenance.html" not in files:
        problems.append("nginx.conf.d/maintenance.html không có trong git: trang bảo trì sẽ trống")

    # 3. Dockerfile chỉ chép những gì có thật.
    problems += dockerfile_copy_problems(files)

    if problems:
        print("Hợp đồng compose / nginx / voya bị phá:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"OK: {len(COMPOSE_FILES)} tệp compose, mount cấu hình đều có trong git, chuỗi bảo trì còn nối, "
          "mọi COPY trong Dockerfile trỏ vào tệp có thật.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
