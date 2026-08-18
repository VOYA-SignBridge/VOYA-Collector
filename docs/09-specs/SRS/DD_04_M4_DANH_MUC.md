# Từ điển dữ liệu — Nhóm M4: Danh mục & Registry

*11 bảng · 75 cột. Trích từ CSDL đang chạy ngày 18/08/2026.
Quy ước đọc bảng: xem [DD_00_QUY_UOC_VA_MUC_LUC.md](DD_00_QUY_UOC_VA_MUC_LUC.md).*

**Đây là nhóm cài đặt mô hình ba mặt phẳng danh mục.** Nhóm chia làm ba tầng
không lẫn nhau:

```
Danh mục hệ thống ──sao chép MỘT LẦN──► Danh mục của tổ chức ──ghim──► Ảnh chụp bất biến
 community_* (KHÔNG RLS)                 dialects, profiles… (RLS)     registry_versions
```

**Luật xuyên suốt: lúc chạy KHÔNG bao giờ rơi ngược về mặt phẳng cộng đồng.**
Thiếu dữ liệu danh mục thì hệ thống **dừng**, không suy đoán.

---

## 4.1 Bảng `languages` — Danh mục ngôn ngữ

**Khoá chính:** `code` · **RLS:** — không bật · **Số cột:** 2 · **Số hàng
(10/08/2026):** 2

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| code | varchar | 50 | Primary key | Mã ngôn ngữ, ví dụ `vn`, `en` |
| name | text | — | Not null | Tên hiển thị của ngôn ngữ |

**Bảng đơn giản nhất lược đồ, và không bật RLS có chủ ý:** danh mục ngôn ngữ là
dữ liệu tham chiếu dùng chung, giống nhau ở mọi tổ chức, không mang thông tin của
ai cả.

---

## 4.2 Bảng `regions` — Danh mục vùng miền

**Khoá chính:** `code` · **RLS:** — không bật · **Số cột:** 8

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| code | text | — | Primary key | Mã vùng miền; giá trị dự phòng là `unclassified` |
| name_vi | text | — | Not null | Tên tiếng Việt |
| name_en | text | — | Not null, Default '' | Tên tiếng Anh |
| status | text | — | Not null, Default 'approved' | Trạng thái duyệt |
| sort_order | integer | 32 | Not null, Default 0 | **Thứ tự hiển thị theo địa lý**, không theo bảng chữ cái |
| is_active | boolean | — | Not null, Default true | Vùng còn dùng |
| note | text | — | Null | Ghi chú |
| updated_at | timestamptz | — | Not null, Default now() | Lần sửa gần nhất |

**`sort_order` là cột mang thông tin, không phải cột trang trí.** Thứ tự địa lý
(từ Bắc vào Nam) nói lên quan hệ gần – xa giữa các phương ngữ; sắp lại theo bảng
chữ cái làm mất thông tin đó. Giao diện quản trị danh mục nói thẳng luật này:
*"Thứ tự do máy chủ quyết định (theo địa lý, không theo bảng chữ cái) — hiển thị
đúng thứ tự nhận được, không sắp xếp lại."*

**Vùng miền tham gia định danh lớp** (cột thứ năm của chỉ mục
`uq_classes_tenant_slug_lang_dialect_region`), nên nó **không** phải một thuộc tính
mô tả — nó là một phần của khoá.

---

## 4.3 Bảng `dialects` — Phương ngữ của tổ chức

**Khoá chính:** `(tenant_id, dialect_id)` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:**
14 · **Số hàng (10/08/2026):** 9

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| tenant_id | text | — | Primary key (kép), Default 'default', Foreign key → tenants.tenant_id | Tổ chức sở hữu phương ngữ |
| dialect_id | text | — | Primary key (kép) | Mã phương ngữ, suy ra từ tên khi người dùng đề xuất |
| display_name | text | — | Not null | Tên hiển thị |
| language | text | — | Not null, Default 'vn', Foreign key → languages.code | Ngôn ngữ chứa phương ngữ này |
| is_alphabet | boolean | — | Not null, Default false | **Phương ngữ bảng chữ cái** — nhóm lớp chiếm 64 % kho dữ liệu hiện tại |
| is_active | boolean | — | Not null, Default true | Còn hiện trong hộp chọn ở màn hình thu hay đã tắt |
| status | text | — | Not null, Default 'pending' | **Trạng thái duyệt**: chờ duyệt / đã duyệt / bị từ chối |
| merged_into | text | — | Null, **Foreign key kép** → dialects(tenant_id, dialect_id) | **Phương ngữ đích khi bị gộp** — tự tham chiếu trong cùng tổ chức |
| created_by | uuid | — | Null, Foreign key → users.id | Người đề xuất |
| approved_by | uuid | — | Null, Foreign key → users.id | Người duyệt |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm đề xuất |
| approved_at | timestamptz | — | Null | Thời điểm duyệt |
| note | text | — | Null | Ghi chú |
| display_order | integer | 32 | Not null, Default 0 | Thứ tự hiển thị |

**`status = 'pending'` là giá trị MẶC ĐỊNH, và đó là điểm thiết kế.** Người thu dữ
liệu đề xuất một phương ngữ mới và **dùng được ngay**; quản trị viên duyệt sau.
Giao diện nói đúng như vậy: *"Bạn dùng được ngay, quản trị viên sẽ duyệt sau."*
Nếu mặc định là *đã duyệt*, danh mục sẽ trôi thành danh sách tự do; nếu bắt chờ
duyệt mới dùng được, buổi thu ngoài hiện trường sẽ dừng lại.

**`merged_into` tự tham chiếu bằng KHOÁ NGOẠI GHÉP `(tenant_id, dialect_id)`**,
không phải bằng `dialect_id` đơn. Với khoá đơn, phương ngữ của tổ chức A gộp được
vào phương ngữ của tổ chức B — cơ sở dữ liệu không phản đối. Khoá ghép chặn điều
đó ở tầng ràng buộc.

**Vì sao từ chối một đề xuất BẮT BUỘC nêu nơi gộp:** phương ngữ bị từ chối mà
không có `merged_into` sẽ để lại các mẫu trỏ tới một mã không còn hợp lệ. Giao
diện chặn trước, ngay tại chỗ thao tác: *"Từ chối bắt buộc chọn nơi gộp — dữ liệu
đã gắn mã này sẽ chuyển sang đó thay vì mồ côi."*

---

## 4.4 Bảng `dialect_aliases` — Bí danh phương ngữ

**Khoá chính:** `(tenant_id, old_dialect_id)` · **RLS:** ✔ bật, ✔ FORCE · **Số
cột:** 5 · **Số hàng (10/08/2026):** 0

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| tenant_id | text | — | Primary key (kép), Default 'default', Foreign key → tenants.tenant_id | Tổ chức |
| old_dialect_id | text | — | Primary key (kép) | Mã phương ngữ **cũ**, đã bị gộp đi |
| new_dialect_id | text | — | Not null, **Foreign key kép** → dialects(tenant_id, dialect_id) | Mã phương ngữ **đích** |
| merged_at | timestamptz | — | Not null, Default now() | Thời điểm gộp |
| merged_by | uuid | — | Null, Foreign key → users.id | Người thực hiện gộp |

Cùng vai trò với `signer_aliases` ở nhóm M3: giữ **đường phân giải** từ mã cũ sang
mã mới, để mọi tham chiếu lịch sử không mồ côi sau khi gộp.

---

## 4.5 Bảng `recognition_profiles` — Hồ sơ nhận dạng

**Khoá chính:** `(tenant_id, profile_id)` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:**
7 · **Số hàng (10/08/2026):** 6

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| tenant_id | text | — | Primary key (kép), Default 'default', Foreign key → tenants.tenant_id | Tổ chức sở hữu |
| profile_id | text | — | Primary key (kép) | Mã hồ sơ nhận dạng |
| display_name | text | — | Not null | Tên hiển thị |
| is_trainable | boolean | — | Not null, Default true | **Hồ sơ này có dùng để huấn luyện không** |
| is_active | boolean | — | Not null, Default true | Hồ sơ còn dùng |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm tạo |
| display_order | integer | 32 | Not null, Default 0 | Thứ tự hiển thị |

**Hồ sơ nhận dạng là nhóm lớp phục vụ cùng một mô hình.** Nó trả lời câu *"mô hình
này nhận dạng được những lớp nào"* — và chính là thứ hiện ra ở hộp chọn **"Bộ nhận
diện"** trên màn hình nhận dạng thời gian thực.

**Cột `is_trainable` hiển thị nguyên văn trên giao diện quản trị là "(không huấn
luyện)".** Một hồ sơ tồn tại để nhóm lớp phục vụ mục đích khác — ví dụ chỉ để tra
cứu — không nhất thiết dùng để huấn luyện.

> **Bảng này là nguồn của một lỗi có thật, đáng ghi lại.** Trước khi nó tồn tại,
> danh sách hồ sơ nhận dạng được **gắn cứng ở hai nơi trong mã** và **đã lệch nhau**
> (6 mục so với 5). Hệ quả: **7 lớp bị loại khỏi bước chia dữ liệu trong im lặng**
> — không thông báo, không lỗi, chỉ có kết quả huấn luyện trên một tập nhãn khác
> với tập người dùng nghĩ.

---

## 4.6 Bảng `vocabulary_groups` — Nhóm từ vựng

**Khoá chính:** `(tenant_id, group_id)` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 6
· **Số hàng (10/08/2026):** 5

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| tenant_id | text | — | Primary key (kép), Foreign key → tenants.tenant_id | Tổ chức sở hữu |
| group_id | text | — | Primary key (kép), Check | Mã nhóm từ vựng |
| display_name | text | — | Not null | Tên hiển thị |
| display_order | integer | 32 | Not null, Default 0 | Thứ tự hiển thị |
| is_active | boolean | — | Not null, Default true | Nhóm còn dùng |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm tạo |

Nhóm từ vựng là chiều phân loại **theo chủ đề** (chào hỏi, số đếm, gia đình…),
khác với hồ sơ nhận dạng vốn phân loại **theo mô hình phục vụ**. Hai chiều độc lập
nhau, và một lớp mang cả hai.

---

## 4.7 Bảng `vocabulary_registry_meta` — Con trỏ phiên bản hiện hành

**Khoá chính:** `tenant_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 3 · **Số hàng
(10/08/2026):** 1

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| tenant_id | text | — | Primary key, Default 'default', Foreign key → tenants.tenant_id | Tổ chức — **một hàng cho mỗi tổ chức** |
| version | bigint | 64 | Not null, Default 1 | **Số hiệu phiên bản danh mục đang hiệu lực** của tổ chức đó |
| updated_at | timestamptz | — | Not null, Default now() | Lần đổi phiên bản gần nhất |

**Bảng ba cột này là con trỏ, không phải kho.** Nó nói *"tổ chức này đang dùng
phiên bản mấy"*; nội dung phiên bản nằm ở `registry_versions`.

> **Tách con trỏ khỏi kho là bài học từ một lỗi thật.** Thiết kế trước đó dùng
> **một bộ đếm bị ghi đè** và **một tệp ảnh chụp bị ghi đè**. Hệ quả: *"bộ dữ liệu
> ghim phiên bản 2"* **không thực hiện được**, vì nội dung phiên bản 2 **biến mất
> ngay khi phiên bản 3 được ghi**. Con trỏ đổi được; kho thì chỉ **thêm**.

---

## 4.8 Bảng `registry_versions` — Ảnh chụp danh mục bất biến

**Khoá chính:** `(tenant_id, version)` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 7 ·
**Số hàng (10/08/2026):** 89

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| tenant_id | text | — | Primary key (kép), Foreign key → tenants.tenant_id | Tổ chức sở hữu phiên bản |
| version | bigint | 64 | Primary key (kép) | **Số hiệu phiên bản**, tăng dần trong phạm vi một tổ chức |
| content_hash | text | — | Not null | **Mã băm nội dung** — cho phép đối chiếu rằng ảnh chụp không bị sửa |
| snapshot | jsonb | — | Not null | **Toàn bộ nội dung danh mục tại thời điểm đó**, lưu nguyên khối |
| note | text | — | Null | Ghi chú về lần thay đổi |
| created_by | uuid | — | Null, Foreign key → users.id | Người tạo phiên bản |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm chụp |

**Đây là bảng làm cho việc GHIM PHIÊN BẢN khả thi.** Tác vụ huấn luyện tham chiếu
tới đây bằng khoá ngoại ghép
`training_jobs(tenant_id, registry_version) → registry_versions(tenant_id, version)`
— một quan hệ **ghim**, không phải tham chiếu tới trạng thái hiện tại. Chạy lại
tác vụ sáu tháng sau vẫn dùng **đúng tập nhãn của lần đầu**.

**`snapshot` kiểu `jsonb` lưu nguyên khối, không chuẩn hoá.** Đây là **phi chuẩn
hoá có chủ đích**: mục tiêu của bảng là *bảo toàn một trạng thái đã có thật*, không
phải *truy vấn hiệu quả bên trong trạng thái đó*. Chuẩn hoá nó ra thành các bảng
con sẽ khiến ảnh chụp phụ thuộc vào lược đồ hiện hành — tức mất đúng tính bất biến
mà nó tồn tại để giữ.

**89 hàng** nghĩa là danh mục đã qua 89 lần thay đổi được ghi nhận. Không hàng nào
bị ghi đè.

---

## 4.9 Bảng `community_dialects` — Phương ngữ mặt phẳng cộng đồng

**Khoá chính:** `dialect_id` · **RLS:** — **không bật (có chủ ý)** · **Số cột:** 9
· **Số hàng (10/08/2026):** 9

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| dialect_id | text | — | Primary key | Mã phương ngữ chuẩn của mặt phẳng cộng đồng |
| display_name | text | — | Not null | Tên hiển thị |
| language | text | — | Not null, Default 'vn' | Ngôn ngữ |
| is_alphabet | boolean | — | Not null, Default false | Phương ngữ bảng chữ cái |
| display_order | integer | 32 | Not null, Default 0 | Thứ tự hiển thị theo địa lý |
| is_active | boolean | — | Not null, Default true | Còn dùng |
| note | text | — | Null | Ghi chú |
| updated_by | uuid | — | Null, Foreign key → users.id | Người sửa gần nhất — **chỉ quản trị nền tảng** |
| updated_at | timestamptz | — | Not null, Default now() | Lần sửa gần nhất |

---

## 4.10 Bảng `community_profiles` — Hồ sơ nhận dạng mặt phẳng cộng đồng

**Khoá chính:** `profile_id` · **RLS:** — **không bật (có chủ ý)** · **Số cột:** 8
· **Số hàng (10/08/2026):** 6

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| profile_id | text | — | Primary key | Mã hồ sơ nhận dạng chuẩn |
| display_name | text | — | Not null | Tên hiển thị |
| is_trainable | boolean | — | Not null, Default true | Hồ sơ dùng để huấn luyện |
| display_order | integer | 32 | Not null, Default 0 | Thứ tự hiển thị |
| is_active | boolean | — | Not null, Default true | Còn dùng |
| note | text | — | Null | Ghi chú |
| updated_by | uuid | — | Null, Foreign key → users.id | Người sửa gần nhất |
| updated_at | timestamptz | — | Not null, Default now() | Lần sửa gần nhất |

---

## 4.11 Bảng `community_versions` — Ảnh chụp danh mục cộng đồng

**Khoá chính:** `version` · **RLS:** — **không bật (có chủ ý)** · **Số cột:** 6 ·
**Số hàng (10/08/2026):** 1

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| version | bigint | 64 | Primary key | Số hiệu phiên bản danh mục cộng đồng |
| content_hash | text | — | Not null | Mã băm nội dung |
| snapshot | jsonb | — | Not null | Toàn bộ nội dung danh mục cộng đồng tại thời điểm đó |
| note | text | — | Null | Ghi chú |
| created_by | uuid | — | Null, Foreign key → users.id | Người tạo phiên bản |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm chụp |

**Bảng này là đích của khoá ngoại `tenants.cloned_from_community_version`** — tức
mỗi tổ chức ghi lại **mình đã kế thừa danh mục cộng đồng ở phiên bản nào**.

---

## Ba bảng `community_*` không bật RLS — lập luận đầy đủ

**Đây là chỗ dễ bị đọc thành một lỗ hổng, nên phải nói đủ ba vế:**

1. **Vì sao không bật.** Ba bảng này là **mặt phẳng đọc chung**: mọi tổ chức đọc
   cùng nội dung. Không có gì để phân tách theo `tenant_id` vì chúng **không mang
   cột đó**.
2. **Vì sao vẫn an toàn.** An toàn **chỉ vì** luật không-rơi-ngược được cưỡng chế
   ở tầng ứng dụng: dữ liệu chảy từ mặt phẳng cộng đồng sang tổ chức **đúng một
   lần, lúc khởi tạo**, và **không có đường ngược lại lúc chạy**. Nếu luật này hỏng,
   ba bảng không RLS trở thành đường rò dữ liệu giữa hai mặt phẳng.
3. **Điều này KHÔNG được cưỡng chế ở tầng CSDL.** Nó là kiểm tra ở tầng ứng dụng —
   **mức bảo đảm thấp hơn** so với phần còn lại của lược đồ, và phải phát biểu
   đúng như vậy.

**Phân biệt phải giữ rõ:**

| | Kế thừa (được phép) | Rơi về (bị cấm) |
|---|---|---|
| Khi nào | **Một lần**, lúc khởi tạo tổ chức | Lúc chạy, khi tổ chức thiếu dữ liệu |
| Kết quả | Thuộc về tổ chức đó, sửa được | Đọc dữ liệu của mặt phẳng khác |
| Dấu vết | `tenants.cloned_from_community_version` | Không có |

Hai thứ **trông giống nhau trên sơ đồ** nhưng khác nhau hoàn toàn về hệ quả.

---

## Tổng kết nhóm M4

```
community_versions (1) ──< tenants          [kế thừa MỘT LẦN, có dấu vết]
tenants (1) ──1 vocabulary_registry_meta    [con trỏ phiên bản hiện hành]
tenants (1) ──< registry_versions           [kho ảnh chụp, CHỈ THÊM]
tenants (1) ──< dialects ──< dialect_aliases
dialects (1) ──< dialects (merged_into)     [tự tham chiếu, KHOÁ NGOẠI GHÉP]
tenants (1) ──< recognition_profiles
tenants (1) ──< vocabulary_groups
languages (1) ──< dialects · classes · samples · raw_uploads
regions (1) ──< classes                     [cột thứ 5 của định danh lớp]
```

| Đặc điểm | Giá trị |
|---|:--:|
| Bảng mặt phẳng **tổ chức** (có RLS) | 6 |
| Bảng mặt phẳng **cộng đồng** (không RLS, có chủ ý) | 3 |
| Bảng **tham chiếu dùng chung** (không RLS) | 2 (`languages`, `regions`) |
| Khoá chính **kép** | 6 / 11 bảng |
| Khoá ngoại ghép trong nhóm | 3 |
| Bảng lưu ảnh chụp `jsonb` bất biến | 2 |
