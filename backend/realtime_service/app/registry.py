from __future__ import annotations

import json
from pathlib import Path

from .schemas import ModelRegistry


def load_registry(registry_path: str) -> ModelRegistry:
    p = Path(registry_path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"registry not found: {p}")

    data = json.loads(p.read_text(encoding="utf-8"))
    registry = ModelRegistry.parse_obj(data)

    # Enforce deterministic uniqueness on model IDs
    seen = set()
    for m in registry.models:
        if m.id in seen:
            raise ValueError(f"duplicate model id in registry: {m.id}")
        seen.add(m.id)

    return registry
