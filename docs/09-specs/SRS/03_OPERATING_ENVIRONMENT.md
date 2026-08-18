# 3. Môi trường vận hành (Operating Environment)

*Hệ thống là **ứng dụng web**, không phải ứng dụng di động gốc. Nó chạy trên một
máy chủ duy nhất dưới dạng 15 dịch vụ container, và người dùng truy cập bằng
trình duyệt trên máy tính cá nhân.*

---

## 3.1 Phía máy chủ

### 3.1.1 Phần cứng

| Hạng mục | Tối thiểu | Máy triển khai thực tế | Ghi chú |
|---|---|---|---|
| CPU | 4 nhân | **6 nhân** | Dưới 4 nhân thì hàng đợi xử lý nền không theo kịp đường thu |
| RAM | 8 GB | **12 GB** | **Bắt buộc** đặt hạn mức bộ nhớ cho từng container — xem §3.1.4 |
| Ổ đĩa | 60 GB trống | 160 GB | Ảnh container ≈ 12 GB; dữ liệu tăng theo số mẫu |
| GPU | Không bắt buộc | **1 GPU NVIDIA** | Không có GPU thì huấn luyện và suy luận vẫn chạy trên CPU, chậm hơn nhiều |
| Mạng | Ra Internet được | — | Cần cho đồng bộ kho lưu trữ ngoài và gửi thư |

### 3.1.2 Phần mềm nền

| Phần mềm | Phiên bản | Vai trò |
|---|---|---|
| Hệ điều hành | Linux (khuyến nghị) hoặc Windows có WSL2 | Máy triển khai chính chạy Linux |
| Docker Engine | 24 trở lên | Đóng gói toàn bộ hệ thống |
| Docker Compose | v2 | Điều phối 15 dịch vụ |
| NVIDIA Container Toolkit | Bản hiện hành | **Chỉ khi có GPU** |
| Git | Bất kỳ | Lấy mã nguồn |

**Không cần cài trực tiếp trên máy chủ:** Python, Node.js, PostgreSQL, Redis —
tất cả nằm trong container. Đây là hệ quả của yêu cầu NFR-M1 (dựng lại từ mã
nguồn bằng một lệnh), và là điều làm việc triển khai lên máy thứ hai khả thi.

### 3.1.3 Mười lăm dịch vụ container

| Nhóm | Dịch vụ | Vai trò |
|---|---|---|
| **Biên** | `nginx` | **Cổng vào duy nhất**; một điểm phục vụ cho cả giao diện lẫn API, nên trình duyệt không phải đối mặt với chính sách cùng nguồn |
| **Ứng dụng** | `frontend` | Giao diện đơn trang React, phục vụ tĩnh sau khi dựng |
| | `backend` | Dịch vụ API, xử lý toàn bộ nghiệp vụ đồng bộ |
| | `realtime_service` | Suy luận thời gian thực; tách riêng vì vòng đời và nhu cầu GPU khác `backend` |
| **Xử lý nền** | `worker` | Tác vụ bất đồng bộ: trích đặc trưng, đồng bộ kho ngoài, dựng bản xem trước |
| | `celery-beat` | Bộ lập lịch: đối soát định kỳ, nhắc hạn, dọn dẹp |
| | `trainer` | Huấn luyện mô hình, chiếm GPU; tách riêng để không tranh chấp với `worker` |
| **Dữ liệu** | `postgres` | Cơ sở dữ liệu quan hệ; **nơi cưỡng chế cách ly** |
| | `redis` | Trung gian truyền tác vụ, bộ đếm hạn mức, bộ đệm phiên |
| | `pg-backup` | Sao lưu định kỳ |
| **Khởi tạo** | `sot-init` | Kéo và **xác minh chữ ký** danh mục trước khi bất kỳ dịch vụ nào chạy |
| **Quan trắc** | `prometheus` | Thu thập chỉ số |
| | `grafana` | Biểu đồ và **cảnh báo** |
| | `loki` | Kho nhật ký |
| | `promtail` | Thu gom nhật ký từ container |

**Ba lý do tách dịch vụ** — nêu ra để phân biệt với việc tách vì mốt kiến trúc:

1. `trainer` tách khỏi `worker` vì **cạnh tranh tài nguyên**: một tác vụ huấn
   luyện chiếm GPU hàng giờ; chung tiến trình thì tác vụ trích đặc trưng ngắn bị
   bỏ đói.
2. `realtime_service` tách khỏi `backend` vì **vòng đời khác nhau**: nó giữ mô
   hình đã nạp trong bộ nhớ và phục vụ kết nối dài; `backend` phục vụ yêu cầu
   ngắn và khởi động lại thường xuyên hơn.
3. `sot-init` tách ra vì nó phải chạy **trước** và **kết thúc** trước khi các
   dịch vụ khác bắt đầu — một quan hệ thứ tự, không phải quan hệ gọi.

**`sot-init` thoát với mã lỗi chuyên biệt sẽ chặn toàn bộ hệ thống khởi động.**
Đây là quyết định có chủ ý: một máy không xác thực được danh mục thì không được
phép phục vụ. Thiết kế fail-closed ở đây trả giá bằng khả năng sẵn sàng để đổi
lấy khả năng không phục vụ dữ liệu sai.

### 3.1.4 Hạn mức tài nguyên theo thành phần

Trên một máy 12 GB RAM chạy 14 dịch vụ, **không đặt hạn mức bộ nhớ là một lỗi
thiết kế vận hành**: một dịch vụ rò bộ nhớ sẽ kéo cả máy xuống, và hệ điều hành
sẽ chọn nạn nhân theo cách không ai muốn.

| Dịch vụ | Hạn mức bộ nhớ | Lý do |
|---|---|---|
| `postgres` | Cấp phát lớn nhất | Nơi mọi truy vấn đi qua |
| `redis` | 400 MB, chính sách loại bỏ `volatile-lru` | Là bộ đệm và trung gian truyền tin, **không** phải kho bền |
| `trainer` | Cấp phát riêng, có GPU | Chiếm tài nguyên hàng giờ |
| `backend`, `worker` | Trung bình | Nhiều tiến trình con |
| Nhóm quan trắc | Nhỏ | Không được cạnh tranh với ứng dụng |

Toàn bộ 15 dịch vụ đều có `healthcheck`. Hai chi tiết bắt buộc, học từ sự cố thật:
ảnh dịch vụ **không có** công cụ tải trang phổ biến nên phép kiểm sức khoẻ phải
viết bằng thứ có sẵn trong ảnh; và phải dùng địa chỉ IPv4 cố định `127.0.0.1` thay
vì tên máy chủ cục bộ — tên đó có thể phân giải ra IPv6 mà dịch vụ không lắng nghe.

### 3.1.5 Công nghệ phía máy chủ

| Thành phần | Công nghệ và phiên bản |
|---|---|
| Khung dịch vụ web | FastAPI 0.95.2 trên Uvicorn 0.22 / Gunicorn |
| Kiểm định dữ liệu | Pydantic 1.10.11 |
| Truy cập dữ liệu | SQLAlchemy 1.4.50 + psycopg2 2.9.7 |
| Cơ sở dữ liệu | PostgreSQL (chính sách bảo mật mức hàng, trigger bất biến) |
| Hàng đợi tác vụ | Celery 5.3.1 với Redis 4.5.1 làm trung gian |
| Thị giác máy tính | MediaPipe 0.10.21, OpenCV headless 4.11 |
| Học sâu | PyTorch 2.7.1 (bản `cu128`, phủ cả `sm_86` lẫn `sm_120`), scikit-learn 1.3.2 |
| Xác thực | passlib + bcrypt 4.0.1, python-jose 3.3.0 (JWT) |
| Phân quyền | Casbin 1.36.0 (RBAC-with-domains) — mặc định `AUTHZ_MODE=shadow`: **chỉ quan sát**, hệ cũ quyết định |
| Tổng hợp giọng nói | edge-tts 7.2.8 |
| Nhật ký và chỉ số | structlog 24.4, prometheus-client 0.20, asgi-correlation-id 4.3 |
| Kho ngoài | google-api-python-client 2.196 (Drive + Sheets) |

---

## 3.2 Phía máy khách (người dùng)

### 3.2.1 Yêu cầu tối thiểu

| Hạng mục | Yêu cầu |
|---|---|
| Trình duyệt | Hỗ trợ **WebAssembly** và **WebRTC** — Chrome, Edge, Firefox bản hiện hành |
| Camera | Bất kỳ webcam nào cho ảnh 640×480 trở lên |
| CPU | Đủ để chạy trích điểm mốc ở **tối thiểu 15 khung/giây** (NFR-P2) |
| Quyền trình duyệt | Truy cập camera; truy cập micro **chỉ khi** dùng nút nhập bằng giọng nói |
| Mạng | Không cần ổn định liên tục: mất kết nối khi đang gửi thì dữ liệu **giữ lại trong trình duyệt** và thử lại được |

**Yêu cầu về máy khách là có thật, và đó là đánh đổi có chủ ý.** Vì trích điểm
mốc chạy **trong trình duyệt**, chi phí tính toán dời từ máy chủ sang máy người
dùng. Đổi lại: video thô không bắt buộc rời khỏi máy đó, băng thông giảm mạnh, và
không có video thô để rò rỉ.

### 3.2.2 Công nghệ phía trình duyệt

| Thành phần | Công nghệ và phiên bản |
|---|---|
| Khung giao diện | React 19.1 + TypeScript 5.9, dựng bằng Vite 7.1 |
| Định tuyến | react-router-dom 7.9, chạy dưới `basename` cấu hình được |
| Giao diện | Tailwind CSS 4.1; 70 biểu tượng SVG, **0 emoji** trong giao diện |
| Trích điểm mốc | `@mediapipe/hands` 0.4 (WebAssembly), `@mediapipe/camera_utils`, `@mediapipe/drawing_utils` |
| Dựng hình khung xương | three.js 0.185 (3D) và canvas 2D — ba bộ dựng khác nhau |
| Biểu đồ | recharts 3.2 |
| Gọi API | axios 1.15 |
| Đa ngôn ngữ | Lớp i18n tự viết; **không có chuỗi cứng trong mã** |
| Kiểm thử | Vitest 4.1 + Testing Library |

**Một cái bẫy đã ghim vào `package.json`:** lệnh kiểm kiểu phải là
`npm run typecheck` (tức `tsc -b --noEmit`). Lệnh quen tay `npx tsc --noEmit` sẽ
đọc `tsconfig.json` gốc — tệp đó là `files: []` cộng hai project reference — nên
nó kiểm **đúng không tệp nào**, thoát 0, và trông y hệt một lượt kiểm sạch. Một
lần quét mã từng giấu 14 lỗi kiểu sau lỗ hổng đó.

### 3.2.3 Tham số thu mặc định

| Tham số | Giá trị | Ghi chú |
|---|---|---|
| `TARGET_FRAMES` | 60 khung | Cửa sổ thu chuẩn |
| Bước nhảy cửa sổ trượt | 2 | Áp ở bước xử lý nền |
| `CAPTURE_FRAME_WIDTH` | 1280 | Chiều rộng khung hình lấy từ camera |
| Số chiều mỗi khung | **126** | 21 điểm mốc × 3 toạ độ × 2 bàn tay |
| Tốc độ trích tối thiểu | 15 khung/giây | Cửa sổ 60 khung hoàn tất trong ≈ 4 giây |

---

## 3.3 Đường truy cập và triển khai

| Hạng mục | Giá trị |
|---|---|
| Giao thức | HTTPS qua `nginx` (cổng vào duy nhất) |
| Đường dẫn cơ sở | `/voya` trên máy chủ CTU; `/` khi chạy cục bộ |
| Phiên làm việc | Token trong cookie mà mã trong trình duyệt **không đọc được**; thời hạn 3 giờ |
| Bảng điều khiển chỉ số | `/grafana` |
| Điểm kiểm sức khoẻ | `/health` |

**Đường dẫn cơ sở là một ràng buộc lan toả:** mọi liên kết tuyệt đối, mọi đường
chuyển hướng và mọi tài nguyên tĩnh phải tôn trọng nó. Chuyển hướng khi đăng xuất
cũng phải nằm **trong** đường dẫn cơ sở, nếu không người dùng bị đá ra khỏi ứng
dụng.

**Biến `FRONTEND_BASE_URL` phải khớp chính xác địa chỉ người dùng gõ vào trình
duyệt.** Sai biến này thì liên kết trong thư đặt lại mật khẩu trỏ sai máy chủ,
người dùng bấm vào và không tới được — mà hệ thống không báo lỗi gì.

---

## 3.4 Ba cái bẫy của môi trường container

Ba mục dưới đây là bài học từ sự cố thật, và chúng giải thích vì sao hệ thống có
những công cụ vận hành trông có vẻ thừa.

**a) Trạng thái khoẻ mạnh không đồng nghĩa với mã mới.** Một ảnh giao diện từng
chạy **sau mã nguồn năm tiếng** trong khi toàn bộ container báo khoẻ mạnh; trang
web tải hoàn hảo và phục vụ gói mã cũ. Lệnh liệt kê container trả lời *"tiến
trình còn sống"*, không trả lời *"đó có phải tiến trình bạn vừa dựng"*. Đây là lý
do có `scripts/check_deploy_freshness.py`, và nó bắt ba kiểu lệch.

Chi tiết dễ quên: **một ảnh container chống lưng cho năm dịch vụ**. Dựng lại ảnh
mà chỉ khởi động lại một dịch vụ thì bốn dịch vụ còn lại vẫn chạy mã cũ — hay
quên nhất là bộ lập lịch.

**b) Thay đổi cấu hình không tự có hiệu lực.** Sửa tệp biến môi trường rồi khởi
động lại container là **không đủ**: biến môi trường được nạp lúc **tạo**
container, không phải lúc khởi động. Phải tạo lại container.

**c) Mất cấu hình chồng lớp.** Chạy lệnh điều phối **trần** — không kèm danh sách
tệp khai báo — sẽ đánh rơi các lớp chồng lên, trong đó có lớp GPU. Hệ thống vẫn
chạy, chỉ có điều **không còn GPU**, và không có thông báo nào. Cách vá: khai báo
`COMPOSE_FILE` trong `.env` để mọi lệnh đều đọc đủ.

---

## 3.5 Môi trường phát triển và kiểm thử

| Môi trường | Cấu hình |
|---|---|
| Chạy bộ kiểm thử | `sh scripts/run_tests.sh` — **luôn dùng kịch bản này**, không gọi trực tiếp bộ chạy kiểm thử |
| Ảnh kiểm thử | `backend/Dockerfile.test`, container chạy **trên mạng của các dịch vụ** |
| CSDL đích | `signdb_test`, biến `EXPECTED_DATABASE` bắt buộc khớp |
| Vai chạy | `voya_test_app` — **không** `SUPERUSER`, **không** `BYPASSRLS` |

**Vì sao bắt buộc dùng kịch bản:** nó đặt đúng cơ sở dữ liệu đích, đúng không gian
bộ đệm riêng, đúng vai chạy và đúng ảnh container. Sự cố ngày 13/08/2026 xảy ra
chính vì bỏ qua nó — bộ kiểm thử áp một phiên bản lược đồ dở dang lên **cơ sở dữ
liệu sản xuất** và đóng dấu phiên bản sai. Hai lớp chốt chặn đã được thêm sau đó.

**Môi trường đo phải tách khỏi môi trường kiểm thử chức năng.** Container đo hiệu
năng (`voya_backend_perf`) tách khỏi container thí nghiệm cách ly
(`voya_backend_iso`) — không phải phòng xa, mà vì hai sự cố đã xảy ra trong cùng
một buổi: một container bị dựng lại **giữa** lượt benchmark, và một cây fixture
được mount làm khối lượng công việc của cùng một URL đổi hẳn trong khi bảng kết
quả trông vẫn bình thường.
