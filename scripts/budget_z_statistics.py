"""Paired z statistics for the matched-budget reallocation comparisons.

Reads reports/scaling_3d_v14_bigru_attention_raw.txt (3,402 runs of the
three-dimensional grid) and recomputes, for every matched budget n*r, the
paired difference in macro-F1 between the higher-performer and the
lower-performer allocation.

Pairing unit is (class pool, held-out fold): within each unit, macro-F1 is
averaged over the sampled performer combinations and the three seeds before
the difference is taken. The reported statistic is the one-sample paired z

    z = mean(d) / (sd(d) / sqrt(n_pairs)),   d_i = F1_high(i) - F1_low(i)

Writes reports/budget_z_statistics.json.
"""
import json
import math
import statistics as st
from collections import defaultdict

RAW = 'reports/scaling_3d_v14_bigru_attention_raw.txt'
OUT = 'reports/budget_z_statistics.json'

# Matched budgets: (budget, lower-performer cell, higher-performer cell)
PAIRS = [
    (8,  'n1_r8', 'n2_r4'),
    (12, 'n2_r6', 'n3_r4'),
    (16, 'n2_r8', 'n4_r4'),
    (24, 'n3_r8', 'n4_r6'),
]


def load(path):
    """rows[(C, pool, fold, cell)] -> list of macro-F1 over combos x seeds"""
    rows = defaultdict(list)
    for line in open(path, encoding='utf-8'):
        p = line.split()
        if len(p) >= 9 and p[0].startswith('C=') and 'seed=' in line and p[7] == 'f1':
            C = int(p[0][2:])
            rows[(C, p[1], p[2], p[3])].append(float(p[8]))
    return rows


def paired_z(rows, C, low, high):
    """Both z forms for one vocabulary size and one matched budget.

    z_paired      -- pairs by (class pool, held-out fold); respects the blocking
                     structure of the design. This is the form the thesis reports.
    z_two_sample  -- treats every run as an independent observation. Recovered
                     here because it is the form the earlier draft printed; it
                     ignores that runs share pools, folds, performer
                     combinations and seeds, so it understates the standard
                     error and is anti-conservative.
    """
    units = sorted({(pool, fold) for (c, pool, fold, cell) in rows
                    if c == C and cell in (low, high)})
    diffs, hi_all, lo_all = [], [], []
    for pool, fold in units:
        lo = rows.get((C, pool, fold, low))
        hi = rows.get((C, pool, fold, high))
        if not lo or not hi:
            continue
        diffs.append(st.mean(hi) - st.mean(lo))
        hi_all.extend(hi)
        lo_all.extend(lo)
    if len(diffs) < 2:
        return None
    mean_d = st.mean(diffs)
    sd_d = st.stdev(diffs)
    se = sd_d / math.sqrt(len(diffs))
    se2 = math.sqrt(st.variance(hi_all) / len(hi_all)
                    + st.variance(lo_all) / len(lo_all))
    return {
        'n_pairs': len(diffs),
        'n_runs_per_arm': len(hi_all),
        'mean_gain': mean_d,
        'sd': sd_d,
        'se': se,
        'z_paired': (mean_d / se) if se > 0 else float('nan'),
        'z_two_sample': ((st.mean(hi_all) - st.mean(lo_all)) / se2) if se2 > 0
                        else float('nan'),
    }


rows = load(RAW)
total_runs = sum(len(v) for v in rows.values())
out = {'source': RAW, 'total_runs': total_runs, 'results': {}}

print('runs doc duoc: %d' % total_runs)
print()
print('%-7s %-4s %-14s %6s %8s %10s %12s' %
      ('budget', 'C', 'so sanh', 'n_cap', 'gain', 'z_paired', 'z_two_sample'))
print('-' * 70)

pair_zs, two_zs = {'low': [], 'high': []}, {'low': [], 'high': []}
for budget, low, high in PAIRS:
    for C in (5, 10, 30):
        r = paired_z(rows, C, low, high)
        if r is None:
            continue
        key = 'budget%d_C%d' % (budget, C)
        out['results'][key] = dict(r, budget=budget, C=C, low=low, high=high)
        # "fewer than three performers" = the lower-n arm has n < 3
        region = 'low' if int(low[1]) < 3 else 'high'
        pair_zs[region].append(r['z_paired'])
        two_zs[region].append(r['z_two_sample'])
        print('%-7d %-4d %-14s %6d %8.4f %10.2f %12.2f' %
              (budget, C, '%s->%s' % (low, high), r['n_pairs'],
               r['mean_gain'], r['z_paired'], r['z_two_sample']))

print()
for region, label in (('low', 'duoi ba nguoi ky'), ('high', 'tu ba nguoi ky tro len')):
    out['ranges_' + region] = {
        'z_paired': [min(pair_zs[region]), max(pair_zs[region])],
        'z_two_sample': [min(two_zs[region]), max(two_zs[region])],
    }
    print('%-24s z_paired %.2f-%.2f | z_two_sample %.2f-%.2f' %
          (label, min(pair_zs[region]), max(pair_zs[region]),
           min(two_zs[region]), max(two_zs[region])))

json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print()
print('da ghi %s' % OUT)
