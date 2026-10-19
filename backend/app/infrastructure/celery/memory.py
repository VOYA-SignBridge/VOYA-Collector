"""Memory hygiene helpers for long-lived Celery worker processes."""

from __future__ import annotations

import ctypes
import ctypes.util
import gc
import logging

logger = logging.getLogger(__name__)

_libc = None
_malloc_trim_supported = None


def _get_libc():
    global _libc
    if _libc is None:
        try:
            _libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6")
        except Exception:
            _libc = False
    return _libc or None


def malloc_trim() -> bool:
    """Return freed heap pages to the OS when glibc supports it."""
    global _malloc_trim_supported
    if _malloc_trim_supported is False:
        return False
    libc = _get_libc()
    if libc is None or not hasattr(libc, "malloc_trim"):
        _malloc_trim_supported = False
        return False
    try:
        libc.malloc_trim(0)
        _malloc_trim_supported = True
        return True
    except Exception:
        _malloc_trim_supported = False
        return False


def get_rss_mb() -> float:
    """Return current process RSS in MiB, or -1 when unavailable."""
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        return -1.0


def release_memory(context: str = "") -> None:
    """Collect Python garbage and release free glibc pages after heavy tasks."""
    before = get_rss_mb()
    gc.collect()
    trimmed = malloc_trim()
    after = get_rss_mb()
    if before >= 0 and after >= 0:
        logger.info(
            "[MEM][RELEASE] %s rss %.0fMB -> %.0fMB (freed %.0fMB, trim=%s)",
            context or "-",
            before,
            after,
            max(0.0, before - after),
            trimmed,
        )
