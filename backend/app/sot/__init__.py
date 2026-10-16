"""SOT (Source of Truth) — versioned catalog + schema published to Google Drive.

A registered machine (holding an Ed25519 private key) PUBLISHES immutable
versions of the catalog CSVs + DB schema to a `SOT/` folder on Drive. Servers
and VPS are READ-ONLY: on deploy, before any worker runs, they pull the latest
version, VERIFY its signature against the committed authorized public keys,
then ensure their own DB is a SUPERSET of it (add what's missing, never delete).

See individual modules:
    keys.py        — Ed25519 keygen / sign / verify + authorized-key registry
    manifest.py    — checksums, manifest build/validate, version naming
    store.py       — SotStore abstraction (Drive in prod, filesystem in tests)
    publisher.py   — writer path (guarded: registered machines only)
    reader_sync.py — reader path (verify + schema + superset data sync)
    cli.py         — `keygen` / `publish` / `verify` / `sync`
"""

# Bump when the catalog DB schema changes in a way readers must guarantee.
SOT_SCHEMA_VERSION = 8
