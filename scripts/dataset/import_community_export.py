#!/usr/bin/env python3
"""Import a downloaded Drive ``Community`` tree into the local dataset.

The Drive layout is intentionally different from the on-disk layout:

    Community/Samples/...  -> dataset/features/...
    Community/Videos/...   -> dataset/raw_videos/...

Google Sheets exported as XLSX are the catalogue snapshot.  This utility reads
them without a third-party XLSX dependency, projects them onto the repository's
CSV contracts, and copies only artefacts referenced by those catalogues.

Dry-run is the default.  ``--apply`` writes catalogues atomically and copies
files through ``*.part`` paths.  The source export is never modified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence
from xml.etree import ElementTree as ET


DEFAULT_TENANT_ID = "default"

LABEL_FIELDS = [
    "class_uid", "class_idx", "slug", "label_original", "language",
    "dialect", "is_common_global", "is_common_language", "folder_name",
    "created_at", "migrated_at", "hands_required", "semantic_label",
    "vocabulary_scope", "recognition_profile", "vocabulary_group",
    "collection_campaign", "is_active", "motion_type", "tenant_id", "region",
]

SAMPLE_FIELDS = [
    "sample_uid", "class_uid", "slug", "label_original", "language",
    "dialect", "source_type", "user_id", "session_id", "fps_original",
    "fps_processed", "seq_len", "augment_id", "completeness", "file_path",
    "storage_key", "storage_url", "checksum", "created_at", "left_hand_ratio",
    "right_hand_ratio", "both_hands_ratio", "jitter", "quality_flags",
    "signer_id", "collection_campaign", "raw_landmarks_available",
    "normalization_version", "preprocess_contract_version",
    "sequence_length_original", "quality_status", "auth_user_id", "tenant_id",
    "review_status",
]

RAW_UPLOAD_FIELDS = [
    "upload_uid", "class_uid", "slug", "label_original", "language",
    "dialect", "source_type", "user_id", "session_id", "original_filename",
    "local_path", "storage_key", "storage_url", "created_at", "updated_at",
    "tenant_id", "visibility",
]

WORKBOOKS = {
    "labels": ("community - Labels.xlsx", "labels"),
    "samples": ("community - Samples.xlsx", "samples"),
    "videos": ("community - Videos.xlsx", "videos"),
}

_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_REL_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_NS_REL_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


class ImportRefused(RuntimeError):
    """The export cannot be imported without guessing or overwriting data."""


@dataclass(frozen=True)
class CopyItem:
    source: Path
    destination: Path
    catalog_key: str
    relocated: bool = False


@dataclass
class ImportPlan:
    labels: list[dict[str, str]] = field(default_factory=list)
    samples: list[dict[str, str]] = field(default_factory=list)
    videos: list[dict[str, str]] = field(default_factory=list)
    copies: list[CopyItem] = field(default_factory=list)
    relocated_samples: list[dict[str, str]] = field(default_factory=list)
    unreferenced_samples: list[str] = field(default_factory=list)
    duplicate_unreferenced_samples: list[str] = field(default_factory=list)
    unique_unreferenced_samples: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    value = 0
    for ch in letters.upper():
        value = value * 26 + ord(ch) - ord("A") + 1
    return value - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(node.text or "" for node in item.iter(f"{{{_NS_MAIN}}}t"))
        for item in root.findall(f"{{{_NS_MAIN}}}si")
    ]


def _sheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relation_id = None
    for sheet in workbook.findall(f".//{{{_NS_MAIN}}}sheet"):
        if sheet.attrib.get("name") == sheet_name:
            relation_id = sheet.attrib.get(f"{{{_NS_REL_DOC}}}id")
            break
    if not relation_id:
        raise ImportRefused(f"XLSX has no sheet named {sheet_name!r}")

    relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for relation in relations.findall(f"{{{_NS_REL_PKG}}}Relationship"):
        if relation.attrib.get("Id") == relation_id:
            target = relation.attrib.get("Target", "").replace("\\", "/")
            if target.startswith("/"):
                return target.lstrip("/")
            return str(PurePosixPath("xl") / target)
    raise ImportRefused(f"XLSX relationship {relation_id!r} is missing")


def _cell_value(cell: ET.Element, shared: Sequence[str]) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{{{_NS_MAIN}}}t"))
    value = cell.find(f"{{{_NS_MAIN}}}v")
    raw = value.text if value is not None and value.text is not None else ""
    if cell_type == "s" and raw:
        try:
            return shared[int(raw)]
        except (ValueError, IndexError) as exc:
            raise ImportRefused(f"invalid shared-string index {raw!r}") from exc
    if cell_type == "b":
        return "1" if raw == "1" else "0"
    return raw


def read_xlsx_rows(path: Path, sheet_name: str) -> list[dict[str, str]]:
    """Read one worksheet as dictionaries using the XLSX OpenXML payload."""
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ImportRefused(f"cannot open workbook {path}: {exc}") from exc
    with archive:
        shared = _shared_strings(archive)
        worksheet = ET.fromstring(archive.read(_sheet_path(archive, sheet_name)))
        matrix: list[list[str]] = []
        for row in worksheet.findall(f".//{{{_NS_MAIN}}}sheetData/{{{_NS_MAIN}}}row"):
            values: dict[int, str] = {}
            for cell in row.findall(f"{{{_NS_MAIN}}}c"):
                index = _column_index(cell.attrib.get("r", "A1"))
                values[index] = _cell_value(cell, shared).strip()
            if values:
                width = max(values) + 1
                matrix.append([values.get(index, "") for index in range(width)])
        if not matrix:
            return []
        headers = matrix[0]
        if not headers or any(not name for name in headers):
            raise ImportRefused(f"{path.name}/{sheet_name} has a blank header")
        if len(set(headers)) != len(headers):
            raise ImportRefused(f"{path.name}/{sheet_name} has duplicate headers")
        return [
            {name: (values[index] if index < len(values) else "")
             for index, name in enumerate(headers)}
            for values in matrix[1:]
            if any(values)
        ]


def _require_columns(rows: Sequence[Mapping[str, str]], columns: Iterable[str], label: str) -> None:
    if not rows:
        raise ImportRefused(f"{label} contains no data rows")
    missing = sorted(set(columns) - set(rows[0]))
    if missing:
        raise ImportRefused(f"{label} is missing columns: {', '.join(missing)}")


def _require_unique(rows: Sequence[Mapping[str, str]], field_name: str, label: str) -> None:
    values = [str(row.get(field_name) or "").strip() for row in rows]
    if any(not value for value in values):
        raise ImportRefused(f"{label} contains a blank {field_name}")
    duplicates = [value for value, count in Counter(values).items() if count > 1]
    if duplicates:
        raise ImportRefused(
            f"{label} contains duplicate {field_name}: {', '.join(duplicates[:5])}"
        )


def _project(row: Mapping[str, str], fields: Sequence[str], tenant_id: str) -> dict[str, str]:
    projected = {field: str(row.get(field) or "").strip() for field in fields}
    if "tenant_id" in projected:
        projected["tenant_id"] = tenant_id
    return projected


def _normalise_storage_key(value: str, expected_tree: str) -> str:
    raw = str(value or "").strip().replace("\\", "/").strip("/")
    if not raw:
        raise ImportRefused(f"blank {expected_tree} storage key")
    if len(raw) >= 2 and raw[1] == ":":
        raise ImportRefused(f"absolute Windows path is not allowed: {value!r}")
    parts = [part for part in raw.split("/") if part]
    if any(part in (".", "..") for part in parts):
        raise ImportRefused(f"path traversal is not allowed: {value!r}")
    if parts and parts[0].lower() == "dataset":
        parts = parts[1:]
    drive_alias = "samples" if expected_tree == "features" else "videos"
    if parts and parts[0].lower() == drive_alias:
        parts[0] = expected_tree
    elif not parts or parts[0].lower() != expected_tree:
        parts.insert(0, expected_tree)
    if len(parts) < 2:
        raise ImportRefused(f"incomplete {expected_tree} storage key: {value!r}")
    return PurePosixPath(*parts).as_posix()


def _inside(root: Path, relative_key: str) -> Path:
    root = root.resolve()
    destination = (root / Path(*PurePosixPath(relative_key).parts)).resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise ImportRefused(f"destination escapes dataset root: {relative_key!r}") from exc
    return destination


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_npz(path: Path) -> None:
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - training environments carry numpy
        raise ImportRefused("numpy is required to validate NPZ contracts") from exc
    try:
        with np.load(path, allow_pickle=False) as archive:
            if "sequence" not in archive.files:
                raise ImportRefused(f"{path} has no 'sequence' array")
            sequence = archive["sequence"]
    except ImportRefused:
        raise
    except Exception as exc:
        raise ImportRefused(f"cannot read NPZ {path}: {exc}") from exc
    if tuple(sequence.shape) != (60, 126):
        raise ImportRefused(f"{path} has shape {tuple(sequence.shape)}, expected (60, 126)")
    if str(sequence.dtype) != "float32":
        raise ImportRefused(f"{path} has dtype {sequence.dtype}, expected float32")
    if not bool(np.isfinite(sequence).all()):
        raise ImportRefused(f"{path} contains NaN or infinity")


def _index_files(root: Path, suffixes: tuple[str, ...]) -> tuple[dict[str, Path], dict[str, list[Path]]]:
    by_relative: dict[str, Path] = {}
    by_name: dict[str, list[Path]] = defaultdict(list)
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        relative = path.relative_to(root).as_posix()
        by_relative[relative] = path
        by_name[path.name].append(path)
    return by_relative, by_name


def _resolve_source(
    *,
    source_root: Path,
    catalog_key: str,
    by_relative: Mapping[str, Path],
    by_name: Mapping[str, Sequence[Path]],
    expected_checksum: str,
) -> tuple[Path, bool]:
    parts = PurePosixPath(catalog_key).parts
    relative = PurePosixPath(*parts[1:]).as_posix()
    exact = by_relative.get(relative)
    if exact is not None:
        return exact, False
    candidates = list(by_name.get(PurePosixPath(catalog_key).name, ()))
    if len(candidates) > 1 and len(expected_checksum) == 64:
        candidates = [path for path in candidates if _sha256(path) == expected_checksum.lower()]
    if len(candidates) != 1:
        raise ImportRefused(
            f"cannot resolve {catalog_key!r}: found {len(candidates)} source files by basename"
        )
    try:
        candidates[0].resolve().relative_to(source_root.resolve())
    except ValueError as exc:
        raise ImportRefused(f"resolved source escapes {source_root}: {candidates[0]}") from exc
    return candidates[0], True


def _catalog_is_empty_or_equal(
    path: Path,
    fields: Sequence[str],
    rows: Sequence[Mapping[str, str]],
) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        existing = list(reader)
    if existing and (header != list(fields) or existing != list(rows)):
        raise ImportRefused(
            f"refusing to replace populated catalogue with different content: {path}"
        )
    return bool(existing and header == list(fields) and existing == list(rows))


def _write_csv_atomic(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".import.part")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise", restval="")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _copy_atomic(item: CopyItem) -> str:
    destination = item.destination
    if destination.exists():
        if destination.is_file() and _sha256(destination) == _sha256(item.source):
            return "unchanged"
        raise ImportRefused(f"refusing to overwrite different file: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".import.part")
    try:
        shutil.copy2(item.source, temporary)
        if _sha256(temporary) != _sha256(item.source):
            raise ImportRefused(f"checksum changed while copying {item.source}")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return "copied"


def _read_export(community_root: Path, kind: str) -> list[dict[str, str]]:
    filename, sheet = WORKBOOKS[kind]
    path = community_root / "Lookup list" / filename
    if not path.is_file():
        raise ImportRefused(f"missing workbook: {path}")
    return read_xlsx_rows(path, sheet)


def build_plan(
    community_root: Path,
    dataset_root: Path,
    *,
    tenant_id: str,
    include_videos: bool,
) -> ImportPlan:
    labels_raw = _read_export(community_root, "labels")
    samples_raw = _read_export(community_root, "samples")
    videos_raw = _read_export(community_root, "videos")
    _require_columns(labels_raw, ("class_uid", "folder_name", "deleted_at"), "Labels")
    _require_columns(
        samples_raw,
        ("sample_uid", "class_uid", "file_path", "storage_key", "checksum", "deleted_at"),
        "Samples",
    )
    _require_columns(
        videos_raw,
        ("upload_uid", "local_path", "storage_key", "deleted_at"),
        "Videos",
    )

    labels_active = [row for row in labels_raw if not str(row.get("deleted_at") or "").strip()]
    samples_active = [row for row in samples_raw if not str(row.get("deleted_at") or "").strip()]
    videos_active = [row for row in videos_raw if not str(row.get("deleted_at") or "").strip()]
    _require_unique(labels_active, "class_uid", "Labels")
    _require_unique(samples_active, "sample_uid", "Samples")
    _require_unique(videos_active, "upload_uid", "Videos")
    known_classes = {str(row["class_uid"]).strip() for row in labels_active}
    unknown_classes = sorted({
        str(row.get("class_uid") or "").strip()
        for row in samples_active
        if str(row.get("class_uid") or "").strip() not in known_classes
    })
    if unknown_classes:
        raise ImportRefused(
            f"Samples reference classes absent from Labels: {', '.join(unknown_classes[:5])}"
        )

    plan = ImportPlan(
        labels=[_project(row, LABEL_FIELDS, tenant_id) for row in labels_active],
        samples=[_project(row, SAMPLE_FIELDS, tenant_id) for row in samples_active],
        videos=[_project(row, RAW_UPLOAD_FIELDS, tenant_id) for row in videos_active],
    )

    sample_root = community_root / "Samples"
    sample_relative, samples_by_name = _index_files(sample_root, (".npz",))
    referenced_sources: set[Path] = set()
    checksum_cache: dict[Path, str] = {}
    for source_row, output_row in zip(samples_active, plan.samples):
        file_key = _normalise_storage_key(
            str(source_row.get("file_path") or source_row.get("storage_key") or ""),
            "features",
        )
        storage_key = _normalise_storage_key(
            str(source_row.get("storage_key") or source_row.get("file_path") or ""),
            "features",
        )
        if file_key != storage_key:
            raise ImportRefused(
                f"sample {output_row['sample_uid']} has different file_path/storage_key"
            )
        output_row["file_path"] = file_key
        output_row["storage_key"] = file_key
        expected_checksum = output_row.get("checksum", "").lower()
        source, relocated = _resolve_source(
            source_root=sample_root,
            catalog_key=file_key,
            by_relative=sample_relative,
            by_name=samples_by_name,
            expected_checksum=expected_checksum,
        )
        referenced_sources.add(source.resolve())
        _validate_npz(source)
        if len(expected_checksum) == 64:
            checksum_cache.setdefault(source, _sha256(source))
            if checksum_cache[source] != expected_checksum:
                raise ImportRefused(
                    f"SHA-256 mismatch for sample {output_row['sample_uid']}: {source}"
                )
        destination = _inside(dataset_root, file_key)
        plan.copies.append(CopyItem(source, destination, file_key, relocated))
        if relocated:
            plan.relocated_samples.append({
                "sample_uid": output_row["sample_uid"],
                "catalog_key": file_key,
                "source": source.relative_to(sample_root).as_posix(),
            })

    all_sample_files = set(path.resolve() for path in sample_relative.values())
    unreferenced = sorted(all_sample_files - referenced_sources)
    selected_hashes: set[str] = set()
    for source in referenced_sources:
        selected_hashes.add(checksum_cache.get(source) or _sha256(source))
    for path in unreferenced:
        relative = path.relative_to(sample_root.resolve()).as_posix()
        plan.unreferenced_samples.append(relative)
        if _sha256(path) in selected_hashes:
            plan.duplicate_unreferenced_samples.append(relative)
        else:
            plan.unique_unreferenced_samples.append(relative)

    if include_videos:
        video_root = community_root / "Videos"
        video_relative, videos_by_name = _index_files(video_root, (".mp4", ".mov", ".avi"))
        for source_row, output_row in zip(videos_active, plan.videos):
            local_key = _normalise_storage_key(
                str(source_row.get("local_path") or source_row.get("storage_key") or ""),
                "raw_videos",
            )
            storage_key = _normalise_storage_key(
                str(source_row.get("storage_key") or source_row.get("local_path") or ""),
                "raw_videos",
            )
            if local_key != storage_key:
                raise ImportRefused(
                    f"video {output_row['upload_uid']} has different local_path/storage_key"
                )
            output_row["local_path"] = local_key
            output_row["storage_key"] = local_key
            source, relocated = _resolve_source(
                source_root=video_root,
                catalog_key=local_key,
                by_relative=video_relative,
                by_name=videos_by_name,
                expected_checksum="",
            )
            destination = _inside(dataset_root, local_key)
            plan.copies.append(CopyItem(source, destination, local_key, relocated))
            if relocated:
                plan.warnings.append(
                    f"video source relocated: {source.relative_to(video_root).as_posix()} -> {local_key}"
                )
    else:
        plan.videos = []

    if plan.unique_unreferenced_samples:
        plan.warnings.append(
            f"{len(plan.unique_unreferenced_samples)} unreferenced NPZ file(s) have unique content"
        )
    if plan.duplicate_unreferenced_samples:
        plan.warnings.append(
            f"{len(plan.duplicate_unreferenced_samples)} unreferenced NPZ file(s) duplicate catalogued content"
        )
    return plan


def _summary(plan: ImportPlan, *, applied: bool, copied: int = 0, unchanged: int = 0) -> dict:
    review_status = Counter(row.get("review_status") or "(blank)" for row in plan.samples)
    quality_status = Counter(row.get("quality_status") or "(blank)" for row in plan.samples)
    return {
        "mode": "apply" if applied else "dry-run",
        "catalogues": {
            "labels": len(plan.labels),
            "samples": len(plan.samples),
            "videos": len(plan.videos),
        },
        "sample_status": {
            "review": dict(sorted(review_status.items())),
            "quality": dict(sorted(quality_status.items())),
        },
        "files": {
            "planned": len(plan.copies),
            "copied": copied,
            "unchanged": unchanged,
            "relocated_samples": len(plan.relocated_samples),
            "unreferenced": len(plan.unreferenced_samples),
            "unreferenced_duplicates": len(plan.duplicate_unreferenced_samples),
            "unreferenced_unique": len(plan.unique_unreferenced_samples),
        },
        "relocated_sample_examples": plan.relocated_samples[:10],
        "unreferenced_samples": plan.unreferenced_samples,
        "warnings": plan.warnings,
    }


def apply_plan(plan: ImportPlan, dataset_root: Path) -> tuple[int, int]:
    catalogues = [
        (dataset_root / "labels.csv", LABEL_FIELDS, plan.labels),
        (dataset_root / "samples.csv", SAMPLE_FIELDS, plan.samples),
    ]
    if plan.videos:
        catalogues.append(
            (dataset_root / "raw_videos" / "uploads.csv", RAW_UPLOAD_FIELDS, plan.videos)
        )
    catalog_unchanged = {
        path: _catalog_is_empty_or_equal(path, fields, rows)
        for path, fields, rows in catalogues
    }

    copied = unchanged = 0
    for item in plan.copies:
        result = _copy_atomic(item)
        if result == "copied":
            copied += 1
        else:
            unchanged += 1
    for path, fields, rows in catalogues:
        if not catalog_unchanged[path]:
            _write_csv_atomic(path, fields, rows)
    return copied, unchanged


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("community_root", type=Path, help="Downloaded Community folder")
    parser.add_argument(
        "--dataset-root", type=Path, default=repo_root / "dataset",
        help="Local dataset directory (default: repository dataset/)",
    )
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument(
        "--include-videos", action="store_true",
        help="Also import Videos and raw_videos/uploads.csv (not needed for training)",
    )
    parser.add_argument("--apply", action="store_true", help="Copy files and write CSVs")
    parser.add_argument("--report", type=Path, help="Optional JSON report path")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    # Windows may inherit a legacy console code page even when paths and labels
    # are Unicode.  Keep human-readable Vietnamese output from turning a
    # successful validation into a late UnicodeEncodeError.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = parse_args(argv)
    community_root = args.community_root.resolve()
    dataset_root = args.dataset_root.resolve()
    try:
        if not community_root.is_dir():
            raise ImportRefused(f"Community root does not exist: {community_root}")
        if not args.tenant_id.strip() or any(ch in args.tenant_id for ch in "/\\."):
            raise ImportRefused(f"invalid tenant id: {args.tenant_id!r}")
        plan = build_plan(
            community_root,
            dataset_root,
            tenant_id=args.tenant_id.strip(),
            include_videos=bool(args.include_videos),
        )
        copied = unchanged = 0
        if args.apply:
            copied, unchanged = apply_plan(plan, dataset_root)
        report = _summary(
            plan, applied=bool(args.apply), copied=copied, unchanged=unchanged
        )
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        print(rendered)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(rendered + "\n", encoding="utf-8")
        return 0
    except ImportRefused as exc:
        print(f"[REFUSED] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
