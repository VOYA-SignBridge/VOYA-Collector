# Kiến Trúc Pháp Lý và Tuân Thủ (Legal & Compliance Architecture)

Đối với SignBridge - một nền tảng Enterprise AI SaaS xử lý dữ liệu sinh trắc (nhận diện cử chỉ tay), việc quản lý tài liệu pháp lý (Chính sách bảo mật, Điều khoản dịch vụ, Thoả thuận chia sẻ dữ liệu) không thể chỉ lưu trữ đơn giản dưới dạng một chuỗi văn bản. Nó cần có vòng đời, lịch sử thay đổi (versioning) và quy trình phê duyệt (approval workflow).

## 1. Hạn chế của thiết kế truyền thống
Cách thiết kế phổ biến nhưng sai lầm ở các ứng dụng vừa và nhỏ:
```text
LEGAL_DOCUMENT
- id
- title
- content
- status
- updated_at
```
Cách tiếp cận này ghi đè (overwrite) lên tài liệu cũ. Khi có thay đổi, ta mất đi nội dung mà user đã đồng ý trong quá khứ, dẫn tới vi phạm quy định kiểm toán bảo mật (như GDPR).

## 2. Thiết kế Cơ sở Dữ liệu Enterprise (Document Revisioning)
Hệ thống Legal của SignBridge tách bạch trách nhiệm thành nhiều bảng:

```text
LEGAL_DOCUMENTS (Chỉ lưu Metadata)
        │
        ▼
LEGAL_DOCUMENT_VERSIONS (Lưu phiên bản nội dung cụ thể không thể sửa đổi)
        │
        ├─────────────────────────────┐
        ▼                             ▼
LEGAL_APPROVALS (Quy trình duyệt)  LEGAL_ATTACHMENTS (File PDF, DOCX đính kèm)
        │
        ▼
LEGAL_COMMENTS (Trao đổi sửa đổi)
        │
        ▼
LEGAL_ACCEPTANCES (Lưu dấu vết User đồng ý với Version cụ thể)
```

1. **`LEGAL_DOCUMENTS`**: Lưu định danh cốt lõi (Ví dụ: `code = 'privacy-policy'`, `type = 'POLICY'`, `title = 'Privacy Policy'`).
2. **`LEGAL_DOCUMENT_VERSIONS`**: Lưu nội dung (Content) theo phiên bản (`version = 'v1.0'`, `status = 'DRAFT' | 'REVIEW' | 'PUBLISHED'`). Mỗi lần sửa đổi sẽ sinh ra Version mới, không bao giờ ghi đè Version cũ.
3. **`LEGAL_APPROVALS` & `LEGAL_COMMENTS`**: Hệ thống cho phép các Reviewer (Ví dụ: Legal Team) phê duyệt và để lại comment trực tiếp trên từng version trước khi Public.
4. **`LEGAL_ACCEPTANCES`**: Ghi nhận bằng chứng người dùng đã bấm "Đồng ý" (Lưu `user_id`, `version_id`, `accepted_at`, `ip_address`).

## 3. Mở rộng tương lai: Cấu trúc Document - Section - Paragraph
Đối với các tài liệu đồ sộ của Enterprise, thay vì lưu toàn bộ một cục văn bản khổng lồ, tài liệu sẽ được xé nhỏ theo dạng cây:

```text
Document (Privacy Policy)
  ↓
Section (Section 1: Data Collection)
  ↓
Paragraph (Đoạn nội dung)
```
Tương đương với database:
```text
LEGAL_DOCUMENT -> LEGAL_SECTION -> LEGAL_SECTION_VERSION
```

**Lợi ích vượt trội của kiến trúc này:**
- **Chỉ sửa một phần nhỏ:** Không cần copy/paste lại nguyên cả một tài liệu dài khi chỉ sửa một đoạn văn.
- **Reorder (Đảo thứ tự):** Dễ dàng thay đổi thứ tự các phần (Sections).
- **Đa ngôn ngữ (i18n):** Map từng Section/Paragraph với bản dịch tương ứng.
- **Diff (So sánh thay đổi):** Giúp Reviewer (và User) dễ dàng nhìn thấy highlight những câu chữ nào đã bị thay đổi giữa Version 1.0 và 1.1 mà không cần quét lại toàn bộ tài liệu.
