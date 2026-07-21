# Known Issues & Pending Decisions

> Cập nhật 2026-07-21 (pre-freeze). Mục nào cần quyết định nghiệp vụ thì KHÔNG tự xử lý bằng code.

## Test đỏ đã biết — NGOÀI phạm vi release `isds2026-paper-pipeline-v1`

Hai test dưới đây fail và **được quyết định là ngoài phạm vi** release này. Cả hai
đều nằm ngoài đường đi của research pipeline (manifest → split → train → aggregate),
không ảnh hưởng tới bất kỳ artifact nào dùng cho bài báo.

| # | Test | Triệu chứng | Nguyên nhân gốc | Vì sao không chặn release |
|---|---|---|---|---|
| T1 | `backend/tests/test_schema_evolution.py::test_backward_compatibility_defaults` | `assert rows[0]["gdrive_synced"] is True` → nhận `False` | Schema tự mâu thuẫn: `metadata_db.py:120` (CREATE TABLE) khai `gdrive_synced BOOLEAN DEFAULT FALSE`, còn `metadata_db.py:214` (ALTER migration) khai `DEFAULT TRUE`. DB dựng mới đi theo nhánh CREATE nên nhận `FALSE`; DB migrate từ bản cũ nhận `TRUE`. | Cột này chỉ điều khiển mirror lên Google Drive (`sync_tasks`). Manifest builder quét filesystem (`dataset/features/**.npz`), **không** đọc cột này. Sửa default sẽ đổi hành vi sync (có thể gây re-upload hàng loạt hoặc bỏ sót upload) → cần owner quyết, không tự sửa trong vòng freeze. |
| T2 | `frontend/src/hooks/useTrainingAPI.test.ts` (2 test) | `expect(axiosClient.post).toHaveBeenCalledWith(...)` → `Number of calls: 0` | Test viết 2026-07-15 (`1be7f25`) khẳng định hook phải dùng `axiosClient`. Thiết kế sau đó **cố ý** đổi sang raw `fetch` + CSRF double-submit + `credentials:'include'` (commit `3f63161`). Test lỗi thời, đang khẳng định điều ngược với thiết kế hiện hành. | Thuần frontend, không đụng research pipeline. Sửa test = viết lại assertion cho luồng fetch — là product work, cố tình không làm trong vòng freeze. **Không** xoá/sửa test để làm xanh cổng. |

## Regression từ commit `cb46a07` (2026-07-21) — đã phát hiện, một phần đã khôi phục

`cb46a07 "Update training for long sequence"` đã đưa nhiều file về trạng thái cũ hơn.
Ba trường hợp đã xác nhận:

| File | Mất gì | Trạng thái |
|---|---|---|
| `processed/splits/make_splits.py` | 229 dòng: `split_from_manifest`, `run_manifest_mode`, `_assert_signer_disjoint`, 6 CLI flag manifest-mode | **Đã khôi phục** (working tree bị revert về blob của `a0bb4c1`, 2026-07-05) |
| `frontend/vite.config.ts` | Toàn bộ block `test:` (`environment: 'jsdom'`, `setupFiles`) → vitest chạy ở môi trường node, mọi test chết vì `window is not defined`; **cả suite frontend im lặng không chạy** | **Đã khôi phục** block `test:` |
| `frontend/vite.config.ts` | `base: ''` và manual chunk `vendor_react` / `vendor_router` | **CHƯA khôi phục** — đổi output build có rủi ro về đường dẫn deploy và cache; cần owner xác nhận |
| `frontend/src/hooks/useTrainingAPI.ts` | CSRF token header + `credentials:'include'` + surface backend error detail | Working tree đã bị revert về bản không CSRF; **đã restore về HEAD** |

**Bài học:** `git status` sạch không đủ — cần so blob với HEAD. Test đã bắt được
trường hợp 1 (`ImportError`) nhưng KHÔNG bắt được trường hợp 2, vì mất cấu hình test
làm cho suite biến mất thay vì fail. Đó là lý do có `backend/tests/test_research_suites.py`.

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
