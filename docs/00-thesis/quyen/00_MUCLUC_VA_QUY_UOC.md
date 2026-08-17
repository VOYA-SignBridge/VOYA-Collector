# Quyển luận văn — mục lục, quy ước và phần đầu quyển

*Dựng 16/08/2026. Thư mục `docs/00-thesis/quyen/` chứa **bản thảo theo cấu trúc
mẫu CT553H**: mỗi phần/chương một tệp, đánh số theo thứ tự đóng quyển.*

---

## 1. Bản đồ tệp ↔ mục lục mẫu

| Mục trong mục lục mẫu | Tệp | Trạng thái |
|---|---|---|
| COMMITMENT TO RESULTS | — | mẫu trường, điền tay |
| MỤC LỤC · DANH MỤC HÌNH · DANH MỤC BẢNG | tệp này, §4–§6 | khung + quy ước |
| BẢNG TRA CỨU THUẬT NGỮ | tệp này, §3 | **xong** |
| TÓM TẮT / ABSTRACT | tệp này, §7 | **xong** |
| **PHẦN GIỚI THIỆU** (mục 1–7) | `01_PHAN_GIOI_THIEU.md` | **xong** — xem §2 |
| **CHƯƠNG 1: MÔ TẢ BÀI TOÁN** | `02_CHUONG1_MO_TA_BAI_TOAN.md` | **xong** |
| **CHƯƠNG 2: CƠ SỞ LÝ THUYẾT** | `03_CHUONG2_CO_SO_LY_THUYET.md` | **xong** — xem §2 |
| **CHƯƠNG 3: THIẾT KẾ VÀ CÀI ĐẶT GIẢI PHÁP** | `04_CHUONG3_THIET_KE_VA_CAI_DAT.md` | **xong** |
| **CHƯƠNG 4: KIỂM THỬ VÀ ĐÁNH GIÁ** | `05_CHUONG4_KIEM_THU_VA_DANH_GIA.md` | **xong** |
| **PHẦN KẾT LUẬN** | `06_PHAN_KET_LUAN.md` | **xong** |
| TÀI LIỆU THAM KHẢO | `../BANG_TRA_TRICH_DAN.md` + thư viện Zotero | **xong** — xem §8 |
| **PHỤ LỤC A**: Mô hình dữ liệu đầy đủ | `PHU_LUC_A_MO_HINH_DU_LIEU.md` | **xong** |
| **PHỤ LỤC B**: Cài đặt hệ thống | `PHU_LUC_B_CAI_DAT_HE_THONG.md` | **xong** |
| **PHỤ LỤC C**: Đặc tả use case chi tiết | `PHU_LUC_C_DAC_TA_USE_CASE.md` | **xong** |
| **PHỤ LỤC D**: Bộ ca kiểm thử chi tiết | `PHU_LUC_D_CA_KIEM_THU.md` | **xong** |
| **PHỤ LỤC E**: Giao thức đo và quyết định kiến trúc | `PHU_LUC_E_GIAO_THUC_DO.md` | **xong** |
| **PHỤ LỤC F**: Phân tích so sánh mở rộng | `PHU_LUC_F_SO_SANH_MO_RONG.md` | **xong** — xem §2 |

Mẫu chỉ liệt kê hai phụ lục A và B như **ví dụ**, không phải giới hạn. Đề tài này
có khối lượng thiết kế lớn hơn một đồ án thông thường, nên tách sáu phụ lục theo
**loại tạo tác** thay vì dồn tất cả vào một khối: A là dữ liệu, B là vận hành, C là
đặc tả, D là bằng chứng kiểm thử, E là phương pháp, F là phân tích so sánh mở rộng
của Chương 2. Người phản biện tra được đúng
chỗ mà không phải lật qua ba mươi trang không liên quan.

### Nguyên tắc phân bổ nội dung chính ↔ phụ lục

Hệ thống có 57 bảng dữ liệu, 79 use case, 213 điểm cuối API và 2.528 ca kiểm thử.
Đưa hết vào thân bài thì thân bài không còn đọc được. Luật cắt như sau:

| Loại nội dung | Vào thân bài | Vào phụ lục |
|---|---|---|
| Mô hình dữ liệu | **sơ đồ theo nhóm mô-đun** (7 nhóm) + bảng tóm tắt nhóm | CDM đầy đủ, PDM đầy đủ, danh mục 57 bảng kèm từng cột |
| Use case | danh sách 79 UC + đặc tả chi tiết **8 UC trục chính** | đặc tả chi tiết toàn bộ 79 UC |
| Kiểm thử | kịch bản + ca kiểm thử **đại diện mỗi nghiệp vụ** | bảng ca kiểm thử đầy đủ |
| Điểm cuối API | bảng đếm theo bộ định tuyến | danh mục đầy đủ (`/openapi.json`) |
| Quyết định thiết kế | lập luận + bảng so sánh **các tiêu chí quyết định** | ma trận **đầy đủ mọi tiêu chí** (Phụ lục F), biên bản ADR, giao thức đo chi tiết |

Câu hỏi để quyết mỗi lần phân vân: *người phản biện có cần đọc mục này để hiểu
lập luận không, hay chỉ cần biết nó tồn tại và tra được?* Cần để hiểu → thân bài.
Chỉ cần tra → phụ lục.

### Luật tách thân ↔ phụ lục cho phần lý thuyết (Chương 2 ↔ Phụ lục F)

Một quy tắc duy nhất, áp cho mọi đoạn, bảng và hình của Chương 2:

> **Lập luận không bao giờ bị đẩy ra phụ lục. Chỉ phân tích mở rộng, tiêu chí thứ
> cấp và chi tiết hỗ trợ cho lập luận mới được đẩy ra Phụ lục F.**

Cụ thể hoá bằng sáu câu hỏi:

| # | Câu hỏi | Nếu CÓ |
|---|---|---|
| 1 | Nội dung liên quan trực tiếp tới một cụm từ trong **tên đề tài**? | Thân bài |
| 2 | Nó dẫn trực tiếp tới một quyết định thiết kế ở Chương 3? | Thân bài |
| 3 | Bỏ nó đi thì người đọc còn hiểu **vì sao chọn** phương án hiện tại không? | Không còn hiểu → thân bài |
| 4 | Nó chủ yếu bổ sung tiêu chí, trường hợp biên hay chi tiết cho một kết luận đã rõ? | Phụ lục F |
| 5 | Nó mô tả **hiện thực cụ thể** thay vì lý thuyết hoặc lý do? | Chương 3/4, **không** phải phụ lục F |
| 6 | Nó chứa kết quả đo, số liệu kiểm thử, quan sát thực nghiệm hay bằng chứng về hiện thực của CTU.SignBridge? | Chương 4 / Phụ lục D–E; **tuyệt đối không** Chương 2 hay Phụ lục F |

Hệ quả bắt buộc, đã áp dụng cho toàn bộ Chương 2:

* **Không tách phương án khỏi lý do chọn.** Nếu thân chương chọn lược đồ dùng
  chung thì thân chương **phải** giới thiệu cả ba mô hình và so sánh chúng. Viết
  "chọn lược đồ dùng chung, xem phụ lục để biết hai mô hình còn lại" là sai.
* **Thân giữ tiêu chí quyết định, phụ lục giữ ma trận đầy đủ.** Không bảng nào
  bị cắt: bảng trong thân là tập con của bảng trong phụ lục, và mỗi bảng ở hai
  nơi đều trỏ sang nhau.
* **Dẫn chiếu phải nói phụ lục chứa gì**, không viết "xem thêm phụ lục". Mẫu
  đúng: *"Phân tích mở rộng về khả năng khôi phục riêng tenant, mức tuỳ biến và
  chi phí vận hành được trình bày tại Phụ lục F.2, Bảng F-3."*

**Ba lớp không được lẫn nhau:** Chương 2 trả lời *vì sao*; Chương 3 trả lời *thiết
kế thế nào*; Chương 4 trả lời *bằng chứng nào cho thấy nó chạy được trong phạm vi
đã phát biểu*. Phụ lục F chỉ mở rộng lớp thứ nhất. Viết gọn:

* **Chương 2** = khái niệm nền + các phương án + tiêu chí quyết định + lý do chọn + đánh đổi
* **Phụ lục F** = so sánh mở rộng + tiêu chí thứ cấp + trường hợp biên
* **Chương 3** = thiết kế cụ thể + ánh xạ sang hiện thực
* **Chương 4** = phương pháp kiểm chứng + phép đo + kết quả + giới hạn

### Ranh giới thực nghiệm của Chương 2

**Chương 2 chỉ trình bày cơ sở lý thuyết, các phương án kiến trúc, so sánh định
tính, cơ sở lựa chọn và đánh đổi.** Chương này **không** trình bày kết quả đo, kết
quả kiểm thử, số liệu thực nghiệm, tỉ lệ đạt/không đạt, sự cố quan sát được trong
quá trình phát triển, hay bằng chứng về mức độ hoàn thành của CTU.SignBridge. Khi
cần nói về một thuộc tính có thể kiểm chứng, Chương 2 chỉ xác định **cần kiểm
chứng điều gì và vì sao**; phương pháp đo và kết quả thuộc Chương 4 cùng các phụ
lục thực nghiệm.

| Loại phát biểu | Chương 2 |
|---|---|
| Khái niệm, nguyên lý | Có |
| Phương án kiến trúc | Có |
| So sánh định tính | Có |
| Lý do chọn | Có |
| Đánh đổi | Có |
| Thuộc tính **cần** được kiểm chứng | Có |
| Phương pháp đo cụ thể | **Không** |
| Kết quả kiểm thử | **Không** |
| Tỉ lệ phần trăm, số PASS/FAIL | **Không** |
| Sự cố đã xảy ra trong CTU.SignBridge | **Không** |
| Benchmark của bản hiện thực | **Không** |

### Ba trạng thái của một quyết định — không được suy ra lẫn nhau

Chương 2 dùng nhiều cụm **"định hướng được chọn"**. Cụm đó là kết luận của riêng
Chương 2 và **không** hàm ý hai điều còn lại:

> **Được chọn ≠ Đã hiện thực ≠ Đã kiểm chứng.**

* **Được chọn** — kết luận lý thuyết, Chương 2.
* **Đã hiện thực** — trình bày ở Chương 3, kèm phạm vi thực tế.
* **Đã kiểm chứng** — có bằng chứng ở Chương 4, trong phạm vi phép đo đã định nghĩa.

Ví dụ đúng: Chương 2 chọn lược đồ dùng chung kèm cưỡng chế ở tầng cơ sở dữ liệu;
Chương 3 mô tả cơ chế đó được hiện thực trên những bảng và đường nào; Chương 4 báo
cáo cách ly được kiểm chứng trong phạm vi mô hình đe doạ và tập phép thử đã định
nghĩa. Ba câu này **không thay thế được cho nhau**.

---

## 2. Hai phần viết trước, nay đã chuyển vào thư mục này

Phần giới thiệu và Chương 2 được viết trước phần còn lại và từng nằm ở thư mục
cha dưới tên `LUANVAN_PHANGIOITHIEU.md` và `LUANVAN_CHUONG2.md`. Ngày 16/08/2026
chúng được **chuyển vào đây** và đổi tên theo thứ tự đóng quyển, để cả quyển nằm
trong một thư mục và số hiệu tệp chính là thứ tự đọc:

```
00 phần đầu quyển · 01 phần giới thiệu · 02 chương 1 · 03 chương 2
04 chương 3 · 05 chương 4 · 06 phần kết luận · PHU_LUC_A…F
```

Lịch sử tệp được giữ nguyên (chuyển bằng thao tác đổi tên có theo dõi), nên
`git log --follow` vẫn truy được về các bản nháp trước.

Phần giới thiệu **giữ nguyên** nội dung, chỉ đổi vị trí. Chương 2 thì đã được
viết sâu thêm ngày 17/08/2026 — xem ghi chú ở cuối mục này. Các việc còn phải
làm khi đóng quyển cũng ghi ở đó.

**Phần giới thiệu** — ánh xạ tiêu đề:

| Mục lục mẫu | Tiêu đề trong tệp |
|---|---|
| 1. Đặt vấn đề | 1.1 Đặt vấn đề |
| 2. Lịch sử giải quyết vấn đề | 1.2 (7 tiểu mục, có phần khoảng trống nghiên cứu) |
| 3. Mục tiêu đề tài | 1.3 (1 tổng quát + 5 cụ thể) |
| 4. Đối tượng và phạm vi nghiên cứu | 1.4.1, 1.4.2 |
| 5. Nội dung nghiên cứu | 1.5.1 quy trình · 1.5.2 công nghệ · 1.5.3 công cụ |
| 6. Những đóng góp chính | 1.6.1, 1.6.2, 1.6.3 |
| 7. Bố cục quyển luận văn | 1.7 |

Hai việc phải làm khi đóng quyển: đổi tiêu đề cấp một từ "CHƯƠNG 1 — GIỚI THIỆU"
thành "PHẦN GIỚI THIỆU", và **cắt bỏ khối "PHỤ CHÚ CHO TÁC GIẢ"** ở cuối tệp —
khối đó là ghi chú làm việc, không thuộc quyển.

**Chương 2** giữ nguyên 11 mục (2.1–2.11). Mục 1.7 của phần giới thiệu phải nói
đúng số chương của quyển này là **bốn**, không phải năm như một số bản nháp cũ.

**Chương 2 được viết sâu thêm ngày 17/08/2026.** Số mục cấp một không đổi, nhưng
bên trong thì khác nhiều, nên các điểm dưới đây cần biết trước khi đọc hoặc
sửa tiếp:

* **Khuôn lập luận thống nhất.** Mỗi quyết định kiến trúc lớn nay đi theo cùng
  một mạch: khái niệm → các phương án → bảng so sánh → yêu cầu của bài toán →
  định hướng được chọn → **đánh đổi mà lựa chọn đó mang theo**. Dòng cuối là
  dòng dễ bị cắt nhất khi rút gọn, và cũng là dòng hội đồng hỏi nhiều nhất —
  đừng cắt.
* **Chương 2 đã tách đôi với Phụ lục F, không mất nội dung nào.** Mười tám bảng
  so sánh rộng nay tồn tại ở hai mức: thân chương giữ các **tiêu chí quyết định**
  (5–9 dòng), phụ lục giữ **ma trận đầy đủ**. Đã kiểm bằng máy: **306/306 dòng
  bảng gốc còn nguyên** trong thân hoặc phụ lục, 18/18 bảng thân đều có câu dẫn
  chiếu nêu rõ phụ lục chứa tiêu chí nào. Bảng 2-43 từ 31 dòng rút thành bảng
  tóm tắt 17 nhóm; danh mục đầy đủ ở Bảng F-18.
  **Lưu ý khi rút gọn tiếp:** phần lớn dung lượng thân chương là **văn xuôi**
  (31.579 / 39.944 từ), nên chuyển thêm bảng sang phụ lục gần như không giảm số
  trang. Muốn giảm trang thì phải nén văn xuôi, và khi nén thì giữ đúng thứ tự
  ưu tiên: **lý do chọn và đánh đổi là phần cuối cùng được đụng tới.**
* **Bốn khối lý thuyết nền được bổ sung**, vì bản trước sâu về "chọn kiến trúc
  nào" nhưng nông về "cơ sở khoa học nào sinh ra các tiêu chí so sánh đó":
  mô hình hoá dữ liệu quan hệ (§2.1.6 — ba mức CDM/LDM/PDM, chuẩn hoá và phi
  chuẩn hoá có chủ đích, chiến lược khoá, bốn loại toàn vẹn); chất lượng dữ
  liệu và thời điểm kiểm tra (§2.1.4–2.1.5); ranh giới giao dịch và nhất quán
  xuyên kho (§2.7.3–2.7.4); mô hình đe doạ, nhật ký kiểm toán và khung nguồn
  gốc (§2.4.5, §2.5.9, §2.8.5).
* **Một phát biểu đã bị hạ mức, phải giữ nguyên mức đó.** Bản trước mô tả cưỡng
  chế ở tầng cơ sở dữ liệu gần với nghĩa "làm cho đường sai trở thành bất khả
  thi". §2.4.5 nay nêu **hai mô hình đe doạ** và Bảng 2-17 chỉ rõ: bảo đảm chỉ
  có hiệu lực khi kẻ tấn công **không** có thông tin xác thực cơ sở dữ liệu của
  ứng dụng. Câu đúng để dùng ở Chương 3, Chương 4 và Kết luận nằm nguyên văn
  trong §2.4.5. Đây là quy tắc phát biểu thứ tư, cùng hạng với ba quy tắc ở §9.
* **Mục 2.6 đã được dựng lại quanh "thu thập", không chỉ "biểu diễn".** Tên đề
  tài có hai vế ngang hàng — *thu thập* và *quản lý* — nhưng bản trước chỉ sâu ở
  vế thứ hai. §2.6 nay có mô hình phiên thu, ba phương thức thu nhận, chiến lược
  thu có hướng dẫn / mở / kết hợp, các chiều bao phủ, và khái niệm giao thức thu
  tách khỏi lược đồ. Phần điểm mốc lùi về đúng vai trò: **một kỹ thuật thu nhận**,
  không phải trục chính của mục. Xử lý tín hiệu thô (cắt ghép, chuẩn hoá khung,
  khử nhiễu, tăng cường dữ liệu) **cố ý nằm ngoài phạm vi** — đó là đường ống thị
  giác máy tính, không phải phân hệ thu thập.
* **Số hiệu bảng và hình đã đổi.** Chương 2 trước dùng dấu chấm (`Bảng 2.6`),
  lệch với ba chương còn lại; nay dùng dấu gạch theo đúng §4 của tệp này. Số
  lượng hiện là **43 bảng, 10 ô chờ hình**. Danh mục ở §5 và §6 được **sinh lại
  từ chính tệp chương**, nên khớp theo định nghĩa — nếu sửa bảng trong chương thì
  sinh lại danh mục, đừng sửa tay hai nơi.
* **Mười hai khoá trích dẫn mới — ĐÃ XÁC MINH XONG 17/08/2026.** Các khối lý
  thuyết bổ sung cần nguồn: Codd, Chen, Elmasri & Navathe (mô hình hoá dữ liệu);
  Härder & Reuter (ACID); Richardson (transactional outbox); Wang & Strong (chất
  lượng dữ liệu); Shostack (mô hình đe doạ); Moreau & Missier (PROV); Bass và
  Newman (kiểu kiến trúc); ISO/IEC 25010 (thuộc tính chất lượng); Pang và cs.
  (ReBAC). Toàn bộ ở `../SignBridge_Reference/BOSUNG_CHUONG2.bib`, mỗi mục có
  trường `annote` ghi kết quả xác minh. **Ba mục đã phải sửa:**

  | Mục | Sai ở bản soạn | Đã sửa thành |
  |---|---|---|
  | Zanzibar | tác giả "Christopher D. Richards" | **Christina** D. Richards |
  | Elmasri & Navathe | bản 7th ghi năm 2016 | **2015** (khoá đổi thành `elmasri_fundamentals_2015`) |
  | ISO/IEC 25010 | trích bản 2011 | **bản 2023** (bản 2011 đã bị huỷ và thay thế) — khoá `iso_25010_2023` |

  Về ISO 25010: bản 2023 đổi tên hai đặc tính (*usability* → *interaction
  capability*, *portability* → *flexibility*) và thêm *safety*. Bảng 2-1 chỉ dùng
  bốn tên **không đổi giữa hai bản**, nên trích bản 2023 là nhất quán. Nếu về sau
  thêm usability hoặc portability vào bảng thì **phải dùng tên mới**.

  Còn lại: **nhập vào Zotero trước khi dựng bản Word**. Tổng của Chương 2 nay là
  **64 khoá / 114 lượt trích**, nên `BANG_TRA_TRICH_DAN.md` cần sinh lại bằng
  `python scripts/sinh_bang_tra_trichdan.py`.
* **Provenance đã được nối sang Chương 3.** §2.8.5 (khung đối tượng – hoạt động –
  chủ thể) trước đó không có nơi nào dùng lại; nay Chương 3 nhóm M3 có một đoạn
  nối chuỗi *người ký → phiên thu → mẫu → bản thô/dẫn xuất → phiên bản bộ dữ liệu*
  về đúng khung đó, kèm giới hạn **43,4 %** và câu từ chối tuyên bố tuân thủ đầy
  đủ W3C PROV.
  **Cảnh báo:** con số 43,4 % là số liệu hiện trạng thuộc Chương 3 và Chương 4;
  **không được đưa ngược vào §2.8.5**. Chương 2 chỉ trình bày mô hình nguồn gốc và
  yêu cầu về tính đầy đủ của quan hệ, không nêu mức độ đạt được trên dữ liệu thật.
  Đây đúng là loại số dễ bị chép ngược lên phần lý thuyết nhất.
* **Tên hệ thống đã chốt: `CTU.SignBridge` (dấu chấm).** Dạng gạch nối
  `CTU-SignBridge` đã bị thay toàn bộ ngày 17/08/2026 (11 chỗ, bốn tệp) cho khớp
  tên chính thức của đề tài. **Chỉ đổi tên hệ thống trong văn bản** — định danh
  kỹ thuật thật sự dùng gạch nối hoặc gạch dưới (tên kho mã, tên máy, tên gói,
  tên bảng, biến môi trường) thì **giữ nguyên**, đừng đổi theo.
* **Phạm vi đóng góp đã được nói rõ.** §2.1.8 và Bảng 2-42 gọi đối tượng của
  luận văn là **phân hệ thu thập và quản lý dữ liệu ngôn ngữ ký hiệu**, không
  phải toàn bộ nền tảng CTU.SignBridge. Giữ cách gọi này ở Chương 3 và Kết luận.

---

## 3. Bảng tra cứu thuật ngữ

*Bảng 0-1: Bảng chú giải thuật ngữ*

| STT | Thuật ngữ / Viết tắt | Định nghĩa / Giải thích |
|---|---|---|
| 1 | **VSL** (Vietnamese Sign Language) | Ngôn ngữ Ký hiệu Việt Nam |
| 2 | **SaaS** (Software as a Service) | Mô hình cung cấp phần mềm dưới dạng dịch vụ, nhiều tổ chức dùng chung một bản triển khai |
| 3 | **Tenant** (tổ chức / đơn vị thuê bao) | Ranh giới quản trị logic cao nhất đối với dữ liệu nghiệp vụ, thành viên, quyền và cấu hình của một đơn vị. Dữ liệu tenant **được cô lập theo mặc định**; truy cập ra ngoài phạm vi chỉ hợp lệ qua cơ chế chia sẻ hoặc cấp quyền **tường minh và có quản trị** |
| 4 | **Multi-tenancy** (đa thuê bao) | Kiến trúc cho phép nhiều tenant dùng chung hạ tầng nhưng cách ly dữ liệu |
| 5 | **RLS** (Row-Level Security) | Cơ chế của PostgreSQL cưỡng chế điều kiện truy cập ở cấp hàng đối với truy vấn chạy dưới **những vai chịu RLS**. Trong luận văn, RLS đưa điều kiện phạm vi tenant ra khỏi trách nhiệm của truy vấn nghiệp vụ thông thường, **trong ranh giới tin cậy và mô hình đe doạ ở §2.4.5** |
| 6 | **GUC** (Grand Unified Configuration) | Biến cấu hình phiên của PostgreSQL; ở đây dùng `app.tenant_id` và `app.system_scope` để mang ngữ cảnh tenant |
| 7 | **Fail-closed** (mặc định từ chối) | Nguyên tắc: thiếu thông tin thì **từ chối**, không đoán. Đối lập là fail-open |
| 8 | **RBAC** (Role-Based Access Control) | Kiểm soát truy cập theo vai |
| 9 | **SOT** (Source of Truth — nguồn sự thật) | Bản dữ liệu được coi là đúng khi các bản sao mâu thuẫn nhau. Ở đây là `dataset/samples.csv` và các tạo tác danh mục đã ký |
| 10 | **Ed25519** | Lược đồ chữ ký số trên đường cong Edwards, dùng để ký các tạo tác nguồn sự thật |
| 11 | **Manifest** (bản kê) | Tệp liệt kê tên và mã băm SHA-256 của mọi tệp trong một bản công bố; chữ ký phủ lên bản kê chứ không lên từng tệp |
| 12 | **Tamper-evident** (bằng chứng giả mạo) | Sửa được nhưng không giấu được: mọi thay đổi đều để lại dấu vết phát hiện được. Khác với *tamper-proof* (chống sửa) |
| 13 | **Landmark** (điểm mốc) | Toạ độ các khớp bàn tay do mô hình thị giác trích ra; ở đây là 21 điểm × 3 toạ độ × 2 tay = 126 chiều/khung |
| 14 | **MediaPipe Hands** | Giải pháp ước lượng 21 điểm mốc bàn tay của MediaPipe. Trong đường thu của CTU.SignBridge, thành phần này được thực thi **phía máy khách** để tạo biểu diễn điểm mốc; chi tiết cách nhúng thuộc Chương 3 |
| 15 | **`.npz`** | Định dạng lưu trữ mảng số nhiều chiều có nén của NumPy; mỗi mẫu ký hiệu là một tệp `.npz` |
| 16 | **Class / lớp từ vựng** | Một đơn vị từ vựng cần nhận dạng (một từ, một chữ cái); là nhãn của mẫu |
| 17 | **Dialect** (phương ngữ) | Biến thể vùng miền của một ký hiệu; là **một phần của định danh lớp**, không phải thuộc tính phụ |
| 18 | **Registry** (danh mục có phiên bản) | Tập hợp lớp – phương ngữ – nhóm từ vựng của một tenant, được ghim phiên bản để tái lập được |
| 19 | **Consent** (đồng thuận) | Chấp thuận **có phiên bản** của chủ thể dữ liệu đối với một văn bản và một **phạm vi sử dụng** xác định. Ba phạm vi hiện dùng: huấn luyện nội bộ, phát hành nghiên cứu, thư viện công khai. Khác với giấy phép tái sử dụng và thoả thuận truy cập — xem §2.9.2 |
| 20 | **Signer** (người ký) | **Chủ thể dữ liệu** — người có bàn tay trong mẫu. Khác với tài khoản thu mẫu |
| 21 | **Celery / Broker** | Khung xử lý tác vụ bất đồng bộ; Redis đóng vai trung gian truyền tác vụ |
| 22 | **Idempotency** (tính lũy đẳng) | Chạy lại một thao tác nhiều lần cho cùng kết quả như chạy một lần |
| 23 | **CTIVR** (Cross-Tenant Isolation Violation Rate) | Tỉ lệ vi phạm cách ly xuyên tổ chức |
| 24 | **UASR** (Unauthorized Action Success Rate) | Tỉ lệ thao tác trái quyền thành công |
| 25 | **p50 / p95 / p99** | Phân vị 50/95/99 của phân bố độ trễ |
| 26 | **CDM / PDM** | Mô hình dữ liệu mức khái niệm / mức vật lý |
| 27 | **UC** (Use Case) | Trường hợp sử dụng |
| 28 | **SPA** (Single-Page Application) | Ứng dụng web một trang |
| 29 | **TOTP** (Time-based One-Time Password) | Mật khẩu dùng một lần theo thời gian, dùng cho xác thực hai yếu tố |
| 30 | **Soft delete** (xoá mềm) | Đánh dấu đã xoá thay vì xoá vật lý, cho phép khôi phục |
| 31 | **Toàn vẹn quan hệ** (relational integrity) | Dữ liệu thoả các ràng buộc cấu trúc của miền: khoá chính, khoá ngoài, miền giá trị, và **toàn vẹn xuyên phạm vi**. Xem Chương 2 §2.1.6 và §2.2.6 |
| 32 | **Toàn vẹn xuyên phạm vi** (cross-scope integrity) | Hai đối tượng có quan hệ với nhau phải cùng thuộc một tổ chức. Khoá ngoài thường chỉ bảo đảm đối tượng **tồn tại**, không bảo đảm nó **cùng phạm vi** |
| 33 | **Toàn vẹn lịch sử** (historical/version integrity) | Một phiên bản đã công bố tiếp tục biểu diễn đúng trạng thái tại thời điểm công bố. Cơ chế: phiên bản bất biến. Xem §2.8.1–2.8.2 |
| 34 | **Toàn vẹn nội dung** (content integrity) | Phát hiện được nội dung tệp/tạo tác bị thay đổi so với mã băm hoặc bản kê. Xem §2.8.6 |
| 35 | **Mô hình đe doạ** (threat model) | Phát biểu kèm theo mỗi khẳng định bảo mật: chống lại **ai**, có **năng lực gì**, với giả định nào về thành phần được tin cậy. Xem §2.4.5 |
| 36 | **Phiên thu** (collection session) | Bối cảnh chung của một nhóm mẫu được thu cùng nhau; đơn vị gắn người ký, người vận hành, phương thức thu và trạng thái đồng thuận. Xem §2.6.1 |
| 37 | **Độ bao phủ** (coverage) | Phân bố dữ liệu trên các chiều lớp × người ký × vùng × phiên thu. Nền tảng cung cấp siêu dữ liệu cần thiết để độ bao phủ **có thể được định lượng và quản trị**, nhưng **không tự bảo đảm** tính cân bằng hay tính đại diện của dữ liệu. Xem §2.6.4 |

**Ba từ "toàn vẹn" ở các dòng 31, 33, 34 là ba khái niệm khác nhau — không dùng thay
nhau.** Câu "hệ thống bảo đảm tính toàn vẹn dữ liệu" là câu mơ hồ và không nên xuất
hiện trong quyển. Viết cụ thể: *"ràng buộc tổ hợp giữ toàn vẹn tham chiếu xuyên phạm
vi"*, hoặc *"xác minh mã băm phát hiện thay đổi nội dung của một tạo tác đã công bố"*,
hoặc *"tham chiếu phiên bản bất biến giữ toàn vẹn lịch sử của một bản phát hành"*.

---

## 4. Quy ước đánh số hình và bảng

Mẫu của trường đánh số theo dạng `Hình <n>-<m>` / `Bảng <n>-<m>`. Quyển này lấy
**`n` = số hiệu chương**, `m` = thứ tự xuất hiện trong chương:

```
Hình 3-5   →  hình thứ 5 của Chương 3
Bảng 4-2   →  bảng thứ 2 của Chương 4
Bảng 0-1   →  bảng thuộc phần đầu quyển (bảng thuật ngữ)
Hình A-1   →  hình thứ 1 của Phụ lục A
```

Hình và bảng trong **Phần giới thiệu** dùng tiền tố `0`.

### Ô chờ hình

Mọi chỗ cần hình trong bản thảo được đánh dấu bằng một khối như sau, để khi dựng
bản Word chỉ việc thay khối bằng ảnh và giữ nguyên dòng chú thích:

```
> ### ▣ HÌNH 3-2 — Kiến trúc triển khai 14 dịch vụ
> **Loại:** sơ đồ khối · **Công cụ đề nghị:** draw.io
> **Nguồn dựng:** docker-compose.yml + docker-compose.prod.yml
> **Phải thể hiện:** ... (liệt kê phần tử bắt buộc có)
> **Chú thích dưới hình:** *Hình 3-2: Kiến trúc triển khai ...*
```

Ô chờ hình **không phải chỗ trống**: nó nêu rõ hình phải chứa gì, để người vẽ
không vẽ ra một hình đẹp nhưng không chứng minh được điều thân bài đang nói.

---

## 5. Danh mục hình — khung

Điền số trang sau khi dựng bản Word. Danh sách này là **đầu ra của các ô chờ
hình** trong bốn chương; giữ đồng bộ hai chiều.

| Hình | Tên | Ở đâu |
|---|---|---|
| Hình 0-1 | Quy trình nghiên cứu | Phần giới thiệu, mục 5.1 |
| Hình 1-1 | Sơ đồ use case tổng quát — tác nhân và 8 nghiệp vụ | Ch1 §2 |
| Hình 1-2 | Cây kế thừa tác nhân | Ch1 §2.1 |
| Hình 1-3 | Use case Nghiệp vụ 1 — Danh tính và quyền truy cập | Ch1 §2.1 |
| Hình 1-4 | Use case Nghiệp vụ 2 — Thu thập và quản lý dữ liệu mẫu | Ch1 §2.2 |
| Hình 1-5 | Use case Nghiệp vụ 3 — Danh mục từ vựng và phương ngữ | Ch1 §2.3 |
| Hình 1-6 | Use case Nghiệp vụ 4 — Huấn luyện, đánh giá và suy luận | Ch1 §2.4 |
| Hình 1-7 | Use case Nghiệp vụ 5–8 — Quản trị, vận hành và tích hợp | Ch1 §2.5 |
| Hình 1-8 | Vòng đời một mẫu dữ liệu xuyên ba nghiệp vụ | Ch1 §1.4 |
| Hình 2-1 | Chuỗi biểu diễn từ tín hiệu nguồn đến đặc trưng dẫn xuất | Ch2 §2.1.2 |
| Hình 2-2 | Bốn mức chia sẻ tài nguyên trong kiến trúc đa thuê bao | Ch2 §2.2.2 |
| Hình 2-3 | Hai cách tham chiếu nội dung và phạm vi bảo đảm của từng cách | Ch2 §2.2.9 |
| Hình 2-4 | Ba cách chia sẻ danh mục và sự phụ thuộc vào trạng thái thượng nguồn | Ch2 §2.3.4 |
| Hình 2-5 | Năm tầng cần cô lập trên đường đi của một yêu cầu | Ch2 §2.4.1 |
| Hình 2-6 | Hai mô hình đe dọa và ranh giới tin cậy của cơ chế cô lập | Ch2 §2.4.5 |
| Hình 2-7 | Cấu trúc 21 điểm mốc bàn tay của MediaPipe Hands | Ch2 §2.6.6 |
| Hình 2-8 | Ba mô hình quản lý phiên bản bộ dữ liệu | Ch2 §2.8.2 |
| Hình 2-9 | Chuỗi nguồn gốc theo khung đối tượng – hoạt động – chủ thể | Ch2 §2.8.5 |
| Hình 2-10 | Vòng đời dữ liệu và vòng đời quản trị với các cổng kiểm soát | Ch2 §2.11.1 |
| Hình 3-1 | Bối cảnh sản phẩm và các bên liên quan | Ch3 §1.1 |
| Hình 3-2 | Kiến trúc triển khai 15 dịch vụ container | Ch3 §2.1 |
| Hình 3-3 | Tương tác giữa các thành phần khi thu một mẫu | Ch3 §2.2 |
| Hình 3-4 | Bốn tầng cưỡng chế cách ly tổ chức | Ch3 §2.3 |
| Hình 3-5 | Mô hình dữ liệu theo bảy nhóm mô-đun | Ch3 §3.1 |
| Hình 3-6 | Nhóm M1 + M2: Danh tính, Tổ chức và Phân quyền | Ch3 §3.1 |
| Hình 3-7 | Nhóm M3: Kho dữ liệu mẫu | Ch3 §3.1 |
| Hình 3-8 | Nhóm M4: Danh mục ba mặt phẳng | Ch3 §3.1 |
| Hình 3-9 | Luồng xử lý bất đồng bộ của một bản ghi | Ch3 §4.2 |
| Hình 3-10 | Vòng đời trạng thái của một mẫu | Ch3 §4.2 |
| Hình 3-11 | Cơ chế công bố và xác minh nguồn sự thật | Ch3 §4.5 |
| Hình 3-12 | Luồng huấn luyện và ba cổng chặn | Ch3 §4.6 |
| Hình 3-13 | Kiến trúc nhận dạng thời gian thực | Ch3 §4.7 |
| Hình 3-14 | Giao diện thu mẫu trực tiếp | Ch3 §5 |
| Hình 3-15 | Giao diện danh mục lớp và chi tiết lớp | Ch3 §5 |
| Hình 3-16 | Giao diện console quản trị | Ch3 §5 |
| Hình 4-1 | Hai nền chạy kiểm thử và câu hỏi mỗi nền trả lời | Ch4 §3.2 |
| Hình 4-2 | Bốn lớp bằng chứng của phép đo cách ly | Ch4 §5.2 |
| Hình 4-3 | Phân bố độ trễ theo điểm cuối | Ch4 §5.3 |
| Hình 4-4 | Phân bố dung lượng mẫu và tỉ lệ giảm | Ch4 §5.4 |
| Hình A-1 | Mô hình dữ liệu mức khái niệm (CDM) | Phụ lục A §2 |
| Hình A-2 … A-8 | Mô hình vật lý (PDM) theo bảy nhóm mô-đun | Phụ lục A §3 |

## 6. Danh mục bảng — khung

| Bảng | Tên | Ở đâu |
|---|---|---|
| Bảng 0-1 | Bảng chú giải thuật ngữ | Phần đầu quyển |
| Bảng 1-1 | Bốn nhóm tác nhân | Ch1 §2 |
| Bảng 1-2 | Chi tiết 10 tác nhân người và cơ chế phân biệt | Ch1 §2 |
| Bảng 1-3 | Sáu tác nhân hệ thống | Ch1 §2 |
| Bảng 1-4 | Ma trận tác nhân × nghiệp vụ | Ch1 §2 |
| Bảng 1-5 | Tám nhóm nghiệp vụ | Ch1 §2 |
| Bảng 1-6 … 1-13 | Danh sách use case theo từng nghiệp vụ (8 bảng) | Ch1 §2.1–2.8 |
| Bảng 1-14 … 1-21 | Mô tả chức năng chi tiết 8 use case trục chính | Ch1 §2.1–2.8 |
| Bảng 1-22 | Yêu cầu thực thi | Ch1 §3.1 |
| Bảng 1-23 | Yêu cầu an toàn thông tin | Ch1 §3.2 |
| Bảng 1-24 | Yêu cầu bảo mật | Ch1 §3.3 |
| Bảng 1-25 | Yêu cầu về tính tin cậy | Ch1 §3.4 |
| Bảng 1-26 | Yêu cầu về tính duy trì được | Ch1 §3.5 |
| Bảng 1-27 | Ràng buộc thực thi | Ch1 §4.1 |
| Bảng 1-28 | Ràng buộc thiết kế | Ch1 §4.2 |
| Bảng 2-1 | Các thuộc tính chất lượng dùng làm tiêu chí so sánh trong chương | Ch2 § |
| Bảng 2-2 | Bốn nhóm đặc trưng dữ liệu và ràng buộc phát sinh đối với nền tảng | Ch2 §2.1.1 |
| Bảng 2-3 | Siêu dữ liệu tối thiểu và câu hỏi mà mỗi nhóm cho phép trả lời | Ch2 §2.1.3 |
| Bảng 2-4 | Sáu chiều chất lượng dữ liệu và cơ chế kiểm tra tương ứng | Ch2 §2.1.4 |
| Bảng 2-5 | So sánh ba thời điểm kiểm tra chất lượng | Ch2 §2.1.5 |
| Bảng 2-6 | Ba mức mô hình dữ liệu | Ch2 §2.1.6 |
| Bảng 2-7 | Chuẩn hóa và phi chuẩn hóa có chủ đích | Ch2 §2.1.6 |
| Bảng 2-8 | So sánh ba cách tổ chức định danh | Ch2 §2.1.6 |
| Bảng 2-9 | Bốn loại toàn vẹn ở tầng cơ sở dữ liệu quan hệ | Ch2 §2.1.6 |
| Bảng 2-10 | Định vị đề tài theo giai đoạn vòng đời và phạm vi quản trị | Ch2 §2.1.8 |
| Bảng 2-11 | Bốn mức chia sẻ tài nguyên trong kiến trúc đa thuê bao | Ch2 §2.2.2 |
| Bảng 2-12 | So sánh ba mô hình tổ chức dữ liệu đa thuê bao | Ch2 §2.2.7 |
| Bảng 2-13 | Các yêu cầu khi nội dung nằm ngoài cơ sở dữ liệu | Ch2 §2.2.9 |
| Bảng 2-14 | Ba phạm vi quản trị dữ liệu | Ch2 §2.3.1 |
| Bảng 2-15 | So sánh ba cách chia sẻ danh mục giữa nền tảng và tenant | Ch2 §2.3.4 |
| Bảng 2-16 | Năm tầng cần cô lập và câu hỏi mà mỗi tầng trả lời | Ch2 §2.4.1 |
| Bảng 2-17 | Phạm vi bảo đảm của các cơ chế theo mô hình đe dọa | Ch2 §2.4.5 |
| Bảng 2-18 | So sánh bốn chiến lược cưỡng chế cô lập dữ liệu | Ch2 §2.4.9 |
| Bảng 2-19 | So sánh năm mô hình kiểm soát truy cập | Ch2 §2.5.7 |
| Bảng 2-20 | So sánh phiên có trạng thái và token tự chứa | Ch2 §2.5.8 |
| Bảng 2-21 | Nhật ký vận hành và nhật ký kiểm toán | Ch2 §2.5.9 |
| Bảng 2-22 | Các câu hỏi kiểm soát và cơ chế tương ứng | Ch2 §2.5.10 |
| Bảng 2-23 | So sánh ba phương thức thu nhận dữ liệu | Ch2 §2.6.2 |
| Bảng 2-24 | So sánh ba chiến lược thu thập | Ch2 §2.6.3 |
| Bảng 2-25 | Các chiều bao phủ và câu hỏi tương ứng | Ch2 §2.6.4 |
| Bảng 2-26 | So sánh các mức biểu diễn dữ liệu thu nhận | Ch2 §2.6.6 |
| Bảng 2-27 | So sánh trích xuất tại máy khách và tại máy chủ | Ch2 §2.6.7 |
| Bảng 2-28 | So sánh xử lý đồng bộ và xử lý bất đồng bộ | Ch2 §2.7.1 |
| Bảng 2-29 | So sánh ba chiến lược nhất quán giữa cơ sở dữ liệu và kho nội dung | Ch2 §2.7.4 |
| Bảng 2-30 | So sánh lưu nội dung trong cơ sở dữ liệu và lưu bên ngoài | Ch2 §2.7.5 |
| Bảng 2-31 | So sánh ba mô hình quản lý phiên bản bộ dữ liệu | Ch2 §2.8.2 |
| Bảng 2-32 | Ba nghĩa của "toàn vẹn" và cơ chế tương ứng | Ch2 §2.8.4 |
| Bảng 2-33 | Ánh xạ khung đối tượng – hoạt động – chủ thể vào miền ứng dụng | Ch2 §2.8.5 |
| Bảng 2-34 | Ba cơ chế và thuộc tính mà mỗi cơ chế thực sự bảo đảm | Ch2 §2.8.6 |
| Bảng 2-35 | Bốn lớp cho phép và điều kiện sử dụng | Ch2 §2.9.2 |
| Bảng 2-36 | So sánh đồng thuận nhị phân và đồng thuận có phiên bản | Ch2 §2.9.3 |
| Bảng 2-37 | Các mức xử lý liên quan đến thu hồi và xóa | Ch2 §2.9.4 |
| Bảng 2-38 | So sánh ba kiểu kiến trúc phần mềm | Ch2 §2.10.1 |
| Bảng 2-39 | Ba cách đóng gói đơn vị triển khai | Ch2 §2.10.2 |
| Bảng 2-40 | Phân biệt cấu hình triển khai và cấu hình tenant | Ch2 §2.10.2 |
| Bảng 2-41 | Các cổng nối vòng đời dữ liệu và vòng đời quản trị | Ch2 §2.11.1 |
| Bảng 2-42 | Đối chiếu các hệ thống liên quan theo tiêu chí của chương | Ch2 §2.11.2 |
| Bảng 2-43 | Tóm tắt các nhóm quyết định kiến trúc và định hướng được chọn | Ch2 §2.11.4 |
| Bảng F-1 | So sánh ba mô hình tổ chức dữ liệu đa thuê bao | Phụ lục §F.2.1 |
| Bảng F-2 | So sánh ba cách chia sẻ danh mục giữa nền tảng và tenant | Phụ lục §F.3.1 |
| Bảng F-3 | So sánh bốn chiến lược cưỡng chế cô lập dữ liệu | Phụ lục §F.4.1 |
| Bảng F-4 | So sánh năm mô hình kiểm soát truy cập | Phụ lục §F.5.1 |
| Bảng F-5 | So sánh phiên có trạng thái và token tự chứa | Phụ lục §F.5.2 |
| Bảng F-6 | Nhật ký vận hành và nhật ký kiểm toán | Phụ lục §F.5.3 |
| Bảng F-7 | So sánh ba phương thức thu nhận dữ liệu | Phụ lục §F.6.1 |
| Bảng F-8 | So sánh ba chiến lược thu thập | Phụ lục §F.6.2 |
| Bảng F-9 | So sánh các mức biểu diễn dữ liệu thu nhận | Phụ lục §F.6.3 |
| Bảng F-10 | So sánh trích xuất tại máy khách và tại máy chủ | Phụ lục §F.6.4 |
| Bảng F-11 | So sánh xử lý đồng bộ và xử lý bất đồng bộ | Phụ lục §F.7.1 |
| Bảng F-12 | So sánh ba chiến lược nhất quán giữa cơ sở dữ liệu và kho nội dung | Phụ lục §F.7.2 |
| Bảng F-13 | So sánh lưu nội dung trong cơ sở dữ liệu và lưu bên ngoài | Phụ lục §F.7.3 |
| Bảng F-14 | So sánh ba mô hình quản lý phiên bản bộ dữ liệu | Phụ lục §F.8.1 |
| Bảng F-15 | So sánh đồng thuận nhị phân và đồng thuận có phiên bản | Phụ lục §F.9.1 |
| Bảng F-16 | So sánh ba kiểu kiến trúc phần mềm | Phụ lục §F.10.1 |
| Bảng F-17 | Đối chiếu các hệ thống liên quan theo tiêu chí của chương | Phụ lục §F.11.1 |
| Bảng F-18 | Tổng hợp các quyết định kiến trúc, phương án và cơ sở lựa chọn | Phụ lục §F.11.2 |
| Bảng 3-1 | So sánh ba mô hình cách ly dữ liệu đa tổ chức | Ch3 §2.3 |
| Bảng 3-2 | So sánh phương án biểu diễn dữ liệu | Ch3 §2.3 |
| Bảng 3-3 | So sánh phương án tổ chức bước xử lý | Ch3 §2.3 |
| Bảng 3-4 | So sánh phương án thẩm quyền ký | Ch3 §2.3 |
| Bảng 3-5 | Bảy nhóm mô-đun dữ liệu | Ch3 §3.1 |
| Bảng 3-6 | Danh mục bảng dữ liệu theo nhóm (tóm tắt) | Ch3 §3.2 |
| Bảng 3-7 | Các quan hệ then chốt và lực lượng | Ch3 §3.3 |
| Bảng 3-8 | Ba miền dữ liệu và ranh giới | Ch3 §3.4 |
| Bảng 3-9 | Bộ định tuyến và số điểm cuối | Ch3 §4.1 |
| Bảng 3-10 | Ba cổng chặn huấn luyện | Ch3 §4.6 |
| Bảng 4-1 | Các chức năng được kiểm thử | Ch4 §2.1 |
| Bảng 4-2 | Tiêu chí đạt / không đạt | Ch4 §2.3 |
| Bảng 4-3 | Sản phẩm bàn giao kiểm thử | Ch4 §2.5 |
| Bảng 4-4 | Môi trường kiểm thử | Ch4 §3.2 |
| Bảng 4-5 | Rủi ro kiểm thử | Ch4 §3.6 |
| Bảng 4-6 | Kịch bản kiểm thử | Ch4 §4 |
| Bảng 4-7 … 4-14 | Ca kiểm thử chức năng theo nghiệp vụ | Ch4 §5.1 |
| Bảng 4-15 | Kết quả đo cách ly xuyên kho | Ch4 §5.2 |
| Bảng 4-16 | Kết quả đo độ trễ dịch vụ | Ch4 §5.3 |
| Bảng 4-17 | Kết quả đo hiệu quả lưu trữ | Ch4 §5.4 |
| Bảng 4-18 | Ma trận giả mạo nguồn sự thật | Ch4 §5.5 |
| Bảng 4-19 | Đối chiếu mục tiêu đề tài với kết quả | Ch4 §6 |

---

## 7. Tóm tắt và Abstract

### TÓM TẮT

Ngôn ngữ Ký hiệu Việt Nam là ngôn ngữ tự nhiên của cộng đồng người khiếm thính –
khiếm ngôn, nhưng thuộc nhóm ngôn ngữ **ít tài nguyên**: dữ liệu huấn luyện phân
tán ở từng nhóm nghiên cứu, khác nhau về quy ước gán nhãn, và hầu như không dùng
lại được giữa các nhóm. Trong phạm vi các lớp công cụ được khảo sát ở luận văn,
chưa thấy một nền tảng đơn lẻ nào kết hợp đồng thời thu nhận chuyên biệt cho ngôn
ngữ ký hiệu, quản trị nhiều tổ chức, và quản trị nguồn gốc cùng phiên bản ngay từ
thời điểm thu.

Luận văn thiết kế, hiện thực và đánh giá **phân hệ SaaS đa thuê bao phục vụ thu
thập và quản lý dữ liệu Ngôn ngữ Ký hiệu Việt Nam trong CTU.SignBridge** — tức
phần thu nhận, tổ chức, quản lý và quản trị vòng đời dữ liệu, chứ không phải toàn
bộ nền tảng. Đóng góp trọng tâm là **cách ly dữ liệu giữa các tổ chức được
cưỡng chế ở tầng cơ sở dữ liệu**, theo một mệnh đề kiểm chứng được: *một truy vấn
không khai báo tổ chức trả về không hàng nào, và ứng dụng không tự vô hiệu hoá
được cơ chế đó*. Cơ chế gồm bốn tầng — cột phân biệt, chính sách bảo mật mức
hàng, phạm vi giao dịch, và tách vai cơ sở dữ liệu — mỗi tầng bịt một lối vòng mà
ba tầng còn lại để hở.

Hệ thống còn giải quyết bốn bài toán mà một công cụ thu dữ liệu thông thường
không đặt ra: với các luồng thu chỉ yêu cầu điểm mốc, việc trích xuất ngay tại
trình duyệt cho phép video thô không phải rời khỏi máy người đóng góp; danh mục từ vựng ba mặt
phẳng có ghim phiên bản để một bộ dữ liệu tái lập được; nguồn sự thật ký số bằng
Ed25519 với xác minh **fail-closed**; và cơ chế đồng thuận có phiên bản gắn với
**chủ thể dữ liệu** chứ không gắn với tài khoản thu.

Kết quả được đánh giá trên bốn trục, bằng các phép đo có khả năng thất bại và có
đối chứng dương. Phép đo cách ly đối kháng qua đường API, thực hiện trên một
phiên bản mã đã ghim, cho tỉ lệ vi phạm xuyên tổ chức **0/450** và tỉ lệ thao tác
trái quyền lọt **0/180**, không còn ca nào không kết luận được. Biểu diễn điểm mốc giảm **92,2 %** dung lượng so với video
gốc trên 54 cặp khớp thời lượng. Ma trận chín kịch bản giả mạo nguồn sự thật đạt
tám thuộc tính và phát hiện một giới hạn thật về thứ tự phiên bản. Luận văn nêu
thẳng các giới hạn đó thay vì làm tròn chúng thành kết quả.

**Từ khoá:** ngôn ngữ ký hiệu Việt Nam, SaaS đa thuê bao, cách ly dữ liệu,
row-level security, thu thập dữ liệu, nguồn sự thật ký số, đồng thuận dữ liệu.

### ABSTRACT

Vietnamese Sign Language is the natural language of the Vietnamese Deaf
community, yet it remains a **low-resource** language: training data is scattered
across individual research groups, annotated under incompatible conventions, and
seldom reusable across groups. Among the classes of systems reviewed in this
thesis, no single platform was found to combine domain-specific sign language
acquisition, multi-organisational governance, and provenance and version
management from the point of collection.

This thesis designs, implements and evaluates the **multi-tenant SaaS subsystem
for Vietnamese Sign Language data collection and management within
CTU.SignBridge** — the acquisition, organisation, management and lifecycle
governance of the data, rather than the platform as a whole.
Its central contribution is **cross-organisation data isolation enforced at the
database layer**, stated as a testable proposition: *a query that does not
declare its organisation returns zero rows, and the application cannot switch
that mechanism off*. The mechanism has four layers — discriminator column,
row-level security policy, transaction-scoped context, and database role
separation — each closing a bypass the other three leave open.

The system further addresses four problems an ordinary collection tool does not
raise: for landmark-only acquisition flows, browser-side extraction allows the raw
video to remain on the contributor's device; a three-plane, version-pinned vocabulary
registry that makes a dataset reproducible; an Ed25519-signed source of truth
with **fail-closed** verification; and versioned consent bound to the **data
subject** rather than to the capturing account.

Results are evaluated along four axes using measurements designed to be capable
of failing and equipped with positive controls. Adversarial isolation probing
through the public API, run against a pinned code revision, yields a cross-tenant
violation rate of **0/450** and an unauthorised-action success rate of **0/180**,
with no inconclusive cases. The
landmark representation reduces storage by **92.2 %** against source video over
54 duration-matched pairs. A nine-scenario source-of-truth tampering matrix
satisfies eight properties and surfaces one genuine limitation in version
ordering. These limitations are reported as found rather than rounded into
results.

**Keywords:** Vietnamese Sign Language, multi-tenant SaaS, data isolation,
row-level security, data collection, signed source of truth, data consent.

---

## 8. Quy ước trích dẫn

Quyển soạn trên Word, thư mục trích dẫn lấy từ **Zotero**, không từ tệp `.bib`.
Bản thảo markdown trong thư mục này đánh dấu trích dẫn bằng khoá dạng
`[@kleppmann_designing_2017]`. Khi chuyển sang Word:

1. Tra khoá trong `../BANG_TRA_TRICH_DAN.md`, lấy cột **Tiêu đề**.
2. Dán tiêu đề vào hộp *Add/Edit Citation* (`Ctrl+Alt+C`) của Zotero.
3. Kiểm bốn cặp dễ nhầm nêu ở cuối bảng tra — Word vẫn chèn bình thường khi chọn
   nhầm, và không công cụ nào bắt được.

Khoá trong `.bib` đổi mỗi lần xuất lại từ Zotero, nên **không** coi khoá là thứ
bền vững; nó chỉ để tra ngược về bản thảo.

---

## 9. Bảy quy tắc phát biểu giữ xuyên suốt quyển

Các phát biểu dưới đây đã bị hạ mức có chủ đích sau khi đối chiếu với mã nguồn và
kết quả đo. Chúng phải nhất quán ở **Tóm tắt, Chương 3, Chương 4 và Kết luận** —
lệch một chỗ là một câu hỏi phản biện không trả lời được.

| Chủ đề | **Không viết** | **Viết** |
|---|---|---|
| Phân quyền | triển khai đầy đủ ở bốn cấp phạm vi | kiến trúc hỗ trợ nhiều cấp; cưỡng chế hiện chứng minh được ở cấp hệ thống và cấp tổ chức |
| Bất đồng bộ | bảo đảm thử lại an toàn và lũy đẳng | thực hiện bất đồng bộ bốn năng lực; thử lại và tính lũy đẳng chưa đồng đều giữa các đường |
| Nguồn sự thật | bảo đảm trạng thái mới nhất luôn thắng | cung cấp bằng chứng giả mạo và xác thực nguồn ký; chưa cưỡng chế đơn điệu phiên bản |
| **Cách ly tổ chức** | cơ chế khiến việc truy cập chéo tổ chức trở thành **bất khả thi trong mọi trường hợp** | cơ chế **đưa điều kiện phạm vi ra khỏi trách nhiệm của truy vấn nghiệp vụ thông thường** và loại bỏ lớp lỗi thiếu điều kiện lọc, **trong phạm vi mô hình đe doạ đã nêu ở Chương 2 §2.4.5** |
| **Độ bao phủ dữ liệu** | nền tảng bảo đảm bộ dữ liệu cân bằng hoặc đại diện | nền tảng lưu đủ siêu dữ liệu để độ bao phủ **có thể được định lượng và quản trị** trên các chiều lớp × người ký × vùng × phiên thu |
| **Toàn vẹn** | "hệ thống bảo đảm tính toàn vẹn dữ liệu" | nêu rõ **nghĩa nào** trong ba nghĩa ở §3 (quan hệ / lịch sử / nội dung) |
| **Ranh giới Chương 2** | "kết quả cho thấy…", "đạt X %", "đã kiểm thử…", "thực nghiệm chứng minh…" xuất hiện trong Chương 2 | Chương 2 chỉ nêu nguyên lý, phương án, tiêu chí, định hướng và đánh đổi; số liệu và bằng chứng thực nghiệm thuộc Chương 4 |

**Quy tắc về nguồn của số liệu.** Kết quả thực nghiệm **gốc** được trình bày và
phân tích ở Chương 4. Tóm tắt, Abstract và Kết luận **được phép nhắc lại** những
kết quả chính đã trình bày đầy đủ ở Chương 4, nhưng **không được giới thiệu một
phép đo hay một con số chỉ xuất hiện ở đó**. Nói cách khác: Chương 4 là nguồn,
Tóm tắt và Kết luận là bản tóm lược của nguồn, Chương 2 không có số liệu.

**Quy tắc về cách viết một con số.** Mọi số liệu thực nghiệm phải đi kèm ngữ cảnh
đủ để kiểm chứng: **đơn vị đo, kích thước hoặc mẫu số của tập quan sát, điều kiện
và môi trường đo**, và — **khi đại lượng có phân bố** — thống kê phân bố hoặc
khoảng biến thiên phù hợp. Không phải số nào cũng có phân bố: `0/450` cần mẫu số
và điều kiện đo, còn độ trễ thì cần thêm phân vị. Con số trần trụi là con số không
kiểm chứng được.

**Về quy tắc cách ly tổ chức.** Mệnh đề trung tâm của quyển — *"một truy vấn không
khai báo tổ chức trả về 0 hàng, và ứng dụng không tự vô hiệu hoá được cơ chế đó"* —
vẫn đúng và vẫn giữ nguyên. Điều phải kèm theo là **ranh giới của nó**: mệnh đề đó
nói về đường truy vấn của ứng dụng, không phải về một kẻ tấn công đã chiếm được
thông tin xác thực cơ sở dữ liệu. Chương 2 §2.4.5 và Bảng 2-17 định nghĩa hai mô
hình đe doạ; Chương 4 báo cáo kết quả đo **trong mô hình thứ nhất**. Không mở rộng
kết luận sang mô hình thứ hai ở bất kỳ chương nào.
