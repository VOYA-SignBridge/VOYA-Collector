# PHỤ LỤC A-2: TỪ ĐIỂN DỮ LIỆU (DATA DICTIONARY)

> **Nguồn:** `information_schema.columns`, `pg_constraint`, `pg_attribute` và
> `pg_class` trên cơ sở dữ liệu `signdb` **đang chạy**, đo ngày **18/08/2026**,
> phiên bản lược đồ **5**. Không dòng nào trong phụ lục này được suy đoán từ mã
> nguồn hay từ trí nhớ.

> **Phạm vi:** đủ **59 bảng** và **636 cột**, chia theo bảy nhóm mô-đun đã dùng ở
> Chương 3 §3.4.1. Mỗi bảng một mục riêng, trình bày đầy đủ, không rút gọn.

---

## Quy ước trình bày

**Cột `Ràng buộc`** ghi đủ mọi ràng buộc mà trường tham gia, theo thứ tự: khoá
chính, khoá ngoại kèm bảng đích, ràng buộc duy nhất, tính bắt buộc, giá trị mặc
định, và tập giá trị hợp lệ nếu trường có ràng buộc kiểm tra. Ghi `—` khi trường
không tham gia ràng buộc nào.

**Ghi chú *(khoá ghép)*** đánh dấu khoá ngoại gồm nhiều cột. Đây là cơ chế làm
việc trỏ chéo tổ chức trở nên **bất khả thi ở tầng ràng buộc**, chứ không chỉ bị
chặn ở tầng ứng dụng — và là điểm thiết kế quan trọng nhất của lược đồ này.

**Trường cho phép để trống** đều được nói rõ trong phần diễn giải rằng **giá trị
trống nghĩa là gì**. Một trường để trống mà không có định nghĩa nghiệp vụ là một
trường sẽ bị đọc sai.

**Số thứ tự** lấy theo `ordinal_position` thật của cơ sở dữ liệu. Số bị khuyết là
trường đã bị gỡ; khoảng trống được giữ nguyên để đối chiếu với cơ sở dữ liệu không
bị lệch.

---

## A-2.1 Nhóm M1 — Danh tính & Truy cập

*Nhóm gồm 8 bảng.*

### Bảng `users`

*Bảng A2-1: Từ điển dữ liệu bảng `users`*

**Mô tả:** Tài khoản người dùng của nền tảng. Là gốc của mọi quan hệ danh tính.

**Khoá chính:** `id` · **Số trường:** 15 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 10

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `id` | Uuid | Khoá chính | Định danh tài khoản, sinh tự động. |
| 2 | `username` | Text | Duy nhất · Bắt buộc | Tên đăng nhập, duy nhất toàn nền tảng. |
| 3 | `email` | Text | Duy nhất · Bắt buộc | Địa chỉ thư điện tử dùng đăng nhập và nhận mã xác thực. |
| 4 | `password_hash` | Text | Bắt buộc | Mã băm mật khẩu kèm muối. Hệ thống không có đường đọc ngược ra mật khẩu gốc. |
| 5 | `is_active` | Boolean | Bắt buộc · Mặc định: `true` | Tài khoản còn hoạt động hay đã bị vô hiệu. |
| 6 | `is_admin` | Boolean | Bắt buộc · Mặc định: `false` | Cờ quản trị nền tảng. Đây là cơ chế phân biệt quản trị nền tảng với quản trị tổ chức — hai vai không kế thừa nhau. |
| 7 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 8 | `role_id` | Uuid | Khoá ngoại → `roles` | Vai mặc định gán cho tài khoản. |
| 9 | `phone_number` | Varchar(20) | Duy nhất | Số điện thoại, dùng cho kênh gửi mã thứ hai. |
| 10 | `updated_at` | Timestamptz | — | Thời điểm bản ghi được sửa lần gần nhất. |
| 11 | `deleted_at` | Timestamptz | — | Mốc xoá mềm. Để trống nghĩa là bản ghi còn hiệu lực; có giá trị nghĩa là đã rời khỏi tập làm việc nhưng dữ liệu vẫn còn. |
| 12 | `tenant_id` | Text | Khoá ngoại → `tenants` · Bắt buộc | Tổ chức nhà của tài khoản. Bảng này có chính sách cách ly nhưng kèm lối thoát phạm vi hệ thống, vì truy vấn phân giải đăng nhập chạy trước khi biết tổ chức. |
| 13 | `email_verified_at` | Timestamptz | — | Thời điểm chứng minh quyền kiểm soát địa chỉ thư. Để trống nghĩa là chưa xác thực. |
| 14 | `phone_verified_at` | Timestamptz | — | Thời điểm chứng minh quyền kiểm soát số điện thoại. |
| 15 | `sessions_invalid_before` | Timestamptz | — | Mốc thu hồi hàng loạt: mọi phiên cấp trước mốc này đều mất hiệu lực. Là cơ chế thu hồi mức hai trong ba mức. |

### Bảng `refresh_tokens`

*Bảng A2-2: Từ điển dữ liệu bảng `refresh_tokens`*

**Mô tả:** Phiên đăng nhập. Mỗi dòng là một phiên với token làm mới, thiết bị và địa chỉ.

**Khoá chính:** `token_hash` · **Số trường:** 8 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 30

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `token_hash` | Text | Khoá chính | Mã băm của token làm mới. Chỉ lưu mã băm, không lưu token. |
| 2 | `user_id` | Uuid | Khoá ngoại → `users` · Bắt buộc | Tài khoản sở hữu phiên. |
| 3 | `expires_at` | Timestamptz | Bắt buộc | Thời điểm token hết hạn tự nhiên. |
| 4 | `revoked_at` | Timestamptz | — | Thời điểm phiên bị thu hồi chủ động, do đăng xuất hoặc do biện pháp quản trị. |
| 5 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 6 | `family_id` | Uuid | — | Định danh chuỗi token của cùng một phiên, dùng phát hiện việc dùng lại token đã xoay. |
| 7 | `replaced_by` | Text | — | Token kế tiếp đã thay thế token này trong chuỗi xoay. |
| 8 | `reuse_detected_at` | Timestamptz | — | Thời điểm phát hiện một token đã xoay bị dùng lại — dấu hiệu token bị đánh cắp. |

### Bảng `password_reset_tokens`

*Bảng A2-3: Từ điển dữ liệu bảng `password_reset_tokens`*

**Mô tả:** Token đặt lại mật khẩu, dùng một lần và có hạn.

**Khoá chính:** `token_hash` · **Số trường:** 5 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 7

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `token_hash` | Text | Khoá chính | Mã băm token đặt lại mật khẩu, dùng một lần. |
| 2 | `user_id` | Uuid | Khoá ngoại → `users` · Bắt buộc | Tài khoản yêu cầu đặt lại mật khẩu. |
| 3 | `expires_at` | Timestamptz | Bắt buộc | Thời điểm hết hạn. Sau mốc này bản ghi không còn dùng được. |
| 4 | `used_at` | Timestamptz | — | Thời điểm token được tiêu. Có giá trị nghĩa là không dùng lại được. |
| 5 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |

### Bảng `verification_codes`

*Bảng A2-4: Từ điển dữ liệu bảng `verification_codes`*

**Mô tả:** Mã một lần chứng minh quyền kiểm soát một địa chỉ liên hệ.

**Khoá chính:** `challenge_id` · **Số trường:** 11 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 2

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `challenge_id` | Uuid | Khoá chính | Định danh lượt phát mã. |
| 2 | `user_id` | Uuid | Khoá ngoại → `users` | Tài khoản yêu cầu mã. Để trống với luồng khôi phục khi chưa xác định được tài khoản. |
| 3 | `purpose` | Text | Bắt buộc · Giá trị: `verify_email`, `verify_phone`, `reset_password` | Mục đích phát mã: xác thực địa chỉ, khôi phục tài khoản, hay xác nhận lời mời. |
| 4 | `channel` | Text | Bắt buộc · Giá trị: `email`, `sms` | Kênh gửi: thư điện tử hoặc tin nhắn. |
| 5 | `destination` | Text | Bắt buộc | Địa chỉ đích nhận mã. Một mã chứng minh quyền kiểm soát đúng địa chỉ này, không phải quyền với tài khoản. |
| 6 | `code_hash` | Text | Bắt buộc | Mã băm của mã một lần. Chỉ lưu mã băm. |
| 7 | `attempts` | Integer | Bắt buộc · Mặc định: `0` | Số lần đã thử nhập sai. |
| 8 | `max_attempts` | Integer | Bắt buộc · Mặc định: `5` | Ngân sách lần thử. Hết ngân sách thì mã bị vô hiệu ngay, phải xin mã mới. |
| 9 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 10 | `expires_at` | Timestamptz | Bắt buộc | Thời điểm hết hạn. Sau mốc này bản ghi không còn dùng được. |
| 11 | `consumed_at` | Timestamptz | — | Thời điểm mã được tiêu. |

### Bảng `user_totp`

*Bảng A2-5: Từ điển dữ liệu bảng `user_totp`*

**Mô tả:** Bí mật xác thực hai yếu tố theo chuẩn TOTP của một tài khoản.

**Khoá chính:** `user_id` · **Số trường:** 5 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `user_id` | Uuid | Khoá chính · Khoá ngoại → `users` | Tài khoản bật xác thực hai yếu tố. |
| 2 | `secret_enc` | Text | Bắt buộc | Bí mật TOTP ở dạng đã mã hoá. |
| 3 | `confirmed_at` | Timestamptz | — | Thời điểm người dùng nhập đúng mã đầu tiên, xác nhận kích hoạt. Để trống nghĩa là bí mật đã sinh nhưng chưa kích hoạt. |
| 4 | `last_used_step` | Bigint | — | Chỉ số khoảng thời gian của mã dùng gần nhất, dùng chặn phát lại cùng một mã trong chính cửa sổ của nó. |
| 5 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |

### Bảng `user_recovery_codes`

*Bảng A2-6: Từ điển dữ liệu bảng `user_recovery_codes`*

**Mô tả:** Mã khôi phục dùng một lần, dự phòng khi mất thiết bị sinh mã.

**Khoá chính:** `code_hash` · **Số trường:** 4 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `code_hash` | Text | Khoá chính | Mã băm của một mã khôi phục dùng một lần. |
| 2 | `user_id` | Uuid | Khoá ngoại → `users` · Bắt buộc | Tài khoản sở hữu mã khôi phục. |
| 3 | `used_at` | Timestamptz | — | Thời điểm mã bị tiêu vĩnh viễn. |
| 4 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |

### Bảng `user_action_passcodes`

*Bảng A2-7: Từ điển dữ liệu bảng `user_action_passcodes`*

**Mô tả:** Mã xác thực lại cho thao tác nhạy cảm. Gắn với PHIÊN hiện tại chứ không gắn với tài khoản, nên đặc quyền không đi theo người dùng sang thiết bị khác.

**Khoá chính:** `user_id` · **Số trường:** 8 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `user_id` | Uuid | Khoá chính · Khoá ngoại → `users` | Tài khoản đang được nâng quyền. |
| 2 | `passcode_hash` | Text | Bắt buộc | Mã băm của mã xác thực lại cho thao tác nhạy cảm. |
| 3 | `status` | Text | Bắt buộc · Mặc định: `'ACTIVE'` · Giá trị: `ACTIVE`, `LOCKED`, `REVOKED` | Trạng thái của mã: đang chờ, đã dùng, hay đã khoá. |
| 4 | `failed_count` | Smallint | Bắt buộc · Mặc định: `0` | Số lần nhập sai liên tiếp. |
| 5 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 6 | `updated_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được sửa lần gần nhất. |
| 7 | `locked_until` | Timestamptz | — | Thời điểm hết khoá sau khi nhập sai quá ngưỡng. |
| 8 | `revoked_at` | Timestamptz | — | Thời điểm chủ động hạ quyền, kết thúc cửa sổ đặc quyền trước hạn. |

### Bảng `api_keys`

*Bảng A2-8: Từ điển dữ liệu bảng `api_keys`*

**Mô tả:** Khoá API cấp cho hệ thống bên thứ ba. Chỉ lưu mã băm; giá trị khoá hiển thị đúng một lần lúc tạo.

**Khoá chính:** `key_id` · **Số trường:** 12 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `key_id` | Uuid | Khoá chính | Định danh khoá API. |
| 2 | `tenant_id` | Text | Khoá ngoại → `tenants` · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 3 | `name` | Text | Bắt buộc · Mặc định: `''` | Nhãn do người dùng đặt để nhận ra khoá. |
| 4 | `prefix` | Text | Duy nhất · Bắt buộc | Tiền tố công khai của khoá, dùng nhận diện khoá mà không lộ giá trị. |
| 5 | `key_hash` | Text | Bắt buộc | Mã băm khoá. Giá trị khoá chỉ hiển thị đúng một lần lúc tạo và không lưu lại. |
| 6 | `scopes` | Text | Bắt buộc · Mặc định: `'read'` | Phạm vi quyền của khoá: chỉ đọc hoặc đọc–ghi. |
| 7 | `created_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã tạo khoá. |
| 8 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 9 | `last_used_at` | Timestamptz | — | Thời điểm khoá được dùng gần nhất. |
| 10 | `expires_at` | Timestamptz | — | Thời điểm hết hạn. Sau mốc này bản ghi không còn dùng được. |
| 11 | `revoked_at` | Timestamptz | — | Thời điểm bị thu hồi. Để trống nghĩa là còn hiệu lực. |
| 12 | `revoked_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã thu hồi khoá. |

---

## A-2.2 Nhóm M2 — Tổ chức & Phân quyền

*Nhóm gồm 10 bảng.*

### Bảng `tenants`

*Bảng A2-9: Từ điển dữ liệu bảng `tenants`*

**Mô tả:** Tổ chức — ranh giới cách ly cao nhất của hệ thống. Bảng chứa cả tổ chức thật lẫn đúng một tổ chức dự trữ đóng vai mặt phẳng Cộng đồng.

**Khoá chính:** `tenant_id` · **Số trường:** 20 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 3

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `tenant_id` | Text | Khoá chính | Định danh tổ chức. Đây là ranh giới cách ly cao nhất của toàn hệ thống. |
| 2 | `display_name` | Text | — | Tên hiển thị cho người dùng. |
| 3 | `slug` | Text | Duy nhất | Định danh ngắn dùng trên đường dẫn, duy nhất toàn nền tảng. |
| 4 | `is_active` | Boolean | Bắt buộc · Mặc định: `true` | Bản ghi còn hiệu lực hay đã ngưng sử dụng. |
| 5 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 6 | `deleted_at` | Timestamptz | — | Mốc xoá mềm. Để trống nghĩa là bản ghi còn hiệu lực; có giá trị nghĩa là đã rời khỏi tập làm việc nhưng dữ liệu vẫn còn. |
| 7 | `cloned_from_community_version` | Bigint | Khoá ngoại → `community_versions` | Phiên bản danh mục hệ thống đã sao chép vào tổ chức lúc khởi tạo. Ghi lại để biết tổ chức kế thừa từ đâu — đây là kế thừa một lần, không phải đường rơi về lúc chạy. |
| 8 | `cloned_at` | Timestamptz | — | Thời điểm thực hiện lần sao chép danh mục duy nhất đó. |
| 9 | `plan_code` | Text | Khoá ngoại → `plans` · Bắt buộc · Mặc định: `'free'` | Gói dịch vụ tổ chức đang dùng. |
| 10 | `billing_status` | Text | Bắt buộc · Mặc định: `'active'` · Giá trị: `trialing`, `active`, `past_due`, `suspended`, `cancelled` | Trạng thái thương mại: đang hoạt động, quá hạn, hay đã dừng. Tách khỏi trạng thái quản trị một cách có chủ ý. |
| 11 | `trial_ends_at` | Timestamptz | — | Thời điểm kết thúc giai đoạn dùng thử. |
| 12 | `current_period_start` | Timestamptz | — | Đầu kỳ hạn hiện tại của đăng ký dịch vụ. |
| 13 | `current_period_end` | Timestamptz | — | Cuối kỳ hạn hiện tại; là mốc để gửi nhắc hạn và tính ân hạn. |
| 14 | `is_self_serve` | Boolean | Bắt buộc · Mặc định: `false` | Tổ chức có cho tự đăng ký hay chỉ nhận thành viên theo lời mời. |
| 15 | `owner_user_id` | Uuid | Khoá ngoại → `users` | Tài khoản chủ sở hữu tổ chức. |
| 16 | `suspended_at` | Timestamptz | — | Thời điểm bị đình chỉ bằng biện pháp quản trị. |
| 17 | `suspended_reason` | Text | — | Lý do đình chỉ. Bắt buộc có khi đình chỉ, để người dùng và quản trị viên kế tiếp đều biết vì sao. |
| 18 | `tenant_type` | Text | Bắt buộc · Mặc định: `'ORGANIZATION'` · Giá trị: `COMMUNITY`, `ORGANIZATION` | Loại tổ chức. Giá trị COMMUNITY dành cho đúng một tổ chức dự trữ là mặt phẳng Cộng đồng; mọi tổ chức thật đều là ORGANIZATION. |
| 19 | `is_system_reserved` | Boolean | Bắt buộc · Mặc định: `false` | Cờ đánh dấu tổ chức do hệ thống dự trữ. Đây là NHÃN, không phải quyền — nó không tự chặn đường truy cập nào. |
| 21 | `billing_exempt` | Boolean | Bắt buộc · Mặc định: `false` | Miễn trừ tính phí, dùng cho tổ chức nội bộ. |

### Bảng `workspaces`

*Bảng A2-10: Từ điển dữ liệu bảng `workspaces`*

**Mô tả:** Không gian làm việc bên trong một tổ chức. Đã có bề mặt vận hành nhưng CHƯA phân vùng dữ liệu.

**Khoá chính:** `workspace_id` · **Số trường:** 9 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 4

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `workspace_id` | Uuid | Khoá chính · Duy nhất · Mặc định: sinh UUID | Định danh không gian làm việc. |
| 2 | `tenant_id` | Text | Khoá ngoại → `tenants` · Duy nhất · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 3 | `name` | Text | Bắt buộc | Tên không gian làm việc. |
| 4 | `description` | Text | Bắt buộc · Mặc định: `''` | Mô tả nghiệp vụ, dùng cho màn hình quản trị. |
| 5 | `status` | Text | Bắt buộc · Mặc định: `'ACTIVE'` · Giá trị: `ACTIVE`, `ARCHIVED`, `DELETED` | Trạng thái vòng đời của bản ghi. |
| 6 | `is_default` | Boolean | Bắt buộc · Mặc định: `false` | Không gian làm việc mặc định của tổ chức. |
| 7 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 8 | `archived_at` | Timestamptz | — | Thời điểm lưu trữ, ngưng dùng nhưng chưa xoá. |
| 9 | `deleted_at` | Timestamptz | — | Mốc xoá mềm. Để trống nghĩa là bản ghi còn hiệu lực; có giá trị nghĩa là đã rời khỏi tập làm việc nhưng dữ liệu vẫn còn. |

### Bảng `projects`

*Bảng A2-11: Từ điển dữ liệu bảng `projects`*

**Mô tả:** Dự án bên trong một không gian làm việc. Cùng tình trạng với không gian làm việc.

**Khoá chính:** `project_id` · **Số trường:** 10 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 6

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `project_id` | Uuid | Khoá chính · Duy nhất · Mặc định: sinh UUID | Định danh dự án. |
| 2 | `tenant_id` | Text | Khoá ngoại → `tenants` · Duy nhất · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 3 | `workspace_id` | Uuid | Khoá ngoại → `workspaces` *(khoá ghép)* · Duy nhất · Bắt buộc | Không gian làm việc chứa dự án. Khoá ngoại ghép mang định danh tổ chức, nên dự án không thể thuộc không gian làm việc của tổ chức khác. |
| 4 | `name` | Text | Bắt buộc | Tên dự án. |
| 5 | `description` | Text | Bắt buộc · Mặc định: `''` | Mô tả nghiệp vụ, dùng cho màn hình quản trị. |
| 6 | `status` | Text | Bắt buộc · Mặc định: `'ACTIVE'` · Giá trị: `ACTIVE`, `ARCHIVED`, `DELETED` | Trạng thái vòng đời của bản ghi. |
| 7 | `is_default` | Boolean | Bắt buộc · Mặc định: `false` | Dự án mặc định của không gian làm việc. |
| 8 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 9 | `archived_at` | Timestamptz | — | Thời điểm lưu trữ dự án. |
| 10 | `deleted_at` | Timestamptz | — | Mốc xoá mềm. Để trống nghĩa là bản ghi còn hiệu lực; có giá trị nghĩa là đã rời khỏi tập làm việc nhưng dữ liệu vẫn còn. |

### Bảng `project_allocations`

*Bảng A2-12: Từ điển dữ liệu bảng `project_allocations`*

**Mô tả:** Hạn mức phân bổ cho từng dự án. Là bảng mới nhất của lược đồ.

**Khoá chính:** (`tenant_id`, `project_id`, `metric`) · **Số trường:** 7 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 4

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `tenant_id` | Text | Khoá chính · Khoá ngoại → `tenants` | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 2 | `project_id` | Uuid | Khoá chính · Khoá ngoại → `projects` *(khoá ghép)* | Dự án được phân bổ hạn mức. |
| 3 | `metric` | Text | Khoá chính | Loại hạn mức được phân bổ, ví dụ số mẫu hay dung lượng. |
| 4 | `allocated` | Bigint | — | Mức phân bổ cho dự án theo loại hạn mức tương ứng. |
| 5 | `note` | Text | Bắt buộc · Mặc định: `''` | Ghi chú tự do của người quản trị. |
| 6 | `updated_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã sửa bản ghi lần gần nhất. |
| 7 | `updated_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được sửa lần gần nhất. |

### Bảng `memberships`

*Bảng A2-13: Từ điển dữ liệu bảng `memberships`*

**Mô tả:** Tư cách thành viên đa hình, phục vụ cả ba cấp phạm vi bằng MỘT bảng. Khoá ngoại tự trỏ cưỡng chế luật cấp dưới phải có cấp trên.

**Khoá chính:** `membership_id` · **Số trường:** 14 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 30

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `membership_id` | Uuid | Khoá chính · Duy nhất · Mặc định: sinh UUID | Định danh tư cách thành viên. |
| 2 | `user_id` | Uuid | Khoá ngoại → `users` · Duy nhất · Bắt buộc | Tài khoản được cấp tư cách thành viên. |
| 3 | `scope_level` | Text | Bắt buộc · Mặc định: `'TENANT'` · Giá trị: `TENANT`, `WORKSPACE`, `PROJECT` | Cấp phạm vi của tư cách thành viên. Đây là cột làm bảng này thành bảng đa hình: một bảng phục vụ cả ba cấp thay vì ba bảng riêng. |
| 4 | `tenant_id` | Text | Khoá ngoại → `tenants` · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 5 | `workspace_id` | Uuid | Khoá ngoại → `workspaces` *(khoá ghép)* | Không gian làm việc, chỉ có giá trị khi cấp phạm vi là WORKSPACE hoặc PROJECT. |
| 6 | `project_id` | Uuid | Khoá ngoại → `projects` *(khoá ghép)* | Dự án, chỉ có giá trị khi cấp phạm vi là PROJECT. |
| 7 | `parent_membership_id` | Uuid | Khoá ngoại → `memberships` *(khoá ghép)* | Tư cách thành viên cấp trên. Khoá ngoại tự trỏ này cưỡng chế luật: có tư cách ở cấp dưới thì phải có tư cách ở cấp trên. |
| 8 | `legacy_role` | Text | Giá trị: `admin`, `editor` | Vai theo mô hình hai phạm vi cũ, giữ lại cho dữ liệu kế thừa. |
| 9 | `status` | Text | Bắt buộc · Mặc định: `'ACTIVE'` · Giá trị: `ACTIVE`, `INVITED`, `SUSPENDED`, `REMOVED` | Trạng thái tư cách thành viên. |
| 10 | `joined_at` | Timestamptz | — | Thời điểm gia nhập. |
| 11 | `suspended_at` | Timestamptz | — | Thời điểm tạm ngưng tư cách thành viên. |
| 12 | `left_at` | Timestamptz | — | Thời điểm rời khỏi phạm vi. |
| 13 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 14 | `updated_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được sửa lần gần nhất. |

### Bảng `roles`

*Bảng A2-14: Từ điển dữ liệu bảng `roles`*

**Mô tả:** Định nghĩa vai. Một bảng chứa cả vai dựng sẵn của nền tảng lẫn vai riêng của tổ chức, phân biệt bằng việc cột tổ chức có để trống hay không.

**Khoá chính:** `role_id` · **Số trường:** 12 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 17

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `role_id` | Uuid | Khoá chính · Duy nhất · Mặc định: sinh UUID | Định danh vai. |
| 2 | `role_code` | Varchar(50) | Bắt buộc | Mã vai dùng trong mã nguồn và trong phép kiểm quyền. |
| 3 | `description` | Text | Mặc định: `''` | Mô tả nghiệp vụ, dùng cho màn hình quản trị. |
| 4 | `tenant_id` | Text | Khoá ngoại → `tenants` | Tổ chức sở hữu vai. Cột này CHO PHÉP TRỐNG, và trống nghĩa là vai dựng sẵn của nền tảng dùng chung cho mọi tổ chức. |
| 5 | `scope_level` | Text | Duy nhất · Giá trị: `SYSTEM`, `TENANT`, `WORKSPACE`, `PROJECT` | Cấp phạm vi mà vai này áp dụng được. |
| 6 | `is_builtin` | Boolean | Bắt buộc · Mặc định: `false` | Vai dựng sẵn của hệ thống hay vai do tổ chức tự tạo. |
| 7 | `is_active` | Boolean | Bắt buộc · Mặc định: `true` | Bản ghi còn hiệu lực hay đã ngưng sử dụng. |
| 8 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 9 | `role_name` | Text | — | Tên vai hiển thị cho người dùng. |
| 10 | `tenant_type_constraint` | Text | Giá trị: `COMMUNITY`, `ORGANIZATION` | Giới hạn vai chỉ dùng được cho một loại tổ chức nhất định. |
| 11 | `created_by_user_id` | Uuid | Khoá ngoại → `users` | Tài khoản đã tạo vai. |
| 12 | `updated_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được sửa lần gần nhất. |

### Bảng `permissions`

*Bảng A2-15: Từ điển dữ liệu bảng `permissions`*

**Mô tả:** Danh mục quyền của nền tảng. Mọi phép kiểm hỏi một mã quyền cụ thể, không hỏi tư cách thành viên.

**Khoá chính:** `permission_code` · **Số trường:** 9 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 63

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `permission_code` | Text | Khoá chính | Mã quyền, là khoá chính. Mọi phép kiểm trong hệ thống hỏi một mã quyền cụ thể, không hỏi tư cách thành viên. |
| 2 | `description` | Text | Bắt buộc · Mặc định: `''` | Mô tả nghiệp vụ, dùng cho màn hình quản trị. |
| 3 | `applicable_scope` | Text | Bắt buộc · Giá trị: `SYSTEM`, `TENANT`, `WORKSPACE`, `PROJECT` | Cấp phạm vi mà quyền này có nghĩa. |
| 4 | `risk_level` | Text | Bắt buộc · Mặc định: `'NORMAL'` · Giá trị: `NORMAL`, `SENSITIVE`, `CRITICAL` | Mức rủi ro của quyền, dùng phân loại thao tác cần xác thực lại. |
| 5 | `requires_passcode` | Boolean | Bắt buộc · Mặc định: `false` | Quyền này có buộc xác thực lại trong phiên trước khi thực hiện hay không. |
| 6 | `is_api_assignable` | Boolean | Bắt buộc · Mặc định: `false` | Quyền có cấp được cho khoá API hay chỉ cấp cho người. |
| 7 | `is_active` | Boolean | Bắt buộc · Mặc định: `true` | Bản ghi còn hiệu lực hay đã ngưng sử dụng. |
| 8 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 9 | `is_custom_role_allowed` | Boolean | Bắt buộc · Mặc định: `true` | Vai do tổ chức tự tạo có được nhận quyền này hay không. |

### Bảng `role_permissions`

*Bảng A2-16: Từ điển dữ liệu bảng `role_permissions`*

**Mô tả:** Bảng nối vai với quyền.

**Khoá chính:** (`role_id`, `permission_code`) · **Số trường:** 3 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 345

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `role_id` | Uuid | Khoá chính · Khoá ngoại → `roles` | Vai được cấp quyền. |
| 2 | `permission_code` | Text | Khoá chính · Khoá ngoại → `permissions` | Quyền được cấp cho vai. |
| 3 | `granted_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm cấp quyền. |

### Bảng `role_assignments`

*Bảng A2-17: Từ điển dữ liệu bảng `role_assignments`*

**Mô tả:** Lần gán vai. Trỏ vào tư cách thành viên chứ không vào cặp người–phạm vi, nên phạm vi được kế thừa chứ không lưu lại hai chỗ.

**Khoá chính:** `assignment_id` · **Số trường:** 9 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 14

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `assignment_id` | Uuid | Khoá chính · Mặc định: sinh UUID | Định danh lần gán vai. |
| 2 | `user_id` | Uuid | Khoá ngoại → `users` · Bắt buộc | Tài khoản được gán vai. |
| 3 | `role_id` | Uuid | Khoá ngoại → `roles` · Bắt buộc | Vai được gán. |
| 4 | `membership_id` | Uuid | Khoá ngoại → `memberships` *(khoá ghép)* | Tư cách thành viên mà lần gán vai này dựa vào. CHO PHÉP TRỐNG: trống nghĩa là gán vai cấp hệ thống, không thuộc tổ chức nào. Khoá ngoại là khoá ghép cùng tài khoản, nên không thể gán vai cho người này dựa trên tư cách của người khác. |
| 5 | `assigned_by_user_id` | Uuid | Khoá ngoại → `users` · Bắt buộc | Tài khoản đã thực hiện việc gán. |
| 6 | `assigned_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm gán vai. |
| 7 | `revoked_by_user_id` | Uuid | Khoá ngoại → `users` | Tài khoản đã thu hồi vai. |
| 8 | `revoked_at` | Timestamptz | — | Thời điểm bị thu hồi. Để trống nghĩa là còn hiệu lực. |
| 9 | `revoke_reason` | Text | — | Lý do thu hồi vai. |

### Bảng `tenant_invitations`

*Bảng A2-18: Từ điển dữ liệu bảng `tenant_invitations`*

**Mô tả:** Lời mời gia nhập tổ chức. Là ĐƯỜNG DUY NHẤT đưa một người vào tổ chức.

**Khoá chính:** `invitation_id` · **Số trường:** 11 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `invitation_id` | Uuid | Khoá chính | Định danh lời mời. |
| 2 | `tenant_id` | Text | Khoá ngoại → `tenants` · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 3 | `email` | Text | Bắt buộc | Địa chỉ được mời. Một lời mời gắn với đúng một địa chỉ và không sửa được. |
| 4 | `role` | Text | Giá trị: `admin`, `editor` | Vai dự kiến cấp cho người được mời khi họ chấp nhận. |
| 5 | `token_hash` | Text | Duy nhất · Bắt buộc | Mã băm của mã mời dùng một lần. |
| 6 | `invited_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã gửi lời mời. |
| 7 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 8 | `expires_at` | Timestamptz | Bắt buộc | Thời điểm hết hạn. Sau mốc này bản ghi không còn dùng được. |
| 9 | `accepted_at` | Timestamptz | — | Thời điểm lời mời được chấp nhận. |
| 10 | `accepted_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã chấp nhận lời mời. |
| 11 | `revoked_at` | Timestamptz | — | Thời điểm lời mời bị thu hồi trước khi dùng. |

---

## A-2.3 Nhóm M3 — Kho dữ liệu mẫu

*Nhóm gồm 6 bảng.*

### Bảng `samples`

*Bảng A2-19: Từ điển dữ liệu bảng `samples`*

**Mô tả:** Bảng trung tâm của hệ thống. Mỗi dòng là một biểu diễn đặc trưng đã xử lý xong của một lần thực hiện ký hiệu.

**Khoá chính:** `sample_uid` · **Số trường:** 42 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 3.860

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `sample_uid` | Text | Khoá chính | Định danh mẫu, ổn định qua các lần chạy lại. Chính tính ổn định này làm một lượt xử lý lặp lại ghi đè thay vì nhân bản dữ liệu. |
| 2 | `class_uid` | Text | Khoá ngoại → `classes` *(khoá ghép)* | Lớp từ vựng mà mẫu thuộc về. Khoá ngoại ghép mang định danh tổ chức, nên mẫu của tổ chức này không trỏ được sang lớp của tổ chức khác. |
| 3 | `slug` | Text | — | Bản chuẩn hoá không dấu của nhãn lớp, chép lại tại thời điểm thu. Là ảnh chụp lịch sử: đổi nhãn lớp về sau không cập nhật cột này. |
| 4 | `label_original` | Text | — | Nhãn hiển thị nguyên văn tại thời điểm thu, giữ dấu tiếng Việt. |
| 5 | `language` | Text | Khoá ngoại → `languages` | Mã ngôn ngữ của bản ghi. |
| 6 | `dialect` | Text | Khoá ngoại → `dialects` *(khoá ghép)* | Phương ngữ của ký hiệu. Là một phần định danh lớp, không phải thuộc tính mô tả. |
| 7 | `source_type` | Text | — | Đường thu đã sinh ra mẫu: thu trực tiếp qua camera hay tải lên tệp video. Đây là cách duy nhất truy được xuất xứ tệp tải lên, vì bảng không có khoá ngoại tới bảng bản tải lên thô. |
| 8 | `user_id` | Text | — | Hiện vật lịch sử. Định danh nội bộ của lượt thu, có từ trước khi hệ thống có khái niệm tài khoản. Không dùng để suy ra chủ thể dữ liệu. |
| 9 | `auth_user_id` | Uuid | Khoá ngoại → `users` | Tài khoản đã đăng nhập lúc thu, tức người vận hành. Không được nhầm với người ký. |
| 10 | `session_id` | Text | — | Mã phiên thu dạng chuỗi thuộc lược đồ cũ, đã được thay bằng cột định danh phiên thu. |
| 11 | `fps_original` | Text | — | Tần số khung hình của nguồn trước xử lý. |
| 12 | `fps_processed` | Text | — | Tần số khung hình sau khi cắt cửa sổ và chuẩn hoá. |
| 13 | `seq_len` | Integer | — | Số khung của cửa sổ sau xử lý. |
| 14 | `augment_id` | Integer | — | Cột phân biệt bản gốc với bản tăng cường. Giá trị 0 là một lần người thật thực hiện ký hiệu; các giá trị khác là biến thể do máy sinh. Đây là cột quyết định con số nào dùng khi nói về công sức thu thập và con số nào nói về kích thước tập huấn luyện. |
| 15 | `completeness` | Real | — | Tỉ lệ khung phát hiện được bàn tay. Tính lại được từ tệp đặc trưng nên là chỉ số tái lập được. Giá trị 0 nghĩa là không phát hiện được bàn tay nào, không nghĩa là tệp rỗng. |
| 16 | `file_path` | Text | — | Đường dẫn tệp đặc trưng trên hệ tệp cục bộ. |
| 17 | `storage_url` | Text | — | Địa chỉ bản sao trên kho lưu trữ ngoài. Để trống nghĩa là chưa đẩy lên được và tác vụ đối soát sẽ điền sau, không nghĩa là mẫu hỏng. |
| 18 | `checksum` | Text | — | Mã băm nội dung tệp đặc trưng, dùng phát hiện tệp bị sửa hoặc hỏng. |
| 19 | `created_at` | Timestamptz | — | Thời điểm bản ghi được tạo. |
| 20 | `sheets_synced` | Boolean | Mặc định: `false` | Đã phản chiếu sang bảng tính ngoài hay chưa. |
| 21 | `gdrive_synced` | Boolean | Mặc định: `true` | Đã đẩy lên kho lưu trữ ngoài hay chưa. Giá trị mặc định của cột này trên cơ sở dữ liệu đang chạy khác với giá trị khai trong nhánh tạo bảng của mã nguồn — một lỗi lược đồ đã biết, ghi ở danh sách vấn đề tồn đọng. |
| 23 | `status` | Varchar(20) | Mặc định: `'PENDING'` | Trạng thái vòng đời mẫu, từ chờ xử lý tới sẵn sàng hoặc thất bại. |
| 24 | `error_log` | Text | Mặc định: `''` | Lý do thất bại do tiến trình nền ghi lại. Chuỗi rỗng nghĩa là không có lỗi. |
| 25 | `updated_at` | Timestamptz | — | Thời điểm bản ghi được sửa lần gần nhất. |
| 26 | `storage_key` | Text | Mặc định: `''` | Khoá đối tượng do kho lưu trữ ngoài trả về sau khi đẩy tệp thành công. |
| 27 | `session_uid` | Text | — | Mã phiên thu dạng chuỗi thuộc lược đồ trung gian. |
| 28 | `username` | Text | — | Hiện vật lịch sử. Tên hiển thị chép lại tại thời điểm thu, là bản sao chụp chứ không dùng để suy ra chủ thể dữ liệu. |
| 30 | `deleted_at` | Timestamptz | — | Mốc xoá mềm. Để trống nghĩa là bản ghi còn hiệu lực; có giá trị nghĩa là đã rời khỏi tập làm việc nhưng dữ liệu vẫn còn. |
| 31 | `left_hand_ratio` | Real | — | Tỉ lệ khung phát hiện được bàn tay trái. |
| 32 | `right_hand_ratio` | Real | — | Tỉ lệ khung phát hiện được bàn tay phải. |
| 33 | `both_hands_ratio` | Real | — | Tỉ lệ khung phát hiện được cả hai tay, dùng đối chiếu với số bàn tay mà lớp yêu cầu. |
| 34 | `jitter` | Real | — | Độ rung của chuỗi điểm mốc. KHÔNG tái lập được, vì nó phụ thuộc chuỗi thời gian trước chuẩn hoá mà chuỗi đó không được lưu. Khi báo cáo phải phân biệt rõ với độ đầy đủ. |
| 35 | `quality_flags` | Text | — | Các cờ chất lượng do bước chấm điểm gắn, ví dụ cửa sổ đã bị đệm thêm. |
| 36 | `signer_id` | Text | Khoá ngoại → `signers` *(khoá ghép)* | Người ký, tức chủ thể dữ liệu. Để trống nghĩa là không quy kết được về nguyên tắc, và chuỗi nguồn gốc đứt ở đúng vị trí đó. Đây là cột chi phối đường phát hành dữ liệu qua bảng đồng thuận người ký. |
| 37 | `collection_campaign` | Text | — | Chiến dịch thu đã sinh ra mẫu. |
| 38 | `raw_landmarks_available` | Boolean | — | Bản điểm mốc thô trước chuẩn hoá còn giữ hay không. |
| 39 | `normalization_version` | Text | — | Phiên bản thuật toán chuẩn hoá đã áp, là điều kiện để so sánh hai mẫu thu ở hai thời điểm khác nhau. |
| 40 | `preprocess_contract_version` | Text | — | Phiên bản hợp đồng tiền xử lý, ghim định dạng đầu ra mà bước huấn luyện trông đợi. |
| 41 | `sequence_length_original` | Integer | — | Số khung của bản ghi gốc trước khi cắt cửa sổ. So với số khung sau xử lý sẽ biết cửa sổ đã bị cắt hay bị đệm. |
| 42 | `quality_status` | Text | — | Kết luận chất lượng tổng hợp từ các chỉ số đo được. |
| 43 | `tenant_id` | Text | Khoá ngoại → `signers` *(khoá ghép)* · Bắt buộc · Mặc định: `'default'` | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 44 | `capture_session_id` | Uuid | Khoá ngoại → `capture_sessions` | Phiên thu chứa mẫu. Là cột phiên thu đang dùng, thay cho hai cột phiên thu dạng chuỗi ở trên. |

### Bảng `classes`

*Bảng A2-20: Từ điển dữ liệu bảng `classes`*

**Mô tả:** Lớp từ vựng. Định danh duy nhất gồm NĂM cột, trong đó có cả phương ngữ và vùng miền.

**Khoá chính:** `class_uid` · **Số trường:** 23 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 63

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `class_uid` | Text | Khoá chính | Định danh lớp từ vựng, ổn định suốt vòng đời lớp. Mọi mẫu đã thu đều trỏ tới định danh này. |
| 2 | `class_idx` | Integer | — | Chỉ số lớp dùng làm nhãn số khi huấn luyện. Giữ cố định khi sửa lớp, vì đổi nó làm mô hình đã huấn luyện nói về một không gian nhãn khác với lúc suy luận. |
| 3 | `slug` | Text | — | Bản chuẩn hoá không dấu của nhãn, giữ phân biệt các chữ cái tiếng Việt có dấu phụ cho bảng chữ cái ngón tay. |
| 4 | `label_original` | Text | — | Nhãn hiển thị nguyên văn, giữ dấu tiếng Việt. |
| 5 | `language` | Text | Khoá ngoại → `languages` | Mã ngôn ngữ của bản ghi. |
| 6 | `dialect` | Text | Khoá ngoại → `dialects` *(khoá ghép)* | Phương ngữ. Là một trong năm cột hợp thành định danh duy nhất của lớp. |
| 7 | `is_common_global` | Boolean | — | Lớp dùng chung cho mọi ngôn ngữ. |
| 8 | `is_common_language` | Boolean | — | Lớp dùng chung trong phạm vi một ngôn ngữ. |
| 9 | `folder_name` | Text | — | Tên thư mục lưu tệp đặc trưng của lớp trên hệ tệp. |
| 10 | `created_at` | Timestamptz | — | Thời điểm bản ghi được tạo. |
| 11 | `migrated_at` | Timestamptz | — | Thời điểm lớp được chuyển từ lược đồ cũ sang lược đồ hiện tại. |
| 12 | `deleted_at` | Timestamptz | — | Mốc xoá mềm. Để trống nghĩa là bản ghi còn hiệu lực; có giá trị nghĩa là đã rời khỏi tập làm việc nhưng dữ liệu vẫn còn. |
| 13 | `description` | Text | Mặc định: `''` | Mô tả nghiệp vụ, dùng cho màn hình quản trị. |
| 14 | `is_active` | Boolean | Mặc định: `true` | Bản ghi còn hiệu lực hay đã ngưng sử dụng. |
| 15 | `hands_required` | Integer | — | Số bàn tay mà ký hiệu yêu cầu. Giao diện thu dùng giá trị này để nhắc người ký và để chấm chất lượng. |
| 16 | `semantic_label` | Text | — | Nhãn ngữ nghĩa dùng nhóm các lớp cùng ý nghĩa. |
| 17 | `vocabulary_scope` | Text | — | Phạm vi từ vựng của lớp. |
| 18 | `recognition_profile` | Text | Khoá ngoại → `recognition_profiles` *(khoá ghép)* | Hồ sơ nhận dạng chứa lớp, tức nhóm lớp cùng phục vụ một mô hình. |
| 19 | `vocabulary_group` | Text | Khoá ngoại → `vocabulary_groups` *(khoá ghép)* | Nhóm từ vựng chứa lớp. |
| 20 | `collection_campaign` | Text | — | Chiến dịch thu gắn với lớp. |
| 21 | `motion_type` | Text | — | Kiểu chuyển động của ký hiệu: tĩnh hay có chuyển động. |
| 22 | `tenant_id` | Text | Khoá ngoại → `vocabulary_groups` *(khoá ghép)* · Bắt buộc · Mặc định: `'default'` | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 23 | `region` | Text | Khoá ngoại → `regions` · Bắt buộc · Mặc định: `'unclassified'` | Vùng miền. Cũng là một phần định danh lớp: hai biến thể cùng nhãn, cùng phương ngữ nhưng khác vùng miền là HAI lớp khác nhau. |

### Bảng `capture_sessions`

*Bảng A2-21: Từ điển dữ liệu bảng `capture_sessions`*

**Mô tả:** Phiên thu — một lượt ngồi trước camera sinh ra nhiều mẫu. Là thực thể có vòng đời, vì quyền sở hữu phiên đổi được.

**Khoá chính:** `capture_session_id` · **Số trường:** 11 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 250

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `capture_session_id` | Uuid | Khoá chính | Định danh phiên thu, tức một lượt ngồi trước camera sinh ra nhiều mẫu. |
| 2 | `tenant_id` | Text | Khoá ngoại → `tenants` · Duy nhất · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 3 | `class_uid` | Text | Khoá ngoại → `classes` *(khoá ghép)* · Duy nhất · Bắt buộc | Lớp được thu trong phiên. |
| 4 | `session_id` | Text | Duy nhất · Bắt buộc | Mã phiên dạng chuỗi thuộc lược đồ cũ. |
| 5 | `signer_id` | Text | Khoá ngoại → `signers` *(khoá ghép)* | Người ký của phiên thu. Cột này đổi được qua thao tác gán lại người ký, nên phiên thu là một thực thể có vòng đời chứ không phải một nhãn. |
| 6 | `auth_user_id` | Uuid | Khoá ngoại → `users` | Tài khoản đã vận hành buổi thu. |
| 7 | `source_type` | Text | — | Đường thu: camera hay tệp video. |
| 8 | `started_at` | Timestamptz | — | Thời điểm bắt đầu phiên thu. |
| 9 | `ended_at` | Timestamptz | — | Thời điểm kết thúc phiên thu. |
| 10 | `note` | Text | — | Ghi chú tự do của người quản trị. |
| 11 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |

### Bảng `raw_uploads`

*Bảng A2-22: Từ điển dữ liệu bảng `raw_uploads`*

**Mô tả:** Bản tải lên thô. Được ghi TRƯỚC mọi bước chuẩn hoá, để một lỗi xử lý không làm mất dữ liệu gốc.

**Khoá chính:** `upload_uid` · **Số trường:** 21 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `upload_uid` | Text | Khoá chính | Định danh bản tải lên thô. |
| 2 | `class_uid` | Text | Khoá ngoại → `classes` *(khoá ghép)* | Lớp đích của tệp tải lên. |
| 3 | `slug` | Text | — | Bản chuẩn hoá không dấu của nhãn lớp, chép lại tại thời điểm tải lên. |
| 4 | `label_original` | Text | — | Nhãn hiển thị nguyên văn của lớp đích, giữ dấu tiếng Việt. |
| 5 | `language` | Text | Khoá ngoại → `languages` | Mã ngôn ngữ của bản ghi. |
| 6 | `dialect` | Text | Khoá ngoại → `dialects` *(khoá ghép)* | Phương ngữ khai cho cả lô tải lên. |
| 7 | `source_type` | Text | — | Nguồn của bản thô. Với bảng này giá trị luôn là đường tải lên tệp video. |
| 8 | `user_id` | Text | — | Hiện vật lịch sử, định danh nội bộ của lượt tải lên. |
| 9 | `auth_user_id` | Uuid | Khoá ngoại → `users` | Tài khoản đã đăng nhập lúc tải lên, tức người vận hành. |
| 10 | `session_id` | Text | — | Mã phiên dạng chuỗi thuộc lược đồ cũ. |
| 11 | `original_filename` | Text | — | Tên tệp gốc do người dùng tải lên, đã làm sạch trước khi dùng làm tên lưu trữ. |
| 12 | `local_path` | Text | — | Đường dẫn bản thô trên hệ tệp cục bộ. Bản thô được ghi TRƯỚC mọi bước chuẩn hoá, để một lỗi trong khâu xử lý không làm mất dữ liệu đã quay. |
| 13 | `storage_key` | Text | — | Khoá đối tượng trên kho lưu trữ, trả về sau khi ghi tệp thành công. |
| 14 | `storage_url` | Text | — | Địa chỉ bản thô trên kho lưu trữ ngoài. |
| 15 | `created_at` | Timestamptz | — | Thời điểm bản ghi được tạo. |
| 16 | `updated_at` | Timestamptz | — | Thời điểm bản ghi được sửa lần gần nhất. |
| 17 | `deleted_at` | Timestamptz | — | Mốc xoá mềm. Để trống nghĩa là bản ghi còn hiệu lực; có giá trị nghĩa là đã rời khỏi tập làm việc nhưng dữ liệu vẫn còn. |
| 18 | `status` | Varchar(20) | Mặc định: `'PENDING'` | Trạng thái xử lý của bản tải lên. |
| 19 | `session_uid` | Text | — | Phiên thu gắn với bản tải lên. |
| 20 | `username` | Text | — | Tên hiển thị của người tải lên tại thời điểm tải. |
| 21 | `tenant_id` | Text | Khoá ngoại → `tenants` · Bắt buộc · Mặc định: `'default'` | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |

### Bảng `signers`

*Bảng A2-23: Từ điển dữ liệu bảng `signers`*

**Mô tả:** Người ký — CHỦ THỂ DỮ LIỆU, tách khỏi tài khoản vận hành.

**Khoá chính:** `signer_id` · **Số trường:** 9 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 4

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `signer_id` | Text | Khoá chính | Định danh người ký. Người ký là CHỦ THỂ DỮ LIỆU, tách khỏi tài khoản vận hành — đây là phân biệt trung tâm của mô hình đồng thuận. |
| 2 | `display_name` | Text | — | Tên hiển thị cho người dùng. |
| 3 | `regional_group` | Text | — | Nhóm vùng miền của người ký, dùng khi chia tập theo người ký. |
| 4 | `external_user_id` | Uuid | Khoá ngoại → `users` | Định danh của người ký ở hệ thống ngoài, nếu có. |
| 5 | `is_active` | Boolean | Mặc định: `true` | Bản ghi còn hiệu lực hay đã ngưng sử dụng. |
| 6 | `created_at` | Timestamptz | — | Thời điểm bản ghi được tạo. |
| 7 | `tenant_id` | Text | Khoá ngoại → `tenants` · Bắt buộc · Mặc định: `'default'` | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 8 | `note` | Text | — | Ghi chú tự do của người quản trị. |
| 9 | `display_order` | Integer | Bắt buộc · Mặc định: `0` | Thứ tự hiển thị trong danh sách; số nhỏ đứng trước. |

### Bảng `signer_aliases`

*Bảng A2-24: Từ điển dữ liệu bảng `signer_aliases`*

**Mô tả:** Bí danh người ký sau khi gộp hai bản ghi trùng. Chỉ thêm, không sửa.

**Khoá chính:** (`tenant_id`, `old_signer_id`) · **Số trường:** 6 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `tenant_id` | Text | Khoá chính · Khoá ngoại → `signers` *(khoá ghép)* | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 2 | `old_signer_id` | Text | Khoá chính | Định danh người ký cũ, trước khi gộp. |
| 3 | `new_signer_id` | Text | Khoá ngoại → `signers` *(khoá ghép)* · Bắt buộc | Định danh người ký sau khi gộp. Giữ đường dẫn từ định danh cũ sang định danh mới thay vì xoá bản ghi cũ, để mọi tham chiếu lịch sử vẫn phân giải được. |
| 4 | `reason` | Text | — | Lý do gộp hai bản ghi người ký. |
| 5 | `merged_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm gộp. |
| 6 | `merged_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã thực hiện việc gộp. |

---

## A-2.4 Nhóm M4 — Danh mục & Registry

*Nhóm gồm 11 bảng.*

### Bảng `languages`

*Bảng A2-25: Từ điển dữ liệu bảng `languages`*

**Mô tả:** Danh mục ngôn ngữ của nền tảng.

**Khoá chính:** `code` · **Số trường:** 2 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 2

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `code` | Varchar(50) | Khoá chính | Mã ngôn ngữ, là khoá chính. |
| 2 | `name` | Text | Bắt buộc | Tên ngôn ngữ hiển thị. |

### Bảng `regions`

*Bảng A2-26: Từ điển dữ liệu bảng `regions`*

**Mô tả:** Danh mục vùng miền của nền tảng.

**Khoá chính:** `code` · **Số trường:** 8 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 5

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `code` | Text | Khoá chính | Mã vùng miền, là khoá chính. Vùng miền là một phần định danh lớp, không phải nhãn mô tả. |
| 2 | `name_vi` | Text | Bắt buộc | Tên vùng miền tiếng Việt. |
| 3 | `name_en` | Text | Bắt buộc · Mặc định: `''` | Tên vùng miền tiếng Anh. |
| 4 | `status` | Text | Bắt buộc · Mặc định: `'approved'` | Trạng thái vùng miền trong danh mục. |
| 5 | `sort_order` | Integer | Bắt buộc · Mặc định: `0` | Thứ tự sắp xếp trong danh sách. |
| 6 | `is_active` | Boolean | Bắt buộc · Mặc định: `true` | Bản ghi còn hiệu lực hay đã ngưng sử dụng. |
| 7 | `note` | Text | — | Ghi chú tự do của người quản trị. |
| 8 | `updated_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được sửa lần gần nhất. |

### Bảng `dialects`

*Bảng A2-27: Từ điển dữ liệu bảng `dialects`*

**Mô tả:** Phương ngữ trong phạm vi một tổ chức, có quy trình đề xuất và duyệt.

**Khoá chính:** (`tenant_id`, `dialect_id`) · **Số trường:** 14 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 11

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `tenant_id` | Text | Khoá chính · Khoá ngoại → `dialects` *(khoá ghép)* · Mặc định: `'default'` | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 2 | `dialect_id` | Text | Khoá chính | Định danh phương ngữ trong phạm vi một tổ chức. |
| 3 | `display_name` | Text | Bắt buộc | Tên hiển thị cho người dùng. |
| 4 | `language` | Text | Khoá ngoại → `languages` · Bắt buộc · Mặc định: `'vn'` | Mã ngôn ngữ của bản ghi. |
| 5 | `is_alphabet` | Boolean | Bắt buộc · Mặc định: `false` | Phương ngữ này là bảng chữ cái ngón tay hay từ vựng thông thường. Hai loại có luật chuẩn hoá nhãn khác nhau. |
| 6 | `is_active` | Boolean | Bắt buộc · Mặc định: `true` | Bản ghi còn hiệu lực hay đã ngưng sử dụng. |
| 7 | `status` | Text | Bắt buộc · Mặc định: `'pending'` | Trạng thái duyệt của phương ngữ: chờ duyệt, đã duyệt hay bị từ chối. Phương ngữ chưa duyệt không dùng để đăng ký lớp được. |
| 8 | `merged_into` | Text | Khoá ngoại → `dialects` *(khoá ghép)* | Phương ngữ đích khi bản ghi này bị gộp. Khoá ngoại tự trỏ mang định danh tổ chức, nên không gộp chéo tổ chức được. |
| 9 | `created_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã tạo bản ghi. |
| 10 | `approved_by` | Uuid | Khoá ngoại → `users` | Tài khoản quản trị nền tảng đã duyệt phương ngữ. |
| 11 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 12 | `approved_at` | Timestamptz | — | Thời điểm duyệt phương ngữ. |
| 13 | `note` | Text | — | Ghi chú tự do của người quản trị. |
| 14 | `display_order` | Integer | Bắt buộc · Mặc định: `0` | Thứ tự hiển thị trong danh sách; số nhỏ đứng trước. |

### Bảng `dialect_aliases`

*Bảng A2-28: Từ điển dữ liệu bảng `dialect_aliases`*

**Mô tả:** Bí danh phương ngữ sau khi gộp. Chỉ thêm, không sửa.

**Khoá chính:** (`tenant_id`, `old_dialect_id`) · **Số trường:** 5 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `tenant_id` | Text | Khoá chính · Khoá ngoại → `tenants` · Mặc định: `'default'` | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 2 | `old_dialect_id` | Text | Khoá chính | Định danh phương ngữ cũ trước khi gộp. |
| 3 | `new_dialect_id` | Text | Khoá ngoại → `dialects` *(khoá ghép)* · Bắt buộc | Định danh phương ngữ sau khi gộp. Giữ bí danh thay vì xoá bản ghi cũ, để tham chiếu lịch sử vẫn phân giải được. |
| 4 | `merged_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm gộp phương ngữ. |
| 5 | `merged_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã thực hiện việc gộp. |

### Bảng `recognition_profiles`

*Bảng A2-29: Từ điển dữ liệu bảng `recognition_profiles`*

**Mô tả:** Hồ sơ nhận dạng — nhóm lớp cùng phục vụ một mô hình.

**Khoá chính:** (`tenant_id`, `profile_id`) · **Số trường:** 7 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 6

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `tenant_id` | Text | Khoá chính · Khoá ngoại → `tenants` · Mặc định: `'default'` | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 2 | `profile_id` | Text | Khoá chính | Định danh hồ sơ nhận dạng, tức nhóm lớp cùng phục vụ một mô hình. |
| 3 | `display_name` | Text | Bắt buộc | Tên hiển thị cho người dùng. |
| 4 | `is_trainable` | Boolean | Bắt buộc · Mặc định: `true` | Hồ sơ này có đủ điều kiện đưa vào huấn luyện hay không. Cờ này khác với việc lớp đã đăng ký: đã đăng ký không đồng nghĩa huấn luyện được. |
| 5 | `is_active` | Boolean | Bắt buộc · Mặc định: `true` | Bản ghi còn hiệu lực hay đã ngưng sử dụng. |
| 6 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 7 | `display_order` | Integer | Bắt buộc · Mặc định: `0` | Thứ tự hiển thị trong danh sách; số nhỏ đứng trước. |

### Bảng `vocabulary_groups`

*Bảng A2-30: Từ điển dữ liệu bảng `vocabulary_groups`*

**Mô tả:** Nhóm từ vựng trong phạm vi tổ chức.

**Khoá chính:** (`tenant_id`, `group_id`) · **Số trường:** 6 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 5

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `tenant_id` | Text | Khoá chính · Khoá ngoại → `tenants` | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 2 | `group_id` | Text | Khoá chính | Định danh nhóm từ vựng trong phạm vi tổ chức. |
| 3 | `display_name` | Text | Bắt buộc | Tên hiển thị cho người dùng. |
| 4 | `display_order` | Integer | Bắt buộc · Mặc định: `0` | Thứ tự hiển thị trong danh sách; số nhỏ đứng trước. |
| 5 | `is_active` | Boolean | Bắt buộc · Mặc định: `true` | Bản ghi còn hiệu lực hay đã ngưng sử dụng. |
| 6 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |

### Bảng `vocabulary_registry_meta`

*Bảng A2-31: Từ điển dữ liệu bảng `vocabulary_registry_meta`*

**Mô tả:** Siêu dữ liệu danh mục của tổ chức. Đúng một dòng cho mỗi tổ chức.

**Khoá chính:** `tenant_id` · **Số trường:** 3 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 1

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `tenant_id` | Text | Khoá chính · Khoá ngoại → `tenants` · Mặc định: `'default'` | Tổ chức sở hữu danh mục. Bảng này có đúng một dòng cho mỗi tổ chức. |
| 2 | `version` | Bigint | Bắt buộc · Mặc định: `1` | Số hiệu phiên bản danh mục hiện hành của tổ chức. Tăng mỗi khi danh mục đổi. |
| 3 | `updated_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được sửa lần gần nhất. |

### Bảng `registry_versions`

*Bảng A2-32: Từ điển dữ liệu bảng `registry_versions`*

**Mô tả:** Ảnh chụp danh mục có phiên bản. Đây là thứ tác vụ huấn luyện ghim vào. Bất biến theo QUY ƯỚC ở tầng ứng dụng, KHÔNG có trigger cưỡng chế.

**Khoá chính:** (`tenant_id`, `version`) · **Số trường:** 7 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 91

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `tenant_id` | Text | Khoá chính · Khoá ngoại → `tenants` | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 2 | `version` | Bigint | Khoá chính | Số hiệu phiên bản danh mục. Cùng với định danh tổ chức tạo thành khoá chính. |
| 3 | `content_hash` | Text | Bắt buộc | Mã băm nội dung ảnh chụp, dùng phát hiện ảnh chụp bị sửa. |
| 4 | `snapshot` | Jsonb | Bắt buộc | Toàn bộ nội dung danh mục tại thời điểm chốt phiên bản. Đây là thứ tác vụ huấn luyện ghim vào, và là thứ làm một thí nghiệm tái lập được. Tính bất biến của cột này là QUY ƯỚC ở tầng ứng dụng, không có trigger cưỡng chế — khác với văn bản pháp lý. |
| 5 | `note` | Text | — | Ghi chú tự do của người quản trị. |
| 6 | `created_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã chốt phiên bản danh mục. |
| 7 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |

### Bảng `community_dialects`

*Bảng A2-33: Từ điển dữ liệu bảng `community_dialects`*

**Mô tả:** DANH MỤC HỆ THỐNG — phương ngữ chuẩn để sao chép cho tổ chức mới. Tên bảng là di sản; bảng này KHÔNG phải mặt phẳng Cộng đồng.

**Khoá chính:** `dialect_id` · **Số trường:** 9 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 9

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `dialect_id` | Text | Khoá chính | Định danh phương ngữ chuẩn của danh mục hệ thống. Bảng này thuộc DANH MỤC HỆ THỐNG, không phải mặt phẳng Cộng đồng — tên bảng là di sản. |
| 2 | `display_name` | Text | Bắt buộc | Tên hiển thị cho người dùng. |
| 3 | `language` | Text | Bắt buộc · Mặc định: `'vn'` | Mã ngôn ngữ của bản ghi. |
| 4 | `is_alphabet` | Boolean | Bắt buộc · Mặc định: `false` | Phương ngữ là bảng chữ cái ngón tay hay từ vựng thông thường. |
| 5 | `display_order` | Integer | Bắt buộc · Mặc định: `0` | Thứ tự hiển thị trong danh sách; số nhỏ đứng trước. |
| 6 | `is_active` | Boolean | Bắt buộc · Mặc định: `true` | Bản ghi còn hiệu lực hay đã ngưng sử dụng. |
| 7 | `note` | Text | — | Ghi chú tự do của người quản trị. |
| 8 | `updated_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã sửa bản ghi lần gần nhất. |
| 9 | `updated_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được sửa lần gần nhất. |

### Bảng `community_profiles`

*Bảng A2-34: Từ điển dữ liệu bảng `community_profiles`*

**Mô tả:** DANH MỤC HỆ THỐNG — hồ sơ nhận dạng chuẩn.

**Khoá chính:** `profile_id` · **Số trường:** 8 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 6

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `profile_id` | Text | Khoá chính | Định danh hồ sơ nhận dạng chuẩn của danh mục hệ thống. |
| 2 | `display_name` | Text | Bắt buộc | Tên hiển thị cho người dùng. |
| 3 | `is_trainable` | Boolean | Bắt buộc · Mặc định: `true` | Hồ sơ có đủ điều kiện huấn luyện hay không. |
| 4 | `display_order` | Integer | Bắt buộc · Mặc định: `0` | Thứ tự hiển thị trong danh sách; số nhỏ đứng trước. |
| 5 | `is_active` | Boolean | Bắt buộc · Mặc định: `true` | Bản ghi còn hiệu lực hay đã ngưng sử dụng. |
| 6 | `note` | Text | — | Ghi chú tự do của người quản trị. |
| 7 | `updated_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã sửa bản ghi lần gần nhất. |
| 8 | `updated_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được sửa lần gần nhất. |

### Bảng `community_versions`

*Bảng A2-35: Từ điển dữ liệu bảng `community_versions`*

**Mô tả:** DANH MỤC HỆ THỐNG — phiên bản danh mục chuẩn, là nguồn sao chép MỘT LẦN lúc khởi tạo tổ chức.

**Khoá chính:** `version` · **Số trường:** 6 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 1

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `version` | Bigint | Khoá chính | Số hiệu phiên bản danh mục hệ thống, là khoá chính. |
| 2 | `content_hash` | Text | Bắt buộc | Mã băm nội dung ảnh chụp danh mục hệ thống. |
| 3 | `snapshot` | Jsonb | Bắt buộc | Nội dung danh mục hệ thống tại thời điểm công bố. Đây là nguồn được SAO CHÉP MỘT LẦN vào tổ chức mới lúc khởi tạo; lúc chạy không có đường đọc ngược về đây. |
| 4 | `note` | Text | — | Ghi chú tự do của người quản trị. |
| 5 | `created_by` | Uuid | Khoá ngoại → `users` | Tài khoản quản trị nền tảng đã công bố phiên bản. |
| 6 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |

---

## A-2.5 Nhóm M5 — Huấn luyện & Mô hình

*Nhóm gồm 3 bảng.*

### Bảng `training_jobs`

*Bảng A2-36: Từ điển dữ liệu bảng `training_jobs`*

**Mô tả:** Tác vụ huấn luyện. Mang quan hệ ghim phiên bản danh mục — quan hệ ghim duy nhất tồn tại trong hệ thống.

**Khoá chính:** `job_id` · **Số trường:** 19 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 90

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `job_id` | Text | Khoá chính · Duy nhất | Định danh tác vụ huấn luyện. |
| 2 | `status` | Text | Bắt buộc | Trạng thái vòng đời của bản ghi. |
| 3 | `model_type` | Text | — | Kiến trúc mô hình được dùng cho lượt huấn luyện. |
| 4 | `config` | Jsonb | — | Toàn bộ siêu tham số của lượt chạy, lưu dạng cấu trúc. Là một phần của bản ghi nguồn gốc. |
| 5 | `auth_user_id` | Uuid | Khoá ngoại → `users` | Tài khoản đã khởi động tác vụ. |
| 6 | `created_at` | Timestamptz | — | Thời điểm bản ghi được tạo. |
| 7 | `started_at` | Timestamptz | — | Thời điểm tác vụ bắt đầu chạy, khác với thời điểm được xếp hàng. |
| 8 | `completed_at` | Timestamptz | — | Thời điểm tác vụ kết thúc. |
| 9 | `current_epoch` | Integer | Bắt buộc · Mặc định: `0` | Chu kỳ huấn luyện đang chạy. |
| 10 | `total_epochs` | Integer | Bắt buộc · Mặc định: `0` | Tổng số chu kỳ dự kiến. |
| 11 | `checkpoint_path` | Text | — | Đường dẫn tệp trọng số mô hình sinh ra. Đây là đầu ra bền vững phải chịu ràng buộc giam hãm theo tổ chức. |
| 12 | `test_acc` | Real | — | Độ chính xác trên tập kiểm thử giữ lại. |
| 13 | `test_f1` | Real | — | Điểm F1 trên tập kiểm thử giữ lại. |
| 14 | `error_message` | Text | — | Lý do thất bại nếu tác vụ hỏng. |
| 15 | `promoted_at` | Timestamptz | — | Thời điểm mô hình được thăng hạng thành phiên bản đang phục vụ. Để trống nghĩa là đã huấn luyện xong nhưng CHƯA phục vụ ai — phiên bản mới nhất không phải phiên bản đang phục vụ. |
| 16 | `evaluation` | Jsonb | — | Kết quả đánh giá chi tiết gồm độ chính xác theo lớp và ma trận nhầm lẫn. |
| 17 | `superseded_at` | Timestamptz | — | Thời điểm bị một phiên bản mới hơn thay thế. |
| 18 | `tenant_id` | Text | Khoá ngoại → `registry_versions` *(khoá ghép)* · Duy nhất · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 19 | `registry_version` | Bigint | Khoá ngoại → `registry_versions` *(khoá ghép)* | Phiên bản danh mục đã ghim cho lượt chạy. Đây là QUAN HỆ GHIM PHIÊN BẢN DUY NHẤT tồn tại trong hệ thống: nó ghim không gian nhãn, không ghim nội dung bộ dữ liệu. |

### Bảng `training_job_classes`

*Bảng A2-37: Từ điển dữ liệu bảng `training_job_classes`*

**Mô tả:** Ảnh chụp tập lớp THỰC SỰ tham gia một lượt huấn luyện sau ba cổng chặn, không phải tập người dùng chọn.

**Khoá chính:** (`job_id`, `class_idx`) · **Số trường:** 5 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `job_id` | Text | Khoá chính · Khoá ngoại → `training_jobs` | Tác vụ huấn luyện chứa ảnh chụp này. |
| 2 | `class_idx` | Integer | Khoá chính | Chỉ số lớp đã gán cho lượt chạy. Chỉ số phải liên tục từ 0, vì một chỉ số nhảy cóc nghĩa là mô hình học trên không gian nhãn khác với lúc suy luận. |
| 3 | `class_uid` | Text | Khoá ngoại → `classes` | Lớp thực sự tham gia lượt chạy. |
| 4 | `label` | Text | Bắt buộc | Nhãn hiển thị của lớp tại thời điểm chốt, lưu lại thành ảnh chụp. |
| 5 | `tenant_id` | Text | Khoá ngoại → `tenants` · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |

### Bảng `training_metrics`

*Bảng A2-38: Từ điển dữ liệu bảng `training_metrics`*

**Mô tả:** Chỉ số theo từng chu kỳ huấn luyện. Chỉ thêm.

**Khoá chính:** (`job_id`, `epoch`) · **Số trường:** 9 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 393

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `job_id` | Text | Khoá chính · Khoá ngoại → `training_jobs` | Tác vụ huấn luyện sinh ra chỉ số. |
| 2 | `epoch` | Integer | Khoá chính | Chu kỳ huấn luyện tương ứng với dòng chỉ số. |
| 3 | `train_loss` | Real | — | Hàm mất mát trên tập huấn luyện. |
| 4 | `train_acc` | Real | — | Độ chính xác trên tập huấn luyện. |
| 5 | `val_loss` | Real | — | Hàm mất mát trên tập kiểm định. |
| 6 | `val_acc` | Real | — | Độ chính xác trên tập kiểm định. |
| 7 | `val_f1` | Real | — | Điểm F1 trên tập kiểm định. |
| 8 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 9 | `tenant_id` | Text | Khoá ngoại → `tenants` · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |

---

## A-2.6 Nhóm M6 — Dịch vụ tổ chức & Tích hợp

*Nhóm gồm 12 bảng.*

### Bảng `plans`

*Bảng A2-39: Từ điển dữ liệu bảng `plans`*

**Mô tả:** Gói cước và hạn mức. Hệ thống lưu giá nhưng KHÔNG thu tiền.

**Khoá chính:** `plan_code` · **Số trường:** 25 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 4

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `plan_code` | Text | Khoá chính | Mã gói cước, là khoá chính. |
| 2 | `display_name` | Text | Bắt buộc | Tên hiển thị cho người dùng. |
| 3 | `description` | Text | Bắt buộc · Mặc định: `''` | Mô tả nghiệp vụ, dùng cho màn hình quản trị. |
| 4 | `max_seats` | Integer | — | Số thành viên tối đa của tổ chức dùng gói này. |
| 5 | `max_samples` | Integer | — | Số mẫu tối đa được lưu. |
| 6 | `max_storage_mb` | Integer | — | Dung lượng lưu trữ tối đa tính bằng megabyte. |
| 7 | `max_classes` | Integer | — | Số lớp từ vựng tối đa. |
| 8 | `max_training_jobs_per_month` | Integer | — | Số lượt huấn luyện tối đa mỗi tháng. |
| 9 | `max_concurrent_training_jobs` | Integer | Mặc định: `1` | Số tác vụ huấn luyện chạy đồng thời tối đa. |
| 10 | `max_queued_training_jobs` | Integer | Mặc định: `3` | Số tác vụ huấn luyện chờ trong hàng đợi tối đa. |
| 11 | `max_api_keys` | Integer | Mặc định: `0` | Số khoá API tối đa. |
| 12 | `max_webhook_endpoints` | Integer | Mặc định: `0` | Số điểm nhận webhook tối đa. |
| 13 | `price_cents` | Bigint | Mặc định: `0` | Giá gói tính bằng đơn vị nhỏ nhất của tiền tệ. Hệ thống lưu giá nhưng KHÔNG thu tiền. |
| 14 | `currency` | Text | Bắt buộc · Mặc định: `'VND'` | Đơn vị tiền tệ của giá. |
| 15 | `billing_period` | Text | Bắt buộc · Mặc định: `'monthly'` · Giá trị: `monthly`, `yearly`, `none` | Chu kỳ tính phí. |
| 16 | `is_self_serve` | Boolean | Bắt buộc · Mặc định: `false` | Gói có cho tự đăng ký hay chỉ cấp bằng tay. |
| 17 | `is_listed` | Boolean | Bắt buộc · Mặc định: `true` | Gói có hiển thị công khai trên bảng giá hay không. |
| 18 | `trial_days` | Integer | Bắt buộc · Mặc định: `0` | Số ngày dùng thử kèm gói. |
| 19 | `sort_order` | Integer | Bắt buộc · Mặc định: `0` | Thứ tự hiển thị trong bảng giá. |
| 20 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 21 | `updated_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được sửa lần gần nhất. |
| 26 | `max_workspaces` | Integer | — | Số không gian làm việc tối đa. |
| 27 | `max_projects` | Integer | — | Số dự án tối đa. |
| 28 | `included_training_credits` | Integer | — | Số tín dụng huấn luyện kèm theo gói. |
| 29 | `audit_retention_days` | Integer | — | Số ngày giữ nhật ký kiểm toán. |

### Bảng `tenant_subscriptions`

*Bảng A2-40: Từ điển dữ liệu bảng `tenant_subscriptions`*

**Mô tả:** Đăng ký dịch vụ của tổ chức: kỳ hạn, trạng thái, ân hạn, nhắc hạn.

**Khoá chính:** `subscription_id` · **Số trường:** 15 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 3

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `subscription_id` | Uuid | Khoá chính | Định danh đăng ký dịch vụ. |
| 2 | `tenant_id` | Text | Khoá ngoại → `tenants` · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 3 | `plan_code` | Text | Khoá ngoại → `plans` · Bắt buộc | Gói cước đang áp dụng. |
| 4 | `status` | Text | Bắt buộc · Mặc định: `'active'` | Trạng thái đăng ký. Trạng thái quá hạn vẫn cho ghi dữ liệu — đó là chủ ý, không phải lỗ hổng. |
| 5 | `started_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bắt đầu đăng ký. |
| 6 | `ended_at` | Timestamptz | — | Thời điểm kết thúc đăng ký. |
| 7 | `changed_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã đổi gói. |
| 8 | `note` | Text | Bắt buộc · Mặc định: `''` | Ghi chú tự do của người quản trị. |
| 9 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 10 | `current_period_start` | Timestamptz | — | Đầu kỳ hạn hiện tại. |
| 11 | `current_period_end` | Timestamptz | — | Cuối kỳ hạn hiện tại. |
| 12 | `auto_renew` | Boolean | Bắt buộc · Mặc định: `true` | Có tự động gia hạn khi hết kỳ hay không. |
| 13 | `grace_until` | Timestamptz | — | Hạn cuối của giai đoạn ân hạn sau khi quá kỳ. Sau mốc này mới áp khoá mềm. |
| 14 | `trial_ends_at` | Timestamptz | — | Thời điểm kết thúc dùng thử. |
| 15 | `last_reminder_days` | Integer | — | Mốc nhắc hạn gần nhất đã gửi, tính bằng số ngày trước hạn. Dùng để không gửi trùng một mốc nhắc. |

### Bảng `tenant_usage_daily`

*Bảng A2-41: Từ điển dữ liệu bảng `tenant_usage_daily`*

**Mô tả:** Mức sử dụng theo ngày của tổ chức, theo từng loại hạn mức.

**Khoá chính:** (`tenant_id`, `usage_date`, `metric`) · **Số trường:** 5 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 85

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `tenant_id` | Text | Khoá chính · Khoá ngoại → `tenants` | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 2 | `usage_date` | Date | Khoá chính | Ngày thống kê mức sử dụng. |
| 3 | `metric` | Text | Khoá chính | Loại hạn mức được đo trong ngày. |
| 4 | `value` | Bigint | Bắt buộc · Mặc định: `0` | Giá trị đo được của loại hạn mức tương ứng. |
| 5 | `computed_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm tính toán dòng thống kê. |

### Bảng `tenant_exports`

*Bảng A2-42: Từ điển dữ liệu bảng `tenant_exports`*

**Mô tả:** Yêu cầu xuất toàn bộ dữ liệu của một tổ chức.

**Khoá chính:** `export_id` · **Số trường:** 13 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `export_id` | Uuid | Khoá chính | Định danh yêu cầu xuất dữ liệu tổ chức. |
| 2 | `tenant_id` | Text | Khoá ngoại → `tenants` · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 3 | `requested_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã yêu cầu xuất dữ liệu. |
| 4 | `status` | Text | Bắt buộc · Mặc định: `'pending'` · Giá trị: `pending`, `running`, `ready`, `failed`, `expired` | Trạng thái của lượt xuất. |
| 5 | `scope` | Text | Bắt buộc · Mặc định: `'metadata'` · Giá trị: `metadata`, `full` | Phạm vi dữ liệu được xuất. |
| 6 | `file_path` | Text | — | Đường dẫn tệp lưu trữ kết quả. |
| 7 | `size_bytes` | Bigint | — | Kích thước tệp kết quả tính bằng byte. |
| 8 | `row_counts` | Jsonb | — | Số dòng theo từng bảng đã đưa vào bản xuất. |
| 9 | `error` | Text | — | Lý do thất bại nếu lượt xuất hỏng. |
| 10 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 11 | `completed_at` | Timestamptz | — | Thời điểm hoàn tất việc dựng tệp. |
| 12 | `expires_at` | Timestamptz | — | Thời điểm liên kết tải về hết hạn. Liên kết có giới hạn thời gian là một biện pháp bảo vệ, không phải một tiện ích. |
| 13 | `export_purpose` | Text | Bắt buộc · Mặc định: `'tenant_portability'` · Giá trị: `tenant_portability`, `internal_training`, `research_release`, `public_library` | Mục đích xuất dữ liệu, ghi lại để phục vụ kiểm toán. |

### Bảng `tenant_purges`

*Bảng A2-43: Từ điển dữ liệu bảng `tenant_purges`*

**Mô tả:** Yêu cầu dọn sạch dữ liệu tổ chức. Bản ghi này phải SỐNG SÓT qua chính thao tác dọn.

**Khoá chính:** `purge_id` · **Số trường:** 10 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `purge_id` | Uuid | Khoá chính | Định danh yêu cầu dọn sạch dữ liệu tổ chức. |
| 2 | `tenant_id` | Text | Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 3 | `display_name` | Text | Bắt buộc · Mặc định: `''` | Tên tổ chức tại thời điểm dọn, chép lại vì tổ chức sẽ không còn sau thao tác. |
| 4 | `requested_by` | Uuid | — | Tài khoản đã yêu cầu dọn sạch. |
| 5 | `row_counts` | Jsonb | — | Số dòng đã xoá theo từng bảng. |
| 6 | `files_removed` | Integer | Bắt buộc · Mặc định: `0` | Số tệp đã xoá khỏi lưu trữ. |
| 7 | `bytes_removed` | Bigint | Bắt buộc · Mặc định: `0` | Tổng dung lượng đã giải phóng. |
| 8 | `export_id` | Uuid | — | Bản xuất dữ liệu đã dựng trước khi dọn, nếu có. |
| 9 | `reason` | Text | Bắt buộc · Mặc định: `''` | Lý do dọn sạch. |
| 10 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |

### Bảng `webhook_endpoints`

*Bảng A2-44: Từ điển dữ liệu bảng `webhook_endpoints`*

**Mô tả:** Điểm nhận sự kiện của hệ thống bên thứ ba.

**Khoá chính:** `endpoint_id` · **Số trường:** 14 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `endpoint_id` | Uuid | Khoá chính | Định danh điểm nhận sự kiện. |
| 2 | `tenant_id` | Text | Khoá ngoại → `tenants` · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 3 | `url` | Text | Bắt buộc | Địa chỉ đích nhận sự kiện. |
| 4 | `secret` | Text | Bắt buộc | Bí mật dùng ký các sự kiện gửi đi, để phía nhận xác minh được nguồn. |
| 5 | `event_types` | Text | Bắt buộc · Mặc định: `'*'` | Danh sách loại sự kiện mà điểm nhận này đăng ký. |
| 6 | `is_active` | Boolean | Bắt buộc · Mặc định: `true` | Bản ghi còn hiệu lực hay đã ngưng sử dụng. |
| 7 | `description` | Text | Bắt buộc · Mặc định: `''` | Mô tả nghiệp vụ, dùng cho màn hình quản trị. |
| 8 | `created_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã tạo điểm nhận. |
| 9 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 10 | `last_success_at` | Timestamptz | — | Thời điểm gửi thành công gần nhất. |
| 11 | `last_failure_at` | Timestamptz | — | Thời điểm gửi thất bại gần nhất. |
| 12 | `failure_streak` | Integer | Bắt buộc · Mặc định: `0` | Số lần thất bại liên tiếp. Vượt ngưỡng thì điểm nhận bị tự động tắt. |
| 13 | `disabled_at` | Timestamptz | — | Thời điểm điểm nhận bị tắt. |
| 14 | `disabled_reason` | Text | — | Lý do tắt điểm nhận. |

### Bảng `webhook_deliveries`

*Bảng A2-45: Từ điển dữ liệu bảng `webhook_deliveries`*

**Mô tả:** Lịch sử từng lượt gửi sự kiện. Chỉ thêm.

**Khoá chính:** `delivery_id` · **Số trường:** 12 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `delivery_id` | Uuid | Khoá chính | Định danh một lượt gửi sự kiện. |
| 2 | `tenant_id` | Text | Khoá ngoại → `tenants` · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 3 | `endpoint_id` | Uuid | Khoá ngoại → `webhook_endpoints` · Bắt buộc | Điểm nhận đích của lượt gửi. |
| 4 | `event_type` | Text | Bắt buộc | Loại sự kiện được gửi. |
| 5 | `payload` | Jsonb | Bắt buộc | Nội dung sự kiện. |
| 6 | `status` | Text | Bắt buộc · Mặc định: `'pending'` · Giá trị: `pending`, `delivered`, `failed`, `dropped` | Trạng thái lượt gửi. |
| 7 | `attempts` | Integer | Bắt buộc · Mặc định: `0` | Số lần đã thử gửi. |
| 8 | `last_status_code` | Integer | — | Mã trạng thái HTTP mà phía nhận trả về ở lần thử gần nhất. |
| 9 | `last_error` | Text | — | Mô tả lỗi ở lần thử gần nhất. |
| 10 | `next_attempt_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm thử gửi lại tiếp theo. |
| 11 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 12 | `delivered_at` | Timestamptz | — | Thời điểm gửi thành công. |

### Bảng `support_tickets`

*Bảng A2-46: Từ điển dữ liệu bảng `support_tickets`*

**Mô tả:** Phiếu hỗ trợ trong phạm vi một tổ chức.

**Khoá chính:** `ticket_id` · **Số trường:** 10 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 2

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `ticket_id` | Uuid | Khoá chính · Mặc định: sinh UUID | Định danh phiếu hỗ trợ. |
| 2 | `tenant_id` | Text | Khoá ngoại → `tenants` · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 3 | `user_id` | Uuid | Khoá ngoại → `users` | Tài khoản đã tạo phiếu. |
| 4 | `subject` | Text | Bắt buộc | Tiêu đề phiếu. |
| 5 | `category` | Text | Bắt buộc · Mặc định: `'other'` · Giá trị: `account`, `billing`, `data`, `bug`, `other` | Nhóm vấn đề của phiếu. |
| 6 | `status` | Text | Bắt buộc · Mặc định: `'open'` · Giá trị: `open`, `pending`, `resolved`, `closed` | Trạng thái vòng đời của bản ghi. |
| 7 | `priority` | Text | Bắt buộc · Mặc định: `'normal'` · Giá trị: `low`, `normal`, `high`, `urgent` | Mức ưu tiên xử lý. |
| 8 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 9 | `updated_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được sửa lần gần nhất. |
| 10 | `resolved_at` | Timestamptz | — | Thời điểm phiếu được đánh dấu đã giải quyết. |

### Bảng `support_messages`

*Bảng A2-47: Từ điển dữ liệu bảng `support_messages`*

**Mô tả:** Tin nhắn trong một phiếu hỗ trợ. Chỉ thêm.

**Khoá chính:** `message_id` · **Số trường:** 9 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 4

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `message_id` | Uuid | Khoá chính · Mặc định: sinh UUID | Định danh tin nhắn trong phiếu hỗ trợ. |
| 2 | `tenant_id` | Text | Khoá ngoại → `tenants` · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 3 | `ticket_id` | Uuid | Khoá ngoại → `support_tickets` · Bắt buộc | Phiếu hỗ trợ chứa tin nhắn. |
| 4 | `author_id` | Uuid | Khoá ngoại → `users` | Tài khoản đã viết tin nhắn. |
| 5 | `author_label` | Text | Bắt buộc | Tên hiển thị của người viết tại thời điểm gửi. Là bằng chứng lịch sử nên không đổi theo khi tài khoản đổi tên. |
| 6 | `is_staff` | Boolean | Bắt buộc · Mặc định: `false` | Tin nhắn do nhân viên hỗ trợ viết hay do người dùng viết. |
| 7 | `body` | Text | Bắt buộc | Nội dung tin nhắn. |
| 8 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 9 | `author_kind` | Text | Mặc định: `'user'` · Giá trị: `user`, `staff`, `bot` | Loại tác giả tin nhắn. |

### Bảng `notifications`

*Bảng A2-48: Từ điển dữ liệu bảng `notifications`*

**Mô tả:** Thông báo trong ứng dụng gửi tới một tài khoản.

**Khoá chính:** `notification_id` · **Số trường:** 10 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 2

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `notification_id` | Uuid | Khoá chính · Mặc định: sinh UUID | Định danh thông báo. |
| 2 | `tenant_id` | Text | Khoá ngoại → `tenants` · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 3 | `user_id` | Uuid | Khoá ngoại → `users` · Bắt buộc | Tài khoản nhận thông báo. |
| 4 | `kind` | Text | Bắt buộc | Loại thông báo, dùng để lọc trên giao diện. |
| 5 | `title` | Text | Bắt buộc | Tiêu đề thông báo. |
| 6 | `body` | Text | Bắt buộc · Mặc định: `''` | Nội dung thông báo. |
| 7 | `link` | Text | — | Đường dẫn tới trang mà thông báo trỏ tới. |
| 8 | `severity` | Text | Bắt buộc · Mặc định: `'info'` · Giá trị: `info`, `success`, `warning`, `critical` | Mức độ nghiêm trọng của thông báo. |
| 9 | `read_at` | Timestamptz | — | Thời điểm người dùng đọc. Để trống nghĩa là chưa đọc. |
| 10 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |

### Bảng `event_outbox`

*Bảng A2-49: Từ điển dữ liệu bảng `event_outbox`*

**Mô tả:** Hộp thư đi cho sự kiện gửi ra ngoài, bảo đảm sự kiện không mất khi phía nhận hỏng.

**Khoá chính:** `event_id` · **Số trường:** 11 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `event_id` | Uuid | Khoá chính · Mặc định: sinh UUID | Định danh sự kiện trong hộp thư đi. |
| 2 | `tenant_id` | Text | Khoá ngoại → `tenants` | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 3 | `event_type_code` | Text | Bắt buộc | Mã loại sự kiện. |
| 4 | `payload` | Jsonb | Bắt buộc · Mặc định: `'{}'` | Nội dung sự kiện. |
| 5 | `occurred_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm sự kiện xảy ra trong nghiệp vụ, khác với thời điểm ghi vào hộp thư. |
| 6 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 7 | `dispatch_status` | Text | Bắt buộc · Mặc định: `'PENDING'` · Giá trị: `PENDING`, `IN_FLIGHT`, `DONE`, `FAILED` | Trạng thái gửi của sự kiện. |
| 8 | `attempts` | Integer | Bắt buộc · Mặc định: `0` | Số lần đã thử gửi. |
| 9 | `available_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm sự kiện sẵn sàng để tiến trình gửi lấy ra. |
| 10 | `processed_at` | Timestamptz | — | Thời điểm xử lý xong. |
| 11 | `last_error` | Text | — | Lỗi ở lần gửi gần nhất. |

### Bảng `google_sheets_sync_status`

*Bảng A2-50: Từ điển dữ liệu bảng `google_sheets_sync_status`*

**Mô tả:** Trạng thái phản chiếu dữ liệu sang bảng tính ngoài.

**Khoá chính:** `id` · **Số trường:** 7 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 1

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `id` | Integer | Khoá chính · Tự tăng | Định danh dòng trạng thái đồng bộ. |
| 2 | `table_name` | Varchar(50) | Duy nhất · Bắt buộc | Bảng nguồn đang được phản chiếu. |
| 3 | `current_spreadsheet_id` | Varchar(100) | Bắt buộc · Mặc định: `''` | Định danh bảng tính đích hiện tại. Đây là MỘT giá trị duy nhất cho toàn hệ thống, nên đường đồng bộ này không mang phạm vi tổ chức — một hạn chế đã biết. |
| 4 | `current_sheet_index` | Integer | Bắt buộc · Mặc định: `1` | Chỉ số trang tính đang ghi. |
| 5 | `current_data_rows` | Integer | Bắt buộc · Mặc định: `0` | Số dòng dữ liệu đã ghi ở trang tính hiện tại. |
| 6 | `max_rows_per_sheet` | Integer | Bắt buộc · Mặc định: `500000` | Số dòng tối đa mỗi trang tính trước khi chuyển sang trang mới. |
| 7 | `updated_at` | Timestamptz | Mặc định: thời điểm hiện tại | Thời điểm bản ghi được sửa lần gần nhất. |

---

## A-2.7 Nhóm M7 — Pháp lý, Kiểm toán & Nền tảng

*Nhóm gồm 9 bảng.*

### Bảng `legal_documents`

*Bảng A2-51: Từ điển dữ liệu bảng `legal_documents`*

**Mô tả:** Văn bản pháp lý ĐÃ CÔNG BỐ. Bất biến sau công bố, cưỡng chế bằng trigger ở tầng cơ sở dữ liệu.

**Khoá chính:** `doc_id` · **Số trường:** 21 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 4

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `doc_id` | Uuid | Khoá chính | Định danh kỹ thuật của văn bản. |
| 2 | `kind` | Text | Duy nhất · Bắt buộc · Giá trị: `terms`, `privacy`, `data_contribution`, `guardian` | Loại văn bản pháp lý. Cùng với số hiệu phiên bản tạo thành ĐỊNH DANH NGHIỆP VỤ mà mọi bản ghi chấp thuận trỏ tới. |
| 3 | `version` | Text | Duy nhất · Bắt buộc | Số hiệu phiên bản văn bản. |
| 4 | `effective_from` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Ngày văn bản bắt đầu có hiệu lực. |
| 5 | `content_hash` | Text | Bắt buộc | Mã băm nội dung. Đây là điểm neo của tính toàn vẹn: một bản ghi chấp thuận trỏ tới đúng nội dung đã ký chứ không trỏ tới một văn bản có thể đổi. |
| 6 | `url` | Text | Bắt buộc | Địa chỉ công khai để đọc văn bản. |
| 7 | `title` | Text | Bắt buộc · Mặc định: `''` | Tiêu đề văn bản. |
| 8 | `requires_reconsent` | Boolean | Bắt buộc · Mặc định: `false` | Thay đổi này có buộc mọi tài khoản chấp thuận lại hay không. Cờ này tách sửa lỗi chính tả khỏi đổi phạm vi xử lý dữ liệu — không phân biệt hai loại sẽ dẫn tới một trong hai thái cực đều xấu. |
| 9 | `body` | Text | Bắt buộc · Mặc định: `''` | Thân văn bản lưu trong cơ sở dữ liệu. Đây là vật mang nội dung mà cả bốn văn bản đang có hiệu lực đều dùng. Trigger bất biến kiểm trên cột này và trên mã băm nội dung. |
| 10 | `body_format` | Text | Bắt buộc · Mặc định: `'markdown'` · Giá trị: `markdown`, `text`, `file` | Định dạng của thân văn bản. |
| 11 | `language` | Text | Bắt buộc · Mặc định: `'vi'` | Mã ngôn ngữ của bản ghi. |
| 12 | `change_summary` | Text | Bắt buộc · Mặc định: `''` | Tóm tắt thay đổi so với phiên bản trước. |
| 13 | `published_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm công bố. Từ mốc này hàng dữ liệu trở thành BẤT BIẾN, cưỡng chế bằng trigger ở tầng cơ sở dữ liệu chứ không bằng kiểm tra ở ứng dụng. |
| 14 | `published_by` | Uuid | Khoá ngoại → `users` | Tài khoản quản trị đã công bố. Thao tác này đòi xác thực lại trong phiên. |
| 15 | `storage_backend` | Text | Bắt buộc · Mặc định: `'local'` | Kho lưu trữ chứa tệp văn bản nếu dùng vật mang tệp. |
| 16 | `storage_key` | Text | — | Khoá đối tượng của tệp văn bản trên kho lưu trữ. |
| 17 | `byte_size` | Integer | Bắt buộc · Mặc định: `0` | Kích thước nội dung tính bằng byte. |
| 18 | `file_key` | Text | — | Khoá tệp đính kèm. Lược đồ mở sẵn đường này nhưng chưa văn bản nào đang có hiệu lực dùng tới. |
| 19 | `file_name` | Text | — | Tên tệp đính kèm. |
| 20 | `file_mime` | Text | — | Kiểu MIME của tệp đính kèm. |
| 21 | `file_size` | Bigint | — | Kích thước tệp đính kèm. |

### Bảng `legal_document_drafts`

*Bảng A2-52: Từ điển dữ liệu bảng `legal_document_drafts`*

**Mô tả:** Bản thảo văn bản pháp lý. Khác với bản đã công bố, bản thảo sửa được.

**Khoá chính:** `draft_id` · **Số trường:** 21 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 1

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `draft_id` | Uuid | Khoá chính | Định danh bản thảo văn bản. |
| 2 | `kind` | Text | Bắt buộc · Giá trị: `terms`, `privacy`, `data_contribution`, `guardian` | Loại văn bản mà bản thảo hướng tới. |
| 3 | `title` | Text | Bắt buộc · Mặc định: `''` | Tiêu đề bản thảo. |
| 4 | `language` | Text | Bắt buộc · Mặc định: `'vi'` | Mã ngôn ngữ của bản ghi. |
| 5 | `body` | Text | Bắt buộc · Mặc định: `''` | Thân bản thảo. Khác với văn bản đã công bố, bản thảo SỬA ĐƯỢC. |
| 6 | `body_format` | Text | Bắt buộc · Mặc định: `'markdown'` | Định dạng thân bản thảo. |
| 7 | `change_summary` | Text | Bắt buộc · Mặc định: `''` | Tóm tắt thay đổi dự kiến. |
| 8 | `target_version` | Text | Bắt buộc · Mặc định: `''` | Số hiệu phiên bản mà bản thảo sẽ mang khi công bố. |
| 9 | `requires_reconsent` | Boolean | Bắt buộc · Mặc định: `false` | Bản thảo này khi công bố có buộc chấp thuận lại hay không. |
| 10 | `effective_from` | Timestamptz | — | Ngày hiệu lực dự kiến. |
| 11 | `status` | Text | Bắt buộc · Mặc định: `'draft'` · Giá trị: `draft`, `in_review`, `approved`, `published`, `discarded` | Trạng thái duyệt của bản thảo. |
| 12 | `revision` | Integer | Bắt buộc · Mặc định: `1` | Số lần sửa bản thảo. |
| 13 | `based_on_version` | Text | — | Phiên bản đã công bố mà bản thảo dựa vào. |
| 14 | `published_version` | Text | — | Phiên bản đã công bố sinh ra từ bản thảo này. |
| 15 | `storage_key` | Text | — | Khoá đối tượng nếu bản thảo lưu dạng tệp. |
| 16 | `content_hash` | Text | — | Mã băm nội dung bản thảo. |
| 17 | `byte_size` | Integer | Bắt buộc · Mặc định: `0` | Kích thước nội dung bản thảo. |
| 18 | `created_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã tạo bản ghi. |
| 19 | `updated_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã sửa bản ghi lần gần nhất. |
| 20 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |
| 21 | `updated_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được sửa lần gần nhất. |

### Bảng `legal_document_events`

*Bảng A2-53: Từ điển dữ liệu bảng `legal_document_events`*

**Mô tả:** Lịch sử vòng đời văn bản pháp lý. Chỉ thêm, cưỡng chế bằng trigger.

**Khoá chính:** `event_id` · **Số trường:** 12 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 5

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `event_id` | Bigint | Khoá chính · Tự tăng | Định danh sự kiện vòng đời văn bản. |
| 2 | `occurred_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm sự kiện xảy ra. |
| 3 | `actor_user_id` | Uuid | — | Tài khoản đã thực hiện hành động. |
| 4 | `actor_label` | Text | Bắt buộc · Mặc định: `''` | Tên hiển thị của người thực hiện tại thời điểm đó. Là bằng chứng lịch sử nên KHÔNG đổi theo khi tài khoản đổi tên. |
| 5 | `action` | Text | Bắt buộc | Hành động đã thực hiện: soạn, duyệt, công bố hay huỷ. |
| 6 | `kind` | Text | — | Loại văn bản liên quan. |
| 7 | `version` | Text | — | Phiên bản văn bản liên quan. |
| 8 | `draft_id` | Uuid | — | Bản thảo liên quan tới sự kiện. |
| 9 | `revision` | Integer | — | Số lần sửa tại thời điểm sự kiện. |
| 10 | `storage_key` | Text | — | Khoá đối tượng liên quan. |
| 11 | `content_hash` | Text | — | Mã băm nội dung tại thời điểm sự kiện. |
| 12 | `detail` | Jsonb | — | Chi tiết bổ sung của sự kiện. |

### Bảng `user_consents`

*Bảng A2-54: Từ điển dữ liệu bảng `user_consents`*

**Mô tả:** Chấp thuận của TÀI KHOẢN với điều khoản dịch vụ. KHÔNG chi phối đường phát hành dữ liệu.

**Khoá chính:** `consent_id` · **Số trường:** 11 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 21

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `consent_id` | Uuid | Khoá chính | Định danh bản ghi chấp thuận. |
| 2 | `user_id` | Uuid | Khoá ngoại → `users` · Bắt buộc | Tài khoản đã chấp thuận. |
| 3 | `kind` | Text | Khoá ngoại → `legal_documents` *(khoá ghép)* · Bắt buộc | Loại văn bản được chấp thuận. Cùng với phiên bản tạo thành khoá ngoại ghép trỏ tới đúng nội dung đã ký. |
| 4 | `version` | Text | Khoá ngoại → `legal_documents` *(khoá ghép)* · Bắt buộc | Phiên bản văn bản được chấp thuận. |
| 5 | `accepted_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm chấp thuận. |
| 6 | `ip_hash` | Text | — | Mã băm địa chỉ IP lúc chấp thuận, là bằng chứng bổ trợ mà không lưu địa chỉ gốc. |
| 7 | `user_agent` | Text | — | Thông tin trình duyệt lúc chấp thuận. |
| 8 | `withdrawn_at` | Timestamptz | — | Thời điểm rút chấp thuận. |
| 9 | `source` | Text | Bắt buộc · Mặc định: `'user'` · Giá trị: `user`, `backfill`, `import` | Nguồn phát sinh chấp thuận: lúc đăng ký, lúc đăng nhập hay từ trang tài khoản. |
| 10 | `note` | Text | Bắt buộc · Mặc định: `''` | Ghi chú tự do của người quản trị. |
| 11 | `recorded_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã ghi nhận, dùng khi chấp thuận được ghi hộ. |

### Bảng `signer_consents`

*Bảng A2-55: Từ điển dữ liệu bảng `signer_consents`*

**Mô tả:** Đồng thuận của NGƯỜI KÝ về việc sử dụng dữ liệu của mình. Đây mới là bảng chi phối đường phát hành dữ liệu.

**Khoá chính:** `consent_id` · **Số trường:** 11 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 1

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `consent_id` | Uuid | Khoá chính | Định danh bản ghi đồng thuận của người ký. |
| 2 | `tenant_id` | Text | Khoá ngoại → `signers` *(khoá ghép)* · Bắt buộc | Định danh tổ chức sở hữu bản ghi. Là cột phân biệt mà chính sách bảo mật mức hàng so với biến ngữ cảnh của phiên. |
| 3 | `signer_id` | Text | Khoá ngoại → `signers` *(khoá ghép)* · Bắt buộc | Người ký đã cho đồng thuận. Đây là ĐỒNG THUẬN CỦA CHỦ THỂ DỮ LIỆU, khác hẳn với việc tài khoản chấp thuận điều khoản dịch vụ — chỉ bảng này chi phối đường phát hành dữ liệu. |
| 4 | `scope` | Text | Bắt buộc · Giá trị: `internal_training`, `research_release`, `public_library` | Mức phát hành mà người ký cho phép. Ba mức tăng dần: dùng nội bộ để huấn luyện, phát hành cho nghiên cứu, và đưa vào thư viện công khai. |
| 5 | `kind` | Text | Khoá ngoại → `legal_documents` *(khoá ghép)* · Bắt buộc | Loại văn bản đồng thuận được ký. |
| 6 | `version` | Text | Khoá ngoại → `legal_documents` *(khoá ghép)* · Bắt buộc | Phiên bản văn bản đồng thuận. |
| 7 | `granted_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm cho đồng thuận. |
| 8 | `withdrawn_at` | Timestamptz | — | Thời điểm RÚT đồng thuận. Bản ghi cho đồng thuận gốc được giữ nguyên làm lịch sử — rút là thêm một sự kiện, không phải xoá một sự kiện. Sau mốc này mọi bản phát hành MỚI đều loại dữ liệu của người ký; các bản đã cấp không bị thu hồi và dữ liệu không bị xoá khỏi lưu trữ. |
| 9 | `guardian_name` | Text | — | Tên người giám hộ khi người ký chưa đủ tuổi tự quyết. |
| 10 | `evidence` | Text | — | Bằng chứng của việc cho đồng thuận, ví dụ tham chiếu tới bản ký giấy. |
| 11 | `recorded_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã ghi nhận đồng thuận. |

### Bảng `audit_log`

*Bảng A2-56: Từ điển dữ liệu bảng `audit_log`*

**Mô tả:** Nhật ký kiểm toán bền vững. Đường ghi TỪ CHỐI ghi khi thiếu phạm vi.

**Khoá chính:** `audit_id` · **Số trường:** 10 · **Bảo mật mức hàng:** ✔ có, kèm cưỡng chế với chủ sở hữu bảng · **Số bản ghi (18/08/2026):** 1

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `audit_id` | Bigint | Khoá chính · Tự tăng | Số thứ tự bản ghi kiểm toán, tự tăng. |
| 2 | `tenant_id` | Text | Khoá ngoại → `tenants` | Tổ chức liên quan tới thao tác. Đường ghi nhật ký TỪ CHỐI ghi khi không xác định được phạm vi, vì một bản ghi không biết mình thuộc tổ chức nào là bản ghi không dùng được làm bằng chứng. |
| 3 | `actor_user_id` | Uuid | Khoá ngoại → `users` | Tài khoản đã thực hiện thao tác. |
| 4 | `actor_label` | Text | — | Tên hiển thị của người thực hiện tại thời điểm đó. Là bằng chứng lịch sử nên KHÔNG cập nhật khi tài khoản đổi tên. |
| 5 | `action` | Text | Bắt buộc | Mã hành động đã thực hiện. |
| 6 | `target_type` | Text | — | Loại đối tượng bị tác động. |
| 7 | `target_id` | Text | — | Định danh đối tượng bị tác động. |
| 8 | `detail` | Jsonb | — | Chi tiết thao tác, gồm giá trị cũ với những hành động có thay đổi giá trị. |
| 9 | `ip_hash` | Text | — | Mã băm địa chỉ IP của người thực hiện. |
| 10 | `created_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được tạo. |

### Bảng `platform_settings`

*Bảng A2-57: Từ điển dữ liệu bảng `platform_settings`*

**Mô tả:** Tham số cấu hình nền tảng, áp được vào thể hiện đang chạy mà không cần khởi động lại.

**Khoá chính:** `key` · **Số trường:** 4 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `key` | Text | Khoá chính | Khoá cấu hình, là khoá chính. |
| 2 | `value` | Text | Bắt buộc | Giá trị cấu hình hiện tại. |
| 3 | `updated_by` | Uuid | Khoá ngoại → `users` | Tài khoản đã đổi cấu hình lần gần nhất. |
| 4 | `updated_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm bản ghi được sửa lần gần nhất. |

### Bảng `sot_authorized_keys`

*Bảng A2-58: Từ điển dữ liệu bảng `sot_authorized_keys`*

**Mô tả:** Khoá công khai của các máy được phép ghi nguồn sự thật.

**Khoá chính:** `public_key` · **Số trường:** 7 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 0

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `public_key` | Text | Khoá chính | Khoá công khai của máy được phép ghi nguồn sự thật, là khoá chính. Tập khoá tin cậy hiệu lực là HỢP của bảng này với danh sách khoá nền ghi trong mã nguồn, không phải thay thế. |
| 2 | `name` | Text | Duy nhất · Bắt buộc | Nhãn nhận diện máy ghi. |
| 3 | `fingerprint` | Text | Bắt buộc | Dấu vân tay của khoá, dùng đối chiếu nhanh. |
| 4 | `note` | Text | — | Ghi chú tự do của người quản trị. |
| 5 | `added_by` | Text | — | Tài khoản đã đăng ký khoá. Thao tác này đòi xác thực lại. |
| 6 | `added_at` | Timestamptz | Bắt buộc · Mặc định: thời điểm hiện tại | Thời điểm đăng ký khoá. |
| 7 | `revoked_at` | Timestamptz | — | Thời điểm thu hồi khoá. Sau mốc này mọi tạo tác đã ký bằng khoá đó không còn xác minh được, nên một lượt khởi động sau đó sẽ DỪNG nếu bản công bố hiện hành mang chữ ký của khoá vừa thu hồi. |

### Bảng `schema_migrations`

*Bảng A2-59: Từ điển dữ liệu bảng `schema_migrations`*

**Mô tả:** Lịch sử các bước di trú lược đồ đã áp. Chỉ thêm.

**Khoá chính:** (`version`, `applied_at`) · **Số trường:** 6 · **Bảo mật mức hàng:** — không bật · **Số bản ghi (18/08/2026):** 6

| STT | Tên trường | Kiểu dữ liệu | Ràng buộc | Diễn giải |
|---:|---|---|---|---|
| 1 | `version` | Integer | Khoá chính | Số hiệu phiên bản lược đồ đã áp. |
| 2 | `applied_at` | Timestamptz | Khoá chính · Mặc định: thời điểm hiện tại | Thời điểm áp bước di trú. |
| 3 | `applied_by` | Text | Bắt buộc | Tài khoản hoặc tiến trình đã áp bước di trú. |
| 4 | `applied_on` | Text | — | Máy đã chạy bước di trú. |
| 5 | `note` | Text | — | Ghi chú tự do của người quản trị. |
| 6 | `migration_checksum` | Text | — | Mã băm nội dung bước di trú, dùng phát hiện một bước đã bị sửa sau khi áp. |

---
