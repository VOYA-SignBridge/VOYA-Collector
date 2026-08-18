# 10.6 Thiết kế chi tiết — Nghiệp vụ 6: Quản trị người dùng và chính sách

***9 use case** (UC601–UC609) cài đặt trên **34 điểm cuối** của hai bộ định tuyến
`admin` và `legal_admin`.*

Nghiệp vụ này trả lời: **ai đặt luật, và lấy gì làm bằng chứng?** Nó tách khỏi
Nghiệp vụ 7 dù cùng do quyền quản trị nền tảng kiểm, vì **hai nghiệp vụ hỏng theo
hai kiểu khác nhau**: NV6 sai thì **chính sách sai** — một tài khoản có quyền nó
không đáng có, một văn bản pháp lý sai hiệu lực. NV7 sai thì hệ thống **mất dữ
liệu hoặc chạy sai mã**.

---

## CN6.1 — Quản lý tài khoản và phân quyền nền tảng (UC601, UC602)

### Mục đích

Khoá, mở, cảnh báo và cấp/gỡ quyền quản trị nền tảng cho tài khoản.

### Giao diện 1 — Quản lý hệ thống (`/admin/users`, `AdminUsersPage.tsx`, 250 dòng)

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| 1 | Tiêu đề | **"Quản lý hệ thống"** — "Quản trị danh sách người dùng và phân quyền" |
| 2 | Cột bảng | **"Tên người dùng"** · **"Trạng thái"** · **"Quyền quản trị"** · **"Thao tác"** |
| 3 | Huy hiệu trạng thái | **"Hoạt động"** · **"Bị khóa"** · **"Khóa tạm"** · **"Vô hiệu"** · **"Đã cảnh báo"** |
| 4 | Nút | **"Khoá"** |
| 5 | Nút | **"Mở khoá"** |
| 6 | Nút | **"Cảnh báo"** |
| 7 | Hộp nhập cảnh báo | *"Nội dung cảnh báo gửi tới "{tên}" (người dùng sẽ thấy khi đăng nhập):"* |
| 8 | Nút | **"Cấp Admin"** / **"Gỡ Admin"** |
| 9 | Màn chờ | "Đang tải danh sách người dùng..." |
| 10 | Trạng thái rỗng | *"Không có người dùng nào."* |

**Thông báo kết quả:** *"Đã khóa tài khoản"* · *"Đã mở khóa tài khoản"* · *"Đã gửi
cảnh báo tới {tên}"* · *"Đã cập nhật quyền cho người dùng"*.

**Một chốt chặn đáng nói riêng:** *"Không thể tự gỡ quyền admin của chính mình!"*
Đây là ràng buộc chống tự khoá cửa — nếu quản trị viên cuối cùng gỡ quyền của
chính mình, hệ thống không còn ai cấp quyền lại được, và cách khôi phục duy nhất
là can thiệp trực tiếp vào cơ sở dữ liệu.

**Ba trạng thái khoá không được lẫn:** *"Bị khóa"* (khoá hành chính, vô thời hạn),
*"Khóa tạm"* (có `lock_until`, tự mở khi hết hạn), và *"Vô hiệu"* (`is_active` =
false). Chúng đến từ các cột khác nhau và có đường mở khác nhau.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `users` | | X *(khoá, cờ quản trị, `is_active`)* | | X |
| 2 | `refresh_tokens` | | X *(thu hồi khi khoá)* | | X |
| 3 | `notifications` | X *(cảnh báo)* | | | X |
| 4 | `audit_log` | X | | | |

### Ràng buộc

* Khoá tài khoản kích hoạt **mức thu hồi phiên thứ ba**: thu hồi theo biện pháp
  quản trị (NFR-C3)
* Lý do khoá do quản trị viên ghi **được hiển thị cho người dùng ở màn hình đăng
  nhập** — xem CN1.3 ngoại lệ 3
* Không tự gỡ quyền quản trị của chính mình

---

## CN6.2 — Phiên hoạt động, chặn IP và ngắt phiên (UC603)

### Mục đích

Nhìn thấy ai đang kết nối, từ đâu, và có công cụ **cắt ngay** khi cần.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `POST` | `/api/v1/admin/block-ip` | Chặn một địa chỉ IP |
| `POST` | `/api/v1/admin/unblock-ip` | Bỏ chặn |
| `POST` | `/api/v1/admin/force-logout` | Ngắt phiên của một tài khoản **kèm lý do** |

### Giao diện 1 — Phiên hoạt động (`/admin/activity`, `AdminActivityPage.tsx`, 577 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề | — | **"Phiên hoạt động"** — "Người dùng đang kết nối, vị trí, mức sử dụng và công cụ xử lý bất thường" |
| 2 | Công tắc cập nhật | trực tiếp | **"Trực tiếp"** / **"Tạm dừng"** |
| 3 | Chip chỉ số | — | **"Đang online"** |
| 4 | Chip chỉ số | — | **"Tổng phiên"** |
| 5 | Chip chỉ số | — | **"IP bị chặn"** (đổi màu đỏ khi > 0) |
| 6 | Chip chỉ số | — | **"Định vị GeoIP"** → **"Bật"** hoặc **"Chưa có DB"** |
| 7 | Nút | — | **"Chặn IP"** |
| 8 | Cột bảng | — | **"Người dùng"** · **"Vị trí"** · **"Trình duyệt"** · **"Hoạt động"** · **"Thao tác"** |
| 9 | Hộp nhập lý do ngắt | mẫu sẵn | *"Lý do ngắt phiên "{tên}" (sẽ hiển thị cho người dùng):"* — giá trị gợi ý: **"Vi phạm quy định sử dụng"** |
| 10 | Khối nhật ký kiểm toán | — | Đọc `audit_log` |
| 11 | Màn chờ | — | "Đang tải phiên hoạt động..." |

**Chip số 6 là một ví dụ về "giá trị đặc biệt để tránh suy luận sai".** **"Chưa có
DB"** khác hẳn với "không có ai ở xa": nó nói rằng **cột Vị trí không đáng tin**
vì cơ sở dữ liệu định vị chưa được nạp. Không phân biệt hai điều đó thì cột Vị trí
trống sẽ bị đọc thành thông tin.

**Thành phần số 9 buộc nhập lý do, và lý do đó hiển thị cho người dùng.** Ngắt
phiên không kèm lý do sẽ đẩy người dùng tới chỗ nghĩ hệ thống hỏng và thử lại
nhiều lần.

**Thông báo kết quả:** *"Đã chặn {ip}"* · *"Đã bỏ chặn {ip}"* · *"Đã đăng xuất
{tên}"*.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `refresh_tokens` | | X *(thu hồi)* | | X |
| 2 | Danh sách IP bị chặn trên Redis | X | | X | X |
| 3 | `audit_log` | X | | | X |
| 4 | `users` | | | | X |
| 5 | `notifications` | X | | | |

### Ràng buộc

* **NFR-C6** hạn mức và chặn tính theo **IP thật**, không cho phía gọi tự khai
* **BR-9.2** mọi thao tác ở đây để lại nhật ký kiểm toán bền vững
* Chặn IP **ảnh hưởng cả người dùng hợp lệ** dùng chung địa chỉ đó — đây là đánh
  đổi có ý thức, và là lý do có hai ngưỡng cảnh báo trung gian trước khi chặn tự
  động (CN1.3 ngoại lệ 2)

---

## CN6.3 — Soạn, công bố và theo dõi văn bản pháp lý (UC604, UC605, UC606)

### Mục đích

Đưa một văn bản pháp lý vào hiệu lực theo một đường **có bằng chứng**, và làm cho
nội dung đã công bố **không sửa được**.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/api/v1/admin/legal/documents` | Danh sách bản đã công bố |
| `POST` | `/api/v1/admin/legal/documents` | **Công bố** một bản |
| `POST` | `/api/v1/admin/legal/documents/upload` | Công bố từ tệp |
| `GET` · `POST` · `PATCH` | `/api/v1/admin/legal/drafts[/{id}]` | Bản nháp |
| `GET` | `/api/v1/admin/legal/events` | Lịch sử vòng đời |

### Giao diện 1 — Văn bản pháp lý (`/admin/legal`, `AdminLegalPage.tsx`, 437 dòng)

**Nhóm A — Đầu trang và cảnh báo thiếu văn bản**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| A1 | Tiêu đề | **"Văn bản pháp lý"** |
| A2 | **Ghi chú bất biến** | *"Nội dung một bản đã công bố không sửa được. Muốn đổi thì công bố phiên bản mới."* |
| A3 | Cảnh báo thiếu | **"Chưa công bố: {danh sách}"** |
| A4 | **Hệ quả của việc thiếu** | *"Khi chưa công bố, đăng ký vẫn chạy nhưng **không thu chấp thuận nào**."* |

**Cảnh báo A3 + A4 nói ra một hệ quả mà không ai đoán được từ giao diện khác:**
một bản triển khai chưa công bố văn bản nào vẫn cho đăng ký, nhưng **không thu
được chấp thuận nào** — tức mọi tài khoản tạo trong giai đoạn đó không có bằng
chứng chấp thuận. Đây là lý do cảnh báo này nằm ngay đầu trang.

**Nhóm B — Độ phủ chấp thuận**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| B1 | Tiêu đề khối | **"Độ phủ chấp thuận"** |
| B2 | Cột bảng | **"Loại"** · **"Bản hiện hành"** · **"Tài khoản"** · **"Đã đồng ý"** · **"Người dùng tự bấm"** · **"Còn thiếu"** |
| B3 | **Ghi chú phân biệt** | *"Chênh lệch giữa **Đã đồng ý** và **Người dùng tự bấm** là số dòng do người vận hành ghi hộ. **Chúng không phải chữ ký.**"* |

**Thành phần B3 là mục trung thực nhất của toàn bộ console quản trị.** Nó tách
**hai con số trông giống nhau**: số bản ghi chấp thuận tồn tại, và số bản ghi do
chính người dùng tạo ra. Phần chênh lệch là dữ liệu backfill — và bảng nói thẳng
rằng **chúng không phải chữ ký**. Không có cột này, một con số "độ phủ 100 %" sẽ
được đọc thành "mọi người đã đồng ý".

**Nhóm C — Bản nháp và công bố**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| C1 | Tiêu đề khối | **"Bản nháp"** |
| C2 | Hộp chọn | Nhãn trợ năng **"Loại văn bản cần soạn"** |
| C3 | Nút | **"Soạn bản mới"** |
| C4 | Ghi chú điểm xuất phát | *"Không có bản nháp nào đang mở. Bản mới sẽ chép sẵn nội dung bản đang hiệu lực làm điểm xuất phát."* |
| C5 | Tiêu đề khối | **"Các bản đã công bố"** |
| C6 | Cột bảng | **"Bản"** · **"Trạng thái"** |
| C7 | Trạng thái rỗng | *"Chưa công bố bản nào."* |
| C8 | Xem trước | **"{loại} — bản {phiên bản}"** |
| C9 | **Cổng xác thực lại** | Trước khi công bố: hộp thoại **"Công bố văn bản pháp lý"**; sai hoặc huỷ → *"Mật khẩu không đúng, hoặc bạn đã huỷ."* |

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `legal_document_drafts` | X | X | | X |
| 2 | `legal_documents` | X | **không sửa được** | | X |
| 3 | `legal_document_events` | X | | | X |
| 4 | `user_consents` | | | | X *(đếm độ phủ)* |
| 5 | `users` | | | | X *(mẫu số)* |
| 6 | `user_action_passcodes` | X | X | | X |
| 7 | `audit_log` | X | | | |

### Tiến trình

1. Quản trị viên chọn loại văn bản và bấm **"Soạn bản mới"**; hệ thống **chép sẵn
   nội dung bản đang hiệu lực** làm điểm xuất phát.
2. Sửa nội dung trên bản nháp (bản nháp **sửa được**, khác bản đã công bố).
3. Bấm công bố → **hộp thoại xác thực lại trong phiên** (C9).
4. Hệ thống tạo hàng mới trong `legal_documents` kèm **mã băm nội dung**, đặt ngày
   hiệu lực, ghi sự kiện vòng đời và nhật ký kiểm toán.
5. Từ thời điểm đó, nội dung bản này **bất biến ở tầng cơ sở dữ liệu** (trigger).

### Ràng buộc

* **BR-3.4** văn bản đã công bố **bất biến**, cưỡng chế bằng **trigger ở tầng CSDL**
  chứ không bằng kiểm tra ở ứng dụng
* **BR-3.5** cờ riêng tách "sửa lỗi chính tả" khỏi "đổi phạm vi xử lý dữ liệu";
  chỉ loại thứ hai buộc chấp thuận lại
* **BR-9.1** công bố văn bản pháp lý là một trong **ba thao tác đòi xác thực lại
  trong phiên**
* **BR-3.3** chấp thuận trỏ tới cặp (loại, phiên bản) — nên nếu nội dung sửa được
  dưới chân nó, **bằng chứng chấp thuận biến thành lời khẳng định suông**

---

## CN6.4 — Cấu hình nền tảng (UC607, UC608, UC609)

### Mục đích

Đặt các giá trị áp cho **mọi tổ chức**: bật/tắt kênh tin nhắn, ngưỡng cảnh báo,
tham số hạn mức mặc định.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `platform_settings` | X | X | | X |
| 2 | `plans` | X | X | | X |
| 3 | `audit_log` | X | | | |

### Ràng buộc

* Cấu hình nền tảng áp cho **mọi tổ chức** — sai ở đây là sai cho tất cả, và đó là
  lý do NV6 tách khỏi NV5
* Kênh tin nhắn tắt được ở đây, và **giao diện xác minh liên hệ phải xuống cấp có
  kiểm soát** khi đó (CN1.5 thành phần số 9)

---

## CN6.5 — Nhật ký kiểm toán

Không phải một use case riêng mà là **hạ tầng bằng chứng** cho toàn bộ NV6, nên
ghi thành mục riêng.

### Cơ chế

| Nơi ghi | Vai trò |
|---|---|
| Redis | Đường nhanh, đọc trong ứng dụng |
| `audit_log` (PostgreSQL) | **Bản bền** |

### Ràng buộc

* **BR-9.3** ghi nhật ký **từ chối khi thiếu phạm vi** (fail-closed) — không có
  ngữ cảnh tổ chức thì không ghi, thay vì ghi một dòng không quy được về đâu
* **BR-9.4** `audit_log.actor_label` là **bằng chứng lịch sử**: khi tài khoản đổi
  tên, năm chỗ khác được cập nhật theo nhưng cột này thì **không**. Một bản ghi
  kiểm toán phải nói ra tên **tại thời điểm hành động xảy ra**
* Ba chỉ số và ba cảnh báo Grafana dựng trên nhật ký này; giá trị **`-1`** trong
  chỉ số nghĩa là *"không đo được"*, **khác hẳn** `0`

---

## Tổng kết ma trận chức năng ↔ use case của Nghiệp vụ 6

| Chức năng | Use case phủ | Màn hình chính |
|---|---|---|
| CN6.1 Quản lý tài khoản và quyền nền tảng | UC601, UC602 | `/admin/users` |
| CN6.2 Phiên hoạt động, chặn IP, ngắt phiên | UC603 | `/admin/activity` |
| CN6.3 Văn bản pháp lý | UC604, UC605, UC606 | `/admin/legal` |
| CN6.4 Cấu hình nền tảng | UC607, UC608, UC609 | `/admin` (các khối cấu hình) |
| CN6.5 Nhật ký kiểm toán | — (hạ tầng bằng chứng) | `/admin/activity` |
