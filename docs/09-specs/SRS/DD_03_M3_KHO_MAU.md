# Từ điển dữ liệu — Nhóm M3: Kho dữ liệu mẫu

*6 bảng · 112 cột. Trích từ CSDL đang chạy ngày 18/08/2026.
Quy ước đọc bảng: xem [DD_00_QUY_UOC_VA_MUC_LUC.md](DD_00_QUY_UOC_VA_MUC_LUC.md).*

**Đây là nhóm trọng tâm của luận văn.** Cả 6 bảng đều mang `tenant_id`, đều bật
RLS + FORCE, và **9 trong 22 khoá ngoại ghép** của toàn lược đồ nằm ở nhóm này.

---

## 3.1 Bảng `samples` — Mẫu dữ liệu ký hiệu

**Khoá chính:** `sample_uid` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 42 · **Số
hàng (10/08/2026):** 3.860

*Bảng lớn nhất lược đồ. Chia theo sáu nhóm cột để đọc được.*

### Nhóm A — Định danh và quy kết

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| sample_uid | text | — | Primary key, Check | Định danh mẫu, **tính cố định từ dữ liệu đầu vào** chứ không sinh ngẫu nhiên — nhờ đó chạy lại tác vụ ghi đè thay vì nhân bản |
| tenant_id | text | — | Not null, Default 'default', Foreign key → tenants.tenant_id | **Cột phân biệt tổ chức** — cơ sở của toàn bộ chính sách RLS |
| class_uid | text | — | Null, **Foreign key kép** → classes(tenant_id, class_uid) | Lớp từ vựng mà mẫu thuộc về |
| signer_id | text | — | Null, **Foreign key kép** → signers(tenant_id, signer_id) | **NGƯỜI KÝ — chủ thể dữ liệu.** Độ phủ đo 10/08/2026: **43,4 %** |
| auth_user_id | uuid | — | Null, Foreign key → users.id | **TÀI KHOẢN THU MẪU** — người bấm nút. Độ phủ: **95,7 %** |
| user_id | text | — | Null | Tên người thực hiện nhập tự do từ mô hình cũ; giữ để tương thích ngược |
| username | text | — | Null | **Bản sao tên đăng nhập lúc ghi** — đây là cột bị cập nhật khi tài khoản đổi tên |
| capture_session_id | uuid | — | Null, Foreign key → capture_sessions.capture_session_id | Phiên thu chứa mẫu |
| session_id | text | — | Null | Mã phiên dạng chuỗi từ mô hình cũ |
| session_uid | text | — | Null | Mã phiên chuẩn hoá |

> **Hai cột quy kết, tuyệt đối đừng lẫn.** `auth_user_id` là *ai bấm nút*;
> `signer_id` là *ai có bàn tay trong dữ liệu*. Một nghiên cứu sinh có thể thu hàng
> trăm mẫu của nhiều người ký khác nhau. Gộp hai cột là đánh mất khả năng trả lời
> yêu cầu rút dữ liệu — và **56,6 % kho dữ liệu hiện không quy được về người ký**.

### Nhóm B — Nhãn và ngôn ngữ

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| slug | text | — | Null | Nhãn chuẩn hoá (không dấu, không khoảng trắng) |
| label_original | text | — | Null | Nhãn gốc người dùng nhập, giữ nguyên dấu |
| language | text | — | Null, Foreign key → languages.code | Mã ngôn ngữ |
| dialect | text | — | Null, **Foreign key kép** → dialects(tenant_id, dialect_id) | Phương ngữ — **một phần định danh lớp**, không phải thuộc tính phụ |
| collection_campaign | text | — | Null | Đợt thu thập, dùng để nhóm dữ liệu theo chiến dịch |

### Nhóm C — Nguồn và tham số kỹ thuật

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| source_type | text | — | Null | Nguồn mẫu: thu qua camera hay tải tệp video |
| fps_original | text | — | Null | Tốc độ khung hình của nguồn |
| fps_processed | text | — | Null | Tốc độ khung hình sau chuẩn hoá |
| seq_len | integer | 32 | Null | Số khung của chuỗi sau chuẩn hoá (mục tiêu 60) |
| sequence_length_original | integer | 32 | Null | Số khung của chuỗi **trước** chuẩn hoá |
| augment_id | integer | 32 | Null | Chỉ số biến thể tăng cường; rỗng hoặc 0 nghĩa là **bản gốc** |
| raw_landmarks_available | boolean | — | Null | Có còn bản điểm mốc thô trước chuẩn hoá không |
| normalization_version | text | — | Null | **Phiên bản thuật toán chuẩn hoá** đã áp — điều kiện để tái lập |
| preprocess_contract_version | text | — | Null | Phiên bản hợp đồng tiền xử lý |

**`normalization_version` và `preprocess_contract_version` là hai cột phục vụ khả
năng tái lập.** Không có chúng, hai mẫu trông giống nhau có thể đã đi qua hai
đường xử lý khác nhau mà không ai biết.

### Nhóm D — Lưu trữ

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| file_path | text | — | Null, Check | Đường dẫn tệp đặc trưng `.npz` trên hệ tệp cục bộ |
| storage_key | text | — | Null, Default '' | Khoá đối tượng trên kho lưu trữ ngoài |
| storage_url | text | — | Null | Địa chỉ tải trên kho ngoài |
| checksum | text | — | Null | Mã kiểm tra toàn vẹn của tệp đặc trưng |
| gdrive_synced | boolean | — | Null, Default true | Đã đẩy lên kho ngoài chưa |
| sheets_synced | boolean | — | Null, Default false | Đã phản chiếu sang bảng tính chưa |

**Mẫu thiếu `storage_key` vẫn dùng được cho huấn luyện** trên chính máy triển
khai; tác vụ đối soát theo lịch điền bù về sau. Đây là lý do đẩy tệp lên kho ngoài
**không chặn** đường thu.

### Nhóm E — Chất lượng

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| completeness | real | 24 | Null | **Độ đầy đủ** — tỉ lệ khung thật sự thấy bàn tay. **Tính lại được** từ tệp đặc trưng |
| jitter | real | 24 | Null | **Độ rung** quỹ đạo điểm mốc. **KHÔNG tính lại được** — phụ thuộc chuỗi trước chuẩn hoá |
| left_hand_ratio | real | 24 | Null | Tỉ lệ khung thấy tay trái |
| right_hand_ratio | real | 24 | Null | Tỉ lệ khung thấy tay phải |
| both_hands_ratio | real | 24 | Null | Tỉ lệ khung thấy **đủ hai tay** — dùng để kiểm lớp yêu cầu hai tay |
| quality_flags | text | — | Null | Cờ chất lượng dạng chuỗi (ví dụ đã đệm khung cho đủ độ dài) |
| quality_status | text | — | Null | Kết luận chất lượng tổng hợp |

> **Hai chỉ số, hai giá trị chứng minh khác nhau.** `completeness` tái lập được;
> `jitter` thì không. Một chỉ số tái lập được và một chỉ số không tái lập được
> **không có cùng giá trị chứng minh**, và phải nói rõ khi báo cáo.
>
> **`completeness = 0` KHÔNG có nghĩa tệp rỗng** — nó có nghĩa *không phát hiện
> được bàn tay nào*. Hai điều đó khác nhau.

### Nhóm F — Trạng thái và vòng đời

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| status | varchar | 20 | Null, Default 'PENDING' | Trạng thái xử lý: `PENDING` → `PROCESSING` → `READY`, nhánh `FAILED` |
| error_log | text | — | Null, Default '' | Lý do thất bại, **đọc được cho người dùng** |
| created_at | timestamptz | — | Null | Thời điểm ghi mẫu |
| updated_at | timestamptz | — | Null | Lần cập nhật gần nhất |
| deleted_at | timestamptz | — | Null | **Cờ xoá mềm** — đây là cột làm cho thùng rác khả thi |

### Chín khoá ngoại của bảng `samples`

```
samples(tenant_id, class_uid)  → classes(tenant_id, class_uid)      [GHÉP]
samples(tenant_id, signer_id)  → signers(tenant_id, signer_id)      [GHÉP]
samples(tenant_id, dialect)    → dialects(tenant_id, dialect_id)    [GHÉP]
samples(tenant_id)             → tenants(tenant_id)
samples(auth_user_id)          → users(id)
samples(language)              → languages(code)
samples(capture_session_id)    → capture_sessions(capture_session_id)
```

**Ba khoá ghép là cơ chế cách ly, không phải trang trí.** Với khoá ngoại đơn, mẫu
của tổ chức A trỏ được tới lớp của tổ chức B — cơ sở dữ liệu **không phản đối**, vì
khoá vẫn tồn tại. Khoá ghép làm việc đó **bất khả thi ở tầng ràng buộc**, không
phải ở tầng kiểm tra của ứng dụng.

---

## 3.2 Bảng `classes` — Lớp từ vựng

**Khoá chính:** `class_uid` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 23 · **Số hàng
(10/08/2026):** 63

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| class_uid | text | — | Primary key | Định danh lớp |
| tenant_id | text | — | Not null, Default 'default', Foreign key → tenants.tenant_id | Tổ chức sở hữu lớp |
| class_idx | integer | 32 | Null | **Chỉ số lớp dùng khi huấn luyện** — thứ tự trong không gian nhãn |
| slug | text | — | Null | Nhãn chuẩn hoá |
| label_original | text | — | Null | Nhãn gốc giữ nguyên dấu |
| language | text | — | Null, Foreign key → languages.code | Mã ngôn ngữ |
| dialect | text | — | Null, **Foreign key kép** → dialects(tenant_id, dialect_id) | Phương ngữ — **tham gia định danh lớp** |
| region | text | — | Not null, Default 'unclassified', Foreign key → regions.code | Vùng miền — **cũng tham gia định danh lớp** |
| semantic_label | text | — | Null | Nhãn ngữ nghĩa, dùng khi nhiều biến thể cùng nghĩa |
| description | text | — | Null, Default '' | Mô tả lớp |
| hands_required | integer | 32 | Null | **Số bàn tay lớp này yêu cầu** — đọc từ đây, **không suy đoán từ khung hình** |
| motion_type | text | — | Null | Loại chuyển động của ký hiệu |
| vocabulary_scope | text | — | Null | Phạm vi từ vựng |
| vocabulary_group | text | — | Null, **Foreign key kép** → vocabulary_groups(tenant_id, group_id) | Nhóm từ vựng |
| recognition_profile | text | — | Null, **Foreign key kép** → recognition_profiles(tenant_id, profile_id) | **Hồ sơ nhận dạng** — nhóm lớp phục vụ cùng một mô hình |
| collection_campaign | text | — | Null | Đợt thu thập |
| is_common_global | boolean | — | Null | Lớp dùng chung toàn cầu |
| is_common_language | boolean | — | Null | Lớp dùng chung trong một ngôn ngữ |
| is_active | boolean | — | Null, Default true | Lớp còn dùng |
| folder_name | text | — | Null | Tên thư mục lưu tệp đặc trưng trên hệ tệp |
| created_at | timestamptz | — | Null | Thời điểm tạo |
| migrated_at | timestamptz | — | Null | Thời điểm di trú từ hệ thống tiền thân |
| deleted_at | timestamptz | — | Null | Cờ xoá mềm |

### Ba chỉ mục duy nhất — nơi định nghĩa "hai lớp có phải một lớp không"

```sql
uq_classes_tenant_class_uid
  ON classes (tenant_id, class_uid)
  -- Đây là chỉ mục ĐỠ LƯNG cho mọi khoá ngoại ghép trỏ tới bảng này

uq_classes_tenant_class_idx
  ON classes (tenant_id, class_idx) WHERE deleted_at IS NULL AND class_idx IS NOT NULL
  -- Chỉ số lớp duy nhất trong một tổ chức, chỉ tính lớp còn sống

uq_classes_tenant_slug_lang_dialect_region
  ON classes (tenant_id, slug, language, dialect, region) WHERE deleted_at IS NULL
  -- ĐỊNH DANH LỚP: NĂM CỘT
```

> **Chỉ mục thứ ba là phát biểu chính thức về định danh lớp: NĂM cột.**
> Hai lớp cùng nhãn khác phương ngữ là **hai lớp**. Cùng nhãn, cùng phương ngữ,
> khác vùng miền cũng là **hai lớp**.
>
> **Điều này đã trả giá thật.** Một chỉ mục cũ chỉ dùng **bốn** cột (thiếu
> `region`) đã **cấm** hai biến thể cùng nhãn khác vùng miền tồn tại song song, và
> điều đó **chặn việc nhập dữ liệu từ nguồn từ điển quốc gia**. Chỉ mục 4 cột đã
> được gỡ ngày **17/08/2026**; lỗi sống sót hai ngày vì công cụ kiểm trạng thái là
> một câu hỏi tự nguyện, không phải một cổng chặn.

**Vì sao khoá chính là `class_uid` đơn mà khoá ngoại lại ghép:** khoá chính đơn
giữ được tương thích với mã cũ tham chiếu theo `class_uid`; chỉ mục duy nhất
`(tenant_id, class_uid)` cung cấp mặt đỡ cho khoá ngoại ghép. Hai thứ cùng tồn tại,
và **khoá ngoại dùng cái thứ hai**.

---

## 3.3 Bảng `capture_sessions` — Phiên thu

**Khoá chính:** `capture_session_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 11 ·
**Số hàng (10/08/2026):** 250

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| capture_session_id | uuid | — | Primary key | Định danh phiên thu |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức sở hữu |
| class_uid | text | — | Not null, **Foreign key kép** → classes(tenant_id, class_uid) | Lớp đang thu trong phiên |
| session_id | text | — | Not null, Check | Mã phiên dạng chuỗi, hiển thị cho người dùng |
| signer_id | text | — | Null, **Foreign key kép** → signers(tenant_id, signer_id) | **Người ký của phiên** — phiên thu gắn với **đúng một** người ký |
| auth_user_id | uuid | — | Null, Foreign key → users.id | Tài khoản vận hành buổi thu |
| source_type | text | — | Null | Nguồn: camera hay tệp video |
| started_at | timestamptz | — | Null | Thời điểm bắt đầu phiên |
| ended_at | timestamptz | — | Null, Check | Thời điểm kết thúc phiên |
| note | text | — | Null | Ghi chú buổi thu |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm tạo bản ghi |

**Ràng buộc duy nhất kép:** `UNIQUE (tenant_id, class_uid, session_id)` — mã phiên
chỉ cần duy nhất **trong một lớp của một tổ chức**, không cần duy nhất toàn cầu.

**Ràng buộc `CHECK` trên cặp `(ended_at, started_at)`:** thời điểm kết thúc không
được **trước** thời điểm bắt đầu. Một bất biến nhỏ, nhưng nó chặn được cả một lớp
lỗi tính thời lượng âm ở khâu thống kê.

**Vì sao phiên thu gắn với đúng một người ký:** đây là đơn vị mà hệ thống dùng để
trả lời *"những mẫu nào là của người này"*. Đổi người ký giữa buổi ⇒ **mở phiên
thu mới**, chứ không sửa `signer_id` của phiên đang chạy.

---

## 3.4 Bảng `raw_uploads` — Bản tải lên thô

**Khoá chính:** `upload_uid` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 21 · **Số
hàng (10/08/2026):** 0

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| upload_uid | text | — | Primary key | Định danh lượt tải lên |
| tenant_id | text | — | Not null, Default 'default', Foreign key → tenants.tenant_id | Tổ chức sở hữu |
| class_uid | text | — | Null, **Foreign key kép** → classes(tenant_id, class_uid) | Lớp đích của tệp |
| slug | text | — | Null | Nhãn chuẩn hoá |
| label_original | text | — | Null | Nhãn gốc |
| language | text | — | Null, Foreign key → languages.code | Mã ngôn ngữ |
| dialect | text | — | Null, **Foreign key kép** → dialects(tenant_id, dialect_id) | Phương ngữ |
| source_type | text | — | Null | Nguồn tệp |
| user_id | text | — | Null | Tên người thực hiện nhập tự do |
| auth_user_id | uuid | — | Null, Foreign key → users.id | Tài khoản tải lên |
| username | text | — | Null | Bản sao tên đăng nhập lúc ghi |
| session_id | text | — | Null | Mã phiên dạng chuỗi |
| session_uid | text | — | Null | Mã phiên chuẩn hoá |
| original_filename | text | — | Null | **Tên tệp gốc** người dùng tải lên |
| local_path | text | — | Null | Đường dẫn bản thô trên hệ tệp — **ghi TRƯỚC mọi bước chuẩn hoá** |
| storage_key | text | — | Null | Khoá đối tượng trên kho ngoài |
| storage_url | text | — | Null | Địa chỉ tải trên kho ngoài |
| status | varchar | 20 | Null, Default 'PENDING' | Trạng thái xử lý |
| created_at | timestamptz | — | Null | Thời điểm tải lên |
| updated_at | timestamptz | — | Null | Lần cập nhật gần nhất |
| deleted_at | timestamptz | — | Null | Cờ xoá mềm |

**Bảng này chỉ phục vụ đường tải tệp video.** Đường thu qua webcam **không sinh
video**, nên không tạo hàng ở đây — đó là lý do lược đồ **không có** bảng lưu video
thô riêng, và là chỗ để trống **có chủ ý**.

**`local_path` được ghi trước mọi bước chuẩn hoá** (BR-5.3 / NFR-R2). Nếu bước
chuẩn hoá có lỗi, dữ liệu gốc vẫn còn để xử lý lại. Thứ tự này là một **ràng buộc
thiết kế**, không phải chi tiết cài đặt.

---

## 3.5 Bảng `signers` — Người ký (chủ thể dữ liệu)

**Khoá chính:** `signer_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 9 · **Số hàng
(10/08/2026):** 4

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| signer_id | text | — | Primary key | Định danh người ký |
| tenant_id | text | — | Not null, Default 'default', Foreign key → tenants.tenant_id | Tổ chức sở hữu bản ghi người ký |
| display_name | text | — | Null | Tên hiển thị |
| regional_group | text | — | Null | Nhóm vùng miền của người ký |
| external_user_id | uuid | — | Null, Foreign key → users.id | **Tài khoản tương ứng, nếu người ký cũng là người dùng hệ thống** — cầu nối để họ tự quản đồng thuận của mình |
| is_active | boolean | — | Null, Default true | Bản ghi còn dùng |
| note | text | — | Null | Ghi chú |
| display_order | integer | 32 | Not null, Default 0 | Thứ tự hiển thị trong danh sách |
| created_at | timestamptz | — | Null | Thời điểm tạo |

**Chỉ mục duy nhất kép:** `uq_signers_tenant_signer_id ON signers (tenant_id,
signer_id)` — mặt đỡ cho các khoá ngoại ghép từ `samples`, `capture_sessions` và
`signer_aliases`.

> **Người ký là một THỰC THỂ, không phải một cột.** Tách nó ra cho phép ba việc mà
> một cột không làm được: gán lại người ký khi phát hiện sai · gắn đồng thuận vào
> đúng chủ thể · trả lời được câu *"những dòng nào là của người này"*.
>
> **Bốn hàng trên 3.860 mẫu** là con số phải báo cáo, không phải giấu: `signer_id`
> chỉ có **4 giá trị phân biệt** và phủ **43,4 %** kho dữ liệu. Nguyên nhân nằm ở
> giao diện thu — ô *"Người thực hiện"* là **nhập tự do**, và mắt xích *mẫu ↔ người
> ký* chỉ thiết lập được đáng tin **tại thời điểm thu**.

**`external_user_id` là cột nối hai thế giới:** một người ký có thể chỉ là một
bản ghi siêu dữ liệu (người tham gia buổi thu, không có tài khoản), hoặc là một
người dùng thật của hệ thống. Chỉ ở trường hợp thứ hai họ mới tự rút đồng thuận
được qua màn hình `/settings/consents`.

---

## 3.6 Bảng `signer_aliases` — Bí danh người ký

**Khoá chính:** `(tenant_id, old_signer_id)` · **RLS:** ✔ bật, ✔ FORCE · **Số
cột:** 6 · **Số hàng (10/08/2026):** 0

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| tenant_id | text | — | Primary key (kép), Foreign key → tenants.tenant_id | Tổ chức |
| old_signer_id | text | — | Primary key (kép), Check | Mã người ký **cũ**, đã bị gộp đi |
| new_signer_id | text | — | Not null, **Foreign key kép** → signers(tenant_id, signer_id) | Mã người ký **đích** sau khi gộp |
| reason | text | — | Null | Lý do gộp |
| merged_at | timestamptz | — | Not null, Default now() | Thời điểm gộp |
| merged_by | uuid | — | Null, Foreign key → users.id | Người thực hiện gộp |

**Ràng buộc `CHECK` trên cặp `(old_signer_id, new_signer_id)`:** hai giá trị
**không được bằng nhau** — chặn bản ghi tự trỏ vào chính nó, thứ sẽ tạo vòng lặp
vô hạn khi phân giải bí danh.

**Vì sao cần bảng này:** khi phát hiện hai bản ghi người ký thực ra là **một
người**, gộp chúng lại phải để lại **dấu vết** — nếu không, mọi tham chiếu cũ tới
mã đã biến mất sẽ mồ côi. Bảng bí danh giữ đường phân giải từ mã cũ sang mã mới.

---

## Tổng kết nhóm M3

```
signers (1) ──< capture_sessions (1) ──< samples
signers (1) ──< samples                              [KHOÁ NGOẠI GHÉP]
signers (1) ──< signer_aliases                       [KHOÁ NGOẠI GHÉP]
classes (1) ──< samples                              [KHOÁ NGOẠI GHÉP]
classes (1) ──< capture_sessions                     [KHOÁ NGOẠI GHÉP]
classes (1) ──< raw_uploads                          [KHOÁ NGOẠI GHÉP]
dialects (1) ──< samples · classes · raw_uploads     [KHOÁ NGOẠI GHÉP]
users (1) ──< samples (auth_user_id)                 [tài khoản thu — KHÁC người ký]
```

**Chuỗi nguồn gốc mà nhóm này bảo toàn:**

```
Người ký → Phiên thu → Mẫu → Bản tải lên thô / Biểu diễn dẫn xuất → Phiên bản bộ dữ liệu
```

Mỗi mắt xích là một quan hệ **truy vấn được**, nên câu hỏi *"mẫu này từ đâu ra,
qua bước nào, do ai"* trả lời được bằng truy vấn chứ không bằng suy đoán. Nhưng
**mắt xích đầu chỉ tồn tại ở 43,4 % dữ liệu**; với phần còn lại, chuỗi đứt ở đúng
vị trí **không dựng lại được**.

| Đặc điểm | Giá trị |
|---|:--:|
| Bảng có `tenant_id` | **6 / 6** |
| Bảng bật RLS + FORCE | **6 / 6** |
| **Khoá ngoại ghép trong nhóm** | **9** |
| Chỉ mục duy nhất định nghĩa danh tính lớp | **5 cột** |
| Bảng lớn nhất lược đồ | `samples` — 42 cột |
