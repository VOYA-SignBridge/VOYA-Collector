# Thuyết minh kiến trúc và nghiệp vụ nền tảng CTU-SignBridge

*Bản thuyết minh dạng luận văn. Trình bày kiến trúc, luồng nghiệp vụ, lập luận
thiết kế, so sánh phương án và các nguyên lý rút ra. Các chi tiết cài đặt cụ thể
được để ở những tài liệu kỹ thuật riêng.*

---

## 1. Bối cảnh và bài toán

### 1.1 Vì sao một nền tảng, chứ không phải một tập dữ liệu

Nghiên cứu nhận dạng ngôn ngữ ký hiệu tiếng Việt gặp một trở ngại có tính hệ
thống: dữ liệu khan hiếm, phân tán, và phần lớn được thu theo từng đề tài riêng
lẻ. Mỗi nhóm nghiên cứu tự dựng quy trình thu, tự đặt quy ước đặt tên, tự lưu trữ
theo cách của mình. Kết quả là các bộ dữ liệu tuy cùng nói về một ngôn ngữ nhưng
không ghép được với nhau, và không kiểm chứng chéo được.

Cách tiếp cận thông thường — công bố một bộ dữ liệu tĩnh — chỉ giải quyết vấn đề
một lần. Bộ dữ liệu ấy sẽ lỗi thời, không mở rộng được, và không trả lời được câu
hỏi ai đã đóng góp mẫu nào, trong điều kiện gì, với sự đồng thuận đến đâu.

Luận văn này chọn hướng khác: xây dựng một **nền tảng thu thập và quản trị dữ
liệu** để nhiều đơn vị cùng đóng góp, mỗi đơn vị giữ quyền kiểm soát dữ liệu của
mình, và phần dùng chung được hình thành từ những đóng góp tường minh. Sản phẩm
không phải một bộ dữ liệu, mà là **hạ tầng sinh ra và duy trì các bộ dữ liệu**.

### 1.2 Ba yêu cầu định hình toàn bộ kiến trúc

Ba yêu cầu dưới đây không độc lập; chúng ràng buộc lẫn nhau và giải thích gần như
mọi quyết định kiến trúc về sau.

**Thứ nhất, nhiều đơn vị dùng chung một hệ thống nhưng dữ liệu phải tách bạch.**
Một trường học tham gia thu dữ liệu cần chắc chắn rằng dữ liệu của họ không lọt
sang đơn vị khác, kể cả do sơ suất lập trình. Đây không phải yêu cầu tiện nghi mà
là điều kiện để họ đồng ý tham gia.

**Thứ hai, dữ liệu phải dùng lại được cho nghiên cứu.** Một mô hình huấn luyện
hôm nay phải trả lời được: nó học từ đúng những mẫu nào, phiên bản nào, theo tiêu
chí chia tách nào. Nếu không, kết quả không tái lập và không so sánh được.

**Thứ ba, người ký giữ quyền đối với dữ liệu về chính mình.** Dữ liệu ngôn ngữ ký
hiệu gắn với cơ thể và cách biểu đạt của một người cụ thể. Quyền đồng thuận và
quyền rút lại phải là cơ chế vận hành được, không phải một điều khoản trên giấy.

### 1.3 Vì sao ba yêu cầu này khó thoả cùng lúc

Yêu cầu thứ nhất đẩy hệ thống về phía **tách biệt**: mỗi đơn vị một khoang kín.
Yêu cầu thứ hai đẩy về phía **dùng chung**: dữ liệu càng gộp được thì nghiên cứu
càng có giá trị. Yêu cầu thứ ba đặt lên trên cả hai một ràng buộc **có thể đảo
ngược**: một mẫu đã vào bộ dữ liệu vẫn phải rút ra được.

Kiến trúc trình bày dưới đây là một lời giải cho ba lực kéo ngược chiều đó.

---

## 2. Ba miền dữ liệu

Nền tảng phân biệt ba loại phạm vi dữ liệu, khác nhau về chủ sở hữu, về quyền
truy cập, và về cách dữ liệu đi vào.

### 2.1 Miền dữ liệu của tổ chức

Đây là phạm vi mặc định. Mỗi tổ chức tham gia — một trường, một trung tâm, một
nhóm nghiên cứu — có một miền dữ liệu riêng. Mọi dữ liệu thu trong miền ấy thuộc
về tổ chức ấy, không cần ai tuyên bố thêm.

Nguyên tắc mặc định phát biểu như sau:

> Dữ liệu được thu nhận trong phạm vi của một tổ chức thì thuộc về tổ chức đó.

Câu này có vẻ hiển nhiên, nhưng nó loại bỏ một lớp lỗi rất khó phát hiện: dữ liệu
được tạo ra mà không rõ thuộc về ai, rồi mặc định rơi về một phạm vi chung nào
đó. Khi ấy ranh giới sở hữu bị xói mòn dần, và không ai nhận ra cho tới lúc cần
xoá hoặc cần trả lời về nguồn gốc.

### 2.2 Miền dùng chung

Bên cạnh các miền riêng, nền tảng có một **miền dùng chung** — nơi chứa dữ liệu
mà cộng đồng được phép sử dụng. Miền này tồn tại vì mục tiêu học thuật của đề
tài: nếu mọi dữ liệu đều đóng kín trong từng tổ chức thì nền tảng chỉ là một tập
hợp các kho rời rạc, không tạo ra giá trị chung nào.

Điểm mấu chốt, và cũng là chỗ dễ hiểu sai nhất: **miền dùng chung không phải là
một cửa sổ nhìn xuyên qua mọi tổ chức.** Nó là một phạm vi độc lập, chỉ chứa dữ
liệu đã đi vào nó bằng một trong hai con đường tường minh:

- **Đóng góp trực tiếp** — người dùng chủ động đóng góp cho cộng đồng ngay từ
  đầu, không qua một tổ chức trung gian nào.
- **Tổ chức chủ động công bố** — một tổ chức chọn một số tài nguyên trong kho
  riêng của mình và công bố chúng ra miền dùng chung.

Ở con đường thứ hai, quyền sở hữu **không chuyển giao**. Tổ chức công bố chỉ cấp
quyền sử dụng đối với một tài nguyên cụ thể, ở một phiên bản cụ thể; bản gốc vẫn
thuộc về họ, và họ vẫn có quyền thu hồi trạng thái công bố.

Hệ quả quan trọng: nếu một tổ chức có một nghìn mẫu và công bố một trăm, thì miền
dùng chung nhìn thấy **đúng một trăm mẫu ấy**. Chín trăm mẫu còn lại không trở
nên khả kiến chỉ vì một trăm mẫu kia đã được công bố.

### 2.3 Miền danh mục hệ thống

Loại thứ ba thường bị gộp nhầm vào miền dùng chung, nhưng bản chất khác hẳn. Đây
là các danh mục do nền tảng quản trị: danh sách ngôn ngữ, danh sách vùng miền,
các hồ sơ cấu hình, các bảng phân loại chuẩn. Mọi tổ chức đều tham chiếu đến
chúng, nhưng chúng **không phải dữ liệu được đóng góp**.

Sự phân biệt này không phải chuyện chữ nghĩa. Dữ liệu đóng góp cần đồng thuận,
cần ghi công, cần giấy phép sử dụng, và cần rút lại được. Danh mục hệ thống không
cần thứ nào trong số đó. Gộp hai loại vào một chỗ sẽ dẫn tới hoặc là áp đặt thủ
tục đồng thuận lên một bảng cấu hình, hoặc — nguy hiểm hơn — bỏ qua thủ tục đồng
thuận cho dữ liệu thật.

### 2.4 Bảng đối chiếu ba miền

| | Chủ sở hữu | Đi vào bằng cách nào | Ai đọc được |
|---|---|---|---|
| Miền tổ chức | Tổ chức thu dữ liệu | Mặc định, khi thu trong phạm vi tổ chức | Chỉ thành viên tổ chức, theo quyền |
| Miền dùng chung | Nền tảng, thay mặt cộng đồng | Đóng góp trực tiếp, hoặc tổ chức công bố | Theo chính sách công khai |
| Danh mục hệ thống | Nền tảng | Do quản trị viên hệ thống định nghĩa | Mọi tổ chức tham chiếu |

---

## 3. Vòng đời dữ liệu

Phần này mô tả hành trình của một mẫu dữ liệu, từ lúc một người thực hiện động
tác ký hiệu cho tới lúc nó góp phần vào một mô hình nhận dạng.

### 3.1 Thu nhận

Nền tảng cung cấp hai đường thu.

**Thu trực tiếp qua trình duyệt.** Người ký ngồi trước máy tính có camera, thực
hiện động tác, và hệ thống ghi lại. Đường này phù hợp với các buổi thu có tổ
chức, khi có người hướng dẫn khung hình và kiểm tra chất lượng tại chỗ.

**Tải lên tệp video.** Người dùng gửi lên các video đã quay sẵn. Đường này phù
hợp với dữ liệu có từ trước, hoặc khi việc thu diễn ra ở nơi không có kết nối
ổn định.

Hai đường khác nhau về trải nghiệm nhưng hội tụ về cùng một biểu diễn dữ liệu, và
— điều quan trọng hơn — **cả hai đều mang theo thông tin về phạm vi tổ chức xuyên
suốt**, từ lúc gửi yêu cầu cho tới khi dữ liệu nằm yên trong cơ sở dữ liệu, trong
tệp danh mục, trong kho tệp, và trong các tác vụ nền xử lý sau đó.

Yêu cầu "xuyên suốt" này nghe đơn giản nhưng là nơi phát sinh nhiều lỗi nhất.
Một tác vụ nền chạy tách khỏi yêu cầu gốc rất dễ mất ngữ cảnh, và khi mất thì
cám dỗ tự nhiên là đoán — chẳng hạn dò tìm trong toàn kho xem tài nguyên này
thuộc về ai. Nền tảng đặt ra nguyên tắc ngược lại: **thiếu ngữ cảnh thì dừng, chứ
không đoán.**

### 3.2 Biểu diễn dữ liệu — vì sao không lưu video

Đây là quyết định thiết kế có ảnh hưởng rộng nhất.

Thay vì lưu video, hệ thống trích xuất **toạ độ các điểm mốc bàn tay** ngay tại
trình duyệt của người dùng, rồi chỉ gửi lên chuỗi toạ độ ấy. Video gốc không bao
giờ rời khỏi máy người dùng.

Lập luận cho lựa chọn này có ba tầng.

**Tầng dung lượng.** Một chuỗi toạ độ nhỏ hơn video tương ứng hàng chục lần. Phép
đo ghép cặp trên các đoạn ký hiệu thật cho thấy mức giảm khoảng **chín mươi hai
phần trăm** trên tổng dung lượng. Với một nền tảng dự kiến tích luỹ hàng chục
nghìn mẫu từ nhiều đơn vị, khác biệt này quyết định việc hệ thống có vận hành nổi
trên hạ tầng của một trường đại học hay không.

**Tầng băng thông.** Việc trích xuất diễn ra tại máy người dùng nghĩa là chi phí
tính toán được phân tán, và đường truyền chỉ tải một lượng dữ liệu nhỏ. Điều này
quan trọng với bối cảnh triển khai thực tế, nơi đường truyền không phải lúc nào
cũng tốt.

**Tầng phơi bày thông tin.** Biểu diễn điểm mốc không giữ lại diện mạo, trang
phục, hay bối cảnh phòng thu. Mức phơi bày hình ảnh trực tiếp vì thế thấp hơn
đáng kể so với lưu video.

Cần nói rõ giới hạn của tầng thứ ba, vì đây là chỗ rất dễ tuyên bố quá. **Biểu
diễn điểm mốc không đồng nghĩa với ẩn danh.** Chuỗi toạ độ vẫn liên kết với danh
tính người đóng góp, với phiên thu, với siêu dữ liệu; và bản thân dáng ký hiệu là
một đặc trưng cá nhân. Chính vì vậy hệ thống vẫn duy trì cơ chế đồng thuận và rút
đồng thuận — nếu dữ liệu đã ẩn danh thật thì những cơ chế ấy không có đối tượng
để áp dụng.

### 3.3 Chuẩn hoá và phân đoạn

Một đoạn video thô chưa dùng được ngay. Nó cần đi qua vài bước biến đổi.

**Phân đoạn theo cửa sổ thời gian.** Một đoạn quay có thể chứa nhiều lần thực
hiện cùng một ký hiệu, xen kẽ với những khoảng người ký chuẩn bị hoặc hạ tay.
Hệ thống cắt đoạn quay thành các cửa sổ có độ dài cố định, trượt theo một bước
nhất định.

Việc cắt không thuần cơ học. Mỗi cửa sổ được chấm theo hai tiêu chí: **mức độ đầy
đủ** — tỉ lệ khung hình thực sự phát hiện được bàn tay — và **mức độ hoạt động** —
biên độ thay đổi giữa các khung liên tiếp. Cửa sổ nào không đạt ngưỡng sẽ bị loại.
Hệ thống cũng nhận biết đoạn kết thúc khi tay đã hạ, để không sinh ra những cửa
sổ rỗng ở cuối.

Một chi tiết đáng lưu ý về mặt phương pháp: hệ thống giữ lại một nhóm nhỏ các cửa
sổ tốt nhất, để trong trường hợp toàn bộ đoạn quay không sinh đủ số mẫu tối
thiểu thì còn có thể bù. Đây là sự cân bằng giữa hai rủi ro: quá khắt khe thì mất
dữ liệu của một buổi thu công phu, quá dễ dãi thì đưa nhiễu vào bộ dữ liệu.

**Tăng cường dữ liệu.** Từ mỗi cửa sổ hợp lệ, hệ thống sinh thêm một số biến thể
bằng các phép biến đổi hình học nhẹ. Mục đích là tăng khả năng khái quát của mô
hình mà không cần thu thêm dữ liệu thật. Hệ số tăng cường cho dữ liệu tải lên
được cấu hình tách khỏi hệ số cho dữ liệu thu trực tiếp, vì hai nguồn có đặc tính
khác nhau.

### 3.4 Tổ chức và phiên bản hoá

Dữ liệu sau chuẩn hoá được tổ chức theo một hệ phân cấp phân loại: ngôn ngữ,
phương ngữ, vùng miền, và lớp ký hiệu. Điểm cần nhấn mạnh là **vùng miền là một
phần của định danh lớp**, không phải một thuộc tính mô tả gắn thêm. Hai biến thể
của cùng một từ ở hai vùng khác nhau là hai lớp khác nhau, vì chúng khác nhau về
động tác và mô hình phải phân biệt được.

Trên hệ phân loại ấy, nền tảng dựng khái niệm **phiên bản bộ dữ liệu**. Một phiên
bản là một ảnh chụp bất biến: danh sách chính xác các mẫu tham gia, cùng thông
tin về cách chia tách tập huấn luyện và tập kiểm thử.

Vì sao cần phiên bản hoá thay vì huấn luyện thẳng trên trạng thái hiện tại? Vì
trạng thái hiện tại luôn thay đổi — có mẫu mới được thêm, có mẫu bị đánh dấu xoá,
có nhãn được sửa. Một mô hình huấn luyện trên "dữ liệu hiện có" không trả lời
được câu hỏi cơ bản nhất của nghiên cứu tái lập: *dữ liệu ấy chính xác là gì*.

Quan hệ đúng phải là một chuỗi truy vết được:

> phiên bản mô hình → công việc huấn luyện → phiên bản bộ dữ liệu

chứ không phải quan hệ mờ giữa "mô hình" và "dữ liệu".

### 3.5 Huấn luyện và quản lý mô hình

Một công việc huấn luyện nhận đầu vào là một phiên bản bộ dữ liệu đã cố định,
cộng với cấu hình huấn luyện. Kết quả sinh ra không chỉ là một tệp trọng số, mà
là một **artifact có phiên bản**, đi kèm những thông tin cần thiết để dùng lại:
cấu hình kiến trúc, bảng ánh xạ nhãn, các chỉ số đánh giá, và bản kê khai nội
dung.

Bảng ánh xạ nhãn phải đi cùng trọng số, đây là điểm dễ sai. Nếu một mô hình được
huấn luyện khi hệ thống có hai mươi lớp, rồi sau đó danh mục lớp thay đổi, thì
việc suy diễn bằng bảng nhãn hiện tại sẽ cho ra kết quả sai một cách âm thầm — mô
hình trả về đúng chỉ số, nhưng chỉ số ấy được dịch sang sai tên lớp.

### 3.6 Phân biệt phiên bản mới nhất với phiên bản đang phục vụ

Đây là một nguyên lý nhỏ nhưng có giá trị vận hành lớn.

Trong quản lý mô hình, cần tách bạch hai khái niệm:

- **Phiên bản mới nhất** — bản được tạo ra sau cùng.
- **Phiên bản đang phục vụ** — bản hiện được chọn để suy diễn.

Hai giá trị này không nhất thiết trùng nhau, và việc chúng khác nhau là **hợp
lệ**. Khi một mô hình mới bộc lộ suy giảm chất lượng, người quản trị cần quay về
bản trước. Thao tác đúng là **đổi con trỏ phục vụ**, không phải xoá bản mới.

Phân biệt này quan trọng vì nó biến việc quay lui từ một thao tác phá huỷ thành
một thao tác lựa chọn. Lịch sử được giữ nguyên; chỉ quyết định "dùng bản nào" thay
đổi. Và vì đó là một quyết định quản trị, nó cần được ghi nhật ký: ai thực hiện,
lúc nào, từ bản nào sang bản nào, vì lý do gì.

### 3.7 Nhận dạng

Nền tảng cung cấp một mô-đun nhận dạng thời gian thực như một minh chứng ở hạ
nguồn: dữ liệu thu được thực sự dùng được.

Luồng xử lý đi từ camera, qua bước trích xuất điểm mốc tại trình duyệt, tới một
dịch vụ suy diễn tách biệt, rồi trả về nhãn đã được phân giải sang dạng người đọc
hiểu được.

Việc tách dịch vụ suy diễn ra khỏi ứng dụng chính là một lựa chọn có chủ đích.
Suy diễn là tác vụ nặng và có đặc tính tải khác hẳn các thao tác quản trị dữ
liệu; để chung một tiến trình thì một lượt suy diễn chậm sẽ chiếm mất tài nguyên
của đường tải dữ liệu lên. Tách ra cũng cho phép bố trí phần cứng khác nhau cho
hai loại công việc.

Cần nêu đúng phạm vi: mô-đun này phục vụ hai miền từ vựng có mô hình đã đăng ký,
không phải nhận dạng ngôn ngữ ký hiệu tổng quát. Nó là minh chứng tính khả dụng,
không phải một đóng góp về mô hình — việc huấn luyện và tối ưu mô hình nằm ngoài
phạm vi đề tài.

---

## 4. Hai mặt phẳng lưu trữ và bài toán nhất quán

### 4.1 Vì sao có hai mặt phẳng

Hệ thống lưu dữ liệu ở hai nơi song song: một cơ sở dữ liệu quan hệ, và một tập
các tệp danh mục dạng bảng cùng các tệp dữ liệu trên đĩa.

Sự tồn tại của hai mặt phẳng là kết quả của lịch sử phát triển: phiên bản đầu của
hệ thống dùng tệp làm nguồn chính, vì nó đơn giản, dễ mang đi, và dễ kiểm tra
bằng mắt. Cơ sở dữ liệu được đưa vào sau, để phục vụ truy vấn và các ràng buộc
toàn vẹn.

Cấu hình này có ưu điểm thật. Tệp danh mục dễ sao lưu, dễ chuyển giao cho nhóm
nghiên cứu khác, và không phụ thuộc vào một máy chủ cơ sở dữ liệu đang chạy. Với
một đề tài học thuật cần công bố dữ liệu, đó là lợi thế đáng kể.

### 4.2 Rủi ro của cấu hình này

Nhưng hai mặt phẳng tạo ra một rủi ro có tính hệ thống, và nó là bài học đáng giá
nhất của đề tài về mặt kỹ thuật.

Cơ chế kiểm soát truy cập theo dòng của cơ sở dữ liệu là một công cụ mạnh: một
truy vấn **quên bộ lọc phạm vi** vẫn chỉ trả về dữ liệu thuộc phạm vi hiện hành,
nên một lớp sơ suất phổ biến của tầng ứng dụng được chặn ở tầng dưới.

Cần phát biểu chính xác mức bảo đảm này, vì nó dễ bị nói quá. Cơ chế ấy **không**
độc lập hoàn toàn với tầng ứng dụng: bản thân **danh tính phạm vi** là do tầng
ứng dụng thiết lập. Cơ sở dữ liệu cưỡng chế "chỉ thấy dòng thuộc phạm vi đang
khai báo"; nó không tự kiểm chứng được phạm vi khai báo ấy có đúng với người dùng
đã xác thực hay không.

Nói cách khác: cơ chế này chặn *truy vấn viết sai*, không chặn *ngữ cảnh bị đặt
sai*. Đây là hai loại lỗi khác nhau, và chỉ loại thứ nhất được tầng dưới đỡ.

Ngoài ra, nó **chỉ biết đến cơ sở dữ liệu**. Nó không biết gì về các tệp trên đĩa.

Nghĩa là: một đường đọc đi qua cơ sở dữ liệu thì được bảo vệ, còn một đường đọc đi
qua tệp danh mục thì không — trừ khi mã ứng dụng tự lọc. Và nếu ai đó viết một
hàm đọc tệp mà quên lọc theo tổ chức, lỗ hổng ấy không có cơ chế nào ở tầng dưới
bắt được.

Điều làm rủi ro này khó phát hiện là nó **không gây ra triệu chứng**. Hệ thống
chạy bình thường, không báo lỗi, không chậm đi. Chỉ khi có người chủ động thử đọc
dữ liệu của đơn vị khác thì mới lộ ra.

### 4.3 Cách xử lý và bài học rút ra

Hướng xử lý là đặt cổng kiểm soát ngay tại các hàm đọc tệp ở tầng thấp nhất: các
hàm này bắt buộc phải nhận thông tin về phạm vi tổ chức, và **từ chối hoạt động
nếu không có**. Không có đường lùi, không có giá trị mặc định.

Điểm tinh tế: từ chối khi thiếu ngữ cảnh phải là **lỗi ồn ào**, không phải trả về
tập rỗng. Trả về tập rỗng nghe có vẻ an toàn hơn, nhưng nó tạo ra một dạng hỏng
tệ hơn — hệ thống báo "không có dữ liệu" trong khi thực tế là "không biết được
phép xem dữ liệu nào". Người vận hành sẽ đi tìm nguyên nhân ở dữ liệu thay vì ở
phân quyền.

Nhưng đặt cổng ở tầng thấp cũng sinh ra một rủi ro đối xứng, và đây là bài học
thứ hai: **một bản vá bảo mật chưa hoàn tất có thể biến thành sự cố khả dụng.**
Khi các hàm ở tầng thấp bắt đầu đòi hỏi ngữ cảnh mà những nơi gọi chúng chưa được
cập nhật, thì người dùng hợp lệ cũng bị từ chối. Về mặt hiện tượng, người dùng
thấy hệ thống hỏng; về mặt bảo mật, không có gì được cải thiện cho tới khi toàn
bộ chuỗi gọi được chuyển đổi.

Hệ quả về phương pháp: một thay đổi kiểu này phải được xem là **một cuộc chuyển
đổi có kiểm soát**, với danh sách những nơi cần sửa được liệt kê rõ và kiểm tra
được tự động, chứ không phải một lần sửa hai hàm rồi coi là xong.

### 4.4 Hai mức cách ly, và mức nào là phạm vi đánh giá

Việc phát biểu "hệ thống cách ly dữ liệu giữa các đơn vị" chỉ có nghĩa khi nói rõ
**cách ly trước kẻ tấn công nào**. Có hai mức, khác nhau về giả định.

**Mức thứ nhất — cách ly trước người dùng của giao diện lập trình.** Kẻ tấn công
là một người dùng hợp lệ của hệ thống: họ gọi các đường giao tiếp với định danh
của đơn vị khác, đoán mã tài nguyên, sửa tham số, hoặc lợi dụng một truy vấn quên
lọc phạm vi. Họ **không** có thông tin đăng nhập vào cơ sở dữ liệu và **không**
thực thi được câu lệnh tuỳ ý.

Ở mức này, cơ chế kiểm soát theo dòng phát huy đúng vai trò: ứng dụng xác thực
người dùng, thiết lập ngữ cảnh, và từ đó mọi truy vấn — kể cả truy vấn viết thiếu
điều kiện lọc — đều bị giới hạn trong phạm vi ấy.

**Mức thứ hai — cách ly trước một vai cơ sở dữ liệu bị chiếm dụng.** Kẻ tấn công
thực thi được câu lệnh tuỳ ý dưới chính vai mà ứng dụng dùng.

Ở mức này hệ thống **không** bảo đảm được, và lý do mang tính cấu trúc chứ không
phải một lỗi có thể vá: ngữ cảnh phạm vi là một giá trị do phiên kết nối tự khai
báo. Một vai thực thi được câu lệnh tuỳ ý thì cũng khai báo được mình thuộc phạm
vi nào. Việc siết thêm các cơ chế phụ trợ không thay đổi điều đó, vì chúng nằm ở
cánh cửa thứ hai, còn danh tính phạm vi là cánh cửa thứ nhất.

**Phạm vi đánh giá của đề tài là mức thứ nhất.** Đây là mức phù hợp với mô hình đe
doạ thực tế của một nền tảng nhiều đơn vị dùng chung, nơi người dùng tương tác qua
giao diện lập trình chứ không có quyền truy cập cơ sở dữ liệu.

Vì vậy các phát biểu sau **không** được dùng:

> ~~Cách ly được cưỡng chế tại tầng cơ sở dữ liệu và không phụ thuộc tính đúng đắn
> của tầng ứng dụng.~~
>
> ~~Ngay cả khi vai cơ sở dữ liệu của ứng dụng bị chiếm, dữ liệu của đơn vị khác
> vẫn an toàn.~~

Phát biểu đúng:

> Ngữ cảnh phạm vi được xác lập từ danh tính và tư cách thành viên đã xác thực ở
> tầng ứng dụng; sau đó cơ sở dữ liệu cưỡng chế phạm vi hàng một cách độc lập tại
> tầng của nó, nhờ đó truy vấn thiếu bộ lọc hoặc truy cập tài nguyên của đơn vị
> khác bị từ chối mặc định, và hệ thống hỏng-thì-đóng khi thiếu ngữ cảnh.

Về việc tách vai vận hành khỏi vai quản trị lược đồ, chỉ phát biểu phần chứng minh
được:

> Vai chạy ứng dụng không có đặc quyền tối cao, không có quyền bỏ qua kiểm soát
> theo dòng, và không có quyền thay đổi lược đồ; nên nó không thể trực tiếp vô
> hiệu hoá cơ chế kiểm soát bằng các đặc quyền đó.

Không mở rộng thành "không tự thu hồi được bảo đảm": vai ấy tuy không tắt được cơ
chế, nhưng đổi được chính đầu vào mà cơ chế tin cậy.

### 4.5 Nguyên lý: dữ liệu gieo phải nhất quán trên mọi mặt phẳng

Từ hai mặt phẳng nảy ra một yêu cầu cho công tác kiểm thử và đo đạc. Khi dựng một
tập dữ liệu thử nghiệm, nó phải tồn tại **đồng thời và khớp nhau** ở cả cơ sở dữ
liệu, tệp danh mục, và tệp trên đĩa.

Nếu chỉ gieo vào một mặt phẳng, mọi phép thử sẽ cho kết quả trông như thành công
nhưng vô nghĩa. Chẳng hạn, một phép thử "người dùng của đơn vị A không đọc được
dữ liệu của đơn vị B" sẽ đạt — nhưng nó đạt vì dữ liệu ấy không tồn tại ở nơi hệ
thống đi tìm, chứ không phải vì cơ chế cách ly hoạt động.

Vì cơ sở dữ liệu và hệ tệp không nằm chung một giao dịch nguyên tử, việc gieo dữ
liệu phải theo một **giao thức có bù trừ**: dựng tệp trước, ghi cơ sở dữ liệu sau,
đọc lại để đối chiếu ba nguồn, và chỉ khi tất cả khớp mới đánh dấu tập dữ liệu là
dùng được. Hỏng ở bất kỳ bước nào thì phải dọn sạch những gì đã tạo, và tuyệt đối
không để lại dấu hiệu "sẵn sàng".

---

## 5. Xử lý bất đồng bộ

### 5.1 Vì sao cần

Các công việc như trích xuất đặc trưng từ video, đồng bộ lên kho lưu trữ đám mây,
hay huấn luyện mô hình đều mất từ vài giây tới vài giờ. Bắt người dùng chờ là
không khả thi.

Hệ thống vì thế tách các công việc này ra một hàng đợi, do các tiến trình nền xử
lý. Người dùng gửi yêu cầu, nhận phản hồi ngay, và công việc thật chạy phía sau.

### 5.2 Bốn nhóm công việc

**Thu nhận và xử lý.** Nhận video, trích xuất điểm mốc, phân đoạn, tăng cường, và
lưu kết quả. Đây là công việc nặng nhất.

**Đồng bộ kho lưu trữ.** Tải tệp lên kho đám mây, xuất dữ liệu ra bảng tính, đồng
bộ danh mục, dọn dẹp các tệp không còn dùng.

**Bảo trì định kỳ.** Đối soát giữa các mặt phẳng lưu trữ, tổng hợp số liệu sử
dụng, dọn dữ liệu hết hạn.

**Huấn luyện.** Chạy công việc huấn luyện và lưu kết quả.

### 5.3 Hai nguyên lý về độ tin cậy

Từ việc rà soát các luồng bất đồng bộ, hai nguyên lý nổi lên.

**Thử lại và tính bất biến khi lặp phải đi cùng nhau.** Một công việc có cơ chế
thử lại mà không bảo đảm tính bất biến khi thực thi nhiều lần thì chính cơ chế
thử lại trở thành nguồn hỏng: một lượt tải lên thành công nhưng bước ghi nhận
sau đó thất bại sẽ khiến toàn bộ công việc chạy lại, và lần chạy thứ hai tạo ra
một bản sao thừa.

Cách phòng tránh là làm cho mỗi công việc **nhận diện được rằng phần việc của
mình đã hoàn thành**: bằng một khoá định danh dẫn xuất từ nội dung, bằng thao tác
ghi đè thay vì thêm mới, hoặc bằng một phép kiểm tra sự tồn tại trước khi tạo.

Nguyên lý này áp dụng không đều trong hệ thống hiện tại. Các thao tác cập nhật
siêu dữ liệu theo khoá chính là bất biến khi lặp; các thao tác tạo tài nguyên mới
và tải đối tượng lên kho đám mây thì chưa.

**Thử lại phải được đặt ở nơi lỗi có tính thoáng qua.** Lỗi mạng khi gọi dịch vụ
bên ngoài đáng thử lại; lỗi do dữ liệu đầu vào sai thì thử lại bao nhiêu lần cũng
vậy. Đặt cơ chế thử lại lên nhóm thứ hai chỉ làm chậm việc phát hiện vấn đề.

### 5.4 Đánh đổi: gộp các bước xử lý vào một công việc

Trong hệ thống hiện tại, các bước phân đoạn và tăng cường nằm **bên trong** công
việc thu nhận, chứ không phải các công việc độc lập.

Cách này có ưu điểm: dữ liệu trung gian không cần lưu ra ngoài rồi đọc lại, nên
nhanh hơn và ít điểm hỏng hơn. Với khối lượng hiện tại, đó là lựa chọn hợp lý.

Nhưng nó cũng có cái giá phải nói rõ: không thể chạy lại riêng bước tăng cường mà
không chạy lại toàn bộ quá trình từ video gốc; và không thể phân bổ tài nguyên
khác nhau cho từng bước. Vì vậy không nên mô tả hệ thống như một dây chuyền bốn
chặng điều phối độc lập — nó là bốn năng lực, thực thi trong hai nhóm công việc.

---

## 6. Nguồn sự thật và tính toàn vẹn dữ liệu

### 6.1 Bài toán

Khi nhiều máy cùng tham gia chuẩn bị dữ liệu, cần một câu trả lời dứt khoát cho
câu hỏi: **phiên bản nào là phiên bản đúng?**

Nếu không có cơ chế, tình huống điển hình sẽ là: hai máy cùng sửa danh mục, mỗi
máy có một bản khác nhau, và khi đồng bộ thì bản đến sau ghi đè bản đến trước
một cách âm thầm.

### 6.2 Cách tiếp cận

Hệ thống áp dụng mô hình **một nguồn sự thật có ký số**. Mỗi phiên bản dữ liệu
được đóng gói cùng một bản kê khai liệt kê các tệp thành phần và giá trị băm của
từng tệp. Bản kê khai ấy được ký bằng khoá riêng của máy phát hành.

Phía nhận thực hiện bốn phép kiểm trước khi chấp nhận:

1. **Toàn vẹn nội dung** — giá trị băm thực tế của từng tệp có khớp bản kê khai
   không.
2. **Hợp lệ chữ ký** — chữ ký có đúng với nội dung bản kê khai không.
3. **Thẩm quyền người ký** — chữ ký ấy thuộc về một máy đã được đăng ký hay không.
4. **Chính sách phiên bản** — phiên bản này có được phép thay thế phiên bản hiện
   hành không.

### 6.3 Vì sao phép kiểm thứ ba không thể thiếu

Ba phép kiểm đầu thường bị nhầm là đủ, nhưng chúng không tương đương nhau.

Một người có ý đồ xấu hoàn toàn có thể dựng một bộ dữ liệu khác, tính giá trị băm
đúng cho nó, viết một bản kê khai hợp lệ, rồi ký bằng khoá **của chính họ**. Chữ
ký ấy hợp lệ về mặt toán học. Nếu hệ thống chỉ hỏi "chữ ký có hợp lệ không" mà
không hỏi "hợp lệ theo khoá của ai", thì tính toàn vẹn được bảo đảm nhưng **thẩm
quyền thì không**.

Nói cách khác: toàn vẹn trả lời câu hỏi *nội dung có bị sửa không*; thẩm quyền
trả lời câu hỏi *ai có quyền nói rằng đây là bản đúng*. Hai câu hỏi khác nhau, và
một hệ thống nguồn sự thật phải trả lời được cả hai.

### 6.4 Giới hạn phải nêu: bằng chứng giả mạo, không phải chống giả mạo

Cơ chế băm và ký số cung cấp **bằng chứng giả mạo**: nếu dữ liệu bị sửa, việc đó
sẽ bị phát hiện. Nó **không** làm cho kho lưu trữ trở nên không thể sửa được.

Phân biệt này quan trọng khi phát biểu kết quả. Câu đúng là "hệ thống phát hiện
được thay đổi trái phép và từ chối tiếp nhận"; câu sai là "dữ liệu không thể bị
sửa".

### 6.5 Giới hạn thứ hai: thứ tự phiên bản

Kiểm chứng thực nghiệm cho thấy một giới hạn cụ thể ở phép kiểm thứ tư. Một con
trỏ phiên bản được ký hợp lệ bởi một máy được uỷ quyền vẫn có thể trỏ về một
phiên bản cũ hơn, và hệ thống chấp nhận.

Hệ quả cần mô tả chính xác: cơ chế hợp nhất **không xoá** những tài nguyên chỉ có
ở phiên bản mới; nhưng với những mục tồn tại ở cả hai phiên bản, **giá trị cũ ghi
đè giá trị mới**.

Vì vậy không nên gọi hành vi này là "không phá huỷ" theo nghĩa rộng. Mất một giá
trị mới hơn vẫn là mất, dù không có thao tác xoá nào diễn ra.

Ba thuộc tính cần tách bạch khi phát biểu:

| Thuộc tính | Câu hỏi nó trả lời | Trạng thái |
|---|---|---|
| Toàn vẹn | Nội dung có bị sửa không? | Đạt |
| Xác thực nguồn | Ai có thẩm quyền công bố? | Đạt |
| Đơn điệu phiên bản | Bản mới hơn có luôn thắng không? | Chưa cưỡng chế |

### 6.6 Đối chiếu với nguyên lý quay lui mô hình

Giới hạn ở mục 6.5 làm nổi bật giá trị của nguyên lý đã nêu ở mục 3.6.

Ở quản lý mô hình, quay lui được thiết kế như một **thao tác lựa chọn**: đổi con
trỏ phục vụ, giữ nguyên lịch sử. Ở nguồn sự thật dữ liệu, việc trỏ về phiên bản
cũ lại gây **ghi đè giá trị**. Cùng một nhu cầu nghiệp vụ — "quay về bản trước" —
nhưng hai cách hiện thực khác nhau về hệ quả.

Bài học tổng quát: khi thiết kế cơ chế quay lui, cần xác định rõ nó là *đổi lựa
chọn* hay *đổi trạng thái*. Cái đầu bảo toàn thông tin; cái sau thì không.

---

## 7. Các nguyên lý thiết kế rút ra

Phần này tổng hợp những nguyên lý đã được kiểm nghiệm trong quá trình xây dựng và
đánh giá hệ thống. Chúng có giá trị vượt ra ngoài đề tài cụ thể.

### 7.1 Thiếu ngữ cảnh thì dừng, không đoán

Khi một thành phần cần biết "dữ liệu này thuộc phạm vi nào" mà không được cung
cấp thông tin ấy, phản ứng đúng là báo lỗi. Ba phản ứng sai thường gặp:

- Trả về toàn bộ dữ liệu, coi như "không giới hạn".
- Trả về tập rỗng, coi như "không có gì".
- Rơi về một phạm vi mặc định nào đó.

Phương án thứ nhất là lỗ hổng. Phương án thứ hai che giấu lỗi và làm người vận
hành đi sai hướng. Phương án thứ ba biến phạm vi mặc định thành một phạm vi có
đặc quyền ngầm, và không ai giải thích được ràng buộc của hệ thống về sau.

### 7.2 Kế thừa lúc khởi tạo khác với rơi về lúc chạy

Một tổ chức mới có thể được khởi tạo từ một nguồn sẵn có — danh mục chuẩn, hoặc
một phiên bản dữ liệu dùng chung. Đó là **kế thừa tại thời điểm khởi tạo**: hệ
thống sao chép một ảnh chụp, ghi lại nguồn gốc và điều kiện sử dụng, và từ đó tổ
chức tự quản lý bản của mình.

Điều này khác hoàn toàn với **rơi về lúc chạy**: mỗi khi không tìm thấy dữ liệu
trong phạm vi của mình thì đi tìm ở phạm vi khác. Hành vi thứ hai làm mờ ranh
giới sở hữu, khiến dữ liệu của một tổ chức thay đổi khi nguồn bên ngoài thay đổi,
và làm mất khả năng truy vết nguồn gốc.

Ranh giới giữa hai khái niệm này cần được giữ tường minh, vì về mặt hiện tượng
chúng trông giống nhau: cả hai đều khiến tổ chức mới "có sẵn dữ liệu".

### 7.3 Ngoại lệ phải là một phạm vi, không phải một lối đi vòng

Miền dùng chung là một ngoại lệ so với nguyên tắc cách ly. Có hai cách hiện thực
một ngoại lệ như vậy.

**Cách thứ nhất** — tạo một đường truy cập đặc biệt bỏ qua cơ chế kiểm soát phạm
vi. Đơn giản để viết, nhưng nó tạo ra một lối đi vòng, và mọi lối đi vòng đều có
xu hướng được dùng lại cho những mục đích không lường trước.

**Cách thứ hai** — coi miền dùng chung là một phạm vi như mọi phạm vi khác, chỉ
khác về chính sách truy cập. Cách này giữ nguyên toàn bộ cơ chế kiểm soát, và
điều duy nhất khác biệt là ai được phép đọc.

Hệ thống chọn cách thứ hai. Hệ quả là miền dùng chung vẫn chịu đúng các ràng buộc
như một tổ chức bình thường, và không tồn tại đường nào cho phép "đọc tất cả" chỉ
vì đang phục vụ một yêu cầu công khai.

Một hệ quả phụ đáng nêu: **tư cách thành viên của miền dùng chung không tự nó cho
phép mọi hành động.** Việc một phạm vi mang tính công khai không miễn cho nó phép
kiểm tra quyền cụ thể.

### 7.4 Tổng hợp cũng có thể rò rỉ

Một điểm phản trực giác. Người ta thường cho rằng trả về một con số tổng hợp thì
an toàn, vì không lộ bản ghi nào.

Thực tế, một con số tổng hợp trên toàn bộ dữ liệu của mọi tổ chức vẫn rò rỉ thông
tin: nó cho biết quy mô tổng thể, và quan trọng hơn, **sự thay đổi của nó giữa
hai lần gọi** cho biết một tổ chức nào đó vừa có hoạt động. Người quan sát bên
ngoài có thể dùng chênh lệch ấy để suy ra nhịp độ làm việc của các đơn vị mà họ
không có quyền biết.

Nguyên lý rút ra: phạm vi của một phép tổng hợp phải được xác định tường minh
theo chính sách, không phải mặc định là "tất cả những gì đọc được".

### 7.5 Không có đường quay ngược từ công khai vào riêng tư

Khi một tài nguyên xuất hiện ở miền công khai, thông tin kèm theo nó không được
phép trở thành công cụ để truy cập ngược vào miền riêng của tổ chức nguồn.

Cụ thể, phản hồi công khai không nên chứa các định danh nội bộ, đường dẫn lưu
trữ, hay khoá đối tượng có thể thử lại với các giao diện dành cho tổ chức. Nếu
cần lưu vết nguồn gốc để phục vụ kiểm toán, ánh xạ ấy nên tồn tại ở tầng nội bộ
có kiểm soát.

Phát biểu ngắn gọn: **hiểu biết có được từ miền công khai không được tự nó cấp
quyền truy cập vào miền riêng.**

### 7.6 Công cụ đo phải có khả năng thất bại

Đây là nguyên lý quan trọng nhất về mặt phương pháp, rút ra từ nhiều lần đo hỏng.

Một phép đo chỉ có giá trị nếu nó **có thể cho kết quả xấu**. Nếu vì một lý do
nào đó phép đo luôn cho kết quả tốt bất kể thực trạng, thì con số nó sinh ra
không mang thông tin.

Dạng hỏng điển hình: phép thử "người dùng của đơn vị A không đọc được dữ liệu của
đơn vị B" cho kết quả đạt, nhưng nguyên nhân là dữ liệu của B không tồn tại ở nơi
hệ thống tìm kiếm. Kết quả trông giống hệt trường hợp cách ly hoạt động đúng.

Cách phòng ngừa là **đối chứng dương**: trước khi tin vào các kết quả "đã bị
chặn", phải chứng minh rằng chủ sở hữu hợp lệ **thật sự làm được** thao tác tương
ứng trên dữ liệu của chính mình. Nếu ngay cả chủ sở hữu cũng bị từ chối, mọi kết
quả "đã bị chặn" đều vô nghĩa.

Nguyên lý này mở rộng thành một tiêu chí chung cho mọi phép đo trong đề tài: bên
cạnh câu hỏi *kết quả là bao nhiêu*, luôn phải trả lời được câu hỏi *phép đo này
sẽ trông thế nào nếu hệ thống hỏng*.

### 7.7 Kiểm tra kết quả cuối, không chỉ kiểm tra mã trả về

Khi đánh giá một cơ chế bảo vệ, việc hệ thống trả về mã "từ chối" chưa đủ. Cần
kiểm tra thêm rằng **trạng thái không thay đổi**.

Một thao tác có thể ghi được một phần dữ liệu rồi mới gặp lỗi và báo từ chối. Xét
theo mã trả về thì đúng; xét theo hệ quả thì dữ liệu đã bị thay đổi.

Vì vậy mọi phép thử về cách ly cần so sánh trạng thái trước và sau, trên tất cả
các mặt phẳng lưu trữ.

Một tinh chỉnh nữa: so sánh phải thực hiện trên trạng thái **có dữ liệu sẵn**.
Kiểm tra "không có gì được ghi thêm" trên một kho rỗng sẽ bỏ lọt trường hợp một
bản ghi có sẵn bị ghi đè.

### 7.8 Phân biệt "chưa quan sát thấy vi phạm" với "có cơ chế ngăn vi phạm"

Hai phát biểu này thường bị dùng thay cho nhau, nhưng chúng khác nhau về bản chất
và về mức độ bảo đảm.

*Chưa quan sát thấy vi phạm* là một nhận định về những gì đã kiểm tra. Nó có thể
đúng đơn thuần vì chưa ai thử đúng cách.

*Có cơ chế ngăn vi phạm* là một nhận định về cấu trúc của hệ thống: tồn tại một
ràng buộc khiến vi phạm không xảy ra được.

Khi báo cáo kết quả đánh giá, cần nói rõ đang phát biểu điều nào. Một phần hệ
thống có thể chưa từng bộc lộ vấn đề nhưng cũng chưa có ràng buộc nào bảo đảm;
mô tả nó như đã được bảo vệ là một suy diễn vượt quá bằng chứng.

### 7.9 Phép đo phải gắn với một phiên bản mã xác định

Kết quả đo chỉ có ý nghĩa khi biết nó đo trên phiên bản nào của hệ thống.

Điều này khó hơn vẻ ngoài. Một mã định danh phiên bản trong hệ quản lý mã nguồn
chỉ chứng minh điểm xuất phát; nếu còn những thay đổi chưa được ghi nhận thì hai
lần đo cùng mã định danh vẫn có thể chạy trên hai phiên bản khác nhau. Tương tự,
một môi trường thực thi được dựng từ trước có thể đang chạy mã cũ hơn mã hiện tại.

Nguyên tắc thực hành: chụp một dấu vân tay của toàn bộ mã nguồn tại thời điểm đo,
kiểm lại ngay trước khi phép đo bắt đầu, và coi mọi thay đổi xảy ra sau thời điểm
đóng băng là lý do để đo lại từ đầu. Không ghép kết quả của hai phiên bản.

### 7.10 Phát hiện trong lúc đo thì ghi lại, không sửa ngay

Khi một phép đo bộc lộ vấn đề, cám dỗ tự nhiên là sửa rồi đo tiếp. Làm vậy sẽ
khiến kết quả cuối cùng mô tả một phiên bản không tồn tại — nửa đầu đo trên bản
cũ, nửa sau đo trên bản đã sửa.

Cách đúng là ghi nhận phát hiện như một kết quả của chính phiên bản đang đo, hoàn
tất lượt đo, rồi mới quyết định sửa hay không.

---

## 8. So sánh các phương án thiết kế

### 8.1 Cách ly dữ liệu giữa các tổ chức

| Phương án | Ưu điểm | Nhược điểm |
|---|---|---|
| Mỗi tổ chức một cơ sở dữ liệu riêng | Cách ly mạnh nhất, dễ giải thích | Chi phí vận hành tăng tuyến tính; nâng cấp lược đồ phải lặp lại cho từng tổ chức; truy vấn xuyên tổ chức cho mục đích nghiên cứu rất khó |
| Chung cơ sở dữ liệu, chung bảng, phân biệt bằng cột định danh và kiểm soát ở tầng ứng dụng | Đơn giản, chi phí thấp | Chỉ cần một chỗ quên lọc là rò rỉ; không có lớp bảo vệ dự phòng |
| Chung cơ sở dữ liệu, kiểm soát ở tầng cơ sở dữ liệu theo từng dòng | Chi phí vận hành thấp; **truy vấn quên bộ lọc vẫn không rò dữ liệu**; vẫn hỗ trợ tổng hợp nghiên cứu khi được cấp quyền | Danh tính phạm vi do tầng ứng dụng khai báo, nên cơ chế không độc lập hoàn toàn với tầng ấy; không bao phủ dữ liệu nằm ngoài cơ sở dữ liệu |

Hệ thống chọn phương án thứ ba, vì nó cân bằng giữa chi phí vận hành của một đề
tài học thuật và yêu cầu bảo đảm với các đơn vị tham gia. Nhược điểm cuối cùng —
không bao phủ dữ liệu ngoài cơ sở dữ liệu — chính là vấn đề đã phân tích ở mục 4.

### 8.2 Biểu diễn dữ liệu

| Phương án | Dung lượng | Phơi bày thông tin | Khả năng dùng lại |
|---|---|---|---|
| Lưu video gốc | Rất lớn | Cao: diện mạo, bối cảnh | Cao nhất: trích xuất lại được theo phương pháp mới |
| Lưu điểm mốc | Nhỏ | Thấp hơn, nhưng không phải ẩn danh | Bị khoá vào phương pháp trích xuất đã chọn |
| Lưu cả hai | Rất lớn | Cao | Cao nhất |

Lựa chọn lưu điểm mốc đánh đổi khả năng dùng lại để lấy dung lượng và mức phơi
bày thấp hơn. Cái giá cần nói thẳng: nếu sau này xuất hiện một phương pháp trích
xuất đặc trưng tốt hơn, dữ liệu đã thu **không** áp dụng phương pháp mới được, vì
video gốc không còn.

Đây là đánh đổi có ý thức, không phải thiếu sót. Với mục tiêu xây dựng hạ tầng
thu thập ở quy mô nhiều đơn vị, dung lượng và quyền riêng tư được ưu tiên hơn.

### 8.3 Tổ chức các bước xử lý

| Phương án | Ưu điểm | Nhược điểm |
|---|---|---|
| Xử lý đồng bộ trong yêu cầu | Đơn giản; kết quả tức thì | Người dùng phải chờ; không chịu được tải |
| Một công việc nền gộp mọi bước | Ít điểm hỏng; không cần lưu dữ liệu trung gian | Không chạy lại từng bước được; không phân bổ tài nguyên riêng cho từng bước |
| Mỗi bước một công việc nền riêng | Điều phối linh hoạt; chạy lại từng phần | Phức tạp hơn; cần lưu và đọc lại dữ liệu trung gian; nhiều điểm hỏng hơn |

Hệ thống dùng phương án thứ hai cho đường thu nhận, và phương án thứ ba cho các
tác vụ đồng bộ kho lưu trữ. Sự khác biệt hợp lý: các bước trong đường thu nhận
gắn bó chặt và luôn chạy cùng nhau, còn các tác vụ đồng bộ thì độc lập và có tần
suất khác nhau.

### 8.4 Thẩm quyền ký trong cơ chế nguồn sự thật

| Phương án | Ưu điểm | Nhược điểm |
|---|---|---|
| Thẩm quyền theo máy phát hành | Đơn giản; phù hợp khi số máy ít và được quản lý tập trung | Thẩm quyền không trùng với ranh giới tổ chức |
| Thẩm quyền theo tổ chức | Mỗi tổ chức tự chịu trách nhiệm về dữ liệu của mình; phù hợp với mô hình nhiều đơn vị | Phức tạp hơn: cần quản lý khoá theo tổ chức, cần định nghĩa quan hệ tin cậy giữa các miền |

Hệ thống hiện dùng phương án thứ nhất. Điều này phù hợp với giai đoạn hiện tại,
khi số máy phát hành ít và cùng thuộc một đơn vị quản lý. Nhưng cần nêu rõ giới
hạn: **thẩm quyền ký chưa được phân tách theo tổ chức**, nên không thể phát biểu
rằng mỗi tổ chức có một miền tin cậy mật mã riêng.

---

## 9. Giới hạn và hướng phát triển

### 9.1 Phạm vi tổ chức chưa phủ đều toàn bộ vòng đời

Ranh giới tổ chức được cưỡng chế đầy đủ ở lớp thu nhận và quản lý dữ liệu: lớp ký
hiệu, mẫu, các đường thu, và các công việc huấn luyện thuộc luồng ứng dụng chính.

Nhánh theo dõi thực nghiệm và quản lý phiên bản mô hình hiện gắn quyền sở hữu
theo **người dùng** chứ chưa theo tổ chức. Chưa có bằng chứng nào cho thấy đã xảy
ra truy cập chéo tổ chức qua nhánh này; nhưng cũng chưa có ràng buộc nào bảo đảm
điều đó không xảy ra được.

Đây là khoảng cách giữa kiến trúc đích và hiện thực. Việc thu hẹp nó là một thay
đổi xuyên nhiều tầng — lược đồ dữ liệu, giao diện lập trình, các tiến trình nền,
và mô hình sở hữu artifact — nên được xếp vào hướng phát triển tiếp theo thay vì
sửa vội.

### 9.2 Vòng đời công bố sang miền dùng chung mới hoàn thiện một phần

Việc đóng góp trực tiếp vào miền dùng chung đã hoạt động. Việc một tổ chức chủ
động công bố từng tài nguyên từ kho riêng của mình sang miền dùng chung hiện chỉ
tồn tại ở dạng công cụ quản trị, chưa thành một luồng nghiệp vụ hoàn chỉnh; và
thao tác thu hồi tương ứng chưa được hiện thực.

### 9.3 Thu hồi không viết lại quá khứ

Một vấn đề cần định nghĩa rõ về mặt chính sách trước khi hiện thực.

Giả sử một tổ chức công bố một mẫu, mẫu ấy tham gia vào một phiên bản bộ dữ liệu
dùng chung, và phiên bản ấy được dùng để huấn luyện một mô hình. Sau đó tổ chức
thu hồi mẫu.

Việc thu hồi có thể ngăn mẫu tham gia các phiên bản sau, và ngăn việc tải xuống.
Nhưng nó **không thể** làm cho mô hình đã huấn luyện trở nên chưa từng học mẫu
ấy. Phiên bản bộ dữ liệu và mô hình đã sinh ra cần giữ thông tin nguồn gốc phản
ánh đúng thực tế rằng chúng được hình thành khi mẫu còn hợp lệ.

Việc có xử lý các sản phẩm dẫn xuất hay không là một quyết định thuộc phạm vi
quản trị và pháp lý, không giải quyết được bằng một thao tác xoá dữ liệu.

### 9.4 Bảng ghi nhận yêu cầu xoá đơn vị chưa được bảo vệ theo dòng

Rà soát ban đầu tìm ra hai bảng mang thông tin phạm vi nhưng chưa bật cơ chế kiểm
soát theo dòng: bảng danh sách các đơn vị, và bảng ghi nhận yêu cầu xoá đơn vị.
Điểm đáng nói là bảng thứ nhất không hề bị loại trừ có cân nhắc — nó chưa từng
được nhắc tới trong danh sách cần bảo vệ, nên khoảng trống ấy là một chỗ bỏ sót
im lặng chứ không phải một ngoại lệ được cân nhắc rồi chấp nhận.

Bảng thứ nhất đã được đưa vào diện bảo vệ trong chính bản chỉnh sửa mà chương này
mô tả. Đây là bảng gốc, mỗi dòng chính là một đơn vị, nên vị từ phạm vi tiêu chuẩn
đọc ra thành "chỉ nhìn thấy dòng của chính mình" mà không cần đặt thêm quy ước
riêng. Ba đường đọc xuyên đơn vị hợp lệ còn lại đã được kiểm kê và đều chạy dưới
phạm vi hệ thống được tuyên bố tường minh.

Bảng thứ hai vẫn còn trống. Từng có lập luận rằng nó thuộc mặt phẳng điều khiển
nên không cần bảo vệ — sau khi một đơn vị bị xoá thì không còn phạm vi nào để giới
hạn theo. Lập luận ấy chỉ đứng vững nếu vai vận hành không có đường truy cập trực
tiếp tới bảng. Rà soát cho thấy điều kiện ấy không thoả: vai vận hành có đủ bốn
quyền thao tác dữ liệu trên bảng đó.

Vì vậy trạng thái đúng phải ghi: đây là **một khoảng trống cách ly thật**, không
phải một ngoại lệ có giải trình, và nó vẫn còn mở tại thời điểm đo.

### 9.5 Bảng dữ liệu phân quyền có thể tự sửa

Một khoảng trống cùng loại nhưng ở mặt phẳng phân quyền: một số bảng cấu thành dữ
liệu phân quyền hiện chưa bật cơ chế kiểm soát theo dòng, trong khi vai vận hành
có đủ quyền ghi lên chúng.

Ở trạng thái hiện tại điều này vô hại, vì cơ chế phân quyền mới đang chạy ở chế độ
đối chiếu và không đưa ra quyết định nào. Nhưng kể từ lúc nó trở thành bên cưỡng
chế, đây sẽ là một nguyên thuỷ leo thang đặc quyền có cùng hình dạng với vấn đề đã
nêu ở mục 4.4: **thẩm quyền do chính bên bị ràng buộc tự tuyên bố.**

Ghi nhận trước là cách duy nhất để việc chuyển sang chế độ cưỡng chế không vô tình
mở ra một lỗ hổng.

### 9.6 Phân quyền theo nhiều cấp phạm vi mới áp dụng ở hai cấp

Mô hình phân quyền được thiết kế cho bốn cấp phạm vi. Trong hiện thực, việc gán
vai và cưỡng chế mới diễn ra ở cấp hệ thống và cấp tổ chức. Hai cấp thấp hơn đã
được mô hình hoá trong lược đồ dữ liệu nhưng chưa có giao diện nghiệp vụ, nên
chưa có ai được cấp quyền ở đó và cũng chưa có gì để kiểm chứng.

---

## 10. Kết luận phần thuyết minh

Kiến trúc trình bày ở trên là lời giải cho ba lực kéo ngược chiều đã nêu ở mục
1.3: tách bạch để các đơn vị yên tâm tham gia, dùng chung để dữ liệu có giá trị
nghiên cứu, và đảo ngược được để tôn trọng quyền của người đóng góp.

Ba lựa chọn cốt lõi định hình toàn bộ hệ thống:

- **Cách ly là mặc định, dùng chung là ngoại lệ tường minh.** Dữ liệu thu ở đâu
  thuộc về nơi đó; muốn đưa ra miền chung phải có một hành động công bố cụ thể.
- **Ngoại lệ được hiện thực như một phạm vi, không phải một lối đi vòng.** Miền
  dùng chung chịu đúng cơ chế kiểm soát như mọi phạm vi khác.
- **Thiếu ngữ cảnh thì dừng.** Không có giá trị mặc định, không có đường lùi, và
  mọi từ chối đều phải ồn ào để người vận hành nhìn thấy.

Về mặt phương pháp, đóng góp có giá trị lâu dài nhất của đề tài có lẽ không nằm ở
một con số cụ thể nào, mà ở kỷ luật đánh giá: mỗi phép đo phải có khả năng thất
bại, mỗi kết quả phải gắn với một phiên bản mã xác định, và mỗi phát biểu phải
được giới hạn đúng vào phạm vi mà bằng chứng thực sự bao phủ.
