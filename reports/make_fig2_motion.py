#!/usr/bin/env python3
"""Regenerate Figure 2 — per-class frame-to-frame motion, fingerspelling subset.

Reads the precomputed statistic in ``reports/motion_by_class.json`` (mean L2
displacement between consecutive frames, per class) and draws the horizontal bar
chart used in the paper. The JSON is released, so this figure is reproducible
WITHOUT access to the private landmark files.

    python reports/make_fig2_motion.py

The figure makes one point: Q and Z sit far above the other fingerspelling
classes. Z is expected — it is a genuinely dynamic letter in the language. Q is
not: it is a static letter whose samples nevertheless carry word-sign levels of
motion, which is the data-quality contamination discussed in the paper. The
shaded band marks the motion range actually spanned by the Hòa Đê word signs,
so Q can be read against it directly.
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

DYNAMIC_LETTERS = {"z"}      # dynamic by linguistic definition
ANOMALOUS_LETTERS = {"q"}    # static label, anomalous measured motion


def build_figure(motion: dict, out_path: Path) -> None:
    alphabet = motion["alphabet"]
    hoa_de = motion["hoa_de"]

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

    # Q counts as static: its *label* is static, which is the whole point of the
    # figure. Only Z is dynamic by linguistic definition.
    n_static = sum(1 for n, _ in ordered if n.lower() not in DYNAMIC_LETTERS)
    ax.legend(
        handles=[
            Patch(facecolor=COLOR_STATIC, label=f"Tĩnh ({n_static} chữ)"),
            Patch(facecolor=COLOR_DYNAMIC, label="Động — Z (nhãn ngôn ngữ)"),
            Patch(facecolor=COLOR_STATIC, hatch="//", edgecolor="white",
                  label="Q — nhãn tĩnh, bất thường"),
        ],
        loc="lower right", fontsize=13, frameon=False,
    )

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
    build_figure(motion, args.out)


if __name__ == "__main__":
    main()
