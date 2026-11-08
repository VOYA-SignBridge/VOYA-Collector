# Scripts

Chạy các lệnh từ thư mục gốc của repository.

| Thư mục | Mục đích | Tính chất |
|---|---|---|
| `dataset/` | Kiểm tra dataset, tạo/kiểm tra manifest và báo cáo chất lượng | Chủ yếu chỉ đọc |
| `training/` | Tạo split, chạy thí nghiệm và kiểm tra training artifact | Có thể tạo output/checkpoint |
| `evaluation/` | Tổng hợp kết quả, thống kê và tạo biểu đồ/báo cáo | Đọc output, ghi report |
| `migration/` | Chuyển schema, merge signer và quarantine file | Có thể sửa/move dữ liệu; ưu tiên dry-run |
| `maintenance/` | Khởi tạo database và làm mới token Drive | Công cụ vận hành |

Các file ở ngay `scripts/` là thành phần dùng chung hoặc orchestrator:

- `_console.py`: chuẩn hóa UTF-8 khi chạy trên Windows.
- `research_validity.py`: logic đánh giá research validity dùng chung cho backend và evaluation.
- `prepare_research_release.py`: điều phối nhiều bước tạo research release.

Ví dụ:

```powershell
python scripts/dataset/create_dataset_manifest.py --help
python scripts/training/verify_determinism.py --help
python scripts/migration/quarantine_files.py  # dry-run mặc định
```

