import numpy as np
from app.config import settings


def _scale(seq: np.ndarray, factor: float) -> np.ndarray:
    return (seq * factor).astype(np.float32)


def _jitter(seq: np.ndarray, sigma: float) -> np.ndarray:
    noise = np.random.normal(0, sigma, seq.shape).astype(np.float32)
    return (seq + noise).astype(np.float32)


def _time_warp(seq: np.ndarray, factor: float) -> np.ndarray:
    T, D = seq.shape
    new_T = max(1, int(round(T * factor)))
    idx = np.linspace(0, T - 1, new_T).astype(np.int32)
    warped = seq[idx]
    # ensure same length by pad/truncate back to T
    if warped.shape[0] < T:
        pad = np.zeros((T - warped.shape[0], D), dtype=np.float32)
        warped = np.vstack([warped, pad])
    else:
        warped = warped[:T]
    return warped.astype(np.float32)


def _hand_dropout(seq: np.ndarray, drop_left: bool = True) -> np.ndarray:
    # left hand occupies first 63 dims, right hand last 63 dims
    out = seq.copy().astype(np.float32)
    if drop_left:
        out[:, :63] = 0.0
    else:
        out[:, 63:] = 0.0
    return out


def _rotate_xy(seq: np.ndarray, angle_deg: float) -> np.ndarray:
    """Rotate hand keypoints in the image plane.

    - Expects D=126 (2 hands * 21 * 3). If not, returns seq unchanged.
    - Preserves missing landmarks (all-zero triples) as zeros.
    - For raw MediaPipe coords (not normalized), rotates around center (0.5, 0.5).
    - For normalized coords (centered), rotates around origin (0, 0).
    """
    if not isinstance(seq, np.ndarray) or seq.ndim != 2 or seq.shape[1] != 126:
        return seq

    out = seq.astype(np.float32, copy=True)
    T = out.shape[0]
    arr = out.reshape(T, 2, 21, 3)

    normalized = bool(getattr(settings, "normalize_keypoints", False))
    cx, cy = (0.0, 0.0) if normalized else (0.5, 0.5)

    a = float(angle_deg) * (np.pi / 180.0)
    ca = float(np.cos(a))
    sa = float(np.sin(a))

    for h in range(2):
        pts = arr[:, h, :, :]
        # mask: landmark triple is non-zero
        mask = np.any(pts != 0.0, axis=2)  # [T,21]
        if not mask.any():
            continue

        x = pts[:, :, 0]
        y = pts[:, :, 1]

        x0 = x - cx
        y0 = y - cy

        xr = (ca * x0) - (sa * y0) + cx
        yr = (sa * x0) + (ca * y0) + cy

        # Only write back rotated coordinates where original landmark exists
        x_new = x.copy()
        y_new = y.copy()
        x_new[mask] = xr[mask]
        y_new[mask] = yr[mask]
        pts[:, :, 0] = x_new
        pts[:, :, 1] = y_new

        # Keep raw coords in a sane range
        if not normalized:
            pts[:, :, 0] = np.clip(pts[:, :, 0], 0.0, 1.0)
            pts[:, :, 1] = np.clip(pts[:, :, 1], 0.0, 1.0)

    return arr.reshape(T, 126).astype(np.float32)


def _landmark_dropout(seq: np.ndarray, p: float = 0.1) -> np.ndarray:
    """Randomly drop (zero-out) some landmarks across the sequence."""
    if not isinstance(seq, np.ndarray) or seq.ndim != 2 or seq.shape[1] != 126:
        return seq
    p = float(np.clip(p, 0.0, 1.0))
    if p <= 0.0:
        return seq

    out = seq.astype(np.float32, copy=True)
    T = out.shape[0]
    arr = out.reshape(T, 2, 21, 3)
    # sample mask per (hand, landmark) and apply for all frames
    drop = (np.random.rand(2, 21) < p)
    for h in range(2):
        for lm in range(21):
            if drop[h, lm]:
                arr[:, h, lm, :] = 0.0
    return arr.reshape(T, 126).astype(np.float32)


def _frame_dropout(seq: np.ndarray, p: float = 0.05) -> np.ndarray:
    """Randomly zero-out whole frames to simulate occlusion/missed detection."""
    if not isinstance(seq, np.ndarray) or seq.ndim != 2:
        return seq
    p = float(np.clip(p, 0.0, 1.0))
    if p <= 0.0:
        return seq
    out = seq.astype(np.float32, copy=True)
    T = out.shape[0]
    mask = (np.random.rand(T) < p)
    out[mask] = 0.0
    return out


def _mirror_hands(seq: np.ndarray) -> np.ndarray:
    """
    Proper horizontal mirror for keypoint sequences.
    This does two things:
    - Flip the x coordinate (normalized) for all landmarks: x -> 1 - x
    - Swap left/right blocks so the resulting order matches flipped input
    """
    out = seq.copy().astype(np.float32)
    if out.size == 0:
        return out
    # left and right blocks (each 21 landmarks * 3 coords = 63)
    T = out.shape[0]
    left = out[:, :63].reshape(T, 21, 3).copy()
    right = out[:, 63:].reshape(T, 21, 3).copy()

    # flip x coordinate (first coord in each landmark triple)
    # - raw MediaPipe coords are in [0,1] -> mirror via x := 1-x
    # - normalized coords (centered) -> mirror via x := -x
    if bool(getattr(settings, "normalize_keypoints", False)):
        left[..., 0] = -left[..., 0]
        right[..., 0] = -right[..., 0]
    else:
        left[..., 0] = 1.0 - left[..., 0]
        right[..., 0] = 1.0 - right[..., 0]

    # swap hands (left <- right, right <- left) after flipping x
    out[:, :63] = right.reshape(T, 63)
    out[:, 63:] = left.reshape(T, 63)
    return out


def augment_n(seq: np.ndarray, n: int = 8) -> list:
    """
    Produce up to n augmentations deterministically composed from common ops
    to match live-capture distribution.
    Always returns a list of length n (duplicates original if needed).
    """
    variants = []
    variants.append(seq)  # original
    # common, low-risk variants
    variants.append(_jitter(seq, 0.01))
    variants.append(_jitter(seq, 0.02))
    variants.append(_jitter(seq, 0.03))
    variants.append(_scale(seq, 1.05))
    variants.append(_scale(seq, 0.95))
    variants.append(_time_warp(seq, 1.15))
    variants.append(_time_warp(seq, 0.85))
    variants.append(_hand_dropout(seq, drop_left=True))
    variants.append(_hand_dropout(seq, drop_left=False))

    # rotation in image plane (helps camera tilt / user angle)
    variants.append(_rotate_xy(seq, 10.0))
    variants.append(_rotate_xy(seq, -10.0))
    variants.append(_rotate_xy(seq, 20.0))
    variants.append(_rotate_xy(seq, -20.0))

    # occlusion / missed keypoints
    variants.append(_landmark_dropout(seq, 0.08))
    variants.append(_frame_dropout(seq, 0.05))

    # combined
    variants.append(_jitter(_rotate_xy(seq, 15.0), 0.015))
    # If we canonicalize mirror orientation at ingestion/inference time, adding a mirrored
    # variant often becomes a near-duplicate. Keep it only when mirror canonicalization is off.
    if not bool(getattr(settings, "canonicalize_mirror", True)):
        variants.append(_mirror_hands(seq))

    # If user asks for more than the base menu, generate extra randomized compositions.
    # This increases diversity without changing shapes.
    while len(variants) < n:
        v = seq
        # sample a light composition of ops
        if np.random.rand() < 0.70:
            v = _jitter(v, float(np.random.uniform(0.005, 0.03)))
        if np.random.rand() < 0.60:
            v = _scale(v, float(np.random.uniform(0.90, 1.10)))
        if np.random.rand() < 0.50:
            v = _time_warp(v, float(np.random.uniform(0.80, 1.25)))
        if np.random.rand() < 0.50:
            v = _rotate_xy(v, float(np.random.uniform(-25.0, 25.0)))
        if np.random.rand() < 0.25:
            v = _landmark_dropout(v, float(np.random.uniform(0.05, 0.15)))
        if np.random.rand() < 0.20:
            v = _frame_dropout(v, float(np.random.uniform(0.03, 0.10)))
        variants.append(v.astype(np.float32))

    return variants[:n]
