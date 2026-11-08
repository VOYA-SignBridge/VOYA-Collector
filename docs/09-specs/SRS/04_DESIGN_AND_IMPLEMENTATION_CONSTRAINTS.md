# 4. Ràng buộc về thiết kế và thực thi (Design and Implementation Constraints)

*Ràng buộc chia hai loại: **ngoại sinh** (hoàn cảnh áp đặt — phần cứng, ngân
sách, di sản) và **tự đặt** (nhóm phát triển chọn, và phải bảo vệ được lựa chọn
đó). Trộn hai loại là cách nhanh nhất để một quyết định kiến trúc bị đọc nhầm
thành một sự bó tay.*

---

## 4.1 Ràng buộc thực thi (ngoại sinh)

| Mã | Ràng buộc | Hệ quả lên thiết kế |
|---|---|---|
| RB-T1 | **Một máy chủ vật lý duy nhất**: 6 nhân, 12 GB RAM, một GPU | Không dựng được cụm; mọi dịch vụ chạy container trên cùng máy, phải đặt hạn mức bộ nhớ cho từng container để một dịch vụ rò bộ nhớ không giết cả máy |
| RB-T2 | **Không có ngân sách hạ tầng đám mây** | Kho đối tượng chuyên dụng bị loại; dùng hệ tệp cục bộ cộng kho lưu trữ ngoài miễn phí. Đây là nguồn gốc của bài toán **hai mặt phẳng lưu trữ** |
| RB-T3 | Triển khai đặt sau đường dẫn cơ sở `/voya` trên máy chủ của đơn vị | Mọi liên kết tuyệt đối, mọi đường chuyển hướng và mọi tài nguyên tĩnh phải tôn trọng đường dẫn cơ sở |
| RB-T4 | Kho lưu trữ ngoài có **hạn mức lượt gọi** và có thể tạm ngừng phục vụ | Đồng bộ phải bất đồng bộ và có thử lại; hỏng đồng bộ **không được** làm hỏng đường thu |
| RB-T5 | Người dùng thu dữ liệu bằng **máy tính cá nhân phổ thông**, đường truyền không ổn định | Trích đặc trưng tại máy khách; giữ dữ liệu ở trình duyệt khi mất mạng |
| RB-T6 | Thời gian thực hiện giới hạn trong một học kỳ, một người thực hiện | Ưu tiên hoàn thiện trục cách ly và trục dữ liệu; các tầng phân quyền sâu hơn giữ ở mức thiết kế tham chiếu |

---

## 4.2 Ràng buộc thiết kế

| Mã | Ràng buộc | Loại | Lý do |
|---|---|---|---|
| RB-D1 | **Kế thừa một hệ thống đang chạy**, không viết mới từ đầu | Ngoại sinh | Hệ thống tiền thân đã có dữ liệu thật và người dùng thật. Chuyển đổi phải theo lối **bóp nghẹt dần**: mở rộng song song rồi chuyển tải, không thay thế một lần |
| RB-D2 | Nguồn sự thật của kho mẫu hiện là **tệp CSV**; cơ sở dữ liệu quan hệ là bản sao truy vấn | Ngoại sinh | Di sản kiến trúc. Không sửa được trong phạm vi đề tài mà không phá dữ liệu đang có; phải thiết kế cơ chế **đối soát** thay vì giấu |
| RB-D3 | Cách ly phải cưỡng chế **ở tầng cơ sở dữ liệu**, không ở tầng ứng dụng | **Tự đặt** | Là đóng góp lõi. Lọc ở tầng ứng dụng hỏng theo kiểu **hỏng im lặng**: một hàm quên điều kiện lọc vẫn chạy, vẫn trả kết quả, vẫn qua kiểm thử chức năng — chỉ có điều nó trả cả dữ liệu của tổ chức khác |
| RB-D4 | Vai chạy của ứng dụng **không được có quyền DDL** | **Tự đặt** | Lệnh vô hiệu hoá chính sách bảo mật mức hàng là một lệnh DDL. Một vai vừa ghi được dữ liệu vừa chạy được DDL thì **tự gỡ được vòng vây của chính nó** |
| RB-D5 | Không lưu video thô ở đường thu qua webcam | **Tự đặt** | Vừa là yêu cầu quyền riêng tư, vừa là nguồn của hiệu quả lưu trữ. Hệ quả: **không đo ngược lại được** tỉ lệ giảm dung lượng trên chính dữ liệu của hệ thống — phải đo trên nguồn video bên ngoài |
| RB-D6 | Biểu diễn dữ liệu cố định ở **126 chiều mỗi khung** (21 điểm mốc × 3 toạ độ × 2 bàn tay) | **Tự đặt** | Quyết định về phạm vi: chỉ dùng thông tin bàn tay. Tư thế toàn thân và biểu cảm khuôn mặt nằm ngoài phạm vi |
| RB-D7 | Danh mục **không có đường rơi ngược** về mặt phẳng cộng đồng lúc chạy | **Tự đặt** | Rơi ngược làm dữ liệu của hai mặt phẳng lẫn vào nhau mà không ai biết. Thiếu thì **dừng** |
| RB-D8 | Văn bản pháp lý đã công bố là **bất biến ở tầng cơ sở dữ liệu** | **Tự đặt** | Chấp thuận trỏ tới cặp (loại, phiên bản); đổi nội dung dưới chân nó biến bằng chứng thành lời khẳng định suông |
| RB-D9 | Mọi phép đo trong đề tài phải **có khả năng thất bại** và có **đối chứng dương** | **Tự đặt** | Ràng buộc phương pháp. Một phép đo không thể thất bại thì không đo gì cả |

---

## 4.3 Ràng buộc chính sách và pháp lý

| Hạng mục | Nội dung |
|---|---|
| Căn cứ pháp lý | **Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15** (ban hành 26/06/2025, hiệu lực 01/01/2026) và **Nghị định 356/2025/NĐ-CP** (hiệu lực cùng ngày) |
| Khả năng tiếp cận | **WCAG 2.2** của W3C được dùng làm **khung tham chiếu** để hình thành yêu cầu giao diện |
| Đồng thuận | Đăng ký **luôn** kéo theo chấp thuận văn bản pháp lý; không chấp thuận thì tài khoản không được tạo |

**Năm năng lực hệ thống mà yêu cầu pháp lý chuyển thành**, và cả năm đều đã có
mặt trong thiết kế trước khi đối chiếu luật:

1. Truy được các bản ghi liên quan tới một chủ thể dữ liệu → quan hệ *người ký –
   mẫu*, ghi nhận tại thời điểm thu
2. Bảo toàn phiên bản văn bản và bằng chứng chấp thuận → văn bản bất biến + chấp
   thuận trỏ tới cặp (loại, phiên bản)
3. Giới hạn người và quy trình được phép xử lý dữ liệu → cách ly + phân quyền
4. Chứng minh được điều gì đã xảy ra với dữ liệu → nhật ký kiểm toán bền vững
5. Vòng đời xoá phủ cả siêu dữ liệu lẫn tệp ngoài cơ sở dữ liệu → xoá mềm, thùng
   rác, dọn hẳn

**Hai phát biểu phải giữ đúng mức, không được nới:**

* **Không tuyên bố đã tuân thủ pháp lý toàn diện.** Đánh giá tuân thủ đầy đủ còn
  phụ thuộc quy trình vận hành, nội dung văn bản, vai trò pháp lý của các bên và
  bối cảnh triển khai thực tế. Bản SRS này chỉ chuyển yêu cầu pháp lý thành ràng
  buộc kiến trúc.
* **Không tuyên bố đạt một mức conform WCAG cụ thể.** WCAG 2.2 là khung tham
  chiếu; tuyên bố mức AA hay bất kỳ mức nào khác cần kế hoạch kiểm thử và bằng
  chứng tương ứng, và hiện chưa có.

**Một suy diễn sai cần chặn trước:** dữ liệu đã chuyển sang điểm mốc **không**
đương nhiên ra khỏi phạm vi quản trị dữ liệu cá nhân. Mức độ nhận dạng phải đánh
giá theo khả năng liên kết với cá nhân, dữ liệu phụ trợ và mục đích xử lý.

---

## 4.4 Ràng buộc về giao diện với hệ thống khác

| Hệ thống ngoài | Ràng buộc |
|---|---|
| Google Drive | Giữ tệp đặc trưng, video thô, bản xem trước. Hạn mức lượt gọi → mọi thao tác phải bất đồng bộ và có thử lại |
| Google Sheets | Phản chiếu nguồn sự thật để đối soát. Bản xuất **giữ lại** dòng đã xoá mềm kèm dấu `deleted_at` — không dịch dòng, vì dịch dòng làm mọi tham chiếu theo số hàng sai |
| SMTP | Gửi mã xác thực, lời mời, nhắc hạn, thư phiếu hỗ trợ, cảnh báo. Cấu hình sai thì thư **không gửi được trong im lặng** |
| Cổng SMS | Kênh thứ hai cho mã xác thực |
| Prometheus / Grafana / Loki | Quan trắc. **Cảnh báo sống ở Grafana**, không có thành phần quản lý cảnh báo riêng — quyết định hợp với quy mô một máy chủ |
| Ứng dụng bên thứ ba | Gọi API bằng khoá (lưu dạng băm), phạm vi theo khoá; nhận sự kiện qua webhook có ký |
| **Cổng thanh toán** | **Không có.** Hệ thống đo và ghi nhận mức sử dụng nhưng **không thu tiền** |

---

## 4.5 Chuẩn mã nguồn và quy ước phát triển

### 4.5.1 Kiến trúc và tổ chức mã

```
backend/app/
  routers/        27 tệp — 25 được mount, 214 điểm cuối HTTP gọi được
  storage/        tầng truy cập dữ liệu; nơi ĐẶT ngữ cảnh tổ chức
  processing/     trích đặc trưng, cắt cửa sổ, tăng cường, chấm chất lượng
  sot/            công bố và xác minh nguồn sự thật
  training/       điều phối huấn luyện
frontend/src/
  pages/          hơn 30 màn hình
  components/     thành phần dùng lại
  i18n/           chuỗi hiển thị, không có chuỗi cứng trong mã
scripts/          công cụ vận hành: sao lưu, đối soát, kiểm độ tươi triển khai
```

**Một quy ước có ý nghĩa kiến trúc:** ngữ cảnh tổ chức được đặt ở **đúng một khối
quản lý ngữ cảnh** trong tầng truy cập dữ liệu. Không có đường nào khác đặt được
ngữ cảnh này. Đây là điều làm tầng cưỡng chế thứ ba khả thi — nếu mỗi hàm tự đặt
ngữ cảnh theo cách riêng, không ai bảo đảm được lệnh gán luôn giới hạn trong
phạm vi giao dịch.

### 4.5.2 Quy ước bắt buộc

| Quy ước | Nội dung | Vì sao |
|---|---|---|
| Cấu hình tách khỏi mã | Theo Twelve-Factor; đổi cấu hình **không cần dựng lại ảnh** | Ảnh container chống lưng cho năm dịch vụ |
| Không chuỗi cứng trong giao diện | Mọi chuỗi hiển thị đi qua lớp i18n | Đa ngôn ngữ là yêu cầu, không phải tính năng thêm |
| Không emoji trong giao diện | 70 biểu tượng SVG thống nhất | Emoji hiển thị khác nhau giữa hệ điều hành và không đổi màu theo chủ đề |
| Màu trạng thái thành công | **Xanh dương CTU**, không phải xanh lá | Hệ thiết kế của đơn vị |
| Khai báo mô hình trả về của API | **Bắt buộc** | Bỏ `response_model` = gỡ bộ lọc bảo mật; đã từng làm rò mã băm mật khẩu ra ngoài |
| Lệnh kiểm kiểu | `npm run typecheck`, **không** `npx tsc --noEmit` | Lệnh sau kiểm đúng không tệp nào và vẫn thoát 0 |
| Ký tự xuống dòng cho tệp `.sh` | Ép LF bằng `.gitattributes` | Quy ước Windows làm container giao diện chết trong vòng lặp |
| Chạy kiểm thử | Chỉ qua `scripts/run_tests.sh` | Đặt đúng CSDL đích, vai chạy, không gian bộ đệm |

### 4.5.3 Quy ước kiểm thử

Tỉ lệ mã kiểm thử trên mã dịch vụ là **0,68 : 1** (41.760 / 61.097 dòng, đếm
17/08/2026). Con số này là **hệ quả của một nguyên tắc**, không phải mục tiêu tự
đặt: mỗi khẳng định trung tâm phải có một phản chứng, nên phần lớn hợp đồng được
ghim bằng **hai** ca kiểm thử thay vì một.

**Năm dạng "đỏ giả" đã gặp** — ghi lại để không mất thời gian chẩn đoán lại; dạng
gần nhất là *thư mục làm việc trôi sang `frontend` → nạp nhầm tệp `.env` → mật
khẩu CSDL rỗng*, và dạng khó nhất là *stack biến mất giữa chừng*, cho 208 lỗi
trông y hệt một đợt hồi quy, phân định bằng thông điệp "host lookup failed".

### 4.5.4 Quản lý thay đổi cấu trúc dữ liệu

Hai loại thay đổi, **phải tách**:

| Loại | Chạy khi nào | Được làm gì |
|---|---|---|
| Bước tự động lúc khởi động | Mỗi lần dịch vụ khởi động | **Chỉ thêm**: tạo bảng còn thiếu, thêm cột còn thiếu |
| Lệnh di trú tường minh (`app.cli.migrate`) | Do người vận hành gọi | Mọi thay đổi **một chiều**: chuyển dữ liệu, bỏ bảng cũ, bỏ chỉ mục |

**Hai chốt chặn bắt buộc:**

1. **Chốt phiên bản hai chiều.** Backend **từ chối khởi động** khi phiên bản lược
   đồ không khớp — cả khi lược đồ cũ hơn lẫn khi mới hơn. Chiều thứ hai quan
   trọng không kém: một dịch vụ cũ chạy trên lược đồ mới sẽ ghi dữ liệu thiếu cột.
2. **Chốt đích đến.** Lệnh di trú bắt buộc khai `EXPECTED_DATABASE`. Chốt này
   sinh ra từ sự cố ngày 13/08/2026, khi biến `POSTGRES_DB` **không tham gia dựng
   chuỗi kết nối** và một lượt chạy đi nhầm vào cơ sở dữ liệu sản xuất.

**Kiểm nợ lược đồ: sau BA lần khởi động liên tiếp, phần chênh lệch cấu trúc phải
rỗng.** Ba lần chứ không phải một, vì có loại chênh lệch chỉ lộ ra ở lần thứ hai
hoặc thứ ba.

### 4.5.5 Cổng trước khi triển khai

Bốn bước, chạy theo thứ tự; bước nào đỏ thì dừng:

```
1. Bộ kiểm thử dịch vụ         → 0 đỏ, và sổ dấu vết báo 0 hàng còn sót
2. Bộ kiểm thử + kiểm kiểu giao diện (npm run typecheck)
3. Nợ lược đồ                  → rỗng sau BA lần khởi động liên tiếp
4. Kiểm chứng độ tươi triển khai
```

---

## 4.6 Ba giới hạn phạm vi được tuyên bố trước

Ba điểm dưới đây **không** phải khiếm khuyết phát hiện muộn; chúng được tuyên bố
ngay tại phần ràng buộc để các phần sau không phải biện minh:

1. **Phân quyền nhiều cấp mới cưỡng chế ở hai cấp.** Mô hình dữ liệu và kiến trúc
   phân quyền hỗ trợ một hệ phân cấp mở rộng được, nhưng cưỡng chế lúc chạy hiện
   chỉ chứng minh được ở cấp **hệ thống** và cấp **tổ chức**. Hai cấp bên dưới
   (không gian làm việc, dự án) có cấu trúc dữ liệu nhưng **chưa có bề mặt vận
   hành** — đối chiếu OpenAPI: không đường dẫn nào chứa hai khái niệm này.
2. **Cách ly phủ nửa đầu vòng đời dữ liệu.** Ranh giới tổ chức được cưỡng chế
   chặt trên đường thu nhận và quản lý mẫu. Nửa sau — huấn luyện và mô hình — mới
   ở mức kiến trúc đích, chưa cưỡng chế theo ranh giới tổ chức ở mọi đường.
3. **Thu hồi không viết lại quá khứ.** Rút đồng thuận loại dữ liệu khỏi mọi bản
   phát hành **sau đó**; nó không xoá dữ liệu khỏi lưu trữ và không thu hồi được
   giấy phép đã cấp cho bên thứ ba. Giao diện nói thẳng điều này, và **có kiểm
   thử ghim đúng câu chữ đó** — để một lần sửa giao diện về sau không vô tình
   biến một giới hạn thành một lời hứa.

---

## 4.7 Ba hạn chế kỹ thuật đã biết, chưa xử lý

| Hạn chế | Mô tả | Vì sao chưa xử lý |
|---|---|---|
| Tính lũy đẳng chưa đồng đều ở đường xử lý nền | Việc tạo tài nguyên và tải đối tượng lên kho ngoài **chưa** bảo đảm chạy lại nhiều lần cho cùng kết quả | Cần thiết kế lại khoá lũy đẳng cho bốn nhóm công việc nền; ngoài phạm vi học kỳ |
| Đơn điệu phiên bản của nguồn sự thật chưa cưỡng chế | Hệ thống chấp nhận bản công bố có số hiệu phiên bản **thấp hơn** bản đang dùng; nguyên tắc chỉ-điền bảo vệ tài nguyên mới, nhưng giá trị dùng chung **bị ghi đè lùi** | Đã ghi vào phần hạn chế và có bằng chứng đo |
| Cách ly ở mặt phẳng tệp yếu hơn mặt phẳng CSDL | Đường ghi tệp **không** chịu chính sách bảo mật mức hàng; cách ly dựa vào cấu trúc thư mục theo tổ chức cộng kiểm tra ở tầng ứng dụng | Hệ quả trực tiếp của RB-D2. Phát biểu phải nói đúng mức này, không được gộp chung với mức bảo đảm của CSDL |
