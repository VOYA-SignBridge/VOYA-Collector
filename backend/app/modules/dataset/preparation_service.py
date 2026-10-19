"""Application workflow for preparing trainable dataset artifacts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.modules.dataset.preparation_tasks import (
    create_pending_report,
    next_manifest_version,
    prepare_dataset,
    read_report,
)


@dataclass(frozen=True)
class UnsupportedDialectsError(ValueError):
    dialects: list[str]


def queue_preparation(
    *,
    dialects: Optional[list[str]],
    profiles: Optional[list[str]],
    seed: int,
    profiles_for_dialects: Callable[[list[str]], tuple[list[str], list[str]]],
    create_report: Callable[..., Any] = create_pending_report,
    next_version: Callable[[], str] = next_manifest_version,
    dispatch: Callable[..., Any] = prepare_dataset.delay,
) -> dict[str, Any]:
    """Resolve profiles, persist queued state, then dispatch one preparation run."""
    resolved_profiles = profiles
    if not resolved_profiles and dialects:
        resolved_profiles, unsupported = profiles_for_dialects(dialects)
        if not resolved_profiles:
            raise UnsupportedDialectsError(unsupported)

    run_id = uuid.uuid4().hex[:12]
    version = next_version()
    create_report(run_id, version, resolved_profiles or [], seed)
    dispatch(run_id=run_id, profiles=resolved_profiles, seed=seed, version=version)
    return {
        "run_id": run_id,
        "manifest_version": version,
        "profiles": resolved_profiles,
        "status": "queued",
    }


def preparation_report(run_id: str) -> Optional[dict[str, Any]]:
    return read_report(run_id)
