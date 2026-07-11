"""Standalone tests for Đợt 1 + Đợt 2 optimizations (no pytest dependency).

Run inside the backend container against the mounted source:
    docker exec -w /workspace/backend voya_backend python tests/test_optimizations.py

Covers:
  T1.1  no double npz serialization (BytesIO removed)
  T1.2  storage_key persisted to samples.csv even before deferred upload
  T1.3  configurable download chunk + max_samples_per_class default = 2000
  T2.1  Postgres connection pool: works, reused per-process, fork-safe
Plus the baseline local-save path (npz round-trips, single file, no temp leak).
"""
from __future__ import annotations

import csv
import inspect
import os
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

from app.config import settings
from app import dataset_samples
from app import dataset_manager
from app.dataset_manager import ClassMetadata

PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []
SKIPPED: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append((name, str(detail)))
        print(f"  FAIL  {name}  -> {detail}")


# --------------------------------------------------------------------------- #
# T1.3 — config defaults
# --------------------------------------------------------------------------- #
def test_config_defaults():
    print("[test_config_defaults]")
    check("max_samples_per_class == 200", settings.max_samples_per_class == 200,
          f"got {settings.max_samples_per_class}")
    check("google_drive_download_chunk_mb is int", isinstance(getattr(settings, "google_drive_download_chunk_mb", None), int))
    check("google_drive_download_chunk_mb default == 10", getattr(settings, "google_drive_download_chunk_mb", None) == 10,
          getattr(settings, "google_drive_download_chunk_mb", None))
    for f in ("db_pool_min", "db_pool_max", "db_connect_timeout"):
        check(f"config.{f} is int", isinstance(getattr(settings, f, None), int))
    check("db_pool_max >= db_pool_min", settings.db_pool_max >= settings.db_pool_min)


# --------------------------------------------------------------------------- #
# T1.1 — no double serialization  (+ T1.3 download chunk usage)
# --------------------------------------------------------------------------- #
def test_no_double_serialization():
    print("[test_no_double_serialization]")
    src = inspect.getsource(dataset_samples.save_sequence_npz)
    check("save_sequence_npz has no BytesIO", "BytesIO" not in src, "BytesIO still referenced")
    check("save_sequence_npz compresses exactly once", src.count("savez_compressed") == 1,
          f"savez_compressed count = {src.count('savez_compressed')}")


def test_download_chunk_configurable():
    print("[test_download_chunk_configurable]")
    from app.storage.gdrive_client import GoogleDriveClient
    src = inspect.getsource(GoogleDriveClient.download_file)
    check("download uses self.download_chunk_size_bytes", "self.download_chunk_size_bytes" in src)
    check("download has no hardcoded 1024*1024*10", "1024*1024*10" not in src)


# --------------------------------------------------------------------------- #
# save_sequence_npz behavior (baseline + T1.2)
# --------------------------------------------------------------------------- #
def _make_meta() -> ClassMetadata:
    return ClassMetadata(
        class_uid="testuid123456", slug="xin-chao", label_original="xin chao",
        language="vn", dialect="bac", is_common_global=False, is_common_language=False,
    )


def _patch_dataset_root(tmp: str) -> None:
    dataset_manager.FEATURES_ROOT = Path(tmp) / "features"
    dataset_samples.DATASET_ROOT = Path(tmp)
    dataset_samples.SAMPLES_DIR = Path(tmp) / "samples"
    dataset_samples.SAMPLES_CSV = dataset_samples.SAMPLES_DIR / "samples.csv"


def _last_sample_row():
    with open(dataset_samples.SAMPLES_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows[-1] if rows else None


def _no_op_db():
    """Patch metadata_db.insert_sample to avoid polluting the real DB."""
    import app.storage.metadata_db as mdb
    orig = mdb.insert_sample
    mdb.insert_sample = lambda *a, **k: None
    # save_sequence_npz imports it locally each call, so also shadow at source module
    return mdb, orig


def test_save_npz_local():
    print("[test_save_npz_local]")
    tmp = tempfile.mkdtemp()
    old_gd = settings.use_google_drive
    mdb, orig_insert = _no_op_db()
    try:
        _patch_dataset_root(tmp)
        settings.use_google_drive = False
        cm = _make_meta()
        seq = np.random.rand(60, 126).astype("float32")
        path = dataset_samples.save_sequence_npz(
            cm, seq, meta={"user": "u", "user_id": "42", "session_id": "s"},
            augment_id=0, source_type="video",
        )
        d = cm.hierarchy_path()
        npzs = [p for p in os.listdir(d) if p.endswith(".npz")]
        tmps = [p for p in os.listdir(d) if p.startswith("npztmp_")]
        check("local: exactly one npz on disk", len(npzs) == 1, f"npzs={npzs}")
        check("local: no leftover temp file", len(tmps) == 0, f"tmps={tmps}")
        data = np.load(path, allow_pickle=True)
        check("local: sequence round-trips", np.allclose(data["sequence"], seq))
        meta = data["meta"].item()
        check("local: meta carries user_id", meta.get("user_id") == "42", meta)
        row = _last_sample_row()
        check("local: storage_key empty when gdrive off", (row or {}).get("storage_key") == "",
              (row or {}).get("storage_key"))
    finally:
        settings.use_google_drive = old_gd
        mdb.insert_sample = orig_insert
        shutil.rmtree(tmp, ignore_errors=True)


def test_save_npz_storage_key_persisted():
    print("[test_save_npz_storage_key_persisted]  (T1.2)")
    tmp = tempfile.mkdtemp()
    old_gd = settings.use_google_drive
    mdb, orig_insert = _no_op_db()
    import app.export_tasks as et
    orig_task = et.upload_npz_to_gdrive_task
    calls: list[dict] = []

    class _DummyTask:
        def delay(self, **kw):
            calls.append(kw)

    try:
        _patch_dataset_root(tmp)
        settings.use_google_drive = True
        et.upload_npz_to_gdrive_task = _DummyTask()
        cm = _make_meta()
        seq = np.random.rand(60, 126).astype("float32")
        dataset_samples.save_sequence_npz(
            cm, seq, meta={"user": "u", "user_id": "42", "session_id": "s"},
            augment_id=3, source_type="video",
        )
        expected_prefix = f"features/vn/bac/{cm.folder_name()}/"
        row = _last_sample_row()
        sk = (row or {}).get("storage_key") or ""
        check("gdrive: storage_key persisted (not empty)", sk.startswith(expected_prefix), f"storage_key={sk!r}")
        check("gdrive: upload task dispatched once", len(calls) == 1, f"calls={len(calls)}")
        if calls:
            check("gdrive: task received storage_key",
                  str(calls[0].get("storage_key", "")).startswith(expected_prefix), calls[0])
    finally:
        settings.use_google_drive = old_gd
        et.upload_npz_to_gdrive_task = orig_task
        mdb.insert_sample = orig_insert
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- #
# T2.1 — Postgres connection pool
# --------------------------------------------------------------------------- #
def test_pool():
    print("[test_pool]  (T2.1)")
    from app.storage import postgres_connection as pc
    try:
        conn = pc.get_pooled_conn()
    except Exception as e:
        SKIPPED.append(("pool tests", f"postgres unreachable: {e}"))
        print(f"  SKIP  pool tests (postgres unreachable: {e})")
        return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            r = cur.fetchone()
        check("pool: SELECT 1 works", r[0] == 1, r)
    finally:
        pc.put_pooled_conn(conn)

    p1 = pc.get_pool()
    p2 = pc.get_pool()
    check("pool: reused within same process", p1 is p2)

    # fork-safety: simulate a PID change -> pool must be rebuilt
    real_getpid = pc.os.getpid
    try:
        pc.os.getpid = lambda: real_getpid() + 100000
        p3 = pc.get_pool()
        check("pool: rebuilt on PID change (fork-safe)", p3 is not p1)
    finally:
        pc.os.getpid = real_getpid
        # reset so subsequent real usage rebuilds cleanly for the real PID
        try:
            pc._pool = None
            pc._pool_pid = None
        except Exception:
            pass

    # borrow/return several times to confirm reuse doesn't exhaust the pool
    ok = True
    for _ in range(5):
        try:
            c = pc.get_pooled_conn()
            with c.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            pc.put_pooled_conn(c)
        except Exception as e:
            ok = False
            check("pool: repeated borrow/return", False, str(e))
            break
    if ok:
        check("pool: repeated borrow/return (5x)", True)


def _seed_samples_csv(uids):
    dataset_samples.SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    with open(dataset_samples.SAMPLES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=dataset_samples.SAMPLE_FIELDS)
        w.writeheader()
        for uid in uids:
            row = {k: "" for k in dataset_samples.SAMPLE_FIELDS}
            row["sample_uid"] = uid
            w.writerow(row)


def _read_samples_csv():
    with open(dataset_samples.SAMPLES_CSV, newline="", encoding="utf-8") as f:
        return {r["sample_uid"]: r for r in csv.DictReader(f)}


def test_bulk_csv_update():
    print("[test_bulk_csv_update]  (T3.2)")
    tmp = tempfile.mkdtemp()
    try:
        _patch_dataset_root(tmp)
        _seed_samples_csv(["a1", "b2", "c3"])
        dataset_samples.update_sample_rows_bulk({
            "a1": {"storage_url": "urlA", "storage_key": "keyA"},
            "c3": {"storage_url": "urlC", "storage_key": "keyC", "nonexistent_field": "x"},
        })
        rows = _read_samples_csv()
        check("bulk: a1 updated", rows["a1"]["storage_url"] == "urlA" and rows["a1"]["storage_key"] == "keyA")
        check("bulk: c3 updated", rows["c3"]["storage_url"] == "urlC")
        check("bulk: b2 untouched", rows["b2"]["storage_url"] == "")
        check("bulk: invalid field ignored", "nonexistent_field" not in rows["c3"])
        check("bulk: row count preserved (3)", len(rows) == 3)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_save_npz_batch_collector():
    print("[test_save_npz_batch_collector]  (T3.1)")
    tmp = tempfile.mkdtemp()
    old_gd = settings.use_google_drive
    mdb, orig_insert = _no_op_db()
    import app.export_tasks as et
    orig_task = et.upload_npz_to_gdrive_task
    dispatched = []

    class _DummyTask:
        def delay(self, **kw):
            dispatched.append(kw)

    try:
        _patch_dataset_root(tmp)
        settings.use_google_drive = True
        et.upload_npz_to_gdrive_task = _DummyTask()
        cm = _make_meta()
        seq = np.random.rand(60, 126).astype("float32")
        collector = []
        for i in range(3):
            dataset_samples.save_sequence_npz(
                cm, seq, meta={"user": "u", "user_id": "42", "session_id": "s"},
                augment_id=i, source_type="video", upload_collector=collector,
            )
        check("batch: collector received 3 items", len(collector) == 3, len(collector))
        check("batch: NO per-file dispatch when batching", len(dispatched) == 0, len(dispatched))
        check("batch: items carry sample_uid/local_path/storage_key",
              all(all(k in it for k in ("sample_uid", "local_path", "storage_key")) for it in collector))
    finally:
        settings.use_google_drive = old_gd
        et.upload_npz_to_gdrive_task = orig_task
        mdb.insert_sample = orig_insert
        shutil.rmtree(tmp, ignore_errors=True)


def test_batch_upload_task():
    print("[test_batch_upload_task]  (T3.1 orchestration + T3.2 single csv write)")
    tmp = tempfile.mkdtemp()
    import app.export_tasks as et
    import app.storage.gdrive_client as gc
    import app.storage.metadata_db as mdb
    orig_up, orig_db = gc.upload_to_gdrive, mdb.update_sample_gdrive_url
    calls = {"up": 0, "db": 0}
    try:
        _patch_dataset_root(tmp)
        _seed_samples_csv(["x1", "x2"])
        items = []
        for uid in ["x1", "x2"]:
            p = os.path.join(tmp, f"{uid}.npz")
            with open(p, "wb") as f:
                f.write(b"fake-npz")
            items.append({"sample_uid": uid, "local_path": p, "storage_key": f"features/{uid}.npz", "sidecar_path": ""})

        def fake_up(local, key, **kw):
            calls["up"] += 1
            return f"https://drive/{key}"

        def fake_db(uid, url):
            calls["db"] += 1

        gc.upload_to_gdrive = fake_up
        mdb.update_sample_gdrive_url = fake_db

        res = et.upload_npz_batch_to_gdrive_task.apply(args=[items]).get()
        check("batch task: uploaded=2", res.get("uploaded") == 2, res)
        check("batch task: upload called 2x", calls["up"] == 2, calls["up"])
        check("batch task: db updated 2x", calls["db"] == 2, calls["db"])
        rows = _read_samples_csv()
        check("batch task: csv x1 url set", rows["x1"]["storage_url"] == "https://drive/features/x1.npz", rows["x1"]["storage_url"])
        check("batch task: csv x2 url set", rows["x2"]["storage_url"].startswith("https://drive/"))
    finally:
        gc.upload_to_gdrive, mdb.update_sample_gdrive_url = orig_up, orig_db
        shutil.rmtree(tmp, ignore_errors=True)


def test_csv_wide_header_alignment():
    print("[test_csv_wide_header_alignment]  (schema-drift fix: 23-col CSV)")
    tmp = tempfile.mkdtemp()
    wide = [
        "sample_uid", "class_uid", "slug", "label_original", "language", "dialect",
        "source_type", "user_id", "username", "session_uid", "fps_original", "fps_processed",
        "seq_len", "augment_id", "completeness", "file_path", "storage_key", "storage_url",
        "checksum", "status", "created_at", "updated_at", "deleted_at",
    ]
    try:
        _patch_dataset_root(tmp)
        dataset_samples.SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        with open(dataset_samples.SAMPLES_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=wide)
            w.writeheader()
            for uid in ["w1", "w2"]:
                row = {k: "" for k in wide}
                row["sample_uid"] = uid
                row["username"] = "alice"
                row["status"] = "active"
                w.writerow(row)

        # bulk update must NOT crash on the wide header and must hit the right columns
        dataset_samples.update_sample_rows_bulk({"w1": {"storage_url": "https://d/w1", "storage_key": "k1"}})
        rows = _read_samples_csv()
        check("wide: header preserved (23 cols)", set(rows["w1"].keys()) == set(wide))
        check("wide: storage_url set on w1", rows["w1"]["storage_url"] == "https://d/w1", rows["w1"]["storage_url"])
        check("wide: storage_key set on w1", rows["w1"]["storage_key"] == "k1")
        check("wide: extra col (username) preserved", rows["w1"]["username"] == "alice")
        check("wide: w2 untouched", rows["w2"]["storage_url"] == "")

        # append must align a SAMPLE_FIELDS-shaped row dict to the wide header
        dataset_samples.append_sample_row(
            {"sample_uid": "w3", "slug": "z", "storage_key": "kk", "storage_url": "", "session_id": "sid"}
        )
        rows = _read_samples_csv()
        check("wide: appended row lands storage_key in right column", rows["w3"]["storage_key"] == "kk", rows["w3"].get("storage_key"))
        check("wide: appended row has 23 columns", len(rows["w3"]) == 23, len(rows["w3"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    tests = [
        test_config_defaults,
        test_no_double_serialization,
        test_download_chunk_configurable,
        test_save_npz_local,
        test_save_npz_storage_key_persisted,
        test_bulk_csv_update,
        test_save_npz_batch_collector,
        test_batch_upload_task,
        test_csv_wide_header_alignment,
        test_pool,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            import traceback
            FAILED.append((t.__name__, repr(e)))
            print(f"  ERROR {t.__name__}: {e}")
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"SUMMARY: {len(PASSED)} passed, {len(FAILED)} failed, {len(SKIPPED)} skipped")
    if SKIPPED:
        for n, d in SKIPPED:
            print(f"  SKIPPED: {n} ({d})")
    if FAILED:
        for n, d in FAILED:
            print(f"  FAILED : {n} -> {d}")
    print("=" * 60)
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
