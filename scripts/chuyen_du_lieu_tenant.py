"""Chuyển trọn dữ liệu của MỘT người thu từ tenant nguồn sang tenant đích.

Chạy TRONG container backend (cần mã app + /dataset):

    docker exec -i voya_backend python /workspace/scripts/chuyen_du_lieu_tenant.py \
        --source default --target truong-chuyen-biet-soc-trang-a9690c \
        --classes 246947e9-...,8d76181c-... --signer S105 --move-dialect gdcbst \
        --actor superadmin            # mặc định CHẠY THỬ; thêm --apply để ghi

Vì sao là script chứ không phải endpoint: app chưa có đường chuyển xuyên tenant
(`sync_reassign_sample` chỉ cùng tenant), và lần này là một lần sửa dữ liệu bị
tạo nhầm tenant (17/09/2026), không phải một tính năng.

Mặt phẳng phải đi cùng nhau, theo đúng thứ tự `sync_reassign_sample` dùng:
khoá catalog -> sao lưu -> chép tệp sang chỗ mới (kiểm sha256) -> MỘT transaction
DB -> ghi CSV -> bỏ tệp cũ -> Drive (đẩy bản mới, xoá bản cũ) -> kiểm toán.
Hỏng trước khi commit DB: xoá bản chép, không đổi gì. Hỏng sau commit: dừng to,
in đường dẫn bản sao lưu để khôi phục tay.

Vì sao DB phải tháo/gắn lại hai khoá: khoá ghép theo tenant làm hai lượt
`ON UPDATE CASCADE` (từ `classes` và từ `signers`) cùng kéo `samples` mà mỗi lượt
lại đòi dòng kia đã ở tenant đích. Nên: tạm bỏ `samples.signer_id` và
`capture_sessions.collection_session_id`, dời người ký + phiên thu thập + lớp,
rồi gắn lại — tất cả trong một transaction, không ai thấy trạng thái giữa chừng.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app")

from app import audit  # noqa: E402
from app.catalog_sync import _catalog_lock, _write_csv, _write_samples_csv  # noqa: E402
from app.dataset_manager import DATASET_ROOT, MASTER_LABELS, tenant_features_root  # noqa: E402
from app.dataset_samples import SAMPLES_CSV, raw_archive_path  # noqa: E402
from app.storage.metadata_db import _cursor, _fetch_all  # noqa: E402
from app.tenant_context import system_scope, tenant_scope  # noqa: E402

ROOT = Path(DATASET_ROOT)


class Abort(RuntimeError):
    pass


def sha(path: Path) -> str:
    with path.open("rb") as s:
        return hashlib.file_digest(s, "sha256").hexdigest()


def read_csv(path: Path):
    import csv

    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def inventory(a):
    """Everything that moves, plus the checks that make the move safe."""
    src, dst, classes = a.source, a.target, a.classes
    with system_scope("chuyen tenant: kiem ke"):
        tgt = _fetch_all("SELECT tenant_id, is_active, deleted_at FROM tenants WHERE tenant_id = %s", (dst,))
        if not tgt or not tgt[0]["is_active"] or tgt[0]["deleted_at"]:
            raise Abort(f"tenant dich {dst} khong ton tai hoac khong hoat dong")
        cls = _fetch_all("SELECT * FROM classes WHERE tenant_id = %s AND class_uid = ANY(%s)", (src, classes))
        if len(cls) != len(classes):
            raise Abort("co lop khong thuoc tenant nguon")
        samples = _fetch_all("SELECT * FROM samples WHERE tenant_id = %s AND class_uid = ANY(%s)", (src, classes))
        foreign = [s["sample_uid"] for s in samples if s["signer_id"] not in (a.signer, None)]
        if foreign:
            raise Abort(f"lop co mau cua nguoi ky khac, khong chuyen nguyen lop duoc: {foreign}")
        stray = _fetch_all("SELECT sample_uid FROM samples WHERE signer_id = %s AND NOT (class_uid = ANY(%s))",
                           (a.signer, classes))
        if stray:
            raise Abort(f"nguoi ky {a.signer} con mau ngoai cac lop chuyen: {[r['sample_uid'] for r in stray]}")
        cs_ids = sorted({str(s["capture_session_id"]) for s in samples if s["capture_session_id"]})
        caps = _fetch_all("SELECT * FROM capture_sessions WHERE capture_session_id::text = ANY(%s)", (cs_ids,))
        mixed = _fetch_all("SELECT capture_session_id FROM samples WHERE capture_session_id::text = ANY(%s) "
                           "AND NOT (class_uid = ANY(%s))", (cs_ids, classes))
        if mixed:
            raise Abort("phien thu chua mau ngoai cac lop chuyen")
        col_ids = sorted({str(c["collection_session_id"]) for c in caps if c["collection_session_id"]})
        shared = _fetch_all("SELECT capture_session_id FROM capture_sessions WHERE collection_session_id::text = ANY(%s) "
                            "AND NOT (capture_session_id::text = ANY(%s))", (col_ids, cs_ids))
        if shared:
            raise Abort("phien thu thap dung chung voi phien thu khong chuyen")
        dialects = sorted({c["dialect"] for c in cls})
        have = {r["dialect_id"] for r in _fetch_all("SELECT dialect_id FROM dialects WHERE tenant_id = %s", (dst,))}
        missing = [d for d in dialects if d not in have and d != a.move_dialect]
        if missing:
            raise Abort(f"tenant dich thieu phuong ngu {missing}")
        profiles = {c["recognition_profile"] for c in cls if c["recognition_profile"]}
        have_p = {r["profile_id"] for r in _fetch_all("SELECT profile_id FROM recognition_profiles WHERE tenant_id = %s", (dst,))}
        if profiles - have_p:
            raise Abort(f"tenant dich thieu recognition profile {sorted(profiles - have_p)}")
        groups = sorted({c["vocabulary_group"] for c in cls if c["vocabulary_group"]})
    return {"classes": cls, "samples": samples, "caps": caps, "cs_ids": cs_ids,
            "col_ids": col_ids, "groups": groups}


def new_rel(old_rel: str, dst: str) -> str:
    """features/<lang>/<dialect>/<folder>/<file> -> layout of the target tenant."""
    parts = Path(old_rel).parts
    if parts[0] != "features" or "_tenants" in parts:
        raise Abort(f"duong dan khong theo bo cuc tenant khoi tao: {old_rel}")
    return (tenant_features_root(dst) / Path(*parts[1:])).relative_to(ROOT).as_posix()


def file_plan(inv, dst):
    """[(old, new)] for every npz, sidecar, class metadata.json and raw copy."""
    pairs, seen_dirs = [], set()
    for s in inv["samples"]:
        old = ROOT / s["file_path"]
        new = ROOT / new_rel(s["file_path"], dst)
        pairs.append((old, new))
        pairs.append((old.with_suffix(".json"), new.with_suffix(".json")))
        pairs.append((raw_archive_path(old), raw_archive_path(new)))
        if old.parent not in seen_dirs:
            seen_dirs.add(old.parent)
            pairs.append((old.parent / "metadata.json", new.parent / "metadata.json"))
    pairs = [(o, n) for o, n in pairs if o.exists()]
    clash = [str(n) for _, n in pairs if n.exists()]
    if clash:
        raise Abort(f"cho moi da co tep: {clash[:3]}")
    return pairs


def db_move(cur, a, inv):
    """One transaction. Order matters — see the module docstring."""
    src, dst, classes, signer = a.source, a.target, a.classes, a.signer
    uids = [s["sample_uid"] for s in inv["samples"]]
    if a.move_dialect:
        cur.execute(
            "INSERT INTO dialects (tenant_id, dialect_id, display_name, language, is_alphabet, is_active, "
            "  status, note, created_by, created_at, approved_by, approved_at, display_order) "
            "SELECT %s, dialect_id, display_name, language, is_alphabet, is_active, status, note, created_by, "
            "  created_at, approved_by, approved_at, display_order FROM dialects WHERE tenant_id = %s AND dialect_id = %s "
            "ON CONFLICT (tenant_id, dialect_id) DO NOTHING", (dst, src, a.move_dialect))
        if a.approve_dialect:
            # A pending dialect is visible to its creator only; the samples under
            # it were already accepted, so the tenant gets it approved.
            cur.execute(
                "UPDATE dialects SET status = 'approved', approved_at = NOW(), "
                "  approved_by = (SELECT id FROM users WHERE username = %s) "
                "WHERE tenant_id = %s AND dialect_id = %s AND status = 'pending'",
                (a.actor, dst, a.move_dialect))
    for g in inv["groups"]:
        cur.execute(
            "INSERT INTO vocabulary_groups (tenant_id, group_id, display_name, display_order, is_active) "
            "SELECT %s, group_id, display_name, display_order, is_active FROM vocabulary_groups "
            "WHERE tenant_id = %s AND group_id = %s ON CONFLICT DO NOTHING", (dst, src, g))
    # Detach the two links whose CASCADE paths would fight each other.
    cur.execute("UPDATE samples SET signer_id = NULL WHERE sample_uid = ANY(%s)", (uids,))
    cur.execute("UPDATE capture_sessions SET collection_session_id = NULL WHERE capture_session_id::text = ANY(%s)",
                (inv["cs_ids"],))
    cur.execute("UPDATE signers SET tenant_id = %s WHERE signer_id = %s AND tenant_id = %s", (dst, signer, src))
    if cur.rowcount != 1:
        raise Abort(f"khong doi duoc tenant cua nguoi ky {signer}")
    cur.execute("UPDATE collection_sessions SET tenant_id = %s WHERE collection_session_id::text = ANY(%s)",
                (dst, inv["col_ids"]))
    # Cascades to samples + capture_sessions via the composite (tenant_id, class_uid) keys.
    cur.execute("UPDATE classes SET tenant_id = %s WHERE tenant_id = %s AND class_uid = ANY(%s)", (dst, src, classes))
    if cur.rowcount != len(classes):
        raise Abort("khong doi duoc tenant cua du lop")
    for s in inv["samples"]:
        rel = new_rel(s["file_path"], dst)
        key = new_rel(s["storage_key"], dst) if (s["storage_key"] or "").startswith("features/") else s["storage_key"]
        cur.execute("UPDATE samples SET signer_id = %s, file_path = %s, storage_key = %s "
                    "WHERE sample_uid = %s AND tenant_id = %s", (signer, rel, key, s["sample_uid"], dst))
        if cur.rowcount != 1:
            raise Abort(f"mau {s['sample_uid']} khong theo lop sang tenant dich")
    for c in inv["caps"]:
        cur.execute("UPDATE capture_sessions SET collection_session_id = %s WHERE capture_session_id = %s "
                    "AND tenant_id = %s", (c["collection_session_id"], c["capture_session_id"], dst))
    if a.move_dialect:
        cur.execute("SELECT count(*) FROM classes WHERE tenant_id = %s AND dialect = %s", (src, a.move_dialect))
        if cur.fetchone()[0] == 0:
            cur.execute("DELETE FROM dialects WHERE tenant_id = %s AND dialect_id = %s", (src, a.move_dialect))
    # Post-conditions, inside the same transaction.
    cur.execute("SELECT count(*) FROM samples WHERE sample_uid = ANY(%s) AND tenant_id = %s "
                "AND signer_id = %s", (uids, dst, signer))
    if cur.fetchone()[0] != len(uids):
        raise Abort("hau dieu kien: khong du mau o tenant dich")
    cur.execute("SELECT count(*) FROM samples WHERE tenant_id = %s AND (class_uid = ANY(%s) OR signer_id = %s)",
                (src, classes, signer))
    if cur.fetchone()[0] != 0:
        raise Abort("hau dieu kien: tenant nguon con sot du lieu")


def csv_move(a, inv, uids_rel):
    lab_fields, labels = read_csv(MASTER_LABELS)
    n = 0
    for r in labels:
        if r.get("class_uid") in a.classes:
            r["tenant_id"] = a.target
            n += 1
    if n != len(a.classes):
        raise Abort(f"labels.csv: tim thay {n}/{len(a.classes)} lop")
    _, samples = read_csv(SAMPLES_CSV)
    m = 0
    for r in samples:
        new = uids_rel.get(r.get("sample_uid"))
        if new:
            r["tenant_id"] = a.target
            r["file_path"] = new["file_path"]
            if r.get("storage_key", "").startswith("features/"):
                r["storage_key"] = new["storage_key"]
            m += 1
    if m != len(uids_rel):
        raise Abort(f"samples.csv: tim thay {m}/{len(uids_rel)} mau")
    _write_csv(MASTER_LABELS, lab_fields, labels)
    _write_samples_csv(samples)
    return n, m


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--classes", required=True, type=lambda s: [x.strip() for x in s.split(",") if x.strip()])
    p.add_argument("--signer", required=True)
    p.add_argument("--move-dialect", default="")
    p.add_argument("--approve-dialect", action="store_true",
                   help="Approve the moved dialect in the target tenant")
    p.add_argument("--actor", required=True)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()

    inv = inventory(a)
    pairs = file_plan(inv, a.target)
    print(f"Lop: {len(inv['classes'])}  mau: {len(inv['samples'])}  phien thu: {len(inv['caps'])}  "
          f"phien thu thap: {len(inv['col_ids'])}  nhom tu vung can chep: {inv['groups']}  tep: {len(pairs)}")
    for o, n in pairs:
        print(f"  {o.relative_to(ROOT).as_posix()}  ->  {n.relative_to(ROOT).as_posix()}")

    if not a.apply:
        with system_scope("chuyen tenant: chay thu (ROLLBACK)"):
            try:
                with _cursor() as cur:
                    db_move(cur, a, inv)
                    raise Abort("__dry_run__")
            except Abort as exc:
                if str(exc) != "__dry_run__":
                    raise
        print("CHAY THU: phan DB qua het rang buoc va hau dieu kien, da ROLLBACK. Chua ghi gi.")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = ROOT / f"_backup_chuyen_tenant_{stamp}"
    uids_rel = {s["sample_uid"]: {"file_path": new_rel(s["file_path"], a.target),
                                  "storage_key": new_rel(s["storage_key"], a.target)
                                  if (s["storage_key"] or "").startswith("features/") else s["storage_key"]}
                for s in inv["samples"]}
    with _catalog_lock():
        for o, _ in pairs:
            dst = backup / o.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(o, dst)
        for f in (MASTER_LABELS, SAMPLES_CSV):
            shutil.copy2(f, backup / Path(f).name)
        print(f"Sao luu: {backup}")
        copied = []
        try:
            for o, n in pairs:
                n.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(o, n)
                copied.append(n)
                if sha(o) != sha(n):
                    raise Abort(f"sha256 khac sau khi chep: {n}")
            with system_scope(f"chuyen tenant {a.source}->{a.target} ({a.actor})"):
                with _cursor() as cur:
                    db_move(cur, a, inv)
        except Exception:
            for n in copied:
                n.unlink(missing_ok=True)
            print("THAT BAI truoc khi commit DB: da go ban chep, khong doi gi.", file=sys.stderr)
            raise
        try:
            labels_n, samples_n = csv_move(a, inv, uids_rel)
            for _, n in pairs:
                if n.suffix == ".json" and n.name.startswith("sample_"):
                    d = json.loads(n.read_text(encoding="utf-8"))
                    uid = n.stem.replace("sample_", "")
                    if uid in uids_rel and str(d.get("storage_key", "")).startswith("features/"):
                        d["storage_key"] = uids_rel[uid]["storage_key"]
                        n.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            for o, _ in pairs:
                o.unlink()
            for o, _ in pairs:
                for d in (o.parent, o.parent.parent):
                    if d.exists() and not any(d.iterdir()) and d != ROOT:
                        d.rmdir()
        except Exception:
            print(f"!!! DB DA COMMIT nhung CSV/tep loi. Khoi phuc tay tu {backup}", file=sys.stderr)
            raise
    print(f"Da chuyen: DB + labels.csv ({labels_n}) + samples.csv ({samples_n}) + {len(pairs)} tep.")

    # Drive: same pairing as sync_reassign_sample — re-upload, then delete the old copy.
    try:
        from app.export_tasks import delete_gdrive_files_task, upload_npz_to_gdrive_task

        for s in inv["samples"]:
            new = uids_rel[s["sample_uid"]]
            local = ROOT / new["file_path"]
            upload_npz_to_gdrive_task.delay(sample_uid=s["sample_uid"], local_path=str(local),
                                            storage_key=new["storage_key"],
                                            sidecar_path=str(local.with_suffix(".json")))
            if s["storage_key"] and s["storage_key"] != new["storage_key"]:
                delete_gdrive_files_task.delay(refs=[s["storage_key"]])
        print("Drive: da xep hang day ban moi + xoa ban cu.")
    except Exception as exc:
        print(f"CANH BAO Drive: {exc}", file=sys.stderr)

    with system_scope("chuyen tenant: kiem toan"):
        actor = _fetch_all("SELECT id, username, email FROM users WHERE username = %s", (a.actor,))[0]
        audit.record("tenant.data_moved", actor={"id": str(actor["id"]), "username": actor["username"],
                                                  "email": actor["email"]},
                     target_type="tenant", target_id=a.target, tenant_id=a.target,
                     detail={"from": a.source, "classes": a.classes, "signer": a.signer,
                             "samples": [s["sample_uid"] for s in inv["samples"]],
                             "dialect_moved": a.move_dialect or None, "backup": str(backup)})
    from app import vocabulary_registry as vr
    for t in (a.source, a.target):
        with tenant_scope(t):
            print(f"Registry {t}: v{vr._bump(t, note='chuyen du lieu giua tenant')}")


if __name__ == "__main__":
    try:
        main()
    except Abort as exc:
        print(f"DUNG: {exc}", file=sys.stderr)
        sys.exit(2)
