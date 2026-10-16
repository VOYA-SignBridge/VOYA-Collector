# 10. Thiết kế chi tiết (Detailed Design) — Mục lục

*Phần Thiết kế chi tiết chia theo **tám nghiệp vụ**, mỗi nghiệp vụ một tệp. Lý do
tách: gộp cả tám vào một tệp cho ra một tài liệu không ai đọc hết, và bản gộp
buộc phải nén mỗi chức năng xuống vài dòng — tức mất đúng thứ mà phần này tồn tại
để ghi lại.*

---

## Khung trình bày, giữ nhất quán ở cả tám tệp

Mỗi chức năng trình bày theo cùng một khuôn:

| Mục | Nội dung |
|---|---|
| **Mục đích** | Chức năng này giải bài toán gì, và vì sao nó tồn tại |
| **Điểm cuối API** | Phương thức · đường dẫn · vai trò |
| **Giao diện** | Mỗi màn hình một mục, kèm tuyến, tên tệp và số dòng mã |
| **Thành phần điều khiển** | Bảng `No. · Loại điều khiển · Giá trị mặc định · Ghi chú`, nhãn ghi **nguyên văn** chuỗi trong mã |
| **Dữ liệu sử dụng** | Bảng `No. · Bảng/cấu trúc · Thêm · Sửa · Xoá · Truy vấn` |
| **Tiến trình** | Các bước xử lý theo thứ tự |
| **Luồng luân phiên** | Các đường đi hợp lệ khác |
| **Luồng ngoại lệ** | Tình huống hỏng và hành vi tương ứng, kèm thông báo nguyên văn |
| **Ràng buộc** | Mã quy tắc nghiệp vụ (BR-*) và yêu cầu phi chức năng (NFR-*) áp cho chức năng đó |

**Nguồn dựng bảng thành phần:** đọc trực tiếp mã màn hình trong `frontend/src/`.
Nhãn điều khiển ghi nguyên văn để đối chiếu lại được. Chỗ nào chưa đọc hết mã thì
ghi rõ *(chưa liệt kê đủ)* thay vì suy đoán.

---

## Bộ tệp

| Tệp | Nghiệp vụ | Use case | Điểm cuối | Số chức năng |
|---|---|---|:--:|:--:|
| [10_1_DETAILED_DESIGN_NV1.md](10_1_DETAILED_DESIGN_NV1.md) | Danh tính và quyền truy cập | UC101–UC114 | 34 | 9 |
| [10_2_DETAILED_DESIGN_NV2.md](10_2_DETAILED_DESIGN_NV2.md) | Thu thập và quản lý dữ liệu mẫu | UC201–UC213 | 38 | 7 |
| [10_3_DETAILED_DESIGN_NV3.md](10_3_DETAILED_DESIGN_NV3.md) | Danh mục từ vựng và phương ngữ | UC301–UC310 | 22 | 6 |
| [10_4_DETAILED_DESIGN_NV4.md](10_4_DETAILED_DESIGN_NV4.md) | Huấn luyện, đánh giá và suy luận | UC401–UC409 | 31 | 9 |
| [10_5_DETAILED_DESIGN_NV5.md](10_5_DETAILED_DESIGN_NV5.md) | Tổ chức và đăng ký dịch vụ | UC501–UC508 | 28 | 4 |
| [10_6_DETAILED_DESIGN_NV6.md](10_6_DETAILED_DESIGN_NV6.md) | Quản trị người dùng và chính sách | UC601–UC609 | 34 | 5 |
| [10_7_DETAILED_DESIGN_NV7.md](10_7_DETAILED_DESIGN_NV7.md) | Vận hành hệ thống và nguồn sự thật | UC701–UC706 | 13 | 5 |
| [10_8_DETAILED_DESIGN_NV8.md](10_8_DETAILED_DESIGN_NV8.md) | Hỗ trợ và tích hợp | UC801–UC806 | 22 | 5 |
| | | **75** | **213** | **50** |

---

## Bản đồ màn hình ↔ nghiệp vụ

| Tuyến | Màn hình | Nghiệp vụ |
|---|---|:--:|
| `/login` | `LoginPage` | NV1 |
| `/register` | `RegisterPage` | NV1 |
| `/invitation` | `InvitationPage` | NV1 |
| `/forgot-password` · `/reset-password` | `ForgotPasswordPage` · `ResetPasswordPage` | NV1 |
| `/verify` | `VerifyContactPage` | NV1 |
| `/legal/:kind` | `LegalDocumentPage` | NV1 |
| `/settings/account` | `AccountPage` | NV1 |
| `/settings/security` | `SecuritySettingsPage` + `TwoFactorSection` | NV1 |
| `/settings/consents` | `ConsentsPage` | NV1 |
| `/upload` | `UploadPage` · `CaptureCamera` · `FullscreenCaptureModal` · `UploadVideoForm` | NV2 |
| `/labels` | `LabelsPage` | NV2 · NV3 |
| `/labels/:id` | `LabelDetailPage` | NV2 |
| `/trash` | `TrashPage` | NV2 |
| `/admin/vocabulary` | `AdminVocabularyPage` · `AddDialectModal` | NV3 |
| `/training` | `TrainingPipeline` + 9 thành phần con | NV4 |
| `/realtime` | `RealtimeRuntime` (qua `TrialGate`) | NV4 · NV1 |
| `/settings/organization` | `OrganizationPage` | NV5 |
| `/settings/billing` | `BillingPage` | NV5 |
| `/settings/workspaces` | `WorkspacesPage` | NV5 |
| `/admin/tenants` | `AdminTenantsPage` | NV5 |
| `/console` | `ConsoleLayout` + `ConsoleHomePage` | NV5 |
| `/console/allocations` | `ConsoleAllocationsPage` | NV5 |
| `/console/policies` | `ConsolePoliciesPage` | NV5 · NV6 |
| `/admin/users` | `AdminUsersPage` | NV6 |
| `/admin/activity` | `AdminActivityPage` | NV6 |
| `/admin/legal` | `AdminLegalPage` | NV6 |
| `/admin/sot` | `SotAdminPage` | NV7 |
| `/admin/resources` | `AdminResourcesPage` | NV7 |
| `/settings/support` · `/admin/support` | `SupportPage` · `AdminSupportPage` | NV8 |
| `/notifications` | `NotificationsPage` · `NotificationBell` | NV8 |
| `/settings/integrations` | `IntegrationsPage` | NV8 |

**Về vỏ `/console` (thêm 18/08/2026).** Ba mục còn lại của console —
`/console/members`, `/console/billing`, `/console/integrations` — **không có
trang riêng**: chúng dựng lại đúng `OrganizationPage`, `BillingPage`,
`IntegrationsPage` bên trong `ConsoleLayout`. Gom một chỗ cho quản trị viên tổ
chức mà không nhân đôi màn hình, vì hai bản sao của cùng một màn hình sẽ lệch
nhau ở lần sửa thứ hai.

`ConsoleLayout` là **vỏ điều hướng, không phải hàng rào quyền**. Quyền vẫn do
từng điểm cuối cưỡng chế (`require_tenant_admin`); giấu một mục khỏi thanh bên
không chặn được ai gõ thẳng URL, và đó là lý do phép kiểm nằm ở máy chủ.

---

## Những chỗ đặc tả lệch với cài đặt — ghi lại, không lấp

Phần Thiết kế chi tiết mô tả **hệ thống đang chạy**. Khi nó lệch với đặc tả use
case ở Chương 1, bản SRS ghi cả hai và nói rõ bên nào là mã:

| # | Chênh lệch | Ghi ở đâu |
|---|---|---|
| 1 | **UC210** — Chương 1 gọi là *"Gán lại người ký cho phiên thu"*; điểm cuối và giao diện thực tế là *"Đổi nhãn cho lần quay"* (chuyển phiên thu sang một **lớp** khác, không gán lại người ký) | [NV2 §CN2.5](10_2_DETAILED_DESIGN_NV2.md) — mục cuối |
| 2 | **Chuỗi chưa qua i18n** — nút *"Complete Session ({n} mẫu)"* trong `SessionPanel` còn tiếng Anh, đúng loại lỗi mà công cụ đo độ phủ i18n từng bỏ sót hai lần | [NV2 §CN2.1](10_2_DETAILED_DESIGN_NV2.md) — Giao diện 4 |
| 3 | **`AUTHZ_MODE=shadow`** — Casbin chỉ quan sát; hệ phân quyền cũ hai phạm vi là bên quyết định | [02_USER_CLASSES §2.7](02_USER_CLASSES_AND_CHARACTERISTICS.md) |
| 4 | **Webhook 0 hàng** — cơ chế đã cài đặt nhưng chưa có người dùng thật | [NV8 §CN8.5](10_8_DETAILED_DESIGN_NV8.md) |
| 5 | **Sao lưu tự động chưa từng chạy** (rà soát 08/08/2026) — cơ chế có, lịch có, không có bản sao lưu nào | [NV7 §CN7.4](10_7_DETAILED_DESIGN_NV7.md) |

---

## Chức năng có mô hình dữ liệu nhưng chưa có bề mặt vận hành

Ghi lại để người đọc không tìm nhầm:

| Chức năng | Trạng thái |
|---|---|
| Không gian làm việc (`workspaces`) và dự án (`projects`) | ○ **Có bảng, 0 bản ghi gán vai, không đường dẫn API nào.** Không có gì để thiết kế chi tiết |
| Thu tiền | ○ Không có cổng thanh toán. Hệ thống đo và ghi nhận mức dùng, **không thu** |
| Giao diện cho một phần API quản trị tổ chức | ○ API có, màn hình tương ứng chưa đủ |

---

## Tài liệu liên quan

* Đặc tả đầy đủ 75 use case (khung use case UML: tác nhân, quan hệ, xử lý sự kiện,
  luồng luân phiên, luồng ngoại lệ, kết quả mong đợi):
  `docs/00-thesis/quyen/PHU_LUC_C_DAC_TA_USE_CASE.md` và
  `docs/09-specs/USE_CASE_SPECIFICATION.md`
* Kiến trúc ứng dụng: [08_SOFTWARE_DESIGN_ARCHITECTURE.md](08_SOFTWARE_DESIGN_ARCHITECTURE.md)
* Từ điển dữ liệu đủ 57 bảng: [09_DATA_DESIGN_AND_DICTIONARY.md](09_DATA_DESIGN_AND_DICTIONARY.md)
* Quy tắc nghiệp vụ BR-1…BR-10: [07_BUSINESS_RULES.md](07_BUSINESS_RULES.md)
