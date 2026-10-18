import csv
import hashlib
import io
import json
import zipfile

import numpy as np
import pytest

from app.portable_export import write_feature_bundle


def test_export_relocates_into_real_training_loader_and_optimizer(tmp_path):
    from processed.train_utils.dataset_loader import NPZSignDataset
    from processed.train_utils.models.tcn import TCNModel
    import torch

    source = tmp_path / "source"
    source.mkdir()
    rows, paths = [], []
    for i in range(2):
        path = source / f"sample_{i}.npz"
        sequence = np.random.default_rng(i).normal(size=(60, 126)).astype(np.float32)
        np.savez_compressed(path, sequence=sequence, landmarks_raw=np.zeros((60, 126)), meta={"label": "Xin chào"})
        paths.append(path)
        rows.append({"sample_uid": f"sample-{i}", "class_uid": f"class-{i}",
                     "file_path": str(path), "label_original": "Xin chào", "seq_len": 60})
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as bundle:
        write_feature_bundle(bundle, rows, paths, source, list(rows[0]))
    other_host = tmp_path / "another-host"
    with zipfile.ZipFile(output) as bundle:
        bundle.extractall(other_host)
    for path in paths:
        path.unlink()  # No fallback to source files can make this test pass.
    manifest = json.loads((other_host / "manifest.json").read_text())
    exported = json.loads((other_host / "samples.json").read_text(encoding="utf-8"))
    csv_rows = list(csv.DictReader((other_host / "samples.csv").open(encoding="utf-8")))
    assert [r["file_path"] for r in csv_rows] == [r["file_path"] for r in exported]
    for name, checksum in manifest["sha256"].items():
        assert hashlib.sha256((other_host / name).read_bytes()).hexdigest() == checksum
    dataset = NPZSignDataset(other_host / "samples.csv", root=other_host,
                            class_uid_to_target_idx=manifest["class_uid_to_target_idx"], to_tensor=True)
    assert len(dataset) == 2
    x = torch.stack([dataset[i][0] for i in range(2)])
    y = torch.tensor([int(dataset[i][1]) for i in range(2)])
    model = TCNModel(input_dim=126, output_dim=2, channels=8, levels=1, dropout=0)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    loss = torch.nn.functional.cross_entropy(model(x), y)
    assert torch.isfinite(loss)
    loss.backward()
    optimizer.step()


@pytest.mark.parametrize("issue", ["missing", "outside", "shape", "checksum"])
def test_bad_feature_cannot_be_published(tmp_path, issue):
    path = tmp_path / "sample.npz"
    np.savez_compressed(path, sequence=np.ones((60, 125 if issue == "shape" else 126)))
    row = {"class_uid": "c", "sample_uid": "s", "file_path": str(path)}
    if issue == "missing":
        path.unlink()
    if issue == "checksum":
        row["checksum"] = "0" * 64
    with zipfile.ZipFile(io.BytesIO(), "w") as bundle, pytest.raises(ValueError):
        write_feature_bundle(bundle, [row], [] if issue == "outside" else [path], tmp_path, list(row))
