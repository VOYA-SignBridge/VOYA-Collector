# Thuyết minh nghiệp vụ vận hành

*Bản thuyết minh dạng luận văn. Trình bày các luồng nghiệp vụ ở góc nhìn người
sử dụng và người quản trị: vai trò, vòng đời tài khoản và tổ chức, kiểm soát truy
cập, đồng thuận, kiểm duyệt dữ liệu, và nhật ký kiểm toán. Phần kiến trúc kỹ
thuật được trình bày ở tài liệu riêng.*

---

## 1. Các chủ thể tham gia

Nền tảng phục vụ bốn nhóm chủ thể có nhu cầu và quyền hạn khác nhau. Việc phân
biệt rõ bốn nhóm này là điều kiện để thiết kế phân quyền hợp lý.

**Người ký.** Người thực hiện động tác ngôn ngữ ký hiệu trước camera. Đây là chủ
thể mà dữ liệu nói về, nên họ giữ quyền đồng thuận và quyền rút lại. Đáng lưu ý:
người ký không nhất thiết là người có tài khoản — một buổi thu có thể do cộng tác
viên vận hành, còn người ký chỉ tham gia biểu diễn.

**Cộng tác viên thu dữ liệu.** Người vận hành buổi thu: chọn lớp ký hiệu cần thu,
hướng dẫn người ký, kiểm tra chất lượng tại chỗ, và gửi dữ liệu lên hệ thống.

**Quản trị viên tổ chức.** Người chịu trách nhiệm về dữ liệu của một đơn vị: mời
và quản lý thành viên, duyệt dữ liệu, quyết định công bố hay giữ riêng.

**Quản trị viên hệ thống.** Người vận hành nền tảng: quản lý danh mục chuẩn, các
tổ chức, các văn bản pháp lý, và hạ tầng.

Phân biệt giữa **người ký** và **người có tài khoản thu dữ liệu** là điểm dễ bị bỏ
qua nhưng có hệ quả lớn. Hai khái niệm này tương ứng với hai loại định danh khác
nhau trong hệ thống, và nhầm lẫn giữa chúng dẫn tới hai lỗi nghiêm trọng: gán
quyền sở hữu dữ liệu cho sai người, và không thực thi được yêu cầu rút đồng thuận
của người ký thật sự.

---

## 2. Mô hình phân quyền

### 2.1 Ba tầng quyết định

Quyền truy cập được quyết định bởi sự kết hợp của ba yếu tố, chứ không bởi riêng
yếu tố nào:

> chủ thể — phạm vi — quyền cụ thể

Không yếu tố nào trong ba yếu tố này tự nó đủ. Cụ thể, **tư cách thành viên không
bao giờ tự nó cho phép hành động.** Việc một người thuộc về một tổ chức chỉ trả
lời câu hỏi "họ được xét quyền trong phạm vi nào", chứ không trả lời "họ được làm
gì".

Nguyên lý này nghe hiển nhiên nhưng thường bị vi phạm trong thực tế, dưới dạng
các phép kiểm tra kiểu "nếu là thành viên thì cho qua". Cách kiểm tra ấy hoạt động
đúng cho tới khi tổ chức có nhiều loại thành viên với quyền hạn khác nhau.

### 2.2 Vì sao định danh phải dựa trên mã, không dựa trên tên

Một quyết định thiết kế tưởng nhỏ nhưng ảnh hưởng tới toàn bộ mô hình phân quyền:
mọi phép kiểm tra quyền sở hữu đều dựa trên **mã định danh nội bộ**, không dựa
trên tên hiển thị.

Lý do: hai người có thể trùng tên. Nếu hệ thống xác định "dữ liệu này của ai"
bằng cách so tên, thì một người có thể sửa hoặc xoá dữ liệu của người trùng tên
với mình. Đây không phải tình huống giả định — trong một tập dữ liệu có hàng trăm
người tham gia, trùng tên là chuyện thường.

Hệ quả kèm theo: khi một người đổi tên hiển thị, tên cũ đã được sao chép vào
nhiều nơi cần được cập nhật đồng bộ. Nhưng có một ngoại lệ quan trọng — **nhãn
ghi trong nhật ký kiểm toán không được đổi.** Nhật ký ghi lại việc đã xảy ra tại
một thời điểm, với tên mà chủ thể mang tại thời điểm đó. Sửa lại tên trong nhật
ký là viết lại lịch sử, và làm mất giá trị của chính nhật ký.

### 2.3 Nhiều cấp phạm vi

Mô hình được thiết kế cho nhiều cấp phạm vi lồng nhau: cấp hệ thống, cấp tổ chức,
và hai cấp thấp hơn để tổ chức công việc bên trong một đơn vị.

Việc tách cấp tổ chức khỏi các cấp thấp hơn là một tinh chỉnh so với thiết kế ban
đầu, và đáng giải thích. Bản đầu gộp *ranh giới cách ly* với *ranh giới tổ chức
công việc* làm một. Khi gộp như vậy, mỗi nhóm công việc mới lại buộc phải trở
thành một đơn vị cách ly mới — không dùng được cho một trường có nhiều lớp cùng
tham gia thu dữ liệu, vì họ cần chia nhóm công việc mà không cần chia tách dữ
liệu.

Tách ra thì mỗi khái niệm làm đúng việc của nó: đơn vị là ranh giới cách ly và
ranh giới tính phí; các cấp dưới là cách sắp xếp công việc bên trong.

Cần nêu đúng hiện trạng: hai cấp thấp hơn hiện đã có trong mô hình dữ liệu nhưng
chưa có giao diện nghiệp vụ tương ứng, nên chưa có ai được cấp quyền ở đó. Đây là
khoảng cách giữa thiết kế và hiện thực, không phải một thiếu sót được che giấu.

---

## 3. Vòng đời tổ chức

### 3.1 Khởi tạo

Khi một đơn vị mới tham gia, hệ thống tạo cho họ một miền dữ liệu riêng. Việc
khởi tạo không chỉ là thêm một bản ghi: đơn vị mới cần có sẵn danh mục phân loại
để bắt đầu làm việc, vì một lớp ký hiệu không thể tồn tại nếu không gắn được vào
một phương ngữ trong danh mục của chính đơn vị đó.

Vì vậy quá trình khởi tạo bao gồm việc nhân bản danh mục chuẩn vào phạm vi mới.
Bỏ qua bước này sẽ tạo ra một đơn vị trông bình thường trong danh sách nhưng từ
chối mọi thao tác ghi — một dạng hỏng đặc biệt khó chẩn đoán, vì triệu chứng xuất
hiện muộn và ở xa nguyên nhân.

Điểm cần phân biệt: việc kế thừa danh mục lúc khởi tạo là **một lần sao chép tại
thời điểm tạo**, không phải một liên kết động. Sau đó đơn vị tự quản lý bản của
mình; nếu danh mục gốc thay đổi, dữ liệu của đơn vị không tự đổi theo. Sự phân
biệt này giữ cho quyền sở hữu và khả năng truy vết nguồn gốc được rõ ràng.

### 3.2 Mời và quản lý thành viên

Quản trị viên của một đơn vị có thể mời người khác tham gia. Lời mời được gửi qua
kênh liên lạc đã xác minh, và người nhận phải chủ động chấp nhận — không có việc
thêm thẳng một tài khoản vào đơn vị mà chủ tài khoản không biết.

Một bất biến được cưỡng chế: **mọi tài khoản đang hoạt động phải là thành viên của
đơn vị mà nó thuộc về.** Bất biến này nghe thừa, nhưng nó bảo vệ một điều thực
chất — đường phân quyền đi từ tài khoản, qua tư cách thành viên, tới phạm vi hiệu
dụng, rồi mới tới quyết định cho phép. Một tài khoản thiếu vế thứ hai sẽ bị hệ
thống coi là không phải thành viên ở mọi phép kiểm quyền, kể cả khi nó được ghi
nhận thuộc về đơn vị.

Dạng hỏng này đặc biệt khó chẩn đoán vì tài khoản trông hoàn toàn bình thường
trong danh sách; chỉ khi nó thao tác thì mới bị từ chối, và thông báo từ chối
không chỉ ra nguyên nhân thật.

---

## 4. Vòng đời tài khoản

### 4.1 Đăng ký và xác minh

Quy trình đăng ký yêu cầu xác minh kênh liên lạc trước khi tài khoản được kích
hoạt đầy đủ. Việc xác minh dùng mã dùng một lần, gửi qua kênh mà người dùng đã
khai báo.

Tại thời điểm đăng ký, người dùng phải chấp nhận các văn bản điều khoản đang có
hiệu lực. Việc chấp nhận được ghi nhận kèm **định danh nội dung của chính văn bản
tại thời điểm đó** — không chỉ ghi "đã đồng ý", mà ghi "đã đồng ý với đúng bản
này". Nhờ vậy, khi điều khoản thay đổi, hệ thống phân biệt được ai đã chấp nhận
bản nào, và biết cần yêu cầu ai chấp nhận lại.

### 4.2 Phiên đăng nhập và ba mức thu hồi

Một tài khoản có thể đăng nhập từ nhiều thiết bị. Hệ thống quản lý các phiên này
như những thực thể riêng, cho phép người dùng nhìn thấy danh sách thiết bị đang
đăng nhập và chủ động chấm dứt phiên trên thiết bị mình không còn dùng.

Có ba mức thu hồi, và việc phân biệt chúng là cần thiết:

- **Thu hồi một phiên** — đăng xuất một thiết bị cụ thể.
- **Thu hồi mọi phiên trừ phiên hiện tại** — dùng khi nghi ngờ tài khoản bị truy
  cập trái phép nhưng vẫn muốn tiếp tục làm việc.
- **Thu hồi toàn bộ** — dùng khi đổi mật khẩu hoặc khi xử lý sự cố bảo mật.

Ba mức này giải quyết ba tình huống khác nhau; gộp lại thành một sẽ khiến người
dùng hoặc là không xử lý được sự cố, hoặc là tự đăng xuất mình khỏi thiết bị đang
dùng.

### 4.3 Xác thực hai yếu tố

Người dùng có thể bật lớp xác thực thứ hai dựa trên mã thời gian sinh bởi ứng
dụng trên điện thoại. Đây là cơ chế tiêu chuẩn, nhưng việc tự hiện thực nó đặt ra
một yêu cầu về kiểm chứng: thuật toán phải được đối chiếu với các bộ giá trị mẫu
đã công bố trong tiêu chuẩn, chứ không chỉ kiểm bằng cách "thử đăng nhập thấy
được".

Lý do: một hiện thực sai lệch về múi giờ hoặc về độ dài cửa sổ thời gian vẫn cho
phép đăng nhập thành công trong điều kiện thử nghiệm, nhưng sẽ thất bại hoặc —
tệ hơn — chấp nhận mã đã hết hạn trong điều kiện thực tế.

### 4.4 Khôi phục tài khoản

Quy trình quên mật khẩu được gộp thành một luồng liền mạch thay vì bắt người dùng
đi qua nhiều bước rời rạc. Về mặt kỹ thuật, luồng này vẫn tách thành các giai
đoạn xác minh và xác nhận riêng, nhưng chúng **dùng chung một hạn mức tần suất**.

Chi tiết này quan trọng hơn vẻ ngoài. Nếu mỗi giai đoạn có hạn mức riêng, kẻ tấn
công có thể lợi dụng bằng cách xoay vòng giữa các giai đoạn để nhân số lần thử
lên. Dùng chung hạn mức khiến tổng số lần thử bị giới hạn thật sự.

### 4.5 Chế độ nâng quyền tạm thời

Với các thao tác nhạy cảm — thay đổi cấu hình bảo mật, thu hồi phiên của người
khác, xử lý dữ liệu nhạy cảm — hệ thống yêu cầu xác thực lại ngay cả khi người
dùng đang trong phiên hợp lệ. Trạng thái "đã xác thực lại" có hiệu lực trong một
khoảng thời gian ngắn.

Cơ chế này bảo vệ trước tình huống một phiên đăng nhập bị chiếm dụng: kẻ tấn công
có thể xem được dữ liệu, nhưng không thực hiện được các thao tác có hậu quả lớn
nếu không biết mật khẩu.

---

## 5. Kiểm soát truy cập ở tầng cổng vào

### 5.1 Mặc định từ chối

Hệ thống áp dụng nguyên tắc **mặc định từ chối** ở tầng cổng vào: mọi đường giao
tiếp đều yêu cầu xác thực, trừ những đường được liệt kê tường minh trong danh sách
ngoại lệ.

Cách làm ngược lại — mặc định cho phép, rồi bảo vệ từng đường một — có một nhược
điểm chí mạng: mỗi đường mới thêm vào hệ thống sẽ **mặc định không được bảo vệ**,
và việc quên bảo vệ không gây ra triệu chứng nào. Với mặc định từ chối, việc quên
khai báo sẽ khiến đường đó không dùng được — một lỗi ồn ào, phát hiện ngay.

Đây là một trường hợp cụ thể của nguyên lý chung: **thiết kế sao cho sai sót gây
ra sự cố khả dụng chứ không gây ra lỗ hổng bảo mật.**

### 5.2 Danh sách ngoại lệ phải được rà soát định kỳ

Danh sách ngoại lệ là nơi tập trung rủi ro, nên nó cần được rà soát như một tài
sản riêng. Một đường được đưa vào danh sách vì một lý do hợp lệ ở thời điểm ấy có
thể trở nên không hợp lệ khi hành vi của nó thay đổi.

Trường hợp minh hoạ: một điểm truy cập cung cấp số liệu tổng hợp cho trang công
khai. Ở thiết kế ban đầu, nó tổng hợp trên toàn bộ dữ liệu — điều này vừa vi phạm
ranh giới đơn vị, vừa tạo ra một kênh suy luận, vì chênh lệch số liệu giữa hai
lần gọi cho biết có đơn vị nào đó vừa hoạt động. Sau khi thu hẹp phạm vi về một
nguồn được chỉ định tường minh, rủi ro ấy được loại bỏ.

Bài học rút ra: **một phép tổng hợp cũng có thể rò rỉ thông tin**, và phạm vi của
nó phải được quy định bởi chính sách chứ không mặc định là "tất cả những gì đọc
được".

### 5.3 Chế độ dùng thử

Người dùng chưa đăng ký được phép trải nghiệm một phần chức năng trong một hạn
mức thời gian mỗi ngày. Mục đích là hạ rào cản tiếp cận: người quan tâm có thể
đánh giá hệ thống trước khi quyết định tham gia.

Việc đếm thời gian sử dụng cần chính xác nhưng không được tốn kém, vì nó diễn ra
liên tục trong suốt phiên. Cách hiện thực dùng một cấu trúc dữ liệu gọn nhẹ trong
bộ nhớ đệm, đánh dấu từng đơn vị thời gian đã dùng — đủ chính xác để cưỡng chế
hạn mức, đủ nhẹ để không ảnh hưởng tới trải nghiệm.

---

## 6. Đồng thuận và khuôn khổ pháp lý

### 6.1 Vì sao đồng thuận phải là cơ chế vận hành

Dữ liệu ngôn ngữ ký hiệu gắn chặt với cơ thể và cách biểu đạt của một cá nhân.
Ngay cả khi chỉ lưu toạ độ điểm mốc, dáng ký hiệu vẫn là một đặc trưng cá nhân, và
dữ liệu vẫn liên kết được với danh tính qua siêu dữ liệu.

Vì vậy đồng thuận không thể chỉ là một dòng trong điều khoản sử dụng. Nó phải là
một trạng thái có thể tra cứu, có thể thay đổi, và **có người đọc** — nghĩa là các
quy trình xử lý dữ liệu phải thực sự kiểm tra trạng thái ấy trước khi hành động.

### 6.2 Thang mức đồng thuận

Đồng thuận không phải một công tắc bật/tắt, vì các mục đích sử dụng khác nhau đặt
ra mức độ phơi bày khác nhau. Hệ thống dùng một thang nhiều mức, phân biệt tối
thiểu ba trường hợp: dữ liệu chỉ dùng nội bộ đơn vị, dữ liệu dùng cho nghiên cứu,
và dữ liệu được công bố ra ngoài.

Người ký chọn mức phù hợp với mình, và có thể thay đổi lựa chọn về sau.

### 6.3 Rút đồng thuận là rút thật

Nguyên tắc quan trọng nhất của phần này: **rút đồng thuận phải có hiệu lực thực
tế**, không phải một ghi chú không ai đọc.

Cụ thể, khi một người rút đồng thuận, các mẫu liên quan không còn được đưa vào các
phiên bản bộ dữ liệu mới và không còn được công bố. Việc rút không khó hơn việc
đồng ý — đây là một yêu cầu về thiết kế giao diện, không chỉ về mặt kỹ thuật.

### 6.4 Giới hạn: thu hồi không viết lại quá khứ

Có một ranh giới cần định nghĩa rõ, vì nó thường bị hiểu sai.

Giả sử một mẫu đã tham gia vào một phiên bản bộ dữ liệu, và phiên bản ấy đã được
dùng để huấn luyện một mô hình. Sau đó người ký rút đồng thuận.

Việc rút ngăn mẫu tham gia các phiên bản sau và ngăn việc phát hành. Nhưng nó
**không thể** làm cho mô hình đã huấn luyện trở nên chưa từng học mẫu ấy. Phiên
bản bộ dữ liệu và mô hình đã sinh ra phải giữ thông tin nguồn gốc phản ánh đúng
thực tế rằng chúng được hình thành khi mẫu còn hợp lệ.

Việc có xử lý các sản phẩm dẫn xuất hay không là một quyết định thuộc phạm vi quản
trị và pháp lý. Nó không giải quyết được bằng một thao tác xoá dữ liệu, và không
nên hứa hẹn rằng nó giải quyết được.

### 6.5 Văn bản pháp lý và tính bất biến

Các văn bản điều khoản được lưu trong hệ thống với nội dung đầy đủ, không chỉ là
đường dẫn tới một tệp bên ngoài. Lý do: khi cần chứng minh một người đã đồng ý với
điều gì, phải trưng ra được **đúng nội dung tại thời điểm đó**.

Một bản văn đã công bố không được sửa. Muốn thay đổi thì phải công bố bản mới, và
hệ thống ghi nhận việc chấp nhận theo từng bản. Ràng buộc này được cưỡng chế ở
tầng lưu trữ chứ không chỉ ở tầng ứng dụng, vì đây là loại bảo đảm mà một sơ suất
lập trình không được phép phá vỡ.

---

## 7. Quản trị dữ liệu ở góc nhìn người dùng

### 7.1 Xoá mềm và thùng rác

Thao tác xoá của người dùng là **xoá mềm**: bản ghi được đánh dấu đã xoá và chuyển
vào thùng rác, tệp dữ liệu vẫn được giữ lại. Chỉ khi thùng rác được dọn sạch thì
tệp mới thực sự bị loại bỏ.

Đây là lựa chọn có chủ đích, không phải sự dở dang. Dữ liệu thu được là kết quả
của một buổi làm việc có sự tham gia của người thật; một thao tác nhấn nhầm không
nên phá huỷ nó vĩnh viễn. Thùng rác được phân theo từng người dùng, nên một người
không nhìn thấy và không khôi phục được thứ người khác đã xoá.

Cần phân biệt xoá mềm với việc rút đồng thuận. Xoá mềm là thao tác quản lý dữ
liệu, có thể hoàn tác. Rút đồng thuận là một quyết định về quyền, và nó có hiệu
lực ngay đối với việc sử dụng dữ liệu, bất kể bản ghi còn tồn tại hay không.

### 7.2 Kiểm duyệt và chỉnh sửa

Dữ liệu sau khi thu cần được rà soát: nhãn có đúng không, chất lượng có đạt
không, có mẫu nào bị gán nhầm lớp không.

Thao tác sửa nhãn của một mẫu kéo theo việc di chuyển tệp dữ liệu sang vị trí
tương ứng với lớp mới. Đây là một thao tác trải trên nhiều mặt phẳng lưu trữ, nên
nó được giao cho tiến trình nền thay vì thực hiện đồng bộ trong yêu cầu — vừa để
người dùng không phải chờ, vừa để có cơ chế thử lại khi một bước thất bại.

### 7.3 Các chỉ số chất lượng và khả năng tái lập

Mỗi mẫu được gắn một số chỉ số chất lượng. Cần phân biệt hai loại, vì chúng khác
nhau về khả năng kiểm chứng:

- **Chỉ số tính lại được từ dữ liệu đã lưu** — chẳng hạn tỉ lệ khung hình phát
  hiện được bàn tay. Loại này có thể kiểm tra lại bất cứ lúc nào.
- **Chỉ số chỉ đo được tại thời điểm thu** — chẳng hạn độ ổn định của luồng video
  đầu vào. Loại này không tính lại được sau khi video gốc không còn.

Sự phân biệt này quan trọng khi đánh giá độ tin cậy của siêu dữ liệu. Một chỉ số
thuộc loại thứ hai, nếu bị ghi sai tại thời điểm thu, sẽ không có cách nào phát
hiện về sau.

Một lưu ý về cách đọc số liệu: giá trị bằng không ở chỉ số hoàn chỉnh **không**
đồng nghĩa với tệp rỗng. Nó có nghĩa là quá trình phát hiện bàn tay thất bại trên
toàn bộ khung hình — tệp vẫn tồn tại và vẫn có kích thước, chỉ là nội dung không
mang thông tin. Nhầm hai trường hợp này dẫn tới những kết luận sai về dung lượng
và về chất lượng dữ liệu.

---

## 8. Đăng ký dịch vụ và hạn mức

Nền tảng có mô hình gói dịch vụ với các hạn mức khác nhau, kèm vòng đời gồm thời
hạn, nhắc gia hạn, thời gian ân hạn, và khoá mềm khi quá hạn.

Hai điểm cần nêu rõ về phạm vi hiện tại.

**Hệ thống không thu tiền.** Toàn bộ phần thanh toán nằm ngoài phạm vi triển khai;
cái được hiện thực là vòng đời trạng thái đăng ký, không phải giao dịch tài chính.
Với một đề tài học thuật, đây là ranh giới hợp lý: mô hình hoá được nghiệp vụ mà
không phải xử lý các yêu cầu tuân thủ của việc thanh toán thật.

**Trạng thái quá hạn vẫn cho phép ghi dữ liệu.** Đây là lựa chọn có chủ đích, không
phải thiếu sót. Khoá hoàn toàn quyền ghi khi một đơn vị chậm gia hạn sẽ làm gián
đoạn một buổi thu đang diễn ra với sự tham gia của người thật. Cái giá của việc
chặn cao hơn nhiều so với cái lợi.

---

## 9. Nhật ký kiểm toán

### 9.1 Vì sao cần

Với một hệ thống nhiều đơn vị cùng dùng, câu hỏi "ai đã làm gì" phải trả lời
được. Đây là yêu cầu vừa để xử lý sự cố, vừa để các đơn vị tham gia yên tâm rằng
mọi thao tác trên dữ liệu của họ đều để lại dấu vết.

### 9.2 Hai tầng ghi và bài học về việc có hai nguồn

Nhật ký được ghi đồng thời vào một kho tạm phục vụ tra cứu nhanh và một kho bền
phục vụ lưu trữ dài hạn.

Cấu hình hai kho từng dẫn tới một tình huống đáng ghi nhận: cả hai đều hoạt động,
nhưng chỉ kho tạm có người đọc, còn kho bền thì không giao diện nào truy vấn tới.
Về hình thức hệ thống có nhật ký đầy đủ; về thực chất, phần dữ liệu dài hạn không
ai xem.

Bài học tổng quát: **sự tồn tại của dữ liệu không đồng nghĩa với việc dữ liệu đó
được sử dụng.** Khi rà soát một cơ chế, cần kiểm cả hai đầu — đầu ghi và đầu đọc.

### 9.3 Từ chối khi thiếu ngữ cảnh

Việc ghi nhật ký tuân theo cùng nguyên tắc như các đường đọc dữ liệu: nếu không
xác định được phạm vi của thao tác, hệ thống báo lỗi thay vì ghi một bản ghi
không rõ thuộc về đâu.

Một bản ghi nhật ký không xác định được phạm vi tệ hơn là không có bản ghi: nó tạo
cảm giác có dấu vết, trong khi dấu vết ấy không dùng để trả lời được câu hỏi nào.

---

## 10. Các nguyên lý rút ra từ phần nghiệp vụ

**Định danh phải ổn định và không mơ hồ.** Mọi phép kiểm quyền dựa trên mã định
danh nội bộ, không dựa trên tên hiển thị. Tên có thể trùng và có thể đổi; mã thì
không.

**Tư cách thành viên không phải quyền.** Thuộc về một phạm vi chỉ quyết định nơi
xét quyền, không quyết định được làm gì.

**Sai sót nên gây sự cố khả dụng, không nên gây lỗ hổng.** Nguyên tắc mặc định từ
chối, và việc từ chối ồn ào khi thiếu ngữ cảnh, đều phục vụ mục tiêu này.

**Thao tác phá huỷ cần có đường lùi; quyết định về quyền thì có hiệu lực ngay.**
Xoá dữ liệu là xoá mềm và hoàn tác được; rút đồng thuận có hiệu lực lập tức đối
với việc sử dụng.

**Lịch sử không được viết lại.** Nhãn trong nhật ký kiểm toán giữ nguyên giá trị
tại thời điểm ghi. Văn bản pháp lý đã công bố không được sửa. Thông tin nguồn gốc
của một phiên bản dữ liệu phản ánh đúng thực tế tại thời điểm hình thành.

**Cơ chế chỉ có giá trị khi có người đọc.** Một trạng thái đồng thuận không được
kiểm tra, hay một nhật ký không được truy vấn, chỉ tạo ra cảm giác an toàn.
