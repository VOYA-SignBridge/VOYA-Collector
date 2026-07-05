import logging
import os
from datetime import datetime
from typing import Dict, Any

import redis
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.storage.postgres_connection import connect_postgres

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger("health")


def _check_postgres() -> None:
    conn = connect_postgres(connect_timeout=3, application_name="voya_backend_health")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    finally:
        conn.close()


def _check_redis() -> None:
    client = redis.from_url(settings.broker_url, socket_connect_timeout=3)
    try:
        client.ping()
    finally:
        client.close()


@router.get("", tags=["health"])
@router.get("/", tags=["health"])
async def health_check() -> Dict[str, Any]:
    """
    Quick health check endpoint.
    Returns: {"status": "healthy"} if all systems operational
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@router.get("/ready", tags=["health"])
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness probe: checks if service is ready to accept traffic.
    Verifies database connectivity and essential services.
    """
    checks: Dict[str, str] = {}

    try:
        _check_postgres()
        checks["database"] = "ok"
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        checks["database"] = f"error: {str(e)}"

    try:
        _check_redis()
        checks["redis"] = "ok"
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        checks["redis"] = f"error: {str(e)}"

    if all(v == "ok" for v in checks.values()):
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
        }

    raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})


@router.get("/live", tags=["health"])
async def liveness_check() -> Dict[str, Any]:
    """
    Liveness probe: checks if process is alive.
    Used by container orchestration to restart unhealthy containers.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/status", tags=["health"])
async def detailed_status() -> Dict[str, Any]:
    """
    Detailed system status for monitoring and debugging.
    """
    status_info: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat(),
        "environment": {
            "debug_logging": bool(getattr(settings, "debug_logging", False)),
        },
        "services": {},
        "configuration": {},
    }

    # Database status
    try:
        _check_postgres()
        status_info["services"]["database"] = {
            "status": "connected",
            "host": getattr(settings, "postgres_host", "unknown"),
            "port": getattr(settings, "postgres_port", "unknown"),
        }
    except Exception as e:
        status_info["services"]["database"] = {"status": "error", "error": str(e)}

    # Storage configuration
    status_info["configuration"]["storage"] = {
        "dataset_root": str(getattr(settings, "dataset_root", "/dataset")),
        "google_drive_enabled": bool(getattr(settings, "use_google_drive", False)),
        "google_drive_root_folder_id": getattr(settings, "google_drive_root_folder_id", ""),
    }

    # Redis configuration
    status_info["configuration"]["redis"] = {
        "broker_url": getattr(settings, "broker_url", "unknown").split("@")[-1],  # Hide auth
    }

    # Processing configuration
    status_info["configuration"]["processing"] = {
        "feature_dim": int(getattr(settings, "feature_dim", 126)),
        "seq_len": int(getattr(settings, "seq_len", 60)),
        "aug_per_seq": int(getattr(settings, "augment_per_seq", 8)),
        "video_aug_per_seq": int(getattr(settings, "video_augment_per_seq", 0) or 0),
        "enable_live_aug": bool(getattr(settings, "enable_live_aug", True)),
        "carry_forward_missing": bool(getattr(settings, "carry_forward_missing", True)),
    }

    return status_info


@router.get("/config", tags=["health"])
async def config_check() -> Dict[str, Any]:
    """
    Configuration validation endpoint.
    Helps diagnose configuration issues.
    """
    errors = []
    warnings = []

    # Check database config consistency
    db_url = getattr(settings, "database_url", "")
    postgres_user = getattr(settings, "postgres_user", "")
    if postgres_user and postgres_user not in db_url:
        errors.append(f"Database URL does not match POSTGRES_USER: {postgres_user}")

    # Check storage paths
    dataset_root = getattr(settings, "dataset_root", "/dataset")
    if not os.path.exists(dataset_root):
        warnings.append(f"Dataset root does not exist: {dataset_root}")

    if getattr(settings, "use_google_drive", False):
        credentials = getattr(settings, "google_drive_credentials", "")
        if not credentials:
            errors.append("Google Drive enabled but GOOGLE_DRIVE_CREDENTIALS is not set")

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


@router.get("/deps", tags=["health"])
async def dependencies_check() -> Dict[str, Any]:
    """
    Check external dependencies (database, Redis, etc.)
    """
    deps_status: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat(),
        "dependencies": {},
    }

    # Database
    try:
        _check_postgres()
        deps_status["dependencies"]["postgres"] = {
            "status": "ok",
            "response_time_ms": 0,
        }
    except Exception as e:
        deps_status["dependencies"]["postgres"] = {
            "status": "error",
            "error": str(e),
        }

    # Redis
    try:
        _check_redis()
        deps_status["dependencies"]["redis"] = {
            "status": "ok",
            "response_time_ms": 0,
        }
    except Exception as e:
        deps_status["dependencies"]["redis"] = {
            "status": "error",
            "error": str(e),
        }

    return deps_status
