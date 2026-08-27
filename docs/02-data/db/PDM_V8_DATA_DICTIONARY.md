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

**Mô tả nghiệp vụ phủ 660/660 cột — toàn bộ tám nhóm A–H.**

| trạng thái | số cột |
|---|---:|
| `VERIFIED` | 608 |
| `NEEDS_REVIEW` | 33 |
| `LEGACY` | 12 |
| `DERIVED` | 7 |

Mô tả KHÔNG đến từ catalog: cơ sở dữ liệu có **0** `COMMENT ON COLUMN` và
**0** `COMMENT ON TABLE`. Suy mô tả từ tên cột là bịa — người đọc không phân
biệt được một dòng lấy từ hệ thống với một dòng đoán ra. Vì vậy mô tả sống ở
`evidence/pdm_v8_descriptions.csv`, tách khỏi catalog, mỗi dòng mang nhãn:

* *(không nhãn)* — **VERIFIED**: có bằng chứng từ mã hoặc từ dữ liệu đã đo
* `LEGACY` — dấu vết lịch sử, KHÔNG phải nguồn chuẩn
* `DERIVED` — do pipeline tính ra, không do người nhập
* **`CẦN DUYỆT`** — cấu trúc vật lý đã xác thực từ catalog, nhưng **ý định
  nghiệp vụ** chưa đủ bằng chứng để khẳng định mạnh hơn

**`CẦN DUYỆT` KHÔNG có nghĩa là dữ liệu sai.** Kiểu, ràng buộc, khoá và
cardinality của những cột ấy lấy từ catalog như mọi cột khác; thứ còn thiếu
là một đường mã hoặc một quyết định thiết kế nói cột ấy DÙNG để làm gì. Mỗi
dòng như vậy đều ghi rõ thiếu bằng chứng nào — không dòng nào để trống lý do.

Chưa chạy `COMMENT ON` nào trên sản xuất: đó sẽ là DDL mới và kéo theo câu
hỏi phiên bản migration chỉ để phục vụ tài liệu.

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
| 3 | `scope_level` | `text` | — | — | `'TENANT'::text` | — | Mức phạm vi: TENANT, WORKSPACE hoặc PROJECT.<br><sub>Quyết định hai cột workspace_id/project_id phải NULL hay NOT NULL — xem ck_memberships_shape. Ràng buộc CÂY thì ở nơi khác: ct_memberships_chain (xem parent_membership_id) mới là thứ kiểm quan hệ cha-con giữa các tầng</sub> |
| 4 | `tenant_id` | `text` | — | FK | — | `(tenant_id, workspace_id, project_id)` → `projects(tenant_id, workspace_id, project_id)`<br>`(tenant_id, workspace_id)` → `workspaces(tenant_id, workspace_id)`<br>`tenants.tenant_id`<br>`tenants.tenant_id` | Tổ chức xác định phạm vi của tư cách thành viên.<br><sub>Cột chịu HAI khoá ngoại vật lý cùng trỏ tenants.tenant_id, một RESTRICT một CASCADE. Khác project_allocations, cặp này được tái tạo cả trên bản CÀI MỚI — xem docs/10-issues/KNOWN_ISSUES.md</sub> |
| 5 | `workspace_id` | `uuid` | ✓ | FK | — | `(tenant_id, workspace_id, project_id)` → `projects(tenant_id, workspace_id, project_id)`<br>`(tenant_id, workspace_id)` → `workspaces(tenant_id, workspace_id)` | Workspace của tư cách thành viên. NULL khi scope_level = TENANT; NOT NULL với WORKSPACE và PROJECT.<br><sub>ck_memberships_shape ràng ba cột thành đúng ba hình dạng hợp lệ</sub> |
| 6 | `project_id` | `uuid` | ✓ | FK | — | `(tenant_id, workspace_id, project_id)` → `projects(tenant_id, workspace_id, project_id)` | Project của tư cách thành viên. NOT NULL chỉ khi scope_level = PROJECT.<br><sub>Khoá ngoại ghép BA cột (tenant, workspace, project) nên không trỏ được sang project của workspace hay tổ chức khác</sub> |
| 7 | `parent_membership_id` | `uuid` | ✓ | FK | — | `(parent_membership_id, user_id)` → `memberships(membership_id, user_id)` | Tư cách thành viên cấp trên trong cây phạm vi, của CÙNG một người.<br><sub>Khoá ngoại ghép (parent_membership_id, user_id) bảo đảm cha thuộc CÙNG tài khoản. Constraint trigger ct_memberships_chain còn cưỡng chế bốn điều mà khoá ngoại không nói: (1) membership TENANT không được có cha, WORKSPACE/PROJECT bắt buộc có; (2) cha của WORKSPACE phải là TENANT, cha của PROJECT phải là WORKSPACE — đúng tầng liền trên; (3) với PROJECT, workspace_id của cha phải TRÙNG workspace_id của con — cùng NHÁNH, không chỉ cùng tổ chức; (4) một membership ACTIVE không được treo dưới cha đã thôi ACTIVE</sub> |
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
| 3 | `metric` | `text` | — | PK | — | — | Chỉ tiêu được chia: `samples`, `storage_mb` hoặc `training_jobs_per_month`.<br><sub>Ánh xạ sang cột gói qua workspace_admin.ALLOCATABLE_METRICS. Từ v8, chỉ `storage_mb` còn được cưỡng chế đối với MỨC SỬ DỤNG THỰC TẾ; `samples` và `training_jobs_per_month` vẫn phân bổ được theo trần khai báo của gói, nhưng mức sử dụng thực tế không còn bị hai trần ấy chặn</sub> |
| 4 | `allocated` | `bigint` | ✓ | — | — | — | Phần chỉ tiêu dành cho project này. NULL nghĩa là KHÔNG GIỚI HẠN, không phải chưa điền.<br><sub>Đường quản trị cấp phát (workspace_admin.set_project_allocation) kiểm tổng phần cấp cho các project không vượt trần khai báo tương ứng của gói, từ chối 409 nếu vượt; CHECK ở CSDL chỉ cấm giá trị âm</sub> |
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
| 7 | `is_default` | `boolean` | — | — | `false` | — | Project mặc định của workspace.<br><sub>Chỉ mục duy nhất MỘT PHẦN uq_projects_default_active: mỗi workspace có tối đa MỘT project vừa is_default = true, vừa status = 'ACTIVE', vừa chưa xoá mềm</sub> |
| 8 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo. |
| 9 | `archived_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm lưu trữ. |
| 10 | `deleted_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm xoá mềm. |

### `role_assignments` — 9 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `assignment_id` | `uuid` | — | PK | `gen_random_uuid()` | — | Định danh lượt gán vai. |
| 2 | `user_id` | `uuid` | — | FK | — | `(membership_id, user_id)` → `memberships(membership_id, user_id)`<br>`users.id` | Tài khoản NHẬN lượt gán vai — chủ thể của quyền.<br><sub>NOT NULL, ON DELETE CASCADE: xoá người thì xoá luôn phép gán</sub> |
| 3 | `role_id` | `uuid` | — | FK | — | `roles.role_id` | Vai trò được gán.<br><sub>Constraint trigger ct_role_assignments_scope TỪ CHỐI gán một vai đã tắt (`roles.is_active = false`): một dòng gán 'đang hiệu lực' cho vai đã tắt sẽ khiến giao diện nói người này có vai còn Casbin nói không</sub> |
| 4 | `membership_id` | `uuid` | ✓ | FK | — | `(membership_id, user_id)` → `memberships(membership_id, user_id)` | Tư cách thành viên mà lượt gán này gắn vào.<br><sub>Khoá ngoại ghép (membership_id, user_id) bảo đảm vai được gán cho đúng người của membership. ct_role_assignments_scope còn cưỡng chế: (1) phạm vi SYSTEM KHI VÀ CHỈ KHI membership_id IS NULL — hai chiều; (2) phạm vi của vai phải BẰNG phạm vi của membership, không phải quan hệ thống trị; (3) vai thuộc một tổ chức chỉ gán được TRONG tổ chức đó — khoá ngoại không phản đối vì cả hai định danh đều có thật; (4) vai giới hạn theo loại tổ chức chỉ gán được trong tổ chức đúng loại</sub> |
| 5 | `assigned_by_user_id` | `uuid` | — | FK | — | `users.id` | Tài khoản THỰC HIỆN việc cấp vai — tác nhân.<br><sub>NOT NULL, ON DELETE RESTRICT: CSDL từ chối xoá một tài khoản khi vẫn còn Role Assignment tham chiếu tài khoản đó ở vai trò người cấp. Giữ được dấu vết tác nhân chừng nào bản ghi cấp vai còn tồn tại</sub> |
| 6 | `assigned_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm cấp vai. |
| 7 | `revoked_by_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản THỰC HIỆN việc thu hồi vai — tác nhân thu hồi.<br><sub>NULL cho tới khi vai bị thu hồi</sub> |
| 8 | `revoked_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm thu hồi vai. |
| 9 | `revoke_reason` | `text` | ✓ | — | — | — | Lý do thu hồi. |

### `role_permissions` — 3 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `role_id` | `uuid` | — | PK FK | — | `roles.role_id` | Vai trò được cấp quyền. |
| 2 | `permission_code` | `text` | — | PK FK | — | `permissions.permission_code` | Quyền được cấp cho vai trò.<br><sub>Constraint trigger ct_role_permissions_dominance ngăn vai ở phạm vi HẸP chứa quyền có phạm vi RỘNG hơn (authz_scope_rank(role) < authz_scope_rank(permission) thì từ chối) — rào chắn leo thang quyền ở tầng CSDL. Chiều ngược lại được phép và cần thiết: vai TENANT chứa quyền PROJECT chính là cơ chế thống trị phạm vi. Cùng trigger còn chặn vai TUỲ CHỈNH chứa quyền có is_custom_role_allowed = false ở BẤT KỲ phạm vi nào — nửa còn lại của ck_permissions_system_not_custom_role, vốn chỉ chặn quyền SYSTEM</sub> |
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
| 10 | `tenant_type_constraint` | `text` | ✓ | — | — | — | Giới hạn vai trò chỉ áp cho một loại tổ chức (COMMUNITY hoặc ORGANIZATION); NULL nghĩa là không giới hạn.<br><sub>Constraint trigger ct_roles_tenant_type kiểm loại tổ chức SỞ HỮU vai phải khớp giá trị này. Đây là bảo đảm giữa các hàng mà CHECK không làm được — CHECK chỉ ràng được miền giá trị. Trigger thứ hai, ct_role_assignments_scope, chặn tiếp ở lúc GÁN</sub> |
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
| 3 | `slug` | `text` | ✓ | — | — | — | Slug — dạng rút gọn của tên tổ chức. **`CẦN DUYỆT`**<br><sub>Có ràng buộc duy nhất (tenants_slug_key, không phải chỉ mục một phần); chưa xác nhận consumer hiện hành, và chưa xác nhận cột có thực sự tham gia URL/route hay không</sub> |
| 4 | `is_active` | `boolean` | — | — | `true` | — | Tổ chức còn hoạt động hay không. |
| 5 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo tổ chức. |
| 6 | `deleted_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm xoá mềm tổ chức. |
| 7 | `cloned_from_community_version` | `bigint` | ✓ | FK | — | `community_versions.version` | Phiên bản danh mục Community mà tổ chức được nhân bản từ đó lúc tạo.<br><sub>Kế thừa xảy ra lúc TẠO, không phải một đường vọng lại lúc chạy</sub> |
| 8 | `cloned_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm nhân bản danh mục. |
| 9 | `plan_code` | `text` | — | FK | `'free'::text` | `plans.plan_code` | Gói dịch vụ hiện hành; là nguồn ĐỌC của mọi phép cưỡng chế hạn mức.<br><sub>Lịch sử đổi gói nằm ở tenant_subscriptions</sub> |
| 10 | `billing_status` | `text` | — | — | `'active'::text` | — | Trạng thái billing/dịch vụ của tổ chức; được dùng để quyết định tổ chức còn ghi được dữ liệu hay không. |
| 11 | `trial_ends_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm hết hạn dùng thử. |
| 12 | `current_period_start` | `timestamp with time zone` | ✓ | — | — | — | Đầu kỳ hạn hiện tại của đăng ký. |
| 13 | `current_period_end` | `timestamp with time zone` | ✓ | — | — | — | Cuối kỳ hạn hiện tại; mốc để nhắc hạn và mở kỳ mới. |
| 14 | `is_self_serve` | `boolean` | — | — | `false` | — | Tổ chức tự đăng ký hay do quản trị viên nền tảng tạo. |
| 15 | `owner_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản được chỉ định làm chủ sở hữu tổ chức; có thể NULL.<br><sub>KHÁC chiều với users.tenant_id — hai quan hệ riêng, không phải nghịch đảo của nhau</sub> |
| 16 | `suspended_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm tạm ngưng dịch vụ. |
| 17 | `suspended_reason` | `text` | ✓ | — | — | — | Lý do tạm ngưng. |
| 18 | `tenant_type` | `text` | — | — | `'ORGANIZATION'::text` | — | Loại tổ chức: COMMUNITY hay ORGANIZATION.<br><sub>Community là một tenant DỰ TRỮ, không phải một mặt phẳng riêng</sub> |
| 19 | `is_system_reserved` | `boolean` | — | — | `false` | — | Tổ chức do nền tảng giữ chỗ, không được xoá. |
| 21 | `billing_exempt` | `boolean` | — | — | `false` | — | Miễn trừ hạn mức thương mại.<br><sub>Không dùng các TRẦN THƯƠNG MẠI tương ứng để chặn; mức sử dụng vẫn được đo</sub> |

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
| 3 | `name` | `text` | — | — | — | — | Tên workspace, duy nhất trong phạm vi tổ chức đối với workspace chưa xoá mềm.<br><sub>Chỉ mục duy nhất MỘT PHẦN uq_workspaces_tenant_name, predicate `deleted_at IS NULL`</sub> |
| 4 | `description` | `text` | — | — | `''::text` | — | Mô tả workspace. |
| 5 | `status` | `text` | — | — | `'ACTIVE'::text` | — | Trạng thái workspace. |
| 6 | `is_default` | `boolean` | — | — | `false` | — | Workspace mặc định của tổ chức.<br><sub>Chỉ mục duy nhất MỘT PHẦN uq_workspaces_default_active: mỗi tổ chức có tối đa MỘT workspace vừa is_default = true, vừa status = 'ACTIVE', vừa chưa xoá mềm</sub> |
| 7 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo. |
| 8 | `archived_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm lưu trữ. |
| 9 | `deleted_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm xoá mềm. |

## B. Authentication & User Security

### `password_reset_tokens` — 5 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `token_hash` | `text` | — | PK | — | — | Băm SHA-256 của mã đặt lại mật khẩu. Bảng KHÔNG lưu mã gốc.<br><sub>Mã được sinh với entropy CAO nên không cần slow hash kiểu mật khẩu; CSDL chỉ giữ SHA-256 của mã. Cùng cách với refresh token</sub> |
| 2 | `user_id` | `uuid` | — | FK | — | `users.id` | Tài khoản mà mã đặt lại này thuộc về. |
| 3 | `expires_at` | `timestamp with time zone` | — | — | — | — | Thời điểm mã hết hiệu lực. |
| 4 | `used_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm mã đã được dùng; NULL khi chưa dùng.<br><sub>Dùng một lần: khác `expires_at` ở chỗ mã có thể chết vì đã tiêu, không chỉ vì hết giờ</sub> |
| 5 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm phát mã. |

### `refresh_tokens` — 8 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `token_hash` | `text` | — | PK | — | — | Băm SHA-256 của refresh token. Bảng KHÔNG lưu token gốc.<br><sub>Token sinh với entropy CAO nên không cần slow hash kiểu mật khẩu; CSDL chỉ giữ SHA-256. Khác `verification_codes.code_hash` (mã entropy thấp, phải HMAC + pepper)</sub> |
| 2 | `user_id` | `uuid` | — | FK | — | `users.id` | Tài khoản giữ token này. |
| 3 | `expires_at` | `timestamp with time zone` | — | — | — | — | Thời điểm token hết hạn. |
| 4 | `revoked_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm token bị thu hồi.<br><sub>Ghi bằng `COALESCE(revoked_at, NOW())` nên KHÔNG ghi đè mốc cũ: ghi đè sẽ làm cửa sổ ân hạn trượt theo mỗi lần gọi, và một token bị trộm sống mãi bằng cách gọi lại đều đặn</sub> |
| 5 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm phát token. |
| 6 | `family_id` | `uuid` | ✓ | — | — | — | Định danh HỌ token: cả chuỗi xoay bắt nguồn từ một lần đăng nhập.<br><sub>NULL với token cấp trước khi cơ chế này ra đời — những token ấy chỉ đốt được chính mình</sub> |
| 7 | `replaced_by` | `text` | ✓ | — | — | — | Tham chiếu logic tới refresh token đã thay thế token này trong chuỗi xoay; lưu bằng băm của token kế nhiệm.<br><sub>KHÔNG có khoá ngoại: trỏ tới `token_hash` nhưng CSDL không cưỡng chế, nên một hàng đã dọn để lại tham chiếu treo. Hàng đã hết hạn được giữ thêm 7 ngày trước khi dọn (auth.purge_expired_refresh_tokens, mặc định retain_days=7, chạy hằng ngày qua saas_tasks.cleanup_refresh_tokens) để chuỗi `replaced_by` còn dựng lại được đường xoay khi điều tra. Đây là chính sách lưu giữ của HÀNG trong mã ứng dụng, không phải ràng buộc CSDL và không phải TTL của giá trị cột</sub> |
| 8 | `reuse_detected_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm phát hiện một refresh token đã bị thay thế được dùng lại NGOÀI cửa sổ ân hạn — coi như bị đánh cắp.<br><sub>Cột là BẰNG CHỨNG trạng thái, không phải tác nhân: CSDL không có trigger nào ở đây. Khi workflow phát hiện tái sử dụng (auth._burn_token_family) ghi mốc này, chính nó thu hồi mọi token cùng `family_id` và chặn các access token liên quan qua Redis; cố ý KHÔNG thu hồi toàn tài khoản, vì kẻ trộm theo cấu trúc đang giữ token MỚI NHẤT của họ</sub> |

### `user_action_passcodes` — 8 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `user_id` | `uuid` | — | PK FK | — | `users.id` | Tài khoản sở hữu mã hành động. Vừa là khoá chính vừa là khoá ngoại, nên mỗi tài khoản có tối đa MỘT cấu hình. |
| 2 | `passcode_hash` | `text` | — | — | — | — | Băm mã hành động, dùng CÙNG bộ băm mật khẩu với `auth.py`.<br><sub>Cố ý không tự chọn thuật toán riêng: hai bộ băm cho hai loại bí mật nghĩa là hai lịch nâng cấp tham số, và cái ít được để ý sẽ tụt lại</sub> |
| 3 | `status` | `text` | — | — | `'ACTIVE'::text` | — | Trạng thái: `ACTIVE`, `LOCKED` hoặc `REVOKED`.<br><sub>CSDL CÓ ràng tập này: ck_user_action_passcodes_status CHECK (status = ANY (ARRAY['ACTIVE','LOCKED','REVOKED'])). app/authorization/passcode.py ghi đúng ba giá trị ấy — hai lớp cùng nói một điều, nên thêm trạng thái mới phải sửa CẢ HAI</sub> |
| 4 | `failed_count` | `smallint` | — | — | `0` | — | Số lần nhập sai tích luỹ.<br><sub>CHỈ về 0 khi nhập ĐÚNG, không tự về 0 theo thời gian: một mã sáu ký tự với đồng hồ tự tha thứ là một mã dò được, chỉ chậm hơn. ck_user_action_passcodes_failed_count cấm giá trị âm</sub> |
| 5 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm đặt mã. |
| 6 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm cập nhật gần nhất. |
| 7 | `locked_until` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm hết khoá sau khi nhập sai; NULL khi không bị khoá.<br><sub>Thời gian khoá TĂNG DẦN theo ngưỡng số lần sai</sub> |
| 8 | `revoked_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm mã bị thu hồi. |

### `user_recovery_codes` — 4 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `code_hash` | `text` | — | PK | — | — | Băm HMAC-SHA256 của một mã khôi phục. Bảng KHÔNG lưu mã gốc.<br><sub>Mã khôi phục được BĂM chứ không mã hoá, vì chỉ cần trả lời đúng/sai — khác `user_totp.secret_enc` vốn cần chính bí mật để tính lại mã</sub> |
| 2 | `user_id` | `uuid` | — | FK | — | `users.id` | Tài khoản sở hữu bộ mã khôi phục. |
| 3 | `used_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm mã đã được dùng; NULL khi chưa dùng.<br><sub>Mỗi mã dùng ĐÚNG MỘT LẦN: lượt xác minh đòi `used_at IS NULL`</sub> |
| 4 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm cấp mã. |

### `user_totp` — 5 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `user_id` | `uuid` | — | PK FK | — | `users.id` | Tài khoản sở hữu cấu hình TOTP. Vừa là khoá chính vừa là khoá ngoại, nên mỗi tài khoản có tối đa MỘT cấu hình. |
| 2 | `secret_enc` | `text` | — | — | — | — | Bí mật TOTP đã **MÃ HOÁ** (Fernet) — KHÔNG phải băm.<br><sub>Trong các cột lưu VẬT LIỆU XÁC THỰC của nhóm B, đây là trường duy nhất phải giữ ở dạng KHÔI PHỤC ĐƯỢC; các credential còn lại dùng cơ chế một chiều hợp với loại bí mật của chúng. TOTP cần chính bí mật để tính lại mã nên băm một chiều là vô dụng</sub> |
| 3 | `confirmed_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm người dùng xác nhận và 2FA bật; NULL khi bí mật đã ghi nhưng chưa bật.<br><sub>Bật 2FA là HAI bước có chủ ý: gộp làm một sẽ khoá người dùng ra khỏi tài khoản khi ứng dụng xác thực quét hỏng hoặc đồng hồ lệch</sub> |
| 4 | `last_used_step` | `bigint` | ✓ | — | — | — | Bước thời gian TOTP đã dùng gần nhất — chống phát lại.<br><sub>Một mã TOTP sống 30 giây; không ghi lại bước đã dùng thì người nhìn trộm màn hình gõ lại đúng mã đó vẫn vào được, và đó chính là kịch bản 2FA sinh ra để chặn</sub> |
| 5 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm bắt đầu đăng ký TOTP.<br><sub>Đặt lại khi người dùng đăng ký lại: lượt ghi đè cũng xoá `confirmed_at` và `last_used_step`</sub> |

### `verification_codes` — 11 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `challenge_id` | `uuid` | — | PK | — | — | Định danh một thử thách xác minh. |
| 2 | `user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản liên quan tới thử thách, nếu đã tồn tại; có thể NULL với thử thách tạo TRƯỚC khi đăng ký hoàn tất.<br><sub>Đây là lý do quan hệ mang tên 'is associated with' chứ không 'has'</sub> |
| 3 | `purpose` | `text` | — | — | — | — | Mục đích: `verify_email`, `verify_phone` hoặc `reset_password`.<br><sub>verification_codes_purpose_valid ràng đúng ba giá trị này. Trên sản xuất hiện chỉ quan sát thấy verify_email và reset_password</sub> |
| 4 | `channel` | `text` | — | — | — | — | Kênh gửi mã: `email` hoặc `sms`.<br><sub>verification_codes_channel_valid ràng đúng hai giá trị này. Trên sản xuất hiện chỉ quan sát thấy email</sub> |
| 5 | `destination` | `text` | — | — | — | — | Địa chỉ hoặc số điện thoại mà mã được gửi tới.<br><sub>Cùng với `purpose`, được buộc vào thông điệp băm để TÁCH MIỀN: một mã phát để xác minh số điện thoại không được đồng thời hợp lệ như mã đặt lại mật khẩu, và cùng một mã gửi tới hai địa chỉ khác nhau không được va nhau</sub> |
| 6 | `code_hash` | `text` | — | — | — | — | Băm HMAC-SHA256 của mã, khoá bằng pepper NGOÀI cơ sở dữ liệu.<br><sub>Không dùng SHA-256 trần như token: mã sáu chữ số chỉ có một triệu khả năng, băm trần là duyệt cạn trong một giây. Pepper nằm ngoài CSDL nên một bản sao lưu bị lộ vẫn không đủ để dò</sub> |
| 7 | `attempts` | `integer` | — | — | `0` | — | Số lần đã thử nhập mã.<br><sub>Chịu BẤT BIẾN NHIỀU CỘT verification_codes_attempts_bounded: attempts >= 0 AND attempts <= max_attempts. CSDL không cho phép một thử thách ghi nhận nhiều lần thử hơn mức trần của chính nó</sub> |
| 8 | `max_attempts` | `integer` | — | — | `5` | — | Số lần thử tối đa trước khi thử thách chết; mặc định 5.<br><sub>Mặc định 5 ở cấp cột. Cùng `attempts` chịu verification_codes_attempts_bounded, nên hạ trần xuống dưới số lần đã thử sẽ bị CSDL từ chối</sub> |
| 9 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm phát thử thách. |
| 10 | `expires_at` | `timestamp with time zone` | — | — | — | — | Thời điểm thử thách hết giờ. |
| 11 | `consumed_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm mã đã được tiêu; NULL khi chưa dùng.<br><sub>Khác `expires_at`: một thử thách chết vì ĐÃ DÙNG, vì HẾT GIỜ, hoặc vì cạn `max_attempts` — ba đường khác nhau</sub> |

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
| 20 | `collection_campaign` | `text` | ✓ | — | — | — | Đợt thu thập mà lớp được tạo ra trong đó. **`CẦN DUYỆT`**<br><sub>Cùng câu hỏi như `samples.collection_campaign`: quy tắc đặt tên đợt chưa xác nhận.</sub> |
| 21 | `motion_type` | `text` | ✓ | — | — | — | Lớp là ký hiệu tĩnh hay động.<br><sub>Đo được: `static` và `dynamic`</sub> |
| 22 | `tenant_id` | `text` | — | FK | `'default'::text` | `(tenant_id, dialect)` → `dialects(tenant_id, dialect_id)`<br>`(tenant_id, recognition_profile)` → `recognition_profiles(tenant_id, profile_id)`<br>`(tenant_id, vocabulary_group)` → `vocabulary_groups(tenant_id, group_id)`<br>`tenants.tenant_id` | Tổ chức xác định phạm vi của lớp. |
| 23 | `region` | `text` | — | FK | `'unclassified'::text` | `regions.code` | Chiều phân loại vùng miền của lớp; tham gia khoá duy nhất TỰ NHIÊN của lớp chưa xoá mềm.<br><sub>Chỉ mục duy nhất MỘT PHẦN uq_classes_tenant_slug_lang_dialect_region gồm (tenant_id, slug, language, dialect, region) với predicate `deleted_at IS NULL`; vì vậy vùng miền tham gia phân biệt các lớp trùng mọi chiều còn lại. Khoá chính vẫn là `class_uid`. Mặc định `unclassified`</sub> |

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
| 1 | `profile_id` | `text` | — | PK | — | — | Định danh hồ sơ nhận dạng trong KHUÔN nền tảng.<br><sub>Thuộc KHUÔN cấu hình cấp nền tảng — thứ mọi tổ chức mới được nhân bản từ đó. KHÔNG phải hồ sơ nhận dạng lưu trong tenant Community dự trữ</sub> |
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
| 1 | `version` | `bigint` | — | PK | — | — | Số hiệu phiên bản của KHUÔN nền tảng.<br><sub>KHÁC `registry_versions.version` (phiên bản registry của một tổ chức) và khác `vocabulary_registry_meta.version` (con trỏ). Ba khái niệm, cùng một chữ. Đây là phiên bản của KHUÔN nền tảng, không phải phiên bản dữ liệu của tenant Community dự trữ</sub> |
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
| 6 | `is_active` | `boolean` | — | — | `true` | — | Phương ngữ còn được chọn trong các ô chọn hay không.<br><sub>TRỤC KHÁC với `status`. Đo được: `testdatase` có status=approved nhưng is_active=false; vì vậy một mục ĐÃ ĐƯỢC DUYỆT vẫn có thể bị loại khỏi các danh sách lựa chọn đang hoạt động</sub> |
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
| 1 | `tenant_id` | `text` | — | PK FK | `'default'::text` | `(tenant_id, version)` → `registry_versions(tenant_id, version)`<br>`tenants.tenant_id` | Tổ chức mà con trỏ này thuộc về.<br><sub>Đồng thời là khoá chính (vocabulary_registry_meta_pkey), nên mỗi tổ chức có nhiều nhất MỘT dòng metadata; cardinality là 1 — 0..1, KHÔNG phải 1–1 bắt buộc: một tổ chức có thể chưa có dòng nào</sub> |
| 2 | `version` | `bigint` | ✓ | FK | — | `(tenant_id, version)` → `registry_versions(tenant_id, version)` | CON TRỎ tới phiên bản registry đang công bố của tổ chức. NULL = chưa công bố phiên bản nào.<br><sub>Không phải một phiên bản riêng: nó chỉ trỏ vào registry_versions. Trước v7 chỗ này dùng số 0 làm sentinel 'chưa công bố', nhưng KHÔNG có hàng (tenant, 0) tương ứng trong registry_versions; khi khoá ngoại ghép được áp, sentinel ấy thành tham chiếu không hợp lệ và làm hỏng đường tạo tổ chức. Catalog hiện KHÔNG có CHECK nào cấm version = 0</sub> |
| 3 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm con trỏ được cập nhật gần nhất. |

## D. VSL Collection & Dataset

### `capture_sessions` — 12 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `capture_session_id` | `uuid` | — | PK | — | — | Định danh phiên thu một lớp ký hiệu. |
| 2 | `tenant_id` | `text` | — | FK | — | `(tenant_id, class_uid)` → `classes(tenant_id, class_uid)`<br>`(tenant_id, collection_session_id)` → `collection_sessions(tenant_id, collection_session_id)`<br>`(tenant_id, signer_id)` → `signers(tenant_id, signer_id)`<br>`tenants.tenant_id` | Tổ chức sở hữu bản ghi. |
| 3 | `class_uid` | `text` | — | FK | — | `(tenant_id, class_uid)` → `classes(tenant_id, class_uid)` | Lớp ký hiệu được thu trong phiên này. |
| 4 | `session_id` | `text` | — | — | — | — | Mã phiên do client gửi; duy nhất theo (tổ chức, lớp), KHÔNG duy nhất một mình.<br><sub>Đo: 61 giá trị khác nhau, một mã trải nhiều lớp. CHECK capture_sessions_session_id_not_blank cấm chuỗi rỗng</sub> |
| 5 | `signer_id` | `text` | ✓ | FK | — | `(tenant_id, signer_id)` → `signers(tenant_id, signer_id)` | Người ký TÓM TẮT của phiên, giữ lại từ thiết kế cũ. `LEGACY`<br><sub>Dữ liệu bác bỏ giả định một phiên một người: 10/253 phiên mang từ 2 nhãn người ký trở lên. KHÔNG dùng làm chân lý. Khoá ngoại ghép tenant-aware VẪN còn hiệu lực — LEGACY ở đây nghĩa là cột không còn là nguồn danh tính chuẩn, KHÔNG có nghĩa là nó mất toàn vẹn tham chiếu</sub> |
| 6 | `auth_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã thực hiện phiên thu.<br><sub>Khác danh tính người ký</sub> |
| 7 | `source_type` | `text` | ✓ | — | — | — | Kênh thu của phiên. |
| 8 | `started_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm phiên bắt đầu. |
| 9 | `ended_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm phiên kết thúc.<br><sub>CHECK capture_sessions_ends_after_start là BẤT BIẾN NHIỀU CỘT có điều kiện: (ended_at IS NULL) OR (started_at IS NULL) OR (ended_at >= started_at)</sub> |
| 10 | `note` | `text` | ✓ | — | — | — | Ghi chú tự do. **`CẦN DUYỆT`**<br><sub>Không đường mã nào đọc cột này; ai ghi và ghi gì vào đó chưa xác nhận.</sub> |
| 11 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo bản ghi. |
| 12 | `collection_session_id` | `uuid` | ✓ | FK | — | `(tenant_id, collection_session_id)` → `collection_sessions(tenant_id, collection_session_id)` | Buổi thu chứa phiên này; NULL với dữ liệu có trước khi có phân cấp.<br><sub>ON DELETE SET NULL</sub> |

### `collection_sessions` — 9 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `collection_session_id` | `uuid` | — | PK | — | — | Định danh buổi thu. |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` | Tổ chức sở hữu bản ghi; là phạm vi áp dụng cách ly tenant. |
| 3 | `session_code` | `text` | — | — | — | — | Mã buổi thu do client sinh, duy nhất trong phạm vi một tổ chức.<br><sub>UNIQUE (tenant_id, session_code). CHECK collection_sessions_code_not_blank cấm chuỗi rỗng</sub> |
| 5 | `opened_by_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã mở buổi thu.<br><sub>Là người VẬN HÀNH, không phải người ký</sub> |
| 6 | `source_type` | `text` | ✓ | — | — | — | Kênh thu: camera trực tiếp hay tải video lên. |
| 7 | `started_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm buổi thu bắt đầu. |
| 8 | `ended_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm buổi thu kết thúc; NULL khi chưa đóng.<br><sub>CHECK collection_sessions_ends_after_start là BẤT BIẾN NHIỀU CỘT có điều kiện: (ended_at IS NULL) OR (started_at IS NULL) OR (ended_at >= started_at) — buổi thu chưa đóng hoặc chưa rõ giờ mở vẫn hợp lệ</sub> |
| 9 | `note` | `text` | ✓ | — | — | — | Ghi chú tự do của người vận hành. **`CẦN DUYỆT`**<br><sub>Không đường mã nào đọc cột này; ai ghi và ghi gì vào đó chưa xác nhận.</sub> |
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
| 7 | `source_type` | `text` | ✓ | — | — | — | Loại nguồn của lượt tải lên; đường ghi hiện hành gán giá trị `video`.<br><sub>Đường TẠO upload hiện hành (routers/upload.py) gán cứng `video`. CSDL KHÔNG cưỡng chế — không có CHECK nào — và đường gương/nhập CSV→DB chép nguyên giá trị từ tệp, nên không đường nào bảo đảm cột này luôn là `video`. Sản xuất hiện có 1 hàng, giá trị `video`</sub> |
| 8 | `user_id` | `text` | ✓ | — | — | — | Nhãn người ký/tài khoản dạng văn bản, theo hợp đồng dữ liệu cũ; đường ghi hiện hành vẫn điền cột này. KHÔNG phải khoá ngoại tới users.<br><sub>Thuộc account_rename.STATE_COPIES: giá trị đã lưu ĐƯỢC CẬP NHẬT khi tài khoản đổi tên, nên không phải ảnh chụp lịch sử bất biến. Vẫn ghi ở hàng mới (có trong _RAW_UPLOAD_DB_KEYS)</sub> |
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
| 20 | `username` | `text` | ✓ | — | — | — | Bản sao tên tài khoản, chỉ còn trên dữ liệu cũ. `LEGACY`<br><sub>Nghỉ hưu theo ĐƯỜNG GHI, không phải cột bỏ hoang: `username` vắng trong _RAW_UPLOAD_DB_KEYS nên hàng mới không có giá trị, nhưng giá trị cũ vẫn thuộc account_rename.STATE_COPIES và được cập nhật khi đổi tên. Hàng duy nhất trên sản xuất để trống cột này</sub> |
| 21 | `tenant_id` | `text` | — | FK | `'default'::text` | `(tenant_id, class_uid)` → `classes(tenant_id, class_uid)`<br>`(tenant_id, dialect)` → `dialects(tenant_id, dialect_id)`<br>`tenants.tenant_id` | Tổ chức sở hữu video. |

### `samples` — 46 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `sample_uid` | `text` | — | PK | — | — | Định danh mẫu.<br><sub>CHECK samples_uid_is_hex10 buộc ĐÚNG 10 ký tự hex THƯỜNG: `^[0-9a-f]{10}$`</sub> |
| 2 | `class_uid` | `text` | ✓ | FK | — | `(tenant_id, class_uid)` → `classes(tenant_id, class_uid)`<br>`classes.class_uid` | Lớp ký hiệu mà mẫu này mang nhãn. |
| 3 | `slug` | `text` | ✓ | — | — | — | Bản sao slug của lớp tại thời điểm ghi. **`CẦN DUYỆT`**<br><sub>Phi chuẩn hoá; nguồn chuẩn là classes</sub> |
| 4 | `label_original` | `text` | ✓ | — | — | — | Bản sao nhãn gốc của lớp tại thời điểm ghi. **`CẦN DUYỆT`**<br><sub>Phi chuẩn hoá</sub> |
| 5 | `language` | `text` | ✓ | FK | — | `languages.code` | Ngôn ngữ ký hiệu của mẫu. |
| 6 | `dialect` | `text` | ✓ | FK | — | `(tenant_id, dialect)` → `dialects(tenant_id, dialect_id)` | Phương ngữ của mẫu. |
| 7 | `source_type` | `text` | ✓ | — | — | — | Kênh thu: camera hay video tải lên. |
| 8 | `user_id` | `text` | ✓ | — | — | — | Nhãn người ký/tài khoản dạng văn bản, theo hợp đồng dữ liệu cũ; đường ghi hiện hành vẫn điền cột này. KHÔNG phải khoá ngoại tới users.<br><sub>Thuộc account_rename.STATE_COPIES: giá trị đã lưu ĐƯỢC CẬP NHẬT khi tài khoản đổi tên, nên đây KHÔNG phải ảnh chụp lịch sử bất biến — khác hẳn audit_log.actor_label vốn nằm trong FROZEN_COPIES. Vẫn ghi ở mọi hàng mới (có trong _SAMPLE_DB_KEYS; 3.864/3.864 dòng có giá trị, kể cả 08/2026), và hiện vẫn là trường cho thấy 10/253 phiên chứa nhiều nhãn người ký. Danh tính chuẩn hoá ở signer_id, nhưng cột đó mới điền 43% và đang đóng băng</sub> |
| 9 | `auth_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã thực hiện thao tác thu/tải mẫu này.<br><sub>Khác hẳn danh tính người ký. 166/3.864 dòng còn trống</sub> |
| 10 | `session_id` | `text` | ✓ | — | — | — | Mã phiên do client gửi tại thời điểm thu.<br><sub>Đo: 2.867/3.864 dòng có giá trị, 61 giá trị khác nhau</sub> |
| 11 | `fps_original` | `text` | ✓ | — | — | — | Tốc độ khung hình của nguồn gốc. **`CẦN DUYỆT`**<br><sub>Kiểu text chứ không phải số — cần xác nhận vì sao</sub> |
| 12 | `fps_processed` | `text` | ✓ | — | — | — | Tốc độ khung hình sau xử lý. **`CẦN DUYỆT`**<br><sub>Kiểu text chứ không phải số</sub> |
| 13 | `seq_len` | `integer` | ✓ | — | — | — | Độ dài chuỗi sau khi đệm về độ dài đích. |
| 14 | `augment_id` | `integer` | ✓ | — | — | — | Chỉ số bản tăng cường; 0 là bản gốc. |
| 15 | `completeness` | `real` | ✓ | — | — | — | Tỷ lệ khung hình có bàn tay hợp lệ. `DERIVED`<br><sub>TÁI TÍNH ĐƯỢC từ npz đã lưu. Bằng hand_presence() trên chuỗi đã chuẩn hoá: completeness = both_hands_ratio khi lớp cần 2 tay, ngược lại là tỷ lệ có BẤT KỲ tay nào</sub> |
| 16 | `file_path` | `text` | ✓ | — | — | — | Đường dẫn tệp đặc trưng, tương đối so với gốc dataset.<br><sub>CHECK samples_file_path_is_local chỉ cấm giá trị bắt đầu bằng `http` — CSDL không cưỡng chế gì thêm. Việc đường dẫn phải tương đối so với gốc dataset là hợp đồng của ỨNG DỤNG, không phải của lược đồ</sub> |
| 17 | `storage_url` | `text` | ✓ | — | — | — | Đường dẫn hoặc URL nơi tệp đang nằm.<br><sub>Được cập nhật sau khi đẩy lên Drive</sub> |
| 18 | `checksum` | `text` | ✓ | — | — | — | Tổng kiểm của tệp đặc trưng. **`CẦN DUYỆT`**<br><sub>Thuật toán băm cần xác nhận</sub> |
| 19 | `created_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm ghi mẫu. |
| 20 | `sheets_synced` | `boolean` | ✓ | — | `false` | — | Đã đồng bộ sang Google Sheets chưa. |
| 21 | `gdrive_synced` | `boolean` | ✓ | — | `true` | — | Đã đồng bộ lên Google Drive chưa.<br><sub>Bẫy đã biết: CREATE TABLE mặc định FALSE còn ALTER mặc định TRUE, nên máy cài mới và máy cũ khác nhau</sub> |
| 23 | `status` | `character varying(20)` | ✓ | — | `'PENDING'::character varying` | — | Không còn được cập nhật. `LEGACY`<br><sub>KHÔNG đường ghi hiện hành nào cập nhật cột này: `status` không có trong _SAMPLE_DB_KEYS nên lượt upsert bỏ qua nó hoàn toàn; giá trị đến từ DEFAULT 'PENDING' của câu ALTER. Trạng thái kiểm duyệt sống ở review_status. Đo: PENDING trên cả 3.864 dòng</sub> |
| 24 | `error_log` | `text` | ✓ | — | `''::text` | — | Thông báo lỗi của lượt xử lý, nếu có. **`CẦN DUYỆT`**<br><sub>Mặc định chuỗi rỗng. Đường ghi và tập thông báo chưa xác nhận; không rõ nó ghi lỗi của lượt xử lý nào.</sub> |
| 25 | `updated_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm cập nhật gần nhất. |
| 26 | `storage_key` | `text` | ✓ | — | `''::text` | — | Khoá tệp trên kho lưu trữ, tương đối so với gốc dataset. |
| 27 | `session_uid` | `text` | ✓ | — | — | — | Mã phiên thứ hai, khác session_id. **`CẦN DUYỆT`**<br><sub>Đo: 991 dòng có giá trị, 109 giá trị khác nhau. Quan hệ với session_id chưa rõ</sub> |
| 28 | `username` | `text` | ✓ | — | — | — | Bản sao tên tài khoản, chỉ còn trên dữ liệu cũ. `LEGACY`<br><sub>Nghỉ hưu theo ĐƯỜNG GHI, không phải cột bỏ hoang: không câu INSERT/upsert nào còn điền nó (`username` vắng trong _SAMPLE_DB_KEYS), nhưng giá trị cũ VẪN thuộc account_rename.STATE_COPIES và được cập nhật khi tài khoản đổi tên. Đo theo tháng: 05/2026 764/1244, 06/2026 400/440, 07/2026 5/2176, 08/2026 0/4</sub> |
| 30 | `deleted_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm xoá mềm; tệp VẪN nằm trên đĩa cho tới khi dọn Thùng rác.<br><sub>Vì vậy xoá mềm không trả lại dung lượng</sub> |
| 31 | `left_hand_ratio` | `real` | ✓ | — | — | — | Tỷ lệ khung hình phát hiện được tay trái. `DERIVED`<br><sub>TÁI TÍNH ĐƯỢC từ npz đã lưu: hand_presence() chỉ hỏi khối tay có khác 0 không, và normalize_single_hand trả nguyên khối rỗng (`if not np.any(h): return h`), nên chuẩn hoá không đổi câu trả lời</sub> |
| 32 | `right_hand_ratio` | `real` | ✓ | — | — | — | Tỷ lệ khung hình phát hiện được tay phải. `DERIVED`<br><sub>TÁI TÍNH ĐƯỢC từ npz đã lưu — cùng cơ chế với left_hand_ratio</sub> |
| 33 | `both_hands_ratio` | `real` | ✓ | — | — | — | Tỷ lệ khung hình phát hiện được cả hai tay. `DERIVED`<br><sub>TÁI TÍNH ĐƯỢC từ npz đã lưu — cùng cơ chế với left_hand_ratio</sub> |
| 34 | `jitter` | `real` | ✓ | — | — | — | Độ rung của chuỗi landmark, phân vị 95. `DERIVED`<br><sub>KHÔNG tái tính được từ npz ĐÃ CHUẨN HOÁ: chỉ số đo ĐỘ DỜI toạ độ và phải tính TRƯỚC normalize_hands_vector_126, khi toạ độ còn ở thang ảnh MediaPipe 0..1. NHƯNG kho raw giữ đúng mảng ấy — `landmarks_raw` [T_original, 126], trước khi căn cổ tay và co giãn — nên với mẫu CÓ kho raw thì tính lại được. Đo: 1.678/3.864 mẫu có raw (raw_landmarks_available), 2.186 mẫu KHÔNG có và với chúng chỉ số này là không khôi phục được</sub> |
| 35 | `quality_flags` | `text` | ✓ | — | — | — | Các cờ cảnh báo chất lượng của lượt thu. `DERIVED`<br><sub>KHÔNG tái tính được chỉ từ hàng samples và npz đã chuẩn hoá. Cần THÊM hai thứ mà hàng samples không bảo đảm: (1) mảng trước chuẩn hoá để có jitter_p95 — chỉ có ở 1.678/3.864 mẫu qua `landmarks_raw`; (2) đúng bộ ngưỡng qc_* tại thời điểm thu, vốn không lưu cạnh mẫu mà chỉ nằm trong nhật ký JSONL của lượt thu. Điều kiện (2) chưa mẫu nào thoả từ dữ liệu đã lưu</sub> |
| 36 | `signer_id` | `text` | ✓ | FK | — | `(tenant_id, signer_id)` → `signers(tenant_id, signer_id)` | Danh tính người ký đã chuẩn hoá, khi đã phân định được.<br><sub>2.186/3.864 dòng còn trống, ĐANG ĐÓNG BĂNG chờ duyệt 266 khối thời gian</sub> |
| 37 | `collection_campaign` | `text` | ✓ | — | — | — | Đợt thu thập mà mẫu thuộc về. **`CẦN DUYỆT`**<br><sub>Lấy từ cấu hình `collection_campaign` lúc thu, nhưng quy tắc đặt tên đợt và ai quyết định nó chưa được ghi ở đâu.</sub> |
| 38 | `raw_landmarks_available` | `boolean` | ✓ | — | — | — | Có bản landmark thô trong kho raw hay không.<br><sub>Kho raw là nửa KHÔNG tái tạo được của một mẫu: `sequence` dựng lại được từ raw bằng cách chạy lại bộ chuẩn hoá, còn raw thì không dựng lại được từ đâu. Cột này vì thế quyết định mẫu nào còn tính lại được jitter. Đo: 1.678/3.864 mẫu có raw</sub> |
| 39 | `normalization_version` | `text` | ✓ | — | — | — | Phiên bản thuật toán chuẩn hoá đã áp cho mẫu.<br><sub>Cho phép chạy lại chuẩn hoá mà vẫn biết mẫu nào đã dùng phiên bản nào</sub> |
| 40 | `preprocess_contract_version` | `text` | ✓ | — | — | — | Phiên bản hợp đồng tiền xử lý. |
| 41 | `sequence_length_original` | `integer` | ✓ | — | — | — | Số khung hình trước khi đệm hoặc cắt. |
| 42 | `quality_status` | `text` | ✓ | — | — | — | Kết luận chất lượng: đạt hay bị gắn cờ. `DERIVED`<br><sub>KHÔNG tái tính được chỉ từ hàng samples và npz đã chuẩn hoá — cùng hai điều kiện như quality_flags, vì cả hai là đầu ra của evaluate_quality(metrics, cfg)</sub> |
| 43 | `tenant_id` | `text` | — | FK | `'default'::text` | `(tenant_id, capture_session_id)` → `capture_sessions(tenant_id, capture_session_id)`<br>`(tenant_id, class_uid)` → `classes(tenant_id, class_uid)`<br>`(tenant_id, signer_id)` → `signers(tenant_id, signer_id)`<br>`(tenant_id, dialect)` → `dialects(tenant_id, dialect_id)`<br>`tenants.tenant_id` | Tổ chức sở hữu mẫu; là phạm vi áp dụng cách ly tenant.<br><sub>Tham gia 4 khoá ngoại GHÉP — tới Capture Session, Class, Signer và Dialect — đồng thời có khoá ngoại ĐƠN fk_samples_tenant tới Tenant. Là trụ neo tenant của bảng</sub> |
| 44 | `capture_session_id` | `uuid` | ✓ | FK | — | `(tenant_id, capture_session_id)` → `capture_sessions(tenant_id, capture_session_id)`<br>`capture_sessions.capture_session_id` | Phiên thu chứa mẫu này.<br><sub>997/3.864 dòng còn trống — dữ liệu có trước khi đường ghi nối phân cấp. Chỉ có trong CSDL, không có trong samples.csv</sub> |
| 45 | `review_status` | `text` | — | — | `'pending'::text` | — | Trạng thái kiểm duyệt của mẫu.<br><sub>MIỀN CHO PHÉP do ck_samples_review_status quy định: pending, approved, rejected. QUAN SÁT trên sản xuất: approved 3.862, pending 2, rejected 0 — miền rộng hơn dữ liệu đang có</sub> |
| 46 | `reviewed_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã kiểm duyệt mẫu. |
| 47 | `reviewed_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm kiểm duyệt. |
| 48 | `review_note` | `text` | ✓ | — | `''::text` | — | Ghi chú của người kiểm duyệt. |

### `signer_aliases` — 6 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `tenant_id` | `text` | — | PK FK | — | `(tenant_id, new_signer_id)` → `signers(tenant_id, signer_id)`<br>`tenants.tenant_id` | Tổ chức sở hữu bản ghi gộp. |
| 2 | `old_signer_id` | `text` | — | PK | — | — | Định danh người ký đã bị gộp đi.<br><sub>CHECK signer_aliases_not_self (old_signer_id <> new_signer_id) cấm tự gộp vào chính mình</sub> |
| 3 | `new_signer_id` | `text` | — | FK | — | `(tenant_id, new_signer_id)` → `signers(tenant_id, signer_id)` | Định danh người ký còn lại sau khi gộp. |
| 4 | `reason` | `text` | ✓ | — | — | — | Lý do gộp. |
| 5 | `merged_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm gộp. |
| 6 | `merged_by` | `uuid` | ✓ | FK | — | `users.id` | Người thực hiện gộp. |

### `signers` — 9 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `signer_id` | `text` | — | PK | — | — | Định danh chuẩn hoá của người ký; là KHOÁ CHÍNH toàn bảng.<br><sub>Cặp (tenant_id, signer_id) có chỉ mục duy nhất riêng (uq_signers_tenant_signer_id) để làm ĐÍCH cho các khoá ngoại tenant-aware từ samples và capture_sessions</sub> |
| 2 | `display_name` | `text` | ✓ | — | — | — | Tên hiển thị của người ký. |
| 3 | `regional_group` | `text` | ✓ | — | — | — | Nhóm vùng miền của người ký. **`CẦN DUYỆT`**<br><sub>Quan hệ với bảng regions cần xác nhận</sub> |
| 4 | `external_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản hệ thống tương ứng, nếu người ký cũng là người dùng.<br><sub>NULL khi người ký không có tài khoản</sub> |
| 5 | `is_active` | `boolean` | ✓ | — | `true` | — | Người ký còn tham gia thu hay không. |
| 6 | `created_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm đăng ký người ký. |
| 7 | `tenant_id` | `text` | — | FK | `'default'::text` | `tenants.tenant_id` | Tổ chức quản lý hồ sơ người ký. |
| 8 | `note` | `text` | ✓ | — | — | — | Ghi chú tự do. **`CẦN DUYỆT`**<br><sub>Không đường mã nào đọc cột này; ai ghi và ghi gì vào đó chưa xác nhận.</sub> |
| 9 | `display_order` | `integer` | — | — | `0` | — | Thứ tự hiển thị do người vận hành sắp. |

## E. Legal, Consent & Governance

### `audit_log` — 10 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `audit_id` | `bigint` | — | PK | `nextval('audit_log_audit_id_seq'::regclass)` | — | Số thứ tự dòng kiểm toán. |
| 2 | `tenant_id` | `text` | ✓ | FK | — | `tenants.tenant_id` | Tổ chức của hành động. NULL với hành động cấp NỀN TẢNG.<br><sub>Là bảng duy nhất trong nhóm có tenant_id cho phép NULL — không phải mọi dòng đều thuộc một tổ chức</sub> |
| 3 | `actor_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản thực hiện hành động. |
| 4 | `actor_label` | `text` | ✓ | — | — | — | Nhãn người thực hiện, chụp lại tại thời điểm ghi.<br><sub>Thuộc account_rename.FROZEN_COPIES: đổi tên tài khoản KHÔNG cập nhật cột này — đây là ảnh chụp lịch sử, đối lập với các STATE_COPIES (samples.user_id, samples.username, raw_uploads.*) vốn được đồng bộ theo tên hiện hành. Còn lại sau khi tài khoản bị xoá</sub> |
| 5 | `action` | `text` | — | — | — | — | Hành động được ghi lại.<br><sub>CHECK audit_log_action_not_blank cấm chuỗi rỗng</sub> |
| 6 | `target_type` | `text` | ✓ | — | — | — | Loại đối tượng bị tác động. |
| 7 | `target_id` | `text` | ✓ | — | — | — | Định danh đối tượng bị tác động. |
| 8 | `detail` | `jsonb` | ✓ | — | — | — | Dữ liệu bổ sung, dạng JSON. |
| 9 | `ip_hash` | `text` | ✓ | — | — | — | Băm địa chỉ IP của lượt thao tác; cột KHÔNG lưu địa chỉ IP trực tiếp.<br><sub>Cơ chế KHÁC user_consents.ip_hash: HMAC-SHA256 với pepper NGOÀI cơ sở dữ liệu, tách miền bằng tiền tố `audit-ip`. Cố ý KHÔNG muối theo người thực hiện, để trả lời được 'có phải cùng một nơi vừa thử ba tài khoản quản trị không'. Không có pepper thì hàm trả None thay vì ghi một bản băm đảo ngược được</sub> |
| 10 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm ghi dòng kiểm toán. |

### `legal_document_drafts` — 21 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `draft_id` | `uuid` | — | PK | — | — | Định danh bản thảo văn bản. |
| 2 | `kind` | `text` | — | — | — | — | Loại văn bản mà bản thảo này nhắm tới.<br><sub>MIỀN CHO PHÉP do ck_legal_drafts_kind quy định: terms, privacy, data_contribution, guardian — cùng bộ với legal_documents.kind</sub> |
| 3 | `title` | `text` | — | — | `''::text` | — | Tiêu đề dự kiến. |
| 4 | `language` | `text` | — | — | `'vi'::text` | — | Ngôn ngữ bản thảo. |
| 5 | `body` | `text` | — | — | `''::text` | — | Thân bản thảo. |
| 6 | `body_format` | `text` | — | — | `'markdown'::text` | — | Dạng thân bản thảo. |
| 7 | `change_summary` | `text` | — | — | `''::text` | — | Tóm tắt thay đổi dự kiến. |
| 8 | `target_version` | `text` | — | — | `''::text` | — | Số hiệu phiên bản dự kiến đặt khi công bố. |
| 9 | `requires_reconsent` | `boolean` | — | — | `false` | — | Bản công bố từ bản thảo này sẽ buộc chấp thuận lại. |
| 10 | `effective_from` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm hiệu lực dự kiến. |
| 11 | `status` | `text` | — | — | `'draft'::text` | — | Trạng thái: `draft`, `in_review`, `approved`, `published` hoặc `discarded`.<br><sub>MIỀN CHO PHÉP do ck_legal_drafts_status quy định: draft, in_review, approved, published, discarded. Chỉ mục duy nhất MỘT PHẦN uq_legal_draft_open cho phép tối đa MỘT bản thảo ở một trong BA trạng thái draft, in_review, approved cho mỗi `kind`</sub> |
| 12 | `revision` | `integer` | — | — | `1` | — | Số lần sửa bản thảo, bắt đầu từ 1.<br><sub>CHECK ck_legal_drafts_revision buộc revision >= 1: không có bản sửa số 0</sub> |
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
| 1 | `event_id` | `bigint` | — | PK | `nextval('legal_document_events_event_id_seq'`… | — | Số thứ tự sự kiện trong sổ.<br><sub>Sổ CHỈ-THÊM được cưỡng chế bằng trigger trg_legal_events_append_only (BEFORE UPDATE OR DELETE): mọi lượt sửa hoặc xoá đều bị từ chối. Đính chính bằng cách ghi một dòng sự kiện mới</sub> |
| 2 | `occurred_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm sự kiện xảy ra. |
| 3 | `actor_user_id` | `uuid` | ✓ | — | — | — | Tài khoản thực hiện. Giữ như dấu vết, KHÔNG có khoá ngoại.<br><sub>Cố ý: một sổ đăng bạ không được cản chính hành động nó ghi lại. Bản trước có khoá ngoại và nó chặn lượt xoá tài khoản theo yêu cầu quyền riêng tư, để lại 9 hàng users mồ côi</sub> |
| 4 | `actor_label` | `text` | — | — | `''::text` | — | Nhãn người thực hiện, điền ngay lúc ghi.<br><sub>Thuộc account_rename.FROZEN_COPIES: đổi tên tài khoản KHÔNG cập nhật cột này. Là danh tính còn lại sau khi tài khoản bị xoá</sub> |
| 5 | `action` | `text` | — | — | — | — | Hành động được ghi lại.<br><sub>CHECK ck_legal_events_action_not_blank cấm chuỗi rỗng — cùng ràng buộc với audit_log.action</sub> |
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
| 2 | `kind` | `text` | — | — | — | — | Loại văn bản: `terms`, `privacy`, `data_contribution` hoặc `guardian`.<br><sub>MIỀN CHO PHÉP do legal_documents_kind_valid quy định. Cùng với `version` tạo thành khoá tự nhiên mà mọi chấp thuận neo vào</sub> |
| 3 | `version` | `text` | — | — | — | — | Phiên bản văn bản.<br><sub>`(kind, version)` là đích của khoá ngoại từ user_consents và signer_consents</sub> |
| 4 | `effective_from` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm văn bản bắt đầu có hiệu lực.<br><sub>trg_legal_documents_freeze cấm đổi cột này MỘT KHI bản đã có hiệu lực (OLD.effective_from <= now()) — đổi nó là viết lại câu trả lời cho 'hôm đó bản nào đang áp dụng'. Bản chưa tới hiệu lực thì vẫn sửa được</sub> |
| 5 | `content_hash` | `text` | — | — | — | — | Băm nội dung tại thời điểm công bố; là thứ chữ ký chấp thuận trỏ vào.<br><sub>Bất biến được CSDL cưỡng chế, nhưng KHÔNG bằng CHECK — bằng trigger trg_legal_documents_freeze (BEFORE UPDATE) ném restrict_violation nếu kind/version/body/content_hash đổi. Muốn đổi nội dung thì phải công bố phiên bản mới. Vì là trigger nên nó không hiện ra trong danh sách CHECK của bảng</sub> |
| 6 | `url` | `text` | — | — | — | — | Đường dẫn công khai tới văn bản. |
| 7 | `title` | `text` | — | — | `''::text` | — | Tiêu đề văn bản. |
| 8 | `requires_reconsent` | `boolean` | — | — | `false` | — | Bản này buộc người đã chấp thuận bản cũ phải chấp thuận lại.<br><sub>Phân biệt sửa lỗi chính tả với thay đổi thực chất về quyền và nghĩa vụ</sub> |
| 9 | `body` | `text` | — | — | `''::text` | — | Thân văn bản lưu thẳng trong cơ sở dữ liệu.<br><sub>Cùng trigger trg_legal_documents_freeze bảo vệ: sửa `body` của bản đã công bố bị từ chối ở tầng CSDL</sub> |
| 10 | `body_format` | `text` | — | — | `'markdown'::text` | — | Dạng thân văn bản: `markdown`, `text` hoặc `file`.<br><sub>MIỀN CHO PHÉP do ck_legal_documents_body_format quy định: markdown, text, file. Máy CÀI MỚI thiếu giá trị `file` do một lỗi thứ tự câu lệnh — xem docs/10-issues/KNOWN_ISSUES.md</sub> |
| 11 | `language` | `text` | — | — | `'vi'::text` | — | Ngôn ngữ của bản văn bản. |
| 12 | `change_summary` | `text` | — | — | `''::text` | — | Tóm tắt thay đổi so với bản trước. |
| 13 | `published_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm công bố. |
| 14 | `published_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã công bố văn bản. |
| 15 | `storage_backend` | `text` | — | — | `'local'::text` | — | Nơi lưu thân văn bản khi không nằm trong cột `body`. |
| 16 | `storage_key` | `text` | ✓ | — | — | — | Khoá tra thân văn bản trong kho định-địa-chỉ-bằng-nội-dung. |
| 17 | `byte_size` | `integer` | — | — | `0` | — | Kích thước thân văn bản. |
| 18 | `file_key` | `text` | ✓ | — | — | — | Khoá tra tệp đính kèm khi `body_format = 'file'`.<br><sub>CHECK ck_legal_documents_file_pair là BẤT BIẾN NHIỀU CỘT dạng tương đương: (body_format = 'file') = (file_key IS NOT NULL) — buộc cột này có giá trị KHI VÀ CHỈ KHI body_format = 'file', và cấm cả chiều ngược lại</sub> |
| 19 | `file_name` | `text` | ✓ | — | — | — | Tên tệp gốc của bản văn bản dạng tệp. |
| 20 | `file_mime` | `text` | ✓ | — | — | — | Kiểu MIME của tệp đính kèm. |
| 21 | `file_size` | `bigint` | ✓ | — | — | — | Kích thước tệp đính kèm. |

### `signer_consents` — 11 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `consent_id` | `uuid` | — | PK | — | — | Định danh bản ghi chấp thuận của người ký. |
| 2 | `tenant_id` | `text` | — | FK | — | `(tenant_id, signer_id)` → `signers(tenant_id, signer_id)`<br>`tenants.tenant_id` | Tổ chức xác định phạm vi của bản ghi. |
| 3 | `signer_id` | `text` | — | FK | — | `(tenant_id, signer_id)` → `signers(tenant_id, signer_id)` | Người ký LÀ CHỦ THỂ của chấp thuận.<br><sub>Khoá ngoại ghép `(tenant_id, signer_id)`</sub> |
| 4 | `scope` | `text` | — | — | — | — | Mức cho phép sử dụng dữ liệu: `internal_training`, `research_release` hoặc `public_library`.<br><sub>MIỀN CHO PHÉP do signer_consents_scope_valid quy định. Thang ba mức, rộng dần. `tenant_exports.export_purpose` dùng CÙNG bộ từ vựng — đó là chỗ nối chấp thuận vào phép phát hành</sub> |
| 5 | `kind` | `text` | — | FK | — | `(kind, version)` → `legal_documents(kind, version)` | Loại văn bản được chấp thuận. |
| 6 | `version` | `text` | — | FK | — | `(kind, version)` → `legal_documents(kind, version)` | Phiên bản văn bản được chấp thuận.<br><sub>Cùng cơ chế neo `(kind, version)` như user_consents</sub> |
| 7 | `granted_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm cho phép. |
| 8 | `withdrawn_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm rút cho phép.<br><sub>CHECK signer_consents_withdraw_after_grant là BẤT BIẾN NHIỀU CỘT có điều kiện: (withdrawn_at IS NULL) OR (withdrawn_at >= granted_at) — chưa rút thì vẫn hợp lệ</sub> |
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
| 4 | `status` | `text` | — | — | `'pending'::text` | — | Trạng thái: `pending`, `running`, `ready`, `failed` hoặc `expired`.<br><sub>MIỀN CHO PHÉP do ck_tenant_exports_status quy định: pending, running, ready, failed, expired</sub> |
| 5 | `scope` | `text` | — | — | `'metadata'::text` | — | Phạm vi dữ liệu xuất: `metadata` hoặc `full`.<br><sub>MIỀN CHO PHÉP do ck_tenant_exports_scope quy định: metadata, full</sub> |
| 6 | `file_path` | `text` | ✓ | — | — | — | Đường dẫn tệp kết quả.<br><sub>Tệp xuất CỐ Ý không tính vào hạn mức dung lượng: nó là bản sao của byte đã tính</sub> |
| 7 | `size_bytes` | `bigint` | ✓ | — | — | — | Kích thước tệp kết quả. |
| 8 | `row_counts` | `jsonb` | ✓ | — | — | — | Số hàng đã xuất theo từng bảng, dạng JSON. |
| 9 | `error` | `text` | ✓ | — | — | — | Thông báo lỗi khi lượt xuất thất bại. |
| 10 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm yêu cầu. |
| 11 | `completed_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm hoàn tất. |
| 12 | `expires_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm tệp xuất hết hạn và bị dọn. |
| 13 | `export_purpose` | `text` | — | — | `'tenant_portability'::text` | — | Mục đích phát hành: `tenant_portability`, `internal_training`, `research_release` hoặc `public_library`.<br><sub>MIỀN CHO PHÉP do ck_tenant_exports_purpose quy định. Ba giá trị sau TRÙNG bộ từ vựng của signer_consents.scope — đó là chỗ mức chấp thuận quyết định mẫu nào được phép ra khỏi hệ thống</sub> |

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
| 8 | `export_id` | `uuid` | ✓ | — | — | — | Lượt xuất dữ liệu thực hiện trước khi xoá, nếu có.<br><sub>Dấu vết định danh lượt xuất thực hiện trước khi xoá, KHÔNG phải liên kết tham chiếu: bảng tenant_purges không có khoá ngoại nào cả. Cho thấy tổ chức đã được trao dữ liệu trước khi bị xoá</sub> |
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
| 6 | `ip_hash` | `text` | ✓ | — | — | — | Băm địa chỉ IP tại thời điểm chấp thuận; cột KHÔNG lưu địa chỉ IP trực tiếp.<br><sub>Cơ chế: SHA-256 KHÔNG khoá trên `ip|user_id` (routers/auth.py). Muối theo người dùng nên hai tài khoản cùng IP cho hai bản băm khác nhau — cố ý, vì bằng chứng chấp thuận là của TỪNG người. Nhưng muối ấy nằm ngay trong cùng hàng, nên KHÔNG suy ra được rằng cột này chống truy vết: xem ghi chú ở audit_log.ip_hash và docs/10-issues/KNOWN_ISSUES.md</sub> |
| 7 | `user_agent` | `text` | ✓ | — | — | — | Chuỗi user-agent lúc chấp thuận. |
| 8 | `withdrawn_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm rút chấp thuận.<br><sub>Rút là rút: bản ghi không bị xoá, nhưng hiệu lực chấm dứt từ mốc này</sub> |
| 9 | `source` | `text` | — | — | `'user'::text` | — | Nguồn bản ghi: `user`, `backfill` hoặc `import`.<br><sub>MIỀN CHO PHÉP do ck_user_consents_source quy định: user, backfill, import. QUAN SÁT trên sản xuất: hiện chỉ có `user` và `backfill`. Đây là lý do tên quan hệ dùng 'anchors' chứ không 'signs'</sub> |
| 10 | `note` | `text` | — | — | `''::text` | — | Ghi chú kèm bản ghi chấp thuận. |
| 11 | `recorded_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã GHI bản ghi này.<br><sub>NULL khi chính người dùng tự chấp thuận qua giao diện</sub> |

## F. Training & Evaluation

### `training_job_classes` — 5 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `job_id` | `text` | — | PK FK | — | `training_jobs.job_id` | Lượt huấn luyện mà ánh xạ lớp này thuộc về. |
| 2 | `class_idx` | `integer` | — | PK | — | — | Chỉ số lớp trong không gian nhãn CỦA RIÊNG lượt huấn luyện này.<br><sub>Là hợp đồng đầu ra của job, đọc lại theo đúng thứ tự chỉ số. Không phải `classes.class_idx` của danh mục. Cùng `job_id` tạo thành KHOÁ CHÍNH (training_job_classes_pkey), nên mỗi job không có hai dòng cùng chỉ số</sub> |
| 3 | `class_uid` | `text` | ✓ | FK | — | `classes.class_uid` | Lớp VSL nguồn tương ứng, nếu ánh xạ còn gắn được với lớp hiện hành.<br><sub>Tra ngược từ `label` TẠI THỜI ĐIỂM GHI và để NULL nếu không khớp. Đây là đường dẫn tiện lợi về danh mục, được phép mất khi lớp bị xoá — `label` mới là hợp đồng</sub> |
| 4 | `label` | `text` | — | — | — | — | Nhãn lớp, chụp lại tại thời điểm huấn luyện. Đây LÀ hợp đồng đầu ra.<br><sub>Một nhãn không tra được về danh mục vẫn phải lưu; vì thế nó NOT NULL còn class_uid thì không</sub> |
| 5 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` | Tổ chức xác định phạm vi của ánh xạ lớp huấn luyện. |

### `training_jobs` — 19 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `job_id` | `text` | — | PK | — | — | Định danh lượt huấn luyện. |
| 2 | `status` | `text` | — | — | — | — | Trạng thái vòng đời: `queued`, `running`, `completed`, `failed` hoặc `cancelled`.<br><sub>Không có CHECK nào ràng tập này; nó đến từ mã. Trên sản xuất hiện có completed, failed, cancelled — hai giá trị kia là trạng thái tạm</sub> |
| 3 | `model_type` | `text` | ✓ | — | — | — | Kiến trúc mô hình của lượt huấn luyện.<br><sub>Đối chiếu với `model.get_model_name()` lúc nạp lại điểm lưu; mặc định TCN khi điểm lưu không khai</sub> |
| 4 | `config` | `jsonb` | ✓ | — | — | — | Cấu hình huấn luyện đã dùng, dạng JSON.<br><sub>Đọc lại bằng `TrainingConfig(**config_raw)`, nên hình dạng do lớp ấy quy định chứ không tự do</sub> |
| 5 | `auth_user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản được ghi nhận là tác nhân của lượt huấn luyện.<br><sub>Có thể NULL. Catalog không chứng minh hành động cụ thể (khởi chạy, yêu cầu…), nên mô tả dừng ở 'tác nhân'</sub> |
| 6 | `created_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm tạo lượt huấn luyện. |
| 7 | `started_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm bắt đầu thực thi; NULL khi chưa chạy. |
| 8 | `completed_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm kết thúc thực thi; NULL khi chưa xong. |
| 9 | `current_epoch` | `integer` | — | — | `0` | — | Epoch đang chạy, đếm từ 1.<br><sub>Vòng lặp huấn luyện là `range(1, cfg.epochs + 1)` — MỘT-based, không phải zero-based</sub> |
| 10 | `total_epochs` | `integer` | — | — | `0` | — | Tổng số epoch dự kiến. |
| 11 | `checkpoint_path` | `text` | ✓ | — | — | — | Đường dẫn tệp điểm lưu mô hình sau khi huấn luyện.<br><sub>Là đường dẫn tệp, không phải khoá kho đối tượng: `load_checkpoint()` mở trực tiếp. Có đường dự phòng khi bộ chạy không trả về đường dẫn</sub> |
| 12 | `test_acc` | `real` | ✓ | — | — | — | Độ chính xác trên tập kiểm tra, thang **0..1**.<br><sub>Tính bằng số dự đoán đúng chia tổng mẫu, không nhân 100. Đọc từ điểm lưu ở cấp job</sub> |
| 13 | `test_f1` | `real` | ✓ | — | — | — | F1 **macro** trên tập kiểm tra, thang 0..1.<br><sub>`macro_f1` tính F1 từng lớp rồi lấy trung bình KHÔNG trọng số, nên lớp hiếm có trọng lượng ngang lớp phổ biến</sub> |
| 14 | `error_message` | `text` | ✓ | — | — | — | Lý do lượt huấn luyện thất bại hoặc bị huỷ. |
| 15 | `promoted_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm quản trị viên đưa mô hình này lên phục vụ nhận dạng thời gian thực. |
| 16 | `evaluation` | `jsonb` | ✓ | — | — | — | Kết quả đánh giá bổ sung, dạng JSON.<br><sub>NULL với các job chạy trước khi tính năng đánh giá được thêm; giao diện phải chịu được điều đó</sub> |
| 17 | `superseded_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm một lượt thăng hạng SAU cho cùng phương ngữ chiếm chỗ phục vụ.<br><sub>Mỗi phương ngữ chỉ có MỘT chỗ phục vụ, nên 'đang phục vụ' = promoted_at có giá trị VÀ superseded_at còn trống. Riêng promoted_at không trả lời được câu hỏi ấy</sub> |
| 18 | `tenant_id` | `text` | — | FK | — | `(tenant_id, registry_version)` → `registry_versions(tenant_id, version)`<br>`tenants.tenant_id` | Tổ chức xác định phạm vi của lượt huấn luyện. |
| 19 | `registry_version` | `bigint` | ✓ | FK | — | `(tenant_id, registry_version)` → `registry_versions(tenant_id, version)` | Phiên bản registry của chính tổ chức, neo vào lượt huấn luyện để lưu nguồn gốc không gian từ vựng tại thời điểm chạy.<br><sub>NULL khi lượt huấn luyện không gắn phiên bản. Khoá ngoại ghép `(tenant_id, registry_version)` nên phiên bản phải thuộc đúng tổ chức ấy — cho biết ảnh chụp từ vựng NÀO gắn với lượt chạy, thay vì chỉ biết chạy lúc nào</sub> |

### `training_metrics` — 9 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `job_id` | `text` | — | PK FK | — | `(tenant_id, job_id)` → `training_jobs(tenant_id, job_id)`<br>`training_jobs.job_id` | Lượt huấn luyện mà bản ghi chỉ số thuộc về.<br><sub>Có HAI khoá ngoại tới training_jobs: khoá một cột (di sản) và khoá ghép `(tenant_id, job_id)` tenant-aware. Cả hai đều CASCADE</sub> |
| 2 | `epoch` | `integer` | — | PK | — | — | Epoch mà bộ chỉ số này được ghi, đếm từ 1.<br><sub>Cùng gốc đếm với `training_jobs.current_epoch`. `(job_id, epoch)` là KHOÁ CHÍNH của bảng (training_metrics_pkey), không phải một chỉ mục duy nhất riêng; ghi lại cùng epoch thì bỏ qua</sub> |
| 3 | `train_loss` | `real` | ✓ | — | — | — | Loss trên dữ liệu huấn luyện tại epoch.<br><sub>Hàm loss là entropy chéo (`nn.CrossEntropyLoss`)</sub> |
| 4 | `train_acc` | `real` | ✓ | — | — | — | Độ chính xác trên dữ liệu huấn luyện tại epoch, thang **0..1**. |
| 5 | `val_loss` | `real` | ✓ | — | — | — | Loss trên dữ liệu kiểm định tại epoch.<br><sub>Cùng hàm entropy chéo</sub> |
| 6 | `val_acc` | `real` | ✓ | — | — | — | Độ chính xác trên dữ liệu kiểm định tại epoch, thang **0..1**. |
| 7 | `val_f1` | `real` | ✓ | — | — | — | F1 **macro** trên dữ liệu kiểm định tại epoch, thang 0..1.<br><sub>Cùng `macro_f1` với test_f1: trung bình không trọng số trên các lớp</sub> |
| 8 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm ghi bản ghi chỉ số. |
| 9 | `tenant_id` | `text` | — | FK | — | `(tenant_id, job_id)` → `training_jobs(tenant_id, job_id)`<br>`tenants.tenant_id` | Tổ chức xác định phạm vi của chỉ số.<br><sub>SUY RA từ hàng job cha ngay trong câu INSERT, không nhận từ người gọi: thẩm quyền của đầu ra phải là hàng job đã lưu, không phải điều lượt gọi tuyên bố. Job không tồn tại thì lượt ghi lặng lẽ không làm gì, thay vì tạo chỉ số mồ côi</sub> |

## G. Plan, Billing & Storage

### `plans` — 25 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `plan_code` | `text` | — | PK | — | — | Mã gói, ổn định và là thứ mọi phép cưỡng chế tra theo.<br><sub>Không sửa được lúc chạy: nó là khoá chính và có khoá ngoại từ `tenants` lẫn `tenant_subscriptions` trỏ tới</sub> |
| 2 | `display_name` | `text` | — | — | — | — | Tên gói hiển thị cho người dùng. |
| 3 | `description` | `text` | — | — | `''::text` | — | Mô tả gói cho bảng giá. |
| 4 | `max_seats` | `integer` | ✓ | — | — | — | Giá trị số thành viên khai trong cấu hình gói.<br><sub>Giá trị được khai trong cấu hình gói; HIỆN CHƯA có cổng nào cưỡng chế. Xem `plans.PLAN_LIMIT_ENFORCEMENT` — API trả cờ này ra để giao diện không trình bày nó như một cam kết. CHECK ck_plans_limits_non_negative cấm giá trị âm cho nhóm trần gốc. Gỡ khỏi `USAGE_METRICS` ở v8: số thành viên thuộc mặt phẳng phân quyền, ở đó vì lý do bảo mật chứ không vì lý do thương mại</sub> |
| 5 | `max_samples` | `integer` | ✓ | — | — | — | Giá trị số mẫu khai trong cấu hình gói.<br><sub>Giá trị được khai trong cấu hình gói; HIỆN CHƯA có cổng nào cưỡng chế. Xem `plans.PLAN_LIMIT_ENFORCEMENT` — API trả cờ này ra để giao diện không trình bày nó như một cam kết. Gỡ ở v8 vì `samples` và `classes` là hai cách nói về cùng một tài nguyên. VẪN được `workspace_admin.ALLOCATABLE_METRICS` đọc để chia cho từng project — xem mục OPEN trong docs/10-issues/KNOWN_ISSUES.md</sub> |
| 6 | `max_storage_mb` | `integer` | ✓ | — | — | — | Trần dung lượng dữ liệu của tổ chức, tính bằng MB. **Đang được cưỡng chế**.<br><sub>Hạn mức DỮ LIỆU duy nhất từ v8. Cưỡng chế đồng bộ ở mọi đường ghi qua `app/storage_quota.py`; NULL nghĩa là không giới hạn</sub> |
| 7 | `max_classes` | `integer` | ✓ | — | — | — | Giá trị số lớp khai trong cấu hình gói.<br><sub>Giá trị được khai trong cấu hình gói; HIỆN CHƯA có cổng nào cưỡng chế. Xem `plans.PLAN_LIMIT_ENFORCEMENT` — API trả cờ này ra để giao diện không trình bày nó như một cam kết. Gỡ ở v8 cùng lý do với `max_samples`</sub> |
| 8 | `max_training_jobs_per_month` | `integer` | ✓ | — | — | — | Giá trị số lượt huấn luyện mỗi tháng khai trong cấu hình gói.<br><sub>Giá trị được khai trong cấu hình gói; HIỆN CHƯA có cổng nào cưỡng chế. Xem `plans.PLAN_LIMIT_ENFORCEMENT` — API trả cờ này ra để giao diện không trình bày nó như một cam kết. Gỡ ở v8: chặn theo SỐ LẦN phạt người chạy nhiều job nhỏ và tha người chạy ít job nặng, trong khi thứ tốn kém là compute. Vẫn được màn hình cấp phát project đọc</sub> |
| 9 | `max_concurrent_training_jobs` | `integer` | ✓ | — | `1` | — | Số lượt huấn luyện được chạy đồng thời. **Đang được cưỡng chế**, nhưng là kiểm soát AN TOÀN VẬN HÀNH cho bộ chạy GPU, không phải hạn mức thương mại.<br><sub>Job vượt mức vào hàng đợi chứ không bị từ chối. Đừng đem lên bảng giá</sub> |
| 10 | `max_queued_training_jobs` | `integer` | ✓ | — | `3` | — | Số lượt huấn luyện được xếp hàng. **Đang được cưỡng chế**, cũng là kiểm soát an toàn vận hành. |
| 11 | `max_api_keys` | `integer` | ✓ | — | `0` | — | Trần số khoá API còn hiệu lực. **Đang được cưỡng chế**.<br><sub>`plans.check_quota` đếm khoá chưa thu hồi trên bảng nguồn</sub> |
| 12 | `max_webhook_endpoints` | `integer` | ✓ | — | `0` | — | Trần số webhook đang bật. **Đang được cưỡng chế**.<br><sub>`plans.check_quota` đếm trên bảng nguồn</sub> |
| 13 | `price_cents` | `bigint` | ✓ | — | `0` | — | Giá NIÊM YẾT của gói, theo đơn vị nhỏ nhất của `currency`.<br><sub>Hệ thống KHÔNG có bộ xử lý thanh toán: không hoá đơn, không cổng thanh toán, không ghi nhận giao dịch. Đây là cấu hình bảng giá, không phải số tiền đã hoặc sẽ thu. NULL nghĩa là CHƯA CÔNG BỐ, khác 0 là miễn phí</sub> |
| 14 | `currency` | `text` | — | — | `'VND'::text` | — | Đơn vị tiền của giá niêm yết; mặc định VND.<br><sub>VND không có đơn vị lẻ, nên `price_cents` với tiền Việt thực chất là số đồng</sub> |
| 15 | `billing_period` | `text` | — | — | `'monthly'::text` | — | Chu kỳ tính phí khai cho gói; mặc định `monthly`.<br><sub>MIỀN CHO PHÉP do ck_plans_billing_period quy định. Là cấu hình thương mại. Chu kỳ được `subscription_lifecycle` dùng để đặt kỳ hạn và nhắc hạn — KHÔNG để thu tiền</sub> |
| 16 | `is_self_serve` | `boolean` | — | — | `false` | — | Gói này có cho tổ chức tự đăng ký hay không.<br><sub>Đường tự đăng ký đòi cờ này bật; `tenant_admin` từ chối nếu không</sub> |
| 17 | `is_listed` | `boolean` | — | — | `true` | — | Gói có hiện trên bảng giá công khai hay không.<br><sub>Gói của tenant nền tảng không lộ ra nhờ cờ này</sub> |
| 18 | `trial_days` | `integer` | — | — | `0` | — | Số ngày dùng thử khi mở kỳ hạn đầu tiên. |
| 19 | `sort_order` | `integer` | — | — | `0` | — | Thứ tự hiển thị trên bảng giá. |
| 20 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo gói. |
| 21 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm sửa gói gần nhất.<br><sub>Gói sửa được lúc chạy qua `PATCH /billing/plans/{code}`; seed dùng ON CONFLICT DO NOTHING nên một lượt triển khai lại không ghi đè chỉnh tay</sub> |
| 26 | `max_workspaces` | `integer` | ✓ | — | — | — | Giá trị số workspace khai trong cấu hình gói.<br><sub>Giá trị được khai trong cấu hình gói; HIỆN CHƯA có cổng nào cưỡng chế. Xem `plans.PLAN_LIMIT_ENFORCEMENT` — API trả cờ này ra để giao diện không trình bày nó như một cam kết. CHECK ck_plans_v6_limits_non_negative cấm giá trị âm cho nhóm trần v6 (max_workspaces, max_projects và các trần cùng đợt)</sub> |
| 27 | `max_projects` | `integer` | ✓ | — | — | — | Giá trị số project khai trong cấu hình gói.<br><sub>Giá trị được khai trong cấu hình gói; HIỆN CHƯA có cổng nào cưỡng chế. Xem `plans.PLAN_LIMIT_ENFORCEMENT` — API trả cờ này ra để giao diện không trình bày nó như một cam kết.</sub> |
| 28 | `included_training_credits` | `integer` | ✓ | — | — | — | Lượng tín dụng huấn luyện được KÈM THEO gói.<br><sub>Là một khoản ĐƯỢC CẤP, không phải một trần — nên không mô tả bằng chữ 'tối đa'. Giá trị được khai trong cấu hình gói; HIỆN CHƯA có cổng nào cưỡng chế. Xem `plans.PLAN_LIMIT_ENFORCEMENT` — API trả cờ này ra để giao diện không trình bày nó như một cam kết.</sub> |
| 29 | `audit_retention_days` | `integer` | ✓ | — | — | — | Số ngày giữ nhật ký kiểm toán khai trong cấu hình gói.<br><sub>Giá trị được khai trong cấu hình gói; HIỆN CHƯA có cổng nào cưỡng chế. Xem `plans.PLAN_LIMIT_ENFORCEMENT` — API trả cờ này ra để giao diện không trình bày nó như một cam kết. Chưa có cơ chế dọn nào đọc giá trị này</sub> |

### `storage_reservations` — 5 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `reservation_id` | `uuid` | — | PK | — | — | Định danh một khoản giữ chỗ đang bay.<br><sub>Có định danh chứ không phải một cột đếm, và đó là điểm mấu chốt: một tiến trình chết giữa chừng để lại khoản treo phân biệt được với lượt tải đang chạy thật</sub> |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` | Tổ chức mà khoản giữ chỗ thuộc về. |
| 3 | `bytes` | `bigint` | — | — | — | — | Số byte tạm giữ cho một lượt ghi CHƯA hoàn tất.<br><sub>CHECK ck_storage_reservations_not_negative cấm giá trị âm. Phép nhận việc hỏi `đã dùng + đang giữ chỗ + sắp tới <= trần`, nên tổng các khoản này tham gia quyết định hạn mức dù chưa byte nào chạm đĩa. Đây là cách chống đua khi nhiều lượt tải cùng lúc</sub> |
| 4 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm giữ chỗ. |
| 5 | `expires_at` | `timestamp with time zone` | — | — | — | — | Thời điểm khoản giữ chỗ hết hiệu lực.<br><sub>Khoản quá hạn KHÔNG còn tính vào tổng đang giữ, kể cả trước khi lượt quét dọn nó — nếu không, một tiến trình chết sẽ giam chỗ của tổ chức tới hôm sau</sub> |

### `tenant_storage` — 4 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `tenant_id` | `text` | — | PK FK | — | `tenants.tenant_id` | Tổ chức sở hữu bộ đếm. Vừa là khoá chính vừa là khoá ngoại, nên mỗi tổ chức có tối đa MỘT dòng. |
| 2 | `bytes_used` | `bigint` | — | — | `0` | — | Số byte ĐÃ nằm trên đĩa theo bộ đếm — phần đã quyết toán.<br><sub>CHECK ck_tenant_storage_not_negative cấm giá trị âm — bộ đếm không tụt xuống dưới 0 dù lượt gỡ có trừ quá tay. Khác `storage_reservations.bytes` (đang giữ chỗ, chưa chạm đĩa). Là bản gần đúng cho tốc độ: sự thật là lượt đi bộ đĩa, và `reconcile()` ghi đè theo đĩa khi lệch</sub> |
| 3 | `reconciled_at` | `timestamp with time zone` | ✓ | — | — | — | Lần gần nhất bộ đếm được dựng lại từ lượt đi bộ đĩa thật.<br><sub>Lượt đối chiếu đếm ba nguồn tính phí: cây `features/`, kho `raw/`, và video thô quy chủ theo hàng `raw_uploads`</sub> |
| 4 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm bộ đếm thay đổi gần nhất. |

### `tenant_subscriptions` — 15 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `subscription_id` | `uuid` | — | PK | — | — | Định danh một dòng lịch sử đăng ký. |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` | Tổ chức mà dòng lịch sử này thuộc về. |
| 3 | `plan_code` | `text` | — | FK | — | `plans.plan_code` | Gói được chọn tại dòng lịch sử này.<br><sub>KHÔNG phải gói hiện hành: nguồn đọc của mọi phép cưỡng chế là `tenants.plan_code`. Bảng này ghi CHUỖI thay đổi</sub> |
| 4 | `status` | `text` | — | — | `'active'::text` | — | Trạng thái của dòng đăng ký.<br><sub>Dòng cũ chuyển sang `superseded` khi đổi gói. LƯU Ý: ràng buộc 'mỗi tổ chức tối đa một dòng đang mở' nằm ở `ended_at`, KHÔNG ở cột này — uq_tenant_subscriptions_open có predicate `ended_at IS NULL` và không đọc `status`</sub> |
| 5 | `started_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm dòng đăng ký này bắt đầu. |
| 6 | `ended_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm dòng đăng ký này kết thúc; NULL khi đang mở.<br><sub>Là cột QUYẾT ĐỊNH dòng nào còn mở: chỉ mục duy nhất MỘT PHẦN uq_tenant_subscriptions_open trên `tenant_id` có predicate `ended_at IS NULL`, nên mỗi tổ chức có tối đa MỘT dòng chưa kết thúc. Predicate KHÔNG nhìn `status`</sub> |
| 7 | `changed_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản thực hiện lượt đổi gói. |
| 8 | `note` | `text` | — | — | `''::text` | — | Ghi chú kèm lượt đổi gói. |
| 9 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm ghi dòng. |
| 10 | `current_period_start` | `timestamp with time zone` | ✓ | — | — | — | Đầu kỳ hạn hiện tại. |
| 11 | `current_period_end` | `timestamp with time zone` | ✓ | — | — | — | Cuối kỳ hạn hiện tại; là mốc để nhắc hạn, mở kỳ mới và tính ân hạn. |
| 12 | `auto_renew` | `boolean` | — | — | `true` | — | Kỳ hạn có tự mở lại khi hết hạn hay không. |
| 13 | `grace_until` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm hết ân hạn sau khi kỳ hạn kết thúc; NULL khi chưa vào ân hạn.<br><sub>Đặt lại về NULL mỗi khi mở kỳ hạn mới</sub> |
| 14 | `trial_ends_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm hết dùng thử. |
| 15 | `last_reminder_days` | `integer` | ✓ | — | — | — | MỐC NHẮC ĐÃ GỬI, tính bằng số ngày còn lại tại lần nhắc đó.<br><sub>KHÔNG phải số ngày còn lại hiện tại. Các mốc là (7, 3, 1) ngày; cột giữ mốc gần nhất đã gửi để không nhắc trùng, và về NULL khi mở kỳ hạn mới</sub> |

### `tenant_usage_daily` — 5 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `tenant_id` | `text` | — | PK FK | — | `tenants.tenant_id` | Tổ chức của số đo. |
| 2 | `usage_date` | `date` | — | PK | — | — | Ngày của số đo, theo **UTC**.<br><sub>Lượt gộp lấy ngày hôm qua theo `datetime.now(timezone.utc)`</sub> |
| 3 | `metric` | `text` | — | PK | — | — | Tên chỉ số: `samples_created`, `raw_uploads_created`, `training_jobs_started`, `training_seconds`, `storage_mb`, `active_users`.<br><sub>Đo trên sản xuất, khớp `usage._ROLLUPS`</sub> |
| 4 | `value` | `bigint` | — | — | `0` | — | Giá trị chỉ số của ngày đó.<br><sub>Bảng này phục vụ BÁO CÁO, không phải cưỡng chế: `plans.check_quota` đếm thẳng trên bảng nguồn chứ không đọc ở đây. `storage_mb` là số đo TẠI THỜI ĐIỂM, nên cộng dồn nhiều ngày lại là vô nghĩa — `usage_totals` lấy giá trị cuối</sub> |
| 5 | `computed_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm số đo được tính.<br><sub>Mọi câu gộp là `INSERT ... ON CONFLICT DO UPDATE`, nên chạy lại cùng một ngày cho ra đúng một kết quả</sub> |

## H. Integration & Operations

### `event_outbox` — 11 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `event_id` | `uuid` | — | PK | `gen_random_uuid()` | — | Định danh một sự kiện trong sổ phát. |
| 2 | `tenant_id` | `text` | ✓ | FK | — | `tenants.tenant_id` | Tổ chức phát sinh sự kiện; NULL với sự kiện cấp nền tảng. |
| 3 | `event_type_code` | `text` | — | — | — | — | Mã loại sự kiện.<br><sub>CHECK ck_event_outbox_type_not_blank cấm chuỗi rỗng. Thuộc KHÔNG GIAN TÊN sự kiện NỘI BỘ, không đồng nhất với `webhook_deliveries.event_type` (không gian nghiệp vụ, khai ở `webhooks.EVENT_TYPES`). Hiện chỉ có `authorization.policy.changed`, dùng để vô hiệu hoá bộ nhớ đệm quyền giữa các tiến trình API. Đường webhook KHÔNG đọc bảng này: `deliver_webhooks` chỉ quét `webhook_deliveries`</sub> |
| 4 | `payload` | `jsonb` | — | — | `'{}'::jsonb` | — | Dữ liệu kèm sự kiện, dạng JSON. |
| 5 | `occurred_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm sự kiện XẢY RA — mốc mà mỗi tiến trình đọc dùng để biết mình đã nạp tới đâu.<br><sub>Đây là cột thực sự điều khiển cơ chế hiện tại, không phải `dispatch_status`</sub> |
| 6 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm ghi dòng. |
| 7 | `dispatch_status` | `text` | — | — | `'PENDING'::text` | — | Trạng thái phát, mặc định `PENDING`. **`CẦN DUYỆT`**<br><sub>MIỀN CHO PHÉP do ck_event_outbox_status quy định: PENDING, IN_FLIGHT, DONE, FAILED. Miền thì biết, NGƯỜI GHI thì không: không đường mã hiện hành nào đặt cột này. Vòng đời dự kiến — ai chuyển sang IN_FLIGHT/DONE/FAILED — cần tác giả xác nhận</sub> |
| 8 | `attempts` | `integer` | — | — | `0` | — | Số lần thử phát. **`CẦN DUYỆT`**<br><sub>CHECK ck_event_outbox_attempts cấm giá trị âm. Không đường mã hiện hành nào TĂNG cột này; `policy_invalidator` không đếm số lần thử</sub> |
| 9 | `available_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm sớm nhất được thử phát lại. **`CẦN DUYỆT`**<br><sub>Chưa có đường đọc lẫn đường ghi hiện hành. Ngữ nghĩa xếp lịch — cột này chặn lượt thử lại theo cách nào — chưa xác nhận</sub> |
| 10 | `processed_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm sự kiện được xử lý xong. **`CẦN DUYỆT`**<br><sub>Bộ đọc hiện hành CỐ Ý không đánh dấu cột này, và lý do nằm trong mã: sự kiện được PHÁT TOẢ cho nhiều tiến trình API, nên tiến trình đầu tiên đánh dấu sẽ 'tiêu thụ' mất sự kiện và các tiến trình còn lại không bao giờ thấy nó. Ngữ nghĩa 'một người tiêu thụ đã xong' trong thiết kế outbox đầy đủ chưa được triển khai và chưa xác nhận</sub> |
| 11 | `last_error` | `text` | ✓ | — | — | — | Lỗi của lần phát gần nhất. **`CẦN DUYỆT`**<br><sub>Không đường mã hiện hành nào ghi cột này. Nguồn lỗi và thời điểm ghi chưa xác nhận</sub> |

### `google_sheets_sync_status` — 7 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `id` | `integer` | — | PK | `nextval('google_sheets_sync_status_id_seq'::`… | — | Định danh dòng trạng thái đồng bộ. `LEGACY`<br><sub>Con trỏ của cơ chế đồng bộ CŨ. `get_sync_status`/`upsert_sync_status` không còn đường gọi nào; quan sát tại lượt rà 26/08/2026: hàng duy nhất (`samples`) đứng yên từ 11/07/2026 trong khi lượt export vẫn chạy và theo dõi vị trí bằng tệp mốc `.samples_sheet.synced`.</sub> |
| 2 | `table_name` | `character varying(50)` | — | — | — | — | Bảng nguồn mà con trỏ này theo dõi. `LEGACY`<br><sub>Con trỏ của cơ chế đồng bộ CŨ. `get_sync_status`/`upsert_sync_status` không còn đường gọi nào; quan sát tại lượt rà 26/08/2026: hàng duy nhất (`samples`) đứng yên từ 11/07/2026 trong khi lượt export vẫn chạy và theo dõi vị trí bằng tệp mốc `.samples_sheet.synced`.</sub> |
| 3 | `current_spreadsheet_id` | `character varying(100)` | — | — | `''::character varying` | — | Định danh **bảng tính Google** đang được ghi vào — không phải thư mục Drive. `LEGACY`<br><sub>Con trỏ của cơ chế đồng bộ CŨ. `get_sync_status`/`upsert_sync_status` không còn đường gọi nào; quan sát tại lượt rà 26/08/2026: hàng duy nhất (`samples`) đứng yên từ 11/07/2026 trong khi lượt export vẫn chạy và theo dõi vị trí bằng tệp mốc `.samples_sheet.synced`.</sub> |
| 4 | `current_sheet_index` | `integer` | — | — | `1` | — | Chỉ số trang tính hiện tại, đếm từ 1. `LEGACY`<br><sub>Con trỏ của cơ chế đồng bộ CŨ. `get_sync_status`/`upsert_sync_status` không còn đường gọi nào; quan sát tại lượt rà 26/08/2026: hàng duy nhất (`samples`) đứng yên từ 11/07/2026 trong khi lượt export vẫn chạy và theo dõi vị trí bằng tệp mốc `.samples_sheet.synced`. Mặc định 1; quy ước đánh số của cơ chế cũ chưa xác nhận được độc lập — không caller nào còn lại để chứng minh</sub> |
| 5 | `current_data_rows` | `integer` | — | — | `0` | — | Số dòng dữ liệu đã ghi trong trang tính hiện tại. `LEGACY`<br><sub>Con trỏ của cơ chế đồng bộ CŨ. `get_sync_status`/`upsert_sync_status` không còn đường gọi nào; quan sát tại lượt rà 26/08/2026: hàng duy nhất (`samples`) đứng yên từ 11/07/2026 trong khi lượt export vẫn chạy và theo dõi vị trí bằng tệp mốc `.samples_sheet.synced`.</sub> |
| 6 | `max_rows_per_sheet` | `integer` | — | — | `500000` | — | Ngưỡng dòng mỗi trang tính trước khi chuyển trang; mặc định 500.000. **`CẦN DUYỆT`**<br><sub>Con trỏ của cơ chế đồng bộ CŨ. `get_sync_status`/`upsert_sync_status` không còn đường gọi nào; quan sát tại lượt rà 26/08/2026: hàng duy nhất (`samples`) đứng yên từ 11/07/2026 trong khi lượt export vẫn chạy và theo dõi vị trí bằng tệp mốc `.samples_sheet.synced`. Chưa xác nhận đây là ngưỡng an toàn nội bộ hay giới hạn của Google Sheets</sub> |
| 7 | `updated_at` | `timestamp with time zone` | ✓ | — | `now()` | — | Thời điểm con trỏ được cập nhật gần nhất. `LEGACY`<br><sub>Con trỏ của cơ chế đồng bộ CŨ. `get_sync_status`/`upsert_sync_status` không còn đường gọi nào; quan sát tại lượt rà 26/08/2026: hàng duy nhất (`samples`) đứng yên từ 11/07/2026 trong khi lượt export vẫn chạy và theo dõi vị trí bằng tệp mốc `.samples_sheet.synced`.</sub> |

### `notifications` — 10 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `notification_id` | `uuid` | — | PK | `gen_random_uuid()` | — | Định danh thông báo. |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` | Ngữ cảnh tổ chức của thông báo.<br><sub>Bất biến NGHIỆP VỤ 'người nhận thuộc tổ chức này' KHÔNG được khoá ngoại cưỡng chế: hai khoá ngoại tới `tenants` và `users` là riêng rẽ, không có khoá ghép nối chúng. Và `notifications.notify()` cũng không kiểm tư cách thành viên — người gọi cung cấp cả hai giá trị. Hậu quả dưới RLS là mất im lặng chứ không phải rò rỉ: một dòng gắn nhầm tổ chức sẽ VÔ HÌNH với chính người nhận. Một khoá ngoại ghép sang `users` cũng không giải được, vì một người có thể thuộc nhiều tổ chức — thẩm quyền nằm ở Membership</sub> |
| 3 | `user_id` | `uuid` | — | FK | — | `users.id` | Tài khoản NHẬN thông báo. |
| 4 | `kind` | `text` | — | — | — | — | Loại thông báo.<br><sub>Đo trên sản xuất: `security`, `support`</sub> |
| 5 | `title` | `text` | — | — | — | — | Tiêu đề thông báo. |
| 6 | `body` | `text` | — | — | `''::text` | — | Nội dung thông báo. |
| 7 | `link` | `text` | ✓ | — | — | — | Đường dẫn trong ứng dụng để người nhận mở thứ liên quan. |
| 8 | `severity` | `text` | — | — | `'info'::text` | — | Mức độ nghiêm trọng: `info`, `success`, `warning` hoặc `critical`.<br><sub>MIỀN CHO PHÉP do notifications_severity_valid quy định. QUAN SÁT trên sản xuất: hiện chỉ có `info` và `critical`</sub> |
| 9 | `read_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm người nhận đã đọc; NULL khi chưa đọc. |
| 10 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm phát thông báo. |

### `platform_settings` — 4 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `key` | `text` | — | PK | — | — | Khoá cấu hình cấp nền tảng.<br><sub>Danh sách trắng ở `platform_settings.EDITABLE`, không phải bảng tự do: mỗi khoá khai kiểu, khoảng giá trị và nhãn</sub> |
| 2 | `value` | `text` | — | — | — | — | Giá trị cấu hình, lưu dưới dạng VĂN BẢN.<br><sub>Kiểu thật do `EDITABLE[key]['type']` quy định và được kiểm khoảng khi ghi; cột chỉ là nơi chứa</sub> |
| 3 | `updated_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản sửa cấu hình gần nhất. |
| 4 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm sửa gần nhất. |

### `schema_migrations` — 6 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `version` | `integer` | — | PK | — | — | Phiên bản lược đồ mà lượt áp này đưa cơ sở dữ liệu tới.<br><sub>Cùng với `applied_at` tạo thành khoá chính, nên MỘT phiên bản có NHIỀU dòng: mỗi lượt chạy migration đóng một dấu mới. Bảng là LỊCH SỬ ÁP, không phải trạng thái hiện tại</sub> |
| 2 | `applied_at` | `timestamp with time zone` | — | PK | `now()` | — | Thời điểm lượt áp. |
| 3 | `applied_by` | `text` | — | — | — | — | Vai cơ sở dữ liệu đã chạy lượt áp.<br><sub>Lấy bằng `SELECT current_user`, nên là danh tính CSDL chứ không phải tài khoản ứng dụng</sub> |
| 4 | `applied_on` | `text` | ✓ | — | — | — | Danh tính MÁY đã chạy lệnh.<br><sub>Danh tính máy chạy lượt áp, lấy từ biến môi trường của môi trường triển khai; dùng làm xuất xứ của lượt áp. Khi một lượt migration chạy từ chỗ không ai ngờ, cột này là thứ nói ra điều đó</sub> |
| 5 | `note` | `text` | ✓ | — | — | — | Ghi chú người vận hành kèm lượt áp. |
| 6 | `migration_checksum` | `text` | ✓ | — | — | — | Băm SHA-256 của payload migration theo chiều NÂNG CẤP (forward/up) của phiên bản ấy.<br><sub>Sinh ra để phát hiện việc SỬA một migration ĐÃ ÁP. `storage.schema_version.assert_startup_compatible` (gọi từ `app/db.py` lúc khởi động) ném khi checksum LỆCH, nên backend từ chối khởi động — fail-closed. Checksum THIẾU thì chỉ cảnh báo, vì chính lượt triển khai mang cột này lên sẽ tự làm sập sản xuất nếu chặn; đường chặn cho trường hợp ấy nằm ở `app.cli.migrate`, chạy TRƯỚC khi stack lên. Giá trị NULL KHÔNG được tự điền — 'nếu NULL thì ghi giá trị hiện tại' sẽ khiến một migration đã bị sửa tự hợp thức hoá; xác nhận một lần bằng `--adopt-checksum`</sub> |

### `support_messages` — 9 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `message_id` | `uuid` | — | PK | `gen_random_uuid()` | — | Định danh tin nhắn trong phiếu. |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` | Tổ chức giữ tin nhắn.<br><sub>Không dư thừa dù suy được qua phiếu: đây là phạm vi TRỰC TIẾP mà RLS bám vào</sub> |
| 3 | `ticket_id` | `uuid` | — | FK | — | `support_tickets.ticket_id` | Phiếu chứa tin nhắn này. |
| 4 | `author_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản viết tin nhắn; NULL khi tác giả không phải người. |
| 5 | `author_label` | `text` | — | — | — | — | Nhãn tác giả, chụp lại TẠI THỜI ĐIỂM GỬI.<br><sub>Không chạy theo tên hiện tại: một cuộc trao đổi hỗ trợ là bằng chứng lịch sử, và đọc lại phiếu cũ theo tên mới sẽ thấy những cái tên chưa từng tồn tại vào lúc đó</sub> |
| 6 | `is_staff` | `boolean` | — | — | `false` | — | Người GỬI có phải nhân viên hỗ trợ tại thời điểm gửi hay không.<br><sub>Đóng băng theo vai lúc GỬI, không lúc đọc: một người từng là quản trị viên rồi thôi vai không làm câu trả lời cũ của họ thành câu của người dùng thường. KHÔNG phải cột nghỉ hưu — vẫn được ghi ở mọi tin nhắn mới. CHECK ck_support_author_kind_matches là BẤT BIẾN HAI CỘT dạng tương đương: (author_kind = 'staff') = is_staff, nên hai cột không thể bất đồng và `bot` bắt buộc có is_staff = false</sub> |
| 7 | `body` | `text` | — | — | — | — | Nội dung tin nhắn. |
| 8 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm gửi tin nhắn. |
| 9 | `author_kind` | `text` | ✓ | — | `'user'::text` | — | Loại tác giả: `user`, `staff` hoặc `bot`.<br><sub>MIỀN CHO PHÉP do ck_support_author_kind quy định: user, staff, bot. Thêm sau `is_staff` và được lấp ngược từ cột ấy cho dòng cũ. Diễn đạt được thứ `is_staff` không diễn đạt nổi — `bot` — nên nó là nguồn chuẩn khi cần phân biệt ba loại; `admin_attention` dùng nó để bỏ qua tin của bot. CSDL còn buộc hai cột KHÔNG được bất đồng: xem ck_support_author_kind_matches ở `is_staff`</sub> |

### `support_tickets` — 10 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `ticket_id` | `uuid` | — | PK | `gen_random_uuid()` | — | Định danh phiếu hỗ trợ. |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` | Tổ chức giữ phiếu.<br><sub>Nội dung phiếu là dữ liệu của tenant; thư báo chỉ gửi cho quản trị viên của CHÍNH tổ chức ấy</sub> |
| 3 | `user_id` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã MỞ phiếu.<br><sub>Khác người viết từng tin nhắn trong phiếu</sub> |
| 4 | `subject` | `text` | — | — | — | — | Tiêu đề phiếu. |
| 5 | `category` | `text` | — | — | `'other'::text` | — | Phân loại phiếu: `account`, `billing`, `data`, `bug` hoặc `other`.<br><sub>MIỀN CHO PHÉP do support_tickets_category_valid quy định. SỬA LẠI phát biểu cũ: CSDL CÓ ràng tập này</sub> |
| 6 | `status` | `text` | — | — | `'open'::text` | — | Trạng thái phiếu: `open`, `pending`, `resolved` hoặc `closed`.<br><sub>MIỀN CHO PHÉP do support_tickets_status_valid quy định — BỐN giá trị, kể cả `closed`. QUAN SÁT trên sản xuất mới chỉ thấy ba giá trị đầu</sub> |
| 7 | `priority` | `text` | — | — | `'normal'::text` | — | Mức ưu tiên phiếu: `low`, `normal`, `high` hoặc `urgent`.<br><sub>MIỀN CHO PHÉP do support_tickets_priority_valid quy định. SỬA LẠI phát biểu cũ: CSDL CÓ ràng tập này</sub> |
| 8 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm mở phiếu. |
| 9 | `updated_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm cập nhật gần nhất. |
| 10 | `resolved_at` | `timestamp with time zone` | ✓ | — | — | — | Mốc thời gian liên quan tới việc hoàn tất xử lý phiếu. **`CẦN DUYỆT`**<br><sub>CSDL KHÔNG ràng cột này với `status = 'resolved'` cũng không với `'closed'` — mà miền cho phép cả hai là hai trạng thái riêng. Đường ghi nào đặt cột này, và nó ứng với trạng thái nào, cần xác nhận</sub> |

### `webhook_deliveries` — 12 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `delivery_id` | `uuid` | — | PK | — | — | Định danh một lượt giao. |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` | Tổ chức sở hữu lượt giao. |
| 3 | `endpoint_id` | `uuid` | — | FK | — | `webhook_endpoints.endpoint_id` | Endpoint đích của lượt giao.<br><sub>Xoá endpoint thì lịch sử giao của nó đi theo (CASCADE)</sub> |
| 4 | `event_type` | `text` | — | — | — | — | Loại sự kiện nghiệp vụ được giao.<br><sub>Tập riêng ở `webhooks.EVENT_TYPES` (sample.created, training.completed, …). KHÁC `event_outbox.event_type_code`, vốn là tín hiệu nội bộ</sub> |
| 5 | `payload` | `jsonb` | — | — | — | — | Thân yêu cầu sẽ gửi tới endpoint, dạng JSON. |
| 6 | `status` | `text` | — | — | `'pending'::text` | — | Trạng thái giao: `pending`, `delivered`, `failed` hoặc `dropped`.<br><sub>MIỀN CHO PHÉP do ck_webhook_deliveries_status quy định — BỐN giá trị, kể cả `dropped` mà mô tả cũ bỏ sót. `failed` chỉ đặt khi đã CẠN số lần thử; trước đó lượt giao vẫn là `pending`</sub> |
| 7 | `attempts` | `integer` | — | — | `0` | — | Số lần đã thử giao. 0 nghĩa là CHƯA gửi lần nào. |
| 8 | `last_status_code` | `integer` | ✓ | — | — | — | Mã HTTP của lần thử gần nhất; NULL khi lỗi mạng hoặc hết giờ. |
| 9 | `last_error` | `text` | ✓ | — | — | — | Mô tả lỗi của lần thử gần nhất, cắt còn 500 ký tự. |
| 10 | `next_attempt_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm sớm nhất được thử lại.<br><sub>Lịch chờ CỐ ĐỊNH tính bằng phút, `webhooks.RETRY_SCHEDULE_MINUTES = (1, 5, 25, 125)`, và `MAX_ATTEMPTS = len(...) + 1 = 5`. Không có jitter. Đây là chính sách RUNTIME, lược đồ không cưỡng chế gì</sub> |
| 11 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm xếp lượt giao vào hàng.<br><sub>Lượt giao được XẾP HÀNG trong request (chỉ một câu INSERT), còn việc gửi chạy ở tác vụ nền `saas_tasks.deliver_webhooks`, lịch beat mỗi phút. Nên độ trễ của endpoint khách hàng KHÔNG cộng vào thời gian chờ của thao tác nghiệp vụ đã xếp hàng — nó chiếm thời gian của worker giao. Khoảng cách created_at → lần thử đầu vì thế tối đa khoảng một phút</sub> |
| 12 | `delivered_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm giao thành công; NULL khi chưa thành công. |

### `webhook_endpoints` — 14 cột

| # | Cột | Kiểu | Null | Khoá | Mặc định | Tham chiếu | Mô tả |
|--:|---|---|:--:|:--:|---|---|---|
| 1 | `endpoint_id` | `uuid` | — | PK | — | — | Định danh endpoint. |
| 2 | `tenant_id` | `text` | — | FK | — | `tenants.tenant_id` | Tổ chức sở hữu endpoint. |
| 3 | `url` | `text` | — | — | — | — | Địa chỉ HTTP nhận sự kiện. |
| 4 | `secret` | `text` | — | — | — | — | Bí mật ký webhook, lưu ở dạng KHÔNG mã hoá (`whsec_` + 32 byte ngẫu nhiên).<br><sub>HMAC-SHA256 cần khoá KHÔI PHỤC ĐƯỢC nên không thể chỉ lưu băm một chiều — nhưng điều đó KHÔNG đòi lưu thô: `user_totp.secret_enc` cũng khôi phục được mà vẫn mã hoá bằng Fernet. Điểm riêng của cột này là bí mật đối xứng lưu KHÔNG mã hoá, và đó là vấn đề gia cố được ghi riêng ở docs/10-issues/KNOWN_ISSUES.md, không phải yêu cầu của HMAC. Đường đọc đã kiểm: `webhooks.create_endpoint` trả bí mật đúng MỘT lần lúc tạo; `webhooks.list_endpoints` loại cột này ngay ở câu SELECT nên nó không rời khỏi CSDL</sub> |
| 5 | `event_types` | `text` | — | — | `'*'::text` | — | Các loại sự kiện endpoint này đăng ký nhận. **`CẦN DUYỆT`**<br><sub>Cách biểu diễn nhiều loại và ý nghĩa của ký tự đại diện chưa xác nhận</sub> |
| 6 | `is_active` | `boolean` | — | — | `true` | — | Endpoint còn nhận sự kiện hay không.<br><sub>Lượt quét giao chỉ lấy lượt chờ của endpoint đang bật</sub> |
| 7 | `description` | `text` | — | — | `''::text` | — | Mô tả endpoint do người vận hành đặt. |
| 8 | `created_by` | `uuid` | ✓ | FK | — | `users.id` | Tài khoản đã tạo endpoint. |
| 9 | `created_at` | `timestamp with time zone` | — | — | `now()` | — | Thời điểm tạo endpoint. |
| 10 | `last_success_at` | `timestamp with time zone` | ✓ | — | — | — | Lần giao thành công gần nhất. |
| 11 | `last_failure_at` | `timestamp with time zone` | ✓ | — | — | — | Lần giao thất bại gần nhất. |
| 12 | `failure_streak` | `integer` | — | — | `0` | — | Số lần hỏng LIÊN TIẾP; về 0 ngay khi có một lượt giao thành công. |
| 13 | `disabled_at` | `timestamp with time zone` | ✓ | — | — | — | Thời điểm endpoint bị tắt.<br><sub>Tự tắt khi `failure_streak` chạm `webhooks.FAILURE_STREAK_LIMIT = 20` — ngắt mạch để một endpoint chết không kéo hàng đợi mãi. Chính sách runtime, không phải ràng buộc lược đồ</sub> |
| 14 | `disabled_reason` | `text` | ✓ | — | — | — | Lý do endpoint bị tắt. |

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
