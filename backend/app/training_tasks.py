"""Celery task: run one training job in the trainer container.

Why this exists (P1):
  - Training used to run as a subprocess INSIDE the backend API container,
    competing for CPU with request serving. It now runs in a dedicated
    Celery worker (service `trainer`, queue "training", concurrency 1 —
    jobs stay strictly serialized).
  - Progress used to be scraped from stdout with string-splitting. The train
    script now writes a structured JSONL metrics file (--metrics_file);
    this task tails it and persists每 epoch to Postgres. The backend serves
    progress from Postgres (WebSocket polls DB), so backend and trainer
    share no process state.

Coordination contracts:
  - Job state lives in Postgres (training_jobs / training_metrics).
  - Cancellation: backend sets Redis key ``training:cancel:{job_id}``;
    this task polls it every loop tick and terminates the subprocess.
  - Subprocess stdout/stderr go to a per-job log file (debuggable, no
    pipe-drain threads needed).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import redis

from app.worker import celery_app

import logging

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path("/workspace")
OUTPUTS_DIR = WORKSPACE_ROOT / "processed" / "train_utils" / "outputs"
JOB_ARTIFACTS_DIR = OUTPUTS_DIR / "job_artifacts"

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CANCEL_KEY_PREFIX = "training:cancel:"
TRAINING_JOB_TIMEOUT_SECONDS = int(os.getenv("TRAINING_JOB_TIMEOUT_SECONDS", str(6 * 3600)))

POLL_INTERVAL_SECONDS = 2
TERMINATE_GRACE_SECONDS = 30


def _now() -> str:
    return datetime.now().isoformat()


def _get_redis() -> Optional["redis.Redis"]:
    try:
        client = redis.from_url(
            REDIS_URL, decode_responses=True,
            socket_connect_timeout=2, socket_timeout=5,
        )
        client.ping()
        return client
    except Exception as e:
        logger.warning("[TRAINER] Redis unavailable (cancel disabled): %s", e)
        return None


def _update_job(row: Dict[str, Any], **fields: Any) -> None:
    """Best-effort DB update — a DB hiccup must not kill a training run."""
    row.update(fields)
    try:
        from app.storage.metadata_db import upsert_training_job

        upsert_training_job(row)
    except Exception as e:
        logger.warning("[TRAINER] job %s DB update failed: %s", row.get("job_id"), e)


def _escalate_system_failure(row: Dict[str, Any], job_id: str, error: str, source: str) -> None:
    """Notify admins if this trainer-side failure is a system/infra problem (not
    the user's data). Best-effort — never let alerting break the task."""
    try:
        from app.training_alerts import notify_admins_training_failure

        actor = str(row.get("username") or row.get("auth_user_id") or row.get("user_id") or "")
        notify_admins_training_failure(job_id=job_id, actor=actor, error=error, source=source)
    except Exception as e:
        logger.warning("[TRAINER] job %s admin escalation failed: %s", job_id, e)


def _insert_metric(job_id: str, m: Dict[str, Any]) -> None:
    try:
        from app.storage.metadata_db import insert_training_metric

        insert_training_metric({
            "job_id": job_id,
            "epoch": int(m["epoch"]),
            "train_loss": float(m.get("train_loss") or 0.0),
            "train_acc": float(m.get("train_acc") or 0.0),
            "val_loss": float(m.get("val_loss") or 0.0),
            "val_acc": float(m.get("val_acc") or 0.0),
            "val_f1": float(m.get("val_f1") or 0.0),
        })
    except Exception as e:
        logger.warning("[TRAINER] job %s metric epoch=%s DB write failed: %s", job_id, m.get("epoch"), e)


def _build_cmd(config: Dict[str, Any], metrics_file: Path) -> list:
    cmd = [
        "python", "-m", "processed.train_utils.train_tcn",
        f"--model_type={config.get('model_type', 'tcn')}",
        f"--epochs={int(config.get('epochs', 80))}",
        f"--batch_size={int(config.get('batch_size', 32))}",
        f"--lr={float(config.get('learning_rate', 0.001))}",
        f"--dropout={float(config.get('dropout', 0.3))}",
        f"--channels={int(config.get('channels', 64))}",
        f"--levels={int(config.get('levels', 3))}",
        f"--kernel_size={int(config.get('kernel_size', 5))}",
        f"--metrics_file={metrics_file}",
        "--run_diagnostics",
    ]
    for dialect in (config.get("dialects") or []):
        cmd.append(f"--dialect={dialect}")
    for language in (config.get("languages") or []):
        cmd.append(f"--filter_language={language}")
    return cmd


@celery_app.task(bind=True, name="app.training_tasks.run_training_job")
def run_training_job(self, job_id: str) -> Dict[str, Any]:
    from app.storage.metadata_db import get_training_job

    try:
        row = get_training_job(job_id)
    except Exception as e:
        logger.error("[TRAINER] job %s: cannot read DB: %s", job_id, e)
        raise self.retry(exc=e, countdown=15, max_retries=3)

    if not row:
        logger.warning("[TRAINER] job %s not found in DB — skipping", job_id)
        return {"status": "skipped", "reason": "not_found"}

    # Idempotency: duplicate deliveries / requeues run only once
    if str(row.get("status")) != "queued":
        logger.info("[TRAINER] job %s status=%s (not queued) — skipping", job_id, row.get("status"))
        return {"status": "skipped", "reason": f"status_{row.get('status')}"}

    config: Dict[str, Any] = row.get("config") or {}
    redis_client = _get_redis()
    cancel_key = f"{CANCEL_KEY_PREFIX}{job_id}"

    # Pre-start cancel check (cancelled while sitting in the Celery queue)
    if redis_client and redis_client.exists(cancel_key):
        _update_job(row, status="cancelled", completed_at=_now(),
                    error_message="Bị hủy khi đang chờ trong queue")
        return {"status": "cancelled", "when": "pre_start"}

    JOB_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_file = JOB_ARTIFACTS_DIR / f"{job_id}.metrics.jsonl"
    log_file = JOB_ARTIFACTS_DIR / f"{job_id}.log"
    # Fresh start for retried/requeued jobs
    for stale in (metrics_file,):
        try:
            if stale.exists():
                stale.unlink()
        except Exception:
            pass

    _update_job(row, status="running", started_at=_now())
    logger.info("[TRAINER] job %s starting (model=%s epochs=%s)",
                job_id, config.get("model_type"), config.get("epochs"))

    env = os.environ.copy()
    env["PYTHONPATH"] = str(WORKSPACE_ROOT)
    env["PYTHONUNBUFFERED"] = "1"

    cmd = _build_cmd(config, metrics_file)
    logger.info("[TRAINER] job %s CMD: %s (log: %s)", job_id, " ".join(cmd), log_file)

    log_handle = open(log_file, "w", encoding="utf-8", errors="replace")
    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(WORKSPACE_ROOT),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=env,
        )
    except Exception as e:
        log_handle.close()
        msg = f"Không khởi động được training process: {e}"
        _update_job(row, status="failed", completed_at=_now(), error_message=msg)
        _escalate_system_failure(row, job_id, msg, source="trainer_spawn")
        return {"status": "failed", "reason": "spawn_error"}

    started_monotonic = time.monotonic()
    metrics_pos = 0
    final_info: Dict[str, Any] = {}
    cancelled = False
    timed_out = False

    def _consume_new_metric_lines() -> None:
        nonlocal metrics_pos, final_info
        if not metrics_file.exists():
            return
        try:
            with open(metrics_file, "r", encoding="utf-8") as mf:
                mf.seek(metrics_pos)
                while True:
                    # readline() (not iteration) — file iterators forbid tell()
                    line = mf.readline()
                    if not line:
                        break
                    if not line.endswith("\n"):
                        break  # partial line still being written
                    metrics_pos = mf.tell()
                    try:
                        payload = json.loads(line)
                    except Exception:
                        continue
                    if payload.get("type") == "epoch":
                        _insert_metric(job_id, payload)
                        _update_job(row, current_epoch=int(payload.get("epoch") or 0))
                    elif payload.get("type") == "final":
                        final_info = payload
        except Exception as e:
            logger.warning("[TRAINER] job %s metrics tail error: %s", job_id, e)

    def _terminate_process() -> None:
        try:
            process.terminate()
            try:
                process.wait(timeout=TERMINATE_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                logger.warning("[TRAINER] job %s SIGTERM ignored — SIGKILL", job_id)
                process.kill()
                process.wait()
        except Exception as e:
            logger.warning("[TRAINER] job %s terminate error: %s", job_id, e)

    # Single-threaded supervision loop: drain metrics, watch cancel + timeout
    while True:
        rc = process.poll()
        _consume_new_metric_lines()
        if rc is not None:
            break

        if not cancelled and redis_client:
            try:
                if redis_client.exists(cancel_key):
                    logger.info("[TRAINER] job %s cancel requested — terminating", job_id)
                    cancelled = True
                    _terminate_process()
                    continue
            except Exception:
                pass  # Redis hiccup — keep training

        if not timed_out and (time.monotonic() - started_monotonic) > TRAINING_JOB_TIMEOUT_SECONDS:
            logger.warning("[TRAINER] job %s timeout after %ss — killing", job_id, TRAINING_JOB_TIMEOUT_SECONDS)
            timed_out = True
            _terminate_process()
            continue

        time.sleep(POLL_INTERVAL_SECONDS)

    log_handle.close()
    _consume_new_metric_lines()  # final drain
    returncode = process.returncode
    logger.info("[TRAINER] job %s exited rc=%s cancelled=%s timed_out=%s", job_id, returncode, cancelled, timed_out)

    if redis_client:
        try:
            redis_client.delete(cancel_key)
        except Exception:
            pass

    if cancelled:
        _update_job(row, status="cancelled", completed_at=_now(),
                    error_message=row.get("error_message") or "Bị hủy bởi người dùng")
        return {"status": "cancelled"}

    if timed_out:
        msg = f"Quá thời gian tối đa {TRAINING_JOB_TIMEOUT_SECONDS // 3600}h — job bị dừng tự động"
        _update_job(row, status="failed", completed_at=_now(), error_message=msg)
        _escalate_system_failure(row, job_id, msg, source="trainer_timeout")
        return {"status": "failed", "reason": "timeout"}

    if returncode != 0:
        msg = f"Training process thoát với mã lỗi {returncode} (xem {log_file.name})"
        _update_job(row, status="failed", completed_at=_now(), error_message=msg)
        _escalate_system_failure(row, job_id, msg, source="trainer_exit")
        return {"status": "failed", "returncode": returncode}

    # Success — checkpoint path comes from the train script's "final" record
    # (exact file, no mtime guessing). Fallback: newest .pt in outputs/.
    checkpoint_path = str(final_info.get("checkpoint_path") or "")
    if not checkpoint_path or not Path(checkpoint_path).exists():
        try:
            candidates = sorted(OUTPUTS_DIR.glob("*.pt"), key=lambda x: x.stat().st_mtime, reverse=True)
            checkpoint_path = str(candidates[0]) if candidates else ""
        except Exception:
            checkpoint_path = ""

    test_acc = final_info.get("test_acc")
    test_f1 = final_info.get("test_f1")
    evaluation = final_info.get("evaluation")  # confusion matrix + per-class

    _update_job(
        row,
        status="completed",
        completed_at=_now(),
        checkpoint_path=checkpoint_path or None,
        test_acc=float(test_acc) if test_acc is not None else None,
        test_f1=float(test_f1) if test_f1 is not None else None,
        evaluation=evaluation if isinstance(evaluation, dict) else None,
    )
    logger.info("[TRAINER] job %s ✓ completed checkpoint=%s acc=%s f1=%s",
                job_id, checkpoint_path, test_acc, test_f1)
    return {"status": "completed", "checkpoint_path": checkpoint_path}


# ============================================================================
# Model backup + artifact retention
# ============================================================================

@celery_app.task(bind=True, max_retries=5, default_retry_delay=30)
def backup_promoted_checkpoint_task(self, job_id: str, checkpoint_path: str):
    """Mirror a PROMOTED model checkpoint to Google Drive.

    Only promoted models are backed up — experimental runs in outputs/ are
    reproducible and not worth the bandwidth. Dispatched by the promote
    endpoint; failure never blocks the promotion itself.
    """
    from app.config import settings

    if not getattr(settings, "use_google_drive", False):
        return {"status": "skipped", "reason": "gdrive_disabled"}

    from app.storage.gdrive_client import upload_to_gdrive

    try:
        src = Path(checkpoint_path)
        if not src.exists():
            logger.warning("[MODEL_BACKUP] checkpoint not found: %s", checkpoint_path)
            return {"status": "skipped", "reason": "file_not_found"}

        storage_key = f"models/promoted/{src.name}"
        logger.info("[MODEL_BACKUP] job %s uploading %s -> gdrive:%s", job_id, src, storage_key)
        url = upload_to_gdrive(str(src), storage_key, content_type="application/octet-stream", make_public=False)

        # Sidecar JSON (metadata) if present
        sidecar = src.with_suffix(".json")
        if sidecar.exists():
            try:
                upload_to_gdrive(str(sidecar), f"models/promoted/{sidecar.name}",
                                 content_type="application/json", make_public=False)
            except Exception as e:
                logger.warning("[MODEL_BACKUP] sidecar upload failed: %s", e)

        logger.info("[MODEL_BACKUP] job %s ✓ backed up: %s", job_id, url)
        return {"status": "success", "url": url}
    except Exception as exc:
        logger.error("[MODEL_BACKUP] job %s failed: %s", job_id, exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True)
def cleanup_training_artifacts(self):
    """Daily retention sweep (Celery beat).

    - outputs/*.pt: keep the newest TRAINING_OUTPUTS_KEEP runs (default 20);
      promoted models are safe to prune here because promotion copies them
      to the realtime config dir and re-points checkpoint_path there.
    - job_artifacts/: delete logs/metrics older than
      TRAINING_ARTIFACTS_KEEP_DAYS (default 30).
    """
    keep_n = int(os.getenv("TRAINING_OUTPUTS_KEEP", "20"))
    keep_days = int(os.getenv("TRAINING_ARTIFACTS_KEEP_DAYS", "30"))

    removed_ckpts = 0
    removed_artifacts = 0

    try:
        checkpoints = sorted(OUTPUTS_DIR.glob("*.pt"), key=lambda p: p.stat().st_mtime, reverse=True)
        for stale in checkpoints[keep_n:]:
            try:
                sidecar = stale.with_suffix(".json")
                stale.unlink()
                if sidecar.exists():
                    sidecar.unlink()
                removed_ckpts += 1
            except Exception as e:
                logger.warning("[RETENTION] cannot remove %s: %s", stale, e)
    except Exception as e:
        logger.warning("[RETENTION] outputs sweep failed: %s", e)

    try:
        cutoff = time.time() - keep_days * 86400
        if JOB_ARTIFACTS_DIR.exists():
            for artifact in JOB_ARTIFACTS_DIR.iterdir():
                try:
                    if artifact.is_file() and artifact.stat().st_mtime < cutoff:
                        artifact.unlink()
                        removed_artifacts += 1
                except Exception as e:
                    logger.warning("[RETENTION] cannot remove %s: %s", artifact, e)
    except Exception as e:
        logger.warning("[RETENTION] artifacts sweep failed: %s", e)

    logger.info("[RETENTION] removed %d old checkpoints, %d old artifacts (keep_n=%d, keep_days=%d)",
                removed_ckpts, removed_artifacts, keep_n, keep_days)
    return {"removed_checkpoints": removed_ckpts, "removed_artifacts": removed_artifacts}
