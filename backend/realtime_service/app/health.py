from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request) -> Dict[str, Any]:
    bundles = getattr(request.app.state, "model_bundles", {}) or {}

    models = []
    for model_id, b in bundles.items():
        models.append(
            {
                "id": model_id,
                "normalization_version": b.normalization_version,
                "checkpoint_sha256": b.checkpoint_sha256,
                "warmup_ok": bool(b.warmup_ok),
                "language": b.language,
                "dialect": b.dialect,
            }
        )

    models.sort(key=lambda m: m["id"])

    return {
        "status": "ok",
        "model_count": len(models),
        "models": models,
    }


@router.get("/models")
def list_models(request: Request) -> List[Dict[str, Any]]:
    """Public-safe list of selectable models.

    Does NOT expose labels, checkpoint paths, or internal contracts.
    """
    registry = getattr(request.app.state, "registry", None)
    if registry is None:
        return []

    out: List[Dict[str, Any]] = []
    for m in registry.models:
        out.append(
            {
                "id": m.id,
                "name": m.name,
                "language": m.language,
                "dialect": m.dialect,
            }
        )
    return out
