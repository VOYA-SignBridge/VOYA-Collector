"""Discovery and selection of deployment-ready dataset splits."""

from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path("/workspace")
_DEPLOY_SPLIT_VERSION_RE = re.compile(r"_v(\d+)$")


def deployment_splits(workspace_root: Path = WORKSPACE_ROOT) -> list[dict[str, Any]]:
    """Return valid deployment splits, newest version first."""
    found: list[dict[str, Any]] = []
    versions = workspace_root / "processed" / "splits" / "versions"
    if not versions.is_dir():
        return found

    for directory in sorted(versions.iterdir()):
        if not directory.is_dir() or "_deploy_" not in directory.name:
            continue
        if not all((directory / f"{part}.csv").exists() for part in ("train", "val", "test")):
            continue
        try:
            metadata = json.loads(
                (directory / "split_metadata.json").read_text(encoding="utf-8")
            )
        except Exception as exc:
            logger.warning("[DEPLOY_SPLIT] bỏ qua %s: %s", directory.name, exc)
            continue

        dialects: set[str] = set()
        try:
            with (directory / "train.csv").open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    value = (row.get("dialect") or "").strip()
                    if value:
                        dialects.add(value)
        except Exception as exc:
            logger.warning(
                "[DEPLOY_SPLIT] %s: không đọc được dialect (%s)",
                directory.name,
                exc,
            )
            continue

        if dialects:
            match = _DEPLOY_SPLIT_VERSION_RE.search(directory.name)
            found.append(
                {
                    "split_version": directory.name,
                    "recognition_profile": str(metadata.get("recognition_profile") or ""),
                    "dialects": dialects,
                    "_version_num": int(match.group(1)) if match else 0,
                }
            )

    found.sort(key=lambda item: item["_version_num"], reverse=True)
    logger.info(
        "[DEPLOY_SPLIT] %d split triển khai khả dụng: %s",
        len(found),
        [item["split_version"] for item in found],
    )
    return found


def deployment_split_for(
    dialects: list[str],
    workspace_root: Path = WORKSPACE_ROOT,
) -> Optional[dict[str, Any]]:
    """Pick the newest deployment split covering every requested dialect."""
    wanted = {str(dialect).strip() for dialect in dialects or [] if str(dialect).strip()}
    if not wanted:
        return None
    for candidate in deployment_splits(workspace_root):
        if wanted <= candidate["dialects"]:
            return candidate
    return None


# Compatibility names retained for callers importing the old private helpers.
_deployment_splits = deployment_splits
_deployment_split_for = deployment_split_for
