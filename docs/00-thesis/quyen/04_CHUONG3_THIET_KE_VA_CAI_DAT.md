# CHƯƠNG 3: THIẾT KẾ VÀ CÀI ĐẶT GIẢI PHÁP

*Chương 1 nói hệ thống **phải làm gì**. Chương 2 nói những nguyên lý nào **có sẵn**
để làm việc đó. Chương này nói hệ thống **làm bằng cách nào**, và quan trọng hơn —
**vì sao làm theo cách đó chứ không theo cách khác**.*

*Mỗi quyết định lớn trong chương đi kèm ba thứ: các phương án đã cân nhắc, tiêu
chí lựa chọn, và **cái giá phải trả**. Một thiết kế trình bày mà không nêu cái giá
phải trả là một thiết kế chưa được cân nhắc, hoặc một thiết kế đang giấu điều gì
đó. Chương này cũng nêu thẳng ba giới hạn thiết kế ngay tại chỗ chúng phát sinh,
không dồn hết sang phần Kết luận.*

**Mốc đo của toàn chương:** mọi con số về mã nguồn, lược đồ và cấu hình trong
chương này được đếm lại trên nhánh `deploy_ctu_ver-2.2.1` và trên cơ sở dữ liệu
`signdb` đang chạy, ngày **18/08/2026**. Cách đếm được nêu kèm từng con số, để
người phản biện kiểm chứng lại được bằng đúng câu lệnh đó.

---

## 3.1. Phân tích bài toán và yêu cầu hệ thống

### 3.1.1. Mô tả chi tiết bài toán

#### a. Phát biểu bài toán từ góc nhìn thiết kế

Chương 1 mô tả bài toán từ góc nhìn nghiệp vụ: nhiều tổ chức cùng cần thu thập dữ
liệu Ngôn ngữ Ký hiệu Việt Nam (VSL), nhưng không tổ chức nào đủ nguồn lực để tự
dựng và tự vận hành một hệ thống riêng, trong khi dữ liệu của họ lại không thể trộn
chung. Cùng bài toán đó, phát biểu lại từ góc nhìn thiết kế, trở thành một câu hỏi
kỹ thuật cụ thể hơn nhiều:

> Làm thế nào để **một bản triển khai duy nhất**, chạy trên **một máy chủ duy
> nhất**, phục vụ **nhiều tổ chức độc lập**, mà ranh giới dữ liệu giữa họ được bảo
> đảm bằng một **cơ chế cưỡng chế được**, chứ không bằng kỷ luật lập trình?

Chữ "cưỡng chế được" là chỗ bài toán trở nên khó. Một hệ thống lọc dữ liệu theo tổ
chức bằng điều kiện `WHERE tenant_id = ?` trong mã ứng dụng **không sai** — nó chạy
đúng cho tới khi một lập trình viên viết một truy vấn mới và quên mất điều kiện đó.
Và khi quên, hệ thống **không báo lỗi**: nó trả về nhiều dữ liệu hơn cần thiết, một
cách im lặng, và không có phép kiểm nào tự động bắt được. Đó là dạng lỗi nguy hiểm
nhất trong một hệ thống nhiều tổ chức: **hỏng nhưng không kêu**.

Vì vậy toàn bộ Chương 3 xoay quanh một nguyên tắc thiết kế duy nhất, và mọi mục còn
lại là hệ quả của nó:

> **Ranh giới cách ly phải nằm ở tầng thấp hơn tầng mà lập trình viên có thể quên.**

#### b. Ba vấn đề nghiệp vụ và ba câu hỏi thiết kế tương ứng

Ba vấn đề nghiệp vụ nêu ở Chương 1 §1.2 được dịch sang ba câu hỏi thiết kế. Mỗi câu
hỏi được trả lời ở một mục cụ thể trong chương này; cột cuối là địa chỉ trả lời.

*Bảng 3-1: Từ vấn đề nghiệp vụ tới câu hỏi thiết kế*

| # | Vấn đề nghiệp vụ (Ch.1 §1.2) | Câu hỏi thiết kế | Trả lời ở |
|---|---|---|---|
| 1 | Nhiều tổ chức dùng chung hạ tầng nhưng dữ liệu không được trộn | Đặt cơ chế cách ly ở tầng nào, và bịt những lối vòng nào? | §3.3.3.1, §3.6.2 a |
| 2 | Dữ liệu VSL là dữ liệu sinh trắc học của người thật; đồng thuận phải rút lại được | Làm sao để "rút đồng thuận" là một sự kiện **có hiệu lực kỹ thuật**, không phải một cột siêu dữ liệu thụ động? | §3.5.5, §3.6.2 d |
| 3 | Danh mục từ vựng là tạo tác nghiên cứu, phải trích dẫn lại được sau nhiều tháng | Làm sao để một phiên bản danh mục **không đổi được dưới chân** một thí nghiệm đã công bố? | §3.3.3.4, §3.5.4 |

#### c. Bốn đặc điểm làm bài toán này khác một ứng dụng thu dữ liệu thông thường

Bốn đặc điểm dưới đây quyết định gần như mọi lựa chọn kỹ thuật trong chương. Nếu bỏ
bất kỳ đặc điểm nào, thiết kế đơn giản đi đáng kể — và đó chính là lý do phải nêu
chúng ra trước, thay vì để chúng xuất hiện như những phức tạp không giải thích được.

1. **Dữ liệu rời trình duyệt ở dạng đã trích đặc trưng.** Điểm mốc bàn tay được
   trích ngay tại máy người dùng bằng WebAssembly. Với đường thu qua webcam, video
   thô **không bắt buộc rời khỏi máy đó**. Hệ quả dây chuyền: băng thông thấp, kho
   lưu trữ nhỏ, và không có video thô để rò rỉ — nhưng cũng **không trích lại được
   loại đặc trưng khác về sau**.
2. **Ranh giới tổ chức do cơ sở dữ liệu cưỡng chế**, không do lập trình viên nhớ
   viết điều kiện lọc. Đây là ràng buộc tự đặt (RB-D3) và là đóng góp lõi của
   luận văn.
3. **Danh mục từ vựng là tạo tác có phiên bản và có chữ ký số**, không phải một
   bảng tra cứu sửa tự do. Một máy không xác minh được chữ ký thì **không được
   phép phục vụ**.
4. **Chủ thể dữ liệu tách khỏi tài khoản vận hành.** Người có bàn tay trong mẫu
   (*người ký*) và tài khoản bấm nút thu (*người vận hành*) là hai vế khác nhau, và
   đồng thuận gắn vào vế thứ nhất. Đây là điều một công cụ thu dữ liệu thông thường
   không cần phân biệt.

#### d. Khoanh phạm vi của đối tượng thiết kế

Phải khoanh phạm vi ngay tại đây, vì phần còn lại của chương liên tục nhắc tới các
thành phần hạ nguồn. Đối tượng thiết kế và đánh giá của luận văn là **phân hệ thu
thập và quản lý dữ liệu** trong nền tảng CTU.SignBridge, không phải toàn bộ nền
tảng. Các thành phần huấn luyện và nhận dạng **được thiết kế và cài đặt đầy đủ**
trong hệ thống, nhưng trong luận văn chúng đóng vai **bên tiêu thụ dữ liệu ở hạ
nguồn** — chúng có mặt để chứng minh vòng đời dữ liệu khép kín, không phải để được
đánh giá về chất lượng nhận dạng.

Ba loại trừ tường minh, nhắc lại từ Chương 1 §1.3 vì chúng chi phối cách đọc chương
này:

* **Không đánh giá độ chính xác mô hình.** Đối tượng của đề tài là hạ tầng.
* **Không chứng minh cách ly hiệu năng.** Hệ thống có hạn mức và giới hạn tần suất,
  nhưng hai thứ đó không chứng minh được một tổ chức không làm chậm tổ chức khác.
* **Không hiện thực sổ cái phân tán.** Cơ chế toàn vẹn ở đây là chữ ký số trên tạo
  tác, không phải blockchain.

---

### 3.1.2. Các tác nhân của hệ thống

Hệ thống có **10 tác nhân người** và **6 tác nhân hệ thống**. Tác nhân hệ thống được
mô hình hoá tường minh chứ không ẩn đi, vì bốn trong sáu tác nhân đó **nằm ngoài
ranh giới hệ thống** và có thể ngừng phục vụ bất kỳ lúc nào — thiết kế phải chịu
được điều đó.

#### a. Bốn nhóm tác nhân người

*Bảng 3-2: Bốn nhóm tác nhân người*

| Nhóm | Gồm | Đặc điểm chung |
|---|---|---|
| Chưa có danh tính | A1 Khách vãng lai | Không đăng nhập; chỉ chạm được phần công khai |
| Người dùng cuối | A2 Người dùng đã đăng nhập «abstract», A3 Người khiếm thính – khiếm ngôn, A4 Người dùng bình thường | Dùng hệ thống để **giao tiếp** và giữ tài khoản của mình |
| Bên tổ chức / bên thứ ba | A5 Thành viên tổ chức, A6 Biên tập viên / Nghiên cứu sinh, A7 Quản trị tổ chức | Thuộc một tổ chức; **đóng góp và khai thác dữ liệu** trong ranh giới tổ chức đó |
| Bên vận hành nền tảng | A8 Quản trị nền tảng, A9 Nhân viên hỗ trợ, A10 Kỹ sư vận hành | Giữ cả nền tảng chạy đúng, cho **mọi** tổ chức |

#### b. Chi tiết mười tác nhân người và cơ chế phân biệt

Cột cuối của Bảng 3-3 trả lời một câu hỏi mà nhiều đặc tả bỏ qua: **hệ thống có tự
phân biệt được vai này không?** Việc trả lời thẳng câu này là một quyết định trình
bày có chủ ý — một mô hình tác nhân đẹp trên giấy nhưng không ánh xạ được xuống một
điều kiện kiểm tra trong mã là một mô hình chưa cài đặt.

Ký hiệu: ✅ kiểm được bằng một điều kiện cụ thể trong mã hoặc CSDL · 🟡 kiểm được lớp
quyền bao ngoài nhưng không kiểm được chính vai đó · ⚠️ không có cột, cờ hay điều
kiện nào phân biệt.

*Bảng 3-3: Mười tác nhân người*

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

Bốn tác nhân mang dấu ⚠️ hoặc 🟡 vẫn được giữ trong mô hình, và lý do là nghiệp vụ
chứ không phải sơ suất:

* **A3 và A4 khác nhau ở người, không khác nhau ở quyền.** Tài khoản của người
  khiếm thính và tài khoản của người nghe được có đúng cùng bộ quyền kỹ thuật. Cái
  tách họ ra là **mục tiêu** khi dùng hệ thống — và mục tiêu khác nhau vẫn sinh ra
  use case khác nhau. Bỏ A3 đi thì không còn ai để giải thích vì sao đồng thuận lại
  chi phối việc phát hành dữ liệu.
* **A9 và A10 làm hai công việc khác hẳn nhau trên cùng một quyền nền tảng.** Tách
  sẵn ở tầng mô hình để khi hệ thống thêm vai riêng thì đặc tả không phải viết lại.
  Sáu use case của A10 hơn nữa **chạy ngoài ứng dụng** — trên dòng lệnh của máy
  triển khai — nên ranh giới thật của họ là quyền hệ điều hành, không phải quyền
  trong ứng dụng.

**Một ranh giới không được vẽ sai: A7 ≠ A8.** Quản trị nền tảng không kế thừa Quản
trị tổ chức và ngược lại. A7 kiểm bằng vai trong một tổ chức, phạm vi đúng **một**
tổ chức, đưa người vào bằng **lời mời**. A8 kiểm bằng cờ trên tài khoản, phạm vi
toàn nền tảng, đưa người vào bằng **gán trực tiếp theo mã tài khoản**.

Lý do rất cụ thể, và nó là một quyết định thiết kế chứ không phải một quy ước vẽ
hình: mã tài khoản **không phải bí mật**. Nếu quản trị viên tổ chức gán trực tiếp
được theo mã tài khoản, họ kéo được bất kỳ ai trên hệ thống vào tổ chức của mình mà
người kia không hay biết — và từ đó dữ liệu của người kia rơi vào phạm vi quản trị
của họ. Đường đưa người vào của A7 vì thế **bắt buộc** là lời mời: một cơ chế đòi
hỏi chính người được mời hành động.

#### c. Sáu tác nhân hệ thống

*Bảng 3-4: Sáu tác nhân hệ thống*

| Mã | Tác nhân | Hiện thực bằng | Vai trò | Nằm trong ranh giới hệ thống? |
|---|---|---|---|---|
| S1 | Dịch vụ gửi tin | SMTP + cổng SMS | Gửi mã xác thực, lời mời, nhắc hạn, thư phiếu hỗ trợ, cảnh báo | **Không** |
| S2 | Kho lưu trữ ngoài | Google Drive + Google Sheets | Giữ tệp đặc trưng, video thô, bản xem trước; phản chiếu nguồn sự thật để đối soát | **Không** |
| S3 | Dịch vụ suy luận | Suy luận trên GPU + tổng hợp giọng nói | Phục vụ mô hình đang hoạt động, nạp nóng khi thăng hạng, đọc thành tiếng | Có (`realtime_service`) |
| S4 | Tiến trình nền | Hàng đợi tác vụ Celery + bộ lập lịch | Trích đặc trưng, tăng cường, dựng bản xem trước, xoá tệp, đối soát, sao lưu theo lịch | Có (`worker`, `celery-beat`) |
| S5 | Máy ghi nguồn sự thật | Máy được cấp khoá ký Ed25519 | Ghi vào nguồn sự thật và công bố bản đã ký | **Không** — là một máy vật lý khác |
| S6 | Ứng dụng bên thứ ba | Hệ thống ngoài dùng khoá API | Gọi API trong phạm vi của khoá; nhận sự kiện webhook | **Không** |

Bốn tác nhân nằm ngoài ranh giới (S1, S2, S5, S6) sinh ra bốn ràng buộc thiết kế cụ
thể, và cả bốn đều xuất hiện lại trong chương:

| Tác nhân ngoài | Điều gì xảy ra khi nó hỏng | Thiết kế phải chịu được bằng |
|---|---|---|
| S1 hỏng | Không gửi được mã xác thực, lời mời | Cooldown **không bị tiêu**; báo lỗi gửi rõ ràng thay vì im lặng (§3.5.1) |
| S2 hỏng | Không đẩy được tệp lên kho ngoài | Đường thu **không hỏng theo**; giữ đường dẫn cục bộ, tác vụ đối soát điền sau (§3.5.3) |
| S5 không xác minh được | Danh mục không đáng tin | **Dừng cả hệ thống**, không suy đoán (§3.3.1) |
| S6 gọi sai phạm vi | Rò dữ liệu qua khoá API | Khoá mang phạm vi tổ chức; lưu **mã băm**, không lưu khoá (§3.5.6) |

> ### ▣ HÌNH 3-1 — Cây kế thừa tác nhân
> **Loại:** sơ đồ phân cấp UML · **Công cụ:** draw.io
> **Phải thể hiện:** ba chuỗi kế thừa `A2→A5→A6→A7`, `A2→{A3,A4}`, `A8→{A9,A10}`;
> A1 đứng ngoài mọi chuỗi; **A8 tách hẳn khỏi nhánh tổ chức** — đây là điểm phải
> nhìn thấy được từ hình, vì nó là ranh giới quyền quan trọng nhất trong mô hình.
> Sáu tác nhân hệ thống S1–S6 vẽ thành một cột riêng bên phải, **có đường kẻ phân
> biệt** cái nào nằm trong và cái nào nằm ngoài ranh giới hệ thống.
> **Chú thích:** *Hình 3-1: Cây kế thừa tác nhân và ranh giới giữa quản trị tổ chức
> với quản trị nền tảng.*

---

### 3.1.3. Các chức năng của hệ thống

#### a. Tám nhóm nghiệp vụ

Ranh giới giữa các nghiệp vụ **không phải màn hình**, mà là **thứ đang bị quản lý**:
danh tính, dữ liệu thô, danh mục, mô hình, tổ chức, chính sách, hạ tầng, và dịch vụ
vành ngoài. Cách chia theo đối tượng quản lý chứ không theo màn hình là một lựa
chọn có hệ quả: nó làm cho một màn hình có thể phục vụ hai nghiệp vụ, nhưng đổi lại
mỗi nghiệp vụ có một chủ sở hữu rõ ràng và một kiểu hỏng đặc trưng.

*Bảng 3-5: Tám nhóm nghiệp vụ*

| # | Nghiệp vụ | Câu hỏi nghiệp vụ đó trả lời | Dải mã UC | Số UC |
|---|---|---|---|:--:|
| NV1 | Danh tính và quyền truy cập | Anh là ai, và anh đã đồng ý những gì? | UC101–UC114 | 14 |
| NV2 | Thu thập và quản lý dữ liệu mẫu | Mẫu vào hệ thống bằng đường nào, và mất đi bằng đường nào? | UC201–UC213 | 13 |
| NV3 | Danh mục từ vựng và phương ngữ | Được phép thu **lớp** nào, theo phương ngữ nào? | UC301–UC310 | 10 |
| NV4 | Huấn luyện, đánh giá và suy luận | Dữ liệu thành mô hình bằng cách nào, rồi mô hình phục vụ ai? | UC401–UC409 | 9 |
| NV5 | Tổ chức và đăng ký dịch vụ | Ai thuộc về tổ chức nào, trong hạn mức nào? | UC501–UC508 | 8 |
| NV6 | Quản trị người dùng và chính sách | Ai đặt luật, và lấy gì làm bằng chứng? | UC601–UC609 | 9 |
| NV7 | Vận hành hệ thống và nguồn sự thật | Hệ thống có đang chạy đúng thứ ta nghĩ không? | UC701–UC706 | 6 |
| NV8 | Hỗ trợ và tích hợp | Hỏng thì kêu ai, và máy khác nối vào thế nào? | UC801–UC806 | 6 |
| | | | **Tổng** | **75** |

**Cách các nghiệp vụ nối nhau.** NV1 → NV3 → NV2 là vòng đời của một mẫu: phải có
danh tính và đồng thuận trước, mẫu chỉ có nghĩa khi thuộc về một lớp trong danh
mục, rồi mới thu được mẫu. NV4 là chỗ dữ liệu thành sản phẩm. NV5, NV6, NV7 là ba
tầng quản trị **không lồng nhau**: một tổ chức tự quản mình (NV5), nền tảng đặt luật
cho mọi tổ chức (NV6), còn hạ tầng bên dưới thì không biết tổ chức là gì (NV7). NV8
là vành ngoài.

**Vì sao NV6 và NV7 tách ra dù cùng do quyền quản trị nền tảng kiểm:** vì chúng
**hỏng theo hai kiểu khác nhau**. NV6 sai thì *chính sách* sai — một tài khoản có
quyền nó không đáng có, một văn bản pháp lý sai hiệu lực. NV7 sai thì *hệ thống mất
dữ liệu hoặc chạy sai mã* — bản sao lưu chưa từng chạy, mã cũ đang phục vụ, nguồn
sự thật lệch khỏi bản sao. Người chịu trách nhiệm và cách phát hiện cũng khác nhau.

#### b. Ánh xạ từ nghiệp vụ xuống bề mặt API

Tám nhóm nghiệp vụ được cài đặt thành **27 bộ định tuyến API** với **224 điểm cuối
trên 199 đường dẫn** dưới tiền tố `/api/`, một giao diện đơn trang **71 tệp màn
hình**, và một bộ công cụ vận hành chạy trên dòng lệnh.

**Con số này đọc từ bảng định tuyến của ứng dụng đã dựng, không đếm bộ trang trí
trong mã** — và hai cách cho hai kết quả khác nhau, nên phải nói rõ dùng cách nào.
Đếm bộ trang trí `@router.<phương thức>` trong `backend/app/routers/` ra 227: nó
gộp cả những khai báo không được đăng ký dưới tiền tố `/api/`, và bỏ sót những
điểm cuối khai báo ngoài thư mục ấy. Bảng định tuyến trả lời đúng câu người đọc
hỏi — *hệ thống thực sự phục vụ bao nhiêu điểm cuối* — nên nó là nguồn được chọn.

Một cái bẫy khi đếm lại: mỗi bộ định tuyến được gắn **hai lần**, một lần dưới
`/api/v1/...` và một lần dưới đường không tiền tố (`/workspaces/...`) để giữ
tương thích với các bản giao diện cũ. Đếm toàn bộ bảng định tuyến mà không lọc
tiền tố sẽ ra **419**, tức đếm mỗi điểm cuối hai lần cộng thêm các đường phục vụ
tài liệu và kiểm tra sức khoẻ. Con số ấy không sai về mặt số học và sai hoàn toàn
về mặt ý nghĩa.

*Bảng 3-6: Bộ định tuyến và số điểm cuối theo nghiệp vụ*

| Nghiệp vụ | Bộ định tuyến | Điểm cuối |
|---|---|:--:|
| NV1 Danh tính và quyền truy cập | `auth` (14), `verification` (6), `two_factor` (5), `legal` (8), `trial` (2) | 35 |
| NV2 Thu thập và quản lý dữ liệu mẫu | `upload` (3), `dataset` (16), `label_sessions` (6), `jobs` (2), `dataset_exporter` (1) | 28 |
| NV3 Danh mục từ vựng và phương ngữ | `classes` (16), `vocabulary` (6) | 22 |
| NV4 Huấn luyện, đánh giá và suy luận | `training` (13), `experiments` (12), `inference` (1), `realtime_proxy` (3), `tts` (3) | 32 |
| NV5 Tổ chức và đăng ký dịch vụ | `tenants` (21), `workspaces` (14), `billing` (7) | 42 |
| NV6 Quản trị người dùng và chính sách | `admin` (22), `legal_admin` (12) | 34 |
| NV7 Vận hành hệ thống và nguồn sự thật | `sot_admin` (6), `health` (7) | 13 |
| NV8 Hỗ trợ và tích hợp | `support` (8), `notifications` (5), `integrations` (9) | 22 |
| | **Tổng** | **228** |

**Cách đếm, để con số kiểm chứng lại được:** số bộ trang trí phương thức HTTP
(`@router.get|post|put|patch|delete`) trong `backend/app/routers/`. Con số này lệch
vài đơn vị so với số đường dẫn trong đặc tả OpenAPI, vì một hàm có thể đăng ký nhiều
phương thức trên cùng một đường dẫn, và ngược lại một đường dẫn có tham số có thể
sinh nhiều mục trong đặc tả. Nêu cách đếm ra là điều kiện để con số này có giá trị.

**Một thay đổi so với các bản trước của tài liệu, phải ghi nhận:** bộ định tuyến
`workspaces` với **14 điểm cuối** là bề mặt vận hành cho hai cấp phạm vi dưới tổ
chức (không gian làm việc và dự án). Trước bộ định tuyến này, hai cấp đó **có bảng
nhưng không có API**, và phát biểu chính thức của luận văn phải là *"kiến trúc hỗ
trợ nhiều cấp; cưỡng chế chứng minh được ở cấp hệ thống và cấp tổ chức"*. Phát biểu
đó nay đã đổi một phần — chi tiết và **giới hạn còn lại** ở §3.3.3.2.

---

### 3.1.4. Mô hình Use Case

#### a. Vì sao mô hình use case của luận văn không trùng với danh mục chức năng của sản phẩm

CTU.SignBridge là một sản phẩm hoàn chỉnh. Đặc tả đầy đủ của nó gồm **75 use case**
trải trên tám nhóm nghiệp vụ, và toàn bộ 75 use case đó đã được liệt kê ở Bảng 3-5,
với đặc tả chi tiết ở **Phụ lục C**. Nhưng đưa nguyên vẹn 75 use case vào Chương 3 là
một sai lầm về phạm vi, chứ không phải một sự đầy đủ đáng khen — và lý do rất cụ thể:

> Một sơ đồ use case có 75 hình bầu dục không nói với người đọc rằng hệ thống làm
> được nhiều việc. Nó nói rằng tác giả **chưa quyết định được luận văn của mình nói
> về cái gì**.

Phạm vi nghiên cứu tuyên bố ở §3.1.1 d là **phân hệ thu thập và quản lý dữ liệu VSL
theo mô hình SaaS đa tổ chức**. Huấn luyện, nhận dạng, hỗ trợ, tích hợp và thanh
toán là các phân hệ **có thật trong sản phẩm** nhưng **ở hạ nguồn hoặc ở vành ngoài**
của phạm vi đó. Nếu chúng đứng ngang hàng với Tổ chức, Không gian làm việc, Dự án,
Bộ dữ liệu và Thu nhận dữ liệu trên cùng một sơ đồ, câu hỏi đầu tiên của hội đồng sẽ
là một câu hỏi mà tác giả tự tạo ra cho mình: *"vậy đề tài là nền tảng quản lý dữ
liệu hay nền tảng huấn luyện?"*

Vì vậy Chương 3 dùng **mô hình use case thu gọn theo phạm vi luận văn**: **24 use
case** chia **năm nhóm**. Quan hệ giữa hai mô hình được phát biểu tường minh:

*Bảng 3-9: Hai mô hình use case và quan hệ giữa chúng*

| | Danh mục chức năng sản phẩm | **Mô hình use case của luận văn** |
|---|---|---|
| Số use case | 75 | **24** |
| Phạm vi | Toàn bộ CTU.SignBridge | Phân hệ thu thập và quản lý dữ liệu |
| Vị trí trong quyển | **Phụ lục C** | **Chương 3 §3.1.4 và §3.5** |
| Mức chi tiết | Đặc tả đầy đủ từng use case | 7 use case đặc tả đầy đủ ở thân bài, 17 use case còn lại đặc tả ở Phụ lục C |
| Vai trò | Chứng minh sản phẩm hoàn chỉnh | **Chứng minh các cam kết của đề cương** |

Cách trình bày này giữ được cả hai: không mất công việc đã làm (Phụ lục C giữ đủ 75),
và không làm loãng đóng góp (Chương 3 chỉ nói về 24).

#### b. Năm nguyên tắc dựng mô hình

Năm nguyên tắc dưới đây được áp dụng khi rút từ 75 xuống 24, và chúng cũng là năm
tiêu chí để kiểm tra lại mô hình. Bốn nguyên tắc đầu là kỷ luật UML; nguyên tắc thứ
năm là kỷ luật trung thực.

**Nguyên tắc 1 — Tác nhân phải nằm ngoài ranh giới hệ thống.**
Một thành phần bên trong hệ thống không phải là tác nhân, dù nó có "hành động". Bản
đặc tả nháp đặt *Processing Worker* làm tác nhân chính của use case xử lý bản ghi;
điều đó sai, vì tiến trình nền là một phần của hệ thống, không phải một bên ngoài
hệ thống có mục tiêu riêng. Cách viết đúng:

```
Ở MÔ HÌNH USE CASE:            Người đóng góp dữ liệu ──► Tải dữ liệu lên
                                Người đóng góp dữ liệu ──► Theo dõi xử lý

Ở THIẾT KẾ CHỨC NĂNG (§3.5.3): Backend ──► Hàng đợi ──► Tiến trình nền ──► Kho lưu trữ
```

Hệ quả: `worker`, `celery-beat`, `realtime_service` **không xuất hiện** trên sơ đồ
use case, vì cả ba là dịch vụ của chính CTU.SignBridge. Chỉ bốn tác nhân hệ thống
thật sự nằm ngoài ranh giới mới được vẽ, và cả bốn đều ở vai **tác nhân phụ**: dịch
vụ gửi tin, kho lưu trữ ngoài, máy ghi nguồn sự thật, ứng dụng bên thứ ba.

**Nguyên tắc 2 — Ghi nhật ký kiểm toán không phải một quan hệ `«include»`.**
Bản đặc tả nháp cho nhiều use case quản trị `«include»` use case *Xem nhật ký kiểm
toán*. Điều này sai về nghĩa: quản trị viên tạo một tổ chức thì **hệ thống ghi** một
bản ghi kiểm toán, chứ quản trị viên **không phải đi xem** nhật ký như một bước bắt
buộc để hoàn tất việc tạo tổ chức.

```
SAI:   Quản lý tổ chức  «include»  Xem nhật ký kiểm toán

ĐÚNG:  Quản lý tổ chức
            └── (hành vi nội bộ) Hệ thống ghi một bản ghi kiểm toán   → hậu điều kiện

       Xem nhật ký kiểm toán  ← là một use case ĐỘC LẬP, có hai tác nhân:
            Quản trị nền tảng  ──► xem nhật ký toàn nền tảng
            Quản trị tổ chức   ──► xem nhật ký trong phạm vi tổ chức mình
```

Việc ghi nhật ký thuộc về **hậu điều kiện** của use case, và đó là chỗ đúng của nó.
Sửa này áp cho sáu use case trong bản nháp.

Ba loại quan hệ UML được dùng trong quyển, mỗi loại cho đúng một tình huống. Giữ kỷ
luật này quan trọng, vì `«include»` và `«extend»` bị dùng lẫn là lỗi phổ biến nhất
trong sơ đồ use case, và nó làm sơ đồ mất khả năng diễn đạt.

*Bảng 3-7: Ba loại quan hệ và tình huống dùng*

| Quan hệ | Nghĩa dùng trong quyển | Ví dụ trong mô hình |
|---|---|---|
| `«include»` | A **luôn luôn** gọi B; bỏ B thì A không hoàn tất được | UC-A2 Đăng ký `«include»` Chấp thuận văn bản pháp lý nền tảng |
| `«extend»` | B **chỉ đôi khi** chen vào A, tại một điểm mở rộng, theo một điều kiện | Xác thực lại `«extend»` UC-B1 Quản lý tổ chức — *khi thao tác không hoàn tác được* |
| Tổng quát hoá | B là dạng chuyên biệt của A | Gửi mã xác thực → chuyên biệt thành *gửi qua email* và *gửi qua tin nhắn* |
| `«constraint»` *(chú thích, không phải quan hệ UML chuẩn)* | B **thay đổi kết quả** của A mà không phải một bước của A | UC-C5 Đồng thuận người ký `«constraint»` UC-D4 Xuất bộ dữ liệu |

Dòng cuối cần giải thích: quan hệ giữa việc rút đồng thuận và việc xuất dữ liệu
**không biểu diễn được** bằng ba loại quan hệ chuẩn. Rút đồng thuận không phải một
bước của việc xuất dữ liệu, cũng không phải một nhánh mở rộng của nó — nó là một sự
kiện xảy ra ở thời điểm khác, chạy **ngược chiều** dòng nghiệp vụ, và làm đổi kết
quả của mọi lần xuất **sau đó**. Đây là ràng buộc nghiệp vụ đặc trưng nhất của hệ
thống, nên nó được ghi bằng chú thích `«constraint»` trên sơ đồ chứ không bị bỏ đi
cho gọn.

**Nguyên tắc 3 — Yêu cầu phi chức năng không sinh ra use case.**
Không có use case nào tên là *"Cách ly dữ liệu tổ chức"*, vì **không tác nhân nào
thực hiện việc cách ly**. Cách ly là một bất biến của hệ thống:

$$\text{Request}(T_A) \Rightarrow \neg\,\text{Data}(T_B)$$

Nó xuất hiện như **điều kiện ràng buộc** trên mọi use case chạm vào tài nguyên của
tổ chức — xem mẫu, quản lý lớp, xuất bộ dữ liệu, quản lý thành viên — và được chứng
minh bằng phép đo ở Chương 4 §5.2, không bằng một hình bầu dục. Nguyên tắc này cũng
áp cho *xử lý bất đồng bộ*, *hiệu quả lưu trữ* và *độ trễ*: cả ba là thuộc tính
thiết kế, không phải mục tiêu tương tác của tác nhân.

**Nguyên tắc 4 — Use case dừng ở mức yêu cầu, không xuống mức cài đặt.**
Bản đặc tả nháp đưa vào luồng sự kiện những chi tiết như "21 điểm mốc × 3 toạ độ × 2
bàn tay = 126 đặc trưng", "băm mật khẩu bằng bcrypt", "đưa token vào danh sách từ
chối", "ghi tệp sidecar cạnh tệp đặc trưng", "chuỗi proxy tin cậy". Những thông tin
này **rất có giá trị** — nhưng chúng thuộc §3.5 Thiết kế chức năng và §3.6 Cài đặt,
không thuộc mô hình use case. Một use case mô tả *cái gì phải xảy ra*, thiết kế chức
năng mô tả *xảy ra bằng cách nào*.

Khuôn use case dùng trong quyển vì thế rút còn **mười trường**: mã, tên, tác nhân
chính, tác nhân phụ, mục tiêu, tiền điều kiện, kích hoạt, luồng chính, luồng thay
thế / ngoại lệ, hậu điều kiện, và quan hệ với use case khác.

**Nguyên tắc 5 — Không đặc tả cái chưa hiện thực như thể đã chạy.**
Đây là nguyên tắc quan trọng nhất, và nó chi phối §h dưới đây. Một use case viết
xong trông giống hệt nhau dù chức năng đã chạy hay chưa; vì vậy mỗi use case trong
mô hình mang thêm một cột **trạng thái hiện thực**, với ba giá trị:

| Ký hiệu | Nghĩa | Kiểm bằng |
|:--:|---|---|
| ✔ | Đã hiện thực và có bề mặt vận hành kiểm chứng được từ bên ngoài | Có điểm cuối API **và** có kiểm thử |
| ◐ | Một phần — có bề mặt nhưng cưỡng chế hoặc phân vùng dữ liệu chưa đầy đủ | Có điểm cuối, nhưng nêu rõ phần chưa đạt |
| ○ | **Thiết kế đích** — chưa có bảng hoặc chưa có bề mặt | Nêu đích danh cái còn thiếu |

#### c. Tác nhân trong mô hình thu gọn

Mô hình thu gọn dùng **sáu tác nhân chính** và **bốn tác nhân phụ**. Sáu tác nhân
chính là hợp nhất của mười tác nhân ở Bảng 3-3, gộp theo **quyền** chứ không theo
mục tiêu — vì mục tiêu khác nhau mà quyền giống nhau thì không sinh ra nhánh khác
nhau trên sơ đồ.

*Bảng 3-10: Tác nhân trong mô hình use case của luận văn*

| Mã | Tác nhân | Ứng với Bảng 3-3 | Vai |
|---|---|---|---|
| **P1** | Khách vãng lai | A1 | Chính |
| **P2** | Người dùng đã đăng nhập | A2, A3, A4 | Chính |
| **P3** | Thành viên tổ chức | A5 | Chính (kế thừa P2) |
| **P4** | Biên tập viên dữ liệu | A6 | Chính (kế thừa P3) |
| **P5** | Quản trị tổ chức | A7 | Chính (kế thừa P4) |
| **P6** | Quản trị nền tảng | A8, A9, A10 | Chính |
| S1 | Dịch vụ gửi tin | S1 | **Phụ** — nằm ngoài ranh giới |
| S2 | Kho lưu trữ ngoài | S2 | **Phụ** — nằm ngoài ranh giới |
| S5 | Máy ghi nguồn sự thật | S5 | **Phụ** — là một máy vật lý khác |
| S6 | Ứng dụng bên thứ ba | S6 | **Phụ** — nằm ngoài ranh giới |

**Hai tác nhân của Bảng 3-3 bị loại khỏi sơ đồ, và lý do phải nêu:** S3 *Dịch vụ suy
luận* và S4 *Tiến trình nền* là **dịch vụ bên trong** CTU.SignBridge (`realtime_service`,
`worker`), nên theo Nguyên tắc 1 chúng không phải tác nhân. Chúng xuất hiện ở sơ đồ
kiến trúc (§3.3.1) và sơ đồ tuần tự (§3.3.2), là chỗ đúng của chúng.

*Bảng 3-8: Ma trận tác nhân × nhóm use case* — `●` tác nhân chính · `○` có tham gia

| Tác nhân | A. Danh tính | B. Tổ chức | C. Danh mục & Thu nhận | D. Bộ dữ liệu | E. Toàn vẹn |
|---|:--:|:--:|:--:|:--:|:--:|
| P1 Khách vãng lai | ● | ○ | | | |
| P2 Người dùng đã đăng nhập | ● | ○ | | | |
| P3 Thành viên tổ chức | ○ | ○ | ● | ○ | |
| P4 Biên tập viên dữ liệu | ○ | ○ | ● | ● | ○ |
| P5 Quản trị tổ chức | ○ | ● | ○ | ○ | ● |
| P6 Quản trị nền tảng | ○ | ● | ○ | | ● |
| S1 Dịch vụ gửi tin *(phụ)* | ○ | ○ | | | |
| S2 Kho lưu trữ ngoài *(phụ)* | | | ○ | ○ | ○ |
| S5 Máy ghi nguồn sự thật *(phụ)* | | | | | ● |
| S6 Ứng dụng bên thứ ba *(phụ)* | | | ○ | ○ | |

Một điểm đọc được từ ma trận này và đáng nói: **cột B và cột E là hai cột duy nhất
có P6 ở vai chính, và cột B là cột duy nhất P5 và P6 cùng có mặt.** Đó chính là chỗ
ranh giới P5 ≠ P6 phải được vẽ rõ nhất, và là lý do UC-B1 và UC-B4 đều nằm trong bảy
use case đặc tả đầy đủ ở thân bài.

**Một tác nhân được thêm vào, không có trong Bảng 3-3:** ở nhóm D dưới đây xuất hiện
vai *người nhận bộ dữ liệu* — người tải một bản phát hành về để dùng. Vai này khác
*người đóng góp dữ liệu*, vì cam kết pháp lý họ phải chấp nhận là một cam kết khác
(xem §g, bất biến 1). Hiện tại vai này trùng với P4 trong cài đặt, nhưng phải tách
ở mô hình vì đó là hai chủ thể pháp lý khác nhau.

#### d. Danh mục 24 use case của mô hình luận văn

*Bảng 3-11: Mô hình use case theo phạm vi luận văn*

**Nhóm A — Danh tính và truy cập (3 use case)**

| Mã | Use case | Tác nhân chính | Trạng thái | Vị trí đặc tả |
|---|---|---|:--:|---|
| **UC-A1** | **Đăng nhập và thiết lập phạm vi phiên** | P1 Khách vãng lai | ✔ | **Thân bài §3.5.1** |
| UC-A2 | Đăng ký và chấp thuận văn bản nền tảng | P1 Khách vãng lai | ✔ | Phụ lục C |
| UC-A3 | Quản lý bảo mật tài khoản (mật khẩu, 2FA, khôi phục) | P2 Người dùng đã đăng nhập | ✔ | Phụ lục C |

**Nhóm B — Tổ chức, phân cấp và phân quyền (5 use case)**

| Mã | Use case | Tác nhân chính | Trạng thái | Vị trí đặc tả |
|---|---|---|:--:|---|
| **UC-B1** | **Quản lý tổ chức** | P6 Quản trị nền tảng | ✔ | **Thân bài §3.5.1** |
| UC-B2 | Quản lý không gian làm việc | P5 Quản trị tổ chức | **◐** | Thân bài (nhắc) |
| UC-B3 | Quản lý dự án | P5 Quản trị tổ chức | **◐** | Thân bài (nhắc) |
| **UC-B4** | **Mời và gỡ thành viên** | P5 Quản trị tổ chức | ✔ | **Thân bài §3.5.1** |
| **UC-B5** | **Quản lý gán vai theo phạm vi** | P5 Quản trị tổ chức | **◐** | **Thân bài §3.5.1** |

**Nhóm C — Danh mục VSL và thu nhận dữ liệu (9 use case)**

| Mã | Use case | Tác nhân chính | Trạng thái | Vị trí đặc tả |
|---|---|---|:--:|---|
| UC-C1 | Duyệt danh mục từ vựng | P3 Thành viên tổ chức | ✔ | Phụ lục C |
| **UC-C2** | **Quản lý lớp ký hiệu** | P4 Biên tập viên | ✔ | **Thân bài §3.5.2** |
| UC-C3 | Quản lý phương ngữ và vùng miền | P4 Biên tập viên | ✔ | Thân bài (nhắc) |
| UC-C4 | Mở rộng danh mục của tổ chức từ danh mục hệ thống | P4 Biên tập viên | ✔ | Thân bài (nhắc) |
| UC-C5 | Quản lý người ký và đồng thuận của người ký | P4 Biên tập viên | **◐** | Thân bài (nhắc) |
| **UC-C6** | **Thu mẫu từ camera** | P3 Thành viên tổ chức | ✔ | **Thân bài §3.5.3** |
| UC-C7 | Tải lên dữ liệu nguồn có sẵn | P3 Thành viên tổ chức | ✔ | Thân bài (nhắc) |
| UC-C8 | Theo dõi xử lý và quản lý mẫu, phiên thu, thùng rác | P3 Thành viên tổ chức | ✔ | Phụ lục C |
| UC-C9 | Xem thống kê thu thập | P3 Thành viên tổ chức | ✔ | Phụ lục C |

**Nhóm D — Bộ dữ liệu, phiên bản và quản trị dữ liệu (4 use case)**

| Mã | Use case | Tác nhân chính | Trạng thái | Vị trí đặc tả |
|---|---|---|:--:|---|
| UC-D1 | Quản lý bộ dữ liệu | P4 Biên tập viên | **○** | Thân bài (nhắc) — §3.5.4 |
| **UC-D2** | **Tạo phiên bản bộ dữ liệu và ghim phiên bản danh mục** | P4 Biên tập viên | **○ / ◐** | **Thân bài §3.5.4** |
| UC-D3 | Xem nguồn gốc của một phiên bản bộ dữ liệu | P4 Biên tập viên | **◐** | Thân bài (nhắc) |
| **UC-D4** | **Xuất một phiên bản bộ dữ liệu** | P4 Biên tập viên | ✔ | **Thân bài §3.5.4** |

**Nhóm E — Toàn vẹn và quản trị nền tảng (3 use case)**

| Mã | Use case | Tác nhân chính | Trạng thái | Vị trí đặc tả |
|---|---|---|:--:|---|
| **UC-E1** | **Xác minh toàn vẹn nguồn sự thật** | P6 Quản trị nền tảng | ✔ | **Thân bài §3.5.6** |
| UC-E2 | Đối soát dữ liệu giữa nguồn sự thật và bản sao | P6 Quản trị nền tảng | ✔ | Thân bài (nhắc) |
| UC-E3 | Xem nhật ký kiểm toán theo phạm vi | P5 Quản trị tổ chức, P6 Quản trị nền tảng | ✔ | Thân bài (nhắc) |

**Tổng: 24 use case** — 3 + 5 + 9 + 4 + 3.

Ngoài 24 use case trên, mô hình giữ **một tác nhân trình diễn hạ nguồn** để thể hiện
vòng đời dữ liệu khép kín, nhưng **không** đặc tả nó thành các use case ngang hàng:

```
Dữ liệu đã quản lý ──► «downstream» Huấn luyện và nhận dạng
                       (UC401–UC409 — đặc tả ở Phụ lục C)
```

#### e. Bảy use case đặc tả đầy đủ ở thân bài

Tiêu chí: use case đó phải là **nơi một cam kết của đề cương được thi hành**, và
phải là **đối tượng của một phép đo hoặc một lập luận ở Chương 4**.

*Bảng 3-12: Bảy use case đặc tả đầy đủ, và cam kết mà mỗi use case gánh*

| Mã | Use case | Cam kết đề cương được thi hành | Đo/kiểm ở |
|---|---|---|---|
| UC-A1 | Đăng nhập và thiết lập phạm vi phiên | Là nơi **ngữ cảnh tổ chức ra đời**; mọi phép cưỡng chế phía sau dựa vào bước này | Ch.4 §5.2 (đối chứng dương) |
| UC-B1 | Quản lý tổ chức | **Tạo ra một ranh giới cách ly**; sai ở đây thì mọi cưỡng chế phía sau vô nghĩa | Ch.4 §5.2 |
| UC-B4 | Mời và gỡ thành viên | Ranh giới **P5 ≠ P6**: đường duy nhất đưa người vào tổ chức là lời mời | Ch.4 §5.2 (ma trận vai × tổ chức) |
| UC-B5 | Quản lý gán vai theo phạm vi | **RBAC nhiều cấp** — cam kết trực tiếp của đề cương | Ch.4 §5.2, có nêu giới hạn |
| UC-C2 | Quản lý lớp ký hiệu | **Danh mục VSL có phương ngữ và vùng miền**; định danh lớp năm cột | Ch.4 §5.6 (chứng cứ hai chiều) |
| UC-C6 | Thu mẫu từ camera | **Trích đặc trưng tại trình duyệt** và hiệu quả lưu trữ | Ch.4 §5.4 |
| UC-D4 | Xuất một phiên bản bộ dữ liệu | **Cổng đồng thuận** + **giam hãm đầu ra theo tổ chức** | Ch.4 §5.2 (C5), §5.7 |

Riêng **UC-D2** *Tạo phiên bản bộ dữ liệu* được trình bày ở §3.5.4 như **thiết kế
đích**, với phần đã có và phần chưa có tách bạch — lý do ở §h.

#### f. Những gì được đẩy sang Phụ lục, và vì sao

Việc đẩy sang phụ lục **không phải** loại bỏ. Các use case dưới đây là use case hợp
lệ của sản phẩm, đã cài đặt và đã chạy; chúng chỉ không đứng ngang hàng với Tổ chức,
Không gian làm việc, Dự án, Bộ dữ liệu và Thu nhận dữ liệu trên sơ đồ của luận văn.

*Bảng 3-13: Nhóm chức năng đẩy sang Phụ lục C và lý do*

| Nhóm | Use case | Lý do đẩy sang phụ lục |
|---|---|---|
| Huấn luyện và suy luận | UC401–UC409 (9 UC) | Là **bên tiêu thụ hạ nguồn**, đã tuyên bố ngoài phạm vi ở §3.1.1 d. Giữ ở thân bài sẽ làm lệch câu hỏi của hội đồng sang chất lượng mô hình |
| Luồng con của xác thực | UC103 Gửi mã xác thực, UC104 Xác thực địa chỉ, UC106 Yếu tố thứ hai, UC109 Quản lý 2FA | Là **luồng con** của UC-A2 và UC-A3, không phải mục tiêu độc lập của tác nhân |
| Thao tác lẻ trên mẫu | UC208 Xem lại video, UC209 Xoá phiên, UC211 Xoá mẫu, UC212 Thùng rác | Gộp thành **UC-C8**; tách lẻ ở thân bài chỉ làm sơ đồ đông mà không thêm lập luận |
| Dùng thử và đọc thành tiếng | UC114, UC408 | Chức năng trình diễn, không gánh cam kết nào |
| Hỗ trợ | UC801–UC804 | Vành ngoài; đề cương xếp là phần chưa bắt buộc |
| Tích hợp | UC805 Khoá API, UC806 Webhook | Vành ngoài. **Nhưng**: ràng buộc cách ly trên đường khoá API vẫn phải nêu ở §3.5.6, vì đó là bề mặt duy nhất một hệ thống ngoài chạm vào dữ liệu tổ chức |
| Thanh toán và hạn mức | UC506, UC609 | Đề cương xếp *fully automated resource governance* là phần chưa bắt buộc hiện thực đầy đủ |
| Vận hành chi tiết | UC701 Quản lý máy ghi, UC704 Sức khoẻ, UC705 Sao lưu, UC706 Độ tươi | Là công việc của A10 **chạy ngoài ứng dụng**, trên dòng lệnh. Giữ UC-E1 và UC-E2 làm đại diện |

#### g. Bảy bất biến phải chỉnh trước khi vẽ sơ đồ

Bảy điểm dưới đây là chỗ bản đặc tả nháp mô tả hệ thống **khác với** mô hình dữ liệu
và mã nguồn hiện tại. Đây không phải lỗi chính tả: nếu không sửa, use case, sơ đồ
thực thể quan hệ và cài đặt sẽ nói ba phiên bản khác nhau của cùng một luật, và hội
đồng sẽ tìm ra chỗ lệch đó.

**Bất biến 1 — Có BA loại đồng thuận, không phải một.**
Đây là điểm nghiêm trọng nhất về mô hình nghiệp vụ. Bản nháp để một use case duy
nhất (*Accept legal document*) vừa đóng vai chấp thuận điều khoản dịch vụ, vừa quyết
định mức phát hành của các mẫu mà tài khoản đó đóng góp. Điều đó mâu thuẫn với chính
lập luận trung tâm của luận văn: **tài khoản vận hành ≠ chủ thể dữ liệu**.

```
(1) Người dùng nền tảng ──► Chấp thuận văn bản pháp lý nền tảng
        ghi vào: user_consents          → chi phối: quyền dùng dịch vụ

(2) Người ký / người đại diện ──► Cho và RÚT đồng thuận về dữ liệu của mình
        ghi vào: signer_consents        → chi phối: ĐƯỜNG PHÁT HÀNH DỮ LIỆU

(3) Người nhận bộ dữ liệu ──► Chấp nhận cam kết sử dụng trước khi tải về
        ghi vào: (chưa có bảng)         → chi phối: điều kiện tải bản phát hành
```

Chỉ vế (2) chi phối việc một mẫu có xuất hiện trong bản phát hành hay không. Vế (1)
**không** suy ra được vế (2): một tài khoản chấp thuận điều khoản dịch vụ không có
nghĩa người có bàn tay trong mẫu đã đồng ý cho dùng dữ liệu của mình. Vế (3) hiện
**chưa có bảng** và được ghi là thiết kế đích.

Trong lược đồ, hai bảng `user_consents` và `signer_consents` **đã tách sẵn** (§3.4.2,
nhóm M7); chỗ sai chỉ nằm ở bản đặc tả use case. Sửa: tách thành UC-A2 (vế 1) và
UC-C5 (vế 2), và ghi vế 3 là ○.

**Bất biến 2 — Định danh lớp gồm năm cột, trong đó có vùng miền.**
Bản nháp kiểm trùng lớp theo `nhãn + ngôn ngữ + phương ngữ`. Khoá duy nhất thật trên
cơ sở dữ liệu gồm **năm cột**:

```
(tenant_id, slug, language, dialect, region)
```

Đây không phải chi tiết cài đặt mà là **luật nghiệp vụ**: hai biến thể cùng một từ,
cùng phương ngữ, khác vùng miền là **hai lớp khác nhau**. Bản nháp kiểm bốn cột sẽ
đặc tả một hệ thống **từ chối** đúng những gì hệ thống thật cho phép. Ràng buộc kèm
theo phải giữ: *chưa phân loại* ≠ *dùng chung* — hai giá trị đó không được coi là
một khi so trùng.

**Bất biến 3 — BA khái niệm khác nhau, và cả ba đều từng bị gọi là "cộng đồng".**
Đây là chỗ dễ nhầm nhất trong toàn bộ mô hình, và bản nháp nhầm ở cả hai hướng: gọi
danh mục cấu hình của hệ thống là "cộng đồng", và mô tả "cộng đồng" như một đường
đi tắt đọc được từ mọi nơi, nằm ngoài mọi phạm vi tổ chức.

*Bảng 3-9a: Ba khái niệm phải tách bạch*

| | **Danh mục hệ thống** *(System Catalog)* | **Cộng đồng** *(Community)* | **Tổ chức mồi `default`** |
|---|---|---|---|
| Hiện thực bằng | Ba bảng `community_*` — **tên bảng là di sản, không phải nghĩa** | **Một hàng của bảng `tenants`**: `tenant_id='community'`, `tenant_type='COMMUNITY'`, `is_system_reserved=TRUE` | Một hàng của `tenants` với `tenant_type='ORGANIZATION'`, `is_system_reserved=FALSE` |
| Chứa gì | **Chỉ cấu hình**: phương ngữ nào tồn tại, hồ sơ nhận dạng nào tồn tại. **Không** chứa mẫu, điểm mốc, bản ghi đồng thuận, thông tin quy kết hay giấy phép | Dữ liệu đóng góp cho cộng đồng, sau khi được duyệt | **Corpus nghiên cứu thật** của hệ thống tiền thân |
| Chịu cách ly theo tổ chức | **Không** — là danh mục phẳng của nền tảng, mọi tổ chức đọc chung, **không tổ chức nào ghi được** | **Có** — chịu **đúng** RLS / RBAC / khoá ngoại ghép như mọi tổ chức khác | **Có** |
| Đường vào | Quản trị nền tảng công bố | Yêu cầu đóng góp → duyệt | Thu nhận bình thường |
| Trạng thái hiện thực | ✔ | **○ — Community Data Commons hiện là 0 dòng mã**; hàng tenant dự trữ đã có, dữ liệu chưa có | ✔ |

**Quyết định kiến trúc đáng bảo vệ nhất ở đây: Cộng đồng là một tenant dự trữ, KHÔNG
phải một mức phạm vi thứ năm.** Phương án kia — đặt Cộng đồng ngang hàng với
`SYSTEM / TENANT / WORKSPACE / PROJECT` — đòi **một trục phân quyền song song**: miền
riêng cho bộ máy quyền, bảng thành viên riêng, chuỗi thống trị phạm vi riêng, chính
sách cách ly riêng. Bốn cơ chế nhân đôi, và mỗi cái là một chỗ để hai nhánh trôi khỏi
nhau. Là **một tenant**, Cộng đồng **thừa hưởng nguyên** bốn tầng đã có và đã được
kiểm ở §3.3.3.1 — **không có đường vòng nào cần viết, nên cũng không có đường vòng nào
để quên**. Một chỉ mục duy nhất (`uq_tenants_single_community`) bảo đảm tồn tại **nhiều
nhất một** tenant cộng đồng.

**Rủi ro kèm theo, và cách xử — phải nêu, vì `tenant_type` không tự giải quyết nó:**
nếu ở đâu đó trong mã có một phép kiểm dạng *"người này thuộc tenant đang xét thì cho
qua"*, thì đường ấy **âm thầm trở thành cửa vào Cộng đồng** ngay khi Cộng đồng có dữ
liệu. Cột `tenant_type` và cờ `is_system_reserved` **là nhãn, không phải quyền**, nên
chúng không chặn được điều đó. Cái chặn được là một quy tắc về mã:

> **Tư cách thành viên không bao giờ là điều kiện đủ để cho qua. Mọi phép kiểm phải hỏi
> một QUYỀN cụ thể, không hỏi "có phải thành viên không".**

**`default` không phải Cộng đồng, và cũng không phải "dữ liệu chung".** Nó là một tổ
chức bình thường về mọi mặt cách ly, đang giữ corpus nghiên cứu thật. Coi nó là dữ liệu
chung là mở một lỗ hổng đúng bằng **toàn bộ dữ liệu lịch sử**.

*Một dấu vết của sự nhầm lẫn này còn trong mã, và được nêu ra chứ không giấu:* điểm
cuối thống kê mang tên `/classes/community-stats` **không** đọc mặt phẳng Cộng đồng —
nó đọc một tổ chức cấu hình được, mặc định là `default`. Hành vi hiện tại được **giữ
nguyên có chủ ý**, vì đổi nó là một quyết định chính sách chứ không phải một bản vá
cách ly. Điều đã sửa được ngay là **phạm vi đã trở thành tường minh**: bản trước đọc
toàn bộ kho nên bốn con số ấy rò quy mô của mọi tổ chức; nay thêm dữ liệu vào một tổ
chức khác **không** làm chúng đổi.

Luật *kế thừa lúc khởi tạo ≠ rơi về lúc chạy* (RB-D7) áp cho quan hệ **Danh mục hệ
thống → Tổ chức**, và phải xuất hiện trong luồng của UC-C4.

**Bất biến 4 — Thẩm quyền của nguồn sự thật chỉ có MỘT chiều cho MỖI loại dữ liệu.**
Bản nháp chứa hai phát biểu ngược nhau: một chỗ nói lệch thì dựng lại nguồn sự thật
từ cơ sở dữ liệu, chỗ khác nói cơ sở dữ liệu được dựng lại từ nguồn sự thật. Hai
chiều không thể cùng là thẩm quyền. Phát biểu đúng tách theo **loại dữ liệu**:

| Loại dữ liệu | Thẩm quyền | Bản dẫn xuất | Cơ chế |
|---|---|---|---|
| Danh mục và lược đồ | **Tạo tác đã ký** trên máy phát hành (S5) | Cơ sở dữ liệu của mỗi máy triển khai | Xác minh chữ ký rồi hợp nhất **chỉ điền, không xoá** |
| Kho mẫu | **Tệp CSV nguồn sự thật** (RB-D2) | Bảng quan hệ | Đối soát định kỳ theo chiều CSV → CSDL |

Đường ngược lại **có tồn tại**, nhưng nó không phải một thẩm quyền thứ hai: đó là
**sửa chữa một lượt ghi hỏng giữa chừng**. Khi một mẫu đã ghi vào cơ sở dữ liệu mà
chưa kịp nối vào tệp nguồn sự thật, tác vụ đối soát điền nốt dòng còn thiếu. Phân
biệt này phải viết rõ trong hậu điều kiện của UC-E2, vì gộp hai thứ lại chính là chỗ
sinh ra mâu thuẫn trong bản nháp.

**Bất biến 5 — Gán vai theo phạm vi, không phải "một thành viên một vai".**
Bản nháp giả định mỗi thành viên có đúng một vai cố định trong tập `admin/editor/viewer`.
Mô hình thật tách hai sự thật khác nhau:

```
memberships       : anh THUỘC VỀ đâu   (cấp phạm vi: HỆ THỐNG | TỔ CHỨC | KHÔNG GIAN LÀM VIỆC | DỰ ÁN)
role_assignments  : anh LÀM ĐƯỢC GÌ ở đó (trỏ vào một membership, không trỏ vào cặp người–phạm vi)
```

Một người vì thế có thể mang vai khác nhau ở hai không gian làm việc của cùng một tổ
chức. Cách viết use case phải tổng quát theo mô hình này (UC-B5), chứ không kể tên
ba vai cứng.

**Bất biến 6 — Hai đường thu là hai đường khác nhau, không phải một.**
Bản nháp nói điểm mốc được trích tại trình duyệt (đường camera), rồi ở use case xử lý
lại nói tiến trình nền trích điểm mốc từ video. Hai phát biểu chỉ cùng đúng khi đầu
vào là tệp video. Với đường camera, **video chưa từng rời máy khách**, nên không có
gì để trích lại. Sửa: tách hai đường ngay ở mô hình use case:

```
UC-C6  Thu mẫu từ camera : Camera → trích điểm mốc TẠI MÁY KHÁCH → gửi chuỗi số → kiểm tra → mẫu
UC-C7  Tải lên dữ liệu   : Tệp video → lưu bản thô → trích điểm mốc Ở MÁY CHỦ → mẫu
```

Bước xử lý nền chung của hai đường **không** là một use case; nó là §3.5.3 Thiết kế
chức năng, và biểu diễn bằng sơ đồ tuần tự.

**Bất biến 7 — Xác thực lại thao tác nhạy cảm là một cơ chế có phạm vi phiên.**
Bản nháp mô tả việc nâng quyền như một cửa sổ đặc quyền mở bằng mật khẩu và yếu tố
thứ hai. Cài đặt thật dùng **mã xác thực lại theo thao tác** (`user_action_passcodes`),
gắn với **phiên hiện tại**, không theo tài khoản. Hệ quả phải giữ trong đặc tả: nâng
quyền **không đi theo tài khoản sang thiết bị khác**. Trong mô hình thu gọn, cơ chế
này không phải một use case riêng mà là **tiền điều kiện** của UC-B1 (dọn sạch dữ
liệu tổ chức) và của use case công bố văn bản pháp lý.

#### h. Bốn use case bổ sung, và trạng thái hiện thực thật của chúng

Bốn use case dưới đây được bổ sung vì chúng ứng trực tiếp với bốn cam kết của đề
cương mà bản đặc tả nháp không phủ. Nhưng theo Nguyên tắc 5, mỗi use case phải kèm
trạng thái hiện thực **đo được**, không phải trạng thái mong muốn.

**UC-B2 Quản lý không gian làm việc — trạng thái ◐**

| Đã có | Chưa có |
|---|---|
| Bảng `workspaces` với khoá ghép mang `tenant_id`, bật chính sách cách ly | — |
| **14 điểm cuối API** trong bộ định tuyến `workspaces`: tạo, đổi tên, lưu trữ, liệt kê thành viên, gán và thu vai | — |
| Bảng `memberships` với `scope_level = 'WORKSPACE'` | — |
| | **Dữ liệu chưa mang định danh không gian làm việc.** `samples`, `classes`, `training_jobs` mang `tenant_id`, không mang `workspace_id` — kiểm lại 18/08 vẫn đúng |
| | Chế độ phân quyền đang ở **`shadow`**: một lần gán vai cấp không gian làm việc **ghi đúng dữ liệu** và bộ máy quyền đọc được nó, nhưng bên **quyết định lúc chạy** vẫn là hệ hai phạm vi cũ |

Phát biểu đúng, phải giữ nguyên câu chữ ở mọi chỗ trong quyển: *"Không gian làm việc
và dự án đã có bề mặt vận hành và có cấu trúc phân quyền; chúng **chưa phân vùng dữ
liệu**, và vai ở hai cấp này **chưa đổi được kết quả của một phép kiểm quyền lúc
chạy**."* Viết ngắn hơn thành *"đã hỗ trợ bốn cấp phân quyền"* là **overclaim**, và
là loại overclaim mà một câu truy vấn `\d samples` đủ để bác bỏ.

**UC-B3 Quản lý dự án — trạng thái ◐**

Cùng tình trạng với UC-B2. Số liệu đo ngày **18/08/2026**: 2 không gian làm việc, 3 dự
án, 3 tenant, và tư cách thành viên đã trải đủ ba cấp. Cây `Tổ chức ⊃ Không gian làm
việc ⊃ Dự án` vì thế **đã tồn tại thật ở tầng phân quyền** — nhưng vẫn **chưa phân
vùng dữ liệu**: không một dòng mẫu hay lớp nào mang định danh dự án.

**UC-B5 Quản lý gán vai theo phạm vi — trạng thái ◐**

Luồng chính, viết theo mô hình thật chứ không theo ba vai cứng:

```
Quản trị viên chọn thành viên
        ↓
chọn vai trong danh mục vai áp dụng được
        ↓
chọn phạm vi áp dụng (tổ chức | không gian làm việc | dự án)
        ↓
Hệ thống kiểm tính hợp lệ của chuỗi phạm vi
   — membership cấp dưới phải có membership cấp trên
        ↓
Hệ thống tạo membership tương ứng, rồi tạo bản ghi gán vai trỏ vào membership đó
        ↓
Hệ thống ghi một bản ghi kiểm toán
```

Bước kiểm chuỗi phạm vi **được cưỡng chế bằng trigger ở tầng cơ sở dữ liệu**
(`ct_memberships_chain` và `ct_role_assignments_scope`, §3.4.3 d), không bằng kiểm
tra ở ứng dụng — đó là điều đáng nói của use case này. Giới hạn: xem UC-B2.

**UC-D1 / UC-D2 / UC-D3 Quản lý bộ dữ liệu, phiên bản và nguồn gốc — trạng thái ○ / ◐**

Đây là chỗ phải nói thẳng nhất trong cả mục, và cũng là chỗ Nguyên tắc 5 có giá trị
nhất. Kiểm tra trên cơ sở dữ liệu `signdb` đang chạy ngày 18/08/2026 — không một bảng
nào trong chín bảng dưới đây tồn tại:

*Bảng 3-14: Trạng thái thật của nhóm bảng phiên bản bộ dữ liệu*

| Thực thể cần cho vòng đời bộ dữ liệu | Trạng thái trên CSDL | Cái thật sự tồn tại |
|---|---|---|
| `datasets` | **Không có bảng** | — |
| `dataset_versions` | **Không có bảng** | — |
| `dataset_version_samples` | **Không có bảng** | — |
| `sample_revisions` | **Không có bảng** | `samples` sửa tại chỗ, chỉ có `deleted_at` |
| `registry_versions` | **Có** | Ảnh chụp danh mục bất biến theo quy ước, có mã băm |
| Quan hệ ghim phiên bản | **Có, đúng một quan hệ** | `training_jobs(tenant_id, registry_version) → registry_versions(tenant_id, version)` |

Chín tệp định nghĩa cấu trúc cho nhóm bảng này **có nằm trong kho mã nguồn**
(`backend/migrations/001_*.sql` và `002_*.sql`) nhưng **chưa bao giờ được áp** lên cơ
sở dữ liệu đang chạy — chúng nằm ngoài đường di trú hiện hành.

Vì vậy ba use case UC-D1, UC-D2, UC-D3 được trình bày như sau, và không được trình
bày khác đi:

* **Cái đã đạt, và phát biểu đúng mức:** hệ thống ghim được **không gian nhãn** của
  một lượt huấn luyện vào một phiên bản danh mục bất biến. Chạy lại một tác vụ sáu
  tháng sau vẫn dùng đúng tập nhãn của lần đầu.
* **Cái chưa đạt:** hệ thống **chưa ghim được nội dung bộ dữ liệu** — tập mẫu cụ thể
  đã tham gia một lượt huấn luyện không được đóng băng thành một thực thể có phiên
  bản. Toàn bộ lập luận về khả năng tái lập của luận văn **phải dừng đúng ở ranh
  giới này**.
* **UC-D4 Xuất một phiên bản bộ dữ liệu** là use case duy nhất trong nhóm mang trạng
  thái ✔, nhưng tên của nó phải đọc đúng: nó xuất **bộ dữ liệu tại thời điểm hiện
  tại theo một bộ lọc**, kèm bản kê và mã băm, chứ không xuất một *phiên bản đã được
  đóng băng từ trước*. Đây là hai việc khác nhau, và gọi việc thứ nhất bằng tên của
  việc thứ hai là chỗ dễ overclaim nhất trong cả chương.

Trình bày ba use case này ở mức thiết kế đích **có giá trị**: nó chỉ ra khoảng cách
giữa mô hình cần có và hệ thống đang có, và đó là một kết quả nghiên cứu. Trình bày
chúng như đã chạy là bịa lược đồ.

#### i. Đối chiếu mã số với bản đặc tả nháp tiếng Anh

Bản đặc tả nháp `Use case Minh.docx` chứa **63 use case** chia thành **7 nhóm**, dùng
một hệ đánh số **không tương thích** với hệ 75 use case / 8 nhóm của Phụ lục C. Bảng
dưới đây là bảng ánh xạ để hợp nhất hai tài liệu; mọi mã trong Chương 3 dùng hệ
UC-A1…UC-E3 của §d, và mọi mã trong Phụ lục C dùng hệ 75.

*Bảng 3-15: Ánh xạ mã số — bản nháp tiếng Anh → mã Phụ lục C*

| Nhóm bản nháp | Mã nháp | Tên | **Mã Phụ lục C** | Ghi chú |
|---|---|---|---|---|
| Identity and access | UC101–UC110 | Register … Manage profile | UC101–UC110 | **trùng khớp** |
| | UC111 | Accept legal document | **UC112** | lệch 1 — hệ chính thức có thêm UC111 *Xem văn bản pháp lý* |
| | UC112 | Withdraw consent | **UC113** | lệch 1 |
| | UC113 | Use trial recognition | **UC114** | lệch 1 |
| Sample data | UC201–UC204 | Record … Monitor job status | UC201–UC204 | **trùng khớp** |
| | UC205–UC212 | Browse label catalog … Export dataset | **UC206–UC213** | lệch 1 — hệ chính thức có thêm UC205 *Đặt tuỳ chọn thu* |
| Vocabulary | UC301, UC302 | Register / Update class | UC301, UC302 | **trùng khớp** |
| | UC303 | Remove class | **UC304** | hệ chính thức có thêm UC303 *Gộp hai lớp trùng* |
| | UC304 | Propose dialect | **UC306** | |
| | UC305 | Moderate dialect proposal | **UC307** | |
| | UC306 | View collection statistics | **UC305** | **đảo thứ tự** |
| Training | UC401–UC404 | Start … Review evaluation | UC401–UC404 | **trùng khớp** |
| | UC405 | Promote model version | **UC406** | hệ chính thức có thêm UC405 *Thử mô hình đã huấn luyện* |
| | UC406 | Recognize sign in realtime | **UC407** | |
| | UC407 | Speak recognized text | **UC408** | |
| Service organization | UC501–UC508 | Manage tenants … Purge tenant data | UC501–UC508 | **trùng khớp toàn bộ** |
| Platform management | UC601–UC605 | Elevate … Configure settings | UC601–UC605 | **trùng khớp** |
| | UC606 | Publish legal document | **UC607** | hệ chính thức tách *soạn/duyệt* (UC606) khỏi *công bố* (UC607) |
| | UC607 | Manage SOT writer machines | **UC701** | **đổi nghiệp vụ** — sang NV7 |
| | UC608 | Verify source-of-truth integrity | **UC702** | **đổi nghiệp vụ** |
| | UC609 | Monitor system health | **UC704** | **đổi nghiệp vụ** |
| | UC610 | Synchronize storage and database | **UC703** | **đổi nghiệp vụ + đảo thứ tự** |
| | UC611 | Manage billing plans | **UC609** | **đổi nghiệp vụ** — quay lại NV6 |
| Support and Integration | UC701–UC706 | Create ticket … Manage webhooks | **UC801–UC806** | **cả nhóm dời một trăm** |

*Bảng 3-16: Bảy lỗi nội tại của bản nháp, độc lập với việc chọn hệ đánh số nào*

| # | Vị trí | Lỗi | Sửa thành |
|---|---|---|---|
| 1 | UC601, ô *Use case* | Tên ghi là **"Recognize"**, trong khi toàn bộ phần thân và mọi dẫn chiếu từ UC508 / UC606 / UC607 đều gọi nó là *Elevate privileges* | **"Elevate privileges" / "Nâng quyền tạm thời"** |
| 2 | UC101, ô *Relationships* | `Include: UC112 Accept legal document` — trong chính hệ đánh số của bản nháp, *Accept legal document* là UC111, còn UC112 là *Withdraw consent* | `UC111` (hệ nháp) → **`UC112`** (hệ Phụ lục C) |
| 3 | UC101, luồng sự kiện bước 3 | Dẫn chiếu `(UC011)` — không tồn tại use case nào mang mã này; lỗi đảo chữ số của `UC111` | **`UC112`** (hệ Phụ lục C) |
| 4 | UC401, luồng thay thế | Dẫn chiếu `(UC031 View collection statistics)` — không tồn tại; lỗi đảo chữ số của `UC306` trong hệ nháp | **`UC305`** (hệ Phụ lục C) |
| 5 | UC608, ô nhãn trường | `Main ctor` — thiếu chữ `a`, và ô giá trị bỏ trống | `Main actor:` **A10 Kỹ sư vận hành** |
| 6 | UC607–UC610 (nháp), ô *Main actor* | Ghi là *Platform Administrator*; bốn use case này chạy **trên dòng lệnh của máy triển khai**, không chạy trong ứng dụng | **A10 Kỹ sư vận hành** |
| 7 | Toàn bộ nhóm 2–7, ô *Classification* | **Mọi** use case đều ghi `Complex` — kể cả *Monitor job status* và *View notifications*. Đây là dấu vết chép dán, và nó làm cột này mất hết giá trị phân loại | Phân loại lại: **19 Đơn giản / 41 Trung bình / 15 Phức tạp** |

Ba điểm về cách viết, cần thống nhất trước khi đưa vào quyển:

* **Ô *Expected result* bỏ trống ở cả 63/63 use case.** Hậu điều kiện là phần duy
  nhất của một đặc tả use case biến thành một khẳng định **kiểm thử được**. Bỏ trống
  nó là cắt đứt cầu nối giữa Phụ lục C và Phụ lục D. Khuôn viết hậu điều kiện và bộ
  hậu điều kiện đã bổ sung cho toàn bộ 63 use case nằm ở §j.
* **Tên tác nhân không thống nhất.** Bản nháp dùng *Data Contributor*, *Data Editor*,
  *Processing Worker*; quyển dùng A1–A10 / S1–S6 ở Phụ lục C và P1–P6 ở Chương 3.
  Phải quy về một bộ tên, nếu không sơ đồ và bảng đặc tả sẽ nói về hai mô hình tác
  nhân khác nhau. *Processing Worker* thì bị loại hẳn theo Nguyên tắc 1.
* **Ba tiêu đề nhóm cần sửa:** *"Sample data collection and mannagement"* (thừa một
  chữ `n`), *"Training và Inference"* (lẫn hai ngôn ngữ trong một tiêu đề),
  *"Vocabulary List"* (là danh từ, trong khi các tiêu đề còn lại là cụm danh động từ).

#### j. Hậu điều kiện — khuôn viết và nguyên tắc

Hậu điều kiện (*Expected result*) là trường quan trọng nhất của một đặc tả use case,
vì nó là trường duy nhất **chuyển thẳng thành một ca kiểm thử**. Một luồng sự kiện
mô tả điều gì xảy ra; chỉ hậu điều kiện mới nói **hệ thống ở trạng thái nào sau khi
xong**, và trạng thái thì kiểm được.

Khuôn dùng thống nhất cho cả 75 use case, gồm ba vế theo đúng thứ tự:

```
1. TRẠNG THÁI DỮ LIỆU  — bản ghi nào tồn tại / đổi / biến mất, ở bảng nào
2. TRẠNG THÁI PHIÊN     — quyền, phạm vi, phiên của tác nhân sau khi xong
3. HỆ QUẢ QUAN SÁT ĐƯỢC — bằng chứng mà một phép kiểm bên ngoài nhìn thấy được
                          (bản ghi kiểm toán, thông báo, tệp sinh ra, mã trạng thái)
```

Hai nguyên tắc bắt buộc khi viết hậu điều kiện:

**Nguyên tắc A — Luồng thất bại cũng có hậu điều kiện.** Trường này không chỉ mô tả
kết cục khi mọi thứ trôi chảy. Với mỗi luồng ngoại lệ đáng kể, phải nói rõ hệ thống
**ở trạng thái nào** — và trong phần lớn trường hợp, câu đúng là *"không có tác dụng
phụ nào; hệ thống ở đúng trạng thái trước khi bắt đầu"*. Một hậu điều kiện chỉ viết
cho nhánh thành công là một hậu điều kiện chưa dùng được để kiểm thử.

**Nguyên tắc B — Hậu điều kiện phải nêu cả cái KHÔNG xảy ra, khi cái đó dễ bị hiểu
nhầm là có.** Ví dụ, hậu điều kiện của use case rút đồng thuận phải ghi thẳng: *"dữ
liệu **không** bị xoá khỏi lưu trữ; các bản phát hành **đã cấp** không bị thu hồi"*.
Không ghi vế phủ định này thì đặc tả đang ngầm hứa một điều hệ thống không làm.

**Ví dụ áp dụng — hậu điều kiện của UC-C6 *Thu mẫu từ camera*:**

> **Luồng chính.** (1) Một bản ghi mẫu tồn tại trong phạm vi tổ chức của người thu,
> ở trạng thái `pending`, gắn với đúng lớp và đúng phiên thu; một tác vụ nền đã được
> xếp hàng. (2) Phiên của người dùng không đổi; hạn mức đã dùng của tổ chức tăng
> đúng một đơn vị. (3) Giao diện hiển thị mã tác vụ và trạng thái *đang xử lý*; một
> bản ghi kiểm toán tồn tại với đúng phạm vi tổ chức. **Không có** tệp video nào rời
> khỏi máy người dùng.
>
> **Luồng ngoại lệ — thiếu đồng thuận của người ký.** (1) **Không** có bản ghi mẫu
> nào được tạo. (2) Phiên không đổi; hạn mức **không** thay đổi. (3) Giao diện điều
> hướng tới màn hình đồng thuận; một bản ghi kiểm toán *từ chối vì thiếu đồng thuận*
> tồn tại.
>
> **Luồng ngoại lệ — mất kết nối lúc gửi.** (1) **Không** có bản ghi mẫu nào ở phía
> máy chủ. (2) Phiên không đổi. (3) Dữ liệu điểm mốc **vẫn còn** ở bộ nhớ trình
> duyệt và gửi lại được; không mất bản thu (NFR-R1).

Bộ hậu điều kiện đầy đủ, viết theo khuôn này cho **cả 63 use case của bản nháp**,
nằm ở tệp đi kèm `PHU_LUC_C_HAU_DIEU_KIEN.md` và được nhập vào Phụ lục C khi hợp
nhất hai tài liệu.

> ### ▣ HÌNH 3-2 — Sơ đồ use case tổng quát của phân hệ nghiên cứu
> **Loại:** sơ đồ use case UML · **Công cụ:** draw.io
> **Phải thể hiện:** đúng **24 use case** của Bảng 3-11, nhóm thành năm khối A–E; sáu
> tác nhân chính P1–P6 bên trái với ba chuỗi kế thừa `P2→P3→P4→P5`; bốn tác nhân phụ
> S1, S2, S5, S6 bên phải, **nằm ngoài khung ranh giới hệ thống**; khối «downstream»
> Huấn luyện và nhận dạng vẽ **nét đứt** ở góc dưới phải để thể hiện nó ngoài phạm vi
> nghiên cứu. **Không** vẽ `worker`, `celery-beat`, `realtime_service` như tác nhân.
> **Chú thích:** *Hình 3-2: Sơ đồ use case của phân hệ thu thập và quản lý dữ liệu VSL.*

> ### ▣ HÌNH 3-3 — Sơ đồ use case A: Tổ chức, phân cấp và phân quyền
> **Loại:** sơ đồ use case UML
> **Phải thể hiện:** năm use case UC-B1…UC-B5; quan hệ `«include»` từ UC-B4 tới use
> case gửi mã xác thực (tác nhân phụ S1 nối vào đây); quan hệ `«extend»` từ use case
> xác thực lại tới UC-B1 với điều kiện *"khi thao tác không hoàn tác được"*; ba cấp
> phạm vi vẽ thành ba vùng lồng nhau **có nhãn trạng thái ✔ / ◐** đúng theo Bảng 3-11.
> **Chú thích:** *Hình 3-3: Use case nhóm Tổ chức, phân cấp và phân quyền.*

> ### ▣ HÌNH 3-4 — Sơ đồ use case B: Danh mục VSL và thu nhận dữ liệu
> **Loại:** sơ đồ use case UML
> **Phải thể hiện:** chín use case UC-C1…UC-C9; **hai đường thu vẽ tách bạch** (UC-C6
> đường camera, UC-C7 đường tệp video) — đây là điểm phải nhìn thấy được từ hình,
> theo Bất biến 6; tác nhân phụ S2 nối vào UC-C7 bằng mũi tên **đi ra**; UC-C5 nối
> tới UC-C6 bằng nét đứt nhãn `«constraint»` (không có đồng thuận thì không thu được).
> **Chú thích:** *Hình 3-4: Use case nhóm Danh mục VSL và thu nhận dữ liệu.*

> ### ▣ HÌNH 3-5 — Sơ đồ use case C: Bộ dữ liệu, phiên bản và quản trị dữ liệu
> **Loại:** sơ đồ use case UML
> **Phải thể hiện:** bốn use case UC-D1…UC-D4 và ba use case nhóm E; **UC-D1, UC-D2,
> UC-D3 vẽ bằng nét đứt kèm nhãn trạng thái ○ / ◐** để phân biệt thiết kế đích với
> phần đã hiện thực — đây là điểm phải nhìn thấy được từ hình, theo Nguyên tắc 5;
> ràng buộc `«constraint»` từ UC-C5 (đồng thuận người ký) tới UC-D4 (xuất dữ liệu).
> **Chú thích:** *Hình 3-5: Use case nhóm Bộ dữ liệu, phiên bản và quản trị dữ liệu;
> nét đứt là phần ở mức thiết kế đích.*

> ### ▣ HÌNH 3-6 — Ba loại đồng thuận và phạm vi chi phối của từng loại
> **Loại:** sơ đồ khối
> **Phải thể hiện:** ba nhánh của Bất biến 1 đặt cạnh nhau; mỗi nhánh ghi **bảng dữ
> liệu** nó ghi vào và **thứ nó chi phối**; một đường gạch chéo giữa nhánh (1) và
> nhánh (2) thể hiện *"chấp thuận điều khoản KHÔNG suy ra đồng thuận dữ liệu"* — đây
> là điểm phải nhìn thấy được từ hình.
> **Chú thích:** *Hình 3-6: Ba loại đồng thuận và ranh giới giữa chúng.*

---

### 3.1.5. Các yêu cầu phi chức năng

Mỗi yêu cầu dưới đây có một mã, một phát biểu **kiểm chứng được**, và một cách kiểm.
Yêu cầu không nêu được cách kiểm là yêu cầu không dùng được — nó không phân biệt nổi
hệ thống đạt với hệ thống không đạt.

So với Chương 1, các bảng trong mục này bổ sung thêm **một cột**: *thiết kế đáp ứng
bằng cơ chế nào*. Đó là đóng góp riêng của Chương 3 — Chương 1 phát biểu yêu cầu,
Chương 3 chỉ ra cấu trúc đáp ứng nó, và Chương 4 đo xem cấu trúc đó có thật sự hoạt
động không.

#### 3.1.5.1. Yêu cầu thực thi

*Bảng 3-17: Yêu cầu thực thi*

| Mã | Yêu cầu | Thiết kế đáp ứng bằng | Cách kiểm |
|---|---|---|---|
| NFR-P1 | Độ trễ của các điểm cuối đọc thường dùng ở mức **dưới 100 ms tại phân vị 95** trong điều kiện không tranh chấp | Chỉ mục theo `(tenant_id, …)` khớp với khuôn chính sách cách ly; tránh truy vấn N+1 ở tầng truy cập dữ liệu (§3.6.2 a) | Đo độ trễ cơ sở, 1.000 lượt/điểm cuối, ba lượt chạy độc lập, lấy trung vị của ba giá trị phân vị (Ch.4 §5.3) |
| NFR-P2 | Trích điểm mốc tại trình duyệt đạt tối thiểu **15 khung/giây** trên máy tính xách tay phổ thông, để cửa sổ thu 60 khung hoàn tất trong khoảng 4 giây | MediaPipe biên dịch sang WebAssembly chạy tại máy khách; không có vòng gửi–nhận qua mạng trong vòng lặp thu (§3.5.3) | Đo trên máy tham chiếu nêu ở Phụ lục B |
| NFR-P3 | Thao tác thu mẫu **không được chặn** giao diện: mọi bước xử lý nặng chạy trên tiến trình nền | Ranh giới đồng bộ/bất đồng bộ đặt ngay sau bước ghi bản ghi mẫu; API trả **mã tác vụ**, không trả kết quả (§3.5.3) | Kiểm chức năng: sau khi bấm Lưu, giao diện trả về trong dưới 1 giây kèm mã tác vụ |
| NFR-P4 | Một mẫu sau chuẩn hoá chiếm **không quá 100 KiB** ở phân vị 95 | Biểu diễn 126 chiều/khung, lưu ở định dạng mảng số có nén; không lưu khung ảnh (§3.3.3.3) | Thống kê trên toàn bộ tệp đặc trưng (Ch.4 §5.4) |
| NFR-P5 | Biểu diễn điểm mốc giảm **trên 90 %** dung lượng so với video nguồn | Hệ quả trực tiếp của lựa chọn biểu diễn ở §3.3.3.3 | Đo ghép cặp khớp thời lượng trên nguồn video ngoài, báo cáo kèm cỡ mẫu và khoảng phân bố (Ch.4 §5.4) |

**Ghi chú giới hạn, phải giữ nguyên khi trích dẫn:** NFR-P1 nói về **độ trễ cơ sở**,
không nói về thông lượng và **không chứng minh cách ly hiệu năng** giữa các tổ chức.
Hai điều đó là hai phép đo khác nhau, và luận văn chỉ làm phép đo thứ nhất.

#### 3.1.5.2. Yêu cầu an toàn thông tin

Nhóm yêu cầu này là nhóm mang đóng góp lõi của luận văn. Bảy yêu cầu dưới đây không
độc lập với nhau: NFR-S1 là phát biểu mục tiêu, còn NFR-S2 đến NFR-S4 là ba lối vòng
mà nếu không bịt thì NFR-S1 chỉ đúng trên giấy.

*Bảng 3-18: Yêu cầu an toàn thông tin*

| Mã | Yêu cầu | Thiết kế đáp ứng bằng | Cách kiểm |
|---|---|---|---|
| NFR-S1 | **Cách ly dữ liệu giữa các tổ chức phải được cưỡng chế ở tầng cơ sở dữ liệu.** Một truy vấn không khai báo tổ chức trả về 0 hàng | Bốn tầng cưỡng chế ở §3.3.3.1: cột phân biệt → chính sách mức hàng → phạm vi giao dịch → tách vai CSDL | Đo đối kháng qua API: nhóm đúng quyền – sai tổ chức phải bị chặn 100 %, kèm **đối chứng dương** chứng minh chủ sở hữu làm được (Ch.4 §5.2) |
| NFR-S2 | Ứng dụng **không được tự vô hiệu hoá** cơ chế cách ly | Tầng 4: vai chạy `voya_app` không có quyền DDL, không phải siêu người dùng, không sở hữu bảng (§3.6.2 a) | Truy vấn siêu dữ liệu về quyền của vai, **cộng** thử nghiệm phát lệnh vô hiệu hoá và kiểm nó bị từ chối |
| NFR-S3 | Ngữ cảnh tổ chức phải **giới hạn trong phạm vi giao dịch**, không rò sang yêu cầu kế tiếp trên cùng kết nối | Tầng 3: `SET LOCAL` trong đúng **một** khối quản lý ngữ cảnh; không có đường nào khác đặt được ngữ cảnh (§3.6.2 a) | Kiểm thử tuần tự hai yêu cầu của hai tổ chức trên cùng một kết nối lấy từ bể |
| NFR-S4 | Công việc nền xuyên tổ chức phải đi qua **một phạm vi riêng biệt**, không mượn định danh của một tổ chức nào | Biến ngữ cảnh thứ hai `app.system_scope`, tách hẳn khỏi `app.tenant_id` (§3.3.3.1) | Kiểm rằng phạm vi hệ thống là một **biến riêng**, không phải một giá trị đặc biệt của biến tổ chức; sentinel chỉ nhận đúng chuỗi `on` |
| NFR-S5 | Mọi thao tác nhạy cảm để lại **nhật ký kiểm toán bền vững**, và việc ghi nhật ký **từ chối khi thiếu ngữ cảnh** | Bảng `audit_log` có `tenant_id` và bật chính sách; đường ghi fail-closed (§3.5.6) | Kiểm sự tồn tại bản ghi sau mỗi thao tác nhạy cảm; kiểm hành vi **từ chối** khi không có phạm vi |
| NFR-S6 | Tạo tác danh mục phải **có bằng chứng giả mạo**: sửa được nhưng không giấu được | Bản kê băm SHA-256 từng tệp + chữ ký Ed25519 phủ bản kê (§3.3.3.4) | Ma trận chín kịch bản giả mạo (Ch.4 §5.5) |
| NFR-S7 | Không xác minh được nguồn sự thật thì hệ thống **dừng**, không suy đoán | `sot-init` thoát mã lỗi chuyên biệt, và mọi dịch vụ khác phụ thuộc khởi động vào nó (§3.3.1) | Kiểm mã thoát của tiến trình khởi tạo **và** trạng thái các dịch vụ phụ thuộc |

#### 3.1.5.3. Yêu cầu bảo mật

*Bảng 3-19: Yêu cầu bảo mật*

| Mã | Yêu cầu | Thiết kế đáp ứng bằng | Cách kiểm |
|---|---|---|---|
| NFR-C1 | Cổng truy cập **mặc định từ chối**: một điểm cuối mới không khai báo công khai thì tự động yêu cầu xác thực | Kiểm soát đặt ở **tầng trung gian**, trước bộ định tuyến; danh sách ngoại lệ công khai là danh sách duy nhất (§3.6.2 b) | Kiểm ở tầng trung gian, không ở từng điểm cuối; kiểm thử liệt kê **toàn bộ** điểm cuối và đối chiếu danh sách ngoại lệ |
| NFR-C2 | Mật khẩu lưu dạng **băm có muối**; không có đường đọc ngược | bcrypt; **mô hình trả về** của mọi điểm cuối khai báo tường minh, đóng vai bộ lọc (§3.5.1) | Rà soát lược đồ **và** rà soát mô hình trả về của API |
| NFR-C3 | Phiên đăng nhập có **ba mức thu hồi**: một phiên, mọi phiên của một tài khoản, và thu hồi theo biện pháp quản trị | Bảng `refresh_tokens` có `revoked_at`; danh sách từ chối token truy cập trong Redis (§3.5.1) | Kiểm thử từng mức, riêng biệt |
| NFR-C4 | Hỗ trợ **xác thực hai yếu tố** theo chuẩn TOTP, kèm mã khôi phục dùng một lần | Cài đặt TOTP riêng; bảng `user_totp` và `user_recovery_codes` (§3.5.1) | Kiểm bằng **vector thử của tiêu chuẩn**, không chỉ kiểm "đăng nhập được" |
| NFR-C5 | Thao tác **không hoàn tác được** đòi xác thực lại trong phiên | UC601 Nâng quyền tạm thời, `«extend»` ba use case; bảng `user_action_passcodes` (§3.5.6) | Kiểm thử cho ba use case: UC508, UC607, UC609 |
| NFR-C6 | Giới hạn tần suất tính theo **địa chỉ IP thật**, không cho phía gọi tự khai | Địa chỉ lấy từ cấu hình proxy tin cậy ở `nginx`, không lấy từ tiêu đề do phía gọi đặt | Kiểm rằng tiêu đề do phía gọi đặt **không** ảnh hưởng tới bộ đếm |
| NFR-C7 | Biểu mẫu đăng nhập **không được dùng để dò tên tài khoản**: sai tên và sai mật khẩu trả cùng một thông báo và cùng độ trễ | Một nhánh trả lỗi duy nhất cho cả hai trường hợp (§3.5.1) | Kiểm thử so sánh hai nhánh, cả nội dung lẫn thời gian |
| NFR-C8 | Liên kết đặt lại mật khẩu chỉ trỏ tới **danh sách máy chủ được phép** | `FRONTEND_BASE_URL` cấu hình tường minh, không dựng từ tiêu đề `Host` | Kiểm thử với tiêu đề máy chủ giả mạo |

#### 3.1.5.4. Yêu cầu về tính tin cậy

*Bảng 3-20: Yêu cầu về tính tin cậy*

| Mã | Yêu cầu | Thiết kế đáp ứng bằng | Cách kiểm |
|---|---|---|---|
| NFR-R1 | Mất kết nối trong lúc thu **không được làm mất bản thu** | Dữ liệu điểm mốc giữ ở bộ nhớ trình duyệt cho tới khi máy chủ xác nhận; nút gửi lại (§3.5.3) | Kiểm thử ngắt mạng ở bước gửi |
| NFR-R2 | Bản gốc tải lên phải được **lưu trước** mọi bước chuẩn hoá | Thứ tự bước trong tác vụ nền: ghi `raw_uploads` **trước** cắt cửa sổ (§3.5.3) | Kiểm **thứ tự ghi** trong luồng xử lý, không chỉ kiểm sự tồn tại của bản ghi |
| NFR-R3 | Xoá là **xoá mềm**, khôi phục được cho tới khi dọn hẳn | Cột `deleted_at` trên `samples`, `classes`, `raw_uploads`; thùng rác theo người dùng (§3.5.3) | Kiểm thử khôi phục từ thùng rác ở cả ba mức xoá |
| NFR-R4 | Sao lưu cơ sở dữ liệu chạy **theo lịch**, và phải **diễn tập khôi phục được** | Dịch vụ `pg-backup`; chế độ `--drill` khôi phục vào CSDL tạm (§3.6.3) | Chạy chế độ diễn tập; kiểm toàn vẹn bằng phương pháp **phát hiện được tệp cụt** |
| NFR-R5 | Nguồn sự thật và bản sao truy vấn phải có **cơ chế đối soát định kỳ** | Tác vụ định kỳ trên `celery-beat`, chiều CSV → CSDL (§3.4.3 e) | Kiểm sự tồn tại **và kết quả** của tác vụ đối soát |
| NFR-R6 | Hệ thống phải phát hiện được **mã đang chạy không khớp mã nguồn** | Công cụ kiểm độ tươi triển khai, bắt ba kiểu lệch (§3.6.3) | Chạy công cụ trên một triển khai cố ý để cũ |
| NFR-R7 | Tác vụ nền thất bại phải **thông báo tới chủ sở hữu tác vụ**, không chỉ ghi log | Bảng `notifications` + `event_outbox`; tác vụ hỏng ghi cả hai (§3.5.6) | Kiểm thử tác vụ huấn luyện hỏng |

**Giới hạn phải nêu, không được để lẫn vào phần đánh giá:** cơ chế **thử lại** và
**tính lũy đẳng** hiện **chưa đồng đều** giữa các đường xử lý nền. Việc tạo tài
nguyên và tải đối tượng lên kho ngoài chưa bảo đảm chạy lại nhiều lần cho cùng kết
quả. Kết luận đúng mức cho cam kết tương ứng là *"đạt về năng lực, có hạn chế về độ
tin cậy"* — không phải *"đạt một phần"* về năng lực. Hai cách nói này khác nhau, và
hội đồng đánh giá chúng khác nhau.

#### 3.1.5.5. Yêu cầu về khả năng bảo trì và mở rộng

*Bảng 3-21: Yêu cầu về khả năng bảo trì và mở rộng*

| Mã | Yêu cầu | Thiết kế đáp ứng bằng | Cách kiểm |
|---|---|---|---|
| NFR-M1 | Toàn bộ hệ thống **dựng lại được từ mã nguồn** bằng một lệnh trên máy sạch | `deploy.sh` tự dò GPU và chọn overlay; pre-flight chặn trước khi dựng ảnh (§3.6.3) | Diễn tập triển khai trên **máy thứ hai** (đã thực hiện) |
| NFR-M2 | Cấu hình tách khỏi mã theo nguyên tắc Twelve-Factor; đổi cấu hình **không cần dựng lại ảnh** | Biến môi trường qua tệp `.env`; mã ứng dụng không đọc hằng số triển khai | Rà soát; kiểm thử đổi biến môi trường và tạo lại container |
| NFR-M3 | Thay đổi cấu trúc dữ liệu chia **hai loại**: bước tự động lúc khởi động chỉ được **thêm**, mọi thay đổi một chiều phải qua lệnh di trú tường minh | `ensure_tables()` chỉ chứa câu lệnh thêm; các câu một chiều nằm sau `app.cli.migrate` (§3.6.3) | Rà soát chính sách DDL lúc khởi động; kiểm thử nợ lược đồ bằng **ba lần khởi động liên tiếp** |
| NFR-M4 | Backend **từ chối khởi động** khi phiên bản lược đồ lệch, theo **cả hai chiều** | So sánh `schema_migrations.version` với hằng số trong mã; lệch thì thoát (§3.6.3) | Kiểm thử với lược đồ **cũ hơn** và lược đồ **mới hơn** |
| NFR-M5 | Lệnh di trú phải có **chốt chặn đích đến**: chạy nhầm lên cơ sở dữ liệu sản xuất bị chặn | Biến `EXPECTED_DATABASE` phải khớp tên CSDL trong DSN thì lệnh mới chạy (§3.6.3) | Kiểm thử với biến đích không khớp |
| NFR-M6 | Bộ kiểm thử chạy trong môi trường **giống môi trường thật**, trên mạng của các dịch vụ | `Dockerfile.test` + container chạy trên mạng của compose; `scripts/run_tests.sh` là cửa duy nhất (§3.6.3) | Hạ tầng kiểm thử đóng gói riêng (Ch.4 §3.2) |
| NFR-M7 | Giao diện hỗ trợ **đa ngôn ngữ**, không có chuỗi cứng trong mã | Lớp i18n; chỉ thị có biên `i18n-ignore-next-line` cho ngoại lệ có chủ ý (§3.6.1) | Công cụ đo độ phủ i18n chạy trong cổng trước triển khai |
| NFR-M8 | Hệ thống phát ra **chỉ số và nhật ký có cấu trúc**, đủ để dựng cảnh báo | Prometheus + Loki; nhãn phân loại ít, thông tin phân biệt ở siêu dữ liệu có cấu trúc (§3.5.6) | Kiểm sự tồn tại của chỉ số **và** của cảnh báo tương ứng |

---

### 3.1.6. Các ràng buộc về thực thi và thiết kế

Phân biệt giữa hai loại ràng buộc trong mục này: **ràng buộc thực thi** đến từ bên
ngoài và không thương lượng được (phần cứng, ngân sách, thời gian); **ràng buộc
thiết kế** là những điều kiện tự đặt hoặc kế thừa, và mỗi ràng buộc phải kèm lý do —
một ràng buộc tự đặt mà không nêu được lý do thì là một sở thích, không phải một
ràng buộc.

#### 3.1.6.1. Ràng buộc về thực thi

*Bảng 3-22: Ràng buộc thực thi*

| Mã | Ràng buộc | Hệ quả lên thiết kế |
|---|---|---|
| RB-T1 | **Một máy chủ vật lý duy nhất**: 6 nhân, 12 GB RAM, một GPU | Không dựng được cụm; mọi dịch vụ chạy container trên cùng máy, và **phải đặt hạn mức bộ nhớ cho từng container** để một dịch vụ rò bộ nhớ không giết cả máy. Đây là ràng buộc loại bỏ hai trong ba phương án cách ly ở §3.3.3.1 |
| RB-T2 | **Không có ngân sách hạ tầng đám mây** | Kho đối tượng chuyên dụng bị loại; dùng hệ tệp cục bộ cộng kho lưu trữ ngoài miễn phí. Đây là nguồn gốc của **bài toán hai mặt phẳng lưu trữ** ở §3.4.3 e |
| RB-T3 | Triển khai đặt sau đường dẫn cơ sở `/voya` trên máy chủ của đơn vị | Mọi liên kết tuyệt đối, mọi đường chuyển hướng và mọi tài nguyên tĩnh phải tôn trọng đường dẫn cơ sở — kể cả đường chuyển hướng khi phiên hết hạn |
| RB-T4 | Kho lưu trữ ngoài có **hạn mức lượt gọi** và có thể tạm ngừng phục vụ | Đồng bộ phải bất đồng bộ và có thử lại; **hỏng đồng bộ không được làm hỏng đường thu** |
| RB-T5 | Người dùng thu dữ liệu bằng **máy tính cá nhân phổ thông**, đường truyền không ổn định | Trích đặc trưng tại máy khách; giữ dữ liệu ở trình duyệt khi mất mạng |
| RB-T6 | Thời gian thực hiện đề tài giới hạn trong một học kỳ, một người thực hiện | Ưu tiên hoàn thiện **trục cách ly** và **trục dữ liệu**; các tầng phân quyền sâu hơn giữ ở mức thiết kế tham chiếu và bề mặt tối thiểu |

#### 3.1.6.2. Ràng buộc về thiết kế

*Bảng 3-23: Ràng buộc thiết kế*

| Mã | Ràng buộc | Lý do |
|---|---|---|
| RB-D1 | **Kế thừa một hệ thống đang chạy**, không viết mới từ đầu | Hệ thống tiền thân đã có dữ liệu thật và người dùng thật. Chuyển đổi phải theo lối **bóp nghẹt dần**: mở rộng song song rồi chuyển tải, không thay thế một lần |
| RB-D2 | Nguồn sự thật của kho mẫu hiện là **tệp CSV**, cơ sở dữ liệu quan hệ là bản sao truy vấn | Di sản kiến trúc từ hệ thống tiền thân. Không sửa được trong phạm vi đề tài mà không phá dữ liệu đang có; **phải thiết kế cơ chế đối soát thay vì giấu** |
| RB-D3 | Cách ly phải cưỡng chế **ở tầng cơ sở dữ liệu**, không ở tầng ứng dụng | Ràng buộc **tự đặt**, và là đóng góp lõi. Lý do đã trình bày ở §3.1.1 a |
| RB-D4 | Vai chạy của ứng dụng **không được có quyền DDL** | Lệnh vô hiệu hoá chính sách bảo mật mức hàng **là một lệnh DDL**. Một vai vừa ghi được dữ liệu vừa chạy được DDL thì **tự gỡ được vòng vây của chính nó**, và bảo đảm biến thành lời khuyên |
| RB-D5 | Không lưu video thô ở đường thu qua webcam | Vừa là yêu cầu về quyền riêng tư, vừa là nguồn của hiệu quả lưu trữ. Hệ quả: **không đo ngược lại được** tỉ lệ giảm dung lượng trên chính dữ liệu của hệ thống — phải đo trên nguồn video bên ngoài |
| RB-D6 | Biểu diễn dữ liệu cố định ở **126 chiều mỗi khung** (21 điểm mốc × 3 toạ độ × 2 bàn tay) | Quyết định về phạm vi: chỉ dùng thông tin bàn tay. Tư thế toàn thân và biểu cảm khuôn mặt **nằm ngoài phạm vi**, và không thu bổ sung được về sau |
| RB-D7 | Danh mục của tổ chức **không có đường rơi ngược** về danh mục hệ thống lúc chạy | Rơi ngược làm dữ liệu của hai mặt phẳng lẫn vào nhau **mà không ai biết**. Thiếu thì dừng |
| RB-D8 | Văn bản pháp lý đã công bố là **bất biến ở tầng cơ sở dữ liệu** | Chấp thuận trỏ tới một cặp (loại, phiên bản); đổi nội dung dưới chân nó biến **bằng chứng** thành **lời khẳng định suông** |
| RB-D9 | Mọi phép đo trong luận văn phải **có khả năng thất bại** và có **đối chứng dương** | Ràng buộc phương pháp. Một phép đo không thể thất bại thì không đo gì cả — xem Chương 4 §2.2 |

#### Ba giới hạn phạm vi được tuyên bố trước

Ba điểm dưới đây **không** phải khiếm khuyết phát hiện muộn; chúng được tuyên bố
ngay tại đây để các mục sau không phải biện minh, và để phần Kết luận không phải
thú nhận:

1. **Phân quyền bốn cấp mới cưỡng chế ở hai cấp.** Mô hình dữ liệu và kiến trúc
   phân quyền hỗ trợ một hệ phân cấp bốn cấp (hệ thống, tổ chức, không gian làm
   việc, dự án), và từ 18/08/2026 hai cấp dưới **đã có bề mặt API**. Nhưng cưỡng chế
   **lúc chạy** vẫn chỉ chứng minh được ở cấp hệ thống và cấp tổ chức, vì hai lý do
   cụ thể nêu ở §3.3.3.2.
2. **Cách ly phủ nửa đầu vòng đời dữ liệu chặt hơn nửa sau.** Ranh giới tổ chức được
   cưỡng chế chặt trên đường thu nhận và quản lý mẫu. Nửa sau — huấn luyện, đầu ra
   mô hình, đồng bộ ra dịch vụ ngoài — đã được gia cố nhưng còn hai đường **cố ý**
   chạy ngoài phạm vi tổ chức, nêu đích danh ở §3.4.3 e.
3. **Thu hồi không viết lại quá khứ.** Rút đồng thuận loại dữ liệu khỏi mọi bản phát
   hành **sau đó**; nó không xoá dữ liệu khỏi lưu trữ và không thu hồi được giấy
   phép đã cấp cho bên thứ ba. Giao diện nói thẳng điều này, và **có kiểm thử ghim
   đúng câu chữ đó** — để một lần sửa giao diện về sau không vô tình biến một giới
   hạn thành một lời hứa.

---

## 3.2. Tổng quan hệ thống

### 3.2.1. Bối cảnh hệ thống

CTU.SignBridge là một **nền tảng web đa tổ chức** để thu thập, tổ chức, quản lý và
hỗ trợ khai thác dữ liệu Ngôn ngữ Ký hiệu Việt Nam. Nhiều tổ chức — một trường, một
nhóm nghiên cứu, một doanh nghiệp — dùng chung **một bản triển khai duy nhất**,
nhưng dữ liệu của họ **được cô lập theo mặc định**: truy cập ra ngoài phạm vi của
mình chỉ hợp lệ qua cơ chế chia sẻ hoặc cấp quyền tường minh và có quản trị.

```
┌────────────────────────── NGOÀI RANH GIỚI HỆ THỐNG ──────────────────────────┐
│                                                                              │
│  Người ký (webcam)      S1 Dịch vụ gửi tin        S2 Kho lưu trữ ngoài       │
│  Người dùng cuối        (SMTP + SMS)              (Drive + Sheets)           │
│                                                                              │
│  S5 Máy ghi nguồn sự thật (giữ khoá ký Ed25519)   S6 Ứng dụng bên thứ ba     │
│                                                                              │
└──────┬──────────────────┬──────────────────┬──────────────────┬──────────────┘
       │ HTTPS            │ SMTP/HTTP        │ HTTP API         │ HTTPS + khoá API
┌──────▼──────────────────▼──────────────────▼──────────────────▼──────────────┐
│                          CTU.SignBridge  (một máy chủ)                        │
│                                                                              │
│  ┌───────────┐  ┌────────────┐  ┌─────────────┐  ┌────────────────────────┐  │
│  │ Giao diện │  │ Dịch vụ    │  │ Xử lý nền   │  │ Suy luận thời gian     │  │
│  │ web (SPA) │  │ ứng dụng   │  │ + huấn luyện│  │ thực                   │  │
│  └───────────┘  └────────────┘  └─────────────┘  └────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  CSDL quan hệ · Hàng đợi · Kho tệp · Quan trắc (chỉ số, nhật ký, cảnh báo) │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

Bốn đặc điểm ở §3.1.1 c quyết định hình dạng của bối cảnh này, và hai trong bốn đặc
điểm đó thể hiện ngay trên sơ đồ:

* **Mũi tên từ người ký đi vào hệ thống mang chuỗi số, không mang video.** Với đường
  thu qua webcam, video thô không rời máy người dùng.
* **S5 nằm ngoài hệ thống và không có mũi tên đi vào theo chiều điều khiển.** Máy
  phát hành nguồn sự thật không gọi vào hệ thống; hệ thống **kéo** tạo tác đã ký từ
  kho lưu trữ ngoài và **tự xác minh**. Chiều mũi tên này là một quyết định thiết
  kế: nó có nghĩa là hệ thống không phải tin ai cả, chỉ phải tin một khoá công khai
  đã ghi trong mã nguồn.

> ### ▣ HÌNH 3-7 — Bối cảnh hệ thống và các bên liên quan
> **Loại:** sơ đồ ngữ cảnh (context diagram) · **Công cụ:** draw.io
> **Phải thể hiện:** hộp hệ thống ở giữa; bốn tác nhân hệ thống ngoài ranh giới (S1,
> S2, S5, S6) kèm **chiều mũi tên dữ liệu đúng**; sáu tác nhân người P1–P6 bên trái;
> **ranh giới hệ thống vẽ rõ**; nhãn trên mũi tên từ người ký ghi *"chuỗi điểm mốc,
> không phải video"* — đây là điểm phải nhìn thấy được từ hình.
> **Chú thích:** *Hình 3-7: Bối cảnh hệ thống CTU.SignBridge và các bên liên quan.*

### 3.2.2. Tổng quan các phân hệ chức năng

Hệ thống chia thành **sáu phân hệ**. Ranh giới giữa các phân hệ là **thứ đang bị
quản lý**, không phải màn hình — cùng nguyên tắc đã dùng để chia tám nhóm nghiệp vụ
ở §3.1.3.

*Bảng 3-24: Sáu phân hệ chức năng*

| Phân hệ | Quản lý cái gì | Ứng với nhóm use case | Vị trí trong mã nguồn |
|---|---|---|---|
| **PH1 Danh tính và phiên** | Tài khoản, phiên, yếu tố xác thực, chấp thuận văn bản nền tảng | A | `routers/auth`, `verification`, `two_factor`, `legal` |
| **PH2 Tổ chức và phân quyền** | Tổ chức, không gian làm việc, dự án, tư cách thành viên, gán vai | B | `routers/tenants`, `workspaces`; `workspace_admin.py`, `storage/authz_schema.py` |
| **PH3 Danh mục VSL** | Lớp ký hiệu, phương ngữ, vùng miền, hồ sơ nhận dạng, phiên bản danh mục | C (một phần) | `routers/classes`, `vocabulary`; `class_registry.py` |
| **PH4 Thu nhận và xử lý dữ liệu** | Mẫu, phiên thu, bản tải lên thô, người ký, tác vụ nền | C (một phần) | `routers/upload`, `dataset`, `label_sessions`, `jobs`; `processing/` |
| **PH5 Bộ dữ liệu và quản trị dữ liệu** | Bản phát hành, đồng thuận, nguồn gốc, xuất dữ liệu | D | `routers/dataset_exporter`; `export_tasks.py`, `consent.py` |
| **PH6 Toàn vẹn và vận hành** | Nguồn sự thật ký số, đối soát, kiểm toán, quan trắc, sao lưu | E | `sot/`, `routers/sot_admin`, `health`; `scripts/` |

**Ba phân hệ mang đóng góp của luận văn** — PH2, PH4, PH5 — và ba phân hệ còn lại tồn
tại để chúng chạy được. Cách chia này giải thích vì sao §3.5 Thiết kế chức năng dành
nhiều chỗ nhất cho PH2, PH4 và PH5.

**Quan hệ phụ thuộc giữa các phân hệ**, và một tính chất đáng nói:

```
PH1 ──► PH2 ──► PH3 ──► PH4 ──► PH5
 │        │                       ▲
 │        └───────────────────────┘   (phạm vi tổ chức chi phối mọi phân hệ dưới)
 │
 └──────────────────────────────────► PH6 (kiểm toán mọi phân hệ)

PH6 ──► TẤT CẢ   (xác minh nguồn sự thật chạy TRƯỚC mọi phân hệ khác)
```

Chiều mũi tên cuối là chỗ dễ vẽ ngược: PH6 vừa là phân hệ **ở dưới cùng** về mặt
nghiệp vụ, vừa là phân hệ **chạy trước tiên** về mặt thời gian. Một máy không xác
minh được nguồn sự thật thì năm phân hệ còn lại không được phép khởi động — chi tiết
ở §3.3.1.

---

## 3.3. Kiến trúc hệ thống

### 3.3.1. Các thành phần trong kiến trúc hệ thống

Hệ thống đóng gói theo container. Tệp khai báo triển khai định nghĩa **15 dịch vụ**,
trong đó một dịch vụ là container khởi tạo chạy một lần rồi thoát, còn lại **14 dịch
vụ chạy thường trực**.

*Bảng 3-25: Mười lăm dịch vụ trong kiến trúc triển khai*

| Nhóm | Dịch vụ | Vai trò | Vì sao là một dịch vụ riêng |
|---|---|---|---|
| **Biên** | `nginx` | Cổng vào duy nhất; một điểm phục vụ cho cả giao diện lẫn API | Trình duyệt không phải đối mặt với chính sách cùng nguồn; và là chỗ duy nhất biết địa chỉ IP thật của phía gọi (NFR-C6) |
| **Ứng dụng** | `frontend` | Giao diện đơn trang React, phục vụ tĩnh sau khi dựng | Tách vòng đời dựng khỏi vòng đời chạy |
| | `backend` | Dịch vụ API, xử lý toàn bộ nghiệp vụ đồng bộ | — |
| | `realtime_service` | Suy luận thời gian thực | **Vòng đời khác**: giữ mô hình đã nạp trong bộ nhớ, phục vụ kết nối dài |
| **Xử lý nền** | `worker` | Trích đặc trưng, đồng bộ kho ngoài, dựng bản xem trước | Tách công việc dài khỏi vòng đời yêu cầu HTTP |
| | `celery-beat` | Bộ lập lịch: đối soát định kỳ, nhắc hạn, dọn dẹp | Lập lịch là một trách nhiệm khác với thực thi |
| | `trainer` | Huấn luyện mô hình, chiếm GPU | **Cạnh tranh tài nguyên**: một tác vụ huấn luyện chiếm GPU hàng giờ |
| **Dữ liệu** | `postgres` | Cơ sở dữ liệu quan hệ | **Nơi cưỡng chế cách ly** |
| | `redis` | Trung gian truyền tác vụ, bộ đếm hạn mức, danh sách từ chối token | — |
| | `pg-backup` | Sao lưu định kỳ | Sao lưu phải sống sót qua việc khởi động lại ứng dụng |
| **Khởi tạo** | `sot-init` | Kéo và **xác minh chữ ký** danh mục trước khi bất kỳ dịch vụ nào chạy | **Quan hệ thứ tự**, không phải quan hệ gọi |
| **Quan trắc** | `prometheus` | Thu thập chỉ số | — |
| | `grafana` | Biểu đồ và **cảnh báo** | Không có thành phần quản lý cảnh báo riêng — hợp với quy mô một máy chủ |
| | `loki` | Kho nhật ký | — |
| | `promtail` | Thu gom nhật ký từ container | — |

#### Ba lý do tách dịch vụ — để phân biệt với việc tách vì mốt kiến trúc

1. **Cạnh tranh tài nguyên** (`trainer` tách khỏi `worker`): một tác vụ huấn luyện
   chiếm GPU hàng giờ; nếu chung tiến trình, các tác vụ trích đặc trưng ngắn sẽ bị
   bỏ đói. Đây là lý do đo được, không phải lý do thẩm mỹ.
2. **Mô hình vòng đời khác nhau** (`realtime_service` tách khỏi `backend`): dịch vụ
   suy luận giữ mô hình đã nạp trong bộ nhớ và phục vụ kết nối dài; `backend` phục vụ
   yêu cầu ngắn và khởi động lại thường xuyên hơn. Gộp chung nghĩa là mỗi lần triển
   khai bản mới đều đá mọi kết nối suy luận đang chạy.
3. **Quan hệ thứ tự, không phải quan hệ gọi** (`sot-init`): nó phải chạy **trước** và
   **kết thúc** trước khi các dịch vụ khác bắt đầu. Đây không phải một dịch vụ được
   gọi; nó là một điều kiện tiên quyết.

**Ba dịch vụ này KHÔNG tách theo ranh giới nghiệp vụ.** Cần nói rõ để không bị hiểu
nhầm thành kiến trúc vi dịch vụ: `backend` là một khối duy nhất phục vụ cả tám nhóm
nghiệp vụ. Ràng buộc RB-T1 (một máy chủ, 12 GB RAM) loại bỏ phương án tách theo
nghiệp vụ — mỗi vi dịch vụ sẽ mang theo một tiến trình, một bể kết nối và một phần
bộ nhớ nền, và mười khối như vậy không chạy nổi trên máy này.

#### Một chi tiết kiến trúc đáng nói riêng: fail-closed lúc khởi động

`sot-init` thoát với mã lỗi chuyên biệt sẽ **chặn toàn bộ hệ thống khởi động**. Đây
là quyết định có chủ ý, không phải hiệu ứng phụ: **một máy không xác thực được danh
mục thì không được phép phục vụ**.

Thiết kế fail-closed ở đây trả giá bằng **khả năng sẵn sàng** để đổi lấy **khả năng
không phục vụ dữ liệu sai**. Cái giá này là thật và đã trả: một lần khoá ký chưa được
cấp cho máy triển khai mới đã làm cả hệ thống không lên được, và cách xử lý đúng là
cấp khoá chứ không phải nới lỏng phép kiểm. Nguyên tắc phải giữ: **khi một cơ chế
fail-closed gây phiền, đường sửa là làm cho điều kiện được thoả, không phải làm cho
điều kiện biến mất.**

> ### ▣ HÌNH 3-8 — Kiến trúc triển khai
> **Loại:** sơ đồ triển khai UML · **Công cụ:** draw.io
> **Nguồn dựng:** `docker-compose.yml` + `docker-compose.prod.yml` + `docker-compose.gpu.yml`
> **Phải thể hiện:** 15 dịch vụ nhóm theo sáu nhóm ở Bảng 3-25; mạng nội bộ; các
> volume bền vững; **mũi tên phụ thuộc khởi động** từ `sot-init` tới `backend` và
> `worker` vẽ khác kiểu với mũi tên gọi; GPU gắn vào `trainer` và `realtime_service`;
> `nginx` là cổng vào duy nhất từ ngoài; hạn mức bộ nhớ ghi cạnh mỗi container.
> **Chú thích:** *Hình 3-8: Kiến trúc triển khai 15 dịch vụ container.*

### 3.3.2. Quá trình tương tác giữa các thành phần

Trình bày hai luồng tương tác, vì chúng bộc lộ hai loại quyết định thiết kế khác nhau.

#### a. Luồng trục chính — thu một mẫu qua webcam

Chọn luồng này vì nó chạm vào gần như mọi thành phần.

```
Trình duyệt              Backend        Redis      Worker     Postgres   Kho ngoài
    │                       │             │          │           │           │
 1  │ trích điểm mốc        │             │          │           │           │
    │ (WebAssembly, tại máy)│             │          │           │           │
 2  │──── POST mẫu ────────►│             │          │           │           │
 3  │                       │─ mở phạm vi tổ chức (SET LOCAL) ──►│           │
 4  │                       │─ kiểm đồng thuận + hạn mức ───────►│           │
 5  │                       │─ ghi bản ghi mẫu (pending) ───────►│           │
 6  │                       │── đẩy tác vụ►│          │           │           │
 7  │◄─── trả mã tác vụ ────│             │          │           │           │
    │        ╌╌╌╌╌╌╌╌╌╌ RANH GIỚI ĐỒNG BỘ / BẤT ĐỒNG BỘ ╌╌╌╌╌╌╌╌╌╌         │
 8  │                       │             │◄─ lấy ───│           │           │
 9  │                       │             │          │─ ghi kho thô ────────►│
10  │                       │             │          │─ cắt cửa sổ, tăng cường│
11  │                       │             │          │─ chấm chất lượng       │
12  │                       │             │          │─ ghi tệp đặc trưng ───►│
13  │                       │             │          │─ cập nhật (ready) ────►│
14  │◄─ hỏi trạng thái ────►│─────────────────────────────────►│           │
```

Bốn điểm thiết kế lộ ra từ luồng này, và cả bốn đều là quyết định chứ không phải chi
tiết cài đặt:

**Bước 1 quyết định toàn bộ phần còn lại.** Vì trích đặc trưng xảy ra trước bước 2,
thứ đi qua mạng là một mảng số khoảng vài chục KiB thay vì một tệp video vài MiB. Hệ
quả dây chuyền: băng thông thấp hơn, kho lưu trữ nhỏ hơn, và **không có video thô để
rò rỉ**.

**Bước 3 xảy ra trước bước 4.** Phạm vi tổ chức được mở **trước** mọi truy vấn, không
phải sau. Nếu đảo thứ tự, phép kiểm ở bước 4 chạy ngoài phạm vi và sẽ khớp 0 hàng —
rồi mã ứng dụng đọc "0 hàng" thành **"không có gì"** thay vì **"chưa có ngữ cảnh"**.
Đây là cái bẫy đã mắc ba lần trong hai ngày, và nó được phân tích riêng ở §3.4.1 b.

**Bước 7 trả về trước khi bước 8–13 xảy ra.** Người dùng không chờ. Đổi lại, giao
diện **phải** có đường hỏi trạng thái (bước 14) và **phải** xử lý được trạng thái
"đang xử lý" như một trạng thái hợp lệ chứ không phải một lỗi.

**Bước 9 xảy ra trước bước 10.** Bản thô được ghi **trước** mọi bước chuẩn hoá (NFR-R2).
Nếu bước chuẩn hoá có lỗi, dữ liệu gốc vẫn còn để xử lý lại. Thứ tự này là một **ràng
buộc thiết kế**, không phải một chi tiết cài đặt, và nó được kiểm bằng một ca kiểm
thử ghim đúng thứ tự ghi.

> ### ▣ HÌNH 3-9 — Tương tác giữa các thành phần khi thu một mẫu
> **Loại:** sơ đồ tuần tự (sequence diagram) UML
> **Phải thể hiện:** sáu đường đời như sơ đồ trên; **đánh dấu rõ ranh giới đồng bộ /
> bất đồng bộ** ở bước 7; khối `SET LOCAL` ở bước 3 vẽ thành một **khung `ref`** để
> nhấn rằng đó là một khối quản lý ngữ cảnh duy nhất; vòng lặp hỏi trạng thái ở bước
> 14; nhánh ngoại lệ "mất mạng ở bước 2 → giữ dữ liệu ở trình duyệt".
> **Chú thích:** *Hình 3-9: Trình tự tương tác khi thu một mẫu qua webcam.*

#### b. Luồng khởi động — xác minh nguồn sự thật trước khi phục vụ

Chọn luồng này vì nó bộc lộ một loại quan hệ khác hẳn: quan hệ **thứ tự**, không
phải quan hệ gọi.

```
docker compose up
       │
       ├─► sot-init  ─┬─► kéo bản công bố từ kho lưu trữ ngoài
       │              ├─► tính lại mã băm từng tệp, đối chiếu bản kê    ─── lệch ⇒ EXIT 4
       │              ├─► kiểm chữ ký Ed25519 phủ bản kê                ─── hỏng ⇒ EXIT 4
       │              ├─► tra khoá ký trong danh sách tin cậy           ─── lạ  ⇒ EXIT 4
       │              └─► hợp nhất vào CSDL theo nguyên tắc CHỈ ĐIỀN
       │                                    │
       │                              exit 0 │  exit 4
       │                                    ▼      ▼
       └─────────────────► backend, worker,  │   TOÀN BỘ STACK KHÔNG LÊN
                           trainer khởi động ◄┘
```

Hai điểm thiết kế:

**Ba điểm DỪNG là ba phép kiểm khác nhau, không thay thế được cho nhau.** Toàn vẹn
(mã băm khớp), tính hợp lệ mật mã (chữ ký đúng), và **thẩm quyền** (khoá nào ký).
Điểm thứ ba là chỗ dễ bỏ sót nhất — phân tích ở §3.3.3.4.

**Hợp nhất là chỉ-điền, không-xoá.** Máy triển khai bảo đảm cơ sở dữ liệu của mình là
**tập cha** của bản công bố: thêm cái thiếu, không bao giờ xoá. Lý do: hai máy triển
khai có thể có dữ liệu riêng hợp lệ mà bản công bố chưa biết, và một phép hợp nhất
có xoá sẽ im lặng phá dữ liệu đó.

### 3.3.3. Cơ sở thiết kế ứng dụng

Bốn quyết định lớn định hình kiến trúc. Mỗi quyết định trình bày theo cùng một khuôn:
các phương án đã cân nhắc, tiêu chí, lựa chọn, và **cái giá phải trả**.

#### 3.3.3.1. Kiến trúc đa thuê bao và cô lập dữ liệu

##### a. Chọn mô hình cách ly

*Bảng 3-26: So sánh ba mô hình cách ly dữ liệu đa tổ chức*

| Tiêu chí | Mỗi tổ chức một CSDL riêng | Mỗi tổ chức một lược đồ riêng | **Dùng chung lược đồ + cưỡng chế theo hàng** |
|---|---|---|---|
| Mức cách ly | Cao nhất | Cao | Trung bình – cao |
| Chi phí tài nguyên | Rất cao (n bản CSDL) | Cao | **Thấp** |
| Thay đổi cấu trúc | Phải chạy trên n bản | Phải chạy trên n lược đồ | **Một lần** |
| Truy vấn xuyên tổ chức (thống kê nền tảng) | Rất khó | Khó | **Dễ, qua một phạm vi riêng** |
| Rủi ro chính | Vận hành không xuể | Số lược đồ bùng nổ | **Rò dữ liệu nếu điều kiện lọc sót** |
| Phù hợp với RB-T1 (một máy chủ, 12 GB) | Không | Khó | **Có** |

**Chọn: dùng chung lược đồ, cưỡng chế theo hàng.** Ràng buộc RB-T1 loại hai phương
án đầu — một máy chủ 12 GB RAM không chạy nổi n bản cơ sở dữ liệu.

**Cái giá phải trả, nói thẳng:** lựa chọn này mang theo đúng rủi ro nguy hiểm nhất —
**rò dữ liệu khi điều kiện lọc sót**, và rò một cách im lặng. Toàn bộ thiết kế bốn
tầng dưới đây tồn tại để bịt rủi ro đó, và đó là lý do nó là đóng góp lõi của luận
văn chứ không phải một mục kỹ thuật phụ.

##### b. Bốn tầng cưỡng chế cách ly

Bốn tầng, mỗi tầng bịt **một lối vòng mà ba tầng còn lại để hở**. Đây là điểm mấu
chốt: bốn tầng này không phải bốn lớp phòng thủ giống nhau chồng lên nhau cho chắc;
chúng bịt bốn lỗ khác nhau, và bỏ bất kỳ tầng nào cũng để lại một lỗ cụ thể.

**Tầng 1 — Cột phân biệt.**
Mỗi bảng chịu ranh giới tổ chức mang một cột `tenant_id`. Cần thiết, nhưng một mình
thì **chỉ là siêu dữ liệu**: không có gì buộc truy vấn phải dùng nó.
*Lối vòng còn hở:* mọi truy vấn quên điều kiện lọc.

**Tầng 2 — Chính sách bảo mật mức hàng.**
Chính sách so sánh cột phân biệt với một biến ngữ cảnh của phiên. Toàn bộ 35 chính
sách trong hệ thống dùng **cùng một khuôn**:

```sql
(current_setting('app.system_scope', true) = 'on')
OR (tenant_id = current_setting('app.tenant_id', true))
```

Chi tiết quyết định nằm ở **tham số thứ hai `true`** — dạng đọc "cho phép thiếu". Khi
biến chưa được gán, hàm trả về NULL thay vì ném lỗi, nên phép so sánh cho ra NULL.
**NULL không phải TRUE**, nên hàng không lọt qua chính sách. Đó chính là cơ chế làm
mệnh đề *"không khai báo tổ chức ⇒ 0 hàng"* thành đúng.

Nếu dùng dạng đọc "bắt buộc có", biến chưa gán sẽ ném lỗi — nghe có vẻ an toàn hơn,
nhưng thực tế biến **mọi công việc nền hợp lệ** thành lỗi hệ thống, và áp lực vận
hành sẽ đẩy người ta tới chỗ tắt chính sách. **Fail-closed im lặng ở đây an toàn hơn
fail-closed ồn ào**, đúng vì lý do con người chứ không vì lý do kỹ thuật.
*Lối vòng còn hở:* biến ngữ cảnh dính lại trên kết nối và rò sang yêu cầu kế tiếp.

**Tầng 3 — Phạm vi giao dịch.**
Biến ngữ cảnh được gán bằng lệnh **giới hạn trong giao dịch** (`SET LOCAL`), trong
một khối quản lý ngữ cảnh **duy nhất** của mã nguồn. Lệnh gán thường (không giới hạn
giao dịch) sẽ **dính lại trên kết nối** và rò sang yêu cầu kế tiếp khi dùng bể kết
nối. Đây là lỗi kinh điển của cặp *"bảo mật mức hàng cộng bể kết nối"*, và nó **không
sinh ra thông báo lỗi nào** — chỉ có một người dùng xui xẻo đọc được dữ liệu của
người khác.
*Lối vòng còn hở:* ứng dụng tự tắt chính sách.

**Tầng 4 — Tách vai cơ sở dữ liệu.**
Vai chạy của ứng dụng (`voya_app`) chỉ có quyền thao tác dữ liệu; quyền thay đổi cấu
trúc nằm ở một vai riêng. Lý do rất cụ thể: **lệnh vô hiệu hoá chính sách bảo mật
mức hàng là một lệnh thay đổi cấu trúc**. Một vai vừa ghi được dữ liệu vừa chạy được
lệnh cấu trúc thì **tự gỡ được vòng vây của chính nó**, và bảo đảm biến thành lời
khuyên.

Cần nói thêm hai điều mà nhiều tài liệu bỏ qua:

* Chỉ bật cờ *"cưỡng chế cả với chủ sở hữu bảng"* là **không đủ**, vì cơ sở dữ liệu
  miễn trừ chính sách **vô điều kiện** cho vai siêu người dùng. Vai chạy của ứng dụng
  vì thế **không được là siêu người dùng**, và điều đó phải kiểm được bằng truy vấn
  siêu dữ liệu chứ không bằng niềm tin.
* Vai chạy cũng **không được là chủ sở hữu bảng**, vì chủ sở hữu có thể tự bật/tắt
  cờ cưỡng chế trên bảng của mình.

##### c. Biến ngữ cảnh thứ hai, và vì sao nó phải là một biến riêng

Công việc nền hợp lệ **xuyên tổ chức** vẫn tồn tại: đối soát dữ liệu lúc khởi động,
tiến trình đọc nguồn sự thật, bảo trì theo lịch. Nó được phục vụ bằng một biến ngữ
cảnh **thứ hai** (`app.system_scope`), tách hẳn khỏi biến tổ chức.

Đây là một quyết định thiết kế có chủ ý, không phải một sự tình cờ. Lý do:

> Nếu *"hành động thay mọi tổ chức"* là một **giá trị** của cùng biến tổ chức — ví dụ
> `tenant_id = '*'` hay `tenant_id = 'system'` — thì **một lỗi gõ sai tên tổ chức có
> thể vô tình sinh ra đặc quyền đó**. Tách thành một biến riêng làm điều đó **không
> thể xảy ra do nhầm lẫn**.

Biến này còn được gia cố thêm: nó chỉ nhận đúng chuỗi `'on'`, không nhận `'true'`,
`'1'` hay bất kỳ giá trị nào khác. Một giá trị lạ được đọc thành "không bật".

##### d. Cách ly ở mặt phẳng tệp — một tầng khác, với mức bảo đảm khác

Bốn tầng trên chỉ áp cho tài nguyên **nằm trong cơ sở dữ liệu**. Tệp đặc trưng nằm
trên hệ tệp, và ở đó cách ly dựa vào **cấu trúc thư mục** cộng kiểm tra ở tầng ứng
dụng — mức bảo đảm **thấp hơn**, và phải phát biểu đúng như vậy.

Bố cục thư mục có một tính chất bất đối xứng, và nó đã sinh ra một lỗi thật đáng ghi
lại vì nó là ví dụ điển hình của **"phạm vi được truyền đúng nhưng vẫn rò"**:

```
tổ chức mồi (default)  →  FEATURES_ROOT/
tổ chức khác (iso_a)   →  FEATURES_ROOT/_tenants/iso_a/
```

Bất đối xứng này có lý do tốt: đổi bố cục của tổ chức mồi thì hai mươi nơi gọi phải
mọc thêm nhánh "mới-rồi-cũ", và hàng nghìn tệp sẵn có nằm sau nhánh đó vĩnh viễn.
Nhưng nó tạo ra một hệ quả mà **mọi hàm đi bộ trên cây đều thừa hưởng**:

$$\text{root}(\texttt{iso\_a}) \subset \text{root}(\texttt{default})$$

Nên một lượt quét đệ quy từ thư mục của tổ chức mồi **đi xuyên vào dữ liệu của mọi tổ
chức khác**. Phạm vi vẫn được truyền đúng, hàm vẫn nhận đúng tổ chức — chỉ là phạm vi
của một tổ chức lại **chứa** phạm vi của những tổ chức còn lại.

Đo ngày 17/08/2026 trên ba nơi gọi:

| Nơi gọi | Loại | Trạng thái trước khi vá | Hậu quả đo được |
|---|---|---|---|
| Xoá tệp của một tổ chức | phá huỷ | **có chốt chặn**, kèm ghi chú nêu đúng cái bẫy này | — |
| Gộp tệp cho bản xuất | đọc | **không có chốt chặn** | bản xuất của tổ chức mồi mang theo tệp của mọi tổ chức khác |
| Tính dung lượng để kế toán | đọc | **không có chốt chặn** | tổ chức mồi bị tính 7 MB trong khi thực sở hữu 1 MB |

**Bài học thiết kế, và nó khái quát hơn lỗi cụ thể:** bất đối xứng đã được hiểu đúng
**một lần**, trên đường phá huỷ, và **không được mang sang** hai đường đọc. Bản vá vì
thế không phải là thêm một câu điều kiện vào hai chỗ, mà là **một hàm duyệt dùng
chung duy nhất** — vì *một chốt chặn viết riêng cho từng nơi gọi là một chốt chặn mà
nơi gọi thứ tư sẽ không biết là có tồn tại*. Một ca kiểm thử riêng thất bại nếu một
nơi gọi mới đi bộ thẳng trên thư mục gốc.

> ### ▣ HÌNH 3-10 — Bốn tầng cưỡng chế cách ly tổ chức
> **Loại:** sơ đồ tầng
> **Phải thể hiện:** bốn tầng xếp chồng; cạnh mỗi tầng ghi **lối vòng mà nó bịt**
> (tầng 1: không bịt gì; tầng 2: truy vấn quên lọc; tầng 3: rò ngữ cảnh qua bể kết
> nối; tầng 4: ứng dụng tự tắt chính sách); một mũi tên "tấn công" thử xuyên qua và
> bị chặn ở từng tầng; **mặt phẳng tệp vẽ tách ra bên cạnh** với nhãn ghi rõ mức bảo
> đảm thấp hơn — đây là điểm phải nhìn thấy được từ hình.
> **Chú thích:** *Hình 3-10: Bốn tầng cưỡng chế cách ly, lối vòng mà mỗi tầng bịt, và
> mặt phẳng tệp với mức bảo đảm khác.*

#### 3.3.3.2. Phân quyền theo phạm vi

##### a. Bốn cấp phạm vi và cách mô hình hoá

Mô hình phân quyền ban đầu có nhiều bảng rời rạc cho từng loại vai. Bản hiện tại gộp
về **một mô hình gán vai theo phạm vi**, tách hai sự thật khác nhau:

```
memberships       : anh THUỘC VỀ đâu
                    scope_level ∈ { SYSTEM, TENANT, WORKSPACE, PROJECT }
                    + tự trỏ (parent_membership_id, user_id)

role_assignments  : anh LÀM ĐƯỢC GÌ ở đó
                    trỏ vào membership_id — KHÔNG trỏ vào cặp (người, phạm vi)
```

**Vì sao `role_assignments` trỏ vào membership chứ không vào cặp (người, phạm vi):**
vì phạm vi của một lần gán vai được **kế thừa** từ membership, nên nó không bị lưu
lại hai chỗ và không thể lệch nhau. Khoá ngoại ở đây là **khoá ghép**
`(membership_id, user_id)`, và đó là điều đáng nói: với khoá đơn, một bản ghi gán vai
cho người A dựa trên tư cách thành viên của người B là **hợp lệ về mặt cơ sở dữ
liệu**. Khoá ghép làm điều đó bất khả thi ở tầng ràng buộc.

Ràng buộc *"membership cấp dưới phải có membership cấp trên"* được cưỡng chế bằng
chính khoá ngoại **tự trỏ** cộng một trigger (`ct_memberships_chain`) — không bằng
kiểm tra ở ứng dụng.

##### b. Bảng thành viên tổ chức là một khung nhìn

Hệ quả đáng chú ý của việc gộp: bảng thành viên tổ chức **không còn là một bảng**, mà
là một **khung nhìn** trên lát cắt `scope_level = 'TENANT'` của bảng `memberships`.
Điều này giữ được toàn bộ mã cũ đọc theo tên bảng đó, đồng thời đưa mọi tư cách thành
viên về một chỗ.

**Cái giá phải trả rất cụ thể:** khung nhìn **không tạo chỉ mục được** và **không
nhận mệnh đề xử lý xung đột**, nên **mọi đường ghi phải sửa để ghi vào bảng gốc**.
Khung nhìn được khai báo `security_invoker`, nghĩa là nó chạy với quyền của người
gọi chứ không của người tạo — nếu không, nó sẽ trở thành một lối vòng qua chính sách
cách ly.

##### c. Trạng thái thật của bốn cấp — phải phát biểu đúng

Đây là chỗ dễ overclaim nhất trong cả chương, nên phát biểu được viết ra thành câu
chuẩn để dùng nhất quán ở mọi nơi trong quyển.

*Bảng 3-27: Trạng thái cưỡng chế theo từng cấp phạm vi*

| Cấp | Có bảng | Có bề mặt API | Dữ liệu phân vùng theo cấp này | Quyết định quyền lúc chạy | Chứng minh được từ ngoài |
|---|:--:|:--:|:--:|:--:|---|
| Hệ thống | ✔ | ✔ | — (không áp dụng) | ✔ | **Có** |
| Tổ chức | ✔ | ✔ | ✔ (35/36 bảng mang `tenant_id` bật chính sách; ngoại lệ `tenant_purges`) | ✔ | **Có** — Ch.4 §5.2 |
| Không gian làm việc | ✔ | ✔ *(14 điểm cuối)* | ✘ | ✘ *(chế độ `shadow`)* | **Chưa** |
| Dự án | ✔ | ✔ | ✘ | ✘ *(chế độ `shadow`)* | **Chưa** |

**Câu phát biểu chuẩn, dùng nguyên văn ở mọi chỗ:**

> *Kiến trúc phân quyền hỗ trợ bốn cấp phạm vi, và cả bốn cấp đều có cấu trúc dữ liệu
> cùng bề mặt vận hành. Cưỡng chế lúc chạy được **chứng minh** ở cấp hệ thống và cấp
> tổ chức. Hai cấp dưới hiện **chưa phân vùng dữ liệu** và **chưa đổi được kết quả
> của một phép kiểm quyền**, vì bộ máy phân quyền mới đang chạy ở chế độ song song
> quan sát (`shadow`), trong khi bên quyết định lúc chạy vẫn là hệ hai phạm vi cũ.*

Số liệu đo ngày **18/08/2026**: hệ thống có **2 không gian làm việc**, **3 dự án** và
**3 tenant** (2 tổ chức thật + 1 tenant cộng đồng dự trữ); tư cách thành viên đã trải
đủ ba cấp (10 cấp tổ chức, 10 cấp không gian làm việc, 10 cấp dự án). Nhưng **3.860
dòng mẫu và 63 lớp vẫn không mang định danh dự án**, và bảng hạn mức phân bổ theo dự
án có **0 dòng**. Cây `Tổ chức ⊃ Không gian làm việc ⊃ Dự án` tồn tại ở tầng phân quyền
nhưng chưa phân vùng dữ liệu — nói khác đi là overclaim, và là loại overclaim mà một
câu truy vấn mô tả bảng đủ để bác bỏ.

##### d. Bốn bất biến phân quyền cưỡng chế ở tầng cơ sở dữ liệu

Bốn trigger dưới đây là chỗ mô hình phân quyền trở thành **bảo đảm** thay vì **quy
ước**. Chi tiết ở §3.4.3 d; nêu ở đây để thấy chúng thuộc về thiết kế phân quyền chứ
không phải một chi tiết lược đồ:

| Bất biến | Cưỡng chế bằng |
|---|---|
| Membership cấp dưới phải có membership cấp trên | `ct_memberships_chain` |
| Lần gán vai phải khớp phạm vi của membership | `ct_role_assignments_scope` |
| Vai không cấp được quyền vượt cấp của chính nó | `ct_role_permissions_dominance` |
| Vai nền tảng và vai riêng của tổ chức không lẫn nhau | `ct_roles_tenant_type` |

**Một quyết định ngược trực giác, cần giải thích:** bảng `role_assignments` **không
mang cột `tenant_id`** và **không bật chính sách cách ly**. Thoạt nhìn đây là một lỗ
hổng. Thực ra nó là hệ quả của mô hình: một bản ghi gán vai không có phạm vi của
riêng nó — phạm vi của nó **là** phạm vi của membership mà nó trỏ tới, và bảng
`memberships` thì có `tenant_id` và **có** bật chính sách. Thêm `tenant_id` vào
`role_assignments` sẽ tạo ra hai nguồn sự thật cho cùng một dữ kiện, và hai nguồn thì
lệch được.

Nhưng phải nói kèm giới hạn: điều này có nghĩa là **cách ly của bảng gán vai là cách
ly gián tiếp**, phụ thuộc vào việc mọi truy vấn đều đi qua `memberships`. Đây là một
điểm yếu đã biết, và nó nằm trong danh sách hạn chế ở §3.7.

#### 3.3.3.3. Tổ chức xử lý và lưu trữ

##### a. Chọn cách biểu diễn dữ liệu

*Bảng 3-28: So sánh phương án biểu diễn dữ liệu*

| Tiêu chí | Video thô | Khung ảnh đã trích | **Chuỗi điểm mốc bàn tay** |
|---|---|---|---|
| Dung lượng mỗi mẫu | MiB | trăm KiB | **hàng chục KiB** |
| Video rời khỏi máy người dùng | Bắt buộc | Bắt buộc | **Không bắt buộc** |
| Thông tin giữ lại | Đầy đủ | Đầy đủ theo khung | Chỉ hình học bàn tay |
| Trích lại đặc trưng khác về sau | Được | Được | **Không** |
| Chi phí tính toán ở máy chủ | Cao | Trung bình | **Thấp** (đã trích ở máy khách) |
| Rủi ro lộ diện người tham gia | Cao | Cao | **Thấp hơn** — nhưng *không phải* ẩn danh |

**Chọn: chuỗi điểm mốc bàn tay**, 126 chiều mỗi khung (21 điểm mốc × 3 toạ độ × 2 bàn
tay), lưu ở định dạng mảng số có nén.

**Hai điều phải nói thẳng kèm lựa chọn này:**

* **Đây là một phép biến đổi có mất mát, và mất mát là một chiều.** Không lấy lại
  được video, nên cũng không trích lại được loại đặc trưng khác về sau. Nếu một
  nghiên cứu tương lai cần biểu cảm khuôn mặt hay tư thế toàn thân, dữ liệu đã thu
  **không phục vụ được** — phải thu lại. Đây là hệ quả trực tiếp của RB-D5 và RB-D6,
  và nó là cái giá thật của quyết định về quyền riêng tư.
* **Không được lập luận "điểm mốc là ẩn danh".** Chuỗi điểm mốc không mang hình ảnh
  khuôn mặt, nhưng nó vẫn là dữ liệu **về một con người cụ thể**, và vẫn có thể quy
  về người đó khi ghép với siêu dữ liệu khác. Thuật ngữ dùng thống nhất trong quyển
  là **"không lộ diện"**, không phải "ẩn danh".

##### b. Chọn cách tổ chức các bước xử lý

*Bảng 3-29: So sánh phương án tổ chức bước xử lý*

| Tiêu chí | Xử lý đồng bộ trong yêu cầu | Mỗi bước một tác vụ nền | **Gộp các bước vào một tác vụ nền** |
|---|---|---|---|
| Người dùng phải chờ | Có | Không | **Không** |
| Số lần chạm hàng đợi | 0 | Nhiều | **1** |
| Chạy lại từng bước riêng | — | Được | **Không** — chạy lại cả cụm |
| Trạng thái trung gian phải lưu | Không | Nhiều | **Ít** |
| Độ phức tạp vận hành | Thấp | **Cao** | Trung bình |

**Chọn: gộp các bước vào một tác vụ nền.** Đánh đổi được chấp nhận có ý thức: mất khả
năng chạy lại từng bước riêng, đổi lấy việc không phải quản lý một chuỗi trạng thái
trung gian. Với quy mô hiện tại — một máy chủ, một hàng đợi — chi phí vận hành của
phương án giữa lớn hơn giá trị nó mang lại.

**Giới hạn phải ghi:** vì cả cụm chạy lại cùng nhau, **tính lũy đẳng phải bảo đảm ở
mức cụm**. Hiện tại **chưa bảo đảm đồng đều**: bước ghi tệp đặc trưng chạy lại an
toàn, nhưng bước tải lên kho ngoài có thể tạo bản trùng. Đây là hạn chế đã biết, nêu
lại ở §3.7 và ở Chương 4.

##### c. Hai mặt phẳng lưu trữ — một cấu hình không lý tưởng, phải nói thẳng

Ràng buộc RB-D2 để lại một cấu hình di sản: **nguồn sự thật của kho mẫu là một tệp
CSV**, còn cơ sở dữ liệu quan hệ là **bản sao để truy vấn**. Đây là di sản từ hệ
thống tiền thân, không phải một thiết kế được chọn.

*Bảng 3-30: Rủi ro của hai mặt phẳng lưu trữ và cách xử lý*

| Rủi ro | Cách xử lý | Mức bảo đảm |
|---|---|---|
| Hai mặt phẳng lệch nhau | Tác vụ đối soát định kỳ, chiều CSV → CSDL | Trung bình — phát hiện được, sửa được |
| Một mẫu có trong CSDL nhưng thiếu ở CSV | Tác vụ đối soát chiều ngược, **chỉ để sửa một lượt ghi hỏng giữa chừng** (§3.1.4 g, Bất biến 4) | Trung bình |
| Đường ghi tệp **không** chịu chính sách cách ly | Cấu trúc thư mục theo tổ chức + một hàm duyệt dùng chung có chốt chặn (§3.3.3.1 d) | **Thấp hơn** mặt phẳng CSDL — phải phát biểu đúng như vậy |
| Kiểm thử ghi nhầm vào dữ liệu thật | Bộ kiểm thử từng ghi vào tệp nguồn sự thật thật; đã bổ sung chốt chặn hai lớp (§3.6.3) | Cao |

**Phát biểu đúng mức về cách ly, phải giữ nhất quán ở mọi nơi trong quyển:** cách ly
được **cưỡng chế ở tầng cơ sở dữ liệu** cho mọi tài nguyên nằm trong cơ sở dữ liệu;
với tài nguyên nằm trên hệ tệp, cách ly dựa vào **cấu trúc lưu trữ và kiểm tra ở tầng
ứng dụng**. Phép đo ở Chương 4 đo **cả hai mặt phẳng**, và đó là lý do nó được gọi là
phép đo *xuyên kho*.

#### 3.3.3.4. Phiên bản, provenance và toàn vẹn

##### a. Chọn mô hình thẩm quyền ký

*Bảng 3-31: So sánh phương án thẩm quyền ký*

| Tiêu chí | Không ký, tin vào kho lưu trữ | Mọi máy đều ký được | **Một máy phát hành duy nhất giữ khoá ký** |
|---|---|---|---|
| Phát hiện sửa đổi | Không | Có | **Có** |
| Xác định được ai sửa | Không | Có | **Có** |
| Rủi ro khoá bị lộ | — | **n lần** | **1 lần** |
| Hợp nhất hai máy | Ghi đè lẫn nhau | Xung đột | **Một chiều, chỉ điền** |
| Chi phí vận hành | Thấp | Cao | Trung bình |

**Chọn: một máy phát hành duy nhất.** Máy đó giữ khoá riêng Ed25519 và công bố các
phiên bản bất biến của danh mục và lược đồ. Máy chủ và các máy triển khai khác **chỉ
đọc**.

##### b. Hợp đồng xác minh có bốn vế — và chúng không thay thế được cho nhau

```
Tạo tác hợp lệ  =  Toàn vẹn
                 ∧ Chữ ký hợp lệ về mật mã
                 ∧ Người ký được tin cậy
                 ∧ Chính sách phiên bản hợp lệ
```

**Vế thứ ba là chỗ dễ bỏ sót nhất**, và đáng phân tích riêng: một kẻ tấn công dựng dữ
liệu khác, tính mã băm đúng, viết bản kê đúng, rồi **tự ký bằng khoá của hắn**. Chữ
ký ấy **hợp lệ về mật mã**. Nếu hệ thống chỉ hỏi *"chữ ký có hợp lệ không"* mà không
hỏi *"hợp lệ theo khoá nào"* thì **toàn vẹn đúng nhưng thẩm quyền sai**.

Cài đặt ở đây vì thế trả về **tên khoá đã đăng ký** thay vì một giá trị đúng/sai, nên
*"ai ký"* là một phần của kết quả xác minh chứ không phải một câu hỏi phụ.

##### c. Ba tính chất đạt được, phát biểu tách bạch

| Tính chất | Nghĩa | Trạng thái |
|---|---|---|
| **Toàn vẹn** | Sửa được nhưng **không giấu được** | **Đạt** — bản kê băm SHA-256 toàn bộ tệp, chữ ký phủ bản kê |
| **Xác thực nguồn** | Biết **ai** ký, không chỉ biết "có chữ ký hợp lệ" | **Đạt** — hàm xác minh trả về tên khoá đã đăng ký |
| **Đơn điệu phiên bản** | Bản mới **không bị bản cũ ghi đè lùi** | **Chưa cưỡng chế** — xem dưới |

**Vế thứ tư là giới hạn đã biết.** Hệ thống chấp nhận một bản công bố có số hiệu phiên
bản **thấp hơn** bản đang dùng. Tài nguyên mới hơn không bị xoá — nguyên tắc chỉ-điền
bảo vệ điều đó — nhưng giá trị dùng chung **bị ghi đè lùi**. Bằng chứng và đánh giá ở
Chương 4 §5.5.

##### d. Ba mức "bất biến" — không được gộp làm một

Trong hệ thống có ba thứ được gọi là "bất biến", và chúng có **ba mức bảo đảm khác
nhau**. Gộp chúng vào một câu là một lỗi phát biểu, không phải một cách viết gọn.

*Bảng 3-32: Ba mức bất biến và cơ chế cưỡng chế*

| Đối tượng | Cưỡng chế bằng | Mức bảo đảm | Phá được bằng cách nào |
|---|---|---|---|
| **Văn bản pháp lý** đã công bố | **Trigger ở tầng CSDL** (`trg_legal_documents_freeze`) | **Cao nhất** | Chỉ bằng quyền thay đổi cấu trúc — mà vai ứng dụng không có |
| **Phiên bản danh mục** (`registry_versions`) | **Quy ước ở tầng ứng dụng** — **không có trigger** | Trung bình | Một câu lệnh cập nhật viết sai |
| **Tạo tác nguồn sự thật** đã ký | **Mật mã** (mã băm + chữ ký) | Cao — nhưng chỉ **phát hiện**, không **ngăn** | Sửa được, nhưng không giấu được |

Phân biệt này quan trọng vì toàn bộ lập luận về khả năng **tái lập thí nghiệm** dựa
vào tính bất biến của `registry_versions`, mà đó lại là mức bảo đảm **yếu nhất** trong
ba mức. Phát biểu đúng: *"phiên bản danh mục là bất biến theo quy ước ở tầng ứng dụng;
tính bất biến này chưa được cưỡng chế bằng ràng buộc cơ sở dữ liệu như với văn bản
pháp lý."*

##### e. Chuỗi nguồn gốc, và mắt xích yếu nhất của nó

Mô hình dữ liệu bảo toàn nguồn gốc bằng cách tách ba loại thứ vốn hay bị gộp: **đối
tượng** được quản lý, **hoạt động** sinh ra chúng, và **chủ thể** gắn với hoạt động
đó. Trên đường thu, điều này có nghĩa là người ký, tài khoản vận hành, phiên thu, bản
tải lên thô, biểu diễn dẫn xuất và tư cách thành viên trong một bản phát hành đều
được mô hình hoá thành **quan hệ tường minh**, thay vì bị dồn vào một trường "người
tạo" duy nhất.

```
Người ký → Phiên thu → Mẫu → Bản tải lên thô / Biểu diễn dẫn xuất → Bản phát hành
   ▲                                                                      │
   └──────────────── đồng thuận chi phối ─────────────────────────────────┘
```

Luận văn **không tuyên bố** hiện thực đầy đủ mô hình dữ liệu nguồn gốc chuẩn W3C
PROV, cũng không sinh tài liệu hay giao diện trao đổi theo chuẩn đó. Điều được khẳng
định hẹp hơn: **mỗi mắt xích trong chuỗi trên là một quan hệ truy vấn được**, nên câu
hỏi *"mẫu này từ đâu ra, qua bước nào, do ai"* trả lời được bằng truy vấn chứ không
bằng suy đoán.

**Mắt xích yếu nhất phải nêu đích danh.** Quan hệ giữa mẫu và người ký chỉ thiết lập
được đáng tin **tại thời điểm thu**. Đo trên 3.860 dòng, tái xác minh ngày 18/08/2026:

| Cột quy kết | Có giá trị | Là ai |
|---|---:|---|
| `user_id` | 3.860 (100 %) | định danh nội bộ của lượt thu — **hiện vật lịch sử**, có từ trước khi hệ thống có tài khoản |
| `auth_user_id` | 3.694 (95,7 %) | **tài khoản đã đăng nhập** lúc thu |
| `username` | 1.169 (30,3 %) | tên hiển thị chép lại tại thời điểm thu — **hiện vật lịch sử** |
| `signer_id` | **1.674 (43,4 %)** | **người ký** — chủ thể dữ liệu |

Chỉ `auth_user_id` và `signer_id` là hai vai nghiệp vụ khác nhau và không được gộp.
Với **56,6 %** số dòng còn lại, chuỗi nguồn gốc **đứt ở đúng vị trí không dựng lại
được**: không có gì trong dữ liệu cho phép suy ra ai là người ký, và một phép suy
đoán ở đây sẽ tạo ra bằng chứng giả.

Con số 1.674 không ngẫu nhiên: nó **đúng bằng** số mẫu của một chiến dịch thu duy
nhất. Nghĩa là quy kết chủ thể dữ liệu chỉ được thiết lập cho đúng một chiến dịch —
một kết quả nghiên cứu về khoảng cách giữa mô hình đúng và dữ liệu lịch sử, không
phải một khiếm khuyết cần giấu.

#### 3.3.3.5. Năm nguyên lý thiết kế xuyên suốt

Năm nguyên lý dưới đây rút ra từ quá trình xây dựng, và chúng lặp lại ở nhiều chỗ
trong hệ thống. Chúng được nêu tách ra vì mỗi nguyên lý đã ngăn hoặc đã phát hiện một
lỗi thật.

1. **Thiếu ngữ cảnh thì dừng, không đoán.** Áp cho cách ly (không có tổ chức ⇒ 0
   hàng), cho danh mục (thiếu dữ liệu ⇒ dừng), cho nguồn sự thật (không xác minh được
   ⇒ không khởi động), cho nhật ký kiểm toán (không có phạm vi ⇒ **từ chối ghi**).
2. **Kế thừa lúc khởi tạo khác với rơi về lúc chạy.** Sao chép danh mục hệ thống vào
   một tổ chức mới là **kế thừa** — xảy ra một lần, kết quả thuộc về tổ chức đó. Đọc
   danh mục hệ thống khi tổ chức thiếu dữ liệu là **rơi về** — và bị cấm (RB-D7). Hai
   thứ trông giống nhau trên sơ đồ nhưng khác nhau hoàn toàn về hệ quả.
3. **Ngoại lệ phải là một phạm vi, không phải một lối đi vòng.** Công việc nền xuyên
   tổ chức cần một phạm vi **được đặt tên và kiểm được**, chứ không phải một giá trị
   đặc biệt lẫn trong dữ liệu thường.
4. **Tổng hợp cũng có thể rò rỉ.** Một điểm cuối trả về "số mẫu toàn nền tảng" không
   trả dữ liệu của ai cả — nhưng nếu một tổ chức chỉ có một thành viên thì con số tổng
   hợp ấy nói về đúng người đó. Mọi điểm cuối thống kê phải đi qua cùng cơ chế phạm vi.
5. **Không có đường quay ngược từ công khai vào riêng tư.** Dữ liệu đã công bố sang
   mặt phẳng dùng chung thì không rút lại được bằng một nút bấm. Vì thế đường công bố
   phải là một hành động **tường minh, có xác thực lại, và có bản ghi**.

---

## 3.4. Thiết kế dữ liệu

### 3.4.1. Mô hình dữ liệu

#### a. Quy mô và cách trình bày

Lược đồ hiện có **59 bảng và 1 khung nhìn**, với **123 khoá ngoại**, **35 chính sách
bảo mật mức hàng** và **6 trigger**. Số liệu đo trực tiếp trên cơ sở dữ liệu `signdb`
đang chạy ngày **18/08/2026**, dựng từ danh mục hệ thống (`pg_class`, `pg_constraint`,
`pg_policy`, `pg_trigger`) — không suy đoán từ mã nguồn. Phiên bản lược đồ: **5**.

**Một đính chính cần ghi lại, vì nó là bài học về phương pháp:** các bản nháp trước
của tài liệu này ghi "80+ bảng". Con số đó sai, và nó sai vì đếm gộp một cơ sở dữ
liệu **bản sao diễn tập** (56 bảng trùng tên, dùng cho một lần chuyển đổi phân quyền)
cùng các cơ sở dữ liệu kiểm thử. Bài học: *một con số về lược đồ phải đếm trên đúng
một cơ sở dữ liệu được đặt tên, vì hội đồng có thể yêu cầu đếm lại — và câu lệnh đếm
là câu lệnh ai cũng chạy được.*

Trình bày cả 59 bảng trong một sơ đồ quan hệ duy nhất là trình bày một thứ không ai
đọc được. Chương này vì thế trình bày mô hình theo **bảy nhóm mô-đun**, mỗi nhóm là
một khối chức năng khép kín; **mô hình mức khái niệm và mức vật lý đầy đủ nằm ở Phụ
lục A**.

*Bảng 3-33: Bảy nhóm mô-đun dữ liệu*

| # | Nhóm mô-đun | Số bảng | Trả lời câu hỏi | Chịu ranh giới tổ chức |
|---|---|:--:|---|---|
| M1 | Danh tính & Truy cập | 8 | Anh là ai, phiên của anh còn hiệu lực không | Một phần |
| M2 | Tổ chức & Phân quyền | 10 (+1 khung nhìn) | Anh thuộc tổ chức nào, với vai gì, ở phạm vi nào | Có |
| M3 | Kho dữ liệu mẫu | 6 | Dữ liệu ký hiệu và người ký ra nó | **Có — trọng tâm** |
| M4 | Danh mục & Registry | 11 | Được phép thu lớp nào, phiên bản danh mục nào | Có, trừ ba bảng danh mục hệ thống |
| M5 | Huấn luyện & Mô hình | 3 | Dữ liệu thành mô hình như thế nào | Có |
| M6 | Dịch vụ tổ chức & Tích hợp | 12 | Gói cước, hạn mức, khoá API, hỗ trợ | Có |
| M7 | Pháp lý, Kiểm toán & Nền tảng | 9 | Ai đồng ý gì, ai làm gì, cấu hình nền tảng | Một phần |
| | **Tổng** | **59** | | |

**Về số thực thể ở mức khái niệm:** 59 bảng rút về khoảng **18–20 thực thể nghiệp
vụ**. Các bảng có vòng đời tạm (token, mã xác thực, mã hành động) gộp về một khái
niệm *Thông tin xác thực*; các bảng lịch sử (bí danh, sự kiện, lịch sử gửi, chỉ số
theo chu kỳ) **không lên** mô hình khái niệm. Hướng dẫn dựng ba mức mô hình ở Phụ lục A.

> ### ▣ HÌNH 3-11 — Mô hình dữ liệu theo nhóm mô-đun
> **Loại:** sơ đồ khối
> **Phải thể hiện:** bảy khối M1–M7 với số bảng của từng khối; các cạnh giữa khối thể
> hiện quan hệ chính (M2→M3 ranh giới tổ chức, M4→M3 lớp, M3→M5 dữ liệu huấn luyện,
> M7→M3 đồng thuận chi phối phát hành); **tô nền khác nhau cho khối chịu và không
> chịu ranh giới tổ chức**.
> **Chú thích:** *Hình 3-11: Kiến trúc mô hình dữ liệu theo bảy nhóm mô-đun.*

Bốn nhóm cần giải thích riêng vì chúng mang các quyết định thiết kế đáng bảo vệ.

#### b. M1 — Danh tính & Truy cập, và cái bẫy fail-open

Nhóm này **cố ý không phủ ranh giới tổ chức hoàn toàn**. Lý do rất cụ thể: bảng tài
khoản phải truy vấn được **trước khi** biết tổ chức — chính lúc đăng nhập. Nếu bảng
tài khoản chịu chính sách theo tổ chức mà không có lối thoát, thì truy vấn tìm tài
khoản lúc đăng nhập sẽ khớp 0 hàng, và **hệ thống không đăng nhập được cho ai cả**.

Cách giải: bảng `users` **có** cột `tenant_id` và **có** chính sách, nhưng chính sách
chứa nhánh `app.system_scope = 'on'` cho đúng những truy vấn chạy trước khi ngữ cảnh
tổ chức tồn tại.

**Đây là chỗ sinh ra một cái bẫy đã mắc ba lần trong hai ngày**, và nó đáng viết vào
quyển vì nó là bài học thật về ranh giới giữa hai tầng:

> Khi một truy vấn chạy **trước khi** biết tổ chức, chính sách khớp **0 hàng**. Mã
> ứng dụng nhận về một tập rỗng và đọc nó thành **"không có gì"** thay vì **"chưa có
> ngữ cảnh"**. Hai câu đó dẫn tới hai hành vi ngược nhau: câu đầu dẫn tới *tạo mới*
> hoặc *cho qua*, câu sau dẫn tới *dừng*.
>
> Nói cách khác: **cách ly fail-closed ở tầng cơ sở dữ liệu vẫn có thể bị tầng ứng
> dụng diễn giải sai thành fail-open.** Một cơ chế an toàn ở tầng dưới không tự động
> làm tầng trên an toàn.

Bảng trong nhóm: tài khoản; token làm mới; token đặt lại mật khẩu; mã xác thực; bí
mật TOTP; mã khôi phục; mã xác thực lại cho thao tác nhạy cảm; khoá API.

#### c. M2 — Tổ chức & Phân quyền

Thiết kế của nhóm này đã trình bày ở §3.3.3.2. Ở đây chỉ nêu hình dạng lược đồ và
**một điểm phải vẽ đúng** ở sơ đồ thực thể quan hệ:

`memberships` là **một** bảng đa hình, không phải ba bảng. Nó có `scope_level` nhận
bốn giá trị, ba cột phạm vi (`tenant_id` / `workspace_id` / `project_id`), và **tự
trỏ** qua khoá ngoại ghép `(parent_membership_id, user_id)`. Vẽ nó thành
`workspace_members` và `project_members` là vẽ hai bảng **không tồn tại**.

Tương tự, `roles.tenant_id` **cho phép NULL**: danh mục vai nền tảng và vai riêng của
tổ chức nằm trong **cùng một bảng**, phân biệt bằng giá trị NULL. Ở mô hình khái niệm
nên là **một** thực thể `Vai` có thuộc tính phân biệt nguồn, không phải hai thực thể.

#### d. M3 — Kho dữ liệu mẫu

Nhóm trọng tâm. Sáu bảng: mẫu, lớp, phiên thu, bản tải lên thô, người ký, bí danh
người ký. Ba quyết định mô hình hoá đáng bảo vệ:

**Thứ nhất — người ký là một thực thể, không phải một cột.** Tài khoản thu mẫu và
người có bàn tay trong mẫu là hai vế khác nhau. Tách người ký thành thực thể riêng
cho phép ba việc mà một cột không cho phép: gán lại người ký khi phát hiện sai; gắn
đồng thuận vào **đúng chủ thể**; và trả lời được câu *"những dòng nào là của người
này"*. Số liệu về độ phủ của quan hệ này ở §3.3.3.4 e.

**Thứ hai — khoá ngoại là khoá ghép có mang định danh tổ chức.** Quan hệ từ mẫu tới
lớp không đi qua một cột đơn, mà qua cặp `(tenant_id, class_uid)`.

Lý do: **một khoá ngoại đơn cho phép mẫu của tổ chức A trỏ tới lớp của tổ chức B** —
cơ sở dữ liệu không phản đối, vì khoá vẫn tồn tại. Khoá ghép làm việc đó **bất khả
thi ở tầng ràng buộc**, không phải ở tầng kiểm tra của ứng dụng. Danh sách đủ 20 khoá
ghép giữ phạm vi ở §3.4.3 c.

**Thứ ba — định danh lớp gồm cả phương ngữ và vùng miền.** Khoá duy nhất của lớp gồm
**năm cột**: `(tenant_id, slug, language, dialect, region)`.

Điểm này có một lịch sử đáng ghi lại, vì nó là ví dụ hoàn hảo về khoảng cách giữa
"mã đã đúng" và "hệ thống hành xử đúng":

| Thời điểm | Trạng thái mã | Trạng thái CSDL đang chạy | Hành vi thật |
|---|---|---|---|
| Trước 17/08/2026 | Khoá 5 cột, có `region` | **Chỉ mục cũ 4 cột vẫn còn**, và vì chặt hơn nên nó thắng | Hai lớp chỉ khác vùng miền **bị từ chối** — cam kết "biến thể theo vùng" không hiện thực được |
| Từ 17/08/2026 | Khoá 5 cột | Chỉ mục cũ **đã gỡ**; còn lại `uq_classes_tenant_slug_lang_dialect_region` — xác nhận lại 18/08 | Biến thể theo vùng vào được; trùng hoàn toàn vẫn bị chặn |

**Bài học phương pháp, và nó áp cho cả quyển:** *"commit đã có" không phải bằng chứng
cho một cam kết về hành vi hệ thống.* Một dòng bằng chứng trỏ tới một commit chỉ
chứng minh **mã đã đổi**; nó không chứng minh **cơ sở dữ liệu đang chạy** hành xử
theo mã đó. Bằng chứng đúng loại là một **cặp thao tác có đối chứng** — một lượt chèn
phải thành công, một lượt chèn phải bị từ chối — chứ không phải một mã băm commit.

**Một quan hệ KHÔNG được vẽ:** `samples` **không có** khoá ngoại tới `raw_uploads`.
Xuất xứ từ tệp tải lên tới mẫu đặc trưng **không** được cưỡng chế ở tầng ràng buộc —
nó chỉ tồn tại qua một cột kiểu nguồn và quy ước đặt tên. Vẽ quan hệ đó như một quan
hệ có thật là mô tả sai mức bảo đảm của chuỗi nguồn gốc.

> ### ▣ HÌNH 3-12 — Nhóm M3: Kho dữ liệu mẫu
> **Loại:** sơ đồ quan hệ thực thể
> **Phải thể hiện:** sáu bảng và quan hệ; **vẽ rõ khoá ngoại ghép mang định danh tổ
> chức** (ghi cặp cột trên cạnh); phân biệt quan hệ *"tài khoản thu"* với quan hệ
> *"người ký"* bằng **hai cạnh khác nhau** từ bảng mẫu — đây là điểm phải nhìn thấy
> được từ hình; **không vẽ** cạnh từ `raw_uploads` tới `samples`.
> **Chú thích:** *Hình 3-12: Mô hình dữ liệu nhóm Kho dữ liệu mẫu.*

#### e. M4 — Danh mục & Registry: danh mục hệ thống và danh mục của tổ chức

Nhóm này cài đặt quan hệ sao chép một chiều giữa hai danh mục:

```
DANH MỤC HỆ THỐNG ──sao chép MỘT LẦN──► Danh mục của tổ chức ──ghim──► Tác vụ huấn luyện
 (bảng community_*,                      (tổ chức tự sửa)              (không gian nhãn cố định)
  CHỈ chứa cấu hình)                              │                              │
        │                                         │                              │
        └──────── ✗ KHÔNG có đường rơi ngược lúc chạy ──────────────────────────┘

  ─────────────────────────────────────────────────────────────────────────────
  Tách bạch với hai thứ trên:
  CỘNG ĐỒNG = một hàng của `tenants` (tenant_type='COMMUNITY'), chịu ĐÚNG cách ly
              như mọi tổ chức khác — KHÔNG phải một mặt phẳng ngoại lệ
```

Luật xuyên suốt (RB-D7): **lúc chạy KHÔNG bao giờ rơi ngược về danh mục hệ thống**;
thiếu dữ liệu thì **dừng**, không suy đoán.

**Ba chi tiết lược đồ phải vẽ đúng, và cả ba là chỗ dễ vẽ sai nhất:**

1. **Ba bảng `community_*` KHÔNG phải Cộng đồng — chúng là Danh mục hệ thống.** Tên
   bảng là **di sản**, không phải nghĩa: chúng chứa cấu hình (phương ngữ nào tồn tại,
   hồ sơ nhận dạng nào tồn tại) để sao chép cho tổ chức mới, và **không** chứa mẫu,
   điểm mốc, bản ghi đồng thuận hay thông tin quy kết. Tên miền đã được sửa ở tầng API
   và tầng dịch vụ (`/vocabulary/catalog/*`); **tên bảng vật lý giữ nguyên có chủ ý**,
   vì đổi tên bảng đòi một cửa sổ triển khai, còn tên khái niệm thì phải hết sai
   **ngay**. Có kiểm thử chặn nếu các bảng này mọc thêm cột kiểu khoá lưu trữ, mã đồng
   thuận hay mã người đóng góp.
2. **Ba bảng đó không có cột `tenant_id` và không bật chính sách cách ly** — đúng, vì
   chúng là danh mục phẳng của nền tảng, mọi tổ chức **đọc chung** và **không tổ chức
   nào ghi được**. An toàn của chúng đến từ *thiếu vắng một đường ghi*, cộng luật
   không-rơi-ngược cưỡng chế ở tầng ứng dụng.
3. **Cộng đồng LÀ một hàng của bảng `tenants`**, mang `tenant_type='COMMUNITY'` và
   `is_system_reserved=TRUE`, có chỉ mục bảo đảm nhiều nhất một hàng như vậy. Vẽ nó
   thành một mặt phẳng nằm ngoài cây tổ chức là vẽ sai — và sai theo hướng nguy hiểm,
   vì nó gợi ý một đường đọc không chịu cách ly. Lý do của quyết định này ở §3.1.4 g,
   Bất biến 3.

**Ba lỗi có thật đã thúc đẩy thiết kế này**, và cả ba đáng đưa vào quyển vì chúng cho
thấy mỗi ràng buộc ở đây trả lời một sự cố cụ thể:

1. Danh sách hồ sơ nhận dạng gắn cứng ở **hai nơi** và đã lệch nhau (6 mục so với 5)
   → **7 lớp bị loại khỏi bước chia dữ liệu trong im lặng**.
2. Số hiệu phiên bản danh mục là một bộ đếm **bị ghi đè**, và ảnh chụp là một tệp
   **bị ghi đè** → *"bộ dữ liệu ghim phiên bản 2"* **không thực hiện được**, vì nội
   dung phiên bản 2 biến mất ngay khi phiên bản 3 được ghi.
3. Không có khái niệm thành viên tổ chức → hoặc không tổ chức nào tự quản được, hoặc
   **mọi quản trị viên nền tảng thành biên tập viên của mọi tổ chức**.

**Một phân biệt phải giữ rõ trong quyển: "đã đăng ký" không đồng nghĩa "huấn luyện
được".** Một lớp có đủ mẫu nhưng người ký chưa đồng ý ở mức tương ứng thì với đường
phát hành nghiên cứu, nó là một lớp **rỗng**.

> ### ▣ HÌNH 3-13 — Danh mục hệ thống, tổ chức, và Cộng đồng
> **Loại:** sơ đồ khối
> **Phải thể hiện:** **Danh mục hệ thống** ở trên, **Danh mục của tổ chức** ở dưới, mũi
> tên sao chép **một chiều** có nhãn *"một lần, lúc khởi tạo"*, và một mũi tên **gạch
> chéo** thể hiện đường rơi ngược bị cấm; quan hệ ghim phiên bản từ tác vụ huấn luyện
> tới một phiên bản danh mục cụ thể.
> **Điểm phải nhìn thấy được từ hình:** **Cộng đồng vẽ NẰM TRONG cây tổ chức**, cạnh
> `default` và các tổ chức khác, kèm nhãn `tenant_type='COMMUNITY'` — **không** vẽ nó
> thành một mặt phẳng ngoài. Ba bảng `community_*` gắn nhãn **"Danh mục hệ thống (tên
> bảng là di sản)"**, và có một đường kẻ phân tách chúng khỏi khối Cộng đồng.
> **Chú thích:** *Hình 3-13: Danh mục hệ thống, danh mục của tổ chức, và vị trí của
> Cộng đồng trong cây tổ chức.*

---

### 3.4.2. Danh mục các bảng dữ liệu

Bảng dưới đây liệt kê tên, vai trò và trạng thái cách ly của toàn bộ **59 bảng và 1
khung nhìn** (59 bảng), theo bảy nhóm mô-đun. **Chi tiết từng cột, kiểu dữ liệu, ràng buộc và
chỉ mục nằm ở Phụ lục A.**

Ký hiệu cột **RLS**: ✔ có bật chính sách bảo mật mức hàng **và** bật cờ cưỡng chế với
chủ sở hữu bảng · — không bật · *(kế thừa)* khung nhìn chạy với quyền người gọi.

Ký hiệu cột **Vòng đời**: `Mutable` sửa được · `Soft-delete` xoá mềm · `Immutable`
bất biến · `Append-only` chỉ thêm · `Revocable` thu hồi được · `Ephemeral` có hạn ·
`Upsert` ghi đè theo khoá · `Catalogue` danh mục tham chiếu.

#### M1 — Danh tính & Truy cập (8 bảng)

*Bảng 3-34: Danh mục bảng nhóm M1*

| Bảng | Khoá chính | Vai trò | Vòng đời | RLS |
|---|---|---|---|:--:|
| `users` | `id` | Tài khoản: định danh, mã băm mật khẩu, cờ quản trị nền tảng, trạng thái | Mutable, Soft-delete | ✔ |
| `refresh_tokens` | `token_hash` | Phiên đăng nhập: token làm mới, thiết bị, địa chỉ IP, thời điểm thu hồi | Ephemeral, Revocable | — |
| `password_reset_tokens` | `token_hash` | Token đặt lại mật khẩu, dùng một lần, có hạn | Ephemeral | — |
| `verification_codes` | `challenge_id` | Mã xác thực địa chỉ liên hệ, hai kênh (email và tin nhắn) | Ephemeral | — |
| `user_totp` | `user_id` | Bí mật xác thực hai yếu tố theo chuẩn TOTP | Mutable | — |
| `user_recovery_codes` | `code_hash` | Mã khôi phục dùng một lần | Ephemeral | — |
| `user_action_passcodes` | `user_id` | Mã xác thực lại cho thao tác nhạy cảm — gắn với **phiên**, không gắn với tài khoản | Ephemeral | — |
| `api_keys` | `key_id` | Khoá API: lưu **mã băm**, không lưu khoá; mang phạm vi tổ chức | Revocable | ✔ |

**Vì sao sáu bảng trong nhóm không bật chính sách cách ly:** cả sáu đều khoá theo tài
khoản (`user_id`) chứ không theo tổ chức, và một tài khoản có thể thuộc nhiều tổ
chức. Ranh giới của chúng là **danh tính**, không phải tổ chức — đặt chính sách theo
tổ chức lên chúng sẽ là đặt sai loại ranh giới.

#### M2 — Tổ chức & Phân quyền (9 bảng + 1 khung nhìn)

*Bảng 3-35: Danh mục bảng nhóm M2*

| Bảng | Khoá chính | Vai trò | Vòng đời | RLS |
|---|---|---|---|:--:|
| `tenants` | `tenant_id` | Tổ chức: **ranh giới cách ly cao nhất**; trạng thái quản trị tách khỏi trạng thái thương mại | Mutable, Soft-delete | ✔ |
| `workspaces` | `workspace_id` | Không gian làm việc trong một tổ chức | Mutable, Soft-delete | ✔ |
| `projects` | `project_id` | Dự án trong một không gian làm việc; khoá ngoại ghép `(tenant_id, workspace_id)` | Mutable, Soft-delete | ✔ |
| `memberships` | `membership_id` | **Tư cách thành viên đa hình**: `scope_level ∈ {SYSTEM, TENANT, WORKSPACE, PROJECT}`, tự trỏ tới membership cấp trên | Revocable | ✔ |
| `roles` | `role_id` | Định nghĩa vai; `tenant_id` **cho phép NULL** = vai nền tảng và vai riêng của tổ chức chung một bảng | Mutable | ✔ |
| `permissions` | `permission_code` | Danh mục quyền | Catalogue | — |
| `role_permissions` | (`role_id`, `permission_code`) | Bảng nối vai ↔ quyền | Mutable | — |
| `role_assignments` | `assignment_id` | Gán vai; trỏ vào `membership_id` qua khoá ghép `(membership_id, user_id)`. **`membership_id` NULLABLE**: NULL = gán vai cấp **hệ thống**, không thuộc tổ chức nào | Revocable | **—** |
| `project_allocations` | `allocation_id` | **Hạn mức phân bổ cho một dự án**; khoá ghép `(tenant_id, project_id)` — bảng thứ 59, thêm sau snapshot 17/08 | Mutable | ✔ |
| `tenant_invitations` | `invitation_id` | Lời mời: địa chỉ nhận, vai dự kiến, hạn dùng, trạng thái | Ephemeral | ✔ |
| `tenant_members` ⟨khung nhìn⟩ | — | Lát cắt `scope_level = 'TENANT'` của `memberships` | dẫn xuất | *(kế thừa)* |

Lý do `role_assignments` không mang `tenant_id` và không bật chính sách đã phân tích
ở §3.3.3.2 d, cùng với giới hạn kèm theo.

#### M3 — Kho dữ liệu mẫu (6 bảng)

*Bảng 3-36: Danh mục bảng nhóm M3*

| Bảng | Khoá chính | Vai trò | Vòng đời | RLS |
|---|---|---|---|:--:|
| `samples` | `sample_uid` | **Mẫu dữ liệu** — bảng trung tâm; siêu dữ liệu, chỉ số chất lượng, đường dẫn tệp, bốn cột quy kết | Mutable, Soft-delete | ✔ |
| `classes` | `class_uid` | Lớp từ vựng; **định danh năm cột** `(tenant_id, slug, language, dialect, region)` | Mutable, Soft-delete | ✔ |
| `capture_sessions` | `capture_session_id` | Phiên thu: gom nhiều mẫu cùng một lượt ngồi trước camera; **chuyển chủ sở hữu được** | Mutable | ✔ |
| `raw_uploads` | `upload_uid` | Bản tải lên thô, ghi **trước** chuẩn hoá (NFR-R2) | Mutable, Soft-delete | ✔ |
| `signers` | `signer_id` | **Người ký** — chủ thể dữ liệu | Mutable | ✔ |
| `signer_aliases` | (`tenant_id`, `old_signer_id`) | Bí danh, phục vụ gộp hai bản ghi người ký trùng | Append-only | ✔ |

**`capture_sessions` là một thực thể có hành vi, không phải một nhãn.** Sáu đường
nghiệp vụ chạm vào nó: liệt kê phiên của một lớp, **xoá** phiên, **chuyển chủ sở
hữu**, đọc khung hình, hỏi trạng thái dựng bản xem trước, và tải bản xem trước dựng
lại từ điểm mốc. Việc có đường chuyển chủ sở hữu nghĩa là quyền sở hữu một phiên thu
**đổi được** — đó là một vòng đời, nên ở mô hình khái niệm nó phải là một thực thể,
không phải một thuộc tính gộp của mẫu.

#### M4 — Danh mục & Registry (11 bảng)

*Bảng 3-37: Danh mục bảng nhóm M4*

| Bảng | Khoá chính | Vai trò | Vòng đời | RLS |
|---|---|---|---|:--:|
| `languages` | `code` | Danh mục ngôn ngữ | Catalogue | — |
| `regions` | `code` | Danh mục vùng miền | Catalogue | — |
| `dialects` | (`tenant_id`, `dialect_id`) | Phương ngữ của tổ chức; tự trỏ `merged_into` khi gộp | Mutable | ✔ |
| `dialect_aliases` | (`tenant_id`, `old_dialect_id`) | Bí danh phương ngữ sau khi gộp | Append-only | ✔ |
| `recognition_profiles` | (`tenant_id`, `profile_id`) | Hồ sơ nhận dạng: nhóm lớp phục vụ cùng một mô hình | Mutable | ✔ |
| `vocabulary_groups` | (`tenant_id`, `group_id`) | Nhóm từ vựng | Mutable | ✔ |
| `vocabulary_registry_meta` | `tenant_id` | Siêu dữ liệu danh mục của tổ chức | Mutable | ✔ |
| `registry_versions` | (`tenant_id`, `version`) | **Phiên bản danh mục** — ảnh chụp có mã băm; bất biến **theo quy ước, không có trigger** | Immutable *(quy ước)* | ✔ |
| `community_dialects` | `dialect_id` | **Danh mục hệ thống**: phương ngữ chuẩn — *tên bảng là di sản, không phải nghĩa* | Mutable | — |
| `community_profiles` | `profile_id` | **Danh mục hệ thống**: hồ sơ nhận dạng chuẩn | Mutable | — |
| `community_versions` | `version` | **Danh mục hệ thống**: phiên bản danh mục chuẩn | Immutable | — |

#### M5 — Huấn luyện & Mô hình (3 bảng)

*Bảng 3-38: Danh mục bảng nhóm M5*

| Bảng | Khoá chính | Vai trò | Vòng đời | RLS |
|---|---|---|---|:--:|
| `training_jobs` | `job_id` | Tác vụ huấn luyện: phạm vi, tham số, trạng thái, **phiên bản danh mục đã ghim** | Mutable | ✔ |
| `training_job_classes` | (`job_id`, `class_idx`) | **Ảnh chụp** tập lớp thực sự tham gia sau khi qua ba cổng chặn, cùng chỉ số đã gán | Immutable | ✔ |
| `training_metrics` | (`job_id`, `epoch`) | Chỉ số theo chu kỳ huấn luyện | Append-only | ✔ |

Quan hệ `training_jobs(tenant_id, registry_version) → registry_versions(tenant_id, version)`
là **quan hệ ghim phiên bản duy nhất tồn tại trong hệ thống**. Nó ghim *không gian
nhãn*, **không** ghim *nội dung bộ dữ liệu* — giới hạn đã phân tích ở §3.1.4 h.

#### M6 — Dịch vụ tổ chức & Tích hợp (12 bảng)

*Bảng 3-39: Danh mục bảng nhóm M6*

| Bảng | Khoá chính | Vai trò | Vòng đời | RLS |
|---|---|---|---|:--:|
| `plans` | `plan_code` | Gói cước và hạn mức | Catalogue | — |
| `tenant_subscriptions` | `subscription_id` | Đăng ký dịch vụ của tổ chức: kỳ hạn, trạng thái, ân hạn | Mutable | ✔ |
| `tenant_usage_daily` | (`tenant_id`, `usage_date`, `metric`) | Mức sử dụng theo ngày | Upsert | ✔ |
| `tenant_exports` | `export_id` | Yêu cầu xuất dữ liệu tổ chức | Ephemeral | ✔ |
| `tenant_purges` | `purge_id` | Yêu cầu dọn sạch dữ liệu tổ chức | Append-only | **—** |
| `webhook_endpoints` | `endpoint_id` | Điểm nhận sự kiện | Mutable, Revocable | ✔ |
| `webhook_deliveries` | `delivery_id` | Lịch sử gửi sự kiện | Append-only | ✔ |
| `support_tickets` | `ticket_id` | Phiếu hỗ trợ | Mutable | ✔ |
| `support_messages` | `message_id` | Tin nhắn trong phiếu | Append-only | ✔ |
| `notifications` | `notification_id` | Thông báo trong ứng dụng | Mutable | ✔ |
| `event_outbox` | `event_id` | Hộp thư đi cho sự kiện gửi ra ngoài | Append-then-drain | ✔ |
| `google_sheets_sync_status` | `id` | Trạng thái phản chiếu sang bảng tính ngoài | Upsert | — |

**`tenant_purges` là bảng duy nhất mang `tenant_id` mà không bật chính sách cách ly**
— ngoại lệ duy nhất còn lại của độ phủ. Nêu đích danh ở đây thay vì để nó tan vào một
con số phần trăm; lý do và đánh giá rủi ro ở §3.4.3 b.

#### M7 — Pháp lý, Kiểm toán & Nền tảng (9 bảng)

*Bảng 3-40: Danh mục bảng nhóm M7*

| Bảng | Khoá chính | Vai trò | Vòng đời | RLS |
|---|---|---|---|:--:|
| `legal_documents` | `doc_id` | Văn bản pháp lý đã công bố; định danh nghiệp vụ là cặp (`kind`, `version`); toàn vẹn neo vào `content_hash` | **Immutable sau công bố (trigger)** | — |
| `legal_document_drafts` | `draft_id` | Bản thảo, sửa được | Mutable | — |
| `legal_document_events` | `event_id` | Lịch sử vòng đời văn bản | Append-only *(trigger)* | — |
| `user_consents` | `consent_id` | Chấp thuận của **tài khoản**; khoá ghép tới (`kind`, `version`) | Append-only | — |
| `signer_consents` | `consent_id` | Đồng thuận của **người ký** — thứ chi phối đường phát hành | **Revocable** (`withdrawn_at`) | ✔ |
| `audit_log` | `audit_id` | Nhật ký kiểm toán bền vững | Append-only | ✔ |
| `platform_settings` | `key` | Cấu hình nền tảng | Mutable | — |
| `sot_authorized_keys` | `public_key` | Khoá công khai được tin cậy của máy phát hành — **hợp với danh sách khoá nền ghi trong mã nguồn**, không thay thế nó | Revocable | — |
| `schema_migrations` | (`version`, `applied_at`) | Lịch sử di trú lược đồ | Append-only | — |

**`user_consents` và `signer_consents` là hai bảng khác nhau, không phải hai lát của
một bảng.** Vế thứ nhất là tài khoản chấp thuận điều khoản dịch vụ; vế thứ hai là
**chủ thể dữ liệu** cho phép dùng dữ liệu của mình. Chỉ vế thứ hai chi phối đường phát
hành dữ liệu. Gộp chúng ở mô hình khái niệm là **sai về ngữ nghĩa pháp lý** — đây là
Bất biến 1 ở §3.1.4 g, thể hiện xuống tầng lược đồ.

**`legal_documents` không có bảng phiên bản con.** Định danh nghiệp vụ là cặp
(`kind`, `version`) trên chính bảng đó, và cả hai bảng đồng thuận đều trỏ vào cặp này
bằng **khoá ngoại ghép**. Vẽ một thực thể `Phiên bản văn bản pháp lý` riêng là vẽ một
bảng không tồn tại.

### 3.4.3. Mối liên hệ giữa các đối tượng

#### a. Các quan hệ then chốt

*Bảng 3-41: Các quan hệ then chốt và ghi chú thiết kế*

| Quan hệ | Lực lượng | Ghi chú thiết kế |
|---|---|---|
| Tổ chức — Tài khoản | n : m, qua `memberships` | Một người thuộc nhiều tổ chức **với vai khác nhau ở mỗi tổ chức** |
| Tổ chức — Không gian làm việc — Dự án | 1 : n : n | Cây ba cấp; khoá ghép giữ phạm vi ở mỗi tầng |
| Dự án — Hạn mức phân bổ | 1 : n, **khoá ghép** | `project_allocations` — bảng thứ 59, thêm sau snapshot 17/08 |
| Membership — Membership | tự trỏ, khoá ghép | Cưỡng chế *"cấp dưới phải có cấp trên"* bằng chính khoá ngoại + trigger |
| Membership — Gán vai | 1 : n, **khoá ghép** `(membership_id, user_id)` | Phạm vi **kế thừa** từ membership, không lưu lại hai chỗ |
| Tổ chức — Mẫu | 1 : n | Ranh giới cách ly; cưỡng chế bằng chính sách mức hàng |
| Lớp — Mẫu | 1 : n, **khoá ghép** | Khoá ngoại mang cả `tenant_id` → không trỏ chéo tổ chức được |
| Người ký — Mẫu | 1 : n, **khoá ghép** | Phủ **43,4 %**; phần còn lại **không quy kết được** |
| Phiên thu — Mẫu | 1 : n | Một lượt ngồi trước camera sinh nhiều mẫu |
| Bản tải lên thô — Mẫu | *(không có khoá ngoại)* | **Không cưỡng chế ở tầng ràng buộc** — chỉ qua cột kiểu nguồn và quy ước tên |
| Phương ngữ — Lớp | 1 : n, **khoá ghép** | Phương ngữ là **một phần định danh lớp**, không phải thuộc tính phụ |
| Phiên bản danh mục — Tác vụ huấn luyện | 1 : n, **khoá ghép** | Ghim **không gian nhãn**; điều kiện để tái lập được thí nghiệm |
| Văn bản pháp lý — Chấp thuận | 1 : n, khoá ghép tới (`kind`, `version`) | Văn bản bất biến, nên chấp thuận trỏ tới **nội dung xác định** |
| Người ký — Đồng thuận | 1 : n | Đồng thuận có phiên bản; **rút là rút thật** |
| Gói cước — Đăng ký dịch vụ | 1 : n | Trạng thái thương mại tách khỏi trạng thái quản trị |

#### b. Độ phủ của cơ chế cách ly

Số liệu đo trực tiếp trên `signdb` ngày 18/08/2026:

*Bảng 3-42: Ma trận phạm vi dữ liệu*

| Mặt phẳng | Số bảng | Có cột `tenant_id` | Bật chính sách cách ly |
|---|---:|---:|---:|
| **Tổ chức** | 36 | 36 | **35** |
| Nền tảng (danh mục, pháp lý, cấu hình, phân quyền) | 11 | 0 | 0 |
| Danh tính (thuộc tài khoản, cắt ngang tổ chức) | 7 | 0 | 0 |
| Danh mục hệ thống (`community_*`) | 3 | 0 | 0 |
| Hệ thống / vận hành | 2 | 0 | 0 |
| **Cộng** | **59** | **36** | **35** |

**Ba con số phải phát biểu đúng, và chúng dễ bị trộn lẫn:**

* **Ranh giới tổ chức trùng chính xác với tập bảng mang cột phạm vi: 36/36.** Không
  có bảng nào thuộc tổ chức mà thiếu cột phạm vi, và ngược lại không có bảng nào mang
  cột phạm vi mà không thuộc tổ chức. Đây là một tính chất mạnh, vì nó có nghĩa là
  không tồn tại bảng nào "quên" mất mình thuộc về ai.
* **Độ phủ chính sách: 35/36 ≈ 97,2 %**, với **đúng một** ngoại lệ được nêu đích
  danh: `tenant_purges` — đo lại ngày 18/08 vẫn đúng một ngoại lệ đó.
* **Cờ cưỡng chế với chủ sở hữu bảng: 35/35 = 100 %.** Đây là con số riêng, không
  được gộp vào con số trên: một bảng có chính sách nhưng không bật cờ này vẫn bị chủ
  sở hữu bảng đi vòng qua.

#### c. Hai mươi bốn khoá ngoại ghép giữ phạm vi

Đây là nhóm ràng buộc đáng đưa vào quyển nhất, vì nó làm việc trỏ chéo tổ chức **bất
khả thi ở tầng ràng buộc**, chứ không chỉ bị chặn ở tầng ứng dụng:

```
memberships(tenant_id, workspace_id)             → workspaces(tenant_id, workspace_id)
memberships(tenant_id, workspace_id, project_id) → projects(tenant_id, workspace_id, project_id)
memberships(parent_membership_id, user_id)       → memberships(membership_id, user_id)
projects(tenant_id, workspace_id)                → workspaces(tenant_id, workspace_id)
project_allocations(tenant_id, project_id)       → projects(tenant_id, project_id)
role_assignments(membership_id, user_id)         → memberships(membership_id, user_id)

samples(tenant_id, class_uid)                    → classes(tenant_id, class_uid)
samples(tenant_id, signer_id)                    → signers(tenant_id, signer_id)
samples(tenant_id, dialect)                      → dialects(tenant_id, dialect_id)
capture_sessions(tenant_id, class_uid)           → classes(tenant_id, class_uid)
capture_sessions(tenant_id, signer_id)           → signers(tenant_id, signer_id)
raw_uploads(tenant_id, class_uid)                → classes(tenant_id, class_uid)
raw_uploads(tenant_id, dialect)                  → dialects(tenant_id, dialect_id)
signer_aliases(tenant_id, new_signer_id)         → signers(tenant_id, signer_id)

classes(tenant_id, dialect)                      → dialects(tenant_id, dialect_id)
classes(tenant_id, recognition_profile)          → recognition_profiles(tenant_id, profile_id)
classes(tenant_id, vocabulary_group)             → vocabulary_groups(tenant_id, group_id)
dialect_aliases(tenant_id, new_dialect_id)       → dialects(tenant_id, dialect_id)
dialects(tenant_id, merged_into)                 → dialects(tenant_id, dialect_id)

training_jobs(tenant_id, registry_version)       → registry_versions(tenant_id, version)
training_metrics(tenant_id, job_id)              → training_jobs(tenant_id, job_id)

signer_consents(tenant_id, signer_id)            → signers(tenant_id, signer_id)
user_consents(kind, version)                     → legal_documents(kind, version)
signer_consents(kind, version)                   → legal_documents(kind, version)
```

**Ba nhóm khoá, ba mục đích khác nhau — không được gộp:**

* **Khoá giữ phạm vi** (đa số): làm việc trỏ chéo tổ chức bất khả thi ở tầng ràng
  buộc. `dialects(tenant_id, merged_into)` là một trường hợp **tự trỏ**: bí danh
  phương ngữ sau khi gộp vẫn phải nằm trong cùng tổ chức.
* **Khoá giữ chủ thể** — `role_assignments(membership_id, user_id)`: bảo đảm lần gán
  vai và tư cách thành viên thuộc về **cùng một người**. Với khoá đơn, một bản ghi gán
  vai cho người A dựa trên tư cách của người B là hợp lệ về mặt cơ sở dữ liệu.
* **Khoá ghim phiên bản** — hai dòng `(kind, version)`: một bản ghi đồng thuận trỏ tới
  đúng phiên bản văn bản đã ký, và văn bản đó bất biến sau công bố. Đây là chỗ hai cơ
  chế — bất biến và khoá ghép — kết hợp để biến một bản ghi đồng thuận thành **bằng
  chứng** thay vì một lời khẳng định.

#### d. Sáu trigger — các bất biến cưỡng chế ở tầng cơ sở dữ liệu

*Bảng 3-43: Sáu trigger và bất biến mà mỗi trigger bảo vệ*

| Trigger | Bảng | Bảo vệ điều gì | Nếu không có thì sao |
|---|---|---|---|
| `trg_legal_documents_freeze` | `legal_documents` | Bất biến sau công bố | Chấp thuận trỏ tới nội dung có thể đổi dưới chân nó |
| `trg_legal_events_append_only` | `legal_document_events` | Chỉ thêm, không sửa không xoá | Lịch sử vòng đời văn bản sửa được ⇒ mất giá trị làm bằng chứng |
| `ct_memberships_chain` | `memberships` | Membership cấp dưới phải có membership cấp trên | Một người có vai ở dự án mà không thuộc tổ chức chứa dự án đó |
| `ct_role_assignments_scope` | `role_assignments` | Lần gán vai khớp phạm vi của membership | Vai cấp tổ chức gán nhầm vào membership cấp dự án |
| `ct_role_permissions_dominance` | `role_permissions` | Vai không cấp được quyền vượt cấp của chính nó | Leo thang đặc quyền qua việc tự thêm quyền vào vai mình quản |
| `ct_roles_tenant_type` | `roles` | Vai nền tảng và vai của tổ chức không lẫn nhau | Một tổ chức tự tạo được một vai mang quyền nền tảng |

**`registry_versions` KHÔNG nằm trong danh sách này**, và điều đó phải nói ra. Tính
bất biến của ảnh chụp danh mục là **quy ước ở tầng ứng dụng**, không có trigger đứng
sau — khác hẳn `legal_documents`. Đây là phân biệt đã nêu ở §3.3.3.4 d, và nó là một
trong ba giới hạn thiết kế tổng kết ở §3.7.

#### e. Ba miền dữ liệu và ranh giới giữa chúng

Ngoài phân nhóm theo mô-đun, dữ liệu còn chia theo **quyền quản trị**. Ba miền này
**không lồng nhau**, và nhầm lẫn giữa chúng là nguồn của nhiều lỗi.

*Bảng 3-44: Ba miền dữ liệu*

| | Miền của tổ chức | Miền Cộng đồng | Miền danh mục hệ thống |
|---|---|---|---|
| Hiện thực bằng | Một hàng `tenants`, `tenant_type='ORGANIZATION'` | **Một hàng `tenants`, `tenant_type='COMMUNITY'`** (nhiều nhất một) | Ba bảng `community_*` — **không** phải một tenant |
| Ai sửa được | Tổ chức sở hữu | Không ai sửa trực tiếp; chỉ nhận qua quy trình duyệt đóng góp | Quản trị nền tảng |
| Ai đọc được | Chỉ tổ chức đó | Theo **quyền cụ thể**, không theo tư cách thành viên | Mọi tổ chức, chỉ đọc |
| Cưỡng chế bằng | **Chính sách bảo mật mức hàng** | **Cùng chính sách đó** — Cộng đồng không có ngoại lệ nào | **Chữ ký số** |
| Ví dụ | mẫu, lớp, phiên thu | dữ liệu đã duyệt vào tenant `community` | phương ngữ chuẩn, lược đồ |
| Đường vào | thu nhận | **yêu cầu đóng góp → duyệt** *(○ chưa hiện thực)* | công bố có ký |
| Đường ra | xuất dữ liệu tổ chức | không có | không có |

**Ranh giới quan trọng nhất: giá trị `default` KHÔNG phải là miền dùng chung.** Tổ
chức mang định danh `default` là tổ chức **mồi** — nơi dữ liệu lịch sử của hệ thống
tiền thân nằm lại. Nó là một tổ chức **bình thường về mọi mặt cách ly**. Coi nó là
"dữ liệu chung" là mở một lỗ hổng đúng bằng **toàn bộ dữ liệu lịch sử**.

**Một cái bẫy cụ thể trong mã, đáng ghi lại vì nó khái quát được:** hàm chuẩn hoá
định danh tổ chức trả về `default` khi nhận chuỗi rỗng. Hệ quả: một hàm kiểm tra viết
**sau** bước chuẩn hoá sẽ **không bao giờ thấy chuỗi rỗng**, và trở thành **mã chết**
— nó tồn tại, được đọc như một chốt chặn, nhưng không bao giờ kích hoạt.

> Nguyên tắc rút ra: **kiểm tham số thô trước khi chuẩn hoá.** Một phép kiểm đặt sau
> một phép biến đổi chỉ kiểm được những gì phép biến đổi cho qua.

#### f. Hai đường vượt ranh giới tổ chức — nêu đích danh

Phép đo cách ly ở Chương 4 chạy trên mặt phẳng **đọc theo yêu cầu HTTP**. Có hai
đường **không** đi qua mặt phẳng đó, và cả hai phải nêu tên chứ không được để tan vào
một câu tổng quát:

*Bảng 3-45: Hai đường nằm ngoài phép đo cách ly*

| Đường | Bản chất | Mức phơi nhiễm hôm nay | Trở thành rò rỉ thật khi nào |
|---|---|---|---|
| Xuất bộ dữ liệu ra tệp | Đọc theo phạm vi lời gọi, nhưng đi trên **mặt phẳng tệp** | Đã có chốt chặn sau bản vá C5 (§3.3.3.1 d) | — |
| **Đồng bộ ra bảng tính ngoài** | Chạy bằng **quyền hệ thống**, **không mang phạm vi tổ chức**; mọi mẫu của mọi tổ chức đổ vào **một** bảng tính duy nhất | **Bằng không** — toàn bộ 3.860 dòng hiện thuộc một tổ chức | **Đúng vào ngày tổ chức thứ hai thu mẫu đầu tiên** |

Đường thứ hai là một **ranh giới thiết kế bị vượt qua**, chưa phải một vụ rò rỉ đã
xảy ra — và phải nói đúng như vậy, không mạnh hơn, không nhẹ hơn. Ghi chú trong mã
nói rõ đây là chủ ý ở thời điểm viết: bảng tính là ảnh chụp toàn kho vào một bảng duy
nhất, không phải bản xuất theo tổ chức. Cách viết đúng cho quyển: *cách ly được cưỡng
chế ở tầng cơ sở dữ liệu cho đường đọc theo yêu cầu; đường đồng bộ ra dịch vụ ngoài
chạy bằng quyền hệ thống và không mang phạm vi tổ chức — đó là một hạn chế đã biết,
không phải một lỗ hổng chưa phát hiện.*

#### g. Một con số phải đọc đúng: 3.860 dòng ≠ 3.860 lần ký

Bảng `samples` có cột đánh dấu bản tăng cường. Phân bố đo ngày 18/08/2026:

| Mức tăng cường | Số dòng | Là gì |
|---:|---:|---|
| 0 | **3.420** | Bản gốc — một lần người thật thực hiện một ký hiệu |
| 1 | 110 | Bản tăng cường do máy sinh |
| 2–7 | 330 (55 mỗi mức) | Bản tăng cường do máy sinh |
| | **3.860** | **Tổng số dòng** |

**440 dòng (11,4 %) không phải một lần ký của con người**, mà là biến thể sinh ra từ
một bản gốc. Hệ quả bắt buộc cho cách phát biểu trong cả quyển:

* Con số dùng khi nói về **công sức thu thập** và **đa dạng người ký** là **3.420**.
* Con số **3.860** chỉ dùng được khi nói về **kích thước tập đưa vào huấn luyện**.

Trộn hai con số này là cách tự thổi phồng quy mô dữ liệu mà người phản biện kiểm được
bằng một câu truy vấn nhóm theo cột tăng cường.

> ### ▣ HÌNH 3-14 — Nhóm M1 và M2: Danh tính, Tổ chức và Phân quyền
> **Loại:** sơ đồ quan hệ thực thể rút gọn
> **Phải thể hiện:** 17 bảng của hai nhóm; lực lượng quan hệ; **đánh dấu bảng nào
> chịu chính sách bảo mật mức hàng** bằng một ký hiệu thống nhất; khung nhìn
> `tenant_members` vẽ bằng **nét đứt** để phân biệt với bảng thật; quan hệ **tự trỏ**
> của `memberships` vẽ rõ, vì đó là chỗ cưỡng chế cây phạm vi.
> **Chú thích:** *Hình 3-14: Mô hình dữ liệu nhóm Danh tính, Tổ chức và Phân quyền.*

> ### ▣ HÌNH 3-15 — Ba miền dữ liệu và đường đi giữa chúng
> **Loại:** sơ đồ khối
> **Phải thể hiện:** ba miền của Bảng 3-44 thành ba vùng; các mũi tên đường vào và
> đường ra; **`default` vẽ nằm TRONG miền tổ chức** kèm nhãn *"tổ chức mồi, không
> phải dữ liệu chung"* — đây là điểm phải nhìn thấy được từ hình; hai đường vượt ranh
> giới ở Bảng 3-45 vẽ bằng nét chấm gạch màu cảnh báo.
> **Chú thích:** *Hình 3-15: Ba miền dữ liệu, đường đi hợp lệ giữa chúng, và hai
> đường vượt ranh giới đã biết.*

---

## 3.5. Thiết kế chức năng

Phần này trình bày thiết kế của các chức năng trục chính. Mỗi mục theo cùng khuôn:
**luồng xử lý**, **các quyết định thiết kế**, và **giới hạn**. Sáu mục dưới đây ánh
xạ một-một với sáu phân hệ ở §3.2.2.

### 3.5.1. Quản lý tenant và quyền truy cập

#### a. UC-B1 — Tạo và quản lý một tổ chức

Đây là hành động **tạo ra một ranh giới cách ly**, nên nó phải làm nhiều việc hơn là
chèn một hàng.

```
Quản trị nền tảng yêu cầu tạo tổ chức
   ├─ kiểm định danh tổ chức: không rỗng, hợp lệ, chưa tồn tại
   │     ↳ kiểm trên THAM SỐ THÔ, trước bước chuẩn hoá  (§3.4.3 e)
   ├─ tạo hàng trong bảng tổ chức
   ├─ SAO CHÉP MỘT LẦN danh mục hệ thống vào tổ chức mới
   │     ↳ ghi lại phiên bản danh mục hệ thống đã sao chép — "kế thừa", KHÔNG phải "rơi về"
   ├─ tạo membership cấp tổ chức cho người quản trị đầu tiên
   ├─ tạo thư mục lưu trữ theo tổ chức
   └─ ghi bản ghi kiểm toán

Xoá / dọn sạch tổ chức
   ├─ TIỀN ĐIỀU KIỆN: xác thực lại trong phiên  (NFR-C5)
   ├─ xoá mềm trước, dọn hẳn là thao tác riêng
   └─ ghi bản ghi kiểm toán
```

**Ba quyết định thiết kế:**

1. **Sao chép một lần, không tham chiếu.** Tổ chức mới **giữ bản sao** của danh mục
   hệ thống, không giữ một con trỏ tới nó. Lý do: nếu giữ con trỏ, thì một thay đổi
   ở danh mục hệ thống sẽ **đổi ngầm** danh mục của mọi tổ chức, và không tổ chức
   nào biết. Bản sao làm mỗi tổ chức thành chủ sở hữu thật của danh mục mình.
2. **Kiểm tham số thô trước khi chuẩn hoá** — lý do ở §3.4.3 e.
3. **Xoá mềm tách khỏi dọn hẳn.** Hai thao tác, hai mức xác thực, hai bản ghi kiểm
   toán. Gộp chúng là biến một thao tác đảo ngược được thành một thao tác không.

#### b. UC-B4 — Mời và gỡ thành viên

**Vì sao đường vào tổ chức bắt buộc là lời mời**, đã phân tích ở §3.1.2 b: mã tài
khoản không phải bí mật. Ở đây bổ sung phần thiết kế:

```
Quản trị tổ chức mời một địa chỉ
   ├─ tạo lời mời: địa chỉ, vai dự kiến, hạn dùng, mã dùng một lần
   ├─ gửi thư qua S1  ─── S1 hỏng ⇒ báo lỗi gửi, KHÔNG tiêu cooldown
   └─ ghi bản ghi kiểm toán

Người được mời mở liên kết
   ├─ KIỂM MÃ TRƯỚC KHI TẠO TÀI KHOẢN: chưa hết hạn, chưa thu hồi, chưa dùng
   │     ↳ thứ tự này có chủ ý: một tài khoản thật KHÔNG BAO GIỜ bị mắc kẹt ở sai tổ chức
   ├─ địa chỉ email lấy từ lời mời và KHÔNG SỬA ĐƯỢC
   │     ↳ một lời mời gắn với đúng một địa chỉ
   ├─ tạo tài khoản (hoặc gắn membership nếu tài khoản đã tồn tại)
   ├─ đánh dấu lời mời đã dùng
   └─ ghi bản ghi kiểm toán
```

**Quyết định thiết kế đáng nói: thứ tự kiểm trước khi tạo.** Nếu tạo tài khoản trước
rồi mới kiểm mã, một lời mời hết hạn sẽ để lại một tài khoản thật **không thuộc tổ
chức nào**, và người dùng không hiểu vì sao mình đăng nhập được mà không thấy gì.
Kiểm trước làm trạng thái hỏng đó **không tồn tại được**.

#### c. UC-B5 — Gán vai theo phạm vi

Luồng và cơ chế cưỡng chế đã trình bày ở §3.1.4 h và §3.3.3.2. Nhắc lại điểm thiết kế
quan trọng nhất: **một lần gán vai cấp không gian làm việc cần HAI dòng** — một
membership mang cấp phạm vi tương ứng, và một bản ghi gán vai trỏ vào membership đó
qua khoá ghép. Khoá ghép ở bước hai là thứ bảo đảm lần gán vai và tư cách thành viên
thuộc về **cùng một người**.

#### d. UC-A1 — Đăng nhập và thiết lập phạm vi phiên

```
Nhập tên đăng nhập (hoặc email) và mật khẩu
   ├─ kiểm giới hạn tần suất theo IP THẬT và theo tài khoản   (NFR-C6)
   ├─ kiểm mã băm mật khẩu
   │     ↳ SAI TÊN và SAI MẬT KHẨU trả CÙNG một thông báo và CÙNG độ trễ  (NFR-C7)
   ├─ kiểm trạng thái tài khoản: hoạt động, không bị khoá,
   │     đã chấp thuận văn bản đang có hiệu lực, đăng ký dịch vụ không bị chặn cứng
   ├─ nếu bật 2FA ⇒ CHƯA cấp phiên, chuyển sang bước yếu tố thứ hai
   ├─ cấp token truy cập + token làm mới; ghi phiên kèm thiết bị và IP
   ├─ THIẾT LẬP PHẠM VI TỔ CHỨC MẶC ĐỊNH cho phiên
   └─ ghi bản ghi kiểm toán
```

**Ba cơ chế bảo vệ, và lý do từng cái:**

**Cổng mặc định từ chối.** Kiểm soát truy cập đặt ở **tầng trung gian**, trước khi
yêu cầu tới bộ định tuyến. Một điểm cuối mới viết ra mà tác giả quên khai báo quyền
thì **tự động yêu cầu xác thực** — ngược với mô hình "mỗi điểm cuối tự khai báo", nơi
**quên khai báo nghĩa là để ngỏ**.

Thiết kế này từng bịt **tám lỗ công khai** đã tồn tại, trong đó có một điểm cuối làm
lộ mười tên tài khoản thật. Bài học: *danh sách ngoại lệ công khai phải được rà soát
định kỳ, vì nó là chỗ duy nhất còn lại có thể sai.*

**Ba mức thu hồi phiên, không được lẫn:** thu hồi một phiên (đăng xuất trên một thiết
bị); thu hồi mọi phiên của một tài khoản (đổi mật khẩu); thu hồi theo biện pháp quản
trị (đình chỉ tài khoản). Đăng xuất còn đưa token truy cập vào **danh sách từ chối**
cho tới khi nó hết hạn tự nhiên — nếu không, đăng xuất chỉ thu hồi token làm mới, còn
token truy cập vẫn dùng được tới lúc hết hạn.

**Mô hình trả về là một cơ chế bảo vệ, không phải tài liệu hoá.** Bỏ khai báo mô hình
trả về của một điểm cuối tương đương với **gỡ bộ lọc bảo mật** — và đã làm **rò mã
băm mật khẩu** ra ngoài trong một lần sửa. Đây là bài học đáng ghi vì nó phản trực
giác: một thay đổi trông như dọn dẹp mã lại là một thay đổi về bảo mật.

**Xác thực hai yếu tố** cài đặt theo chuẩn TOTP và **kiểm bằng vector thử của tiêu
chuẩn**, không chỉ kiểm bằng "đăng nhập được". Phân biệt này quan trọng: một cài đặt
sai lệch múi giờ vẫn cho đăng nhập được với ứng dụng sinh mã **cùng lỗi**, nhưng
không tương thích với ứng dụng chuẩn — và lỗi chỉ lộ ra khi người dùng đổi ứng dụng.

### 3.5.2. Quản lý danh mục VSL

#### a. UC-C2 — Đăng ký và quản lý lớp ký hiệu

```
Biên tập viên tạo một lớp
   ├─ nhập: nhãn, ngôn ngữ, phương ngữ, VÙNG MIỀN, số bàn tay yêu cầu, chỉ tiêu thu
   ├─ sinh slug từ nhãn
   │     ↳ giữ phân biệt các chữ cái tiếng Việt có dấu phụ cho bảng chữ cái ngón tay
   ├─ kiểm trùng theo ĐỦ NĂM CỘT (tenant, slug, ngôn ngữ, phương ngữ, vùng miền)
   │     ↳ "chưa phân loại" ≠ "dùng chung" — hai giá trị này KHÔNG được coi là một
   ├─ ghi hàng lớp trong phạm vi tổ chức
   ├─ tăng số hiệu phiên bản danh mục của tổ chức
   └─ ghi bản ghi kiểm toán
```

**Quyết định thiết kế: vùng miền là một phần định danh, không phải một thuộc tính.**
Hai biến thể cùng một từ, cùng phương ngữ, khác vùng miền là **hai lớp khác nhau** —
vì chúng là hai ký hiệu khác nhau trong thực tế. Đưa vùng miền xuống hàng thuộc tính
phụ sẽ làm hệ thống từ chối chính thứ nó cần thu thập. Lịch sử của điểm này và bài
học phương pháp kèm theo ở §3.4.1 d.

**Gộp hai lớp trùng** ghi một bí danh vào bảng bí danh lớp thay vì xoá hàng cũ, nên
mọi tham chiếu lịch sử vẫn phân giải được. Nguyên tắc chung: *khi hợp nhất hai thực
thể, giữ lại đường dẫn từ định danh cũ tới định danh mới; xoá định danh cũ là làm
hỏng mọi bằng chứng trỏ tới nó.*

#### b. UC-C4 — Mở rộng danh mục của tổ chức từ danh mục hệ thống

Đây là chỗ luật *kế thừa ≠ rơi về* được thi hành, và nó là một cam kết trực tiếp của
đề cương: **tổ chức mở rộng được danh mục dùng chung mà không sửa bản gốc.**

```
Lúc tạo tổ chức (MỘT LẦN):
   danh mục hệ thống ──sao chép──► danh mục của tổ chức
   ghi lại: phiên bản danh mục hệ thống đã sao chép

Lúc chạy (MỌI LÚC KHÁC):
   tổ chức đọc danh mục CỦA MÌNH
   thiếu dữ liệu ⇒ DỪNG, báo lỗi
   ✗ KHÔNG BAO GIỜ đọc sang danh mục hệ thống
```

**Tính chất đạt được, phát biểu chính xác:** danh mục hệ thống **không bị tổ chức nào
sửa được**, vì không có đường ghi nào từ tổ chức sang danh mục hệ thống. Việc một tổ
chức thêm hai trăm lớp riêng không làm danh mục hệ thống thay đổi một dòng. Đây là vế
khó nhất trong ba vế của cam kết, và nó đạt được bằng **thiếu vắng một đường ghi**,
chứ không bằng một phép kiểm — cách bảo đảm mạnh hơn.

### 3.5.3. Thu nhận và quản lý dữ liệu mẫu

#### a. Hai đường thu, tách bạch

Theo Bất biến 6 (§3.1.4 g), hai đường thu là hai đường khác nhau và phải vẽ tách:

```
UC-C6  ĐƯỜNG CAMERA
   Camera → trích điểm mốc TẠI TRÌNH DUYỆT (WebAssembly)
          → gửi chuỗi số (vài chục KiB)
          → kiểm đồng thuận + hạn mức → ghi bản ghi mẫu → tác vụ nền
   ✗ Video KHÔNG rời máy người dùng — nên KHÔNG có gì để trích lại ở máy chủ

UC-C7  ĐƯỜNG TỆP VIDEO
   Tệp video → tải lên → GHI BẢN THÔ TRƯỚC (NFR-R2)
             → tác vụ nền trích điểm mốc Ở MÁY CHỦ
             → ghi bản ghi mẫu
```

#### b. Luồng xử lý một bản ghi

```
ĐỒNG BỘ — trong vòng đời một yêu cầu HTTP
   ├─ mở phạm vi tổ chức (SET LOCAL, trong đúng một khối quản lý ngữ cảnh)
   ├─ kiểm đồng thuận NGƯỜI KÝ còn hiệu lực   → thiếu ⇒ chặn ghi, điều hướng chấp thuận
   ├─ kiểm hạn mức tổ chức                      → vượt ⇒ từ chối, nêu hạn mức gói
   ├─ ghi bản ghi mẫu (trạng thái `pending`)
   └─ đẩy tác vụ vào hàng đợi, trả mã tác vụ    → người dùng KHÔNG chờ (NFR-P3)

╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌ RANH GIỚI ĐỒNG BỘ / BẤT ĐỒNG BỘ ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌

BẤT ĐỒNG BỘ — tiến trình nền
   ├─ ghi kho thô                     ← TRƯỚC mọi chuẩn hoá  (NFR-R2)
   ├─ cắt cửa sổ trượt (60 khung, bước nhảy 2)
   ├─ chuẩn hoá không gian toạ độ
   ├─ chấm chất lượng: độ đầy đủ, độ rung, tỉ lệ hiện diện của tay
   ├─ sinh các biến thể tăng cường
   ├─ ghi tệp đặc trưng + tệp mô tả đi kèm
   │     ↳ tệp mô tả cho phép dựng lại hàng đăng ký TỪ TỆP, nếu hàng bị mất
   ├─ nối hàng vào nguồn sự thật, rồi phản chiếu sang CSDL
   ├─ cập nhật bản ghi mẫu (`ready` + chỉ số)
   └─ đẩy tác vụ đồng bộ kho ngoài (có thử lại)
```

**Bốn nhóm công việc chạy nền:** trích đặc trưng và chuẩn hoá; đồng bộ kho lưu trữ
ngoài; dựng bản xem trước; bảo trì theo lịch (đối soát, nhắc hạn, sao lưu, dọn dẹp).

#### c. Hai chỉ số chất lượng và khả năng tái lập

**Độ đầy đủ tính lại được** từ tệp đặc trưng; **độ rung thì không**, vì nó phụ thuộc
vào chuỗi thời gian **trước** khi chuẩn hoá — mà chuỗi đó không được lưu.

Đây là một phân biệt phải giữ khi báo cáo: **một chỉ số tái lập được và một chỉ số
không tái lập được không có cùng giá trị chứng minh.** Chỉ số thứ nhất kiểm lại được
bởi người khác; chỉ số thứ hai chỉ tin được nếu tin vào quy trình đã sinh ra nó.

Ngoài ra, **độ đầy đủ bằng 0 không có nghĩa tệp rỗng** — nó có nghĩa **không phát
hiện được bàn tay nào**, và hai điều đó khác nhau. Nhầm chúng dẫn tới việc xoá nhầm
những mẫu vẫn còn dữ liệu.

#### d. Ba nhánh lỗi và hành vi tương ứng

| Nhánh lỗi | Hành vi | Vì sao thiết kế như vậy |
|---|---|---|
| Không phát hiện được bàn tay | Kết thúc tác vụ ở trạng thái thất bại, nêu lý do; **không tạo hàng mẫu** | Một hàng mẫu không có dữ liệu là một hàng gây nhiễu mọi thống kê về sau |
| Bản ghi ngắn hơn cửa sổ | **Đệm thêm** và ghi lại sự kiện đó vào chỉ số chất lượng | Loại bỏ im lặng làm mất dữ liệu mà không ai biết; đệm và ghi nhận giữ được cả hai |
| Kho ngoài không phản hồi | Thử lại; hết lượt thì **giữ đường dẫn cục bộ**, tác vụ đối soát điền khoá lưu trữ sau | RB-T4: hỏng đồng bộ **không được** làm hỏng đường thu |

#### e. Giới hạn về độ tin cậy, phải nêu

Cơ chế thử lại **không đồng đều** giữa bốn nhóm công việc nền, và **tính lũy đẳng
chưa bảo đảm** cho việc tạo tài nguyên và tải đối tượng lên kho ngoài. Kết luận đúng
mức: *"đạt về năng lực, có hạn chế về độ tin cậy"*.

> ### ▣ HÌNH 3-16 — Luồng xử lý bất đồng bộ của một bản ghi
> **Loại:** sơ đồ hoạt động UML
> **Phải thể hiện:** **hai đường thu vẽ tách bạch** (camera và tệp video) hội tụ vào
> cùng một tác vụ nền; ranh giới đồng bộ / bất đồng bộ; thứ tự **ghi kho thô trước
> chuẩn hoá**; ba nhánh lỗi ở Bảng trên và hành vi tương ứng.
> **Chú thích:** *Hình 3-16: Luồng xử lý bất đồng bộ của một bản ghi thu, cho cả hai
> đường thu.*

> ### ▣ HÌNH 3-17 — Vòng đời trạng thái của một mẫu
> **Loại:** máy trạng thái UML
> **Phải thể hiện:** `pending → processing → ready`; nhánh `failed`; nhánh `deleted`
> (xoá mềm) → `purged` (xoá hẳn) và **cạnh khôi phục ngược** từ `deleted` về `ready`;
> ghi rõ hành động nào của tác nhân nào gây ra mỗi chuyển trạng thái.
> **Chú thích:** *Hình 3-17: Máy trạng thái vòng đời một mẫu dữ liệu.*

### 3.5.4. Quản lý dataset, phiên bản và provenance

Đây là mục phải viết cẩn thận nhất về mặt phát biểu, vì nó là chỗ khoảng cách giữa
**thiết kế đích** và **hiện thực** rộng nhất. Theo Nguyên tắc 5 (§3.1.4 b), phần đã
có và phần chưa có được tách bạch ngay trong cách trình bày.

#### a. Cái đã có: ghim không gian nhãn

```
Tác vụ huấn luyện ──ghim──► Phiên bản danh mục của tổ chức
   training_jobs(tenant_id, registry_version) → registry_versions(tenant_id, version)
```

**Tính chất đạt được:** chạy lại một tác vụ huấn luyện sáu tháng sau vẫn dùng **đúng
tập nhãn của lần đầu**, kể cả khi danh mục đã thay đổi. Ảnh chụp phiên bản danh mục
có mã băm nội dung, nên phát hiện được nếu nó bị sửa.

Kèm theo, bảng ảnh chụp lớp tham gia (`training_job_classes`) lưu **tập lớp thực sự
tham gia sau ba cổng chặn**, cùng chỉ số lớp đã gán — không phải tập người dùng chọn.
Phân biệt này quan trọng: người dùng chọn 30 lớp nhưng chỉ 22 lớp qua được ba cổng
thì mô hình học trên 22 lớp, và bản ghi phải nói đúng con số 22.

#### b. Cái chưa có: ghim nội dung bộ dữ liệu

*Bảng 3-46: Khoảng cách giữa mô hình cần có và lược đồ hiện có*

| Thực thể cần cho vòng đời bộ dữ liệu | Trạng thái | Hệ quả |
|---|---|---|
| `datasets` — bộ dữ liệu là một thực thể có chủ | **Không có bảng** | Không có đối tượng để gắn siêu dữ liệu và quyền sở hữu |
| `dataset_versions` — phiên bản đóng băng | **Không có bảng** | Không đóng băng được *tập mẫu cụ thể* của một lần huấn luyện |
| `dataset_version_samples` — thành viên của phiên bản | **Không có bảng** | Không trả lời được *"phiên bản này gồm đúng những mẫu nào"* |
| `sample_revisions` — bản sửa của mẫu | **Không có bảng** | Mẫu sửa tại chỗ; một lần sửa siêu dữ liệu **đổi ngầm** nội dung của mọi bản phát hành trỏ tới nó |

Chín tệp định nghĩa cấu trúc cho nhóm bảng này **có trong kho mã nguồn** nhưng **chưa
bao giờ được áp** lên cơ sở dữ liệu đang chạy.

**Phát biểu đúng mức, và toàn bộ lập luận về khả năng tái lập của luận văn phải dừng
đúng ở đây:**

> Hệ thống ghim được **không gian nhãn** của một lượt huấn luyện vào một phiên bản
> danh mục bất biến, nên tập nhãn tái lập được. Hệ thống **chưa ghim được nội dung bộ
> dữ liệu**: tập mẫu cụ thể đã tham gia một lượt huấn luyện không được đóng băng
> thành một thực thể có phiên bản, nên hai lượt chạy cách nhau vài tháng có thể học
> trên hai tập mẫu khác nhau **mà không có gì ghi lại sự khác nhau đó**.

#### c. UC-D4 — Xuất bộ dữ liệu, và cổng đồng thuận

Đây là use case duy nhất trong nhóm đã hiện thực đầy đủ, nhưng **tên của nó phải đọc
đúng**: nó xuất **bộ dữ liệu tại thời điểm hiện tại theo một bộ lọc**, kèm bản kê và
mã băm — chứ không xuất một *phiên bản đã đóng băng từ trước*. Gọi việc thứ nhất bằng
tên của việc thứ hai là chỗ dễ overclaim nhất trong cả chương.

```
Yêu cầu xuất
   ├─ mở phạm vi tổ chức
   ├─ CỔNG ĐỒNG THUẬN: chỉ lấy mẫu có đồng thuận NGƯỜI KÝ ở mức tương ứng
   │     ↳ mẫu không đủ mức KHÔNG XUẤT HIỆN trong bản xuất — không phải bị đánh dấu
   ├─ duyệt tệp bằng HÀM DUYỆT DÙNG CHUNG có chốt chặn phạm vi  (§3.3.3.1 d)
   ├─ dựng bản kê: danh sách tệp + mã băm từng tệp
   ├─ đóng gói
   └─ ghi bản ghi kiểm toán
```

**Số liệu về hiệu lực thật của cổng đồng thuận**, đo ngày 18/08/2026 trên toàn kho:

| | Số mẫu | Tỉ lệ |
|---|---:|---:|
| Nối được vào một đồng thuận **còn hiệu lực** | **430** | 11,1 % |
| Có định danh người ký nhưng **không có** bản ghi đồng thuận | 1.244 | 32,2 % |
| Không có định danh người ký, **không nối được về nguyên tắc** | 2.186 | 56,6 % |

Nghĩa là: **cơ chế đồng thuận đã chạy được, nhưng 88,9 % kho mẫu hiện chưa phát hành
được theo đúng luật mà chính hệ thống cưỡng chế.**

Đây là một **hạn chế về dữ liệu, không phải về mã** — và phải viết đúng như vậy, vì
hai loại hạn chế này được đánh giá rất khác nhau. Một hạn chế về mã nghĩa là cơ chế
chưa làm được việc của nó; một hạn chế về dữ liệu nghĩa là cơ chế làm đúng việc của
nó, và kết quả đúng là *"phần lớn dữ liệu lịch sử chưa đủ điều kiện phát hành"*.

### 3.5.5. Chia sẻ, đồng thuận và quản trị dữ liệu

Đây là phần khác biệt nhất so với một công cụ thu dữ liệu thông thường.

#### a. Ba loại đồng thuận và ranh giới giữa chúng

Cấu trúc ba loại đã trình bày ở §3.1.4 g (Bất biến 1). Ở đây bổ sung phần thiết kế:

*Bảng 3-47: Ba loại đồng thuận và cơ chế thi hành*

| | (1) Chấp thuận văn bản nền tảng | (2) Đồng thuận của người ký | (3) Cam kết của người nhận dữ liệu |
|---|---|---|---|
| Chủ thể | Tài khoản | **Người ký** (chủ thể dữ liệu) | Người tải bản phát hành |
| Ghi vào | `user_consents` | `signer_consents` | *(chưa có bảng)* |
| Chi phối | Quyền dùng dịch vụ | **Đường phát hành dữ liệu** | Điều kiện tải về |
| Rút lại được | Không (là điều kiện dùng dịch vụ) | **Có** — `withdrawn_at` | — |
| Trạng thái | ✔ | ✔ | **○ thiết kế đích** |

**Vế (1) không suy ra vế (2).** Một tài khoản chấp thuận điều khoản dịch vụ không có
nghĩa người có bàn tay trong mẫu đã đồng ý cho dùng dữ liệu của mình. Đây là hệ quả
trực tiếp của phân biệt *tài khoản vận hành ≠ chủ thể dữ liệu*, và nó là chỗ mô hình
này khác một hệ thống thu dữ liệu thông thường.

#### b. Thang ba mức đồng thuận

Đồng thuận của người ký có **ba mức**, gắn với **người ký** chứ không gắn với tài
khoản. Mỗi đường phát hành dữ liệu đọc mức đồng thuận **trước khi** lấy mẫu; mẫu
không đủ mức thì **không xuất hiện** trong bản phát hành đó — không phải bị đánh dấu
rồi lọc sau. Phân biệt này quan trọng: *không xuất hiện* là một tính chất của truy
vấn; *bị đánh dấu rồi lọc sau* là một bước có thể quên.

#### c. Bốn nghĩa của "thu hồi", và hệ thống chỉ thi hành nghĩa thứ hai

*Bảng 3-48: Bốn nghĩa của "thu hồi"*

| # | Nghĩa | Đã thi hành? | Bằng cơ chế nào |
|---|---|---|---|
| 1 | Thu hồi quyền truy cập của một người | **Có** | Cơ chế cách ly và thu hồi vai |
| 2 | Gỡ khỏi các bản phát hành **mới** | **Có** | Cổng đồng thuận trên bốn đường dữ liệu |
| 3 | Xoá khỏi lưu trữ | **Không** | Là thao tác vận hành, làm tay |
| 4 | Thu hồi giấy phép **đã cấp** cho bên thứ ba | **Không** | Cần cơ chế pháp lý, không phải cơ chế kỹ thuật |

Hứa *"xoá là biến mất hoàn toàn"* là hứa nghĩa 3 và 4 trong khi chỉ làm nghĩa 2. Giao
diện nói thẳng điều này, và **có kiểm thử ghim đúng câu chữ đó** — để một lần sửa
giao diện về sau không vô tình biến một giới hạn thành một lời hứa. Đây là một cách
dùng kiểm thử ít gặp: kiểm thử ở đây không bảo vệ một hành vi, nó bảo vệ **một phát
biểu trung thực**.

#### d. Văn bản pháp lý bất biến

Bất biến sau khi công bố, **cưỡng chế bằng trigger ở tầng cơ sở dữ liệu** chứ không
bằng kiểm tra ở ứng dụng (RB-D8). Lý do: chấp thuận trỏ tới một cặp (loại, phiên
bản); đổi nội dung dưới chân nó biến **bằng chứng** thành **lời khẳng định suông**.

Một cờ riêng tách *"sửa lỗi chính tả"* khỏi *"đổi phạm vi xử lý dữ liệu"*; chỉ loại
thứ hai buộc chấp thuận lại. Không phân biệt hai loại này dẫn tới một trong hai thái
cực đều xấu: hoặc mọi người phải chấp thuận lại vì một dấu phẩy, hoặc một thay đổi
thực chất lọt qua như một sửa lỗi chính tả.

**Vật mang nội dung — phải phát biểu đúng, vì lược đồ hỗ trợ hai cách và quyển dễ
viết sai thành một cách.** Bảng văn bản pháp lý mang **đồng thời** ba nhóm cột: một
cột thân văn bản kèm định dạng; một nhóm cột tệp đính kèm (khoá lưu trữ, tên, kiểu
MIME, kích thước) cùng một cột chọn kho lưu trữ; và một địa chỉ liên kết. Cả hai cách
mang nội dung đều **neo vào cùng một cột mã băm nội dung**, và trigger bất biến kiểm
trên **cả thân văn bản lẫn mã băm**.

Trạng thái thật, đo ngày 18/08/2026: **cả bốn văn bản đang có hiệu lực đều mang thân
trong cơ sở dữ liệu**, kho lưu trữ là cục bộ, và **không văn bản nào dùng đường tệp
đính kèm**. Vì vậy câu đúng cho quyển là:

> *Định danh nghiệp vụ của một văn bản là cặp (loại, phiên bản); tính toàn vẹn neo
> vào mã băm nội dung; lược đồ hỗ trợ **hai** vật mang — thân trong cơ sở dữ liệu và
> tệp đính kèm — và **bốn văn bản đang có hiệu lực dùng vật mang thứ nhất**.*

Viết gọn thành *"chỉ lưu địa chỉ và mã băm, không lưu thân"* là **sai với cả bốn văn
bản hiện hành**; viết thành *"luôn lưu thân trong cơ sở dữ liệu"* là bỏ mất đường tệp
mà lược đồ đã mở sẵn cho các văn bản sau.

### 3.5.6. Quản trị và vận hành hệ thống

#### a. UC-E1 — Xác minh toàn vẹn nguồn sự thật

**Luồng công bố** (trên máy phát hành S5):

```
Dựng tạo tác ──► tính SHA-256 từng tệp ──► viết bản kê ──► ký bản kê (Ed25519)
                                                              │
                                                    đẩy lên kho lưu trữ ngoài
```

**Luồng xác minh** (trên mọi máy khác, lúc khởi động và khi quản trị viên yêu cầu):

```
Kéo bản công bố
   ├─ tính lại mã băm, đối chiếu bản kê      → lệch ⇒ DỪNG
   ├─ kiểm chữ ký phủ bản kê                 → hỏng/thiếu ⇒ DỪNG
   ├─ tra khoá ký trong danh sách tin cậy    → không tin cậy ⇒ DỪNG
   └─ hợp nhất theo nguyên tắc CHỈ ĐIỀN, KHÔNG XOÁ
```

Hợp đồng bốn vế và phân tích vế thứ ba ở §3.3.3.4 b.

**Một bài học thiết kế đáng ghi lại:** danh sách cột bắt buộc dùng để kiểm bản công bố
từng **thiếu sáu cột**. Hệ quả: một bản công bố có lược đồ thiếu vẫn **qua được khâu
xác minh**, rồi mới hỏng giữa chừng lúc nhập dữ liệu, khi ghi những cột mà bản kê chưa
từng hứa là có.

Đây là ví dụ điển hình của *"phép kiểm không phủ hết thứ mà nó bảo vệ"* — và nó là lý
do phép đo ở Chương 4 phải chạy qua **đúng đường tiêu thụ của ứng dụng**, không qua
một hàm trợ giúp viết riêng cho phép đo.

#### b. UC-E2 — Đối soát giữa nguồn sự thật và bản sao

Theo Bất biến 4 (§3.1.4 g), thẩm quyền chỉ có một chiều cho mỗi loại dữ liệu, và
đường ngược lại là **sửa chữa một lượt ghi hỏng giữa chừng**, không phải một thẩm
quyền thứ hai:

```
Đối soát định kỳ
   ├─ dòng có ở nguồn sự thật, thiếu ở CSDL   → điền vào CSDL      (chiều thẩm quyền)
   ├─ dòng có ở CSDL, thiếu ở nguồn sự thật   → nối vào nguồn sự thật
   │     ↳ ĐÂY LÀ SỬA MỘT LƯỢT GHI HỎNG GIỮA CHỪNG, không phải đảo thẩm quyền
   ├─ tệp có, không có dòng nào trỏ tới        → liệt kê riêng (tệp mồ côi)
   └─ dòng có, tệp không tồn tại               → liệt kê riêng (tệp thiếu)
```

Hai loại cuối được liệt kê **tách nhau**, vì chúng sửa theo **hai hướng ngược nhau**:
tệp mồ côi thì hoặc dựng lại hàng từ tệp mô tả đi kèm, hoặc dọn tệp; tệp thiếu thì
hoặc khôi phục từ bản sao lưu, hoặc đánh dấu hàng là hỏng. Gộp chúng vào một danh
sách "không khớp" là làm mất thông tin cần để sửa.

#### c. UC-E3 — Nhật ký kiểm toán theo phạm vi

Hai điểm thiết kế:

**Ghi nhật ký fail-closed.** Đường ghi kiểm toán **từ chối ghi** khi không có phạm vi
(NFR-S5). Lý do: một bản ghi kiểm toán không biết mình thuộc tổ chức nào là một bản
ghi không dùng được làm bằng chứng, và tệ hơn — nó có thể bị đọc nhầm sang tổ chức
khác. Thà không có bản ghi còn hơn có một bản ghi sai phạm vi.

**Hai tác nhân, hai phạm vi, cùng một use case.** Quản trị nền tảng xem nhật ký toàn
nền tảng; quản trị tổ chức xem nhật ký **trong phạm vi tổ chức mình**. Cùng một use
case với hai phạm vi khác nhau, cưỡng chế bằng chính cơ chế cách ly — không phải hai
use case, và cũng không phải hai bảng.

#### d. Quan trắc ba tầng

Chỉ số (Prometheus), biểu đồ và cảnh báo (Grafana), nhật ký (Loki + Promtail). Cảnh
báo **sống ở Grafana**, không có thành phần quản lý cảnh báo riêng — một quyết định
hợp với quy mô một máy chủ, và phải nói ra để không bị hiểu là thiếu sót.

**Hai bài học vận hành đáng đưa vào quyển:**

* **Nhãn phân loại nhật ký phải ít.** Đặt định danh tổ chức làm nhãn phân loại sinh
  ra số chuỗi nhật ký bằng *số tổ chức × số dịch vụ*, và làm hệ thống nhật ký sập.
  Thông tin phân biệt phải nằm ở **siêu dữ liệu có cấu trúc**, không nằm ở nhãn. Đây
  là một trường hợp mà giải pháp trực giác nhất — "gắn nhãn tổ chức để lọc cho tiện"
  — là giải pháp phá hệ thống.
* **Giá trị đặc biệt để tránh suy luận sai.** Một chỉ số trả về `-1` mang nghĩa
  *"không đo được"*, khác hẳn `0` nghĩa là *"đo được và bằng không"*. Không phân biệt
  hai giá trị này thì biểu đồ sẽ vẽ một đường bằng phẳng ở đáy và **không ai biết hệ
  thống đang mù**.

#### e. Sao lưu và khôi phục

Nguyên tắc: *một bản sao lưu chưa diễn tập khôi phục là một bản sao lưu chưa tồn tại*.
Hệ thống có chế độ diễn tập chạy được, khôi phục vào một cơ sở dữ liệu tạm.

**Hai bài học kỹ thuật:**

* Thứ tự thao tác phải là **kết xuất trước, nén sau**. Đảo lại thì một lỗi ở bước kết
  xuất bị che bởi bước nén.
* Công cụ liệt kê nội dung tệp sao lưu **không** phát hiện được tệp bị cụt — nó đọc
  phần đầu tệp và báo "hợp lệ". Phải kiểm bằng phương pháp **đọc hết nội dung**.

#### f. Bề mặt tích hợp và ranh giới với bên thứ ba

Khoá API là bề mặt duy nhất một hệ thống ngoài (S6) chạm vào dữ liệu tổ chức, nên nó
là **phép thử cuối cùng** của phát biểu "cách ly cưỡng chế ở tầng cơ sở dữ liệu":

* Khoá lưu dạng **mã băm**; hệ thống không có đường đọc lại giá trị khoá.
* Khoá mang **phạm vi tổ chức**, và mọi yêu cầu dùng khoá đi qua **cùng** khối quản
  lý ngữ cảnh như yêu cầu của người dùng — không có đường tắt riêng cho khoá API.
* Điểm nhận webhook có lịch sử gửi chịu chính sách cách ly, nên một tổ chức không đọc
  được lịch sử gửi của tổ chức khác.

**Một cơ chế cách ly chỉ đúng khi người dùng ngồi trước trình duyệt là một cơ chế
chưa đủ** — đó là lý do bề mặt này được kiểm cùng ma trận đối kháng ở Chương 4.

> ### ▣ HÌNH 3-18 — Cơ chế công bố và xác minh nguồn sự thật
> **Loại:** sơ đồ hoạt động
> **Phải thể hiện:** hai luồng công bố và xác minh đặt cạnh nhau; **ba điểm DỪNG**
> đánh dấu nổi bật; ranh giới giữa máy phát hành (**có khoá riêng**) và máy tiêu thụ
> (**chỉ có khoá công khai**); nguyên tắc chỉ-điền vẽ bằng mũi tên một chiều vào cơ
> sở dữ liệu.
> **Chú thích:** *Hình 3-18: Cơ chế công bố và xác minh nguồn sự thật ký số.*

> ### ▣ HÌNH 3-19 — Ba loại đồng thuận và cổng phát hành dữ liệu
> **Loại:** sơ đồ hoạt động
> **Phải thể hiện:** ba loại đồng thuận của Bảng 3-47 nối vào ba chỗ khác nhau trong
> vòng đời; **cổng đồng thuận đặt ở bước CHỌN mẫu**, không đặt ở bước lọc sau — đây
> là điểm phải nhìn thấy được từ hình; nhánh rút đồng thuận vẽ **ngược chiều** dòng
> chảy chính.
> **Chú thích:** *Hình 3-19: Ba loại đồng thuận, cổng phát hành, và nhánh rút đồng
> thuận chạy ngược dòng.*

---

## 3.6. Cài đặt giải pháp

### 3.6.1. Tổ chức cài đặt hệ thống

#### a. Công nghệ sử dụng và lý do chọn

*Bảng 3-49: Công nghệ theo tầng*

| Tầng | Công nghệ | Lý do chọn, liên hệ với ràng buộc |
|---|---|---|
| Giao diện | React + TypeScript, ứng dụng đơn trang | Kiểu tĩnh bắt được lỗi hợp đồng dữ liệu ở thời điểm dựng, không ở thời điểm chạy |
| Trích đặc trưng tại máy khách | MediaPipe biên dịch sang WebAssembly | Điều kiện để thoả RB-D5 và NFR-P2: không có WebAssembly thì phải gửi video lên máy chủ |
| Dịch vụ API | Python + FastAPI | Cùng ngôn ngữ với phần xử lý dữ liệu và huấn luyện — một ngôn ngữ ít hơn là một nguồn lỗi ít hơn |
| Cơ sở dữ liệu | PostgreSQL | **Điều kiện tiên quyết của RB-D3**: cơ chế bảo mật mức hàng là thứ làm cách ly cưỡng chế được ở tầng CSDL |
| Hàng đợi tác vụ | Celery + Redis | Đủ cho một máy chủ; Redis đồng thời làm bộ đếm hạn mức và danh sách từ chối token |
| Học sâu | PyTorch | Hệ sinh thái GPU và tính khả dụng của mô hình chuỗi thời gian |
| Đóng gói | Docker Compose | RB-T1: một máy chủ, không có cụm — không cần bộ điều phối container |
| Quan trắc | Prometheus + Grafana + Loki | Cảnh báo sống ở Grafana; không có thành phần quản lý cảnh báo riêng |

**Một lựa chọn đáng nói riêng: PostgreSQL không phải một lựa chọn tuỳ ý.** Ràng buộc
RB-D3 yêu cầu cách ly cưỡng chế ở tầng cơ sở dữ liệu, và cơ chế bảo mật mức hàng là
thứ làm điều đó khả thi. Nếu đổi sang một hệ quản trị không có cơ chế tương đương,
toàn bộ thiết kế bốn tầng ở §3.3.3.1 sụp về hai tầng, và đóng góp lõi của luận văn
mất chỗ đứng.

#### b. Tổ chức mã nguồn

```
backend/app/
  routers/        27 bộ định tuyến, 224 điểm cuối
  storage/        tầng truy cập dữ liệu — NƠI DUY NHẤT đặt ngữ cảnh tổ chức
  processing/     trích đặc trưng, cắt cửa sổ, tăng cường, chấm chất lượng
  sot/            công bố và xác minh nguồn sự thật
  training/       điều phối huấn luyện
  cli/            công cụ dòng lệnh: di trú lược đồ, cấp vai CSDL
backend/tests/    153 tệp kiểm thử
backend/migrations/  các bước di trú một chiều
frontend/src/
  pages/          71 tệp màn hình
  components/     thành phần dùng lại
  api/            lớp gọi API, ánh xạ kiểu với backend
  i18n/           chuỗi hiển thị — không có chuỗi cứng trong mã
scripts/          công cụ vận hành: sao lưu, đối soát, kiểm độ tươi triển khai, chạy kiểm thử
docs/             tài liệu thiết kế, đặc tả, và quyển luận văn
```

**Quy mô**, đếm lại ngày 18/08/2026:

*Bảng 3-50: Quy mô mã nguồn*

| Phần | Số tệp | Số dòng |
|---|---:|---:|
| Dịch vụ (Python, `backend/app`) | 164 | **62.817** |
| Giao diện (TypeScript, `frontend/src`) | 227 | **49.716** |
| Kiểm thử (Python, `backend/tests`) | 153 | **42.544** |

Tỉ lệ mã kiểm thử trên mã dịch vụ là **0,68 : 1**. Con số này là **hệ quả trực tiếp**
của một nguyên tắc phương pháp (RB-D9) chứ không phải một mục tiêu tự đặt: mỗi khẳng
định trung tâm phải có **một phản chứng**, nên phần lớn hợp đồng được ghim bằng **hai**
ca kiểm thử thay vì một — một ca chứng minh việc hợp lệ làm được, một ca chứng minh
việc không hợp lệ bị chặn.

#### c. Một quy ước có ý nghĩa kiến trúc

**Ngữ cảnh tổ chức được đặt ở đúng một khối quản lý ngữ cảnh** trong tầng truy cập dữ
liệu. Không có đường nào khác đặt được ngữ cảnh này.

Đây là điều làm **tầng 3** của cơ chế cách ly (§3.3.3.1 b) khả thi: nếu mỗi hàm tự
đặt ngữ cảnh theo cách riêng, không ai bảo đảm được lệnh gán luôn giới hạn trong giao
dịch. Quy ước "một cửa duy nhất" ở đây không phải một sở thích về phong cách mã — nó
là **điều kiện để một bảo đảm an toàn thành đúng**.

Nguyên tắc khái quát, và nó lặp lại ở ba chỗ khác trong hệ thống (hàm duyệt tệp dùng
chung ở §3.3.3.1 d, cửa duy nhất phân giải nguồn dữ liệu huấn luyện, cửa duy nhất
chạy kiểm thử ở §3.6.3):

> **Một bảo đảm chỉ mạnh bằng số lối vào của nó.** Khi một tính chất phải đúng ở mọi
> nơi, cách bảo đảm hiệu quả nhất không phải là kiểm nó ở mọi nơi, mà là làm cho chỉ
> có **một** nơi có thể vi phạm.

#### d. Giao diện người dùng

Giao diện là ứng dụng đơn trang, chia ba khu vực theo quyền: khu vực người dùng, khu
vực tổ chức, và console quản trị nền tảng. Ba quy ước được giữ nhất quán:

* **Bộ biểu tượng đồng nhất** — 70 biểu tượng vector, **không dùng emoji** trong giao
  diện. Emoji hiển thị khác nhau giữa các hệ điều hành và không đổi màu theo chủ đề.
* **Không có chuỗi cứng trong mã.** Mọi chuỗi hiển thị đi qua lớp đa ngôn ngữ
  (NFR-M7), và độ phủ được kiểm bằng công cụ trong cổng trước triển khai.

  **Bài học đáng ghi:** độ phủ này từng được báo cáo là 100 % và **sai hai lần** —
  công cụ đo bỏ sót các chuỗi nằm trong **biểu thức điều kiện** và trong **chuỗi
  mẫu**. Bài học khái quát: *một công cụ đo tự chế có thể sinh ra con số đẹp cho đúng
  thứ nó không đo được.* Cách sửa là mở rộng công cụ và bổ sung chỉ thị có biên cho
  các ngoại lệ có chủ ý, không phải hạ chuẩn.
* **Vỏ console quản trị KHÔNG phải hàng rào quyền.** Việc một trang nằm dưới đường
  dẫn quản trị **không tự nó chặn ai**; quyền vẫn kiểm ở tầng dịch vụ. Nhầm hai thứ
  này là một lỗ hổng kinh điển: giấu một nút bấm không phải là chặn một điểm cuối.

> ### ▣ HÌNH 3-20 — Giao diện thu mẫu trực tiếp
> **Loại:** ảnh chụp màn hình
> **Phải thể hiện:** khung camera có **vẽ chồng điểm mốc bàn tay theo thời gian
> thực**; bảng chọn lớp – ngôn ngữ – phương ngữ – vùng miền; chỉ báo số bàn tay yêu
> cầu; nút thu và vùng xem lại.
> **Chú thích:** *Hình 3-20: Màn hình thu mẫu trực tiếp với điểm mốc bàn tay vẽ chồng
> theo thời gian thực.*

> ### ▣ HÌNH 3-21 — Giao diện danh mục lớp và chi tiết lớp
> **Phải thể hiện:** danh sách lớp kèm số mẫu và **cột vùng miền**; màn chi tiết một
> lớp với danh sách phiên thu, chỉ số chất lượng và thao tác quản trị.
> **Chú thích:** *Hình 3-21: Màn hình danh mục lớp và chi tiết một lớp.*

> ### ▣ HÌNH 3-22 — Console quản trị và trang quản lý tổ chức
> **Phải thể hiện:** thanh bên ba tầng (nền tảng / tổ chức / cài đặt); trang quản lý
> tổ chức hoặc trang nhật ký kiểm toán làm ví dụ tiêu biểu.
> **Chú thích:** *Hình 3-22: Console quản trị nền tảng.*

### 3.6.2. Cài đặt các cơ chế cốt lõi

Mục này trình bày cài đặt của năm cơ chế mang đóng góp của luận văn. Với mỗi cơ chế:
**cài đặt thế nào**, **sai ở đâu thì hỏng**, và **kiểm bằng gì**.

#### a. Cơ chế cách ly bốn tầng

**Tầng 1 và 2 — cột phân biệt và chính sách.** Toàn bộ 35 chính sách dùng cùng một
khuôn, và việc **dùng cùng một khuôn** là một quyết định cài đặt: một chính sách viết
khác đi là một chính sách phải rà soát riêng.

```sql
CREATE POLICY tenant_isolation ON <bảng>
  USING (
    (current_setting('app.system_scope', true) = 'on')
    OR (tenant_id = current_setting('app.tenant_id', true))
  );
ALTER TABLE <bảng> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <bảng> FORCE ROW LEVEL SECURITY;
```

Riêng bảng `roles` thêm nhánh `tenant_id IS NULL` để danh mục vai nền tảng đọc được
từ mọi tổ chức. Đây là **ngoại lệ duy nhất về hình dạng chính sách**, và nó được nêu
ra chứ không giấu.

**Tầng 3 — một khối quản lý ngữ cảnh duy nhất.** Hình dạng cài đặt:

```
mở giao dịch
   SET LOCAL app.tenant_id = <định danh tổ chức>      ← LOCAL, không phải SET thường
   ... mọi truy vấn của yêu cầu này ...
đóng giao dịch  → ngữ cảnh tự biến mất cùng giao dịch
```

**Sai ở đâu thì hỏng:** dùng `SET` thay vì `SET LOCAL` làm giá trị **dính lại trên
kết nối**, và khi kết nối được trả về bể rồi cấp cho yêu cầu kế tiếp, yêu cầu đó chạy
với ngữ cảnh của tổ chức trước. Lỗi này **không sinh ra thông báo nào**.

**Tầng 4 — cấp vai cơ sở dữ liệu.** Có một công cụ dòng lệnh riêng để cấp vai
`voya_app` với đúng bộ quyền cần thiết. Ba tính chất phải đồng thời đúng, và cả ba
kiểm được bằng truy vấn siêu dữ liệu:

| Tính chất | Vì sao cần |
|---|---|
| Không có quyền thay đổi cấu trúc | Lệnh vô hiệu hoá chính sách là một lệnh cấu trúc |
| **Không phải siêu người dùng** | Siêu người dùng được miễn trừ chính sách **vô điều kiện** |
| **Không phải chủ sở hữu bảng** | Chủ sở hữu tự bật/tắt được cờ cưỡng chế trên bảng của mình |

**Ba cái bẫy cho kết quả "đạt" giả** khi kiểm cơ chế này, và cả ba đã gặp:

1. **Chạy phép kiểm dưới vai quản trị.** Vai quản trị được miễn trừ chính sách, nên
   mọi phép kiểm đều "đạt" — và không kiểm gì cả. Phép kiểm phải chạy dưới đúng vai
   `voya_app`.
2. **Quên rằng sentinel chỉ nhận đúng một giá trị.** Đặt `app.system_scope = 'true'`
   không bật phạm vi hệ thống; nó được đọc thành "không bật". Một phép kiểm dựa vào
   giá trị sai sẽ kết luận sai theo hướng ngược lại.
3. **Kiểm bằng đường đọc mà không kiểm đường ghi.** Chính sách chặn đọc chéo tổ chức
   không tự động chặn **ghi** chéo tổ chức; hai vế phải kiểm riêng.

#### b. Cổng truy cập mặc định từ chối

Cài đặt ở tầng trung gian, chạy **trước** bộ định tuyến:

```
Yêu cầu tới
   ├─ đường dẫn có trong DANH SÁCH NGOẠI LỆ CÔNG KHAI?
   │     ├─ có  → cho qua
   │     └─ không → BẮT BUỘC xác thực
   ├─ phân giải phiên → xác định tài khoản
   ├─ xác định tổ chức của yêu cầu → mở phạm vi
   └─ chuyển tới bộ định tuyến
```

**Sai ở đâu thì hỏng:** danh sách ngoại lệ công khai là **chỗ duy nhất còn lại có thể
sai**, nên nó phải được rà soát định kỳ và phải có một ca kiểm thử **liệt kê toàn bộ
điểm cuối** rồi đối chiếu với danh sách đó. Không có ca kiểm thử này thì một đường dẫn
thêm vào danh sách vì lý do gỡ lỗi sẽ nằm lại đó vĩnh viễn.

#### c. Cài đặt cổng đồng thuận và giam hãm đầu ra

**Cổng đồng thuận** đặt ở bước **chọn** mẫu, không ở bước lọc sau. Cài đặt bằng một
phép nối vào bảng đồng thuận người ký với điều kiện *chưa rút*, nên mẫu không đủ điều
kiện **không bao giờ xuất hiện trong tập kết quả** — thay vì xuất hiện rồi bị bỏ.

**Giam hãm đầu ra huấn luyện** là một nhóm bản vá riêng, và nó đáng ghi lại vì bốn
lỗi tìm được đều thuộc loại *"phạm vi được truyền đúng nhưng vẫn rò"*:

*Bảng 3-51: Bốn lỗi giam hãm đầu ra và bản chất của chúng*

| # | Lỗi | Bản chất |
|---|---|---|
| 1 | Bảng tác vụ huấn luyện giữ trong bộ nhớ **toàn tiến trình** → tổ chức B đọc được tác vụ của A, gồm cả đường dẫn điểm kiểm tra mô hình | Bộ nhớ tiến trình **không** chịu chính sách cách ly. Lượt nạp lại lúc khởi động nạp tác vụ của **mọi** tổ chức, nên lỗ mở sẵn sau mỗi lần khởi động lại |
| 2 | Kết nối dài chạy **ngoài mọi phạm vi** | Tầng trung gian đặt phạm vi chỉ chạy cho yêu cầu HTTP; giao thức khác đi vòng qua nó |
| 3 | Đường dự phòng gắn điểm kiểm tra của tổ chức khác vào một tác vụ | Sau bước gắn sai, **mọi** phép kiểm phạm vi phía sau đều "đạt", vì hàng tác vụ thật sự thuộc về tổ chức gọi |
| 4 | Lượt dọn định kỳ xoá điểm kiểm tra xuyên tổ chức | Rủi ro **toàn vẹn**, theo lịch — nguy hiểm hơn rò rỉ vì nó phá dữ liệu |

**Bài học chung của bốn lỗi:** ba trong bốn lỗi nằm ở chỗ dữ liệu **rời khỏi phạm vi
của cơ sở dữ liệu** — bộ nhớ tiến trình, kết nối dài, hệ tệp. Cơ chế cách ly ở tầng
cơ sở dữ liệu **không tự lan sang** ba nơi đó, và mỗi nơi cần một cơ chế riêng. Đây là
lý do phát biểu về cách ly trong quyển luôn kèm mệnh đề *"cho mọi tài nguyên nằm
trong cơ sở dữ liệu"*.

Sau bốn bản vá, **không còn năng lực xuyên tổ chức nào đo được** trên nhóm này. Phần
còn lại là **nợ gia cố, không phải lỗ hổng**: tên tệp điểm kiểm tra chưa mang định
danh tổ chức, và thư mục đầu ra còn phẳng.

#### d. Cài đặt ba cổng chặn huấn luyện

*Bảng 3-52: Ba cổng chặn và điểm áp dụng*

| Cổng | Hỏi gì | Áp ở đâu | Hỏng thì hậu quả |
|---|---|---|---|
| Đồng thuận | Người ký cho phép dùng ở mức phát hành này không? | Lúc **chọn** mẫu | Phát hành vượt phạm vi được phép |
| Sàn số mẫu mỗi lớp | Lớp này đủ mẫu để chia tập không? | **Trước** khi đánh chỉ số lớp | Tập kiểm thử rỗng; chỉ số vô nghĩa |
| Hạn mức tổ chức | Tổ chức còn hạn mức tính toán không? | Lúc **xếp hàng** | Một tổ chức chiếm hết GPU chung |

Ba cổng hỏi **ba câu khác nhau** và **không thay thế được cho nhau**.

**Một chi tiết thứ tự có hậu quả thật: sàn số mẫu phải áp TRƯỚC khi đánh chỉ số lớp.**
Nếu đánh chỉ số trước rồi mới loại lớp, chỉ số lớp sẽ **nhảy cóc**, và mô hình được
huấn luyện trên một không gian nhãn khác với không gian nhãn lúc suy luận — một lỗi
**không sinh ra thông báo nào**, chỉ sinh ra kết quả sai.

**Phân biệt thứ hai đáng giữ: lọc lúc chia tập ≠ từ chối lúc chạy.** Lọc là loại lớp
không đủ điều kiện rồi **tiếp tục**; từ chối là **dừng cả tác vụ**. Hệ thống làm cả
hai, ở hai chỗ khác nhau, và phải nói rõ chỗ nào làm gì — nếu không, người dùng sẽ
tưởng mô hình được huấn luyện trên đúng tập lớp mình chọn.

#### e. Cài đặt xác minh nguồn sự thật

Điểm cài đặt đáng nói nhất: **hàm xác minh trả về tên khoá đã đăng ký**, không trả về
một giá trị đúng/sai. Chữ ký hợp lệ theo khoá nào là **một phần của kết quả**, không
phải một câu hỏi phụ mà nơi gọi phải nhớ hỏi thêm.

Đây là một kỹ thuật thiết kế API đáng khái quát: *khi một câu trả lời "có" chỉ có
nghĩa nếu kèm theo một bối cảnh, đừng trả về "có" — hãy trả về bối cảnh đó.* Một hàm
trả `true` mời gọi nơi gọi quên hỏi "theo khoá nào"; một hàm trả tên khoá thì không.

### 3.6.3. Triển khai hệ thống

#### a. Quy trình triển khai

```
scripts/deploy.sh
   ├─ PRE-FLIGHT — chạy TRƯỚC khi dựng ảnh
   │     ├─ kiểm biến môi trường bắt buộc
   │     ├─ kiểm đường dẫn cơ sở khớp với địa chỉ truy cập  (RB-T3)
   │     └─ dò GPU → chọn overlay tương ứng
   ├─ dựng ảnh
   ├─ sot-init  → xác minh nguồn sự thật  → thất bại ⇒ DỪNG CẢ STACK
   ├─ dựng cơ sở dữ liệu (chỉ THÊM) + kiểm phiên bản lược đồ
   ├─ khởi động 14 dịch vụ thường trực
   └─ kiểm sức khoẻ 13/13 dịch vụ
```

**Vì sao pre-flight chạy trước bước dựng ảnh:** dựng ảnh mất nhiều phút. Phát hiện
thiếu một biến môi trường **sau** khi dựng xong là lãng phí toàn bộ thời gian đó, và
tệ hơn — nó tạo áp lực bỏ qua phép kiểm.

#### b. Bốn chốt chặn vận hành, và sự cố sinh ra từng cái

Bốn cơ chế dưới đây đều ra đời sau một sự cố thật. Nêu cả sự cố lẫn cơ chế, vì một
chốt chặn không có sự cố đi kèm trông giống một sự cẩn thận thừa.

*Bảng 3-53: Bốn chốt chặn vận hành*

| Chốt chặn | Sự cố sinh ra nó | Cơ chế |
|---|---|---|
| **Chốt chặn đích di trú** | Một lệnh di trú chạy nhầm lên cơ sở dữ liệu **sản xuất**, áp một lược đồ dở dang rồi đóng dấu phiên bản | Biến `EXPECTED_DATABASE` phải khớp tên cơ sở dữ liệu trong chuỗi kết nối thì lệnh mới chạy (NFR-M5) |
| **Từ chối khởi động khi lệch lược đồ** | Mã mới chạy trên lược đồ cũ, hỏng giữa chừng ở một đường ít dùng | So sánh phiên bản lược đồ với hằng số trong mã; lệch **theo cả hai chiều** đều từ chối khởi động (NFR-M4) |
| **Cửa duy nhất chạy kiểm thử** | Bộ kiểm thử **ghi vào cơ sở dữ liệu sản xuất**, và một lần khác ghi vào tệp nguồn sự thật thật | `scripts/run_tests.sh` là cửa duy nhất; nó dựng môi trường kiểm thử riêng và chặn nếu đích trỏ vào cơ sở dữ liệu sản xuất (NFR-M6) |
| **Kiểm độ tươi triển khai** | Container báo "khoẻ" trong khi đang chạy **mã cũ** | Công cụ riêng bắt **ba kiểu lệch** giữa mã đang chạy và mã nguồn (NFR-R6) |

**Chốt chặn thứ tư đáng phân tích thêm**, vì nó chống lại một loại nhầm lẫn phổ biến:
**"khoẻ" không đồng nghĩa "đúng phiên bản"**. Một container chạy mã cũ vẫn trả về mã
trạng thái 200 cho mọi phép kiểm sức khoẻ. Ngoài ra, một ảnh duy nhất chống lưng cho
**năm dịch vụ**, nên một lần cập nhật quên tạo lại một trong năm dịch vụ đó sẽ để lại
một dịch vụ chạy mã cũ trong khi bốn dịch vụ kia đã mới.

#### c. Hai loại thay đổi lược đồ

Đây là cài đặt của NFR-M3, và ranh giới giữa hai loại phải rõ:

| | Bước tự động lúc khởi động | Lệnh di trú tường minh |
|---|---|---|
| Được làm gì | **Chỉ THÊM**: thêm bảng, thêm cột, thêm chỉ mục | Mọi thay đổi **một chiều**: đổi kiểu, gỡ cột, gỡ chỉ mục, chuyển đổi dữ liệu |
| Chạy khi nào | Mỗi lần khởi động | Chỉ khi được gọi tường minh |
| Chốt chặn | — | `EXPECTED_DATABASE` + sao lưu trước |
| Kiểm bằng | **Ba lần khởi động liên tiếp** phải cho cùng một lược đồ | Hậu điều kiện của từng bước |

**Vì sao kiểm bằng ba lần khởi động liên tiếp:** một bước tự động viết sai có thể
**thêm rồi lại thiếu** ở lần chạy sau, và lỗi đó chỉ lộ ra khi so hai lần chạy. Lần
thứ ba xác nhận trạng thái đã ổn định.

**Một sự cố đáng ghi lại về loại thứ nhất:** bước tự động lúc khởi động từng **thiếu
hai bảng, bảy khoá ngoại và mười bốn cột** so với cơ sở dữ liệu đang chạy — nghĩa là
một máy dựng mới sẽ có lược đồ **khác** máy đang chạy, và khác **trong im lặng**. Tệ
hơn, một cột có **hai giá trị mặc định trái ngược nhau** ở hai nhánh mã: nhánh tạo
bảng và nhánh thêm cột. Cơ sở dữ liệu dựng mới đi theo nhánh thứ nhất, cơ sở dữ liệu
nâng cấp đi theo nhánh thứ hai, và hai máy hành xử khác nhau trên cùng một mã.

**Bài học:** *một bước dựng lược đồ tự động phải được kiểm bằng cách dựng từ đầu và
so với môi trường thật, chứ không bằng cách quan sát rằng ứng dụng vẫn chạy.*

#### d. Hạn mức tài nguyên và tương thích phần cứng

Ràng buộc RB-T1 (6 nhân, 12 GB RAM, một GPU) buộc mỗi container phải có **hạn mức bộ
nhớ tường minh**, để một dịch vụ rò bộ nhớ không giết cả máy. Cấu hình sản xuất là
một tệp phủ riêng chứa các hạn mức đó cùng cấu hình bộ đệm.

**Hai cái bẫy vận hành đã gặp, và cả hai thuộc loại "cấu hình bị đánh rơi trong im
lặng":**

* **Gọi công cụ điều phối container mà không kèm tệp phủ GPU** thì GPU bị bỏ, và dịch
  vụ huấn luyện chạy trên CPU — chậm hàng chục lần nhưng **không báo lỗi**. Cách sửa:
  ghi danh sách tệp cấu hình vào biến môi trường để mọi lệnh đều mang đủ.
* **Lệnh khởi động lại không đọc lại tệp cấu hình.** Đổi một biến môi trường rồi khởi
  động lại container thì container vẫn chạy với giá trị cũ — phải **tạo lại** container
  chứ không phải khởi động lại. Đây là chỗ trực giác sai: "khởi động lại" nghe như
  "đọc lại mọi thứ", nhưng không phải.

#### e. Diễn tập triển khai trên máy thứ hai

Đây là phép kiểm của NFR-M1, và nó **đã thực hiện**. Toàn bộ hệ thống dựng lại được
từ mã nguồn trên một máy sạch bằng một lệnh, với kịch bản triển khai tự dò cấu hình
GPU và chọn tệp phủ tương ứng.

Diễn tập này có giá trị vượt ra ngoài việc chứng minh một yêu cầu: nó là **cách duy
nhất** phát hiện những phụ thuộc ngầm vào trạng thái của máy đang chạy — một tệp ai
đó tạo tay, một biến môi trường đặt trong phiên làm việc, một bảng thêm cột bằng câu
lệnh trực tiếp. Sự cố "lược đồ khởi động thiếu hai bảng" ở §c chính là do diễn tập
này phát hiện.

---

## 3.7. Tổng kết chương

### a. Những gì chương này đã trình bày

Chương này đã đi từ **phân tích yêu cầu** tới **hệ thống đang chạy**, qua bốn chặng:

1. **Phân tích và mô hình hoá** (§3.1): bài toán phát biểu lại từ góc nhìn thiết kế
   quanh một nguyên tắc duy nhất — *ranh giới cách ly phải nằm ở tầng thấp hơn tầng
   mà lập trình viên có thể quên*; mười tác nhân người và sáu tác nhân hệ thống; tám
   nhóm nghiệp vụ cài đặt thành 27 bộ định tuyến với 224 điểm cuối; và một **mô hình
   use case thu gọn theo phạm vi luận văn gồm 24 use case**, rút ra từ danh mục 75 use
   case của sản phẩm theo năm nguyên tắc dựng mô hình.
2. **Kiến trúc** (§3.2, §3.3): sáu phân hệ chức năng; 15 dịch vụ container với ba lý
   do tách dịch vụ nêu rõ; và **bốn quyết định kiến trúc lớn**, mỗi quyết định đặt
   cạnh các phương án bị loại, tiêu chí chọn, và **cái giá phải trả**.
3. **Dữ liệu** (§3.4): 59 bảng và 1 khung nhìn theo bảy nhóm mô-đun; 24 khoá ngoại
   ghép giữ phạm vi; sáu trigger cưỡng chế bất biến; ba miền dữ liệu và ranh giới
   giữa chúng.
4. **Chức năng và cài đặt** (§3.5, §3.6): thiết kế của sáu phân hệ; cài đặt của năm cơ
   chế cốt lõi kèm *"sai ở đâu thì hỏng"*; và bốn chốt chặn vận hành cùng sự cố sinh
   ra từng cái.

### b. Đóng góp thiết kế trung tâm

**Bốn tầng cưỡng chế cách ly** (§3.3.3.1 b) là đóng góp lõi. Điểm đáng bảo vệ không
phải là "có bốn tầng cho chắc", mà là: **mỗi tầng bịt đúng một lối vòng mà ba tầng
còn lại để hở**, và bỏ bất kỳ tầng nào cũng để lại một lỗ cụ thể nêu tên được.

*Bảng 3-54: Bốn tầng và lối vòng mà mỗi tầng bịt*

| Tầng | Bịt lối vòng nào | Bỏ tầng này thì hở gì |
|---|---|---|
| 1. Cột phân biệt | *(không bịt gì — là điều kiện cần)* | Không có gì để so sánh |
| 2. Chính sách mức hàng | Truy vấn quên điều kiện lọc | Mọi truy vấn viết thiếu đều rò |
| 3. Phạm vi giao dịch | Ngữ cảnh dính lại trên kết nối, rò sang yêu cầu kế tiếp | Một người dùng đọc được dữ liệu của người trước trên cùng kết nối |
| 4. Tách vai cơ sở dữ liệu | Ứng dụng tự vô hiệu hoá chính sách | Bảo đảm biến thành **lời khuyên** |

Tầng thứ tư là tầng biến cơ chế từ *lời khuyên* thành *bảo đảm*, và nó là tầng hay bị
bỏ nhất trong các hệ thống tương tự — vì nó không sửa một lỗ hổng đang thấy, mà loại
bỏ **khả năng** tạo ra lỗ hổng đó.

### c. Năm giới hạn thiết kế, nêu thẳng tại chỗ phát sinh

Năm giới hạn dưới đây đã được nêu ngay tại mục tương ứng, không dồn sang phần Kết
luận. Tập hợp lại ở đây để chúng đọc được như một danh sách.

*Bảng 3-55: Năm giới hạn thiết kế*

| # | Giới hạn | Nêu ở | Bản chất |
|---|---|---|---|
| 1 | Hai cấp phạm vi dưới (không gian làm việc, dự án) đã có bề mặt API nhưng **chưa phân vùng dữ liệu** và **chưa đổi được kết quả kiểm quyền lúc chạy** | §3.3.3.2 c | Hiện thực chưa đầy đủ, đã có bề mặt |
| 2 | **Chưa ghim được nội dung bộ dữ liệu** — chỉ ghim được không gian nhãn; bốn bảng cần thiết **không tồn tại** | §3.1.4 h, §3.5.4 b | **Chưa hiện thực** — là thiết kế đích |
| 3 | Tính lũy đẳng **chưa đồng đều** ở đường xử lý nền, đặc biệt ở bước tải lên kho ngoài | §3.3.3.3 b, §3.5.3 e | Hạn chế về độ tin cậy, không về năng lực |
| 4 | **Đơn điệu phiên bản** của nguồn sự thật **chưa được cưỡng chế**; và tính bất biến của phiên bản danh mục là **quy ước**, không có trigger | §3.3.3.4 c, d | Cơ chế yếu hơn mức phát biểu tự nhiên gợi ra |
| 5 | Đường **đồng bộ ra bảng tính ngoài** chạy bằng quyền hệ thống, **không mang phạm vi tổ chức** | §3.4.3 f | Ranh giới thiết kế bị vượt; phơi nhiễm hôm nay bằng không |

Ba giới hạn đầu là **khoảng cách giữa mô hình đích và hiện thực**; hai giới hạn cuối
là **cơ chế yếu hơn mức mà một cách phát biểu tự nhiên gợi ra**. Hai loại này khác
nhau, và việc phân biệt chúng là một phần của việc báo cáo trung thực.

### d. Ba bài học phương pháp rút ra từ quá trình thiết kế

Ba bài học dưới đây vượt ra ngoài hệ thống cụ thể này, và chúng là kết quả nghiên cứu
theo đúng nghĩa — chúng được rút ra từ những lỗi thật, đo được:

1. **Một cơ chế an toàn ở tầng dưới không tự động làm tầng trên an toàn.** Cách ly
   fail-closed ở tầng cơ sở dữ liệu vẫn bị tầng ứng dụng diễn giải sai thành
   fail-open, khi mã đọc *"0 hàng"* thành *"không có gì"* thay vì *"chưa có ngữ cảnh"*
   (§3.4.1 b). Lỗi này đã lặp lại ba lần trong hai ngày.
2. **"Commit đã có" không phải bằng chứng cho một cam kết về hành vi hệ thống.** Một
   chỉ mục cũ còn sót trên cơ sở dữ liệu đang chạy đã vô hiệu hoá một cam kết trong
   khi mã đã hoàn toàn đúng (§3.4.1 d). Bằng chứng đúng loại là một **cặp thao tác có
   đối chứng**, không phải một mã băm commit.
3. **Một bảo đảm chỉ mạnh bằng số lối vào của nó.** Khi một tính chất phải đúng ở mọi
   nơi, cách hiệu quả nhất không phải là kiểm nó ở mọi nơi, mà là làm cho chỉ **một**
   nơi có thể vi phạm (§3.6.1 c). Nguyên tắc này xuất hiện bốn lần trong hệ thống, và
   mỗi lần nó ra đời sau một lỗi mà một chốt chặn viết riêng lẻ đã bỏ sót.

### e. Nối sang Chương 4

Chương này đưa ra các khẳng định; Chương 4 kiểm chứng chúng bằng các phép đo **có khả
năng thất bại** và có **đối chứng dương** (RB-D9). Bảng dưới đây là bản đồ giữa hai
chương, để mỗi khẳng định thiết kế truy được tới đúng phép đo tương ứng.

*Bảng 3-56: Từ khẳng định thiết kế tới phép đo ở Chương 4*

| Khẳng định ở Chương 3 | Phép đo ở Chương 4 |
|---|---|
| Cách ly cưỡng chế ở tầng CSDL (§3.3.3.1) | §5.2 — ma trận đối kháng qua API, kèm đối chứng dương |
| Độ trễ đọc dưới 100 ms ở phân vị 95 (§3.1.5.1) | §5.3 — đo độ trễ cơ sở, ba lượt chạy độc lập |
| Hiệu quả lưu trữ của biểu diễn điểm mốc (§3.3.3.3 a) | §5.4 — đo ghép cặp trên nguồn video ngoài |
| Tạo tác danh mục có bằng chứng giả mạo (§3.3.3.4) | §5.5 — ma trận chín kịch bản giả mạo |
| Vùng miền là một phần định danh lớp (§3.4.1 d) | §5.6 — chứng cứ hai chiều: biến thể vào được, trùng bị chặn |
| Cổng đồng thuận chi phối đường phát hành (§3.5.4 c) | §5.7 — đếm mẫu phát hành được trước và sau khi rút đồng thuận |
| Giam hãm đầu ra theo tổ chức (§3.6.2 c) | §5.2 — nhóm phép đo C3 và C5 |
