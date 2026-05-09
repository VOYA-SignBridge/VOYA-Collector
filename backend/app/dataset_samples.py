from __future__ import annotations

import os
import csv
import uuid
import logging
from typing import Dict, Any, List
from filelock import FileLock
from datetime import datetime
from app.config import settings
from app.storage.artifact_store import store_training_artifact_minio


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


def list_samples() -> List[Dict[str, str]]:
    _ensure_samples_file()
    lock = FileLock(str(SAMPLES_CSV) + ".lock")
    with lock:
        with open(SAMPLES_CSV, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))


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
    """Save a (T,D) sequence to the local dataset tree and mirror to MinIO when enabled."""
    import numpy as np
    import io

    sample_uid = uuid.uuid4().hex[:10]
    created_at = (meta or {}).get("created_at") or now_str()

    metadata = {
        "class_uid": class_meta.class_uid,
        "slug": class_meta.slug,
        "label_original": class_meta.label_original,
        "language": class_meta.language,
        "dialect": class_meta.dialect,
        "augment_id": augment_id,
        "created_at": created_at,
        **meta,
        "user_id": meta.get("user_id") or meta.get("user") or "",
    }

    metadata_for_storage = dict(metadata)
    metadata_for_storage["storage_provider"] = "local+minio" if bool(getattr(settings, "use_minio", False)) else "local"

    buffer = io.BytesIO()
    np.savez_compressed(buffer, sequence=sequence.astype("float32"), meta=metadata_for_storage)
    buffer.seek(0)

    log = logging.getLogger(__name__)
    log.info("[SAVE_SEQUENCE] Writing training artifact locally and mirroring to MinIO when enabled")
    storage_info = store_training_artifact_minio(
        buffer,
        class_meta,
        sample_uid=sample_uid,
        augment_id=augment_id,
        metadata=metadata_for_storage,
    )
    local_path = storage_info["local_path"]
    storage_url = storage_info.get("minio_url") or storage_info.get("storage_url")
    storage_key = storage_info["storage_key"]
    metadata["storage_provider"] = storage_info.get("storage_provider", "local")
    metadata["storage_url"] = storage_url
    metadata["storage_key"] = storage_key
    result_path = local_path

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
            "file_path": result_path,
            "storage_key": storage_key,
            "storage_url": storage_url,
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
            "user_id": meta.get("user_id") or meta.get("user") or None,
            "session_id": meta.get("session_id", ""),
            "fps_original": meta.get("fps_original", meta.get("fps", "")),
            "fps_processed": meta.get("fps_processed", meta.get("fps", "")),
            "seq_len": int(sequence.shape[0]),
            "augment_id": int(augment_id),
            "completeness": float(meta.get("completeness") or 0.0),
            "file_path": result_path,
            "storage_url": metadata.get("storage_url"),
            "checksum": metadata.get("checksum"),
            "created_at": created_at,
        }
        insert_sample(db_row)
    except Exception as e:
        if getattr(settings, "debug_logging", False):
            logging.getLogger(__name__).debug("[DB] insert_sample failed: %s", e)

    return result_path
