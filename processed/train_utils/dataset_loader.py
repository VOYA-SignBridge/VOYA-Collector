from __future__ import annotations
import csv
import json
import os
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
        augment_fn: Optional[Any] = None,
    ) -> None:
        self.csv_path = Path(csv_path)
        # Whether the caller NAMED a features root, as opposed to us guessing one.
        # An explicit root has to outrank the `file_path` column (see
        # _resolve_feature_path): a split CSV carries the path the features had
        # when the split was made, so any experiment that swaps the feature tree
        # — a preprocessing ablation, a rebuilt corpus, a restored backup — was
        # silently reading the ORIGINAL tree while believing otherwise, and both
        # arms came out identical for the most convincing possible reason.
        self.root_is_explicit = bool(root)
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
        self.augment_fn = augment_fn

        # Mỗi epoch đọc lại toàn bộ .npz từ đĩa (giải nén zip cho từng mẫu) —
        # với num_workers=0 chi phí này nằm thẳng trên luồng chính và lấn át cả
        # thời gian tính của model. Giữ mảng đã giải nén trong RAM: augmentation
        # vẫn chạy lại mỗi epoch trên bản copy nên kết quả huấn luyện không đổi.
        # TRAIN_FEATURE_CACHE_MB=0 để tắt.
        try:
            budget_mb = float(os.environ.get('TRAIN_FEATURE_CACHE_MB', '512'))
        except ValueError:
            budget_mb = 512.0
        self._cache_budget_bytes = int(max(budget_mb, 0.0) * 1024 * 1024)
        self._feature_cache: Dict[str, Any] = {}
        self._cache_bytes = 0
        self._cache_full_logged = False

        # _resolve_feature_path phải stat() 1-2 lần cho mỗi mẫu để dò đúng vị trí
        # file. Trên bind mount Windows/WSL2 một stat tốn ~1 ms, nhân với số mẫu
        # × số epoch thì đây là phần đắt nhất của cả vòng huấn luyện. Layout thư
        # mục không đổi trong một lần chạy nên nhớ luôn kết quả theo chỉ số dòng.
        self._path_cache: Dict[int, Path] = {}

        self._legacy_signer_map: Dict[str, str] = {}
        try:
            mapping_path = Path(__file__).resolve().parents[2] / 'config' / 'legacy_signer_mapping.json'
            raw_map = json.loads(mapping_path.read_text(encoding='utf-8'))
            self._legacy_signer_map = dict(raw_map.get('legacy_name_to_signer_id') or {})
        except Exception:
            # Không có bảng gộp thì giữ nguyên tên thô — hành vi như trước.
            self._legacy_signer_map = {}
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
                l2i_path = Path(__file__).resolve().parents[1] / 'analysis' / 'label_to_index.json'
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

        # Drop rows whose feature file is missing or 0-byte BEFORE training.
        # A single corrupt/empty npz (e.g. a download that failed midway) used
        # to raise EOFError inside __getitem__ and kill the entire run. Pruning
        # here is a cheap stat() per row and keeps split counts self-consistent
        # (each split is its own CSV/dataset, so length changes don't misalign).
        self._prune_unreadable_rows()

    def _prune_unreadable_rows(self) -> None:
        kept: List[Dict[str, str]] = []
        dropped = 0
        for r in self.rows:
            try:
                path = self._resolve_feature_path(r)
                if path.stat().st_size > 0:
                    kept.append(r)
                else:
                    dropped += 1
            except Exception:
                dropped += 1
        if dropped:
            print(
                f"[DATASET] Pruned {dropped} unreadable/empty feature file(s) "
                f"from {self.csv_path.name}; {len(kept)} usable samples remain."
            )
        self.rows = kept

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

    def _root_relative_candidate(self, row: Dict[str, str]) -> Optional[Path]:
        """Where this row's file would live under an explicitly named root."""
        folder_name = (row.get('folder_name') or '').strip()
        file_name = (row.get('file') or '').strip()
        if not folder_name or not file_name:
            return None
        language = (row.get('language') or 'vn').strip() or 'vn'
        dialect = (row.get('dialect') or '').strip()
        if not dialect:
            lk = (row.get('label_key') or '').strip()
            _, inferred = self._infer_language_dialect_from_label_key(lk, default_language=language)
            dialect = (inferred or '').strip()
        return self.root / language / (dialect or 'common') / folder_name / file_name

    def _resolve_feature_path(self, row: Dict[str, str]) -> Path:
        # An explicitly requested root wins over the CSV's remembered path.
        # Without this, `--features_root` is accepted, reported in the run
        # config, and then ignored for every row whose `file_path` still
        # resolves — which is every row of a freshly built split.
        if getattr(self, 'root_is_explicit', False):
            cand = self._root_relative_candidate(row)
            if cand is not None and cand.exists():
                return cand

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

    def _canonical_signer(self, row: Dict[str, str]) -> str:
        """Danh tính NGƯỜI KÝ, chuẩn hoá các biến thể viết hoa/thường.

        Ưu tiên `user_id` chứ không phải `signer_id`, ngược với trực giác. Lý do:
        `signer_id` được suy ra từ TÀI KHOẢN thu thập, nên khi nhiều người cùng
        ký dưới một tài khoản thì họ bị gộp thành một. Dữ liệu hoa-de có đúng
        trường hợp đó: S010 (tài khoản "tran") chứa cả Nhung lẫn Khoa. Dùng
        signer_id ở đây sẽ khiến split "tách người" âm thầm để hai người khác
        nhau nằm cả ở train lẫn test — đúng thứ rò rỉ mà split này muốn chặn.
        `user_id` ghi tên người ký thật, còn biến thể chính tả thì đã có bảng gộp
        được chủ dữ liệu xác nhận (xem scripts/apply_signer_merges.py).
        """
        raw = (row.get('user_id') or '').strip()
        if raw:
            return self._legacy_signer_map.get(raw, raw)
        return (row.get('signer_id') or '').strip()

    def _feature_path_for(self, idx: int, row: Dict[str, str]) -> Path:
        """_resolve_feature_path có nhớ kết quả — tránh stat() lại mỗi epoch."""
        cached = self._path_cache.get(idx)
        if cached is not None:
            return cached
        resolved = self._resolve_feature_path(row)
        self._path_cache[idx] = resolved
        return resolved

    def _cache_put(self, key: str, x: "np.ndarray") -> None:
        if self._cache_budget_bytes <= 0:
            return
        nbytes = int(x.nbytes)
        if self._cache_bytes + nbytes > self._cache_budget_bytes:
            if not self._cache_full_logged:
                print(
                    f"[DATASET] feature cache đầy ở {self._cache_bytes / 1048576:.0f} MB "
                    f"({len(self._feature_cache)} mẫu); phần còn lại đọc thẳng từ đĩa. "
                    "Tăng TRAIN_FEATURE_CACHE_MB nếu còn RAM."
                )
                self._cache_full_logged = True
            return
        self._feature_cache[key] = x
        self._cache_bytes += nbytes

    def __getitem__(self, idx: int):
        r = self.rows[idx]
        path = self._feature_path_for(idx, r)

        cached = self._feature_cache.get(str(path))
        if cached is not None:
            # Bản copy: augment_fn được phép sửa tại chỗ.
            return self._finalize(r, path, cached.copy())

        try:
            with np.load(path, allow_pickle=False) as data:  # type: ignore[attr-defined]
                arr = self._choose_array_from_npz(data)
        except Exception as e:
            # Size-prefilter catches 0-byte files; this catches the rarer case
            # of a non-empty but truncated/corrupt archive. Fall back to a
            # neighbouring sample rather than crashing the whole training run.
            n = len(self.rows)
            print(f"[DATASET] Skipping corrupt feature {path} ({e}); using neighbour.")
            for step in range(1, n):
                alt_idx = (idx + step) % n
                alt = self.rows[alt_idx]
                try:
                    alt_path = self._feature_path_for(alt_idx, alt)
                    with np.load(alt_path, allow_pickle=False) as data:  # type: ignore[attr-defined]
                        arr = self._choose_array_from_npz(data)
                    r, path = alt, alt_path
                    break
                except Exception:
                    continue
            else:
                raise RuntimeError(f"No readable feature file found near index {idx}") from e
        x = np.asarray(arr, dtype=self.dtype)
        # enforce expected temporal-first shape (T, D) without modifying dimensions
        if x.ndim != 2:
            raise ValueError(f"Invalid feature shape {tuple(x.shape)} in {path}; expected 2D (T,D).")
        if tuple(x.shape) != (_EXPECTED_SEQ_LEN, _EXPECTED_FEATURE_DIM):
            raise ValueError(
                f"Invalid feature shape {tuple(x.shape)} in {path}; expected ({_EXPECTED_SEQ_LEN}, {_EXPECTED_FEATURE_DIM})."
            )

        # Cache mảng thô đã qua kiểm tra shape; augmentation/kiểm tra hữu hạn vẫn
        # chạy lại mỗi lần lấy mẫu trong _finalize.
        self._cache_put(str(path), x)
        return self._finalize(r, path, x.copy() if self.augment_fn is not None else x)

    def _finalize(self, r: Dict[str, Any], path: Any, x: "np.ndarray"):
        if self.augment_fn is not None:
            x = self.augment_fn(x)

            x = np.asarray(
                x,
                dtype=self.dtype
            )

            if tuple(x.shape) != (
                _EXPECTED_SEQ_LEN,
                _EXPECTED_FEATURE_DIM
            ):
                raise ValueError(
                    f"Augmentation returned invalid shape {tuple(x.shape)}"
                )
            
        x = np.ascontiguousarray( x, dtype=np.float32 )

        if not np.isfinite(x).all(): 
            raise ValueError( f"Non-finite values detected in {path}" )
    
        y = self._resolve_target(r)

        # All-string meta: torch default_collate rejects None values, and
        # manifest-era CSVs carry signer_id (normalized) instead of the legacy
        # free-text user_id — prefer it, fall back for old split CSVs.
        meta = {
            'sample_id': r.get('sample_id') or '',
            'label_slug': r.get('label_slug') or '',
            'label_original': r.get('label_original') or '',
            'file_path': str(path),
            'class_uid': r.get('class_uid') or '',
            'signer_id': self._canonical_signer(r),
            'language': r.get('language') or '',
            'dialect': r.get('dialect') or '',
        }

        if self.to_tensor and TORCH_AVAILABLE:
            x = torch.from_numpy(x)
            y = torch.as_tensor(y, dtype=torch.long)
        return x, y, meta

def build_dataloader(csv_path: Union[str, Path], batch_size: int = 16, shuffle: bool = True, augment_fn=None):
    if not TORCH_AVAILABLE:
        raise RuntimeError('PyTorch is not installed; DataLoader is unavailable. Use NPZSignDataset directly.')
    ds = NPZSignDataset(csv_path, to_tensor=True, augment_fn=augment_fn)
    return DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=2,
        pin_memory=True,
        persistent_workers=True,
    )
