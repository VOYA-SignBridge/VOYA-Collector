# 10.5 Thiết kế chi tiết — Nghiệp vụ 5: Tổ chức và đăng ký dịch vụ

***8 use case** (UC501–UC508) cài đặt trên **28 điểm cuối** của hai bộ định tuyến
`tenants` và `billing`.*

Nghiệp vụ này trả lời: **ai thuộc về tổ chức nào, trong hạn mức nào?** Nó có **hai
màn hình cho hai vai khác nhau**, và ranh giới giữa chúng là ranh giới A7 ≠ A8 —
thứ không được vẽ sai.

---

## CN5.1 — Quản lý tổ chức của mình (UC501, UC502)

### Mục đích

Cho **quản trị tổ chức** điều hành đúng **một** tổ chức: thành viên, lời mời, gói
dịch vụ, và mang dữ liệu của tổ chức đi.

### Giao diện 1 — Tổ chức của tôi (`/settings/organization`, `OrganizationPage.tsx`, 938 dòng)

**Nhóm A — Trạng thái truy cập trang**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| A1 | Tiêu đề | **"Tổ chức của tôi"** — "Thành viên, lời mời, và mang dữ liệu của tổ chức đi." |
| A2 | Trạng thái chưa thuộc tổ chức | **"Tài khoản của bạn chưa thuộc tổ chức nào"** + *"Bạn vẫn đóng góp dữ liệu bình thường. Tổ chức là thứ cần khi bạn muốn quản lý một nhóm người thu, hạn mức riêng và bản xuất riêng."* |
| A3 | Trạng thái không phải quản trị | **"Bạn không phải quản trị viên của tổ chức này"** + *"Trang này dành cho người quản trị tổ chức. Bạn vẫn dùng được mọi tính năng đóng góp dữ liệu như bình thường — chỉ phần quản lý thành viên là do quản trị viên tổ chức phụ trách."* |

**Hai trạng thái A2 và A3 là ví dụ về từ chối quyền có tính xây dựng.** Cả hai đều
nói rõ **người dùng vẫn làm được gì**, thay vì chỉ nói họ không được vào. Một
thông báo "không có quyền" trần trụi để người dùng tưởng tài khoản mình hỏng.

**Nhóm B — Thông tin tổ chức**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| B1 | Huy hiệu trạng thái | **"Đang hoạt động"** / **"Đã tạm dừng"** |
| B2 | Dòng thông tin | **"Mã tổ chức"** |
| B3 | Dòng thông tin | **"Thành viên"** |
| B4 | Dòng thông tin | **"Lập ngày"** |
| B5 | Dòng thông tin | **"Định danh rút gọn"** |

**Nhóm C — Gói dịch vụ và tự động gia hạn**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| C1 | Tiêu đề khối | **"Gói dịch vụ"** — "Kỳ hạn hiện tại và thiết lập gia hạn của tổ chức." |
| C2 | Trạng thái chưa có gói | *"Tổ chức này chưa có đăng ký nào. Hãy liên hệ quản trị viên nền tảng."* |
| C3 | Dòng kỳ hạn | **"Còn {n} ngày · hết hạn {ngày}"**, hoặc **"Gói không có kỳ hạn"** |
| C4 | Công tắc | **"Tự động gia hạn"** |
| C5 | Mô tả trạng thái bật | *"Kỳ mới sẽ mở ngay khi kỳ này kết thúc."* |
| C6 | Mô tả trạng thái tắt | *"Kỳ này kết thúc là dừng — dữ liệu vẫn giữ, tổ chức chuyển sang chỉ đọc."* |
| C7 | Nút | **"Tắt tự gia hạn"** / **"Bật tự gia hạn"** |
| C8 | Hộp thoại xác nhận | **"Tắt tự động gia hạn?"** — *"Kỳ hiện tại **vẫn chạy hết** (tới {ngày}). Bạn không mất gì ngay bây giờ."* + nút **"Xác nhận tắt"** / **"Giữ nguyên"** |
| C9 | Ghi chú ân hạn | Nêu ba trạng thái bằng chữ in đậm: **chỉ đọc** · **vẫn còn nguyên** · **vẫn ghi được** / "hết thời gian ân hạn" |

**Nhóm C9 nói ra vòng đời đăng ký bằng đúng ba từ khoá mà người dùng cần:** dữ
liệu **vẫn còn nguyên**, quyền ghi **vẫn ghi được** trong ân hạn, và sau đó chuyển
**chỉ đọc**. Đây là chỗ dễ hứa quá hoặc doạ quá; giao diện chọn nói đúng từng mốc.

**Nhóm D — Thành viên**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| D1 | Tiêu đề khối | **"Thành viên"** — *"Vai quyết định người đó làm được gì với dữ liệu của tổ chức."* |
| D2 | Cột bảng | **"Người dùng"** |
| D3 | Nhãn bản thân | **"— bạn"** |
| D4 | Hộp chọn vai | Nhãn trợ năng **"Vai của {ai}"** |
| D5 | Nút | **"Gỡ"** |
| D6 | Giá trị dự phòng | **"(không tên)"** |
| D7 | Hộp thoại gỡ | **"Gỡ thành viên khỏi tổ chức?"** — *"**{tên}** sẽ mất quyền truy cập dữ liệu của tổ chức."* · *"Những mẫu họ đã đóng góp **vẫn ở lại** với tổ chức. Tài khoản của họ không bị xoá, và bạn có thể mời lại bất cứ lúc nào."* + **"Gỡ khỏi tổ chức"** / **"Giữ nguyên"** |

**Nhóm E — Lời mời**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| E1 | Tiêu đề khối | **"Lời mời"** — *"Người được mời tự tạo tài khoản bằng liên kết. Bạn không cần biết mật khẩu của họ."* |
| E2 | Ô nhập | **"Email người được mời"** |
| E3 | Hộp chọn vai | Vai dự kiến |
| E4 | Nút | **"Gửi lời mời"** |
| E5 | Danh sách chờ | **"{vai} · hết hạn {ngày}"**; rỗng thì *"Chưa có lời mời nào đang chờ."* |
| E6 | Nút | **"Thu hồi"** |
| E7 | Hộp thoại kết quả | **"Đã tạo lời mời"** + ô **"Liên kết mời"** |
| E8 | Cảnh báo gửi thư hỏng | Nêu trạng thái **"chưa gửi được thư"** |
| E9 | Nút chép | Thành công: *"Đã chép liên kết mời."*; hỏng: *"Trình duyệt không cho chép. Hãy bôi đen rồi chép tay."* |

**Thành phần E7 + E8 là một thiết kế chống hỏng im lặng.** Cấu hình máy chủ thư
sai làm thư mời **không gửi được mà không báo gì** — kiểu hỏng nguy hiểm nhất
trong nhóm tích hợp. Giao diện vì thế **luôn hiện liên kết mời** để quản trị viên
gửi tay được, và **nói rõ khi thư chưa gửi được** thay vì để họ tưởng đã xong.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `tenants` | | | | X |
| 2 | `role_assignments` | X | X *(đổi vai)* | X *(gỡ)* | X |
| 3 | `tenant_members` ⟨khung nhìn⟩ | | | | X |
| 4 | `tenant_invitations` | X | X *(thu hồi)* | | X |
| 5 | `tenant_subscriptions` | | X *(tự gia hạn)* | | X |
| 6 | `plans` | | | | X |
| 7 | `users` | | | | X |
| 8 | `audit_log` | X | | | |

### Tiến trình — mời một thành viên

1. Quản trị tổ chức nhập email và chọn vai dự kiến.
2. Hệ thống tạo lời mời (token lưu **dạng băm**), đặt hạn dùng.
3. Hệ thống gửi thư **và** hiện liên kết mời ngay trên màn hình.
4. Người được mời mở liên kết → CN1.2. **Lời mời chỉ tiêu thụ được khi tạo tài
   khoản mới, và chỉ với đúng địa chỉ đã nêu.**

### Luồng ngoại lệ

| # | Tình huống | Thông báo |
|---|---|---|
| 1 | Không đọc được thông tin tổ chức | *"Không đọc được thông tin tổ chức của bạn."* |
| 2 | Không tạo được lời mời | *"Không tạo được lời mời."* |
| 3 | Không thu hồi được lời mời | *"Không thu hồi được lời mời."* |
| 4 | Không đổi được vai | *"Không đổi được vai của thành viên này."* |
| 5 | Không gỡ được thành viên | *"Không gỡ được thành viên này."* |
| 6 | Không đổi được thiết lập gia hạn | *"Không đổi được thiết lập gia hạn."* |

### Ràng buộc

* **BR-1.4** quản trị tổ chức đưa người vào **chỉ bằng lời mời** — màn hình này
  **không có** ô nhập mã tài khoản để gán trực tiếp, và đó là điểm khác biệt cốt
  lõi với CN5.3
* **BR-1.3** A7 **không kế thừa** A8 và ngược lại
* **BR-8.2** trạng thái quản trị (đình chỉ) và trạng thái thương mại là hai trục
  khác nhau
* Gỡ thành viên **không xoá dữ liệu họ đã đóng góp** — và hộp thoại D7 nói rõ
  điều đó trước khi bấm

---

## CN5.2 — Gói cước, hạn mức và mức sử dụng (UC505, UC506)

### Mục đích

Cho tổ chức thấy **mình đang ở đâu so với hạn mức**, bằng số liệu đọc từ dữ liệu
thật chứ không từ một bộ đếm riêng.

### Giao diện 1 — Gói dịch vụ (`/settings/billing`, `BillingPage.tsx`, 270 dòng)

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| 1 | Tiêu đề | **"Gói dịch vụ"** — "Hạn mức và mức dùng của tổ chức" |
| 2 | Giá gói | **"{giá} /tháng"** |
| 3 | Nhãn không giới hạn | **"/ không giới hạn"** |
| 4 | Tiêu đề khối | **"Hạn mức"** |
| 5 | **Ghi chú nguồn số liệu** | *"Số liệu đọc trực tiếp từ dữ liệu hiện có, không phải từ một bộ đếm riêng."* |
| 6 | Tiêu đề khối | **"Mức dùng 30 ngày qua"** |
| 7 | **Ghi chú cách tính** | *"Dung lượng lấy theo lần đo gần nhất; các chỉ số còn lại là tổng cộng dồn."* |
| 8 | Chỉ số | **"Mẫu đã thu"** |
| 9 | Chỉ số | **"Lượt huấn luyện"** |
| 10 | Chỉ số | **"Thời gian huấn luyện"** — "{n} phút" hoặc "{n} giờ" |
| 11 | Chỉ số | **"Dung lượng"** — MB hoặc GB |
| 12 | Chỉ số | **"Người đóng góp"** |
| 13 | Banner dùng thử | *"Bản dùng thử kết thúc vào {ngày}. Liên hệ quản trị viên nền tảng để chuyển sang gói chính thức."* |
| 14 | Banner tạm ngưng | *"Tổ chức đang tạm ngưng: bạn vẫn xem được dữ liệu nhưng không thêm mới được. Vui lòng liên hệ quản trị viên nền tảng."* |
| 15 | Nút | **"Thử lại"** khi lỗi tải |

**Ghi chú số 5 và số 7 cùng phục vụ một mục tiêu: nói ra cách con số được tính.**
Số dùng để **chặn** ("đang dùng") đọc trực tiếp từ dữ liệu hiện có; số dùng để
**tính tiền** ("đã từng dùng") đọc từ `tenant_usage_daily`. Hai nguồn khác nhau,
**có chủ đích** — và giao diện nói rõ để người đọc không thắc mắc vì sao hai chỗ
lệch nhau.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `plans` | | | | X |
| 2 | `tenant_subscriptions` | | | | X |
| 3 | `tenant_usage_daily` | | | | X |
| 4 | `samples` · `training_jobs` | | | | X *(đếm)* |
| 5 | `tenants` | | | | X |

### Ràng buộc

* **BR-8.1** giá trị **rỗng** ở cột hạn mức nghĩa là **không giới hạn**, không
  phải "bằng không" — thành phần số 3 hiển thị đúng nghĩa đó
* **BR-8.4** hai nguồn số liệu khác nhau cho "chặn" và "tính tiền"
* **BR-8.5** hệ thống **không thu tiền** — không có cổng thanh toán; giá hiển thị
  là thông tin gói, không phải một luồng mua

---

## CN5.3 — Quản trị tổ chức toàn nền tảng (UC503, UC504, UC507)

### Mục đích

Cho **quản trị nền tảng** tạo tổ chức, gắn tài khoản, và chuyển tổ chức nhà —
những việc mà quản trị tổ chức **không được phép làm**.

### Giao diện 1 — Tổ chức (`/admin/tenants`, `AdminTenantsPage.tsx`, 637 dòng)

**Nhóm A — Danh sách và tạo mới**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| A1 | Tiêu đề | **"Tổ chức"** |
| A2 | Ô tích | **"Hiện cả tổ chức đã xoá mềm"** |
| A3 | Nút | **"Tải lại"** |
| A4 | Tiêu đề khối | **"Tạo tổ chức mới"** |
| A5 | Ô nhập | Nhãn trợ năng **"Mã tổ chức"** |
| A6 | Ô nhập | **"Tên hiển thị"** |
| A7 | Nút | **"Tạo"** |
| A8 | **Cảnh báo bất biến** | *"Mã tổ chức là khoá dùng trong mọi bảng dữ liệu và **không đổi được** về sau."* |
| A9 | Cột bảng | **"Mã"** · **"Tên"** · **"Thành viên"** · **"Trạng thái"** · **"Tạo lúc"** |
| A10 | Nút mở/đóng | **"Quản lý"** / **"Đóng"** |
| A11 | Trạng thái rỗng | *"Chưa có tổ chức nào."* |

**Cảnh báo A8 là cảnh báo quan trọng nhất của màn hình này.** Mã tổ chức đi vào
**mọi bảng dữ liệu** và vào **khoá ngoại ghép**; đổi nó về sau là đổi một khoá đã
được 34 bảng tham chiếu. Nói trước ở đúng ô nhập rẻ hơn nhiều so với sửa sau.

**Nhóm B — Thành viên của một tổ chức**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| B1 | Tiêu đề khối | **"Thành viên — {mã tổ chức}"** |
| B2 | Hộp chọn vai | Nhãn trợ năng **"Vai của {ai}"** |
| B3 | Nút | **"Gỡ"** |
| B4 | Ô nhập | **"ID tài khoản có sẵn"** (nhãn trợ năng "ID tài khoản") |
| B5 | Hộp chọn | Nhãn trợ năng **"Vai khi gắn"** |
| B6 | Nút | **"Gắn tài khoản"** |
| B7 | Nút | Chuyển **tổ chức nhà** của tài khoản |
| B8 | Trạng thái rỗng | *"Chưa có thành viên nào."* |

**Thông báo kết quả:** *"Đã tạo tổ chức"* · *"Đã đổi vai"* · *"Đã gỡ thành viên"* ·
*"Đã gắn tài khoản vào tổ chức"* · *"Đã chuyển tổ chức nhà của tài khoản"*.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `tenants` | X | X | X *(mềm)* | X |
| 2 | `role_assignments` | X | X | X | X |
| 3 | `users` | | X *(tổ chức nhà)* | | X |
| 4 | `tenant_subscriptions` | X | X | | X |
| 5 | `audit_log` | X | | | |

### Ràng buộc — ranh giới A7 ≠ A8

| | CN5.1 (quản trị tổ chức) | CN5.3 (quản trị nền tảng) |
|---|---|---|
| Đưa người vào bằng | **Lời mời** (E2–E4) | **Gắn trực tiếp theo ID tài khoản** (B4–B6) |
| Phạm vi | Đúng một tổ chức | Mọi tổ chức |
| Tạo tổ chức mới | Không | Có (A4–A7) |

**Vì sao hai màn hình phải khác nhau ở đúng điểm này:** mã tài khoản **không phải
bí mật**. Nếu ô "ID tài khoản có sẵn" (B4) xuất hiện trên màn hình của quản trị tổ
chức, họ kéo được **bất kỳ ai trên hệ thống** vào tổ chức của mình mà người kia
không hay biết. Đường đưa người vào của A7 vì thế **bắt buộc** là lời mời — thứ
đòi hỏi chính người được mời hành động (BR-1.4).

---

## CN5.4 — Xuất dữ liệu và dọn sạch dữ liệu tổ chức (UC508)

### Mục đích

Cho tổ chức **mang dữ liệu của mình đi**, và — ở đầu kia — cho phép xoá sạch dữ
liệu của một tổ chức khi kết thúc quan hệ.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `tenant_exports` | X | X *(trạng thái, hạn tải)* | | X |
| 2 | `tenant_purges` | X | X *(xác nhận)* | | X |
| 3 | `samples` · `classes` · `capture_sessions` | | | X **(dọn sạch)** | X |
| 4 | Tệp `.npz` + kho ngoài | | | X | X |
| 5 | `audit_log` | X | | | |

### Tiến trình — dọn sạch dữ liệu tổ chức

1. Quản trị viên yêu cầu dọn sạch.
2. Hệ thống **đòi xác thực lại trong phiên** — đây là một trong ba thao tác không
   hoàn tác được (BR-9.1).
3. Hệ thống ghi yêu cầu vào `tenant_purges` kèm người yêu cầu và thời điểm.
4. Hệ thống xoá dữ liệu ở **cả hai mặt phẳng lưu trữ**.

### Ràng buộc

* **BR-9.1** dọn sạch dữ liệu tổ chức đòi **xác thực lại trong phiên**
* **BR-9.6** dữ liệu đã công bố sang mặt phẳng dùng chung **không rút lại được**
  bằng một nút bấm — dọn sạch không chạm tới phần đã công bố
* **Khoảng trống đã biết:** `tenant_purges` **không bật** chính sách bảo mật mức
  hàng, nên một quản trị viên nền tảng đọc được toàn bộ lịch sử yêu cầu dọn của
  mọi tổ chức. Điều này đúng với vai đó, **song không có tầng cưỡng chế nào đứng
  sau** — đã ghi vào phần hạn chế

---

## Tổng kết ma trận chức năng ↔ use case của Nghiệp vụ 5

| Chức năng | Use case phủ | Màn hình chính |
|---|---|---|
| CN5.1 Quản lý tổ chức của mình | UC501, UC502 | `/settings/organization` |
| CN5.2 Gói cước, hạn mức, mức dùng | UC505, UC506 | `/settings/billing` |
| CN5.3 Quản trị tổ chức toàn nền tảng | UC503, UC504, UC507 | `/admin/tenants` |
| CN5.4 Xuất và dọn sạch dữ liệu tổ chức | UC508 | `/settings/organization` (khối xuất) |
