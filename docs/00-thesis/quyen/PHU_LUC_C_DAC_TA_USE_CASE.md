# PHỤ LỤC C: ĐẶC TẢ USE CASE CHI TIẾT

*Chương 1 §2 trình bày bối cảnh nghiệp vụ và đặc tả các use case cốt lõi. Phụ lục
này chứa phần còn lại của mô hình chức năng: khuôn đặc tả, mô tả đầy đủ các tác
nhân và quan hệ giữa chúng, toàn bộ quan hệ giữa các use case, bảng phân loại đủ
75 use case, và đặc tả chi tiết các use case mà thân bài chỉ nhắc tên.*

**Nguồn đặc tả:** `docs/09-specs/USE_CASE_SPECIFICATION.md` — bản dựng lại từ mã
nguồn đang chạy: 26 bộ định tuyến, hơn 30 màn hình và bộ công cụ vận hành. Mỗi use
case có ít nhất một điểm cuối, một màn hình hoặc một kịch bản thật đứng sau.

**Sơ đồ:** đặc tả để vẽ các hình use case và hoạt động nằm ở
`SO_DO_UML_VA_HUONG_DAN_VE.md`.

---

## 1. Khuôn đặc tả

Mỗi use case được mô tả bằng đúng khuôn sau, và **không** bỏ ô nào:

| Ô | Nội dung |
|---|---|
| **Tên use case / ID** | Tên tiếng Việt và mã `UC<nghiệp vụ><thứ tự>` |
| **Actor chính** | Tác nhân khởi phát và hưởng lợi chính |
| **Mức độ cần thiết** | Cốt lõi / Quan trọng / Tuỳ chọn |
| **Phân loại** | Đơn giản / Trung bình / Phức tạp |
| **Các thành phần tham gia và mối quan tâm** | Ai còn liên quan, và mỗi bên cần gì ở use case này |
| **Mô tả tóm tắt** | Một đoạn nói rõ mục tiêu nghiệp vụ |
| **Các mối quan hệ** | Association / Include / Extend / Generalization |
| **Xử lý sự kiện** | Luồng chính, đánh số; mỗi bước nêu rõ dữ liệu và phép kiểm |
| **Luồng luân phiên** | Các đường đi hợp lệ khác dẫn tới cùng mục tiêu |
| **Luồng ngoại lệ** | Mỗi nhánh có tên in đậm và nêu đủ bốn ý (xem dưới) |
| **Kết quả mong đợi** | Trạng thái hệ thống sau khi use case kết thúc, cả khi thành công lẫn khi bị chặn |

Ba mục luồng luôn đứng theo đúng thứ tự trên. **Luồng luân phiên** khác **Luồng
ngoại lệ** ở chỗ: luân phiên là một đường đi *hợp lệ* dẫn tới cùng mục tiêu
nghiệp vụ, còn ngoại lệ là một tình huống *hỏng* làm mục tiêu không đạt được theo
cách thông thường. Gộp hai loại này lại — như bản đặc tả đầu tiên đã làm — khiến
người đọc không phân biệt được cái nào là tính năng và cái nào là sự cố.

Mỗi nhánh trong **Luồng ngoại lệ** phải trả lời đủ bốn câu:

1. **Điều kiện phát sinh** — xảy ra ở bước nào của luồng chính, khi dữ liệu hoặc
   trạng thái nào không như mong đợi.
2. **Phản ứng của hệ thống** — hệ thống dừng ở đâu, báo gì, và báo cho ai.
3. **Trạng thái dữ liệu để lại** — cái gì đã được ghi, cái gì chưa, và trạng thái
   đó có nhất quán không.
4. **Đường đi tiếp của tác nhân** — làm gì để thoát khỏi tình huống, và nếu lỗi
   lặp lại thì leo thang tới đâu (thử lại có trần, khoá tạm, hay kênh hỗ trợ).

### 1.1 Mức độ cần thiết

| Giá trị | Nghĩa | Số lượng |
|---|---|---|
| **Cốt lõi** | Thiếu thì hệ thống không dùng được cho mục đích của nó | 26 |
| **Quan trọng** | Thiếu thì nghiệp vụ khập khiễng nhưng hệ thống vẫn chạy | 39 |
| **Tuỳ chọn** | Làm nghiệp vụ thuận tiện hơn, không đổi bản chất | 10 |

### 1.2 Phân loại độ phức tạp

Phân loại **không** đặt theo cảm tính. Nó tính từ ba đại lượng đếm được của chính
đặc tả: số bước của luồng chính (\(b\)), tổng số nhánh luân phiên và nhánh ngoại
lệ (\(n\)) và số quan hệ với use case khác (\(q\)):

$$\text{điểm} = b + 1{,}5n + 2q$$

| Phân loại | Khoảng điểm | Số lượng |
|---|---|---|
| **Đơn giản** | ≤ 14 | 20 |
| **Trung bình** | 15 – 20 | 45 |
| **Phức tạp** | > 20 | 10 |

Hệ số 1,5 cho nhánh luân phiên hoặc ngoại lệ và 2 cho quan hệ phản ánh chi phí
thật khi hiện thực: một nhánh rẽ tốn hơn một bước thuận, và một quan hệ với use
case khác kéo theo cả việc kiểm thử phối hợp giữa hai use case.

**Ghi chú về ngưỡng.** Ba khoảng điểm trên đã được hiệu chỉnh lại sau khi các đặc
tả được viết sâu thêm: cùng một use case, khi luồng chính được tách bước chi tiết
hơn và các nhánh ngoại lệ được nêu đủ bốn ý, số bước và số nhánh đều tăng, nên
điểm tăng theo. Công thức giữ nguyên; chỉ ngưỡng phân loại được dịch lên để tỷ lệ
giữa ba nhóm vẫn phản ánh đúng độ chênh về công sức hiện thực. Điểm của từng use
case tính lại được từ chính nội dung đặc tả trong phụ lục này, nên bảng phân loại
kiểm chứng được chứ không phải một nhận định.

### 1.3 Quy ước chiều của quan hệ — chỗ hay bị vẽ ngược

* `Include: X` nghĩa là **use case này gọi X**, và X **luôn luôn** chạy.
* `Extend: X` nghĩa là **use case này mở rộng X** — bản thân nó là phần thêm vào
  X trong một điều kiện nào đó. Use case **cơ sở không** liệt kê phần mở rộng của
  mình; chỗ nào cần tra ngược thì ghi trong ngoặc *(UCxxx mở rộng use case này)*,
  và đó là chú thích chứ không phải khai báo quan hệ.

### 1.4 Quy tắc phân chia thân bài / phụ lục

Thân bài không lặp lại toàn bộ đặc tả — làm vậy sẽ biến Chương 1 thành một danh
mục chức năng và che mất phần phân tích nghiệp vụ. Quy tắc là: **mỗi nghiệp vụ
chọn đúng một use case trục chính** để đặc tả đầy đủ ngay trong thân bài, và use
case đó phải thoả cả hai điều kiện:

1. Mức độ cần thiết là **Cốt lõi**, hoặc là chức năng mà cả nhóm nghiệp vụ xoay
   quanh — thiếu nó thì các use case còn lại của nhóm không có chỗ đứng; và
2. Nó mang ít nhất một quan hệ với use case khác, hoặc thể hiện một quyết định
   thiết kế đặc trưng của nhóm, để người đọc thấy được cả chức năng lẫn cấu trúc.

Áp quy tắc cho tám nhóm: **8 use case đặc tả ở thân bài**, **67 use case đặc tả ở
§5 của phụ lục này**. Toàn bộ 75 use case đều có mặt ở bảng phân loại §4, kèm cột
cho biết đặc tả chi tiết nằm ở đâu.

*Bảng C-1: Tám use case trục chính đặc tả ở thân bài*

| Nghiệp vụ | Mã | Tên use case | Vị trí trong thân bài | Lý do được chọn làm trục chính |
|---|---|---|---|---|
| 1 | UC105 | Đăng nhập | Chương 1, Bảng 1-14 | Cửa vào của mọi chức năng còn lại; mang «extend» từ UC106 và cơ chế chống dò nhiều lớp |
| 2 | UC201 | Thu mẫu từ camera | Chương 1, Bảng 1-15 | Chức năng sinh ra dữ liệu của cả hệ thống; mang «include» tới UC203 và quan hệ khái quát hoá *Thu nhận mẫu* |
| 3 | UC301 | Đăng ký lớp từ vựng | Chương 1, Bảng 1-16 | Không có lớp thì không thu được mẫu; thể hiện khoá định danh năm thuộc tính của lớp |
| 4 | UC401 | Khởi động tác vụ huấn luyện | Chương 1, Bảng 1-17 | Nơi ba cổng chặn độc lập gặp nhau — đặc điểm nghiệp vụ riêng của nhóm này |
| 5 | UC502 | Mời thành viên | Chương 1, Bảng 1-18 | Đường **duy nhất** để một tổ chức có thêm thành viên; nền tảng của mô hình đa tổ chức |
| 6 | UC607 | Công bố văn bản pháp lý | Chương 1, Bảng 1-19 | Cánh cửa một chiều; mang «include» tới UC601 và quyết định tính bất biến ở tầng dữ liệu |
| 7 | UC702 | Xác minh toàn vẹn nguồn sự thật | Chương 1, Bảng 1-20 | Chạy trước mọi dịch vụ khác; phân biệt toàn vẹn với thẩm quyền |
| 8 | UC805 | Quản lý khoá API | Chương 1, Bảng 1-21 | Danh tính máy tách khỏi danh tính người, chịu cùng ranh giới cách ly dữ liệu |

---

## 2. Tác nhân

### 2.1 Nguyên tắc chọn tác nhân

Một tác nhân chỉ đứng riêng khi nó **sở hữu ít nhất một use case** mà không tác
nhân nào khác gọi tới, hoặc có **quyền khác hẳn** trên cùng use case đó và hệ
thống **kiểm được** sự khác biệt ấy. Không thoả điều nào thì đó là *hồ sơ người
dùng* — một cách mô tả người ngoài đời — chứ không phải một vai trong mô hình.

Hệ thống có **10 tác nhân người** và **6 tác nhân hệ thống**.

### 2.2 Tác nhân người

| Mã | Tác nhân | Kế thừa từ | Mục tiêu chính | Hệ thống kiểm bằng |
|---|---|---|---|---|
| **A1** | Khách vãng lai | *(gốc)* | Tìm hiểu hệ thống, đọc văn bản pháp lý, dùng thử nhận dạng, tạo tài khoản | không có phiên đăng nhập ✅ |
| **A2** | Người dùng đã đăng nhập «trừu tượng» | *(gốc)* | Giữ danh tính, hồ sơ, đồng thuận, thông báo và kênh hỗ trợ của chính mình | phiên đăng nhập hợp lệ ✅ |
| **A3** | Người khiếm thính – khiếm ngôn | A2 | **Chủ thể dữ liệu**: ký hiệu bản ngữ để đóng góp mẫu, và dùng nhận dạng để giao tiếp | ⚠️ không phân biệt được |
| **A4** | Người dùng bình thường | A2 | Nghe – nói được; dùng hệ thống để **hiểu** người ký, có thể ký hộ hoặc phiên dịch | ⚠️ không phân biệt được |
| **A5** | Thành viên tổ chức | A2 | Đưa mẫu vào hệ thống và quản lý mẫu **của mình** trong tổ chức | là thành viên của một tổ chức ✅ |
| **A6** | Biên tập viên / Nghiên cứu sinh | A5 | Giữ danh mục lớp sạch; biến dữ liệu thành mô hình và kết quả trích dẫn được | vai `editor` của tổ chức ✅ |
| **A7** | Quản trị tổ chức | A6 | Điều hành **một** tổ chức: thành viên, hạn mức, xuất dữ liệu, tích hợp | vai `admin` của tổ chức ✅ |
| **A8** | Quản trị nền tảng | *(gốc)* | Đặt luật cho mọi tổ chức và giữ bằng chứng | cờ quản trị nền tảng ✅ |
| **A9** | Nhân viên hỗ trợ | A8 | Trực hàng đợi phiếu hỗ trợ | 🟡 dùng chung quyền của A8 |
| **A10** | Kỹ sư vận hành | A8 | Giữ hệ thống chạy đúng mã, đúng dữ liệu, có bản sao lưu | 🟡 quyền A8 + quyền trên máy chủ |

**Cột cuối** trả lời: *hệ thống có tự phân biệt được vai này không?* ✅ là có một
điều kiện cụ thể trong mã quyết định vai; 🟡 là kiểm được lớp quyền bao ngoài
nhưng không kiểm được chính vai đó; ⚠️ là không có căn cứ nào — vai chỉ tồn tại ở
quy trình. Bốn vai không có dấu ✅ được bàn riêng ở §6.

### 2.3 Quan hệ giữa các tác nhân

Quan hệ duy nhất giữa các tác nhân là **khái quát hoá** (generalization): tác nhân
con làm được mọi việc của tác nhân cha, và thêm việc của riêng nó. Có đúng **ba
chuỗi**:

| Chuỗi | Nội dung | Hệ thống kiểm được? |
|---|---|---|
| `A2 → A5 → A6 → A7` | Bên tổ chức: thành viên → biên tập viên / nghiên cứu sinh → quản trị tổ chức | ✅ Có — vai trong bảng thành viên tổ chức |
| `A2 → {A3, A4}` | Người dùng cuối: người khiếm thính – khiếm ngôn và người dùng bình thường | ⚠️ Không — khác **mục tiêu**, không khác quyền |
| `A8 → {A9, A10}` | Bên vận hành: nhân viên hỗ trợ và kỹ sư vận hành | 🟡 Một phần |

**A1 Khách vãng lai đứng ngoài mọi chuỗi** vì chưa có danh tính: không thể nói một
người dùng đã đăng nhập "là một khách vãng lai có thêm quyền".

**A8 tách hẳn khỏi nhánh tổ chức.** Đây là ranh giới cứng, không phải lựa chọn
trình bày: quản trị nền tảng **không** kế thừa quản trị tổ chức và ngược lại.

| | A7 Quản trị **tổ chức** | A8 Quản trị **nền tảng** |
|---|---|---|
| Phạm vi | đúng **một** tổ chức | toàn nền tảng |
| Đưa người vào bằng | **lời mời** (UC502) | **gán trực tiếp** theo mã tài khoản (UC501) |
| Giao diện | trang tổ chức | các trang quản trị nền tảng |

Lý do rất cụ thể: gán thành viên theo **mã tài khoản**, mà mã tài khoản không phải
bí mật. Nếu quản trị viên tổ chức làm được việc đó, họ kéo được bất kỳ ai trên hệ
thống vào tổ chức của mình mà người kia không hay biết. Đường đưa người vào dành
cho A7 vì thế **bắt buộc** là lời mời — thứ đòi hỏi chính người được mời hành động.

### 2.4 Tác nhân hệ thống

Tác nhân hệ thống là hệ thống ngoài hoặc thành phần tự động **khởi phát hoặc tham
gia** vào một use case. Thành phần chỉ chuyển tiếp dữ liệu mà không có quyết định
nào — máy chủ web, bộ thu nhật ký — **không** phải tác nhân.

| Mã | Tác nhân | Gồm những gì | Vai trò |
|---|---|---|---|
| **S1** | Dịch vụ gửi tin | Thư điện tử + cổng tin nhắn | Gửi mã xác thực, lời mời, nhắc hạn, thư phiếu hỗ trợ, cảnh báo |
| **S2** | Kho lưu trữ ngoài | Kho tệp đám mây + bảng tính đối soát | Giữ tệp đặc trưng, video thô, bản xem trước; phản chiếu danh bạ mẫu |
| **S3** | Dịch vụ suy luận | Suy luận thời gian thực trên GPU + tổng hợp giọng nói | Phục vụ mô hình đang hoạt động, nạp nóng khi thăng hạng, đọc thành tiếng |
| **S4** | Tiến trình nền | Tiến trình xử lý + bộ lập lịch | Trích đặc trưng, tăng cường, dựng bản xem trước, xoá tệp, đối soát, sao lưu theo lịch |
| **S5** | Máy ghi nguồn sự thật | Máy được cấp khoá ký | Ghi vào danh bạ nguồn sự thật và công bố |
| **S6** | Ứng dụng bên thứ ba | Hệ thống ngoài dùng khoá giao diện lập trình | Gọi API trong phạm vi của khoá; nhận sự kiện webhook |

**S4 gộp tiến trình xử lý và bộ lập lịch** nhưng giữ nguyên phân biệt quan trọng
nhất ở ô **Loại** của từng use case: `internal` nghĩa là **không ai bấm nút** —
việc tự chạy theo hàng đợi hoặc theo lịch. Use case duy nhất mang loại này hiện
nay là UC203.

---

## 3. Quan hệ giữa các use case

### 3.1 «include» — 13 quan hệ

Đọc là: **use case cột trái luôn gọi use case cột giữa**.

| Use case cơ sở | «include» | Vì sao luôn xảy ra |
|---|---|---|
| UC101 Đăng ký tài khoản | UC112 Chấp thuận văn bản pháp lý | Cưỡng chế đồng thuận đang bật: không chấp thuận thì tài khoản không tồn tại |
| UC102 Đăng ký theo lời mời | UC103 Gửi mã xác thực | Địa chỉ được mời vẫn phải được chứng minh là có thật |
| UC104 Xác thực địa chỉ liên hệ | UC103 Gửi mã xác thực | Không có mã thì không có gì để xác thực |
| UC108 Khôi phục tài khoản | UC103 Gửi mã xác thực | Bước một của khôi phục chính là gửi mã |
| UC112 Chấp thuận văn bản pháp lý | UC111 Xem văn bản pháp lý | Phải đọc được văn bản thì mới ký được nó |
| UC201 Thu mẫu bằng máy quay | UC203 Xử lý bản ghi | Mẫu chỉ tồn tại sau khi trích xuất đặc trưng |
| UC202 Tải tệp video | UC203 Xử lý bản ghi | Cùng lý do, khác nguồn đầu vào |
| UC503 Chấp nhận lời mời | UC102 Đăng ký theo lời mời | Lời mời **chỉ** được tiêu thụ ở đường tạo tài khoản |
| UC508 Xoá sạch dữ liệu tổ chức | UC601 Nâng quyền tạm thời | Thao tác không hoàn tác được, đòi xác thực lại |
| UC607 Công bố văn bản pháp lý | UC601 Nâng quyền tạm thời | Bản đã công bố là bất biến, không sửa lại được |
| UC609 Quản lý gói dịch vụ | UC601 Nâng quyền tạm thời | Hạ gói hay treo một tổ chức gây hậu quả thương mại thật |
| UC703 Đồng bộ kho lưu trữ và cơ sở dữ liệu | UC702 Kiểm toàn vẹn nguồn sự thật | Muốn sửa lệch thì phải biết lệch ở đâu trước |
| UC803 Trực hàng đợi hỗ trợ | UC802 Trả lời phiếu hỗ trợ | Trực hàng đợi luôn kết thúc bằng một lượt trả lời |

### 3.2 «extend» — 13 quan hệ

Đọc là: **use case cột trái là phần thêm vào use case cột giữa**, chỉ chạy khi
điều kiện ở cột phải đúng.

| Use case mở rộng | «extend» | Điều kiện |
|---|---|---|
| UC102 Đăng ký theo lời mời | UC101 Đăng ký tài khoản | Khi khách tới bằng liên kết lời mời có mã thông hành |
| UC106 Xác thực yếu tố thứ hai | UC105 Đăng nhập | Khi tài khoản đã bật xác thực hai yếu tố |
| UC109 Quản lý xác thực hai yếu tố | UC110 Quản lý hồ sơ cá nhân | Khi người dùng vào phần Bảo mật |
| UC113 Rút đồng thuận | UC112 Chấp thuận văn bản pháp lý | Khi người ký rút lại đồng thuận đã cho |
| UC114 Dùng thử nhận dạng | UC407 Nhận dạng ký hiệu thời gian thực | Khi người dùng chưa đăng nhập; giới hạn số phút mỗi ngày |
| UC208 Xem trước phiên thu | UC207 Xem chi tiết lớp | Khi muốn xem lại bản dựng của phiên thu |
| UC210 Gán lại người ký của phiên thu | UC207 Xem chi tiết lớp | Khi phát hiện phiên thu gán sai người ký |
| UC212 Quản lý thùng rác | UC211 Xoá mẫu | Khi cần hoàn tác hoặc xoá vĩnh viễn một mẫu |
| UC212 Quản lý thùng rác | UC304 Gỡ lớp khỏi danh mục | Khi cần hoàn tác hoặc xoá vĩnh viễn một lớp |
| UC303 Gộp hai lớp | UC302 Cập nhật lớp | Khi việc cần làm là gộp hai lớp trùng, không phải đổi tên một lớp |
| UC310 Nhân bản danh mục cho tổ chức | UC501 Quản lý tổ chức | Khi tổ chức vừa tạo cần danh mục mồi để bắt đầu thu |
| UC405 Thử mô hình đã huấn luyện | UC404 Xem đánh giá và nguồn gốc | Khi muốn thử một mẫu thật trước khi quyết định thăng hạng |
| UC408 Đọc thành tiếng kết quả nhận dạng | UC407 Nhận dạng ký hiệu thời gian thực | Khi người dùng bật đầu ra giọng nói |

### 3.3 «generalization» giữa các use case

| Use case cha | Use case con | Ghi chú |
|---|---|---|
| **Thu nhận mẫu** «trừu tượng» | UC201 Thu mẫu bằng máy quay, UC202 Tải tệp video | Hai nguồn đầu vào, cùng một kết quả: một mẫu đã trích đặc trưng |
| **Gỡ bỏ dữ liệu** «trừu tượng» | UC209 Xoá phiên thu, UC211 Xoá mẫu, UC304 Gỡ lớp khỏi danh mục | Cùng ngữ nghĩa xoá mềm, ba mức khác nhau |
| UC103 Gửi mã xác thực | Gửi qua thư điện tử, gửi qua tin nhắn | Hai kênh, cùng một hợp đồng mã một lần |

---

## 4. Bảng phân loại đủ 75 use case

Cột **Vị trí** cho biết đặc tả chi tiết của use case đó nằm ở thân bài hay ở §5
của phụ lục này.

### Nghiệp vụ 1 — Danh tính và quyền truy cập

*14 use case: 1 đặc tả ở thân bài, 13 đặc tả ở §5 của phụ lục này.*

| Mã | Tên use case | Tác nhân chính | Mức độ cần thiết | Phân loại | Vị trí đặc tả |
|---|---|---|---|---|---|
| UC101 | Đăng ký tài khoản | Khách vãng lai | Cốt lõi | Phức tạp | Phụ lục C §5 |
| UC102 | Đăng ký theo lời mời | Khách vãng lai | Cốt lõi | Phức tạp | Phụ lục C §5 |
| UC103 | Gửi mã xác thực | Người dùng đã đăng nhập | Cốt lõi | Trung bình | Phụ lục C §5 |
| UC104 | Xác thực địa chỉ liên hệ | Người dùng đã đăng nhập | Cốt lõi | Trung bình | Phụ lục C §5 |
| UC105 | Đăng nhập | Khách vãng lai | Cốt lõi | Trung bình | **Thân bài** |
| UC106 | Xác thực yếu tố thứ hai | Người dùng đã đăng nhập | Quan trọng | Trung bình | Phụ lục C §5 |
| UC107 | Đăng xuất | Người dùng đã đăng nhập | Cốt lõi | Đơn giản | Phụ lục C §5 |
| UC108 | Khôi phục tài khoản | Khách vãng lai | Cốt lõi | Phức tạp | Phụ lục C §5 |
| UC109 | Quản lý xác thực hai yếu tố | Người dùng đã đăng nhập | Quan trọng | Trung bình | Phụ lục C §5 |
| UC110 | Quản lý hồ sơ cá nhân | Người dùng đã đăng nhập | Quan trọng | Trung bình | Phụ lục C §5 |
| UC111 | Xem văn bản pháp lý | Khách vãng lai | Cốt lõi | Trung bình | Phụ lục C §5 |
| UC112 | Chấp thuận văn bản pháp lý | Người dùng đã đăng nhập | Cốt lõi | Trung bình | Phụ lục C §5 |
| UC113 | Rút đồng thuận | Người khiếm thính – khiếm ngôn | Cốt lõi | Trung bình | Phụ lục C §5 |
| UC114 | Dùng thử nhận dạng | Khách vãng lai | Tuỳ chọn | Trung bình | Phụ lục C §5 |

### Nghiệp vụ 2 — Thu thập và quản lý dữ liệu mẫu

*13 use case: 1 đặc tả ở thân bài, 12 đặc tả ở §5 của phụ lục này.*

| Mã | Tên use case | Tác nhân chính | Mức độ cần thiết | Phân loại | Vị trí đặc tả |
|---|---|---|---|---|---|
| UC201 | Thu mẫu từ camera | Người khiếm thính – khiếm ngôn | Cốt lõi | Phức tạp | **Thân bài** |
| UC202 | Tải lên tệp video | Thành viên tổ chức | Cốt lõi | Phức tạp | Phụ lục C §5 |
| UC203 | Xử lý bản ghi | Tiến trình nền (S4) | Cốt lõi | Phức tạp | Phụ lục C §5 |
| UC204 | Theo dõi trạng thái tác vụ | Thành viên tổ chức | Quan trọng | Đơn giản | Phụ lục C §5 |
| UC205 | Đặt tuỳ chọn thu | Thành viên tổ chức | Tuỳ chọn | Đơn giản | Phụ lục C §5 |
| UC206 | Duyệt danh mục lớp | Thành viên tổ chức | Cốt lõi | Đơn giản | Phụ lục C §5 |
| UC207 | Xem chi tiết lớp | Thành viên tổ chức | Cốt lõi | Trung bình | Phụ lục C §5 |
| UC208 | Xem lại video phiên thu | Thành viên tổ chức | Quan trọng | Trung bình | Phụ lục C §5 |
| UC209 | Xoá phiên thu | Thành viên tổ chức | Quan trọng | Trung bình | Phụ lục C §5 |
| UC210 | Gán lại người ký cho phiên thu | Biên tập viên / Nghiên cứu sinh | Tuỳ chọn | Trung bình | Phụ lục C §5 |
| UC211 | Xoá mẫu | Thành viên tổ chức | Cốt lõi | Trung bình | Phụ lục C §5 |
| UC212 | Quản lý thùng rác | Thành viên tổ chức | Quan trọng | Trung bình | Phụ lục C §5 |
| UC213 | Xuất ảnh chụp bộ dữ liệu | Biên tập viên / Nghiên cứu sinh | Quan trọng | Trung bình | Phụ lục C §5 |

### Nghiệp vụ 3 — Danh mục từ vựng và phương ngữ

*10 use case: 1 đặc tả ở thân bài, 9 đặc tả ở §5 của phụ lục này.*

| Mã | Tên use case | Tác nhân chính | Mức độ cần thiết | Phân loại | Vị trí đặc tả |
|---|---|---|---|---|---|
| UC301 | Đăng ký lớp từ vựng | Biên tập viên / Nghiên cứu sinh | Cốt lõi | Phức tạp | **Thân bài** |
| UC302 | Cập nhật lớp | Biên tập viên / Nghiên cứu sinh | Quan trọng | Trung bình | Phụ lục C §5 |
| UC303 | Gộp hai lớp trùng | Biên tập viên / Nghiên cứu sinh | Quan trọng | Trung bình | Phụ lục C §5 |
| UC304 | Gỡ lớp | Biên tập viên / Nghiên cứu sinh | Quan trọng | Trung bình | Phụ lục C §5 |
| UC305 | Xem thống kê thu thập | Thành viên tổ chức | Quan trọng | Đơn giản | Phụ lục C §5 |
| UC306 | Đề xuất phương ngữ | Biên tập viên / Nghiên cứu sinh | Tuỳ chọn | Đơn giản | Phụ lục C §5 |
| UC307 | Kiểm duyệt đề xuất phương ngữ | Quản trị nền tảng | Tuỳ chọn | Trung bình | Phụ lục C §5 |
| UC308 | Bảo trì danh mục mẫu của cộng đồng | Quản trị nền tảng | Quan trọng | Đơn giản | Phụ lục C §5 |
| UC309 | Công bố phiên bản danh mục cộng đồng | Quản trị nền tảng | Quan trọng | Đơn giản | Phụ lục C §5 |
| UC310 | Sao chép danh mục vào một tổ chức | Quản trị nền tảng | Quan trọng | Trung bình | Phụ lục C §5 |

### Nghiệp vụ 4 — Huấn luyện, đánh giá và suy luận

*9 use case: 1 đặc tả ở thân bài, 8 đặc tả ở §5 của phụ lục này.*

| Mã | Tên use case | Tác nhân chính | Mức độ cần thiết | Phân loại | Vị trí đặc tả |
|---|---|---|---|---|---|
| UC401 | Khởi động tác vụ huấn luyện | Biên tập viên / Nghiên cứu sinh | Cốt lõi | Phức tạp | **Thân bài** |
| UC402 | Theo dõi tiến trình huấn luyện | Biên tập viên / Nghiên cứu sinh | Cốt lõi | Đơn giản | Phụ lục C §5 |
| UC403 | Huỷ tác vụ huấn luyện | Biên tập viên / Nghiên cứu sinh | Quan trọng | Trung bình | Phụ lục C §5 |
| UC404 | Xem kết quả đánh giá và nguồn gốc | Biên tập viên / Nghiên cứu sinh | Quan trọng | Trung bình | Phụ lục C §5 |
| UC405 | Thử mô hình đã huấn luyện | Biên tập viên / Nghiên cứu sinh | Quan trọng | Trung bình | Phụ lục C §5 |
| UC406 | Thăng hạng phiên bản mô hình | Quản trị nền tảng | Quan trọng | Trung bình | Phụ lục C §5 |
| UC407 | Nhận dạng ký hiệu thời gian thực | Người khiếm thính – khiếm ngôn | Cốt lõi | Phức tạp | Phụ lục C §5 |
| UC408 | Đọc thành tiếng văn bản nhận dạng | Người dùng bình thường | Tuỳ chọn | Trung bình | Phụ lục C §5 |
| UC409 | Chuẩn bị bản phát hành nghiên cứu | Biên tập viên / Nghiên cứu sinh | Quan trọng | Trung bình | Phụ lục C §5 |

### Nghiệp vụ 5 — Tổ chức và đăng ký dịch vụ

*8 use case: 1 đặc tả ở thân bài, 7 đặc tả ở §5 của phụ lục này.*

| Mã | Tên use case | Tác nhân chính | Mức độ cần thiết | Phân loại | Vị trí đặc tả |
|---|---|---|---|---|---|
| UC501 | Quản lý tổ chức | Quản trị nền tảng | Cốt lõi | Trung bình | Phụ lục C §5 |
| UC502 | Mời thành viên | Quản trị tổ chức | Cốt lõi | Phức tạp | **Thân bài** |
| UC503 | Chấp nhận lời mời | Khách vãng lai | Cốt lõi | Trung bình | Phụ lục C §5 |
| UC504 | Đổi vai thành viên | Quản trị tổ chức | Quan trọng | Đơn giản | Phụ lục C §5 |
| UC505 | Gỡ thành viên | Quản trị tổ chức | Quan trọng | Đơn giản | Phụ lục C §5 |
| UC506 | Quản lý gói dịch vụ | Quản trị tổ chức | Quan trọng | Trung bình | Phụ lục C §5 |
| UC507 | Yêu cầu xuất dữ liệu tổ chức | Quản trị tổ chức | Quan trọng | Trung bình | Phụ lục C §5 |
| UC508 | Dọn sạch dữ liệu tổ chức | Quản trị nền tảng | Tuỳ chọn | Trung bình | Phụ lục C §5 |

### Nghiệp vụ 6 — Quản trị người dùng và chính sách

*9 use case: 1 đặc tả ở thân bài, 8 đặc tả ở §5 của phụ lục này.*

| Mã | Tên use case | Tác nhân chính | Mức độ cần thiết | Phân loại | Vị trí đặc tả |
|---|---|---|---|---|---|
| UC601 | Nâng quyền tạm thời | Quản trị nền tảng | Quan trọng | Trung bình | Phụ lục C §5 |
| UC602 | Quản lý tài khoản người dùng | Quản trị nền tảng | Cốt lõi | Trung bình | Phụ lục C §5 |
| UC603 | Áp dụng biện pháp bảo mật | Quản trị nền tảng | Quan trọng | Đơn giản | Phụ lục C §5 |
| UC604 | Xem nhật ký kiểm toán | Quản trị nền tảng | Quan trọng | Đơn giản | Phụ lục C §5 |
| UC605 | Cấu hình tham số nền tảng | Quản trị nền tảng | Quan trọng | Đơn giản | Phụ lục C §5 |
| UC606 | Soạn và duyệt văn bản pháp lý | Quản trị nền tảng | Quan trọng | Trung bình | Phụ lục C §5 |
| UC607 | Công bố văn bản pháp lý | Quản trị nền tảng | Cốt lõi | Trung bình | **Thân bài** |
| UC608 | Rà soát hồ sơ đồng thuận | Quản trị nền tảng | Quan trọng | Đơn giản | Phụ lục C §5 |
| UC609 | Quản lý gói cước | Quản trị nền tảng | Tuỳ chọn | Trung bình | Phụ lục C §5 |

### Nghiệp vụ 7 — Vận hành hệ thống và nguồn sự thật

*6 use case: 1 đặc tả ở thân bài, 5 đặc tả ở §5 của phụ lục này.*

| Mã | Tên use case | Tác nhân chính | Mức độ cần thiết | Phân loại | Vị trí đặc tả |
|---|---|---|---|---|---|
| UC701 | Quản lý máy ghi nguồn sự thật | Kỹ sư vận hành | Quan trọng | Đơn giản | Phụ lục C §5 |
| UC702 | Xác minh toàn vẹn nguồn sự thật | Kỹ sư vận hành | Quan trọng | Trung bình | **Thân bài** |
| UC703 | Đồng bộ kho lưu trữ và cơ sở dữ liệu | Kỹ sư vận hành | Quan trọng | Trung bình | Phụ lục C §5 |
| UC704 | Giám sát sức khoẻ hệ thống | Kỹ sư vận hành | Quan trọng | Trung bình | Phụ lục C §5 |
| UC705 | Sao lưu và khôi phục dữ liệu | Kỹ sư vận hành | Cốt lõi | Trung bình | Phụ lục C §5 |
| UC706 | Kiểm chứng độ tươi của triển khai | Kỹ sư vận hành | Quan trọng | Đơn giản | Phụ lục C §5 |

### Nghiệp vụ 8 — Hỗ trợ và tích hợp

*6 use case: 1 đặc tả ở thân bài, 5 đặc tả ở §5 của phụ lục này.*

| Mã | Tên use case | Tác nhân chính | Mức độ cần thiết | Phân loại | Vị trí đặc tả |
|---|---|---|---|---|---|
| UC801 | Tạo phiếu hỗ trợ | Người dùng đã đăng nhập | Quan trọng | Đơn giản | Phụ lục C §5 |
| UC802 | Trả lời phiếu hỗ trợ | Người dùng đã đăng nhập | Quan trọng | Đơn giản | Phụ lục C §5 |
| UC803 | Trực hàng đợi hỗ trợ | Nhân viên hỗ trợ | Quan trọng | Trung bình | Phụ lục C §5 |
| UC804 | Xem thông báo | Người dùng đã đăng nhập | Quan trọng | Đơn giản | Phụ lục C §5 |
| UC805 | Quản lý khoá API | Quản trị tổ chức | Tuỳ chọn | Trung bình | **Thân bài** |
| UC806 | Quản lý điểm nhận webhook | Quản trị tổ chức | Tuỳ chọn | Trung bình | Phụ lục C §5 |

## 5. Đặc tả chi tiết 67 use case

*Trình bày theo thứ tự nghiệp vụ và thứ tự mã. Tám use case trục chính đã đặc tả ở
Chương 1 §2 không lặp lại ở đây; vị trí của chúng ghi ở Bảng C-1.*

*Mỗi đặc tả gồm ba phần luồng, theo đúng thứ tự: **Xử lý sự kiện** mô tả luồng
chính khi mọi điều kiện đều thoả; **Luồng luân phiên** mô tả các đường đi hợp lệ
khác dẫn tới cùng mục tiêu; **Luồng ngoại lệ** mô tả các tình huống hỏng, mỗi
tình huống nêu đủ bốn ý — điều kiện phát sinh, phản ứng của hệ thống, trạng thái
dữ liệu để lại, và đường đi tiếp của tác nhân kể cả khi lỗi lặp lại.*

---

### 5.1 Nghiệp vụ 1 — Danh tính và quyền truy cập

#### UC101 — Đăng ký tài khoản

*Bảng C-2: Mô tả chức năng Đăng ký tài khoản*

| **Tên use case** | Đăng ký tài khoản | **ID** | UC101 |
|---|---|---|---|
| **Actor chính** | Khách vãng lai | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Khách vãng lai | **Phân loại** | Phức tạp |
| **Loại** | external | **Nghiệp vụ** | 1 — Danh tính và quyền truy cập |

**Các thành phần tham gia và mối quan tâm:**

- **Khách vãng lai** — có được một tài khoản dùng được ngay, không phải khai nhiều hơn mức cần thiết.
- **Tổ chức tiếp nhận** — chỉ nhận thành viên hợp lệ; người lạ không được ghi vào danh mục lớp của tổ chức.
- **Bộ phận pháp chế của nền tảng** — mọi tài khoản đều để lại bằng chứng đã chấp thuận đúng phiên bản văn bản đang hiệu lực.
- **Dịch vụ gửi tin (S1)** — nhận yêu cầu gửi mã xác thực tới địa chỉ vừa khai.

**Mô tả tóm tắt:** *Khách vãng lai tạo một tài khoản trên nền tảng bằng tên đăng nhập, địa chỉ thư điện tử và mật khẩu. Tài khoản được tạo bên trong một tổ chức và chưa dùng được cho tới khi các văn bản pháp lý đang hiệu lực được chấp thuận.*

**Các mối quan hệ:**

- **Association (kết hợp):** Khách vãng lai – Đăng ký tài khoản; Dịch vụ gửi tin (S1)
- **Include (bao gồm):** UC112 Chấp thuận văn bản pháp lý
- **Extend (mở rộng):** không *(UC102 mở rộng use case này)*
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Khách vãng lai mở trang đăng ký. Hệ thống hiển thị biểu mẫu gồm bốn trường bắt buộc — tên đăng nhập, địa chỉ thư điện tử, mật khẩu, xác nhận mật khẩu — kèm danh sách các văn bản pháp lý đang hiệu lực, mỗi văn bản ghi rõ loại, số phiên bản và ngày hiệu lực.
2. Khách nhập bốn trường trên. Hệ thống chuẩn hoá địa chỉ thư về dạng chữ thường và cắt khoảng trắng thừa ngay khi khách rời khỏi trường, để hai cách gõ khác nhau của cùng một địa chỉ không tạo ra hai tài khoản.
3. Khách mở từng văn bản để đọc (UC111), rồi đánh dấu ô chấp thuận tương ứng. Riêng văn bản đồng thuận thu thập dữ liệu, khách chọn một trong ba mức phát hành được đề nghị (UC112).
4. Khách bấm nút "Tạo tài khoản".
5. Hệ thống kiểm hai hạn mức chống lạm dụng tính theo địa chỉ IP của yêu cầu: số lần gửi biểu mẫu trong một phút, và số tài khoản **thật sự được tạo** từ địa chỉ đó trong cửa sổ 24 giờ. Hai hạn mức này được kiểm trước mọi thao tác tốn kém khác.
6. Hệ thống kiểm chính sách mở đăng ký của nền tảng: nếu nền tảng đang ở chế độ chỉ nhận thành viên qua lời mời, yêu cầu phải kèm một mã mời hợp lệ.
7. Hệ thống kiểm tên đăng nhập và địa chỉ thư chưa bị tài khoản nào dùng.
8. Hệ thống kiểm mật khẩu đạt chính sách độ dài tối thiểu và kiểm hai trường mật khẩu khớp nhau, rồi băm mật khẩu bằng hàm băm có làm chậm chủ đích.
9. Hệ thống tạo bản ghi tài khoản, gắn tài khoản vào một tổ chức, và lưu một bản ghi đồng thuận cho **mỗi** văn bản đã chấp thuận, mỗi bản ghi kèm số phiên bản và mã băm nội dung văn bản tại thời điểm chấp thuận.
10. Hệ thống ghi một mục vào nhật ký kiểm toán gồm hành động, định danh tài khoản mới, định danh tổ chức, địa chỉ IP và thời điểm.
11. Hệ thống phát một mã dùng một lần gửi tới địa chỉ thư vừa khai (UC103), tạo phiên làm việc, đặt token truy cập và token làm mới vào cookie chỉ đọc phía máy chủ, rồi chuyển khách tới bảng điều khiển kèm dải nhắc xác thực địa chỉ.

**Luồng luân phiên:**

1. **Đăng ký bằng lời mời:** nếu khách tới trang đăng ký bằng liên kết lời mời, luồng chuyển sang UC102 — trường địa chỉ thư được điền sẵn và khoá lại, tổ chức cùng vai của tài khoản lấy theo mã mời chứ không theo mặc định, và bước 6 kiểm mã mời thay vì kiểm chính sách mở đăng ký. Các bước 7–11 giữ nguyên.
2. **Chưa chọn mức phát hành:** khách có thể tạo tài khoản mà chưa chọn mức phát hành cho văn bản đồng thuận thu thập dữ liệu, nếu văn bản này không nằm trong nhóm buộc phải chấp thuận. Tài khoản dùng được bình thường, nhưng mẫu do tài khoản đó đóng góp không phát hành được ở bất kỳ mức nào cho tới khi mức phát hành được chọn ở trang Tài khoản (UC112).

**Luồng ngoại lệ:**

1. **Đăng ký tự phục vụ đang đóng.** Ở bước 6, nếu quản trị nền tảng đã tắt đăng ký tự phục vụ và yêu cầu không kèm mã mời, hệ thống dừng ngay tại đây và trả về thông báo rằng nền tảng chỉ nhận thành viên qua lời mời. Không có bản ghi tài khoản nào được tạo, và biểu mẫu giữ lại những gì khách đã gõ trừ hai trường mật khẩu. Khách phải liên hệ quản trị viên của tổ chức mình muốn tham gia để xin một lời mời; khi nhận được liên kết mời, khách đi theo luồng luân phiên 1. Nếu khách không biết liên hệ ai, đường còn lại là gửi phiếu hỗ trợ qua biểu mẫu công khai (UC801).

2. **Trùng tên đăng nhập hoặc địa chỉ thư điện tử.** Ở bước 7, nếu giá trị khách nhập đã thuộc về một tài khoản khác, hệ thống dừng lại và báo lỗi ngay tại trường sai, giữ nguyên các trường còn lại để khách không phải gõ lại từ đầu. Không có tài khoản nào được tạo và không mã xác thực nào được gửi. Khách sửa lại giá trị bị trùng rồi gửi lại. Nếu khách thử lặp lại nhiều lần với các giá trị khác nhau, hạn mức mười lần trên một phút ở bước 5 sẽ chặn trước khi việc dò tên trở nên hữu ích cho người dò. Trường hợp khách tin rằng địa chỉ đó là của chính mình nhưng không đăng nhập được, đường xử lý đúng là khôi phục tài khoản (UC108) chứ không phải đăng ký lại.

3. **Mật khẩu không đạt chính sách.** Ở bước 8, nếu mật khẩu ngắn hơn độ dài tối thiểu hoặc hai trường mật khẩu không khớp, hệ thống liệt kê từng yêu cầu chưa đạt ngay dưới trường mật khẩu và không tạo tài khoản. Lượt gửi này vẫn tính vào hạn mức mười lần trên một phút, nhưng **không** tính vào hạn mức số tài khoản trong 24 giờ vì hạn mức đó chỉ đếm tài khoản thật sự được tạo. Khách nhập lại mật khẩu đạt yêu cầu và gửi lại; không có giới hạn riêng cho số lần sửa mật khẩu ngoài hạn mức chung theo phút.

4. **Chạm trần tần suất theo địa chỉ IP.** Ở bước 5, nếu số lần gửi biểu mẫu từ địa chỉ IP đó đã vượt mười lần trong một phút, hoặc số tài khoản đã tạo từ địa chỉ đó đã chạm trần một trăm tài khoản trong 24 giờ, hệ thống từ chối yêu cầu trước khi chạm tới cơ sở dữ liệu và trả về thời gian còn phải chờ. Trần theo phút nhằm chặn kịch bản tự động gửi biểu mẫu liên tục; trần theo ngày nhằm chặn việc tạo hàng loạt tài khoản. Khách chờ hết cửa sổ rồi thử lại. Nếu khách đang dùng một địa chỉ IP chia sẻ cho nhiều người — phòng máy của trường, mạng của một tổ chức — và cả nhóm cùng đăng ký trong một buổi, ngưỡng cảnh báo trung gian sẽ ghi vào nhật ký để quản trị viên phân biệt được đợt đăng ký thật với một đợt tấn công; khách trong tình huống này nên đăng ký theo lời mời (UC102), đường không bị trần tài khoản theo ngày ràng buộc như đường tự phục vụ.

5. **Chưa chấp thuận đủ văn bản bắt buộc.** Ở bước 3, chừng nào còn một văn bản bắt buộc chưa được đánh dấu, nút "Tạo tài khoản" vẫn ở trạng thái khoá, và nếu yêu cầu vẫn được gửi thẳng tới máy chủ thì tầng cưỡng chế đồng thuận từ chối nó. Đây là hành vi có chủ ý và không có đường vòng: một tài khoản không kèm đồng thuận là trạng thái mà hệ thống không cho tồn tại, vì mọi mẫu dữ liệu về sau đều phải truy được về một đồng thuận cụ thể. Khách buộc phải đọc và đánh dấu đủ các văn bản bắt buộc mới đi tiếp được.

6. **Tạo được tài khoản nhưng chưa gắn được vào tổ chức.** Ở bước 9, nếu bản ghi tài khoản đã được ghi nhưng thao tác gắn tài khoản vào tổ chức thất bại, hệ thống **không** xoá tài khoản vừa tạo mà báo lỗi nêu đích danh tình trạng: tài khoản đã có, tư cách thành viên thì chưa. Khách vẫn đăng nhập được nhưng chưa thấy dữ liệu của tổ chức nào. Đường xử lý là nhờ quản trị tổ chức mời lại tài khoản đó vào tổ chức (UC502), hoặc gửi phiếu hỗ trợ (UC801). Hệ thống chọn báo lỗi rõ ràng thay vì im lặng dọn dẹp, vì một thao tác xoá tài khoản tự động chạy trên đường lỗi là chỗ dễ xoá nhầm tài khoản có thật.

7. **Không gửi được mã xác thực.** Ở bước 11, nếu dịch vụ gửi tin từ chối hoặc hết thời gian chờ, tài khoản **vẫn đã được tạo** và phiên làm việc vẫn được cấp; hệ thống hiển thị cảnh báo rằng chưa gửi được mã và cho khách yêu cầu gửi lại (UC104). Đây là quyết định có chủ ý: buộc việc tạo tài khoản phụ thuộc vào kết quả gửi thư sẽ biến một sự cố của nhà cung cấp thư thành một sự cố đăng ký, và để lại những tài khoản dở dang mà khách không biết mình đã có. Nếu việc gửi lại vẫn hỏng sau vài lần, khách dùng hệ thống ở mức không cần địa chỉ đã xác thực và liên hệ hỗ trợ (UC801).

**Kết quả mong đợi:** Một tài khoản mới tồn tại bên trong đúng một tổ chức, kèm một bản ghi đồng thuận cho mỗi văn bản bắt buộc — mỗi bản ghi gắn số phiên bản và mã băm nội dung tại thời điểm chấp thuận. Khách đang ở trong một phiên làm việc hợp lệ, một mã xác thực đã được phát tới địa chỉ vừa khai, và nhật ký kiểm toán có một mục truy được về lần tạo tài khoản này. Nếu bất kỳ phép kiểm nào ở bước 5–8 không đạt, không có bản ghi tài khoản nào được tạo và không có mã nào được gửi.

---

#### UC102 — Đăng ký theo lời mời

*Bảng C-3: Mô tả chức năng Đăng ký theo lời mời*

| **Tên use case** | Đăng ký theo lời mời | **ID** | UC102 |
|---|---|---|---|
| **Actor chính** | Khách vãng lai | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Khách vãng lai mở liên kết lời mời | **Phân loại** | Phức tạp |
| **Loại** | external | **Nghiệp vụ** | 1 — Danh tính và quyền truy cập |

**Các thành phần tham gia và mối quan tâm:**

- **Người được mời** — vào đúng tổ chức đã mời mình, với đúng vai đã được hứa.
- **Quản trị tổ chức đã gửi lời mời** — lời mời chỉ dùng được một lần, đúng người, đúng địa chỉ.
- **Nền tảng** — mã mời hết hạn hoặc đã thu hồi thì không tạo ra tài khoản nào.

**Mô tả tóm tắt:** *Khách vãng lai đăng ký bằng một mã mời do quản trị tổ chức phát hành. Mã mời quyết định tài khoản thuộc về tổ chức nào và bắt đầu với vai gì, nhờ đó việc đăng ký vẫn thực hiện được ngay cả khi đăng ký tự phục vụ đang đóng.*

**Các mối quan hệ:**

- **Association (kết hợp):** Khách vãng lai – Đăng ký theo lời mời
- **Include (bao gồm):** UC103 Gửi mã xác thực
- **Extend (mở rộng):** UC101 Đăng ký tài khoản
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Khách mở liên kết lời mời nhận được qua thư điện tử. Liên kết mang theo mã mời dưới dạng một chuỗi ngẫu nhiên dài, không đoán được.
2. Hệ thống đọc mã mời và hiển thị ba thông tin lấy từ chính lời mời: tên tổ chức mời, địa chỉ thư được mời, và vai được đề nghị.
3. Khách nhập tên đăng nhập, mật khẩu và xác nhận mật khẩu. Trường địa chỉ thư đã điền sẵn theo lời mời và ở trạng thái chỉ đọc.
4. Khách chấp thuận các văn bản pháp lý đang hiệu lực (UC112) và bấm "Tham gia".
5. Hệ thống kiểm mã mời **trước khi** tạo bất kỳ bản ghi nào: mã tồn tại, chưa quá hạn, chưa bị thu hồi, chưa được dùng, và địa chỉ thư trong yêu cầu trùng khớp với địa chỉ ghi trong lời mời.
6. Hệ thống kiểm tên đăng nhập chưa bị dùng và mật khẩu đạt chính sách, giống bước 7–8 của UC101.
7. Hệ thống tạo tài khoản, gắn vào tổ chức đã mời với đúng vai ghi trong lời mời, đánh dấu lời mời là đã dùng kèm thời điểm và định danh tài khoản đã dùng nó, rồi ghi một mục vào nhật ký kiểm toán.
8. Hệ thống lưu các bản ghi đồng thuận, tạo phiên làm việc và chuyển khách tới bảng điều khiển của tổ chức mời.

**Luồng luân phiên:**

1. **Địa chỉ được mời đã có tài khoản:** ở bước 5, nếu địa chỉ thư trong lời mời đã thuộc về một tài khoản đang tồn tại, hệ thống không tạo tài khoản mới mà chuyển khách sang màn hình đăng nhập kèm ngữ cảnh lời mời. Sau khi đăng nhập, người dùng chấp nhận lời mời như một thao tác gắn thành viên (UC503).
2. **Đăng ký tự phục vụ vẫn đang mở:** khách nhận lời mời vẫn có thể bỏ qua liên kết và tự đăng ký theo UC101. Khi đó tài khoản được tạo ngoài tổ chức mời, và lời mời vẫn còn nguyên hiệu lực cho tới khi hết hạn — đó là lý do luồng luân phiên 1 tồn tại.

**Luồng ngoại lệ:**

1. **Lời mời không còn hiệu lực.** Ở bước 5, nếu mã mời đã quá hạn, đã bị quản trị tổ chức thu hồi, hoặc đã được dùng bởi một lần đăng ký trước đó, hệ thống từ chối và **không** tạo tài khoản nào. Thứ tự kiểm — kiểm mã mời trước khi ghi bản ghi tài khoản — chính là điều bảo đảm hệ thống không bao giờ để lại một tài khoản thật nằm sai tổ chức. Màn hình nêu rõ lý do từ chối là hết hạn hay đã dùng, vì hai lý do này dẫn tới hai hành động khác nhau: hết hạn thì xin quản trị tổ chức gửi lại lời mời mới (UC502), còn đã dùng nghĩa là tài khoản có thể đã tồn tại và khách nên thử đăng nhập hoặc khôi phục tài khoản (UC108).

2. **Địa chỉ thư trong yêu cầu khác địa chỉ được mời.** Ở bước 5, nếu yêu cầu gửi lên mang một địa chỉ khác với địa chỉ ghi trong lời mời — điều chỉ xảy ra khi có người sửa yêu cầu ở tầng dưới giao diện, vì trường này đã bị khoá — hệ thống từ chối với thông báo rằng lời mời này được gửi cho một địa chỉ khác, và không tạo tài khoản. Một lời mời gắn với đúng một địa chỉ; cho phép đổi địa chỉ ở bước cuối sẽ biến lời mời thành một tấm vé vào tổ chức chuyển nhượng được. Khách muốn dùng địa chỉ khác phải xin quản trị tổ chức thu hồi lời mời cũ và phát lời mời mới cho đúng địa chỉ đó.

3. **Trùng tên đăng nhập.** Ở bước 6, nếu tên đăng nhập đã bị dùng, hệ thống báo lỗi tại trường đó và giữ nguyên ngữ cảnh lời mời, kể cả mã mời — lời mời **không** bị tiêu vì lần gửi này không tạo ra tài khoản nào. Khách chọn tên khác và gửi lại. Đây là điểm khác biệt quan trọng so với việc tiêu mã mời quá sớm: nếu mã bị đánh dấu đã dùng ngay khi khách bấm nút, một lỗi trùng tên sẽ làm mất luôn lời mời và buộc quản trị tổ chức phải phát lại.

4. **Lời mời bị thu hồi trong lúc khách đang điền biểu mẫu.** Ở bước 5, nếu quản trị tổ chức thu hồi lời mời sau khi màn hình đã hiển thị ở bước 2 nhưng trước khi khách bấm "Tham gia", hệ thống từ chối tại thời điểm gửi chứ không phải tại thời điểm mở liên kết. Không có tài khoản nào được tạo. Đây là chủ ý: thẩm quyền quyết định nằm ở trạng thái của lời mời tại thời điểm ghi dữ liệu, không phải tại thời điểm khách nhìn thấy nó. Khách cần liên hệ lại với người đã mời mình.

**Kết quả mong đợi:** Tài khoản mới thuộc đúng tổ chức đã mời với đúng vai ghi trong lời mời, và lời mời chuyển sang trạng thái đã dùng, gắn với chính tài khoản vừa tạo nên không ai dùng lại được nó. Trường hợp lời mời không còn hiệu lực, hệ thống kết thúc mà không để lại tài khoản nào — trạng thái duy nhất không được phép xuất hiện là một tài khoản thật nằm sai tổ chức.

---

#### UC103 — Gửi mã xác thực

*Bảng C-4: Mô tả chức năng Gửi mã xác thực*

| **Tên use case** | Gửi mã xác thực | **ID** | UC103 |
|---|---|---|---|
| **Actor chính** | Người dùng đã đăng nhập | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Người dùng yêu cầu gửi mã | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 1 — Danh tính và quyền truy cập |

**Các thành phần tham gia và mối quan tâm:**

- **Người dùng** — nhận được mã trong thời gian ngắn, trên đúng kênh mình chọn.
- **Nền tảng** — không để đường gửi mã trở thành công cụ gửi thư rác hoặc công cụ dò địa chỉ.
- **Dịch vụ gửi tin (S1)** — nhận nội dung và kênh gửi.

**Mô tả tóm tắt:** *Hệ thống phát một mã dùng một lần tới một địa chỉ — thư điện tử hoặc số điện thoại — để người giữ địa chỉ đó chứng minh quyền kiểm soát nó. Use case này được dùng lại bởi xác thực địa chỉ liên hệ, khôi phục tài khoản và đường đăng ký theo lời mời.*

**Các mối quan hệ:**

- **Association (kết hợp):** Người dùng đã đăng nhập – Gửi mã xác thực; Dịch vụ gửi tin (S1)
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** gửi qua thư điện tử; gửi qua tin nhắn

**Xử lý sự kiện:**

1. Người dùng yêu cầu hệ thống gửi mã tới một địa chỉ, kèm mục đích của lần gửi — xác thực thư điện tử, xác thực số điện thoại, hoặc đặt lại mật khẩu.
2. Hệ thống chuẩn hoá địa chỉ đích: địa chỉ thư đưa về chữ thường và cắt khoảng trắng; số điện thoại đưa về dạng quốc tế đầy đủ, sau khi bỏ dấu cách, dấu gạch và dấu ngoặc. Số bắt đầu bằng chữ số 0 mà không có mã quốc gia bị từ chối chứ không được đoán mã quốc gia thay người dùng.
3. Hệ thống kiểm thời gian chờ tối thiểu giữa hai lần gửi cho cùng một tài khoản và cùng một mục đích, và kiểm hạn mức số lần gửi tính theo địa chỉ IP.
4. Hệ thống sinh một mã sáu chữ số bằng bộ sinh số ngẫu nhiên dùng cho mật mã, băm mã kèm mục đích và địa chỉ đích, rồi lưu bản băm cùng thời điểm hết hạn và số lần thử tối đa. Mã gốc không được lưu ở bất kỳ đâu.
5. Hệ thống **đóng mã đang sống trước đó** của cùng tài khoản và cùng mục đích, để tại mỗi thời điểm người dùng chỉ có đúng một mã còn hiệu lực, trên kênh họ vừa chọn.
6. Hệ thống chuyển mã cho dịch vụ gửi tin theo kênh đã chọn.
7. Hệ thống trả về cho màn hình: địa chỉ đích đã che bớt ký tự, thời hạn sống còn lại của mã, và số giây phải chờ trước khi được phép yêu cầu gửi lại — đủ để giao diện hiển thị đồng hồ đếm ngược.

**Luồng luân phiên:**

1. **Gửi lại mã:** người dùng bấm "Gửi lại" sau khi hết thời gian chờ. Hệ thống chạy lại từ bước 3; mã cũ bị đóng ở bước 5 nên mã trong thư đầu tiên không còn dùng được nữa. Đây là điểm người dùng hay nhầm: nếu họ nhận hai thư và nhập mã trong thư cũ, hệ thống sẽ từ chối.
2. **Đổi kênh gửi:** người dùng chuyển từ thư điện tử sang tin nhắn hoặc ngược lại. Thao tác này cũng chạy lại từ bước 3 và đóng mã của kênh trước đó, vì một người chỉ giữ một mã sống.

**Luồng ngoại lệ:**

1. **Chưa hết thời gian chờ giữa hai lần gửi.** Ở bước 3, nếu lần gửi trước cách đây chưa đủ khoảng chờ tối thiểu, hệ thống từ chối và trả về đúng số giây còn lại. Mã đã phát trước đó **vẫn còn hiệu lực** và người dùng nên tìm lại trong hộp thư thay vì yêu cầu mã mới. Khoảng chờ này bảo vệ hai phía: nó ngăn một người bấm liên tục làm hộp thư của chính họ đầy mã vô nghĩa, và ngăn kẻ khác dùng địa chỉ của nạn nhân làm đích cho một luồng thư rác. Sau khi hết khoảng chờ, người dùng bấm lại bình thường.

2. **Chạm trần số lần gửi theo địa chỉ IP.** Ở bước 3, nếu địa chỉ IP đã vượt hạn mức trong cửa sổ thời gian, hệ thống từ chối kèm thời gian chờ. Hạn mức này đếm số lần **yêu cầu gửi**, không đếm số lần gửi thành công, nên một kẻ dò địa chỉ không thể lách bằng cách nhắm vào các địa chỉ không tồn tại. Người dùng hợp lệ bị vạ lây — thường là nhiều người sau cùng một địa chỉ IP — phải chờ hết cửa sổ; nếu công việc gấp, đường thay thế là nhờ quản trị tổ chức xác thực hộ hoặc gửi phiếu hỗ trợ (UC801).

3. **Số điện thoại không đúng dạng.** Ở bước 2, nếu số điện thoại không ở dạng quốc tế hợp lệ, hệ thống từ chối kèm một ví dụ đúng dạng và không phát mã nào. Hệ thống cố tình không suy đoán mã quốc gia theo vị trí máy chủ, vì suy đoán sai sẽ gửi mã của người dùng Việt Nam tới một số máy ở nước khác. Người dùng nhập lại số ở dạng đầy đủ.

4. **Kênh tin nhắn chưa được cấu hình trên bản triển khai.** Ở bước 6, bản triển khai hiện tại không có nhà cung cấp tin nhắn, nên lựa chọn gửi qua tin nhắn bị ẩn khỏi giao diện; nếu yêu cầu vẫn được gửi lên, tầng gửi tin báo lỗi tường minh chứ không im lặng coi như đã gửi. Đây là chủ ý được ghi thẳng trong mã nguồn: một hệ thống xác thực mà tin nhắn âm thầm không tới nơi còn tệ hơn một hệ thống thừa nhận nó không gửi được. Người dùng chuyển sang kênh thư điện tử.

5. **Dịch vụ gửi tin từ chối hoặc hết thời gian chờ.** Ở bước 6, nếu nhà cung cấp thư trả lỗi, hệ thống báo cho người dùng rằng chưa gửi được. Bản ghi mã vẫn tồn tại trong cơ sở dữ liệu nhưng vô dụng vì không ai nhận được nó; nó sẽ hết hạn theo thời hạn sống bình thường và bị dọn sau đó. Người dùng chờ hết khoảng chờ tối thiểu rồi thử lại. Nếu lỗi lặp lại nhiều lần, đây là sự cố hạ tầng chứ không phải lỗi thao tác: kỹ sư vận hành phát hiện qua giám sát (UC704) và người dùng dùng đường hỗ trợ (UC801).

**Kết quả mong đợi:** Tồn tại đúng một mã còn sống cho cặp tài khoản – mục đích, chỉ ở dạng băm trong cơ sở dữ liệu, kèm thời hạn sống và ngân sách lần thử; mọi mã phát trước đó của cùng cặp đã bị đóng. Màn hình nhận đủ dữ liệu để đếm ngược: địa chỉ đích đã che bớt, thời hạn còn lại và thời gian chờ trước lần gửi kế tiếp. Khi bị hạn mức từ chối, không mã mới nào được phát và mã cũ giữ nguyên hiệu lực.

---

#### UC104 — Xác thực địa chỉ liên hệ

*Bảng C-5: Mô tả chức năng Xác thực địa chỉ liên hệ*

| **Tên use case** | Xác thực địa chỉ liên hệ | **ID** | UC104 |
|---|---|---|---|
| **Actor chính** | Người dùng đã đăng nhập | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Người dùng đã đăng nhập | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 1 — Danh tính và quyền truy cập |

**Các thành phần tham gia và mối quan tâm:**

- **Người dùng** — chứng minh được địa chỉ của mình để mở khoá các chức năng cần địa chỉ đã xác thực.
- **Nền tảng** — chỉ gửi thông báo quan trọng tới địa chỉ đã được chứng minh là có thật.
- **Quản trị tổ chức** — biết chắc thành viên trong tổ chức liên lạc được.

**Mô tả tóm tắt:** *Người dùng đã đăng nhập chứng minh quyền kiểm soát địa chỉ thư điện tử hoặc số điện thoại gắn với tài khoản, bằng cách nhập mã dùng một lần nhận được trên chính kênh đó.*

**Các mối quan hệ:**

- **Association (kết hợp):** Người dùng đã đăng nhập – Xác thực địa chỉ liên hệ
- **Include (bao gồm):** UC103 Gửi mã xác thực
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Người dùng mở trang Tài khoản. Hệ thống hiển thị từng địa chỉ đang lưu kèm trạng thái: đã xác thực vào lúc nào, hay chưa từng xác thực.
2. Người dùng chọn địa chỉ cần xác thực và bấm "Gửi mã" (UC103).
3. Hệ thống hiển thị ô nhập mã sáu chữ số, kèm địa chỉ đích đã che bớt ký tự và đồng hồ đếm ngược tới lúc mã hết hạn.
4. Người dùng nhập mã nhận được.
5. Hệ thống lấy mã đang sống của tài khoản theo đúng mục đích, kiểm mã chưa hết hạn, kiểm số lần thử chưa vượt trần, **tăng bộ đếm lần thử trước khi so sánh**, rồi băm mã người dùng nhập theo cùng cách và so với bản băm đã lưu.
6. Mã khớp: hệ thống đánh dấu bản ghi mã đã bị tiêu, ghi mốc thời gian xác thực lên tài khoản cho đúng địa chỉ đó, và làm mới phần hiển thị trạng thái.

**Luồng luân phiên:**

1. **Xác thực số điện thoại thay vì thư điện tử:** các bước như nhau, chỉ khác kênh gửi ở bước 2 và mục đích ghi trên bản ghi mã. Trên bản triển khai hiện tại kênh tin nhắn chưa có nhà cung cấp, nên nhánh này chỉ dùng được sau khi cấu hình nhà cung cấp (xem UC103, ngoại lệ 4).
2. **Xác thực ngay sau khi đăng ký:** mã đã được phát ở bước 11 của UC101, nên người dùng vào thẳng bước 4 mà không cần bấm "Gửi mã".

**Luồng ngoại lệ:**

1. **Mã sai.** Ở bước 5, hệ thống trả về một thông báo chung là mã không đúng hoặc đã hết hạn, và lần thử vừa rồi đã bị trừ khỏi ngân sách lần thử của chính mã đó. Hệ thống **cố tình không phân biệt** ba tình huống mã sai, mã hết hạn và mã chưa từng tồn tại: phân biệt chúng sẽ cho người đang giữ một địa chỉ đánh cắp biết được có hay không một lượt xác thực đang diễn ra. Người dùng nhập lại trong phạm vi ngân sách còn lại. Bộ đếm được tăng **trước** khi so sánh, nên nếu tiến trình chết giữa chừng thì hệ quả là mất một lượt thử chứ không bao giờ là được thêm một lượt thử.

2. **Nhập sai quá số lần cho phép.** Ở bước 5, khi số lần thử chạm trần, hệ thống đánh dấu mã đã bị tiêu ngay lập tức — kể cả lần thử cuối có đúng đi nữa cũng không còn dùng được — và trả về thông báo yêu cầu xin mã mới. Cách làm này giới hạn không gian đoán mã sáu chữ số xuống còn vài lần thử cho mỗi mã, nên độ dài mã không phải là thứ chống đoán, chính trần lần thử mới là. Người dùng bấm "Gửi mã" lần nữa sau khi hết khoảng chờ tối thiểu (UC103) và làm lại từ bước 3.

3. **Mã đã hết hạn.** Ở bước 5, mã quá thời hạn sống bị coi như không tồn tại và trả về cùng thông báo chung ở ngoại lệ 1. Bản ghi mã hết hạn không bị xoá ngay mà được tác vụ dọn định kỳ thu hồi về sau, nên số liệu về số lần phát mã vẫn còn để đối chiếu khi cần điều tra. Người dùng xin mã mới.

4. **Địa chỉ trên tài khoản đổi giữa chừng.** Ở bước 5, nếu người dùng đổi địa chỉ liên hệ ở tab khác sau khi mã đã được phát, mã cũ không còn dùng được vì bản băm của nó gắn với địa chỉ đích tại lúc phát. Hệ thống từ chối bằng thông báo chung. Đây là hệ quả có chủ ý của thiết kế: một mã chứng minh quyền kiểm soát **địa chỉ mà nó được gửi tới**, không phải quyền đối với tài khoản nói chung. Người dùng xin mã mới cho địa chỉ mới.

**Kết quả mong đợi:** Địa chỉ liên hệ mang một mốc thời gian xác thực trên bản ghi tài khoản, mã vừa dùng đã bị tiêu và không dùng lại được. Khi mã sai hoặc hết hạn, ngân sách lần thử của mã giảm đúng một đơn vị và trạng thái xác thực của tài khoản không đổi; hết ngân sách thì mã bị vô hiệu ngay lập tức.

---

#### UC106 — Xác thực yếu tố thứ hai

*Bảng C-6: Mô tả chức năng Xác thực yếu tố thứ hai*

| **Tên use case** | Xác thực yếu tố thứ hai | **ID** | UC106 |
|---|---|---|---|
| **Actor chính** | Người dùng đã đăng nhập | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Tài khoản đã bật xác thực hai yếu tố | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 1 — Danh tính và quyền truy cập |

**Các thành phần tham gia và mối quan tâm:**

- **Chủ tài khoản** — mật khẩu bị lộ vẫn chưa đủ để người khác vào được tài khoản.
- **Quản trị nền tảng** — các tài khoản có quyền cao được bảo vệ bằng hai lớp.
- **Nền tảng** — mã đã dùng không dùng lại được trong chính cửa sổ thời gian của nó.

**Mô tả tóm tắt:** *Người dùng hoàn tất việc đăng nhập bằng cách nhập mã sáu chữ số do ứng dụng xác thực sinh ra, hoặc bằng một mã khôi phục đã được cấp trước đó.*

**Các mối quan hệ:**

- **Association (kết hợp):** Người dùng đã đăng nhập – Xác thực yếu tố thứ hai
- **Include (bao gồm):** không
- **Extend (mở rộng):** UC105 Đăng nhập
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Sau khi mật khẩu được chấp nhận ở UC105, hệ thống nhận ra tài khoản có bật xác thực hai yếu tố nên **chưa** cấp phiên làm việc, mà cấp một vé trung gian có thời hạn ngắn, chỉ dùng được cho đúng bước xác thực này.
2. Hệ thống hiển thị màn hình nhập mã sáu chữ số từ ứng dụng xác thực, kèm đường dẫn phụ "Dùng mã khôi phục".
3. Người dùng mở ứng dụng xác thực và nhập mã đang hiển thị.
4. Hệ thống giải mã bí mật của tài khoản, tính mã đúng cho khoảng thời gian hiện tại cùng một khoảng liền trước và liền sau để bù lệch đồng hồ, rồi so với mã người dùng nhập bằng phép so sánh không phụ thuộc thời gian.
5. Mã khớp: hệ thống ghi nhận khoảng thời gian vừa dùng để chính mã đó không dùng lại được lần nữa trong cửa sổ của nó.
6. Hệ thống cấp phiên làm việc đầy đủ, xoá vé trung gian, ghi một mục vào nhật ký kiểm toán và hoàn tất lượt đăng nhập đã bắt đầu ở UC105.

**Luồng luân phiên:**

1. **Dùng mã khôi phục thay cho ứng dụng xác thực:** ở bước 3, người dùng bấm "Dùng mã khôi phục" và nhập một mã trong bộ mã đã lưu khi bật tính năng. Hệ thống đối chiếu với các bản băm đã lưu, tiêu vĩnh viễn mã vừa dùng, rồi đi tiếp bước 6 và hiển thị số mã khôi phục còn lại. Khi số còn lại xuống thấp, hệ thống nhắc người dùng cấp lại bộ mã mới (UC109).

**Luồng ngoại lệ:**

1. **Mã sai hoặc đã quá cửa sổ thời gian.** Ở bước 4, hệ thống báo mã không đúng và giữ nguyên vé trung gian để người dùng thử lại. Nguyên nhân thường gặp nhất không phải là kẻ tấn công mà là đồng hồ điện thoại lệch giờ, nên thông báo lỗi nhắc thẳng người dùng kiểm tra đồng hồ trên thiết bị. Số lần thử bị giới hạn; khi hết lượt, vé trung gian bị huỷ và người dùng phải nhập lại mật khẩu từ đầu (UC105). Các lần thử sai này cũng tính vào ngân sách chống dò của cặp tài khoản – địa chỉ IP, nên việc dò mã hai yếu tố cũng bị chặn dần như việc dò mật khẩu.

2. **Vé trung gian hết hạn.** Ở bước 4, nếu người dùng để màn hình nhập mã quá lâu, vé trung gian hết hiệu lực và hệ thống từ chối kèm thông báo phiên xác thực đã hết hạn, mời đăng nhập lại. Không có phiên nào được cấp và không có trạng thái dở dang nào để lại. Thời hạn ngắn của vé là chủ ý: một vé đã qua bước mật khẩu mà sống lâu chính là một nửa tài khoản để ngỏ trên máy dùng chung.

3. **Mất thiết bị sinh mã và hết mã khôi phục.** Ở bước 3, nếu người dùng vừa không mở được ứng dụng xác thực vừa dùng hết mười mã khôi phục, họ không còn đường tự phục vụ nào để vào tài khoản. Đường khôi phục tài khoản (UC108) cũng yêu cầu yếu tố thứ hai nên không gỡ được tình huống này. Cách xử lý duy nhất là gửi phiếu hỗ trợ (UC801) để quản trị nền tảng tắt xác thực hai yếu tố cho tài khoản sau khi xác minh danh tính bằng đường ngoài hệ thống; thao tác đó của quản trị viên được ghi vào nhật ký kiểm toán (UC602). Hệ thống chọn không tự động mở khoá vì bất kỳ cơ chế tự động nào ở đây cũng chính là một đường vòng qua chính lớp bảo vệ vừa dựng.

4. **Không giải mã được bí mật của tài khoản.** Ở bước 4, nếu khoá mã hoá dùng để bảo vệ bí mật sinh mã bị đổi hoặc thiếu trong cấu hình, hệ thống không xác định được thiết lập bảo mật của tài khoản và từ chối lượt đăng nhập bằng lỗi máy chủ thay vì bỏ qua bước xác thực hai yếu tố. Đây là điểm quan trọng của thiết kế: khi không đọc được trạng thái bảo mật, hệ thống **đóng** chứ không **mở**. Kỹ sư vận hành khôi phục cấu hình khoá; người dùng không có thao tác nào để tự xử lý ngoài việc thử lại sau.

**Kết quả mong đợi:** Lượt đăng nhập hoàn tất bằng một phiên làm việc đầy đủ, vé trung gian đã bị xoá, và khoảng thời gian của mã vừa dùng được ghi nhận nên chính mã đó không dùng lại được. Nếu dùng mã khôi phục, mã đó bị tiêu vĩnh viễn và số mã còn lại được thông báo cho người dùng. Khi không xác định được thiết lập bảo mật của tài khoản, hệ thống từ chối cấp phiên thay vì bỏ qua lớp bảo vệ thứ hai.

---

#### UC107 — Đăng xuất

*Bảng C-7: Mô tả chức năng Đăng xuất*

| **Tên use case** | Đăng xuất | **ID** | UC107 |
|---|---|---|---|
| **Actor chính** | Người dùng đã đăng nhập | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Người dùng đã đăng nhập | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 1 — Danh tính và quyền truy cập |

**Các thành phần tham gia và mối quan tâm:**

- **Người dùng** — rời khỏi hệ thống là mất quyền ngay lập tức, kể cả trên máy dùng chung.
- **Nền tảng** — token đã phát không còn hiệu lực trước thời hạn tự nhiên của nó.

**Mô tả tóm tắt:** *Người dùng kết thúc phiên làm việc hiện tại. Token làm mới bị thu hồi và token truy cập được đưa vào danh sách từ chối, để nó mất hiệu lực ngay chứ không phải đợi tới lúc hết hạn tự nhiên.*

**Các mối quan hệ:**

- **Association (kết hợp):** Người dùng đã đăng nhập – Đăng xuất
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Người dùng bấm "Đăng xuất" trên thanh điều hướng.
2. Hệ thống xác định phiên hiện tại từ cookie token làm mới, thu hồi token đó và đánh dấu bản ghi phiên là đã đóng kèm thời điểm và lý do đóng.
3. Hệ thống đưa token truy cập đang cầm vào danh sách từ chối, với thời gian sống của mục từ chối đúng bằng phần thời hạn còn lại của token. Nhờ đó token mất hiệu lực ngay, thay vì còn dùng được cho tới khi hết hạn tự nhiên.
4. Hệ thống xoá cookie token truy cập và cookie token làm mới, đặt đúng đường dẫn gốc mà bản triển khai đang phục vụ để trình duyệt thật sự xoá được chúng.
5. Hệ thống ghi một mục vào nhật ký kiểm toán và chuyển người dùng về màn hình đăng nhập, giữ nguyên tiền tố đường dẫn của bản triển khai.

**Luồng luân phiên:**

1. **Đăng xuất khỏi mọi thiết bị:** ở bước 1, nếu người dùng chọn phương án này từ trang Bảo mật, hệ thống thu hồi toàn bộ phiên của tài khoản chứ không riêng phiên hiện tại, và đưa mọi token truy cập còn hạn của tài khoản vào danh sách từ chối. Đây là thao tác nên dùng sau khi mất thiết bị hoặc nghi ngờ mật khẩu bị lộ.
2. **Đăng xuất tự động do quá hạn không hoạt động:** nếu phiên không được làm mới trong khoảng thời gian tối đa cho phép, phía máy chủ coi phiên đã chết; lần gọi kế tiếp bị từ chối và giao diện đưa người dùng về màn hình đăng nhập. Đường này không do người dùng kích hoạt nhưng để lại cùng một trạng thái cuối.

**Luồng ngoại lệ:**

1. **Phiên đã bị thu hồi từ nơi khác.** Ở bước 2, nếu phiên đã bị đóng trước đó — do quản trị viên thu hồi, do đăng xuất khỏi mọi thiết bị ở một trình duyệt khác, hoặc do đã quá hạn — hệ thống vẫn xoá cookie phía trình duyệt và báo đăng xuất thành công. Không báo lỗi cho người dùng là chủ ý: mục tiêu của thao tác này là "sau khi bấm xong thì không còn quyền", và mục tiêu đó đã đạt. Báo lỗi ở đây chỉ khiến người dùng tưởng mình vẫn còn đăng nhập.

2. **Mất kết nối trong lúc gửi yêu cầu đăng xuất.** Ở bước 2, nếu yêu cầu không tới được máy chủ, giao diện vẫn xoá trạng thái phía trình duyệt và chuyển về màn hình đăng nhập, nhưng phiên phía máy chủ **chưa** bị thu hồi và token làm mới vẫn còn hiệu lực cho tới khi hết hạn. Đây là một khoảng rủi ro thật cần nói rõ trong tài liệu vận hành: trên máy dùng chung, người dùng cần bấm đăng xuất khi mạng còn hoạt động, và nếu nghi ngờ thì dùng "Đăng xuất khỏi mọi thiết bị" ở lần đăng nhập kế tiếp để dọn sạch các phiên còn treo.

3. **Token làm mới đã bị xoay lại ở một tab khác.** Ở bước 2, khi người dùng mở nhiều tab, tab này có thể cầm một token đã bị tab kia xoay đi. Hệ thống nhận ra token thuộc cùng một họ token của phiên và vẫn đóng đúng phiên đó, thay vì báo lỗi hoặc coi đây là dấu hiệu token bị đánh cắp. Cơ chế ân hạn ngắn sau mỗi lần xoay tồn tại chính vì tình huống nhiều tab này.

**Kết quả mong đợi:** Phiên hiện tại đã đóng ở phía máy chủ, token làm mới bị thu hồi, token truy cập nằm trong danh sách từ chối cho tới khi hết hạn tự nhiên, và cookie phía trình duyệt đã bị xoá. Người dùng ở màn hình đăng nhập dưới đúng đường dẫn gốc của bản triển khai, và nhật ký kiểm toán ghi lần đăng xuất.

---

#### UC108 — Khôi phục tài khoản

*Bảng C-8: Mô tả chức năng Khôi phục tài khoản*

| **Tên use case** | Khôi phục tài khoản | **ID** | UC108 |
|---|---|---|---|
| **Actor chính** | Khách vãng lai | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Khách vãng lai | **Phân loại** | Phức tạp |
| **Loại** | external | **Nghiệp vụ** | 1 — Danh tính và quyền truy cập |

**Các thành phần tham gia và mối quan tâm:**

- **Chủ tài khoản** — lấy lại quyền truy cập mà không phải nhờ tới quản trị viên.
- **Nền tảng** — đường khôi phục không trở thành đường chiếm tài khoản, và không dùng để dò xem địa chỉ nào đã đăng ký.
- **Dịch vụ gửi tin (S1)** — chuyển mã và thư thông báo đổi mật khẩu.

**Mô tả tóm tắt:** *Khách vãng lai không đăng nhập được sẽ lấy lại quyền truy cập qua một cửa duy nhất: xác định tài khoản, chứng minh quyền kiểm soát địa chỉ đang lưu bằng mã dùng một lần, rồi đặt mật khẩu mới.*

**Các mối quan hệ:**

- **Association (kết hợp):** Khách vãng lai – Khôi phục tài khoản; Dịch vụ gửi tin (S1)
- **Include (bao gồm):** UC103 Gửi mã xác thực
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Khách mở màn hình "Quên mật khẩu", nhập địa chỉ thư điện tử hoặc tên đăng nhập của tài khoản và bấm "Tiếp tục".
2. Hệ thống tra tài khoản, phát một mã dùng một lần với mục đích đặt lại mật khẩu và gửi tới địa chỉ đang lưu của tài khoản (UC103). Địa chỉ đích **không** lấy theo dữ liệu khách nhập mà lấy theo dữ liệu đang lưu trên tài khoản.
3. Hệ thống hiển thị màn hình nhập mã, kèm địa chỉ đích đã che bớt ký tự và đồng hồ đếm ngược.
4. Khách nhập mã. Hệ thống kiểm mã như ở UC104 bước 5, tiêu mã ngay khi khớp, và cấp một giấy phép đặt lại mật khẩu có thời hạn ngắn.
5. Hệ thống hiển thị biểu mẫu nhập mật khẩu mới và ô xác nhận lại.
6. Khách nhập mật khẩu mới hai lần và bấm "Đặt lại".
7. Hệ thống kiểm giấy phép còn hiệu lực, kiểm mật khẩu đạt chính sách, băm và lưu mật khẩu mới.
8. Hệ thống thu hồi **toàn bộ** phiên đang mở của tài khoản, ghi một mục vào nhật ký kiểm toán và gửi một thư báo tới địa chỉ của tài khoản, cho biết mật khẩu vừa bị đổi và thời điểm đổi.
9. Hệ thống chuyển khách về màn hình đăng nhập để đăng nhập lại bằng mật khẩu mới.

**Luồng luân phiên:**

1. **Tài khoản có bật xác thực hai yếu tố:** ở bước 4, sau khi mã dùng một lần được chấp nhận, hệ thống yêu cầu thêm mã từ ứng dụng xác thực hoặc một mã khôi phục trước khi cấp giấy phép đặt lại. Một địa chỉ thư bị chiếm không được phép vượt qua lớp bảo vệ thứ hai.
2. **Đổi mật khẩu khi vẫn đăng nhập được:** người dùng còn nhớ mật khẩu cũ thì dùng chức năng đổi mật khẩu ở trang Bảo mật, đường này yêu cầu nhập mật khẩu hiện tại và không đi qua kênh thư điện tử.

**Luồng ngoại lệ:**

1. **Tài khoản không tồn tại.** Ở bước 2, nếu không tra được tài khoản nào theo dữ liệu khách nhập, hệ thống vẫn trả về đúng thông báo như trường hợp thành công — rằng nếu địa chỉ tồn tại thì mã đã được gửi — và vẫn hiển thị màn hình nhập mã ở bước 3. Không có thư nào được gửi và không có mã nào được phát. Nhờ vậy biểu mẫu này không dùng được để kiểm tra xem một địa chỉ đã đăng ký hay chưa. Khách nhập nhầm địa chỉ sẽ chờ mã không bao giờ tới; họ cần thử lại với địa chỉ khác hoặc liên hệ hỗ trợ (UC801).

2. **Nhập sai mã.** Ở bước 4, hệ thống trả về thông báo chung như ở UC104 và trừ một lượt trong ngân sách lần thử của mã. Điểm cần lưu ý về thiết kế: bước xác minh mã và bước xác nhận mật khẩu mới dùng **chung một ngân sách tần suất**, nên việc kiên trì đoán mã tiêu đúng ngân sách như việc bắt đầu lại quy trình từ đầu, và kẻ tấn công không có đường nào rẻ hơn. Hết lượt thử thì mã bị tiêu và khách phải bắt đầu lại từ bước 1.

3. **Giấy phép đặt lại mật khẩu hết hạn.** Ở bước 7, nếu khách để màn hình nhập mật khẩu mới quá lâu, hệ thống từ chối lưu mật khẩu và yêu cầu làm lại từ bước 1. Mật khẩu cũ vẫn còn nguyên hiệu lực, các phiên đang mở không bị đụng tới. Thời hạn ngắn của giấy phép là chủ ý: nó là một tấm vé đổi mật khẩu, và một tấm vé như vậy nằm lâu trên máy dùng chung là một tài khoản để ngỏ.

4. **Mật khẩu mới không đạt chính sách.** Ở bước 7, hệ thống liệt kê các yêu cầu chưa đạt và giữ nguyên giấy phép để khách nhập lại, miễn là giấy phép còn hạn. Trạng thái tài khoản không đổi.

5. **Không gửi được thư báo đã đổi mật khẩu.** Ở bước 8, nếu dịch vụ gửi tin hỏng, mật khẩu **vẫn đã đổi** và các phiên vẫn đã bị thu hồi; hệ thống ghi lỗi gửi thư vào nhật ký kỹ thuật và không hoàn tác thao tác đổi mật khẩu. Hệ quả cần chấp nhận là chủ tài khoản không nhận được cảnh báo — đây chính là lý do mục kiểm toán ở bước 8 phải luôn được ghi, để một lượt đổi mật khẩu đáng ngờ vẫn truy được về sau (UC604).

**Kết quả mong đợi:** Tài khoản mang mã băm của mật khẩu mới, toàn bộ phiên đang mở đã bị thu hồi, một thư báo đã được gửi tới địa chỉ của tài khoản, và nhật ký kiểm toán ghi lần đặt lại. Với một địa chỉ không tồn tại, kết quả nhìn từ bên ngoài giống hệt trường hợp thành công nhưng không mã nào được phát và không thư nào được gửi.

---

#### UC109 — Quản lý xác thực hai yếu tố

*Bảng C-9: Mô tả chức năng Quản lý xác thực hai yếu tố*

| **Tên use case** | Quản lý xác thực hai yếu tố | **ID** | UC109 |
|---|---|---|---|
| **Actor chính** | Người dùng đã đăng nhập | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Người dùng đã đăng nhập | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 1 — Danh tính và quyền truy cập |

**Các thành phần tham gia và mối quan tâm:**

- **Chủ tài khoản** — bật được lớp bảo vệ thứ hai và vẫn có đường vào khi mất thiết bị.
- **Nền tảng** — bí mật sinh mã không bao giờ hiển thị lại sau lần đầu; mọi thao tác tắt hoặc cấp lại đều đòi mật khẩu.

**Mô tả tóm tắt:** *Người dùng bật, xác nhận hoặc tắt cơ chế xác thực hai yếu tố dựa trên mã một lần theo thời gian cho tài khoản của mình, và cấp lại bộ mã khôi phục khi cần.*

**Các mối quan hệ:**

- **Association (kết hợp):** Người dùng đã đăng nhập – Quản lý xác thực hai yếu tố
- **Include (bao gồm):** không
- **Extend (mở rộng):** UC110 Quản lý hồ sơ cá nhân
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Người dùng mở trang Bảo mật. Hệ thống hiển thị trạng thái bật hoặc tắt, thời điểm bật, và số mã khôi phục chưa dùng còn lại.
2. Người dùng bấm "Bật". Hệ thống sinh một bí mật ngẫu nhiên, lưu ở trạng thái chờ xác nhận dưới dạng đã mã hoá, và hiển thị bí mật đó cho người dùng dưới hai hình thức: một mã vạch hai chiều để quét, và một chuỗi ký tự để nhập tay khi không quét được.
3. Người dùng quét mã vạch bằng ứng dụng xác thực trên điện thoại. Ứng dụng ghi tài khoản dưới tên nhà phát hành của nền tảng kèm nhãn tài khoản, để người dùng phân biệt được với các mục khác trong ứng dụng.
4. Người dùng nhập mã sáu chữ số mà ứng dụng đang hiển thị.
5. Hệ thống kiểm mã theo bí mật đang chờ. Mã khớp: hệ thống chuyển bí mật sang trạng thái đã kích hoạt, sinh mười mã khôi phục, lưu bản băm của từng mã, và hiển thị toàn bộ mười mã cho người dùng **đúng một lần**.
6. Người dùng lưu bộ mã khôi phục ra nơi an toàn và xác nhận đã lưu. Hệ thống ghi một mục vào nhật ký kiểm toán và đóng màn hình.

**Luồng luân phiên:**

1. **Tắt xác thực hai yếu tố:** người dùng bấm "Tắt" và phải nhập lại mật khẩu tài khoản. Hệ thống kiểm mật khẩu, xoá bí mật cùng toàn bộ mã khôi phục còn lại, ghi một mục vào nhật ký kiểm toán, và từ lần đăng nhập sau tài khoản chỉ còn một lớp bảo vệ.
2. **Cấp lại bộ mã khôi phục:** người dùng nhập lại mật khẩu tài khoản; hệ thống vô hiệu toàn bộ mã cũ — kể cả các mã chưa dùng — rồi sinh và hiển thị bộ mười mã mới đúng một lần. Đường này dùng khi người dùng làm mất giấy ghi mã, hoặc khi số mã còn lại đã xuống thấp.
3. **Nhập tay chuỗi bí mật:** ở bước 3, nếu điện thoại không quét được mã vạch, người dùng nhập chuỗi ký tự vào ứng dụng xác thực. Các bước còn lại không đổi.

**Luồng ngoại lệ:**

1. **Mã xác nhận sai khi đang bật.** Ở bước 5, hệ thống báo mã không đúng và nhắc người dùng kiểm tra đồng hồ trên điện thoại, vì lệch giờ là nguyên nhân phổ biến hơn nhiều so với quét nhầm. Bí mật vẫn nằm ở trạng thái chờ và xác thực hai yếu tố **chưa** được bật, nên tài khoản không rơi vào trạng thái nửa vời khoá mất chính chủ. Người dùng nhập lại mã mới trong khoảng thời gian kế tiếp; nếu vẫn không được, họ bắt đầu lại từ bước 2 để lấy một bí mật mới.

2. **Bật lại khi đang bật.** Ở bước 2, nếu tài khoản đã bật xác thực hai yếu tố, hệ thống từ chối việc đăng ký một bí mật mới và yêu cầu tắt trước rồi bật lại. Thiết kế này ngăn tình huống hai bí mật cùng tồn tại mà người dùng không biết bí mật nào đang có hiệu lực — tình huống dẫn thẳng tới việc mất quyền vào tài khoản.

3. **Xác nhận khi chưa bắt đầu đăng ký.** Ở bước 4, nếu yêu cầu xác nhận được gửi lên mà không có bí mật chờ nào — thường do người dùng để màn hình mở quá lâu rồi làm mới trang, hoặc do gọi trực tiếp vào giao diện lập trình — hệ thống từ chối với thông báo chưa bắt đầu đăng ký. Người dùng bắt đầu lại từ bước 2.

4. **Mật khẩu sai ở nhánh tắt hoặc nhánh cấp lại mã.** Hệ thống từ chối thao tác và giữ nguyên mọi trạng thái: xác thực hai yếu tố vẫn bật, bộ mã khôi phục cũ vẫn còn hiệu lực. Yêu cầu nhập mật khẩu ở hai nhánh này là chủ ý, vì cả hai đều là thao tác hạ thấp mức bảo vệ của tài khoản, và một phiên bị chiếm không được phép làm điều đó chỉ bằng vài cú bấm. Lần nhập sai cũng tính vào ngân sách chống dò của tài khoản.

5. **Người dùng đóng màn hình trước khi lưu mã khôi phục.** Ở bước 6, nếu người dùng rời khỏi trang mà chưa lưu bộ mã, hệ thống **không** hiển thị lại bộ mã đó lần nào nữa, vì chỉ bản băm được lưu. Xác thực hai yếu tố vẫn đang bật và vẫn dùng bình thường bằng ứng dụng xác thực. Người dùng phải vào lại trang Bảo mật và cấp lại bộ mã mới theo luồng luân phiên 2. Đây là đánh đổi có chủ ý: lưu mã khôi phục ở dạng đọc lại được sẽ biến chính chúng thành một bản sao mật khẩu nằm trong cơ sở dữ liệu.

**Kết quả mong đợi:** Tài khoản có xác thực hai yếu tố ở đúng trạng thái người dùng chọn: khi bật, bí mật đã kích hoạt ở dạng mã hoá và mười mã khôi phục đã được hiển thị đúng một lần rồi chỉ còn lưu dưới dạng băm; khi tắt, cả bí mật lẫn mã khôi phục đã bị xoá. Mọi lần bật, tắt hay cấp lại đều có một mục kiểm toán, và một lần xác nhận thất bại luôn để lại trạng thái cũ nguyên vẹn.

---

#### UC110 — Quản lý hồ sơ cá nhân

*Bảng C-10: Mô tả chức năng Quản lý hồ sơ cá nhân*

| **Tên use case** | Quản lý hồ sơ cá nhân | **ID** | UC110 |
|---|---|---|---|
| **Actor chính** | Người dùng đã đăng nhập | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Người dùng đã đăng nhập | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 1 — Danh tính và quyền truy cập |

**Các thành phần tham gia và mối quan tâm:**

- **Người dùng** — sửa được thông tin của mình mà không phải nhờ quản trị viên.
- **Nền tảng** — tên đăng nhập đã được chép sang nhiều nơi phải được cập nhật đồng bộ.
- **Bộ phận kiểm toán** — nhãn tác nhân đã ghi trong nhật ký là bằng chứng lịch sử, không được viết lại.

**Mô tả tóm tắt:** *Người dùng xem và cập nhật thông tin tài khoản của chính mình: tên hiển thị, tên đăng nhập, địa chỉ liên hệ, ngôn ngữ giao diện và các trường hồ sơ người ký.*

**Các mối quan hệ:**

- **Association (kết hợp):** Người dùng đã đăng nhập – Quản lý hồ sơ cá nhân
- **Include (bao gồm):** không
- **Extend (mở rộng):** không *(UC109 mở rộng use case này)*
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Người dùng mở trang Tài khoản. Hệ thống hiển thị bốn nhóm thông tin: hồ sơ cơ bản gồm tên hiển thị, tên đăng nhập, ngôn ngữ giao diện; địa chỉ liên hệ kèm trạng thái đã xác thực hay chưa; hồ sơ người ký gồm các trường mô tả đặc điểm ký hiệu; và lịch sử đồng thuận.
2. Người dùng sửa các trường cần đổi và bấm "Lưu".
3. Hệ thống kiểm tính hợp lệ của từng giá trị mới theo kiểu dữ liệu và độ dài, và kiểm tên đăng nhập hoặc địa chỉ liên hệ mới chưa thuộc về tài khoản khác.
4. Hệ thống lưu thay đổi vào bản ghi tài khoản.
5. Nếu tên đăng nhập bị đổi, hệ thống lan giá trị mới sang mọi nơi đã sao chép nó, bao gồm cả tệp danh bạ mẫu — tên đăng nhập được nhân bản ra nhiều chỗ vì lý do hiệu năng, nên đổi ở một chỗ mà quên các chỗ còn lại sẽ tạo ra hai người từ một người.
6. Hệ thống ghi một mục vào nhật ký kiểm toán và hiển thị hồ sơ đã cập nhật.

**Luồng luân phiên:**

1. **Đổi ngôn ngữ giao diện:** thay đổi có hiệu lực ngay trên trình duyệt hiện tại và được lưu vào hồ sơ, nên các lần đăng nhập sau trên thiết bị khác cũng dùng ngôn ngữ đó.
2. **Cập nhật hồ sơ người ký:** các trường mô tả người ký chỉ ảnh hưởng tới siêu dữ liệu của mẫu thu về sau; các mẫu đã thu giữ nguyên giá trị tại thời điểm thu, vì chúng mô tả điều kiện của lần thu chứ không mô tả người ở hiện tại.

**Luồng ngoại lệ:**

1. **Tên đăng nhập đã có người dùng.** Ở bước 3, hệ thống từ chối và giữ nguyên tên cũ; không có thay đổi bộ phận nào được lưu, kể cả các trường khác trong cùng lần gửi. Người dùng chọn tên khác. Việc kiểm trùng ở đây bắt buộc phải chặt vì tên đăng nhập vừa là định danh đăng nhập vừa là nhãn hiển thị trong nhiều bảng dữ liệu.

2. **Đổi địa chỉ liên hệ.** Ở bước 4, khi địa chỉ thư hoặc số điện thoại bị đổi, hệ thống xoá mốc xác thực của địa chỉ đó — địa chỉ mới trở lại trạng thái chưa được chứng minh — và yêu cầu người dùng xác thực lại (UC104). Ngoài ra thao tác đổi địa chỉ thư đòi nhập mật khẩu hiện tại, và nếu tài khoản có bật xác thực hai yếu tố thì đòi thêm mã của yếu tố thứ hai. Lý do là địa chỉ thư chính là đích của đường khôi phục tài khoản: ai đổi được địa chỉ này thì thực chất đã chiếm được tài khoản, nên nó phải được bảo vệ ngang với mật khẩu.

3. **Địa chỉ mới trùng địa chỉ đang dùng hoặc đã thuộc tài khoản khác.** Ở bước 3, hệ thống từ chối và nêu rõ trường hợp nào trong hai trường hợp đó, vì hai trường hợp này dẫn tới hai hành động khác nhau: trùng chính địa chỉ đang dùng là thao tác thừa, còn trùng địa chỉ của người khác nghĩa là người dùng cần chọn địa chỉ khác hoặc kiểm tra lại xem mình có hai tài khoản không.

4. **Lan tên đăng nhập mới thất bại một phần.** Ở bước 5, nếu việc cập nhật một trong các nơi sao chép không hoàn tất — chẳng hạn tệp danh bạ mẫu đang bị khoá bởi một tiến trình khác — hệ thống báo lỗi nêu rõ phần nào chưa cập nhật thay vì báo thành công. Bản ghi tài khoản đã mang tên mới, nên hệ thống ở trạng thái lệch cho tới khi phần còn lại được đồng bộ; kỹ sư vận hành xử lý bằng tác vụ đồng bộ kho lưu trữ và cơ sở dữ liệu (UC703).

5. **Nhãn tác nhân trong nhật ký kiểm toán không đổi theo.** Ở bước 5, các mục kiểm toán đã ghi trước đó vẫn giữ tên đăng nhập cũ. Đây **không** phải lỗi đồng bộ mà là yêu cầu: nhật ký kiểm toán ghi lại ai đã hành động dưới tên nào tại thời điểm nào, nên viết lại nhãn cũ theo tên mới sẽ phá huỷ chính giá trị làm bằng chứng của nhật ký. Người đọc nhật ký đối chiếu qua định danh tài khoản, trường không bao giờ đổi.

**Kết quả mong đợi:** Hồ sơ tài khoản mang các giá trị mới đã qua kiểm tính hợp lệ, và tên đăng nhập mới đã lan tới mọi nơi từng sao chép nó, kể cả danh bạ mẫu. Địa chỉ liên hệ vừa đổi trở lại trạng thái chưa xác thực, còn nhãn tác nhân trong các mục kiểm toán cũ giữ nguyên giá trị lịch sử của chúng.

---

#### UC111 — Xem văn bản pháp lý

*Bảng C-11: Mô tả chức năng Xem văn bản pháp lý*

| **Tên use case** | Xem văn bản pháp lý | **ID** | UC111 |
|---|---|---|---|
| **Actor chính** | Khách vãng lai | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Khách vãng lai | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 1 — Danh tính và quyền truy cập |

**Các thành phần tham gia và mối quan tâm:**

- **Khách vãng lai và người dùng** — đọc được điều khoản trước khi quyết định tham gia.
- **Bộ phận pháp chế** — bản đang hiệu lực là bản duy nhất công chúng đọc được.
- **Người ký đóng góp dữ liệu** — hiểu rõ mức phát hành mà mình sắp đồng ý.

**Mô tả tóm tắt:** *Bất kỳ ai, đã đăng nhập hay chưa, đều đọc được các văn bản pháp lý mà nền tảng đã công bố: điều khoản sử dụng, chính sách quyền riêng tư và văn bản đồng thuận thu thập dữ liệu. Việc đọc là công khai; việc chấp thuận thì không.*

**Các mối quan hệ:**

- **Association (kết hợp):** Khách vãng lai – Xem văn bản pháp lý
- **Include (bao gồm):** không
- **Extend (mở rộng):** không *(UC112 dùng lại use case này qua quan hệ «include»)*
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Khách mở mục văn bản pháp lý. Hệ thống liệt kê các văn bản **đang hiệu lực**, mỗi văn bản kèm loại, số phiên bản, ngày hiệu lực và ngôn ngữ.
2. Khách chọn một văn bản.
3. Hệ thống đọc nội dung của phiên bản đang hiệu lực từ cơ sở dữ liệu và kết xuất để đọc trên trình duyệt, giữ nguyên cấu trúc điều khoản và đánh số mục.
4. Hệ thống hiển thị kèm mã băm nội dung và ngày hiệu lực ở chân trang, để người đọc đối chiếu được với bản mà mình đã chấp thuận trong lịch sử đồng thuận.
5. Khách có thể chọn tải tệp văn bản thay vì đọc trên màn hình.
6. Hệ thống trả tệp đính kèm đúng phiên bản đang hiển thị.

**Luồng luân phiên:**

1. **Đọc từ trong luồng chấp thuận:** khi được mở từ màn hình chấp thuận (UC112), văn bản hiển thị trong cùng trang thay vì mở trang riêng, và ô đánh dấu chấp thuận chỉ mở khoá sau khi người dùng cuộn hết nội dung.
2. **Đọc bản dịch:** nếu văn bản có nhiều phiên bản ngôn ngữ cùng hiệu lực, hệ thống hiển thị bản theo ngôn ngữ giao diện và cho phép chuyển sang ngôn ngữ khác; mã băm nội dung ở bước 4 đổi theo bản ngôn ngữ đang đọc, vì mỗi bản là một văn bản riêng.

**Luồng ngoại lệ:**

1. **Loại văn bản chưa có phiên bản nào được công bố.** Ở bước 3, nếu loại văn bản được yêu cầu chưa từng công bố, hệ thống trả về trạng thái không tìm thấy kèm thông báo rõ ràng, thay vì hiển thị một trang trống khiến người đọc tưởng nền tảng không có điều khoản. Trong trạng thái này, cơ chế cưỡng chế đồng thuận cũng không yêu cầu chấp thuận loại văn bản đó, nên người dùng không bị kẹt. Quản trị nền tảng khắc phục bằng cách soạn và công bố văn bản (UC606).

2. **Yêu cầu một phiên bản đã bị thay thế.** Ở bước 2, chỉ phiên bản đang hiệu lực là công khai. Yêu cầu một phiên bản cũ trả về không tìm thấy đối với người đọc thường; việc tra một phiên bản đã bị thay thế là thao tác của quản trị nền tảng trong màn hình quản lý văn bản (UC606), và của người tra hồ sơ đồng thuận khi cần đối chiếu (UC608). Người dùng muốn biết mình đã chấp thuận bản nào xem lịch sử đồng thuận ở trang Tài khoản, nơi ghi số phiên bản và mã băm.

3. **Phiên bản được công bố không kèm tệp đính kèm.** Ở bước 6, nếu văn bản chỉ có nội dung dạng văn bản trong cơ sở dữ liệu mà không có tệp, hệ thống nói rõ điều đó và giữ nguyên bản kết xuất trên màn hình thay vì trả về một tệp rỗng. Người đọc dùng chức năng in của trình duyệt nếu cần bản lưu.

**Kết quả mong đợi:** Người đọc nhận đúng nội dung của phiên bản đang hiệu lực, kèm số phiên bản, ngày hiệu lực và mã băm nội dung để đối chiếu với lịch sử đồng thuận của mình. Với loại văn bản chưa công bố, hệ thống trả về trạng thái không tìm thấy tường minh chứ không phải một trang trống.

---

#### UC112 — Chấp thuận văn bản pháp lý

*Bảng C-12: Mô tả chức năng Chấp thuận văn bản pháp lý*

| **Tên use case** | Chấp thuận văn bản pháp lý | **ID** | UC112 |
|---|---|---|---|
| **Actor chính** | Người dùng đã đăng nhập | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Người dùng đã đăng nhập | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 1 — Danh tính và quyền truy cập |

**Các thành phần tham gia và mối quan tâm:**

- **Người ký đóng góp dữ liệu** — kiểm soát được mức phát hành áp cho mẫu của mình.
- **Bộ phận pháp chế** — mỗi đồng thuận gắn với đúng phiên bản và mã băm nội dung, nên chứng minh được người dùng đã đồng ý với **văn bản nào**.
- **Nghiên cứu sinh khai thác dữ liệu** — chỉ dùng được mẫu có đồng thuận phù hợp với mục đích sử dụng.

**Mô tả tóm tắt:** *Người dùng đã đăng nhập đọc và chấp thuận các văn bản pháp lý đang hiệu lực — điều khoản sử dụng, chính sách quyền riêng tư, và văn bản đồng thuận thu thập dữ liệu quyết định mẫu do họ đóng góp được phát hành tới đâu.*

**Các mối quan hệ:**

- **Association (kết hợp):** Người dùng đã đăng nhập – Chấp thuận văn bản pháp lý
- **Include (bao gồm):** UC111 Xem văn bản pháp lý
- **Extend (mở rộng):** không *(UC113 mở rộng use case này)*
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Hệ thống hiển thị các văn bản đang hiệu lực mà tài khoản chưa chấp thuận, kèm ngày hiệu lực và lý do phải chấp thuận. Nếu người dùng đang thao tác gì đó bị chặn vì thiếu đồng thuận, màn hình này chen vào trước và ghi nhớ trang đích.
2. Người dùng mở một văn bản và đọc nội dung ngay trong trang (UC111).
3. Với văn bản đồng thuận thu thập dữ liệu, người dùng chọn một trong ba mức phát hành: chỉ dùng nội bộ tổ chức, dùng cho nghiên cứu có kiểm soát, hoặc phát hành công khai. Ba mức tạo thành một thang từ hẹp tới rộng.
4. Người dùng đánh dấu ô chấp thuận cho từng văn bản và bấm "Chấp thuận".
5. Hệ thống ghi một bản ghi đồng thuận cho **mỗi** văn bản, mỗi bản ghi lưu kèm số phiên bản, mã băm nội dung tại thời điểm chấp thuận, mức phát hành đã chọn nếu có, thời điểm và địa chỉ IP.
6. Hệ thống ghi một mục vào nhật ký kiểm toán, gỡ rào chặn đồng thuận cho tài khoản, và đưa người dùng trở lại trang họ đang muốn tới.

**Luồng luân phiên:**

1. **Chấp thuận trong lúc đăng ký:** các bước 2–4 diễn ra ngay trên biểu mẫu đăng ký; các bản ghi đồng thuận được ghi cùng lúc với bản ghi tài khoản ở bước 9 của UC101, nên không tồn tại khoảnh khắc nào tài khoản có mặt mà đồng thuận thì chưa.
2. **Nâng hoặc hạ mức phát hành sau này:** người dùng vào trang Tài khoản chọn lại mức phát hành. Hệ thống ghi một bản ghi đồng thuận mới thay vì sửa bản cũ, nên lịch sử cho thấy mức nào có hiệu lực trong khoảng thời gian nào — điều bắt buộc phải có, vì mỗi mẫu dữ liệu được đối chiếu với mức có hiệu lực tại thời điểm phát hành.

**Luồng ngoại lệ:**

1. **Văn bản có phiên bản mới sau khi người dùng đã chấp thuận bản cũ.** Ở bước 1, khi bộ phận pháp chế công bố phiên bản mới của một văn bản, hệ thống coi đồng thuận cũ là chưa phủ bản mới và hỏi lại người dùng ngay lần đăng nhập kế tiếp. Đồng thuận cũ **không** bị xoá; nó vẫn là bằng chứng cho khoảng thời gian nó có hiệu lực. Người dùng đọc phần thay đổi và chấp thuận lại. Cơ chế này là hệ quả trực tiếp của việc lưu mã băm nội dung: một chữ ký cho văn bản A không tự động là chữ ký cho văn bản A đã sửa.

2. **Người dùng từ chối chấp thuận.** Ở bước 4, nếu người dùng đóng màn hình mà không đánh dấu, hệ thống giữ tài khoản ở chế độ hạn chế: đọc được các trang thông tin, nhưng không thu mẫu, không tải lên, không xuất dữ liệu và không huấn luyện. Hệ thống nói rõ chức năng nào đang bị chặn và vì thiếu văn bản nào, thay vì trả về lỗi không quyền chung chung khiến người dùng tưởng mình bị cấm. Người dùng chấp thuận lúc nào thì các chức năng mở lại lúc đó, không cần đăng nhập lại.

3. **Chưa chọn mức phát hành.** Ở bước 3, nếu người dùng chấp thuận văn bản đồng thuận nhưng bỏ trống mức phát hành, hệ thống ghi nhận đồng thuận ở mức hẹp nhất và cảnh báo rằng mẫu do tài khoản đóng góp sẽ không xuất hiện trong bản phát hành nào rộng hơn. Thang đồng thuận được cưỡng chế **hai lần** — một lần lúc thu mẫu và một lần lúc dựng bản phát hành — nên một mẫu thu được ở mức hẹp không thể lọt vào bản phát hành rộng chỉ vì người dựng bản phát hành quên lọc.

4. **Ghi bản ghi đồng thuận thất bại giữa chừng.** Ở bước 5, khi người dùng chấp thuận nhiều văn bản trong một lần bấm, các bản ghi được ghi trong cùng một giao dịch; nếu một bản ghi hỏng thì cả lần chấp thuận bị huỷ và rào chặn giữ nguyên. Hệ thống chọn cách này thay vì ghi được bao nhiêu hay bấy nhiêu, vì một tài khoản đã chấp thuận điều khoản sử dụng nhưng chưa chấp thuận văn bản đồng thuận là trạng thái mà tầng cưỡng chế không diễn giải được. Người dùng bấm lại; nếu lỗi lặp lại thì đây là sự cố cơ sở dữ liệu và cần đường hỗ trợ (UC801).

**Kết quả mong đợi:** Mỗi văn bản đang hiệu lực có đúng một bản ghi đồng thuận của tài khoản, lưu số phiên bản, mã băm nội dung, mức phát hành đã chọn và thời điểm; rào chặn đồng thuận được gỡ và người dùng trở lại đúng trang họ đang muốn tới. Nếu một bản ghi không ghi được, cả lần chấp thuận bị huỷ và rào chặn giữ nguyên, để không tồn tại trạng thái chấp thuận nửa vời.

---

#### UC113 — Rút đồng thuận

*Bảng C-13: Mô tả chức năng Rút đồng thuận*

| **Tên use case** | Rút đồng thuận | **ID** | UC113 |
|---|---|---|---|
| **Actor chính** | Người khiếm thính – khiếm ngôn | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Người ký là chủ thể dữ liệu | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 1 — Danh tính và quyền truy cập |

**Các thành phần tham gia và mối quan tâm:**

- **Người ký (chủ thể dữ liệu)** — rút lại là rút thật, và mẫu của mình không xuất hiện trong bản phát hành mới nào nữa.
- **Bộ phận pháp chế** — việc chấp thuận đã xảy ra vẫn được lưu làm bằng chứng, việc rút được ghi bên cạnh chứ không xoá đè.
- **Nghiên cứu sinh** — bản phát hành dựng sau thời điểm rút phải loại đúng các mẫu liên quan.

**Mô tả tóm tắt:** *Người ký rút lại một đồng thuận đã cho. Việc rút có hiệu lực thật: từ thời điểm đó, các mẫu thuộc phạm vi đồng thuận ấy bị loại khỏi mọi bản phát hành mới.*

**Các mối quan hệ:**

- **Association (kết hợp):** Người khiếm thính – khiếm ngôn – Rút đồng thuận
- **Include (bao gồm):** không
- **Extend (mở rộng):** UC112 Chấp thuận văn bản pháp lý
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Người ký mở trang Tài khoản, mục Đồng thuận. Hệ thống liệt kê từng đồng thuận đã cho: loại văn bản, số phiên bản, mức phát hành đã chọn, thời điểm chấp thuận, và trạng thái còn hiệu lực hay đã rút.
2. Người ký bấm "Rút lại" trên một đồng thuận. Hệ thống hiển thị phần mô tả hệ quả: những chức năng sẽ bị khoá, và phạm vi mẫu sẽ bị loại khỏi các bản phát hành về sau.
3. Người ký xác nhận.
4. Hệ thống ghi mốc thời gian rút lên chính bản ghi đồng thuận đó, giữ nguyên các trường của lần chấp thuận gốc — phiên bản, mã băm, thời điểm — vì đó là bằng chứng lịch sử.
5. Hệ thống loại các mẫu thuộc phạm vi đồng thuận đó khỏi mọi lượt xuất dữ liệu và mọi bản phát hành dựng về sau. Việc loại này được thực hiện tại thời điểm dựng bản phát hành, bằng cách đối chiếu với trạng thái đồng thuận hiện hành, chứ không phải bằng cách đánh dấu sẵn lên từng mẫu.
6. Hệ thống ghi một mục vào nhật ký kiểm toán và gửi thông báo cho quản trị viên của tổ chức, để họ biết dung lượng dữ liệu dùng được của tổ chức vừa thay đổi.

**Luồng luân phiên:**

1. **Hạ mức phát hành thay vì rút hẳn:** ở bước 2, nếu người ký chỉ muốn thu hẹp phạm vi chứ không rút toàn bộ, họ chọn lại mức phát hành hẹp hơn ở UC112. Cách này giữ mẫu của họ dùng được trong phạm vi hẹp thay vì loại bỏ hoàn toàn.
2. **Chấp thuận lại sau khi rút:** người ký có thể chấp thuận lại chính văn bản đó bất cứ lúc nào (UC112). Thao tác tạo một bản ghi đồng thuận **mới** và không xoá dấu vết lần rút, nên lịch sử vẫn cho thấy có một khoảng thời gian đồng thuận không có hiệu lực — khoảng đó quyết định các bản phát hành dựng trong khoảng ấy không được chứa mẫu của người này.

**Luồng ngoại lệ:**

1. **Rút một văn bản bắt buộc.** Ở bước 3, nếu văn bản bị rút nằm trong nhóm buộc phải chấp thuận mới dùng được hệ thống, hệ thống cảnh báo rằng tài khoản sẽ chuyển sang chế độ hạn chế ngay sau khi rút, và hỏi xác nhận lần thứ hai bằng cách yêu cầu người ký gõ lại một từ khoá xác nhận. Sau khi rút, người ký vẫn đăng nhập được và vẫn xem được dữ liệu của mình, nhưng không thu thêm mẫu và không xuất dữ liệu. Đường quay lại là chấp thuận lại theo luồng luân phiên 2.

2. **Bản phát hành đã dựng và đã phân phối.** Ở bước 5, hệ thống nêu rõ trong phần mô tả hệ quả rằng các bản phát hành đã được dựng và đã gửi ra ngoài **không** thu hồi lại được bằng thao tác này. Việc rút áp cho các bản phát hành dựng về sau. Đây là giới hạn thật của hệ thống và được nói thẳng thay vì hứa hẹn quá mức: một tệp đã nằm trên máy của bên thứ ba không thể bị một nút bấm trong hệ thống này xoá đi. Người ký cần đường xử lý ngoài hệ thống thì liên hệ bộ phận pháp chế qua kênh hỗ trợ (UC801).

3. **Mẫu đang nằm trong một lượt xuất dữ liệu đang chạy.** Ở bước 5, nếu một tác vụ xuất dữ liệu đã bắt đầu trước thời điểm rút và đang chạy dở, tác vụ đó vẫn hoàn tất với tập mẫu nó đã chọn ở đầu lượt. Hệ thống không dừng tác vụ giữa chừng vì một tệp xuất dở là tệp không dùng được cho ai. Bản xuất kế tiếp sẽ loại mẫu đã rút. Quản trị viên muốn chắc chắn thì huỷ tệp xuất vừa tạo và chạy lại (UC213).

4. **Người ký không phải chủ tài khoản đóng góp mẫu.** Ở bước 1, một tài khoản chỉ rút được đồng thuận của chính nó. Với các mẫu được thu hộ — người thu là tài khoản A còn người ký là người B không có tài khoản — hệ thống hiện chưa có đường để người B tự rút đồng thuận, vì không có danh tính nào trong hệ thống ứng với người B. Đây là một khoảng trống đã được nêu ở §6 của phụ lục này; đường xử lý hiện tại là người B liên hệ tổ chức đã thu mẫu, và quản trị tổ chức xoá các mẫu liên quan (UC211).

**Kết quả mong đợi:** Bản ghi đồng thuận mang thêm mốc thời gian rút trong khi các trường của lần chấp thuận gốc giữ nguyên làm bằng chứng lịch sử; từ thời điểm đó, mọi lượt xuất dữ liệu và bản phát hành dựng mới đều loại các mẫu thuộc phạm vi đồng thuận ấy. Các bản phát hành đã phân phối trước đó không bị ảnh hưởng, và điều này được nói rõ với người ký trước khi họ xác nhận.

---

#### UC114 — Dùng thử nhận dạng

*Bảng C-14: Mô tả chức năng Dùng thử nhận dạng*

| **Tên use case** | Dùng thử nhận dạng | **ID** | UC114 |
|---|---|---|---|
| **Actor chính** | Khách vãng lai | **Mức độ cần thiết** | Tuỳ chọn |
| **Kích hoạt bởi** | Khách vãng lai | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 1 — Danh tính và quyền truy cập |

**Các thành phần tham gia và mối quan tâm:**

- **Khách vãng lai** — thử được năng lực nhận dạng trước khi quyết định tạo tài khoản.
- **Nền tảng** — tài nguyên suy luận có hạn nên phần dùng thử phải có trần theo ngày.
- **Dịch vụ suy luận (S3)** — nhận các cửa sổ điểm mốc và trả nhãn dự đoán.

**Mô tả tóm tắt:** *Khách vãng lai thử chức năng nhận dạng ký hiệu thời gian thực mà không cần tài khoản, trong một ngân sách thời gian tính theo ngày và theo trình duyệt.*

**Các mối quan hệ:**

- **Association (kết hợp):** Khách vãng lai – Dùng thử nhận dạng; Dịch vụ suy luận (S3)
- **Include (bao gồm):** không
- **Extend (mở rộng):** UC407 Nhận dạng ký hiệu thời gian thực
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Khách mở trang nhận dạng công khai và bấm "Dùng thử".
2. Hệ thống cấp một vé dùng thử gắn với trình duyệt hiện tại và mở một bản đếm số phút đã dùng trong ngày. Bản đếm lưu theo từng phút của ngày, nên nó ghi được "phút thứ mấy trong ngày đã tiêu" chứ không chỉ tổng số phút, và tự hết hạn khi sang ngày mới.
3. Hệ thống xin quyền dùng máy quay của trình duyệt và bật cơ chế theo vết bàn tay chạy ngay trên máy khách. Ảnh từ máy quay **không** rời khỏi máy khách; thứ gửi đi là các toạ độ điểm mốc bàn tay.
4. Hệ thống gom các điểm mốc thành cửa sổ trượt và gửi tới dịch vụ suy luận, rồi hiển thị nhãn dự đoán kèm độ tin cậy.
5. Hệ thống hiển thị số phút dùng thử còn lại trong ngày, cập nhật theo thời gian thực.
6. Khi khách dừng hoặc đóng trang, hệ thống chốt số phút đã tiêu vào ngân sách ngày và huỷ vé dùng thử.

**Luồng luân phiên:**

1. **Tạo tài khoản giữa chừng:** khách bấm "Tạo tài khoản" ngay trên màn hình dùng thử; sau khi đăng ký xong (UC101), họ dùng chức năng nhận dạng đầy đủ (UC407) và không còn bị ngân sách dùng thử ràng buộc.

**Luồng ngoại lệ:**

1. **Hết ngân sách dùng thử trong ngày.** Ở bước 2 hoặc giữa chừng ở bước 5, khi số phút đã tiêu chạm trần của ngày, hệ thống dừng gửi dữ liệu tới dịch vụ suy luận, đóng máy quay và hiển thị lời mời tạo tài khoản (UC101). Ngân sách gắn với trình duyệt chứ không gắn với người, nên nó là biện pháp hạn chế lạm dụng ở mức hợp lý chứ không phải một hàng rào không vượt được — điều này được nói rõ để không ai nhầm nó với một cơ chế kiểm soát truy cập. Khách chờ sang ngày hôm sau hoặc tạo tài khoản.

2. **Trình duyệt không cấp quyền dùng máy quay.** Ở bước 3, nếu khách từ chối quyền hoặc trình duyệt chặn sẵn, hệ thống hiển thị hướng dẫn cấp quyền theo từng trình duyệt và đề nghị đường thay thế là tải lên một tệp video ngắn. Vé dùng thử **không** bị tiêu vì chưa có phút nào được dùng. Nếu máy không có máy quay, đường tải video là đường duy nhất.

3. **Dịch vụ suy luận không phản hồi.** Ở bước 4, nếu dịch vụ suy luận hết thời gian chờ hoặc trả lỗi, hệ thống hiển thị thông báo dịch vụ đang tạm ngưng và **không** trừ ngân sách cho quãng thời gian hỏng. Số lần thử lại được giới hạn: sau vài lần liên tiếp không phản hồi, hệ thống dừng hẳn phiên dùng thử thay vì gửi lại vô hạn, và mời khách thử lại sau. Việc dừng có giới hạn là chủ ý — một vòng lặp thử lại không có điểm dừng vừa làm nóng máy khách vừa dồn thêm tải lên chính dịch vụ đang hỏng.

4. **Không phát hiện được bàn tay trong khung hình.** Ở bước 4, nếu cơ chế theo vết không thấy bàn tay nào — thiếu sáng, tay ra ngoài khung, máy quay bị che — hệ thống hiển thị gợi ý căn khung hình thay vì đưa ra một dự đoán dựa trên dữ liệu rỗng. Thời gian này vẫn tính vào ngân sách vì máy quay vẫn đang chạy. Khách chỉnh lại tư thế và tiếp tục.

5. **Máy khách quá yếu để chạy cơ chế theo vết.** Ở bước 3, nếu số khung hình xử lý được xuống quá thấp, hệ thống hạ tần số lấy mẫu và cảnh báo rằng kết quả nhận dạng sẽ kém chính xác, thay vì âm thầm trả về những dự đoán dựng trên dữ liệu quá thưa. Khách có thể tiếp tục với chất lượng thấp hoặc dừng lại.

**Kết quả mong đợi:** Khách vãng lai thấy được kết quả nhận dạng theo thời gian thực trong phạm vi ngân sách thời gian của ngày, và số phút đã dùng được ghi vào bản đếm gắn với trình duyệt. Khi hết ngân sách hoặc khi dịch vụ suy luận không phản hồi, phiên dùng thử dừng lại có kiểm soát; quãng thời gian dịch vụ hỏng không bị trừ vào ngân sách.

---

### 5.2 Nghiệp vụ 2 — Thu thập và quản lý dữ liệu mẫu

#### UC202 — Tải tệp video

*Bảng C-15: Mô tả chức năng Tải tệp video*

| **Tên use case** | Tải tệp video | **ID** | UC202 |
|---|---|---|---|
| **Actor chính** | Thành viên tổ chức | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Thành viên tổ chức | **Phân loại** | Phức tạp |
| **Loại** | external | **Nghiệp vụ** | 2 — Thu thập và quản lý dữ liệu mẫu |

**Các thành phần tham gia và mối quan tâm:**

- **Thành viên tổ chức** — đưa được các buổi quay đã thực hiện ngoài hiện trường vào hệ thống theo lô.
- **Người ký xuất hiện trong video** — bản gốc được giữ nguyên, và mức đồng thuận của mình vẫn theo mẫu.
- **Tổ chức** — không vượt hạn mức mẫu của gói dịch vụ mà không biết.
- **Kho lưu trữ ngoài (S2)** — nhận bản thô trước khi có bất kỳ bước chuẩn hoá nào.

**Mô tả tóm tắt:** *Thành viên tổ chức tải lên một hoặc nhiều tệp video của các ký hiệu đã quay sẵn. Tệp thô được lưu vào kho trước khi chuẩn hoá, sau đó điểm mốc bàn tay mới được trích xuất từ nó.*

**Các mối quan hệ:**

- **Association (kết hợp):** Thành viên tổ chức – Tải tệp video; Kho lưu trữ ngoài (S2)
- **Include (bao gồm):** UC203 Xử lý bản ghi
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** *Thu nhận mẫu* (trừu tượng)

**Xử lý sự kiện:**

1. Thành viên mở trang tải lên và khai bốn thông tin bắt buộc cho cả lô: lớp đích, ngôn ngữ, phương ngữ và người ký. Bốn giá trị này quyết định mẫu sinh ra thuộc về lớp nào và quy về ai, nên chúng được khai trước khi chọn tệp chứ không phải sau.
2. Thành viên chọn các tệp video và bấm "Tải lên". Trình duyệt gửi kèm mỗi tệp một mã lô ổn định do máy khách sinh ra, để một lần gửi lại vì mất mạng không tạo ra hai bản ghi cho cùng một tệp.
3. Hệ thống kiểm từng tệp: phần mở rộng nằm trong danh sách định dạng video được chấp nhận, dung lượng không vượt trần một tệp, và tên tệp được làm sạch trước khi dùng làm tên lưu trữ.
4. Hệ thống kiểm hạn mức mẫu của tổ chức theo gói dịch vụ, tính trên số tệp còn lại trong lô sau bước 3.
5. Hệ thống ghi từng tệp thô vào kho lưu **trước** mọi bước chuẩn hoá, ở một nhánh thư mục riêng dành cho bản thô. Đây là điểm cốt yếu của thiết kế: bản gốc phải tồn tại độc lập với kết quả xử lý, để một lỗi trong khâu trích đặc trưng không làm mất dữ liệu đã quay.
6. Hệ thống trả biên nhận tải lên, liệt kê tệp nào được chấp nhận, tệp nào bị từ chối và vì lý do gì.
7. Thành viên bấm "Xử lý". Hệ thống đưa mỗi tệp thành một tác vụ nền (UC203) và trả về mã tác vụ tương ứng.
8. Thành viên theo dõi tiến độ của các tác vụ (UC204) và mở lớp để xem mẫu sinh ra (UC207).

**Luồng luân phiên:**

1. **Tải lên và xử lý ngay:** thành viên bật tuỳ chọn xử lý tự động; bước 7 diễn ra ngay sau bước 6 mà không cần bấm thêm. Luồng chỉ khác ở chỗ ai kích hoạt, còn các bước xử lý là một.
2. **Tải lên nhiều lớp trong một buổi:** thành viên lặp lại từ bước 1 cho từng lớp. Hệ thống không hỗ trợ khai lớp khác nhau cho từng tệp trong cùng một lô, vì một lô một lớp là ràng buộc giúp tránh loại sai sót gán nhãn khó phát hiện nhất.
3. **Gửi lại lô sau khi mất mạng:** thành viên bấm lại "Tải lên" với cùng tập tệp; nhờ mã lô ở bước 2, hệ thống nhận ra các tệp đã lưu và chỉ nhận phần còn thiếu, thay vì nhân đôi dữ liệu.

**Luồng ngoại lệ:**

1. **Định dạng tệp không được hỗ trợ.** Ở bước 3, tệp có phần mở rộng ngoài danh sách chấp nhận bị từ chối ngay tại máy chủ, kèm danh sách định dạng hợp lệ hiển thị ngay trên dòng của tệp đó. Các tệp còn lại trong lô **vẫn tiếp tục** được xử lý — hệ thống không huỷ cả lô vì một tệp sai, vì một buổi quay ngoài hiện trường thường có vài tệp lẫn định dạng và bắt tải lại toàn bộ là phí công. Thành viên chuyển đổi định dạng tệp bị loại rồi tải bổ sung.

2. **Tệp vượt trần dung lượng.** Ở bước 3, tệp lớn hơn trần cho phép bị từ chối kèm con số giới hạn cụ thể để thành viên biết phải cắt ngắn tới đâu. Không phần nào của tệp đó được ghi vào kho. Với các buổi quay dài, cách xử lý đúng là cắt thành nhiều đoạn theo từng ký hiệu trước khi tải lên; một tệp video dài chứa nhiều ký hiệu cũng không dùng được vì mỗi tệp được gán đúng một lớp.

3. **Vượt hạn mức mẫu của tổ chức.** Ở bước 4, nếu số tệp trong lô làm tổ chức vượt hạn mức của gói dịch vụ, hệ thống nhận đúng số tệp còn nằm trong hạn mức và từ chối phần vượt, nêu rõ tên từng tệp bị từ chối cùng số suất còn lại. Cách xử lý từng phần này là chủ ý: từ chối cả lô sẽ khiến một tổ chức sắp đầy hạn mức không tải lên được gì cả. Quản trị tổ chức nâng gói dịch vụ (UC506) hoặc dọn bớt dữ liệu cũ (UC212) rồi tải phần còn lại.

4. **Kho lưu trữ không sẵn sàng.** Ở bước 5, nếu kho lưu trữ ngoài từ chối hoặc hết thời gian chờ, hệ thống dừng lượt tải tại tệp đang xử lý và báo lỗi lưu trữ. Các tệp đã ghi xong trước đó vẫn còn và đã có biên nhận; tệp đang ghi dở **không** được đăng ký thành mẫu, nên hệ thống không để lại mẫu trỏ tới một tệp không đầy đủ. Thành viên thử lại lô còn thiếu sau ít phút; nếu lỗi lặp lại thì đây là sự cố hạ tầng và kỹ sư vận hành xử lý (UC704).

5. **Không phát hiện được bàn tay trong toàn bộ video.** Sau bước 7, khi tác vụ nền chạy, nếu không khung hình nào có bàn tay, tác vụ kết thúc ở trạng thái thất bại kèm lý do cụ thể và **không** tạo mẫu nào. Tệp thô vẫn nằm nguyên trong kho, nên thành viên xem lại được video để biết vấn đề là thiếu sáng, tay ra ngoài khung hay quay nhầm nội dung. Đây là lỗi phổ biến nhất trong khâu tải lên và là lý do bản thô được giữ độc lập ở bước 5.

6. **Đứt kết nối giữa chừng.** Ở bước 2, nếu trình duyệt mất mạng khi đang gửi, phần đã gửi bị bỏ và không có biên nhận nào được trả về. Thành viên tải lại theo luồng luân phiên 3; mã lô bảo đảm lần gửi lại không nhân đôi dữ liệu. Với các tệp lớn, nguyên nhân thường gặp là thời gian chờ của tầng cổng vào chứ không phải của ứng dụng, nên thông báo lỗi nhắc thành viên tải từng tệp thay vì cả lô.

**Kết quả mong đợi:** Mọi tệp được chấp nhận đã nằm nguyên vẹn trong nhánh lưu trữ bản thô **trước** bất kỳ bước chuẩn hoá nào, và mỗi tệp có một tác vụ xử lý kèm mã tác vụ để theo dõi. Biên nhận nêu rõ tệp nào được nhận, tệp nào bị từ chối và vì lý do gì; các tệp bị từ chối không để lại phần ghi dở dang nào trong kho.

---

#### UC203 — Xử lý bản ghi

*Bảng C-16: Mô tả chức năng Xử lý bản ghi*

| **Tên use case** | Xử lý bản ghi | **ID** | UC203 |
|---|---|---|---|
| **Actor chính** | Tiến trình nền (S4) | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Hàng đợi có một lượt thu hoặc một lượt tải lên | **Phân loại** | Phức tạp |
| **Loại** | **internal** | **Nghiệp vụ** | 2 — Thu thập và quản lý dữ liệu mẫu |

**Các thành phần tham gia và mối quan tâm:**

- **Tiến trình nền (S4)** — hoàn tất được công việc mà không giữ người dùng chờ.
- **Người đóng góp** — biết mẫu của mình đã thành hình hay thất bại vì lý do gì.
- **Nghiên cứu sinh** — mẫu sinh ra có chỉ số chất lượng và tệp mô tả đi kèm để tái lập được.
- **Kho lưu trữ ngoài (S2)** — nhận tệp đặc trưng theo cơ chế thử lại có giới hạn.

**Mô tả tóm tắt:** *Tiến trình nền biến một bản ghi thô thành một mẫu dùng được cho huấn luyện: trích điểm mốc bàn tay, cắt cửa sổ độ dài cố định, sinh biến thể tăng cường, ghi tệp đặc trưng và đăng ký mẫu vào nguồn sự thật. Đây là use case duy nhất của hệ thống do máy khởi phát chứ không do người bấm nút.*

**Các mối quan hệ:**

- **Association (kết hợp):** Tiến trình nền (S4) – Xử lý bản ghi; Kho lưu trữ ngoài (S2)
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Tiến trình nhận việc từ hàng đợi, đánh dấu tác vụ đang chạy và ghi thời điểm bắt đầu để màn hình theo dõi hiển thị được (UC204).
2. Tiến trình đọc bản ghi thô và trích điểm mốc bàn tay theo từng khung hình: 21 điểm mốc × 3 toạ độ × 2 bàn tay, tức 126 đặc trưng cho mỗi khung.
3. Tiến trình cắt chuỗi khung hình thành cửa sổ có độ dài cố định theo cấu hình của bản triển khai, và chuẩn hoá hệ toạ độ để khoảng cách giữa người ký và máy quay không trở thành một đặc trưng giả.
4. Tiến trình tính các chỉ số chất lượng của từng cửa sổ, gồm độ đầy đủ — tỷ lệ khung hình thật sự thấy bàn tay — và độ rung của quỹ đạo điểm mốc.
5. Tiến trình sinh các biến thể tăng cường của cửa sổ theo hệ số cấu hình. Hệ số này khác nhau giữa mẫu thu trực tiếp và mẫu từ video tải lên, và được ghi vào nhật ký cấu hình mỗi lần chạy để về sau đối chiếu được.
6. Tiến trình ghi tệp đặc trưng, kèm một tệp mô tả nằm cạnh nó chứa đủ thông tin để dựng lại dòng dữ liệu nếu danh bạ bị mất.
7. Tiến trình ghi một dòng mẫu vào danh bạ nguồn sự thật rồi soi sang cơ sở dữ liệu. Bản phản chiếu ra bảng tính **không** nằm ở bước này mà do một tác vụ theo lịch thực hiện, để một sự cố của dịch vụ bảng tính không chặn đường ghi dữ liệu.
8. Tiến trình chuyển việc đẩy tệp lên kho lưu trữ ngoài cho một tác vụ riêng có thử lại — tối đa năm lần, cách nhau mười giây — và ghi khoá lưu trữ vào dòng dữ liệu khi đẩy thành công.
9. Tiến trình đánh dấu tác vụ hoàn tất, ghi số mẫu đã sinh, và gửi thông báo cho chủ sở hữu lượt thu.

**Luồng luân phiên:**

1. **Nguồn là lượt thu trực tiếp:** khi việc đến từ màn hình thu mẫu, các điểm mốc đã được trích ngay trên máy người dùng, nên bước 2 được bỏ qua và tiến trình bắt đầu từ bước 3. Đây là lý do hệ số tăng cường ở bước 5 khác nhau giữa hai nguồn.
2. **Chạy lại một tác vụ đã thất bại:** người dùng bấm chạy lại từ màn hình theo dõi; tiến trình chạy lại toàn bộ các bước với cùng mã định danh mẫu. Vì mã định danh là cố định, lần chạy lại **ghi đè** kết quả cũ chứ không nhân bản dữ liệu.

**Luồng ngoại lệ:**

1. **Không phát hiện được bàn tay.** Ở bước 2, nếu không khung hình nào cho ra điểm mốc, tiến trình kết thúc tác vụ ở trạng thái thất bại kèm lý do đọc được cho người dùng, và **không** tạo dòng mẫu nào. Tiến trình không thử lại, vì thử lại cùng một tệp sẽ cho cùng kết quả và chỉ tốn tài nguyên hàng đợi. Người dùng xem lại tệp gốc và quay lại (UC201) hoặc tải lên tệp khác (UC202).

2. **Cửa sổ ngắn hơn độ dài quy định.** Ở bước 3, nếu bản ghi quá ngắn, tiến trình đệm thêm cho đủ độ dài và **ghi việc đã đệm vào chỉ số chất lượng** của mẫu, thay vì âm thầm loại mẫu hoặc âm thầm đệm. Cách này giữ lại dữ liệu ít ỏi của các lớp hiếm, đồng thời để người dựng bộ dữ liệu tự quyết định có loại các mẫu đã đệm hay không. Mẫu đệm quá nhiều sẽ lộ ra ở chỉ số độ đầy đủ thấp khi xem chi tiết lớp (UC207).

3. **Đẩy tệp lên kho lưu trữ thất bại.** Ở bước 8, sau năm lần thử cách nhau mười giây mà vẫn hỏng, tác vụ đẩy tệp dừng hẳn thay vì thử lại vô hạn. Dòng dữ liệu giữ nguyên đường dẫn cục bộ và **không** có khoá lưu trữ; mẫu vẫn dùng được cho huấn luyện trên chính máy triển khai. Tác vụ đối soát chạy theo lịch sẽ phát hiện dòng thiếu khoá lưu trữ và điền về sau (UC703). Giới hạn năm lần là điểm quan trọng: một vòng thử lại không có điểm dừng khi kho lưu trữ hỏng dài ngày sẽ làm nghẽn hàng đợi và chặn cả các lượt thu đang chờ.

4. **Ghi vào danh bạ nguồn sự thật thất bại.** Ở bước 7, nếu không ghi được dòng vào danh bạ, tiến trình dừng và trả việc về hàng đợi thay vì đi tiếp. Trạng thái "mẫu có trong cơ sở dữ liệu nhưng thiếu trong danh bạ" bị coi là bất nhất và phải được sửa, vì danh bạ mới là nguồn sự thật còn cơ sở dữ liệu chỉ là bản soi. Nếu lỗi vẫn lặp lại sau các lần thử lại của hàng đợi, tác vụ đối soát dựng lại phần thiếu từ cơ sở dữ liệu (UC703).

5. **Tiến trình dừng đột ngột giữa chừng.** Ở bất kỳ bước nào, nếu tiến trình bị dừng — hết bộ nhớ, máy chủ khởi động lại, hàng đợi thu hồi việc quá hạn — việc quay lại hàng đợi và được một tiến trình khác nhận. Vì mã định danh mẫu được tính cố định từ dữ liệu đầu vào chứ không sinh ngẫu nhiên, lần chạy lại ghi đè lên kết quả dở dang chứ không tạo thêm bản sao. Số lần một việc được nhận lại cũng có trần; vượt trần thì việc bị đánh dấu thất bại vĩnh viễn để người dùng thấy, thay vì luẩn quẩn trong hàng đợi mãi.

6. **Hết bộ nhớ khi xử lý video dài.** Ở bước 2, một tệp dài với độ phân giải cao có thể vượt hạn mức bộ nhớ của tiến trình. Tiến trình bị hệ điều hành dừng, việc quay lại hàng đợi theo ngoại lệ 5, và nếu lặp lại đủ số lần thì tác vụ chuyển sang trạng thái thất bại kèm lý do. Cách xử lý là cắt video thành các đoạn ngắn hơn rồi tải lại (UC202).

**Kết quả mong đợi:** Một bản ghi thô trở thành các mẫu có tệp đặc trưng, tệp mô tả đi kèm và chỉ số chất lượng, được đăng ký thành dòng trong danh bạ nguồn sự thật rồi soi sang cơ sở dữ liệu. Tệp đã được đẩy lên kho lưu trữ và khoá lưu trữ đã ghi vào dòng dữ liệu; nếu đẩy thất bại sau các lần thử, dòng vẫn dùng được với đường dẫn cục bộ và chờ tác vụ đối soát điền bù. Trường hợp thất bại, tác vụ mang trạng thái thất bại kèm lý do đọc được và không có mẫu rác nào được tạo.

---

#### UC204 — Theo dõi trạng thái tác vụ

*Bảng C-17: Mô tả chức năng Theo dõi trạng thái tác vụ*

| **Tên use case** | Theo dõi trạng thái tác vụ | **ID** | UC204 |
|---|---|---|---|
| **Actor chính** | Thành viên tổ chức | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Thành viên tổ chức | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 2 — Thu thập và quản lý dữ liệu mẫu |

**Các thành phần tham gia và mối quan tâm:**

- **Thành viên tổ chức** — biết lượt tải lên của mình đang ở đâu và bao giờ xong.
- **Nền tảng** — không để mã tác vụ trở thành đường dò dữ liệu của tổ chức khác.

**Mô tả tóm tắt:** *Thành viên tổ chức theo dõi tiến độ của các tác vụ nền sinh ra từ những lượt thu và lượt tải lên của mình.*

**Các mối quan hệ:**

- **Association (kết hợp):** Thành viên tổ chức – Theo dõi trạng thái tác vụ
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Thành viên mở danh sách tác vụ. Hệ thống hiển thị các tác vụ gần đây của chính tài khoản đó, mỗi dòng gồm tên tệp nguồn, lớp đích, trạng thái, tiến độ và thời điểm bắt đầu.
2. Hệ thống làm mới trạng thái các tác vụ đang chạy theo một chu kỳ cố định, và dừng làm mới khi không còn tác vụ nào đang chạy — vòng hỏi trạng thái có điều kiện dừng chứ không chạy mãi.
3. Thành viên mở một tác vụ để xem chi tiết: tệp nguồn, lớp đích, số mẫu đã sinh ra, và nhật ký các bước đã hoàn tất.
4. Khi tác vụ kết thúc thành công, hệ thống hiển thị các mẫu thu được kèm liên kết tới trang chi tiết lớp (UC207).

**Luồng luân phiên:**

1. **Theo dõi từ trang tải lên:** ngay sau bước 7 của UC202, các tác vụ vừa tạo hiện thành một dải tiến độ ngay trên trang tải lên; nội dung và nguồn dữ liệu giống hệt danh sách tác vụ, chỉ khác vị trí hiển thị.

**Luồng ngoại lệ:**

1. **Tác vụ thất bại.** Ở bước 4, hệ thống hiển thị lý do thất bại đúng như tiến trình nền đã ghi — không phát hiện bàn tay, tệp hỏng, hết bộ nhớ — kèm nút chạy lại với chính tệp nguồn đó. Số lần chạy lại thủ công không giới hạn nhưng mỗi lần là một quyết định của người dùng, khác với cơ chế thử lại tự động vốn có trần. Nếu ba lần chạy lại đều thất bại cùng một lý do, thông báo khuyên thành viên xem lại tệp gốc thay vì tiếp tục chạy lại.

2. **Không tìm thấy tác vụ.** Ở bước 3, nếu mã tác vụ không tồn tại, hoặc tồn tại nhưng thuộc một tổ chức khác, hệ thống trả về cùng một câu trả lời là không tìm thấy. Việc trả lời giống nhau cho hai trường hợp là chủ ý: nếu hệ thống phân biệt "không có" với "không được xem", mã tác vụ sẽ trở thành công cụ dò xem tổ chức khác có bao nhiêu việc đang chạy. Thành viên kiểm tra lại đường dẫn hoặc quay về danh sách tác vụ của mình.

3. **Hàng đợi ùn việc.** Ở bước 1, khi số việc chờ vượt năng lực xử lý, hệ thống hiển thị vị trí trong hàng đợi và thời gian chờ ước tính, thay vì một thanh tiến độ đứng yên khiến người dùng tưởng hệ thống treo. Thành viên không có thao tác nào để đẩy nhanh; kỹ sư vận hành thấy độ dài hàng đợi trong giám sát (UC704) và tăng số tiến trình xử lý nếu cần.

4. **Tác vụ treo quá lâu ở trạng thái đang chạy.** Ở bước 2, nếu một tác vụ ở trạng thái đang chạy vượt quá thời hạn hiển thị cho phép mà không cập nhật tiến độ, hệ thống đánh dấu nó là nghi treo và gợi ý chạy lại. Nguyên nhân thường gặp là tiến trình xử lý đã chết mà chưa kịp ghi trạng thái thất bại; hàng đợi sẽ tự thu hồi việc quá hạn và giao lại, nên trong nhiều trường hợp tác vụ tự hoàn tất mà không cần can thiệp.

**Kết quả mong đợi:** Người dùng biết chính xác từng tác vụ của mình đang ở trạng thái nào — chờ, đang chạy, hoàn tất hay thất bại — cùng lý do khi thất bại và đường đi tới các mẫu khi thành công. Mã tác vụ của tổ chức khác luôn trả về cùng một câu trả lời không tìm thấy, nên màn hình này không dùng để dò dữ liệu chéo tổ chức được.

---

#### UC205 — Đặt tuỳ chọn thu mẫu

*Bảng C-18: Mô tả chức năng Đặt tuỳ chọn thu mẫu*

| **Tên use case** | Đặt tuỳ chọn thu mẫu | **ID** | UC205 |
|---|---|---|---|
| **Actor chính** | Thành viên tổ chức | **Mức độ cần thiết** | Tuỳ chọn |
| **Kích hoạt bởi** | Thành viên tổ chức | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 2 — Thu thập và quản lý dữ liệu mẫu |

**Các thành phần tham gia và mối quan tâm:**

- **Thành viên tổ chức** — không phải chọn lại ngôn ngữ và phương ngữ ở mỗi buổi thu.
- **Tổ chức** — tuỳ chọn cá nhân không được phép nới rộng phạm vi ghi của tài khoản.

**Mô tả tóm tắt:** *Thành viên tổ chức lưu lại ngôn ngữ và phương ngữ mình thường thu, để các màn hình thu mẫu thôi hỏi lại hai câu đó ở mỗi phiên làm việc.*

**Các mối quan hệ:**

- **Association (kết hợp):** Thành viên tổ chức – Đặt tuỳ chọn thu mẫu
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Thành viên mở màn hình thu mẫu. Hệ thống đọc tuỳ chọn đã lưu của tài khoản và chọn sẵn ngôn ngữ cùng phương ngữ tương ứng.
2. Thành viên thay đổi lựa chọn cho buổi thu hiện tại.
3. Thành viên đánh dấu "Đặt làm mặc định của tôi" và lưu.
4. Hệ thống lưu tuỳ chọn gắn với tài khoản, không gắn với thiết bị, nên nó theo người dùng sang máy khác.
5. Hệ thống áp tuỳ chọn cho các màn hình thu mẫu, tải lên và duyệt danh mục từ lần mở kế tiếp trở đi.

**Luồng luân phiên:**

1. **Đổi tạm cho một buổi thu:** thành viên đổi lựa chọn ở bước 2 nhưng không đánh dấu lưu làm mặc định. Giá trị mới chỉ có hiệu lực cho phiên làm việc hiện tại; lần mở sau vẫn dùng giá trị đã lưu trước đó.

**Luồng ngoại lệ:**

1. **Tài khoản chưa có tuỳ chọn nào.** Ở bước 1, hệ thống lấy giá trị mặc định của tổ chức thay vì để trống hai ô. Để trống là lựa chọn tệ hơn vì nó buộc mọi thành viên mới phải trả lời hai câu hỏi trước khi thu được mẫu đầu tiên, và câu trả lời sai ở đây tạo ra mẫu gắn sai phương ngữ — loại sai sót chỉ lộ ra rất muộn.

2. **Phương ngữ đã lưu không còn hiệu lực.** Ở bước 1, nếu phương ngữ trong tuỳ chọn đã bị từ chối trong khâu kiểm duyệt hoặc đã bị gỡ khỏi danh mục, hệ thống quay về mặc định theo ngôn ngữ và hiển thị một dòng giải thích vì sao lựa chọn cũ biến mất. Nếu im lặng thay giá trị, thành viên sẽ thu cả buổi dưới một phương ngữ mà họ không hề chọn. Thành viên chọn phương ngữ khác hoặc đề xuất phương ngữ mới (UC306).

3. **Tuỳ chọn không phải là quyền.** Ở bước 5, tuỳ chọn chỉ quyết định giá trị được chọn sẵn trên giao diện. Nếu tài khoản không có quyền ghi vào phạm vi tương ứng, thao tác thu mẫu vẫn bị từ chối ở tầng kiểm quyền dù ô đã được chọn sẵn. Đây là ranh giới cần nói rõ trong tài liệu vì nó dễ bị hiểu nhầm: một giá trị mặc định thuận tiện không bao giờ được phép trở thành một đường nới quyền.

**Kết quả mong đợi:** Tuỳ chọn ngôn ngữ và phương ngữ được lưu theo tài khoản và có hiệu lực trên mọi thiết bị người dùng đăng nhập, làm giá trị chọn sẵn cho các màn hình thu mẫu, tải lên và danh mục. Tuỳ chọn không làm thay đổi phạm vi mà tài khoản được phép ghi.

---

#### UC206 — Duyệt danh mục lớp

*Bảng C-19: Mô tả chức năng Duyệt danh mục lớp*

| **Tên use case** | Duyệt danh mục lớp | **ID** | UC206 |
|---|---|---|---|
| **Actor chính** | Thành viên tổ chức | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Thành viên tổ chức | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 2 — Thu thập và quản lý dữ liệu mẫu |

**Các thành phần tham gia và mối quan tâm:**

- **Thành viên tổ chức** — biết còn lớp nào thiếu mẫu để thu tiếp cho đúng chỗ.
- **Tổ chức** — chỉ nhìn thấy danh mục của mình; lớp của tổ chức khác không lộ ra.

**Mô tả tóm tắt:** *Thành viên tổ chức duyệt các lớp trong danh mục từ vựng, lọc theo ngôn ngữ và phương ngữ, để chọn lớp cần thu tiếp.*

**Các mối quan hệ:**

- **Association (kết hợp):** Thành viên tổ chức – Duyệt danh mục lớp
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Thành viên mở trang danh mục lớp.
2. Hệ thống lấy tổ chức hiện hành từ ngữ cảnh phiên làm việc và trả về các lớp mà tổ chức đó nhìn thấy được: lớp của chính tổ chức, cộng với phần danh mục dùng chung ở chế độ chỉ đọc. Mỗi dòng kèm số mẫu hiện có và tiến độ so với mục tiêu thu.
3. Thành viên lọc theo ngôn ngữ, theo phương ngữ, theo trạng thái, hoặc tìm theo từ khoá trong tên lớp.
4. Hệ thống trả về các lớp khớp điều kiện, sắp xếp sao cho những lớp còn cách xa mục tiêu thu nhất nằm ở đầu — mục đích của màn hình này là trả lời câu hỏi "thu gì tiếp theo".
5. Thành viên chọn một lớp để xem chi tiết (UC207) hoặc bắt đầu thu mẫu ngay cho lớp đó (UC201).

**Luồng luân phiên:**

1. **Duyệt phần danh mục dùng chung:** thành viên chuyển sang tab danh mục cộng đồng. Các lớp ở đây hiển thị ở chế độ chỉ đọc; muốn thu mẫu cho một lớp cộng đồng, tổ chức phải nhân bản lớp đó về danh mục của mình trước (UC310).

**Luồng ngoại lệ:**

1. **Danh mục của tổ chức còn trống.** Ở bước 2, nếu tổ chức chưa có lớp nào, hệ thống không hiển thị một bảng rỗng mà hướng dẫn cách tạo lớp đầu tiên (UC301) hoặc nhân bản từ danh mục dùng chung (UC310). Đây là màn hình đầu tiên mà một tổ chức mới nhìn thấy, nên một bảng rỗng không lời giải thích là chỗ người dùng mới bỏ cuộc.

2. **Bộ lọc không cho kết quả nào.** Ở bước 4, hệ thống báo không tìm thấy lớp nào khớp và liệt kê các điều kiện lọc đang bật kèm nút xoá từng điều kiện. Nguyên nhân thường gặp là bộ lọc phương ngữ còn sót lại từ lần duyệt trước.

3. **Lớp của tổ chức khác.** Ở bước 2, lớp thuộc tổ chức khác không xuất hiện trong kết quả, kể cả khi tên lớp trùng khớp từ khoá tìm kiếm. Việc lọc này do tầng cách ly dữ liệu ở cơ sở dữ liệu thực hiện chứ không do câu truy vấn của màn hình, nên một lỗi ở tầng giao diện cũng không làm lộ dữ liệu sang tổ chức khác. Hệ quả cần biết: nếu ngữ cảnh tổ chức chưa được thiết lập đúng, kết quả trả về là danh sách rỗng chứ không phải danh sách đầy đủ.

4. **Số mẫu hiển thị lệch so với thực tế.** Ở bước 2, các số đếm được tính từ bản soi trong cơ sở dữ liệu chứ không đếm lại tệp, nên nếu bản soi lệch với danh bạ nguồn sự thật thì con số hiển thị cũng lệch theo. Lệch loại này được tác vụ đối soát định kỳ phát hiện và sửa (UC703); người dùng nghi ngờ số đếm sai thì đối chiếu ở trang chi tiết lớp, nơi liệt kê từng phiên thu.

**Kết quả mong đợi:** Thành viên thấy đúng tập lớp mà tổ chức mình được phép nhìn, kèm số mẫu và khoảng cách tới mục tiêu, sắp xếp để trả lời được câu hỏi thu gì tiếp theo. Lớp của tổ chức khác không xuất hiện trong bất kỳ kết quả nào, kể cả khi khớp từ khoá tìm kiếm.

---

#### UC207 — Xem chi tiết lớp

*Bảng C-20: Mô tả chức năng Xem chi tiết lớp*

| **Tên use case** | Xem chi tiết lớp | **ID** | UC207 |
|---|---|---|---|
| **Actor chính** | Thành viên tổ chức | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Thành viên tổ chức | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 2 — Thu thập và quản lý dữ liệu mẫu |

**Các thành phần tham gia và mối quan tâm:**

- **Thành viên tổ chức** — đánh giá được chất lượng dữ liệu mình đã thu cho một lớp.
- **Biên tập viên** — phát hiện phiên thu gán sai người ký để sửa (UC210).
- **Nghiên cứu sinh** — nhìn được chỉ số chất lượng trước khi đưa lớp vào tập huấn luyện.

**Mô tả tóm tắt:** *Thành viên tổ chức mở một lớp và xem các phiên thu cùng các mẫu đã ghi cho lớp đó, kèm chỉ số chất lượng của từng mẫu.*

**Các mối quan hệ:**

- **Association (kết hợp):** Thành viên tổ chức – Xem chi tiết lớp
- **Include (bao gồm):** không
- **Extend (mở rộng):** không *(UC208 và UC210 mở rộng use case này)*
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Thành viên mở một lớp từ danh mục.
2. Hệ thống hiển thị thông tin định danh của lớp: tên, ngôn ngữ, phương ngữ, vùng, số bàn tay yêu cầu và mục tiêu số mẫu. Năm thuộc tính đầu hợp thành khoá định danh của lớp, nên hai lớp cùng tên khác vùng là hai lớp khác nhau.
3. Hệ thống liệt kê các phiên thu của lớp, mỗi dòng gồm người ký, ngày thu, số mẫu trong phiên, nguồn dữ liệu là thu trực tiếp hay tải lên, và dấu hiệu cho biết tài khoản hiện tại có phải chủ sở hữu phiên hay không.
4. Thành viên mở một phiên thu. Hệ thống hiển thị từng mẫu trong phiên kèm hai chỉ số chất lượng: độ đầy đủ và độ rung.
5. Thành viên có thể xem trước phiên thu (UC208), xoá phiên (UC209), xoá một mẫu đơn lẻ (UC211) hoặc gán lại người ký (UC210).

**Luồng luân phiên:**

1. **Mở từ màn hình theo dõi tác vụ:** sau khi một tác vụ xử lý hoàn tất, người dùng vào thẳng bước 4 với phiên thu vừa sinh ra, bỏ qua bước duyệt danh sách.

**Luồng ngoại lệ:**

1. **Tài khoản không sở hữu phiên thu.** Ở bước 5, thành viên không phải chủ sở hữu chỉ xem được ở chế độ chỉ đọc: các nút xoá và gán lại bị ẩn, và nếu yêu cầu vẫn được gửi thẳng lên máy chủ thì tầng kiểm quyền từ chối. Chỉ chủ sở hữu phiên hoặc tài khoản có vai biên tập trong tổ chức mới thao tác được. Thành viên cần sửa dữ liệu của người khác thì nhờ biên tập viên của tổ chức.

2. **Tệp đặc trưng của một mẫu không đọc được.** Ở bước 4, nếu tệp không mở được — tệp đã bị xoá dưới nền, khoá lưu trữ trỏ sai, hoặc kho lưu trữ đang không phản hồi — hệ thống vẫn hiển thị dòng dữ liệu của mẫu kèm dấu "tệp không sẵn sàng", thay vì để hỏng cả trang. Người dùng vẫn thấy được siêu dữ liệu và vẫn xoá được mẫu hỏng. Nếu nhiều mẫu cùng lỗi, nguyên nhân thường là kho lưu trữ chứ không phải từng tệp, và tác vụ đối soát sẽ liệt kê chúng (UC703).

3. **Chỉ số chất lượng bằng không.** Ở bước 4, độ đầy đủ bằng không có nghĩa là không khung hình nào trong cửa sổ thấy đủ số bàn tay mà lớp yêu cầu — **không** có nghĩa là tệp rỗng. Phân biệt hai điều này quan trọng vì chúng dẫn tới hai cách xử lý khác nhau: mẫu độ đầy đủ thấp là mẫu quay hỏng cần thu lại, còn tệp rỗng là sự cố xử lý cần chạy lại tác vụ. Số bàn tay yêu cầu lấy theo siêu dữ liệu của lớp chứ không suy đoán từ dữ liệu.

4. **Phiên thu đã bị xoá mềm.** Ở bước 3, các phiên đã xoá không xuất hiện trong danh sách này; chúng nằm ở thùng rác và khôi phục được (UC212). Người dùng không tìm thấy một phiên mình chắc chắn đã thu nên kiểm thùng rác trước khi kết luận dữ liệu đã mất.

**Kết quả mong đợi:** Người dùng nắm được chất lượng dữ liệu của một lớp ở mức từng phiên thu và từng mẫu, biết mình có quyền thao tác trên phiên nào, và các mẫu có tệp không đọc được vẫn hiện ra kèm dấu hiệu thay vì làm hỏng cả trang.

---

#### UC208 — Xem trước phiên thu

*Bảng C-21: Mô tả chức năng Xem trước phiên thu*

| **Tên use case** | Xem trước phiên thu | **ID** | UC208 |
|---|---|---|---|
| **Actor chính** | Thành viên tổ chức | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Thành viên tổ chức | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 2 — Thu thập và quản lý dữ liệu mẫu |

**Các thành phần tham gia và mối quan tâm:**

- **Thành viên tổ chức** — xem lại được động tác đã thu để quyết định giữ hay bỏ.
- **Tiến trình nền (S4)** — dựng bản xem trước ngoài luồng tương tác.

**Mô tả tóm tắt:** *Thành viên tổ chức phát lại bản dựng xem trước của một phiên thu để đánh giá bản ghi có dùng được không.*

**Các mối quan hệ:**

- **Association (kết hợp):** Thành viên tổ chức – Xem trước phiên thu; Tiến trình nền (S4)
- **Include (bao gồm):** không
- **Extend (mở rộng):** UC207 Xem chi tiết lớp
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Thành viên bấm "Xem trước" trên một phiên thu.
2. Hệ thống kiểm phiên này đã có bản dựng xem trước còn hạn hay chưa.
3. Chưa có: hệ thống đưa việc dựng vào hàng đợi, trả về mã tác vụ và hiển thị tiến độ ngay tại chỗ.
4. Tiến trình nền đọc chuỗi điểm mốc của phiên, vẽ khung xương bàn tay lên từng khung hình rồi ghép thành video, và lưu bản dựng cạnh phiên thu. Tác vụ này có trần thử lại là hai lần, cách nhau mười lăm giây.
5. Hệ thống phát bản xem trước ngay trong trang, kèm thanh tua và số hiệu mẫu tương ứng với từng đoạn.

**Luồng luân phiên:**

1. **Bản dựng đã có sẵn:** ở bước 2, nếu bản dựng còn hạn, hệ thống bỏ qua bước 3–4 và phát ngay. Đây là đường đi thường gặp nhất sau lần xem đầu tiên.
2. **Dựng lại theo yêu cầu:** thành viên bấm "Dựng lại" khi nghi bản xem trước không khớp dữ liệu hiện tại — chẳng hạn sau khi xoá bớt mẫu trong phiên. Hệ thống bỏ bản cũ và chạy lại từ bước 3.

**Luồng ngoại lệ:**

1. **Dựng bản xem trước thất bại.** Ở bước 4, sau hai lần thử lại mà vẫn hỏng, tác vụ dừng ở trạng thái thất bại và hệ thống hiển thị lý do kèm nút dựng lại thủ công. **Các mẫu không bị ảnh hưởng**: bản xem trước là sản phẩm phụ dựng lại được bất cứ lúc nào, nên hỏng bản xem trước không bao giờ được phép làm hỏng dữ liệu gốc. Thành viên vẫn đánh giá được phiên thu qua các chỉ số chất lượng ở UC207.

2. **Bản xem trước quá hạn giữ.** Ở bước 2, bản dựng cũ hơn thời hạn giữ bị coi như không có và hệ thống dựng bản mới. Cơ chế hết hạn tồn tại để bản xem trước không tích tụ chiếm chỗ ổ đĩa — chúng là dữ liệu dựng lại được, khác với tệp đặc trưng.

3. **Hai bàn tay chồng lên nhau trong khung hình.** Ở bước 5, bản xem trước vẽ hai bàn tay bằng hai nét phân biệt. Khi hai tay chồng nhau tới mức bộ theo vết không tách được, đoạn đó được **đánh dấu** trên thanh tua thay vì dựng nhập hai tay thành một. Việc đánh dấu là cần thiết vì mẫu bị nhập tay là loại lỗi nhìn bản xem trước không ra, và người dùng cần biết chỗ nào đáng ngờ để quyết định thu lại.

4. **Phiên thu không còn mẫu nào.** Ở bước 3, nếu toàn bộ mẫu trong phiên đã bị xoá, hệ thống không đưa việc vào hàng đợi mà báo ngay rằng không còn gì để dựng, và gợi ý xem thùng rác nếu người dùng cho rằng dữ liệu bị xoá nhầm (UC212).

**Kết quả mong đợi:** Phiên thu có một bản dựng xem trước phát được trong trang, khớp với dữ liệu điểm mốc hiện tại của phiên, và các đoạn hai bàn tay chồng nhau được đánh dấu trên thanh tua. Khi dựng thất bại, dữ liệu mẫu không bị ảnh hưởng và người dùng vẫn đánh giá được phiên thu qua các chỉ số chất lượng.

---

#### UC209 — Xoá phiên thu

*Bảng C-22: Mô tả chức năng Xoá phiên thu*

| **Tên use case** | Xoá phiên thu | **ID** | UC209 |
|---|---|---|---|
| **Actor chính** | Thành viên tổ chức | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Thành viên tổ chức | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 2 — Thu thập và quản lý dữ liệu mẫu |

**Các thành phần tham gia và mối quan tâm:**

- **Thành viên tổ chức** — bỏ được cả buổi thu hỏng mà không phải xoá từng mẫu.
- **Người ký** — dữ liệu chỉ rời khỏi tập làm việc, tệp vẫn còn cho tới khi thùng rác được dọn.
- **Bộ phận kiểm toán** — mọi lượt xoá đều ghi lại người thực hiện và thời điểm.

**Mô tả tóm tắt:** *Thành viên tổ chức gỡ bỏ trọn một phiên thu không dùng được. Việc xoá là xoá mềm: các mẫu rời khỏi tập làm việc nhưng tệp vẫn được giữ cho tới khi thùng rác bị dọn sạch.*

**Các mối quan hệ:**

- **Association (kết hợp):** Thành viên tổ chức – Xoá phiên thu
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** *Gỡ bỏ dữ liệu* (trừu tượng)

**Xử lý sự kiện:**

1. Thành viên mở một phiên thu và bấm "Xoá phiên".
2. Hệ thống hiển thị số mẫu trong phiên, người ký và ngày thu, kèm cảnh báo rằng các mẫu sẽ rời khỏi tập làm việc nhưng vẫn khôi phục được từ thùng rác.
3. Thành viên xác nhận.
4. Hệ thống kiểm người gọi là chủ sở hữu phiên thu, hoặc có vai biên tập trên tổ chức sở hữu phiên.
5. Hệ thống ghi mốc thời gian xoá và định danh người thực hiện lên **mọi** mẫu của phiên, đồng thời ở danh bạ nguồn sự thật và ở bản soi trong cơ sở dữ liệu.
6. Hệ thống chuyển phiên vào thùng rác của tài khoản và ghi một mục vào nhật ký kiểm toán gồm phiên, số mẫu, người thực hiện và thời điểm.
7. Hệ thống quay lại trang chi tiết lớp; phiên đã biến khỏi danh sách và số đếm của lớp giảm tương ứng.

**Luồng luân phiên:**

1. **Xoá nhiều phiên cùng lúc:** thành viên chọn nhiều phiên trong danh sách rồi xoá theo lô. Các bước kiểm quyền và ghi dấu lặp lại cho từng phiên; nếu một phiên bị từ chối vì thiếu quyền, các phiên còn lại vẫn được xử lý và báo cáo cuối liệt kê phần bị bỏ qua.

**Luồng ngoại lệ:**

1. **Người gọi không phải chủ sở hữu và không có vai biên tập.** Ở bước 4, hệ thống từ chối và không thay đổi gì. Một thành viên không xoá được phiên thu do người khác ghi, kể cả khi hai người cùng tổ chức — vì phiên thu mang dữ liệu của một người ký cụ thể và người chịu trách nhiệm về nó là người đã thu. Thành viên cần xoá dữ liệu của người khác thì nhờ biên tập viên hoặc quản trị tổ chức.

2. **Phiên đã bị xoá từ trước.** Ở bước 5, nếu các mẫu đã mang mốc thời gian xoá, hệ thống báo thành công mà **không** ghi đè mốc cũ. Nhờ vậy một cú bấm lặp lại — hoặc hai tab cùng gửi lệnh — là vô hại và không làm sai lệch thời điểm xoá đã ghi trong kiểm toán. Đây là tính chất bắt buộc với mọi thao tác xoá trong hệ thống này.

3. **Ghi dấu xoá thành công ở một nơi và thất bại ở nơi kia.** Ở bước 5, nếu danh bạ đã ghi dấu nhưng bản soi cơ sở dữ liệu chưa, hoặc ngược lại, hệ thống báo lỗi nêu rõ tình trạng lệch thay vì báo thành công. Phiên có thể hiện ra ở màn hình này mà biến mất ở màn hình kia cho tới khi tác vụ đối soát chạy và lấy danh bạ làm chuẩn (UC703). Thành viên không cần làm gì thêm ngoài việc đợi lượt đối soát kế tiếp.

4. **Phiên đang được một tác vụ khác dùng.** Ở bước 5, nếu một tác vụ dựng xem trước hoặc một lượt xuất dữ liệu đang đọc phiên này, thao tác xoá mềm vẫn thực hiện được vì nó chỉ ghi thêm một mốc thời gian chứ không đụng tới tệp. Tác vụ đang chạy hoàn tất với dữ liệu nó đã đọc. Đây là ưu điểm trực tiếp của việc xoá mềm: không có tranh chấp khoá và không có tệp biến mất giữa chừng.

**Kết quả mong đợi:** Toàn bộ mẫu của phiên mang mốc thời gian xoá và định danh người thực hiện ở cả danh bạ lẫn cơ sở dữ liệu; phiên biến khỏi tập làm việc, xuất hiện trong thùng rác, và số đếm của lớp giảm tương ứng. Tệp không bị đụng tới, nên thao tác này hoàn tác được cho tới khi thùng rác bị dọn.

---

#### UC210 — Gán lại người ký của phiên thu

*Bảng C-23: Mô tả chức năng Gán lại người ký của phiên thu*

| **Tên use case** | Gán lại người ký của phiên thu | **ID** | UC210 |
|---|---|---|---|
| **Actor chính** | Biên tập viên / Nghiên cứu sinh | **Mức độ cần thiết** | Tuỳ chọn |
| **Kích hoạt bởi** | Biên tập viên | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 2 — Thu thập và quản lý dữ liệu mẫu |

**Các thành phần tham gia và mối quan tâm:**

- **Biên tập viên** — sửa được sai sót quy kết mà không phải thu lại dữ liệu.
- **Người ký thật** — được ghi nhận đúng là chủ thể dữ liệu, và mức đồng thuận của họ áp đúng cho mẫu.
- **Bộ phận kiểm toán** — cả người ký cũ lẫn người ký mới đều được ghi lại.

**Mô tả tóm tắt:** *Biên tập viên sửa lại người ký gắn với một phiên thu khi bản ghi bị đăng ký nhầm sang người khác.*

**Các mối quan hệ:**

- **Association (kết hợp):** Biên tập viên / Nghiên cứu sinh – Gán lại người ký của phiên thu
- **Include (bao gồm):** không
- **Extend (mở rộng):** UC207 Xem chi tiết lớp
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Biên tập viên mở một phiên thu và bấm "Gán lại".
2. Hệ thống hiển thị người ký hiện tại kèm ô tìm kiếm trong danh sách người ký của tổ chức.
3. Biên tập viên chọn đúng người ký, nhập lý do sửa và xác nhận.
4. Hệ thống kiểm người gọi có vai biên tập trên tổ chức sở hữu phiên thu.
5. Hệ thống ghi lại người ký trên **mọi** mẫu của phiên, đồng thời ở danh bạ nguồn sự thật và ở bản soi cơ sở dữ liệu, giữ nguyên mọi trường khác của mẫu.
6. Hệ thống ghi một mục kiểm toán lưu cả người ký cũ, người ký mới, lý do và người thực hiện.
7. Hệ thống hiển thị lại phiên thu với người ký đã sửa.

**Luồng luân phiên:**

1. **Gán cho một người ký chưa có hồ sơ:** biên tập viên tạo hồ sơ người ký mới ngay trong ô tìm kiếm ở bước 2 rồi chọn hồ sơ vừa tạo. Hồ sơ người ký là một bản ghi mô tả chủ thể dữ liệu, không nhất thiết gắn với một tài khoản đăng nhập.

**Luồng ngoại lệ:**

1. **Người gọi không đủ vai.** Ở bước 4, hệ thống từ chối và không sửa gì. Gán lại người ký làm thay đổi **nguồn gốc dữ liệu** — nó quyết định mẫu này thuộc về ai và chịu mức đồng thuận nào — nên nó không thuộc quyền của thành viên thường, kể cả người đã thu chính phiên đó. Thành viên phát hiện sai sót thì báo cho biên tập viên của tổ chức.

2. **Người ký mới có mức đồng thuận hẹp hơn.** Ở bước 5, hệ thống áp mức hẹp hơn cho các mẫu của phiên kể từ thời điểm gán lại, và cảnh báo trước cho biên tập viên biết số mẫu sẽ rời khỏi phạm vi phát hành nào. Đây là hệ quả bắt buộc: đồng thuận đi theo người ký chứ không đi theo mẫu, nên sửa người ký là sửa cả cơ sở pháp lý của mẫu. Nếu người ký mới chưa từng cho đồng thuận nào, các mẫu này không phát hành được ở bất kỳ mức nào cho tới khi có đồng thuận.

3. **Ghi lệch giữa danh bạ và cơ sở dữ liệu.** Ở bước 5, nếu một trong hai nơi ghi thành công còn nơi kia thất bại, hệ thống báo lỗi nêu rõ phần chưa ghi. Tác vụ đối soát dựng lại bản soi từ danh bạ thay vì để hai phiên bản sự thật cùng tồn tại (UC703). Trong khoảng thời gian lệch, các màn hình đọc từ cơ sở dữ liệu vẫn hiển thị người ký cũ.

4. **Phiên thu đã bị xoá mềm.** Ở bước 1, phiên nằm trong thùng rác không gán lại được. Biên tập viên phải khôi phục phiên trước (UC212) rồi mới sửa. Ràng buộc này tránh việc sửa nguồn gốc của dữ liệu đang chờ bị xoá vĩnh viễn, một thao tác không có ý nghĩa nghiệp vụ nào.

**Kết quả mong đợi:** Mọi mẫu của phiên quy về đúng người ký thật, đồng bộ ở cả danh bạ lẫn cơ sở dữ liệu, và mức đồng thuận áp cho các mẫu này là mức của người ký mới. Nhật ký kiểm toán lưu cả người ký cũ, người ký mới và lý do sửa, nên nguồn gốc dữ liệu vẫn truy ngược được sau khi sửa.

---

#### UC211 — Xoá mẫu

*Bảng C-24: Mô tả chức năng Xoá mẫu*

| **Tên use case** | Xoá mẫu | **ID** | UC211 |
|---|---|---|---|
| **Actor chính** | Thành viên tổ chức | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Thành viên tổ chức | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 2 — Thu thập và quản lý dữ liệu mẫu |

**Các thành phần tham gia và mối quan tâm:**

- **Thành viên tổ chức** — loại được mẫu hỏng khỏi tập làm việc.
- **Người ký** — thao tác này hoàn tác được cho tới khi thùng rác bị dọn.
- **Nghiên cứu sinh** — số đếm của lớp phản ánh đúng số mẫu còn dùng được.

**Mô tả tóm tắt:** *Thành viên tổ chức gỡ một mẫu đơn lẻ khỏi tập làm việc. Cũng như với phiên thu, việc xoá là xoá mềm và hoàn tác được cho tới khi thùng rác bị dọn sạch.*

**Các mối quan hệ:**

- **Association (kết hợp):** Thành viên tổ chức – Xoá mẫu
- **Include (bao gồm):** không
- **Extend (mở rộng):** không *(UC212 mở rộng use case này)*
- **Generalization (tổng quát hoá):** *Gỡ bỏ dữ liệu* (trừu tượng)

**Xử lý sự kiện:**

1. Thành viên mở danh sách mẫu của một phiên thu và bấm "Xoá" trên một mẫu.
2. Hệ thống hiển thị mã mẫu, lớp, chỉ số chất lượng và hỏi xác nhận.
3. Thành viên xác nhận.
4. Hệ thống kiểm người gọi là chủ sở hữu mẫu hoặc có vai biên tập trên tổ chức.
5. Hệ thống ghi mốc thời gian xoá và định danh người thực hiện lên dòng dữ liệu, đồng thời ở danh bạ và ở cơ sở dữ liệu. Tệp đặc trưng **không** bị đụng tới.
6. Hệ thống loại mẫu khỏi các số đếm hiển thị cho lớp, đưa mẫu vào thùng rác và ghi một mục vào nhật ký kiểm toán.

**Luồng luân phiên:**

1. **Xoá nhiều mẫu cùng lúc:** thành viên chọn nhiều mẫu rồi xoá theo lô; các bước 4–6 lặp cho từng mẫu và báo cáo cuối liệt kê những mẫu bị bỏ qua vì thiếu quyền.
2. **Xoá cả phiên thay vì từng mẫu:** khi phần lớn mẫu trong phiên đều hỏng, thao tác đúng là xoá cả phiên (UC209) — cùng một cơ chế xoá mềm nhưng một lần bấm và một mục kiểm toán.

**Luồng ngoại lệ:**

1. **Người gọi không phải chủ sở hữu.** Ở bước 4, hệ thống từ chối và giữ nguyên mẫu, theo cùng nguyên tắc đã nêu ở UC209.

2. **Mẫu đã bị xoá trước đó.** Ở bước 5, hệ thống báo thành công mà không ghi lần thứ hai và không đổi mốc thời gian đã có. Thao tác xoá là bất biến theo số lần gọi, nên hai tab cùng bấm hoặc một lần bấm lặp đều cho cùng kết quả.

3. **Mẫu vừa bị xoá là mẫu cuối cùng của lớp.** Ở bước 6, hệ thống giữ nguyên lớp trong danh mục với số đếm bằng không, không tự xoá lớp. Lý do: một lớp là một **mục trong danh mục từ vựng**, tồn tại độc lập với việc đã thu được mẫu nào hay chưa; tự xoá lớp khi hết mẫu sẽ làm biến mất chính mục tiêu thu mà tổ chức đã đặt ra. Muốn bỏ lớp thì dùng UC304.

4. **Mẫu đang nằm trong một tập huấn luyện đang chạy.** Ở bước 5, việc xoá mềm không dừng lượt huấn luyện đang chạy, vì lượt đó đã đọc dữ liệu vào từ đầu. Mô hình sinh ra vẫn ghi trong phần nguồn gốc là đã dùng mẫu này, và mẫu đã xoá vẫn truy được trong thùng rác — nhờ vậy bản ghi nguồn gốc của mô hình không trỏ vào hư không. Lượt huấn luyện kế tiếp sẽ không còn mẫu này.

**Kết quả mong đợi:** Mẫu mang mốc thời gian xoá ở cả hai nơi lưu, biến khỏi số đếm của lớp và nằm trong thùng rác; tệp đặc trưng vẫn còn. Lớp giữ nguyên trong danh mục kể cả khi số mẫu về không, và một lần bấm lặp lại không làm thay đổi mốc thời gian đã ghi.

---

#### UC212 — Quản lý thùng rác

*Bảng C-25: Mô tả chức năng Quản lý thùng rác*

| **Tên use case** | Quản lý thùng rác | **ID** | UC212 |
|---|---|---|---|
| **Actor chính** | Thành viên tổ chức | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Thành viên tổ chức | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 2 — Thu thập và quản lý dữ liệu mẫu |

**Các thành phần tham gia và mối quan tâm:**

- **Thành viên tổ chức** — hoàn tác được thao tác xoá nhầm.
- **Tổ chức** — giải phóng được dung lượng khi thật sự muốn xoá hẳn.
- **Kho lưu trữ ngoài (S2)** — chỉ ở bước xoá vĩnh viễn mới nhận lệnh xoá tệp.

**Mô tả tóm tắt:** *Thành viên tổ chức xem lại những gì mình đã xoá và chọn khôi phục về tập làm việc hoặc xoá vĩnh viễn. Xoá vĩnh viễn là bước duy nhất chạm tới tệp đã lưu.*

**Các mối quan hệ:**

- **Association (kết hợp):** Thành viên tổ chức – Quản lý thùng rác; Kho lưu trữ ngoài (S2)
- **Include (bao gồm):** không
- **Extend (mở rộng):** UC211 Xoá mẫu; UC304 Gỡ lớp khỏi danh mục
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Thành viên mở trang thùng rác. Hệ thống liệt kê các mẫu, phiên thu và lớp mà **chính tài khoản đó** đã xoá, kèm ngày xoá và loại đối tượng.
2. Thành viên chọn một hoặc nhiều mục.
3. Thành viên bấm "Khôi phục".
4. Hệ thống xoá mốc thời gian xoá trên các dòng tương ứng, đồng thời ở danh bạ và ở cơ sở dữ liệu, và trả các mục về tập làm việc.
5. Hệ thống cập nhật lại số đếm của các lớp liên quan và ghi một mục vào nhật ký kiểm toán.

**Luồng luân phiên:**

1. **Xoá vĩnh viễn thay vì khôi phục:** ở bước 3, thành viên bấm "Xoá vĩnh viễn". Hệ thống cảnh báo thao tác không hoàn tác được và yêu cầu xác nhận lần thứ hai, rồi xoá dòng ở danh bạ, xoá dòng ở cơ sở dữ liệu, và **chuyển lệnh xoá tệp cho một tác vụ nền có thử lại**. Thứ tự này — xoá bản ghi trước, xoá tệp sau — được chọn có cân nhắc và hệ quả của nó nêu ở ngoại lệ 1.
2. **Dọn theo lịch:** với dữ liệu của cả một tổ chức đã ngừng dịch vụ, việc dọn không đi qua màn hình này mà theo cơ chế ân hạn rồi xoá của vòng đời tổ chức (UC508).

**Luồng ngoại lệ:**

1. **Xoá tệp thất bại ở nhánh xoá vĩnh viễn.** Các dòng dữ liệu đã biến mất trước khi lệnh xoá tệp chạy, nên một lần thất bại vĩnh viễn để lại **tệp mồ côi** trong kho chứ không để lại mẫu dở dang trong danh bạ. Đây là đánh đổi có chủ ý: một tệp thừa chiếm chỗ ổ đĩa là vấn đề dọn dẹp, còn một dòng mẫu trỏ tới tệp đã mất là vấn đề đúng đắn dữ liệu, và vấn đề thứ hai nặng hơn hẳn. Tệp mồ côi được báo cáo đối soát định kỳ liệt kê để kỹ sư vận hành dọn (UC703).

2. **Khôi phục một mẫu mà lớp cha đã bị xoá vĩnh viễn.** Ở bước 4, hệ thống từ chối và giải thích rằng phải khôi phục hoặc tạo lại lớp trước. Nếu cho phép, hệ thống sẽ có những mẫu trỏ tới một lớp không tồn tại — trạng thái làm hỏng mọi số đếm và mọi lượt xuất dữ liệu. Thành viên tạo lại lớp với đúng năm thuộc tính định danh (UC301) rồi khôi phục lại.

3. **Phạm vi nhìn thấy của thùng rác.** Ở bước 1, thành viên chỉ thấy những gì chính mình đã xoá. Biên tập viên và quản trị tổ chức thấy phạm vi rộng hơn trong tổ chức của họ. Hệ quả cần biết: một mẫu do người khác xoá sẽ không xuất hiện trong thùng rác của bạn dù bạn là người đã thu nó; trong trường hợp đó phải nhờ biên tập viên khôi phục.

4. **Thùng rác trống nhưng dữ liệu vẫn thiếu.** Ở bước 1, nếu người dùng không tìm thấy mục đã xoá, khả năng còn lại là thùng rác đã được dọn — dữ liệu khi đó đã bị xoá vĩnh viễn và **không** khôi phục được từ trong hệ thống. Đường duy nhất còn lại là bản sao lưu định kỳ, và việc khôi phục từ bản sao lưu là thao tác của kỹ sư vận hành ở quy mô toàn cơ sở dữ liệu (UC705), không phải một thao tác cho từng mẫu. Điều này cần được nói rõ với người dùng ngay trên màn hình cảnh báo ở nhánh xoá vĩnh viễn.

**Kết quả mong đợi:** Các mục được khôi phục trở lại tập làm việc với số đếm của lớp cập nhật đúng; các mục bị xoá vĩnh viễn biến mất khỏi cả danh bạ lẫn cơ sở dữ liệu và lệnh xoá tệp đã được giao cho tác vụ nền. Sau nhánh xoá vĩnh viễn, trạng thái xấu nhất có thể để lại là một tệp mồ côi trong kho — không bao giờ là một dòng dữ liệu trỏ tới tệp đã mất.

---

#### UC213 — Xuất ảnh chụp bộ dữ liệu

*Bảng C-26: Mô tả chức năng Xuất ảnh chụp bộ dữ liệu*

| **Tên use case** | Xuất ảnh chụp bộ dữ liệu | **ID** | UC213 |
|---|---|---|---|
| **Actor chính** | Biên tập viên / Nghiên cứu sinh | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Nghiên cứu sinh chạy công cụ dòng lệnh | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 2 — Thu thập và quản lý dữ liệu mẫu |

**Các thành phần tham gia và mối quan tâm:**

- **Nghiên cứu sinh** — có một ảnh chụp bộ dữ liệu tái lập được để huấn luyện và công bố.
- **Người ký** — chỉ mẫu có đồng thuận phù hợp mới lọt vào ảnh chụp.
- **Kỹ sư vận hành** — công cụ chạy trên máy triển khai nên cần quyền hệ điều hành.

**Mô tả tóm tắt:** *Nghiên cứu sinh dựng một ảnh chụp bộ dữ liệu sẵn sàng cho huấn luyện, từ danh bạ nguồn sự thật, bằng công cụ dòng lệnh trên máy triển khai. Chỉ những mẫu có đồng thuận cho phép mức phát hành được yêu cầu mới được đưa vào.*

> **Ranh giới hiện thực:** use case này chạy bằng **công cụ dòng lệnh**, không phải bằng một màn hình. Bộ định tuyến xuất dữ liệu qua giao diện web vẫn nằm trong mã nguồn nhưng **không được gắn** vào ứng dụng, nên không đường dẫn nào chạm tới. Đường xuất **dữ liệu của một tổ chức** qua giao diện là UC507, một use case khác.

**Các mối quan hệ:**

- **Association (kết hợp):** Biên tập viên / Nghiên cứu sinh – Xuất ảnh chụp bộ dữ liệu
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Nghiên cứu sinh chạy công cụ xuất dữ liệu trên máy triển khai, nêu ngôn ngữ, danh sách phương ngữ, mức phát hành cần dùng và thư mục đích.
2. Hệ thống đọc danh bạ nguồn sự thật và báo cáo trước khi làm gì: số mẫu đủ điều kiện, số mẫu bị loại vì đồng thuận, số mẫu bị loại vì đã xoá, và phân bố mẫu theo lớp.
3. Nghiên cứu sinh xem báo cáo và xác nhận thực hiện.
4. Hệ thống đối chiếu từng dòng với trạng thái đồng thuận hiện hành của người ký và với trạng thái xoá của mẫu. Việc đối chiếu diễn ra tại thời điểm xuất chứ không dựa vào một dấu đã đánh sẵn trên mẫu.
5. Hệ thống nạp tệp đặc trưng, dựng ma trận đặc trưng cùng bảng chỉ mục nhãn, và ghi một bản kê khai liệt kê chính xác những dòng đã đưa vào, kèm cấu hình đã dùng.
6. Hệ thống báo cáo tổng kết: số mẫu, số lớp, số dòng bị loại theo từng lý do, và mã bản kê khai để đối chiếu về sau.

**Luồng luân phiên:**

1. **Chạy thử không ghi tệp:** nghiên cứu sinh chạy công cụ ở chế độ chỉ báo cáo; các bước 1–2 diễn ra bình thường rồi dừng, không ghi tệp nào. Đây là cách kiểm tra bộ lọc trước khi tiêu tài nguyên dựng ma trận.
2. **Bật tuỳ chọn tự sửa kích thước:** khi biết trước bộ dữ liệu có lẫn tệp từ các phiên bản cấu hình cũ, nghiên cứu sinh bật tuỳ chọn tự đệm hoặc cắt về đúng độ dài cửa sổ; mọi lần sửa đều được ghi vào bản kê khai ở bước 5.

**Luồng ngoại lệ:**

1. **Tệp đặc trưng sai độ dài cửa sổ.** Ở bước 5, nếu một tệp không đúng độ dài quy định — thường do được sinh dưới một cấu hình cũ — hệ thống dừng và báo đích danh tệp đó khi tuỳ chọn tự sửa đang tắt. Khi tuỳ chọn bật, hệ thống đệm hoặc cắt bớt và **ghi việc sửa vào bản kê khai**, để người đọc kết quả biết được bao nhiêu phần dữ liệu đã bị can thiệp. Việc âm thầm sửa mà không ghi lại là điều bị loại bỏ có chủ ý, vì nó làm hỏng khả năng tái lập của số liệu công bố.

2. **Đồng thuận đã bị rút.** Ở bước 4, mẫu có đồng thuận đã rút bị loại, kể cả khi mẫu đó từng có mặt trong một ảnh chụp xuất trước đây. Đây là điểm mấu chốt của cơ chế rút đồng thuận (UC113): việc rút chỉ có hiệu lực thật khi bộ lọc được áp lại ở **mỗi** lần xuất, chứ không phải một lần lúc thu mẫu.

3. **Mẫu không ghi nhận mức phát hành nào.** Ở bước 4, mẫu của người ký chưa từng chọn mức phát hành bị loại khỏi **mọi** mức, kể cả mức hẹp nhất. Hệ thống chọn cách mặc định đóng thay vì mặc định mở, vì một mẫu không rõ được phép dùng tới đâu là một mẫu không được phép phát hành. Cách khắc phục là người ký chọn mức phát hành (UC112) rồi chạy lại lượt xuất.

4. **Tệp nằm trên kho lưu trữ ngoài.** Ở bước 5, dòng dữ liệu chỉ có khoá lưu trữ mà không có bản cục bộ sẽ được nạp về vùng đệm trước khi dựng ma trận, để phần xuất dữ liệu chỉ có một đường mã chung cho cả tệp cục bộ lẫn tệp từ xa. Nếu kho lưu trữ không phản hồi, lượt xuất dừng với danh sách các tệp chưa nạp được; nghiên cứu sinh chạy lại sau, và những tệp đã nạp về vùng đệm không phải tải lại.

5. **Không có mẫu nào đủ điều kiện.** Ở bước 6, hệ thống báo rằng ảnh chụp rỗng và **không** ghi ra thư mục kết quả. Một kho lưu trữ rỗng nhưng có cấu trúc hợp lệ là thứ nguy hiểm hơn một lỗi rõ ràng, vì nó sẽ được đưa vào một lượt huấn luyện và chỉ lộ ra ở bước cuối. Nghiên cứu sinh nới điều kiện lọc hoặc kiểm lại mức phát hành đã yêu cầu.

**Kết quả mong đợi:** Tồn tại một ảnh chụp bộ dữ liệu gồm ma trận đặc trưng, bảng chỉ mục nhãn và một bản kê khai liệt kê chính xác các dòng đã đưa vào cùng cấu hình đã dùng, nên lượt xuất tái lập được. Mọi mẫu không đủ điều kiện đồng thuận đều bị loại và được đếm theo từng lý do; nếu không mẫu nào đủ điều kiện, hệ thống báo rỗng và không ghi ra thư mục kết quả.

---

### 5.3 Nghiệp vụ 3 — Danh mục từ vựng và phương ngữ

#### UC302 — Cập nhật lớp

*Bảng C-27: Mô tả chức năng Cập nhật lớp*

| **Tên use case** | Cập nhật lớp | **ID** | UC302 |
|---|---|---|---|
| **Actor chính** | Biên tập viên / Nghiên cứu sinh | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Biên tập viên | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 3 — Danh mục từ vựng và phương ngữ |

**Các thành phần tham gia và mối quan tâm:**

- **Biên tập viên** — sửa được sai sót trong danh mục mà không phải xoá và tạo lại lớp.
- **Nghiên cứu sinh** — chỉ số lớp phải giữ nguyên, vì mô hình đã huấn luyện tham chiếu nhãn theo vị trí.
- **Thành viên đang thu mẫu** — biết yêu cầu thu của lớp đã thay đổi.

**Mô tả tóm tắt:** *Biên tập viên sửa thông tin của một lớp đã có: tên nhãn, yêu cầu thu hoặc mục tiêu số mẫu.*

**Các mối quan hệ:**

- **Association (kết hợp):** Biên tập viên / Nghiên cứu sinh – Cập nhật lớp
- **Include (bao gồm):** không
- **Extend (mở rộng):** không *(UC303 mở rộng use case này)*
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Biên tập viên mở một lớp và bấm "Sửa".
2. Hệ thống hiển thị thông tin hiện tại của lớp — tên nhãn, ngôn ngữ, phương ngữ, vùng, số bàn tay yêu cầu, mục tiêu số mẫu — cùng số mẫu đã thu được, để người sửa nhìn thấy hệ quả trước khi đổi.
3. Biên tập viên thay đổi các trường cần sửa và xác nhận.
4. Hệ thống kiểm người gọi có vai biên tập trên tổ chức sở hữu lớp, và kiểm hạn mức tần suất ghi vào danh mục.
5. Hệ thống kiểm tên nhãn mới không trùng với một lớp đang hoạt động khác trong cùng phạm vi định danh — cùng ngôn ngữ, phương ngữ và vùng.
6. Hệ thống lưu thay đổi, **giữ nguyên** mã định danh và chỉ số lớp, rồi ghi một mục vào nhật ký kiểm toán gồm giá trị cũ và giá trị mới của từng trường đã đổi.
7. Hệ thống hiển thị lớp đã cập nhật.

**Luồng luân phiên:**

1. **Chỉ sửa mục tiêu số mẫu:** đây là thay đổi thường gặp nhất và không kéo theo hệ quả nào lên dữ liệu đã thu; các bước 4–6 vẫn chạy đủ nhưng cảnh báo ở bước 3 không xuất hiện.
2. **Thực ra cần gộp lớp:** ở bước 3, nếu biên tập viên đang đổi tên lớp thành tên của một lớp đã có, hệ thống nhận ra ý định và đề nghị dùng thao tác gộp (UC303) thay vì đổi tên — vì đổi tên chỉ làm hai mục trùng nhau chứ không nhập được dữ liệu.

**Luồng ngoại lệ:**

1. **Tên nhãn mới trùng lớp đang hoạt động.** Ở bước 5, hệ thống từ chối và nêu đích danh lớp đang giữ tên đó kèm số mẫu của nó, để biên tập viên quyết định được nên đổi tên khác hay nên gộp hai lớp. Không thay đổi nào được lưu, kể cả các trường không xung đột trong cùng lần gửi. Cần lưu ý phạm vi kiểm trùng là **cả năm thuộc tính định danh**: hai lớp cùng tên nhưng khác vùng là hai lớp hợp lệ, không phải trùng lặp — vùng là một phần của danh tính lớp chứ không phải một nhãn mô tả.

2. **Yêu cầu đổi chỉ số lớp.** Ở bước 6, chỉ số lớp **không bao giờ** được gán lại bởi một lượt sửa, và giao diện không có ô nào cho phép nhập nó. Lý do phải nói rõ vì nó là loại lỗi im lặng nguy hiểm nhất trong hệ thống này: mô hình đã huấn luyện lưu nhãn theo **vị trí** trong bảng chỉ mục, nên đổi chỉ số của một lớp sẽ khiến mọi dự đoán của mọi mô hình cũ trỏ sang nhãn khác mà không có thông báo lỗi nào, không có bản ghi nào sai định dạng, và không ai phát hiện ra cho tới khi đối chiếu thủ công. Biên tập viên muốn thay đổi cấu trúc nhãn thì huấn luyện lại mô hình (UC401).

3. **Đổi số bàn tay yêu cầu khi lớp đã có mẫu.** Ở bước 3, hệ thống cảnh báo rằng các mẫu đã thu được đánh giá theo yêu cầu **tại thời điểm thu**, nên chỉ số chất lượng của chúng không được tính lại theo yêu cầu mới. Hệ quả cụ thể: một lớp đổi từ một tay sang hai tay sẽ có các mẫu cũ trông như đạt yêu cầu trong khi thực chất chúng chỉ ghi một tay. Cách xử lý đúng thường là tạo một lớp mới thay vì sửa lớp cũ, và biên tập viên được nhắc điều đó ngay trên cảnh báo.

4. **Chạm hạn mức tần suất ghi danh mục.** Ở bước 4, nếu tài khoản đã thực hiện quá nhiều thao tác ghi danh mục trong cửa sổ thời gian, hệ thống từ chối kèm thời gian chờ. Hạn mức này tồn tại vì danh mục là dữ liệu dùng chung cho cả tổ chức và một kịch bản tự động sửa hàng loạt có thể làm hỏng nó nhanh hơn mức con người kịp nhận ra. Biên tập viên chờ hết cửa sổ; với các đợt sửa lớn có kế hoạch, đường đúng là làm theo lô qua công cụ quản trị chứ không bấm liên tục trên giao diện.

5. **Người gọi không có vai biên tập.** Ở bước 4, hệ thống từ chối. Danh mục quyết định dữ liệu của cả tổ chức được gán nhãn thế nào, nên quyền ghi vào nó hẹp hơn quyền thu mẫu. Thành viên thường phát hiện sai sót thì báo cho biên tập viên.

**Kết quả mong đợi:** Lớp mang thông tin đã sửa trong khi mã định danh và chỉ số lớp giữ nguyên, nên các mô hình đã huấn luyện vẫn tra đúng nhãn. Nhật ký kiểm toán lưu giá trị cũ và giá trị mới của từng trường; khi tên nhãn xung đột, không thay đổi nào được lưu, kể cả các trường không xung đột trong cùng lần gửi.

---

#### UC303 — Gộp hai lớp

*Bảng C-28: Mô tả chức năng Gộp hai lớp*

| **Tên use case** | Gộp hai lớp | **ID** | UC303 |
|---|---|---|---|
| **Actor chính** | Biên tập viên / Nghiên cứu sinh | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Biên tập viên | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 3 — Danh mục từ vựng và phương ngữ |

**Các thành phần tham gia và mối quan tâm:**

- **Biên tập viên** — dọn được danh mục khi phát hiện hai mục cùng chỉ một ký hiệu.
- **Người đóng góp** — mẫu đã thu chuyển sang lớp đích chứ không mất đi.
- **Nghiên cứu sinh** — chỉ số lớp nguồn được cho nghỉ hẳn, không tái sử dụng.

**Mô tả tóm tắt:** *Biên tập viên nhập một lớp vào một lớp khác khi danh mục có hai mục cùng chỉ một ký hiệu. Mẫu của lớp nguồn chuyển sang lớp đích thay vì bị mất.*

**Các mối quan hệ:**

- **Association (kết hợp):** Biên tập viên / Nghiên cứu sinh – Gộp hai lớp
- **Include (bao gồm):** không
- **Extend (mở rộng):** UC302 Cập nhật lớp
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Biên tập viên mở lớp nguồn và chọn "Gộp vào lớp khác".
2. Biên tập viên chọn lớp đích trong danh sách các lớp cùng ngôn ngữ và cùng phương ngữ.
3. Hệ thống hiển thị bảng đối chiếu hai lớp: tên, vùng, số bàn tay yêu cầu, số mẫu của mỗi bên, và số mẫu sẽ chuyển; kèm cảnh báo rằng lớp nguồn sẽ biến khỏi danh mục.
4. Biên tập viên xác nhận.
5. Hệ thống chuyển toàn bộ mẫu của lớp nguồn sang lớp đích — đổi tham chiếu lớp trên từng dòng mẫu, đồng thời ở danh bạ nguồn sự thật và ở bản soi cơ sở dữ liệu — trong một giao dịch duy nhất.
6. Hệ thống cho lớp nguồn nghỉ, giữ lại bản ghi của nó ở trạng thái đã nghỉ chứ không xoá dòng, và ghi một mục kiểm toán nêu tên cả hai lớp cùng số mẫu đã chuyển.
7. Hệ thống hiển thị lớp đích với số mẫu đã cộng gộp.

**Luồng luân phiên:**

1. **Gộp nhiều lớp vào một:** biên tập viên lặp lại từ bước 1 cho từng lớp nguồn. Hệ thống không hỗ trợ chọn nhiều nguồn trong một lần, vì mỗi lần gộp cần một quyết định riêng về việc mẫu sẽ chịu yêu cầu thu nào sau khi gộp.

**Luồng ngoại lệ:**

1. **Hai lớp khác ngôn ngữ hoặc khác phương ngữ.** Ở bước 2, hệ thống không liệt kê các lớp thuộc ngôn ngữ hoặc phương ngữ khác, và từ chối nếu yêu cầu vẫn được gửi lên. Hai mục khác nhau ở hai trường đó **không phải** là bản trùng mà là hai ký hiệu khác nhau của hai cộng đồng khác nhau; gộp chúng sẽ trộn dữ liệu của hai phương ngữ thành một lớp và làm hỏng chính khả năng phân biệt phương ngữ mà bộ dữ liệu này được dựng để nghiên cứu. Nếu biên tập viên tin rằng hai phương ngữ thực chất là một, đường xử lý đúng là đề nghị quản trị nền tảng hợp nhất phương ngữ ở danh mục dùng chung (UC307).

2. **Chỉ số lớp của lớp nguồn.** Ở bước 6, chỉ số của lớp nguồn được cho **nghỉ vĩnh viễn** và không bao giờ được cấp lại cho một lớp khác. Nếu tái sử dụng, mọi mô hình huấn luyện trước thời điểm gộp sẽ tra bảng chỉ mục ra một nhãn khác hẳn — cùng loại lỗi im lặng đã nêu ở UC302. Đây là lý do bản ghi lớp nguồn được giữ ở trạng thái đã nghỉ thay vì bị xoá dòng: dòng đó chính là thứ giữ chỗ cho chỉ số đã dùng.

3. **Gộp một lớp vào chính nó.** Ở bước 2, hệ thống loại lớp nguồn khỏi danh sách chọn và từ chối yêu cầu nếu nó vẫn được gửi lên. Thao tác này không có ý nghĩa nghiệp vụ và nếu thực hiện sẽ cho lớp nghỉ ngay sau khi chuyển mẫu về chính nó, tức là làm mất cả lớp lẫn dữ liệu.

4. **Hai lớp có số bàn tay yêu cầu khác nhau.** Ở bước 3, hệ thống nêu rõ mẫu sau khi gộp sẽ được xét theo yêu cầu của **lớp đích**, và cho biết bao nhiêu mẫu chuyển sang sẽ không đạt yêu cầu mới. Biên tập viên cân nhắc rồi quyết định; nếu số mẫu không đạt quá lớn, cách đúng thường là giữ hai lớp riêng.

5. **Giao dịch chuyển mẫu thất bại giữa chừng.** Ở bước 5, nếu một phần mẫu đã đổi tham chiếu mà phần còn lại chưa, toàn bộ giao dịch bị hoàn tác và lớp nguồn **không** bị cho nghỉ. Hệ thống chọn hoàn tác toàn bộ thay vì giữ phần đã làm, vì trạng thái nửa gộp — một lớp đã nghỉ nhưng vẫn còn mẫu trỏ tới nó — là trạng thái không có màn hình nào hiển thị đúng được. Biên tập viên thử lại; nếu lỗi lặp lại, đây là sự cố cơ sở dữ liệu cần kỹ sư vận hành xem xét.

**Kết quả mong đợi:** Toàn bộ mẫu của lớp nguồn đã thuộc về lớp đích ở cả danh bạ lẫn cơ sở dữ liệu, lớp nguồn ở trạng thái đã nghỉ và chỉ số của nó bị giữ lại vĩnh viễn không cấp cho ai. Nếu giao dịch chuyển mẫu hỏng giữa chừng, mọi thứ trở về nguyên trạng và lớp nguồn vẫn hoạt động bình thường.

---

#### UC304 — Gỡ lớp khỏi danh mục

*Bảng C-29: Mô tả chức năng Gỡ lớp khỏi danh mục*

| **Tên use case** | Gỡ lớp khỏi danh mục | **ID** | UC304 |
|---|---|---|---|
| **Actor chính** | Biên tập viên / Nghiên cứu sinh | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Biên tập viên | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 3 — Danh mục từ vựng và phương ngữ |

**Các thành phần tham gia và mối quan tâm:**

- **Biên tập viên** — bỏ được lớp đăng ký nhầm.
- **Người đóng góp** — mẫu chỉ rời tập làm việc, còn khôi phục được.
- **Nghiên cứu sinh** — biết lớp nào đang được mô hình đã thăng hạng tham chiếu tới.

**Mô tả tóm tắt:** *Biên tập viên gỡ một lớp khỏi danh mục. Thao tác trước hết là xoá mềm; việc xoá vĩnh viễn, kèm theo cả mẫu và tệp, là một bước riêng và không hoàn tác được.*

**Các mối quan hệ:**

- **Association (kết hợp):** Biên tập viên / Nghiên cứu sinh – Gỡ lớp khỏi danh mục; Kho lưu trữ ngoài (S2)
- **Include (bao gồm):** không
- **Extend (mở rộng):** không *(UC212 mở rộng use case này)*
- **Generalization (tổng quát hoá):** *Gỡ bỏ dữ liệu* (trừu tượng)

**Xử lý sự kiện:**

1. Biên tập viên mở một lớp và bấm "Xoá".
2. Hệ thống hiển thị số mẫu lớp đang giữ, số phiên thu liên quan, và cảnh báo rằng toàn bộ số đó sẽ rời tập làm việc cùng với lớp nhưng vẫn khôi phục được từ thùng rác.
3. Biên tập viên xác nhận.
4. Hệ thống kiểm vai biên tập và hạn mức tần suất ghi danh mục, và kiểm xem có mô hình đã thăng hạng nào còn tham chiếu tới lớp này không.
5. Hệ thống ghi dấu đã xoá lên bản ghi lớp và lên toàn bộ mẫu thuộc lớp, rồi chuyển cả cụm vào thùng rác.
6. Hệ thống ghi một mục vào nhật ký kiểm toán và làm mới danh mục.

**Luồng luân phiên:**

1. **Khôi phục từ thùng rác:** biên tập viên mở thùng rác và khôi phục lớp (UC212). Hệ thống xoá dấu đã xoá trên lớp **và** trên các mẫu đã bị xoá cùng nó trong cùng thao tác, để lớp trở lại đúng trạng thái trước khi xoá chứ không trở lại rỗng.
2. **Xoá vĩnh viễn từ thùng rác:** biên tập viên chọn xoá hẳn; hệ thống hỏi xác nhận rõ ràng, rồi xoá dòng lớp, xoá các dòng mẫu và chuyển lệnh xoá tệp đặc trưng cho tác vụ nền. Từ điểm này không còn đường hoàn tác nào trong hệ thống.

**Luồng ngoại lệ:**

1. **Một mô hình đã thăng hạng còn tham chiếu tới lớp.** Ở bước 4, hệ thống cảnh báo rằng bảng chỉ mục nhãn của mô hình đó sẽ trỏ tới một lớp không còn trong danh mục, nên kết quả suy luận vẫn ra chỉ số nhưng không tra ngược được thành tên nhãn. Hệ thống **không** chặn thao tác, vì việc dọn danh mục là quyền của tổ chức, nhưng bắt buộc hiển thị danh sách mô hình bị ảnh hưởng để quyết định được đưa ra có hiểu biết. Cách xử lý khuyến nghị là hạ hạng mô hình liên quan (UC406) trước khi xoá lớp.

2. **Lớp đang có mẫu chưa xử lý xong.** Ở bước 5, nếu còn tác vụ nền đang sinh mẫu cho lớp, các mẫu sinh ra sau thời điểm xoá sẽ thuộc về một lớp đã bị đánh dấu xoá và cũng nằm trong thùng rác. Hệ thống không huỷ tác vụ đang chạy. Biên tập viên nên đợi các tác vụ của lớp kết thúc (UC204) trước khi xoá, hoặc kiểm lại thùng rác sau đó.

3. **Xoá tệp thất bại ở nhánh xoá vĩnh viễn.** Việc xoá tệp được giao cho tác vụ nền có thử lại và chạy **sau khi** các dòng dữ liệu đã biến mất, nên một lần thất bại vĩnh viễn để lại tệp mồ côi trong kho chứ không để lại mẫu trỏ tới tệp đã mất. Báo cáo đối soát định kỳ liệt kê các tệp này để kỹ sư vận hành dọn (UC703).

4. **Lớp thuộc danh mục dùng chung.** Ở bước 4, một lớp nhân bản từ danh mục dùng chung chỉ xoá được **bản sao trong tổ chức**; mục gốc ở bản mẫu dùng chung không bị ảnh hưởng và chỉ quản trị nền tảng chạm tới được (UC308). Điều này cần nói rõ vì biên tập viên dễ tưởng mình vừa xoá một mục khỏi danh mục của cả nền tảng.

**Kết quả mong đợi:** Lớp và toàn bộ mẫu của nó mang dấu đã xoá và nằm trong thùng rác, khôi phục lại được thành đúng trạng thái trước khi xoá. Khi có mô hình đã thăng hạng tham chiếu tới lớp, quyết định được đưa ra sau khi đã nhìn thấy danh sách mô hình bị ảnh hưởng; ở nhánh xoá vĩnh viễn, phần rủi ro còn lại chỉ là tệp mồ côi trong kho.

---

#### UC305 — Xem thống kê thu thập

*Bảng C-30: Mô tả chức năng Xem thống kê thu thập*

| **Tên use case** | Xem thống kê thu thập | **ID** | UC305 |
|---|---|---|---|
| **Actor chính** | Thành viên tổ chức | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Thành viên tổ chức | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 3 — Danh mục từ vựng và phương ngữ |

**Các thành phần tham gia và mối quan tâm:**

- **Thành viên tổ chức** — biết thu tiếp lớp nào thì có ích nhất.
- **Quản trị tổ chức** — theo dõi được tiến độ chung của tổ chức.
- **Nghiên cứu sinh** — đánh giá được độ cân bằng giữa các lớp trước khi huấn luyện.

**Mô tả tóm tắt:** *Thành viên tổ chức xem tiến độ thu thập: số mẫu theo lớp, độ cân bằng giữa các lớp, đóng góp theo người ký, và số mẫu còn thiếu để đạt mục tiêu.*

**Các mối quan hệ:**

- **Association (kết hợp):** Thành viên tổ chức – Xem thống kê thu thập
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Thành viên mở bảng điều khiển của tổ chức.
2. Hệ thống hiển thị các số tổng trong phạm vi tổ chức hiện hành: số lớp, số mẫu còn hiệu lực, số người ký, và tỷ lệ lớp đã đạt mục tiêu.
3. Hệ thống hiển thị phân bố mẫu theo lớp, sắp xếp theo khoảng cách tới mục tiêu, kèm biểu đồ cho thấy độ chênh giữa lớp nhiều mẫu nhất và lớp ít mẫu nhất.
4. Thành viên nhập một mục tiêu số mẫu cho mỗi lớp; hệ thống tính kế hoạch cân bằng — mỗi lớp còn thiếu bao nhiêu mẫu và tổng số buổi thu ước tính.
5. Thành viên mở một lớp từ kế hoạch và bắt đầu thu cho lớp đó (UC201).

**Luồng luân phiên:**

1. **Xem theo người ký:** thành viên chuyển sang tab đóng góp theo người ký để thấy mỗi người ký đã đóng bao nhiêu mẫu cho những lớp nào. Số liệu này quan trọng vì một bộ dữ liệu do một người ký chiếm phần lớn sẽ cho kết quả đánh giá lạc quan giả khi chia tập theo mẫu thay vì theo người.

**Luồng ngoại lệ:**

1. **Tổ chức chưa có dữ liệu nào.** Ở bước 2, hệ thống hiển thị trạng thái trống kèm đúng hai bước đầu tiên cần làm — đăng ký một lớp, rồi thu một mẫu — thay vì một bảng số không. Đây là màn hình mặc định sau khi đăng nhập nên nó quyết định ấn tượng đầu của một tổ chức mới.

2. **Số của tổ chức và số của phần dùng chung.** Ở bước 2, hệ thống tách riêng hai nhóm số và **không bao giờ cộng chúng vào nhau**. Cộng gộp sẽ cho một tổ chức cảm giác mình có nhiều dữ liệu hơn thực tế và dẫn tới quyết định huấn luyện sai. Bảng điều khiển ghi rõ nhóm nào là của tổ chức, nhóm nào là danh mục dùng chung ở chế độ chỉ đọc.

3. **Bản soi trong cơ sở dữ liệu chậm hơn danh bạ.** Ở bước 3, khi hai nguồn lệch nhau, hệ thống hiển thị số của danh bạ nguồn sự thật và ghi chú thời điểm bản soi được cập nhật gần nhất. Chọn nguồn nào là một quyết định phải nhất quán trong toàn hệ thống, vì hai màn hình lấy số từ hai nguồn khác nhau sẽ hiển thị hai con số khác nhau cho cùng một câu hỏi và làm mất lòng tin vào cả hai.

4. **Một lớp có số đếm âm hoặc vượt mục tiêu bất thường.** Ở bước 3, số liệu bất thường thường là dấu hiệu của lệch giữa danh bạ và bản soi chứ không phải lỗi tính toán. Hệ thống hiển thị số như nó có, không tự sửa, và người dùng đối chiếu bằng trang chi tiết lớp (UC207); việc sửa lệch thuộc về tác vụ đối soát (UC703).

**Kết quả mong đợi:** Người xem có một bức tranh trung thực về tiến độ thu thập: số của tổ chức tách bạch với số của phần dùng chung, độ chênh giữa các lớp nhìn thấy được, và kế hoạch cân bằng nêu rõ mỗi lớp còn thiếu bao nhiêu mẫu để đạt mục tiêu.

---

#### UC306 — Đề xuất phương ngữ

*Bảng C-31: Mô tả chức năng Đề xuất phương ngữ*

| **Tên use case** | Đề xuất phương ngữ | **ID** | UC306 |
|---|---|---|---|
| **Actor chính** | Biên tập viên / Nghiên cứu sinh | **Mức độ cần thiết** | Tuỳ chọn |
| **Kích hoạt bởi** | Biên tập viên | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 3 — Danh mục từ vựng và phương ngữ |

**Các thành phần tham gia và mối quan tâm:**

- **Biên tập viên** — thu được ký hiệu vùng miền chưa có trong danh mục dùng chung.
- **Quản trị nền tảng** — kiểm soát được danh mục dùng chung để nó không phân mảnh.
- **Cộng đồng người dùng ký hiệu** — phương ngữ vùng miền được ghi nhận đúng tên.

**Mô tả tóm tắt:** *Biên tập viên đề xuất một phương ngữ vùng miền mới cho danh mục từ vựng dùng chung. Phương ngữ đề xuất dùng được trong nội bộ tổ chức nhưng phải qua kiểm duyệt mới thành một mục của danh mục chung.*

**Các mối quan hệ:**

- **Association (kết hợp):** Biên tập viên / Nghiên cứu sinh – Đề xuất phương ngữ
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Biên tập viên mở danh mục từ vựng và bấm "Đề xuất phương ngữ".
2. Biên tập viên nhập mã phương ngữ, tên hiển thị, ngôn ngữ mà phương ngữ thuộc về, vùng địa lý tương ứng và lý do đề xuất.
3. Biên tập viên gửi đề xuất.
4. Hệ thống kiểm vai biên tập, kiểm mã phương ngữ đúng dạng và chưa bị dùng bởi một phương ngữ nào — kể cả phương ngữ đang chờ duyệt hay đã bị từ chối.
5. Hệ thống lưu phương ngữ ở trạng thái chờ duyệt, gắn với tổ chức đề xuất, và gửi thông báo cho quản trị nền tảng.
6. Hệ thống hiển thị phương ngữ trong danh mục của tổ chức kèm dấu chờ duyệt, để tổ chức dùng được ngay cho việc thu mẫu nội bộ.

**Luồng luân phiên:**

1. **Dùng phương ngữ chờ duyệt để thu mẫu:** tổ chức tạo lớp và thu mẫu dưới phương ngữ đang chờ. Dữ liệu được ghi bình thường; điều chưa có là tư cách một mục trong danh mục dùng chung, và hệ quả của việc bị từ chối nêu ở ngoại lệ 3.

**Luồng ngoại lệ:**

1. **Mã phương ngữ đã tồn tại.** Ở bước 4, hệ thống từ chối và hiển thị phương ngữ đang giữ mã đó kèm trạng thái của nó — đã chấp nhận, đang chờ, hay đã bị từ chối. Hiển thị cả ba trạng thái là cần thiết: một mã đang bị một đề xuất chờ duyệt chiếm chỗ dẫn tới hành động khác hẳn so với một mã đã chính thức thuộc về phương ngữ khác. Biên tập viên chọn mã khác hoặc liên hệ tổ chức đã đề xuất trước.

2. **Người gọi không đủ vai.** Ở bước 4, hệ thống từ chối; thành viên thường không ghi được vào danh mục, kể cả ở dạng đề xuất. Ràng buộc này giữ cho số lượng đề xuất ở mức mà quản trị nền tảng xử lý được.

3. **Đề xuất bị từ chối về sau.** Nếu quản trị nền tảng từ chối (UC307), các lớp mà tổ chức đã tạo theo phương ngữ đó **vẫn còn** cùng toàn bộ mẫu đã thu — không dữ liệu nào bị xoá. Điều bị chặn là dùng chúng để huấn luyện: một lớp có phương ngữ không hợp lệ bị cổng kiểm tra loại ra trước khi lượt huấn luyện bắt đầu. Biên tập viên xử lý bằng cách sửa các lớp sang một phương ngữ đã được chấp nhận (UC302), hoặc đề xuất lại với lập luận đầy đủ hơn. Việc dữ liệu được giữ nguyên trong lúc chờ là chủ ý: công thu mẫu ngoài hiện trường không nên phụ thuộc vào tốc độ duyệt của một người ở nơi khác.

4. **Trùng nội dung với phương ngữ đã có nhưng khác mã.** Ở bước 4, hệ thống không phát hiện được trường hợp này bằng máy vì tên hiển thị là văn bản tự do. Việc phát hiện thuộc về khâu kiểm duyệt (UC307), nơi quản trị viên được hệ thống gợi ý các phương ngữ gần giống. Đây là giới hạn thật và là lý do khâu kiểm duyệt do người thực hiện chứ không tự động hoá.

**Kết quả mong đợi:** Phương ngữ mới tồn tại ở trạng thái chờ duyệt, dùng được ngay cho việc thu mẫu nội bộ của tổ chức đề xuất, và quản trị nền tảng đã nhận được thông báo. Mã phương ngữ được giữ chỗ nên không đề xuất nào khác chiếm mất; nếu về sau bị từ chối, dữ liệu đã thu vẫn còn nguyên và chỉ bị chặn ở cổng kiểm tra dữ liệu huấn luyện.

---

#### UC307 — Kiểm duyệt đề xuất phương ngữ

*Bảng C-32: Mô tả chức năng Kiểm duyệt đề xuất phương ngữ*

| **Tên use case** | Kiểm duyệt đề xuất phương ngữ | **ID** | UC307 |
|---|---|---|---|
| **Actor chính** | Quản trị nền tảng | **Mức độ cần thiết** | Tuỳ chọn |
| **Kích hoạt bởi** | Quản trị nền tảng | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 3 — Danh mục từ vựng và phương ngữ |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị nền tảng** — giữ danh mục dùng chung nhất quán giữa mọi tổ chức.
- **Tổ chức đề xuất** — biết kết quả và lý do.
- **Nghiên cứu sinh** — danh mục phương ngữ ổn định thì kết quả giữa các nghiên cứu mới so sánh được.

**Mô tả tóm tắt:** *Quản trị nền tảng xem xét các phương ngữ do các tổ chức đề xuất và quyết định chấp nhận hay từ chối đưa vào danh mục dùng chung.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị nền tảng – Kiểm duyệt đề xuất phương ngữ
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở danh sách phương ngữ đang chờ duyệt, sắp theo thời điểm đề xuất.
2. Hệ thống hiển thị từng đề xuất kèm mã, tên hiển thị, ngôn ngữ, vùng, tổ chức đề xuất, lý do, và số lớp cùng số mẫu mà tổ chức đã thu dưới phương ngữ đó.
3. Quản trị viên mở một đề xuất. Hệ thống hiển thị thêm danh sách các phương ngữ đã chấp nhận có tên hoặc vùng gần giống, để phát hiện trùng lặp.
4. Quản trị viên bấm "Chấp nhận".
5. Hệ thống đánh dấu phương ngữ đã được chấp nhận, đưa vào bản mẫu danh mục dùng chung, và ghi một mục vào nhật ký kiểm toán.
6. Hệ thống gửi thông báo cho tổ chức đề xuất và gỡ trạng thái chờ cho các lớp đang phụ thuộc phương ngữ đó, nhờ vậy chúng dùng được cho huấn luyện ngay.

**Luồng luân phiên:**

1. **Từ chối đề xuất:** ở bước 4, quản trị viên bấm "Từ chối" và **bắt buộc** nhập lý do — hệ thống không cho gửi khi ô lý do trống. Hệ thống lưu lý do, đánh dấu đề xuất đã bị từ chối, giữ mã phương ngữ ở trạng thái đã dùng để không ai đề xuất lại cùng mã mà không biết, và gửi lý do cho tổ chức đề xuất.
2. **Hướng người đề xuất về một mục đã có:** ở bước 3, khi thấy đề xuất trùng nội dung với một phương ngữ đã chấp nhận, quản trị viên từ chối kèm lý do nêu đích danh mã của mục nên dùng thay thế. Tổ chức đề xuất sửa các lớp của mình sang mã đó (UC302).

**Luồng ngoại lệ:**

1. **Đề xuất đã được một quản trị viên khác xử lý.** Ở bước 5, nếu trạng thái của đề xuất đã đổi kể từ lúc màn hình được mở, hệ thống báo trạng thái hiện tại và **không** ghi quyết định lần thứ hai. Cách này tránh việc một đề xuất mang hai quyết định trái ngược trong nhật ký kiểm toán. Quản trị viên làm mới danh sách và xem quyết định đã có cùng lý do của nó.

2. **Chấp nhận một phương ngữ mà tổ chức đề xuất đã ngừng dùng.** Ở bước 5, hệ thống vẫn chấp nhận và đưa vào danh mục dùng chung, vì giá trị của một mục danh mục không phụ thuộc vào việc tổ chức nào còn dùng nó. Thông báo ở bước 6 vẫn được gửi và có thể không ai đọc; đây là hệ quả chấp nhận được.

3. **Từ chối một phương ngữ đã có nhiều mẫu.** Ở bước 4, hệ thống hiển thị số lớp và số mẫu sẽ bị chặn khỏi huấn luyện ngay trên hộp thoại xác nhận, để quyết định không được đưa ra khi chưa biết cái giá của nó. Dữ liệu **không** bị xoá; nó chỉ không đi qua được cổng kiểm tra dữ liệu huấn luyện cho tới khi được gán sang một phương ngữ hợp lệ.

4. **Không có đề xuất nào đang chờ.** Ở bước 1, hệ thống hiển thị trạng thái trống kèm liên kết tới lịch sử các đề xuất đã xử lý, vì câu hỏi thường gặp tiếp theo của quản trị viên là "lần trước tôi đã quyết định gì với mã này".

**Kết quả mong đợi:** Đề xuất có một quyết định dứt khoát kèm lý do: khi chấp nhận, phương ngữ vào danh mục dùng chung và các lớp phụ thuộc nó được gỡ trạng thái chờ; khi từ chối, lý do tới được tổ chức đề xuất và mã phương ngữ vẫn được giữ để không ai đề xuất lại cùng mã mà không biết. Một đề xuất không bao giờ mang hai quyết định trong nhật ký kiểm toán.

---

#### UC308 — Bảo trì danh mục mẫu dùng chung

*Bảng C-33: Mô tả chức năng Bảo trì danh mục mẫu dùng chung*

| **Tên use case** | Bảo trì danh mục mẫu dùng chung | **ID** | UC308 |
|---|---|---|---|
| **Actor chính** | Quản trị nền tảng | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Quản trị nền tảng | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 3 — Danh mục từ vựng và phương ngữ |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị nền tảng** — giữ bản mẫu cấu hình mà mọi tổ chức mới khởi tạo từ đó.
- **Tổ chức mới** — nhận được danh mục mồi dùng ngay được.
- **Nghiên cứu sinh** — biết bản mẫu hiện tại đã khác gì so với phiên bản đã đóng băng gần nhất.

**Mô tả tóm tắt:** *Quản trị nền tảng sửa bản mẫu dùng chung — các phương ngữ và hồ sơ thu mẫu mà mọi tổ chức khởi tạo từ đó. Bản mẫu là mặt phẳng sống, sửa được; nó chưa phải thứ các tổ chức tiêu thụ cho tới khi được đóng băng thành một phiên bản (UC309).*

> **Ranh giới thuật ngữ:** bản mẫu này là **danh mục hệ thống** — mẫu cấu hình do nền tảng quản lý. Nó **không** chứa dữ liệu do người dùng đóng góp, không chứa video, điểm mốc, bản ghi đồng thuận hay giấy phép. Kho dữ liệu cộng đồng theo nghĩa đầy đủ là một thiết kế thuộc phần Hướng phát triển, chưa hiện thực.

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị nền tảng – Bảo trì danh mục mẫu dùng chung
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở danh mục mẫu dùng chung. Hệ thống hiển thị các phương ngữ và hồ sơ thu mẫu đang sống, mã băm nội dung của bản mẫu hiện tại, và phiên bản công bố gần nhất kèm mã băm của nó.
2. Quản trị viên đối chiếu hai mã băm để biết bản mẫu đã bị sửa kể từ lần công bố gần nhất hay chưa. Hai mã băm khác nhau nghĩa là đang có thay đổi chưa được đóng băng.
3. Quản trị viên sửa một phương ngữ hoặc một hồ sơ thu mẫu.
4. Hệ thống kiểm tính hợp lệ của giá trị mới, lưu thay đổi lên bản mẫu đang sống, và ghi lại người thực hiện cùng thời điểm.
5. Hệ thống tính lại mã băm nội dung, để chênh lệch so với phiên bản đã công bố luôn nhìn thấy được ở bước 1 của lần mở sau.

**Luồng luân phiên:**

1. **Nạp bù từ tệp mồi:** quản trị viên chạy lại lượt nạp mồi ban đầu. Thao tác này **chỉ chèn phần còn thiếu**; các dòng quản trị viên đã sửa được giữ nguyên. Hệ thống **cố ý không có** đường nào ghi đè bản sửa bằng tệp mồi, nên đây là công cụ vá chỗ trống chứ không phải công cụ khôi phục về mặc định.
2. **Đóng băng sau khi sửa:** khi bộ thay đổi đã đủ, quản trị viên công bố một phiên bản mới (UC309). Chừng nào chưa công bố, các tổ chức khởi tạo mới vẫn nhận nội dung theo phiên bản đã đóng băng gần nhất.

**Luồng ngoại lệ:**

1. **Mã không có trong bản mẫu.** Ở bước 4, hệ thống trả về không tìm thấy thay vì lặng lẽ tạo mới. Ranh giới giữa sửa và tạo phải rõ ràng ở mặt phẳng này, vì một mục tạo nhầm sẽ theo bản mẫu sang mọi tổ chức khởi tạo về sau.

2. **Giá trị không hợp lệ.** Ở bước 4, hệ thống từ chối và giữ nguyên bản mẫu, không lưu một phần. Vì bản mẫu là nguồn khởi tạo cho mọi tổ chức, một dòng hỏng ở đây nhân lên thành một dòng hỏng trong mỗi tổ chức mới.

3. **Tổ chức muốn tự sửa mặt phẳng này.** Ở bước 3, chỉ quản trị nền tảng chạm được bản mẫu dùng chung. Một tổ chức chỉ sửa danh mục **của chính tổ chức đó**; muốn thay đổi bản mẫu thì đề xuất và chờ kiểm duyệt (UC306, UC307). Ranh giới này là một trong hai mặt phẳng cách ly của kiến trúc và không có ngoại lệ nào cho vai quản trị tổ chức.

4. **Sửa một mục mà nhiều tổ chức đã nhân bản.** Ở bước 4, thay đổi trên bản mẫu **không** lan sang các bản sao đã nằm trong danh mục của các tổ chức. Đây là điểm dễ hiểu nhầm nhất và phải nói rõ: nhân bản là một thao tác chép tại thời điểm khởi tạo, không phải một liên kết sống. Muốn các tổ chức có mục mới, quản trị viên chạy lại lượt nhân bản cho từng tổ chức (UC310), và lượt đó cũng chỉ điền chỗ trống.

**Kết quả mong đợi:** Bản mẫu dùng chung phản ánh đúng nội dung quản trị viên vừa sửa, và mã băm nội dung cho biết ngay bản mẫu đã khác phiên bản công bố gần nhất tới mức nào. Các bản sao danh mục đã nằm trong các tổ chức không bị thay đổi theo, và tệp mồi không bao giờ ghi đè lên phần quản trị viên đã sửa.

---

#### UC309 — Công bố phiên bản danh mục dùng chung

*Bảng C-34: Mô tả chức năng Công bố phiên bản danh mục dùng chung*

| **Tên use case** | Công bố phiên bản danh mục dùng chung | **ID** | UC309 |
|---|---|---|---|
| **Actor chính** | Quản trị nền tảng | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Quản trị nền tảng | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 3 — Danh mục từ vựng và phương ngữ |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị nền tảng** — đóng băng được một trạng thái danh mục để trích dẫn.
- **Nghiên cứu sinh** — một kết quả nghiên cứu tham chiếu được tới đúng phiên bản danh mục đã dùng.
- **Tổ chức** — biết mình đang khởi tạo từ phiên bản nào.

**Mô tả tóm tắt:** *Quản trị nền tảng đóng băng bản mẫu đang sống thành một phiên bản bất biến có đánh số. Phiên bản là thứ các tổ chức và các mô hình đã huấn luyện tham chiếu tới, nên việc đóng băng là điều làm cho một trạng thái danh mục trở nên trích dẫn được.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị nền tảng – Công bố phiên bản danh mục dùng chung
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở danh mục và đọc lịch sử phiên bản: số hiệu, mã băm nội dung, người thực hiện, thời điểm và ghi chú của từng phiên bản.
2. Quản trị viên viết ghi chú mô tả nội dung thay đổi so với phiên bản trước.
3. Quản trị viên thực hiện công bố.
4. Hệ thống tính mã băm nội dung của bản mẫu đang sống và so với mã băm của phiên bản công bố gần nhất.
5. Nội dung có thay đổi: hệ thống đúc một phiên bản bất biến mới giữ đúng nội dung đó, gán số hiệu kế tiếp và trả về số hiệu.
6. Hệ thống báo rõ có thật sự tạo ra phiên bản mới hay không, và ghi một mục vào nhật ký kiểm toán.

**Luồng luân phiên:**

1. **Tra một phiên bản cũ:** quản trị viên mở một số hiệu trong lịch sử để đọc nội dung tại thời điểm đó. Nội dung này là bản đóng băng, không phải bản mẫu đang sống, nên nó cho biết chính xác một tổ chức khởi tạo hồi đó đã nhận được gì.

**Luồng ngoại lệ:**

1. **Nội dung không thay đổi so với phiên bản gần nhất.** Ở bước 5, hệ thống **không** đúc ra một phiên bản trùng nội dung. Thay vào đó nó trả về đúng phiên bản đang giữ nội dung ấy và báo rằng không có gì được tạo mới, để màn hình nói được "phiên bản 7 đã giữ nội dung này" thay vì báo thành công khiến người dùng tưởng vừa có một mốc mới. Nếu cho phép đúc bản trùng, lịch sử phiên bản sẽ đầy những số hiệu không phân biệt được với nhau và mất giá trị trích dẫn.

2. **Sửa nội dung của một phiên bản đã công bố.** Sau bước 5, nội dung của phiên bản là bất biến và hệ thống không cung cấp đường nào để sửa nó. Một chỉnh sửa là một phiên bản mới. Ràng buộc này là điều kiện để một bài báo trích dẫn "danh mục phiên bản 7" mà không cần kèm theo ngày tháng.

3. **Tra một số hiệu không tồn tại.** Ở bước 1, hệ thống trả về không tìm thấy. Trường hợp thường gặp là số hiệu bị chép nhầm từ một tài liệu cũ; quản trị viên đối chiếu bằng mã băm nội dung, vốn ổn định hơn số hiệu khi dữ liệu được chuyển giữa các bản triển khai.

4. **Hai quản trị viên công bố gần như đồng thời.** Ở bước 5, người thứ hai nhận kết quả rằng nội dung hiện tại đã nằm trong phiên bản do người thứ nhất vừa đúc, theo đúng cơ chế ở ngoại lệ 1. Không có phiên bản trùng nào được tạo và không có lỗi nào cần xử lý.

**Kết quả mong đợi:** Tồn tại một phiên bản danh mục bất biến, có số hiệu và mã băm nội dung, trích dẫn được trong một bài công bố mà không cần kèm ngày tháng. Nếu nội dung không đổi, hệ thống trả về đúng phiên bản đang giữ nội dung ấy thay vì đúc thêm một bản trùng làm loãng lịch sử phiên bản.

---

#### UC310 — Nhân bản danh mục cho tổ chức

*Bảng C-35: Mô tả chức năng Nhân bản danh mục cho tổ chức*

| **Tên use case** | Nhân bản danh mục cho tổ chức | **ID** | UC310 |
|---|---|---|---|
| **Actor chính** | Quản trị nền tảng | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Quản trị nền tảng | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 3 — Danh mục từ vựng và phương ngữ |

**Các thành phần tham gia và mối quan tâm:**

- **Tổ chức mới** — bắt đầu với danh mục dùng được ngay thay vì danh mục trống.
- **Quản trị nền tảng** — mồi danh mục một lần cho mỗi tổ chức, không dùng thao tác này để sửa dữ liệu.

**Mô tả tóm tắt:** *Quản trị nền tảng khởi tạo danh mục cho một tổ chức mới từ bản mẫu dùng chung, để tổ chức có sẵn phương ngữ và hồ sơ thu mẫu dùng được ngay.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị nền tảng – Nhân bản danh mục cho tổ chức
- **Include (bao gồm):** không
- **Extend (mở rộng):** UC501 Quản lý tổ chức
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên chọn tổ chức cần khởi tạo danh mục.
2. Hệ thống hiển thị nội dung hiện có của bản mẫu — số phương ngữ, số hồ sơ thu mẫu — và những mục mà tổ chức đã có, để thấy trước phần sẽ được chèn.
3. Quản trị viên xác nhận nhân bản.
4. Hệ thống chép các dòng của bản mẫu sang danh mục của tổ chức, **chỉ chèn phần chưa có**, và giữ nguyên mọi dòng tổ chức đã tự sửa.
5. Hệ thống báo cáo số phương ngữ và số hồ sơ thu mẫu đã tạo, cùng số mục đã bỏ qua vì đã tồn tại.

**Luồng luân phiên:**

1. **Nhân bản trong lúc tạo tổ chức:** thao tác này thường chạy như một bước của quy trình tạo tổ chức (UC501), nên quản trị viên không phải mở màn hình riêng. Kết quả và các ràng buộc là một.

**Luồng ngoại lệ:**

1. **Chạy lần thứ hai trên cùng một tổ chức.** Ở bước 4, việc chạy lại là vô hại nhưng **chỉ điền chỗ trống**. Đây **không phải công cụ khôi phục**: một tổ chức đã sửa danh mục theo hướng riêng vẫn giữ nguyên các dòng của mình, và bản mẫu không ghi đè lên chúng. Quản trị viên muốn đưa tổ chức về đúng nội dung bản mẫu thì phải sửa từng mục bằng tay — hệ thống cố ý không có nút đưa về mặc định, vì nút đó sẽ xoá công cấu hình của tổ chức chỉ bằng một cú bấm.

2. **Mã tổ chức không tồn tại.** Ở bước 4, các dòng danh mục **không** có khoá ngoại trỏ tới bảng tổ chức, nên nếu ghi bừa, hệ thống sẽ tạo ra những dòng mang một mã tổ chức không ai với tới được — chúng không hiện ở bất kỳ màn hình nào và chỉ chiếm chỗ. Vì vậy hệ thống kiểm tính hợp lệ của mã tổ chức **trước khi** ghi. Đây là một trong những chỗ mà ràng buộc toàn vẹn phải nằm ở tầng ứng dụng vì không có ràng buộc nào ở tầng cơ sở dữ liệu đảm nhiệm.

3. **Thiếu mã tổ chức trong yêu cầu.** Ở bước 3, hệ thống từ chối thay vì suy đoán tổ chức hiện hành từ ngữ cảnh phiên làm việc. Suy đoán ở thao tác này rất nguy hiểm vì quản trị nền tảng thường làm việc ngoài ngữ cảnh của bất kỳ tổ chức nào, và một suy đoán sai sẽ mồi danh mục vào nhầm tổ chức.

4. **Bản mẫu đang trống.** Ở bước 2, nếu bản mẫu chưa có mục nào, hệ thống báo rõ và không tạo gì, thay vì báo nhân bản thành công với con số không. Quản trị viên nạp mồi cho bản mẫu trước (UC308).

**Kết quả mong đợi:** Danh mục của tổ chức có đủ các mục của bản mẫu mà nó còn thiếu, trong khi mọi mục tổ chức đã tự sửa giữ nguyên. Báo cáo nêu rõ đã tạo bao nhiêu và bỏ qua bao nhiêu, nên chạy lại nhiều lần vẫn cho kết quả xác định và không phá dữ liệu.

---

### 5.4 Nghiệp vụ 4 — Huấn luyện, đánh giá và suy luận

#### UC402 — Theo dõi tiến trình huấn luyện

*Bảng C-36: Mô tả chức năng Theo dõi tiến trình huấn luyện*

| **Tên use case** | Theo dõi tiến trình huấn luyện | **ID** | UC402 |
|---|---|---|---|
| **Actor chính** | Biên tập viên / Nghiên cứu sinh | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Nghiên cứu sinh | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 4 — Huấn luyện, đánh giá và suy luận |

**Các thành phần tham gia và mối quan tâm:**

- **Nghiên cứu sinh** — biết lượt chạy đang tiến triển hay đã đứng.
- **Tổ chức khác trong hàng đợi** — hàng đợi chỉ có một chỗ chạy nên vị trí chờ phải minh bạch.

**Mô tả tóm tắt:** *Nghiên cứu sinh theo dõi một lượt huấn luyện đang chạy: tiến độ theo chu kỳ, đường cong mất mát và độ chính xác, cùng vị trí của lượt chạy trong hàng đợi.*

**Các mối quan hệ:**

- **Association (kết hợp):** Biên tập viên / Nghiên cứu sinh – Theo dõi tiến trình huấn luyện
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Nghiên cứu sinh mở danh sách lượt chạy của tổ chức và chọn một lượt.
2. Hệ thống hiển thị trạng thái, thời gian đã chạy, và **cấu hình mà lượt chạy được khởi động với** — kiến trúc mô hình, số chu kỳ, kích thước lô, cách chia tập, bộ lọc lớp. Cấu hình được chốt tại thời điểm khởi động và không đổi theo cấu hình hiện hành của hệ thống.
3. Hệ thống hiển thị các số đo đã ghi, mỗi chu kỳ một điểm: mất mát trên tập huấn luyện, mất mát trên tập kiểm định, độ chính xác trên tập kiểm định.
4. Hệ thống làm mới số đo theo chu kỳ trong khi lượt chạy còn chạy, và **dừng làm mới** khi lượt chạy đã kết thúc — vòng hỏi trạng thái có điều kiện dừng rõ ràng.
5. Khi lượt chạy kết thúc, hệ thống hiển thị số đo cuối cùng và liên kết sang phần đánh giá (UC404).

**Luồng luân phiên:**

1. **Xem nhật ký thô của lượt chạy:** nghiên cứu sinh mở tab nhật ký để đọc dòng ghi của tiến trình huấn luyện. Đây là đường duy nhất để chẩn đoán các lỗi không được tóm tắt thành số đo, chẳng hạn cảnh báo về hình dạng dữ liệu.

**Luồng ngoại lệ:**

1. **Lượt chạy vẫn còn trong hàng đợi.** Ở bước 2, hệ thống hiển thị vị trí trong hàng đợi và tình trạng chỗ chạy đang bị lượt nào chiếm, thay vì hiển thị các đường cong trống khiến người dùng tưởng lượt chạy đã bắt đầu mà không tiến triển. Hệ thống chỉ có **một chỗ chạy** cho huấn luyện, nên chờ là trạng thái bình thường chứ không phải sự cố. Nghiên cứu sinh có thể huỷ lượt chạy đang chờ (UC403) nếu muốn nhường chỗ.

2. **Lượt chạy thất bại giữa chừng.** Ở bước 5, hệ thống hiển thị thông báo lỗi do tiến trình ghi lại **và** chu kỳ cuối cùng đã ghi được số đo. Phân biệt hai tình huống này rất quan trọng: một lượt chạy hỏng ở chu kỳ thứ bốn mươi là dấu hiệu của vấn đề dữ liệu hoặc tài nguyên xuất hiện muộn, còn một lượt chạy hỏng trước chu kỳ đầu tiên thường là lỗi cấu hình hoặc thiếu dữ liệu. Nghiên cứu sinh đọc nhật ký ở luồng luân phiên 1 rồi khởi động lại với cấu hình sửa (UC401).

3. **Tiến trình ngừng ghi số đo nhưng trạng thái vẫn là đang chạy.** Ở bước 3, nếu quá một khoảng thời gian mà không có chu kỳ mới, hệ thống đánh dấu lượt chạy là nghi treo thay vì hiển thị một đường cong đứng yên như thể bình thường. Nguyên nhân thường gặp là tiến trình bị hệ điều hành dừng vì hết bộ nhớ, hoặc thiết bị tính toán bị một tiến trình khác chiếm. Nghiên cứu sinh huỷ lượt chạy (UC403) để trả chỗ cho hàng đợi; cơ chế dọn dẹp cũng tự thu hồi chỗ chạy của các lượt quá hạn, nên hàng đợi không bị chặn vô thời hạn.

4. **Lượt chạy thuộc tổ chức khác.** Ở bước 1, lượt chạy ngoài phạm vi tổ chức hiện hành không xuất hiện trong danh sách, và mở thẳng bằng mã lượt chạy trả về không tìm thấy — cùng một câu trả lời với trường hợp mã không tồn tại, theo nguyên tắc đã nêu ở UC204.

**Kết quả mong đợi:** Nghiên cứu sinh biết lượt chạy đang ở đâu và với cấu hình nào: vị trí trong hàng đợi khi còn chờ, đường cong số đo theo chu kỳ khi đang chạy, lý do và chu kỳ cuối cùng khi thất bại. Một lượt chạy ngừng ghi số đo được đánh dấu nghi treo thay vì hiển thị như đang tiến triển bình thường.

---

#### UC403 — Huỷ lượt huấn luyện

*Bảng C-37: Mô tả chức năng Huỷ lượt huấn luyện*

| **Tên use case** | Huỷ lượt huấn luyện | **ID** | UC403 |
|---|---|---|---|
| **Actor chính** | Biên tập viên / Nghiên cứu sinh | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Nghiên cứu sinh | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 4 — Huấn luyện, đánh giá và suy luận |

**Các thành phần tham gia và mối quan tâm:**

- **Nghiên cứu sinh** — dừng được lượt chạy sai cấu hình mà không phải chờ hết.
- **Các tổ chức khác** — chỗ chạy được trả lại cho người kế tiếp trong hàng đợi.

**Mô tả tóm tắt:** *Nghiên cứu sinh dừng một lượt huấn luyện đang chờ hoặc đang chạy, giải phóng chỗ chạy duy nhất cho tổ chức kế tiếp trong hàng đợi.*

**Các mối quan hệ:**

- **Association (kết hợp):** Biên tập viên / Nghiên cứu sinh – Huỷ lượt huấn luyện
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Nghiên cứu sinh mở một lượt chạy và bấm "Huỷ".
2. Hệ thống hỏi xác nhận, nêu rõ số chu kỳ đã chạy và rằng phần đã chạy dở **không** khôi phục được — không có bản lưu trung gian nào được giữ lại cho một lượt bị huỷ.
3. Nghiên cứu sinh xác nhận.
4. Hệ thống kiểm người gọi là chủ lượt chạy hoặc có vai biên tập trên tổ chức sở hữu.
5. Hệ thống đặt cờ huỷ để tiến trình huấn luyện đọc được ở cuối chu kỳ hiện tại, đánh dấu lượt chạy đã huỷ và trả lại chỗ trong hàng đợi.
6. Hệ thống ghi một mục vào nhật ký kiểm toán và làm mới danh sách lượt chạy; lượt kế tiếp trong hàng đợi bắt đầu chạy.

**Luồng luân phiên:**

1. **Huỷ một lượt còn đang chờ:** ở bước 5, lượt chạy chưa chiếm chỗ nên hệ thống chỉ cần gỡ nó khỏi hàng đợi. Không có tiến trình nào phải dừng và thao tác kết thúc ngay.
2. **Xoá hẳn bản ghi lượt chạy sau khi huỷ:** nghiên cứu sinh chọn xoá bản ghi để dọn danh sách. Số đo và bản kê khai của lượt chạy mất theo, nên hệ thống hỏi xác nhận lần thứ hai và nêu rõ điều đó.

**Luồng ngoại lệ:**

1. **Lượt chạy đã kết thúc trước khi lệnh huỷ tới.** Ở bước 5, hệ thống báo trạng thái cuối cùng — hoàn tất hoặc thất bại — và không huỷ gì cả. Mô hình đã sinh ra vẫn còn nguyên. Đây là tình huống thường gặp khi người dùng bấm huỷ đúng lúc lượt chạy sắp xong; hệ thống không coi đó là lỗi.

2. **Tiến trình huấn luyện không phản hồi cờ huỷ.** Ở bước 5, nếu tiến trình đã treo hoặc đã chết mà chưa kịp cập nhật trạng thái, hệ thống **vẫn** đánh dấu lượt chạy là đã huỷ và để cơ chế dọn dẹp thu hồi chỗ chạy sau một thời hạn. Nhờ vậy một tiến trình chết không chặn hàng đợi vô thời hạn — điều sẽ xảy ra nếu hệ thống chờ tiến trình xác nhận mới dám giải phóng chỗ. Hệ quả cần chấp nhận: trong khoảng chờ thu hồi, tài nguyên tính toán vẫn bị chiếm bởi một tiến trình mà hệ thống coi như đã chết. Kỹ sư vận hành thấy tình trạng này qua giám sát (UC704).

3. **Người gọi không phải chủ lượt chạy và không có vai biên tập.** Ở bước 4, hệ thống từ chối. Một lượt huấn luyện chiếm chỗ chạy duy nhất của cả hệ thống, nên việc cho phép bất kỳ thành viên nào huỷ lượt của người khác sẽ biến hàng đợi thành nơi tranh chấp. Thành viên cần chỗ gấp thì thương lượng qua quản trị tổ chức.

4. **Lượt chạy bị huỷ khi đã ghi được vài chu kỳ số đo.** Ở bước 5, các số đo đã ghi **vẫn được giữ** và xem lại được ở UC402, dù không có mô hình nào được sinh ra. Giữ lại số đo là chủ ý: chúng cho biết đường cong đã đi theo hướng nào trước khi người dùng quyết định dừng, và đó thường chính là lý do họ dừng.

**Kết quả mong đợi:** Lượt chạy ở trạng thái đã huỷ, chỗ chạy được trả lại cho hàng đợi và lượt kế tiếp bắt đầu, kể cả khi tiến trình cũ không phản hồi. Các số đo đã ghi được giữ lại để xem lại, còn mô hình thì không được sinh ra.

---

#### UC404 — Xem đánh giá và nguồn gốc

*Bảng C-38: Mô tả chức năng Xem đánh giá và nguồn gốc*

| **Tên use case** | Xem đánh giá và nguồn gốc | **ID** | UC404 |
|---|---|---|---|
| **Actor chính** | Biên tập viên / Nghiên cứu sinh | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Nghiên cứu sinh | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 4 — Huấn luyện, đánh giá và suy luận |

**Các thành phần tham gia và mối quan tâm:**

- **Nghiên cứu sinh** — biết kết quả này có so sánh được với lượt chạy trước hay không.
- **Hội đồng đánh giá** — kiểm chứng được điều kiện sinh ra một con số công bố.
- **Người ký** — biết mẫu bị loại vì đồng thuận được đếm và công khai.

**Mô tả tóm tắt:** *Nghiên cứu sinh đọc kết quả đánh giá của một lượt chạy đã hoàn tất — độ chính xác theo lớp, mức nhầm lẫn giữa các lớp — cùng bản ghi nguồn gốc nêu chính xác mẫu nào, cách chia tập nào và phiên bản mã nào đã tạo ra kết quả đó.*

**Các mối quan hệ:**

- **Association (kết hợp):** Biên tập viên / Nghiên cứu sinh – Xem đánh giá và nguồn gốc
- **Include (bao gồm):** không
- **Extend (mở rộng):** không *(UC405 mở rộng use case này)*
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Nghiên cứu sinh mở một lượt chạy đã hoàn tất và chọn mục "Đánh giá".
2. Hệ thống hiển thị độ chính xác tổng thể, độ chính xác theo từng lớp, và ma trận nhầm lẫn trên tập giữ lại, kèm số mẫu của mỗi lớp trong tập đó — một độ chính xác cao trên một lớp có ba mẫu không mang cùng ý nghĩa với độ chính xác ấy trên một lớp có ba trăm mẫu.
3. Nghiên cứu sinh chọn mục "Nguồn gốc".
4. Hệ thống hiển thị bản ghi nguồn gốc: mã bản kê khai bộ dữ liệu, cách chia tập đã dùng, số người ký ở mỗi phía của phép chia, số mẫu bị loại vì đồng thuận, số lớp bị loại vì không đạt sàn số mẫu, cấu hình huấn luyện và phiên bản mã nguồn.
5. Nghiên cứu sinh dùng bản ghi nguồn gốc để quyết định kết quả này có so sánh được với một lượt chạy trước hay không.

**Luồng luân phiên:**

1. **So sánh hai lượt chạy:** nghiên cứu sinh mở hai lượt chạy cạnh nhau và đối chiếu bản ghi nguồn gốc trước khi đối chiếu số đo. Đây là thứ tự đúng: hai con số chỉ so sánh được khi hai bản ghi nguồn gốc khớp nhau ở cách chia tập và ở tập lớp.

**Luồng ngoại lệ:**

1. **Lượt chạy không có phần đánh giá.** Ở bước 2, nếu lượt chạy hỏng trước khi tới bước đánh giá, hệ thống nói thẳng điều đó thay vì hiển thị một ma trận rỗng hay một độ chính xác bằng không. Một ma trận rỗng dễ bị đọc nhầm thành "mô hình sai hoàn toàn", trong khi sự thật là chưa từng có phép đánh giá nào chạy.

2. **Phép chia tập không tách rời người ký.** Ở bước 4, hệ thống ghi rõ trên bản ghi nguồn gốc rằng kết quả **không** tách rời người ký, nghĩa là cùng một người ký có mẫu ở cả tập huấn luyện lẫn tập kiểm tra. Con số sinh ra từ phép chia này luôn cao hơn con số của phép chia tách rời người ký, nên đem hai loại so với nhau là sai lầm mà bản ghi nguồn gốc tồn tại để ngăn. Hệ thống không ẩn kết quả cũng không tự hạ thấp nó; nó ghi điều kiện và để người đọc kết luận.

3. **Lượt chạy cũ không có bản kê khai.** Ở bước 4, với các lượt chạy có trước khi cơ chế bản kê khai ra đời, hệ thống hiển thị "không có thông tin nguồn gốc" thay vì dựng lại một bản nghe có vẻ hợp lý từ dữ liệu hiện tại. Dựng lại sẽ mô tả bộ dữ liệu **hôm nay** chứ không phải bộ dữ liệu lúc huấn luyện, và một bản ghi nguồn gốc sai còn tệ hơn không có bản nào. Kết quả của những lượt chạy này không dùng để công bố được.

4. **Số mẫu bị loại vì đồng thuận lớn bất thường.** Ở bước 4, nếu số này chiếm tỷ lệ đáng kể, hệ thống hiển thị nổi bật nó thay vì để lẫn trong bảng. Nguyên nhân thường là một nhóm người ký chưa chọn mức phát hành (UC112) chứ không phải họ đã từ chối; phân biệt hai điều đó dẫn tới hai hành động khác nhau, nên bản ghi nguồn gốc tách riêng số mẫu "đã rút đồng thuận" và số mẫu "chưa có mức phát hành".

**Kết quả mong đợi:** Người đọc có đủ căn cứ để trả lời câu hỏi kết quả này so sánh được với lượt chạy nào: số đo theo lớp kèm số mẫu của từng lớp, và bản ghi nguồn gốc nêu bản kê khai bộ dữ liệu, cách chia tập, số người ký mỗi phía, số mẫu bị loại theo từng lý do và phiên bản mã. Với lượt chạy không có thông tin nguồn gốc, hệ thống nói thẳng điều đó thay vì dựng lại một bản nghe hợp lý.

---

#### UC405 — Thử mô hình đã huấn luyện

*Bảng C-39: Mô tả chức năng Thử mô hình đã huấn luyện*

| **Tên use case** | Thử mô hình đã huấn luyện | **ID** | UC405 |
|---|---|---|---|
| **Actor chính** | Biên tập viên / Nghiên cứu sinh | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Nghiên cứu sinh | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 4 — Huấn luyện, đánh giá và suy luận |

**Các thành phần tham gia và mối quan tâm:**

- **Nghiên cứu sinh** — thử một mẫu thật trước khi quyết định đưa mô hình ra phục vụ.
- **Quản trị nền tảng** — có thêm căn cứ trước khi thăng hạng.
- **Dịch vụ suy luận (S3)** — không bị ảnh hưởng, vì lượt thử dùng bản lưu của chính lượt chạy.

**Mô tả tóm tắt:** *Nghiên cứu sinh đưa một mẫu qua mô hình do một lượt huấn luyện đã hoàn tất sinh ra, trước khi quyết định có thăng hạng nó hay không. Trả lời câu hỏi là bản lưu của chính lượt chạy đó, không phải mô hình đang phục vụ nhận dạng.*

**Các mối quan hệ:**

- **Association (kết hợp):** Biên tập viên / Nghiên cứu sinh – Thử mô hình đã huấn luyện
- **Include (bao gồm):** không
- **Extend (mở rộng):** UC404 Xem đánh giá và nguồn gốc
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Nghiên cứu sinh mở một lượt chạy đã hoàn tất và chọn "Thử mô hình này".
2. Nghiên cứu sinh cung cấp một cửa sổ điểm mốc: quay tại chỗ bằng máy quay, hoặc chọn một mẫu đã có trong bộ dữ liệu.
3. Hệ thống kiểm hạn mức số lần dự đoán của tổ chức theo gói dịch vụ.
4. Hệ thống nạp bản lưu mô hình của **chính lượt chạy đó** — không phải mô hình đang phục vụ — và đưa cửa sổ qua mô hình.
5. Hệ thống hiển thị nhãn dự đoán, độ tin cậy, và **chỉ số nhãn mà mô hình thực sự trả về**, bên cạnh tên lớp mà chỉ số đó tra ra trong danh mục hiện tại.
6. Nghiên cứu sinh đối chiếu kết quả với nhãn mong đợi và quyết định có thăng hạng hay không (UC406).

**Luồng luân phiên:**

1. **Thử hàng loạt bằng mẫu có sẵn:** nghiên cứu sinh chọn nhiều mẫu của một lớp và chạy lần lượt, để thấy mô hình nhầm lớp này sang lớp nào. Kết quả bổ sung cho ma trận nhầm lẫn ở UC404 bằng các ví dụ cụ thể.

**Luồng ngoại lệ:**

1. **Lượt chạy chưa sinh ra mô hình.** Ở bước 4, một lượt chạy chưa hoàn tất hoặc đã bị huỷ không có bản lưu nào; hệ thống báo rõ rằng lượt chạy chưa sinh ra mô hình, thay vì báo lỗi nạp tệp khiến người dùng đi tìm nguyên nhân ở kho lưu trữ. Nghiên cứu sinh chờ lượt chạy xong hoặc chọn lượt khác.

2. **Hết hạn mức số lần dự đoán.** Ở bước 3, hệ thống từ chối và hiển thị hạn mức của gói dịch vụ cùng thời điểm hạn mức được đặt lại. Lượt thử này tiêu cùng ngân sách với chức năng nhận dạng (UC407), nên một đợt thử mô hình dài có thể làm cạn hạn mức dùng cho người dùng cuối. Quản trị tổ chức nâng gói (UC506) nếu cần.

3. **Cửa sổ đầu vào sai kích thước.** Ở bước 4, nếu cửa sổ không khớp độ dài hoặc số chiều đặc trưng mà mô hình được huấn luyện với, hệ thống báo đích danh sai lệch — mong đợi bao nhiêu, nhận được bao nhiêu — thay vì đệm bừa rồi trả về một nhãn vô nghĩa. Nguyên nhân thường gặp là mẫu được sinh dưới một cấu hình cửa sổ cũ.

4. **Chỉ số nhãn đã trôi so với danh mục hiện tại.** Ở bước 5, nếu danh mục thay đổi sau khi mô hình được huấn luyện — có lớp bị gộp (UC303) hoặc bị gỡ (UC304) — thì chỉ số mô hình trả về có thể tra ra một lớp khác với lớp lúc huấn luyện, hoặc không tra ra gì. Hệ thống hiển thị **cả hai**: chỉ số thô của mô hình và tên lớp tra được hôm nay. Đây chính là điều màn hình này tồn tại để phơi ra; nếu chỉ hiển thị tên lớp, sai lệch sẽ trôi qua không ai thấy. Cách xử lý là huấn luyện lại mô hình theo danh mục hiện tại (UC401).

5. **Không cấp quyền máy quay ở nhánh quay tại chỗ.** Ở bước 2, hệ thống hướng dẫn cấp quyền và cho chọn mẫu có sẵn làm đường thay thế, giống cơ chế đã mô tả ở UC114.

**Kết quả mong đợi:** Nghiên cứu sinh thấy dự đoán của **đúng bản lưu mô hình thuộc lượt chạy đó**, kèm cả chỉ số nhãn thô lẫn tên lớp tra được hôm nay, nên mọi trôi lệch giữa mô hình và danh mục hiện tại đều lộ ra. Mô hình đang phục vụ nhận dạng không bị ảnh hưởng bởi lượt thử này.

---

#### UC406 — Thăng hạng phiên bản mô hình

*Bảng C-40: Mô tả chức năng Thăng hạng phiên bản mô hình*

| **Tên use case** | Thăng hạng phiên bản mô hình | **ID** | UC406 |
|---|---|---|---|
| **Actor chính** | Quản trị nền tảng | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Quản trị nền tảng | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 4 — Huấn luyện, đánh giá và suy luận |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị nền tảng** — quyết định mô hình nào phục vụ người dùng cuối.
- **Người dùng nhận dạng** — chất lượng nhận dạng thay đổi ngay sau thao tác này.
- **Dịch vụ suy luận (S3)** — nhận lệnh nạp nóng phiên bản mới.
- **Nghiên cứu sinh** — phiên bản là bất biến nên kết quả công bố vẫn tra ngược được.

**Mô tả tóm tắt:** *Quản trị nền tảng đưa mô hình do một lượt huấn luyện sinh ra thành mô hình đang hoạt động của một phương ngữ, để chức năng nhận dạng thời gian thực bắt đầu phục vụ bằng mô hình đó.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị nền tảng – Thăng hạng phiên bản mô hình; Dịch vụ suy luận (S3)
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở một lượt chạy đã hoàn tất và xem phần đánh giá cùng nguồn gốc của nó (UC404).
2. Quản trị viên bấm "Thăng hạng" và chọn phương ngữ mà mô hình sẽ phục vụ.
3. Hệ thống hiển thị mô hình đang hoạt động của phương ngữ đó và mô hình sắp thay thế, đặt cạnh nhau: số đo, số lớp, bản kê khai bộ dữ liệu và ngày huấn luyện.
4. Quản trị viên xác nhận.
5. Hệ thống đăng ký một **phiên bản mô hình bất biến** mới, gồm tệp mô hình, bảng chỉ mục nhãn, số đo và thông tin nguồn gốc; phiên bản được cấp một số hiệu không bao giờ dùng lại.
6. Hệ thống đánh dấu phiên bản mới là phiên bản đang hoạt động của phương ngữ và cho phiên bản cũ nghỉ — bản ghi của phiên bản cũ vẫn còn nguyên, chỉ mất tư cách đang hoạt động.
7. Hệ thống yêu cầu dịch vụ suy luận nạp phiên bản mới và ghi một mục vào nhật ký kiểm toán.

**Luồng luân phiên:**

1. **Quay về một phiên bản cũ:** quản trị viên mở lịch sử phiên bản của phương ngữ và thăng hạng lại một phiên bản trước đó. Vì phiên bản là bất biến, việc quay lui là **một lần thăng hạng nữa**, không phải một lần sửa; nhật ký kiểm toán vì vậy ghi đủ cả đường đi lẫn đường về.
2. **Thăng hạng cho một phương ngữ chưa có mô hình nào:** bước 3 không có gì để so sánh nên hệ thống chỉ hiển thị mô hình sắp đưa vào; các bước còn lại không đổi.

**Luồng ngoại lệ:**

1. **Mô hình mới kém hơn mô hình đang chạy.** Ở bước 3, hệ thống hiển thị rõ những số đo bị suy giảm và mức suy giảm. Việc thăng hạng **vẫn được phép** — có những lý do chính đáng để đưa vào một mô hình có độ chính xác tổng thể thấp hơn nhưng phủ nhiều lớp hơn — nhưng câu xác nhận nêu đích danh các số đã giảm, để quyết định không bị đưa ra do nhìn nhầm. Hệ thống không tự chặn vì một ngưỡng cứng ở đây sẽ khoá mất chính những trường hợp cần đến phán đoán của con người.

2. **Tệp mô hình không đọc được.** Ở bước 5, hệ thống từ chối đăng ký phiên bản và giữ nguyên mô hình đang phục vụ. Lý do phải kiểm ở đây chứ không phải lúc nạp: một phiên bản được đăng ký mà không có tệp sẽ hỏng ở **mọi** lần nạp về sau, kể cả sau khi máy chủ khởi động lại, và lúc đó phương ngữ mất mô hình mà không ai biết vì sao. Quản trị viên kiểm lại kho lưu trữ hoặc chọn lượt chạy khác.

3. **Dịch vụ suy luận từ chối nạp phiên bản mới.** Ở bước 7, hệ thống **giữ nguyên phiên bản cũ đang phục vụ** và báo lỗi nạp, thay vì để phương ngữ đó rơi vào trạng thái không còn mô hình nào. Bản ghi phiên bản mới vẫn tồn tại trong sổ đăng ký và vẫn là phiên bản đang hoạt động theo dữ liệu, nên có một khoảng lệch giữa "phiên bản được đánh dấu đang hoạt động" và "phiên bản thực sự đang nạp trong bộ nhớ". Khoảng lệch này được hiển thị trên màn hình giám sát (UC704) và biến mất khi dịch vụ suy luận nạp lại thành công. Quản trị viên thử nạp lại hoặc khởi động lại dịch vụ suy luận.

4. **Bảng chỉ mục nhãn của mô hình không khớp danh mục hiện tại.** Ở bước 5, nếu mô hình được huấn luyện trên một tập lớp đã thay đổi, hệ thống cảnh báo số lớp lệch và liệt kê các chỉ số không tra được. Thăng hạng vẫn thực hiện được, nhưng người dùng cuối sẽ thấy các nhãn thiếu tên. Đây là hệ quả trực tiếp của nguyên tắc không tái sử dụng chỉ số lớp đã nêu ở UC302 và UC303.

**Kết quả mong đợi:** Phương ngữ có một phiên bản mô hình đang hoạt động, được đăng ký bất biến kèm tệp mô hình, bảng chỉ mục nhãn, số đo và nguồn gốc; dịch vụ suy luận đã nạp phiên bản đó và nhật ký kiểm toán ghi lần thăng hạng. Nếu dịch vụ suy luận không nạp được, mô hình cũ tiếp tục phục vụ và phương ngữ không bao giờ rơi vào trạng thái không có mô hình nào.

---

#### UC407 — Nhận dạng ký hiệu thời gian thực

*Bảng C-41: Mô tả chức năng Nhận dạng ký hiệu thời gian thực*

| **Tên use case** | Nhận dạng ký hiệu thời gian thực | **ID** | UC407 |
|---|---|---|---|
| **Actor chính** | Người khiếm thính – khiếm ngôn | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Người ký | **Phân loại** | Phức tạp |
| **Loại** | external | **Nghiệp vụ** | 4 — Huấn luyện, đánh giá và suy luận |

**Các thành phần tham gia và mối quan tâm:**

- **Người khiếm thính – khiếm ngôn** — truyền đạt được nội dung bằng ngôn ngữ ký hiệu của mình.
- **Người dùng bình thường** — nhận được nội dung dưới dạng chữ, và dạng tiếng nếu bật (UC408).
- **Dịch vụ suy luận (S3)** — nhận cửa sổ điểm mốc và trả nhãn kèm độ tin cậy.
- **Tổ chức** — hạn mức số lần dự đoán của gói dịch vụ được tôn trọng.

**Mô tả tóm tắt:** *Người dùng thực hiện ký hiệu trước máy quay và hệ thống hiển thị liên tục nhãn nhận được, dùng mô hình đang hoạt động của phương ngữ được chọn.*

**Các mối quan hệ:**

- **Association (kết hợp):** Người khiếm thính – khiếm ngôn – Nhận dạng ký hiệu thời gian thực; Người dùng bình thường (bên nhận kết quả); Dịch vụ suy luận (S3)
- **Include (bao gồm):** không
- **Extend (mở rộng):** không *(UC114 và UC408 mở rộng use case này)*
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Người dùng mở trang nhận dạng.
2. Hệ thống liệt kê các mô hình đang hoạt động kèm phương ngữ, số lớp và ngày thăng hạng; người dùng chọn một mô hình.
3. Hệ thống xin quyền dùng máy quay và bật cơ chế theo vết bàn tay chạy **trên máy người dùng**. Hình ảnh không rời khỏi máy; thứ được gửi đi là toạ độ điểm mốc.
4. Hệ thống gom các khung điểm mốc thành cửa sổ trượt và gửi mỗi cửa sổ hoàn chỉnh tới dịch vụ suy luận, đồng thời trừ vào hạn mức số lần dự đoán của tổ chức.
5. Hệ thống hiển thị nhãn dự đoán kèm độ tin cậy, và tích luỹ các dự đoán gần đây thành một bản ghi lời đang chạy.
6. Người dùng dừng phiên; hệ thống đóng luồng gửi và trả lại quyền dùng máy quay.

**Luồng luân phiên:**

1. **Bật đầu ra giọng nói:** người dùng bật tính năng đọc thành tiếng (UC408) trong lúc đang nhận dạng; luồng chính không đổi, chỉ thêm một nhánh xử lý bản ghi lời.
2. **Dùng thử không cần tài khoản:** khách vãng lai đi theo UC114, cùng cơ chế nhưng chịu ngân sách thời gian theo ngày thay vì hạn mức dự đoán của tổ chức.

**Luồng ngoại lệ:**

1. **Phương ngữ được chọn chưa có mô hình đang hoạt động.** Ở bước 2, hệ thống nói rõ phương ngữ đó chưa có mô hình nào được thăng hạng và liệt kê các phương ngữ đã có, thay vì để danh sách trống. Người dùng chọn phương ngữ khác; chất lượng nhận dạng khi dùng mô hình của phương ngữ khác sẽ thấp hơn và hệ thống ghi chú điều đó.

2. **Độ tin cậy dưới ngưỡng hiển thị.** Ở bước 5, hệ thống **không hiển thị gì** thay vì đưa ra một phỏng đoán có khả năng sai. Với một công cụ hỗ trợ giao tiếp, một nhãn sai hiển thị dứt khoát còn tệ hơn không có nhãn: người đối thoại tin vào nó. Người dùng thấy màn hình im lặng thì ký lại rõ hơn hoặc chậm hơn; hệ thống hiển thị một chỉ báo cho biết nó vẫn đang nhận dữ liệu, để im lặng không bị hiểu là treo.

3. **Dịch vụ suy luận không sẵn sàng.** Ở bước 4, hệ thống ngừng gửi cửa sổ, hiển thị thông báo về tình trạng dịch vụ, và **vẫn giữ khung hình xem trước** để người dùng biết máy quay còn hoạt động. Số lần thử kết nối lại có trần; hết trần thì hệ thống dừng hẳn và mời thử lại sau, thay vì gửi lại vô hạn làm nặng thêm một dịch vụ đang hỏng. Các cửa sổ không gửi được **không** bị trừ vào hạn mức dự đoán.

4. **Hết hạn mức số lần dự đoán của gói dịch vụ.** Ở bước 4, hệ thống dừng luồng, hiển thị hạn mức và thời điểm đặt lại, và giữ nguyên bản ghi lời đã có. Quản trị tổ chức nâng gói dịch vụ (UC506) hoặc chờ kỳ hạn mức mới.

5. **Tốc độ khung hình của thiết bị quá thấp.** Ở bước 4, nếu máy không giữ nổi nhịp theo vết, các cửa sổ gửi đi sẽ thưa và không phản ánh đúng động tác. Hệ thống cảnh báo rằng các dự đoán sẽ không đáng tin và đề nghị đóng bớt ứng dụng khác hoặc hạ độ phân giải, thay vì tiếp tục hiển thị kết quả như thể bình thường.

6. **Mất kết nối mạng giữa phiên.** Ở bước 4, các cửa sổ trong lúc mất kết nối bị bỏ chứ không xếp hàng gửi bù — một dự đoán trễ vài giây không còn giá trị trong hội thoại và sẽ chèn nhãn sai chỗ vào bản ghi lời. Khi kết nối trở lại, hệ thống tiếp tục từ cửa sổ hiện tại và ghi một dấu ngắt quãng trên bản ghi lời.

**Kết quả mong đợi:** Người ký thấy nhãn nhận được theo thời gian thực kèm độ tin cậy, tích luỹ thành một bản ghi lời dùng để giao tiếp; hình ảnh từ máy quay không rời khỏi máy người dùng. Các dự đoán dưới ngưỡng tin cậy không được hiển thị, và các cửa sổ không gửi được không bị trừ vào hạn mức dự đoán.

---

#### UC408 — Đọc thành tiếng kết quả nhận dạng

*Bảng C-42: Mô tả chức năng Đọc thành tiếng kết quả nhận dạng*

| **Tên use case** | Đọc thành tiếng kết quả nhận dạng | **ID** | UC408 |
|---|---|---|---|
| **Actor chính** | Người dùng bình thường | **Mức độ cần thiết** | Tuỳ chọn |
| **Kích hoạt bởi** | Người dùng bật đầu ra giọng nói | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 4 — Huấn luyện, đánh giá và suy luận |

**Các thành phần tham gia và mối quan tâm:**

- **Người dùng bình thường** — nghe được nội dung mà không phải nhìn màn hình.
- **Người khiếm thính – khiếm ngôn** — thông điệp của mình tới được người nghe.
- **Dịch vụ suy luận (S3)** — thành phần tổng hợp giọng nói nhận câu và trả về âm thanh.

**Mô tả tóm tắt:** *Người dùng chuyển bản ghi lời đã nhận dạng thành tiếng nói, để người đối thoại nghe được thông điệp mà không cần đọc màn hình.*

**Các mối quan hệ:**

- **Association (kết hợp):** Người dùng bình thường – Đọc thành tiếng kết quả nhận dạng; Người khiếm thính – khiếm ngôn (bên tạo câu); Dịch vụ suy luận (S3)
- **Include (bao gồm):** không
- **Extend (mở rộng):** UC407 Nhận dạng ký hiệu thời gian thực
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Người dùng bật đầu ra giọng nói và chọn một giọng đọc trong danh sách các giọng đang có.
2. Hệ thống làm nóng trước thành phần tổng hợp giọng nói cho giọng đó, để câu đầu tiên không bị trễ hơn các câu sau.
3. Khi các dự đoán tích luỹ đủ và ổn định, hệ thống gom chúng thành một câu theo quy tắc ngắt câu đã đặt.
4. Hệ thống gửi câu tới thành phần tổng hợp giọng nói và phát đoạn âm thanh trả về.
5. Hệ thống hiển thị phần văn bản vừa đọc bên cạnh bản ghi lời, để người đối thoại đối chiếu được giữa cái được nghe và cái được nhận dạng.

**Luồng luân phiên:**

1. **Đọc lại một câu:** người dùng bấm nút phát lại trên một câu đã đọc; hệ thống dùng lại đoạn âm thanh đã có nếu còn trong bộ đệm, hoặc gửi lại câu đó ở bước 4.
2. **Tắt giọng nói giữa chừng:** người dùng tắt tính năng; bản ghi lời vẫn tiếp tục chạy như ở UC407 và không có gì trong dữ liệu bị ảnh hưởng.

**Luồng ngoại lệ:**

1. **Giọng đọc được chọn chưa được cài trên bản triển khai.** Ở bước 1, hệ thống dùng giọng mặc định và **nói rõ** đã thay giọng nào bằng giọng nào, thay vì im lặng đổi. Người dùng nghe thấy một giọng khác giọng mình chọn mà không được báo sẽ tưởng hệ thống hỏng.

2. **Thành phần tổng hợp giọng nói ngừng hoạt động.** Ở bước 4, hệ thống **vẫn giữ bản ghi lời trên màn hình**, tắt nút bật giọng nói và hiển thị lý do. Chức năng nhận dạng ở UC407 tiếp tục chạy bình thường: đầu ra giọng nói là một lớp bổ sung, và hỏng lớp bổ sung không được phép làm hỏng chức năng chính. Người dùng đọc chữ trên màn hình cho tới khi dịch vụ trở lại.

3. **Dự đoán lặp lại liên tiếp.** Ở bước 3, hệ thống **không** đọc lại một nhãn vẫn đang giống nhãn trước đó. Một ký hiệu giữ nguyên trong nhiều cửa sổ liên tiếp là **một** ký hiệu, không phải nhiều ký hiệu; nếu đọc theo từng cửa sổ, người nghe sẽ nghe một từ lặp lại hàng chục lần. Quy tắc gộp này áp ở tầng bản ghi lời chứ không ở tầng mô hình.

4. **Câu quá dài so với giới hạn của thành phần tổng hợp.** Ở bước 4, hệ thống cắt câu tại điểm ngắt gần nhất và đọc thành nhiều đoạn liên tiếp, thay vì để lời gọi bị từ chối và mất cả câu. Việc cắt được thực hiện theo ranh giới nhãn nên không có ký hiệu nào bị xé đôi.

**Kết quả mong đợi:** Nội dung đã nhận dạng được phát thành tiếng bằng giọng người dùng chọn hoặc bằng giọng mặc định kèm thông báo thay thế, mỗi ký hiệu ổn định chỉ đọc một lần, và phần văn bản đã đọc hiển thị bên cạnh bản ghi lời để đối chiếu. Khi thành phần tổng hợp giọng nói hỏng, chức năng nhận dạng vẫn chạy nguyên vẹn.

---

#### UC409 — Chuẩn bị bản phát hành nghiên cứu

*Bảng C-43: Mô tả chức năng Chuẩn bị bản phát hành nghiên cứu*

| **Tên use case** | Chuẩn bị bản phát hành nghiên cứu | **ID** | UC409 |
|---|---|---|---|
| **Actor chính** | Biên tập viên / Nghiên cứu sinh | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Nghiên cứu sinh chạy dây chuyền phát hành | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 4 — Huấn luyện, đánh giá và suy luận |

**Các thành phần tham gia và mối quan tâm:**

- **Nghiên cứu sinh** — có một bản phát hành trích dẫn được và tái lập được.
- **Hội đồng đánh giá** — kiểm chứng được từng bước đã chạy và kết quả kiểm tổng của từng bước.
- **Người ký** — chỉ mẫu đủ điều kiện đồng thuận có mặt trong bản phát hành.

**Mô tả tóm tắt:** *Nghiên cứu sinh dựng một bản phát hành nghiên cứu trích dẫn được: kiểm tra mẫu, đóng băng bản kê khai bộ dữ liệu, dẫn xuất các phép chia tập, và ghi lại toàn bộ quá trình. Dây chuyền dừng ở bước hỏng đầu tiên nên một bản phát hành không bao giờ ở trạng thái dựng dở.*

**Các mối quan hệ:**

- **Association (kết hợp):** Biên tập viên / Nghiên cứu sinh – Chuẩn bị bản phát hành nghiên cứu
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Nghiên cứu sinh chạy dây chuyền phát hành trên máy triển khai, nêu tên đợt thu và số hiệu bản kê khai sẽ tạo.
2. Hệ thống chạy bộ kiểm tra các mẫu thử nghiệm của đợt thu, để bảo đảm dữ liệu đọc được và đúng định dạng trước khi tiêu tài nguyên cho các bước sau.
3. Hệ thống rà soát bộ dữ liệu để phát hiện mẫu trùng lặp — cùng nội dung nhưng khác mã định danh — và báo cáo số lượng cùng vị trí.
4. Hệ thống tạo bản kê khai bộ dữ liệu với số hiệu đã nêu, và **không bao giờ ghi đè** một số hiệu đã tồn tại.
5. Hệ thống kiểm tra lại chính bản kê khai vừa tạo, gồm cả kiểm tổng của từng tệp được liệt kê trong đó, để một tệp bị sửa sau khi kê khai sẽ lộ ra ngay.
6. Hệ thống dẫn xuất phép chia theo mẫu, rồi thử dẫn xuất phép chia **tách rời người ký** cho từng hồ sơ thu mẫu.
7. Hệ thống tổng hợp kết quả và ghi nhật ký phát hành lưu mọi lệnh đã chạy, mã thoát của từng lệnh, và các kiểm tổng thu được.

**Luồng luân phiên:**

1. **Chạy lại một bước riêng lẻ:** sau khi sửa nguyên nhân của một bước hỏng, nghiên cứu sinh chạy lại dây chuyền từ bước đó thay vì từ đầu. Nhật ký phát hành ghi cả các lần chạy trước, nên lịch sử không bị mất.

**Luồng ngoại lệ:**

1. **Một bước trong dây chuyền hỏng.** Ở bất kỳ bước nào từ 2 đến 7, dây chuyền dừng **ngay tại bước hỏng đầu tiên** và các bước sau không chạy. Nhờ vậy một bản phát hành hoặc đầy đủ hoặc không tồn tại, chứ không bao giờ ở trạng thái dựng dở — trạng thái nguy hiểm nhất vì nó trông giống một bản phát hành thật. Nghiên cứu sinh đọc mã thoát trong nhật ký, sửa nguyên nhân, rồi chạy lại theo luồng luân phiên 1.

2. **Không đủ đa dạng người ký để dựng phép chia tách rời người ký.** Ở bước 6, việc không dựng được phép chia này được **báo cáo chứ không làm dừng dây chuyền**. Đây là quyết định thiết kế quan trọng: số người ký quá ít là một **sự thật về bộ dữ liệu**, không phải một lỗi của dây chuyền, và che nó đi bằng cách coi như lỗi rồi dừng lại mới là sai lầm thật sự. Bản phát hành vẫn được dựng, kèm ghi chú rằng phép chia tách rời người ký không khả dụng cho hồ sơ thu mẫu nào. Kết quả đánh giá trên bản phát hành đó phải được đọc kèm ghi chú này.

3. **Số hiệu bản kê khai đã tồn tại.** Ở bước 4, hệ thống từ chối ghi đè và dừng dây chuyền. Một bản kê khai đã đóng băng là thứ các bài công bố trích dẫn tới; ghi đè nó sẽ làm mọi trích dẫn cũ trỏ tới một nội dung khác. Nghiên cứu sinh chọn một số hiệu mới.

4. **Phát hiện mẫu trùng lặp.** Ở bước 3, hệ thống báo cáo số lượng nhưng **không** tự loại bỏ. Việc tự loại sẽ thay đổi bộ dữ liệu mà người dựng bản phát hành không biết; quyết định giữ hay bỏ thuộc về họ, vì hai bản ghi giống nhau có thể là một lỗi nhân bản, cũng có thể là hai lần thu hợp lệ cho cùng một ký hiệu.

5. **Kiểm tổng của một tệp không khớp bản kê khai.** Ở bước 5, dây chuyền dừng và nêu đích danh tệp lệch. Nguyên nhân có thể là tệp bị ghi lại bởi một lượt xử lý chạy song song, hoặc tệp hỏng trong lúc truyền. Nghiên cứu sinh không được sửa bản kê khai cho khớp tệp — chiều đúng là điều tra vì sao tệp đổi, rồi tạo bản kê khai mới nếu thay đổi là hợp lệ.

6. **Kỳ vọng dây chuyền huấn luyện luôn một mô hình.** Sau bước 7, **không** mô hình nào được huấn luyện. Một lượt chạy chính thức phải được khởi động riêng và khai báo rõ mục đích nghiên cứu (UC401), để không ai vô tình huấn luyện một mô hình rồi dùng số đo của nó cho bài công bố mà không qua bước khai báo. Ranh giới này được nêu ngay trong báo cáo tổng kết ở bước 7.

**Kết quả mong đợi:** Bản phát hành hoặc đầy đủ hoặc không tồn tại: khi thành công, có một bản kê khai đóng băng không ghi đè số hiệu cũ, các phép chia tập đã dẫn xuất, và một nhật ký phát hành lưu mọi lệnh, mã thoát cùng kiểm tổng. Việc không dựng được phép chia tách rời người ký được báo cáo như một sự thật về bộ dữ liệu chứ không làm dừng dây chuyền, và không mô hình nào được huấn luyện từ bước này.

---

### 5.5 Nghiệp vụ 5 — Tổ chức và đăng ký dịch vụ

#### UC501 — Quản lý tổ chức

*Bảng C-44: Mô tả chức năng Quản lý tổ chức*

| **Tên use case** | Quản lý tổ chức | **ID** | UC501 |
|---|---|---|---|
| **Actor chính** | Quản trị nền tảng | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Quản trị nền tảng | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 5 — Tổ chức và đăng ký dịch vụ |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị nền tảng** — tạo và quản lý ranh giới dữ liệu của từng tổ chức.
- **Tổ chức mới** — có ranh giới dữ liệu riêng ngay từ khi được tạo.
- **Người dùng được gắn** — biết mình thuộc về tổ chức nào.

**Mô tả tóm tắt:** *Quản trị nền tảng tạo tổ chức, sửa thuộc tính, gắn tài khoản vào tổ chức nhà và xoá các tổ chức không còn dùng.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị nền tảng – Quản lý tổ chức
- **Include (bao gồm):** không
- **Extend (mở rộng):** không *(UC310 mở rộng use case này)*
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở trang Tổ chức. Hệ thống liệt kê các tổ chức kèm mã định danh, số thành viên, gói dịch vụ và trạng thái.
2. Quản trị viên bấm "Tổ chức mới" và nhập tên hiển thị, mã định danh ngắn và gói dịch vụ ban đầu.
3. Hệ thống kiểm mã định danh đúng dạng và chưa bị dùng, rồi tạo tổ chức cùng ranh giới dữ liệu riêng của nó — mọi bảng dữ liệu nghiệp vụ đều mang cột tổ chức và chịu chính sách cách ly ở tầng cơ sở dữ liệu.
4. Hệ thống khởi tạo danh mục cho tổ chức từ bản mẫu dùng chung (UC310) và hiển thị tổ chức mới.
5. Quản trị viên gắn một tài khoản đã có vào tổ chức làm tổ chức nhà và cấp vai quản trị tổ chức, để tổ chức có người chịu trách nhiệm ngay từ đầu.
6. Hệ thống ghi mục kiểm toán cho cả việc tạo tổ chức lẫn việc gắn tài khoản.

**Luồng luân phiên:**

1. **Sửa thuộc tính tổ chức:** quản trị viên đổi tên hiển thị hoặc gói dịch vụ từ danh sách ở bước 1. Mã định danh **không** đổi được sau khi tạo, vì nó là thứ mọi dòng dữ liệu của tổ chức tham chiếu tới.
2. **Xoá một tổ chức không còn dùng:** quản trị viên chọn xoá từ danh sách. Hệ thống chỉ cho xoá khi tổ chức không còn giữ dữ liệu; nếu còn, phải xoá sạch dữ liệu trước (UC508) — một hành động riêng, có chủ đích và có xác thực lại.

**Luồng ngoại lệ:**

1. **Mã định danh đã được dùng.** Ở bước 3, hệ thống từ chối và gợi ý một mã còn trống dựa trên tên tổ chức. Không có tổ chức nào được tạo. Mã định danh phải là duy nhất trong toàn nền tảng vì nó là khoá cách ly dữ liệu; hai tổ chức trùng mã sẽ nhìn thấy dữ liệu của nhau, tức là hỏng đúng tính chất quan trọng nhất của hệ thống.

2. **Xoá một tổ chức còn giữ dữ liệu.** Ở luồng luân phiên 2, hệ thống từ chối và nêu số mẫu, số lớp còn lại. Lý do tách làm hai thao tác: xoá bản ghi tổ chức là thao tác nhẹ và dễ bấm nhầm, còn phá huỷ dữ liệu là thao tác không hoàn tác được; gộp chúng vào một nút sẽ khiến một cú bấm nhầm ở màn hình danh sách xoá mất dữ liệu của cả một tổ chức. Quản trị viên chạy UC508 trước, và nên đề nghị tổ chức xuất dữ liệu (UC507) trước đó nữa.

3. **Quản trị tổ chức muốn tự gắn tài khoản vào tổ chức mình.** Ở bước 5, thao tác gắn tài khoản **không** dành cho quản trị tổ chức mà là đặc quyền của quản trị nền tảng. Nếu cho phép, một quản trị tổ chức chỉ cần biết mã định danh hoặc địa chỉ thư của một người là kéo được người đó vào tổ chức mình mà họ không hay biết — và từ đó dữ liệu của người đó nằm trong phạm vi tổ chức ấy. Đường vào đúng của một người là lời mời, tức là có sự đồng ý của cả hai phía (UC502, UC503).

4. **Chuyển quản trị viên cuối cùng ra khỏi một tổ chức còn thành viên.** Ở bước 5, hệ thống từ chối. Một tổ chức còn người dùng mà không còn ai có quyền quản trị là trạng thái chỉ quản trị nền tảng gỡ được, và nó thường chỉ lộ ra khi có người cần đổi vai gấp. Quản trị viên phải cấp vai quản trị cho một thành viên khác trước (UC504).

5. **Khởi tạo danh mục thất bại sau khi tổ chức đã được tạo.** Ở bước 4, nếu lượt nhân bản danh mục hỏng, tổ chức **vẫn tồn tại** nhưng có danh mục trống. Hệ thống báo lỗi nêu rõ tình trạng đó thay vì xoá tổ chức vừa tạo. Quản trị viên chạy lại lượt nhân bản (UC310); vì lượt đó chỉ điền chỗ trống nên chạy lại là an toàn.

**Kết quả mong đợi:** Tổ chức mới tồn tại với mã định danh duy nhất, ranh giới dữ liệu riêng, danh mục đã mồi từ bản mẫu, và ít nhất một tài khoản giữ vai quản trị tổ chức. Nhật ký kiểm toán ghi cả lần tạo lẫn lần gắn tài khoản; nếu bước mồi danh mục hỏng, tổ chức vẫn tồn tại và tình trạng thiếu danh mục được báo rõ thay vì bị dọn ngầm.

---

#### UC503 — Chấp nhận lời mời

*Bảng C-45: Mô tả chức năng Chấp nhận lời mời*

| **Tên use case** | Chấp nhận lời mời | **ID** | UC503 |
|---|---|---|---|
| **Actor chính** | Khách vãng lai | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Khách mở liên kết lời mời | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 5 — Tổ chức và đăng ký dịch vụ |

**Các thành phần tham gia và mối quan tâm:**

- **Người được mời** — gia nhập đúng tổ chức, đúng vai.
- **Quản trị tổ chức** — lời mời chỉ tiêu thụ một lần, đúng người.
- **Nền tảng** — không tạo tài khoản nào từ một lời mời đã hết hiệu lực.

**Mô tả tóm tắt:** *Người được mời gia nhập tổ chức. Một lời mời được tiêu thụ tại đúng một thời điểm — lúc tài khoản được tạo — nên việc chấp nhận lời mời và việc đăng ký là cùng một hành động, và mã mời quyết định tổ chức cùng vai của tài khoản mới.*

> **Ranh giới hiện thực:** lời mời **chỉ** được tiêu thụ trên đường đăng ký. Người **đã có tài khoản** hiện **không có đường nào** tự chấp nhận lời mời — đây là một khoảng trống thật của hệ thống, không phải chi tiết bị bỏ sót khi viết đặc tả. Xem nhánh ngoại lệ 1.

**Các mối quan hệ:**

- **Association (kết hợp):** Khách vãng lai – Chấp nhận lời mời
- **Include (bao gồm):** UC102 Đăng ký theo lời mời
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Người được mời mở liên kết trong thư mời. Hệ thống đọc mã mời và hiển thị tổ chức mời, địa chỉ được mời và vai được đề nghị.
2. Người được mời tạo tài khoản qua biểu mẫu lời mời (UC102).
3. Hệ thống kiểm lại mã mời **đúng lúc tạo tài khoản**: chưa hết hạn, chưa bị thu hồi, chưa được chấp nhận bởi ai.
4. Hệ thống tạo tài khoản, gắn vào tổ chức mời với vai đã ghi trong lời mời, và đóng dấu lời mời là đã được chấp nhận bởi chính tài khoản đó.
5. Hệ thống ghi một mục vào nhật ký kiểm toán và thông báo cho các quản trị viên đã phát lời mời.
6. Hệ thống đưa người dùng vào phiên làm việc và chuyển tới bảng điều khiển của tổ chức.

**Luồng luân phiên:**

1. **Lời mời phát cho một vai đặc biệt:** nếu lời mời đề nghị vai biên tập hoặc quản trị tổ chức, tài khoản mới nhận vai đó ngay khi tạo, không cần một bước cấp vai riêng. Vai được lấy từ lời mời chứ không từ dữ liệu người dùng gửi lên.

**Luồng ngoại lệ:**

1. **Người được mời đã có tài khoản.** Ở bước 2, **không có đường tự phục vụ nào**. Người đó phải hoặc đăng ký một tài khoản **mới** trên địa chỉ được mời, hoặc nhờ quản trị nền tảng gắn tài khoản đang có vào tổ chức (UC501). Đây là khoảng trống đã nêu ở phần ranh giới hiện thực, và hệ quả nhìn thấy được của nó là: danh sách lời mời của một tổ chức có thể hiển thị một lời mời mà người nhận **không cách nào** chấp nhận, cho tới khi nó hết hạn. Cách xử lý tạm thời trong vận hành là quản trị tổ chức báo cho quản trị nền tảng để gắn thủ công. Việc mô tả thẳng khoảng trống này quan trọng hơn việc viết một luồng nghe hợp lý mà hệ thống không có.

2. **Lời mời đã hết hiệu lực.** Ở bước 3, nếu mã đã hết hạn, đã bị thu hồi hoặc đã được chấp nhận, hệ thống từ chối và mời người dùng xin một lời mời mới. Phép kiểm chạy **trước** khi tạo tài khoản, nên một mã cũ không bao giờ để lại một tài khoản thật nằm sai tổ chức — thứ tự này là điều kiện để hệ thống không bao giờ ở trạng thái nửa vời.

3. **Hai người cùng mở một liên kết mời.** Ở bước 4, dấu chấp nhận chỉ được ghi khi ô đó còn trống, và phép ghi có điều kiện này diễn ra trong một câu lệnh duy nhất ở cơ sở dữ liệu. Trong hai lượt chấp nhận gần như đồng thời, đúng một lượt thắng; lượt còn lại nhận thông báo rằng lời mời đã được người khác chấp nhận và **không** có tài khoản nào được tạo cho họ. Nếu không có ràng buộc này, một liên kết mời bị chuyển tiếp cho nhiều người sẽ tạo ra nhiều tài khoản trong tổ chức mà quản trị viên không hề mời.

4. **Người dùng sửa địa chỉ trong biểu mẫu.** Ở bước 2, địa chỉ được mời do mã mời quyết định; mọi thay đổi ở phía trình duyệt đều bị bỏ qua và yêu cầu mang địa chỉ khác bị từ chối, như đã mô tả ở UC102. Một lời mời gắn với đúng một địa chỉ.

**Kết quả mong đợi:** Người được mời có một tài khoản thuộc đúng tổ chức mời với đúng vai đã hứa, và lời mời mang dấu đã được chấp nhận bởi chính tài khoản đó nên không dùng lại được. Trong hai lượt chấp nhận đồng thời chỉ một lượt tạo được tài khoản; với lời mời hết hiệu lực, không tài khoản nào được tạo.

---

#### UC504 — Đổi vai thành viên

*Bảng C-46: Mô tả chức năng Đổi vai thành viên*

| **Tên use case** | Đổi vai thành viên | **ID** | UC504 |
|---|---|---|---|
| **Actor chính** | Quản trị tổ chức | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Quản trị tổ chức | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 5 — Tổ chức và đăng ký dịch vụ |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị tổ chức** — điều chỉnh được quyền ghi của từng thành viên.
- **Thành viên bị đổi vai** — biết phạm vi thao tác của mình thay đổi.
- **Bộ phận kiểm toán** — đổi vai là đổi quyền, nên giá trị cũ là một phần của bằng chứng.

**Mô tả tóm tắt:** *Quản trị tổ chức thay đổi vai của một thành viên trong tổ chức, qua đó thay đổi phạm vi những gì thành viên đó được ghi.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị tổ chức – Đổi vai thành viên
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở danh sách thành viên của tổ chức.
2. Hệ thống hiển thị từng thành viên kèm vai hiện tại, ngày gia nhập và lần hoạt động gần nhất.
3. Quản trị viên chọn một thành viên và chọn vai mới trong danh sách vai hợp lệ.
4. Hệ thống kiểm người gọi có vai quản trị trên **chính tổ chức đó**, không phải trên một tổ chức khác mà họ cũng là thành viên.
5. Hệ thống lưu vai mới và ghi một mục kiểm toán lưu **cả vai cũ lẫn vai mới**, người thực hiện và thời điểm.
6. Hệ thống hiển thị danh sách thành viên đã cập nhật. Vai mới có hiệu lực ở lần kiểm quyền kế tiếp của thành viên đó, không cần họ đăng nhập lại.

**Luồng luân phiên:**

1. **Nâng vai cho một thành viên mới:** đây là đường đi thường gặp sau khi một người gia nhập với vai mặc định và chứng minh được năng lực; các bước không đổi.

**Luồng ngoại lệ:**

1. **Hạ vai của quản trị viên duy nhất.** Ở bước 4, hệ thống từ chối khi thành viên bị đổi là người duy nhất còn vai quản trị trong tổ chức. Nếu cho phép, tổ chức rơi vào trạng thái không ai quản trị được và chỉ quản trị nền tảng gỡ được — một tình huống thường xảy ra do nhầm lẫn chứ không do cố ý. Quản trị viên cấp vai quản trị cho người khác trước rồi mới hạ vai.

2. **Quản trị viên tự hạ vai của chính mình.** Ở bước 3, hệ thống hỏi xác nhận rõ ràng và nêu rằng tài khoản sẽ **không tự hoàn tác được** thao tác này. Nếu vẫn còn quản trị viên khác thì thao tác được phép; nếu không, nó rơi vào ngoại lệ 1. Sau khi hạ vai, người dùng phải nhờ một quản trị viên khác nâng lại.

3. **Giá trị vai không hợp lệ.** Ở bước 3, một giá trị vai không nằm trong tập vai hệ thống định nghĩa bị từ chối. Điểm cần lưu ý về kiểm toán: mục kiểm toán ghi vai **đã thật sự lưu**, không ghi lại chuỗi thô mà người gọi gửi lên. Ghi chuỗi thô sẽ biến nhật ký kiểm toán thành nơi lưu dữ liệu chưa qua kiểm tra, và một nhật ký như vậy không dùng làm bằng chứng được.

4. **Thành viên đã bị gỡ khỏi tổ chức trong lúc màn hình đang mở.** Ở bước 5, hệ thống báo rằng quan hệ thành viên không còn tồn tại và không tạo lại nó. Đổi vai cho một người không còn trong tổ chức sẽ âm thầm khôi phục quyền truy cập của họ — đúng thứ mà thao tác gỡ thành viên vừa loại bỏ. Quản trị viên làm mới danh sách; muốn người đó quay lại thì mời lại (UC502).

**Kết quả mong đợi:** Thành viên mang vai mới và phạm vi thao tác thay đổi ngay ở lần kiểm quyền kế tiếp, không cần đăng nhập lại. Nhật ký kiểm toán lưu cả vai cũ lẫn vai mới, và tổ chức luôn còn ít nhất một tài khoản giữ vai quản trị.

---

#### UC505 — Gỡ thành viên khỏi tổ chức

*Bảng C-47: Mô tả chức năng Gỡ thành viên khỏi tổ chức*

| **Tên use case** | Gỡ thành viên khỏi tổ chức | **ID** | UC505 |
|---|---|---|---|
| **Actor chính** | Quản trị tổ chức | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Quản trị tổ chức | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 5 — Tổ chức và đăng ký dịch vụ |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị tổ chức** — kiểm soát được ai còn quyền vào dữ liệu của tổ chức.
- **Thành viên bị gỡ** — vẫn giữ tài khoản của mình, chỉ mất quyền trong tổ chức đó.
- **Tổ chức** — mẫu đã đóng góp vẫn ở lại với tổ chức.

**Mô tả tóm tắt:** *Quản trị tổ chức gỡ một thành viên khỏi tổ chức. Người đó vẫn giữ tài khoản; chỉ quan hệ thành viên và quyền truy cập đi kèm chấm dứt.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị tổ chức – Gỡ thành viên khỏi tổ chức
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở danh sách thành viên và bấm "Gỡ" trên một thành viên.
2. Hệ thống hiển thị phần đóng góp của thành viên đó — số mẫu, số phiên thu — và nêu rõ rằng dữ liệu **vẫn ở lại** với tổ chức sau khi họ rời đi.
3. Quản trị viên xác nhận.
4. Hệ thống kiểm người gọi có vai quản trị trên tổ chức, và kiểm người bị gỡ không phải quản trị viên cuối cùng.
5. Hệ thống kết thúc quan hệ thành viên, thu hồi các phiên làm việc đang mở trong phạm vi tổ chức đó, và ghi một mục vào nhật ký kiểm toán.
6. Hệ thống gửi thông báo cho thành viên bị gỡ, để họ không phải đoán vì sao dữ liệu đột nhiên biến mất khỏi màn hình của mình.

**Luồng luân phiên:**

1. **Thành viên tự rời tổ chức:** hệ thống hiện chưa có đường tự phục vụ cho việc này; người dùng muốn rời phải yêu cầu quản trị tổ chức thực hiện. Đây là một giới hạn cần biết khi đọc mô hình quyền.

**Luồng ngoại lệ:**

1. **Người bị gỡ là quản trị viên cuối cùng.** Ở bước 4, hệ thống từ chối, theo cùng lý do đã nêu ở UC504.

2. **Tổ chức bị gỡ là tổ chức nhà của thành viên.** Ở bước 5, thành viên vẫn đăng nhập được nhưng không còn tổ chức nào làm ngữ cảnh ghi dữ liệu, nên mọi thao tác ghi của họ bị từ chối cho tới khi quản trị nền tảng gán một tổ chức nhà khác (UC501) hoặc họ nhận một lời mời mới. Hệ thống nêu rõ điều này trong thông báo ở bước 6, vì nếu không, người dùng sẽ thấy một tài khoản đăng nhập được nhưng "không làm gì được" và không biết vì sao.

3. **Dữ liệu đã đóng góp của thành viên.** Ở bước 2, mẫu **không** bị xoá theo quan hệ thành viên. Việc xoá chúng là một hành động riêng (UC211) và kéo theo hệ quả về đồng thuận, vì người ký vẫn là chủ thể dữ liệu kể cả sau khi rời tổ chức và vẫn giữ quyền rút đồng thuận (UC113). Trộn hai việc — gỡ người và xoá dữ liệu — vào một thao tác sẽ khiến một thay đổi nhân sự bình thường phá huỷ dữ liệu nghiên cứu.

4. **Thành viên đang có tác vụ nền chạy dở.** Ở bước 5, các tác vụ xử lý hoặc huấn luyện do họ khởi động **vẫn chạy tiếp** tới khi hoàn tất, vì chúng đã được cấp phép ở thời điểm khởi động và kết quả thuộc về tổ chức. Điều bị chặn ngay lập tức là các thao tác mới. Quản trị viên muốn dừng hẳn thì huỷ lượt chạy (UC403).

**Kết quả mong đợi:** Quan hệ thành viên chấm dứt, các phiên làm việc trong phạm vi tổ chức bị thu hồi, và người bị gỡ nhận được thông báo. Tài khoản của họ vẫn tồn tại, dữ liệu họ đã đóng góp vẫn ở lại với tổ chức, và quyền rút đồng thuận của họ với tư cách chủ thể dữ liệu không bị ảnh hưởng.

---

#### UC506 — Quản lý đăng ký dịch vụ

*Bảng C-48: Mô tả chức năng Quản lý đăng ký dịch vụ*

| **Tên use case** | Quản lý đăng ký dịch vụ | **ID** | UC506 |
|---|---|---|---|
| **Actor chính** | Quản trị tổ chức | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Quản trị tổ chức | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 5 — Tổ chức và đăng ký dịch vụ |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị tổ chức** — biết hạn mức còn lại và kỳ hạn kết thúc khi nào.
- **Thành viên tổ chức** — không bị chặn ghi giữa một buổi thu vì hết hạn mà không ai báo trước.
- **Dịch vụ gửi tin (S1)** — chuyển các thư nhắc trước hạn.

**Mô tả tóm tắt:** *Quản trị tổ chức xem đăng ký dịch vụ của tổ chức — gói, hạn mức, thời điểm kết thúc kỳ — và bật hoặc tắt cơ chế tự động gia hạn.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị tổ chức – Quản lý đăng ký dịch vụ; Dịch vụ gửi tin (S1)
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở trang Đăng ký dịch vụ.
2. Hệ thống hiển thị gói hiện tại, từng hạn mức mà gói cấp — số mẫu, số lần dự đoán, dung lượng lưu trữ, số thành viên — kèm mức đã dùng trên từng hạn mức và thời điểm kết thúc kỳ hiện tại.
3. Hệ thống hiển thị trạng thái bật hoặc tắt của cơ chế tự động gia hạn, và lịch sử các kỳ đã qua.
4. Quản trị viên đổi trạng thái tự động gia hạn và xác nhận.
5. Hệ thống lưu thiết lập và ghi một mục vào nhật ký kiểm toán.
6. Khi gần tới thời điểm kết thúc kỳ, một tác vụ theo lịch gửi các thư nhắc qua dịch vụ gửi tin, theo các mốc thời gian đã cấu hình.

**Luồng luân phiên:**

1. **Đổi gói dịch vụ:** quản trị viên chọn một gói khác; hệ thống ghi nhận thay đổi và áp hạn mức mới từ kỳ kế tiếp. Việc thanh toán không diễn ra trong hệ thống — xem ngoại lệ 4.

**Luồng ngoại lệ:**

1. **Kỳ hạn đã kết thúc mà chưa gia hạn.** Ở bước 2, hệ thống hiển thị thời gian ân hạn còn lại trước khi tổ chức chuyển sang chế độ hạn chế, thay vì chỉ hiện một trạng thái quá hạn không kèm hệ quả. Trong thời gian ân hạn, tổ chức **vẫn ghi được**: đây là quyết định có chủ ý, vì cắt quyền ghi ngay khi hết hạn sẽ làm mất công của một buổi thu đang dở dang vì một lý do hành chính. Quản trị viên gia hạn trong khoảng này thì mọi thứ tiếp diễn bình thường.

2. **Hết cả thời gian ân hạn.** Hệ thống chuyển tổ chức sang chế độ khoá mềm: **chặn thao tác ghi nhưng vẫn cho đọc và xuất dữ liệu**. Nguyên tắc là một tổ chức luôn lấy lại được dữ liệu của chính mình, kể cả khi quan hệ thương mại đã chấm dứt; khoá cả đường đọc sẽ biến một tranh chấp hợp đồng thành một vụ giữ dữ liệu làm con tin. Quản trị viên xuất dữ liệu (UC507) rồi gia hạn hoặc kết thúc.

3. **Hạn mức bị vượt trong kỳ.** Ở bước 2, khi một hạn mức chạm trần, các thao tác tiêu hạn mức đó bị từ chối kèm thông báo nêu đích danh hạn mức nào, còn các chức năng khác vẫn chạy. Chẳng hạn hết hạn mức mẫu thì không tải lên được nhưng vẫn nhận dạng và huấn luyện được. Việc tách theo từng hạn mức thay vì khoá toàn bộ giúp tổ chức tiếp tục làm việc trong phần còn dùng được.

4. **Không có cơ chế thu tiền trong hệ thống.** Ở bước 4 và ở luồng luân phiên 1, hệ thống **không** thực hiện thanh toán và không kết nối tới bất kỳ cổng thanh toán nào. Thay đổi gói được ghi nhận như một sự kiện quản trị, còn việc thanh toán diễn ra ngoài nền tảng theo thoả thuận riêng. Đây là ranh giới hiện thực cần nêu rõ để người đọc không suy ra rằng có một luồng thanh toán đang tồn tại; mọi trạng thái "đã thanh toán" trong hệ thống đều do người vận hành đặt.

5. **Thư nhắc không gửi được.** Ở bước 6, nếu dịch vụ gửi tin hỏng, kỳ hạn **vẫn** trôi theo lịch và tổ chức có thể chạm ân hạn mà không nhận được cảnh báo nào. Vì vậy trạng thái kỳ hạn luôn hiển thị ngay trên bảng điều khiển của tổ chức chứ không chỉ trong thư — một cơ chế nhắc phụ thuộc hoàn toàn vào thư điện tử là cơ chế sẽ im lặng đúng lúc cần nhất.

**Kết quả mong đợi:** Quản trị tổ chức nhìn thấy đúng gói, từng hạn mức kèm mức đã dùng, thời điểm kết thúc kỳ và trạng thái tự động gia hạn; thiết lập vừa đổi đã được lưu và ghi kiểm toán. Khi kỳ hạn kết thúc, tổ chức đi qua ân hạn rồi mới tới khoá mềm, và trong khoá mềm vẫn đọc và xuất được dữ liệu của chính mình.

---

#### UC507 — Yêu cầu xuất dữ liệu tổ chức

*Bảng C-49: Mô tả chức năng Yêu cầu xuất dữ liệu tổ chức*

| **Tên use case** | Yêu cầu xuất dữ liệu tổ chức | **ID** | UC507 |
|---|---|---|---|
| **Actor chính** | Quản trị tổ chức | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Quản trị tổ chức | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 5 — Tổ chức và đăng ký dịch vụ |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị tổ chức** — lấy lại được toàn bộ dữ liệu của tổ chức mình.
- **Tổ chức khác** — không bao giờ tải được bản xuất của tổ chức này.
- **Kho lưu trữ ngoài (S2)** — giữ tệp kho lưu và phục vụ liên kết tải có thời hạn.

**Mô tả tóm tắt:** *Quản trị tổ chức yêu cầu một bản xuất đầy đủ dữ liệu của tổ chức — mẫu, danh mục, thành viên, nhật ký kiểm toán — và tải về khi kho lưu đã dựng xong.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị tổ chức – Yêu cầu xuất dữ liệu tổ chức; Kho lưu trữ ngoài (S2)
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở trang tổ chức và bấm "Xuất dữ liệu".
2. Hệ thống liệt kê nội dung bản xuất sẽ gồm những gì — mẫu và tệp đặc trưng, danh mục lớp và phương ngữ, danh sách thành viên, nhật ký kiểm toán trong phạm vi tổ chức — kèm ước tính dung lượng, rồi hỏi xác nhận.
3. Quản trị viên xác nhận. Hệ thống nhận yêu cầu, tạo bản ghi bản xuất ở trạng thái đang dựng và trả về mã bản xuất.
4. Tiến trình nền dựng kho lưu dữ liệu của tổ chức và lưu vào kho lưu trữ. Tác vụ có trần thử lại; hết trần thì chuyển sang trạng thái thất bại thay vì chạy lại vô hạn.
5. Hệ thống chuyển bản xuất sang trạng thái sẵn sàng, kèm dung lượng thật và thời hạn giữ tệp.
6. Quản trị viên tải kho lưu qua một liên kết có thời hạn ngắn, được sinh riêng cho mỗi lần tải.

**Luồng luân phiên:**

1. **Xuất trước khi xoá dữ liệu:** khi tổ chức chấm dứt hợp tác, lượt xuất này được chạy trước UC508 và kết quả của nó được ghi nhận trong bản xem trước của lần xoá.
2. **Tải lại bản xuất còn hạn:** quản trị viên tải lại từ danh sách bản xuất; hệ thống sinh một liên kết mới có thời hạn thay vì tái sử dụng liên kết cũ, để một liên kết bị chuyển tiếp không sống mãi.

**Luồng ngoại lệ:**

1. **Đã có một bản xuất đang dựng.** Ở bước 3, hệ thống từ chối yêu cầu thứ hai chạy song song và chỉ tới bản đang dựng kèm tiến độ. Một bản xuất đầy đủ đọc toàn bộ dữ liệu của tổ chức, nên cho phép nhiều lượt chạy cùng lúc là cách nhanh nhất để một tổ chức tự làm nghẽn hệ thống. Quản trị viên đợi bản hiện tại xong.

2. **Kho lưu đã quá thời hạn giữ.** Ở bước 6, liên kết bị từ chối và bản xuất hiển thị ở trạng thái đã hết hạn. Tệp bị dọn theo lịch để không tích tụ các bản sao đầy đủ dữ liệu nằm ngoài vòng kiểm soát thông thường — bản thân một kho lưu như vậy là một điểm rủi ro dữ liệu. Quản trị viên yêu cầu một bản xuất mới.

3. **Quản trị viên của tổ chức khác mở liên kết.** Ở bước 6, hệ thống từ chối. Bản xuất thuộc về tổ chức đã yêu cầu nó, và quyền tải được kiểm theo tổ chức chứ không chỉ theo việc người gọi có nắm được đường dẫn hay không. Liên kết có thời hạn là lớp bảo vệ thứ hai chứ không phải lớp duy nhất.

4. **Dựng kho lưu thất bại.** Ở bước 4, hệ thống đánh dấu bản xuất là thất bại kèm lý do và **không** giữ lại kho lưu dở dang. Một tệp nén dở dang tải về được sẽ trông như một bản xuất thành công cho tới khi có người mở nó ra — thường là rất lâu sau, khi dữ liệu gốc đã không còn. Quản trị viên chạy lại; nếu nguyên nhân là dung lượng, kỹ sư vận hành xử lý (UC704).

5. **Dữ liệu thay đổi trong lúc đang dựng.** Ở bước 4, bản xuất phản ánh trạng thái tại thời điểm nó đọc từng phần, nên các thay đổi xảy ra giữa chừng có thể vào hoặc không vào bản xuất. Hệ thống ghi thời điểm bắt đầu và kết thúc vào bản kê khai của kho lưu, để người dùng biết bản xuất tương ứng với khoảng thời gian nào thay vì giả định nó là một ảnh chụp tức thời.

**Kết quả mong đợi:** Tổ chức có một kho lưu chứa đủ dữ liệu của mình, tải về được qua liên kết có thời hạn và chỉ bởi quản trị viên của chính tổ chức đó, kèm bản kê khai ghi khoảng thời gian mà bản xuất phản ánh. Một lượt dựng thất bại không bao giờ để lại kho lưu dở dang tải về được.

---

#### UC508 — Xoá sạch dữ liệu tổ chức

*Bảng C-50: Mô tả chức năng Xoá sạch dữ liệu tổ chức*

| **Tên use case** | Xoá sạch dữ liệu tổ chức | **ID** | UC508 |
|---|---|---|---|
| **Actor chính** | Quản trị nền tảng | **Mức độ cần thiết** | Tuỳ chọn |
| **Kích hoạt bởi** | Quản trị nền tảng | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 5 — Tổ chức và đăng ký dịch vụ |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị nền tảng** — xoá được dữ liệu của một tổ chức đã chấm dứt hợp tác.
- **Tổ chức bị xoá** — có cơ hội xuất dữ liệu trước khi mất hẳn.
- **Bộ phận kiểm toán** — mục kiểm toán về lần xoá **sống sót** sau khi dữ liệu biến mất.

**Mô tả tóm tắt:** *Quản trị nền tảng xoá vĩnh viễn dữ liệu của một tổ chức. Thao tác không hoàn tác được, nên nó đi kèm một bản xem trước nêu chính xác những gì sẽ bị phá huỷ và một lần xác thực lại.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị nền tảng – Xoá sạch dữ liệu tổ chức; Kho lưu trữ ngoài (S2)
- **Include (bao gồm):** UC601 Nâng quyền tạm thời
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở tổ chức và chọn "Xoá sạch dữ liệu".
2. Hệ thống hiển thị bản xem trước: số mẫu, số lớp, số tệp, tổng dung lượng, số thành viên và số lượt chạy sẽ bị phá huỷ, kèm thời điểm bản xuất dữ liệu gần nhất nếu có.
3. Quản trị viên đọc bản xem trước và gõ lại **mã định danh của tổ chức** để xác nhận.
4. Hệ thống yêu cầu xác thực lại danh tính của quản trị viên (UC601).
5. Hệ thống xoá các dòng dữ liệu của tổ chức và các tệp đã lưu, theo thứ tự bảo đảm không bao giờ để lại một dòng dữ liệu trỏ tới một tệp đã biến mất.
6. Hệ thống ghi một mục kiểm toán **sống sót sau lần xoá** — mục này nằm ngoài phạm vi dữ liệu bị xoá — lưu ai đã xoá cái gì, khi nào và với những con số nào.
7. Hệ thống báo cáo tổng kết lần xoá: đã xoá bao nhiêu dòng, bao nhiêu tệp, còn sót gì.

**Luồng luân phiên:**

1. **Xuất dữ liệu trước khi xoá:** ở bước 2, hệ thống đề nghị chạy một lượt xuất dữ liệu (UC507) và ghi nhận quản trị viên có thực hiện hay không. Ghi nhận này nằm trong mục kiểm toán ở bước 6, nên về sau trả lời được câu hỏi tổ chức có được trao lại dữ liệu trước khi mất hay không.
2. **Xoá theo cơ chế ân hạn:** với tổ chức ngừng dịch vụ theo quy trình bình thường, dữ liệu được giữ trong một khoảng ân hạn tính bằng ngày rồi mới dọn, thay vì xoá ngay. Thao tác trong use case này là đường xoá **có chủ đích và tức thời**, dùng khi có yêu cầu rõ ràng.

**Luồng ngoại lệ:**

1. **Số liệu đã thay đổi giữa lúc xem trước và lúc xác nhận.** Ở bước 5, nếu các con số không còn khớp với bản xem trước — chẳng hạn tổ chức vừa thu thêm mẫu — hệ thống **dừng lại** và yêu cầu quản trị viên xem một bản xem trước mới. Sự đồng ý được cho trên một tập số cụ thể; nếu tập số đó đã đổi thì sự đồng ý không còn áp cho việc sắp làm.

2. **Gõ sai chuỗi xác nhận.** Ở bước 3, hệ thống từ chối và không thực hiện gì. Việc phải gõ lại mã định danh — chứ không phải bấm một nút "Đồng ý" — chính là thứ phân biệt hành động này với một cú bấm nhầm ở màn hình danh sách. Không có phím tắt nào bỏ qua bước này.

3. **Xoá tệp thất bại giữa chừng.** Ở bước 5, hệ thống **dừng** và báo cáo danh sách những tệp còn lại. Một lần xoá dở dang được báo cáo đúng như vậy và không bao giờ được trình bày là đã hoàn tất — vì báo hoàn tất trong khi dữ liệu vẫn còn là loại sai sót có hậu quả pháp lý, không chỉ kỹ thuật. Quản trị viên chạy lại sau khi kỹ sư vận hành khôi phục kết nối tới kho lưu trữ; lần chạy lại xử lý phần còn lại.

4. **Xác thực lại thất bại.** Ở bước 4, nếu quản trị viên không hoàn tất được bước nâng quyền tạm thời, thao tác dừng và không dòng nào bị xoá. Yêu cầu xác thực lại tồn tại cho tình huống một phiên làm việc bị bỏ quên trên máy dùng chung: mật khẩu vừa nhập lại là bằng chứng người ngồi trước máy đúng là chủ tài khoản.

5. **Tổ chức vẫn còn thành viên đang hoạt động.** Ở bước 2, hệ thống nêu rõ số thành viên và cảnh báo rằng họ sẽ mất toàn bộ dữ liệu ngay lập tức, không có thông báo trước từ hệ thống. Việc báo cho họ là trách nhiệm quy trình của quản trị viên, không phải một bước tự động — và điều đó được nói thẳng trên màn hình thay vì để người dùng giả định hệ thống sẽ tự lo.

**Kết quả mong đợi:** Dữ liệu của tổ chức đã bị xoá vĩnh viễn theo thứ tự không để lại dòng trỏ tới tệp đã mất, và một mục kiểm toán **sống sót sau lần xoá** ghi ai đã xoá cái gì, khi nào, với những con số nào. Nếu một phần không xoá được, hệ thống báo cáo đúng phần còn lại thay vì trình bày lần xoá như đã hoàn tất.

---

### 5.6 Nghiệp vụ 6 — Quản trị người dùng và chính sách

#### UC601 — Nâng quyền tạm thời

*Bảng C-51: Mô tả chức năng Nâng quyền tạm thời*

| **Tên use case** | Nâng quyền tạm thời | **ID** | UC601 |
|---|---|---|---|
| **Actor chính** | Quản trị nền tảng | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Một thao tác nhạy cảm được yêu cầu | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 6 — Quản trị người dùng và chính sách |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị nền tảng** — chứng minh lại danh tính trước thao tác không hoàn tác được.
- **Nền tảng** — một phiên bị chiếm không đủ để thực hiện thao tác phá huỷ.

**Mô tả tóm tắt:** *Trước một thao tác quản trị mang tính phá huỷ hoặc không hoàn tác được, quản trị nền tảng chứng minh lại rằng đúng là mình đang ngồi tại máy. Trạng thái nâng quyền có thời hạn và chỉ áp cho phiên làm việc hiện tại.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị nền tảng – Nâng quyền tạm thời
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên kích hoạt một thao tác đòi nâng quyền — xoá sạch dữ liệu tổ chức, công bố văn bản pháp lý, sửa hạn mức gói dịch vụ.
2. Hệ thống chặn thao tác lại và yêu cầu nhập lại mật khẩu tài khoản. Mật khẩu là yếu tố **duy nhất** được hỏi ở bước này.
3. Quản trị viên nhập mật khẩu.
4. Hệ thống xác minh mật khẩu và cấp một khoảng thời gian nâng quyền, gắn với **đúng phiên làm việc hiện tại**.
5. Hệ thống ghi một mục kiểm toán lưu lần nâng quyền cùng thao tác đã yêu cầu nó, để về sau đọc được cặp "vì sao nâng quyền" và "đã làm gì sau đó".
6. Hệ thống thực hiện thao tác ban đầu và hiển thị thời gian nâng quyền còn lại trên thanh trạng thái.

**Luồng luân phiên:**

1. **Đã ở trạng thái nâng quyền:** nếu quản trị viên vừa nâng quyền cho một thao tác trước đó và khoảng thời gian còn hiệu lực, các bước 2–4 được bỏ qua và thao tác chạy ngay. Mỗi thao tác vẫn ghi mục kiểm toán riêng.
2. **Chủ động hạ quyền:** quản trị viên kết thúc trạng thái nâng quyền ngay từ thanh trạng thái; hệ thống thu hồi lập tức chứ không đợi hết hạn. Đây là thao tác nên làm trước khi rời máy.

**Luồng ngoại lệ:**

1. **Mật khẩu nhập sai.** Ở bước 4, hệ thống từ chối, giữ phiên ở trạng thái chưa nâng quyền, và **tính lần sai vào cùng ngân sách chống dò của tài khoản** như một lần đăng nhập thất bại. Nhờ vậy màn hình nâng quyền không trở thành một cửa dò mật khẩu không bị đếm. Thao tác ban đầu không được thực hiện. Quản trị viên nhập lại; sau nhiều lần sai liên tiếp, cơ chế chống dò áp thời gian chờ tăng dần và cuối cùng chặn tạm thời — kể cả với tài khoản quản trị.

2. **Khoảng thời gian nâng quyền hết hạn trước khi thao tác được xác nhận.** Ở bước 6, nếu quản trị viên đọc bản xem trước quá lâu rồi mới bấm xác nhận, hệ thống hỏi lại mật khẩu thay vì từ chối thẳng. Thời hạn ngắn là chủ ý: mục tiêu của cơ chế này là bảo đảm người đang ngồi trước máy tại **thời điểm thao tác** đúng là chủ tài khoản, nên một trạng thái nâng quyền sống lâu sẽ vô hiệu hoá chính nó.

3. **Trạng thái nâng quyền trên một thiết bị khác.** Ở bước 4, trạng thái nâng quyền **không** đi theo tài khoản sang trình duyệt hoặc thiết bị khác; nó thuộc về đúng phiên đã chứng minh. Quản trị viên mở cùng tài khoản ở máy thứ hai phải nhập lại mật khẩu ở máy đó. Nếu gắn trạng thái này vào tài khoản, một phiên bị bỏ quên ở máy khác sẽ thừa hưởng quyền vừa nâng.

4. **Tài khoản không có mật khẩu cục bộ.** Ở bước 2, nếu tài khoản được tạo qua một đường không đặt mật khẩu, cơ chế này không dùng được và thao tác nhạy cảm bị chặn hoàn toàn. Đây là trạng thái hiếm và cách xử lý là đặt mật khẩu cho tài khoản trước.

> **Ghi chú hiện trạng:** mô-đun mã dùng một lần đã sẵn sàng trong hệ thống nhưng đường nâng quyền **không** gọi tới nó, nên đặc tả không nêu một yếu tố thứ hai mà hiện thực chưa đòi hỏi. Nếu về sau bổ sung, điểm chèn là giữa bước 3 và bước 4.

**Kết quả mong đợi:** Phiên làm việc hiện tại — và chỉ phiên đó — mang trạng thái nâng quyền có thời hạn, thao tác nhạy cảm đã thực hiện, và nhật ký kiểm toán ghi cả lần nâng quyền lẫn thao tác đã yêu cầu nó. Một lần nhập mật khẩu sai để lại phiên ở trạng thái cũ và tiêu một lượt trong ngân sách chống dò của tài khoản.

---

#### UC602 — Quản lý tài khoản người dùng

*Bảng C-52: Mô tả chức năng Quản lý tài khoản người dùng*

| **Tên use case** | Quản lý tài khoản người dùng | **ID** | UC602 |
|---|---|---|---|
| **Actor chính** | Quản trị nền tảng | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Quản trị nền tảng | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 6 — Quản trị người dùng và chính sách |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị nền tảng** — xử lý được tài khoản vi phạm hoặc bị chiếm.
- **Chủ tài khoản** — được thông báo và biết lý do.
- **Bộ phận kiểm toán** — mọi thay đổi quyền và trạng thái đều có vết kèm giá trị cũ.

**Mô tả tóm tắt:** *Quản trị nền tảng xem xét các tài khoản trên nền tảng và tác động lên chúng: cấp hoặc thu quyền quản trị nền tảng, khoá và mở khoá, hoặc gửi một thông báo cảnh cáo.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị nền tảng – Quản lý tài khoản người dùng
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở trang Người dùng. Hệ thống liệt kê các tài khoản kèm tổ chức nhà, vai, trạng thái và lần hoạt động gần nhất.
2. Quản trị viên mở một tài khoản và xem chi tiết: các quan hệ thành viên, các phiên làm việc đang mở, phần đóng góp dữ liệu, và trạng thái đồng thuận.
3. Quản trị viên chọn một thao tác: đổi quyền quản trị nền tảng, khoá tài khoản, mở khoá, hoặc gửi cảnh cáo.
4. Hệ thống yêu cầu nhập lý do — bắt buộc với thao tác khoá và cảnh cáo, vì hai thao tác này ảnh hưởng trực tiếp tới người dùng và họ có quyền biết vì sao.
5. Hệ thống áp dụng thay đổi, ghi một mục kiểm toán kèm **trạng thái cũ và trạng thái mới**, rồi gửi thông báo cho chủ tài khoản.
6. Hệ thống hiển thị tài khoản đã cập nhật.

**Luồng luân phiên:**

1. **Khoá kèm thu hồi phiên:** khi nghi tài khoản bị chiếm, quản trị viên khoá tài khoản và đồng thời buộc đăng xuất mọi phiên của nó (UC603). Chỉ khoá mà không thu hồi phiên sẽ để kẻ đang giữ phiên tiếp tục hoạt động cho tới khi token hết hạn.
2. **Mở khoá sau khi xác minh:** quản trị viên mở khoá sau khi chủ tài khoản chứng minh danh tính qua kênh hỗ trợ; mục kiểm toán của lần mở khoá ghi lý do và phiếu hỗ trợ liên quan.

**Luồng ngoại lệ:**

1. **Quản trị viên tự khoá tài khoản của mình.** Ở bước 5, hệ thống từ chối. Nếu cho phép, một thao tác nhầm sẽ loại chính người đang xử lý sự cố ra khỏi hệ thống, và việc mở khoá lại cần một quản trị viên khác — người có thể không có mặt. Muốn dừng phiên của mình thì dùng đăng xuất (UC107).

2. **Thu quyền của quản trị viên nền tảng cuối cùng.** Ở bước 5, hệ thống từ chối. Một nền tảng không còn quản trị viên nào là trạng thái chỉ sửa được bằng can thiệp trực tiếp vào cơ sở dữ liệu trên máy chủ — tức là không còn nằm trong phạm vi vận hành bình thường. Quản trị viên cấp quyền cho người khác trước.

3. **Tài khoản bị khoá cố đăng nhập.** Sau bước 5, mọi lượt đăng nhập của tài khoản bị từ chối kèm lý do đã ghi ở bước 4 (UC105), thay vì một thông báo sai mật khẩu chung chung. Nói rõ lý do là chủ ý ở đây: người bị khoá cần biết để liên hệ đúng nơi, và việc giấu lý do không mang lại lợi ích an ninh nào vì họ đã vượt qua bước nhập mật khẩu.

4. **Tài khoản bị cảnh cáo.** Sau bước 5, người dùng thấy thông báo cảnh cáo ở lần đăng nhập kế tiếp và phải **xác nhận đã đọc** trước khi tiếp tục dùng hệ thống. Cơ chế này bảo đảm cảnh cáo không trôi qua như một thông báo thường; nó cũng để lại bằng chứng rằng người dùng đã được thông báo, phục vụ các bước xử lý tiếp theo nếu vi phạm lặp lại.

5. **Trường nhạy cảm trong dữ liệu trả về.** Ở bước 2, hệ thống **không bao giờ** trả về mã băm mật khẩu hay bí mật xác thực hai yếu tố. Việc chặn do một bộ lọc dữ liệu trả về đảm nhiệm, và điều đáng ghi lại trong tài liệu là: chính việc gỡ bộ lọc này khỏi một điểm cuối — một thay đổi trông như đơn giản hoá mã nguồn — đã từng làm lộ hai trường đó ra ngoài. Bộ lọc trả về ở đây là một biện pháp an ninh, không phải một chi tiết trình bày.

**Kết quả mong đợi:** Tài khoản mang trạng thái hoặc quyền mới, nhật ký kiểm toán lưu giá trị cũ và giá trị mới kèm lý do, và chủ tài khoản đã được thông báo. Nền tảng luôn còn ít nhất một quản trị viên, không ai tự khoá được chính mình, và dữ liệu trả về không bao giờ chứa mã băm mật khẩu hay bí mật xác thực hai yếu tố.

---

#### UC603 — Áp dụng biện pháp an ninh

*Bảng C-53: Mô tả chức năng Áp dụng biện pháp an ninh*

| **Tên use case** | Áp dụng biện pháp an ninh | **ID** | UC603 |
|---|---|---|---|
| **Actor chính** | Quản trị nền tảng | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Quản trị nền tảng | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 6 — Quản trị người dùng và chính sách |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị nền tảng** — phản ứng được với hành vi lạm dụng đang diễn ra.
- **Người dùng hợp lệ** — không bị chặn oan vì dùng chung một cổng ra mạng.
- **Bộ phận kiểm toán** — mỗi biện pháp đều có lý do và người thực hiện.

**Mô tả tóm tắt:** *Quản trị nền tảng phản ứng với hành vi lạm dụng: buộc một phiên làm việc kết thúc, hoặc chặn một dải địa chỉ không cho tới được nền tảng.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị nền tảng – Áp dụng biện pháp an ninh
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở nhật ký an ninh và xem lại hoạt động đáng ngờ: các lượt đăng nhập thất bại, các lượt chạm hạn mức, các yêu cầu bị chặn, số định danh khác nhau đã thử từ cùng một địa chỉ.
2. Quản trị viên chọn một phiên làm việc hoặc một địa chỉ vi phạm.
3. Quản trị viên chọn "Buộc đăng xuất" hoặc "Chặn địa chỉ", nhập lý do và thời hạn chặn nếu có.
4. Hệ thống áp dụng biện pháp: thu hồi phiên và đưa token của nó vào danh sách từ chối, hoặc thêm địa chỉ vào danh sách chặn ở tầng vào.
5. Hệ thống ghi một mục kiểm toán và hiển thị biện pháp trong nhật ký an ninh.
6. Về sau quản trị viên bỏ chặn địa chỉ khi thấy đủ căn cứ; việc bỏ chặn được ghi thành một mục kiểm toán **riêng**, không phải xoá mục cũ.

**Luồng luân phiên:**

1. **Chặn tự động theo hạn mức:** phần lớn hành vi dò mật khẩu bị chặn bởi cơ chế hạn mức tự động trước khi cần tới thao tác của con người — chặn dần theo cặp định danh và địa chỉ, rồi chặn cứng theo địa chỉ khi số lượt vượt trần. Use case này dành cho các trường hợp cơ chế tự động không bao phủ.

**Luồng ngoại lệ:**

1. **Địa chỉ thuộc dải dùng chung.** Ở bước 4, hệ thống cảnh báo khi địa chỉ nằm trong một dải được biết là dùng chung — mạng của một trường học, một nhà cung cấp di động — vì chặn nó là chặn tất cả những người sau cổng ra đó. Quản trị viên cân nhắc dùng biện pháp hẹp hơn: khoá tài khoản cụ thể (UC602) thay vì chặn địa chỉ. Đây chính là tình huống mà một biện pháp an ninh gây hại nhiều hơn mối đe doạ nó nhắm tới.

2. **Chặn chính địa chỉ mà quản trị viên đang dùng.** Ở bước 4, hệ thống từ chối. Nếu cho phép, quản trị viên sẽ tự đẩy mình ra khỏi hệ thống và việc gỡ chặn đòi can thiệp trực tiếp trên máy chủ. Hệ thống so địa chỉ của yêu cầu hiện tại với dải sắp chặn và cảnh báo cả khi địa chỉ nằm trong dải chứ không chỉ khi trùng khít.

3. **Phiên đã kết thúc trước khi lệnh thu hồi tới.** Ở bước 4, hệ thống báo trạng thái hiện tại và không thu hồi lần thứ hai, theo cùng nguyên tắc bất biến theo số lần gọi đã áp cho các thao tác xoá.

4. **Nguồn của địa chỉ bị làm giả.** Ở bước 4, địa chỉ dùng cho các biện pháp này được lấy theo chuỗi máy chủ trung gian **tin cậy** đã cấu hình, **không** lấy trực tiếp từ một trường tiêu đề do người gọi tự đặt. Nếu lấy từ tiêu đề tuỳ ý, chính kẻ tấn công sẽ chọn được địa chỉ nào bị đếm và bị chặn — nghĩa là họ vừa thoát khỏi hạn mức vừa khiến hệ thống chặn nhầm người khác. Cấu hình sai danh sách máy chủ trung gian tin cậy là một trong những lỗi làm vô hiệu toàn bộ nhóm biện pháp này, và nó không tự lộ ra: hệ thống vẫn chạy bình thường, chỉ là các con số đếm sai địa chỉ.

**Kết quả mong đợi:** Phiên vi phạm đã bị thu hồi hoặc địa chỉ vi phạm đã nằm trong danh sách chặn, kèm lý do và người thực hiện trong nhật ký kiểm toán; việc bỏ chặn về sau là một mục riêng chứ không xoá mục cũ. Quản trị viên không tự chặn được đường kết nối của chính mình, và mọi biện pháp đều tính trên địa chỉ lấy từ chuỗi máy chủ trung gian tin cậy.

---

#### UC604 — Tra cứu nhật ký kiểm toán

*Bảng C-54: Mô tả chức năng Tra cứu nhật ký kiểm toán*

| **Tên use case** | Tra cứu nhật ký kiểm toán | **ID** | UC604 |
|---|---|---|---|
| **Actor chính** | Quản trị nền tảng | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Quản trị nền tảng | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 6 — Quản trị người dùng và chính sách |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị nền tảng** — điều tra được một sự việc đã xảy ra.
- **Tổ chức** — dấu vết của mình không lộ sang tổ chức khác.
- **Bộ phận kiểm toán bên ngoài** — xuất được tập dấu vết để rà soát độc lập.

**Mô tả tóm tắt:** *Quản trị nền tảng đọc bản ghi bền vững về việc ai đã làm gì: tài khoản nào, hành động gì, trên đối tượng nào, từ địa chỉ nào và vào lúc nào.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị nền tảng – Tra cứu nhật ký kiểm toán
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở trang Kiểm toán.
2. Hệ thống xác định phạm vi tổ chức của người gọi, rồi hiển thị các mục mới nhất trước, mỗi mục gồm tác nhân, nhãn tác nhân tại thời điểm hành động, hành động, đối tượng, địa chỉ và thời điểm.
3. Quản trị viên lọc theo tác nhân, theo loại hành động, theo đối tượng hoặc theo khoảng thời gian.
4. Hệ thống trả về các mục khớp kèm phần chi tiết đã ghi, gồm cả **giá trị cũ** ở những hành động có thay đổi giá trị.
5. Quản trị viên xuất tập kết quả đã lọc để rà soát bên ngoài; lần xuất này cũng được ghi thành một mục kiểm toán.

**Luồng luân phiên:**

1. **Tra từ một đối tượng cụ thể:** quản trị viên mở lịch sử kiểm toán ngay từ trang của một tài khoản, một tổ chức hoặc một mẫu, thay vì lọc từ trang chung. Nguồn dữ liệu là một.

**Luồng ngoại lệ:**

1. **Không xác định được phạm vi tổ chức của người gọi.** Ở bước 2, hệ thống trả về **rỗng** chứ không trả về tất cả. Đây là một quyết định thiết kế đã phải trả giá để học: một truy vấn chạy **trước khi** biết phạm vi sẽ đọc xuyên qua ranh giới các tổ chức, và kết quả trông hoàn toàn bình thường nên không ai phát hiện. Vì vậy nhật ký kiểm toán hỏng theo hướng **đóng**. Hệ quả người dùng thấy được: một màn hình trống có thể nghĩa là "không có gì" mà cũng có thể nghĩa là "chưa xác định được phạm vi", nên hệ thống hiển thị rõ phạm vi đang áp ở đầu trang.

2. **Không tính được con số chính xác.** Ở bước 2, khi một số đếm không tính được — nguồn đếm không sẵn sàng, hoặc phạm vi quá lớn — hệ thống trả về giá trị `-1` với ý nghĩa quy ước là **"đừng suy luận"**, chứ không trả về 0. Trả 0 sẽ bị đọc thành "không có sự kiện nào", và một báo cáo an ninh dựa trên con số đó sẽ kết luận ngược hoàn toàn với sự thật.

3. **Yêu cầu sửa hoặc xoá một mục kiểm toán.** Ở bước 4, các mục **không** sửa và không xoá được từ giao diện này, và không có thao tác quản trị nào trong hệ thống làm được điều đó. Một nhật ký ghi đè được thì không còn là bằng chứng. Trường hợp một mục chứa dữ liệu nhập sai, cách xử lý là ghi thêm một mục đính chính, không phải sửa mục cũ.

4. **Sự kiện chỉ có ở một trong hai nơi ghi.** Hệ thống ghi sự kiện vào cả kho nhanh phục vụ hiển thị lẫn bảng bền vững trong cơ sở dữ liệu. Nếu một sự kiện chỉ có ở kho nhanh, nó sẽ biến mất khi kho đó bị dọn; nếu chỉ có ở bảng bền, nó không hiện trên các màn hình theo thời gian thực. Bảng bền là nguồn để đối chiếu khi hai bên lệch nhau, và các lệch loại này là dấu hiệu cần kiểm tra đường ghi chứ không phải dấu hiệu có người xoá dấu vết.

**Kết quả mong đợi:** Người điều tra có tập dấu vết đúng phạm vi được phép, kèm giá trị cũ ở những hành động có thay đổi, và xuất được ra ngoài để rà soát độc lập. Khi không xác định được phạm vi, kết quả là rỗng chứ không phải toàn bộ; các mục kiểm toán không sửa và không xoá được từ bất kỳ giao diện nào.

---

#### UC605 — Cấu hình tham số nền tảng

*Bảng C-55: Mô tả chức năng Cấu hình tham số nền tảng*

| **Tên use case** | Cấu hình tham số nền tảng | **ID** | UC605 |
|---|---|---|---|
| **Actor chính** | Quản trị nền tảng | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Quản trị nền tảng | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 6 — Quản trị người dùng và chính sách |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị nền tảng** — đổi được tham số vận hành mà không phải triển khai lại.
- **Kỹ sư vận hành** — biết tham số nào đổi được lúc chạy và tham số nào phải triển khai lại.
- **Bộ phận kiểm toán** — mỗi lần đổi đều lưu giá trị cũ.

**Mô tả tóm tắt:** *Quản trị nền tảng thay đổi các tham số vận hành của nền tảng — mở đăng ký tự phục vụ, hạn mức, thời hạn lưu giữ, ngưỡng cảnh báo — mà không cần triển khai lại hệ thống.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị nền tảng – Cấu hình tham số nền tảng
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở mục Cấu hình. Hệ thống hiển thị từng tham số kèm giá trị hiện tại, giá trị mặc định, mô tả tác dụng và dấu cho biết tham số đó đổi được lúc chạy hay phải triển khai lại.
2. Quản trị viên đổi một giá trị và lưu.
3. Hệ thống kiểm kiểu dữ liệu và khoảng giá trị cho phép của tham số đó.
4. Hệ thống lưu tham số, áp ngay cho các tiến trình đang chạy, và ghi một mục kiểm toán **kèm giá trị cũ**.
5. Hệ thống hiển thị giá trị mới và thời điểm có hiệu lực.

**Luồng luân phiên:**

1. **Đưa một tham số về mặc định:** quản trị viên bấm nút đặt lại; hệ thống ghi mục kiểm toán như một lần đổi giá trị bình thường, có giá trị cũ.

**Luồng ngoại lệ:**

1. **Giá trị không hợp lệ.** Ở bước 3, hệ thống từ chối và giữ nguyên giá trị cũ. Kiểm khoảng giá trị ở đây quan trọng hơn ở các màn hình khác vì nhiều tham số điều khiển cơ chế bảo vệ: một hạn mức đặt nhầm thành số rất lớn sẽ vô hiệu hoá chính hạn mức đó mà không có lỗi nào xuất hiện.

2. **Tham số thuộc mức triển khai.** Ở bước 2, các tham số được nướng vào ảnh chương trình lúc dựng — địa chỉ máy chủ, khoá bí mật, đường dẫn gốc — hiển thị ở trạng thái chỉ đọc kèm ghi chú rằng chúng đòi một lần **triển khai lại**, không phải một lần khởi động lại. Phân biệt này quan trọng vì khởi động lại dịch vụ trông giống như đã nạp cấu hình mới nhưng thực tế không: mã nguồn và một phần cấu hình nằm trong ảnh chương trình, nên chúng chỉ đổi khi ảnh được dựng lại. Kỹ sư vận hành thực hiện việc này qua quy trình triển khai (UC706).

3. **Bật đăng ký tự phục vụ.** Ở bước 4, thay đổi này được đánh dấu là một thay đổi **chính sách có hệ quả an toàn thông tin** và ghi nhận như vậy trong kiểm toán, vì nó mở cửa cho bất kỳ ai tạo tài khoản. Hệ thống hiển thị cảnh báo nêu các cơ chế phòng vệ đang phụ thuộc vào việc cửa này đóng — hạn mức tạo tài khoản theo địa chỉ, kiểm duyệt lời mời — để quyết định được đưa ra có hiểu biết.

4. **Tắt một cảnh báo phần cứng.** Quản trị viên tắt được một cảnh báo gây nhiễu, nhưng hệ thống ghi lại ai đã tắt và vào lúc nào, nên **một cảnh báo bị tắt không bao giờ là vô danh**. Kinh nghiệm vận hành cho thấy cảnh báo bị tắt tạm thời rồi quên bật lại là nguyên nhân phổ biến của các sự cố lẽ ra đã được phát hiện sớm, nên màn hình giám sát hiển thị danh sách cảnh báo đang tắt như một mục thường trực (UC704).

5. **Hai quản trị viên đổi cùng một tham số gần như đồng thời.** Ở bước 4, bản lưu sau ghi đè bản lưu trước và cả hai lần đổi đều có mục kiểm toán riêng kèm giá trị cũ tương ứng. Không có cơ chế khoá; lịch sử kiểm toán là thứ cho phép truy lại thứ tự thật sự đã xảy ra.

**Kết quả mong đợi:** Tham số vận hành mang giá trị mới, có hiệu lực ngay với các tiến trình đang chạy, và nhật ký kiểm toán lưu giá trị cũ. Các tham số thuộc mức triển khai vẫn ở trạng thái chỉ đọc kèm ghi chú rằng chúng đòi một lần triển khai lại; mọi cảnh báo bị tắt đều truy được về người đã tắt.

---

#### UC606 — Soạn và duyệt văn bản pháp lý

*Bảng C-56: Mô tả chức năng Soạn và duyệt văn bản pháp lý*

| **Tên use case** | Soạn và duyệt văn bản pháp lý | **ID** | UC606 |
|---|---|---|---|
| **Actor chính** | Quản trị nền tảng | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Quản trị nền tảng | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 6 — Quản trị người dùng và chính sách |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị nền tảng** — soạn và sửa tự do trước khi công bố.
- **Người duyệt** — đối chiếu được bản nháp với các phiên bản đã công bố.
- **Người dùng** — chỉ nhìn thấy bản đã công bố, không nhìn thấy bản nháp.

**Mô tả tóm tắt:** *Quản trị nền tảng soạn một văn bản pháp lý dưới dạng bản nháp, đưa nó qua vòng duyệt, rồi mới công bố. Mọi thứ trước lúc công bố đều sửa được tự do; công bố là cánh cửa một chiều (UC607).*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị nền tảng – Soạn và duyệt văn bản pháp lý
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở danh sách bản nháp. Hệ thống hiển thị từng bản kèm loại văn bản, trạng thái trong vòng duyệt, người sửa gần nhất và thời điểm sửa.
2. Quản trị viên tạo một bản nháp mới hoặc mở một bản đang có. Bản nháp mới thường được tạo bằng cách sao chép phiên bản đang hiệu lực, để phần thay đổi nhìn thấy được.
3. Quản trị viên sửa nội dung và siêu dữ liệu — loại văn bản, ngôn ngữ, ngày dự kiến hiệu lực — rồi lưu. Hệ thống ghi nhận người sửa và thời điểm.
4. Quản trị viên chuyển bản nháp sang trạng thái kế tiếp trong vòng duyệt, ví dụ từ đang soạn sang chờ duyệt.
5. Người duyệt đọc bản nháp và đối chiếu với các phiên bản đã công bố của cùng loại văn bản, kể cả phiên bản đã bị thay thế.
6. Khi bản nháp được chấp nhận, quản trị viên công bố từ chính bản nháp đó (UC607), tạo ra một phiên bản bất biến kèm mã băm nội dung.

**Luồng luân phiên:**

1. **Bỏ một bản nháp:** ở bước 3, bản nháp bị xoá bất cứ lúc nào và không để lại gì trong lịch sử công bố. Chỉ việc công bố mới là không hoàn tác được, nên giai đoạn nháp cố ý được để lỏng.
2. **Soạn bản dịch:** quản trị viên tạo bản nháp cho một ngôn ngữ khác của cùng loại văn bản. Mỗi bản ngôn ngữ là một văn bản riêng có mã băm riêng, nên đồng thuận của người dùng gắn với đúng bản ngôn ngữ họ đã đọc.

**Luồng ngoại lệ:**

1. **Công bố mà chưa qua vòng duyệt.** Ở bước 6, việc công bố yêu cầu nhập lại mật khẩu (UC601) trong khi việc soạn và duyệt thì không. Chênh lệch này phản ánh đúng mức độ hệ quả: sửa bản nháp không ảnh hưởng tới ai, còn công bố thì đặt ra một nghĩa vụ pháp lý cho toàn bộ người dùng và buộc mọi tài khoản phải chấp thuận lại (UC112).

2. **Đối chiếu với một phiên bản đã bị thay thế.** Ở bước 5, quản trị viên đọc được **mọi** phiên bản cũ, kể cả phiên bản không còn hiệu lực; công chúng thì chỉ đọc được bản đang hiệu lực (UC111). Sự bất đối xứng này là cần thiết: người duyệt phải biết điều khoản đã thay đổi thế nào qua các đời, còn người dùng cần một câu trả lời rõ ràng cho câu hỏi "hôm nay tôi đang chịu điều khoản nào".

3. **Hai người sửa cùng một bản nháp.** Ở bước 3, bản lưu sau ghi đè bản lưu trước và bản nháp ghi lại người thực hiện lần sửa cuối. Hệ thống không khoá bản nháp và không trộn thay đổi. Đây cũng chính là lý do vòng duyệt diễn ra **trên bản nháp** chứ không trên văn bản đã công bố: mất một đoạn sửa trên bản nháp là phiền toái, còn mất một đoạn trên văn bản đang có hiệu lực là sự cố pháp lý.

4. **Nội dung bản nháp rỗng hoặc thiếu siêu dữ liệu bắt buộc.** Ở bước 6, hệ thống từ chối công bố và liệt kê các trường còn thiếu. Việc kiểm ở thời điểm công bố chứ không ở thời điểm lưu nháp là chủ ý — bản nháp được phép dở dang, còn phiên bản công bố thì không.

**Kết quả mong đợi:** Bản nháp phản ánh nội dung mới nhất và đi đúng trạng thái trong vòng duyệt, trong khi công chúng vẫn chỉ nhìn thấy phiên bản đang hiệu lực. Không có nghĩa vụ pháp lý nào phát sinh cho tới bước công bố, và bước công bố đòi xác thực lại cùng đủ siêu dữ liệu bắt buộc.

---

#### UC608 — Tra cứu hồ sơ đồng thuận

*Bảng C-57: Mô tả chức năng Tra cứu hồ sơ đồng thuận*

| **Tên use case** | Tra cứu hồ sơ đồng thuận | **ID** | UC608 |
|---|---|---|---|
| **Actor chính** | Quản trị nền tảng | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Quản trị nền tảng | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 6 — Quản trị người dùng và chính sách |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị nền tảng** — giải thích được vì sao một mẫu được hoặc không được phát hành.
- **Người ký** — việc rút đồng thuận của mình được ghi nhận và tra ra được.
- **Bộ phận pháp chế** — có chứng cứ về phiên bản văn bản mà mỗi người đã chấp thuận.

**Mô tả tóm tắt:** *Quản trị nền tảng tra cứu ai đã chấp thuận phiên bản nào của văn bản nào, và một đồng thuận đã bị rút vào lúc nào — chính là bằng chứng đứng sau mọi quyết định phát hành dữ liệu.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị nền tảng – Tra cứu hồ sơ đồng thuận
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở mục quản trị văn bản pháp lý và đọc lịch sử công bố: phiên bản nào của loại văn bản nào có hiệu lực từ lúc nào, do ai công bố, kèm mã băm nội dung.
2. Quản trị viên tra một tài khoản cụ thể.
3. Hệ thống hiển thị các đồng thuận của tài khoản đó: loại văn bản, số phiên bản, mã băm nội dung tại thời điểm chấp thuận, mức phát hành đã chọn, thời điểm chấp thuận, và thời điểm rút nếu có.
4. Quản trị viên dùng hồ sơ này để giải thích vì sao một mẫu cụ thể có hoặc không có mặt trong một bản phát hành, bằng cách đối chiếu thời điểm dựng bản phát hành với trạng thái đồng thuận tại thời điểm đó.

**Luồng luân phiên:**

1. **Tra ngược từ một mẫu:** quản trị viên mở một mẫu và đi tới hồ sơ đồng thuận của người ký gắn với mẫu đó. Đây là chiều tra thường dùng khi trả lời một khiếu nại cụ thể về một đoạn dữ liệu.

**Luồng ngoại lệ:**

1. **Tài khoản chưa có đồng thuận nào.** Ở bước 3, hệ thống báo rõ rằng tài khoản chưa từng cho đồng thuận, và **không được để lẫn** trạng thái này với trạng thái đã rút. Hai trạng thái cùng dẫn tới việc mẫu không phát hành được, nhưng ý nghĩa và cách xử lý khác hẳn: chưa cho đồng thuận thường là do người dùng bỏ qua bước chọn mức phát hành và chỉ cần được nhắc, còn đã rút là một quyết định có chủ ý phải được tôn trọng. Giao diện hiển thị hai trạng thái bằng hai nhãn khác nhau chứ không gộp thành "không đủ điều kiện".

2. **Đồng thuận đã bị rút.** Ở bước 3, việc rút hiển thị **bên cạnh** lần chấp thuận gốc chứ không thay thế nó. Lần chấp thuận đã thực sự xảy ra và là một sự kiện lịch sử; xoá nó đi là huỷ chính bằng chứng cho phép giải thích các bản phát hành đã dựng trước thời điểm rút.

3. **Mã băm không khớp phiên bản được nêu tên.** Ở bước 3, nếu mã băm lưu trong bản ghi đồng thuận không khớp mã băm của phiên bản mà bản ghi nêu tên, hệ thống **đánh dấu** bản ghi đó là bất nhất thay vì hiển thị như một bản ghi bình thường. Trường hợp này chỉ xảy ra khi có sự cố dữ liệu, và nó phải nhìn thấy được vì một bản ghi đồng thuận không đối chiếu được với nội dung văn bản thì không dùng làm bằng chứng được. Bộ phận pháp chế xử lý bằng cách yêu cầu người dùng chấp thuận lại (UC112).

4. **Người ký không có tài khoản trên hệ thống.** Ở bước 2, với các mẫu thu hộ, người ký chỉ tồn tại dưới dạng một hồ sơ mô tả chứ không phải một tài khoản, nên không có bản ghi đồng thuận nào tra được theo tài khoản. Đồng thuận của họ, nếu có, được thu bằng văn bản giấy ngoài hệ thống. Đây là một khoảng trống thật và được nêu ở §6 của phụ lục này; hệ quả là các mẫu ấy phải được xử lý theo mức phát hành hẹp nhất.

**Kết quả mong đợi:** Người tra cứu trả lời được câu hỏi vì sao một mẫu có hoặc không có trong một bản phát hành, dựa trên phiên bản văn bản, mã băm nội dung và mốc thời gian chấp thuận hay rút. Trạng thái chưa từng cho đồng thuận hiển thị tách biệt với trạng thái đã rút, và bản ghi có mã băm không khớp được đánh dấu thay vì trình bày như hợp lệ.

---

#### UC609 — Quản lý gói dịch vụ

*Bảng C-58: Mô tả chức năng Quản lý gói dịch vụ*

| **Tên use case** | Quản lý gói dịch vụ | **ID** | UC609 |
|---|---|---|---|
| **Actor chính** | Quản trị nền tảng | **Mức độ cần thiết** | Tuỳ chọn |
| **Kích hoạt bởi** | Quản trị nền tảng | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 6 — Quản trị người dùng và chính sách |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị nền tảng** — đặt được chính sách hạn mức cho toàn nền tảng.
- **Tổ chức** — biết hạn mức của mình thay đổi và vì sao.
- **Bộ phận kiểm toán** — thay đổi thương mại có vết và đòi xác thực lại.

**Mô tả tóm tắt:** *Quản trị nền tảng sửa danh mục gói dịch vụ — các hạn mức mà mỗi gói cấp — và gán gói cho một tổ chức.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị nền tảng – Quản lý gói dịch vụ
- **Include (bao gồm):** UC601 Nâng quyền tạm thời
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở trang quản trị gói dịch vụ.
2. Hệ thống liệt kê các gói kèm hạn mức của từng gói — số thành viên, số lớp, số mẫu, số lượt huấn luyện, số lần dự đoán — và số tổ chức đang dùng mỗi gói.
3. Quản trị viên sửa hạn mức của một gói và lưu, sau khi xác thực lại (UC601).
4. Hệ thống kiểm tính hợp lệ và lưu. Các tổ chức đang dùng gói đó nhận hạn mức mới ở **lần kiểm hạn mức kế tiếp**, không phải sau khi đăng nhập lại.
5. Quản trị viên gán một gói cho một tổ chức và đặt kỳ hạn bắt đầu, kết thúc.
6. Hệ thống ghi một mục kiểm toán và hiển thị mức sử dụng toàn nền tảng theo từng gói.

**Luồng luân phiên:**

1. **Đình chỉ một tổ chức:** từ bước 5, quản trị viên đặt trạng thái thương mại của tổ chức thành đình chỉ. Trạng thái này chặn thao tác ghi nhưng **vẫn cho đọc và xuất dữ liệu**, và nó nằm trên **trục thương mại** — khác hẳn với việc khoá tài khoản mang tính hành chính ở UC602. Một tổ chức bị đình chỉ vì chưa thanh toán không phải là một tổ chức vi phạm, và hai loại trạng thái này không được trộn vào nhau vì chúng có đường gỡ khác nhau.
2. **Cho một gói nghỉ:** quản trị viên đánh dấu một gói không còn nhận tổ chức mới; các tổ chức đang dùng vẫn giữ nguyên hạn mức cho tới khi được chuyển sang gói khác.

**Luồng ngoại lệ:**

1. **Hạ hạn mức xuống dưới mức các tổ chức đang dùng.** Ở bước 4, hệ thống cảnh báo và liệt kê các tổ chức sẽ vượt hạn mức ngay sau khi lưu. Những tổ chức đó **giữ nguyên dữ liệu đã có** nhưng không thêm được nữa cho tới khi họ dọn bớt hoặc đổi gói. Hệ thống không xoá dữ liệu vượt mức và không được phép làm thế: hạn mức là ràng buộc lên hành động thêm mới, không phải một cái trần áp hồi tố lên dữ liệu đã tồn tại.

2. **Xoá một gói đang được tổ chức sử dụng.** Ở bước 3, hệ thống từ chối; gói chỉ sửa được hoặc cho nghỉ. Nếu xoá, các tổ chức đang tham chiếu tới nó sẽ mất định nghĩa hạn mức và hệ thống không còn cơ sở nào để quyết định cho phép hay từ chối một thao tác ghi.

3. **Xác thực lại thất bại.** Ở bước 3, nếu quản trị viên không hoàn tất bước nâng quyền, thay đổi không được lưu. Hạn mức gói là dữ liệu có hệ quả thương mại lên nhiều tổ chức cùng lúc, nên nó nằm trong nhóm thao tác đòi chứng minh lại danh tính.

4. **Chạm hạn mức tần suất ghi danh mục.** Ở bước 3, thao tác ghi vào danh mục gói chịu chung hạn mức tần suất với các thao tác danh mục khác, nên một đợt sửa nhiều gói liên tiếp có thể bị chặn tạm thời. Quản trị viên chờ hết cửa sổ rồi tiếp tục.

**Kết quả mong đợi:** Danh mục gói phản ánh đúng chính sách hạn mức hiện hành, các tổ chức nhận hạn mức mới ở lần kiểm kế tiếp, và mọi thay đổi đều đã qua xác thực lại cùng ghi kiểm toán. Việc hạ hạn mức không bao giờ xoá dữ liệu đã có; nó chỉ chặn việc thêm mới cho tới khi tổ chức dọn bớt hoặc đổi gói.

---

### 5.7 Nghiệp vụ 7 — Vận hành hệ thống và nguồn sự thật

#### UC701 — Quản lý máy ghi nguồn sự thật

*Bảng C-59: Mô tả chức năng Quản lý máy ghi nguồn sự thật*

| **Tên use case** | Quản lý máy ghi nguồn sự thật | **ID** | UC701 |
|---|---|---|---|
| **Actor chính** | Kỹ sư vận hành | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Kỹ sư vận hành | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 7 — Vận hành hệ thống và nguồn sự thật |

**Các thành phần tham gia và mối quan tâm:**

- **Kỹ sư vận hành** — kiểm soát được máy nào có quyền ghi vào nguồn sự thật.
- **Nền tảng** — một máy không đăng ký không ghi được, kể cả khi có quyền mạng.
- **Máy ghi nguồn sự thật (S5)** — được cấp và bị thu khoá ký.

**Mô tả tóm tắt:** *Kỹ sư vận hành quyết định máy nào được ghi vào nguồn sự thật. Một máy chỉ ghi được khi khoá ký của nó đã đăng ký; việc cấp và thu khoá thực hiện tại trang này.*

**Các mối quan hệ:**

- **Association (kết hợp):** Kỹ sư vận hành – Quản lý máy ghi nguồn sự thật; Máy ghi nguồn sự thật (S5)
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Kỹ sư vận hành mở trang quản trị nguồn sự thật.
2. Hệ thống hiển thị các máy đã đăng ký: vân tay khoá công khai, nhãn máy, người đăng ký, thời điểm đăng ký và lần ghi gần nhất.
3. Kỹ sư đăng ký một máy mới bằng nhãn và vân tay khoá công khai của máy đó. Quyền quản trị nền tảng là đủ ở đây; khác với xoá sạch dữ liệu hay công bố văn bản pháp lý, thao tác này **không** đòi xác thực lại.
4. Hệ thống lưu khoá vào bảng khoá được phép, hợp nhất tập này với các khoá nền đã cam kết sẵn trong mã nguồn, và ghi một mục vào nhật ký kiểm toán.
5. Kỹ sư thu hồi một máy khi máy đó ngừng sử dụng; hệ thống gỡ khoá khỏi bảng và ghi nhận việc thu hồi.
6. Hệ thống hiển thị lại danh sách máy được phép ghi sau thay đổi.

**Luồng luân phiên:**

1. **Đổi nhãn của một máy:** kỹ sư sửa nhãn mà không đụng tới vân tay khoá; danh tính máy nằm ở vân tay, nhãn chỉ để người đọc nhận ra.

**Luồng ngoại lệ:**

1. **Vân tay khoá đã tồn tại.** Ở bước 4, hệ thống từ chối. Một vân tay ứng với đúng một máy; cho phép hai bản ghi cùng vân tay sẽ khiến việc thu hồi một bản ghi không thật sự thu hồi được quyền ghi, vì bản ghi còn lại vẫn cho phép. Kỹ sư kiểm lại xem máy đã được đăng ký dưới nhãn khác chưa.

2. **Thu hồi máy công bố duy nhất.** Ở bước 5, hệ thống cảnh báo rằng sau thao tác này sẽ **không còn máy nào công bố được** vào nguồn sự thật, và hệ quả không dừng ở việc ngừng ghi: thành phần khởi tạo nguồn sự thật sẽ từ chối và **cả hệ thống không khởi động được**. Kỹ sư phải đăng ký máy thay thế trước khi thu hồi máy cũ. Đây là cảnh báo bắt buộc phải đọc chứ không phải một dòng ghi chú, vì hậu quả của nó chỉ lộ ra ở lần khởi động kế tiếp — có thể là nhiều ngày sau.

3. **Một máy có khoá chưa đăng ký cố ghi.** Máy đó bị từ chối ngay tại bước khởi động, bằng một mã thoát riêng **cố ý chặn toàn bộ hệ thống** thay vì chỉ ghi cảnh báo rồi chạy tiếp. Việc chặn là có chủ đích và **không được nới lỏng**: một máy ghi được vào nguồn sự thật mà không ai cấp phép chính là mất kiểm soát nguồn gốc dữ liệu, và chạy tiếp trong trạng thái đó nguy hiểm hơn nhiều so với việc dịch vụ không lên. Kỹ sư đăng ký khoá của máy rồi khởi động lại.

4. **Khoá nền đã cam kết trong mã nguồn.** Ở bước 5, các khoá này **không** thu hồi được từ trang quản trị; muốn đổi phải sửa mã nguồn và triển khai lại. Đây là một ràng buộc thật cần biết khi lập kế hoạch xử lý sự cố lộ khoá: đường xử lý nhanh chỉ có với khoá đăng ký qua cơ sở dữ liệu, còn khoá nền đòi một vòng triển khai.

**Kết quả mong đợi:** Tập khoá được phép ghi phản ánh đúng các máy đang thực sự vận hành: máy mới ghi được ngay sau khi đăng ký, máy đã thu hồi bị từ chối ở lần khởi động kế tiếp, và mọi lần cấp hoặc thu đều để lại một mục kiểm toán truy được về người thực hiện.

---

#### UC703 — Đồng bộ kho lưu trữ và cơ sở dữ liệu

*Bảng C-60: Mô tả chức năng Đồng bộ kho lưu trữ và cơ sở dữ liệu*

| **Tên use case** | Đồng bộ kho lưu trữ và cơ sở dữ liệu | **ID** | UC703 |
|---|---|---|---|
| **Actor chính** | Kỹ sư vận hành | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Kỹ sư vận hành | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 7 — Vận hành hệ thống và nguồn sự thật |

**Các thành phần tham gia và mối quan tâm:**

- **Kỹ sư vận hành** — đưa ba nơi lưu về trạng thái nhất quán sau sự cố.
- **Nghiên cứu sinh** — số liệu dùng để huấn luyện phản ánh đúng dữ liệu thật.
- **Kho lưu trữ ngoài (S2)** — được đối chiếu để tìm tệp mồ côi và tệp thiếu.

**Mô tả tóm tắt:** *Kỹ sư vận hành đối chiếu ba nơi ghi nhận một mẫu — tệp danh bạ, bản soi trong cơ sở dữ liệu và kho lưu trữ đối tượng — sau khi một sự cố làm chúng lệch nhau.*

**Các mối quan hệ:**

- **Association (kết hợp):** Kỹ sư vận hành – Đồng bộ kho lưu trữ và cơ sở dữ liệu; Kho lưu trữ ngoài (S2)
- **Include (bao gồm):** UC702 Xác minh toàn vẹn nguồn sự thật
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Kỹ sư mở trang Dữ liệu và đọc báo cáo hiện trạng: số dòng theo từng nguồn — danh bạ, cơ sở dữ liệu, kho lưu trữ — và chênh lệch giữa chúng.
2. Kỹ sư khởi động một lượt đồng bộ.
3. Hệ thống quét các tệp cục bộ, đọc danh bạ và đọc cơ sở dữ liệu, rồi tính ra tập các phép sửa cần thực hiện, phân loại theo từng kiểu lệch.
4. Hệ thống áp các phép sửa **theo chiều an toàn**: danh bạ là nguồn sự thật, bản soi trong cơ sở dữ liệu được dựng lại từ danh bạ, và không bao giờ theo chiều ngược lại.
5. Hệ thống trả về mã tác vụ để kỹ sư theo dõi lượt chạy.
6. Hệ thống báo cáo tổng kết: số dòng đã thêm vào bản soi, số khoá lưu trữ đã điền bù, số tệp mồ côi phát hiện được, và số dòng chưa xử lý được.

**Luồng luân phiên:**

1. **Chạy theo lịch:** một tác vụ theo lịch thực hiện chính phép đối soát này theo chu kỳ ngắn, nên phần lớn lệch nhỏ được sửa mà không cần ai bấm. Use case này là đường chạy thủ công, dùng sau một sự cố hoặc khi cần kết quả ngay.
2. **Chỉ báo cáo, không sửa:** kỹ sư chạy ở chế độ chỉ đọc để xem tập phép sửa trước khi cho phép áp. Đây là bước nên làm khi chênh lệch lớn bất thường.

**Luồng ngoại lệ:**

1. **Đã có một lượt đồng bộ đang chạy.** Ở bước 2, hệ thống từ chối lượt chạy song song thứ hai và chỉ tới lượt đang chạy. Hai lượt cùng sửa một tập dữ liệu sẽ giẫm lên nhau và cho ra kết quả phụ thuộc vào thứ tự chạy — đúng loại lỗi khó tái lập nhất.

2. **Một phép sửa bị bỏ qua trong im lặng.** Ở bước 4, hệ thống báo rõ từng phép sửa không thực hiện được cùng lý do. Đây là kiểu hỏng mà báo cáo này tồn tại để phơi ra: một lượt đồng bộ kết thúc với thông báo thành công trong khi thực tế không ghi được gì — vì thiếu quyền ghi, vì chính sách cách ly dữ liệu chặn câu lệnh cập nhật, hoặc vì ngữ cảnh tổ chức chưa được đặt — sẽ khiến người vận hành tin rằng dữ liệu đã nhất quán trong khi nó vẫn lệch. Kỹ sư đọc phần lý do và xử lý nguyên nhân gốc trước khi chạy lại.

3. **Dòng dữ liệu có tệp đã mất.** Ở bước 6, các dòng này được **liệt kê chứ không bị xoá**. Xoá dữ liệu thật không bao giờ là một bước sửa chữa tự động: một tệp không đọc được lúc này có thể chỉ vì kho lưu trữ đang không phản hồi, và một lượt đồng bộ đã xoá dòng thì không có đường quay lại. Kỹ sư điều tra từng dòng và quyết định thủ công.

4. **Bản phản chiếu ra bảng tính.** Ở bước 4, các dòng đã xoá mềm **giữ nguyên vị trí** của mình trong bản phản chiếu kèm dấu hiệu đã xoá, thay vì bị gỡ đi làm các dòng sau dồn lên. Nếu dồn chỗ, mọi tham chiếu theo số dòng từ các bảng tính bên ngoài sẽ trỏ sai — và sai theo cách không có thông báo lỗi nào.

**Kết quả mong đợi:** Sau lượt chạy, ba nơi lưu cùng mô tả một tập mẫu như nhau trong phạm vi các phép sửa an toàn: bản soi khớp danh bạ, các dòng thiếu khoá lưu trữ đã được điền bù, và những gì không tự sửa được — tệp mồ côi, dòng mất tệp — nằm trong một danh sách tường minh để xử lý bằng tay.

---

#### UC704 — Giám sát tình trạng hệ thống

*Bảng C-61: Mô tả chức năng Giám sát tình trạng hệ thống*

| **Tên use case** | Giám sát tình trạng hệ thống | **ID** | UC704 |
|---|---|---|---|
| **Actor chính** | Kỹ sư vận hành | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Kỹ sư vận hành | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 7 — Vận hành hệ thống và nguồn sự thật |

**Các thành phần tham gia và mối quan tâm:**

- **Kỹ sư vận hành** — phát hiện sự cố trước khi người dùng phát hiện.
- **Người dùng** — dịch vụ giữ được mức đáp ứng ổn định.
- **Dịch vụ gửi tin (S1)** — chuyển cảnh báo tới người trực.

**Mô tả tóm tắt:** *Kỹ sư vận hành theo dõi tình trạng của hệ thống đang chạy: mức sẵn sàng của từng dịch vụ, độ sâu hàng đợi, mức dùng tài nguyên và các cảnh báo đã kích hoạt.*

**Các mối quan hệ:**

- **Association (kết hợp):** Kỹ sư vận hành – Giám sát tình trạng hệ thống; Dịch vụ gửi tin (S1)
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Kỹ sư mở trang Tài nguyên.
2. Hệ thống hiển thị tình trạng từng dịch vụ trong bản triển khai, khả năng kết nối tới cơ sở dữ liệu và bộ đệm, cùng độ sâu của từng hàng đợi.
3. Hệ thống hiển thị tài nguyên máy chủ: mức dùng bộ xử lý, bộ nhớ, dung lượng đĩa còn trống, và bộ xử lý đồ hoạ nếu môi trường chạy nhìn thấy nó.
4. Hệ thống hiển thị các mục cần chú ý: tác vụ thất bại gần đây, tiến trình nghi treo, hạn mức sắp chạm trần, cảnh báo đang bị tắt.
5. Kỹ sư mở một mục và đi tiếp tới trang xử lý được mục đó.
6. Khi một ngưỡng cảnh báo bị vượt, hệ thống gửi cảnh báo qua thư điện tử tới người trực.

**Luồng luân phiên:**

1. **Nhận cảnh báo trước khi mở trang:** phần lớn sự cố tới với kỹ sư qua thư cảnh báo ở bước 6 chứ không qua việc chủ động mở trang; các bước 2–5 khi đó là quá trình chẩn đoán sau khi nhận cảnh báo.

**Luồng ngoại lệ:**

1. **Dịch vụ báo khoẻ nhưng đang chạy mã cũ.** Ở bước 2, trạng thái khoẻ **không** chứng minh dịch vụ đang chạy mã hiện tại — nó chỉ chứng minh tiến trình còn sống và trả lời được. Việc kiểm tra độ mới của bản triển khai là một use case riêng (UC706), và không có chỉ báo nào trên trang này thay thế được nó. Nhầm hai điều này là nguyên nhân của loại sự cố "đã sửa rồi mà lỗi vẫn còn".

2. **Số đo bộ xử lý bằng không.** Ở bước 3, nếu số đo được lấy trong một khoảng thời gian quá ngắn, kết quả luôn là không phần trăm — không phải vì máy rảnh mà vì phép đo cần một khoảng để so sánh. Hệ thống dùng khoảng đủ dài để con số có nghĩa. Người đọc thấy một dãy số không tuyệt đối nên nghi ngờ công cụ đo trước khi kết luận về máy chủ.

3. **Máy chủ có bộ xử lý đồ hoạ nhưng hệ thống báo không có.** Ở bước 3, đây thường **không** phải lỗi phần cứng mà là biểu hiện của một tệp cấu hình triển khai bị thiếu, khiến môi trường chạy không được cấp quyền nhìn thấy thiết bị. Hệ quả nghiêm trọng hơn một dòng hiển thị sai: các lượt huấn luyện sẽ chạy trên bộ xử lý thường và chậm hàng chục lần mà không báo lỗi. Kỹ sư kiểm lại tập tệp cấu hình đang được nạp (UC706).

4. **Cảnh báo gửi đi bị mất định dạng.** Ở bước 6, nội dung thư cảnh báo là **văn bản thuần**; mọi đánh dấu định dạng đặt trong đó sẽ hiển thị nguyên dạng cho người đọc thay vì được kết xuất. Đây là ràng buộc của kênh gửi cảnh báo và cần biết khi soạn mẫu thư, nếu không người trực sẽ nhận được một thư đầy ký hiệu đánh dấu giữa lúc đang xử lý sự cố.

5. **Nguồn số liệu giám sát không phản hồi.** Ở bước 2, nếu chính thành phần thu thập số liệu ngừng hoạt động, trang giám sát hiển thị trạng thái "không có số liệu" cho các mục liên quan thay vì hiển thị giá trị cũ như thể còn mới. Một bảng điều khiển hiển thị số liệu đã đóng băng là bảng điều khiển nói dối vào đúng lúc nguy hiểm nhất.

**Kết quả mong đợi:** Kỹ sư có một bức tranh hiện thời và trung thực về hệ thống: mỗi dịch vụ hiện đúng trạng thái của nó hoặc thừa nhận không có số liệu, các mục cần xử lý được liệt kê kèm đường đi tới nơi xử lý, và mọi ngưỡng bị vượt đều tới được người trực qua thư.

---

#### UC705 — Sao lưu và khôi phục dữ liệu

*Bảng C-62: Mô tả chức năng Sao lưu và khôi phục dữ liệu*

| **Tên use case** | Sao lưu và khôi phục dữ liệu | **ID** | UC705 |
|---|---|---|---|
| **Actor chính** | Kỹ sư vận hành | **Mức độ cần thiết** | Cốt lõi |
| **Kích hoạt bởi** | Kỹ sư vận hành, hoặc bộ lập lịch | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 7 — Vận hành hệ thống và nguồn sự thật |

**Các thành phần tham gia và mối quan tâm:**

- **Kỹ sư vận hành** — có bản sao lưu dùng được thật khi cần khôi phục.
- **Tổ chức** — dữ liệu của họ chịu được một sự cố mất dữ liệu.
- **Tiến trình nền (S4)** — chạy lượt sao lưu theo lịch mà không cần người bấm.

**Mô tả tóm tắt:** *Kỹ sư vận hành tạo bản sao lưu cơ sở dữ liệu và khi cần thì khôi phục từ một bản sao. Việc khôi phục vào môi trường thật cố ý khó hơn việc diễn tập khôi phục, vì hai việc này có hệ quả trái ngược nhau.*

**Các mối quan hệ:**

- **Association (kết hợp):** Kỹ sư vận hành – Sao lưu và khôi phục dữ liệu; Tiến trình nền (S4)
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Kỹ sư chạy công cụ sao lưu. Công cụ **kết xuất cơ sở dữ liệu xong rồi mới nén** kết quả — thứ tự này bảo đảm phần nén không bao giờ bắt đầu trên một tệp còn đang được ghi.
2. Hệ thống ghi tệp kho lưu vào nơi lưu bản sao và báo dung lượng cùng mã kiểm tổng của tệp.
3. Để kiểm chứng một bản sao, kỹ sư chạy lượt khôi phục ở **chế độ diễn tập**: bản sao được nạp vào một cơ sở dữ liệu tạm, không phải môi trường thật.
4. Hệ thống báo kết quả diễn tập: bản sao có nạp được không, và nó chứa những bảng nào với bao nhiêu dòng.
5. Để khôi phục thật, kỹ sư nêu **đích danh** đích đến và truyền một cờ bắt buộc dành riêng cho môi trường thật.
6. Hệ thống khôi phục bản sao vào đích đã nêu và báo cáo kết quả.

**Luồng luân phiên:**

1. **Sao lưu theo lịch:** bộ lập lịch chạy chính công cụ ở bước 1 theo chu kỳ, không cần người bấm. Kết quả nằm ở cùng nơi lưu và được kiểm chứng bằng cùng quy trình diễn tập.
2. **Sao lưu có mã hoá và nhân bản sang ổ khác:** cơ chế mã hoá tệp sao lưu và cơ chế đặt bản sao thứ hai ở ổ đĩa khác đều **có sẵn nhưng mặc định tắt**; kỹ sư bật chúng bằng cấu hình khi môi trường yêu cầu.

**Luồng ngoại lệ:**

1. **Đọc mục lục tệp kho lưu và nhầm đó là kiểm chứng.** Ở bước 3, việc liệt kê mục lục của một tệp kho lưu **không** phát hiện được tệp bị cắt cụt: mục lục nằm ở phần đầu tệp và vẫn đọc được ngay cả khi phần dữ liệu phía sau đã mất. Chỉ việc nạp thật mới phát hiện. Đó chính là lý do chế độ diễn tập tồn tại như một chế độ riêng thay vì dựa vào lệnh liệt kê. Một quy trình vận hành coi "liệt kê được mục lục" là bằng chứng bản sao lành sẽ phát hiện ra sự thật vào đúng lúc cần khôi phục.

2. **Vô tình khôi phục đè lên môi trường thật.** Ở bước 5, công cụ **từ chối** chạm vào cơ sở dữ liệu thật nếu không có cờ bắt buộc; mọi lệnh gọi thiếu cờ đều đi vào cơ sở dữ liệu tạm. Đây là hàng rào giữa một lượt diễn tập và một lượt phá huỷ dữ liệu, và nó cố ý bất tiện. Kỹ sư gõ nhầm đích sẽ nhận được một lượt diễn tập chứ không phải một sự cố.

3. **Bản sao đã mã hoá.** Ở bước 6, bản sao mã hoá phải được giải mã trước khi nạp; nếu thiếu khoá, lượt khôi phục dừng. Vì cơ chế mã hoá mặc định tắt, người vận hành **không được mặc định** rằng bản sao trong tay là bản đã mã hoá hay chưa — trạng thái này phải được đọc từ cấu hình chứ không suy đoán.

4. **Lịch sao lưu đã cấu hình nhưng chưa từng chạy.** Ở bước 1, một lịch tồn tại trong cấu hình **không** đồng nghĩa với việc có bản sao. Cách kiểm duy nhất đáng tin là mở nơi lưu bản sao và xem tệp mới nhất có ngày tháng nào. Đây là bài học đã trả giá: một cơ chế sao lưu tự động được cấu hình nhưng chưa từng chạy sẽ để lại đúng cảm giác an toàn mà không để lại bản sao nào.

**Kết quả mong đợi:** Tồn tại một bản sao lưu mới, có kiểm tổng, và đã được chứng minh là nạp được bằng một lượt diễn tập thật; khi cần khôi phục, đích đến luôn là thứ kỹ sư nêu tên tường minh chứ không bao giờ là môi trường thật do sơ suất.

---

#### UC706 — Kiểm tra độ mới của bản triển khai

*Bảng C-63: Mô tả chức năng Kiểm tra độ mới của bản triển khai*

| **Tên use case** | Kiểm tra độ mới của bản triển khai | **ID** | UC706 |
|---|---|---|---|
| **Actor chính** | Kỹ sư vận hành | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Kỹ sư vận hành | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 7 — Vận hành hệ thống và nguồn sự thật |

**Các thành phần tham gia và mối quan tâm:**

- **Kỹ sư vận hành** — biết chắc mã đang chạy là mã vừa triển khai.
- **Nghiên cứu sinh và người dùng** — thứ họ đang dùng đúng là phiên bản được mô tả.

**Mô tả tóm tắt:** *Sau một lần triển khai, kỹ sư vận hành kiểm tra rằng mã đang chạy đúng là mã trong cây mã nguồn. Một phép kiểm tra tình trạng chỉ trả lời "tiến trình còn sống", nó không bao giờ trả lời "đây có phải tiến trình anh vừa dựng".*

**Các mối quan hệ:**

- **Association (kết hợp):** Kỹ sư vận hành – Kiểm tra độ mới của bản triển khai
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Kỹ sư chạy công cụ kiểm tra độ mới trên máy triển khai. Công cụ chỉ đọc và không thay đổi gì, nên chạy được bất cứ lúc nào kể cả giữa giờ cao điểm.
2. Hệ thống đối chiếu thứ mà **mỗi thành phần đang chạy** thực sự phục vụ với thứ đang có trong cây mã nguồn, theo ba kiểu lệch: ảnh chương trình dựng trước lần sửa mã gần nhất, thành phần đang chạy một ảnh khác ảnh mới nhất, và tệp cấu hình môi trường đã đổi sau khi thành phần được tạo.
3. Hệ thống liệt kê mọi dịch vụ đang chạy mã cũ, kèm lý do cụ thể vì sao bị coi là cũ.
4. Hệ thống chỉ trả về mã thoát thành công khi **toàn bộ** những gì đang chạy đều là bản hiện tại.
5. Kỹ sư dựng lại và triển khai lại đúng những thành phần được nêu tên.

**Luồng luân phiên:**

1. **Chạy như một bước bắt buộc sau triển khai:** công cụ được gọi ở cuối quy trình triển khai; mã thoát khác không làm quy trình dừng lại và báo lỗi, thay vì để người vận hành tự nhớ kiểm tra.

**Luồng ngoại lệ:**

1. **Mọi dịch vụ đều báo khoẻ nhưng vẫn cũ.** Ở bước 2, các thành phần có thể trả lời bình thường trong khi phục vụ một ảnh chương trình dựng từ nhiều giờ trước. Đây chính là tình huống công cụ này tồn tại để bắt, và trạng thái khoẻ trên trang giám sát (UC704) không thay thế được nó. Biểu hiện điển hình: một lỗi vừa được sửa vẫn tái diễn trên môi trường thật.

2. **Một ảnh chương trình dùng chung cho nhiều dịch vụ.** Ở bước 3, nhiều dịch vụ của hệ thống dựng từ cùng một ảnh, nên một bản dựng cũ làm **tất cả** chúng cùng cũ. Báo cáo vì vậy nêu tên **từng dịch vụ** chứ không chỉ dịch vụ mà kỹ sư đang để ý. Bỏ sót một dịch vụ trong nhóm này — thường là dịch vụ chạy tác vụ theo lịch, vì nó không có giao diện nên ít ai nhớ — sẽ để lại một phần hệ thống chạy mã cũ mà không ai kiểm.

3. **Tệp cấu hình môi trường đã đổi.** Ở bước 5, một thay đổi trong tệp cấu hình môi trường **không** được nạp lại bằng lệnh khởi động lại thành phần; phải tạo lại thành phần đó. Báo cáo nêu rõ chênh lệch này thay vì che đi, vì lệnh khởi động lại tạo ra đúng cảm giác đã áp cấu hình mới trong khi thực tế thành phần vẫn giữ giá trị cũ từ lúc được tạo.

4. **Cây mã nguồn trên máy triển khai không khớp nhánh cần triển khai.** Ở bước 2, công cụ so với cây mã nguồn **đang có trên máy**, nên nếu cây đó chưa được cập nhật thì kết quả "mọi thứ đều mới" là đúng nhưng vô nghĩa. Kỹ sư kiểm nhánh và mã sửa đổi hiện tại trước khi tin vào kết quả.

**Kết quả mong đợi:** Sau khi công cụ trả về thành công, mọi thành phần đang phục vụ đều chạy đúng mã và đúng cấu hình hiện tại của cây mã nguồn trên máy triển khai; nếu không, kỹ sư có danh sách đích danh những thành phần phải dựng lại kèm lý do.

---

### 5.8 Nghiệp vụ 8 — Hỗ trợ và tích hợp

#### UC801 — Tạo phiếu hỗ trợ

*Bảng C-64: Mô tả chức năng Tạo phiếu hỗ trợ*

| **Tên use case** | Tạo phiếu hỗ trợ | **ID** | UC801 |
|---|---|---|---|
| **Actor chính** | Người dùng đã đăng nhập | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Người dùng đã đăng nhập | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 8 — Hỗ trợ và tích hợp |

**Các thành phần tham gia và mối quan tâm:**

- **Người dùng** — có một kênh chính thức để báo sự cố và được trả lời.
- **Nhân viên hỗ trợ** — nhận phiếu đúng phân loại để xử lý nhanh.
- **Dịch vụ gửi tin (S1)** — báo cho người trực khi có phiếu mới.

**Mô tả tóm tắt:** *Người dùng đã đăng nhập mở một phiếu hỗ trợ mô tả sự cố hoặc yêu cầu, chọn phân loại để phiếu tới đúng hàng đợi.*

**Các mối quan hệ:**

- **Association (kết hợp):** Người dùng đã đăng nhập – Tạo phiếu hỗ trợ; Dịch vụ gửi tin (S1)
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Người dùng mở trang Hỗ trợ. Hệ thống hiển thị các phân loại phiếu và một vài gợi ý tự trợ giúp dựa trên hoạt động gần đây của tài khoản — chẳng hạn một tác vụ vừa thất bại.
2. Người dùng chọn phân loại, nhập tiêu đề và mô tả, rồi gửi.
3. Hệ thống kiểm tính hợp lệ và tạo phiếu ở trạng thái mở, gắn với tài khoản người gửi và **trong phạm vi tổ chức** của họ.
4. Hệ thống gửi thư báo cho người trực rằng có phiếu mới.
5. Hệ thống hiển thị phiếu vừa tạo kèm mã phiếu và trạng thái, để người dùng theo dõi và trả lời tiếp (UC802).

**Luồng luân phiên:**

1. **Giải quyết bằng gợi ý tự trợ giúp:** ở bước 1, nếu gợi ý trả lời được vấn đề, người dùng đóng trang mà không tạo phiếu. Đây là kết quả mong muốn nhất và là lý do các gợi ý được đặt trước biểu mẫu chứ không sau.

**Luồng ngoại lệ:**

1. **Tiêu đề hoặc mô tả để trống.** Ở bước 3, hệ thống từ chối và **giữ nguyên** nội dung người dùng đã gõ ở các ô còn lại. Mất nội dung đã soạn khi gửi hụt là lỗi giao diện gây bực bội nhất trong toàn bộ luồng hỗ trợ, vì người dùng vốn đã đang gặp sự cố.

2. **Tài khoản đang có quá nhiều phiếu mở.** Ở bước 3, hệ thống đề nghị trả lời trên một phiếu đang có thay vì mở thêm phiếu mới, và liệt kê các phiếu đó. Nhiều phiếu cho cùng một vấn đề làm loãng hàng đợi và khiến người trực trả lời hai lần cho một việc.

3. **Thư báo cho người trực không gửi được.** Ở bước 4, phiếu **vẫn tồn tại** và vẫn xuất hiện trong hàng đợi (UC803). Thư chỉ là tiện lợi, không phải bản ghi chính thức, nên một sự cố của dịch vụ gửi tin làm chậm phản hồi chứ không làm mất phiếu. Cơ chế thông báo tồn đọng sẽ bắt được các phiếu bị bỏ quên.

4. **Truy vấn phục vụ thông báo nối lệch kiểu định danh.** Ở bước 4, phép nối giữa bảng phiếu và bảng tài khoản phải thực hiện trên các định danh **cùng kiểu dữ liệu**. Một phép so sánh lệch kiểu ở chỗ này từng khiến các thư báo **không bao giờ** được gửi, trong khi hệ thống không báo lỗi nào: truy vấn trả về tập rỗng và mã nguồn hiểu đó là "không có ai cần báo". Biểu hiện bên ngoài là người trực không nhận được thư nào và tưởng rằng không có phiếu mới.

**Kết quả mong đợi:** Một phiếu hỗ trợ tồn tại ở trạng thái mở, gắn đúng tài khoản và đúng tổ chức, hiện trong hàng đợi của người trực, và người dùng có mã phiếu để theo dõi — kể cả khi thư thông báo không gửi được.

---

#### UC802 — Trả lời phiếu hỗ trợ

*Bảng C-65: Mô tả chức năng Trả lời phiếu hỗ trợ*

| **Tên use case** | Trả lời phiếu hỗ trợ | **ID** | UC802 |
|---|---|---|---|
| **Actor chính** | Người dùng đã đăng nhập | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Người dùng hoặc nhân viên hỗ trợ | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 8 — Hỗ trợ và tích hợp |

**Các thành phần tham gia và mối quan tâm:**

- **Người dùng** — theo dõi được toàn bộ mạch trao đổi.
- **Nhân viên hỗ trợ** — trả lời trong đúng ngữ cảnh phiếu.
- **Tổ chức** — nội dung phiếu không rời khỏi ranh giới tổ chức.

**Mô tả tóm tắt:** *Người dùng và nhân viên hỗ trợ trao đổi trên một phiếu cho tới khi vấn đề được giải quyết, và trạng thái phiếu được cập nhật theo.*

**Các mối quan hệ:**

- **Association (kết hợp):** Người dùng đã đăng nhập – Trả lời phiếu hỗ trợ; Nhân viên hỗ trợ – Trả lời phiếu hỗ trợ
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Người dùng mở một phiếu. Hệ thống hiển thị mạch trao đổi theo thứ tự thời gian, mỗi tin kèm tác giả và thời điểm.
2. Người dùng viết nội dung trả lời và gửi.
3. Hệ thống kiểm người gọi là chủ phiếu hoặc là người trực có quyền trên phạm vi của phiếu.
4. Hệ thống ghi thêm tin nhắn vào mạch, cập nhật thời điểm hoạt động gần nhất của phiếu, và gửi thông báo cho phía còn lại.
5. Hệ thống hiển thị mạch trao đổi đã cập nhật.

**Luồng luân phiên:**

1. **Người trực trả lời:** khi tác giả là người trực, hệ thống đánh dấu tin nhắn đến từ bộ phận hỗ trợ, để mạch trao đổi vẫn đọc được ai nói gì khi phiếu kéo dài nhiều lượt.
2. **Trả lời kèm đổi trạng thái:** người trực vừa trả lời vừa đặt trạng thái phiếu trong cùng thao tác (UC803).

**Luồng ngoại lệ:**

1. **Phiếu đã đóng.** Ở bước 3, một tin nhắn mới trên phiếu đã đóng sẽ **mở lại** phiếu và hệ thống ghi nhận ai đã mở lại cùng thời điểm. Cách này đúng với thực tế vận hành: một vấn đề tưởng đã xong quay lại thường là cùng một vấn đề, và bắt người dùng mở phiếu mới sẽ làm mất mạch trao đổi trước đó.

2. **Người gọi không phải chủ phiếu và cũng không phải người trực.** Ở bước 3, hệ thống từ chối và không hiển thị nội dung phiếu. Phiếu hỗ trợ thường chứa mô tả chi tiết về dữ liệu và cấu hình của một tổ chức, nên nó nằm trong ranh giới tổ chức như mọi dữ liệu khác, không phải một khu vực chung.

3. **Tin nhắn rỗng hoặc quá dài.** Ở bước 3, hệ thống từ chối kèm giới hạn cụ thể và giữ nguyên nội dung đã soạn. Với nội dung dài, người dùng được đề nghị đính kèm tệp thay vì dán toàn bộ nhật ký vào thân tin nhắn.

4. **Hai bên cùng gửi tin trong cùng khoảnh khắc.** Ở bước 4, cả hai tin đều được ghi và hiển thị theo thời điểm; hệ thống không khoá mạch trao đổi. Hệ quả có thể thấy là hai tin trả lời chéo nhau, và người trực xử lý bằng cách đọc lại toàn mạch trước khi kết luận.

**Kết quả mong đợi:** Mạch trao đổi của phiếu chứa đủ các tin theo đúng thứ tự và đúng tác giả, thời điểm hoạt động gần nhất được cập nhật để phiếu không bị hàng đợi bỏ quên, và phía còn lại nhận được thông báo có tin mới.

---

#### UC803 — Trực hàng đợi hỗ trợ

*Bảng C-66: Mô tả chức năng Trực hàng đợi hỗ trợ*

| **Tên use case** | Trực hàng đợi hỗ trợ | **ID** | UC803 |
|---|---|---|---|
| **Actor chính** | Nhân viên hỗ trợ | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Nhân viên hỗ trợ | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 8 — Hỗ trợ và tích hợp |

**Các thành phần tham gia và mối quan tâm:**

- **Nhân viên hỗ trợ** — xử lý phiếu theo thứ tự và không bỏ sót.
- **Người dùng đang chờ** — được trả lời trong thời gian cam kết.
- **Dịch vụ gửi tin (S1)** — gửi thông báo khi hàng đợi tồn đọng.

**Mô tả tóm tắt:** *Nhân viên hỗ trợ xử lý hàng đợi phiếu đang mở: đọc theo thứ tự, trả lời và đặt trạng thái cho từng phiếu.*

**Các mối quan hệ:**

- **Association (kết hợp):** Nhân viên hỗ trợ – Trực hàng đợi hỗ trợ; Dịch vụ gửi tin (S1)
- **Include (bao gồm):** UC802 Trả lời phiếu hỗ trợ
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Nhân viên hỗ trợ mở hàng đợi. Hệ thống liệt kê phiếu trong phạm vi được phép, sắp theo trạng thái và theo thời gian chờ kể từ tin nhắn gần nhất của người dùng.
2. Nhân viên mở phiếu đang chờ lâu nhất và đọc toàn bộ mạch trao đổi.
3. Nhân viên trả lời (UC802).
4. Nhân viên đặt trạng thái phiếu: mở, đang chờ người dùng, hoặc đã giải quyết.
5. Hệ thống lưu trạng thái, gửi thông báo cho người yêu cầu và làm mới hàng đợi.
6. Khi hàng đợi vượt ngưỡng — thời gian chờ của phiếu cũ nhất, hoặc số phiếu chưa trả lời — hệ thống gửi thông báo tồn đọng cho người trực.

**Luồng luân phiên:**

1. **Chuyển phiếu cho người khác:** nhân viên chuyển một phiếu cần chuyên môn khác; phiếu giữ nguyên mạch trao đổi và chỉ đổi người phụ trách, để người dùng không phải kể lại từ đầu.

**Luồng ngoại lệ:**

1. **Hàng đợi rỗng.** Ở bước 1, hệ thống nói rõ rằng không còn phiếu nào chờ xử lý, thay vì hiển thị một bảng trống mà người trực phải tự diễn giải là "rỗng" hay "chưa tải được".

2. **Phiếu đã được người khác nhận và đặt trạng thái.** Ở bước 4, hệ thống báo trạng thái hiện tại và **không ghi đè âm thầm**. Hai người trực cùng xử lý một phiếu là chuyện thường xảy ra vào đầu ca; ghi đè im lặng sẽ khiến một phiếu đã được trả lời quay lại trạng thái mở, hoặc ngược lại, một phiếu chưa xong bị đánh dấu đã giải quyết.

3. **Thông báo tồn đọng bị nhầm với thông báo phiếu mới.** Ở bước 6, hai loại thông báo này phản ánh hai thứ khác nhau và **không được gộp làm một**: thông báo phiếu mới phản ánh một **sự kiện** — vừa có phiếu — còn thông báo tồn đọng phản ánh một **trạng thái** — hàng đợi đã chờ bao lâu và còn bao nhiêu phiếu. Chúng dùng ngưỡng khác nhau và tần suất khác nhau; gộp lại sẽ hoặc gây nhiễu, hoặc bỏ sót đúng thứ cần báo động.

4. **Ngưỡng tồn đọng đặt quá cao hoặc quá thấp.** Ở bước 6, ngưỡng quá thấp làm người trực quen với thông báo và bỏ qua chúng, còn ngưỡng quá cao khiến cảnh báo chỉ tới khi tình hình đã xấu. Ngưỡng là tham số cấu hình (UC605) và cần được đặt theo số liệu hàng đợi thật chứ không theo mặc định.

**Kết quả mong đợi:** Mọi phiếu trong hàng đợi đều có trạng thái phản ánh đúng việc đang chờ ai, phiếu chờ lâu nhất được xử lý trước, và tình trạng tồn đọng vượt ngưỡng luôn tới được người chịu trách nhiệm thay vì tích tụ im lặng.

---

#### UC804 — Xem thông báo

*Bảng C-67: Mô tả chức năng Xem thông báo*

| **Tên use case** | Xem thông báo | **ID** | UC804 |
|---|---|---|---|
| **Actor chính** | Người dùng đã đăng nhập | **Mức độ cần thiết** | Quan trọng |
| **Kích hoạt bởi** | Người dùng đã đăng nhập | **Phân loại** | Đơn giản |
| **Loại** | external | **Nghiệp vụ** | 8 — Hỗ trợ và tích hợp |

**Các thành phần tham gia và mối quan tâm:**

- **Người dùng** — không bỏ lỡ việc cần mình xử lý.
- **Quản trị nền tảng** — thông báo hành chính bắt buộc phải được xác nhận đã đọc.

**Mô tả tóm tắt:** *Người dùng đọc các thông báo hệ thống sinh ra cho mình — tác vụ đã xong, lời mời, cảnh báo hạn mức, thông báo hành chính — và đánh dấu đã đọc.*

**Các mối quan hệ:**

- **Association (kết hợp):** Người dùng đã đăng nhập – Xem thông báo
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Hệ thống hiển thị số thông báo chưa đọc trên thanh điều hướng của mọi trang.
2. Người dùng mở trang Thông báo. Hệ thống liệt kê thông báo mới nhất trước, mỗi mục kèm loại, nội dung tóm tắt và thời điểm.
3. Người dùng lọc theo loại để tìm nhanh nhóm mình quan tâm.
4. Người dùng mở một thông báo và đi tiếp tới trang mà nó nhắc tới — một tác vụ, một phiếu hỗ trợ, một lời mời.
5. Hệ thống đánh dấu thông báo đã đọc, hoặc người dùng đánh dấu tất cả đã đọc, và số chưa đọc ở bước 1 được cập nhật.

**Luồng luân phiên:**

1. **Đọc ngay từ thanh điều hướng:** người dùng mở danh sách rút gọn ngay trên thanh điều hướng và xử lý các mục gần nhất mà không mở trang đầy đủ.

**Luồng ngoại lệ:**

1. **Đối tượng được nhắc tới đã bị xoá.** Ở bước 4, nếu tác vụ, phiếu hoặc lời mời đã không còn, hệ thống nói rõ điều đó tại chỗ thay vì mở một trang hỏng hoặc một trang trống. Thông báo vẫn được đánh dấu đã đọc, vì nó đã hoàn thành vai trò của mình.

2. **Thông báo hành chính.** Ở bước 2, các thông báo hành chính — cảnh cáo tài khoản, thay đổi điều khoản — **phải được xác nhận đã đọc** trước khi người dùng tiếp tục dùng hệ thống, và không thể bỏ qua bằng cách đánh dấu tất cả đã đọc từ danh sách. Cơ chế này để lại bằng chứng rằng người dùng đã được thông báo, điều mà một thông báo đọc lướt không cung cấp được.

3. **Phạm vi hiển thị.** Ở bước 2, người dùng chỉ thấy thông báo của **chính tài khoản mình**; không có chế độ xem chéo tài khoản ở màn hình này, kể cả cho quản trị tổ chức. Muốn biết một thành viên đã được thông báo hay chưa thì tra nhật ký kiểm toán (UC604).

4. **Quá nhiều thông báo tích tụ.** Ở bước 2, khi số chưa đọc lớn, hệ thống vẫn hiển thị con số thật thay vì cắt ở một ngưỡng và ghi dấu cộng, để người dùng ước lượng đúng khối lượng cần xử lý. Các thông báo cũ được dọn theo thời hạn lưu giữ đã cấu hình.

**Kết quả mong đợi:** Người dùng nhìn thấy đúng số việc còn phải xử lý, mỗi thông báo dẫn tới đúng nơi hành động hoặc nói rõ vì sao không dẫn được, và các thông báo hành chính để lại dấu vết xác nhận đã đọc.

---

#### UC806 — Quản lý điểm nhận sự kiện

*Bảng C-68: Mô tả chức năng Quản lý điểm nhận sự kiện*

| **Tên use case** | Quản lý điểm nhận sự kiện | **ID** | UC806 |
|---|---|---|---|
| **Actor chính** | Quản trị tổ chức | **Mức độ cần thiết** | Tuỳ chọn |
| **Kích hoạt bởi** | Quản trị tổ chức | **Phân loại** | Trung bình |
| **Loại** | external | **Nghiệp vụ** | 8 — Hỗ trợ và tích hợp |

**Các thành phần tham gia và mối quan tâm:**

- **Quản trị tổ chức** — nối được hệ thống ngoài vào luồng sự kiện của tổ chức.
- **Ứng dụng bên thứ ba (S6)** — nhận sự kiện có chữ ký để kiểm chứng nguồn gốc.
- **Nền tảng** — điểm nhận sự kiện không trở thành đường tới các dịch vụ nội bộ.

**Mô tả tóm tắt:** *Quản trị tổ chức đăng ký các địa chỉ nhận sự kiện của nền tảng, thử chúng, và xem lại lịch sử giao nhận.*

**Các mối quan hệ:**

- **Association (kết hợp):** Quản trị tổ chức – Quản lý điểm nhận sự kiện; Ứng dụng bên thứ ba (S6)
- **Include (bao gồm):** không
- **Extend (mở rộng):** không
- **Generalization (tổng quát hoá):** không

**Xử lý sự kiện:**

1. Quản trị viên mở trang Tích hợp và đọc danh sách các loại sự kiện mà nền tảng phát ra, kèm cấu trúc dữ liệu của mỗi loại.
2. Quản trị viên thêm một điểm nhận: địa chỉ đích và các loại sự kiện muốn đăng ký.
3. Hệ thống kiểm địa chỉ — đúng dạng, dùng giao thức được phép, không trỏ vào vùng mạng nội bộ — rồi lưu điểm nhận kèm một bí mật dùng để ký các lần gửi.
4. Quản trị viên bấm "Thử". Hệ thống gửi một sự kiện thử tới địa chỉ đó và hiển thị mã trạng thái cùng nội dung phản hồi nhận được.
5. Khi một sự kiện đã đăng ký xảy ra, hệ thống gửi sự kiện kèm chữ ký tính từ bí mật, và ghi lại lần gửi cùng kết quả.
6. Quản trị viên mở lịch sử giao nhận để xem trạng thái từng lần gửi và nội dung đã gửi.

**Luồng luân phiên:**

1. **Xoay bí mật ký:** quản trị viên cấp lại bí mật khi nghi nó bị lộ; các lần gửi sau dùng bí mật mới, và hệ thống nhận bên ngoài phải cập nhật theo, nếu không chữ ký sẽ không kiểm chứng được.
2. **Tạm dừng một điểm nhận:** quản trị viên tắt điểm nhận trong lúc hệ thống bên ngoài đang bảo trì, thay vì để nó nhận hàng loạt lần gửi thất bại.

**Luồng ngoại lệ:**

1. **Địa chỉ không hợp lệ hoặc không tới được.** Ở bước 3, hệ thống từ chối lưu một địa chỉ sai dạng. Ở bước 4, một địa chỉ hợp lệ nhưng không phản hồi được báo lỗi kèm mã trạng thái nhận được, để quản trị viên phân biệt giữa "sai địa chỉ", "máy chủ từ chối" và "máy chủ không tồn tại" — ba nguyên nhân với ba cách sửa khác nhau.

2. **Giao nhận thất bại khi sự kiện thật xảy ra.** Ở bước 5, hệ thống thử lại với khoảng cách tăng dần và ghi lại từng lần thử. Số lần thử có trần; hết trần thì lần gửi đó được đánh dấu thất bại vĩnh viễn. Điểm nhận **không** bị gỡ tự động, vì một hệ thống bên ngoài ngừng vài giờ để bảo trì không phải lý do để xoá cấu hình tích hợp của khách hàng.

3. **Điểm nhận hỏng kéo dài.** Ở bước 6, khi **toàn bộ** các lần thử gần đây đều thất bại, hệ thống đánh dấu điểm nhận là đang hỏng và hiển thị nổi bật. Nếu không, một tích hợp chết sẽ im lặng trong nhiều tuần và chỉ lộ ra khi có người hỏi vì sao dữ liệu bên kia thiếu.

4. **Địa chỉ trỏ tới một dịch vụ nội bộ.** Ở bước 3, hệ thống từ chối các địa chỉ nhắm vào vùng mạng nội bộ của bản triển khai. Nếu cho phép, cơ chế gửi sự kiện trở thành một đường để người ngoài buộc máy chủ gọi tới chính các dịch vụ bên trong — cơ sở dữ liệu, bộ đệm, dịch vụ siêu dữ liệu của môi trường chạy — và trả kết quả ra ngoài. Đây là một lỗ hổng nghiêm trọng và phép kiểm ở bước 3 là biện pháp chặn nó.

**Kết quả mong đợi:** Các điểm nhận đã đăng ký nhận được đúng những loại sự kiện đã chọn, kèm chữ ký để bên ngoài kiểm chứng được nguồn gốc; mọi lần gửi đều để lại vết trong lịch sử giao nhận, và một tích hợp hỏng kéo dài luôn nhìn thấy được thay vì âm thầm mất dữ liệu.

---

## 6. Bốn tác nhân mà mã nguồn chưa phân biệt được

Ghi rõ ở đây để người đọc không tưởng nhầm rằng phần mềm đang bảo đảm những phân
biệt này. Bảng này bổ sung cho Bảng 1-2 ở Chương 1.

| Tác nhân | Hiện trạng trong mã | Vì sao vẫn giữ trong mô hình |
|---|---|---|
| **A3** Người khiếm thính – khiếm ngôn | Không có cột nào phân loại người ký | Đây là **chủ thể dữ liệu** của cả đề tài. Mức đồng thuận gắn với người ký, và chính người ký quyết định mẫu của mình được phát hành tới đâu. Bỏ A3 thì không còn ai để giải thích vì sao đồng thuận chi phối việc phát hành |
| **A4** Người dùng bình thường | Như trên | Là **phía bên kia** của cuộc giao tiếp. Đầu ra giọng nói (UC408) tồn tại **chỉ vì** có người nghe ở đầu bên kia |
| **A9** Nhân viên hỗ trợ | Hàng đợi kiểm bằng quyền quản trị nền tảng | Trực phiếu khác hẳn đặt chính sách. Tách sẵn ở tầng mô hình để khi thêm vai riêng thì đặc tả không phải viết lại |
| **A10** Kỹ sư vận hành | Quyền quản trị + quyền trên máy chủ | Sáu use case của A10 **chạy ngoài ứng dụng**, nên ranh giới thật của họ là quyền hệ điều hành chứ không phải một cột trong cơ sở dữ liệu |

---

## 7. Ba use case nói thẳng là chưa làm được

Đặc tả này bóc từ mã nguồn đang chạy, nên chỗ nào hệ thống **chưa** làm được thì
nói thẳng thay vì mô tả thứ chỉ tồn tại trong mong muốn:

| Mã | Use case | Trạng thái thật |
|---|---|---|
| UC213 | Xuất ảnh chụp bộ dữ liệu | Có đường xuất, nhưng **ảnh chụp bất biến có ghim phiên bản** mới hoàn thiện một phần |
| UC503 | Chấp nhận lời mời | Đường hoạt động; giao diện của luồng này mới được bổ sung muộn |
| UC508 | Dọn sạch dữ liệu tổ chức | Hoạt động, nhưng **bảng ghi nhận yêu cầu dọn chưa được bảo vệ theo hàng** — đây là một trong hai bảng nằm ngoài độ phủ nêu ở Phụ lục A §5 |
