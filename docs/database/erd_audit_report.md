# BÁO CÁO ĐỐI CHIẾU ERD (ERD AUDIT REPORT)

**Tài liệu tham chiếu:** 
- `database_dictionary.md` (Thiết kế cũ)
- `SignBridge_Architecture.md` và `Refactore_SignBridge.md` (Nguyên tắc Enterprise SAAS)

## Mục đích
Báo cáo này liệt kê chi tiết khoảng trống (Gaps) giữa thiết kế CSDL hiện tại và tầm nhìn Enterprise SAAS (13 nguyên tắc), từ đó đưa ra hướng dẫn để cập nhật `database_dictionary.md` trong Task 1.10.

---

## 1. Gaps về Cấu trúc Phân cấp (Hierarchy)
- **Hiện tại:** Các bảng chỉ liên kết phẳng (User, Dataset, Labels).
- **Thiếu sót:** 
  - Thiếu bảng `TENANTS` (Chủ sở hữu).
  - Thiếu bảng `WORKSPACES` (Phòng ban/AI Lab).
  - Thiếu bảng `PROJECTS` (Nhóm các Models/Datasets).
- **Giải pháp:** Bổ sung 3 bảng trên. Bảng `PROJECTS` có khóa ngoại `workspace_id`, bảng `WORKSPACES` có khóa ngoại `tenant_id`.

## 2. Gaps về Tư cách Thành viên (Membership)
- **Hiện tại:** Dùng bảng `USERS` và `ROLES` trực tiếp (`users.role_id`).
- **Thiếu sót:** Phá vỡ nguyên tắc Multi-tenancy (một người có thể thuộc nhiều dự án với các role khác nhau).
- **Giải pháp:** 
  - Gỡ bỏ `role_id` khỏi bảng `USERS`.
  - Thêm các bảng: `TENANT_MEMBERS` (user_id, tenant_id, role), `WORKSPACE_MEMBERS` (user_id, workspace_id, role), `PROJECT_MEMBERS` (user_id, project_id, role).
  - (Tùy chọn) Lưu rule vào Casbin (bảng `casbin_rule`) thay vì hardcode role trong bảng.

## 3. Gaps về Quyền sở hữu và Cách ly Dữ liệu (Isolation)
- **Hiện tại:** Bảng `LABELS`, `DATASETS_SAMPLES` không có định danh sở hữu đa tầng.
- **Thiếu sót:** Không thể áp dụng Row Level Security (RLS) hiệu quả.
- **Giải pháp:** Tất cả các bảng dữ liệu (như `MODELS`, `DATASETS`, `SAMPLES`, `CAMERAS`) bắt buộc phải thêm 4 cột:
  - `tenant_id`
  - `workspace_id`
  - `project_id`
  - `owner_id` (người tạo ra)

## 4. Gaps về 7-Layer Logging
- **Hiện tại:** Bảng log rất sơ sài (hoặc chưa có bảng chuyên dụng).
- **Giải pháp:** Đập bỏ/Xây mới hệ thống 7 bảng log:
  1. `AUDIT_LOGS` (Lưu JSONB `old_data`, `new_data`) - Partition theo tháng.
  2. `ACCESS_LOGS` - Partition theo tháng.
  3. `AUTH_LOGS`
  4. `AUTHORIZATION_LOGS` (Dành cho Casbin Enforcer)
  5. `SECURITY_LOGS`
  6. `BUSINESS_EVENTS` (Inference, Upload Model...)
  7. `SYSTEM_LOGS`
  *Tất cả phải có cột `trace_id` và `tenant_id`.*

## 5. Gaps về Legal & Compliance Module
- **Hiện tại:** (Chưa có)
- **Giải pháp:** Bổ sung các bảng:
  - `LEGAL_DOCUMENTS` (Metadata: ID, Code, Type, Title)
  - `LEGAL_DOCUMENT_VERSIONS` (Version, Status, Content Markdown/HTML)
  - `LEGAL_APPROVALS` & `LEGAL_COMMENTS` (Workflow phê duyệt)
  - `LEGAL_ATTACHMENTS` (File đính kèm)
  - `LEGAL_ACCEPTANCES` (Ghi nhận User Accept bản nào)
  - `COOKIE_CONSENTS` (Quản lý thiết lập cookies của người dùng)

## 6. Gaps về Quản lý Tài nguyên & Billing (Resource Management)
- **Hiện tại:** (Chưa có)
- **Giải pháp:** Bổ sung các bảng:
  - `RESOURCE_QUOTAS` (Giới hạn Storage, GPU, API limit... cấp cho Tenant/Workspace)
  - `RESOURCE_USAGES` (Mức sử dụng thực tế hiện tại)
  - `RESOURCE_RESERVATIONS` (Đặt lịch sử dụng tài nguyên cứng như Camera, GPU)
  - Hệ thống Billing: `SUBSCRIPTIONS`, `PLANS`, `INVOICES`, `PAYMENTS`.

---

## KẾT LUẬN
Bảng `database_dictionary.md` cần được thiết kế lại diện rộng. 
Tiếp theo (Task 1.10), chúng ta sẽ ghi đè nội dung `database_dictionary.md` để bổ sung toàn bộ các thực thể trên với cấu trúc bảng (Table Schema) chi tiết (Kiểu dữ liệu, Khóa chính, Khóa ngoại).


---

## KẾT LUẬN CUỐI (Decision Record — cập nhật 2026-07, sau khi chốt ERD v2)

Các gap nêu trên đã được phân xử trong [`erd_v2_unified_design.md`](erd_v2_unified_design.md) (ADR-1 → ADR-8). Trạng thái từng đề xuất:

| Đề xuất trong báo cáo này | Trạng thái | Quyết định |
|---|---|---|
| Thêm `TENANTS` / `TENANT_MEMBERS` | ⏸ **Hoãn có chủ đích** | ADR-1: `WORKSPACE` chính là đơn vị tenant ở MVP; đường nâng cấp để sẵn |
| Gỡ `users.role_id`, chuyển hết sang Membership | 🔶 **Áp dụng một phần** | ADR-2: giữ `role_id` = System Role; quyền workspace/project qua `WORKSPACE_MEMBERS`/`PROJECT_MEMBERS` + Casbin |
| 4 cột isolation trên mọi bảng (`tenant_id, workspace_id, project_id, owner_id`) | 🔶 **Áp dụng một phần** | Bảng cấp cao mang `workspace_id` + `owner_id/created_by`; bảng dòng lớn filter qua JOIN (ADR-8: middleware thay RLS ở MVP) |
| 7-Layer Logging (7 bảng log) | ⏸ **Hoãn** | ADR-6: giữ 3 bảng + chuẩn TraceID trong file log |
| PostgreSQL RLS | ⏸ **Hoãn** | ADR-8: middleware `tenant_context` + repository filter; RLS là chốt chặn phase sau |
| Quota/Usage tách riêng | ✅ **Áp dụng** | ADR-5: bảng `WORKSPACE_QUOTAS` |
| Bổ sung bảng thiếu (`SYSTEM_AUDIT_LOGS`, `USER_SESSIONS`, `CATEGORIES`, `CLASS_CATEGORIES`, `SIGN_FEATURES`, `PROJECT_MEMBERS`) | ✅ **Áp dụng** | Đã vào `database_dictionary.md` (ERD v2 — 37 bảng) |
