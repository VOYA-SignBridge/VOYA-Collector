# CDM v8 — gói nhập PowerDesigner

Mô hình khái niệm **hiện trạng** (as-built) của CTU.SignBridge, sinh từ bằng
chứng catalog đã đóng băng ở `../evidence/`.

```
49  thực thể      33 mạnh · 12 phụ thuộc · 4 kết hợp
399 thuộc tính
53  định danh     49 chính + 4 thay thế
116 quan hệ       111 suy từ khoá ngoại + 5 khai tay · 12 định danh
```

## Chạy

1. Mở PowerDesigner, tạo một **Conceptual Data Model** rỗng, lưu vào **chính
   thư mục này** (script tìm CSV cạnh tệp `.cdm`).
2. `Tools → Execute Commands → Edit/Run Script` (Ctrl+Shift+X), mở
   `06_powerdesigner_import.vbs`, bấm Run.
3. Hộp thoại cuối in ra bốn con số. **Phải là 49 / 399 / 53 / 116.** Lệch con
   số nào thì dừng và đối chiếu CSV — đừng sửa tay trên sơ đồ, vì sửa tay là
   lúc mô hình bắt đầu trôi khỏi bằng chứng.

Script **không** đặt vị trí hộp. Bố cục để PowerDesigner tự sắp rồi chỉnh tay,
cùng lý do bộ sinh ERD tách hình học khỏi ngữ nghĩa.

## Vì sao không có tệp `.cdm` sẵn

Định dạng XML của PowerDesigner phụ thuộc phiên bản và mang internal object ID.
Tự đoán nó là cách chắc chắn tạo ra một tệp **mở được nhưng sai** — đúng loại
lỗi khó phát hiện nhất. Script trên dùng chính API của PowerDesigner.

## Ba ranh giới gói này giữ

**CDM này là HIỆN TRẠNG, không phải kiến trúc đích.** Các cải tiến đã bàn —
`Sample Review`, `Quality Assessment`, `Processing Result`, `File Object`,
`Model Version`, `Quota Metric`, `Consent Evidence` — **không có bảng nào chống
lưng**, nên chúng không nằm ở đây. Chúng thuộc một mô hình *refined* riêng.
Trộn hai thứ vào một hình là làm người đọc không phân biệt được đâu là hệ thống,
đâu là đề xuất.

**Không có khoá ngoại trong hộp thực thể.** `tenant_id`, `user_id`, `project_id`
chỉ xuất hiện qua quan hệ; PowerDesigner sẽ tự sinh chúng khi chuyển xuống LDM
rồi PDM. Ngoại lệ có chủ ý: các thuộc tính kết thúc bằng **`Snapshot`**.

**`… Snapshot` KHÔNG phải quan hệ.** `Legal Document Event` và `Tenant Purge`
giữ định danh của đối tượng liên quan dưới dạng **ảnh chụp**, và trong CSDL
chúng **cố ý không có khoá ngoại**: một sổ đăng bạ không được cản chính hành
động nó ghi lại, và lịch sử purge phải sống sót sau khi tenant bị xoá. Nối quan
hệ từ chúng là phá đúng tính chất ấy.

## Định danh: nghiệp vụ, không phải khoá thay thế

UUID và serial của PostgreSQL **không** vào CDM. Định danh lấy từ khoá tự nhiên:
`Tenant Slug`, `Username`, `Language Code`, `Prefix`, `Document Kind`…

Khi một thực thể không có khoá tự nhiên bền vững — `Audit Entry`,
`Support Message`, `Webhook Delivery` — thì một định danh sự kiện ở mức khái
niệm là hợp lệ; không giả vờ tìm khoá tự nhiên không tồn tại.

**Khoá duy nhất MỘT PHẦN không được dùng làm định danh.** `Workspace` +
`Name` chỉ duy nhất khi `deleted_at IS NULL`, nên xoá mềm rồi tạo lại cùng tên
sẽ cho hai occurrence trùng định danh. Chúng được ghi là *alternate identifier
áp cho bản ghi đang sống*, không phải định danh chính.

## Năm quan hệ khai tay, và vì sao

| quan hệ | thay cho |
|---|---|
| `Legal Document` 1 — 1..N `Legal Document Version` | tách từ khoá tự nhiên `(kind, version)` |
| `Role` M — N `Permission` *(Granted At)* | bảng `role_permissions` |
| `API Key` M — N `Permission` | thuộc tính `scopes` đã loại |
| `Tenant Invitation` 0..N — 0..1 `Role` | thuộc tính `role` dạng text đã loại |
| `Tenant` 0..1 — 0..1 `Registry Version` | bảng `vocabulary_registry_meta` |

## 111 quan hệ từ 131 khoá ngoại

Chênh lệch có ba nguồn, không phải mất mát:

* khoá ngoại của bảng **không vào CDM** (chứng thực, outbox, migration…)
* khoá ngoại của bảng **đã gộp** vào cha hoặc đã thành quan hệ
* **hợp nhất theo cột neo**: hai khoá ngoại cùng neo một cột và cùng trỏ một
  cha là **một** quan hệ khái niệm; khoá ghép thắng. Cùng luật bộ sinh ERD dùng.

Bằng chứng cho việc gộp theo **cột neo** chứ không theo cặp bảng: `Sample` có
hai khoá ngoại tới `User` và chúng **không** gộp, vì neo vào `auth_user_id`
(người thu) và `reviewed_by` (người duyệt) — hai liên kết thật sự khác nhau.

## Tệp

| tệp | nội dung |
|---|---|
| `01_entities.csv` | 49 thực thể · loại · cha định danh · bảng nguồn |
| `02_attributes.csv` | 399 thuộc tính · kiểu · thứ tự · cột nguồn |
| `03_identifiers.csv` | định danh chính và thay thế |
| `04_relationships.csv` | 116 quan hệ · lực lượng hai đầu · có định danh không · nguồn |
| `05_relationship_attributes.csv` | thuộc tính của quan hệ M:N |
| `06_powerdesigner_import.vbs` | script nhập |

Cột **`Source Table`** và **`Source Column`** giữ đường về PDM, nên mọi dòng
trong CDM truy ngược được tới `../evidence/` — không dòng nào ra đời từ trí nhớ.
