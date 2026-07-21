# Known Issues & Pending Decisions

> Cập nhật 2026-07-19. Mục nào cần quyết định nghiệp vụ thì KHÔNG tự xử lý bằng code.

## Chờ quyết định nghiệp vụ (owner)

| # | Vấn đề | Hành động khi quyết |
|---|---|---|
| 1 | **7 file orphan/invalid** đang `pending` trong `config/orphan_file_decisions.json` (5 npz lớp `vo-tay` không có dòng nhãn; 1 bản copy `sample_d6ef358990(1).npz`; 1 file không có provenance signer) | Sửa `decision` → `quarantine`/`keep`, chạy `python scripts/quarantine_files.py --confirm` |
| 2 | **spa** (2 lớp) chưa gán scope/profile | Sửa `config/legacy_vocabulary_mapping.json` → chạy lại migration → manifest version mới |
| 3 | **can-tho** (40 mẫu, 8 lớp) đã revert về needs_review theo chỉ thị 2026-07-19; đồng thời KHÔNG có signer provenance | Xác nhận profile + xác nhận ai ký (hoặc thu mới) |
| 4 | Mảnh UUID lạc `d70872b4-...` từng dính vào `migrated_at` của lớp `vao-lop` (đã tách ra, lưu tại backup `labels_pre_row41_fix_*`) — có thể là tàn dư một dòng nhãn bị mất (nghi liên quan lớp `vo-tay` mồ côi) | Đối chiếu thủ công nếu muốn khôi phục nhãn vo-tay |

## Giới hạn dữ liệu hiện tại (chặn thí nghiệm)

- **Signer-disjoint**: alphabet bị chặn bởi `vn/alphabet/p` (1 signer); hoa_de chỉ có 2 signer thực sau merge (3 tập cần ≥3); central 0 mẫu. → Cần chiến dịch thu isds2026 với nhiều signer/label.
- **Raw landmarks**: 865/865 mẫu legacy không có raw (`raw_landmarks_available=0`) — ablation tiền xử lý chỉ khả thi trên dữ liệu thu MỚI (npz_v2 đã bật cho luồng camera).
- **Session metadata**: 38 lớp legacy không có session_id.

## Kiến trúc — biết trước, chưa xử lý (có chủ đích)

- `app/routers/experiments.py` (hệ model_versions) vẫn dormant; nếu kích hoạt phải thêm `from app import train_task` vào `worker.py` (nếu không task treo im lặng).
- Realtime service chỉ hỗ trợ TCN khi promote; Phase 4 (profile routing) chưa triển khai.
- `nginx :8000` chỉ route một phần API — dev FE dùng vite proxy (same-origin); **không** đặt `VITE_API_URL` tuyệt đối trong dev (xem `frontend/.env.example`).
- CORS `allow_credentials=False` là chủ đích (cookie auth chạy same-origin qua gateway/proxy).
- File `*_backup.py` / `verify_refactor.py` / `run_kfold_cv.py` trong `processed/train_utils` là scratch cũ — cân nhắc dọn trước khi nộp báo cáo.

## Đã sửa gần đây (tham chiếu)

- **Samples catalog bị tách 2 file** (2026-07-20): layout cũ `dataset/samples.csv`
  (879 dòng lịch sử, khớp bản trên Drive) vs layout tạm `dataset/samples/samples.csv`
  (chỉ dòng mới) — mirror Drive đè bản thiếu lên bản đủ. Đã merge (886 dòng,
  header union 21 cột), code trỏ về `dataset/samples.csv` duy nhất, file tạm
  đổi tên `.pre_merge_bak`, backup tại `dataset/backups/`. Hệ quả tốt: bí ẩn
  "samples.csv bị reset còn 3 dòng" trong audit trước thực ra là do tách file —
  nguồn dữ liệu lịch sử VẪN CÒN ĐỦ, legacy splits giờ có thể tái tạo được.

- Login bounce ở dev 5173 (stale Bearer đè cookie) — fix 2 tầng, commit `3f63161`.
- `migrated_at` hỏng của `vao-lop` làm STARTUP_SYNC fail mỗi lần khởi động — đã sửa, DB sync đủ 43 lớp.
- `normalize_dialect` bị định nghĩa trùng (bản đầu bị shadow) — đã xóa bản chết.
