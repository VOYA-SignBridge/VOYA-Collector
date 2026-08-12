# Văn bản pháp lý là TỆP, không phải markdown

*Thêm 2026-08-10 (lược đồ v3.15). Không thay thế `docs/LEGAL_DOCUMENTS.md` — bổ
sung một đường lưu trữ thứ hai bên cạnh đường markdown đã có.*

---

## 1. Vì sao

Văn bản pháp lý thật không ra đời trong một ô soạn markdown. Phòng pháp chế gửi
`.docx`; bản đã ký và đóng dấu về dưới dạng `.pdf`. Bắt người ta dán nội dung
vào một ô markdown làm mất **định dạng**, mất **chữ ký**, mất **con dấu** — và
mất luôn bản gốc để đối chiếu khi có tranh chấp.

Đường markdown **không bị bỏ**. Bốn văn bản đã công bố trên máy chạy thật đang
mang thân markdown, và có chữ ký trỏ vào băm của thân đó. Hai đường cùng sống;
`body_format` là thứ phân biệt (`markdown` | `text` | `file`).

## 2. Lưu ở đâu

Cùng kho định-địa-chỉ-bằng-nội-dung mà markdown đang dùng
(`app/legal_store.py`), nên tính **bất biến** và **khử trùng lặp** có sẵn:

```
dataset/legal/<kind>/<hash[0:2]>/<hash><ext>
```

Tên tệp LÀ băm sha256 của nội dung. Không có cách nào tráo nội dung mà giữ
nguyên địa chỉ — với một tài liệu có chữ ký trỏ vào, đó là tính chất quan trọng
nhất.

Đuôi tệp theo **danh sách trắng** (`ALLOWED_EXTENSIONS`): `.pdf`, `.docx`,
`.doc`, `.odt`, `.md`, `.txt`. Danh sách trắng chứ không phải đen — một kho nhận
mọi thứ trừ vài đuôi cấm sẽ nhận `.svg` (chạy được script khi mở trực tiếp) và
`.html`. Trần kích thước 25 MB.

## 3. Băm mô tả đúng thứ người ta ký

Đây là tính chất phải giữ bằng mọi giá:

| Loại | `content_hash` là băm của |
|---|---|
| `markdown` / `text` | byte UTF-8 của **thân bài** |
| `file` | byte của **tệp** |

`user_consents` trỏ tới `(kind, version)`, và `content_hash` là thứ cho phép một
người đối chiếu bản họ đang xem với bản họ đã ký. Băm sai thứ nghĩa là một chữ
ký không đối chiếu được với bất cứ cái gì.

Ghim ở `test_legal_files.py::test_bam_la_bam_BYTE_CUA_TEP` và
`::test_bam_cua_ban_markdown_van_la_bam_UTF8_cua_than_bai`.

## 4. Lược đồ

Bốn cột **NULLABLE** trên `legal_documents`, và nullable là bắt buộc: bốn văn
bản đã công bố không có tệp. Một cột `NOT NULL` ở đây sẽ hoặc chặn migration,
hoặc buộc phải bịa một giá trị cho hàng cũ — và bịa dữ liệu trên bảng làm bằng
chứng pháp lý là điều không được phép.

```sql
file_key   TEXT    -- khoá trong kho blob
file_name  TEXT    -- tên gốc, hiện lúc tải về
file_mime  TEXT    -- suy từ ĐUÔI CỦA KHOÁ, không từ header người tải lên khai
file_size  BIGINT
```

Hai ràng buộc đi kèm:

* `ck_legal_documents_body_format` được **nới** để nhận `'file'`. Ràng buộc cũ
  chỉ cho `('markdown','text')` và nó đã chặn đúng — một cột trạng thái không có
  CHECK là một cột sẽ nhận mọi lỗi chính tả.
* `ck_legal_documents_file_pair` — `(body_format = 'file') = (file_key IS NOT NULL)`.
  Thiếu nó, một lượt ghi hụt tạo ra hàng `body_format='file'` mà `file_key` NULL:
  giao diện chọn trình đọc tệp, và người dùng thấy trang trắng thay vì điều khoản
  họ sắp ký.

## 5. API

### Tải lên — `POST /admin/legal/documents/upload`

`multipart/form-data`, **cần nâng quyền** (`sudo`), quản trị viên nền tảng.

| Trường | Bắt buộc | Ghi chú |
|---|---|---|
| `kind` | có | một trong `terms`, `privacy`, `data_contribution`, `guardian` |
| `version` | có | không sửa được sau khi công bố |
| `file` | có | ≤ 25 MB, đuôi trong danh sách trắng |
| `title`, `language`, `change_summary` | không | |
| `requires_reconsent` | không | bật = đá mọi người dùng ra màn hình chấp thuận |
| `effective_from` | không | ISO 8601. Bỏ trống = ngay; tương lai = lên lịch |

Đi qua **cùng một** `legal.register_document` với đường markdown — nên khoá tư
vấn theo loại, nhánh idempotent, và cách xử lý xung đột `uq_legal_effective`
dùng chung, không nhân bản.

### Tải xuống — `GET /legal/{kind}/file`

**CÔNG KHAI**, cùng lý do như `/{kind}/content`: phải đọc được **trước khi** tạo
tài khoản. Gác nó sau cổng đăng nhập nghĩa là bắt người ta đồng ý với thứ họ
chưa mở ra được. Đã thêm bốn đường vào `PUBLIC_ROUTES`.

`?version=` để đọc lại đúng bản mình đã ký. `?download=true` buộc tải về; bỏ
trống thì trình duyệt tự mở.

Hai chi tiết quyết định tính an toàn:

* **`Content-Type` suy từ ĐUÔI CỦA KHOÁ trong kho**, không từ cột `file_mime` và
  càng không từ header người tải lên khai. Khoá do `storage_key` sinh ra và đuôi
  của nó đã qua danh sách trắng, nên kể cả khi một hàng trong cơ sở dữ liệu bị
  sửa, đường này vẫn không phục vụ được một kiểu nội dung ngoài dự kiến.
* **`Content-Disposition` luôn có `filename`, đã làm sạch.** Một tên tệp mang
  dấu ngoặc kép hoặc xuống dòng là một header bị tách.

Kèm `X-Content-Type-Options: nosniff` và `Cache-Control: immutable` — nội dung
định địa chỉ bằng băm thì bất biến, nên cache được vĩnh viễn.

## 6. Giao diện

`components/legal/DocumentViewer.tsx` chọn một trong ba đường:

1. `file` + PDF → nhúng thẳng bằng `<object>`
2. `file` + định dạng khác → thẻ siêu dữ liệu + nút tải
3. còn lại → markdown, đúng như trước

**Vì sao không dựng trình đọc DOCX trong trình duyệt.** Không trình duyệt nào mở
được `.docx` tự nhiên. Hai cách làm được đều tệ hơn việc không làm: kéo về một
thư viện chuyển đổi vài trăm KB cho ra bản dựng *gần giống* bản gốc — và với tài
liệu người ta sắp ký thì "gần giống" là hướng hỏng tệ nhất, vì nó trông như bản
thật; hoặc gửi tệp qua dịch vụ xem của bên thứ ba, tức **gửi văn bản pháp lý của
tổ chức ra ngoài**.

Nên: nói thẳng đây là tệp gì, bao nhiêu byte, và đưa nút tải.

**`<object>` chứ không phải `<iframe>`** — `<object>` có nội dung dự phòng dựng
sẵn, nên trình duyệt không mở được PDF (nhiều trình duyệt di động) sẽ thấy một
lời giải thích kèm nút tải thay vì một khung trắng.

Biểu mẫu tải lên: `components/legal/UploadDocumentForm.tsx`, gắn ở
`/admin/legal`, đặt **trước** trình soạn markdown vì đây là đường thường dùng.

## 7. Kiểm chứng

| Tệp | Số test | Canh gì |
|---|---|---|
| `backend/tests/test_legal_files.py` | 17 | kho nhị phân, danh sách trắng đuôi, băm đúng thứ, **đường markdown cũ không hỏng** |

Nhóm `TestDuongMarkdownCuKhongHong` tồn tại riêng để một đường lưu trữ MỚI không
giết đường CŨ trong im lặng.

```bash
docker run ... voya_backend_test:latest python -m pytest tests/test_legal_files.py -q
```

## 8. Chưa làm

* **Không có đường xoá tệp.** Cùng mô hình với văn bản: đã công bố thì không sửa,
  không xoá — `ON DELETE RESTRICT` từ `user_consents` chặn ngay khi có người đầu
  tiên ký.
* **`collect_garbage` giờ thấy tệp nhị phân** (`iter_keys` duyệt cả danh sách
  đuôi), nhưng vẫn mặc định `dry_run=True` và chưa có lịch chạy.
* **Chưa quét virus.** Tệp do quản trị viên nền tảng tải lên, không phải người
  dùng cuối, nên bề mặt hẹp — nhưng đây là một giả định, không phải một biện pháp.
