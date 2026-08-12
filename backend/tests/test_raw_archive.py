"""The recording lives in its own tree, and it is written first.

Two halves of a sample are not equally replaceable. `sequence` is a function of
the raw landmarks — re-run the normalizer and you have it back. The raw
landmarks are a function of a person having been in front of a camera. So they
go to disk first, into dataset/raw/, mirroring the features tree:

    dataset/features/vn/common/class_x/sample_ab.npz   model input
    dataset/raw/vn/common/class_x/sample_ab.npz        the recording

That ordering is chosen for the crash that survives it: raw-without-features is
recoverable by a later normalization pass, features-without-raw is a lost take.
It is also what makes the known z defect in normalize_single_hand fixable — a
re-run over an archive we hold, rather than a new collection campaign.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import app.dataset_samples as ds
from app.dataset_samples import (
    load_display_sequence,
    load_world_sequence,
    raw_archive_path,
)

LANDMARKS = 21


def _hand(wx: float, wy: float, frames: int) -> np.ndarray:
    h = np.zeros((frames, LANDMARKS, 3), dtype=np.float32)
    for i in range(LANDMARKS):
        h[:, i, 0] = wx + (0.0 if i == 0 else 0.01 * i)
        h[:, i, 1] = wy + (0.0 if i == 0 else 0.008 * i)
        h[:, i, 2] = 0.002 * i
    return h


def _seq(left=None, right=None, frames: int = 6) -> np.ndarray:
    s = np.zeros((frames, 126), dtype=np.float32)
    if left is not None:
        s[:, :63] = left.reshape(frames, 63)
    if right is not None:
        s[:, 63:] = right.reshape(frames, 63)
    return s


class TestArchivePath:
    def test_features_becomes_raw_keeping_the_class_hierarchy(self):
        p = Path("/data/dataset/features/vn/common/class_x/sample_ab.npz")
        assert raw_archive_path(p) == Path("/data/dataset/raw/vn/common/class_x/sample_ab.npz")

    def test_only_the_rightmost_features_segment_is_rewritten(self):
        """A deployment may sit under any prefix; only the dataset-relative
        segment is ours to rename."""
        p = Path("/srv/features/app/dataset/features/vn/common/c/s.npz")
        got = raw_archive_path(p)
        assert got == Path("/srv/features/app/dataset/raw/vn/common/c/s.npz")

    def test_a_path_with_no_features_segment_still_resolves(self):
        p = Path("/tmp/loose/sample_ab.npz").resolve()
        assert raw_archive_path(p).name == "sample_ab.npz"
        assert raw_archive_path(p).parent.name == "raw"


class TestSplitWrite:
    @pytest.fixture
    def class_meta(self, tmp_path):
        class _Meta:
            class_uid = "cuid"
            slug = "test"
            label_original = "test"
            language = "vn"
            dialect = "common"

            def hierarchy_path(self):
                return tmp_path / "dataset" / "features" / "vn" / "common" / "class_t"

            def folder_name(self):
                return "class_t"

        return _Meta()

    @pytest.fixture(autouse=True)
    def _local_only(self, monkeypatch):
        monkeypatch.setattr(ds.settings, "use_google_drive", False, raising=False)
        monkeypatch.setattr(ds, "append_sample_row", lambda *a, **k: None, raising=False)

    def _save(self, class_meta, **kw):
        return Path(ds.save_sequence_npz(
            class_meta, _seq(_hand(0.0, 0.0, 6)), meta={}, augment_id=0,
            source_type="camera", **kw,
        ))

    def test_the_recording_lands_in_the_raw_tree(self, class_meta):
        raw = _seq(_hand(0.3, 0.5, 6))
        path = self._save(class_meta, raw_sequence=raw)
        archived = raw_archive_path(path)
        assert archived.is_file(), "the recording must exist in dataset/raw/"
        with np.load(archived, allow_pickle=True) as z:
            assert np.allclose(z["landmarks_raw"], raw)

    def test_the_features_file_no_longer_carries_the_recording(self, class_meta):
        """It is opened for every sample of every epoch, and the raw and world
        arrays were measured at 33% of a v2 npz."""
        path = self._save(class_meta, raw_sequence=_seq(_hand(0.3, 0.5, 6)))
        with np.load(path, allow_pickle=True) as z:
            keys = set(z.keys())
        assert "landmarks_raw" not in keys
        assert "sequence" in keys and "landmarks_normalized" in keys

    def test_readers_follow_the_recording_into_the_archive(self, class_meta):
        raw = _seq(_hand(0.3, 0.5, 6))
        path = self._save(class_meta, raw_sequence=raw)
        seq, source = load_display_sequence(path)
        assert source == "raw"
        assert np.allclose(seq, raw)

    def test_world_landmarks_travel_with_the_recording(self, class_meta):
        world = _seq(_hand(-0.04, 0.0, 6))
        path = self._save(class_meta, raw_sequence=_seq(_hand(0.3, 0.5, 6)),
                          world_sequence=world)
        got = load_world_sequence(path)
        assert got is not None and np.allclose(got, world)
        with np.load(path, allow_pickle=True) as z:
            assert "landmarks_world" not in set(z.keys())

    def test_a_sample_with_no_recording_writes_no_archive(self, class_meta):
        """Legacy paths that never captured raw landmarks must not leave an
        empty file that later readers would mistake for one."""
        path = self._save(class_meta)
        assert not raw_archive_path(path).exists()

    def test_the_contract_version_says_where_to_look(self, class_meta):
        path = self._save(class_meta, raw_sequence=_seq(_hand(0.3, 0.5, 6)))
        with np.load(path, allow_pickle=True) as z:
            assert z["meta"].item()["storage_contract_version"] == "npz_v3_split_raw"

    def test_a_failed_archive_write_stops_the_sample(self, class_meta, monkeypatch):
        """The ordering only protects the take if the failure is loud. Writing
        the features half after a failed archive write would produce exactly the
        loss this design exists to prevent."""
        def _boom(path, arrays):
            if "landmarks_raw" in arrays:
                raise OSError("disk full")
            raise AssertionError("features must not be written after the archive failed")

        monkeypatch.setattr(ds, "_atomic_write_npz", _boom)
        with pytest.raises(OSError):
            self._save(class_meta, raw_sequence=_seq(_hand(0.3, 0.5, 6)))


class TestLegacyInlineStillReads:
    """1997 archived samples keep the recording inline. Nothing rewrites them —
    moving a key inside 1997 files is a risk taken for no gain — so both
    layouts must resolve."""

    def test_inline_raw_is_preferred_when_present(self, tmp_path):
        raw = _seq(_hand(0.3, 0.5, 6))
        p = tmp_path / "s.npz"
        np.savez_compressed(p, sequence=_seq(_hand(0.0, 0.0, 6)),
                            landmarks_raw=raw, meta={})
        seq, source = load_display_sequence(p)
        assert source == "raw" and np.allclose(seq, raw)

    def test_inline_world_is_preferred_when_present(self, tmp_path):
        world = _seq(_hand(-0.04, 0.0, 6))
        p = tmp_path / "s.npz"
        np.savez_compressed(p, sequence=_seq(_hand(0.0, 0.0, 6)),
                            landmarks_world=world, meta={})
        got = load_world_sequence(p)
        assert got is not None and np.allclose(got, world)
