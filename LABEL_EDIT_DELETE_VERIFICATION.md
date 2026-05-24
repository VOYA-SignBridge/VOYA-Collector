# Cập nhật chức năng chỉnh sửa/xóa nhãn - Kiểm tra hoàn chỉnh

## ✅ Cấu hình Backend (không hardcode - sử dụng .env)

### 1. **backend/app/config.py** - Config Settings
- `google_sheets_labels_spreadsheet_id`: Từ env `GOOGLE_SHEETS_LABELS_SPREADSHEET_ID`
- `google_sheets_labels_sheet_gid`: Từ env `GOOGLE_SHEETS_LABELS_SHEET_GID`
- `google_sheets_samples_spreadsheet_id`: Từ env `GOOGLE_SHEETS_SAMPLES_SPREADSHEET_ID`
- `google_sheets_samples_sheet_gid`: Từ env `GOOGLE_SHEETS_SAMPLES_SHEET_GID`

### 2. **backend/app/catalog_sync.py** - Transactional Sync
- ✅ `sync_update_class()`: Cập nhật nhãn + sync Drive + Google Sheets
- ✅ `sync_delete_class()`: Xóa nhãn + xóa Drive + Google Sheets
- ✅ `_sync_drive_and_sheets_versioned_tables()`: Đồng bộ cả Drive và Sheets trong 1 transaction
- ✅ Chỉ sync: `labels2.0.csv` và `samples2.0.csv` (KHÔNG động đến `labels.csv` / `samples.csv`)
- ✅ Tự động rollback nếu Sheets hoặc Drive sync thất bại
- ✅ Trả về `op_id` và `operation_logs` trong response

### 3. **backend/app/storage/gdrive_client.py** - Google Sheets Support
- ✅ SCOPES bao gồm: `'https://www.googleapis.com/auth/spreadsheets'`
- ✅ Phương thức: `get_sheets_service()` - tạo Sheets service
- ✅ Phương thức: `replace_sheet_values()` - cập nhật Sheets

### 4. **backend/app/routers/classes.py & dataset.py**
- ✅ Trả về `op_id` và `operation_logs` trong response của update/delete

## ✅ Cấu hình Frontend (không hardcode - nhận từ backend)

### 1. **frontend/src/api/dataset.ts**
- ✅ `updateClass()`: Nhận và trả lại `op_id`, `operation_logs` từ backend
- ✅ `deleteClass()`: Nhận `op_id`, `operation_logs` từ backend response

### 2. **frontend/src/pages/LabelsPage.tsx**
- ✅ Helper `extractOperationLogs()`: Trích xuất logs từ response
- ✅ Helper `extractMessage()`: Trích xuất message từ response
- ✅ Hiển thị logs trong UI khi update/delete thành công hoặc thất bại

## ✅ Cấu hình .env - Đầy đủ & Chính xác

```
GOOGLE_SHEETS_LABELS_SPREADSHEET_ID=1ulsPQ1qDe31Y8cHKQwx_KPrq-BA2eZenRf-LLq74QkY
GOOGLE_SHEETS_LABELS_SHEET_GID=1266519527
GOOGLE_SHEETS_SAMPLES_SPREADSHEET_ID=1f3xv2_X13Vmj63DwgP3YXFp3vmQV-kSHq5G_lvWIls0
GOOGLE_SHEETS_SAMPLES_SHEET_GID=580985092
GOOGLE_SHEETS_API_KEY=AIzaSyCBpNAkr-Bc36HNVXuM4uhW0AO0riGbvD8

GOOGLE_DRIVE_CREDENTIALS=/gdrive/credentials.json
GOOGLE_DRIVE_TOKEN=/gdrive/token.json
```

## ✅ Quy trình Transactional

### Khi cập nhật nhãn (update):
1. ✅ Backup thư mục cũ (local snapshot)
2. ✅ Cập nhật thư mục local từ `old_path` → `new_path`
3. ✅ Cập nhật CSV local (labels.csv, samples.csv)
4. ✅ Cập nhật Postgres metadata DB
5. ✅ Sync Drive: di chuyển `old_path` → `new_path` trên Drive
6. ✅ Sync Google Sheets: cập nhật `labels2.0` + `samples2.0` sheets
7. ✅ Nếu Step 5 hoặc 6 thất bại → **Tự động rollback từ backup**

### Khi xóa nhãn (delete):
1. ✅ Backup thư mục (local snapshot)
2. ✅ Xóa từ thư mục local
3. ✅ Cập nhật CSV local (loại bỏ hàng)
4. ✅ Xóa từ Postgres DB
5. ✅ Xóa Drive: xóa thư mục trên Drive
6. ✅ Sync Google Sheets: cập nhật `labels2.0` + `samples2.0` sheets (loại bỏ hàng)
7. ✅ Nếu Step 5 hoặc 6 thất bại → **Tự động rollback từ backup**

## ✅ Kết quả hiển thị cho User

### Thành công:
```json
{
  "deleted": true,
  "class_uid": "...",
  "class_idx": 1,
  "sample_count": 5,
  "raw_upload_count": 2,
  "op_id": "class_delete_1",
  "operation_logs": [
    "class delete sync begin: class_uid=... feature=... raw=...",
    "drive delete completed for class_uid=...",
    "syncing versioned outputs after delete for class_uid=...",
    "versioned outputs synced successfully for class_uid=..."
  ]
}
```

### Frontend UI hiển thị:
- ✅ Toast message: "Đã xóa nhãn #1 và đồng bộ dữ liệu liên quan."
- ✅ Chi tiết logs trong phần "Hoạt động (logs)"

## ✅ Tóm tắt Kiểm tra

| Thành phần | Trạng thái | Ghi chú |
|-----------|-----------|---------|
| Config từ .env | ✅ | Không hardcode, sử dụng settings |
| Backend update/delete | ✅ | Transactional, có rollback |
| Drive sync (versioned CSV) | ✅ | Chỉ `2.0.csv`, không động labels.csv |
| Google Sheets sync | ✅ | Cập nhật trong 1 transaction |
| Operation logs | ✅ | Thu thập, trả về frontend |
| Frontend UI | ✅ | Hiển thị logs + success/error messages |
| Google Drive Auth | ✅ | Scopes bao gồm Sheets |

**Kết luận**: Tất cả chức năng edit/delete nhãn đã được cập nhật hoàn chỉnh, cấu hình từ .env không hardcode, và hỗ trợ transactional sync với Google Sheets + Drive.
