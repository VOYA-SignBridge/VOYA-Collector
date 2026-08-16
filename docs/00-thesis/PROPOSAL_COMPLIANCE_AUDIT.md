# Đối chiếu proposal ↔ hệ thống — cái gì THIẾU so với cam kết

*Đo ngày 15/08/2026. Nguyên tắc: **được phép làm dư proposal, không được làm
thiếu.** Mục "Included" và "Expected Outcomes" là cam kết ràng buộc, không phải
danh sách mong muốn — thiếu một dòng ở đó không ghi được thành Future Work, vì
chính proposal đã có mục Excluded riêng và dòng đó không nằm trong đó.*

---

## 1. Tám mục tiêu cụ thể

| # | Cam kết (Specific Objectives) | Đo được hôm nay | |
|---|---|---|---|
| 1 | Kiến trúc **Workspace–Project**; mỗi workspace là một tenant độc lập với **projects, members, dataset ownership** riêng | Bảng `workspaces`, `projects` có thật, khoá ngoại ghép chống bắc cầu tenant. Nhưng **không router nào tạo được chúng**; mỗi tenant có đúng 1 workspace + 1 project mặc định do backfill sinh; dữ liệu (`samples`, `classes`) **chưa mang `project_id`** — `scope_resolver.py:16-21` ghi thẳng "cây bốn tầng vừa được dựng nhưng dữ liệu chưa được gắn vào nó" và dùng `_default_project()` để lấp | **THIẾU** |
| 2 | Cách ly dữ liệu tenant theo logic | RLS + FORCE trên 32/34 bảng mang `tenant_id`, fail-closed khi thiếu ngữ cảnh, `voya_app` không SUPERUSER/BYPASSRLS. Hở: `tenants`, `tenant_purges` | **GẦN ĐỦ** |
| 3 | IAM đa tenant, **RBAC ba phạm vi system / workspace / project** | Casbin RBAC-with-domains có thật: `model.conf`, 4 domain, 13 vai dựng sẵn (2 SYSTEM / 5 TENANT / 2 WORKSPACE / 4 PROJECT). Nhưng `AUTHZ_MODE=shadow` → **hệ cũ hai phạm vi quyết định**; và không có workspace/project thật để gán vai ở hai tầng dưới | **THIẾU** |
| 4 | Mô hình quản lý dữ liệu chuẩn hoá: từ vựng, phương ngữ, người đóng góp, **tài nguyên project** | `vocabulary_registry.py` + `community_*` + `dialects` + `signers` + `registry_versions` đầy đủ | **GẦN ĐỦ** (vế "project resources" phụ thuộc mục 1) |
| 5 | Trích xuất điểm mốc trên trình duyệt để **cải thiện hiệu quả lưu trữ** | Có, chạy thật. Nhưng dùng **MediaPipe Hands**, không phải Holistic; và **chưa có phép đo hiệu quả lưu trữ nào** | **THIẾU 2 vế** |
| 6 | Xử lý bất đồng bộ | Celery + Redis; ingest → cắt cửa sổ theo hoạt động (`pipeline.py`) → tăng cường (`augmentations.py`, `augmenter.py`) → đồng bộ đám mây | **ĐỦ** |
| 7 | Cơ chế toàn vẹn & đồng bộ dữ liệu (SOT), **theo workspace** | SOT có thật: ký Ed25519, phiên bản bất biến, lược đồ v8, `catalog_schema` mang `tenant_id` | **CẦN MỘT PHÉP KIỂM** — chưa có test nào chứng minh SOT phân tách theo workspace |
| 8 | Đánh giá: **chức năng, cách ly tenant, hiệu quả lưu trữ, hiệu năng** | Chức năng: ~1.7k test xanh. Cách ly: chưa có số đối kháng. Lưu trữ: chưa đo. Hiệu năng: chưa đo | **THIẾU 3/4** |

## 2. Công nghệ đã tuyên bố

| Công nghệ | Trạng thái |
|---|---|
| FastAPI · React 18 / TS / Vite / Tailwind · PostgreSQL 16 · Celery · Redis · Docker Compose · Nginx | **ĐỦ** |
| **MinIO (S3-compatible object storage)** | **KHÔNG TỒN TẠI** trong stack — không có service trong `docker-compose.yml`, không có `boto3`/client S3 trong `requirements.txt`. Thực tế: hệ tệp cục bộ + Google Drive |
| **MediaPipe Holistic** | `@mediapipe/holistic@0.5.x` **có trong `package.json` nhưng không tệp nguồn nào import**. Mã dùng `@mediapipe/hands` ở cả 4 chỗ: `FullscreenCaptureModal`, `RealtimeRuntime`, `handTracking.ts`, `TestTrainedModelModal` |

### Về MediaPipe: proposal tự mâu thuẫn, và hệ thống đứng về phía đúng

Đây không hẳn là hệ thống làm thiếu. Chính proposal nói hai điều loại trừ nhau:

* mục Included: "Browser-based landmark extraction (**MediaPipe Holistic**)"
* mục Excluded: "**Full-body pose and facial-expression capture** (schema fields reserved; recording/processing pipelines not implemented)"

Toàn bộ lý do tồn tại của Holistic là gộp **pose + face + hands**. Loại trừ pose
và face rồi vẫn khai Holistic là mô tả một thứ không thể có. Con số proposal tự
nêu — "21 landmarks/hand, 126 values/frame" — chính xác là số của **Hands**
(21 × 3 × 2 = 126), không phải Holistic (543 điểm mốc).

Nên cách xử lý đúng là **sửa proposal thành Hands** kèm giải trình: lựa chọn này
nhất quán với mục Excluded và với con số 126 chiều đã công bố. Đây là chỗ duy
nhất trong bản audit này mà sửa câu chữ là lời giải đúng, không phải né tránh.

## 3. Chín kết quả mong đợi

| # | Cam kết | |
|---|---|---|
| 1 | Nền tảng SaaS đa tenant chạy được | **ĐỦ** — 14 container healthy |
| 2 | Kiến trúc Workspace–Project + RBAC ba phạm vi | **THIẾU** hiện thực (xem mục tiêu 1, 3) |
| 3 | Cách ly tenant cưỡng chế nhất quán ở tầng truy cập dữ liệu | **GẦN ĐỦ** |
| 4 | Phân loại từ vựng chuẩn + cơ chế tenant mở rộng từ vựng dùng chung mà không đụng bản chuẩn | **ĐỦ** |
| 5 | Giảm **trên 90%** dung lượng mỗi mẫu so với video thô | **CHƯA ĐO** — không có phép đo nào trong kho |
| 6 | Pipeline xử lý bất đồng bộ | **ĐỦ** |
| 7 | Cơ chế toàn vẹn có ký, mở rộng theo workspace | **CẦN PHÉP KIỂM** |
| 8 | Đánh giá thực nghiệm bốn mặt | **THIẾU 3/4** |
| 9 | Kiến trúc tham chiếu cho SaaS đầy đủ | **DƯ** — xem §5 |

## 4. Tổng hợp: bảy khoảng thiếu thật

Xếp theo trọng số trong quyển × công sức đóng:

| # | Thiếu | Vì sao nặng | Đóng bằng gì |
|---|---|---|---|
| 1 | **`project_id` trên dữ liệu + CRUD workspace/project** | Đây là mục tiêu số 1, kết quả số 2, và là danh từ trung tâm của cả đề tài. Không có nó, "Workspace–Project" chỉ là hai bảng rỗng | Router CRUD + cột `project_id` trên `samples`/`classes` + backfill + gỡ `_default_project()` |
| 2 | **RBAC ba phạm vi chưa cưỡng chế** | Mục tiêu số 3. Casbin đã dựng xong nhưng đang `shadow` | Làm sạch mismatch → `AUTHZ_MODE=casbin`. Phải thu hồi quyền ghi 6 nguồn phân quyền trước |
| 3 | **Chưa đo hiệu quả lưu trữ** | Kết quả số 5 hứa một con số cụ thể ">90%" | 1–2 giờ: so tổng `dataset/raw/` với tổng `.npz` tương ứng, báo trung vị + khoảng |
| 4 | **Chưa đo hiệu năng** | Mục tiêu số 8 | 2–3 giờ: `hey`/`locust` bắn 5–6 endpoint, báo p50/p95/p99 |
| 5 | **Chưa đo cách ly bằng thực nghiệm** | Mục tiêu số 8, và là đóng góp lõi | Bộ đối kháng + CTIVR/UASR/TCBVR (xem `TENANT_ISOLATION_AND_AUTHZ.md`) |
| 6 | **MinIO không tồn tại** | Đã nêu đích danh trong Technologies và trong Cơ sở lý thuyết §5 | Hoặc thêm service MinIO + định tuyến một đường blob qua nó; hoặc sửa proposal thành "kho blob mờ: hệ tệp + Google Drive" kèm ADR |
| 7 | **SOT theo workspace chưa có bằng chứng** | Included + kết quả số 7 | Một test: hai tenant, hai gói SOT, không cái nào đọc được của cái kia |

Hai bảng hở RLS (`tenants`, `tenant_purges`) không nằm trong bảng này vì chúng
là khiếm khuyết chất lượng của mục tiêu 2 chứ không phải hạng mục thiếu — nhưng
chúng vẫn phải đóng trước khi công bố số đo cách ly.

## 5. Phần LÀM DƯ — được phép, và nên khai

Mục Excluded của proposal ghi rõ: *"Fully automated per-tenant resource
governance and quotas, complete tenant-lifecycle automation, and legal/consent
management **designed at the architecture level and reserved for future
realization**."*

Ba thứ đó đã được **hiện thực thật**, vượt cam kết:

| Hạng mục | Trạng thái |
|---|---|
| Quản trị tài nguyên & hạn mức theo tenant | 8 chỉ số hạn mức cưỡng chế ở đường ghi, mã 402, header `X-Quota-*`, bảng giá sửa được lúc chạy |
| Tự động hoá vòng đời tổ chức | Kỳ hạn, tự gia hạn, nhắc 7/3/1 ngày, ân hạn, khoá mềm — 7/9 bước, quét mỗi giờ |
| Quản lý pháp lý & đồng thuận | Kho văn bản pháp lý có trigger bất biến, cưỡng chế chấp nhận điều khoản, đồng thuận ba mức có thể rút |

Và ngoài phạm vi proposal hoàn toàn: 2FA/TOTP tự viết kiểm bằng vector RFC,
vòng đời phiên ba mức thu hồi, nhật ký kiểm toán ghi kép, quan trắc
Loki/Grafana/Prometheus có cảnh báo, sao lưu–khôi phục có diễn tập, i18n vi/en,
console quản trị 21 mục, Casbin PDM v5 gộp 8 bảng còn 2.

**Điều này đáng nói ra trong quyển**, nhưng nói ở đúng chỗ: phần "vượt phạm vi
đã cam kết", không phải dùng nó để lấp chỗ của bảy khoảng thiếu ở §4. Hội đồng
chấm theo cam kết, và phần dư không bù được phần thiếu.

Cũng nên tự nhận thẳng: chính phần dư này đã tiêu mất thời gian mà mục tiêu 1,
3, 5 cần. Đó là một bài học về quản lý phạm vi, và nếu tự nêu trong phần Hạn chế
thì nó thành một nhận định trưởng thành thay vì một lỗ hổng bị phát hiện.

## 6. Hai chỗ khác trong proposal cần kiểm chứng, không phải kỹ thuật

* **Methodology giai đoạn 2**: "requirements analysis with domain stakeholders in
  Can Tho". Nếu buổi làm việc đó có thật, phải có bằng chứng (biên bản, ảnh, danh
  sách). Nếu không, bỏ khỏi quyển.
* **Experimental Datasets** liệt kê "Field-collected VSL data (Can Tho) — thu tại
  cơ sở giáo dục đặc biệt và hợp tác xã". Dữ liệu hiện có là **3.860 mẫu, 100%
  nguồn camera, 64% là bảng chữ cái**. Nếu chưa có đợt thu tại chỗ, dòng này
  trong Chương 4 sẽ không có gì chống lưng.

Số liệu bịa là rủi ro lớn nhất trong một buổi bảo vệ; hai dòng trên rẻ để sửa và
đắt để bị hỏi.
