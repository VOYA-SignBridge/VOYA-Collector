"""Pull + apply the latest SOT version — READER path (server/VPS, read-only).

Runs at deploy time BEFORE any worker, and NEVER writes to the store. Order:

  1. Read LATEST.json + LATEST.sig, VERIFY the signature against the committed
     authorized keys. Unsigned/forged => REJECT, touch nothing.
  2. Read that version's manifest + signature, VERIFY it too, and confirm
     LATEST actually points at this manifest (sha256 match).
  3. Download each catalog CSV and check its sha256 against the signed manifest.
     Any mismatch (tamper / truncated) => REJECT, touch nothing.
  4. Apply the schema idempotently, then confirm every required column exists
     (schema must be a SUPERSET of SOT — extra columns are fine, missing is not).
  5. Upsert every SOT row (superset data sync): add/update, NEVER delete rows the
     server has beyond SOT.

All DB operations are injected so this is unit-testable without Postgres; the
production wiring lives in `run_sync()`.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from app.sot import keys, manifest as m
from app.sot.store import SotStore, read_text

logger = logging.getLogger(__name__)


class SotSyncRejected(RuntimeError):
    """Raised when SOT content fails verification; the DB is left untouched."""


@dataclass
class SyncResult:
    status: str
    version: Optional[str] = None
    signed_by: Optional[str] = None
    schema_applied: bool = False
    schema_gaps: List[str] = field(default_factory=list)
    rows_upserted: Dict[str, int] = field(default_factory=dict)
    rows_failed: Dict[str, int] = field(default_factory=dict)
    server_extras: Dict[str, int] = field(default_factory=dict)
    reason: Optional[str] = None


# Injected DB surface — bound to metadata_db in run_sync(), faked in tests.
@dataclass
class CatalogSink:
    apply_schema: Callable[[str], None]
    column_exists: Callable[[str, str], bool]
    count_rows: Callable[[str], int]
    upsert_class: Callable[[dict], None]
    upsert_sample: Callable[[dict], None]
    upsert_raw_upload: Callable[[dict], None]


# Which CSV feeds which table + upsert.
_CSV_TABLE = {
    "labels.csv": "classes",
    "samples.csv": "samples",
    "raw_uploads.csv": "raw_uploads",
}


def _parse_csv(data: bytes) -> List[dict]:
    return list(csv.DictReader(io.StringIO(data.decode("utf-8"))))


def _read_or_reject(store: SotStore, rel_path: str, what: str) -> bytes:
    """Read a file the version/manifest promises exists.

    A missing file means the publish is INCOMPLETE (not every file uploaded) or a
    file was renamed/removed on the store. Turn that into a clean SotSyncRejected
    so `_cmd_sync` reports "REJECTED (DB untouched)" and exits 4 — instead of the
    raw FileNotFoundError bubbling up as an uncaught traceback + exit 1, which
    hides the real cause (exactly the confusing failure a renamed labels.csv gave).
    """
    try:
        return store.read_bytes(rel_path)
    except FileNotFoundError as exc:
        raise SotSyncRejected(
            f"incomplete SOT version: missing {what} ({rel_path}) — the publish did "
            "not upload every file, or a file was renamed/removed on the store"
        ) from exc


def sync_from_sot(store: SotStore, sink: CatalogSink, *, authorized_keys: List[dict]) -> SyncResult:
    # --- 1. LATEST + signature ------------------------------------------------
    if not store.exists(m.LATEST_NAME):
        return SyncResult(status="empty", reason="no LATEST.json in SOT (nothing published yet)")

    latest_bytes = store.read_bytes(m.LATEST_NAME)
    try:
        latest_sig = read_text(store, m.LATEST_SIG_NAME)
    except Exception as exc:
        raise SotSyncRejected(f"LATEST.sig missing/unreadable: {exc}") from exc

    if keys.verify_with_authorized(latest_bytes, latest_sig, authorized_keys) is None:
        raise SotSyncRejected("LATEST.json signature not from any registered machine — rejected")

    import json

    latest = json.loads(latest_bytes.decode("utf-8"))
    version = latest.get("version")
    parsed = m.parse_version_name(str(version or ""))
    if not parsed:
        raise SotSyncRejected(f"LATEST points at invalid version name: {version!r}")

    # --- 2. Manifest + signature ---------------------------------------------
    manifest_bytes = _read_or_reject(store, f"{version}/{m.MANIFEST_NAME}", "manifest.json")
    manifest_sig = _read_or_reject(store, f"{version}/{m.MANIFEST_SIG_NAME}", "manifest.sig").decode("utf-8")
    signed_by = keys.verify_with_authorized(manifest_bytes, manifest_sig, authorized_keys)
    if signed_by is None:
        raise SotSyncRejected(f"{version} manifest signature invalid — rejected")

    if latest.get("manifest_sha256") != m.sha256_bytes(manifest_bytes):
        raise SotSyncRejected("LATEST.manifest_sha256 does not match the version's manifest")

    manifest = json.loads(manifest_bytes.decode("utf-8"))
    m.validate_manifest_shape(manifest)
    if manifest.get("version") != version:
        raise SotSyncRejected("manifest.version disagrees with LATEST.version")

    # --- 3. Download + checksum every catalog file ---------------------------
    file_hashes = manifest["files"]
    csv_bytes: Dict[str, bytes] = {}
    for name in m.CATALOG_FILES:
        data = _read_or_reject(store, f"{version}/{name}", name)
        expected = file_hashes.get(name)
        if expected != m.sha256_bytes(data):
            raise SotSyncRejected(f"{name} checksum mismatch (tampered/truncated) — rejected")
        csv_bytes[name] = data

    schema_sql = _read_or_reject(store, f"{version}/schema/schema.sql", "schema/schema.sql")
    if file_hashes.get("schema/schema.sql") != m.sha256_bytes(schema_sql):
        raise SotSyncRejected("schema.sql checksum mismatch — rejected")

    result = SyncResult(status="applied", version=version, signed_by=signed_by)

    # --- 4. Schema: apply idempotently, then verify SUPERSET coverage --------
    sink.apply_schema(schema_sql.decode("utf-8"))
    result.schema_applied = True
    for table, cols in manifest.get("required_columns", {}).items():
        for col in cols:
            if not sink.column_exists(table, col):
                result.schema_gaps.append(f"{table}.{col}")
    if result.schema_gaps:
        # Schema is NOT a superset — do not import data against an incomplete schema.
        raise SotSyncRejected(
            f"schema missing required columns after apply: {result.schema_gaps}"
        )

    # --- 5. Data: superset upsert (add/update, never delete server extras) ----
    upsert_by_table = {
        "classes": sink.upsert_class,
        "samples": sink.upsert_sample,
        "raw_uploads": sink.upsert_raw_upload,
    }
    for name in m.CATALOG_FILES:
        table = _CSV_TABLE[name]
        rows = _parse_csv(csv_bytes[name])
        upsert = upsert_by_table[table]
        # Per-row isolation: the content is already signature+checksum verified,
        # so a row that fails here is an operational hiccup (e.g. a stray bad
        # row / constraint), NOT tampering. Skip it and keep going rather than
        # aborting the whole sync — a single row must not block the deploy.
        # Each upsert() is its own DB transaction, so a failure rolls back only
        # that row and never poisons the ones after it.
        ok = 0
        failed = 0
        for row in rows:
            try:
                upsert(row)
                ok += 1
            except Exception as exc:
                failed += 1
                logger.warning("[SOT] %s: skipped a row that failed to upsert: %s", table, exc)
        result.rows_upserted[table] = ok
        if failed:
            result.rows_failed[table] = failed
        # Superset visibility: how many rows the server has beyond SOT.
        try:
            extra = sink.count_rows(table) - len(rows)
            result.server_extras[table] = max(0, extra)
        except Exception:
            pass

    logger.info(
        "[SOT] synced %s signed_by=%s upserted=%s failed=%s extras=%s",
        version, signed_by, result.rows_upserted, result.rows_failed, result.server_extras,
    )
    return result


# ---------------------------------------------------------------------------
# Production wiring
# ---------------------------------------------------------------------------

def effective_authorized_keys() -> List[dict]:
    """Committed baseline (authorized_keys.json) UNION the DB-managed registry.

    The DB registry lets an admin register/revoke writer machines at runtime (via
    the SOT admin page) and have THIS deployment's reader trust them immediately,
    with no git commit + redeploy. The committed file stays the always-on baseline;
    if the DB is unreachable we fall back to it alone — fail-safe, since an outage
    then NARROWS trust (fewer accepted signers), never widens it.
    """
    merged = {
        e.get("public_key"): e
        for e in keys.load_authorized_keys()
        if e.get("public_key")
    }
    try:
        from app.storage import metadata_db as db

        for row in db.sot_list_authorized_keys(include_revoked=False):
            pk = row.get("public_key")
            if pk and pk not in merged:  # committed baseline wins on conflict
                merged[pk] = {
                    "name": row.get("name"),
                    "public_key": pk,
                    "fingerprint": row.get("fingerprint"),
                }
    except Exception as exc:
        logger.warning(
            "[SOT] DB authorized-key lookup failed; using committed baseline only: %s", exc
        )
    return list(merged.values())


def run_sync() -> SyncResult:
    """Entry point for the `sot-init` container / CLI `sync`.

    Binds the injected DB surface to metadata_db + the real Drive store, then
    runs sync_from_sot. Returns a SyncResult; raises SotSyncRejected on bad SOT.
    """
    from app.sot.store import GDriveSotStore
    from app.storage import metadata_db as db

    store = GDriveSotStore(read_only=True)
    sink = CatalogSink(
        apply_schema=_apply_schema_sql,
        column_exists=db._column_exists,
        count_rows=lambda t: db._fetch_all(f"SELECT COUNT(*) AS c FROM {t}")[0]["c"],
        upsert_class=db.upsert_class,
        upsert_sample=db.upsert_sample,
        upsert_raw_upload=db.upsert_raw_upload,
    )
    authorized = effective_authorized_keys()
    return sync_from_sot(store, sink, authorized_keys=authorized)


_DOLLAR_TAG_RE = re.compile(r"\$[A-Za-z0-9_]*\$")


def _split_sql_statements(sql: str) -> List[str]:
    """Split SQL on top-level ';' only.

    A naive ``sql.split(';')`` breaks the moment a statement legitimately
    contains a ';' — e.g. a future trigger / PL-pgSQL function body wrapped in
    ``$$ ... ; ... $$`` — silently dropping half a CREATE and leaving the table
    unbuilt. This respects single-quoted strings and ``$tag$``-dollar-quoted
    blocks so the whole body stays one statement.
    """
    stmts: List[str] = []
    buf: List[str] = []
    i, n = 0, len(sql)
    in_squote = False
    dollar_tag: Optional[str] = None
    while i < n:
        ch = sql[i]
        if dollar_tag is not None:
            if sql.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
            else:
                buf.append(ch)
                i += 1
            continue
        if in_squote:
            buf.append(ch)
            if ch == "'":
                in_squote = False
            i += 1
            continue
        if ch == "'":
            in_squote = True
            buf.append(ch)
            i += 1
            continue
        if ch == "$":
            mt = _DOLLAR_TAG_RE.match(sql, i)
            if mt:
                tag = mt.group(0)
                dollar_tag = tag
                buf.append(tag)
                i += len(tag)
                continue
        if ch == ";":
            stmts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf)
    if tail.strip():
        stmts.append(tail)
    return [s.strip() for s in stmts if s.strip()]


def _apply_schema_sql(schema_sql: str) -> None:
    """Run each statement idempotently; a failing stmt must not abort the rest."""
    from app.storage.metadata_db import _execute

    for stmt in _split_sql_statements(schema_sql):
        try:
            _execute(stmt)
        except Exception as exc:
            logger.warning("[SOT] schema stmt skipped: %s : %s", exc, stmt[:100])
