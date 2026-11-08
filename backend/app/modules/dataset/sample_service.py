"""Application workflows for dataset sample access and legacy NPZ uploads."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping

import numpy as np

from app.config import settings
from app.modules.dataset.catalog import ClassMetadata, load_labels
from app.modules.dataset.samples import list_samples, save_sequence_npz
from app.storage.gdrive_client import materialize_sample_artifacts
from app.storage.metadata_db import get_sample_owner


class SampleAccessDeniedError(Exception):
    """The authenticated user does not own the requested sample."""


class SampleNotFoundError(Exception):
    """The requested sample is absent from the sample catalogue."""


class SampleArtifactMissingError(Exception):
    """The sample exists, but its local and remote artifacts are unavailable."""


class InvalidSampleUploadError(Exception):
    """The uploaded file is not a supported dataset sample."""


class SampleLabelNotFoundError(Exception):
    """No active class matches the legacy class index."""


def ensure_sample_access(
    sample_id: str,
    current_user: Mapping[str, Any],
    *,
    owner_lookup: Callable[[str], Any] = get_sample_owner,
) -> None:
    """Allow admins or the sample owner to mutate a sample.

    Samples without ``auth_user_id`` are legacy/guest samples and remain
    admin-only, preserving the previous router behavior.
    """
    if current_user.get("is_admin"):
        return

    owner_id = owner_lookup(sample_id)
    if owner_id is None:
        raise SampleAccessDeniedError(
            "Chỉ admin mới có thể xóa mẫu không có chủ sở hữu"
        )
    if str(owner_id) != str(current_user["id"]):
        raise SampleAccessDeniedError(
            "Bạn không có quyền thực hiện thao tác này trên mẫu này"
        )


def resolve_sample_artifact(
    sample_id: str,
    *,
    sample_loader: Callable[[], Iterable[Dict[str, Any]]] = list_samples,
    materializer: Callable[[list[Dict[str, Any]], Path], list[Any]] = materialize_sample_artifacts,
    dataset_root: Path | None = None,
) -> Path:
    """Return a local artifact path, materializing its remote copy if needed."""
    match = next(
        (sample for sample in sample_loader() if sample.get("sample_uid") == sample_id),
        None,
    )
    if match is None:
        raise SampleNotFoundError("Sample not found")

    file_path = Path(match.get("file_path") or "")
    if str(file_path) and file_path.is_file():
        return file_path

    root = Path(dataset_root or settings.dataset_root)
    resolved = materializer([match], root / "cache" / "sample_downloads")
    if not resolved:
        raise SampleArtifactMissingError("Sample file missing on disk")
    return Path(resolved[0])


def _class_metadata_by_index(
    rows: Iterable[Mapping[str, Any]],
) -> Dict[int, ClassMetadata]:
    result: Dict[int, ClassMetadata] = {}
    for row in rows:
        try:
            class_idx = int(row.get("class_idx") or 0)
        except (TypeError, ValueError):
            continue
        if class_idx <= 0:
            continue
        result[class_idx] = ClassMetadata(
            class_uid=row["class_uid"],
            slug=row["slug"],
            label_original=row["label_original"],
            language=row["language"],
            dialect=row["dialect"],
            is_common_global=bool(int(row.get("is_common_global") or 0)),
            is_common_language=bool(int(row.get("is_common_language") or 0)),
            class_idx=class_idx,
        )
    return result


def save_uploaded_npz(
    *,
    class_idx: int,
    filename: str | None,
    file_object: Any,
    current_user: Mapping[str, Any],
    user: str = "",
    session_id: str = "",
    frames: int = 0,
    duration: float = 0.0,
    source: str = "video",
    label_loader: Callable[[], Iterable[Mapping[str, Any]]] = load_labels,
    saver: Callable[..., str] = save_sequence_npz,
) -> str:
    """Validate a legacy NPZ upload and persist it through canonical storage."""
    class_meta = _class_metadata_by_index(label_loader()).get(int(class_idx))
    if class_meta is None:
        raise SampleLabelNotFoundError("label not found (class_idx)")
    if not (filename or "").endswith(".npz"):
        raise InvalidSampleUploadError("Only .npz uploads are supported")

    try:
        archive = np.load(file_object, allow_pickle=False)
        sequence = archive.get("sequence")
    except Exception as exc:
        raise InvalidSampleUploadError("Invalid npz") from exc
    if sequence is None or not isinstance(sequence, np.ndarray) or sequence.ndim != 2:
        raise InvalidSampleUploadError("npz must contain 2D 'sequence'")

    return saver(
        class_meta,
        sequence.astype(np.float32),
        meta={
            "user": user or current_user.get("username", ""),
            "user_id": current_user["id"],
            "auth_user_id": current_user["id"],
            "session_id": session_id,
            "fps_original": "",
            "fps_processed": "",
            "completeness": "",
            "frames": int(frames or sequence.shape[0]),
            "duration": str(duration or ""),
            "source": source,
        },
        augment_id=0,
        source_type=source or "upload",
    )
