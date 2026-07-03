from __future__ import annotations

import argparse
import logging
import sys
import time

from app.config import settings
from app.db import init_db
from app.logging_config import configure_logging


def run_init_db() -> int:
    configure_logging()
    logger = logging.getLogger("cli.init_db")
    started_at = time.time()

    logger.info(
        "[INIT_DB] start dataset_root=%s database_url=%s",
        settings.dataset_root,
        settings.database_url,
    )

    try:
        ok = init_db()
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
    parser.parse_args(argv)
    return run_init_db()


if __name__ == "__main__":
    sys.exit(main())