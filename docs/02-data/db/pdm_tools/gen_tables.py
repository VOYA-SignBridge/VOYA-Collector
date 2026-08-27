import csv, io, pathlib, collections

NHOM = {}
TEN_NHOM = {
 "A": "Tenant & Access Management", "B": "Authentication & User Security",
 "C": "VSL Vocabulary & Registry",  "D": "VSL Collection & Dataset",
 "E": "Legal, Consent & Governance","F": "Training & Evaluation",
 "G": "Plan, Billing & Storage",    "H": "Integration & Operations",
}
HERE = pathlib.Path(__file__).resolve().parent
# Doc tu ban da COMMIT trong evidence/, khong tu ban nhap trong thu muc lam
# viec: tai lieu sinh ra phai dung lai duoc tu repo, khong phu thuoc mot may.
EVIDENCE = HERE.parent / "evidence"
for dong in (HERE / "groups.txt").read_text(encoding="utf-8").split("\n"):
    p = dong.split()
    if not p: continue
    for t in p[1:]: NHOM[t] = p[0]

tbl = list(csv.DictReader(io.StringIO((EVIDENCE / "pdm_v8_tables.csv").read_text(encoding="utf-8"))))
fk  = list(csv.DictReader(io.StringIO((EVIDENCE / "pdm_v8_foreign_keys.csv").read_text(encoding="utf-8"))))
theo = {r["tbl"]: r for r in tbl}

out = []
w = out.append
w("# Bảng cơ sở dữ liệu v8 — nguồn cho PDM\n")
w("Sinh thẳng từ catalog của `signdb` (sản xuất) ngày 26/08/2026, lược đồ **v8**,")
w("checksum `fb5b9b90c553`. Không gõ tay dòng nào: 62 bảng, 131 khoá ngoại.\n")
w("Cách đọc cardinality: cột **Cha** là `1` khi mọi cột khoá ngoại đều NOT NULL,")
w("và `0..1` khi có cột cho phép NULL — tức là con **có thể chưa** nối cha.\n")

w("## 1. Sáu mươi hai bảng theo tám nhóm\n")
for k in "ABCDEFGH":
    ts = sorted(t for t, g in NHOM.items() if g == k)
    tong_cot = sum(int(theo[t]["n_cols"]) for t in ts)
    w(f"### {k}. {TEN_NHOM[k]} — {len(ts)} bảng, {tong_cot} cột\n")
    w("| Bảng | Khoá chính | Cột | FK ra | FK vào | RLS | Có `tenant_id` |")
    w("|---|---|---:|---:|---:|:--:|:--:|")
    for t in ts:
        r = theo[t]
        w(f"| `{t}` | `{r['pk']}` | {r['n_cols']} | {r['fk_ra']} | {r['fk_vao']} | "
          f"{'✓' if r['rls']=='t' else '—'} | {'✓' if r['co_tenant_id']=='t' else '—'} |")
    w("")

ghep = [r for r in fk if int(r["n_cols"]) > 1]
w(f"## 2. Hai mươi bảy khoá ngoại GHÉP — rào cản xuyên tenant\n")
w("Đây là nhóm đáng nói nhất trong luận văn. Khoá ngoại ghép `(tenant_id, <khoá>)`")
w("khiến việc trỏ sang hàng của tổ chức khác **không biểu diễn được** ở tầng lược")
w("đồ, chứ không phải chỉ bị chặn bởi mã ứng dụng. Trên ERD nên vẽ chúng khác")
w("kiểu với khoá ngoại một cột.\n")
w("| Con | Cột con | Cha | Cột cha | Cha | Con | ON DELETE |")
w("|---|---|---|---|:--:|:--:|---|")
for r in sorted(ghep, key=lambda x: (x["child_table"], x["conname"])):
    w(f"| `{r['child_table']}` | `{r['child_cols']}` | `{r['parent_table']}` | "
      f"`{r['parent_cols']}` | {r['parent_card']} | {r['child_card']} | {r['on_delete']} |")
w("")

w(f"## 3. Toàn bộ {len(fk)} khoá ngoại\n")
w("| Con | Cột con | Cha | Cột cha | Cha | Con | ON DELETE | Tên ràng buộc |")
w("|---|---|---|---|:--:|:--:|---|---|")
for r in fk:
    w(f"| `{r['child_table']}` | `{r['child_cols']}` | `{r['parent_table']}` | "
      f"`{r['parent_cols']}` | {r['parent_card']} | {r['child_card']} | "
      f"{r['on_delete']} | `{r['conname']}` |")
w("")

dem = collections.Counter(r["parent_table"] for r in fk)
w("## 4. Bảng bị trỏ tới nhiều nhất (quyết định bố cục hình)\n")
w("Bảng càng nhiều mũi tên vào thì càng phải đặt ở trung tâm, nếu không hình sẽ")
w("thành mạng dây.\n")
w("| Bảng cha | Số khoá ngoại trỏ vào |")
w("|---|---:|")
for t, n in dem.most_common(12):
    w(f"| `{t}` | {n} |")
w("")

# newline="\n" TUONG MINH: mac dinh cua write_text la newline=None,
# tuc dich xuong dong thanh os.linesep — CRLF tren Windows. Cung mot bo sinh
# se cho hai chuoi byte khac nhau tuy he dieu hanh, va phep so byte chung
# minh tinh tai lap se sai o dung cho no can dung.
(HERE.parent / "PDM_V8_TABLES.md").write_text("\n".join(out), encoding="utf-8", newline="\n")
print("da sinh:", len(out), "dong")
