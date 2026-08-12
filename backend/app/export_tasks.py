"""Celery periodic tasks for mirroring catalog data to Google Sheets.

Design:
    - Labels and samples are written to local CSV + Postgres immediately during
      upload / edit / delete (see catalog_sync.py). The CSVs are the source of
      truth for what the sheets should contain.
    - Both `export_labels_to_sheets()` and `export_samples_to_sheets()` do a
      FULL REPLACE of their sheet from the current CSV (clear + write), so
      deletes and renames propagate — an append-only samples export used to
      leave stale rows on the sheet forever even though the CSV/DB were correct.
    - A content hash guards the (whole-sheet) rewrite so the 30s beat only calls
      the Sheets API when the CSV actually changed.
    - If Sheets/Drive is unreachable the task retries; the local CSV + Postgres
      remain the authoritative copy, so no data is lost.

Scale note:
    Google Sheets limit is 10,000,000 cells (~500k rows at 19 cols). Full
    replace is fine well within that; a dataset that large would need a
    different (paginated / multi-sheet) strategy.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from app.worker import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


def _rows_to_values(rows: List[Dict[str, Any]], fieldnames: List[str]) -> List[List[Any]]:
    """Convert dict rows to Sheets-compatible value matrix (no header row)."""
    result = []
    for row in rows:
        result.append([str(row.get(field) or "") for field in fieldnames])
    return result


# `platform_wide`: this reads every sample to rebuild ONE shared spreadsheet.
# It is dispatched from inside catalog mutations — that is, from a tenant
# request — so without this flag the tenant header would scope the read and the
# export would quietly publish a sheet missing every other tenant's rows. See
# app/worker.py:setup_structlog_context.
@celery_app.task(bind=True, max_retries=3, default_retry_delay=30,
                 platform_wide=True)
def export_samples_to_sheets(self):
    """Mirror samples.csv to Google Sheets via FULL REPLACE.

    Called by Celery beat every 30s and on every catalog mutation.

    Previously this only APPENDED newly-uploaded (unsynced) rows and never
    cleared the sheet, so deleting or renaming a sample/class left stale rows on
    the sheet forever — the local samples.csv and Postgres were corrected, only
    the sheet drifted. A full replace (same approach as labels) keeps the sheet
    an exact mirror of samples.csv, so deletes and renames propagate. A content
    hash guards against needlessly rewriting the sheet when nothing changed.
    """
    from app.dataset_samples import SAMPLE_FIELDS, SAMPLES_CSV, list_samples

    try:
        spreadsheet_id = str(getattr(settings, "google_sheets_samples_spreadsheet_id", "")).strip()
        sheet_gid = int(getattr(settings, "google_sheets_samples_sheet_gid", 0) or 0)

        if not spreadsheet_id or not sheet_gid:
            logger.debug("[EXPORT] Samples Sheets sync skipped: spreadsheet not configured")
            return {"status": "skipped", "reason": "not_configured"}

        # Active rows from samples.csv (authoritative, correct storage_key) PLUS
        # every soft-deleted sample from Postgres, each carrying a deleted_at
        # marker. Sorting active+deleted together by a STABLE key (created_at,
        # sample_uid) keeps a soft-deleted row IN PLACE (just marked) instead of
        # removing it and shifting every row below it up — which made a fixed
        # sheet row appear to change its label ("đổi tên").
        from app.storage.metadata_db import list_all_deleted_samples

        active = list_samples()
        seen = {(r.get("sample_uid") or "") for r in active}
        merged: List[Dict[str, Any]] = []
        for r in active:
            rr = dict(r)
            rr["deleted_at"] = ""  # active row: marker empty
            merged.append(rr)
        try:
            for r in list_all_deleted_samples():
                if (r.get("sample_uid") or "") in seen:
                    continue
                merged.append(r)
        except Exception as exc:  # DB unreachable: fall back to active-only
            logger.warning("[EXPORT] deleted-samples marker load failed: %s", exc)
        merged.sort(key=lambda r: (str(r.get("created_at") or ""), str(r.get("sample_uid") or "")))

        # Full matrix: header (+ deleted_at) + every row, in the sheet's column order.
        header = list(SAMPLE_FIELDS) + ["deleted_at"]
        values = [header]
        for row in merged:
            values.append([str(row.get(field, "") or "") for field in header])

        # Skip the (whole-sheet) rewrite when the matrix is unchanged since the
        # last successful sync — keeps the 30s beat from churning the API.
        import hashlib
        import json as _json
        digest = hashlib.sha256(
            _json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        guard = SAMPLES_CSV.parent / ".samples_sheet.synced"
        try:
            if guard.exists() and guard.read_text(encoding="utf-8").strip() == digest:
                logger.debug("[EXPORT] Samples sheet already up-to-date; skipping rewrite")
                return {"status": "skipped", "reason": "unchanged", "rows": len(merged)}
        except Exception:
            pass

        from app.storage.gdrive_client import get_gdrive_client
        client = get_gdrive_client()
        client.replace_sheet_values(spreadsheet_id, sheet_gid, values)

        try:
            guard.write_text(digest, encoding="utf-8")
        except Exception:
            pass

        logger.info("[EXPORT] ✅ Mirrored %d samples to Sheets (%d active + %d deleted)",
                    len(merged), len(active), len(merged) - len(active))
        return {"status": "success", "synced_count": len(merged)}

    except Exception as exc:
        logger.error("[EXPORT] Samples Sheets export failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60,
                 platform_wide=True)  # one shared sheet — see export_samples_to_sheets
def export_labels_to_sheets(self):
    """Batch sync labels.csv to Google Sheets.

    Labels change less frequently than samples, so this runs less often.
    For labels, we use the full replace approach since the dataset typically
    has < 10K labels and the full state needs to be accurate.
    """
    from app.storage.metadata_db import ensure_tables

    try:
        ensure_tables()

        spreadsheet_id = str(getattr(settings, "google_sheets_labels_spreadsheet_id", "")).strip()
        sheet_gid = int(getattr(settings, "google_sheets_labels_sheet_gid", 0) or 0)

        if not spreadsheet_id or not sheet_gid:
            logger.debug("[EXPORT] Labels Sheets sync skipped: spreadsheet not configured")
            return {"status": "skipped", "reason": "not_configured"}

        # Labels are small enough to do full replace safely
        from app.dataset_manager import load_labels, LABEL_FIELDS

        # Active labels from labels.csv PLUS soft-deleted classes from Postgres,
        # each carrying a deleted_at marker, ordered by class_idx (stable). A
        # soft-deleted label therefore stays on the sheet WITH a marker instead
        # of vanishing and shifting every row below it up by one.
        from app.storage.metadata_db import list_deleted_classes

        active = load_labels()
        seen = {(r.get("class_uid") or "") for r in active}
        merged: List[Dict[str, Any]] = []
        for r in active:
            rr = dict(r)
            rr.setdefault("deleted_at", "")
            merged.append(rr)
        try:
            for r in list_deleted_classes():
                if (r.get("class_uid") or "") in seen:
                    continue
                row = dict(r)
                # DB stores is_common_* as booleans; match the CSV "0"/"1" form.
                row["is_common_global"] = str(int(bool(r.get("is_common_global"))))
                row["is_common_language"] = str(int(bool(r.get("is_common_language"))))
                merged.append(row)
        except Exception as exc:  # DB unreachable: fall back to active-only
            logger.warning("[EXPORT] deleted-classes marker load failed: %s", exc)

        if not merged:
            logger.debug("[EXPORT] No labels to export")
            return {"status": "skipped", "reason": "no_labels"}

        def _idx(r: Dict[str, Any]) -> int:
            try:
                return int(r.get("class_idx") or 0)
            except (TypeError, ValueError):
                return 0
        merged.sort(key=lambda r: (_idx(r), str(r.get("class_uid") or "")))

        # Build full matrix with header (+ deleted_at marker column).
        header = list(LABEL_FIELDS) + ["deleted_at"]
        values = [header]
        for row in merged:
            values.append([str(row.get(field, "") or "") for field in header])

        from app.storage.gdrive_client import get_gdrive_client
        client = get_gdrive_client()
        client.replace_sheet_values(spreadsheet_id, sheet_gid, values)

        logger.info("[EXPORT] ✅ Synced %d labels to Sheets (%d active + %d deleted)",
                    len(merged), len(active), len(merged) - len(active))
        return {"status": "success", "synced_count": len(merged)}

    except Exception as exc:
        logger.error("[EXPORT] Labels Sheets export failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60,
                 platform_wide=True)  # mirrors the whole catalogue, not one tenant's
def mirror_catalog_csvs_to_drive(self):
    """Periodically mirror local catalog CSV snapshots to Google Drive.

    Why: the per-append Drive mirror was removed (it hammered the API on every
    sample), which silently left the Drive copies of samples.csv / labels.csv /
    raw_uploads.csv frozen. This batch task refreshes them on a beat schedule.
    replace_existing=True updates each file IN PLACE, so existing share links
    keep pointing at fresh content.
    """
    from app.storage.catalog_mirror import _mirror_csv_to_gdrive_sync
    from app.dataset_samples import SAMPLES_CSV
    from app.dataset_manager import MASTER_LABELS
    from app.raw_uploads import RAW_UPLOADS_CSV

    if not getattr(settings, "use_google_drive", False):
        return {"status": "skipped", "reason": "gdrive_disabled"}

    results = {}
    for local_path, remote_name in [
        (SAMPLES_CSV, "samples.csv"),
        (MASTER_LABELS, "labels.csv"),
        (RAW_UPLOADS_CSV, "raw_uploads.csv"),
    ]:
        try:
            _mirror_csv_to_gdrive_sync(local_path, remote_name)
            results[remote_name] = "ok"
        except Exception as exc:  # per-file: one failure must not block the rest
            logger.warning("[CSV_MIRROR] %s failed: %s", remote_name, exc)
            results[remote_name] = f"failed: {exc}"

    logger.info("[CSV_MIRROR] snapshot mirror done: %s", results)
    return {"status": "done", "results": results}


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30,
                 platform_wide=True)  # integrity sweep over every tenant's rows
def reconcile_samples_csv_task(self):
    """Periodic safety-net: re-add any ACTIVE Postgres sample missing from
    samples.csv (lost to a rare append-vs-catalog-rewrite race). Append-only and
    idempotent — Postgres is authoritative, so nothing is ever removed."""
    try:
        from app.dataset_samples import reconcile_samples_csv_from_db

        restored = reconcile_samples_csv_from_db()
        if restored:
            logger.warning("[RECONCILE] samples.csv healed: %d row(s) restored", restored)
        return {"status": "done", "restored": restored}
    except Exception as exc:
        logger.warning("[RECONCILE] task failed: %s", exc)
        return {"status": "error", "error": str(exc)}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def delete_gdrive_paths_task(self, rel_paths: list):
    """Delete Drive folders/files by dataset-relative path (async cleanup).

    Catalog class delete now removes local files + DB rows synchronously and
    defers Drive cleanup to this task, so the HTTP request never blocks on — or
    fails because of — Drive I/O. Best-effort: a Drive delete failure is logged
    and retried, never rolled back into the (already committed) local delete.
    """
    if not getattr(settings, "use_google_drive", False):
        return {"status": "skipped", "reason": "gdrive_disabled"}

    from app.storage.gdrive_client import get_gdrive_client

    client = get_gdrive_client()
    results = {}
    failures = 0
    for rel in rel_paths or []:
        if not rel:
            continue
        try:
            client.delete_path(rel)
            results[rel] = "ok"
        except Exception as exc:  # per-path: one failure must not block the rest
            logger.warning("[GDRIVE_DELETE] %s failed: %s", rel, exc)
            results[rel] = f"failed: {exc}"
            failures += 1
    logger.info("[GDRIVE_DELETE] done: %s", results)
    # Retry the whole task if any path failed (transient Drive/network error).
    # delete_path is idempotent — an already-deleted path resolves to nothing and
    # returns False, so re-running the successful ones on retry is harmless.
    if failures and self.request.retries < self.max_retries:
        raise self.retry(exc=RuntimeError(f"{failures} Drive folder delete(s) failed"))
    return {"status": "done", "results": results}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def delete_gdrive_files_task(self, refs: list):
    """Delete individual Drive FILES by storage_key (dataset-relative file path),
    Drive URL, gdrive:// ref, or file ID.

    Used when purging a single sample. `delete_gdrive_paths_task` routes through
    `delete_path`, which only resolves FOLDERS — so a *file* ref (e.g.
    ``features/vn/common/class_x_ab12cd34/sample_ab12.npz`` or ``gdrive://<id>``)
    never matched and the .npz was left on Drive forever. `delete_file` resolves
    the parent folder + filename (or the ID/URL) and deletes the actual file.
    """
    if not getattr(settings, "use_google_drive", False):
        return {"status": "skipped", "reason": "gdrive_disabled"}

    from app.storage.gdrive_client import get_gdrive_client

    client = get_gdrive_client()
    results = {}
    failures = 0
    for ref in refs or []:
        if not ref:
            continue
        try:
            ok = client.delete_file(ref)
            results[ref] = "ok" if ok else "not_found"
        except Exception as exc:  # per-file: one failure must not block the rest
            logger.warning("[GDRIVE_FILE_DELETE] %s failed: %s", ref, exc)
            results[ref] = f"failed: {exc}"
            failures += 1
    logger.info("[GDRIVE_FILE_DELETE] done: %s", results)
    if failures and self.request.retries < self.max_retries:
        raise self.retry(exc=RuntimeError(f"{failures} Drive file delete(s) failed"))
    return {"status": "done", "results": results}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def move_gdrive_paths_task(self, pairs: list):
    """Move Drive folders by (old_rel, new_rel) path pairs (async, after a
    local class rename). Tolerant of a missing source folder — many classes
    have features on Drive but never uploaded raw videos — so a missing folder
    is skipped, never raised. Best-effort: failures are logged, not rolled back
    into the committed local rename."""
    if not getattr(settings, "use_google_drive", False):
        return {"status": "skipped", "reason": "gdrive_disabled"}

    from app.storage.gdrive_client import get_gdrive_client

    client = get_gdrive_client()
    results = {}
    failures = 0
    for pair in pairs or []:
        try:
            old_rel, new_rel = pair[0], pair[1]
        except (TypeError, IndexError):
            continue
        key = f"{old_rel} -> {new_rel}"
        try:
            client.move_folder_path(old_rel, new_rel)
            results[key] = "ok"
        except FileNotFoundError:
            results[key] = "skipped (source missing)"
        except Exception as exc:
            logger.warning("[GDRIVE_MOVE] %s failed: %s", key, exc)
            results[key] = f"failed: {exc}"
            failures += 1
    logger.info("[GDRIVE_MOVE] done: %s", results)
    # Retry on a transient failure so a one-off Drive/network error doesn't
    # silently drop the rename. move_folder_path is idempotent on retry: an
    # already-moved pair now has a missing source -> FileNotFoundError -> skipped.
    if failures and self.request.retries < self.max_retries:
        raise self.retry(exc=RuntimeError(f"{failures} Drive folder move(s) failed"))
    return {"status": "done", "results": results}


@celery_app.task(bind=True, max_retries=5, default_retry_delay=15)
def upload_raw_video_to_gdrive_task(
    self,
    upload_uid: str,
    local_path: str,
    storage_key: str,
    content_type: str = "application/octet-stream",
):
    """Mirror a raw uploaded video to Google Drive in the background.

    Dispatched by /upload/video after the local save + metadata write.
    Keeps the HTTP request fast: the user never waits for the Drive transfer.
    On success, updates uploads.csv and Postgres so the record points at
    the Drive mirror instead of only the local path.
    """
    from app.storage.gdrive_client import upload_to_gdrive
    from app.storage.metadata_db import update_raw_upload_gdrive_url
    from app.raw_uploads import update_raw_upload_row
    import os

    try:
        if not os.path.exists(local_path):
            logger.warning("[GDRIVE_RAW_VIDEO] Local file not found: %s", local_path)
            return {"status": "skipped", "reason": "file_not_found"}

        logger.info("[GDRIVE_RAW_VIDEO] Uploading %s to GDrive key %s", local_path, storage_key)
        storage_url = upload_to_gdrive(local_path, storage_key, content_type=content_type)
        if not storage_url:
            raise RuntimeError("upload_to_gdrive returned None")

        # Point the metadata records at the Drive mirror (best-effort each)
        try:
            update_raw_upload_row(upload_uid, {"storage_url": storage_url})
        except Exception as e:
            logger.warning("[GDRIVE_RAW_VIDEO] CSV update failed for %s: %s", upload_uid, e)
        try:
            update_raw_upload_gdrive_url(upload_uid, storage_url)
        except Exception as e:
            logger.warning("[GDRIVE_RAW_VIDEO] DB update failed for %s: %s", upload_uid, e)

        logger.info("[GDRIVE_RAW_VIDEO] Mirror complete: %s -> %s", upload_uid, storage_url)
        return {"status": "success", "storage_url": storage_url}

    except Exception as exc:
        logger.error("[GDRIVE_RAW_VIDEO] Upload failed for %s: %s", upload_uid, exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=5, default_retry_delay=10)
def upload_npz_to_gdrive_task(self, sample_uid: str, local_path: str, storage_key: str, sidecar_path: str):
    from app.storage.gdrive_client import upload_to_gdrive
    from app.processing.utils import atomic_write_json
    from app.storage.metadata_db import update_sample_gdrive_url
    from app.dataset_samples import update_sample_row
    import json
    import os

    try:
        if not os.path.exists(local_path):
            logger.warning("[GDRIVE_UPLOAD] Local file not found: %s", local_path)
            return {"status": "skipped", "reason": "file_not_found"}

        logger.info("[GDRIVE_UPLOAD] Uploading %s to GDrive key %s", local_path, storage_key)
        storage_url = upload_to_gdrive(local_path, storage_key)
        
        if not storage_url:
            raise RuntimeError("upload_to_gdrive returned None")

        logger.info("[GDRIVE_UPLOAD] Upload successful: %s", storage_url)

        # 1. Update sidecar JSON
        try:
            if os.path.exists(sidecar_path):
                with open(sidecar_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                metadata["storage_url"] = storage_url
                metadata["storage_key"] = storage_key
                metadata["storage_provider"] = "local+gdrive"
                atomic_write_json(sidecar_path, metadata, indent=2)
        except Exception as e:
            logger.warning("[GDRIVE_UPLOAD] Failed to update sidecar JSON: %s", e)

        # 2. Update Postgres database
        update_sample_gdrive_url(sample_uid, storage_url)

        # 3. Update samples.csv
        update_sample_row(sample_uid, {
            "storage_url": storage_url,
            "storage_key": storage_key
        })

        return {"status": "success", "storage_url": storage_url}

    except Exception as exc:
        logger.error("[GDRIVE_UPLOAD] Upload failed for %s: %s", sample_uid, exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def upload_npz_batch_to_gdrive_task(self, items: list):
    """Upload MANY npz files in one task (video pipeline batches its output here).

    Why: dispatching one task per npz meant hundreds of Celery tasks + hundreds
    of Drive sessions per video (429 risk, queue flooding). This uploads the
    whole batch reusing the singleton Drive client, then updates samples.csv
    ONCE for the batch instead of rewriting the whole file per file.

    Failed items are retried as a smaller batch (successful uploads are not
    repeated). The local npz stays canonical, so nothing is lost on failure.
    """
    from app.storage.gdrive_client import upload_to_gdrive
    from app.processing.utils import atomic_write_json
    from app.storage.metadata_db import update_sample_gdrive_url
    from app.dataset_samples import update_sample_rows_bulk
    import json
    import os

    if not items:
        return {"status": "skipped", "reason": "empty_batch"}

    csv_updates: Dict[str, Dict[str, Any]] = {}
    failed: List[Dict[str, Any]] = []
    ok = 0

    for it in items:
        sample_uid = it.get("sample_uid", "")
        local_path = it.get("local_path", "")
        storage_key = it.get("storage_key", "")
        sidecar_path = it.get("sidecar_path", "")
        try:
            if not local_path or not os.path.exists(local_path):
                logger.warning("[GDRIVE_BATCH] file not found, skipping: %s", local_path)
                continue

            storage_url = upload_to_gdrive(local_path, storage_key)
            if not storage_url:
                raise RuntimeError("upload_to_gdrive returned None")

            # sidecar (best-effort, per item)
            try:
                if sidecar_path and os.path.exists(sidecar_path):
                    with open(sidecar_path, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                    metadata["storage_url"] = storage_url
                    metadata["storage_key"] = storage_key
                    metadata["storage_provider"] = "local+gdrive"
                    atomic_write_json(sidecar_path, metadata, indent=2)
            except Exception as e:
                logger.warning("[GDRIVE_BATCH] sidecar update failed for %s: %s", sample_uid, e)

            # DB per-item (pooled connection → cheap)
            try:
                update_sample_gdrive_url(sample_uid, storage_url)
            except Exception as e:
                logger.warning("[GDRIVE_BATCH] DB update failed for %s: %s", sample_uid, e)

            csv_updates[sample_uid] = {"storage_url": storage_url, "storage_key": storage_key}
            ok += 1
        except Exception as e:
            logger.warning("[GDRIVE_BATCH] upload failed for %s: %s", sample_uid, e)
            failed.append(it)

    # ONE csv rewrite for the whole batch (T3.2)
    try:
        update_sample_rows_bulk(csv_updates)
    except Exception as e:
        logger.error("[GDRIVE_BATCH] bulk csv update failed: %s", e)

    logger.info("[GDRIVE_BATCH] done: uploaded=%d failed=%d total=%d", ok, len(failed), len(items))

    if failed and self.request.retries < self.max_retries:
        # Retry ONLY the failed items so successful uploads aren't repeated.
        raise self.retry(args=[failed], countdown=30)

    return {"status": "done", "uploaded": ok, "failed": len(failed)}
