"""Trích lược đồ AS-BUILT từ CSDL đang chạy, rồi đối chiếu với `ensure_tables()`.

Chạy:
    VOYA_TEST_CMD="python scripts/reverse_asbuilt_schema.py" bash scripts/run_tests.sh

Vì sao đọc CSDL trước, đọc mã sau — chứ không ngược lại
========================================================
Hai nguồn trả lời hai câu khác nhau:

```
lược đồ CSDL      "hệ thống ĐANG CÓ gì"        <- nguồn của as-built
ensure_tables()   "mã HIỆN MUỐN tạo ra gì"     <- nguồn đối chiếu
```

Chúng không luôn trùng nhau, và vụ chỉ mục bốn cột ngày 17/08/2026 là bằng
chứng: mã đã đổi sang khoá năm cột, nhưng chỉ mục cũ vẫn nằm trong CSDL cho tới
khi có một câu `DROP` thật sự chạy. Một mô hình vẽ từ `ensure_tables()` sẽ không
thấy chỉ mục ấy — tức là vẽ as-INTENDED và gọi nó là as-built.

Chênh lệch KHÔNG được tự động sửa theo bên nào. Nó được phân loại:

```
runtime      có trong CSDL, có trong mã          -> vào As-built PDM
legacy       có trong CSDL, KHÔNG còn trong mã   -> tồn dư, phải điều tra
declared     có trong mã, CHƯA có trong CSDL     -> khai báo chưa materialize
target-only  không ở cả hai, chỉ có trong thiết kế
```

Chỉ nhóm `runtime` được vào As-built PDM.

Tự kiểm cơ sở dữ liệu
=====================
`run_tests.sh` có hai lớp chặn, và lớp hai (`conftest`) là một fixture của
pytest — nó KHÔNG chạy cho lệnh này. Nên script tự kiểm `current_database()`
trước khi đọc bất cứ thứ gì. Script chỉ đọc, nhưng "chỉ đọc" không phải lý do để
bỏ kiểm: một lượt trích nhầm vào sản xuất sẽ sinh ra một mô hình as-built của
CSDL sai, và không ai phát hiện được bằng cách nhìn tệp kết quả.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

CSDL_CHO_PHEP = {"signdb_test", "signdb_ci", "postgres_test"}
DICH = REPO / "docs" / "00-thesis" / "asbuilt"

#: Miền nghiệp vụ -> tiền tố/tên bảng. Dùng để tách diagram, không phải để phân
#: quyền. Bảng không khớp miền nào rơi vào `Z_chua_phan_loai` — cố ý hiện ra
#: thay vì bị nhét im lặng vào một miền sẵn có.
MIEN = {
    # Tên ĐẦY ĐỦ cho những bảng dễ bắt nhầm. Một tiền tố `user_` ở miền A sẽ nuốt
    # luôn `user_consents` — vốn thuộc miền E — vì vòng lặp duyệt theo thứ tự khai
    # báo và A đứng trước E. Tiền tố rộng chỉ dùng khi cả họ tên chắc chắn cùng
    # một miền.
    "A_tenant_iam_authz": (
        "tenants", "users", "memberships", "tenant_members", "roles", "role_",
        "permissions", "policy", "casbin", "sessions", "api_keys", "two_factor",
        "totp", "password_", "email_verification", "invitations", "tenant_invitations",
        "sudo", "access_", "workspaces", "projects",
        "refresh_tokens", "user_totp", "user_recovery_codes",
        "user_action_passcodes", "verification_codes",
    ),
    "B_danh_muc_vsl": (
        "classes", "dialects", "dialect_", "vocabulary", "registry_", "sign_",
        "catalog", "recognition_profiles",
        # Ba bảng `community_*` là siêu dữ liệu DANH MỤC, không phải dữ liệu
        # nghiệp vụ của reserved tenant `community`: chúng không có `tenant_id`
        # và không có RLS. Xếp chúng vào miền tenant sẽ gợi ý ngược lại.
        "community_", "languages", "regions",
    ),
    "C_nguoi_ky_phien_thu_mau": (
        "signers", "signer_", "capture_sessions", "samples", "sample_",
        "raw_uploads", "quality",
    ),
    "D_huan_luyen_hien_vat": (
        "training_", "model_", "experiment", "datasets", "dataset_", "splits",
        "checkpoint",
    ),
    "E_phap_ly_dong_thuan_kiem_toan": (
        "legal_", "consents", "user_consents", "signer_consents", "audit",
        "audit_log", "terms",
    ),
    "F_control_plane": (
        "tenant_exports", "tenant_usage", "tenant_subscriptions", "billing",
        "plans", "webhook", "notifications", "support_", "outbox", "event_",
        "schema_migrations", "migration_", "sot_", "trial", "usage_",
        "google_sheets_sync_status", "platform_settings", "tenant_purges",
    ),
}


def _mien_cua(ten: str) -> str:
    for mien, tien_to in MIEN.items():
        for t in tien_to:
            if ten == t or ten.startswith(t):
                return mien
    return "Z_chua_phan_loai"


# --------------------------------------------------------------------- CSDL


def _cur():
    from app.storage.metadata_db import _migration_cursor
    return _migration_cursor()


def _kiem_csdl(cur) -> str:
    cur.execute("SELECT current_database()")
    ten = cur.fetchone()[0]
    if ten not in CSDL_CHO_PHEP:
        raise SystemExit(
            f"TU CHOI: '{ten}' khong nam trong danh sach CSDL test "
            f"({', '.join(sorted(CSDL_CHO_PHEP))}). Lop hai cua run_tests.sh la "
            f"mot fixture pytest nen no KHONG chay cho lenh nay; day la ban thay the.")
    return ten


TRUY_VAN = {
    "cot": """
        SELECT c.table_name, c.column_name, c.ordinal_position, c.data_type,
               c.character_maximum_length, c.numeric_precision, c.is_nullable,
               c.column_default
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema = c.table_schema AND t.table_name = c.table_name
        WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
        ORDER BY c.table_name, c.ordinal_position
    """,
    # Khoá ngoại lấy qua pg_constraint chứ không qua information_schema:
    # information_schema tách khoá nhiều cột thành nhiều dòng và không giữ thứ
    # tự cột, nên một khoá ngoại HỢP (tenant_id, job_id) đọc lên giống hai khoá
    # đơn — đúng thứ luận văn cần phân biệt.
    "khoa": """
        SELECT con.conname, cl.relname AS bang, con.contype,
               pg_get_constraintdef(con.oid) AS dinh_nghia
        FROM pg_constraint con
        JOIN pg_class cl ON cl.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = cl.relnamespace
        WHERE n.nspname = 'public'
        ORDER BY cl.relname, con.contype, con.conname
    """,
    "chi_muc": """
        SELECT tablename, indexname, indexdef
        FROM pg_indexes WHERE schemaname = 'public'
        ORDER BY tablename, indexname
    """,
    "view": """
        SELECT table_name, view_definition
        FROM information_schema.views WHERE table_schema = 'public'
        ORDER BY table_name
    """,
    "trigger": """
        SELECT c.relname AS bang, t.tgname, pg_get_triggerdef(t.oid) AS dinh_nghia
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE NOT t.tgisinternal AND n.nspname = 'public'
        ORDER BY c.relname, t.tgname
    """,
    # RLS: ba thuộc tính riêng biệt hay bị gộp. `relrowsecurity` là BẬT,
    # `relforcerowsecurity` là áp cả cho CHỦ SỞ HỮU bảng. Bật mà không force thì
    # vai sở hữu đi xuyên qua mọi policy — và vai migration chính là vai đó.
    "rls": """
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        ORDER BY c.relname
    """,
    "policy": """
        SELECT tablename, policyname, cmd, qual, with_check
        FROM pg_policies WHERE schemaname = 'public'
        ORDER BY tablename, policyname
    """,
}


def doc_lich_su_csdl() -> dict:
    ra: dict = {}
    with _cur() as cur:
        cur.execute("SELECT set_config('app.system_scope','on',false)")
        ra["_database"] = _kiem_csdl(cur)
        for ten, sql in TRUY_VAN.items():
            cur.execute(sql)
            cot = [d[0] for d in cur.description]
            ra[ten] = [dict(zip(cot, hang)) for hang in cur.fetchall()]
    return ra


# ----------------------------------------------------------------- ý định mã


#: `CREATE TABLE [IF NOT EXISTS] <tên> (` — dấu mở ngoặc là BẮT BUỘC.
#:
#: Bản đầu không đòi dấu ngoặc và báo về bảy "bảng" tên `ch`, `does`, `if`,
#: `listing`, `sai`, `statements`. Không cái nào là bảng: biểu thức khớp cụm
#: "CREATE TABLE" nằm trong VĂN XUÔI chú thích rồi lấy từ kế tiếp. Một danh sách
#: `declared` bịa ra sẽ đi thẳng vào ma trận sai khác của luận văn.
#:
#: `<tên>` cũng nhận dạng `{HẰNG}`: `schema_version.py` viết
#: `CREATE TABLE IF NOT EXISTS {SCHEMA_VERSION_TABLE} (`, và bản đầu xếp
#: `schema_migrations` vào `legacy` — "có trong CSDL, mã không còn tạo" — cho một
#: bảng mã VẪN tạo, chỉ là tạo bằng tên nội suy. Đó là kết luận nguy hiểm nhất
#: trong bốn nhóm, vì nó mời người đọc đi xoá một bảng đang được dùng.
_MAU_CREATE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(\{[A-Za-z_][A-Za-z0-9_]*\}|[A-Za-z_][A-Za-z0-9_.]*)\s*\(",
    re.IGNORECASE)


def _giai_hang(ten: str, nguon: str) -> str:
    """`{HẰNG}` -> giá trị chuỗi của hằng đó, tìm ở cấp module trong cùng tệp."""
    if not (ten.startswith("{") and ten.endswith("}")):
        return ten
    hang = ten[1:-1]
    m = re.search(rf"^{re.escape(hang)}\s*[:=][^=]*?[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']",
                  nguon, re.MULTILINE)
    return m.group(1) if m else ten


def bang_ma_muon_tao() -> tuple:
    """(tên bảng mã khai `CREATE TABLE`, tên chưa giải được).

    Quét văn bản chứ không gọi `ensure_tables()`: gọi nó sẽ TẠO bảng, làm hỏng
    đúng phép đo đang thực hiện — lược đồ sau lượt gọi không còn là lược đồ ta
    muốn chụp. Đây cũng là lý do script không chạy migration nào.

    Giới hạn còn lại, ghi ra thay vì giấu: tên bảng dựng động ở mức phức tạp hơn
    một hằng chuỗi (nối chuỗi, tra từ điển, vòng lặp trên danh sách) vẫn không
    giải được. Chúng nằm trong vế thứ hai của giá trị trả về, và một mục ở đó
    nghĩa là ma trận sai khác CHƯA đầy đủ — không phải "không có gì".
    """
    ra: set = set()
    chua_giai: set = set()
    for tep in (REPO / "backend" / "app").rglob("*.py"):
        try:
            nguon = tep.read_text(encoding="utf-8")
        except OSError:
            continue
        for tho in _MAU_CREATE.findall(nguon):
            ten = _giai_hang(tho, nguon).split(".")[-1].lower()
            (chua_giai if ten.startswith("{") else ra).add(ten)
    return ra, chua_giai


#: Tệp `.sql` là ẢNH CHỤP một CSDL, không phải tài liệu thiết kế.
#:
#: `backup.sql` là đầu ra `pg_dump` ngày 30/07/2026. Một bảng chỉ xuất hiện ở đó
#: là bằng chứng về QUÁ KHỨ — nó từng tồn tại thật rồi bị bỏ — chứ không phải
#: bằng chứng về ý định kiến trúc. Gộp hai loại này lại sẽ đưa `user_profiles`
#: vào Target PDM với nhãn "cấu phần kiến trúc mục tiêu", trong khi sự thật
#: ngược lại: nó là thứ đã bị loại bỏ.
#:
#: Cùng một đuôi tệp, hai loại chứng cứ trái hướng nhau.
ANH_CHUP_KHONG_PHAI_THIET_KE = ("backup.sql", "merge_data.sql")


def bang_trong_sql_khong_thi_hanh() -> tuple:
    """(bảng trong DDL THIẾT KẾ, bảng chỉ có trong ẢNH CHỤP cũ)."""
    ra: dict = defaultdict(list)
    lich_su: dict = defaultdict(list)
    for tep in REPO.rglob("*.sql"):
        if ".git" in tep.parts:
            continue
        if tep.name in ANH_CHUP_KHONG_PHAI_THIET_KE:
            try:
                for m in _MAU_CREATE.findall(tep.read_text(encoding="utf-8")):
                    lich_su[m.split(".")[-1].lower()].append(tep.name)
            except OSError:
                pass
            continue
        try:
            noi_dung = tep.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in _MAU_CREATE.findall(noi_dung):
            ra[m.split(".")[-1].lower()].append(str(tep.relative_to(REPO)).replace("\\", "/"))
    return dict(ra), dict(lich_su)


# ------------------------------------------------------------------- kết quả


def _revision() -> tuple:
    """(SHA đang đứng, "sach" | mô tả cây bẩn).

    Chạy trong container, nơi `git` có thể không có và `.git` được mount vào —
    nên cả hai đường đều phải chịu được thất bại mà không làm hỏng phép chụp
    lược đồ. Không đọc được thì nói không đọc được; không đoán.
    """
    # Ưu tiên biến môi trường: script chạy TRONG container, và container không
    # có `git`. Đường git bên dưới giữ lại để chạy trực tiếp trên máy chủ.
    tu_moi_truong = os.environ.get("VOYA_ASBUILT_REVISION", "").strip()
    if tu_moi_truong:
        return (tu_moi_truong, os.environ.get("VOYA_ASBUILT_TREE", "khong ro").strip())

    import subprocess
    def _chay(*args):
        return subprocess.run(args, cwd=str(REPO), capture_output=True,
                              text=True, timeout=30)
    try:
        r = _chay("git", "rev-parse", "HEAD")
        if r.returncode != 0:
            return ("khong doc duoc git", "khong ro")
        sha = r.stdout.strip()
        d = _chay("git", "status", "--porcelain")
        if d.returncode != 0:
            return (sha, "khong ro")
        so = len([x for x in d.stdout.splitlines() if x.strip()])
        return (sha, "sach" if so == 0 else f"{so} tệp")
    except Exception as exc:
        return (f"khong doc duoc ({type(exc).__name__})", "khong ro")


def main() -> int:
    lich_su = doc_lich_su_csdl()
    bang_that = sorted({r["table_name"] for r in lich_su["cot"]})
    trong_ma, ten_chua_giai = bang_ma_muon_tao()
    trong_sql, trong_anh_chup = bang_trong_sql_khong_thi_hanh()

    # Tên VIEW phải tách khỏi "chưa materialize".
    #
    # `tenant_members` khai `CREATE TABLE` trong ERD nhưng runtime dựng nó thành
    # VIEW trên `memberships` (PDM v5, kèm `security_invoker`). Xếp nó vào
    # `declared` đọc lên là "mã có, CSDL chưa có" — sai, và sai theo hướng khiến
    # người đọc đi tạo một bảng chồng lên một view đang phục vụ.
    ten_view = {v["table_name"] for v in lich_su["view"]}

    phan_loai: dict = {}
    for b in bang_that:
        phan_loai[b] = "runtime" if b in trong_ma else "legacy"
    for b in sorted(ten_view):
        phan_loai[b] = "view"
    for b in sorted(trong_ma - set(bang_that) - ten_view):
        phan_loai[b] = "declared"
    for b in sorted(set(trong_sql) - set(bang_that) - trong_ma - ten_view):
        phan_loai[b] = "target-only"
    for b in sorted(set(trong_anh_chup) - set(bang_that) - trong_ma
                    - ten_view - set(trong_sql)):
        phan_loai[b] = "historical"

    DICH.mkdir(parents=True, exist_ok=True)
    (DICH / "asbuilt_schema.json").write_text(
        json.dumps(lich_su, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    theo_mien: dict = defaultdict(list)
    for b in bang_that:
        theo_mien[_mien_cua(b)].append(b)

    rls = {r["relname"]: r for r in lich_su["rls"]}
    so_cot: dict = defaultdict(int)
    for r in lich_su["cot"]:
        so_cot[r["table_name"]] += 1
    fk = [k for k in lich_su["khoa"] if k["contype"] == "f"]
    fk_hop = [k for k in fk if k["dinh_nghia"].count(",") >= 1
              and re.search(r"FOREIGN KEY \([^)]*,", k["dinh_nghia"])]

    rev, ban = _revision()
    dong = [
        "# Lược đồ AS-BUILT — trích trực tiếp từ CSDL đang chạy",
        "",
        f"Nguồn: `{lich_su['_database']}`. Sinh bởi `scripts/reverse_asbuilt_schema.py`.",
        "",
        f"**Revision:** `{rev}` — " + (
            "cây làm việc **sạch**; phép chụp này đủ tư cách làm as-built."
            if ban == "sach" else
            "⚠ **không xác định được** cây làm việc sạch hay bẩn."
            if ban == "khong ro" else
            f"⚠ **cây làm việc CÓ THAY ĐỔI CHƯA COMMIT** ({ban.replace('ban:', '')} tệp)"),
        "",
        "Revision phải nằm trong tệp này, không nằm trong trí nhớ người chạy. Một mô",
        "hình as-built không tự khai nó chụp lúc nào thì không đối chiếu lại được, và",
        "câu *\"tái dựng từ lược đồ của revision được đóng băng\"* trong luận văn không",
        "có gì chống lưng. Nếu dòng trên báo cây làm việc bẩn thì phép chụp này chưa",
        "đủ tư cách làm as-built cho bản nộp — chạy lại sau khi commit.",
        "",
        "**Nguồn của tệp này là CƠ SỞ DỮ LIỆU, không phải mã.** `ensure_tables()` chỉ",
        "dùng để đối chiếu. Hai nguồn trả lời hai câu khác nhau — *đang có gì* và *mã",
        "muốn tạo gì* — và khi chúng lệch, không bên nào được tự động thắng.",
        "",
        "## Tổng lượng",
        "",
        f"- bảng: **{len(bang_that)}**",
        f"- view: {len(lich_su['view'])}",
        f"- khoá ngoại: {len(fk)} (trong đó **hợp nhiều cột: {len(fk_hop)}**)",
        f"- ràng buộc CHECK: {sum(1 for k in lich_su['khoa'] if k['contype'] == 'c')}",
        f"- UNIQUE: {sum(1 for k in lich_su['khoa'] if k['contype'] == 'u')}",
        f"- chỉ mục: {len(lich_su['chi_muc'])}"
        f" (partial: {sum(1 for i in lich_su['chi_muc'] if ' WHERE ' in i['indexdef'])})",
        f"- trigger: {len(lich_su['trigger'])}",
        f"- bảng bật RLS: {sum(1 for r in rls.values() if r['relrowsecurity'])}"
        f" — trong đó FORCE: {sum(1 for r in rls.values() if r['relforcerowsecurity'])}",
        f"- policy: {len(lich_su['policy'])}",
        "",
        "## Ma trận sai khác As-built ↔ mã ↔ thiết kế",
        "",
        "| Phân loại | Nghĩa | Số |",
        "|---|---|---|",
    ]
    y_nghia = {
        "runtime": "có trong CSDL **và** trong mã → vào As-built PDM",
        "view": "materialize dưới dạng **VIEW**, không phải bảng nền → vào As-built PDM, vẽ khác bảng",
        "legacy": "có trong CSDL, **không** còn trong mã → tồn dư, phải điều tra",
        "declared": "có trong mã, **chưa** materialize dưới bất kỳ dạng nào",
        "target-only": "chỉ có trong DDL **thiết kế** chưa thi hành → sang Target PDM",
        "historical": "chỉ có trong **ảnh chụp CSDL cũ** (`pg_dump`) → đã bị bỏ, KHÔNG phải target",
    }
    for loai, nghia in y_nghia.items():
        dong.append(f"| `{loai}` | {nghia} | {sum(1 for v in phan_loai.values() if v == loai)} |")

    dong += ["", "**Giới hạn của phép quét này.** Nó đọc VĂN BẢN mã nguồn, nên một câu",
             "`CREATE TABLE` có tên bảng dựng động phức tạp hơn một hằng chuỗi sẽ không được",
             "nhìn thấy. Tên chưa giải được trong lượt này: "
             + (", ".join(f"`{t}`" for t in sorted(ten_chua_giai)) if ten_chua_giai
                else "**không có**") + ".",
             "",
             "Mục nào ở đây nghĩa là ma trận trên CHƯA đầy đủ, chứ không phải \"không có gì\".",
             "Bản đầu của công cụ này báo `schema_migrations` là tồn dư — cho một bảng mã vẫn",
             "tạo, qua `CREATE TABLE IF NOT EXISTS {SCHEMA_VERSION_TABLE}`. Đó là kết luận",
             "nguy hiểm nhất trong bốn nhóm, vì nó mời người đọc đi xoá một bảng đang dùng."]

    for loai in ("legacy", "declared", "target-only", "historical"):
        ds = sorted(b for b, v in phan_loai.items() if v == loai)
        dong += ["", f"### `{loai}` — {len(ds)} bảng", ""]
        if not ds:
            dong.append("_(không có)_")
        for b in ds:
            nguon = trong_sql.get(b) or trong_anh_chup.get(b)
            dong.append(f"- `{b}`" + (f" — {', '.join(sorted(set(nguon)))}" if nguon else ""))

    dong += ["", "## As-built theo miền (một miền = một diagram)", ""]
    for mien in sorted(theo_mien):
        ds = sorted(theo_mien[mien])
        dong += ["", f"### PDM-{mien}  ({len(ds)} bảng)", "",
                 "| Bảng | Cột | RLS | FORCE | Policy |", "|---|---|---|---|---|"]
        for b in ds:
            r = rls.get(b, {})
            n_pol = sum(1 for p in lich_su["policy"] if p["tablename"] == b)
            dong.append(
                f"| `{b}` | {so_cot[b]} | {'✓' if r.get('relrowsecurity') else '—'} "
                f"| {'✓' if r.get('relforcerowsecurity') else '—'} | {n_pol} |")

    (DICH / "ASBUILT_INVENTORY.md").write_text("\n".join(dong) + "\n", encoding="utf-8")

    print(f"CSDL      : {lich_su['_database']}")
    print(f"bang      : {len(bang_that)}")
    for loai in y_nghia:
        print(f"  {loai:<12}: {sum(1 for v in phan_loai.values() if v == loai)}")
    print(f"viet ra   : {DICH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
