# Từ điển dữ liệu — Nhóm M2: Tổ chức & Phân quyền

*9 bảng · 97 cột. Trích từ CSDL đang chạy ngày 18/08/2026.
Quy ước đọc bảng: xem [DD_00_QUY_UOC_VA_MUC_LUC.md](DD_00_QUY_UOC_VA_MUC_LUC.md).*

**Đặc điểm chung của nhóm:** đây là nơi **định nghĩa ra các đơn vị cách ly**, và
là nơi mô hình phân quyền theo phạm vi (`scope_level`) được cài đặt. Nhóm đã qua
một lần tái cấu trúc lớn: nhiều bảng vai rời rạc gộp về **một mô hình gán vai theo
phạm vi**.

---

## 2.1 Bảng `tenants` — Tổ chức

**Khoá chính:** `tenant_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 20 · **Số hàng
(10/08/2026):** 1

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| tenant_id | text | — | Primary key | **Mã tổ chức** — khoá dùng trong mọi bảng dữ liệu, **không đổi được** về sau |
| display_name | text | — | Null | Tên hiển thị |
| slug | text | — | Null, Unique | Định danh rút gọn dùng trên URL |
| is_active | boolean | — | Not null, Default true | Trạng thái **quản trị**: còn hoạt động hay đã tạm dừng |
| created_at | timestamptz | — | Not null, Default now() | Ngày lập tổ chức |
| deleted_at | timestamptz | — | Null | Cờ xoá mềm |
| cloned_from_community_version | bigint | 64 | Null, Foreign key → community_versions.version | **Phiên bản danh mục cộng đồng** đã sao chép lúc khởi tạo — dấu vết của quan hệ *kế thừa một lần* |
| cloned_at | timestamptz | — | Null | Thời điểm sao chép danh mục |
| plan_code | text | — | Not null, Default 'free', Foreign key → plans.plan_code | Gói cước đang áp |
| billing_status | text | — | Not null, Default 'active', Check | Trạng thái **thương mại** — trục khác hẳn `is_active` |
| trial_ends_at | timestamptz | — | Null | Ngày kết thúc bản dùng thử |
| current_period_start | timestamptz | — | Null | Mốc bắt đầu kỳ hạn hiện tại |
| current_period_end | timestamptz | — | Null | Mốc kết thúc kỳ hạn hiện tại |
| is_self_serve | boolean | — | Not null, Default false | Tổ chức tự đăng ký hay do quản trị nền tảng lập |
| owner_user_id | uuid | — | Null, Foreign key → users.id | Tài khoản chủ sở hữu |
| suspended_at | timestamptz | — | Null | Thời điểm bị đình chỉ |
| suspended_reason | text | — | Null | **Lý do đình chỉ do quản trị viên ghi** — hiển thị cho người dùng ở màn hình đăng nhập |
| tenant_type | text | — | Not null, Default 'ORGANIZATION', Check | Loại tổ chức |
| is_system_reserved | boolean | — | Not null, Default false | Tổ chức do hệ thống giữ chỗ, không cho xoá |
| billing_exempt | boolean | — | Not null, Default false | Miễn áp hạn mức thương mại |

**Ghi chú thiết kế — hai trạng thái không được lẫn.** `is_active` / `suspended_at`
là **trục quản trị**; `billing_status` là **trục thương mại**. Một tổ chức
`past_due` **vẫn ghi được** — đó là chủ ý, không phải sót (BR-8.3).

**Thay đổi so với ảnh chụp 10/08/2026:** bảng này **nay đã bật RLS**. Ảnh chụp cũ
ghi nó là một trong hai bảng có `tenant_id` mà không bật chính sách, kèm lập luận
*"cơ chế cách ly không thể tự bảo vệ chính cái bảng định nghĩa ra các đơn vị cách
ly"*. Lập luận đó vẫn đúng về mặt cấu trúc — truy vấn phân giải ngữ cảnh vẫn phải
đọc bảng này trước khi ngữ cảnh tồn tại — nên **chính sách hiện hành phải cho phép
đường phân giải đó đi qua**. Chương 3 và Phụ lục A đang trích con số cũ và cần cập nhật.

**`cloned_from_community_version` là bằng chứng của luật không-rơi-ngược:** nó ghi
lại tổ chức này đã kế thừa danh mục cộng đồng ở **phiên bản nào**, một lần, lúc
khởi tạo. Không có đường đọc ngược lại mặt phẳng cộng đồng lúc chạy.

---

## 2.2 Bảng `workspaces` — Không gian làm việc

**Khoá chính:** `workspace_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 9 · **Số
hàng:** 0 · **Trạng thái: ○ có bảng, chưa có bề mặt API**

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| workspace_id | uuid | — | Primary key, Default gen_random_uuid() | Định danh không gian làm việc |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức sở hữu |
| name | text | — | Not null | Tên hiển thị |
| description | text | — | Not null, Default '' | Mô tả |
| status | text | — | Not null, Default 'ACTIVE', Check | Trạng thái vòng đời |
| is_default | boolean | — | Not null, Default false | Không gian mặc định của tổ chức |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm tạo |
| archived_at | timestamptz | — | Null | Cờ lưu trữ |
| deleted_at | timestamptz | — | Null | Cờ xoá mềm |

**Ràng buộc duy nhất kép:** `UNIQUE (tenant_id, workspace_id)` — chuẩn bị sẵn để
các bảng con tham chiếu bằng **khoá ngoại ghép mang định danh tổ chức**.

---

## 2.3 Bảng `projects` — Dự án

**Khoá chính:** `project_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 10 · **Số
hàng:** 0 · **Trạng thái: ○ có bảng, chưa có bề mặt API**

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| project_id | uuid | — | Primary key, Default gen_random_uuid() | Định danh dự án |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức sở hữu |
| workspace_id | uuid | — | Not null, **Foreign key kép** → workspaces(tenant_id, workspace_id) | Không gian làm việc chứa dự án |
| name | text | — | Not null | Tên hiển thị |
| description | text | — | Not null, Default '' | Mô tả |
| status | text | — | Not null, Default 'ACTIVE', Check | Trạng thái vòng đời |
| is_default | boolean | — | Not null, Default false | Dự án mặc định |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm tạo |
| archived_at | timestamptz | — | Null | Cờ lưu trữ |
| deleted_at | timestamptz | — | Null | Cờ xoá mềm |

**Hai ràng buộc duy nhất kép:** `UNIQUE (tenant_id, project_id)` và
`UNIQUE (tenant_id, workspace_id, project_id)` — cái sau cho phép bảng con tham
chiếu **cả ba cấp phạm vi** trong một khoá ngoại duy nhất.

**Ghi chú trung thực về hai bảng 2.2 và 2.3 — cập nhật 18/08/2026.** Cấu trúc dữ
liệu vẫn đầy đủ như mô tả trên. Điều **đã đổi**: hai bảng này nay **có bề mặt vận
hành** — router `backend/app/routers/workspaces.py` (12 điểm cuối) và màn hình
`/settings/workspaces` cho tạo, đổi tên, lưu trữ, và gán/thu vai ở cấp workspace
lẫn cấp project.

Điều **chưa đổi**, và phải giữ nguyên trong mọi phát biểu:

* **Dữ liệu chưa gắn vào cây.** `samples`, `classes`, `training_jobs` vẫn chỉ mang
  `tenant_id`. `scope_resolver._default_project` còn nguyên là cây cầu tạm — nó
  đúng hôm nay **chỉ vì** mỗi tenant có đúng một project, và sẽ sai vào ngày
  project thứ hai ra đời.
* **`AUTHZ_MODE=shadow`.** Một lần gán vai cấp workspace ghi đúng hai dòng
  (`memberships` + `role_assignments`) và Casbin đọc được chúng, nhưng bên **quyết
  định** lúc chạy vẫn là hệ cũ hai phạm vi.

Vì vậy phát biểu chính thức trong quyển **không đổi**: *"kiến trúc hỗ trợ nhiều
cấp; cưỡng chế chứng minh được ở cấp hệ thống và cấp tổ chức"*. Có bề mặt vận hành
**không** đồng nghĩa với có cưỡng chế — và trang `/settings/workspaces` in ra đúng
hai câu này ngay đầu màn hình để không ai đọc nhầm.

---

## 2.4 Bảng `roles` — Định nghĩa vai

**Khoá chính:** `role_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 12 · **Số hàng
(10/08/2026):** 3

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| role_id | uuid | — | Primary key, Default gen_random_uuid() | Định danh vai |
| role_code | varchar | 50 | Not null | Mã vai dùng trong mã nguồn và chính sách Casbin |
| description | text | — | Null, Default '' | Mô tả vai |
| tenant_id | text | — | Null, Foreign key → tenants.tenant_id | Tổ chức sở hữu vai; **rỗng** nghĩa là vai dựng sẵn toàn nền tảng |
| scope_level | text | — | Null, Check | **Cấp phạm vi vai áp dụng**: hệ thống · tổ chức · không gian làm việc · dự án |
| is_builtin | boolean | — | Not null, Default false | Vai dựng sẵn (13 vai) hay vai do tổ chức tự tạo |
| is_active | boolean | — | Not null, Default true | Vai còn dùng được |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm tạo |
| role_name | text | — | Null | Tên hiển thị cho người dùng |
| tenant_type_constraint | text | — | Null, Check | Giới hạn vai này chỉ áp cho một **loại** tổ chức nhất định |
| created_by_user_id | uuid | — | Null, Foreign key → users.id | Người tạo vai tuỳ chỉnh |
| updated_at | timestamptz | — | Not null, Default now() | Lần sửa gần nhất |

**Bốn ràng buộc `CHECK` trên bảng này**, và chúng là chỗ luật phân quyền được
cưỡng chế ở tầng CSDL chứ không chỉ ở tầng ứng dụng:

* `scope_level` chỉ nhận bốn giá trị hợp lệ
* `tenant_type_constraint` chỉ nhận giá trị hợp lệ
* Ràng buộc trên bộ ba `(is_builtin, tenant_id, scope_level)` — **vai dựng sẵn
  không được thuộc về một tổ chức cụ thể**
* Ràng buộc trên cặp `(scope_level, tenant_id)` — vai cấp hệ thống không được mang
  `tenant_id`

**Số hàng 3 so với 13 vai dựng sẵn:** 13 là số vai **được định nghĩa trong mô hình
phân quyền** (2 hệ thống / 5 tổ chức / 2 không gian làm việc / 4 dự án); 3 là số
hàng **đã được gieo vào bảng** tại thời điểm chụp. Hai con số không mâu thuẫn.

---

## 2.5 Bảng `permissions` — Danh mục quyền

**Khoá chính:** `permission_code` · **RLS:** — không bật · **Số cột:** 9

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| permission_code | text | — | Primary key, Check | Mã quyền, ví dụ `sample.create` |
| description | text | — | Not null, Default '' | Mô tả quyền |
| applicable_scope | text | — | Not null, Check | Cấp phạm vi mà quyền này có nghĩa |
| risk_level | text | — | Not null, Default 'NORMAL', Check | **Mức rủi ro** của quyền — cơ sở để quyết định có đòi xác thực lại không |
| requires_passcode | boolean | — | Not null, Default false | **Quyền này có đòi mã xác thực lại không** — nối tới `user_action_passcodes` |
| is_api_assignable | boolean | — | Not null, Default false | Quyền có gán được cho **khoá API** không |
| is_active | boolean | — | Not null, Default true | Quyền còn dùng |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm định nghĩa |
| is_custom_role_allowed | boolean | — | Not null, Default true | Vai tuỳ chỉnh của tổ chức có được cấp quyền này không |

**Ba cột cờ (6, 7, 9) là ba hàng rào khác nhau, không thay thế nhau:**

* `requires_passcode` — quyền nguy hiểm với **người dùng**, đòi xác thực lại
* `is_api_assignable` — quyền nguy hiểm khi trao cho **máy**; ví dụ quyền dọn sạch
  dữ liệu không nên gán được cho một khoá API chạy tự động ban đêm
* `is_custom_role_allowed` — quyền nguy hiểm khi để **tổ chức tự cấp cho nhau**

Ba ràng buộc `CHECK` ghép các cặp cột này lại, nên không thể tạo một quyền vừa
`applicable_scope` cấp hệ thống vừa cho phép vai tuỳ chỉnh của tổ chức cấp.

---

## 2.6 Bảng `role_permissions` — Vai ↔ Quyền

**Khoá chính:** `(role_id, permission_code)` · **RLS:** — không bật · **Số cột:** 3

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| role_id | uuid | — | Primary key (kép), Foreign key → roles.role_id | Vai được cấp quyền |
| permission_code | text | — | Primary key (kép), Foreign key → permissions.permission_code | Quyền được cấp |
| granted_at | timestamptz | — | Not null, Default now() | Thời điểm gắn quyền vào vai |

Bảng nối thuần tuý, hiện thực quan hệ **n:m** giữa vai và quyền.

---

## 2.7 Bảng `memberships` — Tư cách thành viên theo phạm vi

**Khoá chính:** `membership_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 14

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| membership_id | uuid | — | Primary key, Default gen_random_uuid() | Định danh tư cách thành viên |
| user_id | uuid | — | Not null, Foreign key → users.id | Tài khoản |
| scope_level | text | — | Not null, Default 'TENANT', Check | **Cấp phạm vi** của tư cách này |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức |
| workspace_id | uuid | — | Null, **Foreign key kép** → workspaces(tenant_id, workspace_id) | Không gian làm việc, khi phạm vi ở cấp đó |
| project_id | uuid | — | Null, **Foreign key kép** → projects(tenant_id, workspace_id, project_id) | Dự án, khi phạm vi ở cấp đó |
| parent_membership_id | uuid | — | Null, **Foreign key kép** → memberships(membership_id, user_id) | **Tư cách cha** — dựng cây phạm vi lồng nhau |
| legacy_role | text | — | Null, Check | Vai theo mô hình cũ, giữ để tương thích ngược |
| status | text | — | Not null, Default 'ACTIVE', Check | Trạng thái: đang hoạt động / bị đình chỉ / đã rời |
| joined_at | timestamptz | — | Null | Thời điểm gia nhập |
| suspended_at | timestamptz | — | Null | Thời điểm bị đình chỉ |
| left_at | timestamptz | — | Null | Thời điểm rời tổ chức |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm tạo bản ghi |
| updated_at | timestamptz | — | Not null, Default now() | Lần sửa gần nhất |

**Sáu ràng buộc `CHECK` trên bảng này** — nhiều nhất trong toàn lược đồ, và mỗi
cái chặn một trạng thái vô nghĩa:

* `(scope_level, workspace_id, project_id)` — phạm vi cấp tổ chức **không được**
  mang `workspace_id`; phạm vi cấp dự án **bắt buộc** mang cả hai
* `scope_level` và `status` chỉ nhận giá trị hợp lệ
* `(status, left_at)` — trạng thái *đã rời* **bắt buộc** có `left_at`, và ngược lại
* `(scope_level, legacy_role)` và `legacy_role` — vai cũ chỉ có nghĩa ở cấp tổ chức

**`parent_membership_id` tham chiếu chính bảng này bằng khoá ngoại ghép
`(membership_id, user_id)`**, không phải bằng `membership_id` đơn. Lý do: khoá đơn
cho phép một tư cách của người A trỏ tới tư cách cha của người B. Khoá ghép làm
điều đó **bất khả thi ở tầng ràng buộc**.

---

## 2.8 Bảng `role_assignments` — Gán vai

**Khoá chính:** `assignment_id` · **RLS:** — không bật · **Số cột:** 9

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| assignment_id | uuid | — | Primary key, Default gen_random_uuid() | Định danh lần gán vai |
| user_id | uuid | — | Not null, Foreign key → users.id | Người được gán |
| role_id | uuid | — | Not null, Foreign key → roles.role_id | Vai được gán |
| membership_id | uuid | — | Null, **Foreign key kép** → memberships(membership_id, user_id) | **Tư cách thành viên** mà lần gán này bám vào — đây là chỗ phạm vi được xác định |
| assigned_by_user_id | uuid | — | Not null, Foreign key → users.id | Người thực hiện gán |
| assigned_at | timestamptz | — | Not null, Default now() | Thời điểm gán |
| revoked_by_user_id | uuid | — | Null, Foreign key → users.id | Người thu hồi |
| revoked_at | timestamptz | — | Null | Thời điểm thu hồi |
| revoke_reason | text | — | Null | Lý do thu hồi |

**Ràng buộc `CHECK` trên cặp `(revoked_by_user_id, revoked_at)`:** đã thu hồi thì
**bắt buộc** ghi ai thu hồi, và ngược lại. Không có trạng thái *"đã thu hồi nhưng
không biết ai làm"*.

**Khoá ngoại ghép `(membership_id, user_id)` là điểm thiết kế cốt lõi của bảng
này:** nó bảo đảm lần gán vai và tư cách thành viên **thuộc về cùng một người**.
Với khoá đơn, một bản ghi có thể gán vai cho người A dựa trên tư cách thành viên
của người B — cơ sở dữ liệu không phản đối vì cả hai khoá đều tồn tại.

**Ghi chú trung thực về bảng này.** Ảnh chụp 10/08/2026 ghi bảng này **có** RLS;
truy vấn ngày 18/08/2026 cho thấy **không**. Bảng không mang cột `tenant_id` —
phạm vi tổ chức đến **gián tiếp** qua `membership_id`. Đây là một khoảng trống
thật: quan hệ gián tiếp không được chính sách bảo mật mức hàng bảo vệ, và việc lọc
phải do tầng ứng dụng làm.

---

## 2.9 Khung nhìn `tenant_members`

**Không phải bảng** — là **khung nhìn** trên lát cắt `scope_level = 'TENANT'` của
`role_assignments` nối `memberships`. Số hàng tại ảnh chụp 10/08/2026: 10.

Hệ quả cụ thể của việc là khung nhìn, **cả hai đều đã trả giá**:

* **Không tạo được chỉ mục** trên nó
* **Không dùng được mệnh đề xử lý xung đột** (`ON CONFLICT`) khi ghi — **mọi đường
  ghi phải nhắm vào bảng nền**

Khung nhìn dùng chế độ **`security_invoker`** (chạy theo quyền của người gọi), để
chính sách bảo mật mức hàng của các bảng nền vẫn áp đúng. Nếu dùng chế độ mặc định
(chạy theo quyền chủ sở hữu khung nhìn), khung nhìn sẽ **vượt qua** chính sách của
bảng nền — đúng lối vòng mà bốn tầng cưỡng chế tồn tại để bịt.

---

## 2.10 Bảng `tenant_invitations` — Lời mời

**Khoá chính:** `invitation_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 11 · **Số
hàng (10/08/2026):** 0

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| invitation_id | uuid | — | Primary key | Định danh lời mời |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức mời |
| email | text | — | Not null, Check | **Địa chỉ nhận** — lời mời nêu đích danh, đăng ký bằng email khác sẽ bị từ chối |
| role | text | — | Null, Check | Vai dự kiến khi gia nhập |
| token_hash | text | — | Not null, Unique | **Mã băm** của token trong liên kết mời |
| invited_by | uuid | — | Null, Foreign key → users.id | Người gửi lời mời |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm tạo |
| expires_at | timestamptz | — | Not null | Hạn dùng |
| accepted_at | timestamptz | — | Null | Thời điểm được chấp nhận |
| accepted_by | uuid | — | Null, Foreign key → users.id | Tài khoản đã tiêu thụ lời mời |
| revoked_at | timestamptz | — | Null | Cờ thu hồi |

**Ràng buộc `CHECK` trên cặp `(accepted_by, accepted_at)`:** đã chấp nhận thì
**bắt buộc** biết ai chấp nhận. Không có trạng thái *"lời mời đã dùng nhưng không
biết ai dùng"*.

**Vì sao bảng này tồn tại thay vì cho gán trực tiếp:** mã tài khoản **không phải
bí mật**. Nếu quản trị viên tổ chức gán trực tiếp được theo mã tài khoản, họ kéo
được bất kỳ ai trên hệ thống vào tổ chức của mình mà người kia không hay biết.
Đường đưa người vào của quản trị tổ chức vì thế **bắt buộc** là lời mời — thứ đòi
hỏi chính người được mời hành động (BR-1.4).

---

## Tổng kết quan hệ trong nhóm M2

```
tenants (1) ──< workspaces (1) ──< projects          [cây phạm vi, KHOÁ NGOẠI GHÉP]
tenants (1) ──< memberships ──> users
memberships (1) ──< role_assignments ──> roles       [KHOÁ NGOẠI GHÉP (membership_id, user_id)]
roles (n) ──< role_permissions >── permissions        [n:m]
tenants (1) ──< tenant_invitations
tenants (n) ──> plans                                 [gói cước]
tenants (n) ──> community_versions                    [danh mục kế thừa một lần]
```

| Đặc điểm | Giá trị |
|---|:--:|
| Bảng có `tenant_id` | 6 |
| Bảng bật RLS | 6 |
| **Khoá ngoại ghép trong nhóm** | **5** |
| Ràng buộc `CHECK` | **18** |
| Bảng chưa có bề mặt API | 2 (`workspaces`, `projects`) |

**Nhóm này có mật độ ràng buộc `CHECK` cao nhất lược đồ (18 ràng buộc trên 9
bảng).** Đó không phải ngẫu nhiên: phân quyền là chỗ một trạng thái vô nghĩa
(*"vai cấp hệ thống thuộc về một tổ chức"*, *"đã rời nhưng không có ngày rời"*)
không gây lỗi ngay mà gây **quyền sai** về sau. Đẩy các bất biến đó xuống tầng CSDL
làm chúng không phụ thuộc vào việc lập trình viên nhớ kiểm.
