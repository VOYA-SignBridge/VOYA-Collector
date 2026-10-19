# Công cụ migration

Đây là nhóm cần thận trọng nhất: các script có thể ghi lại CSV hoặc di chuyển
file dataset. Luôn chạy dry-run trước và kiểm tra backup/output.

| File | Chức năng | Chế độ an toàn |
|---|---|---|
| `apply_signer_merges.py` | Áp dụng quyết định gộp signer vào registry và mapping legacy | Dry-run mặc định; chỉ ghi khi có `--confirm` |
| `cleanup_legacy_features.py` | Xóa các thư mục `class_*` theo cấu trúc dataset cũ | Chỉ xóa khi có `--delete` |
| `dialect_mapping_reclassifier.py` | Phân loại lại class/sample theo file mapping phương ngữ | Chỉ ghi khi có `--apply` và không có `--dry-run` |
| `dialect_reclassifier.py` | Audit và di chuyển thư mục class sai tầng phương ngữ | Chỉ di chuyển khi có `--apply` |
| `feature_structure_audit.py` | Phát hiện feature folder theo cấu trúc legacy hoặc đặt sai tầng | Chỉ đọc |
| `global_common_promoter.py` | Tìm hoặc promote class dùng chung nhiều ngôn ngữ | Chỉ copy khi có `--promote`; hỗ trợ `--dry-run` |
| `migrate_legacy_vocabulary_schema.py` | Nâng labels/signers/catalog cũ sang vocabulary schema mới | Hỗ trợ `--dry-run` và tạo backup trước khi ghi |
| `quarantine_files.py` | Di chuyển những file đã được quyết định là `quarantine` ra khỏi feature tree | Dry-run mặc định; chỉ move khi có `--confirm` |

Không chạy các script này trên bản dataset duy nhất. Với dataset đang dùng
chung, hãy tạo bản sao/staging hoặc backup trước.

Luôn chạy từ root repository, ví dụ:

```powershell
python scripts/migration/feature_structure_audit.py --help
python scripts/migration/dialect_reclassifier.py --help
```

