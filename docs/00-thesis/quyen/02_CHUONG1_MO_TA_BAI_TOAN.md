# CHƯƠNG 1: MÔ TẢ BÀI TOÁN

*Chương này trả lời ba câu hỏi, theo đúng thứ tự đó: bài toán nghiệp vụ là gì, hệ
thống phải làm được những gì, và những ràng buộc nào giới hạn cách làm. Toàn bộ
chức năng liệt kê ở đây đều có ít nhất một điểm cuối API, một màn hình hoặc một
công cụ vận hành thật đứng sau; chỗ nào hệ thống chưa làm được, chương nói thẳng
là chưa.*

---

## 1. Mô tả chi tiết bài toán

### 1.1 Bối cảnh nghiệp vụ

Ngôn ngữ Ký hiệu Việt Nam (VSL) là ngôn ngữ tự nhiên của cộng đồng người khiếm
thính – khiếm ngôn Việt Nam [@woodward_sign_2000]. Về mặt tài nguyên tính toán,
nó thuộc nhóm **ngôn ngữ ít tài nguyên**: khối lượng dữ liệu có gán nhãn nhỏ hơn
nhiều bậc so với các ngôn ngữ ký hiệu đã có bộ dữ liệu tham chiếu công khai như
WLASL [@li_wlasl_baibao_2020] hay AUTSL [@sincan_autsl_2020].

Điều đáng chú ý là **thiếu hụt không nằm ở nỗ lực thu thập**. Các nhóm nghiên cứu
trong nước đã và đang thu dữ liệu VSL [@pham_vietnamese_2021; @chu_cross-attention_2025;
@nguyenquoc_multiview_2026], và ngành giáo dục đã xây dựng từ điển ký hiệu ở quy
mô quốc gia [@bogddt_qipedc_2019]. Thiếu hụt nằm ở chỗ khác: **những nỗ lực đó
không cộng dồn được**. Mỗi nhóm thu theo quy ước riêng, gán nhãn theo danh mục
riêng, lưu theo định dạng riêng, và ràng buộc sử dụng theo thoả thuận riêng. Kết
quả là n nhóm tạo ra n bộ dữ liệu rời rạc chứ không tạo ra một bộ dữ liệu lớn gấp
n lần.

Bài toán của đề tài vì thế **không phải** "thu thêm dữ liệu VSL", mà là: *xây một
hạ tầng để nhiều đơn vị cùng thu dữ liệu trên một nền tảng chung, mà vẫn giữ được
ranh giới sở hữu, ranh giới điều kiện sử dụng, và khả năng tái lập của từng bộ dữ
liệu*.

Ba nhóm hưởng lợi trực tiếp:

| Bên liên quan | Cần gì ở hệ thống | Nếu không có hệ thống thì sao |
|---|---|---|
| **Người khiếm thính – khiếm ngôn** (chủ thể dữ liệu) | Đóng góp ký hiệu bản ngữ, và **kiểm soát được** dữ liệu của mình được dùng tới đâu | Ký hiệu của họ nằm trong các bộ dữ liệu mà họ không biết phạm vi sử dụng, không rút lại được |
| **Nhóm nghiên cứu / cơ sở đào tạo** | Thu dữ liệu theo danh mục chuẩn, tái lập được thí nghiệm, không lộ dữ liệu sang nhóm khác | Mỗi nhóm dựng lại toàn bộ hạ tầng thu thập, và dữ liệu không dùng chung được |
| **Đơn vị vận hành nền tảng** | Đặt luật chung, giữ bằng chứng, và bảo đảm ranh giới giữa các tổ chức không thủng | Không ai chịu trách nhiệm khi dữ liệu của hai đơn vị lẫn vào nhau |

### 1.2 Ba vấn đề nghiệp vụ cụ thể

Bài toán tổng quát ở trên phân rã thành ba vấn đề mà hệ thống phải giải, và cả ba
đều **kiểm chứng được** — nghĩa là nêu được điều kiện để nói hệ thống đã giải hay
chưa.

**Vấn đề 1 — Ranh giới dữ liệu giữa các tổ chức không thể dựa vào kỷ luật lập
trình.** Khi nhiều tổ chức dùng chung một bản triển khai, cách phổ biến nhất là
mỗi truy vấn tự thêm điều kiện lọc theo tổ chức. Cách này hỏng theo một kiểu đặc
biệt nguy hiểm: **hỏng im lặng**. Một hàm truy vấn quên điều kiện lọc vẫn chạy,
vẫn trả kết quả, vẫn qua được kiểm thử chức năng — chỉ có điều nó trả cả dữ liệu
của tổ chức khác, và không có thông báo lỗi nào.

Bằng chứng cho thấy đây không phải nguy cơ lý thuyết: trong chính hệ thống này,
ba hàm truy vấn ở tầng truy cập dữ liệu — xoá một mẫu, xoá mẫu theo lớp, cập nhật
đường dẫn lưu trữ — **không có điều kiện lọc theo tổ chức**. Vá tay được ba hàm
đã biết; không vá được những hàm sẽ viết sau mà tác giả quên lọc.

Điều kiện để nói vấn đề này đã giải: *một truy vấn không khai báo tổ chức phải trả
về **không hàng nào**, chứ không phải mọi hàng; và ứng dụng không được tự vô hiệu
hoá cơ chế đó.*

**Vấn đề 2 — Một bộ dữ liệu không tái lập được thì không dùng để nghiên cứu
được.** Một mẫu ký hiệu chỉ có nghĩa khi biết nó thuộc lớp nào, theo phương ngữ
nào, do ai ký. Nếu danh mục lớp thay đổi mà không ghi phiên bản, thì hai lần chạy
huấn luyện cách nhau một tháng trên "cùng một bộ dữ liệu" thực chất chạy trên hai
tập nhãn khác nhau, và không ai phát hiện ra.

Đây cũng là lỗi đã xảy ra thật: danh sách hồ sơ nhận dạng từng được gắn cứng ở hai
nơi trong mã và **đã lệch nhau** (6 mục so với 5 mục), khiến bảy lớp bị loại khỏi
bước chia dữ liệu **trong im lặng**.

Điều kiện để nói vấn đề này đã giải: *mọi bộ dữ liệu phải ghim được một phiên bản
danh mục bất biến, và việc thiếu dữ liệu danh mục phải làm hệ thống **dừng**, chứ
không suy đoán.*

**Vấn đề 3 — Người có bàn tay trong dữ liệu phải là một chủ thể có quyền, không
phải một cột siêu dữ liệu.** Tài khoản bấm nút thu mẫu và người thực hiện ký hiệu
**không phải một người**. Một nghiên cứu sinh có thể thu hàng trăm mẫu của nhiều
người ký khác nhau. Nếu hệ thống chỉ ghi nhận tài khoản thu, thì khi một người ký
yêu cầu rút lại phần đóng góp của mình, hệ thống **không xác định nổi đó là những
dòng nào**.

Đo trên kho dữ liệu hiện có ngày 10/08/2026: định danh tài khoản thu phủ 95,7 %
số mẫu, còn định danh người ký chỉ phủ **43,4 %**. Nghĩa là **56,6 % kho dữ liệu
không truy được về người có bàn tay trong đó**. Con số này là một kết quả cần báo
cáo, không phải một khiếm khuyết cần giấu.

Điều kiện để nói vấn đề này đã giải: *đồng thuận phải gắn với người ký, có phiên
bản, và phải thực sự chi phối đường phát hành dữ liệu — chứ không chỉ là một ô
tích trong biểu mẫu.*

### 1.3 Phạm vi bài toán

| Thuộc phạm vi | Ngoài phạm vi |
|---|---|
| Thu nhận dữ liệu ký hiệu qua webcam và qua tệp video | Nhận dạng ký hiệu **liên tục** (câu, đoạn) |
| Biểu diễn dữ liệu bằng điểm mốc bàn tay | Thu nhận tư thế toàn thân và biểu cảm khuôn mặt |
| Danh mục từ vựng, phương ngữ và vùng miền có phiên bản | Xây dựng từ điển VSL đầy đủ |
| Cách ly dữ liệu giữa các tổ chức, cưỡng chế ở tầng CSDL | Cách ly **hiệu năng** giữa các tổ chức |
| Đồng thuận, quy kết và quản trị dữ liệu chủ thể | Cơ chế pháp lý thu hồi giấy phép đã cấp cho bên thứ ba |
| Huấn luyện mô hình nhận dạng từ đơn và phục vụ suy luận | Cải tiến kiến trúc mô hình học sâu |
| Nguồn sự thật ký số cho danh mục và lược đồ | Sổ cái phân tán |

Hai loại trừ cần nói rõ vì dễ bị hiểu nhầm thành thiếu sót:

*Không đánh giá độ chính xác mô hình.* Đối tượng của đề tài là **hạ tầng**, không
phải mô hình. Một con số độ chính xác cao trên bộ dữ liệu mất cân bằng hiện tại
(64 % là lớp bảng chữ cái) sẽ nói về bộ dữ liệu chứ không nói về hệ thống. Mô
hình ở đây đóng vai người tiêu thụ dữ liệu, để chứng minh vòng đời khép kín.

*Không chứng minh cách ly hiệu năng.* Hệ thống có hạn mức và giới hạn tần suất,
nhưng hai thứ đó không chứng minh được rằng một tổ chức không làm chậm tổ chức
khác. Muốn khẳng định điều đó phải có thí nghiệm tải riêng, và luận văn không làm
việc đó.

### 1.4 Luồng nghiệp vụ trục chính

Toàn bộ nghiệp vụ của hệ thống xoay quanh **vòng đời của một mẫu dữ liệu**. Hiểu
được vòng đời này là hiểu được vì sao hệ thống có tám nhóm chức năng chứ không
phải một.

```
[1] Danh tính & đồng thuận      → ai đóng góp, và đồng ý tới mức nào
        ↓
[2] Danh mục từ vựng             → được phép thu lớp nào, phương ngữ nào
        ↓
[3] Thu nhận                     → webcam (trích điểm mốc tại trình duyệt)
                                   hoặc tệp video (lưu bản thô trước)
        ↓
[4] Xử lý bất đồng bộ            → cắt cửa sổ · tăng cường · chấm chất lượng
        ↓
[5] Kiểm duyệt & quản trị        → xem lại, sửa, xoá mềm, thùng rác
        ↓
[6] Ảnh chụp bộ dữ liệu          → ghim phiên bản danh mục, bất biến
        ↓
[7] Huấn luyện & đánh giá        → qua ba cổng chặn (đồng thuận, sàn lớp, hạn mức)
        ↓
[8] Thăng hạng & phục vụ         → mô hình đang phục vụ, nhận dạng thời gian thực
```

Hai nhánh cắt ngang vòng đời này, và chúng là chỗ hệ thống khác một công cụ thu
dữ liệu thông thường:

* **Nhánh rút đồng thuận.** Người ký rút lại đồng thuận ở bước [1] thì mọi bản
  phát hành **sau đó** ở bước [6] phải loại dữ liệu của họ. Nhánh này chạy ngược
  chiều dòng chảy chính, và đó là lý do đồng thuận không thể là một cột siêu dữ
  liệu thụ động.
* **Nhánh nguồn sự thật.** Danh mục ở bước [2] được công bố dưới dạng tạo tác đã
  ký; mọi máy chủ trước khi chạy phải xác minh chữ ký. Không xác minh được thì
  **dừng cả hệ thống**, không suy đoán.

> ### ▣ HÌNH 1-8 — Vòng đời một mẫu dữ liệu xuyên ba nghiệp vụ
> **Loại:** sơ đồ hoạt động (activity diagram) · **Công cụ:** draw.io hoặc Mermaid
> **Nguồn dựng:** `docs/09-specs/USE_CASE_SPECIFICATION.md` §6.2
> **Phải thể hiện:** tám bước của vòng đời trên; hai nhánh cắt ngang (rút đồng
> thuận, xác minh nguồn sự thật); nút quyết định "dùng được?" dẫn sang xoá mềm →
> thùng rác → khôi phục hoặc mất hẳn; mã UC ghi cạnh từng bước.
> **Chú thích dưới hình:** *Hình 1-8: Vòng đời một mẫu dữ liệu, từ đồng thuận tới
> mô hình đang phục vụ.*

---

## 2. Các chức năng của hệ thống

### 2.0 Tác nhân

Hệ thống có **10 tác nhân người** và **6 tác nhân hệ thống**.

*Bảng 1-1: Bốn nhóm tác nhân*

| Nhóm | Gồm | Đặc điểm chung |
|---|---|---|
| Chưa có danh tính | A1 Khách vãng lai | Không đăng nhập; chỉ chạm được phần công khai |
| Người dùng cuối | A2 Người dùng đã đăng nhập «abstract», A3 Người khiếm thính – khiếm ngôn, A4 Người dùng bình thường | Dùng hệ thống để **giao tiếp** và giữ tài khoản của mình |
| Bên tổ chức / bên thứ ba | A5 Thành viên tổ chức, A6 Biên tập viên / Nghiên cứu sinh, A7 Quản trị tổ chức | Thuộc một tổ chức; **đóng góp và khai thác dữ liệu** trong ranh giới tổ chức đó |
| Bên vận hành nền tảng | A8 Quản trị nền tảng, A9 Nhân viên hỗ trợ, A10 Kỹ sư vận hành | Giữ cả nền tảng chạy đúng, cho **mọi** tổ chức |

*Bảng 1-2: Chi tiết tác nhân người và cơ chế phân biệt*

Cột cuối trả lời một câu quan trọng: **hệ thống có tự phân biệt được vai này
không?** Ký hiệu: ✅ kiểm được bằng một điều kiện cụ thể trong mã hoặc CSDL ·
🟡 kiểm được lớp quyền bao ngoài nhưng không kiểm được chính vai đó · ⚠️ không có
cột, cờ hay điều kiện nào phân biệt.

| Mã | Tác nhân | Kế thừa | Mục tiêu chính | Số UC | Hệ thống kiểm bằng |
|---|---|---|---|:--:|---|
| A1 | Khách vãng lai | — | Tìm hiểu, đọc văn bản pháp lý, dùng thử nhận dạng, tạo tài khoản | 7 | không có phiên đăng nhập ✅ |
| A2 | Người dùng đã đăng nhập «abstract» | — | Giữ danh tính, hồ sơ, đồng thuận, thông báo, kênh hỗ trợ của chính mình | 10 | kiểm phiên đăng nhập ✅ |
| A3 | Người khiếm thính – khiếm ngôn | A2 | **Chủ thể dữ liệu**: ký hiệu bản ngữ để đóng góp mẫu, và dùng nhận dạng để giao tiếp | 3 | ⚠️ không phân biệt được |
| A4 | Người dùng bình thường | A2 | Nghe – nói được; dùng hệ thống để **hiểu** người ký | 1 | ⚠️ không phân biệt được |
| A5 | Thành viên tổ chức | A2 | Đưa mẫu vào hệ thống và quản lý mẫu của mình trong tổ chức | 10 | là thành viên của một tổ chức ✅ |
| A6 | Biên tập viên / Nghiên cứu sinh | A5 | Giữ danh mục lớp sạch; biến dữ liệu thành mô hình và kết quả trích dẫn được | 13 | vai `editor` trong tổ chức ✅ |
| A7 | Quản trị tổ chức | A6 | Điều hành **một** tổ chức: thành viên, hạn mức, xuất dữ liệu, tích hợp | 7 | vai `admin` trong tổ chức ✅ |
| A8 | Quản trị nền tảng | — | Đặt luật cho mọi tổ chức và giữ bằng chứng | 16 | cờ quản trị nền tảng trên tài khoản ✅ |
| A9 | Nhân viên hỗ trợ | A8 | Trực hàng đợi phiếu hỗ trợ | 1 | 🟡 hiện dùng chung quyền quản trị nền tảng |
| A10 | Kỹ sư vận hành | A8 | Giữ hệ thống chạy đúng mã, đúng dữ liệu, có bản sao lưu | 6 | 🟡 quyền quản trị + quyền trên máy chủ |

Bốn tác nhân mang dấu ⚠️ hoặc 🟡 vẫn được giữ trong mô hình, vì lý do nghiệp vụ:

* **A3 và A4 khác nhau ở người, không khác nhau ở quyền.** Tài khoản của người
  khiếm thính và tài khoản của người nghe được có đúng cùng bộ quyền kỹ thuật.
  Cái tách họ ra là **mục tiêu** khi dùng hệ thống — và mục tiêu khác nhau vẫn
  sinh ra use case khác nhau. Bỏ A3 đi thì không còn ai để giải thích vì sao đồng
  thuận lại chi phối việc phát hành dữ liệu.
* **A9 và A10** làm hai công việc khác hẳn nhau trên cùng một quyền nền tảng.
  Tách sẵn ở tầng mô hình để khi hệ thống thêm vai riêng thì đặc tả không phải
  viết lại. Sáu use case của A10 hơn nữa **chạy ngoài ứng dụng** — trên dòng lệnh
  của máy triển khai — nên ranh giới thật của họ là quyền hệ điều hành.

**Một ranh giới không được vẽ sai: A7 ≠ A8.** Quản trị nền tảng không kế thừa
Quản trị tổ chức và ngược lại. A7 kiểm bằng vai trong một tổ chức, phạm vi đúng
**một** tổ chức, đưa người vào bằng **lời mời**. A8 kiểm bằng cờ trên tài khoản,
phạm vi toàn nền tảng, đưa người vào bằng **gán trực tiếp theo mã tài khoản**. Lý
do rất cụ thể: mã tài khoản không phải bí mật, nên nếu quản trị viên tổ chức gán
trực tiếp được, họ kéo được bất kỳ ai trên hệ thống vào tổ chức của mình mà người
kia không hay biết. Đường đưa người vào của A7 vì thế **bắt buộc** là lời mời —
thứ đòi hỏi chính người được mời hành động.

*Bảng 1-3: Sáu tác nhân hệ thống*

| Mã | Tác nhân | Gồm | Vai trò |
|---|---|---|---|
| S1 | Dịch vụ gửi tin | SMTP + cổng SMS | Gửi mã xác thực, lời mời, nhắc hạn, thư phiếu hỗ trợ, cảnh báo |
| S2 | Kho lưu trữ ngoài | Google Drive + Google Sheets | Giữ tệp đặc trưng, video thô, bản xem trước; phản chiếu nguồn sự thật để đối soát |
| S3 | Dịch vụ suy luận | Suy luận trên GPU + tổng hợp giọng nói | Phục vụ mô hình đang hoạt động, nạp nóng khi thăng hạng, đọc thành tiếng |
| S4 | Tiến trình nền | Hàng đợi tác vụ + bộ lập lịch | Trích đặc trưng, tăng cường, dựng bản xem trước, xoá tệp, đối soát, sao lưu theo lịch |
| S5 | Máy ghi nguồn sự thật | Máy được cấp khoá ký | Ghi vào nguồn sự thật và công bố bản đã ký |
| S6 | Ứng dụng bên thứ ba | Hệ thống ngoài dùng khoá API | Gọi API trong phạm vi của khoá; nhận sự kiện webhook |

*Bảng 1-4: Ma trận tác nhân × nghiệp vụ* — `●` tác nhân chính · `○` có tham gia

| Tác nhân | NV1 | NV2 | NV3 | NV4 | NV5 | NV6 | NV7 | NV8 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| A1 Khách vãng lai | ● | | | ○ | ○ | | | |
| A2 Người dùng đã đăng nhập | ● | | | | | | | ● |
| A3 Người khiếm thính – khiếm ngôn | ● | ● | | ● | | | | |
| A4 Người dùng bình thường | ○ | ○ | | ● | | | | |
| A5 Thành viên tổ chức | ○ | ● | ○ | | ○ | | | ○ |
| A6 Biên tập viên / Nghiên cứu sinh | ○ | ● | ● | ● | ○ | | | ○ |
| A7 Quản trị tổ chức | ○ | ○ | ○ | | ● | | | ● |
| A8 Quản trị nền tảng | ○ | | ● | ○ | ● | ● | ○ | |
| A9 Nhân viên hỗ trợ | | | | | | ○ | | ● |
| A10 Kỹ sư vận hành | | ○ | | | | ○ | ● | |
| S1 Dịch vụ gửi tin | ○ | | | | ○ | | | ○ |
| S2 Kho lưu trữ ngoài | | ● | | | ○ | | ○ | |
| S3 Dịch vụ suy luận | ○ | | | ● | | | | |
| S4 Tiến trình nền | | ● | | | ○ | | ● | |
| S5 Máy ghi nguồn sự thật | | | | | | | ● | |
| S6 Ứng dụng bên thứ ba | | | | | | | | ● |

> ### ▣ HÌNH 1-1 — Sơ đồ use case tổng quát
> **Loại:** sơ đồ use case UML · **Công cụ:** draw.io
> **Nguồn dựng:** `docs/09-specs/USE_CASE_SPECIFICATION.md` §6.1
> **Phải thể hiện:** 10 tác nhân người bên trái, 6 tác nhân hệ thống bên phải, 8
> khối nghiệp vụ ở giữa (mỗi khối ghi dải mã UC); các đường kế thừa tác nhân vẽ
> nét đứt; ranh giới hệ thống là một khung bao quanh 8 khối nghiệp vụ.
> **Chú thích dưới hình:** *Hình 1-1: Sơ đồ use case tổng quát — 10 tác nhân
> người, 6 tác nhân hệ thống và 8 nhóm nghiệp vụ.*

> ### ▣ HÌNH 1-2 — Cây kế thừa tác nhân
> **Loại:** sơ đồ phân cấp · **Nguồn dựng:** §2.2 của tài liệu đặc tả use case
> **Phải thể hiện:** ba chuỗi kế thừa `A2→A5→A6→A7`, `A2→{A3,A4}`, `A8→{A9,A10}`;
> A1 đứng ngoài mọi chuỗi; **A8 tách hẳn khỏi nhánh tổ chức** (đây là điểm phải
> nhìn thấy được từ hình).
> **Chú thích dưới hình:** *Hình 1-2: Cây kế thừa tác nhân và ranh giới giữa quản
> trị tổ chức với quản trị nền tảng.*

### 2.0.1 Tám nhóm nghiệp vụ

Ranh giới giữa các nghiệp vụ **không phải màn hình**, mà là **thứ đang bị quản
lý**: danh tính, dữ liệu thô, danh mục, mô hình, tổ chức, chính sách, hạ tầng, và
dịch vụ vành ngoài.

*Bảng 1-5: Tám nhóm nghiệp vụ*

| # | Nghiệp vụ | Câu hỏi nghiệp vụ đó trả lời | Mã | Số UC |
|---|---|---|---|:--:|
| 1 | Danh tính và quyền truy cập | Anh là ai, và anh đã đồng ý những gì? | UC101–UC114 | 14 |
| 2 | Thu thập và quản lý dữ liệu mẫu | Mẫu vào hệ thống bằng đường nào, và mất đi bằng đường nào? | UC201–UC213 | 13 |
| 3 | Danh mục từ vựng và phương ngữ | Được phép thu **lớp** nào, theo phương ngữ nào? | UC301–UC310 | 10 |
| 4 | Huấn luyện, đánh giá và suy luận | Dữ liệu thành mô hình bằng cách nào, rồi mô hình phục vụ ai? | UC401–UC409 | 9 |
| 5 | Tổ chức và đăng ký dịch vụ | Ai thuộc về tổ chức nào, trong hạn mức nào? | UC501–UC508 | 8 |
| 6 | Quản trị người dùng và chính sách | Ai đặt luật, và lấy gì làm bằng chứng? | UC601–UC609 | 9 |
| 7 | Vận hành hệ thống và nguồn sự thật | Hệ thống có đang chạy đúng thứ ta nghĩ không? | UC701–UC706 | 6 |
| 8 | Hỗ trợ và tích hợp | Hỏng thì kêu ai, và máy khác nối vào thế nào? | UC801–UC806 | 6 |
| | | | **Tổng** | **79** |

**Cách các nghiệp vụ nối nhau.** NV1 → NV2 → NV3 là vòng đời của một mẫu: có danh
tính và đồng thuận trước, rồi mới thu được mẫu, và mẫu chỉ có nghĩa khi thuộc về
một lớp trong danh mục. NV4 là chỗ dữ liệu thành sản phẩm. NV5, NV6, NV7 là ba
tầng quản trị **không lồng nhau**: một tổ chức tự quản mình (NV5), nền tảng đặt
luật cho mọi tổ chức (NV6), còn hạ tầng bên dưới thì không biết tổ chức là gì
(NV7). NV8 là vành ngoài.

NV6 và NV7 tách ra dù cùng do quyền quản trị nền tảng kiểm, vì chúng **hỏng theo
hai kiểu khác nhau**: NV6 sai thì chính sách sai — một tài khoản có quyền nó
không đáng có, một văn bản pháp lý sai hiệu lực. NV7 sai thì hệ thống mất dữ liệu
hoặc chạy sai mã — bản sao lưu chưa từng chạy, mã cũ đang phục vụ, nguồn sự thật
lệch khỏi bản sao. Người chịu trách nhiệm cũng khác.

**Quy ước mã số:** chữ số đầu là số hiệu nghiệp vụ, hai chữ số sau là thứ tự
trong nghiệp vụ đó, xếp theo **dòng chảy nghiệp vụ** chứ không theo bảng chữ cái.
Đặc tả chi tiết đủ 79 use case ở **Phụ lục C**; thân bài chỉ trình bày chi tiết
tám use case trục chính, mỗi nghiệp vụ một.

---

### 2.1 Nghiệp vụ 1 — Danh tính và quyền truy cập

**Phân tích nghiệp vụ.** Nghiệp vụ này trả lời hai câu tách bạch: *anh là ai* và
*anh đã đồng ý những gì*. Gộp hai câu lại là sai lầm phổ biến — một tài khoản đã
xác thực nhưng chưa chấp thuận văn bản pháp lý đang có hiệu lực thì **đăng nhập
được nhưng không ghi được gì**, và đó là hành vi có chủ ý chứ không phải lỗi.

Ba điểm nghiệp vụ đáng chú ý:

1. **Cưỡng chế đồng thuận là điều kiện tồn tại của tài khoản.** Đăng ký luôn kéo
   theo chấp thuận văn bản pháp lý; không chấp thuận thì tài khoản không được tạo.
2. **Hai đường vào khác nhau về bản chất.** Đăng ký tự do tạo một tài khoản chưa
   thuộc tổ chức nào; đăng ký theo lời mời tạo một tài khoản **đã** là thành viên
   một tổ chức. Lời mời chỉ được tiêu thụ ở đường thứ hai.
3. **Rút đồng thuận là hành động của chủ thể dữ liệu, không phải của tài khoản.**
   Đây là chỗ A3 tách khỏi A2 (xem §2.0).

*Bảng 1-6: Danh sách use case Nghiệp vụ 1*

| Mã | Chức năng | Tác nhân chính | Mức ưu tiên |
|---|---|---|---|
| UC101 | Đăng ký tài khoản | Khách vãng lai | Essential |
| UC102 | Đăng ký theo lời mời | Khách vãng lai | Essential |
| UC103 | Gửi mã xác thực | Người dùng đã đăng nhập | Essential |
| UC104 | Xác thực địa chỉ liên hệ | Người dùng đã đăng nhập | Essential |
| UC105 | Đăng nhập | Khách vãng lai | Essential |
| UC106 | Xác thực yếu tố thứ hai | Người dùng đã đăng nhập | Important |
| UC107 | Đăng xuất | Người dùng đã đăng nhập | Essential |
| UC108 | Khôi phục tài khoản | Khách vãng lai | Essential |
| UC109 | Quản lý xác thực hai yếu tố | Người dùng đã đăng nhập | Important |
| UC110 | Quản lý hồ sơ cá nhân | Người dùng đã đăng nhập | Important |
| UC111 | Xem văn bản pháp lý | Khách vãng lai | Essential |
| UC112 | Chấp thuận văn bản pháp lý | Người dùng đã đăng nhập | Essential |
| UC113 | Rút đồng thuận | Người khiếm thính – khiếm ngôn | Essential |
| UC114 | Dùng thử nhận dạng | Khách vãng lai | Optional |

*Bảng 1-14: Mô tả chức năng Đăng nhập*

| **Use Case** | Đăng nhập | **ID** | UC105 |
|---|---|---|---|
| **Tác nhân chính** | Khách vãng lai | **Mức ưu tiên** | Essential |
| **Kích hoạt bởi** | Khách vãng lai | **Loại** | external |

**Mô tả ngắn:** *Khách vãng lai đăng nhập bằng tên đăng nhập (hoặc email) và mật
khẩu để nhận một phiên làm việc. Nếu tài khoản đã bật xác thực hai yếu tố, phiên
chỉ được cấp sau khi qua yếu tố thứ hai.*

**Quan hệ:**
- **Association:** Khách vãng lai – Đăng nhập
- **Include:** không
- **Extend:** không *(UC106 mở rộng use case này)*
- **Generalization:** không

**Luồng chính:**
1. Hệ thống hiển thị biểu mẫu đăng nhập.
2. Khách nhập tên đăng nhập (hoặc email) và mật khẩu, bấm "Đăng nhập".
3. Hệ thống kiểm giới hạn số lần thử theo địa chỉ IP và theo tài khoản.
4. Hệ thống xác minh mã băm mật khẩu — hợp lệ.
5. Hệ thống kiểm trạng thái tài khoản: đang hoạt động, không bị khoá, đã chấp
   thuận các văn bản đang có hiệu lực, gói dịch vụ không ở trạng thái khoá cứng.
6. Hệ thống cấp một token truy cập và một token làm mới, ghi nhận phiên kèm thiết
   bị và địa chỉ IP, ghi một mục vào nhật ký kiểm toán.
7. Hệ thống đưa người dùng tới bảng điều khiển và hiển thị thông báo quản trị nếu
   có.

**Luồng ngoại lệ:**
1. **Sai thông tin đăng nhập:** ở bước 4, hệ thống trả **một** thông báo lỗi
   chung cho cả trường hợp không có tài khoản lẫn sai mật khẩu, để biểu mẫu không
   dùng được vào việc dò tên tài khoản.
2. **Cần yếu tố thứ hai:** ở bước 6, nếu tài khoản bật hai yếu tố, hệ thống **chưa**
   cấp phiên và yêu cầu yếu tố thứ hai (UC106).
3. **Tài khoản bị khoá hoặc đình chỉ:** ở bước 5, hệ thống từ chối và hiển thị lý
   do quản trị viên đã ghi, kèm kênh liên hệ hỗ trợ.
4. **Còn văn bản chưa chấp thuận:** ở bước 5, hệ thống vẫn cho đăng nhập nhưng
   điều hướng tới màn hình chấp thuận và **chặn mọi thao tác ghi** cho tới khi
   chấp thuận xong (UC112).
5. **Chạm trần số lần thử:** ở bước 3, hệ thống từ chối mọi lần thử tiếp theo từ
   địa chỉ IP hoặc tài khoản đó trong khoảng thời gian khoá.

> ### ▣ HÌNH 1-3 — Use case Nghiệp vụ 1: Danh tính và quyền truy cập
> **Phải thể hiện:** A1, A2, A3 bên trái; S1 bên phải; 14 use case UC101–UC114;
> các quan hệ «include» (UC101→UC112, UC102→UC103, UC104→UC103, UC108→UC103,
> UC112→UC111) và «extend» (UC102→UC101, UC106→UC105, UC113→UC112).
> **Chú thích:** *Hình 1-3: Sơ đồ use case Nghiệp vụ Danh tính và quyền truy cập.*

---

### 2.2 Nghiệp vụ 2 — Thu thập và quản lý dữ liệu mẫu

**Phân tích nghiệp vụ.** Đây là nghiệp vụ lõi. Nó trả lời hai câu đối xứng: *mẫu
vào hệ thống bằng đường nào*, và *mẫu mất đi bằng đường nào*. Câu thứ hai quan
trọng ngang câu thứ nhất — một hệ thống thu dữ liệu không có đường xoá kiểm soát
được sẽ tích luỹ dữ liệu rác cho tới lúc không dùng được.

Bốn quyết định nghiệp vụ định hình nghiệp vụ này:

1. **Hai nguồn đầu vào, một kết quả.** Thu qua webcam và tải tệp video là hai use
   case khác nhau nhưng đều kết thúc ở cùng một chỗ: một mẫu đã trích đặc trưng.
   Chúng khái quát hoá về một use case trừu tượng *Thu nhận mẫu*.
2. **Trích đặc trưng ở phía trình duyệt.** Với đường webcam, điểm mốc bàn tay
   được trích ngay tại máy người dùng, nên video thô **không bắt buộc rời khỏi
   máy đó**. Đây vừa là quyết định về quyền riêng tư, vừa là nguồn gốc của hiệu
   quả lưu trữ đo được ở Chương 4.
3. **Lưu bản thô trước khi chuẩn hoá.** Với đường tải tệp, bản gốc được ghi vào
   kho thô **trước** mọi bước chuẩn hoá, để một lỗi trong xử lý không làm mất dữ
   liệu gốc.
4. **Xoá là xoá mềm.** Xoá phiên thu, xoá mẫu và gỡ lớp đều là ba mức của cùng
   một ngữ nghĩa xoá mềm, đi qua thùng rác, khôi phục được cho tới khi dọn hẳn.

**Một use case ở nghiệp vụ này không có tác nhân người:** UC203 Xử lý bản ghi do
tiến trình nền (S4) khởi phát, mang loại `internal`.

*Bảng 1-7: Danh sách use case Nghiệp vụ 2*

| Mã | Chức năng | Tác nhân chính | Mức ưu tiên |
|---|---|---|---|
| UC201 | Thu mẫu từ camera | Người khiếm thính – khiếm ngôn | Essential |
| UC202 | Tải lên tệp video | Thành viên tổ chức | Essential |
| UC203 | Xử lý bản ghi | Tiến trình nền (S4) | Essential |
| UC204 | Theo dõi trạng thái tác vụ | Thành viên tổ chức | Important |
| UC205 | Đặt tuỳ chọn thu | Thành viên tổ chức | Optional |
| UC206 | Duyệt danh mục lớp | Thành viên tổ chức | Essential |
| UC207 | Xem chi tiết lớp | Thành viên tổ chức | Essential |
| UC208 | Xem lại video phiên thu | Thành viên tổ chức | Important |
| UC209 | Xoá phiên thu | Thành viên tổ chức | Important |
| UC210 | Gán lại người ký cho phiên thu | Biên tập viên / Nghiên cứu sinh | Optional |
| UC211 | Xoá mẫu | Thành viên tổ chức | Essential |
| UC212 | Quản lý thùng rác | Thành viên tổ chức | Important |
| UC213 | Xuất ảnh chụp bộ dữ liệu | Biên tập viên / Nghiên cứu sinh | Important |

*Bảng 1-15: Mô tả chức năng Thu mẫu từ camera*

| **Use Case** | Thu mẫu từ camera | **ID** | UC201 |
|---|---|---|---|
| **Tác nhân chính** | Người khiếm thính – khiếm ngôn | **Mức ưu tiên** | Essential |
| **Kích hoạt bởi** | Người ký | **Loại** | external |

**Mô tả ngắn:** *Người ký thực hiện một ký hiệu trước camera. Điểm mốc bàn tay
được trích ngay trong trình duyệt và gửi lên nền tảng; một lượt thu trở thành đúng
một mẫu của lớp đã chọn.*

**Quan hệ:**
- **Association:** Người ký – Thu mẫu từ camera; Thành viên tổ chức (vận hành buổi
  thu); Kho lưu trữ ngoài (S2)
- **Include:** UC203 Xử lý bản ghi
- **Extend:** không
- **Generalization:** *Thu nhận mẫu* «abstract»

**Luồng chính:**
1. Người ký mở trang thu và chọn lớp cần thu, ngôn ngữ và phương ngữ.
2. Hệ thống xin quyền camera và khởi động bộ theo dõi bàn tay tại máy khách, vẽ
   các điểm mốc phát hiện được chồng lên khung hình.
3. Hệ thống hiển thị hướng dẫn thu: khung hình, số bàn tay lớp này yêu cầu, và
   thời lượng mục tiêu.
4. Người ký bấm "Thu"; hệ thống gom các khung điểm mốc kèm dấu thời gian cho tới
   khi người ký dừng.
5. Hệ thống hiển thị cửa sổ vừa thu để xem lại và hỏi giữ hay bỏ.
6. Người ký bấm "Lưu".
7. Hệ thống kiểm hạn mức số mẫu của tổ chức, tính lượt thu này là đúng một mẫu.
8. Hệ thống gửi các khung và siêu dữ liệu (lớp, phiên thu, phương ngữ, người ký)
   lên máy chủ; máy chủ lưu mẫu và chuyển cho tiến trình xử lý nền (UC203).
9. Hệ thống hiển thị mẫu mới trong danh sách phiên thu kèm các chỉ số chất lượng.

**Luồng ngoại lệ:**
1. **Không có camera hoặc bị từ chối quyền:** ở bước 2, hệ thống hướng dẫn cách
   cấp quyền và đề nghị đường thay thế là tải tệp video (UC202).
2. **Không phát hiện được bàn tay:** ở bước 4, nếu suốt cửa sổ thu không thấy bàn
   tay nào, hệ thống từ chối lưu và gợi ý chỉnh khung hình.
3. **Lớp yêu cầu hai tay:** ở bước 4, nếu lớp yêu cầu hai tay mà chỉ theo dõi được
   một, hệ thống cảnh báo trước khi lưu. Yêu cầu này **đọc từ siêu dữ liệu của
   lớp**, không suy đoán từ khung hình.
4. **Vượt hạn mức:** ở bước 7, hệ thống từ chối lưu và hiển thị hạn mức của gói
   dịch vụ kèm đường dẫn đổi gói (UC506).
5. **Chưa có đồng thuận hiệu lực:** ở bước 6, hệ thống chặn thao tác ghi và điều
   hướng tới màn hình chấp thuận (UC112).
6. **Lỗi mạng:** ở bước 8, hệ thống **giữ lại** cửa sổ đã thu trong trình duyệt và
   cho thử lại, thay vì huỷ bản thu.

> ### ▣ HÌNH 1-4 — Use case Nghiệp vụ 2: Thu thập và quản lý dữ liệu mẫu
> **Phải thể hiện:** A3, A5, A6 bên trái; S2, S4 bên phải; 13 use case; quan hệ
> khái quát hoá `Thu nhận mẫu «abstract» → {UC201, UC202}` và
> `Xoá dữ liệu «abstract» → {UC209, UC211, UC304}`; «include» UC201→UC203 và
> UC202→UC203; UC203 đánh dấu `internal`.
> **Chú thích:** *Hình 1-4: Sơ đồ use case Nghiệp vụ Thu thập và quản lý dữ liệu mẫu.*

---

### 2.3 Nghiệp vụ 3 — Danh mục từ vựng và phương ngữ

**Phân tích nghiệp vụ.** Nghiệp vụ này trả lời câu *được phép thu lớp nào, theo
phương ngữ nào*. Nó là điều kiện tiên quyết của Nghiệp vụ 2: một mẫu không thuộc
lớp nào trong danh mục là một mẫu vô nghĩa.

Ba nguyên tắc nghiệp vụ:

1. **Phương ngữ là một phần của định danh lớp, không phải thuộc tính phụ.** Cùng
   một từ có thể có ký hiệu khác nhau ở hai vùng miền; coi chúng là một lớp thì
   mô hình học phải khớp hai phân bố mâu thuẫn.
2. **Danh mục có ba mặt phẳng, và không có đường rơi ngược.** Danh mục hệ thống
   được sao chép **một lần** vào danh mục của tổ chức khi tổ chức được tạo; từ đó
   tổ chức tự sửa danh mục của mình. Lúc chạy, hệ thống **không bao giờ** rơi
   ngược về danh mục hệ thống khi tổ chức thiếu dữ liệu — thiếu thì **dừng**.
3. **Đề xuất phương ngữ mới phải qua kiểm duyệt của nền tảng.** Nếu mỗi tổ chức
   tự đặt mã phương ngữ, hai tổ chức sẽ đặt hai mã khác nhau cho cùng một vùng
   miền, và dữ liệu hết gộp được.

*Bảng 1-8: Danh sách use case Nghiệp vụ 3*

| Mã | Chức năng | Tác nhân chính | Mức ưu tiên |
|---|---|---|---|
| UC301 | Đăng ký lớp từ vựng | Biên tập viên / Nghiên cứu sinh | Essential |
| UC302 | Cập nhật lớp | Biên tập viên / Nghiên cứu sinh | Important |
| UC303 | Gộp hai lớp trùng | Biên tập viên / Nghiên cứu sinh | Important |
| UC304 | Gỡ lớp | Biên tập viên / Nghiên cứu sinh | Important |
| UC305 | Xem thống kê thu thập | Thành viên tổ chức | Important |
| UC306 | Đề xuất phương ngữ | Biên tập viên / Nghiên cứu sinh | Optional |
| UC307 | Kiểm duyệt đề xuất phương ngữ | Quản trị nền tảng | Optional |
| UC308 | Bảo trì danh mục mẫu của cộng đồng | Quản trị nền tảng | Important |
| UC309 | Công bố phiên bản danh mục cộng đồng | Quản trị nền tảng | Important |
| UC310 | Sao chép danh mục vào một tổ chức | Quản trị nền tảng | Important |

*Bảng 1-16: Mô tả chức năng Đăng ký lớp từ vựng*

| **Use Case** | Đăng ký lớp từ vựng | **ID** | UC301 |
|---|---|---|---|
| **Tác nhân chính** | Biên tập viên / Nghiên cứu sinh | **Mức ưu tiên** | Essential |
| **Kích hoạt bởi** | Biên tập viên | **Loại** | external |

**Mô tả ngắn:** *Biên tập viên đưa một đơn vị từ vựng mới vào danh mục của tổ
chức, kèm ngôn ngữ, phương ngữ, vùng miền, nhóm từ vựng và số bàn tay yêu cầu.
Lớp chỉ tồn tại sau bước này mới thu mẫu được.*

**Quan hệ:**
- **Association:** Biên tập viên – Đăng ký lớp
- **Include:** không
- **Extend:** không *(UC302, UC303 tác động lên lớp đã đăng ký)*
- **Generalization:** không

**Luồng chính:**
1. Biên tập viên mở danh mục lớp của tổ chức và bấm "Thêm lớp".
2. Hệ thống hiển thị biểu mẫu, nạp sẵn danh sách ngôn ngữ, phương ngữ, vùng miền
   và nhóm từ vựng **của tổ chức đó**.
3. Biên tập viên nhập nhãn hiển thị, chọn ngôn ngữ – phương ngữ – vùng miền, chọn
   nhóm từ vựng và hồ sơ nhận dạng, khai số bàn tay yêu cầu.
4. Hệ thống kiểm trùng theo khoá định danh lớp — **gồm cả phương ngữ và vùng
   miền**, chứ không chỉ nhãn.
5. Hệ thống sinh mã định danh lớp, ghi vào danh mục của tổ chức và tăng phiên bản
   danh mục.
6. Hệ thống hiển thị lớp mới trong danh mục, sẵn sàng nhận mẫu.

**Luồng ngoại lệ:**
1. **Trùng lớp:** ở bước 4, hệ thống từ chối và chỉ ra lớp đang tồn tại; nếu đúng
   là hai lớp cần hợp nhất, biên tập viên chuyển sang UC303.
2. **Phương ngữ chưa có trong danh mục:** ở bước 3, hệ thống đề nghị đường đề
   xuất phương ngữ mới (UC306) thay vì cho nhập tự do.
3. **Thiếu quyền:** thành viên không có vai biên tập bị từ chối ở bước 1.
4. **Vượt hạn mức số lớp:** ở bước 5, hệ thống từ chối và hiển thị hạn mức gói.

> ### ▣ HÌNH 1-5 — Use case Nghiệp vụ 3: Danh mục từ vựng và phương ngữ
> **Phải thể hiện:** A6 và A8 ở hai phía; ranh giới giữa danh mục **của tổ chức**
> (UC301–UC306) và danh mục **của nền tảng** (UC307–UC310); mũi tên sao chép một
> chiều từ danh mục cộng đồng sang danh mục tổ chức (UC310) — vẽ **một chiều** để
> thể hiện không có đường rơi ngược.
> **Chú thích:** *Hình 1-5: Sơ đồ use case Nghiệp vụ Danh mục từ vựng và phương ngữ.*

---

### 2.4 Nghiệp vụ 4 — Huấn luyện, đánh giá và suy luận

**Phân tích nghiệp vụ.** Nghiệp vụ này là chỗ dữ liệu trở thành sản phẩm. Nó có
một đặc điểm nghiệp vụ ít gặp: **ba cổng chặn độc lập** đứng giữa "có dữ liệu" và
"chạy được huấn luyện", và ba cổng đó hỏi ba câu khác nhau:

| Cổng | Câu hỏi | Hỏng thì hậu quả gì |
|---|---|---|
| Đồng thuận | Người ký có cho phép dùng dữ liệu ở mức phát hành này không? | Phát hành dữ liệu vượt phạm vi được phép — rủi ro pháp lý |
| Sàn số mẫu mỗi lớp | Lớp này có đủ mẫu để chia tập không? | Tập kiểm thử rỗng, chỉ số đánh giá vô nghĩa |
| Hạn mức tổ chức | Tổ chức còn hạn mức tính toán không? | Một tổ chức chiếm hết tài nguyên GPU chung |

Ba cổng này **không thay thế được cho nhau**, và thứ tự áp dụng có ý nghĩa: sàn
số mẫu phải áp **trước** khi đánh chỉ số lớp, nếu không chỉ số lớp sẽ nhảy cóc và
mô hình huấn luyện trên một không gian nhãn khác với không gian nhãn lúc suy luận.

Phân biệt phải giữ rõ: **"đã đăng ký" không đồng nghĩa "huấn luyện được"**. Một
lớp có 500 mẫu mà người ký chưa đồng ý ở mức tương ứng thì với đường phát hành
nghiên cứu, nó là một lớp **rỗng**.

*Bảng 1-9: Danh sách use case Nghiệp vụ 4*

| Mã | Chức năng | Tác nhân chính | Mức ưu tiên |
|---|---|---|---|
| UC401 | Khởi động tác vụ huấn luyện | Biên tập viên / Nghiên cứu sinh | Essential |
| UC402 | Theo dõi tiến trình huấn luyện | Biên tập viên / Nghiên cứu sinh | Essential |
| UC403 | Huỷ tác vụ huấn luyện | Biên tập viên / Nghiên cứu sinh | Important |
| UC404 | Xem kết quả đánh giá và nguồn gốc | Biên tập viên / Nghiên cứu sinh | Important |
| UC405 | Thử mô hình đã huấn luyện | Biên tập viên / Nghiên cứu sinh | Important |
| UC406 | Thăng hạng phiên bản mô hình | Quản trị nền tảng | Important |
| UC407 | Nhận dạng ký hiệu thời gian thực | Người khiếm thính – khiếm ngôn | Essential |
| UC408 | Đọc thành tiếng văn bản nhận dạng | Người dùng bình thường | Optional |
| UC409 | Chuẩn bị bản phát hành nghiên cứu | Biên tập viên / Nghiên cứu sinh | Important |

*Bảng 1-17: Mô tả chức năng Khởi động tác vụ huấn luyện*

| **Use Case** | Khởi động tác vụ huấn luyện | **ID** | UC401 |
|---|---|---|---|
| **Tác nhân chính** | Biên tập viên / Nghiên cứu sinh | **Mức ưu tiên** | Essential |
| **Kích hoạt bởi** | Biên tập viên | **Loại** | external |

**Mô tả ngắn:** *Biên tập viên chọn phạm vi dữ liệu và cấu hình huấn luyện, hệ
thống kiểm ba cổng chặn rồi đưa tác vụ vào hàng đợi GPU.*

**Quan hệ:**
- **Association:** Biên tập viên – Khởi động huấn luyện; Tiến trình nền (S4)
- **Include:** không
- **Extend:** không *(UC402, UC403 thao tác trên tác vụ đã khởi động)*
- **Generalization:** không

**Luồng chính:**
1. Biên tập viên mở trang huấn luyện và chọn phạm vi: nhóm từ vựng, hồ sơ nhận
   dạng, phương ngữ, đường phát hành (nội bộ hay nghiên cứu).
2. Hệ thống hiển thị số lớp và số mẫu **thực sự đủ điều kiện** sau khi áp cổng
   đồng thuận, kèm số mẫu bị loại và lý do.
3. Biên tập viên đặt tham số huấn luyện và bấm "Bắt đầu".
4. Hệ thống áp cổng sàn số mẫu mỗi lớp, loại các lớp không đủ, rồi **mới** đánh
   chỉ số lớp trên tập lớp còn lại.
5. Hệ thống kiểm hạn mức tính toán của tổ chức.
6. Hệ thống ghim phiên bản danh mục vào bản ghi tác vụ, tạo tác vụ ở trạng thái
   `queued` và trả về mã tác vụ.
7. Tiến trình huấn luyện nhận tác vụ, chuyển trạng thái `running` và bắt đầu phát
   chỉ số theo từng chu kỳ.
8. Hệ thống hiển thị tác vụ trong danh sách kèm trạng thái theo thời gian thực.

**Luồng ngoại lệ:**
1. **Không đủ lớp sau khi lọc:** ở bước 4, nếu số lớp còn lại dưới ngưỡng tối
   thiểu, hệ thống từ chối khởi động và liệt kê từng lớp bị loại kèm lý do —
   **không** âm thầm huấn luyện trên tập nhỏ hơn.
2. **Chưa có đồng thuận đủ mức cho đường nghiên cứu:** ở bước 2, hệ thống hiển
   thị số mẫu bị loại; nếu sau khi loại còn 0 mẫu thì lớp đó báo rỗng.
3. **Vượt hạn mức tính toán:** ở bước 5, tác vụ bị từ chối kèm hạn mức của gói.
4. **Không có GPU khả dụng:** ở bước 7, tác vụ nằm lại `queued`; hệ thống hiển
   thị vị trí trong hàng đợi thay vì báo lỗi.
5. **Tác vụ hỏng giữa chừng:** hệ thống chuyển trạng thái `failed`, giữ lại nhật
   ký, và **thông báo cho chủ sở hữu tác vụ** chứ không chỉ ghi log.

> ### ▣ HÌNH 1-6 — Use case Nghiệp vụ 4: Huấn luyện, đánh giá và suy luận
> **Phải thể hiện:** A6, A8, A3, A4 và S3; ba cổng chặn vẽ thành ba nút quyết
> định trên đường vào UC401; UC407 nối tới S3; «extend» UC408→UC407 và
> UC114→UC407; «extend» UC405→UC404.
> **Chú thích:** *Hình 1-6: Sơ đồ use case Nghiệp vụ Huấn luyện, đánh giá và suy luận.*

---

### 2.5 Nghiệp vụ 5 — Tổ chức và đăng ký dịch vụ

**Phân tích nghiệp vụ.** Nghiệp vụ này trả lời *ai thuộc về tổ chức nào, trong
hạn mức nào*. Hai phân biệt phải giữ rõ:

* **Hạn mức "đang dùng" (để chặn) khác hạn mức "đã từng dùng" (để tính tiền).**
  Hai con số đọc từ hai nguồn khác nhau, có chủ đích. Con số dùng để chặn nằm trên
  đường ghi nóng; nếu nó hỏng và trả về một giá trị chặn, một sự cố cơ sở dữ liệu
  sẽ biến thành "mọi tổ chức hết hạn mức" — nhân sự cố lên nhiều lần. Ranh giới
  bảo mật thật nằm ở cơ chế cách ly, không nằm ở bộ đếm hạn mức.
* **Trạng thái thương mại khác trạng thái quản trị.** Một tổ chức quá hạn thanh
  toán **vẫn ghi được dữ liệu**. Đây là quyết định nghiệp vụ, không phải sơ suất:
  khoá dữ liệu của một trường vì hoá đơn trễ hai ngày là cách nhanh nhất để mất
  họ. Khoá cứng chỉ áp ở mức nghiêm trọng hơn nhiều.

*Bảng 1-10: Danh sách use case Nghiệp vụ 5*

| Mã | Chức năng | Tác nhân chính | Mức ưu tiên |
|---|---|---|---|
| UC501 | Quản lý tổ chức | Quản trị nền tảng | Essential |
| UC502 | Mời thành viên | Quản trị tổ chức | Essential |
| UC503 | Chấp nhận lời mời | Khách vãng lai | Essential |
| UC504 | Đổi vai thành viên | Quản trị tổ chức | Important |
| UC505 | Gỡ thành viên | Quản trị tổ chức | Important |
| UC506 | Quản lý gói dịch vụ | Quản trị tổ chức | Important |
| UC507 | Yêu cầu xuất dữ liệu tổ chức | Quản trị tổ chức | Important |
| UC508 | Dọn sạch dữ liệu tổ chức | Quản trị nền tảng | Optional |

*Bảng 1-18: Mô tả chức năng Mời thành viên*

| **Use Case** | Mời thành viên | **ID** | UC502 |
|---|---|---|---|
| **Tác nhân chính** | Quản trị tổ chức | **Mức ưu tiên** | Essential |
| **Kích hoạt bởi** | Quản trị tổ chức | **Loại** | external |

**Mô tả ngắn:** *Quản trị tổ chức gửi lời mời tới một địa chỉ liên hệ kèm vai dự
kiến. Lời mời chỉ trở thành tư cách thành viên khi chính người được mời hành
động.*

**Quan hệ:**
- **Association:** Quản trị tổ chức – Mời thành viên; Dịch vụ gửi tin (S1)
- **Include:** không
- **Extend:** không *(UC503 tiêu thụ lời mời này)*
- **Generalization:** không

**Luồng chính:**
1. Quản trị tổ chức mở trang tổ chức, tab Thành viên, bấm "Mời".
2. Nhập địa chỉ liên hệ và chọn vai dự kiến (`viewer`, `editor`, `admin`).
3. Hệ thống kiểm hạn mức số thành viên của gói dịch vụ.
4. Hệ thống sinh một lời mời có hạn dùng, mã dùng một lần, gắn với **đúng địa chỉ
   đó** và đúng tổ chức đó.
5. Hệ thống nhờ S1 gửi lời mời và hiển thị lời mời ở trạng thái `pending`.
6. Người được mời mở liên kết và hoàn tất theo UC503.
7. Hệ thống ghi tư cách thành viên, chuyển lời mời sang `accepted`, và ghi nhật
   ký kiểm toán.

**Luồng ngoại lệ:**
1. **Đã là thành viên:** ở bước 3, hệ thống từ chối và chỉ ra bản ghi thành viên
   hiện có.
2. **Vượt hạn mức thành viên:** ở bước 3, từ chối kèm hạn mức gói.
3. **Lời mời hết hạn:** ở bước 6, hệ thống từ chối và cho quản trị viên gửi lại.
4. **Địa chỉ nhận không khớp:** nếu người mở liên kết đăng nhập bằng một tài khoản
   có địa chỉ khác, hệ thống **từ chối** — lời mời gắn với địa chỉ, không gắn với
   liên kết.
5. **Gửi tin thất bại:** ở bước 5, lời mời vẫn được tạo và quản trị viên gửi lại
   được; hệ thống không im lặng bỏ qua.

---

### 2.6 Nghiệp vụ 6 — Quản trị người dùng và chính sách

**Phân tích nghiệp vụ.** Nghiệp vụ này trả lời *ai đặt luật, và lấy gì làm bằng
chứng*. Hai cơ chế nghiệp vụ đáng chú ý:

* **Văn bản pháp lý bất biến sau khi công bố.** Một chấp thuận trỏ tới một cặp
  (loại văn bản, phiên bản). Nếu nội dung phiên bản đó sửa được sau khi đã có
  người ký, thì bằng chứng chấp thuận biến thành một lời khẳng định suông. Vì thế
  bản đã công bố **không sửa được**; muốn đổi nội dung thì công bố phiên bản mới.
  Một cờ riêng tách "sửa lỗi chính tả" khỏi "đổi phạm vi xử lý dữ liệu" — chỉ
  loại thứ hai mới buộc người dùng chấp thuận lại.
* **Chế độ nâng quyền tạm thời.** Các thao tác không hoàn tác được — dọn sạch dữ
  liệu tổ chức, công bố văn bản pháp lý, đổi gói dịch vụ — đòi xác thực lại ngay
  trước khi thực hiện, dù người dùng đã đăng nhập.

*Bảng 1-11: Danh sách use case Nghiệp vụ 6*

| Mã | Chức năng | Tác nhân chính | Mức ưu tiên |
|---|---|---|---|
| UC601 | Nâng quyền tạm thời | Quản trị nền tảng | Important |
| UC602 | Quản lý tài khoản người dùng | Quản trị nền tảng | Essential |
| UC603 | Áp dụng biện pháp bảo mật | Quản trị nền tảng | Important |
| UC604 | Xem nhật ký kiểm toán | Quản trị nền tảng | Important |
| UC605 | Cấu hình tham số nền tảng | Quản trị nền tảng | Important |
| UC606 | Soạn và duyệt văn bản pháp lý | Quản trị nền tảng | Important |
| UC607 | Công bố văn bản pháp lý | Quản trị nền tảng | Essential |
| UC608 | Rà soát hồ sơ đồng thuận | Quản trị nền tảng | Important |
| UC609 | Quản lý gói cước | Quản trị nền tảng | Optional |

*Bảng 1-19: Mô tả chức năng Công bố văn bản pháp lý*

| **Use Case** | Công bố văn bản pháp lý | **ID** | UC607 |
|---|---|---|---|
| **Tác nhân chính** | Quản trị nền tảng | **Mức ưu tiên** | Essential |
| **Kích hoạt bởi** | Quản trị nền tảng | **Loại** | external |

**Mô tả ngắn:** *Quản trị nền tảng đưa một bản thảo văn bản pháp lý thành phiên
bản có hiệu lực. Bản đã công bố là bất biến; hệ thống lưu mã băm nội dung làm
bằng chứng.*

**Quan hệ:**
- **Association:** Quản trị nền tảng – Công bố văn bản pháp lý
- **Include:** UC601 Nâng quyền tạm thời
- **Extend:** không
- **Generalization:** không

**Luồng chính:**
1. Quản trị viên mở bản thảo đã duyệt (UC606) và bấm "Công bố".
2. Hệ thống yêu cầu xác thực lại (UC601).
3. Quản trị viên khai số hiệu phiên bản, ngày hiệu lực, và **có buộc chấp thuận
   lại hay không**.
4. Hệ thống tính mã băm nội dung, ghi bản công bố kèm mã băm đó và khoá bản ghi
   lại bằng ràng buộc ở tầng cơ sở dữ liệu.
5. Nếu buộc chấp thuận lại, hệ thống đánh dấu mọi tài khoản là "còn văn bản chưa
   chấp thuận" và chặn thao tác ghi của họ cho tới khi chấp thuận (UC112).
6. Hệ thống ghi một sự kiện vào lịch sử văn bản và vào nhật ký kiểm toán.

**Luồng ngoại lệ:**
1. **Trùng số hiệu phiên bản:** ở bước 4, hệ thống từ chối; số hiệu phiên bản là
   duy nhất theo loại văn bản.
2. **Cố sửa bản đã công bố:** ràng buộc ở tầng cơ sở dữ liệu từ chối thao tác,
   **kể cả** khi lệnh phát ra từ chính ứng dụng.
3. **Xác thực lại thất bại:** ở bước 2, thao tác dừng và không có gì được ghi.

---

### 2.7 Nghiệp vụ 7 — Vận hành hệ thống và nguồn sự thật

**Phân tích nghiệp vụ.** Nghiệp vụ này trả lời một câu mà hầu hết hệ thống không
hỏi: *hệ thống có đang chạy đúng thứ ta nghĩ không?* Ba use case của nghiệp vụ
này tồn tại vì ba sự cố có thật:

* **Kiểm chứng độ tươi của triển khai (UC706)** — một ảnh giao diện từng chạy sau
  mã nguồn **năm tiếng** trong khi toàn bộ container báo khoẻ mạnh. Trang web tải
  hoàn hảo và phục vụ gói mã cũ. Câu lệnh liệt kê container trả lời "tiến trình
  còn sống", không trả lời "đó có phải tiến trình bạn vừa dựng".
* **Xác minh toàn vẹn nguồn sự thật (UC702)** — danh mục và lược đồ được công bố
  dưới dạng tạo tác ký số; máy chủ trước khi chạy phải xác minh chữ ký với khoá
  công khai đã ghi sẵn trong mã. Không xác minh được thì **chặn cả hệ thống khởi
  động**, có chủ ý.
* **Sao lưu và khôi phục (UC705)** — nguyên tắc nghiệp vụ: *một bản sao lưu chưa
  được diễn tập khôi phục là một bản sao lưu chưa tồn tại*. Công cụ liệt kê nội
  dung tệp sao lưu **không** phát hiện được tệp bị cụt.

*Bảng 1-12: Danh sách use case Nghiệp vụ 7*

| Mã | Chức năng | Tác nhân chính | Mức ưu tiên |
|---|---|---|---|
| UC701 | Quản lý máy ghi nguồn sự thật | Kỹ sư vận hành | Important |
| UC702 | Xác minh toàn vẹn nguồn sự thật | Kỹ sư vận hành | Important |
| UC703 | Đồng bộ kho lưu trữ và cơ sở dữ liệu | Kỹ sư vận hành | Important |
| UC704 | Giám sát sức khoẻ hệ thống | Kỹ sư vận hành | Important |
| UC705 | Sao lưu và khôi phục dữ liệu | Kỹ sư vận hành | Essential |
| UC706 | Kiểm chứng độ tươi của triển khai | Kỹ sư vận hành | Important |

*Bảng 1-20: Mô tả chức năng Xác minh toàn vẹn nguồn sự thật*

| **Use Case** | Xác minh toàn vẹn nguồn sự thật | **ID** | UC702 |
|---|---|---|---|
| **Tác nhân chính** | Kỹ sư vận hành | **Mức ưu tiên** | Important |
| **Kích hoạt bởi** | Kỹ sư vận hành, hoặc tiến trình khởi động | **Loại** | external / internal |

**Mô tả ngắn:** *Trước khi bất kỳ dịch vụ nào chạy, hệ thống kéo bản công bố mới
nhất của danh mục, kiểm mã băm từng tệp theo bản kê, kiểm chữ ký phủ bản kê, và
kiểm người ký có nằm trong danh sách khoá được tin cậy hay không.*

**Quan hệ:**
- **Association:** Kỹ sư vận hành – Xác minh toàn vẹn; Máy ghi nguồn sự thật (S5)
- **Include:** không
- **Extend:** không *(UC703 include use case này)*
- **Generalization:** không

**Luồng chính:**
1. Tiến trình khởi tạo kéo bản công bố mới nhất từ kho lưu trữ ngoài.
2. Hệ thống tính lại mã băm SHA-256 của từng tệp và đối chiếu với bản kê.
3. Hệ thống kiểm chữ ký Ed25519 phủ bản kê.
4. Hệ thống tra khoá công khai đã ký trong danh sách khoá được tin cậy; kết quả
   xác minh trả về **tên khoá đã đăng ký**, không phải một giá trị đúng/sai.
5. Hệ thống hợp nhất bản công bố vào cơ sở dữ liệu theo nguyên tắc **chỉ điền,
   không xoá**: thêm phần thiếu, không bao giờ gỡ phần đang có.
6. Các dịch vụ còn lại được phép khởi động.

**Luồng ngoại lệ:**
1. **Mã băm không khớp:** dừng ở bước 2 với mã thoát chuyên biệt; **cả hệ thống
   không khởi động**.
2. **Chữ ký hỏng hoặc thiếu:** dừng ở bước 3, cùng hành vi.
3. **Chữ ký hợp lệ nhưng người ký không được tin cậy:** dừng ở bước 4. Đây là ca
   quan trọng nhất — một kẻ tấn công dựng được dữ liệu khác, tính mã băm đúng,
   viết bản kê đúng, rồi tự ký bằng khoá của hắn. Chữ ký ấy **hợp lệ về mật mã**.
   Nếu hệ thống chỉ hỏi "chữ ký có hợp lệ không" mà không hỏi "hợp lệ theo khoá
   nào" thì toàn vẹn đúng nhưng thẩm quyền sai.
4. **Bản công bố lùi phiên bản:** hệ thống **chấp nhận** — đây là một **giới hạn
   đã biết**, ghi rõ ở Chương 4. Tài nguyên mới hơn không bị xoá, nhưng giá trị
   dùng chung bị ghi đè lùi.

---

### 2.8 Nghiệp vụ 8 — Hỗ trợ và tích hợp

**Phân tích nghiệp vụ.** Vành ngoài của hệ thống: kênh để người dùng báo hỏng, và
đường để hệ thống khác nối vào. Một phân biệt nghiệp vụ đáng ghi: thư báo **phiếu
mới** là một *sự kiện* (gửi ngay khi phiếu được tạo), còn thư báo **tồn đọng** là
một *trạng thái* (gửi khi hàng đợi vượt ngưỡng thời gian hoặc số lượng). Lẫn hai
loại này thì hoặc là gửi thư trùng lặp, hoặc là không bao giờ gửi.

*Bảng 1-13: Danh sách use case Nghiệp vụ 8*

| Mã | Chức năng | Tác nhân chính | Mức ưu tiên |
|---|---|---|---|
| UC801 | Tạo phiếu hỗ trợ | Người dùng đã đăng nhập | Important |
| UC802 | Trả lời phiếu hỗ trợ | Người dùng đã đăng nhập | Important |
| UC803 | Trực hàng đợi hỗ trợ | Nhân viên hỗ trợ | Important |
| UC804 | Xem thông báo | Người dùng đã đăng nhập | Important |
| UC805 | Quản lý khoá API | Quản trị tổ chức | Optional |
| UC806 | Quản lý điểm nhận webhook | Quản trị tổ chức | Optional |

*Bảng 1-21: Mô tả chức năng Quản lý khoá API*

| **Use Case** | Quản lý khoá API | **ID** | UC805 |
|---|---|---|---|
| **Tác nhân chính** | Quản trị tổ chức | **Mức ưu tiên** | Optional |
| **Kích hoạt bởi** | Quản trị tổ chức | **Loại** | external |

**Mô tả ngắn:** *Quản trị tổ chức tạo, thu hồi và xem lịch sử sử dụng khoá API để
hệ thống bên thứ ba gọi vào trong phạm vi tổ chức mình.*

**Quan hệ:**
- **Association:** Quản trị tổ chức – Quản lý khoá API; Ứng dụng bên thứ ba (S6)
- **Include:** không · **Extend:** không · **Generalization:** không

**Luồng chính:**
1. Quản trị tổ chức mở trang Tích hợp và bấm "Tạo khoá".
2. Nhập tên gợi nhớ và chọn phạm vi quyền của khoá.
3. Hệ thống sinh khoá, lưu **mã băm** của khoá chứ không lưu khoá, và hiển thị
   giá trị khoá **đúng một lần**.
4. Ứng dụng bên thứ ba gọi API kèm khoá; hệ thống phân giải khoá về đúng tổ chức
   và áp cùng cơ chế cách ly như với một phiên người dùng.
5. Quản trị viên xem thời điểm dùng gần nhất của từng khoá.
6. Khi cần, quản trị viên thu hồi khoá; hiệu lực tức thì.

**Luồng ngoại lệ:**
1. **Mất khoá:** không khôi phục được, chỉ tạo khoá mới — hệ quả trực tiếp của
   việc chỉ lưu mã băm.
2. **Khoá bị dùng ngoài phạm vi:** hệ thống từ chối và ghi nhật ký kiểm toán.
3. **Vượt hạn mức số khoá:** từ chối kèm hạn mức gói.

> ### ▣ HÌNH 1-7 — Use case Nghiệp vụ 5–8: Quản trị, vận hành và tích hợp
> **Phải thể hiện:** gộp bốn nghiệp vụ quản trị trong một hình, chia bốn vùng có
> nhãn; A7, A8, A9, A10 và S1, S5, S6; ba «include» tới UC601 (từ UC508, UC607,
> UC609) vẽ nổi bật vì chúng thể hiện quy tắc "thao tác không hoàn tác được thì
> phải xác thực lại".
> **Chú thích:** *Hình 1-7: Sơ đồ use case các nghiệp vụ quản trị, vận hành và
> tích hợp.*

---

## 3. Các yêu cầu phi chức năng

Mỗi yêu cầu dưới đây có một mã, một phát biểu **kiểm chứng được**, và một cách
kiểm. Yêu cầu không nêu được cách kiểm là yêu cầu không dùng được — nó không phân
biệt nổi hệ thống đạt với hệ thống không đạt.

### 3.1 Yêu cầu thực thi

*Bảng 1-22: Yêu cầu thực thi*

| Mã | Yêu cầu | Cách kiểm |
|---|---|---|
| NFR-P1 | Độ trễ của các điểm cuối đọc thường dùng phải ở mức **dưới 100 ms tại phân vị 95** trong điều kiện không tranh chấp | Đo độ trễ cơ sở, 1.000 lượt/điểm cuối, ba lượt chạy độc lập, lấy trung vị của ba giá trị phân vị (Ch4 §5.3) |
| NFR-P2 | Trích điểm mốc tại trình duyệt phải đạt tối thiểu **15 khung/giây** trên máy tính xách tay phổ thông, để cửa sổ thu 60 khung hoàn tất trong khoảng 4 giây | Đo trên máy tham chiếu nêu ở Phụ lục B |
| NFR-P3 | Thao tác thu mẫu **không được chặn** giao diện: mọi bước xử lý nặng chạy trên tiến trình nền | Kiểm chức năng: sau khi bấm Lưu, giao diện trả về trong dưới 1 giây kèm mã tác vụ |
| NFR-P4 | Một mẫu sau chuẩn hoá chiếm **không quá 100 KiB** ở phân vị 95 | Thống kê trên toàn bộ tệp đặc trưng (Ch4 §5.4) |
| NFR-P5 | Biểu diễn điểm mốc phải giảm **trên 90 %** dung lượng so với video nguồn | Đo ghép cặp khớp thời lượng, báo cáo kèm cỡ mẫu và khoảng phân bố (Ch4 §5.4) |

Ghi chú giới hạn: NFR-P1 nói về **độ trễ cơ sở**, không nói về thông lượng và
không chứng minh cách ly hiệu năng giữa các tổ chức.

### 3.2 Yêu cầu an toàn thông tin

*Bảng 1-23: Yêu cầu an toàn thông tin*

| Mã | Yêu cầu | Cách kiểm |
|---|---|---|
| NFR-S1 | **Cách ly dữ liệu giữa các tổ chức phải được cưỡng chế ở tầng cơ sở dữ liệu.** Một truy vấn không khai báo tổ chức trả về 0 hàng | Đo đối kháng qua API: nhóm đúng quyền – sai tổ chức phải bị chặn 100 %, kèm đối chứng dương chứng minh chủ sở hữu làm được (Ch4 §5.2) |
| NFR-S2 | Ứng dụng **không được tự vô hiệu hoá** cơ chế cách ly | Vai chạy của ứng dụng không có quyền DDL và không có quyền vượt chính sách; kiểm bằng truy vấn siêu dữ liệu và bằng thử nghiệm phát lệnh vô hiệu hoá |
| NFR-S3 | Ngữ cảnh tổ chức phải **giới hạn trong phạm vi giao dịch**, không rò sang yêu cầu kế tiếp trên cùng kết nối | Kiểm thử tuần tự hai yêu cầu của hai tổ chức trên cùng kết nối |
| NFR-S4 | Công việc nền xuyên tổ chức phải đi qua **một phạm vi riêng biệt**, không mượn định danh của một tổ chức nào | Kiểm rằng phạm vi hệ thống là một biến ngữ cảnh riêng, không phải một giá trị đặc biệt của biến tổ chức |
| NFR-S5 | Mọi thao tác nhạy cảm phải để lại **nhật ký kiểm toán bền vững**, và việc ghi nhật ký phải **từ chối khi thiếu ngữ cảnh** | Kiểm sự tồn tại bản ghi sau mỗi thao tác nhạy cảm; kiểm hành vi từ chối khi không có phạm vi |
| NFR-S6 | Tạo tác danh mục phải **có bằng chứng giả mạo**: sửa được nhưng không giấu được | Ma trận chín kịch bản giả mạo (Ch4 §5.5) |
| NFR-S7 | Không xác minh được nguồn sự thật thì hệ thống **dừng**, không suy đoán | Kiểm mã thoát của tiến trình khởi tạo và trạng thái các dịch vụ phụ thuộc |

### 3.3 Yêu cầu bảo mật

*Bảng 1-24: Yêu cầu bảo mật*

| Mã | Yêu cầu | Cách kiểm |
|---|---|---|
| NFR-C1 | Cổng truy cập **mặc định từ chối**: một điểm cuối mới không khai báo công khai thì tự động yêu cầu xác thực | Kiểm ở tầng trung gian, không ở từng điểm cuối; kiểm thử liệt kê toàn bộ điểm cuối và đối chiếu danh sách ngoại lệ |
| NFR-C2 | Mật khẩu lưu dạng **băm có muối**; không có đường đọc ngược | Rà soát lược đồ và rà soát mô hình trả về của API |
| NFR-C3 | Phiên đăng nhập có **ba mức thu hồi**: một phiên, mọi phiên của một tài khoản, và thu hồi theo biện pháp quản trị | Kiểm thử từng mức |
| NFR-C4 | Hỗ trợ **xác thực hai yếu tố** theo chuẩn TOTP, kèm mã khôi phục dùng một lần | Kiểm bằng vector thử của tiêu chuẩn, không chỉ kiểm "đăng nhập được" |
| NFR-C5 | Thao tác **không hoàn tác được** đòi xác thực lại trong phiên | Kiểm thử cho ba use case: dọn sạch dữ liệu tổ chức, công bố văn bản pháp lý, đổi gói cước |
| NFR-C6 | Giới hạn tần suất tính theo **địa chỉ IP thật**, không cho phía gọi tự khai | Kiểm rằng tiêu đề do phía gọi đặt không ảnh hưởng tới bộ đếm |
| NFR-C7 | Biểu mẫu đăng nhập **không được dùng để dò tên tài khoản**: sai tên và sai mật khẩu trả cùng một thông báo và cùng độ trễ | Kiểm thử so sánh hai nhánh |
| NFR-C8 | Liên kết đặt lại mật khẩu chỉ trỏ tới **danh sách máy chủ được phép** | Kiểm thử với tiêu đề máy chủ giả mạo |

### 3.4 Yêu cầu về tính tin cậy

*Bảng 1-25: Yêu cầu về tính tin cậy*

| Mã | Yêu cầu | Cách kiểm |
|---|---|---|
| NFR-R1 | Mất kết nối trong lúc thu **không được làm mất bản thu**: dữ liệu đã thu giữ lại ở trình duyệt và thử lại được | Kiểm thử ngắt mạng ở bước gửi |
| NFR-R2 | Bản gốc tải lên phải được **lưu trước** mọi bước chuẩn hoá | Kiểm thứ tự ghi trong luồng xử lý |
| NFR-R3 | Xoá là **xoá mềm**, khôi phục được cho tới khi dọn hẳn | Kiểm thử khôi phục từ thùng rác ở cả ba mức xoá |
| NFR-R4 | Sao lưu cơ sở dữ liệu chạy **theo lịch**, và phải **diễn tập khôi phục được** | Chạy chế độ diễn tập; kiểm tính toàn vẹn bằng phương pháp phát hiện được tệp cụt |
| NFR-R5 | Nguồn sự thật và bản sao truy vấn phải có **cơ chế đối soát định kỳ** | Kiểm sự tồn tại và kết quả của tác vụ đối soát |
| NFR-R6 | Hệ thống phải phát hiện được **mã đang chạy không khớp mã nguồn** | Công cụ kiểm độ tươi triển khai, bắt được ba kiểu lệch |
| NFR-R7 | Tác vụ nền thất bại phải **thông báo tới chủ sở hữu tác vụ**, không chỉ ghi log | Kiểm thử tác vụ huấn luyện hỏng |

Giới hạn phải nêu: cơ chế **thử lại** và **tính lũy đẳng** hiện **chưa đồng đều**
giữa các đường xử lý nền. Việc tạo tài nguyên và tải đối tượng lên kho ngoài chưa
bảo đảm chạy lại nhiều lần cho cùng kết quả. Đây là hạn chế đã biết, không phải
điều chưa rà soát.

### 3.5 Yêu cầu về tính duy trì được

*Bảng 1-26: Yêu cầu về tính duy trì được*

| Mã | Yêu cầu | Cách kiểm |
|---|---|---|
| NFR-M1 | Toàn bộ hệ thống **dựng lại được từ mã nguồn** bằng một lệnh trên máy sạch | Diễn tập triển khai trên máy thứ hai (đã thực hiện) |
| NFR-M2 | Cấu hình tách khỏi mã theo nguyên tắc Twelve-Factor; đổi cấu hình **không cần dựng lại ảnh** | Rà soát; kiểm thử đổi biến môi trường |
| NFR-M3 | Thay đổi cấu trúc dữ liệu chia **hai loại**: bước tự động lúc khởi động chỉ được **thêm**, mọi thay đổi một chiều phải qua lệnh di trú tường minh | Rà soát chính sách DDL lúc khởi động; kiểm thử nợ lược đồ bằng ba lần khởi động liên tiếp |
| NFR-M4 | Backend **từ chối khởi động** khi phiên bản lược đồ lệch, theo **cả hai chiều** | Kiểm thử với lược đồ cũ hơn và mới hơn |
| NFR-M5 | Lệnh di trú phải có **chốt chặn đích đến**: chạy nhầm lên cơ sở dữ liệu sản xuất bị chặn | Kiểm thử với biến đích không khớp |
| NFR-M6 | Bộ kiểm thử chạy trong môi trường **giống môi trường thật**, trên mạng của các dịch vụ | Hạ tầng kiểm thử đóng gói riêng (Ch4 §3.2) |
| NFR-M7 | Giao diện hỗ trợ **đa ngôn ngữ**, không có chuỗi cứng trong mã | Công cụ đo độ phủ i18n chạy trong cổng trước triển khai |
| NFR-M8 | Hệ thống phát ra **chỉ số và nhật ký có cấu trúc**, đủ để dựng cảnh báo | Kiểm sự tồn tại của chỉ số và của cảnh báo tương ứng |

---

## 4. Các ràng buộc về thực thi và thiết kế

### 4.1 Ràng buộc về thực thi

*Bảng 1-27: Ràng buộc thực thi*

| Mã | Ràng buộc | Hệ quả lên thiết kế |
|---|---|---|
| RB-T1 | **Một máy chủ vật lý duy nhất**: 6 nhân, 12 GB RAM, một GPU | Không dựng được cụm; mọi dịch vụ chạy container trên cùng máy, phải đặt hạn mức bộ nhớ cho từng container để một dịch vụ rò bộ nhớ không giết cả máy |
| RB-T2 | **Không có ngân sách hạ tầng đám mây** | Kho đối tượng chuyên dụng bị loại; dùng hệ tệp cục bộ cộng kho lưu trữ ngoài miễn phí. Đây là nguồn gốc của bài toán hai mặt phẳng lưu trữ ở Chương 3 |
| RB-T3 | Triển khai đặt sau đường dẫn cơ sở `/voya` trên máy chủ của đơn vị | Mọi liên kết tuyệt đối, mọi đường chuyển hướng và mọi tài nguyên tĩnh phải tôn trọng đường dẫn cơ sở |
| RB-T4 | Kho lưu trữ ngoài có **hạn mức lượt gọi** và có thể tạm ngừng phục vụ | Đồng bộ phải bất đồng bộ và có thử lại; hỏng đồng bộ không được làm hỏng đường thu |
| RB-T5 | Người dùng thu dữ liệu bằng **máy tính cá nhân phổ thông**, đường truyền không ổn định | Trích đặc trưng tại máy khách; giữ dữ liệu ở trình duyệt khi mất mạng |
| RB-T6 | Thời gian thực hiện đề tài giới hạn trong một học kỳ, một người thực hiện | Ưu tiên hoàn thiện trục cách ly và trục dữ liệu; các tầng phân quyền sâu hơn giữ ở mức thiết kế tham chiếu |

### 4.2 Ràng buộc về thiết kế

*Bảng 1-28: Ràng buộc thiết kế*

| Mã | Ràng buộc | Lý do |
|---|---|---|
| RB-D1 | **Kế thừa một hệ thống đang chạy**, không viết mới từ đầu | Hệ thống tiền thân đã có dữ liệu thật và người dùng thật. Chuyển đổi phải theo lối bóp nghẹt dần: mở rộng song song rồi chuyển tải, không thay thế một lần |
| RB-D2 | Nguồn sự thật của kho mẫu hiện là **tệp CSV**, cơ sở dữ liệu quan hệ là bản sao truy vấn | Di sản kiến trúc từ hệ thống tiền thân. Không sửa được trong phạm vi đề tài mà không phá dữ liệu đang có; phải thiết kế cơ chế đối soát thay vì giấu |
| RB-D3 | Cách ly phải cưỡng chế **ở tầng cơ sở dữ liệu**, không ở tầng ứng dụng | Ràng buộc tự đặt, và là đóng góp lõi. Lý do ở §1.2, vấn đề 1 |
| RB-D4 | Vai chạy của ứng dụng **không được có quyền DDL** | Lệnh vô hiệu hoá chính sách bảo mật mức hàng là một lệnh DDL. Một vai vừa ghi được dữ liệu vừa chạy được DDL thì tự gỡ được vòng vây của chính nó |
| RB-D5 | Không lưu video thô ở đường thu qua webcam | Vừa là yêu cầu về quyền riêng tư, vừa là nguồn của hiệu quả lưu trữ. Hệ quả: **không đo ngược lại được** tỉ lệ giảm dung lượng trên chính dữ liệu của hệ thống — phải đo trên nguồn video bên ngoài |
| RB-D6 | Biểu diễn dữ liệu cố định ở **126 chiều mỗi khung** (21 điểm mốc × 3 toạ độ × 2 bàn tay) | Quyết định về phạm vi: chỉ dùng thông tin bàn tay. Tư thế toàn thân và biểu cảm khuôn mặt nằm ngoài phạm vi |
| RB-D7 | Danh mục **không có đường rơi ngược** về mặt phẳng cộng đồng lúc chạy | Rơi ngược làm dữ liệu của hai mặt phẳng lẫn vào nhau mà không ai biết. Thiếu thì dừng |
| RB-D8 | Văn bản pháp lý đã công bố là **bất biến ở tầng cơ sở dữ liệu** | Chấp thuận trỏ tới một cặp (loại, phiên bản); đổi nội dung dưới chân nó biến bằng chứng thành lời khẳng định suông |
| RB-D9 | Mọi phép đo trong luận văn phải **có khả năng thất bại** và có **đối chứng dương** | Ràng buộc phương pháp. Một phép đo không thể thất bại thì không đo gì cả — xem Chương 4 §2.2 |

### 4.3 Ba giới hạn phạm vi được tuyên bố trước

Ba điểm dưới đây **không** phải khiếm khuyết phát hiện muộn; chúng được tuyên bố
ngay ở chương mô tả bài toán để các chương sau không phải biện minh:

1. **Phân quyền nhiều cấp mới cưỡng chế ở hai cấp.** Mô hình dữ liệu và kiến trúc
   phân quyền hỗ trợ một hệ phân cấp mở rộng được, nhưng cưỡng chế lúc chạy hiện
   chỉ chứng minh được ở cấp **hệ thống** và cấp **tổ chức**. Hai cấp bên dưới có
   cấu trúc dữ liệu nhưng chưa có bề mặt vận hành.
2. **Cách ly phủ nửa đầu vòng đời dữ liệu.** Ranh giới tổ chức được cưỡng chế
   chặt trên đường thu nhận và quản lý mẫu. Nửa sau — huấn luyện và mô hình — mới
   ở mức kiến trúc đích, chưa cưỡng chế theo ranh giới tổ chức ở mọi đường.
3. **Thu hồi không viết lại quá khứ.** Rút đồng thuận loại dữ liệu khỏi mọi bản
   phát hành **sau đó**; nó không xoá dữ liệu khỏi lưu trữ và không thu hồi được
   giấy phép đã cấp cho bên thứ ba. Giao diện nói thẳng điều này, và có kiểm thử
   ghim đúng câu chữ đó.
