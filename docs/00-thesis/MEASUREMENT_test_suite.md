# Bộ kiểm thử tự động — kết quả chạy

*Đo 18/08/2026 trên cơ sở dữ liệu `signdb_test`, qua `scripts/run_tests.sh`
(container dựng từ `backend/Dockerfile.test`, nối vào mạng compose). Mã kiểm thử
và mã dịch vụ ở đúng trạng thái của commit `ea10033`.*

```
lượt đầu      2.551 ca · 2.543 xanh · 7 đỏ · 1 bỏ qua  (20 ph 16 s)
              → 4 bản vá đóng 6 ca; ca thứ 7 xanh do xoá dữ liệu, chưa có bản vá
lượt xác nhận 2.551 ca · 2.550 xanh · 0 đỏ · 1 bỏ qua  (20 ph 49 s)
```

**Bảy ca đỏ, sáu nguyên nhân đã đóng.** Ca thứ bảy (§1c) xanh trở lại vì hàng dữ
liệu gây đỏ bị xoá tay, không vì nguyên nhân được sửa — nó sẽ đỏ lại nếu tái
diễn. Đọc "0 đỏ" của lượt xác nhận đúng như nó là: kết quả của **lượt ấy**.

Ca bỏ qua là bộ nghiên cứu chạy như tiến trình con, bỏ qua có điều kiện đúng như
thiết kế.

**Con số được công bố là của lượt xác nhận.** Lượt đầu vẫn được ghi ở đây, vì
một bộ kiểm thử chỉ xanh sau khi có người sửa thì phần đáng đọc nằm ở chỗ đã sửa
gì — và ở chỗ **sáu trong bảy ca đỏ không phải lỗi của sản phẩm**.

---

## 1. Bảy ca đỏ của lượt đầu, và cách phân định từng ca

```
FAILED test_account_rename.py::TestTenDiTheoDuLieu::test_doi_ten_keo_theo_hang_mau
FAILED test_account_rename.py::TestTenDiTheoDuLieu::test_bao_cao_so_hang_da_doi
FAILED test_account_rename.py::TestSoatTenLacHau::test_khong_con_hang_nao_lac_hau_sau_khi_doi
FAILED test_schema_backfill.py::test_every_sample_with_a_real_session_id_got_linked
FAILED test_schema_backfill.py::test_every_live_user_is_a_member_of_their_tenant
FAILED test_schema_backfill.py::test_admins_were_carried_over_as_admins
FAILED test_sot_integration.py::test_double_sync_is_idempotent
```

Nguyên tắc phân định: **không ca nào được gọi là "đỏ giả" nếu chưa truy được ra
hàng dữ liệu gây đỏ.** Cả bảy đều đã truy tới tận hàng.

### a) Ba ca đổi tên tài khoản — fixture dựng dữ liệu xuyên tổ chức

Triệu chứng: `users` đổi được 1 hàng, còn `samples.user_id`, `samples.username`,
`raw_uploads.*`, `signers.display_name` đều **0 hàng**.

```
[RENAME] ... 'rn17ab1355' -> 'rn17ab1355x'; {'samples.csv': 0, 'users': 1,
'samples.user_id': 0, 'samples.username': 0, 'raw_uploads.user_id': 0, ...}
```

Nguyên nhân nằm ở fixture, không ở đường đổi tên. Fixture mượn một lớp có thật
để thoả khoá ngoại, bằng câu `SELECT class_uid, tenant_id FROM classes LIMIT 1`
**không kèm `ORDER BY`**. Truy trực tiếp cho thấy nó nhận về lớp của tổ chức
`iso_b`, trong khi tài khoản thử thuộc `default`:

```
classes LIMIT 1     -> class_uid='isobdel63b5c5', tenant_id='iso_b'
tenant của users mới -> default
```

Hàng mẫu vì thế nằm ở một tổ chức khác hẳn tổ chức của chủ nó. Đường đổi tên lọc
`tenant_id = %s` — **cố ý**, và chú thích ngay trong mã nói rõ vì sao: không có
mệnh đề đó thì nhánh `auth_user_id IS NULL` sẽ đổi tên cả hàng vô chủ của tổ
chức khác trùng tên hiển thị. Sản phẩm từ chối đúng; phép kiểm đo sai thứ nó
tưởng mình đang đo.

Đáng chú ý về **thời điểm lộ**: câu `LIMIT 1` không `ORDER BY` chỉ đổi hành vi
khi `iso_a`/`iso_b` bắt đầu có dữ liệu. Nó là một phép kiểm phụ thuộc thứ tự,
nằm im cho tới khi một bộ đo khác gieo dữ liệu vào cùng cơ sở dữ liệu.

**Đã vá:** fixture lấy lớp trong đúng tổ chức của tài khoản, kèm `ORDER BY` để
tất định.

### b) Hai ca đối chiếu backfill — bất biến toàn cục bị nhiễm

Hai phép kiểm này nói về **một đợt backfill một lần** trên dữ liệu đã có, nhưng
khẳng định trên **toàn bảng**. Hàng gây đỏ:

| Phép kiểm | Hàng vi phạm | Bản chất |
|---|---|---|
| mẫu có `session_id` mà chưa nối phiên thu | 8 hàng, **toàn bộ** ở `iso_a`/`iso_b`, `session_id` dạng `sess-iso_a-target` | Fixture của bộ đo cách ly, tạo **sau** backfill; chúng chỉ cần tồn tại để bị thử đọc/ghi xuyên tổ chức nên không ai gán phiên thu |
| quản trị viên bị hạ vai | `iso_admin_a@iso_a` vai `editor` | Được gieo như vậy **có chủ ý**: bộ đo cần một tài khoản có cờ quản trị nền tảng nhưng vai trong tổ chức không đủ quyền, để tách hai câu hỏi "có phải quản trị nền tảng" và "có quyền trong tổ chức này" |

**Đã vá:** loại các tổ chức tổng hợp (`iso\_%`) khỏi hai bất biến này.

Bản vá đầu tiên **làm hai ca đỏ theo một cách khác**, và cái bẫy đáng ghi lại:
mệnh đề `LIKE 'iso\_%'` cho `IndexError: tuple index out of range` — một thông
điệp không nhắc gì tới `LIKE`. Lý do là `_fetch_all` khai `params: tuple = ()`
rồi vẫn truyền tuple rỗng ấy vào `cur.execute(sql, params)`, nên psycopg luôn
chạy bước nội suy và một `%` đơn thành ô giữ chỗ không có đối số. Phải viết `%%`.

### c) Một ca tài khoản thiếu tư cách thành viên — CHƯA CÓ BẢN VÁ

**Ca này xanh trở lại vì hàng dữ liệu gây đỏ bị xoá tay, không phải vì nguyên
nhân được sửa.** Sáu ca còn lại đều có một thay đổi mã hoặc cấu hình đứng sau;
ca này thì không. Ghi tách ra ở đây để không ai đọc "0 đỏ" thành "bảy nguyên
nhân đã đóng" — mới đóng sáu.

Hàng vi phạm là `t0044254306@default`, tạo lúc 10:56:59 **trong chính lượt chạy
ấy**, và vẫn còn sau khi suite tự khai *"đã xoá 232/232 hàng, 0 hàng còn sót"* —
tức nó nằm ngoài cơ chế dọn được theo dõi.

Chạy riêng ca tình nghi (`test_a_stale_version_from_an_open_tab_is_refused`, ca
duy nhất tạo tên đúng dạng mà không dọn) **không tái hiện**: không tài khoản nào
bị rò. Sản phẩm từ chối đăng ký đúng cách. Nguồn rò nằm ở một phép kiểm khác và
chưa truy ra.

**Không nới phép kiểm này.** Một tài khoản sống thiếu tư cách thành viên là lỗi
thật dù nằm ở tổ chức nào — mọi phép kiểm quyền theo tư cách thành viên sẽ trả
về "không phải thành viên", và phép đo cách ly mất đối chứng dương. Chỉ đổi phần
**báo cáo**: liệt kê đích danh tài khoản, tổ chức và thời điểm tạo, thay vì trả
về một con số trần bắt người đọc tự đi truy.

### d) Một ca đồng bộ nguồn sự thật — hệ quả của bản vá trong cùng lượt

`TimeoutError: The read operation timed out`. Xem §2.

---

## 2. Bản vá mã sản xuất, và bài học đắt nhất của lượt đo

Chương 4 §6.4a ghi rằng cách xử lý đúng cho sự cố treo ở mốc 62 % là hạ trần chờ
của khách hàng dịch vụ ngoài xuống **5 giây × 1 lần**. Biến môi trường đã được
đặt đúng, `scripts/run_tests.sh` đã truyền đúng.

Giá trị ấy **chưa bao giờ có hiệu lực**:

```python
self.timeout_seconds = max(30, int(timeout_seconds or 120))   # backend/app/storage/gdrive_client.py
```

Sàn 30 giây nuốt im lặng mọi cấu hình thấp hơn nó. Đây là dạng hỏng nguy hiểm
hơn một lỗi lộ liễu, vì **nó trông như đã được xử lý**: tài liệu ghi có, cấu
hình có, hành vi thì không.

Sàn được hạ xuống 1 để cấu hình có hiệu lực thật. Ngay lượt chạy sau đó,
`test_double_sync_is_idempotent` đỏ vì một lượt đọc Drive cần hơn 5 giây — tức
con số đã chạy tốt suốt thời gian qua vốn là **30**, còn 5 chỉ tồn tại trên
giấy. Mặc định của môi trường kiểm thử vì vậy được ghi đúng thành 30.

> **Hệ quả cho phương pháp, áp cho mọi biện pháp giảm thiểu về sau:** một biện
> pháp chưa được quan sát thấy có tác dụng thì chưa phải là một biện pháp đã áp
> dụng.

---

## 3. Ba con số hay bị nhầm với nhau

| Con số | Giá trị | Nó là gì |
|---|---|---|
| Ca thu thập được | **2.551** | Số **ca** pytest dựng ra — tham số hoá làm một hàm sinh nhiều ca |
| Ca chạy xanh | **2.550** (18/08/2026) | Số ca của một **lượt chạy thật**, kèm 1 bỏ qua |
| Hàm kiểm thử, đếm tĩnh | **2.010** trong 150 tệp | Số **hàm** trong mã nguồn — **không phải** số đã chạy xanh |

Rủi ro R8 của kế hoạch kiểm thử là báo con số đếm tĩnh như thể nó là số đã chạy.
Chỉ con số của lượt chạy thật mới được viết vào quyển, và phải kèm ngày.

*Số hàm kiểm thử phía giao diện trong Chương 4 (**429** trong 58 tệp) được giữ
nguyên từ lượt đo trước: bộ đếm dùng ở đây cho 380 trong 51 tệp, tức hai công cụ
đếm hai thứ khác nhau. Thay một con số không tái lập được bằng một con số không
tái lập được khác thì không cải thiện gì — chỗ này cần một phép đếm có công cụ
xác định trước khi sửa.*

---

## 4. Tái lập

```sh
bash scripts/run_tests.sh backend/tests -q -rf
```

Hai lớp chặn của kịch bản bảo đảm lượt chạy không nhắm vào `signdb`: nó viết lại
DSN sang vai kiểm thử và cơ sở dữ liệu kiểm thử, và hai vai ấy không có quyền
`CONNECT` vào cơ sở dữ liệu sản xuất. Lớp thứ hai là fixture của pytest, nên
công cụ nào chạy qua `VOYA_TEST_CMD` phải tự kiểm `current_database()`.

Kết quả chi tiết theo từng nghiệp vụ ở **Phụ lục D**; bối cảnh và cách đọc ở
**Chương 4 §6.3–§6.4**.
