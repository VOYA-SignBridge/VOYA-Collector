"""Application workflow for preparing trainable dataset artifacts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.modules.dataset.preparation_tasks import read_report


@dataclass(frozen=True)
class UnsupportedDialectsError(ValueError):
    dialects: list[str]


def queue_preparation(
    *,
    dialects: Optional[list[str]],
    profiles: Optional[list[str]],
    seed: int,
    profiles_for_dialects: Callable[[list[str]], tuple[list[str], list[str]]],
    tenant_id: Optional[str] = None,
    minimum_samples: int = 25,
    with_research: bool = False,
    requested_by: str = "",
    create_report: Optional[Callable[..., Any]] = None,
    next_version: Optional[Callable[[], str]] = None,
    dispatch: Optional[Callable[..., Any]] = None,
) -> dict[str, Any]:
    """Persist queued state before dispatching one preparation run.

    The operational path only needs dialects. Recognition profiles are resolved
    when research artifacts were requested; requiring them unconditionally made
    an otherwise valid operational split fail before it reached the worker.

    ``tenant_id=None`` retains the old injection contract used by module-level
    callers while the HTTP path always supplies an owner.
    """
    resolved_profiles = profiles
    if not resolved_profiles and dialects and (with_research or tenant_id is None):
        resolved_profiles, unsupported = profiles_for_dialects(dialects)
        if not resolved_profiles:
            raise UnsupportedDialectsError(unsupported)

    run_id = uuid.uuid4().hex[:12]
    if tenant_id is None:
        from app.modules.dataset import preparation_tasks as tasks

        version = (next_version or tasks.next_manifest_version)()
        (create_report or tasks.create_pending_report)(
            run_id, version, resolved_profiles or [], seed
        )
        (dispatch or tasks.prepare_dataset.delay)(
            run_id=run_id, profiles=resolved_profiles, seed=seed, version=version
        )
        return {
            "run_id": run_id,
            "manifest_version": version,
            "profiles": resolved_profiles,
            "status": "queued",
        }

    # Resolve at call time so tests can patch the canonical task boundary without
    # this service retaining a stale imported Celery proxy.
    from app.modules.dataset import preparation_tasks as tasks

    selected_dialects = [str(value).strip() for value in (dialects or []) if str(value).strip()]
    floor = int(minimum_samples)
    report_writer = create_report or tasks.create_pending_report
    task_dispatch = dispatch or tasks.prepare_dataset.delay
    report_writer(
        run_id,
        tenant_id=tenant_id,
        dialects=selected_dialects,
        floor=floor,
        seed=seed,
        with_research=with_research,
        requested_by=requested_by,
    )
    task_dispatch(
        run_id=run_id,
        tenant_id=tenant_id,
        dialects=selected_dialects,
        min_samples_per_class=floor,
        seed=seed,
        with_research=with_research,
        profiles=resolved_profiles,
        requested_by=requested_by,
    )
    return {
        "run_id": run_id,
        "dialects": selected_dialects,
        "min_samples_per_class": floor,
        "profiles": resolved_profiles,
        "status": "queued",
    }


def preparation_report(run_id: str) -> Optional[dict[str, Any]]:
    return read_report(run_id)
