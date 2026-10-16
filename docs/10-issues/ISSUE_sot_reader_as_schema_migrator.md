# Nợ kiến trúc — reader SOT đang hành xử như một bộ migration độc lập

**Mở:** 15/08/2026 · **Mức độ:** nợ kiến trúc · **Hotfix đã có:** chốt chặn đối tượng đã retire
**Cùng họ với:** [ISSUE_runtime_schema_mutation.md](ISSUE_runtime_schema_mutation.md)

---

## 1. Phát biểu

Gói SOT hiện mang hai thứ khác hẳn nhau trong cùng một hiện vật:

```
gói SOT
├── dữ liệu danh mục / nghiệp vụ
└── BẢN CHỤP SQL LƯỢC ĐỒ, đông lạnh lúc publish
        ↓
    reader sync  (mỗi lượt sot_init)
        ↓
    ĐỔI lược đồ vật lý của cơ sở dữ liệu đang chạy
```

Điều đó biến một **hiện vật lịch sử đã ký** thành một **nguồn quyền lực về lược
đồ**, song song và xung đột với hệ thống migration.

## 2. Chuyện đã xảy ra

`catalog_schema.export_schema_sql()` chụp `DDL_STATEMENTS + MIGRATION_STATEMENTS
+ INDEX_STATEMENTS` tại thời điểm publish. Gói `Ver5_06082026` ký ngày 06/08 —
trước khi `region` vào định danh lớp — nên chứa:

| câu | số lượng trong gói |
|---|---|
| `CREATE UNIQUE INDEX … uq_classes_tenant_slug_lang_dialect` | 1 |
| bản có `region` | 0 |

`reader_sync._apply_schema_sql()` phát lại toàn bộ ở **mỗi** lượt sync, bằng vai
migration, và trước 15/08 còn **nuốt mọi lỗi**. Kết quả đo trong một lượt triển
khai duy nhất:

```
migrate --status  TRƯỚC up -d  → khớp, còn sót 0
up -d  (sot_init chạy)
migrate --status  SAU  up -d  → KHÔNG KHỚP, còn sót 1
```

`migrate` gỡ chỉ mục, `sot_init` dựng lại. Không ai được báo, vì `--status` chỉ
được chạy ở đầu lượt triển khai.

## 3. Vì sao chữ ký không cứu được

Chữ ký hợp lệ chứng minh gói **không bị sửa**. Nó không chứng minh nội dung còn
**đúng với hệ thống hôm nay**. Trước 15/08 chỉ câu hỏi thứ nhất được hỏi, và gói
này trả lời "đúng" cho nó một cách hoàn toàn trung thực.

## 4. Hotfix đã áp (không phải giải pháp cuối)

`reader_sync` nay xác định đối tượng mà từng câu định TẠO, và bỏ qua câu nào
dựng lại một đối tượng nằm trong `retired_indexes()` — **cùng nguồn** mà
`migrate --status` dùng, không tạo danh sách thứ hai. Thất bại ngoài dự kiến
không còn bị nuốt: chúng vào `SyncResult.schema_failed`, ghi mức `error`, và
trạng thái đổi thành `applied_degraded`.

Bộ kiểm: `backend/tests/test_sot_cannot_resurrect_retired.py` (8 ca, có cả một
gói ký thật đi qua `sync_from_sot`). Đột biến gỡ chốt chặn → 3 đỏ.

Bất biến được khoá:

> Một hiện vật lịch sử được phép **mô tả** lược đồ của thời điểm nó ra đời,
> nhưng không được vượt quyền migration để **khôi phục** thứ hệ thống hiện hành
> đã retire.

## 5. Hướng đúng

```
Hệ migration   = nguồn quyền lực DUY NHẤT của lược đồ vật lý
Gói SOT        = dữ liệu + KHAI BÁO tương thích lược đồ
```

Gói nên nói `schema_contract_version = 5`, hoặc mang mô tả lược đồ để **kiểm
chứng**, chứ reader không nên chạy `CREATE TABLE` / `CREATE INDEX` lên cơ sở dữ
liệu sản xuất ở mỗi lượt sync.

Phát lại lược đồ, nếu còn cần, chỉ hợp lý ở ba chỗ:

- dựng mới một cơ sở dữ liệu trắng (bootstrap)
- fixture của bộ kiểm
- không gian nhập liệu tách biệt

Không phải một lượt sync định kỳ trên sản xuất.

## 6. Vì sao chưa làm ngay

Đổi hợp đồng gói SOT đụng vào hiện vật **đã ký, dùng chung giữa hai máy**, và
các gói cũ vẫn phải đọc được. Việc này cần một phiên bản gói mới với hợp đồng
mới, không phải một bản vá trong mã reader.

Và kể cả khi publish gói mới, **chốt chặn ở §4 vẫn phải giữ**: một máy khác,
hoặc một lượt khôi phục từ bản cũ, vẫn có thể đọc gói lịch sử. Gói mới không
chữa được một reader không an toàn.

## 7. Còn một điểm chưa siết

`sot-init` thoát khác 0 sẽ chặn cả stack (backend/worker/trainer đều gate trên
`service_completed_successfully`). Hiện gói SOT có sẵn một câu thất bại lành
tính:

```
CREATE INDEX … ON tenant_members(user_id)
  -> cannot create index on relation "tenant_members"   (nó là VIEW từ PDM v5)
```

Nên `applied_degraded` tạm thời vẫn thoát 0 — **một quyết định vận hành có ghi
chú**, không phải sơ suất. Khi câu ấy được xử lý (publish gói sạch, hoặc gỡ nó
khỏi bản chụp), đổi `app/sot/cli.py` để `applied_degraded` trả 5 và một lượt
phát lại hỏng sẽ chặn triển khai.

## 8. Việc cần làm khi mở lại

- [ ] Gói SOT khai báo `schema_contract_version` thay vì nhúng SQL thi hành
- [ ] Reader **kiểm chứng** tương thích, không **áp** lược đồ
- [ ] Giữ đường phát lại chỉ cho bootstrap / test / nhập liệu tách biệt
- [ ] `applied_degraded` → mã thoát khác 0 sau khi câu `tenant_members` được xử lý
- [ ] `Ver5_06082026` giữ **bất biến**; lược đồ mới đi kèm `Ver6_…`, chữ ký mới
