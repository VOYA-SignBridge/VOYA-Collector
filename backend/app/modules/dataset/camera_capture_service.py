"""Camera capture conversion, quality control and dataset persistence."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Dict

import numpy as np

from app.config import settings
from app.modules.dataset.catalog import (
    get_or_register_class,
    list_classes,
    parse_hands_required,
    set_class_hands_required,
)
from app.modules.dataset.raw_uploads import now_str
from app.modules.dataset.samples import raw_archive_path, save_sequence_npz
from app.modules.saas import storage_quota
from app.modules.saas.tenant_context import require_tenant
from app.modules.saas.webhooks import emit
from app.modules.security.quota_deps import guard_storage
from app.processing.quality import (
    compute_quality_metrics,
    evaluate_quality,
    qc_threshold_snapshot,
    record_quality_attempt,
)
from app.processing.utils import (
    DEFAULT_NORMALIZATION_VERSION,
    normalize_hands_vector_126,
    normalize_sequence,
)

logger = logging.getLogger("upload.camera")


class CameraQualityRejected(ValueError):
    def __init__(self, detail: Dict[str, Any]):
        super().__init__(str(detail.get("message") or "camera sample rejected"))
        self.detail = detail


class CameraClassNotFoundError(LookupError):
    """The explicitly selected class does not belong to the request tenant."""


def _class_by_uid(class_uid: str):
    uid = str(class_uid or "").strip()
    if not uid:
        return None
    tenant_id = require_tenant()
    found = next(
        (item for item in list_classes(tenant_id=tenant_id) if item.class_uid == uid),
        None,
    )
    if found is None:
        raise CameraClassNotFoundError("Nhãn không thuộc tổ chức hiện tại")
    return found


def _bytes_written(npz_path) -> int:
    """Billable bytes written for one camera sample and its raw archive."""
    path = Path(npz_path)
    total = 0
    for artifact in (path, raw_archive_path(path), path.with_suffix(".json")):
        try:
            total += artifact.stat().st_size
        except OSError:
            continue
    return total


def _coerce_nested_values(value) -> np.ndarray:
    values: list[float] = []

    def collect(item) -> None:
        if item is None:
            return
        if isinstance(item, (int, float)):
            values.append(float(item))
        elif isinstance(item, dict):
            for key in ("x", "y", "z", "visibility"):
                if key in item:
                    try:
                        values.append(float(item.get(key) or 0.0))
                    except Exception:
                        values.append(0.0)
            for nested in item.values():
                if isinstance(nested, (list, tuple)):
                    collect(nested)
        elif isinstance(item, (list, tuple, np.ndarray)):
            for nested in item:
                collect(nested)

    collect(value)
    return np.asarray(values, dtype=np.float32)


def _flatten_landmarks(
    landmarks,
    keys: tuple[str, str] = ("left_hand", "right_hand"),
) -> np.ndarray | None:
    if landmarks is None:
        return None
    if isinstance(landmarks, (list, tuple, np.ndarray)):
        try:
            return np.asarray(landmarks, dtype=np.float32).flatten()
        except Exception:
            return _coerce_nested_values(landmarks)
    if isinstance(landmarks, dict):
        values: list[float] = []
        for key in keys:
            points = list(landmarks.get(key, []))[:21]
            points.extend([None] * (21 - len(points)))
            for point in points:
                if not isinstance(point, dict):
                    values.extend((0.0, 0.0, 0.0))
                    continue
                for coordinate in ("x", "y", "z"):
                    value = point.get(coordinate)
                    values.append(float(value) if value is not None else 0.0)
        return np.asarray(values, dtype=np.float32)
    return np.asarray(landmarks, dtype=np.float32).flatten()


def frames_to_sequence(
    frames: list,
    feature_dim: int,
    *,
    keys: tuple[str, str] = ("left_hand", "right_hand"),
) -> np.ndarray:
    """Convert accepted camera frame shapes into a fixed-width float matrix."""
    rows: list[np.ndarray] = []
    for frame in frames:
        raw = frame.get("landmarks") if isinstance(frame, dict) else None
        flattened = _flatten_landmarks(raw, keys=keys)
        if flattened is None:
            raise ValueError("frame missing landmarks")
        rows.append(flattened)

    sequence = np.zeros((len(rows), feature_dim), dtype=np.float32)
    for index, row in enumerate(rows):
        values = np.asarray(row, dtype=np.float32).flatten()
        length = min(values.size, feature_dim)
        sequence[index, :length] = values[:length]
    return sequence


def _resolve_signer(current_user: Dict[str, Any]) -> str:
    try:
        from app.modules.dataset.signers import resolve_signer_for_user

        return resolve_signer_for_user(current_user)
    except Exception as exc:
        logger.warning("[SIGNER] resolution failed: %s", exc)
        return ""


def _quality_record(
    *,
    class_meta,
    label: str,
    session_id: str,
    signer_id: str,
    status: str,
    verdict,
    metrics,
    thresholds: dict,
    sample_path: str | None = None,
) -> dict:
    record = {
        "attempt_id": uuid.uuid4().hex[:12],
        "campaign": getattr(settings, "collection_campaign", "") or "",
        "signer_id": signer_id,
        "session_id": session_id,
        "recognition_profile": class_meta.recognition_profile or "",
        "vocabulary_scope": class_meta.vocabulary_scope or "",
        "label": label,
        "status": status,
        "flags": verdict.flags,
        "metrics": metrics.as_dict(),
        "quality_config_version": thresholds["quality_config_version"],
        "quality_thresholds": thresholds,
        "source_type": "camera",
        "timestamp": now_str(),
    }
    if sample_path is not None:
        record["sample_path"] = sample_path
    return record


def capture_camera_sample(
    *,
    payload: dict,
    current_user: Dict[str, Any],
    user: str,
    label: str,
    language: str,
    dialect: str,
    session_id: str,
    class_uid: str = "",
    visibility: str = "private",
) -> Dict[str, Any]:
    """Validate, normalize, quality-check and persist one camera capture."""
    frames = payload.get("frames")
    if not frames:
        return {"success": False, "message": "Missing label or frames"}

    max_frames = int(getattr(settings, "max_camera_frames", 600))
    if max_frames > 0 and isinstance(frames, list) and len(frames) > max_frames:
        return {"success": False, "message": f"Too many frames (max {max_frames})"}

    hands_required_payload = parse_hands_required(payload.get("hands_required")) or 0
    client_quality = (
        payload.get("quality_info")
        if isinstance(payload.get("quality_info"), dict)
        else None
    )
    class_meta = _class_by_uid(class_uid)
    if class_meta is None:
        class_meta = get_or_register_class(
            label_original=label,
            language=language,
            dialect=dialect or "",
        )
    else:
        label = class_meta.label_original
        language = class_meta.language
        dialect = class_meta.dialect
    effective_hands = class_meta.hands_required or hands_required_payload
    if not class_meta.hands_required and hands_required_payload in (1, 2):
        try:
            set_class_hands_required(class_meta.class_uid, hands_required_payload)
        except Exception as exc:
            logger.warning("[QC] persisting hands_required failed: %s", exc)

    feature_dim = int(getattr(settings, "feature_dim", 126))
    try:
        sequence = frames_to_sequence(frames, feature_dim)
    except Exception as exc:
        logger.error("[LANDMARKS][ERROR] %s", exc)
        return {"success": False, "message": f"Invalid frames payload: {exc}"}

    if getattr(settings, "debug_logging", False):
        logger.debug("[LANDMARKS] built_seq shape=%s dtype=%s", sequence.shape, sequence.dtype)

    raw_sequence = sequence.astype(np.float32, copy=True)
    original_length = int(sequence.shape[0])
    world_sequence = None
    try:
        world_rows = [
            _flatten_landmarks(
                frame.get("landmarks") if isinstance(frame, dict) else None,
                keys=("left_hand_world", "right_hand_world"),
            )
            for frame in frames
        ]
        if any(
            row is not None and row.size and np.any(row != 0.0)
            for row in world_rows
        ):
            world_sequence = np.zeros((len(world_rows), feature_dim), dtype=np.float32)
            for index, row in enumerate(world_rows):
                if row is None or not row.size:
                    continue
                length = min(row.size, feature_dim)
                world_sequence[index, :length] = row[:length].astype(np.float32)
    except Exception as exc:
        logger.warning("[LANDMARKS][world] ignored malformed world landmarks: %s", exc)
        world_sequence = None
    padded, _info = normalize_sequence(
        sequence,
        expected_T=int(getattr(settings, "seq_len", 60)),
        expected_D=feature_dim,
    )
    left_valid = np.any(padded[:, :63] != 0.0, axis=1)
    right_valid = np.any(padded[:, 63:] != 0.0, axis=1)
    frame_valid = left_valid | right_valid

    metrics = compute_quality_metrics(padded, hands_required=effective_hands)
    verdict = evaluate_quality(metrics, settings)
    thresholds = qc_threshold_snapshot(settings)
    logger.info(
        "[QC] label=%s hands_required=%s completeness=%.3f L=%.3f R=%.3f "
        "both=%.3f jitter_p95=%.4f activity=%.4f flags=%s",
        label,
        effective_hands or 0,
        metrics.completeness,
        metrics.left_hand_ratio,
        metrics.right_hand_ratio,
        metrics.both_hands_ratio,
        metrics.jitter_p95,
        metrics.activity,
        verdict.flags or "-",
    )

    signer_id = _resolve_signer(current_user)
    if settings.qc_enabled and verdict.reject_code:
        record_quality_attempt(
            _quality_record(
                class_meta=class_meta,
                label=label,
                session_id=session_id,
                signer_id=signer_id,
                status="rejected",
                verdict=verdict,
                metrics=metrics,
                thresholds=thresholds,
            )
        )
        raise CameraQualityRejected(
            {
                "code": verdict.reject_code,
                "message": "Mẫu không đạt chất lượng tối thiểu, vui lòng thu lại.",
                "metrics": metrics.as_dict(),
            }
        )

    normalization_version = DEFAULT_NORMALIZATION_VERSION
    for index in range(padded.shape[0]):
        padded[index] = normalize_hands_vector_126(
            padded[index], normalization_version
        )

    metadata = {
        "user": user,
        "user_id": user,
        "auth_user_id": current_user["id"],
        "visibility": visibility,
        "signer_id": signer_id,
        "session_id": session_id,
        "collection_campaign": getattr(settings, "collection_campaign", "") or "",
        "vocabulary_scope": class_meta.vocabulary_scope or "",
        "recognition_profile": class_meta.recognition_profile or "",
        "vocabulary_group": class_meta.vocabulary_group or "",
        "semantic_label": class_meta.semantic_label or "",
        "normalization_version": normalization_version,
        "preprocess_contract_version": "v2",
        "coordinate_space": "wrist_centred_v1",
        "target_sequence_length": int(getattr(settings, "seq_len", 60)),
        "feature_dimension": feature_dim,
        "sequence_length_original": original_length,
        "quality_status": "flagged" if verdict.warning_codes else "ok",
        "fps_original": None,
        "fps_processed": None,
        "completeness": round(metrics.completeness, 4),
        "left_hand_ratio": round(metrics.left_hand_ratio, 4),
        "right_hand_ratio": round(metrics.right_hand_ratio, 4),
        "both_hands_ratio": round(metrics.both_hands_ratio, 4),
        "any_hand_ratio": round(metrics.any_hand_ratio, 4),
        "jitter": round(metrics.jitter_p95, 5),
        "jitter_p95": round(metrics.jitter_p95, 5),
        "activity": round(metrics.activity, 5),
        "quality_flags": verdict.flags,
        "quality_config_version": thresholds["quality_config_version"],
        "quality_thresholds": thresholds,
        "hands_required": effective_hands or None,
        "client_quality": client_quality,
        "created_at": now_str(),
    }
    upper_bound = int(padded.nbytes) * 2
    for array in (
        raw_sequence,
        world_sequence,
        frame_valid,
        left_valid,
        right_valid,
    ):
        if array is not None:
            upper_bound += int(np.asarray(array).nbytes)
    upper_bound += 64 * 1024

    reservation = guard_storage(current_user, nbytes=upper_bound)
    settled = False
    try:
        try:
            path = save_sequence_npz(
                class_meta,
                padded,
                meta=metadata,
                augment_id=0,
                source_type="camera",
                raw_sequence=raw_sequence,
                world_sequence=world_sequence,
                coordinate_space="wrist_centred_v1",
                frame_valid_mask=frame_valid,
                left_hand_valid_mask=left_valid,
                right_hand_valid_mask=right_valid,
            )
        except Exception as exc:
            logger.error("[UPLOAD][camera][ERROR] sample save failed: %s", exc)
            return {"success": False, "message": f"Sample upload failed: {exc}"}

        storage_quota.settle(
            reservation,
            _bytes_written(path),
            absorb_overflow=True,
        )
        settled = True
    finally:
        if not settled:
            storage_quota.release(reservation)

    record_quality_attempt(
        _quality_record(
            class_meta=class_meta,
            label=label,
            session_id=session_id,
            signer_id=signer_id,
            status="flagged" if verdict.warning_codes else "accepted",
            verdict=verdict,
            metrics=metrics,
            thresholds=thresholds,
            sample_path=path,
        )
    )
    quality = metrics.as_dict()
    quality["warnings"] = [
        {
            "code": code,
            "message": "Chất lượng mẫu thấp — mẫu đã được lưu và đánh dấu để kiểm tra.",
            "detail": {
                "completeness": round(metrics.completeness, 4),
                "jitter_p95": round(metrics.jitter_p95, 5),
                "hands_required": effective_hands or None,
            },
        }
        for code in verdict.warning_codes
    ]
    emit(
        class_meta.tenant_id,
        "sample.created",
        {
            "session_id": session_id,
            "label": label,
            "language": language,
            "dialect": dialect,
            "class_uid": class_meta.class_uid,
            "source_type": "camera",
        },
    )
    return {
        "success": True,
        "id": session_id,
        "paths": [path],
        "total_samples": 1,
        "message": "saved original sample",
        "language": language,
        "dialect": dialect,
        "quality": quality,
    }
