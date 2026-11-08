# Chủ sở hữu mẫu — vì sao Thùng rác của người đóng góp trống

Ngày 2026-08-01. Ba tồn đọng tìm thấy khi gỡ nhóm E (`dataset.py`, `upload.py`,
`training.py`). Tài liệu này ghi **bằng chứng truy vết**, cách sửa, và những rủi
ro còn lại.

---

## 1. Vấn đề gốc: `samples.csv` không có cột `auth_user_id`

Quyền sở hữu một mẫu được xác định bằng `samples.auth_user_id` (UUID tài khoản),
**không** bằng tên. Nhưng cột đó **chỉ tồn tại trong Postgres**. `samples.csv`
có 31 cột và không có nó.

Hệ quả: mọi dòng đi qua CSV — chuyển máy, khôi phục từ Drive, sync lại — đều vào
Postgres với `auth_user_id = NULL`. Người thu mẫu mở Thùng rác thì **trống**, và
nút "dọn sạch" của họ xoá **0 mẫu** mà vẫn báo thành công.

`ON CONFLICT ... auth_user_id = COALESCE(EXCLUDED.auth_user_id, samples.auth_user_id)`
bảo vệ được giá trị **đã có**, nhưng không tạo ra được giá trị cho dòng **mới**.

### Truy vết 168 dòng

Con số 168 là số dòng `dataset/samples.csv` tăng lên khi gộp dữ liệu máy deploy
(3692 → 3860), **không phải** chênh lệch hiện tại giữa hai máy (bây giờ chỉ còn
15 dòng, toàn `dialect=testdata`, đã cố ý bỏ).

Xác định bằng cách so `samples.csv` với `samples.csv.bak-presync-20260731-130256`:

| `user_id` trong CSV | số mẫu | phương ngữ |
|---|---|---|
| `Khoa` | 110 | `bang-chu-cai` |
| `Trâm` | 45 | `spa` |
| `Thu Ngân` | 11 | `spa` |
| `eeeaeb8b-…fc644` (UUID của Minh) | 2 | `hoa-de` |

Cả 168 dòng đều có `signer_id` rỗng, `collection_campaign` rỗng, `source_type=camera`.

### `backup.sql` KHÔNG cứu được

`backup.sql` ở gốc repo là một `pg_dump` **cũ**: 1016 mẫu, 6 tài khoản. Nó chứa
đúng **2** trong 168 dòng, và cả hai cũng có `auth_user_id` NULL. Đối chiếu với
toàn bộ `samples.csv`: 997/3860 dòng có mặt trong dump, và chỉ **5** dòng có chủ
sở hữu để lấy lại. Dump không phải nguồn khôi phục.

Nhưng nó cho thấy **nguyên nhân lịch sử**:

| trong dump | số dòng |
|---|---|
| `auth_user_id` NULL, `user_id` là **UUID** | 998 |
| `auth_user_id` có, `user_id` là **tên** | 15 |
| `auth_user_id` NULL, `user_id` là tên | 3 |

Bản cũ của ứng dụng ghi **UUID tài khoản vào cột `user_id`** và không ghi
`auth_user_id`. Bản mới ghi tên vào `user_id` và UUID vào `auth_user_id`. Vì vậy
với dữ liệu cũ, **`user_id` chính là chủ sở hữu**, chỉ nằm sai cột.

Trên CSV máy deploy: 992/1357 dòng có `user_id` là UUID của `Minh`.

### Đã sửa

1. **`SAMPLE_FIELDS` thêm `auth_user_id` ở CUỐI** (`dataset_samples.py`).
   Cuối, vì bản mirror Google Sheets ghi header nguyên văn thành dòng 1 — chèn
   giữa sẽ đẩy lệch mọi cột đang có trên Sheets.
2. **`ensure_samples_column()`** — migration idempotent, ghi qua file tạm +
   `os.replace`, đệm cả dòng thiếu cột. Gọi từ `init_db()` **trước** bước sync.
3. **`_uuid_or_none()`** trong `metadata_db` — `""` và tên người → NULL. Không có
   nó, dòng cũ đầu tiên sẽ làm hỏng cả lần sync
   (`invalid input syntax for type uuid: ""`).
4. **`app/cli/backfill_sample_owners.py`** — gắn lại chủ sở hữu từ `user_id`.

### Khớp theo TÊN là sai — cơ sở dữ liệu chứng minh điều đó

Bản đầu của lệnh backfill khớp `user_id` với `users.username`. **Đó là sai**, và
dữ liệu thật bác bỏ nó. Đo trên 3692 dòng đã có chủ (2026-08-01):

| `user_id` (người **ký**) | tài khoản **sở hữu** |
|---|---|
| `Khoa` | Khoa **340** dòng, Minh **129** dòng |
| `Trân` | Minh **620** dòng — tài khoản `Trân` sở hữu **0** |
| `Ảnh` | Minh 405 |
| `Nhung` | Minh 99 |
| `Thư` | Minh 104 |
| `Minh` | Minh 1530, Minh6868 5 |

`user_id` là **người ký**; `auth_user_id` là **tài khoản chạy máy thu**. Một tài
khoản thu cho rất nhiều người ký — đúng như ghi chú `account_ids_not_signers`
trong `legacy_signer_mapping.json` đã cảnh báo. Khớp theo tên sẽ giao **620 mẫu
của Minh cho Trân**, rồi cho Trân quyền xoá chúng.

Lệnh đã được viết lại. Chỉ ba mức đầu được ghi:

| mức | điều kiện | tự động? |
|---|---|---|
| `override` | chủ dữ liệu chỉ định trong `config/sample_owner_overrides.json` | có |
| `uuid` | `user_id` **chính là** `users.id` (bản cũ ghi UUID vào cột này — 998 dòng trong dump) | có |
| `observed` | **mọi** dòng đã có chủ mang cùng `user_id` đều thuộc **một** tài khoản | có |
| `split` | các dòng đó chia cho nhiều tài khoản | **không** |
| `namesake` | có tài khoản trùng tên nhưng **không có bằng chứng nào** | **không** |

`namesake` không bao giờ tự động — đó chính là cái bẫy `Trân`. Và `Trâm` vs
`Trân` cách nhau đúng một dấu, là **hai người khác nhau** (chủ dữ liệu xác nhận
2026-07-31).

Ngược lại, `Thungan` và `Thu Ngân` là **cùng một người nhưng hai tài khoản**.
`config/legacy_signer_merge.json` gộp chúng cho split theo người ký — nhưng
**quyền sở hữu đi theo tài khoản đã thu**, nên ở đây chúng **không** được gộp.
Danh tính người ký và quyền sở hữu tài khoản là hai câu hỏi khác nhau.

### Kết quả chạy thật (2026-08-01)

Sau khi gỡ `docker-compose.yml`, dựng Postgres và chạy `init_db`:

```
classes:     CSV 63,   DB 56   -> thêm 7
samples:     CSV 3860, DB 3692 -> thêm 168
raw_uploads: CSV 14,   DB 14   -> không thiếu
```

Đúng con số dự đoán, và khoảng trống chủ sở hữu xuất hiện đúng như đã cảnh báo:
**3860 dòng / 3694 có chủ / 168 thiếu**.

Báo cáo backfill trên 168 dòng đó:

| `user_id` | số mẫu | mức | kết luận |
|---|---|---|---|
| `Khoa` | 110 | `split` | 469 mẫu cùng tên chia cho 2 tài khoản |
| `Trâm` | 45 | `none` | không có tài khoản khớp, không có mẫu cùng tên đã có chủ |
| `Thu Ngân` | 11 | `none` | như trên |
| `eeeaeb8b-…` | 2 | `uuid` | chính là id tài khoản Minh |

**Chỉ 2/168 khôi phục được trên máy này.** Đã ghi 2 dòng đó và đẩy 3694 ô
`auth_user_id` ngược vào `samples.csv` (kiểm chứng: 0 ô thuộc cột khác bị đổi).

166 dòng còn lại **chỉ Postgres của máy deploy mới trả lời được**. Cách đúng:
chạy `--apply --write-csv` **trên máy deploy** (ở đó DB có sẵn chủ sở hữu), rồi
mang `samples.csv` đó về — cột `auth_user_id` bây giờ đi cùng file.

```bash
docker compose run --rm backend python -m app.cli.backfill_sample_owners
docker compose run --rm backend python -m app.cli.backfill_sample_owners --apply --write-csv
```

`--write-csv` ghi ngược vào `samples.csv` để lần chuyển máy sau không mất nữa.
`backfill_sample_owner()` chỉ động vào dòng `auth_user_id IS NULL`, nên chạy lại
với ánh xạ sai cũng **không thể** ghi đè chủ sở hữu đúng.

---

## 2. Thao tác hàng loạt trên Thùng rác

**Trước:** `_user_owns_sample()` gọi `get_sample_owner()` **một truy vấn mỗi
uid** — chọn 200 mẫu là 200 vòng. Và uid không thuộc về mình bị **lọc im lặng**:
chọn 10, sở hữu 7, thông báo "Đã khôi phục 7 mẫu", không nhắc 3 cái còn lại.

**Sau:** `partition_sample_ownership()` — **một** truy vấn, **bốn** rổ:

| rổ | nghĩa |
|---|---|
| `owned` | của mình |
| `foreign` | của tài khoản khác |
| `unowned` | `auth_user_id` NULL — dữ liệu cũ, cần admin |
| `missing` | không có trong DB |

Bốn rổ chứ không phải hai, vì "không phải của bạn" có ba nguyên nhân rất khác
nhau. Riêng `unowned` là toàn bộ dữ liệu lịch sử ở mục 1 — báo nó là "của người
khác" là nói sai với chính người đã thu nó.

API trả thêm `skipped_count` và `skipped` (kèm lý do + tối đa 20 uid ví dụ), và
câu thông báo có phần đuôi: *"Bỏ qua 3 mẫu: 2 thuộc về tài khoản khác; 1 chưa
gắn chủ sở hữu (dữ liệu cũ) — cần admin."*

Khi DB lỗi, mọi uid rơi vào `missing` → **từ chối cả lô**. Hướng an toàn là
hướng này: coi chủ sở hữu không đọc được là "của bạn" sẽ cho một người đóng góp
xoá vĩnh viễn dữ liệu của người khác ngay giữa lúc sự cố.

Hàm hỗ trợ thêm trong `metadata_db.py`: `list_users_basic()`,
`sample_owner_gap_report()` (gom theo `user_id` → biến "3855 dòng vô chủ" thành
"Khoa: 110, Trâm: 45, …"), `backfill_sample_owner()`.

Kiểm thử: `backend/tests/test_sample_ownership.py` — 34 test, không cần DB.

---

## 3. `promoted_at` mồ côi — ĐÃ sửa bằng `superseded_at`

`training.py` đổi khoá slot realtime từ `model_id = training_<job_id>` sang
**`model_id = dialect`**: một phương ngữ = một model, promote bản mới **thay**
bản cũ trong `models.json`.

Nhưng `job.promoted_at` vẫn được đặt cho job mới mà **không có gì xoá của job
cũ**. Sau lần promote thứ hai cho `hoa-de`, DB có **hai job cùng mang
`promoted_at`** trong khi chỉ một đang phục vụ.

Điều đáng chú ý: **repo đã có sẵn lời giải đúng** ở
`experiment_tracking_api_revised.py::promote_model_version()`, chạy trên bảng
`model_versions` với unique index `idx_one_production_per_dialect` — nó archive
bản production cũ (`status='archived', promoted_at=NULL`) rồi mới promote bản
mới, **trong một transaction**, có chống đua. `training_jobs` là đường cũ hơn và
đơn giản hơn, chỉ là chưa bao giờ được nâng lên cùng mức.

**Đã chọn:** thêm cột `superseded_at` thay vì xoá `promoted_at`. Lý do: "được
promote lúc T1, bị thay lúc T2" là dữ kiện kiểm toán đáng giữ (và có ích cho
luận văn), còn retention sweep thì cần phân biệt checkpoint đang sống với
checkpoint đã nghỉ.

- `supersede_other_promotions(job_id, dialect)` — **hai lệnh trong một
  transaction** (`_cursor()` commit khi thoát), trả về danh sách job vừa bị thay.
- `dialect` đọc từ `config->'dialects'->>0` vì `training_jobs` **không có** cột
  dialect; `COALESCE(..., 'multi')` khớp mặc định của router.
- Router quét luôn **cache in-memory**: `_ensure_job_loaded()` không đọc lại job
  đã kết thúc, nên chỉ sửa DB thì UI vẫn hiện cờ cũ tới lần khởi động sau.
- `superseded_at` **không** nằm trong `SQL_UPSERT_TRAINING_JOB` — chỉ một hàm sở
  hữu cột này, để một lần cập nhật trạng thái thường không làm sống lại cờ cũ.
- Ghi hỏng ở bước này **không** làm hỏng promote: model đã phục vụ rồi.

"Đang phục vụ" = `promoted_at IS NOT NULL AND superseded_at IS NULL`.

Kiểm thử: `backend/tests/test_promotion_supersede.py` — 13 test, không cần DB.

---

## 4. Bảng `dialects` cũ nuốt mất danh mục phương ngữ — ĐÃ xử lý

Khi chạy `init_db` thật, log hiện:

```
migration statement failed (ignored): column "tenant_id" does not exist
vocabulary registry seed skipped: column "tenant_id" of relation "dialects" does not exist
```

Máy này **đã có sẵn** một bảng `dialects` từ schema cũ:

```
code varchar(50) PK | language_code varchar(50) FK->languages | name text
```

với 8 dòng — và `CREATE TABLE IF NOT EXISTS dialects (...)` của danh mục mới
**im lặng không làm gì**. Ba bảng kia (`recognition_profiles`, `dialect_aliases`,
`vocabulary_registry_meta`) tạo được, riêng `dialects` thì không → **toàn bộ đợt
1 của danh mục phương ngữ chưa thực sự cài lên máy này**, và sẽ chưa cài được
trên bất kỳ máy nào có bảng cũ.

### Kiểm tra phạm vi ảnh hưởng trước khi động vào

| kiểm tra | kết quả |
|---|---|
| FK trỏ **vào** `dialects` | **không có** — chỉ một FK đi ra `languages` |
| code đọc schema cũ (`code`/`name`/`language_code`) | **0 chỗ** trong toàn repo |
| SOT có xuất bảng `dialects` | **không** — chỉ `classes`/`samples`/`raw_uploads` |
| `processed/` (bộ train) đọc DB | **không đọc một dòng nào** — chỉ đọc snapshot JSON |
| 8 dòng bảng cũ vs `config/dialects.seed.csv` | **trùng khít cả 8** (Chung, Miền Bắc, Hòa Đê, Bảng chữ cái, …) |

Nghĩa là bảng cũ không giữ thứ gì độc nhất. **Đã DROP.**

### Cách sửa

Lệnh dọn là **phần tử đầu tiên của `DDL_STATEMENTS`**, có guard theo hình dạng
bảng (`có code` AND `không có dialect_id`) nên chạy lại là no-op.

Thứ tự quan trọng và **trải qua hai danh sách**: `ensure_tables()` chạy
`DDL_STATEMENTS` trước, rồi mới `MIGRATION_STATEMENTS` — nơi `CREATE TABLE IF
NOT EXISTS dialects` thật sự nằm. Đặt lệnh DROP vào `MIGRATION_STATEMENTS` sẽ
làm nó chạy **sau** khi `CREATE` đã no-op → máy mất hẳn bảng `dialects` tới lần
khởi động sau.

### Khoá ngoại — kế hoạch cũ ghi sai

`MERGE_WORK_LOG.md` ghi "cắm FK `classes.dialect → dialects(dialect_id)`".
Postgres **từ chối**: khoá chính là `(tenant_id, dialect_id)` nên
`dialect_id` một mình không unique — *"there is no unique constraint matching
given keys"*. Phải composite:

```sql
FOREIGN KEY (tenant_id, dialect) REFERENCES dialects(tenant_id, dialect_id)
  ON UPDATE CASCADE
```

`ensure_vocabulary_foreign_keys()` cắm cho **cả `classes` và `samples`**, chạy
**sau seed** (FK không thể trỏ tới hàng chưa tồn tại) và **trước sync**. Mọi lỗi
được ghi log chứ không raise: thiếu FK thì yếu đi, nhưng raise sẽ chặn khởi động
đúng lúc người vận hành cần app sống để đi sửa dữ liệu.
`unregistered_dialects_in_use()` gọi tên trước những giá trị sẽ chặn FK.

### Kết quả chạy thật

```
[VOCAB_FK] classes.dialect -> dialects(dialect_id) đã cắm
[VOCAB_FK] samples.dialect -> dialects(dialect_id) đã cắm
vocabulary FK: {'classes': 'added', 'samples': 'added'}
→ chạy lần 2: {'classes': 'exists', 'samples': 'exists'}
```

Kiểm chứng FK **thật sự chặn**:

```
INSERT INTO classes(... dialect) VALUES (... 'phuong-ngu-bia-dat');
ERROR: violates foreign key constraint "classes_dialect_fkey"
DETAIL: Key (tenant_id, dialect)=(default, phuong-ngu-bia-dat) is not present in table "dialects".
```

Giá trị hợp lệ (`hoa-de`) vẫn qua. Dữ liệu nguyên vẹn: 63 lớp, 3860 mẫu, 9
phương ngữ, 6 profile.

**Và bộ train hết chạy bằng giá trị gắn sẵn.** Trước đó
`dataset/vocabulary_registry.json` **không tồn tại** nên `RECOGNITION_PROFILES`
rơi về `_FALLBACK_PROFILES`. Sau seed:

```
RECOGNITION_PROFILES = ('alphabet','central','hoa_de','legacy_unassigned','north','south')
registry_version     = 2
đang dùng fallback?  False
```

Kiểm thử: `backend/tests/test_dialect_registry_migration.py` — 11 test.

---

## 5. Rủi ro còn lại

| rủi ro | mức | ghi chú |
|---|---|---|
| Bảng `dialects` cũ chặn danh mục | **đã xử lý** | mục 4 — đã DROP + seed + FK, chạy 2 lần idempotent |
| FK chặn ghi khi thêm phương ngữ mới | trung bình | phải tạo dòng `dialects` **trước** khi ghi lớp/mẫu. Luồng `create_dialect` (status `pending`) đã ghi dòng ngay nên vẫn chạy được; nhưng script ngoài app ghi thẳng SQL sẽ bị chặn — đó là chủ ý |
| 166 dòng vẫn vô chủ | **cao** | chỉ Postgres máy deploy trả lời được; tạm thời chỉ admin thấy chúng |
| Sheets thêm một cột ở cuối | thấp | mirror ghi header động; cột mới nằm sau cùng |
| UUID tài khoản lộ ra Sheets | thấp | `user_id` vốn đã chứa UUID ở 992 dòng máy deploy |
| Migration CSV chạy lúc đang có writer | thấp | dùng chung `FileLock` với mọi writer khác |
| Test ghi vào catalog thật | **đã chặn** | `init_db()` migrate `samples.csv`; `test_init_db_fallback.py` có fixture `autouse` mock nó — đã xảy ra một lần 2026-08-01, dữ liệu không mất |
| `Trâm`/`Trân` bị gộp nhầm về sau | trung bình | `namesake` không tự động + `test_auto_tiers_are_exactly_the_three_sound_ones` |
| `--write-csv` chạy khi đang thu mẫu | trung bình | ghi lại cả file; nên chạy lúc rảnh |
| Hai admin promote cùng lúc | thấp | `supersede_other_promotions` chống được phần DB, nhưng `models.json` là file — vẫn có thể đua |
