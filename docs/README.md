# Tài liệu kỹ thuật CTU.SignBridge

Thư mục này chỉ chứa **tài liệu kỹ thuật** của hệ thống. Luận văn, bài báo và báo cáo nghiên cứu không nằm trong repo; ai cần thì giữ bản riêng ở `Extra_docs/` trên máy mình.

## Bắt đầu từ đâu

| Bạn cần | Đọc |
|---|---|
| Dựng web trên một máy mới | [06-operations/TRIEN_KHAI_TU_DAU.md](06-operations/TRIEN_KHAI_TU_DAU.md) |
| Cập nhật máy chạy web, làm việc với nhánh `main`, xử lý xung đột | [06-operations/CHUYEN_SANG_MAIN.md](06-operations/CHUYEN_SANG_MAIN.md) |
| Bắt đầu viết code (cài môi trường, chạy test, cấu trúc mã) | [HUONG_DAN_DEV.html](HUONG_DAN_DEV.html), mở bằng trình duyệt |
| Hiểu hệ thống chạy thế nào | [01-architecture/CONCEPTS.md](01-architecture/CONCEPTS.md), rồi [01-architecture/MULTITENANT_ARCHITECTURE.md](01-architecture/MULTITENANT_ARCHITECTURE.md) |
| Biết lỗi nào đang tồn tại | [10-issues/KNOWN_ISSUES.md](10-issues/KNOWN_ISSUES.md) |

## Các thư mục

| Thư mục | Nội dung |
|---|---|
| `01-architecture/` | Kiến trúc: tổ chức (tenant), Community, danh mục từ vựng, cô lập dữ liệu, SSO, vòng đời hạ tầng |
| `02-data/` | Dữ liệu: lược đồ CSDL, lưu trữ Drive, vòng đời phương ngữ, chủ sở hữu mẫu. `db/` chứa PDM, ERD và bộ sinh tài liệu từ CSDL |
| `03-security/` | Bảo mật: phân quyền, phiên đăng nhập, 2FA, quên mật khẩu, nhật ký kiểm toán |
| `04-legal/` | Văn bản pháp lý và đồng thuận. `published/` là các văn bản đã công bố, không được sửa |
| `05-frontend/` | Giao diện: hệ thiết kế, đa ngôn ngữ, khả năng tiếp cận, trang quản trị |
| `06-operations/` | Vận hành: triển khai, cập nhật, sao lưu, chuyển máy, CI/CD, giám sát, thông báo |
| `07-business/` | Gói dịch vụ, hạn mức dung lượng, vòng đời đăng ký |
| `08-testing/` | Cách chạy test và chuẩn viết test |
| `09-specs/` | Đặc tả yêu cầu (SRS) và use case |
| `10-issues/` | Lỗi đã biết, sự cố, nợ kỹ thuật |
| `11-worklog/` | **Lịch sử:** nhật ký các đợt làm việc và bản ghi các lần triển khai cũ. Chỉ đọc khi cần tra vì sao một quyết định được đưa ra |

[TENANT_ISOLATION_AND_AUTHZ.md](TENANT_ISOLATION_AND_AUTHZ.md) nằm ở gốc vì mã nguồn trỏ thẳng tới đường dẫn này. Nội dung thuộc nhóm bảo mật: tổng quan phân quyền và cách ly tổ chức.

## Vận hành: tra nhanh

| Việc | Tài liệu |
|---|---|
| Triển khai máy mới, máy trống hoặc chuyển máy | [TRIEN_KHAI_TU_DAU.md](06-operations/TRIEN_KHAI_TU_DAU.md) |
| Quy trình nhánh, cập nhật web, xử lý xung đột | [CHUYEN_SANG_MAIN.md](06-operations/CHUYEN_SANG_MAIN.md) |
| GPU, migration, dung lượng đĩa Docker | [DEPLOY_SECOND_MACHINE.md](06-operations/DEPLOY_SECOND_MACHINE.md) |
| Sao lưu và khôi phục | [BACKUP_RESTORE.md](06-operations/BACKUP_RESTORE.md) |
| Gói chuyển server, chi tiết kỹ thuật | [HOST_TRANSFER.md](06-operations/HOST_TRANSFER.md) |
| CI/CD trên GitHub | [CI_CD.md](06-operations/CI_CD.md) |
| Log, chỉ số, cảnh báo | [OBSERVABILITY_PLAN.md](06-operations/OBSERVABILITY_PLAN.md) |
| Thư thông báo, kênh hỗ trợ | [NOTIFICATIONS_AND_SUPPORT.md](06-operations/NOTIFICATIONS_AND_SUPPORT.md) |

## Quy ước

- Viết tài liệu mới vào **đúng thư mục chủ đề**, không đặt tệp lẻ ở gốc `docs/`.
- Bản ghi của một đợt làm việc hay một lần triển khai, tức tài liệu có ngày trong tên, đặt vào `11-worklog/`.
- Đổi tên hoặc dời một tệp thì tìm và sửa các chỗ đang trỏ tới nó: `git grep -n "<tên tệp>"`.
