# Kiến trúc multi-tenant — Tenant / Workspace / Project / Repository

Ngày 2026-08-04. Bản thiết kế tổng thể do chủ dự án chốt, kèm **chín điểm** mà
bản gốc còn để mở hoặc tự mâu thuẫn — các điểm đó đã được chốt sẵn ở §1 và đánh
dấu **▲ CHỐT** ngay tại chỗ áp dụng. Sửa lại chỗ nào không đồng ý thì sửa ở §1,
phần thân sẽ theo.

```
Tenant  — công ty/tổ chức, ranh giới cô lập dữ liệu
├── Workspace — phòng ban / nhóm nghiên cứu / đơn vị
│   ├── Project — dự án (thuộc ĐÚNG một workspace)
│   │   └── Repository — không gian file + version
│   │       ├── Folder / File / Artifact
│   │       ├── Dataset / Document
│   │       └── Branch / Commit / Release
│   └── Personal Workspace
└── Tenant-level policies
```

Quan hệ với tài liệu khác:

| tài liệu | vai trò |
|---|---|
| [`MULTITENANT_PREP.md`](../11-worklog/MULTITENANT_PREP.md) | ghi 2026-07-31 — nền `tenant_id` **đã đặt** trong `metadata_db.py`, và danh sách chỗ còn giả định một tenant. Vẫn đúng, tài liệu này **mở rộng** chứ không thay thế. |
| [`REGISTRY_ARCHITECTURE.md`](REGISTRY_ARCHITECTURE.md) | ba mặt phẳng Community/Tenant/Artifact. §14 dưới đây **không được** mâu thuẫn với nó. |
| [`AUTH_TOKEN_LIFECYCLE.md`](../03-security/AUTH_TOKEN_LIFECYCLE.md) | các lỗ hổng vòng đời token; §19 phụ thuộc vào việc vá xong. |
| `docs/06-operations/OBSERVABILITY_PLAN.md` | Loki label bounded + audit ở Postgres. §18 áp dụng nguyên tắc đó. |

---

## 1. Chín điểm chốt (khác hoặc bổ sung so với bản gốc)

| # | vấn đề trong bản gốc | ▲ CHỐT |
|---|---|---|
| 1 | §12.4 đặt blob ở `/data/tenants/<id>/objects/` (storage nền tảng) trong khi đã quyết định tenant cắm Drive của họ | **Drive của tenant là kho blob MỜ**: tên object là `blob_id`, không có cấu trúc thư mục nghiệp vụ, backend là người đọc duy nhất. Cây đọc-được cho người chỉ là **export tuỳ chọn**. |
| 2 | §12.5 cây vật lý materialized song song với DB | Cây vật lý là **dẫn xuất, dựng lại được bằng một lệnh, không ai ghi tay, không bao giờ là nguồn sự thật**. Nếu không có consumer thật thì **bỏ hẳn**. |
| 3 | §18 `SET LOCAL` trên connection pool | Bắt buộc **một context manager duy nhất** mở transaction + set context + trả conn. **Cấm** gọi `get_pooled_conn()` trực tiếp ở tầng nghiệp vụ. Cấm `SET` không có `LOCAL`. |
| 4 | RLS policy hỏi bảng cũng bật RLS → đệ quy | Dùng hàm **`SECURITY DEFINER`** trả tập quyền đã tính; bảng membership có policy permissive riêng. |
| 5 | §4.1 `access_scope` liệt kê 3 giá trị (trùng lặp), chưa định nghĩa Admin + `PROJECT_ONLY` | Chỉ có **2** giá trị. Ràng buộc DB: `workspace_role ∈ {Admin, Manager}` ⇒ ép `FULL_WORKSPACE`. |
| 6 | §9 "mỗi user tối đa 1 Personal Workspace" vs §3.3 user thuộc nhiều tenant | Personal Workspace là **một cho mỗi cặp (user, tenant)**, nằm hẳn trong ranh giới tenant. |
| 7 | §14.5 fork dùng chung blob vs §15.4 xoá vật lý theo consent | Dữ liệu có **consent ràng buộc KHÔNG được dedup xuyên project/fork** — fork phải copy thật. `ref_count` thay bằng **GC mark-and-sweep**. |
| 8 | §5.5 thiếu luật chống leo thang quyền | **Không ai cấp được vai trò cao hơn vai trò của chính mình** trên cùng tài nguyên. `share.reshare` bị chặn trần bởi role của người reshare. |
| 9 | §2.1 Tenant Admin "không giới hạn" vs §16.4 audit bất biến | Tenant Admin **không xoá/sửa được audit của tenant mình**. Runtime role bị `REVOKE UPDATE, DELETE` trên `audit_events` / `access_events`. |

Hai mục bản gốc bỏ sót, được bổ sung ở §19 và §18.4: **luật vàng cấu hình bảo
mật tenant** và **bộ xem log của tenant**.

---

## 2. Phạm vi từng tầng

| Tầng | Ý nghĩa |
|---|---|
| Tenant | Ranh giới công ty, cô lập dữ liệu |
| Workspace | Phòng ban, nhóm cộng tác, chính sách |
| Project | Đơn vị sở hữu và thực hiện công việc |
| Repository | Không gian quản lý file và version |
| Folder / File / Dataset | Tài nguyên cụ thể, phân quyền riêng được |

Repository **không chỉ** chứa dataset/video. Nó chứa video, ảnh, âm thanh, NPZ,
CSV, JSON, YAML, DOCX, PDF, TXT, Markdown, biểu mẫu, template, tài liệu nội bộ,
cấu hình nghiệp vụ. Vì vậy tầng lưu trữ là **Versioned Artifact Repository độc
lập định dạng**: nó quản đường dẫn logic, revision, blob, lịch sử, branch,
commit, release, share, fork — không quản "ý nghĩa" của file.

Mỗi project thuộc **đúng một** workspace. Nhưng:

> **Thuộc cùng workspace KHÔNG có nghĩa được xem mọi project trong workspace đó.**

---

## 3. Nguyên tắc visibility

### 3.1 Tenant Admin

Tương đương lãnh đạo cấp cao nhất của công ty. Nhìn thấy toàn bộ workspace,
project và tài nguyên trong tenant; xem thành viên, quyền và lịch sử; quản lý
tenant members; tạo/archive/khôi phục workspace; cấp và thu hồi vai trò; cấu
hình tenant policy; phê duyệt thao tác nhạy cảm; move project giữa workspace;
xem audit và access log; emergency revoke.

Đây là vai trò nghiệp vụ **duy nhất** không bị giới hạn bởi workspace, project
hoặc resource grant **trong chính tenant đó**.

Nhưng hành động quan trọng vẫn phải: xác thực lại, MFA nếu tenant bật, nhập lý
do, ghi audit, và có thể cần người phê duyệt thứ hai.

```
Tenant Admin xem Project X         → được phép
Tenant Admin chuyển Project X      → cần xác thực lại
Tenant Admin xoá dữ liệu nhạy cảm  → cần policy và quy trình xoá
```

> **▲ CHỐT (điểm 9).** "Không giới hạn" là về **đọc và quản trị**, không phải về
> audit. Tenant Admin **không** xoá hay sửa được `audit_events` / `access_events`
> của tenant mình. Audit mà chủ thể xoá được thì vô nghĩa với đúng người cần
> giám sát nhất. Cưỡng chế ở tầng DB, không phải ở tầng ứng dụng.

### 3.2 Workspace Admin và Workspace Manager

**Workspace Admin** — toàn quyền trong workspace được giao: thấy toàn bộ project;
quản lý thành viên; tạo/archive/khôi phục project; quản lý workspace policy; phê
duyệt share/import/export/move; xem quyền mọi project; xem audit thuộc workspace.

**Workspace Manager** — gần Admin: thấy toàn bộ project; quản lý hoạt động và
chia sẻ; quản lý thành viên thường; phê duyệt một số thao tác theo policy. Nhưng
**không** xoá workspace, **không** thay Workspace Admin, **không** sửa policy cấp
cao trừ khi có capability riêng.

### 3.3 Các vai trò còn lại

Workspace Editor / Commenter / Viewer **không** tự động thấy toàn bộ project. Họ
chỉ thấy project mình là thành viên, project được share trực tiếp, file/folder
được cấp quyền, và tài nguyên chung của workspace mà role cho phép.

> **Nhìn thấy Workspace ≠ Nhìn thấy toàn bộ Project trong Workspace.**

User có thể thấy *tên* workspace để biết project nằm ở đâu, nhưng không được xem
danh sách hay metadata của project không được cấp.

### 3.4 Cùng workspace không tự động có quyền

Hai project cùng workspace chỉ có nghĩa **đủ điều kiện để thiết lập direct
share**. Quyền thật phải có ít nhất một trong:

```
Project membership
OR Resource grant
OR Active share
OR Share link hợp lệ
OR Workspace Admin/Manager
OR Tenant Admin
```

---

## 4. Định danh người dùng

**Không** dùng email, username hay số tăng dần làm định danh phân quyền chính.

### 4.1 Định danh toàn hệ thống

```
users
- user_id UUID          -- bất biến, không phụ thuộc email, không hiển thị để nhập tay
- display_name
- status
- created_at
- disabled_at
```

### 4.2 Danh tính đăng nhập

```
user_identities
- identity_id UUID
- user_id UUID
- identity_type          -- EMAIL | USERNAME | GOOGLE | MICROSOFT | INSTITUTION_ACCOUNT
- normalized_value
- verified_at
- is_primary
```

Quyền **không** gắn với email. Đổi email thì permission vẫn còn, vì permission
gắn với `user_id` / `tenant_member_id`.

### 4.3 Thành viên trong tenant

```
tenant_members
- tenant_member_id UUID  -- danh tính của user TRONG một tenant
- tenant_id UUID
- user_id UUID
- public_member_code
- tenant_role            -- TENANT_ADMIN | TENANT_AUDITOR | TENANT_MEMBER
- status
- joined_at
```

```
User U1
├── Tenant A → tenant_member_id M1
└── Tenant B → tenant_member_id M2
```

Permission trong tenant lưu bằng `tenant_member_id`.

> **Ghi chú migration.** Bảng `tenant_members` hiện có (`metadata_db.py`) dùng
> khoá `(tenant_id, user_id)` và role `admin|editor|viewer`. Cần thêm
> `tenant_member_id` làm surrogate key, `public_member_code`, `status`, và ánh xạ
> role cũ → mới. Hàm `can_edit_registry` trong `vocabulary_registry.py` đã ép
> đúng nguyên tắc "editor tenant A không có quyền ở tenant B" — giữ nguyên logic,
> chỉ đổi cột.

### 4.4 Mã thành viên công khai

Để share riêng tư qua ID, mỗi tenant member có mã dễ nhập:

```
USR-7Q2M-4K8P
```

Sinh ngẫu nhiên, không tuần tự, không chứa thông tin nội bộ, khó đoán, unique,
rotate được, **không phải khoá chính**.

Người dùng tìm người nhận bằng: tên, email đã xác minh, mã thành viên, danh bạ
tenant, hoặc nhóm. Backend phải **chuyển giá trị tìm kiếm thành
`tenant_member_id` hợp lệ trước khi tạo quyền**.

Không được tin trực tiếp `user_id` do client gửi. Backend xác minh: user tồn tại
+ membership đang active + đúng tenant + người cấp có thẩm quyền + resource nằm
trong phạm vi cho phép.

### 4.5 Người chưa có tài khoản

```
resource_invitations
- invitation_id / tenant_id
- invited_email
- resource_type / resource_id
- intended_role
- invited_by / expires_at / status
```

```
Mời bằng email → PENDING
→ người nhận đăng ký và XÁC MINH email
→ liên kết invitation với user_id
→ tạo tenant membership
→ tạo resource grant
```

**Không tạo quyền vĩnh viễn dựa trên email chưa xác minh.**

---

## 5. Membership ba tầng

```
tenant_members → workspace_members → project_members
```

### 5.1 Workspace membership

```
workspace_members
- workspace_member_id
- tenant_id / workspace_id
- tenant_member_id
- workspace_role     -- ADMIN | MANAGER | EDITOR | COMMENTER | VIEWER
- access_scope       -- FULL_WORKSPACE | PROJECT_ONLY
- status
```

> **▲ CHỐT (điểm 5).** `access_scope` có **đúng hai** giá trị (bản gốc liệt kê
> `FULL_WORKSPACE` hai lần). Và ràng buộc DB:
>
> ```sql
> CHECK (workspace_role NOT IN ('ADMIN','MANAGER') OR access_scope = 'FULL_WORKSPACE')
> ```
>
> Admin/Manager theo định nghĩa nhìn toàn workspace; lưu tổ hợp
> `ADMIN + PROJECT_ONLY` là trạng thái vô nghĩa, chặn ngay ở schema thay vì để
> tầng ứng dụng đoán.

**`FULL_WORKSPACE`** — thành viên thật của phòng ban: thấy workspace, truy cập
tài nguyên chung theo role, được thêm vào nhiều project, xem danh bạ workspace
nếu được phép.

**`PROJECT_ONLY`** — chỉ đặt trong workspace để tiếp tục truy cập một/vài
project: thấy workspace chứa project, **chỉ** thấy project được cấp, không thấy
project khác, không thấy tài nguyên chung, không xem toàn bộ thành viên workspace,
**không thừa hưởng** quyền workspace-level.

Dùng khi: mời cộng tác viên vào một project; project được chuyển sang workspace
mới; thành viên cũ cần giữ quyền project nhưng không thuộc phòng ban mới.

### 5.2 Project membership

```
project_members
- project_member_id
- tenant_id / workspace_id / project_id
- tenant_member_id
- project_role       -- ADMIN | MANAGER | EDITOR | COMMENTER | VIEWER
- status
```

Project member **phải** có workspace membership tương ứng, nhưng membership đó có
thể là `PROJECT_ONLY`.

Xoá hoặc khoá workspace membership **phải** xử lý đồng thời project membership
liên quan — không để quyền mồ côi.

---

## 6. Role và Capability

Role chỉ là **một tập permission định nghĩa sẵn**. Backend kiểm tra capability,
không viết logic theo tên role.

### 6.1 Tenant

| Role | Phạm vi |
|---|---|
| Tenant Admin | Toàn bộ tenant |
| Tenant Auditor | Audit và lịch sử; mặc định không chỉnh nội dung |
| Tenant Member | Chỉ phạm vi được cấp |

### 6.2 Workspace

| Role | Quyền mặc định |
|---|---|
| Workspace Admin | Toàn quyền workspace |
| Workspace Manager | Thấy toàn workspace, quản lý hoạt động và share |
| Workspace Editor | Chỉnh tài nguyên workspace-level hoặc project được cấp |
| Workspace Commenter | Xem và bình luận tài nguyên được cấp |
| Workspace Viewer | Chỉ xem tài nguyên được cấp |

Chỉ Admin và Manager nhìn toàn bộ project. Editor/Commenter/Viewer vẫn cần
project membership hoặc resource grant cụ thể.

### 6.3 Project

| Role | Quyền mặc định |
|---|---|
| Project Admin | Quản lý project, member, policy, share |
| Project Manager | Quản lý hoạt động, repository, release |
| Project Editor | Tạo và chỉnh sửa dữ liệu |
| Project Commenter | Xem và bình luận |
| Project Viewer | Chỉ xem |

### 6.4 Resource

Cho repository, folder, file, dataset, document:

| Role | Quyền |
|---|---|
| Viewer | Xem |
| Commenter | Xem + bình luận |
| Editor | Xem + bình luận + sửa |
| Manager | Editor + quản lý chia sẻ |
| Owner | Toàn quyền với tài nguyên |

Giao diện giống Google Drive, nhưng backend luôn kiểm tra capability cụ thể.

### 6.5 Danh mục capability

```
# Nội dung
resource.discover          resource.view_metadata     resource.view_content
resource.comment           resource.edit              resource.rename
resource.move              resource.delete            resource.restore

# File
file.upload   file.replace   file.download   file.preview   file.view_history

# Chia sẻ
share.create        share.manage       share.change_role
share.revoke        share.create_link  share.reshare      share.view_access_list

# Project
project.create      project.update     project.archive    project.restore
project.move        project.manage_members                project.manage_policy

# Import / Export
import.create  import.approve  import.cancel
export.create  export.approve  export.download  export.cancel

# Repository / version
repository.create_branch    repository.commit          repository.open_merge_request
repository.review_merge_request                        repository.merge
repository.create_release   repository.restore_revision

# Fork
fork.create   fork.sync_upstream   fork.view_upstream
fork.propose_merge             fork.detach_upstream

# Audit
audit.view    access_log.view     permission_history.view     export_history.view
```

**`view`, `download`, `export` và `fork` là bốn quyền khác nhau.** Người dùng có
thể xem nội dung trong hệ thống mà không được tải hay xuất ra ngoài.

### 6.6 Chống leo thang quyền

> **▲ CHỐT (điểm 8).** Bản gốc thiếu hẳn luật này — thiếu nó thì một Editor có
> `share.create` cấp được Owner cho người khác (và gián tiếp cho chính mình).
>
> 1. **Không ai cấp được vai trò cao hơn vai trò của chính mình** trên cùng tài
>    nguyên. Thứ tự: `Viewer < Commenter < Editor < Manager < Owner`.
> 2. `share.reshare` bị chặn trần bởi role hiệu lực của người reshare, không phải
>    role gốc của grant.
> 3. Không ai tự nâng role của chính mình. Đổi role của chính mình luôn cần một
>    principal khác có thẩm quyền cao hơn.
> 4. Tenant Admin là ngoại lệ duy nhất, và mọi lần dùng ngoại lệ đều ghi audit
>    với `permission_source = TENANT_ADMIN`.

---

## 7. Quyền hiệu lực

```
        Tenant role
      ∪ Workspace role
      ∪ Project role
      ∪ Resource grant
      ∪ Share grant
      ∪ Share link
```

rồi **bị giới hạn** bởi:

```
      ∩ Tenant policy
      ∩ Workspace policy
      ∩ Project policy
      ∩ Data classification
      ∩ Consent / license policy
      ∩ Resource restriction
```

> **Deny hoặc restriction mạnh hơn Allow.**

```
Project role cho phép export
Share grant cho phép export
Nhưng consent policy cấm export
→ KHÔNG được export
```

Ngoại lệ nghiệp vụ đã chốt: Tenant Admin truy cập được toàn tenant. Nhưng xoá,
export dữ liệu nhạy cảm, move project và đổi Admin vẫn phải qua xác thực + audit.

Giai đoạn đầu **không** triển khai explicit deny tuỳ ý cho từng user — nó làm mô
hình quyền khó hiểu. Restriction đến từ policy và data classification.

---

## 8. Chia sẻ

### 8.1 Đối tượng chia sẻ được

workspace-level folder, project, repository, folder, file, document, dataset,
dataset version, release, template, link.

### 8.2 Đối tượng nhận quyền

```
USER | GROUP | PROJECT | WORKSPACE | TENANT | SHARE_LINK
```

```
File A
├── User U1 — Editor
├── User U2 — Commenter
├── Project P2 — Viewer
└── Group Research-Team — Viewer
```

### 8.3 Chế độ visibility

**Private / Restricted** (mặc định) — chỉ owner + project members được phép +
người được thêm trực tiếp. Private **không** có nghĩa một người: owner có thể
thêm user, group hoặc project khác.

**Project access** — chia cho thành viên project theo role tương ứng.

**Workspace access** — cấp cho toàn workspace, một nhóm, hoặc một số workspace
role:

```
Everyone in Workspace A — Viewer
Workspace Editors — Commenter
```

Workspace access **không** tự động cấp quyền edit.

**Tenant access** — chỉ cho tài nguyên nội bộ toàn công ty: `Anyone in Tenant — Viewer`.

**Link access** — bốn mức:

```
Specific invited users with link
Anyone in this Workspace with link
Anyone in this Tenant with link
Anyone with link
```

`Anyone with link` **bị cấm mặc định** với: raw video; thông tin người tham gia;
tài liệu nội bộ nhạy cảm; dữ liệu bị hạn chế download; dữ liệu có consent giới hạn.

### 8.4 Share link

```
share_links
- share_link_id / tenant_id
- resource_type / resource_id
- token_hash                 -- CHỈ lưu hash
- link_scope / resource_role
- allow_download / allow_export
- expires_at / max_uses / usage_count
- password_hash
- created_by / revoked_by / revoked_at / status
```

Token thật chỉ hiển thị một lần khi tạo link.

### 8.5 Kế thừa quyền

Folder con và file mặc định kế thừa từ folder cha (`inherit_permissions = true`).
Nguồn quyền phải được lưu:

```
DIRECT | PROJECT_ROLE | WORKSPACE_ROLE | INHERITED_FOLDER
       | SHARE_GRANT  | SHARE_LINK     | TENANT_ADMIN
```

Tắt kế thừa thì: UI cảnh báo, quyền tính độc lập, mọi thay đổi ghi audit.

### 8.6 Bình luận

```
comments
- comment_id / resource_id / artifact_revision_id / parent_comment_id
- author_member_id / content
- anchor_type / anchor_value
- status / created_at / resolved_at
```

`anchor_value` có thể là: trang PDF, đoạn văn, dòng text, timecode video, hoặc
cell/row của dữ liệu có cấu trúc.

---

## 9. Màn hình Manage Access

Mỗi project, repository, folder, file có một màn hình Manage access hiển thị: ai
có quyền; role; **quyền đến từ đâu**; trực tiếp hay kế thừa; ngày cấp; người cấp;
ngày hết hạn; quyền download; quyền export; share link đang hoạt động; group/
project đang được cấp; và **policy nào đang hạn chế**.

```
Nguyễn A — Editor
Nguồn: Project role

Trần B — Commenter
Nguồn: Direct share    Cấp bởi: Nguyễn C    Hết hạn: 30/08/2026

Project Research B — Viewer
Nguồn: Repository share

Anyone in Tenant — Viewer
Nguồn: Link access     Download: Disabled
```

Người đủ quyền có thể: thêm user/group, đổi role, cấm download, đặt hạn, thu hồi
quyền, thu hồi link, xem lịch sử cấp quyền.

---

## 10. Personal Workspace

> **▲ CHỐT (điểm 6).** Bản gốc nói "mỗi user tối đa một Personal Workspace" trong
> khi §4.3 cho phép user thuộc nhiều tenant. Nếu Personal Workspace là **toàn
> cục**, nó thành cây cầu vượt ranh giới tenant: user staging dữ liệu tenant A
> vào đó rồi share sang tenant B — thủng đúng thứ đang xây.
>
> **Một Personal Workspace cho mỗi cặp (user, tenant)**, nằm hẳn trong ranh giới
> tenant, chịu policy và quota của tenant đó.

```
system_settings
- setting_key / setting_value / value_type / updated_by / updated_at
```

```
personal_workspace_limit_per_user_per_tenant = 1
personal_workspace_project_limit            = 5
```

Tenant override được (System default 5 → Tenant A 10, Tenant B dùng mặc định).

Personal Workspace: owner là Workspace Admin; mặc định Restricted; tạo một lần;
thêm thành viên được; share project/file/folder được; người được mời **không**
trở thành owner; quota tính riêng; **không** tự động cho tenant member khác nhìn thấy.

Khi user bị vô hiệu hoá: không xoá ngay; Tenant Admin chuyển được ownership; dữ
liệu giữ theo retention policy; share link có thể bị suspend.

---

## 11. Import và Export

### 11.1 Định dạng

Nhận: video/ảnh/audio; NPZ, NPY; CSV, TSV; JSON, YAML; DOCX, PDF; TXT, Markdown;
ZIP/TAR package; dataset manifest; repository package; template package.

File không nhận diện được vẫn lưu dưới dạng binary artifact, chỉ không tự parse
metadata.

### 11.2 Luồng import

```
Chọn file/package → Chọn Workspace/Project/Folder đích → Kiểm tra quyền
→ Kiểm tra định dạng → Quét file nguy hiểm → Tính checksum → Preview
→ Mapping metadata/profile → Xác nhận → Tạo artifact/revision → Tạo commit → Ghi audit
```

Import **không được ghi đè** file cũ. Trùng tên thì chọn: Replace as new revision
/ Keep both / Rename imported / Skip / Cancel.

### 11.3 Export

Export được: file, folder, dataset version, repository release, project, toàn bộ
repository. Package gồm:

```
manifest.json  files/  checksums.sha256  metadata.json
registry_snapshot.json  lineage.json  permissions_summary.json  export_info.json
```

Quyền tách bốn tầng: `resource.view` / `file.download` / `export.create` /
`export.approve`.

**Mọi export phải log** — dữ liệu đã ra ngoài thì không thu hồi hoàn toàn được
bằng kỹ thuật.

### 11.4 Giữa các workspace

Hai cơ chế: **direct share** (nếu tenant policy và cả hai workspace cho phép),
hoặc **export/import có kiểm soát**:

```
Project nguồn yêu cầu export → Workspace nguồn duyệt → Tạo package bất biến
→ Workspace đích duyệt import → Project đích chấp nhận → Ghi lineage
```

Không bắt buộc mọi trao đổi khác workspace phải copy dữ liệu; chọn giữa share và
import tuỳ policy.

---

## 12. Di chuyển Project sang Workspace khác

Giữ nguyên: `project_id`, `repository_id`, `dataset_id`, `artifact_id`, history.
Thay đổi: `projects.workspace_id`, `project_storage_locations`, membership liên
quan workspace, share liên quan workspace, policy hiệu lực.

### 12.1 Ai được thực hiện

Tenant Admin, **hoặc** (Source Workspace Admin + Target Workspace Admin + Project
Admin). Policy có thể yêu cầu thêm approver.

Người thực hiện phải: xác thực lại, có `project.move`, nhập lý do, xem trước ảnh
hưởng, xác nhận lần cuối.

### 12.2 Hai loại move — đừng dùng chung một máy trạng thái

> **▲ CHỐT (hệ quả của điểm 1).** Blob nằm trong phạm vi tenant
> (`objects/` của tenant). Do đó **move project TRONG cùng tenant không đụng vào
> blob**. Bản gốc gộp hai ca vào một máy trạng thái 11 bước, khiến ca phổ biến
> nhất phải chịu copy–verify–grace vô ích.

**Move nội bộ tenant** (ca thường):

```
PENDING_APPROVAL → APPROVED → LOCKED → UPDATING_DATABASE → COMPLETED
                                              ↘ FAILED
```

Không có `MOVING_STORAGE`, không `VERIFYING` checksum, không grace period. Blob
đứng yên; chỉ cập nhật DB và dựng lại cây link (nếu §16.5 còn giữ cây).

**Move xuyên tenant** (hiếm, cần Tenant Admin hai bên): mới cần đủ
`PREPARING → MOVING_STORAGE → VERIFYING → ROLLING_BACK`, vì blob phải copy sang
storage của tenant đích (§17.5).

### 12.3 Luồng move nội bộ

```
1. Tạo project_move_request
2. Kiểm tra quyền và approver
3. Chụp snapshot hiện trạng (permission + policy)
4. Khoá ghi tạm thời
5. Kiểm tra quota workspace mới
6. Chuẩn bị membership mới (PROJECT_ONLY cho người chưa thuộc workspace đích)
7. Cập nhật workspace_id + project_storage_locations
8. Áp policy workspace mới
9. Đánh giá lại toàn bộ share
10. Dựng lại cây link (nếu có)
11. Mở khoá project
12. Thông báo thành viên
13. Ghi audit
```

### 12.4 Dataset sau khi move

Vì `project_id` giữ nguyên: dataset không đổi owner; dataset version không bị
viết lại; registry snapshot không đổi; lineage không đổi; artifact không mất liên
kết. Chỉ **phạm vi workspace và policy hiệu lực** thay đổi.

### 12.5 Thành viên sau khi move

Giữ nguyên project role. Ai chưa thuộc workspace mới thì tạo workspace membership
với `access_scope = PROJECT_ONLY`.

Họ **vẫn**: thấy project, truy cập tài nguyên project, comment/sửa theo role cũ.
Họ **không**: thấy project khác trong workspace mới, thấy tài nguyên chung, xem
toàn bộ thành viên workspace, dùng capability workspace-level.

UI phải nói rõ:

```
Project X đã được chuyển sang Workspace Y.
Bạn vẫn có quyền Editor trong Project X.
Quyền này KHÔNG bao gồm các Project khác trong Workspace Y.
```

### 12.6 Share sau khi move

| loại share | xử lý |
|---|---|
| Direct user grant | giữ, trừ khi policy mới hạn chế hơn → `SUSPENDED_PENDING_REVIEW` |
| Share với project cùng chuyển | giữ active sau khi xác minh lại policy |
| Share với project ở workspace cũ | thành cross-workspace → `SUSPENDED_PENDING_REAPPROVAL`, cần Admin hai bên duyệt (hoặc Tenant Admin theo policy), hoặc chuyển sang import/export/fork |
| Share link | đánh giá lại scope workspace/tenant/public; link không hợp lệ **bị suspend trước**, không âm thầm tiếp tục |

### 12.7 Archive sau khi move

Vì giữ nguyên `project_id`, **không** archive chính project đang hoạt động. Thứ
được archive: binding workspace cũ, storage location cũ, permission snapshot cũ,
policy snapshot cũ, move snapshot.

```
Project P01
├── Workspace W01 — ARCHIVED_BINDING
└── Workspace W02 — ACTIVE_BINDING
```

Archive project row cũ rồi tạo project mới sẽ làm đổi `project_id` — trái yêu cầu.

---

## 13. Đường dẫn và storage

Tách **ba** khái niệm: logical path / project physical tree / immutable blob storage.

### 13.1 PostgreSQL là nguồn sự thật

Postgres quản: tenant, workspace, project, folder tree, artifact, revision,
ownership, permissions, storage location, share, fork, audit.

**Filesystem không tự quyết định quyền.**

### 13.2 Đường dẫn logic

```
/Documents/Consent/form.docx
/Datasets/Fingerspelling/sample-001.npz
```

```
artifact_nodes
- artifact_id / project_id / parent_folder_id
- name / relative_path / current_revision_id
```

**Không lưu absolute path** vào từng artifact.

### 13.3 Project storage root

```
project_storage_locations
- storage_location_id / project_id / tenant_id / workspace_id
- root_path / status / move_job_id / created_at / archived_at
```

Đường dẫn đầy đủ = `root_path + relative_path`. Move project chỉ cập nhật root,
không cập nhật đường dẫn tuyệt đối của từng file.

### 13.4 Blob bất biến — và nó nằm ở đâu

```
blob_objects
- blob_id / tenant_id / storage_key
- size / checksum / media_type / status
```

```
artifact_revisions
- revision_id / artifact_id / blob_id / created_by / created_at
```

> **▲ CHỐT (điểm 1) — mâu thuẫn lớn nhất của bản gốc.**
>
> Bản gốc đặt blob ở `/data/tenants/<tenant_id>/objects/...` (storage nền tảng),
> nhưng quyết định trước đó là **tenant cắm Drive của họ**. Hai cái không cùng
> tồn tại êm được: nếu tenant nhìn thấy cây thư mục thật trên Drive của họ thì
> **ACL của Google vượt mặt toàn bộ §6–§8** — ai có quyền trên Drive đó đọc được
> hết, còn share link, expiry, `allow_download` của hệ thống chỉ là trang trí.
>
> **Chốt: Drive của tenant là kho blob MỜ.**
>
> - `storage_key` là `blob_id` (hoặc dẫn xuất của nó), **không** phản ánh tên
>   file hay cấu trúc thư mục nghiệp vụ.
> - Backend là **người đọc duy nhất**; người dùng không bao giờ nhận URL Drive
>   trực tiếp, chỉ nhận URL có chữ ký do backend cấp, hết hạn ngắn.
> - Tenant vẫn **sở hữu dung lượng, vẫn thu hồi quyền được bất cứ lúc nào** — đó
>   là điểm bán hàng của BYO storage, và nó không đòi hỏi Drive phải đọc được.
> - Muốn có cây đọc-được cho người thì đó là **export tuỳ chọn** (§11.3), không
>   phải là kho.
>
> Đây là cách duy nhất giữ được mô hình quyền — vốn chính là đóng góp của luận văn.

`ref_count` bị bỏ khỏi `blob_objects`: xem §15.5.

### 13.5 Cây vật lý materialized

> **▲ CHỐT (điểm 2).** Dự án đã ăn đúng quả này một lần với CSV↔DB (Postgres chỉ
> là mirror của CSV, và có bốn cách làm sync im lặng thất bại). §12.5 bản gốc tái
> tạo cùng cấu trúc lỗi ở chiều ngược lại.
>
> Nếu giữ cây materialized thì phải tuyên bố ngay trong code và tài liệu:
> **dẫn xuất, dựng lại được bằng một lệnh, không ai ghi tay, không bao giờ là
> nguồn sự thật, không bao giờ được đọc để trả lời câu hỏi về quyền.**
>
> Và câu hỏi phải trả lời trước khi viết dòng nào: **ai thực sự đọc nó?** Nếu chỉ
> là để người vận hành `ls` cho dễ, thì đổi lấy một lệnh CLI dump cây từ DB —
> rẻ hơn và không bao giờ lệch. **Không có consumer thật thì bỏ hẳn.**

Nếu vẫn giữ:

```
/data/tenants/T1/workspaces/W2/projects/P1/
├── .project-manifest.json
├── Documents/
└── Datasets/
```

Entry là symlink/hardlink/manifest reference/cached materialization. Khi move,
cây được dựng lại; blob không copy; DB cập nhật root; checksum xác minh lại.

### 13.6 Move cùng filesystem

Atomic rename: `rename(old_project_root, new_project_root)`.

```
Khoá project → tạo thư mục cha mới → rename root → cập nhật DB → verify → xong
```

### 13.7 Move khác volume / storage node (chỉ ca xuyên tenant)

```
Copy new tree → verify checksum → verify file count → cập nhật active pointer
→ old location = ARCHIVED_PENDING_DELETE → grace period → xoá sau
```

**Không xoá location cũ trước khi location mới được xác minh.**

### 13.8 Rollback

Copy thất bại: old location vẫn active, new location bị quarantine, DB không đổi
binding cuối. Storage xong nhưng DB lỗi: move job tiếp tục hoặc rollback, project
vẫn khoá, **không cho truy cập trạng thái nửa cũ nửa mới**.

---

## 14. Registry và Dataset Version

Dataset version tiếp tục pin:

```
tenant_registry_version_id
registry_snapshot_hash
class_mapping_hash
sample_manifest_hash
```

Registry version: append-only; có `content_hash`; snapshot ghi một lần; thiếu
version hoặc lệch hash là **fatal**; **không fallback** sang registry khác. Xem
[`REGISTRY_ARCHITECTURE.md`](REGISTRY_ARCHITECTURE.md).

Project move **không** làm đổi registry pin.

Share và fork phải **mang theo snapshot gốc**. Project nhận không được dùng
registry hiện tại của mình để diễn giải lại dataset cũ.

**UX** — người dùng không cần thấy raw hash, chỉ thấy `Compatible` /
`Needs mapping` / `Not compatible`. Mặc định *"Giữ cấu hình gốc của dữ liệu —
Khuyên dùng"*; tuỳ chọn nâng cao *"Chuyển sang cấu hình hiện tại của Project
đích"*. Cần mapping thì mở wizard hiển thị: profile nguồn, profile đích, class
không ánh xạ được, dữ liệu có thể bị loại, và version mới sẽ được tạo.

---

## 15. Share và Fork

### 15.1 Share

Cho người/project khác truy cập **cùng một** tài nguyên; không tạo repository
mới. Có thể: theo dõi branch hiện tại, pin một release, chỉ xem, bình luận,
chỉnh sửa, tạo branch đóng góp, gửi merge request.

### 15.2 Fork

Tạo repository **độc lập**:

```
Repository B
forked_from_repository_id = Repository A
forked_from_commit_id     = A:C120
```

Fork có owner, project, thành viên, role, branch, commit, release riêng; sync
upstream được; gửi merge request ngược được.

> Share = dùng chung repository. Fork = repository mới có lineage riêng.

### 15.3 Quyền fork

Nguồn cần `fork.create`; đích cần `repository.create` hoặc
`project.import_resource`. Ngoài ra: source policy cho phép derivative; workspace
đích cho phép fork; consent/license không cấm; quota đích đủ; approver đã duyệt
nếu dữ liệu nhạy cảm.

### 15.4 UX

```
Nhấn Fork → Chọn version/commit/release → Chọn Workspace đích → Chọn Project đích
→ Chọn branch ban đầu → Xem quyền và dung lượng → Xác nhận
```

Hệ thống tự xử lý lineage, blob reference, registry snapshot, commit nguồn,
permission, audit.

### 15.5 Storage của fork — và xung đột với xoá theo consent

> **▲ CHỐT (điểm 7).** Bản gốc để hai điều loại trừ nhau đứng cạnh nhau: §14.5
> nói fork trong cùng tenant dùng **copy-on-write, chia sẻ blob**; §15.4 nói xoá
> theo consent phải **xoá vật lý**. Blob có nhiều tham chiếu thì xoá là phá fork
> của người khác, không xoá là không tuân thủ. Không thể để lửng lơ.
>
> **Chốt hai luật:**
>
> 1. **Dữ liệu có consent ràng buộc không được dedup xuyên project/fork.** Blob
>    mang `consent_bound = true` thì fork **copy thật**, mỗi project giữ bản
>    riêng, xoá được độc lập. Tốn dung lượng — và đó là cái giá đúng để trả.
>    Dữ liệu không ràng buộc consent (tài liệu, cấu hình, template) vẫn
>    copy-on-write bình thường.
> 2. **Bỏ `ref_count`, dùng GC mark-and-sweep.** Đếm tham chiếu sẽ đua khi
>    commit/fork/delete chạy đồng thời, và một lần đếm sai là mất dữ liệu vĩnh
>    viễn hoặc rác vĩnh viễn. Quét định kỳ từ `artifact_revisions` để đánh dấu
>    blob còn sống, xoá phần còn lại sau grace period.

Fork **khác tenant**: copy blob sang storage tenant đích, tính checksum, áp quota
và retention của tenant đích. **Không dùng chung storage object xuyên tenant** —
đây cũng là lý do move xuyên tenant cần máy trạng thái đầy đủ (§12.2).

### 15.6 Sync upstream

Ba chế độ: `Manual sync` / `Notify when updates are available` / `Detached`.

```
Upstream có 5 thay đổi mới      [Preview] [Sync] [Ignore]
```

### 15.7 Conflict

| Loại file | Xử lý |
|---|---|
| TXT / Markdown | Three-way merge |
| JSON có schema | Merge theo field |
| CSV có khoá ổn định | Merge theo record |
| DOCX / PDF / NPZ / video / ảnh | **Không** auto-merge nội dung |

Binary conflict: Keep mine / Use upstream / Keep both / Upload resolved version /
Abort.

Main branch được bảo vệ; commit từ share hoặc fork đi qua branch + merge request.

---

## 16. Thu hồi quyền, archive, xoá

### 16.1 Trạng thái

```
PENDING → ACTIVE → SUSPENDED → REVOKED
                 → EXPIRED
```

### 16.2 Thu hồi thường

Chặn xem; chặn comment/edit; chặn download/export; **huỷ signed URL đang có**;
giữ audit; **không** tự xoá artifact đã tạo hợp lệ trước đó.

### 16.3 Tạm đình chỉ

Dùng khi: project đang move, nghi ngờ sự cố bảo mật, chờ phê duyệt, policy vừa
đổi. `ACTIVE → SUSPENDED`, sau điều tra về `ACTIVE` hoặc sang `REVOKED`.

### 16.4 Thu hồi do consent hoặc pháp lý

Khác hẳn revoke thường: dừng job đang dùng dữ liệu; chặn export; đánh dấu dataset
bị ảnh hưởng; **rà soát fork và derivative** (§15.5 làm việc này khả thi); xử lý
cache và managed export; xoá vật lý sau legal-hold check; giữ audit metadata tối
thiểu.

### 16.5 Ai được thu hồi

| Phạm vi | Người có quyền |
|---|---|
| File/folder share | Resource Manager hoặc Owner |
| Project member | Project Admin |
| Workspace member | Workspace Admin |
| Cross-workspace share | Admin hai workspace hoặc Tenant Admin |
| Emergency revoke | Tenant Admin |
| Legal deletion | Tenant Admin theo policy/compliance |

Mọi thu hồi lưu: `revoked_by`, `revoked_at`, `reason`, `scope`,
`before_permissions`, `after_permissions`.

---

## 17. Audit, Access Log và bộ xem log của tenant

### 17.1 Content history

```
FILE_CREATED   FILE_EDITED    FILE_REPLACED   FILE_RENAMED   FILE_MOVED
FILE_DELETED   FILE_RESTORED  REVISION_CREATED
BRANCH_CREATED COMMIT_CREATED MERGE_COMPLETED
COMMENT_CREATED  COMMENT_RESOLVED
```

### 17.2 Administrative audit

```
MEMBER_INVITED  MEMBER_ADDED   ROLE_CHANGED
ACCESS_GRANTED  ACCESS_UPDATED ACCESS_REVOKED
SHARE_LINK_CREATED  SHARE_LINK_REVOKED
PROJECT_MOVED   PROJECT_ARCHIVED  PROJECT_RESTORED
FORK_CREATED    FORK_SYNCED
EXPORT_APPROVED IMPORT_APPROVED
```

### 17.3 Access log

```
WORKSPACE_OPENED  PROJECT_OPENED  FOLDER_VIEWED  FILE_VIEWED
FILE_DOWNLOADED   RAW_MEDIA_ACCESSED  DATASET_USED
REPOSITORY_EXPORTED  SHARE_LINK_OPENED
```

Không log từng video chunk — một access event cho một phiên/request nghiệp vụ.

### 17.4 Trường log

```
actor_user_id / actor_tenant_member_id / actor_role
acting_tenant_id / acting_workspace_id / acting_project_id
resource_type / resource_id / action
permission_source / grant_id / role_at_time
before_state / after_state / reason
request_id / ip_address / user_agent / created_at
```

Phải ghi **cả user lẫn scope đại diện**, vì cùng một người mang vai trò khác nhau
ở nhiều workspace/project.

> **▲ CHỐT (điểm 9).** Audit bất biến, cưỡng chế ở tầng DB:
>
> ```sql
> REVOKE UPDATE, DELETE ON audit_events, access_events FROM <runtime_role>;
> ```
>
> Sửa một quyền tạo event **mới**, không viết đè. Tenant Admin không phải ngoại
> lệ. Retention do nền tảng đặt, không phải tenant.

### 17.5 Bộ xem log của tenant

Hiện trạng phải sửa: security log đang là **một list Redis toàn cục** `sec:log`,
cắt cứng 500 dòng (`backend/app/activity.py`) — không có tenant, không giữ lâu,
tràn là mất. Bảng `audit_log` có trong `backend/migrations/001_create_production_schema.sql`
nhưng runtime không dùng.

Log mà tenant xem được là **`audit_events` + `access_events` ở Postgres**, không
phải Loki — đúng theo `docs/06-operations/OBSERVABILITY_PLAN.md`: Loki giữ chi tiết kỹ thuật,
hết hạn 7 ngày, dành cho vận hành; sự kiện nghiệp vụ vào Postgres và giữ lâu.
Khách hàng không muốn stack trace, họ muốn biết **ai làm gì, lúc nào, trên cái gì**.

Ba tab cho Tenant Admin / Tenant Auditor:

| tab | nội dung |
|---|---|
| Hoạt động | tạo/sửa/xoá tài nguyên, thu mẫu, purge, sửa registry (kèm version trước/sau) |
| Bảo mật | đăng nhập thành/bại, đổi mật khẩu, mời/gỡ thành viên, đổi role, kết nối/ngắt Drive, thu hồi phiên |
| Hệ thống | job train, đồng bộ, export, và **lỗi đã lọc** — chỉ lỗi thuộc dữ liệu của họ, đã bỏ chi tiết nội bộ |

Lọc theo người/hành động/khoảng thời gian, và **xuất CSV**.

Ba ràng buộc:

1. **Không** cho tenant query Loki thô — log backend trộn lẫn mọi tenant. Nếu sau
   này thật sự cần, dùng multi-tenancy gốc của Loki qua `X-Scope-OrgID`.
2. **Tenant không xoá được audit của chính mình** (§17.4).
3. Sửa cardinality trước: `logging/promtail-config.yaml` đang đặt `request_id` /
   `task_id` làm **label** — lỗi thật. `tenant_id` phải vào **structured
   metadata**, tuyệt đối không thành label, nếu không mỗi tenant mới là một nhân
   số stream.

---

## 18. Cấu hình bảo mật do tenant tự quản

Bản gốc có bảng `tenant_settings` trong §17 nhưng không định nghĩa nội dung. Đây
là phần bù.

> **LUẬT VÀNG.** Tenant **chỉ được siết chặt hơn** sàn của nền tảng, **không bao
> giờ nới lỏng**. Mọi giá trị resolve theo:
>
> ```
> hiệu_lực = nghiêm_ngặt_hơn(sàn_nền_tảng, lựa_chọn_tenant)
> ```
>
> Không có ngoại lệ, kể cả khi khách yêu cầu.

**Tenant được chỉnh:** độ dài mật khẩu tối thiểu và chu kỳ đổi; thời hạn access/
refresh token và số phiên đồng thời; domain email được phép mời (ví dụ chỉ
`@ctu.edu.vn`); IP allowlist của tenant; bắt buộc MFA theo vai trò; ai được
export / xem PII người ký / purge vĩnh viễn; retention của trash; kết nối Drive;
địa chỉ nhận cảnh báo.

**Tenant KHÔNG được chỉnh:** ngưỡng rate limit và khoá brute-force (chỉ siết,
không nới); khoá và thuật toán JWT; khoá ký SOT; chặn IP toàn hệ thống; giới hạn
upload; quota GPU/dung lượng; feature contract của pipeline.

**Vướng mắc trong code hiện tại.** Toàn bộ tham số này đang là env var toàn cục
trong `backend/app/config.py`: `min_password_length`, `access_token_expire_minutes`,
`refresh_token_expire_minutes`, cookie settings, cùng các bậc trong
`backend/app/rate_limit.py`. Cần bảng `tenant_settings` và **một hàm resolve duy
nhất** áp luật vàng — không để mỗi call site tự đọc `settings`, vì chỉ cần một
chỗ đọc thẳng là thủng.

Thêm nữa: key `ratelimit:` và cơ chế chặn IP trong `activity.py` đều keyed toàn
cục. Hiện chặn một IP ở tenant A sẽ chặn luôn tenant B. Phải thêm `tenant_id` vào key.

---

## 19. Bảng PostgreSQL

```
-- danh tính
users                    user_identities          tenant_members

-- tổ chức
workspaces               workspace_members
projects                 project_members          project_workspace_history

-- nội dung
repositories             repository_branches      repository_commits
repository_releases
artifact_nodes           artifacts                artifact_revisions
blob_objects

-- quyền
resource_grants          resource_invitations     share_links      comments

-- vận hành
project_move_requests    project_move_approvals   project_move_jobs
project_storage_locations
import_jobs              export_jobs

-- phái sinh
repository_forks         upstream_links           merge_requests   merge_conflicts

-- dữ liệu
registry_versions        dataset_versions

-- quan sát
audit_events             access_events            notifications

-- cấu hình
system_settings          tenant_settings          tenant_storage
```

`tenant_storage` (thêm mới, cho BYO Drive):

```
tenant_storage
- tenant_id (PK) / provider / root_object_prefix
- refresh_token_enc          -- mã hoá bằng khoá nền tảng; KHÔNG bao giờ log, KHÔNG trả ra API
- scopes / account_email     -- account_email chỉ để hiển thị "đang nối tới ..."
- connected_by / connected_at / last_verified_at / status
```

`resource_grants`:

```
resource_grants
- grant_id / tenant_id / workspace_id / project_id
- resource_type / resource_id
- principal_type / principal_id
- resource_role / permission_overrides
- permission_source / inherited_from_grant_id
- valid_from / expires_at / status
- granted_by / revoked_by / revocation_reason / created_at / revoked_at
```

> **Ghi chú.** `permission_overrides` **không** được dùng để mã hoá explicit deny
> trong giai đoạn đầu (§7). Restriction đến từ policy và data classification.

---

## 20. RLS — lớp fail-closed cuối cùng

Runtime database role: **không** superuser, **không** `BYPASSRLS`, **không** phải
table owner, **không** dùng chung với migration role.

### 20.1 Context

```sql
SET LOCAL app.user_id      = '...';
SET LOCAL app.tenant_id    = '...';
SET LOCAL app.workspace_id = '...';
SET LOCAL app.project_id   = '...';
```

Các giá trị lấy từ **session đã xác thực**, không lấy từ request body.

> **▲ CHỐT (điểm 3) — lỗ rò nguy hiểm nhất trong cả bản thiết kế.**
>
> `backend/app/storage/postgres_connection.py` hiện chỉ có `get_pooled_conn()` /
> `put_pooled_conn()` trần, **không có transaction wrapper nào**. Hai cách hỏng:
>
> - `SET LOCAL` chỉ sống trong transaction. Query chạy autocommit sẽ có context
>   **rỗng** → fail-closed nghĩa là hỏng toàn hệ thống (dễ phát hiện).
> - Nếu ai đó viết `SET` thay vì `SET LOCAL`, context **dính lại trên
>   connection** và rò sang tenant kế tiếp mượn đúng connection đó (**im lặng,
>   nguy hiểm hơn nhiều**).
>
> **Bắt buộc:**
> 1. Một context manager duy nhất: mở transaction → `SET LOCAL` đủ bốn biến →
>    yield → commit/rollback → `putconn`.
> 2. **Cấm** gọi `get_pooled_conn()` trực tiếp ở tầng nghiệp vụ; kiểm bằng test
>    hoặc lint.
> 3. **Cấm** `SET` không có `LOCAL`; grep trong CI.
> 4. Nếu về sau thêm PgBouncer, phải chạy **session mode** hoặc bảo đảm mọi thứ
>    nằm trong transaction.

### 20.2 Điều kiện

```
Tenant Admin trong tenant
OR Workspace Admin/Manager trong workspace
OR Project membership
OR Resource grant
OR Active share
OR Valid share link
```

> **▲ CHỐT (điểm 4).** Policy trên `projects` phải hỏi `workspace_members` /
> `tenant_members`; các bảng đó cũng bật RLS → **đệ quy và chậm**.
>
> Giải: viết một hàm **`SECURITY DEFINER`** (ví dụ
> `app.effective_project_ids(uuid)`) trả về tập id mà user truy cập được, đã tính
> sẵn; policy chỉ so với tập đó. Bảng membership có policy permissive riêng để
> hàm đọc được. Hàm phải `STABLE`, `search_path` cố định, và **không** nhận tham
> số do client kiểm soát ngoài context đã set.

Application RBAC vẫn chạy **trước** để trả lỗi rõ ràng; RLS chỉ để chặn truy vấn
thiếu điều kiện. Các bảng share và membership cần **composite FK** để ngăn cấp
quyền chéo tenant hoặc sai workspace.

---

## 21. UX

```
Share "Protocol.docx"

People with access
- Nguyễn A — Editor
- Trần B — Commenter

General access
- Restricted

[Add people, group or user code]
Role: Viewer | Commenter | Editor | Manager
Advanced: Allow download · Allow export · Expiry date
```

```
Move Project X          From: Workspace A  →  To: Workspace B

Impact:
- 8 members retain Project access
- 3 members receive PROJECT_ONLY access
- 2 shares need reapproval
- 1 public link will be suspended
- Workspace B disables external export

[Review permissions]  [Confirm move]
```

```
Fork Repository X       Source: Release v3
Destination: Workspace B / Project Y

Options:
- Track upstream updates
- Copy current permissions: No
- Include comments: No

[Create Fork]
```

Registry: người dùng thường chỉ thấy `Compatible` / `Needs mapping` /
`Not compatible`. Hash, snapshot ID, registry version nằm trong mục kỹ thuật nâng cao.

---

## 22. Phạm vi: hiện thực vs thiết kế

Bản thiết kế này là roadmap nhiều tháng. Mốc luận văn: **13/08/2026 nộp sách,
18–19/08/2026 bảo vệ**. Không dựng xong toàn bộ, và ép sẽ ra một hệ nửa vời không
demo được. Chia đôi dứt khoát:

### 22.1 HIỆN THỰC — lõi cô lập hai mặt phẳng

| # | hạng mục | vì sao bắt buộc |
|---|---|---|
| 1 | Context manager transaction + `SET LOCAL` (§20.1) | mọi thứ khác đứng trên nó; làm sau là phải sửa lại toàn bộ |
| 2 | `users` / `user_identities` / `tenant_members` (§4) | định danh bất biến là tiền đề của mọi grant |
| 3 | `workspaces` / `workspace_members` / `projects` / `project_members` (§5) | gồm cả `PROJECT_ONLY` |
| 4 | `resource_grants` + quyền hiệu lực (§7) + chống leo thang (§6.6) | phần lõi |
| 5 | RLS fail-closed + hàm `SECURITY DEFINER` (§20) | đóng góp có thể chứng minh được bằng test |
| 6 | `audit_events` / `access_events` + bộ xem của tenant (§17) | thay `sec:log` Redis |
| 7 | `tenant_settings` + luật vàng (§18) | |
| 8 | `tenant_storage` + luồng gắn Drive (§13.4) | |
| 9 | Màn hình Manage Access (§9) | thứ demo được, nhìn thấy được |

### 22.2 CHỈ THIẾT KẾ — ghi rõ trong sách là *đã thiết kế, chưa hiện thực*

Repository / branch / commit / release; fork + sync upstream + conflict
resolution; máy trạng thái move (§12.2 ca xuyên tenant); import/export package;
comment có anchor; group principal.

Đây hoàn toàn chính đáng trong luận văn. §23 với hơn 20 quyết định chốt **chính
là** phần đóng góp thiết kế đó — nó đứng vững kể cả khi code chưa chạm tới.

### 22.3 Thứ tự làm

```
1. Context manager + transaction  ─┐
2. Định danh + membership          ├─ bắt buộc trước khi có tenant thứ hai
3. resource_grants + RLS          ─┘
4. audit_events + bộ xem log
5. tenant_settings + luật vàng
6. get_gdrive_client(tenant_id) + OAuth   (~20 call site, cache folder per-instance)
7. Manage Access UI
8. Sửa promtail cardinality
```

Bước 1–3 là bắt buộc **trước khi** có tenant thứ hai chạm vào hệ thống. Các bước
còn lại làm song song được.

---

## 23. Các quyết định chốt

```
 1. Tenant ≡ công ty; Workspace ≡ phòng ban.
 2. Tenant Admin nhìn toàn bộ tenant, không bị giới hạn bởi Workspace,
    Project hoặc Resource grant — NHƯNG không xoá/sửa được audit.   ▲
 3. Workspace Admin và Manager nhìn toàn bộ Project trong Workspace mình quản.
 4. Workspace Editor/Commenter/Viewer chỉ thấy Project hoặc tài nguyên được cấp.
 5. Cùng Workspace không tự động có quyền truy cập Project khác.
 6. Private resource có thể thêm User, Group hoặc Project khác.
 7. Chia sẻ dùng Viewer, Commenter, Editor, Manager, Owner.
 8. Quyền lưu bằng user_id / tenant_member_id bất biến, không lưu email.
 9. access_scope có ĐÚNG hai giá trị; Admin/Manager bị ép FULL_WORKSPACE. ▲
10. Không ai cấp được vai trò cao hơn vai trò của chính mình.          ▲
11. Personal Workspace: một cho mỗi cặp (user, tenant).                ▲
12. Project move giữ nguyên project_id và cập nhật workspace_id.
13. Thành viên cũ giữ quyền Project qua PROJECT_ONLY membership.
14. Share, link và policy phải được đánh giá lại sau Project move.
15. Archive binding và storage location cũ, không archive Project đang chạy.
16. PostgreSQL quản logical path, ownership và permission.
17. Drive của tenant là kho blob MỜ; backend là người đọc duy nhất.     ▲
18. Cây vật lý là dẫn xuất, dựng lại được, không bao giờ là nguồn sự thật. ▲
19. Move nội bộ tenant KHÔNG đụng blob; chỉ move xuyên tenant mới cần
    copy–verify–switch–archive.                                        ▲
20. Dữ liệu ràng buộc consent không dedup xuyên fork; GC mark-and-sweep
    thay cho ref_count.                                                ▲
21. Import/export hỗ trợ nhiều định dạng và có permission riêng
    (view / download / export.create / export.approve tách rời).
22. Dataset Version luôn pin Registry Version và Snapshot; share/fork
    mang theo snapshot gốc.
23. Share = dùng chung Repository. Fork = Repository mới có lineage riêng.
24. Tenant chỉ được siết chặt hơn sàn nền tảng, không bao giờ nới lỏng. ▲
25. RLS là lớp fail-closed; context qua SET LOCAL trong transaction,
    cấm truy cập connection pool trần.                                 ▲
26. Mọi truy cập, bình luận, sửa đổi, cấp quyền, thu hồi, move, fork,
    import và export đều phải được lưu vết.

▲ = chốt bổ sung hoặc khác bản gốc (xem §1).
```
