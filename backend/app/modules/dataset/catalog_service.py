"""Read-only dataset catalogue used by training APIs."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable, Optional

from app.modules.training.schemas import DatasetInfo, SplitProvenance

WORKSPACE_ROOT = Path("/workspace")
DATASET_ROOT = WORKSPACE_ROOT / "dataset"
SAMPLES_CSV = DATASET_ROOT / "samples.csv"
LABELS_CSV = DATASET_ROOT / "labels.csv"


def load_samples_and_labels(
    samples_csv: Path = SAMPLES_CSV,
    labels_csv: Path = LABELS_CSV,
) -> tuple[list[dict], list[dict]]:
    samples: list[dict] = []
    labels: dict[str, dict] = {}
    if labels_csv.exists():
        with labels_csv.open("r", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                class_uid = row.get("class_uid", "").strip()
                if class_uid:
                    labels[class_uid] = row
    if samples_csv.exists():
        with samples_csv.open("r", encoding="utf-8") as handle:
            samples.extend(csv.DictReader(handle))
    return samples, list(labels.values())


def dialects_by_language(labels: list[dict]) -> dict[str, list[str]]:
    dialects: dict[str, set[str]] = {}
    for label in labels:
        language = label.get("language", "vn").strip() or "vn"
        dialect = label.get("dialect", "").strip()
        dialects.setdefault(language, set())
        if dialect:
            dialects[language].add(dialect)
    return {language: sorted(values) for language, values in dialects.items()}


def profiles_for_dialects(
    dialects: list[str],
    *,
    labels_csv: Path = LABELS_CSV,
) -> tuple[list[str], list[str]]:
    _, labels = load_samples_and_labels(labels_csv=labels_csv)
    wanted = {str(value).strip() for value in dialects if str(value).strip()}
    by_dialect: dict[str, set[str]] = {}
    for label in labels:
        dialect = str(label.get("dialect") or "").strip()
        profile = str(label.get("recognition_profile") or "").strip()
        if dialect in wanted and profile:
            by_dialect.setdefault(dialect, set()).add(profile)
    profiles: list[str] = []
    unsupported: list[str] = []
    for dialect in sorted(wanted):
        found = {p for p in by_dialect.get(dialect, set()) if p != "legacy_unassigned"}
        if found:
            profiles.extend(found)
        else:
            unsupported.append(dialect)
    return sorted(set(profiles)), unsupported


def build_dataset_info(
    *,
    dialect: Optional[str],
    language: Optional[str],
    effective_provenance: Callable[[Optional[str]], SplitProvenance],
    samples_csv: Path = SAMPLES_CSV,
    labels_csv: Path = LABELS_CSV,
) -> DatasetInfo:
    samples, labels = load_samples_and_labels(samples_csv, labels_csv)
    dialect_map = dialects_by_language(labels)
    if dialect or language:
        labels_by_uid = {
            label.get("class_uid", "").strip(): label
            for label in labels
            if label.get("class_uid", "").strip()
        }
        matching = {
            uid for uid, label in labels_by_uid.items()
            if (not language or (label.get("language", "vn").strip() or "vn") == language)
            and (not dialect or label.get("dialect", "").strip() == dialect)
        }
        samples = [sample for sample in samples if sample.get("class_uid", "").strip() in matching]
    class_counts: dict[str, int] = {}
    for sample in samples:
        uid = sample.get("class_uid", "").strip()
        if uid:
            class_counts[uid] = class_counts.get(uid, 0) + 1
    uid_to_dialect = {
        label.get("class_uid", "").strip(): label.get("dialect", "").strip()
        for label in labels if label.get("class_uid", "").strip()
    }
    samples_by_dialect: dict[str, int] = {}
    for sample in samples:
        value = uid_to_dialect.get(sample.get("class_uid", "").strip(), "")
        if value:
            samples_by_dialect[value] = samples_by_dialect.get(value, 0) + 1
    provenance = effective_provenance(dialect)
    return DatasetInfo(
        total_samples=len(samples),
        total_classes=len(class_counts),
        languages=list(dialect_map),
        dialects=dialect_map,
        class_distribution=class_counts,
        samples_by_dialect=samples_by_dialect,
        split_info=provenance.counts or None,
        split_provenance=provenance,
    )


_load_samples_and_labels = load_samples_and_labels
_profiles_for_dialects = profiles_for_dialects
