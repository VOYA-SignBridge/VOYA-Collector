"""
Experiment Tracking Storage Layer — SignBridge MVP

Provides database access for the 3-table MVP schema defined in
migrations/002_mvp_schema.sql:

  - experiments        : one row per training run
  - experiment_metrics : one row per epoch per experiment
  - model_versions     : registered checkpoints ready for inference

Schema anchors reproducibility via subset_path (frozen snapshot directory)
and feature_contract (JSONB describing the feature extraction pipeline).

Usage:
    from app.storage.experiment_tracking_api_revised import (
        validate_schema,
        create_experiment,
        log_metric,
        update_experiment_status,
        update_experiment_summary,
        create_model_version,
        update_model_status,
        get_best_model_for_dialect,
        get_experiment,
        list_experiments,
        list_models,
    )

    validate_schema()   # call once at startup

    exp = create_experiment(
        dialect="hoa-de",
        subset_path="outputs/subset_hoa-de_20260603_120000",
        hyperparameters={"lr": 0.001, "batch_size": 32, "epochs": 80},
    )
    exp_id = exp["experiment_id"]

    update_experiment_status(exp_id, "running")

    for epoch in range(1, 81):
        log_metric(exp_id, epoch, train_loss=..., train_acc=...,
                   val_loss=..., val_acc=..., val_f1=...)

    update_experiment_status(exp_id, "completed")
    update_experiment_summary(exp_id, best_epoch=45, best_val_acc=0.924, best_val_f1=0.891)

    mv = create_model_version(
        model_family="hoa-de-tcn",
        experiment_id=exp_id,
        dialect="hoa-de",
        checkpoint_path="outputs/tcn_hoa-de_20260603_120000.pt",
        feature_contract={
            "extractor": "mediapipe_hands",
            "extractor_version": "0.9.3",
            "input_shape": [60, 126],
            "normalization": "current_v1",
        },
    )

    update_model_status(mv["version_id"], "production")

    best = get_best_model_for_dialect("hoa-de", status="production")
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.storage.metadata_db import _cursor

logger = logging.getLogger(__name__)

# Valid status values — enforced at the Python layer before DB writes
_EXPERIMENT_STATUSES = frozenset({"pending", "queued", "running", "completed", "failed"})
_MODEL_STATUSES = frozenset({"candidate", "production", "archived"})

# Safe ORDER BY columns for list_experiments — never accept arbitrary user strings
_ALLOWED_EXPERIMENT_ORDER = frozenset({"best_val_f1", "best_val_acc", "created_at"})


# ============================================================================
# Schema Validation
# ============================================================================

def validate_schema() -> None:
    """
    Verify that all three MVP tables exist in the database.

    Purpose:
        Startup guard. Confirms migration 002_mvp_schema.sql has been applied
        before the application begins accepting requests. Does NOT create or
        modify tables — schema management belongs to migrations, not runtime code.

    Parameters:
        None

    Returns:
        None on success.

    Failure behavior:
        Raises RuntimeError with a clear human-readable message if any table
        is missing. Caller (e.g., FastAPI startup event) should catch this and
        halt startup.
    """
    required_tables = ("experiments", "experiment_metrics", "model_versions")
    with _cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
            """,
            (list(required_tables),),
        )
        found = {row[0] for row in cur.fetchall()}

    missing = [t for t in required_tables if t not in found]
    if missing:
        raise RuntimeError(
            f"Experiment tracking schema not found. "
            f"Missing tables: {missing}. "
            f"Run migration 002_mvp_schema.sql before starting the server."
        )

    logger.info("Experiment tracking schema validated: all 3 tables present.")


# ============================================================================
# Experiment Management
# ============================================================================

def create_experiment(
    dialect: str,
    subset_path: str,
    hyperparameters: Dict[str, Any],
    split_manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a new experiment record with status 'pending'.

    Purpose:
        Called at the start of a training run, before any epochs execute.
        The returned experiment_id must be stored by the caller and passed
        to log_metric() and update_experiment_status() throughout training.

    Parameters:
        dialect       : Dialect being trained. E.g. "hoa-de", "can-tho".
        subset_path   : Path to the frozen subset snapshot directory.
                        E.g. "outputs/subset_hoa-de_20260603_120000".
                        This is the reproducibility anchor — it points to
                        the frozen train/val/test CSVs and label mappings.
        hyperparameters : Dict of training configuration. Will be stored as JSONB.
                        E.g. {"lr": 0.001, "batch_size": 32, "epochs": 80,
                               "dropout": 0.3, "channels": 64}.
        split_manifest  : Optional dict with split counts/hashes for fast dashboard
                        queries without reading the filesystem.
                        E.g. {"train_count": 150, "val_count": 30, "test_count": 20}.

    Returns:
        {
            "experiment_id": int,
            "dialect":       str,
            "status":        "pending",
            "subset_path":   str,
            "created_at":    datetime,
        }

    Failure behavior:
        Raises RuntimeError if the INSERT fails (e.g., DB constraint violation).
        Does NOT catch connection errors — callers should treat those as fatal.
    """
    hyperparams_json = json.dumps(hyperparameters or {})
    split_json = json.dumps(split_manifest) if split_manifest is not None else None

    with _cursor() as cur:
        cur.execute(
            """
            INSERT INTO experiments
                (dialect, status, subset_path, split_manifest, hyperparameters, created_at)
            VALUES (%s, 'pending', %s, %s, %s, NOW())
            RETURNING experiment_id, dialect, status, subset_path, created_at
            """,
            (dialect, subset_path, split_json, hyperparams_json),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(
                f"Failed to create experiment for dialect '{dialect}'"
            )

        return {
            "experiment_id": row[0],
            "dialect":       row[1],
            "status":        row[2],
            "subset_path":   row[3],
            "created_at":    row[4],
        }


def get_experiment(experiment_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve a single experiment record including all per-epoch metrics.

    Purpose:
        Used by the API layer to serve experiment detail pages. Returns
        the full experiment header plus the complete learning curve as
        a nested list. JSONB fields are deserialized to Python dicts.

    Parameters:
        experiment_id : Integer PK from create_experiment().

    Returns:
        Full experiment dict with nested "metrics" list, or None if not found.

        {
            "experiment_id":  int,
            "dialect":        str,
            "status":         str,
            "subset_path":    str,
            "split_manifest": dict,
            "hyperparameters": dict,
            "best_epoch":     int | None,
            "best_val_acc":   float | None,
            "best_val_f1":    float | None,
            "created_at":     datetime,
            "completed_at":   datetime | None,
            "metrics": [
                {
                    "epoch":         int,
                    "train_loss":    float | None,
                    "train_acc":     float | None,
                    "val_loss":      float | None,
                    "val_acc":       float | None,
                    "val_f1":        float | None,
                    "learning_rate": float | None,
                    "recorded_at":   datetime,
                },
                ...
            ]
        }

    Failure behavior:
        Returns None if experiment_id does not exist. Raises on DB errors.
    """
    with _cursor() as cur:
        cur.execute(
            """
            SELECT experiment_id, dialect, status, subset_path,
                   split_manifest, hyperparameters,
                   best_epoch, best_val_acc, best_val_f1,
                   created_at, completed_at
            FROM experiments
            WHERE experiment_id = %s
            """,
            (experiment_id,),
        )
        row = cur.fetchone()
        if not row:
            return None

        cur.execute(
            """
            SELECT epoch, train_loss, train_acc, val_loss, val_acc,
                   val_f1, learning_rate, recorded_at
            FROM experiment_metrics
            WHERE experiment_id = %s
            ORDER BY epoch ASC
            """,
            (experiment_id,),
        )
        metrics = [
            {
                "epoch":         m[0],
                "train_loss":    m[1],
                "train_acc":     m[2],
                "val_loss":      m[3],
                "val_acc":       m[4],
                "val_f1":        m[5],
                "learning_rate": m[6],
                "recorded_at":   m[7],
            }
            for m in cur.fetchall()
        ]

    def _j(val):
        # psycopg2 may auto-deserialize JSONB to dict; handle both str and dict
        if not val:
            return {}
        return val if isinstance(val, dict) else json.loads(val)

    return {
        "experiment_id":   row[0],
        "dialect":         row[1],
        "status":          row[2],
        "subset_path":     row[3],
        "split_manifest":  _j(row[4]),
        "hyperparameters": _j(row[5]),
        "best_epoch":      row[6],
        "best_val_acc":    row[7],
        "best_val_f1":     row[8],
        "created_at":      row[9],
        "completed_at":    row[10],
        "metrics":         metrics,
    }


def list_experiments(
    dialect: Optional[str] = None,
    status: Optional[str] = None,
    order_by: str = "created_at",
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    List experiments with optional dialect and status filters.

    Purpose:
        Powers the experiment list view in the API. Returns summary rows —
        does NOT include per-epoch metrics (use get_experiment for that).
        Best summary fields (best_epoch, best_val_acc, best_val_f1) are
        denormalized on the experiments table for zero-aggregation queries.

    Parameters:
        dialect  : Filter to a specific dialect. None returns all dialects.
        status   : Filter by status ('pending', 'running', 'completed', 'failed').
                   None returns all statuses.
        order_by : Sort column. Must be one of 'best_val_f1', 'best_val_acc',
                   'created_at'. Defaults to 'created_at' (most recent first).
                   Invalid values fall back to 'created_at'.
        limit    : Maximum rows to return. Default 100.

    Returns:
        List of experiment summary dicts (may be empty). Each dict:
        {
            "experiment_id": int,
            "dialect":       str,
            "status":        str,
            "subset_path":   str,
            "best_epoch":    int | None,
            "best_val_acc":  float | None,
            "best_val_f1":   float | None,
            "created_at":    datetime,
            "completed_at":  datetime | None,
        }

    Failure behavior:
        Returns empty list if no experiments match. Raises on DB errors.
    """
    order_col = order_by if order_by in _ALLOWED_EXPERIMENT_ORDER else "created_at"

    query = """
        SELECT experiment_id, dialect, status, subset_path,
               best_epoch, best_val_acc, best_val_f1,
               created_at, completed_at
        FROM experiments
        WHERE 1=1
    """
    params: List[Any] = []

    if dialect is not None:
        query += " AND dialect = %s"
        params.append(dialect)

    if status is not None:
        query += " AND status = %s"
        params.append(status)

    query += f" ORDER BY {order_col} DESC NULLS LAST LIMIT %s"
    params.append(limit)

    with _cursor() as cur:
        cur.execute(query, params)
        return [
            {
                "experiment_id": row[0],
                "dialect":       row[1],
                "status":        row[2],
                "subset_path":   row[3],
                "best_epoch":    row[4],
                "best_val_acc":  row[5],
                "best_val_f1":   row[6],
                "created_at":    row[7],
                "completed_at":  row[8],
            }
            for row in cur.fetchall()
        ]


def list_models(
    dialect: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    List model versions with optional dialect and status filters.

    Purpose:
        Exists primarily for API convenience and UI support — not a core
        provenance requirement. Provenance is anchored by subset_path in the
        experiments table and feature_contract in model_versions. This function
        provides a simple flat listing for dashboards and API consumers.

    Parameters:
        dialect : Filter to a specific dialect. None returns all dialects.
        status  : Filter by status ('candidate', 'production', 'archived').
                  None returns all statuses. Invalid value raises ValueError.
        limit   : Maximum rows to return. Default 100.

    Returns:
        List of model version dicts (may be empty). Each dict matches the
        shape returned by get_best_model_for_dialect() including deserialized
        JSONB fields.

    Failure behavior:
        Raises ValueError for invalid status values. Returns empty list if
        no models match. Raises on DB errors.
    """
    conditions: List[str] = []
    params: List[Any] = []

    if dialect is not None:
        conditions.append("dialect = %s")
        params.append(dialect)

    if status is not None:
        if status not in _MODEL_STATUSES:
            raise ValueError(
                f"Invalid model status '{status}'. "
                f"Must be one of: {sorted(_MODEL_STATUSES)}"
            )
        conditions.append("status = %s")
        params.append(status)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    with _cursor() as cur:
        cur.execute(
            f"""
            SELECT version_id, model_family, version_string, experiment_id, dialect,
                   checkpoint_path, feature_contract, runtime_env,
                   accuracy, f1_macro, status, created_at
            FROM model_versions
            {where}
            ORDER BY created_at DESC NULLS LAST
            LIMIT %s
            """,
            params,
        )
        def _j(val):
            if not val:
                return {}
            return val if isinstance(val, dict) else json.loads(val)

        return [
            {
                "version_id":       row[0],
                "model_family":     row[1],
                "version_string":   row[2],
                "experiment_id":    row[3],
                "dialect":          row[4],
                "checkpoint_path":  row[5],
                "feature_contract": _j(row[6]),
                "runtime_env":      _j(row[7]),
                "accuracy":         row[8],
                "f1_macro":         row[9],
                "status":           row[10],
                "created_at":       row[11],
            }
            for row in cur.fetchall()
        ]


def log_metric(
    experiment_id: int,
    epoch: int,
    train_loss: Optional[float] = None,
    train_acc: Optional[float] = None,
    val_loss: Optional[float] = None,
    val_acc: Optional[float] = None,
    val_f1: Optional[float] = None,
    learning_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Insert one epoch of training metrics. Idempotent via ON CONFLICT upsert.

    Purpose:
        Called once per epoch inside the training loop. If called twice for
        the same (experiment_id, epoch) — e.g. due to a retry — the existing
        row is updated with the new values rather than raising a duplicate key
        error. This makes the training loop retry-safe.

    Parameters:
        experiment_id : Integer from create_experiment().
        epoch         : Epoch number (1-indexed).
        train_loss    : Training loss for this epoch.
        train_acc     : Training accuracy (0.0 to 1.0).
        val_loss      : Validation loss.
        val_acc       : Validation accuracy (0.0 to 1.0).
        val_f1        : Validation macro F1 score (0.0 to 1.0).
        learning_rate : Learning rate used this epoch.

    Returns:
        {
            "metric_id":     int,
            "experiment_id": int,
            "epoch":         int,
            "val_acc":       float | None,
            "val_f1":        float | None,
            "recorded_at":   datetime,
        }

    Failure behavior:
        Raises RuntimeError if the upsert returns no row (should not happen
        under normal conditions). FK violation (invalid experiment_id) raises
        psycopg2.errors.ForeignKeyViolation — not suppressed.
    """
    with _cursor() as cur:
        cur.execute(
            """
            INSERT INTO experiment_metrics
                (experiment_id, epoch, train_loss, train_acc,
                 val_loss, val_acc, val_f1, learning_rate, recorded_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (experiment_id, epoch) DO UPDATE SET
                train_loss    = EXCLUDED.train_loss,
                train_acc     = EXCLUDED.train_acc,
                val_loss      = EXCLUDED.val_loss,
                val_acc       = EXCLUDED.val_acc,
                val_f1        = EXCLUDED.val_f1,
                learning_rate = EXCLUDED.learning_rate,
                recorded_at   = NOW()
            RETURNING metric_id, experiment_id, epoch, val_acc, val_f1, recorded_at
            """,
            (experiment_id, epoch, train_loss, train_acc,
             val_loss, val_acc, val_f1, learning_rate),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(
                f"Failed to log metric for experiment {experiment_id} epoch {epoch}"
            )

        return {
            "metric_id":     row[0],
            "experiment_id": row[1],
            "epoch":         row[2],
            "val_acc":       row[3],
            "val_f1":        row[4],
            "recorded_at":   row[5],
        }


def update_experiment_status(
    experiment_id: int,
    new_status: str,
) -> Dict[str, Any]:
    """
    Transition an experiment's status. Sets completed_at on terminal transitions.

    Purpose:
        Called by the training script at key lifecycle points:
          - "running"   immediately after training starts
          - "completed" after training finishes successfully
          - "failed"    in the except block of the training loop

    Parameters:
        experiment_id : Integer from create_experiment().
        new_status    : One of 'pending', 'running', 'completed', 'failed'.

    Returns:
        {
            "experiment_id": int,
            "status":        str,
            "completed_at":  datetime | None,
        }

    Failure behavior:
        Raises ValueError immediately (before any DB call) if new_status is
        not a valid enum value. Raises RuntimeError if the experiment_id does
        not exist (RETURNING returned no row).
    """
    if new_status not in _EXPERIMENT_STATUSES:
        raise ValueError(
            f"Invalid experiment status '{new_status}'. "
            f"Must be one of: {sorted(_EXPERIMENT_STATUSES)}"
        )

    terminal = new_status in ("completed", "failed")

    with _cursor() as cur:
        cur.execute(
            """
            UPDATE experiments
            SET status       = %s,
                completed_at = CASE WHEN %s THEN NOW() ELSE completed_at END
            WHERE experiment_id = %s
            RETURNING experiment_id, status, completed_at
            """,
            (new_status, terminal, experiment_id),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(
                f"Experiment {experiment_id} not found — cannot update status"
            )

        return {
            "experiment_id": row[0],
            "status":        row[1],
            "completed_at":  row[2],
        }


def mark_experiment_starting(experiment_id: int) -> Optional[Dict[str, Any]]:
    """
    Atomically claim the right to start an experiment.

    Transitions status from ('pending' | 'failed') → 'queued' in a single
    atomic UPDATE. Returns the updated row if the claim succeeded; None if
    the experiment does not exist or its status is not in {'pending', 'failed'}.

    Callers must call get_experiment() first to distinguish 404 (not found)
    from 409 (wrong status) — this function cannot tell the difference between
    a missing row and a row with a non-startable status.
    """
    with _cursor() as cur:
        cur.execute(
            """
            UPDATE experiments
            SET status = 'queued'
            WHERE experiment_id = %s
              AND status IN ('pending', 'failed')
            RETURNING experiment_id, dialect, status
            """,
            (experiment_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "experiment_id": row[0],
        "dialect":       row[1],
        "status":        row[2],
    }


def update_experiment_summary(
    experiment_id: int,
    best_epoch: int,
    best_val_acc: float,
    best_val_f1: float,
) -> Dict[str, Any]:
    """
    Write cached summary metrics to the experiments row after training ends.

    Purpose:
        Called once after the training loop completes (after update_experiment_status
        with 'completed'). Writes the three best-of-run metrics that allow fast
        dashboard queries without aggregating the metrics table.

        Does NOT change the experiment status — call update_experiment_status first.

    Parameters:
        experiment_id : Integer from create_experiment().
        best_epoch    : Which epoch produced the best val checkpoint.
        best_val_acc  : Best validation accuracy observed across all epochs.
        best_val_f1   : Best validation macro F1 observed across all epochs.

    Returns:
        {
            "experiment_id": int,
            "best_epoch":    int,
            "best_val_acc":  float,
            "best_val_f1":   float,
        }

    Failure behavior:
        Raises RuntimeError if the experiment_id does not exist.
    """
    with _cursor() as cur:
        cur.execute(
            """
            UPDATE experiments
            SET best_epoch   = %s,
                best_val_acc = %s,
                best_val_f1  = %s
            WHERE experiment_id = %s
            RETURNING experiment_id, best_epoch, best_val_acc, best_val_f1
            """,
            (best_epoch, best_val_acc, best_val_f1, experiment_id),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(
                f"Experiment {experiment_id} not found — cannot update summary"
            )

        return {
            "experiment_id": row[0],
            "best_epoch":    row[1],
            "best_val_acc":  row[2],
            "best_val_f1":   row[3],
        }


# ============================================================================
# Model Version Management
# ============================================================================

def create_model_version(
    model_family: str,
    experiment_id: int,
    dialect: str,
    checkpoint_path: str,
    feature_contract: Dict[str, Any],
    runtime_env: Optional[Dict[str, Any]] = None,
    accuracy: Optional[float] = None,
    f1_macro: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Register a trained checkpoint as a candidate model version.

    Purpose:
        Called after training is complete and the checkpoint is saved.
        Generates version_string automatically as "{model_family}-v{experiment_id}"
        so version numbering is deterministic and traceable back to training.
        New versions always start with status='candidate'.

    Parameters:
        model_family    : Encodes dialect + architecture.
                          E.g. "hoa-de-tcn", "can-tho-tcn".
                          Allows multiple architectures per dialect without schema changes.
        experiment_id   : Integer from create_experiment(). FK to experiments table.
                          Also determines the auto-generated version_string.
        dialect         : Dialect this model is trained for. Denormalized from
                          model_family for index efficiency on dialect-scoped queries.
        checkpoint_path : Filesystem path to the saved .pt file.
                          E.g. "outputs/tcn_hoa-de_20260603_120000.pt".
        feature_contract : Required. Documents what feature extraction this model
                          expects at inference time. Must be preserved for future
                          compatibility checks if the feature pipeline changes.
                          E.g. {
                            "extractor": "mediapipe_hands",
                            "extractor_version": "0.9.3",
                            "input_shape": [60, 126],
                            "normalization": "current_v1",
                          }
        runtime_env     : Optional. Python/PyTorch/CUDA versions for reproducibility
                          hygiene. E.g. {"pytorch_version": "2.0.1", "cuda": "11.8"}.
        accuracy        : Validation accuracy at best_epoch.
        f1_macro        : Validation macro F1 at best_epoch.

    Returns:
        {
            "version_id":     int,
            "model_family":   str,
            "version_string": str,   # auto-generated: "{model_family}-v{experiment_id}"
            "dialect":        str,
            "status":         "candidate",
            "created_at":     datetime,
        }

    Failure behavior:
        Raises RuntimeError on insert failure (e.g., UNIQUE violation if the
        same experiment_id + model_family combination is registered twice).

    # TODO: Future Model Registry enhancement — enforce that only one model version
    # per dialect may hold status='production' at a time. This is intentionally
    # deferred from Phase 2 MVP scope. For now, multiple production versions per
    # dialect are allowed. When implementing: add a partial unique index or
    # enforce in update_model_status() by demoting previous production versions
    # before promoting the new one.
    """
    version_string = f"{model_family}-v{experiment_id}"
    contract_json = json.dumps(feature_contract)
    runtime_json = json.dumps(runtime_env) if runtime_env is not None else None

    with _cursor() as cur:
        cur.execute(
            """
            INSERT INTO model_versions
                (model_family, version_string, experiment_id, dialect,
                 checkpoint_path, feature_contract, runtime_env,
                 accuracy, f1_macro, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'candidate', NOW())
            RETURNING version_id, model_family, version_string, dialect, status, created_at
            """,
            (model_family, version_string, experiment_id, dialect,
             checkpoint_path, contract_json, runtime_json,
             accuracy, f1_macro),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(
                f"Failed to register model version '{version_string}' "
                f"for family '{model_family}'"
            )

        return {
            "version_id":     row[0],
            "model_family":   row[1],
            "version_string": row[2],
            "dialect":        row[3],
            "status":         row[4],
            "created_at":     row[5],
        }


def update_model_status(
    version_id: int,
    new_status: str,
) -> Dict[str, Any]:
    """
    Promote or archive a model version.

    Purpose:
        Controls the model lifecycle: candidate → production → archived.
        Typical flow: create_model_version() produces 'candidate'; after
        manual or automated validation, caller promotes to 'production';
        when superseded, moves to 'archived'.

    Parameters:
        version_id : Integer PK from create_model_version().
        new_status : One of 'candidate', 'production', 'archived'.

    Returns:
        {
            "version_id":     int,
            "model_family":   str,
            "version_string": str,
            "dialect":        str,
            "status":         str,
        }

    Failure behavior:
        Raises ValueError immediately (before DB call) for invalid status values.
        Raises RuntimeError if version_id does not exist.
    """
    if new_status not in _MODEL_STATUSES:
        raise ValueError(
            f"Invalid model status '{new_status}'. "
            f"Must be one of: {sorted(_MODEL_STATUSES)}"
        )

    with _cursor() as cur:
        cur.execute(
            """
            UPDATE model_versions
            SET status = %s
            WHERE version_id = %s
            RETURNING version_id, model_family, version_string, dialect, status
            """,
            (new_status, version_id),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(
                f"Model version {version_id} not found — cannot update status"
            )

        return {
            "version_id":     row[0],
            "model_family":   row[1],
            "version_string": row[2],
            "dialect":        row[3],
            "status":         row[4],
        }


def get_model_version(version_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch a single model version by primary key.

    Returns the full model version dict including promoted_at, or None if the
    version_id does not exist. Used by the promote endpoint for pre-flight
    checks (404/409/422) before calling promote_model_version().
    """
    with _cursor() as cur:
        cur.execute(
            """
            SELECT version_id, model_family, version_string, experiment_id, dialect,
                   checkpoint_path, feature_contract, runtime_env,
                   accuracy, f1_macro, status, created_at, promoted_at
            FROM model_versions
            WHERE version_id = %s
            """,
            (version_id,),
        )
        row = cur.fetchone()

    if row is None:
        return None

    def _j(val):
        if not val:
            return {}
        return val if isinstance(val, dict) else json.loads(val)

    return {
        "version_id":       row[0],
        "model_family":     row[1],
        "version_string":   row[2],
        "experiment_id":    row[3],
        "dialect":          row[4],
        "checkpoint_path":  row[5],
        "feature_contract": _j(row[6]),
        "runtime_env":      _j(row[7]),
        "accuracy":         row[8],
        "f1_macro":         row[9],
        "status":           row[10],
        "created_at":       row[11],
        "promoted_at":      row[12],
    }


class _PromotionRace(Exception):
    """Raised inside _cursor() when step-3 UPDATE returns 0 rows, forcing rollback."""


def promote_model_version(version_id: int) -> Optional[Dict[str, Any]]:
    """
    Atomically promote a candidate model to production for its dialect.

    Transaction flow (single connection, single COMMIT):
        1. SELECT dialect WHERE version_id = X AND status = 'candidate'.
           Returns None immediately if version_id is missing or not candidate.
        2. UPDATE SET status='archived', promoted_at=NULL WHERE dialect=X AND
           status='production' AND version_id != X. The version_id guard prevents
           archiving a concurrently-promoted copy of the target version itself.
           Zero rows affected is acceptable (no prior production model).
        3. UPDATE SET status='production', promoted_at=NOW() WHERE version_id=X
           AND status='candidate' RETURNING .... Raises _PromotionRace (forcing
           full rollback including step 2) if a concurrent transaction changed the
           status between step 1 and step 3. Returns None after rollback.

    Returns:
        Promoted row dict on success:
        {
            "version_id":      int,
            "model_family":    str,
            "version_string":  str,
            "dialect":         str,
            "checkpoint_path": str,
            "status":          "production",
            "promoted_at":     datetime,
        }

        None if version_id does not exist, is not 'candidate', or was
        concurrently modified between the SELECT and the final UPDATE.
        In the concurrent-modification case the archive from step 2 is also
        rolled back — the dialect never loses its production model.

    Raises:
        psycopg2.errors.UniqueViolation when a concurrent promotion for the
        same dialect commits first, violating idx_one_production_per_dialect.
        Caller maps this to HTTP 409.
    """
    try:
        with _cursor() as cur:
            # Step 1: read dialect — also verifies candidate status atomically
            cur.execute(
                """
                SELECT dialect FROM model_versions
                WHERE version_id = %s
                  AND status     = 'candidate'
                """,
                (version_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            dialect = row[0]

            # Step 2: archive current production row for this dialect (0 rows OK).
            # AND version_id != %s: if two concurrent requests both promote version X,
            # the second must not archive the production row the first just created.
            # Without this guard, Tx B's step 2 would archive Tx A's committed
            # production row, leaving 0 production models for the dialect.
            cur.execute(
                """
                UPDATE model_versions
                   SET status      = 'archived',
                       promoted_at = NULL
                 WHERE dialect     = %s
                   AND status      = 'production'
                   AND version_id != %s
                """,
                (dialect, version_id),
            )

            # Step 3: promote target — RETURNING detects concurrent race.
            # Must raise (not return) on 0 rows so psycopg2 rolls back step 2.
            # A plain return here would commit the archive without a new production
            # row, leaving the dialect with zero production models.
            cur.execute(
                """
                UPDATE model_versions
                   SET status      = 'production',
                       promoted_at = NOW()
                 WHERE version_id = %s
                   AND status     = 'candidate'
                RETURNING version_id, model_family, version_string, dialect,
                          checkpoint_path, status, promoted_at
                """,
                (version_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise _PromotionRace  # triggers conn.rollback() via with conn:
    except _PromotionRace:
        return None

    return {
        "version_id":      row[0],
        "model_family":    row[1],
        "version_string":  row[2],
        "dialect":         row[3],
        "checkpoint_path": row[4],
        "status":          row[5],
        "promoted_at":     row[6],
    }


def get_best_model_for_dialect(
    dialect: str,
    status: str = "production",
) -> Optional[Dict[str, Any]]:
    """
    Return the most recently registered model for a dialect at a given status.

    Purpose:
        Primary query for inference routing — "which model should serve this
        dialect?" Returns the latest (by created_at) model matching the
        dialect + status filter. When serving production traffic, call with
        status='production'. When evaluating candidates, use status='candidate'.

    Parameters:
        dialect : Dialect to look up. E.g. "hoa-de", "can-tho".
        status  : Model status filter. Default 'production'.
                  Must be one of 'candidate', 'production', 'archived'.

    Returns:
        Full model version dict with deserialized JSONB fields, or None if
        no model exists for this dialect at the given status.

        {
            "version_id":      int,
            "model_family":    str,
            "version_string":  str,
            "dialect":         str,
            "checkpoint_path": str,
            "feature_contract": dict,
            "runtime_env":     dict,
            "accuracy":        float | None,
            "f1_macro":        float | None,
            "status":          str,
            "created_at":      datetime,
            "experiment_id":   int,
        }

    Failure behavior:
        Raises ValueError for invalid status values (prevents accidental
        queries against the wrong status tier). Returns None (not an error)
        if no model found for the given dialect + status combination.
    """
    if status not in _MODEL_STATUSES:
        raise ValueError(
            f"Invalid model status '{status}'. "
            f"Must be one of: {sorted(_MODEL_STATUSES)}"
        )

    with _cursor() as cur:
        cur.execute(
            """
            SELECT version_id, model_family, version_string, dialect,
                   checkpoint_path, feature_contract, runtime_env,
                   accuracy, f1_macro, status, created_at, experiment_id
            FROM model_versions
            WHERE dialect = %s
              AND status  = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (dialect, status),
        )
        row = cur.fetchone()
        if not row:
            return None

        def _j(val):
            if not val:
                return {}
            return val if isinstance(val, dict) else json.loads(val)

        return {
            "version_id":       row[0],
            "model_family":     row[1],
            "version_string":   row[2],
            "dialect":          row[3],
            "checkpoint_path":  row[4],
            "feature_contract": _j(row[5]),
            "runtime_env":      _j(row[6]),
            "accuracy":         row[7],
            "f1_macro":         row[8],
            "status":           row[9],
            "created_at":       row[10],
            "experiment_id":    row[11],
        }
