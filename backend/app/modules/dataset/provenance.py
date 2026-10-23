"""Dataset split provenance and training-readiness inspection."""

from __future__ import annotations

import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from app.modules.training.schemas import SplitProvenance

logger = logging.getLogger(__name__)
WORKSPACE_ROOT = Path("/workspace")
SPLITS_DIR = WORKSPACE_ROOT / "processed" / "splits"


def provenance_from_artifact(
    artifact: Any,
    *,
    canonical_signer: Callable[[Mapping[str, object], Optional[Mapping[str, str]]], str],
    identity_column: Callable[[Sequence[str]], Optional[str]],
    legacy_signer_map: Optional[Mapping[str, str]] = None,
) -> SplitProvenance:
    """Describe the exact split artifact selected by the trainer.

    The resolver owns the choice of files.  This function only reads those
    resolved files and deliberately receives the signer helpers from the
    caller: ``processed`` is mounted at runtime and is not importable from the
    API package until ``/workspace`` has been added to ``sys.path``.
    """
    metadata = dict(getattr(artifact, "metadata", None) or {})
    provenance = SplitProvenance(
        split_id=str(getattr(artifact, "split_id", "") or "") or None,
        purpose=str(getattr(artifact, "purpose", "") or "") or None,
        owner_state=str(getattr(artifact, "owner_state", "") or "") or None,
        split_mode=metadata.get("split_mode"),
        dataset_manifest=str(metadata.get("dataset_manifest") or "") or None,
        valid_for_research=metadata.get("valid_for_research"),
    )

    paths = {
        "train": Path(artifact.train_csv),
        "val": Path(artifact.val_csv),
        "test": Path(artifact.test_csv),
    }
    seen: dict[str, set[str]] = {}
    chosen_identity: Optional[str] = None
    for part, path in paths.items():
        signers: set[str] = set()
        count = 0
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                column = identity_column(reader.fieldnames or ())
                chosen_identity = chosen_identity or column
                for row in reader:
                    count += 1
                    signer = canonical_signer(row, legacy_signer_map)
                    if signer:
                        signers.add(signer)
        except Exception as exc:
            logger.warning("[SPLIT_PROV] không đọc được %s: %s", path.name, exc)
        seen[part] = signers
        provenance.counts[part] = count
        provenance.signers[part] = sorted(signers)

    provenance.identity_column = chosen_identity
    train = seen.get("train", set())
    validation = seen.get("val", set())
    test = seen.get("test", set())
    overlap = sorted(
        (train & validation) | (train & test) | (validation & test)
    )
    provenance.signer_disjoint = bool(train and test) and not overlap

    if chosen_identity is None:
        provenance.warning = (
            "Tập dữ liệu đang dùng không có cột định danh người ký "
            "(user_id hoặc signer_id), nên KHÔNG kiểm được người ký có bị lẫn "
            "giữa các phân vùng hay không."
        )
    elif overlap:
        provenance.warning = (
            f"{len(overlap)} người ký xuất hiện ở cả các phân vùng "
            f"({', '.join(overlap[:5])}{'…' if len(overlap) > 5 else ''}). "
            "Kết quả sẽ lạc quan hơn thực tế: mô hình đã thấy chính người đó lúc học."
        )
    elif not train or not test:
        provenance.warning = "Tập huấn luyện hoặc tập đánh giá rỗng."
    return provenance


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


def split_class_uids(
    dialects: Sequence[str], splits_dir: Path = SPLITS_DIR
) -> dict[str, str]:
    """Return the classes the trainer will read from all three split parts."""
    selected = {value for value in dialects if value}
    output: dict[str, str] = {}
    for part in ("train", "val", "test"):
        path = Path(splits_dir) / f"{part}.csv"
        if not path.exists():
            continue
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    dialect = (row.get("dialect") or "").strip()
                    class_uid = (row.get("class_uid") or "").strip()
                    if class_uid and dialect and (not selected or dialect in selected):
                        output[class_uid] = dialect
        except Exception as exc:
            logger.warning("[TRAIN_VALIDATE] không đọc được split %s: %s", part, exc)
    return output


def split_classes_below_floor(
    dialects: Sequence[str], minimum_samples: int, splits_dir: Path = SPLITS_DIR
) -> list[tuple[str, str, int]]:
    """Classes present in the pinned split but below the database sample floor."""
    if minimum_samples <= 0:
        return []
    in_split = split_class_uids(dialects, splits_dir)
    if not in_split:
        return []

    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        "SELECT c.class_uid, c.label_original, c.slug, "
        "       count(s.sample_uid) FILTER (WHERE s.deleted_at IS NULL) AS n "
        "  FROM classes c LEFT JOIN samples s ON s.class_uid = c.class_uid "
        " WHERE c.class_uid = ANY(%s) "
        " GROUP BY c.class_uid, c.label_original, c.slug "
        "HAVING count(s.sample_uid) FILTER (WHERE s.deleted_at IS NULL) < %s "
        " ORDER BY 4 ASC",
        (sorted(in_split), minimum_samples),
    )
    return [
        (
            str(row.get("label_original") or row.get("slug") or row.get("class_uid") or "").strip(),
            str(row.get("class_uid") or "").strip(),
            int(row.get("n") or 0),
        )
        for row in rows
    ]


def split_row_counts(
    dialects: Sequence[str], splits_dir: Path = SPLITS_DIR
) -> dict[str, dict[str, int]]:
    selected = {value for value in dialects if value}
    output: dict[str, dict[str, int]] = {}
    for part in ("train", "val", "test"):
        path = Path(splits_dir) / f"{part}.csv"
        if not path.exists():
            continue
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    dialect = (row.get("dialect") or "").strip()
                    class_uid = (row.get("class_uid") or "").strip()
                    if not class_uid or not dialect or (selected and dialect not in selected):
                        continue
                    output.setdefault(
                        class_uid, {"train": 0, "val": 0, "test": 0}
                    )[part] += 1
        except Exception as exc:
            logger.warning("[TRAIN_VALIDATE] không đọc được split %s: %s", part, exc)
    return output


def split_evidence_problems(
    dialects: Sequence[str], minimum_samples: int, splits_dir: Path = SPLITS_DIR
) -> list[str]:
    counts = split_row_counts(dialects, splits_dir)
    if not counts:
        return []
    below: list[str] = []
    missing: list[str] = []
    for class_uid, parts in sorted(counts.items()):
        total = sum(parts.values())
        if minimum_samples > 0 and total < minimum_samples:
            below.append(f"{class_uid} ({total} hàng)")
        empty = [part for part in ("train", "val", "test") if parts[part] == 0]
        if empty:
            missing.append(f"{class_uid} (rỗng ở {'/'.join(empty)})")
    problems: list[str] = []
    if below:
        problems.append(
            f"{len(below)} lớp có tổng số hàng dưới sàn {minimum_samples}: "
            + ", ".join(below[:5])
            + (f" và {len(below) - 5} lớp nữa" if len(below) > 5 else "")
        )
    if missing:
        problems.append(
            f"{len(missing)} lớp vắng mặt ở ít nhất một phần: "
            + ", ".join(missing[:5])
            + (f" và {len(missing) - 5} lớp nữa" if len(missing) > 5 else "")
        )
    return problems


def split_snapshot(splits_dir: Path = SPLITS_DIR) -> dict[str, Any]:
    path = Path(splits_dir) / "split_metadata.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("[SPLITS] khai báo split không đọc được: %s", exc)
        return {}


def operational_splits(
    tenant_id: str, splits_dir: Path = SPLITS_DIR, workspace_root: Path = WORKSPACE_ROOT
) -> list[dict[str, Any]]:
    """List only immutable operational artifacts owned by the active tenant."""
    workspace = str(workspace_root)
    if workspace not in sys.path:
        sys.path.insert(0, workspace)
    from processed.train_utils.split_artifact import (
        SplitArtifactError,
        operational_root,
        resolve_operational,
    )

    root = operational_root(splits_dir)
    output: list[dict[str, Any]] = []
    if not root.is_dir():
        return output
    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue
        try:
            artifact = resolve_operational(splits_dir, directory.name, tenant_id=tenant_id)
        except SplitArtifactError:
            continue
        metadata = artifact.metadata or {}
        classes = metadata.get("classes") or []
        dialects = sorted(
            {str(item.get("dialect") or "") for item in classes if item.get("dialect")}
        )
        counts: dict[str, int] = {}
        for part in ("train", "val", "test"):
            try:
                with Path(getattr(artifact, f"{part}_csv")).open(encoding="utf-8") as handle:
                    counts[part] = max(sum(1 for _ in handle) - 1, 0)
            except OSError:
                counts[part] = 0
        output.append({
            "split_id": artifact.split_id,
            "dialects": dialects,
            "num_classes": int(metadata.get("num_classes") or len(classes)),
            "min_samples_per_class": (metadata.get("policy") or {}).get("min_samples_per_class"),
            "generated_at": metadata.get("generated_at"),
            "split_mode": metadata.get("split_mode"),
            "counts": counts,
        })
    output.sort(key=lambda row: str(row.get("generated_at") or ""), reverse=True)
    return output
