"""Evidence tests for the 2026-07-21 fixes.

Run so you SEE the behaviour (each test prints an [evidence] line):

    ../.venv/Scripts/python.exe -m pytest tests/test_reassign_sheets_owner.py -v -s
    # or inside the container:
    docker exec voya_worker python -m pytest /workspace/backend/tests/test_reassign_sheets_owner.py -v -s

Covers:
  1. sync_reassign_sample  — a Drive-only sample is materialised-or-REFUSED; the
     old Drive copy is NEVER deleted unless the moved file is re-uploaded
     (regression: reassign used to delete-without-upload => data loss).
  2. export_*_to_sheets    — soft-deleted rows stay on the sheet WITH a deleted_at
     marker, in a STABLE position, so deleting one row no longer shifts every row
     below it up (the "đổi tên trên spreadsheet" the user reported).
  3. save_sequence_npz     — meta["auth_user_id"] is persisted to the DB row and
     user_id keeps the DISPLAY name (the contract the video pipeline now honours
     so video/augmented samples are owned, not auth_user_id=NULL).

These mock at the seam (locks / DB / Drive / Celery dispatch) — no worker, no real
Drive, no real Postgres writes — so they are deterministic and fast.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import MagicMock
from pathlib import Path

import pytest

from app import catalog_sync as cs
from app import export_tasks as et
from app import dataset_samples as ds
from app.catalog_sync import CatalogSyncError
from app.dataset_samples import SAMPLE_FIELDS
from app.dataset_manager import LABEL_FIELDS


# ===========================================================================
# 1. sync_reassign_sample — Drive-only data-loss regression
# ===========================================================================

def _fake_target_meta(tmp_path: Path):
    tgt = tmp_path / "features" / "vn" / "common" / "class_tgt_TARGET00"
    return SimpleNamespace(
        class_uid="TARGET", slug="tgt", label_original="Target",
        language="vn", dialect="common",
        folder_name=lambda: "class_tgt_TARGET00",
        hierarchy_path=lambda: tgt,
    )


def _setup_reassign(monkeypatch, tmp_path, *, download=None, gdrive=True):
    """Patch every external seam of sync_reassign_sample and return the handles a
    test asserts on. `download` ∈ {None, "success", "fail"} controls the fake
    Drive download used to materialise a Drive-only sample."""
    monkeypatch.setattr(cs, "_catalog_lock", lambda: contextlib.nullcontext())
    monkeypatch.setattr(cs, "ensure_tables", lambda: None)
    monkeypatch.setattr(cs, "slog", MagicMock())
    monkeypatch.setattr(cs, "load_labels", lambda: [{"class_uid": "TARGET", "class_idx": "2"}])
    monkeypatch.setattr(cs, "_build_class_meta_from_row", lambda row: _fake_target_meta(tmp_path))
    monkeypatch.setattr(cs, "_write_samples_csv", MagicMock())
    monkeypatch.setattr(cs, "db_upsert_sample", MagicMock())
    monkeypatch.setattr(cs, "_update_sample_metadata_json", lambda *a, **k: None)
    monkeypatch.setattr(cs, "_sync_drive_and_sheets_versioned_tables", lambda *a, **k: None)
    monkeypatch.setattr(cs, "_google_drive_configured", lambda: gdrive)

    client = MagicMock()
    if download == "success":
        def _dl(ref, local):
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"materialised-npz")
            return local
        client.download_file.side_effect = _dl
    elif download == "fail":
        client.download_file.side_effect = RuntimeError("drive 404")
    monkeypatch.setattr(cs, "get_gdrive_client", lambda: client)

    del_task, up_task = MagicMock(), MagicMock()
    monkeypatch.setattr(et, "delete_gdrive_files_task", del_task)
    monkeypatch.setattr(et, "upload_npz_to_gdrive_task", up_task)

    return SimpleNamespace(client=client, del_task=del_task, up_task=up_task)


def test_reassign_local_file_moves_uploads_new_and_deletes_old(monkeypatch, tmp_path):
    """Happy path: a locally-present .npz is moved into the target class, the new
    file is uploaded, and only then is the OLD Drive copy deleted."""
    env = _setup_reassign(monkeypatch, tmp_path, gdrive=True)

    old = tmp_path / "features" / "vn" / "bang" / "class_src" / "sample_ab.npz"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"real-data")
    row = {"sample_uid": "S1", "class_uid": "SOURCE",
           "storage_key": "features/vn/bang/class_src/sample_ab.npz",
           "storage_url": "https://drive.google.com/file/d/OLDID/view",
           "file_path": str(old)}
    monkeypatch.setattr(cs, "list_samples", lambda: [row])

    res = cs.sync_reassign_sample("S1", "TARGET")

    new = tmp_path / "features" / "vn" / "common" / "class_tgt_TARGET00" / "sample_ab.npz"
    print(f"\n[evidence] changed={res['changed']} moved_to_exists={new.exists()} "
          f"old_gone={not old.exists()} upload={env.up_task.delay.call_count} "
          f"delete={env.del_task.delay.call_count}")
    assert res["changed"] is True
    assert new.exists() and not old.exists()                 # file physically moved
    assert env.up_task.delay.call_count == 1                 # new copy uploaded
    assert env.del_task.delay.call_count == 1                # old copy deleted
    assert env.del_task.delay.call_args.kwargs["refs"] == ["features/vn/bang/class_src/sample_ab.npz"]


def test_reassign_drive_only_materialises_then_moves(monkeypatch, tmp_path):
    """Drive-only sample: it is downloaded from Drive first, then moved + uploaded,
    and the old Drive copy is deleted (paired with the upload)."""
    env = _setup_reassign(monkeypatch, tmp_path, download="success", gdrive=True)

    old = tmp_path / "features" / "vn" / "bang" / "class_src" / "sample_cd.npz"  # NOT created
    row = {"sample_uid": "S2", "class_uid": "SOURCE",
           "storage_key": "features/vn/bang/class_src/sample_cd.npz",
           "storage_url": "https://drive.google.com/file/d/OLDID2/view",
           "file_path": str(old)}
    monkeypatch.setattr(cs, "list_samples", lambda: [row])

    res = cs.sync_reassign_sample("S2", "TARGET")

    print(f"\n[evidence] changed={res['changed']} download={env.client.download_file.call_count} "
          f"upload={env.up_task.delay.call_count} delete={env.del_task.delay.call_count}")
    assert res["changed"] is True
    assert env.client.download_file.call_count == 1          # materialised from Drive
    assert env.up_task.delay.call_count == 1                 # then re-uploaded
    assert env.del_task.delay.call_count == 1                # old deleted only after upload


def test_reassign_drive_only_unfetchable_REFUSES_and_never_deletes(monkeypatch, tmp_path):
    """★ Regression: if a Drive-only sample cannot be materialised (download fails),
    the reassign is REFUSED and the old Drive copy is NEVER deleted — the old code
    deleted it and skipped the upload, silently losing the .npz."""
    env = _setup_reassign(monkeypatch, tmp_path, download="fail", gdrive=True)

    old = tmp_path / "features" / "vn" / "bang" / "class_src" / "sample_ef.npz"  # NOT created
    row = {"sample_uid": "S3", "class_uid": "SOURCE",
           "storage_key": "features/vn/bang/class_src/sample_ef.npz",
           "storage_url": "https://drive.google.com/file/d/OLDID3/view",
           "file_path": str(old)}
    monkeypatch.setattr(cs, "list_samples", lambda: [row])

    with pytest.raises(CatalogSyncError) as ei:
        cs.sync_reassign_sample("S3", "TARGET")

    print(f"\n[evidence] refused error_code={ei.value.error_code} "
          f"download_tried={env.client.download_file.call_count} "
          f"delete={env.del_task.delay.call_count} upload={env.up_task.delay.call_count}")
    assert ei.value.error_code == "SAMPLE_NOT_MATERIALIZED"
    assert env.del_task.delay.call_count == 0                # ★ never delete without upload
    assert env.up_task.delay.call_count == 0


def test_reassign_no_drive_ref_refuses_without_touching_drive(monkeypatch, tmp_path):
    """A sample with no local file and no Drive URL to fetch is refused too — and
    no Drive delete/upload is attempted at all."""
    env = _setup_reassign(monkeypatch, tmp_path, gdrive=True)  # no download configured

    old = tmp_path / "features" / "vn" / "bang" / "class_src" / "sample_gh.npz"  # NOT created
    row = {"sample_uid": "S4", "class_uid": "SOURCE",
           "storage_key": "features/vn/bang/class_src/sample_gh.npz",
           "storage_url": "",  # not a Drive URL -> nothing to download
           "file_path": str(old)}
    monkeypatch.setattr(cs, "list_samples", lambda: [row])

    with pytest.raises(CatalogSyncError) as ei:
        cs.sync_reassign_sample("S4", "TARGET")

    print(f"\n[evidence] refused error_code={ei.value.error_code} "
          f"download={env.client.download_file.call_count} delete={env.del_task.delay.call_count}")
    assert ei.value.error_code == "SAMPLE_NOT_MATERIALIZED"
    assert env.client.download_file.call_count == 0
    assert env.del_task.delay.call_count == 0


# ===========================================================================
# 2. Sheets export — soft-deleted rows stay, marked, in a stable position
# ===========================================================================

def _sheet_client(monkeypatch):
    """A fake gdrive client that records every replace_sheet_values() matrix."""
    writes = []
    client = MagicMock()
    client.replace_sheet_values.side_effect = lambda sid, gid, values: writes.append(values)
    monkeypatch.setattr("app.storage.gdrive_client.get_gdrive_client", lambda: client)
    return writes


def _pos(values, uid):
    header = values[0]
    ui = header.index("sample_uid")
    for i, row in enumerate(values[1:], start=1):
        if row[ui] == uid:
            return i
    return -1


def _cell(values, uid, col, key="sample_uid"):
    header = values[0]
    ci = header.index(col)
    ki = header.index(key)
    for row in values[1:]:
        if row[ki] == uid:
            return row[ci]
    return None


def _srow(uid, created):
    r = {f: "" for f in SAMPLE_FIELDS}
    r["sample_uid"] = uid
    r["created_at"] = created
    r["label_original"] = f"lbl_{uid}"
    return r


def _drow(uid, created, deleted_at):
    r = _srow(uid, created)
    r["deleted_at"] = deleted_at
    return r


def test_samples_sheet_has_deleted_at_column_and_marks_deleted_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(et.settings, "google_sheets_samples_spreadsheet_id", "SID", raising=False)
    monkeypatch.setattr(et.settings, "google_sheets_samples_sheet_gid", 111, raising=False)
    monkeypatch.setattr(ds, "SAMPLES_CSV", tmp_path / "samples.csv", raising=False)
    writes = _sheet_client(monkeypatch)

    monkeypatch.setattr(ds, "list_samples", lambda: [_srow("A", "2026-01-01"), _srow("C", "2026-01-03")])
    monkeypatch.setattr("app.storage.metadata_db.list_all_deleted_samples",
                        lambda: [_drow("B", "2026-01-02", "2026-06-01T00:00:00Z")])

    et.export_samples_to_sheets.run()
    values = writes[-1]

    print(f"\n[evidence] header_tail={values[0][-1]!r} rows={len(values) - 1} "
          f"B_deleted_at={_cell(values, 'B', 'deleted_at')!r} A_deleted_at={_cell(values, 'A', 'deleted_at')!r}")
    assert values[0][-1] == "deleted_at"                      # marker column exists
    assert len(values) - 1 == 3                               # deleted B is KEPT, not dropped
    assert _cell(values, "B", "deleted_at") == "2026-06-01T00:00:00Z"   # marked deleted
    assert _cell(values, "A", "deleted_at") == ""             # active rows unmarked
    assert _cell(values, "C", "deleted_at") == ""


def test_soft_deleting_a_row_does_not_shift_the_others(monkeypatch, tmp_path):
    """★ The reported bug: deleting a middle row must NOT move the rows around it.
    With the marker column + stable sort, B stays in place (marked) and A/C keep
    their exact positions."""
    monkeypatch.setattr(et.settings, "google_sheets_samples_spreadsheet_id", "SID", raising=False)
    monkeypatch.setattr(et.settings, "google_sheets_samples_sheet_gid", 111, raising=False)
    monkeypatch.setattr(ds, "SAMPLES_CSV", tmp_path / "samples.csv", raising=False)
    writes = _sheet_client(monkeypatch)

    # Run 1: A,B,C all active.
    monkeypatch.setattr(ds, "list_samples",
                        lambda: [_srow("A", "2026-01-01"), _srow("B", "2026-01-02"), _srow("C", "2026-01-03")])
    monkeypatch.setattr("app.storage.metadata_db.list_all_deleted_samples", lambda: [])
    et.export_samples_to_sheets.run()
    before = writes[-1]

    # Run 2: B is now soft-deleted (removed from the active csv, present in DB).
    monkeypatch.setattr(ds, "list_samples",
                        lambda: [_srow("A", "2026-01-01"), _srow("C", "2026-01-03")])
    monkeypatch.setattr("app.storage.metadata_db.list_all_deleted_samples",
                        lambda: [_drow("B", "2026-01-02", "2026-06-01T00:00:00Z")])
    et.export_samples_to_sheets.run()
    after = writes[-1]

    print(f"\n[evidence] before A/B/C = {_pos(before,'A')}/{_pos(before,'B')}/{_pos(before,'C')} | "
          f"after A/B/C = {_pos(after,'A')}/{_pos(after,'B')}/{_pos(after,'C')} "
          f"| B_marker={_cell(after,'B','deleted_at')!r}")
    # A and C did NOT move; B is still present (marked), not removed.
    assert _pos(after, "A") == _pos(before, "A") == 1
    assert _pos(after, "C") == _pos(before, "C") == 3
    assert _pos(after, "B") == 2
    assert _cell(after, "B", "deleted_at") != ""              # visibly marked deleted


def test_samples_sheet_dedupes_active_over_deleted(monkeypatch, tmp_path):
    """If a uid appears in both the active csv and the deleted DB set, it is written
    ONCE (active wins) — no duplicate row on the sheet."""
    monkeypatch.setattr(et.settings, "google_sheets_samples_spreadsheet_id", "SID", raising=False)
    monkeypatch.setattr(et.settings, "google_sheets_samples_sheet_gid", 111, raising=False)
    monkeypatch.setattr(ds, "SAMPLES_CSV", tmp_path / "samples.csv", raising=False)
    writes = _sheet_client(monkeypatch)

    monkeypatch.setattr(ds, "list_samples", lambda: [_srow("A", "2026-01-01")])
    monkeypatch.setattr("app.storage.metadata_db.list_all_deleted_samples",
                        lambda: [_drow("A", "2026-01-01", "2026-06-01T00:00:00Z")])

    et.export_samples_to_sheets.run()
    values = writes[-1]
    a_rows = [r for r in values[1:] if r[values[0].index("sample_uid")] == "A"]
    print(f"\n[evidence] A_row_count={len(a_rows)} A_deleted_at={_cell(values,'A','deleted_at')!r}")
    assert len(a_rows) == 1                                   # not duplicated
    assert _cell(values, "A", "deleted_at") == ""            # active copy wins


def test_labels_sheet_keeps_deleted_class_marked_and_ordered(monkeypatch):
    monkeypatch.setattr(et.settings, "google_sheets_labels_spreadsheet_id", "LID", raising=False)
    monkeypatch.setattr(et.settings, "google_sheets_labels_sheet_gid", 222, raising=False)
    writes = _sheet_client(monkeypatch)

    def _lrow(uid, idx):
        r = {f: "" for f in LABEL_FIELDS}
        r["class_uid"] = uid
        r["class_idx"] = str(idx)
        r["label_original"] = f"lbl_{uid}"
        r["is_common_global"] = "0"
        r["is_common_language"] = "0"
        return r

    monkeypatch.setattr("app.dataset_manager.load_labels", lambda: [_lrow("A", 1), _lrow("C", 3)])
    monkeypatch.setattr("app.storage.metadata_db.list_deleted_classes", lambda: [{
        "class_uid": "B", "class_idx": 2, "slug": "b", "label_original": "lbl_B",
        "language": "vn", "dialect": "common",
        "is_common_global": False, "is_common_language": False,  # DB booleans
        "folder_name": "class_b", "created_at": None, "migrated_at": None,
        "deleted_at": "2026-06-01T00:00:00Z",
    }])

    et.export_labels_to_sheets.run()
    values = writes[-1]
    ui = values[0].index("class_uid")
    order = [row[ui] for row in values[1:]]

    print(f"\n[evidence] header_tail={values[0][-1]!r} order={order} "
          f"B_deleted_at={_cell(values,'B','deleted_at',key='class_uid')!r} "
          f"B_is_common_global={_cell(values,'B','is_common_global',key='class_uid')!r}")
    assert values[0][-1] == "deleted_at"
    assert order == ["A", "B", "C"]                           # stable class_idx order, deleted kept in place
    assert _cell(values, "B", "deleted_at", key="class_uid") == "2026-06-01T00:00:00Z"
    # DB boolean normalised to the csv "0"/"1" form (not "False").
    assert _cell(values, "B", "is_common_global", key="class_uid") == "0"


# ===========================================================================
# 3. Ownership — meta["auth_user_id"] is persisted (contract the pipeline honours)
# ===========================================================================

def test_save_sequence_npz_persists_auth_user_id_and_display_name(monkeypatch, tmp_path):
    """The video pipeline now puts the auth UUID in meta['auth_user_id'] and the
    DISPLAY name in meta['user_id']. This test locks the sink contract: whatever
    the pipeline supplies as auth_user_id lands on the Postgres row, and user_id
    stays the display name (previously the UUID leaked into user_id + owner=NULL)."""
    import numpy as np

    monkeypatch.setattr(ds.settings, "use_google_drive", False, raising=False)

    class_dir = tmp_path / "features" / "vn" / "common" / "class_x_00000000"
    class_meta = SimpleNamespace(
        class_uid="C1", slug="x", label_original="X",
        language="vn", dialect="common",
        folder_name=lambda: "class_x_00000000",
        hierarchy_path=lambda: class_dir,
    )

    captured = {}
    monkeypatch.setattr(ds, "append_sample_row", lambda row: captured.__setitem__("csv", row))
    monkeypatch.setattr("app.storage.metadata_db.insert_sample",
                        lambda row: captured.__setitem__("db", row))

    seq = np.zeros((60, 126), dtype="float32")
    meta = {"user": "Alice", "user_id": "Alice", "auth_user_id": "uuid-123", "session_id": "s1"}
    ds.save_sequence_npz(class_meta, seq, meta=meta, augment_id=0, source_type="video")

    print(f"\n[evidence] db.auth_user_id={captured['db']['auth_user_id']!r} "
          f"db.user_id={captured['db']['user_id']!r} csv.user_id={captured['csv']['user_id']!r}")
    assert captured["db"]["auth_user_id"] == "uuid-123"       # owner persisted
    assert captured["db"]["user_id"] == "Alice"               # display name, NOT the UUID
    assert captured["csv"]["user_id"] == "Alice"


def test_save_sequence_npz_missing_auth_user_id_is_null_not_crash(monkeypatch, tmp_path):
    """A guest/legacy capture with no auth_user_id must still save (owner NULL),
    not raise — so the absence of an owner never blocks a capture."""
    import numpy as np

    monkeypatch.setattr(ds.settings, "use_google_drive", False, raising=False)
    class_dir = tmp_path / "features" / "vn" / "common" / "class_y_00000000"
    class_meta = SimpleNamespace(
        class_uid="C2", slug="y", label_original="Y", language="vn", dialect="common",
        folder_name=lambda: "class_y_00000000", hierarchy_path=lambda: class_dir,
    )
    captured = {}
    monkeypatch.setattr(ds, "append_sample_row", lambda row: None)
    monkeypatch.setattr("app.storage.metadata_db.insert_sample",
                        lambda row: captured.__setitem__("db", row))

    seq = np.zeros((60, 126), dtype="float32")
    ds.save_sequence_npz(class_meta, seq, meta={"user_id": "Bob"}, augment_id=0, source_type="camera")

    print(f"\n[evidence] db.auth_user_id={captured['db']['auth_user_id']!r} (None => guest, no crash)")
    assert captured["db"]["auth_user_id"] is None
