# Từ điển dữ liệu — Nhóm M6: Dịch vụ tổ chức & Tích hợp

*11 bảng · 134 cột. Trích từ CSDL đang chạy ngày 18/08/2026.
Quy ước đọc bảng: xem [DD_00_QUY_UOC_VA_MUC_LUC.md](DD_00_QUY_UOC_VA_MUC_LUC.md).*

**Nhóm nhiều cột nhất lược đồ.** Nó gom bốn việc khác nhau: gói cước và hạn mức ·
xuất và dọn dữ liệu · khoá API và webhook · hỗ trợ và thông báo.

**Một phát biểu phải giữ đúng mức:** hệ thống **đo và ghi nhận** mức sử dụng nhưng
**không thu tiền**. Không có cổng thanh toán. Giá trong `plans` là thông tin gói,
không phải một luồng mua.

---

## 6.1 Bảng `plans` — Gói cước và hạn mức

**Khoá chính:** `plan_code` · **RLS:** — không bật · **Số cột:** 25 · **Số hàng
(10/08/2026):** 4

### Nhóm A — Định danh gói

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| plan_code | text | — | Primary key | Mã gói, ví dụ `free` |
| display_name | text | — | Not null | Tên hiển thị |
| description | text | — | Not null, Default '' | Mô tả gói |
| sort_order | integer | 32 | Not null, Default 0 | Thứ tự hiển thị trong bảng giá |
| is_listed | boolean | — | Not null, Default true | Gói có hiện công khai không |
| is_self_serve | boolean | — | Not null, Default false | Tổ chức tự đăng ký được gói này không |

### Nhóm B — Hạn mức

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| max_seats | integer | 32 | Null, Check | Số thành viên tối đa. **Rỗng = KHÔNG GIỚI HẠN** |
| max_samples | integer | 32 | Null, Check | Số mẫu tối đa |
| max_storage_mb | integer | 32 | Null, Check | Dung lượng tối đa (MB) |
| max_classes | integer | 32 | Null, Check | Số lớp từ vựng tối đa |
| max_training_jobs_per_month | integer | 32 | Null, Check | Số lượt huấn luyện mỗi tháng |
| max_concurrent_training_jobs | integer | 32 | Null, Default 1, Check | Số tác vụ huấn luyện **chạy song song** — trần này bảo vệ GPU dùng chung |
| max_queued_training_jobs | integer | 32 | Null, Default 3, Check | Số tác vụ được xếp hàng chờ |
| max_api_keys | integer | 32 | Null, Default 0, Check | Số khoá API — **mặc định 0**, tức gói cơ bản không có tích hợp |
| max_webhook_endpoints | integer | 32 | Null, Default 0, Check | Số điểm nhận webhook |
| max_workspaces | integer | 32 | Null, Check | Số không gian làm việc — **hạn mức cho cấp phạm vi chưa có bề mặt API** |
| max_projects | integer | 32 | Null, Check | Số dự án — như trên |
| included_training_credits | integer | 32 | Null, Check | Tín dụng huấn luyện kèm theo gói |
| audit_retention_days | integer | 32 | Null, Check | **Số ngày giữ nhật ký kiểm toán** |

> **Quy tắc đọc quan trọng nhất của bảng này: giá trị RỖNG ở cột hạn mức nghĩa là
> KHÔNG GIỚI HẠN, không phải "bằng không".** Phân biệt này **đã được ghim bằng
> kiểm thử**, vì đọc nhầm sẽ **chặn toàn bộ hoạt động** của các gói không giới hạn
> — một lỗi im lặng và tê liệt.

### Nhóm C — Giá và kỳ hạn

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| price_cents | bigint | 64 | Null, Default 0, Check | **Giá tính bằng đơn vị nhỏ nhất** — số nguyên, không dùng số thực |
| currency | text | — | Not null, Default 'VND' | Đơn vị tiền tệ |
| billing_period | text | — | Not null, Default 'monthly', Check | Chu kỳ tính: tháng / năm |
| trial_days | integer | 32 | Not null, Default 0, Check | Số ngày dùng thử |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm tạo gói |
| updated_at | timestamptz | — | Not null, Default now() | Lần sửa gần nhất |

**`price_cents` là số nguyên, không phải số thực — đây là quy ước bắt buộc với
tiền tệ.** Số thực dấu phẩy động không biểu diễn chính xác được các giá trị thập
phân, nên phép cộng nhiều khoản sẽ tích luỹ sai số. Lưu bằng đơn vị nhỏ nhất và
chia khi hiển thị là cách duy nhất đúng.

**Ba ràng buộc `CHECK` gộp nhiều cột** — một ràng buộc phủ **11 cột hạn mức và
giá** cùng lúc, bảo đảm mọi giá trị không âm. Đặt một `CHECK` chung thay vì 11
`CHECK` riêng là quyết định về khả năng bảo trì: thêm một cột hạn mức mới chỉ cần
sửa một chỗ.

---

## 6.2 Bảng `tenant_subscriptions` — Đăng ký dịch vụ

**Khoá chính:** `subscription_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 15 ·
**Số hàng (10/08/2026):** 1

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| subscription_id | uuid | — | Primary key | Định danh lượt đăng ký |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức đăng ký |
| plan_code | text | — | Not null, Foreign key → plans.plan_code | Gói đang áp |
| status | text | — | Not null, Default 'active' | Trạng thái: đang hoạt động / quá hạn / đã kết thúc |
| started_at | timestamptz | — | Not null, Default now() | Thời điểm bắt đầu |
| ended_at | timestamptz | — | Null | Thời điểm kết thúc |
| current_period_start | timestamptz | — | Null | Mốc bắt đầu kỳ hạn hiện tại |
| current_period_end | timestamptz | — | Null | Mốc kết thúc kỳ hạn hiện tại |
| auto_renew | boolean | — | Not null, Default true | **Tự động gia hạn** — công tắc người dùng bật/tắt được |
| grace_until | timestamptz | — | Null | **Hết kỳ hạn nhưng vẫn ghi được tới mốc này** — cửa sổ ân hạn |
| trial_ends_at | timestamptz | — | Null | Ngày kết thúc dùng thử |
| last_reminder_days | integer | 32 | Null | **Đã nhắc ở mốc còn bao nhiêu ngày** — chống gửi trùng thư nhắc |
| changed_by | uuid | — | Null, Foreign key → users.id | Người thay đổi đăng ký |
| note | text | — | Not null, Default '' | Ghi chú |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm tạo bản ghi |

**`grace_until` cài đặt vòng đời ba mốc, và giao diện nói đúng ba mốc đó:**

| Giai đoạn | Điều kiện | Quyền của tổ chức |
|---|---|---|
| Trong kỳ | `now < current_period_end` | Ghi bình thường |
| **Ân hạn** | `current_period_end < now < grace_until` | **Vẫn ghi được** |
| Sau ân hạn | `now > grace_until` | **Chỉ đọc**; dữ liệu **vẫn còn nguyên** |

**`last_reminder_days` là cột chống gửi trùng.** Không có nó, tác vụ nhắc hạn chạy
hằng ngày sẽ gửi thư mỗi ngày trong suốt giai đoạn sắp hết hạn. Ghi lại mốc đã
nhắc biến việc nhắc từ *"gửi mỗi lần chạy"* thành *"gửi mỗi khi vượt một mốc mới"*.

---

## 6.3 Bảng `tenant_usage_daily` — Mức sử dụng theo ngày

**Khoá chính:** `(tenant_id, usage_date, metric)` · **RLS:** ✔ bật, ✔ FORCE ·
**Số cột:** 5 · **Số hàng (10/08/2026):** 69

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| tenant_id | text | — | Primary key (kép), Foreign key → tenants.tenant_id | Tổ chức |
| usage_date | date | — | Primary key (kép) | **Ngày** đo (không phải dấu thời gian) |
| metric | text | — | Primary key (kép) | **Tên chỉ số** — mô hình khoá–giá trị, thêm chỉ số mới không cần đổi lược đồ |
| value | bigint | 64 | Not null, Default 0 | Giá trị đo được |
| computed_at | timestamptz | — | Not null, Default now() | Thời điểm tính |

**Khoá chính ba cột với `metric` là mô hình khoá–giá trị có chủ đích.** Thêm một
chỉ số mới (ví dụ *số phút GPU*) chỉ cần ghi hàng mới, không cần thêm cột. Đánh
đổi: **không kiểm được ở tầng CSDL** rằng tên chỉ số hợp lệ.

> **Bảng này là nguồn cho việc TÍNH TIỀN ("đã từng dùng"). Con số dùng để CHẶN
> ("đang dùng") đọc từ nguồn khác, CÓ CHỦ ĐÍCH.** Giao diện gói dịch vụ nói thẳng:
> *"Số liệu đọc trực tiếp từ dữ liệu hiện có, không phải từ một bộ đếm riêng."*
> Hai nguồn khác nhau vì hai câu hỏi khác nhau: *đã dùng bao nhiêu trong kỳ* và
> *hiện đang chiếm bao nhiêu*.

---

## 6.4 Bảng `tenant_exports` — Yêu cầu xuất dữ liệu

**Khoá chính:** `export_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 12 · **Số
hàng (10/08/2026):** 0

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| export_id | uuid | — | Primary key | Định danh yêu cầu xuất |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức yêu cầu |
| requested_by | uuid | — | Null, Foreign key → users.id | Người yêu cầu |
| status | text | — | Not null, Default 'pending', Check | Trạng thái xử lý |
| scope | text | — | Not null, Default 'metadata', Check | **Phạm vi xuất**: chỉ siêu dữ liệu hay cả tệp đặc trưng |
| file_path | text | — | Null | Đường dẫn gói kết quả |
| size_bytes | bigint | 64 | Null | Kích thước gói |
| row_counts | jsonb | — | Null | **Số hàng theo từng bảng** trong gói — bằng chứng đối chiếu |
| error | text | — | Null | Lý do thất bại |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm yêu cầu |
| completed_at | timestamptz | — | Null | Thời điểm hoàn tất |
| expires_at | timestamptz | — | Null | **Hạn tải** — gói tự hết hiệu lực |

**`row_counts` kiểu `jsonb` là bằng chứng đối chiếu, không phải thống kê trang
trí.** Nó cho người nhận gói kiểm được rằng bản xuất **đủ số hàng** so với thứ họ
mong đợi, mà không phải mở gói ra đếm.

**`expires_at` làm gói xuất tự hết hạn.** Một gói dữ liệu tổ chức nằm mãi trên đĩa
là một bề mặt tấn công tồn tại vô thời hạn.

---

## 6.5 Bảng `tenant_purges` — Yêu cầu dọn sạch dữ liệu

**Khoá chính:** `purge_id` · **RLS:** — **KHÔNG BẬT** · **Số cột:** 10 · **Số
hàng (10/08/2026):** 0

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| purge_id | uuid | — | Primary key | Định danh yêu cầu dọn |
| tenant_id | text | — | Not null | Tổ chức bị dọn — **không có khoá ngoại**, vì tổ chức có thể đã bị xoá |
| display_name | text | — | Not null, Default '' | **Bản sao tên tổ chức lúc dọn** — giữ lại vì hàng gốc sẽ biến mất |
| requested_by | uuid | — | Null | Người yêu cầu |
| row_counts | jsonb | — | Null | Số hàng đã xoá theo từng bảng |
| files_removed | integer | 32 | Not null, Default 0 | Số tệp đã xoá |
| bytes_removed | bigint | 64 | Not null, Default 0 | Dung lượng đã giải phóng |
| export_id | uuid | — | Null | **Bản xuất trước khi dọn**, nếu có — đường quay lại duy nhất |
| reason | text | — | Not null, Default '' | Lý do dọn |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm dọn |

> ### Đây là bảng DUY NHẤT có `tenant_id` mà không bật RLS
>
> **Độ phủ cách ly là 34/35 ≈ 97,1 % chính vì bảng này.**
>
> **Vì sao không bật:** bảng ghi nhận yêu cầu **dọn sạch dữ liệu của một tổ chức**,
> và nó phải sống sót **sau khi tổ chức đó biến mất**. Bật chính sách theo
> `tenant_id` lên nó sẽ khiến bản ghi trở nên không đọc được bằng bất kỳ ngữ cảnh
> nào ngay khi tổ chức bị xoá — tức mất luôn bằng chứng về việc đã dọn.
>
> **Rủi ro, nêu thẳng:** một quản trị viên nền tảng đọc được **toàn bộ lịch sử yêu
> cầu dọn của mọi tổ chức**. Điều này đúng với vai đó, **song không có tầng cưỡng
> chế nào đứng sau** — việc lọc hoàn toàn do tầng ứng dụng làm.

**Ba cột `display_name`, `row_counts`, `export_id` cùng phục vụ một mục tiêu: giữ
đủ bằng chứng khi đối tượng gốc đã biến mất.** Không có `display_name`, bản ghi chỉ
còn một mã tổ chức không tra được thành tên. Không có `export_id`, không biết dữ
liệu đã được xuất ra trước khi dọn hay chưa.

---

## 6.6 Bảng `api_keys` — Khoá API

**Khoá chính:** `key_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 12 · **Số hàng
(10/08/2026):** 0

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| key_id | uuid | — | Primary key | Định danh khoá |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức sở hữu khoá |
| name | text | — | Not null, Default '' | **Tên gợi nhớ** do người dùng đặt |
| prefix | text | — | Not null, Unique | **Tiền tố khoá** — đủ để nhận ra trên giao diện, **không đủ để dùng** |
| key_hash | text | — | Not null | **MÃ BĂM của khoá**; giá trị gốc không lưu ở đâu cả |
| scopes | text | — | Not null, Default 'read' | Phạm vi quyền: chỉ đọc / đọc và ghi |
| created_by | uuid | — | Null, Foreign key → users.id | Người cấp khoá |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm cấp |
| last_used_at | timestamptz | — | Null | **Lần dùng gần nhất** — cơ sở để phát hiện khoá bỏ quên |
| expires_at | timestamptz | — | Null | Hạn dùng |
| revoked_at | timestamptz | — | Null | Thời điểm thu hồi |
| revoked_by | uuid | — | Null, Foreign key → users.id | Người thu hồi |

**Cặp `prefix` (rõ) và `key_hash` (băm) là một mẫu thiết kế đáng nêu.** Người dùng
cần **nhận ra** khoá nào trong danh sách để thu hồi đúng cái; nhưng hệ thống
**không được** lưu khoá đủ để dùng lại. Tiền tố giải được mâu thuẫn đó: nó định
danh mà không cấp quyền.

Giao diện nói đúng cơ chế: *"Đây là lần **duy nhất** giá trị này hiện ra. Máy chủ
chỉ lưu bản băm, nên không ai — **kể cả quản trị viên** — đọc lại được. Nếu mất,
hãy thu hồi và cấp lại."*

**`last_used_at` là cột vệ sinh an ninh:** một khoá cấp ba tháng trước và chưa
dùng lần nào là khoá nên thu hồi.

---

## 6.7 Bảng `webhook_endpoints` — Điểm nhận sự kiện

**Khoá chính:** `endpoint_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 14 · **Số
hàng (10/08/2026):** 0

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| endpoint_id | uuid | — | Primary key | Định danh điểm nhận |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức sở hữu |
| url | text | — | Not null | Địa chỉ nhận sự kiện |
| secret | text | — | Not null | **Bí mật để ký tải trọng** — bên nhận dùng nó xác minh sự kiện đúng là từ hệ thống |
| event_types | text | — | Not null, Default '*' | Danh sách loại sự kiện quan tâm; `*` là tất cả |
| is_active | boolean | — | Not null, Default true | Điểm nhận còn hoạt động |
| description | text | — | Not null, Default '' | Mô tả |
| created_by | uuid | — | Null, Foreign key → users.id | Người đăng ký |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm đăng ký |
| last_success_at | timestamptz | — | Null | Lần gửi thành công gần nhất |
| last_failure_at | timestamptz | — | Null | Lần gửi hỏng gần nhất |
| failure_streak | integer | 32 | Not null, Default 0 | **Số lần hỏng liên tiếp** — cơ sở để tự tắt |
| disabled_at | timestamptz | — | Null | Thời điểm bị tự động tắt |
| disabled_reason | text | — | Null | Lý do tắt |

**Bộ ba `failure_streak` + `disabled_at` + `disabled_reason` cài đặt cơ chế ngắt
mạch (circuit breaker).** Một điểm nhận chết mà hệ thống cứ gửi mãi sẽ làm nghẽn
hàng đợi và tiêu tài nguyên vô ích. Đếm số lần hỏng **liên tiếp** (không phải tổng
số lần hỏng) là cách phân biệt *"bên nhận đang chết"* với *"bên nhận thỉnh thoảng
lỗi"*.

**`secret` lưu ở dạng RÕ, không băm — và đó là đúng.** Khác với khoá API, hệ thống
**cần** giá trị gốc để **tự tính chữ ký** cho mỗi lần gửi. Băm một chiều không dùng
được cho mục đích này. Đây là cùng lý do với `user_totp.secret_enc` ở nhóm M1.

---

## 6.8 Bảng `webhook_deliveries` — Lịch sử gửi sự kiện

**Khoá chính:** `delivery_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 12 · **Số
hàng (10/08/2026):** 0

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| delivery_id | uuid | — | Primary key | Định danh lượt gửi |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức |
| endpoint_id | uuid | — | Not null, Foreign key → webhook_endpoints.endpoint_id | Điểm nhận |
| event_type | text | — | Not null | Loại sự kiện |
| payload | jsonb | — | Not null | **Tải trọng đã gửi**, lưu nguyên để gửi lại được |
| status | text | — | Not null, Default 'pending', Check | Trạng thái: chờ / thành công / thất bại |
| attempts | integer | 32 | Not null, Default 0 | Số lần đã thử |
| last_status_code | integer | 32 | Null | **Mã trả về HTTP** của lần thử gần nhất |
| last_error | text | — | Null | Lỗi của lần thử gần nhất |
| next_attempt_at | timestamptz | — | Not null, Default now() | **Thời điểm thử lại kế tiếp** — cài đặt lùi dần theo cấp số |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm tạo lượt gửi |
| delivered_at | timestamptz | — | Null | Thời điểm gửi thành công |

**`next_attempt_at` biến việc thử lại thành dữ liệu thay vì thành logic.** Tiến
trình nền chỉ cần hỏi *"lượt nào tới hạn thử lại"*, không cần giữ lịch trong bộ
nhớ — nên khởi động lại tiến trình không làm mất lịch thử lại.

**`payload` lưu nguyên khối là điều kiện để gửi lại được.** Không có nó, một lượt
gửi hỏng chỉ còn cách dựng lại tải trọng từ trạng thái hiện tại — mà trạng thái
hiện tại có thể đã khác với lúc sự kiện xảy ra.

---

## 6.9 Bảng `support_tickets` — Phiếu hỗ trợ

**Khoá chính:** `ticket_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 10

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| ticket_id | uuid | — | Primary key, Default gen_random_uuid() | Định danh phiếu |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức |
| user_id | uuid | — | Null, Foreign key → users.id | Người mở phiếu |
| subject | text | — | Not null | **Tiêu đề** — giao diện đòi tối thiểu 5 ký tự |
| category | text | — | Not null, Default 'other', Check | Phân loại vấn đề |
| status | text | — | Not null, Default 'open', Check | Trạng thái: mở / đang xử lý / đã đóng |
| priority | text | — | Not null, Default 'normal', Check | Mức ưu tiên |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm mở |
| updated_at | timestamptz | — | Not null, Default now() | Lần cập nhật gần nhất — **cơ sở tính tồn đọng** |
| resolved_at | timestamptz | — | Null | Thời điểm đóng |

**`updated_at` là cột nuôi cơ chế thư tồn đọng.** Hai loại thư khác nhau về bản
chất: thư *phiếu mới* là **sự kiện** (gửi một lần khi tạo); thư *tồn đọng* là
**trạng thái** (gửi khi hàng đợi quá **5 giờ** hoặc quá **10 tin** chưa trả lời).
Gộp hai loại sẽ hoặc gửi lặp, hoặc không bao giờ nhắc lại một hàng đợi đang ứ.

---

## 6.10 Bảng `support_messages` — Tin nhắn trong phiếu

**Khoá chính:** `message_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 9

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| message_id | uuid | — | Primary key, Default gen_random_uuid() | Định danh tin |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức |
| ticket_id | uuid | — | Not null, Foreign key → support_tickets.ticket_id | Phiếu chứa tin |
| author_id | uuid | — | Null, Foreign key → users.id | Tài khoản người gửi; **rỗng khi người gửi là trợ lý tự động** |
| author_label | text | — | Not null | **Tên người gửi tại thời điểm gửi**, chép cứng |
| author_kind | text | — | Null, Default 'user', Check | **Loại người gửi**: người dùng / nhân viên trực / trợ lý tự động |
| is_staff | boolean | — | Not null, Default false | Tin do bên vận hành gửi |
| body | text | — | Not null | Nội dung — giao diện đòi tối thiểu 10 ký tự |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm gửi |

**Ràng buộc `CHECK` trên cặp `(author_kind, is_staff)`** buộc hai cột nhất quán:
không thể có tin vừa mang loại *người dùng* vừa đánh dấu *nhân viên*.

**`author_label` chép cứng theo cùng nguyên tắc với `audit_log.actor_label`:** một
tin nhắn phải nói ra tên người gửi **tại thời điểm gửi**. Cập nhật nó theo tên hiện
tại là viết lại lịch sử hội thoại.

**`author_id` rỗng là trạng thái hợp lệ**, không phải dữ liệu thiếu: trợ lý tự động
trả lời ngay khi phiếu được tạo, và nó không có tài khoản.

---

## 6.11 Bảng `notifications` — Thông báo trong ứng dụng

**Khoá chính:** `notification_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 10

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| notification_id | uuid | — | Primary key, Default gen_random_uuid() | Định danh thông báo |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức |
| user_id | uuid | — | Not null, Foreign key → users.id | **Người nhận** |
| kind | text | — | Not null | Loại thông báo: gói dịch vụ / bảo mật / huấn luyện |
| title | text | — | Not null | Tiêu đề |
| body | text | — | Not null, Default '' | Nội dung |
| link | text | — | Null | Đường dẫn tới màn hình liên quan |
| severity | text | — | Not null, Default 'info', Check | Mức độ: thông tin / cảnh báo / lỗi |
| read_at | timestamptz | — | Null | **Cờ đã đọc** — rỗng nghĩa là chưa đọc |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm phát sinh |

**`read_at` rỗng là nguồn của số đếm trên chuông thông báo.** Ba giá trị `kind`
khớp đúng ba nguồn mà giao diện liệt kê ở trạng thái rỗng: *"Khi có việc cần bạn
biết — gói dịch vụ, bảo mật, huấn luyện — nó sẽ xuất hiện ở đây."*

**Đường này tồn tại vì thư điện tử có thể không gửi được.** Cấu hình máy chủ thư
sai làm thư **im lặng không tới**; thông báo trong ứng dụng không phụ thuộc vào đó.

---

## Tổng kết nhóm M6

```
plans (1) ──< tenants                          [gói đang áp]
plans (1) ──< tenant_subscriptions ──> tenants [lịch sử đăng ký]
tenants (1) ──< tenant_usage_daily             [khoá 3 cột: tổ chức × ngày × chỉ số]
tenants (1) ──< tenant_exports
tenant_purges                                  [KHÔNG có khoá ngoại tới tenants — cố ý]
tenants (1) ──< api_keys
tenants (1) ──< webhook_endpoints (1) ──< webhook_deliveries
tenants (1) ──< support_tickets (1) ──< support_messages
tenants (1) ──< notifications ──> users
```

| Đặc điểm | Giá trị |
|---|:--:|
| Bảng có `tenant_id` | **11 / 11** |
| Bảng bật RLS + FORCE | **9 / 11** |
| Bảng **không** bật RLS | 2 — `plans` (dữ liệu tham chiếu chung), `tenant_purges` (**khoảng trống thật**) |
| Cột `jsonb` | 4 |
| Bảng lưu giá trị **băm** | 1 (`api_keys`) |
| Bảng lưu giá trị **rõ có chủ đích** | 1 (`webhook_endpoints.secret`) |

**Ba cách lưu bí mật trong lược đồ, và mỗi cách có lý do kỹ thuật riêng — không
được đánh đồng:**

| Cách | Bảng | Vì sao |
|---|---|---|
| **Băm** một chiều | `api_keys.key_hash`, mọi `*_token_hash` | Hệ thống chỉ cần **so khớp**, không cần đọc lại |
| **Mã hoá** hai chiều | `user_totp.secret_enc` | Cần bí mật gốc để **tự sinh mã** đối chiếu |
| **Rõ** | `webhook_endpoints.secret` | Cần giá trị gốc để **tự ký** mỗi lần gửi |
