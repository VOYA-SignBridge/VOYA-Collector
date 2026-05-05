from __future__ import annotations
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import numpy as np
except Exception as e:  # pragma: no cover
    np = None  # type: ignore

# Optional torch support
try:
    import torch
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except Exception:
    Dataset = object  # type: ignore
    DataLoader = object  # type: ignore
    TORCH_AVAILABLE = False


_FEATURE_DIM_TRUNCATE_WARNED = False
_EXPECTED_SEQ_LEN = 60
_EXPECTED_FEATURE_DIM = 126


class NPZSignDataset(Dataset):  # type: ignore[misc]
    """
    Minimal dataset for sign features stored as .npz.

    Returns (X, y, meta):
      - X: numpy array (T, D) or (D,) (torch tensor if torch available and to_tensor=True)
            - y: int class index (normalized to 0-based)
      - meta: dict with keys: sample_id, label_slug, label_original, file_path
    """

    def __init__(
        self,
        csv_path: Union[str, Path],
        root: Optional[Union[str, Path]] = None,
        label_to_index_json: Optional[Union[str, Path]] = None,
        to_tensor: bool = False,
        feature_key_priority: Optional[List[str]] = None,
        dtype: str = "float32",
    ) -> None:
        self.csv_path = Path(csv_path)
        if root:
            self.root = Path(root)
        else:
            try:
                from train_model.dataset_versioning import get_features_dir, get_data_root
                self.root = get_features_dir(get_data_root())
            except Exception:
                # Fallback heuristic: <repo>/dataset/features, where repo is parent of train_model/
                self.root = Path(__file__).resolve().parents[1].parent / 'dataset' / 'features'
        self.rows: List[Dict[str, str]] = []
        self.to_tensor = bool(to_tensor and TORCH_AVAILABLE)
        self.dtype = dtype
        self.feature_key_priority = feature_key_priority or [
            'sequence',
            'features', 'x', 'data', 'arr_0'
        ]

        # label mapping (optional, fallback to labels.csv / class_idx in CSV)
        self.label_to_index: Dict[str, int] = {}
        self.index_to_label: Dict[int, Dict[str, str]] = {}
        self._class_idx_to_label: Dict[int, Dict[str, str]] = {}
        if label_to_index_json:
            l2i_path = Path(label_to_index_json)
        else:
            try:
                from train_model.dataset_versioning import get_analysis_dir
                l2i_path = get_analysis_dir() / 'label_to_index.json'
            except Exception:
                l2i_path = Path(__file__).resolve().parents[1] / 'processed' / 'analysis' / 'label_to_index.json'
        i2l_path = l2i_path.with_name('index_to_label.json')
        try:
            self.label_to_index = json.loads(l2i_path.read_text(encoding='utf-8'))
        except Exception:
            self.label_to_index = {}
        try:
            raw = json.loads(i2l_path.read_text(encoding='utf-8'))
            # keys may be strings in json; convert to int
            self.index_to_label = {int(k): v for k, v in raw.items()}
        except Exception:
            self.index_to_label = {}

        # fallback to labels.csv if mapping JSON is missing or empty
        if not self.label_to_index:
            try:
                from train_model.dataset_versioning import get_labels_csv, get_data_root
                labels_csv = get_labels_csv(get_data_root())
            except Exception:
                labels_csv = Path(__file__).resolve().parents[1].parent / 'dataset' / 'labels.csv'
            if labels_csv.exists():
                with labels_csv.open('r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        try:
                            class_idx = int((r.get('class_idx') or '').strip())
                        except Exception:
                            continue
                        slug = (r.get('slug') or '').strip()
                        language = (r.get('language') or 'vn').strip()
                        dialect = (r.get('dialect') or '').strip()
                        label_key = f"{language}/{dialect}/{slug}" if dialect else f"{language}/{slug}"
                        self.label_to_index[label_key] = class_idx - 1
                        self._class_idx_to_label[class_idx] = {
                            'label_key': label_key,
                            'label_slug': slug,
                            'label_original': (r.get('label_original') or '').strip(),
                            'language': language,
                            'dialect': dialect,
                        }
                if self.label_to_index:
                    self.index_to_label = {v: {
                        'label_key': k,
                        'label_slug': (self._class_idx_to_label.get(v + 1, {}).get('label_slug') or ''),
                        'label_original': (self._class_idx_to_label.get(v + 1, {}).get('label_original') or ''),
                        'language': (self._class_idx_to_label.get(v + 1, {}).get('language') or 'vn'),
                        'dialect': (self._class_idx_to_label.get(v + 1, {}).get('dialect') or ''),
                    } for k, v in self.label_to_index.items()}

        # load CSV rows
        with self.csv_path.open('r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                self.rows.append(r)

        if np is None:
            raise RuntimeError('numpy is required to load .npz files but is not installed.')

        # normalize labels to 0-based if inputs are 1-based
        self._label_offset = 0
        try:
            if self.label_to_index:
                vals = list(self.label_to_index.values())
                if vals and (min(vals) >= 1) and (0 not in set(vals)):
                    self._label_offset = 1
            else:
                idxs = []
                for r in self.rows:
                    v = r.get('class_idx')
                    if v is not None and v != '':
                        try:
                            idxs.append(int(v))
                        except Exception:
                            pass
                if idxs and (min(idxs) >= 1) and (0 not in set(idxs)):
                    self._label_offset = 1
        except Exception:
            # be conservative; leave offset at 0 if any issue arises
            self._label_offset = 0

    def __len__(self) -> int:
        return len(self.rows)

    def _resolve_target(self, row: Dict[str, str]) -> int:
        # Prefer explicit label_key (language/dialect/slug) via mapping.
        label_key = (row.get('label_key') or '').strip()
        if label_key and self.label_to_index:
            idx = self.label_to_index.get(label_key)
            if idx is not None:
                return int(idx) - int(self._label_offset)
            raise ValueError(f"Invalid label_key '{label_key}' not found in label mapping.")

        # Next: try building label_key from CSV fields.
        slug = (row.get('label_slug') or '').strip()
        if slug and self.label_to_index:
            dialect = (row.get('dialect') or '').strip()
            language = (row.get('language') or 'vn').strip()
            candidate_key = f"{language}/{dialect}/{slug}" if dialect else f"{language}/{slug}"
            idx = self.label_to_index.get(candidate_key)
            if idx is not None:
                return int(idx) - int(self._label_offset)

            # Backward-compat: older label_to_index keyed by slug only.
            idx = self.label_to_index.get(slug)
            if idx is not None:
                return int(idx) - int(self._label_offset)
        # fallback to class_idx (must be valid)
        try:
            class_idx = int(row['class_idx'])
        except Exception:
            raise ValueError(f"Invalid class_idx '{row.get('class_idx')}' in row; cannot resolve label.")
        if self._class_idx_to_label and class_idx not in self._class_idx_to_label:
            raise ValueError(f"class_idx '{class_idx}' not found in labels.csv mapping.")
        return int(class_idx) - int(self._label_offset)

    def _infer_language_dialect_from_label_key(self, label_key: str, *, default_language: str = 'vn') -> Tuple[str, str]:
        lk = (label_key or '').strip()
        if not lk:
            return (default_language, '')
        parts = [p for p in lk.split('/') if p]
        if len(parts) >= 3:
            return (parts[0], parts[1])
        if len(parts) == 2:
            return (parts[0], '')
        return (default_language, '')

    def _resolve_feature_path(self, row: Dict[str, str]) -> Path:
        file_path = (row.get('file_path') or '').strip()
        if file_path:
            candidate = Path(file_path)
            if candidate.exists():
                return candidate
            if file_path.startswith('/dataset/'):
                repo_root = Path(__file__).resolve().parents[2]
                mapped = repo_root / file_path.lstrip('/')
                if mapped.exists():
                    return mapped
            # Some rows may store absolute paths from a different environment; keep legacy fallback below.

        folder_name = (row.get('folder_name') or '').strip()
        file_name = (row.get('file') or '').strip()
        if not folder_name or not file_name:
            if file_path:
                raise FileNotFoundError(f"Feature file not found at file_path '{file_path}'.")
            raise FileNotFoundError("Row is missing folder_name or file; cannot resolve feature path.")

        language = (row.get('language') or 'vn').strip() or 'vn'
        dialect = (row.get('dialect') or '').strip()
        if not dialect:
            lk = (row.get('label_key') or '').strip()
            _, inferred_dialect = self._infer_language_dialect_from_label_key(lk, default_language=language)
            dialect = (inferred_dialect or '').strip()

        candidates: List[Path] = []
        if dialect:
            candidates.append(self.root / language / dialect / folder_name / file_name)
        else:
            # dialect missing: try language/common
            candidates.append(self.root / language / 'common' / folder_name / file_name)

        for cand in candidates:
            if cand.exists():
                return cand
        raise FileNotFoundError(
            "Missing feature file. Tried: " + " | ".join(str(p) for p in candidates)
        )

    def _choose_array_from_npz(self, npz: Any) -> Any:
        # try priority keys
        for k in self.feature_key_priority:
            if k in npz:
                return npz[k]
        # otherwise first array-like
        for k in npz.keys():
            try:
                arr = npz[k]
                # basic check array-ness
                _ = getattr(arr, 'shape', None)
                return arr
            except Exception:
                continue
        raise KeyError('No array found in npz archive')

    def __getitem__(self, idx: int):
        r = self.rows[idx]
        path = self._resolve_feature_path(r)
        with np.load(path, allow_pickle=False) as data:  # type: ignore[attr-defined]
            arr = self._choose_array_from_npz(data)
        x = np.asarray(arr, dtype=self.dtype)
        # enforce expected temporal-first shape (T, D) without modifying dimensions
        if x.ndim != 2:
            raise ValueError(f"Invalid feature shape {tuple(x.shape)} in {path}; expected 2D (T,D).")
        if tuple(x.shape) != (_EXPECTED_SEQ_LEN, _EXPECTED_FEATURE_DIM):
            raise ValueError(
                f"Invalid feature shape {tuple(x.shape)} in {path}; expected ({_EXPECTED_SEQ_LEN}, {_EXPECTED_FEATURE_DIM})."
            )
        y = self._resolve_target(r)

        meta = {
            'sample_id': r.get('sample_id'),
            'label_slug': r.get('label_slug'),
            'label_original': r.get('label_original'),
            'file_path': str(path),
        }

        if self.to_tensor and TORCH_AVAILABLE:
            x = torch.from_numpy(x)
            y = torch.as_tensor(y, dtype=torch.long)
        return x, y, meta


def pad_collate_fn(
    batch: List[Tuple[Any, int, Dict[str, Any]]],
    *,
    feature_dim: Optional[int] = None,
    on_feature_dim_mismatch: str = "truncate",
    log_feature_dim_mismatch: bool = False,
    max_log_paths: int = 3,
):
    """Pad variable-length time series to max length in batch (temporal axis=0).

    Returns (X_pad, y_tensor, lengths, metas).

    feature_dim:
      - None (default): pad feature dimension to max D in the batch (legacy behavior)
      - int: enforce a fixed feature dimension across all batches.

    on_feature_dim_mismatch: when feature_dim is set and a sample has D > feature_dim
      - 'truncate' (default): truncate to feature_dim
      - 'error': raise an error
    """

    if not TORCH_AVAILABLE:
        xs, ys, metas = zip(*batch)
        lengths = [x.shape[0] if hasattr(x, 'shape') and len(x.shape) >= 1 else 1 for x in xs]
        return list(xs), list(ys), lengths, list(metas)

    xs, ys, metas = zip(*batch)
    xs = list(xs)
    ys_t = torch.as_tensor(ys, dtype=torch.long)
    lengths = torch.as_tensor([x.shape[0] for x in xs], dtype=torch.long)
    if feature_dim is None:
        D = max(int(x.shape[1]) if x.ndim >= 2 else 1 for x in xs)
    else:
        D = int(feature_dim)
    T = int(lengths.max())
    X_pad = torch.zeros((len(xs), T, D), dtype=xs[0].dtype)
    for i, x in enumerate(xs):
        t = x.shape[0]
        d = x.shape[1] if x.ndim >= 2 else 1
        if feature_dim is not None and d > D:
            if on_feature_dim_mismatch == 'error':
                raise RuntimeError(f"Sample feature dim {d} exceeds fixed feature_dim={D}")
            # default: truncate
            global _FEATURE_DIM_TRUNCATE_WARNED
            if log_feature_dim_mismatch and not _FEATURE_DIM_TRUNCATE_WARNED:
                try:
                    # log a few example paths to help trace upstream feature extraction issues
                    example_paths: List[str] = []
                    for j in range(min(len(metas), max(1, int(max_log_paths)))):
                        p = metas[j].get('file_path') if isinstance(metas[j], dict) else None
                        if p:
                            example_paths.append(str(p))
                    suffix = (" Examples: " + " | ".join(example_paths)) if example_paths else ""
                except Exception:
                    suffix = ""
                print(
                    f"[WARN] Feature dim mismatch: truncating sample features from D={d} to fixed feature_dim={D}."
                    + suffix
                )
                _FEATURE_DIM_TRUNCATE_WARNED = True
            x = x[:, :D]
            d = D
        if d != D:
            # right-pad feature dimension if needed
            tmp = torch.zeros((t, D), dtype=X_pad.dtype)
            tmp[:, :d] = x if isinstance(x, torch.Tensor) else torch.from_numpy(x)
            X_pad[i, :t] = tmp
        else:
            X_pad[i, :t] = x if isinstance(x, torch.Tensor) else torch.from_numpy(x)
    return X_pad, ys_t, lengths, list(metas)


def build_dataloader(csv_path: Union[str, Path], batch_size: int = 16, shuffle: bool = True):
    if not TORCH_AVAILABLE:
        raise RuntimeError('PyTorch is not installed; DataLoader is unavailable. Use NPZSignDataset directly.')
    ds = NPZSignDataset(csv_path, to_tensor=True)
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle, collate_fn=pad_collate_fn)
