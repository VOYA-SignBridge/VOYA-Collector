"""Database schema initialization and dataset catalog mirroring at startup."""

from __future__ import annotations

import logging
import os
import time

from app.storage.rls import IsolationPostureError

logger = logging.getLogger("db.init")


def check_isolation_posture():
    """Verify RLS using the application connection after policies are installed."""
    from app.config import settings
    from app.storage.metadata_db import _cursor
    from app.storage.rls import assert_isolation_enforceable

    with _cursor() as cur:
        return assert_isolation_enforceable(
            cur.connection, strict=settings.db_strict_isolation
        )


def _existing_keys(table: str, key_column: str) -> set[str]:
    """Return every persisted key, including keys of soft-deleted rows."""
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(f"SELECT {key_column} FROM {table}")
    return {
        str(row[key_column]).strip()
        for row in rows
        if row.get(key_column) is not None
    }


def _sync_one_table(
    *,
    label: str,
    table: str,
    key_column: str,
    csv_rows: list,
    upsert,
    full: bool,
) -> tuple[int, int]:
    """Push missing rows and return ``(written, rows_only_in_database)``."""
    if not csv_rows:
        return (0, 0)

    csv_by_key = {}
    for row in csv_rows:
        key = str(row.get(key_column) or "").strip()
        if key:
            csv_by_key[key] = row
    if not csv_by_key:
        return (0, 0)

    database_keys = _existing_keys(table, key_column)
    missing_keys = [key for key in csv_by_key if key not in database_keys]
    only_in_database = len(database_keys - set(csv_by_key))
    rows_to_write = (
        list(csv_by_key.values())
        if full
        else [csv_by_key[key] for key in missing_keys]
    )
    for row in rows_to_write:
        upsert(row)

    if full:
        logger.info(
            "[STARTUP_SYNC] %s: re-upsert all %d rows", label, len(rows_to_write)
        )
    elif missing_keys:
        logger.info(
            "[STARTUP_SYNC] %s: CSV %d, DB %d; adding %d missing rows",
            label,
            len(csv_by_key),
            len(database_keys),
            len(missing_keys),
        )
    if only_in_database:
        logger.warning(
            "[STARTUP_SYNC] %s: %d rows exist only in PostgreSQL",
            label,
            only_in_database,
        )
    return (len(rows_to_write), only_in_database)


def sync_missing_data_on_startup(full: bool | None = None) -> bool:
    """Mirror CSV records by primary-key set, with parents written first."""
    from app.modules.dataset.catalog import _load_all_labels_unscoped
    from app.modules.dataset.raw_uploads import list_raw_uploads
    from app.modules.dataset.samples import _load_all_samples_unscoped
    from app.storage.metadata_db import (
        upsert_class,
        upsert_raw_upload,
        upsert_sample,
    )

    if full is None:
        full = os.getenv("VOYA_DB_FULL_RESYNC", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    started_at = time.time()
    total_written = 0
    try:
        for label, table, key_column, rows, upsert in (
            (
                "classes",
                "classes",
                "class_uid",
                _load_all_labels_unscoped(),
                upsert_class,
            ),
            (
                "samples",
                "samples",
                "sample_uid",
                _load_all_samples_unscoped(),
                upsert_sample,
            ),
            (
                "raw_uploads",
                "raw_uploads",
                "upload_uid",
                list_raw_uploads(),
                upsert_raw_upload,
            ),
        ):
            written, _ = _sync_one_table(
                label=label,
                table=table,
                key_column=key_column,
                csv_rows=rows,
                upsert=upsert,
                full=full,
            )
            total_written += written
        logger.info(
            "[STARTUP_SYNC][SUCCESS] wrote %d rows, duration_ms=%.1f",
            total_written,
            (time.time() - started_at) * 1000,
        )
        return True
    except Exception as exc:
        logger.exception("[STARTUP_SYNC] Failed to sync missing data: %s", exc)
        return False


def init_db(full_resync: bool | None = None) -> bool:
    """Run platform-wide bootstrap work under an explicit system scope."""
    from app.modules.saas.tenant_context import system_scope

    with system_scope("boot: schema init, integrity checks, CSV->DB sync"):
        return _init_db(full_resync)


def _init_db(full_resync: bool | None = None) -> bool:
    """Ensure the current metadata schema exists, then mirror missing records.

    PostgreSQL remains best-effort for application startup, so initialization
    reports failure instead of preventing the HTTP service from starting.
    """
    started_at = time.time()
    logger.info("[DB_INIT] starting schema initialization")
    try:
        from app.storage.metadata_db import (
            _column_exists,
            drop_all_tables,
            ensure_tables,
        )

        ensure_tables()
        check_isolation_posture()

        try:
            from app.modules.dataset.vocabulary_registry import seed_from_csv

            seed_from_csv()
        except Exception as exc:
            logger.warning("[DB_INIT] vocabulary registry seed skipped: %s", exc)

        try:
            from app.storage.metadata_db import (
                ensure_vocabulary_foreign_keys,
                unregistered_dialects_in_use,
            )

            orphans = unregistered_dialects_in_use()
            if orphans:
                logger.warning(
                    "[DB_INIT] %d unregistered dialect values are in use: %s",
                    len(orphans),
                    ", ".join(
                        f"{row['src']}.{row['dialect']}({row['n']})"
                        for row in orphans[:8]
                    ),
                )
            logger.info(
                "[DB_INIT] vocabulary FK: %s", ensure_vocabulary_foreign_keys()
            )
        except Exception as exc:
            logger.warning("[DB_INIT] vocabulary FK step skipped: %s", exc)

        try:
            from app.modules.dataset.samples import ensure_samples_column

            ensure_samples_column("auth_user_id")
        except Exception as exc:
            logger.warning("[DB_INIT] sample owner migration skipped: %s", exc)

        try:
            from app.modules.dataset.samples import ensure_samples_column
            from app.modules.saas.tenancy import DEFAULT_TENANT_ID, TENANT_COLUMN

            if ensure_samples_column(TENANT_COLUMN, fill=DEFAULT_TENANT_ID):
                logger.info(
                    "[DB_INIT] samples.csv: added %s and backfilled %s",
                    TENANT_COLUMN,
                    DEFAULT_TENANT_ID,
                )
        except Exception as exc:
            logger.warning("[DB_INIT] sample tenant migration skipped: %s", exc)

        try:
            from app.modules.dataset.catalog import _ensure_labels_file

            _ensure_labels_file()
        except Exception as exc:
            logger.warning("[DB_INIT] labels.csv header migration skipped: %s", exc)

        logger.info(
            "[DB_INIT][SUCCESS] duration_ms=%.1f",
            (time.time() - started_at) * 1000,
        )
        sync_succeeded = sync_missing_data_on_startup(full=full_resync)
        schema_is_healthy = _column_exists("samples", "deleted_at")

        # A catalog read can fail transiently while a CSV writer holds its lock.
        # That is not evidence of database corruption and must never trigger the
        # destructive recovery path: users and training history are not mirrored
        # in those CSV files and could not be restored afterwards.
        if schema_is_healthy:
            if not sync_succeeded:
                logger.error(
                    "[DB_INIT] Startup CSV->DB sync failed, but the schema is "
                    "intact; the database was left untouched."
                )
            return sync_succeeded

        logger.warning(
            "[DB_INIT] Schema is corrupt (samples.deleted_at missing); "
            "rebuilding from CSV. This drops data that the CSV catalog may not "
            "be able to restore."
        )
        drop_all_tables()
        ensure_tables()
        if not sync_missing_data_on_startup():
            logger.error("[DB_INIT] Retry sync failed after schema rebuild.")
            return False
        return True
    except IsolationPostureError:
        raise
    except Exception:
        logger.exception("[DB_INIT][FAILURE] schema initialization failed")
        return False
