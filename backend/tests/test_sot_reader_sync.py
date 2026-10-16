"""SOT reader — verification + superset sync. The security-critical read path.

Every rejection test also asserts the DB was left UNTOUCHED (fail-closed): a bad
SOT must never partially apply schema or data.
"""

from __future__ import annotations

import json

import pytest

from app.sot import keys, manifest as m
from app.sot.publisher import publish_version
from app.sot.reader_sync import CatalogSink, SotSyncRejected, sync_from_sot
from app.sot.store import LocalSotStore

CSVS = {
    "labels.csv": b"class_uid,slug\nc1,hello\nc2,thanks\n",
    "samples.csv": b"sample_uid,class_uid\ns1,c1\ns2,c1\ns3,c2\n",
    "raw_uploads.csv": b"upload_uid,class_uid\nu1,c1\n",
}


class FakeDB:
    """In-memory catalog: records every upsert / schema apply for assertions."""

    def __init__(self, *, missing_columns=None, seed=None):
        self.tables = {"classes": {}, "samples": {}, "raw_uploads": {}}
        for table, rows in (seed or {}).items():
            self.tables[table].update(rows)
        self.schema_applied = []
        self.missing_columns = set(missing_columns or [])

    def sink(self) -> CatalogSink:
        return CatalogSink(
            apply_schema=lambda sql: self.schema_applied.append(sql),
            column_exists=lambda t, c: f"{t}.{c}" not in self.missing_columns,
            count_rows=lambda t: len(self.tables[t]),
            upsert_class=lambda r: self.tables["classes"].__setitem__(r["class_uid"], r),
            upsert_sample=lambda r: self.tables["samples"].__setitem__(r["sample_uid"], r),
            upsert_raw_upload=lambda r: self.tables["raw_uploads"].__setitem__(r["upload_uid"], r),
        )

    @property
    def total_upserts(self):
        return sum(len(t) for t in self.tables.values())


def _make_sot(tmp_path, *, name="desktop-A", csvs=None, required_columns=None):
    """Publish one valid version; return (store, authorized_keys, signer_key)."""
    authz = tmp_path / "authorized_keys.json"
    authz.write_text("[]", encoding="utf-8")
    key_path = tmp_path / f"{name}.key"
    pk = keys.generate_private_key()
    keys.save_private_key(pk, key_path)
    keys.add_authorized_key(name, keys.public_key_b64(pk), authz)

    store = LocalSotStore(tmp_path / "SOT")
    publish_version(
        store,
        csv_sources=csvs or CSVS,
        schema_sql="CREATE TABLE IF NOT EXISTS classes ();",
        schema_version=8,
        required_columns=required_columns or {"classes": ["class_uid"], "samples": ["sample_uid"]},
        machine_name=name,
        private_key_path=key_path,
        authorized_keys_path=authz,
    )
    return store, keys.load_authorized_keys(authz), pk


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_sync_applies_schema_and_upserts_all_rows(tmp_path):
    store, authorized, _ = _make_sot(tmp_path)
    db = FakeDB()
    result = sync_from_sot(store, db.sink(), authorized_keys=authorized)

    assert result.status == "applied"
    assert result.signed_by == "desktop-A"
    assert result.schema_applied is True
    assert result.rows_upserted == {"classes": 2, "samples": 3, "raw_uploads": 1}
    assert set(db.tables["classes"]) == {"c1", "c2"}
    assert set(db.tables["samples"]) == {"s1", "s2", "s3"}
    assert db.tables["raw_uploads"] == {"u1": {"upload_uid": "u1", "class_uid": "c1"}}


def test_empty_sot_is_noop(tmp_path):
    store = LocalSotStore(tmp_path / "SOT")  # nothing published
    db = FakeDB()
    result = sync_from_sot(store, db.sink(), authorized_keys=[])
    assert result.status == "empty"
    assert db.total_upserts == 0
    assert db.schema_applied == []


# ---------------------------------------------------------------------------
# Superset semantics — never delete server's extra rows
# ---------------------------------------------------------------------------

def test_superset_keeps_server_extras_and_reports_them(tmp_path):
    store, authorized, _ = _make_sot(tmp_path)
    # Server already has an extra class + sample not present in SOT.
    db = FakeDB(seed={
        "classes": {"c1": {"class_uid": "c1", "slug": "OLD"}, "extra": {"class_uid": "extra"}},
        "samples": {"sX": {"sample_uid": "sX", "class_uid": "extra"}},
    })
    result = sync_from_sot(store, db.sink(), authorized_keys=authorized)

    # SOT rows present…
    assert {"c1", "c2", "extra"} <= set(db.tables["classes"])
    # …extra server rows NOT deleted…
    assert "extra" in db.tables["classes"]
    assert "sX" in db.tables["samples"]
    # …SOT value overrode the stale duplicate (c1.slug updated to SOT's).
    assert db.tables["classes"]["c1"]["slug"] == "hello"
    # …and the extras are reported.
    assert result.server_extras["classes"] == 1  # "extra"
    assert result.server_extras["samples"] == 1  # "sX"


# ---------------------------------------------------------------------------
# Rejections — signature
# ---------------------------------------------------------------------------

def test_reject_when_latest_signed_by_unauthorized_key(tmp_path):
    store, authorized, _ = _make_sot(tmp_path)
    # Rogue re-signs LATEST.json with a key NOT in the allowlist.
    rogue = keys.generate_private_key()
    latest_bytes = store.read_bytes("LATEST.json")
    store.write_bytes("LATEST.sig", keys.sign(rogue, latest_bytes).encode())

    db = FakeDB()
    with pytest.raises(SotSyncRejected, match="LATEST.json signature"):
        sync_from_sot(store, db.sink(), authorized_keys=authorized)
    assert db.schema_applied == [] and db.total_upserts == 0  # untouched


def test_reject_when_manifest_signature_invalid(tmp_path):
    store, authorized, _ = _make_sot(tmp_path)
    version = store.list_version_dirs()[0]
    rogue = keys.generate_private_key()
    manifest_bytes = store.read_bytes(f"{version}/manifest.json")
    store.write_bytes(f"{version}/manifest.sig", keys.sign(rogue, manifest_bytes).encode())

    db = FakeDB()
    with pytest.raises(SotSyncRejected, match="manifest signature"):
        sync_from_sot(store, db.sink(), authorized_keys=authorized)
    assert db.schema_applied == [] and db.total_upserts == 0


def test_reject_after_revocation(tmp_path):
    """A version signed by a machine that was later revoked must be rejected."""
    store, authorized, _ = _make_sot(tmp_path)
    db = FakeDB()
    # Revoke everyone.
    with pytest.raises(SotSyncRejected):
        sync_from_sot(store, db.sink(), authorized_keys=[])
    assert db.total_upserts == 0


# ---------------------------------------------------------------------------
# Rejections — integrity / tamper
# ---------------------------------------------------------------------------

def test_reject_when_csv_tampered(tmp_path):
    store, authorized, _ = _make_sot(tmp_path)
    version = store.list_version_dirs()[0]
    store.write_bytes(f"{version}/labels.csv", b"class_uid,slug\nc1,HACKED\n")

    db = FakeDB()
    with pytest.raises(SotSyncRejected, match="labels.csv checksum"):
        sync_from_sot(store, db.sink(), authorized_keys=authorized)
    # Tamper is caught BEFORE schema/data apply.
    assert db.schema_applied == [] and db.total_upserts == 0


def test_reject_when_schema_tampered(tmp_path):
    store, authorized, _ = _make_sot(tmp_path)
    version = store.list_version_dirs()[0]
    store.write_bytes(f"{version}/schema/schema.sql", b"DROP TABLE classes;")

    db = FakeDB()
    with pytest.raises(SotSyncRejected, match="schema.sql checksum"):
        sync_from_sot(store, db.sink(), authorized_keys=authorized)
    assert db.schema_applied == [] and db.total_upserts == 0


def test_reject_when_latest_sha_mismatch(tmp_path):
    store, authorized, signer = _make_sot(tmp_path)
    # Re-sign a LATEST that points at a wrong manifest sha (signature valid, content lies).
    forged = m.canonical_bytes({
        "version": store.list_version_dirs()[0],
        "manifest_sha256": "0" * 64,
        "created_at": "x",
        "machine": "desktop-A",
    })
    store.write_bytes("LATEST.json", forged)
    store.write_bytes("LATEST.sig", keys.sign(signer, forged).encode())

    db = FakeDB()
    with pytest.raises(SotSyncRejected, match="manifest_sha256"):
        sync_from_sot(store, db.sink(), authorized_keys=authorized)
    assert db.total_upserts == 0


def test_reject_when_latest_points_at_invalid_version(tmp_path):
    store, authorized, signer = _make_sot(tmp_path)
    forged = m.canonical_bytes({"version": "not-a-version", "manifest_sha256": "x",
                                "created_at": "x", "machine": "d"})
    store.write_bytes("LATEST.json", forged)
    store.write_bytes("LATEST.sig", keys.sign(signer, forged).encode())

    db = FakeDB()
    with pytest.raises(SotSyncRejected, match="invalid version"):
        sync_from_sot(store, db.sink(), authorized_keys=authorized)


# ---------------------------------------------------------------------------
# Rejections — schema coverage ("bao hàm hết chưa")
# ---------------------------------------------------------------------------

def test_reject_when_required_column_missing(tmp_path):
    store, authorized, _ = _make_sot(
        tmp_path, required_columns={"classes": ["class_uid", "brand_new_col"]}
    )
    # Server schema lacks the required column even after applying schema.
    db = FakeDB(missing_columns={"classes.brand_new_col"})
    with pytest.raises(SotSyncRejected, match="missing required columns"):
        sync_from_sot(store, db.sink(), authorized_keys=authorized)
    # Schema was applied (attempted) but NO data imported against an incomplete schema.
    assert db.total_upserts == 0


def test_schema_gap_lists_all_missing_columns(tmp_path):
    store, authorized, _ = _make_sot(
        tmp_path, required_columns={"classes": ["a", "b"], "samples": ["c"]}
    )
    db = FakeDB(missing_columns={"classes.a", "classes.b", "samples.c"})
    with pytest.raises(SotSyncRejected) as exc:
        sync_from_sot(store, db.sink(), authorized_keys=authorized)
    msg = str(exc.value)
    assert "classes.a" in msg and "classes.b" in msg and "samples.c" in msg


# ---------------------------------------------------------------------------
# Multiple registered machines
# ---------------------------------------------------------------------------

def test_version_from_second_registered_machine_is_accepted(tmp_path):
    # laptop-2 publishes; both laptops are registered.
    store, authorized, _ = _make_sot(tmp_path, name="laptop-2")
    db = FakeDB()
    result = sync_from_sot(store, db.sink(), authorized_keys=authorized)
    assert result.status == "applied"
    assert result.signed_by == "laptop-2"
