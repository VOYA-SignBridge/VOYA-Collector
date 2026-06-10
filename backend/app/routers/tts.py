"""TTS Router — serve synthesized Vietnamese speech audio.

Endpoints:
  GET /tts/speak?text=...&voice=...  →  audio/mpeg (MP3)
  GET /tts/voices                    →  list of allowed voices
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.config import settings
from app.services.tts_service import ALLOWED_VOICES, ALLOWED_VOICE_IDS, synthesize

logger = logging.getLogger("tts_router")

router = APIRouter(prefix="/tts", tags=["tts"])


@router.get("/voices")
async def list_voices():
    """Return list of available Vietnamese TTS voices."""
    return {
        "voices": ALLOWED_VOICES,
        "default": settings.tts_default_voice,
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
        raise HTTPException(status_code=400, detail=str(exc))
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
