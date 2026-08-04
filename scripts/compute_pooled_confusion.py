"""Pooled LOSO confusion matrix + per-class F1, per architecture, per profile.

Inference-only: loads the .pt weights already saved by each LOSO run, runs a
forward pass over that fold's held-out test set, and pools the per-fold
confusion matrices into one matrix per architecture. No training happens
here — each checkpoint was already fit; this only asks it questions.

Folds are pooled by matching on LABEL STRING, not tensor index: two folds
were not guaranteed to assign the same class the same integer index (label
maps are built per-split), and summing raw matrices by position without that
check would silently mix rows across classes if any fold ever diverged.

    docker compose exec -T trainer sh -lc \
        'cd /workspace && python scripts/compute_pooled_confusion.py'
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import torch  # noqa: E402
from processed.train_utils.models import get_model_class  # noqa: E402
from processed.train_utils.train_tcn import build_loader, compute_test_evaluation  # noqa: E402

FEATURES_ROOT = Path("/dataset/features")

PROFILES = {
    "hoa_de": {
        "root": REPO / "processed/train_utils/outputs/loso/hoa_de_loso_v11"
                       / "isds2026_v11" / "hoa_de" / "hoa_de_loso_v11",
        "out": REPO / "reports" / "confusion_hoa_de.json",
    },
    "alphabet": {
        "root": REPO / "processed/train_utils/outputs/loso/alphabet_loso_v13"
                       / "isds2026_v13" / "alphabet" / "alphabet_loso_v13",
        "out": REPO / "reports" / "confusion_alphabet.json",
    },
}


def find_checkpoints(root: Path):
    """Yield (fold, model_type, seed, pt_path) for every saved checkpoint."""
    for fold_dir in sorted(root.glob("test_*")):
        fold = fold_dir.name.replace("test_", "")
        for model_dir in sorted(fold_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            for seed_dir in sorted(model_dir.glob("seed_*")):
                pts = list(seed_dir.glob("*.pt"))
                if pts:
                    yield fold, model_dir.name, seed_dir.name, pts[0]


@torch.no_grad()
def evaluate_one(pt_path: Path, device: str, model_type: str):
    ckpt = torch.load(pt_path, map_location="cpu", weights_only=False)
    # ckpt["model_type"] is a display label ("BiGRU + Attention", "TCN" — the
    # latter hardcoded in build_checkpoint() regardless of actual architecture)
    # and is NOT a valid registry key. The directory name is: sweep scripts lay
    # checkpoints out as .../<fold>/<registry_key>/seed_<n>/*.pt, so it is passed
    # in by the caller instead of trusted from the checkpoint's own field.
    label_to_idx = ckpt["label_to_idx"]
    num_classes = ckpt["num_classes"]
    in_dim = ckpt.get("feature_dim") or ckpt.get("in_dim")

    model_class = get_model_class(model_type)
    config = ckpt.get("model_config") or ckpt.get("config") or {}
    model = model_class.from_config(input_dim=in_dim, output_dim=num_classes, config=config)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device).eval()

    test_csv = pt_path.parent / "test.csv"
    label_json = pt_path.parent / "label_to_index.json"
    loader = build_loader(
        test_csv, batch_size=32, shuffle=False, num_workers=0,
        features_root=FEATURES_ROOT, label_to_index_json=label_json,
        feature_dim=in_dim, seed=42,
    )
    result = compute_test_evaluation(model, loader, device, num_classes, label_to_idx)
    return result  # {"labels", "confusion_matrix", "per_class"}


def pool_by_label(results: list[dict]) -> dict:
    """Sum confusion matrices across folds/seeds, aligned by label string."""
    all_labels = sorted({lab for r in results for lab in r["labels"]})
    idx = {lab: i for i, lab in enumerate(all_labels)}
    n = len(all_labels)
    pooled = [[0] * n for _ in range(n)]
    for r in results:
        local_labels = r["labels"]
        cm = r["confusion_matrix"]
        for i_local, lab_i in enumerate(local_labels):
            for j_local, lab_j in enumerate(local_labels):
                pooled[idx[lab_i]][idx[lab_j]] += cm[i_local][j_local]

    per_class = []
    for c, lab in enumerate(all_labels):
        tp = pooled[c][c]
        support = sum(pooled[c])
        pred_total = sum(pooled[r][c] for r in range(n))
        precision = tp / pred_total if pred_total else 0.0
        recall = tp / support if support else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        per_class.append({"label": lab, "precision": round(precision, 4),
                           "recall": round(recall, 4), "f1": round(f1, 4), "support": support})
    macro_f1 = sum(p["f1"] for p in per_class) / len(per_class)
    return {"labels": all_labels, "confusion_matrix": pooled,
            "per_class": per_class, "macro_f1": round(macro_f1, 4),
            "n_pooled_runs": len(results)}


def main() -> None:
    # Forced CPU: this container's GPU is a 4GB card already running the 2x2
    # exposure experiment. Two concurrent CUDA processes on it previously wedged
    # the Docker engine badly enough that even `ps` stopped answering (see
    # reports/matched_v13_run.sh). Inference on a held-out fold is <90 samples,
    # trivially fast on CPU, so there is no reason to risk the GPU for it.
    device = "cpu"
    for profile, spec in PROFILES.items():
        root = spec["root"]
        if not root.exists():
            print(f"[BO QUA] {profile}: khong thay {root}")
            continue
        by_model: dict[str, list[dict]] = defaultdict(list)
        n_total = 0
        for fold, model_type, seed, pt in find_checkpoints(root):
            n_total += 1
            try:
                r = evaluate_one(pt, device, model_type)
            except Exception as exc:
                print(f"  [LOI] {profile} {fold} {model_type} {seed}: {exc}")
                continue
            by_model[model_type].append(r)
            print(f"  [{profile}] {fold:8s} {model_type:16s} {seed:9s} "
                  f"macro_f1_fold={sum(p['f1'] for p in r['per_class'])/len(r['per_class']):.4f}")

        out = {}
        for model_type, results in by_model.items():
            pooled = pool_by_label(results)
            out[model_type] = pooled
            print(f"  == {profile}/{model_type}: pooled macro_f1={pooled['macro_f1']:.4f} "
                  f"tren {pooled['n_pooled_runs']} lan chay ==")
            worst = sorted(pooled["per_class"], key=lambda p: p["f1"])[:3]
            for w in worst:
                print(f"      thap nhat: {w['label']:<12s} f1={w['f1']:.3f} support={w['support']}")

        spec["out"].parent.mkdir(parents=True, exist_ok=True)
        spec["out"].write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  -> ghi {spec['out']} ({n_total} checkpoint da doc)\n")


if __name__ == "__main__":
    main()
