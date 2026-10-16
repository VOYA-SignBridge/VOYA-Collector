"""Kiem tra cac bat bien ma bai bao dua ra, doc thang tu CSV da sinh.

Bai bao khang dinh ba dieu ve cach chia du lieu. Script nay kiem tra tung dieu
tren file that, thay vi tin vao mo ta:

  1. Held-out (protocol A): nguoi muc tieu vang mat o CA train LAN val.
     P_train ∩ P_test = P_val ∩ P_test = ∅

  2. Matched (A vs B): test GIU NGUYEN tung sample_uid; |train| va so mau moi
     lop khong doi. Neu B chi don gian them du lieu vao thi chenh lech doc duoc
     se lan giua "phoi nhiem nguoi ky" va "train nhieu hon" — do la ly do phai
     doi cho chu khong chi them.

  3. Test khong dinh vao development: T_p ∩ (D_train ∪ D_val) = ∅ o ca hai
     giao thuc.

Dung:
    python scripts/verify_loso_splits.py processed/splits/loso/hoa_de_matched
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def read(fold: Path, name: str):
    p = fold / f'{name}.csv'
    if not p.exists():
        return []
    with p.open(encoding='utf-8') as f:
        return list(csv.DictReader(f))


def uids(rows):
    return {r['sample_uid'] for r in rows}


def performers(rows):
    return {r['user_id'] for r in rows}


def class_counts(rows):
    return Counter(r['label_slug'] for r in rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('loso_dir', type=Path)
    args = ap.parse_args()

    folds = {d.name: d for d in sorted(args.loso_dir.iterdir())
             if d.is_dir() and d.name.startswith('test_')}
    if not folds:
        raise SystemExit(f'Khong co fold test_* nao trong {args.loso_dir}')

    checks: list[tuple[bool, str]] = []

    def check(ok: bool, msg: str):
        checks.append((bool(ok), msg))

    # --- 1 & 3: tung fold ---
    for name, d in folds.items():
        tr, va, te = read(d, 'train'), read(d, 'val'), read(d, 'test')
        meta = json.loads((d / 'split_metadata.json').read_text(encoding='utf-8'))
        target = meta.get('held_out_performer', '')
        protocol = meta.get('protocol', 'A')

        check(not (uids(te) & (uids(tr) | uids(va))),
              f'{name}: test khong trung sample nao voi train/val')
        check(bool(te), f'{name}: test khong rong')
        check(performers(te) == {target},
              f'{name}: test chi chua {target}')

        if protocol == 'A':
            check(target not in performers(tr),
                  f'{name}: {target} vang mat o train')
            check(target not in performers(va),
                  f'{name}: {target} vang mat o val')
        else:
            check(target in performers(tr),
                  f'{name}: {target} CO mat o train (protocol B)')
            check(target in performers(va),
                  f'{name}: {target} CO mat o val (protocol B)')

    # --- 2: cap A/B khop nhau ---
    pairs = sorted({n[:-2] for n in folds if n.endswith('_A')}
                   & {n[:-2] for n in folds if n.endswith('_B')})
    for base in pairs:
        a, b = folds[f'{base}_A'], folds[f'{base}_B']
        tr_a, va_a, te_a = read(a, 'train'), read(a, 'val'), read(a, 'test')
        tr_b, va_b, te_b = read(b, 'train'), read(b, 'val'), read(b, 'test')

        check(uids(te_a) == uids(te_b),
              f'{base}: test giong het nhau giua A va B ({len(te_a)} mau)')
        check(len(tr_a) == len(tr_b),
              f'{base}: |train| khong doi ({len(tr_a)} vs {len(tr_b)})')
        check(len(va_a) == len(va_b),
              f'{base}: |val| khong doi ({len(va_a)} vs {len(va_b)})')
        ca, cb = class_counts(tr_a), class_counts(tr_b)
        check(ca == cb,
              f'{base}: so mau train moi lop khong doi'
              + ('' if ca == cb else f' — lech: {ca - cb or cb - ca}'))

    if not pairs:
        print('[note] khong co cap A/B — bo qua kiem tra matched.\n')

    npass = sum(1 for ok, _ in checks if ok)
    for ok, msg in checks:
        print(f'  [{"PASS" if ok else "FAIL"}] {msg}')
    print(f'\n{npass}/{len(checks)} kiem tra dat')
    return 0 if npass == len(checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
