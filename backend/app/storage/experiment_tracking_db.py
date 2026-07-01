"""
Experiment Tracking & Model Versioning Database Layer

Provides high-level API for interacting with the new production schema:
- Dataset versioning
- Experiment tracking
- Model version management
- Deployment tracking
- Audit logging

This module maintains backward compatibility while adding new capabilities.
All functions handle connection pooling and error recovery automatically.
"""

import json
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, UUID
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import Json

from app.config import settings
from app.storage.postgres_connection import connect_postgres

logger = logging.getLogger(__name__)


# ============================================================================
# CONNECTION MANAGEMENT
# ============================================================================

@contextmanager
def _cursor():
    """Context manager for database cursor with automatic cleanup"""
    conn = connect_postgres(
        connect_timeout=5,
        application_name="voya_backend_experiment_tracking"
    )
    try:
        with conn:
            with conn.cursor() as cur:
                yield cur
    finally:
        conn.close()


def _execute(sql: str, params: Dict[str, Any] | tuple | None = None) -> None:
    """Execute SQL statement without returning results"""
    with _cursor() as cur:
        cur.execute(sql, params)


def _fetch_one(sql: str, params: Dict[str, Any] | tuple | None = None) -> Optional[tuple]:
    """Fetch single row"""
    with _cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def _fetch_all(sql: str, params: Dict[str, Any] | tuple | None = None) -> List[tuple]:
    """Fetch all rows"""
    with _cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


# ============================================================================
# DATASET VERSIONING
# ============================================================================

def create_dataset(
    name: str,
    language: str,
    dialect: str,
    description: str = "",
    created_by: UUID = None,
    tags: List[str] = None
) -> Dict[str, Any]:
    """Create a new dataset container"""
    dataset_id = str(uuid4())

    sql = """
    INSERT INTO datasets (
        dataset_id, name, description, language, dialect,
        created_by, tags
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING dataset_id, name, language, dialect, created_at
    """

    row = _fetch_one(sql, (
        dataset_id,
        name,
        description,
        language,
        dialect,
        created_by,
        tags or []
    ))

    if not row:
        raise RuntimeError("Failed to create dataset")

    return {
        "dataset_id": str(row[0]),
        "name": row[1],
        "language": row[2],
        "dialect": row[3],
        "created_at": row[4].isoformat()
    }


def create_dataset_version(
    dataset_id: str,
    version_number: str,
    total_samples: int,
    total_augmentations: int,
    data_hash: str,
    created_by: UUID,
    description: str = "",
    manifest_path: str = None,
    parent_version_id: str = None
) -> Dict[str, Any]:
    """Create an immutable dataset version snapshot"""
    version_id = str(uuid4())

    sql = """
    INSERT INTO dataset_versions (
        dataset_version_id, dataset_id, version_number,
        total_samples, total_augmentations,
        language, dialect, data_hash,
        manifest_path, description,
        created_by, parent_version_id
    )
    SELECT
        %s, %s, %s,
        %s, %s,
        d.language, d.dialect, %s,
        %s, %s,
        %s, %s
    FROM datasets d
    WHERE d.dataset_id = %s
    RETURNING
        dataset_version_id, dataset_id, version_number,
        total_samples, created_at
    """

    row = _fetch_one(sql, (
        version_id,
        dataset_id,
        version_number,
        total_samples,
        total_augmentations,
        data_hash,
        manifest_path,
        description,
        created_by,
        parent_version_id,
        dataset_id
    ))

    if not row:
        raise RuntimeError(f"Dataset {dataset_id} not found")

    return {
        "dataset_version_id": str(row[0]),
        "dataset_id": str(row[1]),
        "version_number": row[2],
        "total_samples": row[3],
        "created_at": row[4].isoformat()
    }


def link_samples_to_dataset_version(
    dataset_version_id: str,
    samples: List[Dict[str, Any]]  # [{sample_uid, augment_id, sort_order}, ...]
) -> int:
    """Link multiple samples to a dataset version"""
    sql = """
    INSERT INTO dataset_samples_mapping (
        dataset_version_id, sample_uid, augment_id, sort_order
    )
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (dataset_version_id, sample_uid, augment_id) DO NOTHING
    """

    count = 0
    with _cursor() as cur:
        for sample in samples:
            cur.execute(sql, (
                dataset_version_id,
                sample["sample_uid"],
                sample.get("augment_id", 0),
                sample.get("sort_order", count)
            ))
            count += 1

    return count


def create_dataset_split(
    dataset_version_id: str,
    split_name: str,
    split_ratios: Dict[str, float],
    train_count: int,
    val_count: int,
    test_count: int,
    created_by: UUID,
    random_seed: int = None,
    stratify_by: str = None,
    description: str = None
) -> Dict[str, Any]:
    """Create a train/val/test split for a dataset version"""
    split_id = str(uuid4())

    sql = """
    INSERT INTO dataset_splits (
        split_id, dataset_version_id, split_name,
        split_ratios, train_count, val_count, test_count,
        random_seed, stratify_by, description,
        created_by
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING
        split_id, split_name, train_count, val_count, test_count, created_at
    """

    row = _fetch_one(sql, (
        split_id,
        dataset_version_id,
        split_name,
        Json(split_ratios),
        train_count,
        val_count,
        test_count,
        random_seed,
        stratify_by,
        description,
        created_by
    ))

    if not row:
        raise RuntimeError("Failed to create dataset split")

    return {
        "split_id": str(row[0]),
        "split_name": row[1],
        "train_count": row[2],
        "val_count": row[3],
        "test_count": row[4],
        "created_at": row[5].isoformat()
    }


# ============================================================================
# EXPERIMENT TRACKING
# ============================================================================

def create_experiment(
    name: str,
    dataset_version_id: str,
    dataset_split_id: str,
    model_architecture: str,
    hyperparameters: Dict[str, Any],
    created_by: UUID,
    description: str = "",
    random_seed: int = None,
    tags: List[str] = None
) -> Dict[str, Any]:
    """Create a new experiment record"""
    experiment_id = str(uuid4())

    sql = """
    INSERT INTO experiments (
        experiment_id, name, description,
        dataset_version_id, dataset_split_id,
        model_architecture, hyperparameters,
        created_by, random_seed, tags
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING
        experiment_id, name, status, created_at
    """

    row = _fetch_one(sql, (
        experiment_id,
        name,
        description,
        dataset_version_id,
        dataset_split_id,
        model_architecture,
        Json(hyperparameters),
        created_by,
        random_seed,
        tags or []
    ))

    if not row:
        raise RuntimeError("Failed to create experiment")

    return {
        "experiment_id": str(row[0]),
        "name": row[1],
        "status": row[2],
        "created_at": row[3].isoformat()
    }


def update_experiment_status(
    experiment_id: str,
    status: str,
    checkpoint_path: str = None,
    duration_seconds: int = None,
    error_message: str = None
) -> None:
    """Update experiment status after training"""
    sql = """
    UPDATE experiments
    SET
        status = %s,
        checkpoint_path = %s,
        duration_seconds = %s,
        error_message = %s,
        completed_at = CASE WHEN %s IN ('completed', 'failed') THEN NOW() ELSE completed_at END,
        started_at = CASE WHEN started_at IS NULL THEN NOW() ELSE started_at END
    WHERE experiment_id = %s
    """

    _execute(sql, (
        status,
        checkpoint_path,
        duration_seconds,
        error_message,
        status,
        experiment_id
    ))

    logger.info(f"[EXPERIMENT] {experiment_id} status={status}")


def log_experiment_metric(
    experiment_id: str,
    epoch: int,
    train_loss: float = None,
    train_accuracy: float = None,
    train_f1_macro: float = None,
    val_loss: float = None,
    val_accuracy: float = None,
    val_f1_macro: float = None,
    learning_rate: float = None,
    custom_metrics: Dict[str, Any] = None,
    per_class_metrics: Dict[str, Any] = None
) -> None:
    """Log per-epoch metrics"""
    sql = """
    INSERT INTO experiment_metrics (
        experiment_id, epoch,
        train_loss, train_accuracy, train_f1_macro,
        val_loss, val_accuracy, val_f1_macro,
        learning_rate, custom_metrics, per_class_metrics
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (experiment_id, epoch) DO UPDATE SET
        train_loss = EXCLUDED.train_loss,
        val_accuracy = EXCLUDED.val_accuracy,
        val_f1_macro = EXCLUDED.val_f1_macro,
        recorded_at = NOW()
    """

    _execute(sql, (
        experiment_id,
        epoch,
        train_loss,
        train_accuracy,
        train_f1_macro,
        val_loss,
        val_accuracy,
        val_f1_macro,
        learning_rate,
        Json(custom_metrics) if custom_metrics else None,
        Json(per_class_metrics) if per_class_metrics else None
    ))


def get_best_experiment_metrics(experiment_id: str) -> Dict[str, Any]:
    """Get best validation metrics from experiment"""
    sql = """
    SELECT
        MAX(val_accuracy) as best_val_accuracy,
        MAX(val_f1_macro) as best_val_f1,
        MIN(val_loss) as best_val_loss,
        MAX(epoch) as total_epochs
    FROM experiment_metrics
    WHERE experiment_id = %s
    """

    row = _fetch_one(sql, (experiment_id,))
    if not row:
        return {}

    return {
        "best_val_accuracy": float(row[0]) if row[0] else None,
        "best_val_f1": float(row[1]) if row[1] else None,
        "best_val_loss": float(row[2]) if row[2] else None,
        "total_epochs": row[3] or 0
    }


# ============================================================================
# MODEL VERSIONING
# ============================================================================

def create_model_version(
    model_id: str,
    version_string: str,
    experiment_id: str,
    checkpoint_path: str,
    accuracy: float,
    f1_macro: float,
    feature_contract: Dict[str, Any],
    created_by: UUID,
    input_shape: str = "(60, 126)",
    output_shape: str = "(*,)",
    loss: float = None,
    test_accuracy: float = None,
    test_f1_macro: float = None,
    per_class_f1: Dict[str, float] = None,
    approval_notes: str = None,
    tags: List[str] = None
) -> Dict[str, Any]:
    """Register a model version after training"""
    version_id = str(uuid4())

    sql = """
    INSERT INTO model_versions (
        model_version_id, model_id, version_string,
        experiment_id, checkpoint_path, checkpoint_hash,
        model_architecture, input_shape, output_shape,
        feature_contract, accuracy, f1_macro, loss,
        test_accuracy, test_f1_macro,
        per_class_f1, created_by, approval_notes, tags
    )
    SELECT
        %s, %s, %s,
        %s, %s, NULL,
        e.model_architecture, %s, %s,
        %s, %s, %s, %s,
        %s, %s,
        %s, %s, %s, %s
    FROM experiments e
    WHERE e.experiment_id = %s
    RETURNING
        model_version_id, model_id, version_string,
        accuracy, f1_macro, created_at
    """

    row = _fetch_one(sql, (
        version_id,
        model_id,
        version_string,
        experiment_id,
        checkpoint_path,
        input_shape,
        output_shape,
        Json(feature_contract),
        accuracy,
        f1_macro,
        loss,
        test_accuracy,
        test_f1_macro,
        Json(per_class_f1) if per_class_f1 else None,
        created_by,
        approval_notes,
        tags or [],
        experiment_id
    ))

    if not row:
        raise RuntimeError(f"Experiment {experiment_id} not found")

    return {
        "model_version_id": str(row[0]),
        "model_id": row[1],
        "version_string": row[2],
        "accuracy": float(row[3]),
        "f1_macro": float(row[4]),
        "created_at": row[5].isoformat()
    }


def promote_model_version(
    model_version_id: str,
    target_status: str,  # 'staging', 'production'
    approved_by: UUID = None,
    approval_notes: str = None
) -> Dict[str, Any]:
    """Promote model to next stage in lifecycle"""
    sql = """
    UPDATE model_versions
    SET
        status = %s,
        approved_by = %s,
        approval_notes = %s,
        published_at = CASE WHEN %s = 'production' THEN NOW() ELSE published_at END
    WHERE model_version_id = %s
    RETURNING model_version_id, model_id, version_string, status
    """

    row = _fetch_one(sql, (
        target_status,
        approved_by,
        approval_notes,
        target_status,
        model_version_id
    ))

    if not row:
        raise RuntimeError(f"Model version {model_version_id} not found")

    logger.info(f"[MODEL] {row[1]} v{row[2]} promoted to {target_status}")

    return {
        "model_version_id": str(row[0]),
        "model_id": row[1],
        "version_string": row[2],
        "status": row[3]
    }


def get_active_model_version(model_id: str, environment: str = "production") -> Optional[Dict[str, Any]]:
    """Get currently active model version for an environment"""
    sql = """
    SELECT DISTINCT ON (m.model_id)
        m.model_version_id,
        m.model_id,
        m.version_string,
        m.status,
        m.checkpoint_path,
        m.accuracy,
        m.f1_macro,
        m.feature_contract,
        d.environment,
        d.deployment_status
    FROM model_versions m
    LEFT JOIN model_deployments d ON m.model_version_id = d.model_version_id
    WHERE m.model_id = %s
        AND (d.environment = %s OR d.environment IS NULL)
    ORDER BY m.model_id,
             CASE WHEN m.status = 'production' THEN 0
                  WHEN m.status = 'staging' THEN 1
                  WHEN m.status = 'candidate' THEN 2
                  ELSE 3 END,
             m.created_at DESC
    LIMIT 1
    """

    row = _fetch_one(sql, (model_id, environment))
    if not row:
        return None

    return {
        "model_version_id": str(row[0]),
        "model_id": row[1],
        "version_string": row[2],
        "status": row[3],
        "checkpoint_path": row[4],
        "accuracy": float(row[5]) if row[5] else None,
        "f1_macro": float(row[6]) if row[6] else None,
        "feature_contract": row[7],
        "environment": row[8],
        "deployment_status": row[9]
    }


# ============================================================================
# DEPLOYMENT TRACKING
# ============================================================================

def create_deployment(
    model_version_id: str,
    environment: str,
    deployed_by: UUID,
    region: str = None,
    deployment_notes: str = None,
    traffic_percentage: int = 100
) -> Dict[str, Any]:
    """Create deployment record"""
    deployment_id = str(uuid4())

    sql = """
    INSERT INTO model_deployments (
        deployment_id, model_version_id, environment,
        region, deployed_by, deployment_notes,
        traffic_percentage
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING
        deployment_id, deployment_status, created_at
    """

    row = _fetch_one(sql, (
        deployment_id,
        model_version_id,
        environment,
        region,
        deployed_by,
        deployment_notes,
        traffic_percentage
    ))

    if not row:
        raise RuntimeError("Failed to create deployment")

    return {
        "deployment_id": str(row[0]),
        "deployment_status": row[1],
        "created_at": row[2].isoformat()
    }


def update_deployment_status(
    deployment_id: str,
    status: str,
    models_json_synced: bool = False,
    health_check_status: str = None
) -> None:
    """Update deployment status"""
    sql = """
    UPDATE model_deployments
    SET
        deployment_status = %s,
        deployment_completed_at = CASE WHEN %s = 'active' THEN NOW() ELSE deployment_completed_at END,
        models_json_synced = %s,
        models_json_sync_timestamp = CASE WHEN %s THEN NOW() ELSE models_json_sync_timestamp END,
        health_check_status = %s,
        health_check_timestamp = NOW()
    WHERE deployment_id = %s
    """

    _execute(sql, (
        status,
        status,
        models_json_synced,
        models_json_synced,
        health_check_status,
        deployment_id
    ))

    logger.info(f"[DEPLOYMENT] {deployment_id} status={status}")


# ============================================================================
# AUDIT LOGGING
# ============================================================================

def log_audit_event(
    entity_type: str,
    entity_id: str,
    action: str,
    actor_user_id: UUID,
    old_values: Dict[str, Any] = None,
    new_values: Dict[str, Any] = None,
    reason: str = None,
    entity_name: str = None,
    request_id: str = None
) -> int:
    """Log an audit event"""
    sql = """
    INSERT INTO audit_log (
        entity_type, entity_id, entity_name,
        action, actor_user_id,
        old_values, new_values, reason,
        request_id
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING audit_id
    """

    row = _fetch_one(sql, (
        entity_type,
        entity_id,
        entity_name,
        action,
        actor_user_id,
        Json(old_values) if old_values else None,
        Json(new_values) if new_values else None,
        reason,
        request_id
    ))

    if not row:
        raise RuntimeError("Failed to log audit event")

    return row[0]


# ============================================================================
# QUERY HELPERS
# ============================================================================

def get_experiment_by_id(experiment_id: str) -> Optional[Dict[str, Any]]:
    """Get experiment details"""
    sql = """
    SELECT
        experiment_id, name, status,
        dataset_version_id, dataset_split_id,
        created_at, started_at, completed_at,
        duration_seconds, checkpoint_path,
        model_architecture, hyperparameters
    FROM experiments
    WHERE experiment_id = %s
    """

    row = _fetch_one(sql, (experiment_id,))
    if not row:
        return None

    return {
        "experiment_id": str(row[0]),
        "name": row[1],
        "status": row[2],
        "dataset_version_id": str(row[3]),
        "dataset_split_id": str(row[4]),
        "created_at": row[5].isoformat() if row[5] else None,
        "started_at": row[6].isoformat() if row[6] else None,
        "completed_at": row[7].isoformat() if row[7] else None,
        "duration_seconds": row[8],
        "checkpoint_path": row[9],
        "model_architecture": row[10],
        "hyperparameters": row[11]
    }


def get_dataset_version_by_id(version_id: str) -> Optional[Dict[str, Any]]:
    """Get dataset version details"""
    sql = """
    SELECT
        dataset_version_id, dataset_id,
        version_number, total_samples, total_augmentations,
        language, dialect, is_frozen, is_published,
        created_at, published_at
    FROM dataset_versions
    WHERE dataset_version_id = %s
    """

    row = _fetch_one(sql, (version_id,))
    if not row:
        return None

    return {
        "dataset_version_id": str(row[0]),
        "dataset_id": str(row[1]),
        "version_number": row[2],
        "total_samples": row[3],
        "total_augmentations": row[4],
        "language": row[5],
        "dialect": row[6],
        "is_frozen": row[7],
        "is_published": row[8],
        "created_at": row[9].isoformat() if row[9] else None,
        "published_at": row[10].isoformat() if row[10] else None
    }


def list_model_versions(model_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """List recent model versions for a model"""
    sql = """
    SELECT
        model_version_id, model_id, version_string,
        status, accuracy, f1_macro, test_accuracy,
        created_at
    FROM model_versions
    WHERE model_id = %s
    ORDER BY created_at DESC
    LIMIT %s
    """

    rows = _fetch_all(sql, (model_id, limit))
    return [
        {
            "model_version_id": str(row[0]),
            "model_id": row[1],
            "version_string": row[2],
            "status": row[3],
            "accuracy": float(row[4]) if row[4] else None,
            "f1_macro": float(row[5]) if row[5] else None,
            "test_accuracy": float(row[6]) if row[6] else None,
            "created_at": row[7].isoformat() if row[7] else None
        }
        for row in rows
    ]


def list_experiments(dataset_version_id: str = None, limit: int = 20) -> List[Dict[str, Any]]:
    """List experiments, optionally filtered by dataset version"""
    if dataset_version_id:
        sql = """
        SELECT
            experiment_id, name, status,
            dataset_version_id, created_at, completed_at
        FROM experiments
        WHERE dataset_version_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """
        rows = _fetch_all(sql, (dataset_version_id, limit))
    else:
        sql = """
        SELECT
            experiment_id, name, status,
            dataset_version_id, created_at, completed_at
        FROM experiments
        ORDER BY created_at DESC
        LIMIT %s
        """
        rows = _fetch_all(sql, (limit,))

    return [
        {
            "experiment_id": str(row[0]),
            "name": row[1],
            "status": row[2],
            "dataset_version_id": str(row[3]),
            "created_at": row[4].isoformat() if row[4] else None,
            "completed_at": row[5].isoformat() if row[5] else None
        }
        for row in rows
    ]
