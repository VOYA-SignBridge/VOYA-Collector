import os
import json
import tempfile
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
    seq, info = normalize_sequence(sequence_array, expected_T=int(getattr(settings, "seq_len", 60)), expected_D=int(getattr(settings, "feature_dim", 126)))
    # atomic write
    fd, tmp = tempfile.mkstemp(prefix="npztmp_", suffix=".npz", dir=label_folder)
    os.close(fd)
    try:
        with open(tmp, "wb") as f:
            np.savez_compressed(f, sequence=seq.astype(np.float32), meta=meta or {})
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp, outpath)
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except Exception: pass
    return outpath


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