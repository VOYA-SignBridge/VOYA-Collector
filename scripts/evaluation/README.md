# Công cụ evaluation và báo cáo

Nhóm này đọc checkpoint/result đã có để tính metric, kiểm tra độ tin cậy và tạo
bảng/biểu đồ. Chúng không phải unit test của backend, dù một số file có chữ
`test` vì chúng kiểm tra artifact nghiên cứu.

| File | Chức năng chính |
|---|---|
| `aggregate_experiment_results.py` | Gom các run hợp lệ thành bảng CSV/LaTeX và loại run không đạt research validity |
| `audit_checkpoint_validity.py` | Quét checkpoint, áp dụng tiêu chí C1–C14 và phân loại valid/invalid/unverifiable |
| `budget_z_statistics.py` | Tính paired-z cho các cấu hình có cùng ngân sách dữ liệu |
| `compute_baselines.py` | Tính baseline đơn giản trên các fold để so với mô hình học sâu |
| `compute_pooled_confusion.py` | Gộp confusion matrix từ nhiều fold/checkpoint |
| `make_fig_budget16.py` | Vẽ biểu đồ reallocation từ kết quả paired-z |
| `make_ldm_dot.py` | Đọc schema PostgreSQL và sinh sơ đồ quan hệ dạng DOT |
| `summarize_budget_grid.py` | Tóm tắt grid-search theo ngân sách |
| `summarize_loso_results.py` | Tóm tắt kết quả LOSO và khoảng tin cậy |
| `test_research_validity_fault_injection.py` | Cố tình làm hỏng metadata/checkpoint để kiểm tra validity gate có phát hiện không |
| `variance_decomposition.py` | Phân rã phương sai theo người ký, kiến trúc và seed |

Nhóm này thường ghi file vào `reports/` nhưng không sửa dataset. Một số script
phụ thuộc vào artifact nghiên cứu cụ thể; nếu artifact không tồn tại, script
nên báo thiếu đầu vào thay vì tự tạo dữ liệu giả.

