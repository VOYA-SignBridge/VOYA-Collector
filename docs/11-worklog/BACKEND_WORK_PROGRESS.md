# Backend — nhật ký tiến độ

**Cập nhật:** 2026-08-07
**Kèm theo:** [BACKEND_WORK_PLAN.md](BACKEND_WORK_PLAN.md) — kế hoạch; tài liệu này ghi *đã làm được gì và tìm thấy gì*
**Tham chiếu kỹ thuật A2+A3:** [TENANT_ISOLATION.md](../01-architecture/TENANT_ISOLATION.md) — kiến trúc, luồng nghiệp vụ, vận hành
**Mốc chặn:** sách luận văn 13/08/2026 (6 ngày), bảo vệ 18–19/08/2026

---

## 1. Trạng thái

| Mã | Việc | Trạng thái | Ghi chú |
|---|---|---|---|
| **A1** | `tenant_id` vào SOT | ✅ **xong, đã triển khai** | Backfill đã chạy + xác minh; stack đã rebuild; xem §7 |
| **A2** | Role ứng dụng không-superuser | ✅ **xong (code+DB), chờ cutover** | `voya_app` đã cấp; RLS đã cắn thật; xem §9 |
| **A3** | RLS 3 bảng + tenant context | ✅ **xong, chờ cutover** | 6/6 đột biến bị bắt; xem §9.2–9.4 |
| **A4** | Phân vùng lưu trữ theo tenant | ✅ **xong** | Chia theo *tenant*, không theo *thời điểm*; xem §9.5 |
| **B1** | `torch.load(weights_only=False)` × 5 | ✅ **xong** | Gom về `checkpoint_io`, thêm chặn traversal |
| **B2** | `/realtime/predict` rate limit | ✅ **xong** | 600/phút/actor |
| **B3** | Rate limit các đường ghi | ✅ **xong** | upload / training / catalog |
| **B4** | Router chết + mount thiếu guard | ✅ **xong** | Bỏ 2 import treo; `/jobs/{id}` cần đăng nhập |

**Còn nợ trước khi coi là hoàn tất:** bước cutover — đổi `DATABASE_URL` sang `voya_app` và
`DB_STRICT_ISOLATION=1`, rebuild image, force-recreate. Xem §9.7. Cho tới lúc đó, deploy đang
chạy **vẫn nối bằng `admin`**, nên policy đã cài nhưng chưa có hiệu lực trên máy thật.

**Trạng thái git:** merge vẫn đang dở (`MERGE_HEAD` còn), **chưa commit lần nào**. Toàn bộ
A1–A4 và B1–B4 đang nằm ở working tree.

---

## 2. A1 — đã làm gì

### 2.1 Một nguồn cho danh tính tenant

`backend/app/tenancy.py` (mới). Trước đó chuỗi `'default'` là literal trần **13 chỗ** trong DDL của `metadata_db.py` và không ở đâu khác; A1 đưa `tenant_id` vào cả CSV nên con số đó sẽ vượt 20 ở 4 module.

Module cung cấp:

| Ký hiệu | Vai trò |
|---|---|
| `DEFAULT_TENANT_ID` | Tenant khởi tạo, có validator chặn ngay lúc import |
| `TENANT_COLUMN` | Tên cột, để header CSV / khoá dict / danh sách cột SQL không tự phát âm khác nhau |
| `is_valid_tenant_id` | Kiểm dạng, **không** strip |
| `normalize_tenant_id` | Đường **GHI CSV**: vắng → tenant khởi tạo |
| `optional_tenant_id` | Đường **UPSERT DB**: vắng → `None` |
| `tenant_id_of` | Đọc tenant ra khỏi một dòng CSV / payload |

**Cố ý không phải biến môi trường.** `tenant_id` là khoá ngoại và được ghi vào `dataset/samples.csv` — thứ được nhân bản lên Drive và Sheets. Nếu đổi được qua env sau khi đã có dữ liệu thì mọi lần ghi sau sẽ rơi vào một tenant mà dữ liệu cũ không chia sẻ, **tách đôi kho ngữ liệu mà không báo lỗi**, vì cả hai nửa đều hợp lệ khi xét riêng. Đổi tên tenant khởi tạo là một cuộc di trú dữ liệu, không phải một dòng cấu hình.

### 2.2 Phân biệt "vắng mặt" với "mặc định" — phần chịu lực của A1

Đây là chỗ dễ hỏng nhất và nó suýt hỏng.

Nếu tầng upsert coi *"dòng này không nói gì về tenant"* là *"dòng này thuộc tenant khởi tạo"*, thì mỗi lần đồng bộ lúc khởi động từ một CSV do máy cũ ghi sẽ **ghi đè toàn bộ hàng của tenant B về `default`** — đúng cái mất phân vùng mà A1 sinh ra để chặn, chỉ là tái tạo ở tầng thấp hơn một bậc.

Nên:

```sql
-- INSERT: dòng mới thật sự không có tenant thì thuộc tenant khởi tạo
COALESCE(%(tenant_id)s, 'default')

-- ON CONFLICT: đọc THAM SỐ, không đọc EXCLUDED
tenant_id = COALESCE(%(tenant_id)s, samples.tenant_id)
```

`EXCLUDED.tenant_id` là giá trị **sau khi** mệnh đề VALUES đã thay tenant khởi tạo vào chỗ NULL — dùng nó ở đây thì mọi dòng đều bị viết lại thành `default`. Đọc tham số mới giữ được phân biệt "không có ý kiến" / "thuộc về X".

### 2.3 Bảng thay đổi

| File | Thay đổi |
|---|---|
| `app/tenancy.py` | **mới** — hằng số + 4 primitive + validator lúc import |
| `app/storage/metadata_db.py` | 13 literal → 1 nguồn; 3 câu upsert thêm cột + ngữ nghĩa vắng-mặt; 3 tuple khoá; `list_active_samples` thêm cột |
| `app/dataset_samples.py` | `SAMPLE_FIELDS` +1; `ensure_samples_column(column, fill=)`; chốt chặn dòng dư ô; `append_sample_row` đóng dấu; phép chiếu DB→CSV ép tenant |
| `app/dataset_manager.py` | `LABEL_FIELDS` +1; `ClassMetadata.tenant_id`; nâng header có backfill; `append_label_row` đóng dấu |
| `app/raw_uploads.py` | `RAW_UPLOAD_FIELDS` +1; `_upgrade_raw_uploads_header()` mới; `append_raw_upload_row` đóng dấu |
| `app/catalog_sync.py` | 2 phép chiếu DB→CSV (trash class, trash sample) ép tenant |
| `app/db.py` | Migration `samples.csv` + `labels.csv` chạy **trước** sync lúc boot |
| `app/sot/catalog_schema.py` | `REQUIRED_COLUMNS` +`tenant_id` cho cả 3 bảng |
| `tests/test_tenant_sot_column.py` | **mới** — 197 test |
| `tests/test_sample_ownership.py` | Sửa 1 test ghim sai bất biến |
| `tests/conftest.py` | Thêm đường `/testvideos` để khử một skip |
| `tests/test_features_root_override.py` | Bỏ đường tuyệt đối `/dataset/...` → khử skip còn lại |

**Mở rộng phạm vi có chủ đích:** kế hoạch nói "2 CSV", thực tế làm 3. `raw_uploads` là bảng thứ ba mà sync lúc khởi động ghi vào và là bảng thứ ba A3 sẽ đặt RLS lên; bỏ sót nó thì lỗi ghi-đè-âm-thầm vẫn sống ở đúng một trong ba.

---

## 3. Lỗ hổng đã tìm thấy

Chia theo nguồn, vì hai loại nói lên hai điều khác nhau.

### 3.1 Trong mã có sẵn

| # | Lỗ | Bằng chứng | Xử lý |
|---|---|---|---|
| 1 | **`list_active_samples()` không SELECT `tenant_id`** | Phép chiếu điền `""` cho cột câu SQL không trả về | Đã vá cả câu SQL lẫn phép chiếu |
| 2 | **2 phép chiếu DB→CSV ở `catalog_sync`** cùng lỗ, trên đường **trash/restore** | `_db_class_row_to_label_row`, `_db_sample_row_to_csv_row` | Đã ép tenant |
| 3 | **`append_raw_upload_row` ghi 16 cột vào file header 15 cột** | `DictWriter` chỉ phát header khi file rỗng | Thêm `_upgrade_raw_uploads_header()` |
| 4 | **`admin` là superuser + BYPASSRLS** | `pg_roles` | ⬜ chưa xử lý — đây là A2 |
| 5 | **Không có ngữ cảnh tenant ở đâu cả** | grep `current_setting`/`SET LOCAL` = 0 kết quả | ⬜ A3 |
| 6 | **`torch.load(weights_only=False)` × 5** | `training.py` ×4, `training_tasks.py` ×1 | ⬜ B1 |
| 7 | **Rate limit chỉ phủ `auth.py`** | `upload.py` — đường đắt nhất — không có hạn mức | ⬜ B3 |
| 8 | **2 router import mà không mount** | `experiments.py`, `dataset_exporter.py` | ⬜ B4 |

Lỗ 1–3 cùng một họ và cùng một cách sinh ra: **một phép chiếu điền `""` cho mọi cột nguồn không cung cấp**. Cột nào mà `""` có nghĩa "chưa biết" thì vô hại; `tenant_id` thì `""` nghĩa là *chưa gán ai*, và nó được ghi ngược vào nguồn sự thật. Đã ép giá trị ở cả ba nơi để một lần sửa câu SQL sau này không mở lại lỗ.

### 3.2 Trong chính công việc A1 của tôi

Ghi lại vì chúng cho thấy chỗ nào dễ sai, không phải để tự trách.

| # | Sai | Phát hiện bằng | Hậu quả nếu lọt |
|---|---|---|---|
| 1 | Định dùng fallback `'default'` ở tầng upsert | Tự soát khi viết `optional_tenant_id` | **Tái tạo đúng lỗi A1 phải chặn** |
| 2 | `%(tenant_id)s` nằm trong comment SQL | Grep `%` trong comment | psycopg2 nội suy cả trong comment |
| 3 | `TENANT_COLUMN` trong 3 tuple `_*_DB_KEYS` | `test_sot_schema_coverage` đỏ | Bộ kiểm tra đọc tuple như **văn bản nguồn** (cố ý, để chạy trên checkout trần) nên đọc ra tên định danh |
| 4 | `REQUIRED_COLUMNS` thiếu `tenant_id` | cùng test | Máy đọc SOT **qua bước verify rồi chết giữa lúc import** |
| 5 | **`$` trong regex Python** | Sở thú kiểu dữ liệu | Xem §3.3 |
| 6 | **Không kiểm kiểu** | Sở thú kiểu dữ liệu | Xem §3.3 |
| 7 | **Một test giả** | Tự soát | Xem §4.1 |
| 8 | Chạy container thiếu 3 biến Redis | 6 test đỏ oan | Suýt đi sửa 3 test lành |
| 9 | Lấy số file `.npz` theo trí nhớ (3.871) | Đếm lại: **8.784** | Sai số trong tài liệu |

### 3.3 Hai lỗ chỉ lộ ra nhờ kiểm nhiều kiểu dữ liệu

**`$` khớp cả trước newline cuối chuỗi.**

```
'truong-b\n'   với ^...$  -> True     <-- nhận nhầm
'truong-b\n'   với \A..\Z -> False
```

Một tenant id có newline ở cuối sẽ: phá vỡ dòng CSV nó được ghi vào; từ A4 tạo một thư mục có newline trong tên; và **so sánh khác `"truong-b"`, tức là một phân vùng riêng biệt nhưng nhìn y hệt trong mọi dòng log**. Đã đổi sang `\A…\Z`, kèm ghi chú vì sao.

Việc strip vẫn nằm ở `normalize_tenant_id` — ô CSV do người sửa tay hay có khoảng trắng thừa, file ghi kiểu CRLF trả về `\r`. Cả hai đều là *cùng một tenant* nên được sửa; còn dạng thô thì validator vẫn từ chối, và đó là thứ chặn giá trị chưa-strip trở thành phân vùng của riêng nó.

**`str(123)` = `"123"`, khớp bảng chữ cái cho phép.** Một số nguyên từ JSON body sẽ **âm thầm thành tenant "123"**. Giá trị đến các hàm này là: ô CSV (luôn `str`), hàng psycopg2 (`str` hoặc `None`), và **thân request JSON (bất kỳ kiểu gì)** — chỉ cái cuối mới đưa được `int`/`bool`/`list` vào. Nay chỉ nhận `str` hoặc `None`, còn lại `TypeError`.

---

## 4. Test — phương pháp và bằng chứng

### 4.1 Một test giả đã bị loại

```python
assert TENANT_COLUMN in inspect.getsource(list_active_samples)   # VÔ DỤNG
```

Xoá `tenant_id` khỏi câu SELECT thì test này **vẫn xanh**, vì chính đoạn comment phía trên câu truy vấn có chứa từ đó. Đã thay bằng: gọi thật `list_active_samples()`, tìm hàng của tenant B, đọc giá trị trả về.

Nguyên tắc rút ra, ghi ở đầu file test: **không assert lên văn bản nguồn ở chỗ quan sát được hành vi.**

### 4.2 Ba nguyên tắc của bộ test

1. **Không assert văn bản nguồn khi quan sát được hành vi.**
2. **Mỗi hàm nhận đầu vào đi qua một sở thú kiểu dữ liệu**, không phải một chuỗi đẹp — 8 kiểu không-phải-chuỗi, 19 chuỗi sai dạng, 7 hợp lệ, 6 rỗng. Chính nó lôi ra §3.3.
3. **Kịch bản gốc có nhóm đối chứng âm.** `TestRebuildFromCsv` chạy đúng đường `sync_missing_data_on_startup` hai lần: CSV **có** cột → tenant B sống sót; CSV **không** có cột → tenant B **bị mất, và test khẳng định điều đó**. Nhóm đối chứng âm làm test dương không thể xanh vì lý do vô can, đồng thời ghi lại bằng mã cái giá của việc bỏ cột.

Dữ liệu CSV trong test là dữ liệu thật chứ không phải `"abc"`: nhãn ở đây là tiếng Việt đi qua Google Sheets, nên có ca dấu phẩy, dấu nháy kép, **xuống dòng trong ô**, dấu tiếng Việt, khoảng trắng bao quanh.

### 4.3 Kiểm chứng bằng đột biến

Phá từng thứ bộ test tuyên bố bảo vệ, xem có đỏ không. Script: `scratchpad/mutate.py` (tự khôi phục file kể cả khi lỗi).

| Đột biến | Phá | Kết quả |
|---|---|---|
| M1 | "vắng mặt" → trả `default` | 9 đỏ |
| M2 | `ON CONFLICT` đọc `EXCLUDED` | 2 đỏ |
| M3 | Bỏ `tenant_id` khỏi SELECT reconcile | 2 đỏ |
| M4 | Migration điền rỗng | 10 đỏ |
| M5 | Bỏ kiểm kiểu | 16 đỏ |
| M6 | Neo regex `\Z` → `$` | 1 đỏ |
| M7 | Writer thôi đóng dấu | 2 đỏ |
| M8 | Bỏ cột khỏi header `samples.csv` | 6 đỏ |
| M9 | Bỏ chốt chặn dòng dư ô | 2 đỏ |

**9/9 bị bắt.** Trước khi sửa §4.1, M3 **sống sót** — đó là lý do phải chạy phép kiểm này chứ không tin vào màu xanh.

### 4.4 Số liệu

| Mốc | Kết quả |
|---|---|
| Trước A1 | 710 qua · 1 skip |
| Sau A1, bộ test A1 bản đầu (65 test) | 774 qua · 2 skip · 0 hỏng |
| Sau khi siết test + khử skip video | **907 qua · 1 skip · 0 hỏng** |
| Sau khi khử nốt skip cuối | *(xem §4.4.1)* |
| File test A1 | **197 test** |

#### 4.4.1 Cả hai skip đều là lỗi đường dẫn, không phải thiếu dữ liệu

Điểm chung: **một đường dẫn tuyệt đối đúng với container `backend` nhưng sai với container test.** Suite chạy trong `voya_backend_test` chỉ mount repo ở `/src`; mọi thứ nằm ngoài đó là vô hình.

| Skip | Nguyên nhân | Dữ liệu có trên máy? | Cách khử |
|---|---|---|---|
| `test_video_pipeline` — trích xuất video thật | conftest dò `E:/CTU_ProjectOutside/Videos` (đường Windows) và `dataset/raw_videos/` (**rỗng vì ta đã xoá 14 video**) | **Có — 4.362 clip** | Thêm đường `/testvideos` vào conftest + mount |
| `test_features_root_override:119` — tích hợp ablation zfix | Test hardcode `/dataset/features_zfix/v2`, là chỗ volume rơi vào trong container *backend* | **Có — `dataset/features_zfix/v2`** | Ưu tiên đường tương đối repo, rồi mới đến đường tuyệt đối |

Cả hai đều **skip trên đúng cái máy duy nhất chạy được chúng** — dạng skip tệ nhất, vì nó im lặng và trông như "môi trường này không hỗ trợ".

Clip test đặt ở `E:\CTU_ProjectOutside\voya_test_clips`, **ngoài repo, cố ý không đưa video vào cây git** vì vừa xoá dữ liệu có mặt người. Test đó nay chạy MediaPipe thật trên clip thật.

### 4.5 Lệnh chạy đúng

Thiếu 3 biến Redis là 6 test đỏ oan — conftest `setdefault` chúng về `localhost`, mà trong container thì localhost không có Redis.

```bash
docker run --rm --network voya-collector_voya_network \
  -e DATABASE_URL=postgresql://admin:admin@postgres:5432/signdb \
  -e REDIS_URL=redis://redis:6379/0 \
  -e CELERY_BROKER_URL=redis://redis:6379/0 \
  -e CELERY_RESULT_BACKEND=redis://redis:6379/0 \
  -e TTS_REDIS_URL=redis://redis:6379/0 \
  -v "E:\CTU_ProjectOutside\VOYA-Collector:/src" \
  -v "E:\CTU_ProjectOutside\voya_test_clips:/testvideos" \
  -w /src voya_backend_test:latest \
  python -m pytest backend/tests -q -rs
```

---

## 5. Dang dở

### 5.1 Thuộc A1 — đã hoàn tất

Backfill và triển khai đã xong, xem §8. Không còn mục nào treo trong A1.

### 5.2 Cố ý không làm (và vì sao)

- **`list_active_samples()` vẫn thiếu** `auth_user_id`, các cột chất lượng, `signer_id`, `normalization_version`. Đường reconcile vốn đã lossy ở những cột đó từ trước A1; mở rộng câu truy vấn là một thay đổi riêng với bề mặt test riêng. **Đã ghi lại thay vì lặng lẽ sửa kèm.**
- **Sheets export:** header là `SAMPLE_FIELDS + ["deleted_at"]`, nên `deleted_at` dịch sang phải một cột. Nó **vẫn là cột cuối** — bất biến thật sự là "cột đánh dấu nằm cuối", và bất biến đó còn nguyên. Ai đọc theo chỉ số cột cứng sẽ vỡ; ai đọc theo tên thì không.
- **`dialect_mapping_reclassifier.py`** ghi bằng `SAMPLE_FIELDS`; chỉ chạy tay và chỉ sau khi migration đã chạy. Rủi ro thấp, ghi nhận.
- **Đổi tên bảng `community_*`**, Community Data Commons, consent, reuse detection, lật `hands126_v2` — vẫn trong danh sách *không đụng trước 13/08*.

### 5.3 Chưa bắt đầu

A2 → A3 → A4 theo đúng thứ tự trong [BACKEND_WORK_PLAN.md](BACKEND_WORK_PLAN.md). **A2 phải xong trước A3**, nếu không A3 chỉ tạo ra bằng chứng giả.

---

## 6. Quyết định đã chốt

| Quyết định | Lý do |
|---|---|
| `DEFAULT_TENANT_ID` là hằng, **không** phải env | Đổi qua env sau khi có dữ liệu sẽ tách đôi kho ngữ liệu mà không báo lỗi |
| Vắng mặt ≠ mặc định, ở tầng upsert | Nếu không thì mỗi lần sync từ CSV cũ sẽ cướp dữ liệu tenant khác |
| Giá trị sai dạng thì **raise**, không tự sửa | Sửa im lặng biến một lỗi gõ thành phân vùng mới |
| Dòng dư ô thì **raise**, không migrate | `db.py` bắt exception và ghi log → boot tiếp tục, catalog nguyên vẹn; ghi lệch SOT tệ hơn nhiều |
| Tên cột là literal trong 3 tuple `_*_DB_KEYS` | Một bộ kiểm tra đọc chúng như văn bản nguồn; thứ thật sự cần một-nguồn là **giá trị** tenant |
| Clip test để **ngoài** repo | Vừa xoá dữ liệu có mặt người; đưa video vào cây git là đi ngược lại |
| Mở rộng A1 sang `raw_uploads` | Bỏ sót thì lỗi ghi-đè-âm-thầm còn sống ở đúng 1 trong 3 bảng sync |

---

## 7. Triển khai A1 — 2026-08-07

### 7.1 Trình tự đã chạy

| Bước | Kết quả |
|---|---|
| Suite đầy đủ | **908 qua · 0 skip · 0 hỏng** |
| Sao lưu 3 CSV kèm SHA256 | `voya_backups/pre_A1_backfill_20260807-013621` |
| Dừng 3 writer (`backend`, `worker`, `celery-beat`) | beat chạy reconcile định kỳ và **có** ghi vào `samples.csv` |
| Backfill | `samples.csv` 32→33 cột · `labels.csv` 19→20 · `uploads.csv` 15→16 |
| Xác minh đối chiếu bản sao lưu | 3.860 + 63 + 0 dòng giữ nguyên; **mọi ô cũ byte-identical**; thứ tự cột cũ không đổi; tenant đồng nhất `default` |
| Rebuild image + recreate 5 service | Giữ đủ 3 compose file (`yml` + `prod` + `gpu`) |
| Boot mới | Migration nhận cột đã có → no-op; `STARTUP_SYNC: CSV 3860 = DB 3860`, ghi 0 hàng |
| Sức khoẻ | 12 healthy + `sot_init` exited(0) đúng thiết kế |

Việc xác minh **đối chiếu từng ô với bản sao lưu**, không chỉ đếm cột — migration ghi lại toàn bộ file nên phải chứng minh nó không tái mã hoá gì.

### 7.2 Lỗ hổng lớn phát hiện lúc triển khai: **xoá không bền**

Ngay sau khi recreate stack, 14 dòng `raw_uploads` đã xoá hôm 06/08 **xuất hiện lại trong Postgres**.

```
voya_sot_init: [sync] applied version=Ver4_05082026 signed_by=desktop-admin
               upserted={'classes': 63, 'samples': 3860, 'raw_uploads': 14}
```

**Cơ chế.** Snapshot SOT đã ký ngày 05/08 vẫn chứa 14 dòng đó. Cơ chế đồng bộ là **chỉ-điền, không-bao-giờ-xoá**, và `sot-init` chạy mỗi lần khởi động stack. Nên mọi thao tác xoá đều bị hoàn tác ở lần khởi động kế tiếp.

**Không phải do A1.** Đây là tính chất có sẵn của kiến trúc SOT; A1 chỉ làm nó lộ ra vì phải restart stack. Bộ nhớ dự án đã ghi tính chất này từ trước ("sync không xoá nhưng ghi đè lùi") — cái thiếu là **nối nó với hệ quả: một lần xoá không sống qua lần boot sau**.

**Thiếu sót trong khâu kiểm của tôi.** Lần xác minh trước tôi kiểm 5 nơi + Drive + backup + container đang chạy và kết luận "đã xoá sạch". Kết luận đó đúng **tại thời điểm đó**, nhưng tôi **không kiểm nội dung snapshot SOT như một nguồn phục hồi**. Danh sách "5 nơi" đã thiếu nơi thứ sáu.

**Thứ tự sửa bị đảo so với trực giác.** `_gather_csv_sources()` trong `app/sot/cli.py` dựng snapshot từ **DATABASE**, không từ file CSV:

```python
rows = db._fetch_all(f"SELECT {cols} FROM {table} WHERE deleted_at IS NULL ORDER BY {keys_[0]}")
```

Publish trước khi xoá sẽ publish lại đúng 14 dòng đó. Nên: **xoá ở DB trước → publish sau**.

**Đã xử lý:**

1. Ghi biên bản 14 dòng (`dataset/backups/raw_uploads_resurrected_20260807-014754.json`, 10,9 KB, chỉ metadata)
2. `DELETE FROM raw_uploads` → 0 hàng
3. Publish thử vào **kho cục bộ** trước, soi nội dung: `raw_uploads.csv` chỉ còn header, samples 3.860, labels 63, cả ba mang `tenant_id`
4. Publish thật lên Drive → **`Ver5_06082026`**
5. Chạy sync tường minh để lấy bằng chứng:

```
[sync] applied version=Ver5_06082026 signed_by=desktop-admin
       upserted={'classes': 63, 'samples': 3860, 'raw_uploads': 0}
```

`raw_uploads` = 0 sau khi sync. Đường phục hồi đã đóng.

**Kiểm trước khi publish:** cột `tenant_id` vốn đã có trong DDL **từ trước A1**, nên máy đọc chạy mã cũ vẫn có cột và không bị `REQUIRED_COLUMNS` từ chối.

### 7.3 Hệ quả cần ghi vào sách

Trong hệ thống này, **mọi thao tác xoá đều không bền cho tới khi có một phiên bản SOT mới được publish**. Điều này đụng thẳng vào phần "quyền thu hồi dữ liệu" của [COMMUNITY_DATA_COMMONS.md](../01-architecture/COMMUNITY_DATA_COMMONS.md): hiện chưa có đường nào để một lệnh xoá đi xuyên qua snapshot bất biến. Bốn nghĩa của "thu hồi" trong tài liệu đó đều giả định xoá là bền — giả định này **sai với hiện trạng**.

Quy trình xoá đúng, từ nay:

1. Xoá ở Postgres (và CSV, và file)
2. **Publish một phiên bản SOT mới**
3. Xác minh bằng `python -m app.sot.cli sync` rồi đếm lại

---

## 8. Điều phần A1 này *không* khẳng định

- **Chưa chứng minh A1 chạy đúng trên dữ liệu thật.** Mọi bằng chứng đến từ test với dữ liệu tổng hợp và một tenant B nhân tạo. Backfill 3.860 dòng thật chưa chạy. *(Đã chạy sau đó — xem §7.)*
- **Chưa có cô lập tenant.** A1 chỉ làm cho `tenant_id` *đúng và không mất*. Nó vẫn là một cột metadata, chưa phải ranh giới an ninh — đó là A2+A3. *(Đã làm — xem §9.)*
- **9/9 đột biến bị bắt không có nghĩa là không còn lỗi.** Nó chỉ nói: chín cách hỏng cụ thể mà tôi nghĩ ra đều bị bắt. Lỗi ở dạng tôi chưa nghĩ tới thì phép kiểm này không nói gì.
- **Chưa chạy suite trên máy khác.** Kết quả gắn với máy này, image này, dữ liệu này.

---

## 9. A2 → A4 và B1 → B4 — 2026-08-07

Tham chiếu kỹ thuật đầy đủ (kiến trúc, luồng nghiệp vụ, vận hành):
[TENANT_ISOLATION.md](../01-architecture/TENANT_ISOLATION.md). Mục này ghi *đã làm gì, tìm thấy gì, đo được gì*.

### 9.1 A2 — role ứng dụng không-superuser

Phát hiện quan trọng nhất của đợt khảo sát hoá ra đúng như dự đoán và **nghiêm trọng hơn
một chút so với cách kế hoạch mô tả**: không chỉ `admin` là superuser, mà `rolbypassrls` của
nó cũng bằng `true`. Nghĩa là một phép kiểm chỉ nhìn `rolbypassrls` sẽ bỏ sót đúng những
role nguy hiểm nhất — role superuser có `rolbypassrls = false` vẫn bỏ qua RLS. Hàm
`RolePrivileges.can_bypass_rls` **OR** hai thuộc tính chứ không kiểm riêng lẻ, và có test
ghim đúng điểm đó.

**Đã cài:**

| Thành phần | Vai trò |
|---|---|
| `app/cli/provision_db_roles.py` | Cấp `voya_app` (idempotent, xoay được mật khẩu); `--check` in tư thế |
| `app/storage/rls.py` | GUC, policy DDL, `apply_scope`, `assert_isolation_enforceable` |
| `settings.migration_database_url` | DSN riêng cho DDL, rỗng = chưa tách (tương thích ngược) |
| `settings.db_strict_isolation` | `1` = từ chối boot khi policy có mà role bỏ qua được |
| `metadata_db._migration_cursor` | Một kết nối autocommit cho toàn bộ DDL, ngoài pool |

**Bằng chứng thật, đo trên Postgres 17.10 đang chạy:**

```
no-GUC                          : 0        <- fail closed
SET LOCAL app.tenant_id=default : 3860
app.system_scope=on             : 3860
ALTER TABLE samples DISABLE RLS : ERROR: must be owner of table samples
```

Dòng cuối là điểm chốt của A2: bảo đảm **không tự thu hồi được**.

### 9.2 Ba chỗ DDL phải đổi kết nối — hai chỗ không nằm trong kế hoạch

Kế hoạch chỉ nói `ensure_tables()`. Rà thật thì có ba:

| Nơi | Nếu bỏ sót |
|---|---|
| `metadata_db.ensure_tables` / `drop_all_tables` | Schema không dựng được |
| `metadata_db.ensure_vocabulary_foreign_keys` | FK danh mục **im lặng** không cắm; giá trị dialect lạ hết bị chặn |
| `sot/reader_sync._apply_schema_sql` | Máy reader tụt lại một phiên bản schema, **im lặng** |

Cả hai chỗ sau đều đã bọc `try/except` ghi log rồi đi tiếp, nên hỏng ở đây **không tạo ra
lỗi nào nhìn thấy được** — chỉ tạo ra một deployment thiếu ràng buộc mà mọi thứ vẫn báo
xanh. Đây đúng là họ lỗi mà `verify_integrity_constraints()` được viết ra để chống.

Việc gom DDL vào **một** kết nối cũng bỏ được hơn một trăm lần bắt tay connect+auth mỗi lần
boot (trước đó mỗi câu lệnh mở một kết nối riêng).

### 9.3 A3 — tenant context

`app/tenant_context.py` (ContextVar) + `app/tenant_middleware.py` (ASGI thuần).

**Ba quyết định đáng ghi:**

1. **Mặc định là "không có tenant", không phải tenant khởi tạo.** Fail-closed chỉ là một
   tính chất nếu trạng thái đóng là trạng thái bạn nhận được khi *không làm gì*.
2. **ASGI thuần, không phải `BaseHTTPMiddleware`.** Cái sau chạy ứng dụng phía dưới trong
   một task nó tự sinh; truyền context qua ranh giới đó là nguồn lỗi tinh vi đã biết, và
   giá trị đang truyền quyết định dữ liệu của tenant nào được trả về.
3. **`system_scope` bắt buộc có `reason`.** Biến `grep -rn "system_scope("` thành một bản
   kiểm kê đọc được của mọi chỗ vượt ranh giới — 7 chỗ, liệt kê trong
   [TENANT_ISOLATION.md](../01-architecture/TENANT_ISOLATION.md) §4.5.

**Chính sách phải quyết, không né được:** 9 trong 16 endpoint của `classes.py` và 6 trong 16
của `dataset.py` là **công khai** (trang duyệt nhãn, demo realtime). Dưới RLS chúng sẽ trắng.
Nên có `settings.public_tenant_id` — tenant duy nhất có catalogue công khai. Đây là *một
chính sách được đặt tên*, không phải một fallback lặng lẽ; đặt rỗng thì ẩn danh không thấy gì.

### 9.4 Bộ chứng minh — và vì sao nó chạy trên một database riêng

Chứng minh cô lập cần tenant thứ hai có hàng thật. Ghi vào database đang chạy là **không
chấp nhận được**: beat `reconcile_samples_csv_task` đối soát hàng active ngược vào
`dataset/samples.csv` mỗi 5 phút, nên fixture của test có thể bị chép vào nguồn sự thật — và
theo §7.3, gỡ ra khỏi đó cần publish một phiên bản SOT mới.

Nên: tạo database mới mỗi lần chạy, dựng bằng **DDL thật** + **policy thật**, rồi xoá.

| File test (mới) | Số test | Phủ |
|---|---|---|
| `test_tenant_isolation.py` | 38 | đọc / fail-closed / ghi / role / tầng ứng dụng / phân giải request / kiểm kê ranh giới |
| `test_db_role_isolation.py` | 36 | tư thế role, DDL cấp quyền, tách DSN, hình dạng policy |
| `test_storage_partition.py` | 17 | bố cục, traversal, chủ sở hữu sống sót vòng đời CSV |
| `test_security_hardening.py` | 26 | B1 chặn traversal + symlink, B2/B3 khoá hạn mức + **limiter không trả lời thay authenticator**, B4 mount |
| **Tổng mới** | **117** | |

**Kiểm chứng bằng đột biến — 10/10 bị bắt** (`scratchpad/mutate_rls.py`, tự khôi phục file):

| # | Đột biến | Kết quả |
|---|---|---|
| M1 | predicate luôn `true` (fail **open**) | CAUGHT |
| M2 | bỏ `WITH CHECK` | CAUGHT |
| M3 | `current_setting` bỏ `missing_ok` | CAUGHT |
| M4 | bỏ `FORCE ROW LEVEL SECURITY` | CAUGHT |
| M5 | `apply_scope` thành no-op | CAUGHT |
| M6 | `set_config(..., false)` — `SET` thay vì `SET LOCAL` | CAUGHT |
| M7 | tắt phân vùng lưu trữ (mọi tenant chung một cây) | CAUGHT |
| M8 | bỏ chủ sở hữu khi đọc lớp từ một dòng dữ liệu | CAUGHT |
| M9 | chặn checkpoint bằng so khớp chuỗi thay vì `resolve()` | CAUGHT |
| M10 | hạn mức luôn khoá theo IP (một NAT bóp cả phòng) | CAUGHT |

Không có nghĩa là hết lỗi; chỉ nghĩa là **mười cách hỏng cụ thể** đều bị bắt.

### 9.4b Một lỗi rò trạng thái test đã tồn tại từ trước, lộ ra nhờ A4

`test_optimizations._patch_dataset_root()` **gán thẳng** `dataset_manager.FEATURES_ROOT` và
ba biến module khác, không qua `monkeypatch`, nên **không bao giờ được khôi phục**. Mọi test
chạy sau nó trong cùng tiến trình đều thấy một `dataset/` trỏ vào thư mục tạm đã bị xoá.

Lỗi này vô hình cho tới khi có test khác so sánh với giá trị đó — test A4 của tôi là cái đầu
tiên, và nó **chỉ đỏ khi chạy trọn bộ**, không đỏ khi chạy riêng file. Đây là dạng lỗi test
đắt nhất để truy: triệu chứng xuất hiện ở một file vô can, phụ thuộc **thứ tự chạy**.

Đã sửa cả hai đầu: một fixture autouse khôi phục 4 biến trong `test_optimizations`, và test
A4 đọc `dataset_manager.FEATURES_ROOT` **động** thay vì bind lúc import.

### 9.5 A4 — phân vùng lưu trữ, chia theo *tenant* chứ không theo *thời điểm*

Kế hoạch đề xuất "hai bố cục cùng sống, đọc thử mới trước rồi rơi về cũ". Rà thật thì
`hierarchy_path()` có **20 nơi gọi** — preview, đổi tên/di chuyển lớp, validator, oversample,
reclassifier. Đổi đường dẫn của tenant khởi tạo nghĩa là cả 20 nơi phải có fallback, và cả
8.784 file `.npz` nằm sau fallback đó vĩnh viễn.

Chia theo **tenant** thay vì theo **thời điểm** cho kết quả tốt hơn với ít việc hơn: tenant
khởi tạo giữ nguyên bố cục cũ, mọi tenant khác vào `_tenants/<id>/`. Mỗi tenant có **đúng
một** bố cục → **không đường đọc nào cần fallback**, không file nào di chuyển, và mọi tenant
tạo từ nay được phân vùng từ byte đầu tiên.

**Lỗ tìm thấy khi làm việc này:** `get_or_register_class._find_legacy_folder()` dò thư mục
theo slug dưới `FEATURES_ROOT` chung. Với tenant thứ hai, nó sẽ **nhận nhầm thư mục của
tenant khởi tạo** bất cứ khi nào slug trùng — mà slug trùng là *ca thường*, không phải ca
biên: hai deployment cùng thu ngôn ngữ ký hiệu tiếng Việt đều có thư mục cho `cam-on`. Đã
đổi sang dò trong subtree của tenant gọi.

Kèm theo: hai nơi tạo `ClassMetadata` không truyền `tenant_id`, nên mọi lớp tạo qua ứng dụng
đều sinh ra dưới tenant khởi tạo và **phân vùng lưu trữ sẽ không bao giờ kích hoạt**. Đã lấy
tenant từ ngữ cảnh gọi.

### 9.6 B1–B4

| Mã | Đã làm | Ghi chú đáng nhớ |
|---|---|---|
| B1 | `app/checkpoint_io.py`: chặn traversal (so sánh đường dẫn **đã resolve**) + thử `weights_only=True` trước | So khớp chuỗi là cách sai kinh điển: `"<root>/../../etc/passwd"` **có** bắt đầu bằng prefix hợp lệ. Symlink cũng bị bắt — đó mới là vector chuỗi cung ứng thật |
| B2/B3 | `enforce_actor_limit` + 4 hạn mức cấu hình được | Khoá theo **user** khi biết, theo IP khi không: người thu mẫu ngồi sau một NAT của trường, khoá theo IP là cả phòng chia nhau một hạn mức |
| B4 | Bỏ import `experiments` + `dataset_exporter`; `/jobs/{id}` cần đăng nhập | 681 dòng đọc như endpoint đang sống, không URL nào tới được, **vẫn chạy lúc import mỗi lần boot**. `/jobs/{id}` trả `traceback` — bản kê khai đường dẫn, bố cục module, phiên bản thư viện |

**Một trade-off được ghim bằng test, không phải bỏ sót:** rate limiter **fail OPEN** khi Redis
chết (`_incr_with_window` trả `(0, 0)`). Ngược lại là một cú nấc Redis cắt ngang buổi thu mẫu
tại trường chuyên biệt — mất những bản ghi rất đắt để sắp xếp — đổi lấy việc chặn lạm dụng
trên một endpoint đã có xác thực. Khác hẳn ranh giới tenant, vốn fail **CLOSED**: cái đó bảo
vệ dữ liệu của người khác, cái này bảo vệ dung lượng.

#### Lỗi thiết kế trong chính B3, do suite bắt được

Bản B3 đầu tiên gắn hạn mức lên `/upload/*` và `/training/*` **không phân biệt đã đăng nhập
hay chưa**. Suite đỏ ở `test_upload_endpoints_require_authentication`: request ẩn danh nhận
**429 thay vì 401**.

Triệu chứng nhẹ, nguyên nhân thì không:

1. **Limiter đã trả lời thay câu hỏi của lớp xác thực.** Nó chỉ được phép quyết *bao nhiêu*,
   không được quyết *có được vào không*.
2. **Nghiêm trọng hơn:** mọi caller ẩn danh dùng chung **một** xô, khoá theo IP. Một kẻ dù
   sao cũng sẽ bị 401 có thể làm cạn hạn mức của người dùng hợp lệ **sau cùng một NAT** — tức
   là chính cơ chế chống lạm dụng lại tạo ra một đường từ chối dịch vụ. Ở trường chuyên biệt,
   cả phòng là một NAT.

Sửa: `rate_limited(..., allow_anonymous=False)` mặc định — endpoint bắt buộc đăng nhập thì
**không đếm** request ẩn danh, cứ để nó đi tiếp tới 401 của chính endpoint. Chỉ
`/realtime/predict` — endpoint duy nhất phục vụ ẩn danh thật — đặt `allow_anonymous=True`,
vì bỏ đếm ở đó nghĩa là không còn trần nào, tức là quay lại đúng B2.

Đây là lý do đáng ghi cho việc **chạy trọn bộ suite thay vì chỉ chạy test của phần mình
sửa**: bộ test của B3 xanh hết; thứ bắt được lỗi là một test xác thực viết từ trước, ở một
file khác.

### 9.6b Bảng thay đổi

**Module mới** (7 file, 1.016 dòng):

| File | Dòng | Vai trò |
|---|---|---|
| `app/tenant_context.py` | 236 | ContextVar + `tenant_scope` / `system_scope(reason)` / `platform_command` |
| `app/storage/rls.py` | 230 | Hai GUC, policy DDL, `apply_scope`, `assert_isolation_enforceable` |
| `app/tenant_middleware.py` | 122 | ASGI thuần; phân giải tenant từ phiên, không từ header |
| `app/checkpoint_io.py` | 134 | Chặn traversal + `weights_only=True` trước |
| `app/cli/provision_db_roles.py` | 223 | Cấp/xoay `voya_app`; `--check` in tư thế |
| `app/rate_limit_deps.py` | 71 | Dây nối FastAPI cho hạn mức (tách để không tạo vòng import với `auth`) |

**Test mới** (4 file, 117 test) — xem bảng §9.4. Ngoài ra sửa 4 file test cũ, mỗi cái vì một
lý do khác nhau và đều được ghi lại: `test_dialect_registry_migration` (ghim DDL đi qua
cursor migration), `test_optimizations` (rò trạng thái module, §9.4b), `test_training_lifecycle`
+ `test_upload_camera_training` (seam checkpoint mới).

**Sửa** (17 file): `config.py` (+6 setting), `db.py` (vỏ scope + boot assertion),
`metadata_db.py` (`_migration_cursor`, `apply_scope` ở 2 lối vào, DDL một kết nối),
`worker.py` (2 signal), `sot/cli.py`, `sot/reader_sync.py`, `main.py` (middleware, bỏ 2 import
chết), `rate_limit.py` (`enforce_actor_limit`), 4 router, và **6 nơi dựng `ClassMetadata`**
(xem §9.5), `feature_structure_audit.py`, `conftest.py`, `pyproject.toml`, `.env.example`.

### 9.7 Kết quả test

| Mốc | Kết quả |
|---|---|
| Trước A2 (role `admin`) | 908 qua · 0 skip |
| Sau A2–A4 + B1–B4, role `voya_app` | 1.025 qua · 0 hỏng · 0 skip — *xem §9.10: không tái lập được, lệnh chạy không được ghi lại* |
| Sau cutover, môi trường đầy đủ | **1.030 qua · 0 hỏng · 0 skip** · 12 phút (§9.10, §9.11) |
| Đột biến | **11/11 bị bắt** (§9.9) |

Toàn bộ chạy với `DATABASE_URL` trỏ role **bị giới hạn** — nếu chạy bằng `admin` thì mọi
khẳng định cô lập đều xanh vì lý do sai.

Hai vòng đỏ trên đường đi, cả hai đều đáng ghi vì **bộ test của phần đang sửa không bắt được
chúng**:

| Vòng | Hỏng | Nguyên nhân thật |
|---|---|---|
| 1 | 4 test `test_dialect_registry_migration` | Ghim wiring cũ; DDL nay phải đi qua cursor migration. Test đã được sửa để ghim bất biến **mới**, không phải để xanh lại |
| 2 | 14 test (3 A4 + 11 training) | (a) rò trạng thái module có sẵn từ trước §9.4b; (b) seam checkpoint đổi; (c) **lỗi thiết kế thật trong B3** — xem §9.6 |

### 9.8 Cutover — ĐÃ TRIỂN KHAI 2026-08-07

| Bước | Trạng thái |
|---|---|
| 1. `provision_db_roles` — tạo `voya_app` | ✅ đã chạy, đã xác minh trên Postgres 17.10 |
| 2. Full suite với `DATABASE_URL` trỏ `voya_app` | ✅ |
| 3. Sao lưu `.env` | ✅ `voya_backups/env_pre_A2A3_20260807-085839.bak` |
| 4. Đổi `.env` → `voya_app` + `DB_STRICT_ISOLATION=1` | ✅ |
| 5. `docker compose build backend` | ✅ |
| 6. `up -d` toàn stack với **cả ba** file compose | ✅ 13 healthy + `sot_init` exited(0) |
| 7. `provision_db_roles --check` | ✅ exit 0, "tenant isolation is in force" |

Xác minh sau triển khai — chạy trực tiếp trong container, không qua bộ test:

| Đo | Kết quả |
|---|---|
| Role runtime | `voya_app`, superuser **False**, bypassrls **False** |
| RLS | bật trên `classes`, `raw_uploads`, `samples` |
| Log khởi động (cả 4 gunicorn worker) | `[RLS] tenant isolation in force: role=voya_app` |
| `tenant_scope("default")` → `COUNT(*) samples` | 3.860 |
| `tenant_scope("nonexistent-tenant")` | **0** |
| `system_scope(...)` | 3.860 |
| `ALTER TABLE samples DISABLE ROW LEVEL SECURITY` | từ chối — `InsufficientPrivilege` |
| Dữ liệu | `samples` 3.860 hàng, toàn bộ `tenant_id='default'`; `samples.csv` 3.860 dòng |
| `GET /dataset/labels` (ẩn danh) | 200, trả dữ liệu thật qua tenant công khai |
| `GET /dataset/samples` (ẩn danh) | **401** — không phải 429; đúng hành vi B3 |

### 9.9 Hai lỗi phát hiện *lúc* triển khai, không lỗi nào bộ test bắt được

**(1) `--check` soi nhầm kết nối — lỗi của tôi.** Nó chỉ mở `connect_migration()`, tức role
DDL, vốn **bắt buộc** phải là superuser. Nên trên một hệ đã cutover hoàn toàn đúng nó vẫn in
`connected as: admin / superuser: True / WARNING: policies are theatre` rồi exit **0**.

Cái sai không phải một dòng chữ thừa. Đó là một công cụ chẩn đoán **không bao giờ có thể
báo xanh** — nghĩa là nó chưa từng đo cái nó nói là đang đo, và nếu cô lập thật sự hỏng thì
đầu ra cũng y hệt. Một cảnh báo luôn bật dạy người vận hành bỏ qua đúng dòng quan trọng nhất.

Đã sửa: `--check` mở **cả hai** DSN, chỉ coi role **runtime** là phát hiện, và exit **3** khi
runtime bypass được RLS *hoặc* khi không bảng nào bật RLS (role bị giới hạn trên một database
không có policy thì cũng không được cô lập — nó chỉ không nhìn thấy sự khác biệt). Ba test
trong `TestCheckCommand` ghìm cả hai nửa, và đột biến **M11** khôi phục lại đúng bug này.

**Vì sao bộ test không bắt:** 1.025 test đều không chạm nhánh `--check`. Bài học không phải
"viết thêm test" mà: **công cụ chẩn đoán cũng là mã sản xuất** và phải bị đột biến như mọi
mã khác. Một cái test đọc `--check` mà chỉ assert "không crash" thì cũng đã xanh.

**(2) Triển khai rơi mất hai file override — lỗi vận hành, hỏng lặng lẽ.** Runbook cũ viết
bằng bash:

```bash
COMPOSE="-f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.gpu.yml"
docker compose $COMPOSE up -d --force-recreate ...
```

Chạy trên PowerShell: dòng 1 **lỗi** (`CommandNotFoundException`), `$COMPOSE` rỗng, dòng 2
vẫn **thành công** với mỗi file base. Hậu quả: `mem_limit=0` trên mọi container và
`DeviceRequests=null` — trainer chạy **không GPU**. Mọi container báo healthy nên không có
tín hiệu nào cho biết.

Đây là **lần tái diễn thứ hai** của cùng một sự cố (lần trước 2026-07-22, xem
`stack-missing-prod-override`), lần này nguyên nhân gốc khác hẳn: không phải quên gõ, mà là
một phép gán thất bại **không chặn** lệnh kế tiếp, cộng với việc `docker compose` không có
`-f` vẫn là lệnh hợp lệ. Hai sự thật vô hại ghép lại thành một lần triển khai trông đúng mà
không đúng.

Đã sửa ở tài liệu: runbook viết bằng **PowerShell**, ba cờ `-f` viết thẳng trong lệnh, và
thêm bước xác minh bắt buộc:

```powershell
docker inspect voya_trainer --format "{{json .HostConfig.DeviceRequests}} {{.HostConfig.Memory}}"
# "null 0"  =>  override đã bị rơi
```

**Rollback** = khôi phục hai dòng đã comment sẵn trong `.env` rồi triển khai lại (đủ ba cờ
`-f`); role `admin` và policy đều còn nguyên, chỉ là policy thôi có hiệu lực.

### 9.10 Lệnh chạy suite — ba mảnh thiếu, ba kiểu đỏ giả

Kiểm tra lại con số 1.025 báo ở §9.7, tôi **không tái lập được** — vì lệnh tôi dùng lần đó
không được ghi lại đầy đủ. Ghi ở đây để lần sau không mất thời gian nữa:

```powershell
docker run --rm --network voya-collector_voya_network `
  -v "E:\CTU_ProjectOutside\VOYA-Collector:/src" `
  -v "E:\CTU_ProjectOutside\Videos:/testvideos:ro" `
  -w /src/backend -e PYTHONPATH=/src/backend `
  -e DATABASE_URL="postgresql://voya_app:<pw>@postgres:5432/signdb" `
  -e MIGRATION_DATABASE_URL="postgresql://admin:admin@postgres:5432/signdb" `
  -e VOYA_APP_DB_PASSWORD="<pw>" `
  -e REDIS_URL="redis://redis:6379/15" -e CELERY_BROKER_URL="redis://redis:6379/15" `
  -e CELERY_RESULT_BACKEND="redis://redis:6379/15" -e TTS_REDIS_URL="redis://redis:6379/15" `
  voya_backend_test:latest python -m pytest tests -q --no-header
```

| Thiếu | Hậu quả | Nhìn giống |
|---|---|---|
| Bốn biến Redis | `conftest` `setdefault` về `localhost:6379`, container dùng-một-lần không có gì nghe ở đó | **13 đỏ** ở watermark / rate-limit / password-reset / sync — y như lỗi mã |
| Mount cả repo ở `/src` | 3 file `import processed.*` từ gốc repo qua `parents[2]` | **3 lỗi lúc collect**, cả suite dừng |
| Mount `Videos:/testvideos:ro` | test trích npz từ video không có dữ liệu | **skip** — kiểu skip tệ nhất, trông như "môi trường không hỗ trợ" trên đúng máy duy nhất chạy được |

**Redis db 15, không phải db 0, khi stack đang chạy thật.** Test rate-limit ghi vào chính
namespace backend production đang đọc; chạy trên db 0 có thể khoá nhầm người dùng thật.

### 9.11 Hai lỗi trong `processing/ingest.py`, do một test đỏ chỉ ra

Lần chạy đầu đủ môi trường: **1.027 qua · 1 hỏng · 0 skip**. Cái đỏ duy nhất là
`Read-only file system: '/testvideos/resampled_….mp4'`, và nó **không** phải lỗi mount.

**(1) File tạm được ghi cạnh video nguồn.** `ffmpeg_resample` gọi `mkstemp(dir=dirname(input))`
kèm chú thích *"same directory for atomicity/cleanup"*. Chú thích sai: file này chỉ được đọc
rồi xoá, **không bao giờ được rename đè lên cái gì**, nên không có tính nguyên tử nào để
giành. Cái giá thì có thật — thư mục nguồn buộc phải ghi được, và mỗi lần sập giữa chừng lại
bỏ lại một `resampled_*.mp4` trong cây dữ liệu, kể cả `dataset/raw/` vốn để chứa **đúng** cái
đã tải lên và không gì khác. Đã đổi sang thư mục tạm hệ thống.

**(2) Rò file tạm ở đúng nhánh cần dọn nhất.** `raise RuntimeError("Cannot open video file")`
nằm **trên** khối `try/finally`, nên một bản resample không mở được sẽ để lại file tạm mãi
mãi. Đã đưa cả `VideoCapture` lẫn phép kiểm tra vào trong `try`.

Vì sao không ai thấy: upload thật rơi vào thư mục ghi được, nên nhánh read-only chưa từng
chạy trong production. Nó lộ ra vì tôi mount kho video `:ro` — và đúng ra phải mount `:ro`,
vì đó là dữ liệu gốc. Hai test mới trong `TestSourceDirectoryIsNotScratchSpace` ghìm cả hai.

---

## 10. 2026-08-07, đợt 2 — Celery mang tenant, RLS đủ 13 bảng, cưỡng chế xác minh email

Ba mục ở §4 của [TENANT_LIFECYCLE_AND_OTP.md](../01-architecture/TENANT_LIFECYCLE_AND_OTP.md) từng được ghi là
**không** khẳng định. Đợt này làm ba trong số đó. SMS vẫn để nguyên theo yêu cầu.

### 10.1 Mở đầu bằng một báo động giả — và nó dạy đúng điều cần biết

Báo cáo nhận được là "cơ sở dữ liệu PostgreSQL mất tiêu". Không mất gì: 26 bảng còn nguyên,
3.860 mẫu, 10 tài khoản, volume nguyên vẹn. Cái mất là **khả năng nhìn thấy**, và nguyên nhân
là chính RLS vừa bật:

| Truy vấn cùng bảng, cùng lúc, vai trò `voya_app` | users | samples | training_jobs |
|---|---|---|---|
| Không đặt scope | 0 | 0 | 0 |
| `SET app.tenant_id='default'` | 10 | 3.860 | 85 |

Đây chính là thiết kế fail-closed hoạt động đúng. Nhưng nó có một cái giá phải ghi ra:
**mọi đường quên đặt scope đều trông y hệt như mất dữ liệu.** Người vận hành nhìn màn hình
trống không phân biệt được "policy chặn" với "bảng rỗng". Nếu sau này có thêm một màn hình
trống bất thường, câu hỏi đầu tiên phải là `SELECT current_setting('app.tenant_id', true)`,
không phải mở backup ra.

Lỗi "redis down" trong ảnh chụp là do stack đang được dựng lại đúng lúc đó (`RestartCount=0`,
`StartedAt` cách thời điểm chụp vài chục giây), không phải sự cố Redis.

### 10.2 Celery: tenant đi theo thông điệp

**Trước:** mọi task chạy ở system scope, bất kể ai gọi. Một task gửi đi từ trong request của
tenant A đọc được dữ liệu của mọi tenant.

**Cách làm:** không sửa 40 điểm gọi `.delay()`/`.apply_async()` — sửa một chỗ, hai signal.

```
before_task_publish  ->  headers["voya_tenant"] = current_tenant()   (nếu có)
task_prerun          ->  header có   -> enter_tenant_scope(...)
                         header không -> enter_system_scope(...)      (như cũ)
```

Vì sao header chứ không phải tham số task: sửa 40 điểm gọi thì **điểm bị bỏ sót** là một lệnh
ghi xuyên tenant im lặng, chứ không phải một lỗi kiểu dữ liệu.

Một giả định phải đo chứ không tin: Celery có chuyển header tuỳ ý vào `task.request` không?
Có — kiểm bằng cách xuất bản thật rồi đọc phong bì thô từ Redis; khoá nằm trong `headers`, và
`Context(headers)` phơi nó ra thành thuộc tính.

**Bảo đảm về mặt cấu trúc:** header chỉ có thể **thu hẹp** phạm vi. Không có chuỗi nào dẫn tới
system scope, vì system là thứ nhận được khi *không* phải một tenant hợp lệ. Nên không có
danh sách chặn nào để quên. `"system"` là một tenant id hợp lệ, và nó bị coi là một tenant
**tên là** "system" — khớp đúng những dòng có `tenant_id='system'`, gần như chắc chắn là không
dòng nào.

### 10.3 Cái bẫy suýt ship: tác vụ tổng hợp bị bó hẹp

Sáu tác vụ đọc **toàn bộ** bảng để dựng **một** artifact chung cho cả hệ thống — và ba trong số
đó được gửi đi từ bên trong biến đổi danh mục, tức là từ trong request của một tenant:

```
export_samples_to_sheets      export_labels_to_sheets
mirror_catalog_csvs_to_drive  reconcile_samples_csv_task
download_missing_files_to_local  cleanup_training_artifacts
```

Bó chúng vào tenant người gọi sẽ **xuất ra một bảng tính thiếu dòng của mọi tenant khác**.
Thất bại này vô hình: lệnh xuất chạy xong, báo thành công, chỉ là ngắn hơn.

Giải pháp: cờ `platform_wide=True` ngay trên khai báo task, và nó **thắng** header.
`download_missing_files_to_local` là ca đáng chú ý — thân hàm của nó đã ghi rõ trong comment
rằng nó dựa vào system scope, và nó được gửi từ router admin. Không có cờ này thì tôi vừa làm
hỏng đúng thứ mà comment ấy cảnh báo.

Test `test_exactly_these_tasks_are_platform_wide` liệt kê thẳng sáu tên thay vì dò tự động:
thêm tác vụ tổng hợp thứ bảy phải là một hành động có ý thức, kèm một test phải sửa.

### 10.4 RLS: 5 → 13 bảng

Tám bảng còn lại (`dialect_aliases`, `dialects`, `recognition_profiles`, `registry_versions`,
`signers`, `tenant_invitations`, `tenant_members`, `vocabulary_registry_meta`) trước đây được
bỏ ra với lý do "chỉ tới được qua các đường đã join vào năm bảng kia". Lý do đó đúng với mã
**đang có** — mà đó chính xác là điều module này tồn tại để thôi phụ thuộc vào. Lọc ở tầng ứng
dụng bảo vệ mã đã viết; policy bảo vệ mã sẽ viết. Riêng `registry_versions` là sổ nguồn gốc
của mặt phẳng artifact: đọc được lịch sử phiên bản của tenant khác là đọc được từ vựng của họ.

Kiểm trước khi bật: **không bảng nào có `tenant_id` NULL**. Một dòng NULL sẽ không khớp policy
nào và biến mất khỏi tầm nhìn ứng dụng — không phân biệt được với bị xoá.

Thêm `test_every_tenant_scoped_table_has_a_policy` khẳng định `RLS_TABLES == TENANT_SCOPED_TABLES`.
Trước đó hai danh sách chỉ trùng nhau do trùng hợp: một bảng có trong danh sách đầu mà không có
trong danh sách sau thì vẫn có cột, vẫn có khoá ngoại, vẫn qua được phép kiểm triển khai đếm số
bảng "được bảo vệ" — và vẫn đọc được bởi mọi tenant.

Đã áp lên cơ sở dữ liệu thật: **13/13 bảng `relrowsecurity AND relforcerowsecurity`.**

**Bộ kiểm triển khai trước đó không hề hỏi về RLS.** `verify_deployment` đếm khoá ngoại
`tenant_id` và báo xanh — nhưng khoá ngoại chỉ chứng minh cột trỏ tới chỗ có thật, nó không
nói gì về việc truy vấn *có bị lọc* theo cột đó hay không. Đã thêm hai phép kiểm tách bạch,
vì đó là hai thất bại khác nhau:

```
PASS  RLS bat tren bang     13/13 bang
PASS  RLS co hieu luc       role voya_app bi rang buoc
```

Cái thứ hai là cái nguy hiểm hơn: policy có mặt nhưng vai trò kết nối bỏ qua được, khi đó
`pg_policies` lẫn `pg_tables.rowsecurity` đều báo cô lập đang hoạt động.

### 10.5 Cưỡng chế xác minh email

`REQUIRE_EMAIL_VERIFICATION`, **mặc định TẮT**. Cưỡng chế ở đúng **một** chỗ: `login`. Một cổng
ở lối vào hơn một decorator trên tám mươi endpoint, nơi cái bị quên là cái lỗ.

Vị trí trong hàm quan trọng ngang bản thân phép kiểm. Nó nằm **sau** phép kiểm mật khẩu: nếu
đặt trước, endpoint này trở thành máy tra "địa chỉ này có tài khoản chưa xác minh không?", trả
lời được mà **không cần biết mật khẩu**. `test_a_wrong_password_is_still_401_not_403` ghìm
đúng thứ tự đó.

Bật cờ mà không chuẩn bị sẽ khoá cả 10 tài khoản hiện có — **kể cả người vừa bật cờ**, và giờ
không đăng nhập được để tắt nó đi. Nên có `app/cli/verify_existing_emails.py`:

```
python -m app.cli.verify_existing_emails --check    # ai sẽ bị khoá (exit 2)
python -m app.cli.verify_existing_emails --apply    # chấp nhận các địa chỉ đang có
```

Lệnh này **không xác minh gì cả**. Nó ghi nhận rằng các địa chỉ này được chấp nhận nguyên
trạng — một quyết định về dữ liệu cũ, không phải một bằng chứng về nó. Cái nó mua được là yêu
cầu áp dụng từ nay trở đi, cho các tài khoản tạo từ nay trở đi, là nơi duy nhất nó có thể áp
dụng một cách trung thực.

### 10.6 `email_service` ghi mã OTP vào log

`_send` ghi **toàn bộ thân thư** khi `SMTP_HOST` trống — mà thân thư xác minh *chính là* mã.
Nặng hơn: docstring do chính tôi viết ở đợt trước khẳng định mã "không bao giờ được ghi log ở
đây". `sms_service` từ chối đúng lối tắt này và giải thích tại sao; phía email thì lặng lẽ
dùng nó.

Hôm nay không kích hoạt vì SMTP đã cấu hình. Nhưng một lần triển khai làm mất `SMTP_HOST` sẽ
**không hỏng** — nó vẫn "chạy" trong khi ghi mọi OTP xuống đĩa, nơi nhiều người đọc được hơn
cơ sở dữ liệu.

Sửa bằng tham số `loggable=` **bắt buộc** (không có giá trị mặc định, để người thêm hàm gửi
thứ ba phải tự trả lời "thân thư này có được phép nằm trong log không?"). Mã OTP → ném
`EmailNotConfigured` → 503. Link đặt lại mật khẩu → giữ tiện ích log dev vốn có tài liệu, vì
token 32 byte dùng một lần là rủi ro khác hẳn mã sáu chữ số.

### 10.7 Ba lỗi trong chính công cụ đo của tôi

Đáng ghi lại vì cả ba đều **im lặng** — không cái nào báo lỗi.

**(1) `CELERY_BROKER_URL` thắng cả `Celery(broker=...)` lẫn `conf.update(broker_url=...)`.**
Test xuất bản của tôi tưởng đang ghi vào db 14; thực tế ghi vào db 15 — chính db mà bộ đếm
rate-limit của suite đang dùng — trong khi đọc db 14 và thấy rỗng. Triệu chứng là "hàng đợi
trống", không bao giờ là một lỗi. Chỉ `monkeypatch.delenv` mới thật sự dời được điểm đến.
Đã dọn 7 thông điệp lạc khỏi db 15; production dùng db 0, hàng đợi rỗng, không ảnh hưởng.

**(2) Tên hàng đợi chưa khai báo thì xuất bản vào hư không.** Với transport Redis, tên hàng đợi
*là* khoá list. Đặt `queue="voya_tenant_probe"` không tạo ra khoá nào. Cô lập phải đến từ số db,
không phải từ tên hàng đợi.

**(3) Một khẳng định của test sai, không phải mã sai.** Tôi viết
`test_a_header_cannot_buy_system_scope` khẳng định `"system"` bị từ chối. Nó không bị từ chối —
nó là một tenant id hợp lệ. Bất biến đúng là "không bao giờ trở thành system scope", và tôi đã
sửa **test** để ghìm điều đó, chứ không nới mã cho khớp test.

### 10.8 Bộ test ghi vào cơ sở dữ liệu sản xuất — hai lần trong một phiên

Đây là vấn đề hạ tầng, không phải một lỗi lẻ.

**Lần 1:** hai tài khoản `reg_*@example.com` và `pipe_*@example.com` do các lần chạy suite
trước để lại trong bảng `users` thật. Đã xuất CSV sang `voya_backups/removed_test_users_20260807.csv`
rồi xoá — 0 mẫu, 0 tham chiếu trên cả 16 khoá ngoại.

**Lần 2, do chính tôi gây ra ngay trong đợt này:** `test_apply_marks_the_account` gọi
`main(["--apply"])` không giới hạn phạm vi, và đánh dấu **cả 10 tài khoản thật** là đã xác minh
(cùng một dấu thời gian 12:11:40). Đã trả về NULL toàn bộ.

Nguyên nhân gốc không phải sự bất cẩn mà là **thiếu cách diễn đạt phạm vi hẹp**. Nên đã thêm
`--email-like PATTERN` vào CLI — vừa là thứ người vận hành thật sự cần ("chỉ grandfather các địa
chỉ CTU"), vừa khiến test không thể chạm vào dữ liệu nó không tạo ra. Kèm
`test_a_filtered_run_leaves_everyone_else_alone` ghìm đúng tính chất đã bị vi phạm.

**Quy tắc từ nay:** sau mỗi lần chạy suite, kiểm
`SELECT * FROM users WHERE email LIKE '%@example.%'`. Suite dùng chính `signdb` là chủ ý — RLS
và unique index bộ phận chỉ chứng minh được trên Postgres thật — nhưng hệ quả thì phải trả giá
bằng kỷ luật dọn dẹp.

### 10.9 Breadcrumb "Dashboard" bấm không được

Nguyên nhân không phải thiếu link. `PageHeader` gắn `hover:text-slate-700` cho cả crumb
**không có** `href`, nên "Dashboard" đổi màu khi rê chuột rồi không đi đâu — đọc như link hỏng.
Đã thêm `href` ở 4 trang **và** bỏ hiệu ứng hover khỏi chữ không bấm được: chỉ hiển thị dấu
hiệu bấm được khi cú bấm thật sự hoạt động.

### 10.10 Số liệu

| Phép đo | Kết quả |
|---|---|
| Suite backend đầy đủ, vai trò `voya_app` | **1.182 qua · 0 hỏng · 0 skip** (13:15) |
| Suite frontend | **157 qua / 22 file** |
| Bảng có RLS thực thi trên DB thật | **13/13** (`relrowsecurity AND relforcerowsecurity`) |
| `verify_deployment` | `RLS bat tren bang 13/13` · `RLS co hieu luc: role voya_app bi rang buoc` |
| Test mới đợt này | 20 (Celery) + 11 (cưỡng chế email) + 1 (RLS↔FK khớp danh sách) + 3 (PageHeader) |

Lượt chạy **trước** khi sửa cho **1.167 qua · 4 hỏng**. Bốn cái đỏ đó là toàn bộ giá trị của
lần chạy này, và không cái nào tôi đoán trước được:

| Đỏ | Loại |
|---|---|
| `test_tenant_admin_may_invite_into_their_own_tenant` | **hồi quy thật** — §10.4, `tenant_role` |
| `test_a_typoed_tenant_id_is_refused` | test xanh-sai-lý-do — RLS chặn trước FK |
| `test_a_real_tenant_is_accepted` | như trên |
| `test_boundary_crossings_are_an_allowlist` | allowlist làm đúng việc — 2 file mới cần khai báo |

Frontend cũng đỏ 8 sau khi sửa breadcrumb: hai file test mock `react-router-dom` mà không có
`Link`, nên chỉ cần crumb nào đó dựng một `Link` là cả file nổ. Đã bổ sung mock theo đúng khuôn
đã có sẵn trong `LabelDetailPage.test.tsx`.

### 10.11 Điều đợt này *không* khẳng định

- **Không khẳng định SMS hoạt động.** Vẫn ném lỗi, theo yêu cầu để nguyên.
- **Không khẳng định `REQUIRE_EMAIL_VERIFICATION` đã bật.** Nó tắt. Bật là quyết định vận hành,
  và trình tự bắt buộc là chạy CLI trước.
- **Không khẳng định mọi task đã được kiểm với tenant thật.** Cơ chế có test; việc chạy một job
  huấn luyện thật dưới tenant B thì chưa.
- **Không khẳng định RLS trên `users` bảo vệ đường xác thực.** Xem §2.2 của
  TENANT_LIFECYCLE_AND_OTP.md — tầng danh tính được miễn trừ và buộc phải thế.
- **Không khẳng định chống được người trong cuộc có quyền DB.** Ai có `MIGRATION_DATABASE_URL`
  bỏ qua được toàn bộ.
