import json, glob, os, statistics as st
from collections import defaultdict

ROOTS = {
    'hoa_de':   'processed/train_utils/outputs/loso/hoa_de_loso_v11',
    'alphabet': 'processed/train_utils/outputs/loso/alphabet_loso_v13',
}
SKIP = {'index_to_label.json', 'label_to_index.json'}


def harvest(root):
    runs = {}
    for j in glob.glob(root + '/**/seed_*/*.json', recursive=True):
        if os.path.basename(j) in SKIP:
            continue
        parts = j.replace(os.sep, '/').split('/')
        idx = [i for i, x in enumerate(parts) if x.startswith('seed_')]
        if not idx:
            continue
        i = idx[-1]
        try:
            seed = int(parts[i].split('_')[1])
        except ValueError:
            continue
        arch = parts[i - 1]
        folds = [x for x in parts if x.startswith('test_')]
        if not folds:
            continue
        fold = folds[-1]
        try:
            d = json.load(open(j, encoding='utf-8'))
        except Exception:
            continue
        acc = (d.get('test') or {}).get('acc')
        if acc is not None:
            runs[(fold, arch, seed)] = float(acc)
    return runs


def decompose(runs):
    """Balanced two-way ANOVA with replication: performer x architecture, seeds as replicates."""
    folds = sorted({k[0] for k in runs})
    archs = sorted({k[1] for k in runs})
    seeds = sorted({k[2] for k in runs})
    a, b, r = len(folds), len(archs), len(seeds)
    assert len(runs) == a * b * r, 'unbalanced design'

    vals = list(runs.values())
    grand = sum(vals) / len(vals)

    fold_mean = {f: st.mean(runs[(f, m, s)] for m in archs for s in seeds) for f in folds}
    arch_mean = {m: st.mean(runs[(f, m, s)] for f in folds for s in seeds) for m in archs}
    cell_mean = {(f, m): st.mean(runs[(f, m, s)] for s in seeds) for f in folds for m in archs}

    ss_total = sum((x - grand) ** 2 for x in vals)
    ss_fold = b * r * sum((fold_mean[f] - grand) ** 2 for f in folds)
    ss_arch = a * r * sum((arch_mean[m] - grand) ** 2 for m in archs)
    ss_inter = r * sum((cell_mean[(f, m)] - fold_mean[f] - arch_mean[m] + grand) ** 2
                       for f in folds for m in archs)
    ss_seed = sum((runs[(f, m, s)] - cell_mean[(f, m)]) ** 2
                  for f in folds for m in archs for s in seeds)

    seed_sds = [st.stdev([runs[(f, m, s)] for s in seeds]) for f in folds for m in archs]

    return {
        'n_runs': len(runs), 'folds': a, 'archs': b, 'seeds': r,
        'arch_names': archs, 'fold_names': folds,
        'grand': grand, 'ss_total': ss_total,
        'pct': {
            'performer':   100 * ss_fold / ss_total,
            'architecture': 100 * ss_arch / ss_total,
            'interaction': 100 * ss_inter / ss_total,
            'seed':        100 * ss_seed / ss_total,
        },
        'closure': 100 * (ss_fold + ss_arch + ss_inter + ss_seed) / ss_total,
        'arch_mean': arch_mean, 'fold_mean': fold_mean,
        'seed_sd_median': st.median(seed_sds),
        'seed_sd_max': max(seed_sds),
        'arch_range': max(arch_mean.values()) - min(arch_mean.values()),
        'fold_range': max(fold_mean.values()) - min(fold_mean.values()),
    }


out = {}
for prof, root in ROOTS.items():
    runs = harvest(root)
    if not runs:
        print('%s: KHONG tim thay run nao' % prof)
        continue
    res = decompose(runs)
    out[prof] = res
    print('=== %s ===' % prof)
    print('  runs=%d (%d fold x %d arch x %d seed)  closure=%.4f%%'
          % (res['n_runs'], res['folds'], res['archs'], res['seeds'], res['closure']))
    for k in ('performer', 'architecture', 'interaction', 'seed'):
        print('  %-13s %6.2f%%' % (k, res['pct'][k]))
    print('  arch range = %.4f | fold range = %.4f | ratio = %.2fx'
          % (res['arch_range'], res['fold_range'], res['fold_range'] / res['arch_range']))
    print('  seed SD: median=%.4f max=%.4f' % (res['seed_sd_median'], res['seed_sd_max']))
    print('  arch means:', {m: round(v, 3) for m, v in sorted(res['arch_mean'].items(),
                                                              key=lambda x: -x[1])})
    print()

json.dump({p: {'pct': r['pct'], 'n_runs': r['n_runs'], 'closure': r['closure'],
               'seed_sd_median': r['seed_sd_median'], 'arch_range': r['arch_range'],
               'fold_range': r['fold_range'],
               'arch_mean': r['arch_mean'], 'fold_mean': r['fold_mean']}
           for p, r in out.items()},
          open('reports/variance_decomposition.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('da ghi reports/variance_decomposition.json')
