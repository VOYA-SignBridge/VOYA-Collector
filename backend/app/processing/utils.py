import os
import json
import tempfile
from pathlib import Path
from typing import Any, Union

import numpy as np

def atomic_write_json(path: Union[str, Path], obj: Any, *, indent: int = 2):
    """Atomically write JSON to disk (temp file + replace).

    Prevents corrupt/partial JSON when the process is killed mid-write.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp = tempfile.mkstemp(prefix="jsontmp_", suffix=p.suffix or ".json", dir=str(p.parent))
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass

def normalize_sequence(sequence, expected_T: int = 60, expected_D: int = 126):
    """Normalize/pad/truncate a sequence to (expected_T, expected_D).

    Returns (sequence_ndarray, info_dict) where info contains 'original_shape' and 'normalized' flag.
    """
    seq = np.asarray(sequence)
    original_shape = tuple(seq.shape)
    try:
        # Ensure 2D
        if seq.ndim == 1:
            if seq.size == expected_T * expected_D:
                seq = seq.reshape((expected_T, expected_D))
            else:
                if expected_D and seq.size % expected_D == 0:
                    seq = seq.reshape((-1, expected_D))
                else:
                    seq = seq.reshape((seq.shape[0], -1))
        seq = seq.astype(np.float32)
        T, D = seq.shape
        # Adjust feature dim
        if D != expected_D:
            if D > expected_D:
                seq = seq[:, :expected_D]
            else:
                pad_cols = expected_D - D
                seq = np.pad(seq, ((0, 0), (0, pad_cols)), mode="constant", constant_values=0.0)
        # Adjust temporal length
        T = seq.shape[0]
        if T > expected_T: 
            idx = np.linspace( 0, T - 1, expected_T ).astype(np.int32) 
            seq = seq[idx]
        elif T < expected_T:
            pad_rows = expected_T - T
            seq = np.pad(seq, ((0, pad_rows), (0, 0)), mode="constant", constant_values=0.0)
        normalized = tuple(seq.shape) != original_shape
    except Exception:
        seq = np.zeros((expected_T, expected_D), dtype=np.float32)
        normalized = True
    info = {"original_shape": original_shape, "normalized": bool(normalized)}
    return seq, info

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


def _hand_blocks_126(vec: np.ndarray):
    """Split a (126,) vector into (left(21,3), right(21,3))."""
    arr = np.asarray(vec, dtype=np.float32).reshape(2, 21, 3)
    return arr[0].copy(), arr[1].copy()
