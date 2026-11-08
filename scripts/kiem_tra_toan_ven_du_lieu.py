"""Kiểm tra toàn vẹn dữ liệu máy này: tệp trên đĩa ↔ CSV ↔ Postgres ↔ sidecar.

Chỉ ĐỌC. In từng mục với số lệch; mã thoát 1 nếu có lệch nghiêm trọng.
Chạy trong container backend:  python /tmp/k.py
"""
import csv, io, json, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/app")
from app.storage.metadata_db import _fetch_all  # noqa: E402
from app.modules.saas.tenant_context import system_scope  # noqa: E402

DATASET = Path("/dataset"); WS = Path("/workspace")
bad = 0


def rd(p):
    return list(csv.DictReader(io.StringIO(p.read_bytes().decode("utf-8-sig").replace("\r\n", "\n"))))


def rel_of(fp):
    return (fp or "").replace("\\", "/").replace("/dataset/", "", 1).lstrip("/")


def report(title, n, detail=""):
    global bad
    flag = "OK " if n == 0 else "LỆCH"
    if n: bad += 1
    print(f"  [{flag}] {title}: {n} {detail}")


# ---------------- MẪU ----------------
print("== MẪU ==")
csv_s = rd(DATASET / "samples.csv")
with system_scope("kiem tra: mau"):
    db_s = _fetch_all("SELECT sample_uid, class_uid, slug, dialect, language, user_id, signer_id, auth_user_id::text AS auth_user_id, "
                      "review_status, tenant_id, file_path, storage_url, storage_key, checksum, deleted_at FROM samples")
    db_c = _fetch_all("SELECT class_uid, slug, dialect, language, folder_name, class_idx, region, tenant_id, deleted_at FROM classes")
    signers = _fetch_all("SELECT signer_id, display_name, external_user_id::text AS ext, is_active FROM signers WHERE tenant_id='default'")
    users = {r["id"] for r in _fetch_all("SELECT id::text AS id FROM users")}
    raw = _fetch_all("SELECT upload_uid, local_path, status, deleted_at FROM raw_uploads")
    jobs = _fetch_all("SELECT job_id, status, checkpoint_path FROM training_jobs")
print(f"  samples.csv {len(csv_s)} | DB {len(db_s)} (sống {sum(1 for s in db_s if not s['deleted_at'])})")
c_by = {r["sample_uid"]: r for r in csv_s}; d_by = {r["sample_uid"]: r for r in db_s}
report("DB có, CSV không", len(set(d_by) - set(c_by)))
report("CSV có, DB không", len(set(c_by) - set(d_by)))
mism = Counter()
for uid in set(c_by) & set(d_by):
    c, d = c_by[uid], d_by[uid]
    for f in ("class_uid", "slug", "dialect", "signer_id", "auth_user_id", "review_status", "tenant_id", "storage_key"):
        if (c.get(f) or "") != (d.get(f) or ""):
            mism[f] += 1
    if rel_of(c["file_path"]) != rel_of(d["file_path"]): mism["file_path"] += 1
report("CSV ↔ DB lệch trường", sum(mism.values()), dict(mism))
no_npz, no_side, side_mism, npz_keys = [], [], Counter(), Counter()
for r in csv_s:
    p = DATASET / rel_of(r["file_path"])
    if not p.exists(): no_npz.append(r["sample_uid"]); continue
    sc = p.with_suffix(".json")
    if not sc.exists(): no_side.append(r["sample_uid"]); continue
    try:
        d = json.loads(sc.read_text(encoding="utf-8"))
    except Exception:
        side_mism["json hỏng"] += 1; continue
    for f in ("class_uid", "signer_id", "auth_user_id", "review_status"):
        if str(d.get(f) or "") != (r.get(f) or ""): side_mism[f] += 1
report("dòng CSV thiếu npz trên đĩa", len(no_npz))
report("dòng CSV thiếu sidecar", len(no_side))
report("sidecar ↔ CSV lệch trường", sum(side_mism.values()), dict(side_mism))
report("mẫu trỏ tài khoản không tồn tại", sum(1 for r in csv_s if r.get("auth_user_id") and r["auth_user_id"] not in users))
report("mẫu trỏ người ký không có trong sổ", sum(1 for r in csv_s if r.get("signer_id") and r["signer_id"] not in {s["signer_id"] for s in signers}))
alive_cls = {c["class_uid"] for c in db_c if not c["deleted_at"]}
report("mẫu trỏ lớp không tồn tại / đã xoá", sum(1 for r in csv_s if r["class_uid"] not in alive_cls))
report("mẫu không có Drive storage_url", sum(1 for r in csv_s if not (r.get("storage_url") or "").strip()), "(chỉ thông tin)") if False else None
print(f"  (thông tin) mẫu chưa có chủ: {sum(1 for r in csv_s if not r.get('auth_user_id'))}; chưa lên Drive: {sum(1 for r in csv_s if not (r.get('storage_url') or '').strip())}")
in_csv = {rel_of(r["file_path"]) for r in csv_s}
orphans = [str(p.relative_to(DATASET)) for p in (DATASET / "features").rglob("*.npz") if str(p.relative_to(DATASET)).replace("\\", "/") not in in_csv]
report("npz mồ côi trên đĩa", len(orphans), orphans[:3])

# ---------------- LỚP ----------------
print("== LỚP ==")
csv_c = rd(DATASET / "labels.csv")
print(f"  labels.csv {len(csv_c)} | DB {len(db_c)} (sống {len(alive_cls)})")
lc = {c["class_uid"] for c in csv_c}
report("DB có (sống), labels.csv không", len({c["class_uid"] for c in db_c if not c["deleted_at"]} - lc))
print(f"  (thông tin) lớp trong thùng rác (ẩn khỏi labels.csv theo thiết kế): {sum(1 for c in db_c if c['deleted_at'])}")
report("labels.csv có, DB không", len(lc - {c["class_uid"] for c in db_c}))
cm = Counter()
dbc_by = {c["class_uid"]: c for c in db_c}
for c in csv_c:
    d = dbc_by.get(c["class_uid"])
    if not d: continue
    for f in ("slug", "dialect", "language", "folder_name", "region", "tenant_id"):
        if (c.get(f) or "") != (d.get(f) or ""): cm[f] += 1
    if str(c.get("class_idx") or "") != str(d.get("class_idx") or ""): cm["class_idx"] += 1
report("labels.csv ↔ DB lệch trường", sum(cm.values()), dict(cm))
no_dir = [f"{c['dialect']}/{c['slug']}" for c in db_c if not c["deleted_at"] and not (DATASET / "features" / c["language"] / c["dialect"] / c["folder_name"]).exists()]
n_samples = Counter(r["class_uid"] for r in csv_s)
print(f"  (thông tin) lớp sống chưa có thư mục features (0 mẫu): {len(no_dir)} {no_dir}")
report("lớp có mẫu nhưng thiếu thư mục", sum(1 for c in db_c if n_samples.get(c["class_uid"]) and not (DATASET / "features" / c["language"] / c["dialect"] / c["folder_name"]).exists()))

# ---------------- NGƯỜI KÝ ----------------
print("== NGƯỜI KÝ ==")
sc = rd(DATASET / "signers.csv") if (DATASET / "signers.csv").exists() else []
print(f"  signers.csv {len(sc)} | DB {len(signers)} (hoạt động {sum(1 for s in signers if s['is_active'])})")
report("signers.csv ↔ DB khác tập signer_id", len({s['signer_id'] for s in sc} ^ {s['signer_id'] for s in signers}) if sc else 0)
report("người ký gắn tài khoản không tồn tại", sum(1 for s in signers if s["ext"] and s["ext"] not in users))
used = Counter(r["signer_id"] for r in csv_s)
print("  (thông tin) mẫu theo người ký:", {f"{s['signer_id']}({s['display_name']})": used.get(s["signer_id"], 0) for s in signers if s["is_active"]})

# ---------------- VIDEO THÔ / JOB / MÔ HÌNH ----------------
print("== VIDEO THÔ ==")
report("raw_uploads sống thiếu tệp", sum(1 for r in raw if not r["deleted_at"] and r["local_path"] and not Path(r["local_path"]).exists()),
       [r["local_path"] for r in raw if not r["deleted_at"] and r["local_path"] and not Path(r["local_path"]).exists()][:3])
print("== HUẤN LUYỆN ==")
comp = [j for j in jobs if j["status"] == "completed" and j["checkpoint_path"]]
miss_ck = [j["checkpoint_path"] for j in comp if not Path(j["checkpoint_path"]).exists()]
print(f"  job completed có checkpoint: {len(comp)}")
report("job completed thiếu tệp .pt", len(miss_ck), [Path(p).name for p in miss_ck])
print("== REALTIME ==")
mj = WS / "backend" / "realtime_service" / "config" / "models.json"
cfg = json.loads(mj.read_text(encoding="utf-8"))
ck_dir = mj.parent
missing = []
def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "checkpoint_path" and isinstance(v, str) and not (ck_dir / v).exists(): missing.append(v)
            walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
walk(cfg)
report("models.json trỏ checkpoint không có", len(missing), missing)
print("== SPLIT / MANIFEST / ĐỒNG THUẬN ==")
for f in ("consent_snapshot.json", "signers.csv", "vocabulary_registry.json"):
    print(f"  {'có ' if (DATASET / f).exists() else 'THIẾU'} dataset/{f}")
sp = WS / "processed" / "splits"
ops = sorted((sp / "operational").glob("*")) if (sp / "operational").exists() else []
print(f"  processed/splits: {len(list(sp.glob('*.csv')))} csv gốc, {len(ops)} split vận hành, {len(list((sp/'versions').glob('*'))) if (sp/'versions').exists() else 0} version nghiên cứu")
# tập chia trỏ file có tồn tại?
dangling = 0; checked = 0
for csvf in list(sp.rglob("*.csv"))[:60]:
    try:
        rows = rd(csvf)
    except Exception:
        continue
    col = next((c for c in ("file_path", "path", "npz_path") if rows and c in rows[0]), None)
    if not col: continue
    for r in rows[:200]:
        checked += 1
        p = r[col].replace("\\", "/")
        p2 = p.replace("/dataset/", "", 1).replace("/workspace/", "", 1).lstrip("/")
        if not ((DATASET / p2.replace("dataset/", "", 1)).exists() or (WS / p2).exists() or Path(p).exists()):
            dangling += 1
report(f"dòng split trỏ npz không tồn tại (mẫu {checked} dòng)", dangling)
print("\nKẾT QUẢ:", "ĐẦY ĐỦ, KHÔNG LỆCH" if bad == 0 else f"{bad} mục lệch — xem trên")
sys.exit(1 if bad else 0)
