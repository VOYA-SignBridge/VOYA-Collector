"""Dung cac fold leave-one-signer-out tu mot split manifest da co.

Vi sao can rieng script nay: make_splits.py --split_mode strict_signer_disjoint
doi val VA test cung phai tach nguoi ky, nen no (dung dan) tu choi chay khi so
nguoi ky it — voi 4 nguoi thi khong the vua tach ca val lan test vua phu du lop.
LOSO can dieu kien yeu hon va van trung thuc: TEST la mot nguoi hoan toan moi,
con val chi dung de early stopping nen lay tu chinh nhom nguoi huan luyen.

Moi fold duoc ghi kem split_metadata.json dung dinh dang cua make_splits, va
valid_for_research chi bang true khi TU KIEM TRA dat: test tach nguoi khoi
train/val, train va test deu phu du lop, khong split nao rong.

Dung:
    python processed/splits/make_loso_folds.py \
        --source processed/splits/versions/hoa_de_sample_v5 \
        --output_version hoa_de_loso_v5
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def read_split(src: Path):
    rows, fields = [], None
    for name in ('train', 'val', 'test'):
        p = src / f'{name}.csv'
        if not p.exists():
            continue
        with p.open(encoding='utf-8') as f:
            rd = csv.DictReader(f)
            fields = rd.fieldnames
            rows.extend(list(rd))
    return rows, fields


def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True,
                    help='Thu muc split da tao boi make_splits (che do manifest)')
    ap.add_argument('--output_version', type=str, required=True)
    ap.add_argument('--group_col', type=str, default='signer_id')
    ap.add_argument('--label_col', type=str, default='label_slug')
    ap.add_argument('--val_fraction', type=float, default=0.2)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--fold_signers', type=str, default='',
                    help='Danh sach nguoi ky dung lam fold test (phay ngan cach). '
                         'Mac dinh: tat ca. Dung khi mot so nguoi chi phu vai lop.')
    ap.add_argument('--require_full_coverage', action='store_true',
                    help='Chi giu cac lop ma MOI nguoi ky lam fold deu co mau. Lop nao '
                         'chi mot nguoi ky co thi khong the tach nguoi — bo di thay vi '
                         'ghi ra split khong danh gia duoc.')
    ap.add_argument('--out_root', type=Path,
                    default=REPO_ROOT / 'processed' / 'splits' / 'versions')
    args = ap.parse_args()

    src_meta_path = args.source / 'split_metadata.json'
    src_meta = json.loads(src_meta_path.read_text(encoding='utf-8')) if src_meta_path.exists() else {}
    checksum = str(src_meta.get('dataset_manifest_checksum', ''))
    if not checksum:
        print('[CANH BAO] split nguon khong co dataset_manifest_checksum — '
              'cac run se truot C5.')

    rows, fields = read_split(args.source)
    rows = [r for r in rows if (r.get(args.group_col) or '').strip()]
    if not rows:
        raise SystemExit(f'Khong co dong nao co {args.group_col}.')

    by_signer = defaultdict(list)
    for r in rows:
        by_signer[r[args.group_col]].append(r)
    all_signers = sorted(by_signer)
    labels = sorted({r[args.label_col] for r in rows})
    print(f'{len(rows)} mau | {len(labels)} lop | {len(all_signers)} nguoi ky: '
          f'{ {s: len(v) for s, v in sorted(by_signer.items())} }')

    signers = ([s.strip() for s in args.fold_signers.split(',') if s.strip()]
               if args.fold_signers else all_signers)
    unknown = [s for s in signers if s not in by_signer]
    if unknown:
        raise SystemExit(f'Nguoi ky khong co trong du lieu: {unknown}')
    if args.fold_signers:
        print(f'fold test chi lay tu: {signers}')

    if args.require_full_coverage:
        covered = {l for l in labels
                   if all(any(r[args.label_col] == l for r in by_signer[s]) for s in signers)}
        dropped = sorted(set(labels) - covered)
        if dropped:
            print(f'bo {len(dropped)} lop khong duoc moi nguoi ky phu: {dropped}')
        labels = sorted(covered)
        rows = [r for r in rows if r[args.label_col] in covered]
        by_signer = defaultdict(list)
        for r in rows:
            by_signer[r[args.group_col]].append(r)
        print(f'con lai: {len(rows)} mau | {len(labels)} lop')

    # Mau cua nguoi KHONG lam fold van dung de huan luyen (them da dang), mien
    # la ho khong nam trong test — dieu do van giu nguyen tinh tach nguoi.
    extra = [s for s in all_signers if s not in signers and s in by_signer]
    if extra:
        print(f'nguoi chi dung de huan luyen (khong lam fold test): {extra}')

    root = args.out_root / args.output_version
    summary = []

    for held in signers:
        test_rows = by_signer[held]
        pool = [r for r in rows if r[args.group_col] != held]

        by_lab = defaultdict(list)
        for r in pool:
            by_lab[r[args.label_col]].append(r)

        rng = random.Random(args.seed)
        train_rows, val_rows = [], []
        for lab in sorted(by_lab):
            items = sorted(by_lab[lab], key=lambda r: r.get('sample_id', ''))
            rng.shuffle(items)
            k = max(1, int(round(len(items) * args.val_fraction)))
            val_rows.extend(items[:k])
            train_rows.extend(items[k:])

        # --- tu kiem tra, khong tu khai ---
        reasons = []
        tr_s = {r[args.group_col] for r in train_rows}
        va_s = {r[args.group_col] for r in val_rows}
        te_s = {r[args.group_col] for r in test_rows}
        if not tr_s.isdisjoint(te_s):
            reasons.append(f'train/test dung chung nguoi ky: {tr_s & te_s}')
        if not va_s.isdisjoint(te_s):
            reasons.append(f'val/test dung chung nguoi ky: {va_s & te_s}')
        for name, subset in (('train', train_rows), ('val', val_rows), ('test', test_rows)):
            if not subset:
                reasons.append(f'{name} rong')
        tr_lab = {r[args.label_col] for r in train_rows}
        te_lab = {r[args.label_col] for r in test_rows}
        if tr_lab != set(labels):
            reasons.append(f'train thieu lop: {sorted(set(labels) - tr_lab)}')
        if te_lab != set(labels):
            reasons.append(f'test thieu lop: {sorted(set(labels) - te_lab)}')

        fold = root / f'test_{held}'
        write_csv(fold / 'train.csv', train_rows, fields)
        write_csv(fold / 'val.csv', val_rows, fields)
        write_csv(fold / 'test.csv', test_rows, fields)

        meta = {
            'split_mode': 'leave_one_signer_out',
            'recognition_profile': src_meta.get('recognition_profile', ''),
            'include_common': src_meta.get('include_common', False),
            'seed': args.seed,
            'group_col': args.group_col,
            'held_out_signer': held,
            'valid_for_research': not reasons,
            'invalid_reasons': reasons,
            'num_classes': len(labels),
            'label_keys': sorted({r.get('label_key', '') for r in rows} - {''}),
            'counts': {'train': len(train_rows), 'val': len(val_rows), 'test': len(test_rows)},
            'signers': {'train': sorted(tr_s), 'val': sorted(va_s), 'test': sorted(te_s)},
            'signer_counts': {
                'train': dict(Counter(r[args.group_col] for r in train_rows)),
                'val': dict(Counter(r[args.group_col] for r in val_rows)),
                'test': dict(Counter(r[args.group_col] for r in test_rows)),
            },
            'class_coverage': {
                'train': len(tr_lab) / len(labels),
                'test': len(te_lab) / len(labels),
            },
            'dataset_manifest': src_meta.get('dataset_manifest', ''),
            'dataset_manifest_checksum': checksum,
            'source_split_version': src_meta.get('output_version', args.source.name),
            'output_version': f'{args.output_version}/test_{held}',
        }
        (fold / 'split_metadata.json').write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        summary.append((held, meta))
        flag = 'HOP LE' if not reasons else 'KHONG HOP LE: ' + '; '.join(reasons)
        print(f"  test={held:8s} train={len(train_rows):4d} val={len(val_rows):3d} "
              f"test={len(test_rows):4d}  {flag}")

    n_ok = sum(1 for _, m in summary if m['valid_for_research'])
    print(f'\n{n_ok}/{len(summary)} fold hop le -> {root}')
    return 0 if n_ok == len(summary) else 1


if __name__ == '__main__':
    raise SystemExit(main())
