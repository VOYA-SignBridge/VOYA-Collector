# CTU-SignBridge — Tổng hợp hệ thống & khung luận văn

*Dựng 2026-08-10. Nguồn: mã nguồn nhánh `deploy_ctu_ver-2.2.1`, `docs/`, `Extra_docs/`,
đề cương `docs/00-thesis/proposal/MNM_Thesis proposal_CT553H.docx`.*

Tài liệu này trả lời ba câu: **hệ thống thật sự là gì**, **chỗ nào đề cương nói khác
với thứ đã dựng**, và **quyển luận văn nên gồm những gì, lấy bằng chứng ở đâu**.

---

## 1. Hệ thống, nói trong một đoạn

CTU-SignBridge là nền tảng web đa-tổ-chức (SaaS multi-tenant) để **thu thập, chuẩn hoá
và quản lý dữ liệu Ngôn ngữ ký hiệu Việt Nam**. Người đóng góp ký hiệu trước webcam;
trình duyệt trích điểm mốc bàn tay bằng MediaPipe ngay tại máy khách, nên **video thô
không bắt buộc rời khỏi máy người dùng**; chuỗi toạ độ được đóng gói `.npz`, đưa qua
hàng đợi bất đồng bộ để cắt cửa sổ, tăng cường, chấm chất lượng, rồi ghi vào kho dữ
liệu có danh mục từ vựng chuẩn và siêu dữ liệu phương ngữ. Nhiều tổ chức dùng chung
một bản triển khai nhưng **không đọc được dữ liệu của nhau** — ranh giới đó do chính
PostgreSQL cưỡng chế, không phải do lập trình viên nhớ viết `WHERE`.

---

## 2. Số liệu chốt (dùng cho Chương 4)

| Hạng mục | Số | Nguồn kiểm chứng |
|---|---|---|
| Bảng CSDL | **44** | `docs/02-data/db/schema_erd.sql` |
| Bảng có chính sách RLS | **13** | `backend/app/storage/rls.py` |
| Điểm cuối API | **209** | đếm decorator trong `backend/app/routers/` |
| Router nghiệp vụ | 26 | `backend/app/routers/` |
| Mã backend | **47.334 dòng** Python (143 tệp) | `backend/app/` |
| Mã frontend | **41.316 dòng** TS/TSX (194 tệp) | `frontend/src/` |
| Mã kiểm thử | **26.700 dòng** (104 tệp) | `backend/tests/` |
| Test backend | **1.696 xanh / 0 đỏ** (bản sao sản xuất) | `docs/08-testing/TESTING.md` |
| Test backend trên CSDL dựng-từ-số-không | **1.681 xanh / 0 đỏ / 15 skip** | CI `signdb_ci` |
| Test frontend | **363** (45 tệp) | `docs/08-testing/TESTING.md` |
| Dịch vụ container | **13** (đủ 13 healthy) | `docker-compose.yml` |
| Mẫu đã thu | **3.860** | `dataset/samples.csv` |
| Lớp từ vựng | **60** | như trên |
| Phân bố phương ngữ | bảng chữ cái 2.487 · hoa-đề 830 · common 363 · Cần Thơ 109 · spa 71 | như trên |
| Kích thước một mẫu `.npz` | **≈ 44 KB** (60 khung × 126 chiều) | `dataset/features/` |
| Phiên bản lược đồ SOT | 8 | `backend/app/sot/__init__.py` |

**Cảnh báo về số liệu:** cột "phân bố phương ngữ" cho thấy dữ liệu **rất lệch** —
64% là bảng chữ cái. Đừng viết "bộ dữ liệu cân bằng"; hãy viết đúng và đưa mất cân
bằng vào phần Hạn chế. Tương tự, 100% mẫu là nguồn `camera`, không có mẫu từ video.

---

## 3. Kiến trúc chạy thật

### 3.1 Mười ba dịch vụ

| Nhóm | Dịch vụ | Vai trò |
|---|---|---|
| Biên | `nginx` | cổng vào duy nhất, một origin cho cả SPA lẫn API |
| Ứng dụng | `frontend` · `backend` · `realtime_service` | SPA React 19 · FastAPI · dịch vụ suy luận thời gian thực |
| Xử lý nền | `worker` · `celery-beat` · `trainer` | tác vụ nhập liệu/đồng bộ · hẹn giờ · huấn luyện (GPU) |
| Dữ liệu | `postgres` · `redis` · `pg-backup` | siêu dữ liệu · broker + hạn mức · sao lưu định kỳ |
| Khởi tạo | `sot-init` | kéo + kiểm chữ ký danh mục trước khi bất kỳ dịch vụ nào chạy |
| Quan trắc | `prometheus` · `grafana` · `loki` · `promtail` | chỉ số · cảnh báo/biểu đồ · nhật ký |

`sot-init` **thoát mã 4 sẽ chặn cả stack** — có chủ ý: một máy không xác thực được
danh mục thì không được phép chạy.

### 3.2 Luồng dữ liệu

```
Webcam / Video
   │  MediaPipe Hands chạy TRONG TRÌNH DUYỆT (WebAssembly)
   ▼
21 điểm mốc × 3 toạ độ × 2 tay = 126 chiều/khung
   │  POST /upload/camera
   ▼
FastAPI ──► Redis (broker) ──► Celery worker
                                  │
                                  ├─ ghi kho thô (dataset/raw/) TRƯỚC khi chuẩn hoá
                                  ├─ cắt cửa sổ trượt T=60, stride=2
                                  ├─ tăng cường dữ liệu
                                  ├─ chấm chất lượng (completeness, jitter, tỉ lệ tay)
                                  ├─ ghi dataset/features/<class_uid>/<uid>.npz  (≈44 KB)
                                  └─ ghi samples.csv (nguồn sự thật) + PostgreSQL (bản sao)
                                          │
                                          └─ đồng bộ Google Drive (bất đồng bộ, có thử lại)
```

**Chi tiết dễ bị hỏi khi bảo vệ:** nguồn sự thật của kho mẫu là **tệp CSV**
(`dataset/samples.csv` ở gốc), PostgreSQL là **bản sao để truy vấn**. Đây là di sản
kiến trúc, không phải thiết kế lý tưởng — hãy nói thẳng và giải thích cơ chế đối soát
(beat định kỳ CSV↔DB) thay vì giấu.

---

## 4. Bảy trụ cột nội dung — mỗi trụ là một đóng góp có thể bảo vệ

### Trụ 1 — Cô lập tenant hai mặt phẳng (ĐÓNG GÓP LÕI)

Khẳng định trung tâm, chép nguyên từ `docs/01-architecture/TENANT_ISOLATION.md`:

> Một truy vấn không khai báo tenant trả về **0 hàng**, không phải mọi hàng.
> Và ứng dụng **không tự tắt được** cơ chế đó.

Cơ chế, bốn tầng, mỗi tầng có lý do tồn tại riêng:

1. **Cột phân biệt** `tenant_id` trên 13 bảng — cần, nhưng một mình thì chỉ là siêu dữ liệu.
2. **Row-Level Security** đọc GUC `app.tenant_id` bằng `current_setting(..., true)`.
   Dạng `missing_ok` này khiến chính sách **fail-closed**: chưa gán thì so sánh ra
   NULL, NULL không phải TRUE, nên thấy 0 hàng.
3. **`SET LOCAL` trong một context manager duy nhất.** `SET` thường sẽ dính lại trên
   connection pool và rò sang request kế tiếp — lỗi kinh điển RLS-cộng-pooling,
   **không sinh ra thông báo lỗi nào**, chỉ có một người dùng xui đọc được dữ liệu
   của người khác.
4. **Tách hai vai CSDL.** `voya_app` chỉ DML; DDL nằm ở vai riêng. Vì
   `ALTER TABLE ... DISABLE ROW LEVEL SECURITY` là DDL — một vai vừa ghi được dữ liệu
   vừa chạy được DDL thì **tự gỡ được vòng vây của chính nó**, và bảo đảm biến thành
   lời khuyên. `FORCE ROW LEVEL SECURITY` **không đủ**: PostgreSQL miễn trừ RLS vô
   điều kiện cho SUPERUSER.

GUC thứ hai `app.system_scope` cho công việc nền tảng hợp lệ xuyên tenant (đồng bộ
CSV→DB lúc khởi động, SOT reader, bảo trì Celery). Cố ý làm thành **GUC riêng** chứ
không phải một "tenant id ma thuật", để "hành động thay mọi người" không bao giờ sinh
ra được từ một lỗi gõ tên tenant.

*Lập luận mạnh nhất để đưa vào quyển:* ba hàm trong `storage/metadata_db.py` —
`delete_sample()`, `delete_samples_by_class()`, `update_sample_gdrive_url()` — **đến
hôm nay vẫn không lọc tenant**. Vá tay là vá ba hàm đã biết; chính sách ở CSDL vá luôn
những hàm sẽ viết sau mà tác giả quên lọc. Đây là luận cứ "cưỡng chế ở tầng CSDL"
tốt nhất bạn có, và nó là bằng chứng thật chứ không phải giả định.

### Trụ 2 — Nguồn sự thật ký số (SOT)

Một máy đăng ký giữ khoá riêng **Ed25519** *công bố* các phiên bản bất biến của danh
mục + lược đồ lên thư mục `SOT/` trên Drive. Máy chủ và VPS **chỉ đọc**: lúc triển
khai, trước khi bất kỳ worker nào chạy, chúng kéo bản mới nhất, **kiểm chữ ký** với
khoá công khai đã commit, rồi bảo đảm CSDL của mình là **tập cha** của bản đó —
thêm cái thiếu, **không bao giờ xoá**.

Ba tính chất đáng viết:
- **Tamper-evident**: manifest băm SHA-256 toàn bộ tệp, chữ ký phủ manifest.
- **Fail-closed**: không xác thực được thì dừng, không suy đoán (`sot-init` exit 4).
- **Chỉ-điền, không-xoá**: hợp nhất hai máy an toàn theo một chiều.

`REQUIRED_COLUMNS` trong `catalog_schema.py` mang một bài học đáng kể: sáu cột từng
thiếu khỏi danh sách kiểm, khiến một reader có lược đồ thiếu vẫn **qua được khâu xác
thực** rồi mới hỏng giữa chừng lúc nhập, khi ghi những cột mà manifest chưa từng hứa
là có. Đây là ví dụ sách giáo khoa về "kiểm tra không phủ hết bằng thứ nó bảo vệ".

### Trụ 3 — Danh mục từ vựng ba mặt phẳng

```
System Catalog ──clone MỘT LẦN──► Tenant Registry ──pin──► Dataset/Campaign
 (cấu hình, admin HT)              (tenant tự sửa)          (bất biến, có hash)
```

Luật xuyên suốt: **runtime KHÔNG bao giờ fallback ngược về Community**; thiếu dữ liệu
thì **DỪNG**, không suy đoán.

Ba lỗi thật đã thúc đẩy thiết kế này (dùng làm phần "Phân tích vấn đề"):
1. Danh sách profile gắn cứng ở hai nơi và đã lệch nhau (6 vs 5) → **7 lớp `spa` bị
   lọc khỏi split trong im lặng**.
2. `registry_version` là bộ đếm bị ghi đè, snapshot là một tệp bị ghi đè → "dataset
   pin v2" **không thực hiện được**, vì nội dung v2 biến mất ngay khi v3 ghi.
3. Không có khái niệm thành viên tenant → hoặc không tenant nào tự quản được, hoặc
   mọi admin hệ thống thành editor của mọi tenant.

Kèm phân biệt **"đã đăng ký ≠ huấn luyện được"**: một lớp có 500 mẫu mà người ký chưa
đồng ý mức tương ứng thì với đường phát hành nghiên cứu nó là lớp **rỗng**.

### Trụ 4 — Đồng thuận & quy kết dữ liệu (điểm mạnh khác biệt nhất)

Đây là phần ít hệ thống thu dữ liệu nào làm, và là chỗ luận văn của bạn khác các đề
tài "làm web thu dữ liệu" thông thường.

- **`auth_user_id` ≠ `signer_id`**: tài khoản bấm nút thu ≠ người có bàn tay trong dữ
  liệu. Chủ thể dữ liệu là vế thứ hai. Phủ đo được ngày 10/08/2026: `auth_user_id`
  95,7% mẫu (3 giá trị phân biệt); `signer_id` **43,4%** (4 giá trị).
- **Hệ quả đo được:** *56,6% kho dữ liệu không truy được về người có bàn tay trong đó.*
  Nếu ai đó nói "tôi rút phần đóng góp của tôi", hệ thống **không xác định nổi đó là
  những dòng nào**. Con số này là một kết quả nghiên cứu, không phải một lỗi cần giấu.
- **Bốn nghĩa của "thu hồi"**, và hệ thống chỉ thi hành nghĩa thứ hai:

  | # | Nghĩa | Đã thi hành? |
  |---|---|---|
  | 1 | Thu hồi quyền truy cập của một người | có (RLS + vai) |
  | 2 | Gỡ khỏi bản phát hành **mới** | **có** — bốn đường dữ liệu đều qua cổng đồng thuận |
  | 3 | Xoá khỏi lưu trữ | không — thao tác vận hành, làm tay |
  | 4 | Thu hồi giấy phép **đã cấp** cho bên thứ ba | không — cần cơ chế pháp lý |

  Hứa "xoá là biến mất hoàn toàn" là hứa nghĩa 3 và 4 trong khi chỉ làm nghĩa 2.
  Giao diện nói thẳng điều này và **có test ghim câu chữ**.
- **Văn bản pháp lý bất biến sau khi công bố** (trigger ở CSDL). Lý do: một chấp thuận
  trỏ tới `(kind, version)`; đổi nội dung dưới chân nó biến bằng chứng thành lời khẳng
  định suông. Cờ `requires_reconsent` tách "sửa lỗi chính tả" khỏi "đổi phạm vi xử lý
  dữ liệu".

### Trụ 5 — Vòng đời tổ chức & quản trị tài nguyên

Tenant CRUD, lời mời, OTP hai kênh, gói cước, kỳ hạn/nhắc/ân hạn/khoá mềm, xuất dữ
liệu, xoá mềm + `tenant_purges`. Hai phân biệt cần giữ rõ trong quyển:

- **Hạn mức "đang dùng" (để chặn) ≠ "đã từng dùng" (để tính tiền)** — cố ý đọc từ hai
  nguồn khác nhau. `current_usage` **fail-OPEN** (trả 0 khi truy vấn hỏng), ngược với
  phần còn lại: nó nằm trên đường ghi nóng, và biến sự cố CSDL thành "mọi người hết
  hạn mức" là nhân sự cố lên. Ranh giới thật nằm ở RLS, không ở đây.
- **Trạng thái thương mại ≠ trạng thái quản trị.** `past_due` vẫn ghi được là **quyết
  định**, không phải sơ suất: khoá dữ liệu của một trường vì hoá đơn trễ hai ngày là
  cách nhanh nhất để mất họ.

### Trụ 6 — Bảo mật & danh tính

Xác thực bằng token (access + refresh), phiên có ba mức thu hồi, **2FA TOTP tự viết
kiểm bằng vector RFC**, sudo mode, cổng truy cập mặc-định-từ-chối ở middleware, giới
hạn tốc độ theo IP thật (không cho caller tự chọn), allowlist host công khai cho
liên kết đặt lại mật khẩu, nhật ký kiểm toán ghi cả Redis lẫn bảng `audit_log` và
**fail-closed khi không có phạm vi**.

Bài học đáng viết vào phần Thảo luận: **RLS fail-OPEN ở mặt phẳng danh tính.** Truy
vấn chạy *trước khi* biết tenant khớp 0 dòng, và "0 dòng" bị mã đọc thành "không có
gì" thay vì "chưa có ngữ cảnh" — sai lầm này lặp **ba lần trong hai ngày**. Đó là
minh chứng rằng fail-closed ở tầng CSDL vẫn có thể bị tầng ứng dụng diễn giải sai.

### Trụ 7 — Vận hành: quan trắc, sao lưu, kiểm chứng triển khai

- **Quan trắc**: Prometheus + Grafana + Loki/Promtail; cảnh báo sống ở Grafana (không
  có Alertmanager); nguyên tắc label Loki **thấp lực lượng** + structured metadata.
- **Sao lưu**: hai kho, thứ tự dump-trước-nén-sau, diễn tập khôi phục bằng `--drill`.
  Bài học: `pg_restore --list` **không** bắt được tệp cụt.
- **Kiểm chứng triển khai**: `scripts/check_deploy_freshness.py`. Lý do tồn tại là một
  sự cố thật — **một image frontend từng chạy sau mã nguồn 5 tiếng trong khi cả 13
  container báo healthy**, trang web tải hoàn hảo và phục vụ bundle cũ. `docker compose
  ps` trả lời "tiến trình còn sống", không phải "đó có phải tiến trình bạn vừa dựng".

---

## 5. Đề cương nói một đằng, hệ thống làm một nẻo — 6 chỗ phải xử lý

**Đây là phần quan trọng nhất của tài liệu này.** Sáu chỗ dưới đây nếu để nguyên trong
quyển sẽ là sáu câu hỏi phản biện mà bạn không trả lời được.

| # | Đề cương / bản nháp LaTeX cũ nói | Hệ thống thật | Xử lý đề xuất |
|---|---|---|---|
| 1 | Phân quyền bằng **Casbin** (RBAC-with-domains) | Kiểm quyền **tự viết**: `require_admin` (`users.is_admin`) + `require_tenant_admin` (`tenant_members.role`), vai `admin\|editor\|viewer`. Casbin chỉ tồn tại ở nhánh v2 dạng **stub rỗng**. | Viết lại thành "RBAC hai phạm vi hiện thực trực tiếp"; **giữ Casbin ở phần Cơ sở lý thuyết** như mô hình tham chiếu và nêu lý do không dùng thư viện (một tenant-role duy nhất, không cần policy engine). Trung thực và vẫn đủ hàn lâm. |
| 2 | Lưu trữ đối tượng **MinIO** | Không có MinIO trong stack. Thực tế: **hệ tệp cục bộ + Google Drive**. | Bỏ MinIO khỏi phần công nghệ; chuyển sang "kho blob mờ" như ADR đã chốt. Giữ MinIO ở Hướng phát triển. |
| 3 | Mô hình **Workspace → Project** ba cấp, RBAC ba phạm vi (system/workspace/project) | Lược đồ có `tenants` **phẳng** + `tenant_members`; **không có bảng workspace/project**. RBAC **hai** phạm vi. | Theo ADR-001 "workspace **là** tenant": khai báo thẳng rằng cấp workspace/project là **thiết kế tham chiếu** (Chương 3, có ERD v2 đầy đủ) còn phần **hiện thực & đánh giá** dừng ở cấp tenant. Đề cương đã dự phòng chỗ này ở mục Excluded. |
| 4 | **MediaPipe Holistic** | Mã dùng **MediaPipe Hands**. Gói `@mediapipe/holistic` có trong `package.json` nhưng **không tệp nguồn nào import**. | Sửa thành Hands ở mọi chỗ. Con số 126 chiều/khung trong đề cương vốn đã là con số của Hands (21×3×2), nên phần định lượng không đổi. |
| 5 | Bản nháp LaTeX cũ (`Extra_docs/90-research/LuanVan_LaTeX`) nói **Keycloak SSO**, **Star Schema**, benchmark **JMeter** | Không có Keycloak (đề cương mới đã bỏ, bản nháp thì chưa). Lược đồ là quan hệ chuẩn hoá, **không phải star schema**. Chưa có kết quả JMeter nào trong kho. | **Không dùng lại bản nháp LaTeX đó làm nền.** Nó mô tả một hệ thống chưa từng tồn tại. Chỉ lấy lại phần khung `preample.tex`/`coverpage.tex`. |
| 6 | "Giảm **trên 90%** dung lượng so với video thô" | Chưa có phép đo nào trong kho. Đã biết: `.npz` ≈ 44 KB/mẫu. | **Phải đo thật** trước khi viết (xem §7 mục 2). Nếu không kịp đo, hạ thành phát biểu định tính có trích dẫn. |

Ngoài ra: bản nháp Chương 1 cũ nêu "khảo sát sơ bộ với 3 nhóm nghiên cứu và 5 tình
nguyện viên" — nếu khảo sát đó **không thật sự diễn ra**, hãy bỏ. Số liệu bịa là rủi
ro lớn nhất trong một buổi bảo vệ.

---

## 6. Khung quyển luận văn đề xuất (5 chương) và bằng chứng cho từng mục

### Chương 1 — Giới thiệu (~8–10 trang)
| Mục | Nội dung | Lấy ở đâu |
|---|---|---|
| 1.1 Đặt vấn đề | VSL thiếu tài nguyên; dữ liệu phân mảnh; hạ tầng thu thập dùng chung không tồn tại | Đề cương §I.1 |
| 1.2 Ba vấn đề vận hành cụ thể | mất dữ liệu khi rớt mạng · trùng lặp xuyên nhóm · thiếu phân loại chuẩn | Chỉ giữ nếu có bằng chứng thật |
| 1.3 Mục tiêu | 1 tổng quát + 5 cụ thể | Đề cương §I.2 (**giữ nguyên**) |
| 1.4 Phạm vi | Bảng Included/Excluded — **cập nhật theo §5 trên** | Đề cương §I.3 |
| 1.5 Ý nghĩa | khoa học + thực tiễn | Đề cương |
| 1.6 Bố cục | 5 chương | — |

### Chương 2 — Cơ sở lý thuyết (~15–18 trang)
Bảy khái niệm lõi của đề cương ánh xạ **1-1** thành bảy tiểu mục — đề cương đã viết
sẵn phần này gần như đủ dùng, kèm đủ trích dẫn IEEE:
1. VSL & phát triển bộ dữ liệu — [1][2][5][8][9][7]
2. SaaS multi-tenancy & cô lập tenant — [3][4][10][11][12]
3. IAM & RBAC đa tenant — [13][14][15]
4. Ước lượng tư thế & thu theo điểm mốc — [16][17][18]
5. Xử lý bất đồng bộ — [19][20][21]
6. Toàn vẹn dữ liệu & chữ ký số — [19][23]
7. Cloud-native & di trú hệ thống (Twelve-Factor, Strangler Fig) — [24][6]

**Bổ sung một tiểu mục 2.8** mà đề cương chưa có nhưng hệ thống làm rất kỹ:
*đồng thuận, quy kết và quản trị dữ liệu chủ thể*. Đây là chỗ Trụ 4 cần chỗ dựa lý
thuyết.

### Chương 3 — Phân tích & thiết kế (~25–30 trang) — **chương dày nhất**
| Mục | Nội dung | Bằng chứng |
|---|---|---|
| 3.1 Yêu cầu | chức năng + phi chức năng | `Extra_docs/06-usecases/` |
| 3.2 Kiến trúc tổng thể | 13 dịch vụ, sơ đồ triển khai, luồng dữ liệu | `docker-compose.yml`, `ctu_signbridge_architecture.png` |
| 3.3 Thiết kế CSDL | ERD 44 bảng; **giải thích các cặp khái niệm không được gộp** | `docs/02-data/db/schema_erd.sql`, `docs/01-architecture/CONCEPTS.md` |
| 3.4 Thiết kế cô lập tenant | bốn tầng ở Trụ 1; bảng so sánh 3 mô hình cô lập và lý do chọn shared-schema+RLS | `docs/01-architecture/TENANT_ISOLATION.md` |
| 3.5 Thiết kế IAM | token, phiên, 2FA, cổng mặc-định-từ-chối, hai vòng quyền | `docs/03-security/SESSION_LIFECYCLE.md`, `docs/03-security/TWO_FACTOR.md` |
| 3.6 Danh mục ba mặt phẳng | System Catalog / Commons / Tenant | `docs/01-architecture/REGISTRY_ARCHITECTURE.md` |
| 3.7 Đường ống bất đồng bộ | ba bước bắt tay, thử lại, đồng bộ Drive | `backend/app/processing/`, `sync_tasks.py` |
| 3.8 SOT ký số | Ed25519, manifest, fail-closed, hợp nhất chỉ-điền | `backend/app/sot/` |
| 3.9 Đồng thuận & quy kết | ba mức, bốn nghĩa thu hồi, văn bản bất biến | `docs/04-legal/CONSENT_ENFORCEMENT.md`, `docs/04-legal/LEGAL_DOCUMENTS.md` |
| 3.10 Thiết kế tham chiếu (chưa hiện thực) | Workspace/Project, quota tự động, Commons | `docs/01-architecture/MULTITENANT_ARCHITECTURE.md` + 8 ADR |

**Mẹo:** tám ADR trong `Extra_docs/01-architecture/adr/` nên vào **Phụ lục** và được
trích dẫn ở thân bài. Đó là bằng chứng "có quy trình thiết kế", thứ hội đồng đánh giá
cao và hầu hết luận văn không có.

### Chương 4 — Hiện thực & đánh giá (~20–25 trang)
| Mục | Nội dung | Trạng thái |
|---|---|---|
| 4.1 Môi trường & công nghệ | Docker Compose, 13 dịch vụ, cấu hình máy | ✅ có |
| 4.2 Hiện thực các mô-đun | thu trực tiếp, danh mục, huấn luyện, nhận dạng thời gian thực, quản trị | ✅ có, kèm ảnh chụp màn hình |
| 4.3 **Kiểm thử** | 1.696 backend + 363 frontend; hai nền chạy; 5 kiểu "đỏ giả" | ✅ **rất mạnh, phải làm nổi bật** |
| 4.4 **Kiểm chứng cô lập tenant** | test chứng minh truy vấn không ngữ cảnh trả 0 hàng | ✅ có test, cần trích dẫn cụ thể |
| 4.5 Hiệu quả lưu trữ | so `.npz` với video thô | ⚠️ **phải đo** |
| 4.6 Hiệu năng | độ trễ API, thông lượng worker | ⚠️ **phải đo** |
| 4.7 Đối chiếu mục tiêu | bảng 5 mục tiêu × mức đạt | cần dựng |

### Chương 5 — Kết luận (~5–7 trang)
Đóng góp · Hạn chế (nêu thẳng: dữ liệu lệch 64% bảng chữ cái, 56,6% mẫu không quy kết
được người ký, CSV còn là nguồn sự thật, workspace/project mới ở mức thiết kế) ·
Hướng phát triển.

---

## 7. Việc phải làm trước 13/08 — xếp theo tỉ lệ giá trị/công sức

1. **Chốt ngôn ngữ + khuôn mẫu quyển** (30 phút). Xem §8.
2. **Đo hiệu quả lưu trữ** (1–2 giờ) — cần cho mục 4.5, và là con số đề cương đã hứa.
   Cách rẻ nhất: lấy N clip trong `dataset/raw/`, so tổng dung lượng với tổng `.npz`
   tương ứng, báo cáo trung vị + khoảng, **không** báo một con số trần trụi.
3. **Đo độ trễ API** (2–3 giờ) — không cần JMeter; một script `locust`/`hey` bắn vào
   5–6 endpoint chính rồi báo p50/p95/p99 là đủ cho một luận văn kỹ thuật.
4. **Trích xuất bằng chứng cô lập tenant** (1 giờ) — chọn 3–5 test trong `backend/tests/`
   chứng minh trực tiếp "không ngữ cảnh ⇒ 0 hàng", đưa mã test vào quyển. Đây là
   bằng chứng thuyết phục nhất bạn có cho đóng góp lõi.
5. **Vẽ lại 4 sơ đồ**: triển khai 13 dịch vụ · luồng dữ liệu · ERD rút gọn theo cụm ·
   bốn tầng cô lập. `docs/02-data/db/voya_erd.drawio` đã có sẵn nền cho cái thứ ba.
6. **Viết Chương 3** trước, không phải Chương 1. Chương 3 dày nhất, khó nhất, và mọi
   chương khác đều tham chiếu nó.

---

## 8. Ba quyết định cần bạn chốt trước khi tôi viết chương

1. **Ngôn ngữ quyển**: đề cương và bản nháp LaTeX đều bằng **tiếng Anh**; luận văn
   CT553H thường nộp **tiếng Việt**. Chọn sai là phải dịch lại 80 trang.
2. **Khuôn mẫu**: LaTeX (dùng lại `preample.tex`/`coverpage.tex` có sẵn, bỏ phần thân)
   hay Word theo `DeCuong_LuanVan.docx`.
3. **Mức trung thực với §5**: sửa đề cương cho khớp hệ thống (đề xuất của tôi), hay
   giữ nguyên đề cương và bổ sung phần giải trình sai khác ở Chương 4.

---

## 9. Nguồn tài liệu trong kho — bản đồ nhanh

| Cần viết về | Đọc |
|---|---|
| Ranh giới khái niệm dễ nhầm | `docs/01-architecture/CONCEPTS.md` ← **đọc trước tiên, chất lượng luận văn** |
| Cô lập tenant | `docs/01-architecture/TENANT_ISOLATION.md`, `backend/app/storage/rls.py` |
| Kiến trúc đa tenant đầy đủ | `docs/01-architecture/MULTITENANT_ARCHITECTURE.md` (1.412 dòng) |
| Danh mục & registry | `docs/01-architecture/REGISTRY_ARCHITECTURE.md` |
| Commons (thiết kế, chưa dựng) | `docs/01-architecture/COMMUNITY_DATA_COMMONS.md` |
| SOT | `backend/app/sot/__init__.py` + `catalog_schema.py` |
| Kiểm thử | `docs/08-testing/TESTING.md` |
| Đồng thuận / pháp lý | `docs/04-legal/CONSENT_ENFORCEMENT.md`, `docs/04-legal/LEGAL_DOCUMENTS.md` |
| Quan trắc | `docs/06-operations/OBSERVABILITY_PLAN.md` |
| Sao lưu | `docs/06-operations/BACKUP_RESTORE.md` |
| Quyết định kiến trúc | `Extra_docs/01-architecture/adr/ADR-001..008` |
| Hạn chế đã biết | `docs/10-issues/KNOWN_ISSUES.md` (49 KB — mỏ vàng cho phần Hạn chế) |
