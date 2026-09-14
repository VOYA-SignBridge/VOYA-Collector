import numpy as np

def normalize_single_hand(hand: np.ndarray) -> np.ndarray:
    """
    Normalize ONE hand independently.

    hand shape: (21,3)
    """

    h = hand.astype(np.float32).copy()

    # empty hand
    if not np.any(h):
        return h

    # wrist landmark
    wrist = h[0, :2].copy()

    # translate
    h[:, :2] = h[:, :2] - wrist

    # compute scale
    valid = np.linalg.norm(h[:, :2], axis=1) > 1e-6

    if valid.any():

        pts = h[valid, :2]

        span_x = pts[:,0].max() - pts[:,0].min()
        span_y = pts[:,1].max() - pts[:,1].min()

        scale = max(span_x, span_y)

        if scale > 1e-6:
            h[:, :2] = h[:, :2] / scale

    return h

def normalize_hands_vector_126(vec: np.ndarray) -> np.ndarray:

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
    left = normalize_single_hand(left)
    right = normalize_single_hand(right)

    out = np.concatenate([
        left.reshape(-1),
        right.reshape(-1)
    ]).astype(np.float32)

    return out