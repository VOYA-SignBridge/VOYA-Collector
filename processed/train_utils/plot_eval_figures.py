"""Plot evaluation figures (confusion heatmap, per-class metrics) from eval JSON.

Usage (run from repo root):
    python train_model/train_utils/plot_eval_figures.py \
        --eval_json train_model/processed/train_utils/outputs/eval_YYYYMMDD_HHMMSS.json \
        --out_dir train_model/processed/train_utils/outputs
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import math

import matplotlib.pyplot as plt
import numpy as np

try:
    import seaborn as sns
    SEABORN = True
except Exception:
    SEABORN = False


def plot_confusion(cm: np.ndarray, out_path: Path, figsize=(8, 6), cmap="Blues"):
    plt.figure(figsize=figsize)
    if SEABORN:
        sns.heatmap(cm, annot=True, fmt="d", cmap=cmap)
    else:
        plt.imshow(cm, interpolation="nearest", cmap=cmap)
        plt.colorbar()
        for (i, j), val in np.ndenumerate(cm):
            plt.text(j, i, int(val), ha="center", va="center")
    plt.ylabel("True label")
    plt.xlabel("Predicted label")
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()


def plot_per_class(per_class: list, out_path: Path, figsize=(10, 6)):
    classes = [p["class"] for p in per_class]
    precision = [p["precision"] for p in per_class]
    recall = [p["recall"] for p in per_class]
    f1 = [p["f1"] for p in per_class]

    x = np.arange(len(classes))
    width = 0.25
    plt.figure(figsize=figsize)
    plt.bar(x - width, precision, width, label="Precision")
    plt.bar(x, recall, width, label="Recall")
    plt.bar(x + width, f1, width, label="F1")
    plt.xlabel("Class index")
    plt.xticks(x, [str(c) for c in classes], rotation=90)
    plt.ylabel("Score")
    plt.ylim(0.0, 1.0)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()


def plot_summary(summary: dict, out_dir: Path):
    cm = np.array(summary.get("confusion_matrix", []))
    per_class = summary.get("per_class", [])
    stamp = summary.get("timestamp", "eval")

    out_dir.mkdir(parents=True, exist_ok=True)
    if cm.size:
        plot_confusion(cm, out_dir / f"confusion_{stamp}.png")
    if per_class:
        plot_per_class(per_class, out_dir / f"per_class_{stamp}.png")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--eval_json", type=Path, required=True)
    p.add_argument("--out_dir", type=Path, default=None)
    args = p.parse_args()

    data = json.loads(args.eval_json.read_text(encoding="utf-8"))
    out_dir = args.out_dir or args.eval_json.parent
    plot_summary(data, out_dir)
    print(f"Saved plots to {out_dir}")


if __name__ == "__main__":
    main()
