import csv, io, pathlib, collections

HERE = pathlib.Path(__file__).resolve().parent
# Doc tu ban da COMMIT trong evidence/, khong tu ban nhap trong thu muc lam
# viec: tai lieu sinh ra phai dung lai duoc tu repo, khong phu thuoc mot may.
EVIDENCE = HERE.parent / "evidence"

def doc(t):
    return list(csv.DictReader(io.StringIO(pathlib.Path(t).read_text(encoding="utf-8"))))

cols = doc(EVIDENCE / "pdm_v8_columns.csv")
fks = doc(EVIDENCE / "pdm_v8_foreign_keys.csv")
chks = doc(EVIDENCE / "pdm_v8_checks.csv")
uqs = doc(EVIDENCE / "pdm_v8_uniques.csv")
# Nguon bang chung THU SAU. Them sau khi `trg_legal_documents_freeze` di qua bon
# nhom QA ma khong cong nao thay: no cuong che tinh bat bien o tang CSDL nhung
# khong nam trong pg_constraint. Cong may duoi cung se HONG neu mot trigger cua
# san xuat khong duoc mo ta nao dan ten.
trgs = doc(EVIDENCE / "pdm_v8_triggers.csv")

# Lớp phủ mô tả nghiệp vụ. Nó KHÔNG đến từ catalog — không có COMMENT nào trong
# CSDL — mà từ `pdm_v8_descriptions.csv`, một tệp người viết và người duyệt.
# Giữ hai nguồn tách bạch là chủ ý: dòng nào của hệ thống, dòng nào của tác giả,
# phải phân biệt được. `semantic_status` in kèm chính vì thế.
# KHONG boc trong try/except FileNotFoundError. Ban dau co, va no bien mot tep
# mo ta bi mat thanh mot phu luc sinh ra binh thuong nhung TRONG RONG mo ta —
# hong im lang, dung kieu tai lieu nay ton tai de tranh.
mota = {}
_trung = 0
for d in doc(EVIDENCE / "pdm_v8_descriptions.csv"):
    _k = (d["table_name"], d["column_name"])
    if _k in mota:
        _trung += 1
    mota[_k] = d

TEN = {"A":"Tenant & Access Management","B":"Authentication & User Security",
       "C":"VSL Vocabulary & Registry","D":"VSL Collection & Dataset",
       "E":"Legal, Consent & Governance","F":"Training & Evaluation",
       "G":"Plan, Billing & Storage","H":"Integration & Operations"}
NHOM = {}
for d in (HERE / "groups.txt").read_text(encoding="utf-8").split("\n"):
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
import collections as _cl
_pb = _cl.Counter(x["semantic_status"] for x in mota.values())
w(f"**Mô tả nghiệp vụ phủ {len(mota)}/{len(cols)} cột — toàn bộ tám nhóm A–H.**")
w("")
w("| trạng thái | số cột |")
w("|---|---:|")
for _k in ("VERIFIED", "NEEDS_REVIEW", "LEGACY", "DERIVED"):
    w(f"| `{_k}` | {_pb.get(_k, 0)} |")
w("")
w("Mô tả KHÔNG đến từ catalog: cơ sở dữ liệu có **0** `COMMENT ON COLUMN` và")
w("**0** `COMMENT ON TABLE`. Suy mô tả từ tên cột là bịa — người đọc không phân")
w("biệt được một dòng lấy từ hệ thống với một dòng đoán ra. Vì vậy mô tả sống ở")
w("`evidence/pdm_v8_descriptions.csv`, tách khỏi catalog, mỗi dòng mang nhãn:")
w("")
w("* *(không nhãn)* — **VERIFIED**: có bằng chứng từ mã hoặc từ dữ liệu đã đo")
w("* `LEGACY` — dấu vết lịch sử, KHÔNG phải nguồn chuẩn")
w("* `DERIVED` — do pipeline tính ra, không do người nhập")
w("* **`CẦN DUYỆT`** — cấu trúc vật lý đã xác thực từ catalog, nhưng **ý định")
w("  nghiệp vụ** chưa đủ bằng chứng để khẳng định mạnh hơn")
w("")
w("**`CẦN DUYỆT` KHÔNG có nghĩa là dữ liệu sai.** Kiểu, ràng buộc, khoá và")
w("cardinality của những cột ấy lấy từ catalog như mọi cột khác; thứ còn thiếu")
w("là một đường mã hoặc một quyết định thiết kế nói cột ấy DÙNG để làm gì. Mỗi")
w("dòng như vậy đều ghi rõ thiếu bằng chứng nào — không dòng nào để trống lý do.")
w("")
w("Chưa chạy `COMMENT ON` nào trên sản xuất: đó sẽ là DDL mới và kéo theo câu")
w("hỏi phiên bản migration chỉ để phục vụ tài liệu.")
w("")
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

# newline="\n" TUONG MINH: mac dinh cua write_text la newline=None,
# tuc dich xuong dong thanh os.linesep — CRLF tren Windows. Cung mot bo sinh
# se cho hai chuoi byte khac nhau tuy he dieu hanh, va phep so byte chung
# minh tinh tai lap se sai o dung cho no can dung.
(HERE.parent / "PDM_V8_DATA_DICTIONARY.md").write_text("\n".join(o), encoding="utf-8", newline="\n")
print("da sinh", len(o), "dong")


# ---------------------------------------------------------------- cong may
# Bat bien cua Phu luc C.8. In moi lan chay, thoat 1 neu lech — de mot ban
# sinh lech khong the di qua ma khong ai thay.
HOP_LE = {"VERIFIED", "NEEDS_REVIEW", "LEGACY", "DERIVED"}
_ten_cot = {(c["table_name"], c["column_name"]) for c in cols}
_ten_mota = set(mota)
_pb = collections.Counter(x["semantic_status"] for x in mota.values())
_thieu_note = [k for k, v in mota.items()
               if v["semantic_status"] == "NEEDS_REVIEW" and not (v.get("note") or "").strip()]
_sai_tt = [k for k, v in mota.items() if v["semantic_status"] not in HOP_LE]

_g = [("catalog columns", len(_ten_cot), 660),
      ("description rows", len(_ten_mota), 660),
      ("dictionary rows", len(_ten_cot & _ten_mota), 660),
      (None, None, None),
      ("duplicate descriptions", _trung, 0),
      ("missing descriptions", len(_ten_cot - _ten_mota), 0),
      ("extra descriptions", len(_ten_mota - _ten_cot), 0),
      (None, None, None)]
_g += [(k, _pb.get(k, 0), None) for k in ("VERIFIED", "NEEDS_REVIEW", "LEGACY", "DERIVED")]
_g += [(None, None, None),
       ("description status total", sum(_pb.values()), 660),
       ("NEEDS_REVIEW without note", len(_thieu_note), 0),
       ("invalid semantic_status", len(_sai_tt), 0)]

print()
print("--- cong may (Phu luc C.8) ---")
_le = 0
for _n, _co, _can in _g:
    if _n is None:
        print()
        continue
    if _can is not None and _co != _can:
        _le += 1
        print("%-26s %6d   <-- LECH, can %d" % (_n, _co, _can))
    else:
        print("%-26s %6d" % (_n, _co))
if _thieu_note:
    print("   thieu note:", ", ".join("%s.%s" % k for k in _thieu_note[:10]))
if _sai_tt:
    print("   trang thai la:", ", ".join("%s.%s" % k for k in _sai_tt[:10]))
# --- nguon bang chung thu sau: trigger ---
_mota_text = " ".join((v.get("description") or "") + " " + (v.get("note") or "")
                      for v in mota.values())
_trg_thieu = [t["trigger_name"] for t in trgs if t["trigger_name"] not in _mota_text]
print()
print("%-26s %6d" % ("database triggers", len(trgs)))
print("%-26s %6d" % ("trigger claims documented", len(trgs) - len(_trg_thieu)))
if _trg_thieu:
    _le += 1
    print("%-26s %6d   <-- LECH, can 0" % ("undocumented triggers", len(_trg_thieu)))
    for _t in _trg_thieu:
        print("   khong mo ta nao dan:", _t)
else:
    print("%-26s %6d" % ("undocumented triggers", 0))

if _le:
    raise SystemExit(1)
