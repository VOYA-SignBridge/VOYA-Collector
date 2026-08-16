from __future__ import annotations

import csv
import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from filelock import FileLock

from app.config import settings
from app.dataset_manager import (
    ClassMetadata,
    LABEL_FIELDS,
    MASTER_LABELS,
    DATASET_ROOT,
    _load_all_labels_unscoped,
    load_labels,
    regenerate_label_indexes,
    slugify,
    normalize_dialect,
    normalize_region,
    parse_bool,
)
from app.dataset_samples import (
    SAMPLE_FIELDS,
    SAMPLES_CSV,
    _load_all_samples_unscoped,
    list_samples,
)
from app.logging_utils import get_logger as get_structured_logger, OperationStatus, OperationType
from app.processing.utils import atomic_write_json
from app.raw_uploads import RAW_UPLOAD_FIELDS, RAW_UPLOADS_CSV, list_raw_uploads
from app.tenancy import TENANT_COLUMN, normalize_tenant_id, tenant_id_of
from app.storage.gdrive_client import get_gdrive_client
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
    soft_delete_class as db_soft_delete_class,
    soft_delete_samples_by_class as db_soft_delete_samples_by_class,
    soft_delete_raw_uploads_by_class as db_soft_delete_raw_uploads_by_class,
    restore_class as db_restore_class,
    restore_samples_by_class as db_restore_samples_by_class,
    restore_raw_uploads_by_class as db_restore_raw_uploads_by_class,
    soft_delete_sample as db_soft_delete_sample,
    restore_sample as db_restore_sample,
    list_deleted_classes as db_list_deleted_classes,
    get_deleted_class as db_get_deleted_class,
    list_samples_by_class as db_list_samples_by_class,
    list_deleted_samples as db_list_deleted_samples,
    get_deleted_sample as db_get_deleted_sample,
)

logger = logging.getLogger(__name__)
slog = get_structured_logger("catalog.sync")
CATALOG_LOCK = DATASET_ROOT / ".catalog_sync.lock"


class CatalogSyncError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400, error_code: str = "CATALOG_SYNC_FAILED", logs: list | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.logs = logs or []


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


def _purge_raw_archive(sample_file: Optional[Path], sample_uid: str) -> None:
    """Delete a purged sample's raw recording along with its features file.

    Contract v3 stores the recording in a parallel tree, and a purge that only
    removed the features half would leave the landmarks — the actual record of a
    person signing — on disk after the sample was destroyed at the contributor's
    request. Purge is the hard-delete path; soft delete does not reach here and
    keeps both halves, which is what makes Trash restorable.
    """
    if sample_file is None:
        return
    try:
        from app.dataset_samples import raw_archive_path

        archived = raw_archive_path(sample_file)
        if archived.exists():
            archived.unlink()
            logger.info("[CATALOG] purged raw archive for %s", sample_uid)
    except Exception as exc:
        logger.warning("[CATALOG] raw archive purge failed for %s: %s", sample_uid, exc)


def _resolve_sample_file_path(row: Dict[str, Any]) -> Optional[Path]:
    file_path = row.get("file_path") or ""
    if not file_path:
        return None
    try:
        return Path(file_path)
    except Exception:
        return None


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
        # `hierarchy_path()` is derived from this. Dropping it makes every
        # class-move, rename and trash/restore in this module read and write the
        # bootstrap tenant's directory tree regardless of who owns the class.
        tenant_id=tenant_id_of(row),
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

    # `region` phải được MANG THEO, không được để rơi về mặc định.
    #
    # `ClassMetadata.region` mặc định là `unclassified`, nên dựng lại object mà
    # không truyền trường này biến MỌI lần sửa nhãn thành một lần xoá vùng:
    # đổi chính tả của `ăn [bac]` là nó thành `ăn [unclassified]`, im lặng, và
    # bản ghi không còn phân biệt được với biến thể miền Nam. Với dữ liệu QIPEDC
    # — nơi hàng trăm từ chỉ khác nhau ở đúng trường này — đó là mất dữ liệu chứ
    # không phải phiền toái.
    #
    # Người gọi ĐƯỢC đổi vùng, nhưng phải nói ra; im lặng nghĩa là giữ nguyên.
    region = normalize_region(
        payload["region"] if "region" in payload else row.get("region"))

    slug = slugify(label_original)
    class_uid = row["class_uid"]
    class_idx = int(row["class_idx"]) if str(row.get("class_idx") or "").strip() else None
    folder_override = f"class_{slug}_{class_uid[:8]}"
    return ClassMetadata(
        region=region,
        class_uid=class_uid,
        class_idx=class_idx,
        slug=slug,
        label_original=label_original,
        language=language,
        dialect=dialect,
        is_common_global=is_common_global,
        is_common_language=is_common_language and not is_common_global,
        folder_override=folder_override,
        # The retarget keeps the class with its owner: a move must not be able
        # to relocate a class into another tenant's tree.
        tenant_id=tenant_id_of(row),
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


def _google_drive_configured() -> bool:
    if not getattr(settings, "use_google_drive", False):
        return False
    credentials_path = Path(str(getattr(settings, "google_drive_credentials", "")))
    return credentials_path.exists()


def _drive_relative_path(local_path: Path) -> Optional[str]:
    return _dataset_storage_key(local_path)


def _sync_drive_catalog_csv(local_path: Path, remote_name: str) -> None:
    if not _google_drive_configured():
        logger.info("[CATALOG][GDRIVE] csv sync skipped: google drive not configured for %s", remote_name)
        return

    try:
        from app.storage.gdrive_client import apply_gdrive_suffix_to_remote_path, upload_to_gdrive

        remote_path = apply_gdrive_suffix_to_remote_path(remote_name)
        logger.info("[CATALOG][GDRIVE] csv sync begin: local=%s remote=%s", local_path, remote_path)
        upload_to_gdrive(
            str(local_path),
            remote_path,
            content_type="text/csv",
            make_public=False,
            replace_existing=True,
        )
        logger.info("[CATALOG][GDRIVE] csv sync done: local=%s remote=%s", local_path, remote_path)
    except Exception as exc:
        logger.warning("[CATALOG][GDRIVE] csv sync failed for %s: %s", remote_name, exc)


def _sync_drive_catalog_snapshots() -> None:
    _sync_drive_catalog_csv(MASTER_LABELS, "labels.csv")
    _sync_drive_catalog_csv(SAMPLES_CSV, "samples.csv")
    _sync_drive_catalog_csv(RAW_UPLOADS_CSV, "raw_uploads.csv")


def _sync_drive_and_sheets_versioned_tables(label_rows: Sequence[Dict[str, Any]] | None = None,
                                            sample_rows: Sequence[Dict[str, Any]] | None = None) -> None:
    """Mirror catalog CSVs to Drive and export labels/samples to Sheets — async.

    This name was referenced in class update/delete but never defined, so every
    catalog mutation raised NameError *after* doing the destructive work and
    then failed its own rollback. It now simply dispatches the existing Celery
    tasks (best-effort, non-blocking): the request thread neither waits on nor
    fails because of Google API calls. Args are accepted for call-site
    compatibility but unused (the tasks read the freshly written CSVs).
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
    except Exception as exc:  # dispatch failure (e.g. broker down) must not break CRUD
        logger.warning("[CATALOG] async Drive/Sheets sync dispatch failed: %s", exc)


def _dispatch_gdrive_folder_delete(paths: Sequence[Path]) -> None:
    """Queue Drive folder deletion (async cleanup) for the given local paths."""
    rel_paths = [rel for rel in (_drive_relative_path(p) for p in paths) if rel]
    if not rel_paths:
        return
    try:
        from app.export_tasks import delete_gdrive_paths_task

        delete_gdrive_paths_task.delay(rel_paths=rel_paths)
    except Exception as exc:
        logger.warning("[CATALOG] Drive folder delete dispatch failed for %s: %s", rel_paths, exc)


def _dispatch_gdrive_folder_move(pairs: Sequence[tuple[Path, Path]]) -> None:
    """Queue Drive folder moves (async) for (old_local, new_local) path pairs."""
    rel_pairs = []
    for old_path, new_path in pairs:
        old_rel = _drive_relative_path(old_path)
        new_rel = _drive_relative_path(new_path)
        if old_rel and new_rel and old_rel != new_rel:
            rel_pairs.append([old_rel, new_rel])
    if not rel_pairs:
        return
    try:
        from app.export_tasks import move_gdrive_paths_task

        move_gdrive_paths_task.delay(pairs=rel_pairs)
    except Exception as exc:
        logger.warning("[CATALOG] Drive folder move dispatch failed for %s: %s", rel_pairs, exc)


def _doi_pham_vi(tenant_id: Any) -> None:
    """Từ chối khi người gọi không mang phạm vi tenant. Không có đường lùi.

    Kiểm THAM SỐ THÔ, và phải gọi TRƯỚC `normalize_tenant_id()`. Hàm chuẩn hoá
    có `fallback=DEFAULT_TENANT_ID`, nên `""` và `None` đều trả về `"default"` —
    cố ý, vì nó phục vụ các hàng CSV có trước khi tenant tồn tại. Nhưng ở đường
    ghi theo yêu cầu, "trống" mang nghĩa NGƯỢC LẠI: không xác định được người
    gọi thuộc tenant nào.

    Kiểm sau khi chuẩn hoá thì `if not scope` là mã chết và một lượt gọi thiếu
    phạm vi chạy lặng lẽ với toàn quyền của tenant khởi tạo — tenant mặc định
    trở thành siêu tenant ngầm. `sync_reassign_sample` mắc đúng lỗi này và chỉ
    bị bắt bởi một ca kiểm `tenant_id=""` ngày 16/08/2026.
    """
    if not str(tenant_id or "").strip():
        raise CatalogSyncError("Thieu tenant context", status_code=400,
                               error_code="TENANT_SCOPE_REQUIRED")


def _write_samples_csv(rows: Sequence[Dict[str, Any]]) -> None:
    """Rewrite samples.csv using its REAL on-disk header (may be wider than
    SAMPLE_FIELDS). Writing with SAMPLE_FIELDS (19 cols) into the 23-col file
    silently misaligns every row, so honour the actual header instead."""
    from app.dataset_samples import _samples_fieldnames

    _write_csv(SAMPLES_CSV, _samples_fieldnames(), rows)


def _invalidate_tts_cache(label_text: str) -> None:
    """Best-effort: drop the cached TTS audio for a label whose text is being
    renamed away or deleted, so realtime playback never serves the stale clip.
    Purely a cache cleanup — never affects the catalog mutation."""
    try:
        from app.services.tts_service import invalidate_text_cache_sync

        invalidate_text_cache_sync(label_text)
    except Exception as exc:
        logger.debug("[CATALOG] TTS cache invalidate skipped for '%s': %s", label_text, exc)


def _rows_to_matrix(fieldnames: Sequence[str], rows: Sequence[Dict[str, Any]]) -> List[List[Any]]:
    matrix: List[List[Any]] = [list(fieldnames)]
    for row in rows:
        matrix.append([row.get(field, "") for field in fieldnames])
    return matrix


def _google_sheets_configured() -> bool:
    return bool(
        getattr(settings, "google_sheets_labels_spreadsheet_id", "")
        and int(getattr(settings, "google_sheets_labels_sheet_gid", 0) or 0)
        and getattr(settings, "google_sheets_samples_spreadsheet_id", "")
        and int(getattr(settings, "google_sheets_samples_sheet_gid", 0) or 0)
    )


def _sync_drive_move_folder_pairs(pairs: Sequence[tuple[Path, Path]]) -> None:
    if not _google_drive_configured():
        logger.info("[CATALOG][GDRIVE] move skipped: google drive not configured")
        return

    from app.storage.gdrive_client import get_gdrive_client

    client = get_gdrive_client()
    moved_pairs: List[tuple[str, str]] = []
    try:
        for old_path, new_path in pairs:
            old_rel = _drive_relative_path(old_path)
            new_rel = _drive_relative_path(new_path)
            if not old_rel or not new_rel or old_rel == new_rel:
                logger.debug(
                    "[CATALOG][GDRIVE] move skipped: old=%s new=%s old_rel=%s new_rel=%s",
                    old_path,
                    new_path,
                    old_rel,
                    new_rel,
                )
                continue
            logger.info("[CATALOG][GDRIVE] move begin: %s -> %s", old_rel, new_rel)
            client.move_folder_path(old_rel, new_rel)
            moved_pairs.append((old_rel, new_rel))
            logger.info("[CATALOG][GDRIVE] move done: %s -> %s", old_rel, new_rel)
    except Exception:
        logger.warning("[CATALOG][GDRIVE] move failed; starting rollback for %s moved pair(s)", len(moved_pairs))
        for old_rel, new_rel in reversed(moved_pairs):
            try:
                logger.info("[CATALOG][GDRIVE] move rollback begin: %s -> %s", new_rel, old_rel)
                client.move_folder_path(new_rel, old_rel)
                logger.info("[CATALOG][GDRIVE] move rollback done: %s -> %s", new_rel, old_rel)
            except Exception as rollback_exc:
                logger.error(
                    "[CATALOG][ROLLBACK][GDRIVE] Failed to move folder back %s -> %s: %s",
                    new_rel,
                    old_rel,
                    rollback_exc,
                )
        raise


def _sync_drive_delete_folder_pairs(pairs: Sequence[Path]) -> None:
    if not _google_drive_configured():
        logger.info("[CATALOG][GDRIVE] delete skipped: google drive not configured")
        return

    from app.storage.gdrive_client import get_gdrive_client

    client = get_gdrive_client()
    for path in pairs:
        rel = _drive_relative_path(path)
        if not rel:
            logger.debug("[CATALOG][GDRIVE] delete skipped: cannot build relative path for %s", path)
            continue
        logger.info("[CATALOG][GDRIVE] delete begin: %s", rel)
        client.delete_path(rel)
        logger.info("[CATALOG][GDRIVE] delete done: %s", rel)


def _restore_drive_from_backup(backup_root: Path, remote_root: Path) -> None:
    if not _google_drive_configured():
        logger.info("[CATALOG][GDRIVE] restore skipped: google drive not configured")
        return

    from app.storage.gdrive_client import get_gdrive_client

    client = get_gdrive_client()
    backup_root = Path(backup_root)
    remote_root = Path(remote_root)
    if not backup_root.exists():
        logger.debug("[CATALOG][GDRIVE] restore skipped: backup not found=%s", backup_root)
        return
    logger.info(
        "[CATALOG][GDRIVE] restore begin: backup=%s remote=%s",
        backup_root,
        _drive_relative_path(remote_root) or remote_root.as_posix(),
    )
    client.upload_folder_tree(str(backup_root), _drive_relative_path(remote_root) or remote_root.as_posix(), make_public=False, replace_existing=True)
    logger.info(
        "[CATALOG][GDRIVE] restore done: backup=%s remote=%s",
        backup_root,
        _drive_relative_path(remote_root) or remote_root.as_posix(),
    )


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


def sync_update_class(class_idx: int | str, payload: Dict[str, Any], *,
                      tenant_id: str) -> Dict[str, Any]:
    """Hai lượt đọc, hai vai trò — xem `sync_soft_delete_sample`."""
    ensure_tables()
    _doi_pham_vi(tenant_id)
    scope = normalize_tenant_id(tenant_id)
    op_id = f"class_update_{class_idx}"
    slog.start_operation(op_id)
    op_logs: List[str] = []

    with _catalog_lock():
        # TUẦN TỰ HOÁ: `_write_csv(MASTER_LABELS, ...)` phía dưới ghi lại TOÀN
        # BỘ labels.csv từ `rows`. Lọc nó theo tenant sẽ xoá trắng lớp của mọi
        # tenant khác — im lặng, trong một thao tác mang tên 'sửa một lớp'.
        rows = _load_all_labels_unscoped()
        # THẨM QUYỀN: người gọi chỉ chạm được lớp trong phạm vi của mình.
        target_row = _find_class_row_by_ref(load_labels(scope), class_idx)

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

        all_samples_before = _load_all_samples_unscoped()
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
                    new_sample_row["storage_url"] = str(new_file_path)
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

                raw_rows_after.append(new_raw_row)

            _write_csv(MASTER_LABELS, LABEL_FIELDS, updated_label_rows)
            regenerate_label_indexes()
            _write_samples_csv(sample_rows_after)
            _write_csv(RAW_UPLOADS_CSV, RAW_UPLOAD_FIELDS, raw_rows_after)

            # Mirror to Postgres.
            _sync_db_class(updated_class_row)
            _sync_db_samples([row for row in sample_rows_after if row.get("class_uid") == new_meta.class_uid])
            _sync_db_raw_uploads([row for row in raw_rows_after if row.get("class_uid") == new_meta.class_uid])

            # Trashed (soft-deleted) samples of this class live only in the DB,
            # not in samples.csv, so the loop above never touched them. Relabel
            # them here (new name + moved feature path) so restoring one later
            # brings it back consistent with the renamed class. deleted_at is
            # preserved — the upsert's ON CONFLICT clause never sets it.
            try:
                for dbrow in db_list_samples_by_class(old_meta.class_uid, include_deleted=True):
                    if not dbrow.get("deleted_at"):
                        continue  # active rows already handled above
                    updated = dict(dbrow)
                    old_fp = _resolve_sample_file_path(updated)
                    if old_fp is not None:
                        new_fp = _sample_new_path(old_fp, old_feature_dir, new_feature_dir)
                        updated["file_path"] = str(new_fp)
                        updated["storage_url"] = str(new_fp)
                    updated.update(
                        {
                            "class_uid": new_meta.class_uid,
                            "slug": new_meta.slug,
                            "label_original": new_meta.label_original,
                            "language": new_meta.language,
                            "dialect": new_meta.dialect,
                        }
                    )
                    db_upsert_sample(updated)
            except Exception as exc:
                logger.warning(
                    "[CATALOG] relabel of trashed samples failed for class_uid=%s: %s",
                    old_meta.class_uid, exc,
                )

            # If the spoken text changed, drop the old label's cached TTS audio
            # so realtime doesn't read the stale clip.
            if old_meta.label_original != new_meta.label_original:
                _invalidate_tts_cache(old_meta.label_original)

            # Drive folder move + catalog mirror run async (best-effort). The
            # rename is already committed locally + in Postgres; Google being out
            # of sync — e.g. a raw-videos folder that was never uploaded to Drive
            # — must not fail or slow the rename. This inline Drive move used to
            # raise FileNotFoundError and roll the whole rename back.
            _dispatch_gdrive_folder_move(
                [
                    (old_feature_dir, new_feature_dir),
                    (old_raw_dir, new_raw_dir),
                ]
            )
            _sync_drive_and_sheets_versioned_tables(updated_label_rows, sample_rows_after)
            op_logs.append("dispatched async Drive folder move + catalog mirror")

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
                "op_id": op_id,
                "operation_logs": op_logs,
            }
        except Exception as exc:
            # Roll back the visible state first.
            try:
                _write_csv(MASTER_LABELS, LABEL_FIELDS, rows)
                regenerate_label_indexes()
                _write_samples_csv(all_samples_before)
                _write_csv(RAW_UPLOADS_CSV, RAW_UPLOAD_FIELDS, all_raw_before)
                _restore_tree(backup_feature_dir, old_feature_dir)
                _restore_tree(backup_raw_dir, old_raw_dir)
                db_upsert_class(target_row)
                _sync_db_samples(all_samples_before)
                _sync_db_raw_uploads(all_raw_before)
                # Do NOT sync the non-versioned catalog snapshots (labels.csv / samples.csv) to Drive
                # Also restore versioned csvs
                _sync_drive_and_sheets_versioned_tables(rows, all_samples_before)
                op_logs.append("rollback: restored local CSVs and trees; versioned Drive+Sheets outputs restored")
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
            raise CatalogSyncError(str(exc), status_code=getattr(exc, "status_code", 500), error_code=getattr(exc, "error_code", "CATALOG_SYNC_FAILED"), logs=op_logs) from exc
        finally:
            shutil.rmtree(snapshot_root, ignore_errors=True)


def sync_delete_class(class_idx: int | str, *, tenant_id: str) -> Dict[str, Any]:
    """Hai lượt đọc, hai vai trò — xem `sync_soft_delete_sample`."""
    ensure_tables()
    _doi_pham_vi(tenant_id)
    scope = normalize_tenant_id(tenant_id)
    op_id = f"class_delete_{class_idx}"
    slog.start_operation(op_id)

    op_logs: List[str] = []

    with _catalog_lock():
        # TUẦN TỰ HOÁ: `_write_csv(MASTER_LABELS, ...)` phía dưới ghi lại TOÀN
        # BỘ labels.csv từ `rows`. Lọc nó theo tenant sẽ xoá trắng lớp của mọi
        # tenant khác — im lặng, trong một thao tác mang tên 'sửa một lớp'.
        rows = _load_all_labels_unscoped()
        # THẨM QUYỀN: người gọi chỉ chạm được lớp trong phạm vi của mình.
        target_row = _find_class_row_by_ref(load_labels(scope), class_idx)

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
        all_samples_before = _load_all_samples_unscoped()
        all_raw_before = list_raw_uploads()
        sample_rows_before = [row for row in all_samples_before if row.get("class_uid") == old_meta.class_uid]
        raw_rows_before = [row for row in all_raw_before if row.get("class_uid") == old_meta.class_uid]
        old_feature_dir = old_meta.hierarchy_path()
        old_raw_dir = Path(settings.dataset_root) / "raw_videos" / old_meta.language / old_meta.dialect / old_meta.folder_name()
        snapshot_root = Path(tempfile.mkdtemp(prefix="catalog_sync_"))
        backup_feature_dir = _backup_tree(old_feature_dir, snapshot_root)
        backup_raw_dir = _backup_tree(old_raw_dir, snapshot_root)
        try:
            # LOCAL-FIRST: commit the local filesystem + CSV + DB delete
            # synchronously (fast, transactional), then hand ALL Google Drive /
            # Sheets work to Celery. Previously every Drive call ran inline —
            # ~14s per delete, holding the catalog lock — and a single Drive
            # error (or the undefined versioned-sync helper) rolled the whole
            # thing back, so deletes appeared to "hang then fail".
            logger.info("[CATALOG] class delete begin (local-first): class_uid=%s", old_meta.class_uid)
            op_logs.append(f"class delete begin: class_uid={old_meta.class_uid}")

            _remove_tree(old_feature_dir)
            _remove_tree(old_raw_dir)

            remaining_label_rows = [row for row in rows if row.get("class_uid") != old_meta.class_uid]
            remaining_sample_rows = [row for row in all_samples_before if row.get("class_uid") != old_meta.class_uid]
            remaining_raw_rows = [row for row in all_raw_before if row.get("class_uid") != old_meta.class_uid]

            _write_csv(MASTER_LABELS, LABEL_FIELDS, remaining_label_rows)
            regenerate_label_indexes()
            _write_samples_csv(remaining_sample_rows)
            _write_csv(RAW_UPLOADS_CSV, RAW_UPLOAD_FIELDS, remaining_raw_rows)

            # Children BEFORE the parent. The reverse order left samples whose
            # class_uid pointed at a row that no longer existed whenever the
            # sample delete failed after the class delete succeeded — 39 such
            # orphans accumulated in production, invisible to every class-scoped
            # query. samples.class_uid now has a FK to classes, so the reverse
            # order would also be rejected outright.
            db_delete_samples_by_class(old_meta.class_uid)
            db_delete_raw_uploads_by_class(old_meta.class_uid)
            db_delete_class(old_meta.class_uid)

            # The label is gone — drop its cached TTS audio.
            _invalidate_tts_cache(old_meta.label_original)

            # Async, best-effort Drive cleanup + catalog mirror (never blocks
            # or fails the delete the user just confirmed).
            _dispatch_gdrive_folder_delete([old_feature_dir, old_raw_dir])
            _sync_drive_and_sheets_versioned_tables(remaining_label_rows, remaining_sample_rows)
            op_logs.append("dispatched async Drive folder delete + catalog mirror")

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
                "op_id": op_id,
                "operation_logs": op_logs,
            }
        except Exception as exc:
            # Only LOCAL state was touched, so rollback is local only (no Drive).
            try:
                logger.info("[CATALOG][ROLLBACK] restoring local/db state after delete failure for class_uid=%s", old_meta.class_uid)
                _write_csv(MASTER_LABELS, LABEL_FIELDS, rows)
                regenerate_label_indexes()
                _write_samples_csv(all_samples_before)
                _write_csv(RAW_UPLOADS_CSV, RAW_UPLOAD_FIELDS, all_raw_before)
                _restore_tree(backup_feature_dir, old_feature_dir)
                _restore_tree(backup_raw_dir, old_raw_dir)
                db_upsert_class(target_row)
                _sync_db_samples(all_samples_before)
                _sync_db_raw_uploads(all_raw_before)
                op_logs.append("rollback: restored local CSVs/DB/trees from backup")
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
            raise CatalogSyncError(str(exc), status_code=getattr(exc, "status_code", 500), error_code=getattr(exc, "error_code", "CATALOG_SYNC_FAILED"), logs=op_logs) from exc
        finally:
            shutil.rmtree(snapshot_root, ignore_errors=True)


# ===========================================================================
# Trash: soft delete / restore / purge (classes)
# ===========================================================================

def _db_class_row_to_label_row(dbrow: Dict[str, Any]) -> Dict[str, Any]:
    """Project a DB classes row back into a labels.csv row (LABEL_FIELDS)."""
    row = {f: (dbrow.get(f) if dbrow.get(f) is not None else "") for f in LABEL_FIELDS}
    row["class_idx"] = "" if dbrow.get("class_idx") in (None, "") else str(dbrow.get("class_idx"))
    row["is_common_global"] = str(int(bool(dbrow.get("is_common_global"))))
    row["is_common_language"] = str(int(bool(dbrow.get("is_common_language"))))
    # This projection fills "" for anything the DB row lacks, and it feeds the
    # restore-from-trash path — so a query that forgets tenant_id would write an
    # unassigned class back into the source of truth. Force a concrete owner.
    row[TENANT_COLUMN] = tenant_id_of(row)
    return row


def _db_sample_row_to_csv_row(dbrow: Dict[str, Any]) -> Dict[str, Any]:
    from app.dataset_samples import _samples_fieldnames

    hdr = _samples_fieldnames()
    row = {f: (dbrow.get(f) if dbrow.get(f) is not None else "") for f in hdr}
    # Same reason as _db_class_row_to_label_row: restoring a soft-deleted sample
    # must not put a tenant-less row back into samples.csv. Only stamp when the
    # on-disk header actually has the column — before the migration runs it does
    # not, and adding a key the header lacks would raise in csv.DictWriter.
    if TENANT_COLUMN in hdr:
        row[TENANT_COLUMN] = tenant_id_of(row)
    return row


def sync_soft_delete_class(class_idx: int | str, *, tenant_id: str) -> Dict[str, Any]:
    """Move a class to Trash: hide it from the active catalog (labels/samples/
    raw CSVs) and set deleted_at in the DB. Local files + Drive content are KEPT
    so it can be restored; a later purge removes them permanently. Fast: no
    inline Google I/O (the catalog mirror is dispatched async)."""
    ensure_tables()
    _doi_pham_vi(tenant_id)
    scope = normalize_tenant_id(tenant_id)
    op_id = f"class_soft_delete_{class_idx}"
    slog.start_operation(op_id)
    op_logs: List[str] = []

    with _catalog_lock():
        # TUẦN TỰ HOÁ: `_write_csv(MASTER_LABELS, ...)` phía dưới ghi lại TOÀN
        # BỘ labels.csv từ `rows`. Lọc nó theo tenant sẽ xoá trắng lớp của mọi
        # tenant khác — im lặng, trong một thao tác mang tên 'sửa một lớp'.
        rows = _load_all_labels_unscoped()
        # THẨM QUYỀN: người gọi chỉ chạm được lớp trong phạm vi của mình.
        target_row = _find_class_row_by_ref(load_labels(scope), class_idx)
        if target_row is None:
            slog.log_operation(
                OperationType.CLASS_DELETE, OperationStatus.FAILURE,
                {"class_idx": class_idx, "reason": "not_found"},
                duration_ms=slog.end_operation(op_id), error_code="CLASS_NOT_FOUND",
            )
            raise CatalogSyncError(f"Class {class_idx} not found", status_code=404, error_code="CLASS_NOT_FOUND")

        old_meta = _build_class_meta_from_row(target_row)
        all_samples_before = _load_all_samples_unscoped()
        all_raw_before = list_raw_uploads()
        sample_rows_before = [r for r in all_samples_before if r.get("class_uid") == old_meta.class_uid]
        raw_rows_before = [r for r in all_raw_before if r.get("class_uid") == old_meta.class_uid]

        try:
            remaining_label_rows = [r for r in rows if r.get("class_uid") != old_meta.class_uid]
            remaining_sample_rows = [r for r in all_samples_before if r.get("class_uid") != old_meta.class_uid]
            remaining_raw_rows = [r for r in all_raw_before if r.get("class_uid") != old_meta.class_uid]

            _write_csv(MASTER_LABELS, LABEL_FIELDS, remaining_label_rows)
            regenerate_label_indexes()
            _write_samples_csv(remaining_sample_rows)
            _write_csv(RAW_UPLOADS_CSV, RAW_UPLOAD_FIELDS, remaining_raw_rows)

            # Ensure the class + its samples/raw exist in the DB before marking
            # them deleted, so the trash record and restore are reliable even for
            # a class that lived only in the CSV catalog (register_class does not
            # always upsert to Postgres).
            db_upsert_class(target_row)
            _sync_db_samples(sample_rows_before)
            _sync_db_raw_uploads(raw_rows_before)

            db_soft_delete_class(old_meta.class_uid)
            db_soft_delete_samples_by_class(old_meta.class_uid)
            db_soft_delete_raw_uploads_by_class(old_meta.class_uid)

            _sync_drive_and_sheets_versioned_tables(remaining_label_rows, remaining_sample_rows)
            op_logs.append("soft-deleted to trash; async catalog mirror dispatched")

            slog.log_operation(
                OperationType.CLASS_DELETE, OperationStatus.SUCCESS,
                {"class_idx": class_idx, "class_uid": old_meta.class_uid, "soft": True,
                 "sample_count": len(sample_rows_before)},
                duration_ms=slog.end_operation(op_id),
            )
            return {
                "deleted": True, "soft": True, "class_uid": old_meta.class_uid,
                "class_idx": old_meta.class_idx, "sample_count": len(sample_rows_before),
                "raw_upload_count": len(raw_rows_before), "op_id": op_id, "operation_logs": op_logs,
            }
        except Exception as exc:
            try:
                _write_csv(MASTER_LABELS, LABEL_FIELDS, rows)
                regenerate_label_indexes()
                _write_samples_csv(all_samples_before)
                _write_csv(RAW_UPLOADS_CSV, RAW_UPLOAD_FIELDS, all_raw_before)
                db_restore_class(old_meta.class_uid)
                db_restore_samples_by_class(old_meta.class_uid)
                db_restore_raw_uploads_by_class(old_meta.class_uid)
            except Exception as rb:
                logger.error("[CATALOG][ROLLBACK] soft-delete restore failed for %s: %s", old_meta.class_uid, rb)
            raise CatalogSyncError(str(exc), status_code=getattr(exc, "status_code", 500),
                                   error_code=getattr(exc, "error_code", "CATALOG_SYNC_FAILED"), logs=op_logs) from exc


def sync_restore_class(class_uid: str, *, tenant_id: str) -> Dict[str, Any]:
    """Restore a soft-deleted class from Trash: clear deleted_at in the DB and
    rebuild its labels.csv + samples.csv rows from the DB records."""
    ensure_tables()
    _doi_pham_vi(tenant_id)
    scope = normalize_tenant_id(tenant_id)
    op_id = f"class_restore_{class_uid}"
    slog.start_operation(op_id)

    with _catalog_lock():
        dbrow = db_get_deleted_class(class_uid)
        # `rows` ghi lại cả labels.csv -> toàn cục. `already` là câu hỏi THẨM
        # QUYỀN ("lớp này đã sống trong tenant của người gọi chưa") -> phạm vi.
        rows = _load_all_labels_unscoped()
        already = any(r.get("class_uid") == class_uid for r in load_labels(scope))
        if dbrow is None and not already:
            raise CatalogSyncError(f"Deleted class {class_uid} not found in trash", status_code=404, error_code="CLASS_NOT_FOUND")

        # Clear soft-delete flags in DB.
        db_restore_class(class_uid)
        db_restore_samples_by_class(class_uid)
        db_restore_raw_uploads_by_class(class_uid)

        if not already and dbrow is not None:
            rows.append(_db_class_row_to_label_row(dbrow))
            _write_csv(MASTER_LABELS, LABEL_FIELDS, rows)
            regenerate_label_indexes()

            # Rebuild samples.csv rows from DB (dedupe against existing).
            # TUẦN TỰ HOÁ: `existing + restored` được ghi đè lên cả tệp, nên
            # `existing` phải chứa hàng của MỌI tenant.
            existing = _load_all_samples_unscoped()
            existing_uids = {r.get("sample_uid") for r in existing}
            db_samples = db_list_samples_by_class(class_uid, include_deleted=True)
            restored = [_db_sample_row_to_csv_row(s) for s in db_samples
                        if s.get("sample_uid") not in existing_uids]
            if restored:
                _write_samples_csv(existing + restored)

        _sync_drive_and_sheets_versioned_tables(None, None)
        slog.log_operation(
            OperationType.CLASS_UPDATE, OperationStatus.SUCCESS,
            {"class_uid": class_uid, "restored": True}, duration_ms=slog.end_operation(op_id),
        )
        return {"restored": True, "class_uid": class_uid, "op_id": op_id}


def sync_purge_class(class_uid: str, *, tenant_id: str) -> Dict[str, Any]:
    """Permanently delete a class (from Trash or active): remove local files,
    hard-delete DB rows, dispatch async Drive folder deletion. Irreversible."""
    ensure_tables()
    _doi_pham_vi(tenant_id)
    scope = normalize_tenant_id(tenant_id)
    op_id = f"class_purge_{class_uid}"
    slog.start_operation(op_id)

    with _catalog_lock():
        rows = _load_all_labels_unscoped()
        # THẨM QUYỀN: chỉ xoá vĩnh viễn được lớp trong phạm vi người gọi.
        active_row = next((r for r in load_labels(scope)
                           if r.get("class_uid") == class_uid), None)
        meta_row = active_row or db_get_deleted_class(class_uid)
        if meta_row is None:
            raise CatalogSyncError(f"Class {class_uid} not found", status_code=404, error_code="CLASS_NOT_FOUND")

        old_meta = _build_class_meta_from_row(meta_row)
        feature_dir = old_meta.hierarchy_path()
        raw_dir = Path(settings.dataset_root) / "raw_videos" / old_meta.language / old_meta.dialect / old_meta.folder_name()

        # If still in the active catalog, drop it from the CSVs too.
        if active_row is not None:
            _write_csv(MASTER_LABELS, LABEL_FIELDS, [r for r in rows if r.get("class_uid") != class_uid])
            regenerate_label_indexes()
            _write_samples_csv([r for r in _load_all_samples_unscoped()
                                if r.get("class_uid") != class_uid])
            _write_csv(RAW_UPLOADS_CSV, RAW_UPLOAD_FIELDS,
                       [r for r in list_raw_uploads() if r.get("class_uid") != class_uid])

        _remove_tree(feature_dir)
        _remove_tree(raw_dir)

        db_delete_samples_by_class(class_uid)
        db_delete_raw_uploads_by_class(class_uid)
        db_delete_class(class_uid)

        _invalidate_tts_cache(old_meta.label_original)

        _dispatch_gdrive_folder_delete([feature_dir, raw_dir])
        _sync_drive_and_sheets_versioned_tables(None, None)

        slog.log_operation(
            OperationType.CLASS_DELETE, OperationStatus.SUCCESS,
            {"class_uid": class_uid, "purged": True}, duration_ms=slog.end_operation(op_id),
        )
        return {"purged": True, "class_uid": class_uid, "op_id": op_id}


def list_trash_classes() -> List[Dict[str, Any]]:
    ensure_tables()
    return db_list_deleted_classes()


# ===========================================================================
# Trash: soft delete / restore / purge (samples)
# ===========================================================================

def sync_soft_delete_sample(sample_uid: str, *, tenant_id: str) -> Dict[str, Any]:
    """Move a single sample to Trash: remove it from samples.csv and set
    deleted_at in the DB. The .npz file + Drive copy are kept for restore.

    HAI LƯỢT ĐỌC, HAI VAI TRÒ KHÁC NHAU — 16/08/2026
    ================================================
    Bản trước dùng MỘT lượt `list_samples()` cho cả hai việc, và đó là lý do
    không thể chỉ đổi nó thành `list_samples(scope)`:

        THẨM QUYỀN      "người gọi được xoá mẫu nào"      -> PHẢI theo phạm vi
        TUẦN TỰ HOÁ     "ghi lại toàn bộ samples.csv"     -> PHẢI là toàn cục

    Lọc theo tenant rồi đưa vào `_write_samples_csv()` sẽ ghi đè cả tệp bằng
    riêng phần của một tenant — tức là XOÁ TRẮNG hàng của mọi tenant khác, im
    lặng, trong một thao tác mang tên "xoá mềm một mẫu". Một bản vá an ninh làm
    mất dữ liệu thì tệ hơn lỗ hổng nó vá.

    Nên: phân giải trong `_theo_pham_vi`, tuần tự hoá từ `_toan_bo`.
    """
    ensure_tables()
    _doi_pham_vi(tenant_id)
    scope = normalize_tenant_id(tenant_id)
    op_id = f"sample_soft_delete_{sample_uid}"
    slog.start_operation(op_id)
    with _catalog_lock():
        # THẨM QUYỀN: chỉ thấy mẫu trong phạm vi người gọi.
        target = next((r for r in list_samples(scope)
                       if r.get("sample_uid") == sample_uid), None)
        if target is None:
            raise CatalogSyncError(f"Sample {sample_uid} not found", status_code=404, error_code="SAMPLE_NOT_FOUND")
        # TUẦN TỰ HOÁ: toàn bộ tệp, giữ nguyên hàng của mọi tenant khác.
        rows = _load_all_samples_unscoped()
        try:
            _write_samples_csv([r for r in rows if r.get("sample_uid") != sample_uid])
            db_upsert_sample(target)  # ensure DB row exists before marking deleted
            db_soft_delete_sample(sample_uid)
            _sync_drive_and_sheets_versioned_tables(None, None)
        except Exception as exc:
            try:
                _write_samples_csv(rows)
                db_restore_sample(sample_uid)
            except Exception as rb:
                logger.error("[CATALOG][ROLLBACK] sample soft-delete restore failed for %s: %s", sample_uid, rb)
            raise CatalogSyncError(str(exc), status_code=getattr(exc, "status_code", 500),
                                   error_code=getattr(exc, "error_code", "CATALOG_SYNC_FAILED")) from exc
        slog.log_operation(
            OperationType.SAMPLE_DELETE, OperationStatus.SUCCESS,
            {"sample_uid": sample_uid, "soft": True}, duration_ms=slog.end_operation(op_id),
        )
        return {"deleted": True, "soft": True, "sample_uid": sample_uid}


def sync_restore_sample(sample_uid: str, *, tenant_id: str) -> Dict[str, Any]:
    """Restore a soft-deleted sample: clear deleted_at and re-add its samples.csv
    row from the DB record.

    Hai lượt đọc, hai vai trò — xem `sync_soft_delete_sample`. `already` hỏi
    trong PHẠM VI (mẫu này đã sống trong tenant của người gọi chưa), còn `rows`
    dùng để ghi lại toàn bộ tệp nên phải toàn cục.
    """
    ensure_tables()
    _doi_pham_vi(tenant_id)
    scope = normalize_tenant_id(tenant_id)
    op_id = f"sample_restore_{sample_uid}"
    slog.start_operation(op_id)
    with _catalog_lock():
        dbrow = db_get_deleted_sample(sample_uid)
        already = any(r.get("sample_uid") == sample_uid for r in list_samples(scope))
        rows = _load_all_samples_unscoped()
        if dbrow is None and not already:
            raise CatalogSyncError(f"Deleted sample {sample_uid} not found in trash", status_code=404, error_code="SAMPLE_NOT_FOUND")
        db_restore_sample(sample_uid)
        if not already and dbrow is not None:
            _write_samples_csv(rows + [_db_sample_row_to_csv_row(dbrow)])
        _sync_drive_and_sheets_versioned_tables(None, None)
        slog.log_operation(
            OperationType.SAMPLE_DELETE, OperationStatus.SUCCESS,
            {"sample_uid": sample_uid, "restored": True}, duration_ms=slog.end_operation(op_id),
        )
        return {"restored": True, "sample_uid": sample_uid}


def sync_reassign_sample(sample_uid: str, target_class_ref: int | str,
                         *, tenant_id: str) -> Dict[str, Any]:
    """Move ONE sample to a different EXISTING class (it was recorded under the
    wrong label). Moves the local .npz (+ sidecar) into the target class folder,
    relabels the samples.csv + Postgres row, and re-mirrors to Drive (upload the
    moved file to its new path, then delete the old Drive copy). The caller
    enforces ownership.

    If the .npz is Drive-only (not materialized locally) it is downloaded from
    Drive FIRST, then moved + re-uploaded like any local sample. If it cannot be
    materialized (no local copy and no Drive copy to fetch), the reassign is
    REFUSED rather than committed — the previous behaviour deleted the old Drive
    file and never re-uploaded it, silently losing the sample.

    HAI LỖI ĐÃ SỬA Ở ĐÂY, 16/08/2026 — độc lập với nhau
    ===================================================
    **P0-A — phân giải xuyên tenant.** Bản trước tìm cả mẫu lẫn lớp đích trong
    TOÀN BỘ kho (`load_labels()`, `list_samples()` khi hai hàm ấy còn không có
    tham số tenant). Endpoint gọi nó chỉ kiểm QUYỀN SỞ HỮU (`auth_user_id`), và
    KHÔNG kiểm gì với `target_class_ref`. Đo được trên bộ dựng lại phép đo:

        iso_user_a, mẫu CỦA CHÍNH MÌNH, target_class_ref = lớp của iso_b
        -> lớp của iso_b được phân giải thành công

    Nay cả hai phép phân giải chạy BÊN TRONG phạm vi tenant, và một lớp thuộc
    tenant khác không phân biệt được với một lớp không tồn tại.

    **P0-B — ghi hai mặt phẳng không nguyên tử.** Đây là lỗi KHÁC, không phải
    chi tiết của lỗi trên: nó xảy ra cả khi mẫu và lớp cùng một tenant. Thứ tự
    cũ là

        di chuyển tệp -> ghi samples.csv -> ghi PostgreSQL

    và khối `except` chỉ hoàn nguyên phần TỆP. Nên khi PostgreSQL từ chối —
    trong lượt đo là `fk_samples_class_tenant` — kết quả là:

        HTTP 400          người gọi thấy "thất bại"
        PostgreSQL        không đổi
        samples.csv       ĐÃ ĐỔI, không hoàn nguyên
        tệp .npz          đã về chỗ cũ  -> file_path treo

    Và vì đường đọc lấy từ CSV, tenant B nhìn thấy mẫu của A trong lớp của B —
    do một request đã báo lỗi.

    Nay PostgreSQL ghi TRƯỚC: nó là nơi ràng buộc được cưỡng chế, nên nó phải là
    cửa ải. CSV chỉ được ghi sau khi ràng buộc đã qua.

    Điều này CHƯA phải nguyên tử đầy đủ: một lượt ghi CSV hỏng sau khi
    PostgreSQL đã commit vẫn để lại lệch theo chiều ngược lại. Đóng hẳn khoảng
    đó cần staging/bù trừ hoặc một nguồn chân lý duy nhất — mở riêng, không gộp
    vào P0 này. Xem docs/10-issues/.
    """
    ensure_tables()
    _doi_pham_vi(tenant_id)
    scope = normalize_tenant_id(tenant_id)
    op_id = f"sample_reassign_{sample_uid}"
    slog.start_operation(op_id)
    with _catalog_lock():
        # Phân giải TRONG phạm vi, trước mọi tác dụng phụ. Không tìm toàn cục
        # rồi mới so `tenant_id`: mọi thứ xảy ra ở giữa là một kênh phụ trả lời
        # "đối tượng này có thật không".
        target_row = _find_class_row_by_ref(load_labels(scope), target_class_ref)
        if target_row is None:
            slog.end_operation(op_id)
            # Cùng thông điệp với một lớp không tồn tại. Nói "lớp này thuộc
            # tenant khác" là tự dựng lại phép thử tồn tại vừa gỡ.
            raise CatalogSyncError(f"Target class {target_class_ref} not found",
                                   status_code=404, error_code="CLASS_NOT_FOUND")
        target_meta = _build_class_meta_from_row(target_row)

        rows = list_samples(scope)
        sample_row = next((r for r in rows if r.get("sample_uid") == sample_uid), None)
        if sample_row is None:
            slog.end_operation(op_id)
            raise CatalogSyncError(f"Sample {sample_uid} not found",
                                   status_code=404, error_code="SAMPLE_NOT_FOUND")

        if sample_row.get("class_uid") == target_meta.class_uid:
            slog.end_operation(op_id)
            return {"changed": False, "sample_uid": sample_uid, "class_uid": target_meta.class_uid}

        old_storage_key = str(sample_row.get("storage_key") or "").strip()
        old_storage_url = str(sample_row.get("storage_url") or "").strip()
        old_file = _resolve_sample_file_path(sample_row)
        if old_file is not None and not old_file.is_absolute():
            old_file = Path(settings.dataset_root) / old_file

        target_dir = target_meta.hierarchy_path()
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = old_file.name if old_file else f"sample_{sample_uid}.npz"
        new_file = target_dir / filename
        new_sidecar = new_file.with_suffix(".json")
        old_sidecar = old_file.with_suffix(".json") if old_file else None

        moved_main = False
        moved_side = False
        try:
            # Drive-only sample (not materialized on this machine): fetch it from
            # Drive FIRST so the move + re-upload below runs the exact same path
            # as a local sample. Without this, the Drive block deleted the old
            # file but skipped the upload (new_file never existed) — losing the .npz.
            if old_file is not None and not old_file.exists() and _google_drive_configured():
                dl_ref = (old_storage_url
                          if old_storage_url.startswith(("gdrive://", "https://drive.google.com"))
                          else "")
                if dl_ref:
                    try:
                        get_gdrive_client().download_file(dl_ref, str(old_file))
                    except Exception as exc:
                        logger.warning("[CATALOG] reassign: materialize from Drive failed for %s: %s", sample_uid, exc)

            # Refuse rather than relabel a row whose file we cannot relocate: the
            # old code would delete the Drive copy and never re-upload it.
            if old_file is not None and not old_file.exists():
                raise CatalogSyncError(
                    "Mẫu chưa có bản .npz trên máy để di chuyển; hãy đồng bộ (pull) file "
                    "từ Drive rồi đổi nhãn lại.",
                    status_code=409, error_code="SAMPLE_NOT_MATERIALIZED")

            if old_file is not None and old_file.exists():
                if new_file.exists():
                    raise CatalogSyncError(f"Target file already exists: {new_file}",
                                           status_code=409, error_code="SAMPLE_PATH_CONFLICT")
                shutil.move(str(old_file), str(new_file))
                moved_main = True
                if old_sidecar and old_sidecar.exists():
                    shutil.move(str(old_sidecar), str(new_sidecar))
                    moved_side = True
                _update_sample_metadata_json(new_file, target_meta)

            new_key = _dataset_storage_key(new_file) or (
                f"features/{target_meta.language}/{target_meta.dialect}/"
                f"{target_meta.folder_name()}/{filename}")

            updated = dict(sample_row)
            updated.update({
                "class_uid": target_meta.class_uid,
                "slug": target_meta.slug,
                "label_original": target_meta.label_original,
                "language": target_meta.language,
                "dialect": target_meta.dialect,
                "file_path": str(_relative_to_dataset(new_file) or new_file),
                "storage_key": new_key,
                # The old Drive URL is stale after the move; the re-upload task
                # below rewrites it. Meanwhile keep the local path (same shape as
                # a fresh upload before its Drive mirror completes).
                "storage_url": str(new_file),
            })
            # PostgreSQL TRƯỚC, CSV SAU. Đây là nửa P0-B của bản vá 16/08/2026.
            #
            # Ràng buộc được cưỡng chế ở cơ sở dữ liệu, không ở đây — trong lượt
            # đo, `fk_samples_class_tenant` là thứ duy nhất chặn được lượt ghi
            # xuyên tenant. Nên nó phải là CỬA ẢI, không phải bước cuối.
            #
            # Thứ tự cũ ghi CSV trước, và khối `except` bên dưới chỉ hoàn nguyên
            # phần TỆP. Một lượt PostgreSQL từ chối để lại `samples.csv` đã đổi
            # trong khi HTTP trả lỗi — và vì đường đọc lấy từ CSV, thay đổi ấy
            # nhìn thấy được với người dùng.
            #
            # Đọc lại `rows` từ đĩa: `db_upsert_sample` có thể chạy lâu, và bản
            # chụp trước đó đã cũ. Ghi đè bằng bản cũ sẽ nuốt mất lượt ghi song
            # song — `_catalog_lock()` che phần lớn, nhưng đọc lại thì rẻ.
            db_upsert_sample(updated)
            _write_samples_csv([
                updated if r.get("sample_uid") == sample_uid else r
                for r in _load_all_samples_unscoped()
            ])

            # Drive: delete the old file, upload the moved one to its new path.
            # Reuses existing tasks — no new Drive primitive — and is best-effort:
            # the local catalog is already the source of truth.
            # Drive re-mirror: upload the moved file to its new path, and delete
            # the old Drive copy ONLY when we actually have the new file to upload
            # — pairing the two so a reassign can never delete without re-uploading.
            if _google_drive_configured() and new_file.exists():
                try:
                    from app.export_tasks import delete_gdrive_files_task, upload_npz_to_gdrive_task

                    upload_npz_to_gdrive_task.delay(
                        sample_uid=sample_uid, local_path=str(new_file),
                        storage_key=new_key, sidecar_path=str(new_sidecar))
                    old_ref = old_storage_key or (
                        old_storage_url
                        if old_storage_url.startswith(("gdrive://", "https://drive.google.com"))
                        else "")
                    if old_ref and old_ref != new_key:
                        delete_gdrive_files_task.delay(refs=[old_ref])
                except Exception as exc:
                    logger.warning("[CATALOG] reassign Drive re-mirror dispatch failed for %s: %s", sample_uid, exc)

            _sync_drive_and_sheets_versioned_tables(None, None)
            slog.log_operation(
                OperationType.SAMPLE_UPDATE, OperationStatus.SUCCESS,
                {"sample_uid": sample_uid, "class_uid": target_meta.class_uid,
                 "slug": target_meta.slug, "reassigned": True},
                duration_ms=slog.end_operation(op_id),
            )
            return {
                "changed": True, "sample_uid": sample_uid,
                "class_uid": target_meta.class_uid,
                "label_original": target_meta.label_original,
                "slug": target_meta.slug,
            }
        except Exception as exc:
            try:  # roll the local move back so the file isn't stranded
                if moved_side and new_sidecar.exists() and old_sidecar is not None:
                    shutil.move(str(new_sidecar), str(old_sidecar))
                if moved_main and new_file.exists() and old_file is not None:
                    shutil.move(str(new_file), str(old_file))
            except Exception as rb:
                logger.error("[CATALOG][ROLLBACK] reassign restore failed for %s: %s", sample_uid, rb)
            slog.end_operation(op_id)
            raise CatalogSyncError(str(exc), status_code=getattr(exc, "status_code", 500),
                                   error_code=getattr(exc, "error_code", "CATALOG_SYNC_FAILED")) from exc


def list_trash_samples() -> List[Dict[str, Any]]:
    ensure_tables()
    return db_list_deleted_samples()


def list_trash_samples_for_user(auth_user_id: str) -> List[Dict[str, Any]]:
    """A single contributor's own soft-deleted samples (ownership by UUID)."""
    ensure_tables()
    from app.storage.metadata_db import list_deleted_samples_for_user as _db_for_user

    return _db_for_user(auth_user_id)


# ===========================================================================
# Bulk trash actions (multi-select + empty trash)
# ===========================================================================

def _bulk(fn, ids: Sequence[str]) -> Dict[str, Any]:
    ok: List[str] = []
    failed: List[Dict[str, str]] = []
    for i in ids or []:
        try:
            fn(i)
            ok.append(i)
        except Exception as exc:
            logger.warning("[CATALOG][BULK] %s(%s) failed: %s", getattr(fn, "__name__", fn), i, exc)
            failed.append({"id": i, "error": str(exc)})
    return {"ok": ok, "failed": failed, "ok_count": len(ok), "failed_count": len(failed)}


def bulk_restore_classes(class_uids: Sequence[str]) -> Dict[str, Any]:
    return _bulk(sync_restore_class, class_uids)


def bulk_purge_classes(class_uids: Sequence[str]) -> Dict[str, Any]:
    return _bulk(sync_purge_class, class_uids)


def bulk_restore_samples(sample_uids: Sequence[str]) -> Dict[str, Any]:
    return _bulk(sync_restore_sample, sample_uids)


def bulk_purge_samples(sample_uids: Sequence[str]) -> Dict[str, Any]:
    return _bulk(sync_purge_sample, sample_uids)


def empty_class_trash() -> Dict[str, Any]:
    """Permanently delete every soft-deleted class."""
    return bulk_purge_classes([c["class_uid"] for c in list_trash_classes()])


def empty_sample_trash() -> Dict[str, Any]:
    """Permanently delete every soft-deleted sample (whose class is active)."""
    return bulk_purge_samples([s["sample_uid"] for s in list_trash_samples()])


def sync_purge_sample(sample_uid: str, *, tenant_id: str) -> Dict[str, Any]:
    """Permanently delete a soft-deleted sample: remove the .npz (+ sidecar),
    hard-delete the DB row, and delete the Drive copy. Irreversible.

    Hai lượt đọc, hai vai trò — xem `sync_soft_delete_sample`. Thao tác này
    KHÔNG hoàn tác được, nên cổng phạm vi ở đây là chỗ ít được phép sai nhất
    trong cả tệp.
    """
    ensure_tables()
    _doi_pham_vi(tenant_id)
    scope = normalize_tenant_id(tenant_id)
    op_id = f"sample_purge_{sample_uid}"
    slog.start_operation(op_id)
    with _catalog_lock():
        # Prefer the samples.csv row (active) else the soft-deleted DB row.
        # THẨM QUYỀN theo phạm vi; `rows` toàn cục chỉ để ghi lại cả tệp.
        target = next((r for r in list_samples(scope)
                       if r.get("sample_uid") == sample_uid), None)
        rows = _load_all_samples_unscoped()
        dbrow = db_get_deleted_sample(sample_uid) if target is None else None
        source = target or dbrow
        if source is None:
            raise CatalogSyncError(f"Sample {sample_uid} not found", status_code=404, error_code="SAMPLE_NOT_FOUND")

        sample_file = _resolve_sample_file_path(source)
        if sample_file and not sample_file.is_absolute():
            sample_file = Path(settings.dataset_root) / sample_file
        try:
            if sample_file and sample_file.exists():
                sample_file.unlink()
                sidecar = sample_file.with_suffix(".json")
                if sidecar.exists():
                    sidecar.unlink()
            _purge_raw_archive(sample_file, sample_uid)
        except Exception as exc:
            logger.warning("[CATALOG] purge sample file remove failed for %s: %s", sample_uid, exc)

        if target is not None:
            _write_samples_csv([r for r in rows if r.get("sample_uid") != sample_uid])
        db_delete_sample(sample_uid)

        # Purging a sample removes a single .npz FILE from Drive. Route through
        # delete_gdrive_files_task (-> gdrive_client.delete_file), which handles a
        # relative file path, a Drive URL, a gdrive:// ref, or a file ID. The old
        # delete_gdrive_paths_task only resolved FOLDERS, so the file ref never
        # matched and the .npz was orphaned on Drive after every purge.
        drive_ref = str(source.get("storage_key") or "").strip()
        if not drive_ref:
            storage_url = str(source.get("storage_url") or "").strip()
            if storage_url.startswith(("gdrive://", "https://drive.google.com")):
                drive_ref = storage_url
        if drive_ref:
            try:
                from app.export_tasks import delete_gdrive_files_task

                delete_gdrive_files_task.delay(refs=[drive_ref])
            except Exception as exc:
                logger.warning("[CATALOG] purge sample Drive delete dispatch failed for %s: %s", sample_uid, exc)

        _sync_drive_and_sheets_versioned_tables(None, None)
        slog.log_operation(
            OperationType.SAMPLE_DELETE, OperationStatus.SUCCESS,
            {"sample_uid": sample_uid, "purged": True}, duration_ms=slog.end_operation(op_id),
        )
        return {"purged": True, "sample_uid": sample_uid}


def sync_delete_sample(sample_uid: str, *, tenant_id: str) -> Dict[str, Any]:
    """Hai lượt đọc, hai vai trò — xem `sync_soft_delete_sample`."""
    ensure_tables()
    _doi_pham_vi(tenant_id)
    scope = normalize_tenant_id(tenant_id)
    op_id = f"sample_delete_{sample_uid}"
    slog.start_operation(op_id)

    with _catalog_lock():
        # THẨM QUYỀN theo phạm vi; `rows` toàn cục chỉ để ghi lại cả tệp.
        rows = _load_all_samples_unscoped()
        target_row = None
        for row in list_samples(scope):
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
            _purge_raw_archive(sample_file, sample_uid)

            remaining_rows = [row for row in rows if row.get("sample_uid") != sample_uid]
            _write_samples_csv(remaining_rows)
            db_delete_sample(sample_uid)

            from app.storage.catalog_mirror import mirror_samples_to_gdrive_and_sheets

            mirror_samples_to_gdrive_and_sheets(SAMPLES_CSV)

            drive_ref = str(target_row.get("storage_key") or "").strip()
            if not drive_ref:
                storage_url = str(target_row.get("storage_url") or "").strip()
                if storage_url.startswith(("gdrive://", "https://drive.google.com")):
                    drive_ref = storage_url
            if drive_ref:
                try:
                    get_gdrive_client().delete_file(drive_ref)
                except Exception as drive_exc:
                    logger.warning("[CATALOG][GDRIVE] sample delete mirror failed for %s: %s", sample_uid, drive_exc)

            slog.log_operation(
                OperationType.SAMPLE_DELETE,
                OperationStatus.SUCCESS,
                {"sample_uid": sample_uid, "class_uid": target_row.get("class_uid")},
                duration_ms=slog.end_operation(op_id),
            )
            return {"deleted": True, "sample_uid": sample_uid}
        except Exception as exc:
            try:
                _write_samples_csv(rows)
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
