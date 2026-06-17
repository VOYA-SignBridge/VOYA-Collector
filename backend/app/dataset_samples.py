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
SAMPLES_DIR = DATASET_ROOT / "samples"
SAMPLES_CSV = SAMPLES_DIR / "samples.csv"

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
]


def now_str() -> str:
    return datetime.utcnow().isoformat() + "Z"


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
        file_exists = SAMPLES_CSV.exists()
        with open(SAMPLES_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=SAMPLE_FIELDS)
            if not file_exists or os.path.getsize(SAMPLES_CSV) == 0:
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
                rows = list(csv.DictReader(f))
            
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
                    writer = csv.DictWriter(f, fieldnames=SAMPLE_FIELDS)
                    writer.writeheader()
                    writer.writerows(rows)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, SAMPLES_CSV)
        except Exception as e:
            logging.getLogger(__name__).error("[UPDATE_SAMPLE_ROW] failed: %s", e)


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
    class_meta, sequence, meta: Dict[str, Any], augment_id: int, source_type: str
) -> str:
    """Save a (T,D) sequence locally first, then mirror to Google Drive when enabled.

    Returns the local file path. If Drive upload succeeds, the Drive URL is also stored
    in the sample metadata, but the local NPZ remains the canonical on-disk artifact.
    """
    import numpy as np
    import io

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

    # Create in-memory buffer for npz
    buffer = io.BytesIO()
    np.savez_compressed(buffer, sequence=sequence.astype("float32"), meta=metadata)
    buffer.seek(0)

    class_dir = class_meta.hierarchy_path()
    class_dir.mkdir(parents=True, exist_ok=True)
    fpath = class_dir / fname
    sidecar = class_dir / f"sample_{sample_uid}.json"

    fd, tmp = tempfile.mkstemp(prefix="npztmp_", suffix=".npz", dir=str(class_dir))
    os.close(fd)
    try:
        with open(tmp, "wb") as f:
            np.savez_compressed(
                f, sequence=sequence.astype("float32"), meta=metadata
            )
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

    if use_google_drive:
        folder_name = class_meta.folder_name()
        storage_key = f"features/{class_meta.language}/{class_meta.dialect}/{folder_name}/{fname}"
        # Defer upload to Celery background task
        try:
            from app.export_tasks import upload_npz_to_gdrive_task
            upload_npz_to_gdrive_task.delay(
                sample_uid=sample_uid,
                local_path=str(fpath),
                storage_key=storage_key,
                sidecar_path=str(sidecar)
            )
            log.info("[SAVE_SEQUENCE] Google Drive upload deferred to Celery for key: %s", storage_key)
        except Exception as e:
            log.warning("[SAVE_SEQUENCE] Failed to dispatch Celery upload task: %s", e)
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
            "storage_key": storage_key if storage_url else "",
            "storage_url": storage_url or "",
            "checksum": metadata.get("checksum", ""),
            "created_at": created_at,
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
        }
        insert_sample(db_row)
    except Exception as e:
        if getattr(settings, "debug_logging", False):
            logging.getLogger(__name__).debug("[DB] insert_sample failed: %s", e)

    return result_path
