# Bản Thiết Kế Kiến Trúc Tổng Thể Hệ Thống SignBridge (Master Blueprint)

Tài liệu này là bản thiết kế hệ thống toàn diện nhất, bao trùm toàn bộ từ luồng nghiệp vụ hiện tại, cấu trúc mã nguồn Frontend/Backend, cho đến định hướng mở rộng hệ thống thành một **Nền tảng MLOps Toàn Diện (End-to-End MLOps Platform)** hoạt động trên hạ tầng tự host (Self-hosted) tối ưu chi phí.

---

> [!IMPORTANT]  
> ## 0. Thiết Kế Các Luồng Nghiệp Vụ Cốt Lõi (Core Business Workflows)
> Dựa trên thiết kế cấu trúc Dữ liệu (`database_dictionary.md`), dưới đây là sự kết hợp giữa **Kiến trúc phần mềm** và **Luật Database** để xử lý hoàn hảo các luồng nghiệp vụ quan trọng nhất của SignBridge mà không làm hệ thống sụp đổ.

### 0.1. Luồng Thu Thập Trực Tiếp Từ Camera (Live Capture)
* **Bối cảnh:** User mở Webcam và thực hiện ghi hình trực tiếp trên Web. Cần quay 5 video cho 1 từ vựng.
* **Tư vấn Thiết kế & Tối ưu:**
  * **TUYỆT ĐỐI KHÔNG TÍNH CHECKSUM:** Vì đây là video quay trực tiếp (Live), nó mang tính "Độc nhất" (Unique). Việc bắt Frontend tính mã Checksum cho video Live là vô nghĩa và lãng phí CPU điện thoại. Bỏ qua bước Checksum ở luồng này.
  * **Cơ Chế Bắt Tay 3 Bước (3-Step Handshake):** 
    1. Frontend gọi API `Create Session` để mở 1 "Khung chứa" (Bảng `COLLECTION_SESSIONS` với `status='in_progress'`).
    2. Frontend gửi thẳng 5 video lên Cloud (MinIO/Google Drive).
    3. Frontend gọi API `Commit Session`. Backend lúc này mới chốt sổ, Insert 5 dòng vào `SAMPLES` và đổi status thành `completed`.
  * **Dọn Rác Tức Thì (Auto-Cleanup Video):** Ngay khi API báo tải lên thành công, Frontend lập tức gọi lệnh `URL.revokeObjectURL()` xóa sạch các file Video tạm (Blobs) khỏi RAM điện thoại.
  * **Xử lý rớt mạng:** Nếu User quay được 3 cái rồi tắt trình duyệt, Session sẽ kẹt ở `in_progress`. Mỗi đêm, Cronjob sẽ dọn rác các Session kẹt này mà không ảnh hưởng tới Database chính.
  * **Đồng bộ Google Sheets (Queue):** Không bắt User đợi đồng bộ. Backend sẽ ném lệnh sang Celery Worker để chạy ngầm update Sheets (Cập nhật bảng `SAMPLE_SYNC_STATUS`).

### 0.2. Luồng Tải File Bằng Tay (Batch Upload Workflow)
* **Bối cảnh:** User chọn 50 file Video từ Máy tính để tải lên cùng lúc.
* **Tư vấn Thiết kế & Tối ưu:**
  * **BẮT BUỘC TÍNH CHECKSUM TRƯỚC KHI TẢI (Client-Side Hashing):** Để chống gian lận (User nộp lại file cũ để cày điểm). Frontend phải chạy Web Worker băm file lấy mã SHA-256 rồi gửi mã lên Server hỏi trước. Nếu trùng, chặn không cho upload để tiết kiệm băng thông mạng.
  * **Tuyệt kỹ Khôi Phục Từ Thùng Rác (Zero-Upload Restoration):** Nếu mã Checksum Frontend gửi lên lại trùng với một Video đã bị xóa (nằm trong Thùng rác `deleted_at IS NOT NULL`), hệ thống sẽ **không báo lỗi**, mà ngầm đổi `deleted_at = NULL` để khôi phục video đó. Frontend báo "Tải thành công" nhưng thực chất là lôi từ thùng rác ra. Chống cày điểm tuyệt đối!
  * **Gom Nhóm (Grouping) & Bulk Insert:** Khi User nộp 50 file thuộc 3 Nhãn khác nhau. Backend `Service Layer` sẽ có nhiệm vụ Gom 50 file đó thành 3 Nhóm. Tạo ra 3 `COLLECTION_SESSIONS` tương ứng, và dùng **DUY NHẤT 1 LỆNH BULK INSERT** để ghi 50 dòng vào bảng `SAMPLES`. Tốc độ ghi DB tăng gấp 100 lần so với việc dùng vòng lặp FOR.

### 0.3. Luồng Quản Lý Thư Viện & Xung Đột Nhãn (Taxonomy Forking)
* **Bối cảnh:** Hệ thống có 10.000 Nhãn (Labels) thuộc nhiều Phương ngữ (Dialects). Xảy ra tình trạng User A và User B tranh cãi về cách ra dấu của từ "Xin chào".
* **Tư vấn Thiết kế & Tối ưu:**
  * **Áp dụng DDD (Domain-Driven Design):** Cấm lập trình viên chọc ngoáy trực tiếp lệnh `UPDATE CLASSES`. Mọi thao tác sửa Nhãn phải đi qua `TaxonomyForkingEngine`.
  * **Quy tắc Rẽ Nhánh (Forking):** Khi User B cố ý sửa tên/chi tiết của Nhãn "Xin chào" đã có Video, hệ thống sẽ tự động nhân bản (Fork) ra một Nhãn mới mang ID của User B. Các video quá khứ của User A vẫn nối với Nhãn gốc. Dữ liệu không bao giờ bị dẫm chân lên nhau.
  * **Soft Delete (Xóa mềm):** Ràng buộc Khóa ngoại (Foreign Key) `ON DELETE RESTRICT` được áp dụng. Admin bấm xóa 1 Nhãn, DB sẽ báo lỗi chặn lại nếu Nhãn đó đang chứa Video. Bắt buộc dùng `deleted_at` (Ẩn đi) thay vì xóa thật (DROP).

### 0.4. Luồng Nhận Diện Thời Gian Thực (Realtime Inference & Active Learning)
* **Bối cảnh:** Người dùng đưa tay ra trước Camera, AI nhận diện chữ và Server phải thu thập lại kết quả đó để làm giàu dữ liệu (Active Learning).
* **Tư vấn Thiết kế & Tối ưu:**
  * **Tách DB Đọc - Ghi (CQRS & Redis):** Cấu trúc 10.000 Nhãn phải được nén lại và ném lên RAM của **Redis Cache**. Khi User vào trang Nhận diện, Frontend kéo cái Cache này về trong 0.05 giây thay vì chọc vào PostgreSQL.
  * **RAM Buffer (Đệm bộ nhớ):** Khi User đang làm dấu, AI sinh ra 30 kết quả nhận diện mỗi giây. Tuyệt đối **KHÔNG** gọi API `INSERT INFERENCE_LOGS` liên tục. Frontend phải gom các kết quả này vào một mảng trong RAM (Buffer). Khi User bấm "Kết thúc", Frontend mới gom cả cục đó bắn 1 phát qua API để Backend lưu vào DB.

### 0.5. Luồng Quản Trị Tổ Chức & Không Gian Làm Việc (GitHub-like Workspace Model)
* **Bối cảnh:** Hệ thống không chỉ là công cụ thu thập đơn lẻ mà là một Nền tảng Đám mây MLOps giống như GitHub. Người dùng có thể tự lập tổ chức, làm việc nhóm độc lập.
* **Tư vấn Thiết kế & Tối ưu:**
  * **Cấu trúc Không Gian Làm Việc (Workspaces):** Bất kỳ người dùng (User) nào cũng có thể tự tạo `WORKSPACES` (giống như GitHub Organization). Bên trong Workspace chứa nhiều `PROJECTS` (giống GitHub Repositories).
  * **Phân Quyền Nhóm (RBAC trong Workspace):**
    * **Trưởng nhóm (Owner):** Có quyền thêm/xóa thành viên (`WORKSPACE_MEMBERS`), duyệt Video, cấp phát tài nguyên lưu trữ (Storage Quota), và khởi tạo tiến trình Train Model.
    * **Thành viên (Member/Contributor):** Có quyền vào các Project của nhóm để Live Capture hoặc Batch Upload dữ liệu.
  * **Cô lập Dữ liệu (Data Isolation):** Dữ liệu của Workspace A hoàn toàn vô hình với Workspace B (Ngoại trừ kho `CLASSES` dùng chung). Điều này cho phép nền tảng vận hành theo mô hình SaaS B2B (Cho thuê nền tảng MLOps cho các trường học/viện nghiên cứu khác).

### 0.6. Luồng Huấn Luyện AI Cá Nhân Hóa (Personalized MLOps Workflow)
* **Bối cảnh:** Một người khiếm thính muốn tự xây dựng một mô hình AI nhận diện bộ từ vựng chỉ dùng trong gia đình hoặc nhóm bạn thân của họ.
* **Tư vấn Thiết kế & Tối ưu:**
  * **Quyền năng End-to-End cho User thường:** User không chỉ đóng góp Data mà còn sử dụng nền tảng để tự Train AI. Họ tự tạo `PROJECT` cá nhân -> Tự tải video lên -> Tự duyệt video.
  * **Luồng Train Model (Pipeline):** 
    1. Người dùng vào màn hình Project, chọn tính năng **"Đóng băng Dữ liệu (Create Dataset Version)"**. Hệ thống sẽ snapshot toàn bộ Video hợp lệ thành `DATASETS` v1.0.
    2. Người dùng chọn **Kiến trúc Model** (Ví dụ: YOLOv8-Pose, LSTM, TimeSformer) do hệ thống cung cấp sẵn.
    3. Nhấn **"Start Training"**. Giao diện sẽ hiển thị thanh tiến trình (Progress Bar) thông qua WebSockets.
    4. Khi Server Train xong, tự động lưu kết quả vào bảng `MODELS`, cung cấp đường link tải File Trọng số (`.pt`, `.tflite`) cho người dùng.

### 0.7. Luồng Giám Sát Hệ Thống & Quản Trị Trung Tâm (Global Admin Workflow)
* **Bối cảnh:** Admin (Superuser) cần theo dõi sức khỏe của toàn bộ nền tảng, quản lý pháp lý và kiểm duyệt chất lượng. Admin mặc định được hưởng toàn bộ tính năng của User.
* **Tư vấn Thiết kế & Tối ưu:**
  * **Giám sát Sức khỏe (System Monitoring):** Admin truy cập trang `Dashboard Monitor` để xem biểu đồ thời gian thực về Dung lượng ổ cứng (MinIO), Số lượng request/giây (Traffic), và Tình trạng RAM/GPU của cụm K3s. (Tích hợp Grafana/Prometheus nhúng qua Iframe hoặc gọi API).
  * **Hệ thống Cảnh báo tự động (Alerting - Miễn phí 100%):** Không bắt Admin phải ngồi nhìn màn hình 24/24. 
    * **Với Zalo:** Để dùng Zalo miễn phí, hệ thống sẽ tạo một **Zalo Official Account (Zalo OA)**. Các Admin chỉ cần bấm "Quan tâm" (Follow) tài khoản OA này. Khi đó, Server gọi API Zalo OA nhắn tin cảnh báo cho Admin sẽ **hoàn toàn miễn phí**.
    * **Đề xuất thay thế (Telegram Bot):** Nếu Zalo OA sau này thắt chặt chính sách, hệ thống sẽ dùng **Telegram Bot API** (miễn phí vĩnh viễn, không giới hạn tin nhắn) để "bắn" cảnh báo RAM/Ổ cứng trực tiếp vào nhóm chat của các Admin.
  * **Kiểm Duyệt Thư Viện (Taxonomy & QA):** Admin sở hữu trang `Quản Lý Thư Viện Nhãn` để xét duyệt các Nhãn mới do cộng đồng đề xuất. Tiến hành Random Check (Kiểm tra ngẫu nhiên) các Video từ các Workspace công khai.
  * **Luồng Văn Bản Pháp Lý (Legal Management):** Admin có giao diện để soạn thảo, ban hành phiên bản mới của Privacy Policy hoặc ToS. Khi Admin ban hành bản mới vào bảng `LEGAL_DOCUMENTS` (status = active), toàn bộ User khi đăng nhập vào hệ thống sẽ bị chặn lại và yêu cầu tick chọn đồng ý (bảng `USER_CONSENTS`) trước khi được dùng tiếp.

### 0.8. Luồng Xác Thực & Khôi Phục Tài Khoản (Auth & Password Recovery Workflow)
* **Bối cảnh:** Người dùng quên mật khẩu, cần lấy lại tài khoản an toàn. Phải tối ưu chi phí (Ưu tiên dùng đồ miễn phí).
* **Tư vấn Thiết kế & Tối ưu:**
  * **Đăng Nhập Bằng Google (Google OAuth 2.0 - Miễn phí 100%):** Đây là giải pháp hoàn hảo nhất. Tích hợp nút "Đăng nhập bằng Google". Người dùng không cần nhớ mật khẩu, hệ thống không tốn tiền gửi mã SMS OTP để xác thực. Toàn bộ khâu xác thực danh tính do Google lo (Miễn phí vĩnh viễn).
  * **Mật Khẩu Truyền Thống & Khôi Phục:** Nếu người dùng tạo tài khoản bằng số điện thoại/Email thường:
    * **Khôi phục Email:** Gửi Link đặt lại mật khẩu qua hệ thống SMTP (Ví dụ: dùng Gmail SMTP hoặc SendGrid bản Free).
    * **Khôi phục bằng Zalo OA (Miễn phí):** Tương tự như cảnh báo Admin, nếu người dùng đã "Quan tâm" Zalo OA của SignBridge, hệ thống sẽ gửi tin nhắn chứa Link/Mã OTP khôi phục qua Zalo OA hoàn toàn miễn phí. (Tuyệt đối không dùng Zalo ZNS vì ZNS có thu phí).
  * **Chống Spam OTP:** Đặt Rate-Limit bằng Redis (Ví dụ: 1 tài khoản chỉ được yêu cầu gửi link OTP 3 lần trong 5 phút).

### 0.9. Luồng Hỗ Trợ Khách Hàng (Live Support & Helpdesk)
* **Bối cảnh:** Người dùng (người khiếm thính hoặc quản trị viên cấp dưới) gặp khó khăn trong việc tải video hoặc tạo dự án, cần hỗ trợ ngay lập tức.
* **Tư vấn Thiết kế & Tối ưu:**
  * **Bong bóng Chat (Live Chat Bubble):** Nhúng một nút "Hỗ trợ" ở góc dưới màn hình. Khi bấm vào, một hộp thoại chat hiện lên để kết nối trực tiếp với Admin.
  * **Giao tiếp qua WebSockets:** Luồng tin nhắn chat phải được truyền qua Socket để đạt tốc độ Real-time.
  * **Luân chuyển Ticket (Ticket Routing):** Khi User nhắn tin, tin nhắn sẽ được đẩy vào một hàng đợi (Queue) trong màn hình `Helpdesk Dashboard` của Admin. Bất kỳ Admin nào rảnh có thể bấm "Tiếp nhận" (Claim) để hỗ trợ. Nếu Admin Offline, hệ thống tự động ghi nhận thành dạng Ticket (Hộp thư) để Admin xử lý khi online lại.

---

> ## 1. Kiến Trúc Mở Rộng Frontend (Web-App / Single Page Application)
> 
> SignBridge không phải là một trang Web tĩnh đọc tin tức. Đây là một **Web-App (Ứng dụng Web)** đòi hỏi sự phản hồi tức thì (Real-time), xử lý Video nặng và chạy Trí Tuệ Nhân Tạo (Edge AI) ngay trên Trình duyệt. 

### 1.1. Tiêu Chuẩn Progressive Web App (PWA) - "Tải Xuống Như App Native"

Chính xác như hình ảnh bạn gửi (Nút biểu tượng màn hình có mũi tên tải xuống), đó là công nghệ **Progressive Web App (PWA)**. Đây là Tiêu chuẩn Vàng cho các Web-App hiện đại.

**A. Ý Nghĩa Của Nút Tải Xuống (Installability):**
* Bạn **KHÔNG** cần phải viết một dòng code Kotlin (Android) hay Swift (iOS) nào cả. Bạn cũng **KHÔNG** cần đưa App lên Google Play hay App Store (Đỡ tốn tiền và thời gian duyệt mệt mỏi).
* Chỉ với code React hiện tại, trình duyệt (Chrome/Safari) sẽ tự động hiện nút **"Cài đặt Ứng dụng" (Install App)** trên thanh địa chỉ.
* Khi người dùng bấm tải, Web-App sẽ được "cài" thẳng vào Laptop (thành một phần mềm Desktop) hoặc màn hình chính của Điện thoại (thành một Icon App). Khi bấm vào, nó chạy ẩn thanh địa chỉ của trình duyệt, mang lại cảm giác 100% giống App xịn (Native App).

**B. Yêu Cầu Kỹ Thuật (Cách Thiết Kế Trong React):**
Để trình duyệt cho phép hiện cái nút Tải xuống đó, Frontend bắt buộc phải thiết kế 3 thành phần cốt lõi:
1. **Web App Manifest (`manifest.json`):** Một file JSON cấu hình tên App (SignBridge), màu nền (Theme Color), và các Icon đủ mọi kích cỡ (192x192, 512x512) để hiển thị đẹp trên cả iPhone lẫn Windows.
2. **Service Workers:** Trái tim của PWA. Đây là một đoạn script chạy ngầm dưới trình duyệt. Nó có nhiệm vụ "Cache" (lưu nháp) toàn bộ giao diện HTML/CSS/JS. Nhờ nó, SignBridge sẽ **mở lên ngay lập tức trong 0.1 giây** ngay cả khi mạng yếu, thậm chí User có thể xài Offline tạm thời.
3. **Bảo mật HTTPS:** PWA bắt buộc phải chạy trên đường truyền mã hóa HTTPS (Sẽ được cấu hình ở máy chủ).

*Mẹo cho lập trình viên:* Trong hệ sinh thái React/Vite hiện tại, chúng ta sẽ thiết kế tính năng này bằng thư viện `vite-plugin-pwa` để tự động hóa toàn bộ quá trình tạo Service Worker.

---

### 1.2. Chiến Lược Responsive & Adaptive Design (Mobile-First)

Vì người dùng (người khiếm thính) sẽ sử dụng điện thoại để quay ngôn ngữ ký hiệu là chủ yếu, trong khi Quản trị viên (Admin) lại dùng Máy tính (PC) để kiểm duyệt, Frontend bắt buộc phải tuân thủ nghiêm ngặt nguyên tắc **Mobile-First**:

* **Giao diện Điện thoại (Mobile - Mặc định):** 
  * Áp dụng bố cục dọc (Portrait). Khai tử thanh Menu trên cùng (Header Navbar) và thay bằng Thanh điều hướng dưới đáy (Bottom Navigation Bar) tương tự Tiktok/Facebook để người dùng dễ dàng thao tác bằng ngón cái bằng 1 tay.
  * Màn hình Camera phải chiếm tối đa 80% không gian (Full-screen view) để họ nhìn rõ các cử chỉ tay của chính mình.
  * *Xử lý rủi ro xoay màn hình:* Phải có logic khóa hướng (Orientation Lock) hoặc xử lý phép chiếu toán học khi người dùng cố tình xoay ngang điện thoại, tránh việc tọa độ nhận diện AI của Mediapipe bị lật ngược.
* **Giao diện Máy tính/Máy tính bảng (Desktop/Tablet):** 
  * Áp dụng bố cục chia màn hình (Split-screen) hoặc Sidebar dọc bên trái. 
  * Ví dụ: Khi Admin duyệt video, màn hình sẽ chia làm 2 cột: Cột trái là Video Player bự, Cột phải là danh sách lịch sử để dễ dàng đối chiếu.
* **Công cụ cốt lõi:** Sử dụng các Breakpoints mặc định của **Tailwind CSS** (`sm:`, `md:`, `lg:`) để giao diện tự động bẻ khung hình mượt mà, hạn chế tuyệt đối việc viết mã CSS Media Queries thủ công rườm rà.

---

### 1.3. Thiết Kế Các Component Cốt Lõi (Core Components)

Dưới đây là chi tiết thiết kế các Component quan trọng nhất của SignBridge, áp dụng triệt để Mô hình Container-Presenter để tối ưu Render:

#### 1. Cụm Thu Thập AI Thời Gian Thực (Live Capture Module)
Yêu cầu: Chạy Mediapipe lấy 100 điểm tọa độ mỗi khung hình. Phải vẽ đè lên luồng Camera ở mức 30 FPS mà không làm đơ trang Web.
* **`LiveCameraContainer` (Smart):** Gọi hook `useMediapipe()`. Xin quyền Webcam. Bắn dữ liệu (Frames & Landmarks) vào bộ nhớ tạm.
* **`CanvasOverlay` (Dumb):** Nơi thực sự vẽ hình. **Quy tắc tử huyệt:** Không dùng các thẻ `<div>` để vẽ điểm (Sẽ gây DOM Reflow làm sập RAM). Phải truyền tọa độ vào thẻ `<canvas>` và dùng hàm `requestAnimationFrame` của WebGL/HTML5 để vẽ.
* **Tại sao tối ưu?** Chỉ có cái Canvas bị vẽ lại 30 lần/giây, còn các Nút bấm hay Giao diện xung quanh đứng im, tiết kiệm tối đa CPU.

#### 2. Cụm Quản Lý Thư Viện Nhãn (Taxonomy Library Module)
Yêu cầu: Backend trả về 1 Cây thư mục gồm 10,000 Từ vựng (Labels). Nếu in toàn bộ ra HTML, trình duyệt sẽ sập.
* **`TaxonomyVirtualTree` (Smart):** 
  * Áp dụng kỹ thuật **DOM Virtualization (Ảo hóa DOM)** qua thư viện như `react-window` hoặc `TanStack Virtual`. 
  * **Tại sao?** Dù có 10,000 Nhãn, nó chỉ render (vẽ) ra HTML đúng 20 Nhãn đang hiển thị trên màn hình người dùng. Kéo chuột tới đâu, vẽ tới đó.
* **`LabelCard` (Dumb):** Hiển thị thông tin 1 Nhãn. Component này bắt buộc phải được bọc trong `React.memo()`. 
  * **Tại sao?** Khi User xóa 1 Nhãn, chỉ cái Nhãn đó biến mất. `React.memo` giúp 9,999 Nhãn còn lại không bị render lại vô ích.

#### 3. Cụm Tải Lên Hàng Loạt (Batch Upload Module)
Yêu cầu: User kéo thả 50 file Video (Mỗi file 200MB). Trình duyệt phải băm file tính Checksum (SHA-256) trước khi Upload.
* **`BatchUploadDropzone` (Smart):** 
  * Nếu dùng Javascript chạy tính Checksum bằng luồng chính (Main Thread), trang web sẽ bị đóng băng (Đơ nút bấm, không cuộn chuột được) trong lúc tính.
  * **Giải pháp kiến trúc:** Áp dụng **Web Workers**. Tách logic tính Checksum ném sang 1 luồng chạy nền độc lập của Trình duyệt. Giao diện (UI Thread) vẫn mượt mà, có thể làm việc khác trong lúc chờ.

---

### 1.4. Chiến Lược Quản Lý Trạng Thái (State Management Strategy)

Trong một Web App, nếu lưu sai chỗ, dữ liệu sẽ bị rò rỉ (Memory Leak) hoặc mất đồng bộ.

1. **Dữ liệu bay hơi siêu nhanh (Siêu tốc):** Ví dụ: Tọa độ ngón tay (thay đổi mili-giây).
   * *Giải pháp:* Tuyệt đối không dùng `useState`. Dùng `useRef` để giữ giá trị (không gây re-render) và bơm thẳng vào `<canvas>`.
2. **Dữ liệu cục bộ (Local State):** Ví dụ: Trạng thái mở/đóng của một Modal, Ô input nhập Text.
   * *Giải pháp:* Dùng `useState` bên trong nội bộ Component đó.
3. **Dữ liệu hệ thống (Global UI State):** Ví dụ: Đang ở chế độ Dark Mode hay Light Mode, Sidebar đang mở hay đóng, Info của User đang đăng nhập.
   * *Giải pháp:* Dùng **Zustand** (Siêu nhẹ, không cồng kềnh và nhiều mã nồi như Redux).
4. **Dữ liệu từ Máy chủ (Server State):** Ví dụ: Danh sách Video vừa fetch từ API, Cây thư mục Nhãn.
   * *Giải pháp:* Dùng **TanStack Query (React Query)**. Công cụ này là trùm. Nó sẽ tự động Caching dữ liệu. Lần 1 tải danh sách mất 1 giây. Lần 2 user quay lại trang đó, nó lấy từ Cache ra trong 0.001 giây, không cần chọc Server (Giảm tải cho Backend).

---

### 1.5. Xử Lý API, Tách Khối & Phân Luồng Giao Tiếp (Advanced Standards)

Để Web-App thực sự đạt đẳng cấp doanh nghiệp, việc phân định rõ luồng giao tiếp API và thư viện UI là bắt buộc:

**A. Xử Lý API Chuyên Nghiệp (API Component Separation):**
* **Tuyệt đối cấm:** Viết trực tiếp `axios.get('/api/labels')` hay `fetch()` nằm trần trụi bên trong HTML Component. Nếu Backend đổi URL, bạn sẽ phải đi sửa từng Component một.
* **Giải pháp thiết kế:** Tách toàn bộ API ra một lớp độc lập nằm ở thư mục `shared/api/`. 
  * Tạo file `apiClient.ts` (cấu hình Header, gắn sẵn Token auth).
  * Viết các Hook chuyên dụng: `useFetchLabels()`, `useCreateSession()`.
  * Các Component UI chỉ việc gọi Hook. UI hoàn toàn "mù" (không biết) API lấy dữ liệu từ URL nào, đảm bảo tính tách biệt (Decoupling) tuyệt đối.

**B. Khi Nào Dùng WebSockets, Khi Nào Dùng REST API?**
Đừng lạm dụng Sockets. Chúng ta chia luồng rõ ràng như sau:
1. **Chỉ dùng HTTP/REST API (Không Socket):**
   * Cho các thao tác CRUD cơ bản nhanh gọn (như Lấy danh sách nhãn, Xóa Nhãn, Đăng nhập, Tạo Session mới). Trả kết quả liền trong dưới 1 giây.
2. **Bắt buộc dùng WebSockets (hoặc Server-Sent Events - SSE):**
   * Cho các thao tác **chạy nền lâu dài (Long-running tasks)**. Ví dụ: Khi User bấm nút *"Tải lên 50 video"*, Server có thể mất vài phút xử lý. Thay vì để Frontend bị treo, Frontend gửi request REST qua API rồi đi làm việc khác. Khi Server xử lý xong từng Video, Server bắn 1 gói tin qua **Socket** xuống Frontend để cập nhật thanh tiến trình (Progress Bar: 10%... 50%... 100%).
   * Các tính năng trong tương lai: *"Train Model AI"*, *"Xuất file Dataset ZIP"*. Đây đều là các tác vụ mất hàng giờ đồng hồ, bắt buộc phải dùng Sockets/SSE để nhận thông báo.

**C. Lựa Chọn Thư Viện UI Tốt Nhất (Kết Hợp TailwindCSS):**
Bạn muốn một bộ thư viện kết hợp với Tailwind vừa đẹp, dễ dùng, lại ít lỗi hiển thị (đặc biệt là trên Mobile)?
* **Khuyên dùng số 1: Shadcn UI** (hoặc Radix UI).
* **Lý do:** Khác với Ant Design hay MUI, Shadcn UI **không phải là một gói NPM cài vào máy**. Nó cho phép bạn copy-paste code gốc của cái Nút bấm, cái Modal vào thẳng dự án của bạn (nằm ở thư mục `shared/ui`). Nó dùng Tailwind 100%, nên nếu bạn không thích màu viền, bạn có thể sửa trực tiếp Class Tailwind trong đó. Nó được cộng đồng React suy tôn là thư viện ít lỗi nhất và dễ tùy biến nhất hiện tại.

**D. Cơ Chế Bắt Lỗi (Error Boundaries) & Tải Mã Lười (Lazy Loading):**
* Bọc các Component nguy hiểm (như luồng bật Camera) vào `ErrorBoundary` để nếu Mediapipe sập, chỉ cái khung Camera bị lỗi trắng, các nút bấm khác vẫn còn nguyên.
* Dùng `React.lazy()` để chỉ tải đoạn code quét điểm ảnh khi người dùng thực sự bấm vào chức năng đó, giúp trang chủ load trong nháy mắt.

### 1.6. Chiến Lược Phân Trang, Tải Lười & Đa Luồng (Performance)
* **Đa luồng (Multi-threading) với Web Workers:** Frontend SignBridge xử lý rất nhiều tác vụ nặng (Băm Checksum 50 file Video lớn, tiền xử lý hình ảnh AI). Nếu để chạy trên luồng chính (Main Thread), trang Web sẽ bị "đứng hình" (Freeze). **Giải pháp:** Tách toàn bộ các tính toán nặng nề này ném sang **Web Workers** để chúng chạy ngầm ở luồng riêng.
* **Phân trang vô tận (Infinite Scrolling):** Khi hiển thị danh sách 10.000 video của thư viện, tuyệt đối không dùng kiểu phân trang 1, 2, 3 truyền thống (rất khó bấm trên điện thoại). Sử dụng **Cursor-based Pagination** kết hợp `Intersection Observer` để tạo hiệu ứng "Cuộn vô tận" (Kéo xuống dưới cùng thì tự load thêm) giống hệt Tiktok.
* **Tải Trang với Skeleton Shimmer:** Khi lần đầu tải trang (ví dụ tải danh sách từ vựng/nhãn), sử dụng **Skeleton Screens với hiệu ứng lướt sóng ánh bạc (Shimmer effect)** giống hệt Facebook. Giao diện xám mờ chuyển động giúp màn hình không bị trống và giảm đáng kể cảm giác chờ đợi.

### 1.7. Nghệ Thuật UX, Trạng Thái Phản Hồi & Tối Ưu SEO
* **Trạng thái Chờ & Thông báo Trung tâm (Centered Status Modal):** Đối với các hành động thay đổi dữ liệu (**Chỉnh sửa, Upload, Xóa**), tuyệt đối không dùng Skeleton Screen hay Toast nhỏ góc màn hình. 
  * Áp dụng thiết kế **Pop-up hình chữ nhật bo góc nằm ngay giữa màn hình** (kèm hiệu ứng làm mờ nền Overlay). 
  * *Giai đoạn Đang xử lý:* Trọn vẹn bên trong Pop-up sẽ hiển thị một vòng xoay (Loading Spinner) kèm dòng chữ "Đang xử lý...".
  * *Giai đoạn Hoàn tất:* Vòng xoay sẽ chuyển đổi mượt mà thành **Biểu tượng Dấu Tích Xanh Lá (Success Indicator)** nằm bên trong ô chữ nhật, kèm thông báo "Thành công!". 
  * Pop-up có nút "X" để tắt thủ công, hoặc sẽ **tự động biến mất sau 2 giây**.
* **Hoạt ảnh Vi mô (Micro-interactions):** Nhấn nhá hiệu ứng tinh tế bằng `Framer Motion`. Khi Pop-up hiện ra, nó sẽ phình to nhẹ nhàng (Scale-up/Fade-in). Sự chuyển đổi từ Spinner sang Dấu Tích Xanh được vẽ ra sinh động, mang lại cảm giác phản hồi cực kỳ chắc chắn và chuyên nghiệp.
* **Tối Ưu Hóa Công Cụ Tìm Kiếm (SEO Best Practices):** Với các trang public như "Từ điển Ngôn ngữ ký hiệu cộng đồng":
  * Dùng `React Helmet` để nhúng tự động thẻ `<title>` và `<meta description>` cuốn hút cho từng trang từ vựng.
  * Tuân thủ Semantic HTML5: Dùng các thẻ `<article>`, `<section>`, và đảm bảo chỉ có duy nhất một thẻ `<h1>` trên mỗi trang chứa Keyword chính để Google Bot lập chỉ mục (Index) đứng Top 1.

### 1.7. Luồng Xác Thực (JWT Authentication Flow & Token Revocation)
Để đảm bảo an toàn tuyệt đối và trải nghiệm mượt mà, SignBridge sử dụng cơ chế bảo mật kết hợp giữa Memory và HttpOnly Cookie:
* **Access Token:** Được lưu trữ hoàn toàn trên RAM (Memory) của trình duyệt Frontend. Khi người dùng bấm F5 (Reload) hoặc mở một Tab mới, token này trong RAM sẽ lập tức bốc hơi, bảo vệ khỏi các lỗ hổng rò rỉ bộ nhớ.
* **Refresh Token:** Được Backend cấp và lưu thẳng vào trình duyệt dưới dạng `HttpOnly Secure Cookie`. Mã độc Javascript (XSS) hoàn toàn không thể đọc được cookie này.
* **Silent Refresh (Cấp lại ngầm):** Khi người dùng F5 làm mất Access Token ở RAM, App lúc khởi tạo sẽ gửi ngay một API `/refresh` ngầm (Silent). Trình duyệt tự động đính kèm Cookie chứa Refresh Token lên Server. Server trả về Access Token mới đưa lại vào RAM. Người dùng tiếp tục lướt web bình thường mà không bị văng ra ngoài đăng nhập lại. Khi chuyển route (SPA), RAM không đổi nên không tốn thêm request.
* **Chiến lược Thu hồi Token (Revocation):** Trong trường hợp người dùng đổi mật khẩu hoặc bấm "Đăng xuất khỏi thiết bị khác", hệ thống cần cơ chế thu hồi token ngay lập tức (dù token chưa hết hạn).
  * **Giải pháp:** Sử dụng kết hợp **Bảng `USER_SESSIONS`** trên Database và **Redis Denylist**. Khi thu hồi, Backend đánh dấu cờ `is_revoked = true` trong CSDL và đẩy `refresh_token_hash` vào Redis Denylist. Bất kì nỗ lực dùng token cũ nào để refresh đều bị Redis từ chối ngay trong vài mili-giây.

### 1.8. Bảo mật Dữ liệu (Workspace Security & Data Isolation)
Hệ thống áp dụng mô hình **Multi-Tenant (Đa người thuê)**, tức là nhiều nhóm nghiên cứu, nhiều doanh nghiệp có thể xài chung một hạ tầng DB nhưng dữ liệu hoàn toàn bị cô lập:
* **Tính riêng tư (Privacy):** Dữ liệu video, session thu thập của `WORKSPACE A` hoàn toàn vô hình đối với `WORKSPACE B`. 
* **Row-Level Security (RLS) hoặc Middleware:** 100% các API truy xuất dữ liệu bắt buộc phải kèm theo tham số `workspace_id` đã được xác thực qua JWT. Middleware chặn đứng các query đọc chéo.
* **Tính hiện diện (Visibility):** Các dữ liệu mang tính dùng chung (như bộ từ vựng `CLASSES` chuẩn quốc gia) sẽ có cờ `visibility = 'global'`. Trong khi đó, các dataset riêng của dự án sẽ mang cờ `visibility = 'private'`.

## 2. Kiến Trúc Mã Nguồn Backend (FastAPI Core)

FastAPI là "trái tim" xử lý logic của toàn bộ hệ thống. Trong các dự án quy mô nhỏ, lập trình viên thường mắc sai lầm là nhồi nhét toàn bộ code (từ kết nối SQL, xác thực Token, đến thuật toán tính toán AI) vào chung một hàm API (Router). Khối code này sẽ nhanh chóng biến thành một mớ bòng bong (Spaghetti code) không thể bảo trì, không thể test, và không ai dám sửa khi hệ thống phình to.

Để giải quyết triệt để, mã nguồn Backend SignBridge tuân thủ nghiêm ngặt chuẩn **Layered Architecture (Kiến trúc phân lớp rành mạch)**. Tương tự như quy trình sản xuất của một tập đoàn lớn, mã nguồn được chia thành các "Phòng ban" (Tầng/Layer) độc lập. Mỗi tầng chỉ làm đúng một nhiệm vụ duy nhất và chỉ được phép ra lệnh cho tầng liền kề ngay bên dưới nó. Kỷ luật thép: Tuyệt đối nghiêm cấm việc viết logic thuật toán hay lệnh gọi Database trực tiếp vào API Router.

### 2.1. Tổng Quan Về Các Tầng Phân Lớp (Layer Breakdown)
Hệ thống được chia làm 5 tầng cốt lõi, mô phỏng 5 phòng ban vận hành:
* **Tầng 1 - Routers (Lễ tân/Cổng giao tiếp):** Nơi duy nhất hứng chịu các đợt tấn công hoặc Request HTTP từ người dùng (Frontend). Tầng này hoàn toàn "mù" (Dumb Layer), nó không biết Database hình thù ra sao. Nó chỉ nhận dữ liệu, chuyển cho bộ phận bên trong xử lý, và trả kết quả cho khách hàng.
* **Tầng 2 - Schemas (Cửa an ninh/Kiểm duyệt):** Sử dụng sức mạnh của Pydantic. Trước khi "Lễ tân" nhận đơn, "Cửa an ninh" sẽ soi xét từng chữ. Gửi thiếu 1 tham số? Sai định dạng email? Cố tình chèn mã độc SQL Injection? Lập tức chặn đứng và ném lỗi 422 (Unprocessable Entity) ra ngoài.
* **Tầng 3 - Services (Phòng Nghiệp vụ/Não bộ):** Trái tim của hệ thống. Chứa toàn bộ chất xám, thuật toán tiền xử lý ảnh, logic kinh doanh cốt lõi (Ví dụ: Điều kiện kiểm tra đã đủ 5 video chưa). Nó nhận dữ liệu "sạch" từ Lễ tân, xử lý, rồi ra lệnh cho Kho.
* **Tầng 4 - Repositories (Thủ kho/Data Access):** Tầng duy nhất trong hệ thống được cầm "Chìa khóa" mở kho dữ liệu (PostgreSQL, Google Drive, MinIO). Thủ kho không quan tâm logic kinh doanh là gì, chỉ biết "Nhận lệnh SELECT thì lấy ra, nhận lệnh INSERT thì nhét vào". Thiết kế này giúp nếu sau này dự án bỏ PostgreSQL chuyển sang MongoDB, ta chỉ việc thay đúng ông Thủ kho, các phòng ban khác không hề hay biết và không bị ảnh hưởng.
* **Tầng 5 - Core & Workers (Hạ tầng & Vận chuyển):** Chứa các cấu hình bảo mật (Token, Password Hashing), kết nối DB, và các công nhân Celery chuyên bưng bê những tác vụ siêu nặng (như gửi email, đồng bộ ảnh) chạy ngầm ở chế độ nền.

### 2.2. Cấu Trúc Thư Mục Chuẩn (Directory Structure)
Mã nguồn trong thư mục gốc `backend/app/` được tổ chức lại theo 5 tầng cốt lõi:

```text
backend/app/
├── core/           # [Tầng Hệ Thống] Cấu hình config, bảo mật auth, logging, rate limiter.
├── routers/        # [Tầng Giao Tiếp HTTP] Đón Request từ Web, khai báo API đường dẫn.
├── services/       # [Tầng Nghiệp Vụ] Chứa não bộ, thuật toán, logic kiểm tra dữ liệu.
├── repositories/   # [Tầng Dữ Liệu] Chuyên chọc vào PostgreSQL, Google Drive, MinIO.
├── schemas/        # [Tầng Kiểm Duyệt] Định nghĩa Pydantic Models (In/Out) cho Swagger.
└── worker/         # [Tầng Tác Vụ Nền] Nơi chứa Celery Tasks chuyên xử lý việc nặng.
```

### 2.3. Quy Trình Giao Tiếp Chữ "U" & Tác Vụ Của Load Balancer
Khi một dữ liệu đi vào, nó phải tuân thủ luồng giao tiếp khép kín hình chữ "U":
1. **Load Balancer (Traefik):** Đứng ở cổng Server. Phân tích URL. Nếu URL có chữ `/api/v1/...`, nó ném ngay gói tin cho FastAPI. Nếu là file tĩnh, ném cho MinIO.
2. **Router (Tầng Giao Tiếp):** Tiếp nhận Request từ Traefik. Dùng `schemas` (Pydantic) kiểm tra tính hợp lệ (VD: Bắt lỗi thiếu Token, sai định dạng). Nếu đúng, nó triệu hồi tầng Service. *Router không bao giờ biết Database trông như thế nào.*
3. **Service (Tầng Nghiệp Vụ):** Nhận lệnh từ Router. Chạy logic nghiệp vụ (Kiểm tra quyền User, thuật toán xử lý File). Nếu là tác vụ nhẹ, nó gọi tầng Repository. Nếu là tác vụ siêu nặng (Băm file 1GB, gửi Zalo), Service ném lệnh cho **Celery (Worker)** chạy ngầm và trả ngay kết quả "Đang xử lý" cho Router.
4. **Repository (Tầng Dữ Liệu):** Nhận lệnh từ Service. Trực tiếp thực thi SQL INSERT vào PostgreSQL, hoặc đẩy API lên Google Drive. Lấy kết quả thô đẩy ngược lên Service.
5. **Trả về (Response):** Service báo xong, Router đóng gói JSON và ném lại cho Traefik đẩy về điện thoại người dùng.

### 2.4. Phân Chia Công Việc Chuyên Môn (Team Workflow)
Nhờ kiến trúc 5 tầng này, Team Dev có thể code song song mà không sợ đụng độ (Merge Conflict):
* **Dev 1 (Dữ liệu/Kho):** Chỉ mở thư mục `repositories/` viết các hàm lưu Google Drive, tối ưu SQL. Không cần bận tâm API tên là gì.
* **Dev 2 (Thuật toán):** Mở thư mục `services/` viết code phân tích ảnh, tiền xử lý.
* **Dev 3 (API & Swagger):** Mở `schemas/` định nghĩa cục dữ liệu, gắn vào `routers/` để sinh tài liệu API tự động cho Frontend làm việc.

### 2.5. Giao Tiếp Giữa Các Component & External Services
* **Trong nội bộ:** Các Services không được gọi API HTTP của nhau (tránh overhead mạng). Chúng triệu hồi trực tiếp các `Class Methods` (Ví dụ: `UploadService` có quyền gọi thẳng `AuthService.verify()`).
* **Với bên ngoài (External Services):** Khi Backend cần giao tiếp với MLOps (Prefect) hoặc Zalo API, `Services` không bao giờ chờ đợi kết quả. Nó luôn đẩy Message (Thông điệp) vào **Redis Queue**, để Celery Worker từ từ giao tiếp với Zalo. Thiết kế này đảm bảo: Nếu server Zalo bị sập, Backend của ta vẫn sống khỏe re.

### 2.6. Chiến Lược Xử Lý Đồng Thời & Threadpool (Concurrency & AsyncIO)
* **Vấn đề "Phản hồi có chậm không?":** Tuyệt đối không. FastAPI hoạt động dựa trên cơ chế Bất đồng bộ (AsyncIO). Khi có hàng ngàn người dùng đẩy Request lên cùng lúc, luồng sự kiện chính (Main Event Loop) của FastAPI sẽ không bao giờ bị khóa (Blocking).
* **Quản trị Threadpool:** 
  * Các tác vụ I/O (Chờ lưu dữ liệu vào ổ cứng, chờ phản hồi từ Google Drive) sẽ tận dụng triệt để lệnh `await` để giải phóng luồng chính.
  * Các tác vụ nặng về CPU (Tính checksum SHA-256, nén ảnh, xử lý dữ liệu AI) tuyệt đối KHÔNG được phép chạy trực tiếp trên Event Loop. Chúng sẽ được ném vào Threadpool ảo (`run_in_threadpool` của Starlette), hoặc chuyển hẳn sang **Celery Worker** xử lý riêng rẽ, đảm bảo API luôn trả về HTTP 200 OK cho Frontend trong chưa tới 100 mili-giây.

### 2.7. Bảo Mật, Validation & Tiêu Chuẩn HTTP (Security & Protocols)
* **Tiêu chuẩn Giao thức (HTTP/2 & HTTPS):** Hệ thống đoạn tuyệt với HTTP/1.1 cổ điển. Cổng Load Balancer (Traefik) sẽ tự động kích hoạt **HTTP/2** (cho phép gộp hàng loạt Request trên cùng 1 kết nối TCP giúp load tài nguyên cực nhanh) và mã hóa toàn bộ dữ liệu bằng chuẩn cao nhất **HTTPS (TLS 1.3)**.
* **Xác thực Input (Input Validation):** Nguyên tắc bảo mật số 1: Không bao giờ tin tưởng dữ liệu Frontend gửi lên. Mọi dữ liệu (Dung lượng file, định dạng video, text nhãn) đi vào Router đều đụng phải khiên bảo vệ **Pydantic**. Nếu một trường dữ liệu bị thiếu hoặc sai kiểu chữ, FastAPI lập tức chặn đứng và ném lỗi 422 (Unprocessable Entity) trước khi code kịp chạm vào tầng Service.
* **Xác thực Danh tính (Authentication):** Sử dụng chuẩn **JWT (JSON Web Tokens)**. Access Token sống trong 15 phút (giảm thiểu rủi ro bị hacker đánh cắp), Refresh Token duy trì đăng nhập được lưu an toàn tuyệt đối dưới dạng HttpOnly Cookie để chống chèn mã độc (XSS).
### 2.8. Luồng Xử Lý Nghiệp Vụ Cốt Lõi (Core Backend Workflow)
Để hình dung rõ nhất cách 5 tầng trên phối hợp với nhau, đây là Kịch bản (Workflow) của tác vụ quan trọng nhất: **Người dùng Upload Video Ký hiệu**.
* **Bước 1 (Pre-flight Hash Check):** Người dùng bấm "Lưu Video". Frontend TỰ ĐỘNG băm file lấy mã SHA-256 và ném lên API `/api/v1/samples/check-hash`. Nếu mã trùng, Backend chặn ngay và báo lỗi (tiết kiệm 100% băng thông tải). Nếu mã chưa tồn tại, Frontend mới bắt đầu Upload thật sự.
* **Bước 2 (Router + Schema):** FastAPI tiếp nhận file. `AuthDependency` dịch ngược JWT. `UploadSchema` soi định dạng (`.webm`/`.mp4`) và dung lượng.
* **Bước 3 (Service Tức thì):** `UploadService` nhận file. Do đã kiểm tra mã băm ở Bước 1, Service lập tức cấp một `sample_uid` mới và gán file này vào phiên làm việc (Session).
* **Bước 4 (Trả kết quả Sớm):** Thay vì chờ Upload lên Google Drive, `UploadService` ném file sang cho Celery Worker chạy ngầm. Lập tức Router trả về HTTP 202 (Accepted). Frontend lập tức hiển thị Vòng xoay Loading.
* **Bước 5 (Worker & Repo Chạy Ngầm):** Celery ở chế độ nền gọi `GdriveRepo` đẩy file lên Google Drive. Thành công lấy được đường Link tải. Celery tiếp tục gọi `DatabaseRepo` để chèn đường link đó và mã SHA-256 vào bảng `SAMPLES`.
* **Bước 6 (Realtime Notify):** Xong xuôi, Celery bắn một gói tin qua WebSocket ngược về Frontend. Vòng xoay loading trên màn hình lập tức biến thành Dấu Tích Xanh "Thành công!".

### 2.9. Chiến Lược Xử Lý Lỗi Tập Trung & Ghi Nhật Ký (Global Exception & Logging)
* **Thông báo Lỗi Đơn Giản (User-Friendly Response):** Nguyên tắc tối thượng là **không bao giờ trả về lỗi thô (Raw Error/Stack Trace)** cho Frontend. Hệ thống sử dụng cơ chế **Global Exception Handler** tại tầng `core/`. Bất kể bên trong sập Database hay rớt mạng, Handler này sẽ "chụp" lấy lỗi, chặn mọi thông tin kỹ thuật, và ép kiểu trả về một đoạn JSON cực kỳ đơn giản: `{"error": true, "message": "Đường truyền đang gián đoạn, vui lòng thử lại!"}`. Nhờ vậy, Frontend chỉ việc bê nguyên câu `message` này in ra màn hình cho người dùng đọc mà không cần phải if/else phức tạp.
* **Ghi Log (Logging):** Để Dev sửa lỗi, thay vì in ra màn hình, hệ thống dùng thư viện `Loguru`. Mọi Request được gán `Request-ID`. Lỗi thực sự (như rớt DB dòng 50) sẽ được ghi âm thầm vào File Log kèm Request-ID, người dùng tuyệt đối không hay biết.

### 2.10. Quản Trị Kết Nối Cơ Sở Dữ Liệu (Connection Pooling)
* **Vấn đề:** Nếu 1000 người dùng truy cập cùng lúc, việc mở 1000 kết nối tới PostgreSQL sẽ làm sập Database (Too many clients).
* **Giải pháp:** Tầng `core/` cấu hình SQLAlchemy sử dụng **Connection Pool** (Ví dụ: Giới hạn chỉ có 20 kết nối chạy luân phiên). Mọi Request từ Router đều sử dụng cơ chế **Dependency Injection** (`yield db`). Khi Request đến, nó mượn 1 kết nối từ Pool, thao tác xong nó tự động nhả kết nối ra ngay lập tức để thằng khác xài. Cực kỳ an toàn và tối ưu bộ nhớ.

---

## 3. Kiến Trúc Cấu Trúc Dữ Liệu (Database Schema)

Hệ thống sử dụng **PostgreSQL** làm cơ sở dữ liệu lõi. Kiến trúc Table được thiết kế để tối ưu hóa truy vấn phân cấp và giải quyết triệt để rủi ro tràn ổ cứng.

### 3.1. Phân Trạch Dữ Liệu Rõ Ràng (Tách Ảnh/Video khỏi Database)
* **Vấn đề "Chỗ nào chứa ảnh/video?":** PostgreSQL sinh ra không phải để chứa file nặng. Tuyệt đối **không lưu Video/Ảnh dưới dạng mã hóa Base64 hay ByteA** trực tiếp vào Table.
* **Giải pháp:** Database SQL chỉ lưu trữ đường dẫn. Còn file gốc sẽ nằm ở `Google Drive` hoặc `MinIO`.

### 3.2. Giải Thích Sự Tương Thích Giữa Database & Kiến Trúc
Dưới đây là 4 cụm bảng cốt lõi quyết định sự sống còn của hệ thống, được thiết kế bám sát tuyệt đối vào Kiến trúc 5 Tầng:

1. **Cụm USERS / WORKSPACES (Quản trị Danh tính & Chống sập GDPR):** 
   * Bảng `USERS` áp dụng cơ chế **Soft Delete** (Xóa mềm bằng `deleted_at`) để tuân thủ luật bảo mật GDPR. Khi người dùng đòi xóa tài khoản, các trường nhạy cảm (Email, Mật khẩu) sẽ bị Null hóa. Tuy nhiên, ID ẩn của họ vẫn được giữ nguyên để không làm đứt gãy Khóa ngoại (CASCADE) kéo theo sự hủy diệt của hàng ngàn Video AI họ đã đóng góp.

2. **Cụm TAXONOMIES (Hệ sinh thái Từ vựng 3 Tầng):**
   * Đập bỏ ý tưởng cây vô hạn (Adjacency List) vì nó gây ác mộng cho kỹ sư ML khi trích xuất Dataset. Hệ thống chốt sử dụng mô hình 3 tầng cực kỳ chặt chẽ và dễ quản lý: `LANGUAGES` (Ngôn ngữ) -> `DIALECTS` (Phương ngữ) -> `CLASSES` (Từ vựng lõi).
   * Ví dụ: Từ vựng `xin-chao` bắt buộc phải có Khóa ngoại (FK) trỏ về phương ngữ `nam` (VSL Miền Nam). Điều này giúp Model AI khi huấn luyện không bị "tẩu hỏa nhập ma" giữa các biến thể vùng miền, và truy vấn xuất dữ liệu cực kỳ nhanh (Không cần đệ quy).

3. **Cụm SESSIONS (Khung thu thập & Cơ chế Commit Handshake):** 
   * Bảng `COLLECTION_SESSIONS` sử dụng Khóa chính tối ưu (Composite-like Key): `CS-YYMMDD-HHMM-[USER_ID_LAST_4]` để nhìn vào là biết ngay ai quay, quay lúc nào.
   * **Cơ chế Bắt tay 3 bước:** Trạng thái khởi tạo là `in_progress`. Chỉ khi User nộp đủ 5 video, Frontend gọi API `/commit` để chốt sổ thành `completed`. Các Session rớt mạng sẽ bị Cronjob xóa ngầm vào ban đêm.

4. **Cụm SAMPLES & SAMPLE_MEDIA (Dữ liệu Video AI & Tối ưu Băng thông):**
   * Lưu các Metadata cốt lõi phục vụ Train AI được tách rạch ròi. `SAMPLES` chỉ lưu trạng thái duyệt (`id`, `session_id`, `status`). Thông số vật lý nằm ở `SAMPLE_MEDIA` (`fps_original`, `seq_len`, `checksum`).
   * **Cột sống còn:** `storage_url` (Trỏ về Google Drive) và `file_path` (Trỏ về MinIO/Local). Khi cần hiển thị lên giao diện web, Frontend chỉ việc đọc cái URL này ra và nhúng vào thẻ `<video src="...">`, giảm tải tuyệt đối cho máy chủ Database.
   * **Chống gian lận (Client-Side Hashing):** Frontend băm file lấy mã SHA-256 đối chiếu với cột `checksum` trước khi tải. Nếu video đã tồn tại, Server chặn ngay lập tức, tiết kiệm 100% dung lượng mạng.

---

### 3.3. Cấu Trúc Các Bảng & Sơ Đồ Thực Thể (ERD)

> [!IMPORTANT]
> **Schema đã được nâng cấp lên ERD v2 (37 bảng) và chuyển về một nguồn duy nhất.**
> - Sơ đồ ERD + đặc tả chi tiết toàn bộ 37 bảng: xem [`docs/database/database_dictionary.md`](database/database_dictionary.md) (Source of Truth về Schema).
> - Các quyết định thiết kế (ADR-1 → ADR-8: Workspace = tenant, tách `DATASET_VERSIONS`/`MODEL_VERSIONS`, Casbin RBAC, Legal 2 bảng, Sheets snapshot, môi trường dev/prod…): xem [`docs/database/erd_v2_unified_design.md`](database/erd_v2_unified_design.md).
>
> Tài liệu này KHÔNG mô tả lại schema để tránh trôi dạt giữa các bản sao. Bản ERD 25 bảng từng nhúng ở đây đã được thay thế bởi ERD v2.

### 🧠 Chiến Lược Quản Lý Phiên Bản AI (MLOps Versioning Strategy)
Để đảm bảo tính tái lập (Reproducibility) trong AI, toàn bộ dữ liệu huấn luyện và mô hình phải được versioning chặt chẽ:
1. **Dataset Versioning (Immutable Manifests):** Mỗi khi chốt sổ một tập dữ liệu để mang đi train, hệ thống sẽ tạo một bản ghi mới trong bảng `DATASETS` kèm một file `manifest_file_path` (định dạng CSV/JSON) chứa danh sách mã SHA-256 của từng video ở thời điểm đó. Nếu user upload thêm video, hệ thống không sửa version cũ mà bắt buộc phải sinh `DATASETS` version mới. Phương pháp này giống với nguyên lý của **DVC (Data Version Control)**.
2. **Model Versioning:** Bảng `MODELS` khóa cứng với `dataset_id`. Một Model Version (VD: `YOLOv8_SL_v2`) luôn biết chính xác nó được sinh ra từ Dataset Version nào. File trọng số (Weights) và Metrics được lưu riêng ở ngoài (`weights_path`, `metadata_file_path`) tránh làm phình Database.
3. **Audit Trail cho MLOps:** Kết hợp với bảng `SYSTEM_AUDIT_LOGS` ở Domain 1, ta có thể truy vết được tài khoản nào đã bấm nút Train tạo ra Model version nào, từ đó loại bỏ hiện tượng "hộp đen" khi nhiều sinh viên/nhà nghiên cứu xài chung hệ thống.

<br>



---

## 4. Giải Pháp MLOps Tự Host Giá Rẻ & Quản Lý Mạng (Infrastructure & Load Balancing)
Hệ thống được thiết kế để chạy trên cụm Server tự host (Self-hosted) nhằm tiết kiệm tối đa chi phí Cloud (AWS/GCP), nhưng vẫn đảm bảo khả năng chịu tải chuẩn doanh nghiệp.

### 4.1. Load Balancer & Reverse Proxy (Traefik / Nginx)
* **Câu hỏi:** "Hệ thống có cần Load Balancer không?" 
* **Trả lời:** **Có, bắt buộc phải có, nhưng KHÔNG tốn tiền.** Thay vì thuê Load Balancer phần cứng đắt đỏ của AWS/Google, chúng ta sẽ dùng **Software Load Balancer (Cân bằng tải bằng phần mềm)**.
* **Giải pháp: Traefik (hoặc Nginx):** 
  * Đóng vai trò là "Người điều phối" đứng ở cửa Server. 
  * Nhận toàn bộ lượng truy cập và tự động chia đường: Trình duyệt vào Web thì dẫn vào Frontend (React), ai gọi API thì dẫn vào Backend (FastAPI), ai tải video thì dẫn thẳng vào MinIO.
  * **Cấp phát SSL/HTTPS tự động:** Traefik sẽ tự động xin chứng chỉ bảo mật Let's Encrypt (Miễn phí 100%) để mã hóa HTTPS. Nhắc lại: *Nếu không có HTTPS, trình duyệt sẽ cấm Web-App bật Camera.*
  * *Mẹo:* Vì chúng ta sử dụng kiến trúc K3s (bên dưới), **Traefik đã được tích hợp mặc định** bên trong K3s. Cài K3s xong là tự động có Load Balancer xịn sò, không tốn thêm tài nguyên cài đặt.

### 4.2. Hệ Thống Lưu Trữ Kép (Google Drive & MinIO Cache)
* **Giữ nguyên Google Drive (Lõi Lưu trữ Chính - Data Lake):** Google Drive là một lựa chọn cực kỳ thông minh và quan trọng để tiết kiệm chi phí lưu trữ Video khổng lồ (Đặc biệt nếu bạn đang dùng tài khoản lưu trữ lớn của trường CTU). Toàn bộ Video sau khi thu thập và xử lý xong sẽ được **chốt giữ vĩnh viễn** trên Google Drive để đảm bảo an toàn không bao giờ mất.
* **MinIO (Bộ nhớ đệm tốc độ cao - Edge Cache):** Để tránh việc liên tục gọi API Google Drive làm chậm hệ thống hoặc bị Google khóa API (Rate-limit) khi có 1000 người truy cập, MinIO sẽ được cài song song làm "Kho trung chuyển". 
  * *Ví dụ:* Khi User tải 50 Video lên, video sẽ vào Server MinIO trước cho cực kỳ nhanh. Ban đêm vắng người, Celery sẽ âm thầm lấy từ MinIO đẩy lên Google Drive một cách nhẹ nhàng.

### 4.3. Công Cụ Tìm Kiếm Siêu Tốc (Meilisearch)
* Khi nền tảng lớn mạnh, người dùng muốn tìm kiếm "Video dạy chữ Xin Chào của tài khoản Nguyễn Văn A". Nếu dùng SQL (PostgreSQL) lệnh `LIKE %...%` để quét 1 triệu video, Server Database sẽ bị treo.
* Sử dụng Meilisearch (nhẹ và tốn ít RAM hơn Elasticsearch rất nhiều) để đánh chỉ mục (Index). Gõ phím đến đâu, video tìm kiếm hiện ra tức thì trong vòng dưới 50 mili-giây.

### 4.4. Hệ Điều Hành Phân Tán & Tác Vụ Nền (K3s, Celery & Prefect)
* **K3s (Kubernetes hạng nhẹ & Cấp phát GPU Động):** Đóng gói toàn bộ Frontend, Backend, Database thành các vùng chứa (Containers).
  * *Scale Web (Chống sập):* K3s tự động giám sát sinh mệnh hệ thống. Nếu lúc 8h tối có 1000 người vào cùng lúc, K3s tự động **nhân bản Backend lên thành 3 bản** để chia lửa (Load Balancer Traefik sẽ chia đều khách cho 3 bản này).
  * *Scale AI Training (Phân bổ GPU):* Do hệ thống cho phép **nhiều người dùng (Workspaces) tự Train AI cùng lúc**, nếu không có K3s, Server sẽ sập vì cháy RAM/GPU. K3s sẽ làm nhiệm vụ tạo ra các `Training Pods` biệt lập. Khi User A bấm "Train", K3s cấp cho User A một phân vùng GPU/RAM vừa đủ để chạy. Các tiến trình Train của nhiều người dùng sẽ được xếp hàng và chạy độc lập, tuyệt đối không dẫm chân lên nhau.
* **Celery & Redis (Tác vụ Vi mô - Micro-tasks):** Celery hiện tại vẫn được giữ lại và làm xương sống cho các **tác vụ nền chớp nhoáng (Fast Background Jobs)**. Khi API nhận yêu cầu, nó ném ngay cho Celery làm để trả kết quả cho User. Ví dụ: Chuyển file từ MinIO sang Google Drive, Gọi API Zalo gửi OTP, Gửi Email khôi phục mật khẩu, Đồng bộ dữ liệu sang Google Sheets. Celery làm việc này cực kỳ xuất sắc và nhẹ nhàng.
* **Prefect (Tác vụ Vĩ mô - MLOps Pipeline):** Đóng vai trò là "Tổng công trình sư". Khác với Celery, Prefect chuyên trị các **chuỗi tác vụ AI khổng lồ (DAG)** chạy mất hàng giờ đồng hồ. Ví dụ chuỗi: *"Lọc 10.000 video -> Trích xuất khung hình -> Gọi GPU Huấn luyện Model -> Đánh giá lỗi"*. Nếu giữa đêm cúp điện, Prefect ghi nhớ tiến độ và sáng mai tự động chạy tiếp đúng ở bước bị đứt, điều mà Celery không thể làm được.

## 5. Chiến Lược Tài Liệu & Tiêu Chuẩn Thiết Bị (Documentation & Hardware Standards)

Để đảm bảo tính kế thừa cho các lập trình viên vào team sau này, cũng như đảm bảo chất lượng video thu thập được, hệ thống áp dụng các tiêu chuẩn sau:

### 5.1. Tiêu Chuẩn Thiết Bị (Edge Hardware)
* **Cấu hình Camera (Webcam/Phone Cam):** 
  * *Tiêu chuẩn:* Độ phân giải tối thiểu 720p (1280x720). Tốc độ khung hình (FPS) bắt buộc phải đẩy lên **60 FPS** để bắt trọn các chuyển động tay cực nhanh mà không bị nhòe (Motion Blur).
  * *Cấu hình Code:* Khi xin quyền mở Camera (`getUserMedia`), Frontend ép cấu hình: `{ video: { width: 1280, height: 720, frameRate: { ideal: 60 } } }`. Smartphone hiện đại hoàn toàn đáp ứng tốt.
* **Cấu hình RAM/Chip:** Được giải quyết qua cơ chế **Hybrid Inference** (Edge AI cho máy > 4GB RAM, Cloud AI cho máy yếu) ở Mục 6.2. Không tích hợp thêm các công cụ kiểm tra ánh sáng rườm rà để đảm bảo tiến độ dự án siêu tốc.

### 5.2. Chiến Lược Tài Liệu Kỹ Thuật (Internal Documentation)
* **Tài liệu API Tự Động (Swagger / Redoc):** 
  * **Giải pháp 0-Code:** Hoàn toàn không cần viết code HTML hay dùng Tool ngoài để sinh tài liệu API. Chúng ta dùng sức mạnh mặc định của FastAPI. Nó sẽ tự động quét các Router và sinh ra trang `/docs` (Swagger UI) và `/redoc`. Mọi API, kiểu dữ liệu, schema đều được liệt kê tự động 100%.
* **Tài liệu Kiến trúc (MkDocs):** Các file Markdown như `SignBridge_Architecture.md` sẽ được MkDocs biên dịch tự động thành một trang Web nội bộ tuyệt đẹp dành cho lập trình viên.

### 5.3. Trang Giới Thiệu (About Page) & Trợ Năng Cho Người Khiếm Thính
Trang About (Giới thiệu dự án) không phải là một trang văn bản tĩnh nhàm chán. Nó được thiết kế như một trung tâm thông tin (Knowledge Hub) chuyên nghiệp tương tự Roboflow:
* **Kiến trúc Layout (Roboflow Style):**
  * **Top Tabs:** Các thẻ điều hướng chính ở trên cùng (VD: `Start`, `Models`, `Workflows`, `Reference`).
  * **Left Sidebar:** Cây thư mục bên trái với các mục có thể đóng mở (Dropdown/Collapsible) như: *Overview*, *Understand -> Architecture, Features, Vocabulary*... Khung nội dung chi tiết nằm ở giữa.
* **Khả năng Mở rộng Động (Extensibility):** Để dễ dàng thêm bớt nội dung, trang About không được hardcode bằng HTML. Toàn bộ nội dung sẽ được xây dựng dựa trên kiến trúc **Markdown/MDX** hoặc một file cấu hình `JSON`. Khi có thông báo hay bài viết mới, Admin chỉ việc ném 1 file `.md` vào thư mục, hệ thống sẽ tự động vẽ ra Menu và liên kết tương ứng.
* **Chế Độ Ký Hiệu Dành Cho Người Khiếm Thính (Deaf-Friendly Mode):** 
  * Sự tinh tế tối thượng: Ở góc trang About sẽ có một công tắc (Toggle) hoặc nút bấm biểu tượng Ngôn ngữ Ký hiệu.
  * Khi người khiếm thính bật nút này lên, toàn bộ các đoạn văn bản giải thích dài dòng trên trang sẽ được chuyển thành **các Video tải sẵn**. Trong video là một chuyên gia (hoặc Admin) đang dùng ngôn ngữ ký hiệu để giới thiệu: Hệ thống này là gì? Cách sử dụng ra sao? Ý nghĩa dự án là gì? Điều này phá vỡ rào cản ngôn ngữ viết và mang lại trải nghiệm 100% bao trùm (Inclusive UX).

## 6. Lộ Trình Triển Khai & Đánh Giá Rủi Ro (Roadmap & Risk Assessment)

### 6.1. Thời gian triển khai (Timeline)
Với quy mô khổng lồ của một nền tảng MLOps như SignBridge, nếu làm từ đầu có thể mất 6 tháng. Nhưng do chúng ta đã có code nền tảng, lộ trình sẽ được chia làm 4 giai đoạn (Phases) để tránh rủi ro:

* **Phase 1: Đập đi xây lại Backend (1 - 2 tuần):** Tái cấu trúc (Refactor) toàn bộ mã nguồn FastAPI hiện tại sang chuẩn `Layered Architecture` (Routers -> Services -> Repositories). Thiết lập lại Database Schema.
* **Phase 2: Nâng cấp hạ tầng tự Host (1 - 2 tuần):** Cài đặt K3s, MinIO (Làm Cache), Traefik và Meilisearch lên Server. Tối ưu hóa lại API Google Drive hiện tại để đồng bộ mượt mà hơn mà không bị Limit.
* **Phase 3: Xây dựng Frontend PWA (2 - 3 tuần):** Code giao diện Web-App mới bằng React/Vite. Áp dụng Web Workers, Virtualization và Canvas Rendering cho Camera. Chuyển đổi thành ứng dụng PWA (Cài đặt được lên máy).
* **Phase 4: Hoàn thiện MLOps Pipeline (3 - 4 tuần):** Thiết lập Prefect, hệ thống đào tạo AI tự động cho người dùng (Train Model), hệ thống Zalo Alert, và Tích hợp luồng Helpdesk (WebSockets).

**=> Tổng thời gian dự kiến để có bản MVP (Sản phẩm khả thi tối thiểu) hoàn chỉnh:** Khoảng 1.5 đến 2 tháng.

### 6.2. Các Vấn Đề Hiện Tại & Rủi Ro Cần Lưu Ý (Current Issues & Risks)
Khi bắt tay vào làm, chúng ta sẽ phải đối mặt với 3 thách thức lớn nhất hiện tại:

1. **Rủi ro giới hạn API Google Drive (Rate-limit):** Vì chúng ta tiếp tục dùng Google Drive làm kho lưu trữ chính, việc nhiều người dùng tải lên cùng lúc có thể khiến Google chặn API tạm thời. (Giải pháp: Luôn phải thông qua Celery để xếp hàng (queue) các luồng gọi API, tuyệt đối không cho Frontend đẩy file dồn dập thẳng lên Google Drive).
2. **Nút thắt cổ chai ở thiết bị người dùng (Client Hardware) & Giải pháp Server-Side Fallback:**
   * *Vấn đề:* Việc chạy AI Mediapipe trực tiếp trên trình duyệt Web (Edge AI) bắt buộc điện thoại phải tương đối mạnh (ví dụ: iPhone 11 trở lên, hoặc Android RAM 4GB+). Máy quá cũ sẽ bị nóng và giật lag khung hình.
   * *Giải pháp (Hybrid Inference):* Thiết kế một cơ chế "Fallback" (Dự phòng) chuyển đổi mượt mà giữa Edge AI và Cloud AI.
     * **Cách Test & Giải phóng RAM (Unload WASM):** Lần đầu mở Camera, Web-App tải thư viện Mediapipe để test trên 20 khung hình. Nếu tốc độ < 15 FPS (máy "Yếu"), Web-App ngay lập tức gọi lệnh **Hủy thư viện (Garbage Collect WASM)** để dọn sạch bộ core AI 15MB ra khỏi RAM trình duyệt. Tuyệt đối không bắt điện thoại cũ phải "cõng" file nặng rác này.
     * **Cách Ghi Nhớ (Caching):** Kết quả test lưu vào `localStorage`. Lần sau mở Web, nếu bộ nhớ báo máy "Yếu", Web-App thậm chí **không tải thư viện Mediapipe về điện thoại nữa** (Tiết kiệm 3G và RAM 100%).
     * **Chế độ Cloud AI (Cho máy yếu):** Trình duyệt lúc này siêu nhẹ, chỉ làm đúng 1 việc: Thu hình Webcam và gửi liên tục qua WebSockets lên Server. Server sẽ chạy Mediapipe giùm và trả tọa độ về. Điện thoại cùi bắp nhất cũng chạy mượt!
3. **Quản lý ổ cứng K3s (Storage Persistence):** Khi triển khai K3s (Kubernetes), nếu Server bị tắt đột ngột do cúp điện, dữ liệu Database PostgreSQL và MinIO có thể bị mất nếu chúng ta không cấu hình `Persistent Volumes` (Lưu trữ bền vững) đúng cách ngay từ ngày đầu.

---
**[KẾT THÚC BẢN THIẾT KẾ KIẾN TRÚC - SẴN SÀNG TRIỂN KHAI]**
