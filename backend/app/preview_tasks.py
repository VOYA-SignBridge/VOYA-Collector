"""Celery task: pre-render a session's skeleton preview video (Tier 3).

Dispatched lazily by GET /classes/{uid}/sessions/{sid}/preview the first time
a client asks for a session that has no preview yet. Rendering is idempotent
(atomic overwrite), so a duplicate enqueue is wasteful but harmless.
"""

from __future__ import annotations

import logging

from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=15)
def render_session_preview_task(self, class_uid: str, session_id: str):
    from app.preview_render import render_preview_for_session

    try:
        out_path = render_preview_for_session(class_uid, session_id)
        return {"status": "ok", "path": str(out_path)}
    except (ValueError, FileNotFoundError) as exc:
        # Bad reference (class/session/npz gone) — retrying cannot fix it.
        logger.warning("[PREVIEW_TASK] permanent failure %s/%s: %s", class_uid, session_id, exc)
        return {"status": "failed", "error": str(exc)}
    except Exception as exc:
        logger.error("[PREVIEW_TASK] render failed %s/%s: %s", class_uid, session_id, exc)
        raise self.retry(exc=exc)
