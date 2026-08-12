"""CSV -> Postgres sync must compare KEY SETS, never row counts.

The old gate was `if db_count < csv_count: sync`. Postgres keeps soft-deleted
rows while the CSV holds active rows only, so after any deletion db_count stays
>= csv_count forever, the branch is never taken again, and new CSV rows are
never synced. Every scenario below is a case where counting says "nothing to
do" and the answer is wrong.

No database needed: `_existing_keys` is the only thing that touches Postgres.
"""

from __future__ import annotations

import pytest

from app import db as app_db


def _row(uid: str, **extra):
    return {"sample_uid": uid, **extra}


def _run(csv_rows, in_db, *, full=False, monkeypatch=None):
    """Call _sync_one_table with a stubbed DB, return (written_rows, only_in_db)."""
    written: list = []
    monkeypatch.setattr(app_db, "_existing_keys", lambda table, key: set(in_db))
    _, only_in_db = app_db._sync_one_table(
        label="samples",
        table="samples",
        key_column="sample_uid",
        csv_rows=csv_rows,
        upsert=written.append,
        full=full,
    )
    return written, only_in_db


def test_syncs_new_row_even_when_db_has_more_rows(monkeypatch):
    """The exact production case: 2 soft-deleted rows in DB, 1 new row in CSV.

    db_count (3) >= csv_count (2), so the old count gate skipped the table and
    'aaa' was never inserted.
    """
    csv_rows = [_row("keep1"), _row("aaa")]
    in_db = {"keep1", "deleted1", "deleted2"}

    written, only_in_db = _run(csv_rows, in_db, monkeypatch=monkeypatch)

    assert [r["sample_uid"] for r in written] == ["aaa"]
    assert only_in_db == 2


def test_syncs_when_counts_are_equal_but_sets_differ(monkeypatch):
    csv_rows = [_row("a"), _row("b")]
    in_db = {"a", "c"}

    written, only_in_db = _run(csv_rows, in_db, monkeypatch=monkeypatch)

    assert [r["sample_uid"] for r in written] == ["b"]
    assert only_in_db == 1


def test_writes_nothing_when_db_already_has_every_key(monkeypatch):
    csv_rows = [_row("a"), _row("b")]

    written, only_in_db = _run(csv_rows, {"a", "b"}, monkeypatch=monkeypatch)

    assert written == []
    assert only_in_db == 0


def test_full_resync_rewrites_existing_rows(monkeypatch):
    """Edits are invisible to a key diff — CSVs carry no updated_at."""
    csv_rows = [_row("a", slug="doi-ten"), _row("b")]

    written, _ = _run(csv_rows, {"a", "b"}, full=True, monkeypatch=monkeypatch)

    assert [r["sample_uid"] for r in written] == ["a", "b"]


def test_rows_without_a_key_are_skipped_not_crashed(monkeypatch):
    csv_rows = [_row(""), _row("  "), _row("a")]

    written, _ = _run(csv_rows, set(), monkeypatch=monkeypatch)

    assert [r["sample_uid"] for r in written] == ["a"]


def test_duplicate_keys_in_csv_are_written_once(monkeypatch):
    csv_rows = [_row("a", slug="cu"), _row("a", slug="moi")]

    written, _ = _run(csv_rows, set(), monkeypatch=monkeypatch)

    assert len(written) == 1
    assert written[0]["slug"] == "moi"  # dòng sau thắng, khớp cách CSV được đọc


def test_empty_csv_touches_nothing(monkeypatch):
    written, only_in_db = _run([], {"a", "b"}, monkeypatch=monkeypatch)

    assert written == []
    assert only_in_db == 0


@pytest.mark.parametrize("flag,expected", [
    ("1", True), ("true", True), ("YES", True), ("on", True),
    ("0", False), ("", False), ("no", False),
])
def test_full_resync_env_flag(flag, expected, monkeypatch):
    """VOYA_DB_FULL_RESYNC lets an operator force a full push without a rebuild."""
    monkeypatch.setenv("VOYA_DB_FULL_RESYNC", flag)
    seen: dict = {}

    monkeypatch.setattr(app_db, "_sync_one_table",
                        lambda **kw: (seen.update(full=kw["full"]), (0, 0))[1])
    monkeypatch.setattr("app.dataset_manager.load_labels", lambda: [])
    monkeypatch.setattr("app.dataset_samples.list_samples", lambda: [])
    monkeypatch.setattr("app.raw_uploads.list_raw_uploads", lambda: [])

    assert app_db.sync_missing_data_on_startup() is True
    assert seen["full"] is expected
