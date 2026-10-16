from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .contracts import validate_checkpoint_schema
from .model_loader import build_bundle, compute_file_sha256, load_checkpoint

logger = logging.getLogger("realtime_service.reload")

router = APIRouter()


class ReloadRequest(BaseModel):
    model_id: str
    checkpoint_path: str
    version_string: str
    dialect: str = ""  # Optional, for backwards compatibility
    language: str = "vn"  # Optional, defaults to Vietnamese


class ReloadResponse(BaseModel):
    dialect: str
    version_string: str
    loaded_at: str
    warmup_ok: bool


def _infer_language(ckpt: Dict[str, Any]) -> str:
    """Extract language from first idx_to_label entry; default 'vn'."""
    idx = ckpt.get("idx_to_label")
    if isinstance(idx, list) and idx and isinstance(idx[0], dict):
        lang = str(idx[0].get("language") or "").strip()
        if lang:
            return lang
    elif isinstance(idx, dict):
        for val in idx.values():
            if isinstance(val, dict):
                lang = str(val.get("language") or "").strip()
                if lang:
                    return lang
            break
    return "vn"


@router.post("/reload", response_model=ReloadResponse)
def reload_model(req: ReloadRequest, request: Request) -> ReloadResponse:
    """Hot-swap/add a model bundle.

    Validates and loads the new checkpoint fully (schema check + warmup) before
    touching any live state. Used for both production model updates and training
    result registration. Not exposed via nginx — Docker network only.
    """
    model_id = req.model_id.strip()
    if not model_id:
        raise HTTPException(status_code=422, detail="model_id must be non-empty")

    ckpt_path = req.checkpoint_path.strip()
    if not ckpt_path:
        raise HTTPException(status_code=422, detail="checkpoint_path must be non-empty")

    if not Path(ckpt_path).is_file():
        raise HTTPException(status_code=422, detail=f"checkpoint not found: {ckpt_path}")

    logger.info(
        "[RELOAD] model_id=%s checkpoint=%s version=%s",
        model_id, ckpt_path, req.version_string,
    )

    try:
        sha = compute_file_sha256(ckpt_path)
        ckpt = load_checkpoint(ckpt_path)
        validate_checkpoint_schema(ckpt)

        label_lookup: Optional[Dict[str, Any]] = (
            getattr(request.app.state, "label_lookup", None) or None
        )
        language = req.language if req.language else _infer_language(ckpt)
        dialect = req.dialect.strip() if req.dialect else model_id

        bundle = build_bundle(
            model_id=model_id,
            model_name=req.version_string,
            checkpoint_path=ckpt_path,
            language=language,
            dialect=dialect,
            ckpt=ckpt,
            checkpoint_sha256=sha,
            label_lookup=label_lookup,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        logger.error("[RELOAD] failed model_id=%s: %s", model_id, exc)
        raise HTTPException(status_code=422, detail=str(exc))

    # Atomic swap — old bundle stays live until this assignment completes
    old_bundle = request.app.state.model_bundles.get(model_id)
    request.app.state.model_bundles[model_id] = bundle
    logger.info(
        "[RELOAD] swapped model_id=%s warmup_ok=%s loaded_at=%s",
        model_id, bundle.warmup_ok, bundle.loaded_at,
    )

    # Free the replaced model explicitly — otherwise its weights linger until
    # the next GC pass, accumulating across retrains.
    if old_bundle is not None:
        del old_bundle
        import gc

        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    return ReloadResponse(
        dialect=dialect,
        version_string=req.version_string,
        loaded_at=bundle.loaded_at,
        warmup_ok=bundle.warmup_ok,
    )
