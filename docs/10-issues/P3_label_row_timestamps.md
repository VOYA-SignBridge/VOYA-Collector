# P3 — `GET /classes/list` đóng dấu thời gian MỚI ở mỗi lượt đọc

**Mở:** 16/08/2026 · **Mức:** P3 · **Cam kết:** không cam kết nào —
chất lượng dữ liệu, **không phải** cách ly

## Hiện tượng

Hai lượt `GET /api/v1/classes/list` cách nhau 0,7 giây, không có thao tác ghi
nào xen giữa:

```
.items[0].created_at:   '2026-08-16T01:26:13.621349Z' -> '2026-08-16T01:26:14.287754Z'
.items[0].migrated_at:  '2026-08-16T01:26:13.621370Z' -> '2026-08-16T01:26:14.287770Z'
```

Trong khi `labels.csv` lưu giá trị thật và **không đổi**:

```
created_at = 2026-08-15T00:00:00+00:00
```

Nghĩa là API **vứt bỏ giá trị đã lưu** và trả về thời điểm của chính lượt gọi.
`created_at` mà người dùng nhìn thấy luôn là "bây giờ", không phải lúc tạo.

## Nguyên nhân — một hàm dựng bị dùng làm hàm hiển thị

`ClassMetadata.to_label_row()` gán cứng:

```python
"created_at": now_str(),
"migrated_at": now_str(),
```

Điều đó **đúng** với mục đích gốc của nó: dựng một hàng MỚI khi đăng ký lớp
(`dataset_manager.py:936`), nơi `now()` thật sự là thời điểm tạo.

Sai ở chỗ `routers/classes.py:158` dùng lại chính hàm ấy để **hiển thị**:

```python
return {"count": len(metas), "items": [m.to_label_row() for m in metas]}
```

Bẫy này **đã được biết** ở đường ghi — `set_class_hands_required` có ghi rõ
trong docstring rằng "rebuilding rows via `to_label_row()` would clobber
created_at/migrated_at" và cố ý chỉ sửa đúng một ô. Đường đọc không có ghi chú
tương ứng, và đã bước vào.

## Vì sao KHÔNG phải vấn đề cách ly

Hai trường này đổi kể cả khi không ai chạm vào tenant nào khác — chúng là hàm
của đồng hồ, không phải của dữ liệu. Đã kiểm bằng cách quan sát chúng đổi giữa
hai lượt đọc liên tiếp không có thao tác ghi xen giữa.

Vì thế bộ đo `measure_read_isolation.py` loại trừ chúng ở READ-3, **có lý do
viết ra**, chứ không phải để phép thử hết đỏ. Nếu loại trừ chúng vô điều kiện mà
không ghi lại, một ngày nào đó `created_at` sẽ mang thông tin thật và phép loại
trừ sẽ che mất một rò rỉ.

## Hệ quả thật

* phản hồi API không tất định — máy khách nào so sánh/đệm theo `created_at` sẽ
  luôn thấy "đã đổi"
* thông tin xuất xứ hiển thị sai: không biết lớp được tạo lúc nào
* mọi so sánh trước/sau ở tầng kiểm thử phải tự loại trừ hai trường này

## Hướng sửa

`to_label_row()` nhận thêm tham số, hoặc tách hẳn hai hàm:

```
to_label_row()          dựng hàng MỚI      -> now() đúng
to_display_row()        hiển thị hàng CŨ   -> đọc giá trị đã lưu
```

Tách hai hàm là hướng nên chọn: cái tên khi ấy nói ra ý định, và chỗ gọi sai sẽ
lộ ra khi đọc chứ không phải khi đo.

## Trước khi sửa

Rà xem frontend có đang hiển thị `created_at` từ endpoint này không. Nếu có, sửa
xong sẽ làm giá trị hiển thị **thay đổi** (từ "hôm nay" thành ngày tạo thật) —
đó là sửa đúng, nhưng cần biết trước để không bị báo là hồi quy.
