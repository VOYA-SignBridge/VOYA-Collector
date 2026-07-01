"""
Experiment Tracking and Model Version Management API.

Minimal wrapper for:
  - Creating and tracking training runs (experiments)
  - Logging per-epoch metrics during training
  - Registering trained model checkpoints (model_versions)

Usage:
  from app.storage.experiment_tracking_api import create_experiment, log_experiment_metric, create_model_version

  # Create experiment at start of training
  exp = create_experiment(
      dialect_id="hoa-de",
      model_architecture="TCNClassifier",
      hyperparameters={"lr": 0.001, "batch_size": 32, "epochs": 50}
  )
  exp_id = exp["experiment_id"]

  # Log metrics per epoch (inside training loop)
  for epoch in range(1, 51):
      train_loss, val_loss, val_acc, val_f1 = train_one_epoch(...)
      log_experiment_metric(
          experiment_id=exp_id,
          epoch=epoch,
          train_loss=train_loss,
          val_loss=val_loss,
          val_acc=val_acc,
          val_f1_macro=val_f1
      )

  # Update status when training completes
  update_experiment_status(exp_id, "completed")

  # Register model after training
  create_model_version(
      model_id="hoa-de",
      version_string="1.0.0",
      experiment_id=exp_id,
      checkpoint_path="checkpoints/tcn_dialect-hoa-de_20260601.pt",
      accuracy=0.945,
      f1_macro=0.943
  )
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.storage.metadata_db import _cursor

logger = logging.getLogger(__name__)


# ============================================================================
# Experiment Management
# ============================================================================

def create_experiment(
    dialect_id: str,
    model_architecture: str = "TCNClassifier",
    hyperparameters: Optional[Dict[str, Any]] = None,
    created_by: str = "system",
) -> Dict[str, Any]:
    """
    Create a new experiment record.

    Args:
        dialect_id: Dialect being trained (e.g., "hoa-de", "bang-chu-cai")
        model_architecture: Architecture name (default: "TCNClassifier")
        hyperparameters: Dict of training hyperparameters
        created_by: User/system creating this experiment

    Returns:
        Dict with experiment_id, status, created_at
    """
    with _cursor() as cur:
        hyperparams_json = json.dumps(hyperparameters or {})
        cur.execute("""
            INSERT INTO experiments
            (dialect_id, model_architecture, hyperparameters, status, created_by, created_at)
            VALUES (%s, %s, %s, 'running', %s, NOW())
            RETURNING experiment_id, status, created_at
        """, (dialect_id, model_architecture, hyperparams_json, created_by))

        row = cur.fetchone()
        if not row:
            raise RuntimeError("Failed to create experiment")

        return {
            "experiment_id": row[0],
            "status": row[1],
            "created_at": row[2],
        }


def log_experiment_metric(
    experiment_id: int,
    epoch: int,
    train_loss: Optional[float] = None,
    train_acc: Optional[float] = None,
    val_loss: Optional[float] = None,
    val_acc: Optional[float] = None,
    val_f1_macro: Optional[float] = None,
    val_f1_weighted: Optional[float] = None,
    learning_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Log per-epoch metrics for an experiment.

    Args:
        experiment_id: ID from create_experiment()
        epoch: Epoch number (1-indexed)
        train_loss: Training loss for this epoch
        train_acc: Training accuracy
        val_loss: Validation loss
        val_acc: Validation accuracy
        val_f1_macro: Macro-averaged F1 score
        val_f1_weighted: Weighted F1 score
        learning_rate: Learning rate used in this epoch

    Returns:
        Dict with metric_id, recorded_at
    """
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO experiment_metrics
            (experiment_id, epoch, train_loss, train_acc, val_loss, val_acc,
             val_f1_macro, val_f1_weighted, learning_rate, recorded_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING metric_id, recorded_at
        """, (experiment_id, epoch, train_loss, train_acc, val_loss, val_acc,
              val_f1_macro, val_f1_weighted, learning_rate))

        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"Failed to log metric for experiment {experiment_id}")

        return {"metric_id": row[0], "recorded_at": row[1]}


def update_experiment_status(
    experiment_id: int,
    status: str,
) -> Dict[str, Any]:
    """
    Update experiment status (e.g., running → completed).

    Args:
        experiment_id: Experiment to update
        status: New status ('pending', 'running', 'completed', 'failed')

    Returns:
        Dict with experiment_id, status, completed_at
    """
    if status not in ("pending", "running", "completed", "failed"):
        raise ValueError(f"Invalid status: {status}")

    with _cursor() as cur:
        completed_at_expr = "NOW()" if status == "completed" else "NULL"
        cur.execute(f"""
            UPDATE experiments
            SET status = %s, completed_at = {completed_at_expr}
            WHERE experiment_id = %s
            RETURNING experiment_id, status, completed_at
        """, (status, experiment_id))

        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"Experiment {experiment_id} not found")

        return {
            "experiment_id": row[0],
            "status": row[1],
            "completed_at": row[2],
        }


def get_experiment(experiment_id: int) -> Optional[Dict[str, Any]]:
    """
    Get full experiment record including all metrics.

    Args:
        experiment_id: Experiment to retrieve

    Returns:
        Dict with experiment data + metrics array, or None if not found
    """
    with _cursor() as cur:
        # Get experiment header
        cur.execute("""
            SELECT experiment_id, dialect_id, model_architecture,
                   hyperparameters, status, started_at, completed_at, created_at, created_by
            FROM experiments
            WHERE experiment_id = %s
        """, (experiment_id,))

        row = cur.fetchone()
        if not row:
            return None

        # Get all metrics for this experiment
        cur.execute("""
            SELECT epoch, train_loss, train_acc, val_loss, val_acc,
                   val_f1_macro, val_f1_weighted, learning_rate, recorded_at
            FROM experiment_metrics
            WHERE experiment_id = %s
            ORDER BY epoch
        """, (experiment_id,))

        metrics = [
            {
                "epoch": m[0],
                "train_loss": m[1],
                "train_acc": m[2],
                "val_loss": m[3],
                "val_acc": m[4],
                "val_f1_macro": m[5],
                "val_f1_weighted": m[6],
                "learning_rate": m[7],
                "recorded_at": m[8],
            }
            for m in cur.fetchall()
        ]

        return {
            "experiment_id": row[0],
            "dialect_id": row[1],
            "model_architecture": row[2],
            "hyperparameters": json.loads(row[3] or "{}"),
            "status": row[4],
            "started_at": row[5],
            "completed_at": row[6],
            "created_at": row[7],
            "created_by": row[8],
            "metrics": metrics,
        }


def list_experiments(
    dialect_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    List experiments with optional filtering.

    Args:
        dialect_id: Filter by dialect (e.g., "hoa-de")
        status: Filter by status
        limit: Max number of results

    Returns:
        List of experiment records (without metrics)
    """
    with _cursor() as cur:
        query = "SELECT experiment_id, dialect_id, status, created_at FROM experiments WHERE 1=1"
        params = []

        if dialect_id:
            query += " AND dialect_id = %s"
            params.append(dialect_id)

        if status:
            query += " AND status = %s"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        cur.execute(query, params)

        return [
            {
                "experiment_id": row[0],
                "dialect_id": row[1],
                "status": row[2],
                "created_at": row[3],
            }
            for row in cur.fetchall()
        ]


# ============================================================================
# Model Version Management
# ============================================================================

def create_model_version(
    model_id: str,
    version_string: str,
    experiment_id: Optional[int] = None,
    checkpoint_path: str = "",
    accuracy: Optional[float] = None,
    f1_macro: Optional[float] = None,
    feature_contract: Optional[Dict[str, Any]] = None,
    created_by: str = "system",
) -> Dict[str, Any]:
    """
    Register a new model version.

    Args:
        model_id: Model identifier (e.g., "hoa-de", "bang-chu-cai")
        version_string: Version identifier (e.g., "1.0.0-20260601")
        experiment_id: Link to training experiment (optional)
        checkpoint_path: Path to checkpoint file
        accuracy: Test accuracy metric
        f1_macro: Macro-averaged F1 score
        feature_contract: Feature specification dict
        created_by: Who created this version

    Returns:
        Dict with version_id, created_at
    """
    with _cursor() as cur:
        contract_json = json.dumps(feature_contract or {})
        cur.execute("""
            INSERT INTO model_versions
            (model_id, version_string, experiment_id, checkpoint_path,
             accuracy, f1_macro, feature_contract, status, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'candidate', %s, NOW())
            RETURNING version_id, created_at
        """, (model_id, version_string, experiment_id, checkpoint_path,
              accuracy, f1_macro, contract_json, created_by))

        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"Failed to create model version {model_id}:{version_string}")

        return {"version_id": row[0], "created_at": row[1]}


def update_model_version_status(
    version_id: int,
    status: str,
) -> Dict[str, Any]:
    """
    Update model version status (e.g., candidate → production).

    Args:
        version_id: Version to update
        status: New status ('candidate', 'staging', 'production')

    Returns:
        Dict with updated version info
    """
    if status not in ("candidate", "staging", "production"):
        raise ValueError(f"Invalid status: {status}")

    with _cursor() as cur:
        cur.execute("""
            UPDATE model_versions
            SET status = %s
            WHERE version_id = %s
            RETURNING version_id, model_id, version_string, status
        """, (status, version_id))

        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"Model version {version_id} not found")

        return {
            "version_id": row[0],
            "model_id": row[1],
            "version_string": row[2],
            "status": row[3],
        }


def get_active_model_version(model_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the current production model for a given model_id.

    Args:
        model_id: Model identifier

    Returns:
        Dict with version info, or None if no production version exists
    """
    with _cursor() as cur:
        cur.execute("""
            SELECT version_id, version_string, checkpoint_path, accuracy, f1_macro, created_at
            FROM model_versions
            WHERE model_id = %s AND status = 'production'
            ORDER BY created_at DESC
            LIMIT 1
        """, (model_id,))

        row = cur.fetchone()
        if not row:
            return None

        return {
            "version_id": row[0],
            "model_id": model_id,
            "version_string": row[1],
            "checkpoint_path": row[2],
            "accuracy": row[3],
            "f1_macro": row[4],
            "created_at": row[5],
        }


def get_latest_model_version(model_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the most recently created model version (any status).

    Args:
        model_id: Model identifier

    Returns:
        Dict with version info, or None if no versions exist
    """
    with _cursor() as cur:
        cur.execute("""
            SELECT version_id, version_string, checkpoint_path, accuracy, f1_macro, status, created_at
            FROM model_versions
            WHERE model_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (model_id,))

        row = cur.fetchone()
        if not row:
            return None

        return {
            "version_id": row[0],
            "model_id": model_id,
            "version_string": row[1],
            "checkpoint_path": row[2],
            "accuracy": row[3],
            "f1_macro": row[4],
            "status": row[5],
            "created_at": row[6],
        }


def list_model_versions(model_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    List all versions for a given model.

    Args:
        model_id: Model identifier
        limit: Max number of results

    Returns:
        List of version records
    """
    with _cursor() as cur:
        cur.execute("""
            SELECT version_id, version_string, accuracy, f1_macro, status, created_at
            FROM model_versions
            WHERE model_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (model_id, limit))

        return [
            {
                "version_id": row[0],
                "model_id": model_id,
                "version_string": row[1],
                "accuracy": row[2],
                "f1_macro": row[3],
                "status": row[4],
                "created_at": row[5],
            }
            for row in cur.fetchall()
        ]


def get_model_version(version_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific model version by ID.

    Args:
        version_id: Version ID to retrieve

    Returns:
        Dict with version info, or None if not found
    """
    with _cursor() as cur:
        cur.execute("""
            SELECT version_id, model_id, version_string, experiment_id,
                   checkpoint_path, accuracy, f1_macro, feature_contract, status, created_at
            FROM model_versions
            WHERE version_id = %s
        """, (version_id,))

        row = cur.fetchone()
        if not row:
            return None

        return {
            "version_id": row[0],
            "model_id": row[1],
            "version_string": row[2],
            "experiment_id": row[3],
            "checkpoint_path": row[4],
            "accuracy": row[5],
            "f1_macro": row[6],
            "feature_contract": json.loads(row[7] or "{}"),
            "status": row[8],
            "created_at": row[9],
        }
