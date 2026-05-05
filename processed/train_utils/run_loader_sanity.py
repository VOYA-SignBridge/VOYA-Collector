from pathlib import Path
from itertools import islice

try:
    # When run as module: python -m processed.train_utils.run_loader_sanity
    from .dataset_loader import NPZSignDataset  # type: ignore
except Exception:  # pragma: no cover
    # When run as script: python processed/train_utils/run_loader_sanity.py
    import sys
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from train_model.train_utils.dataset_loader import NPZSignDataset  # type: ignore

ROOT = Path(__file__).resolve().parents[2]
try:
    from train_model.dataset_versioning import get_splits_dir
    TRAIN_CSV = get_splits_dir() / 'train.csv'
except Exception:
    TRAIN_CSV = Path(__file__).resolve().parents[1] / 'processed' / 'splits' / 'train.csv'


def main():
    ds = NPZSignDataset(TRAIN_CSV)
    print('Dataset length:', len(ds))
    for i, (x, y, meta) in enumerate(islice(ds, 0, 4)):
        print(f'[{i}] shape={getattr(x, "shape", None)} class_idx={y} slug={meta.get("label_slug")} file={Path(meta.get("file_path", "")).name}')


if __name__ == '__main__':
    main()
