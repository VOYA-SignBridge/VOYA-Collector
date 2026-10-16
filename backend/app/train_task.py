import logging
import os
import subprocess
from typing import Any, Dict, List, Optional

from app.worker import celery_app
from app.storage.experiment_tracking_api_revised import (
    get_experiment,
    update_experiment_status,
)

logger = logging.getLogger(__name__)

_TRAIN_SCRIPT = "/processed/train_utils/train_tcn.py"
_FEATURES_ROOT = "/dataset/features"
_OUT_DIR = "/checkpoints"
_API_URL = os.getenv("TRAINING_API_URL", "http://backend:8000/api/v1")

# All 9 hyperparameter keys stored in DB — map to CLI flags
_HP_FLAGS: Dict[str, str] = {
    "lr":           "--lr",
    "epochs":       "--epochs",
    "batch_size":   "--batch_size",
    "dropout":      "--dropout",
    "channels":     "--channels",
    "levels":       "--levels",
    "kernel_size":  "--kernel_size",
    "weight_decay": "--weight_decay",
    "seed":         "--seed",
}


def _normalize_path(db_path: str) -> str:
    """Map Windows absolute paths stored in DB to Linux container mount points.

    DB stores: E:\\VOYA\\VOYA-Collector\\processed\\...
    Container: /processed/...
    """
    p = db_path.replace("\\", "/")
    for win_prefix, linux_prefix in (
        ("E:/VOYA/VOYA-Collector/processed/",   "/processed/"),
        ("E:/VOYA/VOYA-Collector/dataset/",     "/dataset/"),
        ("E:/VOYA/VOYA-Collector/checkpoints/", "/checkpoints/"),
    ):
        if p.startswith(win_prefix):
            return linux_prefix + p[len(win_prefix):]
    return p


def _build_command(
    experiment_id: int,
    subset_path: str,
    dialect: Optional[str],
    hyperparameters: Dict[str, Any],
) -> List[str]:
    """Build subprocess argv for train_tcn.py from a DB experiment record.

    Replay-mode contract:
      - CSVs come from frozen snapshot: {normalized_subset_path}/{train,val,test}.csv
      - --features_root, --out_dir, --tag, --experiment-id, --track, --api-url always injected
      - --experiment-id wires train_tcn tracking to this experiment row (no new row created)
      - dialect "all" → no --dialect flags (subset_mode=False in train_tcn)
      - dialect "hoa-de+bang-chu-cai" → split on + → two --dialect flags
        (_parse_multi_values in train_tcn only splits on comma, not +)
    """
    base = _normalize_path(subset_path)

    cmd: List[str] = [
        "python", _TRAIN_SCRIPT,
        "--train_csv",     f"{base}/train.csv",
        "--val_csv",       f"{base}/val.csv",
        "--test_csv",      f"{base}/test.csv",
        "--features_root", _FEATURES_ROOT,
        "--out_dir",       _OUT_DIR,
        "--tag",           str(experiment_id),
        "--experiment-id", str(experiment_id),
        "--track",
        "--api-url",       _API_URL,
    ]

    if dialect and dialect.lower() != "all":
        for d in dialect.split("+"):
            d = d.strip()
            if d:
                cmd.extend(["--dialect", d])

    for key, flag in _HP_FLAGS.items():
        value = hyperparameters.get(key)
        if value is not None:
            cmd.extend([flag, str(value)])

    return cmd


@celery_app.task(bind=True, name="app.tasks.run_training_job")
def run_training_job(self, experiment_id: int) -> Dict[str, Any]:
    """Replay training from the frozen snapshot defined by experiment_id.

    Status lifecycle managed entirely here — tracking_client.py is absent so
    train_tcn.py's --track flag is silently disabled by its own import guard,
    and it never calls the API.

    Transitions:
        pending  -> running   (before subprocess)
        running  -> completed (exit code 0)
        running  -> failed    (exit code != 0 or exception)
    """
    logger.info("[TRAIN][%d] task received", experiment_id)

    record = get_experiment(experiment_id)
    if record is None:
        raise ValueError(f"Experiment {experiment_id} not found in DB")

    subset_path = record["subset_path"]
    dialect = record.get("dialect")
    hyperparameters = record.get("hyperparameters") or {}

    cmd = _build_command(experiment_id, subset_path, dialect, hyperparameters)
    logger.info("[TRAIN][%d] command:\n  %s", experiment_id, "\n  ".join(cmd))

    update_experiment_status(experiment_id, "running")
    logger.info("[TRAIN][%d] status -> running", experiment_id)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)

        if proc.stdout:
            logger.info("[TRAIN][%d] stdout (last 4000):\n%s",
                        experiment_id, proc.stdout[-4000:])
        if proc.stderr:
            logger.warning("[TRAIN][%d] stderr (last 4000):\n%s",
                           experiment_id, proc.stderr[-4000:])
        logger.info("[TRAIN][%d] exit code: %d", experiment_id, proc.returncode)

        if proc.returncode == 0:
            # Guard: an external process may have already set a terminal status.
            current = get_experiment(experiment_id)
            if current and current["status"] not in ("completed", "failed"):
                update_experiment_status(experiment_id, "completed")
                logger.info("[TRAIN][%d] status -> completed", experiment_id)
            return {
                "experiment_id": experiment_id,
                "status":        "completed",
                "exit_code":     proc.returncode,
            }

        update_experiment_status(experiment_id, "failed")
        logger.error("[TRAIN][%d] status -> failed (exit %d)",
                     experiment_id, proc.returncode)
        return {
            "experiment_id": experiment_id,
            "status":        "failed",
            "exit_code":     proc.returncode,
            "stderr_tail":   proc.stderr[-2000:] if proc.stderr else "",
        }

    except Exception as exc:
        logger.exception("[TRAIN][%d] subprocess raised: %s", experiment_id, exc)
        try:
            update_experiment_status(experiment_id, "failed")
        except Exception:
            pass
        raise
