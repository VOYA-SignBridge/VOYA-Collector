"""Regenerate the matched-budget reallocation figure (thesis Figure 5.6).

Bar heights are the mean macro-F1 gain from the two-performer to the
four-performer allocation at a fixed budget of sixteen recordings per class;
annotations carry the paired z statistic.

Both are read from reports/budget_z_statistics.json so the figure cannot drift
away from the artifact that Chapter 5 cites. Run scripts/budget_z_statistics.py
first if that file is missing.

Usage:  python scripts/make_fig_budget16.py [--two-sample]

    --two-sample   annotate with the pooled two-sample z instead of the paired
                   z. Provided only to reproduce the earlier draft; the paired
                   form is the default and the one the thesis reports.
"""
import argparse
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SRC = 'reports/budget_z_statistics.json'
OUT = 'reports/fig_budget16_reallocation.png'
BUDGET = 16
VOCABS = [5, 10, 30]

ap = argparse.ArgumentParser()
ap.add_argument('--two-sample', action='store_true',
                help='annotate with pooled two-sample z (earlier draft form)')
ap.add_argument('--out', default=OUT)
args = ap.parse_args()

if not os.path.exists(SRC):
    raise SystemExit('missing %s - run scripts/budget_z_statistics.py first' % SRC)

data = json.load(open(SRC, encoding='utf-8'))['results']
zkey = 'z_two_sample' if args.two_sample else 'z_paired'

gains, zs = [], []
for C in VOCABS:
    r = data['budget%d_C%d' % (BUDGET, C)]
    gains.append(r['mean_gain'])
    zs.append(r[zkey])

fig, ax = plt.subplots(figsize=(7.2, 4.6))

x = range(len(VOCABS))
bars = ax.bar(x, gains, width=0.55,
              color='#cccccc', edgecolor='black', linewidth=0.9, zorder=3)

for xi, g, z in zip(x, gains, zs):
    ax.annotate('%.3f\n(z=%.2f)' % (g, z),
                xy=(xi, g), xytext=(0, 6), textcoords='offset points',
                ha='center', va='bottom', fontsize=10, linespacing=1.35,
                zorder=4)

ax.set_xticks(list(x))
ax.set_xticklabels([str(c) for c in VOCABS])
ax.set_xlabel('Vocabulary size (classes)')
ax.set_ylabel('Macro-F1 gain: 2→4 performers at budget %d' % BUDGET)
ax.set_ylim(0.0, 0.200)
ax.set_yticks([i * 0.025 for i in range(9)])
ax.tick_params(direction='out', length=3.5)
for s in ax.spines.values():
    s.set_linewidth(0.9)

fig.tight_layout()
fig.savefig(args.out, dpi=300)
print('gain :', ['%.4f' % g for g in gains])
print('z    : %s -> %s' % (zkey, ['%.2f' % z for z in zs]))
print('da ghi %s' % args.out)
