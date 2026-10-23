"""Validation and durable submission of training jobs."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

from app.modules.training.schemas import SplitProvenance, TrainingConfig, TrainingJob

logger = logging.getLogger(__name__)


class SubmissionValidationError(ValueError):
    pass


class QueueUnavailableError(RuntimeError):
    pass


def eligible_class_counts(dialects: list[str], minimum_samples: int) -> dict[str, int]:
    """Count trainable classes per dialect in the ambient tenant scope."""
    if not dialects or minimum_samples <= 0:
        return {}
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        "SELECT dialect, count(*) AS n FROM ("
        "  SELECT c.dialect, c.class_uid, "
        "         count(s.sample_uid) FILTER (WHERE s.deleted_at IS NULL) AS m "
        "    FROM classes c "
        "    LEFT JOIN samples s ON s.class_uid = c.class_uid "
        "   WHERE c.deleted_at IS NULL AND c.dialect = ANY(%s) "
        "   GROUP BY c.dialect, c.class_uid"
        ") t WHERE m >= %s GROUP BY dialect",
        (list(dialects), minimum_samples),
    )
    return {
        str(row.get("dialect") or ""): int(row.get("n") or 0)
        for row in rows
    }


async def submit_training_job(
    config: TrainingConfig,
    *,
    auth_user_id: Optional[str],
    username: Optional[str],
    tenant_id: str,
    jobs: dict[str, dict[str, Any]],
    research_splits: Callable[[], list[dict[str, Any]]],
    trainable_dialects: Callable[[], dict[str, int]],
    resolve_provenance: Callable[..., SplitProvenance],
    persist_job: Callable[..., Awaitable[None]],
) -> TrainingJob:
    """Validate, persist and enqueue one job in that exact order."""
    if config.run_purpose == "research":
        if not config.split_version:
            raise SubmissionValidationError(
                "Chế độ nghiên cứu cần chọn một split đã versioned."
            )
        available = {item["split_version"]: item for item in research_splits()}
        chosen = available.get(config.split_version)
        if not chosen:
            raise SubmissionValidationError(
                f"Split '{config.split_version}' không dùng được cho nghiên cứu "
                "(không tồn tại, thiếu checksum manifest, hoặc valid_for_research=false). "
                f"Đang dùng được: {sorted(available) or 'chưa có'}."
            )
        config.dataset_version = chosen["dataset_version"]
        config.recognition_profile = chosen["recognition_profile"]

    selected_dialects = [] if config.run_purpose == "research" else list(config.dialects or [])
    if selected_dialects:
        trainable = trainable_dialects()
        empty = [dialect for dialect in selected_dialects if trainable.get(dialect, 0) < 2]
        if empty:
            available = sorted(dialect for dialect, count in trainable.items() if count >= 2)
            raise SubmissionValidationError(
                "Các phương ngữ đã chọn không đủ dữ liệu để huấn luyện "
                f"(cần ≥2 lớp có mẫu trong tập chia): {empty}. "
                f"Phương ngữ đang huấn luyện được: {available or 'chưa có'}. "
                "Nếu bạn vừa thu dữ liệu mới, hãy chia lại tập "
                "(processed/splits/make_splits.py) trước khi huấn luyện."
            )

    split_provenance: Optional[SplitProvenance] = None
    if config.run_purpose != "research":
        split_provenance = resolve_provenance(config=config, tenant_id=tenant_id)
        if not split_provenance.counts.get("train") or not split_provenance.counts.get("test"):
            raise SubmissionValidationError(
                "Tập chia hiện tại không dùng được để huấn luyện "
                f"(train={split_provenance.counts.get('train', 0)}, "
                f"test={split_provenance.counts.get('test', 0)} mẫu). "
                "Hãy chia lại tập dữ liệu trước khi huấn luyện."
            )

    job_id = str(uuid.uuid4())[:8]
    job = TrainingJob(
        id=job_id,
        status="queued",
        config=config,
        created_at=datetime.now().isoformat(),
        total_epochs=config.epochs,
        split_provenance=split_provenance,
    )
    jobs[job_id] = {"job": job, "progress": [], "tenant_id": tenant_id}
    await persist_job(job, auth_user_id=auth_user_id)

    try:
        from app.modules.training.tasks import run_training_job

        await asyncio.to_thread(
            run_training_job.apply_async,
            kwargs={"job_id": job_id},
            queue="training",
        )
        logger.info("job=%s dispatched to trainer by user=%s", job_id, username)
    except Exception as exc:
        job.status = "failed"
        job.completed_at = datetime.now().isoformat()
        job.error_message = f"Không gửi được job tới trainer (Redis/Celery down?): {exc}"
        await persist_job(job)
        raise QueueUnavailableError from exc

    return job
