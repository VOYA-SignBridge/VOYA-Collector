#!/usr/bin/env python3
"""Regenerate Figure 2 — per-class frame-to-frame motion, fingerspelling subset.

Reads the precomputed statistic in ``reports/motion_by_class.json`` (mean L2
displacement between consecutive frames, per class) and draws the horizontal bar
chart used in the paper. The JSON is released, so this figure is reproducible
WITHOUT access to the private landmark files.

    python reports/make_fig2_motion.py

The figure makes one point: the declared motion type and the measured motion
agree for twenty-nine of the thirty classes, and disagree for Q. Eight letters
are dynamic by linguistic definition — Z, R and the six diacritic vowels, each
carrying a stroke — and they measure between 0.13 and 0.25. The twenty-one other
static letters measure between 0.03 and 0.12. Q is declared static and measures
0.17, above every other static class and inside the dynamic band, with the
largest within-class spread of the thirty. The shaded band marks the motion range
spanned by the Hòa Đê word signs, so Q can be read against it directly.

Both the class list and the static/dynamic split come from the catalog, so this
figure cannot drift out of step with the tables.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

# Two hues only: identity here is binary (static vs dynamic label), and the
# blue/orange pair stays separable under all common CVD types. Q is additionally
# given a hatch + a direct label so it never depends on colour alone.
COLOR_STATIC = "#2077cc"
COLOR_DYNAMIC = "#f4642a"
COLOR_BAND = "#fdf0e9"
COLOR_ERR = "#8a8a8a"

def _declared_motion(labels_csv: Path) -> dict:
    """slug -> motion_type, read from the catalog rather than hard-coded here.

    The previous version pinned {"z"} as the only dynamic letter. That went stale
    the moment the seven Vietnamese letters were recorded: R and the six diacritic
    vowels each carry a stroke and are declared dynamic too. Reading the catalog
    means the figure and the tables cannot disagree about what a class is.
    """
    import csv
    out = {}
    with labels_csv.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if (row.get("dialect") or "") == "bang-chu-cai":
                out[row["slug"]] = (row.get("motion_type") or "").strip()
    return out


def build_figure(motion: dict, out_path: Path, declared: dict) -> None:
    alphabet = {k: v for k, v in motion["alphabet"].items() if not k.startswith("_")}
    hoa_de = {k: v for k, v in motion["hoa_de"].items() if not k.startswith("_")}

    DYNAMIC_LETTERS = {s for s, m in declared.items() if m == "dynamic"}
    # A class whose declared type is static but whose measured motion exceeds
    # every other static class. Derived, not asserted: if a recollection fixes
    # the class, the hatch disappears on its own.
    static_means = {s: v["mean"] for s, v in alphabet.items()
                    if declared.get(s) == "static"}
    ANOMALOUS_LETTERS = set()
    if len(static_means) > 1:
        ranked = sorted(static_means.items(), key=lambda kv: -kv[1])
        if ranked[0][1] > ranked[1][1] * 1.25:
            ANOMALOUS_LETTERS = {ranked[0][0]}

    # Descending by mean, drawn top-down: the outliers land at the top where
    # they are read first.
    ordered = sorted(alphabet.items(), key=lambda kv: kv[1]["mean"])
    labels = [name.upper() for name, _ in ordered]
    means = [stats["mean"] for _, stats in ordered]
    stds = [stats["std"] for _, stats in ordered]

    colors, hatches = [], []
    for name, _ in ordered:
        key = name.lower()
        colors.append(COLOR_DYNAMIC if key in DYNAMIC_LETTERS else COLOR_STATIC)
        hatches.append("//" if key in ANOMALOUS_LETTERS else "")

    band_lo = min(s["mean"] for s in hoa_de.values())
    band_hi = max(s["mean"] for s in hoa_de.values())

    fig, ax = plt.subplots(figsize=(12.5, 9.5))

    ax.axvspan(band_lo, band_hi, color=COLOR_BAND, zorder=0)
    ax.text(
        (band_lo + band_hi) / 2, len(labels) / 2 - 0.5,
        "vùng ký hiệu từ\n(hoa-de, đều động)",
        rotation=90, ha="center", va="center", style="italic",
        fontsize=13, color="#7a7a7a", zorder=1,
    )

    bars = ax.barh(
        labels, means, xerr=stds,
        color=colors, edgecolor="white", linewidth=0.0,
        error_kw={"ecolor": COLOR_ERR, "elinewidth": 1.0, "capsize": 3},
        zorder=2,
    )
    for bar, hatch in zip(bars, hatches):
        if hatch:
            bar.set_hatch(hatch)

    # Direct labels on the two outliers only — a number on every bar would be noise.
    for name, stats, mean, std in zip(
        [n for n, _ in ordered], [s for _, s in ordered], means, stds
    ):
        key = name.lower()
        if key in ANOMALOUS_LETTERS:
            ax.text(mean + std + 0.02, labels.index(name.upper()),
                    f"{mean:.2f} — nhãn tĩnh, bất thường",
                    va="center", fontsize=13, fontweight="bold", color="#1a1a1a")
        elif key in DYNAMIC_LETTERS:
            ax.text(mean + std + 0.02, labels.index(name.upper()),
                    f"{mean:.2f}",
                    va="center", fontsize=13, fontweight="bold", color=COLOR_DYNAMIC)

    # An anomalous class keeps the static colour: its *label* is static, which is
    # the whole point of the figure. The hatch marks the disagreement.
    n_static = sum(1 for n, _ in ordered if n.lower() not in DYNAMIC_LETTERS)
    n_dyn = len(ordered) - n_static
    handles = [
        Patch(facecolor=COLOR_STATIC, label=f"Tĩnh ({n_static} chữ)"),
        Patch(facecolor=COLOR_DYNAMIC, label=f"Động ({n_dyn} chữ — Z, R, chữ có dấu)"),
    ]
    for a in sorted(ANOMALOUS_LETTERS):
        handles.append(Patch(facecolor=COLOR_STATIC, hatch="//", edgecolor="white",
                             label=f"{a.upper()} — nhãn tĩnh, đo được bất thường"))
    ax.legend(handles=handles, loc="lower right", fontsize=13, frameon=False)

    ax.set_xlabel("Chuyển động khung-kề-khung trung bình (đơn vị chuẩn hoá)", fontsize=14)
    ax.set_title("Chuyển động theo lớp — bảng chữ cái ngón tay",
                 fontsize=18, fontweight="bold", pad=16)
    ax.set_xlim(0, band_hi + 0.03)
    ax.tick_params(labelsize=13)
    ax.xaxis.grid(True, color="#dddddd", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color("#bbbbbb")
    ax.spines["bottom"].set_color("#bbbbbb")

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    print(f"wrote {out_path}")
    print(f"  {len(labels)} classes; hoa-de band {band_lo:.3f}–{band_hi:.3f}")


def main() -> None:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--motion", type=Path, default=here / "motion_by_class.json")
    parser.add_argument("--out", type=Path, default=here / "fig2_motion_by_class.png")
    args = parser.parse_args()

    motion = json.loads(args.motion.read_text(encoding="utf-8"))
    declared = _declared_motion(here.parent / "dataset" / "labels.csv")
    build_figure(motion, args.out, declared)


if __name__ == "__main__":
    main()
