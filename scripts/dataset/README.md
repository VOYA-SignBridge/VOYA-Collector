# Công cụ dataset

Thư mục này chứa các công cụ kiểm tra và mô tả dataset. Phần lớn là công cụ
chỉ đọc; ngoại lệ là `create_dataset_manifest.py`, vì nó tạo các file manifest
mới trong `dataset/manifests/`.

## Ai sử dụng?

- Lập trình viên/người phụ trách dữ liệu chạy thủ công từ root repository.
- `backend/app/dataset_prep_tasks.py` gọi `create_dataset_manifest.py` và
  `validate_dataset_manifest.py` qua Celery.
- `scripts/prepare_research_release.py` gọi các bước pilot, duplicate, create
  và validate theo đúng thứ tự.

## Các file

| File | Làm gì? | Đọc | Ghi/thay đổi |
|---|---|---|---|
| `audit_duplicate_samples.py` | Tìm file trùng byte, trùng nội dung hoặc gần giống trong cùng một class | NPZ, manifest tùy chọn | Chỉ ghi báo cáo, không xóa mẫu |
| `audit_gdrive_sample_links.py` | Đối chiếu NPZ local với `storage_url` trên Drive để phát hiện URL trỏ nhầm file | PostgreSQL, Drive, NPZ local | Ghi báo cáo; có thể tải file tạm để so sánh |
| `audit_handedness_flips.py` | Phát hiện bàn tay bị nhảy giữa slot trái/phải trong chuỗi landmark | NPZ và manifest | Ghi báo cáo, không sửa NPZ |
| `create_dataset_manifest.py` | Chụp một “danh sách phiên bản” bất biến của các mẫu được dùng | Feature, labels, sidecar, signer mapping | Tạo manifest, checksum, snapshot labels/signers và thống kê |
| `import_community_export.py` | Đối chiếu bản tải `Community` từ Drive với catalog XLSX rồi ánh xạ `Samples`/`Videos` vào layout local | `Community/Lookup list`, NPZ, video | Mặc định dry-run; `--apply` copy nguyên tử vào `dataset/`, không sửa nguồn |
| `oversample_balance.py` | Lập kế hoạch hoặc tạo thêm mẫu augment để cân bằng class | Catalog, NPZ | Mặc định chỉ in kế hoạch; chỉ tạo NPZ khi có `--apply` |
| `report_dataset_coverage.py` | Thống kê độ phủ theo label, signer, session và profile | Manifest đã tạo | In cảnh báo và tùy chọn ghi JSON |
| `report_quality_stats.py` | Tổng hợp accepted/flagged/rejected của quá trình thu thập | `quality_attempts.jsonl` | Ghi báo cáo thống kê |
| `validate_dataset_manifest.py` | Kiểm tra manifest có bị sửa, thiếu file hoặc có orphan | Manifest và feature tree | Không sửa dữ liệu; exit code khác 0 khi lỗi |
| `validate_pilot_samples.py` | Gate chất lượng cho một đợt thu thập trước khi release | NPZ, sidecar, labels, signers | Không sửa dữ liệu; trả PASS/FAIL |

## Cách chạy

Luôn chạy từ root repository:

```powershell
python scripts/dataset/create_dataset_manifest.py --help
python scripts/dataset/validate_dataset_manifest.py --help
python scripts/dataset/oversample_balance.py --help
```

Nhập một bản tải Drive vào máy local: luôn chạy dry-run trước, xem cảnh báo rồi
mới thêm `--apply`. Dữ liệu trong `dataset/` thuộc `.gitignore` và không được
đưa vào commit.

```powershell
python scripts/dataset/import_community_export.py D:\VOYA\Community --include-videos
python scripts/dataset/import_community_export.py D:\VOYA\Community --include-videos --apply
```

Importer từ chối ghi đè catalog hoặc file đã có nội dung khác. File bị di
chuyển trên Drive chỉ được khôi phục về đường dẫn catalog khi basename (và
checksum, nếu catalog có) xác định duy nhất; file ngoài catalog chỉ được báo
cáo, không tự động nhập.

Không chạy `create_dataset_manifest.py` với `--force` trên một phiên bản đã
được dùng để train, vì thao tác đó phá tính bất biến của manifest.

