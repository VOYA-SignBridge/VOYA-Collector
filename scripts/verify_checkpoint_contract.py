"""Reload a checkpoint, validate its contract v2, and re-evaluate the test set.

Usage (inside the trainer/backend container — needs torch):
    python scripts/verify_checkpoint_contract.py \
        --checkpoint processed/train_utils/outputs/isds2026_v2/hoa_de/.../tcn_*.pt \
        --test_csv processed/splits/versions/hoa_de_sample_v2/test.csv \
        --features_root dataset/features

Verifies:
  1. required contract v2 keys present (profile, dataset/split version, label
     maps, common/profile label lists, seed, git_commit, manifest checksum);
  2. label lists are consistent with label_to_idx and the declared profile
     (a hoa_de checkpoint must contain ONLY vn/common/* + vn/hoa_de/* keys);
  3. the model rebuilds from model_config and reproduces the stored test
     accuracy on the referenced test split (tolerance --tol).

Exit 0 = contract valid + metrics reproduced.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from processed.train_utils.dataset_loader import NPZSignDataset  # noqa: E402
from processed.train_utils.models import get_model_class  # noqa: E402

REQUIRED_V2_KEYS = [
    "model_type", "recognition_profile", "include_common", "dataset_version",
    "split_version", "vocabulary_schema_version", "normalization_version",
    "seq_len", "feature_dim", "label_to_idx", "idx_to_label",
    "common_labels", "profile_specific_labels", "num_classes", "seed",
    "git_commit", "training_config", "dataset_manifest_checksum",
    "preprocess_contract_version", "storage_contract_version", "motion_types_present",
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--test_csv", type=Path, required=True)
    ap.add_argument("--features_root", type=Path, default=REPO_ROOT / "dataset" / "features")
    ap.add_argument("--label_map_json", type=Path, default=None,
                    help="label_to_index.json of the run (default: next to test_csv's run dir)")
    ap.add_argument("--tol", type=float, default=1e-6)
    args = ap.parse_args()

    ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    print(f"== Contract fields ({args.checkpoint.name}) ==")
    missing = [k for k in REQUIRED_V2_KEYS if k not in ckpt]
    for k in REQUIRED_V2_KEYS:
        v = ckpt.get(k)
        if k in ("label_to_idx", "idx_to_label"):
            v = f"<{len(v or {})} entries>"
        elif k in ("common_labels", "profile_specific_labels"):
            v = f"<{len(v or [])} labels>"
        elif k == "training_config":
            v = f"<config: aug={ (v or {}).get('augmentation', {}).get('profile') }>"
        print(f"  {k}: {v}")
    if missing:
        print(f"[FAIL] missing contract keys: {missing}")
        return 1

    profile = str(ckpt["recognition_profile"])
    keys = list(ckpt["label_to_idx"].keys())
    allowed_prefixes = {"vn/common/"}
    if profile == "unified":
        from processed.shared.vocabulary import RECOGNITION_PROFILES
        allowed_prefixes |= {f"vn/{p}/" for p in RECOGNITION_PROFILES}
    elif profile:
        allowed_prefixes.add(f"vn/{profile}/")
    bad = [k for k in keys if not any(k.startswith(p) for p in allowed_prefixes)]
    if bad:
        print(f"[FAIL] label keys outside profile scope '{profile}': {bad[:5]}")
        return 1
    declared = set(ckpt["common_labels"]) | set(ckpt["profile_specific_labels"])
    if declared != set(keys):
        print(f"[FAIL] common+profile label lists != label_to_idx keys "
              f"(diff: {set(keys) ^ declared})")
        return 1
    print(f"[OK] label space: {len(keys)} classes, all within common+{profile or 'n/a'}; "
          f"common={len(ckpt['common_labels'])} profile={len(ckpt['profile_specific_labels'])}")

    # Rebuild + evaluate
    model_type_raw = str(ckpt.get("training_config", {}).get("model_type") or "tcn")
    model_cls = get_model_class(model_type_raw)
    model = model_cls.from_config(
        input_dim=int(ckpt["feature_dim"]),
        output_dim=int(ckpt["num_classes"]),
        config=dict(ckpt.get("model_config") or {}),
    )
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    label_map_json = args.label_map_json or (args.test_csv.parent / "label_to_index.json")
    # Profile-run test CSV lives in the run dir alongside label_to_index.json;
    # when pointing at the split-version test.csv instead, pass --label_map_json.
    ds = NPZSignDataset(args.test_csv, root=args.features_root,
                        label_to_index_json=(label_map_json if Path(label_map_json).exists() else None),
                        to_tensor=True)
    if len(ds) == 0:
        print("[FAIL] empty test dataset")
        return 1

    correct = 0
    with torch.inference_mode():
        for i in range(len(ds)):
            x, y, _ = ds[i]
            pred = model(x.unsqueeze(0)).argmax(1).item()
            correct += int(pred == int(y))
    acc = correct / len(ds)
    stored = ckpt.get("metrics", {}).get("test_acc")
    print(f"[OK] re-evaluated test accuracy: {acc:.6f} on {len(ds)} samples "
          f"(stored: {stored})")
    if stored is not None and abs(acc - float(stored)) > max(args.tol, 1.0 / len(ds)):
        print(f"[FAIL] re-evaluated accuracy differs from stored beyond tolerance")
        return 1
    print("CONTRACT VERIFIED — checkpoint is self-describing and reproducible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
