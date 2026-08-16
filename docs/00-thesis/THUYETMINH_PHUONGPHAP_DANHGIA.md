# Thuyết minh phương pháp đánh giá

*Bản thuyết minh dạng luận văn cho phần mở đầu Chương 4. Trình bày cách thiết kế
phép đánh giá, lập luận cho từng lựa chọn phương pháp, và các quy tắc công bố kết
quả.*

---

## 1. Đánh giá cái gì, và vì sao không đánh giá độ chính xác mô hình

### 1.1 Đối tượng đánh giá là hạ tầng, không phải mô hình

Đề tài xây dựng một nền tảng thu thập và quản trị dữ liệu, không xây dựng một mô
hình nhận dạng mới. Việc huấn luyện, tối ưu và so sánh mô hình nằm ngoài phạm vi
đã cam kết.

Điều này định hình toàn bộ cách đánh giá. Câu hỏi trung tâm không phải *mô hình
nhận dạng đúng bao nhiêu phần trăm*, mà là *nền tảng có làm đúng những gì nó
tuyên bố hay không*.

Sự phân biệt này cần được giữ nghiêm ngặt, vì có một cám dỗ thường trực: đưa một
con số về độ chính xác vào báo cáo, vì nó dễ hiểu và trông thuyết phục. Nhưng một
con số như vậy sẽ được đọc như một tuyên bố về chất lượng mô hình, trong khi dữ
liệu và quy trình huấn luyện không được thiết kế để chứng minh điều đó.

### 1.2 Bốn trục đánh giá

Bốn trục dưới đây được chọn vì mỗi trục kiểm chứng một cam kết khác nhau của đề
tài, và vì cả bốn đều đo được bằng bằng chứng khách quan.

| Trục | Câu hỏi cần trả lời |
|---|---|
| Cách ly dữ liệu | Dữ liệu của một đơn vị có bị đơn vị khác truy cập được không? |
| Hiệu quả lưu trữ | Biểu diễn điểm mốc tiết kiệm dung lượng đến mức nào so với video? |
| Độ trễ dịch vụ | Hệ thống phản hồi trong bao lâu, ở điều kiện nào? |
| Toàn vẹn nguồn sự thật | Cơ chế ký số có phát hiện được thay đổi trái phép không? |

Ngoài bốn trục này, phần đánh giá còn bao gồm kiểm chứng tính đúng đắn chức năng
qua bộ kiểm thử tự động, và các rà soát hiện trạng đối với những cam kết mà việc
đo lường định lượng không phù hợp.

### 1.3 Vì sao bốn trục này, không phải bốn trục khác

Có thể hình dung nhiều trục khác — thông lượng, khả năng mở rộng theo số lượng
đơn vị, độ sẵn sàng. Chúng bị loại vì hai lý do.

**Thứ nhất, chúng không nằm trong cam kết.** Đề tài không hứa hẹn triển khai phân
tán quy mô lớn hay tự động co giãn tài nguyên. Đo những thứ không cam kết sẽ làm
loãng phần đánh giá và mở ra những câu hỏi mà công trình không có nghĩa vụ trả
lời.

**Thứ hai, điều kiện đo không cho phép kết luận có ý nghĩa.** Đo khả năng mở rộng
trên một máy đơn lẻ sẽ cho ra những con số đúng về mặt số học nhưng không nói gì
về hành vi của hệ thống ở quy mô thật.

Nguyên tắc chung: **chỉ đo những gì vừa được cam kết, vừa có điều kiện đo cho ra
kết luận đáng tin.**

---

## 2. Nguyên lý nền tảng: phép đo phải có khả năng thất bại

### 2.1 Phát biểu

Một phép đo chỉ mang thông tin nếu tồn tại một trạng thái của hệ thống khiến nó
cho kết quả xấu. Nếu phép đo cho kết quả tốt bất kể hệ thống ra sao, con số nó
sinh ra không nói lên điều gì.

Nghe hiển nhiên, nhưng vi phạm nguyên lý này rất khó nhận ra, vì kết quả sai vẫn
trông hoàn toàn hợp lệ.

### 2.2 Một ví dụ điển hình

Xét phép thử: *tài khoản của đơn vị A gửi yêu cầu đọc một tài nguyên của đơn vị
B; hệ thống trả về "không tìm thấy"; kết luận: cách ly hoạt động.*

Phép thử này có vẻ hợp lý. Nhưng nó cho cùng một kết quả trong ít nhất ba tình
huống khác hẳn nhau:

- Cách ly hoạt động đúng: hệ thống biết tài nguyên tồn tại nhưng từ chối tiết lộ.
- Tài nguyên của B không tồn tại: chưa có ai gieo dữ liệu cho B.
- Đường dẫn yêu cầu sai: tài nguyên nào cũng sẽ nhận phản hồi "không tìm thấy".

Trong hai tình huống sau, phép thử **không đo cách ly**, nhưng vẫn ghi nhận một
điểm đạt. Nếu toàn bộ bộ thử rơi vào tình huống thứ hai hoặc thứ ba, báo cáo sẽ
kết luận "không phát hiện vi phạm nào" trong khi thực tế chưa hề kiểm tra được gì.

### 2.3 Đối chứng dương như một điều kiện tiên quyết

Cách phòng ngừa là bổ sung một nhóm phép thử ngược chiều: chứng minh rằng **chủ
sở hữu hợp lệ thật sự thực hiện được** các thao tác tương ứng trên dữ liệu của
chính mình.

Nếu ngay cả chủ sở hữu cũng bị từ chối, thì mọi kết quả "đã bị chặn" ở nhóm đối
kháng đều vô nghĩa — không phân định được giữa *cách ly hoạt động* và *hệ thống
không đọc được gì*.

Quy tắc công bố suy ra từ đó: **nếu đối chứng dương không đạt, không được công bố
bất kỳ tỉ lệ nào từ lượt đo đó.** Kết quả phải được đánh dấu là không đủ điều kiện
công bố, chứ không phải làm tròn thành một con số đẹp.

### 2.4 Mở rộng sang các trục khác

Nguyên lý này áp dụng cho cả những trục không liên quan đến bảo mật.

Với phép đo hiệu quả lưu trữ, đối chứng tương ứng là: loại bỏ những mẫu mà quá
trình trích xuất đặc trưng thất bại. Một chuỗi toạ độ toàn số không sẽ nén xuống
gần như không còn gì, và nếu tính cả chúng thì tỉ lệ tiết kiệm sẽ được thổi phồng
bởi chính những trường hợp hệ thống hỏng.

Với phép đo đối chứng trên miền dùng chung, đối chứng hai chiều là bắt buộc: phải
chứng minh cả rằng thay đổi dữ liệu riêng **không** làm số liệu công khai đổi,
lẫn rằng thay đổi dữ liệu công khai **có** làm nó đổi. Chỉ có vế đầu thì một
điểm truy cập luôn trả về số không cũng sẽ được chấm là đạt.

---

## 3. Điều kiện đo và tính hợp lệ

### 3.1 Tách môi trường đo khỏi môi trường thí nghiệm

Các phép đo khác nhau đặt ra những yêu cầu mâu thuẫn lên môi trường.

Phép đo độ trễ cần một môi trường **ổn định và không bị can thiệp**: khối lượng
công việc không đổi, không có tiến trình khác tranh tài nguyên.

Phép thử cách ly, ngược lại, **cố ý thay đổi dữ liệu** — nó phải tạo, sửa và xoá
tài nguyên để kiểm chứng ranh giới.

Chạy hai loại này trên cùng một môi trường dẫn tới sai lệch có hệ thống, không
chỉ là nhiễu ngẫu nhiên. Kinh nghiệm thu được trong đề tài cho thấy khi tập dữ
liệu thử nghiệm được gắn vào môi trường đo, một điểm truy cập trả về danh sách
rỗng chuyển thành trả về danh sách có nội dung — cùng một địa chỉ, cùng một truy
vấn, nhưng khối lượng công việc thực tế khác hẳn. Con số độ trễ thu được vẫn trông
hoàn toàn bình thường.

Đây là dạng hỏng nguy hiểm hơn cả sự cố: khi môi trường sập, người đo nhận ra
ngay; khi khối lượng công việc bị thay đổi ngầm, phép đo vẫn cho ra một bảng số
đẹp cho một thứ không phải cái đang cần đo.

Nguyên tắc rút ra: **mỗi loại phép đo có môi trường riêng**, và mỗi kết quả đo
phải ghi kèm thông tin về khối lượng công việc thực tế — chẳng hạn số lượng phần
tử mà mỗi truy vấn trả về — để về sau không ai đọc một con số độ trễ mà không
biết nó ứng với tải nào.

### 3.2 Phép đo phải gắn với một phiên bản mã xác định

Kết quả đo chỉ có ý nghĩa khi xác định được nó đo trên phiên bản nào.

Việc này khó hơn vẻ ngoài vì hai lý do. Thứ nhất, một mã định danh trong hệ quản
lý mã nguồn chỉ chứng minh điểm xuất phát; nếu còn thay đổi chưa được ghi nhận
thì hai lần đo cùng mã định danh vẫn có thể chạy trên hai phiên bản khác nhau.
Thứ hai, môi trường thực thi thường được dựng sẵn từ trước, nên nó có thể đang
chạy một phiên bản cũ hơn phiên bản hiện có.

Thực hành được áp dụng gồm ba lớp:

- Chụp một dấu vân tay của toàn bộ mã nguồn tại thời điểm đo, độc lập với trạng
  thái của hệ quản lý mã.
- So sánh dấu vân tay của môi trường thực thi trước và sau mỗi lượt đo; nếu khác
  nhau, đánh dấu lượt đo là không hợp lệ thay vì tổng hợp kết quả.
- Kiểm lại dấu vân tay mã nguồn **ngay trước khi** phép đo bắt đầu, chứ không chỉ
  tin vào lần chụp lúc dựng môi trường.

Lớp thứ ba được bổ sung sau khi quan sát thấy mã nguồn thay đổi ngay trong lúc
đang đo. Dấu vân tay lúc dựng chỉ chứng minh môi trường được tạo từ đâu; nó không
chứng minh mã còn nguyên khi phép đo chạy.

### 3.3 Đóng băng trong lúc đo

Từ đó suy ra một quy tắc vận hành: giữa thời điểm đóng băng và thời điểm hoàn tất
phép đo, mã nguồn không được thay đổi. Nếu có thay đổi, toàn bộ lượt đo thuộc về
phiên bản cũ và phải làm lại từ đầu.

Đặc biệt, khi phép đo bộc lộ một vấn đề, phản ứng đúng là **ghi nhận nó như một
kết quả của chính phiên bản đang đo**, hoàn tất lượt đo, rồi mới quyết định sửa.
Sửa giữa chừng sẽ khiến báo cáo mô tả một phiên bản không tồn tại.

---

## 4. Quy tắc về công cụ đo

### 4.1 Công cụ đo cũng cần được kiểm chứng

Một phần đáng kể công sức đánh giá được dành cho việc kiểm chứng chính các công cụ
đo, chứ không phải hệ thống được đo. Lý do là các công cụ tự viết có xu hướng
sinh ra những con số hợp lệ cho những thứ chúng không thực sự đo.

Các dạng lỗi đã gặp có thể quy về một hình dạng chung: **công cụ đưa ra một kết
quả trông đúng cho một câu hỏi khác với câu hỏi được đặt ra.**

Vài minh hoạ:

- Địa chỉ đích được viết dưới dạng tên máy thay vì địa chỉ số, khiến mỗi yêu cầu
  phải qua một lần phân giải tên thất bại trước khi thành công. Con số độ trễ thu
  được lớn hơn thực tế nhiều lần, nhưng vẫn là một con số hợp lý về hình thức.
- Đường dẫn được viết theo trí nhớ chứ không đối chiếu với mô tả giao diện thực
  tế. Yêu cầu tới một địa chỉ không tồn tại nhận phản hồi "không tìm thấy", và
  phản hồi đó bị chấm là "đã bị chặn".
- Phản hồi báo hiệu vượt giới hạn tần suất bị tính là lỗi, khiến báo cáo cảnh báo
  ầm ĩ trong khi hệ thống đang hoạt động đúng thiết kế.
- Một phân vị đuôi được tính từ một số quan sát quá nhỏ, nên con số in ra thực
  chất là giá trị của một lượt duy nhất.

### 4.2 Các chốt chặn được đưa vào

Từ những lỗi đó, các công cụ đo được bổ sung một số cơ chế tự phát hiện:

- **Đối chiếu với mô tả giao diện thực tế** trước khi gửi yêu cầu, kiểm cả địa chỉ
  lẫn phương thức; sai thì dừng ngay thay vì ghi nhận một kết quả sai.
- **Phân loại lỗi theo bản chất**: lỗi tầng truyền tải, lỗi vượt giới hạn tần
  suất, và lỗi ứng dụng được tách riêng, vì chúng nói lên những điều khác nhau.
- **Yêu cầu số quan sát tối thiểu** cho các phân vị đuôi; không đủ thì báo giá trị
  không xác định thay vì in ra một con số vô nghĩa.
- **Ghi lại khối lượng công việc thực tế** của mỗi phép đo, để mỗi con số luôn đi
  kèm ngữ cảnh.

Nguyên tắc chung khi dựng công cụ đo: **đặt chốt chặn trước khi chạy, không phải
sau.** Một chốt chặn dựng sẵn thường tự trả công ngay ở lượt đo đầu tiên.

### 4.3 Cảnh giác với một chẩn đoán hợp lý nhưng chưa được chứng minh

Một bài học riêng đáng ghi lại. Khi một lượt đo xuất hiện nhiều lỗi tầng truyền
tải, một giải thích kỹ thuật hợp lý đã được đưa ra, kèm hai số liệu có thật hỗ trợ
cho nó. Giải thích ấy nghe thuyết phục.

Nhưng đối chiếu mốc thời gian cho thấy nguyên nhân thực sự là một sự kiện khác
hẳn, xảy ra ngay giữa lượt đo.

Bài học: **tương thích không phải nhân quả.** Một giải thích phù hợp với dữ liệu
quan sát được vẫn có thể sai. Khác biệt giữa một báo cáo sự cố đáng tin và một câu
chuyện nghe hợp lý nằm ở chỗ có bằng chứng trực tiếp hay chỉ có sự tương thích.

---

## 5. Quy tắc phát biểu kết quả

### 5.1 Giới hạn tuyên bố đúng phạm vi bằng chứng

Mỗi kết quả chỉ được phát biểu trong phạm vi mà phép đo thực sự bao phủ. Cụ thể
với bốn trục:

| Trục | Được nói | Không được nói |
|---|---|---|
| Cách ly | các đường giao tiếp đã khảo sát cưỡng chế ranh giới đơn vị, dưới đúng vai vận hành của ứng dụng | toàn hệ thống bảo đảm tuyệt đối không thể truy cập chéo |
| Lưu trữ | tỉ lệ đo được trên một tập mẫu có tên, tái lập được | tỉ lệ đo trên dữ liệu do chính hệ thống thu |
| Độ trễ | độ trễ trong môi trường có kiểm soát | đã chứng minh cô lập hiệu năng giữa các đơn vị |
| Toàn vẹn | phát hiện được thay đổi và từ chối theo hướng an toàn trong các tình huống đã thử | dữ liệu không thể bị sửa |

### 5.2 Tách "phép đo hợp lệ" khỏi "thuộc tính đạt"

Hai khái niệm này thường bị gộp, dẫn tới hiểu sai.

Một lượt đo có thể **hợp lệ** — thực thi đúng, cho kết quả xác định — mà vẫn phát
hiện ra rằng một thuộc tính mong đợi **không đạt**. Đó là một lượt đo thành công,
vì nó làm đúng việc của nó.

Ngược lại, một lượt đo cho toàn kết quả "đạt" có thể là một lượt đo hỏng, nếu nó
không có khả năng thất bại.

Vì vậy khi báo cáo cần tách hai trục: số kịch bản được thực thi và cho kết quả xác
định, và số kịch bản thoả thuộc tính mong đợi. Ghi "chín trên chín đạt" khi thực
tế là "chín kịch bản thực thi hợp lệ, tám thoả thuộc tính, một phát hiện giới
hạn" sẽ che mất phát hiện đáng giá nhất.

### 5.3 Trình bày kèm cỡ mẫu, khoảng phân bố và giao thức

Một con số đơn lẻ thường che mất chính hiện tượng đáng chú ý.

Chẳng hạn, dung lượng trung vị của một mẫu dữ liệu chỉ nói lên một phần; khoảng
từ phân vị thứ năm đến phân vị thứ chín mươi lăm cho thấy phân bố rộng gấp nhiều
lần, và sự rộng ấy có nguyên nhân kỹ thuật cụ thể — những chuỗi mà một tay vắng
mặt phần lớn thời gian sẽ nén tốt hơn hẳn.

Hình thức trình bày tối thiểu cho mỗi kết quả định lượng gồm ba thành phần: cỡ
mẫu, khoảng phân bố, và giao thức đo. Một con số không kèm ba thứ đó là thứ bị
chất vấn đầu tiên.

### 5.4 Tiêu chí đưa vào phải nêu trước, không giải thích sau

Khi một phép đo chỉ sử dụng một tập con của dữ liệu, tiêu chí chọn tập con ấy
phải được nêu rõ và phải được đặt ra **trước** khi nhìn kết quả.

Điều này phân biệt một tiêu chí hợp lệ với việc chọn lọc số liệu. Chẳng hạn, loại
bỏ những mẫu mà quá trình trích xuất thất bại là một tiêu chí **về tính hợp lệ của
phép trích xuất**, không phải về dung lượng — và nó khiến kết quả cuối cùng thấp
hơn, chứ không cao hơn.

Kết quả khi ấy phải được đọc kèm điều kiện: *mức giảm dung lượng với điều kiện
trích xuất thành công theo tiêu chí đã nêu*, chứ không phải một phát biểu phổ
quát.

### 5.5 Phân biệt chưa quan sát thấy vi phạm với có cơ chế ngăn vi phạm

Đây là phân biệt quan trọng nhất khi báo cáo về các thuộc tính bảo mật.

*Chưa quan sát thấy vi phạm* là nhận định về những gì đã kiểm tra; nó có thể đúng
đơn thuần vì chưa ai thử đúng cách.

*Có cơ chế ngăn vi phạm* là nhận định về cấu trúc hệ thống: tồn tại một ràng buộc
khiến vi phạm không xảy ra được.

Một phần của hệ thống có thể chưa từng bộc lộ vấn đề mà vẫn chưa có ràng buộc nào
bảo đảm. Mô tả nó như đã được bảo vệ là một suy diễn vượt quá bằng chứng, và là
loại lỗi mà người phản biện phát hiện dễ nhất.

---

## 6. Xử lý những cam kết không đo định lượng được

Không phải cam kết nào cũng phù hợp với một con số. Với những cam kết thuộc loại
"hệ thống có làm được việc này không", phương pháp phù hợp là **rà soát hiện
trạng** chứ không phải đo lường.

Rà soát hiện trạng phải đi hết chuỗi từ điểm khởi phát tới hệ quả bền vững, chứ
không dừng ở việc tìm thấy một đoạn mã có tên gọi phù hợp. Với một tác vụ nền
chẳng hạn, chuỗi ấy gồm: có nơi nào phát sinh yêu cầu không, tác vụ có được đăng
ký không, tiến trình nền có thực thi không, và có để lại thay đổi bền vững nào
không.

Kết quả rà soát nên dùng nhiều hơn hai mức, vì ép mọi thứ về "đạt / không đạt" sẽ
làm mất thông tin. Bốn mức đã được dùng trong đề tài:

- **Vận hành được** — đi hết chuỗi và có hệ quả bền vững.
- **Một phần** — có cơ chế nhưng chưa phủ hết, hoặc phạm vi khác với thiết kế
  đích.
- **Chưa vận hành** — có mã nhưng không được nối vào luồng nào.
- **Ngoài phạm vi triển khai** — chỉ tồn tại ở mức thiết kế.

Nguyên tắc đi kèm: **nếu một hạng mục chưa hoàn thiện, không thêm phần hiện thực
giả chỉ để đánh dấu là đã xong.** Ghi nhận trung thực một khoảng trống có giá trị
hơn một ô được đánh dấu mà không có gì phía sau.

---

## 7. Tổng kết phương pháp

Phương pháp đánh giá của đề tài có thể tóm lại trong bốn quy tắc:

1. **Chỉ đo những gì được cam kết và có điều kiện đo đáng tin.**
2. **Mỗi phép đo phải có khả năng cho kết quả xấu**; nếu không, nó không mang
   thông tin. Đối chứng dương là điều kiện tiên quyết, không phải bước bổ sung.
3. **Mỗi kết quả gắn với một phiên bản mã xác định**, một môi trường xác định, và
   một khối lượng công việc xác định.
4. **Mỗi phát biểu giới hạn đúng vào phạm vi bằng chứng bao phủ**, và phân biệt rõ
   giữa phép đo hợp lệ với thuộc tính đạt.

Bốn quy tắc này khiến phần đánh giá dài hơn và các con số công bố thường thấp hơn
so với cách làm thông thường. Đó là chủ đích: một kết quả khiêm tốn nhưng đứng
vững trước chất vấn có giá trị hơn một con số ấn tượng mà người phản biện có thể
bác bỏ bằng một câu hỏi về điều kiện đo.
