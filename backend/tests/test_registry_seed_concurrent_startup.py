"""Every gunicorn worker seeds the vocabulary registry at startup, concurrently.

Measured on production 16/10/2026: of 2-4 workers starting together, some log
`[DB_INIT] vocabulary registry seed skipped: new row violates row-level security
policy for table "dialects" / "registry_versions"`. This reproduces the startup
shape — N fresh processes calling `seed_from_csv()` at the same moment.
"""
from __future__ import annotations

import multiprocessing as mp
import traceback


def _seed(barrier, results):
    try:
        from app.modules.dataset.vocabulary_registry import seed_from_csv

        barrier.wait(timeout=60)
        seed_from_csv()
        results.put(("ok", ""))
    except Exception:  # noqa: BLE001 - the failure under test
        results.put(("error", traceback.format_exc(limit=8)))


def _init(barrier, results):
    try:
        from app.bootstrap.database import init_db

        barrier.wait(timeout=120)
        ok = init_db()
        results.put(("ok" if ok else "init_db returned False", ""))
    except Exception:  # noqa: BLE001
        results.put(("error", traceback.format_exc(limit=8)))


def _registry_state():
    from app.storage import metadata_db as db
    from app.modules.saas.tenant_context import system_scope

    with system_scope("test: doc registry"):
        rows = db._fetch_all(
            "SELECT version, content_hash, jsonb_array_length(snapshot->'dialects') AS n "
            "FROM registry_versions WHERE tenant_id = 'default' ORDER BY version")
    return [dict(r) for r in rows]


def test_concurrent_full_startup_does_not_mint_versions_or_empty_snapshots():
    """Same content must not become new versions on every restart, and no worker
    may ever freeze an EMPTY dialect list (= read under no tenant scope)."""
    from app.bootstrap.database import init_db

    assert init_db()  # Settle once: content now current.
    before = _registry_state()

    ctx = mp.get_context("spawn")
    workers = 4
    for _round in range(3):  # Three simultaneous "restarts" in a row.
        barrier, results = ctx.Barrier(workers), ctx.Queue()
        procs = [ctx.Process(target=_init, args=(barrier, results)) for _ in range(workers)]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=300)
        outcomes = [results.get(timeout=5) for _ in procs]
        assert [s for s, _ in outcomes] == ["ok"] * workers, outcomes

    new = _registry_state()[len(before):]
    # signdb_test still holds empty versions frozen by the bug before the fix;
    # only what THIS run created is under test.
    assert not [r for r in new if r["n"] == 0], f"empty snapshot frozen: {new}"
    assert new == [], f"restarts with unchanged content minted versions: {new}"


def test_concurrent_worker_startup_seed_never_violates_rls():
    ctx = mp.get_context("spawn")  # Fresh interpreters, like gunicorn workers.
    workers = 4
    barrier, results = ctx.Barrier(workers), ctx.Queue()
    procs = [ctx.Process(target=_seed, args=(barrier, results)) for _ in range(workers)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=180)
    outcomes = [results.get(timeout=5) for _ in procs]
    errors = [detail for status, detail in outcomes if status != "ok"]
    assert not errors, "\n\n".join(errors)
