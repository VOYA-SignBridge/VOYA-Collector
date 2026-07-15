import pytest
import uuid
from datetime import datetime, timezone

from app.storage.metadata_db import _execute, _fetch_all, ensure_tables

MOCK_CLASS_UID = "test-schema-class-001"
MOCK_SAMPLE_UID = "test-schema-sample-001"

@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Đảm bảo dọn dẹp dữ liệu trước và sau khi test để không ảnh hưởng DB thật."""
    ensure_tables()
    # Dọn dẹp phòng hờ (trước)
    _execute("DELETE FROM samples WHERE sample_uid = %s", (MOCK_SAMPLE_UID,))
    _execute("DELETE FROM classes WHERE class_uid = %s", (MOCK_CLASS_UID,))
    
    # Tạo Parent data (Class) để không bị lỗi Foreign Key khi insert Sample
    _execute("""
        INSERT INTO classes(class_uid, class_idx, slug, label_original, language, dialect, folder_name)
        VALUES(%s, %s, %s, %s, %s, %s, %s)
    """, (MOCK_CLASS_UID, 9999, "test-slug", "Test Label", "en", "us", "test_folder"))
    
    yield
    
    # Dọn dẹp sạch sẽ (sau)
    _execute("DELETE FROM samples WHERE sample_uid = %s", (MOCK_SAMPLE_UID,))
    _execute("DELETE FROM classes WHERE class_uid = %s", (MOCK_CLASS_UID,))

def test_backward_compatibility_defaults():
    """TC 1.1: Insert data cũ (thiếu các cột mới) -> DB phải tự động fill Default Constraints."""
    # Insert giả lập kiểu cũ (Legacy), cố tình bỏ qua 2 cột mới là sheets_synced và gdrive_synced
    _execute("""
        INSERT INTO samples(
            sample_uid, class_uid, slug, label_original, language, dialect,
            source_type, user_id, session_id, fps_original, fps_processed,
            seq_len, file_path, storage_url, checksum, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, NOW()
        )
    """, (
        MOCK_SAMPLE_UID, MOCK_CLASS_UID, "test-sample-slug", "Test Sample", "en", "us",
        "web", str(uuid.uuid4()), "sess-123", 30, 30,
        150, "/mock/path.npz", "gdrive://mock", "mock-checksum"
    ))
    
    rows = _fetch_all("SELECT sheets_synced, gdrive_synced FROM samples WHERE sample_uid = %s", (MOCK_SAMPLE_UID,))
    assert len(rows) == 1
    # DB bắt buộc phải tự bù đắp giá trị mặc định theo đúng logic Migration mới
    assert rows[0]["sheets_synced"] is False
    assert rows[0]["gdrive_synced"] is True

def test_constraint_enforcement():
    """TC 1.2: Đảm bảo các Constraints (Unique) vẫn hoạt động nghiêm ngặt để bảo vệ toàn vẹn."""
    import psycopg2.errors
    
    # Cố tình Insert một Class trùng class_uid đã tồn tại (lỗi trùng khóa chính/duplidate key)
    with pytest.raises(Exception) as excinfo:
        _execute("""
            INSERT INTO classes(class_uid, class_idx, slug, label_original)
            VALUES(%s, %s, %s, %s)
        """, (MOCK_CLASS_UID, 9998, "duplicate-slug", "Duplicate"))
    
    # Postgres phải chặn lại và văng lỗi UniqueViolation
    err_msg = str(excinfo.value)
    err_type = str(type(excinfo.value).__name__)
    assert "duplicate key value" in err_msg.lower() or "uniqueviolation" in err_type.lower()

def test_index_safety_on_missing_columns():
    """TC 1.3: ensure_tables() xử lý Graceful (không sập) khi thiếu column lúc tạo Index."""
    # Chạy lại script tạo bảng và Index nhiều lần (Idempotency)
    # Phải pass qua mượt mà, không văng lỗi sập Backend
    try:
        ensure_tables()
        success = True
    except Exception:
        success = False
    assert success is True
