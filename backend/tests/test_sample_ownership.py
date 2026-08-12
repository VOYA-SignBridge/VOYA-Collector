"""Ownership of a sample: who may act on it, and how it survives a CSV trip.

Three defects are pinned here, all found on 2026-08-01 while resolving group E:

  1. Every row imported from another machine's samples.csv reached Postgres with
     auth_user_id NULL, because the CSV had no such column. Its contributor then
     opened Trash and saw nothing.
  2. Bulk trash actions resolved ownership one query per uid, and dropped foreign
     uids without telling the caller — "đã khôi phục 7 mẫu" for a selection of 10.
  3. Adding the column to the CSV writes "" into a UUID column, which would abort
     the whole CSV->Postgres sync on the first legacy row.

None of these need a database: the query layer is stubbed and the CSV work is
real file I/O in tmp_path.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.storage.metadata_db import _uuid_or_none, partition_sample_ownership  # noqa: E402
import app.storage.metadata_db as mdb  # noqa: E402
from app.cli.backfill_sample_owners import _fold, _resolve, AUTO_TIERS  # noqa: E402


ME = "11111111-1111-1111-1111-111111111111"
OTHER = "22222222-2222-2222-2222-222222222222"


# --------------------------------------------------------------------------
# 1. partition_sample_ownership — one query, four buckets
# --------------------------------------------------------------------------

@pytest.fixture
def owners(monkeypatch):
    """Stub get_sample_owners and count how many times it is called."""
    calls = []

    def _fake(uids):
        calls.append(list(uids))
        table = {"a": ME, "b": ME, "c": OTHER, "d": None}
        return {u: table[u] for u in uids if u in table}

    monkeypatch.setattr(mdb, "get_sample_owners", _fake)
    return calls


def test_four_buckets(owners):
    split = partition_sample_ownership(["a", "b", "c", "d", "zz"], ME)
    assert split.owned == ["a", "b"]
    assert split.foreign == ["c"]
    assert split.unowned == ["d"]
    assert split.missing == ["zz"]


def test_single_query_not_n_plus_1(owners):
    partition_sample_ownership(["a", "b", "c", "d"], ME)
    assert len(owners) == 1, "ownership must cost ONE query for the whole batch"


def test_skipped_collects_every_non_owned_bucket(owners):
    split = partition_sample_ownership(["a", "c", "d", "zz"], ME)
    assert split.skipped == ["c", "d", "zz"]
    assert len(split.owned) + len(split.skipped) == 4


def test_unowned_is_not_reported_as_foreign(owners):
    """A legacy row with no auth_user_id belongs to nobody yet — telling its
    contributor it belongs to someone else is the wrong message entirely."""
    split = partition_sample_ownership(["d"], ME)
    assert split.unowned == ["d"] and split.foreign == []


def test_input_order_and_dedup_preserved(owners):
    split = partition_sample_ownership(["b", "a", "b", " a ", ""], ME)
    assert split.owned == ["b", "a"]


def test_empty_input_makes_no_query(owners):
    assert partition_sample_ownership([], ME).owned == []
    assert owners == []


def test_db_failure_refuses_the_whole_batch(monkeypatch):
    """An unreadable owner must never read as 'yours' — during an outage that
    would let one contributor purge another's samples."""
    monkeypatch.setattr(mdb, "get_sample_owners", lambda uids: {})
    split = partition_sample_ownership(["a", "b"], ME)
    assert split.owned == [] and split.missing == ["a", "b"]


# --------------------------------------------------------------------------
# 2. _uuid_or_none — "" from a CSV cell must not reach a UUID column
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["", "   ", None, "Khoa", "not-a-uuid", "1234"])
def test_uuid_or_none_rejects_non_uuid(bad):
    assert _uuid_or_none(bad) is None


def test_uuid_or_none_keeps_a_real_uuid():
    assert _uuid_or_none("  " + ME + " ") == ME


def test_insert_sample_normalises_blank_owner(monkeypatch):
    captured = {}
    monkeypatch.setattr(mdb, "_execute", lambda sql, params: captured.update(params))
    mdb.insert_sample({"sample_uid": "x", "auth_user_id": ""})
    assert captured["auth_user_id"] is None


def test_insert_raw_upload_normalises_blank_owner(monkeypatch):
    captured = {}
    monkeypatch.setattr(mdb, "_execute", lambda sql, params: captured.update(params))
    mdb.insert_raw_upload({"upload_uid": "x", "auth_user_id": "  "})
    assert captured["auth_user_id"] is None


# --------------------------------------------------------------------------
# 3. ensure_samples_column — the CSV migration
# --------------------------------------------------------------------------

@pytest.fixture
def csv_module(tmp_path, monkeypatch):
    import app.dataset_samples as ds

    path = tmp_path / "samples.csv"
    monkeypatch.setattr(ds, "SAMPLES_CSV", path)
    monkeypatch.setattr(ds, "SAMPLES_DIR", tmp_path)
    monkeypatch.setattr(ds, "DATASET_ROOT", tmp_path)
    return ds, path


def _write(path: Path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


def test_column_appended_at_the_end(csv_module):
    ds, path = csv_module
    _write(path, [["sample_uid", "slug"], ["a", "x"], ["b", "y"]])
    assert ds.ensure_samples_column("auth_user_id") is True
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["sample_uid", "slug", "auth_user_id"]
    assert rows[1] == ["a", "x", ""]


def test_migration_is_idempotent(csv_module):
    ds, path = csv_module
    _write(path, [["sample_uid"], ["a"]])
    assert ds.ensure_samples_column("auth_user_id") is True
    assert ds.ensure_samples_column("auth_user_id") is False
    with open(path, newline="", encoding="utf-8") as f:
        assert list(csv.reader(f))[0] == ["sample_uid", "auth_user_id"]


def test_ragged_legacy_row_is_padded_not_shifted(csv_module):
    """A short row must not slide its last cell under the new column."""
    ds, path = csv_module
    _write(path, [["sample_uid", "slug", "dialect"], ["a", "x"], ["b", "y", "bac"]])
    ds.ensure_samples_column("auth_user_id")
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["dialect"] == "" and rows[0]["auth_user_id"] == ""
    assert rows[1]["dialect"] == "bac" and rows[1]["auth_user_id"] == ""


def test_existing_values_survive_migration(csv_module):
    ds, path = csv_module
    _write(path, [["sample_uid", "auth_user_id"], ["a", ME]])
    assert ds.ensure_samples_column("auth_user_id") is False
    with open(path, newline="", encoding="utf-8") as f:
        assert list(csv.DictReader(f))[0]["auth_user_id"] == ME


def test_appended_row_carries_the_owner(csv_module):
    ds, path = csv_module
    _write(path, [list(ds.SAMPLE_FIELDS)])
    ds.append_sample_row({"sample_uid": "a", "auth_user_id": ME})
    with open(path, newline="", encoding="utf-8") as f:
        assert list(csv.DictReader(f))[0]["auth_user_id"] == ME


def test_sample_fields_declares_the_column():
    import app.dataset_samples as ds

    # The invariant is APPEND-ONLY, not "auth_user_id is last forever".
    #
    # The Google Sheets mirror writes the header verbatim as row 1, so a column
    # inserted anywhere but the end shifts every existing Sheets column one
    # place right. What must never change is therefore the POSITION of the
    # columns already there — auth_user_id landing at the end was how that got
    # expressed while it was the newest column.
    #
    # A1 appended tenant_id after it, which obeys the rule. Pinning the index
    # keeps the real guarantee: this fails loudly if anyone inserts a column
    # mid-header, and keeps passing as further columns are appended.
    assert ds.SAMPLE_FIELDS.index("auth_user_id") == 31, (
        "auth_user_id must not MOVE — Sheets writes the header verbatim"
    )
    assert "tenant_id" in ds.SAMPLE_FIELDS[32:]


# --------------------------------------------------------------------------
# 4. Backfill matching — a name is not an identity
# --------------------------------------------------------------------------

USERS = [
    {"id": ME, "username": "Khoa", "email": "khoa@x", "is_admin": False},
    {"id": OTHER, "username": "Trâm", "email": "tram@x", "is_admin": False},
    {"id": "33333333-3333-3333-3333-333333333333", "username": "Trân", "email": "tran@x", "is_admin": False},
    {"id": "44444444-4444-4444-4444-444444444444", "username": "Thungan", "email": "tn@x", "is_admin": False},
]


def _obs(**kw):
    """Build the observed-ownership table: {user_id: {accounts, only_account, n}}."""
    return {k: {"user_key": k, "accounts": v[0], "only_account": v[1], "n": v[2]}
            for k, v in kw.items()}


def test_uuid_in_user_id_resolves_directly():
    """998 rows in the historical dump wrote the account UUID into user_id.
    That is the one case where the column really does name the owner."""
    auth, tier, _ = _resolve(ME, USERS, {})
    assert auth == ME and tier == "uuid" and tier in AUTO_TIERS


def test_unanimous_existing_rows_decide():
    obs = _obs(Khoa=(1, ME, 340))
    auth, tier, note = _resolve("Khoa", USERS, {}, obs)
    assert auth == ME and tier == "observed" and tier in AUTO_TIERS
    assert "340" in note


def test_split_ownership_refuses():
    """Measured on the real database: user_id 'Khoa' is 340 rows owned by the
    Khoa account and 129 owned by Minh. The name decides nothing."""
    obs = _obs(Khoa=(2, ME, 469))
    auth, tier, note = _resolve("Khoa", USERS, {}, obs)
    assert auth is None and tier == "split" and tier not in AUTO_TIERS
    assert "2 tài khoản" in note


def test_namesake_account_is_never_enough():
    """The whole reason this tool exists in this shape: 620 rows with user_id
    'Trân' are owned by the MINH account, even though a Trân account exists.
    Matching the name would have handed them to the wrong person."""
    auth, tier, note = _resolve("Trân", USERS, {})
    assert auth is None and tier == "namesake" and tier not in AUTO_TIERS
    assert "KHÔNG có bằng chứng" in note


def test_namesake_loses_to_observed_evidence():
    """Evidence beats spelling: rows say Minh, the name says Trân."""
    obs = {"Trân": {"accounts": 1, "only_account": ME, "n": 620}}
    auth, tier, _ = _resolve("Trân", USERS, {}, obs)
    assert auth == ME and tier == "observed"


def test_tram_and_tran_never_collapse():
    """One diacritic apart, two different people (owner-confirmed 2026-07-31).
    Neither may be resolved from the other's spelling."""
    assert _fold("Trâm") != _fold("Trân")
    for name in ("Trâm", "Trân", "Tram"):
        auth, tier, _ = _resolve(name, USERS, {})
        assert auth is None, f"{name} must never auto-resolve on spelling alone"


def test_thu_ngan_is_not_merged_into_thungan():
    """Same PERSON, two accounts. Signer merging is a different question from
    ownership: each account owns what it recorded."""
    auth, tier, _ = _resolve("Thu Ngân", USERS, {})
    assert auth is None


def test_override_wins_over_everything():
    obs = _obs()
    obs["Thu Ngân"] = {"accounts": 2, "only_account": ME, "n": 9}
    auth, tier, _ = _resolve("Thu Ngân", USERS, {"Thu Ngân": "Thungan"}, obs)
    assert auth == "44444444-4444-4444-4444-444444444444" and tier == "override"


def test_override_naming_an_unknown_account_is_refused():
    auth, tier, note = _resolve("Khoa", USERS, {"Khoa": "ghost"})
    assert auth is None and "không khớp" in note


def test_blank_user_id_is_unresolvable():
    for key in ("", "   ", "(trống)"):
        auth, tier, _ = _resolve(key, USERS, {})
        assert auth is None and tier == "none"


def test_auto_tiers_are_exactly_the_three_sound_ones():
    """A guard on the guard: adding a fuzzy tier back into AUTO_TIERS would
    silently reintroduce name-based ownership."""
    assert set(AUTO_TIERS) == {"override", "uuid", "observed"}


def test_backfill_only_touches_null_owners(monkeypatch):
    """Rerunning with a wrong mapping must be unable to overwrite a good owner."""
    seen = {}

    class _Cur:
        rowcount = 3

        def execute(self, sql, params):
            seen["sql"] = " ".join(sql.split())
            seen["params"] = params

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(mdb, "_cursor", lambda: _Cur())
    assert mdb.backfill_sample_owner("Khoa", ME) == 3
    assert "auth_user_id IS NULL" in seen["sql"]
    assert seen["params"] == (ME, "Khoa")
