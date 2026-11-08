#!/usr/bin/env python3
"""docs/ còn đúng là tài liệu kỹ thuật công khai, gọn và không gãy liên kết?

    python scripts/check_docs.py

Thoát 0 = đạt, 1 = có vi phạm. Chỉ đọc.

Repo này công khai. Ngày 08/11/2026 phải gỡ khỏi nó luận văn, bài báo, báo cáo
nghiên cứu, ba bảng liệt kê người ký bằng tên thật và một email sinh viên. Bốn
luật dưới đây giữ cho chuyện đó không lặp lại:

1. Không tệp nào được theo dõi ở các chỗ dành cho tài liệu riêng
   (luận văn, bài báo, báo cáo, bằng chứng có tên người ký). `.gitignore` đã
   chặn, nhưng `git add -f` vẫn vượt qua được.
2. Không có địa chỉ email thật trong docs/ (chỉ cho phép miền ví dụ).
3. Gốc docs/ không có tệp lẻ: tài liệu mới vào đúng thư mục chủ đề.
4. Liên kết tương đối trong tài liệu phải trỏ tới tệp có thật. Riêng
   11-worklog/ là lịch sử, được phép trỏ tới trạng thái cũ, nên không kiểm.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PRIVATE_PATHS = (
    re.compile(r"^docs/00-thesis/"),
    re.compile(r"^docs/CTU_SignBridge/"),
    re.compile(r"^reports/"),
    re.compile(r"^docs/02-data/db/evidence/[^/]*signer[^/]*\.csv$"),
)
ROOT_FILES_ALLOWED = {
    "docs/README.md",
    "docs/HUONG_DAN_DEV.html",            # VOYA_UI mở theo đúng đường này
    "docs/TENANT_ISOLATION_AND_AUTHZ.md",  # mã nguồn trỏ thẳng tới đường này
}
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\b")
PLACEHOLDER_DOMAIN = re.compile(
    r"(^|\.)(example\.(com|org|net)|x\.com|local|test|invalid|example|localhost)$", re.I)
LINK_RE = re.compile(r"\]\(([^)\s]+?)(?:#[^)]*)?\)")
TEXT_SUFFIXES = {".md", ".html", ".csv", ".txt", ".json", ".py", ".sql", ".drawio", ".vbs", ".bib", ".tex"}


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return out.stdout.splitlines()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    files = tracked()
    problems: list[str] = []

    for f in files:
        if any(rx.search(f) for rx in PRIVATE_PATHS):
            problems.append(f"{f}: tài liệu riêng (luận văn/bài báo/báo cáo/tên người ký) không được vào repo công khai")

    docs = [f for f in files if f.startswith("docs/")]
    for f in docs:
        if f.count("/") == 1 and f not in ROOT_FILES_ALLOWED:
            problems.append(f"{f}: tệp lẻ ở gốc docs/, hãy đặt vào thư mục chủ đề (xem docs/README.md)")
        if Path(f).suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = (ROOT / f).read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in EMAIL_RE.finditer(line):
                if not PLACEHOLDER_DOMAIN.search(m.group(1)):
                    problems.append(f"{f}:{lineno}: có địa chỉ email `{m.group(0)}`; dùng miền ví dụ như user@example.com")
        if f.endswith(".md") and not f.startswith("docs/11-worklog/"):
            for lineno, line in enumerate(text.splitlines(), 1):
                for m in LINK_RE.finditer(line):
                    target = m.group(1)
                    if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith(("/", "<", "#")):
                        continue
                    resolved = os.path.normpath(os.path.join(os.path.dirname(f), target))
                    if not (ROOT / resolved).exists():
                        problems.append(f"{f}:{lineno}: liên kết hỏng -> {target}")

    if problems:
        print("docs/ vi phạm quy ước:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"OK: {len(docs)} tệp trong docs/, không có tài liệu riêng, email thật hay liên kết hỏng.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
