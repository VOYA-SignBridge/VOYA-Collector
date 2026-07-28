"""REAL integration tests for SOT — exercises the glue the unit tests mock:
GDriveSotStore against live Google Drive, and metadata_db against live Postgres.

Auto-skips unless BOTH are reachable, so it is safe in CI/host. It is meant to
run inside the backend container (Postgres is only reachable on the Docker
network):

    docker compose exec -e PYTHONPATH=/app backend \
        python -m pytest tests/test_sot_integration.py -v

Every test publishes to a UNIQUE throwaway Drive folder and uses SOTTEST_-prefixed
rows; a fixture deletes both afterwards, so live data is never touched.
"""

from __future__ import annotations

import itertools
import time
import tempfile
from pathlib import Path

import pytest


def _infra_available():
    try:
        from app.storage.postgres_connection import connect_postgres

        connect_postgres(connect_timeout=3).close()
    except Exception as exc:
        return False, f"Postgres unreachable: {exc}"
    try:
        from app.storage.gdrive_client import get_gdrive_client

        get_gdrive_client()
    except Exception as exc:
        return False, f"Google Drive unavailable: {exc}"
    return True, ""


_OK, _REASON = _infra_available()
pytestmark = pytest.mark.skipif(
    not _OK, reason=f"SOT integration needs live Drive+Postgres ({_REASON})"
)


LAB_HEADER = (
    "class_uid,class_idx,slug,label_original,language,dialect,is_common_global,"
    "is_common_language,folder_name,created_at,migrated_at\n"
)

# class_uid is free-form, so the SOTTEST_ prefix that marks throwaway rows works
# there. sample_uid is NOT: samples carries a CHECK that it is 10 lowercase hex
# chars, which is what stops a spreadsheet from rewriting a uid like
# "7690373e04" as the float 7.69E+10. So synthetic samples need a valid-shaped
# uid. "5070" reads as SOT0 and is still hex, keeping these rows recognisable in
# a database inspection; the fixture teardown finds them by class_uid anyway.
SAMPLE_RT = b"5070000001"      # round-trip test
SAMPLE_NUMERIC = b"5070000002"  # empty-numeric-fields test


def _lab(*rows):
    return (LAB_HEADER + "".join(rows)).encode("utf-8")


# class_idx is filler for these tests — nothing here asserts its value — but it
# may not REPEAT. It is the model's output index, so classes(class_idx) carries a
# unique index, and the old fixed default of 9000 made every synthetic row in a
# test (and across tests sharing the database) collide on it. reader_sync upserts
# row by row and merely logs a row it cannot write, so the collision surfaced as
# a silently short sync rather than an error. Hand out a fresh index per row.
_next_idx = itertools.count(9000)


def _lrow(uid, slug, label, idx=None, dialect="common"):
    if idx is None:
        idx = next(_next_idx)
    return f"{uid},{idx},{slug},{label},vn,{dialect},0,0,class_{slug},2026-07-18T00:00:00Z,\n"


class _Harness:
    def __init__(self):
        from app.sot import keys, catalog_schema

        self.keys = keys
        self.catalog_schema = catalog_schema
        self.ts = f"{time.strftime('%H%M%S')}_{int(time.time() * 1000) % 1000}"
        self.roots: list[str] = []

        self.authz = Path(tempfile.gettempdir()) / f"sot_it_authz_{self.ts}.json"
        self.authz.write_text("[]", encoding="utf-8")
        self.key_path = Path(tempfile.gettempdir()) / f"sot_it_priv_{self.ts}.key"
        pk = keys.generate_private_key()
        keys.save_private_key(pk, self.key_path)
        keys.add_authorized_key(f"itest-{self.ts}", keys.public_key_b64(pk), self.authz)
        self.authorized = keys.load_authorized_keys(self.authz)
        self.schema_sql = catalog_schema.export_schema_sql()

    def root(self, suffix):
        r = f"SOT_PYIT_{self.ts}_{suffix}"
        self.roots.append(r)
        return r

    def sink(self):
        from app.sot.reader_sync import CatalogSink, _apply_schema_sql
        from app.storage import metadata_db as db

        return CatalogSink(
            apply_schema=_apply_schema_sql,
            column_exists=db._column_exists,
            count_rows=lambda t: db._fetch_all(f"SELECT COUNT(*) AS c FROM {t}")[0]["c"],
            upsert_class=db.upsert_class,
            upsert_sample=db.upsert_sample,
            upsert_raw_upload=db.upsert_raw_upload,
        )

    def publish(self, root, labels, samples, raws):
        from app.sot.publisher import publish_version
        from app.sot.store import GDriveSotStore

        store = GDriveSotStore(root_folder=root, read_only=False)
        return publish_version(
            store,
            csv_sources={"labels.csv": labels, "samples.csv": samples, "raw_uploads.csv": raws},
            schema_sql=self.schema_sql,
            schema_version=self.catalog_schema.schema_version(),
            required_columns=self.catalog_schema.REQUIRED_COLUMNS,
            machine_name=f"itest-{self.ts}",
            private_key_path=self.key_path,
            authorized_keys_path=self.authz,
        )

    def reader(self, root):
        from app.sot.store import GDriveSotStore

        return GDriveSotStore(root_folder=root, read_only=True)

    def sync(self, root):
        from app.sot.reader_sync import sync_from_sot

        return sync_from_sot(self.reader(root), self.sink(), authorized_keys=self.authorized)


@pytest.fixture
def sot():
    h = _Harness()
    try:
        yield h
    finally:
        from app.storage import metadata_db as db
        from app.storage.gdrive_client import get_gdrive_client

        try:
            db._execute(
                "DELETE FROM samples WHERE class_uid LIKE %s OR sample_uid LIKE %s",
                ("SOTTEST_%", "SOTTEST_%"),
            )
            db._execute("DELETE FROM classes WHERE class_uid LIKE %s", ("SOTTEST_%",))
        except Exception:
            pass
        for r in h.roots:
            try:
                get_gdrive_client().delete_path(r)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Drive round trip + Postgres upsert
# ---------------------------------------------------------------------------

def test_publish_then_sync_real_drive_and_postgres(sot):
    from app.storage import metadata_db as db

    root = sot.root("rt")
    ver = sot.publish(
        root,
        _lab(_lrow("SOTTEST_rt1", "hello", "Xin chao"), _lrow("SOTTEST_rt2", "thanks", "Cam on")),
        b"sample_uid,class_uid\n" + SAMPLE_RT + b",SOTTEST_rt1\n",
        b"upload_uid\n",
    )
    assert sot.reader(root).list_version_dirs() == [ver]
    res = sot.sync(root)
    assert res.status == "applied"
    row = db._fetch_all("SELECT slug FROM classes WHERE class_uid='SOTTEST_rt2'")
    assert row and row[0]["slug"] == "thanks"
    srow = db._fetch_all("SELECT 1 FROM samples WHERE sample_uid=%s", (SAMPLE_RT.decode(),))
    assert srow


def test_tampered_csv_on_real_drive_is_rejected(sot):
    from app.sot.reader_sync import SotSyncRejected
    from app.sot.store import GDriveSotStore
    from app.storage import metadata_db as db

    root = sot.root("tamper")
    ver = sot.publish(root, _lab(_lrow("SOTTEST_tp1", "ok", "OK")), b"sample_uid\n", b"upload_uid\n")
    sot.sync(root)  # lands cleanly
    # Flip a byte on Drive after publishing.
    GDriveSotStore(root_folder=root, read_only=False).write_bytes(
        f"{ver}/labels.csv", b"class_uid,slug\nSOTTEST_tp1,HACKED\n"
    )
    with pytest.raises(SotSyncRejected):
        sot.sync(root)
    # DB row unchanged (still the pre-tamper value).
    row = db._fetch_all("SELECT slug FROM classes WHERE class_uid='SOTTEST_tp1'")
    assert row and row[0]["slug"] == "ok"


# ---------------------------------------------------------------------------
# Regression guards for the two bugs the real tests caught
# ---------------------------------------------------------------------------

def test_zero_byte_raw_uploads_is_handled(sot):
    # Bug: download_file rejects 0-byte files; an empty raw_uploads.csv crashed sync.
    root = sot.root("zero")
    sot.publish(root, _lab(_lrow("SOTTEST_z1", "z", "Zero")), b"sample_uid\n", b"")
    assert sot.sync(root).status == "applied"


def test_partial_labels_csv_does_not_crash_upsert(sot):
    # Bug: upsert_class used {**row} and raised KeyError on a labels.csv missing columns.
    from app.storage import metadata_db as db

    root = sot.root("partial")
    sot.publish(root, b"class_uid,slug\nSOTTEST_p1,partial\n", b"sample_uid\n", b"upload_uid\n")
    assert sot.sync(root).status == "applied"
    row = db._fetch_all("SELECT slug, label_original FROM classes WHERE class_uid='SOTTEST_p1'")
    assert row and row[0]["slug"] == "partial" and row[0]["label_original"] is None


# ---------------------------------------------------------------------------
# Data fidelity
# ---------------------------------------------------------------------------

def test_unicode_label_round_trips(sot):
    from app.storage import metadata_db as db

    root = sot.root("uni")
    sot.publish(root, _lab(_lrow("SOTTEST_u1", "mien-dien", "Miến Điện", dialect="bac")),
                b"sample_uid\n", b"upload_uid\n")
    sot.sync(root)
    row = db._fetch_all("SELECT label_original FROM classes WHERE class_uid='SOTTEST_u1'")
    assert row and row[0]["label_original"] == "Miến Điện"


def test_empty_numeric_sample_fields_become_null(sot):
    from app.storage import metadata_db as db

    root = sot.root("num")
    samples = (
        b"sample_uid,class_uid,slug,source_type,user_id,session_id,fps_original,fps_processed,"
        b"seq_len,augment_id,completeness,file_path,created_at\n"
        + SAMPLE_NUMERIC + b",SOTTEST_nc,x,camera,u,sess1,,,,,,feat/x.npz,2026-07-18T00:00:00Z\n"
    )
    sot.publish(root, _lab(_lrow("SOTTEST_nc", "x", "X")), samples, b"upload_uid\n")
    sot.sync(root)
    row = db._fetch_all("SELECT seq_len, completeness FROM samples WHERE sample_uid=%s",
                        (SAMPLE_NUMERIC.decode(),))
    assert row and row[0]["seq_len"] is None and row[0]["completeness"] is None


# ---------------------------------------------------------------------------
# Versioning + idempotency + updates against real infra
# ---------------------------------------------------------------------------

def test_latest_version_wins_and_no_duplicate_latest(sot):
    from app.storage import metadata_db as db
    from app.storage.gdrive_client import get_gdrive_client

    root = sot.root("mv")
    sot.publish(root, _lab(_lrow("SOTTEST_mv1", "one", "One")), b"sample_uid\n", b"upload_uid\n")
    v2 = sot.publish(root, _lab(_lrow("SOTTEST_mv1", "one", "One"), _lrow("SOTTEST_mv2", "two", "Two")),
                     b"sample_uid\n", b"upload_uid\n")
    assert len(sot.reader(root).list_version_dirs()) == 2

    # LATEST.json overwritten in place, not duplicated.
    c = get_gdrive_client()
    fs = c.service.files().list(
        q=f"name='{root}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)").execute().get("files", [])
    n_latest = len(c.service.files().list(
        q=f"name='LATEST.json' and '{fs[0]['id']}' in parents and trashed=false",
        fields="files(id)").execute().get("files", []))
    assert n_latest == 1

    res = sot.sync(root)
    assert res.version == v2
    assert db._fetch_all("SELECT 1 FROM classes WHERE class_uid='SOTTEST_mv2'")


def test_double_sync_is_idempotent(sot):
    from app.storage import metadata_db as db

    root = sot.root("idem")
    sot.publish(root, _lab(_lrow("SOTTEST_id1", "a", "A"), _lrow("SOTTEST_id2", "b", "B")),
                b"sample_uid\n", b"upload_uid\n")
    sot.sync(root)
    n1 = db._fetch_all("SELECT COUNT(*) AS c FROM classes WHERE class_uid LIKE %s", ("SOTTEST_id%",))[0]["c"]
    sot.sync(root)
    n2 = db._fetch_all("SELECT COUNT(*) AS c FROM classes WHERE class_uid LIKE %s", ("SOTTEST_id%",))[0]["c"]
    assert n1 == n2 == 2


def test_republish_updates_existing_row(sot):
    from app.storage import metadata_db as db

    root = sot.root("upd")
    sot.publish(root, _lab(_lrow("SOTTEST_up1", "before", "Before")), b"sample_uid\n", b"upload_uid\n")
    sot.sync(root)
    sot.publish(root, _lab(_lrow("SOTTEST_up1", "after", "After")), b"sample_uid\n", b"upload_uid\n")
    sot.sync(root)
    row = db._fetch_all("SELECT slug FROM classes WHERE class_uid='SOTTEST_up1'")
    assert row and row[0]["slug"] == "after"


# ---------------------------------------------------------------------------
# Store contract against real Drive
# ---------------------------------------------------------------------------

def test_read_missing_file_raises_file_not_found(sot):
    root = sot.root("miss")
    sot.publish(root, _lab(_lrow("SOTTEST_m1", "m", "M")), b"sample_uid\n", b"upload_uid\n")
    with pytest.raises(FileNotFoundError):
        sot.reader(root).read_bytes("Ver1_18072026/does_not_exist.bin")


def test_readonly_reader_creates_no_folder(sot):
    from app.storage.gdrive_client import get_gdrive_client

    ghost = f"SOT_GHOST_{sot.ts}"
    dirs = sot.reader(ghost).list_version_dirs()
    created = get_gdrive_client().service.files().list(
        q=f"name='{ghost}' and trashed=false", fields="files(id)").execute().get("files", [])
    assert dirs == [] and not created


def test_column_exists_reflects_real_schema(sot):
    from app.storage import metadata_db as db

    assert db._column_exists("classes", "class_uid") is True
    assert db._column_exists("classes", "definitely_missing_col") is False


def test_unregistered_machine_version_rejected_on_real_drive(sot):
    """The security boundary on REAL infra: an unregistered machine CAN write to
    the shared Drive (same Google credential), but the reader — which trusts only
    the committed authorized_keys — rejects its version and leaves the DB alone.
    This is what makes a read-only Google credential unnecessary."""
    from app.sot import keys
    from app.sot.publisher import publish_version
    from app.sot.reader_sync import SotSyncRejected, sync_from_sot
    from app.sot.store import GDriveSotStore
    from app.storage import metadata_db as db

    root = sot.root("rogue")

    # A rogue machine: it has a key and its OWN allowlist listing itself, so its
    # local publisher guard passes and it really uploads a signed version.
    rogue_authz = Path(tempfile.gettempdir()) / f"sot_rogue_authz_{sot.ts}.json"
    rogue_authz.write_text("[]", encoding="utf-8")
    rogue_key = Path(tempfile.gettempdir()) / f"sot_rogue_{sot.ts}.key"
    rk = keys.generate_private_key()
    keys.save_private_key(rk, rogue_key)
    keys.add_authorized_key("rogue-vps", keys.public_key_b64(rk), rogue_authz)

    publish_version(
        GDriveSotStore(root_folder=root, read_only=False),
        csv_sources={"labels.csv": _lab(_lrow("SOTTEST_rg1", "rg", "Rogue")),
                     "samples.csv": b"sample_uid\n", "raw_uploads.csv": b"upload_uid\n"},
        schema_sql=sot.schema_sql, schema_version=sot.catalog_schema.schema_version(),
        required_columns=sot.catalog_schema.REQUIRED_COLUMNS, machine_name="rogue-vps",
        private_key_path=rogue_key, authorized_keys_path=rogue_authz,
    )

    # The reader uses the OFFICIAL allowlist (which does NOT contain rogue-vps).
    with pytest.raises(SotSyncRejected):
        sync_from_sot(sot.reader(root), sot.sink(), authorized_keys=sot.authorized)
    # Nothing from the rogue landed in the DB.
    assert not db._fetch_all("SELECT 1 FROM classes WHERE class_uid='SOTTEST_rg1'")
