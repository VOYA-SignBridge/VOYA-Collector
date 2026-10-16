# Từ điển dữ liệu — Nhóm M1: Danh tính & Truy cập

*7 bảng · 56 cột. Trích từ CSDL đang chạy ngày 18/08/2026.
Quy ước đọc bảng: xem [DD_00_QUY_UOC_VA_MUC_LUC.md](DD_00_QUY_UOC_VA_MUC_LUC.md).*

**Đặc điểm chung của nhóm:** đây là nhóm **cố ý không phủ ranh giới tổ chức hoàn
toàn**. Bảng `users` phải truy vấn được **trước khi** biết tổ chức — chính lúc
đăng nhập. Sáu bảng còn lại là **bảng phụ thuộc tài khoản**, không mang `tenant_id`
và không bật RLS; chúng được bảo vệ bằng khoá ngoại tới `users` cộng kiểm tra ở
tầng ứng dụng.

**Mọi token và mã một lần trong nhóm này đều lưu ở dạng BĂM**, không lưu giá trị gốc.

---

## 1.1 Bảng `users` — Tài khoản

**Khoá chính:** `id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 15 · **Số hàng
(10/08/2026):** 10

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| id | uuid | — | Primary key | Định danh tài khoản, sinh tự động |
| username | text | — | Not null, Unique | Tên đăng nhập; **được chép vào từng mẫu lúc ghi**, nên đổi tên lan sang 5 chỗ khác |
| email | text | — | Not null, Unique, Check | Địa chỉ thư điện tử; là đường khôi phục khi quên mật khẩu |
| password_hash | text | — | Not null | **Mã băm có muối** của mật khẩu (bcrypt); không có đường đọc ngược |
| is_active | boolean | — | Not null, Default true | Tài khoản còn hiệu lực hay đã vô hiệu hoá |
| is_admin | boolean | — | Not null, Default false | **Cờ quản trị nền tảng** — đây là thứ phân biệt tác nhân A8 với A7 |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm tạo tài khoản |
| role_id | uuid | — | Null, Foreign key → roles.role_id | Vai kế thừa từ mô hình cũ; mô hình hiện hành gán vai qua `role_assignments` |
| phone_number | varchar | 20 | Null, Unique | Số điện thoại; kênh xác thực thứ hai |
| updated_at | timestamptz | — | Null | Lần sửa hồ sơ gần nhất |
| deleted_at | timestamptz | — | Null | **Cờ xoá mềm** — rỗng nghĩa là chưa xoá |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức nhà của tài khoản |
| email_verified_at | timestamptz | — | Null | Thời điểm xác minh email; rỗng nghĩa là **chưa xác minh** |
| phone_verified_at | timestamptz | — | Null | Thời điểm xác minh số điện thoại |
| sessions_invalid_before | timestamptz | — | Null | **Mốc thu hồi hàng loạt**: mọi phiên cấp trước mốc này bị coi là hết hiệu lực — đây là cơ chế của mức thu hồi thứ hai và thứ ba |

**Ghi chú thiết kế.** Chính sách RLS của bảng này **không thể** thuần theo tổ chức:
truy vấn tìm tài khoản lúc đăng nhập chạy **trước khi** ngữ cảnh tổ chức tồn tại.
Đây là chỗ sinh ra cái bẫy *"0 hàng bị đọc thành không có gì"* — đã mắc **ba lần
trong hai ngày**.

**Cột `sessions_invalid_before` đáng nói riêng:** nó biến việc thu hồi *n* phiên
thành một phép ghi **một** giá trị, thay vì phải cập nhật *n* hàng trong
`refresh_tokens`. Đổi mật khẩu hoặc đình chỉ tài khoản chỉ cần đẩy mốc này lên.

---

## 1.2 Bảng `refresh_tokens` — Phiên đăng nhập

**Khoá chính:** `token_hash` · **RLS:** — không bật · **Số cột:** 8 · **Số hàng
(10/08/2026):** 107

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| token_hash | text | — | Primary key | **Mã băm** của token làm mới; giá trị gốc không lưu |
| user_id | uuid | — | Not null, Foreign key → users.id | Chủ sở hữu phiên |
| expires_at | timestamptz | — | Not null | Thời điểm token hết hạn |
| revoked_at | timestamptz | — | Null | Cờ thu hồi; rỗng nghĩa là còn hiệu lực |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm cấp token |
| family_id | uuid | — | Null | **Định danh chuỗi xoay token**: mọi token sinh ra từ một lần đăng nhập chia sẻ giá trị này |
| replaced_by | text | — | Null | Mã băm của token thay thế khi xoay — dựng thành chuỗi để truy vết |
| reuse_detected_at | timestamptz | — | Null | Thời điểm phát hiện **tái sử dụng** một token đã bị thay thế |

**Ghi chú thiết kế — ba cột cuối là hạ tầng cho một cơ chế chưa hoàn tất.**
`family_id`, `replaced_by` và `reuse_detected_at` là bộ ba chuẩn để phát hiện tái
sử dụng token làm mới: nếu một token đã bị thay thế lại được dùng, đó là dấu hiệu
token bị đánh cắp, và cả **chuỗi** (`family_id`) phải bị thu hồi. Lược đồ **đã có
đủ cột**, nhưng cơ chế phát hiện **chưa được cưỡng chế ở tầng ứng dụng** — đây là
khoảng trống đã biết, ghi ở `docs/needFix/`.

Refresh token **xoay ở mỗi lần dùng**, kèm một cửa sổ ân hạn rất ngắn cho lần xoay
trước, để hai tab của cùng một người không đá nhau ra khỏi hệ thống.

---

## 1.3 Bảng `password_reset_tokens` — Token đặt lại mật khẩu

**Khoá chính:** `token_hash` · **RLS:** — không bật · **Số cột:** 5 · **Số hàng
(10/08/2026):** 7

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| token_hash | text | — | Primary key | **Mã băm** của token trong liên kết đặt lại mật khẩu |
| user_id | uuid | — | Not null, Foreign key → users.id | Tài khoản được đặt lại |
| expires_at | timestamptz | — | Not null | Hạn dùng của liên kết |
| used_at | timestamptz | — | Null | Cờ đã dùng — bảo đảm token **dùng một lần** |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm phát hành |

**Ghi chú thiết kế.** Liên kết đặt lại chỉ trỏ tới **danh sách máy chủ được phép**
(`deploy/public_hosts.txt`); tiêu đề `Host` giả mạo không đổi được đích (NFR-C8).

---

## 1.4 Bảng `verification_codes` — Mã xác thực liên hệ

**Khoá chính:** `challenge_id` · **RLS:** — không bật · **Số cột:** 11 · **Số hàng
(10/08/2026):** 2

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| challenge_id | uuid | — | Primary key | Định danh một lượt thử thách xác thực |
| user_id | uuid | — | Null, Foreign key → users.id | Tài khoản liên quan; rỗng khi lượt xác thực xảy ra **trước** lúc có tài khoản |
| purpose | text | — | Not null, Check | Mục đích: xác minh liên hệ, khôi phục tài khoản, đổi email… |
| channel | text | — | Not null, Check | **Kênh gửi**: thư điện tử hoặc tin nhắn |
| destination | text | — | Not null | Địa chỉ đích thật sự nhận mã |
| code_hash | text | — | Not null | **Mã băm** của mã sáu chữ số |
| attempts | integer | 32 | Not null, Default 0, Check | Số lần đã nhập sai |
| max_attempts | integer | 32 | Not null, Default 5, Check | Trần số lần thử — **năm lần**, sau đó phải xin mã mới |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm gửi mã |
| expires_at | timestamptz | — | Not null | Hạn dùng của mã |
| consumed_at | timestamptz | — | Null | Cờ đã tiêu; mã **tiêu ở bước xác nhận**, không phải ở bước cuối |

**Ghi chú thiết kế.** Cặp `attempts` / `max_attempts` được ràng buộc bằng `CHECK`
ở tầng CSDL chứ không chỉ kiểm ở ứng dụng, nên không có đường ghi nào vượt trần
được. Con số 5 hiển thị nguyên văn trên giao diện: *"Nhập sai quá năm lần thì phải
xin mã mới."*

---

## 1.5 Bảng `user_totp` — Bí mật xác thực hai bước

**Khoá chính:** `user_id` · **RLS:** — không bật · **Số cột:** 5

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| user_id | uuid | — | Primary key, Foreign key → users.id | Tài khoản sở hữu — quan hệ **1:1**, mỗi tài khoản một bí mật |
| secret_enc | text | — | Not null | Bí mật TOTP **đã mã hoá** (không phải băm — cần giải để sinh mã đối chiếu) |
| confirmed_at | timestamptz | — | Null | Thời điểm bật thật sự; rỗng nghĩa là **đã ghi danh nhưng chưa xác nhận** |
| last_used_step | bigint | 64 | Null | Chỉ số bước thời gian TOTP đã dùng gần nhất — **chống phát lại**: một mã đã dùng không dùng lại được trong cùng cửa sổ |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm ghi danh |

**Ghi chú thiết kế — đây là bảng duy nhất trong nhóm lưu giá trị MÃ HOÁ thay vì
BĂM.** Lý do kỹ thuật: TOTP cần bí mật gốc để tự sinh mã và so sánh; băm một chiều
không dùng được. Hệ quả vận hành: **thiếu khoá mã hoá thì không đọc được trạng thái
hai bước**, và khi đó hệ thống **từ chối đăng nhập bằng lỗi máy chủ** thay vì bỏ
qua lớp bảo vệ thứ hai — nguyên tắc *không đọc được trạng thái bảo mật thì đóng,
không mở*.

`last_used_step` là cột chống phát lại: không có nó, một mã chụp được trên vai
người dùng vẫn dùng lại được trong 30 giây còn lại của cửa sổ.

---

## 1.6 Bảng `user_recovery_codes` — Mã khôi phục

**Khoá chính:** `code_hash` · **RLS:** — không bật · **Số cột:** 4

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| code_hash | text | — | Primary key | **Mã băm** của một mã khôi phục |
| user_id | uuid | — | Not null, Foreign key → users.id | Tài khoản sở hữu |
| used_at | timestamptz | — | Null | Cờ đã dùng — mỗi mã **dùng được một lần** |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm cấp bộ mã |

**Ghi chú thiết kế.** Khoá chính là **mã băm**, nên hai mã trùng nhau không tồn tại
được. Giao diện nói rõ: *"Đây là lần duy nhất chúng hiển thị… chúng là đường vào
duy nhất nếu bạn mất điện thoại."* Cấp lại bộ mã **huỷ toàn bộ mã cũ ngay lập tức**.

---

## 1.7 Bảng `user_action_passcodes` — Mã xác thực lại cho thao tác nhạy cảm

**Khoá chính:** `user_id` · **RLS:** — không bật · **Số cột:** 8

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| user_id | uuid | — | Primary key, Foreign key → users.id | Tài khoản sở hữu — quan hệ **1:1** |
| passcode_hash | text | — | Not null | **Mã băm** của mã xác thực lại |
| status | text | — | Not null, Default 'ACTIVE', Check | Trạng thái mã: đang hiệu lực / đã khoá / đã thu hồi |
| failed_count | smallint | 16 | Not null, Default 0, Check | Số lần nhập sai liên tiếp |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm đặt mã |
| updated_at | timestamptz | — | Not null, Default now() | Lần đổi gần nhất |
| locked_until | timestamptz | — | Null | Khoá tạm sau khi nhập sai nhiều lần |
| revoked_at | timestamptz | — | Null | Cờ thu hồi vĩnh viễn |

**Ghi chú thiết kế.** Bảng này phục vụ cơ chế **"thao tác không hoàn tác được đòi
xác thực lại trong phiên"** (NFR-C5), áp cho **ba use case**: dọn sạch dữ liệu tổ
chức · công bố văn bản pháp lý · đổi gói cước.

Việc có **cả** `locked_until` (khoá tạm, tự mở) lẫn `revoked_at` (thu hồi vĩnh
viễn) là chủ ý: nhập sai vài lần là sự cố thao tác, còn thu hồi là quyết định. Gộp
hai thứ vào một cột sẽ làm mất khả năng phân biệt.

---

## Tổng kết quan hệ trong nhóm M1

```
users (1) ──< refresh_tokens          (n phiên trên một tài khoản)
users (1) ──< password_reset_tokens
users (1) ──< verification_codes      (user_id CÓ THỂ RỖNG — lượt xác thực trước khi có tài khoản)
users (1) ──1 user_totp               (1:1)
users (1) ──< user_recovery_codes
users (1) ──1 user_action_passcodes   (1:1)
users (n) ──> tenants                 (tổ chức nhà)
users (n) ──> roles                   (vai kế thừa từ mô hình cũ)
```

| Đặc điểm | Số bảng |
|---|:--:|
| Bảng có `tenant_id` | 1 (`users`) |
| Bảng bật RLS | 1 (`users`) |
| Bảng lưu giá trị **băm** | 5 |
| Bảng lưu giá trị **mã hoá** | 1 (`user_totp`) |
| Quan hệ 1:1 với `users` | 2 (`user_totp`, `user_action_passcodes`) |
