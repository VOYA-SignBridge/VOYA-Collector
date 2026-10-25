"""File-backed preferences used by the web capture interface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from filelock import FileLock

from app.config import settings


DEFAULT_PREFERENCES_PATH = Path(settings.dataset_root) / "user_preferences.json"


def load_preferences(path: Path = DEFAULT_PREFERENCES_PATH) -> dict[str, Any]:
    """Load preferences, preserving the legacy fail-open behavior."""
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            value = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def get_value(key: str, *, path: Path = DEFAULT_PREFERENCES_PATH) -> Any:
    """Read one preference value from the shared capture preferences file."""
    return load_preferences(path).get(key)


def set_value(
    key: str,
    value: Any,
    *,
    path: Path = DEFAULT_PREFERENCES_PATH,
) -> None:
    """Update one preference while serializing concurrent writers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path) + ".lock")
    with lock:
        preferences = load_preferences(path)
        preferences[key] = value
        with path.open("w", encoding="utf-8") as file:
            json.dump(preferences, file, ensure_ascii=False, indent=2)


def get_scoped_value(
    bucket: str,
    key: str,
    *,
    path: Path = DEFAULT_PREFERENCES_PATH,
) -> Any:
    """Read a tenant/user preference, with one-way legacy fallback.

    Older versions stored values at the top level.  Keep those values readable
    while all new writes go into the caller's isolated bucket.
    """
    preferences = load_preferences(path)
    scoped = preferences.get(bucket)
    if isinstance(scoped, dict) and key in scoped:
        return scoped[key]

    legacy = preferences.get(key)
    return legacy if not isinstance(legacy, dict) else None


def set_scoped_value(
    bucket: str,
    key: str,
    value: Any,
    *,
    path: Path = DEFAULT_PREFERENCES_PATH,
) -> None:
    """Update one tenant/user preference while serializing writers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path) + ".lock")
    with lock:
        preferences = load_preferences(path)
        scoped = preferences.get(bucket)
        if not isinstance(scoped, dict):
            scoped = {}
        scoped[key] = value
        preferences[bucket] = scoped
        with path.open("w", encoding="utf-8") as file:
            json.dump(preferences, file, ensure_ascii=False, indent=2)
