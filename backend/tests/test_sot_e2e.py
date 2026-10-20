"""SOT end-to-end: publish -> sync round trips through a LocalSotStore, exactly
as desktop(writer) -> server(reader) would, minus the Drive transport."""

from __future__ import annotations

import pytest

from app.sot import keys
from app.sot.publisher import NotRegisteredError, publish_version
from app.sot.reader_sync import CatalogSink, sync_from_sot
from app.sot.store import LocalSotStore

SCHEMA = "CREATE TABLE IF NOT EXISTS classes ();"
REQUIRED = {"classes": ["class_uid"], "samples": ["sample_uid"], "raw_uploads": ["upload_uid"]}


class FakeDB:
    def __init__(self):
        self.tables = {"classes": {}, "samples": {}, "raw_uploads": {}}

    def sink(self):
        return CatalogSink(
            apply_schema=lambda sql: None,
            column_exists=lambda t, c: True,
            count_rows=lambda t: len(self.tables[t]),
            upsert_class=lambda r: self.tables["classes"].__setitem__(r["class_uid"], r),
            upsert_sample=lambda r: self.tables["samples"].__setitem__(r["sample_uid"], r),
            upsert_raw_upload=lambda r: self.tables["raw_uploads"].__setitem__(r["upload_uid"], r),
        )


def _new_registered_machine(authz, name):
    pk = keys.generate_private_key()
    keys.add_authorized_key(name, keys.public_key_b64(pk), authz)
    return pk


def _publish(store, authz, key_path, name, csvs):
    return publish_version(
        store, csv_sources=csvs, schema_sql=SCHEMA, schema_version=8,
        required_columns=REQUIRED, machine_name=name,
        private_key_path=key_path, authorized_keys_path=authz,
    )


def test_publish_then_sync_round_trip(tmp_path):
    authz = tmp_path / "authorized_keys.json"
    authz.write_text("[]", encoding="utf-8")
    key_path = tmp_path / "desktop.key"
    pk = keys.generate_private_key()
    keys.save_private_key(pk, key_path)
    keys.add_authorized_key("desktop-A", keys.public_key_b64(pk), authz)

    store = LocalSotStore(tmp_path / "SOT")
    _publish(store, authz, key_path, "desktop-A", {
        "labels.csv": b"class_uid,slug,label_original\nc1,hello,Xin chao\nc2,thanks,Cam on\n",
        "samples.csv": b"sample_uid,class_uid\ns1,c1\n",
        "raw_uploads.csv": b"upload_uid,class_uid\n",
    })

    db = FakeDB()
    result = sync_from_sot(store, db.sink(), authorized_keys=keys.load_authorized_keys(authz))
    assert result.status == "applied"
    assert db.tables["classes"]["c2"]["label_original"] == "Cam on"
    assert set(db.tables["classes"]) == {"c1", "c2"}


def test_latest_version_wins(tmp_path):
    authz = tmp_path / "authorized_keys.json"
    authz.write_text("[]", encoding="utf-8")
    key_path = tmp_path / "desktop.key"
    pk = keys.generate_private_key()
    keys.save_private_key(pk, key_path)
    keys.add_authorized_key("desktop-A", keys.public_key_b64(pk), authz)
    store = LocalSotStore(tmp_path / "SOT")

    _publish(store, authz, key_path, "desktop-A", {
        "labels.csv": b"class_uid,slug\nc1,a\nc2,b\n",
        "samples.csv": b"sample_uid,class_uid\n", "raw_uploads.csv": b"upload_uid\n",
    })
    # v2 is the FULL updated snapshot (publisher always snapshots the whole catalog).
    v2 = _publish(store, authz, key_path, "desktop-A", {
        "labels.csv": b"class_uid,slug\nc1,a\nc2,b\nc3,c\n",
        "samples.csv": b"sample_uid,class_uid\n", "raw_uploads.csv": b"upload_uid\n",
    })

    db = FakeDB()
    result = sync_from_sot(store, db.sink(), authorized_keys=keys.load_authorized_keys(authz))
    assert result.version == v2
    assert set(db.tables["classes"]) == {"c1", "c2", "c3"}  # picked up v2's new class


def test_second_machine_registration_flow(tmp_path):
    """Before registering laptop-2 it cannot publish; after, it can and the
    version verifies against the (updated) allowlist."""
    authz = tmp_path / "authorized_keys.json"
    authz.write_text("[]", encoding="utf-8")
    store = LocalSotStore(tmp_path / "SOT")

    # laptop-2 has a key but is NOT registered yet.
    laptop2 = keys.generate_private_key()
    key_path = tmp_path / "laptop2.key"
    keys.save_private_key(laptop2, key_path)

    csvs = {"labels.csv": b"class_uid,slug\nc1,a\n",
            "samples.csv": b"sample_uid\n", "raw_uploads.csv": b"upload_uid\n"}

    with pytest.raises(NotRegisteredError):
        _publish(store, authz, key_path, "laptop-2", csvs)

    # Register laptop-2 (add its public key), then it can publish.
    keys.add_authorized_key("laptop-2", keys.public_key_b64(laptop2), authz)
    version = _publish(store, authz, key_path, "laptop-2", csvs)

    db = FakeDB()
    result = sync_from_sot(store, db.sink(), authorized_keys=keys.load_authorized_keys(authz))
    assert result.status == "applied"
    assert result.version == version
    assert result.signed_by == "laptop-2"


def test_export_schema_sql_is_idempotent_ddl(tmp_path):
    """The publisher's schema snapshot is real, idempotent DDL."""
    from app.sot.catalog_schema import REQUIRED_COLUMNS, export_schema_sql, schema_version

    sql = export_schema_sql()
    assert "CREATE TABLE IF NOT EXISTS classes" in sql
    assert "CREATE TABLE IF NOT EXISTS samples" in sql
    assert "raw_uploads" in sql
    assert isinstance(schema_version(), int)
    # Required columns cover the primary keys of every catalog table.
    assert "class_uid" in REQUIRED_COLUMNS["classes"]
    assert "sample_uid" in REQUIRED_COLUMNS["samples"]
    assert "upload_uid" in REQUIRED_COLUMNS["raw_uploads"]
    assert "deleted_at" in REQUIRED_COLUMNS["classes"]  # soft-delete column guaranteed
