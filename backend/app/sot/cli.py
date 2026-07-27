"""SOT command line — `python -m app.sot.cli <cmd>`.

    keygen  --name <machine>   register THIS machine as a writer (creates the
                               private key outside the repo + appends its public
                               key to authorized_keys.json for you to commit)
    publish                    snapshot local CSV + schema into a new SOT version
                               (registered machines only)
    verify  [--version Ver..]  verify signatures/checksums without applying
    sync                       reader path: pull latest, verify, update DB
                               (what the sot-init container runs on the server)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.sot import keys


def _cmd_keygen(args: argparse.Namespace) -> int:
    key_path = Path(args.key_path) if args.key_path else keys.DEFAULT_PRIVATE_KEY_PATH
    try:
        private_key = keys.generate_private_key()
        saved = keys.save_private_key(private_key, key_path, force=args.force)
    except FileExistsError as exc:
        print(f"[keygen] {exc}", file=sys.stderr)
        return 1

    public_b64 = keys.public_key_b64(private_key)
    try:
        keys.add_authorized_key(args.name, public_b64)
        registered = True
    except ValueError as exc:
        registered = False
        print(f"[keygen] NOTE: not added to authorized_keys.json: {exc}", file=sys.stderr)

    print(f"[keygen] private key written to: {saved} (keep secret, never commit)")
    print(f"[keygen] public key : {public_b64}")
    print(f"[keygen] fingerprint: {keys.fingerprint(public_b64)}")
    if registered:
        print("[keygen] added to app/sot/authorized_keys.json — review, then:")
        print('           git add app/sot/authorized_keys.json && git commit -m "sot: register '
              f'{args.name}" && git push')
    return 0


def _csv_cell(value) -> str:
    """Serialize a DB value into a CSV cell the reader's coercers accept:
    None -> "" (becomes NULL), bool -> "true"/"false" (what _bool_value reads),
    everything else -> str() (ints/floats/timestamps parse straight back)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _rows_to_csv_bytes(fieldnames, rows) -> bytes:
    import csv
    import io

    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=list(fieldnames), extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _csv_cell(row.get(k)) for k in fieldnames})
    return buf.getvalue().encode("utf-8")


def _gather_csv_sources() -> dict:
    """Snapshot the catalog straight from the DATABASE — NOT the on-disk CSV mirror.

    Why the DB and not labels.csv/samples.csv/raw_uploads.csv: the SOT reader
    writes synced data into the DB only, never back to those files. So a machine
    that received data via SOT holds it in the DB but not in the files; publishing
    from the files would silently DROP exactly that data ("SOT thiếu dữ liệu đang
    có trong database"). Reading the DB makes a publish a faithful superset of
    everything the machine knows.

    Columns are exactly the keys each reader upsert consumes, so the CSV round-
    trips cleanly (DB -> CSV -> reader upsert -> DB). Soft-deleted rows
    (deleted_at IS NOT NULL) are excluded so a delete is never resurrected.
    """
    from app.storage import metadata_db as db

    specs = (
        ("labels.csv", "classes", db._CLASS_DB_KEYS),
        ("samples.csv", "samples", db._SAMPLE_DB_KEYS),
        ("raw_uploads.csv", "raw_uploads", db._RAW_UPLOAD_DB_KEYS),
    )
    out = {}
    for filename, table, keys_ in specs:
        cols = ", ".join(keys_)
        rows = db._fetch_all(
            f"SELECT {cols} FROM {table} WHERE deleted_at IS NULL ORDER BY {keys_[0]}"
        )
        out[filename] = _rows_to_csv_bytes(keys_, rows)
    return out


def _cmd_publish(args: argparse.Namespace) -> int:
    from app.sot import catalog_schema
    from app.sot.publisher import NotRegisteredError, VersionExistsError, publish_version
    from app.sot.store import GDriveSotStore, LocalSotStore

    if not args.local_store:
        from app.config import settings

        if not str(getattr(settings, "google_drive_root_folder_id", "") or "").strip():
            print(
                "[publish] REFUSED: GOOGLE_DRIVE_ROOT_FOLDER_ID is empty. SOT would be created "
                "in the service account's own My Drive (invisible to the shared folder, and the "
                "container reader would never find it). Set GOOGLE_DRIVE_ROOT_FOLDER_ID first.",
                file=sys.stderr,
            )
            return 2

    store = LocalSotStore(Path(args.local_store)) if args.local_store else GDriveSotStore(read_only=False)

    try:
        version = publish_version(
            store,
            csv_sources=_gather_csv_sources(),
            schema_sql=catalog_schema.export_schema_sql(),
            schema_version=catalog_schema.schema_version(),
            required_columns=catalog_schema.REQUIRED_COLUMNS,
            machine_name=args.name,
            private_key_path=Path(args.key_path) if args.key_path else keys.DEFAULT_PRIVATE_KEY_PATH,
        )
    except NotRegisteredError as exc:
        print(f"[publish] REFUSED: {exc}", file=sys.stderr)
        return 2
    except VersionExistsError as exc:
        print(f"[publish] {exc}", file=sys.stderr)
        return 3

    print(f"[publish] published {version}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    """Dry-run: verify signatures + checksums without touching the DB."""
    from app.sot.reader_sync import (
        CatalogSink, SotSyncRejected, effective_authorized_keys, sync_from_sot,
    )
    from app.sot.store import GDriveSotStore, LocalSotStore

    store = LocalSotStore(Path(args.local_store), read_only=True) if args.local_store else GDriveSotStore(read_only=True)
    noop_sink = CatalogSink(
        apply_schema=lambda _sql: None,
        column_exists=lambda _t, _c: True,  # skip schema-gap check in dry-run
        count_rows=lambda _t: 0,
        upsert_class=lambda _r: None,
        upsert_sample=lambda _r: None,
        upsert_raw_upload=lambda _r: None,
    )
    try:
        result = sync_from_sot(store, noop_sink, authorized_keys=effective_authorized_keys())
    except SotSyncRejected as exc:
        print(f"[verify] INVALID: {exc}", file=sys.stderr)
        return 4
    print(f"[verify] OK version={result.version} signed_by={result.signed_by} "
          f"rows={result.rows_upserted}")
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    from app.config import settings
    from app.sot.reader_sync import SotSyncRejected, run_sync

    # The sot-init container runs this at boot and backend/worker/trainer wait on
    # it with `service_completed_successfully`, so a non-zero exit here keeps the
    # whole application core from ever starting. Seeding the catalog from Drive
    # is a convenience, not a precondition: a machine with no Drive credentials
    # (a fresh clone — gdrive/ is gitignored) must still be able to boot with an
    # empty catalog. Skip cleanly in that case instead of taking the stack down.
    if not settings.use_google_drive:
        print("[sync] skipped: USE_GOOGLE_DRIVE=0 (no SOT source configured)")
        return 0

    try:
        result = run_sync()
    except SotSyncRejected as exc:
        # Ordered first: SotSyncRejected subclasses RuntimeError and would
        # otherwise be swallowed by the catch-all below.
        #
        # This is the ONE failure that must stop the stack. A signature or
        # checksum that does not verify means the source of truth may have been
        # tampered with, and starting workers against it is worse than not
        # starting at all. Fail closed, DB untouched.
        print(f"[sync] REJECTED (DB untouched): {exc}", file=sys.stderr)
        return 4
    except FileNotFoundError as exc:
        # Drive is switched on but this machine was never authorised (no
        # credentials.json / token.json — gdrive/ is gitignored, so this is the
        # normal state of a fresh clone).
        print(f"[sync] skipped: Google Drive not set up on this machine ({exc})", file=sys.stderr)
        return 0
    except Exception as exc:  # noqa: BLE001 — deliberately broad, see below
        # Everything else here is infrastructure: a Drive API 5xx, an expired
        # token, DNS failure, a TLS timeout. None of it says anything about the
        # integrity of the SOT, but every one of them used to exit non-zero —
        # and because backend/worker/trainer gate on
        # `service_completed_successfully`, a momentary Drive outage during a
        # server reboot would leave the entire application down until a human
        # noticed. Seeding the catalog is best-effort; the DB keeps whatever it
        # already had and an admin can re-run the sync from /admin/sot.
        print(
            f"[sync] skipped: could not reach the SOT ({type(exc).__name__}: {exc}). "
            "Startup continues with the existing DB contents.",
            file=sys.stderr,
        )
        return 0
    print(f"[sync] {result.status} version={result.version} signed_by={result.signed_by} "
          f"upserted={result.rows_upserted} extras={result.server_extras}")
    return 0 if result.status in ("applied", "empty") else 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.sot.cli", description="SOT publisher/reader")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_keygen = sub.add_parser("keygen", help="register this machine as a writer")
    p_keygen.add_argument("--name", required=True, help="human label for this machine")
    p_keygen.add_argument("--key-path", default=None, help="override private key path")
    p_keygen.add_argument("--force", action="store_true", help="overwrite existing private key")
    p_keygen.set_defaults(func=_cmd_keygen)

    p_publish = sub.add_parser("publish", help="publish a new SOT version")
    p_publish.add_argument("--name", required=True, help="publishing machine label")
    p_publish.add_argument("--key-path", default=None)
    p_publish.add_argument("--local-store", default=None, help="publish to a local dir instead of Drive")
    p_publish.set_defaults(func=_cmd_publish)

    p_verify = sub.add_parser("verify", help="dry-run verify signatures + checksums")
    p_verify.add_argument("--local-store", default=None, help="verify a local dir instead of Drive")
    p_verify.set_defaults(func=_cmd_verify)

    p_sync = sub.add_parser("sync", help="reader: pull latest, verify, update DB")
    p_sync.set_defaults(func=_cmd_sync)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
