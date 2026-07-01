from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Request

from .registry import load_registry

logger = logging.getLogger("realtime_service.health")

router = APIRouter()


@router.get("/health")
def health(request: Request) -> Dict[str, Any]:
    bundles = getattr(request.app.state, "model_bundles", {}) or {}
    registry = getattr(request.app.state, "registry", None)

    models = []
    for model_id, b in list(bundles.items()):
        models.append(
            {
                "id": model_id,
                "name": b.model_name,
                "normalization_version": b.normalization_version,
                "checkpoint_sha256": b.checkpoint_sha256,
                "warmup_ok": bool(b.warmup_ok),
                "language": b.language,
                "dialect": b.dialect,
                "loaded_at": b.loaded_at,
            }
        )

    models.sort(key=lambda m: m["id"])

    return {
        "status": "ok",
        "model_source": "registry" if registry is not None else "db",
        "model_count": len(models),
        "models": models,
    }


@router.get("/models")
def list_models(request: Request) -> List[Dict[str, Any]]:
    """Public-safe list of selectable models.

    Reloads registry from file to pick up models added after startup.
    Does NOT expose labels, checkpoint paths, or internal contracts.
    Falls back to model_bundles when registry is None (DB-driven startup).
    """
    registry = getattr(request.app.state, "registry", None)

    if registry is not None:
        # Try to reload registry from file to pick up new models (e.g., trained models)
        try:
            registry_path = getattr(request.app.state, "registry_path", None)
            if registry_path and Path(registry_path).exists():
                registry = load_registry(registry_path)
                logger.debug("[MODELS] reloaded registry from %s", registry_path)
        except Exception as e:
            logger.warning("[MODELS] failed to reload registry: %s", e)
            # Fall back to in-memory registry

        if registry is not None:
            return [
                {"id": m.id, "name": m.name, "language": m.language, "dialect": m.dialect}
                for m in registry.models
            ]

    bundles = getattr(request.app.state, "model_bundles", {}) or {}
    return sorted(
        [
            {
                "id": b.model_id,
                "name": b.model_name,
                "language": b.language,
                "dialect": b.dialect,
            }
            for b in list(bundles.values())
        ],
        key=lambda m: m["id"],
    )
