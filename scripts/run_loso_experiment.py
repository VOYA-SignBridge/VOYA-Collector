"""Chay toan bo luoi LOSO: fold x kien truc x seed, roi gom ket qua ve mot file.

Bai bao bao cao 5x4x3 = 60 run cho Hoa De va 5x2x3 = 30 run cho fingerspelling.
Goi tay tung do la cach chac chan de mot run bi thieu ma khong ai nhan ra, hoac
mot run smoke_test lot vao bang ket qua. Script nay chay het luoi, ghi lai tung
dong ngay khi xong, va bo qua nhung o da co ket qua — dut giua chung thi chay
lai la tiep, khong phai lam lai tu dau.

Dinh dang dong ket qua khop voi scripts/summarize_loso_results.py:

    test_H01  hdgcn  seed=42  0.9410  f1  0.9385

Dung:
    python scripts/run_loso_experiment.py processed/splits/loso/hoa_de \
        --results results_hoa_de.txt --run-purpose research
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TRAINER = REPO / 'processed' / 'train_utils' / 'train_tcn.py'
MODELS = ['hdgcn', 'cnn', 'tcn', 'lstm', 'bigru_attention']
DONE = re.compile(r'^(test_\S+)\s+(\S+)\s+seed=(\d+)\s')

# Phai co TRUOC khi torch tao CUDA context, nen dat trong env cua tien trinh con
# chu khong dat trong train_tcn.py. Thieu no thi --determinism strict khong chay
# HandGCN duoc: torch.matmul goi cuBLAS va bao loi ngay giua epoch dau. Trong
# docker bien nay den tu docker-compose.yml; chay ngoai docker thi khong ai dat.
CUBLAS_DETERMINISTIC_CONFIG = ':4096:8'

# Tren WSL2, driver GPU nam o /usr/lib/wsl/lib. ldconfig cache co libcuda.so.1
# nhung KHONG co ten khong phien ban; cuDNN lai dlopen dung "libcuda.so", nen
# libcudnn_cnn_infer.so.8 chet giua epoch dau. Torch van bao cuda available:True
# vi no link theo ten .so.1 — loi chi lo ra khi cuDNN chay that.
WSL_LIB = Path('/usr/lib/wsl/lib')


def child_env(determinism: str) -> dict:
    env = dict(os.environ)
    if determinism == 'strict':
        env['CUBLAS_WORKSPACE_CONFIG'] = CUBLAS_DETERMINISTIC_CONFIG
        env['PYTHONHASHSEED'] = '0'
    if WSL_LIB.is_dir():
        prev = env.get('LD_LIBRARY_PATH', '')
        env['LD_LIBRARY_PATH'] = f'{WSL_LIB}:{prev}' if prev else str(WSL_LIB)
    return env


def existing(results: Path) -> set[tuple[str, str, str]]:
    if not results.exists():
        return set()
    out = set()
    for line in results.read_text(encoding='utf-8').splitlines():
        m = DONE.match(line)
        if m:
            out.add((m.group(1), m.group(2), m.group(3)))
    return out


def read_sidecar(out_dir: Path) -> dict | None:
    cands = sorted(out_dir.glob('*.json'), key=lambda p: p.stat().st_mtime)
    for p in reversed(cands):
        if p.name in ('label_to_index.json', 'index_to_label.json'):
            continue
        try:
            d = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        if isinstance(d, dict) and 'test' in d:
            return d
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('loso_dir', type=Path)
    ap.add_argument('--results', type=Path, required=True)
    ap.add_argument('--runs_dir', type=Path, default=None)
    ap.add_argument('--models', type=str, default=','.join(MODELS))
    ap.add_argument('--seeds', type=str, default='42,43,44')
    ap.add_argument('--epochs', type=int, default=80)
    ap.add_argument('--device', type=str, default='cuda')
    ap.add_argument('--features_root', type=Path, default=REPO / 'dataset' / 'features')
    ap.add_argument('--determinism', choices=['strict', 'fast'], default='strict')
    ap.add_argument('--run-purpose', dest='run_purpose',
                    choices=['smoke_test', 'research'], default='research')
    ap.add_argument('--dataset_version', type=str, default='')
    ap.add_argument('--python', type=str, default=sys.executable)
    ap.add_argument('--dry_run', action='store_true')
    args = ap.parse_args()

    folds = sorted(d for d in args.loso_dir.iterdir()
                   if d.is_dir() and d.name.startswith('test_'))
    if not folds:
        raise SystemExit(f'Khong co fold test_* nao trong {args.loso_dir}')

    models = [m.strip() for m in args.models.split(',') if m.strip()]
    seeds = [s.strip() for s in args.seeds.split(',') if s.strip()]
    runs_dir = args.runs_dir or (args.loso_dir / 'runs')

    summary = json.loads((args.loso_dir / 'loso_summary.json').read_text(encoding='utf-8')) \
        if (args.loso_dir / 'loso_summary.json').exists() else {}
    split_version = summary.get('split_version') or args.loso_dir.name
    dataset_version = args.dataset_version or (summary.get('dataset_manifest_checksum') or '')[:12] \
        or 'unversioned'

    # Fold khong hop le cho nghien cuu thi trainer se tu chan — chan o day luon
    # de khong dot GPU truoc khi biet.
    skipped = []
    usable = []
    dialects = {}
    for d in folds:
        meta = d / 'split_metadata.json'
        ok = True
        if meta.exists():
            m = json.loads(meta.read_text(encoding='utf-8'))
            dialects[d.name] = (m.get('dialect') or '').strip()
            if args.run_purpose == 'research':
                ok = bool(m.get('valid_for_research'))
                if not ok:
                    skipped.append((d.name, '; '.join(m.get('invalid_reasons') or ['?'])))
        if ok:
            usable.append(d)
    missing_dialect = [d.name for d in usable if not dialects.get(d.name)]
    if missing_dialect:
        raise SystemExit(
            f'split_metadata.json khong co truong "dialect" cho: {missing_dialect}.\n'
            f'Thieu no thi trainer khong vao subset mode va se dung label map toan '
            f'cuc trong dataset/labels.csv — model mo ra hang chuc lop cho mot fold '
            f'vai lop, macro-F1 bao cao se sai. Sinh lai split bang '
            f'scripts/make_loso_splits.py.')
    for name, why in skipped:
        print(f'[skip] {name}: {why}')

    grid = [(d, m, s) for d in usable for m in models for s in seeds]
    done = existing(args.results)
    todo = [g for g in grid if (g[0].name, g[1], g[2]) not in done]
    print(f'[plan] {len(usable)} fold x {len(models)} model x {len(seeds)} seed '
          f'= {len(grid)} run ({len(grid) - len(todo)} da co, {len(todo)} can chay)')
    if args.dry_run:
        for d, m, s in todo:
            print(f'  would run {d.name} {m} seed={s}')
        return 0

    args.results.parent.mkdir(parents=True, exist_ok=True)
    failures = []
    t_all = time.time()
    for i, (d, model, seed) in enumerate(todo, 1):
        out_dir = runs_dir / d.name / model / f'seed{seed}'
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            args.python, str(TRAINER),
            '--train_csv', str(d / 'train.csv'),
            '--val_csv', str(d / 'val.csv'),
            '--test_csv', str(d / 'test.csv'),
            '--features_root', str(args.features_root),
            '--model_type', model,
            '--dialect', dialects[d.name],
            '--seed', seed,
            '--epochs', str(args.epochs),
            '--device', args.device,
            '--num_workers', '0',
            '--determinism', args.determinism,
            '--out_dir', str(out_dir),
            '--tag', f'{d.name}-{model}-s{seed}',
            '--dataset_version', dataset_version,
            '--split_version', split_version,
            '--run-purpose', args.run_purpose,
        ]
        t0 = time.time()
        print(f'\n[{i}/{len(todo)}] {d.name} {model} seed={seed} ...', flush=True)
        proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                              env=child_env(args.determinism))
        dt = time.time() - t0
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or '').strip().splitlines()[-12:]
            print(f'    FAILED sau {dt:.0f}s (exit {proc.returncode})')
            for line in tail:
                print(f'      {line}')
            failures.append((d.name, model, seed, proc.returncode))
            (out_dir / 'stderr.log').write_text(proc.stderr or '', encoding='utf-8')
            continue

        side = read_sidecar(out_dir)
        if not side:
            print(f'    FAILED: khong tim thay sidecar json trong {out_dir}')
            failures.append((d.name, model, seed, 'no sidecar'))
            continue
        acc = side['test'].get('acc')
        f1 = side['test'].get('f1')
        line = f'{d.name}\t{model}\tseed={seed}\t{acc:.6f}\tf1\t{f1:.6f}'
        with args.results.open('a', encoding='utf-8') as f:
            f.write(line + '\n')
        print(f'    acc={acc:.4f} f1={f1:.4f}  ({dt:.0f}s)')

    print(f'\n=== xong sau {(time.time() - t_all) / 60:.1f} phut, '
          f'{len(failures)} run loi ===')
    for f in failures:
        print('  FAIL', f)
    print(f'-> {args.results}')
    print(f'   tong hop: python scripts/summarize_loso_results.py {args.results} '
          f'--splits_dir {args.loso_dir} --metric f1')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
