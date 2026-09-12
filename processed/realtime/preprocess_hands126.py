"""Portable inference preprocessing for SignBridge ``hands126_v1`` models.

Keep this module dependency-light: the same algorithm is intended to be ported
verbatim to Android/iOS.  Input and output are float32 arrays ordered as
``MP_Left(63) + MP_Right(63)``.
"""

from __future__ import annotations

import numpy as np


NORMALIZATION_VERSION = "hands126_v1"
FEATURE_DIM = 126


def normalize_hands_vector_126(vec: np.ndarray) -> np.ndarray:
    """Wrist-center and scale-normalize a single 126-value frame.

    Each hand is translated by its own wrist and divided by that hand's maximum
    non-wrist x/y span. z is not changed. Missing landmark triples stay
    exactly zero so missing hands cannot become synthetic non-zero landmarks.
    """

    v = np.asarray(vec, dtype=np.float32).reshape(-1)
    if v.size != FEATURE_DIM:
        raise ValueError(f"hands126_v1 expects {FEATURE_DIM} values, got {v.size}")

    hands = v.reshape(2, 21, 3).copy()
    out = np.zeros_like(hands)
    for hand_idx in range(2):
        hand = hands[hand_idx]
        present = np.any(hand != 0.0, axis=1)
        if not bool(np.any(present)):
            continue

        wrist = hand[0, :2].copy()
        centered_xy = hand[present, :2] - wrist
        non_wrist = np.linalg.norm(centered_xy, axis=1) > 1e-6
        scale = 1.0
        if bool(np.any(non_wrist)):
            points = centered_xy[non_wrist]
            candidate = max(
                float(np.ptp(points[:, 0])),
                float(np.ptp(points[:, 1])),
            )
            if candidate > 1e-6:
                scale = candidate

        out[hand_idx, present] = hand[present]
        out[hand_idx, present, :2] = centered_xy / scale
        out[hand_idx, ~present] = 0.0

    return out.reshape(FEATURE_DIM).astype(np.float32)


def normalize_hands_sequence_126(sequence: np.ndarray) -> np.ndarray:
    """Apply ``hands126_v1`` independently to every frame in ``(T,126)``."""

    seq = np.asarray(sequence, dtype=np.float32)
    if seq.ndim != 2 or seq.shape[1] != FEATURE_DIM:
        raise ValueError(
            f"hands126_v1 expects sequence shape (T,{FEATURE_DIM}), got {tuple(seq.shape)}"
        )
    return np.stack([normalize_hands_vector_126(frame) for frame in seq], axis=0)
