# Label Deletion & Update Implementation - Complete Guide

## Overview
This document outlines the complete implementation of the label deletion and update functionality with proper synchronization across local files, databases, and Google Drive.

## Key Features Implemented

### 1. **Atomic Label Deletion** ✓
- Deletes class from local `labels.csv`
- Removes all associated samples from `samples.csv`
- Removes all associated raw uploads from `raw_uploads.csv`
- Deletes from PostgreSQL database
- All operations are locked with file-level synchronization

### 2. **Google Drive Synchronization** ✓
- **Folder Deletion**: Removes class feature folders and raw video folders from Drive
- **CSV Sync**: Updates all four CSV files:
  - `labels.csv` (local + Drive)
  - `samples.csv` (local + Drive)
  - `raw_uploads.csv` (local + Drive)
  - **NEW**: `labels2.0.csv` (Drive versioned)
  - **NEW**: `samples2.0.csv` (Drive versioned)

### 3. **Comprehensive Logging** ✓
- Structured logging with operation tracking via `app/logging_utils.py`
- Log format: `[OPERATION][STATUS] key=value ... duration_ms=X`
- All operations tracked: CLASS_DELETE, CLASS_UPDATE, CATALOG_ROLLBACK
- Debug logs for Drive operations

### 4. **Error Handling & Rollback** ✓
- Backup system: All deletions create temporary backups in `/tmp/catalog_sync_*`
- Automatic rollback on any failure:
  - Restores local CSVs
  - Restores database records
  - Restores Drive folders
  - Restores versioned CSVs
- Lock mechanism prevents concurrent modifications

### 5. **Enhanced Frontend Response** ✓
- Returns detailed messages in Vietnamese
- Includes deletion statistics (samples count, raw uploads count)
- Proper error messages with error codes
- Sample message: "Nhãn được xóa thành công. Đã xóa 5 mẫu và 3 video gốc."

## Backend Changes

### 1. **catalog_sync.py** (Lines 179-211)
**New Functions Added:**
```python
def _sync_drive_versioned_csv(local_path: Path, drive_file_name: str) -> None
    """Sync versioned CSV files (labels2.0.csv, samples2.0.csv) to Drive"""
    
def _sync_drive_versioned_csvs() -> None
    """Sync both labels2.0.csv and samples2.0.csv to Drive"""
```

**Modified sync_delete_class():**
- Added versioned CSV sync after regular catalog sync
- Enhanced logging with detailed Drive operations
- Improved rollback to restore versioned CSVs

**Modified sync_update_class():**
- Added versioned CSV sync after update
- Improved error handling for Drive operations

### 2. **routers/classes.py** (Lines 59-76)
**Enhanced Response Structure:**
```python
# DELETE Response (Success)
{
    "success": true,
    "message": "Nhãn được xóa thành công. Đã xóa 5 mẫu và 3 video gốc.",
    "deleted": true,
    "class_uid": "uuid...",
    "class_idx": 1,
    "sample_count": 5,
    "raw_upload_count": 3
}

# DELETE Response (Failure)
{
    "success": false,
    "message": "Lỗi xóa nhãn: Class not found",
    "error_code": "CLASS_NOT_FOUND"
}
```

## Frontend Changes

### 1. **api/dataset.ts** (Lines 187-208)
**Updated deleteClass():**
- Now extracts and returns message from backend
- Includes deletion statistics
- Proper error message handling

### 2. **pages/LabelsPage.tsx** (Lines 290-312)
**Enhanced confirmDelete():**
- Uses backend message if available
- Displays detailed deletion statistics
- Better error reporting

**Updated saveEdit():**
- Shows backend message for updates
- Improved user feedback

## File Structure
```
dataset/
├── labels.csv              (Local master labels)
├── samples.csv             (Local samples)
├── raw_uploads.csv         (Local raw uploads)
└── labels/
    ├── labels_language.csv
    └── labels_dialect.csv

# On Google Drive (signbridge-storage):
├── labels.csv              (Synced from local)
├── samples.csv             (Synced from local)
├── raw_uploads.csv         (Synced from local)
├── labels2.0.csv           (Versioned - synced on every change)
├── samples2.0.csv          (Versioned - synced on every change)
└── features/               (Feature folders, synced on updates)
    └── vn/
        └── ...
```

## Database Synchronization
- PostgreSQL tables updated via `app/storage/metadata_db.py`
- Functions used:
  - `db_delete_class(class_uid)`
  - `db_delete_samples_by_class(class_uid)`
  - `db_delete_raw_uploads_by_class(class_uid)`

## Error Codes
| Code | Meaning | HTTP Status |
|------|---------|------------|
| CLASS_NOT_FOUND | Class doesn't exist | 404 |
| CLASS_CONFLICT | Duplicate class name | 409 |
| CLASS_PATH_CONFLICT | Path already exists | 409 |
| CATALOG_SYNC_FAILED | General sync error | 500 |
| CATALOG_ROLLBACK_FAILED | Rollback failed | 500 |

## Logging Example
```
[2026-05-18T10:30:45.123Z] INFO [catalog.sync] [CLASS_DELETE][START] op_id=class_delete_1 duration_ms=0
[2026-05-18T10:30:45.234Z] INFO [CATALOG][GDRIVE] class delete sync begin: class_uid=abc123 feature=dataset/features/vn/test raw=dataset/raw_videos/vn/...
[2026-05-18T10:30:45.456Z] INFO [CATALOG][GDRIVE] class delete sync done: class_uid=abc123
[2026-05-18T10:30:45.567Z] INFO [CATALOG][GDRIVE] syncing versioned CSVs after delete for class_uid=abc123
[2026-05-18T10:30:45.678Z] INFO [CATALOG][GDRIVE] versioned CSVs synced successfully for class_uid=abc123
[2026-05-18T10:30:45.789Z] INFO [catalog.sync] [CLASS_DELETE][SUCCESS] class_idx=1 class_uid=abc123 sample_count=5 raw_upload_count=3 duration_ms=666
```

## Testing

### Test Script Location
`backend/test_delete_class.py`

### Usage
```bash
cd backend
python test_delete_class.py --test all
python test_delete_class.py --test delete
python test_delete_class.py --test update
```

### What It Tests
1. Lists current classes
2. Verifies deletion of the last class
3. Checks local CSV updates
4. Confirms database cleanup
5. Validates no lingering records

## API Endpoints

### DELETE /classes/{class_ref}
- **class_ref**: Can be class_idx (number) or class_uid (UUID)
- **Response**: Full class metadata with deletion stats
- **Example**:
  ```bash
  curl -X DELETE http://localhost:8000/classes/1
  # Returns deletion statistics
  ```

### PUT /classes/{class_ref}
- **Payload**: Fields to update (label_original, language, dialect, etc.)
- **Response**: Updated class metadata with message
- **Example**:
  ```bash
  curl -X PUT http://localhost:8000/classes/1 \
    -H "Content-Type: application/json" \
    -d '{"label_original": "New Label", "dialect": "bac"}'
  ```

## Troubleshooting

### Issue: "Label not found" error
- Check if class_idx or class_uid is correct
- Verify the class exists in `dataset/labels.csv`

### Issue: Google Drive sync fails
- Check `.env` contains valid `GOOGLE_DRIVE_CREDENTIALS`
- Verify `gdrive/credentials.json` exists and is valid
- Check network connectivity

### Issue: Rollback needed
- Check logs for `[CATALOG][ROLLBACK]` entries
- Manual restore from `/tmp/catalog_sync_*` if needed

## Performance Considerations
- File locking ensures atomic operations
- CSV rewrites are buffered and flushed to disk
- Drive operations are sequential (not parallel)
- Typical deletion takes 2-5 seconds (including Drive sync)

## Security Notes
- Class deletion is permanent after Drive sync completes
- Backups are temporary (removed after operation)
- No audit trail of deleted classes (consider adding if needed)
- Drive permissions required: Can delete folders in signbridge-storage

## Next Steps / Future Improvements
1. Add soft-delete with recovery window
2. Implement batch operations for multiple class deletions
3. Add deletion audit trail/activity log
4. Consider archiving deleted classes instead of permanent deletion
5. Add metrics/monitoring for sync operations
