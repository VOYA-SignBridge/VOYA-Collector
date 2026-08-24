"""Which coordinate convention a stored sample is in, and who gets to say.

Two conventions sit side by side on disk and nothing recorded which was which:

  * the camera path normalizes before writing, so each hand's wrist is pinned
    at the origin and its x,y divided by that hand's own span;
  * the video and npz-import paths never normalize at all, so their `sequence`
    is MediaPipe image coordinates with the hands still in their true relative
    positions.

Measured over the corpus: 3431 files in the first convention, 440 in the
second, all of them in the same samples.csv. Guessing wrong is not cosmetic —
a viewer that reads image coordinates as wrist-centred splits the two hands
into separate columns and invents a gap the signer never made, and the 440
image-space files were the ones being told their geometry was damaged.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.dataset_samples import (
    COORD_SPACE_IMAGE,
    coordinate_space_of,
    load_display_sequence,
    load_world_sequence,
)

LANDMARKS = 21


def _hand(wx: float, wy: float, frames: int) -> np.ndarray:
    """(T,21,3) hand ~0.2 wide whose wrist sits exactly at (wx, wy)."""
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


def test_wrist_at_the_origin_is_recognised_without_metadata():
    """The 1874 legacy files carry no coordinate_space at all, so the
    convention has to come from the numbers. It is exact, not a threshold:
    normalization pins landmark 0 at the origin by construction."""
    seq = _seq(_hand(0.0, 0.0, 6), _hand(0.0, 0.0, 6))
    assert coordinate_space_of({}, seq) == "wrist_centred_v1"


def test_image_coordinates_are_recognised_without_metadata():
    seq = _seq(_hand(0.3, 0.5, 6), _hand(0.7, 0.5, 6))
    assert coordinate_space_of({}, seq) == COORD_SPACE_IMAGE


def test_one_hand_off_the_origin_is_enough_to_rule_out_normalization():
    """A normalized sample has EVERY live wrist at the origin. One that does
    not cannot have been through the normalizer."""
    seq = _seq(_hand(0.0, 0.0, 6), _hand(0.7, 0.5, 6))
    assert coordinate_space_of({}, seq) == COORD_SPACE_IMAGE


def test_declared_metadata_beats_the_numbers():
    """The writer stamps what it actually wrote; sniffing is only the fallback."""
    seq = _seq(_hand(0.3, 0.5, 6))
    assert coordinate_space_of({"coordinate_space": "wrist_centred_v1"}, seq) == "wrist_centred_v1"


def test_the_old_spelling_still_reads():
    """1997 files on disk say "mediapipe_normalized". They mean wrist-centred,
    despite the name meaning image coordinates in MediaPipe's own docs."""
    assert coordinate_space_of({"coordinate_space": "mediapipe_normalized"}) == "wrist_centred_v1"


def test_a_sample_with_no_hands_declines_to_answer():
    """Better unknown than a coin flip stamped as fact — nothing is written."""
    assert coordinate_space_of({}, np.zeros((4, 126), dtype=np.float32)) == "unknown"


class TestDisplaySource:
    """What the viewer is told it is being given."""

    def _write(self, tmp_path, **arrays):
        p = tmp_path / "s.npz"
        np.savez_compressed(p, **arrays)
        return p

    def test_raw_landmarks_win_when_present(self, tmp_path):
        raw = _seq(_hand(0.3, 0.5, 6), _hand(0.4, 0.5, 6))
        norm = _seq(_hand(0.0, 0.0, 6), _hand(0.0, 0.0, 6))
        p = self._write(tmp_path, sequence=norm, landmarks_raw=raw, meta={})
        seq, source = load_display_sequence(p)
        assert source == "raw"
        assert np.allclose(seq, raw)

    def test_unnormalized_sequence_is_not_reported_as_normalized(self, tmp_path):
        """The 440-file bug. These never went through the normalizer, so their
        `sequence` IS the recording — yet having no separate landmarks_raw key
        got them a banner saying their geometry had been destroyed."""
        raw = _seq(_hand(0.3, 0.5, 6), _hand(0.7, 0.5, 6))
        p = self._write(tmp_path, sequence=raw, meta={})
        seq, source = load_display_sequence(p)
        assert source == "raw"
        assert np.allclose(seq, raw)

    def test_a_genuinely_normalized_sample_still_says_so(self, tmp_path):
        norm = _seq(_hand(0.0, 0.0, 6), _hand(0.0, 0.0, 6))
        p = self._write(tmp_path, sequence=norm, meta={})
        _, source = load_display_sequence(p)
        assert source == "normalized"

    def test_metadata_is_trusted_over_the_shape_of_the_numbers(self, tmp_path):
        norm = _seq(_hand(0.0, 0.0, 6))
        p = self._write(
            tmp_path, sequence=norm,
            meta=np.array({"coordinate_space": COORD_SPACE_IMAGE}, dtype=object),
        )
        _, source = load_display_sequence(p)
        assert source == "raw"


class TestWorldLandmarks:
    """MediaPipe's metric output — the only 3D array in the archive."""

    def test_absent_key_returns_none_rather_than_zeros(self, tmp_path):
        """Nothing is synthesized. A zero-filled array would be indistinguishable
        from a measurement of a perfectly flat hand."""
        p = tmp_path / "s.npz"
        np.savez_compressed(p, sequence=_seq(_hand(0.0, 0.0, 4), frames=4), meta={})
        assert load_world_sequence(p) is None

    def test_an_all_zero_world_array_is_treated_as_absent(self, tmp_path):
        p = tmp_path / "s.npz"
        np.savez_compressed(
            p,
            sequence=_seq(_hand(0.0, 0.0, 4), frames=4),
            landmarks_world=np.zeros((4, 126), dtype=np.float32),
            meta={},
        )
        assert load_world_sequence(p) is None

    def test_a_real_world_array_comes_back_unchanged(self, tmp_path):
        world = _seq(_hand(-0.04, 0.0, 4), frames=4)
        p = tmp_path / "s.npz"
        np.savez_compressed(p, sequence=_seq(_hand(0.0, 0.0, 4), frames=4),
                            landmarks_world=world, meta={})
        got = load_world_sequence(p)
        assert got is not None and np.allclose(got, world)


class TestWriterStamping:
    """save_sequence_npz records what it wrote, so no future save site can add
    another batch of unlabelled files."""

    @pytest.fixture
    def class_meta(self, tmp_path):
        class _Meta:
            class_uid = "cuid"
            slug = "test"
            label_original = "test"
            language = "vn"
            dialect = "common"
            # Ban sao gia lap cua `ClassMetadata` phai mang truong nay:
            # `save_sequence_npz` doc no de dong dau to chuc len dong du lieu.
            tenant_id = "default"
            vocabulary_scope = ""
            recognition_profile = ""
            vocabulary_group = ""
            semantic_label = ""

            def hierarchy_path(self):
                return tmp_path / "cls"

            def folder_name(self):
                return "class_test_cuid"

        return _Meta()

    @pytest.fixture(autouse=True)
    def _local_only(self, monkeypatch):
        """No Drive round trip: this suite is about what lands in the npz."""
        import app.dataset_samples as ds

        monkeypatch.setattr(ds.settings, "use_google_drive", False, raising=False)
        monkeypatch.setattr(ds, "append_sample_row", lambda *a, **k: None, raising=False)

    def _saved_meta(self, path):
        with np.load(path, allow_pickle=True) as d:
            return d["meta"].item()

    def test_space_is_derived_when_the_caller_says_nothing(self, class_meta, monkeypatch):
        import app.dataset_samples as ds

        monkeypatch.setattr(ds, "append_sample_row", lambda *a, **k: None)
        monkeypatch.setattr(ds, "_maybe_upload_to_drive", lambda *a, **k: None, raising=False)
        path = ds.save_sequence_npz(
            class_meta, _seq(_hand(0.3, 0.5, 6)), meta={}, augment_id=0, source_type="video",
        )
        assert self._saved_meta(path)["coordinate_space"] == COORD_SPACE_IMAGE

    def test_an_explicit_declaration_overrides_a_stale_meta_dict(self, class_meta, monkeypatch):
        """The video pipeline reuses one window_meta across every augmented
        variant, so a value left in it must not survive as if it described
        this write."""
        import app.dataset_samples as ds

        monkeypatch.setattr(ds, "append_sample_row", lambda *a, **k: None)
        monkeypatch.setattr(ds, "_maybe_upload_to_drive", lambda *a, **k: None, raising=False)
        path = ds.save_sequence_npz(
            class_meta, _seq(_hand(0.3, 0.5, 6)),
            meta={"coordinate_space": "wrist_centred_v1"},
            augment_id=0, source_type="video",
            coordinate_space=COORD_SPACE_IMAGE,
        )
        assert self._saved_meta(path)["coordinate_space"] == COORD_SPACE_IMAGE

    def test_world_landmarks_round_trip(self, class_meta, monkeypatch):
        import app.dataset_samples as ds

        monkeypatch.setattr(ds, "append_sample_row", lambda *a, **k: None)
        monkeypatch.setattr(ds, "_maybe_upload_to_drive", lambda *a, **k: None, raising=False)
        world = _seq(_hand(-0.04, 0.0, 6))
        path = ds.save_sequence_npz(
            class_meta, _seq(_hand(0.0, 0.0, 6)), meta={}, augment_id=0,
            source_type="camera", world_sequence=world,
        )
        assert self._saved_meta(path)["world_landmarks_available"] is True
        got = load_world_sequence(path)
        assert got is not None and np.allclose(got, world)

    def test_a_sample_without_world_landmarks_says_so(self, class_meta, monkeypatch):
        import app.dataset_samples as ds

        monkeypatch.setattr(ds, "append_sample_row", lambda *a, **k: None)
        monkeypatch.setattr(ds, "_maybe_upload_to_drive", lambda *a, **k: None, raising=False)
        path = ds.save_sequence_npz(
            class_meta, _seq(_hand(0.0, 0.0, 6)), meta={}, augment_id=0, source_type="camera",
        )
        assert self._saved_meta(path)["world_landmarks_available"] is False
