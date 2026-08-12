# Chuẩn bị multi-tenant — đã làm gì, và còn gì đang giả định một tenant

Ngày 2026-07-31. Hệ thống hiện chạy **một tenant duy nhất**. Tài liệu này ghi
lại phần nền đã đặt trong lần sửa này, và liệt kê **đầy đủ** những chỗ còn giả
định một tenant — vì phần schema là nửa dễ, nửa khó nằm ở ngoài database.

---

## 0. Mô hình: hai mặt phẳng

| | control plane | data plane |
|---|---|---|
| trả lời câu hỏi | "tenant này là ai, được dùng gì" | "dữ liệu của tenant này" |
| bảng | `tenants`, `users`, gói/hạn mức | `classes`, `samples`, `raw_uploads`, `signers`, `training_jobs` |
| khoá | `tenant_id` là PRIMARY KEY | `tenant_id` là CỘT BẮT BUỘC trên MỌI hàng |

Nguyên tắc duy nhất phải giữ: **không truy vấn data-plane nào được phép chạy mà
thiếu điều kiện `tenant_id`**. Mọi lỗi rò rỉ dữ liệu giữa các tenant đều là một
câu `WHERE` quên mất mệnh đề đó.

---

## 1. ĐÃ LÀM (`backend/app/storage/metadata_db.py`)

Toàn bộ nằm trong `MIGRATION_STATEMENTS`, chạy mỗi lần khởi động, idempotent.
**Không đổi hành vi hiện tại**: mọi cột đều `DEFAULT 'default'` nên hàng cũ tự
điền, và chưa đường ghi nào phải sửa.

| việc | chi tiết |
|---|---|
| bảng `tenants` | control plane; seed sẵn một hàng `default` |
| cột `tenant_id` | thêm vào `users`, `classes`, `samples`, `raw_uploads`, `signers`, `training_jobs` — `NOT NULL DEFAULT 'default'` |
| index | `idx_*_tenant_id` trên cả 5 bảng data-plane |
| **uniqueness đổi phạm vi** | `uq_classes_slug_lang_dialect` → `uq_classes_tenant_slug_lang_dialect`<br>`uq_classes_class_idx` → `uq_classes_tenant_class_idx`<br>Bản cũ bị `DROP` **sau khi** bản mới đã tạo. |
| `uq_users_tenant_username` / `_email` | thêm mới, phạm vi theo tenant |
| `verify_integrity_constraints()` | cập nhật theo tên mới |

### Vì sao hai unique index kia là chỗ quan trọng nhất

`class_idx` **chính là chỉ số ô đầu ra của model** (`dataset_loader.py` ánh xạ
`class_idx - 1` sang chỉ số tensor). Ràng buộc cũ là duy nhất **toàn cục**. Với
nhiều tenant điều đó vừa sai vừa chặn:

- **sai**: mỗi tenant huấn luyện model riêng, nên `class_idx` phải đếm lại từ 1
  trong từng tenant. Duy nhất toàn cục ép tenant thứ hai bắt đầu từ 64 — model
  của nó sẽ có 63 ô đầu ra chết.
- **chặn**: `uq_classes_slug_lang_dialect` toàn cục nghĩa là trường B **không
  thể** tạo lớp `xin-chao` vì trường A đã tạo. Người dùng chỉ thấy lỗi 409 khó hiểu.

Đổi phạm vi bây giờ tốn đúng hai câu lệnh. Đổi sau khi đã có dữ liệu nhiều
tenant thì phải dọn trùng lặp trước, lúc đó không còn rẻ nữa.

### Cố ý CHƯA làm

`users_username_key` / `users_email_key` (UNIQUE toàn cục sinh ra từ DDL bảng
`users`) **vẫn còn**. Bỏ ràng buộc duy nhất trên bảng xác thực đang chạy không
phải việc nên chèn vào giữa một lần merge. Chừng nào chưa bỏ, tenant B thật sự
không đăng ký được username mà tenant A đã lấy. Xem bước 3 bên dưới.

---

## 2. CÒN GIẢ ĐỊNH MỘT TENANT — kiểm kê

Đây mới là phần đắt. Xếp theo mức độ khó gỡ.

### 2.1 Bố cục file trên đĩa — KHÓ NHẤT

`settings.dataset_root` là **một thư mục duy nhất** cho cả hệ thống:

```
dataset/
  labels.csv          <- catalog lớp, KHÔNG có cột tenant
  samples.csv         <- catalog mẫu, KHÔNG có cột tenant
  signers.csv         <- KHÔNG có cột tenant
  features/<lang>/<dialect>/<folder>/sample_x.npz
```

Ba file CSV này là **nguồn sự thật** (Postgres chỉ là bản sao — xem
[`csv-to-db-mirror`]). Chúng không có khái niệm tenant, và `FileLock` trên một
file chung nghĩa là mọi tenant tranh nhau **cùng một ổ khoá** — một tenant ghi
nhiều sẽ làm chậm tất cả.

Hai hướng, phải chọn trước khi viết code:

| | `dataset/<tenant_id>/...` | giữ một cây, thêm cột `tenant_id` vào CSV |
|---|---|---|
| cách ly | theo thư mục, rất rõ ràng | chỉ theo cột, dễ quên `WHERE` |
| khoá ghi | mỗi tenant một `FileLock` | vẫn tranh chung một khoá |
| xoá một tenant | `rm -rf` một thư mục | phải lọc và ghi lại cả file |
| xuất dữ liệu cho tenant | copy thư mục | phải lọc |
| công sửa | sửa mọi chỗ dựng đường dẫn | sửa mọi chỗ đọc CSV |

**Đề xuất: đi hướng thư mục.** Cách ly theo đường dẫn là thứ khó vô tình phá vỡ
nhất, và nó biến "xoá dữ liệu của tenant" — nghĩa vụ pháp lý của SaaS — thành
một thao tác thay vì một cuộc rà soát.

### 2.2 Google Drive

`settings.google_drive_root_folder_id` là **một folder ID duy nhất**. Mọi tenant
sẽ đổ file vào chung một thư mục Drive. Cần một folder gốc cho mỗi tenant, lưu
trong `tenants` (thêm cột `drive_root_folder_id`).

### 2.3 Google Sheets export

Một `spreadsheet_id`, một bảng `google_sheets_sync_status` theo `table_name`.
Khoá của bảng đó phải thành `(tenant_id, table_name)`, và mỗi tenant một sheet —
nếu không, tenant A đọc được toàn bộ dữ liệu tenant B chỉ bằng link sheet.

### 2.4 Model / checkpoint / realtime

- `backend/realtime_service/config/models.json` + thư mục `checkpoints/` dùng
  chung. Một model đang phục vụ realtime là model của ai?
- `class_idx → nhãn` được nạp toàn cục ở realtime service.
- Cần: model đăng ký theo tenant, và request realtime phải mang tenant.

### 2.5 Redis

`_KEY_PREFIX = "ratelimit:"` không có tenant. Hạn mức đăng nhập/đăng ký hiện tại
tính theo cặp (IP, identifier) nên **vẫn đúng** khi nhiều tenant — nhưng hạn mức
theo *gói dịch vụ* (số mẫu/tháng, số job huấn luyện) thì bắt buộc phải có khoá
theo tenant. Đặt tiền tố `t:<tenant_id>:` ngay từ khoá đầu tiên, đừng thêm sau.

### 2.6 Admin và phân quyền

`is_admin` hiện là **admin toàn hệ thống**. Multi-tenant cần hai vai riêng biệt:

- `platform_admin` — vận hành cả nền tảng (đây là `is_admin` hiện tại)
- `tenant_admin` — quản trị trong phạm vi một tenant

Trang `/admin/*` hiện tại thấy hết mọi thứ. Nếu gán nhầm `is_admin` cho một
tenant_admin thì họ thấy dữ liệu của mọi khách hàng khác.

### 2.7 Danh tính người ký

`signer_id` (S001…) hiện là **không gian tên toàn cục** trên `dataset/signers.csv`.
`config/legacy_signer_mapping.json` cũng vậy. Với nhiều tenant, `signer_id` phải
duy nhất **trong tenant**, không phải toàn cục — hai trường khác nhau đều có
"S001" của riêng họ là chuyện bình thường. (Xem [`DATASET_SYNC_DEPLOY.md`] về
việc vì sao danh tính người ký không được đoán.)

---

## 3. Thứ tự làm — từ rẻ đến đắt

1. **`app/tenancy.py`**: `DEFAULT_TENANT_ID`, `current_tenant_id(request)`.
   Hôm nay luôn trả `"default"`. Một chỗ duy nhất để đổi sau này, thay vì rải
   chuỗi `"default"` khắp nơi.
2. **Ghi `tenant_id` ở đường ghi**: `upsert_class` / `upsert_sample` /
   `upsert_raw_upload` / `insert_user` nhận `tenant_id`. Vẫn là `default`, nhưng
   từ lúc này cột không còn phụ thuộc vào giá trị DEFAULT của Postgres.
3. **Bỏ UNIQUE toàn cục trên `users`** (`users_username_key`, `users_email_key`).
   Phải làm TRƯỚC khi có tenant thứ hai, và chỉ sau khi bước 2 đã chạy đủ lâu.
4. **Thêm `tenant_id` vào mọi câu đọc** trong `metadata_db.py`. Cách kiểm tra
   thẳng thắn nhất: viết một test quét mã nguồn, bắt mọi `FROM samples` /
   `FROM classes` không kèm `tenant_id`. Rà tay chắc chắn sẽ bỏ sót.
5. **Cột `tenant_id` trong ba file CSV** + tách cây `dataset/` theo tenant (§2.1).
6. **Drive / Sheets / model theo tenant** (§2.2–2.4).
7. **Tách `platform_admin` và `tenant_admin`** (§2.6).

Bước 1–3 làm được ngay và không đổi hành vi. Bước 4 trở đi cần quyết định về
bố cục ở §2.1 trước.

---

## 4. Điều cần nói thẳng

Bước 4 — "thêm `tenant_id` vào mọi câu đọc" — là chỗ rò rỉ dữ liệu thật sự xảy
ra, và nó **không thể** kiểm bằng cách đọc code. Một câu `SELECT` quên mệnh đề
tenant vẫn chạy đúng, vẫn trả kết quả hợp lý, và chỉ sai khi có tenant thứ hai
với dữ liệu thật. Kiểm thử phải có **ít nhất hai tenant có dữ liệu** và một
khẳng định rằng tenant A không bao giờ thấy hàng của tenant B — nếu không thì
không có gì đang được kiểm cả.

Nếu muốn chắc chắn hơn nữa, Postgres có **Row-Level Security**: bật RLS trên các
bảng data-plane và đặt `SET LOCAL app.tenant_id` mỗi transaction, thì một câu
truy vấn quên `WHERE` sẽ trả về rỗng thay vì trả dữ liệu của người khác. Đắt hơn
khi dựng, nhưng nó biến lỗi rò rỉ từ "im lặng" thành "không thể".
