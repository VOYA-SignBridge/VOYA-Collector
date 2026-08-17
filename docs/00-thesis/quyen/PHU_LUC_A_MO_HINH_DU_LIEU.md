# PHỤ LỤC A: MÔ HÌNH DỮ LIỆU ĐẦY ĐỦ

*Phụ lục này chứa mô hình dữ liệu mức khái niệm (CDM), mức vật lý (PDM) và danh
mục đầy đủ các bảng. Thân bài (Chương 3 §3) chỉ trình bày mô hình theo bảy nhóm
mô-đun; ai cần tra một bảng hay một cột cụ thể thì đọc ở đây.*

---

## 1. Giới thiệu

Lược đồ có **57 bảng nghiệp vụ** và **1 khung nhìn**, với **117 khoá ngoại —
trong đó 22 là khoá ghép mang định danh tổ chức**. Số liệu truy vấn trực tiếp cơ
sở dữ liệu đang chạy ngày **17/08/2026**.

*Cơ sở dữ liệu báo 58 bảng; bảng thứ 58 là `schema_migrations`, sổ ghi phiên bản
lược đồ, không thuộc mô hình nghiệp vụ nên không tính vào 57.*

Trình bày toàn bộ trong một sơ
đồ duy nhất là trình bày một thứ không đọc được, nên phụ lục này chia theo đúng
bảy nhóm mô-đun của Chương 3.

**Nguồn dữ liệu của phụ lục:** lược đồ trích tự động từ cơ sở dữ liệu đang chạy
(`docs/02-data/db/schema_erd.sql`) và sơ đồ quan hệ có đủ lực lượng
(`docs/02-data/db/voya_erd.drawio`).

> **Lưu ý khi đóng quyển.** Số hàng trong §4 là **ảnh chụp ngày 10/08/2026**. Nếu
> đưa vào quyển, phải chụp lại ngay trước khi in và ghi ngày chụp — số hàng thay
> đổi mỗi ngày, và một bảng số liệu không ghi ngày là một bảng không kiểm chứng
> được. Ba con số đã thay đổi đáng kể so với ảnh chụp này: `legal_documents`,
> `user_consents` và `audit_log`.

---

## 2. Mô hình mức khái niệm (CDM)

> ### ▣ HÌNH A-1 — Mô hình khái niệm tổng thể
> **Loại:** sơ đồ thực thể – quan hệ mức khái niệm (không có khoá ngoại, không có
> kiểu dữ liệu) · **Công cụ:** draw.io
> **Phải thể hiện:** các thực thể chính và quan hệ giữa chúng, ở mức nghiệp vụ:
> Tổ chức, Tài khoản, Vai, Người ký, Mẫu, Lớp từ vựng, Phiên thu, Phương ngữ,
> Phiên bản danh mục, Tác vụ huấn luyện, Gói cước, Văn bản pháp lý, Đồng thuận.
> **Lực lượng phải ghi rõ** trên mọi cạnh. Không vẽ bảng trung gian — quan hệ n:m
> để nguyên ở mức khái niệm.
> **Chú thích:** *Hình A-1: Mô hình dữ liệu mức khái niệm.*

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
| **Phiên bản danh mục** | Ảnh chụp bất biến của danh mục, để tái lập được |
| **Tác vụ huấn luyện** | Dữ liệu thành mô hình như thế nào |
| **Gói cước / Đăng ký dịch vụ** | Tổ chức được dùng tới hạn mức nào |
| **Văn bản pháp lý** | Điều khoản nào đang có hiệu lực |
| **Đồng thuận** | Người ký cho phép dùng dữ liệu tới mức nào |

**Ba quan hệ khái niệm quan trọng nhất**, và lý do chúng không được gộp:

1. **Tài khoản — Mẫu** và **Người ký — Mẫu** là **hai quan hệ khác nhau**. Tài
   khoản là người bấm nút; người ký là chủ thể dữ liệu. Gộp lại là đánh mất khả
   năng trả lời yêu cầu rút dữ liệu.
2. **Lớp — Phương ngữ** không phải quan hệ "thuộc tính": phương ngữ tham gia vào
   **định danh** của lớp. Hai lớp cùng nhãn khác phương ngữ là **hai lớp**.
3. **Tác vụ huấn luyện — Phiên bản danh mục** là quan hệ **ghim**, không phải
   quan hệ tham chiếu thông thường: nó trỏ tới một ảnh chụp bất biến, không trỏ
   tới trạng thái hiện tại.

---

## 3. Mô hình mức vật lý (PDM)

PDM chia thành bảy sơ đồ theo nhóm mô-đun. Mỗi sơ đồ vẽ đầy đủ cột, kiểu dữ liệu,
khoá chính, khoá ngoại và chỉ mục.

> ### ▣ HÌNH A-2 → A-8 — Mô hình vật lý theo bảy nhóm mô-đun
> **Loại:** sơ đồ quan hệ mức vật lý · **Nguồn dựng:** `docs/02-data/db/voya_erd.drawio`
> **Bảy hình:** A-2 nhóm M1 Danh tính & Truy cập · A-3 nhóm M2 Tổ chức & Phân
> quyền · A-4 nhóm M3 Kho dữ liệu mẫu · A-5 nhóm M4 Danh mục & Registry · A-6
> nhóm M5 Huấn luyện & Mô hình · A-7 nhóm M6 Dịch vụ tổ chức & Tích hợp · A-8
> nhóm M7 Pháp lý, Kiểm toán & Nền tảng.
> **Quy ước ký hiệu bắt buộc, thống nhất cả bảy hình:**
> * Bảng **bật chính sách bảo mật mức hàng**: viền đậm + nhãn `[RLS]`
> * **Khoá ngoại ghép mang định danh tổ chức**: cạnh vẽ nét đôi, ghi cặp cột
> * **Khung nhìn** (`tenant_members`): viền nét đứt
> * **Thực thể yếu**: góc bo, phụ thuộc tồn tại vào thực thể chủ
> **Chú thích mẫu:** *Hình A-4: Mô hình vật lý nhóm Kho dữ liệu mẫu.*

**Không dùng tệp `schema_erd.sql` để dựng sơ đồ trong draw.io.** Đã thử ngày
10/08/2026: công cụ dựng được bảng nhưng **không dựng cạnh nào** — nó coi mỗi
dòng khai báo khoá ngoại là một cột và hiện thành một hàng chữ trong hộp. Bản có
đủ quan hệ kèm lực lượng nằm ở tệp `.drawio`.

---

## 4. Danh mục đầy đủ các bảng dữ liệu

Ký hiệu cột **RLS**: ✔ bảng bật chính sách bảo mật mức hàng · — không bật.
Cột **Hàng**: ảnh chụp 10/08/2026, xem lưu ý ở §1.

### 4.1 Nhóm M1 — Danh tính & Truy cập

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
biết tổ chức. Đây là chỗ sinh ra cái bẫy "0 hàng bị đọc thành không có gì" nêu ở
Chương 3 §3.1.

Mọi token và mã một lần đều lưu ở **dạng băm**, không lưu giá trị gốc.

### 4.2 Nhóm M2 — Tổ chức & Phân quyền

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

**Ghi chú thiết kế.** `tenant_members` là **khung nhìn**, không phải bảng, từ bản
tái cấu trúc phân quyền. Hệ quả cụ thể: không tạo được chỉ mục trên nó, và không
dùng được mệnh đề xử lý xung đột khi ghi — mọi đường ghi phải nhắm vào bảng nền.
Khung nhìn dùng chế độ gọi theo quyền của người gọi, để chính sách bảo mật mức
hàng vẫn áp đúng.

`scope_level` nhận bốn giá trị: hệ thống, tổ chức, không gian làm việc, dự án.
Hai giá trị sau hiện có **0 bản ghi gán vai**.

### 4.3 Nhóm M3 — Kho dữ liệu mẫu

| Bảng | Khoá chính | Cột chính | RLS | Hàng |
|---|---|---|:--:|---:|
| `samples` | `id` | `tenant_id`, `class_uid`, `signer_id`, `auth_user_id`, `session_id`, `dialect`, đường dẫn tệp đặc trưng, `storage_url`, chỉ số chất lượng, `deleted_at` | ✔ | 3.860 |
| `classes` | `id` | `tenant_id`, `class_uid`, nhãn, ngôn ngữ, `dialect`, vùng miền, nhóm từ vựng, hồ sơ nhận dạng, số bàn tay yêu cầu | ✔ | 63 |
| `capture_sessions` | `id` | `tenant_id`, `class_uid`, `signer_id`, thời điểm bắt đầu/kết thúc, thiết bị | ✔ | 250 |
| `raw_uploads` | `id` | `tenant_id`, `class_uid`, `dialect`, tên tệp gốc, kích thước, trạng thái xử lý | ✔ | 0 |
| `signers` | `id` | `tenant_id`, `signer_id`, nhãn hiển thị, siêu dữ liệu | ✔ | 4 |
| `signer_aliases` | `id` | `tenant_id`, bí danh, `new_signer_id` | ✔ | 0 |

**Khoá ngoại ghép trong nhóm này** — đây là cơ chế làm việc trỏ chéo tổ chức trở
nên **bất khả thi ở tầng ràng buộc**:

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

**Hai cột quy kết, đừng lẫn:** `auth_user_id` là tài khoản thu mẫu; `signer_id` là
**người ký** — chủ thể dữ liệu. Độ phủ đo ngày 10/08/2026: `auth_user_id` 95,7 %
(3 giá trị phân biệt), `signer_id` **43,4 %** (4 giá trị phân biệt).

### 4.4 Nhóm M4 — Danh mục & Registry

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
hàng, có chủ đích: chúng là mặt phẳng đọc chung. Điều này an toàn **chỉ vì** luật
không-rơi-ngược được cưỡng chế ở tầng ứng dụng: dữ liệu chảy từ mặt phẳng cộng
đồng sang tổ chức đúng một lần, lúc khởi tạo, và không có đường ngược lại lúc
chạy.

`registry_versions` là bảng làm cho việc **ghim phiên bản** khả thi. Thiết kế
trước đó dùng một bộ đếm bị ghi đè và một tệp ảnh chụp bị ghi đè, khiến "bộ dữ
liệu ghim phiên bản 2" không thực hiện được — nội dung phiên bản 2 biến mất ngay
khi phiên bản 3 được ghi.

### 4.5 Nhóm M5 — Huấn luyện & Mô hình

| Bảng | Khoá chính | Cột chính | RLS | Hàng |
|---|---|---|:--:|---:|
| `training_jobs` | `id` | `tenant_id`, phạm vi, tham số, trạng thái, **`registry_version`**, thời điểm, chủ sở hữu | ✔ | 90 |
| `training_job_classes` | (`job_id`,`class_uid`) | chỉ số lớp đã gán, số mẫu thực dùng | ✔ | 0 |
| `training_metrics` | `id` | `job_id`, chu kỳ, tên chỉ số, giá trị | — | 393 |

Khoá ngoại ghép: `training_jobs(tenant_id, registry_version) → registry_versions(tenant_id, version)`
— chính là quan hệ ghim phiên bản.

`training_job_classes` lưu **tập lớp thực sự tham gia sau khi qua ba cổng chặn**,
không phải tập lớp người dùng chọn. Phân biệt này cần cho việc giải thích kết quả:
nếu chỉ lưu tập được chọn, một lần chạy loại bớt lớp sẽ không để lại dấu vết.

### 4.6 Nhóm M6 — Dịch vụ tổ chức & Tích hợp

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
không phải "bằng không" — một phân biệt đã được ghim bằng kiểm thử, vì đọc nhầm
sẽ chặn toàn bộ hoạt động của các gói không giới hạn.

`tenant_usage_daily` là nguồn cho việc **tính tiền** ("đã từng dùng"). Con số dùng
để **chặn** ("đang dùng") đọc từ nguồn khác, có chủ đích — xem Chương 1 §2.5.

`api_keys` lưu **mã băm**, nên khoá bị mất thì không khôi phục được, chỉ tạo mới.

### 4.7 Nhóm M7 — Pháp lý, Kiểm toán & Nền tảng

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

**Ghi chú thiết kế — ba điểm đáng bảo vệ:**

1. **`legal_documents` bất biến sau khi công bố**, cưỡng chế bằng **trigger ở tầng
   cơ sở dữ liệu** chứ không bằng kiểm tra ở ứng dụng. Chấp thuận trỏ tới cặp
   (`kind`, `version`); nếu nội dung sửa được dưới chân nó, bằng chứng chấp thuận
   biến thành lời khẳng định suông.
2. **`user_consents` và `signer_consents` là hai bảng khác nhau**, không phải hai
   dòng của cùng một bảng. Vế thứ nhất là tài khoản chấp thuận điều khoản dịch
   vụ; vế thứ hai là **chủ thể dữ liệu** cho phép dùng dữ liệu của mình. Chỉ vế
   thứ hai chi phối đường phát hành dữ liệu.
3. **`audit_log.actor_label` là bằng chứng lịch sử, không cập nhật theo tên hiện
   tại.** Khi một tài khoản đổi tên, năm chỗ khác trong hệ thống được cập nhật
   theo — nhưng cột này thì **không**, có chủ đích: một bản ghi kiểm toán phải nói
   ra tên **tại thời điểm hành động xảy ra**.

---

## 5. Độ phủ của cơ chế cách ly

| Chỉ số | Giá trị | Cách kiểm chứng |
|---|---|---|
| Bảng mang cột định danh tổ chức | 34 | Truy vấn danh mục cột |
| Bảng bật chính sách bảo mật mức hàng | 32 | Truy vấn cờ `relrowsecurity` |
| Bảng bật cờ cưỡng chế với chủ sở hữu bảng | **32 / 32 = 100 %** | Truy vấn cờ `relforcerowsecurity` |
| Số chính sách | 32 | Truy vấn danh mục chính sách |
| **Độ phủ** | **32 / 34 ≈ 94,1 %** | — |

**Hai bảng mang định danh tổ chức nhưng không bật chính sách** — nêu đích danh và
đánh giá rủi ro, thay vì để chúng thành một con số trừ đi:

| Bảng | Vì sao không bật | Rủi ro |
|---|---|---|
| `tenants` | Đây là **danh mục các tổ chức**. Truy vấn phân giải ngữ cảnh phải đọc bảng này **trước khi** ngữ cảnh tổ chức tồn tại — bật chính sách lên chính nó thì bước phân giải khớp 0 hàng và không tổ chức nào vào được. Cùng một lý do với bảng tài khoản ở §4.1 | Thấp: bảng chỉ chứa siêu dữ liệu tổ chức, không chứa dữ liệu người dùng. Nhưng nó **liệt kê được tên mọi tổ chức**, nên mọi điểm cuối đọc nó phải tự lọc — và đó là kiểm tra ở tầng ứng dụng, tức mức bảo đảm thấp hơn |
| `tenant_purges` | Bảng ghi nhận **yêu cầu dọn sạch dữ liệu tổ chức**, chỉ ghi và đọc qua đường quản trị nền tảng | Thấp, nhưng là một khoảng trống thật: một quản trị viên nền tảng đọc được toàn bộ lịch sử yêu cầu dọn của mọi tổ chức — điều này đúng với vai đó, song không có tầng cưỡng chế nào đứng sau |

Cả hai đều được ghi vào phần hạn chế của quyển (Kết luận §2.1). Trường hợp
`tenants` đáng chú ý về mặt lập luận: nó cho thấy **cơ chế cách ly không thể tự
bảo vệ chính cái bảng định nghĩa ra các đơn vị cách ly** — một giới hạn có tính
cấu trúc, không phải một sơ suất bỏ quên.

**Vì sao cờ cưỡng chế với chủ sở hữu bảng vẫn chưa đủ:** cơ sở dữ liệu miễn trừ
chính sách **vô điều kiện** cho vai siêu người dùng. Đó là lý do tầng thứ tư —
tách vai — tồn tại, và là lý do bộ kiểm thử phải kiểm rằng vai chạy của ứng dụng
**không** phải siêu người dùng và **không** có quyền vượt chính sách.

---

## 6. Ba chỗ cố ý để trống trong lược đồ

Ghi lại để người đọc không tưởng là thiếu sót:

| Chỗ trống | Vì sao cố ý |
|---|---|
| Không có bảng "trạng thái tài khoản" ba giá trị | Lược đồ có hai cột nhưng chỉ một bậc tự do: cột dấu thời gian là *thời điểm cờ boolean lật*, không phải trạng thái độc lập. Trạng thái "ngừng ghi, còn đọc" nằm ở **trục thương mại** (`tenants.billing_status`), là một trục khác |
| Không có bảng lưu video thô | Đường thu qua webcam **không** sinh video. Bảng `raw_uploads` chỉ phục vụ đường tải tệp |
| Không có bảng "mô hình" riêng | Mô hình được quản lý như hiện vật của tác vụ huấn luyện; tách thành thực thể riêng là việc của bước phát triển tiếp theo |
