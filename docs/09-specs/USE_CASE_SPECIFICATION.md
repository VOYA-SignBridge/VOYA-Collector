# Đặc tả Use Case — CTU.SignBridge / VOYA-Collector

*Hệ thống thu thập, quản lý và huấn luyện dữ liệu Ngôn ngữ Ký hiệu Việt Nam
theo mô hình SaaS đa tổ chức (multi-tenant). Bản 2.0 — dựng lại 2026-08-13.*

---

## 1. Phạm vi và quy ước đọc

### 1.1 Tài liệu này dựa trên cái gì

Toàn bộ use case dưới đây được bóc **từ mã nguồn đang chạy**: 26 bộ định tuyến
backend, hơn 30 trang giao diện, và bộ công cụ vận hành trong `scripts/`. Mỗi use
case có ít nhất một endpoint, một màn hình hoặc một script thật đứng sau. Chỗ nào
hệ thống **chưa** làm được, tài liệu nói thẳng là chưa (xem UC503 và UC213) chứ
không mô tả thứ chỉ tồn tại trong mong muốn.

### 1.2 Quy ước mã số

Mã use case gồm ba chữ số: **chữ số đầu là số hiệu nghiệp vụ**, hai chữ số sau là
thứ tự trong nghiệp vụ đó.

```
UC 4 02
   │  └── use case thứ 2 của nghiệp vụ 4
   └───── nghiệp vụ 4 (Huấn luyện, đánh giá và suy luận)
```

Nghiệp vụ 1 chạy từ UC101; nghiệp vụ 8 kết thúc ở UC806. Thứ tự trong mỗi nghiệp
vụ theo **dòng chảy nghiệp vụ**, không theo bảng chữ cái: use case đứng trước là
việc phải làm trước.

### 1.3 Khuôn trình bày

Mỗi use case gồm đúng các mục của mẫu chuẩn, theo thứ tự:

| Ô trong mẫu | Ở đây |
|---|---|
| Use Case / ID | dòng đầu của bảng thuộc tính |
| Main actor / Priority | dòng hai |
| Trigger / Type | dòng ba |
| Brief description | đoạn in nghiêng ngay dưới bảng |
| Relationship (Association / Include / Extend / Generalization) | danh sách bốn gạch đầu dòng |
| Normal flow | danh sách đánh số |
| Exceptional flow | danh sách đánh số, mỗi nhánh có tên in đậm |

**Priority** nhận ba giá trị: `Essential` (không có thì hệ thống không dùng được),
`Important` (thiếu thì nghiệp vụ khập khiễng nhưng vẫn chạy), `Optional`.
**Type** nhận `external` (một tác nhân ngoài khởi phát) hoặc `internal` (hệ thống
tự khởi phát, ví dụ hàng đợi hoặc bộ lập lịch).

**Quy ước chiều của quan hệ** — chỗ này hay bị vẽ ngược:

* `Include: X` nghĩa là **use case này gọi X**, và X luôn luôn chạy.
* `Extend: X` nghĩa là **use case này mở rộng X**, tức bản thân nó là phần thêm
  vào X trong một điều kiện nào đó. Use case **cơ sở không** liệt kê phần mở rộng
  của mình; chỗ nào cần nhắc, tài liệu ghi trong ngoặc *(UCxxx mở rộng use case
  này)* để tra ngược cho nhanh, chứ đó không phải khai báo quan hệ.

---

## 2. Tác nhân (Actors)

### 2.1 Bốn nhóm tác nhân

Hệ thống có **10 tác nhân người** chia làm bốn nhóm, và **6 tác nhân hệ thống**:

| Nhóm | Gồm | Đặc điểm chung |
|---|---|---|
| **Chưa có danh tính** | A1 Khách vãng lai | Không đăng nhập; chỉ chạm được phần công khai |
| **Người dùng cuối** | A2 Người dùng đã đăng nhập «abstract», A3 Người khiếm thính – khiếm ngôn, A4 Người dùng bình thường | Dùng hệ thống để **giao tiếp** và giữ tài khoản của mình |
| **Bên tổ chức / bên thứ ba** | A5 Thành viên tổ chức, A6 Biên tập viên / Nghiên cứu sinh, A7 Quản trị tổ chức | Thuộc một tổ chức; **đóng góp và khai thác dữ liệu** trong ranh giới tổ chức đó |
| **Bên vận hành nền tảng** | A8 Quản trị nền tảng, A9 Nhân viên hỗ trợ, A10 Kỹ sư vận hành | Giữ cả nền tảng chạy đúng, cho **mọi** tổ chức |

Nhóm "bên tổ chức / bên thứ ba" gộp cả **đối tác nghiên cứu**: một trường, một
nhóm nghiên cứu hay một doanh nghiệp dùng nền tảng đều vào hệ thống bằng cùng một
đường — một tổ chức (tenant) với thành viên của nó. Nghiên cứu sinh vì thế không
phải một nhánh riêng mà là **cách dùng** của vai biên tập (A6).

### 2.2 Cây kế thừa tác nhân

```
                      ┌───────────────────────┐
                      │  Người dùng (User)    │  «abstract»
                      └───────────┬───────────┘
                    ┌─────────────┴──────────────┐
        ┌───────────▼──────────┐   ┌─────────────▼─────────────────┐
        │ A1 Khách vãng lai    │   │ A2 Người dùng đã đăng nhập    │  «abstract»
        │    (Guest)           │   │    (Authenticated User)       │
        └──────────────────────┘   └─────────────┬─────────────────┘
                        ┌────────────────┬───────┴────────┬──────────────────┐
                        │                │                │                  │
              ┌─────────▼────────┐ ┌─────▼──────────┐ ┌───▼──────────────┐ ┌─▼──────────────────┐
              │ A3 Người khiếm   │ │ A4 Người dùng  │ │ A5 Thành viên    │ │ A8 Quản trị        │
              │ thính – khiếm    │ │ bình thường    │ │ tổ chức          │ │ nền tảng           │
              │ ngôn             │ │ (nghe – nói)   │ └───┬──────────────┘ └─┬──────────────────┘
              └──────────────────┘ └────────────────┘     │                  │
                                                 ┌────────▼─────────┐   ┌────▼──────────────┐
                                                 │ A6 Biên tập viên │   │ A9 Nhân viên hỗ   │
                                                 │ / Nghiên cứu sinh│   │ trợ               │
                                                 └────────┬─────────┘   ├───────────────────┤
                                                 ┌────────▼─────────┐   │ A10 Kỹ sư vận     │
                                                 │ A7 Quản trị      │   │ hành              │
                                                 │ tổ chức          │   └───────────────────┘
                                                 └──────────────────┘
```

Ba chuỗi kế thừa:

* `A2 → A5 → A6 → A7` — **bên tổ chức**: quản trị tổ chức làm được mọi việc của
  biên tập viên, biên tập viên làm được mọi việc của thành viên. Từng bậc đều
  hệ thống kiểm được, bằng `tenant_members.role`.
* `A2 → {A3, A4}` — **người dùng cuối**: hai chân dung người dùng của cùng một
  tài khoản đã đăng nhập.
* `A8 → {A9, A10}` — **bên vận hành**: hỗ trợ và vận hành là hai công việc khác
  nhau trên cùng một quyền nền tảng.

### 2.3 Tác nhân người — chi tiết

Cột cuối trả lời một câu: **hệ thống có tự phân biệt được vai này không?** Tức là
khi một tài khoản gọi tới, phần mềm có căn cứ nào để nói "anh là vai này, không
phải vai kia" và **chặn** nếu sai — hay đó chỉ là quy ước giữa người với nhau.

| Ký hiệu | Nghĩa | Hệ quả |
|---|---|---|
| ✅ **Kiểm được** | Có một điều kiện cụ thể trong mã hoặc CSDL quyết định vai này | Gọi sai vai thì bị từ chối. Đây là **ràng buộc của hệ thống**, viết vào luận văn được. |
| 🟡 **Kiểm được một phần** | Kiểm được lớp quyền bao ngoài, nhưng không kiểm được chính vai đó | Ví dụ: biết là quản trị nền tảng, nhưng không biết người đó đang trực hỗ trợ hay đang vận hành hạ tầng. |
| ⚠️ **Không kiểm được** | Không có cột, cờ hay điều kiện nào phân biệt | Vai này chỉ tồn tại ở **quy trình** và ở mô hình nghiệp vụ. Hệ thống không ngăn được ai tự nhận. |

| Mã | Tác nhân | Kế thừa từ | Mục tiêu chính | Sở hữu use case | Hệ thống kiểm bằng |
|---|---|---|---|---|---|
| **A1** | **Khách vãng lai (Guest)** | Người dùng | Tìm hiểu, đọc văn bản pháp lý, dùng thử nhận dạng, tạo tài khoản | UC101, UC102, UC105, UC108, UC111, UC114, UC503 *(7)* | không có phiên đăng nhập ✅ |
| **A2** | **Người dùng đã đăng nhập (Authenticated User)** «abstract» | Người dùng | Giữ danh tính, hồ sơ, đồng thuận, thông báo và kênh hỗ trợ của chính mình | UC103, UC104, UC106, UC107, UC109, UC110, UC112, UC801, UC802, UC804 *(10)* | `get_current_user` ✅ |
| **A3** | **Người khiếm thính – khiếm ngôn (Deaf Signer)** | A2 | **Chủ thể dữ liệu**: ký hiệu bản ngữ để đóng góp mẫu, và dùng nhận dạng để giao tiếp | UC113, UC201, UC407 *(3)* | ⚠️ không phân biệt được |
| **A4** | **Người dùng bình thường (Hearing User)** | A2 | Nghe – nói được; dùng hệ thống để **hiểu** người ký, có thể ký hộ hoặc phiên dịch | UC408 *(1)* | ⚠️ không phân biệt được |
| **A5** | **Thành viên tổ chức (Organization Member)** | A2 | Đưa mẫu vào hệ thống và quản lý mẫu **của mình** trong tổ chức | UC202, UC204–UC209, UC211, UC212, UC305 *(10)* | là thành viên của một tenant ✅ |
| **A6** | **Biên tập viên / Nghiên cứu sinh (Editor / Researcher)** | A5 | Giữ danh mục lớp sạch, và biến dữ liệu thành mô hình + kết quả trích dẫn được | UC210, UC213, UC301–UC304, UC306, UC401–UC405, UC409 *(13)* | `tenant_members.role = 'editor'` ✅ |
| **A7** | **Quản trị tổ chức (Organization Admin)** | A8 | Điều hành **một** tổ chức: thành viên, hạn mức, xuất dữ liệu, tích hợp | UC502, UC504–UC507, UC805, UC806 *(7)* | `tenant_members.role = 'admin'` ✅ |
| **A8** | **Quản trị nền tảng (Platform Administrator)** | Người dùng | Đặt luật cho mọi tổ chức và giữ bằng chứng | UC307–UC310, UC406, UC501, UC508, UC601–UC609 *(16)* | `users.is_admin` ✅ |
| **A9** | **Nhân viên hỗ trợ (Support Staff)** | A8 | Trực hàng đợi phiếu hỗ trợ | UC803 *(1)* | 🟡 hiện dùng chung `require_admin` |
| **A10** | **Kỹ sư vận hành (Operations Engineer)** | A8 | Giữ hệ thống chạy đúng mã, đúng dữ liệu, có bản sao lưu | UC701–UC706 *(6)* | 🟡 `users.is_admin` + quyền trên máy chủ |

Use case duy nhất **không** thuộc tác nhân người nào là **UC203 Process
recording** — do S4 khởi phát, mang `Type: internal`.

### 2.4 Bốn tác nhân mà mã nguồn chưa phân biệt được

Cột cuối §2.3 đánh dấu ⚠️ hoặc 🟡 cho bốn tác nhân, nghĩa là **hệ thống không tự
phân biệt được** chúng. Ghi rõ ở đây để người đọc không tưởng nhầm rằng phần mềm
đang bảo đảm những phân biệt này:

| Tác nhân | Hiện trạng trong mã | Vì sao vẫn giữ trong mô hình |
|---|---|---|
| **A3** Người khiếm thính – khiếm ngôn | Không có cột nào phân loại người ký | Đây là **chủ thể dữ liệu** của cả đề tài. Mức đồng thuận (UC112, UC113) gắn với người ký, và chính người ký quyết định mẫu của mình được phát hành tới đâu. Bỏ A3 đi thì không còn ai để giải thích vì sao đồng thuận lại chi phối việc phát hành. |
| **A4** Người dùng bình thường | Như trên | Là **phía bên kia** của cuộc giao tiếp. Đầu ra giọng nói (UC408) tồn tại **chỉ vì** có người nghe ở đầu bên kia; không có A4 thì use case đó không có chủ. |
| **A9** Nhân viên hỗ trợ | Hàng đợi kiểm bằng `require_admin` | Công việc trực phiếu khác hẳn công việc đặt chính sách. Tách sẵn ở tầng mô hình để khi thêm vai `support` thì đặc tả không phải viết lại. |
| **A10** Kỹ sư vận hành | `users.is_admin` + quyền trên máy chủ | Sáu use case của A10 **chạy ngoài ứng dụng** (dòng lệnh trên máy triển khai), nên ranh giới thật của họ là quyền hệ điều hành chứ không phải một cột trong CSDL. |

Điều cần nhớ: **A3 và A4 khác nhau ở người, không khác nhau ở quyền.** Một tài
khoản của người khiếm thính và một tài khoản của người nghe được có đúng cùng bộ
quyền kỹ thuật. Cái tách họ ra là **mục tiêu** khi dùng hệ thống, và điều đó vẫn
tạo ra use case khác nhau — đó là lý do chính đáng để hai vai này tồn tại.

### 2.5 Ranh giới không được vẽ sai: A7 ≠ A8

**Quản trị nền tảng (A8) không kế thừa Quản trị tổ chức (A7), và ngược lại.** Đây
là ranh giới cứng trong mã, không phải lựa chọn thẩm mỹ:

| | A7 Quản trị **tổ chức** | A8 Quản trị **nền tảng** |
|---|---|---|
| Kiểm bằng | `tenant_members.role = 'admin'` | `users.is_admin` |
| Phạm vi | đúng **một** tổ chức | toàn nền tảng |
| Đưa người vào bằng | **lời mời** (UC502) | **gán trực tiếp** theo id (UC501) |
| Giao diện | `/organization` | 9 trang `/admin/*` |

Lý do rất cụ thể: gán thành viên **theo id tài khoản**, mà id tài khoản không phải
bí mật. Nếu quản trị viên tổ chức làm được việc đó, họ kéo được bất kỳ ai trên hệ
thống vào tổ chức của mình mà người kia không hay biết. Đường đưa người vào dành
cho A7 vì thế **bắt buộc** là lời mời — thứ đòi hỏi chính người được mời hành động.

### 2.6 Tác nhân hệ thống

| Mã | Tác nhân | Gồm những gì | Vai trò | Xuất hiện ở |
|---|---|---|---|---|
| **S1** | **Dịch vụ gửi tin (Notification Gateway)** | SMTP + cổng SMS | Gửi mã xác thực, lời mời, nhắc hạn, thư phiếu hỗ trợ, cảnh báo | UC103, UC502, UC506, UC801 |
| **S2** | **Kho lưu trữ ngoài (External Storage)** | Google Drive + Google Sheets | Giữ tệp đặc trưng `.npz`, video thô, bản xem trước; phản chiếu `samples.csv` để đối soát | UC201, UC202, UC212, UC508, UC703 |
| **S3** | **Dịch vụ suy luận (Inference Service)** | Suy luận realtime trên GPU + tổng hợp giọng nói | Phục vụ mô hình đang hoạt động, nạp nóng khi thăng hạng, đọc thành tiếng | UC114, UC406, UC407, UC408 |
| **S4** | **Tiến trình nền (Background Processor)** | Celery worker + Celery beat | Trích đặc trưng, tăng cường, dựng bản xem trước, xoá tệp, đối soát, sao lưu theo lịch | UC203, UC208, UC212, UC703, UC705 |
| **S5** | **Máy ghi nguồn sự thật (SOT Writer)** | Máy được cấp khoá ký | Ghi vào `samples.csv` và công bố | UC701, UC702 |
| **S6** | **Ứng dụng bên thứ ba (Third-party Client)** | Hệ thống ngoài dùng khoá API | Gọi API trong phạm vi scope của khoá; nhận sự kiện webhook | UC805, UC806 |

**S4 gộp worker và bộ lập lịch** nhưng giữ nguyên phân biệt quan trọng nhất của
chúng ở trường `Type`: `internal` nghĩa là **không ai bấm nút** — việc tự chạy
theo lịch hoặc theo hàng đợi.

### 2.7 Ma trận tác nhân × nghiệp vụ

`●` = tác nhân chính · `○` = có tham gia · trống = không đụng tới.

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

---

## 3. Tám nhóm nghiệp vụ

Ranh giới giữa các nghiệp vụ **không phải màn hình**, mà là **thứ đang bị quản
lý**: danh tính, dữ liệu thô, danh mục, mô hình, tổ chức, chính sách, hạ tầng, và
dịch vụ vành ngoài.

| # | Nghiệp vụ | Câu hỏi nghiệp vụ đó trả lời | Mã | Số UC | Tác nhân chính |
|---|---|---|---|:--:|---|
| **1** | Danh tính và quyền truy cập | Anh là ai, và anh đã đồng ý những gì? | UC101–UC114 | 14 | A1, A2, A3 |
| **2** | Thu thập và quản lý dữ liệu mẫu | Mẫu vào hệ thống bằng đường nào, và mất đi bằng đường nào? | UC201–UC213 | 13 | A3, A5, A6, S4 |
| **3** | Danh mục từ vựng và phương ngữ | Được phép thu **lớp** nào, theo phương ngữ nào? | UC301–UC310 | 10 | A6, A8 |
| **4** | Huấn luyện, đánh giá và suy luận | Dữ liệu thành mô hình bằng cách nào, rồi mô hình phục vụ ai? | UC401–UC409 | 9 | A3, A4, A6, S3 |
| **5** | Tổ chức và đăng ký dịch vụ | Ai thuộc về tổ chức nào, trong hạn mức nào? | UC501–UC508 | 8 | A7, A8 |
| **6** | Quản trị người dùng và chính sách | Ai đặt luật, và lấy gì làm bằng chứng? | UC601–UC609 | 9 | A6 |
| **7** | Vận hành hệ thống và nguồn sự thật | Hệ thống có đang chạy đúng thứ ta nghĩ không? | UC701–UC706 | 6 | A10, S4, S5 |
| **8** | Hỗ trợ và tích hợp | Hỏng thì kêu ai, và máy khác nối vào thế nào? | UC801–UC806 | 6 | A2, A7, A9, S6 |

**Cách các nghiệp vụ nối nhau.** NV1 → NV2 → NV3 là **vòng đời của một mẫu dữ
liệu**: có danh tính và đồng thuận trước, rồi mới thu được mẫu, và mẫu chỉ có
nghĩa khi thuộc về một lớp trong danh mục. NV4 là chỗ dữ liệu thành sản phẩm.
NV5, NV6, NV7 là ba tầng quản trị **không lồng nhau**: một tổ chức tự quản mình
(NV5), nền tảng đặt luật cho mọi tổ chức (NV6), còn hạ tầng bên dưới thì không
biết tổ chức là gì (NV7). NV8 là vành ngoài.

**Vì sao NV6 và NV7 tách ra** dù cùng do `users.is_admin` kiểm: hai nghiệp vụ này
trả lời hai câu khác nhau và hỏng theo hai kiểu khác nhau. NV6 sai thì **chính
sách sai** — một tài khoản có quyền nó không đáng có, một văn bản pháp lý sai
hiệu lực. NV7 sai thì **hệ thống mất dữ liệu hoặc chạy sai mã** — bản sao lưu
chưa từng chạy, mã cũ đang phục vụ, nguồn sự thật lệch khỏi bản sao. Người chịu
trách nhiệm cũng khác: NV6 cần người hiểu chính sách và pháp lý, NV7 cần người
hiểu hạ tầng.

---

## 4. Danh sách use case

### Nghiệp vụ 1 — Danh tính và quyền truy cập

| Mã | Use case | Main actor | Priority |
|---|---|---|---|
| UC101 | Register account | Guest | Essential |
| UC102 | Register by invitation | Guest | Essential |
| UC103 | Send verification code | Authenticated User | Essential |
| UC104 | Verify contact address | Authenticated User | Essential |
| UC105 | Log in | Guest | Essential |
| UC106 | Verify two-factor code | Authenticated User | Important |
| UC107 | Log out | Authenticated User | Essential |
| UC108 | Recover account | Guest | Essential |
| UC109 | Manage two-factor authentication | Authenticated User | Important |
| UC110 | Manage profile | Authenticated User | Important |
| UC111 | View legal document | Guest | Essential |
| UC112 | Accept legal document | Authenticated User | Essential |
| UC113 | Withdraw consent | Deaf Signer | Essential |
| UC114 | Use trial recognition | Guest | Optional |

### Nghiệp vụ 2 — Thu thập và quản lý dữ liệu mẫu

| Mã | Use case | Main actor | Priority |
|---|---|---|---|
| UC201 | Record sample from camera | Deaf Signer | Essential |
| UC202 | Upload video file | Organization Member | Essential |
| UC203 | Process recording | Background Processor (S4) | Essential |
| UC204 | Monitor job status | Organization Member | Important |
| UC205 | Set capture preferences | Organization Member | Optional |
| UC206 | Browse label catalog | Organization Member | Essential |
| UC207 | View label detail | Organization Member | Essential |
| UC208 | Preview session video | Organization Member | Important |
| UC209 | Delete capture session | Organization Member | Important |
| UC210 | Reassign session signer | Editor / Researcher | Optional |
| UC211 | Delete sample | Organization Member | Essential |
| UC212 | Manage trash | Organization Member | Important |
| UC213 | Export dataset snapshot | Editor / Researcher | Important |

### Nghiệp vụ 3 — Danh mục từ vựng và phương ngữ

| Mã | Use case | Main actor | Priority |
|---|---|---|---|
| UC301 | Register class | Editor / Researcher | Essential |
| UC302 | Update class | Editor / Researcher | Important |
| UC303 | Merge classes | Editor / Researcher | Important |
| UC304 | Remove class | Editor / Researcher | Important |
| UC305 | View collection statistics | Organization Member | Important |
| UC306 | Propose dialect | Editor / Researcher | Optional |
| UC307 | Moderate dialect proposal | Platform Administrator | Optional |
| UC308 | Maintain community catalog template | Platform Administrator | Important |
| UC309 | Publish community catalog version | Platform Administrator | Important |
| UC310 | Clone catalog into an organisation | Platform Administrator | Important |

### Nghiệp vụ 4 — Huấn luyện, đánh giá và suy luận

| Mã | Use case | Main actor | Priority |
|---|---|---|---|
| UC401 | Start training job | Editor / Researcher | Essential |
| UC402 | Monitor training progress | Editor / Researcher | Essential |
| UC403 | Cancel training job | Editor / Researcher | Important |
| UC404 | Review evaluation and provenance | Editor / Researcher | Important |
| UC405 | Test trained model | Editor / Researcher | Important |
| UC406 | Promote model version | Platform Administrator | Important |
| UC407 | Recognize sign in realtime | Deaf Signer | Essential |
| UC408 | Speak recognized text | Hearing User | Optional |
| UC409 | Prepare research release | Editor / Researcher | Important |

### Nghiệp vụ 5 — Tổ chức và đăng ký dịch vụ

| Mã | Use case | Main actor | Priority |
|---|---|---|---|
| UC501 | Manage tenants | Platform Administrator | Essential |
| UC502 | Invite member | Organization Admin | Essential |
| UC503 | Accept invitation | Guest | Essential |
| UC504 | Manage member role | Organization Admin | Important |
| UC505 | Remove member | Organization Admin | Important |
| UC506 | Manage subscription | Organization Admin | Important |
| UC507 | Request tenant data export | Organization Admin | Important |
| UC508 | Purge tenant data | Platform Administrator | Optional |

### Nghiệp vụ 6 — Quản trị người dùng và chính sách

| Mã | Use case | Main actor | Priority |
|---|---|---|---|
| UC601 | Elevate privileges | Platform Administrator | Important |
| UC602 | Manage user account | Platform Administrator | Essential |
| UC603 | Apply security action | Platform Administrator | Important |
| UC604 | Review audit log | Platform Administrator | Important |
| UC605 | Configure platform settings | Platform Administrator | Important |
| UC606 | Draft and review legal document | Platform Administrator | Important |
| UC607 | Publish legal document | Platform Administrator | Essential |
| UC608 | Review consent records | Platform Administrator | Important |
| UC609 | Manage billing plans | Platform Administrator | Optional |

### Nghiệp vụ 7 — Vận hành hệ thống và nguồn sự thật

| Mã | Use case | Main actor | Priority |
|---|---|---|---|
| UC701 | Manage SOT writer machines | Operations Engineer | Important |
| UC702 | Verify source-of-truth integrity | Operations Engineer | Important |
| UC703 | Synchronize storage and database | Operations Engineer | Important |
| UC704 | Monitor system health | Operations Engineer | Important |
| UC705 | Back up and restore data | Operations Engineer | Essential |
| UC706 | Verify deployment freshness | Operations Engineer | Important |

### Nghiệp vụ 8 — Hỗ trợ và tích hợp

| Mã | Use case | Main actor | Priority |
|---|---|---|---|
| UC801 | Create support ticket | Authenticated User | Important |
| UC802 | Reply to support ticket | Authenticated User | Important |
| UC803 | Handle support queue | Support Staff | Important |
| UC804 | View notifications | Authenticated User | Important |
| UC805 | Manage API keys | Organization Admin | Optional |
| UC806 | Manage webhook endpoints | Organization Admin | Optional |

---

## 5. Tổng hợp quan hệ

### 5.1 «include» — 13 quan hệ

Đọc là: **use case cột trái luôn gọi use case cột giữa**.

| Use case cơ sở | «include» | Vì sao luôn xảy ra |
|---|---|---|
| UC101 Register account | UC112 Accept legal document | Cưỡng chế đồng thuận đang BẬT: không chấp thuận thì tài khoản không tồn tại. |
| UC102 Register by invitation | UC103 Send verification code | Địa chỉ được mời vẫn phải được chứng minh là có thật. |
| UC104 Verify contact address | UC103 Send verification code | Không có mã thì không có gì để xác thực. |
| UC108 Recover account | UC103 Send verification code | Bước một của khôi phục chính là gửi mã. |
| UC112 Accept legal document | UC111 View legal document | Phải đọc được văn bản thì mới ký được nó. |
| UC201 Record sample from camera | UC203 Process recording | Mẫu chỉ tồn tại sau khi trích xuất đặc trưng. |
| UC202 Upload video file | UC203 Process recording | Cùng lý do, khác nguồn đầu vào. |
| UC503 Accept invitation | UC102 Register by invitation | Lời mời **chỉ** được tiêu thụ ở đường tạo tài khoản. |
| UC508 Purge tenant data | UC601 Elevate privileges | Thao tác không hoàn tác được, đòi xác thực lại. |
| UC607 Publish legal document | UC601 Elevate privileges | Bản đã công bố là bất biến, không sửa lại được. |
| UC609 Manage billing plans | UC601 Elevate privileges | Hạ gói hay treo một tổ chức gây hậu quả thương mại thật. |
| UC703 Synchronize storage and database | UC702 Verify source-of-truth integrity | Muốn sửa lệch thì phải biết lệch ở đâu trước. |
| UC803 Handle support queue | UC802 Reply to support ticket | Trực hàng đợi luôn kết thúc bằng một lượt trả lời. |

### 5.2 «extend» — 13 quan hệ

Đọc là: **use case cột trái là phần thêm vào use case cột giữa**, chỉ chạy khi
điều kiện ở cột phải đúng.

| Use case mở rộng | «extend» | Điều kiện |
|---|---|---|
| UC102 Register by invitation | UC101 Register account | Khi khách tới bằng liên kết lời mời có token. |
| UC106 Verify two-factor code | UC105 Log in | Khi tài khoản đã bật xác thực hai yếu tố. |
| UC109 Manage two-factor authentication | UC110 Manage profile | Khi người dùng vào phần Bảo mật. |
| UC113 Withdraw consent | UC112 Accept legal document | Khi người ký rút lại đồng thuận đã cho. |
| UC114 Use trial recognition | UC407 Recognize sign in realtime | Khi người dùng chưa đăng nhập; giới hạn số phút mỗi ngày. |
| UC208 Preview session video | UC207 View label detail | Khi muốn xem lại bản dựng của phiên thu. |
| UC210 Reassign session signer | UC207 View label detail | Khi phát hiện phiên thu gán sai người ký. |
| UC212 Manage trash | UC211 Delete sample | Khi cần hoàn tác hoặc xoá vĩnh viễn một mẫu. |
| UC212 Manage trash | UC304 Remove class | Khi cần hoàn tác hoặc xoá vĩnh viễn một lớp. |
| UC303 Merge classes | UC302 Update class | Khi việc cần làm là gộp hai lớp trùng, không phải đổi tên một lớp. |
| UC310 Clone catalog into an organisation | UC501 Manage tenants | Khi tổ chức vừa tạo cần danh mục mồi để bắt đầu thu. |
| UC405 Test trained model | UC404 Review evaluation and provenance | Khi muốn thử một mẫu thật trước khi quyết định thăng hạng. |
| UC408 Speak recognized text | UC407 Recognize sign in realtime | Khi người dùng bật đầu ra giọng nói. |

### 5.3 «generalization» — use case

| Use case cha | Use case con | Ghi chú |
|---|---|---|
| **Capture sample** «abstract» | UC201 Record sample from camera, UC202 Upload video file | Hai nguồn đầu vào, cùng một kết quả: một mẫu đã trích đặc trưng. |
| **Remove data** «abstract» | UC209 Delete capture session, UC211 Delete sample, UC304 Remove class | Cùng ngữ nghĩa xoá mềm ba mức khác nhau. |
| UC103 Send verification code | Gửi qua thư (S1), gửi qua SMS (S1) | Hai kênh, cùng hợp đồng mã một lần. |

### 5.4 «generalization» — tác nhân

Xem cây ở §2.2. Ba chuỗi kế thừa:

| Chuỗi | Nội dung | Hệ thống kiểm được? |
|---|---|---|
| `A2 → A5 → A6 → A7` | Bên tổ chức: thành viên → biên tập viên / nghiên cứu sinh → quản trị tổ chức | ✅ Có — `tenant_members.role` |
| `A2 → {A3, A4}` | Người dùng cuối: người khiếm thính – khiếm ngôn và người dùng bình thường | ⚠️ Không — khác **mục tiêu**, không khác quyền (§2.4) |
| `A8 → {A9, A10}` | Bên vận hành: nhân viên hỗ trợ và kỹ sư vận hành | 🟡 Một phần — xem §2.4 |

`A1 Khách vãng lai` đứng ngoài mọi chuỗi vì chưa có danh tính, và `A8` tách khỏi
nhánh tổ chức vì thuộc một mặt phẳng quyền khác hẳn (§2.5).

## 6. Sơ đồ

### 6.1 Tác nhân và nghiệp vụ

```mermaid
flowchart LR
    G([A1 Khách vãng lai])
    AU([A2 Người dùng đã đăng nhập])
    DS([A3 Người khiếm thính – khiếm ngôn])
    HU([A4 Người dùng bình thường])
    OM([A5 Thành viên tổ chức])
    ED([A6 Biên tập viên / Nghiên cứu sinh])
    OA([A7 Quản trị tổ chức])
    PA([A8 Quản trị nền tảng])
    SS([A9 Nhân viên hỗ trợ])
    OE([A10 Kỹ sư vận hành])

    NV1[NV1 · Danh tính<br/>UC101–UC114]
    NV2[NV2 · Thu thập dữ liệu<br/>UC201–UC213]
    NV3[NV3 · Danh mục từ vựng<br/>UC301–UC310]
    NV4[NV4 · Huấn luyện & suy luận<br/>UC401–UC409]
    NV5[NV5 · Tổ chức<br/>UC501–UC508]
    NV6[NV6 · Chính sách<br/>UC601–UC609]
    NV7[NV7 · Vận hành<br/>UC701–UC706]
    NV8[NV8 · Hỗ trợ & tích hợp<br/>UC801–UC806]

    G --> NV1
    AU --> NV1
    AU --> NV8
    DS --> NV1
    DS --> NV2
    DS --> NV4
    HU --> NV4
    OM --> NV2
    ED --> NV2
    ED --> NV3
    ED --> NV4
    OA --> NV5
    OA --> NV8
    PA --> NV3
    PA --> NV5
    PA --> NV6
    SS --> NV8
    OE --> NV7

    NV1 -.-> S1[[S1 Dịch vụ gửi tin]]
    NV2 -.-> S2[[S2 Kho lưu trữ ngoài]]
    NV2 -.-> S4[[S4 Tiến trình nền]]
    NV4 -.-> S3[[S3 Dịch vụ suy luận]]
    NV7 -.-> S5[[S5 Máy ghi SOT]]
    NV8 -.-> S6[[S6 Ứng dụng bên thứ ba]]

    DS -.kế thừa.-> AU
    HU -.kế thừa.-> AU
    OM -.kế thừa.-> AU
    ED -.kế thừa.-> OM
    OA -.kế thừa.-> ED
    SS -.kế thừa.-> PA
    OE -.kế thừa.-> PA
```

### 6.2 Vòng đời một mẫu dữ liệu, xuyên ba nghiệp vụ

```mermaid
flowchart TD
    A[UC112 Đồng thuận<br/>NV1] --> B[UC301 Đăng ký lớp<br/>NV3]
    B --> C{Nguồn đầu vào}
    C -->|camera| D[UC201 Quay mẫu]
    C -->|tệp video| E[UC202 Tải video]
    D --> F[UC203 Xử lý bản ghi<br/>internal · S4]
    E --> F
    F --> G[UC207 Xem chi tiết lớp]
    G --> H{Dùng được?}
    H -->|không| I[UC209/UC211 Xoá mềm]
    I --> J[UC212 Thùng rác]
    J -->|khôi phục| G
    J -->|xoá vĩnh viễn| K[(Mất hẳn)]
    H -->|có| L[UC213 Ảnh chụp dữ liệu<br/>NV2]
    L --> M[UC401 Huấn luyện<br/>NV4]
    M --> N[UC406 Thăng hạng mô hình]
    A -.rút lại.-> O[UC113 Rút đồng thuận]
    O -.loại khỏi mọi bản phát hành sau.-> L
```

---

## 7. Cách dùng tài liệu này khi viết quyển

Mỗi khối ở §8–§15 khớp **1-1** với ô trong mẫu bảng viền của quyển luận văn. Bảng
ba dòng ở đầu mỗi khối là sáu ô trên cùng của mẫu (Use Case / ID / Main actor /
Priority / Trigger / Type); phần còn lại giữ nguyên thứ tự Brief description →
Relationship → Normal flow → Exceptional flow. Markdown không có ô gộp
(`colspan`), nên bốn mục sau nằm **dưới** bảng thay vì nằm trong ô — khi chép vào
Word thì gộp lại thành một khung là khớp mẫu.

---

## 8. Đặc tả chi tiết — Nghiệp vụ 1: Danh tính và quyền truy cập

### UC101 — Register account

| **Use Case** | Register account | **ID** | UC101 |
|---|---|---|---|
| **Main actor** | Guest | **Priority** | Essential |
| **Trigger** | Guest | **Type** | external |

**Brief description:** *The Guest creates a platform account with a username, an email address and a password. The account is created inside a tenant and cannot be used until the legal documents in force have been accepted.*

**Relationship:**
- **Association:** Guest – Register account
- **Include:** UC112 Accept legal document
- **Extend:** None *(UC102 mở rộng use case này)*
- **Generalization:** None

**Normal flow:**
1. System displays the registration form and the list of legal documents currently in force.
2. The Guest enters username, email address, password and password confirmation.
3. The Guest ticks the acceptance box for each document in force (UC112).
4. The Guest clicks the "Create account" button.
5. System checks the per-minute attempt limit and the per-day account-creation limit for the caller IP.
6. System checks that self-serve signup is enabled, that the username and the email are not already taken, and that the password meets the strength policy.
7. System creates the account in the tenant, stores one consent record per accepted document together with the document content hash, and writes an audit entry.
8. System sends a verification code to the email address (UC103) and signs the Guest in as an Authenticated User.

**Exceptional flow:**
1. **Signup closed:** In step 6, if self-serve signup is disabled and no invitation token is present, System refuses with "the platform only accepts members by invitation". The Guest must obtain an invitation (UC102).
2. **Duplicate identity:** In step 6, if the username or the email already exists, an error message is displayed on the offending field. The Guest then edits it and resubmits.
3. **Weak password:** In step 6, if the password fails the strength policy, System displays the unmet requirements and the account is not created.
4. **Rate limit reached:** In step 5, if the IP exceeded the attempt limit, System refuses and displays the time remaining before the next attempt.
5. **Consent not given:** In step 3, if any document in force is left unticked, the "Create account" button stays disabled — enforcement is on, so an account without consent cannot exist.

---

### UC102 — Register by invitation

| **Use Case** | Register by invitation | **ID** | UC102 |
|---|---|---|---|
| **Main actor** | Guest | **Priority** | Essential |
| **Trigger** | Guest opens an invitation link | **Type** | external |

**Brief description:** *The Guest registers by using an invitation token issued by an Organization Admin. The token decides which tenant the account lands in and which role it starts with, so registration is possible even when self-serve signup is closed.*

**Relationship:**
- **Association:** Guest – Register by invitation
- **Include:** UC103 Send verification code
- **Extend:** UC101 Register account
- **Generalization:** None

**Normal flow:**
1. The Guest opens the invitation link received by email.
2. System inspects the token and displays the inviting organisation name, the invited email address and the offered role.
3. The Guest enters username and password; the email field is pre-filled from the invitation and is read-only.
4. The Guest accepts the legal documents in force and clicks "Join".
5. System validates the token **before** creating the account: not expired, not revoked, not already consumed.
6. System creates the account, attaches it to the inviting tenant with the invited role, marks the invitation consumed and writes an audit entry.
7. System signs the Guest in and lands them on the organisation dashboard.

**Exceptional flow:**
1. **Stale token:** In step 5, if the invitation is expired, revoked or already used, System refuses and no account is created — the check runs before creation precisely so that a real account is never stranded in the wrong tenant.
2. **Email mismatch:** In step 3, if the Guest edits the invited address, System ignores the edit and keeps the invited address; an invitation is bound to one address.
3. **Account already exists:** In step 5, if the invited address already has an account, System redirects to the sign-in screen and applies the membership after sign-in (UC503).

---

### UC103 — Send verification code

| **Use Case** | Send verification code | **ID** | UC103 |
|---|---|---|---|
| **Main actor** | Authenticated User | **Priority** | Essential |
| **Trigger** | Authenticated User requests a code | **Type** | external |

**Brief description:** *System issues a one-time code to an address (email or phone number) so that the holder can prove control of it. The code is used by contact verification, by account recovery and by the invitation flow.*

**Relationship:**
- **Association:** Authenticated User – Send verification code; Notification Gateway (S1)
- **Include:** None
- **Extend:** None
- **Generalization:** Send by email, Send by SMS

**Normal flow:**
1. The user asks System to send a code to an email address or a mobile number.
2. System checks the per-IP hourly cap and the per-address resend cooldown.
3. System generates a one-time code, stores its hash with a time-to-live, and discards any previous unused code for the same address.
4. System hands the code to the Notification Gateway (S1) or the Notification Gateway (S1) according to the chosen channel.
5. System returns the remaining cooldown and the code lifetime so the screen can run the countdown.

**Exceptional flow:**
1. **Cooldown not elapsed:** In step 2, if the previous code was sent less than the cooldown ago, System refuses and displays the seconds remaining.
2. **Hourly cap reached:** In step 2, if the caller IP exceeded the hourly cap, System refuses; the cap counts sends, not successes.
3. **SMS channel unavailable:** In step 4, if no SMS provider is configured, System hides the SMS option and offers the email channel only.
4. **Delivery failure:** In step 4, if the provider rejects the message, System reports a send failure and does not consume the cooldown.

---

### UC104 — Verify contact address

| **Use Case** | Verify contact address | **ID** | UC104 |
|---|---|---|---|
| **Main actor** | Authenticated User | **Priority** | Essential |
| **Trigger** | Authenticated User | **Type** | external |

**Brief description:** *The Authenticated User proves control of the email address or the mobile number attached to the account by entering the one-time code received on that channel.*

**Relationship:**
- **Association:** Authenticated User – Verify contact address
- **Include:** UC103 Send verification code
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. System displays the verification status of the account: which address is on file and whether it has already been proven.
2. The user picks the address to verify and clicks "Send code" (UC103).
3. System asks the user for the code sent to that address.
4. The user enters the verification code.
5. System verifies the code against the stored hash and its lifetime. It is ok.
6. System stamps the verification time on the account, consumes the code, and refreshes the status display.

**Exceptional flow:**
1. **Wrong code:** In step 5, if the code does not match, System displays "wrong code" and lets the user retry until the attempt budget for that code is exhausted; the code is then invalidated and a new one must be requested.
2. **Expired code:** In step 5, if the code lifetime has elapsed, System refuses and offers to resend after the cooldown.
3. **Address changed meanwhile:** In step 5, if the address on the account changed after the code was issued, System invalidates the code — a code proves control of the address it was sent to, not of the account.

---

### UC105 — Log in

| **Use Case** | Log in | **ID** | UC105 |
|---|---|---|---|
| **Main actor** | Guest | **Priority** | Essential |
| **Trigger** | Guest | **Type** | external |

**Brief description:** *The Guest signs in with a username (or email) and a password and receives a session. If two-factor authentication is enabled on the account, the session is only issued after the second factor.*

**Relationship:**
- **Association:** Guest – Log in
- **Include:** None
- **Extend:** None *(UC106 mở rộng use case này)*
- **Generalization:** None

**Normal flow:**
1. System displays the sign-in form.
2. The Guest enters the username (or email) and the password, then clicks "Sign in".
3. System checks the per-IP and per-account attempt limits.
4. System verifies the password hash. It is ok.
5. System checks the account state: active, not locked, consents in force accepted, subscription not hard-blocked.
6. System issues an access token and a refresh token, records the session with its device and IP, and writes an audit entry.
7. System lands the user on the dashboard and displays any pending administrative notice.

**Exceptional flow:**
1. **Wrong credentials:** In step 4, System returns one generic error for both an unknown account and a wrong password, so the form cannot be used to enumerate accounts.
2. **Two-factor required:** In step 6, if 2FA is enabled, System issues no session yet and asks for the second factor (UC106).
3. **Account locked or suspended:** In step 5, System refuses and displays the reason recorded by the administrator, with the support channel.
4. **Consent outstanding:** In step 5, if a document in force has not been accepted, System signs the user in but routes them to the consent screen and blocks every write until accepted (UC112).
5. **Attempt limit reached:** In step 3, System refuses further attempts from that IP or account for the lockout window.

---

### UC106 — Verify two-factor code

| **Use Case** | Verify two-factor code | **ID** | UC106 |
|---|---|---|---|
| **Main actor** | Authenticated User | **Priority** | Important |
| **Trigger** | Account has 2FA enabled | **Type** | external |

**Brief description:** *The user completes sign-in by entering the six-digit code produced by their authenticator application, or one of their recovery codes.*

**Relationship:**
- **Association:** Authenticated User – Verify two-factor code
- **Include:** None
- **Extend:** UC105 Log in
- **Generalization:** None

**Normal flow:**
1. System asks the user for the six-digit code from the authenticator application.
2. The user enters the code.
3. System validates the code against the account secret within the accepted time drift window. It is ok.
4. System marks the code as spent so the same code cannot be replayed inside its own window.
5. System issues the session and completes the sign-in started in UC105.

**Exceptional flow:**
1. **Wrong or expired code:** In step 3, System displays an error and lets the user retry; repeated failures consume the attempt budget and abort the sign-in.
2. **Lost device:** In step 2, the user enters a recovery code instead. System consumes that recovery code permanently and warns how many remain.
3. **No recovery code left:** In step 2, the user must use account recovery (UC108) or contact support (UC801).

---

### UC107 — Log out

| **Use Case** | Log out | **ID** | UC107 |
|---|---|---|---|
| **Main actor** | Authenticated User | **Priority** | Essential |
| **Trigger** | Authenticated User | **Type** | external |

**Brief description:** *The Authenticated User ends the current session. The refresh token is revoked and the access token is added to the deny list so that it stops working immediately rather than at its natural expiry.*

**Relationship:**
- **Association:** Authenticated User – Log out
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The user clicks "Sign out".
2. System revokes the refresh token of the current session and marks the session closed.
3. System adds the presented access token to the deny list until its natural expiry.
4. System clears the session cookies and writes an audit entry.
5. System redirects the user to the sign-in screen, staying under the deployment base path.

**Exceptional flow:**
1. **Session already gone:** In step 2, if the session was revoked from another device, System still clears the local state and reports a successful sign-out.
2. **Sign out everywhere:** In step 1, if the user chooses "sign out of all devices", System revokes every session of the account, not only the current one.

---

### UC108 — Recover account

| **Use Case** | Recover account | **ID** | UC108 |
|---|---|---|---|
| **Main actor** | Guest | **Priority** | Essential |
| **Trigger** | Guest | **Type** | external |

**Brief description:** *The Guest who cannot sign in recovers access through one door: identify the account, prove control of the address on file with a one-time code, then set a new password.*

**Relationship:**
- **Association:** Guest – Recover account
- **Include:** UC103 Send verification code
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Guest enters the email address or username of the account and clicks "Continue".
2. System sends a one-time code to the address on file (UC103).
3. System asks the Guest for the code.
4. The Guest enters the code; System verifies it and issues a short-lived recovery grant. The code is consumed at this step.
5. System asks for a new password and its confirmation.
6. The Guest enters the new password and confirms.
7. System stores the new password hash, revokes every existing session of the account, writes an audit entry and notifies the account owner by email.

**Exceptional flow:**
1. **Unknown account:** In step 2, System reports the same "if the address exists, a code has been sent" message either way, so the form cannot be used to test which addresses are registered.
2. **Wrong code:** In step 4, System displays an error; verify and confirm share one rate-limit bucket, so guessing the code exhausts the same budget as restarting the flow.
3. **Grant expired:** In step 6, if the recovery grant has expired, System refuses the new password and the Guest restarts from step 1.
4. **Two-factor enabled:** In step 4, if the account has 2FA, System additionally asks for a second factor before issuing the grant.

---

### UC109 — Manage two-factor authentication

| **Use Case** | Manage two-factor authentication | **ID** | UC109 |
|---|---|---|---|
| **Main actor** | Authenticated User | **Priority** | Important |
| **Trigger** | Authenticated User | **Type** | external |

**Brief description:** *The Authenticated User enables, confirms or disables time-based one-time password authentication on the account and regenerates the recovery codes.*

**Relationship:**
- **Association:** Authenticated User – Manage two-factor authentication
- **Include:** None
- **Extend:** UC110 Manage profile
- **Generalization:** None

**Normal flow:**
1. The user opens the Security settings page; System displays whether 2FA is on and how many recovery codes remain.
2. The user clicks "Enable"; System generates a secret and displays it as a QR code and as text.
3. The user scans the code with an authenticator application and enters the six-digit code it produces.
4. System validates the code, activates 2FA on the account and displays the recovery codes exactly once.
5. The user stores the recovery codes and confirms.

**Exceptional flow:**
1. **Confirmation code wrong:** In step 4, 2FA is not activated and the pending secret is discarded; the user restarts from step 2.
2. **Disable:** The user clicks "Disable" and must re-enter the account password. System verifies it, removes the secret and the recovery codes, and writes an audit entry.
3. **Regenerate recovery codes:** The user re-enters the account password; System invalidates every previous recovery code and displays the new set once.
4. **Wrong password:** In the disable or regenerate branch, if the password is wrong, System refuses and the existing 2FA state is untouched.

---

### UC110 — Manage profile

| **Use Case** | Manage profile | **ID** | UC110 |
|---|---|---|---|
| **Main actor** | Authenticated User | **Priority** | Important |
| **Trigger** | Authenticated User | **Type** | external |

**Brief description:** *The Authenticated User views and updates their own account information: display name, username, contact address, interface language and signer profile fields.*

**Relationship:**
- **Association:** Authenticated User – Manage profile
- **Include:** None
- **Extend:** None *(UC109 mở rộng use case này)*
- **Generalization:** None

**Normal flow:**
1. The user opens the Account page; System displays the profile, the verification status and the consent history.
2. The user edits the fields to change and clicks "Save".
3. System validates the new values and checks that a new username or contact address is not already taken.
4. System stores the change and propagates the new username to every place that copied it, including the sample registry.
5. System displays the updated profile.

**Exceptional flow:**
1. **Username taken:** In step 3, System refuses and the previous username stays in force.
2. **Contact address changed:** In step 4, System clears the verification stamp of that address and asks the user to prove the new one (UC104).
3. **Historical records:** In step 4, the actor label already written into audit entries is **not** rewritten — it is historical evidence of who acted under that name at that time.

---

### UC111 — View legal document

| **Use Case** | View legal document | **ID** | UC111 |
|---|---|---|---|
| **Main actor** | Guest | **Priority** | Essential |
| **Trigger** | Guest | **Type** | external |

**Brief description:** *Anyone, signed in or not, reads the legal documents the platform has published: terms of service, privacy policy and the data-collection consent. Reading is public; accepting (UC112) is not.*

**Relationship:**
- **Association:** Guest – View legal document
- **Include:** None
- **Extend:** None *(UC112 dùng lại use case này qua «include»)*
- **Generalization:** None

**Normal flow:**
1. The Guest opens the legal section; System lists the documents in force with their kind, version and effective date.
2. The Guest selects a document.
3. System returns the body of the published version, rendered for reading in the browser.
4. The Guest may download the document file instead of reading it on screen.
5. System serves the file of that exact version.

**Exceptional flow:**
1. **Unknown kind:** In step 3, if the requested kind has no published version, System returns "not found" rather than an empty page.
2. **Older version requested:** In step 2, only the version in force is public; reading a superseded version is an administrator action (UC606).
3. **No file attached:** In step 5, if the version was published as body text with no uploaded file, System says so and keeps the on-screen rendering available.

---

### UC112 — Accept legal document

| **Use Case** | Accept legal document | **ID** | UC112 |
|---|---|---|---|
| **Main actor** | Authenticated User | **Priority** | Essential |
| **Trigger** | Authenticated User | **Type** | external |

**Brief description:** *The Authenticated User reads and accepts the legal documents in force — terms of service, privacy policy, and the data-collection consent that decides how far the samples they contribute may be released.*

**Relationship:**
- **Association:** Authenticated User – Accept legal document
- **Include:** UC111 View legal document
- **Extend:** None *(UC113 mở rộng use case này)*
- **Generalization:** None

**Normal flow:**
1. System displays the documents in force that the account has not yet accepted, with the effective date of each.
2. The user opens a document and reads its body, rendered from the stored version content.
3. For the data-collection consent, the user selects one of the three release levels offered.
4. The user ticks the acceptance box and clicks "Accept".
5. System records one consent row per document, storing the document version and its content hash, and writes an audit entry.
6. System lifts the consent block and returns the user to the page they were heading for.

**Exceptional flow:**
1. **New version published:** In step 1, when a new version of an accepted document is published, System asks again — a consent is bound to the exact version and hash it was given for.
2. **Refusal:** In step 4, if the user declines, System keeps the account read-only: no capture, no upload, no export.
3. **Anonymous sample:** In step 3, if the account never gave a release level, the samples it contributed cannot be published in any release; the consent scale is enforced at export time, not only at collection time.

---

### UC113 — Withdraw consent

| **Use Case** | Withdraw consent | **ID** | UC113 |
|---|---|---|---|
| **Main actor** | Deaf Signer | **Priority** | Essential |
| **Trigger** | Deaf Signer | **Type** | external |

**Brief description:** *The Deaf Signer withdraws a consent previously given. Withdrawal is real: from that moment the samples covered by it are excluded from every new release.*

**Relationship:**
- **Association:** Deaf Signer – Withdraw consent
- **Include:** None
- **Extend:** UC112 Accept legal document
- **Generalization:** None

**Normal flow:**
1. The Signer opens the Account page and reads the consent history: which document, which version, when accepted.
2. The Signer clicks "Withdraw" on a consent and reads the consequence displayed.
3. The Signer confirms.
4. System stamps the withdrawal time on the consent row, keeping the original acceptance as history.
5. System excludes the samples covered by that consent from every subsequent export and release build.
6. System writes an audit entry and notifies the tenant administrators.

**Exceptional flow:**
1. **Mandatory document:** In step 3, if the withdrawn document is one whose acceptance is required to use the platform, System warns that the account becomes read-only and asks for a second confirmation.
2. **Already published release:** In step 5, System states plainly that releases already built and distributed cannot be recalled; the withdrawal applies to future releases.
3. **Re-consent:** After a withdrawal, the Signer may accept the same document again (UC112); this creates a new consent row and does not erase the withdrawal.

---

### UC114 — Use trial recognition

| **Use Case** | Use trial recognition | **ID** | UC114 |
|---|---|---|---|
| **Main actor** | Guest | **Priority** | Optional |
| **Trigger** | Guest | **Type** | external |

**Brief description:** *The Guest tries realtime sign recognition without an account, within a daily time budget counted per browser and per IP.*

**Relationship:**
- **Association:** Guest – Use trial recognition; Inference Service (S3)
- **Include:** None
- **Extend:** UC407 Recognize sign in realtime
- **Generalization:** None

**Normal flow:**
1. The Guest opens the public recognition page and clicks "Try it".
2. System issues a trial ticket bound to the browser and starts counting the minutes used today.
3. System asks for camera permission and starts client-side hand tracking.
4. System streams the landmark windows to the Realtime Inference Service and displays the predicted label with its confidence.
5. System displays the remaining trial minutes for the day.
6. When the Guest stops, System stores the minutes consumed against the daily budget.

**Exceptional flow:**
1. **Budget exhausted:** In step 2, if today's budget is spent, System stops the trial and invites the Guest to create an account (UC101).
2. **Camera denied:** In step 3, if the browser refuses camera access, System explains how to grant it and offers the video-upload path instead.
3. **Inference service down:** In step 4, if the service does not answer, System displays a service-unavailable notice and does not consume the trial budget.
4. **No hand detected:** In step 4, if no hand is visible, System displays a framing hint rather than a prediction.

---

## 9. Đặc tả chi tiết — Nghiệp vụ 2: Thu thập và quản lý dữ liệu mẫu

### UC201 — Record sample from camera

| **Use Case** | Record sample from camera | **ID** | UC201 |
|---|---|---|---|
| **Main actor** | Deaf Signer | **Priority** | Essential |
| **Trigger** | Deaf Signer | **Type** | external |

**Brief description:** *The Deaf Signer performs a sign in front of the camera. Hand landmarks are extracted in the browser and sent to the platform, where one capture becomes exactly one sample of the chosen class.*

**Relationship:**
- **Association:** Deaf Signer – Record sample from camera; Organization Member (vận hành buổi thu); External Storage (S2)
- **Include:** UC203 Process recording
- **Extend:** None
- **Generalization:** Capture sample (abstract)

**Normal flow:**
1. The Signer opens the capture page and chooses the class to record, the language and the dialect.
2. System asks for camera permission and starts client-side hand tracking, displaying the detected landmarks over the video.
3. System displays the recording guidance: framing, number of hands required by the class, and target duration.
4. The Signer clicks "Record"; System collects landmark frames with their timestamps until the Signer stops.
5. System displays the captured window for review and asks the Signer to keep or discard it.
6. The Signer clicks "Save".
7. System checks the sample quota of the tenant, counting this capture as exactly one sample.
8. System sends the frames and the metadata (class, session, dialect, signer) to the backend, which stores the sample and hands it to the Processing Worker (UC203).
9. System displays the new sample in the session list with its quality metrics.

**Exceptional flow:**
1. **Camera denied or missing:** In step 2, System explains how to grant camera access and offers the video-upload path (UC202).
2. **No hand detected:** In step 4, if no hand is visible for the whole window, System refuses to save and displays a framing hint.
3. **Two hands required:** In step 4, if the class requires two hands and only one is tracked, System warns before saving; the requirement is read from the class metadata, not guessed from the frames.
4. **Quota exceeded:** In step 7, System refuses the save and displays the plan limit reached, with the path to change the plan (UC506).
5. **Consent outstanding:** In step 6, if the account has no consent in force, System blocks the write and routes to the consent screen (UC112).
6. **Network failure:** In step 8, System keeps the captured window in the browser and offers a retry rather than discarding the recording.

---

### UC202 — Upload video file

| **Use Case** | Upload video file | **ID** | UC202 |
|---|---|---|---|
| **Main actor** | Organization Member | **Priority** | Essential |
| **Trigger** | Organization Member | **Type** | external |

**Brief description:** *The Member uploads one or more video files (MP4, MOV) of signs already recorded. The raw file is archived before any normalisation, then landmarks are extracted from it.*

**Relationship:**
- **Association:** Organization Member – Upload video file; External Storage (S2)
- **Include:** UC203 Process recording
- **Extend:** None
- **Generalization:** Capture sample (abstract)

**Normal flow:**
1. The Member opens the upload page, chooses the target class, the dialect and the signer.
2. The Member selects the video files and clicks "Upload".
3. System validates each file: extension, size and duration.
4. System checks the sample quota of the tenant against the number of files.
5. System writes each raw file to the raw archive **before** any normalisation, so the original is never lost to a processing bug.
6. System returns an upload receipt listing the accepted files.
7. The Member clicks "Process"; System enqueues one processing job per file (UC203) and returns the job identifiers.
8. The Member follows the job progress (UC204).

**Exceptional flow:**
1. **Unsupported format:** In step 3, the file is rejected with the list of accepted formats; the other files in the batch still proceed.
2. **File too large:** In step 3, System rejects the file and displays the size limit.
3. **Quota exceeded:** In step 4, System accepts only the files that fit inside the remaining quota and reports which ones were refused.
4. **Storage unavailable:** In step 5, System aborts the upload and reports a storage failure; nothing partially written is registered as a sample.
5. **No landmark found:** During step 7, if the worker finds no hand in the whole video, the job ends in failure with that reason and no sample is created.

---

### UC203 — Process recording

| **Use Case** | Process recording | **ID** | UC203 |
|---|---|---|---|
| **Main actor** | Background Processor (S4) | **Priority** | Essential |
| **Trigger** | A capture or an upload is enqueued | **Type** | internal |

**Brief description:** *The Processing Worker turns a raw recording into a training-ready sample: it extracts hand landmarks, cuts a fixed-length window, augments it, writes the feature file and registers the sample in the source of truth.*

**Relationship:**
- **Association:** Background Processor (S4) – Process recording; External Storage (S2)
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Worker takes the job from the queue and marks it running.
2. The Worker extracts hand landmarks frame by frame — 21 landmarks × 3 coordinates × 2 hands = 126 features per frame.
3. The Worker applies the sliding window of fixed length and normalises the coordinate space.
4. The Worker computes the quality metrics of the window, including completeness and jitter.
5. The Worker generates the augmented variants of the window.
6. The Worker writes the feature file and a sidecar description next to it, so the registry row can be rebuilt from the file alone.
7. The Worker appends the sample row to the source-of-truth registry and mirrors it into the database. The spreadsheet mirror is **not** written here: it is refreshed by its own scheduled task, so a sample is registered long before it appears in the spreadsheet.
8. The Worker hands the upload to the Object Storage off to a separate retrying task and records the returned storage key on the row when it completes.
9. The Worker marks the job finished and notifies the owner.

**Exceptional flow:**
1. **No hand detected:** In step 2, the Worker ends the job as failed with that reason; no sample row is created.
2. **Window too short:** In step 3, if the recording is shorter than the window, the Worker pads it and records that fact in the quality metrics rather than silently dropping the sample.
3. **Storage dispatch fails:** In step 8, the Worker retries; if every retry fails, the row keeps its local path and a reconciliation task fills the storage key later.
4. **Registry write fails:** In step 7, the Worker aborts and requeues; a sample present in the database but missing from the registry is treated as an inconsistency and repaired by the reconciliation task.
5. **Worker crash:** At any step, the job returns to the queue; the sample identifier is stable so a repeat run overwrites rather than duplicates.

---

### UC204 — Monitor job status

| **Use Case** | Monitor job status | **ID** | UC204 |
|---|---|---|---|
| **Main actor** | Organization Member | **Priority** | Important |
| **Trigger** | Organization Member | **Type** | external |

**Brief description:** *The Member follows the progress of the background jobs started by their uploads and captures.*

**Relationship:**
- **Association:** Organization Member – Monitor job status
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Member opens the job list; System displays the recent jobs with their state, progress and start time.
2. System refreshes the state of the running jobs at a fixed interval.
3. The Member opens a job to read its detail: source file, target class, number of samples produced.
4. When a job finishes, System displays the resulting samples and a link to the label detail (UC207).

**Exceptional flow:**
1. **Job failed:** In step 4, System displays the failure reason recorded by the Worker and offers to retry the source file.
2. **Job not found:** In step 3, if the identifier is unknown or belongs to another tenant, System returns "not found" — the same answer for both, so the endpoint cannot be used to probe other tenants.
3. **Queue congested:** In step 1, System displays the queue position rather than an empty progress bar.

---

### UC205 — Set capture preferences

| **Use Case** | Set capture preferences | **ID** | UC205 |
|---|---|---|---|
| **Main actor** | Organization Member | **Priority** | Optional |
| **Trigger** | Organization Member | **Type** | external |

**Brief description:** *The Member stores the language and dialect they normally record in, so that the capture screens stop asking the same two questions at every session.*

**Relationship:**
- **Association:** Organization Member – Set capture preferences
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Member opens the capture screen; System reads the stored preference and pre-selects the language and the dialect.
2. The Member changes the selection.
3. The Member saves it as their default.
4. System stores the preference against the account.
5. System applies it to the capture, upload and catalog screens from then on.

**Exceptional flow:**
1. **No preference yet:** In step 1, System falls back to the organisation's default rather than to a blank selection.
2. **Dialect no longer approved:** In step 1, if the stored dialect was rejected or removed meanwhile, System drops back to the language default and says why.
3. **Preference is not a permission:** In step 5, the preference only decides what is pre-selected; it never widens what the account is allowed to write.

---

### UC206 — Browse label catalog

| **Use Case** | Browse label catalog | **ID** | UC206 |
|---|---|---|---|
| **Main actor** | Organization Member | **Priority** | Essential |
| **Trigger** | Organization Member | **Type** | external |

**Brief description:** *The Member browses the classes of the vocabulary catalog, filtered by language and dialect, to choose what to record next.*

**Relationship:**
- **Association:** Organization Member – Browse label catalog
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Member opens the Labels page.
2. System displays the classes visible to the tenant with, for each, the sample count and the collection progress.
3. The Member filters by language, by dialect or by free-text search.
4. System returns the matching classes and suggests the labels that are furthest from the collection target.
5. The Member selects a class and opens its detail (UC207) or starts a capture on it (UC201).

**Exceptional flow:**
1. **Empty catalog:** In step 2, if the tenant has no class yet, System explains how to register the first one (UC301).
2. **No match:** In step 4, System reports no result and offers to clear the filters.
3. **Cross-tenant class:** In step 2, classes belonging to other tenants are not listed; the community layer is shown separately and read-only.

---

### UC207 — View label detail

| **Use Case** | View label detail | **ID** | UC207 |
|---|---|---|---|
| **Main actor** | Organization Member | **Priority** | Essential |
| **Trigger** | Organization Member | **Type** | external |

**Brief description:** *The Member opens one class and inspects the capture sessions and the samples recorded for it, with the quality metrics of each.*

**Relationship:**
- **Association:** Organization Member – View label detail
- **Include:** None
- **Extend:** None *(UC208 và UC210 mở rộng use case này)*
- **Generalization:** None

**Normal flow:**
1. The Member opens a class from the catalog.
2. System displays the class metadata: name, language, dialect, number of hands required, collection target.
3. System lists the capture sessions of the class with the signer, the date, the sample count and the ownership marker.
4. The Member opens a session; System displays its samples and, for each, the completeness and the jitter.
5. The Member may preview the session (UC208), delete it (UC209) or delete a single sample (UC211).

**Exceptional flow:**
1. **Not the owner:** In step 5, a Contributor who does not own the session sees it read-only; only the owner and an editor can delete or reassign it.
2. **Sample file missing:** In step 4, if the feature file cannot be read, System displays the row with a "file unavailable" marker instead of failing the whole page.
3. **Deleted session:** In step 3, sessions already soft-deleted are hidden from this list and appear in the Trash (UC212).

---

### UC208 — Preview session video

| **Use Case** | Preview session video | **ID** | UC208 |
|---|---|---|---|
| **Main actor** | Organization Member | **Priority** | Important |
| **Trigger** | Organization Member | **Type** | external |

**Brief description:** *The Member plays back a rendered preview of a capture session in order to judge whether the recording is usable.*

**Relationship:**
- **Association:** Organization Member – Preview session video
- **Include:** None
- **Extend:** UC207 View label detail
- **Generalization:** None

**Normal flow:**
1. The Member clicks "Preview" on a session.
2. System reports whether a preview has already been rendered for that session.
3. If none exists, System enqueues the rendering job and displays its progress.
4. The Worker renders the landmark sequence into a video and stores it beside the session.
5. System streams the preview and the Member plays it.

**Exceptional flow:**
1. **Rendering failed:** In step 4, System displays the failure and offers to render again; the samples themselves are untouched.
2. **Preview expired:** In step 2, if the stored preview is older than its retention, System renders a new one.
3. **Overlapping hands:** In step 5, the preview draws both hands with distinct colours; a recording where the hands overlap is flagged rather than silently rendered as one.

---

### UC209 — Delete capture session

| **Use Case** | Delete capture session | **ID** | UC209 |
|---|---|---|---|
| **Main actor** | Organization Member | **Priority** | Important |
| **Trigger** | Organization Member | **Type** | external |

**Brief description:** *The Member removes a whole capture session that turned out to be unusable. The deletion is soft: the samples leave the working set but the files stay until the Trash is purged.*

**Relationship:**
- **Association:** Organization Member – Delete capture session
- **Include:** None
- **Extend:** None
- **Generalization:** Remove data (abstract)

**Normal flow:**
1. The Member opens a session and clicks "Delete session".
2. System displays how many samples the session contains and warns that they leave the working set.
3. The Member confirms.
4. System checks that the caller owns the session or is an editor of the tenant.
5. System marks every sample of the session deleted, stamping the deletion time and the actor.
6. System moves the session to the Trash and writes an audit entry.
7. System returns to the label detail with the session removed from the list.

**Exceptional flow:**
1. **Not the owner:** In step 4, System refuses; a Contributor cannot delete a session recorded by somebody else.
2. **Session already deleted:** In step 5, System reports success without changing anything, so a repeated click is harmless.
3. **Restore:** After step 6, the session can be restored from the Trash (UC212) as long as it has not been purged — this is why the files are kept.

---

### UC210 — Reassign session signer

| **Use Case** | Reassign session signer | **ID** | UC210 |
|---|---|---|---|
| **Main actor** | Editor / Researcher | **Priority** | Optional |
| **Trigger** | Editor / Researcher | **Type** | external |

**Brief description:** *The Editor corrects the signer attached to a capture session when the recording was registered under the wrong person.*

**Relationship:**
- **Association:** Editor / Researcher – Reassign session signer
- **Include:** None
- **Extend:** UC207 View label detail
- **Generalization:** None

**Normal flow:**
1. The Editor opens a session and clicks "Reassign".
2. System displays the current signer and a search field over the collectors of the tenant.
3. The Editor selects the correct signer and confirms.
4. System checks that the Editor has the editor role on the tenant that owns the session.
5. System rewrites the signer on every sample of the session, in the registry and in the database together.
6. System writes an audit entry recording both the previous and the new signer.
7. System displays the session with the corrected signer.

**Exceptional flow:**
1. **Insufficient role:** In step 4, System refuses; reassignment changes provenance, so it is not a contributor-level action.
2. **Partial write:** In step 5, if the registry and the database disagree afterwards, the reconciliation task rebuilds the registry from the database rather than leaving two versions of the truth.
3. **Consent difference:** In step 5, if the new signer has a narrower consent level, System applies the narrower level to the samples from that moment on.

---

### UC211 — Delete sample

| **Use Case** | Delete sample | **ID** | UC211 |
|---|---|---|---|
| **Main actor** | Organization Member | **Priority** | Essential |
| **Trigger** | Organization Member | **Type** | external |

**Brief description:** *The Member removes a single sample from the working set. As with sessions, the deletion is soft and reversible until the Trash is purged.*

**Relationship:**
- **Association:** Organization Member – Delete sample
- **Include:** None
- **Extend:** None *(UC212 mở rộng use case này)*
- **Generalization:** Remove data (abstract)

**Normal flow:**
1. The Member opens the sample list of a session and clicks "Delete" on one sample.
2. System asks for confirmation.
3. The Member confirms.
4. System checks that the caller owns the sample or is an editor of the tenant.
5. System stamps the deletion time and the actor on the sample row, in the registry and in the database.
6. System removes the sample from the counts displayed for the class and writes an audit entry.

**Exceptional flow:**
1. **Not the owner:** In step 4, System refuses.
2. **Sample already deleted:** In step 5, System reports success without a second write.
3. **Last sample of a class:** In step 6, System keeps the class in the catalog with a zero count; a class is a catalog entry, not a by-product of its samples.

---

### UC212 — Manage trash

| **Use Case** | Manage trash | **ID** | UC212 |
|---|---|---|---|
| **Main actor** | Organization Member | **Priority** | Important |
| **Trigger** | Organization Member | **Type** | external |

**Brief description:** *The Member reviews what they have deleted and either restores it to the working set or purges it permanently. Purging is the only step that touches the stored files.*

**Relationship:**
- **Association:** Organization Member – Manage trash; External Storage (S2)
- **Include:** None
- **Extend:** UC211 Delete sample, UC304 Remove class
- **Generalization:** None

**Normal flow:**
1. The Member opens the Trash page; System lists the samples and classes deleted by that account, with the deletion date.
2. The Member selects one or more entries.
3. The Member clicks "Restore".
4. System clears the deletion stamp and returns the entries to the working set, in the registry and in the database.
5. System refreshes the class counts.

**Exceptional flow:**
1. **Purge instead of restore:** In step 3, the Member clicks "Purge permanently"; System warns that the action cannot be undone, asks for confirmation, then deletes the registry row and the database row, and **dispatches** the file deletion to a retrying background task.
2. **Storage delete fails:** In the purge branch, the rows are already gone when the deletion is attempted, so a permanent failure leaves an **orphan file**, not a half-deleted sample. The task retries; what it cannot delete is found again by the reconciliation report (UC703), which is where orphan files are meant to surface. Note the deletion must address the file by its own reference — a folder-only resolution silently deletes nothing, which is exactly how sample purges once left every file behind.
3. **Scope:** In step 1, a Contributor sees only their own deletions; a Platform Administrator sees the whole tenant.
4. **Restore into a purged class:** In step 4, if the parent class has been purged meanwhile, System refuses the restore and explains that the class must be restored first.

---

### UC213 — Export dataset snapshot

| **Use Case** | Export dataset snapshot | **ID** | UC213 |
|---|---|---|---|
| **Main actor** | Editor / Researcher | **Priority** | Important |
| **Trigger** | Editor / Researcher runs the export tool | **Type** | external |

**Brief description:** *The Editor produces a training-ready snapshot of the dataset from the registry, using the command-line export tool on the deployment host. Only samples whose signer consent allows the requested release level are included.*

> **Ranh giới hiện thực:** use case này chạy bằng **công cụ dòng lệnh trên máy triển
> khai**, không phải bằng một màn hình. Bộ định tuyến HTTP `dataset_exporter`
> (`POST /api/dataset/export`) vẫn nằm trong cây mã nhưng **không được gắn vào ứng
> dụng** — `main.py` cố ý không import nó, nên không URL nào chạm tới. Đặc tả một
> nút bấm ở đây là mô tả thứ không tồn tại. Đường xuất **dữ liệu của một tổ chức**
> qua giao diện là UC507, một use case khác.

**Relationship:**
- **Association:** Editor / Researcher – Export dataset snapshot
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Editor runs the export tool on the deployment host, giving the language, the dialects and the release level.
2. System reads the registry and reports how many samples qualify and how many are excluded by consent.
3. The Editor confirms the run.
4. System checks each row against its signer consent and its deletion state.
5. System assembles the feature matrices and the label index, and writes the snapshot manifest that records the exact rows included.
6. System reports the summary: sample count, class count, excluded rows and the manifest identifier.

**Exceptional flow:**
1. **Shape mismatch:** In step 5, if a feature file does not have the expected window length, System reports it; with the auto-fix option on, it pads or truncates the row and records the correction in the manifest.
2. **Consent withdrawn:** In step 4, samples whose consent was withdrawn are excluded even if they were included in a previous snapshot (UC113).
3. **Anonymous samples:** In step 4, samples with no recorded consent level are excluded from every release level.
4. **File stored remotely:** In step 5, rows whose feature file lives in object storage are materialised into a local cache first, so the export reads one code path for local and remote rows alike.
5. **Empty result:** In step 6, if nothing qualifies, System reports an empty snapshot rather than writing an unusable archive.

---

## 10. Đặc tả chi tiết — Nghiệp vụ 3: Danh mục từ vựng và phương ngữ

### UC301 — Register class

| **Use Case** | Register class | **ID** | UC301 |
|---|---|---|---|
| **Main actor** | Editor / Researcher | **Priority** | Essential |
| **Trigger** | Editor / Researcher | **Type** | external |

**Brief description:** *The Editor adds a new sign class to the vocabulary catalog of the organisation, with its language, dialect and capture requirements.*

**Relationship:**
- **Association:** Editor / Researcher – Register class
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Editor opens the vocabulary page and clicks "New class".
2. The Editor enters the label text, the language, the dialect, the number of hands required and the collection target.
3. The Editor clicks "Register".
4. System checks that the caller is an editor or an admin of their **home** tenant — the role is read on the caller's own tenant, never on a tenant named in the request.
5. System checks the catalog rate limit and the class quota of the plan.
6. System checks that no active class of the same label, language and dialect already exists.
7. System assigns a stable class identifier and a class index, stores the class and writes an audit entry.
8. System displays the new class in the catalog, ready for capture.

**Exceptional flow:**
1. **Insufficient role:** In step 4, System refuses. A contributor cannot write into the catalog of the whole organisation.
2. **Duplicate class:** In step 6, System refuses and points at the existing class; a label is unique per language and dialect.
3. **Quota reached:** In step 5, System refuses and displays the class limit of the current plan.
4. **Unapproved dialect:** In step 2, if the chosen dialect is still pending moderation, System accepts the class but marks it not trainable until the dialect is approved (UC307).
5. **Rate limit:** In step 5, System refuses a burst of catalog writes and asks the Editor to retry shortly.

---

### UC302 — Update class

| **Use Case** | Update class | **ID** | UC302 |
|---|---|---|---|
| **Main actor** | Editor / Researcher | **Priority** | Important |
| **Trigger** | Editor / Researcher | **Type** | external |

**Brief description:** *The Editor corrects the metadata of an existing class: its label text, its capture requirements or its collection target.*

**Relationship:**
- **Association:** Editor / Researcher – Update class
- **Include:** None
- **Extend:** None *(UC303 mở rộng use case này)*
- **Generalization:** None

**Normal flow:**
1. The Editor opens a class and clicks "Edit".
2. System displays the current metadata and how many samples already exist for the class.
3. The Editor changes the fields and confirms.
4. System checks the editor role and the catalog rate limit.
5. System validates that the new label does not collide with another active class of the same language and dialect.
6. System stores the change, keeping the class identifier and the class index stable, and writes an audit entry.
7. System displays the updated class.

**Exceptional flow:**
1. **Collision:** In step 5, System refuses and names the colliding class.
2. **Class index:** In step 6, the class index is **never** reassigned by an edit; models already trained refer to it by position, so changing it would silently mislabel every existing prediction.
3. **Requirement change with existing samples:** In step 3, if the number of hands required changes while samples exist, System warns that the existing samples were validated against the old requirement.
4. **Merge instead:** In step 3, if the Editor is trying to fold one class into another, System offers the merge operation rather than a rename.

---

### UC303 — Merge classes

| **Use Case** | Merge classes | **ID** | UC303 |
|---|---|---|---|
| **Main actor** | Editor / Researcher | **Priority** | Important |
| **Trigger** | Editor / Researcher | **Type** | external |

**Brief description:** *The Editor folds one class into another when the catalog turns out to hold two entries for the same sign. The samples of the source class move to the destination class instead of being lost.*

**Relationship:**
- **Association:** Editor / Researcher – Merge classes
- **Include:** None
- **Extend:** UC302 Update class
- **Generalization:** None

**Normal flow:**
1. The Editor opens a class and chooses "Merge into another class".
2. The Editor picks the destination class.
3. System displays how many samples will move and warns that the source class disappears from the catalog.
4. The Editor confirms.
5. System moves every sample of the source class to the destination class, in the registry and in the database together.
6. System retires the source class and writes an audit entry naming both classes.
7. System displays the destination class with the combined sample count.

**Exceptional flow:**
1. **Different language or dialect:** In step 4, System refuses to merge across languages or dialects; two entries that differ there are not duplicates.
2. **Class index:** In step 6, the destination keeps its own class index and the source index is retired, never reused — a reused index would silently relabel every model trained before the merge.
3. **Merge into itself:** In step 2, System refuses.
4. **Conflicting capture requirements:** In step 3, if the two classes disagree on the number of hands required, System states which requirement the merged samples will be judged against.

---

### UC304 — Remove class

| **Use Case** | Remove class | **ID** | UC304 |
|---|---|---|---|
| **Main actor** | Editor / Researcher | **Priority** | Important |
| **Trigger** | Editor / Researcher | **Type** | external |

**Brief description:** *The Editor removes a class from the catalog. The removal is soft first; a purge, which also deletes the samples and their files, is a separate and irreversible step.*

**Relationship:**
- **Association:** Editor / Researcher – Remove class; External Storage (S2)
- **Include:** None
- **Extend:** None *(UC212 mở rộng use case này)*
- **Generalization:** Remove data (abstract)

**Normal flow:**
1. The Editor opens a class and clicks "Delete".
2. System displays how many samples the class holds and warns that they leave the working set with it.
3. The Editor confirms.
4. System checks the editor role and the catalog rate limit.
5. System stamps the deletion on the class and on its samples, and moves them to the Trash.
6. System writes an audit entry and refreshes the catalog.

**Exceptional flow:**
1. **Restore:** From the Trash, the Editor restores the class; System clears the deletion stamp on the class and on the samples that were deleted together with it.
2. **Purge:** From the Trash, the Editor purges the class; System asks for an explicit confirmation, then deletes the class row, its sample rows and the stored feature files.
3. **Class used by a model:** In step 4, if a promoted model refers to the class, System warns that the model's label index will no longer resolve.
4. **Storage delete fails:** In the purge branch, the file deletion is dispatched as a retrying background task after the rows are gone; a permanent failure therefore leaves an orphan file, which the reconciliation report lists (UC703).

---

### UC305 — View collection statistics

| **Use Case** | View collection statistics | **ID** | UC305 |
|---|---|---|---|
| **Main actor** | Organization Member | **Priority** | Important |
| **Trigger** | Organization Member | **Type** | external |

**Brief description:** *The Member reads how far the collection has progressed: samples per class, class balance, contributions per signer, and what to record next to close the gaps.*

**Relationship:**
- **Association:** Organization Member – View collection statistics
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Member opens the dashboard.
2. System displays the totals of the tenant: classes, samples, signers, and the share of classes that reached the target.
3. System displays the per-class distribution, sorted by distance from the target.
4. The Member sets a target sample count; System computes the balance plan — how many samples each class still needs.
5. The Member opens a class from the plan and starts a capture on it (UC201).

**Exceptional flow:**
1. **No data yet:** In step 2, System displays an empty state with the first steps: register a class, then record a sample.
2. **Community layer:** In step 2, System separates the counts of the tenant from the community counts; the two are never added together.
3. **Stale mirror:** In step 3, if the database mirror is behind the registry, System displays the registry counts, which are the source of truth.

---

### UC306 — Propose dialect

| **Use Case** | Propose dialect | **ID** | UC306 |
|---|---|---|---|
| **Main actor** | Editor / Researcher | **Priority** | Optional |
| **Trigger** | Editor / Researcher | **Type** | external |

**Brief description:** *The Editor proposes a new regional dialect for the vocabulary registry. The proposal is usable inside the organisation but must be moderated before it becomes part of the shared registry.*

**Relationship:**
- **Association:** Editor / Researcher – Propose dialect
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Editor opens the vocabulary registry and clicks "Propose dialect".
2. The Editor enters the dialect code, its display name, the language it belongs to and a justification.
3. The Editor submits the proposal.
4. System checks the editor role and that the code is not already taken.
5. System stores the dialect with the state "pending" and notifies the platform administrators.
6. System displays the dialect in the registry marked as pending.

**Exceptional flow:**
1. **Code taken:** In step 4, System refuses and displays the existing dialect with that code.
2. **Insufficient role:** In step 4, System refuses; a contributor cannot write into the registry.
3. **Rejected later:** If the proposal is rejected (UC307), the classes created under it stay but remain not trainable until another dialect is chosen.

---

### UC307 — Moderate dialect proposal

| **Use Case** | Moderate dialect proposal | **ID** | UC307 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Optional |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *The Platform Administrator reviews the dialects proposed by the organisations and approves or rejects them for the shared registry.*

**Relationship:**
- **Association:** Platform Administrator – Moderate dialect proposal
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Administrator opens the pending dialect list.
2. System displays each proposal with its code, name, language, proposer and justification.
3. The Administrator opens one proposal and reviews it.
4. The Administrator clicks "Approve".
5. System marks the dialect approved, publishes it into the shared registry and writes an audit entry.
6. System notifies the proposing organisation and unblocks the classes waiting on that dialect.

**Exceptional flow:**
1. **Rejection:** In step 4, the Administrator clicks "Reject" and must enter a reason. System stores the rejection with the reason and notifies the proposer.
2. **Duplicate of an approved dialect:** In step 3, System displays the near-matching approved dialects so the Administrator can redirect the proposer instead of splitting the registry.
3. **Already moderated:** In step 5, if another administrator moderated the proposal meanwhile, System reports the current state and makes no second write.

---

### UC308 — Maintain community catalog template

| **Use Case** | Maintain community catalog template | **ID** | UC308 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Important |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *The Platform Administrator edits the community template — the shared dialects and capture profiles that every organisation starts from. The template is the live, editable plane; it is not what organisations consume until it is frozen into a version (UC309).*

**Relationship:**
- **Association:** Platform Administrator – Maintain community catalog template
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Administrator opens the community catalog; System displays the live dialects and profiles, the content hash of the live template, and the last published version with its own hash.
2. The Administrator compares the two hashes to see whether the template has been edited since the last publication.
3. The Administrator edits a dialect or a capture profile.
4. System validates the change and stores it on the live template, recording who changed it.
5. System recomputes the content hash so the difference against the published version stays visible.

**Exceptional flow:**
1. **Unknown dialect or profile:** In step 4, System returns "not found" for an identifier that is not in the template.
2. **Invalid value:** In step 4, System refuses and leaves the template untouched.
3. **Refill from the seed files:** The Administrator may re-run the first-install seed. It only inserts what is missing — rows an administrator has since edited are left alone. There is deliberately **no** endpoint that overwrites administrator edits from the seed files, so this is a gap-filler, not a reset.
4. **Not a tenant action:** In step 3, only platform administrators reach this plane; an organisation edits its **own** registry, never the shared template.

---

### UC309 — Publish community catalog version

| **Use Case** | Publish community catalog version | **ID** | UC309 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Important |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *The Platform Administrator freezes the live template into an immutable, numbered version. Versions are what organisations and trained artefacts refer to, so freezing is what makes a catalog state citable.*

**Relationship:**
- **Association:** Platform Administrator – Publish community catalog version
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Administrator opens the catalog and reads the version history: version number, content hash, author and note.
2. The Administrator writes a note describing what changed.
3. The Administrator publishes.
4. System computes the content hash of the live template and compares it with the last published version.
5. System mints a new immutable version holding that content and reports the version number.
6. System reports whether a new version was actually created.

**Exceptional flow:**
1. **Nothing changed:** In step 5, publishing an unchanged template mints **no** duplicate: System returns the version that already holds that content and reports that nothing was created, so the screen can say "v7 already holds this" instead of a misleading success.
2. **Version is immutable:** After step 5, the content of a published version is never edited; a correction is a new version.
3. **Unknown version requested:** In step 1, reading a version number that does not exist returns "not found".

---

### UC310 — Clone catalog into an organisation

| **Use Case** | Clone catalog into an organisation | **ID** | UC310 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Important |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *The Platform Administrator bootstraps a new organisation's registry from the community template, so that the organisation starts with usable dialects and capture profiles instead of an empty catalog.*

**Relationship:**
- **Association:** Platform Administrator – Clone catalog into an organisation
- **Include:** None
- **Extend:** UC501 Manage tenants
- **Generalization:** None

**Normal flow:**
1. The Administrator selects the organisation to bootstrap.
2. System displays what the template currently contains.
3. The Administrator confirms the clone.
4. System copies the template rows into the organisation's registry, inserting only what is not already there.
5. System reports how many dialects and profiles were created.

**Exceptional flow:**
1. **Run twice:** In step 4, a second run is harmless but fills gaps only. It is **not a repair tool**: an organisation that has diverged from the template keeps its own rows, and the template does not overwrite them.
2. **Unknown organisation:** In step 4, the registry rows carry no foreign key to the organisation table, so cloning to an identifier that does not exist would create rows nobody can reach — System validates the identifier itself before writing.
3. **Missing identifier:** In step 3, System refuses without an organisation identifier.

---

## 11. Đặc tả chi tiết — Nghiệp vụ 4: Huấn luyện, đánh giá và suy luận

### UC401 — Start training job

| **Use Case** | Start training job | **ID** | UC401 |
|---|---|---|---|
| **Main actor** | Editor / Researcher | **Priority** | Essential |
| **Trigger** | Editor / Researcher | **Type** | external |

**Brief description:** *The Editor configures and enqueues a training run over the collected dataset. Three quotas are checked before anything else, because the training queue runs one job at a time and serves every organisation in arrival order.*

**Relationship:**
- **Association:** Editor / Researcher – Start training job
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Editor opens the training pipeline page.
2. System displays the dataset information: eligible classes, sample counts and the splits available.
3. The Editor chooses the dialect, the split strategy and the hyper-parameters, then clicks "Start training".
4. System checks the three quotas in order: waiting jobs, running jobs, and runs used this month.
5. System validates the configuration: enough classes, enough samples per class, and a split that leaves a non-empty validation set.
6. System creates the job, records the exact dataset manifest it will train on, and puts it in the training queue.
7. System returns the job identifier and displays the queue position.
8. The Worker picks the job up and the Editor follows the metrics (UC402).

**Exceptional flow:**
1. **Quota reached:** In step 4, System refuses and names which of the three limits was hit; the waiting-jobs cap is what actually stops one organisation from monopolising the single training slot.
2. **Not enough data:** In step 5, System refuses and reports which classes fall below the minimum sample count.
3. **Signer-disjoint split impossible:** In step 5, if a signer-disjoint split is requested but the samples come from too few signers, System refuses rather than silently falling back to a random split, which would inflate the reported accuracy.
4. **No GPU available:** In step 8, if the host exposes no GPU, the job runs on CPU and System states this in the job detail, since the run time changes by an order of magnitude.
5. **Consent-filtered dataset:** In step 6, the manifest excludes samples whose consent does not allow training use; the excluded count is recorded with the job.

---

### UC402 — Monitor training progress

| **Use Case** | Monitor training progress | **ID** | UC402 |
|---|---|---|---|
| **Main actor** | Editor / Researcher | **Priority** | Essential |
| **Trigger** | Editor / Researcher | **Type** | external |

**Brief description:** *The Editor follows a running training job: epoch progress, loss and accuracy curves, and the position of the job in the queue.*

**Relationship:**
- **Association:** Editor / Researcher – Monitor training progress
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Editor opens the job list and selects a job.
2. System displays the job state, the elapsed time and the configuration it was started with.
3. System displays the metrics logged so far, one point per epoch: training loss, validation loss and validation accuracy.
4. System refreshes the metrics while the job runs.
5. When the job finishes, System displays the final metrics and links to the evaluation (UC404).

**Exceptional flow:**
1. **Job still queued:** In step 2, System displays the queue position and the state of the queue instead of empty curves.
2. **Job failed:** In step 5, System displays the failure and the last logged epoch, so a run that died at epoch 40 is not confused with one that never started.
3. **Metrics gap:** In step 3, if the worker stopped logging while the job is still marked running, System flags the job as possibly stalled rather than showing a frozen curve as normal.

---

### UC403 — Cancel training job

| **Use Case** | Cancel training job | **ID** | UC403 |
|---|---|---|---|
| **Main actor** | Editor / Researcher | **Priority** | Important |
| **Trigger** | Editor / Researcher | **Type** | external |

**Brief description:** *The Editor stops a training job that is queued or running, freeing the single training slot for the next organisation in line.*

**Relationship:**
- **Association:** Editor / Researcher – Cancel training job
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Editor opens a job and clicks "Cancel".
2. System asks for confirmation, warning that the partial run is not recoverable.
3. The Editor confirms.
4. System checks that the caller owns the job or is an editor of the owning tenant.
5. System signals the worker to stop, marks the job cancelled and releases the queue slot.
6. System writes an audit entry and refreshes the job list.

**Exceptional flow:**
1. **Job already finished:** In step 5, System reports the final state and cancels nothing.
2. **Worker unresponsive:** In step 5, if the worker does not acknowledge, System marks the job cancelled and lets the janitor reclaim the slot, so a dead worker cannot block the queue indefinitely.
3. **Delete instead:** After cancellation, the Editor may delete the job record; the metrics and the manifest go with it, so System asks a second time.

---

### UC404 — Review evaluation and provenance

| **Use Case** | Review evaluation and provenance | **ID** | UC404 |
|---|---|---|---|
| **Main actor** | Editor / Researcher | **Priority** | Important |
| **Trigger** | Editor / Researcher | **Type** | external |

**Brief description:** *The Editor reads the evaluation of a finished run — per-class accuracy, confusion between classes — together with the provenance record that says exactly which samples, which split and which code version produced it.*

**Relationship:**
- **Association:** Editor / Researcher – Review evaluation and provenance
- **Include:** None
- **Extend:** None *(UC405 mở rộng use case này)*
- **Generalization:** None

**Normal flow:**
1. The Editor opens a finished job and selects "Evaluation".
2. System displays the overall accuracy, the per-class accuracy and the confusion matrix on the held-out set.
3. The Editor selects "Provenance".
4. System displays the dataset manifest identifier, the split strategy, the number of signers on each side of the split, the excluded-by-consent count and the code version.
5. The Editor uses the provenance record to decide whether the result is comparable with a previous run.

**Exceptional flow:**
1. **No evaluation:** In step 2, if the run failed before evaluation, System says so instead of displaying an empty matrix.
2. **Split not signer-disjoint:** In step 4, System marks the result explicitly as not signer-disjoint; comparing it against a signer-disjoint run is a mistake the provenance record exists to prevent.
3. **Manifest missing:** In step 4, for legacy jobs recorded before manifests existed, System displays "provenance unavailable" rather than reconstructing a plausible one.

---

### UC405 — Test trained model

| **Use Case** | Test trained model | **ID** | UC405 |
|---|---|---|---|
| **Main actor** | Editor / Researcher | **Priority** | Important |
| **Trigger** | Editor / Researcher | **Type** | external |

**Brief description:** *The Editor runs a sample through the model produced by a finished training job, before deciding whether it deserves to be promoted. The job's own checkpoint answers, not the model currently serving realtime recognition.*

**Relationship:**
- **Association:** Editor / Researcher – Test trained model
- **Include:** None
- **Extend:** UC404 Review evaluation and provenance
- **Generalization:** None

**Normal flow:**
1. The Editor opens a finished job and selects "Try this model".
2. The Editor supplies a landmark window, either recorded on the spot or picked from existing samples.
3. System checks the prediction quota.
4. System loads the checkpoint of that job and runs the window through it.
5. System displays the predicted label, the confidence, and the label index the model actually used.
6. The Editor compares the answer with the expected label and decides whether to promote (UC406).

**Exceptional flow:**
1. **Job not finished:** In step 4, a job with no checkpoint cannot answer; System says the job produced no model.
2. **Quota exhausted:** In step 3, System refuses and displays the prediction limit of the plan.
3. **Shape mismatch:** In step 4, if the supplied window does not match the input the model was trained on, System reports the mismatch instead of returning a meaningless label.
4. **Label index drift:** In step 5, if the catalog changed after training, System shows the model's own label index; the class the index points at today may differ from the one it was trained on, and that is exactly what this screen exists to reveal.

---

### UC406 — Promote model version

| **Use Case** | Promote model version | **ID** | UC406 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Important |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *The Platform Administrator promotes the model produced by a training run to be the active model of a dialect, so that realtime recognition starts serving it.*

**Relationship:**
- **Association:** Platform Administrator – Promote model version; Inference Service (S3)
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Administrator opens a finished job and reviews its evaluation (UC404).
2. The Administrator clicks "Promote".
3. System displays the currently active model for that dialect and the metrics of both, side by side.
4. The Administrator confirms.
5. System registers a new immutable model version with its artefact, its metrics and its provenance.
6. System marks the new version active for the dialect and the previous one superseded.
7. System asks the Realtime Inference Service to load the new version and writes an audit entry.

**Exceptional flow:**
1. **Worse than the active model:** In step 3, System displays the regression clearly; promotion is still allowed but the confirmation names the metric that dropped.
2. **Artefact missing:** In step 5, if the model file cannot be read, System refuses; a registered version with no artefact would break every subsequent load.
3. **Inference service refuses the load:** In step 7, System keeps the previous version serving and reports the failure, rather than leaving the dialect with no model.
4. **Rollback:** The Administrator may promote an earlier version again; versions are immutable, so a rollback is a promotion, not an edit.

---

### UC407 — Recognize sign in realtime

| **Use Case** | Recognize sign in realtime | **ID** | UC407 |
|---|---|---|---|
| **Main actor** | Deaf Signer | **Priority** | Essential |
| **Trigger** | Deaf Signer | **Type** | external |

**Brief description:** *The user signs in front of the camera and the platform displays the recognised label continuously, using the model currently active for the chosen dialect.*

**Relationship:**
- **Association:** Deaf Signer – Recognize sign in realtime; Hearing User (người nhận kết quả); Inference Service (S3)
- **Include:** None
- **Extend:** None *(UC114 và UC408 mở rộng use case này)*
- **Generalization:** None

**Normal flow:**
1. The user opens the recognition page.
2. System lists the models available and their dialects; the user selects one.
3. System asks for camera permission and starts client-side hand tracking.
4. System buffers the landmark frames into a sliding window and sends each completed window to the Realtime Inference Service.
5. System displays the predicted label with its confidence, and keeps the recent predictions as a running transcript.
6. The user stops the session; System releases the camera.

**Exceptional flow:**
1. **No model for the dialect:** In step 2, System says the dialect has no active model and offers the dialects that do.
2. **Low confidence:** In step 5, if the confidence is below the display threshold, System shows nothing rather than a wrong guess.
3. **Inference service unavailable:** In step 4, System stops sending, displays a service notice and keeps the camera preview running.
4. **Prediction quota:** In step 4, if the plan's prediction quota is exhausted, System stops the stream and displays the limit.
5. **Frame rate too low:** In step 4, if the device cannot sustain the tracking rate, System warns that the predictions will be unreliable.
6. **Malformed or oversized window:** In step 4, System rejects a window that exceeds the body-size cap or whose shape and values do not validate, before it ever reaches the inference service. Transport validation belongs to the platform; normalisation and label decoding belong to the inference service, and the split is deliberate.
7. **Too many concurrent windows:** In step 4, System bounds how many windows are in flight at once and times out those the service does not answer, so one saturated client cannot exhaust the recognition path for everyone.

---

### UC408 — Speak recognized text

| **Use Case** | Speak recognized text | **ID** | UC408 |
|---|---|---|---|
| **Main actor** | Hearing User | **Priority** | Optional |
| **Trigger** | Hearing User | **Type** | external |

**Brief description:** *The user turns the recognised transcript into speech, so that a hearing interlocutor receives the message without reading the screen.*

**Relationship:**
- **Association:** Hearing User – Speak recognized text; Deaf Signer (người tạo câu); Inference Service (S3)
- **Include:** None
- **Extend:** UC407 Recognize sign in realtime
- **Generalization:** None

**Normal flow:**
1. The user enables speech output and picks a voice from the list offered.
2. System pre-warms the TTS Service for that voice.
3. As predictions accumulate, System groups them into an utterance.
4. System sends the utterance to the TTS Service and plays the returned audio.
5. System displays the spoken text alongside the transcript.

**Exceptional flow:**
1. **Voice unavailable:** In step 1, if the requested voice is not installed, System falls back to the default voice and says so.
2. **TTS service down:** In step 4, System keeps the transcript on screen and disables the speech toggle with an explanation.
3. **Repeated prediction:** In step 3, System does not re-speak a label that is still the same as the previous one; a stable prediction is one sign, not many.

---

### UC409 — Prepare research release

| **Use Case** | Prepare research release | **ID** | UC409 |
|---|---|---|---|
| **Main actor** | Editor / Researcher | **Priority** | Important |
| **Trigger** | Editor / Researcher runs the release chain | **Type** | external |

**Brief description:** *The Editor builds a citable research release: validate the samples, freeze a dataset manifest, derive the splits, and record every step. The chain stops at the first failure so a release is never half-built.*

**Relationship:**
- **Association:** Editor / Researcher – Prepare research release
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Editor runs the release chain on the deployment host, naming the campaign and the manifest version.
2. System validates the pilot samples of the campaign.
3. System audits the dataset for duplicate samples.
4. System creates the dataset manifest — never overwriting an existing version.
5. System validates the manifest, including the checksum of every file it lists.
6. System derives the sample-level split, then attempts the signer-disjoint split for each capture profile.
7. System aggregates the experiment results and writes a release log holding every command, its exit code and the resulting checksums.

**Exceptional flow:**
1. **A step fails:** At any step, the chain stops at the first failure; the steps after it do not run, so a release is either complete or absent.
2. **Not enough signer diversity:** In step 6, a failure of the signer-disjoint split is **reported, not fatal** — too few signers is a fact about the dataset, not a bug in the pipeline, and hiding it would be the actual error.
3. **Manifest version exists:** In step 4, System refuses to overwrite; a new release takes a new version.
4. **Training is not part of this:** After step 7, no model is trained. An official run must be launched explicitly with the research purpose, so nobody trains a paper model by accident.

---

## 12. Đặc tả chi tiết — Nghiệp vụ 5: Tổ chức và đăng ký dịch vụ

### UC501 — Manage tenants

| **Use Case** | Manage tenants | **ID** | UC501 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Essential |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *The Platform Administrator creates organisations, edits their attributes, assigns accounts to a home organisation and deletes organisations that are no longer used.*

**Relationship:**
- **Association:** Platform Administrator – Manage tenants
- **Include:** None
- **Extend:** None *(UC310 mở rộng use case này)*
- **Generalization:** None

**Normal flow:**
1. The Administrator opens the Tenants page; System lists the organisations with their member count, plan and state.
2. The Administrator clicks "New tenant" and enters the name, the slug and the initial plan.
3. System validates that the slug is free and creates the organisation with its own data boundary.
4. System displays the new organisation.
5. The Administrator assigns an existing account to the organisation as its home tenant and gives it the admin role.
6. System writes an audit entry for the creation and for the assignment.

**Exceptional flow:**
1. **Slug taken:** In step 3, System refuses and suggests a free slug.
2. **Delete an organisation:** From the list in step 1, the Administrator may delete an organisation. System refuses while it still holds samples: the data must be purged first (UC508), which is a separate and deliberate act.
3. **Assignment is platform-only:** In step 5, this action is not available to an Organization Admin. Attaching an account by identifier would let any organisation pull in any account on the platform; their way in is the invitation (UC502).
4. **Last administrator:** In step 5, System refuses to move the last administrator out of an organisation that still has members.

---

### UC502 — Invite member

| **Use Case** | Invite member | **ID** | UC502 |
|---|---|---|---|
| **Main actor** | Organization Admin | **Priority** | Essential |
| **Trigger** | Organization Admin | **Type** | external |

**Brief description:** *The Organization Admin invites a person to join the organisation by email, choosing the role the invitation grants. The invitation is the only way an organisation can gain a member, because it requires the invited person to act.*

**Relationship:**
- **Association:** Organization Admin – Invite member; Notification Gateway (S1)
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Admin opens the Organisation page and clicks "Invite".
2. The Admin enters the email address and selects the tenant-level role: **admin**, **editor**, or **none**.

   > **Đổi ở PDM v5 (12/08/2026):** vai `viewer` đã được gỡ. Trước đây cột vai
   > là `NOT NULL DEFAULT 'viewer'`, nên "chưa chọn vai" và "chỉ được xem" bị
   > ép thành cùng một giá trị. Giờ hai thứ đó tách ra: **none** nghĩa là chưa
   > có vai ở cấp tổ chức, và quyền đọc/ghi được cấp ở Workspace/Project.
   >
   > API TỪ CHỐI `"viewer"` bằng **422** thay vì im lặng dịch sang `none` — một
   > script hay bookmark cũ còn gửi giá trị đó sẽ lộ ra thay vì bị giấu.
3. The Admin sends the invitation.
4. System checks the admin role on that organisation and the member quota of the plan.
5. System creates an invitation with a single-use token and an expiry, and writes an audit entry.
6. System sends the invitation email through the Email Service.
7. System lists the invitation as pending, with its expiry.

**Exceptional flow:**
1. **Already a member:** In step 4, System refuses and points at the existing membership.
2. **Member quota reached:** In step 4, System refuses and displays the plan limit with the path to change it (UC506).
3. **Mail delivery fails:** In step 6, System keeps the invitation and offers to resend or to copy the link manually.
4. **Revoke:** From step 7, the Admin may revoke a pending invitation; System invalidates the token immediately.
5. **Invalid role:** In step 2, an unrecognised role value is refused; the role vocabulary is fixed.

---

### UC503 — Accept invitation

| **Use Case** | Accept invitation | **ID** | UC503 |
|---|---|---|---|
| **Main actor** | Guest | **Priority** | Essential |
| **Trigger** | Guest opens the invitation link | **Type** | external |

**Brief description:** *The invited person joins the organisation. An invitation is consumed at one single moment — the creation of the account — so accepting it and registering are the same act, and the token decides which organisation and which role the new account gets.*

> **Ranh giới hiện thực:** lời mời **chỉ** được tiêu thụ ở đường đăng ký
> (`consume_invitation` chỉ có một nơi gọi, trong `auth.register`). Người **đã có
> tài khoản** hiện **không có đường nào** tự nhận lời mời — đây là một khoảng
> trống thật của hệ thống, không phải chi tiết bị bỏ sót khi viết đặc tả. Xem
> nhánh ngoại lệ 1.

**Relationship:**
- **Association:** Guest – Accept invitation
- **Include:** UC102 Register by invitation
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The invited person opens the link; System inspects the token and displays the inviting organisation, the invited address and the offered role.
2. The person creates the account through the invitation form (UC102).
3. System validates the token once more, at the moment of creation: not expired, not revoked, not already accepted.
4. System creates the account, attaches it to the inviting organisation with the invited role, and stamps the invitation as accepted by that account.
5. System writes an audit entry and notifies the inviting administrators.
6. System signs the person in and lands them on the organisation dashboard.

**Exceptional flow:**
1. **The invited person already has an account:** In step 2, there is no self-service path. The person must either register a **new** account on the invited address, or ask a Platform Administrator to attach the existing account to the organisation (UC501). This is the gap named above, and it is the reason the invitation list can show a pending invitation that its recipient is unable to accept.
2. **Stale invitation:** In step 3, System refuses and asks the person to request a new one; the check runs before the account is created, so a stale token never leaves a real account stranded in the wrong organisation.
3. **Two people open the same link:** In step 4, the acceptance stamp is written only while it is still empty, so of two simultaneous acceptances exactly one wins and the loser is told the invitation was accepted by somebody else.
4. **Address mismatch:** In step 2, the invited address is fixed by the token; editing it in the form has no effect, since an invitation is bound to one address.

---

### UC504 — Manage member role

| **Use Case** | Manage member role | **ID** | UC504 |
|---|---|---|---|
| **Main actor** | Organization Admin | **Priority** | Important |
| **Trigger** | Organization Admin | **Type** | external |

**Brief description:** *The Organization Admin changes the role of a member inside the organisation, which changes what that member can write.*

**Relationship:**
- **Association:** Organization Admin – Manage member role
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Admin opens the member list of the organisation.
2. System displays each member with their role and their join date.
3. The Admin selects a member and picks the new role.
4. System checks the admin role of the caller on that organisation.
5. System stores the new role and writes an audit entry recording both the previous and the new role — a role change is a permission change, so the previous value is part of the evidence.
6. System displays the updated member list.

**Exceptional flow:**
1. **Last administrator:** In step 4, System refuses to demote the only administrator of the organisation.
2. **Self-demotion:** In step 3, if the Admin demotes themselves, System asks for an explicit confirmation, since the action cannot be undone by that account.
3. **Unknown role:** In step 3, an unrecognised role string is refused; the audit entry records the stored role, not the raw string sent by the caller.
4. **Member removed meanwhile:** In step 5, System reports that the membership no longer exists.

---

### UC505 — Remove member

| **Use Case** | Remove member | **ID** | UC505 |
|---|---|---|---|
| **Main actor** | Organization Admin | **Priority** | Important |
| **Trigger** | Organization Admin | **Type** | external |

**Brief description:** *The Organization Admin removes a member from the organisation. The person keeps their account; only the membership and the access it granted end.*

**Relationship:**
- **Association:** Organization Admin – Remove member
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Admin opens the member list and clicks "Remove" on a member.
2. System displays what the member contributed and states that their samples stay with the organisation.
3. The Admin confirms.
4. System checks the admin role and that the target is not the last administrator.
5. System ends the membership, revokes the member's sessions scoped to that organisation and writes an audit entry.
6. System notifies the removed member.

**Exceptional flow:**
1. **Last administrator:** In step 4, System refuses.
2. **Home organisation:** In step 5, if the removed organisation was the member's home, System requires a Platform Administrator to reassign a home organisation (UC501) before the account can write again.
3. **Contributions:** In step 2, the samples are not deleted with the membership; deleting them is a separate act with its own consent implications (UC113).

---

### UC506 — Manage subscription

| **Use Case** | Manage subscription | **ID** | UC506 |
|---|---|---|---|
| **Main actor** | Organization Admin | **Priority** | Important |
| **Trigger** | Organization Admin | **Type** | external |

**Brief description:** *The Organization Admin reads the organisation's subscription — plan, quotas, period end — and turns automatic renewal on or off.*

**Relationship:**
- **Association:** Organization Admin – Manage subscription; Notification Gateway (S1)
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Admin opens the Billing page.
2. System displays the current plan, the quotas it grants, the usage against each quota and the end of the current period.
3. System displays whether automatic renewal is on.
4. The Admin toggles automatic renewal and confirms.
5. System stores the setting and writes an audit entry.
6. System sends reminders as the period end approaches, through the Email Service.

**Exceptional flow:**
1. **Period expired:** In step 2, if the period ended without renewal, System displays the grace period remaining before the organisation becomes read-only.
2. **Past due:** In step 2, an organisation past due keeps writing until the grace period ends; this is deliberate, so that fieldwork already under way is not lost.
3. **Soft lock:** After the grace period, System blocks writes but keeps reads and exports available, so the organisation can always retrieve its own data.
4. **No payment collection:** In step 4, System does not take payment; the plan change is recorded and settled outside the platform.

---

### UC507 — Request tenant data export

| **Use Case** | Request tenant data export | **ID** | UC507 |
|---|---|---|---|
| **Main actor** | Organization Admin | **Priority** | Important |
| **Trigger** | Organization Admin | **Type** | external |

**Brief description:** *The Organization Admin asks for a complete export of the organisation's data — samples, catalog, members, audit trail — and downloads it when the archive is ready.*

**Relationship:**
- **Association:** Organization Admin – Request tenant data export; External Storage (S2)
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Admin opens the Organisation page and clicks "Export data".
2. System displays what the export will contain and asks for confirmation.
3. The Admin confirms; System accepts the request and returns an export identifier.
4. The Worker assembles the archive of the organisation's data and stores it.
5. System lists the export as ready, with its size and its expiry.
6. The Admin downloads the archive through a time-limited link.

**Exceptional flow:**
1. **Export already running:** In step 3, System refuses a second concurrent export and points at the one in progress.
2. **Archive expired:** In step 6, if the retention has elapsed, the link is refused and the Admin requests a new export.
3. **Cross-tenant access:** In step 6, an administrator of another organisation is refused; the export belongs to the organisation that requested it.
4. **Assembly failed:** In step 4, System marks the export failed with the reason and keeps no partial archive.

---

### UC508 — Purge tenant data

| **Use Case** | Purge tenant data | **ID** | UC508 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Optional |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *The Platform Administrator permanently erases an organisation's data. The action is irreversible, so it is preceded by a preview of exactly what will be destroyed and by a re-authentication.*

**Relationship:**
- **Association:** Platform Administrator – Purge tenant data; External Storage (S2)
- **Include:** UC601 Elevate privileges
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Administrator opens the organisation and selects "Purge data".
2. System displays the purge preview: how many samples, classes, files, members and jobs will be destroyed.
3. The Administrator reads the preview and types the organisation slug to confirm.
4. System requires re-authentication (UC601).
5. System deletes the organisation's rows and the stored files, in an order that never leaves a row pointing at a file that is already gone.
6. System writes an audit entry that survives the purge, recording who purged what and when.
7. System reports the purge summary.

**Exceptional flow:**
1. **Preview mismatch:** In step 5, if the counts changed between the preview and the confirmation, System aborts and asks the Administrator to review a fresh preview.
2. **Storage deletion fails:** In step 5, System stops and reports which files remain; a partial purge is reported, never presented as complete.
3. **Wrong confirmation text:** In step 3, System refuses; typing the slug is what separates this action from a mis-click.
4. **Export first:** In step 2, System offers to run a data export (UC507) before purging, and records whether one was taken.

---

## 13. Đặc tả chi tiết — Nghiệp vụ 6: Quản trị người dùng và chính sách

### UC601 — Elevate privileges

| **Use Case** | Elevate privileges | **ID** | UC601 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Important |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *Before a destructive or irreversible administrative action, the Platform Administrator re-proves that it is really them sitting at the console. The elevation is time-limited and scoped to the current session.*

**Relationship:**
- **Association:** Platform Administrator – Elevate privileges
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Administrator triggers an action that requires elevation.
2. System asks for the account password again. The password is the **only** factor demanded here: the one-time-code module is wired up but not called by the elevation path, so the specification must not promise a second factor the implementation never asks for.
3. The Administrator enters the password.
4. System verifies it and grants an elevated window on the current session only.
5. System writes an audit entry recording the elevation and the action that requested it.
6. System performs the requested action and displays the remaining elevation time.

**Exceptional flow:**
1. **Wrong credentials:** In step 4, System refuses, leaves the session unelevated and counts the failure against the attempt budget.
2. **Elevation expired:** In step 6, if the window elapsed before the action is confirmed, System asks for the credentials again.
3. **Drop privileges:** The Administrator may end the elevated window explicitly; System revokes it immediately rather than waiting for the timeout.
4. **Different session:** In step 4, the elevation does not follow the account to another device; it belongs to the session that proved it.

---

### UC602 — Manage user account

| **Use Case** | Manage user account | **ID** | UC602 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Essential |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *The Platform Administrator inspects the accounts on the platform and acts on them: grant or remove platform administrator rights, lock and unlock an account, or send it a warning notice.*

**Relationship:**
- **Association:** Platform Administrator – Manage user account
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Administrator opens the Users page; System lists the accounts with their organisation, role, state and last activity.
2. The Administrator opens an account and reads its detail: memberships, sessions, contributions and consent state.
3. The Administrator selects an action: change platform role, lock, unlock, or warn.
4. System asks for a reason, which is mandatory for a lock and for a warning.
5. System applies the change, writes an audit entry with the previous and the new state, and notifies the account owner.
6. System displays the updated account.

**Exceptional flow:**
1. **Locking oneself:** In step 5, System refuses to let an Administrator lock their own account.
2. **Last platform administrator:** In step 5, System refuses to remove the platform role from the last remaining administrator.
3. **Locked account signs in:** After a lock, the sign-in attempt is refused with the recorded reason (UC105).
4. **Warning acknowledgement:** After step 5, the warned account sees the notice at the next sign-in and must acknowledge it before continuing.
5. **Sensitive fields:** In step 2, System never returns the password hash or the two-factor secret; the response model filters them, and removing that filter is what once leaked them.

---

### UC603 — Apply security action

| **Use Case** | Apply security action | **ID** | UC603 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Important |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *The Platform Administrator responds to abuse: force a session to end, or block an address range from reaching the platform.*

**Relationship:**
- **Association:** Platform Administrator – Apply security action
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Administrator opens the security log and reviews the suspicious activity: failed sign-ins, rate-limit hits, blocked requests.
2. The Administrator selects the offending session or address.
3. The Administrator chooses "Force sign-out" or "Block address" and enters a reason.
4. System applies the action: revoking the session and denying its tokens, or adding the address to the block list.
5. System writes an audit entry and displays the action in the security log.
6. The Administrator may later unblock the address, which is recorded as its own entry.

**Exceptional flow:**
1. **Address behind a shared gateway:** In step 4, System warns when the address belongs to a range known to be shared, because blocking it removes many users at once.
2. **Blocking oneself:** In step 4, System refuses to block the address the Administrator is currently connected from.
3. **Session already gone:** In step 4, System reports the current state and performs no second revocation.
4. **Rate-limit counting:** The address used for these limits is taken from the trusted proxy chain, never from a header the caller controls; otherwise the caller would choose which address the limits count.

---

### UC604 — Review audit log

| **Use Case** | Review audit log | **ID** | UC604 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Important |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *The Platform Administrator reads the durable record of who did what: which account, which action, on which object, from which address and when.*

**Relationship:**
- **Association:** Platform Administrator – Review audit log
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Administrator opens the Audit page.
2. System displays the entries newest first, with actor, action, target, address and time.
3. The Administrator filters by actor, by action kind or by period.
4. System returns the matching entries with their recorded detail, including the previous value where the action changed one.
5. The Administrator exports the filtered set for an external review.

**Exceptional flow:**
1. **No scope:** In step 2, if the caller's tenant scope cannot be determined, System returns nothing rather than everything — the log fails closed, because a query that runs before the scope is known would otherwise read across organisations.
2. **Unknown count:** In step 2, where a count cannot be computed exactly, System reports `-1`, which means "do not infer", not "zero".
3. **Entry immutability:** In step 4, entries cannot be edited or deleted from this page; the durable log is evidence, and a rewritable log is not.

---

### UC605 — Configure platform settings

| **Use Case** | Configure platform settings | **ID** | UC605 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Important |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *The Platform Administrator changes the runtime settings of the platform — self-serve signup, quotas, retention windows, alert thresholds — without a redeployment.*

**Relationship:**
- **Association:** Platform Administrator – Configure platform settings
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Administrator opens the Settings section; System displays each setting with its current value and its default.
2. The Administrator changes a value and saves.
3. System validates the value against its type and its allowed range.
4. System stores the setting, applies it to the running instance and writes an audit entry with the previous value.
5. System displays the new value and the time it took effect.

**Exceptional flow:**
1. **Invalid value:** In step 3, System refuses and keeps the previous value in force.
2. **Deployment-level setting:** In step 2, settings baked into the container image cannot be changed here; System marks them read-only and states that they require a redeployment, since a restart alone does not reload them.
3. **Turning signup on:** In step 4, enabling self-serve signup is highlighted as a policy change with a security consequence and is recorded as such.
4. **Hardware alert:** The Administrator may silence a hardware alert; System records who silenced it, so a silenced alert is never anonymous.

---

### UC606 — Draft and review legal document

| **Use Case** | Draft and review legal document | **ID** | UC606 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Important |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *The Platform Administrator writes a legal document as a draft, moves it through review, and only then publishes it. Everything before publication is freely editable; publication is the one-way door (UC607).*

**Relationship:**
- **Association:** Platform Administrator – Draft and review legal document
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Administrator opens the drafts list; System displays each draft with its kind, its state and who last touched it.
2. The Administrator creates a draft, or opens an existing one.
3. The Administrator edits the body and the metadata and saves; System stores the change.
4. The Administrator moves the draft to the next state, for example from writing to review.
5. A reviewer reads the draft and the versions already published for that kind, and compares them.
6. When the draft is accepted, the Administrator publishes it from the draft (UC607), which mints an immutable version.

**Exceptional flow:**
1. **Publishing needs re-authentication:** In step 6, publication demands the password again; drafting and reviewing do not.
2. **Draft deleted:** In step 3, a draft may be discarded at any time and leaves nothing behind — only publication is irreversible.
3. **Comparing with a superseded version:** In step 5, administrators may read any past version, including ones no longer in force; the public may not (UC111).
4. **Two administrators edit at once:** In step 3, the last save wins and the draft records who made it, which is why review happens on drafts rather than on published text.

---

### UC607 — Publish legal document

| **Use Case** | Publish legal document | **ID** | UC607 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Essential |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *The Platform Administrator publishes a version of a legal document — terms, privacy policy, data-collection consent. A published version is immutable and becomes the version users are asked to accept.*

**Relationship:**
- **Association:** Platform Administrator – Publish legal document
- **Include:** UC601 Elevate privileges
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Administrator opens the Legal section and creates a draft, or uploads a document file.
2. The Administrator edits the draft body and sets the document kind, the version and the effective date.
3. The Administrator reviews the rendered draft.
4. The Administrator clicks "Publish" and re-authenticates (UC601).
5. System stores the body, computes its content hash and marks the version published; a database trigger makes the row immutable from that point.
6. System makes the version the one in force from its effective date and asks every account to accept it again (UC112).
7. System writes a publication event and notifies the accounts concerned.

**Exceptional flow:**
1. **Editing a published version:** In step 5, any later attempt to modify the row is rejected by the trigger; a correction is a **new version**, never an edit.
2. **Version already exists:** In step 5, System refuses a duplicate kind-and-version pair.
3. **Effective date in the past:** In step 6, System warns that consents will be requested immediately.
4. **Draft discarded:** In step 3, a draft can be deleted freely; only publication is irreversible.

---

### UC608 — Review consent records

| **Use Case** | Review consent records | **ID** | UC608 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Important |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *The Platform Administrator inspects who accepted which version of which document, and when a consent was withdrawn — the evidence behind every release decision the platform makes.*

**Relationship:**
- **Association:** Platform Administrator – Review consent records
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Administrator opens the legal administration section and reads the publication events: which version of which kind became effective when, and by whom.
2. The Administrator looks up an account.
3. System displays that account's consents: document kind, version, content hash, acceptance time and withdrawal time when there is one.
4. The Administrator uses the record to explain why a given sample is or is not included in a release.

**Exceptional flow:**
1. **No consent on file:** In step 3, System reports the account has none; that is the state that makes its samples unreleasable, and it must not be confused with a consent that was withdrawn.
2. **Withdrawn consent:** In step 3, the withdrawal is shown **beside** the original acceptance, not instead of it — the acceptance really happened, and erasing it would destroy the evidence.
3. **Hash mismatch:** In step 3, if the stored hash does not match the version it names, System flags the record instead of rendering it as valid.

---

### UC609 — Manage billing plans

| **Use Case** | Manage billing plans | **ID** | UC609 |
|---|---|---|---|
| **Main actor** | Platform Administrator | **Priority** | Optional |
| **Trigger** | Platform Administrator | **Type** | external |

**Brief description:** *The Platform Administrator edits the catalogue of plans — the quotas each plan grants — and assigns a plan to an organisation.*

**Relationship:**
- **Association:** Platform Administrator – Manage billing plans
- **Include:** UC601 Elevate privileges
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Administrator opens the Billing administration page.
2. System lists the plans with their quotas: members, classes, samples, training runs and predictions.
3. The Administrator edits a plan's quotas and saves.
4. System validates the values and stores them; organisations on that plan pick up the new limits at their next quota check.
5. The Administrator assigns a plan to an organisation and sets the period.
6. System writes an audit entry and displays the platform-wide usage against the plans.

**Exceptional flow:**
1. **Suspending an organisation:** From step 5, the Administrator may also set the organisation's commercial state. Suspension stops writes while leaving reads and exports working — that state lives on the **commercial** axis (`billing_status`), and it is not the same thing as the administrative lock of an account in UC602. The schema deliberately expresses "stop writing, keep reading" here and nowhere else.
2. **Lowering a quota below current usage:** In step 4, System warns that the organisations already above the new limit keep their data but cannot add more.
3. **Plan in use:** In step 3, a plan assigned to organisations cannot be deleted; it can only be edited or retired.
4. **Rate limit:** In step 3, catalogue writes share the same rate limit as the other catalogue operations.

---

## 14. Đặc tả chi tiết — Nghiệp vụ 7: Vận hành hệ thống và nguồn sự thật

### UC701 — Manage SOT writer machines

| **Use Case** | Manage SOT writer machines | **ID** | UC701 |
|---|---|---|---|
| **Main actor** | Operations Engineer | **Priority** | Important |
| **Trigger** | Operations Engineer | **Type** | external |

**Brief description:** *The Operations Engineer decides which machines may write into the source of truth. A machine writes only if its signing key is registered; keys are granted and revoked from this page.*

**Relationship:**
- **Association:** Operations Engineer – Manage SOT writer machines; SOT Writer Machine (S5)
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Operations Engineer opens the SOT admin page.
2. System displays the registered machines: fingerprint, label, who registered it and when it last wrote.
3. The Operations Engineer registers a new machine by entering its label and its public key fingerprint. Platform administrator rights are enough here; unlike a purge or a legal publication, this action does **not** demand re-authentication.
4. System stores the key, which is unioned with the baseline keys committed to the repository, and writes an audit entry.
5. The Operations Engineer may revoke a machine; System removes its key and records the revocation.
6. System displays the resulting list of authorised writers.

**Exceptional flow:**
1. **Duplicate fingerprint:** In step 4, System refuses; one fingerprint is one machine.
2. **Revoking the only publisher:** In step 5, System warns that no machine would be left able to publish, which would stop the whole stack from starting.
3. **Unregistered machine writes:** A machine whose key is not registered is refused at startup with a distinct exit code that deliberately blocks the whole stack — the block is intentional and must not be loosened.
4. **Baseline key:** In step 5, keys committed to the repository cannot be revoked from this page; they are changed by a code change and a redeployment.

---

### UC702 — Verify source-of-truth integrity

| **Use Case** | Verify source-of-truth integrity | **ID** | UC702 |
|---|---|---|---|
| **Main actor** | Operations Engineer | **Priority** | Important |
| **Trigger** | Operations Engineer | **Type** | external |

**Brief description:** *The Operations Engineer verifies that the registry, the database mirror and the stored files still agree, and that the registry carries a valid signature from an authorised machine.*

**Relationship:**
- **Association:** Operations Engineer – Verify source-of-truth integrity; SOT Writer Machine (S5)
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Operations Engineer opens the SOT overview.
2. System displays the registry schema, the row counts and the state of the remote copy.
3. The Operations Engineer clicks "Verify".
4. System checks the signature of the registry against the authorised keys.
5. System compares the registry rows with the database mirror and with the files present in storage.
6. System reports the verdict: signature valid or not, and the exact differences found on each side.

**Exceptional flow:**
1. **Invalid signature:** In step 4, System reports the failure and names the fingerprint that signed, which may be a machine that has since been revoked.
2. **Rows in the database but not in the registry:** In step 5, System lists them; this is the failure mode that live captures produced before the dispatch ordering was fixed, and the reconciliation task repairs it from the database.
3. **Files with no row:** In step 5, System lists orphan files separately from missing files; the two are repaired in opposite directions.
4. **Remote copy behind:** In step 2, System states that synchronisation never deletes, but does overwrite backwards, so a merge must only ever fill blanks.

---

### UC703 — Synchronize storage and database

| **Use Case** | Synchronize storage and database | **ID** | UC703 |
|---|---|---|---|
| **Main actor** | Operations Engineer | **Priority** | Important |
| **Trigger** | Operations Engineer | **Type** | external |

**Brief description:** *The Operations Engineer reconciles the three places where a sample is recorded — the registry file, the database mirror and the object storage — after an incident left them disagreeing.*

**Relationship:**
- **Association:** Operations Engineer – Synchronize storage and database; External Storage (S2)
- **Include:** UC702 Verify source-of-truth integrity
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Operations Engineer opens the Data page and reads the data report: rows per source and the differences between them.
2. The Operations Engineer starts a synchronisation run.
3. System scans the local files, the registry and the database, and computes the repairs needed.
4. System applies the repairs in the safe direction: the registry is the source of truth, and the database is rebuilt from it.
5. System returns a task identifier so the run can be followed.
6. System reports the summary: rows added, storage keys backfilled, rows left unresolved.

**Exceptional flow:**
1. **Run already in progress:** In step 2, System refuses a second concurrent run.
2. **Silent failure modes:** In step 4, System reports explicitly when a repair was skipped; a synchronisation that reports success while having written nothing is the failure this report exists to expose.
3. **Unresolvable rows:** In step 6, rows whose file is gone are listed rather than deleted; deletion of real data is never a repair step.
4. **Spreadsheet mirror:** In step 4, soft-deleted rows keep their marker in the mirror and are not shifted out, so external row references stay valid.

---

### UC704 — Monitor system health

| **Use Case** | Monitor system health | **ID** | UC704 |
|---|---|---|---|
| **Main actor** | Operations Engineer | **Priority** | Important |
| **Trigger** | Operations Engineer | **Type** | external |

**Brief description:** *The Operations Engineer watches the health of the running system: service readiness, queue depth, resource usage and the alerts that fired.*

**Relationship:**
- **Association:** Operations Engineer – Monitor system health; Notification Gateway (S1)
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Operations Engineer opens the Resources page.
2. System displays the health of each service, the database and cache connectivity, and the queue depth.
3. System displays the host resources: CPU, memory, disk and GPU when one is present.
4. System displays the items needing attention: failed jobs, stalled workers, quotas near their limit.
5. The Operations Engineer opens an item and follows it to the page that can act on it.
6. When an alert threshold is crossed, System sends the alert by email.

**Exceptional flow:**
1. **Health is not freshness:** In step 2, a healthy service does not prove it runs the current code; the deployment freshness check is a separate verification.
2. **Sampling artefact:** In step 3, a CPU reading taken over too short an interval always reports zero; System uses an interval long enough to be meaningful.
3. **GPU present but not exposed:** In step 3, if the host has a GPU that the container does not see, System reports it as absent — which is what a missing compose overlay looks like from inside.
4. **Alert delivery:** In step 6, the alert body is plain text; markup placed in it is escaped rather than rendered.

---

### UC705 — Back up and restore data

| **Use Case** | Back up and restore data | **ID** | UC705 |
|---|---|---|---|
| **Main actor** | Operations Engineer | **Priority** | Essential |
| **Trigger** | Operations Engineer, or the scheduler | **Type** | external |

**Brief description:** *The Operations Engineer takes database backups and, when needed, restores one. Restoring into production is deliberately harder than rehearsing a restore, because the two have opposite consequences.*

**Relationship:**
- **Association:** Operations Engineer – Back up and restore data; Background Processor (S4)
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Operations Engineer runs the backup tool, which dumps the database and only then compresses the result.
2. System writes the archive to the backup store and reports its size and checksum.
3. To verify a backup, the Operations Engineer runs a **rehearsal** restore, which loads the archive into a scratch database instead of production.
4. System reports what the rehearsal found: whether the archive loads, and what it contains.
5. To restore for real, the Operations Engineer names the target explicitly and passes the flag that forces a production restore.
6. System restores the archive and reports the outcome.

**Exceptional flow:**
1. **A listing is not a verification:** In step 3, reading the table of contents of an archive does **not** detect a truncated file; only loading it does. This is why the rehearsal exists as its own mode.
2. **Restoring into production by accident:** In step 5, the tool refuses to touch production unless the forcing flag is given; every other invocation lands in a scratch database.
3. **Encrypted archive:** In step 6, an encrypted archive must be decrypted first; encryption and the off-disk copy exist but are off by default, so an operator must not assume either is in place.
4. **Scheduled backups:** In step 1, the scheduler can run the same tool unattended; a schedule that was configured but never fired leaves no archive at all, so the store must be checked, not assumed.

---

### UC706 — Verify deployment freshness

| **Use Case** | Verify deployment freshness | **ID** | UC706 |
|---|---|---|---|
| **Main actor** | Operations Engineer | **Priority** | Important |
| **Trigger** | Operations Engineer | **Type** | external |

**Brief description:** *After a deployment, the Operations Engineer checks that the code actually running is the code in the working tree. A health check answers "is the process alive", never "is it the process you just built".*

**Relationship:**
- **Association:** Operations Engineer – Verify deployment freshness
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Operations Engineer runs the freshness check on the deployment host. The check is read-only.
2. System compares what each running container is serving against what the working tree currently holds.
3. System reports every service that is stale, and why it is stale.
4. System exits with a success code only when everything running is current.
5. The Operations Engineer rebuilds and redeploys whatever the report named.

**Exceptional flow:**
1. **Everything healthy but stale:** In step 2, containers may report healthy while serving an image hours old; that is the exact situation this check exists for, and health status is no substitute.
2. **One image behind several services:** In step 3, several services share one image, so a single stale build makes all of them stale — the report names each of them rather than only the one that was noticed.
3. **Environment file changed:** In step 5, a changed environment file is not picked up by a restart; the containers must be recreated, and the check reports the difference rather than hiding it.

---

## 15. Đặc tả chi tiết — Nghiệp vụ 8: Hỗ trợ và tích hợp

### UC801 — Create support ticket

| **Use Case** | Create support ticket | **ID** | UC801 |
|---|---|---|---|
| **Main actor** | Authenticated User | **Priority** | Important |
| **Trigger** | Authenticated User | **Type** | external |

**Brief description:** *The Authenticated User opens a support ticket describing a problem or a request, choosing a category so that it reaches the right queue.*

**Relationship:**
- **Association:** Authenticated User – Create support ticket; Notification Gateway (S1)
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The user opens the Support page; System displays the categories and a few starting points based on the user's recent activity.
2. The user selects a category, enters a subject and a description, and submits.
3. System validates the input and creates the ticket in the open state, inside the user's organisation.
4. System notifies the staff on duty by email that a new ticket arrived.
5. System displays the ticket with its identifier and its state.

**Exceptional flow:**
1. **Empty description:** In step 3, System refuses and keeps what the user typed.
2. **Too many open tickets:** In step 3, System asks the user to reply on an existing ticket instead of opening another.
3. **Mail not sent:** In step 4, the ticket still exists and appears in the queue; the notification is a convenience, not the record.
4. **Identifier types:** In step 4, the notification query joins on identifiers of the same type; a mismatched comparison here is what once made these emails never send at all.

---

### UC802 — Reply to support ticket

| **Use Case** | Reply to support ticket | **ID** | UC802 |
|---|---|---|---|
| **Main actor** | Authenticated User | **Priority** | Important |
| **Trigger** | Authenticated User or Platform Administrator | **Type** | external |

**Brief description:** *The user and the staff exchange messages on a ticket until it is resolved, and the state of the ticket is updated accordingly.*

**Relationship:**
- **Association:** Authenticated User – Reply to support ticket; Platform Administrator – Reply to support ticket
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The user opens a ticket; System displays the thread in order with the author of each message.
2. The user writes a reply and sends it.
3. System checks that the caller owns the ticket or is staff.
4. System appends the message, updates the ticket's last-activity time and notifies the other side.
5. System displays the updated thread.

**Exceptional flow:**
1. **Ticket closed:** In step 3, replying to a closed ticket reopens it and records who reopened it.
2. **Not the owner:** In step 3, a user who neither owns the ticket nor is staff is refused; tickets stay inside the organisation boundary.
3. **Staff reply:** When the author is staff, System marks the message as coming from support so the thread stays readable.

---

### UC803 — Handle support queue

| **Use Case** | Handle support queue | **ID** | UC803 |
|---|---|---|---|
| **Main actor** | Support Staff | **Priority** | Important |
| **Trigger** | Support Staff | **Type** | external |

**Brief description:** *The Support Staff works the queue of open tickets: reads them in order, answers them and sets their state.*

**Relationship:**
- **Association:** Support Staff – Handle support queue; Notification Gateway (S1)
- **Include:** UC802 Reply to support ticket
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The staff member opens the queue; System lists the tickets of the organisation by state and age.
2. The staff member opens the oldest open ticket and reads the thread.
3. The staff member replies (UC802).
4. The staff member sets the ticket state: open, pending or resolved.
5. System stores the state, notifies the requester and refreshes the queue.
6. System sends a backlog notice when the queue exceeds its age or size threshold.

**Exceptional flow:**
1. **Empty queue:** In step 1, System says so plainly rather than displaying an empty table.
2. **Ticket taken by another staff member:** In step 4, System reports the state already set and does not overwrite it silently.
3. **Backlog notice versus new-ticket notice:** In step 6, the backlog notice reflects a **state** — how long the queue has been waiting — while the new-ticket notice reflects an **event**; the two use different thresholds and must not be merged.

---

### UC804 — View notifications

| **Use Case** | View notifications | **ID** | UC804 |
|---|---|---|---|
| **Main actor** | Authenticated User | **Priority** | Important |
| **Trigger** | Authenticated User | **Type** | external |

**Brief description:** *The Authenticated User reads the notifications the platform produced for them — finished jobs, invitations, quota warnings, administrative notices — and marks them read.*

**Relationship:**
- **Association:** Authenticated User – View notifications
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. System displays the unread count in the navigation bar.
2. The user opens the Notifications page; System lists the notifications newest first, with their kind.
3. The user filters by kind.
4. The user opens a notification and follows it to the page it refers to.
5. System marks it read, or the user marks everything read at once, and the unread count updates.

**Exceptional flow:**
1. **Target gone:** In step 4, if the object referred to has been deleted, System says so instead of opening a broken page.
2. **Mandatory notice:** In step 2, an administrative notice must be acknowledged before the user continues; it cannot be dismissed from the list.
3. **Scope:** In step 2, a user sees only their own notifications; there is no cross-account view here.

---

### UC805 — Manage API keys

| **Use Case** | Manage API keys | **ID** | UC805 |
|---|---|---|---|
| **Main actor** | Organization Admin | **Priority** | Optional |
| **Trigger** | Organization Admin | **Type** | external |

**Brief description:** *The Organization Admin issues and revokes the API keys that let an external application act on the organisation's data within a declared scope.*

**Relationship:**
- **Association:** Organization Admin – Manage API keys; Third-party Client (S6)
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Admin opens the Integrations page; System lists the existing keys with their label, scope, creation date and last use.
2. The Admin clicks "New key", enters a label and selects the scope: read-only or read-write.
3. System generates the key, stores only its hash and displays the secret **once**.
4. The Admin copies the secret into the external application.
5. The Admin may revoke a key at any time; System invalidates it immediately and writes an audit entry.

**Exceptional flow:**
1. **Secret lost:** In step 4, the secret cannot be displayed again; the Admin revokes the key and issues a new one.
2. **Write with a read-only key:** A read-only key attempting a write is refused; a key's authority comes from its own scope, not from the person who created it, because a key has no membership row.
3. **Key used after revocation:** The call is refused and recorded in the security log.
4. **Key quota:** In step 3, System refuses beyond the number of keys the plan allows.

---

### UC806 — Manage webhook endpoints

| **Use Case** | Manage webhook endpoints | **ID** | UC806 |
|---|---|---|---|
| **Main actor** | Organization Admin | **Priority** | Optional |
| **Trigger** | Organization Admin | **Type** | external |

**Brief description:** *The Organization Admin registers the URLs that should receive platform events, tests them, and inspects the delivery history.*

**Relationship:**
- **Association:** Organization Admin – Manage webhook endpoints; Third-party Client (S6)
- **Include:** None
- **Extend:** None
- **Generalization:** None

**Normal flow:**
1. The Admin opens the Integrations page and reads the list of event kinds the platform emits.
2. The Admin adds an endpoint: the destination URL and the event kinds it subscribes to.
3. System validates the URL and stores the endpoint with a signing secret.
4. The Admin clicks "Test"; System sends a test event and displays the response received.
5. When a subscribed event occurs, System delivers it, signed, and records the attempt.
6. The Admin opens the delivery history to read the status of each attempt.

**Exceptional flow:**
1. **Invalid or unreachable URL:** In step 3 or 4, System refuses to store, or reports the delivery failure with the status code returned.
2. **Delivery fails:** In step 5, System retries with a growing delay and records each attempt; the endpoint is not removed automatically.
3. **Endpoint keeps failing:** In step 6, System flags an endpoint whose recent attempts all failed, so a silently broken integration becomes visible.
4. **Private address:** In step 3, a URL pointing at an internal address is refused, so an endpoint cannot be used to reach services inside the deployment.

---

## 16. Ghi chú áp dụng và những chỗ dễ mô hình hoá sai

### 16.1 Năm chỗ cố ý **không** gộp

**1. Xoá mềm ≠ thùng rác ≠ xoá vĩnh viễn.** UC209, UC211 và UC304 chỉ *đánh dấu*;
tệp vẫn còn nguyên. Chỉ nhánh "purge" của UC212 mới chạm tới kho tệp, và nó xoá
tệp **sau khi** dòng dữ liệu đã biến mất — nên một lần xoá tệp thất bại để lại
tệp mồ côi, không phải một mẫu dở dang. Gộp ba mức này thành một use case là bỏ
mất đúng cái tính hoàn tác được mà người dùng trông cậy.

**2. Quản trị nền tảng ≠ quản trị tổ chức.** NV5 và NV6 không kế thừa nhau (§2.5).
Vẽ A7 kế thừa A8 — hoặc ngược lại — là mô tả sai chính cái ranh giới mà backend
đang giữ, và là cách hợp thức hoá một lỗ hổng thật.

**3. Chính sách ≠ hạ tầng.** NV6 và NV7 cùng do một vai kỹ thuật kiểm nhưng hỏng
theo hai kiểu khác nhau, và người chịu trách nhiệm cũng khác nhau (§3).

**4. Người ký ≠ tài khoản thu.** A3 là **chủ thể dữ liệu**; A5 là người có thể
đang vận hành buổi thu. Hệ thống tách `signer_id` khỏi `auth_user_id` đúng vì hai
người đó khác nhau, và UC210 tồn tại vì hai cột ấy gán lệch nhau được. Nhưng phải
nhớ: chúng khác nhau ở **người và mục tiêu**, không khác nhau ở **quyền** — không
có dòng nào trong CSDL nói ai là người khiếm thính (§2.4).

**5. Tác nhân hệ thống là tác nhân thật.** UC203 do S4 khởi phát (`internal`),
không do người dùng. Bỏ nó đi thì không giải thích được vì sao mẫu vừa quay xong
lại chưa dùng huấn luyện được ngay.

### 16.2 Ba use case mô tả **giới hạn** của hệ thống, không phải mong muốn

| Use case | Sự thật được ghi thẳng vào đặc tả |
|---|---|
| **UC503** Accept invitation | Người **đã có tài khoản** hiện không có đường tự nhận lời mời — `consume_invitation` chỉ được gọi ở đường đăng ký. Danh sách lời mời vì thế có thể hiển thị một lời mời mà người nhận không thể chấp nhận. |
| **UC213** Export dataset snapshot | Chạy bằng **công cụ dòng lệnh trên máy triển khai**. Bộ định tuyến HTTP `dataset_exporter` còn trong cây mã nhưng **không được gắn** vào ứng dụng, nên không URL nào chạm tới. |
| **UC601** Elevate privileges | Chỉ hỏi **mật khẩu**. Mô-đun mã một lần đã sẵn sàng nhưng đường nâng quyền không gọi nó, nên đặc tả không được hứa một yếu tố thứ hai mà hiện thực không đòi. |

Ba mục này ở lại trong tài liệu **có chủ ý**. Một đặc tả mô tả hệ thống như nó nên
là sẽ qua được buổi bảo vệ nhưng không dùng được để sửa hệ thống.

### 16.3 Endpoint không thành use case riêng — và vì sao

Bản rà soát đối chiếu **từng endpoint đang được mount** với danh sách use case.
Những nhóm dưới đây cố ý nằm trong luồng của một use case khác, vì chúng không
phải là mục tiêu của ai cả:

| Endpoint | Nằm trong | Lý do |
|---|---|---|
| `POST /auth/refresh` | UC105 | Gia hạn phiên là việc trình duyệt tự làm; không ai "muốn" gia hạn phiên. |
| `GET /auth/me`, `/2fa/status`, `/trial/status` | UC110, UC109, UC114 | Đọc trạng thái để vẽ màn hình. |
| `GET /health/*`, `/metrics` | UC704 | Đầu dò cho máy khác gọi, không có người dùng. |
| `GET /admin/activity`, `/security-log` | UC604, UC603 | Cùng mục tiêu "đọc dấu vết", khác nguồn. |
| `GET /training/splits`, `/dataset-info`, `/queue/status` | UC401, UC402 | Số liệu để cấu hình và theo dõi một lượt chạy. |
| `GET /classes/suggest`, `/collectors`, `/balance` | UC206, UC210, UC305 | Trợ giúp bên trong một màn hình đã có use case. |
| `POST /dataset/samples/add` | UC201 | Cùng đường ghi mẫu, khác điểm vào. |
| `POST /tenants/invitations/inspect` | UC503 | Bước đọc token trước khi nhận lời mời. |
| `POST /upload/video/process` | UC202 | Bước hai của cùng một hành vi tải lên. |

### 16.4 Bảng tra ngược mã cũ → mã mới

Dành cho ai đang giữ bản đánh số cũ (UC001–UC075).

| Cũ | Mới | Cũ | Mới | Cũ | Mới | Cũ | Mới |
|---|---|---|---|---|---|---|---|
| UC001 | UC101 | UC020 | UC208 | UC039 | UC501 | UC058 | UC801 |
| UC002 | UC102 | UC021 | UC209 | UC040 | UC502 | UC059 | UC802 |
| UC003 | UC103 | UC022 | UC210 | UC041 | UC503 | UC060 | UC803 |
| UC004 | UC104 | UC023 | UC211 | UC042 | UC504 | UC061 | UC804 |
| UC005 | UC105 | UC024 | UC212 | UC043 | UC505 | UC062 | UC805 |
| UC006 | UC106 | UC025 | UC213 | UC044 | UC506 | UC063 | UC806 |
| UC007 | UC107 | UC026 | UC301 | UC045 | UC507 | UC064 | UC111 |
| UC008 | UC108 | UC027 | UC302 | UC046 | UC508 | UC065 | UC205 |
| UC009 | UC109 | UC028 | UC304 | UC047 | UC601 | UC066 | UC303 |
| UC010 | UC110 | UC029 | UC306 | UC048 | UC602 | UC067 | UC308 |
| UC011 | UC112 | UC030 | UC307 | UC049 | UC603 | UC068 | UC309 |
| UC012 | UC113 | UC031 | UC305 | UC050 | UC604 | UC069 | UC310 |
| UC013 | UC114 | UC032 | UC401 | UC051 | UC605 | UC070 | UC405 |
| UC014 | UC201 | UC033 | UC402 | UC052 | UC607 | UC071 | UC409 |
| UC015 | UC202 | UC034 | UC403 | UC053 | UC701 | UC072 | UC606 |
| UC016 | UC203 | UC035 | UC404 | UC054 | UC702 | UC073 | UC608 |
| UC017 | UC204 | UC036 | UC406 | UC055 | UC704 | UC074 | UC705 |
| UC018 | UC206 | UC037 | UC407 | UC056 | UC703 | UC075 | UC706 |
| UC019 | UC207 | UC038 | UC408 | UC057 | UC609 | | |
