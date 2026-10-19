"""Discovery of versioned research splits and multi-fold protocols."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)
WORKSPACE_ROOT = Path("/workspace")


def research_splits(workspace_root: Path = WORKSPACE_ROOT) -> list[dict[str, Any]]:
    versions = workspace_root / "processed" / "splits" / "versions"
    if not versions.is_dir():
        return []

    def describe(directory: Path, name: str, protocol: Optional[str]):
        metadata_path = directory / "split_metadata.json"
        if not (directory / "train.csv").exists() or not metadata_path.exists():
            return None
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[SPLITS] bỏ qua %s: metadata không đọc được (%s)", name, exc)
            return None
        if not metadata.get("valid_for_research"):
            return None
        checksum = str(metadata.get("dataset_manifest_checksum") or "").strip()
        if not checksum:
            return None
        stem = Path(str(metadata.get("dataset_manifest") or "")).stem
        dataset_version = stem[len("dataset_manifest_"):] if stem.startswith("dataset_manifest_") else ""
        counts = metadata.get("counts") or {}
        signers = metadata.get("signers") or {}
        return {
            "split_version": name,
            "dataset_version": dataset_version,
            "recognition_profile": str(metadata.get("recognition_profile") or ""),
            "split_mode": str(metadata.get("split_mode") or ""),
            "num_classes": metadata.get("num_classes"),
            "counts": {key: counts.get(key) for key in ("train", "val", "test")},
            "seed": metadata.get("seed"),
            "dataset_manifest_checksum": checksum,
            "protocol": protocol,
            "held_out": sorted(signers.get("test") or []),
            "n_train_signers": len(signers.get("train") or []),
        }

    result: list[dict[str, Any]] = []
    for directory in sorted(versions.iterdir()):
        if not directory.is_dir():
            continue
        flat = describe(directory, directory.name, None)
        if flat is not None:
            result.append(flat)
            continue
        for fold_directory in sorted(directory.iterdir()):
            if fold_directory.is_dir():
                fold = describe(fold_directory, f"{directory.name}/{fold_directory.name}", directory.name)
                if fold is not None:
                    result.append(fold)
    return result


def evaluation_protocols(workspace_root: Path = WORKSPACE_ROOT) -> list[dict[str, Any]]:
    versions = workspace_root / "processed" / "splits" / "versions"
    if not versions.is_dir():
        return []
    result: list[dict[str, Any]] = []
    for directory in sorted(versions.iterdir()):
        if not directory.is_dir() or (directory / "train.csv").exists():
            continue
        folds = []
        for subdirectory in sorted(directory.iterdir()):
            if not subdirectory.is_dir() or not all(
                (subdirectory / f"{part}.csv").exists() for part in ("train", "test")
            ):
                continue
            try:
                metadata = json.loads((subdirectory / "split_metadata.json").read_text(encoding="utf-8"))
            except Exception:
                metadata = {}
            folds.append({
                "fold": subdirectory.name,
                "split_mode": metadata.get("split_mode"),
                "num_classes": metadata.get("num_classes"),
                "counts": metadata.get("counts") or {},
                "held_out": sorted((metadata.get("signers") or {}).get("test") or []),
            })
        if len(folds) < 2:
            continue
        modes = {fold["split_mode"] for fold in folds if fold["split_mode"]}
        result.append({
            "protocol": directory.name,
            "n_folds": len(folds),
            "split_mode": sorted(modes)[0] if len(modes) == 1 else "mixed",
            "num_classes": folds[0].get("num_classes"),
            "folds": folds,
        })
    return result


_research_splits = research_splits
_evaluation_protocols = evaluation_protocols
