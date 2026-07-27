"""SOT publisher — the WRITER path and its "registered machines only" guard."""

from __future__ import annotations

from datetime import date

import pytest

from app.sot import keys, manifest as m
from app.sot.publisher import (
    NotRegisteredError,
    VersionExistsError,
    publish_version,
)
from app.sot.store import LocalSotStore

CSVS = {
    "labels.csv": b"class_uid,slug\nc1,hello\nc2,thanks\n",
    "samples.csv": b"sample_uid,class_uid\ns1,c1\ns2,c1\ns3,c2\n",
    "raw_uploads.csv": b"upload_uid,class_uid\n",
}


def _register(tmp_path, name="desktop-A"):
    """Create a registered writer: private key + entry in authorized_keys.json."""
    authz = tmp_path / "authorized_keys.json"
    authz.write_text("[]", encoding="utf-8")
    key_path = tmp_path / f"{name}.key"
    pk = keys.generate_private_key()
    keys.save_private_key(pk, key_path)
    keys.add_authorized_key(name, keys.public_key_b64(pk), authz)
    return key_path, authz


def _publish(store, tmp_path, *, name="desktop-A", key_path=None, authz=None, today=None, csvs=None):
    return publish_version(
        store,
        csv_sources=csvs or CSVS,
        schema_sql="CREATE TABLE IF NOT EXISTS classes ();",
        schema_version=8,
        required_columns={"classes": ["class_uid"]},
        machine_name=name,
        private_key_path=key_path,
        authorized_keys_path=authz,
        today=today,
    )


def test_publish_happy_path_writes_all_files(tmp_path):
    key_path, authz = _register(tmp_path)
    store = LocalSotStore(tmp_path / "SOT")
    version = _publish(store, tmp_path, key_path=key_path, authz=authz, today=date(2026, 7, 18))

    assert version == "Ver1_18072026"
    for name in ("labels.csv", "samples.csv", "raw_uploads.csv", "schema/schema.sql",
                 "schema/schema_version.txt", "manifest.json", "manifest.sig"):
        assert store.exists(f"{version}/{name}"), name
    assert store.exists("LATEST.json")
    assert store.exists("LATEST.sig")


def test_published_manifest_is_correctly_signed(tmp_path):
    key_path, authz = _register(tmp_path)
    store = LocalSotStore(tmp_path / "SOT")
    version = _publish(store, tmp_path, key_path=key_path, authz=authz)

    manifest_bytes = store.read_bytes(f"{version}/manifest.json")
    sig = store.read_bytes(f"{version}/manifest.sig").decode()
    authorized = keys.load_authorized_keys(authz)
    assert keys.verify_with_authorized(manifest_bytes, sig, authorized) == "desktop-A"


def test_manifest_records_counts_and_hashes(tmp_path):
    import json

    key_path, authz = _register(tmp_path)
    store = LocalSotStore(tmp_path / "SOT")
    version = _publish(store, tmp_path, key_path=key_path, authz=authz)

    manifest = json.loads(store.read_bytes(f"{version}/manifest.json"))
    assert manifest["row_counts"]["labels.csv"] == 2   # 2 data rows
    assert manifest["row_counts"]["samples.csv"] == 3
    assert manifest["row_counts"]["raw_uploads.csv"] == 0
    assert manifest["files"]["labels.csv"] == m.sha256_bytes(CSVS["labels.csv"])


def test_latest_points_at_published_manifest(tmp_path):
    import json

    key_path, authz = _register(tmp_path)
    store = LocalSotStore(tmp_path / "SOT")
    version = _publish(store, tmp_path, key_path=key_path, authz=authz)

    latest = json.loads(store.read_bytes("LATEST.json"))
    manifest_bytes = store.read_bytes(f"{version}/manifest.json")
    assert latest["version"] == version
    assert latest["manifest_sha256"] == m.sha256_bytes(manifest_bytes)


# ---------------------------------------------------------------------------
# Guard: registered machines only
# ---------------------------------------------------------------------------

def test_publish_refused_without_private_key(tmp_path):
    authz = tmp_path / "authorized_keys.json"
    authz.write_text("[]", encoding="utf-8")
    store = LocalSotStore(tmp_path / "SOT")
    with pytest.raises(NotRegisteredError):
        _publish(store, tmp_path, key_path=tmp_path / "does-not-exist.key", authz=authz)


def test_publish_refused_when_key_not_in_allowlist(tmp_path):
    # Key exists on the machine, but was never registered (allowlist empty).
    authz = tmp_path / "authorized_keys.json"
    authz.write_text("[]", encoding="utf-8")
    key_path = tmp_path / "rogue.key"
    keys.save_private_key(keys.generate_private_key(), key_path)
    store = LocalSotStore(tmp_path / "SOT")
    with pytest.raises(NotRegisteredError, match="not in authorized_keys"):
        _publish(store, tmp_path, key_path=key_path, authz=authz)


def test_publish_refused_when_only_other_machine_registered(tmp_path):
    # authorized_keys has laptop-1, but we publish with laptop-2's (unregistered) key.
    authz = tmp_path / "authorized_keys.json"
    authz.write_text("[]", encoding="utf-8")
    keys.add_authorized_key("laptop-1", keys.public_key_b64(keys.generate_private_key()), authz)
    key_path = tmp_path / "laptop-2.key"
    keys.save_private_key(keys.generate_private_key(), key_path)
    store = LocalSotStore(tmp_path / "SOT")
    with pytest.raises(NotRegisteredError):
        _publish(store, tmp_path, name="laptop-2", key_path=key_path, authz=authz)


# ---------------------------------------------------------------------------
# Immutability + numbering
# ---------------------------------------------------------------------------

def test_version_numbers_increment_across_publishes(tmp_path):
    key_path, authz = _register(tmp_path)
    store = LocalSotStore(tmp_path / "SOT")
    v1 = _publish(store, tmp_path, key_path=key_path, authz=authz, today=date(2026, 7, 18))
    v2 = _publish(store, tmp_path, key_path=key_path, authz=authz, today=date(2026, 7, 20))
    v3 = _publish(store, tmp_path, key_path=key_path, authz=authz, today=date(2026, 7, 20))
    assert (v1, v2, v3) == ("Ver1_18072026", "Ver2_20072026", "Ver3_20072026")
    assert store.list_version_dirs() == ["Ver1_18072026", "Ver2_20072026", "Ver3_20072026"]


def test_publish_refuses_to_overwrite_existing_version(tmp_path, monkeypatch):
    # Normal numbering is always max+1 so it never collides; the immutability
    # guard is the safety net for a concurrent-publisher race where two machines
    # compute the SAME next version. Force that collision by pinning the computed
    # name to one whose manifest already exists.
    key_path, authz = _register(tmp_path)
    store = LocalSotStore(tmp_path / "SOT")
    store.write_bytes("Ver1_18072026/manifest.json", b"{}")
    monkeypatch.setattr("app.sot.publisher.m.next_version_name", lambda *a, **k: "Ver1_18072026")
    with pytest.raises(VersionExistsError):
        _publish(store, tmp_path, key_path=key_path, authz=authz, today=date(2026, 7, 18))


def test_publish_rejects_missing_required_csv(tmp_path):
    key_path, authz = _register(tmp_path)
    store = LocalSotStore(tmp_path / "SOT")
    incomplete = {"labels.csv": b"class_uid\n", "samples.csv": b"sample_uid\n"}  # no raw_uploads
    with pytest.raises(ValueError, match="raw_uploads.csv"):
        _publish(store, tmp_path, key_path=key_path, authz=authz, csvs=incomplete)
