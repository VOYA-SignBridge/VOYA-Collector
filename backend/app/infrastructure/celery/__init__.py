"""Shared Celery application infrastructure."""

from app.infrastructure.celery.app import beat_schedule, celery_app

__all__ = ["beat_schedule", "celery_app"]
