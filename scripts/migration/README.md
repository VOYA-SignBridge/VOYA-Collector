# Công cụ migration

Đây là nhóm cần thận trọng nhất: các script có thể ghi lại CSV hoặc di chuyển
file dataset. Luôn chạy dry-run trước và kiểm tra backup/output.

| File | Chức năng | Chế độ an toàn |
|---|---|---|
| `apply_signer_merges.py` | Áp dụng quyết định gộp signer vào registry và mapping legacy | Dry-run mặc định; chỉ ghi khi có `--confirm` |
| `migrate_legacy_vocabulary_schema.py` | Nâng labels/signers/catalog cũ sang vocabulary schema mới | Hỗ trợ `--dry-run` và tạo backup trước khi ghi |
| `quarantine_files.py` | Di chuyển những file đã được quyết định là `quarantine` ra khỏi feature tree | Dry-run mặc định; chỉ move khi có `--confirm` |

Không chạy các script này trên bản dataset duy nhất. Với dataset đang dùng
chung, hãy tạo bản sao/staging hoặc backup trước.

