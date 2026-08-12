import logging
import time
import uuid
from datetime import datetime, timezone

from app.storage.rls import IsolationPostureError

logger = logging.getLogger("db.init")


def check_isolation_posture():
    """Report — and under strict mode, refuse — an isolation guarantee on paper only.

    Deliberately its own function so the boot path reads as one line and the
    swallow-everything handler in `init_db()` can single out this one failure
    (see the `except IsolationPostureError: raise` below). Everything else in
    `init_db()` is best-effort because Postgres is optional here; a database that
    claims tenant isolation and does not provide it is not a degraded mode, it is
    a false statement, and it must not be logged and stepped over.

    The check runs on a connection using the APPLICATION credentials, because
    that is the role whose privileges decide whether policies apply. Asking the
    migration DSN would report on the wrong role — and, once the roles are
    split, would always answer "superuser".
    """
    from app.config import settings
    from app.storage.metadata_db import _cursor
    from app.storage.rls import assert_isolation_enforceable

    with _cursor() as cur:
        return assert_isolation_enforceable(
            cur.connection, strict=settings.db_strict_isolation
        )


def init_db(full_resync: bool | None = None):
    """Run boot-time schema and sync work under platform scope.

    A thin wrapper rather than a `with` block inside `_init_db`, so the scope is
    impossible to fall out of by an early `return` added later — and so the diff
    that introduced it did not re-indent 130 lines of load-bearing code.

    Boot work legitimately spans tenants: the CSV->DB sync carries rows for every
    tenant and the integrity checks count across all of them. Unscoped, every one
    of those reads returns empty under row-level security — and empty is
    indistinguishable from "nothing to do", so `_existing_keys()` would conclude
    the database was empty and re-upsert the entire corpus on every boot.
    """
    from app.tenant_context import system_scope

    with system_scope("boot: schema init, integrity checks, CSV->DB sync"):
        return _init_db(full_resync)


def _init_db(full_resync: bool | None = None):
    """Initialize database tables.

    Note: this project primarily persists labels/samples to CSV + JSON sidecars.
    Postgres is optional and used for mirroring sample metadata via
    `app.storage.metadata_db`.

    Historically this module used SQLAlchemy to create legacy tables named
    `labels` and `samples`. Those schemas conflict with the current
    `samples(sample_uid, ...)` schema used by `metadata_db`.

    We now ensure the correct tables exist using `metadata_db.ensure_tables()`.
    """
    started_at = time.time()
    logger.info("[DB_INIT] starting schema initialization")
    try:
        from app.storage.metadata_db import ensure_tables, drop_all_tables, _column_exists
        ensure_tables()
        logger.info("[DB_INIT][SUCCESS] duration_ms=%.1f", (time.time() - started_at) * 1000)

        # Is the isolation guarantee actually in force? ensure_tables() has just
        # installed the policies; if the application role can bypass them, the
        # deployment now reports isolation it does not have. Checked here rather
        # than at first query so the answer is in the boot log, once, with the
        # role name in it. Raises only when DB_STRICT_ISOLATION is set — see
        # `storage/rls.assert_isolation_enforceable`.
        check_isolation_posture()

        # Vocabulary registry: seed once from config/dialects.seed.csv, then
        # Postgres owns it. Idempotent (ON CONFLICT DO NOTHING), so a display
        # name an operator edited in the app survives every redeploy.
        try:
            from app.vocabulary_registry import seed_from_csv
            seed_from_csv()
        except Exception as exc:
            logger.warning("[DB_INIT] vocabulary registry seed skipped: %s", exc)

        # Foreign keys from classes/samples into the registry. AFTER the seed
        # (a FK cannot reference rows that do not exist yet) and BEFORE the
        # sync below, so the very first import is already checked. Composite
        # key: dialects is keyed (tenant_id, dialect_id).
        try:
            from app.storage.metadata_db import (
                ensure_vocabulary_foreign_keys,
                unregistered_dialects_in_use,
            )

            orphans = unregistered_dialects_in_use()
            if orphans:
                # Name the blockers explicitly — a bare Postgres FK violation
                # says which constraint failed but never which values caused it.
                logger.warning(
                    "[DB_INIT] %d giá trị dialect chưa có trong danh mục: %s",
                    len(orphans),
                    ", ".join(
                        f"{o['src']}.{o['dialect']}({o['n']})" for o in orphans[:8]
                    ),
                )
            logger.info("[DB_INIT] vocabulary FK: %s", ensure_vocabulary_foreign_keys())
        except Exception as exc:
            logger.warning("[DB_INIT] vocabulary FK step skipped: %s", exc)

        # samples.csv must carry auth_user_id BEFORE the sync below runs,
        # otherwise every row it inserts lands with a NULL owner and its
        # contributor sees an empty personal Trash. Idempotent no-op once the
        # column exists.
        try:
            from app.dataset_samples import ensure_samples_column

            ensure_samples_column("auth_user_id")
        except Exception as exc:
            logger.warning("[DB_INIT] samples.csv auth_user_id migration skipped: %s", exc)

        # Same ordering requirement as auth_user_id above: samples.csv must
        # carry tenant_id BEFORE the sync runs, or every row it pushes arrives
        # with no tenant of its own.
        #
        # Unlike auth_user_id, existing rows are backfilled with a VALUE rather
        # than left blank. Every row that predates this migration provably
        # belongs to the bootstrap tenant, the Postgres column is NOT NULL, and
        # a blank cell would read back as "unassigned" — which is how the
        # rebuild-from-CSV path in this same function would lose another
        # tenant's partition. See docs/needFix/BACKEND_WORK_PLAN.md item A1.
        try:
            from app.dataset_samples import ensure_samples_column
            from app.tenancy import DEFAULT_TENANT_ID, TENANT_COLUMN

            if ensure_samples_column(TENANT_COLUMN, fill=DEFAULT_TENANT_ID):
                logger.info(
                    "[DB_INIT] samples.csv: đã thêm cột %s, dòng cũ backfill '%s'",
                    TENANT_COLUMN, DEFAULT_TENANT_ID,
                )
        except Exception as exc:
            logger.warning("[DB_INIT] samples.csv tenant_id migration skipped: %s", exc)

        # labels.csv migrates itself: _ensure_labels_file() detects the outdated
        # header and rewrites it. Touch it here so the migration happens BEFORE
        # the sync rather than on whichever request reads a class first.
        try:
            from app.dataset_manager import _ensure_labels_file

            _ensure_labels_file()
        except Exception as exc:
            logger.warning("[DB_INIT] labels.csv header migration skipped: %s", exc)

        # Check and sync missing data (Idempotent seed)
        success = sync_missing_data_on_startup(full=full_resync)
        
        # Check for missing critical schema changes that might not have applied properly
        schema_ok = _column_exists("samples", "deleted_at")
        
        # The drop is gated on the SCHEMA check alone — deliberately not on the
        # sync result any more.
        #
        # init_db() runs on every backend start, and sync_missing_data_on_startup()
        # returns False for ANY exception, including a transient one: the CSVs it
        # reads sit beside .lock files, so a concurrent writer is enough. The old
        # `if not success or not schema_ok` therefore let a momentary CSV read
        # error trigger drop_all_tables(), which DROPs users, refresh_tokens,
        # password_reset_tokens, training_jobs and training_metrics. None of those
        # exist in the CSVs — the re-seed restores classes/samples/raw_uploads
        # only, and bootstrap_admin_user() recreates just the admin. Every other
        # account and the whole training history were gone, permanently, because
        # a file was briefly locked.
        #
        # A failed sync does not call for demolishing the database: nothing is
        # corrupt, one read did not land. Report it and let the caller decide.
        if not schema_ok:
            logger.warning(
                "[DB_INIT] Schema is corrupt (samples.deleted_at missing) — rebuilding from CSV. "
                "NOTE: this drops users/training history, which the CSVs cannot restore."
            )
            drop_all_tables()
            ensure_tables()
            success_retry = sync_missing_data_on_startup()
            if not success_retry:
                logger.error("[DB_INIT] Retry sync failed.")
                return False
            return True

        if not success:
            logger.error(
                "[DB_INIT] Startup CSV->DB sync failed, but the schema is intact so the "
                "database was left untouched. The DB may be missing recent rows; re-run "
                "the sync once the underlying error is resolved."
            )
            return False

        return True
    except IsolationPostureError:
        # The one failure that must NOT be downgraded to "DB is optional".
        # Everything else here is best-effort because the app can serve from CSV
        # without Postgres; but booting an app that reports tenant isolation it
        # does not have is worse than not booting at all — it turns a known gap
        # into a false claim that every later check agrees with.
        raise
    except Exception:
        # Best-effort: DB is optional
        logger.exception("[DB_INIT][FAILURE] schema initialization failed")
        return False

def _existing_keys(table: str, key_column: str) -> set:
    """Every primary key currently in `table`, soft-deleted rows included.

    Soft-deleted rows must be counted as present: re-inserting one would
    resurrect a sample the owner deleted.
    """
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(f"SELECT {key_column} FROM {table}")
    return {str(r[key_column]).strip() for r in rows if r.get(key_column) is not None}


def _sync_one_table(
    *,
    label: str,
    table: str,
    key_column: str,
    csv_rows: list,
    upsert,
    full: bool,
) -> tuple[int, int]:
    """Push the rows Postgres is missing. Returns (written, only_in_db).

    Compares KEY SETS, not row counts — see sync_missing_data_on_startup().
    """
    if not csv_rows:
        return (0, 0)

    csv_by_key = {}
    for row in csv_rows:
        key = str(row.get(key_column) or "").strip()
        if key:
            csv_by_key[key] = row
    if not csv_by_key:
        return (0, 0)

    in_db = _existing_keys(table, key_column)
    missing_keys = [k for k in csv_by_key if k not in in_db]
    only_in_db = len(in_db - set(csv_by_key))

    to_write = list(csv_by_key.values()) if full else [csv_by_key[k] for k in missing_keys]
    for row in to_write:
        upsert(row)

    if full:
        logger.info("[STARTUP_SYNC] %s: re-upsert TOAN BO %d hang (full resync)", label, len(to_write))
    elif missing_keys:
        logger.info(
            "[STARTUP_SYNC] %s: CSV %d, DB %d -> them %d hang con thieu (vi du: %s)",
            label, len(csv_by_key), len(in_db), len(missing_keys), ", ".join(missing_keys[:5]),
        )
    else:
        logger.info("[STARTUP_SYNC] %s: CSV %d, DB %d -> khong thieu hang nao",
                    label, len(csv_by_key), len(in_db))

    if only_in_db:
        logger.warning(
            "[STARTUP_SYNC] %s: %d hang co trong DB nhung KHONG co trong CSV. "
            "Hang da xoa mem thi binh thuong; ngoai ra la dau hieu CSV bi ghi de "
            "hoac hai may ghi lech nhau.",
            label, only_in_db,
        )
    return (len(to_write), only_in_db)


def sync_missing_data_on_startup(full: bool | None = None) -> bool:
    """Push CSV rows that Postgres does not have. Parents before children.

    Idempotent: every write goes through ON CONFLICT DO UPDATE, which preserves
    deleted_at.

    Why this compares KEY SETS and not counts
    -----------------------------------------
    The previous version gated each table on `db_count < csv_count` and skipped
    the whole table otherwise. That gate is wrong in the one situation that
    actually occurs here:

      * Postgres keeps soft-deleted rows; the CSV holds active rows only. So
        after any deletion db_count >= csv_count permanently, the condition is
        never true again, and NO new row is ever synced — no matter how many
        the CSV has gained. That is why "lan nao sync cung khong cap nhat".
      * Even with equal counts the sets can differ (N added + N deleted).
      * A row edited in place never changes the count, so edits never
        propagated either.

    Comparing the sets of primary keys costs one indexed column scan and is
    correct in all of those cases.

    `full=True` (or VOYA_DB_FULL_RESYNC=1) additionally re-upserts rows that
    already exist, which is the only way to push EDITS, since neither CSV
    carries an updated_at column to diff against.
    """
    from app.dataset_manager import load_labels
    from app.dataset_samples import list_samples
    from app.raw_uploads import list_raw_uploads
    from app.storage.metadata_db import upsert_class, upsert_sample, upsert_raw_upload

    import os

    if full is None:
        full = os.getenv("VOYA_DB_FULL_RESYNC", "").strip().lower() in {"1", "true", "yes", "on"}

    started_at = time.time()
    total_written = 0
    try:
        # Order matters: classes is the parent of samples and raw_uploads.
        for label, table, key_column, rows, upsert in (
            ("classes", "classes", "class_uid", load_labels(), upsert_class),
            ("samples", "samples", "sample_uid", list_samples(), upsert_sample),
            ("raw_uploads", "raw_uploads", "upload_uid", list_raw_uploads(), upsert_raw_upload),
        ):
            written, _ = _sync_one_table(
                label=label, table=table, key_column=key_column,
                csv_rows=rows, upsert=upsert, full=full,
            )
            total_written += written

        logger.info("[STARTUP_SYNC][SUCCESS] da ghi %d hang, duration_ms=%.1f",
                    total_written, (time.time() - started_at) * 1000)
        return True
    except Exception as exc:
        logger.exception("[STARTUP_SYNC] Failed to sync missing data: %s", exc)
        return False

def bootstrap_admin_user():
    """Create admin user from .env if not already exists.
    
    Reads ADMIN_USERNAME and ADMIN_PASSWORD from settings and creates
    a user with is_admin=True if the username doesn't exist yet.
    """
    from app.config import settings
    
    admin_username = getattr(settings, "admin_username", "").strip()
    admin_password = getattr(settings, "admin_password", "").strip()
    
    if not admin_username or not admin_password:
        logger.debug("[BOOTSTRAP_ADMIN] ADMIN_USERNAME or ADMIN_PASSWORD not configured, skipping")
        return
    
    try:
        from app.storage.metadata_db import _column_exists, _execute
        from app.auth import _fetch_user_by_login, get_password_hash
        
        # Check if users table exists
        if not _column_exists("users", "id"):
            logger.warning("[BOOTSTRAP_ADMIN] users table does not exist yet, skipping")
            return
        
        # Check if admin user already exists
        existing = _fetch_user_by_login(admin_username)
        if existing:
            logger.info("[BOOTSTRAP_ADMIN] admin user '%s' already exists, skipping", admin_username)
            return
        
        # Create admin user
        admin_id = str(uuid.uuid4())
        password_hash = get_password_hash(admin_password)
        
        sql = """
        INSERT INTO users(id, username, email, password_hash, is_active, is_admin, created_at)
        VALUES(%s, %s, %s, %s, true, true, %s)
        ON CONFLICT (id) DO NOTHING
        """
        
        _execute(
            sql,
            (
                admin_id,
                admin_username,
                f"{admin_username}@admin.local",
                password_hash,
                datetime.now(timezone.utc),
            ),
        )
        
        logger.info("[BOOTSTRAP_ADMIN] admin user '%s' created successfully", admin_username)
        
    except Exception as exc:
        logger.error("[BOOTSTRAP_ADMIN] failed to create admin user: %s", exc)