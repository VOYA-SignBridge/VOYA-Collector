"""Hand normalization. KEEP BYTE-IDENTICAL WITH backend/app/processing/utils.py.

Two copies exist on purpose — the realtime service loads this file by path and
must not import the backend — and backend/tests/test_normalization_parity.py
fails if they drift.

Versions
--------
hands126_v1  x,y wrist-centred and divided by the hand span; **z untouched**.
             This is a defect, not a choice: the stored z stays in raw MediaPipe
             units while x,y are in units of hand span. Measured over 82 hands
             from the live corpus, x/y span averages 1.085 while z span averages
             0.078 — the third axis arrives ~13.8x smaller than the other two,
             so a model sees it as near-noise regardless of what it encodes.

hands126_v2  identical, except z is centred on the wrist and divided by the SAME
             scale, so all three axes share one unit. Fixes the above.

v1 remains the default. Changing what the default produces would silently
re-define the features under every checkpoint ever trained — the checkpoint
would keep loading and keep predicting, just on inputs that no longer mean what
it learned. Callers name the version they want; `normalization_version` is
already recorded per sample and per checkpoint, and the realtime service already
refuses to serve a checkpoint whose version disagrees with its registry entry.
"""

import numpy as np

NORMALIZATION_V1 = "hands126_v1"
NORMALIZATION_V2 = "hands126_v2"
NORMALIZATION_VERSIONS = (NORMALIZATION_V1, NORMALIZATION_V2)
DEFAULT_NORMALIZATION_VERSION = NORMALIZATION_V1


def normalize_single_hand(hand: np.ndarray,
                          version: str = DEFAULT_NORMALIZATION_VERSION) -> np.ndarray:
    """
    Normalize ONE hand independently.

    hand shape: (21,3)
    """
    if version not in NORMALIZATION_VERSIONS:
        raise ValueError(f"unknown normalization version: {version!r}")

    h = hand.astype(np.float32).copy()

    # empty hand
    if not np.any(h):
        return h

    # wrist landmark
    ndim = 3 if version == NORMALIZATION_V2 else 2
    wrist = h[0, :ndim].copy()

    # translate
    h[:, :ndim] = h[:, :ndim] - wrist

    # compute scale
    #
    # The span is measured on x/y only in BOTH versions. z is the axis whose
    # magnitude MediaPipe does not promise — it is regressed depth, not a
    # measurement — so letting it widen the span would make the scale of a hand
    # depend on the least trustworthy number in the frame. v2 divides z by the
    # x/y scale; it does not let z decide that scale.
    valid = np.linalg.norm(h[:, :2], axis=1) > 1e-6

    if valid.any():

        pts = h[valid, :2]

        span_x = pts[:,0].max() - pts[:,0].min()
        span_y = pts[:,1].max() - pts[:,1].min()

        scale = max(span_x, span_y)

        if scale > 1e-6:
            h[:, :ndim] = h[:, :ndim] / scale

    return h

def normalize_hands_vector_126(vec: np.ndarray,
                               version: str = DEFAULT_NORMALIZATION_VERSION) -> np.ndarray:

    if vec is None:
        return vec

    v = np.asarray(vec, dtype=np.float32)

    if v.size != 126:
        return v

    try:
        arr = v.reshape(2, 21, 3).astype(np.float32)
    except Exception:
        return v

    # preserve semantic hand identity
    left = arr[0]
    right = arr[1]

    # normalize independently
    left = normalize_single_hand(left, version)
    right = normalize_single_hand(right, version)

    out = np.concatenate([
        left.reshape(-1),
        right.reshape(-1)
    ]).astype(np.float32)

    return out