# Kiểm duyệt dữ liệu Cộng đồng

Thiết kế cho quy trình: người dùng cộng đồng đóng góp → dữ liệu dùng được ngay
bởi **chính họ** → qua kiểm duyệt mới **công khai** cho mọi người.

Tài liệu này quyết những gì `COMMUNITY_DATA_COMMONS.md` §0/§10 để mở, và bám
đúng khuôn mẫu đã chạy được cho phương ngữ (`routers/vocabulary.py`).

---

## 0. Chốt phạm vi: Community là hệ đang chạy

**Quyết định:** cộng đồng đang chạy hôm nay *là* Community. Không di chuyển
3.862 mẫu và 64 lớp đi đâu cả. Tenant là thứ hoạt động theo nguyên tắc riêng.

### Trạng thái thật hiện nay

```
tenants:   community (COMMUNITY, reserved, RỖNG)
           default   (ORGANIZATION, 64 lớp / 3.862 mẫu)   <- corpus thật
settings.public_tenant_id = "default"
```

Nghĩa là cái tên `community` đang gắn vào một hàng rỗng, còn dữ liệu cộng đồng
thật thì nằm ở `default`. `classes.py:350` đã ghi nhận mâu thuẫn này và để ngỏ
ba lựa chọn; quyết định ở trên chọn hướng "tenant đang giữ corpus **là**
Community".

### Việc phải làm

Đổi `COMMUNITY_TENANT_ID` (`storage/authz_schema.py:114`) từ `"community"` sang
tenant đang giữ corpus, rồi để bộ ba seed/repair/postcondition tự chỉnh
`tenant_type` và `is_system_reserved`. **Không** làm ngược lại bằng một câu
`UPDATE` tay: chỉ mục duy nhất `uq_tenants_single_community` sẽ chặn khi hàng
`community` cũ còn đó, và lượt khởi động kế tiếp sẽ dựng lại nó rồi vi phạm
chính chỉ mục ấy — hỏng ở chỗ rất xa nguyên nhân.

### Rủi ro phải xử lý cùng lúc

`default` đang giữ **hai** vai: corpus công khai, **và** đích rơi về của
`normalize_tenant_id("")`. Gộp Community vào đó không xoá vai thứ hai — nên một
lỗi làm mất ngữ cảnh tenant sẽ **ghi im lặng vào Community** thay vì báo lỗi.

Đây đúng là chỗ §0 của `COMMUNITY_DATA_COMMONS.md` từng cảnh báo. Cách bịt:
đường rơi-về phải **hỏng to** chứ không rơi về Community. Xem §8, mục PRE-2.

---

## 1. Đơn vị kiểm duyệt là PHIÊN THU, không phải mẫu

Đo trên dữ liệu thật:

| Đại lượng | Số |
|---|---|
| Mẫu (chưa xoá) | 3.862 |
| `capture_session_id` phân biệt | **250** |
| Mẫu mỗi phiên (trung bình) | 11,5 |

Một lần quay sinh ra 1 mẫu gốc + N mẫu tăng cường dùng chung phiên. Kiểm duyệt
theo mẫu nghĩa là bắt người duyệt xem cùng một cử chỉ 11 lần, và bắn 11 thông
báo cho một lần quay. Hàng đợi 250 mục thì duyệt được; 3.862 mục thì không.

**Nên:**

- **Quyết định** ở mức `capture_session_id`.
- **Lưu trạng thái** ở mức mẫu (mỗi dòng một giá trị), vì `samples.csv` là
  nguồn sự thật theo dòng và bộ lọc lúc chọn dữ liệu cũng làm việc theo dòng.
- Một quyết định ghi xuống tất cả các dòng cùng phiên, trong một giao dịch.

Đây cũng chính là hình dạng của `delete_label_session`
(`routers/label_sessions.py:260`): thao tác theo phiên, tác động lên "mẫu gốc
cộng mọi mẫu tăng cường dùng chung `session_id`".

**Dữ liệu cũ không có phiên:** 997 mẫu không có `capture_session_id`. Chúng
được backfill thẳng sang `approved` (§3) nên không rơi vào hàng đợi.

---

## 2. Trạng thái kiểm duyệt

### 2.1 Không tái dùng cột `status`

`samples.status` đã tồn tại, mặc định `'PENDING'`, và **cả 3.862 dòng đều là
`PENDING`** — vì không có dòng mã nào đọc hay ghi nó. Tái dùng nó sẽ:

1. Sinh ra một hàng đợi giả 3.862 mục ngay ngày đầu.
2. Trộn hai nghĩa vào một tên (trạng thái xử lý vs trạng thái duyệt), khiến
   nhật ký kiểm toán về sau không đọc được.

Cột `status` **giữ nguyên, không đụng tới**.

### 2.2 Cột mới

Trên bảng `samples`:

| Cột | Kiểu | Vào `samples.csv`? | Vì sao |
|---|---|---|---|
| `review_status` | `TEXT NOT NULL DEFAULT 'pending'` | **CÓ** | Đây là sự thật quyết định dữ liệu dùng được hay không — phải đi cùng dữ liệu |
| `reviewed_by` | `UUID REFERENCES users(id)` | KHÔNG | Danh tính người duyệt; `samples.csv` được nhân bản sang Google Sheets |
| `reviewed_at` | `TIMESTAMPTZ` | KHÔNG | Vết kiểm toán, thuộc mặt phẳng nền tảng |
| `review_note` | `TEXT DEFAULT ''` | KHÔNG | Có thể chứa nhận xét về người đóng góp |

Ràng buộc: `CHECK (review_status IN ('pending','approved','rejected'))`.

Chỉ mục từng phần cho truy vấn nóng duy nhất — hàng đợi chờ duyệt:

```sql
CREATE INDEX idx_samples_pending_review
    ON samples(tenant_id, created_at DESC)
    WHERE review_status = 'pending' AND deleted_at IS NULL;
```

Từng phần, vì phần đã duyệt lớn dần vô hạn còn phần chờ duyệt thì không — cùng
lý do với `idx_notifications_unread`.

### 2.3 Đưa `review_status` vào CSV

Dùng `dataset_samples.ensure_samples_column()` — nó đã tồn tại đúng cho việc
này: idempotent, ghi qua tệp tạm + `os.replace`, và **nối vào CUỐI header** vì
bản nhân bản Google Sheets phát header nguyên văn thành dòng 1 (chèn giữa sẽ
đẩy mọi cột hiện có sang phải một ô).

Tiền lệ gọi: `db.py:156-176` gọi đúng hàm này cho `auth_user_id` và `tenant_id`
lúc khởi động.

**Kéo theo — phải sửa cùng lượt, nếu không lệch âm thầm:**

1. `sot/catalog_schema.py::REQUIRED_COLUMNS` — thêm `review_status` vào danh
   sách của `samples`. Bỏ qua thì bộ đọc SOT chấp nhận một ảnh chụp không có
   cột này, và một máy khôi phục từ đó sẽ mất trạng thái duyệt **không báo gì**.
2. `metadata_db._SAMPLE_DB_KEYS` — danh sách cột mà upsert THẬT SỰ ghi.
   `REQUIRED_COLUMNS` chỉ là lời hứa; `test_sot_schema_coverage.py` ghim hai
   danh sách vào nhau.
3. Sidecar JSON cạnh mỗi `.npz` — nơi dựng lại một dòng khi CSV hỏng.
4. Bản nhân bản Sheets tự theo header, không cần sửa mã.

### Cái bẫy trong `ON CONFLICT`

`SQL_UPSERT_SAMPLE` phải đọc **THAM SỐ**, không đọc `EXCLUDED`:

```sql
review_status = COALESCE(%(review_status)s, samples.review_status)
```

Vì mệnh đề `VALUES` đã thay giá trị vắng mặt bằng `'pending'`,
`EXCLUDED.review_status` **không bao giờ NULL**. Viết
`COALESCE(EXCLUDED.review_status, …)` theo thói quen sẽ **hạ cấp mọi mẫu đã
duyệt về trạng thái chờ** ở lượt đồng bộ CSV kế tiếp — xoá sạch công của người
kiểm duyệt, không sinh ra lỗi nào. Đúng cái bẫy `tenant_id` đã mắc, và chú thích
cảnh báo nằm ngay cạnh trong file.

`test_sample_review_status.py::test_dong_bo_im_lang_KHONG_ha_cap_mau_da_duyet`
canh chỗ này.

---

## 3. Backfill: 3.862 mẫu cũ là `approved`

Vì sao không để chúng `pending`:

- Sinh ngay một hàng đợi 250 phiên mà không ai từng hứa sẽ duyệt.
- **Mọi lượt huấn luyện đang chạy sẽ mất toàn bộ dữ liệu** ngay khi bộ lọc §5
  bật, vì không dòng nào là `approved`. Hỏng theo hướng an toàn, nhưng hỏng
  toàn bộ.

Đây là corpus nghiên cứu đã dùng để công bố; nó đã được chấp nhận trên thực tế.

### Không có câu UPDATE nào — và đó là chủ ý

Bản thiết kế đầu định dùng một bước dữ liệu có hậu điều kiện. **Đã bỏ.** Sổ
migration chạy **mỗi lần khởi động**, nên một câu

```sql
UPDATE samples SET review_status = 'approved' WHERE review_status = 'pending'
```

sẽ **duyệt sạch mọi mẫu đang thật sự chờ duyệt** ở lần khởi động kế tiếp. Đó là
mìn hẹn giờ, và không hậu điều kiện nào bắt được nó — trạng thái đích *đúng là*
"không còn dòng pending nào".

Cách đã cài, hai câu ở cùng một chỗ:

```sql
ALTER TABLE samples ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL
                    DEFAULT 'approved';   -- dòng ĐÃ TỒN TẠI nhận giá trị này
ALTER TABLE samples ALTER COLUMN review_status SET DEFAULT 'pending';  -- dòng MỚI
```

Backfill nằm trong chính default của câu `ADD COLUMN`, nên **không chạy lại
được**: `IF NOT EXISTS` bỏ qua ở lượt thứ hai, `SET DEFAULT` là idempotent.

Đây **không phải** "một cột hai default trái ngược" như `gdrive_synced`. Chỗ đó
là hai khai báo *độc lập* bất đồng (`CREATE TABLE` nói FALSE, `ALTER` nói TRUE),
và bên thắng phụ thuộc vào việc CSDL cũ hay mới. Chỗ này là một chuỗi hai câu ở
cùng một nơi, nơi chính sự chuyển tiếp là mục đích — nên `review_status` **cố ý
vắng mặt** trong `CREATE TABLE samples`.

### Mẫu mới bắt đầu ở đâu: theo tenant

`dataset_samples.initial_review_status(tenant_id)`:

| Tenant | Trạng thái khởi đầu |
|---|---|
| `settings.public_tenant_id` (mặt tiền công khai) | `pending` |
| Tenant tổ chức | `approved` |
| Không khai báo tenant công khai | `approved` |

Tổ chức vận hành theo quy tắc riêng và **không có hàng đợi kiểm duyệt**. Đóng
dấu `pending` cho họ nghĩa là mẫu nằm chờ một người kiểm duyệt không tồn tại, và
bộ lọc §5 sẽ loại nó khỏi chính lượt huấn luyện của tổ chức đã thu nó.

Việc đóng dấu xảy ra trong `append_sample_row` — **cùng chốt** đóng dấu tenant,
vì `csv.DictWriter(restval="")` biến một khoá bị bỏ quên thành ô **rỗng** trong
nguồn sự thật trong khi Postgres điền default của cột. Hai nguồn nói hai chuyện
về cùng một dòng, và bên sai là bên mà bộ lọc đọc.

---

## 4. Vai và quyền

### 4.1 Quyền mới

```python
Permission("sample.moderate", PROJECT,
           "Duyệt hoặc từ chối mẫu do cộng đồng đóng góp", SENSITIVE),
```

`SENSITIVE` vì nó quyết định thứ gì trở thành công khai.

Phạm vi `PROJECT` giống mọi quyền `sample.*` khác; một vai phạm vi TENANT vẫn
mang được nó — `community_member` (TENANT) đang mang `sample.read` (PROJECT).

**Quản trị viên nền tảng tự động có**, không phải cấp: `platform_administrator`
= `_codes()` = toàn bộ danh mục, không loại trừ (`catalog.py:281`).

### 4.2 Vai mới `community_reviewer`

```python
BuiltinRole("community_reviewer", "Người kiểm duyệt cộng đồng", TENANT,
            "Chuyên gia được cấp quyền duyệt dữ liệu cộng đồng trước khi công khai",
            (
                PERM.TENANT_READ,
                PERM.CLASS_READ, PERM.SAMPLE_READ,
                PERM.SAMPLE_MODERATE,
                PERM.VOCABULARY_READ, PERM.REGISTRY_READ,
                PERM.SIGNER_READ,
            ),
            tenant_type=COMMUNITY),
```

**Vì sao là vai mới chứ không phải `community_curator`:** curator là vai *biên
tập* (`vocabulary.manage`, `registry.publish`, cộng cả bộ quyền đóng góp
project). Người kiểm duyệt là chuyên gia được mời để **phán xét**, không phải
để sửa — cho họ quyền sửa dữ liệu họ đang duyệt là xoá mất ranh giới giữa người
đóng góp và người kiểm duyệt. Hai vai tồn tại song song, cấp chồng được.

`community_reviewer` **không** có `sample.create`: nếu người kiểm duyệt cũng
đóng góp thì họ giữ thêm `community_member`, và hai vai cộng lại.

### 4.3 Cấp vai — thiếu API

Hôm nay chỉ có `POST /workspaces/{id}/members` (`routers/workspaces.py:351`),
tức chỉ cấp được vai ở phạm vi **workspace/project**. **Không có** đường nào
cấp vai phạm vi TENANT.

Cần bổ sung:

```
POST   /tenants/{tenant_id}/roles     { user_email, role_code }
DELETE /tenants/{tenant_id}/roles/{assignment_id}
GET    /tenants/{tenant_id}/roles
```

- Nhận **email**, không nhận UUID (theo `memberIdentity` đã chốt).
- Người gọi: `require_admin` cho Community.
- Trigger `ct_role_assignments_scope` đã tự chặn nếu ai đó cố gán vai gắn
  `tenant_type=COMMUNITY` ở tenant khác — không cần kiểm lại trong mã.
- Ghi `audit_log`; đây là thao tác cấp quyền.

---

## 5. Bộ lọc: đặt ở chỗ CHỌN dữ liệu

Quy tắc, phát biểu một lần:

> Một mẫu **dùng được** với người xem V nếu
> `review_status = 'approved'` **HOẶC** `auth_user_id = V`.
> Khi không có người xem (phát hành, công bố, thống kê công khai):
> **chỉ** `approved`.

Đây đúng là hình dạng của `vr.list_dialects(viewer_id=...)`, và câu chú thích ở
`routers/vocabulary.py:49` mô tả đúng hành vi này cho phương ngữ.

### Các điểm phải cài — bỏ sót chỗ nào thì chỗ đó là đường vòng

| # | Vị trí | Người xem | |
|---|---|---|---|
| 1 | `processed/splits/make_splits.py` — ngay sau `rows = enriched` | không có → chỉ `approved` | ✅ |
| 2 | `cli/prepare_research_release.py` | không có → chỉ `approved` | |
| 3 | `tenant_lifecycle.py` (cạnh `consent_gate.filter_rows`) | không có → chỉ `approved` | |
| 4 | `GET /dataset/samples` | người gọi | |
| 5 | `GET /classes/community-stats` | không có → chỉ `approved` | |

**Bộ lọc ở giao diện không tính.** Cổng đồng thuận đứng ở đúng những chỗ trên
vì lý do này; kiểm duyệt đứng cùng chỗ hoặc nó chỉ là trang trí.

### Đính chính: KHÔNG lọc ở `train_tcn.py`

Bản thiết kế đầu chỉ vào `train_tcn.py`. **Sai tầng, và sai theo hướng làm hỏng
mọi lượt huấn luyện.**

Trainer đọc **split CSV**, và split CSV có 25 cột — không mang `review_status`,
cũng không mang `auth_user_id`. Cổng đọc sự im lặng thành "chưa duyệt" (đúng
theo §5.1), nên lọc ở đó sẽ loại **sạch** dữ liệu.

Chỗ dữ liệu thật sự được **chọn** là lúc rót từ `samples.csv` vào split. Đặt
**trước** sàn số mẫu, cùng lý do bộ lọc phương ngữ phải đứng trước sàn: một lớp
12 mẫu (9 đã duyệt, 3 đang chờ) sẽ vượt sàn 10 rồi mới rụng xuống 9, và split
được dựng trên một lớp không đủ điều kiện.

Import `app.moderation` ở đó **hỏng-thì-đóng**: không import được thì
`SystemExit`, chứ không chạy tiếp mà bỏ cổng.

### §5.1 — im lặng đọc thành `pending`

`moderation.status_of()` đọc ô rỗng và khoá vắng mặt thành `pending`. Đây là
quyết định quan trọng nhất của mô-đun: một dòng đến từ tệp ghi trước lượt
migration không nói gì về việc đã được duyệt hay chưa, và đọc sự im lặng ấy
thành "đã duyệt" biến việc **chép một tệp cũ vào** thành một lần phát hành hàng
loạt.

Hướng hỏng này nhìn thấy được — hàng đợi dài bất thường thì có người đi hỏi.
Hướng ngược lại không ai thấy gì cả.

### Quan hệ với cổng đồng thuận

Hai cổng **độc lập và cùng phải qua**. Đồng thuận trả lời "người ký có cho phép
mức phát hành này không"; kiểm duyệt trả lời "nội dung này có đạt không". Một
mẫu được duyệt vẫn bị đồng thuận chặn, và ngược lại. Không gộp hai cột.

---

## 6. Thông báo

Bảng `notifications` đã có sẵn (`user_id`, `kind`, `title`, `body`, `link`,
`severity`) cùng `notify()` / `notify_many()`.

| `kind` | Khi nào | Gửi cho | `severity` |
|---|---|---|---|
| `moderation.submitted` | Một phiên thu kết thúc (quay hoặc upload xong) | Mọi người giữ `sample.moderate` trong tenant **+ quản trị viên nền tảng** | `info` |
| `moderation.decided` | Người duyệt bấm duyệt/từ chối | **Người đóng góp** | `success` / `warning` |

`moderation.decided` **là phần đề xuất thêm**, không nằm trong yêu cầu gốc. Lý
do: nếu thiếu nó, người đóng góp không bao giờ biết dữ liệu của mình đã công
khai hay bị từ chối, và họ sẽ hỏi qua kênh hỗ trợ — biến một sự kiện tự động
thành việc tay cho quản trị viên.

### Ba quy tắc bắt buộc

1. **Một thông báo cho một PHIÊN**, không phải cho mỗi mẫu. 11,5 mẫu/phiên
   nghĩa là bắn theo mẫu sẽ tạo 11 thông báo cho một lần quay, và cái chuông
   trở thành thứ người ta tắt đi.
2. **Bắn sau khi xử lý xong**, không phải lúc nhận yêu cầu. Trước khi worker
   trích xong đặc trưng thì chưa có gì để duyệt, và một phiên hỏng sẽ tạo mục
   ma trong hàng đợi.
3. **Thất bại khi gửi thông báo không được làm hỏng lượt đóng góp.** Cùng
   nguyên tắc đã ghi ở `training_tasks.py:104-114`.

`link` trỏ thẳng tới phiên trong màn hình kiểm duyệt.

### Huy hiệu console

Thêm vào `admin_attention.collect()`:

```sql
SELECT count(DISTINCT capture_session_id) AS n
  FROM samples
 WHERE tenant_id = %s AND review_status = 'pending' AND deleted_at IS NULL
```

Đếm **phiên**, không đếm mẫu — huy hiệu phải khớp với số mục người ta thấy
trong hàng đợi. Truy vấn này rẻ nhờ chỉ mục từng phần §2.2, và **về 0 khi làm
xong việc**, đúng hợp đồng của module ấy.

---

## 7. Giao diện

### 7.1 Màn hình kiểm duyệt — `/console/moderation`

Người kiểm duyệt **không phải quản trị viên**, nên:

- Vỏ console phải mở cho người giữ `sample.moderate`. Vỏ console **không phải
  hàng rào quyền** — từng route vẫn tự kiểm quyền của mình.
- Thanh bên của họ chỉ hiện mục Kiểm duyệt, không hiện các mục quản trị còn lại.

Nội dung mỗi mục hàng đợi (một **phiên**):

- Nhãn / phương ngữ / vùng, số mẫu trong phiên, thời điểm thu
- Người đóng góp (email + tên, theo `memberIdentity`)
- Xem lại: mẫu gốc (`augment_id = 0`), không phải cả 11 bản tăng cường
- Chỉ số chất lượng đã có: `completeness`, `quality_flags`, tỉ lệ hai tay
- Hai nút: **Duyệt** / **Từ chối** — từ chối **bắt buộc có lý do**

Khuôn mẫu đã chạy: khối "chờ duyệt" trong `AdminVocabularyPage.tsx:174-193`.

### 7.2 Từ chối phải có lý do, và không xoá gì

Theo đúng bài học của `POST /dialects/{id}/reject`: tới lúc người duyệt nhìn
tới thì người đóng góp đã bỏ công quay rồi. Từ chối đặt
`review_status = 'rejected'` + `review_note`, **không** xoá và **không** chuyển
vào Thùng rác. Dữ liệu vẫn thuộc về người đóng góp và họ vẫn dùng được cho
riêng mình — đúng như hợp đồng "chưa duyệt thì chỉ chủ dùng được".

### 7.3 Cấp vai — màn hình quản trị viên

Trong trang quản trị Cộng đồng: ô tìm theo **email**, hiện tên bên cạnh, chọn
vai (`community_reviewer` / `community_curator`), bảng liệt kê ai đang giữ vai
gì cùng ngày cấp và nút thu hồi.

### 7.4 Người đóng góp thấy trạng thái của mình

Trên màn hình mẫu/phiên của chính họ: huy hiệu **Chờ duyệt** / **Đã công khai**
/ **Bị từ chối** (kèm lý do). Không có nó thì lời hứa "qua kiểm duyệt mới công
khai" là vô hình với đúng người cần biết.

---

## 8. Thứ tự thi công

**Phụ thuộc cứng — làm trước, không thì mọi thứ dưới đây chết:**

- **PRE-1 · Cổng truy cập.** `community_reviewer` là vai v5 phạm vi TENANT
  **không có bản sao ở sổ cũ** (`tenant_members.role` chỉ nhận
  `admin|editor|NULL`). Cổng hiện chỉ tra hai ngăn: grant phạm vi SYSTEM, và
  vai ở sổ cũ. Nên thao tác duyệt sẽ bị **403 ở mọi lượt ghi**. Không sửa cổng
  thì vai này là mã chết.
- **PRE-2 · Đường rơi-về của tenant.** Xem §0. `normalize_tenant_id("")` phải
  hỏng to thay vì rơi vào Community.

**Rồi:**

| | Bước | Nội dung | Cần PRE |
|---|---|---|---|
| ✅ | PRE-1 | Cổng nhận vai v5 gắn membership (`access_gate._has_any_tenant_grant`) | — |
| | PRE-2 | `normalize_tenant_id("")` hỏng to thay vì rơi vào Community | — |
| | 1 | Chốt Community = tenant đang giữ corpus (§0) | 2 |
| ✅ | 2 | Cột + ràng buộc + chỉ mục + backfill `approved` (§2, §3) | — |
| ✅ | 3 | `review_status` vào `SAMPLE_FIELDS`, `_SAMPLE_DB_KEYS`, `REQUIRED_COLUMNS`, upsert | — |
| ✅ | 4 | Quyền `sample.moderate` + vai `community_reviewer` (§4) | 1 |
| | 5 | API cấp vai phạm vi TENANT (§4.3) | 1 |
| ◐ | 6 | Bộ lọc ở các điểm chọn dữ liệu (§5) — đường huấn luyện xong, còn 4 | — |
| ✅ | 7 | API duyệt/từ chối theo phiên + thông báo cho người đóng góp (§6) | 1 |
| | 8 | Huy hiệu console (§6) — `pending_session_count()` đã có, chưa nối vào `admin_attention` | — |
| | 9 | Giao diện kiểm duyệt + cấp vai + trạng thái cho người đóng góp (§7) | — |
| | 10 | Cấp `community_member` lúc đăng ký + backfill tài khoản đang có | 1 |

### Nơi ở của phần ghi tệp

`decide_session` **không** tự ghi `samples.csv`. Nó gọi
`catalog_sync.sync_set_review_status()` — mô-đun sở hữu tệp ấy, cùng khoá, thứ
tự ghi và phép hoàn nguyên khi hỏng.

Lý do không phải thẩm mỹ: `test_file_backed_tenant_isolation` liệt kê tường
minh những mô-đun được đọc **toàn kho**, kèm tiêu chí *"không bao giờ là một
đường phục vụ request"*. `decide_session` chạy từ một request. Nới danh sách sẽ
làm bài kiểm im đi mà không sửa điều nó chỉ ra.

Trong hàm ấy: **thẩm quyền hỏi Postgres** (`capture_session_id` không nằm trong
34 cột của CSV, và hàng đợi cũng dựng từ Postgres), **tuần tự hoá đọc toàn cục**
(ghi lại tệp từ một danh sách đã lọc theo tenant sẽ xoá trắng hàng của tenant
khác). Nếu số dòng chạm được trong CSV khác số mẫu trong DB thì ghi WARNING —
chênh lệch đó nghĩa là quyết định sẽ bị lượt đồng bộ sau xoá đi, và nó phải để
lại dấu vết.

Sidecar JSON cạnh mỗi `.npz` cũng mang `review_status`. Cần nói rõ để không ai
trông chờ nhầm: hôm nay **không có bộ đọc tự động nào** dựng lại một dòng
`samples.csv` từ sidecar — nó là hồ sơ xuất xứ cho việc đối chiếu và sửa chữa
thủ công. Trường này có mặt để một lượt dựng lại như thế có gì mà đọc.

Bước 6 phải xong **trước** bước 10: cấp vai cho người mới trong khi bộ lọc chưa
cài nghĩa là dữ liệu chưa duyệt đi thẳng vào corpus công khai — đúng thứ thiết
kế này sinh ra để chặn.

---

## 9. Kiểm thử phải có

| Test | Chứng minh điều gì |
|---|---|
| Mẫu `pending` **không** vào lượt huấn luyện của người khác | §5 điểm 3 thật sự chặn |
| Mẫu `pending` **có** vào lượt huấn luyện của chính chủ | Hợp đồng "chủ dùng được ngay" |
| Mẫu `pending` không lọt vào `prepare_research_release` | §5 điểm 4 |
| `community-stats` không đếm mẫu `pending` | Không rò quy mô chưa duyệt |
| Khách vãng lai không thấy lớp chỉ có mẫu `pending` | Bề mặt công khai sạch |
| Từ chối **không** xoá dữ liệu | §7.2 |
| Một phiên → **một** thông báo, không phải 11 | §6 quy tắc 1 |
| `community_reviewer` ghi được sau khi sửa cổng | PRE-1 thật sự đủ |
| `community_reviewer` **không** sửa được nội dung mẫu | Ranh giới duyệt/biên tập |
| Sau backfill: 0 dòng cũ ở trạng thái `pending` | §3 hậu điều kiện |
| `review_status` có trong `REQUIRED_COLUMNS` của SOT | §2.3 điểm 1 |

---

## 10. Guest — đã xong, giữ nguyên

Đo trên hệ đang chạy, không cần sửa gì:

| Yêu cầu | Cơ chế | Kết quả đo |
|---|---|---|
| Không được quay | mặc-định-từ-chối của `access_gate` | `POST /upload/camera` → 401 |
| Không được train | mặc-định-từ-chối | `POST /training/start` → 401 |
| Biết từ/ngôn ngữ đang có | `PUBLIC_ROUTES` | `/classes/list`, `/vocabulary/registry` → 200 |
| Live recognition có giới hạn | `TRIAL_OR_SESSION_ROUTES` + phiếu | 60 phút/ngày, reset 00:00 (+07) |

Chỉ một chi tiết cần vá: `/classes/list` trả cả `tenant_id` cho khách vãng lai —
rò tên tenant nội bộ. Bỏ trường đó khỏi phản hồi khi người gọi chưa đăng nhập.
