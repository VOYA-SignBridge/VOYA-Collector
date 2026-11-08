"""Labels sync must avoid idle writes without losing catalogue changes."""
from unittest.mock import Mock

import pytest

from app import export_tasks
from app.modules.dataset import catalog as dataset_manager
from app.storage import metadata_db, gdrive_client


@pytest.fixture
def sync(monkeypatch, tmp_path):
    rows = [{"class_uid": "a", "class_idx": "1", "label": "Hello"}]
    deleted = []
    client = Mock()
    monkeypatch.setattr(export_tasks.settings, "google_sheets_labels_spreadsheet_id", "sheet-a")
    monkeypatch.setattr(export_tasks.settings, "google_sheets_labels_sheet_gid", 42)
    monkeypatch.setattr(dataset_manager, "MASTER_LABELS", tmp_path / "labels.csv")
    monkeypatch.setattr(dataset_manager, "LABEL_FIELDS", ["class_uid", "class_idx", "label"])
    monkeypatch.setattr(dataset_manager, "_load_all_labels_unscoped", lambda: list(rows))
    monkeypatch.setattr(metadata_db, "list_deleted_classes", lambda: list(deleted))
    monkeypatch.setattr(metadata_db, "ensure_tables", Mock(side_effect=AssertionError("DDL in periodic task")))
    monkeypatch.setattr(gdrive_client, "get_gdrive_client", lambda: client)
    return export_tasks.export_labels_to_sheets.run, client, rows, deleted, tmp_path


def test_unchanged_labels_skip_remote_write_and_schema_work(sync):
    run, client, _, _, _ = sync
    assert run()["status"] == "success"
    assert run() == {"status": "skipped", "reason": "unchanged", "rows": 1}
    assert client.replace_sheet_values.call_count == 1


def test_rename_and_soft_delete_both_resync(sync):
    run, client, rows, deleted, _ = sync
    run()
    rows[0]["label"] = "Renamed"
    assert run()["status"] == "success"
    deleted.append({**rows.pop(), "deleted_at": "2026-10-17"})
    assert run()["status"] == "success"
    assert client.replace_sheet_values.call_count == 3
    assert client.replace_sheet_values.call_args.args[2][1][-1] == "2026-10-17"


@pytest.mark.parametrize("setting,value", [
    ("google_sheets_labels_spreadsheet_id", "sheet-b"),
    ("google_sheets_labels_sheet_gid", 99),
])
def test_destination_change_resyncs(sync, monkeypatch, setting, value):
    run, client, _, _, _ = sync
    run()
    monkeypatch.setattr(export_tasks.settings, setting, value)
    assert run()["status"] == "success"
    assert client.replace_sheet_values.call_count == 2


def test_failed_upload_does_not_cache_new_content(sync):
    run, client, rows, _, path = sync
    run()
    before = (path / ".labels_sheet.synced").read_text()
    rows[0]["label"] = "Changed"
    client.replace_sheet_values.side_effect = RuntimeError("offline")
    with pytest.raises(Exception, match="offline"):
        run()
    assert (path / ".labels_sheet.synced").read_text() == before
    client.replace_sheet_values.side_effect = None
    assert run()["status"] == "success"


def test_database_failure_never_publishes_partial_catalogue(sync, monkeypatch):
    run, client, _, _, path = sync
    monkeypatch.setattr(metadata_db, "list_deleted_classes", Mock(side_effect=RuntimeError("db offline")))
    with pytest.raises(Exception, match="db offline"):
        run()
    client.replace_sheet_values.assert_not_called()
    assert not (path / ".labels_sheet.synced").exists()


def test_empty_catalogue_preserves_existing_sheet(sync):
    run, client, rows, _, _ = sync
    run()
    rows.clear()
    assert run()["reason"] == "no_labels"
    assert client.replace_sheet_values.call_count == 1


def test_unconfigured_sync_does_no_database_work(sync, monkeypatch):
    run, client, _, _, _ = sync
    monkeypatch.setattr(export_tasks.settings, "google_sheets_labels_spreadsheet_id", "")
    read = Mock(side_effect=AssertionError("unexpected database read"))
    monkeypatch.setattr(metadata_db, "list_deleted_classes", read)
    assert run()["reason"] == "not_configured"
    client.replace_sheet_values.assert_not_called()
    read.assert_not_called()


def test_corrupt_fingerprint_resyncs_instead_of_blocking(sync):
    run, client, _, _, path = sync
    (path / ".labels_sheet.synced").write_bytes(b"\xff\xfe")
    assert run()["status"] == "success"
    assert run()["reason"] == "unchanged"
    assert client.replace_sheet_values.call_count == 1


def test_unwritable_fingerprint_does_not_fail_successful_upload(sync):
    run, client, _, _, path = sync
    (path / ".labels_sheet.synced").mkdir()
    assert run()["status"] == "success"
    assert run()["status"] == "success"
    assert client.replace_sheet_values.call_count == 2


def test_stale_fingerprint_resyncs_to_repair_an_edited_sheet(sync):
    """Cùng nội dung nhưng lần đẩy đã cũ hơn hạn: vẫn đẩy lại, để một sheet bị
    ai đó sửa/xoá tay được vá chứ không bị báo "unchanged" mãi."""
    import os
    import time

    run, client, _, _, path = sync
    assert run()["status"] == "success"
    guard = path / ".labels_sheet.synced"
    old = time.time() - export_tasks._LABELS_SHEET_REFRESH_SECONDS - 5
    os.utime(guard, (old, old))
    assert run()["status"] == "success"
    assert client.replace_sheet_values.call_count == 2
