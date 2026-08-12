# Danh sách gắn sẵn & giá trị bịa — kiểm kê toàn hệ thống

Ngày 2026-08-01. Xuất phát từ một lỗi cụ thể: script đồng bộ dataset ghi
`recognition_profile = "spa"`, mà `spa` không phải một profile hợp lệ. Tài liệu
này trả lời câu hỏi *"lỗi này còn ở chỗ nào khác không"* — có, và nó có **hai
dạng** khác nhau, cần hai cách sửa khác nhau.

---

## Dạng 1 — Danh sách đáng lẽ là DỮ LIỆU nhưng lại gắn sẵn trong mã

> **Cập nhật 2026-08-01 — đợt 1 ĐÃ LÀM XONG.** Bảng đăng ký trong Postgres,
> `app/vocabulary_registry.py`, router `/vocabulary`, task gộp
> `app/catalog_migrations.py`, 14 test. Con số dưới đây là hiện trạng TRƯỚC khi
> sửa, giữ lại làm hồ sơ. Xem §"Đã làm" ở cuối.

Đo được: hệ thống hiện có **6 bản** danh sách phương ngữ / profile nằm rải rác,
**và chúng không khớp nhau** — sau đó test T3 tìm thêm bản thứ 7
(`frontend/src/pages/LabelsPage.tsx`), và việc gỡ merge lộ ra rằng bản #3/#4
thực chất là **hai hàm `normalize_dialect` cùng tên, cái sau che cái trước**.

| # | nơi | nội dung | sai lệch đo được |
|---|---|---|---|
| 1 | `processed/shared/vocabulary.py:29` `RECOGNITION_PROFILES` | `alphabet, north, central, south, hoa_de` | đây là **allow-list dùng để validate**; không có `spa` |
| 2 | `backend/app/config.py:129` `recognition_profiles_raw` | `north, central, south, hoa_de` | thiếu `alphabet`, **và KHÔNG AI ĐỌC BIẾN NÀY** — khai báo rồi bỏ đó, `.env` cũng không đặt |
| 3 | `backend/app/dataset_manager.py` `robust_mapping` (bản 1) | 17 khoá | |
| 4 | `backend/app/dataset_manager.py` `robust_mapping` (bản 2) | 15 khoá | **bản sao gần trùng của #3 trong CÙNG một file**, thiếu `bang-chu-cai` |
| 5 | `frontend/src/config/dialectLabels.ts` | bản HEAD 8 khoá | thiếu `common` và `spa` → lớp spa hiện không có tên hiển thị |
| 6 | `frontend/src/components/FullscreenCaptureModal.tsx:100,140,144,194` | bảng tên thứ hai + `ALPHABET_DIALECT_KEYS` | bản sao thứ 3 của cùng thông tin |

Đối chiếu với dữ liệu thật (`labels.csv` + `samples.csv`):

```
dialect CÓ THẬT      : bac, bang-chu-cai, can-tho, common, hoa-de, nam, spa, trung
backend không biết   : spa
frontend HEAD thiếu  : common, spa
frontend có nhưng KHÔNG có dữ liệu : ha-noi, saigon      <- mục ma
```

`spa` lọt qua `normalize_dialect()` chỉ nhờ nhánh `return slug` cuối hàm — tức là
**hành vi đúng đang đến từ chỗ code bó tay, không phải từ chỗ code hiểu**.

### Phân biệt quan trọng: enum của lược đồ vs danh sách nghiệp vụ

Không phải hằng số nào cũng nên biến thành dữ liệu:

| hằng số | nên để đâu | vì sao |
|---|---|---|
| `VALID_SCOPES = (common, profile_specific)` | **giữ trong mã** | Đúng 2 giá trị theo định nghĩa lược đồ v2; thêm giá trị thứ 3 là đổi lược đồ, phải sửa code kèm theo |
| `MOTION_TYPES = (static, dynamic, mixed)` | **giữ trong mã** | như trên |
| `RECOGNITION_PROFILES` | **phải là dữ liệu** | mở, tăng theo nghiệp vụ; thêm `spa` không cần sửa dòng code nào |
| bảng tên phương ngữ | **phải là dữ liệu** | thuần hiển thị, thay đổi thường xuyên |

### Cảnh báo phải nói trước khi làm

**Không thể suy allow-list ra bằng `SELECT DISTINCT recognition_profile FROM classes`.**
Làm vậy là vòng tròn: chính giá trị sai `spa` mà tôi ghi nhầm hôm qua sẽ tự
biến mình thành hợp lệ, và bộ kiểm tra mất sạch tác dụng — 7 lớp vi phạm sẽ
không bao giờ bị phát hiện.

Cách đúng: một **bảng đăng ký** do chủ dữ liệu quản lý (dữ liệu, không phải mã),
tách khỏi bảng `classes` mà nó dùng để kiểm tra. Gieo mầm từ những giá trị đang
có, nhưng từ đó về sau chỉ người quản trị mới thêm được. Vẫn là "lấy từ
database" đúng như yêu cầu — chỉ khác là lấy từ bảng đăng ký chứ không phải từ
chính dữ liệu đang cần kiểm.

---

## Dạng 2 — Bịa giá trị: lấy trường này điền cho trường khác

Đây là lỗi gốc. Tìm được **2 chỗ**, cùng một khuôn:

### 2.1 Script đồng bộ dataset — ĐÃ GÂY HẬU QUẢ, ĐÃ SỬA

```python
if "recognition_profile" in out and not out["recognition_profile"]:
    out["recognition_profile"] = (r.get("dialect") or "").strip()
```

`dialect` và `recognition_profile` **không phải một thứ**: `dialect` là thư mục
lưu trữ vật lý (đã bị khai tử về mặt ngữ nghĩa trong lược đồ v2), còn
`recognition_profile` quyết định model nào được huấn luyện. Với `bang-chu-cai` /
`hoa-de` thì vô hại vì hai dialect đó vốn đã có giá trị; với `spa` thì nó đẻ ra
một profile không tồn tại.

Hậu quả đo được: **7/63 lớp vi phạm `validate_label_v2`**. Đã sửa về
`legacy_unassigned` + `vocabulary_group=spa` cho khớp 2 lớp cũ → **0/63**.

### 2.2 `scripts/make_loso_splits.py:381` — CÙNG LỖI, CHƯA SỬA

```python
'recognition_profile': args.recognition_profile or args.dialect or 'all',
```

Ghi `dialect` vào ô `recognition_profile` của manifest split. Chưa gây thiệt hại
thấy được (manifest chỉ để ghi chép), nhưng nó là **siêu dữ liệu của một thí
nghiệm** — một split ghi `recognition_profile: spa` mô tả sai chính nó, và bất
kỳ ai đọc lại sau này sẽ tin. Nên để rỗng thay vì bịa.

### 2.3 Không phải lỗi: `language` mặc định `"vn"`

15 chỗ trong backend dùng `or "vn"`. Đây **không** cùng loại: hệ thống hiện chỉ
thu thập tiếng Việt, `vn` là mặc định thật chứ không phải suy ra từ trường khác.
Ghi ở đây để khỏi phải rà lại.

---

## Dạng 3 — Phương ngữ KHÔNG có vòng đời: nó ra đời như tác dụng phụ

Đây mới là gốc của hai dạng trên. Hiện tại **không tồn tại khái niệm "danh sách
phương ngữ"** ở bất cứ đâu — không bảng, không file, không endpoint.

### Nút "Khác (+)" ở live capture không lưu gì cả

`frontend/src/components/FullscreenCaptureModal.tsx:2556`

```jsx
<AddDialectModal onAdd={(name) => {
  const updated = Array.from(new Set([...dialectList, name]));
  setDialectList(updated); setDialect(name);
  setPreference("dialectSelected", name);
}} />
```

Không một lời gọi API. Phương ngữ mới chỉ sống trong `useState` của React và
`localStorage` của đúng trình duyệt đó — **F5 là mất**. Nó chỉ trở nên "có thật"
khi ai đó thu xong một mẫu mang giá trị ấy, tức là phương ngữ **ra đời như một
tác dụng phụ của việc ghi dữ liệu**, và chuỗi người dùng gõ tay trở thành khoá.

Gõ `Miền bắc` thay vì `Miền Bắc` là sinh ra một phương ngữ khác. Không có gì
chặn, không có gì cảnh báo.

### Dropdown được dựng lại bằng cách quét dữ liệu

`FullscreenCaptureModal.tsx:1042`

```js
serverDialects = classes.map(row => displayDialectLabel(row.dialect))
mergedDialects  = [...serverDialects, ...DEFAULT_DIALECTS]
```

và `displayDialectLabel` (dòng 243) rơi về `return value?.trim()` khi slug không
có trong `DIALECT_LABELS`. Hai hệ quả nhìn thấy được trên ảnh chụp màn hình:

1. **Dropdown trộn hai loại chuỗi.** `Bắc`, `Nam` là *tên hiển thị* (có trong
   map); `spa`, `testdatase` là *slug thô* (không có trong map). Người dùng
   chọn cái nào thì đúng chuỗi đó được gửi lên server.
2. **`testdatase` trở thành lựa chọn cho người thu thật.** Danh sách được suy ra
   bằng `DISTINCT dialect` trên dữ liệu, mà dữ liệu thì có cả rác test — nên
   rác test tự thăng cấp thành mục menu. Không có chỗ nào để đánh dấu
   "phương ngữ này đã ngừng dùng".

### Hai màn hình, hai danh sách khác nhau

| màn hình | nguồn | kết quả |
|---|---|---|
| Live capture | `DISTINCT dialect` từ dữ liệu **+** `DEFAULT_DIALECTS` | `spa`, `Nam`, `Bắc`, `testdatase`, … |
| Thư viện nhãn | chỉ `DIALECT_LABELS` gắn sẵn | `Chung, Miền Bắc, Miền Nam, Cần Thơ, Miền Trung, Hòa Đê` |

Cùng một hệ thống, cùng một lúc, hai bộ phương ngữ. Thư viện nhãn **không có**
`spa` và `bang-chu-cai` dù dữ liệu có; live capture **có** rác test dù không nên.

---

## Đề xuất — Postgres là nguồn sự thật, file chỉ là bản xuất khẩu

Khác với `labels.csv` / `samples.csv` (nơi CSV là nguồn sự thật và Postgres là
bản sao — xem `csv-to-db-mirror`), **hai bảng đăng ký này đi ngược lại**:
Postgres giữ bản gốc, file chỉ là bản xuất có đóng dấu.

Lý do không phải sở thích, mà vì **chỉ Postgres mới cưỡng chế được**:

| | CSV làm gốc | Postgres làm gốc |
|---|---|---|
| chặn giá trị lạ | phải nhớ gọi hàm validate | **FOREIGN KEY từ chối tại chỗ** |
| hai tiến trình cùng ghi | FileLock, dễ sót | transaction |
| ai thêm, lúc nào | không có | audit được |
| đọc từ script trên host | trực tiếp | cần bản xuất (xem dưới) |

Dòng thứ nhất là điểm quyết định. Nếu `classes.recognition_profile` có FK trỏ
sang `recognition_profiles(profile_id)`, thì lỗi `spa` **không thể xảy ra** —
không phải "bị phát hiện sau", mà `INSERT` bị Postgres từ chối ngay. Đó chính là
thứ mà một file CSV không bao giờ làm được.

### Ràng buộc thật đã đo được

| môi trường | với tới Postgres? |
|---|---|
| backend, worker, **trainer**, celery_beat | **CÓ** — trainer chạy cùng image `voya_backend`, có `env_file: .env`, `depends_on: postgres` |
| script chạy trực tiếp trên host (`python scripts/make_loso_splits.py`, `compute_baselines.py`, pytest ngoài docker) | **KHÔNG** — service `postgres` không có khối `ports:`, chỉ với tới được từ trong `voya_network` |

Nên `processed/shared/vocabulary.py` (stdlib-only) **không cần** gọi DB: nó đọc
bản xuất. Bản xuất **không phải nguồn sự thật thứ hai** — nó được ghi lại sau mỗi
lần bảng đăng ký đổi, và mang theo dấu để phát hiện lạc hậu:

```
dataset/vocabulary_registry.json     <- SINH RA, đừng sửa tay
{
  "exported_at": "...", "registry_version": 7,
  "dialects":  [{"dialect_id": "bac", "display_name": "Miền Bắc", ...}],
  "profiles":  [{"profile_id": "alphabet", "is_trainable": true, ...}]
}
```

`registry_version` là một số nguyên tăng dần trong DB. Script trên host so số
này với `registry_version` ghi trong manifest của split; lệch thì **báo lỗi
thẳng**, không âm thầm dùng bản cũ. Đây là chỗ mà cách làm cũ (`config/*.json`
chép tay) đã hỏng — file mất mà không ai biết.

### Bước 1 — hai bảng trong Postgres

```sql
CREATE TABLE recognition_profiles (
    profile_id    TEXT PRIMARY KEY,          -- alphabet, north, central, south, hoa_de
    display_name  TEXT NOT NULL,
    is_trainable  BOOLEAN NOT NULL DEFAULT TRUE,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    tenant_id     TEXT NOT NULL DEFAULT 'default',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE dialects (
    dialect_id    TEXT PRIMARY KEY,          -- slug do SERVER sinh
    display_name  TEXT NOT NULL,             -- chuỗi người dùng gõ
    language      TEXT NOT NULL DEFAULT 'vn',
    is_alphabet   BOOLEAN NOT NULL DEFAULT FALSE,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    tenant_id     TEXT NOT NULL DEFAULT 'default',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by    UUID REFERENCES users(id)
);
```

Gieo mầm đúng những gì đang tồn tại: 5 profile + `legacy_unassigned`
(`is_trainable=0`), và 8 dialect có thật. `spa` vào bảng `dialects` (nó LÀ một
dialect có thật), nhưng **không** vào `recognition_profiles` — chờ anh quyết.
`testdatase` vào với `is_active=0`.

### Bước 2 — FK, nhưng theo đúng thứ tự

```sql
-- chỉ chạy được SAU khi bảng đăng ký đã gieo mầm và dữ liệu đã sạch
ALTER TABLE classes ADD CONSTRAINT classes_dialect_fkey
    FOREIGN KEY (dialect) REFERENCES dialects(dialect_id);
```

Postgres từ chối tạo FK khi còn hàng vi phạm — nên phải gieo mầm trước, và
`verify_integrity_constraints()` đã có sẵn cơ chế báo "ràng buộc KHÔNG có hiệu
lực + còn bao nhiêu hàng chặn nó". Cắm hai ràng buộc mới vào đó là xong.

`recognition_profile` **chưa** cắm FK ngay: cột này còn chứa `legacy_unassigned`
và chuỗi rỗng. Cắm sau khi bước 3 chạy đủ lâu.

### Bước 3 — chặn bịa giá trị tại cửa ghi

FK chặn ở tầng DB, nhưng thông báo lỗi của Postgres thì người dùng không đọc
được. Thêm một tầng ở `upsert_class` / `register_class`:

```python
profile = (row.get("recognition_profile") or "").strip()
if profile and profile not in known_profiles():
    raise ValueError(
        f"recognition_profile '{profile}' không có trong bảng đăng ký. "
        f"Để TRỐNG nếu chưa xác định — đừng suy từ dialect."
    )
```

Nguyên tắc đằng sau, áp cho mọi trường:

> **Rỗng là một trạng thái hợp lệ và trung thực. Một giá trị sai thì không.**
> Không bao giờ điền trường này bằng giá trị của trường khác.

Lý do đây không phải chuyện phong cách: một ô rỗng sẽ hiện trong báo cáo cần rà
soát và có người xử lý. Một ô đã điền sai thì **không ai đi kiểm lại** — nó trông
như đã xong.

### Bước 4 — bỏ `settings.recognition_profiles_raw`

Chết hẳn: không ai đọc, không ai đặt, và nội dung sai. Giữ lại chỉ tạo ảo giác
là có chỗ cấu hình.

### Bước 5 — vòng đời của một phương ngữ mới

Đây là phần trả lời câu hỏi *"thêm 1 phương ngữ ở live capture thì các chức năng
khác có thấy không"*. Hiện tại: **không**. Sau khi làm:

```
Người dùng bấm "Khác (+)"  ->  POST /vocabulary/dialects {display_name}
                                 |
                                 v
                   backend slug hoá -> INSERT vào Postgres (nguồn sự thật)
                   -> tăng registry_version -> xuất lại
                      dataset/vocabulary_registry.json cho script trên host
                                 |
                                 v
      MỌI màn hình gọi GET /vocabulary/dialects và nhận cùng một danh sách:
      live capture · thư viện nhãn · trang huấn luyện · bộ lọc thống kê
```

Ba tính chất phải có, thiếu cái nào là quay lại tình trạng cũ:

1. **Một cửa ghi duy nhất.** Chỉ endpoint đó tạo được phương ngữ. Không màn hình
   nào được phép "tự thêm vào state rồi thôi".
2. **`dialect_id` là slug do server sinh, `display_name` là thứ người dùng gõ.**
   Hôm nay hai thứ này đang bị trộn làm một, nên `Miền Bắc` và `bac` cùng đi
   trong một dropdown. Tách ra thì gõ hoa/thường/có dấu thế nào cũng về đúng một
   slug, và đổi tên hiển thị sau này không đụng tới dữ liệu đã thu.
3. **`is_active`.** Rác như `testdatase` được tắt chứ không xoá — dữ liệu cũ vẫn
   tra ngược được, nhưng nó biến khỏi mọi dropdown.

---

## Cách kiểm tra — 4 test, không cái nào cần chạy tay

Kiểm bằng mắt sẽ hỏng lại sau vài tháng. Bốn bất biến dưới đây bắt đúng bốn cách
hệ thống đã hỏng lần này:

### T1 — không có phương ngữ mồ côi
```
Mọi dialect xuất hiện trong classes / samples PHẢI có trong bảng dialects.
```
Bắt được: dữ liệu sinh ra ngoài cửa ghi (chính là cách `testdatase` lọt vào).
Khi FK ở bước 2 đã cắm được thì test này thành **thừa** — Postgres cưỡng chế
sẵn. Giữ nó cho tới lúc đó, và giữ luôn cho lớp CSV (CSV không có FK).

### T2 — không có mục ma
```
Mọi dialect_id is_active=1 nên có ÍT NHẤT một lớp, hoặc is_seeded=1
(cố ý tạo trước, chưa thu).
```
Bắt được: `ha-noi` / `saigon` — hiện trong menu nhưng không có dữ liệu nào.

### T2b — bản xuất không lạc hậu
```
vocabulary_registry.json.registry_version == SELECT registry_version FROM ...
```
Bắt được: bản xuất quên cập nhật — tức là kịch bản đã làm mất
`legacy_signer_mapping.json` và `legacy_vocabulary_mapping.json`, lần này
được phát hiện thay vì im lặng.

### T3 — không còn danh sách gắn sẵn (test quét mã nguồn)
```
Không file .ts/.tsx/.py nào (ngoài dialects.csv và test này) được chứa
một mảng/dict liệt kê từ 3 slug phương ngữ trở lên.
```
Bắt được: cả 6 bản gắn sẵn ở Dạng 1, và chặn bản thứ 7 ra đời. Đây là loại test
xấu xí nhưng hiệu quả — nó là thứ duy nhất ngăn được việc ai đó "tiện tay" thêm
lại một bảng tên vào một component mới.

### T4 — vòng đời đi hết một vòng (test tích hợp)
```
POST /vocabulary/dialects {display_name: "Miền Tây"}
  -> GET /vocabulary/dialects       chứa dialect_id="mien-tay"
  -> GET /classes?dialect=mien-tay  trả 200, rỗng
  -> tạo 1 lớp trong mien-tay       -> lớp hiện ra
  -> GET /training/options          "mien-tay" có trong dialects theo language
  -> KHÔNG deploy lại frontend      dropdown vẫn có nó
```
Bắt được: đúng câu hỏi được đặt ra — thêm ở một chỗ thì các chỗ khác có thấy không.

Bổ sung: **T1 và T2 nên chạy trong `verify_deployment.py`**, không chỉ trong CI.
Máy deploy là nơi dữ liệu lệch, và nó đã lệch một lần rồi.

---

## Phạm vi "làm gọn" — chính xác là những gì

Chia làm hai đợt vì merge còn dở, và đợt 1 đã đủ chặn dữ liệu sai mới sinh ra.

### Đợt 1 — trong lúc còn merge (không đụng file frontend đang xung đột)

| # | việc | file |
|---|---|---|
| 1 | 2 bảng `dialects` + `recognition_profiles` + gieo mầm | `metadata_db.py` MIGRATION_STATEMENTS |
| 2 | `registry_version` + hàm xuất `vocabulary_registry.json` | `app/vocabulary_registry.py` (mới) |
| 3 | `validate_label_v2` đọc bản xuất thay cho tuple gắn sẵn | `processed/shared/vocabulary.py` |
| 4 | chặn tại cửa ghi (bước 3 ở trên) | `dataset_manager.register_class`, `metadata_db.upsert_class` |
| 5 | gộp 2 bản `robust_mapping` thành 1, đọc từ bảng đăng ký | `dataset_manager.py` |
| 6 | xoá `recognition_profiles_raw` | `config.py` |
| 7 | sửa chỗ bịa giá trị còn lại | `scripts/make_loso_splits.py:381` |
| 8 | `GET /vocabulary/registry` | router mới |
| 9 | T1, T2, T2b, T3 | `backend/tests/` |
| 10 | T1+T2 chạy trong verify_deployment | `cli/verify_deployment.py` |

Sau đợt 1: **không tạo được lớp/mẫu với phương ngữ hay profile lạ nữa**, kể cả
qua API, kể cả qua script. Frontend vẫn dùng bảng gắn sẵn nhưng chỉ để *hiển
thị* — sai lệch còn lại chỉ là cái tên, không còn là dữ liệu hỏng.

### Đợt 2 — sau khi gỡ xong nhóm frontend

| # | việc |
|---|---|
| 11 | `dialectLabels.ts` + `FullscreenCaptureModal.tsx` + `LabelsPage.tsx` nạp từ `/vocabulary/registry`, xoá cả 3 bản gắn sẵn |
| 12 | "Khác (+)" gọi `POST /vocabulary/dialects` thay vì chỉ `setState` |
| 13 | tách hiển thị khỏi giá trị: dropdown hiện `display_name`, gửi lên `dialect_id` |
| 14 | T4 (tích hợp trọn vòng) |
| 15 | FK `classes.recognition_profile` sau khi dữ liệu đã sạch đủ lâu |

### Chạy được lâu dài nhờ đâu

Bốn thứ, xếp theo độ bền — cái sau không phụ thuộc vào việc ai đó có nhớ hay không:

1. **FK trong Postgres** — không phụ thuộc vào con người chút nào. Thêm phương
   ngữ lạ là `INSERT` bị từ chối, ở mọi đường ghi, kể cả `psql` gõ tay.
2. **T3 quét mã nguồn** — chặn bản gắn sẵn thứ 7 ra đời. Xấu xí, nhưng nó là thứ
   duy nhất ngăn được việc tiện tay thêm lại một bảng tên vào component mới.
3. **`registry_version`** — bản xuất lạc hậu bị báo lỗi thay vì âm thầm dùng bản cũ.
4. **`is_active` thay vì xoá** — rác test biến khỏi menu mà dữ liệu cũ vẫn tra
   ngược được; không ai phải chọn giữa "xoá mất lịch sử" và "để rác trong menu".

Điều KHÔNG bền, và vì vậy không nên dựa vào: quy ước, tài liệu, và trí nhớ. Cả
ba đã có sẵn trong dự án này rồi — `vocabulary.py` ghi rõ `spa` không phải
profile — mà vẫn không ngăn được lỗi.

---

## ĐÃ LÀM — đợt 1, ngày 2026-08-01

| việc | nơi |
|---|---|
| 4 bảng: `dialects`, `recognition_profiles`, `dialect_aliases`, `vocabulary_registry_meta` — `PRIMARY KEY (tenant_id, …)` sẵn cho multitenant | `metadata_db.py` MIGRATION_STATEMENTS |
| cửa ghi duy nhất: slug hoá, chống trùng, duyệt, gộp, xuất snapshot, phân quyền pending | `app/vocabulary_registry.py` (mới) |
| gộp **hai** `normalize_dialect` thành một, đọc registry; chỉ giữ `_INPUT_ALIASES` | `dataset_manager.py` |
| chặn tại cửa ghi `_assert_known_dialect` (fail-open khi DB lỗi) | `dataset_manager.register_class` |
| `RECOGNITION_PROFILES` đọc snapshot, tuple cũ tụt xuống fallback | `processed/shared/vocabulary.py` |
| xoá `recognition_profiles_raw` chết | `config.py` |
| bỏ `or args.dialect` | `scripts/make_loso_splits.py` |
| `GET /vocabulary/registry`, `POST /dialects`, duyệt / từ chối-kèm-gộp / đổi tên / vô hiệu hoá | `routers/vocabulary.py` (mới) |
| task gộp đúng thứ tự an toàn, mọi bước idempotent | `app/catalog_migrations.py` (mới) |
| T1 T2 T2b T3 + slug — 14 test, không cần DB | `tests/test_vocabulary_registry.py` |
| T1 / T2 / T5 khi kiểm máy deploy | `cli/verify_deployment.py` |
| hạt giống 9 phương ngữ có thật | `config/dialects.seed.csv` |

### Hai điều học được khi làm

1. **T3 tìm ra bản thứ 7** (`LabelsPage.tsx`) mà rà tay đã bỏ sót — đúng lý do
   nên viết test quét mã nguồn thay vì tin vào việc đọc kỹ.
2. **Bộ dò phải bỏ chú thích trước khi quét.** Bản đầu báo nhầm
   `class_registry.py` chỉ vì một dòng comment `# 'bac', 'nam', 'common'`. Một
   test hay báo nhầm sẽ bị tắt, và lúc đó nó vô dụng hơn cả không có.

`_LEGACY_OFFENDERS` giữ 3 bản frontend chưa gỡ được (file còn xung đột merge),
kèm `test_t3_baseline_only_shrinks` — file nào dọn sạch mà còn trong danh sách
là fail, để nó không mục thành danh sách miễn trừ vĩnh viễn.

### Còn nợ của đợt 1

- **Chưa cắm FK** `classes.dialect → dialects(dialect_id)`: Postgres từ chối tạo
  FK khi còn hàng vi phạm, mà bảng chưa seed lần nào (DB chưa chạy được vì
  `docker-compose.yml` còn dấu xung đột). Cắm ngay sau lần seed đầu.
- **Chưa xuất được** `vocabulary_registry.json`, nên `vocabulary.py` đang chạy
  bằng tuple fallback. Cùng lý do.

### Liên quan multitenant

Cả hai bảng trên là **dữ liệu của tenant**, không phải của nền tảng — trường A
và trường B có bộ phương ngữ khác nhau. Nếu làm sau khi đã có tenant thứ hai thì
phải chia lại dữ liệu; làm bây giờ thì chỉ cần thêm cột `tenant_id` như các bảng
khác ở [`MULTITENANT_PREP.md`](MULTITENANT_PREP.md).
