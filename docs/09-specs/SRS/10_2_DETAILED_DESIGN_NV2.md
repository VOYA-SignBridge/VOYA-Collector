# 10.2 Thiết kế chi tiết — Nghiệp vụ 2: Thu thập và quản lý dữ liệu mẫu

*Nghiệp vụ lõi. **13 use case** (UC201–UC213) cài đặt trên **38 điểm cuối** của năm
bộ định tuyến `upload`, `dataset`, `label_sessions`, `jobs`, `dataset_exporter`.*

Nghiệp vụ này trả lời **hai câu đối xứng**: *mẫu vào hệ thống bằng đường nào*, và
*mẫu mất đi bằng đường nào*. Câu thứ hai quan trọng ngang câu thứ nhất — một hệ
thống thu dữ liệu không có đường xoá kiểm soát được sẽ tích luỹ dữ liệu rác cho
tới lúc không dùng được.

---

## CN2.1 — Thu mẫu từ camera (UC201, UC203, UC205)

### Mục đích

Biến một lượt thực hiện ký hiệu trước máy quay thành **đúng một mẫu** của lớp đã
chọn. Điểm mốc bàn tay được trích **ngay trong trình duyệt** bằng WebAssembly, nên
video thô **không bắt buộc rời khỏi máy người dùng**.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `POST` | `/upload/camera` | Nhận chuỗi điểm mốc + siêu dữ liệu, tạo mẫu |
| `GET` | `/classes/preferences` | Đọc tuỳ chọn thu đã lưu của tài khoản (UC205) |
| `POST` | `/classes/preferences` | Lưu tuỳ chọn thu |
| `GET` | `/classes/suggest` | Gợi ý nhãn khi gõ |
| `GET` | `/classes/collectors` | Gợi ý tên người thực hiện |
| `GET` | `/jobs/{jobId}` | Hỏi trạng thái tác vụ nền |

### Giao diện 1 — Trung tâm Thu thập Dữ liệu (`/upload`, `UploadPage.tsx`, 212 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề trang | — | **"Trung tâm Thu thập Dữ liệu"** — "Quy trình gọn nhẹ để tạo bộ dữ liệu hiệu quả" |
| 2 | Thẻ chọn phương thức | **camera** | **"Ghi hình trực tiếp"** — "Thu thập nhanh theo lô với phản hồi tức thì" |
| 3 | Thẻ chọn phương thức | — | **"Tải video lên"** — "Xử lý các tệp video có sẵn" → CN2.2 |
| 4 | Khối gợi ý nhãn nhanh | **tắt theo cờ** | **"Gợi ý nhãn nhanh"** · "Được dùng nhiều hôm nay:" · "Nhấp để tự động điền nhãn giúp thu dữ liệu nhanh hơn" |
| 5 | Khối chặn khi chưa đăng nhập | ẩn | **"Cần đăng nhập để tải lên"** + *"Vui lòng đăng nhập bằng tài khoản của bạn để bắt đầu gửi dữ liệu ký hiệu tay."* + nút "Đăng nhập" |
| 6 | Vùng nạp trễ | — | Giao diện camera nạp trễ; trong lúc chờ hiện "Đang tải giao diện camera..." |
| 7 | Vùng báo lỗi | ẩn | `ErrorBanner`, dùng chung cho cả hai tab |

### Giao diện 2 — Bảng điều khiển thu (`CaptureCamera.tsx`, 447 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề khối | — | **"Ghi chuyển động chuyên nghiệp"** + *"Mở giao diện chụp toàn màn hình để thu dữ liệu tư thế không bị phân tâm. Tối ưu cho tốc độ và độ chính xác."* |
| 2 | Nút chính | — | **"Mở chế độ Toàn màn hình"** → Giao diện 3 |
| 3 | Nút | — | **"Xem hướng dẫn"** |
| 4 | Khối tiến trình | — | **"Tiến trình thu thập"** |
| 5 | Chỉ số | 0 | **"Số mẫu hôm nay"** |
| 6 | Chỉ số | 0 | **"Mẫu/phút"** |
| 7 | Chỉ số | 0 | **"Tổng khung hình"** |
| 8 | Chỉ số | 0 | **"Nhãn khác nhau"** |
| 9 | Nhãn gợi ý | — | **"Mẫu tiếp theo"** |
| 10 | Nút hành động nhanh | — | **"Xóa phiên"** |
| 11 | Nút hành động nhanh | — | **"Lặp lại mẫu trước"** |
| 12 | Bảng thống kê | — | **"Thống kê thu thập đơn giản"** · "Cập nhật trực tiếp" |
| 13 | Chỉ số bảng | 0 | **"Tổng lượt thu"** · **"Số từ thu được"** · **"Tổng khung hình"** |
| 14 | Bảng phân bố | — | **"Số lần thu theo từ"**; rỗng thì hiện "Chưa có thu nào" |
| 15 | Banner mất mạng | ẩn | **"Mất kết nối mạng."** — bắt sự kiện `offline` của trình duyệt |
| 16 | Thông báo thành công | — | *"Đã tải lên mẫu "{nhãn}" thành công."* |

### Giao diện 3 — Chế độ thu toàn màn hình (`FullscreenCaptureModal.tsx`, 2.346 dòng)

Đây là màn hình thu thật; **mọi thao tác ghi đều diễn ra ở đây**.

**Nhóm A — Khung hình và phản hồi thị giác**

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| A1 | Khung video + lớp vẽ chồng | — | Điểm mốc bàn tay vẽ theo thời gian thực trên khung hình |
| A2 | Tiêu đề chế độ | — | **"Ghi toàn màn hình"** |
| A3 | Chỉ báo camera | — | **"Camera sẵn sàng"** (chấm nhấp nháy) |
| A4 | Khung căn tư thế | hiện | **"Đặt vị trí vào khung"** + *"Thấy phần trên cơ thể và hai tay"* |
| A5 | Nút ẩn/hiện hướng dẫn | hiện | **"Hiển thị hướng dẫn"** / **"Ẩn hướng dẫn"** |
| A6 | Chỉ báo số tay | — | **"Số tay:"** |
| A7 | Gợi ý từ danh mục | — | **"Gợi ý catalog: {n} tay"**, kèm chú thích *"Nhãn này có số tay gợi ý từ catalog, nhưng vẫn cho phép thu linh hoạt 1 hoặc 2 tay."* |
| A8 | Cảnh báo không thấy tay | ẩn | **"Không thấy tay — vui lòng hiển thị cả hai tay"** + *"Hệ thống sẽ chỉ lưu khung khi tay được phát hiện"* |

**Nhóm B — Khai báo siêu dữ liệu**

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| B1 | Ô nhập văn bản **(bắt buộc)** | rỗng | **"Nhãn \*"**, gợi ý "vd: xin chào, cảm ơn" |
| B2 | Danh sách gợi ý nhãn | — | Ô tìm "Tìm..."; rỗng thì "Không tìm thấy" |
| B3 | Nút nhập bằng giọng nói | — | `SpeechInputButton`, nhãn "Giọng nói" |
| B4 | Chỉ báo nhãn | — | **"Đã có {n} mẫu"** hoặc **"Nhãn mới ({n} nhãn hiện có)"** |
| B5 | Ô nhập văn bản **(bắt buộc)** | rỗng | **"Người thực hiện \*"**, gợi ý "Ví dụ: Trân"; tên được làm sạch khi gõ |
| B6 | Nút nhập bằng giọng nói | — | Cho ô B5 |
| B7 | Hộp chọn | theo tuỳ chọn tài khoản | **"Ngôn ngữ"** |
| B8 | Hộp chọn | theo tuỳ chọn tài khoản | **"Phương ngữ"** |
| B9 | Dòng tóm tắt danh mục | — | **"{ngôn ngữ} / {phương ngữ} • {n} nhãn"**; khi tải: "Đang tải..." |

**Nhóm C — Phiên thu và số lượt**

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| C1 | Khối phiên thu | — | **"Phiên thu"** · **"Bắt đầu {lúc} · {n} mẫu"** |
| C2 | Nút | — | **"Phiên mới"** |
| C3 | Bộ đếm tăng/giảm | 1 | **"Số lượt thu"**, nút "Tăng số lượt thu" / "Giảm số lượt thu" |
| C4 | Danh sách mẫu đã lưu | — | **"Đã lưu phiên này: {mẫu} mẫu · {từ} từ"**; rỗng thì "Chưa có mẫu nào được lưu" |

**Nhóm D — Điều khiển ghi**

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| D1 | Nút chính | — | **"Bắt đầu chụp"** / **"Bắt đầu chụp ({n}x)"** |
| D2 | Đếm ngược | — | **"Bắt đầu sau {giây}..."** |
| D3 | Màn chuẩn bị | — | **"Chuẩn bị thực hiện:"** · **"Lần chụp {i} / {tổng}"** |
| D4 | Chỉ báo ghi | — | **"ĐANG GHI"** + **"{n} khung đã chụp"** |
| D5 | Dòng trạng thái | — | **"Trạng thái:"** → "Đang ghi" / "Sẵn sàng" / "Đang tải" |
| D6 | Dòng lần chụp | — | **"Lần chụp:"** |

**Nhóm E — Tạm dừng, hoàn tất, lỗi**

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| E1 | Màn tạm dừng | ẩn | **"Đã tạm dừng"** — *"Bạn muốn làm gì với dữ liệu hiện tại?"* + dòng **"Tiến độ:"** |
| E2 | Nút | — | **"Tiếp tục thu (giữ {n} khung)"** |
| E3 | Nút | — | **"Bắt đầu lại từ đầu (xóa dữ liệu)"** |
| E4 | Nút | — | **"Hoàn tất và lưu"** |
| E5 | Màn hoàn tất một lượt | — | **"Đã chụp {n} mẫu!"** · "Chuẩn bị chụp tiếp..." · **"Tiến độ: {đã} / {tổng}"** |
| E6 | Màn hoàn tất cả lô | — | **"Hoàn tất tất cả lần chụp!"** · *"Sẵn sàng chụp tiếp — nhập nhãn mới và nhấn nút Bắt đầu chụp"* |
| E7 | Cảnh báo kết nối | ẩn | **"Kết nối/lưu server đang gặp sự cố"** + *"Vui lòng tạm ngưng thu để tránh mất dữ liệu."* |
| E8 | Hộp thoại lỗi camera | ẩn | **"Lỗi Camera"** + nút **"Làm mới Trang"** / **"Thoát"** + *"Nếu vấn đề tiếp tục, vui lòng kiểm tra quyền truy cập camera trong cài đặt trình duyệt."* |
| E9 | Hộp thoại xác nhận thoát | ẩn | *"Capture chưa hoàn tất ({đã}/{cần}) — bạn có muốn thoát và bỏ dữ liệu này không?"* |
| E10 | Cảnh báo thiếu khung | ẩn | *"Bạn chưa thu đủ khung hình: {đã}/{cần}. Vui lòng tiếp tục quay cho đến khi đủ."* |
| E11 | Lỗi tải danh mục | ẩn | *"Không tải được danh sách bộ ngôn ngữ từ máy chủ."* |

### Giao diện 4 — Bảng phiên thu hiện tại (`SessionPanel.tsx`)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề | — | **"Phiên thu hiện tại"** — "Quản lý các mẫu vừa ghi" |
| 2 | Huy hiệu | — | **"{n} mẫu"** · **"{n} khung hình"** |
| 3 | Chỉ số | — | **"Tổng số mẫu"** · **"Tổng khung hình"** · **"Khung hình trung bình"** |
| 4 | Dòng mã phiên | — | **"Mã phiên"** |
| 5 | Danh sách mẫu | — | **"Mẫu #{mã}"** · trạng thái **"Đã tải lên"** / **"Đang xử lý"** · "{n} khung hình • {nhãn}" |
| 6 | Nút xoá mẫu | — | Nhãn trợ năng "Xoá mẫu này"; xác nhận *"Bạn có chắc muốn xoá mẫu này không?"* |
| 7 | Nút kết thúc phiên | — | **"Complete Session ({n} mẫu)"**; rỗng thì "Chưa có mẫu nào để kết thúc" |
| 8 | Trạng thái rỗng | — | **"Chưa thu mẫu nào"** + *"Bắt đầu ghi hình để thấy các mẫu hiện ra ở đây"* |

*Ghi chú trung thực: nhãn nút số 7 hiện còn lẫn tiếng Anh (**"Complete Session"**)
— đây là một chuỗi lọt qua lớp i18n, đúng loại lỗi mà công cụ đo độ phủ i18n từng
bỏ sót hai lần.*

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `samples` | X | X | X *(mềm)* | X |
| 2 | `capture_sessions` | X | X | | X |
| 3 | `classes` | X *(nhãn mới)* | | | X |
| 4 | `signers` | X | | | X |
| 5 | `dialects` | | | | X |
| 6 | `languages` | | | | X |
| 7 | `signer_consents` | | | | X |
| 8 | `tenant_usage_daily` | X | X | | X |
| 9 | `plans` · `tenant_subscriptions` | | | | X |
| 10 | `audit_log` | X | | | |
| 11 | `dataset/samples.csv` *(nguồn sự thật)* | X | X | | X |
| 12 | Tệp `.npz` + sidecar JSON | X | | | |
| 13 | Kho ngoài (Drive) | X | | | X |

### Tiến trình

1. Người ký mở `/upload`, tab "Ghi hình trực tiếp", bấm "Mở chế độ Toàn màn hình".
2. Trình duyệt xin quyền camera và khởi động bộ theo vết bàn tay **chạy trên máy
   khách**, vẽ điểm mốc chồng lên khung hình để người ký tự căn được tư thế.
3. Hệ thống hiển thị hướng dẫn thu lấy từ **siêu dữ liệu của lớp**: khung hình
   mong muốn, **số bàn tay lớp này yêu cầu**, thời lượng mục tiêu.
4. Người ký khai nhãn và người thực hiện, chọn ngôn ngữ / phương ngữ (điền sẵn
   theo tuỳ chọn tài khoản), đặt số lượt thu.
5. Bấm "Bắt đầu chụp" → đếm ngược → hệ thống gom khung điểm mốc kèm dấu thời gian
   cho tới khi đủ `TARGET_FRAMES` (60), hiển thị số khung đã thu và tỉ lệ khung
   thấy đủ số bàn tay.
6. Hệ thống phát lại cửa sổ vừa thu dưới dạng khung xương; người ký chọn giữ
   hoặc bỏ.
7. Bấm Lưu → **hai cổng ghi**:
   * đồng thuận còn hiệu lực? → không ⇒ chặn ghi, điều hướng chấp thuận
   * tổ chức còn hạn mức? → không ⇒ từ chối, nêu hạn mức gói
8. Hệ thống gửi chuỗi điểm mốc và siêu dữ liệu lên `POST /upload/camera`. Máy chủ
   ghi mẫu ở trạng thái `pending`, đẩy tác vụ nền, và **trả mã tác vụ ngay**.
9. Tiến trình nền (UC203) chạy: ghi kho thô → cắt cửa sổ trượt (60 khung, bước
   nhảy 2) → tăng cường → chấm chất lượng → ghi tệp đặc trưng → cập nhật mẫu sang
   `ready` → đẩy tác vụ đồng bộ kho ngoài.
10. Giao diện hiển thị mẫu mới trong bảng phiên thu; chỉ số chất lượng xuất hiện
    khi tiến trình nền hoàn tất.

### Luồng luân phiên

1. **Thu liên tiếp nhiều lượt trong một lần bấm.** Bộ đếm C3 đặt số lượt; sau mỗi
   lượt hệ thống hiện màn E5 rồi tự chuẩn bị lượt kế. Không phải khai lại nhãn.
2. **Tạm dừng giữa cửa sổ thu.** Màn E1 cho ba lựa chọn — giữ khung đã thu và
   tiếp tục · xoá và làm lại · hoàn tất và lưu phần đang có.
3. **Đổi người ký giữa buổi.** Bấm "Phiên mới" (C2); hệ thống mở **phiên thu
   mới**, vì phiên thu là đơn vị gắn với đúng một người ký.
4. **Không dùng được máy quay.** Chuyển sang CN2.2, vốn đi cùng một tiến trình xử
   lý ở bước 9.

### Luồng ngoại lệ

| # | Tình huống | Hành vi |
|---|---|---|
| 1 | Không có máy quay hoặc quyền bị từ chối | Hộp thoại E8 kèm hướng dẫn cấp quyền theo trình duyệt và đường thay thế. **Không dữ liệu nào được ghi**, không lượt thu nào được tính. Đây là lỗi phổ biến nhất ở các buổi thu ngoài hiện trường, thường vì thiết bị dùng chung đã từ chối quyền từ lần trước và trình duyệt nhớ lựa chọn đó |
| 2 | Không phát hiện được bàn tay suốt cửa sổ thu | Cảnh báo A8; hệ thống **chỉ lưu khung khi tay được phát hiện**, và từ chối lưu nếu không khung nào có tay. **Chặn sớm ở máy khách** tiết kiệm một vòng xử lý và cho người ký phản hồi ngay khi họ còn đứng trước máy quay |
| 3 | Chưa đủ số khung yêu cầu | Cảnh báo E10 nêu **{đã}/{cần}**; không lưu |
| 4 | Lớp yêu cầu hai tay nhưng chỉ theo vết được một | Chỉ báo A6/A7 nêu số tay và gợi ý từ danh mục. Số tay yêu cầu **đọc từ siêu dữ liệu lớp**, không suy đoán từ khung hình — suy đoán sẽ khiến một lớp hai tay được chấp nhận với dữ liệu một tay khi người ký để tay kia ra ngoài khung. Người ký **vẫn lưu được** nếu chủ ý; chỉ số chất lượng phản ánh điều đó |
| 5 | Chưa có đồng thuận còn hiệu lực | Chặn ghi, điều hướng tới CN1.8. **Cửa sổ đã thu giữ lại trong trình duyệt**, nên sau khi chấp thuận thì lưu tiếp mà không phải ký lại |
| 6 | Vượt hạn mức số mẫu | Từ chối lưu, hiển thị hạn mức và mức đã dùng, nêu đường đổi gói. Cửa sổ đã thu **cũng được giữ lại**, để không mất công người ký nếu quản trị viên nâng hạn mức ngay tại chỗ |
| 7 | Mất kết nối khi đang gửi | Banner số 15 (Giao diện 2) và cảnh báo E7. Hệ thống **giữ lại** cửa sổ đã thu và cho thử gửi lại. Số lần thử tự động **có trần**; hết trần thì dừng và để người ký quyết định, **không lặp vô hạn làm nóng thiết bị**. Nếu đóng trang trước khi gửi được, dữ liệu trong bộ nhớ trình duyệt **mất** — và điều này được nói rõ trên thông báo lỗi |
| 8 | Thoát khi chưa thu xong | Hộp thoại E9 hỏi trước khi bỏ dữ liệu |
| 9 | Tiến trình nền hỏng sau khi mẫu đã nhận | Mẫu tồn tại nhưng không có tệp đặc trưng và **không dùng được cho huấn luyện**; trạng thái hiện ở CN2.3 kèm lý do, chạy lại được **mà không cần thu lại** |
| 10 | Không tải được danh mục từ máy chủ | Thông báo E11. Hệ thống **không** rơi về một danh mục mặc định — thiếu dữ liệu danh mục thì dừng, không suy đoán (BR-4.3) |

### Kết quả mong đợi

Một mẫu mới thuộc **đúng lớp, đúng phiên thu và đúng người ký** được ghi vào danh
bạ nguồn sự thật, có tệp đặc trưng cùng chỉ số chất lượng sau khi tiến trình nền
hoàn tất, và tính **đúng một suất** trong hạn mức của tổ chức. Nếu bất kỳ cổng nào
ở bước 7 chặn lại, **không mẫu nào được tạo** và dữ liệu vừa thu vẫn còn trong
trình duyệt để người ký quyết định.

### Ràng buộc

* **BR-5.1** một lượt thu = đúng một mẫu, tính một suất hạn mức
* **BR-5.2** phiên thu gắn với đúng một người ký
* **BR-5.4** đường webcam **không sinh video thô**
* **BR-4.6** số bàn tay yêu cầu đọc từ siêu dữ liệu lớp
* **BR-5.6 / BR-5.7** hai cổng ghi; cổng chặn ⇒ không mẫu nào được tạo
* **NFR-P2** ≥ 15 khung/giây · **NFR-P3** giao diện trả về < 1 giây
* **NFR-R1** mất kết nối không được làm mất bản thu
* **RB-D6** 126 chiều/khung (21 × 3 × 2)

**Một điểm phải nói thẳng về chất lượng dữ liệu:** ô **"Người thực hiện \*"** (B5)
là **nhập tự do**. Đây chính là chỗ sinh ra con số **43,4 %** độ phủ định danh
người ký — mắt xích *mẫu ↔ người ký* chỉ thiết lập được đáng tin **tại thời điểm
thu**, và một ô nhập tự do không bảo đảm được điều đó. Hệ thống có gợi ý tên
(`/classes/collectors`) để giảm sai lệch chính tả, nhưng gợi ý không phải ràng buộc.

---

## CN2.2 — Tải lên tệp video theo lô (UC202, UC203)

### Mục đích

Đưa dữ liệu đã quay sẵn vào hệ thống **theo lô**, cho các buổi thu ngoài hiện
trường hoặc dữ liệu quay bằng thiết bị khác. Kết thúc ở **cùng một chỗ** với
CN2.1: một mẫu đã trích đặc trưng.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `POST` | `/upload/video` | Nhận một tệp video kèm siêu dữ liệu |
| `GET` | `/jobs/{jobId}` | Hỏi trạng thái xử lý |
| `GET` | `/classes/suggest` · `/classes/collectors` | Gợi ý nhãn và người ký |

### Giao diện 1 — Tải video (`UploadVideoForm.tsx`, 1.101 dòng)

**Nhóm A — Đầu trang và thống kê lô**

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| A1 | Tiêu đề | — | **"Tải video"** — "Quản lý và tải nhiều video cùng lúc" |
| A2 | Huy hiệu trạng thái | — | **"{n} chờ"** · **"{n} đang tải"** · **"{n} xong"** · **"{n} lỗi"** |

**Nhóm B — Giá trị mặc định áp cho tệp mới**

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| B1 | Tiêu đề khối | — | **"Giá trị mặc định (áp dụng cho file mới)"** |
| B2 | Ô nhập | rỗng | **"Nhãn mặc định"**, gợi ý "ví dụ: đi bộ" |
| B3 | Nút giọng nói | — | "Dùng giọng nói để điền nhãn mặc định" |
| B4 | Ô nhập | rỗng | **"Người ký hiệu"**, gợi ý "ví dụ: Trân" |
| B5 | Nút giọng nói | — | "Dùng giọng nói để điền tên người ký hiệu" |
| B6 | Dòng gợi ý | — | **"Gợi ý:"** + danh sách tên đã dùng |
| B7 | Hộp chọn | — | **"Bộ ngôn ngữ"**, có mục **"+ Thêm mới..."** |

**Nhóm C — Vùng chọn tệp**

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| C1 | Vùng kéo thả | — | **"Kéo thả video vào đây"** + "hoặc chọn từ máy tính" |
| C2 | Nút | — | **"Chọn file"** |
| C3 | Nút | — | **"Chọn thư mục"** |
| C4 | Nút nhập CSV | — | "Import CSV để ánh xạ label hàng loạt. Format: `filename,label,user,dialect`" |
| C5 | Dòng ràng buộc | — | **"Hỗ trợ: MP4, MOV, AVI, WMV, MKV, WebM • Tối đa 100MB/file"** |
| C6 | Ghi chú thứ tự | — | *"Có thể import CSV trước hoặc sau đều được"* |

**Nhóm D — Danh sách tệp và sửa hàng loạt**

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| D1 | Tiêu đề danh sách | — | **"Danh sách file ({n})"** |
| D2 | Nút chọn | — | **"Chọn tất cả"** / **"Bỏ chọn"**; hiển thị "{n} đã chọn" |
| D3 | Nút | — | **"Sửa hàng loạt"** |
| D4 | Nút | — | **"Xóa đã chọn"** |
| D5 | Bảng sửa hàng loạt | — | **"Áp dụng cho {n} tệp đã chọn:"** |
| D6 | Ô + nút | — | **"Nhãn"** — "Nhập nhãn mới" + **"Áp dụng"** |
| D7 | Ô + nút | — | **"Người ký hiệu"** — "Nhập tên người ký hiệu" + **"Áp dụng"** |
| D8 | Hộp chọn + nút | — | **"Bộ ngôn ngữ"** + **"Áp dụng"** |

**Nhóm E — Thông báo kết quả ánh xạ**

| No. | Nội dung thông báo |
|:--:|---|
| E1 | *"Bỏ qua {n} file trùng lặp"* |
| E2 | *"Đã thêm {n} file, trong đó {m} file đã áp dụng CSV mapping"* |
| E3 | *"Đã lưu {n} mapping từ CSV. Bây giờ hãy thêm video để tự động áp dụng!"* |
| E4 | *"Đã ánh xạ {khớp}/{tổng} file từ CSV. {không khớp} file không tìm thấy trong CSV sẽ dùng giá trị mặc định."* |
| E5 | *"Có {n} lỗi cần sửa trước khi upload"* |

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `raw_uploads` | X | X | | X |
| 2 | `samples` | X | X | | X |
| 3 | `classes` | X | | | X |
| 4 | `signers` | X | | | X |
| 5 | `signer_consents` | | | | X |
| 6 | `tenant_usage_daily` | X | X | | X |
| 7 | Kho thô trên hệ tệp | X | | | X |
| 8 | Kho ngoài (Drive) | X | | | X |

### Tiến trình

1. Người dùng đặt **giá trị mặc định** cho lô: nhãn, người ký hiệu, bộ ngôn ngữ.
2. (Tuỳ chọn) Nhập tệp CSV ánh xạ theo định dạng `filename,label,user,dialect` —
   **trước hoặc sau khi thêm video đều được**.
3. Kéo thả hoặc chọn tệp / chọn cả thư mục. Hệ thống **bỏ qua tệp trùng** và báo
   số lượng.
4. Hệ thống áp ánh xạ CSV cho các tệp khớp tên; tệp không khớp dùng giá trị mặc
   định, và **con số không khớp được nói rõ** (E4).
5. Người dùng sửa từng dòng hoặc dùng **sửa hàng loạt** cho nhóm tệp đã chọn.
6. Hệ thống kiểm hợp lệ trước khi gửi; còn lỗi thì báo E5 và **không gửi**.
7. Hai cổng ghi như CN2.1 (đồng thuận, hạn mức).
8. Với từng tệp: gửi `POST /upload/video`, máy chủ **ghi kho thô trước mọi bước
   chuẩn hoá**, trả mã tác vụ.
9. Tiến trình nền trích điểm mốc **phía máy chủ**, rồi đi tiếp đúng đường của
   CN2.1 bước 9.
10. Huy hiệu A2 cập nhật theo trạng thái từng tệp: chờ → đang tải → xong / lỗi.

### Luồng ngoại lệ

| # | Tình huống | Hành vi |
|---|---|---|
| 1 | Định dạng không hỗ trợ | Tệp bị từ chối; **các tệp còn lại trong lô vẫn tiếp tục**. Không huỷ cả lô vì một tệp sai — một buổi quay hiện trường thường lẫn vài định dạng |
| 2 | Tệp vượt 100 MB | Từ chối kèm con số giới hạn cụ thể, để người dùng biết phải cắt tới đâu |
| 3 | Tệp trùng | Bỏ qua và báo E1 |
| 4 | CSV không khớp tên tệp | Dùng giá trị mặc định và **báo rõ số tệp không khớp** (E4), thay vì im lặng |
| 5 | Còn lỗi hợp lệ chưa sửa | Báo E5 và chặn gửi |
| 6 | Vượt hạn mức giữa lô | Nhận phần còn trong hạn mức, từ chối phần vượt, nêu tên tệp bị từ chối |
| 7 | Không phát hiện được tay trong toàn bộ video | Tác vụ kết thúc **thất bại** kèm lý do; **tệp thô vẫn nằm nguyên trong kho**, nên người dùng xem lại được video để biết nguyên nhân |

### Ràng buộc

* **BR-5.3 / NFR-R2** bản gốc ghi vào kho thô **trước** mọi bước chuẩn hoá
* Khác CN2.1 ở chỗ **trích đặc trưng chạy trên máy chủ** → đường này tiêu tài
  nguyên máy chủ và **có** giữ video thô
* **Hạn chế đã biết:** tính lũy đẳng của bước đẩy lên kho ngoài **chưa bảo đảm** —
  chạy lại có thể tạo bản trùng

---

## CN2.3 — Theo dõi trạng thái tác vụ nền (UC204)

### Mục đích

Cho người dùng biết mẫu vừa gửi đang ở đâu, và khi hỏng thì hỏng vì lý do gì —
thay vì để họ đoán từ việc mẫu chưa xuất hiện.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/jobs/{jobId}` | Trạng thái, tiến độ, lý do lỗi của một tác vụ |

### Giao diện

Hiển thị nội tuyến trong các màn hình thu và tải lên (huy hiệu trạng thái ở
`SessionPanel` và nhóm A của `UploadVideoForm`), không phải một trang riêng.

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| 1 | Huy hiệu trạng thái | **"Đang xử lý"** / **"Đã tải lên"** |
| 2 | Bộ đếm theo trạng thái | "{n} chờ · {n} đang tải · {n} xong · {n} lỗi" |
| 3 | Dòng lý do lỗi | Lý do đọc được, không phải mã lỗi |

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | Trạng thái tác vụ trên Redis | | | | X |
| 2 | `samples` | | | | X |
| 3 | `notifications` | X | | | X |

### Ràng buộc

* Trạng thái **"đang xử lý" là một trạng thái hợp lệ**, không phải một lỗi — giao
  diện phải xử lý được nó như vậy
* **NFR-R7** tác vụ thất bại phải **thông báo tới chủ sở hữu tác vụ**, không chỉ
  ghi log

---

## CN2.4 — Duyệt và quản lý danh mục nhãn (UC206)

### Mục đích

Cho người dùng thấy hệ thống đang có những lớp nào, mỗi lớp thu được bao nhiêu, và
lớp nào **đã đủ điều kiện huấn luyện**.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/dataset/labels` | Danh sách nhãn kèm số mẫu |
| `POST` | `/dataset/labels` | Tạo nhãn mới |
| `PUT` | `/dataset/labels/{class_idx}` · `/classes/{ref}` | Sửa nhãn |
| `DELETE` | `/dataset/labels/{class_idx}` · `/classes/{ref}` | Xoá mềm nhãn |
| `GET` | `/classes/community-stats` | Thống kê mặt phẳng cộng đồng |

### Giao diện 1 — Thư viện nhãn (`/labels`, `LabelsPage.tsx`, 1.014 dòng)

**Nhóm A — Đầu trang và thống kê**

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| A1 | Tiêu đề trang | — | **"Thư viện nhãn"** — "Quản lý và tìm kiếm các nhãn ngôn ngữ ký hiệu." |
| A2 | Đường dẫn phân cấp | — | Dashboard → **"Dữ liệu"** → **"Nhãn"** |
| A3 | Thẻ chỉ số | — | **"Tổng nhãn"** |
| A4 | Thẻ chỉ số | — | **"Tổng mẫu"** ("mẫu video") |
| A5 | Thẻ chỉ số | — | **"Phổ biến"** ("nhãn phổ biến") |
| A6 | Thẻ chỉ số | — | **"Phương ngữ"** ("vùng miền") |
| A7 | Khối hoạt động | — | **"Hoạt động (logs)"** |
| A8 | Thông báo trạng thái | ẩn | Có nút đóng, nhãn trợ năng "Đóng thông báo" |

**Nhóm B — Bộ lọc và tìm kiếm**

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| B1 | Tiêu đề khối | — | **"Danh sách nhãn"** |
| B2 | Hộp chọn ngôn ngữ | — | **"🇻🇳 Tiếng Việt"** / **"🇬🇧 Tiếng Anh"** |
| B3 | Hộp chọn vùng | tất cả | **"Tất cả vùng"**; giá trị dự phòng **"Chưa phân loại"** |
| B4 | Ô tìm kiếm | rỗng | **"Tìm kiếm nhãn, slug hoặc ID..."**, nhãn trợ năng "Tìm kiếm nhãn" |
| B5 | Nút chuyển chế độ xem | lưới | **"Xem dạng lưới"** / **"Xem dạng danh sách"** |

**Nhóm C — Thao tác trên danh mục**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| C1 | Nút | **"Tạo nhãn mới"** |
| C2 | Nút | **"Xuất JSON"** |
| C3 | Nút | **"Xuất CSV"** |

**Nhóm D — Thẻ nhãn trong danh sách**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| D1 | Huy hiệu phạm vi | **"Toàn cầu"** — phân biệt nhãn của mặt phẳng cộng đồng |
| D2 | Thanh tiến độ | **"Tiến độ thu thập"** / **"Tiến độ"** |
| D3 | Nhãn điều kiện | **"Cần thêm {n} lần quay"** hoặc **"Đã đủ điều kiện huấn luyện"** |
| D4 | Trạng thái rỗng | **"Không tìm thấy nhãn"** + *"Thử điều chỉnh bộ lọc hoặc tìm kiếm với từ khóa khác."* |
| D5 | Màn hình chờ | "Đang tải danh sách nhãn..." |

**Thành phần D3 nói ra một luật nghiệp vụ ngay trên thẻ:** một lớp cần đủ số lần
quay tối thiểu mới **đủ điều kiện huấn luyện**. Nhưng phải đọc nó đúng mức —
"đủ điều kiện" ở đây chỉ nói về **số lượng**, không nói về đồng thuận. Một lớp đủ
số mẫu nhưng người ký chưa đồng ý ở mức tương ứng thì với đường phát hành nghiên
cứu, nó vẫn là một lớp **rỗng** (BR-4.7).

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `classes` | X | X | X *(mềm)* | X |
| 2 | `samples` | | | | X *(đếm)* |
| 3 | `dialects` · `languages` · `regions` | | | | X |
| 4 | `community_dialects` · `community_profiles` | | | | X |
| 5 | `audit_log` | X | | | |

### Luồng ngoại lệ

| # | Tình huống | Thông báo |
|---|---|---|
| 1 | Tên nhãn để trống khi tạo | *"Tên nhãn không được để trống."* |
| 2 | Không tạo được nhãn | *"Không thể tạo nhãn."* |
| 3 | Nhãn để trống khi sửa | *"Label không được để trống."* |
| 4 | Không cập nhật được | *"Không thể cập nhật nhãn."* |
| 5 | Không xoá được | *"Không thể xóa nhãn."* |

Thông báo thành công nêu **đủ ba thành phần định danh**: *"Đã tạo nhãn "{nhãn}"
({ngôn ngữ} / {phương ngữ})"*. Đây không phải chi tiết trang trí — vì phương ngữ
tham gia vào **định danh** của lớp (BR-4.1), một thông báo chỉ nêu tên nhãn sẽ
không phân biệt được hai lớp khác phương ngữ.

### Ràng buộc

* **BR-4.1** định danh lớp gồm **năm cột**, trong đó có phương ngữ và vùng miền
* **BR-2.1** danh sách đã bị chính sách bảo mật mức hàng lọc theo tổ chức
* **BR-5.5** xoá nhãn là **xoá mềm**, đi qua thùng rác

---

## CN2.5 — Xem chi tiết lớp và xem lại phiên thu (UC207, UC208)

### Mục đích

Mở từng lần quay ra **xem lại chuyển động** để đánh giá chất lượng, mà **không cần
tới video gốc** — vì video gốc có thể không tồn tại, và ngay cả khi tồn tại thì mở
nó ra là mở luôn danh tính người đóng góp.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/classes/{class_uid}/sessions` | Danh sách lần quay của một lớp |
| `GET` | `/dataset/samples/{id}/data` | Dữ liệu khung hình để dựng lại |
| `POST` | `/classes/{class_uid}/sessions/{session_id}/reassign` | Chuyển lần quay sang nhãn khác |
| `DELETE` | `/dataset/samples/{id}` | Xoá mềm mẫu |

### Giao diện 1 — Chi tiết nhãn (`/labels/:id`, `LabelDetailPage.tsx`, 642 dòng)

**Nhóm A — Đầu trang**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| A1 | Đường dẫn phân cấp | **"Thư viện nhãn"** → tên nhãn |
| A2 | Phụ đề | **"{phương ngữ} · {n} lần quay đã thu thập"** |

**Nhóm B — Danh sách lần quay**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| B1 | Tiêu đề khối | **"Các lần quay (Sessions)"** |
| B2 | Thẻ lần quay | **"Lần quay {n}"**, có nhãn **"của bạn"** nếu là của chính người dùng |
| B3 | Dòng thông tin | **"{n} mẫu"** · huy hiệu **"video nhẹ"** nếu có bản xem trước |
| B4 | Dòng người đóng góp | Tên hoặc **"Ẩn danh"** · thời điểm |
| B5 | Dòng kỹ thuật | **"{n} khung hình"** · nguồn (`camera` mặc định) |
| B6 | Nút | **"Tải .npz"** |
| B7 | Nút | **"Đổi nhãn"** |
| B8 | Nút | **"Xóa"** / "Đang xóa…" |
| B9 | Trạng thái rỗng | **"Chưa có lần quay nào"** + *"Nhãn này chưa có dữ liệu được thu thập."* |

**Nhóm C — Trình xem chuyển động**

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| C1 | Dòng ngữ cảnh | — | **"Người đóng góp: {ai}"** hoặc **"Chọn một lần quay"** |
| C2 | Hộp chọn chất lượng | tự động | Nhãn trợ năng "Chất lượng hiển thị"; mục **"Tự động ({chế độ})"** |
| C3 | Nút chế độ nhẹ | — | **"Eco (tiết kiệm máy)"** |
| C4 | Nút lọc | — | **"Giảm rung"** |
| C5 | Cảnh báo tự hạ cấp | ẩn | *"Máy đang chậm/nóng — đã tự chuyển về chế độ nhẹ hơn. Bạn có thể chọn lại ở menu Chất lượng."* |
| C6 | Ghi chú giới hạn 2D | — | *"khoảng cách thật giữa hai tay và độ sâu không còn"* · *"chiều sâu bị dẹp"* |
| C7 | Màn chờ | — | "Đang tải dữ liệu chuyển động…" · "Đang khởi tạo khung cảnh 3D…" |
| C8 | Hướng dẫn | — | *"Chọn một lần quay ở danh sách bên trái để xem lại chuyển động."* |
| C9 | **Ghi chú quyền riêng tư** | — | *"Trình xem chỉ hiển thị đúng dữ liệu tọa độ đã thu (.npz) — không dùng video quay gốc, nên danh tính người đóng góp luôn được bảo vệ."* |
| C10 | Thông báo thiếu bản xem nhẹ | ẩn | *"Chưa tạo được video xem nhẹ cho lần quay này. Hãy thử chế độ Khung xương 2D."* · "Đang kiểm tra bản xem nhẹ…" |

**Nhóm D — Hộp thoại đổi nhãn**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| D1 | Tiêu đề | **"Đổi nhãn cho lần quay"** |
| D2 | Hướng dẫn | *"Chọn nhãn đúng để chuyển lần quay này sang. Dữ liệu (.npz) sẽ được di chuyển sang nhãn mới."* |
| D3 | Ô tìm | **"Tìm nhãn…"**; rỗng thì "Không có nhãn nào khác." |
| D4 | Trạng thái chạy | "Đang chuyển lần quay…" |

**Ghi chú C9 là một phát biểu về thiết kế, và nó đúng — nhưng phải đọc đúng mức.**
Trình xem thật sự chỉ dựng từ `.npz`, không mở video. Tuy nhiên điều đó **không**
làm dữ liệu trở thành ẩn danh: chuỗi điểm mốc vẫn là dữ liệu về một con người cụ
thể và vẫn quy về người đó được khi ghép với siêu dữ liệu khác. Thuật ngữ đúng là
**"không lộ diện"**, không phải "ẩn danh".

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `classes` | | | | X |
| 2 | `capture_sessions` | | X *(đổi lớp)* | X *(mềm)* | X |
| 3 | `samples` | | X *(đổi `class_uid`)* | X *(mềm)* | X |
| 4 | `signers` | | | | X |
| 5 | Tệp `.npz` (cục bộ + Drive) | | X *(di chuyển)* | | X |
| 6 | `dataset/samples.csv` | | X | | X |
| 7 | `audit_log` | X | | | |

### Tiến trình — xem lại một lần quay

1. Mở `/labels/:id`; hệ thống tải danh sách lần quay của lớp đó.
2. Chọn một lần quay → tải dữ liệu khung hình.
3. Trình xem dựng lại chuỗi khung xương. Hệ thống **tự chọn tầng dựng hình** theo
   năng lực máy, và tự hạ cấp khi máy chậm hoặc nóng (C5).
4. Người dùng chuyển giữa các chế độ hiển thị, bật "Giảm rung" nếu cần.

### Tiến trình — chuyển lần quay sang nhãn khác

1. Bấm "Đổi nhãn" trên thẻ lần quay.
2. Chọn nhãn đích trong hộp thoại D.
3. Máy chủ kiểm quyền: **chỉ chủ sở hữu hoặc quản trị viên**; người khác nhận lỗi
   *"Bạn chỉ có thể đổi nhãn lần quay của chính mình"*.
4. Mẫu gốc **và mọi bản tăng cường cùng `session_id`** được đổi nhãn; tệp `.npz`
   được **di chuyển** sang thư mục của lớp đích, ở cả kho cục bộ lẫn Drive.
5. Một dòng hỏng **không làm dừng các dòng còn lại**; hệ thống ghi lại danh sách
   dòng chuyển được và dòng lỗi.
6. Ghi nhật ký kèm số dòng đã chuyển và số dòng lỗi.

**Một chi tiết bảo mật trong bước 4, ghi lại vì nó dễ làm sai:** phạm vi tổ chức
truyền vào thao tác chuyển là **phạm vi của NGƯỜI GỌI**, không phải của tài
nguyên. Truyền phạm vi của mẫu vào đây sẽ **vô hiệu hoá chính phép kiểm** — một
mẫu của tổ chức khác sẽ tự mang theo phạm vi làm nó hợp lệ.

### Luồng ngoại lệ

| # | Tình huống | Thông báo |
|---|---|---|
| 1 | Không tải được danh sách lần quay | *"Không tải được danh sách lần quay"* |
| 2 | Không tải được dữ liệu khung hình | *"Không tải được dữ liệu khung hình"* |
| 3 | Không tải được dữ liệu nhãn | *"Không tải được dữ liệu nhãn"* + nút **"Thử lại"** |
| 4 | Xoá lần quay | Xác nhận: *"Xóa lần quay này của "{nhãn}"? {n} mẫu sẽ được chuyển vào thùng rác."* |
| 5 | Không xoá được | *"Không xóa được lần quay"* |
| 6 | Không đổi được nhãn | *"Không đổi được nhãn cho lần quay"* |
| 7 | Chưa có bản xem nhẹ | C10 — đề nghị dùng chế độ Khung xương 2D |

### Ràng buộc

* **BR-5.5** xoá lần quay là **xoá mềm**; thông báo xác nhận nói rõ *"sẽ được
  chuyển vào thùng rác"* chứ không nói "xoá"
* **BR-2.1** mọi truy vấn đã bị lọc theo tổ chức ở tầng CSDL
* Trình dựng khung xương từng có lỗi **chồng hai tay lên nhau ở cả ba bộ dựng** —
  đã sửa, và là lý do màn hình này có bộ chọn tầng dựng hình (C2)
* Chỉ số **độ đầy đủ tính lại được** từ `.npz`; **độ rung thì không**. Hai chỉ số
  này **không có cùng giá trị chứng minh**

### Sai lệch giữa đặc tả và cài đặt — phải ghi lại

Chương 1 đặt tên **UC210 là "Gán lại người ký cho phiên thu"**. Điểm cuối thực tế
đang chạy là `/classes/{class_uid}/sessions/{session_id}/reassign`, và nó **chuyển
lần quay sang một NHÃN khác**, không gán lại người ký. Giao diện cũng gọi đúng như
vậy: **"Đổi nhãn cho lần quay"**.

Hai chức năng này giải hai bài toán khác nhau — một cái sửa *nhãn sai*, một cái
sửa *quy kết sai*. Bản SRS ghi nhận **cài đặt hiện có là đổi nhãn**; chức năng gán
lại người ký cho một phiên thu **chưa có bề mặt vận hành tương ứng** trong màn
hình này. Đây là chênh lệch cần chỉnh **ở Chương 1**, không phải chỗ để bản SRS
mô tả theo đặc tả rồi bỏ qua mã.

---

## CN2.6 — Thùng rác: khôi phục và xoá vĩnh viễn (UC212)

### Mục đích

Làm cho "xoá" trở thành một thao tác **hoàn tác được**, và tách hẳn nó khỏi thao
tác **không hoàn tác được** — bằng hai nút khác nhau, ở hai bước khác nhau, với
hai mức xác nhận khác nhau.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/dataset/samples/trash` · `/classes/trash` | Đọc thùng rác hai loại |
| `POST` | `/dataset/samples/{id}/restore` · `/classes/{uid}/restore` | Khôi phục |
| `DELETE` | `/dataset/samples/{id}/purge` · `/classes/{uid}/purge` | Xoá vĩnh viễn |

### Giao diện 1 — Thùng rác (`/trash`, `TrashPage.tsx`, 454 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề | — | **"Thùng rác"** |
| 2 | Ghi chú cơ chế | — | Nêu rõ hai đường: **"Khôi phục"** và **"xóa vĩnh viễn"** |
| 3 | Thẻ tab | mẫu | **"Nhãn đã xóa"** *(chỉ quản trị viên)* · **"Mẫu đã xóa"**, kèm số lượng |
| 4 | Nút chọn | — | **"Chọn tất cả"** / **"Đã chọn {n}"** |
| 5 | Nút | — | **"Khôi phục"** (+ số lượng đã chọn) |
| 6 | Nút | — | **"Xóa vĩnh viễn"** (+ số lượng đã chọn) |
| 7 | Nút | — | **"Làm trống thùng rác"** |
| 8 | Bảng nhãn đã xoá | — | Cột: **"Nhãn"** · **"Ngôn ngữ / Giọng"** · **"Số mẫu"** |
| 9 | Bảng mẫu đã xoá | — | Cột: **"Mã mẫu"** · **"Nhãn"** · **"Người đóng góp"** |
| 10 | Trạng thái rỗng | — | **"Thùng rác trống"** + "Chưa có nhãn nào bị xóa." / "Chưa có mẫu nào bị xóa." |
| 11 | Màn chờ | — | "Đang tải thùng rác…" |

**Hộp thoại xác nhận — bốn biến thể, mỗi cái nói rõ hệ quả riêng:**

| Trường hợp | Tiêu đề | Nội dung |
|---|---|---|
| Xoá vĩnh viễn nhiều mục | **"Xóa vĩnh viễn mục đã chọn"** | *"Bạn sắp xóa VĨNH VIỄN {n} {loại}. Hành động này không thể hoàn tác."* — nút **"Xóa {n} mục"** |
| Làm trống thùng rác | **"Làm trống thùng rác"** | *"Xóa VĨNH VIỄN toàn bộ {n} {loại} trong thùng rác. Hành động này không thể hoàn tác."* — nút **"Làm trống"** |
| Xoá vĩnh viễn một nhãn | **"Xóa vĩnh viễn nhãn"** | *"Xóa VĨNH VIỄN nhãn "{nhãn}" và {n} mẫu bên trong (file + Drive). Không thể hoàn tác."* |
| Xoá vĩnh viễn một mẫu | **"Xóa vĩnh viễn mẫu"** | *"Xóa VĨNH VIỄN mẫu {mã}. Không thể hoàn tác."* |

Với tab nhãn, cụm `{loại}` nở thành **"nhãn (kèm toàn bộ mẫu bên trong)"** — nói
rõ phạm vi lan toả trước khi bấm, không để người dùng phát hiện sau.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `samples` | | X *(khôi phục)* | X **(vĩnh viễn)** | X |
| 2 | `classes` | | X *(khôi phục)* | X **(vĩnh viễn)** | X |
| 3 | Tệp `.npz` cục bộ | | | X | X |
| 4 | Kho ngoài (Drive) | | | X | X |
| 5 | `dataset/samples.csv` | | X | X | X |
| 6 | `audit_log` | X | | | |

### Tiến trình

1. Người dùng mở `/trash`; hệ thống đọc **hai thùng rác riêng** (nhãn và mẫu).
2. Chọn một hoặc nhiều mục.
3a. **Khôi phục:** hệ thống bỏ dấu xoá mềm; mục quay lại danh sách thường.
3b. **Xoá vĩnh viễn:** hệ thống hiện hộp thoại nêu **đúng phạm vi ảnh hưởng**, rồi
    xoá bản ghi **và tệp ở cả kho cục bộ lẫn Drive**.
4. Thao tác theo lô báo kết quả từng phần: *"{nhãn}: {n} thành công, {m} lỗi"*.

### Luồng ngoại lệ

| # | Tình huống | Thông báo |
|---|---|---|
| 1 | Không đọc được thùng rác mẫu | *"Không đọc được thùng rác mẫu"* |
| 2 | Không đọc được thùng rác nhãn | *"Không đọc được thùng rác nhãn"* |
| 3 | Thao tác lô hỏng một phần | *"{nhãn}: {n} thành công, {m} lỗi"* — báo **cả hai con số**, không gộp thành "thất bại" |
| 4 | Thao tác hỏng hoàn toàn | *"{nhãn} thất bại"* |

### Ràng buộc

* **BR-5.5** xoá mềm ở cả ba mức, khôi phục được **cho tới khi dọn hẳn**
* Thùng rác **theo phạm vi người dùng**; tab "Nhãn đã xóa" chỉ hiện với quản trị viên
* Xoá vĩnh viễn là thao tác **không hoàn tác được** → mọi hộp thoại đều nêu rõ
  điều đó bằng chữ **VIẾT HOA** và nêu số lượng cụ thể

**Một lỗi đã từng có ở đường này, ghi lại:** thao tác dọn theo **lớp** hoạt động
đúng, nhưng dọn theo **mẫu** từng gọi nhầm hàm xoá của kho ngoài (`delete_path`
thay vì `delete_file`), nên tệp trên Drive không bị xoá theo. Đây là kiểu lỗi mà
giao diện **không** phản ánh — bản ghi biến mất đúng như người dùng thấy, chỉ có
tệp là còn lại.

---

## CN2.7 — Xuất ảnh chụp bộ dữ liệu (UC213)

### Mục đích

Tạo một bản phát hành dữ liệu **tái lập được**: ghim phiên bản danh mục, có mã
băm, và **chỉ chứa những mẫu mà đồng thuận cho phép**.

### Điểm cuối API

Bộ định tuyến `dataset_exporter` — **KHÔNG được mount**. Tệp có đúng một điểm
cuối `POST /api/dataset/export`, nhưng nó không được `include_router` trong
[main.py](../../../backend/app/main.py), nên **không có URL nào gọi tới được**.

Đường xuất dữ liệu **đang chạy thật** là bản xuất theo tổ chức, đi qua bảng
`tenant_exports` và bộ định tuyến `tenants` (xem tệp Nghiệp vụ 5). Chức năng
mô tả ở mục này vì vậy phải đọc là **thiết kế**, không phải hiện trạng.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `samples` | | | | X |
| 2 | `classes` | | | | X |
| 3 | `signer_consents` | | | | X |
| 4 | `registry_versions` | X | | | X |
| 5 | `tenant_exports` | X | X | | X |
| 6 | Tệp `.npz` | | | | X |
| 7 | `audit_log` | X | | | |

### Tiến trình

1. Người dùng chọn phạm vi bộ dữ liệu (lớp, phương ngữ, hồ sơ nhận dạng).
2. Hệ thống **ghim phiên bản danh mục** hiện hành thành một ảnh chụp bất biến có
   mã băm nội dung.
3. Hệ thống chọn mẫu, **đọc mức đồng thuận trước khi lấy** — mẫu không đủ mức
   **không xuất hiện** trong bản phát hành.
4. Hệ thống dựng gói xuất và ghi kiểm toán.

### Ràng buộc

* **BR-4.4 / BR-4.5** phiên bản danh mục là ảnh chụp bất biến; bộ dữ liệu **ghim**
  vào một phiên bản cụ thể
* **BR-3.8** đồng thuận đọc **trước khi** lấy mẫu
* **BR-3.9** bản phát hành **đã tạo ra** không bị ảnh hưởng khi người ký rút đồng
  thuận sau đó — rút chỉ áp cho các bản phát hành **sau đó**

---

## Tổng kết ma trận chức năng ↔ use case của Nghiệp vụ 2

| Chức năng | Use case phủ | Màn hình chính |
|---|---|---|
| CN2.1 Thu mẫu từ camera | UC201, UC203, UC205 | `/upload` (tab camera) |
| CN2.2 Tải lên tệp video theo lô | UC202, UC203 | `/upload` (tab video) |
| CN2.3 Theo dõi trạng thái tác vụ | UC204 | nội tuyến |
| CN2.4 Duyệt và quản lý danh mục nhãn | UC206 | `/labels` |
| CN2.5 Chi tiết lớp và xem lại phiên thu | UC207, UC208, UC209, **UC210 ⚠** | `/labels/:id` |
| CN2.6 Thùng rác | UC211, UC212 | `/trash` |
| CN2.7 Xuất ảnh chụp bộ dữ liệu | UC213 | — |

**⚠ UC210:** đặc tả Chương 1 gọi là *"Gán lại người ký cho phiên thu"*; cài đặt
hiện có là *"Đổi nhãn cho lần quay"*. Xem phần cuối CN2.5.
