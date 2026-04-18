import os
import json
import tempfile
import logging
from pathlib import Path
from typing import Any, Union

import numpy as np

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

def ema_smooth_sequence(sequence_array: np.ndarray, alpha: float = 0.2) -> np.ndarray:
    """
    Apply exponential moving average smoothing per time step.
    sequence_array: shape (T, D)
    """
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


def mirror_and_swap_hands_126(vec: np.ndarray, *, normalized: bool = False) -> np.ndarray:
    """Mirror a 126-dim (2*21*3) hand vector and swap hands.

    - If not normalized (MediaPipe raw), x is assumed in [0,1] so mirror uses x -> 1 - x.
    - If normalized/centered, mirror uses x -> -x.
    """
    v = np.asarray(vec, dtype=np.float32)
    if v.size != 126:
        return v
    left, right = _hand_blocks_126(v)
    if normalized:
        left[:, 0] = -left[:, 0]
        right[:, 0] = -right[:, 0]
    else:
        left[:, 0] = 1.0 - left[:, 0]
        right[:, 0] = 1.0 - right[:, 0]

    out = np.zeros((126,), dtype=np.float32)
    out[:63] = right.reshape(63)
    out[63:] = left.reshape(63)
    return out


def canonicalize_hands_126(vec: np.ndarray, *, normalized: bool = False, mirror_invariant: bool = True) -> np.ndarray:
    """Make a 126-dim hand vector more invariant to left/right hand and mirroring.

    Steps:
    1) If only one hand is present (other block all zeros), always place it in the first block.
    2) Optionally choose canonical orientation between vec and mirror+swap(vec).
    """
    v = np.asarray(vec, dtype=np.float32)
    if v.size != 126:
        return v

    left = v[:63]
    right = v[63:]
    left_present = bool(np.any(left != 0.0))
    right_present = bool(np.any(right != 0.0))

    # One-hand canonicalization: dominant hand always in first block.
    if right_present and not left_present:
        v2 = np.zeros((126,), dtype=np.float32)
        v2[:63] = right
        return canonicalize_hands_126(v2, normalized=normalized, mirror_invariant=mirror_invariant)

    if mirror_invariant:
        m = mirror_and_swap_hands_126(v, normalized=normalized)
        # Choose deterministic canonical form (bytewise) so vec and its mirror map identically.
        return v if v.tobytes() <= m.tobytes() else m

    return v


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
