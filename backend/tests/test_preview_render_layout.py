"""Layout invariants for the server-rendered preview video.

The server renderer carried the same two defects the browser viewer had, and
they were never ported across:

  1. ONE bounding box was fitted over BOTH hands. Stored coordinates are
     wrist-centred, so each hand spans roughly the same range around its own
     origin — a shared box drew them on top of each other, both wrists landing
     on the same pixel. The two hands read as a single tangled shape.

  2. Every drawing call was guarded by "skip this landmark if it is (0,0,0)",
     which deletes the WRIST from every frame: landmark 0 is exactly the origin
     by construction in wrist-centred data. That removes the joint the thumb,
     index and palm edge all attach to.

Pure numpy — no OpenCV, no video written.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.preview_render import (
    CANVAS_SIZE,
    HAND_CONNECTIONS,
    _fit_transform,
    _hand_columns,
    _hand_present,
    _shared_fit,
    _split_hands,
    _use_columns,
    _wrist_separation,
)

LANDMARKS = 21


def _wrist_centred_hand(rng: np.random.Generator, frames: int) -> np.ndarray:
    """(T, 21, 3) with landmark 0 pinned at the origin, as stored on disk."""
    hand = rng.uniform(-0.4, 0.4, size=(frames, LANDMARKS, 3)).astype(np.float32)
    hand[:, 0, :] = 0.0
    return hand


def _sequence(left: np.ndarray | None, right: np.ndarray | None, frames: int) -> np.ndarray:
    seq = np.zeros((frames, 126), dtype=np.float32)
    if left is not None:
        seq[:, :63] = left.reshape(frames, 63)
    if right is not None:
        seq[:, 63:126] = right.reshape(frames, 63)
    return seq


@pytest.fixture
def rng():
    return np.random.default_rng(4)


def _image_coords_hand(rng: np.random.Generator, frames: int, cx: float) -> np.ndarray:
    """(T, 21, 3) in raw MediaPipe image space, centred on cx — the hands here
    already hold their true position, so nothing may move them."""
    hand = rng.uniform(-0.12, 0.12, size=(frames, LANDMARKS, 3)).astype(np.float32)
    hand[:, :, 0] += cx
    hand[:, :, 1] += 0.5
    return hand


def test_two_hands_are_drawn_in_separate_columns(rng):
    frames = 12
    seq = _sequence(_wrist_centred_hand(rng, frames), _wrist_centred_hand(rng, frames), frames)
    left, right = _split_hands(seq)
    assert _use_columns(left, right), "both wrists sit on the origin — they must be separated"
    lc, rc = _hand_columns(left, right)
    assert lc == (0.0, 0.5) and rc == (0.5, 1.0)

    to_left, to_right = _fit_transform(left, lc), _fit_transform(right, rc)
    for t in range(frames):
        lx = [to_left(float(p[0]), float(p[1]))[0] for p in left[t]]
        rx = [to_right(float(p[0]), float(p[1]))[0] for p in right[t]]
        # The whole left hand stays left of the whole right hand — with a shared
        # fit these ranges were identical.
        assert max(lx) < min(rx), (t, max(lx), min(rx))


def test_a_lone_hand_uses_the_full_canvas(rng):
    frames = 8
    seq = _sequence(_wrist_centred_hand(rng, frames), None, frames)
    left, right = _split_hands(seq)
    assert _hand_present(left) and not _hand_present(right)
    lc, rc = _hand_columns(left, right)
    assert lc == (0.0, 1.0) and rc == (0.0, 1.0)


def test_the_wrist_at_the_origin_still_maps_onto_the_canvas(rng):
    """(0,0,0) is a real wrist position, not a missing landmark."""
    frames = 6
    left = _wrist_centred_hand(rng, frames)
    seq = _sequence(left, None, frames)
    ls, _ = _split_hands(seq)
    assert np.all(ls[:, 0, :] == 0.0), "fixture must keep the wrist at the origin"

    to_px = _fit_transform(ls, (0.0, 1.0))
    px, py = to_px(0.0, 0.0)
    assert 0 <= px <= CANVAS_SIZE and 0 <= py <= CANVAS_SIZE


def test_every_bone_reaches_the_wrist(rng):
    """The thumb, index and palm edge all hang off landmark 0."""
    wrist_bones = [(a, b) for a, b in HAND_CONNECTIONS if a == 0 or b == 0]
    assert len(wrist_bones) == 3, wrist_bones

    frames = 5
    left = _wrist_centred_hand(rng, frames)
    seq = _sequence(left, None, frames)
    ls, _ = _split_hands(seq)
    to_px = _fit_transform(ls, (0.0, 1.0))
    pts = [to_px(float(p[0]), float(p[1])) for p in ls[0]]
    assert len(pts) == LANDMARKS
    for a, b in wrist_bones:
        assert pts[a] != pts[b], "a bone must have length; the wrist collapsed onto its neighbour"


def test_an_undetected_hand_is_reported_absent():
    """All-zero really does mean 'no hand this sequence' — presence is judged
    per hand, never per landmark, because the wrist is legitimately zero."""
    seq = np.zeros((4, 126), dtype=np.float32)
    left, right = _split_hands(seq)
    assert not _hand_present(left) and not _hand_present(right)


def test_image_coordinate_hands_keep_their_real_positions(rng):
    """~11% of stored samples never went through wrist-centring. Their hands are
    already where they were recorded, so splitting them into columns would move
    real data and rescale each hand on its own."""
    frames = 10
    seq = _sequence(
        _image_coords_hand(rng, frames, 0.3),
        _image_coords_hand(rng, frames, 0.7),
        frames,
    )
    left, right = _split_hands(seq)
    sep = _wrist_separation(left, right)
    assert sep is not None and sep > 0.1, sep
    assert not _use_columns(left, right)


def test_relative_hand_size_survives_in_shared_mode(rng):
    """A big hand next to a small one must still look bigger. Per-hand fitting
    normalises that away, which is why shared mode exists."""
    frames = 8
    big = _image_coords_hand(rng, frames, 0.3) * np.array([1.0, 1.0, 1.0], dtype=np.float32)
    small = (_image_coords_hand(rng, frames, 0.7) - np.array([0.7, 0.5, 0.0], dtype=np.float32)) * 0.4
    small += np.array([0.7, 0.5, 0.0], dtype=np.float32)
    seq = _sequence(big, small, frames)
    left, right = _split_hands(seq)
    assert not _use_columns(left, right)

    to_px = _shared_fit(left, right)

    def width(hand):
        xs = [to_px(float(p[0]), float(p[1]))[0] for p in hand[0]]
        return max(xs) - min(xs)

    assert width(left) > width(right) * 1.5, (width(left), width(right))


def test_wrist_separation_is_none_when_hands_never_share_a_frame(rng):
    frames = 6
    left = _wrist_centred_hand(rng, frames)
    seq = _sequence(left, None, frames)
    ls, rs = _split_hands(seq)
    assert _wrist_separation(ls, rs) is None
    assert not _use_columns(ls, rs)


def test_hands_that_genuinely_touch_are_not_pulled_apart(rng):
    """The whole point of the tight threshold.

    In raw landmarks the closest real two-hand recording scores 0.0154. A 0.05
    threshold — which looked safe against wrist-centred data, whose score is
    exactly 0.0 — dragged two such samples into opposite columns and invented a
    gap the signer never made.
    """
    frames = 12

    def hand_at(wx: float, wy: float) -> np.ndarray:
        """Deterministic 21-point hand ~0.2 wide, wrist exactly at (wx, wy)."""
        h = np.zeros((frames, LANDMARKS, 3), dtype=np.float32)
        for i in range(LANDMARKS):
            h[:, i, 0] = wx + (0.0 if i == 0 else 0.01 * i)
            h[:, i, 1] = wy + (0.0 if i == 0 else 0.008 * i)
            h[:, i, 2] = 0.01 * i
        return h

    # Wrists 0.008 apart; each hand spans 0.2 → ratio ≈ 0.04, well inside the
    # band where the old 0.05 threshold misfired.
    seq = _sequence(hand_at(0.400, 0.500), hand_at(0.408, 0.500), frames)
    ls, rs = _split_hands(seq)
    sep = _wrist_separation(ls, rs)
    assert sep is not None and 0.005 < sep < 0.05, sep
    assert not _use_columns(ls, rs), "hands this close were recorded touching — leave them"


def test_a_placeholder_hand_is_not_a_hand(rng):
    """3.3% of stored samples write the left hand as 21 identical points at
    (1.0, 0.0). It is a constant, not a recording."""
    frames = 10
    fake = np.zeros((frames, LANDMARKS, 3), dtype=np.float32)
    fake[:, :, 0] = 1.0
    seq = _sequence(fake, _image_coords_hand(rng, frames, 0.4), frames)
    left, right = _split_hands(seq)
    assert not _hand_present(left), "21 coincident points have no extent"
    assert _hand_present(right)
    assert not _use_columns(left, right), "only one real hand — nothing to separate"


def test_a_placeholder_hand_does_not_squash_the_real_one(rng):
    """The placeholder sits at x=1.0 while the real hand lives near x=0.4, so a
    box that includes it stretches to cover ground no hand ever touched and the
    real hand collapses to a sliver — measured on sample_93dced57ed."""
    frames = 10
    fake = np.zeros((frames, LANDMARKS, 3), dtype=np.float32)
    fake[:, :, 0] = 1.0
    real = _image_coords_hand(rng, frames, 0.4)
    seq = _sequence(fake, real, frames)
    left, right = _split_hands(seq)

    to_px = _shared_fit(left, right)
    xs = [to_px(float(p[0]), float(p[1]))[0] for p in right[0]]
    width = max(xs) - min(xs)
    # With the placeholder counted the real hand fell under ~60px of 480.
    assert width > CANVAS_SIZE * 0.4, width


def test_hands_are_not_stretched(rng):
    """Uniform scale on both axes: a column narrows x, it must not squash the hand."""
    frames = 10
    seq = _sequence(_wrist_centred_hand(rng, frames), _wrist_centred_hand(rng, frames), frames)
    left, right = _split_hands(seq)
    lc, _ = _hand_columns(left, right)
    to_px = _fit_transform(left, lc)
    # A unit square in data space must stay square in pixels.
    x0, y0 = to_px(0.0, 0.0)
    x1, y1 = to_px(0.1, 0.0)
    x2, y2 = to_px(0.0, 0.1)
    assert abs((x1 - x0) - (y2 - y0)) <= 1, ((x1 - x0), (y2 - y0))
