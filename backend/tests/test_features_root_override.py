"""`--features_root` must actually change which files are read.

It did not. `NPZSignDataset._resolve_feature_path` consulted the split CSV's
`file_path` column first, and that column always resolves for a freshly built
split — so an explicitly named root was accepted, echoed back in the run config,
and then ignored for every single row.

The damage this does is specific and nasty: it does not crash, it does not warn,
and it does not even produce odd numbers. Any experiment that swaps the feature
tree — a preprocessing ablation, a rebuilt corpus, a restored backup — quietly
trains both arms on the ORIGINAL tree and reports that the change made no
difference. It was caught only because two of three seeds in the hands126_v1 vs
v2 ablation came back equal to sixteen decimal places, which is not something
two different inputs do.

Guarded here rather than in the ablation script because the defect is in the
loader: every future experiment inherits it.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from processed.train_utils.dataset_loader import NPZSignDataset  # noqa: E402

ROW = {
    "file_path": "dataset/features/vn/bang-chu-cai/class_a_1234/sample_aa.npz",
    "folder_name": "class_a_1234",
    "file": "sample_aa.npz",
    "language": "vn",
    "dialect": "bang-chu-cai",
    "label_key": "vn/alphabet/a",
}

REL = Path("vn/bang-chu-cai/class_a_1234/sample_aa.npz")


def _dataset(root: Path | None) -> NPZSignDataset:
    """Build the object without running __init__ (which reads a CSV)."""
    ds = NPZSignDataset.__new__(NPZSignDataset)
    ds.root = root if root is not None else REPO / "dataset" / "features"
    ds.root_is_explicit = root is not None
    return ds


@pytest.fixture
def two_trees(tmp_path):
    """Two feature trees holding the SAME sample under the same relative path."""
    made = {}
    for arm, value in (("v1", 1.0), ("v2", 2.0)):
        p = tmp_path / arm / REL
        p.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(p, sequence=np.full((4, 126), value, dtype=np.float32))
        made[arm] = tmp_path / arm
    # The path the CSV remembers — deliberately also real, which is the whole
    # point: the bug only appears when `file_path` resolves.
    legacy = tmp_path / "legacy" / REL
    legacy.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(legacy, sequence=np.zeros((4, 126), dtype=np.float32))
    made["legacy"] = legacy
    return made


def test_explicit_root_wins_over_the_csv_path(two_trees):
    row = dict(ROW, file_path=str(two_trees["legacy"]))
    for arm in ("v1", "v2"):
        resolved = _dataset(two_trees[arm])._resolve_feature_path(row)
        assert resolved == two_trees[arm] / REL, (
            f"--features_root={two_trees[arm]} was ignored; read {resolved} instead"
        )


def test_two_roots_really_yield_different_data(two_trees):
    """The property an ablation actually depends on."""
    row = dict(ROW, file_path=str(two_trees["legacy"]))
    seqs = []
    for arm in ("v1", "v2"):
        with np.load(_dataset(two_trees[arm])._resolve_feature_path(row)) as d:
            seqs.append(np.asarray(d["sequence"]))
    assert not np.array_equal(seqs[0], seqs[1]), (
        "both arms read identical bytes — this is exactly how the first z-fix "
        "ablation produced two seeds agreeing to sixteen decimal places"
    )


def test_without_an_explicit_root_the_csv_path_still_wins(two_trees):
    """The default path must not change. Callers that pass no root have always
    relied on `file_path`, and breaking them to fix the override would trade one
    silent failure for another."""
    row = dict(ROW, file_path=str(two_trees["legacy"]))
    assert _dataset(None)._resolve_feature_path(row) == two_trees["legacy"]


def test_explicit_root_falls_back_when_the_sample_is_absent(two_trees, tmp_path):
    """An arm tree that covers only part of the corpus must not silently read
    the other rows from somewhere else... but it must also not crash on a row it
    legitimately cannot serve. Falling back to `file_path` is the documented
    behaviour; the ablation guards coverage separately by filtering the manifest
    to exactly the samples both arms contain."""
    empty = tmp_path / "empty"
    empty.mkdir()
    row = dict(ROW, file_path=str(two_trees["legacy"]))
    assert _dataset(empty)._resolve_feature_path(row) == two_trees["legacy"]


def test_the_real_ablation_split_resolves_into_the_arm_trees():
    """Integration check against the actual split, skipped where it is absent."""
    split = REPO / "processed" / "splits" / "versions" / "zfix" / "train.csv"
    # Repo-relative FIRST. `/dataset/...` is where the volume lands inside the
    # backend container, but the suite runs in voya_backend_test with the repo
    # mounted at /src — so hardcoding the absolute path made this skip on the
    # very machine that has the data, which is the only machine that can run it.
    v2 = next(
        (p for p in (REPO / "dataset" / "features_zfix" / "v2",
                     Path("/dataset/features_zfix/v2")) if p.is_dir()),
        None,
    )
    if not split.exists() or v2 is None:
        pytest.skip("zfix ablation not built on this machine")
    rows = list(csv.DictReader(split.open(encoding="utf-8-sig")))
    ds = _dataset(v2)
    for row in rows[:25]:
        assert str(ds._resolve_feature_path(row)).startswith(str(v2))
