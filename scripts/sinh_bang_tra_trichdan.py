# -*- coding: utf-8 -*-
"""Sinh bảng tra: khoá trích dẫn -> tài liệu, để dùng cạnh Word.

Mỗi khi gặp \\cite{xxx} trong bản thảo, tra bảng này lấy tiêu đề, dán vào ô tìm
của hộp Add/Edit Citation trong Word.
"""
import io, os, re, sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

os.chdir(r"e:\CTU_ProjectOutside\VOYA-Collector")
BIB = "docs/00-thesis/SignBridge_Reference/SignBridge_Reference.bib"
GT = "docs/00-thesis/LUANVAN_PHANGIOITHIEU.md"
C2 = "docs/00-thesis/LUANVAN_CHUONG2.md"
OUT = "docs/00-thesis/BANG_TRA_TRICH_DAN.md"

raw = io.open(BIB, encoding="utf-8", errors="replace").read()


def truong(body, ten):
    mm = re.search(r"(?:^|,)\s*" + ten + r"\s*=\s*\{", body, re.I | re.S)
    if not mm:
        return ""
    i = mm.end() - 1
    d = 0
    for k in range(i, len(body)):
        if body[k] == "{":
            d += 1
        elif body[k] == "}":
            d -= 1
            if d == 0:
                return re.sub(r"\s+", " ", body[i + 1:k]).strip()
    return ""


def sach(t):
    return re.sub(r"\s+", " ", t.replace("{", "").replace("}", "")).strip()


def tac_gia_ngan(a):
    a = sach(a)
    if not a:
        return "—"
    ho = [p.strip() for p in re.split(r"\s+and\s+", a)]
    def ho_cua(x):
        return x.split(",")[0].strip() if "," in x else x.strip()
    if len(ho) == 1:
        return ho_cua(ho[0])
    if len(ho) == 2:
        return "%s & %s" % (ho_cua(ho[0]), ho_cua(ho[1]))
    return ho_cua(ho[0]) + " và cs."


muc = {}
for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", raw):
    j = raw.index("{", m.start())
    d = 0
    for k in range(j, len(raw)):
        if raw[k] == "{":
            d += 1
        elif raw[k] == "}":
            d -= 1
            if d == 0:
                break
    body = raw[m.end():k]
    muc[m.group(2)] = {
        "kieu": m.group(1).lower(),
        "title": sach(truong(body, "title")),
        "author": tac_gia_ngan(truong(body, "author") or truong(body, "editor")),
        "year": sach(truong(body, "year")) or "n.d.",
        "doi": sach(truong(body, "doi")),
        "url": sach(truong(body, "url")),
    }


def dem(path):
    s = io.open(path, encoding="utf-8", errors="replace").read()
    s = s[:re.search(r"^## A\. ", s, re.M).start()] if (
        path.endswith("PHANGIOITHIEU.md") and re.search(r"^## A\. ", s, re.M)) else s
    d = {}
    for m in re.finditer(r"cite\{([^}]*)\}", s):
        for kk in m.group(1).split(","):
            kk = kk.strip()
            if kk and kk not in ("*", "key"):
                d[kk] = d.get(kk, 0) + 1
    return d


dgt, dc2 = dem(GT), dem(C2)
dung = sorted(set(dgt) | set(dc2))

# khoá trong bản thảo -> các khoá "anh em sinh đôi" dễ chọn nhầm trong Word
CAP_BAY = {
    "quochoi_luat_bvdlcn_2025": ["quochoi_luat_shtt_2025", "quochoi_luat_dulieu_2024"],
    "chinhphu_nd356_2025": ["chinhphu_nd165_2025"],
    "nguyenquoc_multiview_2026": ["nguyenquoc_vsl400_dua_2026"],
    "li_wlasl_baibao_2020": ["li_wlasl_giayphep_2020"],
}

L = []
L.append("# Bảng tra trích dẫn — khoá → tài liệu")
L.append("")
L.append("*Sinh tự động ngày 14/08/2026 từ `SignBridge_Reference/SignBridge_Reference.bib`.*")
L.append("")
L.append("Dùng khi soạn trong Word. Gặp `\\cite{xxx}` trong bản thảo thì tra ở đây, chép cột")
L.append("**Tiêu đề** vào ô tìm của hộp **Add/Edit Citation** (`Ctrl+Alt+C`) rồi Enter.")
L.append("")
L.append("Cột **GT/C2** là số lần khoá đó xuất hiện ở phần giới thiệu / Chương 2 — dùng để")
L.append("đếm xem đã chèn hết chưa. Tổng: **%d lượt** ở phần giới thiệu, **%d lượt** ở Chương 2."
         % (sum(dgt.values()), sum(dc2.values())))
L.append("")
L.append("> **Vì sao cần bảng này.** Word lấy dữ liệu từ thư viện Zotero, không từ tệp `.bib`,")
L.append("> và hộp *Add/Edit Citation* tìm theo **tiêu đề** chứ không theo khoá. Bản thảo lại")
L.append("> đánh dấu bằng khoá. Bảng này nối hai đầu đó.")
L.append(">")
L.append("> Khoá trong `.bib` **đổi mỗi lần xuất lại từ Zotero** (đã đổi ba lần trong hai ngày),")
L.append("> nên đừng coi cột *Khoá* là thứ bền vững — nó chỉ để tra ngược về bản thảo. Nếu bản")
L.append("> thảo có sửa, sinh lại bảng bằng `python scripts/sinh_bang_tra_trichdan.py`.")
L.append("")
L.append("| # | Khoá | GT | C2 | Tác giả | Năm | Tiêu đề (chép cột này) |")
L.append("|---|---|---|---|---|---|---|")
for i, k in enumerate(dung, 1):
    e = muc.get(k)
    if not e:
        L.append("| %d | `%s` | %s | %s | ❌ | ❌ | **KHÔNG CÓ TRONG `.bib`** |"
                 % (i, k, dgt.get(k, "") or "", dc2.get(k, "") or ""))
        continue
    L.append("| %d | `%s` | %s | %s | %s | %s | %s |"
             % (i, k, dgt.get(k, "") or "", dc2.get(k, "") or "",
                e["author"], e["year"], e["title"]))

L.append("")
L.append("---")
L.append("")
L.append("## Bốn cặp dễ chọn nhầm trong hộp tìm của Word")
L.append("")
L.append("Bốn tài liệu dưới đây có **anh em sinh đôi** trong thư viện — cùng tác giả, cùng chủ")
L.append("đề, tiêu đề gần giống. Chọn nhầm thì Word vẫn chèn bình thường, danh mục vẫn đẹp, chỉ")
L.append("có điều sai nguồn. Không công cụ nào bắt được.")
L.append("")
L.append("Cột trái là thứ bản thảo cần; cột phải là thứ sẽ hiện ra ngay cạnh nó trong hộp tìm.")
L.append("")
L.append("| Bản thảo cần — CHỌN CÁI NÀY | ĐỪNG chọn nhầm sang |")
L.append("|---|---|")
for k, ems in CAP_BAY.items():
    if k not in dung or k not in muc:
        continue
    trai = "**%s** (%s)<br>`%s`" % (muc[k]["title"], muc[k]["year"], k)
    phai = "<br><br>".join(
        "%s (%s)<br>`%s`" % (muc[e]["title"], muc[e]["year"], e)
        for e in ems if e in muc)
    L.append("| %s | %s |" % (trai, phai))

kh_dung = sorted(set(muc) - set(dung))
L.append("")
L.append("## Mục có trong thư viện nhưng hai chương chưa trích (%d)" % len(kh_dung))
L.append("")
L.append("Phần lớn dành cho Chương 3–5. Không cần chèn bây giờ; Word chỉ đưa vào danh mục")
L.append("những mục thật sự được trích, nên để đó vô hại.")
L.append("")
L.append("| Khoá | Tác giả | Năm | Tiêu đề |")
L.append("|---|---|---|---|")
for k in kh_dung:
    e = muc[k]
    L.append("| `%s` | %s | %s | %s |" % (k, e["author"], e["year"], e["title"]))

io.open(OUT, "w", encoding="utf-8", newline="").write("\n".join(L) + "\n")
tong_gt = sum(dgt.values())
tong_c2 = sum(dc2.values())
print("Da ghi %s" % OUT)
print("  %d khoa duoc trich (GT %d luot, C2 %d luot)" % (len(dung), tong_gt, tong_c2))
print("  %d muc trong .bib chua chuong nao dung" % len(kh_dung))
thieu = [k for k in dung if k not in muc]
print("  khoa KHONG co trong .bib: %s" % (", ".join(thieu) if thieu else "khong con"))
