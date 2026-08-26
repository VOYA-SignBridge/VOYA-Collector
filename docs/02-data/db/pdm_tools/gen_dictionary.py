import csv, io, pathlib, collections

def doc(t):
    return list(csv.DictReader(io.StringIO(pathlib.Path(t).read_text(encoding="utf-8"))))

cols, fks, chks, uqs = doc("cols.csv"), doc("fk.csv"), doc("chk.csv"), doc("uq.csv")

# Lớp phủ mô tả nghiệp vụ. Nó KHÔNG đến từ catalog — không có COMMENT nào trong
# CSDL — mà từ `pdm_v8_descriptions.csv`, một tệp người viết và người duyệt.
# Giữ hai nguồn tách bạch là chủ ý: dòng nào của hệ thống, dòng nào của tác giả,
# phải phân biệt được. `semantic_status` in kèm chính vì thế.
mota = {}
try:
    for d in doc("desc.csv"):
        mota[(d["table_name"], d["column_name"])] = d
except FileNotFoundError:
    pass

TEN = {"A":"Tenant & Access Management","B":"Authentication & User Security",
       "C":"VSL Vocabulary & Registry","D":"VSL Collection & Dataset",
       "E":"Legal, Consent & Governance","F":"Training & Evaluation",
       "G":"Plan, Billing & Storage","H":"Integration & Operations"}
NHOM = {}
for d in pathlib.Path("nhom.txt").read_text().split("\n"):
    p = d.split()
    if p:
        for t in p[1:]: NHOM[t] = p[0]

# cột -> các khoá ngoại chứa nó. Khoá GHÉP xếp trước: nó là ràng buộc mạnh hơn.
ref = collections.defaultdict(list)
for r in fks:
    for c in r["child_cols"].split("+"):
        ref[(r["child_table"], c)].append(r)
for k in ref:
    ref[k].sort(key=lambda r: -int(r["n_cols"]))

def ve_ref(tbl, col):
    rs = ref.get((tbl, col))
    if not rs: return "—"
    ra = []
    for r in rs:
        if int(r["n_cols"]) > 1:
            ra.append(f"`({r['child_cols'].replace('+',', ')})` → `{r['parent_table']}({r['parent_cols'].replace('+',', ')})`")
        else:
            ra.append(f"`{r['parent_table']}.{r['parent_cols']}`")
    return "<br>".join(ra)

theo_bang = collections.defaultdict(list)
for c in cols: theo_bang[c["table_name"]].append(c)
chk_b = collections.defaultdict(list)
for c in chks: chk_b[c["table_name"]].append(c)
uq_b = collections.defaultdict(list)
for u in uqs: uq_b[u["table_name"]].append(u)
fk_b = collections.defaultdict(list)
for f in fks: fk_b[f["child_table"]].append(f)

o = []; w = o.append
w("# Phụ lục C.8 — Data Dictionary (lược đồ v8)\n")
w("Sinh thẳng từ catalog của `signdb` (sản xuất) ngày 26/08/2026, lược đồ **v8**,")
w("checksum `fb5b9b90c553`. **Không ràng buộc nào được gõ tay.**\n")
w("| | |")
w("|---|---:|")
w(f"| bảng | {len(theo_bang)} |")
w(f"| cột | {len(cols)} |")
w(f"| khoá ngoại | {len(fks)} |")
w(f"| CHECK | {len(chks)} |")
w(f"| đối tượng duy nhất (PK/UNIQUE/chỉ mục) | {len(uqs)} |")
w(f"| cột có DEFAULT | {sum(1 for c in cols if c['column_default'])} |")
w("")
w("## Ba điều phải đọc trước khi dùng bảng này\n")
w(f"**Mô tả nghiệp vụ đang phủ {len(mota)}/{len(cols)} cột — nhóm A, C, D và E — bốn miền lõi.** Phần")
w("còn lại trống, và đó là chủ ý. Cơ sở dữ liệu có **0**")
w("`COMMENT ON COLUMN` và **0** `COMMENT ON TABLE`, nên catalog không có nguồn mô")
w("tả nào. Suy mô tả từ tên cột là bịa: người đọc luận văn không phân biệt được")
w("một dòng lấy từ hệ thống với một dòng đoán ra. Mô tả nghiệp vụ phải viết tay")
w("cho các bảng quan trọng, và khi ấy nó là tri thức của tác giả chứ không phải")
w("số liệu của hệ thống.\n")
w("**Cột `Tham chiếu` ưu tiên khoá GHÉP.** Nhiều cặp bảng có CẢ khoá một cột (di")
w("sản) lẫn khoá ghép `(tenant_id, …)`; cả hai đều liệt kê, ghép đứng trước, vì")
w("ghép mới là thứ khiến việc trỏ sang tổ chức khác không biểu diễn được.\n")
w("**Ràng buộc tách sang C.8.2.** 18/68 CHECK phủ NHIỀU cột — ép chúng vào một")
w("dòng cột sẽ làm sai nghĩa. Và 22 bất biến nằm ở **chỉ mục duy nhất một phần**,")
w("thứ `pg_constraint` không hề thấy.\n")

w("---\n\n# C.8.1 — Từ điển cột\n")
for k in "ABCDEFGH":
    ts = sorted(t for t, g in NHOM.items() if g == k)
    w(f"## {k}. {TEN[k]}\n")
    for t in ts:
        rs = theo_bang[t]
        w(f"### `{t}` — {len(rs)} cột\n")
        w("| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |")
        w("|--:|---|---|:--:|:--:|---|---|---|")
        for c in rs:
            khoa = " ".join(x for x in (c["is_pk"], c["is_fk"]) if x) or "—"
            md = c["column_default"]
            md = f"`{md[:44]}`" + ("…" if len(md) > 44 else "") if md else "—"
            m = mota.get((t, c["column_name"]))
            if m:
                bieu = {"VERIFIED":"", "LEGACY":" `LEGACY`", "DERIVED":" `DERIVED`",
                        "NEEDS_REVIEW":" **`CẦN DUYỆT`**"}.get(m["semantic_status"], "")
                mt = m["description"] + bieu + (f"<br><sub>{m['note']}</sub>" if m["note"] else "")
            else:
                mt = ""
            w(f"| {c['ordinal']} | `{c['column_name']}` | `{c['data_type']}` | "
              f"{'✓' if c['nullable']=='YES' else '—'} | {khoa} | {md} | "
              f"{ve_ref(t, c['column_name'])} | {mt} |")
        w("")

w("---\n\n# C.8.2 — Ràng buộc toàn vẹn\n")
w("## C.8.2.a — CHECK\n")
w(f"{len(chks)} ràng buộc, trong đó **{sum(1 for c in chks if c['scope'].startswith('BAT BIEN'))}** phủ nhiều cột.\n")
w("| Bảng | Ràng buộc | Cột | Phạm vi | Quy tắc |")
w("|---|---|---|---|---|")
for c in chks:
    pv = "**nhiều cột**" if c["scope"].startswith("BAT BIEN") else "một cột"
    w(f"| `{c['table_name']}` | `{c['constraint_name']}` | `{c['columns']}` | {pv} | `{c['rule']}` |")
w("")
w("## C.8.2.b — Khoá chính, UNIQUE và chỉ mục duy nhất\n")
w("Cột `Điều kiện` là vị từ của chỉ mục **một phần**: bất biến chỉ áp cho các")
w("hàng thoả vị từ ấy. Đây là nhóm mà một lượt truy `pg_constraint` sẽ bỏ sót")
w("hoàn toàn — 22 trong số đó.\n")
w("| Bảng | Đối tượng | Loại | Cột | Điều kiện |")
w("|---|---|---|---|---|")
for u in uqs:
    w(f"| `{u['table_name']}` | `{u['object_name']}` | {u['kind']} | "
      f"`{u['columns']}` | {('`'+u['predicate']+'`') if u['predicate'] else '—'} |")
w("")
w("## C.8.2.c — Khoá ngoại\n")
w(f"{len(fks)} khoá ngoại, trong đó **{sum(1 for f in fks if int(f['n_cols'])>1)}** là khoá ghép.\n")
w("| Con | Cột con | Cha | Cột cha | Cha | Con | ON DELETE | Ràng buộc |")
w("|---|---|---|---|:--:|:--:|---|---|")
for f in fks:
    w(f"| `{f['child_table']}` | `{f['child_cols']}` | `{f['parent_table']}` | "
      f"`{f['parent_cols']}` | {f['parent_card']} | {f['child_card']} | "
      f"{f['on_delete']} | `{f['conname']}` |")
w("")
w("## C.8.3 — View\n")
w("`tenant_members` là VIEW `security_invoker` trên `memberships`, 7 cột. Nó KHÔNG")
w("nằm trong 660 cột ở trên (đó là cột của bảng). Ghi ở đây vì bỏ nó đi sẽ khiến")
w("phụ lục im lặng về một đối tượng mà mã ứng dụng có đọc — và `security_invoker`")
w("chính là thứ khiến mọi truy vấn qua view chịu đúng chính sách RLS của người")
w("gọi. Gỡ thuộc tính ấy là mở toang view.\n")

pathlib.Path("PDM_V8_DATA_DICTIONARY.md").write_text("\n".join(o), encoding="utf-8")
print("da sinh", len(o), "dong")
