from __future__ import annotations

import os
import csv
import uuid
import tempfile
import logging
import time
from typing import Dict, Any, List
from pathlib import Path
from filelock import FileLock
from datetime import datetime
from app.config import settings
from app.processing.utils import atomic_write_json


DATASET_ROOT = settings.dataset_root
SAMPLES_DIR = DATASET_ROOT
# Canonical catalog file is dataset/samples.csv (repo-root layout, matches the
# historical file and the Drive mirror). A stray dataset/samples/samples.csv
# from an interim layout was merged back on 2026-07-20 and retired
# (renamed *.pre_merge_bak) — do NOT resurrect the subdirectory path.
SAMPLES_CSV = DATASET_ROOT / "samples.csv"

SAMPLE_FIELDS = [
    "sample_uid",
    "class_uid",
    "slug",
    "label_original",
    "language",
    "dialect",
    "source_type",
    "user_id",
    "session_id",
    "fps_original",
    "fps_processed",
    "seq_len",
    "augment_id",
    "completeness",
    "file_path",
    "storage_key",
    "storage_url",
    "checksum",
    "created_at",
    "left_hand_ratio",
    "right_hand_ratio",
    "both_hands_ratio",
    "jitter",
    "quality_flags",
    "signer_id",
    "collection_campaign",
    "raw_landmarks_available",
    "normalization_version",
    "preprocess_contract_version",
    "sequence_length_original",
    "quality_status",
]


def now_str() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _samples_fieldnames() -> List[str]:
    """Return samples.csv's ACTUAL header.

    The on-disk schema drifted wider than SAMPLE_FIELDS (extra DB-mirror columns
    like username/session_uid/status/updated_at/deleted_at). Writers MUST respect
    the real header, otherwise rows misalign against the header and
    csv.DictWriter raises "dict contains fields not in fieldnames". Falls back to
    SAMPLE_FIELDS when the file does not exist yet.
    """
    try:
        if SAMPLES_CSV.exists():
            with open(SAMPLES_CSV, newline="", encoding="utf-8") as f:
                header = next(csv.reader(f), None)
            if header:
                return header
    except Exception:
        pass
    return list(SAMPLE_FIELDS)


def _ensure_samples_file():
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    if not SAMPLES_CSV.exists():
        lock = FileLock(str(SAMPLES_CSV) + ".lock")
        with lock:
            if not SAMPLES_CSV.exists():
                with open(SAMPLES_CSV, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=SAMPLE_FIELDS)
                    writer.writeheader()
    else:
        pass


def append_sample_row(row: Dict[str, Any]):
    _ensure_samples_file()
    lock = FileLock(str(SAMPLES_CSV) + ".lock")
    with lock:
        file_exists = SAMPLES_CSV.exists() and os.path.getsize(SAMPLES_CSV) > 0
        # Match the real on-disk header (may be wider than SAMPLE_FIELDS);
        # extrasaction="ignore" drops keys the header lacks (e.g. session_id),
        # restval="" fills header columns the row dict doesn't provide.
        fieldnames = _samples_fieldnames() if file_exists else list(SAMPLE_FIELDS)
        with open(SAMPLES_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", restval="")
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
            f.flush()
            os.fsync(f.fileno())

    from app.storage.catalog_mirror import mirror_samples_to_gdrive_and_sheets

    mirror_samples_to_gdrive_and_sheets(SAMPLES_CSV)


def list_samples() -> List[Dict[str, str]]:
    _ensure_samples_file()
    lock = FileLock(str(SAMPLES_CSV) + ".lock")
    with lock:
        with open(SAMPLES_CSV, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))


def update_sample_row(sample_uid: str, updates: Dict[str, Any]):
    _ensure_samples_file()
    lock = FileLock(str(SAMPLES_CSV) + ".lock")
    with lock:
        try:
            with open(SAMPLES_CSV, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = list(reader.fieldnames or SAMPLE_FIELDS)
                rows = list(reader)

            updated = False
            for row in rows:
                if row.get("sample_uid") == sample_uid:
                    for k, v in updates.items():
                        if k in row:
                            row[k] = v
                    updated = True
                    break

            if updated:
                tmp_path = str(SAMPLES_CSV) + ".tmp"
                with open(tmp_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", restval="")
                    writer.writeheader()
                    writer.writerows(rows)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, SAMPLES_CSV)
        except Exception as e:
            logging.getLogger(__name__).error("[UPDATE_SAMPLE_ROW] failed: %s", e)


def update_sample_rows_bulk(updates: Dict[str, Dict[str, Any]]):
    """Apply updates to many sample rows in ONE read+write of samples.csv.

    updates: {sample_uid: {field: value, ...}, ...}

    Replaces N calls to update_sample_row() (each of which rewrote the WHOLE
    file under a lock — O(N^2) for a video that produces hundreds of npz).
    Only fields present in SAMPLE_FIELDS are applied.
    """
    if not updates:
        return
    _ensure_samples_file()
    lock = FileLock(str(SAMPLES_CSV) + ".lock")
    with lock:
        try:
            with open(SAMPLES_CSV, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = list(reader.fieldnames or SAMPLE_FIELDS)
                rows = list(reader)

            changed = False
            for row in rows:
                upd = updates.get(row.get("sample_uid", ""))
                if upd:
                    for k, v in upd.items():
                        if k in fieldnames:
                            row[k] = v
                    changed = True

            if changed:
                tmp_path = str(SAMPLES_CSV) + ".tmp"
                with open(tmp_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", restval="")
                    writer.writeheader()
                    writer.writerows(rows)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, SAMPLES_CSV)
        except Exception as e:
            logging.getLogger(__name__).error("[UPDATE_SAMPLE_ROWS_BULK] failed: %s", e)


def _db_row_to_csv_row(r: Dict[str, Any]) -> Dict[str, Any]:
    """Project a Postgres samples row into a samples.csv row. storage_key isn't a
    DB column but equals the relative file_path (features/<lang>/<dialect>/<folder>/
    sample_x.npz), so derive it from file_path."""
    fp = r.get("file_path") or ""
    return {
        "sample_uid": r.get("sample_uid") or "",
        "class_uid": r.get("class_uid") or "",
        "slug": r.get("slug") or "",
        "label_original": r.get("label_original") or "",
        "language": r.get("language") or "",
        "dialect": r.get("dialect") or "",
        "source_type": r.get("source_type") or "",
        "user_id": r.get("user_id") or "",
        "session_id": r.get("session_id") or "",
        "fps_original": r.get("fps_original") or "",
        "fps_processed": r.get("fps_processed") or "",
        "seq_len": str(r.get("seq_len") if r.get("seq_len") is not None else ""),
        "augment_id": str(r.get("augment_id") if r.get("augment_id") is not None else ""),
        "completeness": str(r.get("completeness") if r.get("completeness") is not None else ""),
        "file_path": fp,
        "storage_key": fp,
        "storage_url": r.get("storage_url") or "",
        "checksum": r.get("checksum") or "",
        "created_at": str(r.get("created_at") or ""),
    }


def reconcile_samples_csv_from_db() -> int:
    """Heal samples.csv by appending any ACTIVE Postgres sample that is missing
    from it. Postgres is authoritative, so a row can only be *lost* from the CSV
    (rare append-vs-catalog-rewrite race), never the reverse — hence APPEND-ONLY
    and idempotent. Returns the number of rows restored.

    MUST run under _catalog_lock (same lock every catalog mutation holds). A soft
    delete removes the row from samples.csv and THEN sets deleted_at in the DB; a
    reconcile that read "DB active" in that gap would resurrect the just-trashed
    sample (or leave a CSV orphan after a purge). Holding the catalog lock — and
    reading the DB only after acquiring it — makes reconcile see a settled state,
    so it never re-adds a row a catalog op is deleting. Same lock-acquire order as
    catalog ops (catalog lock, then the samples file lock) → no deadlock."""
    _ensure_samples_file()

    from filelock import Timeout
    from app.catalog_sync import _catalog_lock

    try:
        # Skip this run (not fail) if a catalog op is busy — the beat retries soon.
        with _catalog_lock().acquire(timeout=30):
            try:
                from app.storage.metadata_db import list_active_samples

                db_rows = list_active_samples()
            except Exception as e:
                logging.getLogger(__name__).warning("[RECONCILE] DB read failed: %s", e)
                return 0
            if not db_rows:
                return 0

            lock = FileLock(str(SAMPLES_CSV) + ".lock")
            with lock:
                with open(SAMPLES_CSV, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    fieldnames = list(reader.fieldnames or SAMPLE_FIELDS)
                    existing = {(row.get("sample_uid") or "").strip() for row in reader}

                missing = [r for r in db_rows if (r.get("sample_uid") or "") not in existing]
                if not missing:
                    return 0

                with open(SAMPLES_CSV, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", restval="")
                    for r in missing:
                        writer.writerow(_db_row_to_csv_row(r))
                    f.flush()
                    os.fsync(f.fileno())

            logging.getLogger(__name__).warning(
                "[RECONCILE] restored %d sample row(s) from DB into samples.csv", len(missing)
            )
            return len(missing)
    except Timeout:
        logging.getLogger(__name__).info("[RECONCILE] skipped: catalog busy")
        return 0


def count_samples_for_class(class_uid: str) -> int:
    """Return number of samples for a class_uid based on samples.csv.

    This is the source of truth for enforcing a global per-class cap (e.g. MAX_SAMPLES_PER_CLASS).
    """
    if not class_uid:
        return 0
    _ensure_samples_file()
    lock = FileLock(str(SAMPLES_CSV) + ".lock")
    with lock:
        try:
            with open(SAMPLES_CSV, newline="", encoding="utf-8") as f:
                return sum(
                    1 for row in csv.DictReader(f) if row.get("class_uid") == class_uid
                )
        except FileNotFoundError:
            return 0


def save_sequence_npz(
    class_meta, sequence, meta: Dict[str, Any], augment_id: int, source_type: str,
    upload_collector: "list | None" = None,
    raw_sequence=None,
    frame_valid_mask=None,
    left_hand_valid_mask=None,
    right_hand_valid_mask=None,
) -> str:
    """Save a (T,D) sequence locally first, then mirror to Google Drive when enabled.

    Returns the local file path. If Drive upload succeeds, the Drive URL is also stored
    in the sample metadata, but the local NPZ remains the canonical on-disk artifact.

    upload_collector: when provided (a list), the Drive upload is NOT dispatched
    per-file. Instead the upload descriptor is appended to this list so the caller
    (e.g. the video pipeline generating hundreds of npz) can dispatch ONE batch
    task — avoiding one Celery task + one GDrive session per file. When None
    (default, e.g. camera capture = 1 file), a single upload task is dispatched
    immediately as before.

    Preprocess contract v2 (optional, backward compatible): when raw_sequence
    and the masks are provided, the npz additionally stores
      landmarks_raw          float32 [T_original, 126]  (BEFORE wrist centering/scaling)
      landmarks_normalized   float32 [60, 126]          (same array as legacy 'sequence')
      frame_valid_mask       bool    [60]
      left_hand_valid_mask   bool    [60]
      right_hand_valid_mask  bool    [60]
    The legacy 'sequence' key is ALWAYS written so existing loaders
    (dataset_loader.py feature_key_priority) keep working unchanged. Legacy
    samples without raw landmarks are marked raw_landmarks_available=false —
    raw data is never synthesized from normalized data.
    """
    import numpy as np

    log = logging.getLogger(__name__)

    sample_uid = uuid.uuid4().hex[:10]
    created_at = (meta or {}).get("created_at") or now_str()
    fname = f"sample_{sample_uid}.npz"

    metadata = {
        "class_uid": class_meta.class_uid,
        "slug": class_meta.slug,
        "label_original": class_meta.label_original,
        "language": class_meta.language,
        "dialect": class_meta.dialect,
        "augment_id": augment_id,
        "created_at": created_at,
        **meta,
    }

    class_dir = class_meta.hierarchy_path()
    class_dir.mkdir(parents=True, exist_ok=True)
    fpath = class_dir / fname
    sidecar = class_dir / f"sample_{sample_uid}.json"

    # Preprocess contract v2: raw + masks alongside the legacy 'sequence' key.
    raw_available = raw_sequence is not None
    metadata.setdefault("raw_landmarks_available", bool(raw_available))
    # Stamped by the WRITER (not the caller) so it always describes what was
    # actually put in the archive. scripts/validate_pilot_samples.py gates new
    # campaigns on this; the checkpoint contract records the same token.
    metadata.setdefault(
        "storage_contract_version",
        "npz_v2" if raw_available else "npz_v1_legacy",
    )
    npz_arrays: Dict[str, Any] = {
        "sequence": sequence.astype("float32"),          # legacy key (loaders)
        "landmarks_normalized": sequence.astype("float32"),
        "meta": metadata,
    }
    if raw_available:
        npz_arrays["landmarks_raw"] = np.asarray(raw_sequence, dtype=np.float32)
    if frame_valid_mask is not None:
        npz_arrays["frame_valid_mask"] = np.asarray(frame_valid_mask, dtype=bool)
    if left_hand_valid_mask is not None:
        npz_arrays["left_hand_valid_mask"] = np.asarray(left_hand_valid_mask, dtype=bool)
    if right_hand_valid_mask is not None:
        npz_arrays["right_hand_valid_mask"] = np.asarray(right_hand_valid_mask, dtype=bool)

    fd, tmp = tempfile.mkstemp(prefix="npztmp_", suffix=".npz", dir=str(class_dir))
    os.close(fd)
    try:
        with open(tmp, "wb") as f:
            np.savez_compressed(f, **npz_arrays)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, fpath)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except:
                pass

    try:
        metadata["storage_provider"] = "local"
        atomic_write_json(sidecar, metadata, indent=2)
    except Exception as e:
        logging.getLogger(__name__).warning("[SIDECAR] write failed: %s", e)

    storage_url = None
    storage_key = None
    use_google_drive = settings.use_google_drive

    # Single-mode (e.g. camera) Drive upload is DISPATCHED LATER — only AFTER the
    # samples.csv + Postgres rows exist. Its callback fills storage_url via
    # update_sample_row / update_sample_gdrive_url keyed by sample_uid; dispatched
    # here (before the rows were written) a fast upload could run its write-back
    # first and silently find nothing → row left with empty storage_url and
    # gdrive_synced=false. Batch mode is already safe: the caller dispatches the
    # collected items only after the whole loop has written every row.
    pending_single_upload = None
    if use_google_drive:
        folder_name = class_meta.folder_name()
        storage_key = f"features/{class_meta.language}/{class_meta.dialect}/{folder_name}/{fname}"
        upload_item = {
            "sample_uid": sample_uid,
            "local_path": str(fpath),
            "storage_key": storage_key,
            "sidecar_path": str(sidecar),
        }
        if upload_collector is not None:
            upload_collector.append(upload_item)
        else:
            pending_single_upload = upload_item
    else:
        log.info("[SAVE_SEQUENCE] Google Drive not enabled; keeping local copy only")

    result_path = str(fpath)

    # Append sample record
    try:
        expected_T = int(getattr(settings, "seq_len", 60))
        expected_D = int(getattr(settings, "feature_dim", 126))
        if int(sequence.shape[0]) != expected_T or int(sequence.shape[1]) != expected_D:
            logging.getLogger(__name__).warning(
                "[SHAPE] unexpected sequence shape=%s (expected=%sx%s)",
                tuple(sequence.shape),
                expected_T,
                expected_D,
            )
    except Exception:
        pass

    # Compute relative path for storage (portable across machines)
    try:
        relative_path = str(Path(result_path).relative_to(DATASET_ROOT))
    except ValueError:
        relative_path = result_path  # fallback: keep absolute if outside DATASET_ROOT

    append_sample_row(
        {
            "sample_uid": sample_uid,
            "class_uid": class_meta.class_uid,
            "slug": class_meta.slug,
            "label_original": class_meta.label_original,
            "language": class_meta.language,
            "dialect": class_meta.dialect,
            "source_type": source_type,
            "user_id": meta.get("user_id") or meta.get("user", ""),
            "session_id": meta.get("session_id", ""),
            "fps_original": meta.get("fps_original", meta.get("fps", "")),
            "fps_processed": meta.get("fps_processed", meta.get("fps", "")),
            "seq_len": str(sequence.shape[0]),
            "augment_id": str(augment_id),
            "completeness": str(meta.get("completeness", "")),
            "file_path": relative_path,
            # storage_url is always None here (Drive upload is deferred to Celery),
            # so the old `if storage_url` guard dropped the key entirely. Persist the
            # computed storage_key immediately; the async task fills storage_url later.
            "storage_key": storage_key or "",
            "storage_url": storage_url or "",
            "checksum": metadata.get("checksum", ""),
            "created_at": created_at,
            "left_hand_ratio": str(meta.get("left_hand_ratio", "")),
            "right_hand_ratio": str(meta.get("right_hand_ratio", "")),
            "both_hands_ratio": str(meta.get("both_hands_ratio", "")),
            "jitter": str(meta.get("jitter", "")),
            "quality_flags": str(meta.get("quality_flags", "") or ""),
            "signer_id": str(meta.get("signer_id", "") or ""),
            "collection_campaign": str(meta.get("collection_campaign", "") or ""),
            "raw_landmarks_available": "1" if metadata.get("raw_landmarks_available") else "0",
            "normalization_version": str(meta.get("normalization_version", "") or ""),
            "preprocess_contract_version": str(meta.get("preprocess_contract_version", "") or ""),
            "sequence_length_original": str(meta.get("sequence_length_original", "") or ""),
            "quality_status": str(meta.get("quality_status", "") or ""),
        }
    )

    # Also persist metadata to Postgres if configured
    try:
        from app.storage.metadata_db import insert_sample

        db_row = {
            "sample_uid": sample_uid,
            "class_uid": class_meta.class_uid,
            "slug": class_meta.slug,
            "label_original": class_meta.label_original,
            "language": class_meta.language,
            "dialect": class_meta.dialect,
            "source_type": source_type,
            "user_id": meta.get("user_id") or meta.get("user", ""),
            "auth_user_id": meta.get("auth_user_id") or None,
            "session_id": meta.get("session_id", ""),
            "fps_original": meta.get("fps_original", meta.get("fps", "")),
            "fps_processed": meta.get("fps_processed", meta.get("fps", "")),
            "seq_len": int(sequence.shape[0]),
            "augment_id": int(augment_id),
            "completeness": float(meta.get("completeness") or 0.0),
            "file_path": relative_path,
            "storage_url": metadata.get("storage_url", ""),
            "checksum": metadata.get("checksum", ""),
            "created_at": created_at,
            "gdrive_synced": not use_google_drive,
            "left_hand_ratio": meta.get("left_hand_ratio"),
            "right_hand_ratio": meta.get("right_hand_ratio"),
            "both_hands_ratio": meta.get("both_hands_ratio"),
            "jitter": meta.get("jitter"),
            "quality_flags": meta.get("quality_flags") or None,
            "signer_id": meta.get("signer_id"),
            "collection_campaign": meta.get("collection_campaign"),
            "raw_landmarks_available": metadata.get("raw_landmarks_available"),
            "normalization_version": meta.get("normalization_version"),
            "preprocess_contract_version": meta.get("preprocess_contract_version"),
            "sequence_length_original": meta.get("sequence_length_original"),
            "quality_status": meta.get("quality_status"),
        }
        insert_sample(db_row)
    except Exception as e:
        # Previously logged only in debug mode — a sample could land in
        # samples.csv but never in Postgres and go unnoticed. Always warn.
        logging.getLogger(__name__).warning("[DB] insert_sample failed for %s: %s", sample_uid, e)

    # The row now exists in samples.csv + Postgres, so the single-file Drive
    # upload can safely run: its storage_url write-back will find the sample.
    if pending_single_upload is not None:
        try:
            from app.export_tasks import upload_npz_to_gdrive_task

            upload_npz_to_gdrive_task.delay(**pending_single_upload)
            log.info(
                "[SAVE_SEQUENCE] Google Drive upload deferred to Celery for key: %s",
                pending_single_upload["storage_key"],
            )
        except Exception as e:
            log.warning("[SAVE_SEQUENCE] Failed to dispatch Celery upload task: %s", e)

    return result_path
