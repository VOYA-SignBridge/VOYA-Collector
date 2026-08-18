# 10.1 Thiết kế chi tiết — Nghiệp vụ 1: Danh tính và quyền truy cập

*Nghiệp vụ này gồm **14 use case** (UC101–UC114) cài đặt trên **34 điểm cuối** của
năm bộ định tuyến `auth`, `verification`, `two_factor`, `legal`, `trial`.*

**Khung trình bày mỗi chức năng:** Mục đích · Điểm cuối API · Giao diện · Thành
phần điều khiển · Dữ liệu sử dụng · Tiến trình · Luồng luân phiên · Luồng ngoại lệ
· Ràng buộc.

**Nguồn dựng bảng thành phần:** đọc trực tiếp mã màn hình. Nhãn điều khiển ghi
**nguyên văn** chuỗi hiển thị trong mã, để đối chiếu lại được.

---

## CN1.1 — Đăng ký tài khoản (UC101)

### Mục đích

Tạo một tài khoản mới **chưa thuộc tổ chức nào**, và làm cho việc chấp thuận văn
bản pháp lý trở thành **điều kiện tồn tại** của tài khoản đó chứ không phải một
bước tuỳ chọn sau khi đăng ký.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/api/v1/legal/documents` | Lấy danh sách văn bản đang hiệu lực để dựng ô tích |
| `POST` | `/api/v1/auth/register` | Tạo tài khoản kèm danh sách văn bản đã chấp thuận |

### Giao diện 1 — Tạo tài khoản (`/register`, `RegisterPage.tsx`, 328 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Khung trang xác thực | — | `AuthShell`, tiêu đề **"Tạo tài khoản"** |
| 2 | Liên kết chân trang | — | "Đã có tài khoản?" → **"Đăng nhập →"** sang `/login` |
| 3 | Ô nhập văn bản | rỗng | **"Tên đăng nhập"** |
| 4 | Ô nhập văn bản | rỗng | **"Địa chỉ email"**; lỗi tại chỗ: "Email không đúng định dạng." / "Vui lòng nhập email." |
| 5 | Ô nhập mật khẩu | rỗng | **"Mật khẩu"**, gợi ý nhập "Tối thiểu 8 ký tự"; lỗi: "Mật khẩu phải có ít nhất 8 ký tự." |
| 6 | Ô nhập mật khẩu | rỗng | **"Xác nhận mật khẩu"**, gợi ý "Nhập lại mật khẩu"; lỗi: "Mật khẩu xác nhận không khớp." |
| 7 | Nút chuyển chế độ hiển thị | ẩn | **"Hiện"** / **"Ẩn"** — áp cho cả hai ô mật khẩu |
| 8 | Ô tích chấp thuận | **bỏ tích** | "Tôi đã đọc và đồng ý với" + danh sách liên kết văn bản, mỗi văn bản kèm **"(bản {v})"** |
| 9 | Liên kết văn bản | — | Mở `/legal/:kind` ở phiên bản đang hiệu lực |
| 10 | Thông báo chặn | ẩn | **"Bạn cần đọc và đồng ý trước khi tạo tài khoản."** |
| 11 | Nút gửi | — | **"Tạo tài khoản"**; khi đang gửi đổi thành "Đang tạo tài khoản..." |

**Chi tiết đáng chú ý ở thành phần số 8:** ô tích **không** liệt kê một chuỗi cố
định. Danh sách văn bản được lấy từ máy chủ tại thời điểm mở trang, và mỗi mục
mang **số hiệu phiên bản**. Đây là điều làm bản ghi chấp thuận trỏ được tới một
cặp (loại, phiên bản) xác định thay vì trỏ tới khái niệm mơ hồ "điều khoản hiện
hành".

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `users` | X | | | X |
| 2 | `legal_documents` | | | | X |
| 3 | `user_consents` | X | | | |
| 4 | `verification_codes` | X | | | |
| 5 | `audit_log` | X | | | |

### Tiến trình

1. Hệ thống gọi `GET /api/v1/legal/documents`, dựng danh sách văn bản đang hiệu
   lực kèm số hiệu phiên bản.
2. Khách vãng lai nhập tên đăng nhập, email, mật khẩu và xác nhận mật khẩu.
3. Hệ thống kiểm tại chỗ ba điều kiện: định dạng email, độ dài mật khẩu tối thiểu
   8 ký tự, và hai ô mật khẩu khớp nhau.
4. Khách tích ô chấp thuận. **Chưa tích thì nút gửi không thực hiện được** và
   thông báo chặn hiện ra.
5. Hệ thống gửi `POST /api/v1/auth/register` kèm **danh sách cặp (loại, phiên
   bản)** mà khách đã chấp thuận.
6. Máy chủ tạo tài khoản, ghi các bản ghi chấp thuận **trong cùng giao dịch**, và
   ghi một mục kiểm toán.
7. Hệ thống gửi mã xác thực tới địa chỉ email vừa khai (UC103) và đưa người dùng
   sang màn hình xác minh liên hệ.

### Luồng luân phiên

1. **Đã có tài khoản:** khách bấm "Đăng nhập →" ở bước 2 và chuyển sang CN1.3.
2. **Có lời mời trong tay:** khách không dùng màn hình này mà mở liên kết mời —
   xem CN1.2. Hai đường **khác nhau về bản chất**: đường này tạo tài khoản chưa
   thuộc tổ chức nào; đường kia tạo tài khoản **đã** là thành viên một tổ chức.

### Luồng ngoại lệ

1. **Tên đăng nhập hoặc email đã tồn tại.** Máy chủ từ chối ở bước 6. Vì đây là
   biểu mẫu tạo tài khoản chứ không phải biểu mẫu đăng nhập, thông báo ở đây
   **được phép nói rõ** trường nào đã bị dùng — giấu thông tin ở màn hình này
   không mang lại lợi ích an ninh mà chỉ làm người dùng thử mù.
2. **Không chấp thuận văn bản pháp lý.** Ở bước 4, **tài khoản không được tạo**.
   Đây không phải một bước có thể hoãn lại: không có trạng thái "tài khoản đã tồn
   tại nhưng chưa chấp thuận gì" sinh ra từ đường này.
3. **Danh sách văn bản trống.** Nếu máy chủ chưa công bố văn bản nào, ô tích không
   có gì để liệt kê. Đây là trạng thái của một bản triển khai chưa cấu hình xong,
   và cách xử lý là quản trị nền tảng công bố văn bản (UC605) trước khi mở đăng ký.
4. **Mất kết nối khi gửi.** Dữ liệu trong biểu mẫu giữ nguyên trên màn hình; người
   dùng bấm gửi lại. Vì tài khoản chưa được tạo, không có trạng thái dở dang nào
   ở phía máy chủ.

### Ràng buộc

* **BR-3.1** đăng ký **luôn** kéo theo chấp thuận; không chấp thuận thì tài khoản
  không được tạo
* **BR-3.3** chấp thuận trỏ tới **cặp (loại, phiên bản)**
* **NFR-C2** mật khẩu lưu dạng **băm có muối**; không có đường đọc ngược
* Điểm cuối này nằm trong **danh sách ngoại lệ công khai** của cổng mặc-định-từ-chối
  — và danh sách đó phải được rà soát định kỳ, vì nó là chỗ duy nhất còn lại có
  thể sai (NFR-C1)

---

## CN1.2 — Đăng ký theo lời mời (UC102)

### Mục đích

Tạo một tài khoản **đã là thành viên của một tổ chức**, qua một đường mà **chính
người được mời phải hành động**. Đây là đường đưa người vào tổ chức duy nhất mà
quản trị tổ chức có.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/api/v1/tenants/invitations/{token}` | Đọc thông tin lời mời để hiển thị |
| `POST` | `/api/v1/auth/register` | Tạo tài khoản, **tiêu thụ** token mời |

### Giao diện 1 — Lời mời gia nhập (`/invitation`, `InvitationPage.tsx`, 232 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Khung trang xác thực | — | Tiêu đề **"Lời mời gia nhập"** |
| 2 | Nguồn token | từ URL | Đọc token từ **cả** phần băm (`#token=`) **và** phần truy vấn (`?token=`) |
| 3 | Thẻ thông tin tổ chức | — | **"Bạn được mời vào"** + tên tổ chức |
| 4 | Dòng thông tin | — | **"Lời mời phát cho"** + địa chỉ nhận |
| 5 | Dòng thông tin | — | **"Vai trong tổ chức"** |
| 6 | Dòng thông tin | — | **"Hết hạn"** |
| 7 | Cảnh báo ràng buộc địa chỉ | — | *"Lời mời này nêu đích danh địa chỉ ở trên. Bạn phải đăng ký bằng chính địa chỉ đó — đăng ký bằng email khác sẽ bị từ chối và lời mời vẫn còn nguyên."* |
| 8 | Cảnh báo đang đăng nhập | ẩn | *"Bạn đang đăng nhập bằng một tài khoản khác. Lời mời chỉ dùng được khi tạo tài khoản mới, nên hãy đăng xuất trước rồi mở lại liên kết này."* |
| 9 | Nút chính | — | **"Tạo tài khoản để gia nhập"** |
| 10 | Ô nhập token thủ công | rỗng | **"Mã lời mời"**, gợi ý "Dán mã tại đây" |
| 11 | Nút kiểm tra | — | **"Kiểm tra lời mời"**; khi chạy đổi thành "Đang kiểm tra…" |
| 12 | Liên kết chân trang | — | "Đã có tài khoản?" → "Đăng nhập →" |

**Thành phần số 2 đáng nói riêng:** token được đọc từ **hai vị trí** trong URL.
Lý do là một số máy khách thư điện tử cắt hoặc viết lại phần truy vấn; giữ thêm
đường đọc từ phần băm làm liên kết mời sống sót qua nhiều loại máy khách hơn.

**Thành phần số 8 là một quyết định thiết kế, không phải một thông báo lỗi
thường.** Lời mời **chỉ dùng được khi tạo tài khoản mới**. Cho phép một tài khoản
đang đăng nhập "nhận" lời mời sẽ mở đúng lối vòng mà BR-1.4 tồn tại để chặn.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `tenant_invitations` | | X *(đánh dấu đã tiêu thụ)* | | X |
| 2 | `users` | X | | | X |
| 3 | `role_assignments` | X | | | |
| 4 | `user_consents` | X | | | |
| 5 | `tenants` | | | | X |
| 6 | `audit_log` | X | | | |

### Tiến trình

1. Người được mời mở liên kết trong thư; hệ thống đọc token từ phần băm hoặc phần
   truy vấn của URL.
2. Hệ thống tra lời mời và hiển thị: tổ chức, địa chỉ nhận, vai dự kiến, hạn dùng.
3. Hệ thống cảnh báo rằng phải đăng ký **bằng chính địa chỉ nêu trên lời mời**.
4. Người dùng bấm "Tạo tài khoản để gia nhập" → chuyển sang biểu mẫu đăng ký với
   địa chỉ email **đã điền sẵn và gắn với lời mời**.
5. Người dùng đặt mật khẩu và chấp thuận văn bản pháp lý.
6. Máy chủ tạo tài khoản, **tiêu thụ** token mời, và tạo bản ghi gán vai ở cấp
   phạm vi tổ chức — tất cả trong cùng một giao dịch.
7. Người dùng vào hệ thống với tư cách thành viên tổ chức đó.

### Luồng luân phiên

1. **Nhận mã thay vì mở liên kết:** người dùng dán mã vào ô "Mã lời mời" và bấm
   "Kiểm tra lời mời". Luồng từ bước 2 trở đi không đổi.

### Luồng ngoại lệ

1. **Lời mời hết hạn hoặc đã dùng.** Ở bước 2, hệ thống hiển thị *"Lời mời không
   còn hiệu lực. Hãy đề nghị người mời gửi lại một liên kết mới."* Không có đường
   tự gia hạn — gia hạn là hành động của quản trị tổ chức, vì nếu người được mời
   tự gia hạn được thì hạn dùng không còn ý nghĩa.
2. **Đăng ký bằng email khác với địa chỉ trên lời mời.** Máy chủ **từ chối**, và
   **lời mời vẫn còn nguyên** — không bị tiêu thụ. Hành vi này được nói trước ở
   thành phần số 7 chứ không để người dùng phát hiện sau khi đã điền xong biểu mẫu.
3. **Đang đăng nhập bằng tài khoản khác.** Hệ thống hiển thị cảnh báo số 8 và
   **không** cho tiếp tục; đường xử lý là đăng xuất rồi mở lại liên kết.
4. **Token không đọc được từ URL.** Rơi về ô nhập thủ công (thành phần số 10) kèm
   hướng dẫn: *"Dán mã lời mời bạn nhận được, hoặc mở lại liên kết trong thư mời."*

### Ràng buộc

* **BR-1.4** quản trị tổ chức đưa người vào **chỉ bằng lời mời**
* **BR-1.5** chỉ quản trị nền tảng mới gán trực tiếp theo mã tài khoản
* **BR-3.1** vẫn áp: không chấp thuận văn bản thì tài khoản không được tạo
* Token mời lưu ở **dạng băm** trong `tenant_invitations` (BR-9.5)

---

## CN1.3 — Đăng nhập và xác thực hai bước (UC105, UC106)

### Mục đích

Cấp một phiên làm việc cho người dùng hợp lệ sao cho **mật khẩu bị lộ một mình
vẫn chưa đủ** để người khác vào thay, và biểu mẫu **không dùng được để dò xem tên
tài khoản nào đã tồn tại**.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Kiểm định danh và mật khẩu |
| `POST` | `/api/v1/auth/login/2fa` | Đổi vé trung gian + mã 6 chữ số lấy phiên thật |
| `GET` | `/api/v1/auth/me` | Lấy hồ sơ phiên hiện tại |
| `POST` | `/api/v1/auth/logout` | Thu hồi phiên |

**Hình dạng hồ sơ trả về (`UserOut`) — cập nhật 18/08/2026.** `UserOut` là một
**danh sách CHO PHÉP**, và nó là thứ duy nhất ngăn `password_hash` đi ra ngoài
(`auth._row_to_user` mang cột đó theo trên mọi hồ sơ, cố ý, vì
`authenticate_user` cần nó). Tám trường:

| Trường | Ý nghĩa |
|---|---|
| `id` · `username` · `email` | định danh |
| `is_active` | tài khoản còn hiệu lực |
| `is_admin` | quản trị **NỀN TẢNG** |
| `created_at` | mốc tạo |
| `tenant_id` | tổ chức nhà |
| `tenant_role` | vai **TRONG tổ chức**: `admin` · `editor` · `viewer` · `null` |

`tenant_role` được thêm ngày 18/08/2026 và nó sửa một lỗi **giao diện**: thanh
điều hướng chỉ đọc được `is_admin`, nên quản trị viên của một tổ chức — vốn
luôn có `is_admin = false` — **không nhìn thấy console tổ chức của chính mình**,
dù `require_tenant_admin` cho họ vào. Hai cờ này là hai thẩm quyền khác nhau,
không phải hai mức của một thẩm quyền.

Vai được tra **tại điểm cuối này**, không nhét vào `get_current_user`: mọi điểm
cuối đều đi qua phụ thuộc đó, nên thêm một truy vấn thành viên vào nó là trả giá
một lượt đọc bảng trên **từng** request để phục vụ đúng một màn hình.

### Giao diện 1 — Đăng nhập (`/login`, `LoginPage.tsx`, 263 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Khung trang xác thực | — | Tiêu đề **"Đăng nhập"** |
| 2 | Ô nhập văn bản | rỗng | **"Tên đăng nhập hoặc email"**, gợi ý "vd: minh123 hoặc minh@example.com" |
| 3 | Ô nhập mật khẩu | rỗng | **"Mật khẩu"** |
| 4 | Nút chuyển chế độ hiển thị | ẩn | **"Hiện"** / **"Ẩn"** |
| 5 | Liên kết | — | **"Quên mật khẩu?"** → `/forgot-password` |
| 6 | Nút gửi | — | **"Đăng nhập"**; khi chạy đổi thành "Đang đăng nhập..." |
| 7 | Liên kết chân trang | — | "Chưa có tài khoản?" → **"Tạo tài khoản →"** |
| 8 | Vùng thông báo lỗi | ẩn | **Một** thông báo chung: *"Không đăng nhập được. Hãy kiểm tra lại email và mật khẩu."* |
| 9 | Màn hình chờ | — | `LoadingScreen` — "Đang chuẩn bị giao diện…" |
| 10 | Nạp trước ngầm | — | Trang thu mẫu (`UploadPage`) được **nạp trước** ngay khi bấm đăng nhập, để người dùng không phải chờ tải gói mã sau khi vào |

### Giao diện 2 — Xác thực hai bước (cùng tệp, chế độ khác)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề | — | **"Xác thực hai bước"** |
| 2 | Ô nhập mã | rỗng | **"Mã xác thực"** — 6 chữ số |
| 3 | Nút xác nhận | — | **"Xác nhận"**; khi chạy đổi thành "Đang kiểm tra…" |
| 4 | Liên kết quay lại | — | **"← Quay lại đăng nhập"** |
| 5 | Vùng thông báo lỗi | ẩn | *"Mã không đúng hoặc đã hết hạn."* |

**Thành phần số 8 của Giao diện 1 là một yêu cầu bảo mật, không phải một lựa chọn
về trải nghiệm.** Sai tên tài khoản và sai mật khẩu trả **cùng một thông báo** và
**cùng một độ trễ**, nên biểu mẫu này không dùng được để dò xem tên nào đã có
người đăng ký.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `users` | | | | X |
| 2 | `refresh_tokens` | X | X *(xoay / thu hồi)* | | X |
| 3 | `user_totp` | | | | X |
| 4 | `user_recovery_codes` | | X *(đánh dấu đã dùng)* | | X |
| 5 | `user_consents` | | | | X |
| 6 | `tenants` | | | | X |
| 7 | `audit_log` | X | | | |
| 8 | Bộ đếm hạn mức trên Redis | X | X | X | X |

### Tiến trình

1. Hệ thống hiển thị biểu mẫu gồm hai trường.
2. Người dùng nhập và bấm "Đăng nhập".
3. Hệ thống xác định **địa chỉ IP thật** theo chuỗi máy chủ trung gian tin cậy,
   rồi kiểm **hai lớp hạn mức trước khi làm bất cứ việc gì tốn kém**: hạn mức theo
   cặp (định danh, IP), và hạn mức theo riêng IP.
4. Hệ thống tra tài khoản và so mật khẩu với mã băm đã lưu. **Phép băm cố ý chậm**,
   nên nó chỉ được chạy sau khi hai hạn mức ở bước 3 đã cho qua.
5. Hệ thống kiểm trạng thái tài khoản theo **bốn điều kiện**: đang hoạt động ·
   không bị khoá hành chính · đã chấp thuận đủ văn bản đang hiệu lực · tổ chức
   không ở trạng thái khoá cứng.
6. Hệ thống đặt lại bộ đếm thất bại, cấp một access token và một refresh token,
   ghi nhận phiên kèm thiết bị và địa chỉ, rồi ghi một mục kiểm toán.
7. Hệ thống đặt hai token vào **cookie mà mã trong trình duyệt không đọc được**,
   đúng đường dẫn gốc của bản triển khai, và đưa người dùng tới bảng điều khiển
   kèm các thông báo hành chính nếu có.

### Luồng luân phiên

1. **Tài khoản có bật xác thực hai bước:** ở bước 6, hệ thống **chưa** cấp phiên
   đầy đủ mà cấp một **vé trung gian ngắn hạn** và chuyển sang Giao diện 2. Phiên
   chỉ tồn tại sau khi yếu tố thứ hai được chấp nhận.
2. **Dùng mã khôi phục thay mã ứng dụng:** người dùng nhập một mã khôi phục vào
   ô "Mã xác thực"; mã đó bị đánh dấu đã dùng và không dùng lại được.
3. **Phiên hết hạn và được làm mới:** sau bước 7, refresh token **xoay ở mỗi lần
   dùng** và có một **cửa sổ ân hạn rất ngắn** cho lần xoay trước đó — để hai tab
   của cùng một người không đá nhau ra khỏi hệ thống.

### Luồng ngoại lệ

1. **Sai thông tin đăng nhập.** Ở bước 4, hệ thống trả **một** thông báo lỗi chung
   cho cả trường hợp không tồn tại tài khoản lẫn sai mật khẩu. Mỗi lần thất bại
   làm tăng bộ đếm của cặp (định danh, IP). Trong **mười lần thất bại đầu**, người
   dùng thử lại được ngay; từ lần kế tiếp, hệ thống áp thời gian chờ tăng dần theo
   bậc — **nửa phút · hai phút · năm phút · mười lăm phút** — và giữ ở bậc cuối cho
   tới hết cửa sổ một giờ. Cách chặn tăng dần này là chủ ý: người dùng thật gõ nhầm
   vài lần gần như không bị ảnh hưởng, còn một kịch bản dò tự động thì mất hàng giờ
   cho vài chục lần thử.
2. **Chạm trần theo địa chỉ IP.** Ở bước 3, nếu một IP vượt trần trong cửa sổ mười
   phút, hệ thống chặn cứng địa chỉ đó **mười phút** và từ chối mọi lượt đăng nhập
   từ đó, **kể cả của người dùng hợp lệ**. Trước khi chạm trần cứng, hai ngưỡng
   trung gian ghi cảnh báo vào nhật ký an ninh cùng với **số lượng định danh khác
   nhau đã được thử từ địa chỉ đó** — số liệu phân biệt một văn phòng đông người
   với một đợt dò tài khoản. Người bị vạ lây chờ hết cửa sổ hoặc đổi đường mạng.
3. **Tài khoản bị khoá hoặc tổ chức bị đình chỉ.** Ở bước 5, hệ thống từ chối và
   hiển thị **lý do quản trị viên đã ghi** kèm kênh liên hệ hỗ trợ, thay vì một
   thông báo sai mật khẩu chung chung. Ở bước này người dùng **đã chứng minh biết
   mật khẩu**, nên việc giấu lý do không mang lại lợi ích an ninh mà chỉ khiến họ
   thử lại vô ích.
4. **Còn văn bản pháp lý chưa chấp thuận.** Ở bước 5, hệ thống **vẫn cấp phiên**
   nhưng điều hướng tới màn hình chấp thuận và **chặn mọi thao tác ghi** cho tới
   khi chấp thuận xong. Cho đăng nhập rồi chặn ghi là lựa chọn có cân nhắc: chặn
   ngay từ cửa đăng nhập sẽ khiến người dùng không đọc được chính văn bản mà họ
   được yêu cầu chấp thuận, và cũng không lấy được dữ liệu của mình ra.
5. **Không xác định được thiết lập bảo mật của tài khoản.** Ở bước 5, nếu hệ thống
   không đọc được trạng thái xác thực hai bước — thường do cấu hình khoá mã hoá bị
   thiếu sau một lần triển khai — lượt đăng nhập bị **từ chối bằng một lỗi máy
   chủ** thay vì bỏ qua lớp bảo vệ thứ hai. Nguyên tắc: khi không đọc được trạng
   thái bảo mật, hệ thống **đóng chứ không mở**. Người dùng không có thao tác nào
   tự xử lý; kỹ sư vận hành khôi phục cấu hình.

### Kết quả mong đợi

Người dùng hợp lệ có một phiên làm việc gắn với thiết bị và địa chỉ của mình, một
mục kiểm toán được ghi, và bộ đếm chống dò của họ được đặt lại. Với tài khoản bật
hai yếu tố, **chưa có phiên nào tồn tại** cho tới khi bước xác thực thứ hai hoàn
tất. Mọi lượt thất bại đều tiêu một lượt trong ngân sách chống dò, và **không lượt
nào tiết lộ được tài khoản có tồn tại hay không**.

### Ràng buộc

* **NFR-C7** sai tên và sai mật khẩu trả cùng thông báo và cùng độ trễ
* **NFR-C6** hạn mức tính theo IP thật; tiêu đề do phía gọi đặt không ảnh hưởng
* **NFR-C4** TOTP kiểm bằng **vector thử của tiêu chuẩn**, không chỉ kiểm "đăng
  nhập được" — một cài đặt sai lệch múi giờ vẫn cho đăng nhập được với ứng dụng
  sinh mã cùng lỗi nhưng không tương thích với ứng dụng chuẩn
* **BR-3.2** chưa chấp thuận ⇒ đăng nhập được nhưng không ghi được gì
* Token đặt trong cookie **đúng đường dẫn cơ sở** `/voya` (RB-T3)

---

## CN1.4 — Khôi phục tài khoản (UC108)

### Mục đích

Cho người dùng quên mật khẩu tự đặt lại được, **gộp ba bước vào một cửa** thay vì
bắt họ đi qua ba màn hình rời rạc, mà không biến chính đường khôi phục thành một
lối vào cho người khác.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `POST` | `/api/v1/auth/recover/start` | Gửi mã sáu chữ số tới kênh đã xác minh |
| `POST` | `/api/v1/auth/recover/verify` | Đổi mã lấy một vé đặt lại mật khẩu |
| `POST` | `/api/v1/auth/recover/confirm` | Đặt mật khẩu mới bằng vé |
| `POST` | `/api/v1/auth/forgot-password` | Đường cũ: gửi liên kết đặt lại qua thư |
| `POST` | `/api/v1/auth/reset-password` | Đường cũ: đặt lại bằng token trong liên kết |

### Giao diện 1 — Quên mật khẩu, ba bước một cửa (`/forgot-password`, `ForgotPasswordPage.tsx`, 421 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Chỉ báo bước | bước 1 | **"Bước {n} / 3"** |
| 2 | Hướng dẫn bước 1 | — | *"Nhập tên đăng nhập hoặc email của tài khoản. Chúng tôi sẽ gửi một mã gồm sáu chữ số để bạn tự đặt lại mật khẩu."* |
| 3 | Ô nhập văn bản | rỗng | **"Tên đăng nhập hoặc email"**, gợi ý "vd: minh123 hoặc minh@example.com" |
| 4 | Nhóm nút chọn kênh | kênh mặc định | **"Nhận mã bằng"** — thư điện tử hoặc tin nhắn |
| 5 | Nút bước 1 | — | **"Tiếp tục"**; khi chạy: "Đang gửi mã…" |
| 6 | Nút sửa định danh | — | **"Đổi"** — quay lại bước 1 mà không mất trạng thái |
| 7 | Ô nhập mã | rỗng | Sáu chữ số; gợi ý dưới ô: *"Mã có hiệu lực trong ít phút. Nhập sai quá năm lần thì phải xin mã mới."* |
| 8 | Nút bước 2 | — | **"Xác nhận"**; khi chạy: "Đang kiểm tra…" |
| 9 | Nút gửi lại mã | khoá đếm ngược | **"Gửi lại mã"** / **"Chưa nhận được mã? Gửi lại sau {giây} giây"** |
| 10 | Ô nhập mật khẩu | rỗng | **"Mật khẩu mới"**, gợi ý "Tối thiểu 8 ký tự" |
| 11 | Ô nhập mật khẩu | rỗng | **"Xác nhận mật khẩu mới"**, gợi ý "Nhập lại mật khẩu mới" |
| 12 | Nút chuyển chế độ hiển thị | ẩn | **"Hiện"** / **"Ẩn"** |
| 13 | Nút bước 3 | — | **"Lưu mật khẩu mới"**; khi chạy: "Đang lưu…" |
| 14 | Màn hình kết quả | — | Tiêu đề **"Đã đặt lại mật khẩu"** + thông điệp nêu ở dưới |
| 15 | Nút sau khi xong | — | **"Đăng nhập lại"** |
| 16 | Liên kết chân trang | — | "Nhớ ra mật khẩu rồi?" → **"Quay lại đăng nhập →"** |

**Thông điệp ở thành phần số 14 là một phần của thiết kế bảo mật, không phải một
lời chúc mừng:** *"Mật khẩu đã được đặt lại. Mọi phiên đăng nhập cũ trên các thiết
bị khác đã bị thu hồi, **kể cả phiên của người có thể đã chiếm được tài khoản**."*
Nó nói rõ điều mà người dùng cần biết nhất ở thời điểm đó.

### Giao diện 2 — Đặt lại bằng liên kết trong thư (`/reset-password`, `ResetPasswordPage.tsx`, 153 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Nguồn token | từ tham số `?token=` | Không có token thì hiện thông báo số 2 |
| 2 | Thông báo thiếu token | — | *"Liên kết đặt lại mật khẩu bị thiếu hoặc không hợp lệ. Vui lòng yêu cầu một liên kết mới."* + nút **"Yêu cầu liên kết mới →"** |
| 3 | Ô nhập mật khẩu | rỗng | **"Mật khẩu mới"** |
| 4 | Ô nhập mật khẩu | rỗng | **"Xác nhận mật khẩu mới"** |
| 5 | Nút gửi | — | **"Đặt lại mật khẩu"**; khi chạy: "Đang đặt lại..." |
| 6 | Thông báo thành công | — | *"Mật khẩu đã được đặt lại thành công. Bạn có thể đăng nhập bằng mật khẩu mới ngay bây giờ."* + **"Đăng nhập →"** |

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `users` | | X *(mã băm mật khẩu)* | | X |
| 2 | `verification_codes` | X | X *(số lần thử)* | | X |
| 3 | `password_reset_tokens` | X | X *(`used_at`)* | | X |
| 4 | `refresh_tokens` | | X *(thu hồi **mọi** phiên)* | | X |
| 5 | `audit_log` | X | | | |
| 6 | Bộ đếm hạn mức trên Redis | X | X | | X |

### Tiến trình

1. Người dùng nhập định danh và chọn kênh nhận mã.
2. Hệ thống gửi mã sáu chữ số tới **kênh đã xác minh** của tài khoản đó.
3. Người dùng nhập mã. Hệ thống đổi mã lấy một **vé đặt lại ngắn hạn**; **mã bị
   tiêu ngay ở bước này**, không phải ở bước cuối.
4. Người dùng đặt mật khẩu mới hai lần.
5. Hệ thống đổi mật khẩu, **thu hồi mọi phiên đăng nhập của tài khoản trên mọi
   thiết bị**, và ghi kiểm toán.
6. Hệ thống hiển thị màn hình kết quả nêu rõ việc thu hồi đã xảy ra.

### Luồng luân phiên

1. **Đường liên kết trong thư (đường cũ, vẫn còn):** người dùng bấm liên kết trong
   thư và tới Giao diện 2. Token trong liên kết dùng một lần và có hạn.
2. **Đổi định danh giữa chừng:** bấm "Đổi" ở bước 3 để quay lại bước 1.
3. **Chưa nhận được mã:** bấm "Gửi lại mã" sau khi hết đếm ngược.

### Luồng ngoại lệ

1. **Nhập sai mã quá năm lần.** Mã hiện tại bị vô hiệu; người dùng phải xin mã
   mới. Điều này được nói trước ngay dưới ô nhập (thành phần số 7), không để người
   dùng phát hiện sau khi đã hết lượt.
2. **Mã hết hạn.** Thông báo: *"Mã xác minh không đúng hoặc đã hết hạn."* — **một
   thông báo chung** cho cả hai trường hợp, cùng lý do như ở màn hình đăng nhập.
3. **Định danh không tồn tại.** Hệ thống **không** nói ra điều đó. Đường này không
   được phép trở thành một biểu mẫu dò tài khoản.
4. **Liên kết đặt lại thiếu hoặc hỏng.** Giao diện 2 hiện thông báo số 2 và đưa
   người dùng về đường xin liên kết mới.
5. **Tài khoản không có kênh liên hệ đã xác minh.** Không có đường tự khôi phục;
   người dùng phải liên hệ quản trị viên. Đây chính là lý do màn hình xác minh
   liên hệ (CN1.5) nhấn mạnh *"Địa chỉ đã xác minh là đường khôi phục khi bạn quên
   mật khẩu."*

### Ràng buộc

* **NFR-C8** liên kết đặt lại **chỉ trỏ tới danh sách máy chủ được phép**; tiêu đề
  `Host` giả mạo không đổi được đích
* **NFR-C3** đổi mật khẩu kích hoạt mức thu hồi thứ hai: **mọi phiên** của tài khoản
* Ba bước verify/confirm dùng **chung một xô tần suất** — chi tiết này quan trọng
  khi chẩn đoán: chạm trần ở bước sau vẫn tính vào cùng ngân sách với bước trước
* **BR-9.5** mã và token lưu dạng băm

---

## CN1.5 — Xác minh địa chỉ liên hệ (UC103, UC104)

### Mục đích

Chứng minh người dùng **đang giữ** email và số điện thoại gắn với tài khoản, vì
địa chỉ đã xác minh chính là đường khôi phục khi họ quên mật khẩu.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/api/v1/auth/verification-status` | Trạng thái xác minh của hai kênh |
| `POST` | `/api/v1/auth/verify/send` | Gửi mã tới kênh chỉ định |
| `POST` | `/api/v1/auth/verify/confirm` | Xác nhận mã |

### Giao diện 1 — Xác minh liên hệ (`/verify`, `VerifyContactPage.tsx`, 428 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề trang | — | **"Xác minh liên hệ"** + *"Chứng minh bạn đang giữ email và số điện thoại gắn với tài khoản. Địa chỉ đã xác minh là đường khôi phục khi bạn quên mật khẩu."* |
| 2 | Đường dẫn phân cấp | — | "Trang chủ" → "Xác minh liên hệ" |
| 3 | Thẻ kênh email | — | **"Địa chỉ email"** + giá trị, hoặc **"(chưa có)"** |
| 4 | Huy hiệu trạng thái | — | **"Đã xác minh"** / **"Chưa xác minh"** |
| 5 | Nút gửi mã email | — | **"Gửi mã tới email này"**, hoặc **"Xác minh lại"** nếu đã xác minh |
| 6 | Thẻ kênh SMS | — | **"Số điện thoại"** + giá trị |
| 7 | Ô nhập số điện thoại | rỗng | Nhãn cho trình đọc màn hình: "Số điện thoại nhận mã" |
| 8 | Nút gửi mã SMS | — | **"Gửi mã qua tin nhắn"** |
| 9 | Thông báo kênh tắt | ẩn | *"Hệ thống chưa bật kênh tin nhắn. Bạn vẫn khôi phục tài khoản được bằng email đã xác minh."* |
| 10 | Bảng nhập mã | ẩn | **"Đã gửi mã tới"** + đích + ô **"Nhập mã sáu chữ số"** |
| 11 | Nút xác nhận | — | **"Xác nhận"**; khi chạy: "Đang xác minh…" |
| 12 | Nút gửi lại | khoá đếm ngược | **"Gửi lại mã"** / **"Gửi lại sau {n} giây"** |
| 13 | Nút huỷ | — | **"Huỷ"** |
| 14 | Màn hình chờ | — | "Đang tải trạng thái tài khoản…" |

**Thành phần số 9 là một thiết kế xuống cấp có kiểm soát:** kênh SMS có thể **chưa
được bật** trên một bản triển khai. Thay vì giấu nút đi hoặc để nó hỏng lặng lẽ,
giao diện nói rõ kênh nào không dùng được **và** đường thay thế còn lại là gì.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `verification_codes` | X | X *(số lần thử)* | | X |
| 2 | `users` | | X *(cờ đã xác minh)* | | X |
| 3 | `platform_settings` | | | | X *(kênh SMS có bật không)* |
| 4 | `audit_log` | X | | | |

### Tiến trình

1. Hệ thống đọc trạng thái xác minh của cả hai kênh.
2. Người dùng chọn kênh và bấm nút gửi mã tương ứng.
3. Hệ thống sinh mã sáu chữ số, lưu **dạng băm** kèm hạn dùng, và gửi qua kênh đó.
4. Người dùng nhập mã và bấm "Xác nhận".
5. Hệ thống đánh dấu kênh đó **đã xác minh** và ghi kiểm toán.

### Luồng ngoại lệ

1. **Mã sai hoặc hết hạn.** *"Mã xác minh không đúng hoặc đã hết hạn."*
2. **Không gửi được mã.** *"Không gửi được mã. Vui lòng thử lại."* Với kênh thư,
   nguyên nhân hay gặp nhất là cấu hình máy chủ thư sai — và kiểu hỏng đó **im
   lặng** ở phía máy chủ, nên thông báo ở giao diện là dấu hiệu duy nhất.
3. **Kênh tin nhắn chưa bật.** Hiện thành phần số 9; đường khôi phục còn lại là
   email.
4. **Không đọc được trạng thái tài khoản.** *"Không đọc được trạng thái xác minh
   của tài khoản."*

### Ràng buộc

* Mã lưu **dạng băm**, có hạn dùng và có bộ đếm số lần thử (BR-9.5)
* Hai kênh **độc lập**: xác minh email không tự làm số điện thoại thành đã xác minh

---

## CN1.6 — Quản lý hồ sơ cá nhân (UC110)

### Mục đích

Cho người dùng đổi tên đăng nhập và địa chỉ email của mình, **và nói rõ hệ quả lan
toả** của việc đổi tên — vì tên đăng nhập đã được chép vào dữ liệu tại thời điểm
ghi.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/api/v1/auth/me` | Đọc hồ sơ hiện tại |
| `PATCH` | `/api/v1/auth/me` | Đổi tên đăng nhập |
| `POST` | `/api/v1/auth/change-email/start` | Gửi mã tới địa chỉ **mới** |
| `POST` | `/api/v1/auth/change-email/confirm` | Xác nhận đổi email |

### Giao diện 1 — Tài khoản của tôi (`/settings/account`, `AccountPage.tsx`, 371 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề trang | — | **"Tài khoản của tôi"** — "Sửa tên đăng nhập và địa chỉ liên hệ của bạn." |
| 2 | Banner nhắc xác minh | ẩn | Liệt kê kênh còn thiếu + nút **"Xác minh ngay"** |
| 3 | Khối đổi tên | — | **"Tên đăng nhập"** |
| 4 | Ghi chú hệ quả | — | *"Tên này được chép vào từng mẫu bạn đã đóng góp ngay lúc ghi. Đổi tên ở đây sẽ cập nhật cả những bản sao đó, nên các mẫu cũ của bạn không mang tên cũ nữa."* |
| 5 | Ô nhập văn bản | tên hiện tại | Ràng buộc: *"Tên phải dài ít nhất 3 ký tự."* |
| 6 | Nút lưu | — | **"Lưu tên mới"** |
| 7 | Bảng kết quả lan toả | ẩn | **"Đã cập nhật tên ở những chỗ sau"** + danh sách chỗ đã đổi |
| 8 | Ghi chú kiểm toán | — | *"Nhật ký kiểm toán giữ nguyên tên cũ — đó là bằng chứng lịch sử về việc ai đã làm gì, và sửa nó theo tên mới là viết lại lịch sử."* |
| 9 | Khối đổi email | — | **"Địa chỉ email"** + *"Đây là địa chỉ nhận mã khôi phục khi bạn quên mật khẩu. Mã xác nhận sẽ được gửi tới địa chỉ MỚI, nên hãy chắc bạn đọc được hộp thư đó."* |
| 10 | Dòng hiện trạng | — | **"Đang dùng"**: <địa chỉ> |
| 11 | Ô nhập văn bản | rỗng | **"Địa chỉ email mới"** |
| 12 | Ô nhập mật khẩu | rỗng | **"Mật khẩu hiện tại"** |
| 13 | Nút gửi mã | — | **"Gửi mã tới địa chỉ mới"** |
| 14 | Ô nhập mã | rỗng | **"Mã 6 chữ số vừa gửi"** |
| 15 | Nút xác nhận | — | **"Xác nhận đổi email"** |
| 16 | Nút huỷ | — | **"Huỷ"** |

**Thành phần số 7 và số 8 đứng cạnh nhau là một quyết định về tính trung thực của
giao diện.** Bảng số 7 liệt kê **đúng những chỗ đã đổi**; ghi chú số 8 nêu **chỗ
cố ý không đổi** và lý do. Người dùng vì thế không phải đoán xem "đổi tên" đã lan
tới đâu.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `users` | | X | | X |
| 2 | `samples` | | X *(bản sao tên)* | | X |
| 3 | `dataset/samples.csv` | | X *(cột tên)* | | X |
| 4 | `verification_codes` | X | X | | X |
| 5 | `audit_log` | X | **không sửa `actor_label`** | | X |

### Tiến trình — đổi tên đăng nhập

1. Người dùng sửa ô tên và bấm "Lưu tên mới".
2. Hệ thống kiểm độ dài tối thiểu 3 ký tự và tính duy nhất.
3. Hệ thống cập nhật tên ở bảng tài khoản **và các bản sao đã chép** — gồm cả cột
   tên trong nguồn sự thật tệp.
4. Hệ thống hiển thị bảng liệt kê **đúng những chỗ đã cập nhật**.
5. `audit_log.actor_label` **giữ nguyên tên cũ**.

### Tiến trình — đổi địa chỉ email

1. Người dùng nhập địa chỉ mới **và mật khẩu hiện tại**.
2. Hệ thống gửi mã sáu chữ số **tới địa chỉ MỚI** — không phải tới địa chỉ cũ.
3. Người dùng nhập mã và bấm xác nhận.
4. Hệ thống đổi địa chỉ và đặt lại trạng thái xác minh tương ứng.

**Vì sao mã gửi tới địa chỉ mới:** mục tiêu của bước này là chứng minh người dùng
**đọc được hộp thư mới**. Gửi tới địa chỉ cũ chỉ chứng minh lại điều đã biết, và
sẽ để một địa chỉ mới gõ sai đi lọt.

### Luồng ngoại lệ

1. **Tên không thay đổi.** Hệ thống báo *"Tên không thay đổi."* và không ghi gì.
2. **Tên đã có người dùng.** *"Không đổi được tên tài khoản."*
3. **Mã đổi email sai hoặc hết hạn.** *"Mã không đúng hoặc đã hết hạn."*
4. **Không gửi được mã tới địa chỉ mới.** *"Không gửi được mã tới địa chỉ mới."* —
   thường vì địa chỉ gõ sai, và đây chính là trường hợp mà thiết kế "gửi tới địa
   chỉ mới" bắt được.

### Ràng buộc

* **BR-9.4** `audit_log.actor_label` là **bằng chứng lịch sử**, không cập nhật
  theo tên hiện tại
* Đổi email đòi **mật khẩu hiện tại** — một thao tác chiếm được tài khoản đang mở
  không được phép đổi luôn đường khôi phục

---

## CN1.7 — Bảo mật tài khoản: mật khẩu, hai bước, phiên (UC107, UC109)

### Mục đích

Gom ba việc cùng một mục tiêu vào một chỗ: đổi mật khẩu, bật/tắt lớp bảo vệ thứ
hai, và quản lý các phiên đang mở.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `POST` | `/api/v1/auth/change-password` | Đổi mật khẩu |
| `GET` | `/api/v1/2fa/status` | Trạng thái hai bước và số mã khôi phục còn lại |
| `POST` | `/api/v1/2fa/enroll` | Sinh khoá bí mật để nhập vào ứng dụng xác thực |
| `POST` | `/api/v1/2fa/confirm` | Xác nhận mã 6 chữ số, bật hai bước |
| `POST` | `/api/v1/2fa/disable` | Tắt hai bước (đòi mật khẩu) |
| `POST` | `/api/v1/2fa/recovery-codes` | Cấp lại mã khôi phục (đòi mật khẩu) |
| `POST` | `/api/v1/auth/logout` | Thu hồi phiên |

### Giao diện 1 — Bảo mật (`/settings/security`, `SecuritySettingsPage.tsx`, 233 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề | — | **"Bảo mật"** — "Đổi mật khẩu, xác minh địa chỉ liên hệ, và bật lớp bảo vệ thứ hai." |
| 2 | Khối đổi mật khẩu | — | **"Đổi mật khẩu"** |
| 3 | Ghi chú hệ quả | — | *"Cần mật khẩu hiện tại. Sau khi đổi, mọi thiết bị sẽ bị đăng xuất — kể cả thiết bị bạn đang dùng — nên bạn sẽ phải đăng nhập lại."* |
| 4 | Ô nhập mật khẩu | rỗng | **"Mật khẩu hiện tại"** |
| 5 | Ô nhập mật khẩu | rỗng | **"Mật khẩu mới"** |
| 6 | Ô nhập mật khẩu | rỗng | **"Nhập lại mật khẩu mới"** |
| 7 | Ô nhập mã | ẩn | **"Mã xác thực hai bước, hoặc mã khôi phục"** — chỉ hiện khi máy chủ báo tài khoản đang bật hai bước |
| 8 | Nút gửi | — | **"Đổi mật khẩu"** |
| 9 | Thông báo kiểm tại chỗ | ẩn | "Nhập mật khẩu hiện tại." / "Mật khẩu mới cần ít nhất 8 ký tự." / "Hai ô mật khẩu mới phải giống nhau." |
| 10 | Ghi chú lối thoát | — | *"Quên mật khẩu hiện tại? Hãy đăng xuất rồi dùng \"Quên mật khẩu\" ở màn hình đăng nhập. Nếu bạn cũng không mở được hộp thư, hãy liên hệ quản trị viên — họ mở lại được cửa mà không cần biết mật khẩu của bạn."* |

**Thành phần số 7 cài đặt theo lối "hỏi khi cần, không đoán trước".** Giao diện
**không** gọi trước điểm cuối trạng thái hai bước để quyết định có hiện ô này hay
không; nó hiện ô sau khi máy chủ báo cần. Đoán trước là thêm một lượt gọi và thêm
một chỗ để hai bên lệch nhau.

### Giao diện 2 — Xác thực hai bước (`TwoFactorSection.tsx`)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề khối | — | **"Xác thực hai bước"** |
| 2 | Huy hiệu trạng thái | — | **"Đang bật"** / **"Chưa bật"** |
| 3 | Ghi chú mục đích | — | *"Sau khi bật, mỗi lần đăng nhập bạn sẽ cần thêm mã 6 chữ số từ ứng dụng xác thực trên điện thoại. Mật khẩu bị lộ một mình sẽ không đủ để vào tài khoản."* |
| 4 | Nút bật | — | **"Bật xác thực hai bước"** |
| 5 | Hướng dẫn bước 1 | — | **"Bước 1 — Thêm tài khoản vào ứng dụng xác thực"** + *"Mở Google Authenticator, Microsoft Authenticator, Aegis hoặc tương đương, chọn "Nhập khoá thủ công" và dán chuỗi dưới đây."* |
| 6 | Chuỗi khoá bí mật | — | Hiển thị để chép tay vào ứng dụng |
| 7 | Hướng dẫn bước 2 | — | **"Bước 2 — Nhập mã 6 chữ số ứng dụng đang hiện"** |
| 8 | Nút xác nhận / huỷ | — | **"Xác nhận"** / **"Huỷ"** |
| 9 | Màn hình mã khôi phục | — | **"Lưu {n} mã này ở nơi an toàn ngay bây giờ"** + *"Đây là lần duy nhất chúng hiển thị. Mỗi mã dùng được một lần, và chúng là đường vào duy nhất nếu bạn mất điện thoại."* |
| 10 | Nút chép | — | **"Chép tất cả"** → **"Đã chép"** |
| 11 | Nút đóng | — | **"Tôi đã lưu xong"** |
| 12 | Khối mã khôi phục | — | **"Mã khôi phục"** + *"Còn {n} mã chưa dùng. Cấp lại sẽ huỷ toàn bộ mã cũ ngay lập tức."* |
| 13 | Ô nhập mật khẩu | rỗng | **"Mật khẩu hiện tại"** + *"Bắt buộc cho cả hai thao tác dưới đây. Nếu không, người mượn được máy đang mở của bạn sẽ gỡ được lớp bảo vệ này."* |
| 14 | Nút | — | **"Cấp lại mã khôi phục"** |
| 15 | Nút | — | **"Tắt xác thực hai bước"** |
| 16 | Hộp thoại xác nhận tắt | — | **"Xác nhận tắt"** / **"Giữ nguyên"** |

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `users` | | X *(mã băm mật khẩu)* | | X |
| 2 | `user_totp` | X | X | X *(khi tắt)* | X |
| 3 | `user_recovery_codes` | X | X *(`used_at`)* | X *(cấp lại)* | X |
| 4 | `refresh_tokens` | | X *(thu hồi)* | | X |
| 5 | `audit_log` | X | | | |

### Tiến trình — bật hai bước

1. Người dùng bấm "Bật xác thực hai bước".
2. Hệ thống sinh khoá bí mật và hiển thị để nhập vào ứng dụng xác thực.
3. Người dùng nhập mã 6 chữ số ứng dụng đang hiện và bấm "Xác nhận".
4. Hệ thống kiểm mã, bật hai bước, và **sinh bộ mã khôi phục**.
5. Hệ thống hiển thị bộ mã **một lần duy nhất** và bắt người dùng xác nhận đã lưu.

### Tiến trình — đổi mật khẩu

1. Người dùng nhập mật khẩu hiện tại, mật khẩu mới hai lần.
2. Nếu tài khoản bật hai bước, máy chủ trả tín hiệu cần yếu tố thứ hai → giao diện
   hiện ô số 7 kèm thông báo *"Tài khoản đang bật xác thực hai bước. Nhập mã 6 chữ
   số, hoặc một mã khôi phục."*
3. Hệ thống đổi mật khẩu và **thu hồi mọi phiên trên mọi thiết bị**, kể cả thiết
   bị đang thao tác.

### Luồng ngoại lệ

1. **Sai mật khẩu hiện tại.** *"Không đổi được mật khẩu."*
2. **Thiếu mã hai bước.** Giao diện hiện ô số 7 thay vì báo lỗi chung.
3. **Mất điện thoại và hết mã khôi phục.** Không có đường tự phục hồi; phải liên
   hệ quản trị viên — và ghi chú số 10 của Giao diện 1 nói trước điều đó.
4. **Cấp lại mã khôi phục.** Toàn bộ mã cũ **bị huỷ ngay lập tức**; cảnh báo này
   nằm ngay trong thành phần số 12, trước khi bấm.

### Ràng buộc

* **NFR-C3** ba mức thu hồi phiên: một phiên · mọi phiên của một tài khoản · thu
  hồi theo biện pháp quản trị. **Đừng lẫn ba mức này**
* **NFR-C4** TOTP + mã khôi phục dùng một lần, kiểm bằng vector thử tiêu chuẩn
* Mọi thao tác gỡ lớp bảo vệ (tắt hai bước, cấp lại mã khôi phục) **đòi mật khẩu
  hiện tại**
* **Khoảng trống đã biết:** đăng xuất thu hồi refresh token nhưng **không giết
  access token đang còn hạn**; và **chưa có phát hiện tái sử dụng** refresh token

---

## CN1.8 — Văn bản pháp lý và đồng thuận (UC111, UC112, UC113)

### Mục đích

Cho chủ thể dữ liệu **đọc lại đúng bản văn bản mình đã ký** và **thay đổi quyết
định**. Đây là chức năng phân biệt hệ thống này với một công cụ thu dữ liệu thông
thường: đồng thuận là một trạng thái **có phiên bản, rút được, và chi phối đường
phát hành dữ liệu**.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/api/v1/legal/documents` | Danh sách văn bản đang hiệu lực |
| `GET` | `/api/v1/legal/{kind}` | Siêu dữ liệu một văn bản (phiên bản, hiệu lực, mã băm) |
| `GET` | `/api/v1/legal/{kind}/content` | Thân văn bản |
| `GET` | `/api/v1/legal/me/consents` | Chấp thuận của chính người dùng |
| `POST` | `/api/v1/legal/{kind}/accept` | Ghi nhận đồng ý |
| `POST` | `/api/v1/legal/{kind}/withdraw` | Rút đồng ý |

### Giao diện 1 — Đọc văn bản pháp lý (`/legal/:kind`, `LegalDocumentPage.tsx`, 150 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề | theo loại văn bản | Rơi về "Văn bản pháp lý" nếu loại không nhận ra |
| 2 | Tham số phiên bản | bản hiệu lực | `?version=` — **mở được đúng bản đã ký**, không chỉ bản mới nhất |
| 3 | Thân văn bản | — | Kết xuất Markdown từ nội dung lưu trong CSDL |
| 4 | Dòng siêu dữ liệu | — | **"Phiên bản"** |
| 5 | Dòng siêu dữ liệu | — | **"Hiệu lực từ"** |
| 6 | Dòng siêu dữ liệu | — | **"Ngôn ngữ"** |
| 7 | Dòng siêu dữ liệu | — | **"Mã băm nội dung"** |
| 8 | Khối so sánh | ẩn | **"So với bản trước"** |
| 9 | Ghi chú | — | *"Nếu bạn cần bản văn này để hoàn tất một thủ tục, hãy liên hệ quản trị viên tổ chức."* |
| 10 | Thông báo không tìm thấy | ẩn | *"Không tìm thấy bản {version} của văn bản này."* / *"Hệ thống chưa công bố văn bản này."* |

**Thành phần số 7 — mã băm nội dung — không phải trang trí.** Nó là thứ cho phép
đối chiếu rằng bản đang đọc **đúng là** bản mà bản ghi chấp thuận trỏ tới. Không
có nó, "tôi đã đồng ý với bản 2" là một lời khẳng định không kiểm được.

### Giao diện 2 — Đồng thuận của tôi (`/settings/consents`, `ConsentsPage.tsx`)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề | — | **"Đồng thuận của tôi"** — *"Xem lại từng văn bản bạn đã ký, đọc lại đúng bản đã ký, và thay đổi quyết định."* |
| 2 | Tiêu đề khối | — | **"Chấp thuận của tôi"** |
| 3 | Danh sách văn bản | — | Mỗi mục: loại, phiên bản đã ký, thời điểm ký |
| 4 | Nhãn bắt buộc | — | **"· bắt buộc để dùng hệ thống"** |
| 5 | Dòng thời điểm | — | "… lúc {thời điểm}" |
| 6 | Cảnh báo cần ký lại | ẩn | *"Bản mới đã thay đổi phạm vi so với bản bạn ký, nên nó cần bạn đồng ý lại. **Chấp thuận cũ vẫn được giữ nguyên trong hồ sơ.**"* |
| 7 | Nhãn phiên bản hiện hành | — | **"(bản {v})"** |
| 8 | Nút | — | **"Ghi nhận đồng ý"** |
| 9 | Nút | — | **"Rút đồng ý"** |
| 10 | Thông báo không rút được | ẩn | *"Văn bản này bắt buộc để dùng hệ thống nên không rút riêng được. Nếu bạn muốn dừng hẳn, hãy yêu cầu xoá tài khoản."* |
| 11 | Hộp thoại xác nhận rút | ẩn | **"Rút đồng ý với {loại}?"** — nêu ba hệ quả: áp cho **"mọi mức"**, dữ liệu **"không bị xoá"**, và "Bạn có thể đồng ý lại bất cứ lúc nào ở chính trang này." |
| 12 | Nút trong hộp thoại | — | **"Xác nhận rút"** / **"Giữ nguyên"** |
| 13 | Trạng thái rỗng | — | *"Hệ thống chưa công bố văn bản nào, nên chưa có gì để bạn đồng ý."* |
| 14 | Thông báo kết quả | — | "Đã ghi nhận đồng ý với {loại}." / "Đã rút đồng ý với {loại}." |
| 15 | Thông báo lỗi | — | "Không ghi nhận được đồng ý của bạn." / "Không rút được đồng ý." |

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `legal_documents` | | | | X |
| 2 | `user_consents` | X | | | X |
| 3 | `signer_consents` | X | X *(`withdrawn_at`)* | | X |
| 4 | `legal_document_events` | | | | X |
| 5 | `audit_log` | X | | | |

### Tiến trình

1. Hệ thống liệt kê từng loại văn bản kèm **ba thông tin**: phiên bản người dùng
   đã ký (nếu có) · phiên bản đang hiệu lực · cờ *"bản mới có đổi phạm vi không"*.
2. Người dùng mở và đọc **đúng bản đã ký** — qua tham số `?version=`, không phải
   bản hiện hành.
3a. **Ghi nhận đồng ý:** tạo bản ghi chấp thuận trỏ tới cặp (loại, phiên bản).
3b. **Rút đồng ý:** hộp thoại nêu rõ ba hệ quả trước khi xác nhận; sau khi xác
    nhận, hệ thống đặt `withdrawn_at`.
4. Hệ thống ghi nhật ký kiểm toán.

### Luồng ngoại lệ

1. **Văn bản bắt buộc để dùng hệ thống.** Nút rút bị vô hiệu, kèm thành phần số 10
   nêu đường duy nhất còn lại là yêu cầu xoá tài khoản.
2. **Bản mới đổi phạm vi.** Hiện cảnh báo số 6. Điểm quan trọng trong câu chữ:
   **chấp thuận cũ vẫn được giữ nguyên trong hồ sơ** — nó không bị ghi đè, vì nó
   là bằng chứng về một trạng thái đã có thật trong quá khứ.
3. **Chưa công bố văn bản nào.** Trạng thái rỗng số 13.

### Ràng buộc

* **BR-3.3** chấp thuận trỏ tới **cặp (loại, phiên bản)**, không trỏ "bản hiện hành"
* **BR-3.4** văn bản đã công bố **bất biến ở tầng CSDL** bằng trigger — nếu nội
  dung sửa được dưới chân bản ghi chấp thuận thì bằng chứng biến thành lời khẳng
  định suông
* **BR-3.5** cờ riêng tách "sửa lỗi chính tả" khỏi "đổi phạm vi xử lý dữ liệu";
  chỉ loại thứ hai buộc chấp thuận lại
* **BR-3.9** giao diện **nói thẳng** rằng rút đồng thuận **không** xoá dữ liệu khỏi
  lưu trữ và **không** thu hồi giấy phép đã cấp — và **có kiểm thử ghim đúng câu
  chữ đó**, để một lần sửa giao diện về sau không biến một giới hạn thành lời hứa
* **BR-3.6** `user_consents` (tài khoản chấp thuận điều khoản) và `signer_consents`
  (chủ thể dữ liệu cho phép dùng dữ liệu) là **hai bảng khác nhau**; chỉ vế thứ
  hai chi phối đường phát hành

---

## CN1.9 — Dùng thử nhận dạng cho khách vãng lai (UC114)

### Mục đích

Cho khách chưa có tài khoản thử đường nhận dạng thời gian thực, trong một hạn mức
đủ để đánh giá nhưng không đủ để dùng thay cho tài khoản thật.

### Giao diện

Thành phần `TrialGate.tsx` bọc quanh màn hình `/realtime` (chi tiết màn hình này
ở tệp Nghiệp vụ 4).

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| 1 | Cổng dùng thử | Chặn hoặc cho qua tuỳ hạn mức còn lại |
| 2 | Chỉ báo hạn mức | Số phút còn lại trong ngày |
| 3 | Lời gọi tạo tài khoản | Khi hết hạn mức |

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | Bitmap phút dùng thử trên Redis | X | X | | X |
| 2 | `platform_settings` | | | | X |

### Ràng buộc

* Hạn mức **60 phút mỗi ngày**, đếm bằng **bitmap phút** trên Redis — mỗi phút có
  hoạt động bật một bit, nên chi phí lưu trữ cố định và không phụ thuộc số lượt gọi
* Khách vãng lai **không** tạo được mẫu; đường dùng thử chỉ đọc mô hình đang phục vụ

---

## Tổng kết ma trận chức năng ↔ use case của Nghiệp vụ 1

| Chức năng | Use case phủ | Màn hình chính |
|---|---|---|
| CN1.1 Đăng ký tài khoản | UC101 | `/register` |
| CN1.2 Đăng ký theo lời mời | UC102 | `/invitation` |
| CN1.3 Đăng nhập và hai bước | UC105, UC106, UC107 | `/login` |
| CN1.4 Khôi phục tài khoản | UC108 | `/forgot-password`, `/reset-password` |
| CN1.5 Xác minh liên hệ | UC103, UC104 | `/verify` |
| CN1.6 Quản lý hồ sơ | UC110 | `/settings/account` |
| CN1.7 Bảo mật tài khoản | UC107, UC109 | `/settings/security` |
| CN1.8 Văn bản và đồng thuận | UC111, UC112, UC113 | `/legal/:kind`, `/settings/consents` |
| CN1.9 Dùng thử nhận dạng | UC114 | `/realtime` (qua `TrialGate`) |

**Đủ 14 use case UC101–UC114.**
