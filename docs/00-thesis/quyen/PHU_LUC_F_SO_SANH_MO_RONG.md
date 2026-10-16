# PHỤ LỤC F: PHÂN TÍCH SO SÁNH MỞ RỘNG CHO CÁC QUYẾT ĐỊNH KIẾN TRÚC

*Phụ lục này chứa **bản đầy đủ** của các bảng so sánh mà thân Chương 2 chỉ trình
bày ở mức tiêu chí quyết định. Không nội dung nào bị lược bỏ khỏi luận văn: thân
chương giữ những tiêu chí trực tiếp dẫn tới lựa chọn, còn toàn bộ tiêu chí thứ
cấp, tiêu chí vận hành và trường hợp biên được đưa về đây.*

---

## F.0. Cách đọc phụ lục này

**Phụ lục soi gương Chương 2.** Mỗi mục `F.n` tương ứng đúng mục `2.n`:

| Mục Chương 2 | Mục phụ lục | Nội dung mở rộng |
|---|---|---|
| 2.1 Dữ liệu, chất lượng, mô hình hoá | F.1 | Bảng siêu dữ liệu và chuẩn hoá bản đầy đủ |
| 2.2 Kiến trúc đa thuê bao | F.2 | Ma trận 15 tiêu chí giữa ba mô hình tổ chức dữ liệu |
| 2.3 Phạm vi quản trị, chia sẻ danh mục | F.3 | Ma trận đầy đủ ba cách chia sẻ danh mục |
| 2.4 Cô lập tenant | F.4 | Ma trận 10 tiêu chí giữa bốn chiến lược cưỡng chế |
| 2.5 Danh tính và kiểm soát truy cập | F.5 | Ma trận năm mô hình phân quyền, phiên/token, nhật ký |
| 2.6 Thu thập và thu nhận dữ liệu | F.6 | Bốn ma trận đầy đủ của đường thu |
| 2.7 Xử lý, giao dịch, lưu trữ | F.7 | Ba ma trận đầy đủ về xử lý và nhất quán |
| 2.8 Phiên bản, nguồn gốc, toàn vẹn | F.8 | Ma trận đầy đủ ba mô hình phiên bản |
| 2.9 Quản trị người tham gia | F.9 | Ma trận đầy đủ về đồng thuận |
| 2.10 Kiểu kiến trúc và triển khai | F.10 | Ma trận đầy đủ ba kiểu kiến trúc |
| 2.11 Định vị và tổng hợp | F.11 | Đối chiếu hệ thống liên quan và **danh mục 31 quyết định** |

**Ba điều phụ lục này KHÔNG chứa**, để không lẫn khi tra cứu:

* **Không chứa lập luận lựa chọn.** Lý do chọn một phương án và đánh đổi kèm theo
  nằm hoàn toàn trong thân Chương 2. Đọc riêng phụ lục sẽ thấy các phương án được
  so sánh nhưng không thấy vì sao chọn — đó là chủ ý, không phải thiếu sót.
* **Không chứa chi tiết hiện thực.** Tên bảng dữ liệu, chính sách cụ thể, cấu hình
  và mã nguồn thuộc Chương 3 cùng Phụ lục A và B.
* **Không chứa bằng chứng thực nghiệm.** Số liệu đo, ca kiểm thử và giới hạn của
  phép đo thuộc Chương 4 cùng Phụ lục D và E.

**Quy ước đánh số.** Bảng ở đây đánh số `Bảng F-n` theo thứ tự xuất hiện; mỗi bảng
ghi rõ nó mở rộng cho bảng nào của thân Chương 2.

---

## F.1. Đặc trưng dữ liệu, chất lượng và mô hình hoá

*Mở rộng cho Chương 2 §2.1.*

**Mục này không có bảng mở rộng, và đó là kết quả của việc áp dụng luật tách chứ
không phải một chỗ còn thiếu.**

Các bảng của §2.1 — bốn nhóm đặc trưng dữ liệu (Bảng 2-2), siêu dữ liệu tối thiểu
(Bảng 2-3), sáu chiều chất lượng dữ liệu (Bảng 2-4), ba thời điểm kiểm tra
(Bảng 2-5), ba mức mô hình dữ liệu (Bảng 2-6), chuẩn hoá và phi chuẩn hoá
(Bảng 2-7), ba cách tổ chức định danh (Bảng 2-8) và bốn loại toàn vẹn quan hệ
(Bảng 2-9) — **đã ở mức tiêu chí quyết định**. Mỗi dòng của chúng là một loại câu
hỏi riêng biệt, không phải một tiêu chí thứ cấp của cùng một kết luận. Tách bớt
dòng nào cũng làm mất một nhánh lập luận, nên toàn bộ được giữ trong thân chương.

Đây là ví dụ cho nguyên tắc ở đầu phụ lục: **phụ lục không phải nơi chứa mọi thứ
dài, mà là nơi chứa phần chi tiết của một kết luận đã rõ.** Khi một bảng không có
phần chi tiết tách được, nó không sinh ra mục phụ lục tương ứng.

Cơ sở lý thuyết của mục 2.1 được trích từ \cite{codd_relational_1970},
\cite{chen_entity-relationship_1976} và \cite{elmasri_fundamentals_2015} cho mô
hình hoá dữ liệu, cùng \cite{wang_beyond_1996} cho khái niệm chất lượng dữ liệu
nhiều chiều.

---

## F.2. Các phương án kiến trúc đa thuê bao

*Mở rộng cho Chương 2 §2.2.*

### F.2.1. So sánh ba mô hình tổ chức dữ liệu đa thuê bao — 15 tiêu chí

Thân §2.2.7 chỉ giữ bảy tiêu chí dẫn trực tiếp tới lựa chọn. Tám tiêu chí còn lại nằm ở đây: sao lưu và khôi phục riêng tenant, hiệu suất sử dụng tài nguyên, mức tuỳ biến cho từng tenant, nghiệp vụ đọc ngang nhiều tenant, nguy cơ lệch lược đồ, chi phí khởi tạo tenant mới, yêu cầu về toàn vẹn xuyên phạm vi, và rủi ro đặc trưng của từng mô hình.

**Bảng F-1. So sánh ba mô hình tổ chức dữ liệu đa thuê bao**

| Tiêu chí | CSDL riêng theo tenant | Lược đồ riêng theo tenant | Lược đồ dùng chung |
|---|---|---|---|
| Mức chia sẻ tài nguyên | Thấp | Trung bình | Cao |
| Ranh giới dữ liệu | Cấp cơ sở dữ liệu | Cấp lược đồ | Cấp hàng |
| Di trú cấu trúc | Lặp theo từng CSDL | Lặp theo từng lược đồ | Tập trung, một lần |
| Nguy cơ lệch lược đồ | Cao | Có | Thấp |
| Khởi tạo tenant mới | Cấp phát hạ tầng | Trung bình | Thao tác ghi dữ liệu |
| Sao lưu riêng một tenant | Thuận lợi | Trung bình | Khó hơn, cần lọc theo phạm vi |
| Khôi phục riêng một tenant | Thuận lợi | Trung bình | Khó hơn |
| Chi phí vận hành theo số tenant | Cao | Trung bình | Thấp |
| Hiệu suất sử dụng tài nguyên | Thấp | Trung bình | Cao |
| Tùy biến riêng cho tenant | Cao | Trung bình – cao | Có kiểm soát, trong khuôn khổ lược đồ chung |
| Nghiệp vụ đọc ngang nhiều tenant | Khó | Trung bình | Thuận lợi |
| Yêu cầu đối với cơ chế cưỡng chế cô lập | Thấp hơn | Trung bình | **Rất cao** |
| Yêu cầu về toàn vẹn xuyên phạm vi | Ít phát sinh | Ít phát sinh | **Phải thiết kế tường minh** |
| Phù hợp khi các tenant dùng chung mô hình miền | Có | Có | Rất phù hợp |
| Rủi ro đặc trưng cần phòng ngừa | Vận hành không theo kịp | Sai đường tìm kiếm lược đồ | **Rò dữ liệu khi truy vấn sót điều kiện phạm vi** |

*Nguồn: tác giả tổng hợp định tính từ \cite{bezemer_multi-tenant_2010,chong_architecture_2006,aulbach_multi-tenant_2008,krebs_architectural_2012}; bảng thể hiện so sánh tương đối theo tiêu chí thiết kế, không phải kết quả đo hiệu năng.*

*Bảng này là bản đầy đủ của **Bảng 2-12** ở thân Chương 2.*

---

## F.3. Phạm vi quản trị và các cách chia sẻ danh mục

*Mở rộng cho Chương 2 §2.3.*

### F.3.1. So sánh ba cách chia sẻ danh mục — bản đầy đủ

Thân §2.3.4 giữ sáu tiêu chí phân định. Ở đây bổ sung các tiêu chí về chi phí lưu trữ, khả năng truy vết nguồn gốc của một mục danh mục, và điều kiện tiên quyết của phương án được chọn.

**Bảng F-2. So sánh ba cách chia sẻ danh mục giữa nền tảng và tenant**

| Tiêu chí | A. Dùng chung lúc chạy | B. Tra cứu dự phòng | C. Sao chép có ghim phiên bản |
|---|---|---|---|
| Chi phí lưu trữ | Thấp | Thấp | Cao hơn |
| Mức độ độc lập của tenant | Thấp | Trung bình | Cao |
| Khả năng tùy biến danh mục riêng | Hạn chế | Trung bình | Cao |
| Cập nhật ở nguồn ảnh hưởng tenant | Trực tiếp và tức thì | Có thể, không báo trước | Không ngầm; chỉ khi tenant chủ động cập nhật |
| Kết quả phân giải phụ thuộc thời điểm | Có | **Có** | Không |
| Khả năng tái lập của bộ dữ liệu | Thấp | Trung bình | Cao |
| Khả năng truy vết nguồn gốc mục danh mục | Khó | Trung bình | Rõ ràng qua quan hệ nguồn – phiên bản |
| Điều kiện tiên quyết để có hiệu lực | — | — | **Phiên bản được ghim phải bất biến** |
| Định hướng phù hợp với yêu cầu tái lập | | | **Được chọn** |

*Nguồn: tác giả tổng hợp; tiêu chí phân biệt chính là sự phụ thuộc của kết quả phân giải vào trạng thái thượng nguồn tại thời điểm truy vấn.*

*Bảng này là bản đầy đủ của **Bảng 2-15** ở thân Chương 2.*

---

## F.4. Cô lập tenant và phân tích mô hình đe doạ

*Mở rộng cho Chương 2 §2.4.*

### F.4.1. So sánh bốn chiến lược cưỡng chế cô lập — 10 tiêu chí

Thân §2.4.9 giữ sáu tiêu chí quyết định. Ở đây bổ sung các tiêu chí vận hành, khả năng kiểm chứng bằng kiểm thử hành vi, và dòng về mô hình đe doạ thứ hai.

**Bảng F-3. So sánh bốn chiến lược cưỡng chế cô lập dữ liệu**

| Tiêu chí | Lọc ở tầng ứng dụng | Gán phạm vi ở tầng trung gian | Cưỡng chế ở tầng CSDL | Tách hạ tầng vật lý |
|---|---|---|---|---|
| Mức độ dễ triển khai | Cao | Cao | Trung bình | Thấp |
| Phụ thuộc vào kỷ luật lập trình viên | Rất cao | Trung bình | Thấp | Thấp |
| Bảo vệ được truy vấn SQL thô | Không | Không | Có | Có |
| Bảo vệ được tác vụ nền và kịch bản bảo trì | Không chắc | Không chắc | Có, nếu chạy dưới vai runtime | Có |
| Hành vi khi thiếu ngữ cảnh | Do mã quyết định, dễ fail-open | Do mã quyết định | Mặc định từ chối, tự nhiên fail-closed | Không phát sinh |
| Khả năng suy giảm theo thời gian | Cao — mã mới có thể sót | Trung bình | Thấp | Thấp |
| Kiểm chứng bằng kiểm thử hành vi | Khó phủ hết mọi đường | Khó phủ hết | Kiểm được ở một điểm cưỡng chế | Kiểm được |
| Chống được kẻ tấn công có thông tin xác thực CSDL | Không | Không | **Không** (xem Bảng 2-17) | Có |
| Chi phí vận hành | Thấp | Thấp | Thấp – trung bình | Cao |
| Phù hợp với lược đồ dùng chung | Có nhưng yếu | Có, chưa đủ | **Rất phù hợp** | Không phải mô hình đã chọn |

*Nguồn: tác giả tổng hợp từ \cite{postgresql_rls_2026,saltzer_protection_1975,krebs_architectural_2012,bezemer_multi-tenant_2010,shostack_threat_2014}.*

*Bảng này là bản đầy đủ của **Bảng 2-18** ở thân Chương 2.*

---

## F.5. Các phương án danh tính và kiểm soát truy cập

*Mở rộng cho Chương 2 §2.5.*

### F.5.1. So sánh năm mô hình kiểm soát truy cập — bản đầy đủ

Thân §2.5.7 giữ năm tiêu chí. Ở đây bổ sung chi phí mô hình hoá và hạ tầng, cùng khả năng diễn đạt điều kiện theo ngữ cảnh của từng mô hình.

**Bảng F-4. So sánh năm mô hình kiểm soát truy cập**

| Tiêu chí | ACL | RBAC | ABAC | ReBAC | RBAC theo phạm vi |
|---|---|---|---|---|---|
| Đơn vị cấp quyền | Cặp chủ thể – tài nguyên | Vai trò | Thuộc tính | Quan hệ trong đồ thị | Vai trò trong phạm vi |
| Khả năng quản lý khi quy mô tăng | Thấp | Cao | Trung bình | Trung bình | Cao |
| Khả năng kiểm toán quyền hiệu dụng | Trung bình | Cao | Thấp – trung bình | Trung bình | Cao |
| Diễn đạt điều kiện theo ngữ cảnh | Thấp | Trung bình | Cao | Cao | Trung bình |
| Ánh xạ vào trách nhiệm trong tổ chức | Yếu | Cao | Có thể | Có thể | Cao |
| Hỗ trợ phạm vi đa thuê bao | Thủ công | Cần mở rộng | Có thể qua thuộc tính | Tự nhiên qua quan hệ | **Tự nhiên** |
| Chi phí mô hình hóa và hạ tầng | Thấp | Thấp – trung bình | Cao | Cao | Trung bình |
| Định hướng được chọn | | | | | **Được chọn** |

*Nguồn: tác giả tổng hợp từ \cite{ferraiolo_proposed_2001,sandhu_role-based_1996,hu_guide_2014,casbin_authors_casbin_2024,casbin_authors_rbac_2026,pang_zanzibar_2019}.*

*Bảng này là bản đầy đủ của **Bảng 2-19** ở thân Chương 2.*

### F.5.2. Phiên có trạng thái và token tự chứa — bản đầy đủ

Thân §2.5.8 giữ bốn tiêu chí phân định. Các tiêu chí vận hành còn lại nằm ở đây.

**Bảng F-5. So sánh phiên có trạng thái và token tự chứa**

| Tiêu chí | Phiên có trạng thái | Token tự chứa được ký |
|---|---|---|
| Nơi giữ trạng thái | Máy chủ | Một phần nằm trong token |
| Xác minh mỗi yêu cầu | Tra kho phiên | Kiểm chữ ký |
| Thu hồi tức thì | Trực tiếp | Cần cơ chế bổ sung |
| Quyền bị cũ sau khi đổi vai | Không | Có, tới khi token hết hạn |
| Mở rộng theo chiều ngang | Cần kho phiên dùng chung | Thuận lợi hơn |
| Phù hợp với API nhiều máy khách | Trung bình | Cao |
| Rủi ro khi token bị lộ | Thu hồi được ngay | Còn hiệu lực tới hạn hoặc tới khi có cơ chế chặn |

*Nguồn: tác giả tổng hợp từ \cite{jones_json_2015,sheffer_json_2020,hardt_oauth_2012,nist_sp800_63b_2025}.*

*Bảng này là bản đầy đủ của **Bảng 2-20** ở thân Chương 2.*

### F.5.3. Nhật ký vận hành và nhật ký kiểm toán — bản đầy đủ

Thân §2.5.9 giữ năm tiêu chí. Ở đây bổ sung thời gian lưu, khả năng sửa hoặc xoá, và nhóm người đọc của từng loại nhật ký.

**Bảng F-6. Nhật ký vận hành và nhật ký kiểm toán**

| Tiêu chí | Nhật ký vận hành | Nhật ký kiểm toán |
|---|---|---|
| Mục tiêu | Chẩn đoán, gỡ lỗi, quan trắc | Quy trách nhiệm, đối chiếu nghĩa vụ |
| Người đọc chính | Người vận hành | Người quản trị, người rà soát, chủ thể dữ liệu |
| Chủ thể hành động | Không bắt buộc | **Bắt buộc** |
| Phạm vi và tài nguyên | Không luôn có | **Bắt buộc** |
| Kết quả, kể cả bị từ chối | Thường chỉ ghi lỗi kỹ thuật | **Bắt buộc, gồm cả từ chối** |
| Thời gian lưu | Theo nhu cầu vận hành | Theo chính sách và nghĩa vụ |
| Khả năng sửa hoặc xóa | Có thể xoay vòng tự do | Cần kiểm soát chặt |
| Hệ quả nếu thiếu | Khó gỡ lỗi | **Không chứng minh được điều gì đã xảy ra** |

*Nguồn: tác giả tổng hợp từ \cite{saltzer_protection_1975,nist_sp800_63b_2025}; yêu cầu về khả năng chứng minh liên hệ với các nghĩa vụ ở mục 2.9.*

*Bảng này là bản đầy đủ của **Bảng 2-21** ở thân Chương 2.*

---

## F.6. Phân tích thu thập và thu nhận dữ liệu

*Mở rộng cho Chương 2 §2.6.*

### F.6.1. So sánh ba phương thức thu nhận — bản đầy đủ

Thân §2.6.2 giữ năm tiêu chí ảnh hưởng trực tiếp tới nguồn gốc và mức kiểm soát quy trình thu. Ở đây bổ sung tính đồng nhất về định dạng và điều kiện, cách ánh xạ vào danh mục lớp, và khả năng tận dụng dữ liệu đã tồn tại.

**Bảng F-7. So sánh ba phương thức thu nhận dữ liệu**

| Tiêu chí | Thu trực tiếp | Đóng góp tệp đã có | Nhập từ nguồn ngoài |
|---|---|---|---|
| Mức kiểm soát quy trình thu | Cao | Trung bình | Thấp |
| Siêu dữ liệu tại thời điểm tạo mẫu | Hệ thống **quan sát** được | Do người tải **khai báo** | Phải ánh xạ từ nguồn |
| Liên kết người ký – phiên thu | Tự nhiên, do quy trình sinh ra | Cần khai báo tường minh | Có thể không tồn tại ở nguồn |
| Tính đồng nhất về định dạng và điều kiện | Cao | Thấp | Thấp |
| Ánh xạ vào danh mục lớp | Xác định trước khi thu | Xác định sau | Cần ánh xạ, có thể không toàn phần |
| Độ tin cậy của nguồn gốc | Cao | Trung bình | Phụ thuộc nguồn |
| Tận dụng được dữ liệu đã tồn tại | Thấp | Cao | Cao |
| Phù hợp để thu mới có kiểm soát | Cao | Trung bình | Thấp |

*Nguồn: tác giả tổng hợp; tiêu chí phân biệt chính là việc siêu dữ liệu bối cảnh do hệ thống quan sát hay do bên đóng góp khai báo.*

*Bảng này là bản đầy đủ của **Bảng 2-23** ở thân Chương 2.*

### F.6.2. So sánh ba chiến lược thu thập — bản đầy đủ

Thân §2.6.3 giữ năm tiêu chí. Ở đây bổ sung rào cản đối với người đóng góp và khả năng theo dõi độ bao phủ theo từng chiến lược.

**Bảng F-8. So sánh ba chiến lược thu thập**

| Tiêu chí | Thu có hướng dẫn | Đóng góp mở | Kết hợp |
|---|---|---|---|
| Mức đầy đủ của siêu dữ liệu | Cao, theo thiết kế | Thấp hơn, phụ thuộc khai báo | Cao ở luồng thu mới |
| Rào cản đối với người đóng góp | Trung bình | Thấp | Thấp ở luồng đóng góp |
| Tính nhất quán của nhãn lớp | Cao — xác định trước khi thu | Phụ thuộc khai báo sau | Có kiểm soát theo luồng |
| Nguồn gốc người ký và phiên thu | Cao | Có thể thiếu | Khác nhau theo luồng, được ghi nhận |
| Tận dụng dữ liệu đã tồn tại | Thấp | Cao | Cao |
| Theo dõi độ bao phủ | Trực tiếp | Khó | Được ở luồng có hướng dẫn |
| Định hướng được chọn | | | **Được chọn** |

*Nguồn: tác giả tổng hợp.*

*Bảng này là bản đầy đủ của **Bảng 2-24** ở thân Chương 2.*

### F.6.3. So sánh các mức biểu diễn dữ liệu — bản đầy đủ

Thân §2.6.6 giữ sáu tiêu chí quyết định. Ở đây bổ sung băng thông tải lên, chi phí tính toán ở hạ nguồn, và từng thành phần thị giác được giữ lại hay mất đi.

**Bảng F-9. So sánh các mức biểu diễn dữ liệu thu nhận**

| Tiêu chí | Video nguồn | Chuỗi khung ảnh | Điểm mốc toàn thân | Điểm mốc bàn tay |
|---|---|---|---|---|
| Lượng thông tin thị giác giữ lại | Rất cao | Rất cao | Cao | Giới hạn |
| Hình học bàn tay | Gián tiếp | Gián tiếp | Có | Trực tiếp |
| Thành phần khuôn mặt và đầu | Có | Có | Tùy cấu hình | Không |
| Tư thế cơ thể | Có | Có | Có | Không |
| Dung lượng lưu trữ mỗi mẫu | Cao | Cao | Thấp | Rất thấp |
| Băng thông tải lên | Cao | Cao | Thấp | Rất thấp |
| Khả năng trích xuất lại đặc trưng khác | Cao nhất | Cao | Hạn chế | Không |
| Chi phí tính toán ở hạ nguồn | Cao | Trung bình | Trung bình | Thấp |
| Mức phơi bày thông tin nhận dạng | Cao | Cao | Trung bình | Thấp hơn — **không phải ẩn danh** |
| Định hướng cho biểu diễn dẫn xuất chính | | | | **Được chọn** |

*Nguồn: tác giả tổng hợp; các mức định tính, không phải kết quả đo. Số liệu định lượng về hiệu quả lưu trữ được trình bày ở Chương 4.*

*Bảng này là bản đầy đủ của **Bảng 2-26** ở thân Chương 2.*

### F.6.4. Trích xuất tại máy khách và máy chủ — bản đầy đủ

Thân §2.6.7 giữ năm tiêu chí. Ở đây bổ sung tính đồng nhất của phần cứng, khả năng mở rộng, và khả năng xử lý lại về sau.

**Bảng F-10. So sánh trích xuất tại máy khách và tại máy chủ**

| Tiêu chí | Trích xuất tại máy khách | Trích xuất tại máy chủ |
|---|---|---|
| Tải tính toán trên máy chủ | Thấp hơn | Cao |
| Băng thông tải lên | Thấp nếu chỉ gửi điểm mốc | Cao nếu phải gửi video |
| Tính đồng nhất của phần cứng | Thấp — thiết bị người dùng rất khác nhau | Cao |
| Môi trường thực thi | Không đồng nhất, ngoài tầm kiểm soát | Được kiểm soát |
| Mức phơi bày dữ liệu thị giác | Có thể thấp hơn trong luồng không cần video | Dữ liệu nguồn phải tới máy chủ |
| Mức tin cậy của dữ liệu nhận được | **Không tin cậy hoàn toàn** — sinh ra ngoài tầm kiểm soát | Do backend tạo, tin cậy hơn |
| Khả năng mở rộng | Phân tán theo số người dùng | Tập trung, phải cấp thêm tài nguyên |
| Khả năng xử lý lại về sau | Cần dữ liệu nguồn được giữ | Thuận lợi nếu giữ nguồn |
| Định hướng cho luồng thu điểm mốc | **Được chọn** | |

*Nguồn: tác giả tổng hợp.*

*Bảng này là bản đầy đủ của **Bảng 2-27** ở thân Chương 2.*

---

## F.7. Xử lý, giao dịch và lưu trữ

*Mở rộng cho Chương 2 §2.7.*

### F.7.1. Xử lý đồng bộ và bất đồng bộ — bản đầy đủ

Thân §2.7.1 giữ năm tiêu chí. Ở đây bổ sung yêu cầu về quan trắc, lượng trạng thái phải quản lý, và cách ngữ cảnh tenant được truyền.

**Bảng F-11. So sánh xử lý đồng bộ và xử lý bất đồng bộ**

| Tiêu chí | Đồng bộ | Bất đồng bộ |
|---|---|---|
| Độ phức tạp triển khai | Thấp | Cao hơn |
| Có kết quả ngay trong phản hồi | Có | Không nhất thiết |
| Phù hợp với công việc dài | Không | Có |
| Khả năng thử lại độc lập | Khó | Tốt hơn |
| Độ trễ của yêu cầu người dùng | Bằng thời gian của bước chậm nhất | Ngắn, độc lập với công việc |
| Cô lập thất bại | Thấp | Cao hơn |
| Trạng thái phải quản lý | Không | Nhiều: trạng thái tác vụ, hàng đợi, kết quả |
| Yêu cầu về quan trắc | Thấp | Cao — công việc chạy ngoài tầm nhìn của người dùng |
| Ngữ cảnh tenant | Thừa hưởng từ yêu cầu | **Phải truyền tường minh** (mục 2.7.6) |

*Nguồn: tác giả tổng hợp từ \cite{kleppmann_designing_2017,hohpe_enterprise_2003}.*

*Bảng này là bản đầy đủ của **Bảng 2-28** ở thân Chương 2.*

### F.7.2. Ba chiến lược nhất quán xuyên kho — bản đầy đủ

Thân §2.7.4 giữ năm tiêu chí. Ở đây bổ sung yêu cầu đối với kho ngoài, cơ chế thử lại, và độ phức tạp vận hành của từng chiến lược.

**Bảng F-12. So sánh ba chiến lược nhất quán giữa cơ sở dữ liệu và kho nội dung**

| Tiêu chí | A. Ghi kép trực tiếp | B. Giao dịch phân tán | C. Giao dịch cục bộ + khôi phục bất đồng bộ |
|---|---|---|---|
| Đơn giản khi mới triển khai | Cao | Thấp | Trung bình |
| Tính nguyên tử xuyên hệ thống | Không | Cao | Nhất quán cuối cùng |
| Yêu cầu đối với kho ngoài | Không | **Phải hỗ trợ giao thức cam kết** | Không |
| Cơ chế thử lại | Phải tự xây | Do giao thức xử lý | Tự nhiên, có trạng thái |
| Phát hiện được trạng thái lệch | Không | Không phát sinh | **Có — trạng thái tường minh** |
| Rủi ro tệp mồ côi / tham chiếu hỏng | Cao | Thấp | Thấp, có đối soát |
| Độ phức tạp vận hành | Thấp | Cao | Trung bình |
| Định hướng được chọn | | | **Được chọn** |

*Nguồn: tác giả tổng hợp từ \cite{kleppmann_designing_2017,harder_principles_1983,richardson_microservices_2018,hohpe_enterprise_2003}.*

*Bảng này là bản đầy đủ của **Bảng 2-29** ở thân Chương 2.*

### F.7.3. Lưu nội dung trong và ngoài CSDL — bản đầy đủ

Thân §2.7.5 giữ năm tiêu chí. Ở đây bổ sung sao lưu, truy vấn theo siêu dữ liệu, và khả năng mở rộng độc lập hai tầng.

**Bảng F-13. So sánh lưu nội dung trong cơ sở dữ liệu và lưu bên ngoài**

| Tiêu chí | Nội dung trong CSDL | Nội dung ngoài CSDL + siêu dữ liệu trong CSDL |
|---|---|---|
| Tính đơn giản của giao dịch | Cao — một ranh giới giao dịch duy nhất | Thấp hơn — hai kho, cần chiến lược ở mục 2.7.4 |
| Phù hợp với tệp lớn | Thấp | Cao |
| Tốc độ tăng kích thước CSDL | Cao | Thấp |
| Khả năng mở rộng độc lập hai tầng | Khó | Tốt hơn |
| Truy vấn theo siêu dữ liệu | Cao | Cao — vẫn qua CSDL |
| Sao lưu | Một đơn vị | Hai đơn vị, phải đồng bộ về thời điểm |
| Vấn đề nhất quán xuyên kho | Không phát sinh | **Phải quản lý** |
| Cưỡng chế cô lập | Theo cơ chế của CSDL | Cần điểm kiểm soát riêng cho đường đọc nội dung |
| Định hướng cho nội dung dung lượng lớn | | **Được chọn** |

*Nguồn: tác giả tổng hợp từ \cite{kleppmann_designing_2017,saltzer_protection_1975}.*

*Bảng này là bản đầy đủ của **Bảng 2-30** ở thân Chương 2.*

---

## F.8. Phiên bản, nguồn gốc và toàn vẹn

*Mở rộng cho Chương 2 §2.8.*

### F.8.1. So sánh ba mô hình phiên bản bộ dữ liệu — bản đầy đủ

Thân §2.8.2 giữ năm tiêu chí. Ở đây bổ sung độ phức tạp hiện thực và mức tường minh của quan hệ nguồn gốc.

**Bảng F-14. So sánh ba mô hình quản lý phiên bản bộ dữ liệu**

| Tiêu chí | A. Khả biến | B. Ảnh chụp đầy đủ | C. Bản kê tham chiếu |
|---|---|---|---|
| Tham chiếu lịch sử | Không có | Có | Có |
| Khả năng tái lập | Thấp | Cao | Cao |
| Chi phí lưu trữ | Thấp | Cao — nhân bản theo phiên bản | Thấp hơn B đáng kể |
| Phù hợp với nội dung phương tiện lớn | Ban đầu thuận lợi | Tốn kém nhanh | Phù hợp |
| Độ phức tạp hiện thực | Đơn giản | Trung bình | Trung bình — thêm đồ thị tham chiếu |
| Tường minh về nguồn gốc | Không | Ngầm định qua bản sao | **Tường minh qua bản kê** |
| Điều kiện tiên quyết | — | — | **Đối tượng được tham chiếu phải bất biến** |
| Định hướng được chọn | | | **Được chọn** |

*Nguồn: tác giả tổng hợp.*

*Bảng này là bản đầy đủ của **Bảng 2-31** ở thân Chương 2.*

---

## F.9. Quản trị dữ liệu người tham gia

*Mở rộng cho Chương 2 §2.9.*

### F.9.1. Đồng thuận nhị phân và có phiên bản — bản đầy đủ

Thân §2.9.3 giữ năm tiêu chí. Ở đây bổ sung cách xử lý khi văn bản được sửa đổi và khả năng kiểm toán.

**Bảng F-15. So sánh đồng thuận nhị phân và đồng thuận có phiên bản**

| Tiêu chí | Đồng thuận nhị phân | Đồng thuận có phiên bản |
|---|---|---|
| Biết chủ thể đã chấp thuận hay chưa | Có | Có |
| Biết đã chấp thuận **nội dung nào** | Không | Có |
| Biết chấp thuận vào thời điểm nào | Không nhất thiết | Có |
| Phân biệt phạm vi sử dụng | Không | Có, nếu phạm vi được mô hình hóa |
| Bằng chứng lịch sử khi văn bản thay đổi | Thấp | Cao |
| Xử lý khi văn bản được sửa đổi | Không phân biệt được trước/sau | Tạo phiên bản mới, giữ lịch sử |
| Khả năng kiểm toán | Thấp | Cao |
| Định hướng được chọn | | **Được chọn** |

*Nguồn: tác giả tổng hợp.*

*Bảng này là bản đầy đủ của **Bảng 2-36** ở thân Chương 2.*

---

## F.10. Kiểu kiến trúc, triển khai và tiến hoá

*Mở rộng cho Chương 2 §2.10.*

### F.10.1. So sánh ba kiểu kiến trúc phần mềm — bản đầy đủ

Thân §2.10.1 giữ năm tiêu chí. Ở đây bổ sung chi phí vận hành và quan trắc, cùng cách ranh giới giữa các phần được cưỡng chế.

**Bảng F-16. So sánh ba kiểu kiến trúc phần mềm**

| Tiêu chí | Nguyên khối | Nguyên khối có mô-đun | Vi dịch vụ |
|---|---|---|---|
| Độ phức tạp triển khai | Thấp | Thấp – trung bình | Cao |
| Tính đơn giản của giao dịch | Cao | Cao | Thấp — phải xử lý xuyên dịch vụ |
| Mở rộng độc lập từng năng lực | Thấp | Trung bình | Cao |
| Chi phí vận hành và quan trắc | Thấp | Trung bình | Cao |
| Ranh giới giữa các phần | Tùy kỷ luật | Cao nếu được cưỡng chế | Cao, cưỡng chế bởi ranh giới tiến trình |
| Phù hợp với nhóm phát triển nhỏ | Cao | Cao | Thấp |
| Định hướng được chọn | | **Được chọn** | |

*Nguồn: tác giả tổng hợp từ \cite{bass_software_2021,newman_building_2021}.*

*Bảng này là bản đầy đủ của **Bảng 2-38** ở thân Chương 2.*

---

## F.11. Định vị so sánh và danh mục quyết định đầy đủ

*Mở rộng cho Chương 2 §2.11.*

### F.11.1. Đối chiếu các hệ thống liên quan — bản đầy đủ

Thân §2.11.2 giữ bảy tiêu chí định vị. Ba tiêu chí còn lại nằm ở đây: cô lập ở tầng cơ sở dữ liệu, xử lý bất đồng bộ nội dung phương tiện, và quan hệ với bên tiêu thụ ở hạ nguồn.

**Bảng F-17. Đối chiếu các hệ thống liên quan theo tiêu chí của chương**

| Tiêu chí | ELAN | REDCap | Dataverse, Zenodo | WLASL, AUTSL | QIPEDC | Phân hệ của luận văn |
|---|---|---|---|---|---|---|
| Giai đoạn chính trong vòng đời | Chú giải | Thu thập theo biểu mẫu | Nộp lưu và công bố | Sản phẩm dữ liệu đã hình thành | Tài nguyên từ vựng tham chiếu | Thu nhận, quản trị và công bố |
| **Thu trực tiếp có hướng dẫn** | Không phải trọng tâm | Biểu mẫu có hướng dẫn, không phải thu thị giác | Không | Không áp dụng | Không phải nền tảng thu | **Có, dẫn theo lớp và người ký** |
| **Đóng góp tệp đã có** | Làm việc trên dữ liệu đã có | Có thể đính kèm | Là phương thức chính | Không áp dụng | Không áp dụng | **Có, đường riêng có yêu cầu siêu dữ liệu** |
| **Theo dõi độ bao phủ theo lớp × người ký × vùng** | Không phải trọng tâm | Theo dõi được ở mức bản ghi | Không phải trọng tâm | Là thuộc tính của bản phát hành | Là danh mục, không phải dữ liệu mẫu | **Đo được qua siêu dữ liệu bắt buộc** |
| Mô hình miền chuyên biệt cho ngôn ngữ ký hiệu | Hỗ trợ chú giải đa phương thức | Không chuyên biệt | Không | Có, ở mức nội dung dữ liệu | Có, ở mức từ vựng | Có, ở mức lược đồ |
| Danh mục ngôn ngữ – phương ngữ – lớp có phiên bản | Không phải trọng tâm | Không có danh mục miền | Siêu dữ liệu và phiên bản ở mức đối tượng nộp lưu | Không phải cơ chế của bộ dữ liệu | Có ngữ cảnh vùng, không có cơ chế phiên bản cho tenant | Thành phần cốt lõi |
| Mô hình người ký và phiên thu | Có thể chú giải | Có thể cấu hình theo nghiên cứu | Do người nộp khai báo | Có siêu dữ liệu tương ứng | Không áp dụng | Thực thể bậc nhất, gắn từ thời điểm thu |
| Phạm vi nhiều tổ chức | Không phải trọng tâm | Dự án và nghiên cứu đa điểm | Phạm vi của kho | Không áp dụng | Không áp dụng | Tenant – workspace – project |
| Cô lập ở tầng cơ sở dữ liệu | Không phải trọng tâm | Phụ thuộc triển khai | Theo mô hình của kho | Không áp dụng | Không áp dụng | Mối quan tâm thiết kế trung tâm |
| Phiên bản của bộ dữ liệu | Theo tệp và dự án | Không phải trọng tâm | Có | Theo bản phát hành | Không áp dụng | Theo vòng đời dữ liệu |
| Đồng thuận gắn với chủ thể tại thời điểm thu | Quy trình ngoài công cụ | Có thể cấu hình | Không thuộc giai đoạn thu | Không thuộc phạm vi công cụ | Không áp dụng | Mối quan tâm của đường thu |
| Xử lý bất đồng bộ nội dung phương tiện | Không phải trọng tâm | Không phải trọng tâm | Xử lý của kho lưu trữ | Không áp dụng | Không áp dụng | Thành phần của luồng thu |
| Quan hệ với bên tiêu thụ ở hạ nguồn | Bên ngoài | Bên ngoài | Bên ngoài | Là dữ liệu đầu vào | Là nguồn danh mục | Tích hợp như bên tiêu thụ dữ liệu |

*Nguồn: tác giả tổng hợp trong phạm vi các lớp công cụ được khảo sát, dựa trên \cite{wittenburg_elan_2006,harris_research_2009,harris_redcap_2019,crosas_dataverse_2011,cern_openaire_zenodo_2013,li_wlasl_baibao_2020,sincan_autsl_2020,bogddt_qipedc_2019}; các ô mô tả trọng tâm thiết kế của từng lớp công cụ, **không phải** đánh giá chất lượng.*

*Bảng này là bản đầy đủ của **Bảng 2-42** ở thân Chương 2.*

### F.11.2. Danh mục đầy đủ các quyết định kiến trúc — 31 dòng

Thân §2.11.4 giữ bảng tóm tắt mười bốn nhóm quyết định. Danh mục đầy đủ ba mươi mốt quyết định — kèm các phương án đã cân nhắc, lý do chọn, đánh đổi phải chấp nhận và mục tương ứng của Chương 2 — nằm ở đây.

**Bảng F-18. Tổng hợp các quyết định kiến trúc, phương án và cơ sở lựa chọn**

| Quyết định | Các phương án chính | Định hướng được chọn | Lý do chính | Đánh đổi phải chấp nhận | Mục |
|---|---|---|---|---|---|
| Thời điểm kiểm tra chất lượng | Làm sạch hậu kỳ, kiểm tra lúc thu, kết hợp | Kết hợp theo tiêu chí tái tạo được | Siêu dữ liệu mất đi là mất vĩnh viễn; đánh giá định tính thì không | Hai cơ chế thay vì một; cần trạng thái trung gian | 2.1.5 |
| Mức chuẩn hóa lược đồ | Chuẩn hóa, phi chuẩn hóa | Chuẩn hóa cho dữ liệu giao dịch, phi chuẩn hóa có chủ đích cho ảnh chụp | Ảnh chụp phải bảo toàn ngữ nghĩa lịch sử | Bản sao có thể lệch; chỉ an toàn nếu ảnh chụp bất biến | 2.1.6 |
| Chiến lược định danh | Khóa tự nhiên, khóa thay thế, khóa tổ hợp theo phạm vi | Kết hợp cả ba theo vai trò | Ba loại trả lời ba câu hỏi khác nhau | Lược đồ phức tạp hơn một mô hình thuần nhất | 2.1.6 |
| Tổ chức dữ liệu đa thuê bao | CSDL riêng, lược đồ riêng, lược đồ dùng chung | Lược đồ dùng chung | Các tenant dùng chung mô hình miền; di trú tập trung | Ranh giới thành logic; phát sinh hai nghĩa vụ mới | 2.2.7 |
| Toàn vẹn quan hệ xuyên tenant | Khóa ngoại thông thường, khóa tổ hợp có khóa phạm vi | Khóa tổ hợp có khóa phạm vi | Toàn vẹn tham chiếu không hàm ý toàn vẹn xuyên phạm vi | Khóa ngoại cồng kềnh hơn | 2.2.6 |
| Cưỡng chế cô lập | Lọc ở ứng dụng, gán phạm vi ở tầng trung gian, cưỡng chế ở CSDL, tách hạ tầng | Ràng buộc lược đồ + phân quyền + cưỡng chế ở CSDL | Cơ chế dựa vào kỷ luật lập trình suy giảm theo thời gian | Không mở rộng bảo đảm sang mô hình đe dọa II | 2.4.9 |
| Hành vi khi thiếu ngữ cảnh | Fail-open, fail-closed | Fail-closed | Thiếu ngữ cảnh phải cho 0 hàng, không phải toàn bộ bảng | Công việc nền hợp lệ phải cấp phạm vi tường minh | 2.4.6 |
| Phạm vi cộng đồng | Bỏ lọc phạm vi, phạm vi được quản trị tường minh | Phạm vi được quản trị tường minh | Dùng chung không đồng nghĩa không có phạm vi | Cần hành động đưa dữ liệu vào phạm vi, không tự động | 2.3.2 |
| Mô hình phân quyền | ACL, RBAC, ABAC, ReBAC, RBAC theo phạm vi | RBAC theo phạm vi | Ánh xạ vào trách nhiệm tổ chức; kiểm toán được | Diễn đạt điều kiện ngữ cảnh kém hơn ABAC | 2.5.7 |
| Kế thừa quyền theo cây phạm vi | Kế thừa ngầm, khai báo tường minh | Khai báo tường minh | Phân cấp tài nguyên không đồng nghĩa phân cấp vai | Nhiều khai báo hơn | 2.5.6 |
| Mô hình phiên | Phiên có trạng thái, token tự chứa | Token cho claim, giữ trạng thái nơi cần thu hồi | Cân bằng khả năng mở rộng và khả năng thu hồi | Quyền có thể cũ trong thời gian sống của token | 2.5.8 |
| Thao tác nhạy cảm | Chỉ dựa vào phiên hợp lệ, yêu cầu chứng minh lại | Chứng minh lại danh tính cho nhóm rủi ro cao | Phiên hợp lệ không chứng minh quyền kiểm soát hiện tại | Thêm ma sát cho người dùng ở một số thao tác | 2.5.8 |
| Ghi nhận hành động | Chỉ nhật ký vận hành, tách nhật ký kiểm toán | Tách nhật ký kiểm toán có chủ thể và kết quả | Kiểm soát truy cập không trả lời "điều gì đã xảy ra" | Thêm dữ liệu phải lưu và bảo vệ; hai yêu cầu kéo ngược nhau | 2.5.9 |
| Kế thừa danh mục | Dùng chung lúc chạy, tra cứu dự phòng, sao chép có ghim | Sao chép có ghim phiên bản | Kết quả phân giải không phụ thuộc thời điểm | Trùng lặp; phụ thuộc tính bất biến của phiên bản | 2.3.4 |
| Đơn vị thu thập | Theo tệp, theo phiên thu | Theo phiên thu | Phạm vi ảnh hưởng của một sự cố thu phải truy vấn được, không phải suy đoán | Thêm một thực thể và một bước trong quy trình thu | 2.6.1 |
| Phương thức thu nhận | Coi mọi mẫu như nhau, ghi nhận phương thức | Ghi nhận phương thức như thuộc tính nguồn gốc | Siêu dữ liệu do hệ thống *quan sát* khác mức tin cậy với do người dùng *khai báo* | Hạ nguồn phải xử lý dữ liệu không đồng nhất về mức tin cậy | 2.6.2 |
| Chiến lược thu thập | Thu có hướng dẫn, đóng góp mở, kết hợp | Kết hợp, hai đường tách biệt | Ép một quy trình chung sẽ hoặc loại dữ liệu hợp lệ, hoặc hạ chuẩn luồng thu mới | Duy trì hai tập ràng buộc; phải ghi nhận mẫu đến theo đường nào | 2.6.3 |
| Trách nhiệm về độ bao phủ | Bảo đảm cân bằng, chỉ đo được | Chỉ đo được và quản trị được | Tuyên bố cân bằng là một khẳng định thống kê không có cơ sở | Người dùng phải tự diễn giải và điều chỉnh kế hoạch thu | 2.6.4 |
| Biểu diễn dữ liệu | Video nguồn, khung ảnh, điểm mốc toàn thân, điểm mốc bàn tay | Điểm mốc bàn tay làm biểu diễn dẫn xuất chính | Gọn; video không bắt buộc rời máy người dùng | Mất mát một chiều; không phải ẩn danh | 2.6.1 |
| Vị trí trích xuất đặc trưng | Máy khách, máy chủ | Máy khách cho luồng thu điểm mốc | Phân bố tải; giảm phơi bày | Payload nằm ngoài ranh giới tin cậy; phải kiểm lại | 2.6.3 |
| Tổ chức bước xử lý | Đồng bộ, bất đồng bộ | Ngắn thì đồng bộ, dài hoặc cần thử lại thì bất đồng bộ | Tránh cả hai thái cực | Trạng thái phức tạp hơn; cần quan trắc | 2.7.1 |
| Ngữ nghĩa giao nhận | Giả định exactly-once, thiết kế cho at-least-once | At-least-once kèm xử lý lũy đẳng | Không phân biệt được "chưa xử lý" với "mất xác nhận" | Mỗi bước phải tự bảo đảm lũy đẳng | 2.7.2 |
| Nhất quán giữa hai kho | Ghi kép trực tiếp, giao dịch phân tán, giao dịch cục bộ + khôi phục | Giao dịch cục bộ + khôi phục bất đồng bộ | Kho ngoài không tham gia giao thức cam kết; cần biết khi nào lệch | Nhất quán cuối cùng; thêm tiến trình nền và đối soát | 2.7.4 |
| Lưu nội dung | Trong CSDL, ngoài CSDL | Ngoài CSDL, siêu dữ liệu trong CSDL | Tệp lớn không hợp với tải công việc quan hệ | Nhất quán xuyên kho; cần điểm kiểm quyền riêng | 2.7.5 |
| Phiên bản bộ dữ liệu | Khả biến, ảnh chụp đầy đủ, bản kê tham chiếu | Bản kê tham chiếu, ghim phiên bản danh mục | Tái lập được mà không nhân bản nội dung | Phụ thuộc tính bất biến của đối tượng được tham chiếu | 2.8.2 |
| Mô hình nguồn gốc | Quan hệ đặc thù, khung đối tượng – hoạt động – chủ thể | Khung ba thành phần ở mức mô hình miền | Buộc tách cái gì, quá trình nào và ai chịu trách nhiệm | Không tuyên bố tuân thủ đầy đủ chuẩn | 2.8.5 |
| Bảo đảm toàn vẹn nội dung | Số phiên bản, hash, chữ ký số | Bản kê băm kèm chữ ký số | Hash phát hiện thay đổi; chữ ký xác minh nguồn công bố | Tamper-evident chứ không tamper-proof | 2.8.6 |
| Xử lý khi xác minh thất bại | Quay về bản khác, từ chối | Từ chối, fail-closed | Quay lui im lặng che giấu lỗi toàn vẹn | Một lỗi xác minh làm dừng luồng tiêu thụ | 2.8.7 |
| Mô hình đồng thuận | Nhị phân, có phiên bản | Có phiên bản, gắn chủ thể dữ liệu | Cần biết đã chấp thuận nội dung nào, khi nào | Phải giữ bất biến văn bản và lịch sử phiên bản | 2.9.3 |
| Kiểu kiến trúc phần mềm | Nguyên khối, nguyên khối có mô-đun, vi dịch vụ | Nguyên khối có mô-đun | Các bất biến then chốt cần một ranh giới giao dịch chung | Mở rộng riêng từng năng lực khó hơn | 2.10.1 |
| Chiến lược tiến hóa hệ thống | Thay thế toàn bộ, thay thế dần | Thay thế dần, có chế độ song song | Giới hạn phạm vi rủi ro; sai khác trở thành bằng chứng | Thời gian chuyển đổi dài hơn; duy trì hai đường | 2.10.3 |

*Nguồn: tác giả tổng hợp từ các lập luận trong Chương 2.*

*Bảng này là bản đầy đủ của **Bảng 2-43** ở thân Chương 2.*

---
