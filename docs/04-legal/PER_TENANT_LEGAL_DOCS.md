# Văn bản pháp lý theo tenant — thiết kế và đường di trú

*Đo 2026-08-10. Chưa hiện thực. Tài liệu này tồn tại để lượt thi công không phải
đo lại, và để lý do hoãn được viết ra thay vì đoán.*

---

## 1. Khoảng trống

`legal_documents` **không có cột `tenant_id`** và không nằm trong danh sách RLS
(`rowsecurity = false`). Mọi tổ chức dùng chung một bộ văn bản. Một trường không
thể có điều khoản riêng, và không thể có thoả thuận xử lý dữ liệu (DPA) riêng
với sinh viên của họ.

Với một nền tảng SaaS phục vụ nhiều tổ chức, đó là khoảng trống thật.

## 2. Vì sao nó KHÔNG phải "thêm một cột"

Đây là phần đã đo, và là lý do việc này đắt hơn vẻ ngoài:

```
legal_documents
  PRIMARY KEY (doc_id)
  UNIQUE      (kind, version)          ← mấu chốt

user_consents.(kind, version)   → legal_documents(kind, version)  ON DELETE RESTRICT
signer_consents.(kind, version) → legal_documents(kind, version)  ON DELETE RESTRICT
```

Muốn hai tổ chức cùng có `data_contribution` phiên bản `1.0` thì `UNIQUE (kind,
version)` phải thành `UNIQUE (tenant_id, kind, version)`. **Và điều đó làm hỏng
cả hai khoá ngoại** — một khoá ngoại chỉ trỏ được tới một khoá duy nhất.

Hai khoá ngoại ấy không phải trang trí. `ON DELETE RESTRICT` là thứ ngăn ai đó
xoá một bản văn mà người ta đã ký, biến 20 dòng chấp thuận đang sống thành con
trỏ treo. Chuỗi bằng chứng "người này đã đồng ý với bản văn *này*" là toàn bộ lý
do cỗ máy phiên bản + hash tồn tại.

**Hiện trạng: 20 dòng `user_consents`, 0 dòng `signer_consents`.**

## 3. Hai thiết kế, và cái nào nên đi trước

### Phương án A — không gian tên phiên bản *(khuyến nghị cho lượt đầu)*

Giữ `UNIQUE (kind, version)` toàn cục. Văn bản của tenant dùng phiên bản có tiền
tố: `ctu/2026-08-10`. Thêm cột `tenant_id` chỉ để **truy vấn và RLS**, không đưa
vào khoá duy nhất.

```sql
ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS tenant_id TEXT;
-- NULL = văn bản NỀN TẢNG, áp cho mọi tổ chức. Đây là toàn bộ dữ liệu hiện có.
CREATE INDEX IF NOT EXISTS idx_legal_documents_tenant
  ON legal_documents(tenant_id, kind) WHERE tenant_id IS NOT NULL;
```

| Được | Mất |
|---|---|
| **Không đụng khoá ngoại nào** | phiên bản có tiền tố là quy ước, không phải ràng buộc |
| **Không di trú dòng nào** — 4 văn bản hiện có giữ `tenant_id = NULL` | hai tenant vẫn không dùng được cùng một chuỗi phiên bản |
| Lùi được: bỏ cột là xong | |

### Phương án B — chấp thuận trỏ tới `doc_id` *(mô hình đúng, để sau)*

```sql
ALTER TABLE user_consents   ADD COLUMN doc_id UUID;
ALTER TABLE signer_consents ADD COLUMN doc_id UUID;
UPDATE user_consents c SET doc_id = d.doc_id
  FROM legal_documents d WHERE d.kind = c.kind AND d.version = c.version;
-- rồi mới đổi khoá ngoại, rồi mới đổi UNIQUE
```

Đúng về mô hình — một chấp thuận trỏ tới **một bản văn cụ thể**, không tới một
cặp chuỗi. Nhưng nó chạm vào chính bảng mang bằng chứng, và thứ tự bốn bước ở
trên phải chạy trọn vẹn: dừng giữa chừng để lại khoá ngoại cũ trên dữ liệu mới.

## 4. Chỗ đọc phải sửa (cả hai phương án)

`legal.current_document(kind)` là **cửa duy nhất** mọi nơi khác đi qua. Đổi nó
thành "ưu tiên bản của tenant, không có thì lấy bản nền tảng":

```python
def current_document(kind, tenant_id=None):
    # bản của tenant thắng; NULL = nền tảng, dùng làm mặc định
    ...ORDER BY (tenant_id IS NULL), effective_from DESC LIMIT 1
```

Sáu nơi gọi cần rà: `routers/legal.py` (4 chỗ), `routers/auth.py` (đăng ký),
`legal.record_consent` (kiểm phiên bản), `consent_gate._current_document_version`,
`legal.missing_for_registration`, `legal_admin`.

**Bẫy:** `record_consent` đối chiếu phiên bản người dùng gửi lên với bản đang
hiệu lực. Nếu nó đọc bản nền tảng trong khi giao diện hiển thị bản của tenant thì
mọi lượt ký trả `stale_version` — hỏng toàn bộ, và thông báo lỗi không gợi tới
nguyên nhân.

## 5. RLS

`legal_documents` phải vào danh sách RLS với policy **hai vế**: thấy văn bản của
chính tenant mình **và** văn bản nền tảng (`tenant_id IS NULL`). Bỏ vế thứ hai
thì không tổ chức nào đọc được điều khoản nền tảng, và đăng ký chết ngay.

Nhớ: `test_tenant_isolation::test_boundary_crossings_are_an_allowlist` và danh
sách bảng có RLS đều có test canh — thêm bảng mà quên khai là đỏ, và đó là hành
vi đúng.

## 6. Vì sao HOÃN, viết ra để khỏi đoán

Ba lý do, xếp theo sức nặng:

1. **Nó chạm vào chuỗi bằng chứng đồng thuận** — thứ vừa được nối xong ngày
   09/08 và là lõi đạo đức của cả hệ thống. Một lỗi ở đây không kêu; nó chỉ làm
   một bản ghi trỏ sai chỗ.
2. **Cây làm việc có 455 tệp chưa commit.** Không có mốc nào để lùi về. Một
   thay đổi lược đồ đụng khoá ngoại `RESTRICT` cần có đường lùi trước khi bắt
   đầu, và ở đây đường đó là một commit.
3. **Không tổ chức nào đang cần nó hôm nay** — hệ thống có đúng một tenant.
   Đây là khoảng trống của *thiết kế tham chiếu*, không phải của bản đang chạy.

Thứ tự đúng: **commit trước** → phương án A → dùng thật một thời gian → phương
án B khi có tenant thứ hai thật sự cần.

## 7. Kế hoạch test cho lượt thi công

| Phải chứng minh | Cách |
|---|---|
| Tenant không có văn bản riêng vẫn đọc được bản nền tảng | tenant mới, `current_document` trả bản `tenant_id IS NULL` |
| Bản của tenant thắng bản nền tảng | công bố cả hai, khẳng định trả bản của tenant |
| Đăng ký vẫn chạy khi tenant chưa có bản riêng | luồng đăng ký đầy đủ, không `consent_required` |
| `record_consent` đối chiếu ĐÚNG bản đang hiển thị | ký bản của tenant, không được ra `stale_version` |
| RLS không cho tenant A thấy văn bản riêng của tenant B | hai tenant, đọc chéo, kỳ vọng 0 dòng |
| 20 dòng chấp thuận cũ **không đứt** | đếm trước/sau, và khoá ngoại vẫn còn |
