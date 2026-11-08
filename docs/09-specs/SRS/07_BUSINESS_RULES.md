# 7. Quy tắc nghiệp vụ (Business Rules)

*Quy tắc nghiệp vụ là những mệnh đề mà hệ thống phải giữ đúng bất kể ai thao tác
và qua màn hình nào. Mỗi quy tắc dưới đây ghi kèm **nơi cưỡng chế** — vì một quy
tắc chỉ được kiểm ở giao diện thì không phải quy tắc, mà là một lời nhắc.*

Ký hiệu nơi cưỡng chế: **CSDL** (ràng buộc, trigger, chính sách bảo mật mức hàng)
· **Trung gian** (middleware, trước khi tới bộ định tuyến) · **Dịch vụ** (mã
nghiệp vụ) · **Giao diện** (chỉ ở trình duyệt — mức yếu nhất).

---

## BR-1 · Vai trò và quyền hạn

| # | Quy tắc | Nơi cưỡng chế |
|---|---|---|
| BR-1.1 | Hệ thống có **13 vai dựng sẵn** (2 hệ thống / 5 tổ chức / 2 không gian làm việc / 4 dự án), gán theo mô hình *chủ thể × vai × cấp phạm vi × định danh phạm vi* | CSDL + Dịch vụ |
| BR-1.2 | Cưỡng chế lúc chạy hiện **chỉ chứng minh được ở cấp hệ thống và cấp tổ chức**. Hai cấp dưới có bảng nhưng **0 bản ghi gán vai** và không có bề mặt API | — (giới hạn đã tuyên bố) |
| BR-1.2b | Engine Casbin chạy ở **`AUTHZ_MODE=shadow`**: nó **quan sát và so sánh**, hệ phân quyền cũ hai phạm vi là bên **quyết định** thật | Dịch vụ |
| BR-1.3 | **Quản trị tổ chức ≠ Quản trị nền tảng.** Không vai nào kế thừa vai kia | Dịch vụ |
| BR-1.4 | Quản trị tổ chức đưa người vào **chỉ bằng lời mời**, không bao giờ bằng gán trực tiếp theo mã tài khoản | Dịch vụ |
| BR-1.5 | Quản trị nền tảng đưa người vào bằng **gán trực tiếp**, và phạm vi là toàn nền tảng | Dịch vụ |
| BR-1.6 | Một tài khoản thuộc **nhiều tổ chức** với vai khác nhau ở mỗi tổ chức | CSDL |
| BR-1.7 | Vỏ console quản trị **không phải hàng rào quyền**: nằm dưới `/admin` không tự nó chặn ai | Dịch vụ (chỗ kiểm thật) |
| BR-1.8 | Cổng truy cập **mặc định từ chối**: điểm cuối mới không khai báo công khai thì tự động yêu cầu xác thực | **Trung gian** |

**BR-1.2b phải nói ra, vì bỏ nó đi sẽ mô tả sai hệ thống đang chạy.** Chỉ số lệch
giữa hai bên quyết định chính là **điều kiện dừng** để chuyển sang
`AUTHZ_MODE=casbin`. Chừng nào còn ở `shadow`, mọi phát biểu về hành vi phân
quyền phải nói về **hệ cũ**, không phải về mô hình Casbin bốn miền.

**Vì sao BR-1.4 tồn tại:** mã tài khoản không phải bí mật. Nếu quản trị viên tổ
chức gán trực tiếp được, họ kéo được bất kỳ ai trên hệ thống vào tổ chức của mình
mà người kia không hay biết. Lời mời là thứ đòi hỏi chính người được mời hành
động.

---

## BR-2 · Ranh giới dữ liệu giữa các tổ chức

| # | Quy tắc | Nơi cưỡng chế |
|---|---|---|
| BR-2.1 | **Một truy vấn không khai báo tổ chức trả về 0 hàng**, không phải mọi hàng | **CSDL** |
| BR-2.2 | Ứng dụng **không được tự vô hiệu hoá** cơ chế cách ly: vai chạy không có quyền DDL, không phải siêu người dùng, không có quyền vượt chính sách | **CSDL** |
| BR-2.3 | Ngữ cảnh tổ chức **giới hạn trong phạm vi giao dịch**; không rò sang yêu cầu kế tiếp trên cùng kết nối | Dịch vụ (một khối duy nhất) |
| BR-2.4 | Công việc nền xuyên tổ chức đi qua **một biến ngữ cảnh riêng biệt**, không phải một "giá trị tổ chức đặc biệt" | Dịch vụ + CSDL |
| BR-2.5 | Mẫu của tổ chức A **không thể** trỏ tới lớp của tổ chức B — khoá ngoại là khoá ghép mang định danh tổ chức | **CSDL** (22/117 khoá ngoại) |
| BR-2.6 | Điểm cuối thống kê tổng hợp phải đi qua **cùng cơ chế phạm vi** như điểm cuối dữ liệu | Dịch vụ |
| BR-2.7 | Cách ly ở **mặt phẳng tệp** dựa vào cấu trúc thư mục theo tổ chức cộng kiểm tra ở tầng ứng dụng — **mức bảo đảm thấp hơn** mặt phẳng CSDL | Dịch vụ |

**BR-2.4 giải thích:** nếu "hành động thay mọi tổ chức" là một giá trị của cùng
biến tổ chức, thì một lỗi gõ sai tên tổ chức có thể **vô tình sinh ra đặc quyền
đó**. Tách biến làm điều này không thể xảy ra do nhầm lẫn. Sentinel phạm vi hệ
thống chỉ nhận giá trị `'on'`, không nhận gì khác.

**BR-2.6 giải thích:** một điểm cuối trả về "số mẫu toàn nền tảng" không trả dữ
liệu của ai cả — nhưng nếu một tổ chức chỉ có một thành viên thì con số tổng hợp
ấy nói về đúng người đó. **Tổng hợp cũng có thể rò rỉ.**

**Một cảnh báo về cách đọc BR-2.1:** khi một truy vấn chạy **trước khi** biết tổ
chức (ví dụ lúc đăng nhập), chính sách khớp 0 hàng đúng như thiết kế — nhưng mã
ứng dụng đọc "0 hàng" thành *"không có gì"* thay vì *"chưa có ngữ cảnh"* sẽ biến
fail-closed thành fail-open. Lỗi này đã mắc **ba lần trong hai ngày**.

---

## BR-3 · Đồng thuận và dữ liệu chủ thể

| # | Quy tắc | Nơi cưỡng chế |
|---|---|---|
| BR-3.1 | **Đăng ký luôn kéo theo chấp thuận văn bản pháp lý.** Không chấp thuận thì tài khoản **không được tạo** | Dịch vụ |
| BR-3.2 | Tài khoản còn văn bản chưa chấp thuận: **đăng nhập được nhưng không ghi được gì** | Dịch vụ |
| BR-3.3 | Chấp thuận trỏ tới **cặp (loại, phiên bản)**, không trỏ tới "văn bản hiện hành" | CSDL |
| BR-3.4 | Văn bản pháp lý **đã công bố là bất biến** | **CSDL** (trigger) |
| BR-3.5 | Sửa lỗi chính tả **không** buộc chấp thuận lại; đổi phạm vi xử lý dữ liệu **thì có** — phân biệt bằng một cờ riêng | Dịch vụ |
| BR-3.6 | Đồng thuận gắn với **người ký** (chủ thể dữ liệu), **không** gắn với tài khoản thu | CSDL |
| BR-3.7 | Đồng thuận theo **thang ba mức**, có phiên bản | CSDL + Dịch vụ |
| BR-3.8 | Mọi đường phát hành dữ liệu đọc mức đồng thuận **trước khi** lấy mẫu; mẫu không đủ mức **không xuất hiện** trong bản phát hành đó | Dịch vụ (4 đường dữ liệu) |
| BR-3.9 | Rút đồng thuận loại dữ liệu khỏi mọi bản phát hành **sau đó**; nó **không** xoá dữ liệu khỏi lưu trữ và **không** thu hồi giấy phép đã cấp | Dịch vụ + Giao diện (có kiểm thử ghim câu chữ) |
| BR-3.10 | Một mẫu không quy được về người ký thì với đường phát hành nghiên cứu, nó **không dùng được** | Dịch vụ |

**BR-3.2 là hành vi có chủ ý, không phải lỗi.** Chặn ngay tại cửa đăng nhập sẽ
khiến người dùng không đọc được chính văn bản mà họ được yêu cầu chấp thuận, và
cũng không lấy được dữ liệu của mình ra.

**BR-3.9 là chỗ dễ hứa quá.** Bốn nghĩa của "thu hồi" — thu hồi quyền truy cập ·
gỡ khỏi bản phát hành mới · xoá khỏi lưu trữ · thu hồi giấy phép đã cấp — hệ
thống thi hành nghĩa 1 và 2, **không** thi hành nghĩa 3 và 4. Giao diện nói thẳng
điều này và có kiểm thử ghim đúng câu chữ, để một lần sửa giao diện về sau không
vô tình biến một giới hạn thành một lời hứa.

---

## BR-4 · Danh mục từ vựng

| # | Quy tắc | Nơi cưỡng chế |
|---|---|---|
| BR-4.1 | **Định danh một lớp gồm năm cột**, trong đó có phương ngữ và vùng miền. Hai lớp cùng nhãn khác phương ngữ là **hai lớp** | **CSDL** |
| BR-4.2 | Danh mục hệ thống sao chép sang danh mục tổ chức **đúng một lần, lúc khởi tạo** | Dịch vụ |
| BR-4.3 | **Lúc chạy KHÔNG bao giờ rơi ngược** về mặt phẳng cộng đồng. Thiếu dữ liệu danh mục thì **dừng**, không suy đoán | Dịch vụ |
| BR-4.4 | Phiên bản danh mục là **ảnh chụp bất biến** có mã băm nội dung | CSDL |
| BR-4.5 | Bộ dữ liệu và tác vụ huấn luyện **ghim** một phiên bản danh mục cụ thể, không trỏ tới trạng thái hiện tại | CSDL (khoá ngoại ghép) |
| BR-4.6 | Số bàn tay yêu cầu của một lớp **đọc từ siêu dữ liệu của lớp**, không suy đoán từ khung hình | Dịch vụ |
| BR-4.7 | **"Đã đăng ký" ≠ "huấn luyện được".** Một lớp đủ mẫu nhưng người ký chưa đồng ý ở mức tương ứng thì với đường phát hành nghiên cứu, nó là một lớp **rỗng** | Dịch vụ |

**BR-4.2 và BR-4.3 trông giống nhau trên sơ đồ nhưng khác hoàn toàn về hệ quả.**
Sao chép danh mục cộng đồng vào tổ chức mới là **kế thừa** — xảy ra một lần, kết
quả thuộc về tổ chức đó. Đọc danh mục cộng đồng khi tổ chức thiếu dữ liệu là **rơi
về** — và bị cấm, vì nó làm dữ liệu của hai mặt phẳng lẫn vào nhau mà không ai
biết.

**BR-4.6 có lý do cụ thể:** suy đoán số tay từ khung hình sẽ khiến một lớp hai tay
được chấp nhận với dữ liệu một tay khi người ký để tay kia ra ngoài khung.

**BR-4.1 đã trả giá thật:** một chỉ mục cũ trên CSDL sản xuất chỉ dùng 4 cột đã
**cấm** hai biến thể cùng nhãn khác vùng miền, và điều đó chặn việc nhập dữ liệu
từ nguồn từ điển quốc gia. Chỉ mục 4 cột đã được gỡ ngày 17/08/2026.

---

## BR-5 · Vòng đời dữ liệu mẫu

| # | Quy tắc | Nơi cưỡng chế |
|---|---|---|
| BR-5.1 | **Một lượt thu = đúng một mẫu**, và tính đúng một suất trong hạn mức tổ chức | Dịch vụ |
| BR-5.2 | **Phiên thu gắn với đúng một người ký.** Đổi người ký giữa buổi ⇒ mở phiên thu mới | Dịch vụ |
| BR-5.3 | Bản gốc tải lên ghi vào kho thô **trước** mọi bước chuẩn hoá | Dịch vụ (thứ tự bắt buộc) |
| BR-5.4 | Đường thu qua webcam **không sinh video thô** — điểm mốc trích tại trình duyệt | Giao diện (theo thiết kế) |
| BR-5.5 | **Xoá là xoá mềm.** Xoá phiên thu, xoá mẫu, gỡ lớp là ba mức của cùng ngữ nghĩa, đi qua thùng rác | CSDL (`deleted_at`) + Dịch vụ |
| BR-5.6 | Mẫu chỉ ghi được khi **hai cổng** cùng cho qua: đồng thuận còn hiệu lực **và** tổ chức còn hạn mức | Dịch vụ |
| BR-5.7 | Bất kỳ cổng nào chặn ⇒ **không mẫu nào được tạo**, và dữ liệu vừa thu vẫn còn trong trình duyệt | Dịch vụ + Giao diện |
| BR-5.8 | Trạng thái mẫu: `pending → processing → ready`, nhánh `failed`, nhánh `deleted` → `purged`, và cạnh khôi phục ngược từ `deleted` về `ready` | CSDL |
| BR-5.9 | Bản xuất sang bảng tính ngoài **giữ lại dòng đã xoá mềm** kèm dấu `deleted_at`, không dịch dòng | Dịch vụ |

**BR-5.9 giải thích:** dịch dòng làm mọi tham chiếu theo số hàng sai. Giữ dòng và
đánh dấu là cách duy nhất để bản phản chiếu còn đối soát được.

---

## BR-6 · Huấn luyện và mô hình

| # | Quy tắc | Nơi cưỡng chế |
|---|---|---|
| BR-6.1 | Tác vụ huấn luyện phải qua **ba cổng chặn**: đồng thuận (lúc chọn mẫu) · sàn số mẫu mỗi lớp (trước khi đánh chỉ số lớp) · hạn mức tổ chức (lúc xếp hàng) | Dịch vụ |
| BR-6.2 | **Sàn số mẫu phải áp TRƯỚC khi đánh chỉ số lớp** | Dịch vụ (thứ tự bắt buộc) |
| BR-6.3 | **Lọc lúc chia tập ≠ từ chối lúc chạy.** Lọc là loại lớp không đủ điều kiện rồi tiếp tục; từ chối là dừng cả tác vụ. Hệ thống làm cả hai, ở hai chỗ khác nhau | Dịch vụ |
| BR-6.4 | Tác vụ huấn luyện lưu **tập lớp thực sự tham gia sau ba cổng**, không phải tập lớp người dùng chọn | CSDL |
| BR-6.5 | **Phiên bản mới nhất ≠ phiên bản đang phục vụ.** Mô hình vừa huấn luyện xong chưa phục vụ ai cho tới khi được **thăng hạng** — hành động tường minh, có bản ghi, đảo ngược được | Dịch vụ |
| BR-6.6 | Độ tin cậy của một lượt suy luận đơn lẻ **không phải** chỉ số chất lượng | — (quy tắc phát biểu) |

**BR-6.2 có hậu quả thật nếu làm ngược:** đánh chỉ số trước rồi mới loại lớp sẽ
làm chỉ số lớp **nhảy cóc**, và mô hình huấn luyện trên một không gian nhãn khác
với không gian nhãn lúc suy luận — một lỗi **không sinh ra thông báo nào**, chỉ
sinh ra kết quả sai.

**BR-6.4 giải thích:** nếu chỉ lưu tập được chọn, một lần chạy loại bớt lớp sẽ
không để lại dấu vết, và người dùng sẽ tưởng mô hình được huấn luyện trên tập lớp
mình chọn.

---

## BR-7 · Nguồn sự thật và toàn vẹn

| # | Quy tắc | Nơi cưỡng chế |
|---|---|---|
| BR-7.1 | **Thẩm quyền ký gắn với MÁY**, không gắn với người. Chỉ một máy phát hành duy nhất giữ khoá riêng Ed25519 | Vận hành + Dịch vụ |
| BR-7.2 | Tạo tác hợp lệ = Toàn vẹn **∧** Chữ ký hợp lệ **∧** Người ký được tin cậy **∧** Chính sách phiên bản hợp lệ | Dịch vụ |
| BR-7.3 | Xác minh trả về **tên khoá đã đăng ký**, không trả về giá trị đúng/sai | Dịch vụ |
| BR-7.4 | Không xác minh được ⇒ **DỪNG cả hệ thống**, không suy đoán | `sot-init` (mã thoát chuyên biệt) |
| BR-7.5 | Hợp nhất theo nguyên tắc **CHỈ ĐIỀN, KHÔNG XOÁ**: cơ sở dữ liệu của máy tiêu thụ phải là **tập cha** của bản công bố | Dịch vụ |
| BR-7.6 | Đơn điệu phiên bản **chưa được cưỡng chế**: hệ thống chấp nhận bản công bố có số hiệu thấp hơn bản đang dùng; tài nguyên mới không bị xoá nhưng giá trị dùng chung **bị ghi đè lùi** | ○ giới hạn đã biết |

**BR-7.3 là vế dễ bỏ sót nhất.** Kẻ tấn công dựng dữ liệu khác, tính mã băm đúng,
viết bản kê đúng, rồi **tự ký bằng khoá của hắn** — chữ ký ấy hợp lệ về mật mã.
Nếu hệ thống chỉ hỏi *"chữ ký có hợp lệ không"* mà không hỏi *"hợp lệ theo khoá
nào"* thì toàn vẹn đúng nhưng **thẩm quyền sai**.

---

## BR-8 · Tổ chức, hạn mức và đăng ký dịch vụ

| # | Quy tắc | Nơi cưỡng chế |
|---|---|---|
| BR-8.1 | Giá trị **rỗng** ở cột hạn mức nghĩa là **không giới hạn**, không phải "bằng không" | Dịch vụ (đã ghim bằng kiểm thử) |
| BR-8.2 | Trạng thái **quản trị** (đình chỉ) và trạng thái **thương mại** (`billing_status`) là hai trục khác nhau | CSDL |
| BR-8.3 | Trạng thái `past_due` **vẫn ghi được** — là chủ ý, không phải sót | Dịch vụ |
| BR-8.4 | Con số dùng để **chặn** ("đang dùng") và con số dùng để **tính tiền** ("đã từng dùng") đọc từ hai nguồn khác nhau, có chủ đích | Dịch vụ |
| BR-8.5 | Hệ thống **không thu tiền**. Có đo, có ghi nhận, không có cổng thanh toán | — |
| BR-8.6 | Tổ chức mang định danh `default` là **một tổ chức bình thường** về mọi mặt cách ly, **không** phải "dữ liệu chung" | CSDL |

**BR-8.6 là ranh giới quan trọng nhất trong nhóm này.** Tổ chức `default` là tổ
chức **mồi** — nơi dữ liệu lịch sử của hệ thống tiền thân nằm lại. Coi nó là "dữ
liệu chung" là mở một lỗ hổng **đúng bằng toàn bộ dữ liệu lịch sử**.

Một cái bẫy cụ thể trong mã: hàm chuẩn hoá định danh tổ chức **trả về `default`
khi nhận chuỗi rỗng**. Hệ quả: một hàm kiểm tra viết **sau** bước chuẩn hoá sẽ
không bao giờ thấy chuỗi rỗng, và trở thành mã chết. Nguyên tắc rút ra: **kiểm
tham số thô trước khi chuẩn hoá**.

---

## BR-9 · Thao tác nguy hiểm và bằng chứng

| # | Quy tắc | Nơi cưỡng chế |
|---|---|---|
| BR-9.1 | Thao tác **không hoàn tác được** đòi xác thực lại trong phiên: dọn sạch dữ liệu tổ chức · công bố văn bản pháp lý · đổi gói cước | Dịch vụ |
| BR-9.2 | Mọi thao tác nhạy cảm để lại **nhật ký kiểm toán bền vững** | CSDL + Dịch vụ |
| BR-9.3 | Ghi nhật ký kiểm toán **từ chối khi thiếu phạm vi** (fail-closed) | Dịch vụ |
| BR-9.4 | `audit_log.actor_label` là **bằng chứng lịch sử**: khi tài khoản đổi tên, năm chỗ khác được cập nhật theo nhưng cột này thì **không** | Dịch vụ (có chủ đích) |
| BR-9.5 | Token, mã một lần và khoá API lưu ở **dạng băm**, không lưu giá trị gốc. Mất khoá thì tạo mới, không khôi phục | CSDL |
| BR-9.6 | **Không có đường quay ngược từ công khai vào riêng tư.** Dữ liệu đã công bố sang mặt phẳng dùng chung không rút lại được bằng một nút bấm | Dịch vụ |

**BR-9.4 giải thích:** một bản ghi kiểm toán phải nói ra tên **tại thời điểm hành
động xảy ra**. Cập nhật nó theo tên hiện tại là viết lại lịch sử.

---

## BR-10 · Vận hành và thay đổi hệ thống

| # | Quy tắc | Nơi cưỡng chế |
|---|---|---|
| BR-10.1 | Bước tự động lúc khởi động **chỉ được thêm** (bảng, cột); mọi thay đổi **một chiều** phải qua lệnh di trú tường minh | Dịch vụ |
| BR-10.2 | Backend **từ chối khởi động** khi phiên bản lược đồ lệch, theo **cả hai chiều** | Dịch vụ |
| BR-10.3 | Lệnh di trú bắt buộc khai **cơ sở dữ liệu đích** (`EXPECTED_DATABASE`) | Dịch vụ |
| BR-10.4 | Bộ kiểm thử chỉ chạy qua `scripts/run_tests.sh` | Vận hành |
| BR-10.5 | Sau **ba** lần khởi động liên tiếp, phần chênh lệch cấu trúc phải rỗng | Cổng trước triển khai |
| BR-10.6 | Một bản sao lưu **chưa được diễn tập khôi phục là một bản sao lưu chưa tồn tại** | Vận hành |
| BR-10.7 | Mọi phép đo phải **có khả năng thất bại** và có **đối chứng dương**. Phép đo thiếu đối chứng dương thì kết quả **bị loại**, kể cả khi kết quả đẹp | Phương pháp |

**BR-10.3 sinh ra từ sự cố ngày 13/08/2026:** biến `POSTGRES_DB` **không tham gia
dựng chuỗi kết nối**, và một lượt chạy đi nhầm vào cơ sở dữ liệu sản xuất — áp một
phiên bản lược đồ dở dang lên `signdb` và đóng dấu phiên bản sai.

**BR-10.7 đã được áp thật và đã trả giá:** lượt đo cách ly ngày 15/08/2026 bị loại
khỏi phân tích vì đối chứng dương không đạt, dù 390/630 ca đối kháng cho kết quả
"đã chặn". *Một phép đo không thể thất bại thì không đo gì cả.*

---

## 7.11 Năm nguyên lý xuyên suốt

Năm nguyên lý dưới đây là thứ sinh ra phần lớn các quy tắc ở trên; chúng lặp lại ở
nhiều chỗ khác nhau trong hệ thống:

1. **Thiếu ngữ cảnh thì dừng, không đoán.** Áp cho cách ly (không có tổ chức ⇒ 0
   hàng), danh mục (thiếu dữ liệu ⇒ dừng), nguồn sự thật (không xác minh được ⇒
   không khởi động), nhật ký kiểm toán (không có phạm vi ⇒ từ chối ghi).
2. **Kế thừa lúc khởi tạo khác với rơi về lúc chạy.**
3. **Ngoại lệ phải là một phạm vi, không phải một lối đi vòng.**
4. **Tổng hợp cũng có thể rò rỉ.**
5. **Không có đường quay ngược từ công khai vào riêng tư.**
