# 9. Thiết kế dữ liệu và từ điển dữ liệu (Data Design · Data Dictionary)

*Số liệu lược đồ truy vấn trực tiếp cơ sở dữ liệu đang chạy ngày **17/08/2026**.
Số hàng là **ảnh chụp ngày 10/08/2026** — số hàng thay đổi mỗi ngày, và một bảng
số liệu không ghi ngày là một bảng không kiểm chứng được.*

---

## 9.1 Mô tả miền dữ liệu

### 9.1.1 Miền thông tin

Miền thông tin của hệ thống bao gồm dữ liệu về: **danh tính** (tài khoản, phiên,
yếu tố xác thực), **tổ chức và phân quyền**, **dữ liệu ký hiệu** (mẫu, lớp, phiên
thu, người ký), **danh mục** (ngôn ngữ, phương ngữ, vùng miền, phiên bản), **mô
hình** (tác vụ huấn luyện, chỉ số), **dịch vụ tổ chức** (gói cước, hạn mức, khoá
API, hỗ trợ), và **pháp lý – kiểm toán** (văn bản, đồng thuận, nhật ký).

### 9.1.2 Quy mô lược đồ

| Chỉ số | Giá trị |
|---|---:|
| Bảng nghiệp vụ | **57** |
| Khung nhìn | 1 (`tenant_members`) |
| Bảng kỹ thuật không thuộc mô hình nghiệp vụ | 1 (`schema_migrations`) |
| Khoá ngoại | **117** |
| Trong đó khoá ngoại **ghép** mang định danh tổ chức | **22** |
| Bảng mang cột định danh tổ chức | 34 |
| Bảng bật chính sách bảo mật mức hàng | 32 (**32/32 bật cờ cưỡng chế với chủ sở hữu**) |

*Cơ sở dữ liệu báo 58 bảng; bảng thứ 58 là `schema_migrations` — sổ ghi phiên bản
lược đồ, không thuộc mô hình nghiệp vụ nên không tính vào 57.*

### 9.1.3 Cách chuyển miền thông tin sang cấu trúc dữ liệu

| Bước | Nội dung |
|---|---|
| **Ánh xạ** | Mỗi thực thể nghiệp vụ ánh xạ sang một hoặc nhiều bảng quan hệ PostgreSQL |
| **Hình thái** | Bảng biểu diễn thực thể; hàng là một thể hiện; cột là thuộc tính |
| **Diễn giải ngữ nghĩa** | Quan hệ định nghĩa bằng khoá chính và khoá ngoại. **Khoá ngoại ghép** mang thêm định danh tổ chức để quan hệ chỉ hợp lệ **trong một tổ chức** |
| **Cấu trúc bất thường** | Ba trường hợp cố ý lệch chuẩn: khung nhìn thay bảng (`tenant_members`), trigger bất biến (`legal_documents`), và nguồn sự thật nằm ngoài CSDL (tệp CSV) |

---

## 9.2 Mô hình mức khái niệm (CDM)

**Mười ba thực thể khái niệm** và câu hỏi nghiệp vụ mỗi thực thể trả lời:

| Thực thể | Trả lời câu hỏi |
|---|---|
| **Tổ chức** | Ranh giới cách ly và quản trị: dữ liệu này thuộc về ai |
| **Tài khoản** | Ai đang dùng hệ thống |
| **Vai theo phạm vi** | Tài khoản này làm được gì, ở phạm vi nào |
| **Người ký** | **Chủ thể dữ liệu** — ai có bàn tay trong mẫu |
| **Mẫu** | Một lượt thực hiện ký hiệu, đã trích đặc trưng |
| **Lớp từ vựng** | Mẫu này là ký hiệu của từ nào, theo phương ngữ nào |
| **Phiên thu** | Nhiều mẫu cùng một lượt ngồi trước camera |
| **Phương ngữ / Vùng miền** | Biến thể vùng miền — **một phần định danh lớp** |
| **Phiên bản danh mục** | Ảnh chụp bất biến của danh mục — bảo toàn **không gian nhãn** |
| **Tác vụ huấn luyện** | Dữ liệu thành mô hình như thế nào |
| **Gói cước / Đăng ký dịch vụ** | Tổ chức được dùng tới hạn mức nào |
| **Văn bản pháp lý** | Điều khoản nào đang có hiệu lực |
| **Đồng thuận** | Người ký cho phép dùng dữ liệu tới mức nào |

**Ba quan hệ khái niệm quan trọng nhất, và lý do chúng không được gộp:**

1. **Tài khoản — Mẫu** và **Người ký — Mẫu** là **hai quan hệ khác nhau**. Tài
   khoản là người bấm nút; người ký là chủ thể dữ liệu. Gộp lại là đánh mất khả
   năng trả lời yêu cầu rút dữ liệu.
2. **Lớp — Phương ngữ** không phải quan hệ "thuộc tính": phương ngữ tham gia vào
   **định danh** của lớp. Hai lớp cùng nhãn khác phương ngữ là **hai lớp**.
3. **Tác vụ huấn luyện — Phiên bản danh mục** là quan hệ **ghim**, không phải
   tham chiếu thông thường: nó trỏ tới một ảnh chụp bất biến, không trỏ tới trạng
   thái hiện tại.

---

## 9.3 Mô hình mức logic — bảy nhóm mô-đun

Trình bày cả 57 bảng trong một sơ đồ duy nhất là trình bày một thứ không ai đọc
được. Mô hình vì thế chia theo bảy nhóm, mỗi nhóm là một khối chức năng khép kín.

| # | Nhóm mô-đun | Số bảng | Trả lời câu hỏi | Chịu ranh giới tổ chức |
|---|---|:--:|---|---|
| M1 | Danh tính & Truy cập | 7 | Anh là ai, phiên của anh còn hiệu lực không | Một phần |
| M2 | Tổ chức & Phân quyền | 9 | Anh thuộc tổ chức nào, với vai gì | Có |
| M3 | Kho dữ liệu mẫu | 6 | Dữ liệu ký hiệu và người ký ra nó | **Có — trọng tâm** |
| M4 | Danh mục & Registry | 11 | Được phép thu lớp nào, phiên bản danh mục nào | Có, trừ mặt phẳng cộng đồng |
| M5 | Huấn luyện & Mô hình | 3 | Dữ liệu thành mô hình như thế nào | Có |
| M6 | Dịch vụ tổ chức & Tích hợp | 11 | Gói cước, hạn mức, khoá API, hỗ trợ | Có |
| M7 | Pháp lý, Kiểm toán & Nền tảng | 10 | Ai đồng ý gì, ai làm gì, cấu hình nền tảng | Một phần |
| | **Tổng** | **57** | | |

---

## 9.4 Từ điển dữ liệu (Data Dictionary)

Ký hiệu cột **RLS**: ✔ bảng bật chính sách bảo mật mức hàng · — không bật.
Cột **Hàng**: ảnh chụp 10/08/2026 · `—` nghĩa là không có số liệu tại thời điểm
chụp, **không** phải bằng 0.

### 9.4.1 M1 — Danh tính & Truy cập

| Bảng | Khoá chính | Cột chính | RLS | Hàng |
|---|---|---|:--:|---:|
| `users` | `id` | tên đăng nhập, email, mã băm mật khẩu, cờ quản trị nền tảng, `is_active`, `suspended_at` | ✔ | 10 |
| `refresh_tokens` | `id` | mã băm token, `user_id`, thiết bị, IP, `expires_at`, `revoked_at` | — | 107 |
| `password_reset_tokens` | `id` | mã băm token, `user_id`, `expires_at`, `used_at` | — | 7 |
| `verification_codes` | `id` | mã băm mã, kênh (thư/SMS), địa chỉ đích, `expires_at`, số lần thử | — | 2 |
| `user_totp` | `user_id` | bí mật đã mã hoá, thời điểm kích hoạt | — | — |
| `user_recovery_codes` | `id` | `user_id`, mã băm mã khôi phục, `used_at` | — | — |
| `user_action_passcodes` | `id` | `user_id`, mục đích, mã băm, `expires_at` | — | — |

**Ghi chú thiết kế.** Bảng `users` bật chính sách nhưng chính sách của nó **không
thể** thuần theo tổ chức: truy vấn tìm tài khoản lúc đăng nhập chạy **trước khi**
biết tổ chức. Đây là chỗ sinh ra cái bẫy "0 hàng bị đọc thành không có gì".

Mọi token và mã một lần đều lưu ở **dạng băm**, không lưu giá trị gốc.

### 9.4.2 M2 — Tổ chức & Phân quyền

| Bảng | Khoá chính | Cột chính | RLS | Hàng |
|---|---|---|:--:|---:|
| `tenants` | `id` | mã định danh, tên, `billing_status`, `deleted_at` | — | 1 |
| `workspaces` | `id` | `tenant_id`, tên — **chưa có bề mặt API** | ✔ | — |
| `projects` | `id` | `workspace_id`, tên — **chưa có bề mặt API** | ✔ | — |
| `roles` | `id` | mã vai, cấp phạm vi áp dụng | — | 3 |
| `permissions` | `id` | mã quyền, mô tả | — | — |
| `role_permissions` | (`role_id`,`permission_id`) | — | — | — |
| `role_assignments` | `id` | chủ thể, `role_id`, **`scope_level`**, `scope_id` | ✔ | — |
| `memberships` | `id` | bảng nền của quan hệ thành viên | ✔ | — |
| `tenant_members` ⟨khung nhìn⟩ | — | lát cắt `scope_level = 'tenant'` của `role_assignments` | ✔ | 10 |
| `tenant_invitations` | `id` | `tenant_id`, địa chỉ nhận, vai dự kiến, mã băm token, `expires_at`, trạng thái | ✔ | 0 |

**Ghi chú thiết kế.** `tenant_members` là **khung nhìn**, không phải bảng. Hệ quả
cụ thể: **không tạo được chỉ mục** trên nó, và **không dùng được mệnh đề xử lý
xung đột** khi ghi — mọi đường ghi phải nhắm vào bảng nền. Khung nhìn dùng chế độ
gọi theo quyền của người gọi (`security_invoker`) để chính sách bảo mật mức hàng
vẫn áp đúng.

`scope_level` nhận bốn giá trị: hệ thống, tổ chức, không gian làm việc, dự án.
Số bản ghi gán vai theo cấp: **hệ thống 4 · tổ chức 10 · không gian làm việc 0 ·
dự án 0**.

Bảng `roles` báo 3 hàng ở ảnh chụp 10/08/2026 trong khi danh mục vai dựng sẵn có
**13 vai**. Hai con số này **không mâu thuẫn**: 13 là số vai được định nghĩa
trong mô hình phân quyền (2 hệ thống / 5 tổ chức / 2 không gian làm việc / 4 dự
án), còn 3 là số hàng đã được gieo vào bảng tại thời điểm chụp. Nêu ra vì đây
đúng là kiểu chênh lệch làm người đọc nghĩ một trong hai số bị sai.

### 9.4.3 M3 — Kho dữ liệu mẫu *(nhóm trọng tâm)*

| Bảng | Khoá chính | Cột chính | RLS | Hàng |
|---|---|---|:--:|---:|
| `samples` | `id` | `tenant_id`, `class_uid`, `signer_id`, `auth_user_id`, `session_id`, `dialect`, đường dẫn tệp đặc trưng, `storage_url`, chỉ số chất lượng, `deleted_at` | ✔ | **3.860** |
| `classes` | `id` | `tenant_id`, `class_uid`, nhãn, ngôn ngữ, `dialect`, vùng miền, nhóm từ vựng, hồ sơ nhận dạng, số bàn tay yêu cầu | ✔ | 63 |
| `capture_sessions` | `id` | `tenant_id`, `class_uid`, `signer_id`, thời điểm bắt đầu/kết thúc, thiết bị | ✔ | 250 |
| `raw_uploads` | `id` | `tenant_id`, `class_uid`, `dialect`, tên tệp gốc, kích thước, trạng thái xử lý | ✔ | 0 |
| `signers` | `id` | `tenant_id`, `signer_id`, nhãn hiển thị, siêu dữ liệu | ✔ | 4 |
| `signer_aliases` | `id` | `tenant_id`, bí danh, `new_signer_id` | ✔ | 0 |

**Khoá ngoại ghép trong nhóm này** — cơ chế làm việc trỏ chéo tổ chức trở nên
**bất khả thi ở tầng ràng buộc**, không phải ở tầng kiểm tra của ứng dụng:

```
samples(tenant_id, class_uid)  → classes(tenant_id, class_uid)
samples(tenant_id, signer_id)  → signers(tenant_id, signer_id)
samples(tenant_id, dialect)    → dialects(tenant_id, dialect_id)
classes(tenant_id, dialect)    → dialects(tenant_id, dialect_id)
classes(tenant_id, recognition_profile) → recognition_profiles(tenant_id, profile_id)
classes(tenant_id, vocabulary_group)    → vocabulary_groups(tenant_id, group_id)
capture_sessions(tenant_id, class_uid)  → classes(tenant_id, class_uid)
capture_sessions(tenant_id, signer_id)  → signers(tenant_id, signer_id)
raw_uploads(tenant_id, class_uid)       → classes(tenant_id, class_uid)
```

**Hai cột quy kết, đừng lẫn:**

| Cột | Nghĩa | Độ phủ (10/08/2026) |
|---|---|---|
| `auth_user_id` | Tài khoản **thu** mẫu (người bấm nút) | 95,7 % — 3 giá trị phân biệt |
| `signer_id` | **Người ký** — chủ thể dữ liệu | **43,4 %** — 4 giá trị phân biệt |

**Chuỗi nguồn gốc mà nhóm này bảo toàn:**

```
Người ký → Phiên thu → Mẫu → Bản tải lên thô / Biểu diễn dẫn xuất → Phiên bản bộ dữ liệu
```

Mỗi mắt xích là một quan hệ **truy vấn được**, nên câu hỏi *"mẫu này từ đâu ra,
qua bước nào, do ai"* trả lời được bằng truy vấn chứ không bằng suy đoán. Nhưng
**mắt xích đầu chỉ tồn tại ở 43,4 % dữ liệu** — với phần còn lại, chuỗi đứt ở
đúng vị trí không dựng lại được.

*Luận văn **không tuyên bố** hiện thực đầy đủ mô hình dữ liệu W3C PROV; điều được
khẳng định hẹp hơn là mỗi mắt xích trên là một quan hệ truy vấn được.*

### 9.4.4 M4 — Danh mục & Registry

| Bảng | Khoá chính | Cột chính | RLS | Hàng |
|---|---|---|:--:|---:|
| `languages` | `code` | tên | — | 2 |
| `regions` | `id` | mã vùng, tên | — | — |
| `dialects` | (`tenant_id`,`dialect_id`) | nhãn, trạng thái, `merged_into` | ✔ | 9 |
| `dialect_aliases` | `id` | `tenant_id`, bí danh, `new_dialect_id` | ✔ | 0 |
| `recognition_profiles` | (`tenant_id`,`profile_id`) | nhãn, mô tả | ✔ | 6 |
| `vocabulary_groups` | (`tenant_id`,`group_id`) | nhãn | ✔ | 5 |
| `vocabulary_registry_meta` | `tenant_id` | phiên bản hiện hành, thời điểm cập nhật | ✔ | 1 |
| `registry_versions` | (`tenant_id`,`version`) | **ảnh chụp bất biến**, mã băm nội dung, thời điểm | ✔ | 89 |
| `community_dialects` | `dialect_id` | nhãn — mặt phẳng cộng đồng | — | 9 |
| `community_profiles` | `profile_id` | nhãn — mặt phẳng cộng đồng | — | 6 |
| `community_versions` | `version` | ảnh chụp danh mục cộng đồng | — | 1 |

**Ghi chú thiết kế.** Ba bảng `community_*` **không** bật chính sách bảo mật mức
hàng, **có chủ đích**: chúng là mặt phẳng đọc chung. Điều này an toàn **chỉ vì**
luật không-rơi-ngược được cưỡng chế ở tầng ứng dụng — dữ liệu chảy từ mặt phẳng
cộng đồng sang tổ chức đúng một lần, lúc khởi tạo, và không có đường ngược lại
lúc chạy.

`registry_versions` là bảng làm cho việc **ghim phiên bản** khả thi. Thiết kế
trước đó dùng một bộ đếm bị ghi đè và một tệp ảnh chụp bị ghi đè, khiến *"bộ dữ
liệu ghim phiên bản 2"* **không thực hiện được** — nội dung phiên bản 2 biến mất
ngay khi phiên bản 3 được ghi.

### 9.4.5 M5 — Huấn luyện & Mô hình

| Bảng | Khoá chính | Cột chính | RLS | Hàng |
|---|---|---|:--:|---:|
| `training_jobs` | `id` | `tenant_id`, phạm vi, tham số, trạng thái, **`registry_version`**, thời điểm, chủ sở hữu | ✔ | 90 |
| `training_job_classes` | (`job_id`,`class_uid`) | chỉ số lớp đã gán, số mẫu thực dùng | ✔ | 0 |
| `training_metrics` | `id` | `job_id`, chu kỳ, tên chỉ số, giá trị | — | 393 |

Khoá ngoại ghép: `training_jobs(tenant_id, registry_version) → registry_versions(tenant_id, version)`
— chính là **quan hệ ghim phiên bản**.

`training_job_classes` lưu **tập lớp thực sự tham gia sau khi qua ba cổng chặn**,
không phải tập lớp người dùng chọn. Phân biệt này cần để giải thích kết quả: nếu
chỉ lưu tập được chọn, một lần chạy loại bớt lớp sẽ **không để lại dấu vết**.

### 9.4.6 M6 — Dịch vụ tổ chức & Tích hợp

| Bảng | Khoá chính | Cột chính | RLS | Hàng |
|---|---|---|:--:|---:|
| `plans` | `id` | mã gói, hạn mức mẫu / lớp / thành viên / tính toán, giá | — | 4 |
| `tenant_subscriptions` | `id` | `tenant_id`, `plan_id`, kỳ hạn, trạng thái, ân hạn | ✔ | 1 |
| `tenant_usage_daily` | (`tenant_id`,`ngày`) | số mẫu, số phút tính toán, dung lượng | ✔ | 69 |
| `tenant_exports` | `id` | `tenant_id`, trạng thái, đường dẫn kết quả, hạn tải | ✔ | 0 |
| `tenant_purges` | `id` | `tenant_id`, người yêu cầu, thời điểm, xác nhận | — | 0 |
| `api_keys` | `id` | `tenant_id`, **mã băm khoá**, phạm vi, `last_used_at`, `revoked_at` | ✔ | 0 |
| `webhook_endpoints` | `id` | `tenant_id`, URL, bí mật ký, danh sách sự kiện, trạng thái | ✔ | 0 |
| `webhook_deliveries` | `id` | `endpoint_id`, sự kiện, mã trả về, số lần thử | ✔ | 0 |
| `support_tickets` | `id` | `tenant_id`, người tạo, chủ đề, trạng thái, mức ưu tiên | ✔ | — |
| `support_messages` | `id` | `ticket_id`, người gửi, nội dung, thời điểm | ✔ | — |
| `notifications` | `id` | người nhận, loại, nội dung, `read_at` | ✔ | — |

**Ghi chú thiết kế.** Giá trị **rỗng** ở cột hạn mức nghĩa là **không giới hạn**,
không phải "bằng không" — phân biệt này đã được ghim bằng kiểm thử, vì đọc nhầm sẽ
chặn toàn bộ hoạt động của các gói không giới hạn.

`tenant_usage_daily` là nguồn cho việc **tính tiền** ("đã từng dùng"). Con số dùng
để **chặn** ("đang dùng") đọc từ nguồn khác, **có chủ đích**.

`api_keys` lưu **mã băm**, nên khoá bị mất thì không khôi phục được, chỉ tạo mới.

### 9.4.7 M7 — Pháp lý, Kiểm toán & Nền tảng

| Bảng | Khoá chính | Cột chính | RLS | Hàng |
|---|---|---|:--:|---:|
| `legal_documents` | (`kind`,`version`) | tiêu đề, **thân văn bản**, mã băm nội dung, ngày hiệu lực, `requires_reconsent` | — | 4 |
| `legal_document_drafts` | `id` | `kind`, nội dung, trạng thái nháp, người soạn | — | 1 |
| `legal_document_events` | `id` | `kind`, `version`, loại sự kiện, người thực hiện, thời điểm | — | 5 |
| `user_consents` | `id` | `user_id`, (`kind`,`version`), thời điểm, xuất xứ, mã băm IP | — | 20 |
| `signer_consents` | `id` | `tenant_id`, `signer_id`, (`kind`,`version`), **mức đồng thuận**, `withdrawn_at` | ✔ | 0 |
| `audit_log` | `id` | `tenant_id`, chủ thể, hành động, đối tượng, `actor_label`, thời điểm | ✔ | 0 |
| `platform_settings` | `key` | giá trị, người sửa cuối | — | 0 |
| `sot_authorized_keys` | `public_key` | tên khoá, vân tay, thời điểm thêm, `revoked_at` | — | 0 |
| `google_sheets_sync_status` | `id` | bảng nguồn, bảng tính đích, số hàng, thời điểm | — | 1 |
| `event_outbox` | `id` | loại sự kiện, tải trọng, trạng thái gửi, số lần thử | ✔ | — |

**Ba điểm thiết kế đáng bảo vệ:**

1. **`legal_documents` bất biến sau khi công bố**, cưỡng chế bằng **trigger ở tầng
   cơ sở dữ liệu** chứ không bằng kiểm tra ở ứng dụng. Chấp thuận trỏ tới cặp
   (`kind`, `version`); nếu nội dung sửa được dưới chân nó, bằng chứng chấp thuận
   biến thành lời khẳng định suông.
2. **`user_consents` và `signer_consents` là hai bảng khác nhau**, không phải hai
   dòng của cùng một bảng. Vế thứ nhất là **tài khoản** chấp thuận điều khoản dịch
   vụ; vế thứ hai là **chủ thể dữ liệu** cho phép dùng dữ liệu của mình. **Chỉ vế
   thứ hai chi phối đường phát hành dữ liệu.**
3. **`audit_log.actor_label` là bằng chứng lịch sử, không cập nhật theo tên hiện
   tại.** Khi một tài khoản đổi tên, năm chỗ khác trong hệ thống được cập nhật
   theo — nhưng cột này thì **không**, có chủ đích: một bản ghi kiểm toán phải nói
   ra tên **tại thời điểm hành động xảy ra**.

---

## 9.5 Quan hệ then chốt giữa các đối tượng

| Quan hệ | Lực lượng | Ghi chú thiết kế |
|---|---|---|
| Tổ chức — Tài khoản | n : m, qua bảng gán vai | Một người thuộc nhiều tổ chức với vai khác nhau ở mỗi tổ chức |
| Tổ chức — Mẫu | 1 : n | Ranh giới cách ly; cưỡng chế bằng chính sách bảo mật mức hàng |
| Lớp — Mẫu | 1 : n, **khoá ghép** | Khoá ngoại mang cả định danh tổ chức, nên không trỏ chéo tổ chức được |
| Người ký — Mẫu | 1 : n, **khoá ghép** | Phủ 43,4 %; phần còn lại không quy kết được |
| Phiên thu — Mẫu | 1 : n | Một lượt ngồi trước camera sinh nhiều mẫu |
| Phương ngữ — Lớp | 1 : n, **khoá ghép** | Phương ngữ là **một phần định danh lớp**, không phải thuộc tính phụ |
| Phiên bản danh mục — Tác vụ huấn luyện | 1 : n | Ghim phiên bản: điều kiện để tái lập được thí nghiệm |
| Văn bản pháp lý — Chấp thuận | 1 : n, khoá tới cặp (loại, phiên bản) | Văn bản bất biến, nên chấp thuận trỏ tới nội dung xác định |
| Người ký — Đồng thuận | 1 : n | Đồng thuận có phiên bản; rút là rút thật |
| Gói cước — Đăng ký dịch vụ | 1 : n | Trạng thái thương mại tách khỏi trạng thái quản trị |

---

## 9.6 Ba miền dữ liệu theo quyền quản trị

Ngoài phân nhóm theo mô-đun, dữ liệu còn chia theo **quyền quản trị**. Ba miền này
**không lồng nhau**, và nhầm lẫn giữa chúng là nguồn của nhiều lỗi.

| | Miền của tổ chức | Miền dùng chung | Miền danh mục hệ thống |
|---|---|---|---|
| Ai sửa được | Tổ chức sở hữu | Không ai sửa trực tiếp; chỉ nhận qua công bố | Quản trị nền tảng |
| Ai đọc được | Chỉ tổ chức đó | Mọi tổ chức | Mọi tổ chức, chỉ đọc |
| Cưỡng chế bằng | Chính sách bảo mật mức hàng | Quy trình công bố tường minh | **Chữ ký số** |
| Ví dụ | mẫu, lớp, phiên thu | dữ liệu đã công bố cho cộng đồng | phương ngữ chuẩn, lược đồ |
| Đường vào | thu nhận | **công bố một chiều** | công bố có ký |
| Đường ra | xuất dữ liệu tổ chức | không có | không có |

> **Ranh giới quan trọng nhất: giá trị `default` KHÔNG phải là miền dùng chung.**
> Tổ chức mang định danh `default` là tổ chức **mồi** — nơi dữ liệu lịch sử của hệ
> thống tiền thân nằm lại. Nó là một tổ chức bình thường về mọi mặt cách ly. Coi
> nó là "dữ liệu chung" là mở một lỗ hổng **đúng bằng toàn bộ dữ liệu lịch sử**.

**Một cái bẫy cụ thể trong mã:** hàm chuẩn hoá định danh tổ chức **trả về
`default` khi nhận chuỗi rỗng**. Hệ quả: một hàm kiểm tra viết **sau** bước chuẩn
hoá sẽ không bao giờ thấy chuỗi rỗng, và trở thành **mã chết**. Nguyên tắc rút ra:
*kiểm tham số thô trước khi chuẩn hoá*.

---

## 9.7 Hai mặt phẳng lưu trữ

Ràng buộc RB-D2 để lại một cấu hình không lý tưởng và **phải nói thẳng**: nguồn sự
thật của kho mẫu là **một tệp CSV**, còn cơ sở dữ liệu quan hệ là **bản sao để
truy vấn**. Đây là di sản từ hệ thống tiền thân, không phải một thiết kế được chọn.

| Rủi ro | Cách xử lý |
|---|---|
| Hai mặt phẳng lệch nhau | Tác vụ đối soát định kỳ theo chiều CSV → cơ sở dữ liệu |
| Đường ghi tệp **không** chịu chính sách bảo mật mức hàng | Cách ly ở mặt phẳng tệp cưỡng chế bằng **cấu trúc thư mục theo tổ chức** cộng kiểm tra ở tầng ứng dụng — mức bảo đảm **thấp hơn** mặt phẳng CSDL |
| Kiểm thử ghi nhầm vào dữ liệu thật | Bộ kiểm thử từng ghi vào tệp nguồn sự thật **thật**; đã bổ sung chốt chặn |

**Đường dẫn nguồn sự thật:** `dataset/samples.csv` ở **gốc** thư mục dataset.
`dataset/samples/samples.csv` đã nghỉ hưu và **không còn tồn tại** — nhầm hai
đường dẫn này là lỗi hay lặp lại.

Cạnh mỗi tệp `.npz` có một sidecar JSON đủ để dựng lại hàng tương ứng.

**Phát biểu đúng mức, phải giữ nhất quán:** cách ly được **cưỡng chế ở tầng cơ sở
dữ liệu** cho mọi tài nguyên nằm trong cơ sở dữ liệu; với tài nguyên nằm trên hệ
tệp, cách ly dựa vào cấu trúc lưu trữ và kiểm tra ở tầng ứng dụng. Đây là lý do
phép đo cách ly được gọi là phép đo **xuyên kho**.

---

## 9.8 Độ phủ của cơ chế cách ly

> **CẬP NHẬT 18/08/2026 — số liệu dưới đây đã thay đổi.** Truy vấn lại CSDL đang
> chạy cho: **35** bảng mang `tenant_id` · **34** bật RLS · **34/34** FORCE ·
> **độ phủ 34/35 ≈ 97,1 %** · và **chỉ còn MỘT** bảng hở là `tenant_purges`. Bảng
> `tenants` **nay đã bật RLS**. Bảng số liệu cũ (ảnh chụp 10/08/2026) giữ nguyên ở
> dưới để đối chiếu; số liệu hiện hành và lập luận đầy đủ ở
> [DD_00_QUY_UOC_VA_MUC_LUC.md](DD_00_QUY_UOC_VA_MUC_LUC.md) §1.

*Bảng dưới đây là ảnh chụp **10/08/2026**, không phải số liệu hiện hành:*

| Chỉ số | Giá trị | Cách kiểm chứng |
|---|---|---|
| Bảng mang cột định danh tổ chức | 34 | Truy vấn danh mục cột |
| Bảng bật chính sách bảo mật mức hàng | 32 | Truy vấn cờ `relrowsecurity` |
| Bảng bật cờ cưỡng chế với chủ sở hữu bảng | **32 / 32 = 100 %** | Truy vấn cờ `relforcerowsecurity` |
| Số chính sách | 32 | Truy vấn danh mục chính sách |
| **Độ phủ** | **32 / 34 ≈ 94,1 %** | — |

**Hai bảng mang định danh tổ chức nhưng không bật chính sách** — nêu **đích danh**
kèm đánh giá rủi ro, thay vì để chúng thành một con số trừ đi:

| Bảng | Vì sao không bật | Rủi ro |
|---|---|---|
| `tenants` | Đây là **danh mục các tổ chức**. Truy vấn phân giải ngữ cảnh phải đọc bảng này **trước khi** ngữ cảnh tổ chức tồn tại — bật chính sách lên chính nó thì bước phân giải khớp 0 hàng và **không tổ chức nào vào được** | Thấp: chỉ chứa siêu dữ liệu tổ chức. Nhưng nó **liệt kê được tên mọi tổ chức**, nên mọi điểm cuối đọc nó phải tự lọc — tức mức bảo đảm thấp hơn |
| `tenant_purges` | Ghi nhận yêu cầu dọn sạch dữ liệu tổ chức; chỉ ghi/đọc qua đường quản trị nền tảng | Thấp, nhưng là khoảng trống thật: quản trị viên nền tảng đọc được toàn bộ lịch sử yêu cầu dọn của mọi tổ chức, và **không có tầng cưỡng chế nào đứng sau** |

Trường hợp `tenants` đáng chú ý về mặt lập luận: nó cho thấy **cơ chế cách ly
không thể tự bảo vệ chính cái bảng định nghĩa ra các đơn vị cách ly** — một giới
hạn có tính **cấu trúc**, không phải một sơ suất bỏ quên.

**Vì sao cờ cưỡng chế với chủ sở hữu bảng vẫn chưa đủ:** cơ sở dữ liệu miễn trừ
chính sách **vô điều kiện** cho vai siêu người dùng. Đó là lý do tầng thứ tư —
tách vai — tồn tại, và là lý do bộ kiểm thử phải kiểm rằng vai chạy của ứng dụng
**không** phải siêu người dùng và **không** có quyền vượt chính sách.

---

## 9.9 Ba chỗ cố ý để trống trong lược đồ

Ghi lại để người đọc không tưởng là thiếu sót:

| Chỗ trống | Vì sao cố ý |
|---|---|
| Không có bảng "trạng thái tài khoản" ba giá trị | Lược đồ có hai cột nhưng chỉ **một bậc tự do**: cột dấu thời gian là *thời điểm cờ boolean lật*, không phải trạng thái độc lập. Trạng thái "ngừng ghi, còn đọc" nằm ở **trục thương mại** (`tenants.billing_status`), là một trục khác |
| Không có bảng lưu video thô | Đường thu qua webcam **không** sinh video. Bảng `raw_uploads` chỉ phục vụ đường tải tệp |
| Không có bảng "mô hình" riêng | Mô hình được quản lý như hiện vật của tác vụ huấn luyện; tách thành thực thể riêng là việc của bước phát triển tiếp theo |

---

## 9.10 Ghi chú khi đưa vào quyển luận văn

**Số hàng ở §9.4 là ảnh chụp ngày 10/08/2026.** Nếu đưa vào quyển, phải chụp lại
ngay trước khi in và ghi ngày chụp. Ba con số đã thay đổi đáng kể so với ảnh chụp
này: `legal_documents`, `user_consents` và `audit_log`.

**Không dùng tệp `schema_erd.sql` để dựng sơ đồ trong draw.io.** Đã thử ngày
10/08/2026: công cụ dựng được bảng nhưng **không dựng cạnh nào** — nó coi mỗi dòng
khai báo khoá ngoại là một cột và hiện thành một hàng chữ trong hộp. Bản có đủ
quan hệ kèm lực lượng nằm ở `docs/02-data/db/voya_erd.drawio`.

**Quy ước ký hiệu bắt buộc cho các sơ đồ mức vật lý**, thống nhất cả bảy hình:

* Bảng **bật chính sách bảo mật mức hàng**: viền đậm + nhãn `[RLS]`
* **Khoá ngoại ghép** mang định danh tổ chức: cạnh vẽ **nét đôi**, ghi cặp cột
* **Khung nhìn** (`tenant_members`): viền **nét đứt**
* **Thực thể yếu**: góc bo, phụ thuộc tồn tại vào thực thể chủ
