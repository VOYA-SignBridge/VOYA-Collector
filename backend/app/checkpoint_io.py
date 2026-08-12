"""Loading a `.pt` checkpoint without handing it the interpreter.

The risk
--------
``torch.load(..., weights_only=False)`` unpickles, and unpickling executes code
carried inside the file. A checkpoint is therefore not data — it is a program,
and loading one is running it.

Five call sites in `routers/training.py` and `training_tasks.py` passed
``weights_only=False`` unconditionally. This is not a remote hole: those paths sit
behind `require_admin` and the files are produced by this system. The real
exposure is supply chain (MITRE ATLAS AML.T0010) — a checkpoint fetched from
elsewhere, or a checkpoint directory writable by another process, becomes a code
execution path with admin already assumed.

Two independent defences
------------------------
1. **Where the file may come from.** `resolve_checkpoint_path` compares the
   *resolved* path against the allowed roots, so `..` and symlinks are followed
   before the comparison rather than pattern-matched away. String prefix checks
   are the standard way to get this wrong: ``"/workspace/checkpoints/../../etc"``
   starts with the allowed prefix.
2. **What the file may contain.** `load_checkpoint` tries ``weights_only=True``
   first and only falls back when the content genuinely cannot be represented
   that way — this project's checkpoints deliberately carry metadata dicts, so a
   hard requirement would break loading real artefacts. The fallback is logged.

`realtime_service/app/model_loader.py` already had defence 2; this module is the
backend's version and adds defence 1. The two are kept separate on purpose: the
realtime service is a different container with a different dependency set and
does not import `app.*`.
"""

from __future__ import annotations

import inspect
import logging
from pathlib import Path
from typing import Any, Iterable, Sequence

logger = logging.getLogger(__name__)


class UntrustedCheckpointError(ValueError):
    """Raised when a checkpoint path resolves outside the allowed roots."""


def checkpoint_roots() -> list[Path]:
    """Directories a checkpoint may legitimately live in.

    Imported lazily from the routers so the paths stay defined in one place
    rather than being restated here and drifting.
    """
    from app.routers.training import (
        CHECKPOINTS_DIR,
        OUTPUTS_DIR,
        REALTIME_CHECKPOINTS_DIR,
    )

    return [CHECKPOINTS_DIR, OUTPUTS_DIR, REALTIME_CHECKPOINTS_DIR]


def _is_within(path: Path, root: Path) -> bool:
    """True when `path` is `root` or lives under it, comparing resolved paths."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_checkpoint_path(
    path: str | Path, roots: Sequence[Path] | None = None
) -> Path:
    """Resolve `path` and refuse it unless it sits inside an allowed root.

    `strict=False` so a non-existent path resolves rather than raising: the
    caller's "file not found" is a clearer error than a resolution failure, and
    the containment check is still meaningful on the resolved form.
    """
    candidate = Path(path).resolve(strict=False)
    allowed: Iterable[Path] = roots if roots is not None else checkpoint_roots()

    resolved_roots = []
    for root in allowed:
        try:
            resolved_roots.append(Path(root).resolve(strict=False))
        except Exception:  # pragma: no cover - unresolvable root is a config bug
            continue

    if any(_is_within(candidate, root) for root in resolved_roots):
        return candidate

    raise UntrustedCheckpointError(
        f"checkpoint path {str(path)!r} resolves to {str(candidate)!r}, which is "
        f"outside the allowed roots: {', '.join(str(r) for r in resolved_roots)}"
    )


def load_checkpoint(
    path: str | Path,
    *,
    map_location: str = "cpu",
    roots: Sequence[Path] | None = None,
) -> Any:
    """Validate the path, then load with `weights_only=True` where possible."""
    import torch

    safe_path = resolve_checkpoint_path(path, roots)

    signature = None
    try:
        signature = inspect.signature(torch.load)
    except Exception:  # pragma: no cover - torch always has a signature
        signature = None

    if signature is None or "weights_only" not in signature.parameters:
        # torch too old to offer the safe mode at all.
        return torch.load(str(safe_path), map_location=map_location)

    try:
        return torch.load(str(safe_path), map_location=map_location, weights_only=True)
    except Exception as exc:
        # Expected for this project's own checkpoints, which carry metadata
        # dicts alongside the tensors. Logged at WARNING rather than swallowed
        # so an unexpected fallback on a new artefact is visible.
        logger.warning(
            "[CKPT] weights_only load failed for %s (%s); falling back to full unpickle",
            safe_path.name, exc,
        )

    # torch >= 2.6 defaults weights_only=True, so the fallback must opt out
    # explicitly — otherwise it just repeats the failure above.
    return torch.load(str(safe_path), map_location=map_location, weights_only=False)
