# Gỡ danh tính người ký khỏi nhãn cũ

Đo ngày 23/08/2026 trên `signdb`. Bảng làm việc: [legacy_signer_review.csv](legacy_signer_review.csv).

## Việc tưởng là gì

`samples.user_id` là một ô **chữ tự do** ghi tên người ký trước ống kính — di sản
từ trước khi có bảng `signers`. Kế hoạch: ánh xạ 15 nhãn ấy về `signer_id` rồi bỏ
cột.

## Việc thật ra là gì

Chiều ánh xạ đang **ngược**. `signer_id` — thứ lẽ ra là danh tính chuẩn — hiện
kém tin cậy hơn chính cái nhãn chữ nó phải thay thế.

```
S010  844 mẫu   Ảnh | Khoa | Minh | Nhung | Thư | Trân     ← SÁU người, một id
S011   55 mẫu   Khoa | Minh | Trân                          ← ba người
S001  432 mẫu   Huy | Minh                                  ← hai
S002  345 mẫu   Khang | Khoa                                ← hai
S103    1 mẫu   Minh
S104    1 mẫu   Minh
```

`S010` và `S011` không phải người. Ghi chú trong bảng `signers` nói thẳng:

> `tu sinh 2026-08-08 khi va khoa ngoai: samples tham chieu signer_id chua co dong`

Chúng được **chế ra để một khoá ngoại chịu đi qua**, và giờ 899 mẫu treo dưới hai
cái tên không đại diện cho ai cả.

## Ba con số

| | |
|---|---|
| mẫu có `signer_id` | 1.678 / 3.864 |
| trong đó trỏ vào người **tự sinh** (S010, S011) | **899** (53,6%) |
| mẫu thuộc về một người xuất hiện dưới **nhiều** `signer_id` | **930** (55,4%) |

## Hệ quả không nằm trong CSDL

Chia tập theo người ký (`--user_disjoint`) hiện **không chia được đúng**. Nhãn
`Minh` nằm dưới cả `S001` lẫn `S010`; đẩy `S001` vào tập huấn luyện và `S010` vào
tập kiểm tra là để **cùng một người ở cả hai bên** — đúng thứ chia theo người ký
sinh ra để ngăn. Ngược lại, gộp `S010` thành một người sẽ kéo sáu người thật vào
chung một phía.

Nói cách khác: mọi con số đo bằng chia-theo-người-ký trên dữ liệu hiện tại đều
chưa chứng minh được điều nó tự nhận. Đây là vấn đề **hiệu lực phép đo**, không
phải vấn đề lược đồ.

## Vì sao máy không được tự quyết

```
Minh       1539 mẫu   5 signer_id, 4 tài khoản thu (Minh, Minh123, Minh1234, Minh6868)
Trân        620       2 signer_id
Khoa        579       3 signer_id
Trâm  45  /  Tram  5              ← rất có thể một người, hai cách viết
Thu Ngân 11 / Thungan 5 / Ngan 5  ← rất có thể một người, ba cách viết
eeeaeb8b-a832-4d1d-bac7-ebdd819fc644   ← không phải tên: đây là UUID tài khoản
                                          của người dùng `Minh`, lọt vào ô tên
```

Không phép khớp chuỗi nào — kể cả bỏ dấu rồi so — phân biệt được `Minh` nào là
`Minh6868` và `Minh` nào là `Minh123`. Đoán ở đây không tạo ra dữ liệu sạch, nó
tạo ra dữ liệu **sai mà trông sạch**.

## Cách làm đề nghị

1. **Đừng sửa `samples.user_id`.** Nó là bản ghi gốc; chuẩn hoá tại chỗ là xoá
   bằng chứng. Cột `goi_y_chuan_hoa` trong CSV chỉ là gợi ý để xếp nhóm khi đọc.
2. Người biết dữ liệu điền hai cột `signer_id_de_xuat` và `trang_thai`
   (`UNRESOLVED` · `CONFIRMED` · `NEW_SIGNER_REQUIRED` · `AMBIGUOUS` · `INVALID`).
3. `S010`/`S011` phải được **tách**, không phải đổi tên: mỗi người thật trong đó
   cần một hàng `signers` riêng.
4. Chỉ khi bảng được duyệt xong mới chạy backfill, và backfill phải có hậu điều
   kiện như mọi bước dữ liệu khác — xem `MIGRATION_DATA_STEPS`.

Trước bước 4, `samples.user_id` **không được bỏ**, và mọi kết quả chia theo người
ký nên nói rõ giới hạn này.

## Cột trong bảng làm việc

| cột | nghĩa |
|---|---|
| `nhan_goc` | `samples.user_id` nguyên văn — không sửa |
| `goi_y_chuan_hoa` | thường hoá + cắt khoảng trắng, **chỉ để xếp nhóm** |
| `so_mau`, `mau_da_co_nguoi_ky` | quy mô, và phần đã có `signer_id` |
| `signer_id_dang_mang` | các `signer_id` mà mẫu của nhãn này đang trỏ tới |
| `so_capture_session`, `so_lop` | độ phủ |
| `ngay_dau`, `ngay_cuoi` | khoảng thời gian thu |
| `tai_khoan_thu` | tài khoản đã bấm nút thu (≠ người ký) |
| `signer_id_de_xuat`, `trang_thai`, `ghi_chu` | **để trống — phần người điền** |
