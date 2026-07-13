"""TTS Router — serve synthesized Vietnamese speech audio.

Endpoints:
  GET /tts/speak?text=...&voice=...  →  audio/mpeg (MP3)
  GET /tts/voices                    →  list of allowed voices
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Query
from fastapi.responses import Response

from app.config import settings
from app.dataset_manager import list_classes
from app.services.tts_service import (
    ALLOWED_VOICES,
    ALLOWED_VOICE_IDS,
    TTSSynthesisError,
    cache_exists,
    synthesize,
)

logger = logging.getLogger("tts_router")

router = APIRouter(prefix="/tts", tags=["tts"])


@router.get("/voices")
async def list_voices():
    """Return list of available Vietnamese TTS voices."""
    return {
        "voices": ALLOWED_VOICES,
        "default": settings.tts_default_voice,
    }


async def _prewarm_labels(labels: list[str], voices: list[str]) -> None:
    """Background worker: synthesize + cache every (label, voice) not yet cached."""
    warmed = 0
    for voice in voices:
        for label in labels:
            try:
                if await cache_exists(label, voice):
                    continue
                await synthesize(label, voice)
                warmed += 1
            except Exception as exc:  # never let one bad label abort the batch
                logger.warning("[TTS] prewarm failed for '%s' (%s): %s", label[:30], voice, exc)
    logger.info("[TTS] prewarm done: synthesized %d clip(s) across %d voice(s)", warmed, len(voices))


@router.post("/prewarm")
async def prewarm(background_tasks: BackgroundTasks, payload: dict = Body(default={})):
    """Pre-synthesize + cache TTS for a whole model's vocabulary.

    Given a language/dialect (the realtime model's), warms the Redis cache for
    every class label so the FIRST utterance of each sign is a cache hit
    (~105ms) instead of a cold edge-tts synthesis (~780ms) — for every user.
    Fire-and-forget: returns immediately and warms in the background; labels
    already cached are skipped, so repeat calls are cheap.
    """
    language = (payload.get("language") or "").strip() or None
    dialect = (payload.get("dialect") or "").strip() or None

    voices = payload.get("voices") or [settings.tts_default_voice]
    voices = [v for v in voices if v in ALLOWED_VOICE_IDS] or [settings.tts_default_voice]

    metas = list_classes(language=language, dialect=dialect)
    labels = sorted({
        (m.label_original or "").strip()
        for m in metas
        if (m.label_original or "").strip()
        and len((m.label_original or "").strip()) <= settings.tts_max_text_length
    })

    background_tasks.add_task(_prewarm_labels, labels, voices)
    return {
        "scheduled": len(labels) * len(voices),
        "labels": len(labels),
        "voices": len(voices),
    }


@router.get("/speak")
async def speak(
    text: str = Query(..., min_length=1, max_length=200, description="Text to synthesize"),
    voice: Optional[str] = Query(None, description="Voice ID (e.g. vi-VN-HoaiMyNeural)"),
):
    """Synthesize Vietnamese text to speech audio (MP3).

    Returns audio/mpeg binary response.
    Includes ``X-TTS-Cache`` header (``HIT`` or ``MISS``) for observability.
    """
    # Validate voice if provided
    if voice and voice not in ALLOWED_VOICE_IDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid voice '{voice}'. Allowed: {sorted(ALLOWED_VOICE_IDS)}",
        )

    # Validate text content
    clean_text = text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Text must not be empty")

    if len(clean_text) > settings.tts_max_text_length:
        raise HTTPException(
            status_code=400,
            detail=f"Text too long ({len(clean_text)} chars, max {settings.tts_max_text_length})",
        )

    try:
        mp3_bytes, cache_hit = await synthesize(clean_text, voice)
    except ValueError as exc:
        # Input validation error (bad voice, empty/too-long text)
        raise HTTPException(status_code=400, detail=str(exc))
    except TTSSynthesisError as exc:
        # Upstream (Microsoft edge-tts) failure after retries — not the client's fault
        logger.error("[TTS] upstream synthesis failed: %s", exc)
        raise HTTPException(status_code=502, detail="TTS service temporarily unavailable")
    except Exception as exc:
        logger.error("[TTS] synthesis error: %s", exc)
        raise HTTPException(status_code=500, detail="TTS synthesis failed")

    return Response(
        content=mp3_bytes,
        media_type="audio/mpeg",
        headers={
            "X-TTS-Cache": "HIT" if cache_hit else "MISS",
            "Cache-Control": "public, max-age=3600",  # browser cache 1h
            "Content-Disposition": "inline",
        },
    )
