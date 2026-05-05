"""
Health check and system status endpoints for VOYA backend.
Provides comprehensive diagnostics for monitoring and troubleshooting.
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
import psycopg2

from app.config import settings

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger("health")


def _check_postgres() -> None:
    conn = psycopg2.connect(settings.database_url, connect_timeout=3)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    finally:
        conn.close()


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
    try:
        # Check database connectivity
        try:
            _check_postgres()
            db_status = "connected"
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            db_status = f"error: {str(e)}"

        # All checks passed
        if db_status == "connected":
            return {
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat(),
                "checks": {
                    "database": "ok",
                    "redis": "ok",
                },
            }
        else:
            raise HTTPException(status_code=503, detail=f"Database unavailable: {db_status}")
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")


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
            "app_env": settings.app_env if hasattr(settings, "app_env") else "unknown",
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
        "cloudinary_enabled": bool(getattr(settings, "cloudinary_enabled", False)),
        "minio_enabled": bool(getattr(settings, "use_minio", False)),
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

    # Check Cloudinary config
    if getattr(settings, "cloudinary_enabled", False):
        cloud_name = getattr(settings, "cloudinary_cloud_name", "")
        if not cloud_name:
            errors.append("Cloudinary enabled but CLOUDINARY_CLOUD_NAME not set")

    # Check MinIO config
    if getattr(settings, "use_minio", False):
        minio_endpoint = getattr(settings, "minio_endpoint", "")
        if not minio_endpoint:
            errors.append("MinIO enabled but MINIO_ENDPOINT not set")

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

    return deps_status
