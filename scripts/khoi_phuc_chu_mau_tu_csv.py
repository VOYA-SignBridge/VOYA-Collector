"""Ghi lại `auth_user_id` (chủ mẫu) từ `dataset/samples.csv` vào Postgres.

Vì sao cần: `sot-init` chạy ở mỗi `docker compose up` và upsert bảng `samples`
từ gói SOT đã ký (Ver5_06082026). `ON CONFLICT ... auth_user_id =
COALESCE(EXCLUDED.auth_user_id, samples.auth_user_id)` nên giá trị CŨ trong gói
đè lên giá trị mới ở DB — 1.294 mẫu vừa được gán lại chủ ngày 15/09 quay về tên
chủ cũ sau lượt dựng ảnh. CSV (nguồn sự thật) vẫn đúng; script này đồng bộ DB
theo CSV rồi việc tiếp theo là publish một gói SOT mới từ DB.

Tài khoản đã xoá (Minh123/Minh1234) còn trong CSV → đặt trống ở cả hai nơi.
Chạy trong container backend:  python /tmp/o.py [--apply]
"""
import csv
import io
import sys

sys.path.insert(0, "/app")
from app.storage.metadata_db import _execute, _fetch_all  # noqa: E402
from app.tenant_context import system_scope  # noqa: E402

CSV = "/dataset/samples.csv"
APPLY = "--apply" in sys.argv

raw = open(CSV, "rb").read()
crlf = b"\r\n" in raw
reader = csv.DictReader(io.StringIO(raw.decode("utf-8").replace("\r\n", "\n")))
fields = reader.fieldnames
rows = list(reader)
by_uid = {r["sample_uid"]: r for r in rows}

with system_scope("khoi phuc chu mau tu csv"):
    users = {r["id"] for r in _fetch_all("SELECT id::text AS id FROM users")}
    db = _fetch_all("SELECT sample_uid, auth_user_id::text AS a, signer_id FROM samples")
    fix_owner, fix_signer, csv_touched = {}, {}, 0
    for r in db:
        c = by_uid.get(r["sample_uid"])
        if not c:
            continue
        want = c.get("auth_user_id") or None
        if want and want not in users:
            want = None
            c["auth_user_id"] = ""
            csv_touched += 1
        if (r["a"] or None) != want:
            fix_owner.setdefault(want, []).append(r["sample_uid"])
        ws = c.get("signer_id") or None
        if (r["signer_id"] or None) != ws:
            fix_signer.setdefault(ws, []).append(r["sample_uid"])
    print("owner lệch:", sum(len(v) for v in fix_owner.values()),
          "| signer lệch:", sum(len(v) for v in fix_signer.values()),
          "| dòng CSV trỏ tài khoản đã xoá:", csv_touched)
    if not APPLY:
        print("(xem trước; thêm --apply để ghi)")
        sys.exit(0)
    for want, uids in fix_owner.items():
        _execute("UPDATE samples SET auth_user_id = %s WHERE sample_uid = ANY(%s)", (want, uids))
    for ws, uids in fix_signer.items():
        _execute("UPDATE samples SET signer_id = %s WHERE sample_uid = ANY(%s)", (ws, uids))
    print("đã ghi DB")

if csv_touched:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\r\n" if crlf else "\n")
    w.writeheader()
    w.writerows(rows)
    open(CSV, "wb").write(buf.getvalue().encode("utf-8"))
    print("đã ghi CSV")
