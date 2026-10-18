#!/usr/bin/env python3
"""Dời Google Drive sang bố cục Community/ + Tenants/<slug>/{Samples,Videos,Models}/.

Thiết kế: docs/02-data/DRIVE_STORAGE_AND_LOOKUP_LIST.md. Đích đọc từ
`app.storage.drive_layout` (không gõ lại tên thư mục ở đây).

Nguồn được nhận:
    tenants/<tenant_id>/{features,raw,raw_videos,models}/   bố cục tenant đời đầu
    features/…, features/_tenants/<id>/…, raw_videos/…, models/…   bố cục legacy ở gốc

Các bước (chạy khô thì chỉ in bảng kê, không đổi gì):
    1. làm sạch `tenants.slug` của tổ chức cũ mang hậu tố ngẫu nhiên (DB)
    2. gộp thư mục trùng tên cùng cha (vd. hai `class_giai-thich_246947e9`)
    3. đưa thư mục RỖNG vào Thùng rác
    4. dời từng cây sang đích bằng đổi cha — ID tệp giữ nguyên, nên mọi
       `storage_url` trong DB/CSV/sidecar vẫn đúng
    5. đưa gốc cũ đã rỗng vào Thùng rác
Cuối cùng báo các tệp KHÔNG được DB tham chiếu (chỉ báo, không xoá).

Mọi thứ bị bỏ đi vào Thùng rác Drive (khôi phục được), không xoá vĩnh viễn.
Chạy lại nhiều lần được. Trùng tên tệp ở đích -> báo xung đột, để yên.

Trước khi --apply: dừng voya_worker và voya_celery_beat (chúng ghi Drive), tắt
bộ ghi Drive ở các máy khác. Sau --apply: triển khai mã có bố cục mới.

    docker exec voya_backend python /workspace/scripts/drive_tenant_layout_migrate.py
    docker exec voya_backend python /workspace/scripts/drive_tenant_layout_migrate.py --apply
"""
from __future__ import annotations

import collections
import re
import sys

# Mã của repo (bố cục mới), không phải mã đã dựng trong ảnh.
sys.path.insert(0, "/workspace/backend")
from app.storage import drive_layout as dl  # noqa: E402
from app.storage.gdrive_client import FOLDER_MIME, get_gdrive_client  # noqa: E402
from app.storage.metadata_db import _execute, _fetch_all  # noqa: E402
from app.tenant_admin import TenantError, assert_tenant_name_free  # noqa: E402
from app.tenancy import DEFAULT_TENANT_ID, is_valid_tenant_id  # noqa: E402
from app.tenant_context import system_scope  # noqa: E402

APPLY = "--apply" in sys.argv
client = get_gdrive_client()
svc = client.service
stats = collections.Counter()
conflicts: list[str] = []


def ls(folder_id):
    out, tok = [], None
    while True:
        r = svc.files().list(q=f"'{folder_id}' in parents and trashed=false",
                             fields="nextPageToken, files(id,name,mimeType,createdTime)",
                             orderBy="createdTime", pageSize=1000, pageToken=tok).execute(num_retries=5)
        out += r.get("files", [])
        tok = r.get("nextPageToken")
        if not tok:
            return out


def is_folder(item):
    return item["mimeType"] == FOLDER_MIME


def child(parent_id, name):
    """Thư mục con CŨ NHẤT đúng tên (so từng ký tự: `tenants` khác `Tenants`)."""
    return next((k for k in ls(parent_id) if k["name"] == name and is_folder(k)), None)


def walk_files(folder_id, path):
    for k in ls(folder_id):
        p = f"{path}/{k['name']}"
        if is_folder(k):
            yield from walk_files(k["id"], p)
        else:
            yield p, k["id"]


def file_count(folder_id):
    return sum(1 for _ in walk_files(folder_id, ""))


def trash(item_id, label):
    print(f"  RAC   {label}")
    if APPLY:
        svc.files().update(fileId=item_id, body={"trashed": True}, fields="id").execute(num_retries=5)


def ensure_folder(path):
    """ID thư mục theo đường dẫn từ gốc Drive; chạy khô thì không tạo, trả None nếu chưa có."""
    parent = client.root_folder_id
    for part in path.split("/"):
        c = child(parent, part) if parent else None
        if c is None:
            if not APPLY:
                return None
            c = svc.files().create(body={"name": part, "mimeType": FOLDER_MIME, "parents": [parent]},
                                   fields="id,name,mimeType").execute(num_retries=5)
        parent = c["id"]
    return parent


def move_into(src, src_path, target_path):
    """Đưa cây `src` thành `target_path`. Đích chưa có -> đổi cha + đổi tên (1 lượt gọi).
    Đích đã có -> gộp từng con; trùng tên tệp -> xung đột, để yên."""
    parent_path, name = target_path.rsplit("/", 1)
    parent_id = ensure_folder(parent_path)
    existing = child(parent_id, name) if parent_id else None
    if existing is None:
        stats["tree_moves"] += 1
        print(f"  DOI   {src_path}  ->  {target_path}")
        if APPLY:
            cur = svc.files().get(fileId=src["id"], fields="parents").execute()
            svc.files().update(fileId=src["id"], body={"name": name}, addParents=parent_id,
                               removeParents=",".join(cur.get("parents", [])),
                               fields="id").execute(num_retries=5)
        return
    merge_children(src, src_path, existing, target_path)


def merge_children(src, src_path, dst, dst_path):
    for k in ls(src["id"]):
        sub_src, sub_dst = f"{src_path}/{k['name']}", f"{dst_path}/{k['name']}"
        twin = next((t for t in ls(dst["id"]) if t["name"] == k["name"]), None)
        if twin is None:
            stats["child_moves"] += 1
            print(f"  GOP   {sub_src}  ->  {sub_dst}")
            if APPLY:
                svc.files().update(fileId=k["id"], addParents=dst["id"],
                                   removeParents=src["id"], fields="id").execute(num_retries=5)
        elif is_folder(k) and is_folder(twin):
            merge_children(k, sub_src, twin, sub_dst)
        else:
            conflicts.append(f"{sub_src} (dich da co {sub_dst})")
    if APPLY and not ls(src["id"]):
        trash(src["id"], f"{src_path} (da gop het, rong)")


# --------------------------------------------------------------- 1. slug


def clean_slugs():
    print("\n== 1. SLUG CUA TO CHUC (ten thu muc tren Drive)")
    with system_scope("drive migrate: lam sach slug"):
        rows = _fetch_all("SELECT tenant_id, slug, display_name, tenant_type FROM tenants ORDER BY created_at")
    for r in rows:
        slug = r["slug"] or r["tenant_id"]
        if r["tenant_type"] == "COMMUNITY" or not re.search(r"-[0-9a-f]{6}$", slug):
            continue
        try:
            new = assert_tenant_name_free(r["display_name"] or "", ignore_tenant_id=r["tenant_id"])
        except TenantError as exc:
            print(f"  GIU   {r['tenant_id']}: {exc}")
            continue
        if new == slug or not is_valid_tenant_id(new):
            continue
        print(f"  SLUG  {r['tenant_id']}: {slug} -> {new}")
        stats["slugs"] += 1
        if APPLY:
            with system_scope("drive migrate: lam sach slug"):
                _execute("UPDATE tenants SET slug = %s WHERE tenant_id = %s", (new, r["tenant_id"]))
    dl.clear_tenant_root_cache()


def target_root(tenant_id):
    """Đích trên Drive của một tổ chức. Chạy khô thì slug chưa đổi trong DB, nên tự
    tính slug sạch để bảng kê cho đúng đích sẽ có."""
    root = dl.tenant_drive_root(tenant_id)
    if not APPLY and root.startswith(dl.TENANTS_ROOT + "/") and re.search(r"-[0-9a-f]{6}$", root):
        with system_scope("drive migrate: ten to chuc"):
            name = _fetch_all("SELECT display_name FROM tenants WHERE tenant_id = %s", (tenant_id,))[0]["display_name"]
        try:
            root = f"{dl.TENANTS_ROOT}/{assert_tenant_name_free(name or '', ignore_tenant_id=tenant_id)}"
        except TenantError:
            pass
    return root


# --------------------------------------------------------------- 2-3. trùng tên, rỗng


def dedupe_and_prune(folder, path):
    """Gộp thư mục con trùng tên (mới -> cũ nhất) rồi đưa thư mục rỗng vào Thùng rác.
    Trả về số tệp còn lại trong cây."""
    kids = ls(folder["id"])
    by_name = collections.defaultdict(list)
    for k in kids:
        if is_folder(k):
            by_name[k["name"]].append(k)
    for name, twins in by_name.items():
        for newer in twins[1:]:  # ls() xếp cũ trước
            stats["dupes"] += 1
            print(f"  TRUNG {path}/{name}  (gop ban tao {newer['createdTime'][:10]} vao ban {twins[0]['createdTime'][:10]})")
            merge_children(newer, f"{path}/{name}#moi", twins[0], f"{path}/{name}")
    total = 0
    for k in (ls(folder["id"]) if APPLY else kids):
        if not is_folder(k):
            total += 1
            continue
        n = dedupe_and_prune(k, f"{path}/{k['name']}")
        # Khung thư mục của tổ chức (Lookup list/, Samples/, Videos/, Models/,
        # Tenants/<slug>/) được tạo sẵn cả khi rỗng — không dọn.
        skeleton = (k["name"] in {dl.LOOKUP_LIST_DIRNAME, *dl.DRIVE_TREE_NAMES.values()}
                    or path == dl.TENANTS_ROOT)
        if n == 0 and not skeleton:
            stats["empty"] += 1
            trash(k["id"], f"{path}/{k['name']}/ (rong)")
        total += n
    return total


# --------------------------------------------------------------- 4. kế hoạch dời


def plan_moves(root):
    plan = []  # (src, src_path, target_path)

    old = root.get(dl.OLD_TENANTS_ROOT)
    if old:
        for t in ls(old["id"]):
            if not is_folder(t):
                continue
            if not is_valid_tenant_id(t["name"]):
                conflicts.append(f"{dl.OLD_TENANTS_ROOT}/{t['name']} (ma to chuc khong hop le)")
                continue
            tr = target_root(t["name"])
            for tree in ls(t["id"]):
                if tree["name"] not in dl.DRIVE_TREE_NAMES:
                    conflicts.append(f"{dl.OLD_TENANTS_ROOT}/{t['name']}/{tree['name']} (cay la)")
                    continue
                plan.append((tree, f"{dl.OLD_TENANTS_ROOT}/{t['name']}/{tree['name']}",
                             f"{tr}/{dl.DRIVE_TREE_NAMES[tree['name']]}"))

    community = target_root(DEFAULT_TENANT_ID)
    feats = root.get(dl.FEATURES_TREE)
    if feats:
        for k in ls(feats["id"]):
            if k["name"] == dl.PARTITION_DIRNAME:
                for t in ls(k["id"]):
                    plan.append((t, f"{dl.FEATURES_TREE}/{dl.PARTITION_DIRNAME}/{t['name']}",
                                 f"{target_root(t['name'])}/{dl.DRIVE_TREE_NAMES[dl.FEATURES_TREE]}"))
            else:
                plan.append((k, f"{dl.FEATURES_TREE}/{k['name']}",
                             f"{community}/{dl.DRIVE_TREE_NAMES[dl.FEATURES_TREE]}/{k['name']}"))

    # raw_videos/ và models/ ở gốc KHÔNG phân vùng: chỉ dời khi chắc chắn là của cộng đồng.
    with system_scope("drive migrate: chu so huu video tho va model"):
        raw_rows = _fetch_all("SELECT storage_url, tenant_id FROM raw_uploads")
        job_tenants = {r["tenant_id"] for r in _fetch_all(
            "SELECT DISTINCT tenant_id FROM training_jobs WHERE status = 'completed'")}
    owner_by_id = {m.group(1): r["tenant_id"] for r in raw_rows
                   if (m := re.search(r"/d/([\w-]+)", r.get("storage_url") or ""))}
    rv = root.get(dl.RAW_VIDEOS_TREE)
    if rv:
        owners = collections.Counter(owner_by_id.get(fid, "(khong co trong DB)")
                                     for _, fid in walk_files(rv["id"], dl.RAW_VIDEOS_TREE))
        if set(owners) <= {DEFAULT_TENANT_ID, "(khong co trong DB)"}:
            for k in ls(rv["id"]):
                plan.append((k, f"{dl.RAW_VIDEOS_TREE}/{k['name']}",
                             f"{community}/{dl.DRIVE_TREE_NAMES[dl.RAW_VIDEOS_TREE]}/{k['name']}"))
        else:
            conflicts.append(f"{dl.RAW_VIDEOS_TREE}/ co video cua to chuc khac: {dict(owners)} — DUNG")
    md = root.get(dl.MODELS_TREE)
    if md:
        if job_tenants <= {DEFAULT_TENANT_ID}:
            for k in ls(md["id"]):
                plan.append((k, f"{dl.MODELS_TREE}/{k['name']}",
                             f"{community}/{dl.DRIVE_TREE_NAMES[dl.MODELS_TREE]}/{k['name']}"))
        else:
            conflicts.append(f"{dl.MODELS_TREE}/ co mo hinh cua to chuc {sorted(job_tenants)} — DUNG")
    return plan


# --------------------------------------------------------------- báo cáo tệp mồ côi


def report_unreferenced():
    print("\n== TEP KHONG DUOC DB THAM CHIEU (chi bao, khong xoa)")
    with system_scope("drive migrate: tep duoc tham chieu"):
        urls = [r["u"] for r in _fetch_all(
            "SELECT storage_url AS u FROM samples WHERE storage_url IS NOT NULL "
            "UNION ALL SELECT storage_url FROM raw_uploads WHERE storage_url IS NOT NULL")]
    known = {m.group(1) for u in urls if (m := re.search(r"/d/([\w-]+)", u or ""))}
    roots = {k["name"]: k for k in ls(client.root_folder_id)}
    data_trees = {dl.DRIVE_TREE_NAMES[dl.FEATURES_TREE], dl.DRIVE_TREE_NAMES[dl.RAW_VIDEOS_TREE],
                  dl.FEATURES_TREE, dl.RAW_VIDEOS_TREE}
    found = []

    def scan(folder, path, depth):
        for k in ls(folder["id"]):
            p = f"{path}/{k['name']}"
            if depth == 0 and k["name"] in data_trees:
                found.extend((fp, fid) for fp, fid in walk_files(k["id"], p) if fid not in known)
            elif is_folder(k) and depth < 2:
                scan(k, p, depth + 1)
    for name in (dl.COMMUNITY_ROOT, dl.TENANTS_ROOT, dl.OLD_TENANTS_ROOT):
        if name in roots:
            scan(roots[name], name, 0 if name == dl.COMMUNITY_ROOT else -1)
    by_dir = collections.Counter(p.rsplit("/", 2)[0] for p, _ in found)
    print(f"  {len(found)} tep (DB tham chieu {len(known)} tep)")
    for d, n in by_dir.most_common(30):
        print(f"  {n:>6}  {d}/")


def main():
    print(("AP DUNG" if APPLY else "CHAY KHO (khong doi gi)") + " — goc Drive", client.root_folder_id)
    if dl.current_layout() != dl.TENANT and APPLY:
        print("CANH BAO: GDRIVE_LAYOUT chua phai 'tenant' — ma dang chay se van ghi bo cuc cu.")

    clean_slugs()
    root = {k["name"]: k for k in ls(client.root_folder_id) if is_folder(k)}

    print("\n== 2-3. THU MUC TRUNG TEN VA THU MUC RONG (trong cay du lieu)")
    for name in (dl.OLD_TENANTS_ROOT, dl.FEATURES_TREE, dl.RAW_VIDEOS_TREE, dl.MODELS_TREE,
                 dl.COMMUNITY_ROOT, dl.TENANTS_ROOT):
        if name in root:
            dedupe_and_prune(root[name], name)

    print("\n== 4. DOI")
    plan = plan_moves(root)
    for src, sp, tp in plan:
        print(f"  KE    {sp:<60} -> {tp}")
    if conflicts and APPLY:
        print("\nXUNG DOT — KHONG DOI:", *conflicts, sep="\n  ")
        return 2
    for src, sp, tp in plan:
        move_into(src, sp, tp)

    print("\n== 5. GOC CU")
    for name in (dl.OLD_TENANTS_ROOT, dl.FEATURES_TREE, dl.RAW_VIDEOS_TREE, dl.MODELS_TREE):
        if name not in root:
            continue
        if not APPLY:
            print(f"  RAC   {name}/ (neu rong sau khi doi)")
            continue
        left = file_count(root[name]["id"])
        if left == 0:
            trash(root[name]["id"], f"{name}/ (rong)")
        else:
            print(f"  CON   {name}/ con {left} tep — de yen")

    print(f"\n{'Da' if APPLY else 'Se'}: doi slug {stats['slugs']}, gop trung {stats['dupes']}, "
          f"bo rong {stats['empty']}, doi {stats['tree_moves']} cay, gop {stats['child_moves']} muc con.")
    if conflicts:
        print("XUNG DOT (de yen, xu ly tay):", *conflicts, sep="\n  ")
    report_unreferenced()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
