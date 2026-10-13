# Công cụ maintenance

Các công cụ vận hành môi trường, không phải logic nghiệp vụ của backend.

| File | Chức năng | Khi nào chạy? |
|---|---|---|
| `init-db.ps1` | Khởi tạo database từ Windows PowerShell | Khi dựng database local lần đầu |
| `init-db.sh` | Phiên bản shell cho Linux/container | Khi dựng môi trường Linux |
| `monitor_jobs.py` | Poll trạng thái và metric của một nhóm training job qua backend API | Khi cần quan sát thủ công các job đã biết ID; phải sửa `JOB_IDS` trước khi chạy |
| `refresh_gdrive_token.py` | Đăng nhập OAuth và ghi lại token Drive/Sheets | Khi token local hết hạn hoặc bị thu hồi |

Token và credential là dữ liệu bí mật, phải nằm trong `gdrive/` hoặc đường dẫn
được cấu hình và không được commit lên Git.

