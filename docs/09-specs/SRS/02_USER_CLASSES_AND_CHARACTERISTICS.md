# 2. Lớp người dùng và đặc điểm (User Classes and Characteristics)

*Hệ thống có **10 tác nhân người** và **6 tác nhân hệ thống**. Cột "Hệ thống kiểm
bằng" trả lời một câu quan trọng mà nhiều bản đặc tả bỏ qua: **hệ thống có tự
phân biệt được vai này không?** Một vai không kiểm được vẫn có thể có mặt trong
mô hình vì lý do nghiệp vụ, nhưng phải nói thẳng là chưa kiểm được.*

Ký hiệu: **✅** kiểm được bằng một điều kiện cụ thể trong mã hoặc CSDL ·
**🟡** kiểm được lớp quyền bao ngoài nhưng không kiểm được chính vai đó ·
**⚠️** không có cột, cờ hay điều kiện nào phân biệt.

---

## 2.1 Bốn nhóm tác nhân

| Nhóm | Gồm | Đặc điểm chung |
|---|---|---|
| Chưa có danh tính | A1 Khách vãng lai | Không đăng nhập; chỉ chạm được phần công khai |
| Người dùng cuối | A2 Người dùng đã đăng nhập «abstract», A3 Người khiếm thính – khiếm ngôn, A4 Người dùng bình thường | Dùng hệ thống để **giao tiếp** và giữ tài khoản của mình |
| Bên tổ chức / bên thứ ba | A5 Thành viên tổ chức, A6 Biên tập viên / Nghiên cứu sinh, A7 Quản trị tổ chức | Thuộc một tổ chức; **đóng góp và khai thác dữ liệu** trong ranh giới tổ chức đó |
| Bên vận hành nền tảng | A8 Quản trị nền tảng, A9 Nhân viên hỗ trợ, A10 Kỹ sư vận hành | Giữ cả nền tảng chạy đúng, cho **mọi** tổ chức |

Cây kế thừa: `A2 → A5 → A6 → A7`, `A2 → {A3, A4}`, `A8 → {A9, A10}`. A1 đứng ngoài
mọi chuỗi, và **A8 tách hẳn khỏi nhánh tổ chức** — xem §2.4.

---

## 2.2 Bảng tổng hợp

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

---

## 2.3 Đặc điểm và yêu cầu quan trọng của từng lớp

### A3 — Người khiếm thính – khiếm ngôn (QUAN TRỌNG NHẤT)

Đây là lớp người dùng quan trọng nhất, không phải vì số lượng thao tác, mà vì họ
là **chủ thể dữ liệu**: dữ liệu trong hệ thống là ký hiệu do bàn tay của họ tạo
ra.

**Đặc điểm:**
- Tần suất dùng: theo buổi thu, thường có người vận hành ngồi cùng
- Trình độ kỹ thuật: từ chưa quen máy tính tới thành thạo
- Phương thức giao tiếp chính **không phải tiếng nói** — giao diện không được giả
  định người dùng nghe được hướng dẫn bằng âm thanh
- Quan tâm hàng đầu: đóng góp ký hiệu bản ngữ, và **kiểm soát được** dữ liệu của
  mình được dùng tới đâu

**Yêu cầu quan trọng:**
- Màn hình thu mẫu phải cho phản hồi **thị giác tức thì**: điểm mốc bàn tay vẽ
  chồng lên khung hình theo thời gian thực, chỉ báo số tay phát hiện được, đếm
  ngược trước khi ghi
- Hướng dẫn thu (khung hình mong muốn, số bàn tay lớp này yêu cầu, thời lượng
  mục tiêu) hiển thị ngay trên màn hình thu, đọc từ siêu dữ liệu của lớp
- Xem lại được cửa sổ vừa thu dưới dạng khung xương **trước khi** quyết định giữ
  hay bỏ
- Ký và **rút** đồng thuận theo ba mức, ở màn hình `/settings/consents`
- Giao diện nói thẳng giới hạn: rút đồng thuận loại dữ liệu khỏi các bản phát
  hành **sau đó**, không xoá dữ liệu khỏi lưu trữ và không thu hồi được giấy phép
  đã cấp cho bên thứ ba

**Giới hạn phải nêu:** hệ thống **không phân biệt được** A3 với A4 — tài khoản
của người khiếm thính và tài khoản của người nghe được có đúng cùng bộ quyền kỹ
thuật. Cái tách họ ra là **mục tiêu** khi dùng hệ thống, và mục tiêu khác nhau
vẫn sinh ra use case khác nhau. Bỏ A3 khỏi mô hình thì không còn ai để giải thích
vì sao đồng thuận lại chi phối việc phát hành dữ liệu.

### A5 — Thành viên tổ chức (QUAN TRỌNG)

**Đặc điểm:**
- Tần suất dùng: hàng ngày hoặc theo đợt thu dữ liệu
- Trình độ kỹ thuật: trung bình; biết dùng ứng dụng web, không nhất thiết biết
  lập trình
- Là người **vận hành buổi thu**: bấm nút, chọn lớp, nhập tên người thực hiện
- Chịu trách nhiệm về chất lượng bản ghi

**Yêu cầu quan trọng:**
- Thu liên tiếp nhiều mẫu cho một lớp mà không phải khai lại lớp mỗi lần
- Đổi người ký giữa buổi → hệ thống mở **phiên thu mới**, vì phiên thu là đơn vị
  gắn với đúng một người ký
- Theo dõi trạng thái tác vụ nền của mẫu vừa gửi, và biết vì sao một mẫu hỏng
- Xoá mềm, và khôi phục được từ thùng rác trong phạm vi của chính mình
- Thấy hạn mức tổ chức và mức đã dùng **trước khi** chạm trần

### A6 — Biên tập viên / Nghiên cứu sinh (QUAN TRỌNG)

**Đặc điểm:**
- Tần suất dùng: hàng tuần, theo chu kỳ thí nghiệm
- Trình độ kỹ thuật: cao; hiểu khái niệm bộ dữ liệu, chia tập, phiên bản
- Lớp có **nhiều use case nhất trong nhánh tổ chức** (13 UC)
- Là người phát hiện sớm nhất khi danh mục lớp bẩn hoặc quy kết sai

**Yêu cầu quan trọng:**
- Sửa danh mục lớp, gộp phương ngữ, gán lại người ký cho phiên thu
- Ghim được **phiên bản danh mục bất biến** vào một bộ dữ liệu và một tác vụ
  huấn luyện — điều kiện để chạy lại thí nghiệm sáu tháng sau vẫn ra cùng không
  gian nhãn
- Thấy được **tập lớp thực sự tham gia** sau ba cổng chặn, không phải tập lớp
  mình chọn — nếu chỉ lưu tập được chọn thì một lần chạy loại bớt lớp sẽ không
  để lại dấu vết
- Xuất ảnh chụp bộ dữ liệu kèm mã băm nội dung

### A7 — Quản trị tổ chức

**Đặc điểm:**
- Tần suất dùng: thỉnh thoảng, khi có việc hành chính
- Phạm vi quyền: đúng **một** tổ chức
- Kiểm bằng vai `admin` trong tổ chức đó

**Yêu cầu quan trọng:**
- Mời thành viên (**không** gán trực tiếp — xem §2.4), gán vai, thu hồi vai
- Xem hạn mức, mức sử dụng theo ngày, đổi gói cước (đòi xác thực lại trong phiên)
- Yêu cầu xuất toàn bộ dữ liệu tổ chức; yêu cầu dọn sạch dữ liệu tổ chức
- Quản lý khoá API và webhook của tổ chức

### A8 — Quản trị nền tảng

**Đặc điểm:**
- Tần suất dùng: hàng ngày ở giai đoạn vận hành đầu, sau đó thưa dần
- Trình độ kỹ thuật: cao
- Phạm vi quyền: **toàn nền tảng**, kiểm bằng cờ trên tài khoản
- Lớp có nhiều use case nhất trong toàn hệ thống (16 UC)

**Yêu cầu quan trọng:**
- Console quản trị với thanh bên ba tầng (nền tảng / tổ chức / cài đặt)
- Quản lý tài khoản, khoá/mở tài khoản, chặn địa chỉ IP
- Soạn – công bố – thu hồi văn bản pháp lý; công bố đòi xác thực lại
- Đọc nhật ký kiểm toán; quản lý khoá ký nguồn sự thật (`/admin/sot`)
- Thăng hạng mô hình đang phục vụ

### A9 — Nhân viên hỗ trợ

Trực hàng đợi phiếu hỗ trợ. **Hiện chưa có vai riêng** — dùng chung quyền quản
trị nền tảng (🟡). Tách sẵn ở tầng mô hình để khi hệ thống thêm vai riêng thì đặc
tả không phải viết lại.

### A10 — Kỹ sư vận hành

**Đặc điểm khác biệt quan trọng:** sáu use case của A10 **chạy ngoài ứng dụng** —
trên dòng lệnh của máy triển khai. Ranh giới thật của họ vì thế là **quyền hệ
điều hành**, không phải một vai trong hệ thống.

**Yêu cầu quan trọng:** triển khai (`deploy.sh`), kiểm độ tươi triển khai, sao
lưu và diễn tập khôi phục, chạy di trú lược đồ có chốt chặn đích, chạy các phép
đo, dọn ổ đĩa.

### A1 — Khách vãng lai

Đọc văn bản pháp lý (`/legal/:kind`), đăng ký, đăng nhập, khôi phục tài khoản, và
**dùng thử nhận dạng** với hạn mức 60 phút mỗi ngày. Cổng truy cập là **mặc định
từ chối**: một điểm cuối mới không khai báo công khai thì tự động yêu cầu xác
thực. Thiết kế này từng bịt **tám lỗ công khai** đã tồn tại, trong đó có một điểm
cuối làm lộ mười tên tài khoản thật.

---

## 2.4 Một ranh giới không được vẽ sai: A7 ≠ A8

Quản trị nền tảng **không kế thừa** Quản trị tổ chức, và ngược lại.

| | A7 Quản trị tổ chức | A8 Quản trị nền tảng |
|---|---|---|
| Kiểm bằng | vai trong **một** tổ chức | cờ trên tài khoản |
| Phạm vi | đúng một tổ chức | toàn nền tảng |
| Đưa người vào bằng | **lời mời** | gán trực tiếp theo mã tài khoản |

Lý do rất cụ thể: **mã tài khoản không phải bí mật**. Nếu quản trị viên tổ chức
gán trực tiếp được, họ kéo được bất kỳ ai trên hệ thống vào tổ chức của mình mà
người kia không hay biết. Đường đưa người vào của A7 vì thế **bắt buộc** là lời
mời — thứ đòi hỏi chính người được mời hành động.

---

## 2.5 Sáu tác nhân hệ thống

| Mã | Tác nhân | Gồm | Vai trò |
|---|---|---|---|
| S1 | Dịch vụ gửi tin | SMTP + cổng SMS | Gửi mã xác thực, lời mời, nhắc hạn, thư phiếu hỗ trợ, cảnh báo |
| S2 | Kho lưu trữ ngoài | Google Drive + Google Sheets | Giữ tệp đặc trưng, video thô, bản xem trước; phản chiếu nguồn sự thật để đối soát |
| S3 | Dịch vụ suy luận | Suy luận trên GPU + tổng hợp giọng nói | Phục vụ mô hình đang hoạt động, nạp nóng khi thăng hạng, đọc thành tiếng |
| S4 | Tiến trình nền | Hàng đợi tác vụ (Celery) + bộ lập lịch (celery-beat) | Trích đặc trưng, tăng cường, dựng bản xem trước, xoá tệp, đối soát, sao lưu theo lịch |
| S5 | Máy ghi nguồn sự thật | Máy được cấp khoá ký Ed25519 | Ghi vào nguồn sự thật và công bố bản đã ký |
| S6 | Ứng dụng bên thứ ba | Hệ thống ngoài dùng khoá API | Gọi API trong phạm vi của khoá; nhận sự kiện webhook |

**Về S5 — thẩm quyền ký gắn với MÁY, không gắn với người.** Chỉ một máy được chỉ
định là publisher; các máy khác chỉ có khoá công khai để xác minh. Một máy không
xác minh được danh mục thì không được phép phục vụ.

---

## 2.6 Ma trận tác nhân × nhóm chức năng

`●` tác nhân chính · `○` có tham gia

| Tác nhân | F1 | F2 | F3 | F4 | F5 | F6 | F7 | F8 |
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

---

## 2.7 Mô hình phân quyền đang cài đặt

| Hạng mục | Trạng thái |
|---|---|
| Mô hình gán vai theo phạm vi: chủ thể × vai × **cấp phạm vi** × định danh phạm vi | ✓ |
| Bốn cấp phạm vi: hệ thống, tổ chức, không gian làm việc, dự án | △ — hai cấp dưới **đã có bề mặt vận hành** (router `workspaces` + `/settings/workspaces`, 18/08/2026); gán vai ở đó ghi đúng dữ liệu nhưng **chưa có hiệu lực lúc chạy** vì `AUTHZ_MODE=shadow` |
| Cưỡng chế lúc chạy | ✓ ở cấp **hệ thống** và cấp **tổ chức**; ○ ở hai cấp dưới |
| Số vai dựng sẵn | **13 vai** — 2 hệ thống / 5 tổ chức / 2 không gian làm việc / 4 dự án. **Không có** `tenant_viewer` (đã gỡ khỏi danh mục) |
| Số bản ghi gán vai theo cấp | hệ thống 4 · tổ chức 10 · **không gian làm việc 0 · dự án 0** |
| Engine đánh giá chính sách | Casbin 1.36, mô hình RBAC-with-domains, 4 miền |
| Chế độ cưỡng chế | **`AUTHZ_MODE=shadow`** — Casbin chỉ **quan sát**; hệ phân quyền cũ hai phạm vi là bên **quyết định** thật |
| `tenant_members` | Là **khung nhìn** (`security_invoker`) trên lát cắt `scope_level = 'tenant'` của `role_assignments`, không phải bảng |

**Phát biểu chính thức phải giữ nhất quán:** *"kiến trúc hỗ trợ nhiều cấp; cưỡng
chế chứng minh được ở cấp hệ thống và cấp tổ chức"*. Không được rút gọn thành
"phân quyền bốn cấp".

**Và một điều nữa không được rút gọn:** sự có mặt của Casbin **không** đồng nghĩa
Casbin đang cưỡng chế. Ở chế độ `shadow`, nó chạy song song để **so sánh quyết
định** với hệ cũ và phát ra chỉ số lệch; chính chỉ số đó là điều kiện dừng để
chuyển sang `AUTHZ_MODE=casbin`. Viết "hệ thống dùng Casbin để phân quyền" mà bỏ
qua chi tiết này là mô tả một hệ thống khác với hệ thống đang chạy.

**Một nhầm lẫn kinh điển cần tránh:** vỏ console quản trị **không phải hàng rào
quyền**. Việc một trang nằm dưới đường dẫn `/admin` không tự nó chặn ai; quyền
vẫn kiểm ở tầng dịch vụ.
