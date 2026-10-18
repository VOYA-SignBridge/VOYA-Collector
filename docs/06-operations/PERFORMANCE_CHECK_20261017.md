# Kiểm tra và tối ưu vận hành — 17/10/2026

Đo trên máy triển khai Windows/Docker Desktop, múi giờ Asia/Taipei.

## Thay đổi đã đưa vào chạy

- Đồng bộ nhãn không còn gọi `ensure_tables()` mỗi phút. Cấu trúc DB được
  chuẩn bị ở bước khởi động/migration hiện có.
- Băm nội dung bảng cùng spreadsheet ID và sheet GID. Chỉ ghi Google Sheets
  khi nội dung hoặc đích đồng bộ thay đổi; chỉ lưu dấu băm sau khi ghi thành công.
- Nếu không đọc được danh sách nhãn đã xoá trong DB, tác vụ retry thay vì ghi
  một bản thiếu dữ liệu. Cache lỗi/không ghi được không chặn đồng bộ.
- Giữ hành vi cũ khi danh mục rỗng: bỏ qua, không xoá nội dung bảng từ một
  nguồn có thể chưa sẵn sàng.
- Sửa test quản trị tổ chức để chạy trong MemoryRouter; test xuất dữ liệu
  kiểm tra nút bị khoá trước đồng thuận và gửi tham số đồng thuận sau khi chọn.
- Backend image mới cũng chứa thay đổi `visibility` đã có trong workspace.
  Kiểm tra 169 tệp Python: nội dung đang chạy khớp workspace (chuẩn hoá CRLF/LF).

## Số đo trước/sau

| Phép đo | Trước | Sau |
|---|---:|---:|
| Đồng bộ nhãn định kỳ (67 nhãn) | 4,66–4,90 giây, ghi toàn bộ mỗi lượt | Lượt đầu 2,923 giây; lượt không đổi 0,01524 giây, không ghi Sheets |
| API đọc tài liệu công khai: 20 yêu cầu / 5 kết nối | 20 HTTP 200; p50 148,8 ms; p95 247,4 ms | 20 HTTP 200; p50 45,9 ms; p95 83,6 ms |
| Backend RAM | ~742,5 MiB | ~738,8 MiB |

Mức giảm thời gian đồng bộ không đổi xấp xỉ 99,7%. Đây là giảm công việc DB
và mạng định kỳ; không phải bằng chứng giảm mạnh RAM nền. Số đo API là hai
lượt kiểm tra ngắn ở các thời điểm khác nhau, không chứng minh riêng thay đổi
đồng bộ gây ra toàn bộ chênh lệch độ trễ.

Sau triển khai: 14/14 dịch vụ healthy; backend/worker/trainer/beat không có
restart hoặc OOM. API qua tên miền trả HTTP 200 (~0,55 giây trong một lượt đo).
Tổng RAM các container ở mẫu cuối khoảng 2,28 GiB, có dao động theo tác vụ và
healthcheck. Chưa thay số worker hoặc giới hạn bộ nhớ.

## Kiểm thử

- TypeScript: đạt.
- Frontend đầy đủ: 76 tệp, 568/568 test đạt.
- Backend tách biệt: 46 test đạt, không skip, gồm video thật, một epoch TCN
  sinh checkpoint, khả năng phục vụ các kiến trúc model, giới hạn cửa sổ đo
  latency, pool kết nối, bundle xuất dữ liệu và coverage schema SOT.
- Sau chỉnh sửa cuối và bổ sung tình huống cache lỗi: 33 unit test chọn lọc đạt.
  Hai nhóm backend có phần trùng nhau, không cộng thành số test độc lập.
- `git diff --check` cho các tệp sửa: đạt.

## Thử tải đồng thời, tách biệt

Container riêng: không mạng, tối đa 4 CPU/3 GiB, mount nguồn/dataset/video chỉ
đọc. Không nối DB/Redis thật, không ghi vào dataset hoặc huấn luyện model triển
khai. Chạy đồng thời ba tiến trình:

| Luồng | Kết quả |
|---|---|
| Trích xuất 3 lượt clip D0001B.mp4 | 21,00 giây; mỗi lượt giữ được 9 mẫu |
| TCN, CPU, 1 epoch trên các split sẵn có | 31,23 giây; checkpoint hợp lệ |
| Nhận diện với checkpoint Hòa đê, khung đầu vào tổng hợp | 1.156 lượt trong 45 giây; p50 12,86 ms; p95 39,11 ms; max 190,34 ms |

RAM đỉnh container: 1.723,23 MiB (~1,68 GiB). Cả ba luồng thành công, exit 0,
không OOM. Số đo nhận diện bao gồm chuẩn hoá + suy luận, chưa bao gồm HTTP,
camera, MediaPipe trong trình duyệt hoặc thời gian render. Phần video dùng
pipeline thật và giả lập các nơi ghi dữ liệu. Đây chưa phải load test HTTP
upload có đăng nhập, chưa kiểm chứng GPU training hoặc rò RAM dài hạn.

## Triển khai và bằng chứng

- Image hoàn tác: `voya_backend:pre-perf-20261017`.
- Image chạy mới: `sha256:0548d8ee098aee6926082c71cb6b5c372823472a623c7779037d28373416bc6c`.
- Đã xác nhận không có job active trước khi recreate backend/worker/trainer/beat.
- Hai container thử nghiệm đã được xoá sau khi lưu log; image hoàn tác được giữ.
- Log tại `scratchpad/final-vitest-20261017.log`,
  `scratchpad/backend-perf-tests-20261017.log`,
  `scratchpad/final-backend-unit-20261017.log`,
  `scratchpad/concurrent-perf-20261017.log`,
  `scratchpad/labels-sync-after-20261017.log`.
- Script đo đồng thời: `scratchpad/concurrent_perf_20261017.py`.

Kết quả hiện tại chưa cho thấy cần nâng cấu hình chỉ để phục vụ tải nhẹ.
Việc xác định công suất người dùng đồng thời cần thêm tải HTTP có đăng nhập,
upload thực và huấn luyện GPU ở mức sử dụng dự kiến.

## Kiểm chứng hai tenant từ đầu đến cuối (17/10/2026, sáng)

Stack cô lập riêng (`voya-verify`, DB `verification_test`, cổng 18080), hai tenant
`verify-a` / `verify-b`, mỗi bên 60 mẫu tổng hợp cùng phương ngữ `hoa-de`. Dữ liệu
tổng hợp chỉ để kiểm luồng, không đánh giá độ chính xác.

### Lỗi tìm ra và đã sửa

| # | Lỗi | Hệ quả | Sửa ở |
|---|-----|--------|-------|
| 1 | Tenant mới không có dòng `vocabulary_groups` | Lớp đầu tiên của tenant mới vấp `fk_classes_vocabulary_group`; phiên thu và mẫu hỏng khoá ngoại theo | `metadata_db.upsert_class` tạo nhóm (ON CONFLICT DO NOTHING) trước khi ghi lớp |
| 1b | `seed_system_catalog` chỉ tìm `/config`, image không có thư mục này | Cài mới thì danh mục phương ngữ/profile rỗng | `vocabulary_registry._read_seed` thử thêm `/workspace/config` |
| 2 | `GET /training/dataset-info` đọc CSV chung không lọc tổ chức | Mỗi tenant thấy 120 mẫu và tên phương ngữ riêng của tenant kia | `training._rows_of_tenant` |
| 3 | `make_splits.py --tenant_id` chỉ đóng dấu chủ, không lọc dòng | Split của B chứa 60 mẫu của A: dữ liệu A chảy vào mô hình B | lọc theo `tenant_id` trước cổng kiểm duyệt |
| 4 | Trainer chỉ tìm `.npz` ở cây của tenant khởi tạo | Mọi job tenant khác chết với "train split became empty" | `train_tcn._tenant_feature_candidates` + `dataset_loader` (theo `file_path`, rồi `_tenants/<tenant>/`) |
| 5 | Đổi tên `.zip.part` trên ổ gắn Windows đôi khi `Permission denied`; bước dọn dẹp cũng văng lỗi | Bản xuất kẹt ở `running` vĩnh viễn | `tenant_lifecycle.finish_partial` (thử lại) + `discard_partial` (không ném lỗi), dùng cho cả bản xuất cá nhân |

### Kết quả sau khi sửa (12/12 đạt)

- Tenant mới tạo lớp đầu tiên không cần chèn tay: nhóm `hoa_de_vocabulary` tự có.
- `dataset-info`: mỗi bên đúng 60 mẫu, 2 lớp, chỉ phương ngữ của mình.
- Split mỗi bên chỉ chứa mẫu của chính mình (`verify-a: 60`, `verify-b: 60`).
- Train GPU (RTX 3050) của cả hai tenant `completed`, checkpoint có trên đĩa.
- Từ chối chéo (job, lượt chuẩn bị, gói xuất, split của bên kia): 403/404/400.
- Gói ZIP của mỗi bên chứa đủ 60 mẫu của mình, 0 mẫu của bên kia.

### Thử tải 30 phút

8 phiên đăng nhập thật, 2 tenant, 1 request/giây/phiên, xoay vòng 5 API:
14.392 request, 100% trả 200; p50 130 ms, p95 266 ms, p99 373 ms, max 878 ms.
RAM phẳng suốt 30 phút (backend 415 → 415 MiB, trainer 372 → 373 MiB, worker 158
MiB). Chưa thay được phép thử chạy nhiều giờ/nhiều ngày.

### Lịch sử train trên máy thật (chỉ đọc)

98 job: 12 completed, 84 failed, 2 cancelled. 77/84 lỗi là "Redis down"
20/07–07/08; lỗi gần nhất 14/09 — không có lỗi mới hơn một tháng. 10 job
`completed` tháng 7 trỏ tới checkpoint đã không còn ở đâu trên đĩa; 2 checkpoint
tháng 9 còn và nạp chạy được. Chưa sửa dữ liệu lịch sử.
