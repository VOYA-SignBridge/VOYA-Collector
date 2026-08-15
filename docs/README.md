# Tài liệu CTU-SignBridge

Sắp xếp lại 14/08/2026. Mỗi thư mục trả lời **một loại câu hỏi**; số thứ tự chỉ để
giữ trật tự hiển thị, không hàm ý thứ tự đọc. Cấu trúc trùng quy ước của
[`Extra_docs/`](../Extra_docs/README.md) — tài liệu thiết kế đời đầu nằm ở đó, tài liệu
đang có hiệu lực nằm ở đây.

| Thư mục | Trả lời câu hỏi |
|---|---|
| [`00-thesis/`](00-thesis/) | Quyển luận văn và bài báo |
| [`01-architecture/`](01-architecture/) | Hệ thống được tổ chức thế nào |
| [`02-data/`](02-data/) | Dữ liệu có hình dạng gì, lưu ở đâu |
| [`03-security/`](03-security/) | Ai được làm gì, và chứng minh bằng cách nào |
| [`04-legal/`](04-legal/) | Nghĩa vụ pháp lý và sự đồng thuận |
| [`05-frontend/`](05-frontend/) | Giao diện |
| [`06-operations/`](06-operations/) | Triển khai, sao lưu, giám sát |
| [`07-business/`](07-business/) | Gói cước và vòng đời thuê bao |
| [`08-testing/`](08-testing/) | Chạy kiểm thử ra sao |
| [`09-specs/`](09-specs/) | Đặc tả use case |
| [`10-issues/`](10-issues/) | Cái gì đang hỏng, cái gì đã hỏng |
| [`11-worklog/`](11-worklog/) | Đã làm gì, ngày nào, vì sao |
| [`99-archive/`](99-archive/) | Đã hết hiệu lực, giữ để tra cứu |

---

## 00-thesis — luận văn & bài báo

| Tệp | Nội dung |
|---|---|
| [PHANGIOITHIEU_BAN_SACH.md](00-thesis/PHANGIOITHIEU_BAN_SACH.md) | **Bản chép vào Word** — chỉ mục 1–7, không phụ chú |
| [LUANVAN_PHANGIOITHIEU.md](00-thesis/LUANVAN_PHANGIOITHIEU.md) | Bản làm việc: mục 1–7 + phụ chú A–F cho tác giả |
| [LUANVAN_CHUONG2.md](00-thesis/LUANVAN_CHUONG2.md) | Chương 2 — Cơ sở lý thuyết, 11 mục |
| [LUANVAN_TONGHOP.md](00-thesis/LUANVAN_TONGHOP.md) | Hệ thống thật sự là gì, đề cương nói khác ở đâu |
| [PAPER_PIPELINE_RELEASE.md](00-thesis/PAPER_PIPELINE_RELEASE.md) | Bài ISDS 2026 — phạm vi đóng băng, mọi claim phải có artifact |
| [BANG_TRA_TRICH_DAN.md](00-thesis/BANG_TRA_TRICH_DAN.md) | Khoá `\cite{}` → tiêu đề tài liệu, để chèn trích dẫn trong Word |
| [DO_HIEU_QUA_LUU_TRU.md](00-thesis/DO_HIEU_QUA_LUU_TRU.md) | Bằng chứng cho MT6 — 298,4 B/khung; 28,9% kho là bản sao thừa |
| [DOI_CHIEU_QIPEDC.md](00-thesis/DOI_CHIEU_QIPEDC.md) | Danh mục nền tảng ↔ chuẩn quốc gia; 26,8% kho mẫu bị gộp biến thể vùng |
| [SignBridge_Reference/](00-thesis/SignBridge_Reference/) | Thư mục tham chiếu: `.bib`, script Zotero |
| [proposal/](00-thesis/proposal/) | Đề cương và mẫu gốc (`.docx`, `.pdf`) |

> **Quyển luận văn soạn trên Word, không dùng LaTeX.** Trích dẫn chèn bằng plugin Zotero
> (`Ctrl+Alt+C`, style IEEE); danh mục tài liệu do Word tự sinh. Vì vậy tệp
> `SignBridge_Reference.bib` **không điều khiển gì** — nó chỉ là bản sao đọc được của thư
> viện Zotero. Khoá trích dẫn trong đó đổi mỗi lần xuất lại; đừng dựa vào chúng.

## 01-architecture — kiến trúc

| Tệp | Nội dung |
|---|---|
| [CONCEPTS.md](01-architecture/CONCEPTS.md) | Mười cặp khái niệm bị gộp và ranh giới thật giữa chúng |
| [MULTITENANT_ARCHITECTURE.md](01-architecture/MULTITENANT_ARCHITECTURE.md) | Kiến trúc đa thuê bao |
| [TENANT_ISOLATION.md](01-architecture/TENANT_ISOLATION.md) | Cô lập tenant — kiến trúc, luồng nghiệp vụ, vận hành |
| [TENANT_LIFECYCLE_AND_OTP.md](01-architecture/TENANT_LIFECYCLE_AND_OTP.md) | Vòng đời tenant, lời mời, OTP hai kênh |
| [COMMUNITY_DATA_COMMONS.md](01-architecture/COMMUNITY_DATA_COMMONS.md) | Dữ liệu dùng chung cộng đồng |
| [REGISTRY_ARCHITECTURE.md](01-architecture/REGISTRY_ARCHITECTURE.md) | Registry ba mặt phẳng, phiên bản bất biến |
| [INFRA_LIFECYCLE.md](01-architecture/INFRA_LIFECYCLE.md) | Dựng → triển khai → chạy → sao lưu → nâng cấp → gỡ |
| [SSO_OIDC_DESIGN.md](01-architecture/SSO_OIDC_DESIGN.md) | **CHƯA hiện thực** — thiết kế SSO qua OIDC và lý do hoãn |

## 02-data — dữ liệu & lược đồ

| Tệp | Nội dung |
|---|---|
| [SAAS_SCHEMA_DESIGN.md](02-data/SAAS_SCHEMA_DESIGN.md) | Thiết kế lược đồ SaaS |
| [VOCABULARY_SCHEMA_V2.md](02-data/VOCABULARY_SCHEMA_V2.md) | Recognition profile thay cho trường `dialect` cũ |
| [DIALECT_LIFECYCLE.md](02-data/DIALECT_LIFECYCLE.md) | Vòng đời phương ngữ |
| [SAMPLE_OWNERSHIP.md](02-data/SAMPLE_OWNERSHIP.md) | `user_id` (người ký) ≠ `auth_user_id` (tài khoản thu) |
| [DATA_COLLECTION_PROTOCOL.md](02-data/DATA_COLLECTION_PROTOCOL.md) | Giao thức thu cho chiến dịch ISDS 2026 |
| [gdrive_suffix_2_0.md](02-data/gdrive_suffix_2_0.md) | Hậu tố `2.0` trên bản chụp catalog ở Google Drive |
| [db/](02-data/db/) | `gen_erd.py`, `schema_erd.sql`, `voya_erd.drawio` |

## 03-security — xác thực & phân quyền

| Tệp | Nội dung |
|---|---|
| [AUTHORIZATION.md](03-security/AUTHORIZATION.md) | Phân quyền PDM v5 + Casbin, 13 vai |
| [SESSION_LIFECYCLE.md](03-security/SESSION_LIFECYCLE.md) | Ba mức thu hồi phiên |
| [TWO_FACTOR.md](03-security/TWO_FACTOR.md) | TOTP tự viết, kiểm bằng vector RFC |
| [ACCOUNT_RECOVERY.md](03-security/ACCOUNT_RECOVERY.md) | Khôi phục một cửa |
| [AUDIT_TRAIL.md](03-security/AUDIT_TRAIL.md) | Nhật ký kiểm toán hợp nhất Redis + `audit_log` |
| [AUTH_TOKEN_LIFECYCLE.md](03-security/AUTH_TOKEN_LIFECYCLE.md) | **CÒN THIẾU** — bốn lỗ hổng vòng đời token chưa vá |

## 04-legal — pháp lý & đồng thuận

| Tệp | Nội dung |
|---|---|
| [LEGAL_DOCUMENTS.md](04-legal/LEGAL_DOCUMENTS.md) | Kho văn bản pháp lý, trigger bất biến, quy trình công bố |
| [LEGAL_DOCUMENT_FILES.md](04-legal/LEGAL_DOCUMENT_FILES.md) | Đường lưu trữ thứ hai — văn bản là TỆP, không phải markdown |
| [CONSENT_ENFORCEMENT.md](04-legal/CONSENT_ENFORCEMENT.md) | Thang đồng thuận 3 mức, rút là rút |
| [PER_TENANT_LEGAL_DOCS.md](04-legal/PER_TENANT_LEGAL_DOCS.md) | Văn bản riêng theo tenant |
| [published/](04-legal/published/) | Bốn văn bản **đã công bố** (2026-08-08) |

## 05-frontend — giao diện

| Tệp | Nội dung |
|---|---|
| [UI_DESIGN_SYSTEM.md](05-frontend/UI_DESIGN_SYSTEM.md) | Hệ thiết kế — thành công = xanh dương CTU, 0 emoji |
| [ADMIN_CONSOLE_AND_SETTINGS.md](05-frontend/ADMIN_CONSOLE_AND_SETTINGS.md) | Console quản trị, thanh bên 21 mục |
| [I18N.md](05-frontend/I18N.md) | Đa ngữ, codemod, 7 luật bắt chuỗi |
| [ACCESSIBILITY.md](05-frontend/ACCESSIBILITY.md) | Tiếp cận |
| [realtime_runtime_ui.md](05-frontend/realtime_runtime_ui.md) | Chỗ sửa giao diện nhận diện thời gian thực |

## 06-operations — vận hành

| Tệp | Nội dung |
|---|---|
| [DEPLOY_SECOND_MACHINE.md](06-operations/DEPLOY_SECOND_MACHINE.md) | Triển khai máy thứ hai, tự dò GPU |
| [BACKUP_RESTORE.md](06-operations/BACKUP_RESTORE.md) | Hai kho, thứ tự dump-trước-nén-sau, diễn tập `--drill` |
| [OBSERVABILITY_PLAN.md](06-operations/OBSERVABILITY_PLAN.md) | Loki, Prometheus, Grafana; audit ở Postgres |
| [NOTIFICATIONS_AND_SUPPORT.md](06-operations/NOTIFICATIONS_AND_SUPPORT.md) | Thư phiếu hỗ trợ và tồn đọng |
| [DATASET_SYNC_DEPLOY.md](06-operations/DATASET_SYNC_DEPLOY.md) | Đồng bộ dataset dev ↔ deploy |

## 07-business — kinh doanh

| Tệp | Nội dung |
|---|---|
| [BILLING_MODEL_V6.md](07-business/BILLING_MODEL_V6.md) | Mô hình tính cước v6 |
| [SUBSCRIPTION_LIFECYCLE.md](07-business/SUBSCRIPTION_LIFECYCLE.md) | Kỳ hạn, nhắc, ân hạn, khoá mềm — **không** thu tiền |

## 08-testing · 09-specs

| Tệp | Nội dung |
|---|---|
| [TESTING.md](08-testing/TESTING.md) | Hạ tầng kiểm thử; chạy bằng `scripts/run_tests.sh` |
| [USE_CASE_SPECIFICATION.md](09-specs/USE_CASE_SPECIFICATION.md) | 75 use case, 10 tác nhân người + 6 tác nhân hệ thống |

## 10-issues — sự cố & việc còn thiếu

| Tệp | Nội dung |
|---|---|
| [KNOWN_ISSUES.md](10-issues/KNOWN_ISSUES.md) | Danh sách lỗi đã biết |
| [INCIDENT_2026-08-12_schema_code_skew.md](10-issues/INCIDENT_2026-08-12_schema_code_skew.md) | Sự cố lệch lược đồ ↔ mã, 12/08 |
| [HARDCODED_VOCABULARY_AUDIT.md](10-issues/HARDCODED_VOCABULARY_AUDIT.md) | Kiểm kê danh sách gắn sẵn và giá trị bịa |

## 11-worklog — nhật ký theo mốc

Khảo sát và báo cáo tiến độ đã đóng mốc thời gian. Đọc để biết **vì sao** một quyết định
được đưa ra, không phải để biết hệ thống **hiện** ra sao.

| Tệp | Ngày |
|---|---|
| [MERGE_WORK_LOG.md](11-worklog/MERGE_WORK_LOG.md) | 01/08 — gỡ merge `feature/vocab-schema-v2` |
| [MULTITENANT_PREP.md](11-worklog/MULTITENANT_PREP.md) | 31/07 |
| [BACKEND_WORK_PLAN.md](11-worklog/BACKEND_WORK_PLAN.md) | 06/08 — khảo sát backend |
| [BACKEND_WORK_PROGRESS.md](11-worklog/BACKEND_WORK_PROGRESS.md) | 07/08 |
| [CODE_REVIEW_2026-08-08.md](11-worklog/CODE_REVIEW_2026-08-08.md) | 08/08 |
| [SAAS_V4_2026-08-08.md](11-worklog/SAAS_V4_2026-08-08.md) · [SAAS_V4_HOAN_THIEN_2026-08-08.md](11-worklog/SAAS_V4_HOAN_THIEN_2026-08-08.md) | 08/08 |
| [LEGAL_V5_2026-08-08.md](11-worklog/LEGAL_V5_2026-08-08.md) | 08/08 |
| [DEPLOY_VA_SO_DAU_VET_2026-08-08.md](11-worklog/DEPLOY_VA_SO_DAU_VET_2026-08-08.md) | 08/08 |

## 99-archive

[QUICK_REFERENCE.md](99-archive/QUICK_REFERENCE.md) — ghi chú xoá/sửa nhãn, đã bị các tài
liệu ở `02-data/` thay thế. Bản khác của tệp này còn ở `Extra_docs/99-archive/`.

---

## Quy ước

- **Thư mục `needFix/` đã bị bỏ.** Tên đó gộp ba thứ khác nhau: tài liệu kiến trúc mà mã
  nguồn đang trích dẫn như nguồn tham chiếu, việc còn thiếu, và nhật ký. Chúng đã tách về
  `01-architecture/`, `10-issues/`, `11-worklog/`.
- Tài liệu mô tả thứ **chưa hiện thực** phải nói rõ ở dòng đầu (xem `SSO_OIDC_DESIGN.md`).
- Đường dẫn trong mã nguồn trỏ về tài liệu dùng dạng đầy đủ từ gốc repo
  (`docs/03-security/AUTHORIZATION.md`), không dùng đường dẫn tương đối.
