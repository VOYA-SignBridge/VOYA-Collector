from __future__ import annotations

import csv
import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from filelock import FileLock

from app.config import settings
from app.dataset_manager import (
    ClassMetadata,
    LABEL_FIELDS,
    MASTER_LABELS,
    DATASET_ROOT,
    load_labels,
    regenerate_label_indexes,
    slugify,
    normalize_dialect,
    parse_bool,
)
from app.dataset_samples import SAMPLE_FIELDS, SAMPLES_CSV, list_samples
from app.logging_utils import get_logger as get_structured_logger, OperationStatus, OperationType
from app.processing.utils import atomic_write_json
from app.raw_uploads import RAW_UPLOAD_FIELDS, RAW_UPLOADS_CSV, list_raw_uploads
from app.storage.artifact_store import (
    _cloudinary_upload_bytes,
    build_raw_video_cloudinary_public_id,
    delete_cloudinary_asset,
)
from app.storage.minio_client import delete_file as delete_minio_file, upload_file
from app.storage.metadata_db import (
    delete_class as db_delete_class,
    delete_raw_upload as db_delete_raw_upload,
    delete_raw_uploads_by_class as db_delete_raw_uploads_by_class,
    delete_sample as db_delete_sample,
    delete_samples_by_class as db_delete_samples_by_class,
    ensure_tables,
    upsert_class as db_upsert_class,
    upsert_raw_upload as db_upsert_raw_upload,
    upsert_sample as db_upsert_sample,
)

logger = logging.getLogger(__name__)
slog = get_structured_logger("catalog.sync")
CATALOG_LOCK = DATASET_ROOT / ".catalog_sync.lock"


class CatalogSyncError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400, error_code: str = "CATALOG_SYNC_FAILED"):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


@dataclass
class ClassChange:
    old_meta: ClassMetadata
    new_meta: ClassMetadata
    old_row: Dict[str, Any]
    new_row: Dict[str, Any]
    sample_rows_before: List[Dict[str, Any]]
    sample_rows_after: List[Dict[str, Any]]
    raw_rows_before: List[Dict[str, Any]]
    raw_rows_after: List[Dict[str, Any]]
    old_feature_dir: Path
    old_raw_dir: Path
    backup_root: Path
    backup_feature_dir: Optional[Path]
    backup_raw_dir: Optional[Path]


@dataclass
class RemoteReplay:
    uploaded_minio_keys: List[str]
    uploaded_cloudinary_public_ids: List[str]
    deleted_minio_items: List[Tuple[str, Path]]
    deleted_cloudinary_items: List[Tuple[str, Path]]


@dataclass
class SampleChange:
    old_row: Dict[str, Any]
    new_row: Dict[str, Any]
    backup_file: Optional[Path]
    backup_json: Optional[Path]



def _catalog_lock() -> FileLock:
    CATALOG_LOCK.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(str(CATALOG_LOCK))


def _now_str() -> str:
    from datetime import datetime

    return datetime.utcnow().isoformat() + "Z"


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path) + ".lock")
    with lock:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(fieldnames))
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in fieldnames})
            f.flush()
            os.fsync(f.fileno())


def _relative_to_dataset(path: Path) -> Optional[Path]:
    try:
        return path.resolve().relative_to(Path(DATASET_ROOT).resolve())
    except Exception:
        return None


def _backup_tree(source: Path, snapshot_root: Path) -> Optional[Path]:
    if not source.exists():
        return None
    relative = _relative_to_dataset(source)
    if relative is None:
        return None
    backup_path = snapshot_root / relative
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if backup_path.exists():
        shutil.rmtree(backup_path)
    shutil.copytree(source, backup_path)
    return backup_path


def _restore_tree(backup_path: Optional[Path], target_path: Path) -> None:
    if backup_path is None or not backup_path.exists():
        return
    if target_path.exists():
        shutil.rmtree(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(backup_path, target_path)


def _remove_tree(target_path: Path) -> None:
    if target_path.exists():
        shutil.rmtree(target_path)


def _replace_prefix(value: Any, old_prefix: str, new_prefix: str) -> Any:
    if not isinstance(value, str) or not value:
        return value
    text = value
    if text.startswith(old_prefix):
        return new_prefix + text[len(old_prefix) :]
    return value


def _resolve_sample_file_path(row: Dict[str, Any]) -> Optional[Path]:
    file_path = row.get("file_path") or ""
    if not file_path:
        return None
    try:
        return Path(file_path)
    except Exception:
        return None


def _backup_sample_path(sample_row: Dict[str, Any], snapshot_root: Path) -> Optional[Path]:
    sample_file = _resolve_sample_file_path(sample_row)
    if sample_file is None:
        return None
    relative = _relative_to_dataset(sample_file)
    if relative is None:
        return None
    return snapshot_root / relative


def _backup_raw_path(raw_row: Dict[str, Any], snapshot_root: Path) -> Optional[Path]:
    local_path_text = raw_row.get("local_path") or raw_row.get("storage_url") or ""
    if not local_path_text:
        return None
    try:
        raw_path = Path(local_path_text)
    except Exception:
        return None
    relative = _relative_to_dataset(raw_path)
    if relative is None:
        return None
    return snapshot_root / relative


def _project_sample_row(row: Dict[str, Any], fieldnames: Sequence[str]) -> Dict[str, Any]:
    return {field: row.get(field, "") for field in fieldnames}


def _project_raw_row(row: Dict[str, Any], fieldnames: Sequence[str]) -> Dict[str, Any]:
    return {field: row.get(field, "") for field in fieldnames}


def _build_class_meta_from_row(row: Dict[str, Any]) -> ClassMetadata:
    return ClassMetadata(
        class_uid=row["class_uid"],
        class_idx=int(row["class_idx"]) if str(row.get("class_idx") or "").strip() else None,
        slug=row.get("slug") or slugify(row.get("label_original") or "label"),
        label_original=row.get("label_original") or "",
        language=row.get("language") or "",
        dialect=row.get("dialect") or "",
        is_common_global=parse_bool(row.get("is_common_global")),
        is_common_language=parse_bool(row.get("is_common_language")),
        folder_override=row.get("folder_name") or None,
    )


def _find_class_row_by_ref(rows: Sequence[Dict[str, Any]], class_ref: int | str) -> Optional[Dict[str, Any]]:
    ref = str(class_ref).strip()
    if not ref:
        return None

    if ref.lstrip("-").isdigit():
        for row in rows:
            if str(row.get("class_idx") or "") == ref:
                return row

    for row in rows:
        if row.get("class_uid") == ref:
            return row

    return None


def _build_updated_class_meta(row: Dict[str, Any], payload: Dict[str, Any]) -> ClassMetadata:
    label_original = (payload.get("label_original") or payload.get("label") or row.get("label_original") or "").strip()
    language = (payload.get("language") or row.get("language") or "").strip().lower()
    dialect_input = payload.get("dialect") or row.get("dialect") or ""
    is_common_global = bool(payload.get("is_common_global", parse_bool(row.get("is_common_global"))))
    is_common_language = bool(payload.get("is_common_language", parse_bool(row.get("is_common_language"))))

    if is_common_global:
        language = "global"
        dialect = "global"
        is_common_language = False
    elif is_common_language or dialect_input == "common":
        dialect = "common"
        is_common_language = True
    else:
        dialect = normalize_dialect(str(dialect_input)) or str(dialect_input).strip().lower()

    slug = slugify(label_original)
    class_uid = row["class_uid"]
    class_idx = int(row["class_idx"]) if str(row.get("class_idx") or "").strip() else None
    folder_override = f"class_{slug}_{class_uid[:8]}"
    return ClassMetadata(
        class_uid=class_uid,
        class_idx=class_idx,
        slug=slug,
        label_original=label_original,
        language=language,
        dialect=dialect,
        is_common_global=is_common_global,
        is_common_language=is_common_language and not is_common_global,
        folder_override=folder_override,
    )


def _sample_new_path(old_path: Path, old_root: Path, new_root: Path) -> Path:
    try:
        relative = old_path.resolve().relative_to(old_root.resolve())
        return new_root / relative
    except Exception:
        return new_root / old_path.name


def _raw_new_path(old_path: Path, old_root: Path, new_root: Path) -> Path:
    try:
        relative = old_path.resolve().relative_to(old_root.resolve())
        return new_root / relative
    except Exception:
        return new_root / old_path.name


def _dataset_storage_key(local_path: Path) -> Optional[str]:
    relative = _relative_to_dataset(local_path)
    if relative is None:
        return None
    return relative.as_posix()


def _infer_upload_uid(raw_row: Dict[str, Any]) -> str:
    for candidate in (
        raw_row.get("upload_uid"),
        raw_row.get("storage_key"),
        raw_row.get("local_path"),
    ):
        if not candidate:
            continue
        stem = Path(str(candidate)).stem
        if "_" in stem:
            return stem.rsplit("_", 1)[-1]
    return ""


def _minio_storage_url(storage_key: Optional[str], fallback_path: str) -> str:
    if storage_key and bool(getattr(settings, "use_minio", False)):
        return f"s3://{settings.minio_bucket}/{storage_key}"
    return fallback_path


def _update_sample_metadata_json(sample_path: Path, new_meta: ClassMetadata) -> None:
    json_path = sample_path.with_suffix(".json")
    if not json_path.exists():
        return
    try:
        existing = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        existing = {}
    existing.update(
        {
            "class_uid": new_meta.class_uid,
            "slug": new_meta.slug,
            "label_original": new_meta.label_original,
            "language": new_meta.language,
            "dialect": new_meta.dialect,
            "folder_name": new_meta.folder_name(),
        }
    )
    atomic_write_json(json_path, existing, indent=2)


def _update_class_metadata_json(target_dir: Path, new_meta: ClassMetadata) -> None:
    metadata_path = target_dir / "metadata.json"
    if not metadata_path.exists():
        return
    atomic_write_json(
        metadata_path,
        {
            "class_uid": new_meta.class_uid,
            "class_idx": new_meta.class_idx,
            "slug": new_meta.slug,
            "label_original": new_meta.label_original,
            "language": new_meta.language,
            "dialect": new_meta.dialect,
            "is_common_global": new_meta.is_common_global,
            "is_common_language": new_meta.is_common_language,
            "folder_name": new_meta.folder_name(),
        },
        indent=2,
    )


def _sync_db_class(row: Dict[str, Any]) -> None:
    db_upsert_class(row)


def _sync_db_samples(rows: Sequence[Dict[str, Any]]) -> None:
    for row in rows:
        db_upsert_sample(row)


def _sync_db_raw_uploads(rows: Sequence[Dict[str, Any]]) -> None:
    for row in rows:
        db_upsert_raw_upload(row)


def _delete_remote_assets(
    sample_rows: Sequence[Dict[str, Any]],
    raw_rows: Sequence[Dict[str, Any]],
    *,
    sample_backup_root: Path,
    raw_backup_root: Path,
    sample_old_root: Path,
    raw_old_root: Path,
) -> RemoteReplay:
    replay = RemoteReplay(uploaded_minio_keys=[], uploaded_cloudinary_public_ids=[], deleted_minio_items=[], deleted_cloudinary_items=[])

    for sample_row in sample_rows:
        storage_key = (sample_row.get("storage_key") or "").strip()
        if storage_key and bool(getattr(settings, "use_minio", False)):
            local_path = _resolve_sample_file_path(sample_row)
            if local_path is None:
                continue
            if not delete_minio_file(storage_key):
                raise CatalogSyncError(f"Failed to delete MinIO object {storage_key}", status_code=500, error_code="MINIO_DELETE_FAILED")
            replay.deleted_minio_items.append((storage_key, sample_backup_root / _relative_to_dataset(local_path)))

    for raw_row in raw_rows:
        public_id = (raw_row.get("cloudinary_public_id") or "").strip()
        if public_id:
            local_path_text = raw_row.get("local_path") or ""
            if local_path_text:
                local_path = Path(local_path_text)
                backup_path = raw_backup_root / _relative_to_dataset(local_path)
            else:
                backup_path = None
            if not delete_cloudinary_asset(public_id, resource_type="video"):
                raise CatalogSyncError(f"Failed to delete Cloudinary asset {public_id}", status_code=500, error_code="CLOUDINARY_DELETE_FAILED")
            if backup_path is not None:
                replay.deleted_cloudinary_items.append((public_id, backup_path))

    return replay


def _reupload_deleted_assets(
    replay: RemoteReplay,
    *,
    sample_rows_before: Sequence[Dict[str, Any]],
    raw_rows_before: Sequence[Dict[str, Any]],
) -> None:
    sample_row_by_key = {row.get("storage_key"): row for row in sample_rows_before if row.get("storage_key")}
    raw_row_by_public_id = {
        row.get("cloudinary_public_id"): row for row in raw_rows_before if row.get("cloudinary_public_id")
    }

    for storage_key, backup_path in replay.deleted_minio_items:
        source_row = sample_row_by_key.get(storage_key)
        if source_row and backup_path.exists():
            upload_file(str(backup_path), storage_key)

    for public_id, backup_path in replay.deleted_cloudinary_items:
        source_row = raw_row_by_public_id.get(public_id)
        if source_row and backup_path.exists():
            try:
                file_bytes = backup_path.read_bytes()
                from app.storage.artifact_store import _guess_mime

                result = _cloudinary_upload_bytes(
                    file_bytes,
                    original_filename=source_row.get("original_filename") or backup_path.name,
                    public_id=public_id,
                    resource_type="video",
                )
                if result:
                    logger.info("[CLOUDINARY] Restored deleted asset public_id=%s", public_id)
            except Exception as exc:
                logger.error("[CLOUDINARY] Failed to restore deleted asset public_id=%s: %s", public_id, exc)


def _delete_uploaded_new_assets(replay: RemoteReplay) -> None:
    for storage_key in replay.uploaded_minio_keys:
        delete_minio_file(storage_key)
    for public_id in replay.uploaded_cloudinary_public_ids:
        delete_cloudinary_asset(public_id, resource_type="video")


def sync_update_class(class_idx: int | str, payload: Dict[str, Any]) -> Dict[str, Any]:
    ensure_tables()
    op_id = f"class_update_{class_idx}"
    slog.start_operation(op_id)

    with _catalog_lock():
        rows = load_labels()
        target_row = _find_class_row_by_ref(rows, class_idx)

        if target_row is None:
            slog.log_operation(
                OperationType.CLASS_UPDATE,
                OperationStatus.FAILURE,
                {"class_idx": class_idx, "reason": "not_found"},
                duration_ms=slog.end_operation(op_id),
                error_code="CLASS_NOT_FOUND",
            )
            raise CatalogSyncError(f"Class {class_idx} not found", status_code=404, error_code="CLASS_NOT_FOUND")

        old_meta = _build_class_meta_from_row(target_row)
        new_meta = _build_updated_class_meta(target_row, payload)

        existing = None
        for row in rows:
            if row.get("language") == new_meta.language and row.get("dialect") == new_meta.dialect and row.get("slug") == new_meta.slug:
                existing = row
                break
        if existing and existing.get("class_uid") != old_meta.class_uid:
            slog.log_operation(
                OperationType.CLASS_UPDATE,
                OperationStatus.FAILURE,
                {
                    "class_idx": class_idx,
                    "class_uid": old_meta.class_uid,
                    "new_slug": new_meta.slug,
                    "reason": "conflict",
                },
                duration_ms=slog.end_operation(op_id),
                error_code="CLASS_CONFLICT",
            )
            raise CatalogSyncError(
                "A class with the same label/language/dialect already exists",
                status_code=409,
                error_code="CLASS_CONFLICT",
            )

        if (
            old_meta.slug == new_meta.slug
            and old_meta.label_original == new_meta.label_original
            and old_meta.language == new_meta.language
            and old_meta.dialect == new_meta.dialect
            and old_meta.is_common_global == new_meta.is_common_global
            and old_meta.is_common_language == new_meta.is_common_language
        ):
            slog.log_operation(
                OperationType.CLASS_UPDATE,
                OperationStatus.SUCCESS,
                {
                    "class_idx": class_idx,
                    "class_uid": old_meta.class_uid,
                    "changed": False,
                },
                duration_ms=slog.end_operation(op_id),
            )
            return {"changed": False, "class_uid": old_meta.class_uid, "class_idx": old_meta.class_idx}

        snapshot_root = Path(tempfile.mkdtemp(prefix="catalog_sync_"))
        backup_feature_dir = _backup_tree(old_meta.hierarchy_path(), snapshot_root)
        old_raw_dir = Path(settings.dataset_root) / "raw_videos" / old_meta.language / old_meta.dialect / old_meta.folder_name()
        backup_raw_dir = _backup_tree(old_raw_dir, snapshot_root)

        all_samples_before = list_samples()
        all_raw_before = list_raw_uploads()
        sample_rows_before = [row for row in all_samples_before if row.get("class_uid") == old_meta.class_uid]
        raw_rows_before = [row for row in all_raw_before if row.get("class_uid") == old_meta.class_uid]

        updated_class_row = target_row
        # build updated label rows
        updated_label_rows: List[Dict[str, Any]] = []
        for row in rows:
            if row.get("class_uid") != old_meta.class_uid:
                updated_label_rows.append(row)
                continue
            new_row = dict(row)
            new_row.update(
                {
                    "slug": new_meta.slug,
                    "label_original": new_meta.label_original,
                    "language": new_meta.language,
                    "dialect": new_meta.dialect,
                    "is_common_global": str(int(new_meta.is_common_global)),
                    "is_common_language": str(int(new_meta.is_common_language)),
                    "folder_name": new_meta.folder_name(),
                    "migrated_at": _now_str(),
                }
            )
            updated_label_rows.append(new_row)
            updated_class_row = new_row

        old_feature_dir = old_meta.hierarchy_path()
        new_feature_dir = new_meta.hierarchy_path()
        old_raw_dir = Path(settings.dataset_root) / "raw_videos" / old_meta.language / old_meta.dialect / old_meta.folder_name()
        new_raw_dir = Path(settings.dataset_root) / "raw_videos" / new_meta.language / new_meta.dialect / new_meta.folder_name()
        replay = RemoteReplay(uploaded_minio_keys=[], uploaded_cloudinary_public_ids=[], deleted_minio_items=[], deleted_cloudinary_items=[])

        try:
            if old_feature_dir.exists() and old_feature_dir != new_feature_dir:
                new_feature_dir.parent.mkdir(parents=True, exist_ok=True)
                if new_feature_dir.exists():
                    raise CatalogSyncError(f"Target feature folder already exists: {new_feature_dir}", status_code=409, error_code="CLASS_PATH_CONFLICT")
                shutil.move(str(old_feature_dir), str(new_feature_dir))
            elif not old_feature_dir.exists():
                new_feature_dir.mkdir(parents=True, exist_ok=True)

            if old_raw_dir.exists() and old_raw_dir != new_raw_dir:
                new_raw_dir.parent.mkdir(parents=True, exist_ok=True)
                if new_raw_dir.exists():
                    raise CatalogSyncError(f"Target raw folder already exists: {new_raw_dir}", status_code=409, error_code="CLASS_PATH_CONFLICT")
                shutil.move(str(old_raw_dir), str(new_raw_dir))
            elif not old_raw_dir.exists():
                new_raw_dir.mkdir(parents=True, exist_ok=True)

            _update_class_metadata_json(new_feature_dir, new_meta)

            sample_rows_after = []
            for sample_row in all_samples_before:
                if sample_row.get("class_uid") != old_meta.class_uid:
                    sample_rows_after.append(sample_row)
                    continue
                new_sample_row = dict(sample_row)
                old_file_path = _resolve_sample_file_path(sample_row)
                new_file_path = old_file_path
                if old_file_path is not None:
                    new_file_path = _sample_new_path(old_file_path, old_feature_dir, new_feature_dir)
                    new_sample_row["file_path"] = str(new_file_path)
                    new_sample_row["storage_key"] = _dataset_storage_key(new_file_path) or new_sample_row.get("storage_key", "")
                    new_sample_row["storage_url"] = _minio_storage_url(new_sample_row.get("storage_key"), str(new_file_path))
                    _update_sample_metadata_json(new_file_path, new_meta)
                new_sample_row.update(
                    {
                        "class_uid": new_meta.class_uid,
                        "slug": new_meta.slug,
                        "label_original": new_meta.label_original,
                        "language": new_meta.language,
                        "dialect": new_meta.dialect,
                    }
                )
                sample_rows_after.append(new_sample_row)

                if bool(getattr(settings, "use_minio", False)) and new_sample_row.get("storage_key") and new_file_path and new_file_path.exists():
                    storage_key = str(new_sample_row["storage_key"])
                    storage_result = upload_file(str(new_file_path), storage_key)
                    if not storage_result:
                        raise CatalogSyncError(f"Failed to mirror sample to MinIO: {storage_key}", status_code=500, error_code="MINIO_UPLOAD_FAILED")
                    replay.uploaded_minio_keys.append(storage_key)
                    new_sample_row["storage_url"] = storage_result

            raw_rows_after = []
            for raw_row in all_raw_before:
                if raw_row.get("class_uid") != old_meta.class_uid:
                    raw_rows_after.append(raw_row)
                    continue
                new_raw_row = dict(raw_row)
                old_local_path = Path(raw_row.get("local_path") or raw_row.get("storage_url") or "") if (raw_row.get("local_path") or raw_row.get("storage_url")) else None
                new_local_path = old_local_path
                if old_local_path is not None:
                    new_local_path = _raw_new_path(old_local_path, old_raw_dir, new_raw_dir)
                    new_raw_row["local_path"] = str(new_local_path)
                    new_raw_row["storage_key"] = _dataset_storage_key(new_local_path) or new_raw_row.get("storage_key", "")
                    new_raw_row["storage_url"] = str(new_local_path)
                new_raw_row.update(
                    {
                        "class_uid": new_meta.class_uid,
                        "slug": new_meta.slug,
                        "label_original": new_meta.label_original,
                        "language": new_meta.language,
                        "dialect": new_meta.dialect,
                    }
                )

                if (new_raw_row.get("cloudinary_public_id") or "").strip() and new_local_path is not None and new_local_path.exists():
                    old_public_id = new_raw_row["cloudinary_public_id"]
                    new_public_id = build_raw_video_cloudinary_public_id(
                        new_meta,
                        raw_row.get("session_id") or "",
                        raw_row.get("original_filename") or Path(str(new_local_path)).name,
                        _infer_upload_uid(raw_row) or old_meta.class_uid[:8],
                    )
                    try:
                        file_bytes = Path(new_local_path).read_bytes()
                        result = _cloudinary_upload_bytes(
                            file_bytes,
                            original_filename=raw_row.get("original_filename") or Path(str(new_local_path)).name,
                            public_id=new_public_id,
                            resource_type="video",
                        )
                        if result:
                            new_raw_row["cloudinary_public_id"] = new_public_id
                            new_raw_row["cloudinary_url"] = str(result.get("secure_url") or result.get("url") or "")
                            replay.uploaded_cloudinary_public_ids.append(new_public_id)
                    except Exception as exc:
                        raise CatalogSyncError(f"Failed to mirror raw upload to Cloudinary: {exc}", status_code=500, error_code="CLOUDINARY_UPLOAD_FAILED") from exc

                raw_rows_after.append(new_raw_row)

            # Write the local CSV mirrors only after remote uploads succeed.
            _write_csv(MASTER_LABELS, LABEL_FIELDS, updated_label_rows)
            regenerate_label_indexes()
            _write_csv(SAMPLES_CSV, SAMPLE_FIELDS, sample_rows_after)
            _write_csv(RAW_UPLOADS_CSV, RAW_UPLOAD_FIELDS, raw_rows_after)

            # Mirror to Postgres.
            _sync_db_class(updated_class_row)
            _sync_db_samples([row for row in sample_rows_after if row.get("class_uid") == new_meta.class_uid])
            _sync_db_raw_uploads([row for row in raw_rows_after if row.get("class_uid") == new_meta.class_uid])

            for sample_row in sample_rows_before:
                storage_key = (sample_row.get("storage_key") or "").strip()
                if storage_key and bool(getattr(settings, "use_minio", False)):
                    backup_file = _backup_sample_path(sample_row, snapshot_root)
                    if backup_file is None:
                        raise CatalogSyncError(f"Missing backup for sample {sample_row.get('sample_uid')}", status_code=500, error_code="ROLLBACK_BACKUP_MISSING")
                    if not delete_minio_file(storage_key):
                        raise CatalogSyncError(f"Failed to delete MinIO object {storage_key}", status_code=500, error_code="MINIO_DELETE_FAILED")
                    replay.deleted_minio_items.append((storage_key, backup_file))

            for raw_row in raw_rows_before:
                public_id = (raw_row.get("cloudinary_public_id") or "").strip()
                if public_id:
                    backup_file = _backup_raw_path(raw_row, snapshot_root)
                    if backup_file is None:
                        raise CatalogSyncError(f"Missing backup for raw upload {raw_row.get('upload_uid')}", status_code=500, error_code="ROLLBACK_BACKUP_MISSING")
                    if not delete_cloudinary_asset(public_id, resource_type="video"):
                        raise CatalogSyncError(f"Failed to delete Cloudinary asset {public_id}", status_code=500, error_code="CLOUDINARY_DELETE_FAILED")
                    replay.deleted_cloudinary_items.append((public_id, backup_file))

            slog.log_operation(
                OperationType.CLASS_UPDATE,
                OperationStatus.SUCCESS,
                {
                    "class_idx": class_idx,
                    "class_uid": new_meta.class_uid,
                    "slug": new_meta.slug,
                    "sample_count": len(sample_rows_before),
                    "raw_upload_count": len(raw_rows_before),
                },
                duration_ms=slog.end_operation(op_id),
            )
            return {
                "changed": True,
                "class_uid": new_meta.class_uid,
                "class_idx": new_meta.class_idx,
                "label_original": new_meta.label_original,
                "slug": new_meta.slug,
                "language": new_meta.language,
                "dialect": new_meta.dialect,
            }
        except Exception as exc:
            # Roll back the visible state first.
            try:
                _write_csv(MASTER_LABELS, LABEL_FIELDS, rows)
                regenerate_label_indexes()
                _write_csv(SAMPLES_CSV, SAMPLE_FIELDS, all_samples_before)
                _write_csv(RAW_UPLOADS_CSV, RAW_UPLOAD_FIELDS, all_raw_before)
                _restore_tree(backup_feature_dir, old_feature_dir)
                _restore_tree(backup_raw_dir, old_raw_dir)
                db_upsert_class(target_row)
                _sync_db_samples(all_samples_before)
                _sync_db_raw_uploads(all_raw_before)
                _delete_uploaded_new_assets(replay)
                _reupload_deleted_assets(replay, sample_rows_before=all_samples_before, raw_rows_before=all_raw_before)
            except Exception as rollback_exc:
                logger.error("[CATALOG][ROLLBACK] Failed to restore class update for class_uid=%s: %s", old_meta.class_uid, rollback_exc)
            slog.log_operation(
                OperationType.CATALOG_ROLLBACK,
                OperationStatus.FAILURE,
                {"class_idx": class_idx, "class_uid": old_meta.class_uid, "error": str(exc)},
                duration_ms=slog.end_operation(op_id),
                error_code="CATALOG_ROLLBACK_FAILED",
                error_message=str(exc),
                log_level=logging.ERROR,
            )
            raise CatalogSyncError(str(exc), status_code=getattr(exc, "status_code", 500), error_code=getattr(exc, "error_code", "CATALOG_SYNC_FAILED")) from exc
        finally:
            shutil.rmtree(snapshot_root, ignore_errors=True)


def sync_delete_class(class_idx: int | str) -> Dict[str, Any]:
    ensure_tables()
    op_id = f"class_delete_{class_idx}"
    slog.start_operation(op_id)

    with _catalog_lock():
        rows = load_labels()
        target_row = _find_class_row_by_ref(rows, class_idx)

        if target_row is None:
            slog.log_operation(
                OperationType.CLASS_DELETE,
                OperationStatus.FAILURE,
                {"class_idx": class_idx, "reason": "not_found"},
                duration_ms=slog.end_operation(op_id),
                error_code="CLASS_NOT_FOUND",
            )
            raise CatalogSyncError(f"Class {class_idx} not found", status_code=404, error_code="CLASS_NOT_FOUND")

        old_meta = _build_class_meta_from_row(target_row)
        all_samples_before = list_samples()
        all_raw_before = list_raw_uploads()
        sample_rows_before = [row for row in all_samples_before if row.get("class_uid") == old_meta.class_uid]
        raw_rows_before = [row for row in all_raw_before if row.get("class_uid") == old_meta.class_uid]
        old_feature_dir = old_meta.hierarchy_path()
        old_raw_dir = Path(settings.dataset_root) / "raw_videos" / old_meta.language / old_meta.dialect / old_meta.folder_name()
        snapshot_root = Path(tempfile.mkdtemp(prefix="catalog_sync_"))
        backup_feature_dir = _backup_tree(old_feature_dir, snapshot_root)
        backup_raw_dir = _backup_tree(old_raw_dir, snapshot_root)
        replay = RemoteReplay(uploaded_minio_keys=[], uploaded_cloudinary_public_ids=[], deleted_minio_items=[], deleted_cloudinary_items=[])

        try:
            _remove_tree(old_feature_dir)
            _remove_tree(old_raw_dir)

            remaining_label_rows = [row for row in rows if row.get("class_uid") != old_meta.class_uid]
            remaining_sample_rows = [row for row in all_samples_before if row.get("class_uid") != old_meta.class_uid]
            remaining_raw_rows = [row for row in all_raw_before if row.get("class_uid") != old_meta.class_uid]

            _write_csv(MASTER_LABELS, LABEL_FIELDS, remaining_label_rows)
            regenerate_label_indexes()
            _write_csv(SAMPLES_CSV, SAMPLE_FIELDS, remaining_sample_rows)
            _write_csv(RAW_UPLOADS_CSV, RAW_UPLOAD_FIELDS, remaining_raw_rows)

            db_delete_class(old_meta.class_uid)
            db_delete_samples_by_class(old_meta.class_uid)
            db_delete_raw_uploads_by_class(old_meta.class_uid)

            for sample_row in sample_rows_before:
                storage_key = (sample_row.get("storage_key") or "").strip()
                if storage_key and bool(getattr(settings, "use_minio", False)):
                    backup_file = _backup_sample_path(sample_row, snapshot_root)
                    if backup_file is None:
                        raise CatalogSyncError(f"Missing backup for sample {sample_row.get('sample_uid')}", status_code=500, error_code="ROLLBACK_BACKUP_MISSING")
                    if not delete_minio_file(storage_key):
                        raise CatalogSyncError(f"Failed to delete MinIO object {storage_key}", status_code=500, error_code="MINIO_DELETE_FAILED")
                    replay.deleted_minio_items.append((storage_key, backup_file))

            for raw_row in raw_rows_before:
                public_id = (raw_row.get("cloudinary_public_id") or "").strip()
                if public_id:
                    backup_file = _backup_raw_path(raw_row, snapshot_root)
                    if backup_file is None:
                        raise CatalogSyncError(f"Missing backup for raw upload {raw_row.get('upload_uid')}", status_code=500, error_code="ROLLBACK_BACKUP_MISSING")
                    if not delete_cloudinary_asset(public_id, resource_type="video"):
                        raise CatalogSyncError(f"Failed to delete Cloudinary asset {public_id}", status_code=500, error_code="CLOUDINARY_DELETE_FAILED")
                    replay.deleted_cloudinary_items.append((public_id, backup_file))

            slog.log_operation(
                OperationType.CLASS_DELETE,
                OperationStatus.SUCCESS,
                {
                    "class_idx": class_idx,
                    "class_uid": old_meta.class_uid,
                    "sample_count": len(sample_rows_before),
                    "raw_upload_count": len(raw_rows_before),
                },
                duration_ms=slog.end_operation(op_id),
            )
            return {
                "deleted": True,
                "class_uid": old_meta.class_uid,
                "class_idx": old_meta.class_idx,
                "sample_count": len(sample_rows_before),
                "raw_upload_count": len(raw_rows_before),
            }
        except Exception as exc:
            try:
                _write_csv(MASTER_LABELS, LABEL_FIELDS, rows)
                regenerate_label_indexes()
                _write_csv(SAMPLES_CSV, SAMPLE_FIELDS, all_samples_before)
                _write_csv(RAW_UPLOADS_CSV, RAW_UPLOAD_FIELDS, all_raw_before)
                _restore_tree(backup_feature_dir, old_feature_dir)
                _restore_tree(backup_raw_dir, old_raw_dir)
                db_upsert_class(target_row)
                _sync_db_samples(all_samples_before)
                _sync_db_raw_uploads(all_raw_before)
                _reupload_deleted_assets(replay, sample_rows_before=all_samples_before, raw_rows_before=all_raw_before)
            except Exception as rollback_exc:
                logger.error("[CATALOG][ROLLBACK] Failed to restore class delete for class_uid=%s: %s", old_meta.class_uid, rollback_exc)
            slog.log_operation(
                OperationType.CATALOG_ROLLBACK,
                OperationStatus.FAILURE,
                {"class_idx": class_idx, "class_uid": old_meta.class_uid, "error": str(exc)},
                duration_ms=slog.end_operation(op_id),
                error_code="CATALOG_ROLLBACK_FAILED",
                error_message=str(exc),
                log_level=logging.ERROR,
            )
            raise CatalogSyncError(str(exc), status_code=getattr(exc, "status_code", 500), error_code=getattr(exc, "error_code", "CATALOG_SYNC_FAILED")) from exc
        finally:
            shutil.rmtree(snapshot_root, ignore_errors=True)


def sync_delete_sample(sample_uid: str) -> Dict[str, Any]:
    ensure_tables()
    op_id = f"sample_delete_{sample_uid}"
    slog.start_operation(op_id)

    with _catalog_lock():
        rows = list_samples()
        target_row = None
        for row in rows:
            if row.get("sample_uid") == sample_uid:
                target_row = row
                break

        if target_row is None:
            slog.log_operation(
                OperationType.SAMPLE_DELETE,
                OperationStatus.FAILURE,
                {"sample_uid": sample_uid, "reason": "not_found"},
                duration_ms=slog.end_operation(op_id),
                error_code="SAMPLE_NOT_FOUND",
            )
            raise CatalogSyncError(f"Sample {sample_uid} not found", status_code=404, error_code="SAMPLE_NOT_FOUND")

        backup_root = Path(tempfile.mkdtemp(prefix="catalog_sync_"))
        sample_file = _resolve_sample_file_path(target_row)
        backup_file = None
        backup_json = None
        if sample_file and sample_file.exists():
            relative = _relative_to_dataset(sample_file)
            if relative is not None:
                backup_file = backup_root / relative
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sample_file, backup_file)
            sample_json = sample_file.with_suffix(".json")
            if sample_json.exists() and relative is not None:
                backup_json = backup_root / relative.with_suffix(".json")
                backup_json.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sample_json, backup_json)

        try:
            if sample_file and sample_file.exists():
                sample_file.unlink()
            sample_json = sample_file.with_suffix(".json") if sample_file else None
            if sample_json and sample_json.exists():
                sample_json.unlink()

            remaining_rows = [row for row in rows if row.get("sample_uid") != sample_uid]
            _write_csv(SAMPLES_CSV, SAMPLE_FIELDS, remaining_rows)
            db_delete_sample(sample_uid)

            storage_key = (target_row.get("storage_key") or "").strip()
            if storage_key and bool(getattr(settings, "use_minio", False)):
                if not delete_minio_file(storage_key):
                    raise CatalogSyncError(f"Failed to delete MinIO object {storage_key}", status_code=500, error_code="MINIO_DELETE_FAILED")

            slog.log_operation(
                OperationType.SAMPLE_DELETE,
                OperationStatus.SUCCESS,
                {"sample_uid": sample_uid, "class_uid": target_row.get("class_uid")},
                duration_ms=slog.end_operation(op_id),
            )
            return {"deleted": True, "sample_uid": sample_uid}
        except Exception as exc:
            try:
                _write_csv(SAMPLES_CSV, SAMPLE_FIELDS, rows)
                db_upsert_sample(target_row)
                if backup_file and backup_file.exists() and sample_file:
                    sample_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_file, sample_file)
                if backup_json and backup_json.exists() and sample_file:
                    shutil.copy2(backup_json, sample_file.with_suffix(".json"))
            except Exception as rollback_exc:
                logger.error("[CATALOG][ROLLBACK] Failed to restore sample delete for sample_uid=%s: %s", sample_uid, rollback_exc)
            slog.log_operation(
                OperationType.CATALOG_ROLLBACK,
                OperationStatus.FAILURE,
                {"sample_uid": sample_uid, "error": str(exc)},
                duration_ms=slog.end_operation(op_id),
                error_code="CATALOG_ROLLBACK_FAILED",
                error_message=str(exc),
                log_level=logging.ERROR,
            )
            raise CatalogSyncError(str(exc), status_code=getattr(exc, "status_code", 500), error_code=getattr(exc, "error_code", "CATALOG_SYNC_FAILED")) from exc
        finally:
            shutil.rmtree(backup_root, ignore_errors=True)
