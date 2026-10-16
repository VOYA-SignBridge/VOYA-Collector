"""Tests for Disk Watermark (Backpressure) in sync_tasks.

Uses Mock patching exclusively — no real DB, no real filesystem, no real GDrive.
Follows the same State-Based Testing methodology as the existing test_sync_tasks.py.
"""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from collections import namedtuple

from app.sync_tasks import (
    download_missing_files_to_local,
    _disk_over_watermark,
    DISK_HIGH_WATERMARK,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])

MOCK_SAMPLE = {
    "sample_uid": "wm-test-001",
    "file_path": "wm_test.npz",
    "storage_url": "gdrive://wm-mock-id",
}


@pytest.fixture
def mock_db_conn():
    """Mock the DB connection — identical pattern to test_sync_tasks.py."""
    with patch("app.sync_tasks.connect_postgres") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
        mock_connect.return_value = mock_conn
        yield mock_cursor


# ===== TC 3.1: Normal path — disk is at 50%, download proceeds =====

@patch("app.sync_tasks.shutil.disk_usage")
@patch("app.sync_tasks.download_from_gdrive")
@patch("app.sync_tasks._is_present")
def test_watermark_normal_disk_allows_download(
    mock_is_present, mock_download, mock_disk_usage, mock_db_conn
):
    """TC 3.1: Disk at 50% → download proceeds normally."""
    # 100 GB total, 50 GB used
    mock_disk_usage.return_value = DiskUsage(
        total=100_000_000_000, used=50_000_000_000, free=50_000_000_000
    )
    mock_is_present.return_value = False
    mock_db_conn.fetchall.side_effect = [[MOCK_SAMPLE], []]

    result = download_missing_files_to_local.apply().get()

    assert mock_download.call_count == 1
    assert result["downloaded"] == 1
    assert result["disk_stopped"] is False
    assert result["status"] == "completed"


# ===== TC 3.2: Watermark breach — disk at 96%, download blocked =====

@patch("app.sync_tasks.shutil.disk_usage")
@patch("app.sync_tasks.download_from_gdrive")
@patch("app.sync_tasks._is_present")
def test_watermark_breach_stops_download(
    mock_is_present, mock_download, mock_disk_usage, mock_db_conn
):
    """TC 3.2: Disk at 96% ≥ 95% → download_from_gdrive must NOT be called."""
    # 100 GB total, 96 GB used → 96% > DISK_HIGH_WATERMARK (95%)
    mock_disk_usage.return_value = DiskUsage(
        total=100_000_000_000, used=96_000_000_000, free=4_000_000_000
    )
    mock_is_present.return_value = False
    mock_db_conn.fetchall.side_effect = [[MOCK_SAMPLE], []]

    result = download_missing_files_to_local.apply().get()

    # Must NOT have attempted any download
    assert mock_download.call_count == 0
    assert result["disk_stopped"] is True
    assert result["status"] == "stopped_disk_full"


# ===== TC 3.3: OSError edge case — disk_usage raises, treated as "over" =====

@patch("app.sync_tasks.shutil.disk_usage")
@patch("app.sync_tasks.download_from_gdrive")
@patch("app.sync_tasks._is_present")
def test_watermark_oserror_treated_as_over(
    mock_is_present, mock_download, mock_disk_usage, mock_db_conn
):
    """TC 3.3: shutil.disk_usage raises OSError (e.g. unmounted volume).

    The system must NOT crash the Celery worker. Instead it should treat the
    disk as 'over watermark' and skip downloads safely.
    """
    mock_disk_usage.side_effect = OSError("No such file or directory: '/dataset'")
    mock_is_present.return_value = False
    mock_db_conn.fetchall.side_effect = [[MOCK_SAMPLE], []]

    result = download_missing_files_to_local.apply().get()

    # Must NOT crash, and must NOT have downloaded anything
    assert mock_download.call_count == 0
    assert result["disk_stopped"] is True
    assert result["status"] == "stopped_disk_full"


# ---------------------------------------------------------------------------
# Một ngưỡng, một nguồn
#
# Trước 2026-08-09 cùng một ngưỡng sống ở ba nơi với ba giá trị: 85 trong
# `monitoring.DISK_WARN_PCT`, 0.95 trong `sync_tasks.DISK_HIGH_WATERMARK`, và
# một phép trừ `watermark - 5` = 90 trong `cli/verify_deployment.py`. Bảng quản
# trị cảnh báo ở 85 trong khi kiểm tra sau triển khai im lặng tới 90, và không
# ai sửa được cả ba cùng lúc.
# ---------------------------------------------------------------------------

def test_backpressure_dung_chung_con_so_voi_bang_quan_tri():
    from app.monitoring import DISK_CRIT_PCT

    assert DISK_HIGH_WATERMARK == DISK_CRIT_PCT / 100.0


def test_canh_bao_thap_hon_nguong_chan():
    """Cảnh báo phải đến TRƯỚC lúc chặn, nếu không nó chỉ là một thông báo tang lễ."""
    from app.monitoring import DISK_CRIT_PCT, DISK_WARN_PCT

    assert DISK_WARN_PCT < DISK_CRIT_PCT


def test_hai_con_so_dung_nhu_nguoi_dung_chon():
    """85 / 95 — người dùng chốt ngày 2026-08-09. Ghim lại để một lần 'dọn dẹp'
    sau này không lặng lẽ đổi chính sách."""
    from app.monitoring import DISK_CRIT_PCT, DISK_WARN_PCT

    assert (DISK_WARN_PCT, DISK_CRIT_PCT) == (85, 95)
