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
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import redis

from app.checkpoint_io import load_checkpoint
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

    # Webhook `training.failed` phát ở ĐÂY chứ không ở ba chỗ gọi.
    #
    # Cả ba đường dẫn tới trạng thái `failed` (spawn hỏng, quá giờ, mã thoát
    # khác 0) đều đi qua hàm này — nó đã là phễu duy nhất cho "job hỏng vì lý
    # do hệ thống". Đặt lời gọi ở ba chỗ là ba bản sao sẽ lệch nhau ở lần thêm
    # đường hỏng thứ tư, và cái lệch đó im lặng: khách hàng chỉ đơn giản không
    # bao giờ nhận được thông báo cho đúng kiểu hỏng mới.
    #
    # `cancelled` KHÔNG đi qua đây, và đó là đúng: người dùng tự huỷ thì họ đã
    # biết rồi, không cần hệ thống của họ được báo như một sự cố.
    _emit_training_event(row, "training.failed", {
        "job_id": job_id, "error": error, "source": source,
    })


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


SPLITS_DIR = WORKSPACE_ROOT / "processed" / "splits"


def _resolve_for_run(config: Dict[str, Any], *, tenant_id: str):
    """Hiện vật mà lượt chạy này SẼ đọc. Một cửa, gọi đúng một lần.

    Trả `None` chỉ ở đúng một trường hợp — nhánh tương thích legacy mà hiện vật
    nghiên cứu không xác minh được — và trường hợp đó được ghi nhật ký ở mức
    ERROR chứ không im lặng.

    Vì sao phải tập trung ở đây: trước lượt này có BA cách hiểu khác nhau về
    câu hỏi "lượt này đọc tệp nào" — mặc định của `train_tcn`, nhánh nghiên cứu
    của `_build_cmd`, và `_split_csvs_of` (trả rỗng cho legacy). Ba cách hiểu
    lệch nhau được mà không ai biết, và khi lệch thì cổng đồng thuận soi tệp A
    trong khi trainer đọc tệp B — mỗi tầng vẫn "đúng" mà cả hệ thống sai.
    """
    from processed.train_utils.split_artifact import (
        PURPOSE_OPERATIONAL, PURPOSE_RESEARCH, SplitArtifactError,
        resolve_split_artifact,
    )

    split_id = str(config.get("operational_split_id") or "").strip()
    muc_dich = str(config.get("run_purpose") or "").strip()

    if muc_dich == PURPOSE_OPERATIONAL or split_id:
        # FAIL-CLOSED. Không rơi về ba tệp nghiên cứu, không tự chọn "split mới
        # nhất", không suy từ dialect. Một lượt vận hành học trên mốc nghiên cứu
        # đóng băng là một checkpoint khai sai nguồn gốc.
        #
        # `tenant_id` đến từ HÀNG job đã lưu, không từ `config`. Người gọi ghi
        # được vào `config`; hàng job thì không — nên đó là nguồn thẩm quyền duy
        # nhất chấp nhận được ở đây.
        return resolve_split_artifact(
            purpose=PURPOSE_OPERATIONAL, splits_root=SPLITS_DIR,
            split_id=split_id, tenant_id=tenant_id)

    if muc_dich == PURPOSE_RESEARCH:
        # Nhánh nghiên cứu ghim `split_version` riêng (thư mục versioned), đã có
        # hợp đồng của nó — resolver không quản.
        return None

    # Legacy/smoke_test: hiện vật nghiên cứu đóng băng, nhưng nói RA thay vì để
    # trainer tự lấy mặc định. Chính vì nó im lặng mà `_split_csvs_of` trả rỗng
    # và cổng đồng thuận không soi lượt legacy nào.
    try:
        return resolve_split_artifact(
            purpose=PURPOSE_RESEARCH, splits_root=SPLITS_DIR,
            tenant_id=tenant_id)
    except SplitArtifactError as exc:
        # KHÔNG chặn ở đây, và đây là lựa chọn có ý thức: legacy là hợp đồng
        # tương thích, ba tệp này vốn đã là mặc định của trainer, nên chặn lại
        # sẽ giết mọi lượt chạy cũ vì một sổ băm thiếu. Cái mất là khả năng soi
        # — đúng bằng hiện trạng — nên dấu vết phải đủ to để thấy điều đó.
        logger.error(
            "[TRAINER] không xác minh được hiện vật nghiên cứu đóng băng (%s) — "
            "lượt legacy chạy tiếp bằng mặc định của trainer và KHÔNG được cổng "
            "đồng thuận soi: %s", type(exc).__name__, exc)
        return None


def _build_cmd(config: Dict[str, Any], metrics_file: Path, *,
               tenant_id: str) -> list:
    """`tenant_id` bắt buộc, lấy từ hàng job — xem `_resolve_for_run`."""
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

    # Chế độ nghiên cứu: chạy trên split đã versioned nên checkpoint truy ngược
    # được về đúng phiên bản dữ liệu. Bộ lọc dialect/language KHÔNG áp dụng ở
    # đây — split đã định nghĩa sẵn tập dữ liệu, thêm bộ lọc vào sẽ cắt bớt nó
    # và làm checkpoint không còn khớp với split nó khai báo.
    if str(config.get("run_purpose") or "") == "research" and config.get("split_version"):
        split_dir = f"processed/splits/versions/{config['split_version']}"
        cmd += [
            "--run-purpose=research",
            f"--split_version={config['split_version']}",
            f"--train_csv={split_dir}/train.csv",
            f"--val_csv={split_dir}/val.csv",
            f"--test_csv={split_dir}/test.csv",
            # Bắt buộc khi có --recognition_profile: trainer chuyển sang profile
            # mode và không tự dò được thư mục features từ split CSV.
            f"--features_root={os.getenv('FEATURES_ROOT', '/dataset/features')}",
        ]
        if config.get("dataset_version"):
            cmd.append(f"--dataset_version={config['dataset_version']}")
        if config.get("recognition_profile"):
            cmd.append(f"--recognition_profile={config['recognition_profile']}")
        return cmd

    # Từ đây trở xuống là nhánh vận hành + legacy. Cả hai đi qua CÙNG một
    # resolver, nên `_split_csvs_of(cmd)` — thứ cổng đồng thuận soi — luôn trả
    # đúng tệp trainer sẽ đọc.
    artifact = _resolve_for_run(config, tenant_id=tenant_id)
    if artifact is not None:
        cmd += [
            f"--train_csv={artifact.train_csv}",
            f"--val_csv={artifact.val_csv}",
            f"--test_csv={artifact.test_csv}",
        ]

    for dialect in (config.get("dialects") or []):
        cmd.append(f"--dialect={dialect}")
    for language in (config.get("languages") or []):
        cmd.append(f"--filter_language={language}")

    # `--dialect` là thứ đưa trainer vào chế độ subset, và chế độ subset là nơi
    # nhánh vận hành (`class_uid → target_idx`) sống. Một hiện vật vận hành đã
    # được lọc sẵn theo phương ngữ, nên bộ lọc này là phép đồng nhất — nhưng
    # thiếu nó thì trainer không vào nhánh đó và quay về `enumerate` theo thứ
    # tự hàng. Suy từ chính bản khai chứ không bắt người gọi nhớ.
    if artifact is not None and artifact.purpose == "operational":
        if not any(a.startswith("--dialect=") for a in cmd):
            pham_vi = (artifact.metadata.get("scope") or {}).get("dialects") or []
            for d in pham_vi:
                cmd.append(f"--dialect={d}")
        cmd.append(f"--features_root={os.getenv('FEATURES_ROOT', '/dataset/features')}")

    return cmd


def _split_csvs_of(cmd: list) -> list:
    """Các tệp split mà lệnh này sắp đọc, lấy từ chính lệnh đó.

    Đọc lại từ `cmd` chứ không dựng lại từ `config`: `_build_cmd` có hai nhánh
    và một tập giá trị mặc định, nên suy diễn lần thứ hai là hai bản cài đặt
    của cùng một quy tắc — và bản nào sai thì cổng đồng thuận soi nhầm tệp.

    Sau khi `_build_cmd` đi qua `_resolve_for_run`, `cmd` LUÔN mang đường dẫn
    tường minh (trừ nhánh legacy không xác minh được hiện vật, đã ghi ERROR).
    Nghĩa là hàm này không còn trả rỗng cho lượt vận hành, và bất biến
    *"hiện vật được preflight == hiện vật trainer thật sự đọc"* được bảo đảm
    bằng thứ mạnh nhất có thể: chính argv của tiến trình con.
    """
    prefixes = ("--train_csv=", "--val_csv=", "--test_csv=")
    return [arg.split("=", 1)[1] for arg in cmd if arg.startswith(prefixes)]


def _consent_preflight(config: Dict[str, Any], cmd: list) -> Optional[str]:
    """Trả về câu báo lỗi nếu tập huấn luyện chứa mẫu không được phép dùng.

    Vì sao chặn thay vì lọc: các tệp split là ĐẦU VÀO đã đóng băng, và một
    checkpoint huấn luyện trên tập nhỏ hơn tệp split khai báo là một checkpoint
    nói dối về nguồn gốc của nó. Việc đúng là dựng lại split, và câu báo lỗi
    phải nói ra điều đó.

    Không có tệp split nào để soi (nhánh dialect/language chạy bằng giá trị mặc
    định của trainer) thì cổng không kết luận gì — xem `audit_csv_files`.
    """
    paths = _split_csvs_of(cmd)
    if not paths:
        return None
    try:
        from app.consent_gate import audit_csv_files, scope_for_run_purpose

        scope = scope_for_run_purpose(config.get("run_purpose"))
        result = audit_csv_files(paths, scope=scope)
    except Exception as exc:
        # Cổng hỏng KHÔNG được làm chết mọi lượt huấn luyện. Ghi lại thật to;
        # đây là lựa chọn có ý thức giữa "không huấn luyện được gì" và "một
        # lượt chạy không được soi", và dấu vết phải đủ để phát hiện lựa chọn
        # đó đã xảy ra.
        logger.error("[CONSENT] pre-flight FAILED to run (%s) — job proceeds unchecked: %s",
                     type(exc).__name__, exc)
        return None

    if not result.withheld:
        logger.info("[CONSENT] pre-flight ok: %s", result.summary())
        return None
    return (f"Cổng đồng thuận chặn: {result.summary()}. "
            f"Dựng lại split với mức '{result.scope}' rồi chạy lại.")


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

    # ★ C2c — job không mang tenant thì DỪNG TRƯỚC resolver.
    #
    # Đẩy chuỗi rỗng xuống resolver cũng bị chặn, nhưng thông điệp sẽ nói về
    # hiện vật trong khi lỗi thật nằm ở hàng job. Người đọc nhật ký sáu tháng
    # sau sẽ đi tìm hiện vật bị xoá thay vì một job lập hồ sơ thiếu tenant.
    tenant_job = str(row.get("tenant_id") or "").strip()
    if not tenant_job:
        loi = ("Job không mang `tenant_id` nên không xác định được nó được phép "
               "đọc hiện vật nào. KHÔNG suy ra tenant từ cấu hình lượt chạy.")
        logger.error("[TRAINER] job %s: %s", job_id, loi)
        _update_job(row, status="failed", completed_at=_now(), error_message=loi)
        return {"status": "failed", "reason": "tenant_missing", "detail": loi}

    try:
        cmd = _build_cmd(config, metrics_file, tenant_id=tenant_job)
    except Exception as exc:
        # Hiện vật không phân giải được thì job DỪNG ở đây, chưa từng "running".
        # Chạy tiếp bằng mặc định của trainer là đúng thứ fail-closed sinh ra để
        # chặn: lượt vận hành sẽ lặng lẽ học trên mốc nghiên cứu đóng băng.
        loi = f"Không phân giải được tập chia cho lượt chạy này: {exc}"
        logger.error("[TRAINER] job %s: %s", job_id, loi)
        _update_job(row, status="failed", completed_at=_now(), error_message=loi)
        _escalate_system_failure(row, job_id, loi, source="split_artifact")
        return {"status": "failed", "reason": "split_artifact", "detail": loi}

    # Cổng đồng thuận chạy TRƯỚC khi job chuyển sang "running": một job bị chặn
    # vì lý do đồng thuận chưa từng bắt đầu, và trạng thái của nó phải nói đúng
    # như vậy chứ không phải "đã chạy rồi hỏng".
    blocked = _consent_preflight(config, cmd)
    if blocked:
        logger.warning("[TRAINER] job %s blocked by consent gate: %s", job_id, blocked)
        _update_job(row, status="failed", completed_at=_now(), error_message=blocked)
        return {"status": "failed", "reason": "consent_gate", "detail": blocked}

    _update_job(row, status="running", started_at=_now())
    logger.info("[TRAINER] job %s starting (model=%s epochs=%s)",
                job_id, config.get("model_type"), config.get("epochs"))

    env = os.environ.copy()
    env["PYTHONPATH"] = str(WORKSPACE_ROOT)
    env["PYTHONUNBUFFERED"] = "1"

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
    _record_output_contract(job_id, row, checkpoint_path)

    # Sự kiện phát SAU khi hợp đồng đầu ra đã ghi xong. Đây là sự kiện có giá
    # trị tích hợp cao nhất trong hệ: một lượt huấn luyện chạy hàng chục phút,
    # nên hỏi dò để biết nó xong là vừa chậm vừa tốn, còn webhook thì không.
    _emit_training_event(row, "training.completed", {
        "job_id": job_id, "checkpoint_path": checkpoint_path,
        "test_acc": test_acc, "test_f1": test_f1,
    })

    logger.info("[TRAINER] job %s ✓ completed checkpoint=%s acc=%s f1=%s",
                job_id, checkpoint_path, test_acc, test_f1)
    return {"status": "completed", "checkpoint_path": checkpoint_path}


def _emit_training_event(row: Dict[str, Any], event: str, payload: Dict[str, Any]) -> None:
    """Phát một sự kiện huấn luyện cho tenant SỞ HỮU job.

    Tenant lấy từ chính hàng job, không lấy từ ngữ cảnh đang chạy: tác vụ này
    chạy trong container trainer dưới `platform_wide` scope, nên ngữ cảnh là
    "toàn nền tảng" chứ không phải tenant nào cả. Dùng ngữ cảnh ở đây sẽ gửi
    sự kiện cho sai người, hoặc không gửi cho ai.

    KHÔNG rơi về `default` — sửa 16/08/2026
    ---------------------------------------
    Bản trước là `row.get("tenant_id") or "default"`. Một job mất `tenant_id` sẽ
    phát sự kiện của nó tới **cấu hình webhook của tenant khởi tạo** — tức gửi
    thông tin huấn luyện của một tổ chức tới endpoint của tổ chức khác.

    "Thiếu tenant" KHÔNG BAO GIỜ là cách ngầm để nói "toàn hệ thống". Nếu một
    ngày có job thật sự thuộc hệ thống thì nó phải mang danh tính hệ thống
    TƯỜNG MINH, đúng cách `platform_administrator` được tách khỏi
    `tenant_administrator` — chứ không biểu diễn bằng một ô trống.
    """
    tenant = str(row.get("tenant_id") or "").strip()
    if not tenant:
        # Không phát còn hơn phát nhầm người. Ghi ở mức ERROR: đây là vi phạm
        # hợp đồng dữ liệu, không phải một trục trặc thoáng qua.
        logger.error("[TRAINER] job thieu tenant_id — KHONG phat su kien %s. "
                     "Khong bao gio gui vao pham vi 'default'.", event)
        return
    try:
        from app.webhooks import emit

        emit(tenant, event, payload)
    except Exception as exc:
        logger.warning("[TRAINER] không phát được sự kiện %s: %s", event, type(exc).__name__)


def _record_output_contract(job_id: str, row: Dict[str, Any], checkpoint_path: str) -> None:
    """Đóng băng ánh xạ chỉ số → nhãn của model vào `training_job_classes`.

    Vì sao phải lưu, khi `config` đã có sẵn: `config` chỉ chứa BỘ LỌC
    (`{"dialects": ["bang-chu-cai"]}`), không chứa tập lớp đã giải. Giải lại bộ
    lọc đó sau vài tháng sẽ ra danh mục của LÚC GIẢI, không phải của lúc train
    — danh mục thay đổi liên tục. Nên "model này xuất ra nhãn nào ở chỉ số nào"
    là thứ chỉ đúng nếu được ghi tại thời điểm nó thành sự thật.

    Nguồn là `idx_to_label` trong checkpoint, không phải một truy vấn vào
    `classes`: checkpoint LÀ hiện vật, nên nó là nơi duy nhất nói đúng model
    thực sự học gì. Một truy vấn sẽ chỉ tái tạo một phỏng đoán.

    `label` được lưu nguyên văn thay vì join sang `classes` mỗi lần đọc: đổi
    tên một lớp không được phép đổi nhãn mà một model đã phát hành đang mang.

    Không ném lỗi. Job đã chạy xong và checkpoint đã nằm trên đĩa; làm hỏng
    một job thành công vì không ghi được bảng phụ trợ là đánh đổi sai.

    Nạp qua `checkpoint_io.load_checkpoint` chứ không phải `torch.load` trần:
    module đó kiểm đường dẫn nằm trong các gốc cho phép rồi mới thử
    `weights_only=True`. `torch.load(..., weights_only=False)` giải pickle, tức
    là THỰC THI mã trong file — chấp nhận được với hiện vật của chính mình,
    nhưng chỉ sau khi đã chắc file đúng là hiện vật của chính mình.
    """
    if not checkpoint_path:
        return

    # Hợp đồng tenant kiểm TRƯỚC, ngoài khối `try` rộng bên dưới.
    #
    # Đặt phép kiểm này bên trong `try` là sai theo hai cách. Thứ nhất, mọi
    # ngoại lệ ở đó bị nuốt thành WARNING, nên một vi phạm hợp đồng trông y hệt
    # một trục trặc ghi đĩa. Thứ hai — và đây là cái test bắt được — nếu
    # `load_checkpoint` hỏng TRƯỚC khi tới phép kiểm, ta chỉ thấy cảnh báo về
    # checkpoint và không bao giờ biết job này còn thiếu tenant.
    #
    # Hai loại hỏng, hai cách xử:
    #     vi phạm hợp đồng   -> dừng sớm, ERROR, không ghi đi đâu cả
    #     hỏng thoáng qua    -> best effort, WARNING, job vẫn thành công
    tenant = str(row.get("tenant_id") or "").strip()
    if not tenant:
        # KHÔNG rơi về `default` — sửa 16/08/2026. Một job mất `tenant_id` mà
        # vẫn ghi sẽ đặt hợp đồng lớp đầu ra của mình VÀO TENANT KHỞI TẠO, tức
        # `Train(A)` làm biến đổi `default`. Không ghi còn hơn ghi nhầm chỗ:
        # bỏ qua chỉ mất bảng phụ trợ của MỘT job, ghi nhầm thì làm bẩn danh
        # mục của tenant khởi tạo và không ai biết để dọn.
        logger.error(
            "[TRAINER] job %s thieu tenant_id — KHONG ghi hop dong dau ra. "
            "Khong bao gio ghi vao pham vi 'default'.", job_id)
        return

    try:
        from app.checkpoint_io import load_checkpoint
        from app.storage import metadata_db as db

        ckpt = load_checkpoint(checkpoint_path)
        raw = ckpt.get("idx_to_label")
        if isinstance(raw, dict):
            pairs = [(int(k), str(v)) for k, v in raw.items()]
        elif isinstance(raw, (list, tuple)):
            pairs = [(i, str(v)) for i, v in enumerate(raw)]
        else:
            logger.warning("[TRAINER] job %s: checkpoint khong co idx_to_label — "
                           "khong ghi duoc hop dong dau ra", job_id)
            return

        db.replace_training_job_classes(
            job_id=job_id,
            tenant_id=tenant,
            pairs=sorted(pairs),
        )
        logger.info("[TRAINER] job %s: da ghi %d lop vao hop dong dau ra",
                    job_id, len(pairs))
    except Exception as exc:
        logger.warning("[TRAINER] job %s: khong ghi duoc training_job_classes: %s",
                       job_id, exc.__class__.__name__)


# ============================================================================
# Model backup + artifact retention
# ============================================================================

_DRIVE_UNSAFE_CHARS = re.compile(r"[/\\:*?\"<>|]+")


def _drive_safe_name(raw: str, fallback: str) -> str:
    """Make a Drive folder name from free text (tên hiển thị có dấu vẫn giữ)."""
    cleaned = _DRIVE_UNSAFE_CHARS.sub("-", str(raw or "").strip()).strip(". ")
    return cleaned or fallback


def _build_deploy_manifest(
    ckpt: Dict[str, Any],
    *,
    job_id: str,
    model_id: str,
    display_name: str,
    dialect: str,
    language: str,
    promoted_at: str,
    checkpoint_name: str,
    checkpoint_sha256: str,
    checkpoint_bytes: int,
) -> Dict[str, Any]:
    """Self-describing contract để app khác (mobile…) chạy được model này.

    Gom đủ thứ một client cần mà không phải mở file .pt: nhãn theo đúng thứ tự
    index, hợp đồng tiền xử lý, kích thước input, và hyperparams để dựng lại
    mạng TCN.
    """
    idx_to_label = ckpt.get("idx_to_label")
    if isinstance(idx_to_label, dict):
        # Khóa có thể là str sau khi qua JSON — sắp theo index số.
        labels = [idx_to_label[k] for k in sorted(idx_to_label, key=lambda x: int(x))]
    elif isinstance(idx_to_label, list):
        labels = idx_to_label
    else:
        labels = []

    return {
        "manifest_version": "1.0",
        "model_id": model_id,
        "display_name": display_name,
        "dialect": dialect,
        "language": language,
        "job_id": job_id,
        "promoted_at": promoted_at,
        "trained_at": ckpt.get("created_at"),
        "git_commit": ckpt.get("git_commit"),
        "framework": "pytorch",
        "model_type": str(ckpt.get("model_type", "TCN")),
        "checkpoint": {
            "filename": checkpoint_name,
            "sha256": checkpoint_sha256,
            "size_bytes": checkpoint_bytes,
            "state_dict_key": "model_state_dict",
        },
        "input": {
            "seq_len": ckpt.get("seq_len"),
            "feature_dim": ckpt.get("feature_dim"),
            "shape": [ckpt.get("seq_len"), ckpt.get("feature_dim")],
            "dtype": "float32",
            "normalization_version": ckpt.get("normalization_version"),
            "preprocess_contract": ckpt.get("preprocess_contract"),
        },
        "output": {
            "num_classes": ckpt.get("num_classes"),
            "labels": labels,
            "activation": "softmax",
        },
        "model_config": ckpt.get("model_config"),
        "metrics": ckpt.get("metrics"),
        "vocabulary_schema_version": ckpt.get("vocabulary_schema_version"),
        "dataset_version": ckpt.get("dataset_version"),
        "split_version": ckpt.get("split_version"),
    }


@celery_app.task(bind=True, max_retries=5, default_retry_delay=30)
def backup_promoted_checkpoint_task(
    self,
    job_id: str,
    checkpoint_path: str,
    model_id: str = "",
    display_name: str = "",
    dialect: str = "",
    language: str = "vn",
    promoted_at: str = "",
):
    """Publish a PROMOTED model to Google Drive as a self-contained deploy folder.

    Cấu trúc:  models/<Tên model>/Deploy <YYYY-MM-DD HH-MM-SS>/
                 ├── <checkpoint>.pt          bản weights đang chạy realtime
                 ├── <checkpoint>.json        sidecar cấu hình training (nếu có)
                 └── deploy_manifest.json     hợp đồng inference cho client ngoài

    Mỗi lần promote tạo một thư mục Deploy mới nên lịch sử triển khai giữ
    nguyên; `models/<Tên model>/latest_manifest.json` luôn trỏ bản mới nhất để
    mobile chỉ cần đọc một đường dẫn cố định. Chỉ model đã promote mới được đẩy
    lên — các run thử nghiệm trong outputs/ tái tạo được, không đáng băng thông.
    Lỗi ở đây không bao giờ chặn việc promote.
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

        promoted_at = promoted_at or datetime.now().isoformat()
        folder_name = _drive_safe_name(display_name or model_id or dialect, job_id)
        try:
            deploy_stamp = datetime.fromisoformat(promoted_at).strftime("%Y-%m-%d %H-%M-%S")
        except ValueError:
            deploy_stamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        deploy_dir = f"models/{folder_name}/Deploy {deploy_stamp}"

        logger.info("[MODEL_BACKUP] job %s uploading %s -> gdrive:%s/", job_id, src, deploy_dir)
        # replace_existing ở mọi upload: task này retry tới 5 lần, không có nó
        # thì mỗi lần retry lại đẻ thêm một bản trùng tên trong cùng thư mục.
        url = upload_to_gdrive(
            str(src), f"{deploy_dir}/{src.name}",
            content_type="application/octet-stream", make_public=False,
            replace_existing=True,
        )

        # Sidecar JSON (cấu hình training gốc) nếu có
        sidecar = src.with_suffix(".json")
        if sidecar.exists():
            try:
                upload_to_gdrive(str(sidecar), f"{deploy_dir}/{sidecar.name}",
                                 content_type="application/json", make_public=False,
                                 replace_existing=True)
            except Exception as e:
                logger.warning("[MODEL_BACKUP] sidecar upload failed: %s", e)

        # Manifest: đọc từ chính checkpoint đã deploy nên luôn khớp weights
        try:
            import hashlib

            import torch

            digest = hashlib.sha256()
            with src.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    digest.update(chunk)

            ckpt = load_checkpoint(str(src))
            manifest = _build_deploy_manifest(
                ckpt,
                job_id=job_id,
                model_id=model_id or dialect,
                display_name=display_name or model_id or dialect,
                dialect=dialect,
                language=language,
                promoted_at=promoted_at,
                checkpoint_name=src.name,
                checkpoint_sha256=digest.hexdigest(),
                checkpoint_bytes=src.stat().st_size,
            )
            payload = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")

            upload_to_gdrive(payload, f"{deploy_dir}/deploy_manifest.json",
                             content_type="application/json", make_public=False,
                             replace_existing=True)
            # Con trỏ ổn định cho client ngoài — ghi đè sau mỗi lần promote
            upload_to_gdrive(payload, f"models/{folder_name}/latest_manifest.json",
                             content_type="application/json", make_public=False,
                             replace_existing=True)
        except Exception as e:
            logger.warning("[MODEL_BACKUP] manifest build/upload failed: %s", e)

        logger.info("[MODEL_BACKUP] job %s ✓ published: %s", job_id, deploy_dir)
        return {"status": "success", "url": url, "deploy_dir": deploy_dir}
    except Exception as exc:
        logger.error("[MODEL_BACKUP] job %s failed: %s", job_id, exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, platform_wide=True)  # retention sweep across all tenants
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
