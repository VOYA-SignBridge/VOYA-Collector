"""Loguru-based logging for the v2 stack (Refactore task 2.5).

- Console sink: human-readable, level from env.
- File sink: JSON-lines under logs/, rotated daily, retention per
  LOG_CATEGORIES policy (GC job `gc_log_rotation` deletes old files).
- Every record carries `request_id` (bound by middleware in GĐ 2;
  defaults to "-" outside a request context).

The legacy app keeps its own logging_config.py untouched.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger

_CONFIGURED = False

LOG_DIR = Path(os.getenv("V2_LOG_DIR", "logs"))


def configure_logging(level: str | None = None) -> None:
    """Idempotent logger setup — safe to call from app startup and tests."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = level or os.getenv("V2_LOG_LEVEL", "INFO")
    logger.remove()

    logger.configure(extra={"request_id": "-"})

    # Console (dev-friendly)
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:HH:mm:ss.SSS}</green> | <level>{level:<7}</level> | "
            "rid={extra[request_id]} | <cyan>{name}</cyan> - {message}"
        ),
    )

    # JSON-lines file (machine-readable, rotated)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(
        LOG_DIR / "app-{time:YYYY-MM-DD}.jsonl",
        level=level,
        serialize=True,
        rotation="00:00",
        retention="30 days",
        enqueue=True,  # process-safe (Celery workers share the sink)
    )

    _CONFIGURED = True


def get_logger(name: str):
    """Named logger; call configure_logging() once at startup first."""
    return logger.bind(name=name)
