"""Training job cache and persistence boundary.

Postgres is the source of truth. The process-local mapping only keeps recent
job objects and terminal metrics warm for the HTTP and WebSocket endpoints.
Database failures remain best-effort so an outage does not kill an active job.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.modules.training.schemas import (
    SplitProvenance,
    TrainingConfig,
    TrainingJob,
    TrainingMetrics,
)

logger = logging.getLogger(__name__)

training_jobs: Dict[str, Dict[str, Any]] = {}
TERMINAL_STATUSES = ("completed", "failed", "cancelled")


def _persist_job_sync(job: TrainingJob, auth_user_id: Optional[str] = None) -> None:
    try:
        from app.storage.metadata_db import upsert_training_job

        upsert_training_job({
            "job_id": job.id,
            "status": job.status,
            "model_type": job.config.model_type,
            "config": job.config.dict(),
            "auth_user_id": auth_user_id,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "current_epoch": job.current_epoch,
            "total_epochs": job.total_epochs,
            "checkpoint_path": job.checkpoint_path,
            "test_acc": job.test_acc,
            "test_f1": job.test_f1,
            "error_message": job.error_message,
            "promoted_at": job.promoted_at,
            "split_provenance": job.split_provenance.dict() if job.split_provenance else None,
        })
    except Exception as exc:
        logger.warning("job %s DB write failed (state kept in memory): %s", job.id, exc)


async def _persist_job(job: TrainingJob, auth_user_id: Optional[str] = None) -> None:
    await asyncio.to_thread(_persist_job_sync, job, auth_user_id)


def _persist_metric_sync(job_id: str, metric: TrainingMetrics) -> None:
    try:
        from app.storage.metadata_db import insert_training_metric

        insert_training_metric({
            "job_id": job_id,
            "epoch": metric.epoch,
            "train_loss": metric.train_loss,
            "train_acc": metric.train_acc,
            "val_loss": metric.val_loss,
            "val_acc": metric.val_acc,
            "val_f1": metric.val_f1,
        })
    except Exception as exc:
        logger.warning("metric epoch=%s job=%s DB write failed: %s", metric.epoch, job_id, exc)


def _split_prov_from_row(value: Any) -> Optional[SplitProvenance]:
    if not value:
        return None
    try:
        if isinstance(value, str):
            value = json.loads(value)
        return SplitProvenance(**value)
    except Exception as exc:
        logger.warning("[SPLIT_PROV] không đọc được split_provenance đã lưu: %s", exc)
        return None


def _job_from_db_row(row: Dict[str, Any]) -> TrainingJob:
    config_raw = row.get("config") or {}
    try:
        config = TrainingConfig(**config_raw)
    except Exception:
        config = TrainingConfig()

    def _iso(value: Any) -> Optional[str]:
        if value is None:
            return None
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    return TrainingJob(
        id=str(row["job_id"]),
        status=str(row.get("status") or "failed"),
        config=config,
        created_at=_iso(row.get("created_at")) or datetime.now().isoformat(),
        started_at=_iso(row.get("started_at")),
        completed_at=_iso(row.get("completed_at")),
        current_epoch=int(row.get("current_epoch") or 0),
        total_epochs=int(row.get("total_epochs") or 0),
        checkpoint_path=row.get("checkpoint_path"),
        test_acc=row.get("test_acc"),
        test_f1=row.get("test_f1"),
        error_message=row.get("error_message"),
        promoted_at=_iso(row.get("promoted_at")),
        split_provenance=_split_prov_from_row(row.get("split_provenance")),
    )


def _metrics_from_db_rows(rows: List[Dict[str, Any]]) -> List[TrainingMetrics]:
    metrics: List[TrainingMetrics] = []
    for row in rows:
        try:
            metrics.append(TrainingMetrics(
                epoch=int(row["epoch"]),
                train_loss=float(row.get("train_loss") or 0.0),
                train_acc=float(row.get("train_acc") or 0.0),
                val_loss=float(row.get("val_loss") or 0.0),
                val_acc=float(row.get("val_acc") or 0.0),
                val_f1=float(row.get("val_f1") or 0.0),
            ))
        except Exception:
            continue
    return metrics


async def restore_jobs_from_db(limit: int = 50) -> None:
    """Rehydrate recent jobs and safely requeue persisted queued jobs."""
    try:
        from app.storage.metadata_db import list_training_jobs

        rows = await asyncio.to_thread(list_training_jobs, limit)
    except Exception as exc:
        logger.warning("Cannot read jobs from DB (starting empty): %s", exc)
        return

    restored = 0
    requeued = 0
    for row in reversed(rows):
        try:
            job = _job_from_db_row(row)
        except Exception as exc:
            logger.warning("Skipping malformed job row: %s", exc)
            continue

        if job.id in training_jobs:
            continue

        if job.status == "queued":
            try:
                from app.training_tasks import run_training_job

                run_training_job.apply_async(args=[job.id], queue="training")
                requeued += 1
            except Exception as exc:
                logger.warning("Requeue failed for %s: %s", job.id, exc)

        training_jobs[job.id] = {"job": job, "progress": []}
        restored += 1

    logger.info("restored=%d requeued=%d", restored, requeued)


async def _ensure_job_loaded(job_id: str) -> Optional[Dict[str, Any]]:
    """Return cached job info, refreshing non-terminal state from Postgres."""
    cached = training_jobs.get(job_id)
    if cached and cached["job"].status in TERMINAL_STATUSES:
        return cached

    try:
        from app.storage.metadata_db import get_training_job

        row = await asyncio.to_thread(get_training_job, job_id)
    except Exception as exc:
        logger.warning("DB lookup failed for job %s: %s", job_id, exc)
        return cached
    if not row:
        return cached

    job = _job_from_db_row(row)
    if cached:
        cached["job"] = job
        return cached

    job_info = {"job": job, "progress": []}
    training_jobs[job_id] = job_info
    return job_info
