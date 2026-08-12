"""One dialect = one realtime slot, and the database must say which job holds it.

`model_id` for the realtime registry changed from `training_<job_id>` to the
dialect itself, so promoting a new model DELETES the previous job's entry from
models.json. `promoted_at` alone therefore stopped meaning "currently serving":
after two promotions for `hoa-de`, two jobs carried it and only one was live.

`superseded_at` is the answer chosen over clearing `promoted_at`, because "was
promoted at T1, replaced at T2" is an audit fact worth keeping — and a retention
sweep needs to tell a live checkpoint from a retired one.

No database needed: the cursor is stubbed and the SQL is asserted directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.storage.metadata_db as mdb  # noqa: E402


class _FakeCursor:
    """Records every statement; returns `retiring` rows for the first fetchall."""

    def __init__(self, retiring):
        self.statements = []
        self.params = []
        self._retiring = [(j,) for j in retiring]

    def execute(self, sql, params=None):
        self.statements.append(" ".join(sql.split()))
        self.params.append(params)

    def fetchall(self):
        return self._retiring

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def cursor(monkeypatch):
    made = {}

    def _factory(retiring=("job-old",)):
        cur = _FakeCursor(retiring)
        made["cur"] = cur
        monkeypatch.setattr(mdb, "_cursor", lambda: cur)
        return cur

    return _factory


def test_returns_the_ids_it_retired(cursor):
    cursor(["job-a", "job-b"])
    assert mdb.supersede_other_promotions("job-new", "hoa-de") == ["job-a", "job-b"]


def test_never_supersedes_the_job_being_promoted(cursor):
    cur = cursor()
    mdb.supersede_other_promotions("job-new", "hoa-de")
    assert "job_id <> %(job_id)s" in cur.statements[0]
    assert cur.params[0]["job_id"] == "job-new"


def test_scoped_to_one_dialect(cursor):
    cur = cursor()
    mdb.supersede_other_promotions("job-new", "hoa-de")
    sql = cur.statements[0]
    assert "config->'dialects'->>0" in sql, "training_jobs has no dialect column"
    assert "'multi'" in sql, "a job naming no dialect must match the router's default"
    assert cur.params[0]["dialect"] == "hoa-de"


def test_only_touches_jobs_that_were_actually_promoted(cursor):
    cur = cursor()
    mdb.supersede_other_promotions("job-new", "hoa-de")
    sql = cur.statements[0]
    assert "promoted_at IS NOT NULL" in sql
    assert "superseded_at IS NULL" in sql, "already-retired jobs must not be re-stamped"


def test_clears_its_own_marker_on_re_promotion(cursor):
    """Promoting a job that was superseded earlier must un-retire it, or it
    displays as replaced while it is the one actually serving."""
    cur = cursor([])
    mdb.supersede_other_promotions("job-new", "hoa-de")
    assert len(cur.statements) == 2
    assert "SET superseded_at = NULL" in cur.statements[1]
    assert cur.params[1] == ("job-new",)


def test_both_writes_share_one_transaction(cursor):
    """_cursor() commits on exit, so both statements must run inside ONE of
    them — a crash between two separate cursors would leave the dialect with no
    current model at all."""
    calls = []
    cur = _FakeCursor([])

    def _one_shot():
        calls.append(1)
        return cur

    import contextlib

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(mdb, "_cursor", _one_shot)
        mdb.supersede_other_promotions("job-new", "hoa-de")
    assert len(calls) == 1
    assert len(cur.statements) == 2


def test_zero_previous_promotions_is_not_an_error(cursor):
    cursor([])
    assert mdb.supersede_other_promotions("job-new", "brand-new-dialect") == []


# --------------------------------------------------------------------------
# Schema + model surface
# --------------------------------------------------------------------------

def test_column_is_added_idempotently():
    """Both paths must carry it: a fresh database (CREATE TABLE) and an
    already-deployed one (ALTER ... IF NOT EXISTS)."""
    assert "superseded_at TIMESTAMP WITH TIME ZONE" in " ".join(mdb.DDL_STATEMENTS)
    assert "ADD COLUMN IF NOT EXISTS superseded_at" in " ".join(mdb.MIGRATION_STATEMENTS)


def test_upsert_never_writes_superseded_at():
    """Only supersede_other_promotions owns this column. If the generic job
    upsert wrote it too, a routine status update would resurrect a retired
    job's flag from a stale in-memory copy."""
    assert "superseded_at" not in mdb.SQL_UPSERT_TRAINING_JOB


def test_history_query_exposes_the_column():
    import inspect

    src = inspect.getsource(mdb.list_training_jobs_with_user)
    assert "t.superseded_at" in src, "the history UI cannot show 'đang phục vụ' without it"


def test_job_model_carries_the_field():
    from app.routers.training import TrainingJob, TrainingConfig

    job = TrainingJob(id="j", status="completed", config=TrainingConfig(), created_at="now")
    assert job.superseded_at is None


def test_job_from_db_row_reads_the_column():
    from app.routers.training import _job_from_db_row

    job = _job_from_db_row({
        "job_id": "j", "status": "completed", "config": {},
        "created_at": "2026-08-01T00:00:00", "promoted_at": "2026-08-01T01:00:00",
        "superseded_at": "2026-08-01T02:00:00",
    })
    assert job.promoted_at is not None and job.superseded_at is not None


def test_serving_is_promoted_and_not_superseded():
    """The rule the UI applies, pinned so it cannot drift back to promoted_at alone."""
    from app.routers.training import _job_from_db_row

    def serving(row):
        j = _job_from_db_row(row)
        return j.promoted_at is not None and j.superseded_at is None

    base = {"job_id": "j", "status": "completed", "config": {}, "created_at": "2026-08-01T00:00:00"}
    assert serving({**base, "promoted_at": "T1", "superseded_at": None}) is True
    assert serving({**base, "promoted_at": "T1", "superseded_at": "T2"}) is False
    assert serving({**base, "promoted_at": None, "superseded_at": None}) is False
