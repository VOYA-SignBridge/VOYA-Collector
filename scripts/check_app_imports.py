#!/usr/bin/env python3
"""Mã NGOÀI backend/app còn gọi đúng module `app.*` không?

    python scripts/check_app_imports.py

Thoát 0 = mọi chỗ gọi đều trỏ vào module và tên có thật, 1 = có chỗ hỏng.
Chỉ đọc, không cần cài gói nào của backend.

Vì sao cần
----------
Ngày 08/11/2026, đợt tái cấu trúc dời 9 module vào `backend/app/modules/...`.
Mã trong backend được sửa theo, và pytest xanh. Nhưng CI, script vận hành và
công cụ chuyển server vẫn gọi đường cũ (`from app.tenant_context import ...`,
`python -m app.sync_tasks ...`) bên trong chuỗi `python -c "..."` hoặc trong
YAML/PowerShell. Không trình kiểm kiểu, không bài test nào đọc những chỗ đó:
CI trên `main` dừng ở bước đầu tiên dùng chúng, còn công cụ chuyển server thì
chỉ hỏng vào đúng hôm chuyển máy.

Phép kiểm này đọc mọi tệp được git theo dõi NGOÀI `backend/app/`, tìm:
    from app.x.y import a, b
    import app.x.y
    python -m app.x.y
rồi xác nhận `backend/app/x/y.py` (hoặc gói) tồn tại và định nghĩa `a`, `b`.
Chuỗi tên task Celery kiểu "app.tasks.process_video" KHÔNG bị kiểm: đó là tên
đăng ký, cố ý giữ nguyên qua đợt dời, không phải đường import.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

#: Đuôi tệp có thể chứa lệnh gọi Python vào backend.
SUFFIXES = {".py", ".sh", ".yml", ".yaml", ".ps1", ".bat", ".cmd", ".toml", ".cfg", ".ini", ".md"}
#: Tài liệu kể chuyện lịch sử thì được nhắc đường cũ; chỉ kiểm mã và cấu hình.
SKIP_PREFIXES = ("backend/app/", "docs/", "frontend/")

FROM_RE = re.compile(r"\bfrom\s+(app(?:\.\w+)*)\s+import\s+(\(?[\w\s,]+\)?)")
IMPORT_RE = re.compile(r"(?<![\w.])import\s+(app(?:\.\w+)+)")
RUN_MODULE_RE = re.compile(r"\bpython[0-9.]*\s+-m\s+(app(?:\.\w+)+)")


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [f for f in out.stdout.splitlines()
            if f and not f.startswith(SKIP_PREFIXES)
            and (Path(f).suffix in SUFFIXES or Path(f).name.startswith("Dockerfile"))]


def module_path(module: str) -> Path | None:
    base = BACKEND.joinpath(*module.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=None)
def defined_names(path: Path) -> frozenset[str] | None:
    """Tên cấp module: hàm, lớp, biến, và tên được import vào. None = có `__getattr__`
    hoặc `import *`, tức không suy được tĩnh, nên tin."""
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            if node.name == "__getattr__":
                return None
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        names.add(n.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":
                    return None
                names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, (ast.If, ast.Try)):
            # Định nghĩa trong khối if/try ở cấp module (import tuỳ chọn) vẫn tính.
            for sub in ast.walk(node):
                if isinstance(sub, (ast.FunctionDef, ast.ClassDef)):
                    names.add(sub.name)
                elif isinstance(sub, (ast.Import, ast.ImportFrom)):
                    for alias in sub.names:
                        names.add((alias.asname or alias.name).split(".")[0])
                elif isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    names.add(sub.id)
    return frozenset(names)


def check_from(module: str, imported: str) -> list[str]:
    path = module_path(module)
    if path is None:
        return [f"không có module `{module}`"]
    names = defined_names(path)
    problems = []
    for name in re.findall(r"\w+", imported):
        if name == "as":
            continue
        if names is not None and name not in names and module_path(f"{module}.{name}") is None:
            problems.append(f"`{module}` không có `{name}`")
    return problems


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    failures: list[str] = []
    checked = 0
    for rel in tracked_files():
        try:
            text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in FROM_RE.finditer(line):
                # `from app.x import a as b, c` -> chỉ lấy tên gốc
                imported = re.sub(r"\bas\s+\w+", "", m.group(2))
                checked += 1
                for p in check_from(m.group(1), imported):
                    failures.append(f"{rel}:{lineno}: {p}")
            for rx in (IMPORT_RE, RUN_MODULE_RE):
                for m in rx.finditer(line):
                    checked += 1
                    if module_path(m.group(1)) is None:
                        failures.append(f"{rel}:{lineno}: không có module `{m.group(1)}`")
    if failures:
        print("Mã ngoài backend/app gọi module hoặc tên không tồn tại:")
        for f in failures:
            print(f"  {f}")
        print("Thường do module đã dời chỗ: tìm chỗ mới bằng "
              "`git log --follow --name-status -- backend/app/<tên cũ>.py`.")
        return 1
    print(f"OK: {checked} chỗ gọi vào app.* ngoài backend/app đều trỏ đúng.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
