# PHỤ LỤC B: CÀI ĐẶT HỆ THỐNG

*Phụ lục này cho phép dựng lại toàn bộ hệ thống từ mã nguồn trên một máy sạch.
Nó cũng là bằng chứng cho yêu cầu NFR-M1 ở Chương 1 §3.5: hệ thống dựng lại được
bằng một lệnh — và điều đó đã được kiểm chứng bằng một lần triển khai thật lên
máy thứ hai.*

---

## 1. Yêu cầu cài đặt

### 1.1 Yêu cầu phần cứng

| Hạng mục | Tối thiểu | Máy triển khai thực tế | Ghi chú |
|---|---|---|---|
| CPU | 4 nhân | **6 nhân** | Dưới 4 nhân thì hàng đợi xử lý nền không theo kịp đường thu |
| RAM | 8 GB | **12 GB** | Bắt buộc đặt hạn mức bộ nhớ cho từng container — xem §1.3 |
| Ổ đĩa | 60 GB trống | 160 GB | Ảnh container ≈ 12 GB; dữ liệu tăng theo số mẫu |
| GPU | Không bắt buộc | **1 GPU NVIDIA** | Không có GPU thì huấn luyện và suy luận vẫn chạy trên CPU, chậm hơn nhiều |
| Mạng | Ra Internet được | — | Cần cho đồng bộ kho lưu trữ ngoài và gửi thư |

**Máy khách của người dùng** (để thu mẫu):

| Hạng mục | Yêu cầu |
|---|---|
| Trình duyệt | Hỗ trợ WebAssembly và WebRTC — Chrome, Edge, Firefox bản hiện hành |
| Camera | Bất kỳ webcam nào cho ảnh 640×480 trở lên |
| CPU | Đủ để chạy trích điểm mốc ở **tối thiểu 15 khung/giây** (NFR-P2) |

Trích điểm mốc chạy **trong trình duyệt**, nên yêu cầu về máy khách là có thật —
đây là đánh đổi của quyết định thiết kế ở Chương 3 §2.3.3.

### 1.2 Yêu cầu phần mềm

| Phần mềm | Phiên bản | Vai trò |
|---|---|---|
| Hệ điều hành | Linux (khuyến nghị) hoặc Windows có WSL2 | Máy triển khai chính chạy Linux |
| Docker Engine | 24 trở lên | Đóng gói toàn bộ hệ thống |
| Docker Compose | v2 | Điều phối 15 dịch vụ |
| NVIDIA Container Toolkit | Bản hiện hành | **Chỉ khi có GPU** |
| Git | Bất kỳ | Lấy mã nguồn |

**Không cần cài đặt trực tiếp trên máy chủ:** Python, Node.js, PostgreSQL, Redis.
Tất cả nằm trong container. Đây là hệ quả của yêu cầu NFR-M1, và nó là điều làm
việc triển khai lên máy thứ hai khả thi.

### 1.3 Hạn mức tài nguyên theo từng thành phần

Trên một máy 12 GB RAM chạy 14 dịch vụ, **không đặt hạn mức bộ nhớ là một lỗi
thiết kế vận hành**: một dịch vụ rò bộ nhớ sẽ kéo cả máy xuống, và hệ điều hành
sẽ chọn nạn nhân theo cách không ai muốn.

| Dịch vụ | Hạn mức bộ nhớ | Lý do |
|---|---|---|
| `postgres` | Cấp phát lớn nhất | Nơi mọi truy vấn đi qua |
| `redis` | 400 MB, chính sách loại bỏ theo khoá có hạn dùng | Là bộ đệm và trung gian truyền tin, **không** phải kho bền |
| `trainer` | Cấp phát riêng, có GPU | Chiếm tài nguyên hàng giờ |
| `backend`, `worker` | Trung bình | Nhiều tiến trình con |
| Nhóm quan trắc | Nhỏ | Không được cạnh tranh với ứng dụng |

---

## 2. Triển khai hệ thống

### 2.1 Các bước

```bash
# 1. Lấy mã nguồn
git clone <kho mã nguồn> && cd VOYA-Collector

# 2. Chuẩn bị cấu hình
cp .env.example .env
$EDITOR .env                      # xem §2.2 — bốn biến bắt buộc sửa

# 3. Chuẩn bị danh sách máy chủ công khai được phép
cp deploy/public_hosts.example.txt deploy/public_hosts.txt
$EDITOR deploy/public_hosts.txt

# 4. Triển khai — tự dò GPU
./scripts/deploy.sh               # dựng ảnh rồi khởi động
./scripts/deploy.sh --no-build    # khởi động, không dựng lại ảnh
./scripts/deploy.sh --cpu         # ép chạy CPU dù máy có GPU

# 5. Kiểm chứng sau triển khai
docker compose ps                             # trạng thái dịch vụ
python scripts/check_deploy_freshness.py      # mã đang chạy có khớp mã nguồn không
```

**Kịch bản triển khai tự dò GPU thay vì bắt người vận hành nhớ thêm hay bớt một
tham số.** Cách dò không phải "có trình điều khiển không" mà là **"một container
có thật sự chiếm được GPU không"** — bộ công cụ có thể vắng mặt, hoặc có mặt mà
hỏng, và chỉ một lần yêu cầu thật mới phân biệt được hai trường hợp. Nếu khai báo
GPU trên máy không có bộ công cụ, dịch vụ huấn luyện chết ngay lúc tạo container
và kéo theo cả lượt triển khai.

### 2.2 Bốn biến cấu hình bắt buộc sửa

| Biến | Nội dung | Hỏng thế nào nếu sai |
|---|---|---|
| Mật khẩu cơ sở dữ liệu | Mật khẩu của vai ứng dụng | Không khởi động được |
| Địa chỉ truy cập giao diện | Phải **khớp chính xác** địa chỉ người dùng gõ vào trình duyệt | Liên kết trong thư đặt lại mật khẩu trỏ sai máy chủ; người dùng bấm vào và không tới được |
| Cấu hình máy chủ thư | Máy chủ, cổng, tài khoản | Thư xác thực và lời mời không gửi được — **im lặng** |
| Danh sách tệp khai báo triển khai | Ghi đủ các tệp chồng lớp, kể cả tệp GPU | Lệnh chạy trần **đánh rơi** lớp cấu hình GPU, và hệ thống mất GPU mà không báo gì |

### 2.3 Ba cái bẫy của triển khai bằng container

Ba mục dưới đây là bài học từ sự cố thật, và chúng giải thích vì sao hệ thống có
những công cụ vận hành trông có vẻ thừa.

**a) Trạng thái khoẻ mạnh không đồng nghĩa với mã mới.** Một ảnh giao diện từng
chạy **sau mã nguồn năm tiếng** trong khi toàn bộ container báo khoẻ mạnh; trang
web tải hoàn hảo và phục vụ gói mã cũ. Lệnh liệt kê container trả lời *"tiến
trình còn sống"*, không trả lời *"đó có phải tiến trình bạn vừa dựng"*. Đây là lý
do có công cụ kiểm chứng độ tươi triển khai; nó bắt ba kiểu lệch.

Một chi tiết dễ quên: **một ảnh container chống lưng cho năm dịch vụ**. Dựng lại
ảnh mà chỉ khởi động lại một dịch vụ thì bốn dịch vụ còn lại vẫn chạy mã cũ — hay
quên nhất là bộ lập lịch.

**b) Thay đổi cấu hình không tự có hiệu lực.** Sửa tệp biến môi trường rồi khởi
động lại container là **không đủ**: biến môi trường được nạp lúc **tạo**
container, không phải lúc khởi động. Phải tạo lại container.

**c) Mất cấu hình chồng lớp.** Chạy lệnh điều phối **trần** — không kèm danh sách
tệp khai báo — sẽ đánh rơi các lớp cấu hình chồng lên, trong đó có lớp GPU. Hệ
thống vẫn chạy, chỉ có điều không còn GPU, và không có thông báo nào. Cách vá:
khai báo danh sách tệp trong biến môi trường để mọi lệnh đều đọc đủ.

**d) Kiểm tra sức khoẻ phải phù hợp với môi trường bên trong container.** Ảnh
dịch vụ **không có** công cụ tải trang phổ biến, nên phép kiểm sức khoẻ phải viết
bằng thứ có sẵn trong ảnh. Và phải dùng địa chỉ IPv4 cố định thay vì tên máy chủ
cục bộ — tên đó có thể phân giải ra IPv6 mà dịch vụ không lắng nghe.

### 2.4 Quản lý thay đổi cấu trúc dữ liệu

Hai loại thay đổi, **phải tách**:

| Loại | Chạy khi nào | Được làm gì |
|---|---|---|
| Bước tự động lúc khởi động | Mỗi lần dịch vụ khởi động | **Chỉ thêm**: tạo bảng còn thiếu, thêm cột còn thiếu |
| Lệnh di trú tường minh | Do người vận hành gọi | Mọi thay đổi **một chiều**: chuyển dữ liệu, bỏ bảng cũ, bỏ chỉ mục |

**Hai chốt chặn bắt buộc:**

1. **Chốt phiên bản hai chiều.** Dịch vụ **từ chối khởi động** khi phiên bản lược
   đồ không khớp — cả khi lược đồ cũ hơn lẫn khi mới hơn. Chiều thứ hai quan
   trọng không kém: một dịch vụ cũ chạy trên lược đồ mới sẽ ghi dữ liệu thiếu cột.
2. **Chốt đích đến.** Lệnh di trú bắt buộc khai tên cơ sở dữ liệu đích. Chốt này
   sinh ra từ sự cố ngày 13/08/2026, khi biến cấu hình tên cơ sở dữ liệu **không
   tham gia dựng chuỗi kết nối** và một lượt chạy đi nhầm vào cơ sở dữ liệu sản
   xuất.

**Kiểm nợ lược đồ:** sau **ba** lần khởi động liên tiếp, phần chênh lệch cấu trúc
phải rỗng. Ba lần chứ không phải một, vì có loại chênh lệch chỉ lộ ra ở lần thứ
hai hoặc thứ ba.

### 2.5 Sao lưu và khôi phục

**Nguyên tắc: một bản sao lưu chưa được diễn tập khôi phục là một bản sao lưu
chưa tồn tại.**

```bash
sh scripts/pg_backup.sh                 # sao lưu
sh scripts/pg_backup.sh --drill         # diễn tập khôi phục vào CSDL tạm
```

Ba chi tiết bắt buộc:

* **Thứ tự thao tác:** kết xuất trước, nén sau. Đảo thứ tự sẽ sinh ra tệp trông
  hợp lệ nhưng thiếu phần đuôi.
* **Kiểm toàn vẹn phải đọc hết nội dung.** Công cụ liệt kê nội dung tệp sao lưu
  **không** phát hiện được tệp bị cụt — nó chỉ đọc phần mục lục.
* **Nhiều bản, nhiều nơi.** Cơ chế mã hoá và sao chép sang ổ khác đã có, mặc định
  tắt; bật khi triển khai thật.

### 2.6 Quan trắc

| Thành phần | Địa chỉ | Nội dung |
|---|---|---|
| Bảng điều khiển chỉ số | `/grafana` | Biểu đồ và **cảnh báo** |
| Kho nhật ký | qua bảng điều khiển | Nhật ký có cấu trúc từ mọi dịch vụ |
| Điểm kiểm sức khoẻ | `/health` | Trạng thái từng thành phần |

Cảnh báo sống ở bảng điều khiển, không có thành phần quản lý cảnh báo riêng —
phù hợp với quy mô một máy chủ. **Nội dung thư cảnh báo là văn bản thuần**: đánh
dấu định dạng sẽ bị chuyển thành ký tự thoát, thư vẫn gửi nhưng không đọc được.

### 2.7 Chạy bộ kiểm thử

```bash
sh scripts/run_tests.sh
```

**Luôn dùng kịch bản này**, không gọi trực tiếp bộ chạy kiểm thử. Kịch bản đặt
đúng cơ sở dữ liệu đích, đúng không gian bộ đệm riêng, đúng vai chạy, và đúng ảnh
container kiểm thử. Bỏ qua nó là con đường dẫn tới sự cố ở §2.4.

Chi tiết về hai nền chạy, các dạng "đỏ giả" và cách phân định: Chương 4 §3.2 và
`docs/08-testing/TESTING.md`.

### 2.8 Cổng trước khi triển khai

Bốn bước, chạy theo thứ tự; bước nào đỏ thì dừng:

```
1. Bộ kiểm thử dịch vụ         → 0 đỏ, và sổ dấu vết báo 0 hàng còn sót
2. Bộ kiểm thử + kiểm kiểu giao diện
3. Nợ lược đồ                  → rỗng sau BA lần khởi động liên tiếp
4. Kiểm chứng độ tươi triển khai
```

**Về bước 2:** lệnh kiểm kiểu phải là lệnh của dự án. Lệnh kiểm kiểu mặc định
thường dùng sẽ **không kiểm tệp nào** với cấu hình của dự án này và vẫn thoát
thành công — trông y hệt một lượt kiểm sạch. Một lần quét mã từng giấu **14 lỗi
kiểu** sau lỗ hổng đó.

---

## 3. Triển khai trên máy thứ hai — bằng chứng cho NFR-M1

Hệ thống đã được triển khai thành công lên một máy thứ hai với cấu hình phần cứng
khác. Ba điều được kiểm chứng qua lần triển khai đó:

1. **Quy trình không phụ thuộc máy cụ thể.** Kịch bản triển khai tự dò GPU và tự
   chọn lớp cấu hình phù hợp.
2. **Bước dựng lược đồ trên máy sạch từng thiếu sót nghiêm trọng.** Lần chạy đầu
   trên cơ sở dữ liệu dựng từ số không cho **22 kiểm thử đỏ**, do lược đồ tạo ra
   thiếu **2 bảng, 7 khoá ngoại và 14 cột** so với máy đang chạy. Không có lần
   triển khai này thì mọi máy mới sẽ nhận một lược đồ yếu hơn, trong im lặng.
3. **Một lớp lỗi chỉ xuất hiện trên máy Windows:** tệp kịch bản khởi động bị đổi
   ký tự xuống dòng theo quy ước Windows, khiến container giao diện chết trong
   vòng lặp với thông báo "không tìm thấy tệp thực thi". Đã cố định quy ước xuống
   dòng cho các tệp kịch bản.

---

## 4. Danh mục kịch bản vận hành

| Kịch bản | Công dụng |
|---|---|
| `scripts/deploy.sh` | Triển khai, tự dò GPU |
| `scripts/run_tests.sh` | Chạy bộ kiểm thử đúng môi trường |
| `scripts/check_deploy_freshness.py` | Phát hiện mã đang chạy lệch mã nguồn |
| `scripts/pg_backup.sh` | Sao lưu và diễn tập khôi phục |
| `scripts/init-db.sh` / `.ps1` | Khởi tạo cơ sở dữ liệu và vai |
| `scripts/docker_gc.sh` | Dọn ảnh và lớp không dùng — cần thiết vì ổ đĩa là ràng buộc |
| `scripts/adversarial_isolation.py` | Chạy phép đo cách ly đối kháng (Chương 4 §5.2) |
| `scripts/measure_api_latency.py` | Chạy phép đo độ trễ (Chương 4 §5.3) |
| `scripts/do_hieu_qua_luu_tru.py` | Chạy phép đo hiệu quả lưu trữ (Chương 4 §5.4) |
| `scripts/measure_sot_integrity.sh` | Chạy ma trận giả mạo nguồn sự thật (Chương 4 §5.5) |
| `scripts/freeze_measurement_code.sh` | Đóng băng cây mã trước khi đo, để phép đo gắn với một phiên bản xác định |
