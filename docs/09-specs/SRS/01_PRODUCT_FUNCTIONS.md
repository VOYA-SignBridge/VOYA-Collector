# 1. Các chức năng của sản phẩm (Product Functions)

*Mọi chức năng liệt kê ở đây đều có ít nhất một điểm cuối API, một màn hình, hoặc
một lệnh vận hành thật đứng sau. Chức năng chỉ có mô hình dữ liệu mà chưa có bề
mặt vận hành được đánh dấu **○** và nói rõ là chưa.*

---

## 1.1 Phát biểu sản phẩm

CTU.SignBridge là một **nền tảng web đa tổ chức (multi-tenant SaaS)** để thu thập,
tổ chức, quản lý và hỗ trợ khai thác dữ liệu Ngôn ngữ Ký hiệu Việt Nam (VSL).
Nhiều tổ chức — một trường, một nhóm nghiên cứu, một doanh nghiệp — dùng chung
**một bản triển khai duy nhất**, nhưng dữ liệu của họ **cô lập theo mặc định**:
ranh giới tổ chức được cưỡng chế ở tầng cơ sở dữ liệu, không dựa vào việc lập
trình viên nhớ viết điều kiện lọc.

Bài toán mà sản phẩm giải **không phải** "thu thêm dữ liệu VSL", mà là: *nhiều
đơn vị cùng thu dữ liệu trên một nền tảng chung mà vẫn giữ được ranh giới sở hữu,
ranh giới điều kiện sử dụng và khả năng tái lập của từng bộ dữ liệu*.

Ba đặc điểm phân biệt sản phẩm này với một công cụ thu dữ liệu thông thường:

1. **Dữ liệu rời trình duyệt ở dạng đã trích đặc trưng.** Điểm mốc bàn tay được
   trích ngay tại máy người dùng bằng WebAssembly (MediaPipe Hands), nên với
   đường thu qua webcam, video thô **không bắt buộc rời khỏi máy đó**.
2. **Ranh giới tổ chức do cơ sở dữ liệu cưỡng chế** bằng chính sách bảo mật mức
   hàng (Row-Level Security), cộng khoá ngoại ghép mang định danh tổ chức.
3. **Danh mục từ vựng là tạo tác có phiên bản và có chữ ký số Ed25519**, không
   phải một bảng tra cứu sửa tự do.

## 1.2 Quy mô cài đặt (đếm ngày 17/08/2026)

| Hạng mục | Số lượng | Cách đếm |
|---|---:|---|
| Nhóm nghiệp vụ | 8 | Chương 1 §2.0.1 |
| Use case đặc tả | 75 | UC101–UC806, Phụ lục C |
| Bộ định tuyến API | 27 tệp — **25 được mount** | thư mục `backend/app/routers/` |
| Điểm cuối API | **214 HTTP gọi được** (+1 WebSocket, +13 không mount) | số bộ trang trí phương thức HTTP trong `routers/` |
| Màn hình giao diện | hơn 30 | `frontend/src/pages/` + tuyến trong `App.tsx` |
| Dịch vụ container | 15 (14 thường trực + 1 khởi tạo) | `docker-compose*.yml` |
| Bảng nghiệp vụ | 57 (+1 khung nhìn) | truy vấn CSDL đang chạy |
| Mã dịch vụ | 61.097 dòng Python / 162 tệp | đếm ngày 17/08/2026 |
| Mã giao diện | 48.074 dòng TypeScript / 221 tệp | đếm ngày 17/08/2026 |
| Mã kiểm thử | 41.760 dòng / 151 tệp (0,68 : 1 so với mã dịch vụ) | đếm ngày 17/08/2026 |

*Con số 214 lệch vài đơn vị so với số đường dẫn trong đặc tả OpenAPI, vì một hàm
có thể đăng ký nhiều phương thức trên cùng một đường dẫn. Cách đếm nêu ra để con
số kiểm chứng lại được.*

> **Vì sao phải tách "gọi được" khỏi "có trong mã" (đính chính 18/08/2026).**
> Hai tệp — `experiments.py` (12 điểm cuối) và `dataset_exporter.py` (1) — **có
> mã đầy đủ nhưng không được `include_router`**, nên không URL nào chạm tới
> chúng. Bản trước của bảng này đếm gộp và ra 213 cho 26 bộ định tuyến.
>
> Chúng **cố ý** không được mount: cả hai **không khai một tham chiếu xác thực
> nào** (không `Depends`, không guard tenant). Mount để có thêm ảnh chụp cho tài
> liệu sẽ mở công khai 13 điểm cuối, trong đó có `POST /models/{id}/promote` —
> câu lệnh đưa một mô hình vào phục vụ thật. Giữ nguyên trạng thái không-mount
> là quyết định đúng, và bảng này nói ra thay vì để con số tự nhận công.

---

## 1.3 Tám nhóm chức năng chính

Ranh giới giữa các nhóm **không phải màn hình**, mà là **thứ đang bị quản lý**:
danh tính, dữ liệu thô, danh mục, mô hình, tổ chức, chính sách, hạ tầng, và dịch
vụ vành ngoài.

| # | Nhóm chức năng | Câu hỏi nghiệp vụ | Mã UC | Số UC | Điểm cuối |
|---|---|---|---|:--:|:--:|
| F1 | Danh tính và quyền truy cập | Anh là ai, và anh đã đồng ý những gì? | UC101–UC114 | 14 | 34 |
| F2 | Thu thập và quản lý dữ liệu mẫu | Mẫu vào hệ thống bằng đường nào, và mất đi bằng đường nào? | UC201–UC213 | 13 | 38 |
| F3 | Danh mục từ vựng và phương ngữ | Được phép thu lớp nào, theo phương ngữ nào? | UC301–UC310 | 10 | 22 |
| F4 | Huấn luyện, đánh giá và suy luận | Dữ liệu thành mô hình bằng cách nào, rồi mô hình phục vụ ai? | UC401–UC409 | 9 | 31 |
| F5 | Tổ chức và đăng ký dịch vụ | Ai thuộc về tổ chức nào, trong hạn mức nào? | UC501–UC508 | 8 | 28 |
| F6 | Quản trị người dùng và chính sách | Ai đặt luật, và lấy gì làm bằng chứng? | UC601–UC609 | 9 | 34 |
| F7 | Vận hành hệ thống và nguồn sự thật | Hệ thống có đang chạy đúng thứ ta nghĩ không? | UC701–UC706 | 6 | 13 |
| F8 | Hỗ trợ và tích hợp | Hỏng thì kêu ai, và máy khác nối vào thế nào? | UC801–UC806 | 6 | 22 |
| | | | **Tổng** | **75** | **213** |

> **Cột "Điểm cuối" ở bảng trên là PHÂN BỔ theo nghiệp vụ, không phải đếm theo
> tệp** — một bộ định tuyến (rõ nhất là `tenants`) trải ra hai nhóm. Vì vậy nó
> tổng lại thành 213 chứ không bằng con số 214 ở §1.2, và hai con số **không
> được sửa cho khớp nhau bằng cách nhích một ô**: chúng đếm hai thứ khác nhau.
>
> Sau 18/08/2026 cột này còn **chưa cập nhật** cho ba thay đổi đã biết: F5 nhận
> thêm 14 điểm cuối của `workspaces`, F2 bớt 1 (`dataset_exporter`), F4 bớt 12
> (`experiments`). Không sửa vội vì bảng phân bổ phải soát lại từng use case
> chứ không cộng trừ ở dòng tổng — và một con số cộng trừ cho khớp là đúng loại
> số làm người đọc tin nhầm rằng bảng đã được kiểm.

**Cách các nhóm nối nhau.** F1 → F2 → F3 là vòng đời của một mẫu: có danh tính và
đồng thuận trước, rồi mới thu được mẫu, và mẫu chỉ có nghĩa khi thuộc về một lớp
trong danh mục. F4 là chỗ dữ liệu thành sản phẩm. F5, F6, F7 là ba tầng quản trị
**không lồng nhau**: một tổ chức tự quản mình (F5), nền tảng đặt luật cho mọi tổ
chức (F6), hạ tầng bên dưới không biết tổ chức là gì (F7). F8 là vành ngoài.

F6 và F7 tách ra dù cùng do quyền quản trị nền tảng kiểm, vì chúng **hỏng theo
hai kiểu khác nhau**: F6 sai thì chính sách sai; F7 sai thì hệ thống mất dữ liệu
hoặc chạy sai mã. Người chịu trách nhiệm cũng khác.

---

## 1.4 Chi tiết từng nhóm chức năng

### F1 — Danh tính và quyền truy cập ✓

| Mã | Chức năng | Trạng thái | Ghi chú cài đặt |
|---|---|:--:|---|
| UC101 | Đăng ký tài khoản | ✓ | Luôn kéo theo chấp thuận văn bản pháp lý; không chấp thuận thì **tài khoản không được tạo** |
| UC102 | Đăng ký theo lời mời | ✓ | Tạo tài khoản **đã** là thành viên một tổ chức; tiêu thụ token mời |
| UC103 | Gửi mã xác thực | ✓ | Hai kênh: thư điện tử và SMS |
| UC104 | Xác thực địa chỉ liên hệ | ✓ | Mã lưu dạng băm, có hạn, đếm số lần thử |
| UC105 | Đăng nhập | ✓ | Hai lớp hạn mức (định danh–IP, và riêng IP) kiểm **trước** phép băm mật khẩu |
| UC106 | Xác thực yếu tố thứ hai | ✓ | TOTP, kiểm bằng vector thử của tiêu chuẩn |
| UC107 | Đăng xuất | ✓ | Ba mức thu hồi phiên, không được lẫn |
| UC108 | Khôi phục tài khoản | ✓ | Gộp ba bước vào một cửa; verify và confirm dùng **chung** xô tần suất |
| UC109 | Quản lý xác thực hai yếu tố | ✓ | Kèm mã khôi phục dùng một lần |
| UC110 | Quản lý hồ sơ cá nhân | ✓ | Đổi tên tài khoản lan sang 5 chỗ khác + `samples.csv` |
| UC111 | Xem văn bản pháp lý | ✓ | Công khai, không cần đăng nhập |
| UC112 | Chấp thuận văn bản pháp lý | ✓ | Chấp thuận trỏ tới cặp (loại, phiên bản) bất biến |
| UC113 | Rút đồng thuận | ✓ | Hành động của **người ký**, không phải của tài khoản; giao diện ở `/settings/consents` |
| UC114 | Dùng thử nhận dạng | ✓ | Khách vãng lai, hạn mức 60 phút/ngày đếm bằng Redis bitmap |

**Nguyên tắc đáng nêu:** một tài khoản đã xác thực nhưng chưa chấp thuận văn bản
pháp lý đang hiệu lực thì **đăng nhập được nhưng không ghi được gì**. Đây là hành
vi có chủ ý: chặn ngay tại cửa đăng nhập sẽ khiến người dùng không đọc được chính
văn bản mà họ được yêu cầu chấp thuận.

### F2 — Thu thập và quản lý dữ liệu mẫu ✓

| Mã | Chức năng | Trạng thái | Ghi chú cài đặt |
|---|---|:--:|---|
| UC201 | Thu mẫu từ camera | ✓ | Trích điểm mốc **tại trình duyệt**; màn hình `/upload`, tab "Ghi hình trực tiếp" |
| UC202 | Tải lên tệp video | ✓ | Bản gốc ghi vào kho thô **trước** mọi bước chuẩn hoá |
| UC203 | Xử lý bản ghi | ✓ | Loại `internal`; do tiến trình nền khởi phát, **không có tác nhân người** |
| UC204 | Theo dõi trạng thái tác vụ | ✓ | Trạng thái "đang xử lý" là trạng thái hợp lệ, không phải lỗi |
| UC205 | Đặt tuỳ chọn thu | ✓ | Ngôn ngữ, phương ngữ mặc định của tài khoản |
| UC206 | Duyệt danh mục lớp | ✓ | `/labels` |
| UC207 | Xem chi tiết lớp | ✓ | `/labels/:id`, đã mở cho người dùng thường |
| UC208 | Xem lại video phiên thu | ✓ | Bản dựng khung xương, ba bộ dựng hình |
| UC209 | Xoá phiên thu | ✓ | Xoá **mềm** |
| UC210 | Gán lại người ký cho phiên thu | ✓ | Sửa được quy kết sai sau khi thu |
| UC211 | Xoá mẫu | ✓ | Xoá mềm, qua thùng rác |
| UC212 | Quản lý thùng rác | ✓ | `/trash`, phạm vi theo người dùng |
| UC213 | Xuất ảnh chụp bộ dữ liệu | ✓ | Ghim phiên bản danh mục vào bản xuất |

**Bốn quyết định định hình nhóm này:**

1. **Hai nguồn đầu vào, một kết quả.** Webcam và tải tệp là hai use case khác
   nhau nhưng kết thúc ở cùng một chỗ — một mẫu đã trích đặc trưng. Chúng khái
   quát hoá về use case trừu tượng *Thu nhận mẫu*.
2. **Trích đặc trưng ở phía trình duyệt** (quyền riêng tư + hiệu quả lưu trữ).
3. **Lưu bản thô trước khi chuẩn hoá** (một lỗi xử lý không làm mất dữ liệu gốc).
4. **Xoá là xoá mềm.** Xoá phiên thu, xoá mẫu và gỡ lớp là ba mức của cùng một
   ngữ nghĩa, đi qua thùng rác, khôi phục được cho tới khi dọn hẳn.

### F3 — Danh mục từ vựng và phương ngữ ✓

Quản lý lớp từ vựng, phương ngữ, vùng miền, nhóm từ vựng, hồ sơ nhận dạng, và
**phiên bản danh mục bất biến** (`registry_versions`, 89 bản ghi tại thời điểm
chụp 10/08/2026).

Mô hình **ba mặt phẳng**, và luật xuyên suốt:

```
Danh mục hệ thống ──sao chép MỘT LẦN──► Danh mục của tổ chức ──ghim──► Bộ dữ liệu
 (quản trị nền tảng)                     (tổ chức tự sửa)             (bất biến, có mã băm)
```

**Lúc chạy KHÔNG bao giờ rơi ngược về mặt phẳng cộng đồng.** Thiếu dữ liệu danh
mục thì hệ thống **dừng**, không suy đoán. Ba lỗi có thật đã thúc đẩy thiết kế
này, trong đó có việc danh sách hồ sơ nhận dạng gắn cứng ở hai nơi và lệch nhau
(6 mục so với 5) khiến **7 lớp bị loại khỏi bước chia dữ liệu trong im lặng**.

**Định danh một lớp gồm năm cột**, trong đó có phương ngữ và vùng miền. Hai lớp
cùng nhãn khác phương ngữ là **hai lớp**, không phải một lớp có thuộc tính khác.

### F4 — Huấn luyện, đánh giá và suy luận ✓ / △

| Chức năng | Trạng thái | Ghi chú |
|---|:--:|---|
| Xếp hàng và chạy tác vụ huấn luyện | ✓ | Dịch vụ `trainer` riêng, chiếm GPU |
| Ba cổng chặn huấn luyện | ✓ | Đồng thuận · sàn số mẫu mỗi lớp · hạn mức tổ chức |
| Ghim phiên bản danh mục vào tác vụ | ✓ | Điều kiện để tái lập thí nghiệm |
| Theo dõi chỉ số theo chu kỳ | ✓ | `training_metrics` |
| Thăng hạng mô hình | ✓ | Hành động tường minh, có bản ghi, đảo ngược được |
| Nhận dạng thời gian thực | ✓ | Kết nối dài tới `realtime_service`, mô hình nạp sẵn trong bộ nhớ |
| Đọc thành tiếng (TTS) | ✓ | `edge-tts` |
| Cách ly theo tổ chức trên nửa sau vòng đời | △ | Mới ở mức kiến trúc đích, **chưa cưỡng chế ở mọi đường** |

**Ba cổng chặn hỏi ba câu khác nhau và không thay thế được cho nhau:**

| Cổng | Hỏi gì | Áp ở đâu | Hỏng thì hậu quả |
|---|---|---|---|
| Đồng thuận | Người ký cho phép dùng ở mức phát hành này không? | Lúc **chọn** mẫu | Phát hành vượt phạm vi được phép |
| Sàn số mẫu mỗi lớp | Lớp này đủ mẫu để chia tập không? | **Trước** khi đánh chỉ số lớp | Tập kiểm thử rỗng; chỉ số vô nghĩa |
| Hạn mức tổ chức | Tổ chức còn hạn mức tính toán không? | Lúc **xếp hàng** | Một tổ chức chiếm hết GPU chung |

**Phát biểu đúng mức, phải giữ nhất quán:** hệ thống **không** "nhận dạng ngôn
ngữ ký hiệu Việt Nam". Nó phục vụ nhận dạng cho **các miền từ vựng có mô hình đã
đăng ký**. Độ tin cậy của một lượt suy luận đơn lẻ **không phải** chỉ số chất
lượng — nó là đầu ra của một lượt chạy, không phải kết quả của một phép đánh giá.

### F5 — Tổ chức và đăng ký dịch vụ ✓ / △

| Chức năng | Trạng thái | Ghi chú |
|---|:--:|---|
| Tạo và quản lý tổ chức | ✓ | `/admin/tenants` (nền tảng), `/settings/organization` (tổ chức) |
| Mời thành viên | ✓ | Đường đưa người vào của quản trị tổ chức **bắt buộc** là lời mời |
| Gán vai theo phạm vi | ✓ / △ | Cưỡng chế chứng minh được ở cấp **hệ thống** và cấp **tổ chức**. Engine Casbin chạy ở chế độ **`shadow`** — quan sát và so sánh, **hệ phân quyền cũ hai phạm vi là bên quyết định** |
| Hạn mức và gói cước | ✓ | 4 gói; giá trị **rỗng** ở cột hạn mức nghĩa là *không giới hạn*, không phải *bằng không* |
| Vòng đời đăng ký (kỳ hạn, nhắc, ân hạn, khoá mềm) | ✓ | Trạng thái `past_due` **vẫn ghi được** — là chủ ý |
| Thu tiền | ○ | Không có cổng thanh toán. `tenant_usage_daily` là nguồn để **tính**, không phải để thu |
| Xuất dữ liệu tổ chức / dọn sạch dữ liệu | ✓ | Dọn sạch đòi xác thực lại trong phiên |
| Phạm vi *không gian làm việc* và *dự án* | △ | **Bề mặt vận hành đã có từ 18/08/2026**: router `workspaces` (12 điểm cuối) + màn hình `/settings/workspaces` — tạo/lưu trữ workspace và project, gán và thu vai ở hai cấp. **Hai giới hạn còn nguyên:** dữ liệu (`samples`, `classes`, `training_jobs`) vẫn **chưa mang `project_id`**, và `AUTHZ_MODE=shadow` nên vai ở hai cấp này **chưa đổi được kết quả kiểm quyền**. Cách ly ở hai cấp đó vì thế vẫn **chưa chứng minh được** từ bên ngoài |

### F6 — Quản trị người dùng và chính sách ✓

Quản lý tài khoản toàn nền tảng, khoá/mở tài khoản, chặn địa chỉ IP, soạn – công
bố – thu hồi văn bản pháp lý, đọc nhật ký kiểm toán, cấu hình nền tảng.

**Văn bản pháp lý đã công bố là bất biến ở tầng cơ sở dữ liệu** (trigger, không
phải kiểm tra ở ứng dụng). Một cờ riêng tách "sửa lỗi chính tả" khỏi "đổi phạm vi
xử lý dữ liệu"; chỉ loại thứ hai buộc chấp thuận lại.

**Thao tác không hoàn tác được đòi xác thực lại trong phiên** — áp cho ba use
case: dọn sạch dữ liệu tổ chức, công bố văn bản pháp lý, đổi gói cước.

### F7 — Vận hành hệ thống và nguồn sự thật ✓ / △

| Chức năng | Trạng thái | Ghi chú |
|---|:--:|---|
| Công bố nguồn sự thật đã ký (SHA-256 + Ed25519) | ✓ | Chỉ máy được cấp khoá ký mới công bố được |
| Xác minh lúc khởi động, fail-closed | ✓ | `sot-init` thoát mã lỗi chuyên biệt → **chặn toàn bộ hệ thống khởi động** |
| Quản lý khoá ký được tin cậy | ✓ | `/admin/sot`; khoá trong DB hợp nhất với bộ khoá cam kết trong mã |
| Đối soát CSV ↔ cơ sở dữ liệu | ✓ | Tác vụ định kỳ, chiều CSV → CSDL |
| Sao lưu theo lịch + diễn tập khôi phục | ✓ | `pg_backup.sh --drill`; mã hoá và sao chép sang ổ khác **mặc định tắt** |
| Kiểm chứng độ tươi triển khai | ✓ | Bắt ba kiểu lệch giữa mã đang chạy và mã nguồn |
| Đơn điệu phiên bản của nguồn sự thật | △ | Hệ thống **chấp nhận** bản công bố có số hiệu phiên bản thấp hơn bản đang dùng — giá trị dùng chung bị ghi đè lùi |

**Hợp đồng xác minh có bốn vế, không thay thế được cho nhau:**

```
Tạo tác hợp lệ = Toàn vẹn ∧ Chữ ký hợp lệ ∧ Người ký được tin cậy ∧ Chính sách phiên bản hợp lệ
```

Vế thứ ba dễ bỏ sót nhất: kẻ tấn công dựng dữ liệu khác, tính mã băm đúng, viết
bản kê đúng, rồi **tự ký bằng khoá của hắn** — chữ ký ấy hợp lệ về mật mã. Cài
đặt ở đây trả về **tên khoá đã đăng ký** thay vì một giá trị đúng/sai. Vế thứ tư
là giới hạn đã biết, nêu ở dòng △ trên.

### F8 — Hỗ trợ và tích hợp ✓ / ○

| Chức năng | Trạng thái | Ghi chú |
|---|:--:|---|
| Phiếu hỗ trợ và tin nhắn trong phiếu | ✓ | `/settings/support` (người dùng), `/admin/support` (trực hàng đợi) |
| Thư thông báo phiếu mới và thư tồn đọng | ✓ | Hai loại khác nhau: sự kiện vs trạng thái (5h / 10 tin) |
| Thông báo trong ứng dụng | ✓ | `/notifications` |
| Khoá API cho ứng dụng bên thứ ba | ✓ | Lưu **mã băm**; mất khoá thì tạo mới, không khôi phục |
| Webhook (điểm nhận sự kiện + lịch sử gửi) | ✓ | Có bảng, có điểm cuối; `webhook_deliveries` chưa có bản ghi thật |
| Giao diện cho 20 API quản trị tổ chức | ○ | API có, màn hình tương ứng chưa đủ |

---

## 1.5 Luồng nghiệp vụ trục chính

Toàn bộ nghiệp vụ xoay quanh **vòng đời của một mẫu dữ liệu**:

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
[7] Huấn luyện & đánh giá        → qua ba cổng chặn
        ↓
[8] Thăng hạng & phục vụ         → mô hình đang phục vụ, nhận dạng thời gian thực
```

**Hai nhánh cắt ngang** vòng đời này, và chúng là chỗ hệ thống khác một công cụ
thu dữ liệu thông thường:

* **Nhánh rút đồng thuận.** Người ký rút đồng thuận ở bước [1] thì mọi bản phát
  hành **sau đó** ở bước [6] phải loại dữ liệu của họ. Nhánh này chạy **ngược
  chiều** dòng chảy chính — đó là lý do đồng thuận không thể là một cột siêu dữ
  liệu thụ động.
* **Nhánh nguồn sự thật.** Danh mục ở bước [2] công bố dưới dạng tạo tác đã ký;
  mọi máy chủ trước khi chạy phải xác minh chữ ký. Không xác minh được thì **dừng
  cả hệ thống**.

---

## 1.6 Ngoài phạm vi sản phẩm

| Thuộc phạm vi | Ngoài phạm vi |
|---|---|
| Thu nhận qua webcam và qua tệp video | Nhận dạng ký hiệu **liên tục** (câu, đoạn) |
| Biểu diễn bằng điểm mốc bàn tay (126 chiều/khung) | Tư thế toàn thân và biểu cảm khuôn mặt |
| Danh mục từ vựng, phương ngữ, vùng miền có phiên bản | Xây dựng từ điển VSL đầy đủ |
| Cách ly dữ liệu giữa tổ chức, cưỡng chế ở tầng CSDL | Cách ly **hiệu năng** giữa các tổ chức |
| Đồng thuận, quy kết và quản trị dữ liệu chủ thể | Cơ chế pháp lý thu hồi giấy phép đã cấp cho bên thứ ba |
| Huấn luyện mô hình nhận dạng từ đơn và phục vụ suy luận | Cải tiến kiến trúc mô hình học sâu |
| Nguồn sự thật ký số cho danh mục và lược đồ | Sổ cái phân tán |
| Đo và ghi nhận mức sử dụng theo ngày | **Thu tiền** — không có cổng thanh toán |

Hai loại trừ dễ bị hiểu nhầm thành thiếu sót, nên nói rõ:

* **Không đánh giá độ chính xác mô hình.** Đối tượng của đề tài là hạ tầng. Một
  con số độ chính xác cao trên bộ dữ liệu mất cân bằng hiện tại (64 % là lớp bảng
  chữ cái) sẽ nói về bộ dữ liệu chứ không nói về hệ thống.
* **Không chứng minh cách ly hiệu năng.** Hệ thống có hạn mức và giới hạn tần
  suất, nhưng hai thứ đó không chứng minh được một tổ chức không làm chậm tổ chức
  khác. Khẳng định đó cần một thí nghiệm tải riêng, và luận văn không làm.
