"""Classify training failures and escalate SYSTEM (infra) failures to admins.

A user's run failing because the platform is broken — Redis/Celery down, the
trainer can't spawn, a timeout, GPU/RAM exhaustion — is an ops problem admins
must see, NOT the contributor's fault. Data problems the user can fix (no
samples selected, empty splits) are shown to the user and are NOT escalated.

The notification path is deliberately **Redis-independent**: the canonical
"redis down" failure would break any Redis-backed inbox, so the durable channel
is a structured ERROR log (→ Loki) plus a Prometheus counter (→ Grafana alert).
A best-effort security-log entry is added on top for the in-app admin feed when
Redis happens to be reachable (e.g. a trainer crash while Redis is fine).
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

SYSTEM = "system"
DATA = "data"

# Things the USER can act on themselves → not an admin problem.
_DATA_PATTERNS = re.compile(
    r"no data|không có dữ liệu|thiếu dữ liệu|dataset|splits?|empty|no samples|"
    r"train\.csv|val\.csv|chọn.*(nhãn|phương ngữ)|nhãn|label",
    re.IGNORECASE,
)

# Unambiguous platform/infra failures → admins must see them.
_SYSTEM_PATTERNS = re.compile(
    r"redis|celery|broker|queue|enqueue|dispatch|gửi được job|connection refused|"
    r"10061|trainer|worker|timeout|timed out|quá thời gian|cuda|gpu|out of memory|"
    r"oom|vram|memory|disk|no space|spawn|khởi động được|mã lỗi|return ?code|process",
    re.IGNORECASE,
)


def classify_training_error(message: str) -> str:
    """SYSTEM vs DATA. Data patterns win when present and no infra keyword is —
    otherwise infra, and an unknown internal error defaults to SYSTEM (a bug/infra
    issue the user cannot fix, so admins should still get eyes on it)."""
    msg = message or ""
    if _DATA_PATTERNS.search(msg) and not _SYSTEM_PATTERNS.search(msg):
        return DATA
    return SYSTEM


def is_system_failure(message: str) -> bool:
    return classify_training_error(message) == SYSTEM


def notify_admins_training_failure(
    *, job_id: str, actor: str, error: str, source: str
) -> bool:
    """Escalate a SYSTEM training failure to admins. No-op (returns False) for a
    data failure the user can fix themselves.

    `source` is where it broke: "dispatch" | "trainer_spawn" | "trainer_timeout"
    | "trainer_exit". Returns True if it was treated as a system failure.
    """
    if not is_system_failure(error):
        return False

    # 1) Durable, Redis-independent — structured ERROR log flows to Loki.
    logger.error(
        "[TRAINING_SYSTEM_FAILURE] source=%s job=%s actor=%s error=%s",
        source, job_id, actor, error,
    )

    # 2) Prometheus counter (effective on the backend/API side; Grafana alert).
    try:
        from app.metrics import training_system_failures_total

        training_system_failures_total.labels(source=source).inc()
    except Exception:
        pass

    # 3) Best-effort in-app admin feed (Redis) — skipped silently if Redis down.
    try:
        from app import activity

        activity.log_security_event(
            action="TRAINING_SYSTEM_FAILURE",
            actor=actor or "",
            target=job_id or "",
            reason=error or "",
            extra={"source": source, "severity": "error"},
        )
    except Exception:
        pass

    return True
