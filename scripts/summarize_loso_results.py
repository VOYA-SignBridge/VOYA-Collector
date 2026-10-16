"""Tong hop ket qua leave-one-signer-out va kiem dinh xem chenh lech co that khong.

Vi sao can kiem dinh: tren dataset nho, chenh lech vai mau giua hai model
thuong chi la nhieu do seed. Script nay bao cao trung binh, khoang tin cay
Wilson, va so sanh tung cap bang paired bootstrap tren cac fold — de biet
"model X hon model Y" co dung khong, hay chi la trung hop.

Dung:
    python scripts/summarize_loso_results.py <file_ket_qua.txt>
"""
from __future__ import annotations

import argparse
import math
import random
import re
from collections import defaultdict
from pathlib import Path

LINE = re.compile(r'(test_\S+)\s+(\S+)\s+seed=(\d+)\s+([0-9.]+)(?:\s+f1\s+([0-9.]+))?')


def wilson(k: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


MIN_FOLDS_FOR_TEST = 4


def paired_bootstrap(a: dict, b: dict, folds: list, n_iter: int = 10000,
                     seed: int = 42) -> float | None:
    """p-value 2 phia: xac suat chenh lech quan sat duoc chi do ngau nhien.

    Lay mau lai theo FOLD (khong phai theo run) vi cac run trong cung fold
    khong doc lap — chung dung chung du lieu.

    Duoi MIN_FOLDS_FOR_TEST fold thi tra ve None chu khong tra ve so. Voi 2 fold
    chi co 4 cach lay mau lai; p-value sinh ra khong do duoc gi ngoai chinh no,
    va no se vui ve dan nhan "co y nghia" cho mot chenh lech 0.009 trong khi bo
    qua chenh lech 0.034. Mot o trong doc dung hon mot con so sai.
    """
    if len(folds) < MIN_FOLDS_FOR_TEST:
        return None
    rng = random.Random(seed)
    obs = sum(a[f] for f in folds) / len(folds) - sum(b[f] for f in folds) / len(folds)
    if obs == 0:
        return 1.0
    count = 0
    for _ in range(n_iter):
        pick = [rng.choice(folds) for _ in folds]
        d = sum(a[f] for f in pick) / len(pick) - sum(b[f] for f in pick) / len(pick)
        if (d - obs) * (1 if obs > 0 else -1) <= -abs(obs):
            count += 1
    return min(1.0, 2 * count / n_iter)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('results', type=Path)
    ap.add_argument('--metric', choices=['acc', 'f1'], default='acc')
    ap.add_argument('--splits_dir', type=Path, default=None,
                    help='thu muc chua cac fold test_*; dung de doc so mau test '
                         'moi fold. Thieu thi cac fold duoc coi la bang nhau.')
    args = ap.parse_args()

    n_test: dict[str, int] = {}
    runs: dict[tuple[str, str], list[float]] = defaultdict(list)
    for raw in args.results.read_text(encoding='utf-8', errors='ignore').splitlines():
        m = LINE.search(raw)
        if not m:
            continue
        fold, model = m.group(1), m.group(2)
        val = float(m.group(4) if args.metric == 'acc' else (m.group(5) or m.group(4)))
        runs[(model, fold)].append(val)

    models = sorted({k[0] for k in runs})
    folds = sorted({k[1] for k in runs})
    if not models:
        print('Khong doc duoc ket qua nao.')
        return 1

    # So mau test moi fold. Thieu thi moi fold nang bang nhau — dung hon la lang
    # le cho n=0 roi rot ve trung binh khong trong so ma khong noi gi.
    for f in folds:
        p = (args.splits_dir / f / 'test.csv') if args.splits_dir else None
        n_test[f] = (sum(1 for _ in p.open(encoding='utf-8')) - 1) \
            if (p and p.exists()) else 0
    if not any(n_test.values()):
        print('[warn] khong doc duoc so mau test (thieu --splits_dir): '
              'moi fold duoc nang bang nhau.\n')

    per_fold = {m: {f: (sum(runs[(m, f)]) / len(runs[(m, f)]) if runs[(m, f)] else 0.0)
                    for f in folds} for m in models}
    total_n = sum(n_test.values()) or len(folds)
    weighted = {m: (sum(per_fold[m][f] * (n_test[f] or 1) for f in folds) / total_n)
                for m in models}

    print(f'=== LOSO {len(folds)} fold — chi so: {args.metric} ===')
    print(f'{"model":18s}' + ''.join(f'{f.replace("test_", "")+f" (n={n_test[f]})":>16s}'
                                     for f in folds) + f'{"TB":>9s}')
    for m in sorted(models, key=lambda x: -weighted[x]):
        cells = ''.join(f'{per_fold[m][f]:16.3f}' for f in folds)
        print(f'{m:18s}{cells}{weighted[m]:9.3f}')

    print(f'\n=== Xep hang + khoang tin cay 95% (tren {total_n} mau test) ===')
    order = sorted(models, key=lambda x: -weighted[x])
    for i, m in enumerate(order, 1):
        lo, hi = wilson(weighted[m] * total_n, total_n)
        print(f'  {i}. {m:18s} {weighted[m]:.4f}  CI95=[{lo:.3f}, {hi:.3f}]')

    print('\n=== Chenh lech co that khong? (paired bootstrap theo fold) ===')
    if len(folds) < MIN_FOLDS_FOR_TEST:
        print(f'  Chi co {len(folds)} fold — duoi nguong {MIN_FOLDS_FOR_TEST}, khong '
              f'kiem dinh. Nguoi ky la don vi doc lap, va {len(folds)} nguoi thi khong '
              f'du de noi chenh lech nao la that.')
    best = order[0]
    for m in order[1:]:
        p = paired_bootstrap(per_fold[best], per_fold[m], folds)
        diff = weighted[best] - weighted[m]
        if p is None:
            print(f'  {best} vs {m:18s} chenh {diff:+.3f}  p=—      -> khong kiem dinh')
            continue
        verdict = 'CO Y NGHIA' if p < 0.05 else 'khong ket luan duoc'
        print(f'  {best} vs {m:18s} chenh {diff:+.3f}  p={p:.3f}  -> {verdict}')

    print('\n=== Dao dong do seed (cung fold, cung du lieu) ===')
    for m in order:
        spans = [(max(runs[(m, f)]) - min(runs[(m, f)]), f) for f in folds
                 if len(runs[(m, f)]) > 1]
        if spans:
            worst, wf = max(spans)
            print(f'  {m:18s} bien do lon nhat {worst:.3f} ({wf.replace("test_", "")})')

    print('\n=== Do kho tung nguoi ky (TB moi model) ===')
    for f in folds:
        vals = [per_fold[m][f] for m in models]
        print(f'  {f.replace("test_", ""):8s} (n={n_test[f]:3d}): TB={sum(vals)/len(vals):.3f}'
              f'  [{min(vals):.3f} - {max(vals):.3f}]')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
