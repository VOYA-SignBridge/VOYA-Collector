from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import List

import numpy as np
import torch

try:
    # prefer package import when run as module
    from .dataset_loader import pad_collate_fn, NPZSignDataset
    from .train_tcn import TCNClassifier
except Exception:  # pragma: no cover
    import sys
    from pathlib import Path as _P

    sys.path.append(str(_P(__file__).resolve().parents[2]))
    from train_model.train_utils.dataset_loader import pad_collate_fn, NPZSignDataset  # type: ignore
    from train_model.train_utils.train_tcn import TCNClassifier  # type: ignore

from torch.utils.data import DataLoader


def build_loader(csv_path: Path, batch_size: int, shuffle: bool, num_workers: int) -> DataLoader:
    ds = NPZSignDataset(csv_path, to_tensor=True)
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle, collate_fn=pad_collate_fn, num_workers=num_workers)


def evaluate_collect(model: torch.nn.Module, loader: DataLoader, device: str):
    model.eval()
    all_preds: List[int] = []
    all_targets: List[int] = []
    criterion = torch.nn.CrossEntropyLoss()
    total_loss = 0.0
    total_n = 0
    with torch.no_grad():
        for X, y, lengths, _ in loader:
            X = X.to(device)
            y = y.to(device)
            lengths = lengths.to(device)
            logits = model(X, lengths)
            loss = criterion(logits, y)
            bs = y.size(0)
            total_loss += loss.item() * bs
            total_n += bs
            preds = logits.argmax(1).cpu().numpy()
            targets = y.cpu().numpy()
            all_preds.extend(int(p) for p in preds)
            all_targets.extend(int(t) for t in targets)

    avg_loss = total_loss / total_n if total_n > 0 else 0.0
    acc = float((np.array(all_preds) == np.array(all_targets)).sum() / len(all_preds)) if all_preds else 0.0

    return avg_loss, acc, all_preds, all_targets


def compute_confusion_and_perclass(preds: List[int], targets: List[int], num_classes: int):
    cm = np.zeros((num_classes, num_classes), dtype=int)
    for t, p in zip(targets, preds):
        if 0 <= t < num_classes and 0 <= p < num_classes:
            cm[t, p] += 1
    per_class = []
    for c in range(num_classes):
        tp = int(cm[c, c])
        fp = int(cm[:, c].sum() - tp)
        fn = int(cm[c, :].sum() - tp)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        per_class.append({"class": c, "tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1})
    macro_f1 = float(sum(item["f1"] for item in per_class) / len(per_class)) if per_class else 0.0
    return cm.tolist(), per_class, macro_f1


def main():
    p = argparse.ArgumentParser(description="Evaluate TCN checkpoint and export confusion matrix + metrics.")
    p.add_argument("--ckpt", type=Path, required=True)
    p.add_argument("--test_csv", type=Path, default=Path("processed/splits/test.csv"))
    p.add_argument("--batch_size", type=int, default=32)
    p.add_argument("--num_workers", type=int, default=4)
    p.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--out_dir", type=Path, default=None)
    args = p.parse_args()

    device = args.device

    # allowlist pathlib.WindowsPath for older torch CPU pickles that stored Paths
    try:
        import pathlib

        torch.serialization.add_safe_globals([pathlib.WindowsPath])
    except Exception:
        pass
    ckpt = torch.load(args.ckpt, map_location=device, weights_only=False)
    ckpt_config = ckpt.get("config", {})
    in_dim = ckpt.get("in_dim")
    num_classes = int(ckpt.get("num_classes", ckpt_config.get("num_classes", 1)))

    # Build model using saved config where possible
    channels = int(ckpt_config.get("channels", 64))
    levels = int(ckpt_config.get("levels", 3))
    kernel_size = int(ckpt_config.get("kernel_size", 5))
    dropout = float(ckpt_config.get("dropout", 0.3))

    if in_dim is None:
        # infer from dataset
        ds = NPZSignDataset(args.test_csv, to_tensor=True)
        x0, _, _ = ds[0]
        in_dim = int(x0.shape[1] if x0.ndim >= 2 else 1)

    model = TCNClassifier(in_dim=in_dim, num_classes=num_classes, channels=channels, levels=levels, kernel_size=kernel_size, dropout=dropout)
    model.load_state_dict(ckpt["model_state"])  # type: ignore[index]
    model.to(device)

    loader = build_loader(args.test_csv, args.batch_size, shuffle=False, num_workers=args.num_workers)

    loss, acc, preds, targets = evaluate_collect(model, loader, device)
    cm, per_class, macro_f1 = compute_confusion_and_perclass(preds, targets, num_classes)

    out_dir = args.out_dir or args.ckpt.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary = {
        "timestamp": stamp,
        "checkpoint": str(args.ckpt),
        "test_csv": str(args.test_csv),
        "num_samples": len(preds),
        "loss": loss,
        "accuracy": acc,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion_matrix": cm,
    }

    out_json = out_dir / f"eval_{stamp}.json"
    out_csv = out_dir / f"confusion_{stamp}.csv"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # save confusion matrix as CSV (rows=true, cols=pred)
    import csv as _csv

    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = _csv.writer(fh)
        writer.writerow([""] + [f"pred_{i}" for i in range(num_classes)])
        for i, row in enumerate(cm):
            writer.writerow([f"true_{i}"] + row)

    print(f"Saved evaluation summary to {out_json}")
    print(f"Saved confusion CSV to {out_csv}")


if __name__ == "__main__":
    main()
