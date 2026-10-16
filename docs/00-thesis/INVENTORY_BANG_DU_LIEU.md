# INVENTORY LƯỢC ĐỒ DỮ LIỆU — đầu vào cho CDM / LDM / PDM / Data Dictionary

**Nguồn:** truy vấn danh mục hệ thống của `signdb` (container `voya_postgres`), ngày
17/08/2026, `schema_migrations.version = 5`.
**Cách dựng:** `pg_class`, `pg_constraint`, `pg_policy`, `information_schema.columns`.
Không có dòng nào trong bảng dưới đây được suy đoán từ mã nguồn hay từ trí nhớ.

Tài liệu này **không phải** một mục của quyển. Nó là bảng phân loại trung gian để
từ đó suy ra CDM, LDM, PDM và Data Dictionary một cách có hệ thống, thay vì kéo
thả từng bảng trên PowerDesigner rồi sửa dây.

---

## 0. Năm đính chính về tiền đề, cần chốt trước khi vẽ

### 0.1 Không phải "80+ bảng" — mà là **58 bảng và 1 khung nhìn**

| Đối tượng | Số lượng |
|---|---:|
| Bảng thật (`relkind = 'r'`) trong `public` | **58** |
| Khung nhìn (`tenant_members`) | 1 |
| Khoá ngoại | 118 |
| Bảng bật chính sách bảo mật mức hàng | 34 |
| Cơ sở dữ liệu khác trên cùng máy chủ | `signdb_ci`, `signdb_test`, `signdb_goc`, `signdb_v3test`, `authz_v5`, `signdb_pytest_*` — **đều là bản sao để kiểm thử/diễn tập, không phải mặt phẳng dữ liệu thứ hai** |

`authz_v5` chứa 56 bảng trùng tên với `signdb` nhưng thiếu `schema_migrations`:
đây là bản sao diễn tập của lần chuyển đổi phân quyền v5, không phải một plane riêng.
Nếu đếm gộp nó vào sẽ ra con số ~114 và **sai**.

Con số 58 vẫn là một lược đồ lớn cho một luận văn. Nhưng phải nói đúng con số,
vì hội đồng có thể yêu cầu đếm lại — và `SELECT count(*) FROM pg_class` là một
câu lệnh ai cũng chạy được.

### 0.2 Nhiều thực thể trong bố cục đề xuất **không tồn tại** trong lược đồ

Đây là điểm quan trọng nhất. Bố cục Chương 3 đã thống nhất có các mục dựng ERD cho
những thực thể sau — kiểm tra trên DB thật cho thấy chúng **không có**:

| Thực thể trong bố cục | Trạng thái thật | Cái thật sự tồn tại |
|---|---|---|
| `DATASET`, `DATASET_VERSION` | **Không có bảng** | — |
| `DATASET_VERSION_SAMPLE` | **Không có bảng** | — |
| `SAMPLE_REVISION` | **Không có bảng** | `samples` sửa tại chỗ, chỉ có `deleted_at` |
| `CLASS_REVISION` | **Không có bảng** | `classes` sửa tại chỗ |
| `REGISTRY_VERSION_CLASS` | **Không có bảng** | `registry_versions` lưu ảnh chụp dạng nội dung + mã băm |
| `LEGAL_DOCUMENT_VERSION` | **Không có bảng** | `legal_documents` khoá chính `doc_id`, định danh nghiệp vụ là cặp (`kind`, `version`) — version là **cột**, không phải bảng con |
| `workspace_members`, `project_members` | **Không có bảng** | một bảng `memberships` đa hình với `scope_level` |
| `tenant_role_assignments` / `workspace_...` / `project_...` | **Không có bảng** | một bảng `role_assignments` trỏ vào `memberships` |
| `INVOICE`, `PAYMENT_TRANSACTION`, `RECEIPT` | **Không có bảng** | `plans` + `tenant_subscriptions` + `tenant_usage_daily`; hệ thống **không thu tiền** |
| `MODEL`, `CHECKPOINT`, `model_versions` | **Không có bảng** | mô hình là hiện vật của `training_jobs` trên hệ tệp |
| `CUSTOM_FIELD_DEFINITION` / `_VALUE` | **Không có bảng** | không có cơ chế mở rộng lược đồ theo tenant |

Chín tệp DDL định nghĩa `datasets`, `dataset_versions`, `dataset_splits`,
`dataset_lineage`, `dataset_samples_mapping`, `experiments`, `experiment_metrics`,
`model_versions`, `model_deployments` **có nằm trong repo** —
[001_create_production_schema.sql](backend/migrations/001_create_production_schema.sql) và
[002_mvp_schema.sql](backend/migrations/002_mvp_schema.sql) — nhưng **chưa bao giờ được
áp** lên `signdb`. Tệp 002 tự khai trong phần đầu rằng nó *thay thế* 001; cả hai
đều nằm ngoài đường migration đang chạy (`app.cli.migrate`).

Hệ quả cần biết: [backend/app/train_task.py:7](backend/app/train_task.py#L7) và
[backend/app/routers/experiments.py:45](backend/app/routers/experiments.py#L45) vẫn
import `experiment_tracking_api_revised`, tức là còn đường mã trỏ tới các bảng
`experiments` / `experiment_metrics` / `model_versions` không tồn tại.

**Việc phải quyết, không thể vẽ vòng qua:** hoặc (a) mô tả đúng cái đang có —
ghim phiên bản chỉ đạt tới `registry_versions` (không gian nhãn), còn nội dung bộ
dữ liệu **không** được ghim; hoặc (b) hiện thực nhóm bảng dataset versioning rồi mới
viết. Vẽ `DATASET_VERSION → DATASET_VERSION_SAMPLE → SAMPLE_REVISION` trong CDM
khi ba bảng đó không tồn tại là bịa lược đồ, và đó là kiểu sai hội đồng bắt được
bằng một câu `\d`.

### 0.3 Phụ lục A hiện tại đã lệch so với DB

[PHU_LUC_A_MO_HINH_DU_LIEU.md](docs/00-thesis/quyen/PHU_LUC_A_MO_HINH_DU_LIEU.md)
là ảnh chụp ngày 10/08. So với DB ngày 17/08:

| Chỗ | Phụ lục A ghi | DB thật hôm nay |
|---|---|---|
| `tenants` RLS | — (và §5 lập luận **không thể** bật) | **✔ có bật**, chính sách `tenant_isolation` |
| `roles` RLS | — | **✔**, chính sách `tenant_catalogue_access` |
| `training_metrics` RLS | — | **✔** |
| `role_assignments` RLS | ✔ | **— không bật**, 0 chính sách, và bảng **không có** cột `tenant_id` |
| `tenant_members` là lát cắt của | `role_assignments` | `memberships` |
| `role_permissions` PK | (`role_id`, `permission_id`) | (`role_id`, `permission_code`) |
| Khoá chính `samples` / `classes` / `projects` | `id` | `sample_uid` / `class_uid` / `project_id` |
| §5 độ phủ | 32/34 ≈ 94,1 %, hai ngoại lệ `tenants` + `tenant_purges` | **34/35 ≈ 97,1 %**, còn **một** ngoại lệ: `tenant_purges` |

Lập luận hay nhất của §5 Phụ lục A — "cơ chế cách ly không tự bảo vệ được cái bảng
định nghĩa ra các đơn vị cách ly" — **đã không còn đúng với `tenants`**, vì bảng đó
giờ có chính sách. Lập luận vẫn đúng với `users` (truy vấn đăng nhập chạy trước khi
biết tổ chức), nên nó cần được viết lại quanh `users`, không quanh `tenants`.

### 0.4 "3.860 mẫu" đếm dôi 440 so với số lần người thật ký

`samples` có cột `augment_id`. Phân bố đo ngày 17/08:

| `augment_id` | Số dòng | Là gì |
|---:|---:|---|
| 0 | **3.420** | bản gốc — một lần người thật thực hiện một ký hiệu |
| 1 | 110 | bản tăng cường do máy sinh |
| 2–7 | 55 mỗi mức, cộng 330 | bản tăng cường do máy sinh |
| | **3.860** | tổng số **dòng** |

Nghĩa là **440 dòng (11,4 %) không phải một lần ký của con người**, mà là biến
thể sinh ra từ một bản gốc. Định nghĩa "sample = một lần thực hiện một ký hiệu"
sai với đúng nhóm này.

Hệ quả bắt buộc cho Chương 4: mọi câu "thu được 3.860 mẫu" phải đổi thành
**3.420 mẫu gốc + 440 bản tăng cường**. Con số dùng để nói về công sức thu thập
và về đa dạng người ký là **3.420**; con số 3.860 chỉ dùng được khi nói về kích
thước tập đưa vào huấn luyện. Trộn hai con số này là cách tự thổi phồng quy mô
dữ liệu mà người phản biện kiểm được bằng một câu `GROUP BY augment_id`.

### 0.5 Hai đường vượt ranh giới tổ chức, cùng nằm ngoài phép đo cách ly

Phép đo cách ly (P0-B, 17/08) chạy trên mặt phẳng **đọc theo yêu cầu HTTP**. Có
hai đường ghi/đọc **không** đi qua mặt phẳng đó:

| Đường | Vị trí | Bản chất |
|---|---|---|
| Xuất bộ dữ liệu | `/api/dataset/export` | đọc theo phạm vi lời gọi |
| **Đồng bộ Google Sheets** | [export_tasks.py:82](backend/app/export_tasks.py#L82) | `_load_all_samples_unscoped()` → **một** bảng tính dùng chung |

Đường thứ hai đáng nêu riêng vì nó **ra khỏi hệ thống**: `google_sheets_samples_spreadsheet_id`
là **một** giá trị duy nhất trong cấu hình, nên mọi mẫu của mọi tổ chức đổ vào
cùng một bảng tính. Chú thích ngay tại chỗ nói rõ đây là chủ ý ("bảng tính là
ảnh chụp TOÀN kho vào một bảng duy nhất, không phải bản xuất theo tổ chức").

**Mức phơi nhiễm thực tế hôm nay bằng không**, và phải nói đúng như vậy: cả
3.860 mẫu đều thuộc tenant `default`, tenant `community` có 0 mẫu. Đây là một
**ranh giới thiết kế bị vượt qua**, chưa phải một vụ rò rỉ đã xảy ra. Nó trở
thành rò rỉ thật đúng vào ngày tổ chức thứ hai thu mẫu đầu tiên.

Cách viết đúng cho Chương 3: cách ly được cưỡng chế ở tầng CSDL cho đường đọc
theo yêu cầu; đường đồng bộ ra dịch vụ ngoài **chạy bằng quyền hệ thống và
không mang phạm vi tổ chức** — đó là một hạn chế đã biết, không phải một lỗ hổng
chưa phát hiện.

---

## 1. Quy ước phân loại

**Type** — vai trò cấu trúc của bảng:

| Ký hiệu | Nghĩa |
|---|---|
| `Root` | gốc của một cây sở hữu, không phụ thuộc bảng nghiệp vụ nào |
| `Child` | phụ thuộc một cha nghiệp vụ |
| `Assoc` | bảng kết hợp có thuộc tính/vòng đời riêng |
| `Bridge` | bảng nối thuần, không có vòng đời riêng |
| `Catalogue` | danh mục tham chiếu |
| `Version` | thực thể phiên bản, ảnh chụp bất biến |
| `History` | bản ghi sự kiện, chỉ thêm |
| `View` | khung nhìn dẫn xuất |

**Scope** — mặt phẳng dữ liệu: `Platform` (nền tảng quản lý) · `Tenant` (thuộc một
tổ chức) · `Community` (mặt phẳng đọc chung) · `Identity` (thuộc tài khoản, cắt
ngang tổ chức) · `System` (siêu dữ liệu vận hành).

**Lifecycle:** `Mutable` · `Soft-delete` · `Immutable` · `Append-only` ·
`Revocable` (có `revoked_at` / `left_at`) · `Ephemeral` (có `expires_at`) ·
`Upsert` · `Catalogue`.

**RLS:** ✔ bật (`relrowsecurity` **và** `relforcerowsecurity`, đều có chính sách) · — không bật.

---

## 2. Bảng inventory — 58 bảng + 1 khung nhìn

### M1 — Danh tính & Truy cập (8 bảng)

| Bảng | Khoá chính | Type | Scope | Cha | Nối giữa | Lifecycle | RLS |
|---|---|---|---|---|---|---|:--:|
| `users` | `id` | Root | Identity / Tenant | `tenants`, `roles` | — | Mutable, Soft-delete | ✔ |
| `refresh_tokens` | `token_hash` | Child | Identity | `users` | — | Ephemeral, Revocable | — |
| `password_reset_tokens` | `token_hash` | Child | Identity | `users` | — | Ephemeral | — |
| `verification_codes` | `challenge_id` | Child | Identity | `users` | — | Ephemeral | — |
| `user_totp` | `user_id` | Child (1:1) | Identity | `users` | — | Mutable | — |
| `user_recovery_codes` | `code_hash` | Child | Identity | `users` | — | Ephemeral | — |
| `user_action_passcodes` | `user_id` | Child (1:1) | Identity | `users` | — | Ephemeral | — |
| `api_keys` | `key_id` | Child | Tenant | `tenants` | — | Revocable | ✔ |

> `users` mang cột `tenant_id` và **có** chính sách, nhưng chính sách chứa lối
> thoát `app.system_scope = 'on'` — vì truy vấn phân giải đăng nhập chạy trước khi
> ngữ cảnh tổ chức tồn tại. Đây là chỗ sinh ra bẫy "0 hàng bị đọc thành không có gì".

### M2 — Tổ chức & Phân quyền (9 bảng + 1 khung nhìn)

| Bảng | Khoá chính | Type | Scope | Cha | Nối giữa | Lifecycle | RLS |
|---|---|---|---|---|---|---|:--:|
| `tenants` | `tenant_id` | Root | Tenant | — (→ `plans`, `community_versions`) | — | Mutable, Soft-delete | ✔ |
| `workspaces` | `workspace_id` | Child | Tenant | `tenants` | — | Mutable, Soft-delete | ✔ |
| `projects` | `project_id` | Child | Tenant | `workspaces` (ghép `tenant_id,workspace_id`) | — | Mutable, Soft-delete | ✔ |
| `memberships` | `membership_id` | Assoc | Tenant | `tenants` / `workspaces` / `projects` + tự trỏ `parent_membership_id` | `users` ↔ phạm vi | Revocable | ✔ |
| `roles` | `role_id` | Catalogue + Tenant | Platform ∪ Tenant | `tenants` (**cho phép NULL**) | — | Mutable | ✔ |
| `permissions` | `permission_code` | Catalogue | Platform | — | — | Catalogue | — |
| `role_permissions` | (`role_id`,`permission_code`) | Bridge | Platform | — | `roles` ↔ `permissions` | Mutable | — |
| `role_assignments` | `assignment_id` | Assoc | **(không có `tenant_id`)** | `memberships` | `memberships`/`users` ↔ `roles` | Revocable | **—** |
| `tenant_invitations` | `invitation_id` | Child | Tenant | `tenants` | — | Ephemeral | ✔ |
| `tenant_members` ⟨view⟩ | — | View | Tenant | `memberships` | — | dẫn xuất | kế thừa |

> **Ba điểm phải vẽ đúng ở LDM:**
> 1. `memberships` là **một** bảng đa hình: `scope_level ∈ {TENANT, WORKSPACE, PROJECT}`,
>    ba cột phạm vi `tenant_id` / `workspace_id` / `project_id`, và **tự trỏ**
>    `(parent_membership_id, user_id) → memberships`. Ràng buộc "membership cấp
>    dưới phụ thuộc membership cấp trên" được cưỡng chế bằng chính khoá ngoại tự
>    trỏ này — đây là bất biến nghiệp vụ đáng trình bày nhất trong nhóm.
> 2. `role_assignments` gắn vào **`membership_id`**, không gắn vào (user, scope).
>    Phạm vi của một lần gán vai được kế thừa từ membership, chứ không lưu lại.
> 3. `roles.tenant_id` **nullable**, chính sách cho phép `tenant_id IS NULL`:
>    đây là danh mục vai nền tảng cộng thêm vai riêng của tổ chức trong **cùng
>    một bảng**. Ở CDM nên là một thực thể `Role` có phân biệt nguồn, không phải
>    hai thực thể.

**Độ lấp đầy thực tế** (đo 17/08, không suy từ lược đồ):

| tenant | `workspaces` | `projects` |
|---|---:|---:|
| `default` | 1 | 1 |
| `community` | 0 | 0 |

Hai bảng đều **có** dòng — nhưng cả hệ thống chỉ có **một** workspace và **một**
project, trong khi có 2 tổ chức. Quan trọng hơn con số: 3.860 mẫu và 63 lớp
**không mang `project_id`**, nên cây `Tenant ⊃ Workspace ⊃ Project` tồn tại ở
tầng phân quyền nhưng **chưa phân vùng dữ liệu**.

Ở CDM vẫn vẽ đủ ba cấp vì ba cấp có thật ở `memberships`, nhưng quan hệ
`Project ──< Sample` **không được vẽ**: nó không tồn tại ở bất kỳ tầng nào. Đây
đúng là khoảng cách mà [PROPOSAL_COMPLIANCE_MATRIX](docs/10-issues/PROPOSAL_COMPLIANCE_MATRIX.md)
xếp P1 ở mức `PARTIAL`, và là câu hỏi tự nhiên nhất hội đồng có thể đặt ra khi
đọc Mục tiêu 1.

### M3 — Kho dữ liệu mẫu (6 bảng)

| Bảng | Khoá chính | Type | Scope | Cha | Nối giữa | Lifecycle | RLS |
|---|---|---|---|---|---|---|:--:|
| `samples` | `sample_uid` | Child | Tenant | `capture_sessions`, `classes`, `signers` | — | Mutable, Soft-delete | ✔ |
| `classes` | `class_uid` | Child | Tenant | `tenants` (+ `dialects`, `regions`, `languages`, `recognition_profiles`, `vocabulary_groups`) | — | Mutable, Soft-delete | ✔ |
| `capture_sessions` | `capture_session_id` | Child | Tenant | `tenants` (+ `classes`, `signers`) | — | Mutable | ✔ |
| `raw_uploads` | `upload_uid` | Child | Tenant | `tenants` (+ `classes`, `dialects`) | — | Mutable, Soft-delete | ✔ |
| `signers` | `signer_id` | Child | Tenant | `tenants` | — | Mutable | ✔ |
| `signer_aliases` | (`tenant_id`,`old_signer_id`) | History | Tenant | `signers` | — | Append-only | ✔ |

> **`capture_sessions` là thực thể quản lý được, không phải một nhãn.** Sáu
> đường nghiệp vụ trong [label_sessions.py](backend/app/routers/label_sessions.py):
> liệt kê phiên của một lớp, **xoá** phiên, **chuyển chủ sở hữu** (`/reassign`),
> đọc khung hình, hỏi trạng thái dựng preview, và tải `preview.mp4` dựng lại từ
> điểm mốc. Có `/reassign` nghĩa là quyền sở hữu một phiên thu **đổi được** —
> đó là một vòng đời, nên ở CDM `CaptureSession` phải là một thực thể có hành
> vi, không phải thuộc tính gộp của `Sample`.
>
> **`region` là một phần định danh lớp — và chỉ thật sự có hiệu lực từ 17/08/2026.**
> Khoá duy nhất phải vẽ ở PDM là **5 cột**:
> (`tenant_id`, `slug`, `language`, `dialect`, `region`).
>
> Bản 4 cột `uq_classes_tenant_slug_lang_dialect` tồn tại **song song** trên
> `signdb` cho tới 17/08. Vì chặt hơn, nó vô hiệu hoá `region` trên thực tế:
> `region` có trong khoá trên giấy nhưng cơ sở dữ liệu vẫn từ chối hai lớp chỉ
> khác vùng miền. Đã gỡ bằng `app.cli.migrate --to 5`; chứng cứ hai chiều ghi ở
> [KNOWN_ISSUES](docs/10-issues/KNOWN_ISSUES.md).
>
> Tầng ứng dụng **đã khớp** với khoá 5 cột — `region` nằm trong phép so tìm lớp
> ([dataset_manager.py:887](backend/app/dataset_manager.py#L887)). Đừng chép lại
> phát biểu cũ "ứng dụng dùng 4 cột, CSDL dùng 5"; lệch tầng đó đã được vá, và
> nói nó còn tồn tại là hạ thấp hệ thống sai sự thật.
>
> **`samples` KHÔNG có khoá ngoại tới `raw_uploads`.** Xuất xứ từ tệp tải lên tới
> mẫu đặc trưng **không** được cưỡng chế ở tầng ràng buộc — nó chỉ tồn tại qua
> cột `source_type` và quy ước đặt tên. Đừng vẽ `RAW_UPLOAD 1──1..* SAMPLE` như
> một quan hệ có thật.
>
> **"Không có import từ nguồn ngoài" đúng với kho mẫu, nhưng nói vậy là thiếu.**
> Không có đường nạp nào ghi vào `samples`/`classes` từ một bộ dữ liệu bên ngoài
> — điều đó đúng. Nhưng bốn script QIPEDC **có tồn tại và đã chạy**:
> `tai_mau_qipedc.py`, `doi_chieu_danhmuc_qipedc.py`, `gan_nhan_qipedc.py`,
> `lap_muc_luc_qipedc.py`. Chúng lấy **4.362 mục** từ điển quốc gia và **200
> clip**, dùng cho phép đo hiệu quả lưu trữ
> ([MEASUREMENT_storage_efficiency](docs/00-thesis/MEASUREMENT_storage_efficiency.md))
> và cho bản đối chiếu danh mục
> ([DOI_CHIEU_QIPEDC](docs/00-thesis/DOI_CHIEU_QIPEDC.md)) — **không** ghi vào
> kho mẫu.
>
> Phân biệt này phải giữ nguyên ở cả hai chiều: nói "có import QIPEDC" là
> overclaim, nói "không đụng tới QIPEDC" là tự bỏ mất phần việc đã làm được.
> Câu đúng: *dữ liệu QIPEDC được dùng làm **đối chứng đo lường**, không làm
> **nguồn dữ liệu huấn luyện**.*
>
> **Bốn cột quy kết, không phải hai** — đo trên 3.860 mẫu ngày 17/08:
>
> | Cột | Có giá trị | Là ai |
> |---|---:|---|
> | `user_id` | 3.860 (100 %) | định danh nội bộ của lượt thu, luôn có |
> | `auth_user_id` | 3.694 (95,7 %) | **tài khoản đã đăng nhập** lúc thu |
> | `username` | 1.169 (30,3 %) | tên hiển thị chép lại tại thời điểm thu |
> | `signer_id` | 1.674 (43,4 %) | **người ký** — chủ thể dữ liệu |
>
> Chỉ `auth_user_id` và `signer_id` là hai vai nghiệp vụ khác nhau và không được
> gộp ở CDM. Hai cột còn lại là **hiện vật lịch sử**: `user_id` có mặt từ trước
> khi hệ thống có tài khoản, `username` là bản sao chụp lại tên — cả hai đều
> không dùng để suy ra chủ thể dữ liệu.
>
> Con số 1.674 không phải ngẫu nhiên: nó **đúng bằng** số mẫu của chiến dịch
> `isds2026_v1`, và 2.186 mẫu không thuộc chiến dịch nào có `signer_id` = NULL
> **toàn bộ**. Nghĩa là quy kết chủ thể dữ liệu chỉ được thiết lập cho đúng một
> chiến dịch thu. Đây là ràng buộc phải nêu ở phần hạn chế, vì đường phát hành
> dữ liệu dựa trên `signer_consents`, mà bảng đó khoá theo (`tenant_id`,`signer_id`).
>
> **Nối thử toàn kho vào đồng thuận còn hiệu lực** (`withdrawn_at IS NULL`):
>
> | | Số mẫu | Tỉ lệ |
> |---|---:|---:|
> | Nối được vào một đồng thuận còn hiệu lực | **430** | 11,1 % |
> | Có `signer_id` nhưng **không có** bản ghi đồng thuận | 1.244 | 32,2 % |
> | Không có `signer_id`, không nối được về nguyên tắc | 2.186 | 56,6 % |
>
> Toàn bảng `signer_consents` hiện có **đúng 1 dòng / 1 người ký**. Nói cách
> khác: cơ chế đồng thuận đã chạy được, nhưng **88,9 % kho mẫu hiện chưa phát
> hành được** theo đúng luật mà chính hệ thống cưỡng chế. Đây là hạn chế về
> **dữ liệu**, không phải về mã — và phải viết đúng như vậy, vì hai loại hạn chế
> này được hội đồng đánh giá rất khác nhau.

### M4 — Danh mục & Registry (11 bảng)

| Bảng | Khoá chính | Type | Scope | Cha | Nối giữa | Lifecycle | RLS |
|---|---|---|---|---|---|---|:--:|
| `languages` | `code` | Catalogue | Platform | — | — | Catalogue | — |
| `regions` | `code` | Catalogue | Platform | — | — | Catalogue | — |
| `dialects` | (`tenant_id`,`dialect_id`) | Catalogue | Tenant | `tenants`, `languages` + tự trỏ `merged_into` | — | Mutable | ✔ |
| `dialect_aliases` | (`tenant_id`,`old_dialect_id`) | History | Tenant | `dialects` | — | Append-only | ✔ |
| `recognition_profiles` | (`tenant_id`,`profile_id`) | Catalogue | Tenant | `tenants` | — | Mutable | ✔ |
| `vocabulary_groups` | (`tenant_id`,`group_id`) | Catalogue | Tenant | `tenants` | — | Mutable | ✔ |
| `vocabulary_registry_meta` | `tenant_id` | Child (1:1) | Tenant | `tenants` | — | Mutable | ✔ |
| `registry_versions` | (`tenant_id`,`version`) | **Version** | Tenant | `tenants` | — | Immutable **theo quy ước** (không có trigger) | ✔ |
| `community_dialects` | `dialect_id` | Catalogue | **Community** | — | — | Mutable | — |
| `community_profiles` | `profile_id` | Catalogue | **Community** | — | — | Mutable | — |
| `community_versions` | `version` | Version | **Community** | — | — | Immutable | — |

> Ba bảng `community_*` **không** có cột `tenant_id` và **không** bật chính sách.
> Đây là mặt phẳng đọc chung, an toàn **chỉ vì** luật không-rơi-ngược được cưỡng
> chế ở tầng ứng dụng: dữ liệu chảy từ cộng đồng sang tổ chức đúng một lần lúc
> khởi tạo (`tenants.cloned_from_community_version`), không có đường ngược lại.
> Ở sơ đồ phân vùng, Community phải là **một mặt phẳng thứ ba**, không phải một
> tenant reserved — vì trong lược đồ thật nó **không** phải một hàng của `tenants`.

### M5 — Huấn luyện (3 bảng)

| Bảng | Khoá chính | Type | Scope | Cha | Nối giữa | Lifecycle | RLS |
|---|---|---|---|---|---|---|:--:|
| `training_jobs` | `job_id` | Child | Tenant | `tenants`, **`registry_versions`** | — | Mutable | ✔ |
| `training_job_classes` | (`job_id`,`class_idx`) | Assoc (snapshot) | Tenant | `training_jobs` | `training_jobs` ↔ `classes` | Immutable | ✔ |
| `training_metrics` | (`job_id`,`epoch`) | History | Tenant | `training_jobs` | — | Append-only | ✔ |

> `training_jobs(tenant_id, registry_version) → registry_versions(tenant_id, version)`
> là **quan hệ ghim phiên bản duy nhất tồn tại trong hệ thống**. Nó ghim *không
> gian nhãn*, không ghim *nội dung bộ dữ liệu*. Toàn bộ lập luận tái lập được
> (reproducibility) của quyển phải dừng đúng ở ranh giới này.
>
> `training_job_classes` có `class_idx` trong khoá chính — nó lưu **tập lớp thực
> sự tham gia sau ba cổng chặn** cùng chỉ số đã gán, không phải tập người dùng chọn.
> Đây là một `Assoc` mang ảnh chụp, phải giữ nguyên ở LDM chi tiết.

### M6 — Dịch vụ tổ chức & Tích hợp (12 bảng)

| Bảng | Khoá chính | Type | Scope | Cha | Nối giữa | Lifecycle | RLS |
|---|---|---|---|---|---|---|:--:|
| `plans` | `plan_code` | Catalogue | Platform | — | — | Catalogue | — |
| `tenant_subscriptions` | `subscription_id` | Child | Tenant | `tenants`, `plans` | — | Mutable | ✔ |
| `tenant_usage_daily` | (`tenant_id`,`usage_date`,`metric`) | History | Tenant | `tenants` | — | Upsert | ✔ |
| `tenant_exports` | `export_id` | Child | Tenant | `tenants` | — | Ephemeral | ✔ |
| `tenant_purges` | `purge_id` | Child | Tenant | `tenants` | — | Append-only | **—** |
| `webhook_endpoints` | `endpoint_id` | Child | Tenant | `tenants` | — | Mutable, Revocable | ✔ |
| `webhook_deliveries` | `delivery_id` | History | Tenant | `webhook_endpoints` | — | Append-only | ✔ |
| `support_tickets` | `ticket_id` | Child | Tenant | `tenants` | — | Mutable | ✔ |
| `support_messages` | `message_id` | Child | Tenant | `support_tickets` | — | Append-only | ✔ |
| `notifications` | `notification_id` | Child | Tenant | `tenants`, `users` | — | Mutable | ✔ |
| `event_outbox` | `event_id` | History | Tenant | `tenants` | — | Append-then-drain | ✔ |
| `google_sheets_sync_status` | `id` | Child | System | — | — | Upsert | — |

> `tenant_purges` là **bảng duy nhất** mang `tenant_id` mà không bật chính sách —
> ngoại lệ duy nhất còn lại của độ phủ cách ly. Đây là dòng phải nêu đích danh
> trong phần hạn chế, không được để nó tan vào một con số phần trăm.

### M7 — Pháp lý, Kiểm toán & Nền tảng (9 bảng)

| Bảng | Khoá chính | Type | Scope | Cha | Nối giữa | Lifecycle | RLS |
|---|---|---|---|---|---|---|:--:|
| `legal_documents` | `doc_id` | Version | Platform | — | — | **Immutable sau công bố** (trigger) | — |
| `legal_document_drafts` | `draft_id` | Child | Platform | — | — | Mutable | — |
| `legal_document_events` | `event_id` | History | Platform | — | — | Append-only | — |
| `user_consents` | `consent_id` | Assoc | Identity | `users` | `users` ↔ `legal_documents`(`kind`,`version`) | Append-only | — |
| `signer_consents` | `consent_id` | Assoc | Tenant | `signers` | `signers` ↔ `legal_documents`(`kind`,`version`) | Revocable (`withdrawn_at`) | ✔ |
| `audit_log` | `audit_id` | History | Tenant | `tenants`, `users` | — | Append-only | ✔ |
| `platform_settings` | `key` | Catalogue | Platform | — | — | Mutable | — |
| `sot_authorized_keys` | `public_key` | Catalogue | Platform | — | — | Revocable | — |
| `schema_migrations` | (`version`,`applied_at`) | History | System | — | — | Append-only | — |

> `user_consents` và `signer_consents` là **hai bảng khác nhau**, không phải hai
> lát của một bảng: vế thứ nhất là tài khoản chấp thuận điều khoản dịch vụ; vế
> thứ hai là **chủ thể dữ liệu** cho phép dùng dữ liệu của mình. Chỉ vế thứ hai
> chi phối đường phát hành dữ liệu. Ở CDM, gộp chúng là sai về ngữ nghĩa pháp lý.
>
> `legal_documents` **không có** bảng phiên bản con: định danh nghiệp vụ là cặp
> (`kind`, `version`) trên chính bảng đó, và cả hai bảng đồng thuận đều trỏ vào
> cặp này bằng khoá ngoại ghép.

---

## 3. Ma trận phạm vi — tổng hợp

| Mặt phẳng | Số bảng | Có `tenant_id` | Bật RLS |
|---|---:|---:|---:|
| Tenant | 35 | 35 | 34 |
| Platform (danh mục, pháp lý, cấu hình, phân quyền) | 11 | 0 | 0 |
| Identity (thuộc tài khoản) | 7 | 0 | 0 |
| Community | 3 | 0 | 0 |
| System / vận hành | 2 | 0 | 0 |
| **Cộng** | **58** | **35** | **34** |

Ranh giới Tenant trùng **chính xác** với tập bảng mang cột `tenant_id`: 35/35.
Không có bảng nào thuộc tổ chức mà thiếu cột phạm vi, và ngược lại.

Độ phủ cách ly: **34/35 ≈ 97,1 %**; cả 34 bảng đều bật cờ cưỡng chế với chủ sở
hữu bảng (34/34 = 100 %); tổng số chính sách = 34.

Mọi chính sách đều cùng một khuôn:

```sql
(current_setting('app.system_scope', true) = 'on')
OR (tenant_id = current_setting('app.tenant_id', true))
```

riêng `roles` thêm nhánh `tenant_id IS NULL` để danh mục vai nền tảng đọc được từ
mọi tổ chức.

---

## 4. Khoá ngoại ghép giữ phạm vi — bằng chứng có thật

Đây là nhóm ràng buộc đáng đưa vào quyển nhất, vì nó làm việc trỏ chéo tổ chức
**bất khả thi ở tầng ràng buộc**, chứ không chỉ bị chặn ở tầng ứng dụng:

```
memberships(tenant_id, workspace_id)             → workspaces(tenant_id, workspace_id)
memberships(tenant_id, workspace_id, project_id) → projects(tenant_id, workspace_id, project_id)
projects(tenant_id, workspace_id)                → workspaces(tenant_id, workspace_id)
samples(tenant_id, class_uid)                    → classes(tenant_id, class_uid)
samples(tenant_id, signer_id)                    → signers(tenant_id, signer_id)
samples(tenant_id, dialect)                      → dialects(tenant_id, dialect_id)
classes(tenant_id, dialect)                      → dialects(tenant_id, dialect_id)
classes(tenant_id, recognition_profile)          → recognition_profiles(tenant_id, profile_id)
classes(tenant_id, vocabulary_group)             → vocabulary_groups(tenant_id, group_id)
capture_sessions(tenant_id, class_uid)           → classes(tenant_id, class_uid)
capture_sessions(tenant_id, signer_id)           → signers(tenant_id, signer_id)
raw_uploads(tenant_id, class_uid)                → classes(tenant_id, class_uid)
raw_uploads(tenant_id, dialect)                  → dialects(tenant_id, dialect_id)
dialect_aliases(tenant_id, new_dialect_id)       → dialects(tenant_id, dialect_id)
signer_aliases(tenant_id, new_signer_id)         → signers(tenant_id, signer_id)
training_jobs(tenant_id, registry_version)       → registry_versions(tenant_id, version)
training_metrics(tenant_id, job_id)              → training_jobs(tenant_id, job_id)
memberships(parent_membership_id, user_id)       → memberships(membership_id, user_id)
user_consents(kind, version)                     → legal_documents(kind, version)
signer_consents(kind, version)                   → legal_documents(kind, version)
```

Hai dòng cuối không phải khoá phạm vi mà là **khoá ghim phiên bản**: một bản ghi
đồng thuận trỏ tới đúng phiên bản văn bản đã ký, và văn bản đó bất biến sau công bố.

### 4.1 Sáu trigger — bất biến duy nhất được cưỡng chế ở tầng CSDL

| Trigger | Bảng | Bảo vệ điều gì |
|---|---|---|
| `trg_legal_documents_freeze` | `legal_documents` | bất biến sau công bố |
| `trg_legal_events_append_only` | `legal_document_events` | chỉ thêm |
| `ct_memberships_chain` | `memberships` | membership cấp dưới phải có membership cấp trên |
| `ct_role_assignments_scope` | `role_assignments` | lần gán vai khớp phạm vi của membership |
| `ct_role_permissions_dominance` | `role_permissions` | vai không cấp được quyền vượt cấp |
| `ct_roles_tenant_type` | `roles` | vai nền tảng và vai tổ chức không lẫn nhau |

**`registry_versions` KHÔNG nằm trong danh sách này.** Tính bất biến của ảnh chụp
registry là quy ước ở tầng ứng dụng, không có trigger đứng sau — khác hẳn
`legal_documents`. Chương 3 phải nói đúng mức bảo đảm của từng cái, đừng gộp cả
hai vào một câu "bất biến".

---

## 5. Ghi chú cho bước dựng sơ đồ

**Số miền nên dùng: 7, không phải 13.** Với 58 bảng, chia 13 miền cho ra trung
bình 4,5 bảng mỗi miền — sơ đồ quá mỏng, và taxonomy M1–M7 đã dùng xuyên suốt
Phụ lục A rồi. Giữ M1–M7 thì `LDM-0x`, `PDM-0x`, `DD-0x` khớp sẵn với phần đã viết.

**Số thực thể ở CDM:** rút 58 bảng về khoảng 18–20 thực thể nghiệp vụ. Các bảng
`Ephemeral` của M1 (token, mã xác minh, mã hành động) gộp về một khái niệm
*Thông tin xác thực*; các bảng `History` (`*_aliases`, `*_events`, `webhook_deliveries`,
`training_metrics`) không lên CDM.

**Các `Assoc` bắt buộc giữ ở LDM chi tiết** (có thuộc tính/vòng đời riêng):
`memberships`, `role_assignments`, `training_job_classes`, `user_consents`,
`signer_consents`. Riêng `role_permissions` là `Bridge` thuần — CDM có thể vẽ M:N.

**Đừng vẽ ở ERD:** RLS, `system_scope`, luồng passcode → hành động nhạy cảm,
đường Celery/Redis. Dùng stereotype `«tenant-scoped»` cộng chú giải, và đẩy luồng
sang biểu đồ tuần tự.
