from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI

from .contracts import validate_checkpoint_schema, validate_checkpoint_vs_registry, validate_labels, validate_registry_contract
from .model_loader import build_bundle, compute_file_sha256, load_checkpoint
from .registry import load_registry

logger = logging.getLogger("realtime_service.startup")


def _load_normalization_module(normalization_py_path: str) -> Any:
    """Load processed/shared/normalization.py from an explicit file path.

    This avoids importing backend preprocessing and keeps semantics centralized.
    """
    p = Path(normalization_py_path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"normalization module not found: {p}")

    spec = importlib.util.spec_from_file_location("processed_shared_normalization", str(p))
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load normalization module spec from: {p}")

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]

    # Minimal interface check (Step 0): ensure expected function exists.
    if not hasattr(mod, "normalize_hands_vector_126"):
        raise RuntimeError("normalization module missing required function normalize_hands_vector_126")

    return mod


def initialize_app_state(app: FastAPI, *, registry_path: str, normalization_py_path: str) -> None:
    """All-or-nothing startup initializer.

    Any failure raises and prevents app from starting.
    """
    logger.info("[STARTUP] loading normalization module path=%s", normalization_py_path)
    normalization_module = _load_normalization_module(normalization_py_path)

    logger.info("[STARTUP] loading registry path=%s", registry_path)
    registry = load_registry(registry_path)

    registry_dir = Path(registry_path).parent

    bundles = {}

    for entry in registry.models:
        validate_registry_contract(entry)

        # Resolve ONCE: canonical absolute path, owned at startup
        raw = Path(entry.checkpoint_path)
        resolved = (registry_dir / raw).resolve() if not raw.is_absolute() else raw.resolve()

        # Validate existence BEFORE sha256/torch.load/warmup for clean error
        if not resolved.exists() or not resolved.is_file():
            raise RuntimeError(f"[MODEL] id={entry.id} checkpoint not found: {resolved}")

        # Log resolved path ONCE at startup (useful for Docker/Windows service/CI)
        logger.info("[MODEL] id=%s loading checkpoint path=%s", entry.id, resolved)

        sha = compute_file_sha256(str(resolved))
        ckpt = load_checkpoint(str(resolved))
        validate_checkpoint_schema(ckpt)
        validate_checkpoint_vs_registry(ckpt, entry)

        # Validate labels (structured objects) and alignment with registry scope
        _ = validate_labels(
            ckpt["idx_to_label"],
            num_classes=int(ckpt["num_classes"]),
            registry_language=entry.language,
            registry_dialect=entry.dialect,
        )

        bundle = build_bundle(
            model_id=entry.id,
            model_name=entry.name,
            checkpoint_path=str(resolved),
            language=entry.language,
            dialect=entry.dialect,
            ckpt=ckpt,
            checkpoint_sha256=sha,
        )

        bundles[entry.id] = bundle
        logger.info("[MODEL][READY] id=%s warmup_ok=%s", entry.id, bundle.warmup_ok)

    # Store app state
    app.state.registry = registry
    app.state.model_bundles = bundles
    app.state.normalization_module = normalization_module


def register_startup(app: FastAPI, *, registry_path: str, normalization_py_path: str) -> None:
    @app.on_event("startup")
    def _startup() -> None:
        # Fail-fast: if this raises, uvicorn will fail to boot.
        initialize_app_state(app, registry_path=registry_path, normalization_py_path=normalization_py_path)
