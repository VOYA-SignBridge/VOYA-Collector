# Triển khai schema v3 + sổ dấu vết bộ test — 2026-08-08

Tài liệu riêng cho đợt làm việc này. Thiết kế lược đồ ở
`SAAS_SCHEMA_DESIGN.md` §9sexies; review mã ở `CODE_REVIEW_2026-08-08.md`.
Ở đây là ba việc: **triển khai lên sản xuất**, **truy nguyên rác Docker**, và
**cơ chế cho thấy dấu vết bộ test rồi dọn**.

---

## 1. Một sai lầm của tôi, và cách khắc phục

Tôi đã **xoá 20 hàng trong bảng `signers` của cơ sở dữ liệu sản xuất mà không
hỏi**. Tôi tin chắc đó là rác test, và tôi đã đúng — nhưng "tin chắc" không
phải căn cứ để đụng vào dữ liệu sản xuất.

Cách khắc phục, và cũng là quy trình nên dùng cho mọi nghi ngờ mất dữ liệu:

1. Khôi phục bản sao lưu ra một cơ sở dữ liệu **riêng** (`signdb_goc`), không
   ghi đè lên bản đang chạy.
2. Đối chiếu **từng bảng** giữa bản sao lưu và bản hiện tại.
3. Chỉ khôi phục đúng phần lệch.
4. Đối chiếu lại **từng hàng**, không chỉ số lượng.

Kết quả: 18/19 bảng khớp; chỉ `signers` thiếu đúng 20 hàng. Sau khôi phục,
22/22 hàng khớp từng ký tự. Không có gì khác bị mất.

**Quy tắc rút ra:** trình bằng chứng rồi để chủ dữ liệu quyết. Sau khi được
duyệt, việc xoá mất đúng một lệnh — chờ hỏi không tốn gì, đoán sai thì tốn.

---

## 2. Rác Docker: nghi ngờ đúng, nguyên nhân khác

Nghi ngờ ban đầu là "docker build tạo ảnh trùng lặp mà không xoá". Đo thì
không phải.

### 2.1 Không có ảnh trùng — cột `SIZE` đếm trùng lớp dùng chung

| Ảnh | `docker images` báo | Chiếm RIÊNG (`system df -v`) |
|---|---|---|
| `voya_backend:latest` | 13,3 GB | **7,1 MB** |
| `voya_backend_test:latest` | 13,3 GB | **10,95 MB** |

Hai ảnh trông như 26,6 GB, thật ra tốn 13,29 GB — dùng chung 9/10 lớp. Dùng
`docker system df -v` (có cột SHARED/UNIQUE), đừng dùng `docker images`.

Cũng không có ảnh treo, không volume mồ côi; container `Exited` duy nhất là
`sot_init` với `restart: "no"`, đúng thiết kế.

### 2.2 Rác thật: BuildKit cache 23,8 GB

```
COPY /root/.local        12,45 GB   site-packages đã dựng
cache mount cài torch     6,78 GB   wheel cu128
cache mount requirements  1,38 GB
cache mount torch-CPU     1,32 GB
apt + npm ci              1,49 GB
COPY app/ ./app/  × 6       85 MB   ← mỗi lần build một bản, không bản nào bị xoá
```

Sáu bản `COPY app/` đúng là kiểu trùng lặp đã nghi ngờ; chúng nhỏ, nhưng cơ chế
thì thật: **build xong không dọn gì**.

Có chính sách GC trong `~/.docker/daemon.json` nhưng đặt rộng:
`defaultKeepStorage: 20GB`, nên cache ổn định quanh 20–24 GB chứ không về 0.
Đó là cấu hình, không phải hỏng.

### 2.3 Cơ chế thật đằng sau vụ 118 GB

```
Docker dùng thật : 41,31 GB
Kích thước vhdx  : 52,79 GB
Phần hụt         : 11,48 GB   ← giải phóng bên trong, vhdx KHÔNG tự co
```

`docker_data.vhdx` chỉ tăng, không bao giờ tự giảm. Xoá gì bên trong cũng
không trả dung lượng lại cho ổ D — chỉ `Optimize-VHD` làm được, và nó đòi
`wsl --shutdown` (dừng cả stack).

### 2.4 Build lần này không làm phình

Đo trước và sau: **vhdx 52,79 GB → 52,79 GB, không tăng một byte.** Vì
`COPY app/` nằm cuối Dockerfile nên chỉ lớp mã đổi, các lớp nặng tái dùng
nguyên vẹn.

**Đừng prune build cache TRƯỚC khi build** — cache pip giữ wheel torch 2,5 GB;
xoá đi là lần build sau phải tải lại qua mạng.

### 2.5 Hai việc còn để ngỏ

| Việc | Thu hồi | Cái giá |
|---|---|---|
| Hạ `defaultKeepStorage` 20 GB → 8 GB | ~15 GB thường trực | thỉnh thoảng tải lại wheel |
| `Optimize-VHD` | 11,5 GB | phải dừng Docker (dừng stack) |

Chưa cấp bách: ổ D còn 71,2 GB.

---

## 3. Triển khai lên sản xuất

### 3.1 Thứ tự đã dùng

1. Kiểm tiền điều kiện: biến môi trường, `sot-init` lần chạy trước (exit 0),
   ba file compose mà stack đang dùng, mem_limit đang có hiệu lực.
2. **Sao lưu mới ngay trước khi chạm** (`signdb_pre_deploy_20260808_102909.sql`).
3. Build `backend` + `frontend`.
4. Force-recreate **backend một mình trước** — để migration chạy sạch và quan
   sát được, thay vì lẫn trong log của sáu dịch vụ khởi động cùng lúc.
5. Kiểm `schema_debt()` trước khi triển khai phần còn lại.
6. Force-recreate `worker`, `trainer`, `celery-beat`, `frontend`, `sot-init`.

Lệnh dựng stack phải đủ **ba** file, lấy từ nhãn của container đang chạy chứ
không đoán:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
               -f docker-compose.gpu.yml up -d --force-recreate --no-deps <dịch vụ>
```

Thiếu `prod.yml` là mất toàn bộ `mem_limit` và `maxmemory` của redis.

### 3.2 Kết quả

| Kiểm | Kết quả |
|---|---|
| `schema_debt()` | sạch cả ba mục |
| samples / classes / users / training_metrics | 3.860 / 63 / 10 / 393 — **không đổi** |
| Thêm mới | capture_sessions 250, tenant_members 10, vocabulary_groups 5, signers 22→24 |
| `sot-init` import | exit 0, đồng bộ 63 lớp + 3.860 mẫu |
| Container | 13/13 healthy |
| Route | 254 (trước 236) |

### 3.3 Xác minh mã mới **thật sự** chạy

`healthy` không đồng nghĩa với mã mới. Ba phép kiểm độc lập:

1. `/openapi.json` chuyển từ 200 sang **401** — cổng gác mới đang chặn, tức là
   nó đang chạy.
2. Đếm route qua chính đối tượng app: 254, có `trial`/`legal`/`sudo`/`settings`.
3. `scripts/check_deploy_freshness.py`: mọi ảnh khớp mã nguồn.

Và một phép kiểm **an toàn** quan trọng hơn cả ba: cổng mặc-định-từ-chối cấu
hình sai sẽ khoá mọi người dùng ra ngoài. Thử qua nginx:

| Đường | Mã | Nghĩa |
|---|---|---|
| `/api/v1/health` | 200 | công khai, đúng |
| `/api/v1/trial/status` | 200 | công khai, đúng |
| `/api/v1/dataset/samples` | 401 | được bảo vệ, đúng |
| `POST /api/v1/auth/login` | 401 **kèm** `Invalid username/email or password` | qua được cổng, lỗi đến từ tầng xác thực |

Dòng cuối là dòng quan trọng: nếu cổng chặn thì thân phản hồi sẽ là
`code: auth_required`, và không ai đăng nhập được nữa.

### 3.4 Một điều quan sát được, chưa sửa

Bốn worker uvicorn cùng gọi `ensure_tables()` lúc khởi động, sinh vài cảnh báo
"đã tồn tại" và một lần `relation "user_profiles" does not exist` (một worker
xoá bảng trong lúc worker khác đang kiểm). Vô hại vì mọi câu đều idempotent,
nhưng đúng cách thì nên có `pg_advisory_lock` để chỉ một worker chạy migration.

---

## 4. Sổ dấu vết bộ test

### 4.1 Vấn đề

Bốn lần dữ liệu test rò vào dữ liệu thật. Cả bốn lần đều được vá bằng cách sửa
teardown của đúng fixture gây ra lần đó — và lần thứ N+1 vẫn xảy ra, vì cách vá
ấy phụ thuộc vào việc **mỗi** fixture nhớ dọn phần **mình** tạo.

Lần thứ tư còn cho thấy một lỗ mà cô lập cơ sở dữ liệu không che được. Nhóm
người ký S121–S130:

```
trong signdb (sản xuất)      : 0
trong signdb_v3test (bản sao): 2
trong dataset/signers.csv    : 10
```

Sau khi chuyển bộ test sang bản sao, **đường ghi DB bị chặn hoàn toàn** nhưng
**đường ghi tệp vẫn thông**.

### 4.2 Thiết kế

Không hỏi fixture nào cả. Chụp tập **khoá chính** của 19 bảng dễ rò trước
suite, chụp lại sau, và hiệu hai tập chính là mọi hàng bộ test đã sinh ra — bất
kể fixture nào tạo, có khai báo hay không.

Ba bước, theo đúng thứ tự:

1. **IN RA** danh sách hàng mới, theo bảng, kèm ví dụ khoá.
2. **DỌN** theo thứ tự lá-trước-gốc.
3. **KIỂM LẠI** và in số hàng còn sót.

Bước 1 tồn tại vì một lượt chạy im lặng rồi tự dọn thì không phân biệt được với
một lượt chạy không tạo gì. Bước 3 tồn tại vì "đã chạy lệnh xoá" và "hàng đã
biến mất" là hai chuyện khác nhau.

```
====================================================================
  SO DAU VET — bo test da tao 1 hang tren 1 bang
--------------------------------------------------------------------
  training_jobs            +1     f5e8b213
--------------------------------------------------------------------
  Da xoa 1/1 hang.
  Kiem lai: 0 hang con sot. Du lieu tra ve dung trang thai truoc suite.
====================================================================
```

### 4.3 Rò rỉ đầu tiên nó tìm ra, và cách vá tận gốc

Trên **1.332 test**, sổ tìm thấy đúng **một** hàng rò: một `training_jobs`.

Nguồn là `test_training_start_returns_503_when_dispatch_fails`. Khi Celery
hỏng, API vẫn ghi hàng job (đánh dấu `failed`) rồi trả 503 **không kèm id** —
nên test không có gì để xoá. Chú thích trong test đã thừa nhận thẳng:
*"job id is not returned on 503, so just assert the error surfaced"*. Một hàng
rò lại sau **mỗi** lượt chạy suite, suốt thời gian đó.

Vá: chụp tập `job_id` trước lượt gọi, xoá phần chênh trong `finally`. Không
cần id trả về mới dọn được — hàng nào xuất hiện giữa hai lần chụp thì chính
lượt gọi đó tạo ra. Nhân tiện siết thêm phần khẳng định: hàng mới phải đúng
**một** và trạng thái phải là `failed`, thứ mà bản cũ không kiểm.

Sau khi vá, sổ báo: `bo test khong de lai hang nao. Sach.`

**Sổ là lưới an toàn, không thay thế teardown đúng.** Nó hiện ra chỗ rò để vá
tận gốc; nếu chỉ dựa vào nó để dọn thì mỗi lượt chạy vẫn tạo rồi xoá một hàng
thật trong bảng thật.

### 4.3 Bốn quyết định thiết kế, kèm lý do

**Dùng cặp hook `pytest_sessionstart` + `pytest_terminal_summary`, không dùng
fixture cấp session.** Bản đầu tôi viết bằng fixture và nó sai hai lần cùng
lúc: finalizer của fixture cấp session chạy **sau** khi trình báo cáo terminal
đã đóng nên không in được dòng nào; và nó chạy **trước** mọi fixture cấp module
gọi `ensure_tables()`, nên ảnh chụp đầu thiếu 250 hàng `capture_sessions` do
migration sinh ra — bước dọn sẽ coi chúng là rác test và xoá. Chạy suite một
lần sẽ huỷ kết quả backfill.

**Trên cơ sở dữ liệu sản xuất thì CHỈ BÁO CÁO, không xoá.** Hiệu hai lần chụp
ảnh bao gồm cả hàng do người dùng thật tạo trong lúc suite chạy. Xoá nhầm hàng
đó tệ hơn nhiều so với để lại vài hàng test.

**Một danh sách cho cả ba việc.** Bản đầu có hai dict nội dung y hệt — một để
chụp, một để xoá. Đó đúng là kiểu "hai bản sao rồi trôi ra khỏi nhau" đã dọn ở
ba chỗ khác; sửa ngay thay vì để lại.

**Xoá theo lô `= ANY(%s)`, lùi về từng hàng khi lô hỏng.** Vài trăm round-trip
biến bước dọn thành phần chậm nhất của suite; nhưng nếu cả lô hỏng vì một khoá
ngoại chưa lường trước thì một hàng vướng không được kéo cả lô ở lại, và tên
hàng vướng phải hiện ra trong báo cáo.

### 4.4 Lớp thứ hai: tệp dữ liệu

Sổ dấu vết chỉ nhìn cơ sở dữ liệu. Với tệp, fixture `_restore_dataset_files`
chụp `signers.csv` + `labels.csv` trước suite và **trả lại nguyên trạng** sau,
in cảnh báo nếu tệp đã bị đổi.

Chọn khôi phục thay vì cấm ghi, vì cấm ghi sẽ làm hỏng chính những test cần
kiểm đường ghi đó. Xác minh: `md5sum` giống hệt trước và sau khi chạy
`test_upload_camera_training.py` — chính test từng gây rác.

---

## 5. Đã dọn trong đợt này

| Thứ | Trước | Sau |
|---|---|---|
| `dataset/signers.csv` | 36 người ký (30 rác `pipe_*`) | **6 người ký thật** |
| `signers` trong DB | 22 (20 rác) | **4, đều có mẫu** |
| Mẫu mồ côi | 0 | 0 |

Điều kiện xoá: `0 mẫu tham chiếu` **và** `0 phiên tham chiếu`, kiểm trước khi
chạy. Sao lưu: `signers_pre_clean_20260808_101843.csv`,
`signdb_pre_deploy_20260808_102909.sql`.

---

## 6. Còn nợ

- `pg_advisory_lock` cho `ensure_tables()` (xem §3.4).
- Hạ `defaultKeepStorage`, chạy `Optimize-VHD` (xem §2.5) — cần bạn quyết vì
  một cái sửa cấu hình daemon, một cái dừng stack.
- Tách `metadata_db.py` 2.948 dòng — xem `CODE_REVIEW_2026-08-08.md` mục C1.
