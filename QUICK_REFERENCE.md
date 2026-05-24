# Quick Reference - Label Deletion & Update System

## 🎯 What's Changed

### Backend ✅
```python
# NEW FUNCTIONS (catalog_sync.py)
def _sync_drive_versioned_csv(local_path, drive_file_name)
def _sync_drive_versioned_csvs()

# ENHANCED (routers/classes.py)
@router.delete("/{class_ref}")
def delete_class(class_ref: str):
    # Returns: {success, message with stats, deleted, class_uid, class_idx, sample_count, raw_upload_count}

@router.put("/{class_ref}")
def update_class(class_ref: str, payload: dict):
    # Returns: {success, message, ...result}
```

### Frontend ✅
```typescript
// UPDATED (api/dataset.ts)
export const deleteClass() -> Promise<Result<{
  message: string
  deleted: boolean
  class_uid: string
  class_idx: number
  sample_count: number
  raw_upload_count: number
}>>

// ENHANCED (pages/LabelsPage.tsx)
confirmDelete() - Uses backend message
saveEdit() - Uses backend message
```

## 📊 Response Examples

### Success Response
```json
{
  "success": true,
  "message": "Nhãn được xóa thành công. Đã xóa 5 mẫu và 3 video gốc.",
  "deleted": true,
  "class_uid": "abc-123-def-456",
  "class_idx": 1,
  "sample_count": 5,
  "raw_upload_count": 3
}
```

### Error Response
```json
{
  "success": false,
  "message": "Lỗi xóa nhãn: Class not found",
  "error_code": "CLASS_NOT_FOUND"
}
```

## 🔄 Sync Chain
```
Label Deletion
  ↓
Local Files (labels.csv, samples.csv, raw_uploads.csv)
  ↓
PostgreSQL Database
  ↓
Google Drive (labels.csv, samples.csv, raw_uploads.csv)
  ↓
Google Drive Versioned (NEW! labels2.0.csv, samples2.0.csv)
  ↓
Folders Deleted (features + raw_videos)
  ↓
Success Message to Frontend
```

## 📝 Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `backend/app/catalog_sync.py` | Added versioned CSV sync | 179-211, 806-820, 840-844 |
| `backend/app/routers/classes.py` | Better responses | 59-76 |
| `frontend/src/api/dataset.ts` | Extract stats | 187-208 |
| `frontend/src/pages/LabelsPage.tsx` | Use backend message | 264-298, 290-312 |

## 🚀 How to Deploy

1. **Backend**
```bash
cd backend
# No dependencies to install - uses existing imports
# Restart FastAPI app
```

2. **Frontend**
```bash
cd frontend
npm run build  # or docker compose up --build
```

3. **Docker**
```bash
docker compose up -d --build
```

## ✅ Validation Commands

```bash
# Check backend syntax
python -m py_compile backend/app/catalog_sync.py
python -m py_compile backend/app/routers/classes.py

# Test deletion
python backend/test_delete_class.py --test delete

# Test update
python backend/test_delete_class.py --test update

# API test
curl -X DELETE http://localhost:8000/classes/1
```

## 📋 Checklist for Verification

- [ ] Backend starts without errors
- [ ] Frontend builds successfully
- [ ] Can delete a label via API
- [ ] Success message shows statistics
- [ ] Google Drive files are synced
- [ ] Database records deleted
- [ ] Versioned CSVs updated
- [ ] Error messages appear on failure
- [ ] Rollback works (check logs)

## 🔍 Troubleshooting

| Issue | Fix |
|-------|-----|
| "Versioned CSV sync failed" | Check Google Drive credentials |
| Empty sample_count/raw_upload_count | Verify data exists in CSVs |
| No success message | Update frontend with latest code |
| Class still in database | Check database sync logs |

## 📚 Full Documentation

- `IMPLEMENTATION_GUIDE.md` - Complete technical details
- `COMPLETION_SUMMARY.md` - What was accomplished
- `backend/test_delete_class.py` - Test script
- Logs: Check `[CLASS_DELETE][SUCCESS]` messages

## 🎉 Summary

✅ Label deletion now syncs to Google Drive immediately  
✅ Both local and versioned CSVs updated  
✅ Detailed success/failure messages  
✅ Statistics included (samples, raw uploads)  
✅ Full rollback on any error  
✅ Comprehensive logging  
✅ Vietnamese messages for Vietnamese-speaking users
