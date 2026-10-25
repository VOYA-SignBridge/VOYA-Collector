"""Portable ML smoke test: train a tiny TCN and load it through backend inference.

This exercises the genuine train -> model-export core (dataset_loader, TCN model,
metrics, checkpoint serialization and inference model reconstruction) end to end.
The corpus is deterministic and generated under ``tmp_path`` so a clean checkout
does not silently skip the ML contract merely because the private dataset is absent.

CPU, 1 epoch, tiny model. It writes only below ``tmp_path`` and never mutates the
real dataset, model registry or database.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "processed" / "train_utils" / "train_tcn.py"

try:
    import sklearn  # noqa: F401
    import torch  # noqa: F401
    _DEPS = True
except Exception:
    _DEPS = False

pytestmark = pytest.mark.skipif(
    not (_SCRIPT.exists() and _DEPS),
    reason="needs train_tcn.py + torch + scikit-learn",
)


_FIELDS = [
    "sample_id", "folder_name", "file", "file_path", "class_idx",
    "label_key", "label_slug", "label_original", "language", "dialect",
    "signer_id",
]


def _write_tiny_split(path: Path, features_root: Path, split: str, per_class: int) -> None:
    rows = []
    for class_idx, slug in enumerate(("alpha", "beta"), start=1):
        folder = features_root / "vn" / "smoke" / slug
        folder.mkdir(parents=True, exist_ok=True)
        for item in range(per_class):
            filename = f"{split}_{slug}_{item}.npz"
            relative_path = Path("vn") / "smoke" / slug / filename
            rng = np.random.default_rng(10_000 * class_idx + 100 * len(split) + item)
            sequence = rng.normal(
                loc=0.08 * class_idx,
                scale=0.02,
                size=(60, 126),
            ).astype(np.float32)
            # Match the stored wrist-centred representation closely enough for
            # the production normalization path exercised after training.
            sequence[:, (0, 1, 2, 63, 64, 65)] = 0.0
            np.savez_compressed(features_root / relative_path, sequence=sequence)
            rows.append({
                "sample_id": f"{split}-{slug}-{item}",
                "folder_name": slug,
                "file": filename,
                "file_path": relative_path.as_posix(),
                "class_idx": str(class_idx),
                "label_key": f"vn/smoke/{slug}",
                "label_slug": slug,
                "label_original": slug.title(),
                "language": "vn",
                "dialect": "smoke",
                "signer_id": f"signer-{item % 2}",
            })
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_train_tcn_one_epoch_exports_and_serves_checkpoint(tmp_path, monkeypatch):
    features = tmp_path / "features"
    splits = tmp_path / "splits"
    splits.mkdir()
    _write_tiny_split(splits / "train.csv", features, "train", per_class=2)
    _write_tiny_split(splits / "val.csv", features, "val", per_class=1)
    _write_tiny_split(splits / "test.csv", features, "test", per_class=1)

    out = tmp_path / "out"
    out.mkdir()
    cmd = [
        sys.executable, "-m", "processed.train_utils.train_tcn",
        f"--train_csv={splits / 'train.csv'}",
        f"--val_csv={splits / 'val.csv'}",
        f"--test_csv={splits / 'test.csv'}",
        f"--features_root={features}",
        "--dialect=smoke", "--tag=portable-smoke",
        "--epochs=1", "--batch_size=4", "--device=cpu",
        "--channels=8", "--levels=1", "--kernel_size=3",
        "--augmentation_profile=none", "--num_workers=0",
        f"--out_dir={out}", f"--metrics_file={out / 'metrics.jsonl'}",
    ]
    proc = subprocess.run(
        cmd, cwd=str(_REPO), capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, f"training failed:\n{proc.stderr[-3000:]}"

    ckpts = list(out.rglob("*.pt"))
    assert ckpts, f"no .pt checkpoint produced. stdout tail:\n{proc.stdout[-1500:]}"

    import torch
    ck = torch.load(ckpts[0], map_location="cpu", weights_only=False)
    # The exported model carries everything realtime/promote needs.
    assert ck.get("model_type") == "TCN"
    assert "model_state_dict" in ck
    assert ck.get("feature_dim") == 126
    assert ck.get("num_classes", 0) > 0
    assert isinstance(ck.get("idx_to_label"), dict) and ck["idx_to_label"]
    # a metrics block was recorded
    assert "metrics" in ck

    # Exercise the same trusted loader, architecture registry, normalization and
    # label decoding used by POST /training/jobs/{job_id}/predict. The temporary
    # output is explicitly made an allowed checkpoint root for this test only.
    from app.modules.training.inference_service import predict_checkpoint
    from app.routers import training as training_router

    monkeypatch.setattr(training_router, "OUTPUTS_DIR", out)
    monkeypatch.setattr(training_router, "CHECKPOINTS_DIR", out)
    monkeypatch.setattr(training_router, "REALTIME_CHECKPOINTS_DIR", out)
    probe = np.load(features / "vn" / "smoke" / "alpha" / "test_alpha_0.npz")["sequence"]
    prediction = predict_checkpoint(
        ckpts[0],
        probe.tolist(),
        workspace_root=_REPO,
        labels_csv=tmp_path / "labels.csv",
    )
    assert prediction.label_key in {"vn/smoke/alpha", "vn/smoke/beta"}
    assert 0.0 <= prediction.confidence <= 1.0
