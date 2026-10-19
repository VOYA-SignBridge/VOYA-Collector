"""Compatibility facade for Celery worker memory hygiene helpers."""

from app.infrastructure.celery.memory import get_rss_mb, malloc_trim, release_memory

__all__ = ["get_rss_mb", "malloc_trim", "release_memory"]
