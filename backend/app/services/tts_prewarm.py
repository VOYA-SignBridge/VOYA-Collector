"""TTS Prewarm — pre-synthesize top labels into Redis cache at startup.

Strategy: Hybrid
  - Read label index (``index_to_label.json``)
  - Select top 20% most common labels (configurable via TTS_PREWARM_TOP_PERCENT)
  - Synthesize + cache those labels for each allowed voice
  - Remaining labels are cached on-demand when first requested

Runs as a non-blocking background task; does NOT delay server readiness.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from app.config import settings
from app.services.tts_service import ALLOWED_VOICES, cache_exists, synthesize

logger = logging.getLogger("tts_prewarm")

# Default paths to look for label index
_LABEL_INDEX_PATHS = [
    "/app/processed/analysis/index_to_label.json",      # Docker
    "processed/analysis/index_to_label.json",            # Local dev relative
]


def _find_label_index_path() -> Optional[str]:
    """Locate index_to_label.json, checking multiple possible paths."""
    # Check LABEL_INDEX_PATH env var first
    env_path = os.getenv("LABEL_INDEX_PATH", "").strip()
    if env_path and os.path.isfile(env_path):
        return env_path

    for candidate in _LABEL_INDEX_PATHS:
        if os.path.isfile(candidate):
            return candidate

    return None


def _load_labels(path: str) -> List[str]:
    """Load unique label_original values from index_to_label.json.

    Expected format: dict mapping index (str) → label object with
    ``label_original`` field.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.error("[TTS_PREWARM] failed to load label index: %s", exc)
        return []

    labels: List[str] = []
    seen: set = set()

    if isinstance(data, dict):
        for _idx, entry in data.items():
            if isinstance(entry, dict):
                label = str(entry.get("label_original", "")).strip()
            elif isinstance(entry, str):
                label = entry.strip()
            else:
                continue

            if label and label not in seen:
                labels.append(label)
                seen.add(label)

    elif isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                label = str(entry.get("label_original", "")).strip()
            elif isinstance(entry, str):
                label = entry.strip()
            else:
                continue

            if label and label not in seen:
                labels.append(label)
                seen.add(label)

    return labels


def _select_top_labels(labels: List[str], percent: float) -> List[str]:
    """Select top N% of labels for prewarming.

    Since we don't have usage analytics, we use index order as a
    proxy — labels at lower indices tend to be more commonly used
    (they were assigned first / are more fundamental signs).

    The percent is clamped to [0.05, 1.0].
    """
    pct = max(0.05, min(1.0, percent))
    count = max(1, int(len(labels) * pct))
    selected = labels[:count]
    logger.info(
        "[TTS_PREWARM] selected %d / %d labels (%.0f%%) for prewarm",
        len(selected), len(labels), pct * 100,
    )
    return selected


async def prewarm_tts_cache() -> Dict[str, int]:
    """Pre-synthesize top labels into Redis.

    Returns summary dict: {prewarmed, skipped, errors, total_labels}.
    """
    if not settings.tts_prewarm_on_startup:
        logger.info("[TTS_PREWARM] disabled via TTS_PREWARM_ON_STARTUP=0")
        return {"prewarmed": 0, "skipped": 0, "errors": 0, "total_labels": 0}

    path = _find_label_index_path()
    if not path:
        logger.warning("[TTS_PREWARM] label index not found; skipping prewarm")
        return {"prewarmed": 0, "skipped": 0, "errors": 0, "total_labels": 0}

    all_labels = _load_labels(path)
    if not all_labels:
        logger.warning("[TTS_PREWARM] no labels found in %s", path)
        return {"prewarmed": 0, "skipped": 0, "errors": 0, "total_labels": 0}

    top_labels = _select_top_labels(all_labels, settings.tts_prewarm_top_percent)

    prewarmed = 0
    skipped = 0
    errors = 0
    t0 = time.monotonic()

    for voice_info in ALLOWED_VOICES:
        voice_id = voice_info["id"]
        for i, label in enumerate(top_labels):
            try:
                # Skip if already cached
                if await cache_exists(label, voice_id):
                    skipped += 1
                    continue

                # Synthesize and cache
                await synthesize(label, voice_id)
                prewarmed += 1

                if (prewarmed % 10) == 0:
                    logger.info(
                        "[TTS_PREWARM] progress: %d/%d (voice=%s)",
                        prewarmed, len(top_labels) * len(ALLOWED_VOICES),
                        voice_id,
                    )

                # Small delay to avoid hammering Microsoft TTS API
                await asyncio.sleep(0.1)

            except Exception as exc:
                errors += 1
                logger.warning(
                    "[TTS_PREWARM] failed label='%s' voice=%s: %s",
                    label[:30], voice_id, exc,
                )

    elapsed = time.monotonic() - t0
    summary = {
        "prewarmed": prewarmed,
        "skipped": skipped,
        "errors": errors,
        "total_labels": len(all_labels),
        "top_labels": len(top_labels),
        "voices": len(ALLOWED_VOICES),
        "elapsed_seconds": round(elapsed, 1),
    }
    logger.info("[TTS_PREWARM] completed: %s", summary)
    return summary
