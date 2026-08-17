import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from app.storage.metadata_db import (
    _execute, _fetch_all as original_fetch_all, ensure_tables
)
from app.db import sync_missing_data_on_startup

# Các test dưới đây vá `_load_all_labels_unscoped`, KHÔNG phải `load_labels`.
#
# Đồng bộ lúc khởi động chạy TRƯỚC khi có bất kỳ ngữ cảnh tổ chức nào, nên nó
# phải đọc toàn kho — đó là lý do `db.sync_missing_data_on_startup` gọi hàm
# không-phạm-vi, và là chủ ý chứ không phải bỏ sót. Vá nhầm sang tên cũ thì bản
# vá trượt trong im lặng: hàm thật vẫn chạy, trả về rỗng, và test đỏ ở khẳng
# định cuối với `assert 0 == 1` — một thông báo không hề trỏ về nguyên nhân.


def _postgres_available() -> bool:
    """Đây là các integration test cần Postgres thật (ensure_tables, ALTER TABLE…).

    Khi chạy ngoài Docker (không có host `postgres`), trước đây cả file TREO vì
    fixture cứ thử kết nối lại. Probe một lần với timeout ngắn: kết nối được thì
    chạy, không thì SKIP cả module (connect_postgres tự bound theo connect_timeout
    và ném ngay khi bị refuse nên probe này kết thúc nhanh).
    """
    try:
        from app.storage.postgres_connection import connect_postgres

        conn = connect_postgres(connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="Postgres không truy cập được — chạy trong Docker: "
    "docker compose exec backend pytest tests/test_startup_sync.py",
)

# Mock data
MOCK_CLASS = {
    "class_uid": "test-sync-class-001",
    "class_idx": 9999,
    "slug": "test-slug",
    "label_original": "Test Label",
    "language": "en",
    "dialect": "us",
    "is_common_global": False,
    "is_common_language": False,
    "folder_name": "test_folder",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "migrated_at": None,
}

@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Ensure tables exist, and any mock data is cleaned up before and after each test (Hard Delete)."""
    ensure_tables()
    # classes.dialect carries a composite FK (tenant_id, dialect) -> dialects.
    # MOCK_CLASS deliberately uses the synthetic en/us pair so it can never
    # collide with real data, which means the dialect does not exist in the
    # registry and the INSERT is rejected before the sync logic under test ever
    # runs. Register it here (and drop it in teardown) so the test exercises the
    # constraint instead of dodging it by borrowing a real dialect.
    _execute(
        "INSERT INTO dialects (tenant_id, dialect_id, display_name, language, status) "
        "VALUES ('default', %s, 'Test (en/us)', %s, 'approved') "
        "ON CONFLICT (tenant_id, dialect_id) DO NOTHING",
        (MOCK_CLASS["dialect"], MOCK_CLASS["language"]),
    )
    _execute("DELETE FROM classes WHERE class_uid = %s", (MOCK_CLASS["class_uid"],))
    yield
    # Teardown logic — classes first, the dialect it references second.
    _execute("DELETE FROM classes WHERE class_uid = %s", (MOCK_CLASS["class_uid"],))
    _execute(
        "DELETE FROM dialects WHERE tenant_id = 'default' AND dialect_id = %s",
        (MOCK_CLASS["dialect"],),
    )

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
@patch("app.dataset_manager._load_all_labels_unscoped")
@patch("app.dataset_samples.list_samples")
@patch("app.raw_uploads.list_raw_uploads")
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
@patch("app.dataset_manager._load_all_labels_unscoped")
@patch("app.dataset_samples.list_samples")
@patch("app.raw_uploads.list_raw_uploads")
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
@patch("app.dataset_manager._load_all_labels_unscoped")
@patch("app.dataset_samples.list_samples")
@patch("app.raw_uploads.list_raw_uploads")
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

    # 4. Sync again (should update the slug but NOT touch deleted_at).
    #
    # full=True is REQUIRED to reach the update path at all: the default sync
    # only inserts rows missing from the DB, because no CSV carries updated_at
    # to compare against, so re-upserting every row on every boot would be a
    # silent overwrite. That makes full resync exactly the dangerous case for
    # deleted_at — which is the property this test exists to pin down.
    sync_missing_data_on_startup(full=True)
    
    # 5. Verify deleted_at is NOT NULL
    rows = original_fetch_all("SELECT slug, deleted_at FROM classes WHERE class_uid = %s", (MOCK_CLASS["class_uid"],))
    assert len(rows) == 1
    assert rows[0]["slug"] == "test-slug-updated"
    assert rows[0]["deleted_at"] is not None

@patch("app.db.sync_missing_data_on_startup")
@patch("app.storage.metadata_db.drop_all_tables")
@patch("app.storage.metadata_db.ensure_tables")
@patch("app.storage.metadata_db._column_exists", return_value=False)
def test_init_db_schema_recovery(mock_col, mock_ensure, mock_drop, mock_sync):
    """When the post-ensure schema check STILL reports a missing column, init_db
    must fall back to the nuclear 'drop_all_tables + rebuild' recovery path.

    We force _column_exists -> False so the schema looks 'still broken' after
    ensure_tables (the real ADD COLUMN IF NOT EXISTS migration would auto-heal
    it, so a real dropped column never reaches this branch). Fully mocked, so the
    test is deterministic and touches no real DB / data.
    """
    from app.db import init_db

    mock_sync.return_value = True  # sync succeeds; the schema check is what fails
    result = init_db()

    assert result is True
    mock_drop.assert_called_once()      # nuclear reset was triggered
    assert mock_ensure.call_count == 2  # ensure_tables ran initially + after drop
