# Đồng bộ dataset dev ↔ deploy — việc đã làm và việc còn phải làm

Ngày 2026-07-31. Bản `dataset/` trên máy dev **đã là siêu tập** của cả hai máy.
Tài liệu này ghi lại cách nó được gộp, và những bước bắt buộc khi mang bộ dữ liệu
này sang máy deploy — bỏ bước nào cũng dẫn tới tham chiếu chết hoặc mất dòng.

---

## 1. Đã làm trên máy dev

| | trước | sau |
|---|---|---|
| `dataset/samples.csv` | 3692 dòng | **3860** (+168) |
| `dataset/labels.csv` | 56 lớp | **63** (+7 lớp `spa`) |
| `dataset/features/*.npz` | 3692 | **3871** (+179) |

Kiểm chứng sau khi ghi: 3860 `sample_uid` không trùng lặp, 0 dòng trỏ tới
`class_uid` không tồn tại, 0 dòng thiếu file `.npz`, `class_idx` không đụng nhau.

Sao lưu: `dataset/samples.csv.bak-presync-20260731-130256` (và `labels.csv`).
Báo cáo: `dataset/sync_report-20260731-130256.txt`.

### Bỏ qua có chủ đích

- **1174 dòng trùng `sample_uid`** — giữ bản dev. Bản dev có 31 cột (chỉ số chất
  lượng, `signer_id`, `collection_campaign`, hợp đồng tiền xử lý v2), bản server
  chỉ 19 cột; `user_id` bản dev là tên người thật, bản server là UUID tài khoản;
  `file_path` bản dev là đường dẫn tương đối, bản server là URL Drive. Ghi đè
  bằng bản server là mất dữ liệu.
- **15 dòng test** — `dialect` ∈ {`testdata`, `testdatase`} hoặc slug ∈
  {`test1`, `testlive3`}. 10 trong số đó vốn đã không có file `.npz`.

---

## 2. Hai chỗ phải sửa khi mang sang máy deploy

### 2.1 `class_uid` bị chia đôi

Hai lớp được tạo **độc lập trên hai máy** nên mang UUID khác nhau. Bản gộp giữ
UUID của máy dev:

| slug | UUID GIỮ LẠI (dev) | UUID BỎ (deploy) | số mẫu trên deploy đang trỏ vào UUID bỏ |
|---|---|---|---|
| `q` | `356d0732-cf18-4cfb-bded-5ac06d847a3e` | `795eec29-34d7-4b23-aba9-89cab7a5deec` | **40** |
| `dia-chi` | `df77087d-4fab-4de8-a074-8c3f619a1919` | `dc06f29f-3965-425c-8845-afdf6a2d9916` | 0 |

Trong CSV đã xử lý xong (ánh xạ lại theo `slug` khi gộp). **Nhưng Postgres của
máy deploy thì chưa** — 40 mẫu lớp `q` ở đó vẫn trỏ vào UUID cũ. Chạy trước khi
sync CSV→DB trên máy deploy:

```sql
BEGIN;

-- Chuyển mẫu sang lớp giữ lại
UPDATE samples
   SET class_uid = '356d0732-cf18-4cfb-bded-5ac06d847a3e'
 WHERE class_uid = '795eec29-34d7-4b23-aba9-89cab7a5deec';

UPDATE samples
   SET class_uid = 'df77087d-4fab-4de8-a074-8c3f619a1919'
 WHERE class_uid = 'dc06f29f-3965-425c-8845-afdf6a2d9916';

-- Kiểm: phải trả về 0 trước khi commit
SELECT count(*) FROM samples
 WHERE class_uid IN ('795eec29-34d7-4b23-aba9-89cab7a5deec',
                     'dc06f29f-3965-425c-8845-afdf6a2d9916');

-- Chỉ xoá lớp mồ côi SAU khi câu trên trả 0
DELETE FROM classes
 WHERE class_uid IN ('795eec29-34d7-4b23-aba9-89cab7a5deec',
                     'dc06f29f-3965-425c-8845-afdf6a2d9916');

COMMIT;
```

> Bỏ bước này thì sync CSV→DB sẽ chèn thêm một lớp `q` thứ hai, và 40 mẫu cũ
> thành mồ côi — chúng biến mất khỏi mọi split và mọi trang catalog.

### 2.2 Quy ước `file_path` / `storage_url`

Hai máy dùng ngược nhau. Quy ước chuẩn (đã áp cho toàn bộ 3860 dòng trên máy dev):

```
file_path    = đường dẫn TƯƠNG ĐỐI     features/<lang>/<dialect>/<folder>/sample_x.npz
storage_url  = URL Drive               https://drive.google.com/file/d/...
storage_key  = giống file_path
```

Bản deploy để URL Drive trong `file_path` và bỏ trống `storage_url`. Khi gộp,
`file_path` được lấy từ `storage_key` và URL đẩy sang `storage_url`.

Kiểm nhanh trên máy đích sau khi chép:

```bash
python - <<'PY'
import csv, collections
rows = list(csv.DictReader(open("dataset/samples.csv", newline="", encoding="utf-8-sig")))
k = collections.Counter("url" if (r["file_path"] or "").startswith("http")
                        else "tuong-doi" if (r["file_path"] or "").startswith("features/")
                        else "khac" for r in rows)
print(k)   # phải là {'tuong-doi': <tổng số dòng>}
PY
```

---

## 3. Đường dẫn catalog: đã chốt `dataset/samples.csv`

Máy deploy đang chạy layout cũ `dataset/samples/samples.csv`; máy dev dùng
`dataset/samples.csv`. Đã chốt file gốc là chuẩn — khớp `KNOWN_ISSUES.md`
2026-07-20, khớp `labels.csv` (vốn luôn ở gốc), và là nơi chứa bản gộp đầy đủ.

`backend/app/dataset_samples.py` đã sửa: `SAMPLES_CSV = DATASET_ROOT /
"samples.csv"`, kèm `_warn_if_legacy_catalog_present()` — chạy lúc import, log
**ERROR** nếu máy nào còn dòng ở layout cũ. Máy chưa migrate sẽ hiện ra ngay thay
vì âm thầm bỏ qua 1357 dòng.

Các bước trên máy deploy:

```bash
cd ~/VOYA-Collector
docker compose stop worker celery_beat            # dừng người ghi

cp -a dataset/samples/samples.csv dataset/samples/samples.csv.pre_merge_bak
# chép bản gộp từ máy dev vào dataset/samples.csv (+ labels.csv + features/)
mv dataset/samples/samples.csv dataset/samples/samples.csv.retired

# chạy SQL ở §2.1, rồi sync CSV -> Postgres
docker compose start worker celery_beat
```

Còn thiếu: `backend/app/cli/verify_deployment.py:96` vẫn kiểm
`/dataset/samples/samples.csv` — sửa thành `/dataset/samples.csv` cho khớp
`labels.csv` ngay dòng trên nó.

---

## 4. Vì sao "lần nào sync cũng không cập nhật database" — ĐÃ SỬA

Không phải do chạy thiếu lệnh. `sync_missing_data_on_startup()` trong
`backend/app/db.py` chặn mỗi bảng bằng **so sánh SỐ LƯỢNG**:

```python
if db_classes_count < len(labels):   # <- chỉ sync khi DB ÍT HƠN CSV
```

Postgres **giữ lại hàng xoá mềm**, còn CSV chỉ chứa hàng còn sống. Nên chỉ cần
xoá một mẫu bất kỳ là `db_count >= csv_count` **vĩnh viễn**, điều kiện không bao
giờ đúng lại, và **không dòng mới nào được sync nữa** — dù CSV có thêm bao nhiêu.
Đó chính xác là triệu chứng đã thấy.

Hai kiểu hỏng khác của cùng cái chặn đó:

- số bằng nhau nhưng **tập khác nhau** (thêm N, xoá N) → bỏ qua;
- sửa một hàng tại chỗ **không đổi số đếm** → sửa không bao giờ được đẩy sang DB.

**Cách sửa:** so sánh **tập khoá chính**, không so số đếm. Tốn một lần quét cột
có index, và đúng trong cả ba trường hợp trên. Hàm còn:

- ghi log rõ `CSV n, DB m -> thêm k hàng` mỗi lần chạy, kèm vài `sample_uid` ví dụ;
- **cảnh báo** khi có hàng nằm trong DB mà không có trong CSV (xoá mềm thì bình
  thường, ngoài ra là dấu hiệu CSV bị ghi đè hoặc hai máy ghi lệch nhau);
- không bao giờ chèn lại hàng đã xoá mềm — chúng vẫn được tính là "đã có".

**Đẩy cả những hàng ĐÃ SỬA** thì cần cờ riêng, vì không CSV nào có cột
`updated_at` để so:

```bash
docker compose run --rm backend python -m app.cli.init_db --full-resync
# hoặc: VOYA_DB_FULL_RESYNC=1
```

Kiểm thử: `backend/tests/test_startup_sync_keyset.py` — 14 test, không cần DB.

### Chạy sync cho 168 dòng mới trên máy dev

Chưa chạy được vì `docker-compose.yml` còn dấu xung đột của merge. Sau khi gỡ:

```bash
docker compose up -d postgres redis
docker compose run --rm backend python -m app.cli.init_db     # sync CSV -> Postgres

# Kiểm: hai con số phải bằng nhau
docker compose exec postgres psql -U admin -d signdb -c \
  "SELECT count(*) FROM samples WHERE deleted_at IS NULL;"
wc -l dataset/samples.csv    # trừ 1 dòng header
```

Bảng `classes` cũng cần nhận 7 lớp `spa` mới.

---

## 5. Danh tính người ký — CHƯA xử lý, cần chủ dữ liệu xác nhận

Phần thêm vào mang các tên `Thu Ngân` (11 mẫu) và `Trâm` (45), trong khi máy dev
đã có `Thungan` và `Tram`. Nguyên nhân đã rõ: **hai tài khoản email không tồn
tại nên phải tạo tài khoản mới** — cùng một người, hai tài khoản.

Không dùng cờ `--alias` của `make_loso_splits.py`: đó là chuẩn hoá ép buộc, phải
nhớ gõ đúng ở mọi lần chạy, và không để lại dấu vết. Cơ chế đúng đã có sẵn:

- `config/legacy_signer_mapping.json` → `legacy_name_to_signer_id`
- `scripts/apply_signer_merges.py` → chỉ áp merge do chủ dữ liệu xác nhận, tự nó
  **không suy đoán tên**
- `processed/train_utils/dataset_loader.py` đọc mapping qua `_canonical_signer()`

CSV giữ nguyên tên thô; mapping chỉ là lớp tra cứu.

### ĐÃ XỬ LÝ — chủ dữ liệu xác nhận 2026-07-31

```
Tram      = Trâm                  -> S003   (cùng người, khác dấu)
Thungan   = Thu Ngân  = Ngan      -> S006   (cùng người, 3 tài khoản)
Trân                              -> S001   NGƯỜI KHÁC, không gộp
```

Đã ghi vào `config/legacy_signer_mapping.json` (cả biến thể thường/hoa), thêm
`config/legacy_signer_merge.json` làm hồ sơ xác nhận, và thêm hai hàng
`S003` / `S006` vào `dataset/signers.csv` để `apply_signer_merges.py` chạy sạch.
Số nhóm người ký: **15 chuỗi thô → 12 nhóm**.

`Trân` và `Trâm` được ghi thẳng vào mục `explicitly_not_merged` của cả hai file —
hai chuỗi này chỉ khác một dấu, người sau rất dễ "sửa" nhầm thành một.

### Ba việc đã phát sinh khi làm

1. **File mapping từng MẤT** — chỉ sót bản `.bak_20260727_204104`. Nghĩa là
   `_legacy_signer_map` khi đó **rỗng** và không phép gộp nào có hiệu lực, kể cả
   `Trân`/`Tran`. Đã khôi phục.

2. **Nguyên nhân gốc: `.gitignore` có `*.json` bao trùm**, nên file này chưa bao
   giờ được track — mọi `git clean` / đổi nhánh đều có thể xoá nó. Đã thêm
   `!config/legacy_signer_mapping.json` và `!config/legacy_signer_merge.json`.
   Đây là dữ liệu **không tái tạo được từ bất cứ thứ gì khác trong repo**.

3. **`signer_id` do registry cấp đã đụng không gian tên của bảng legacy.**
   `_next_signer_id()` lấy max+1 từ `dataset/signers.csv` → tài khoản mới tiếp
   theo nhận `S012`, trong khi bảng legacy đã dùng `S012` cho `Nhung`.
   `backend/app/signers.py` giờ cấp từ **S101** trở lên, hai không gian tên rời
   nhau. (Chưa gây hậu quả thật vì `_canonical_signer()` ưu tiên `user_id`, và
   `user_id` chưa bao giờ rỗng — nhưng đó là may, không phải thiết kế.)

Vì sao không đoán: gộp nhầm hai người thành một làm báo cáo sai số người ký;
tách nhầm một người thành hai thì tệ hơn — hai nửa của cùng một người nằm ở cả
train lẫn test, và kết quả "signer-independent" báo ra là kết quả chưa từng đo.
