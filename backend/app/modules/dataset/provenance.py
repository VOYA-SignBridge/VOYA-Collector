"""Dataset split provenance and training-readiness inspection."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Optional

from app.modules.dataset.split_selection import deployment_split_for
from app.modules.training.schemas import SplitProvenance

logger = logging.getLogger(__name__)
WORKSPACE_ROOT = Path("/workspace")
SPLITS_DIR = WORKSPACE_ROOT / "processed" / "splits"


def provenance_from_dir(split_dir: Path) -> SplitProvenance:
    provenance = SplitProvenance()
    metadata_path = split_dir / "split_metadata.json"
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            provenance.split_mode = metadata.get("split_mode")
            provenance.dataset_manifest = str(metadata.get("dataset_manifest") or "") or None
            provenance.valid_for_research = metadata.get("valid_for_research")
        except Exception as exc:
            logger.warning("[SPLIT_PROV] không đọc được split_metadata.json: %s", exc)

    identity_column: Optional[str] = None
    seen: dict[str, set[str]] = {}
    for part in ("train", "val", "test"):
        path = split_dir / f"{part}.csv"
        if not path.exists():
            continue
        signers: set[str] = set()
        count = 0
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                columns = reader.fieldnames or []
                column = "signer_id" if "signer_id" in columns else (
                    "user_id" if "user_id" in columns else None
                )
                identity_column = identity_column or column
                for row in reader:
                    count += 1
                    signer = (row.get(column) or "").strip() if column else ""
                    if signer:
                        signers.add(signer)
        except Exception as exc:
            logger.warning("[SPLIT_PROV] không đọc được %s: %s", path.name, exc)
            continue
        seen[part] = signers
        provenance.counts[part] = count
        provenance.signers[part] = sorted(signers)

    train, validation, test = (
        seen.get("train", set()), seen.get("val", set()), seen.get("test", set())
    )
    overlap = sorted((train & test) | (train & validation))
    provenance.signer_disjoint = bool(train and test) and not overlap
    if identity_column is None and (train or validation or test or provenance.counts):
        provenance.warning = (
            "Tập dữ liệu đang dùng không có cột định danh người ký "
            "(signer_id hoặc user_id), nên KHÔNG kiểm được người ký có bị lẫn "
            "giữa huấn luyện và đánh giá hay không."
        )
    elif not metadata_path.exists():
        provenance.warning = (
            "Tập dữ liệu đang dùng không có split_metadata.json, nên không thể "
            "xác định nó được chia thế nào."
        )
    elif overlap:
        provenance.warning = (
            f"{len(overlap)} người ký xuất hiện ở cả tập huấn luyện và tập đánh giá "
            f"({', '.join(overlap[:5])}{'…' if len(overlap) > 5 else ''}). Kết quả sẽ "
            "lạc quan hơn thực tế: mô hình đã thấy chính người đó lúc học."
        )
    elif not train or not test:
        provenance.warning = "Tập huấn luyện hoặc tập đánh giá rỗng."
    return provenance


def root_split_provenance(workspace_root: Path = WORKSPACE_ROOT) -> SplitProvenance:
    return provenance_from_dir(workspace_root / "processed" / "splits")


def effective_split_provenance(
    dialect: Optional[str], workspace_root: Path = WORKSPACE_ROOT
) -> SplitProvenance:
    if dialect:
        try:
            chosen = deployment_split_for([dialect], workspace_root)
            if chosen:
                directory = workspace_root / "processed" / "splits" / "versions" / chosen["split_version"]
                if (directory / "train.csv").exists():
                    result = provenance_from_dir(directory)
                    result.dataset_manifest = result.dataset_manifest or chosen["split_version"]
                    result.is_deployment_split = True
                    return result
        except Exception as exc:
            logger.warning("[SPLIT_PROV] không phân giải được split cho dialect %s: %s", dialect, exc)
    return root_split_provenance(workspace_root)


def trainable_dialects(workspace_root: Path = WORKSPACE_ROOT) -> dict[str, int]:
    train_csv = workspace_root / "processed" / "splits" / "train.csv"
    classes: dict[str, set[str]] = {}
    if not train_csv.exists():
        return {}
    try:
        with train_csv.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                dialect = (row.get("dialect") or "").strip()
                class_id = (row.get("class_idx") or row.get("label_key") or "").strip()
                if dialect and class_id:
                    classes.setdefault(dialect, set()).add(class_id)
    except Exception as exc:
        logger.warning("[TRAIN_VALIDATE] không đọc được train split: %s", exc)
        return {}
    return {dialect: len(values) for dialect, values in classes.items()}


_provenance_from_dir = provenance_from_dir
_root_split_provenance = root_split_provenance
_effective_split_provenance = effective_split_provenance
_trainable_dialects_from_splits = trainable_dialects
