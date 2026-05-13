from __future__ import annotations

import logging
import threading
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


def _mirror_csv_to_gdrive_sync(local_path: Path, remote_path: str) -> None:
    if not getattr(settings, "use_google_drive", False):
        return

    path = Path(local_path)
    if not path.exists():
        return

    try:
        from app.storage.gdrive_client import upload_to_gdrive

        upload_to_gdrive(
            str(path),
            remote_path,
            content_type="text/csv",
            make_public=False,
        )
        logger.info("[CATALOG_MIRROR] uploaded %s to gdrive:%s", path, remote_path)
    except Exception as exc:
        logger.warning(
            "[CATALOG_MIRROR] failed to upload %s to gdrive:%s: %s",
            path,
            remote_path,
            exc,
        )


def mirror_csv_to_gdrive(local_path: Path, remote_path: str) -> None:
    """Best-effort background mirror for catalog CSV files after local updates."""
    thread = threading.Thread(
        target=_mirror_csv_to_gdrive_sync,
        args=(Path(local_path), remote_path),
        daemon=True,
    )
    thread.start()
