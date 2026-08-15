# Nhật ký gỡ merge `feature/vocab-schema-v2` → `deploy_ctu_ver-2.2.1`

Cập nhật 2026-08-01. Đây là bản ghi **đã làm gì và vì sao**, để phiên sau (hoặc
người khác) không phải dựng lại lập luận. Chi tiết từng chủ đề nằm ở các tài
liệu riêng cùng thư mục; ở đây chỉ tóm tắt và nối chúng lại.

| tài liệu | nội dung |
|---|---|
| [`DATASET_SYNC_DEPLOY.md`](../06-operations/DATASET_SYNC_DEPLOY.md) | gộp dataset dev ↔ deploy, danh tính người ký, lỗi sync DB |
| [`HARDCODED_VOCABULARY_AUDIT.md`](../10-issues/HARDCODED_VOCABULARY_AUDIT.md) | 7 bản danh sách gắn sẵn, 2 chỗ bịa giá trị, đợt 1 đã làm |
| [`DIALECT_LIFECYCLE.md`](../02-data/DIALECT_LIFECYCLE.md) | 10 tầng lưu trữ một `dialect`, 3 tầng bất biến, cơ chế gộp |
| [`MULTITENANT_PREP.md`](MULTITENANT_PREP.md) | nền hai mặt phẳng, những chỗ còn giả định một tenant |
| [`AUTH_TOKEN_LIFECYCLE.md`](../03-security/AUTH_TOKEN_LIFECYCLE.md) | 4 lỗ hổng vòng đời token, chưa sửa |
| [`SAMPLE_OWNERSHIP.md`](../02-data/SAMPLE_OWNERSHIP.md) | `auth_user_id` mất khi đi qua CSV, thao tác hàng loạt, `promoted_at` mồ côi |
| [`REGISTRY_ARCHITECTURE.md`](../01-architecture/REGISTRY_ARCHITECTURE.md) | ba mặt phẳng Community/Tenant/Artifact, version bất biến + hash, bỏ fallback |

---

## 1. Tiến độ gỡ xung đột

| nhóm | trạng thái |
|---|---|
| A–D backend (24 file) | **xong** |
| E — router nghiệp vụ (6) | **đang làm** |
| F — realtime service (4) | chờ |
| G — tts, email, test_schema_evolution (3) | chờ |
| `processed/` (14) | chờ — đang chặn 4 research suite |
| frontend (34) | chờ — chặn đợt 2 của registry |
| gốc repo (4) | chờ — `docker-compose.yml` chặn mọi test cần DB/Redis |

Còn **65 file** xung đột. Test backend: **321 pass / 33 fail / 14 error** —
xem §4, gần như toàn bộ phần đỏ là do merge chưa xong chứ không phải code sai.

### Nguyên tắc gỡ đã dùng

`git checkout --ours` lấy **nguyên khối stage-2** và **vứt bỏ phần git đã tự
merge sạch từ nhánh kia**. Nó suýt làm mất 20 dòng cấu hình ở `config.py` và
131 dòng ở `dataset_manager.py`. Từ đó mọi file đều gỡ **theo từng hunk**, và
script `check_automerge.py` được viết để đo trước xem mỗi lựa chọn mất bao nhiêu dòng.

---

## 2. Lỗi thật tìm được khi gỡ (không phải xung đột, là bug)

Xếp theo mức nghiêm trọng:

| # | lỗi | hậu quả nếu để nguyên |
|---|---|---|
| 1 | `db.py` chặn sync bằng **so sánh số lượng** `db_count < csv_count` | Postgres giữ hàng xoá mềm nên điều kiện **vĩnh viễn sai** sau lần xoá đầu tiên → không dòng mới nào được sync nữa. Đây là "lần nào sync cũng không cập nhật database" |
| 2 | `metadata_db` `SELECT s.username` trên bảng `samples` **không có cột đó** | trang Thùng rác lỗi query — cả bản chung lẫn bản theo người dùng |
| 3 | `.gitignore` có `*.json` bao trùm | **2 file config biến mất**: `legacy_signer_mapping.json` (không phép gộp người ký nào có hiệu lực) và `legacy_vocabulary_mapping.json` (mọi lớp mới sinh ra với `recognition_profile` rỗng → split lọc theo profile bỏ qua trong im lặng) |
| 4 | script đồng bộ ghi `recognition_profile = dialect` | 7/63 lớp vi phạm `validate_label_v2`; `spa` không phải profile hợp lệ |
| 5 | `dataset_samples.py` mất bản vá thứ tự dispatch Drive | `NameError` mỗi lần lưu mẫu (`pending_single_upload` chưa gán) |
| 6 | `activity.py` import `LOGIN_MAX_ATTEMPTS` đã bị xoá, nằm trong `try/except: pass` | cảnh báo dò mật khẩu cho admin **chết âm thầm** |
| 7 | **hai** `normalize_dialect` cùng file, cái sau che cái trước | bản che thiếu `bang-chu-cai`; docstring bản bị che ghi "this is the only implementation" |
| 8 | `REQUIRED_COLUMNS` (SOT) thiếu 14 cột v2 mà upsert có ghi | reader thiếu cột **qua được bước verify rồi mới chết giữa lúc import** |
| 9 | `nginx.conf` bản vocab-v2 dùng `$remote_addr` | mọi người dùng gộp về IP của Cloudflare → danh sách chặn IP của admin chặn tất cả |

---

## 3. Đã xây thêm

### 3.1 Throttle đăng nhập + giới hạn đăng ký

Thay khoá cứng "sai 5 lần khoá 15 phút" bằng: **10 lần sai đầu miễn phí**, sau
đó chờ tăng dần 30s → 120s → 300s → 900s, khoá theo **cặp (IP, tài khoản)**.
Khoá theo cặp là điều ngăn chính cơ chế này trở thành vũ khí — biết tên đăng
nhập của ai đó không còn khoá được họ, vì IP của kẻ tấn công mới là bên bị chờ.

Bộ đếm theo IP **chỉ quan sát** tới ngưỡng cứng: một IP NAT/trường học chở rất
nhiều người dùng hợp lệ. `client_ip()` **bỏ qua header** trừ khi TCP peer nằm
trong `TRUSTED_PROXIES`; Cloudflare **nối thêm** vào XFF nên hop trái nhất do
kẻ tấn công kiểm soát → đọc từ phải sang trái.

15/15 test. 16 biến đã vào `.env.example`, đối chiếu tự động với `rate_limit.py`.

### 3.2 Sửa sync CSV → Postgres

So sánh **tập khoá chính** thay vì số đếm. Thêm log rõ `CSV n, DB m -> thêm k`,
cảnh báo khi DB có hàng mà CSV không có, và cờ `--full-resync` /
`VOYA_DB_FULL_RESYNC=1` để đẩy cả hàng **đã sửa** (cần cờ riêng vì không CSV nào
có `updated_at` để so). 14 test, không cần DB.

### 3.3 Nền multitenant

Bảng `tenants`, cột `tenant_id` trên 6 bảng (`DEFAULT 'default'` nên chưa đổi
hành vi), và **đổi phạm vi hai unique index** sang theo tenant. Cái sau là phần
đắt nếu làm muộn: `class_idx` **chính là ô đầu ra của model**, duy nhất toàn cục
sẽ ép tenant thứ hai bắt đầu từ 64 với 63 ô chết.

### 3.4 Danh mục phương ngữ / profile — đợt 1

Postgres làm nguồn sự thật (ngược với labels/samples), vì **chỉ FK mới cưỡng
chế được**. 4 bảng + `app/vocabulary_registry.py` + `routers/vocabulary.py` +
task gộp `app/catalog_migrations.py` + 14 test.

`dialect_id` **bất biến** (là tên thư mục, tên checkpoint, khoá trong manifest
split); `display_name` giữ dấu và sửa thoải mái. Từ chối một phương ngữ chờ
duyệt **bắt buộc kèm phương ngữ đích để gộp** — nếu không, số mẫu người dùng đã
thu sẽ mồ côi.

### 3.5 Danh tính người ký

`Tram = Trâm → S003`, `Thungan = Thu Ngân = Ngan → S006`, `Trân → S001` là
**người khác** (ghi vào `explicitly_not_merged` ở cả hai file — hai chuỗi chỉ
khác một dấu, người sau rất dễ "sửa" nhầm thành một). 15 chuỗi thô → 12 nhóm.
`signers.py` cấp id mới từ **S101** để không đụng không gian tên legacy.

---

## 4. Vì sao test còn đỏ (không phải lỗi code)

| số | nhóm | nguyên nhân |
|---|---|---|
| 14 | `test_alphabet_slug` | `routers/classes.py` còn marker |
| 9 | ERROR cấp file | marker ở `email_service.py`, `classes.py`, `dataset.py`… |
| 8 | `test_sot_admin` | cần Postgres — không có khối `ports:`, chỉ với tới từ `voya_network` |
| 6 | `test_sync_tasks`, `test_disk_watermark` | cần Redis, cùng lý do |
| 4 | `test_research_suites` | marker ở `processed/` |
| 4 | `test_deploy_fixes` | marker ở `email_service.py` |
| 1 | `test_logging_config` | `docker-compose.yml` còn marker → YAML không parse |
| 1 | `test_training_smoke` | pass khi chạy riêng, phụ thuộc thứ tự |

Kết luận: gỡ nốt xung đột mở khoá phần lớn; phần còn lại **phải chạy trong
container**, chạy trên host là sai môi trường chứ không phải sai code.

---

## 5. Việc còn nợ, theo thứ tự

1. Nhóm E, F, G, `processed/`, frontend, gốc repo.
2. `nginx.conf`: **bắt buộc lấy HEAD** (`$rl_client` từ `$http_cf_connecting_ip`).
3. ~~Sau khi gỡ `docker-compose.yml`: seed danh mục → cắm FK → sync~~ **XONG
   2026-08-01.** Đã gỡ `docker-compose.yml` (6 xung đột lấy HEAD + gộp khối
   `realtime_service` bị trùng key), sync 168 mẫu + 7 lớp, DROP bảng `dialects`
   cũ, seed 9 phương ngữ, cắm FK **composite** `(tenant_id, dialect)` cho cả
   `classes` lẫn `samples`. Lưu ý: FK một cột `dialects(dialect_id)` như ghi ở
   bản trước **không cắm được** — khoá chính là `(tenant_id, dialect_id)`.
   Xem [`SAMPLE_OWNERSHIP.md`](../02-data/SAMPLE_OWNERSHIP.md) mục 4.
4. Đợt 2 của registry: frontend nạp từ `/vocabulary/registry`, xoá 3 bản gắn sẵn,
   nút tạo phương ngữ ở Thư viện nhãn, T4.
5. Mang dataset sang máy deploy — chạy SQL ánh xạ `class_uid` **trước** khi sync.
6. Sau merge: promtail structured metadata, giới hạn API, metrics/alerts, và 4
   lỗ hổng vòng đời token.
