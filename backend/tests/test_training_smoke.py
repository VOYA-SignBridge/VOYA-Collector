"""Real training smoke test: run train_tcn for 1 epoch on the existing splits and
assert it exports a valid TCN checkpoint.

This exercises the genuine train -> model-export core (dataset_loader, TCN model,
metrics, checkpoint serialization) end to end — not mocked. It runs whenever the
prerequisites are present (processed/splits/*.csv + torch + sklearn), so on a
data machine it runs (no skip); on a bare CI box it skips.

CPU, 1 epoch, tiny batch — ~30s. It writes only to a tmp out_dir and reads the
existing npz read-only, so it never mutates the dataset or DB.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SPLITS = _REPO / "processed" / "splits"
_SCRIPT = _REPO / "processed" / "train_utils" / "train_tcn.py"

try:
    import sklearn  # noqa: F401
    import torch  # noqa: F401
    _DEPS = True
except Exception:
    _DEPS = False

_HAVE = _SCRIPT.exists() and (_SPLITS / "train.csv").exists() and (_SPLITS / "val.csv").exists()

pytestmark = pytest.mark.skipif(
    not (_HAVE and _DEPS),
    reason="needs processed/splits/*.csv + torch + scikit-learn (data machine / trainer)",
)


def test_train_tcn_one_epoch_exports_a_valid_checkpoint(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    cmd = [
        sys.executable, "-m", "processed.train_utils.train_tcn",
        "--epochs=1", "--batch_size=8", "--device=cpu",
        f"--out_dir={out}", f"--metrics_file={out / 'metrics.jsonl'}",
    ]
    proc = subprocess.run(
        cmd, cwd=str(_REPO), capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, f"training failed:\n{proc.stderr[-3000:]}"

    ckpts = list(out.glob("*.pt"))
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
