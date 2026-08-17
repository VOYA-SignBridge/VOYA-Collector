# PHỤ LỤC C: ĐẶC TẢ USE CASE CHI TIẾT

*Chương 1 §2 trình bày danh sách đủ 79 use case và đặc tả chi tiết tám use case
trục chính. Phụ lục này chứa phần còn lại: khuôn đặc tả, toàn bộ quan hệ giữa các
use case, và đặc tả chi tiết các use case mà thân bài chỉ nhắc tên.*

**Nguồn đặc tả:** `docs/09-specs/USE_CASE_SPECIFICATION.md` — bản dựng lại từ mã
nguồn đang chạy: 26 bộ định tuyến, hơn 30 màn hình và bộ công cụ vận hành. Mỗi
use case có ít nhất một điểm cuối, một màn hình hoặc một kịch bản thật đứng sau.

---

## 1. Khuôn đặc tả

Mỗi use case gồm đúng các mục sau, theo thứ tự:

| Ô | Nội dung |
|---|---|
| Use Case / ID | Tên và mã |
| Main actor / Priority | Tác nhân chính và mức ưu tiên |
| Trigger / Type | Nguồn kích hoạt và loại |
| Brief description | Một đoạn mô tả |
| Relationship | Association / Include / Extend / Generalization |
| Normal flow | Luồng chính, đánh số |
| Exceptional flow | Luồng ngoại lệ, mỗi nhánh có tên |

**Mức ưu tiên** nhận ba giá trị: `Essential` — không có thì hệ thống không dùng
được; `Important` — thiếu thì nghiệp vụ khập khiễng nhưng vẫn chạy; `Optional`.

**Loại** nhận `external` (một tác nhân ngoài khởi phát) hoặc `internal` (hệ thống
tự khởi phát, theo hàng đợi hoặc theo lịch).

**Quy ước chiều của quan hệ — chỗ này hay bị vẽ ngược:**

* `Include: X` nghĩa là **use case này gọi X**, và X **luôn luôn** chạy.
* `Extend: X` nghĩa là **use case này mở rộng X** — bản thân nó là phần thêm vào
  X trong một điều kiện nào đó. Use case **cơ sở không** liệt kê phần mở rộng của
  mình.

---

## 2. Toàn bộ quan hệ «include» — 13 quan hệ

Đọc là: **use case cột trái luôn gọi use case cột giữa**.

| Use case cơ sở | «include» | Vì sao luôn xảy ra |
|---|---|---|
| UC101 Đăng ký tài khoản | UC112 Chấp thuận văn bản pháp lý | Cưỡng chế đồng thuận đang bật: không chấp thuận thì tài khoản không tồn tại |
| UC102 Đăng ký theo lời mời | UC103 Gửi mã xác thực | Địa chỉ được mời vẫn phải được chứng minh là có thật |
| UC104 Xác thực địa chỉ liên hệ | UC103 Gửi mã xác thực | Không có mã thì không có gì để xác thực |
| UC108 Khôi phục tài khoản | UC103 Gửi mã xác thực | Bước một của khôi phục chính là gửi mã |
| UC112 Chấp thuận văn bản pháp lý | UC111 Xem văn bản pháp lý | Phải đọc được văn bản thì mới ký được nó |
| UC201 Thu mẫu từ camera | UC203 Xử lý bản ghi | Mẫu chỉ tồn tại sau khi trích đặc trưng |
| UC202 Tải lên tệp video | UC203 Xử lý bản ghi | Cùng lý do, khác nguồn đầu vào |
| UC503 Chấp nhận lời mời | UC102 Đăng ký theo lời mời | Lời mời **chỉ** được tiêu thụ ở đường tạo tài khoản |
| UC508 Dọn sạch dữ liệu tổ chức | UC601 Nâng quyền tạm thời | Thao tác không hoàn tác được, đòi xác thực lại |
| UC607 Công bố văn bản pháp lý | UC601 Nâng quyền tạm thời | Bản đã công bố là bất biến, không sửa lại được |
| UC609 Quản lý gói cước | UC601 Nâng quyền tạm thời | Hạ gói hay treo một tổ chức gây hậu quả thương mại thật |
| UC703 Đồng bộ kho lưu trữ và CSDL | UC702 Xác minh toàn vẹn nguồn sự thật | Muốn sửa lệch thì phải biết lệch ở đâu trước |
| UC803 Trực hàng đợi hỗ trợ | UC802 Trả lời phiếu hỗ trợ | Trực hàng đợi luôn kết thúc bằng một lượt trả lời |

## 3. Toàn bộ quan hệ «extend» — 13 quan hệ

Đọc là: **use case cột trái là phần thêm vào use case cột giữa**, chỉ chạy khi
điều kiện ở cột phải đúng.

| Use case mở rộng | «extend» | Điều kiện |
|---|---|---|
| UC102 Đăng ký theo lời mời | UC101 Đăng ký tài khoản | Khi khách tới bằng liên kết lời mời có mã |
| UC106 Xác thực yếu tố thứ hai | UC105 Đăng nhập | Khi tài khoản đã bật xác thực hai yếu tố |
| UC109 Quản lý xác thực hai yếu tố | UC110 Quản lý hồ sơ | Khi người dùng vào phần Bảo mật |
| UC113 Rút đồng thuận | UC112 Chấp thuận văn bản pháp lý | Khi người ký rút lại đồng thuận đã cho |
| UC114 Dùng thử nhận dạng | UC407 Nhận dạng thời gian thực | Khi người dùng chưa đăng nhập; giới hạn số phút mỗi ngày |
| UC208 Xem lại video phiên thu | UC207 Xem chi tiết lớp | Khi muốn xem lại bản dựng của phiên thu |
| UC210 Gán lại người ký | UC207 Xem chi tiết lớp | Khi phát hiện phiên thu gán sai người ký |
| UC212 Quản lý thùng rác | UC211 Xoá mẫu | Khi cần hoàn tác hoặc xoá vĩnh viễn một mẫu |
| UC212 Quản lý thùng rác | UC304 Gỡ lớp | Khi cần hoàn tác hoặc xoá vĩnh viễn một lớp |
| UC303 Gộp hai lớp trùng | UC302 Cập nhật lớp | Khi việc cần làm là gộp hai lớp trùng, không phải đổi tên một lớp |
| UC310 Sao chép danh mục vào tổ chức | UC501 Quản lý tổ chức | Khi tổ chức vừa tạo cần danh mục mồi để bắt đầu thu |
| UC405 Thử mô hình đã huấn luyện | UC404 Xem kết quả đánh giá | Khi muốn thử một mẫu thật trước khi quyết định thăng hạng |
| UC408 Đọc thành tiếng | UC407 Nhận dạng thời gian thực | Khi người dùng bật đầu ra giọng nói |

## 4. Quan hệ «generalization»

**Giữa các use case:**

| Use case cha | Use case con | Ghi chú |
|---|---|---|
| **Thu nhận mẫu** «abstract» | UC201 Thu mẫu từ camera, UC202 Tải lên tệp video | Hai nguồn đầu vào, cùng một kết quả: một mẫu đã trích đặc trưng |
| **Xoá dữ liệu** «abstract» | UC209 Xoá phiên thu, UC211 Xoá mẫu, UC304 Gỡ lớp | Cùng ngữ nghĩa xoá mềm, ba mức khác nhau |
| UC103 Gửi mã xác thực | Gửi qua thư, gửi qua SMS | Hai kênh, cùng hợp đồng mã một lần |

**Giữa các tác nhân:** ba chuỗi kế thừa, xem Chương 1 §2.0 và Hình 1-2.

| Chuỗi | Nội dung | Hệ thống kiểm được? |
|---|---|---|
| `A2 → A5 → A6 → A7` | Thành viên → biên tập viên → quản trị tổ chức | ✅ Có |
| `A2 → {A3, A4}` | Người khiếm thính – khiếm ngôn và người dùng bình thường | ⚠️ Không — khác **mục tiêu**, không khác quyền |
| `A8 → {A9, A10}` | Nhân viên hỗ trợ và kỹ sư vận hành | 🟡 Một phần |

---

## 5. Đặc tả chi tiết bổ sung

Bốn use case dưới đây được đặc tả đầy đủ ở đây vì chúng hay bị hỏi khi bảo vệ và
thân bài chỉ nhắc tên. Đặc tả đủ 79 use case nằm ở tài liệu nguồn nêu ở đầu phụ
lục.

### UC203 — Xử lý bản ghi

| **Use Case** | Xử lý bản ghi | **ID** | UC203 |
|---|---|---|---|
| **Tác nhân chính** | Tiến trình nền (S4) | **Mức ưu tiên** | Essential |
| **Kích hoạt bởi** | Một lượt thu hoặc một lượt tải lên được xếp hàng | **Loại** | **internal** |

**Mô tả ngắn:** *Tiến trình nền biến một bản ghi thô thành một mẫu dùng được cho
huấn luyện: trích điểm mốc bàn tay, cắt cửa sổ độ dài cố định, tăng cường, ghi
tệp đặc trưng và đăng ký mẫu vào nguồn sự thật.*

**Quan hệ:**
- **Association:** Tiến trình nền (S4) – Xử lý bản ghi; Kho lưu trữ ngoài (S2)
- **Include / Extend / Generalization:** không

**Luồng chính:**
1. Tiến trình lấy tác vụ khỏi hàng đợi và đánh dấu đang chạy.
2. Trích điểm mốc bàn tay theo từng khung — 21 điểm mốc × 3 toạ độ × 2 bàn tay =
   126 đặc trưng mỗi khung.
3. Áp cửa sổ trượt độ dài cố định và chuẩn hoá không gian toạ độ.
4. Tính các chỉ số chất lượng của cửa sổ, gồm độ đầy đủ và độ rung.
5. Sinh các biến thể tăng cường của cửa sổ.
6. Ghi tệp đặc trưng **kèm một tệp mô tả đi cạnh**, để dòng đăng ký dựng lại được
   từ chính tệp đó.
7. Thêm dòng mẫu vào nguồn sự thật và phản chiếu sang cơ sở dữ liệu. **Bản phản
   chiếu sang bảng tính không được ghi ở đây** — nó do một tác vụ theo lịch riêng
   làm mới, nên một mẫu được đăng ký từ rất lâu trước khi xuất hiện trên bảng tính.
8. Chuyển việc tải lên kho ngoài sang một tác vụ có thử lại riêng, và ghi khoá
   lưu trữ trả về lên dòng mẫu khi hoàn tất.
9. Đánh dấu tác vụ hoàn thành và thông báo cho chủ sở hữu.

**Luồng ngoại lệ:**
1. **Không phát hiện được bàn tay:** ở bước 2, tác vụ kết thúc ở trạng thái thất
   bại kèm lý do; **không** tạo dòng mẫu nào.
2. **Cửa sổ quá ngắn:** ở bước 3, nếu bản ghi ngắn hơn cửa sổ, tiến trình **đệm
   thêm và ghi nhận việc đó vào chỉ số chất lượng**, thay vì âm thầm bỏ mẫu.
3. **Gửi lên kho ngoài thất bại:** ở bước 8, thử lại; nếu mọi lần thử đều hỏng,
   dòng mẫu giữ đường dẫn cục bộ và một tác vụ đối soát điền khoá lưu trữ về sau.
4. **Ghi nguồn sự thật thất bại:** ở bước 7, tác vụ huỷ bỏ và xếp lại hàng; một
   mẫu có trong cơ sở dữ liệu nhưng thiếu ở nguồn sự thật được coi là **không
   nhất quán** và do tác vụ đối soát sửa.
5. **Tiến trình chết giữa chừng:** tác vụ trở lại hàng đợi; định danh mẫu ổn định
   nên lượt chạy lại **ghi đè** chứ không nhân bản.

### UC407 — Nhận dạng ký hiệu thời gian thực

| **Use Case** | Nhận dạng ký hiệu thời gian thực | **ID** | UC407 |
|---|---|---|---|
| **Tác nhân chính** | Người khiếm thính – khiếm ngôn | **Mức ưu tiên** | Essential |
| **Kích hoạt bởi** | Người ký | **Loại** | external |

**Mô tả ngắn:** *Người dùng ký trước camera và nền tảng hiển thị liên tục nhãn
nhận dạng được, dùng mô hình đang phục vụ cho phương ngữ đã chọn.*

**Quan hệ:**
- **Association:** Người ký – Nhận dạng thời gian thực; Người dùng bình thường
  (người nhận kết quả); Dịch vụ suy luận (S3)
- **Include / Extend / Generalization:** không *(UC114 và UC408 mở rộng use case này)*

**Luồng chính:**
1. Người dùng mở trang nhận dạng.
2. Hệ thống liệt kê các mô hình khả dụng kèm phương ngữ; người dùng chọn một.
3. Hệ thống xin quyền camera và khởi động theo dõi bàn tay tại máy khách.
4. Hệ thống gom khung điểm mốc vào một cửa sổ trượt và gửi mỗi cửa sổ hoàn chỉnh
   tới dịch vụ suy luận.
5. Hệ thống hiển thị nhãn dự đoán kèm độ tin cậy, và giữ các dự đoán gần nhất
   thành một bản ghi chạy.
6. Người dùng dừng phiên; hệ thống giải phóng camera.

**Luồng ngoại lệ:**
1. **Không có mô hình cho phương ngữ:** ở bước 2, hệ thống nói rõ phương ngữ đó
   chưa có mô hình đang phục vụ và đề xuất các phương ngữ có.
2. **Độ tin cậy thấp:** ở bước 5, nếu độ tin cậy dưới ngưỡng hiển thị, hệ thống
   **không hiển thị gì** thay vì hiển thị một phỏng đoán sai.
3. **Dịch vụ suy luận không sẵn sàng:** ở bước 4, hệ thống ngừng gửi, hiển thị
   thông báo dịch vụ và **giữ nguyên khung xem camera**.
4. **Hết hạn mức dự đoán:** ở bước 4, hệ thống dừng luồng và hiển thị hạn mức.
5. **Tốc độ khung quá thấp:** ở bước 4, hệ thống cảnh báo rằng dự đoán sẽ không
   đáng tin.
6. **Cửa sổ dữ liệu sai định dạng hoặc quá lớn:** ở bước 4, hệ thống từ chối
   **trước khi** cửa sổ tới được dịch vụ suy luận. Kiểm tra ở tầng truyền tải
   thuộc về nền tảng; chuẩn hoá và giải mã nhãn thuộc về dịch vụ suy luận — **sự
   phân chia này là có chủ đích**.
7. **Quá nhiều cửa sổ đang chờ:** ở bước 4, hệ thống giới hạn số cửa sổ đang gửi
   cùng lúc và đặt thời hạn cho những cửa sổ dịch vụ không trả lời, để một máy
   khách quá tải không làm cạn đường nhận dạng của mọi người.

### UC501 — Quản lý tổ chức

| **Use Case** | Quản lý tổ chức | **ID** | UC501 |
|---|---|---|---|
| **Tác nhân chính** | Quản trị nền tảng | **Mức ưu tiên** | Essential |
| **Kích hoạt bởi** | Quản trị nền tảng | **Loại** | external |

**Mô tả ngắn:** *Quản trị nền tảng tạo, sửa, đình chỉ và xoá mềm tổ chức; đồng
thời gán tài khoản vào tổ chức theo mã tài khoản.*

**Quan hệ:**
- **Association:** Quản trị nền tảng – Quản lý tổ chức
- **Include:** không · **Extend:** không *(UC310 mở rộng use case này)*

**Luồng chính:**
1. Quản trị viên mở trang quản lý tổ chức.
2. Tạo tổ chức: nhập mã định danh, tên, gói cước khởi điểm.
3. Hệ thống tạo tổ chức và **sao chép danh mục mồi** vào tổ chức đó (UC310).
4. Quản trị viên gán tài khoản đầu tiên làm quản trị tổ chức, **theo mã tài
   khoản**.
5. Hệ thống ghi nhật ký kiểm toán cho mọi thao tác trên.

**Luồng ngoại lệ:**
1. **Trùng mã định danh tổ chức:** từ chối ở bước 2.
2. **Xoá tổ chức:** là **xoá mềm**; dữ liệu còn lại cho tới khi có yêu cầu dọn
   sạch tường minh (UC508), thao tác này đòi xác thực lại.
3. **Đình chỉ tổ chức:** khác xoá. Đình chỉ tác động lên trục **quản trị**; trạng
   thái quá hạn thanh toán tác động lên trục **thương mại**. Hai trục độc lập.

**Ghi chú ranh giới:** đường "gán theo mã tài khoản" ở bước 4 **chỉ** thuộc về
quản trị nền tảng. Quản trị tổ chức đưa người vào bằng **lời mời** (UC502), vì mã
tài khoản không phải bí mật — xem Chương 1 §2.0.

### UC705 — Sao lưu và khôi phục dữ liệu

| **Use Case** | Sao lưu và khôi phục dữ liệu | **ID** | UC705 |
|---|---|---|---|
| **Tác nhân chính** | Kỹ sư vận hành | **Mức ưu tiên** | Essential |
| **Kích hoạt bởi** | Bộ lập lịch, hoặc kỹ sư vận hành | **Loại** | internal / external |

**Mô tả ngắn:** *Hệ thống kết xuất cơ sở dữ liệu theo lịch, kiểm tính toàn vẹn
bản kết xuất, và cho phép diễn tập khôi phục vào một cơ sở dữ liệu tạm.*

**Quan hệ:**
- **Association:** Kỹ sư vận hành – Sao lưu và khôi phục; Tiến trình nền (S4)

**Luồng chính:**
1. Bộ lập lịch kích hoạt tác vụ sao lưu.
2. Hệ thống kết xuất cơ sở dữ liệu ra tệp.
3. Hệ thống nén tệp kết xuất — **theo đúng thứ tự này**, kết xuất trước nén sau.
4. Hệ thống kiểm tính toàn vẹn bằng cách **đọc hết nội dung** bản kết xuất.
5. Hệ thống ghi bản sao vào kho thứ hai.
6. Hệ thống xoá các bản cũ quá hạn giữ.

**Luồng ngoại lệ:**
1. **Đĩa đầy:** tác vụ dừng và phát cảnh báo; **không** ghi đè bản cũ để lấy chỗ.
2. **Bản kết xuất bị cụt:** phát hiện ở bước 4 và đánh dấu bản đó hỏng. Công cụ
   chỉ đọc mục lục **không** phát hiện được lỗi này — đó là lý do bước 4 phải đọc
   hết nội dung.
3. **Diễn tập khôi phục thất bại:** phát cảnh báo; một bản sao lưu chưa được diễn
   tập khôi phục được coi là **chưa tồn tại**.

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
