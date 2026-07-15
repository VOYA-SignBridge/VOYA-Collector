import pytest
from unittest.mock import patch, MagicMock

from app.sync_tasks import download_missing_files_to_local

MOCK_SAMPLE_UID_1 = "test-sync-task-sample-001"
MOCK_SAMPLE_UID_2 = "test-sync-task-sample-002"
MOCK_RAW_UID_1 = "test-sync-task-raw-001"

@pytest.fixture
def mock_db_conn():
    """Mock the DB connection to return specific rows and avoid touching real DB."""
    with patch("app.sync_tasks.connect_postgres") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
        mock_connect.return_value = mock_conn
        yield mock_cursor

@patch("app.sync_tasks.download_from_gdrive")
@patch("app.sync_tasks._is_present")
def test_sync_happy_path_file_missing(mock_is_present, mock_download, mock_db_conn):
    """TC 2.1: File missing locally, URL is gdrive://. Should download."""
    # First fetchall() is for samples, second is for raw_uploads
    mock_db_conn.fetchall.side_effect = [
        [{"sample_uid": MOCK_SAMPLE_UID_1, "file_path": "test_file.npz", "storage_url": "gdrive://mock-id"}],
        [] # No raw uploads
    ]
    
    mock_is_present.return_value = False
    
    # Execute the Celery task synchronously
    download_missing_files_to_local.apply()
    
    assert mock_download.call_count == 1
    args, kwargs = mock_download.call_args
    assert args[0] == "gdrive://mock-id"
    assert "test_file.npz" in args[1]


@patch("app.sync_tasks.download_from_gdrive")
@patch("app.sync_tasks._is_present")
def test_sync_skipped_file_exists(mock_is_present, mock_download, mock_db_conn):
    """TC 2.2: File exists locally -> Skipped."""
    mock_db_conn.fetchall.side_effect = [
        [{"sample_uid": MOCK_SAMPLE_UID_1, "file_path": "test_file.npz", "storage_url": "gdrive://mock-id"}],
        []
    ]
    
    # Simulate file is present and size > 0
    mock_is_present.return_value = True
    
    download_missing_files_to_local.apply()
    
    assert mock_download.call_count == 0


@patch("app.sync_tasks.download_from_gdrive")
@patch("app.sync_tasks._is_present")
def test_sync_edge_case_non_gdrive_url(mock_is_present, mock_download, mock_db_conn):
    """TC 2.3: URL is not gdrive:// (e.g. invalid or legacy absolute path). Must not download."""
    mock_db_conn.fetchall.side_effect = [
        [{"sample_uid": MOCK_SAMPLE_UID_1, "file_path": "test_file.npz", "storage_url": "/legacy/path/to/local"}],
        []
    ]
    
    mock_is_present.return_value = False
    download_missing_files_to_local.apply()
    
    assert mock_download.call_count == 0


@patch("app.sync_tasks.download_from_gdrive")
@patch("app.sync_tasks._is_present")
def test_sync_edge_case_gdrive_error(mock_is_present, mock_download, mock_db_conn):
    """TC 2.4: GDrive API Error gracefully handled without breaking the loop."""
    mock_db_conn.fetchall.side_effect = [
        [
            {"sample_uid": MOCK_SAMPLE_UID_1, "file_path": "test_file_1.npz", "storage_url": "gdrive://mock-id-1"},
            {"sample_uid": MOCK_SAMPLE_UID_2, "file_path": "test_file_2.npz", "storage_url": "gdrive://mock-id-2"}
        ],
        []
    ]
    
    mock_is_present.return_value = False
    
    # Make the first download fail, but the second succeed
    def mock_download_side_effect(url, path):
        if "mock-id-1" in url:
            raise Exception("Mock GDrive Exception")
        return True
        
    mock_download.side_effect = mock_download_side_effect
    
    download_missing_files_to_local.apply()
    
    # It should have called download twice despite the first failure
    assert mock_download.call_count == 2


@patch("app.sync_tasks.download_from_gdrive")
@patch("pathlib.Path.exists")
@patch("pathlib.Path.stat")
def test_sync_edge_case_corrupt_local_file(mock_download, mock_exists, mock_stat, mock_db_conn):
    """TC 2.5: File exists locally but is 0 bytes (corrupt). Must redownload."""
    mock_db_conn.fetchall.side_effect = [
        [{"sample_uid": MOCK_SAMPLE_UID_1, "file_path": "test_file.npz", "storage_url": "gdrive://mock-id"}],
        []
    ]
    
    # Do not mock _is_present, mock its underlying dependencies to test its logic
    mock_exists.return_value = True
    
    # Mock stat to return size 0
    mock_stat_result = MagicMock()
    mock_stat_result.st_size = 0
    mock_stat.return_value = mock_stat_result
    
    download_missing_files_to_local.apply()
    
    # It should redownload because size is 0
    assert mock_download.call_count == 1
