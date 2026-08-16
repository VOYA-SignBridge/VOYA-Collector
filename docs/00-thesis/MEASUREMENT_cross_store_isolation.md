# P0-B — Cách ly xuyên kho, đo đối kháng

**Kết luận:** ĐẠT — đủ điều kiện công bố
**Thời điểm:** 16/08/2026, 07:55 UTC
**Trạng thái công bố:** bốn lớp bằng chứng đều đạt, không còn ca nào không kết luận được

---

## 1. Con số

| chỉ số | giá trị | mẫu số | nghĩa |
|---|---|---|---|
| Tỉ lệ vi phạm xuyên tổ chức | **0,0000** | 450 lượt kết luận được | không một thao tác nào vượt được ranh giới tổ chức |
| Tỉ lệ thao tác trái quyền lọt | **0,0000** | 180 lượt | không một thao tác nào vượt được cổng phân quyền |
| Tỉ lệ vi phạm gộp | **0,0000** | 630 lượt | con số gộp duy nhất được phép công bố |
| Ca không kết luận được | **0** | — | điều kiện bắt buộc để công bố ba con số trên |

Tổng 811 lượt gọi, chia ba nhóm đối kháng và một nhóm ngoại lệ:

| nhóm | câu hỏi | lượt | chặn | vi phạm | mờ |
|---|---|---|---|---|---|
| A | đúng tổ chức, **sai quyền** | 180 | 180 | 0 | 0 |
| B | đúng quyền, **sai tổ chức** | 360 | 360 | 0 | 0 |
| C | sai quyền **và** sai tổ chức | 90 | 90 | 0 | 0 |

Nhóm A **không** được gộp vào chỉ số xuyên tổ chức. Nó nhắm vào tài nguyên của
chính tổ chức mình bằng một vai không đủ quyền, nên theo định nghĩa nó không thể
là vi phạm xuyên tổ chức — nó là vi phạm phân quyền, và đi vào chỉ số riêng. Gộp
lại sẽ làm chính cái tên của chỉ số nói sai.

Phân bố mã trả về trên toàn lượt: 200 (181), 403 (389), 401 (121), 404 (120).
Không có mã 5xx nào.

---

## 2. Bốn lớp bằng chứng

Một con số bằng không chỉ có nghĩa khi bốn điều dưới đây cùng đúng. Thiếu bất kỳ
lớp nào, con số ấy tương thích với một hệ thống hỏng.

### Lớp 1 — đối chứng dương: chủ sở hữu thật sự làm được

| thao tác | kết quả |
|---|---|
| đọc danh tính của chính mình | đạt |
| đọc phiên thu của lớp thuộc tổ chức mình | đạt |
| đọc dữ liệu mẫu của chính mình | đạt |
| **xoá mẫu của chính mình** | đạt |

Không có lớp này, kết quả "không đọc được dữ liệu của bên kia" có hai nguyên
nhân mà phép đo âm không phân biệt được: cách ly hoạt động đúng, hoặc tài khoản
ấy vốn không đọc được gì cả. Khả năng thứ hai từng là sự thật trong dự án này —
một lượt đo trước đó chạy với ba tài khoản không có tư cách thành viên nào, và
480 ca "bị chặn" của nó không chứng minh được điều gì.

Vế **ghi** là bắt buộc chứ không phải cho đủ bộ. Nhóm đối kháng khẳng định bên A
không sửa/xoá được tài nguyên của bên B; nếu bên A vốn không sửa/xoá được bất cứ
thứ gì — vì thiếu quyền, vì cổng chống giả mạo yêu cầu, vì phiên chỉ đọc — thì
"đã chặn" không nói gì về ranh giới tổ chức. Chỉ hiệu số giữa "làm được của
mình" và "không làm được của bên kia" mới quy được cho ranh giới ấy.

#### Đối chứng dương còn làm một việc thứ hai, và nó mới là điểm đáng giữ

Lớp này thường được hiểu là phép kiểm **khả đạt**: chứng minh đường đi tồn tại và
tài khoản chạm tới được. Nhưng ở lượt đo này nó bắt được một thứ khác hẳn và
nghiêm trọng hơn: **tập danh tính được chọn để đo không thuộc lớp phân quyền mà
phép đo định nói về.**

Tài khoản ban đầu mang cờ quản trị nền tảng. Nó vượt mọi đối chứng dương một cách
trơn tru — và chính vì thế nó sẽ vượt luôn mọi rào chắn xuyên tổ chức, một cách
hợp lệ. Ma trận khi ấy vẫn chạy, vẫn cho ra một con số, và con số ấy nói về năng
lực quản trị nền tảng chứ không nói về cách ly tổ chức.

Phát biểu đúng cho phần phương pháp:

> Đối chứng dương được dùng không chỉ để xác lập tính khả đạt, mà còn để **kiểm
> chứng rằng các chủ thể được chọn thật sự đại diện cho lớp phân quyền đã định**,
> trước khi bất kỳ kết quả đối kháng nào được diễn giải.

Đây là bài học mạnh hơn nhiều so với việc kể rằng "một tài khoản quản trị đã làm
phép thử sai".

Thao tác **sửa lớp** cố ý không nằm ở lớp này. Xem mục 4.

### Lớp 2 — đối kháng xuyên tổ chức

Mười bốn thao tác, mỗi thao tác lặp ba mươi lần, nhắm vào tài nguyên của tổ chức
bên kia: đọc phiên thu, đọc dữ liệu mẫu, sửa lớp, xoá mẫu, xoá lớp, đọc hồ sơ tổ
chức, liệt kê thành viên, sửa hồ sơ tổ chức, xoá tổ chức, đổi trạng thái thanh
toán, phân giải mẫu sang lớp của bên kia, và ba thao tác đoán định danh.

Toàn bộ bị chặn. Không có mã 5xx nào, nên không có ca nào mà lỗi máy chủ có thể
đã xảy ra **sau** khi tác dụng phụ kịp ghi xuống đĩa.

Một phép kiểm phụ đáng giữ: mã tài nguyên **lạ** và mã tài nguyên **không tồn
tại** đều trả về 404. Hai câu trả lời khác nhau ở đây sẽ biến giao diện lập trình
thành máy trả lời câu hỏi "tổ chức kia có tài nguyên này không" — một kênh phụ rò
siêu dữ liệu mà không rò một hàng dữ liệu nào.

### Lớp 3 — đối chứng **hai chiều** cho phạm vi công bố đã cấu hình

> **Đây KHÔNG phải "đối chứng Community".** Lớp này đo phạm vi mà điểm cuối
> **thật sự đọc** — giá trị `public_tenant_id` trong cấu hình, hiện là tổ chức
> khởi tạo. Nó **không** đo tổ chức dự trữ mang tên cộng đồng. Chừng nào nguồn
> dữ liệu thật của điểm cuối chưa phải tổ chức ấy thì **không được viết** "ngoại
> lệ Community đã được kiểm chứng" từ kết quả ở đây. Xem mục 4.

Điểm cuối thống kê công khai là ngoại lệ tường minh: nó trả dữ liệu tổng hợp cho
người gọi bất kỳ, không cần chứng thực. Ngoại lệ nào cũng phải trả lời hai câu.

| can thiệp | kỳ vọng | quan sát | |
|---|---|---|---|
| thêm lớp + mẫu vào tổ chức A | không đổi | `0,0,0,0` | đạt |
| thêm lớp + mẫu vào tổ chức B | không đổi | `0,0,0,0` | đạt |
| **thêm lớp + mẫu vào phạm vi công bố** | **phải đổi** | `1,1,1,1` | **đạt** |
| dọn toàn bộ can thiệp | trở về ban đầu | `0,0,0,0` | đạt |

Vế thứ ba là vế quyết định, và lượt đo này cho thấy tại sao. Trạng thái nền của
bốn con số là **`0,0,0,0`** — đúng cái trường hợp suy biến mà một điểm cuối hỏng
trả về hằng số cũng sẽ cho ra. Chỉ hỏi hai câu đầu thì một điểm cuối chết hẳn
cũng "đạt" hoàn hảo. Đối chứng dương ở vế ba chứng minh nó thật sự phản ứng với
dữ liệu thuộc phạm vi công bố, và **chỉ** với dữ liệu ấy.

So sánh là so **trạng thái trước/sau quanh một can thiệp có kiểm soát**, không
phải đọc bốn con số một lần. Điều cần chứng minh là một quan hệ nhân quả, và một
lần đọc không nói được về nhân quả.

Phép đo can thiệp vào đúng phạm vi mà điểm cuối đọc, chứ không vào phạm vi mang
cái tên nghe hợp lý hơn. Mặt phẳng dữ liệu cộng đồng hiện chưa có dòng mã nào.

**Phát biểu được phép rút ra từ lớp này, và chỉ chừng ấy:**

> Số liệu tổng hợp công khai đã được đánh giá là **cách ly khỏi thay đổi trong
> các phạm vi tổ chức riêng**, và **chỉ phản ứng với thay đổi bên trong chính
> phạm vi nguồn đã được cấu hình tường minh của nó.**

Không được suy rộng thành một phát biểu về ngoại lệ Community. Đó là một mặt
phẳng khác, và nó chưa được kiểm.

### Lớp 4 — hậu điều kiện trên ba kho

Sau khi bắn xong toàn bộ ma trận, chín đối tượng được đối chiếu trên **cả ba
kho**: hàng cơ sở dữ liệu, dòng tệp bảng, và **băm nội dung** tệp đặc trưng.

Tám đối tượng nguyên vẹn tuyệt đối trên cả ba kho. Đối tượng thứ chín — mẫu mà
đối chứng dương đã cố ý xoá — mất dòng trong tệp bảng nhưng giữ hàng cơ sở dữ
liệu, đúng ngữ nghĩa xoá mềm. Đây là **bằng chứng dương**, không phải sai lệch:
nó chứng minh lượt xoá thật sự lan tới kho tệp, chứ không dừng ở cơ sở dữ liệu.

Băm nội dung là bắt buộc chứ không phải cho chắc. Phép đếm hàng và phép kiểm tồn
tại đều bỏ qua một tệp bị ghi đè, và một lượt sửa lén đi lọt sẽ hiện ra "còn
nguyên" dưới cả hai phép ấy.

---

## 3. Điều kiện để con số này có nghĩa

Phép đo chạy trên một tiến trình phục vụ **riêng**, không phải tiến trình vận
hành. Bộ thử cố tình phát lệnh xoá tổ chức, xoá mẫu và xoá lớp; cả ba **phải** bị
chặn, nhưng phép đo tồn tại chính vì điều đó chưa được chứng minh. Nếu cách ly
thủng, phép đo sẽ chứng minh bằng cách xoá thật.

| điều kiện | giá trị |
|---|---|
| cơ sở dữ liệu | `signdb_test` — không phải cơ sở dữ liệu vận hành |
| vai lúc chạy | vai ứng dụng đặc quyền tối thiểu |
| quyền siêu người dùng | không |
| quyền bỏ qua kiểm soát theo dòng | **không** |
| phiên bản lược đồ | 5 |
| cây dữ liệu | dùng-một-lần, sinh mới cho lượt này, xoá sau khi xong |

Hai thuộc tính vai phải đọc cùng nhau: kiểm soát theo dòng **thật sự có hiệu
lực**, vì tiến trình nối bằng một vai không có quyền bỏ qua nó. Nối bằng vai quản
trị thì mọi chính sách chỉ là trang trí, và con số bằng không sẽ vô nghĩa.

Kiểm soát theo dòng là **thật**, trên lược đồ thật. Không giả lập, không cắt
chính sách. Giả lập cơ chế này thì phép đo mất toàn bộ giá trị.

Giới hạn tần suất được nới **trong môi trường đo**, không bao giờ trên hệ thống
vận hành. Lý do là kỹ thuật, không phải để lấy số đẹp: mã 429 rơi vào nhóm không
kết luận được, và nguyên tắc công bố là chỉ ghi chỉ số khi số ca không kết luận
bằng không. Giữ nguyên trần thì hơn năm trăm phép thử sẽ cho ra hơn năm trăm ca
mờ và không đo được gì.

### Truy nguyên: mã nào đã được đo

Mã ứng dụng được **đóng băng thành ảnh chụp bất biến** trước khi đo, rồi gắn vào
tiến trình phục vụ ở chế độ **chỉ đọc**. Từ thời điểm chụp, mã của lượt đo không
đổi được nữa — kể cả khi cây làm việc chạy tiếp bên dưới, chuyện đã xảy ra bốn
lần trong dự án này.

| danh tính | giá trị | loại |
|---|---|---|
| **ảnh chụp mã nguồn được đo, bất biến** | `b85d4271d7dcd174…` | **danh tính chính thức của lượt đo** |
| commit gần nhất bên dưới | `69dbce5` | tham chiếu phụ, **không phải** thứ đã được đo |
| cơ sở dữ liệu | `signdb_test`, hỏi máy chủ chứ không đọc lại chuỗi cấu hình | |

Hai dòng đầu phải đọc tách bạch. `b85d4271` là **băm cây mã nguồn đã đóng băng**,
không phải một đối tượng nào của hệ quản lý phiên bản. Nó **không** được gọi là
"commit đã review", vì nó không phải commit: cây làm việc còn hai tệp chưa lưu
tại thời điểm đóng băng (xem dưới). Ép nó thành một khái niệm quản lý phiên bản
mà nó không thuộc về sẽ tạo ra một truy nguyên nghe chặt hơn thực tế.

Điều thật sự bảo chứng cho lượt đo không phải một mã commit, mà là: **mười hai
mô-đun khớp ảnh chụp cả trước lẫn sau**, và ảnh chụp được gắn ở chế độ chỉ đọc
nên không đổi được ở giữa.

Ảnh chụp còn được **đối chiếu từng mô-đun** với mã đang chạy, cả **trước và sau**
lượt đo: mười hai mô-đun quyết định hành vi được hỏi `__file__` của chính mô-đun
đã nạp, rồi băm đúng tệp ở đường dẫn ấy. Không lệch mô-đun nào ở cả hai lần kiểm.

Đối chiếu theo mô-đun chứ không theo "tệp có mặt trong container": thư viện được
nạp theo đường tìm kiếm, và đường ấy có thể trỏ tới một bản khác đã cài sẵn. Khi
đó băm tệp gắn vào thì khớp, còn mã thật sự chạy lại nằm chỗ khác.

**Cây làm việc không sạch tại thời điểm đóng băng**, và điều đó được ghi ra thay
vì làm ngơ. Hai tệp chưa commit: một bản vá đang dở dang cho một lỗ rò bộ nhớ đệm
tiến trình ở đường huấn luyện, và một tệp kiểm thử đi kèm. Ảnh chụp **có** chứa
bản vá ấy, nên nó nằm trong thứ được đo. Nó không nằm trên đường đi nào của ma
trận này — không thao tác nào chạm tới nhóm điểm cuối huấn luyện — nhưng danh
tính của lượt đo là **băm cây ảnh chụp**, không phải commit, và mọi phát biểu
truy nguyên phải bám vào băm ấy.

---

## 4. Điều phép đo **không** chứng minh

Ghi thẳng vào đây, vì một bằng chứng hợp lệ trong đúng phạm vi của nó mạnh hơn
một bằng chứng bị bác vì suy diễn vượt phạm vi.

### Ngoài phạm vi theo thiết kế

Bốn nhóm dữ liệu của đường theo dõi thí nghiệm và mô hình — tập dữ liệu, phiên
bản tập dữ liệu, thí nghiệm, và phiên bản mô hình — **không** nằm trong phạm vi
này. Chúng thuộc mặt phẳng sở hữu theo **người dùng**, không theo tổ chức, nên
chúng không có cột phạm vi để kiểm soát theo dòng bám vào.

Thẩm quyền ký mật mã theo tổ chức cũng nằm ngoài: thẩm quyền ấy hiện gắn theo
**máy**, không theo tổ chức.

### Không kiểm được, và vì sao

**Đổi phạm vi sang không gian làm việc / dự án.** Giao diện lập trình chưa có
điểm cuối nào cho hai tầng này, nên chiều tấn công ấy không được chứng minh theo
chiều nào cả.

**Tạo lớp mang định danh tổ chức của bên kia.** Điểm cuối tạo lớp đọc đúng sáu
trường từ thân yêu cầu, và định danh tổ chức không nằm trong đó — phạm vi lấy từ
ngữ cảnh yêu cầu. Không có vector ghi xuyên tổ chức ở đường này để thử. Thao tác
bị **gỡ khỏi mẫu số**, và việc gỡ được nói ra ở đây thay vì làm lặng lẽ: chấm nó
là "đã chặn" sẽ là một phát biểu về cách ly rút ra từ một đường không hề nhận
tham số phạm vi. Lý do thứ hai, độc lập: chính điểm cuối ấy đang trả lỗi máy chủ
cho **mọi** người gọi trên bản mã đo — xem mục dưới.

### Hai phát hiện của chính lượt đo này — **thuộc hai loại khác nhau**

Cả hai được ghi thành phát hiện của bản mã đang đo, **không** vá rồi đo tiếp. Và
chúng phải đi về hai chỗ khác nhau trong quyển: gộp chung là làm sai bản chất của
cả hai.

#### F1 — Đường gọi thiếu phạm vi: **hồi quy tính khả dụng, hỏng theo hướng đóng**

| trục | phán định |
|---|---|
| Cách ly an ninh | **hỏng theo hướng ĐÓNG** — không tạo ra rò rỉ xuyên tổ chức |
| Tính đúng đắn chức năng | **HỎNG** trên các đường bị ảnh hưởng |
| Ảnh hưởng tới P0-B | là phát hiện; **không** làm phát sinh rò rỉ xuyên tổ chức |
| Ảnh hưởng tới P1-B | **bắt buộc xuất hiện** trong báo cáo kết quả chức năng |

Hàm đọc danh mục lớp từ kho tệp nay bắt buộc nhận phạm vi tổ chức, nhưng lượt
chuyển các nơi gọi chưa xong: bảy nơi còn thiếu. Hai nơi nằm trên đường đi thật —
tạo lớp mới trả lỗi máy chủ cho **mọi** tài khoản, và đồng bộ dữ liệu lúc khởi
động gãy.

Hàm **ném lỗi** chứ không rơi về đọc toàn kho, nên đường gọi thiếu phạm vi gãy
thay vì lặng lẽ đọc dữ liệu của tổ chức khác. Đây là cái giá của việc bịt một lỗ
rò, hiện ra ở dạng dễ thấy nhất.

Điều này **không** được nuốt chỉ vì P0-B xanh. Lỗi tạo lớp là một hỏng hóc chức
năng trên đường đi chính của sản phẩm, và nó phải xuất hiện ở phần kết quả chức
năng và phần thảo luận. Chi tiết:
`docs/10-issues/FINDING_P0B_unscoped_load_labels.md`.

#### F2 — Cờ quản trị gộp hai thẩm quyền: **khuyết tật ranh giới phân quyền**

| trục | phán định |
|---|---|
| Danh tính dùng để đo cách ly | **KHÔNG ĐƯỢC dùng** tài khoản mang cờ quản trị nền tảng |
| Mô hình phân quyền | **khuyết tật ranh giới đặc quyền có thật** |
| Ảnh hưởng tới P0-B | phép đo còn hiệu lực **chỉ vì** các danh tính được đánh giá là người dùng có phạm vi tổ chức, không mang thẩm quyền nền tảng |

Một tài khoản mang cờ ấy đọc, liệt kê và xoá được tổ chức khác. Điều này **không
được trình bày như một vụ vượt ranh giới xuyên tổ chức**: trong mô hình hiện
hành, cờ ấy **mang thẩm quyền nền tảng**, nên hành vi đó đúng với ngữ nghĩa của
nó.

Khuyết tật nằm ở chỗ khác: **một cờ đang đại diện cho hai loại thẩm quyền khác
nhau** — "miễn kiểm quyền sở hữu" và "thẩm quyền trên mọi tổ chức" — và không có
đường cấp riêng lẻ. Hậu quả kép: ngữ nghĩa phân quyền quá rộng, và việc **chọn
danh tính cho phép đo rất dễ sai**.

Chính cái sai thứ hai suýt xảy ra ở đây. Chạy ma trận bằng tài khoản ấy thì mọi
thao tác xuyên tổ chức đo **năng lực quản trị nền tảng** chứ không đo cách ly, và
tỉ lệ vi phạm công bố ra sẽ đo sai đối tượng nhưng trông hoàn toàn hợp lý. Lượt
chính thức vì thế chạy bằng tài khoản tổ chức thường. Chi tiết:
`docs/10-issues/FINDING_P0B_platform_admin_crosses_tenants.md`.

Hệ quả kèm theo: mọi thao tác sửa và xoá lớp gác sau quyền quản trị **nền tảng**,
không sau vai trong tổ chức — nên một tổ chức **không tự sửa được lớp của chính
mình**. Vì vậy thao tác sửa lớp nằm ở nhóm "đúng tổ chức, sai quyền", nơi bị từ
chối là kết cục đúng, chứ không nằm ở đối chứng dương.

### Ranh giới sâu hơn: hai mức cách ly

Phép đo này chứng minh cách ly **Mức I**: kẻ tấn công là người dùng giao diện lập
trình, không có thông tin xác thực cơ sở dữ liệu.

Nó **không** chứng minh Mức II — kẻ tấn công chạy được câu lệnh tuỳ ý dưới vai
ứng dụng. Ở mức đó, phạm vi tổ chức là thứ do **chính tầng ứng dụng tự khai
báo**, nên cơ chế theo dòng thực thi phạm vi cho một ngữ cảnh **đã được khai
báo**; nó không xác thực ngữ cảnh ấy. Đây là giới hạn **cấu trúc**, không phải
một chỗ chưa làm.

Hai câu **không** được viết vào quyển: rằng dữ liệu không lọt kể cả khi mã ứng
dụng có sơ suất, và rằng cách ly được bảo đảm ở tầng thấp nhất. Cả hai đều mạnh
hơn bằng chứng.

---

## 5. Phát biểu được phép dùng

> Cách ly giữa các tổ chức đã được chứng minh trên **các đường giao diện lập
> trình và kho lưu trữ có phạm vi tổ chức đã được đánh giá**, với **không một
> thao tác xuyên tổ chức hay trái quyền nào thành công, và không một ca nào
> không kết luận được** trong ma trận đối kháng đã công bố. Nằm **ngoài** khẳng
> định này: các hỏng hóc chức năng đã biết vốn hỏng theo hướng đóng, phân hệ theo
> dõi thí nghiệm và mô hình có phạm vi theo người dùng, ngữ nghĩa thẩm quyền cấp
> nền tảng, và thẩm quyền ký mật mã theo tổ chức.

Đủ mạnh để đứng, và không để hội đồng tìm được một bảng thiếu cột phạm vi rồi bác
cả kết luận.

Riêng lớp 3, phát biểu **không** được gộp vào câu trên mà phải đứng riêng đúng
phạm vi của nó:

> Số liệu tổng hợp công khai được đánh giá đã được cách ly khỏi thay đổi trong
> các phạm vi tổ chức riêng, và chỉ phản ứng với thay đổi bên trong chính phạm vi
> nguồn đã được cấu hình tường minh của nó.

Không viết "ngoại lệ Community đã được kiểm chứng" cho tới khi nguồn dữ liệu thật
của điểm cuối là tổ chức dự trữ mang tên ấy.

Không có trạng thái "gần đạt". Bốn lớp cùng xanh thì công bố; thiếu một lớp thì
phát biểu hạ xuống *có bằng chứng một phần*, và chỉ số không lên bảng.
