# 5. Yêu cầu giao diện ngoài (External Interface Requirements)

---

## 5.1 Giao diện người dùng (User Interfaces)

Giao diện là **ứng dụng đơn trang** (React 19 + react-router 7), hơn 30 màn hình,
chạy dưới một `basename` cấu hình được (`/voya` trên máy chủ CTU, `/` khi chạy
cục bộ).

### 5.1.1 Ba khu vực theo quyền

| Khu vực | Tiền tố tuyến | Dành cho |
|---|---|---|
| Công khai | `/login`, `/register`, `/legal/*`, … | A1 Khách vãng lai |
| Người dùng và tổ chức | `/`, `/labels`, `/upload`, `/training`, `/settings/*` | A2–A7 |
| Console quản trị nền tảng | `/admin/*` | A8–A10 |

**Vỏ console quản trị không phải hàng rào quyền.** Việc một trang nằm dưới `/admin`
không tự nó chặn ai; quyền vẫn kiểm ở tầng dịch vụ. Nhầm hai thứ này là một lỗ
hổng kinh điển.

### 5.1.2 Danh mục màn hình

**Nhóm công khai / danh tính**

| Tuyến | Màn hình | Chức năng |
|---|---|---|
| `/login` | `LoginPage` | Đăng nhập (UC105), rẽ nhánh sang yếu tố thứ hai (UC106) |
| `/register` | `RegisterPage` | Đăng ký kèm chấp thuận văn bản pháp lý (UC101, UC112) |
| `/invitation` | `InvitationPage` | Đăng ký theo lời mời (UC102) |
| `/forgot-password` | `ForgotPasswordPage` | Khôi phục tài khoản — gộp ba bước một cửa (UC108) |
| `/reset-password` | `ResetPasswordPage` | Đặt lại mật khẩu bằng token dùng một lần |
| `/verify` | `VerifyContactPage` | Xác thực địa chỉ liên hệ, hai kênh (UC103, UC104) |
| `/legal/:kind` | `LegalDocumentPage` | Đọc văn bản pháp lý đang hiệu lực (UC111) |

**Nhóm dữ liệu**

| Tuyến | Màn hình | Chức năng |
|---|---|---|
| `/` | `DashboardPage` | Bảng điều khiển: tổng quan số mẫu, tác vụ, thông báo hành chính |
| `/upload` | `UploadPage` | **Trung tâm Thu thập Dữ liệu** — hai tab: *Ghi hình trực tiếp* (UC201) và *Tải video lên* (UC202) |
| `/labels` | `LabelsPage` | Duyệt danh mục lớp kèm số mẫu (UC206) |
| `/labels/:id` | `LabelDetailPage` | Chi tiết một lớp: phiên thu, chỉ số chất lượng, trình phát khung xương, thao tác quản trị (UC207, UC208) |
| `/trash` | `TrashPage` | Thùng rác, phạm vi theo người dùng (UC212) |
| `/training` | (thư mục `pages/training/`) | Xếp hàng, theo dõi và đánh giá tác vụ huấn luyện (UC401–UC406) |
| `/realtime` | `RealtimeRecognitionPage` | Nhận dạng thời gian thực; có `TrialGate` cho khách vãng lai (UC114) |
| `/notifications` | `NotificationsPage` | Thông báo trong ứng dụng |

**Nhóm cài đặt** (`/settings/*`, mỗi mục là một tuyến thật, không phải tab giả)

| Tuyến | Màn hình | Chức năng |
|---|---|---|
| `/settings/account` | `AccountPage` | Hồ sơ cá nhân (UC110) |
| `/settings/security` | `SecuritySettingsPage` | Mật khẩu, 2FA, mã khôi phục, danh sách phiên đang mở (UC107, UC109) |
| `/settings/consents` | `ConsentsPage` | **Ký và rút đồng thuận theo ba mức** (UC112, UC113) |
| `/settings/organization` | `OrganizationPage` | Thành viên, lời mời, vai (UC501–UC504) |
| `/settings/billing` | `BillingPage` | Gói cước, hạn mức, mức sử dụng (UC505, UC506) |
| `/settings/integrations` | `IntegrationsPage` | Khoá API và webhook (UC804–UC806) |
| `/settings/support` | `SupportPage` | Phiếu hỗ trợ của chính mình (UC801) |
| `/settings/language` | `LanguageSettingsPage` | Ngôn ngữ hiển thị |

**Nhóm console quản trị** (`/admin/*`)

| Tuyến | Màn hình | Chức năng |
|---|---|---|
| `/admin` | `AdminHomePage` | Tổng quan nền tảng |
| `/admin/users` | `AdminUsersPage` | Quản lý tài khoản, khoá/mở, chặn IP (UC601–UC603) |
| `/admin/tenants` | `AdminTenantsPage` | Quản lý tổ chức |
| `/admin/data` | `AdminDataPage` | Kho dữ liệu toàn nền tảng |
| `/admin/vocabulary` | `AdminVocabularyPage` | Danh mục từ vựng, phương ngữ, hồ sơ nhận dạng (UC301–UC310) |
| `/admin/legal` | `AdminLegalPage` | Soạn – công bố – thu hồi văn bản pháp lý (UC604–UC606) |
| `/admin/activity` | `AdminActivityPage` | Nhật ký kiểm toán |
| `/admin/sot` | `SotAdminPage` | Quản lý **máy ghi nguồn sự thật**: khoá được tin cậy, lược đồ, số dòng CSV (UC701–UC703) |
| `/admin/resources` | `AdminResourcesPage` | Tài nguyên máy chủ, tình trạng dịch vụ |
| `/admin/billing` | `AdminBillingPage` | Gói cước toàn nền tảng |
| `/admin/support` | `AdminSupportPage` | Hàng đợi phiếu hỗ trợ (UC802) |
| `/admin/trash` | `TrashPage` | Thùng rác phạm vi nền tảng |

### 5.1.3 Ba quy ước thiết kế giao diện

* **Bộ biểu tượng đồng nhất** — 70 biểu tượng vector, **không dùng emoji**. Emoji
  hiển thị khác nhau giữa các hệ điều hành và không đổi màu theo chủ đề.
* **Không có chuỗi cứng trong mã.** Mọi chuỗi hiển thị đi qua lớp i18n, và độ phủ
  được kiểm bằng công cụ trong cổng trước triển khai. **Bài học:** độ phủ này
  từng được báo cáo là 100 % **sai hai lần** — công cụ đo bỏ sót các chuỗi nằm
  trong biểu thức điều kiện (ternary) và trong chuỗi mẫu (template literal). Đã
  bổ sung hai luật đo và hai chỉ thị có biên (`i18n-ignore-next-line`,
  `@i18n-dynamic`).
* **Màu trạng thái thành công là xanh dương CTU**, theo hệ thiết kế của đơn vị.

### 5.1.4 Yêu cầu về khả năng tiếp cận

Cộng đồng mà dữ liệu mô tả **cũng chính là một nhóm người dùng** của hệ thống,
nên một giao diện giả định một phương thức giao tiếp duy nhất sẽ loại trừ chính
những người mà nền tảng phục vụ.

| Yêu cầu | Trạng thái |
|---|---|
| Không dùng âm thanh làm kênh thông tin duy nhất | ✓ — mọi phản hồi lúc thu mẫu là thị giác |
| Nhãn `aria-label` cho các nút chỉ có biểu tượng | ✓ — có mặt trong mã màn hình thu |
| Nội dung đa ngôn ngữ | ✓ |
| Tuyên bố đạt một mức conform WCAG cụ thể | ○ — **chưa**, vì chưa có kế hoạch kiểm thử và bằng chứng tương ứng |

---

## 5.2 Giao diện phần cứng (Hardware Interfaces)

| # | Thiết bị / giao diện | Yêu cầu và cách hệ thống dùng |
|---|---|---|
| 1 | **Webcam của máy khách** | Truy cập qua `getUserMedia` (WebRTC). Chiều rộng khung hình yêu cầu 1280. Đây là nguồn dữ liệu chính của hệ thống |
| 2 | **CPU của máy khách** | Chạy MediaPipe Hands biên dịch sang WebAssembly, tối thiểu 15 khung/giây. Không đạt thì cửa sổ 60 khung kéo dài quá 4 giây và trải nghiệm thu xuống cấp |
| 3 | **Micro của máy khách** | **Tuỳ chọn** — chỉ dùng cho nút nhập nhãn và tên người thực hiện bằng giọng nói (`SpeechInputButton`) |
| 4 | **GPU NVIDIA trên máy chủ** | Gắn vào hai dịch vụ `trainer` và `realtime_service` qua NVIDIA Container Toolkit. Không có GPU thì cả hai vẫn chạy trên CPU, chậm hơn nhiều |
| 5 | **Ổ đĩa của máy chủ** | Giữ kho tệp đặc trưng, kho thô, ảnh container (≈ 12 GB) và bản sao lưu. Ổ đĩa là ràng buộc thật — có kịch bản dọn ảnh không dùng vì lý do đó |

**Cách dò GPU đáng nói riêng:** kịch bản triển khai không hỏi *"có trình điều
khiển không"* mà hỏi **"một container có thật sự chiếm được GPU không"** — bộ công
cụ có thể vắng mặt, hoặc có mặt mà hỏng, và chỉ một lần yêu cầu thật mới phân
biệt được hai trường hợp. Khai báo GPU trên máy không có bộ công cụ sẽ làm dịch
vụ huấn luyện chết ngay lúc tạo container và kéo theo cả lượt triển khai.

**Không có thiết bị chuyên dụng nào khác.** Hệ thống không dùng găng tay cảm
biến, không dùng camera chiều sâu, không dùng thiết bị theo vết chuyển động. Đây
là quyết định phạm vi (RB-D6): chỉ dùng thông tin bàn tay trích từ ảnh RGB.

---

## 5.3 Giao diện phần mềm (Software Interfaces)

### 5.3.1 Giao diện trong hệ thống

| Giao diện | Mô tả |
|---|---|
| **Giao diện web ↔ API** | HTTP/JSON qua `nginx`. 214 điểm cuối HTTP gọi được trong 25 bộ định tuyến được mount (27 tệp; 2 tệp không mount). Đặc tả máy đọc được ở `/openapi.json` |
| **API ↔ cơ sở dữ liệu** | SQLAlchemy 1.4 tới PostgreSQL. Ngữ cảnh tổ chức đặt ở **đúng một khối** trong tầng truy cập dữ liệu, và **giới hạn trong phạm vi giao dịch** |
| **API ↔ hàng đợi** | Celery 5.3 trên Redis. Backend trả mã tác vụ trước khi công việc chạy xong |
| **Tiến trình nền ↔ kho tệp** | Ghi kho thô **trước**, ghi tệp đặc trưng `.npz` sau |
| **Giao diện web ↔ dịch vụ suy luận** | Kết nối dài qua `realtime_proxy`; mô hình đang phục vụ nạp sẵn trong bộ nhớ |

### 5.3.2 Giao diện với hệ thống ngoài

| Hệ thống ngoài | Giao thức / thư viện | Dùng để làm gì | Hỏng thì sao |
|---|---|---|---|
| **Google Drive** | REST qua `google-api-python-client` 2.196 | Lưu tệp đặc trưng, video thô, bản xem trước | Đường thu **vẫn chạy**; tác vụ đồng bộ vào hàng đợi thử lại |
| **Google Sheets** | REST cùng thư viện | Phản chiếu nguồn sự thật để đối soát bằng mắt | Chỉ mất đường đối soát phụ |
| **SMTP** | Giao thức SMTP, cấu hình theo máy chủ | Mã xác thực, lời mời, nhắc hạn, thư phiếu hỗ trợ, cảnh báo Grafana | **Im lặng không gửi được** — đây là kiểu hỏng nguy hiểm nhất trong nhóm này |
| **Cổng SMS** | HTTP API của nhà cung cấp | Kênh thứ hai cho mã xác thực | Rơi về kênh thư điện tử |
| **Prometheus** | Kéo chỉ số từ `/metrics` | Thu thập chỉ số | Mất quan trắc, không mất chức năng |
| **Grafana** | Giao diện web + contact point thư | Biểu đồ và **cảnh báo** | — |
| **Loki + Promtail** | Đẩy nhật ký | Kho nhật ký có cấu trúc | — |
| **Ứng dụng bên thứ ba** | REST + khoá API | Gọi API trong phạm vi của khoá | — |

**Ba chi tiết tích hợp đã trả giá để biết:**

* **Nội dung thư cảnh báo Grafana là văn bản thuần.** Đánh dấu định dạng bị
  chuyển thành ký tự thoát; thư vẫn gửi nhưng không đọc được.
* **Nhãn phân loại nhật ký phải ít.** Đặt định danh tổ chức làm nhãn sinh ra số
  chuỗi nhật ký bằng *số tổ chức × số dịch vụ*, và làm hệ thống nhật ký sập.
  Thông tin phân biệt phải nằm ở **siêu dữ liệu có cấu trúc**, không nằm ở nhãn.
* **Giá trị `-1` trong chỉ số nghĩa là "không đo được"**, khác hẳn `0` nghĩa là
  "đo được và bằng không". Không phân biệt hai giá trị này thì biểu đồ vẽ một
  đường bằng phẳng ở đáy và không ai biết hệ thống đang mù.

### 5.3.3 API cho bên thứ ba

| Hạng mục | Nội dung |
|---|---|
| Kiểu API | REST/JSON. **Không** có GraphQL |
| Xác thực | Khoá API lưu dạng **mã băm**; mất khoá thì tạo mới, không khôi phục |
| Phân quyền | Phạm vi gắn với khoá; khoá thuộc về một tổ chức |
| Đặc tả | OpenAPI sinh tự động tại `/openapi.json` |
| Sự kiện ra ngoài | Webhook có bí mật ký; lịch sử gửi lưu ở `webhook_deliveries` với mã trả về và số lần thử |
| Hộp thư đi | `event_outbox` — sự kiện ghi vào cùng giao dịch nghiệp vụ rồi mới gửi |

---

## 5.4 Giao diện truyền thông (Communications Interfaces)

### 5.4.1 Giao thức

| Chặng | Giao thức | Ghi chú |
|---|---|---|
| Trình duyệt ↔ `nginx` | **HTTPS** | Cổng vào duy nhất; một điểm phục vụ cho cả giao diện lẫn API nên không phải xử lý chính sách cùng nguồn |
| Trình duyệt ↔ dịch vụ suy luận | Kết nối dài qua proxy | Phục vụ nhận dạng thời gian thực |
| Backend ↔ PostgreSQL | Giao thức PostgreSQL trên mạng nội bộ container | Ngữ cảnh tổ chức đặt trong phạm vi giao dịch |
| Backend ↔ Redis | Giao thức Redis trên mạng nội bộ | Có thử lại khi mất kết nối trung gian |
| Backend ↔ dịch vụ ngoài | HTTPS | Google, SMTP, SMS |

**Không dùng MQTT, không dùng giao thức nhắn tin công nghiệp nào.** Quy mô một
máy chủ và mô hình dữ liệu theo lô không đòi hỏi chúng.

### 5.4.2 Phiên và token

| Hạng mục | Nội dung |
|---|---|
| Vận chuyển token | Cookie mà mã trong trình duyệt **không đọc được**, đúng đường dẫn cơ sở |
| Thời hạn phiên | 3 giờ |
| Token làm mới | **Xoay ở mỗi lần dùng**, kèm cửa sổ ân hạn rất ngắn cho lần xoay trước — để hai tab của cùng một người không đá nhau ra khỏi hệ thống |
| Ba mức thu hồi | Một phiên · mọi phiên của một tài khoản · thu hồi theo biện pháp quản trị |
| Giới hạn tần suất | Tính theo **địa chỉ IP thật** xác định qua chuỗi máy chủ trung gian tin cậy; tiêu đề do phía gọi đặt **không** ảnh hưởng tới bộ đếm |

**Hai khoảng trống đã biết trong vòng đời token:** chưa có phát hiện tái sử dụng
token làm mới; và đăng xuất thu hồi token làm mới nhưng **không giết access token
đang còn hạn**.

### 5.4.3 Thư điện tử

| Yêu cầu | Nội dung |
|---|---|
| Giao thức gửi | SMTP; máy chủ, cổng, tài khoản khai trong biến môi trường |
| Loại thư | Mã xác thực · lời mời vào tổ chức · đặt lại mật khẩu · nhắc hạn đăng ký · thư phiếu hỗ trợ · thư tồn đọng · cảnh báo hệ thống |
| Liên kết trong thư | Chỉ trỏ tới **danh sách máy chủ được phép** (`deploy/public_hosts.txt`); tiêu đề `Host` giả mạo không đổi được đích |
| Địa chỉ gốc | Lấy từ `FRONTEND_BASE_URL`, phải khớp chính xác địa chỉ người dùng gõ |

**Hai loại thư hỗ trợ khác nhau về bản chất, không được gộp:** thư "phiếu mới" là
**sự kiện** (gửi một lần khi phiếu được tạo); thư "tồn đọng" là **trạng thái**
(gửi khi hàng đợi quá 5 giờ hoặc quá 10 tin chưa trả lời).

### 5.4.4 Xử lý mất kết nối và đồng bộ

| Tình huống | Hành vi hệ thống |
|---|---|
| Mất mạng khi đang gửi mẫu | Cửa sổ đã thu **giữ lại trong trình duyệt**, cho thử gửi lại. Số lần thử tự động có trần; hết trần thì dừng và để người dùng quyết định, **không lặp vô hạn làm nóng thiết bị** |
| Người dùng đóng trang trước khi gửi được | Dữ liệu trong bộ nhớ trình duyệt mất — điều này **được nói rõ trên thông báo lỗi** |
| Kho ngoài không phản hồi | Tác vụ đồng bộ thử lại; đường thu không bị chặn |
| Trung gian truyền tin chớp tắt | Celery có thử lại ở mức broker + 3 lần thử ở mức dispatch |
| CSV và cơ sở dữ liệu lệch nhau | Tác vụ đối soát định kỳ theo chiều CSV → CSDL |

### 5.4.5 Khối lượng dữ liệu truyền

Quyết định trích đặc trưng tại trình duyệt định hình toàn bộ đặc tính truyền
thông của hệ thống:

| | Nếu gửi video thô | Cách hệ thống làm |
|---|---|---|
| Thứ đi qua mạng | Một tệp video vài MiB | Một mảng số vài chục KiB |
| Kích thước một mẫu sau chuẩn hoá | — | Trung vị **42,6 KiB**, p95 **82,8 KiB** (n = 3.871, đo 15/08/2026) |
| Hệ quả | Băng thông cao, kho lưu trữ lớn, có video thô để rò rỉ | Băng thông thấp, kho nhỏ, **không có video thô để rò rỉ** |

Bảng phản hồi của API cũng nhỏ: thân trả về của các điểm cuối đọc thường dùng nằm
trong khoảng 22 B – 4.499 B (đo 15/08/2026), nên chi phí truyền không phải yếu tố
chi phối độ trễ.
