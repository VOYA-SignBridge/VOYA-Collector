"""Doi chieu file .npz cuc bo voi ban tren Google Drive theo storage_url.

Vi sao can: storage_url cua mot so dong tro NHAM sang file Drive cua mau khac
(phat hien 23/07/2026: 11 dong rang-muoi cua Minh/Nhung tro sang cat-dau-ca cua
Tran). Loi nam o duong GHI du lieu nen co the anh huong nhieu mau khac ma khong
ai biet, vi binh thuong khong ai doi chieu Drive voi ban cuc bo.

Cach lam (2 tang, tang 1 gan nhu mien phi):
  Tang 1 — lay md5Checksum tu metadata Drive (khong tai file). Khop md5 voi ban
           cuc bo => chac chan dung, bo qua.
  Tang 2 — voi cac dong lech md5, TAI ve va so sanh noi dung mang 'sequence'.
           Byte co the khac nhau do metadata zip du noi dung giong het, nen chi
           ket luan "sai" khi mang so lieu that su khac.
  Ngoai ra: neu mang tai ve trung khop mang cua MOT MAU KHAC trong dataset thi
           bao ro dang tro nham sang mau nao — day la dau van tay cua loi tren.

Dung:
    python scripts/audit_gdrive_sample_links.py --dialect hoa-de
    python scripts/audit_gdrive_sample_links.py --all --limit 200
    python scripts/audit_gdrive_sample_links.py --all --no-download   # chi tang 1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, '/app')

import numpy as np

from app.storage.gdrive_client import get_gdrive_client
from app.storage.metadata_db import _fetch_all

FEATURES_ROOT = Path('/dataset/features')


def extract_file_id(url: str) -> str:
    url = (url or '').strip()
    if url.startswith('gdrive://'):
        return url[len('gdrive://'):]
    m = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    return m.group(1) if m else ''


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_sequence(path: Path):
    with np.load(path, allow_pickle=False) as d:
        key = 'sequence' if 'sequence' in d else list(d.keys())[0]
        return np.asarray(d[key], dtype=np.float32)


def content_sha(arr) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr, dtype=np.float32).tobytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dialect', default='', help='Chi kiem tra mot dialect')
    ap.add_argument('--all', action='store_true', help='Kiem tra toan bo dataset')
    ap.add_argument('--limit', type=int, default=0, help='Gioi han so dong (0 = khong gioi han)')
    ap.add_argument('--no-download', action='store_true',
                    help='Chi chay tang 1 (md5 metadata), khong tai file nao')
    ap.add_argument('--out', type=Path, default=Path('/workspace/reports/gdrive_link_audit.json'))
    args = ap.parse_args()

    if not args.dialect and not args.all:
        print('Can --dialect <ten> hoac --all')
        return 2

    # '%%' vi psycopg2 coi '%' la placeholder khi co tham so di kem
    where = "storage_url LIKE '%%drive.google%%'"
    params: tuple = ()
    if args.dialect:
        where += ' AND dialect = %s'
        params = (args.dialect,)
    else:
        where = where.replace('%%', '%')
    sql = (f'SELECT sample_uid, dialect, slug, user_id, file_path, storage_url '
           f'FROM samples WHERE {where} ORDER BY dialect, slug, sample_uid')
    rows = _fetch_all(sql, params) if params else _fetch_all(sql)
    if args.limit:
        rows = rows[:args.limit]
    print(f'dong can kiem tra: {len(rows)}')

    # Ban do noi dung cuc bo -> dung de nhan dien "tro nham sang mau nao"
    print('dang lap chi muc noi dung cuc bo...')
    local_by_uid: dict[str, Path] = {}
    content_index: dict[str, list[str]] = {}
    for p in FEATURES_ROOT.rglob('*.npz'):
        uid = p.stem.replace('sample_', '')
        local_by_uid[uid] = p
        try:
            content_index.setdefault(content_sha(load_sequence(p)), []).append(uid)
        except Exception:
            pass
    print(f'  {len(local_by_uid)} file npz cuc bo')

    client = get_gdrive_client()
    stats = Counter()
    findings: list[dict] = []

    for i, r in enumerate(rows, 1):
        if i % 100 == 0:
            print(f'  ...{i}/{len(rows)}')
        uid = r['sample_uid']
        local = local_by_uid.get(uid)
        if local is None:
            stats['khong_co_file_cuc_bo'] += 1
            continue

        fid = extract_file_id(str(r['storage_url']))
        if not fid:
            stats['url_khong_doc_duoc'] += 1
            continue

        try:
            meta = client.service.files().get(
                fileId=fid, fields='id,name,md5Checksum,size').execute()
        except Exception as e:
            stats['loi_doc_metadata'] += 1
            findings.append({'sample_uid': uid, 'loai': 'loi_metadata',
                             'chi_tiet': str(e)[:120], 'drive_id': fid})
            continue

        drive_md5 = meta.get('md5Checksum') or ''
        if drive_md5 and drive_md5 == md5_file(local):
            stats['khop_md5'] += 1
            continue

        if args.no_download:
            stats['lech_md5_chua_kiem_tra'] += 1
            findings.append({'sample_uid': uid, 'loai': 'lech_md5_chua_kiem_tra',
                             'dialect': r['dialect'], 'slug': r['slug'],
                             'user_id': r['user_id'], 'drive_id': fid,
                             'drive_name': meta.get('name', '')})
            continue

        # Tang 2: tai ve, so sanh noi dung mang
        try:
            with tempfile.TemporaryDirectory() as td:
                dst = Path(td) / 'probe.npz'
                client.download_file(fid, str(dst))
                remote_arr = load_sequence(dst)
                remote_sha = content_sha(remote_arr)
        except Exception as e:
            stats['loi_tai_file'] += 1
            findings.append({'sample_uid': uid, 'loai': 'loi_tai_file',
                             'chi_tiet': str(e)[:120], 'drive_id': fid})
            continue

        local_sha = content_sha(load_sequence(local))
        if remote_sha == local_sha:
            stats['khop_noi_dung'] += 1
            continue

        matches = [u for u in content_index.get(remote_sha, []) if u != uid]
        stats['NOI_DUNG_SAI'] += 1
        entry = {'sample_uid': uid, 'loai': 'noi_dung_sai',
                 'dialect': r['dialect'], 'slug': r['slug'], 'user_id': r['user_id'],
                 'drive_id': fid, 'drive_name': meta.get('name', '')}
        if matches:
            other = matches[0]
            orow = _fetch_all('SELECT slug, user_id, dialect FROM samples WHERE sample_uid = %s',
                              (other,))
            entry['tro_nham_sang'] = {
                'sample_uid': other,
                'slug': orow[0]['slug'] if orow else '?',
                'user_id': orow[0]['user_id'] if orow else '?',
                'dialect': orow[0]['dialect'] if orow else '?',
            }
        findings.append(entry)

    print('\n=== KET QUA ===')
    for k in ('khop_md5', 'khop_noi_dung', 'NOI_DUNG_SAI', 'lech_md5_chua_kiem_tra',
              'khong_co_file_cuc_bo', 'url_khong_doc_duoc', 'loi_doc_metadata', 'loi_tai_file'):
        if stats[k]:
            print(f'  {k:24s} {stats[k]}')

    wrong = [f for f in findings if f['loai'] == 'noi_dung_sai']
    if wrong:
        print(f'\n=== {len(wrong)} dong co storage_url tro sai file ===')
        for f in wrong[:40]:
            tgt = f.get('tro_nham_sang')
            suffix = (f"  -> that ra la {tgt['user_id']}/{tgt['slug']} ({tgt['sample_uid'][:10]})"
                      if tgt else '  -> khong khop mau nao trong dataset')
            print(f"  {f['sample_uid'][:12]:12s} {str(f['user_id']):6s} {f['slug']:14s}{suffix}")
        if len(wrong) > 40:
            print(f'  ... con {len(wrong) - 40} dong nua')

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {'tong_ket': dict(stats), 'chi_tiet': findings}, ensure_ascii=False, indent=2),
        encoding='utf-8')
    print(f'\nbao cao chi tiet -> {args.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
