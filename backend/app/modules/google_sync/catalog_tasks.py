"""Platform-wide maintenance tasks for dataset catalog mirrors."""

from __future__ import annotations

import logging

from app.config import settings
from app.infrastructure.celery.app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.export_tasks.sync_lookup_lists",
    max_retries=0,
    platform_wide=True,
)
def sync_lookup_lists(self, force: bool = False):
    """Refresh changed lookup sheets across every tenant."""
    if not getattr(settings, "use_google_drive", False):
        return {"status": "skipped", "reason": "gdrive_disabled"}

    import redis

    from app.modules.dataset import lookup_list

    lock = redis.from_url(settings.broker_url).lock(
        "voya:lookup-list:sync", timeout=3600, blocking=False
    )
    if not lock.acquire():
        return {"status": "skipped", "reason": "another sync is running"}
    try:
        result = lookup_list.sync_all(force=bool(force))
    finally:
        try:
            lock.release()
        except Exception:
            logger.warning("[LOOKUP] failed to release the synchronization lock")

    changed = {
        tenant: {
            key: value
            for key, value in report.items()
            if value not in ("khong doi", "chua toi gio")
        }
        for tenant, report in result.items()
    }
    logger.info(
        "[LOOKUP] sync done: %s",
        {tenant: report for tenant, report in changed.items() if report}
        or "khong co gi doi",
    )
    return {"status": "done", "result": result}


@celery_app.task(
    bind=True,
    name="app.export_tasks.reconcile_samples_csv_task",
    max_retries=2,
    default_retry_delay=30,
    platform_wide=True,
)
def reconcile_samples_csv_task(self):
    """Restore active PostgreSQL samples missing from the CSV mirror."""
    try:
        from app.modules.dataset.samples import reconcile_samples_csv_from_db

        restored = reconcile_samples_csv_from_db()
        if restored:
            logger.warning(
                "[RECONCILE] samples.csv healed: %d row(s) restored", restored
            )
        return {"status": "done", "restored": restored}
    except Exception as exc:
        logger.warning("[RECONCILE] task failed: %s", exc)
        return {"status": "error", "error": str(exc)}
