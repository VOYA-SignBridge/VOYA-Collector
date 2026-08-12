#!/usr/bin/env python3
"""Bon baseline khong-hoc tren cac fold LOSO: chance, majority, centroid, 1-NN.

Vi sao can: mot con so accuracy khong noi len gi neu khong biet san bang o dau.
Voi 7 lop, doan bua da duoc ~0.143; neu mot mang sau dat 0.55 thi no chi ngang
mot centroid Euclid tinh trong ba dong numpy. Bai bao bao cao bon moc nay va
script nay la thu sinh ra chung.

Bon baseline, tren chuoi 60x126 lam phang (7560 chieu):

  chance     1 / |C|            — khong nhin du lieu
  majority   lop dong nhat trong train, doan cung mot nhan cho moi mau
  centroid   gan trung binh lop nhat theo khoang cach Euclid
  1-NN       gan mau train nhat theo khoang cach Euclid

Cac o "thieu tay" giu nguyen gia tri 0 — cung dau vao ma mang nhin thay. Lam
sach rieng cho baseline se bien no thanh mot he thong khac va het so sanh duoc.
Val bi bo qua: no de chon checkpoint, ma baseline thi khong co gi de chon.

Xac dinh: khong lay mau, khong xao tron, go the bang theo nhan nho nhat.

Dung:
    python scripts/compute_baselines.py processed/splits/loso/hoa_de \
        --features_root dataset/features
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
SEQ_LEN, FEAT_DIM = 60, 126

# Cung thu tu voi SignFeatureDataset.feature_key_priority. Cac .npz thuc te con
# chua 'landmarks_normalized' / 'landmarks_raw' ben canh 'sequence', va mot key
# 'meta' la object array (doc no voi allow_pickle=False la loi): doc lech mot
# key la baseline dang do tren khong gian dac trung khac voi cai mang nhin thay.
FEATURE_KEYS = ('sequence', 'features', 'x', 'data', 'arr_0')

_features: dict[Path, np.ndarray] = {}
_indexes: dict[Path, dict[str, Path]] = {}


def load_npz(path: Path) -> np.ndarray:
    """Doc mot mau thanh vector 7560 chieu; nho lai vi cac fold dung chung mau."""
    hit = _features.get(path)
    if hit is not None:
        return hit
    with np.load(path, allow_pickle=False) as z:
        key = next((k for k in FEATURE_KEYS if k in z), None)
        if key is None:
            raise KeyError(f'{path}: khong co key nao trong {FEATURE_KEYS} (co {z.files})')
        arr = np.asarray(z[key], dtype=np.float32)
    if arr.ndim > 2:
        arr = arr.reshape(arr.shape[0], -1)
    if arr.ndim != 2 or arr.shape[1] != FEAT_DIM:
        # Cat bot cho vua se im lang bien mot file 1662 chieu thanh rac.
        raise ValueError(f'{path}: cho (>=1, {FEAT_DIM}), nhan {arr.shape}')
    if arr.shape[0] < SEQ_LEN:
        arr = np.vstack([arr, np.zeros((SEQ_LEN - arr.shape[0], FEAT_DIM), np.float32)])
    _features[path] = flat = arr[:SEQ_LEN].reshape(-1)
    return flat


def resolve(row: dict, features_root: Path) -> Path:
    """Duong dan .npz, dung dung cach SignFeatureDataset dung: lang/dialect/folder/file.

    Cac CSV do make_loso_splits.py sinh ra de trong `file_path` — chi co
    folder_name + file — nen phai dung lai duong dan, khong doc san duoc.
    """
    lang = (row.get('language') or 'vn').strip() or 'vn'
    dial = (row.get('dialect') or '').strip()
    if not dial:  # loader suy dialect tu label_key 'vn/hoa-de/<slug>' khi cot trong
        parts = (row.get('label_key') or '').strip().split('/')
        dial = parts[1] if len(parts) == 3 else 'common'
    name = (row.get('file') or '').strip() or Path(
        (row.get('storage_key') or row.get('file_path') or '').strip()).name
    direct = features_root / lang / dial / (row.get('folder_name') or '').strip() / name
    if direct.is_file():
        return direct

    # Du phong: lap chi muc theo ten file MOT lan cho ca lan chay, thay vi
    # rglob() lai ca cay dac trung tren tung dong CSV.
    if features_root not in _indexes:
        _indexes[features_root] = {p.name: p for p in features_root.rglob('*.npz')}
    hit = _indexes[features_root].get(name)
    if hit is None:
        raise FileNotFoundError(f'khong tim thay {name!r} duoi {features_root}')
    return hit


def load_split(csv_path: Path, features_root: Path) -> tuple[np.ndarray, np.ndarray]:
    with csv_path.open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    X = (np.stack([load_npz(resolve(r, features_root)) for r in rows]) if rows
         else np.zeros((0, SEQ_LEN * FEAT_DIM), np.float32))
    return X, np.array([int(r['class_idx']) for r in rows], dtype=np.int64)


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray, labels: list[int]) -> float:
    """Macro-F1 tu tay — sklearn khong nam trong moi truong cua bai bao."""
    scores = []
    for c in labels:
        tp = np.count_nonzero((y_pred == c) & (y_true == c))
        denom = 2 * tp + np.count_nonzero((y_pred == c) & (y_true != c)) \
                       + np.count_nonzero((y_pred != c) & (y_true == c))
        scores.append(0.0 if denom == 0 else 2 * tp / denom)
    return float(np.mean(scores)) if scores else 0.0


def nearest(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Chi so hang B gan nhat moi hang A theo khoang cach Euclid.

    ||a-b||^2 = ||a||^2 - 2a.b + ||b||^2, bo ||a||^2 vi la hang so tren tung
    hang nen khong doi argmin. Tinh o float64: voi 7560 chieu, khai trien nay o
    float32 mat du chu so co nghia de argmin chon sai lang gieng. Chia lo de ma
    tran khoang cach 111 x 94 khong phinh het RAM tren cac fold lon hon.
    """
    B64 = B.astype(np.float64)
    b2 = np.einsum('ij,ij->i', B64, B64)
    step = max(1, int(4e6 // max(1, B.shape[0])))
    out = np.empty(A.shape[0], np.int64)
    for i in range(0, A.shape[0], step):
        a = A[i:i + step].astype(np.float64)
        out[i:i + step] = np.argmin(b2 - 2.0 * (a @ B64.T), axis=1)
    return out


def run_fold(fold_dir: Path, features_root: Path) -> dict | None:
    tr, te = fold_dir / 'train.csv', fold_dir / 'test.csv'
    if not (tr.is_file() and te.is_file()):
        return None
    Xtr, ytr = load_split(tr, features_root)
    Xte, yte = load_split(te, features_root)
    if not len(ytr) or not len(yte):
        return None

    labels = sorted(set(ytr.tolist()) | set(yte.tolist()))
    res = {'n_train': len(ytr), 'n_test': len(yte), 'n_classes': len(labels)}

    def score(pred: np.ndarray) -> dict:
        return {'acc': float(np.mean(pred == yte)), 'f1': macro_f1(yte, pred, labels)}

    res['chance'] = {'acc': 1.0 / len(labels), 'f1': None}

    # most_common() go the bang theo thu tu dong CSV; lay nhan nho nhat de hai
    # lan chay tren cung du lieu khong ra hai con so.
    counts = Counter(ytr.tolist())
    maj = min(labels, key=lambda c: (-counts[c], c))
    res['majority'] = score(np.full_like(yte, maj))

    # Chi lop CO trong train moi co centroid — lop chi xuat hien o test thi
    # mean() cua no la NaN va se hut het argmin ve mot nhan.
    seen = [c for c in labels if np.any(ytr == c)]
    cents = np.stack([Xtr[ytr == c].mean(0) for c in seen])
    res['centroid'] = score(np.asarray(seen)[nearest(Xte, cents)])

    res['1nn'] = score(ytr[nearest(Xte, Xtr)])
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('loso_dir', type=Path, help='thu muc chua cac fold test_*')
    ap.add_argument('--features_root', type=Path, default=REPO / 'dataset' / 'features')
    ap.add_argument('--out', type=Path, default=None)
    args = ap.parse_args()

    folds = sorted(d for d in args.loso_dir.iterdir()
                   if d.is_dir() and d.name.startswith('test_'))
    if not folds:
        raise SystemExit(f'Khong co fold test_* nao trong {args.loso_dir}')

    results = {}
    for d in folds:
        r = run_fold(d, args.features_root)
        if r is None:
            print(f'[skip] {d.name}: thieu train.csv/test.csv hoac partition rong')
            continue
        results[d.name] = r
        print(f'[ok] {d.name}: train={r["n_train"]} test={r["n_test"]} '
              f'classes={r["n_classes"]}')

    if not results:
        raise SystemExit('Khong fold nao chay duoc.')

    methods = ['chance', 'majority', 'centroid', '1nn']
    names = sorted(results)
    n_tot = sum(results[f]['n_test'] for f in names)

    print(f'\n=== Baseline tren {len(names)} fold ({n_tot} mau test) ===')
    head = f'{"baseline":12s}' + ''.join(f'{f.replace("test_", ""):>12s}' for f in names)
    print(head + f'{"mean":>10s}{"weighted":>10s}')
    summary = {}
    for m in methods:
        accs = [results[f][m]['acc'] for f in names]
        w = sum(results[f][m]['acc'] * results[f]['n_test'] for f in names) / n_tot
        cells = ''.join(f'{a:12.3f}' for a in accs)
        print(f'{m:12s}{cells}{sum(accs) / len(accs):10.3f}{w:10.3f}')
        summary[m] = {'per_fold_acc': dict(zip(names, accs)),
                      'mean_acc': sum(accs) / len(accs), 'weighted_acc': w,
                      'per_fold_f1': {f: results[f][m]['f1'] for f in names}}

    out = args.out or (args.loso_dir / 'baselines.json')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'folds': results, 'summary': summary},
                              ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n-> {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
