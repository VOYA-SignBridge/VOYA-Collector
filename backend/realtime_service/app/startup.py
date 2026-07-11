from __future__ import annotations

import json
import importlib.util
import logging
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI

from .contracts import validate_checkpoint_schema, validate_checkpoint_vs_registry, validate_registry_contract
from .model_loader import build_bundle, compute_file_sha256, load_checkpoint
from .registry import load_registry

logger = logging.getLogger("realtime_service.startup")


def _configure_torch_runtime() -> None:
    """Constrain torch runtime for a low-footprint inference service.

    - Disable autograd globally (inference only) → no graph/metadata overhead.
    - Cap CPU threads (default 1) so many small requests don't spawn a thread
      storm that inflates RSS. Override with REALTIME_TORCH_THREADS.
    """
    try:
        import torch

        torch.set_grad_enabled(False)
        threads = int(os.getenv("REALTIME_TORCH_THREADS", "1") or "1")
        if threads > 0:
            torch.set_num_threads(threads)
        logger.info("[STARTUP] torch runtime: grad=off cpu_threads=%d", threads)
    except Exception as exc:  # torch must exist, but never block startup on tuning
        logger.warning("[STARTUP] torch runtime config skipped: %s", exc)


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


def _resolve_optional_path(path_value: str) -> Path | None:
    raw = (path_value or "").strip()
    if not raw:
        return None

    candidate = Path(raw)
    if candidate.exists():
        return candidate

    if candidate.is_absolute():
        return None

    cwd = Path.cwd().resolve()
    for base in [cwd, *cwd.parents]:
        probe = (base / candidate).resolve()
        if probe.exists():
            return probe

    return None


def _load_label_lookup(label_index_path: str) -> Dict[str, Dict[str, Any]]:
    resolved = _resolve_optional_path(label_index_path)
    if resolved is None:
        logger.warning("[STARTUP] label index not found path=%s", label_index_path)
        return {}

    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"failed to load label index: {resolved}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"label index must be a dict: {resolved}")

    lookup: Dict[str, Dict[str, Any]] = {}
    for item in data.values():
        if not isinstance(item, dict):
            continue
        key = str(item.get("label_key") or "").strip()
        if key:
            lookup[key] = item

    return lookup


def _normalize_checkpoint_path(db_path: str) -> str:
    """Remap any absolute path to the /checkpoints container mount.

    DB may store Linux paths (/checkpoints/...) or Windows paths
    (E:\\VOYA\\...\\checkpoints\\...). Both are redirected to /checkpoints/...
    """
    p = db_path.replace("\\", "/")
    if "/checkpoints/" in p:
        idx = p.rfind("/checkpoints/")
        return "/checkpoints/" + p[idx + len("/checkpoints/"):]
    return p


def _infer_language_from_checkpoint(ckpt: Dict[str, Any]) -> str:
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


def _fetch_production_models(backend_url: str) -> List[Dict[str, Any]]:
    """Query backend for production models. 5 attempts, 3 s apart.

    Returns a list (may be empty). Raises RuntimeError if all attempts fail.
    """
    url = f"{backend_url.rstrip('/')}/api/v1/models?status=production"

    for attempt in range(1, 6):
        try:
            logger.info("[STARTUP] backend API attempt %d/5 url=%s", attempt, url)
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if not isinstance(data, list):
                raise ValueError(f"expected list response, got {type(data).__name__}")
            logger.info("[STARTUP] backend API ok: %d production model(s)", len(data))
            return data
        except Exception as exc:
            logger.warning("[STARTUP] backend API attempt %d/5 failed: %s", attempt, exc)
            if attempt < 5:
                time.sleep(3)

    raise RuntimeError("backend API unreachable after 5 attempts")


def _load_bundles_from_backend(
    models: List[Dict[str, Any]],
    label_lookup: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Build ModelBundle objects from a backend API production model list.

    Skips individual entries that fail (missing file, bad schema) and logs a
    warning. Only returns {} if every entry fails — caller decides fallback.
    """
    bundles: Dict[str, Any] = {}

    for entry in models:
        dialect = str(entry.get("dialect") or "").strip()
        if not dialect:
            logger.warning("[STARTUP][DB] entry with empty dialect — skipping: %s", entry)
            continue

        raw_path = str(entry.get("checkpoint_path") or "").strip()
        if not raw_path:
            logger.warning("[STARTUP][DB] dialect=%s: no checkpoint_path — skipping", dialect)
            continue

        checkpoint_path = _normalize_checkpoint_path(raw_path)
        if not Path(checkpoint_path).is_file():
            logger.warning(
                "[STARTUP][DB] dialect=%s: checkpoint not found at %s (raw=%s) — skipping",
                dialect, checkpoint_path, raw_path,
            )
            continue

        version_string = str(entry.get("version_string") or dialect)
        logger.info("[STARTUP][DB] loading dialect=%s checkpoint=%s", dialect, checkpoint_path)

        try:
            sha = compute_file_sha256(checkpoint_path)
            ckpt = load_checkpoint(checkpoint_path)
            validate_checkpoint_schema(ckpt)
            language = _infer_language_from_checkpoint(ckpt)
            bundle = build_bundle(
                model_id=dialect,
                model_name=version_string,
                checkpoint_path=checkpoint_path,
                language=language,
                dialect=dialect,
                ckpt=ckpt,
                checkpoint_sha256=sha,
                label_lookup=label_lookup if label_lookup else None,
            )
            bundles[dialect] = bundle
            logger.info("[STARTUP][DB] ready dialect=%s warmup_ok=%s", dialect, bundle.warmup_ok)
        except Exception as exc:
            logger.error("[STARTUP][DB] failed dialect=%s: %s — skipping", dialect, exc)

    return bundles


def initialize_app_state(
    app: FastAPI,
    *,
    registry_path: str,
    normalization_py_path: str,
    label_index_path: str,
    backend_url: str = "",
) -> None:
    """Load normalization module, label lookup, and all production model bundles.

    When BACKEND_URL is set, queries the backend API for production models and
    builds bundles from those checkpoints. Falls back to models.json if the
    backend is unreachable or returns no loadable models.
    """
    _configure_torch_runtime()

    logger.info("[STARTUP] loading normalization module path=%s", normalization_py_path)
    normalization_module = _load_normalization_module(normalization_py_path)

    logger.info("[STARTUP] loading label index path=%s", label_index_path)
    label_lookup = _load_label_lookup(label_index_path)

    bundles: Dict[str, Any] = {}
    db_source = False

    if backend_url:
        try:
            db_models = _fetch_production_models(backend_url)
            if db_models:
                db_bundles = _load_bundles_from_backend(db_models, label_lookup)
                if db_bundles:
                    bundles = db_bundles
                    db_source = True
                    logger.info(
                        "[STARTUP] %d model(s) loaded from backend API",
                        len(bundles),
                    )
                else:
                    logger.warning(
                        "[STARTUP] backend returned %d model(s) but none loadable"
                        " — falling back to models.json",
                        len(db_models),
                    )
            else:
                logger.warning(
                    "[STARTUP] backend returned empty production list"
                    " — falling back to models.json"
                )
        except RuntimeError as exc:
            logger.warning("[STARTUP] %s — falling back to models.json", exc)

    if not db_source:
        logger.info("[STARTUP] loading registry path=%s", registry_path)
        registry = load_registry(registry_path)
        registry_dir = Path(registry_path).parent

        for entry in registry.models:
            validate_registry_contract(entry)

            raw = Path(entry.checkpoint_path)
            resolved = (registry_dir / raw).resolve() if not raw.is_absolute() else raw.resolve()

            if not resolved.exists() or not resolved.is_file():
                raise RuntimeError(f"[MODEL] id={entry.id} checkpoint not found: {resolved}")

            logger.info("[MODEL] id=%s loading checkpoint path=%s", entry.id, resolved)

            sha = compute_file_sha256(str(resolved))
            ckpt = load_checkpoint(str(resolved))
            validate_checkpoint_schema(ckpt)
            validate_checkpoint_vs_registry(ckpt, entry)

            bundle = build_bundle(
                model_id=entry.id,
                model_name=entry.name,
                checkpoint_path=str(resolved),
                language=entry.language,
                dialect=entry.dialect,
                ckpt=ckpt,
                checkpoint_sha256=sha,
                label_lookup=label_lookup,
            )
            bundles[entry.id] = bundle
            logger.info("[MODEL][READY] id=%s warmup_ok=%s", entry.id, bundle.warmup_ok)

        app.state.registry = registry
    else:
        app.state.registry = None

    app.state.model_bundles = bundles
    app.state.normalization_module = normalization_module
    app.state.label_lookup = label_lookup
    app.state.registry_path = registry_path  # Store for dynamic reload


def register_startup(
    app: FastAPI,
    *,
    registry_path: str,
    normalization_py_path: str,
    label_index_path: str,
    backend_url: str = "",
) -> None:
    @app.on_event("startup")
    def _startup() -> None:
        initialize_app_state(
            app,
            registry_path=registry_path,
            normalization_py_path=normalization_py_path,
            label_index_path=label_index_path,
            backend_url=backend_url,
        )
