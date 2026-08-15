# -*- coding: utf-8 -*-
"""Tách bản SẠCH của phần giới thiệu để chép vào Word.

Lấy từ LUANVAN_PHANGIOITHIEU.md: bỏ khối ghi chú đầu tệp, bỏ toàn bộ phụ chú
A-F, đổi công thức LaTeX thành ký tự thường (Word không hiểu `$...$`).
Giữ nguyên dấu \\cite{} — đó là chỗ cần bấm Ctrl+Alt+C.
"""
import io, os, re, sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

os.chdir(r"e:\CTU_ProjectOutside\VOYA-Collector")
NGUON = "docs/00-thesis/LUANVAN_PHANGIOITHIEU.md"
DICH = "docs/00-thesis/PHANGIOITHIEU_BAN_SACH.md"

s = io.open(NGUON, encoding="utf-8", newline="").read()

# 1. cắt phần phụ chú
m = re.search(r"^---\s*\n---\s*\n\s*# PHỤ CHÚ CHO TÁC GIẢ", s, re.M)
if not m:
    m = re.search(r"^# PHỤ CHÚ CHO TÁC GIẢ", s, re.M)
than = s[:m.start()].rstrip() + "\n"

# 2. bỏ khối trích dẫn ghi chú ngay dưới tiêu đề
NL = "\r\n" if "\r\n" in than else "\n"
than, n_bo = re.subn(
    r"^(# [^\r\n]+)\r?\n\r?\n(?:>[^\r\n]*\r?\n)+\r?\n---\r?\n",
    lambda mm: mm.group(1) + NL + NL, than, count=1)
if not n_bo:
    print("CANH BAO: khong bo duoc khoi ghi chu dau tep — kiem lai bang tay")

# 3. công thức LaTeX -> ký tự thường
than = than.replace(r"$21 \times 3 \times 2 = 126$", "21 × 3 × 2 = 126")
if "$" in than:
    print("CANH BAO: con ky tu $ — kiem lai cong thuc:")
    for i, d in enumerate(than.split("\n"), 1):
        if "$" in d:
            print("   dong %d: %s" % (i, d.strip()[:90]))

io.open(DICH, "w", encoding="utf-8", newline="").write(than)

# 4. thống kê để đối chiếu tiến độ chèn trích dẫn trong Word
muc, dem = None, {}
tong = 0
for dong in than.split("\n"):
    h = re.match(r"^## (\d\..*)$", dong)
    if h:
        muc = h.group(1)
        dem.setdefault(muc, 0)
    n = len(re.findall(r"cite\{", dong))
    if n and muc:
        dem[muc] = dem.get(muc, 0) + n
    tong += n

print("\nDa ghi %s" % DICH)
print("  %d dong, %d tu (uoc luong)" % (than.count("\n") + 1, len(than.split())))
print("\nSo lan bam Ctrl+Alt+C theo tung muc:")
for k, v in dem.items():
    print("  %-46s %d" % (k, v))
print("  %-46s %d" % ("TONG", tong))
