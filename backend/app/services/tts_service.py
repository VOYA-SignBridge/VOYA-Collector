"""TTS Service — edge-tts synthesis with Redis cache.

Cache key format: ``tts:{voice}:{sha256(normalized_text)}``
All keys share Redis DB 0 with the ``tts:`` prefix to coexist with Celery.

Thundering-herd protection:
  When N concurrent requests arrive for the same uncached label, an
  ``asyncio.Lock`` per cache-key ensures only **one** coroutine calls
  edge-tts; the remaining N-1 wait for the lock, then read from cache.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
from typing import Dict, List, Optional

import edge_tts
import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("tts_service")

# ---------------------------------------------------------------------------
# Module-level state (initialized at application startup)
# ---------------------------------------------------------------------------
_redis_pool: Optional[aioredis.Redis] = None
_synth_semaphore: Optional[asyncio.Semaphore] = None

# Per-key locks to prevent thundering herd.  Bounded: evicted after use.
_key_locks: Dict[str, asyncio.Lock] = {}
_key_locks_guard = asyncio.Lock()

# Allowed Vietnamese voices (whitelist)
ALLOWED_VOICES: List[Dict[str, str]] = [
    {
        "id": "vi-VN-HoaiMyNeural",
        "name": "HoaiMy",
        "gender": "female",
        "description": "Giọng nữ ",
    },
    {
        "id": "vi-VN-NamMinhNeural",
        "name": "NamMinh",
        "gender": "male",
        "description": "Giọng nam ",
    },
]

ALLOWED_VOICE_IDS = {v["id"] for v in ALLOWED_VOICES}

CACHE_KEY_PREFIX = "tts"


class TTSSynthesisError(Exception):
    """Raised when edge-tts synthesis fails after all retry attempts.

    Upstream (Microsoft) failure — callers should map this to 502, not 400.
    """


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

async def init_tts() -> None:
    """Initialize Redis connection pool and concurrency semaphore."""
    global _redis_pool, _synth_semaphore

    _redis_pool = aioredis.from_url(
        settings.tts_redis_url,
        decode_responses=False,  # binary values (mp3 bytes)
        max_connections=20,
    )
    _synth_semaphore = asyncio.Semaphore(settings.tts_max_concurrent_synth)

    # Verify connectivity
    try:
        await _redis_pool.ping()
        logger.info("[TTS] Redis connected: %s", settings.tts_redis_url)
    except Exception as exc:
        logger.warning("[TTS] Redis ping failed (will retry on demand): %s", exc)


async def close_tts() -> None:
    """Gracefully close Redis pool."""
    global _redis_pool
    if _redis_pool is not None:
        # redis-py renamed the async close to aclose() in 5.0.1; the pinned
        # 4.5.1 only exposes close(). Prefer aclose() so a future bump keeps
        # working, but fall back so shutdown never raises AttributeError
        # ("Application shutdown failed. Exiting.").
        closer = getattr(_redis_pool, "aclose", None) or getattr(_redis_pool, "close", None)
        try:
            if closer is not None:
                await closer()
        except Exception as exc:  # pragma: no cover - best-effort cleanup
            logger.warning("[TTS] Redis pool close failed: %s", exc)
        _redis_pool = None
    logger.info("[TTS] Redis pool closed")


# ---------------------------------------------------------------------------
# Cache key helpers
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """Normalize text for consistent cache keys."""
    return text.strip().lower()


def _cache_key(voice: str, text: str) -> str:
    """Build cache key: ``tts:{voice}:{sha256(normalized_text)}``."""
    normalized = _normalize_text(text)
    text_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{CACHE_KEY_PREFIX}:{voice}:{text_hash}"


# ---------------------------------------------------------------------------
# Per-key lock management (thundering herd)
# ---------------------------------------------------------------------------

async def _acquire_key_lock(key: str) -> asyncio.Lock:
    async with _key_locks_guard:
        if key not in _key_locks:
            _key_locks[key] = asyncio.Lock()
        return _key_locks[key]


async def _release_key_lock(key: str) -> None:
    """Remove lock entry if no one else is waiting (prevents memory leak)."""
    async with _key_locks_guard:
        lock = _key_locks.get(key)
        if lock is not None and not lock.locked():
            _key_locks.pop(key, None)


# ---------------------------------------------------------------------------
# Core synthesis
# ---------------------------------------------------------------------------

async def _synthesize_to_bytes(text: str, voice: str) -> bytes:
    """Call edge-tts and return raw MP3 bytes."""
    communicate = edge_tts.Communicate(text, voice)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    mp3_bytes = buf.getvalue()
    if not mp3_bytes:
        raise ValueError(f"edge-tts returned empty audio for text='{text}' voice={voice}")
    return mp3_bytes


async def _synthesize_with_retry(text: str, voice: str) -> bytes:
    """Synthesize with timeout + one retry.

    edge-tts is an unofficial Microsoft service: calls can hang or fail
    transiently. A timeout keeps the per-key lock and semaphore from being
    held forever (5 hung calls would otherwise exhaust the semaphore and
    freeze TTS for the whole app until restart).

    Raises TTSSynthesisError after both attempts fail.
    """
    last_exc: Optional[BaseException] = None
    for attempt in (1, 2):
        try:
            return await asyncio.wait_for(
                _synthesize_to_bytes(text, voice),
                timeout=settings.tts_synth_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            last_exc = exc
            logger.warning(
                "[TTS] synth attempt %d/2 timed out after %.0fs (voice=%s, text='%s')",
                attempt, settings.tts_synth_timeout_seconds, voice, text[:30],
            )
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "[TTS] synth attempt %d/2 failed (voice=%s, text='%s'): %s",
                attempt, voice, text[:30], exc,
            )
        if attempt == 1:
            await asyncio.sleep(0.5)  # brief backoff before retry

    raise TTSSynthesisError(f"edge-tts synthesis failed after 2 attempts: {last_exc}")


# ---------------------------------------------------------------------------
# Redis-safe cache helpers (graceful degradation)
#
# If Redis is down, TTS must still work — we skip the cache and synthesize
# directly instead of returning 500 while edge-tts is perfectly healthy.
# ---------------------------------------------------------------------------

async def _cache_get(key: str) -> Optional[bytes]:
    if _redis_pool is None:
        return None
    try:
        return await _redis_pool.get(key)
    except Exception as exc:
        logger.warning("[TTS] Redis GET failed (degraded: no cache): %s", exc)
        return None


async def _cache_set(key: str, value: bytes) -> bool:
    if _redis_pool is None:
        return False
    try:
        await _redis_pool.set(key, value, ex=settings.tts_cache_ttl_seconds)
        return True
    except Exception as exc:
        logger.warning("[TTS] Redis SET failed (audio not cached): %s", exc)
        return False


async def synthesize(
    text: str,
    voice: Optional[str] = None,
) -> tuple[bytes, bool]:
    """Synthesize text to MP3 audio with Redis caching.

    Returns ``(mp3_bytes, cache_hit)`` tuple.

    Thundering-herd safe: concurrent requests for the same key
    coalesce into a single edge-tts call.
    """
    voice = voice or settings.tts_default_voice

    # Validate voice
    if voice not in ALLOWED_VOICE_IDS:
        raise ValueError(f"Voice '{voice}' not allowed. Allowed: {ALLOWED_VOICE_IDS}")

    # Validate text length
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("Text must not be empty")
    if len(clean_text) > settings.tts_max_text_length:
        raise ValueError(f"Text too long ({len(clean_text)} > {settings.tts_max_text_length})")

    key = _cache_key(voice, clean_text)

    # 1. Fast path: cache HIT (Redis failure degrades to miss, not error)
    cached = await _cache_get(key)
    if cached is not None:
        return cached, True

    # 2. Slow path: acquire per-key lock to prevent thundering herd
    lock = await _acquire_key_lock(key)
    try:
        async with lock:
            # Double-check after acquiring lock (another coroutine may have populated)
            cached = await _cache_get(key)
            if cached is not None:
                return cached, True

            # Actual synthesis (bounded by semaphore, with timeout + retry)
            async with _synth_semaphore:  # type: ignore[union-attr]
                logger.info("[TTS] MISS key=%s voice=%s text='%s'", key, voice, clean_text[:50])
                mp3_bytes = await _synthesize_with_retry(clean_text, voice)

            # Store in Redis (best-effort; failure only means no caching)
            if await _cache_set(key, mp3_bytes):
                logger.info("[TTS] cached key=%s size=%d ttl=%ds", key, len(mp3_bytes), settings.tts_cache_ttl_seconds)

            return mp3_bytes, False
    finally:
        await _release_key_lock(key)


def invalidate_text_cache_sync(text: str) -> int:
    """Best-effort SYNC purge of one label's cached audio across all voices.

    Called from the (synchronous) catalog mutation path when a label is renamed
    or deleted, so stale clips don't linger until TTL. Uses a short-lived sync
    Redis client (the module's async pool can't be awaited here). Never raises;
    returns the number of keys deleted (0 on any failure).
    """
    clean = (text or "").strip()
    if not clean:
        return 0
    try:
        import redis as _sync_redis

        client = _sync_redis.from_url(
            settings.tts_redis_url,
            socket_connect_timeout=2,
            socket_timeout=3,
        )
        keys = [_cache_key(v["id"], clean) for v in ALLOWED_VOICES]
        deleted = int(client.delete(*keys)) if keys else 0
        if deleted:
            logger.info("[TTS] invalidated %d cached clip(s) for '%s'", deleted, clean[:40])
        return deleted
    except Exception as exc:  # pragma: no cover - infra dependent
        logger.warning("[TTS] cache invalidate failed for '%s': %s", clean[:40], exc)
        return 0


async def cache_exists(text: str, voice: Optional[str] = None) -> bool:
    """Check if audio for given text+voice is already cached.

    Returns False (instead of raising) when Redis is unavailable.
    """
    voice = voice or settings.tts_default_voice
    key = _cache_key(voice, text.strip())
    if _redis_pool is None:
        return False
    try:
        return await _redis_pool.exists(key) > 0
    except Exception as exc:
        logger.warning("[TTS] Redis EXISTS failed (treated as miss): %s", exc)
        return False
