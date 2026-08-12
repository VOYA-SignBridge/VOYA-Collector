"""The legacy `dialects` table, and the foreign keys that enforce the registry.

Two defects pinned here, both found by running init_db against the real dev
database on 2026-08-01:

  1. An older schema shipped `dialects(code PK, language_code FK, name)`, so
     `CREATE TABLE IF NOT EXISTS dialects` did NOTHING and the whole vocabulary
     registry silently never installed — every INSERT failed with
     'column "tenant_id" does not exist'. IF NOT EXISTS failing open is the
     nastiest kind of migration bug: the logs say "ignored" and move on.

  2. The plan on record was `FOREIGN KEY (dialect) REFERENCES dialects(dialect_id)`.
     Postgres rejects that — `dialects` is keyed `(tenant_id, dialect_id)` for
     multitenancy, so a single-column reference has no unique constraint to
     match. The key must be composite.

These are statement-level tests: no database, the SQL is asserted directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.storage.metadata_db as mdb  # noqa: E402


# --------------------------------------------------------------------------
# 1. Dropping the legacy table
# --------------------------------------------------------------------------

def _legacy_stmt() -> str:
    return mdb.DDL_STATEMENTS[0]


def test_legacy_cleanup_runs_before_the_create():
    """Order is the whole point, and it spans two lists: ensure_tables() runs
    DDL_STATEMENTS first, then MIGRATION_STATEMENTS — which is where the
    registry's CREATE actually lives. Moving the drop into MIGRATION_STATEMENTS
    would put it AFTER the CREATE had already no-opped, leaving the machine
    with no dialects table at all until the next start."""
    assert "DROP TABLE dialects" in _legacy_stmt()
    assert not any("DROP TABLE dialects" in s for s in mdb.MIGRATION_STATEMENTS)
    assert any("CREATE TABLE IF NOT EXISTS dialects" in s for s in mdb.MIGRATION_STATEMENTS), \
        "the registry table must still be created"


def test_ensure_tables_applies_ddl_before_migrations():
    """Pins the execution order the test above depends on.

    Đọc `_apply_schema` chứ không phải `ensure_tables`: từ 12/08/2026 thân hàm
    chuyển sang đó, và `ensure_tables()` chỉ còn là một trong hai cửa vào
    (cửa kia là `migrate_database()`). Thứ tự cần ghim vẫn nằm ở thân chung.
    """
    import inspect

    src = inspect.getsource(mdb._apply_schema)
    assert src.index("DDL_STATEMENTS") < src.index("MIGRATION_STATEMENTS")


def test_the_legacy_drop_is_one_way():
    """`DROP TABLE dialects` không được chạy lúc khởi động.

    Nó có canh kỹ và đã chạy đúng — nhưng đó không phải câu hỏi. Câu hỏi là ai
    cho phép nó chạy, và từ 12/08/2026 câu trả lời không còn là "bất kỳ ai gõ
    `docker compose up`".
    """
    assert _legacy_stmt() in mdb.one_way_statements()
    assert _legacy_stmt() not in mdb.startup_safe(mdb.DDL_STATEMENTS)


def test_cleanup_is_guarded_on_the_legacy_shape():
    """It must fire only on the OLD table (has `code`, lacks `dialect_id`), so
    it is a no-op once migrated and can never drop a live registry."""
    s = _legacy_stmt()
    assert "column_name = 'code'" in s
    assert "column_name = 'dialect_id'" in s
    assert "NOT EXISTS" in s, "must refuse to drop a table that already has dialect_id"


def test_registry_table_still_declares_composite_key():
    create = next(s for s in mdb.MIGRATION_STATEMENTS
                  if "CREATE TABLE IF NOT EXISTS dialects" in s)
    assert "PRIMARY KEY (tenant_id, dialect_id)" in create


# --------------------------------------------------------------------------
# 2. The foreign keys
# --------------------------------------------------------------------------

class _Cur:
    def __init__(self, existing=()):
        self.existing = set(existing)
        self.statements = []
        self._last = None

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        self.statements.append(flat)
        if flat.startswith("SELECT 1 FROM pg_constraint"):
            self._last = (1,) if params[0] in self.existing else None

    def fetchone(self):
        return self._last

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _run(monkeypatch, existing=()):
    """Drive the function with BOTH cursors patched.

    Patching both is the point. `ADD CONSTRAINT` is DDL, and since A2 the
    application role is deliberately unable to run DDL — a role that can ALTER a
    table can also disable the row-level security policies on it. So this
    function must go through the migration cursor, and `_app_cursor_used` below
    turns "it used the wrong connection" into a failing test rather than a
    warning line on the deploy machine that nobody reads.
    """
    cur = _Cur(existing)
    app_cursor_used = []

    def _forbidden_app_cursor():
        app_cursor_used.append(True)
        return cur

    monkeypatch.setattr(mdb, "_cursor", _forbidden_app_cursor)
    monkeypatch.setattr(mdb, "_migration_cursor", lambda: cur)
    result = mdb.ensure_vocabulary_foreign_keys()
    assert not app_cursor_used, (
        "ensure_vocabulary_foreign_keys ran DDL through the application cursor; "
        "the app role has no DDL rights, so this would fail on a deployment with "
        "the roles split and leave the foreign keys silently unenforced"
    )
    return cur, result


def test_both_tables_get_a_key(monkeypatch):
    _, result = _run(monkeypatch)
    assert result == {"classes": "added", "samples": "added"}


def test_key_is_composite_not_single_column(monkeypatch):
    """`REFERENCES dialects(dialect_id)` alone is rejected by Postgres:
    'there is no unique constraint matching given keys'."""
    cur, _ = _run(monkeypatch)
    adds = [s for s in cur.statements if "ADD CONSTRAINT" in s]
    assert len(adds) == 2
    for s in adds:
        assert "FOREIGN KEY (tenant_id, dialect)" in s
        assert "REFERENCES dialects(tenant_id, dialect_id)" in s


def test_existing_constraint_is_not_recreated(monkeypatch):
    cur, result = _run(monkeypatch, existing=("classes_dialect_fkey",))
    assert result["classes"] == "exists" and result["samples"] == "added"
    assert not any("ALTER TABLE classes" in s for s in cur.statements)


def test_a_failure_is_reported_not_raised(monkeypatch):
    """A missing constraint weakens enforcement, but raising here would block
    startup — and the likely cause (a row naming an unregistered dialect) is
    exactly when the operator needs the app up to go fix the data."""

    class _Boom:
        def execute(self, sql, params=None):
            raise RuntimeError("violates foreign key constraint\nDETAIL: ...")

        def fetchone(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(mdb, "_migration_cursor", lambda: _Boom())
    result = mdb.ensure_vocabulary_foreign_keys()
    assert set(result) == {"classes", "samples"}
    assert all(v not in ("added", "exists") for v in result.values())


def test_orphan_report_covers_both_tables():
    import inspect

    src = inspect.getsource(mdb.unregistered_dialects_in_use)
    assert "FROM classes" in src and "FROM samples" in src
    assert "d.tenant_id = c.tenant_id" in src, "must compare per tenant, not dialect alone"


# --------------------------------------------------------------------------
# 3. The seed must cover every dialect the FK will police
# --------------------------------------------------------------------------

def test_seed_covers_every_dialect_used_by_the_catalog():
    """If the seed missed a dialect that labels.csv uses, adding the foreign
    key would fail on a real deployment instead of on this assertion."""
    import csv

    repo = Path(__file__).resolve().parents[2]
    seed_path = repo / "config" / "dialects.seed.csv"
    labels_path = repo / "dataset" / "labels.csv"
    if not (seed_path.exists() and labels_path.exists()):
        pytest.skip("seed or labels.csv not present")

    with open(seed_path, newline="", encoding="utf-8-sig") as f:
        seeded = {r["dialect_id"].strip() for r in csv.DictReader(f)}
    with open(labels_path, newline="", encoding="utf-8-sig") as f:
        used = {(r.get("dialect") or "").strip() for r in csv.DictReader(f)}
    used.discard("")

    missing = sorted(used - seeded)
    assert not missing, f"dialect dùng trong labels.csv nhưng thiếu trong seed: {missing}"
