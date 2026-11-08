import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from app.storage.metadata_db import (
    _execute, _fetch_all as original_fetch_all, ensure_tables
)
from app.bootstrap.database import sync_missing_data_on_startup

# Mock data
MOCK_CLASS = {
    "class_uid": "test-sync-class-001",
    "class_idx": 9999,
    "slug": "test-slug",
    "label_original": "Test Label",
    "language": "vn",
    "dialect": "common",
    "is_common_global": False,
    "is_common_language": False,
    "folder_name": "test_folder",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "migrated_at": None,
}

@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Ensure tables exist, and any mock data is cleaned up before and after each test (Hard Delete)."""
    from app.modules.dataset.vocabulary_registry import seed_from_csv

    ensure_tables()
    # Production calls this immediately before the catalog sync. Keep the
    # integration fixture under the same foreign-key precondition.
    seed_from_csv()
    _execute("DELETE FROM classes WHERE class_uid = %s", (MOCK_CLASS["class_uid"],))
    yield
    # Teardown logic
    _execute("DELETE FROM classes WHERE class_uid = %s", (MOCK_CLASS["class_uid"],))

def fake_fetch_all(query, params=None):
    """
    Fake fetch_all to bypass the count check in sync_missing_data_on_startup.
    When the function checks COUNT(*), we return 0 so it thinks the DB is empty 
    and forces the UPSERT loop to run for our mock data.
    """
    if query.strip().upper().startswith("SELECT COUNT(*)"):
        return [{"c": 0}]
    return original_fetch_all(query, params)

@patch("app.storage.metadata_db._fetch_all", side_effect=fake_fetch_all)
@patch("app.modules.dataset.catalog._load_all_labels_unscoped")
@patch("app.modules.dataset.samples._load_all_samples_unscoped")
@patch("app.modules.dataset.raw_uploads.list_raw_uploads")
def test_sync_on_empty_db(mock_raw, mock_samples, mock_labels, mock_fetch):
    """Test 1: When DB is missing records, it should insert them."""
    mock_labels.return_value = [MOCK_CLASS]
    mock_samples.return_value = []
    mock_raw.return_value = []
    
    # Run sync
    sync_missing_data_on_startup()
    
    # Verify
    rows = original_fetch_all("SELECT * FROM classes WHERE class_uid = %s", (MOCK_CLASS["class_uid"],))
    assert len(rows) == 1
    assert rows[0]["slug"] == "test-slug"

@patch("app.storage.metadata_db._fetch_all", side_effect=fake_fetch_all)
@patch("app.modules.dataset.catalog._load_all_labels_unscoped")
@patch("app.modules.dataset.samples._load_all_samples_unscoped")
@patch("app.modules.dataset.raw_uploads.list_raw_uploads")
def test_sync_idempotency(mock_raw, mock_samples, mock_labels, mock_fetch):
    """Test 2: Running multiple times shouldn't duplicate or throw errors."""
    mock_labels.return_value = [MOCK_CLASS]
    mock_samples.return_value = []
    mock_raw.return_value = []
    
    # Run sync 3 times
    sync_missing_data_on_startup()
    sync_missing_data_on_startup()
    sync_missing_data_on_startup()
    
    # Verify
    rows = original_fetch_all("SELECT * FROM classes WHERE class_uid = %s", (MOCK_CLASS["class_uid"],))
    assert len(rows) == 1

@patch("app.storage.metadata_db._fetch_all", side_effect=fake_fetch_all)
@patch("app.modules.dataset.catalog._load_all_labels_unscoped")
@patch("app.modules.dataset.samples._load_all_samples_unscoped")
@patch("app.modules.dataset.raw_uploads.list_raw_uploads")
def test_sync_soft_delete_safety(mock_raw, mock_samples, mock_labels, mock_fetch):
    """Test 3: Sync shouldn't overwrite deleted_at for existing records."""
    mock_labels.return_value = [MOCK_CLASS]
    mock_samples.return_value = []
    mock_raw.return_value = []
    
    # 1. Insert first
    sync_missing_data_on_startup()
    
    # 2. Simulate soft delete by user
    _execute("UPDATE classes SET deleted_at = NOW() WHERE class_uid = %s", (MOCK_CLASS["class_uid"],))
    
    # 3. Modify the mock data slightly to trigger an UPSERT update
    MOCK_CLASS_MODIFIED = dict(MOCK_CLASS)
    MOCK_CLASS_MODIFIED["slug"] = "test-slug-updated"
    mock_labels.return_value = [MOCK_CLASS_MODIFIED]
    
    # 4. A full sync propagates edits while the upsert still preserves deleted_at.
    # The normal keyset sync deliberately writes missing rows only.
    sync_missing_data_on_startup(full=True)
    
    # 5. Verify deleted_at is NOT NULL
    rows = original_fetch_all("SELECT slug, deleted_at FROM classes WHERE class_uid = %s", (MOCK_CLASS["class_uid"],))
    assert len(rows) == 1
    assert rows[0]["slug"] == "test-slug-updated"
    assert rows[0]["deleted_at"] is not None
