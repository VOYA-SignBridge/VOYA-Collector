# Thuyết minh vận hành và độ tin cậy

*Bản thuyết minh dạng luận văn. Trình bày cách hệ thống được triển khai, sao lưu,
giám sát, và những bài học sự cố có giá trị phương pháp. Phần này thường bị bỏ
qua trong các đề tài phần mềm, nhưng với một nền tảng nhiều đơn vị cùng dùng thì
nó là điều kiện để hệ thống thực sự phục vụ được.*

---

## 1. Bối cảnh triển khai

### 1.1 Ràng buộc thực tế

Hệ thống được triển khai trên hạ tầng của một trường đại học, không phải trên nền
tảng đám mây thương mại. Điều này đặt ra những ràng buộc định hình toàn bộ thiết
kế vận hành: tài nguyên cố định và hữu hạn, không có khả năng co giãn tự động,
không có đội vận hành trực ca, và không có ngân sách cho các dịch vụ quản trị bên
ngoài.

Hệ quả là ba nguyên tắc thực hành:

**Ưu tiên phát hiện sớm hơn là chịu tải cao.** Với tài nguyên cố định, việc quan
trọng không phải là xử lý được đỉnh tải, mà là biết trước khi chạm giới hạn.

**Mọi thứ phải tự phục hồi hoặc tự báo động.** Không có người trực, nên một sự cố
lúc nửa đêm hoặc là hệ thống tự vượt qua, hoặc là phải có thông báo tới được con
người.

**Quy trình phải chạy được bởi một người.** Không giả định có đội vận hành; mọi
thủ tục triển khai, sao lưu, khôi phục đều phải thực hiện được bởi một người
trong thời gian hợp lý.

### 1.2 Đóng gói theo container

Toàn bộ hệ thống được đóng gói thành các container độc lập: ứng dụng chính, giao
diện, cơ sở dữ liệu, bộ nhớ đệm và hàng đợi, các tiến trình nền xử lý công việc,
bộ lập lịch định kỳ, và dịch vụ suy diễn.

Lựa chọn này giải quyết được vấn đề tái lập môi trường — một đề tài học thuật
thường phải chạy trên máy phát triển, máy thử nghiệm, và máy triển khai với cấu
hình khác nhau. Nhưng nó cũng tạo ra một lớp bẫy riêng, trình bày ở mục 2.

### 1.3 Giới hạn tài nguyên theo từng thành phần

Mỗi container được gán giới hạn bộ nhớ riêng thay vì để chúng tự do tranh giành.

Lý do rút ra từ kinh nghiệm: khi không giới hạn, một thành phần rò rỉ bộ nhớ sẽ
kéo cả máy chủ xuống, và triệu chứng xuất hiện ở một thành phần hoàn toàn khác —
thường là thành phần vô tội nhưng nhạy cảm nhất với thiếu bộ nhớ. Việc chẩn đoán
khi ấy đi sai hướng ngay từ đầu.

Đặt giới hạn khiến thành phần có vấn đề tự bộc lộ, và giữ cho phần còn lại của hệ
thống tiếp tục hoạt động.

---

## 2. Những bẫy đặc trưng của triển khai bằng container

Phần này ghi lại các dạng lỗi đã gặp thật. Chúng có chung một đặc điểm: **hệ thống
báo cáo tình trạng khoẻ mạnh trong khi thực tế không phải vậy.**

### 2.1 Trạng thái khoẻ mạnh không đồng nghĩa với mã mới

Mã nguồn của ứng dụng được nướng vào ảnh container tại thời điểm dựng. Nghĩa là
việc khởi động lại một container **không** làm nó chạy mã mới; phải dựng lại ảnh.

Đây là nguồn gốc của một dạng nhầm lẫn tốn thời gian: người triển khai sửa mã,
khởi động lại dịch vụ, thấy nó báo khoẻ mạnh, và kết luận đã triển khai xong. Thực
tế mã cũ vẫn đang chạy.

Tình huống này nghiêm trọng hơn khi có nhiều dịch vụ cùng dùng chung một ảnh — dễ
bỏ sót một vài dịch vụ khi dựng lại, và hệ thống rơi vào trạng thái nửa cũ nửa
mới, nơi các thành phần bất đồng với nhau về cấu trúc dữ liệu.

Biện pháp: một thủ tục kiểm tra độ tươi của bản triển khai, đối chiếu mã thực sự
đang chạy trong container với mã hiện có, thay vì tin vào trạng thái báo cáo.

### 2.2 Thay đổi cấu hình không tự có hiệu lực

Tương tự, việc sửa tệp cấu hình môi trường rồi khởi động lại container không đủ.
Biến môi trường được nạp vào lúc container được tạo; muốn thay đổi có hiệu lực
thì phải tạo lại container, không phải khởi động lại.

Đây là hai thao tác nghe giống nhau nhưng khác hẳn về hệ quả, và sự nhầm lẫn dẫn
tới những giờ chẩn đoán tại sao cấu hình mới "không ăn".

### 2.3 Mất cấu hình chồng lớp

Hệ thống dùng nhiều tệp cấu hình chồng lên nhau: cấu hình cơ sở, cấu hình cho môi
trường triển khai, và cấu hình bổ sung cho phần cứng tăng tốc.

Một số lệnh quản lý container, khi được gọi mà không chỉ định đầy đủ danh sách tệp
cấu hình, sẽ âm thầm bỏ qua các lớp bổ sung. Kết quả là dịch vụ khởi động thành
công nhưng thiếu quyền truy cập phần cứng tăng tốc — nó vẫn chạy, chỉ là chậm hơn
nhiều lần, và không có thông báo nào.

Đây lại là dạng hỏng "vẫn chạy nhưng sai": khó phát hiện hơn hẳn một sự cố dừng
hẳn.

### 2.4 Phép kiểm tra sức khoẻ phải phù hợp với môi trường bên trong

Các phép kiểm tra sức khoẻ của container cần được viết dựa trên những công cụ
thực sự có mặt trong ảnh, không dựa trên giả định. Một phép kiểm dùng công cụ
không tồn tại sẽ luôn thất bại, khiến container bị coi là hỏng dù nó đang hoạt
động bình thường; hoặc tệ hơn, được viết theo cách luôn thành công và trở nên vô
dụng.

Một chi tiết nhỏ nhưng đã gây sự cố thật: kiểm tra kết nối tới máy cục bộ nên dùng
địa chỉ số thay vì tên gọi, vì tên gọi có thể được phân giải sang giao thức mạng
mà dịch vụ không lắng nghe.

### 2.5 Khác biệt giữa các hệ điều hành

Khi mã nguồn được phát triển trên một hệ điều hành và chạy trên hệ điều hành
khác, quy ước xuống dòng trong tệp có thể bị chuyển đổi tự động. Với các tệp kịch
bản khởi động, sự khác biệt này khiến tệp không thực thi được, và thông báo lỗi
nhận được lại chỉ vào một nguyên nhân hoàn toàn khác.

Cách xử lý là khai báo tường minh quy ước xuống dòng cho các loại tệp nhạy cảm,
thay vì phụ thuộc vào cấu hình của từng máy.

### 2.6 Nguyên lý chung rút ra

Sáu tình huống trên có chung một hình dạng: **hệ thống ở trạng thái sai nhưng
không phát tín hiệu nào.**

Nguyên lý phòng ngừa: với mỗi cơ chế mà việc hỏng của nó không gây triệu chứng,
cần một phép kiểm tra chủ động, chạy tự động và định kỳ. Không dựa vào việc ai đó
sẽ để ý thấy.

---

## 3. Quản lý thay đổi cấu trúc dữ liệu

### 3.1 Hai loại thay đổi và vì sao phải tách

Thay đổi cấu trúc cơ sở dữ liệu được chia thành hai loại, xử lý theo hai cách khác
nhau.

**Loại chỉ thêm** — thêm bảng mới, thêm cột mới có giá trị mặc định. Loại này an
toàn với cả mã cũ lẫn mã mới, nên có thể chạy tự động lúc khởi động ứng dụng.

**Loại một chiều** — xoá cột, đổi kiểu dữ liệu, chuyển đổi dữ liệu. Loại này không
hoàn tác được và có thể phá vỡ mã cũ, nên **phải chạy tường minh** bằng một lệnh
riêng, do người vận hành chủ động thực hiện.

Lý do tách: nếu để thao tác phá huỷ chạy tự động lúc khởi động, thì mọi lần khởi
động lại đều mang rủi ro, và một lần khởi động ngoài ý muốn có thể gây mất dữ
liệu. Việc khởi động lại một dịch vụ phải là thao tác an toàn tuyệt đối.

### 3.2 Chốt chặn phiên bản hai chiều

Ứng dụng từ chối khởi động nếu phiên bản cấu trúc dữ liệu không khớp với phiên bản
mà mã nguồn mong đợi — và từ chối theo **cả hai chiều**.

Chiều thứ nhất hiển nhiên: cấu trúc cũ hơn mã thì mã sẽ tham chiếu tới những thứ
chưa tồn tại.

Chiều thứ hai kém hiển nhiên nhưng quan trọng không kém: cấu trúc mới hơn mã. Tình
huống này xảy ra khi triển khai bị quay lui một phần, và nó nguy hiểm vì mã cũ có
thể ghi dữ liệu theo cách không tương thích với cấu trúc mới, làm hỏng dữ liệu một
cách âm thầm.

### 3.3 Chốt chặn đích đến

Một sự cố thực tế đã dẫn tới việc bổ sung chốt chặn này: một lệnh chuyển đổi cấu
trúc được chạy nhầm lên cơ sở dữ liệu vận hành thay vì cơ sở dữ liệu thử nghiệm.

Nguyên nhân là một giả định sai về cách chuỗi kết nối được xây dựng — người vận
hành tin rằng việc chỉ định tên cơ sở dữ liệu trong một biến môi trường sẽ định
tuyến lệnh tới đúng đích, nhưng biến ấy không tham gia vào việc dựng chuỗi kết
nối.

Biện pháp khắc phục không phải là "cẩn thận hơn", mà là một chốt chặn kỹ thuật:
mọi lệnh chuyển đổi cấu trúc phải khai báo tường minh tên cơ sở dữ liệu mà nó kỳ
vọng, và tự dừng nếu đích thực tế không khớp.

Nguyên lý: **khi một sai sót có hậu quả không hồi phục, hãy dựng chốt chặn kỹ
thuật thay vì dựa vào quy trình.**

### 3.4 Lệch cấu trúc trên máy mới

Một dạng lỗi khó phát hiện khác: hàm khởi tạo cấu trúc tự động dần dần lệch khỏi
cấu trúc thực tế của hệ thống đang chạy. Nguyên nhân là các thay đổi được áp trực
tiếp lên hệ thống vận hành qua thời gian mà không được phản ánh lại vào hàm khởi
tạo.

Hệ quả chỉ lộ ra khi dựng hệ thống trên một máy hoàn toàn mới: máy mới thiếu bảng,
thiếu ràng buộc, thiếu cột so với máy đang chạy — nhưng vẫn khởi động được, nên
sai lệch không được phát hiện ngay.

Biện pháp là một phép so sánh tự động giữa cấu trúc do hàm khởi tạo sinh ra và cấu
trúc thực tế, chạy như một phần của bộ kiểm thử.

---

## 4. Sao lưu và khôi phục

### 4.1 Nguyên tắc: sao lưu chưa được diễn tập là sao lưu chưa tồn tại

Đây là nguyên tắc nền tảng của phần này. Một cơ chế sao lưu chạy đều đặn nhưng
chưa từng được dùng để khôi phục thì chưa có bằng chứng nào cho thấy nó hoạt động.

Kinh nghiệm của đề tài xác nhận điều này theo cách khó chịu: cơ chế sao lưu tự
động đã được cấu hình từ lâu, nhưng khi rà soát thì phát hiện nó **chưa từng chạy
lần nào**. Việc cấu hình tồn tại tạo ra cảm giác an toàn suốt một thời gian dài mà
không có gì phía sau.

### 4.2 Thứ tự thao tác quan trọng

Một chi tiết kỹ thuật có hệ quả lớn: khi kết hợp việc xuất dữ liệu với việc nén,
thứ tự thao tác quyết định khả năng phát hiện lỗi.

Nếu nén trực tiếp trong lúc xuất, một lỗi xảy ra giữa chừng có thể tạo ra một tệp
nén hợp lệ về hình thức nhưng chứa dữ liệu không đầy đủ. Nếu xuất ra tệp đầy đủ
trước rồi mới nén, lỗi trong bước xuất sẽ được phát hiện ngay.

### 4.3 Kiểm tra tính toàn vẹn của bản sao lưu

Một cạm bẫy đã gặp: công cụ liệt kê nội dung của một bản sao lưu **không** phát
hiện được tệp bị cắt cụt. Nó đọc phần đầu tệp, thấy cấu trúc hợp lệ, và báo kết
quả bình thường.

Nghĩa là phép kiểm "liệt kê được nội dung" không đủ để kết luận bản sao lưu dùng
được. Phép kiểm đủ mạnh duy nhất là **thực sự khôi phục nó vào một nơi tạm và đối
chiếu kết quả** — tức là một cuộc diễn tập.

Vì vậy hệ thống có một chế độ diễn tập khôi phục: khôi phục bản sao lưu gần nhất
vào một cơ sở dữ liệu tạm, kiểm tra số lượng bản ghi ở các bảng chính, rồi xoá bỏ.
Đây là phép kiểm duy nhất trả lời được câu hỏi "bản sao lưu này có dùng được
không".

### 4.4 Nhiều bản, nhiều nơi

Nguyên tắc thông thường của sao lưu: một bản sao nằm cùng ổ đĩa với dữ liệu gốc
không bảo vệ được trước sự cố ổ đĩa. Hệ thống vì vậy giữ bản sao ở nhiều vị trí,
và có cơ chế mã hoá cho các bản sao được đưa ra ngoài.

Cần nêu đúng hiện trạng: cơ chế mã hoá và sao chép sang thiết bị khác đã được hiện
thực nhưng mặc định chưa bật. Việc mô tả một cơ chế "đã có" khác với việc mô tả nó
"đang hoạt động".

### 4.5 Quản lý dung lượng

Một sự cố đáng ghi: dung lượng ổ đĩa cạn kiệt do các tệp trung gian của hệ thống
container tích luỹ theo thời gian. Hệ quả không chỉ là không ghi được dữ liệu mới,
mà là dịch vụ quản lý container ngừng hoạt động, kéo theo toàn bộ hệ thống.

Hai bài học. Thứ nhất, các tệp trung gian ấy **không tự co lại** khi dữ liệu bên
trong bị xoá; cần thao tác nén lại tường minh. Thứ hai, dung lượng đĩa cần được
theo dõi chủ động với ngưỡng cảnh báo, vì khi nó cạn thì hậu quả lan rộng và việc
khắc phục cũng khó hơn — bản thân các công cụ khắc phục cũng cần chỗ trống để chạy.

---

## 5. Giám sát và cảnh báo

### 5.1 Phân tầng dữ liệu quan sát

Dữ liệu quan sát được chia theo mục đích sử dụng, vì mỗi loại có yêu cầu khác nhau
về khối lượng và thời gian lưu.

**Chỉ số định lượng** — các con số tổng hợp theo thời gian, dùng để vẽ đồ thị và
đặt ngưỡng cảnh báo. Khối lượng nhỏ, lưu dài.

**Nhật ký vận hành** — dòng sự kiện của các dịch vụ, dùng để chẩn đoán. Khối lượng
lớn, lưu ngắn hạn.

**Nhật ký kiểm toán** — vết của các thao tác nghiệp vụ trên dữ liệu, lưu trong cơ
sở dữ liệu quan hệ vì cần truy vấn có cấu trúc và cần giữ lâu dài.

Việc tách ba loại này quan trọng vì trộn chúng lại sẽ dẫn tới hoặc là chi phí lưu
trữ không kiểm soát được, hoặc là mất những vết cần giữ lâu.

### 5.2 Bẫy về số lượng nhãn phân loại

Một sai lầm phổ biến khi thu thập nhật ký là gắn quá nhiều nhãn phân loại có giá
trị đa dạng — chẳng hạn gắn định danh người dùng hoặc định danh yêu cầu làm nhãn.

Hệ quả là số tổ hợp nhãn bùng nổ, và hệ thống lưu trữ nhật ký phải tạo ra một
luồng dữ liệu riêng cho mỗi tổ hợp. Chi phí bộ nhớ và chi phí truy vấn tăng theo
cấp số nhân, và hệ thống giám sát trở thành nguồn tải chính thay vì công cụ hỗ trợ.

Nguyên tắc: nhãn phân loại chỉ dùng cho các giá trị có tập giá trị nhỏ và ổn định
— tên dịch vụ, mức độ nghiêm trọng, môi trường. Những thông tin đa dạng khác được
đưa vào phần nội dung có cấu trúc của bản ghi, nơi chúng vẫn tìm kiếm được nhưng
không tạo ra luồng riêng.

### 5.3 Cảnh báo phải tới được con người

Một hệ thống giám sát chỉ có giá trị nếu cảnh báo của nó đến được người có thể xử
lý. Với bối cảnh không có đội trực, kênh cảnh báo phải là kênh mà người vận hành
thực sự theo dõi.

Một chi tiết kỹ thuật đã gây mất cảnh báo: nội dung thông báo qua thư điện tử được
xử lý như văn bản thuần, nên phần định dạng được viết theo cú pháp đánh dấu sẽ
hiển thị nguyên dạng ký tự thay vì được diễn giải. Thông báo vẫn được gửi, nhưng
khó đọc tới mức dễ bị bỏ qua.

Bài học nhỏ nhưng đúng chủ đề của cả phần này: **một cơ chế an toàn hoạt động
đúng về mặt kỹ thuật vẫn có thể thất bại ở khâu tới được con người.**

### 5.4 Giá trị đặc biệt để tránh suy luận sai

Khi một chỉ số không đo được — chẳng hạn vì thành phần liên quan không phản hồi —
hệ thống ghi một giá trị đặc biệt thay vì ghi số không.

Lý do: số không là một giá trị hợp lệ có ý nghĩa riêng, và nếu dùng nó để biểu thị
"không đo được" thì đồ thị sẽ hiển thị một sự sụt giảm không có thật, và cảnh báo
sẽ kích hoạt sai. Một giá trị được quy ước rõ ràng là "không có dữ liệu" cho phép
cả người lẫn hệ thống cảnh báo phân biệt hai tình huống.

---

## 6. Triển khai trên nhiều máy

Hệ thống được thiết kế để triển khai trên các máy có cấu hình khác nhau, cụ thể là
có hoặc không có phần cứng tăng tốc tính toán.

Thay vì yêu cầu người triển khai chọn cấu hình đúng, kịch bản triển khai tự phát
hiện phần cứng hiện có và áp dụng cấu hình tương ứng. Lý do rất thực tế: việc chọn
sai cấu hình không gây lỗi ngay, mà dẫn tới hệ thống chạy chậm hoặc dịch vụ suy
diễn không khởi động được — những triệu chứng dễ bị quy cho nguyên nhân khác.

Kịch bản triển khai cũng thực hiện một loạt kiểm tra tiên quyết **trước khi** bắt
đầu dựng ảnh: tệp cấu hình có đầy đủ không, dung lượng đĩa còn bao nhiêu, các dịch
vụ phụ thuộc có sẵn sàng không. Việc phát hiện thiếu sót ở phút đầu tốt hơn nhiều
so với phát hiện sau hai mươi phút dựng ảnh.

---

## 7. Hạ tầng kiểm thử

### 7.1 Kiểm thử phải chạy trong môi trường giống môi trường thật

Bộ kiểm thử được chạy trong một container trên cùng mạng nội bộ với các dịch vụ
phụ thuộc, thay vì chạy trực tiếp trên máy phát triển.

Lý do là các phụ thuộc thực tế — cơ sở dữ liệu, bộ nhớ đệm, các thư viện xử lý ảnh
— có hành vi khác nhau giữa các hệ điều hành và các phiên bản. Một bộ kiểm thử
xanh trên máy phát triển nhưng không phản ánh môi trường triển khai chỉ tạo ra
niềm tin sai.

### 7.2 Các dạng thất bại giả

Trong quá trình phát triển, bộ kiểm thử nhiều lần báo đỏ hàng loạt vì những nguyên
nhân không liên quan tới mã nguồn. Ghi lại chúng có giá trị vì chúng lặp lại.

**Thư mục làm việc trôi.** Kịch bản chạy kiểm thử nạp tệp cấu hình theo đường dẫn
tương đối; khi được gọi từ một thư mục khác, nó nạp nhầm tệp và kết nối cơ sở dữ
liệu thất bại với thông báo khó hiểu. Cách khắc phục là dùng đường dẫn tuyệt đối
cho mọi tệp cấu hình.

**Hạ tầng biến mất giữa chừng.** Một lượt chạy dài bị gián đoạn vì các dịch vụ phụ
thuộc dừng giữa chừng, tạo ra hàng trăm lỗi trông như một hồi quy lớn về chức
năng. Dấu hiệu phân biệt là loại thông báo lỗi: lỗi kết nối và lỗi phân giải tên
chỉ ra vấn đề hạ tầng, không phải vấn đề mã nguồn.

**Kiểm thử ghi vào dữ liệu thật.** Việc dùng một bản sao cơ sở dữ liệu cho kiểm
thử không đủ, vì hệ thống còn ghi ra tệp. Một số phép kiểm thử đã tạo và xoá dữ
liệu trên kho tệp thật. Bài học: khi hệ thống có nhiều mặt phẳng lưu trữ, việc cô
lập môi trường kiểm thử phải bao phủ **tất cả** các mặt phẳng, không chỉ mặt phẳng
dễ thấy nhất.

**Kiểm thử trỏ vào cơ sở dữ liệu vận hành.** Sự cố nghiêm trọng nhất trong nhóm
này: một lượt chạy kiểm thử đã áp các thay đổi cấu trúc dở dang lên cơ sở dữ liệu
vận hành. Biện pháp khắc phục gồm hai lớp — một lớp từ chối chạy nếu tên cơ sở dữ
liệu trông giống cơ sở dữ liệu vận hành, và một lớp buộc mọi lượt chạy phải đi qua
một kịch bản chuẩn có sẵn các chốt chặn.

### 7.3 Nguyên lý: phân biệt đỏ thật với đỏ giả

Từ các tình huống trên rút ra một thực hành: khi bộ kiểm thử báo đỏ hàng loạt,
câu hỏi đầu tiên không phải "mã nào hỏng" mà là **"đây có phải hỏng thật không"**.

Dấu hiệu của đỏ giả thường là: số lượng thất bại lớn bất thường, các thất bại trải
đều trên những vùng chức năng không liên quan, và thông báo lỗi thuộc về tầng hạ
tầng chứ không phải tầng nghiệp vụ.

Phân biệt sớm tiết kiệm nhiều giờ chẩn đoán sai hướng.

---

## 8. Tổng kết các nguyên lý vận hành

**Cấu hình tồn tại không đồng nghĩa với cơ chế hoạt động.** Sao lưu đã cấu hình
nhưng chưa từng chạy, nhật ký đã ghi nhưng không ai đọc, cảnh báo đã gửi nhưng
không đọc được — cả ba đều tạo ra cảm giác an toàn không có cơ sở. Mỗi cơ chế an
toàn cần một phép kiểm chứng minh nó đang hoạt động.

**Sao lưu chưa diễn tập là sao lưu chưa tồn tại.** Phép kiểm duy nhất đủ mạnh là
thực sự khôi phục và đối chiếu.

**Khi sai sót có hậu quả không hồi phục, dựng chốt chặn kỹ thuật thay vì dựa vào
quy trình.** Con người sẽ nhầm; chốt chặn thì không.

**Thao tác an toàn phải thực sự an toàn.** Khởi động lại một dịch vụ không được
mang rủi ro mất dữ liệu; vì vậy các thay đổi cấu trúc một chiều phải tách khỏi
đường khởi động.

**Cảnh giác với những hỏng hóc không có triệu chứng.** Container chạy mã cũ, cấu
hình chồng lớp bị bỏ sót, tệp sao lưu bị cắt cụt — tất cả đều để hệ thống ở trạng
thái báo cáo bình thường. Với mỗi cơ chế thuộc loại này, cần một phép kiểm chủ
động chạy định kỳ.

**Khi kiểm thử báo đỏ hàng loạt, xác định đỏ thật hay đỏ giả trước khi chẩn
đoán.** Dấu hiệu nằm ở tầng phát sinh lỗi, không ở số lượng.
