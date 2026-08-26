# Phụ lục C.8 — Data Dictionary (lược đồ v8)

Sinh thẳng từ catalog của `signdb` (sản xuất) ngày 26/08/2026, lược đồ **v8**,
checksum `fb5b9b90c553`. **Không ràng buộc nào được gõ tay.**

| | |
|---|---:|
| bảng | 62 |
| cột | 660 |
| khoá ngoại | 131 |
| CHECK | 68 |
| đối tượng duy nhất (PK/UNIQUE/chỉ mục) | 108 |
| cột có DEFAULT | 220 |

## Ba điều phải đọc trước khi dùng bảng này

**Mô tả nghiệp vụ đang phủ 449/660 cột — nhóm A, C, D và E — bốn miền lõi.** Phần
còn lại trống, và đó là chủ ý. Cơ sở dữ liệu có **0**
`COMMENT ON COLUMN` và **0** `COMMENT ON TABLE`, nên catalog không có nguồn mô
tả nào. Suy mô tả từ tên cột là bịa: người đọc luận văn không phân biệt được
một dòng lấy từ hệ thống với một dòng đoán ra. Mô tả nghiệp vụ phải viết tay
cho các bảng quan trọng, và khi ấy nó là tri thức của tác giả chứ không phải
số liệu của hệ thống.

**Cột `Tham chiếu` ưu tiên khoá GHÉP.** Nhiều cặp bảng có CẢ khoá một cột (di
sản) lẫn khoá ghép `(tenant_id, …)`; cả hai đều liệt kê, ghép đứng trước, vì
ghép mới là thứ khiến việc trỏ sang tổ chức khác không biểu diễn được.

**Ràng buộc tách sang C.8.2.** 18/68 CHECK phủ NHIỀU cột — ép chúng vào một
dòng cột sẽ làm sai nghĩa. Và 22 bất biến nằm ở **chỉ mục duy nhất một phần**,
thứ `pg_constraint` không hề thấy.

---

# C.8.1 — Từ điển cột

## A. Tenant & Access Management

### `api_keys` — 12 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `key_id` | `uuid` | — | PK | — | — | Định danh khoá API. |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` | Tổ chức xác định phạm vi của khoá. |
| 3 | `name` | `text` | — | — | `''::text` | — | Tên khoá do người vận hành đặt. |
| 4 | `prefix` | `text` | — | — | — | — | Tiền tố công khai của khoá, dùng để nhận diện mà không lộ khoá. |
| 5 | `key_hash` | `text` | — | — | — | — | Băm của khoá. Bảng KHÔNG lưu khoá gốc. |
| 6 | `scopes` | `text` | — | — | `'read'::text` | — | Phạm vi thao tác khoá được phép thực hiện. **`CẦN DUYỆT`**<br><sub>Kiểu text với mặc định 'read'; cách phân tách nhiều phạm vi cần xác nhận</sub> |
| 7 | `created_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã tạo khoá. |
| 8 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo khoá. |
| 9 | `last_used_at` | `timestamp with time zone` | ✓ | — | — | — | Lần khoá được dùng gần nhất. |
| 10 | `expires_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm khoá hết hạn. |
| 11 | `revoked_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm thu hồi khoá.<br><sub>Hạn mức số khoá chỉ đếm khoá CHƯA thu hồi</sub> |
| 12 | `revoked_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã thu hồi khoá. |

### `memberships` — 14 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `membership_id` | `uuid` | — | PK | `gen_random_uuid()` | — | Định danh tư cách thành viên. |
| 2 | `user_id` | `uuid` | — | FK | — | `(parent_membership_id, user_id)` → `memberships(membership_id, user_id)`<br>`users.id` | Tài khoản giữ tư cách thành viên này. |
| 3 | `scope_level` | `text` | — | — | `'TENANT'::text` | — | Mức phạm vi: TENANT, WORKSPACE hoặc PROJECT.<br><sub>Quyết định hai cột dưới phải NULL hay NOT NULL — xem ck_memberships_shape</sub> |
| 4 | `tenant_id` | `text` | — | FK | — | `(tenant_id, workspace_id, project_id)` → `projects(tenant_id, workspace_id, project_id)`<br>`(tenant_id, workspace_id)` → `workspaces(tenant_id, workspace_id)`<br>`tenants.tenant_id`<br>`tenants.tenant_id` | Tổ chức xác định phạm vi của tư cách thành viên. |
| 5 | `workspace_id` | `uuid` | ✓ | FK | — | `(tenant_id, workspace_id, project_id)` → `projects(tenant_id, workspace_id, project_id)`<br>`(tenant_id, workspace_id)` → `workspaces(tenant_id, workspace_id)` | Workspace của tư cách thành viên. NULL khi scope_level = TENANT; NOT NULL với WORKSPACE và PROJECT.<br><sub>ck_memberships_shape ràng ba cột thành đúng ba hình dạng hợp lệ</sub> |
| 6 | `project_id` | `uuid` | ✓ | FK | — | `(tenant_id, workspace_id, project_id)` → `projects(tenant_id, workspace_id, project_id)` | Project của tư cách thành viên. NOT NULL chỉ khi scope_level = PROJECT.<br><sub>Khoá ngoại ghép BA cột (tenant, workspace, project) nên không trỏ được sang project của workspace hay tổ chức khác</sub> |
| 7 | `parent_membership_id` | `uuid` | ✓ | FK | — | `(parent_membership_id, user_id)` → `memberships(membership_id, user_id)` | Tư cách thành viên cấp trên trong cây phạm vi, của CÙNG một người.<br><sub>Khoá ngoại là (parent_membership_id, user_id) nên cây bị ràng phải cùng một tài khoản</sub> |
| 8 | `legacy_role` | `text` | ✓ | — | — | — | Vai trò tương thích cũ, chỉ dùng được ở membership cấp tenant. `LEGACY`<br><sub>CHECK giới hạn còn admin|editor và chỉ cho phép khi scope_level = TENANT</sub> |
| 9 | `status` | `text` | — | — | `'ACTIVE'::text` | — | Trạng thái: ACTIVE, INVITED, SUSPENDED hoặc REMOVED. |
| 10 | `joined_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm gia nhập. |
| 11 | `suspended_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm bị tạm đình chỉ. |
| 12 | `left_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm rời đi. CHECK buộc cột này có giá trị KHI VÀ CHỈ KHI status = REMOVED. |
| 13 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo bản ghi. |
| 14 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm cập nhật gần nhất. |

### `permissions` — 9 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `permission_code` | `text` | — | PK | — | — | Mã quyền, dạng `miền.hành_động`.<br><sub>CHECK ràng đúng hình dạng ấy bằng biểu thức chính quy</sub> |
| 2 | `description` | `text` | — | — | `''::text` | — | Mô tả quyền cho người vận hành. |
| 3 | `applicable_scope` | `text` | — | — | — | — | Tầng áp dụng: SYSTEM, TENANT, WORKSPACE hoặc PROJECT. |
| 4 | `risk_level` | `text` | — | — | `'NORMAL'::text` | — | Mức rủi ro: NORMAL, SENSITIVE hoặc CRITICAL. |
| 5 | `requires_passcode` | `boolean` | — | — | `false` | — | Quyền này đòi xác nhận lại bằng mật mã trước khi dùng.<br><sub>Cơ chế sudo mode</sub> |
| 6 | `is_api_assignable` | `boolean` | — | — | `false` | — | Quyền có gán được cho khoá API hay không.<br><sub>CHECK cấm quyền phạm vi SYSTEM được gán cho khoá API</sub> |
| 7 | `is_active` | `boolean` | — | — | `true` | — | Quyền còn hiệu lực hay đã nghỉ hưu. |
| 8 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm khai báo quyền. |
| 9 | `is_custom_role_allowed` | `boolean` | — | — | `true` | — | Quyền có được đưa vào vai trò tuỳ chỉnh của tổ chức hay không.<br><sub>CHECK cấm quyền phạm vi SYSTEM lọt vào vai tuỳ chỉnh</sub> |

### `project_allocations` — 7 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `tenant_id` | `text` | — | PK FK | — | `(tenant_id, project_id)` → `projects(tenant_id, project_id)`<br>`tenants.tenant_id`<br>`tenants.tenant_id` | Tổ chức xác định phạm vi của khoản cấp phát.<br><sub>Cột này đang chịu HAI khoá ngoại trùng nhau với hành vi xoá mâu thuẫn (RESTRICT và CASCADE) — xem docs/10-issues/KNOWN_ISSUES.md</sub> |
| 2 | `project_id` | `uuid` | — | PK FK | — | `(tenant_id, project_id)` → `projects(tenant_id, project_id)` | Project được cấp phát. |
| 3 | `metric` | `text` | — | PK | — | — | Chỉ tiêu được chia: `samples`, `storage_mb` hoặc `training_jobs_per_month`.<br><sub>Ánh xạ sang cột gói qua workspace_admin.ALLOCATABLE_METRICS. CẢNH BÁO: từ v8 chỉ `storage_mb` còn được cưỡng chế ở cấp tổ chức; hai chỉ tiêu kia chia một ngân sách nền tảng không còn kiểm</sub> |
| 4 | `allocated` | `bigint` | ✓ | — | — | — | Phần chỉ tiêu dành cho project này. NULL nghĩa là KHÔNG GIỚI HẠN, không phải chưa điền.<br><sub>Tổng phần cấp cho các project không được vượt trần của gói; CHECK cấm giá trị âm</sub> |
| 5 | `note` | `text` | — | — | `''::text` | — | Ghi chú của người vận hành về khoản cấp phát. |
| 6 | `updated_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản chỉnh khoản cấp phát gần nhất. |
| 7 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm chỉnh gần nhất. |

### `projects` — 10 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `project_id` | `uuid` | — | PK | `gen_random_uuid()` | — | Định danh project. |
| 2 | `tenant_id` | `text` | — | FK | — | `(tenant_id, workspace_id)` → `workspaces(tenant_id, workspace_id)`<br>`tenants.tenant_id` | Tổ chức chứa project này. |
| 3 | `workspace_id` | `uuid` | — | FK | — | `(tenant_id, workspace_id)` → `workspaces(tenant_id, workspace_id)` | Workspace chứa project này.<br><sub>Khoá ngoại ghép (tenant_id, workspace_id) nên project không nằm được trong workspace của tổ chức khác</sub> |
| 4 | `name` | `text` | — | — | — | — | Tên project, duy nhất trong phạm vi workspace.<br><sub>Chỉ mục duy nhất MỘT PHẦN: chỉ áp cho hàng chưa xoá mềm</sub> |
| 5 | `description` | `text` | — | — | `''::text` | — | Mô tả project. |
| 6 | `status` | `text` | — | — | `'ACTIVE'::text` | — | Trạng thái project. |
| 7 | `is_default` | `boolean` | — | — | `false` | — | Project mặc định của workspace.<br><sub>Chỉ mục duy nhất một phần bảo đảm mỗi workspace chỉ có một project mặc định ĐANG HOẠT ĐỘNG</sub> |
| 8 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo. |
| 9 | `archived_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm lưu trữ. |
| 10 | `deleted_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm xoá mềm. |

### `role_assignments` — 9 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `assignment_id` | `uuid` | — | PK | `gen_random_uuid()` | — | Định danh lượt gán vai. |
| 2 | `user_id` | `uuid` | — | FK | — | `(membership_id, user_id)` → `memberships(membership_id, user_id)`<br>`users.id` | Tài khoản NHẬN lượt gán vai — chủ thể của quyền.<br><sub>NOT NULL, ON DELETE CASCADE: xoá người thì xoá luôn phép gán</sub> |
| 3 | `role_id` | `uuid` | — | FK | — | `roles.role_id` | Vai trò được gán. |
| 4 | `membership_id` | `uuid` | ✓ | FK | — | `(membership_id, user_id)` → `memberships(membership_id, user_id)` | Tư cách thành viên mà lượt gán này gắn vào.<br><sub>Khoá ngoại ghép (membership_id, user_id) bảo đảm vai được gán cho đúng người của membership. NULL với phép gán cấp SYSTEM</sub> |
| 5 | `assigned_by_user_id` | `uuid` | — | FK | — | `users.id` | Tài khoản THỰC HIỆN việc cấp vai — tác nhân.<br><sub>NOT NULL, ON DELETE RESTRICT: hệ thống TỪ CHỐI xoá người từng cấp vai, tức coi dấu vết uỷ quyền là bằng chứng phải giữ</sub> |
| 6 | `assigned_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm cấp vai. |
| 7 | `revoked_by_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản THỰC HIỆN việc thu hồi vai — tác nhân thu hồi.<br><sub>NULL cho tới khi vai bị thu hồi</sub> |
| 8 | `revoked_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm thu hồi vai. |
| 9 | `revoke_reason` | `text` | ✓ | — | — | — | Lý do thu hồi. |

### `role_permissions` — 3 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `role_id` | `uuid` | — | PK FK | — | `roles.role_id` | Vai trò được cấp quyền. |
| 2 | `permission_code` | `text` | — | PK FK | — | `permissions.permission_code` | Quyền được cấp cho vai trò. |
| 3 | `granted_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm gắn quyền vào vai trò. |

### `roles` — 12 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `role_id` | `uuid` | — | PK | `gen_random_uuid()` | — | Định danh vai trò. |
| 2 | `role_code` | `character varying(50)` | — | — | — | — | Mã vai trò ổn định, dùng để tra cứu trong mã nguồn. |
| 3 | `description` | `text` | ✓ | — | `''::text` | — | Mô tả vai trò cho người vận hành. |
| 4 | `tenant_id` | `text` | ✓ | FK | — | `tenants.tenant_id` | Tổ chức sở hữu vai trò TUỲ CHỈNH. NULL với vai trò dựng sẵn của nền tảng.<br><sub>ck_role_ownership buộc: NULL khi và chỉ khi is_builtin; vai tuỳ chỉnh phải có tenant và không được ở phạm vi SYSTEM</sub> |
| 5 | `scope_level` | `text` | ✓ | — | — | — | Phạm vi áp dụng: SYSTEM, TENANT, WORKSPACE hoặc PROJECT.<br><sub>Phạm vi SYSTEM chỉ thuộc về nền tảng (tenant_id NULL)</sub> |
| 6 | `is_builtin` | `boolean` | — | — | `false` | — | Vai trò do nền tảng dựng sẵn hay do tổ chức tự tạo.<br><sub>Quyết định tenant_id phải NULL hay NOT NULL</sub> |
| 7 | `is_active` | `boolean` | — | — | `true` | — | Vai trò còn dùng được hay đã nghỉ hưu.<br><sub>Vai rác được nhận nuôi bằng cách tắt cờ này, không xoá</sub> |
| 8 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo vai trò. |
| 9 | `role_name` | `text` | ✓ | — | — | — | Tên vai trò hiển thị. **`CẦN DUYỆT`**<br><sub>Tồn tại song song với role_code sau một lượt di trú; quan hệ giữa hai cột cần xác nhận</sub> |
| 10 | `tenant_type_constraint` | `text` | ✓ | — | — | — | Giới hạn vai trò chỉ áp cho một loại tổ chức (COMMUNITY hoặc ORGANIZATION).<br><sub>NULL nghĩa là không giới hạn theo loại tổ chức</sub> |
| 11 | `created_by_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã tạo vai trò tuỳ chỉnh. |
| 12 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm cập nhật gần nhất. |

### `tenant_invitations` — 11 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `invitation_id` | `uuid` | — | PK | — | — | Định danh lời mời. |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` | Tổ chức phát lời mời. |
| 3 | `email` | `text` | — | — | — | — | Địa chỉ thư người được mời; chuẩn hoá lúc ghi. |
| 4 | `role` | `text` | ✓ | — | — | — | Vai trò dự kiến khi người được mời gia nhập. |
| 5 | `token_hash` | `text` | — | — | — | — | Băm của mã mời. Bảng KHÔNG lưu mã gốc.<br><sub>Nên một bản sao lưu cơ sở dữ liệu không cho phép ai nhận lời mời hộ</sub> |
| 6 | `invited_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã phát lời mời. |
| 7 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm phát lời mời. |
| 8 | `expires_at` | `timestamp with time zone` | — | — | — | — | Thời điểm lời mời hết hạn. |
| 9 | `accepted_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm lời mời được nhận. |
| 10 | `accepted_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã nhận lời mời. |
| 11 | `revoked_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm thu hồi lời mời.<br><sub>Mời lại cùng một địa chỉ sẽ thu hồi lời mời đang mở thay vì tạo thêm</sub> |

### `tenants` — 20 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `tenant_id` | `text` | — | PK | — | — | Định danh tổ chức; là giá trị mọi chính sách cách ly tenant so khớp. |
| 2 | `display_name` | `text` | ✓ | — | — | — | Tên tổ chức hiển thị cho người dùng. |
| 3 | `slug` | `text` | ✓ | — | — | — | Dạng rút gọn của tên tổ chức dùng trong đường dẫn. **`CẦN DUYỆT`**<br><sub>Chưa xác nhận nơi tiêu thụ</sub> |
| 4 | `is_active` | `boolean` | — | — | `true` | — | Tổ chức còn hoạt động hay không. |
| 5 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo tổ chức. |
| 6 | `deleted_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm xoá mềm tổ chức. |
| 7 | `cloned_from_community_version` | `bigint` | ✓ | FK | — | `community_versions.version` | Phiên bản danh mục Community mà tổ chức được nhân bản từ đó lúc tạo.<br><sub>Kế thừa xảy ra lúc TẠO, không phải một đường vọng lại lúc chạy</sub> |
| 8 | `cloned_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm nhân bản danh mục. |
| 9 | `plan_code` | `text` | — | FK | `'free'::text` | `plans.plan_code` | Gói dịch vụ hiện hành; là nguồn ĐỌC của mọi phép cưỡng chế hạn mức.<br><sub>Lịch sử đổi gói nằm ở tenant_subscriptions</sub> |
| 10 | `billing_status` | `text` | — | — | `'active'::text` | — | Trạng thái thanh toán; quyết định tổ chức còn ghi được dữ liệu hay không. |
| 11 | `trial_ends_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm hết hạn dùng thử. |
| 12 | `current_period_start` | `timestamp with time zone` | ✓ | — | — | — | Đầu kỳ hạn hiện tại của đăng ký. |
| 13 | `current_period_end` | `timestamp with time zone` | ✓ | — | — | — | Cuối kỳ hạn hiện tại; mốc để nhắc hạn và mở kỳ mới. |
| 14 | `is_self_serve` | `boolean` | — | — | `false` | — | Tổ chức tự đăng ký hay do quản trị viên nền tảng tạo. |
| 15 | `owner_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản được chỉ định làm chủ sở hữu tổ chức; có thể NULL.<br><sub>KHÁC chiều với users.tenant_id — hai quan hệ riêng, không phải nghịch đảo của nhau</sub> |
| 16 | `suspended_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm tạm ngưng dịch vụ. |
| 17 | `suspended_reason` | `text` | ✓ | — | — | — | Lý do tạm ngưng. |
| 18 | `tenant_type` | `text` | — | — | `'ORGANIZATION'::text` | — | Loại tổ chức: COMMUNITY hay ORGANIZATION.<br><sub>Community là một tenant DỰ TRỮ, không phải một mặt phẳng riêng</sub> |
| 19 | `is_system_reserved` | `boolean` | — | — | `false` | — | Tổ chức do nền tảng giữ chỗ, không được xoá. |
| 21 | `billing_exempt` | `boolean` | — | — | `false` | — | Miễn trừ hạn mức thương mại.<br><sub>Nghĩa là KHÔNG dùng trần để chặn — mức dùng vẫn được đo</sub> |

### `users` — 16 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `id` | `uuid` | — | PK | — | — | Định danh tài khoản. |
| 2 | `username` | `text` | — | — | — | — | Tên đăng nhập.<br><sub>Được chép sang nhiều bảng dữ liệu làm dấu vết lịch sử</sub> |
| 3 | `email` | `text` | — | — | — | — | Địa chỉ thư điện tử; cũng dùng được để đăng nhập. |
| 4 | `password_hash` | `text` | — | — | — | — | Băm mật khẩu. |
| 5 | `is_active` | `boolean` | — | — | `true` | — | Tài khoản còn hoạt động hay không. |
| 6 | `is_admin` | `boolean` | — | — | `false` | — | Quyền quản trị NỀN TẢNG, không phải quyền trong một tổ chức.<br><sub>Khác hẳn vai trong tenant; hai thẩm quyền được kiểm riêng</sub> |
| 7 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo tài khoản. |
| 8 | `role_id` | `uuid` | ✓ | FK | — | `roles.role_id` | Tham chiếu vai trò kiểu cũ. KHÔNG phải đường phân quyền hiện hành. `LEGACY`<br><sub>Đo: 5/13 tài khoản còn giá trị, trong khi RBAC thật chạy qua 37 membership + 27 role assignment</sub> |
| 9 | `phone_number` | `character varying(20)` | ✓ | — | — | — | Số điện thoại dùng cho mã xác minh qua SMS. |
| 10 | `updated_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm cập nhật gần nhất. |
| 11 | `deleted_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm xoá mềm tài khoản. |
| 12 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` | Tổ chức dùng làm ngữ cảnh mặc định/dự phòng của tài khoản; quan hệ thành viên và quyền truy cập CÓ THẨM QUYỀN được biểu diễn qua Membership.<br><sub>Cố ý không mô tả là 'tổ chức mà người dùng thuộc về' — nói vậy sẽ khiến cột này và Membership trông ngang hàng</sub> |
| 13 | `email_verified_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm xác minh địa chỉ thư.<br><sub>Thư hệ thống chỉ gửi tới địa chỉ ĐÃ xác minh</sub> |
| 14 | `phone_verified_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm xác minh số điện thoại. |
| 15 | `sessions_invalid_before` | `timestamp with time zone` | ✓ | — | — | — | Mốc thu hồi phiên: token phát trước thời điểm này không còn hiệu lực.<br><sub>Là mức thu hồi rộng nhất trong ba mức</sub> |
| 16 | `active_tenant_id` | `text` | ✓ | — | — | — | Tổ chức người dùng đang CHỌN làm ngữ cảnh làm việc.<br><sub>Khác `tenant_id`: cái kia là mặc định/dự phòng, cái này là lựa chọn hiện tại</sub> |

### `workspaces` — 9 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `workspace_id` | `uuid` | — | PK | `gen_random_uuid()` | — | Định danh workspace. |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` | Tổ chức chứa workspace này. |
| 3 | `name` | `text` | — | — | — | — | Tên workspace, duy nhất trong phạm vi tổ chức. |
| 4 | `description` | `text` | — | — | `''::text` | — | Mô tả workspace. |
| 5 | `status` | `text` | — | — | `'ACTIVE'::text` | — | Trạng thái workspace. |
| 6 | `is_default` | `boolean` | — | — | `false` | — | Workspace mặc định của tổ chức. |
| 7 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo. |
| 8 | `archived_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm lưu trữ. |
| 9 | `deleted_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm xoá mềm. |

## B. Authentication & User Security

### `password_reset_tokens` — 5 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `token_hash` | `text` | — | PK | — | — |  |
| 2 | `user_id` | `uuid` | — | FK | — | `users.id` |  |
| 3 | `expires_at` | `timestamp with time zone` | — | — | — | — |  |
| 4 | `used_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 5 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |

### `refresh_tokens` — 8 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `token_hash` | `text` | — | PK | — | — |  |
| 2 | `user_id` | `uuid` | — | FK | — | `users.id` |  |
| 3 | `expires_at` | `timestamp with time zone` | — | — | — | — |  |
| 4 | `revoked_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 5 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 6 | `family_id` | `uuid` | ✓ | — | — | — |  |
| 7 | `replaced_by` | `text` | ✓ | — | — | — |  |
| 8 | `reuse_detected_at` | `timestamp with time zone` | ✓ | — | — | — |  |

### `user_action_passcodes` — 8 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `user_id` | `uuid` | — | PK FK | — | `users.id` |  |
| 2 | `passcode_hash` | `text` | — | — | — | — |  |
| 3 | `status` | `text` | — | — | `'ACTIVE'::text` | — |  |
| 4 | `failed_count` | `smallint` | — | — | `0` | — |  |
| 5 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 6 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 7 | `locked_until` | `timestamp with time zone` | ✓ | — | — | — |  |
| 8 | `revoked_at` | `timestamp with time zone` | ✓ | — | — | — |  |

### `user_recovery_codes` — 4 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `code_hash` | `text` | — | PK | — | — |  |
| 2 | `user_id` | `uuid` | — | FK | — | `users.id` |  |
| 3 | `used_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 4 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |

### `user_totp` — 5 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `user_id` | `uuid` | — | PK FK | — | `users.id` |  |
| 2 | `secret_enc` | `text` | — | — | — | — |  |
| 3 | `confirmed_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 4 | `last_used_step` | `bigint` | ✓ | — | — | — |  |
| 5 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |

### `verification_codes` — 11 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `challenge_id` | `uuid` | — | PK | — | — |  |
| 2 | `user_id` | `uuid` | ✓ | FK | — | `users.id` |  |
| 3 | `purpose` | `text` | — | — | — | — |  |
| 4 | `channel` | `text` | — | — | — | — |  |
| 5 | `destination` | `text` | — | — | — | — |  |
| 6 | `code_hash` | `text` | — | — | — | — |  |
| 7 | `attempts` | `integer` | — | — | `0` | — |  |
| 8 | `max_attempts` | `integer` | — | — | `5` | — |  |
| 9 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 10 | `expires_at` | `timestamp with time zone` | — | — | — | — |  |
| 11 | `consumed_at` | `timestamp with time zone` | ✓ | — | — | — |  |

## C. VSL Vocabulary & Registry

### `classes` — 23 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `class_uid` | `text` | — | PK | — | — | Định danh lớp ký hiệu. |
| 2 | `class_idx` | `integer` | ✓ | — | — | — | Chỉ số lớp dùng khi huấn luyện.<br><sub>Chỉ mục duy nhất một phần: chỉ áp cho lớp chưa xoá mềm và có chỉ số</sub> |
| 3 | `slug` | `text` | ✓ | — | — | — | Dạng rút gọn của nhãn, dùng đặt tên thư mục và tệp. |
| 4 | `label_original` | `text` | ✓ | — | — | — | Nhãn gốc do người dùng nhập. |
| 5 | `language` | `text` | ✓ | FK | — | `languages.code` | Chiều phân loại: ngôn ngữ ký hiệu của lớp. |
| 6 | `dialect` | `text` | ✓ | FK | — | `(tenant_id, dialect)` → `dialects(tenant_id, dialect_id)` | Chiều phân loại: phương ngữ của lớp.<br><sub>Khoá ngoại ghép `(tenant_id, dialect)`; cũng là tên thư mục lưu mẫu</sub> |
| 7 | `is_common_global` | `boolean` | ✓ | — | — | — | Lớp thuộc vốn từ phổ thông của mọi ngôn ngữ. **`CẦN DUYỆT`**<br><sub>Quan hệ với `vocabulary_scope` cần xác nhận</sub> |
| 8 | `is_common_language` | `boolean` | ✓ | — | — | — | Lớp thuộc vốn từ phổ thông trong một ngôn ngữ. **`CẦN DUYỆT`**<br><sub>Cùng câu hỏi như `is_common_global`</sub> |
| 9 | `folder_name` | `text` | ✓ | — | — | — | Tên thư mục vật lý chứa mẫu của lớp. |
| 10 | `created_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm đăng ký lớp. |
| 11 | `migrated_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm lớp được chuyển sang cấu trúc phân cấp hiện tại. |
| 12 | `deleted_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm xoá mềm lớp. |
| 13 | `description` | `text` | ✓ | — | `''::text` | — | Mô tả lớp. |
| 14 | `is_active` | `boolean` | ✓ | — | `true` | — | Lớp còn được thu thêm mẫu hay không. |
| 15 | `hands_required` | `integer` | ✓ | — | — | — | Số bàn tay lớp này cần: 1 hoặc 2.<br><sub>Điền theo nguyên tắc lần-thu-đầu-thắng và dùng để chấm chất lượng mẫu</sub> |
| 16 | `semantic_label` | `text` | ✓ | — | — | — | Nhãn ngữ nghĩa chuẩn hoá của lớp. |
| 17 | `vocabulary_scope` | `text` | ✓ | — | — | — | Phạm vi vốn từ mà lớp thuộc về.<br><sub>Đo trên sản xuất hiện chỉ có `profile_specific`</sub> |
| 18 | `recognition_profile` | `text` | ✓ | FK | — | `(tenant_id, recognition_profile)` → `recognition_profiles(tenant_id, profile_id)` | Chiều phân loại: hồ sơ nhận dạng của lớp.<br><sub>Khoá ngoại ghép `(tenant_id, recognition_profile)`</sub> |
| 19 | `vocabulary_group` | `text` | ✓ | FK | — | `(tenant_id, vocabulary_group)` → `vocabulary_groups(tenant_id, group_id)` | Chiều phân loại: nhóm từ vựng của lớp.<br><sub>Khoá ngoại ghép `(tenant_id, vocabulary_group)`</sub> |
| 20 | `collection_campaign` | `text` | ✓ | — | — | — | Đợt thu thập mà lớp được tạo ra trong đó. **`CẦN DUYỆT`** |
| 21 | `motion_type` | `text` | ✓ | — | — | — | Lớp là ký hiệu tĩnh hay động.<br><sub>Đo được: `static` và `dynamic`</sub> |
| 22 | `tenant_id` | `text` | — | FK | `'default'::text` | `(tenant_id, dialect)` → `dialects(tenant_id, dialect_id)`<br>`(tenant_id, recognition_profile)` → `recognition_profiles(tenant_id, profile_id)`<br>`(tenant_id, vocabulary_group)` → `vocabulary_groups(tenant_id, group_id)`<br>`tenants.tenant_id` | Tổ chức xác định phạm vi của lớp. |
| 23 | `region` | `text` | — | FK | `'unclassified'::text` | `regions.code` | Chiều phân loại: vùng miền của lớp — LÀ MỘT PHẦN CỦA ĐỊNH DANH LỚP.<br><sub>Chỉ mục duy nhất gồm NĂM cột (tenant, slug, language, dialect, region), nên hai lớp cùng nhãn khác vùng là hai lớp khác nhau. Mặc định `unclassified`</sub> |

### `community_dialects` — 9 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `dialect_id` | `text` | — | PK | — | — | Định danh phương ngữ trong KHUÔN nền tảng.<br><sub>Khuôn là thứ mọi tổ chức MỚI được nhân bản từ đó. Đây là cấu hình cấp nền tảng, KHÔNG phải dữ liệu của tenant Community dự trữ</sub> |
| 2 | `display_name` | `text` | — | — | — | — | Tên phương ngữ trong khuôn. |
| 3 | `language` | `text` | — | — | `'vn'::text` | — | Ngôn ngữ ký hiệu của mục trong khuôn. |
| 4 | `is_alphabet` | `boolean` | — | — | `false` | — | Mục này là bộ chữ cái ngón tay. |
| 5 | `display_order` | `integer` | — | — | `0` | — | Thứ tự hiển thị trong khuôn. |
| 6 | `is_active` | `boolean` | — | — | `true` | — | Mục có được nhân bản ở trạng thái đang dùng hay không. |
| 7 | `note` | `text` | ✓ | — | — | — | Ghi chú của quản trị viên hệ thống. |
| 8 | `updated_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản sửa khuôn gần nhất. |
| 9 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm sửa khuôn gần nhất. |

### `community_profiles` — 8 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `profile_id` | `text` | — | PK | — | — | Định danh hồ sơ nhận dạng trong KHUÔN nền tảng. |
| 2 | `display_name` | `text` | — | — | — | — | Tên hồ sơ trong khuôn. |
| 3 | `is_trainable` | `boolean` | — | — | `true` | — | Cờ được nhân bản sang recognition_profiles của tổ chức mới. **`CẦN DUYỆT`**<br><sub>Cùng câu hỏi như recognition_profiles.is_trainable: không cổng huấn luyện nào đọc</sub> |
| 4 | `display_order` | `integer` | — | — | `0` | — | Thứ tự hiển thị trong khuôn. |
| 5 | `is_active` | `boolean` | — | — | `true` | — | Hồ sơ có được nhân bản hay không. |
| 6 | `note` | `text` | ✓ | — | — | — | Ghi chú của quản trị viên hệ thống. |
| 7 | `updated_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản sửa khuôn gần nhất. |
| 8 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm sửa khuôn gần nhất. |

### `community_versions` — 6 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `version` | `bigint` | — | PK | — | — | Số hiệu phiên bản của KHUÔN nền tảng.<br><sub>KHÁC `registry_versions.version` (phiên bản registry của một tổ chức) và khác `vocabulary_registry_meta.version` (con trỏ). Ba khái niệm, cùng một chữ</sub> |
| 2 | `content_hash` | `text` | — | — | — | — | Băm nội dung khuôn tại thời điểm đóng băng.<br><sub>Công bố là luỹ đẳng theo NỘI DUNG: khuôn không đổi thì trả về bản đã có chứ không đúc bản trùng</sub> |
| 3 | `snapshot` | `jsonb` | — | — | — | — | Bản chụp bất biến của khuôn tại thời điểm công bố. |
| 4 | `note` | `text` | ✓ | — | — | — | Ghi chú kèm lượt công bố khuôn. |
| 5 | `created_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã công bố khuôn. |
| 6 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm công bố khuôn.<br><sub>`tenants.cloned_from_community_version` trỏ vào đây để ghi lại tổ chức được tạo từ bản khuôn nào</sub> |

### `dialect_aliases` — 5 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `tenant_id` | `text` | — | PK FK | `'default'::text` | `(tenant_id, new_dialect_id)` → `dialects(tenant_id, dialect_id)`<br>`tenants.tenant_id` | Tổ chức xác định phạm vi của bản ghi gộp. |
| 2 | `old_dialect_id` | `text` | — | PK | — | — | Định danh cũ, nay chuyển hướng sang mục khác.<br><sub>Bảng này ghi phép CHUYỂN HƯỚNG; nó không định nghĩa thêm một phương ngữ nào</sub> |
| 3 | `new_dialect_id` | `text` | — | FK | — | `(tenant_id, new_dialect_id)` → `dialects(tenant_id, dialect_id)` | Định danh phương ngữ mà mục cũ được gộp vào. |
| 4 | `merged_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm gộp. |
| 5 | `merged_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã thực hiện gộp. |

### `dialects` — 14 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `tenant_id` | `text` | — | PK FK | `'default'::text` | `(tenant_id, merged_into)` → `dialects(tenant_id, dialect_id)`<br>`tenants.tenant_id` | Tổ chức xác định PHẠM VI của mục phương ngữ.<br><sub>Phạm vi, không phải quyền sở hữu chung chung: mỗi tổ chức có danh mục phương ngữ riêng, nhân bản từ khuôn Community lúc tạo</sub> |
| 2 | `dialect_id` | `text` | — | PK | — | — | Định danh phương ngữ, duy nhất trong phạm vi tổ chức.<br><sub>Slug này chính là thứ hiện trên giao diện và là tên thư mục lưu mẫu</sub> |
| 3 | `display_name` | `text` | — | — | — | — | Tên phương ngữ dạng người đọc. |
| 4 | `language` | `text` | — | FK | `'vn'::text` | `languages.code` | Ngôn ngữ ký hiệu chứa phương ngữ này. |
| 5 | `is_alphabet` | `boolean` | — | — | `false` | — | Phương ngữ này là bộ chữ cái ngón tay. |
| 6 | `is_active` | `boolean` | — | — | `true` | — | Phương ngữ còn được chọn trong các ô chọn hay không.<br><sub>TRỤC KHÁC với `status`. Đo được: `testdatase` có status=approved nhưng is_active=false, nên nó không hiện ở đâu cả</sub> |
| 7 | `status` | `text` | — | — | `'pending'::text` | — | Trạng thái vòng đời của ĐỀ NGHỊ thêm phương ngữ: `pending`, `approved` hoặc `rejected`.<br><sub>TRỤC KHÁC với `is_active`. `pending` = người tạo dùng được ngay, người khác chưa thấy</sub> |
| 8 | `merged_into` | `text` | ✓ | FK | — | `(tenant_id, merged_into)` → `dialects(tenant_id, dialect_id)` | Phương ngữ đích khi mục này bị gộp đi.<br><sub>Từ chối một đề nghị là GỘP, không phải xoá — nếu không, mẫu đã thu dưới phương ngữ ấy sẽ bị bỏ rơi</sub> |
| 9 | `created_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã đề nghị thêm phương ngữ. |
| 10 | `approved_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã duyệt. |
| 11 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm đề nghị. |
| 12 | `approved_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm duyệt. |
| 13 | `note` | `text` | ✓ | — | — | — | Ghi chú của người vận hành. |
| 14 | `display_order` | `integer` | — | — | `0` | — | Thứ tự hiển thị do người vận hành sắp. |

### `languages` — 2 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `code` | `character varying(50)` | — | PK | — | — | Mã ngôn ngữ ký hiệu. |
| 2 | `name` | `text` | — | — | — | — | Tên ngôn ngữ ký hiệu. |

### `recognition_profiles` — 7 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `tenant_id` | `text` | — | PK FK | `'default'::text` | `tenants.tenant_id` | Tổ chức xác định phạm vi của hồ sơ nhận dạng. |
| 2 | `profile_id` | `text` | — | PK | — | — | Định danh hồ sơ nhận dạng, duy nhất trong phạm vi tổ chức. |
| 3 | `display_name` | `text` | — | — | — | — | Tên hồ sơ dạng người đọc. |
| 4 | `is_trainable` | `boolean` | — | — | `true` | — | Cờ được mang theo trong ảnh chụp registry. **`CẦN DUYỆT`**<br><sub>KHÔNG cổng huấn luyện nào đọc cột này; người đọc duy nhất là app/cli/export_registry_snapshot.py. Ý nghĩa dự kiến cần tác giả xác nhận trước khi mô tả nó như một điều kiện huấn luyện</sub> |
| 5 | `is_active` | `boolean` | — | — | `true` | — | Hồ sơ còn được chọn hay đã nghỉ hưu. |
| 6 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo hồ sơ. |
| 7 | `display_order` | `integer` | — | — | `0` | — | Thứ tự hiển thị. |

### `regions` — 8 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `code` | `text` | — | PK | — | — | Mã vùng miền.<br><sub>Dữ liệu tham chiếu dùng chung; bảng KHÔNG có tenant_id</sub> |
| 2 | `name_vi` | `text` | — | — | — | — | Tên vùng miền tiếng Việt. |
| 3 | `name_en` | `text` | — | — | `''::text` | — | Tên vùng miền tiếng Anh. |
| 4 | `status` | `text` | — | — | `'approved'::text` | — | Trạng thái duyệt của mục vùng miền.<br><sub>Khác `is_active`: cột này nói mục đã được duyệt chưa, cột kia nói còn dùng nữa không</sub> |
| 5 | `sort_order` | `integer` | — | — | `0` | — | Thứ tự hiển thị. |
| 6 | `is_active` | `boolean` | — | — | `true` | — | Vùng miền còn được chọn hay đã nghỉ hưu. |
| 7 | `note` | `text` | ✓ | — | — | — | Ghi chú của người vận hành. |
| 8 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm cập nhật gần nhất. |

### `registry_versions` — 7 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `tenant_id` | `text` | — | PK FK | — | `tenants.tenant_id` | Tổ chức sở hữu phiên bản registry này. |
| 2 | `version` | `bigint` | — | PK | — | — | Số hiệu phiên bản registry TRONG PHẠM VI một tổ chức.<br><sub>KHÁC `community_versions.version`, vốn đánh số cho khuôn nền tảng</sub> |
| 3 | `content_hash` | `text` | — | — | — | — | Băm nội dung của bản chụp.<br><sub>Cho phép biết danh mục hiện tại đã khác bản công bố gần nhất chưa, mà không cần so ngày</sub> |
| 4 | `snapshot` | `jsonb` | — | — | — | — | Bản chụp bất biến toàn bộ danh mục của tổ chức tại thời điểm công bố. |
| 5 | `note` | `text` | ✓ | — | — | — | Ghi chú kèm lượt công bố. |
| 6 | `created_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã công bố. |
| 7 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm công bố. |

### `vocabulary_groups` — 6 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `tenant_id` | `text` | — | PK FK | — | `tenants.tenant_id` | Tổ chức xác định phạm vi của nhóm từ vựng. |
| 2 | `group_id` | `text` | — | PK | — | — | Định danh nhóm từ vựng, duy nhất trong phạm vi tổ chức. |
| 3 | `display_name` | `text` | — | — | — | — | Tên nhóm dạng người đọc. |
| 4 | `display_order` | `integer` | — | — | `0` | — | Thứ tự hiển thị. |
| 5 | `is_active` | `boolean` | — | — | `true` | — | Nhóm còn được chọn hay đã nghỉ hưu. |
| 6 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo nhóm. |

### `vocabulary_registry_meta` — 3 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `tenant_id` | `text` | — | PK FK | `'default'::text` | `(tenant_id, version)` → `registry_versions(tenant_id, version)`<br>`tenants.tenant_id` | Tổ chức mà con trỏ này thuộc về.<br><sub>Đồng thời là khoá chính, nên mỗi tổ chức có nhiều nhất MỘT dòng — quan hệ 1–1</sub> |
| 2 | `version` | `bigint` | ✓ | FK | — | `(tenant_id, version)` → `registry_versions(tenant_id, version)` | CON TRỎ tới phiên bản registry đang công bố của tổ chức. NULL = chưa công bố phiên bản nào.<br><sub>Không phải một phiên bản riêng: nó chỉ trỏ vào registry_versions. Trước v7 chỗ này dùng số 0 làm mốc 'chưa có gì', mà 0 là phiên bản KHÔNG BAO GIỜ tồn tại — nên nó làm hỏng lượt tạo tổ chức khi khoá ngoại ghép ra đời</sub> |
| 3 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm con trỏ được cập nhật gần nhất. |

## D. VSL Collection & Dataset

### `capture_sessions` — 12 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `capture_session_id` | `uuid` | — | PK | — | — | Định danh phiên thu một lớp ký hiệu. |
| 2 | `tenant_id` | `text` | — | FK | — | `(tenant_id, class_uid)` → `classes(tenant_id, class_uid)`<br>`(tenant_id, collection_session_id)` → `collection_sessions(tenant_id, collection_session_id)`<br>`(tenant_id, signer_id)` → `signers(tenant_id, signer_id)`<br>`tenants.tenant_id` | Tổ chức sở hữu bản ghi. |
| 3 | `class_uid` | `text` | — | FK | — | `(tenant_id, class_uid)` → `classes(tenant_id, class_uid)` | Lớp ký hiệu được thu trong phiên này. |
| 4 | `session_id` | `text` | — | — | — | — | Mã phiên do client gửi; duy nhất theo (tổ chức, lớp), KHÔNG duy nhất một mình.<br><sub>Đo: 61 giá trị khác nhau, một mã trải nhiều lớp</sub> |
| 5 | `signer_id` | `text` | ✓ | FK | — | `(tenant_id, signer_id)` → `signers(tenant_id, signer_id)` | Người ký TÓM TẮT của phiên, giữ lại từ thiết kế cũ. `LEGACY`<br><sub>Dữ liệu bác bỏ giả định một phiên một người: 10/253 phiên mang từ 2 nhãn người ký trở lên. KHÔNG dùng làm chân lý</sub> |
| 6 | `auth_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã thực hiện phiên thu.<br><sub>Khác danh tính người ký</sub> |
| 7 | `source_type` | `text` | ✓ | — | — | — | Kênh thu của phiên. |
| 8 | `started_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm phiên bắt đầu. |
| 9 | `ended_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm phiên kết thúc. |
| 10 | `note` | `text` | ✓ | — | — | — | Ghi chú tự do. **`CẦN DUYỆT`** |
| 11 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo bản ghi. |
| 12 | `collection_session_id` | `uuid` | ✓ | FK | — | `(tenant_id, collection_session_id)` → `collection_sessions(tenant_id, collection_session_id)` | Buổi thu chứa phiên này; NULL với dữ liệu có trước khi có phân cấp.<br><sub>ON DELETE SET NULL</sub> |

### `collection_sessions` — 9 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `collection_session_id` | `uuid` | — | PK | — | — | Định danh buổi thu. |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` | Tổ chức sở hữu bản ghi; là phạm vi áp dụng cách ly tenant. |
| 3 | `session_code` | `text` | — | — | — | — | Mã buổi thu do client sinh, duy nhất trong phạm vi một tổ chức.<br><sub>UNIQUE (tenant_id, session_code)</sub> |
| 5 | `opened_by_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã mở buổi thu.<br><sub>Là người VẬN HÀNH, không phải người ký</sub> |
| 6 | `source_type` | `text` | ✓ | — | — | — | Kênh thu: camera trực tiếp hay tải video lên. |
| 7 | `started_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm buổi thu bắt đầu. |
| 8 | `ended_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm buổi thu kết thúc; NULL khi chưa đóng.<br><sub>CHECK ended_at >= started_at</sub> |
| 9 | `note` | `text` | ✓ | — | — | — | Ghi chú tự do của người vận hành. **`CẦN DUYỆT`** |
| 10 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo bản ghi. |

### `raw_uploads` — 21 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `upload_uid` | `text` | — | PK | — | — | Định danh lượt tải lên; cũng là khoá chống trùng khi client gửi lại. |
| 2 | `class_uid` | `text` | ✓ | FK | — | `(tenant_id, class_uid)` → `classes(tenant_id, class_uid)` | Lớp ký hiệu của video. |
| 3 | `slug` | `text` | ✓ | — | — | — | Bản sao slug của lớp. **`CẦN DUYỆT`**<br><sub>Phi chuẩn hoá</sub> |
| 4 | `label_original` | `text` | ✓ | — | — | — | Bản sao nhãn gốc của lớp. **`CẦN DUYỆT`**<br><sub>Phi chuẩn hoá</sub> |
| 5 | `language` | `text` | ✓ | FK | — | `languages.code` | Ngôn ngữ ký hiệu. |
| 6 | `dialect` | `text` | ✓ | FK | — | `(tenant_id, dialect)` → `dialects(tenant_id, dialect_id)` | Phương ngữ. |
| 7 | `source_type` | `text` | ✓ | — | — | — | Luôn là video ở bảng này. |
| 8 | `user_id` | `text` | ✓ | — | — | — | Nhãn người ký dạng văn bản tự do. `LEGACY`<br><sub>KHÔNG phải định danh tài khoản</sub> |
| 9 | `auth_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã tải video lên. |
| 10 | `session_id` | `text` | ✓ | — | — | — | Mã phiên tại thời điểm tải lên. |
| 11 | `original_filename` | `text` | ✓ | — | — | — | Tên tệp do người dùng gửi lên, đã làm sạch. |
| 12 | `local_path` | `text` | ✓ | — | — | — | Đường dẫn video trên đĩa máy chủ.<br><sub>Là nguồn quy chủ dung lượng video: thư mục raw_videos KHÔNG phân vùng theo tenant</sub> |
| 13 | `storage_key` | `text` | ✓ | — | — | — | Khoá tệp tương đối so với gốc dataset. |
| 14 | `storage_url` | `text` | ✓ | — | — | — | Vị trí hiện tại của video; cập nhật sau khi đẩy lên Drive. |
| 15 | `created_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm tải lên. |
| 16 | `updated_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm cập nhật gần nhất. |
| 17 | `deleted_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm xoá mềm; tệp vẫn nằm trên đĩa. |
| 18 | `status` | `character varying(20)` | ✓ | — | `'PENDING'::character varying` | — | Trạng thái xử lý của lượt tải lên. **`CẦN DUYỆT`**<br><sub>Cần xác nhận tập giá trị hợp lệ</sub> |
| 19 | `session_uid` | `text` | ✓ | — | — | — | Mã phiên thứ hai. **`CẦN DUYỆT`**<br><sub>Cùng câu hỏi như samples.session_uid</sub> |
| 20 | `username` | `text` | ✓ | — | — | — | Bản sao tên tài khoản tại thời điểm tải lên. `LEGACY`<br><sub>Phi chuẩn hoá</sub> |
| 21 | `tenant_id` | `text` | — | FK | `'default'::text` | `(tenant_id, class_uid)` → `classes(tenant_id, class_uid)`<br>`(tenant_id, dialect)` → `dialects(tenant_id, dialect_id)`<br>`tenants.tenant_id` | Tổ chức sở hữu video. |

### `samples` — 46 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `sample_uid` | `text` | — | PK | — | — | Định danh mẫu.<br><sub>10 ký tự hex</sub> |
| 2 | `class_uid` | `text` | ✓ | FK | — | `(tenant_id, class_uid)` → `classes(tenant_id, class_uid)`<br>`classes.class_uid` | Lớp ký hiệu mà mẫu này mang nhãn. |
| 3 | `slug` | `text` | ✓ | — | — | — | Bản sao slug của lớp tại thời điểm ghi. **`CẦN DUYỆT`**<br><sub>Phi chuẩn hoá; nguồn chuẩn là classes</sub> |
| 4 | `label_original` | `text` | ✓ | — | — | — | Bản sao nhãn gốc của lớp tại thời điểm ghi. **`CẦN DUYỆT`**<br><sub>Phi chuẩn hoá</sub> |
| 5 | `language` | `text` | ✓ | FK | — | `languages.code` | Ngôn ngữ ký hiệu của mẫu. |
| 6 | `dialect` | `text` | ✓ | FK | — | `(tenant_id, dialect)` → `dialects(tenant_id, dialect_id)` | Phương ngữ của mẫu. |
| 7 | `source_type` | `text` | ✓ | — | — | — | Kênh thu: camera hay video tải lên. |
| 8 | `user_id` | `text` | ✓ | — | — | — | Nhãn người ký dạng văn bản tự do, giữ lại làm bằng chứng nguồn gốc. `LEGACY`<br><sub>KHÔNG phải định danh tài khoản. Là nguồn DUY NHẤT cho thấy 10/253 phiên có nhiều người ký</sub> |
| 9 | `auth_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã thực hiện thao tác thu/tải mẫu này.<br><sub>Khác hẳn danh tính người ký. 166/3.864 dòng còn trống</sub> |
| 10 | `session_id` | `text` | ✓ | — | — | — | Mã phiên do client gửi tại thời điểm thu.<br><sub>Đo: 2.867/3.864 dòng có giá trị, 61 giá trị khác nhau</sub> |
| 11 | `fps_original` | `text` | ✓ | — | — | — | Tốc độ khung hình của nguồn gốc. **`CẦN DUYỆT`**<br><sub>Kiểu text chứ không phải số — cần xác nhận vì sao</sub> |
| 12 | `fps_processed` | `text` | ✓ | — | — | — | Tốc độ khung hình sau xử lý. **`CẦN DUYỆT`**<br><sub>Kiểu text chứ không phải số</sub> |
| 13 | `seq_len` | `integer` | ✓ | — | — | — | Độ dài chuỗi sau khi đệm về độ dài đích. |
| 14 | `augment_id` | `integer` | ✓ | — | — | — | Chỉ số bản tăng cường; 0 là bản gốc. |
| 15 | `completeness` | `real` | ✓ | — | — | — | Tỷ lệ khung hình có bàn tay hợp lệ. `DERIVED`<br><sub>Tính lại được từ tệp npz</sub> |
| 16 | `file_path` | `text` | ✓ | — | — | — | Đường dẫn tệp đặc trưng, tương đối so với gốc dataset. |
| 17 | `storage_url` | `text` | ✓ | — | — | — | Đường dẫn hoặc URL nơi tệp đang nằm.<br><sub>Được cập nhật sau khi đẩy lên Drive</sub> |
| 18 | `checksum` | `text` | ✓ | — | — | — | Tổng kiểm của tệp đặc trưng. **`CẦN DUYỆT`**<br><sub>Thuật toán băm cần xác nhận</sub> |
| 19 | `created_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm ghi mẫu. |
| 20 | `sheets_synced` | `boolean` | ✓ | — | `false` | — | Đã đồng bộ sang Google Sheets chưa. |
| 21 | `gdrive_synced` | `boolean` | ✓ | — | `true` | — | Đã đồng bộ lên Google Drive chưa.<br><sub>Bẫy đã biết: CREATE TABLE mặc định FALSE còn ALTER mặc định TRUE, nên máy cài mới và máy cũ khác nhau</sub> |
| 23 | `status` | `character varying(20)` | ✓ | — | `'PENDING'::character varying` | — | Không còn được cập nhật. `LEGACY`<br><sub>Đo: giá trị duy nhất PENDING trên cả 3.864 dòng. Trạng thái kiểm duyệt sống ở review_status</sub> |
| 24 | `error_log` | `text` | ✓ | — | `''::text` | — | Thông báo lỗi của lượt xử lý, nếu có. **`CẦN DUYỆT`** |
| 25 | `updated_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm cập nhật gần nhất. |
| 26 | `storage_key` | `text` | ✓ | — | `''::text` | — | Khoá tệp trên kho lưu trữ, tương đối so với gốc dataset. |
| 27 | `session_uid` | `text` | ✓ | — | — | — | Mã phiên thứ hai, khác session_id. **`CẦN DUYỆT`**<br><sub>Đo: 991 dòng có giá trị, 109 giá trị khác nhau. Quan hệ với session_id chưa rõ</sub> |
| 28 | `username` | `text` | ✓ | — | — | — | Bản sao tên tài khoản tại thời điểm ghi. `LEGACY`<br><sub>Phi chuẩn hoá; đổi tên tài khoản KHÔNG cập nhật ngược về đây</sub> |
| 30 | `deleted_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm xoá mềm; tệp VẪN nằm trên đĩa cho tới khi dọn Thùng rác.<br><sub>Vì vậy xoá mềm không trả lại dung lượng</sub> |
| 31 | `left_hand_ratio` | `real` | ✓ | — | — | — | Tỷ lệ khung hình phát hiện được tay trái. `DERIVED` |
| 32 | `right_hand_ratio` | `real` | ✓ | — | — | — | Tỷ lệ khung hình phát hiện được tay phải. `DERIVED` |
| 33 | `both_hands_ratio` | `real` | ✓ | — | — | — | Tỷ lệ khung hình phát hiện được cả hai tay. `DERIVED` |
| 34 | `jitter` | `real` | ✓ | — | — | — | Độ rung của chuỗi landmark, phân vị 95. `DERIVED`<br><sub>KHÔNG tính lại được từ dữ liệu đã lưu, khác với completeness</sub> |
| 35 | `quality_flags` | `text` | ✓ | — | — | — | Các cờ cảnh báo chất lượng của lượt thu. `DERIVED` |
| 36 | `signer_id` | `text` | ✓ | FK | — | `(tenant_id, signer_id)` → `signers(tenant_id, signer_id)` | Danh tính người ký đã chuẩn hoá, khi đã phân định được.<br><sub>2.186/3.864 dòng còn trống, ĐANG ĐÓNG BĂNG chờ duyệt 266 khối thời gian</sub> |
| 37 | `collection_campaign` | `text` | ✓ | — | — | — | Đợt thu thập mà mẫu thuộc về. **`CẦN DUYỆT`** |
| 38 | `raw_landmarks_available` | `boolean` | ✓ | — | — | — | Có bản landmark thô trong kho raw hay không.<br><sub>Kho raw là nửa KHÔNG tái tạo được của một mẫu</sub> |
| 39 | `normalization_version` | `text` | ✓ | — | — | — | Phiên bản thuật toán chuẩn hoá đã áp cho mẫu.<br><sub>Cho phép chạy lại chuẩn hoá mà vẫn biết mẫu nào đã dùng phiên bản nào</sub> |
| 40 | `preprocess_contract_version` | `text` | ✓ | — | — | — | Phiên bản hợp đồng tiền xử lý. |
| 41 | `sequence_length_original` | `integer` | ✓ | — | — | — | Số khung hình trước khi đệm hoặc cắt. |
| 42 | `quality_status` | `text` | ✓ | — | — | — | Kết luận chất lượng: đạt hay bị gắn cờ. `DERIVED` |
| 43 | `tenant_id` | `text` | — | FK | `'default'::text` | `(tenant_id, capture_session_id)` → `capture_sessions(tenant_id, capture_session_id)`<br>`(tenant_id, class_uid)` → `classes(tenant_id, class_uid)`<br>`(tenant_id, signer_id)` → `signers(tenant_id, signer_id)`<br>`(tenant_id, dialect)` → `dialects(tenant_id, dialect_id)`<br>`tenants.tenant_id` | Tổ chức sở hữu mẫu; là phạm vi áp dụng cách ly tenant.<br><sub>Tham gia 5 khoá ngoại ghép cùng lúc — trụ neo tenant của bảng này</sub> |
| 44 | `capture_session_id` | `uuid` | ✓ | FK | — | `(tenant_id, capture_session_id)` → `capture_sessions(tenant_id, capture_session_id)`<br>`capture_sessions.capture_session_id` | Phiên thu chứa mẫu này.<br><sub>997/3.864 dòng còn trống — dữ liệu có trước khi đường ghi nối phân cấp. Chỉ có trong CSDL, không có trong samples.csv</sub> |
| 45 | `review_status` | `text` | — | — | `'pending'::text` | — | Trạng thái kiểm duyệt của mẫu.<br><sub>Giá trị đang có: pending, approved</sub> |
| 46 | `reviewed_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã kiểm duyệt mẫu. |
| 47 | `reviewed_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm kiểm duyệt. |
| 48 | `review_note` | `text` | ✓ | — | `''::text` | — | Ghi chú của người kiểm duyệt. |

### `signer_aliases` — 6 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `tenant_id` | `text` | — | PK FK | — | `(tenant_id, new_signer_id)` → `signers(tenant_id, signer_id)`<br>`tenants.tenant_id` | Tổ chức sở hữu bản ghi gộp. |
| 2 | `old_signer_id` | `text` | — | PK | — | — | Định danh người ký đã bị gộp đi. |
| 3 | `new_signer_id` | `text` | — | FK | — | `(tenant_id, new_signer_id)` → `signers(tenant_id, signer_id)` | Định danh người ký còn lại sau khi gộp. |
| 4 | `reason` | `text` | ✓ | — | — | — | Lý do gộp. |
| 5 | `merged_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm gộp. |
| 6 | `merged_by` | `uuid` | ✓ | FK | — | `users.id` | Người thực hiện gộp. |

### `signers` — 9 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `signer_id` | `text` | — | PK | — | — | Định danh chuẩn hoá của người ký, trong phạm vi một tổ chức. |
| 2 | `display_name` | `text` | ✓ | — | — | — | Tên hiển thị của người ký. |
| 3 | `regional_group` | `text` | ✓ | — | — | — | Nhóm vùng miền của người ký. **`CẦN DUYỆT`**<br><sub>Quan hệ với bảng regions cần xác nhận</sub> |
| 4 | `external_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản hệ thống tương ứng, nếu người ký cũng là người dùng.<br><sub>NULL khi người ký không có tài khoản</sub> |
| 5 | `is_active` | `boolean` | ✓ | — | `true` | — | Người ký còn tham gia thu hay không. |
| 6 | `created_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm đăng ký người ký. |
| 7 | `tenant_id` | `text` | — | FK | `'default'::text` | `tenants.tenant_id` | Tổ chức quản lý hồ sơ người ký. |
| 8 | `note` | `text` | ✓ | — | — | — | Ghi chú tự do. **`CẦN DUYỆT`** |
| 9 | `display_order` | `integer` | — | — | `0` | — | Thứ tự hiển thị do người vận hành sắp. |

## E. Legal, Consent & Governance

### `audit_log` — 10 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `audit_id` | `bigint` | — | PK | `nextval('audit_log_audit_id_seq'::regclass)` | — | Số thứ tự dòng kiểm toán. |
| 2 | `tenant_id` | `text` | ✓ | FK | — | `tenants.tenant_id` | Tổ chức của hành động. NULL với hành động cấp NỀN TẢNG.<br><sub>Là bảng duy nhất trong nhóm có tenant_id cho phép NULL — không phải mọi dòng đều thuộc một tổ chức</sub> |
| 3 | `actor_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản thực hiện hành động. |
| 4 | `actor_label` | `text` | ✓ | — | — | — | Nhãn người thực hiện, chụp lại tại thời điểm ghi.<br><sub>Là bằng chứng lịch sử: KHÔNG cập nhật khi tài khoản đổi tên, và còn lại sau khi tài khoản bị xoá</sub> |
| 5 | `action` | `text` | — | — | — | — | Hành động được ghi lại; CHECK cấm chuỗi rỗng. |
| 6 | `target_type` | `text` | ✓ | — | — | — | Loại đối tượng bị tác động. |
| 7 | `target_id` | `text` | ✓ | — | — | — | Định danh đối tượng bị tác động. |
| 8 | `detail` | `jsonb` | ✓ | — | — | — | Dữ liệu bổ sung, dạng JSON. |
| 9 | `ip_hash` | `text` | ✓ | — | — | — | Băm địa chỉ IP của lượt thao tác. |
| 10 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm ghi dòng kiểm toán. |

### `legal_document_drafts` — 21 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `draft_id` | `uuid` | — | PK | — | — | Định danh bản thảo văn bản. |
| 2 | `kind` | `text` | — | — | — | — | Loại văn bản mà bản thảo này nhắm tới. |
| 3 | `title` | `text` | — | — | `''::text` | — | Tiêu đề dự kiến. |
| 4 | `language` | `text` | — | — | `'vi'::text` | — | Ngôn ngữ bản thảo. |
| 5 | `body` | `text` | — | — | `''::text` | — | Thân bản thảo. |
| 6 | `body_format` | `text` | — | — | `'markdown'::text` | — | Dạng thân bản thảo. |
| 7 | `change_summary` | `text` | — | — | `''::text` | — | Tóm tắt thay đổi dự kiến. |
| 8 | `target_version` | `text` | — | — | `''::text` | — | Số hiệu phiên bản dự kiến đặt khi công bố. |
| 9 | `requires_reconsent` | `boolean` | — | — | `false` | — | Bản công bố từ bản thảo này sẽ buộc chấp thuận lại. |
| 10 | `effective_from` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm hiệu lực dự kiến. |
| 11 | `status` | `text` | — | — | `'draft'::text` | — | Trạng thái: `draft`, `in_review`, `approved`, `published` hoặc `discarded`.<br><sub>Chỉ mục duy nhất MỘT PHẦN cho phép tối đa một bản thảo đang mở cho mỗi loại văn bản</sub> |
| 12 | `revision` | `integer` | — | — | `1` | — | Số lần sửa bản thảo, bắt đầu từ 1. |
| 13 | `based_on_version` | `text` | ✓ | — | — | — | Phiên bản đã công bố mà bản thảo dựa trên. |
| 14 | `published_version` | `text` | ✓ | — | — | — | Phiên bản thực tế được công bố từ bản thảo này. |
| 15 | `storage_key` | `text` | ✓ | — | — | — | Khoá tra thân bản thảo trong kho. |
| 16 | `content_hash` | `text` | ✓ | — | — | — | Băm nội dung bản thảo. |
| 17 | `byte_size` | `integer` | — | — | `0` | — | Kích thước thân bản thảo. |
| 18 | `created_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã tạo bản thảo. |
| 19 | `updated_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản sửa bản thảo gần nhất. |
| 20 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo bản thảo. |
| 21 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm sửa gần nhất. |

### `legal_document_events` — 12 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `event_id` | `bigint` | — | PK | `nextval('legal_document_events_event_id_seq'`… | — | Số thứ tự sự kiện trong sổ. |
| 2 | `occurred_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm sự kiện xảy ra. |
| 3 | `actor_user_id` | `uuid` | ✓ | — | — | — | Tài khoản thực hiện. Giữ như dấu vết, KHÔNG có khoá ngoại.<br><sub>Cố ý: một sổ đăng bạ không được cản chính hành động nó ghi lại. Bản trước có khoá ngoại và nó chặn lượt xoá tài khoản theo yêu cầu quyền riêng tư, để lại 9 hàng users mồ côi</sub> |
| 4 | `actor_label` | `text` | — | — | `''::text` | — | Nhãn người thực hiện, điền ngay lúc ghi.<br><sub>Là danh tính còn lại sau khi tài khoản bị xoá; KHÔNG cập nhật khi người dùng đổi tên</sub> |
| 5 | `action` | `text` | — | — | — | — | Hành động được ghi lại. |
| 6 | `kind` | `text` | ✓ | — | — | — | Loại văn bản liên quan. Dấu vết, không phải liên kết. |
| 7 | `version` | `text` | ✓ | — | — | — | Phiên bản văn bản liên quan. Dấu vết, không phải liên kết. |
| 8 | `draft_id` | `uuid` | ✓ | — | — | — | Bản thảo liên quan. Dấu vết, không phải liên kết. |
| 9 | `revision` | `integer` | ✓ | — | — | — | Số sửa của bản thảo tại thời điểm sự kiện. |
| 10 | `storage_key` | `text` | ✓ | — | — | — | Khoá tra nội dung tại thời điểm sự kiện. |
| 11 | `content_hash` | `text` | ✓ | — | — | — | Băm nội dung tại thời điểm sự kiện. |
| 12 | `detail` | `jsonb` | ✓ | — | — | — | Dữ liệu bổ sung của sự kiện, dạng JSON. |

### `legal_documents` — 21 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `doc_id` | `uuid` | — | PK | — | — | Định danh bản văn bản pháp lý đã công bố. |
| 2 | `kind` | `text` | — | — | — | — | Loại văn bản: `terms`, `privacy`, `data_contribution` hoặc `guardian`.<br><sub>Cùng với `version` tạo thành khoá tự nhiên mà mọi chấp thuận neo vào</sub> |
| 3 | `version` | `text` | — | — | — | — | Phiên bản văn bản.<br><sub>`(kind, version)` là đích của khoá ngoại từ user_consents và signer_consents</sub> |
| 4 | `effective_from` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm văn bản bắt đầu có hiệu lực. |
| 5 | `content_hash` | `text` | — | — | — | — | Băm nội dung; là thứ chữ ký chấp thuận trỏ vào.<br><sub>Bất biến sau khi công bố — sửa nội dung sẽ làm mọi chấp thuận đã ghi không còn khớp</sub> |
| 6 | `url` | `text` | — | — | — | — | Đường dẫn công khai tới văn bản. |
| 7 | `title` | `text` | — | — | `''::text` | — | Tiêu đề văn bản. |
| 8 | `requires_reconsent` | `boolean` | — | — | `false` | — | Bản này buộc người đã chấp thuận bản cũ phải chấp thuận lại.<br><sub>Phân biệt sửa lỗi chính tả với thay đổi thực chất về quyền và nghĩa vụ</sub> |
| 9 | `body` | `text` | — | — | `''::text` | — | Thân văn bản lưu thẳng trong cơ sở dữ liệu. |
| 10 | `body_format` | `text` | — | — | `'markdown'::text` | — | Dạng thân văn bản: `markdown`, `text` hoặc `file`.<br><sub>Máy CÀI MỚI thiếu giá trị `file` do một lỗi thứ tự câu lệnh — xem docs/10-issues/KNOWN_ISSUES.md</sub> |
| 11 | `language` | `text` | — | — | `'vi'::text` | — | Ngôn ngữ của bản văn bản. |
| 12 | `change_summary` | `text` | — | — | `''::text` | — | Tóm tắt thay đổi so với bản trước. |
| 13 | `published_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm công bố. |
| 14 | `published_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã công bố văn bản. |
| 15 | `storage_backend` | `text` | — | — | `'local'::text` | — | Nơi lưu thân văn bản khi không nằm trong cột `body`. |
| 16 | `storage_key` | `text` | ✓ | — | — | — | Khoá tra thân văn bản trong kho định-địa-chỉ-bằng-nội-dung. |
| 17 | `byte_size` | `integer` | — | — | `0` | — | Kích thước thân văn bản. |
| 18 | `file_key` | `text` | ✓ | — | — | — | Khoá tra tệp đính kèm khi `body_format = 'file'`.<br><sub>CHECK buộc cột này có giá trị KHI VÀ CHỈ KHI body_format = 'file'</sub> |
| 19 | `file_name` | `text` | ✓ | — | — | — | Tên tệp gốc của bản văn bản dạng tệp. |
| 20 | `file_mime` | `text` | ✓ | — | — | — | Kiểu MIME của tệp đính kèm. |
| 21 | `file_size` | `bigint` | ✓ | — | — | — | Kích thước tệp đính kèm. |

### `signer_consents` — 11 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `consent_id` | `uuid` | — | PK | — | — | Định danh bản ghi chấp thuận của người ký. |
| 2 | `tenant_id` | `text` | — | FK | — | `(tenant_id, signer_id)` → `signers(tenant_id, signer_id)`<br>`tenants.tenant_id` | Tổ chức xác định phạm vi của bản ghi. |
| 3 | `signer_id` | `text` | — | FK | — | `(tenant_id, signer_id)` → `signers(tenant_id, signer_id)` | Người ký LÀ CHỦ THỂ của chấp thuận.<br><sub>Khoá ngoại ghép `(tenant_id, signer_id)`</sub> |
| 4 | `scope` | `text` | — | — | — | — | Mức cho phép sử dụng dữ liệu: `internal_training`, `research_release` hoặc `public_library`.<br><sub>Thang ba mức, rộng dần. `tenant_exports.export_purpose` dùng CÙNG bộ từ vựng — đó là chỗ nối chấp thuận vào phép phát hành</sub> |
| 5 | `kind` | `text` | — | FK | — | `(kind, version)` → `legal_documents(kind, version)` | Loại văn bản được chấp thuận. |
| 6 | `version` | `text` | — | FK | — | `(kind, version)` → `legal_documents(kind, version)` | Phiên bản văn bản được chấp thuận.<br><sub>Cùng cơ chế neo `(kind, version)` như user_consents</sub> |
| 7 | `granted_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm cho phép. |
| 8 | `withdrawn_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm rút cho phép.<br><sub>CHECK buộc mốc rút không sớm hơn mốc cho phép</sub> |
| 9 | `guardian_name` | `text` | ✓ | — | — | — | Tên người giám hộ khi người ký chưa đủ tuổi tự quyết. |
| 10 | `evidence` | `text` | ✓ | — | — | — | Mô tả bằng chứng của lượt cho phép. |
| 11 | `recorded_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã ghi bản ghi này. |

### `sot_authorized_keys` — 7 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `public_key` | `text` | — | PK | — | — | Khoá công khai của máy được phép ghi SOT.<br><sub>Khoá công khai không phải bí mật; khoá riêng không bao giờ rời máy ghi</sub> |
| 2 | `name` | `text` | — | — | — | — | Tên máy ghi. |
| 3 | `fingerprint` | `text` | — | — | — | — | Vân tay khoá, dùng để đối chiếu nhanh. |
| 4 | `note` | `text` | ✓ | — | — | — | Ghi chú của người vận hành. |
| 5 | `added_by` | `text` | ✓ | — | — | — | Người đã thêm khoá, dạng VĂN BẢN. **`CẦN DUYỆT`**<br><sub>Kiểu text chứ không phải uuid nên đây không phải tham chiếu tài khoản; lý do thiết kế chưa được ghi lại ở đâu</sub> |
| 6 | `added_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm thêm khoá. |
| 7 | `revoked_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm thu hồi khoá.<br><sub>Bảng này được hợp với danh sách khoá cam kết trong kho mã, nên một máy đăng ký ở đây được tin cậy mà không cần triển khai lại</sub> |

### `tenant_exports` — 13 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `export_id` | `uuid` | — | PK | — | — | Định danh lượt xuất dữ liệu. |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` | Tổ chức yêu cầu xuất. |
| 3 | `requested_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã yêu cầu. |
| 4 | `status` | `text` | — | — | `'pending'::text` | — | Trạng thái: `pending`, `running`, `ready`, `failed` hoặc `expired`. |
| 5 | `scope` | `text` | — | — | `'metadata'::text` | — | Phạm vi dữ liệu xuất: `metadata` hoặc `full`. |
| 6 | `file_path` | `text` | ✓ | — | — | — | Đường dẫn tệp kết quả.<br><sub>Tệp xuất CỐ Ý không tính vào hạn mức dung lượng: nó là bản sao của byte đã tính</sub> |
| 7 | `size_bytes` | `bigint` | ✓ | — | — | — | Kích thước tệp kết quả. |
| 8 | `row_counts` | `jsonb` | ✓ | — | — | — | Số hàng đã xuất theo từng bảng, dạng JSON. |
| 9 | `error` | `text` | ✓ | — | — | — | Thông báo lỗi khi lượt xuất thất bại. |
| 10 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm yêu cầu. |
| 11 | `completed_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm hoàn tất. |
| 12 | `expires_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm tệp xuất hết hạn và bị dọn. |
| 13 | `export_purpose` | `text` | — | — | `'tenant_portability'::text` | — | Mục đích phát hành: `tenant_portability`, `internal_training`, `research_release` hoặc `public_library`.<br><sub>Ba giá trị sau TRÙNG bộ từ vựng của signer_consents.scope — đó là chỗ mức chấp thuận quyết định mẫu nào được phép ra khỏi hệ thống</sub> |

### `tenant_purges` — 10 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `purge_id` | `uuid` | — | PK | — | — | Định danh lượt xoá tổ chức. |
| 2 | `tenant_id` | `text` | — | — | — | — | Định danh tổ chức đã bị xoá. Là CHỮ, là dấu vết, không phải liên kết.<br><sub>Cố ý không có khoá ngoại tới tenants: một khoá ngoại sẽ khiến chính hành động bảng này ghi lại trở nên bất khả thi. Cũng vì thế bảng không nằm trong TENANT_SCOPED_TABLES và không có RLS</sub> |
| 3 | `display_name` | `text` | — | — | `''::text` | — | Tên tổ chức tại thời điểm xoá. |
| 4 | `requested_by` | `uuid` | ✓ | — | — | — | Tài khoản đã yêu cầu xoá. Dấu vết, không có khoá ngoại. |
| 5 | `row_counts` | `jsonb` | ✓ | — | — | — | Số hàng đã xoá theo từng bảng, dạng JSON. |
| 6 | `files_removed` | `integer` | — | — | `0` | — | Số tệp đã gỡ khỏi kho. |
| 7 | `bytes_removed` | `bigint` | — | — | `0` | — | Số byte đã giải phóng. |
| 8 | `export_id` | `uuid` | ✓ | — | — | — | Lượt xuất dữ liệu thực hiện trước khi xoá, nếu có.<br><sub>Dấu vết cho thấy tổ chức đã được trao dữ liệu trước khi bị xoá</sub> |
| 9 | `reason` | `text` | — | — | `''::text` | — | Lý do xoá. |
| 10 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm xoá. |

### `user_consents` — 11 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `consent_id` | `uuid` | — | PK | — | — | Định danh bản ghi chấp thuận của tài khoản. |
| 2 | `user_id` | `uuid` | — | FK | — | `users.id` | Tài khoản LÀ CHỦ THỂ của chấp thuận.<br><sub>Khác `recorded_by`: người ghi bằng chứng không nhất thiết là người được ghi nhận</sub> |
| 3 | `kind` | `text` | — | FK | — | `(kind, version)` → `legal_documents(kind, version)` | Loại văn bản được chấp thuận. |
| 4 | `version` | `text` | — | FK | — | `(kind, version)` → `legal_documents(kind, version)` | Phiên bản văn bản được chấp thuận.<br><sub>Khoá ngoại ghép `(kind, version)` neo chấp thuận vào ĐÚNG MỘT bản; RESTRICT nên không xoá được bản còn người đã chấp thuận</sub> |
| 5 | `accepted_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm chấp thuận. |
| 6 | `ip_hash` | `text` | ✓ | — | — | — | Băm địa chỉ IP lúc chấp thuận.<br><sub>Băm chứ không lưu thẳng: đủ để đối chiếu, không đủ để theo dõi</sub> |
| 7 | `user_agent` | `text` | ✓ | — | — | — | Chuỗi user-agent lúc chấp thuận. |
| 8 | `withdrawn_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm rút chấp thuận.<br><sub>Rút là rút: bản ghi không bị xoá, nhưng hiệu lực chấm dứt từ mốc này</sub> |
| 9 | `source` | `text` | — | — | `'user'::text` | — | Nguồn bản ghi: `user`, `backfill` hoặc `import`.<br><sub>Đo trên sản xuất: hiện có `user` và `backfill`. Đây là lý do tên quan hệ dùng 'anchors' chứ không 'signs'</sub> |
| 10 | `note` | `text` | — | — | `''::text` | — | Ghi chú kèm bản ghi chấp thuận. |
| 11 | `recorded_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã GHI bản ghi này.<br><sub>NULL khi chính người dùng tự chấp thuận qua giao diện</sub> |

## F. Training & Evaluation

### `training_job_classes` — 5 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `job_id` | `text` | — | PK FK | — | `training_jobs.job_id` |  |
| 2 | `class_idx` | `integer` | — | PK | — | — |  |
| 3 | `class_uid` | `text` | ✓ | FK | — | `classes.class_uid` |  |
| 4 | `label` | `text` | — | — | — | — |  |
| 5 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` |  |

### `training_jobs` — 19 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `job_id` | `text` | — | PK | — | — |  |
| 2 | `status` | `text` | — | — | — | — |  |
| 3 | `model_type` | `text` | ✓ | — | — | — |  |
| 4 | `config` | `jsonb` | ✓ | — | — | — |  |
| 5 | `auth_user_id` | `uuid` | ✓ | FK | — | `users.id` |  |
| 6 | `created_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 7 | `started_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 8 | `completed_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 9 | `current_epoch` | `integer` | — | — | `0` | — |  |
| 10 | `total_epochs` | `integer` | — | — | `0` | — |  |
| 11 | `checkpoint_path` | `text` | ✓ | — | — | — |  |
| 12 | `test_acc` | `real` | ✓ | — | — | — |  |
| 13 | `test_f1` | `real` | ✓ | — | — | — |  |
| 14 | `error_message` | `text` | ✓ | — | — | — |  |
| 15 | `promoted_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 16 | `evaluation` | `jsonb` | ✓ | — | — | — |  |
| 17 | `superseded_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 18 | `tenant_id` | `text` | — | FK | — | `(tenant_id, registry_version)` → `registry_versions(tenant_id, version)`<br>`tenants.tenant_id` |  |
| 19 | `registry_version` | `bigint` | ✓ | FK | — | `(tenant_id, registry_version)` → `registry_versions(tenant_id, version)` |  |

### `training_metrics` — 9 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `job_id` | `text` | — | PK FK | — | `(tenant_id, job_id)` → `training_jobs(tenant_id, job_id)`<br>`training_jobs.job_id` |  |
| 2 | `epoch` | `integer` | — | PK | — | — |  |
| 3 | `train_loss` | `real` | ✓ | — | — | — |  |
| 4 | `train_acc` | `real` | ✓ | — | — | — |  |
| 5 | `val_loss` | `real` | ✓ | — | — | — |  |
| 6 | `val_acc` | `real` | ✓ | — | — | — |  |
| 7 | `val_f1` | `real` | ✓ | — | — | — |  |
| 8 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 9 | `tenant_id` | `text` | — | FK | — | `(tenant_id, job_id)` → `training_jobs(tenant_id, job_id)`<br>`tenants.tenant_id` |  |

## G. Plan, Billing & Storage

### `plans` — 25 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `plan_code` | `text` | — | PK | — | — |  |
| 2 | `display_name` | `text` | — | — | — | — |  |
| 3 | `description` | `text` | — | — | `''::text` | — |  |
| 4 | `max_seats` | `integer` | ✓ | — | — | — |  |
| 5 | `max_samples` | `integer` | ✓ | — | — | — |  |
| 6 | `max_storage_mb` | `integer` | ✓ | — | — | — |  |
| 7 | `max_classes` | `integer` | ✓ | — | — | — |  |
| 8 | `max_training_jobs_per_month` | `integer` | ✓ | — | — | — |  |
| 9 | `max_concurrent_training_jobs` | `integer` | ✓ | — | `1` | — |  |
| 10 | `max_queued_training_jobs` | `integer` | ✓ | — | `3` | — |  |
| 11 | `max_api_keys` | `integer` | ✓ | — | `0` | — |  |
| 12 | `max_webhook_endpoints` | `integer` | ✓ | — | `0` | — |  |
| 13 | `price_cents` | `bigint` | ✓ | — | `0` | — |  |
| 14 | `currency` | `text` | — | — | `'VND'::text` | — |  |
| 15 | `billing_period` | `text` | — | — | `'monthly'::text` | — |  |
| 16 | `is_self_serve` | `boolean` | — | — | `false` | — |  |
| 17 | `is_listed` | `boolean` | — | — | `true` | — |  |
| 18 | `trial_days` | `integer` | — | — | `0` | — |  |
| 19 | `sort_order` | `integer` | — | — | `0` | — |  |
| 20 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 21 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 26 | `max_workspaces` | `integer` | ✓ | — | — | — |  |
| 27 | `max_projects` | `integer` | ✓ | — | — | — |  |
| 28 | `included_training_credits` | `integer` | ✓ | — | — | — |  |
| 29 | `audit_retention_days` | `integer` | ✓ | — | — | — |  |

### `storage_reservations` — 5 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `reservation_id` | `uuid` | — | PK | — | — |  |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` |  |
| 3 | `bytes` | `bigint` | — | — | — | — |  |
| 4 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 5 | `expires_at` | `timestamp with time zone` | — | — | — | — |  |

### `tenant_storage` — 4 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `tenant_id` | `text` | — | PK FK | — | `tenants.tenant_id` |  |
| 2 | `bytes_used` | `bigint` | — | — | `0` | — |  |
| 3 | `reconciled_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 4 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — |  |

### `tenant_subscriptions` — 15 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `subscription_id` | `uuid` | — | PK | — | — |  |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` |  |
| 3 | `plan_code` | `text` | — | FK | — | `plans.plan_code` |  |
| 4 | `status` | `text` | — | — | `'active'::text` | — |  |
| 5 | `started_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 6 | `ended_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 7 | `changed_by` | `uuid` | ✓ | FK | — | `users.id` |  |
| 8 | `note` | `text` | — | — | `''::text` | — |  |
| 9 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 10 | `current_period_start` | `timestamp with time zone` | ✓ | — | — | — |  |
| 11 | `current_period_end` | `timestamp with time zone` | ✓ | — | — | — |  |
| 12 | `auto_renew` | `boolean` | — | — | `true` | — |  |
| 13 | `grace_until` | `timestamp with time zone` | ✓ | — | — | — |  |
| 14 | `trial_ends_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 15 | `last_reminder_days` | `integer` | ✓ | — | — | — |  |

### `tenant_usage_daily` — 5 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `tenant_id` | `text` | — | PK FK | — | `tenants.tenant_id` |  |
| 2 | `usage_date` | `date` | — | PK | — | — |  |
| 3 | `metric` | `text` | — | PK | — | — |  |
| 4 | `value` | `bigint` | — | — | `0` | — |  |
| 5 | `computed_at` | `timestamp with time zone` | — | — | `now()` | — |  |

## H. Integration & Operations

### `event_outbox` — 11 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `event_id` | `uuid` | — | PK | `gen_random_uuid()` | — |  |
| 2 | `tenant_id` | `text` | ✓ | FK | — | `tenants.tenant_id` |  |
| 3 | `event_type_code` | `text` | — | — | — | — |  |
| 4 | `payload` | `jsonb` | — | — | `'{}'::jsonb` | — |  |
| 5 | `occurred_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 6 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 7 | `dispatch_status` | `text` | — | — | `'PENDING'::text` | — |  |
| 8 | `attempts` | `integer` | — | — | `0` | — |  |
| 9 | `available_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 10 | `processed_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 11 | `last_error` | `text` | ✓ | — | — | — |  |

### `google_sheets_sync_status` — 7 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `id` | `integer` | — | PK | `nextval('google_sheets_sync_status_id_seq'::`… | — |  |
| 2 | `table_name` | `character varying(50)` | — | — | — | — |  |
| 3 | `current_spreadsheet_id` | `character varying(100)` | — | — | `''::character varying` | — |  |
| 4 | `current_sheet_index` | `integer` | — | — | `1` | — |  |
| 5 | `current_data_rows` | `integer` | — | — | `0` | — |  |
| 6 | `max_rows_per_sheet` | `integer` | — | — | `500000` | — |  |
| 7 | `updated_at` | `timestamp with time zone` | ✓ | — | `now()` | — |  |

### `notifications` — 10 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `notification_id` | `uuid` | — | PK | `gen_random_uuid()` | — |  |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` |  |
| 3 | `user_id` | `uuid` | — | FK | — | `users.id` |  |
| 4 | `kind` | `text` | — | — | — | — |  |
| 5 | `title` | `text` | — | — | — | — |  |
| 6 | `body` | `text` | — | — | `''::text` | — |  |
| 7 | `link` | `text` | ✓ | — | — | — |  |
| 8 | `severity` | `text` | — | — | `'info'::text` | — |  |
| 9 | `read_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 10 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |

### `platform_settings` — 4 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `key` | `text` | — | PK | — | — |  |
| 2 | `value` | `text` | — | — | — | — |  |
| 3 | `updated_by` | `uuid` | ✓ | FK | — | `users.id` |  |
| 4 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — |  |

### `schema_migrations` — 6 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `version` | `integer` | — | PK | — | — |  |
| 2 | `applied_at` | `timestamp with time zone` | — | PK | `now()` | — |  |
| 3 | `applied_by` | `text` | — | — | — | — |  |
| 4 | `applied_on` | `text` | ✓ | — | — | — |  |
| 5 | `note` | `text` | ✓ | — | — | — |  |
| 6 | `migration_checksum` | `text` | ✓ | — | — | — |  |

### `support_messages` — 9 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `message_id` | `uuid` | — | PK | `gen_random_uuid()` | — |  |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` |  |
| 3 | `ticket_id` | `uuid` | — | FK | — | `support_tickets.ticket_id` |  |
| 4 | `author_id` | `uuid` | ✓ | FK | — | `users.id` |  |
| 5 | `author_label` | `text` | — | — | — | — |  |
| 6 | `is_staff` | `boolean` | — | — | `false` | — |  |
| 7 | `body` | `text` | — | — | — | — |  |
| 8 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 9 | `author_kind` | `text` | ✓ | — | `'user'::text` | — |  |

### `support_tickets` — 10 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `ticket_id` | `uuid` | — | PK | `gen_random_uuid()` | — |  |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` |  |
| 3 | `user_id` | `uuid` | ✓ | FK | — | `users.id` |  |
| 4 | `subject` | `text` | — | — | — | — |  |
| 5 | `category` | `text` | — | — | `'other'::text` | — |  |
| 6 | `status` | `text` | — | — | `'open'::text` | — |  |
| 7 | `priority` | `text` | — | — | `'normal'::text` | — |  |
| 8 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 9 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 10 | `resolved_at` | `timestamp with time zone` | ✓ | — | — | — |  |

### `webhook_deliveries` — 12 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `delivery_id` | `uuid` | — | PK | — | — |  |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` |  |
| 3 | `endpoint_id` | `uuid` | — | FK | — | `webhook_endpoints.endpoint_id` |  |
| 4 | `event_type` | `text` | — | — | — | — |  |
| 5 | `payload` | `jsonb` | — | — | — | — |  |
| 6 | `status` | `text` | — | — | `'pending'::text` | — |  |
| 7 | `attempts` | `integer` | — | — | `0` | — |  |
| 8 | `last_status_code` | `integer` | ✓ | — | — | — |  |
| 9 | `last_error` | `text` | ✓ | — | — | — |  |
| 10 | `next_attempt_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 11 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 12 | `delivered_at` | `timestamp with time zone` | ✓ | — | — | — |  |

### `webhook_endpoints` — 14 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `endpoint_id` | `uuid` | — | PK | — | — |  |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` |  |
| 3 | `url` | `text` | — | — | — | — |  |
| 4 | `secret` | `text` | — | — | — | — |  |
| 5 | `event_types` | `text` | — | — | `'*'::text` | — |  |
| 6 | `is_active` | `boolean` | — | — | `true` | — |  |
| 7 | `description` | `text` | — | — | `''::text` | — |  |
| 8 | `created_by` | `uuid` | ✓ | FK | — | `users.id` |  |
| 9 | `created_at` | `timestamp with time zone` | — | — | `now()` | — |  |
| 10 | `last_success_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 11 | `last_failure_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 12 | `failure_streak` | `integer` | — | — | `0` | — |  |
| 13 | `disabled_at` | `timestamp with time zone` | ✓ | — | — | — |  |
| 14 | `disabled_reason` | `text` | ✓ | — | — | — |  |

---

# C.8.2 — Ràng buộc toàn vẹn

## C.8.2.a — CHECK

68 ràng buộc, trong đó **18** phủ nhiều cột.

| Bảng | Ràng buộc | Cột | Phạm vi | Quy tắc |
|---|---|---|---|---|
| `audit_log` | `audit_log_action_not_blank` | `action` | một cột | `CHECK ((action <> ''::text))` |
| `capture_sessions` | `capture_sessions_ends_after_start` | `started_at+ended_at` | **nhiều cột** | `CHECK (((ended_at IS NULL) OR (started_at IS NULL) OR (ended_at >= started_at)))` |
| `capture_sessions` | `capture_sessions_session_id_not_blank` | `session_id` | một cột | `CHECK ((session_id <> ''::text))` |
| `collection_sessions` | `collection_sessions_code_not_blank` | `session_code` | một cột | `CHECK ((session_code <> ''::text))` |
| `collection_sessions` | `collection_sessions_ends_after_start` | `started_at+ended_at` | **nhiều cột** | `CHECK (((ended_at IS NULL) OR (started_at IS NULL) OR (ended_at >= started_at)))` |
| `event_outbox` | `ck_event_outbox_attempts` | `attempts` | một cột | `CHECK ((attempts >= 0))` |
| `event_outbox` | `ck_event_outbox_status` | `dispatch_status` | một cột | `CHECK ((dispatch_status = ANY (ARRAY['PENDING'::text, 'IN_FLIGHT'::text, 'DONE'::text, 'FAILED'::text])))` |
| `event_outbox` | `ck_event_outbox_type_not_blank` | `event_type_code` | một cột | `CHECK ((event_type_code <> ''::text))` |
| `legal_document_drafts` | `ck_legal_drafts_kind` | `kind` | một cột | `CHECK ((kind = ANY (ARRAY['terms'::text, 'privacy'::text, 'data_contribution'::text, 'guardian'::text])))` |
| `legal_document_drafts` | `ck_legal_drafts_revision` | `revision` | một cột | `CHECK ((revision >= 1))` |
| `legal_document_drafts` | `ck_legal_drafts_status` | `status` | một cột | `CHECK ((status = ANY (ARRAY['draft'::text, 'in_review'::text, 'approved'::text, 'published'::text, 'discarded'::text])))` |
| `legal_document_events` | `ck_legal_events_action_not_blank` | `action` | một cột | `CHECK ((action <> ''::text))` |
| `legal_documents` | `ck_legal_documents_body_format` | `body_format` | một cột | `CHECK ((body_format = ANY (ARRAY['markdown'::text, 'text'::text, 'file'::text])))` |
| `legal_documents` | `ck_legal_documents_file_pair` | `body_format+file_key` | **nhiều cột** | `CHECK (((body_format = 'file'::text) = (file_key IS NOT NULL)))` |
| `legal_documents` | `legal_documents_kind_valid` | `kind` | một cột | `CHECK ((kind = ANY (ARRAY['terms'::text, 'privacy'::text, 'data_contribution'::text, 'guardian'::text])))` |
| `memberships` | `ck_memberships_left_consistent` | `status+left_at` | **nhiều cột** | `CHECK (((status = 'REMOVED'::text) = (left_at IS NOT NULL)))` |
| `memberships` | `ck_memberships_legacy_role_tenant_only` | `scope_level+legacy_role` | **nhiều cột** | `CHECK (((scope_level = 'TENANT'::text) OR (legacy_role IS NULL)))` |
| `memberships` | `ck_memberships_legacy_role_valid` | `legacy_role` | một cột | `CHECK (((legacy_role IS NULL) OR (legacy_role = ANY (ARRAY['admin'::text, 'editor'::text]))))` |
| `memberships` | `ck_memberships_scope_level` | `scope_level` | một cột | `CHECK ((scope_level = ANY (ARRAY['TENANT'::text, 'WORKSPACE'::text, 'PROJECT'::text])))` |
| `memberships` | `ck_memberships_shape` | `scope_level+workspace_id+project_id` | **nhiều cột** | `CHECK ((((scope_level = 'TENANT'::text) AND (workspace_id IS NULL) AND (project_id IS NULL)) OR ((scope_level = 'WORKSPACE'::text) AND (workspace_id IS NOT NULL) AND (project_id IS NULL)) OR ((scope_level = 'PROJECT'::text) AND (workspace_id IS NOT NULL) AND (project_id IS NOT NULL))))` |
| `memberships` | `ck_memberships_status` | `status` | một cột | `CHECK ((status = ANY (ARRAY['ACTIVE'::text, 'INVITED'::text, 'SUSPENDED'::text, 'REMOVED'::text])))` |
| `notifications` | `notifications_severity_valid` | `severity` | một cột | `CHECK ((severity = ANY (ARRAY['info'::text, 'success'::text, 'warning'::text, 'critical'::text])))` |
| `permissions` | `ck_permissions_code_shape` | `permission_code` | một cột | `CHECK ((permission_code ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$'::text))` |
| `permissions` | `ck_permissions_risk` | `risk_level` | một cột | `CHECK ((risk_level = ANY (ARRAY['NORMAL'::text, 'SENSITIVE'::text, 'CRITICAL'::text])))` |
| `permissions` | `ck_permissions_scope` | `applicable_scope` | một cột | `CHECK ((applicable_scope = ANY (ARRAY['SYSTEM'::text, 'TENANT'::text, 'WORKSPACE'::text, 'PROJECT'::text])))` |
| `permissions` | `ck_permissions_system_not_api_assignable` | `applicable_scope+is_api_assignable` | **nhiều cột** | `CHECK ((NOT ((applicable_scope = 'SYSTEM'::text) AND is_api_assignable)))` |
| `permissions` | `ck_permissions_system_not_custom_role` | `applicable_scope+is_custom_role_allowed` | **nhiều cột** | `CHECK ((NOT ((applicable_scope = 'SYSTEM'::text) AND is_custom_role_allowed)))` |
| `plans` | `ck_plans_billing_period` | `billing_period` | một cột | `CHECK ((billing_period = ANY (ARRAY['monthly'::text, 'yearly'::text, 'none'::text])))` |
| `plans` | `ck_plans_limits_non_negative` | `max_seats+max_samples+max_storage_mb+max_classes+max_training_jobs_per_month+max_concurrent_training_jobs+max_queued_training_jobs+max_api_keys+max_webhook_endpoints+price_cents+trial_days` | **nhiều cột** | `CHECK (((COALESCE(max_seats, 0) >= 0) AND (COALESCE(max_samples, 0) >= 0) AND (COALESCE(max_storage_mb, 0) >= 0) AND (COALESCE(max_classes, 0) >= 0) AND (COALESCE(max_training_jobs_per_month, 0) >= 0) AND (max_concurrent_training_jobs >= 0) AND (max_queued_training_jobs >= 0) AND (max_api_keys >= 0) AND (max_webhook_endpoints >= 0) AND (price_cents >= 0) AND (trial_days >= 0)))` |
| `plans` | `ck_plans_v6_limits_non_negative` | `max_workspaces+max_projects+included_training_credits+audit_retention_days` | **nhiều cột** | `CHECK (((COALESCE(max_workspaces, 0) >= 0) AND (COALESCE(max_projects, 0) >= 0) AND (COALESCE(included_training_credits, 0) >= 0) AND (COALESCE(audit_retention_days, 0) >= 0)))` |
| `project_allocations` | `ck_project_allocations_nonneg` | `allocated` | một cột | `CHECK (((allocated IS NULL) OR (allocated >= 0)))` |
| `projects` | `ck_projects_status` | `status` | một cột | `CHECK ((status = ANY (ARRAY['ACTIVE'::text, 'ARCHIVED'::text, 'DELETED'::text])))` |
| `role_assignments` | `ck_role_assignments_revoked_consistent` | `revoked_by_user_id+revoked_at` | **nhiều cột** | `CHECK (((revoked_by_user_id IS NULL) OR (revoked_at IS NOT NULL)))` |
| `roles` | `ck_role_ownership` | `tenant_id+scope_level+is_builtin` | **nhiều cột** | `CHECK (((is_builtin AND (tenant_id IS NULL)) OR ((NOT is_builtin) AND (tenant_id IS NOT NULL) AND (scope_level <> 'SYSTEM'::text))))` |
| `roles` | `ck_roles_scope_level` | `scope_level` | một cột | `CHECK ((scope_level = ANY (ARRAY['SYSTEM'::text, 'TENANT'::text, 'WORKSPACE'::text, 'PROJECT'::text])))` |
| `roles` | `ck_roles_system_is_platform_owned` | `tenant_id+scope_level` | **nhiều cột** | `CHECK (((scope_level <> 'SYSTEM'::text) OR (tenant_id IS NULL)))` |
| `roles` | `ck_roles_tenant_type_constraint` | `tenant_type_constraint` | một cột | `CHECK (((tenant_type_constraint IS NULL) OR (tenant_type_constraint = ANY (ARRAY['COMMUNITY'::text, 'ORGANIZATION'::text]))))` |
| `samples` | `ck_samples_review_status` | `review_status` | một cột | `CHECK ((review_status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text])))` |
| `samples` | `samples_file_path_is_local` | `file_path` | một cột | `CHECK (((file_path IS NULL) OR (file_path !~~ 'http%'::text)))` |
| `samples` | `samples_uid_is_hex10` | `sample_uid` | một cột | `CHECK ((sample_uid ~ '^[0-9a-f]{10}$'::text))` |
| `signer_aliases` | `signer_aliases_not_self` | `old_signer_id+new_signer_id` | **nhiều cột** | `CHECK ((old_signer_id <> new_signer_id))` |
| `signer_consents` | `signer_consents_scope_valid` | `scope` | một cột | `CHECK ((scope = ANY (ARRAY['internal_training'::text, 'research_release'::text, 'public_library'::text])))` |
| `signer_consents` | `signer_consents_withdraw_after_grant` | `granted_at+withdrawn_at` | **nhiều cột** | `CHECK (((withdrawn_at IS NULL) OR (withdrawn_at >= granted_at)))` |
| `storage_reservations` | `ck_storage_reservations_not_negative` | `bytes` | một cột | `CHECK ((bytes >= 0))` |
| `support_messages` | `ck_support_author_kind` | `author_kind` | một cột | `CHECK ((author_kind = ANY (ARRAY['user'::text, 'staff'::text, 'bot'::text])))` |
| `support_messages` | `ck_support_author_kind_matches` | `is_staff+author_kind` | **nhiều cột** | `CHECK (((author_kind = 'staff'::text) = is_staff))` |
| `support_tickets` | `support_tickets_category_valid` | `category` | một cột | `CHECK ((category = ANY (ARRAY['account'::text, 'billing'::text, 'data'::text, 'bug'::text, 'other'::text])))` |
| `support_tickets` | `support_tickets_priority_valid` | `priority` | một cột | `CHECK ((priority = ANY (ARRAY['low'::text, 'normal'::text, 'high'::text, 'urgent'::text])))` |
| `support_tickets` | `support_tickets_status_valid` | `status` | một cột | `CHECK ((status = ANY (ARRAY['open'::text, 'pending'::text, 'resolved'::text, 'closed'::text])))` |
| `tenant_exports` | `ck_tenant_exports_purpose` | `export_purpose` | một cột | `CHECK ((export_purpose = ANY (ARRAY['tenant_portability'::text, 'internal_training'::text, 'research_release'::text, 'public_library'::text])))` |
| `tenant_exports` | `ck_tenant_exports_scope` | `scope` | một cột | `CHECK ((scope = ANY (ARRAY['metadata'::text, 'full'::text])))` |
| `tenant_exports` | `ck_tenant_exports_status` | `status` | một cột | `CHECK ((status = ANY (ARRAY['pending'::text, 'running'::text, 'ready'::text, 'failed'::text, 'expired'::text])))` |
| `tenant_invitations` | `tenant_invitations_accept_is_complete` | `accepted_at+accepted_by` | **nhiều cột** | `CHECK (((accepted_by IS NULL) OR (accepted_at IS NOT NULL)))` |
| `tenant_invitations` | `tenant_invitations_email_lower` | `email` | một cột | `CHECK ((email = lower(email)))` |
| `tenant_invitations` | `tenant_invitations_role_valid` | `role` | một cột | `CHECK (((role IS NULL) OR (role = ANY (ARRAY['admin'::text, 'editor'::text]))))` |
| `tenant_storage` | `ck_tenant_storage_not_negative` | `bytes_used` | một cột | `CHECK ((bytes_used >= 0))` |
| `tenants` | `ck_tenants_billing_status` | `billing_status` | một cột | `CHECK ((billing_status = ANY (ARRAY['trialing'::text, 'active'::text, 'past_due'::text, 'suspended'::text, 'cancelled'::text])))` |
| `tenants` | `ck_tenants_type` | `tenant_type` | một cột | `CHECK ((tenant_type = ANY (ARRAY['COMMUNITY'::text, 'ORGANIZATION'::text])))` |
| `user_action_passcodes` | `ck_user_action_passcodes_failed_count` | `failed_count` | một cột | `CHECK ((failed_count >= 0))` |
| `user_action_passcodes` | `ck_user_action_passcodes_status` | `status` | một cột | `CHECK ((status = ANY (ARRAY['ACTIVE'::text, 'LOCKED'::text, 'REVOKED'::text])))` |
| `user_consents` | `ck_user_consents_source` | `source` | một cột | `CHECK ((source = ANY (ARRAY['user'::text, 'backfill'::text, 'import'::text])))` |
| `users` | `users_email_lower` | `email` | một cột | `CHECK ((email = lower(email)))` |
| `verification_codes` | `verification_codes_attempts_bounded` | `attempts+max_attempts` | **nhiều cột** | `CHECK (((attempts >= 0) AND (attempts <= max_attempts)))` |
| `verification_codes` | `verification_codes_channel_valid` | `channel` | một cột | `CHECK ((channel = ANY (ARRAY['email'::text, 'sms'::text])))` |
| `verification_codes` | `verification_codes_purpose_valid` | `purpose` | một cột | `CHECK ((purpose = ANY (ARRAY['verify_email'::text, 'verify_phone'::text, 'reset_password'::text])))` |
| `vocabulary_groups` | `vocabulary_groups_id_not_blank` | `group_id` | một cột | `CHECK ((group_id <> ''::text))` |
| `webhook_deliveries` | `ck_webhook_deliveries_status` | `status` | một cột | `CHECK ((status = ANY (ARRAY['pending'::text, 'delivered'::text, 'failed'::text, 'dropped'::text])))` |
| `workspaces` | `ck_workspaces_status` | `status` | một cột | `CHECK ((status = ANY (ARRAY['ACTIVE'::text, 'ARCHIVED'::text, 'DELETED'::text])))` |

## C.8.2.b — Khoá chính, UNIQUE và chỉ mục duy nhất

Cột `Điều kiện` là vị từ của chỉ mục **một phần**: bất biến chỉ áp cho các
hàng thoả vị từ ấy. Đây là nhóm mà một lượt truy `pg_constraint` sẽ bỏ sót
hoàn toàn — 22 trong số đó.

| Bảng | Đối tượng | Loại | Cột | Điều kiện |
|---|---|---|---|---|
| `api_keys` | `api_keys_pkey` | PRIMARY KEY | `key_id` | — |
| `api_keys` | `api_keys_prefix_key` | UNIQUE CONSTRAINT | `prefix` | — |
| `audit_log` | `audit_log_pkey` | PRIMARY KEY | `audit_id` | — |
| `capture_sessions` | `capture_sessions_pkey` | PRIMARY KEY | `capture_session_id` | — |
| `capture_sessions` | `uq_capture_sessions_natural` | UNIQUE CONSTRAINT | `tenant_id+class_uid+session_id` | — |
| `capture_sessions` | `uq_capture_sessions_tenant` | UNIQUE CONSTRAINT | `tenant_id+capture_session_id` | — |
| `classes` | `classes_pkey` | PRIMARY KEY | `class_uid` | — |
| `classes` | `uq_classes_tenant_class_uid` | UNIQUE INDEX | `tenant_id+class_uid` | — |
| `classes` | `uq_classes_tenant_class_idx` | UNIQUE INDEX (MOT PHAN) | `tenant_id+class_idx` | `((deleted_at IS NULL) AND (class_idx IS NOT NULL))` |
| `classes` | `uq_classes_tenant_slug_lang_dialect_region` | UNIQUE INDEX (MOT PHAN) | `tenant_id+slug+language+dialect+region` | `(deleted_at IS NULL)` |
| `collection_sessions` | `collection_sessions_pkey` | PRIMARY KEY | `collection_session_id` | — |
| `collection_sessions` | `uq_collection_sessions_natural` | UNIQUE CONSTRAINT | `tenant_id+session_code` | — |
| `collection_sessions` | `uq_collection_sessions_tenant` | UNIQUE CONSTRAINT | `tenant_id+collection_session_id` | — |
| `community_dialects` | `community_dialects_pkey` | PRIMARY KEY | `dialect_id` | — |
| `community_profiles` | `community_profiles_pkey` | PRIMARY KEY | `profile_id` | — |
| `community_versions` | `community_versions_pkey` | PRIMARY KEY | `version` | — |
| `dialect_aliases` | `dialect_aliases_pkey` | PRIMARY KEY | `tenant_id+old_dialect_id` | — |
| `dialects` | `dialects_pkey` | PRIMARY KEY | `tenant_id+dialect_id` | — |
| `event_outbox` | `event_outbox_pkey` | PRIMARY KEY | `event_id` | — |
| `google_sheets_sync_status` | `google_sheets_sync_status_pkey` | PRIMARY KEY | `id` | — |
| `google_sheets_sync_status` | `google_sheets_sync_status_table_name_key` | UNIQUE CONSTRAINT | `table_name` | — |
| `languages` | `languages_pkey` | PRIMARY KEY | `code` | — |
| `legal_document_drafts` | `legal_document_drafts_pkey` | PRIMARY KEY | `draft_id` | — |
| `legal_document_drafts` | `uq_legal_draft_open` | UNIQUE INDEX (MOT PHAN) | `kind` | `(status = ANY (ARRAY['draft'::text, 'in_review'::text, 'approved'::text]))` |
| `legal_document_events` | `legal_document_events_pkey` | PRIMARY KEY | `event_id` | — |
| `legal_documents` | `legal_documents_pkey` | PRIMARY KEY | `doc_id` | — |
| `legal_documents` | `legal_documents_kind_version_unique` | UNIQUE CONSTRAINT | `kind+version` | — |
| `legal_documents` | `uq_legal_effective` | UNIQUE INDEX | `kind+effective_from` | — |
| `memberships` | `memberships_pkey` | PRIMARY KEY | `membership_id` | — |
| `memberships` | `uq_memberships_id_user` | UNIQUE CONSTRAINT | `membership_id+user_id` | — |
| `memberships` | `uq_memberships_project_user` | UNIQUE INDEX (MOT PHAN) | `tenant_id+project_id+user_id` | `(scope_level = 'PROJECT'::text)` |
| `memberships` | `uq_memberships_tenant_user` | UNIQUE INDEX (MOT PHAN) | `tenant_id+user_id` | `(scope_level = 'TENANT'::text)` |
| `memberships` | `uq_memberships_workspace_user` | UNIQUE INDEX (MOT PHAN) | `tenant_id+workspace_id+user_id` | `(scope_level = 'WORKSPACE'::text)` |
| `notifications` | `notifications_pkey` | PRIMARY KEY | `notification_id` | — |
| `password_reset_tokens` | `password_reset_tokens_pkey` | PRIMARY KEY | `token_hash` | — |
| `permissions` | `permissions_pkey` | PRIMARY KEY | `permission_code` | — |
| `plans` | `plans_pkey` | PRIMARY KEY | `plan_code` | — |
| `platform_settings` | `platform_settings_pkey` | PRIMARY KEY | `key` | — |
| `project_allocations` | `project_allocations_pkey` | PRIMARY KEY | `tenant_id+project_id+metric` | — |
| `projects` | `projects_pkey` | PRIMARY KEY | `project_id` | — |
| `projects` | `uq_projects_tenant_scope` | UNIQUE CONSTRAINT | `tenant_id+project_id` | — |
| `projects` | `uq_projects_workspace_scope` | UNIQUE CONSTRAINT | `tenant_id+workspace_id+project_id` | — |
| `projects` | `uq_projects_default_active` | UNIQUE INDEX (MOT PHAN) | `tenant_id+workspace_id` | `((is_default = true) AND (status = 'ACTIVE'::text) AND (deleted_at IS NULL))` |
| `projects` | `uq_projects_workspace_name` | UNIQUE INDEX (MOT PHAN) | `tenant_id+workspace_id+name` | `(deleted_at IS NULL)` |
| `raw_uploads` | `raw_uploads_pkey` | PRIMARY KEY | `upload_uid` | — |
| `recognition_profiles` | `recognition_profiles_pkey` | PRIMARY KEY | `tenant_id+profile_id` | — |
| `refresh_tokens` | `refresh_tokens_pkey` | PRIMARY KEY | `token_hash` | — |
| `regions` | `regions_pkey` | PRIMARY KEY | `code` | — |
| `registry_versions` | `registry_versions_pkey` | PRIMARY KEY | `tenant_id+version` | — |
| `role_assignments` | `role_assignments_pkey` | PRIMARY KEY | `assignment_id` | — |
| `role_assignments` | `uq_role_assignments_scoped` | UNIQUE INDEX (MOT PHAN) | `membership_id+role_id` | `((membership_id IS NOT NULL) AND (revoked_at IS NULL))` |
| `role_assignments` | `uq_role_assignments_system` | UNIQUE INDEX (MOT PHAN) | `user_id+role_id` | `((membership_id IS NULL) AND (revoked_at IS NULL))` |
| `role_permissions` | `pk_role_permissions` | PRIMARY KEY | `role_id+permission_code` | — |
| `roles` | `roles_pkey` | PRIMARY KEY | `role_id` | — |
| `roles` | `uq_roles_tenant_scope_key` | UNIQUE CONSTRAINT | `role_id+scope_level` | — |
| `roles` | `uq_roles_builtin_code` | UNIQUE INDEX (MOT PHAN) | `role_code` | `(tenant_id IS NULL)` |
| `roles` | `uq_roles_custom_code` | UNIQUE INDEX (MOT PHAN) | `tenant_id+role_code` | `(tenant_id IS NOT NULL)` |
| `roles` | `uq_roles_platform_scope_name` | UNIQUE INDEX (MOT PHAN) | `scope_level+role_code` | `(tenant_id IS NULL)` |
| `roles` | `uq_roles_tenant_scope_name` | UNIQUE INDEX (MOT PHAN) | `tenant_id+scope_level+role_code` | `(tenant_id IS NOT NULL)` |
| `samples` | `samples_pkey` | PRIMARY KEY | `sample_uid` | — |
| `schema_migrations` | `schema_migrations_pkey` | PRIMARY KEY | `version+applied_at` | — |
| `signer_aliases` | `signer_aliases_pkey` | PRIMARY KEY | `tenant_id+old_signer_id` | — |
| `signer_consents` | `signer_consents_pkey` | PRIMARY KEY | `consent_id` | — |
| `signer_consents` | `uq_signer_consents_live` | UNIQUE INDEX (MOT PHAN) | `tenant_id+signer_id+scope` | `(withdrawn_at IS NULL)` |
| `signers` | `signers_pkey` | PRIMARY KEY | `signer_id` | — |
| `signers` | `uq_signers_tenant_signer_id` | UNIQUE INDEX | `tenant_id+signer_id` | — |
| `sot_authorized_keys` | `sot_authorized_keys_pkey` | PRIMARY KEY | `public_key` | — |
| `sot_authorized_keys` | `sot_authorized_keys_name_key` | UNIQUE CONSTRAINT | `name` | — |
| `storage_reservations` | `storage_reservations_pkey` | PRIMARY KEY | `reservation_id` | — |
| `support_messages` | `support_messages_pkey` | PRIMARY KEY | `message_id` | — |
| `support_tickets` | `support_tickets_pkey` | PRIMARY KEY | `ticket_id` | — |
| `tenant_exports` | `tenant_exports_pkey` | PRIMARY KEY | `export_id` | — |
| `tenant_invitations` | `tenant_invitations_pkey` | PRIMARY KEY | `invitation_id` | — |
| `tenant_invitations` | `tenant_invitations_token_hash_key` | UNIQUE CONSTRAINT | `token_hash` | — |
| `tenant_invitations` | `uq_tenant_invitations_open` | UNIQUE INDEX (MOT PHAN) | `tenant_id+email` | `((accepted_at IS NULL) AND (revoked_at IS NULL))` |
| `tenant_purges` | `tenant_purges_pkey` | PRIMARY KEY | `purge_id` | — |
| `tenant_storage` | `tenant_storage_pkey` | PRIMARY KEY | `tenant_id` | — |
| `tenant_subscriptions` | `tenant_subscriptions_pkey` | PRIMARY KEY | `subscription_id` | — |
| `tenant_subscriptions` | `uq_tenant_subscriptions_open` | UNIQUE INDEX (MOT PHAN) | `tenant_id` | `(ended_at IS NULL)` |
| `tenant_usage_daily` | `tenant_usage_daily_pkey` | PRIMARY KEY | `tenant_id+usage_date+metric` | — |
| `tenants` | `tenants_pkey` | PRIMARY KEY | `tenant_id` | — |
| `tenants` | `tenants_slug_key` | UNIQUE CONSTRAINT | `slug` | — |
| `tenants` | `uq_tenants_single_community` | UNIQUE INDEX (MOT PHAN) | `tenant_type` | `(tenant_type = 'COMMUNITY'::text)` |
| `training_job_classes` | `training_job_classes_pkey` | PRIMARY KEY | `job_id+class_idx` | — |
| `training_jobs` | `training_jobs_pkey` | PRIMARY KEY | `job_id` | — |
| `training_jobs` | `uq_training_jobs_tenant_job` | UNIQUE CONSTRAINT | `tenant_id+job_id` | — |
| `training_metrics` | `training_metrics_pkey` | PRIMARY KEY | `job_id+epoch` | — |
| `user_action_passcodes` | `user_action_passcodes_pkey` | PRIMARY KEY | `user_id` | — |
| `user_consents` | `user_consents_pkey` | PRIMARY KEY | `consent_id` | — |
| `user_consents` | `uq_consent_live` | UNIQUE INDEX (MOT PHAN) | `user_id+kind` | `(withdrawn_at IS NULL)` |
| `user_recovery_codes` | `user_recovery_codes_pkey` | PRIMARY KEY | `code_hash` | — |
| `user_totp` | `user_totp_pkey` | PRIMARY KEY | `user_id` | — |
| `users` | `users_pkey` | PRIMARY KEY | `id` | — |
| `users` | `users_email_key` | UNIQUE CONSTRAINT | `email` | — |
| `users` | `users_phone_number_key` | UNIQUE CONSTRAINT | `phone_number` | — |
| `users` | `users_username_key` | UNIQUE CONSTRAINT | `username` | — |
| `users` | `uq_users_tenant_email` | UNIQUE INDEX | `tenant_id+email` | — |
| `users` | `uq_users_tenant_username` | UNIQUE INDEX | `tenant_id+username` | — |
| `verification_codes` | `verification_codes_pkey` | PRIMARY KEY | `challenge_id` | — |
| `verification_codes` | `uq_verification_codes_live` | UNIQUE INDEX (MOT PHAN) | `user_id+purpose` | `(consumed_at IS NULL)` |
| `vocabulary_groups` | `vocabulary_groups_pkey` | PRIMARY KEY | `tenant_id+group_id` | — |
| `vocabulary_registry_meta` | `vocabulary_registry_meta_pkey` | PRIMARY KEY | `tenant_id` | — |
| `webhook_deliveries` | `webhook_deliveries_pkey` | PRIMARY KEY | `delivery_id` | — |
| `webhook_endpoints` | `webhook_endpoints_pkey` | PRIMARY KEY | `endpoint_id` | — |
| `workspaces` | `workspaces_pkey` | PRIMARY KEY | `workspace_id` | — |
| `workspaces` | `uq_workspaces_tenant_scope` | UNIQUE CONSTRAINT | `tenant_id+workspace_id` | — |
| `workspaces` | `uq_workspaces_default_active` | UNIQUE INDEX (MOT PHAN) | `tenant_id` | `((is_default = true) AND (status = 'ACTIVE'::text) AND (deleted_at IS NULL))` |
| `workspaces` | `uq_workspaces_tenant_name` | UNIQUE INDEX (MOT PHAN) | `tenant_id+name` | `(deleted_at IS NULL)` |

## C.8.2.c — Khoá ngoại

131 khoá ngoại, trong đó **27** là khoá ghép.

| Con | Cột con | Cha | Cột cha | Cha | Con | ON DELETE | Ràng buộc |
|---|---|---|---|:--:|:--:|---|---|
| `api_keys` | `created_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `api_keys_created_by_fkey` |
| `api_keys` | `revoked_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `api_keys_revoked_by_fkey` |
| `api_keys` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_api_keys_tenant` |
| `audit_log` | `actor_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `audit_log_actor_user_id_fkey` |
| `audit_log` | `tenant_id` | `tenants` | `tenant_id` | 0..1 | 0..N | RESTRICT | `fk_audit_log_tenant` |
| `capture_sessions` | `auth_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `capture_sessions_auth_user_id_fkey` |
| `capture_sessions` | `tenant_id+class_uid` | `classes` | `tenant_id+class_uid` | 1 | 0..N | NO ACTION | `fk_capture_sessions_class` |
| `capture_sessions` | `tenant_id+collection_session_id` | `collection_sessions` | `tenant_id+collection_session_id` | 0..1 | 0..N | SET NULL | `fk_capture_sessions_collection` |
| `capture_sessions` | `tenant_id+signer_id` | `signers` | `tenant_id+signer_id` | 0..1 | 0..N | NO ACTION | `fk_capture_sessions_signer` |
| `capture_sessions` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_capture_sessions_tenant` |
| `classes` | `tenant_id+dialect` | `dialects` | `tenant_id+dialect_id` | 0..1 | 0..N | NO ACTION | `classes_dialect_fkey` |
| `classes` | `region` | `regions` | `code` | 1 | 0..N | NO ACTION | `classes_region_fkey` |
| `classes` | `language` | `languages` | `code` | 0..1 | 0..N | NO ACTION | `fk_classes_language` |
| `classes` | `tenant_id+recognition_profile` | `recognition_profiles` | `tenant_id+profile_id` | 0..1 | 0..N | NO ACTION | `fk_classes_recognition_profile` |
| `classes` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_classes_tenant` |
| `classes` | `tenant_id+vocabulary_group` | `vocabulary_groups` | `tenant_id+group_id` | 0..1 | 0..N | NO ACTION | `fk_classes_vocabulary_group` |
| `collection_sessions` | `opened_by_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `collection_sessions_opened_by_user_id_fkey` |
| `collection_sessions` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_collection_sessions_tenant` |
| `community_dialects` | `updated_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `community_dialects_updated_by_fkey` |
| `community_profiles` | `updated_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `community_profiles_updated_by_fkey` |
| `community_versions` | `created_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `community_versions_created_by_fkey` |
| `dialect_aliases` | `merged_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `dialect_aliases_merged_by_fkey` |
| `dialect_aliases` | `tenant_id+new_dialect_id` | `dialects` | `tenant_id+dialect_id` | 1 | 0..N | NO ACTION | `fk_dialect_aliases_new` |
| `dialect_aliases` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_dialect_aliases_tenant` |
| `dialects` | `approved_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `dialects_approved_by_fkey` |
| `dialects` | `created_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `dialects_created_by_fkey` |
| `dialects` | `language` | `languages` | `code` | 1 | 0..N | NO ACTION | `fk_dialects_language` |
| `dialects` | `tenant_id+merged_into` | `dialects` | `tenant_id+dialect_id` | 0..1 | 0..N | NO ACTION | `fk_dialects_merged_into` |
| `dialects` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_dialects_tenant` |
| `event_outbox` | `tenant_id` | `tenants` | `tenant_id` | 0..1 | 0..N | RESTRICT | `fk_event_outbox_tenant` |
| `legal_document_drafts` | `created_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `legal_document_drafts_created_by_fkey` |
| `legal_document_drafts` | `updated_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `legal_document_drafts_updated_by_fkey` |
| `legal_documents` | `published_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `legal_documents_published_by_fkey` |
| `memberships` | `parent_membership_id+user_id` | `memberships` | `membership_id+user_id` | 0..1 | 0..N | CASCADE | `fk_memberships_parent` |
| `memberships` | `tenant_id+workspace_id+project_id` | `projects` | `tenant_id+workspace_id+project_id` | 0..1 | 0..N | CASCADE | `fk_memberships_project` |
| `memberships` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_memberships_tenant` |
| `memberships` | `tenant_id+workspace_id` | `workspaces` | `tenant_id+workspace_id` | 0..1 | 0..N | CASCADE | `fk_memberships_workspace` |
| `memberships` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | CASCADE | `memberships_tenant_id_fkey` |
| `memberships` | `user_id` | `users` | `id` | 1 | 0..N | CASCADE | `memberships_user_id_fkey` |
| `notifications` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_notifications_tenant` |
| `notifications` | `user_id` | `users` | `id` | 1 | 0..N | CASCADE | `notifications_user_id_fkey` |
| `password_reset_tokens` | `user_id` | `users` | `id` | 1 | 0..N | CASCADE | `password_reset_tokens_user_id_fkey` |
| `platform_settings` | `updated_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `platform_settings_updated_by_fkey` |
| `project_allocations` | `tenant_id+project_id` | `projects` | `tenant_id+project_id` | 1 | 0..N | CASCADE | `fk_project_allocations_project` |
| `project_allocations` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_project_allocations_tenant` |
| `project_allocations` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | CASCADE | `project_allocations_tenant_id_fkey` |
| `project_allocations` | `updated_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `project_allocations_updated_by_fkey` |
| `projects` | `tenant_id+workspace_id` | `workspaces` | `tenant_id+workspace_id` | 1 | 0..N | RESTRICT | `fk_inv_ten_02_project_workspace` |
| `projects` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_projects_tenant` |
| `raw_uploads` | `tenant_id+class_uid` | `classes` | `tenant_id+class_uid` | 0..1 | 0..N | NO ACTION | `fk_raw_uploads_class_tenant` |
| `raw_uploads` | `tenant_id+dialect` | `dialects` | `tenant_id+dialect_id` | 0..1 | 0..N | NO ACTION | `fk_raw_uploads_dialect` |
| `raw_uploads` | `language` | `languages` | `code` | 0..1 | 0..N | NO ACTION | `fk_raw_uploads_language` |
| `raw_uploads` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_raw_uploads_tenant` |
| `raw_uploads` | `auth_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `raw_uploads_auth_user_id_fkey` |
| `recognition_profiles` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_recognition_profiles_tenant` |
| `refresh_tokens` | `user_id` | `users` | `id` | 1 | 0..N | CASCADE | `refresh_tokens_user_id_fkey` |
| `registry_versions` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_registry_versions_tenant` |
| `registry_versions` | `created_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `registry_versions_created_by_fkey` |
| `role_assignments` | `membership_id+user_id` | `memberships` | `membership_id+user_id` | 0..1 | 0..N | CASCADE | `fk_role_assignments_membership` |
| `role_assignments` | `assigned_by_user_id` | `users` | `id` | 1 | 0..N | RESTRICT | `role_assignments_assigned_by_user_id_fkey` |
| `role_assignments` | `revoked_by_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `role_assignments_revoked_by_user_id_fkey` |
| `role_assignments` | `role_id` | `roles` | `role_id` | 1 | 0..N | RESTRICT | `role_assignments_role_id_fkey` |
| `role_assignments` | `user_id` | `users` | `id` | 1 | 0..N | CASCADE | `role_assignments_user_id_fkey` |
| `role_permissions` | `permission_code` | `permissions` | `permission_code` | 1 | 0..N | RESTRICT | `fk_role_permissions_permission` |
| `role_permissions` | `role_id` | `roles` | `role_id` | 1 | 0..N | CASCADE | `fk_role_permissions_role` |
| `roles` | `created_by_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `fk_roles_creator` |
| `roles` | `tenant_id` | `tenants` | `tenant_id` | 0..1 | 0..N | CASCADE | `fk_roles_tenant` |
| `samples` | `capture_session_id` | `capture_sessions` | `capture_session_id` | 0..1 | 0..N | SET NULL | `fk_samples_capture_session` |
| `samples` | `tenant_id+capture_session_id` | `capture_sessions` | `tenant_id+capture_session_id` | 0..1 | 0..N | SET NULL | `fk_samples_capture_session_tenant` |
| `samples` | `tenant_id+class_uid` | `classes` | `tenant_id+class_uid` | 0..1 | 0..N | NO ACTION | `fk_samples_class_tenant` |
| `samples` | `language` | `languages` | `code` | 0..1 | 0..N | NO ACTION | `fk_samples_language` |
| `samples` | `tenant_id+signer_id` | `signers` | `tenant_id+signer_id` | 0..1 | 0..N | NO ACTION | `fk_samples_signer` |
| `samples` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_samples_tenant` |
| `samples` | `auth_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `samples_auth_user_id_fkey` |
| `samples` | `class_uid` | `classes` | `class_uid` | 0..1 | 0..N | NO ACTION | `samples_class_uid_fkey` |
| `samples` | `tenant_id+dialect` | `dialects` | `tenant_id+dialect_id` | 0..1 | 0..N | NO ACTION | `samples_dialect_fkey` |
| `samples` | `reviewed_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `samples_reviewed_by_fkey` |
| `signer_aliases` | `tenant_id+new_signer_id` | `signers` | `tenant_id+signer_id` | 1 | 0..N | NO ACTION | `fk_signer_aliases_new` |
| `signer_aliases` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_signer_aliases_tenant` |
| `signer_aliases` | `merged_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `signer_aliases_merged_by_fkey` |
| `signer_consents` | `kind+version` | `legal_documents` | `kind+version` | 1 | 0..N | RESTRICT | `fk_signer_consents_document` |
| `signer_consents` | `tenant_id+signer_id` | `signers` | `tenant_id+signer_id` | 1 | 0..N | NO ACTION | `fk_signer_consents_signer` |
| `signer_consents` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_signer_consents_tenant` |
| `signer_consents` | `recorded_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `signer_consents_recorded_by_fkey` |
| `signers` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_signers_tenant` |
| `signers` | `external_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `fk_signers_user` |
| `storage_reservations` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_storage_reservations_tenant` |
| `support_messages` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_support_messages_tenant` |
| `support_messages` | `author_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `support_messages_author_id_fkey` |
| `support_messages` | `ticket_id` | `support_tickets` | `ticket_id` | 1 | 0..N | CASCADE | `support_messages_ticket_id_fkey` |
| `support_tickets` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_support_tickets_tenant` |
| `support_tickets` | `user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `support_tickets_user_id_fkey` |
| `tenant_exports` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_tenant_exports_tenant` |
| `tenant_exports` | `requested_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `tenant_exports_requested_by_fkey` |
| `tenant_invitations` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_tenant_invitations_tenant` |
| `tenant_invitations` | `accepted_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `tenant_invitations_accepted_by_fkey` |
| `tenant_invitations` | `invited_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `tenant_invitations_invited_by_fkey` |
| `tenant_storage` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..1 | RESTRICT | `fk_tenant_storage_tenant` |
| `tenant_subscriptions` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_tenant_subscriptions_tenant` |
| `tenant_subscriptions` | `changed_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `tenant_subscriptions_changed_by_fkey` |
| `tenant_subscriptions` | `plan_code` | `plans` | `plan_code` | 1 | 0..N | NO ACTION | `tenant_subscriptions_plan_code_fkey` |
| `tenant_usage_daily` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_tenant_usage_daily_tenant` |
| `tenants` | `cloned_from_community_version` | `community_versions` | `version` | 0..1 | 0..N | NO ACTION | `fk_tenants_cloned_version` |
| `tenants` | `owner_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `fk_tenants_owner_user` |
| `tenants` | `plan_code` | `plans` | `plan_code` | 1 | 0..N | RESTRICT | `fk_tenants_plan` |
| `training_job_classes` | `class_uid` | `classes` | `class_uid` | 0..1 | 0..N | SET NULL | `fk_training_job_classes_class` |
| `training_job_classes` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_training_job_classes_tenant` |
| `training_job_classes` | `job_id` | `training_jobs` | `job_id` | 1 | 0..N | CASCADE | `training_job_classes_job_id_fkey` |
| `training_jobs` | `tenant_id+registry_version` | `registry_versions` | `tenant_id+version` | 0..1 | 0..N | NO ACTION | `fk_training_jobs_registry` |
| `training_jobs` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_training_jobs_tenant` |
| `training_jobs` | `auth_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `training_jobs_auth_user_id_fkey` |
| `training_metrics` | `job_id` | `training_jobs` | `job_id` | 1 | 0..N | CASCADE | `fk_training_metrics_job` |
| `training_metrics` | `tenant_id+job_id` | `training_jobs` | `tenant_id+job_id` | 1 | 0..N | CASCADE | `fk_training_metrics_job_tenant` |
| `training_metrics` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_training_metrics_tenant` |
| `user_action_passcodes` | `user_id` | `users` | `id` | 1 | 0..1 | CASCADE | `user_action_passcodes_user_id_fkey` |
| `user_consents` | `kind+version` | `legal_documents` | `kind+version` | 1 | 0..N | RESTRICT | `user_consents_kind_version_fkey` |
| `user_consents` | `recorded_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `user_consents_recorded_by_fkey` |
| `user_consents` | `user_id` | `users` | `id` | 1 | 0..N | CASCADE | `user_consents_user_id_fkey` |
| `user_recovery_codes` | `user_id` | `users` | `id` | 1 | 0..N | CASCADE | `user_recovery_codes_user_id_fkey` |
| `user_totp` | `user_id` | `users` | `id` | 1 | 0..1 | CASCADE | `user_totp_user_id_fkey` |
| `users` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_users_tenant` |
| `users` | `role_id` | `roles` | `role_id` | 0..1 | 0..N | NO ACTION | `users_role_id_fkey` |
| `verification_codes` | `user_id` | `users` | `id` | 0..1 | 0..N | CASCADE | `verification_codes_user_id_fkey` |
| `vocabulary_groups` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_vocabulary_groups_tenant` |
| `vocabulary_registry_meta` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..1 | RESTRICT | `fk_vocabulary_registry_meta_tenant` |
| `vocabulary_registry_meta` | `tenant_id+version` | `registry_versions` | `tenant_id+version` | 0..1 | 0..1 | NO ACTION | `fk_vocabulary_registry_meta_version` |
| `webhook_deliveries` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_webhook_deliveries_tenant` |
| `webhook_deliveries` | `endpoint_id` | `webhook_endpoints` | `endpoint_id` | 1 | 0..N | CASCADE | `webhook_deliveries_endpoint_id_fkey` |
| `webhook_endpoints` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_webhook_endpoints_tenant` |
| `webhook_endpoints` | `created_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `webhook_endpoints_created_by_fkey` |
| `workspaces` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_workspaces_tenant` |

## C.8.3 — View

`tenant_members` là VIEW `security_invoker` trên `memberships`, 7 cột. Nó KHÔNG
nằm trong 660 cột ở trên (đó là cột của bảng). Ghi ở đây vì bỏ nó đi sẽ khiến
phụ lục im lặng về một đối tượng mà mã ứng dụng có đọc — và `security_invoker`
chính là thứ khiến mọi truy vấn qua view chịu đúng chính sách RLS của người
gọi. Gỡ thuộc tính ấy là mở toang view.
