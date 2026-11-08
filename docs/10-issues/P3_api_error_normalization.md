# P3 — Mã lỗi khai báo 404 nhưng endpoint trả 400

**Mở:** 16/08/2026 · **Mức:** P3 (thấp) · **Cam kết liên quan:** không cam kết
nào trong đề cương — đây là chất lượng API, không phải an ninh

## Hiện tượng

`catalog_sync` khai báo:

```python
raise CatalogSyncError(f"Target class {target_class_ref} not found",
                       status_code=404, error_code="CLASS_NOT_FOUND")
```

nhưng đo qua HTTP (16/08/2026, `reassign_gate.json`):

```
T0  A -> lớp KHÔNG TỒN TẠI   HTTP 400  {"detail":"Target class khongtontai0000 not found"}
T1  A -> lớp của tenant B    HTTP 400  {"detail":"Target class isobtarg504e83 not found"}
```

Bộ bắt lỗi của router làm phẳng `CatalogSyncError` xuống 400, bỏ qua
`status_code` đã khai.

## Vì sao KHÔNG phải vấn đề an ninh

Không có phép thử tồn tại tenant ở đây: T0 và T1 trả **cùng** mã trạng thái, và
thân phản hồi chỉ khác nhau ở tiếng vọng định danh do chính người gọi cung cấp.
Sau khi chuẩn hoá phần tiếng vọng, hai thân giống hệt nhau.

Nói cách khác, lỗi này làm mã trạng thái **kém chính xác đều nhau cho mọi
trường hợp** — nó không phân biệt được tenant, nên không rò gì.

## Vì sao vẫn nên sửa

* 400 nghĩa là "yêu cầu của bạn sai cú pháp"; 404 nghĩa là "không có thứ đó".
  Máy khách phân biệt hai việc ấy để quyết định có thử lại hay không.
* `error_code` đã khai đúng nhưng `status_code` bị bỏ, nên hợp đồng lỗi hiện
  **không nhất quán giữa hai trường của cùng một ngoại lệ**.

## Vì sao KHÔNG sửa trong P0

Bộ bắt lỗi này phủ mọi đường của `catalog_sync`. Đổi nó sẽ đổi mã trạng thái của
một loạt endpoint cùng lúc, giữa lúc ~35 caller đang chuyển đổi — dễ tạo hồi quy
không liên quan và làm nhiễu chính phép đo đang chạy.

## Khi sửa

Rà xem có phép thử hoặc mã frontend nào đang **dựa vào** 400 không, trước khi
đổi. Một mã trạng thái sai đã tồn tại đủ lâu thì thường đã có người viết mã dựa
vào nó.
