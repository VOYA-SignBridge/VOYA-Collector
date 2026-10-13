"""Regenerate the matched-budget reallocation figure (thesis Figure 5.6).

Bar heights are the mean macro-F1 gain from the two-performer to the
four-performer allocation at a fixed budget of sixteen recordings per class;
annotations carry the paired z statistic.

Both are read from reports/budget_z_statistics.json so the figure cannot drift
away from the artifact that Chapter 5 cites. Run scripts/evaluation/budget_z_statistics.py
first if that file is missing.

Usage:  python scripts/evaluation/make_fig_budget16.py [--two-sample]

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

def main() -> int:
    """Đọc báo cáo thống kê rồi tạo hình so sánh ngân sách 16 mẫu."""
    ap = argparse.ArgumentParser()
    ap.add_argument('--two-sample', action='store_true',
                    help='annotate with pooled two-sample z (earlier draft form)')
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    if not os.path.exists(SRC):
        raise SystemExit(
            'missing %s - run scripts/evaluation/budget_z_statistics.py first' % SRC)

    with open(SRC, encoding='utf-8') as source:
        data = json.load(source)['results']
    zkey = 'z_two_sample' if args.two_sample else 'z_paired'

    gains, zs = [], []
    for vocab_size in VOCABS:
        result = data['budget%d_C%d' % (BUDGET, vocab_size)]
        gains.append(result['mean_gain'])
        zs.append(result[zkey])

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    x = range(len(VOCABS))
    ax.bar(x, gains, width=0.55, color='#cccccc', edgecolor='black',
           linewidth=0.9, zorder=3)

    for xi, gain, z_value in zip(x, gains, zs):
        ax.annotate('%.3f\n(z=%.2f)' % (gain, z_value),
                    xy=(xi, gain), xytext=(0, 6), textcoords='offset points',
                    ha='center', va='bottom', fontsize=10, linespacing=1.35,
                    zorder=4)

    ax.set_xticks(list(x))
    ax.set_xticklabels([str(c) for c in VOCABS])
    ax.set_xlabel('Vocabulary size (classes)')
    ax.set_ylabel('Macro-F1 gain: 2→4 performers at budget %d' % BUDGET)
    ax.set_ylim(0.0, 0.200)
    ax.set_yticks([i * 0.025 for i in range(9)])
    ax.tick_params(direction='out', length=3.5)
    for spine in ax.spines.values():
        spine.set_linewidth(0.9)

    fig.tight_layout()
    fig.savefig(args.out, dpi=300)
    plt.close(fig)
    print('gain :', ['%.4f' % gain for gain in gains])
    print('z    : %s -> %s' % (zkey, ['%.2f' % z for z in zs]))
    print('da ghi %s' % args.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
