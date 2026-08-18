# PHẦN KẾT LUẬN

---

## 1. Kết quả đạt được

### 1.1 Về lý thuyết

**a) Một mệnh đề cách ly kiểm chứng được, và một thiết kế bốn tầng để đạt nó.**

Đóng góp lý thuyết trung tâm của luận văn không phải là "áp dụng row-level
security cho hệ thống đa thuê bao" — điều đó đã được biết đến
[@postgresql_rls_2026; @aulbach_multi-tenant_2008]. Đóng góp nằm ở chỗ khác: phát
biểu ranh giới cách ly thành một **mệnh đề kiểm chứng được**, rồi chỉ ra rằng
mệnh đề ấy chỉ đúng khi bốn tầng cùng có mặt.

> Một truy vấn không khai báo tổ chức trả về **không hàng nào**, chứ không phải
> mọi hàng. Và **đường truy vấn nghiệp vụ của ứng dụng không tự vô hiệu hoá được**
> cơ chế đó.

Mệnh đề này có một ranh giới phải nêu kèm mỗi lần nó được dùng. Nó phát biểu về
**đường truy vấn của ứng dụng**: cơ chế đưa điều kiện phạm vi ra khỏi trách nhiệm
của truy vấn nghiệp vụ thông thường, kể cả những truy vấn được viết sau khi quy
ước đã được đặt ra. Nó **không** phát biểu rằng dữ liệu vẫn được bảo vệ trước một
kẻ tấn công đã chiếm được thông tin xác thực cơ sở dữ liệu của ứng dụng — trong
tình huống đó, kẻ tấn công đặt lại được chính biến ngữ cảnh mà chính sách đọc.
Hai mô hình đe doạ này được định nghĩa ở Chương 2 §2.4.5 và Bảng 2-17; toàn bộ số
liệu ở Chương 4 thuộc mô hình thứ nhất. Bảo vệ trước mô hình thứ hai là bài toán
của quản lý bí mật và kiểm soát truy cập hạ tầng, nằm ngoài phạm vi luận văn.

Vế thứ hai của mệnh đề là phần ít được nói tới trong tài liệu về đa thuê bao, và
là phần luận văn này đóng góp rõ nhất. Bốn tầng — cột phân biệt, chính sách mức hàng,
phạm vi giao dịch, tách vai cơ sở dữ liệu — mỗi tầng bịt một lối vòng mà ba tầng
còn lại để hở:

| Tầng | Lối vòng nó bịt | Nếu thiếu tầng này |
|---|---|---|
| 1. Cột phân biệt | — | Không có gì để lọc theo |
| 2. Chính sách mức hàng, đọc ngữ cảnh ở dạng "cho phép thiếu" | Truy vấn quên điều kiện lọc | Cách ly phụ thuộc kỷ luật lập trình, và **hỏng im lặng** |
| 3. Gán ngữ cảnh giới hạn trong giao dịch | Ngữ cảnh dính lại trên bể kết nối | Rò dữ liệu sang yêu cầu kế tiếp, **không có thông báo lỗi nào** |
| 4. Tách vai cơ sở dữ liệu | Ứng dụng tự chạy lệnh vô hiệu hoá chính sách | Bảo đảm biến thành **lời khuyên** |

Lập luận mạnh nhất cho tầng 2 là một bằng chứng thực nghiệm chứ không phải một
giả định: trong chính hệ thống này, **ba hàm ở tầng truy cập dữ liệu không lọc
theo tổ chức** — xoá một mẫu, xoá mẫu theo lớp, cập nhật đường dẫn lưu trữ. Vá
tay được ba hàm đã biết; chính sách ở tầng cơ sở dữ liệu vá luôn những hàm sẽ
viết sau mà tác giả quên lọc.

**b) Một nguyên lý phương pháp: phép đo phải có khả năng thất bại.**

Nguyên lý này được phát biểu và **áp dụng có chi phí thật**: một lượt đo cho kết
quả đẹp — 630 lần thử đối kháng, không lần nào vượt được ranh giới — đã bị **loại
khỏi phân tích**, vì đối chứng dương không đạt. Tài khoản thử không đọc được cả
dữ liệu của chính nó, nên "đã bị chặn" tương thích với hai giả thuyết mà phép đo
không phân biệt được.

Từ đó rút ra ba hệ quả áp cho mọi phép đo trong quyển: đối chứng dương là **điều
kiện tiên quyết**, không phải phần bổ sung; đối chứng dương phải phủ **cả vế
ghi**; và "phép đo hợp lệ" phải tách khỏi "thuộc tính đạt" khi phát biểu kết quả.

**c) Bốn ranh giới khái niệm được làm rõ**, mỗi ranh giới sinh ra từ một lỗi thật:

* **Kế thừa lúc khởi tạo ≠ rơi về lúc chạy.** Sao chép danh mục cộng đồng vào một
  tổ chức mới là kế thừa — xảy ra một lần, kết quả thuộc về tổ chức đó. Đọc danh
  mục cộng đồng khi tổ chức thiếu dữ liệu là rơi về, và bị cấm. Hai thứ trông
  giống nhau trên sơ đồ nhưng khác hẳn về hệ quả.
* **Tài khoản thu ≠ chủ thể dữ liệu.** Người bấm nút và người có bàn tay trong dữ
  liệu là hai vế. Đo được: định danh người ký phủ **43,4 %** kho dữ liệu, nghĩa
  là **56,6 % không quy kết được**.
* **Ngoại lệ là một phạm vi, không phải một lối đi vòng.** Công việc nền xuyên tổ
  chức cần một biến ngữ cảnh riêng biệt, để "hành động thay mọi tổ chức" không
  bao giờ sinh ra được từ một lỗi gõ tên tổ chức.
* **Bốn nghĩa của "thu hồi".** Hệ thống chỉ thi hành nghĩa thứ hai — gỡ khỏi các
  bản phát hành mới. Hứa "xoá là biến mất hoàn toàn" là hứa hai nghĩa còn lại.

### 1.2 Về chương trình

Hệ thống đã được xây dựng, triển khai và đang vận hành với dữ liệu thật.

| Hạng mục | Số liệu | Cách kiểm chứng |
|---|---|---|
| Dịch vụ container | 15 khai báo, 14 chạy thường trực | Tệp khai báo triển khai |
| Bảng cơ sở dữ liệu | 57 bảng nghiệp vụ + 1 khung nhìn | Truy vấn siêu dữ liệu, 17/08/2026 |
| Khoá ngoại | 117, trong đó **22 khoá ghép mang định danh tổ chức** | Truy vấn siêu dữ liệu, 17/08/2026 |
| Bảng bật chính sách mức hàng | 32, **32/32 = 100 % bật cờ cưỡng chế với chủ sở hữu bảng** | Truy vấn siêu dữ liệu, 17/08/2026 |
| Độ phủ cách ly | 32/34 bảng mang định danh tổ chức ≈ 94,1 % | Truy vấn siêu dữ liệu, 17/08/2026 |
| Điểm cuối API | 213 trên 26 bộ định tuyến | Đếm bộ trang trí phương thức |
| Mã nguồn dịch vụ | 61.097 dòng, 162 tệp | Đếm dòng, 17/08/2026 |
| Mã nguồn giao diện | 48.074 dòng, 221 tệp | Đếm dòng, 17/08/2026 |
| Mã kiểm thử | 41.760 dòng, 151 tệp | Đếm dòng, 17/08/2026 |
| Kiểm thử chạy xanh | **2.528 xanh / 0 đỏ / 1 bỏ qua** trên 2.529 ca thu thập | Lượt chạy đầy đủ 17/08/2026, 22 ph 14 s |
| Mẫu dữ liệu đã thu | 3.860 mẫu, 60 lớp từ vựng | Nguồn sự thật của kho mẫu |

Bảy khối chức năng đã hoàn thiện và chạy được đầu-cuối: thu nhận dữ liệu hai
đường; danh mục từ vựng ba mặt phẳng có ghim phiên bản; xử lý bất đồng bộ bốn
nhóm công việc; huấn luyện qua ba cổng chặn; nhận dạng thời gian thực; đồng thuận
và khuôn khổ pháp lý có hiệu lực thi hành; và bộ công cụ vận hành gồm sao lưu,
đối soát, kiểm chứng độ tươi triển khai.

### 1.3 Về khả năng ứng dụng thực tiễn

**Đã ứng dụng, không phải sẽ ứng dụng.** Hệ thống đang chạy trên máy chủ của đơn
vị, có dữ liệu thật (3.860 mẫu, 60 lớp) và người dùng thật. Nó cũng đã được triển
khai lại thành công trên **máy thứ hai** với cấu hình phần cứng khác — bằng chứng
rằng quy trình triển khai không phụ thuộc vào một máy cụ thể.

Ba nhóm ứng dụng cụ thể:

* **Cho nhóm nghiên cứu:** nền tảng cung cấp sẵn danh mục chuẩn, cơ chế ghim
  phiên bản để tái lập thí nghiệm, và đường xuất dữ liệu. Một nhóm mới bắt đầu
  thu dữ liệu VSL không phải dựng lại hạ tầng từ đầu.
* **Cho cơ sở đào tạo:** nhiều lớp học có thể cùng thu dữ liệu trên một bản triển
  khai mà dữ liệu của mỗi lớp không lẫn sang lớp khác.
* **Cho cộng đồng người khiếm thính:** đường nhận dạng thời gian thực và đầu ra
  giọng nói phục vụ giao tiếp, và cơ chế đồng thuận cho người đóng góp quyền kiểm
  soát thực chất đối với dữ liệu của mình — không chỉ là một ô tích trong biểu mẫu.

**Giá trị dùng lại được của phần thiết kế.** Thiết kế bốn tầng cách ly không gắn
với miền ngôn ngữ ký hiệu; nó áp dụng được cho bất kỳ hệ thống đa thuê bao nào
dùng chung lược đồ. Tương tự với cơ chế nguồn sự thật ký số và cơ chế đồng thuận
có phiên bản.

---

## 2. Hạn chế và khó khăn

Phần này nêu thẳng những gì hệ thống **chưa** làm được. Ba hạn chế đầu đã được
phát hiện **bởi chính các phép đo của luận văn**, không phải bởi người phản biện.

### 2.1 Hạn chế về phạm vi cưỡng chế

**a) Phân quyền mới cưỡng chế được ở hai trong bốn cấp phạm vi.** Mô hình dữ liệu
và kiến trúc phân quyền hỗ trợ một hệ phân cấp bốn cấp, nhưng cấp không gian làm
việc và cấp dự án hiện có **0 gán vai** và **không có điểm cuối API nào**. Chúng
là cấu trúc dữ liệu, chưa phải bề mặt vận hành. Vì thế không có gì để kiểm chứng
cách ly ở hai cấp đó từ bên ngoài.

Quyết định có ý thức: **không dựng vội hai tầng phân quyền chỉ để khớp đề cương.**
Ghi nhận sai lệch trung thực tốt hơn nhiều so với một bề mặt chưa có nghiệp vụ
thật đứng sau.

**b) Cách ly phủ nửa đầu vòng đời dữ liệu.** Ranh giới tổ chức được cưỡng chế
chặt trên đường thu nhận và quản lý mẫu. Nửa sau — huấn luyện và quản lý mô hình
— mới ở mức kiến trúc đích, chưa cưỡng chế theo ranh giới tổ chức trên mọi đường.

**c) Cách ly ở mặt phẳng hệ tệp yếu hơn ở mặt phẳng cơ sở dữ liệu.** Với tài
nguyên nằm trong cơ sở dữ liệu, cách ly do cơ sở dữ liệu cưỡng chế. Với tài
nguyên nằm trên hệ tệp, cách ly dựa vào cấu trúc thư mục và kiểm tra ở tầng ứng
dụng — mức bảo đảm thấp hơn. Phép đo phủ được cả hai mặt phẳng, nhưng cơ chế thì
không tương đương, và phát biểu trong quyển giữ đúng mức đó.

### 2.2 Hạn chế về độ tin cậy

**a) Thử lại và tính lũy đẳng không đồng đều.** Bốn nhóm công việc nền đều vận
hành, nhưng cơ chế thử lại khác nhau giữa các đường, và tính lũy đẳng **chưa bảo
đảm** cho việc tạo tài nguyên và tải đối tượng lên kho ngoài. Chạy lại một tác vụ
có thể tạo bản trùng.

**b) Nguồn sự thật chưa cưỡng chế đơn điệu phiên bản.** Kịch bản S7 của ma trận
giả mạo cho thấy một bản công bố có số hiệu phiên bản thấp hơn **vẫn được chấp
nhận**. Tài nguyên mới hơn không bị xoá — nguyên tắc chỉ-điền bảo vệ điều đó —
nhưng giá trị dùng chung bị ghi đè lùi.

**c) Nguồn sự thật của kho mẫu vẫn là tệp CSV.** Đây là di sản kiến trúc từ hệ
thống tiền thân, không phải thiết kế được chọn. Hệ quả: phải duy trì một cơ chế
đối soát định kỳ, và đường ghi tệp không chịu chính sách bảo mật mức hàng.

### 2.3 Hạn chế về dữ liệu

**a) Dữ liệu mất cân bằng nặng.** 64 % số mẫu thuộc nhóm bảng chữ cái. Không được
mô tả bộ dữ liệu này là "cân bằng", và mọi kết quả huấn luyện trên nó phải đọc
kèm phân bố này.

**b) Hơn một nửa kho dữ liệu không quy kết được về người ký.** Định danh người ký
phủ 43,4 %. Nếu một người yêu cầu rút phần đóng góp của mình, hệ thống **không
xác định nổi đó là những dòng nào**. Cơ chế đã đúng từ khi được xây; khoảng trống
nằm ở dữ liệu lịch sử thu trước khi cơ chế tồn tại.

**c) 100 % mẫu đến từ nguồn camera**, không có mẫu nào từ đường tải video. Đường
tải video hoạt động và có kiểm thử, nhưng chưa được dùng ở quy mô thật.

### 2.4 Hạn chế về phạm vi đánh giá

**a) Không đánh giá độ chính xác mô hình** — đã tuyên bố ở Chương 1, và lý do nêu
ở Chương 4 §1.

**b) Không chứng minh cách ly hiệu năng.** Hệ thống có hạn mức và giới hạn tần
suất, nhưng không có thí nghiệm tải chứng minh một tổ chức không làm chậm tổ chức
khác. Phép đo độ trễ ở Chương 4 là **độ trễ cơ sở**, không phải phép thử tải.

**c) Phép đo cách ly chạy ở quy mô hai tổ chức.** Nó chứng minh cơ chế hoạt động,
không chứng minh cơ chế giữ được ở quy mô lớn.

**d) Phép đo là đối kháng, không phải chứng minh hình thức.** Kết quả đúng là
"trong 630 lượt thử theo giao thức này, không quan sát thấy vi phạm nào" — không
phải "không thể có vi phạm".

### 2.5 Khó khăn gặp phải trong quá trình thực hiện

Ba nhóm khó khăn đáng ghi lại, vì chúng định hình cách làm về sau:

**a) Lỗi hỏng im lặng chiếm phần lớn thời gian gỡ rối.** Bốn nhóm lỗi nghiêm
trọng nhất tìm được đều **không sinh triệu chứng khi dùng bình thường**: lược đồ
thiếu 2 bảng/7 khoá ngoại/14 cột trên máy mới; ba hàm truy vấn thiếu điều kiện
lọc; sáu cột thiếu trong danh sách kiểm bản công bố; một ảnh giao diện chạy sau
mã nguồn năm tiếng trong khi mọi container báo khoẻ mạnh. Đây là lý do luận văn
đầu tư nhiều vào các cơ chế **phát hiện** chứ không chỉ vào chức năng.

**b) Phân biệt "đỏ thật" với "đỏ giả" tốn công không kém việc sửa lỗi.** Sáu dạng
đỏ giả đã được ghi nhận, trong đó dạng tệ nhất là hạ tầng biến mất giữa lượt chạy
— sinh ra 208 lỗi trông y hệt một hồi quy lớn.

**c) Một sự cố nghiêm trọng: bộ kiểm thử chạy nhầm vào cơ sở dữ liệu sản xuất.**
Ngày 13/08/2026, suite áp một phiên bản lược đồ đang làm dở lên dữ liệu thật và
đóng dấu phiên bản đó. Nguyên nhân: biến cấu hình tên cơ sở dữ liệu **không tham
gia dựng chuỗi kết nối**. Đã bổ sung hai lớp chặn. Bài học tổng quát: **một cấu
hình trông như đang kiểm soát một thứ mà thực ra không kiểm soát gì là dạng nguy
hiểm nhất**, vì nó tạo cảm giác an toàn sai.

---

## 3. Hướng phát triển

### 3.1 Đóng các giới hạn đã biết

Xếp theo tỉ lệ giá trị trên công sức:

| # | Việc | Đóng giới hạn nào | Ước lượng |
|---|---|---|---|
| 1 | **Cưỡng chế đơn điệu phiên bản** ở khâu xác minh nguồn sự thật: từ chối bản công bố có số hiệu thấp hơn, trừ khi có cờ hạ cấp tường minh | §2.2b — kịch bản S7 | Nhỏ |
| 2 | **Chuẩn hoá tính lũy đẳng** cho đường tạo tài nguyên và tải đối tượng: khoá lũy đẳng theo nội dung | §2.2a | Vừa |
| 3 | **Chuyển nguồn sự thật của kho mẫu** từ tệp CSV sang cơ sở dữ liệu, giữ CSV làm bản xuất | §2.2c, §2.1c | Lớn |
| 4 | **Ghi bù định danh người ký** cho dữ liệu lịch sử, ở mức làm được | §2.3b | Vừa, phụ thuộc dữ liệu |
| 5 | **Dựng bề mặt vận hành** cho hai cấp phạm vi dưới, rồi mở rộng phép đo cách ly sang bốn cấp | §2.1a | Lớn |

Việc số 1 đáng làm trước vì chi phí nhỏ và nó biến một giới hạn đã công bố thành
một thuộc tính đạt.

### 3.2 Mở rộng phạm vi đánh giá

* **Thí nghiệm tải để chứng minh cách ly hiệu năng.** Tạo tải ở tổ chức A rồi
  quan sát độ trễ ở tổ chức B — phép đo mà Chương 4 tuyên bố là không làm.
* **Mở rộng phép đo cách ly lên quy mô nhiều tổ chức** và nhiều hạng dữ liệu hơn,
  để trả lời câu hỏi cơ chế có giữ được khi số tổ chức tăng.
* **Kiểm chứng hình thức một phần** cho mệnh đề cách ly, thay vì chỉ đối kháng.

### 3.3 Mở rộng năng lực hệ thống

* **Kho đối tượng chuyên dụng** thay cho cặp hệ tệp cục bộ và kho lưu trữ ngoài,
  khi có ngân sách hạ tầng — sẽ đưa mặt phẳng tệp về cùng mức cưỡng chế với mặt
  phẳng cơ sở dữ liệu.
* **Miền dùng chung cho cộng đồng** với đường công bố hoàn chỉnh: hiện mới hoàn
  thiện một phần, và không có đường quay ngược từ công khai vào riêng tư.
* **Mở rộng biểu diễn dữ liệu** sang tư thế toàn thân và biểu cảm khuôn mặt, phục
  vụ nhận dạng câu liên tục. Lưu ý ràng buộc một chiều: dữ liệu đã thu theo biểu
  diễn hiện tại **không phục vụ được** hướng này, phải thu lại.
* **Cân bằng dữ liệu** bằng một chiến dịch thu có mục tiêu, ưu tiên các lớp ngoài
  nhóm bảng chữ cái.

### 3.4 Hướng nghiên cứu

* **Chuẩn hoá quy trình quy kết và đồng thuận cho dữ liệu ngôn ngữ ký hiệu.** Con
  số 56,6 % không quy kết được không phải chuyện riêng của hệ thống này; nó là
  đặc điểm chung của các bộ dữ liệu thu trước khi khái niệm chủ thể dữ liệu được
  đặt ra. Một khuôn khổ mô tả bộ dữ liệu [@gebru_datasheets_2021] có phần bắt
  buộc về quy kết sẽ giúp cộng đồng tránh lặp lại.
* **Liên thông giữa các nền tảng thu dữ liệu.** Hiện mỗi nền tảng là một ốc đảo.
  Cơ chế danh mục có phiên bản và ký số trong luận văn này là một nền để bàn về
  liên thông, vì nó cho phép hai bên đối chiếu xem có đang nói về cùng một tập
  nhãn hay không.

---

## 4. Lời kết

Luận văn thiết kế, hiện thực và đánh giá **phân hệ thu thập và quản lý dữ liệu
Ngôn ngữ Ký hiệu Việt Nam** trong nền tảng đa tổ chức CTU.SignBridge, với đóng góp
trọng tâm là cơ chế cách ly dữ liệu được cưỡng chế ở tầng cơ sở dữ liệu — phát
biểu thành một mệnh đề kiểm chứng được, và kiểm chứng bằng một phép đo có khả năng
thất bại, trong phạm vi mô hình đe doạ đã nêu ở Chương 2 §2.4.5.

Điều đáng nói nhất ở phần kết quả không phải các con số bằng không, mà là **những
chỗ không bằng không**: một lượt đo bị loại vì đối chứng dương không đạt; một
kịch bản giả mạo phát hiện giới hạn thật về thứ tự phiên bản; hơn một nửa kho dữ
liệu không quy kết được về người ký. Ba phát hiện đó đến từ chính bộ phép đo của
luận văn, và chúng có giá trị hơn ba con số đẹp — vì một hệ thống mà mọi phép đo
đều cho kết quả hoàn hảo thường là một hệ thống chưa được đo đúng chỗ.
