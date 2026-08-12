from __future__ import annotations

import argparse
import logging
import sys
import time

from app.config import settings
from app.db import init_db
from app.logging_config import configure_logging


def _redact_db_url(url: str) -> str:
    """Strip the password from a SQLAlchemy/libpq URL before logging.

    postgresql://user:secret@host:5432/db -> postgresql://user:***@host:5432/db
    Never let credentials reach the logs / Loki.
    """
    try:
        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(url)
        if parts.password:
            netloc = parts.hostname or ""
            if parts.username:
                netloc = f"{parts.username}:***@{netloc}"
            if parts.port:
                netloc = f"{netloc}:{parts.port}"
            parts = parts._replace(netloc=netloc)
        return urlunsplit(parts)
    except Exception:
        return "<hidden>"


def run_init_db(full_resync: bool = False) -> int:
    configure_logging()
    logger = logging.getLogger("cli.init_db")
    started_at = time.time()

    logger.info(
        "[INIT_DB] start dataset_root=%s database_url=%s full_resync=%s",
        settings.dataset_root,
        _redact_db_url(settings.database_url),
        full_resync,
    )

    try:
        ok = init_db(full_resync=full_resync)
        elapsed_ms = (time.time() - started_at) * 1000
        if ok:
            logger.info("[INIT_DB][SUCCESS] duration_ms=%.1f", elapsed_ms)
            return 0
        logger.warning("[INIT_DB][WARNING] init_db returned false duration_ms=%.1f", elapsed_ms)
        return 1
    except Exception as exc:
        logger.exception("[INIT_DB][FAILURE] %s", exc)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize VOYA backend database tables")
    parser.add_argument("--check", action="store_true", help="Run initialization and exit with status code")
    parser.add_argument(
        "--full-resync",
        action="store_true",
        help="Re-upsert EVERY CSV row, not just the ones Postgres is missing. "
             "Needed to propagate edits, since the CSVs carry no updated_at to diff on.",
    )
    args = parser.parse_args(argv)
    return run_init_db(full_resync=args.full_resync)


if __name__ == "__main__":
    sys.exit(main())