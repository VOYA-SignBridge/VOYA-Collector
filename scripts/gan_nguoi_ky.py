"""Gán danh tính người ký (signer_id) cho mẫu theo TÊN người ký ghi lúc thu.

Bối cảnh 15/09/2026: 2.186/3.864 mẫu không có signer_id; S010/S011 là "người ký"
tự sinh khi vá khoá ngoại (08/08) gom 6 người thật; S103/S104 là người ký của hai
tài khoản thử đã xoá. Vì thế mọi phép chia tách người ký đều thấy 5–6 người và
từ chối. Cột `user_id` của mẫu là tên người ký gõ lúc thu (mặc định = username
tài khoản thu), và đó là nguồn danh tính duy nhất còn lại.

QUY TẮC ÁNH XẠ (`MAP` bên dưới) — chủ dự án chốt; sửa bảng là sửa được kết quả:
  * Mỗi tên là MỘT người. Biến thể chính tả gộp lại: Tram=Trâm; Thungan=Thu Ngân=Ngan.
  * "Minh" và "Huy" (S001, tài khoản Minh6868) giữ là HAI người — gộp sau dễ
    (signer_aliases), tách sau khó.
  * "Khang" (10 mẫu thu bằng tài khoản Khoa) là người khác Khoa.
  * Hai dòng user_id là UUID tài khoản Minh → Minh.

Ghi BA nơi cho khớp: Postgres (`samples.signer_id`, `signers`, `signer_aliases`),
`dataset/samples.csv`, sidecar `sample_<uid>.json`; và `dataset/signers.csv`.
Đồng thuận KHÔNG bị đụng: người ký mới chưa có bản ghi nào → cổng nội bộ vẫn cho
qua (quy tắc kế thừa cho người chưa từng được hỏi); nghiên cứu/công bố vẫn cần ký.

Chạy trong container backend:  python /tmp/g.py            (xem trước)
                               python /tmp/g.py --apply    (ghi)
"""
import csv, io, json, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app")
from app.storage.metadata_db import _execute, _fetch_all  # noqa: E402
from app.tenant_context import system_scope  # noqa: E402

APPLY = "--apply" in sys.argv
TENANT = "default"
DATASET = Path("/dataset")
NOW = datetime.now(timezone.utc).isoformat()

# signer_id -> (display_name, external_user_id | None, [tên ghi lúc thu])
MAP = {
    # Số hiệu chọn để KHỚP config/legacy_signer_mapping.json (sổ tên→ID của đường
    # nghiên cứu, 31/07) ở mọi chỗ không đụng sổ ứng dụng: Trâm S003, Ảnh S004,
    # Hoàng Anh S005, Thu Ngân S006, Nhung S012 giống nhau ở cả hai sổ. Hai chỗ
    # hai sổ đã lệch từ trước (nghiên cứu: S001=Trân, S002=Minh; ứng dụng: S001=Huy,
    # S002=Khoa — gắn tài khoản và đồng thuận) thì giữ sổ ứng dụng và cấp số MỚI
    # cho Minh (S014), Trân (S015), Khang (S016). Hiện vật nghiên cứu dựng TRƯỚC
    # 15/09/2026 vẫn mang số cũ — xem ghi chú trong legacy_signer_mapping.json.
    "S001": ("Huy", "eea09456-c189-4f90-97c1-d6458f203d46", ["Huy"]),
    "S002": ("Khoa", "10459d17-114f-418f-a171-2b9ed94970fd", ["Khoa"]),
    "S003": ("Trâm", None, ["Trâm", "Tram"]),
    "S004": ("Ảnh", None, ["Ảnh"]),
    "S005": ("Hoàng Anh", None, ["Hoàng Anh"]),
    "S006": ("Thu Ngân", "01e0245f-c3fb-48a4-9844-bdfd0d2a2ba7", ["Thu Ngân", "Thungan", "Ngan"]),
    "S008": ("Thư", None, ["Thư"]),
    "S012": ("Nhung", None, ["Nhung"]),
    "S014": ("Minh", "eeeaeb8b-a832-4d1d-bac7-ebdd819fc644",
             ["Minh", "eeeaeb8b-a832-4d1d-bac7-ebdd819fc644"]),
    "S015": ("Trân", "70ab8773-454d-4c88-bce0-e4f348558761", ["Trân"]),
    "S016": ("Khang", None, ["Khang"]),
}
RETIRE = {  # người ký tự sinh / của tài khoản thử → ngưng hoạt động sau khi gán lại
    "S010": "tu sinh 08/08 gom 6 nguoi; da tach theo ten 15/09/2026",
    "S011": "tu sinh 08/08 gom 3 nguoi; da tach theo ten 15/09/2026",
    "S103": "nguoi ky cua tai khoan thu Minh123 (da xoa); mau -> S014",
    "S104": "nguoi ky cua tai khoan thu Minh1234 (da xoa); mau -> S014",
    "S007": "so nghien cuu 'ha' — khong co mau o may nay",
    "S009": "so nghien cuu 'user1' — khong co mau o may nay",
    "S013": "so nghien cuu cu = Khoa; ung dung dung S002 cho Khoa — de trong, tranh hai so mot nguoi",
}
ALIASES = {"S103": "S014", "S104": "S014", "S013": "S002"}
name_to_sid = {n: sid for sid, (_, _, names) in MAP.items() for n in names}

with system_scope("gan nguoi ky: doc"):
    rows = _fetch_all(
        "SELECT sample_uid, user_id, signer_id, file_path FROM samples WHERE deleted_at IS NULL")
plan = {}   # sample_uid -> new signer
unknown = {}
for r in rows:
    name = (r["user_id"] or "").strip()
    cur = (r["signer_id"] or "").strip()
    new = name_to_sid.get(name)
    if new is None:
        unknown[name] = unknown.get(name, 0) + 1
        continue
    if cur != new:
        plan[r["sample_uid"]] = (cur or "-", new, r["file_path"])

from collections import Counter
moves = Counter((c, n) for c, n, _ in plan.values())
print("KẾ HOẠCH đổi signer_id (cũ → mới: số mẫu):")
for (c, n), k in sorted(moves.items(), key=lambda kv: -kv[1]):
    print(f"  {c:5s} → {n:5s} {MAP[n][0]:10s} {k:5d}")
print(f"  TỔNG {len(plan)} mẫu; không ánh xạ được: {unknown or 'không'}")
after = Counter(name_to_sid.get((r['user_id'] or '').strip(), r['signer_id']) for r in rows)
print("Sau khi gán, mẫu theo người ký:", {f"{k}({MAP.get(k, ('?',))[0]})": v for k, v in after.most_common()})

if not APPLY:
    print("(xem trước; thêm --apply để ghi)")
    sys.exit(0)

# --- 1. sổ người ký (DB) ---------------------------------------------------
with system_scope("gan nguoi ky: so nguoi ky"):
    for sid, (name, ext, _) in MAP.items():
        _execute(
            "INSERT INTO signers (tenant_id, signer_id, display_name, external_user_id, is_active, created_at) "
            "VALUES (%s, %s, %s, %s, TRUE, NOW()) "
            "ON CONFLICT (tenant_id, signer_id) DO UPDATE SET display_name = EXCLUDED.display_name, "
            "external_user_id = COALESCE(EXCLUDED.external_user_id, signers.external_user_id), is_active = TRUE",
            (TENANT, sid, name, ext))
    for sid, note in RETIRE.items():
        _execute("UPDATE signers SET is_active = FALSE, note = %s WHERE tenant_id = %s AND signer_id = %s",
                 (note, TENANT, sid))
    for old, new in ALIASES.items():
        _execute(
            "INSERT INTO signer_aliases (tenant_id, old_signer_id, new_signer_id, reason, merged_at) "
            "VALUES (%s, %s, %s, %s, NOW()) ON CONFLICT DO NOTHING",
            (TENANT, old, new, "tai khoan thu da xoa; gop ve nguoi ky theo ten"))
    # 2. mẫu (DB) — một câu cho mỗi đích
    by_new = {}
    for uid, (_, new, _) in plan.items():
        by_new.setdefault(new, []).append(uid)
    for new, uids in by_new.items():
        _execute("UPDATE samples SET signer_id = %s WHERE sample_uid = ANY(%s)", (new, uids))
print("DB: đã ghi", len(plan), "mẫu,", len(MAP), "người ký,", len(RETIRE), "ngưng hoạt động")

# --- 3. samples.csv ---------------------------------------------------------
p = DATASET / "samples.csv"
raw = p.read_bytes(); crlf = b"\r\n" in raw
text = raw.decode("utf-8").replace("\r\n", "\n")
reader = csv.DictReader(io.StringIO(text)); fields = reader.fieldnames; csv_rows = list(reader)
n = 0
for r in csv_rows:
    if r["sample_uid"] in plan:
        r["signer_id"] = plan[r["sample_uid"]][1]; n += 1
buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\r\n" if crlf else "\n")
w.writeheader(); w.writerows(csv_rows); p.write_bytes(buf.getvalue().encode("utf-8"))
print("samples.csv: đã ghi", n, "dòng")

# --- 4. sidecar --------------------------------------------------------------
m = 0
for uid, (_, new, fp) in plan.items():
    sc = (DATASET / (fp or "").replace("\\", "/").replace("/dataset/", "", 1).lstrip("/")).with_suffix(".json")
    if sc.exists():
        try:
            d = json.loads(sc.read_text(encoding="utf-8"))
            if d.get("signer_id") != new:
                d["signer_id"] = new
                sc.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8"); m += 1
        except Exception as exc:
            print("  sidecar lỗi", sc, exc)
print("sidecar: đã ghi", m)

# --- 5. signers.csv ----------------------------------------------------------
p = DATASET / "signers.csv"
old = {r["signer_id"]: r for r in csv.DictReader(open(p, encoding="utf-8"))}
for sid, (name, ext, _) in MAP.items():
    r = old.get(sid) or {"signer_id": sid, "created_at": NOW, "regional_group": ""}
    r.update({"display_name": name, "external_user_id": ext or r.get("external_user_id", ""), "is_active": "1"})
    old[sid] = r
for sid in RETIRE:
    if sid in old:
        old[sid]["is_active"] = "0"
with open(p, "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["signer_id", "display_name", "regional_group", "external_user_id", "is_active", "created_at"])
    w.writeheader()
    for sid in sorted(old): w.writerow({k: old[sid].get(k, "") for k in w.fieldnames})
print("signers.csv: đã ghi", len(old), "người ký — XONG")
