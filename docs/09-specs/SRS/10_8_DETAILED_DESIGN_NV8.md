# 10.8 Thiết kế chi tiết — Nghiệp vụ 8: Hỗ trợ và tích hợp

***6 use case** (UC801–UC806) cài đặt trên **22 điểm cuối** của ba bộ định tuyến
`support`, `notifications`, `integrations`.*

Nghiệp vụ vành ngoài. Nó trả lời hai câu: **hỏng thì kêu ai**, và **máy khác nối
vào thế nào**.

---

## CN8.1 — Phiếu hỗ trợ của người dùng (UC801)

### Mục đích

Cho người dùng hỏi bất cứ điều gì và **nhận trả lời ngay** từ trợ lý tự động, đồng
thời để lại việc cho người trực xử lý khi sẵn sàng.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/api/v1/support/tickets` | Danh sách hội thoại của mình |
| `GET` | `/api/v1/support/tickets/{id}` | Mở một hội thoại |
| `POST` | `/api/v1/support/tickets` | Mở hội thoại mới |
| `POST` | `/api/v1/support/tickets/{id}/reply` | Gửi lời nhắn |
| `GET` | `/api/v1/support/starters` | Câu hỏi mở đầu gợi ý |
| `GET` | `/api/v1/support/queue` | Hàng đợi (dành cho người trực) |

### Giao diện 1 — Hỗ trợ (`/settings/support`, `SupportPage.tsx`, 524 dòng)

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| 1 | Tiêu đề | **"Hỗ trợ"** — *"Trợ lý tự động trả lời ngay. Người trực cũng nhận được thông báo và sẽ vào khi sẵn sàng."* |
| 2 | Nút | **"Hội thoại mới"** |
| 3 | Danh sách bên trái | **"Hội thoại của tôi"** |
| 4 | Trạng thái rỗng danh sách | *"Chưa có hội thoại nào. Bấm "Hội thoại mới" để bắt đầu."* |
| 5 | Nút quay lại (màn hẹp) | **"← Danh sách"** |
| 6 | Ô nhập tiêu đề | Kiểm: *"Còn thiếu tiêu đề ở ô trên (từ 5 ký tự)."* |
| 7 | Ô soạn tin | Kiểm: *"Mô tả cần ít nhất 10 ký tự để người trực hiểu chuyện gì đang xảy ra."* |
| 8 | Nút gợi ý | **"Trả lời nhanh"** |
| 9 | Nút | **"Đóng hội thoại này"** |
| 10 | Thông báo đã đóng | *"Hội thoại này đã đóng. Nếu vấn đề còn, hãy mở hội thoại mới."* |
| 11 | Hướng dẫn khi chưa chọn | *"Chọn một hội thoại bên trái, hoặc mở hội thoại mới để hỏi bất cứ điều gì."* |
| 12 | Màn chờ | "Đang tải…" |

**Hai thông báo kiểm hợp lệ (6 và 7) nêu lý do chứ không chỉ nêu quy tắc.** *"để
người trực hiểu chuyện gì đang xảy ra"* giải thích **vì sao** cần 10 ký tự — người
dùng vì thế viết thêm nội dung thật thay vì gõ bừa cho đủ.

**Thành phần số 1 nói rõ hai lớp trả lời**: trợ lý tự động trả lời ngay, người
trực vào sau. Không nói trước điều này thì một câu trả lời tự động sẽ bị hiểu là
câu trả lời cuối cùng.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `support_tickets` | X | X *(trạng thái, đóng)* | | X |
| 2 | `support_messages` | X | | | X |
| 3 | `notifications` | X | | | X |
| 4 | `users` | | | | X |

### Luồng ngoại lệ

| # | Tình huống | Thông báo |
|---|---|---|
| 1 | Không tải được danh sách | *"Không tải được danh sách hội thoại."* |
| 2 | Không mở được hội thoại | *"Không mở được hội thoại."* |
| 3 | Không gửi được tin | *"Không gửi được lời nhắn."* |
| 4 | Không đóng được hội thoại | *"Không đóng được hội thoại."* |

### Ràng buộc

* **BR-2.1** hội thoại thuộc phạm vi tổ chức; `support_tickets` và
  `support_messages` đều bật chính sách bảo mật mức hàng
* Hội thoại đã đóng **không mở lại được** — phải mở hội thoại mới (thành phần 10)

---

## CN8.2 — Hàng đợi hỗ trợ và thư thông báo (UC802, UC803)

### Mục đích

Cho người trực thấy việc cần làm, và **không để một phiếu nằm im vì không ai biết
nó tồn tại**.

### Giao diện 1 — Hàng đợi hỗ trợ (`/admin/support`, `AdminSupportPage.tsx`)

Đọc `/api/v1/support/queue`; hiển thị phiếu theo thứ tự ưu tiên và thời gian chờ.

### Hai loại thư — khác nhau về bản chất, không được gộp

| Loại | Bản chất | Kích hoạt bởi |
|---|---|---|
| Thư **phiếu mới** | **Sự kiện** | Một phiếu được tạo → gửi một lần |
| Thư **tồn đọng** | **Trạng thái** | Hàng đợi quá **5 giờ** hoặc quá **10 tin** chưa trả lời |

Gộp hai loại này sẽ cho ra một trong hai kết quả sai: hoặc gửi lặp thư phiếu mới,
hoặc không bao giờ nhắc lại một hàng đợi đang ứ.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `support_tickets` | | X | | X |
| 2 | `support_messages` | X | | | X |
| 3 | `event_outbox` | X | X | | X |
| 4 | `notifications` | X | | | X |

### Ràng buộc

* **Một bẫy đã làm thư KHÔNG BAO GIỜ gửi:** so sánh `uuid = text` trong truy vấn
  chọn người nhận. Truy vấn không báo lỗi, chỉ trả 0 hàng — nên thư im lặng không
  gửi. Đây là biến thể của cùng một kiểu hỏng với *"0 hàng bị đọc thành không có
  gì"*
* Người trực (A9) hiện **dùng chung quyền quản trị nền tảng** (🟡) — chưa có vai
  riêng

---

## CN8.3 — Thông báo trong ứng dụng (UC803)

### Mục đích

Đưa những việc người dùng **cần biết** tới trước mắt họ, mà không phụ thuộc vào
thư điện tử — vốn có thể không gửi được.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/api/v1/notifications` | Danh sách thông báo |
| `GET` | `/api/v1/notifications/unread-count` | Số chưa đọc (cho chuông) |
| `POST` | `/api/v1/notifications/read` | Đánh dấu một mục đã đọc |
| `POST` | `/api/v1/notifications/read-all` | Đánh dấu tất cả |

### Giao diện 1 — Thông báo (`/notifications`, `NotificationsPage.tsx`, 196 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề | — | **"Thông báo"** |
| 2 | Phụ đề | — | **"{n} thông báo chưa đọc"** hoặc **"Bạn đã đọc hết"** |
| 3 | Bộ lọc | tắt | **"Chỉ chưa đọc"** |
| 4 | Nút | — | **"Đánh dấu tất cả đã đọc"** |
| 5 | Nhãn mục mới | — | **"Mới"** |
| 6 | Trạng thái rỗng | — | **"Chưa có thông báo nào"** / **"Không có thông báo chưa đọc"** + *"Khi có việc cần bạn biết — gói dịch vụ, bảo mật, huấn luyện — nó sẽ xuất hiện ở đây."* |
| 7 | Màn chờ | — | "Đang tải…" |

**Thành phần số 6 liệt kê đúng ba nguồn thông báo** (gói dịch vụ, bảo mật, huấn
luyện), nên trạng thái rỗng không chỉ nói "chưa có gì" mà còn nói **khi nào sẽ
có**.

### Giao diện 2 — Chuông thông báo (`NotificationBell.tsx`)

Hiển thị số chưa đọc trên thanh điều hướng, đọc từ `/unread-count`.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `notifications` | X | X *(`read_at`)* | | X |

### Luồng ngoại lệ

| # | Tình huống | Thông báo |
|---|---|---|
| 1 | Không tải được | *"Không tải được thông báo. Vui lòng thử lại."* |
| 2 | Không đánh dấu được | *"Không đánh dấu được. Vui lòng thử lại."* |

### Ràng buộc

* **NFR-R7** tác vụ nền thất bại phải thông báo tới **chủ sở hữu tác vụ** — đường
  này là nơi thông báo đó xuất hiện

---

## CN8.4 — Khoá API cho ứng dụng bên thứ ba (UC804, UC805)

### Mục đích

Cho hệ thống ngoài gọi API trong **phạm vi giới hạn**, mà không phải chia sẻ mật
khẩu tài khoản.

### Giao diện 1 — Khoá API (`/settings/integrations`, `IntegrationsPage.tsx`, 538 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề khối | — | **"Khoá API"** |
| 2 | Ô nhập | rỗng | **"Tên gợi nhớ"**, gợi ý "vd: đồng bộ đêm" |
| 3 | Hộp chọn quyền | — | **"Quyền"** → **"Chỉ đọc"** / **"Đọc và ghi"** |
| 4 | Nút | — | **"Cấp khoá mới"** |
| 5 | **Hộp thoại hiện khoá một lần** | — | *"Đây là lần **duy nhất** giá trị này hiện ra. Máy chủ chỉ lưu bản băm, nên không ai — kể cả quản trị viên — đọc lại được. Nếu mất, hãy thu hồi và cấp lại."* |
| 6 | Nút | — | **"Sao chép"**; hỏng: *"Trình duyệt không cho sao chép tự động — hãy bôi đen và copy tay."* |
| 7 | Nút đóng | — | **"Tôi đã lưu"**; gợi ý khi chưa chép: **"Hãy sao chép trước khi đóng"** |
| 8 | Cột bảng | — | **"Khoá"** · **"Tên"** · **"Quyền"** · **"Dùng lần cuối"** |
| 9 | Nút thu hồi | — | Xác nhận: *"Thu hồi khoá {prefix}…? Mọi hệ thống đang dùng nó sẽ mất quyền ngay."* |
| 10 | Trạng thái rỗng | — | *"Chưa có khoá nào."* |

**Thành phần số 5 là mẫu mực của việc nói đúng cơ chế thay vì nói một lời cảnh
báo chung.** Nó nêu **lý do kỹ thuật** (máy chủ chỉ lưu bản băm), **hệ quả** (không
ai đọc lại được, **kể cả quản trị viên**), và **đường xử lý** (thu hồi và cấp lại).
Ba phần đó biến một hộp thoại "hãy lưu lại" thành một lời giải thích kiểm chứng được.

**Thành phần số 7 chặn một lỗi thao tác thật:** nút đóng có gợi ý *"Hãy sao chép
trước khi đóng"* cho tới khi người dùng đã bấm chép — vì đóng nhầm là mất khoá.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `api_keys` | X | X *(`revoked_at`, `last_used_at`)* | | X |
| 2 | `audit_log` | X | | | |

### Luồng ngoại lệ

| # | Tình huống | Thông báo |
|---|---|---|
| 1 | Không tải được danh sách | *"Không tải được danh sách khoá API."* |
| 2 | Không thu hồi được | *"Không thu hồi được khoá."* |
| 3 | Trình duyệt chặn sao chép | Hướng dẫn chép tay (thành phần 6) |

### Ràng buộc

* **BR-9.5** khoá lưu **dạng băm**; mất thì **tạo mới**, không khôi phục
* Bảng chỉ hiển thị **tiền tố** khoá (`{prefix}…`), đủ để nhận ra mà không đủ để dùng
* Thu hồi có hiệu lực **ngay** — hộp thoại số 9 nói rõ *"Mọi hệ thống đang dùng nó
  sẽ mất quyền ngay."*
* Khoá thuộc về **một tổ chức**; `api_keys` bật chính sách bảo mật mức hàng

---

## CN8.5 — Webhook (UC806)

### Mục đích

Đẩy sự kiện ra hệ thống ngoài thay vì bắt họ hỏi liên tục.

### Giao diện

Khối webhook trên cùng trang `/settings/integrations`: đăng ký URL nhận, bí mật
ký, danh sách sự kiện quan tâm, và lịch sử gửi.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `webhook_endpoints` | X | X | X | X |
| 2 | `webhook_deliveries` | X | X *(số lần thử)* | | X |
| 3 | `event_outbox` | X | X | | X |

### Tiến trình

1. Sự kiện nghiệp vụ xảy ra → ghi vào **`event_outbox` trong cùng giao dịch** với
   thay đổi dữ liệu.
2. Tiến trình nền đọc hộp thư đi và gửi tới các điểm nhận đã đăng ký, **kèm chữ ký**.
3. Kết quả mỗi lần gửi (mã trả về, số lần thử) ghi vào `webhook_deliveries`.

**Ghi vào hộp thư đi trong cùng giao dịch là điểm cốt lõi:** nó bảo đảm không có
trạng thái *"dữ liệu đã đổi nhưng sự kiện chưa được ghi nhận"* — thứ không sửa
được về sau vì không ai biết nó đã xảy ra.

### Ràng buộc

* `webhook_endpoints` và `webhook_deliveries` đều bật chính sách bảo mật mức hàng
* **Trạng thái thực tế:** cả hai bảng có **0 hàng** tại ảnh chụp 10/08/2026 — cơ
  chế đã cài đặt nhưng **chưa có người dùng thật**. Bản SRS ghi nhận điều đó thay
  vì mô tả như một tính năng đang vận hành

---

## Tổng kết ma trận chức năng ↔ use case của Nghiệp vụ 8

| Chức năng | Use case phủ | Màn hình chính |
|---|---|---|
| CN8.1 Phiếu hỗ trợ của người dùng | UC801 | `/settings/support` |
| CN8.2 Hàng đợi hỗ trợ và thư | UC802, UC803 | `/admin/support` |
| CN8.3 Thông báo trong ứng dụng | UC803 | `/notifications` |
| CN8.4 Khoá API | UC804, UC805 | `/settings/integrations` |
| CN8.5 Webhook | UC806 | `/settings/integrations` |
