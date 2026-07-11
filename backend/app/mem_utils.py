"""Memory hygiene helpers.

Central place for releasing memory back to the OS after heavy jobs
(video processing pulls large native buffers via MediaPipe/OpenCV/NumPy).

Two distinct problems are handled here:
  1. Python heap  -> gc.collect() frees unreachable objects.
  2. glibc arenas -> malloc_trim(0) returns freed pages to the OS.
     Without this, RSS stays at the peak even after Python has freed the
     objects, which looks like a leak on `docker stats`.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import gc
import logging

logger = logging.getLogger(__name__)

_libc = None
_malloc_trim_supported = None  # tri-state: None=unknown, True/False after probe


def _get_libc():
    global _libc
    if _libc is None:
        try:
            _libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6")
        except Exception:
            _libc = False  # sentinel: probed and unavailable
    return _libc or None


def malloc_trim() -> bool:
    """Return freed heap pages to the OS (glibc only). No-op elsewhere.

    Returns True if trim actually ran. Safe to call anywhere — never raises.
    """
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
    """Current process RSS in MB, or -1.0 if psutil is unavailable."""
    try:
        import psutil  # optional dependency

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        return -1.0


def release_memory(context: str = "") -> None:
    """Full release cycle: gc + malloc_trim, with optional RSS logging.

    Call after finishing a heavy unit of work (e.g. one video job).
    """
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
