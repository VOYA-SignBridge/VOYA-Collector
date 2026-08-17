# CHƯƠNG 4: KIỂM THỬ VÀ ĐÁNH GIÁ

*Chương này kiểm chứng những gì Chương 3 khẳng định. Nó gồm hai phần có bản chất
khác nhau và **không được lẫn**: phần kiểm thử trả lời câu "thay đổi có phá thứ
đang chạy không", phần đo lường trả lời câu "tỉ lệ vi phạm là bao nhiêu, độ trễ
là bao nhiêu". Bộ kiểm thử là lưới an toàn khi phát triển; chỉ phần đo lường mới
lên bảng kết quả của luận văn.*

---

## 1. Mục tiêu kiểm thử

Đối tượng đánh giá của đề tài là **hạ tầng**, không phải mô hình học máy. Điều
này quyết định toàn bộ cách đánh giá, nên phải nói rõ trước.

Một con số độ chính xác nhận dạng cao trên bộ dữ liệu hiện tại sẽ **nói về bộ dữ
liệu chứ không nói về hệ thống**: 64 % dữ liệu thuộc nhóm bảng chữ cái, và một mô
hình học tốt trên phân bố lệch như vậy không chứng minh được điều gì về hạ tầng
đã xây. Ngược lại, câu hỏi *"một tổ chức có đọc được dữ liệu của tổ chức khác
không"* là câu hỏi về hạ tầng, và trả lời được bằng một con số.

Bốn mục tiêu kiểm thử, tương ứng bốn trục đánh giá:

| Trục | Câu hỏi | Phương pháp |
|---|---|---|
| **T1 — Chức năng** | Các nghiệp vụ có chạy đúng đặc tả không, và thay đổi có gây hồi quy không? | Bộ kiểm thử tự động, hai nền chạy |
| **T2 — Cách ly** | Tỉ lệ vi phạm ranh giới tổ chức là bao nhiêu? | Đo đối kháng qua API, có đối chứng dương |
| **T3 — Hiệu quả lưu trữ** | Biểu diễn điểm mốc giảm được bao nhiêu dung lượng? | Đo ghép cặp khớp thời lượng trên nguồn video ngoài |
| **T4 — Toàn vẹn nguồn sự thật** | Cơ chế ký số chặn được những dạng giả mạo nào? | Ma trận kịch bản giả mạo |

Trục T2 là trục trung tâm, vì nó kiểm chứng đóng góp lõi của luận văn.

**Một trục cố ý không có:** cách ly hiệu năng. Hệ thống có hạn mức và giới hạn
tần suất, nhưng hai thứ đó **không chứng minh** được rằng một tổ chức không làm
chậm tổ chức khác. Muốn khẳng định điều đó phải có thí nghiệm tải riêng — tạo tải
ở tổ chức A rồi quan sát độ trễ ở tổ chức B. Luận văn không làm việc đó, và phép
đo độ trễ ở §5.3 **không được trích dẫn như thể có làm**.

### 1.1 Nguyên lý nền tảng: phép đo phải có khả năng thất bại

Nguyên lý này chi phối toàn bộ chương và đáng phát biểu tường minh:

> **Một phép đo không thể thất bại thì không đo gì cả.**

Ví dụ điển hình đã xảy ra trong chính đề tài này. Lượt đo cách ly ngày 15/08/2026
cho kết quả đẹp: 630 lần thử đối kháng, không lần nào vượt được ranh giới. Nhưng
lượt đo ấy đã bị **loại khỏi phân tích**, vì đối chứng dương không đạt: tài khoản
thử nghiệm **không đọc được cả dữ liệu của chính nó** — trả về mã 404 cho tài
nguyên mà nó sở hữu.

Khi đó, mọi kết quả "đã bị chặn" trở nên vô nghĩa, vì chúng tương thích với hai
giả thuyết mà phép đo không phân biệt được:

* cách ly đang hoạt động đúng, hoặc
* tài khoản ấy vốn không đọc được gì cả.

Nguyên nhân kỹ thuật: đường đọc lớp và mẫu không thuần cơ sở dữ liệu — nó đọc cả
tệp trên đĩa — trong khi dữ liệu gieo chỉ nằm trong cơ sở dữ liệu, và container
đo không gắn cây dữ liệu nào.

Bài học rút ra và áp cho mọi phép đo sau đó: **đối chứng dương là điều kiện tiên
quyết, không phải phần bổ sung cho đủ bộ.** Và đối chứng dương phải phủ **cả vế
ghi**, không chỉ vế đọc — nếu tài khoản thử vốn không xoá được bất cứ thứ gì, thì
"không xoá được dữ liệu của bên kia" không nói gì về ranh giới tổ chức.

---

## 2. Kế hoạch kiểm thử

### 2.1 Các chức năng được kiểm thử

*Bảng 4-1: Các chức năng được kiểm thử*

| Nhóm | Nội dung kiểm | Số tệp kiểm thử |
|---|---|:--:|
| Cách ly tổ chức và lược đồ | Chính sách bảo mật mức hàng; vai chạy không vượt được chính sách; khoá ngoại mang định danh tổ chức; hình dạng và tiến hoá lược đồ | 9 |
| Xác thực, quyền, cổng truy cập | Cổng mặc định từ chối; giới hạn tần suất; vòng đời phiên và cookie; mã một lần; đặt lại mật khẩu; nâng quyền tạm thời; nhật ký kiểm toán; địa chỉ IP thật | 12 |
| Pháp lý và chấp thuận | Chấp thuận ghi đúng phiên bản; tính bất biến của bản đã công bố; kho lưu văn bản; vòng đời bản thảo; ghi bù chấp thuận | 6 |
| Mặt phẳng thương mại | Gói cước và hạn mức; vòng đời tổ chức; xuất và dọn dữ liệu; khoá API và webhook | 6 |
| Dữ liệu, xử lý, huấn luyện | Luồng tải lên và trích đặc trưng; chỉ số chất lượng; không gian toạ độ; tăng cường; chia tập không trùng người ký; vòng đời huấn luyện; ba mặt phẳng danh mục | 15 |
| Nguồn sự thật | Khoá ký, bản kê, đồng bộ, lược đồ, tích hợp thật với kho ngoài | 10 |
| Vận hành | Nhật ký có cấu trúc; ngưỡng đĩa; khởi động và di trú; đồng bộ đầu vòng đời | 8 |
| Giao diện | Điều hướng, biểu mẫu, trạng thái tải, đa ngôn ngữ, quyền hiển thị | 42 |

**Ba nhóm kiểm thử đáng nêu riêng**, vì chúng kiểm những thứ mà kiểm thử chức năng
thông thường không chạm tới:

* **Kiểm thử phân quyền ở tầng cơ sở dữ liệu.** Không kiểm "API có trả 403
  không", mà kiểm trực tiếp: một lệnh xoá không điều kiện chỉ chạm được dữ liệu
  của tổ chức hiện tại; mệnh đề kiểm ghi chặn được việc ghi sang tổ chức khác;
  vai chạy của ứng dụng **không có** quyền vượt chính sách.
* **Kiểm thử bằng phân tích cú pháp mã nguồn.** Một kiểm thử quét cây cú pháp để
  bảo đảm mọi sự kiện webhook được khai báo đều có chỗ phát thật — bắt được lớp
  lỗi "khai báo mà quên nối dây", thứ không kiểm thử hành vi nào bắt được.
* **Kiểm thử ghim câu chữ.** Giới hạn "thu hồi không xoá khỏi lưu trữ" được ghim
  bằng một kiểm thử trên nội dung hiển thị, để một lần sửa giao diện về sau không
  vô tình biến giới hạn thành lời hứa.

### 2.2 Cách tiếp cận

**Bốn nguyên tắc viết kiểm thử** được giữ nhất quán:

1. **Một kiểm thử, một hành vi.** Tên kiểm thử nói ra hợp đồng, không nói ra thao
   tác. `test_query_without_tenant_returns_zero_rows` nói được hợp đồng;
   `test_samples` thì không.
2. **Dễ đọc hơn là không lặp.** Kiểm thử được phép lặp lại phần dựng dữ liệu, vì
   một kiểm thử phải đọc hiểu được **một mình**, không cần lần theo ba lớp hàm
   trợ giúp. Ngoại lệ duy nhất ưu tiên không lặp là phần dọn dẹp.
3. **Không có logic trong kiểm thử.** Một điều kiện rẽ nhánh trong kiểm thử nghĩa
   là kiểm thử ấy đang kiểm hai thứ, và khi nó đỏ thì không biết thứ nào hỏng.
4. **Mỗi khẳng định trung tâm có một phản chứng.** Kiểm thử "chủ sở hữu đọc được"
   phải đi kèm kiểm thử "người khác không đọc được". Một mình vế đầu không phân
   biệt được hệ thống đúng với hệ thống mở toang.

**Kiểm thử tự dọn thứ mình tạo, không xoá sạch bảng.** Lý do rất cụ thể: bộ kiểm
thử chạy trên **bản sao của cơ sở dữ liệu sản xuất**, không phải cơ sở dữ liệu
rỗng — xoá sạch bảng sẽ xoá dữ liệu đối chứng của các kiểm thử khác và tạo ra một
chuỗi đỏ không liên quan tới thay đổi vừa thực hiện.

**Bốn mức kiểm thử:**

| Mức | Kiểm gì | Ví dụ |
|---|---|---|
| Đơn vị | Một hàm thuần | Phép chuẩn hoá toạ độ, phép tăng cường |
| Tích hợp | Nhiều thành phần thật, cơ sở dữ liệu thật | Luồng đăng ký, luồng tải lên |
| Hệ thống | Qua API công khai, như người dùng | Cổng truy cập, luồng huấn luyện |
| Đo lường | Không phải kiểm thử — xem §5.2–§5.5 | Đo đối kháng, đo độ trễ |

### 2.3 Tiêu chí đánh giá kiểm thử thành công / thất bại

*Bảng 4-2: Tiêu chí đạt / không đạt*

| Hạng mục | Đạt khi | Không đạt khi |
|---|---|---|
| Bộ kiểm thử hồi quy | 0 kiểm thử đỏ trên **cả hai** nền chạy | Bất kỳ kiểm thử đỏ nào không giải thích được bằng nguyên nhân ngoài mã |
| Kiểm kiểu giao diện | Lệnh kiểm kiểu của dự án thoát 0 | Có lỗi kiểu |
| Nợ lược đồ | Rỗng sau **ba** lần khởi động liên tiếp | Còn chênh lệch cấu trúc |
| Độ phủ đa ngôn ngữ | Không còn chuỗi cứng theo công cụ đo | Còn chuỗi cứng |
| Đo cách ly (T2) | Tỉ lệ vi phạm = 0 **và** không còn ca không kết luận được **và** đối chứng dương đạt cả đọc lẫn ghi | Thiếu bất kỳ điều kiện nào trong ba điều kiện trên |
| Đo lưu trữ (T3) | Tỉ lệ giảm > 90 % trên trung vị và trên tổng, cỡ mẫu đạt ngưỡng phát hiện | Cỡ mẫu dưới ngưỡng, hoặc nguồn so sánh không khớp thời lượng |
| Đo toàn vẹn (T4) | Mọi kịch bản cho kết quả **xác định** | Có kịch bản không cho kết quả xác định |

**Phân biệt bắt buộc: "phép đo hợp lệ" khác "thuộc tính đạt".** Ở trục T4, chín
kịch bản đều cho kết quả xác định — phép đo **hợp lệ ở cả chín**. Nhưng thuộc
tính bảo mật chỉ đạt ở tám; kịch bản thứ chín phát hiện một giới hạn thật. Báo
cáo "9/9 đạt" là báo cáo sai, và đó là dạng sai dễ mắc nhất khi gộp hai khái niệm
này.

### 2.4 Tiêu chí đình chỉ và yêu cầu bắt đầu lại

**Đình chỉ lượt chạy khi** một trong các điều kiện sau xảy ra — vì tiếp tục chạy
chỉ sinh thêm kết quả không dùng được:

| Điều kiện | Dấu hiệu nhận biết |
|---|---|
| Hạ tầng biến mất giữa chừng | Hàng loạt lỗi "không phân giải được tên máy chủ" |
| Đĩa đầy | Lỗi ghi tệp ở các kiểm thử đồng bộ, lan sang nhóm không liên quan |
| Ảnh kiểm thử cũ hơn khai báo phụ thuộc | Suite chết ngay ở bước thu thập kiểm thử |
| Sửa tệp mã nguồn **trong lúc** suite đang chạy | Kết quả trộn giữa hai phiên bản mã |
| Bộ đếm giới hạn tần suất dùng chung với ứng dụng đang chạy | Một tệp bắt đầu trả mã 429 từ kiểm thử thứ N |
| **Một ca kiểm thử tích hợp treo chờ mạng ngoài** | Lượt chạy **đứng yên** ở một tỉ lệ phần trăm; **CPU của container gần bằng 0**; bên trong container có một kết nối HTTPS đang mở ra ngoài |

**Bắt đầu lại khi:** nguyên nhân đình chỉ đã được xử lý, và lượt chạy mới bắt đầu
từ đầu — **không** chạy tiếp phần còn lại. Với phép đo, yêu cầu chặt hơn: phép đo
phải gắn với **một phiên bản mã xác định**, nên mọi thay đổi mã trong lúc đo đều
làm lượt đo đó mất hiệu lực.

**Một quy tắc riêng cho phép đo: phát hiện trong lúc đo thì ghi lại, không sửa
ngay.** Nếu phép đo lộ ra một lỗi, đó là một **phát hiện của phép đo** — sửa lỗi
rồi đo lại trong cùng một lượt sẽ làm mất bằng chứng và làm kết quả không quy về
phiên bản mã nào cả.

### 2.5 Sản phẩm bàn giao kiểm thử

*Bảng 4-3: Sản phẩm bàn giao kiểm thử*

| Sản phẩm | Nội dung | Nơi lưu |
|---|---|---|
| Bộ kiểm thử tự động | 151 tệp, 41.760 dòng mã kiểm thử | `backend/tests/`, `frontend/src/**/__tests__/` |
| Sổ dấu vết lượt chạy | Ảnh chụp trạng thái đầu lượt, số kiểm thử, số bỏ qua, nguyên nhân | Tạo tự động mỗi lượt chạy |
| Tài liệu quy trình kiểm thử | Cách chạy, chuẩn viết, danh mục kiểm thử, các dạng "đỏ giả" | `docs/08-testing/TESTING.md` |
| Artefact phép đo cách ly | Dữ liệu thô từng lượt gọi, kèm mã trả về và ngữ cảnh | `MEASUREMENT_cross_store_isolation_raw.json` |
| Artefact phép đo độ trễ | Ba lượt chạy độc lập giữ riêng | `MEASUREMENT_api_latency.json` |
| Artefact phép đo lưu trữ | Thống kê từng tệp và từng cặp ghép | `MEASUREMENT_storage_efficiency.json` |
| Artefact ma trận toàn vẹn | Thông báo từ chối nguyên văn của từng kịch bản | `MEASUREMENT_sot_integrity.json` |
| Cổng trước triển khai | Bốn bước bắt buộc chạy trước mỗi lần triển khai | `docs/08-testing/TESTING.md` §7 |

---

## 3. Quản lý kiểm thử

### 3.1 Các hoạt động được lập kế hoạch

| Giai đoạn | Hoạt động | Kết quả |
|---|---|---|
| Trong lúc phát triển | Chạy tệp kiểm thử liên quan tới phần đang sửa | Phản hồi nhanh |
| Trước khi hợp nhất thay đổi | Chạy toàn bộ suite trên bản sao sản xuất | Không hồi quy trên dữ liệu thật |
| Định kỳ | Chạy toàn bộ suite trên cơ sở dữ liệu dựng từ số không | Mã chạy được trên máy mới |
| Trước khi triển khai | Bốn cổng: kiểm thử dịch vụ, kiểm thử + kiểm kiểu giao diện, nợ lược đồ, độ tươi triển khai | Điều kiện để triển khai |
| Giai đoạn đánh giá | Bốn phép đo T1–T4, mỗi phép đo một lượt riêng, cây mã đóng băng | Số liệu cho Chương 4 |

### 3.2 Môi trường kiểm thử

**Hai nền chạy, và chúng trả lời hai câu khác nhau.** Phân biệt này quan trọng vì
gộp hai nền lại sẽ mất một trong hai câu trả lời.

*Bảng 4-4: Môi trường kiểm thử*

| | Nền 1 — bản sao sản xuất | Nền 2 — dựng từ số không |
|---|---|---|
| Trả lời câu | Thay đổi có phá **dữ liệu thật** không? | Mã có chạy trên một **máy mới** không? |
| Cơ sở dữ liệu | Bản sao của cơ sở dữ liệu sản xuất | Cơ sở dữ liệu trống, dựng bằng lệnh di trú |
| Lượt chạy sạch gần nhất | **2.528 xanh / 0 đỏ / 1 bỏ qua** (17/08/2026, 22 ph 14 s) | **1.681 xanh / 0 đỏ / 15 bỏ qua** (14/08/2026) |
| Chênh lệch 15 kiểm thử | — | Là **bỏ qua**, không phải đỏ: chủ yếu là kiểm thử trích đặc trưng từ video, cần kho clip 2,7 GB không có trên nền này |
| **Quy mô thu thập, 17/08/2026** | **2.528 ca** | — |

**Về con số 2.529.** Đây là số ca pytest **thu thập được**, khác hẳn con số hay
bị nhầm với nó: **1.987** là số *hàm* kiểm thử đếm tĩnh trong 151 tệp. Chênh lệch
là do tham số hoá — một hàm sinh nhiều ca. Chỉ con số của **lượt chạy thật** mới
được viết vào quyển, và phải kèm ngày.

**Đường đi tới con số xanh ấy là phần đáng đọc hơn chính con số** — xem §6.4.

Nền thứ hai chứng minh giá trị của nó ngay lần chạy đầu: **22 kiểm thử đỏ**, và
**không cái nào là lỗi của kiểm thử**. Bước dựng lược đồ tự động khi khởi động
tạo ra một lược đồ **thiếu 2 bảng, 7 khoá ngoại và 14 cột** so với máy đang chạy
— nghĩa là **mọi máy triển khai mới đều nhận một lược đồ yếu hơn, trong im lặng**.
Đây là loại lỗi mà nền thứ nhất không bao giờ phát hiện được, vì nó chạy trên một
cơ sở dữ liệu đã có sẵn cấu trúc đúng.

**Cấu hình kỹ thuật bắt buộc**, mỗi mục có lý do:

| Cấu hình | Vì sao bắt buộc |
|---|---|
| Ảnh container kiểm thử riêng | Ảnh sản xuất **không có** bộ chạy kiểm thử |
| Chạy trên mạng nội bộ của các dịch vụ | Tên máy chủ của cơ sở dữ liệu và hàng đợi chỉ phân giải được bên trong mạng đó |
| Không gian bộ đệm riêng cho kiểm thử | Dùng chung với ứng dụng đang chạy làm bộ đếm giới hạn tần suất trôi qua các lượt, và một tệp sẽ bắt đầu bị từ chối từ kiểm thử thứ N |
| Chạy dưới **vai ứng dụng**, không phải vai quản trị | Vai siêu người dùng được cơ sở dữ liệu miễn trừ chính sách bảo mật **vô điều kiện** — chạy kiểm thử cách ly dưới vai đó sẽ cho kết quả "đạt" giả |
| Cấp quyền tường minh trên nền thứ hai | Cơ sở dữ liệu không tự cấp quyền cho vai khác trên bảng mới; thiếu bước này sinh **41 lỗi ở 3 tệp**, tất cả là lỗi từ chối quyền, một thông báo trỏ nhầm vào mã ứng dụng |

> ### ▣ HÌNH 4-1 — Hai nền chạy kiểm thử
> **Phải thể hiện:** hai nền đặt cạnh nhau; câu hỏi mỗi nền trả lời; nguồn dữ
> liệu khác nhau; **mũi tên chỉ ra 22 lỗi mà chỉ nền 2 bắt được**.
> **Chú thích:** *Hình 4-1: Hai nền chạy kiểm thử và câu hỏi mỗi nền trả lời.*

**Môi trường đo tách khỏi môi trường kiểm thử.** Phép đo độ trễ chạy trên một
container **riêng**, không phải container dùng cho phép đo cách ly. Lý do: hai
phép đo đặt hệ thống ở hai trạng thái khác nhau — phép đo cách ly gieo hàng nghìn
bản ghi và gắn cây dữ liệu, còn phép đo độ trễ cần một cây dữ liệu rỗng. Dùng
chung một container sẽ **dịch chuyển cả phân bố độ trễ** trong khi bảng kết quả
vẫn trông bình thường.

### 3.3 Giao tiếp giữa các nhóm liên quan

Đề tài do một người thực hiện, nên "giao tiếp giữa các nhóm" ở đây là giao tiếp
giữa các vai trò mà một người đảm nhiệm ở các thời điểm khác nhau — và nó vẫn cần
cơ chế, vì trí nhớ không phải cơ chế:

| Kênh | Nội dung | Chu kỳ |
|---|---|---|
| Sổ dấu vết lượt chạy | Trạng thái đầu lượt, kết quả, nguyên nhân bỏ qua | Mỗi lượt chạy |
| Sổ vấn đề đã biết | Lỗi đã phát hiện, chưa xử lý, kèm lý do hoãn | Cập nhật khi phát hiện |
| Cảnh báo qua thư | Sự cố hạ tầng, tác vụ nền thất bại | Tự động |
| Ghi chú phép đo | Điều kiện đo, phiên bản mã, giới hạn phải nêu kèm | Mỗi phép đo |

Nguyên tắc: **cảnh báo phải tới được con người**. Một cảnh báo chỉ hiện trên biểu
đồ mà không ai mở là một cảnh báo không tồn tại. Một bẫy cụ thể đã gặp: nội dung
thư của kênh cảnh báo là **văn bản thuần**, và đánh dấu định dạng bị chuyển thành
ký tự thoát — thư vẫn gửi, chỉ có điều không đọc được.

### 3.4 Tài nguyên và sự cấp phát

| Tài nguyên | Cấu hình | Ghi chú |
|---|---|---|
| Máy chạy kiểm thử | Cùng máy chủ triển khai: 6 nhân, 12 GB RAM, 1 GPU | Ràng buộc RB-T1 |
| Cơ sở dữ liệu kiểm thử | Hai cơ sở dữ liệu tách biệt trên cùng máy chủ | Không được trỏ vào cơ sở dữ liệu sản xuất |
| Kho video đối chứng | 2,7 GB clip thật | Chỉ có trên máy phát triển; nền thứ hai bỏ qua các kiểm thử cần nó |
| Thời gian một lượt chạy đầy đủ | Khoảng 20–30 phút cho phần dịch vụ | Không chạy trong lúc đang sửa mã |

**Một chốt chặn bắt buộc, sinh ra từ sự cố thật.** Ngày 13/08/2026, bộ kiểm thử
chạy nhầm vào **cơ sở dữ liệu sản xuất**: nó áp một phiên bản lược đồ đang làm dở
lên dữ liệu thật và đóng dấu phiên bản đó. Nguyên nhân: biến cấu hình tên cơ sở
dữ liệu **không tham gia dựng chuỗi kết nối**, nên đặt đúng biến đó vẫn không đổi
được đích đến. Đã bổ sung hai lớp chặn, và mọi lượt chạy phải đi qua kịch bản
khởi chạy chuẩn thay vì gọi trực tiếp.

### 3.5 Huấn luyện

Người thực hiện đề tài đã nắm sẵn các công cụ được dùng. Phần cần học trong quá
trình làm, ghi lại vì nó là kiến thức không có trong tài liệu chính thức:

* Hành vi của chính sách bảo mật mức hàng khi kết hợp với bể kết nối — nguồn của
  tầng 3 trong thiết kế cách ly.
* Cách phân biệt "đỏ thật" với "đỏ giả" — sáu dạng đã ghi nhận, xem §3.6.
* Nguyên tắc thiết kế phép đo có đối chứng dương — học từ chính lượt đo bị loại.

### 3.6 Các rủi ro

*Bảng 4-5: Rủi ro kiểm thử*

| # | Rủi ro | Dấu hiệu | Mức | Cách xử lý |
|---|---|---|---|---|
| R1 | **Đỏ giả do hạ tầng** — hạ tầng biến mất giữa lượt chạy | Hàng loạt lỗi "không phân giải được tên máy chủ"; đã gặp ở mức **208 lỗi** trông y hệt một hồi quy lớn | Cao | Phân định bằng dạng thông báo lỗi trước khi điều tra mã |
| R2 | **Đỏ giả do đĩa đầy** | Kiểm thử đồng bộ đỏ, lan sang nhóm không liên quan | Trung bình | Ngưỡng cảnh báo dung lượng đĩa |
| R3 | **Đỏ giả do môi trường** — thư mục làm việc trôi, nạp nhầm tệp cấu hình | Mật khẩu cơ sở dữ liệu rỗng | Trung bình | Dùng đường dẫn tuyệt đối cho tệp cấu hình |
| R4 | **Đỏ giả do bộ đếm dùng chung** | Một tệp bắt đầu bị từ chối từ kiểm thử thứ N | Trung bình | Không gian bộ đệm riêng |
| R5 | **Xanh giả do chạy sai vai** | Kiểm thử cách ly "đạt" trong khi vai chạy được miễn trừ chính sách | **Cao** | Kiểm vai chạy như một điều kiện tiên quyết của lượt chạy |
| R6 | **Kiểm thử ghi vào dữ liệu thật** | Kiểm thử ghi vào tệp nguồn sự thật thật của kho mẫu | **Cao** | Chốt chặn đích đến; bản sao cơ sở dữ liệu **không** che được đường ghi tệp |
| R7 | **Phép đo không có khả năng thất bại** | Kết quả đẹp nhưng đối chứng dương không đạt | **Cao** | Đối chứng dương là điều kiện tiên quyết, phủ cả đọc lẫn ghi |
| R8 | **Số kiểm thử đếm tĩnh nhầm thành số kiểm thử đã chạy** | Báo cáo "1.987 kiểm thử xanh" khi chưa chạy | Trung bình | Chỉ chép số từ lượt chạy thật, kèm số bỏ qua |

Rủi ro R8 đáng nói riêng vì nó là một cái bẫy khi viết luận văn, và ở đề tài này
có tới **ba** con số dễ bị dùng lẫn cho nhau. Đo lại toàn bộ ngày 17/08/2026:

| Con số | Giá trị | Nó là gì |
|---|---|---|
| Hàm kiểm thử, đếm tĩnh | **1.987** trong 151 tệp (dịch vụ) · **429** trong 58 tệp (giao diện) | Số **hàm** trong mã nguồn |
| Ca thu thập được | **2.528** | Số **ca** pytest dựng ra — tham số hoá làm một hàm sinh nhiều ca |
| Ca chạy xanh | **1.696** (14/08/2026) | Số ca của một **lượt chạy thật** |

Chỉ dòng thứ ba được phép viết là "kiểm thử xanh", và phải kèm ngày cùng số bỏ
qua. Hai dòng trên là số của mã nguồn, không phải số của một lượt chạy: một hàm
tham số hoá sinh nhiều ca, còn một hàm bị bỏ qua vẫn được đếm.

---

## 4. Kịch bản kiểm thử

*Bảng 4-6: Kịch bản kiểm thử*

| Mã | Kịch bản | Mục tiêu | Trục |
|---|---|---|---|
| KB01 | Vòng đời tài khoản đầy đủ | Đăng ký → xác thực địa chỉ → chấp thuận văn bản → đăng nhập → bật hai yếu tố → đăng xuất → khôi phục | T1 |
| KB02 | Vòng đời một mẫu dữ liệu | Đăng ký lớp → thu mẫu → xử lý nền → xem chi tiết → xoá mềm → khôi phục → xoá hẳn | T1 |
| KB03 | Vòng đời một tổ chức | Tạo tổ chức → sao chép danh mục → mời thành viên → đổi vai → gỡ thành viên → xuất dữ liệu → dọn sạch | T1 |
| KB04 | Vòng đời huấn luyện | Chọn phạm vi → ba cổng chặn → xếp hàng → chạy → đánh giá → thăng hạng → nhận dạng | T1 |
| KB05 | Vòng đời văn bản pháp lý | Soạn thảo → duyệt → công bố (có nâng quyền) → buộc chấp thuận lại → rút đồng thuận | T1 |
| **KB06** | **Đối kháng xuyên tổ chức** | Tài khoản của tổ chức A thử đọc, sửa, xoá tài nguyên của tổ chức B qua API công khai | **T2** |
| **KB07** | **Đối kháng trái quyền** | Tài khoản vai thấp thử thao tác đòi vai cao, trong **chính tổ chức mình** | **T2** |
| **KB08** | **Đối chứng dương** | Chủ sở hữu đọc **và ghi** được tài nguyên của chính mình | **T2** |
| KB09 | Đo độ trễ cơ sở | Sáu điểm cuối chính, không tranh chấp | T3 |
| KB10 | Đo hiệu quả lưu trữ | Ghép cặp video ↔ điểm mốc, khớp thời lượng | T3 |
| **KB11** | **Giả mạo nguồn sự thật** | Chín dạng giả mạo, chạy qua đúng đường tiêu thụ của ứng dụng | **T4** |
| KB12 | Khởi động trên máy sạch | Dựng lược đồ từ số không, phát hiện nợ lược đồ | T1 |
| KB13 | Diễn tập khôi phục sao lưu | Kết xuất → kiểm toàn vẹn → khôi phục vào cơ sở dữ liệu tạm | T1 |
| KB14 | Phát hiện triển khai lệch mã | Ba kiểu lệch giữa mã đang chạy và mã nguồn | T1 |

KB06, KB07 và KB08 phải chạy **cùng một lượt** trên **cùng một bộ dữ liệu gieo**.
Tách ra là mất khả năng quy kết: chỉ hiệu số giữa "làm được của mình" (KB08) và
"không làm được của bên kia" (KB06) mới quy được cho ranh giới tổ chức.

---

## 5. Các trường hợp kiểm thử

### 5.1 Kiểm thử chức năng

Phần này trình bày các ca kiểm thử **đại diện** cho từng nghiệp vụ. **Bộ ca kiểm
thử đầy đủ nằm ở Phụ lục D.**

*Bảng 4-7: Ca kiểm thử Nghiệp vụ 1 — Danh tính và quyền truy cập*

| Mã | Tiền điều kiện | Dữ liệu vào | Kết quả mong đợi | KQ |
|---|---|---|---|:--:|
| TC101 | Chưa có tài khoản | Thông tin hợp lệ, **không** chấp thuận văn bản | Từ chối tạo tài khoản | Đạt |
| TC102 | Chưa có tài khoản | Thông tin hợp lệ, có chấp thuận | Tạo tài khoản, ghi chấp thuận trỏ đúng phiên bản | Đạt |
| TC103 | Có tài khoản | Tên đăng nhập **không tồn tại** | Thông báo lỗi **giống hệt** trường hợp sai mật khẩu | Đạt |
| TC104 | Có tài khoản | Sai mật khẩu 6 lần liên tiếp | Từ chối theo cặp (tài khoản, IP); **người khác không khoá được tài khoản này** | Đạt |
| TC105 | Tài khoản bật hai yếu tố | Đúng mật khẩu | **Chưa** cấp phiên; yêu cầu yếu tố thứ hai | Đạt |
| TC106 | Tài khoản bật hai yếu tố | Mã sinh theo vector thử của tiêu chuẩn | Chấp nhận đúng theo tiêu chuẩn, không chỉ "đăng nhập được" | Đạt |
| TC107 | Đã đăng nhập, có văn bản mới buộc chấp thuận lại | Thử một thao tác ghi | Chặn ghi, điều hướng tới màn hình chấp thuận | Đạt |
| TC108 | Đã đăng nhập nhiều thiết bị | Đổi mật khẩu | **Mọi** phiên bị thu hồi | Đạt |
| TC109 | Bất kỳ | Yêu cầu đặt lại mật khẩu với tiêu đề máy chủ giả mạo | Liên kết chỉ trỏ tới máy chủ trong danh sách cho phép | Đạt |
| TC110 | Bất kỳ | Gọi một điểm cuối **không** khai báo công khai, không có phiên | Từ chối — mặc định từ chối ở tầng trung gian | Đạt |

*Bảng 4-8: Ca kiểm thử Nghiệp vụ 2 — Thu thập và quản lý dữ liệu mẫu*

| Mã | Tiền điều kiện | Dữ liệu vào | Kết quả mong đợi | KQ |
|---|---|---|---|:--:|
| TC201 | Có lớp, có đồng thuận, còn hạn mức | Chuỗi điểm mốc hợp lệ | Tạo một mẫu, trạng thái `pending`, trả mã tác vụ | Đạt |
| TC202 | Như trên | Chuỗi **không có bàn tay nào** | Từ chối lưu, nêu lý do | Đạt |
| TC203 | Lớp yêu cầu hai tay | Chuỗi chỉ có một tay | Cảnh báo trước khi lưu; yêu cầu đọc từ **siêu dữ liệu lớp** | Đạt |
| TC204 | Tổ chức đã chạm hạn mức | Chuỗi hợp lệ | Từ chối, nêu hạn mức gói | Đạt |
| TC205 | Tài khoản chưa có đồng thuận hiệu lực | Chuỗi hợp lệ | Chặn ghi, điều hướng chấp thuận | Đạt |
| TC206 | Tải lên tệp video | Tệp hợp lệ | **Bản thô được ghi trước** mọi bước chuẩn hoá | Đạt |
| TC207 | Tải lên nhiều tệp, một tệp sai định dạng | Lô hỗn hợp | Từ chối tệp sai, **các tệp còn lại vẫn tiếp tục** | Đạt |
| TC208 | Có mẫu ở trạng thái sẵn sàng | Xoá mẫu | Xoá mềm; mẫu xuất hiện trong thùng rác | Đạt |
| TC209 | Mẫu trong thùng rác | Khôi phục | Mẫu trở lại trạng thái sẵn sàng | Đạt |
| TC210 | Chuỗi trích được | So sánh chuẩn hoá ở đường webcam và đường video | Cho **cùng** không gian toạ độ | Đạt |

*Bảng 4-9: Ca kiểm thử Nghiệp vụ 3 — Danh mục từ vựng*

| Mã | Tiền điều kiện | Dữ liệu vào | Kết quả mong đợi | KQ |
|---|---|---|---|:--:|
| TC301 | Danh mục tổ chức có sẵn | Lớp mới, nhãn trùng nhưng **khác vùng miền** | **Chấp nhận** — vùng miền là một phần định danh lớp | Đạt |
| TC302 | Như trên | Lớp trùng hoàn toàn | Từ chối, chỉ ra lớp đang tồn tại | Đạt |
| TC303 | Tổ chức thiếu một phương ngữ | Truy vấn lớp theo phương ngữ đó | **Dừng** — không rơi ngược về danh mục cộng đồng | Đạt |
| TC304 | Tổ chức mới tạo | Sao chép danh mục | Danh mục được sao chép **một lần**; sửa về sau không lan ngược | Đạt |
| TC305 | Có phiên bản danh mục đã ghim | Danh mục thay đổi sau đó | Bộ dữ liệu ghim vẫn đọc được **nội dung cũ** | Đạt |
| TC306 | Thành viên không có vai biên tập | Thử thêm lớp | Từ chối | Đạt |

*Bảng 4-10: Ca kiểm thử Nghiệp vụ 4 — Huấn luyện và suy luận*

| Mã | Tiền điều kiện | Dữ liệu vào | Kết quả mong đợi | KQ |
|---|---|---|---|:--:|
| TC401 | Có lớp không đủ mẫu | Khởi động huấn luyện | Lớp bị loại **trước** khi đánh chỉ số lớp | Đạt |
| TC402 | Người ký chưa đồng ý mức nghiên cứu | Chuẩn bị bản phát hành nghiên cứu | Mẫu của người đó **không xuất hiện** trong bản phát hành | Đạt |
| TC403 | Sau khi lọc còn dưới ngưỡng lớp | Khởi động huấn luyện | Từ chối, **liệt kê từng lớp bị loại kèm lý do** | Đạt |
| TC404 | Có dữ liệu nhiều người ký | Chia tập | Cùng một người **không** nằm ở cả tập huấn luyện lẫn tập kiểm thử | Đạt |
| TC405 | Tác vụ đang chạy | Huỷ | Chuyển trạng thái huỷ, giải phóng tài nguyên | Đạt |
| TC406 | Tác vụ thất bại | — | **Thông báo tới chủ sở hữu tác vụ**, không chỉ ghi log | Đạt |
| TC407 | Có mô hình mới huấn luyện xong | Chưa thăng hạng | Đường nhận dạng vẫn phục vụ **mô hình đang phục vụ**, không phải mô hình mới nhất | Đạt |
| TC408 | Khách vãng lai | Dùng thử nhận dạng quá số phút cho phép trong ngày | Từ chối, nêu giới hạn | Đạt |

*Bảng 4-11: Ca kiểm thử Nghiệp vụ 5–6 — Tổ chức, gói cước và chính sách*

| Mã | Tiền điều kiện | Dữ liệu vào | Kết quả mong đợi | KQ |
|---|---|---|---|:--:|
| TC501 | Quản trị tổ chức | Mời một địa chỉ | Lời mời `pending`; **chưa** tạo tư cách thành viên | Đạt |
| TC502 | Có lời mời | Mở liên kết bằng tài khoản **địa chỉ khác** | Từ chối — lời mời gắn với địa chỉ | Đạt |
| TC503 | Gói có hạn mức không giới hạn | Ghi vượt mọi ngưỡng | Cho phép — giá trị rỗng nghĩa là không giới hạn | Đạt |
| TC504 | Tổ chức quá hạn thanh toán | Thử ghi dữ liệu | **Cho phép ghi** — trạng thái thương mại tách khỏi trạng thái quản trị | Đạt |
| TC505 | Quản trị nền tảng | Dọn sạch dữ liệu tổ chức **không** xác thực lại | Từ chối | Đạt |
| TC506 | Có bản đã công bố | Sửa nội dung dưới cùng số hiệu phiên bản | Từ chối **ở tầng cơ sở dữ liệu**, kể cả khi lệnh phát từ ứng dụng | Đạt |
| TC507 | Thực hiện một thao tác quản trị | — | Để lại bản ghi kiểm toán **bền vững**, đọc lại được qua API | Đạt |
| TC508 | Ghi kiểm toán **không có phạm vi** | — | **Từ chối ghi** — fail-closed | Đạt |

*Bảng 4-12: Ca kiểm thử cách ly ở tầng cơ sở dữ liệu*

| Mã | Tiền điều kiện | Dữ liệu vào | Kết quả mong đợi | KQ |
|---|---|---|---|:--:|
| TC601 | Hai tổ chức có dữ liệu | Truy vấn **không đặt ngữ cảnh tổ chức** | **0 hàng** — không phải mọi hàng | Đạt |
| TC602 | Ngữ cảnh = tổ chức A | Lệnh xoá **không điều kiện** trên bảng mẫu | Chỉ chạm dữ liệu của A | Đạt |
| TC603 | Ngữ cảnh = tổ chức A | Ghi một hàng mang định danh tổ chức B | Bị mệnh đề kiểm ghi chặn | Đạt |
| TC604 | — | Kiểm thuộc tính của vai chạy ứng dụng | **Không** có quyền vượt chính sách; **không** có quyền cấu trúc | Đạt |
| TC605 | Cùng một kết nối | Yêu cầu của tổ chức A rồi tới yêu cầu của tổ chức B | Ngữ cảnh **không rò** sang yêu cầu sau | Đạt |
| TC606 | Bảng chịu ranh giới tổ chức | Kiểm khoá ngoại | Mọi bảng đều có khoá ngoại mang định danh tổ chức | Đạt |

### 5.2 Trục T2 — Đo cách ly xuyên kho

Đây là phép đo trung tâm của luận văn. Nó khác bộ kiểm thử ở §5.1 về mục đích:
kiểm thử trả lời *"có hồi quy không"*, phép đo trả lời *"tỉ lệ vi phạm là bao
nhiêu"*.

**Giao thức.** Dựng hai tổ chức với dữ liệu thật trên **cả hai mặt phẳng lưu trữ**
— cơ sở dữ liệu và hệ tệp — rồi cho tài khoản của mỗi tổ chức thử đọc, sửa và xoá
tài nguyên qua **đúng API mà người dùng dùng**, tức đi qua toàn bộ chuỗi xác thực
→ phân giải tổ chức → phân quyền → truy vấn.

Bộ thử cố ý phát các lệnh **xoá** tổ chức, **xoá** mẫu và **xoá** lớp. Cả ba phải
bị chặn — và phép đo tồn tại chính vì điều đó chưa được chứng minh. Nếu cách ly
thủng, phép đo sẽ chứng minh bằng cách xoá thật.

*Bảng 4-15: Kết quả đo cách ly xuyên kho* — **17/08/2026**, ảnh chụp mã `P0B-…-4e9611`

| Chỉ số | Giá trị | Mẫu số | Nghĩa |
|---|---|---|---|
| Tỉ lệ vi phạm xuyên tổ chức | **0,0000** | 450 lượt kết luận được | Không một thao tác nào vượt được ranh giới tổ chức |
| Tỉ lệ thao tác trái quyền lọt | **0,0000** | 180 lượt | Không một thao tác nào vượt được cổng phân quyền |
| Tỉ lệ vi phạm gộp | **0,0000** | 630 lượt | Con số gộp duy nhất được phép công bố |
| **Ca không kết luận được** | **0** | — | **Điều kiện bắt buộc** để công bố ba con số trên |

Tổng 811 lượt gọi, chia ba nhóm đối kháng và một nhóm đối chứng:

| Nhóm | Câu hỏi | Lượt | Chặn | Vi phạm | Không kết luận được |
|---|---|:--:|:--:|:--:|:--:|
| A | Đúng tổ chức, **sai quyền** | 180 | 180 | 0 | 0 |
| B | Đúng quyền, **sai tổ chức** | 360 | 360 | 0 | 0 |
| C | Sai quyền **và** sai tổ chức | 90 | 90 | 0 | 0 |

Phân bố mã trả về trên toàn lượt: 200 (181 lượt — nhóm đối chứng dương), 403 (389),
401 (121), 404 (120). **Không có mã lỗi máy chủ nào** — một lỗi máy chủ sẽ làm ca
đó không kết luận được, vì "chặn vì cách ly" và "chặn vì hệ thống hỏng" là hai
việc khác nhau.

**Nhóm A không được gộp vào chỉ số xuyên tổ chức.** Nó nhắm vào tài nguyên của
chính tổ chức mình bằng một vai không đủ quyền, nên theo định nghĩa nó không thể
là vi phạm xuyên tổ chức — nó là vi phạm phân quyền, và đi vào chỉ số riêng. Gộp
lại sẽ làm chính cái tên của chỉ số nói sai.

**Bốn lớp bằng chứng.** Một con số bằng không chỉ có nghĩa khi cả bốn điều dưới
đây cùng đúng; thiếu bất kỳ lớp nào, con số ấy **tương thích với một hệ thống
hỏng**:

| Lớp | Nội dung | Kết quả |
|---|---|---|
| 1 — Đối chứng dương | Chủ sở hữu đọc được danh tính, phiên thu, dữ liệu mẫu của mình, **và xoá được mẫu của mình** | Đạt cả bốn |
| 2 — Đối kháng | Ba nhóm A, B, C như bảng trên | Đạt |
| 3 — Hậu điều kiện | Sau lượt đo, dữ liệu của bên bị nhắm **vẫn còn nguyên** trên cả cơ sở dữ liệu lẫn hệ tệp | Đạt — cả hai tổ chức còn đủ tenant, lớp và mẫu, kèm vân tay nội dung |
| 4 — Không có ca mờ | Mọi lượt gọi đều quy được về "chặn" hoặc "vi phạm" | Đạt — 0 ca |

**Lớp 1 là lớp quan trọng nhất, và vế ghi là bắt buộc chứ không phải cho đủ bộ.**
Nhóm đối kháng khẳng định bên A không sửa hay xoá được tài nguyên của bên B; nếu
bên A vốn không sửa hay xoá được bất cứ thứ gì — vì thiếu quyền, vì cổng chống
giả mạo yêu cầu, vì phiên chỉ đọc — thì "đã chặn" không nói gì về ranh giới tổ
chức. Chỉ **hiệu số** giữa "làm được của mình" và "không làm được của bên kia"
mới quy được cho ranh giới ấy.

**Ba giới hạn phải nêu kèm kết quả:**

1. Phép đo chạy trên **hai tổ chức**, không phải trên số tổ chức lớn. Nó chứng
   minh cơ chế hoạt động, không chứng minh cơ chế giữ được ở quy mô lớn.
2. Phép đo phủ **các tài nguyên có bề mặt API**. Hai cấp phạm vi dưới (không gian
   làm việc, dự án) không có bề mặt API nên **không có gì để đo** ở đó.
3. Phép đo là **đối kháng**, không phải chứng minh hình thức. Kết quả đúng là
   "trong 630 lượt thử theo giao thức này, không quan sát thấy vi phạm nào" —
   không phải "không thể có vi phạm". Phân biệt giữa *chưa quan sát thấy vi phạm*
   và *có cơ chế ngăn vi phạm* phải giữ rõ: lập luận cho vế thứ hai nằm ở thiết
   kế bốn tầng (Chương 3 §2.3.2), còn phép đo này cung cấp bằng chứng thực nghiệm
   cho vế thứ nhất.

> ### ▣ HÌNH 4-2 — Bốn lớp bằng chứng của phép đo cách ly
> **Phải thể hiện:** bốn lớp xếp chồng; cạnh mỗi lớp ghi **kết luận sẽ sai như
> thế nào nếu thiếu lớp đó**; ba nhóm đối kháng A/B/C vẽ thành ba mũi tên với
> đích khác nhau (tài nguyên của mình sai quyền / tài nguyên bên kia đúng quyền /
> cả hai sai).
> **Chú thích:** *Hình 4-2: Bốn lớp bằng chứng và vai trò của từng lớp.*

### 5.2bis Phép đo này gắn với phiên bản mã nào

Quy tắc 3 của phương pháp (Phụ lục E §1) đòi mọi phép đo phải gắn với **một phiên
bản mã xác định**. Mục này trả lời câu đó, và ghi lại cả chặng đường tới câu trả
lời — vì chặng đường ấy chứa hai bài học.

**Phiên bản đã đo.** Lượt đo ngày **17/08/2026** chạy trên một **ảnh chụp mã bất
biến**, không phải trên cây làm việc:

```
snapshot     P0B-20260817T011910-4e9611
tree_sha256  4e961192f079835b…
git HEAD     11a80c21ea2d
môi trường   signdb_test · vai voya_test_app · không siêu người dùng · không vượt chính sách
```

Ảnh chụp được gắn **chỉ đọc** đè lên thư mục mã của container đo, nên mã của lượt
đo **không đổi được kể từ thời điểm chụp** — kể cả khi cây làm việc bên dưới chạy
tiếp. Vân tay mã hiệu dụng được kiểm lại **lần thứ hai** ngay trước khi gieo dữ
liệu, đúng như giao thức đòi, và khớp.

Vì sao phải kiểm hai lần: vân tay lúc chụp chứng minh ảnh được dựng từ cây nào,
nhưng **không** chứng minh cây còn nguyên khi phép đo bắt đầu. Trong dự án này cây
đã đổi **ba lần giữa lúc đang đo** chỉ trong hai ngày.

**Lượt đo trước (16/08, commit `e5d804c`) đã bị thay thế.** Nó vẫn là một phép đo
hợp lệ của commit ấy, nhưng đường cưỡng chế đã được sửa tiếp sau đó — mười một
nơi gọi chuyển sang phạm vi tổ chức fail-closed, cộng hai tệp của tầng cưỡng chế
— nên con số của nó không mô tả mã sẽ nộp kèm quyển. Lượt 17/08 thay thế nó, và
là lượt được trích dẫn.

**Bài học 1 — artefact phải tự khai được phiên bản.** Artefact 16/08 ghi
`git_commit: null`: kịch bản đo cố lấy phiên bản từ biến môi trường rồi từ `git`,
cả hai đường cùng hụt trong container không có `.git`, và nó **ghi rỗng rồi chạy
tiếp**. Phiên bản chỉ còn truy được nhờ **thẻ của ảnh container** — một chỗ nằm
ngoài artefact và bị ghi đè bất cứ lúc nào. Quy tắc 3 khi ấy được tuân thủ trên
thực tế nhưng không ai đọc artefact mà kiểm lại được, tức trên thực tế nó không
còn là một quy tắc.

Nay cờ công bố có **hai vế**: hết ca không kết luận được, **và** xác định được
phiên bản mã. Áp ngược lên artefact 16/08 thì cờ trả về `False` — đó là câu trả
lời mà lượt ấy lẽ ra phải đưa ra.

**Bài học 2 — một cổng chặn nhầm là một cổng sẽ bị tắt.** Bản đầu của cổng ấy khoá
theo "cây làm việc có sạch không", và nó lập tức chặn một lượt đo hoàn toàn hợp
lệ chỉ vì trong kho có **một tệp markdown chưa theo dõi** — thứ không thể chạm
tới một byte nào của mã đang chạy. Cổng được sửa để ghim theo **ảnh chụp**, thứ
bất biến theo cấu trúc và phủ đúng những tệp tham gia hành vi; trạng thái sạch của
git chỉ còn là đường dự phòng cho trường hợp đo mã nung sẵn trong ảnh.

### 5.3 Trục T3a — Đo độ trễ dịch vụ

**Giao thức:**

```
Khởi động   50 lượt / điểm cuối / lượt chạy, KHÔNG tính vào thống kê
Đo          1.000 lượt / điểm cuối / lượt chạy
Đồng thời   1
Lặp lại     3 lượt chạy độc lập
Gộp         trung vị của BA giá trị phân vị, KHÔNG gộp 3.000 mẫu
```

Ba lượt được giữ **riêng** trong artefact. Gộp 3.000 mẫu lại sẽ giấu một lượt bất
thường: nếu lượt thứ hai chậm gấp đôi vì máy bận việc khác, tổng mẫu vẫn cho một
con số trông hợp lý và không ai biết. Ba giá trị đặt cạnh nhau thì bất thường tự
lộ, còn trung vị thì không bị một lượt hỏng kéo đi.

**Ngưỡng công bố phân vị.** Một phân vị chỉ có nghĩa khi đuôi của nó có đủ quan
sát đứng sau — yêu cầu tối thiểu **5 quan sát trong đuôi**: p95 cần ít nhất 100
lượt phục vụ, p99 cần ít nhất 500. Thiếu thì **để trống, không in**.

**Đồng thời = 1** vì đây là **độ trễ cơ sở**: nó trả lời "một yêu cầu tốn bao lâu
khi không có ai tranh chấp", **không** trả lời "hệ thống chịu được bao nhiêu yêu
cầu mỗi giây". Đây là giới hạn phải nêu kèm, không phải khiếm khuyết.

*Bảng 4-16: Kết quả đo độ trễ* — số liệu chi tiết ở `MEASUREMENT_api_latency.md`

Môi trường đo: container riêng, cùng ảnh với sản xuất, cơ sở dữ liệu kiểm thử,
cây dữ liệu rỗng, kết nối giữ sống, vai chạy **không** phải siêu người dùng,
trần giới hạn tần suất đã nâng cho môi trường đo.

> ### ▣ HÌNH 4-3 — Phân bố độ trễ theo điểm cuối
> **Loại:** biểu đồ cột nhóm hoặc biểu đồ hộp
> **Phải thể hiện:** p50, p95, p99 cho từng điểm cuối; **ba lượt chạy vẽ tách
> nhau**, không gộp — để người đọc thấy được tính ổn định giữa các lượt.
> **Chú thích:** *Hình 4-3: Phân bố độ trễ cơ sở theo điểm cuối, ba lượt chạy độc lập.*

### 5.4 Trục T3b — Đo hiệu quả lưu trữ

Đây là phép đo kiểm chứng cam kết *"giảm trên 90 % dung lượng mỗi mẫu so với
video thô"*.

**Một khó khăn phải nói thẳng: không đo ngược được trên chính dữ liệu của hệ
thống.** Kho dữ liệu có 8.784 tệp đặc trưng và **0 tệp video** — vì thiết kế đúng
như vậy: trình duyệt trích điểm mốc tại máy người dùng và chỉ gửi lên mảng số.
Video thô chưa bao giờ rời khỏi trình duyệt.

Đây **không phải thiếu sót của phép đo — nó là hệ quả trực tiếp của thiết kế**.
Chính cơ chế tạo ra hiệu quả lưu trữ cũng là cơ chế làm mất vật đối chứng. Nên
phép đo phải thực hiện trên **một nguồn video bên ngoài**, ghép cặp theo lớp và
khớp thời lượng.

*Bảng 4-17: Kết quả đo hiệu quả lưu trữ*

| Hạng mục | Giá trị |
|---|---|
| **Tỉ lệ giảm công bố** | **92,2 %** |
| Cỡ mẫu | 54 cặp khớp thời lượng, đạt ngưỡng phát hiện |
| Số tệp đặc trưng đo được | 3.871 tệp, tổng 146,0 MiB |
| Kích thước một mẫu — trung vị | 42,6 KiB |
| Kích thước một mẫu — p5 đến p95 | 14,1 – 82,8 KiB |
| Tham số thu để tái lập | 60 khung mục tiêu; 126 chiều mỗi khung |

**Phân bố rộng hơn nhiều so với một con số đơn lẻ gợi ý** — khoảng p5 tới p95
chênh nhau gần **sáu lần**. Nguyên nhân nằm ở chính định dạng lưu trữ: nó có nén,
và một chuỗi mà một bàn tay vắng mặt phần lớn thời gian gồm nhiều giá trị 0 liên
tiếp nên nén rất tốt. Báo cáo một con số trung bình mà không kèm khoảng phân bố
là báo cáo che mất đặc điểm này.

**Hai con số cao hơn đã bị loại, và lý do loại đáng giữ trong quyển**, vì nó
chứng minh vì sao 92,2 % là ước lượng được chọn: một con số 97,6 % hưởng lợi từ
việc so sánh với clip **dài hơn** (không khớp thời lượng), và một con số 95,5 %
hưởng lợi từ những mẫu mà quá trình trích xuất **thất bại** — tệp nhỏ vì trích
hỏng, không phải vì nén tốt.

**Sáu tệp xem trước do chính nền tảng sinh ra không dùng làm mốc được:** trung vị
28,9 KiB, **nhỏ hơn cả trung vị tệp đặc trưng**. Dùng chúng làm mốc "video thô"
cho kết luận ngược hẳn. Lý do hiển nhiên khi nhìn nội dung: khung xương vẽ trên
nền phẳng, gần như không có kết cấu để nén.

**Giới hạn bắt buộc nêu kèm:** nguồn video dùng để ghép cặp là bản quay **đã nén
để phân phối trên web**, không phải luồng thu của chính hệ thống. Không được phát
biểu con số này như đo trên dữ liệu do nền tảng thu.

> ### ▣ HÌNH 4-4 — Phân bố dung lượng mẫu và tỉ lệ giảm
> **Loại:** hai biểu đồ ghép — histogram dung lượng tệp đặc trưng, và biểu đồ tán
> xạ tỉ lệ giảm theo thời lượng clip
> **Phải thể hiện:** khoảng p5–p95 đánh dấu trên histogram; trên biểu đồ tán xạ,
> **đánh dấu các cặp bị loại** kèm lý do loại.
> **Chú thích:** *Hình 4-4: Phân bố dung lượng mẫu và tỉ lệ giảm theo từng cặp.*

### 5.5 Trục T4 — Ma trận giả mạo nguồn sự thật

Phép đo chạy qua **đúng đường tiêu thụ của ứng dụng**, không qua hàm trợ giúp —
điều kiện bắt buộc, vì lỗi đã từng xảy ra chính ở chỗ phép kiểm không phủ hết thứ
nó bảo vệ (Chương 3 §2.3.5).

*Bảng 4-18: Ma trận giả mạo nguồn sự thật* — 16/08/2026

| Ca | Thuộc tính kiểm tra | Kết quả | Đánh giá |
|---|---|---|---|
| S1 | Tạo tác, bản kê và chữ ký đều hợp lệ | Chấp nhận | **Đạt** |
| S2 | Đổi **đúng một byte** trong tạo tác sau khi ký | Từ chối | **Đạt** |
| S3 | Sửa mã băm trong bản kê, giữ chữ ký cũ | Từ chối | **Đạt** |
| S4 | Chữ ký **hợp lệ về mật mã**, người ký **không được tin cậy** | Từ chối | **Đạt** |
| S5 | Chữ ký hỏng | Từ chối | **Đạt** |
| S6 | Thiếu chữ ký khi chính sách đòi ký | Từ chối | **Đạt** |
| S7 | **Hồi quy phiên bản** | Chấp nhận; không xoá tài nguyên mới, nhưng giá trị dùng chung bị lùi | **GIỚI HẠN** |
| S8 | Phiên bản mới, nguồn tin cậy | Chấp nhận | **Đạt** |
| S9 | Công bố chỉ bổ sung, giữ nguyên hàng có sẵn | Chấp nhận | **Đạt** |

**Cách đọc đúng:** 9/9 kịch bản **thực thi và cho kết quả xác định**; 8 thoả
thuộc tính mong đợi; 1 phát hiện **giới hạn thật**. Không được viết "SOT 9/9
đạt".

**S4 quan trọng hơn một phép kiểm mã băm.** Kẻ tấn công dựng được một bộ dữ liệu
khác, tính mã băm đúng, viết bản kê đúng, rồi tự ký bằng khoá của hắn — chữ ký ấy
**hợp lệ về mật mã**. Hợp đồng xác minh vì thế phải có bốn vế, và S4 đo vế thứ ba:

```
Tạo tác hợp lệ = Toàn vẹn ∧ Chữ ký hợp lệ ∧ Người ký được tin cậy ∧ Chính sách phiên bản hợp lệ
```

Hàm xác minh trả về **tên khoá đã đăng ký** thay vì một giá trị đúng/sai, nên "ai
ký" là một phần của kết quả xác minh. S4 **đạt**.

**S7 là phát hiện của lượt đo, và là phần đáng giá nhất.** Hợp đồng ở đây có hai
vế không giống nhau:

* (a) hệ thống có **từ chối** một bản công bố lùi phiên bản không? — **Không**.
* (b) nếu chấp nhận, việc lùi có **phá huỷ** trạng thái mới hơn không? — **Không**;
  nguyên tắc chỉ-điền bảo vệ điều đó, nhưng **giá trị dùng chung bị ghi đè lùi**.

Đo được vế (b) đòi hai lượt đồng bộ thật, nên ca này nằm ngoài ma trận tham số và
phải chạy riêng.

**Ba thuộc tính phải tách bạch khi phát biểu**, và đây là một trong ba phát biểu
đã hạ mức được nêu ở đầu quyển:

| Thuộc tính | Trạng thái |
|---|---|
| Toàn vẹn (bằng chứng giả mạo) | **Đạt** |
| Xác thực nguồn ký | **Đạt** |
| Đơn điệu phiên bản | **Chưa cưỡng chế** |

---

## 6. Đánh giá kiểm thử

### 6.1 Đối chiếu mục tiêu đề tài với kết quả

*Bảng 4-19: Đối chiếu mục tiêu với kết quả*

| # | Mục tiêu | Trạng thái | Bằng chứng chính | Giới hạn |
|---|---|---|---|---|
| O1 | Kiến trúc đa tổ chức | **Đạt, có tinh chỉnh** | 57 bảng, 34 mang định danh tổ chức; mô hình phạm vi bốn cấp | Hai cấp dưới chưa có bề mặt vận hành |
| O2 | Cách ly dữ liệu giữa các tổ chức | **Đạt** | 0/450 vi phạm xuyên tổ chức, 0/180 thao tác trái quyền lọt, 0 ca không kết luận được, đối chứng dương đủ bốn thao tác, hậu điều kiện xác nhận dữ liệu nguyên vẹn — đo trên ảnh chụp mã `4e961192` (§5.2bis) | Hai tổ chức, không phải quy mô lớn; đối kháng chứ không phải chứng minh hình thức |
| O3 | Phân quyền nhiều cấp phạm vi | **Đạt một phần** | Gán vai ở cấp hệ thống và cấp tổ chức, cưỡng chế được | Cấp không gian làm việc và dự án: **0 gán vai**, không có bề mặt API |
| O4 | Phân loại từ vựng và phương ngữ | **Đạt** | Ngôn ngữ / phương ngữ / vùng miền + danh mục có phiên bản, ghim được | — |
| O5 | Hiệu quả lưu trữ | **Đạt** | 92,2 % trên 54 cặp khớp thời lượng | Nguồn video ngoài, đã nén để phân phối web |
| O6 | Xử lý bất đồng bộ | **Đạt, có hạn chế độ tin cậy** | Bốn nhóm công việc đều vận hành trên tiến trình nền | Thử lại và tính lũy đẳng **không đồng đều** |
| O7 | Nguồn sự thật ký số có phiên bản | **Đạt, trừ đơn điệu phiên bản** | 9 kịch bản cho kết quả xác định, 8 thoả thuộc tính | Không cưỡng chế thứ tự phiên bản (S7) |
| O8 | Đánh giá theo bốn trục | **Đạt** | Bốn trục đều có phép đo đóng, có giao thức và giới hạn | Không có trục cách ly hiệu năng, đã tuyên bố trước |

### 6.2 Ba phát biểu đã hạ mức

Ba phát biểu dưới đây được hạ mức **sau khi có kết quả đo**, và phải giữ nhất
quán ở Tóm tắt, Chương 3, Chương 4 và Kết luận:

| Chủ đề | **Không viết** | **Viết** |
|---|---|---|
| Phân quyền | Triển khai đầy đủ ở bốn cấp phạm vi | Kiến trúc hỗ trợ nhiều cấp; cưỡng chế **chứng minh được** ở cấp hệ thống và cấp tổ chức |
| Bất đồng bộ | Bảo đảm thử lại an toàn và lũy đẳng | Thực hiện bất đồng bộ bốn nhóm công việc; thử lại và tính lũy đẳng **chưa đồng đều** |
| Nguồn sự thật | Bảo đảm trạng thái mới nhất luôn thắng | Cung cấp **bằng chứng giả mạo** và **xác thực nguồn ký**; **chưa cưỡng chế** đơn điệu phiên bản |

### 6.3 Đánh giá về chất lượng bộ kiểm thử

Bộ kiểm thử đạt 0 lỗi trên cả hai nền chạy, nhưng con số đó **không tự nó chứng
minh chất lượng**. Ba tiêu chí thực chất hơn:

**Bộ kiểm thử có bắt được lỗi thật không?** Có, và ghi nhận được: 22 lỗi lược đồ
im lặng trên nền chạy thứ hai; ba hàm truy vấn thiếu điều kiện lọc theo tổ chức;
sáu cột thiếu trong danh sách kiểm bản công bố; một rò rỉ mã băm mật khẩu qua
đường trả về của API; và — trong chính lượt chạy phục vụ chương này — **một lỗ
hổng ở đường dọn dữ liệu tổ chức** (§6.4). Năm nhóm lỗi này đều thuộc loại **không
sinh ra triệu chứng khi dùng bình thường**.

**Có phân biệt được đỏ thật với đỏ giả không?** Sáu dạng đỏ giả đã được ghi nhận
và có cách phân định (Bảng 4-5). Đây là điều kiện để bộ kiểm thử còn được tin
cậy: một bộ kiểm thử hay đỏ vì lý do ngoài mã sẽ nhanh chóng bị bỏ qua.

**Có chỗ nào bộ kiểm thử không phủ được không?** Có, và phải nêu:

* Cách ly ở **mặt phẳng hệ tệp** dựa vào cấu trúc thư mục và kiểm tra ở tầng ứng
  dụng — mức bảo đảm **thấp hơn** mặt phẳng cơ sở dữ liệu. Phép đo T2 phủ được cả
  hai mặt phẳng, nhưng cơ chế cưỡng chế thì không tương đương.
* **Hành vi ở quy mô lớn** không được kiểm: mọi phép đo chạy ở quy mô hai tổ chức
  và vài nghìn mẫu.
* **Tính lũy đẳng của đường xử lý nền** chưa có kiểm thử phủ đủ, và đó chính là
  giới hạn đã nêu ở O6.

### 6.4 Lượt chạy 17/08/2026 — một lớp lỗi, tám nơi biểu hiện

Lượt chạy hồi quy ngày 17/08/2026 ban đầu **không hoàn tất**, và quá trình đưa nó
về xanh là phần đáng ghi lại nhất của chương này — vì nó cho thấy một bộ kiểm thử
phát hiện lỗi ở đâu, và **che lỗi ở đâu**.

#### a) Bộ kiểm thử bị chặn bởi cấu hình của khách hàng dịch vụ ngoài

Lượt chạy dừng tiến ở mốc 62 % với mức chiếm CPU 0,4–1,2 %, tức **không tính toán
gì**; bên trong container có một kết nối HTTPS đang mở tới kho lưu trữ ngoài.
Nguyên nhân không nằm ở một ca kiểm thử nào mà ở **tích của hai giá trị mặc
định**: thời hạn 180 giây nhân số lần thử lại 5 = **tối đa 900 giây cho mỗi lượt
gọi không tới đích**.

Loại trừ tệp kiểm thử tích hợp mà tài liệu quy trình cảnh báo **không giải quyết
được gì** — lượt chạy dừng ở đúng cùng một mốc, vì tệp khác cũng gọi ra ngoài, và
có tệp gọi gián tiếp qua module ứng dụng nên tìm theo tên thư viện không phủ hết.

Cách xử lý đúng là **hạ trần chờ cho môi trường kiểm thử** (5 giây × 1 lần), phủ
mọi đường gọi kể cả đường viết sau này, thay vì loại dần từng tệp — loại tệp là
chữa triệu chứng, và triệu chứng mọc lại ở tệp tiếp theo. Sau khi hạ trần, bộ
kiểm thử **chạy hết trong 26 phút**, lần đầu tiên.

#### b) Tám ca đỏ, và bảy trong tám thuộc **cùng một lớp lỗi**

| # | Ca đỏ | Nguyên nhân |
|---|---|---|
| 1 | `test_schema_shape::test_tenant_purge_order_covers_every_tenant_table` | Bảng chỉ số huấn luyện có định danh tổ chức nhưng thiếu trong thứ tự dọn |
| 2 | `test_schema_constraints::test_training_metrics_cannot_orphan_itself` | Ca kiểm thử chèn theo lược đồ cũ |
| 3 | `test_reassign_sheets_owner::…labels_sheet…` | **Vá seam cũ** |
| 4–6 | `test_startup_sync` (3 ca) | **Vá seam cũ** |
| 7–8 | `test_tenant_sot_column::TestRebuildFromCsv` (2 ca) | **Vá seam cũ** |
| 9–10 | `test_upload_camera_training` (2 ca promote) | Gieo dữ liệu thiếu định danh tổ chức |
| 11–12 | `test_subscription_lifecycle::TestNhacTruocHan` (2 ca) | **Vá seam cũ** |

*(Số ca lớn hơn tám vì ba ca chỉ lộ ra sau khi những ca trước được sửa — xem
mục c.)*

**Lớp lỗi chung: bản vá trượt trong im lặng.** Một đợt thay đổi lớn — chuyển các
đường đọc sang phạm vi tổ chức fail-closed — đã đổi tên hàm ở nhiều điểm nối.
Kiểm thử vá hàm **cũ**, hàm cũ không còn được gọi, nên bản vá không tác dụng gì;
hàm thật chạy, trả về rỗng, và ca kiểm thử đỏ ở một khẳng định cách xa nguyên
nhân. Thông báo lỗi thu được là `assert [] == [7]`, `assert 0 == 1`,
`['B'] != ['A','B','C']` — **không thông báo nào trỏ về nguyên nhân thật**.

Đây là giới hạn cố hữu của kỹ thuật giả lập: thứ cần canh là *hàm nào được gọi*,
và giả lập xoá đúng thông tin ấy đi.

#### c) Sửa một lỗi làm lộ hai lỗi — và đó là dấu hiệu tốt

Bản vá cho đường đồng bộ đầu vòng đời làm **hai ca kiểm thử khác chuyển sang đỏ**.
Cả hai vốn chỉ xanh vì chúng vá đúng cái tên cũ mà mã còn dùng nhầm; sửa mã cho
đúng thì bản vá của chúng thành trượt. Nói cách khác, **hai ca ấy đang xanh nhờ
một lỗi**, và chỉ lộ ra khi lỗi được vá.

#### d) Hai lỗi ở mã sản xuất, không phải ở kiểm thử

Trong tám ca trên, sáu là kiểm thử lạc hậu. Hai còn lại là lỗi thật:

**Thứ nhất — dọn dữ liệu tổ chức để sót một bảng.** Bảng chỉ số huấn luyện vừa
được gắn định danh tổ chức ở dạng không cho phép rỗng, nhưng chưa vào thứ tự dọn.
Khoá ngoại của nó tới bảng tổ chức là **hạn chế xoá**, nên mọi dòng còn sót làm
bước xoá tổ chức ở cuối lượt dọn bị từ chối và cả lượt dừng giữa chừng. Thao tác
*Dọn sạch dữ liệu tổ chức* (UC508) vì thế **không hoàn tất** — mà không có triệu
chứng nào khi dùng bình thường.

**Thứ hai — đồng bộ lúc khởi động gọi hàm sai và sẽ chết.** Đường đồng bộ đầu
vòng đời đọc danh mục bằng hàm không-phạm-vi, nhưng **dòng ngay dưới** vẫn gọi
hàm có-phạm-vi với tham số bỏ trống. Hàm đó **ném lỗi** khi không có phạm vi, mà
đồng bộ đầu vòng đời chạy trước khi bất kỳ phạm vi nào tồn tại. Ba ca kiểm thử
của đường này không bắt được, vì cả ba đều giả lập hàm ấy — hàm thật không bao
giờ chạy, chốt chặn không bao giờ nổ.

Lỗi này còn có một **bản sinh đôi chưa ai thấy**: đường xuất bảng tính mẫu, bản
đối xứng của đường xuất bảng tính nhãn vốn đã được chuyển đúng.

#### e) Bịt cả lớp lỗi thay vì bịt từng chỗ

Hai lỗi ở mục d cùng một hình dạng: **gọi một hàm bắt buộc có phạm vi mà bỏ trống
tham số**. Cả hai đều nằm ngoài tầm của kiểm thử hành vi vì kiểm thử giả lập đúng
hàm đó.

Nên bản vá không dừng ở hai chỗ, mà thêm một **bất biến tĩnh** quét cây cú pháp
toàn bộ mã dịch vụ: *không nơi nào được gọi các hàm đọc bắt buộc-có-phạm-vi với
danh sách tham số rỗng*. Luật này không có ngoại lệ hợp lệ nào — hoặc thiếu phạm
vi, hoặc đây là đường bảo trì và phải gọi biến thể mang tên tự-tố-cáo là toàn
cục — nên nó không cần danh sách miễn trừ, thứ vốn là chỗ mà một luật bắt đầu
mục ruỗng.

Bất biến ấy tìm ra **nơi gọi bị bỏ sót thứ hai ngay trong lượt chạy đầu tiên của
chính nó**, ở một tệp không ai nghi ngờ.

#### f) Kết quả sau khi vá

```
lượt đầu     2.528 ca · 2.522 xanh · 6 đỏ · 1 bỏ qua   (26 ph 18 s)
             → 8 bản vá, trong đó 2 vá mã sản xuất và 1 thêm bất biến tĩnh
lượt xác nhận 2.529 ca · 2.528 xanh · 0 đỏ · 1 bỏ qua  (22 ph 14 s)
```

Ca thứ 2.529 là bất biến tĩnh thêm ở mục e. Ca bỏ qua là bộ nghiên cứu chạy như
tiến trình con, bỏ qua có điều kiện đúng như thiết kế.

**Trạng thái phải báo cáo trung thực:** cây mã tại thời điểm chạy đang ở giữa một
đợt thay đổi chưa hoàn tất. Phần lớn các ca đỏ là **hệ quả của đợt thay đổi đang
làm dở**, không phải hồi quy của mã đã ổn định. Nhưng hai lỗi ở mục d là lỗi
thật, và cả hai đều đã được vá cùng với bất biến chặn tái diễn.

*Quy tắc "phát hiện trong lúc đo thì ghi, không sửa ngay" (Phụ lục E §1, quy tắc
4) áp cho **phép đo**, không áp cho bộ kiểm thử. Các phát hiện trên đến từ lượt
chạy hồi quy chứ không từ một phép đo đang mở, nên chúng được ghi vào sổ vấn đề
đã biết **và** được sửa; không có con số đo nào bị thay đổi dưới chân.*

### 6.5 Kết luận chương

Bốn trục đánh giá đều đã đóng. Trục trung tâm — cách ly dữ liệu giữa các tổ chức
— cho tỉ lệ vi phạm bằng không trên 630 lượt thử đối kháng kết luận được, với đối
chứng dương phủ cả đọc lẫn ghi, hậu điều kiện xác nhận dữ liệu bên bị nhắm vẫn
nguyên vẹn trên cả hai mặt phẳng lưu trữ, và kết quả gắn với một **ảnh chụp mã bất
biến** chứ không phải với trạng thái nhất thời của cây làm việc (§5.2bis).

Hai kết quả **không đạt hoàn toàn** đã được báo cáo đúng mức thay vì làm tròn:
phân quyền mới cưỡng chế được ở hai trong bốn cấp phạm vi, và cơ chế nguồn sự
thật chưa cưỡng chế thứ tự phiên bản. Cả hai đều được phát hiện **bởi chính các
phép đo của luận văn**, chứ không phải bởi người phản biện — và đó là điều một bộ
phép đo có khả năng thất bại đáng làm được.
