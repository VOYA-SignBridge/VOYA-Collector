"""`normalize_single_hand` exists TWICE. This pins the two copies together.

    backend/app/processing/utils.py      <- writes what lands on disk
    processed/shared/normalization.py    <- what training reads back

They are byte-equivalent today, and nothing enforced that. Every expensive
defect in this repo so far came from a second copy drifting: the profile list
that silently dropped 7 classes, the six hardcoded dialect lists that disagreed,
the mirror that was correct in one renderer and wrong in three.

The stakes here are worse than a wrong dropdown. If the capture side and the
training side disagree about what a normalized hand is, every checkpoint is
trained on features that no longer describe what inference feeds it, and nothing
raises — accuracy just quietly stops making sense.

There is a KNOWN defect in both copies: z is neither translated nor scaled, so
x/y come out wrist-centred in units of hand-span while z stays in raw MediaPipe
units carrying the absolute wrist depth. Fixing it changes the feature space and
obsoletes every checkpoint, so it is a deliberate decision, not a cleanup. The
z tests below pin the CURRENT behaviour on purpose: whoever fixes it must see
them go red and update both copies plus the retraining decision, rather than
patch one file and ship a silent feature change.

See docs/10-issues/KNOWN_ISSUES.md ("Chờ quyết định nghiệp vụ") and the raw archive
(contract v3), which is what makes the fix affordable at all — the
un-normalized landmarks were kept, so the features can be rebuilt without
re-recording anyone.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.processing.utils import normalize_single_hand as backend_normalize  # noqa: E402
from app.processing.utils import normalize_hands_vector_126 as backend_vec126  # noqa: E402
from processed.shared.normalization import (  # noqa: E402
    normalize_hands_vector_126 as train_vec126,
    normalize_single_hand as train_normalize,
)


def _hands(seed: int, n: int = 40) -> np.ndarray:
    """Plausible MediaPipe hands: x,y in [0,1], z small and signed."""
    rng = np.random.default_rng(seed)
    out = rng.random((n, 21, 3), dtype=np.float32)
    out[:, :, 2] = (out[:, :, 2] - 0.5) * 0.2
    return out


# ---------------------------------------------------------------- parity

@pytest.mark.parametrize("seed", [0, 1, 7, 1234])
def test_both_copies_normalize_identically(seed):
    for hand in _hands(seed):
        np.testing.assert_array_equal(backend_normalize(hand), train_normalize(hand))


@pytest.mark.parametrize("seed", [0, 3, 99])
def test_both_copies_agree_on_the_126_vector(seed):
    rng = np.random.default_rng(seed)
    for _ in range(20):
        vec = rng.random(126).astype(np.float32)
        np.testing.assert_array_equal(backend_vec126(vec), train_vec126(vec))


def test_both_copies_agree_on_the_absent_hand():
    """An all-zero slot means "no hand here", not "a hand at the origin".

    The two copies returning different things for an empty slot would be the
    worst kind of drift: the common case, and invisible in any accuracy metric.
    """
    empty = np.zeros((21, 3), dtype=np.float32)
    for fn in (backend_normalize, train_normalize):
        assert not np.any(fn(empty))

    half = np.zeros(126, dtype=np.float32)
    half[63:] = np.random.default_rng(5).random(63).astype(np.float32)
    np.testing.assert_array_equal(backend_vec126(half), train_vec126(half))
    assert not np.any(backend_vec126(half)[:63]), "an absent hand must stay absent"


# ---------------------------------------------------------------- contract

@pytest.mark.parametrize("fn", [backend_normalize, train_normalize])
def test_wrist_lands_on_the_origin_in_xy(fn):
    for hand in _hands(11, n=10):
        out = fn(hand)
        assert abs(float(out[0, 0])) < 1e-6
        assert abs(float(out[0, 1])) < 1e-6


@pytest.mark.parametrize("fn", [backend_normalize, train_normalize])
def test_hand_span_is_one_after_scaling(fn):
    """x/y are expressed in units of hand span — that is what makes a hand
    recorded close to the camera comparable to the same hand recorded far."""
    for hand in _hands(12, n=10):
        out = fn(hand)
        span = max(float(out[:, 0].ptp()), float(out[:, 1].ptp()))
        assert span == pytest.approx(1.0, abs=1e-5)


@pytest.mark.parametrize("fn", [backend_normalize, train_normalize])
def test_v1_leaves_z_raw(fn):
    """PINS THE KNOWN DEFECT IN v1 — do not "fix" this test, use v2.

    In v1 z passes through untouched: not wrist-centred, not divided by the
    span, so the third coordinate is on a different scale from the first two.
    Every existing checkpoint was trained on exactly this, which is why v1 must
    keep behaving exactly this way.
    """
    for hand in _hands(13, n=10):
        np.testing.assert_array_equal(fn(hand)[:, 2], hand[:, 2])


@pytest.mark.parametrize("fn", [backend_normalize, train_normalize])
def test_v2_puts_z_on_the_same_scale_as_xy(fn):
    """The fix: all three axes share one unit.

    Measured on the live corpus, v1 hands out x/y spans averaging 1.085 against
    a z span of 0.078 — a ~13.8x mismatch that makes z read as noise. After v2
    the ratio is bounded by the geometry of the hand itself, not by an
    accidental difference of units.
    """
    for hand in _hands(14, n=10):
        v1, v2 = fn(hand), fn(hand, "hands126_v2")

        # Recover the divisor from x rather than recomputing it: the span is
        # measured over the landmarks EXCLUDING the wrist (its translated norm
        # is exactly 0, so the `valid` filter drops it), and a test that
        # re-derives that detail is just the implementation written twice.
        centred_x = hand[:, 0] - hand[0, 0]
        i = int(np.argmax(np.abs(v1[:, 0])))
        scale = float(centred_x[i] / v1[i, 0])
        assert scale > 0

        expected = (hand[:, 2] - hand[0, 2]) / scale
        np.testing.assert_allclose(v2[:, 2], expected, rtol=1e-4, atol=1e-6)
        # x/y are untouched by the version change.
        np.testing.assert_allclose(v2[:, :2], v1[:, :2], rtol=1e-6, atol=1e-7)


@pytest.mark.parametrize("fn", [backend_normalize, train_normalize])
def test_v2_puts_the_wrist_at_the_origin_in_all_three_axes(fn):
    for hand in _hands(15, n=10):
        out = fn(hand, "hands126_v2")
        assert abs(float(out[0, 2])) < 1e-6


@pytest.mark.parametrize("fn", [backend_normalize, train_normalize])
def test_v1_stays_the_default(fn):
    """Changing what the default produces would silently re-define the features
    under every checkpoint ever trained — it would keep loading, keep
    predicting, and be wrong without anything reporting it."""
    for hand in _hands(16, n=10):
        np.testing.assert_array_equal(fn(hand), fn(hand, "hands126_v1"))


@pytest.mark.parametrize("fn", [backend_normalize, train_normalize])
def test_an_unknown_version_is_refused(fn):
    """Silently falling back to v1 for a typo'd version would produce v1
    features stamped v2 — the one failure mode the whole versioning exists to
    prevent."""
    with pytest.raises(ValueError):
        fn(_hands(17, n=1)[0], "hands126_v3")


def test_both_copies_expose_the_same_version_names():
    from app.processing import utils as backend_mod
    from processed.shared import normalization as train_mod

    assert backend_mod.NORMALIZATION_VERSIONS == train_mod.NORMALIZATION_VERSIONS
    assert (backend_mod.DEFAULT_NORMALIZATION_VERSION
            == train_mod.DEFAULT_NORMALIZATION_VERSION == "hands126_v1")


@pytest.mark.parametrize("seed", [2, 8])
def test_both_copies_agree_on_v2_too(seed):
    for hand in _hands(seed):
        np.testing.assert_array_equal(
            backend_normalize(hand, "hands126_v2"),
            train_normalize(hand, "hands126_v2"))


def test_the_two_files_have_not_diverged_in_source():
    """Structural backstop for cases the numeric tests cannot reach — a guard
    added on one side only, a different epsilon, a reordered branch."""
    import inspect
    import re

    def body(fn) -> str:
        src = inspect.getsource(fn)
        src = re.sub(r"#.*", "", src)            # comments
        src = re.sub(r'"""(?:.|\n)*?"""', "", src)  # docstring
        return re.sub(r"\s+", "", src)

    assert body(backend_normalize) == body(train_normalize), (
        "backend/app/processing/utils.py and processed/shared/normalization.py "
        "have drifted — capture and training would disagree about what a "
        "normalized hand is, and nothing else would report it"
    )
