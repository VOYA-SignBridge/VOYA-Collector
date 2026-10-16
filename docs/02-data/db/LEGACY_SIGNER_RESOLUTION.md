# Gỡ danh tính người ký

Trạng thái: **đang chờ người duyệt.** Không được sửa `signer_id` nào trước khi
xong. Đo trên `signdb`, lần cuối 24/08/2026.

| hiện vật | vai trò |
|---|---|
| [evidence/signer_resolution_matrix.csv](evidence/signer_resolution_matrix.csv) | **bảng làm việc chính** — 266 khối cần duyệt |
| [evidence/legacy_signer_review.csv](evidence/legacy_signer_review.csv) | từ điển 15 nhãn, hỗ trợ nhận diện biến thể tên |
| [evidence/v6_collection_signer_evidence.csv](evidence/v6_collection_signer_evidence.csv) | ảnh chụp trước khi v6 gỡ `collection_sessions.signer_id` |

## Đơn vị duyệt được SUY RA từ dữ liệu, không chọn trước

Bốn giả thuyết bị bác tuần tự, mỗi lần bằng một phép đo:

| # | giả thuyết | bác bởi |
|---|---|---|
| 1 | nhãn cũ = danh tính | `Minh` nằm dưới **5** `signer_id`; `Trâm`/`Tram` là một người viết hai kiểu |
| 2 | buổi thu có một người ký | **8/60** buổi có 2–3 nhãn |
| 3 | phiên thu có một người ký | **10/253** phiên có 2–3 nhãn |
| 4 | mẫu là đơn vị duy nhất khả dĩ | mẫu trong cùng lượt quay tách nhau sạch theo thời gian |

Đơn vị còn lại — và là đơn vị dùng — là **khối thời gian trong một phiên thu**:
cặp `(capture_session_id, nhãn)`, một đoạn mẫu liền mạch của cùng một người.

```
2a68d0c5:  Trân 06:52:17–06:53:03 │ Minh 06:53:29–06:55:26 │ Khoa 06:55:52–06:57:39
c4b163e7:  Trân 07:05:12–07:07:12 │ Minh 07:07:34–07:09:34 │ Khoa 07:10:02–07:12:00
```

Đây là hành vi thay phiên: quay xong lượt mình rồi nhường máy. Kiểm trên toàn bộ
**266 khối / 253 phiên: 0 cặp chồng lấn.** Ranh giới khối vì thế là dữ kiện, không
phải phỏng đoán — khác hẳn mọi phép khớp theo tên.

266 khối, không phải 3.864 mẫu. Nhỏ đủ để người duyệt tay.

## Vì sao `signer_id` hiện tại không dùng làm chuẩn được

```
S010  844 mẫu   Ảnh | Khoa | Minh | Nhung | Thư | Trân     ← SÁU người, một id
S011   55 mẫu   Khoa | Minh | Trân                          ← ba người
S001  432 mẫu   Huy | Minh                                  ← hai
S002  345 mẫu   Khang | Khoa                                ← hai
```

`S010`/`S011` không phải người. Ghi chú trong bảng `signers` nói thẳng:
`tu sinh 2026-08-08 khi va khoa ngoai` — chúng được chế ra để một khoá ngoại
chịu đi qua. Đường sinh ấy **đã gỡ 24/08/2026**; xem `tests/test_no_synthetic_signer.py`.

| | |
|---|---|
| mẫu có `signer_id` | 1.678 / 3.864 |
| trỏ vào người tự sinh (S010, S011) | **899** (53,6%) |
| thuộc về người xuất hiện dưới **nhiều** `signer_id` | **930** (55,4%) |

## Hệ quả nằm ngoài CSDL

Chia tập theo người ký (`--user_disjoint`) hiện **chưa chứng minh được điều nó tự
nhận**. Nhãn `Minh` nằm dưới cả `S001` lẫn `S010`; đẩy `S001` vào tập huấn luyện
và `S010` vào tập kiểm tra là để **cùng một người ở hai bên**. Gộp `S010` lại thì
kéo sáu người thật vào chung một phía.

Đây là vấn đề **hiệu lực phép đo**, không phải lược đồ. Cho tới khi 266 khối được
duyệt, kết quả cũ chỉ nên gọi là *chia rời theo ĐỊNH DANH*, không phải *chia rời
theo NGƯỜI*.

## Vì sao máy không được tự quyết, kể cả khi khối đã rõ

Chia khối chỉ trả lời **ranh giới nào thuộc cùng một lượt quay**. Nó KHÔNG trả
lời **người đó là ai**. Khối ghi `Minh` vẫn có thể là `Minh6868`, `Minh123`,
`Minh1234`, hoặc một người chưa có trong bảng.

```
Minh       1539 mẫu   5 signer_id, 4 tài khoản thu
Trâm 45 / Tram 5                    ← rất có thể một người
Thu Ngân 11 / Thungan 5 / Ngan 5    ← rất có thể một người
eeeaeb8b-a832-…                     ← không phải tên: UUID tài khoản lọt vào ô tên
```

Đoán ở đây không tạo ra dữ liệu sạch, nó tạo ra dữ liệu **sai mà trông sạch**.

## Cột trong bảng làm việc

| cột | nghĩa |
|---|---|
| `session_code` | mã phiên trình duyệt của buổi thu |
| `capture_session_id` | phiên thu chứa khối |
| `lop` | lớp ký hiệu của phiên |
| `nhan_goc` | `samples.user_id` nguyên văn — **không sửa** |
| `signer_hien_tai` | `signer_id` mà mẫu trong khối đang mang (có thể là id tự sinh) |
| `so_mau` | quy mô khối |
| `bat_dau`, `ket_thuc` | biên thời gian — thứ định nghĩa khối |
| `tai_khoan_thu` | tài khoản đã bấm nút thu (**≠** người ký) |
| `so_nguoi_trong_phien` | 1 nghĩa là phiên chỉ một người; >1 là phiên thay lượt |
| `signer_de_xuat`, `trang_thai`, `ghi_chu` | **để trống — phần người điền** |

### `trang_thai` dùng từ vựng cố định

```
CONFIRMED               đã xác định chắc chắn, `signer_de_xuat` mang id thật
NEW_SIGNER_REQUIRED     là người thật nhưng chưa có hàng `signers`; để trống id
AMBIGUOUS               không phân biệt được giữa nhiều người
UNKNOWN                 chưa xét
INVALID_LEGACY_LABEL    nhãn không phải tên người (ví dụ ô chứa UUID)
```

`signer_de_xuat` chỉ được chứa **một `signer_id` chuẩn có thật**. Không viết
`Minh?`, `maybe_S010`, `new`, `giống Tram` vào cột ấy — những nhận xét đó thuộc
về `ghi_chu`. Một trường định danh chứa phỏng đoán là cách nhanh nhất để phỏng
đoán biến thành sự thật ở lượt đọc sau.

## Sau khi duyệt xong

```
khối đã duyệt → signer_id chuẩn → mọi mẫu trong khối thời gian đó
```

Rồi mới xét `capture_sessions.signer_id`:

* mọi khối trong phiên ra **cùng một** người → giữ, coi như giá trị tóm tắt;
* phiên ra **nhiều** người → đặt `NULL`.

**Không chọn một người đại diện.** Đó đúng là lối tắt đã sinh ra `S010`.

Và chỉ sau đó mới: dựng lại split theo người ký, băm/đánh version lại split, chạy
lại đánh giá, rồi so với kết quả cũ. Split cũ không được ghi đè im lặng — nó phải
được đánh dấu là không còn đại diện cho tập đã đánh giá.

## Thực thể còn để ngỏ: `capture_segment`

266 khối gợi ra một thực thể tự nhiên — một **lượt** liên tục của một người trong
một phiên thu:

```
COLLECTION_SESSION ──< CAPTURE_SESSION ──< CAPTURE_SEGMENT ──< SAMPLE
                                                  │
                                               SIGNER
```

Nó hợp dữ liệu hơn hẳn việc gắn người ký lên tầng phiên. **Nhưng chưa dựng.**
266 khối hiện là hiện vật để duyệt, không phải bảng. Chỉ promote thành thực thể
thật khi khối được chứng minh là đơn vị ổn định cần lưu cho provenance và chia
tập — tránh lặp lại đúng lỗi của `collection_sessions.signer_id`: tạo bất biến
trước khi ngữ nghĩa được chứng minh.

Cho tới lúc đó, `capture_sessions.signer_id` **không còn được coi là chân lý ở
tầng phiên**. Danh tính chuẩn, sau khi duyệt, nằm ở `samples.signer_id`.

## Ba điều không được làm

1. **Đừng sửa `samples.user_id`.** Nó là bản ghi gốc và hiện đáng tin hơn
   `signer_id`. Chuẩn hoá tại chỗ là xoá bằng chứng.
2. **Đừng dùng `signer_aliases` cho `S010`/`S011`.** Alias là *nhiều id cũ → một
   người*; đây là *một id → nhiều người*. Ánh xạ `S010 → Minh` sẽ gán sai toàn bộ
   mẫu của Khoa, Ảnh, Trân, Nhung, Thư.
3. **Đừng tự sinh `signers` để khoá ngoại chịu đi qua.** Chưa biết thì `NULL`.
