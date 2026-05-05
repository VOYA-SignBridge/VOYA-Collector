import os
import json
import tempfile
import numpy as np
import warnings
from pathlib import Path
from typing import Any, Union
from app.config import settings


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

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


def save_json_to_storage(obj, path):
    # Backward-compatible wrapper
    atomic_write_json(path, obj, indent=2)

def save_npz_feature(sequence_array, label_folder, filename, meta=None):
    ensure_dir(label_folder)
    outpath = os.path.join(label_folder, filename)
    np.savez_compressed(outpath, sequence=sequence_array.astype(np.float32), meta=meta or {})
    return outpath

_EMA_SMOOTH_UNSAFE_WARNED = False

def ema_smooth_sequence(sequence_array: np.ndarray, alpha: float = 0.2) -> np.ndarray:
    """
    Apply exponential moving average smoothing per time step.
    sequence_array: shape (T, D)

    WARNING: This operation is generally unsafe for training/inference parity.
    It can introduce distribution shift (train vs. live) and can erase short,
    discriminative motion cues. Prefer model-side temporal smoothing or
    explicitly version/lock this behavior in both training and serving.
    """
    global _EMA_SMOOTH_UNSAFE_WARNED
    if not _EMA_SMOOTH_UNSAFE_WARNED:
        warnings.warn(
            "ema_smooth_sequence() is generally unsafe for training/inference parity; "
            "use only if it is identically applied in both training and serving.",
            RuntimeWarning,
            stacklevel=2,
        )
        _EMA_SMOOTH_UNSAFE_WARNED = True
    if not isinstance(sequence_array, np.ndarray) or sequence_array.ndim != 2:
        return sequence_array
    out = sequence_array.astype(np.float32).copy()
    for t in range(1, out.shape[0]):
        out[t] = alpha * out[t] + (1.0 - alpha) * out[t - 1]
    return out


def normalize_hands_vector_126(vec: np.ndarray) -> np.ndarray:
    """Center+scale normalize a single 126-dim hand vector.

    Matches the behavior used in the video pipeline.
    - Reshapes to (2,21,3)
    - Uses wrist of first present hand as reference, otherwise mean of non-zero points
    - Translates and scales by max span of non-zero points
    """
    if vec is None:
        return vec
    v = np.asarray(vec, dtype=np.float32)
    if v.size != 126:
        return v
    try:
        arr = v.reshape(2, 21, 3).astype(np.float32)
    except Exception:
        return v

    coords = arr.reshape(-1, 3)
    mask = (coords.sum(axis=1) != 0)
    if not mask.any():
        return v

    coords_nonzero = coords[mask][:, :2]

    wrist = None
    for h in range(2):
        w = arr[h, 0, :2]
        if not np.allclose(w, 0.0):
            wrist = w
            break
    if wrist is None:
        wrist = coords_nonzero.mean(axis=0)

    coords[:, :2] = coords[:, :2] - wrist

    xs = coords_nonzero[:, 0] - wrist[0]
    ys = coords_nonzero[:, 1] - wrist[1]
    span_x = xs.max() - xs.min() if xs.size else 0.0
    span_y = ys.max() - ys.min() if ys.size else 0.0
    scale = max(span_x, span_y)
    if scale <= 1e-6:
        scale = 1.0
    coords[:, :2] = coords[:, :2] / float(scale)

    return coords.reshape(-1).astype(np.float32)


def canonicalize_vector_126(vec: np.ndarray) -> np.ndarray:
    """Apply the same normalization+canonicalization policy for both ingestion pipelines."""
    v = np.asarray(vec, dtype=np.float32).reshape(-1)
    # enforce exact dimensionality
    if v.size < 126:
        pad = np.zeros((126 - v.size,), dtype=np.float32)
        v = np.concatenate([v, pad], axis=0)
    elif v.size > 126:
        v = v[:126]

    normalized = bool(getattr(settings, "normalize_keypoints", False))
    if normalized:
        v = normalize_hands_vector_126(v)

    if bool(getattr(settings, "canonicalize_hands", True)):
        v = canonicalize_hands_126(
            v,
            normalized=normalized,
            mirror_invariant=bool(getattr(settings, "canonicalize_mirror", True)),
        )
    return v.astype(np.float32)


def _hand_blocks_126(vec: np.ndarray):
    """Split a (126,) vector into (left(21,3), right(21,3))."""
    arr = np.asarray(vec, dtype=np.float32).reshape(2, 21, 3)
    return arr[0].copy(), arr[1].copy()


def mirror_and_swap_hands_126(vec: np.ndarray, *, normalized: bool = True) -> np.ndarray:
    """Mirror a 126-dim (2*21*3) hand vector and swap hands.

    Assumes normalized coordinates where x is centered around 0.
    Consistently mirrors by negating the x-coordinate (x -> -x).
    """
    v = np.asarray(vec, dtype=np.float32)
    if v.size != 126:
        return v
    left, right = _hand_blocks_126(v)

    def _mirror_hand_x_inplace(hand_21x3: np.ndarray) -> None:
        present_mask = (hand_21x3.sum(axis=1) != 0.0)
        if not bool(np.any(present_mask)):
            return

        # Consistently use x -> -x on valid layout points
        hand_21x3[present_mask, 0] = -hand_21x3[present_mask, 0]

    _mirror_hand_x_inplace(left)
    _mirror_hand_x_inplace(right)

    out = np.zeros((126,), dtype=np.float32)
    out[:63] = right.reshape(63)
    out[63:] = left.reshape(63)
    return out


def _hand_chirality_sign_21(hand_21x3: np.ndarray) -> float:
    """Return a signed area proxy to infer hand orientation/chirality.

    Uses three stable landmarks in MediaPipe Hands ordering:
    - wrist: 0
    - index_mcp: 5
    - pinky_mcp: 17

    The sign is stable under translation/scale; it flips under mirroring.
    """
    h = np.asarray(hand_21x3, dtype=np.float32)
    if h.shape != (21, 3):
        return 0.0
    wrist = h[0, :2]
    index_mcp = h[5, :2]
    pinky_mcp = h[17, :2]
    v1 = index_mcp - wrist
    v2 = pinky_mcp - wrist
    # 2D cross product (z-component)
    return float(v1[0] * v2[1] - v1[1] * v2[0])


def _mirror_hand_about_wrist_21(hand_21x3: np.ndarray) -> np.ndarray:
    """Mirror a single hand (21,3) about the wrist x-axis in-place coordinates.

    We mirror around the wrist's x coordinate so it works for both normalized [0,1]
    and pixel-coordinate inputs.
    """
    h = np.asarray(hand_21x3, dtype=np.float32).copy()
    if h.shape != (21, 3):
        return h
    wrist_x = float(h[0, 0])
    h[:, 0] = (2.0 * wrist_x) - h[:, 0]
    return h


def canonicalize_hands_126(vec: np.ndarray, *, normalized: bool = False, mirror_invariant: bool = True) -> np.ndarray:
    """Legacy per-frame canonically. Maintained for backwards parity.

    WARNING: For temporal models like TCN, use `canonicalize_sequence_126` instead.
    Continual per-frame decisions can cause orientation to flip randomly if
    poses waver along the chirality axis.
    """
    v = np.asarray(vec, dtype=np.float32)
    if v.size != 126:
        return v

    left_present = bool(np.any(v[:63] != 0.0))
    right_present = bool(np.any(v[63:] != 0.0))

    if right_present and not left_present:
        out = np.zeros((126,), dtype=np.float32)
        out[:63] = v[63:]
        v = out
        left_present = True
        right_present = False

    if not mirror_invariant:
        return v

    eps = 1e-6
    if left_present and not right_present:
        hand = v[:63].reshape(21, 3)
        s = _hand_chirality_sign_21(hand)
        if abs(s) <= eps:
            s = float(np.sum(hand[:, 0]))

        if s >= 0.0:
            return v

        m = mirror_and_swap_hands_126(v, normalized=normalized)
        out = np.zeros((126,), dtype=np.float32)
        out[:63] = m[63:]
        return out

    if left_present and right_present:
        left_hand = v[:63].reshape(21, 3)
        right_hand = v[63:].reshape(21, 3)

        s_left = _hand_chirality_sign_21(left_hand)
        s_right = _hand_chirality_sign_21(right_hand)
        a_left = abs(s_left)
        a_right = abs(s_right)

        if a_left > a_right + eps:
            s = s_left
        elif a_right > a_left + eps:
            s = s_right
        else:
            s = s_left - s_right
            if abs(s) <= eps:
                if normalized:
                    s = float(np.sum(left_hand[:, 0]) + np.sum(right_hand[:, 0]))
                else:
                    s = float(np.sum(left_hand[:, 0] - 0.5) + np.sum(right_hand[:, 0] - 0.5))

        if s >= 0.0:
            return v
        return mirror_and_swap_hands_126(v, normalized=normalized)

    return v


def canonicalize_sequence_126(seq_arr: np.ndarray, *, normalized: bool = False, mirror_invariant: bool = True) -> np.ndarray:
    """
    Robust sequence-level canonicalization for temporal stability.

    WARNING: Models like TCN require temporal continuity over sequential frames.
    Per-frame canonicalization (canonicalize_hands_126) fluctuates and causes
    random horizontal flipping between contiguous boundaries.

        Stability strategy:
        - Uses the first 3-5 valid frames to vote on (a) single-hand unification
            (right-only -> left block) and (b) mirror decision.
        - Mirror voting is sign-based (only the sign of chirality contributes).
        - If confidence is low (weak margin / too few votes), it will NOT mirror.
        - Applies the chosen transform uniformly to every frame in the sequence.

    Input: seq_arr shape (T,126)
    Returns: newly matched sequence shaped (T,126)
    """
    a = np.asarray(seq_arr, dtype=np.float32)
    if a.ndim != 2 or a.shape[1] != 126 or a.shape[0] == 0:
        return seq_arr
    
    T = a.shape[0]

    # Collect up to the first 3-5 valid non-zero frames for robust decisions.
    N_FRAMES_FOR_DECISION = 5
    MIN_FRAMES_FOR_DECISION = 3
    decision_frames: list[np.ndarray] = []

    for i in range(T):
        if np.any(a[i] != 0.0):
            decision_frames.append(a[i].copy())
            if len(decision_frames) >= N_FRAMES_FOR_DECISION:
                break

    # Safety trap: Entire sequence devoid of hands -> return original sequence unmodified
    if not decision_frames:
        return seq_arr

    def _presence(frame: np.ndarray) -> tuple[bool, bool]:
        return bool(np.any(frame[:63] != 0.0)), bool(np.any(frame[63:] != 0.0))

    def _sign(x: float, *, eps: float = 1e-6) -> int:
        if x > eps:
            return 1
        if x < -eps:
            return -1
        return 0

    # Hand unification decision: majority vote across first 3-5 valid frames.
    left_only = 0
    right_only = 0
    for f in decision_frames:
        l_present, r_present = _presence(f)
        if l_present and not r_present:
            left_only += 1
        elif r_present and not l_present:
            right_only += 1

    total_single_hand = left_only + right_only
    unify_right_to_left = False
    if total_single_hand >= 2:
        # Confidence gate: require clear majority; ties/weak margins default to no unification.
        if right_only > left_only:
            margin = right_only - left_only
            if margin >= 1 and (margin / float(total_single_hand)) >= 0.6:
                unify_right_to_left = True

    # Mirror decision: sign-based voting across early frames, with confidence gating.
    mirror_needed = False
    if mirror_invariant:
        pos_votes = 0
        neg_votes = 0
        voted = 0

        for f0 in decision_frames:
            f = f0
            if unify_right_to_left:
                l_present, r_present = _presence(f)
                if r_present and not l_present:
                    u = np.zeros((126,), dtype=np.float32)
                    u[:63] = f[63:]
                    f = u

            l_present, r_present = _presence(f)
            chir = 0.0
            if l_present and not r_present:
                chir = _hand_chirality_sign_21(f[:63].reshape(21, 3))
            elif l_present and r_present:
                s_left = _hand_chirality_sign_21(f[:63].reshape(21, 3))
                s_right = _hand_chirality_sign_21(f[63:].reshape(21, 3))
                # Prefer the more confident hand; otherwise use a stable tie-breaker.
                if abs(s_left) > abs(s_right) + 1e-6:
                    chir = s_left
                elif abs(s_right) > abs(s_left) + 1e-6:
                    chir = s_right
                else:
                    chir = s_left - s_right

            v = _sign(float(chir))
            if v == 0:
                continue
            voted += 1
            if v > 0:
                pos_votes += 1
            else:
                neg_votes += 1

        # Confidence gate: if weak/insufficient evidence, do NOT mirror.
        if voted >= max(2, min(MIN_FRAMES_FOR_DECISION, len(decision_frames))):
            margin = abs(pos_votes - neg_votes)
            if margin >= 1 and (margin / float(voted)) >= 0.6:
                mirror_needed = (neg_votes > pos_votes)

    out = np.zeros_like(a)
    for i in range(T):
        f = a[i].copy()
        
        # 1) Uniform block unification pass
        l_p, r_p = _presence(f)
        if unify_right_to_left and r_p and not l_p:
            u = np.zeros((126,), dtype=np.float32)
            u[:63] = f[63:]
            f = u

        # 2) Constant structure mirror pass
        if mirror_needed:
            f = mirror_and_swap_hands_126(f, normalized=normalized)

        # 3) Defensive catch to lock structural offset if it accidentally scattered
        l_p2, r_p2 = _presence(f)
        if unify_right_to_left and r_p2 and not l_p2:
            u2 = np.zeros((126,), dtype=np.float32)
            u2[:63] = f[63:]
            f = u2

        out[i] = f

    return out.astype(np.float32)


def load_npz_features(base_dir: Path):
    """Load all .npz feature files under base_dir.

    Returns a list of dicts: { 'sequence': ndarray(T,D), 'class_idx': int|None, 'path': Path, 'meta': dict }
    """
    base = Path(base_dir)
    files = list(base.rglob("*.npz"))
    samples = []
    for p in files:
        try:
            data = np.load(p, allow_pickle=False)
        except Exception:
            # allow fallback to pickle for meta if needed (sequence should still load)
            data = np.load(p, allow_pickle=True)
        seq = None
        if 'sequence' in data:
            seq = data['sequence']
        elif 'sequences' in data:
            seq = data['sequences']
        else:
            # skip files without sequence
            continue

        # prefer external json metadata if present
        meta = {}
        meta_path = p.with_suffix('.json')
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding='utf-8'))
            except Exception:
                meta = {}
        else:
            # try to extract 'meta' inside npz if available
            try:
                if 'meta' in data:
                    # meta may be stored as an array/object; attempt to coerce to dict
                    raw = data['meta']
                    # if it's an array-like object with item(), use that
                    try:
                        meta = raw.item()
                    except Exception:
                        try:
                            meta = dict(raw)
                        except Exception:
                            meta = {}
            except Exception:
                meta = {}

        class_idx = None
        try:
            class_idx = int(meta.get('class_idx')) if meta.get('class_idx') is not None else None
        except Exception:
            class_idx = None

        samples.append({
            'sequence': np.asarray(seq, dtype=np.float32),
            'class_idx': class_idx,
            'path': p,
            'meta': meta,
        })

    # sort samples by path for deterministic order
    samples.sort(key=lambda s: str(s['path']))
    return samples


def merge_memmap(samples, output_dir: Path):
    """Merge loaded samples into a single numpy.memmap file on disk.

    samples: list from load_npz_features
    output_dir: Path where memmap and metadata will be written

    Returns meta dict with keys: total_samples, shape, dtype, memmap_path, meta_path
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not samples:
        raise ValueError("No samples provided to merge_memmap")

    # infer shape from first sample
    first = samples[0]['sequence']
    if first.ndim != 2:
        raise ValueError("Expected 2D sequences (T,D)")
    T, D = first.shape
    N = len(samples)

    # verify compatible shapes
    for s in samples:
        seq = s['sequence']
        if seq.ndim != 2:
            raise ValueError(f"Sample {s['path']} has ndim!=2")
        if seq.shape[1] != D:
            raise ValueError(f"Feature dim mismatch for {s['path']}: {seq.shape[1]} != {D}")
        if seq.shape[0] != T:
            # allow sequences with T different (should be fixed by validator) but truncate/pad if needed
            # simple behavior: truncate or pad with zeros
            arr = np.zeros((T, D), dtype=np.float32)
            if seq.shape[0] >= T:
                arr[:] = seq[:T, :]
            else:
                arr[:seq.shape[0], :] = seq
            s['sequence'] = arr

    memmap_path = out / "features.dat"
    # create memmap file
    mmap = np.memmap(str(memmap_path), dtype='float32', mode='w+', shape=(N, T, D))
    for i, s in enumerate(samples):
        mmap[i, :, :] = s['sequence']

    mmap.flush()

    # write metadata
    meta = {
        'total_samples': N,
        'shape': [N, T, D],
        'dtype': 'float32',
        'memmap_path': str(memmap_path),
    }
    meta_path = out / 'meta.json'
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')

    return {**meta, 'meta_path': str(meta_path)}
