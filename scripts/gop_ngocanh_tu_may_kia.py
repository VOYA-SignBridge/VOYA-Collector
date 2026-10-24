"""Hợp nhất chỉ-điền từ máy CTU (dump 15/09/2026, nhánh deploy_ctu_ver1.2.0):

  * 3 tài khoản chỉ máy kia có — ngocanh, "Thu Ngân", Trâm — chép NGUYÊN HÀNG
    (cùng id, email, mật khẩu băm, ngày tạo), vào cộng đồng với vai
    community_member như mọi tài khoản mới.
  * người ký S017 "Ngọc Anh" gắn tài khoản ngocanh; S003 Trâm gắn tài khoản Trâm.
  * 133 mẫu bảng chữ cái của ngocanh (camera, 01/08): chép npz + sidecar vào
    dataset/features, thêm hàng vào samples.csv và Postgres. Lớp `Q` bên kia
    mang class_uid khác → ánh xạ về Q của máy này. review_status = approved
    (dữ liệu được chủ dự án duyệt đưa vào ngày 15/09/2026).
  * 10 mẫu `testdata` bên kia: KHÔNG lấy.

Sau script: publish SOT (python -m app.sot.cli publish) để compose-up không lùi.
Chạy trong container backend với OTHER_DSN trỏ tới other_signdb:
    python /tmp/gop.py [--apply]
"""
import csv, io, json, os, shutil, sys
from pathlib import Path

sys.path.insert(0, "/app")
import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402
from app.storage.metadata_db import _execute, _fetch_all, upsert_sample  # noqa: E402
from app.modules.saas.tenant_context import system_scope  # noqa: E402

APPLY = "--apply" in sys.argv
OTHER = psycopg2.connect(os.environ["OTHER_DSN"])
SRC = Path("/workspace/Voya_dump/ngocanh_npz/features")
DATASET = Path("/dataset")
TENANT = "default"
CLASS_MAP = {"795eec29-34d7-4b23-aba9-89cab7a5deec": "356d0732-cf18-4cfb-bded-5ac06d847a3e"}  # Q kia → Q đây
NEW_SIGNER = ("S017", "Ngọc Anh", "0e99b988-b1f0-4c89-a083-204caf10035d")
LINK_SIGNER = {"S003": "a46d61ee-f5f3-4007-b736-daca0fc9014e"}  # Trâm → tài khoản Trâm


def q(sql, args=()):
    with OTHER.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        return cur.fetchall()


# ---- 1. tài khoản -----------------------------------------------------------
users = q("SELECT id::text AS id, username, email, password_hash, is_active, created_at, phone_number "
          "FROM users WHERE username IN ('ngocanh', 'Thu Ngân', 'Trâm') ORDER BY created_at")
with system_scope("gop may kia: doc"):
    have = {r["username"] for r in _fetch_all("SELECT username FROM users")}
    have_email = {r["email"].lower() for r in _fetch_all("SELECT email FROM users")}
    local_classes = {r["class_uid"]: r for r in _fetch_all(
        "SELECT class_uid, slug, dialect, language, folder_name FROM classes WHERE deleted_at IS NULL")}
    have_samples = {r["sample_uid"] for r in _fetch_all("SELECT sample_uid FROM samples")}
to_create = [u for u in users if u["username"] not in have and u["email"].lower() not in have_email]
print("Tài khoản sẽ tạo:", [(u["username"], u["email"]) for u in to_create])

# ---- 2. mẫu -------------------------------------------------------------------
rows = q("SELECT * FROM samples WHERE user_id='ngocanh' AND dialect='bang-chu-cai' AND deleted_at IS NULL ORDER BY created_at")
plan, missing_file, bad_class = [], [], []
for r in rows:
    if r["sample_uid"] in have_samples:
        continue
    cu = CLASS_MAP.get(r["class_uid"], r["class_uid"])
    cls = local_classes.get(cu)
    if not cls:
        bad_class.append((r["sample_uid"], r["class_uid"], r["label_original"]))
        continue
    rel = (r["file_path"] or "").replace("\\", "/").replace("/dataset/", "", 1).lstrip("/")
    src = SRC / rel.replace("features/", "", 1)
    if not src.exists():
        missing_file.append(rel)
        continue
    folder = cls["folder_name"] or Path(rel).parent.name
    new_rel = f"features/{cls['language']}/{cls['dialect']}/{folder}/{Path(rel).name}"
    plan.append((r, cu, cls, src, new_rel))
print(f"Mẫu: {len(rows)} bên kia, {len(plan)} sẽ thêm, {len(missing_file)} thiếu tệp, {len(bad_class)} không có lớp")
if bad_class:
    print("  không có lớp:", bad_class[:5])
lop = {}
for _, cu, cls, _, _ in plan:
    lop[cls["slug"]] = lop.get(cls["slug"], 0) + 1
print("  theo lớp:", dict(sorted(lop.items())))

if not APPLY:
    print("(xem trước; thêm --apply để ghi)")
    sys.exit(0)

# ---- ghi: tài khoản ------------------------------------------------------------
from app.modules.saas.tenant_admin import join_community  # noqa: E402

with system_scope("gop may kia: tai khoan"):
    for u in to_create:
        _execute(
            "INSERT INTO users (id, username, email, password_hash, is_active, is_admin, created_at, phone_number, tenant_id) "
            "VALUES (%s, %s, %s, %s, %s, FALSE, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (u["id"], u["username"], u["email"], u["password_hash"], bool(u["is_active"]),
             u["created_at"], u["phone_number"] or None, TENANT))
for u in to_create:
    join_community(u["id"])
print("đã tạo", len(to_create), "tài khoản (cộng đồng, vai community_member)")

# ---- ghi: người ký ---------------------------------------------------------------
with system_scope("gop may kia: nguoi ky"):
    sid, name, ext = NEW_SIGNER
    _execute("INSERT INTO signers (tenant_id, signer_id, display_name, external_user_id, is_active, created_at) "
             "VALUES (%s, %s, %s, %s, TRUE, NOW()) ON CONFLICT (tenant_id, signer_id) DO UPDATE SET "
             "display_name = EXCLUDED.display_name, external_user_id = EXCLUDED.external_user_id, is_active = TRUE",
             (TENANT, sid, name, ext))
    for s, ext in LINK_SIGNER.items():
        _execute("UPDATE signers SET external_user_id = %s WHERE tenant_id = %s AND signer_id = %s", (ext, TENANT, s))

# ---- ghi: tệp + CSV + DB ---------------------------------------------------------
from app.modules.dataset.samples import _samples_fieldnames, SAMPLES_CSV  # noqa: E402
from filelock import FileLock  # noqa: E402

csv_rows, n_files = [], 0
for r, cu, cls, src, new_rel in plan:
    dst = DATASET / new_rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    side_src = src.with_suffix(".json")
    side = {}
    if side_src.exists():
        side = json.loads(side_src.read_text(encoding="utf-8"))
    side.update({"class_uid": cu, "slug": cls["slug"], "signer_id": NEW_SIGNER[0], "tenant_id": TENANT,
                 "auth_user_id": NEW_SIGNER[2], "review_status": "approved"})
    dst.with_suffix(".json").write_text(json.dumps(side, ensure_ascii=False, indent=2), encoding="utf-8")
    n_files += 1
    row = {
        "sample_uid": r["sample_uid"], "class_uid": cu, "slug": cls["slug"], "label_original": r["label_original"],
        "language": cls["language"], "dialect": cls["dialect"], "source_type": r["source_type"] or "camera",
        "user_id": r["user_id"], "session_id": r["session_id"] or "",
        "fps_original": r["fps_original"] or "", "fps_processed": r["fps_processed"] or "",
        "seq_len": r["seq_len"] or "", "augment_id": r["augment_id"] or 0, "completeness": r["completeness"] or "",
        "file_path": new_rel, "storage_key": new_rel, "storage_url": r["storage_url"] or "",
        "checksum": r["checksum"] or "", "created_at": r["created_at"].isoformat() if r["created_at"] else "",
        "left_hand_ratio": r["left_hand_ratio"] or "", "right_hand_ratio": r["right_hand_ratio"] or "",
        "both_hands_ratio": r["both_hands_ratio"] or "", "jitter": r["jitter"] or "", "quality_flags": r["quality_flags"] or "",
        "signer_id": NEW_SIGNER[0], "auth_user_id": NEW_SIGNER[2], "tenant_id": TENANT, "review_status": "approved",
    }
    csv_rows.append(row)

fields = _samples_fieldnames()
raw = SAMPLES_CSV.read_bytes(); crlf = b"\r\n" in raw
with FileLock(str(SAMPLES_CSV) + ".lock"):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore", restval="", lineterminator="\r\n" if crlf else "\n")
    for row in csv_rows:
        w.writerow(row)
    with open(SAMPLES_CSV, "ab") as fh:
        fh.write(buf.getvalue().encode("utf-8"))
with system_scope("gop may kia: mau"):
    for row in csv_rows:
        upsert_sample(row)
print(f"đã chép {n_files} npz+sidecar, thêm {len(csv_rows)} dòng samples.csv và Postgres — XONG")
