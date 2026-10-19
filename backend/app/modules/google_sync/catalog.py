"""Asynchronous Google synchronization triggered by catalog mutations.

This module translates local dataset paths into Drive paths and dispatches
the existing Celery tasks. Catalog CRUD remains successful when the broker
or Google integration is unavailable; periodic tasks can reconcile it later.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)


def dataset_storage_key(local_path: Path, *, dataset_root: Path | None = None) -> str | None:
    """Return a dataset-relative POSIX path suitable for Google Drive."""
    if dataset_root is None:
        from app.dataset_manager import DATASET_ROOT

        dataset_root = DATASET_ROOT
    try:
        relative = Path(local_path).resolve().relative_to(Path(dataset_root).resolve())
    except (OSError, ValueError):
        return None
    return relative.as_posix()


def dispatch_catalog_refresh(*_legacy_rows: object) -> None:
    """Queue Drive CSV mirroring and full Sheets reconciliation.

    Positional values are accepted for compatibility with the old catalog
    helper, which received already-written rows but never used them.
    """
    try:
        from app.export_tasks import (
            export_labels_to_sheets,
            export_samples_to_sheets,
            mirror_catalog_csvs_to_drive,
        )

        mirror_catalog_csvs_to_drive.delay()
        export_labels_to_sheets.delay()
        export_samples_to_sheets.delay()
    except Exception as exc:  # dispatch failure must not break catalog CRUD
        logger.warning("[CATALOG] async Drive/Sheets sync dispatch failed: %s", exc)


def dispatch_drive_folder_delete(paths: Sequence[Path], *, dataset_root: Path | None = None) -> None:
    """Queue deletion of dataset-relative folders from Google Drive."""
    rel_paths = [
        rel
        for rel in (dataset_storage_key(path, dataset_root=dataset_root) for path in paths)
        if rel
    ]
    if not rel_paths:
        return

    try:
        from app.export_tasks import delete_gdrive_paths_task

        delete_gdrive_paths_task.delay(rel_paths=rel_paths)
    except Exception as exc:
        logger.warning("[CATALOG] Drive folder delete dispatch failed for %s: %s", rel_paths, exc)


def dispatch_drive_folder_move(
    pairs: Sequence[tuple[Path, Path]], *, dataset_root: Path | None = None
) -> None:
    """Queue Drive folder moves for local ``(old_path, new_path)`` pairs."""
    rel_pairs: list[list[str]] = []
    for old_path, new_path in pairs:
        old_rel = dataset_storage_key(old_path, dataset_root=dataset_root)
        new_rel = dataset_storage_key(new_path, dataset_root=dataset_root)
        if old_rel and new_rel and old_rel != new_rel:
            rel_pairs.append([old_rel, new_rel])
    if not rel_pairs:
        return

    try:
        from app.export_tasks import move_gdrive_paths_task

        move_gdrive_paths_task.delay(pairs=rel_pairs)
    except Exception as exc:
        logger.warning("[CATALOG] Drive folder move dispatch failed for %s: %s", rel_pairs, exc)
