from __future__ import annotations

from pathlib import Path
from typing import Optional


def get_code_root() -> Path:
    """Return training code root (the `train_model/` folder)."""
    return Path(__file__).resolve().parent


def get_repo_root(code_root: Optional[Path] = None) -> Path:
    """Return repository root (parent of `train_model/`)."""
    return (code_root or get_code_root()).resolve().parent


def get_data_root(code_root: Optional[Path] = None) -> Path:
    """Return dataset root directory.

    In this repo, the app writes data to <repo>/dataset by default.
    """
    repo_root = get_repo_root(code_root)
    return repo_root / "dataset"


def get_labels_csv(data_root: Optional[Path] = None) -> Path:
    return (data_root or get_data_root()) / "labels.csv"


def get_samples_csv(data_root: Optional[Path] = None) -> Path:
    # App stores samples at dataset/samples/samples.csv
    return (data_root or get_data_root()) / "samples" / "samples.csv"


def get_features_dir(data_root: Optional[Path] = None) -> Path:
    # App stores feature npz at dataset/features/...
    return (data_root or get_data_root()) / "features"


def get_analysis_dir(code_root: Optional[Path] = None) -> Path:
    # Training utilities write derived artifacts here
    root = (code_root or get_code_root()).resolve()
    return get_repo_root(root) / "processed" / "analysis"


def get_splits_dir(code_root: Optional[Path] = None) -> Path:
    root = (code_root or get_code_root()).resolve()
    return get_repo_root(root) / "processed" / "splits"
